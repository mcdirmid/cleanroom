#!/usr/bin/env python3
"""antigravity_run_monitor.py — Structured run monitoring and status inspection for Cleanroom runs.

Inspects coordinator transcripts and SQLite session databases to report:
  - Active and completed worker roles, session IDs, and conversation IDs
  - Current turn counts and context sizes
  - Real-time token usage and cost metrics
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_with_ai"), os.path.join(_repo_root, "update_python_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from update_with_ai.support.lib.antigravity_token_stats import (
    PRICING_MODELS,
    _DEFAULT_BRAIN_DIR,
    _DEFAULT_DB_DIR,
    compute_cost,
    get_conversation_stats,
)


def get_latest_coordinator(brain_dir: str = _DEFAULT_BRAIN_DIR) -> Optional[str]:
    """Finds the most recently modified coordinator conversation ID."""
    if not os.path.isdir(brain_dir):
        return None
    candidates = []
    for entry in os.listdir(brain_dir):
        trans_path = os.path.join(brain_dir, entry, ".system_generated", "logs", "transcript.jsonl")
        if os.path.isfile(trans_path):
            try:
                with open(trans_path, "r", encoding="utf-8") as f:
                    for _ in range(5):
                        line = f.readline()
                        if "Orchestrate cleanroom convergence" in line or "cleanroom_coordinator" in line:
                            candidates.append((os.path.getmtime(trans_path), entry))
                            break
            except Exception:
                continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def inspect_run(
    coordinator_id: str,
    brain_dir: str = _DEFAULT_BRAIN_DIR,
    db_dir: str = _DEFAULT_DB_DIR,
    pricing: str = "gemini-flash",
) -> Dict[str, Any]:
    """Extracts structured telemetry and lifecycle state for a coordinator and its workers."""
    coord_trans = os.path.join(brain_dir, coordinator_id, ".system_generated", "logs", "transcript.jsonl")
    workers: List[Dict[str, Any]] = []

    if os.path.isfile(coord_trans):
        with open(coord_trans, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                tc = obj.get("tool_calls")
                if not tc:
                    continue
                for call in tc:
                    if call.get("name") == "invoke_subagent":
                        args = call.get("args", {})
                        subs = args.get("Subagents", [])
                        if isinstance(subs, str):
                            try:
                                subs = json.loads(subs)
                            except Exception:
                                subs = []
                        for sub in subs:
                            role = sub.get("Role", "worker")
                            prompt = sub.get("Prompt", "")
                            # Extract session ID from prompt if present
                            session_id = ""
                            if "session ID is '" in prompt:
                                session_id = prompt.split("session ID is '")[1].split("'")[0]
                            workers.append({
                                "role": role,
                                "session_id": session_id,
                                "conv_id": "",
                                "status": "invoked",
                            })
                    elif call.get("name") == "manage_subagents":
                        args = call.get("args", {})
                        if args.get("Action") == "kill":
                            cids = args.get("ConversationIds", [])
                            if isinstance(cids, str):
                                try:
                                    cids = json.loads(cids)
                                except Exception:
                                    cids = []
                            for cid in cids:
                                for w in workers:
                                    if w["conv_id"] == cid:
                                        w["status"] = "evicted/killed"

    # Match workers with conversation IDs from subsequent responses
    if os.path.isfile(coord_trans):
        with open(coord_trans, "r", encoding="utf-8") as f:
            w_idx = 0
            for line in f:
                if "Created the following subagents:" in line:
                    try:
                        obj = json.loads(line)
                        content = obj.get("content", "")
                        if "conversationId" in content:
                            for cpart in content.split('"conversationId":'):
                                cand_id = cpart.strip().strip('"').split('"')[0].strip()
                                if len(cand_id) == 36 and cand_id.count("-") == 4:
                                    if w_idx < len(workers):
                                        workers[w_idx]["conv_id"] = cand_id
                                        w_idx += 1
                    except Exception:
                        pass

    # Collect stats for coordinator and each worker
    coord_stats = get_conversation_stats(coordinator_id, db_dir=db_dir) or {}
    coord_costs = (
        compute_cost(
            coord_stats.get("fresh_input_tokens", 0),
            coord_stats.get("cached_input_tokens", 0),
            coord_stats.get("output_tokens", 0),
            pricing_model=pricing,
        )
        if coord_stats
        else {}
    )

    worker_results = []
    for w in workers:
        cid = w.get("conv_id")
        stats = get_conversation_stats(cid, db_dir=db_dir) if cid else None
        costs = (
            compute_cost(
                stats.get("fresh_input_tokens", 0),
                stats.get("cached_input_tokens", 0),
                stats.get("output_tokens", 0),
                pricing_model=pricing,
            )
            if stats
            else {}
        )
        worker_results.append({
            "role": w["role"],
            "session_id": w["session_id"],
            "conv_id": cid or "unknown",
            "status": w["status"],
            "turns": stats.get("turns", 0) if stats else 0,
            "context_tokens": stats.get("last_context_tokens", 0) if stats else 0,
            "peak_context": stats.get("peak_context_tokens", 0) if stats else 0,
            "fresh_input": stats.get("fresh_input_tokens", 0) if stats else 0,
            "cached_input": stats.get("cached_input_tokens", 0) if stats else 0,
            "hit_pct": stats.get("hit_pct", 0.0) if stats else 0.0,
            "output": stats.get("output_tokens", 0) if stats else 0,
            "cost": costs.get("cost", 0.0),
            "saved": costs.get("saved", 0.0),
        })

    return {
        "coordinator_id": coordinator_id,
        "coordinator_stats": coord_stats,
        "coordinator_costs": coord_costs,
        "workers": worker_results,
    }


def format_table(data: Dict[str, Any]) -> str:
    lines = []
    lines.append("| Worker / Role | Session | Conv ID | Turns | Context | Fresh In | Cached In | Hit % | Output | Cost |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    cstats = data.get("coordinator_stats", {})
    ccosts = data.get("coordinator_costs", {})
    cid = data.get("coordinator_id", "")[:8]
    c_fresh = cstats.get("fresh_input_tokens", 0)
    c_cached = cstats.get("cached_input_tokens", 0)
    c_in = c_fresh + c_cached
    c_hit = (c_cached / c_in * 100.0) if c_in > 0 else 0.0

    lines.append(
        f"| `Coordinator` | - | `{cid}` | {cstats.get('turns', 0)} | "
        f"{cstats.get('last_context_tokens', 0):,} | "
        f"{c_fresh:,} | {c_cached:,} | "
        f"{c_hit:.1f}% | {cstats.get('output_tokens', 0):,} | ${ccosts.get('cost', 0.0):.2f} |"
    )

    tot_turns = cstats.get("turns", 0)
    tot_fresh = c_fresh
    tot_cached = c_cached
    tot_out = cstats.get("output_tokens", 0)
    tot_cost = ccosts.get("cost", 0.0)
    last_active_ctx = cstats.get("last_context_tokens", 0)

    for w in data.get("workers", []):
        tot_turns += w["turns"]
        tot_fresh += w["fresh_input"]
        tot_cached += w["cached_input"]
        tot_out += w["output"]
        tot_cost += w["cost"]
        last_active_ctx = w["context_tokens"]
        w_in = w["fresh_input"] + w["cached_input"]
        w_hit = (w["cached_input"] / w_in * 100.0) if w_in > 0 else 0.0
        lines.append(
            f"| `{w['role']}` | `{w['session_id']}` | `{w['conv_id'][:8]}` | {w['turns']} | "
            f"{w['context_tokens']:,} | "
            f"{w['fresh_input']:,} | {w['cached_input']:,} | "
            f"{w_hit:.1f}% | {w['output']:,} | ${w['cost']:.2f} |"
        )

    tot_in = tot_fresh + tot_cached
    tot_hit = (tot_cached / tot_in * 100.0) if tot_in > 0 else 0.0
    lines.append(
        f"| **TOTAL** | - | - | **{tot_turns}** | **{last_active_ctx:,}** | "
        f"**{tot_fresh:,}** | **{tot_cached:,}** | **{tot_hit:.1f}%** | **{tot_out:,}** | **${tot_cost:.2f}** |"
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cleanroom run monitor")
    parser.add_argument("--coordinator", default=None, help="Coordinator conversation ID (default: latest)")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--pricing", default="gemini-flash", choices=list(PRICING_MODELS.keys()))
    args = parser.parse_args(argv)

    coord_id = args.coordinator or get_latest_coordinator()
    if not coord_id:
        sys.stderr.write("Error: No coordinator run found.\n")
        return 1

    data = inspect_run(coord_id, pricing=args.pricing)
    if args.format == "json":
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        sys.stdout.write(format_table(data) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
