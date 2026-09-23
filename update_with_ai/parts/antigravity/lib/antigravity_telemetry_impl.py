# Requirements specified in antigravity_telemetry_impl.pyi
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)
if not os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
    os.environ["BUILD_WORKSPACE_DIRECTORY"] = _repo_root

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, system
from . import antigravity_telemetry

PRICING_TABLE = {
    "gemini-3.8-flash": {"cached_input": 0.50, "fresh_input": 2.00, "output": 12.00},
    "gemini-flash": {"cached_input": 0.50, "fresh_input": 2.00, "output": 12.00},
    "deepseek": {"cached_input": 0.14, "fresh_input": 0.28, "output": 2.19},
}
PRICING_MODELS = PRICING_TABLE
_DEFAULT_DB_DIR = os.path.expanduser("~/.gemini/antigravity/conversations")
_DEFAULT_BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity/brain")


def _decode_varint(data: bytes, i: int) -> Tuple[int, int]:
    val = 0
    shift = 0
    while True:
        if i >= len(data):
            break
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, i


def _decode_pb(data: bytes) -> Dict[int, List[Any]]:
    i = 0
    res: Dict[int, List[Any]] = {}
    while i < len(data):
        tag, i = _decode_varint(data, i)
        wire = tag & 7
        fnum = tag >> 3
        if wire == 0:  # varint
            val, i = _decode_varint(data, i)
            res.setdefault(fnum, []).append(val)
        elif wire == 2:  # length-delimited
            length, i = _decode_varint(data, i)
            sub = data[i : i + length]
            i += length
            res.setdefault(fnum, []).append(sub)
        elif wire == 1:  # 64-bit
            i += 8
        elif wire == 5:  # 32-bit
            i += 4
        else:
            break
    return res


