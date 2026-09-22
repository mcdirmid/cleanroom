#!/usr/bin/env python3
"""antigravity_token_stats.py — Granular token and prompt-cache telemetry for Antigravity conversations.

Extracts Gemini LLM token metrics directly from Antigravity SQLite conversation
databases (~/.gemini/antigravity/conversations/<id>.db).

Surfaces:
  - Fresh (un-cached) input tokens
  - Cached input tokens (prompt cache hits)
  - Output candidate tokens
  - Thinking (reasoning) tokens
  - Prompt cache hit rate (%)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    """Lightweight recursive wire-format protobuf decoder."""
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


def get_conversation_stats(
    conv_id: str, db_dir: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Extracts token metrics for a single conversation ID from its SQLite database."""
    base_dir = db_dir or _DEFAULT_DB_DIR
    db_path = os.path.join(base_dir, f"{conv_id}.db")
    if not os.path.isfile(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
    except Exception:
        return None

    cur = conn.cursor()
    cur.execute(
        "SELECT idx, metadata FROM steps WHERE metadata IS NOT NULL ORDER BY idx;"
    )
    rows = cur.fetchall()
    conn.close()

    turns = 0
    fresh_in = 0
    cached_in = 0
    output = 0
    thinking = 0

    for _idx, meta in rows:
        if not meta:
            continue
        try:
            d = _decode_pb(meta)
            # Gemini usage_metadata is nested in field 9 of step metadata
            if 9 in d and d[9]:
                sub = _decode_pb(d[9][0])
                ints = {k: v[0] for k, v in sub.items() if isinstance(v[0], int)}
                # Protobuf field mappings:
                # 2: prompt_token_count (fresh un-cached input)
                # 5: cached_content_token_count (prompt cache hit)
                # 3: candidates_token_count (output tokens)
                # 9: thinking_tokens (reasoning tokens)
                if 2 in ints or 5 in ints or 3 in ints:
                    turns += 1
                    fresh_in += ints.get(2, 0)
                    cached_in += ints.get(5, 0)
                    output += ints.get(3, 0)
                    thinking += ints.get(9, 0)
        except Exception:
            continue

    total_in = fresh_in + cached_in
    hit_pct = (cached_in / total_in * 100.0) if total_in > 0 else 0.0

    return {
        "conv_id": conv_id,
        "turns": turns,
        "fresh_input_tokens": fresh_in,
        "cached_input_tokens": cached_in,
        "total_input_tokens": total_in,
        "output_tokens": output,
        "thinking_tokens": thinking,
        "cache_hit_pct": hit_pct,
    }


def discover_workers_from_coordinator(
    coord_conv_id: str, brain_dir: Optional[str] = None
) -> List[Tuple[str, str]]:
    """Scans the coordinator's transcript to find child worker conversation IDs and their roles."""
    base_dir = brain_dir or _DEFAULT_BRAIN_DIR
    transcript_path = os.path.join(
        base_dir, coord_conv_id, ".system_generated", "logs", "transcript.jsonl"
    )
    if not os.path.isfile(transcript_path):
        return []

    workers: List[Tuple[str, str]] = []
    seen: set[str] = set()

    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                content = data.get("content", "")
                if not content and "tool_calls" in data:
                    content = json.dumps(data["tool_calls"])

                # Look for subagent creation blocks
                cids = re.findall(
                    r'\"conversationId\":\s*\"([a-f0-9\-]+)\"', content
                )
                for cid in cids:
                    if cid not in seen and cid != coord_conv_id:
                        seen.add(cid)
                        # Attempt to associate role
                        role = "worker"
                        role_match = re.search(
                            r'\"Role\":\s*\"([^\"]+)\"', content
                        ) or re.search(r'role \'([^\']+)\'', content)
                        if role_match:
                            role = role_match.group(1).split(":")[-1].strip()
                        workers.append((cid, role))
            except Exception:
                continue

    return workers


PRICING_MODELS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "name": "DeepSeek-V3",
        "fresh_input_per_m": 0.27,
        "cached_input_per_m": 0.07,
        "output_per_m": 1.10,
    },
    "deepseek-v3": {
        "name": "DeepSeek-V3",
        "fresh_input_per_m": 0.27,
        "cached_input_per_m": 0.07,
        "output_per_m": 1.10,
    },
    "deepseek-r1": {
        "name": "DeepSeek-R1",
        "fresh_input_per_m": 0.55,
        "cached_input_per_m": 0.14,
        "output_per_m": 2.19,
    },
    "gemini-flash": {
        "name": "Gemini 2.5 Flash",
        "fresh_input_per_m": 0.15,
        "cached_input_per_m": 0.0375,
        "output_per_m": 0.60,
    },
}


