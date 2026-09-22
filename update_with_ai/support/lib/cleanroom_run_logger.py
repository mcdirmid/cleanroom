#!/usr/bin/env python3
"""cleanroom_run_logger.py — Out-of-band Run Directory and Timeline Logger.

Manages `.cleanroom/runs/<run_id>/`:
  - timeline.md: Formatted live markdown table of events with transcript links.
  - timeline.log: Plain-text stream for live console tailing (`tail -f`).
  - summary.json: Machine-readable final run statistics including actual token metrics.
  - transcripts/: Semantic symlinks to raw Antigravity agent transcripts.
"""

from __future__ import annotations

from datetime import datetime
import glob
import json
import os
import re
from typing import Any, Dict, List, Optional


def sanitize_table_cell(text: str) -> str:
    """Escapes pipes and collapses newlines to preserve Markdown table rows."""
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("|", r"\|")
    cleaned = cleaned.replace("\n", " <br> ")
    return cleaned.strip()


def sanitize_slug(text: str) -> str:
    """Produces a filesystem-safe identifier slug."""
    s = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    return s.strip("_")


def get_workspace_root(start_dir: Optional[str] = None) -> str:
    """Resolves the Cleanroom workspace root."""
    override = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
    if override and os.path.isdir(override):
        return os.path.abspath(override)

    cur = os.path.abspath(start_dir if start_dir else os.getcwd())
    while True:
        if (
            os.path.exists(os.path.join(cur, "MODULE.bazel"))
            or os.path.exists(os.path.join(cur, "WORKSPACE"))
            or os.path.exists(os.path.join(cur, ".git"))
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start_dir if start_dir else os.getcwd())


def get_cleanroom_base_dir(workspace_root: Optional[str] = None) -> str:
    """Returns the base .cleanroom directory."""
    override = os.environ.get("CLEANROOM_DIR_OVERRIDE")
    if override:
        return os.path.abspath(override)
    root = workspace_root if workspace_root else get_workspace_root()
    return os.path.join(root, ".cleanroom")