class AntigravityTelemetry(antigravity_telemetry.AntigravityTelemetry, Singleton):
    tier = system

    def calculate_cost(self, fresh_tokens: int, cached_tokens: int, output_tokens: int, model: str = "gemini-3.8-flash") -> float:
        rates = PRICING_TABLE.get(model.lower(), PRICING_TABLE["gemini-3.8-flash"])
        cost = (
            (cached_tokens / 1_000_000.0) * rates["cached_input"]
            + (fresh_tokens / 1_000_000.0) * rates["fresh_input"]
            + (output_tokens / 1_000_000.0) * rates["output"]
        )
        return round(cost, 4)

    def get_conversation_stats(self, identifier: str) -> Optional[antigravity_telemetry.ConversationStats]:
        db_dir = os.path.expanduser("~/.gemini/antigravity/conversations")
        db_path = os.path.join(db_dir, f"{identifier}.db")
        if not os.path.isfile(db_path):
            return None

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT idx, metadata FROM steps WHERE metadata IS NOT NULL ORDER BY idx;")
            rows = cur.fetchall()
            conn.close()
        except Exception:
            return None

        turns = 0
        fresh_in = 0
        cached_in = 0
        output = 0
        last_context = 0

        for _idx, meta in rows:
            if not meta:
                continue
            try:
                d = _decode_pb(meta)
                if 9 in d and d[9]:
                    sub = _decode_pb(d[9][0])
                    ints = {k: v[0] for k, v in sub.items() if isinstance(v[0], int)}
                    if 2 in ints or 5 in ints or 3 in ints:
                        turns += 1
                        step_fresh = ints.get(2, 0)
                        step_cached = ints.get(5, 0)
                        fresh_in += step_fresh
                        cached_in += step_cached
                        output += ints.get(3, 0)
                        last_context = step_fresh + step_cached
            except Exception:
                continue

        total_in = fresh_in + cached_in
        hit_pct = round((cached_in / total_in * 100.0), 1) if total_in > 0 else 0.0
        cost = self.calculate_cost(fresh_in, cached_in, output)

        return antigravity_telemetry.ConversationStats(
            agent_name=identifier,
            turns=turns,
            context_tokens=last_context,
            fresh_input_tokens=fresh_in,
            cached_input_tokens=cached_in,
            cache_hit_percentage=hit_pct,
            output_tokens=output,
            estimated_cost_dollars=cost,
        )

    def get_coordinator_run_stats(self, coordinator_id: str) -> Sequence[antigravity_telemetry.ConversationStats]:
        results: List[antigravity_telemetry.ConversationStats] = []
        coord_stats = self.get_conversation_stats(coordinator_id)
        if coord_stats:
            results.append(antigravity_telemetry.ConversationStats(
                agent_name="Coordinator",
                turns=coord_stats.turns,
                context_tokens=coord_stats.context_tokens,
                fresh_input_tokens=coord_stats.fresh_input_tokens,
                cached_input_tokens=coord_stats.cached_input_tokens,
                cache_hit_percentage=coord_stats.cache_hit_percentage,
                output_tokens=coord_stats.output_tokens,
                estimated_cost_dollars=coord_stats.estimated_cost_dollars,
            ))

        brain_dir = os.path.expanduser("~/.gemini/antigravity/brain")
        subagent_pattern = os.path.join(brain_dir, coordinator_id, ".system_generated", "subagents", "*.json")
        idx = 1
        for sa_path in sorted(glob.glob(subagent_pattern)):
            cid = os.path.splitext(os.path.basename(sa_path))[0]
            desc: Dict[str, Any] = {}
            try:
                with open(sa_path, "r", encoding="utf-8") as f:
                    desc = json.load(f).get("subagentDescriptor", {})
            except Exception:
                pass
            role = desc.get("role", "worker")
            w_stats = self.get_conversation_stats(cid)
            if w_stats:
                results.append(antigravity_telemetry.ConversationStats(
                    agent_name=f"Worker {idx} ({role})",
                    turns=w_stats.turns,
                    context_tokens=w_stats.context_tokens,
                    fresh_input_tokens=w_stats.fresh_input_tokens,
                    cached_input_tokens=w_stats.cached_input_tokens,
                    cache_hit_percentage=w_stats.cache_hit_percentage,
                    output_tokens=w_stats.output_tokens,
                    estimated_cost_dollars=w_stats.estimated_cost_dollars,
                ))
                idx += 1

        return results

    def check_context_cap(self, identifier: str, threshold: int) -> bool:
        stats = self.get_conversation_stats(identifier)
        if not stats:
            return False
        return stats.context_tokens >= threshold

    def render_stats_table(self, stats: Sequence[antigravity_telemetry.ConversationStats]) -> str:
        lines = [
            "| Agent / Worker | Turns | Context | Fresh Input | Cached Input | Hit % | Output | Cost (Gemini 3.8 Flash) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        tot_turns = 0
        max_context = 0
        tot_fresh = 0
        tot_cached = 0
        tot_output = 0
        tot_cost = 0.0

        for s in stats:
            lines.append(
                f"| `{s.agent_name}` | {s.turns:,} | {s.context_tokens:,} | "
                f"{s.fresh_input_tokens:,} | {s.cached_input_tokens:,} | {s.cache_hit_percentage}% | "
                f"{s.output_tokens:,} | ${s.estimated_cost_dollars:,.2f} |"
            )
            tot_turns += s.turns
            max_context = max(max_context, s.context_tokens)
            tot_fresh += s.fresh_input_tokens
            tot_cached += s.cached_input_tokens
            tot_output += s.output_tokens
            tot_cost += s.estimated_cost_dollars

        total_input = tot_fresh + tot_cached
        tot_hit = round((tot_cached / total_input * 100.0), 1) if total_input > 0 else 0.0
        lines.append(
            f"| **TOTAL** | **{tot_turns:,}** | **{max_context:,}** | "
            f"**{tot_fresh:,}** | **{tot_cached:,}** | **{tot_hit}%** | "
            f"**{tot_output:,}** | **${tot_cost:,.2f}** |"
        )
        return "\n".join(lines)


def compute_cost(fresh_in: int, cached_in: int, output: int, model: str = "gemini-3.8-flash") -> float:
    return AntigravityTelemetry().calculate_cost(fresh_in, cached_in, output, model=model)


def get_conversation_stats(conv_id: str, db_dir: str = _DEFAULT_DB_DIR, brain_dir: str = _DEFAULT_BRAIN_DIR) -> Optional[antigravity_telemetry.ConversationStats]:
    return AntigravityTelemetry().get_conversation_stats(conv_id)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AntigravityTelemetry,
        keys=[AntigravityTelemetry, antigravity_telemetry.AntigravityTelemetry],
        tier=system,
    )


_initialize_ = __initialize__


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Antigravity Telemetry & Token Stats CLI")
    parser.add_argument("--conv-id", nargs="+", help="Conversation ID(s)")
    parser.add_argument("--coordinator", help="Coordinator conversation ID")
    parser.add_argument("--format", choices=["table", "markdown", "json"], default="markdown")
    parser.add_argument("--check-cap", type=int, help="Check if context exceeds cap")

    args = parser.parse_args(argv)
    telemetry = AntigravityTelemetry()

    if args.check_cap is not None and args.conv_id:
        cid = args.conv_id[0]
        exceeded = telemetry.check_context_cap(cid, args.check_cap)
        if exceeded:
            print("EXCEEDED_CAP")
            return 1
        return 0

    stats: List[antigravity_telemetry.ConversationStats] = []
    if args.coordinator:
        stats = list(telemetry.get_coordinator_run_stats(args.coordinator))
    elif args.conv_id:
        for cid in args.conv_id:
            s = telemetry.get_conversation_stats(cid)
            if s:
                stats.append(s)

    if not stats:
        # If no specific ID, try current or recent
        cid = os.environ.get("ANTIGRAVITY_CONVERSATION_ID", "")
        if cid:
            stats = list(telemetry.get_coordinator_run_stats(cid))
            if not stats:
                s = telemetry.get_conversation_stats(cid)
                if s:
                    stats = [s]

    if stats:
        print(telemetry.render_stats_table(stats))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