def compute_cost(
    fresh: int, cached: int, output: int, pricing_model: str = "deepseek"
) -> Dict[str, float]:
    """Computes dollar costs with and without caching based on selected pricing rates."""
    rates = PRICING_MODELS.get(pricing_model.lower(), PRICING_MODELS["deepseek"])
    f_rate = rates["fresh_input_per_m"]
    c_rate = rates["cached_input_per_m"]
    o_rate = rates["output_per_m"]

    cost = (fresh * f_rate + cached * c_rate + output * o_rate) / 1_000_000.0
    uncached_cost = ((fresh + cached) * f_rate + output * o_rate) / 1_000_000.0
    saved = max(0.0, uncached_cost - cost)
    saved_pct = (saved / uncached_cost * 100.0) if uncached_cost > 0 else 0.0

    return {
        "cost": cost,
        "uncached_cost": uncached_cost,
        "saved": saved,
        "saved_pct": saved_pct,
    }


def format_stats(
    stats_list: Sequence[Dict[str, Any]],
    format_type: str = "table",
    pricing_model: str = "deepseek",
) -> str:
    """Renders token statistics and cost in table, markdown, json, or 1-line summary format."""
    rates = PRICING_MODELS.get(pricing_model.lower(), PRICING_MODELS["deepseek"])
    model_name = rates["name"]

    # Compute cost for each item
    for s in stats_list:
        cost_info = compute_cost(
            s["fresh_input_tokens"],
            s["cached_input_tokens"],
            s["output_tokens"],
            pricing_model=pricing_model,
        )
        s.update(cost_info)

    tot_turns = sum(s["turns"] for s in stats_list)
    tot_fresh = sum(s["fresh_input_tokens"] for s in stats_list)
    tot_cached = sum(s["cached_input_tokens"] for s in stats_list)
    tot_out = sum(s["output_tokens"] for s in stats_list)
    tot_think = sum(s["thinking_tokens"] for s in stats_list)
    tot_in = tot_fresh + tot_cached
    tot_hit = (tot_cached / tot_in * 100.0) if tot_in > 0 else 0.0

    tot_cost_info = compute_cost(
        tot_fresh, tot_cached, tot_out, pricing_model=pricing_model
    )
    tot_cost = tot_cost_info["cost"]
    tot_uncached = tot_cost_info["uncached_cost"]
    tot_saved = tot_cost_info["saved"]
    tot_saved_pct = tot_cost_info["saved_pct"]

    if format_type == "json":
        result_json = {
            "pricing_model": model_name,
            "rates_per_m": rates,
            "totals": {
                "turns": tot_turns,
                "fresh_input_tokens": tot_fresh,
                "cached_input_tokens": tot_cached,
                "output_tokens": tot_out,
                "thinking_tokens": tot_think,
                "cache_hit_pct": tot_hit,
                "cost_usd": tot_cost,
                "uncached_cost_usd": tot_uncached,
                "saved_usd": tot_saved,
                "saved_pct": tot_saved_pct,
            },
            "agents": stats_list,
        }
        return json.dumps(result_json, indent=2)

    if format_type == "summary":
        if len(stats_list) == 1:
            s = stats_list[0]
            label = s.get("label", s["conv_id"][:8])
            return (
                f"[Token Telemetry] {label}: Fresh={s['fresh_input_tokens']:,} | "
                f"Cached={s['cached_input_tokens']:,} ({s['cache_hit_pct']:.1f}% hit) | "
                f"Output={s['output_tokens']:,} | Cost=${s['cost']:.2f} "
                f"(Saved ${s['saved']:.2f}, {s['saved_pct']:.1f}% off)"
            )
        return (
            f"[Token Telemetry Total ({model_name})] Fresh={tot_fresh:,} | "
            f"Cached={tot_cached:,} ({tot_hit:.1f}% hit) | "
            f"Output={tot_out:,} | Cost=${tot_cost:.2f} "
            f"(Saved ${tot_saved:.2f}, {tot_saved_pct:.1f}% off)"
        )

    if format_type == "markdown":
        lines = [
            f"| Agent / Worker | Turns | Fresh Input | Cached Input | Hit % | Output | Cost ({model_name}) | No-Cache | Saved |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for s in stats_list:
            label = s.get("label", s["conv_id"][:8])
            lines.append(
                f"| `{label}` | {s['turns']} | {s['fresh_input_tokens']:,} | "
                f"{s['cached_input_tokens']:,} | {s['cache_hit_pct']:.1f}% | "
                f"{s['output_tokens']:,} | ${s['cost']:.2f} | "
                f"${s['uncached_cost']:.2f} | **${s['saved']:.2f}** ({s['saved_pct']:.1f}%) |"
            )
        lines.append(
            f"| **TOTAL** | **{tot_turns}** | **{tot_fresh:,}** | "
            f"**{tot_cached:,}** | **{tot_hit:.1f}%** | "
            f"**{tot_out:,}** | **${tot_cost:.2f}** | "
            f"**${tot_uncached:.2f}** | **${tot_saved:.2f} ({tot_saved_pct:.1f}%)** |"
        )
        return "\n".join(lines)

    # Standard ASCII table format
    col_w = [18, 5, 12, 12, 8, 10, 10, 10, 14]
    header = (
        f"| {'Worker / Agent':<{col_w[0]}} | {'Turns':<{col_w[1]}} | "
        f"{'Fresh Input':<{col_w[2]}} | {'Cached Input':<{col_w[3]}} | "
        f"{'Hit%':<{col_w[4]}} | {'Output':<{col_w[5]}} | "
        f"{'Cost':<{col_w[6]}} | {'No-Cache':<{col_w[7]}} | {'Saved':<{col_w[8]}} |"
    )
    sep = "|" + "|".join("-" * (w + 2) for w in col_w) + "|"
    total_sep = "|" + "|".join("=" * (w + 2) for w in col_w) + "|"

    out_lines = [header, sep]
    for s in stats_list:
        label = s.get("label", s["conv_id"][:8])
        out_lines.append(
            f"| {label:<{col_w[0]}} | {s['turns']:<{col_w[1]}} | "
            f"{s['fresh_input_tokens']:>{col_w[2]},} | {s['cached_input_tokens']:>{col_w[3]},} | "
            f"{s['cache_hit_pct']:>{col_w[4]-1}.1f}% | {s['output_tokens']:>{col_w[5]},} | "
            f"${s['cost']:>{col_w[6]-1}.2f} | ${s['uncached_cost']:>{col_w[7]-1}.2f} | "
            f"${s['saved']:>{col_w[8]-8}.2f} ({s['saved_pct']:>4.1f}%) |"
        )
    out_lines.append(total_sep)
    out_lines.append(
        f"| {'TOTAL':<{col_w[0]}} | {tot_turns:<{col_w[1]}} | "
        f"{tot_fresh:>{col_w[2]},} | {tot_cached:>{col_w[3]},} | "
        f"{tot_hit:>{col_w[4]-1}.1f}% | {tot_out:>{col_w[5]},} | "
        f"${tot_cost:>{col_w[6]-1}.2f} | ${tot_uncached:>{col_w[7]-1}.2f} | "
        f"${tot_saved:>{col_w[8]-8}.2f} ({tot_saved_pct:>4.1f}%) |"
    )
    return "\n".join(out_lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="antigravity_token_stats",
        description="Query Antigravity conversation SQLite databases for token and prompt-cache statistics",
    )
    parser.add_argument(
        "--conv-id",
        nargs="+",
        help="One or more conversation IDs to query directly",
    )
    parser.add_argument(
        "--coordinator",
        help="Coordinator conversation ID (automatically discovers all child worker conversations)",
    )
    parser.add_argument(
        "--pricing",
        choices=list(PRICING_MODELS.keys()),
        default="deepseek",
        help="Pricing model for cost computation (default: deepseek / DeepSeek-V3)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "markdown", "json", "summary"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--db-dir",
        default=_DEFAULT_DB_DIR,
        help=f"Directory containing conversation SQLite .db files (default: {_DEFAULT_DB_DIR})",
    )
    parser.add_argument(
        "--brain-dir",
        default=_DEFAULT_BRAIN_DIR,
        help=f"Directory containing conversation brain artifacts (default: {_DEFAULT_BRAIN_DIR})",
    )

    args = parser.parse_args(argv)

    targets: List[Tuple[str, str]] = []

    if args.coordinator:
        # Include coordinator itself
        targets.append((args.coordinator, "Coordinator"))
        # Discover children
        children = discover_workers_from_coordinator(
            args.coordinator, brain_dir=args.brain_dir
        )
        for idx, (cid, role) in enumerate(children, start=1):
            targets.append((cid, f"Worker {idx} ({role})"))

    if args.conv_id:
        for cid in args.conv_id:
            targets.append((cid, cid[:8]))

    if not targets:
        parser.print_help()
        return 1

    stats_list: List[Dict[str, Any]] = []
    for cid, label in targets:
        st = get_conversation_stats(cid, db_dir=args.db_dir)
        if st:
            st["label"] = label
            stats_list.append(st)

    if not stats_list:
        sys.stderr.write("No matching conversation statistics found.\n")
        return 1

    rendered = format_stats(
        stats_list, format_type=args.format, pricing_model=args.pricing
    )
    sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