def get_active_run(workspace_root: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Reads .cleanroom/active_run.json if present."""
    base_dir = get_cleanroom_base_dir(workspace_root)
    active_path = os.path.join(base_dir, "active_run.json")
    if not os.path.exists(active_path):
        return None
    try:
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def get_or_create_active_run(
    target: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> dict[str, Any]:
    """Retrieves the active run or initializes a new run directory."""
    active = get_active_run(workspace_root)
    if active and os.path.isdir(active.get("run_dir", "")):
        if target and (not active.get("target") or active.get("target") == "General Convergence"):
            active["target"] = target
            base_dir = get_cleanroom_base_dir(workspace_root)
            try:
                with open(os.path.join(base_dir, "active_run.json"), "w", encoding="utf-8") as f:
                    json.dump(active, f, indent=2)
            except Exception:
                pass
        return active

    base_dir = get_cleanroom_base_dir(workspace_root)
    runs_dir = os.path.join(base_dir, "runs")
    os.makedirs(runs_dir, exist_ok=True)

    now = datetime.now()
    timestamp_id = now.strftime("%Y%m%d_%H%M%S")
    target_slug = sanitize_slug(target) if target else "run"
    run_id = f"{timestamp_id}_{target_slug}" if target_slug else timestamp_id

    run_dir = os.path.join(runs_dir, run_id)
    transcripts_dir = os.path.join(run_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)

    # Maintain .cleanroom/runs/latest symlink
    latest_symlink = os.path.join(runs_dir, "latest")
    try:
        if os.path.islink(latest_symlink) or os.path.exists(latest_symlink):
            os.unlink(latest_symlink)
        os.symlink(run_id, latest_symlink)
    except OSError:
        pass

    target_display = target if target else "General Convergence"
    timeline_md_path = os.path.join(run_dir, "timeline.md")
    with open(timeline_md_path, "w", encoding="utf-8") as f:
        f.write(
            f"# Cleanroom Convergence Run: `{target_display}`\n\n"
            f"- **Run ID**: `{run_id}`\n"
            f"- **Started**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Target**: `{target_display}`\n"
            f"- **Status**: `RUNNING`\n\n"
            f"| Time | Agent | Event | Details |\n"
            f"| :--- | :--- | :--- | :--- |\n"
        )

    timeline_log_path = os.path.join(run_dir, "timeline.log")
    with open(timeline_log_path, "w", encoding="utf-8") as f:
        f.write(f"[{now.strftime('%H:%M:%S')}] RUN_START: Run {run_id} started for target {target_display}\n")

    run_metadata: dict[str, Any] = {
        "run_id": run_id,
        "target": target_display,
        "start_time": now.isoformat(),
        "run_dir": run_dir,
        "timeline_md": timeline_md_path,
        "timeline_log": timeline_log_path,
        "transcripts_dir": transcripts_dir,
    }

    active_path = os.path.join(base_dir, "active_run.json")
    with open(active_path, "w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2)

    return run_metadata


def log_event(
    event_type: str,
    agent: str,
    details: str,
    links: str = "",
    target: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> None:
    """Appends an event row to timeline.md and timeline.log for the active run."""
    try:
        run = get_or_create_active_run(target=target, workspace_root=workspace_root)
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Make absolute paths relative if inside workspace
        root = workspace_root if workspace_root else get_workspace_root()
        if root and root in details:
            details = details.replace(root + os.sep, "").replace(root, "")

        if links:
            details = f"{details} ({links})"

        safe_agent = sanitize_table_cell(agent)
        safe_event = sanitize_table_cell(event_type)
        safe_details = sanitize_table_cell(details)

        md_row = f"| {time_str} | `{safe_agent}` | `{safe_event}` | {safe_details} |\n"
        log_line = f"[{time_str}] [{safe_agent}] {safe_event}: {safe_details}\n"

        md_path = run.get("timeline_md")
        if md_path and os.path.exists(md_path):
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(md_row)

        log_path = run.get("timeline_log")
        if log_path and os.path.exists(log_path):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception:
        # Logging errors should never interrupt runtime tool execution
        pass


def find_brain_transcript(
    conversation_id: str,
    brain_roots: Optional[List[str]] = None,
) -> Optional[str]:
    """Finds the transcript.jsonl file for a given conversation UUID."""
    if not conversation_id or conversation_id == "default":
        return None

    roots: List[str] = []
    if brain_roots:
        roots.extend(brain_roots)
    else:
        roots.append(os.path.expanduser("~/.gemini/antigravity/brain"))
        roots.append(os.path.expanduser("~/.gemini/antigravity-ide/brain"))

    for root in roots:
        if not os.path.isdir(root):
            continue
        cand = os.path.join(root, conversation_id, ".system_generated", "logs", "transcript.jsonl")
        if os.path.exists(cand):
            return cand
        cand_dir = os.path.join(root, conversation_id)
        if os.path.isdir(cand_dir):
            return cand

    default_root = roots[0] if roots else os.path.expanduser("~/.gemini/antigravity/brain")
    return os.path.join(default_root, conversation_id, ".system_generated", "logs", "transcript.jsonl")


def register_transcript(
    conversation_id: str,
    label: str,
    workspace_root: Optional[str] = None,
    brain_roots: Optional[List[str]] = None,
) -> Optional[str]:
    """Creates a semantic symlink under .cleanroom/runs/<run_id>/transcripts/<label>.jsonl.

    Returns the relative path to the symlink (e.g. 'transcripts/<label>.jsonl') or None.
    """
    try:
        run = get_or_create_active_run(workspace_root=workspace_root)
        transcripts_dir = run.get("transcripts_dir")
        if not transcripts_dir:
            return None

        clean_label = sanitize_slug(label)
        symlink_name = f"{clean_label}.jsonl"
        symlink_path = os.path.join(transcripts_dir, symlink_name)

        target_path = find_brain_transcript(conversation_id, brain_roots=brain_roots)
        if not target_path:
            return None

        if os.path.islink(symlink_path) or os.path.exists(symlink_path):
            try:
                os.unlink(symlink_path)
            except OSError:
                pass

        os.symlink(target_path, symlink_path)
        rel_link = f"transcripts/{symlink_name}"
        return rel_link
    except Exception:
        return None


def collect_run_metrics(transcripts_dir: str) -> Dict[str, Any]:
    """Inspects all symlinked agent transcripts and extracts exact token and turn metrics."""
    metrics: Dict[str, Any] = {}
    if not os.path.isdir(transcripts_dir):
        return metrics

    seen_targets = set()
    for link_name in sorted(os.listdir(transcripts_dir)):
        lpath = os.path.join(transcripts_dir, link_name)
        if not (os.path.islink(lpath) or os.path.isfile(lpath)):
            continue
        real_target = os.path.realpath(lpath)
        if real_target in seen_targets:
            continue
        seen_targets.add(real_target)

        full_target = real_target.replace("transcript.jsonl", "transcript_full.jsonl")
        target_file = full_target if os.path.exists(full_target) else real_target
        if not os.path.exists(target_file):
            continue

        turns = 0
        thought_chars = 0
        content_chars = 0
        tool_chars = 0
        tool_calls = 0

        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    t = d.get("type")
                    if t == "PLANNER_RESPONSE":
                        turns += 1
                        thought_chars += len(d.get("thinking") or "")
                        content_chars += len(d.get("content") or "")
                        tool_calls += len(d.get("tool_calls") or [])
                    elif t == "GENERIC":
                        tool_chars += len(d.get("content") or "")
                except Exception:
                    pass

        label = link_name.replace(".jsonl", "")
        thought_tokens = round(thought_chars / 4)
        content_tokens = round(content_chars / 4)
        tool_tokens = round(tool_chars / 4)
        total_tokens = thought_tokens + content_tokens + tool_tokens

        metrics[label] = {
            "turns": turns,
            "thought_tokens": thought_tokens,
            "content_tokens": content_tokens,
            "tool_tokens": tool_tokens,
            "total_tokens": total_tokens,
            "tool_calls": tool_calls,
        }

    return metrics


def finish_run(
    status: str = "COMPLETED",
    summary: Optional[dict[str, Any]] = None,
    workspace_root: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Concludes active run, computes actual token metrics, updates timeline.md, and writes summary.json."""
    try:
        active = get_active_run(workspace_root)
        if not active:
            return None

        now = datetime.now()
        run_dir = active.get("run_dir", "")
        base_dir = get_cleanroom_base_dir(workspace_root)
        transcripts_dir = active.get("transcripts_dir", os.path.join(run_dir, "transcripts"))

        # Extract actual token metrics across all subagents
        token_metrics = collect_run_metrics(transcripts_dir)

        total_turns = sum(m.get("turns", 0) for m in token_metrics.values())
        total_thought_tokens = sum(m.get("thought_tokens", 0) for m in token_metrics.values())
        total_output_tokens = sum(m.get("content_tokens", 0) for m in token_metrics.values())
        total_tool_tokens = sum(m.get("tool_tokens", 0) for m in token_metrics.values())
        total_system_tokens = total_thought_tokens + total_output_tokens + total_tool_tokens

        final_summary: dict[str, Any] = {
            "run_id": active.get("run_id"),
            "target": active.get("target"),
            "start_time": active.get("start_time"),
            "end_time": now.isoformat(),
            "status": status,
            "totals": {
                "turns": total_turns,
                "thought_tokens": total_thought_tokens,
                "output_tokens": total_output_tokens,
                "tool_tokens": total_tool_tokens,
                "total_tokens": total_system_tokens,
            },
            "agents": token_metrics,
        }
        if summary:
            final_summary.update(summary)

        # Write summary.json
        summary_path = os.path.join(run_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(final_summary, f, indent=2)

        # Append final status and Token Breakdown to timeline.md
        md_path = active.get("timeline_md")
        if md_path and os.path.exists(md_path):
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(
                    f"\n---\n\n"
                    f"## Run Finalized: `{status}`\n"
                    f"- **Ended**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"- **Summary File**: [`summary.json`](summary.json)\n\n"
                    f"### Actual Token Usage & Efficiency\n\n"
                    f"| Subagent / Role | Model Turns | Thought Tokens | Output Tokens | Tool Tokens | Total Tokens |\n"
                    f"| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                )
                for agent_label, m in token_metrics.items():
                    f.write(
                        f"| `{agent_label}` | {m.get('turns', 0):,} | {m.get('thought_tokens', 0):,} | "
                        f"{m.get('content_tokens', 0):,} | {m.get('tool_tokens', 0):,} | {m.get('total_tokens', 0):,} |\n"
                    )
                f.write(
                    f"| **Total** | **{total_turns:,}** | **{total_thought_tokens:,}** | "
                    f"**{total_output_tokens:,}** | **{total_tool_tokens:,}** | **{total_system_tokens:,}** |\n"
                )

        # Remove active_run.json so future runs start fresh
        active_path = os.path.join(base_dir, "active_run.json")
        if os.path.exists(active_path):
            try:
                os.remove(active_path)
            except OSError:
                pass

        return final_summary
    except Exception:
        return None
