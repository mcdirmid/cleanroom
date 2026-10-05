#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents.

Provides role-local commands executed inside a commissioned role workspace:
- get_work: Inspects and displays ready dirty units in the local workspace scope.
- submit: Verifies and stamps in-band source metadata (or <ROLE>_AUDIT for auditors).
- blame: Appends critique to a writable spec, or buffers into .cleanroom_blame_buffer.json if read-only.
- fail: Clears LAST_CLEANED and appends failure diagnostics to force unit into dirty state.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _find_repo_root() -> str:
    real_path = os.path.realpath(__file__)
    curr = os.path.dirname(real_path)
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "MODULE.bazel")) or os.path.exists(
            os.path.join(curr, ".git")
        ):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(real_path), "../../.."))


_repo_root = _find_repo_root()
for _p in [
    _repo_root,
    os.path.join(_repo_root, "update_python_with_ai"),
    os.path.join(_repo_root, "update_with_ai"),
    os.path.join(_repo_root, "update_with_ai/support/lib"),
    os.path.join(_repo_root, "update_python_with_ai/support/lib"),
]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

import src_metadata
import cleanroom_workspace_tool

BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
AUDIT_BUFFER_FILE = ".cleanroom_audit_buffer.json"


def find_workspace_root() -> str:
    """Finds the root of the current role workspace containing .cleanroom_role.json."""
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, ".cleanroom_role.json")):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()


def get_current_role_metadata() -> Optional[Dict[str, Any]]:
    """Loads metadata for current role workspace."""
    ws_root = find_workspace_root()
    return cleanroom_workspace_tool.load_role_metadata(ws_root)


# ==============================================================================
# Role Commands: get_work, submit, blame, fail
# ==============================================================================


def run_get_work(
    dir_scope: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Evaluates dirtiness in local workspace scope and prints next ready tasks for this role."""
    root = os.path.abspath(repo_root or find_workspace_root())
    meta = get_current_role_metadata()
    role_name = meta.get("role_name", "") if meta else ""
    d_scope = dir_scope or (meta.get("parts_dir", "staging") if meta else "staging")

    dirty_items = cleanroom_workspace_tool.find_all_dirty_in_scope(
        root, dir_scope=d_scope, role_filter=role_name if role_name else None
    )

    print(
        f"\n=== Cleanroom Work Queue [Role: {(role_name or 'ALL').upper()} | Scope: {d_scope}] ==="
    )
    if not dirty_items:
        print(
            f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
        )
        return 0

    ready_items = cleanroom_workspace_tool.get_ready_dirty_nodes(
        dirty_items, repo_root=root
    )
    print(
        f"Found {len(dirty_items)} dirty unit(s) ({len(ready_items)} ready to clean):"
    )
    for item in ready_items:
        print(f"\n  • [READY - {item['role'].upper()}] {item['target_file']}")
        for r in item["reasons"]:
            print(f"      - {r}")
    if cleanroom_workspace_tool.is_auditor_role(role_name):
        print(
            f"\nACTIONABLE NEXT STEP: Execute verification suite for target, then run 'bin/submit <target_file>' to attest {role_name.upper()}_AUDIT.\n"
        )
    else:
        print(
            "\nACTIONABLE NEXT STEP: Implement or verify target, then run 'bin/submit <file> \"<summary>\"' (or 'bin/submit <file>' if no changes).\n"
        )
    return 1


def _resolve_target_path(target: str, repo_root: str) -> str:
    """Resolves target path cleanly handling absolute and relative paths."""
    target_str = target.strip()
    norm_root = os.path.realpath(repo_root)
    if os.path.isabs(target_str):
        return os.path.realpath(target_str)
    cand1 = os.path.realpath(target_str)
    if os.path.exists(cand1):
        return cand1
    cand2 = os.path.realpath(os.path.join(norm_root, target_str.lstrip("/")))
    if os.path.exists(cand2):
        return cand2
    return cand1


def _is_test_file(target: str) -> bool:
    norm = target.strip().replace("\\", "/")
    return norm.endswith("_test.py") or "/tests/" in norm or norm.startswith("tests/")


def resolve_submit_target(
    target: str,
    repo_root: str,
    role_name: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolves target path and unit name for submit command."""
    target_str = target.strip()

    # 1. Direct path check
    cand_path = _resolve_target_path(target_str, repo_root)
    if os.path.isfile(cand_path):
        stem = os.path.splitext(os.path.basename(cand_path))[0]
        return cand_path, stem

    role_def = cleanroom_workspace_tool.resolve_role_definition(role_name, repo_root)

    # 2. Check virtual role target, e.g. <part_dir>/qa/<unit_name>
    target_norm = target_str.replace("\\", "/").strip("/")
    if f"/{role_name}/" in target_norm:
        part_dir, _, unit_name = target_norm.partition(f"/{role_name}/")
        unit_name = unit_name.strip()
        fb_deps = role_def.get("feedback_role_deps", [])
        if fb_deps:
            fb_def = cleanroom_workspace_tool.resolve_role_definition(
                fb_deps[0], repo_root
            )
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat:
                cand = os.path.realpath(
                    os.path.join(
                        repo_root, fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
                    )
                )
                if os.path.isfile(cand):
                    return cand, unit_name

    # 3. Check bare unit name or stem across parts in scope
    stem = os.path.splitext(os.path.basename(target_str))[0]
    d_scope = meta.get("parts_dir", "staging") if meta else "staging"
    part_dirs = cleanroom_workspace_tool.find_part_dirs_in_scope(repo_root, d_scope)

    if cleanroom_workspace_tool.is_auditor_role(role_name):
        fb_deps = role_def.get("feedback_role_deps", [])
        if fb_deps:
            fb_def = cleanroom_workspace_tool.resolve_role_definition(
                fb_deps[0], repo_root
            )
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat:
                for pd in part_dirs:
                    cand = os.path.realpath(
                        os.path.join(
                            repo_root, fb_pat.format(unit_dir=pd, unit_name=stem)
                        )
                    )
                    if os.path.isfile(cand):
                        return cand, stem
    else:
        src_pat = role_def.get("src_pattern", "")
        if src_pat:
            for pd in part_dirs:
                cand = os.path.realpath(
                    os.path.join(repo_root, src_pat.format(unit_dir=pd, unit_name=stem))
                )
                if os.path.isfile(cand):
                    return cand, stem

    return None, None


def run_submit(
    target: str,
    summary: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Verifies target and stamps in-band metadata or <ROLE>_AUDIT."""
    root = os.path.realpath(repo_root or find_workspace_root())
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    role_name = str(meta.get("role_name") or "") if meta else ""

    # Auditor role submit: reject direct submission of feedback/test files
    if cleanroom_workspace_tool.is_auditor_role(role_name):
        if _is_test_file(target):
            print(f"Error: Cannot submit verification/test file '{target}'.")
            print(
                f"In {role_name.upper()}, your role is auditing the implementation target."
            )
            print(
                f"Submit the audited implementation target instead: bin/submit <impl_file> (or bin/submit <unit_name>)"
            )
            return 1

    target_path, unit_name = resolve_submit_target(target, root, role_name, meta)

    if not target_path or not os.path.isfile(target_path):
        print(f"Error: Target '{target}' not found on disk.")
        return 1

    role_def = cleanroom_workspace_tool.resolve_role_definition(role_name, root)

    # If auditor role: stamp or buffer <ROLE>_AUDIT across primary and companion targets
    if cleanroom_workspace_tool.is_auditor_role(role_name):
        audit_tag = cleanroom_workspace_tool.AUDITOR_ROLE_TAGS.get(
            role_name, f"{role_name.upper()}_AUDIT"
        )

        # Find all associated feedback files for this unit (e.g. lib and tests for qa/coverage)
        part_dir = os.path.dirname(
            os.path.dirname(os.path.relpath(os.path.realpath(target_path), root))
        )
        targets_to_audit = [os.path.realpath(target_path)]
        fb_deps = role_def.get("feedback_role_deps", [])
        for fb_label in fb_deps:
            fb_def = cleanroom_workspace_tool.resolve_role_definition(fb_label, root)
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat and unit_name:
                fb_rel = fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
                fb_full = os.path.realpath(os.path.join(root, fb_rel))
                if os.path.isfile(fb_full) and fb_full not in targets_to_audit:
                    targets_to_audit.append(fb_full)

        buffered_targets: List[str] = []
        stamped_targets: List[str] = []
        now = src_metadata.current_utc_timestamp()

        for t_full in targets_to_audit:
            is_ro = False
            try:
                st = os.stat(t_full)
                is_ro = not bool(st.st_mode & stat.S_IWUSR)
            except OSError:
                is_ro = True

            real_t = os.path.realpath(t_full)
            rel_t = (
                os.path.relpath(real_t, ws_root)
                if real_t.startswith(ws_root)
                else real_t
            )
            if is_ro:
                buffer_path = os.path.join(ws_root, AUDIT_BUFFER_FILE)
                entries: List[Dict[str, Any]] = []
                if os.path.isfile(buffer_path):
                    try:
                        with open(buffer_path, "r", encoding="utf-8") as abf:
                            entries = json.load(abf)
                    except Exception:
                        entries = []
                target_key = rel_t.strip().lstrip("/")
                cleaned_entries = [
                    e
                    for e in entries
                    if not (
                        e.get("target") == target_key
                        and e.get("audit_tag") == audit_tag
                    )
                ]
                cleaned_entries.append(
                    {
                        "target": target_key,
                        "audited_by": role_name,
                        "audit_tag": audit_tag,
                        "timestamp": now,
                    }
                )
                cleanroom_workspace_tool.write_file_with_perms(
                    buffer_path,
                    json.dumps(cleaned_entries, indent=2) + "\n",
                    readonly=False,
                )
                buffered_targets.append(rel_t)
            else:
                src_metadata.stamp_audit(t_full, role_name)
                stamped_targets.append(rel_t)

        if buffered_targets:
            print(
                f"Recorded audit on {', '.join(buffered_targets)} into {AUDIT_BUFFER_FILE}."
            )
            print(
                "It will be harvested into canonical headers when 'cleanroom-sync' runs."
            )
        if stamped_targets:
            print(
                f"✔ Audited target stamped: {', '.join(stamped_targets)} (Tagged: {audit_tag})"
            )
        return 0

    # Producer role submit:
    # 1. Enforce that read-only files cannot be submitted
    is_ro = False
    try:
        st = os.stat(target_path)
        is_ro = not bool(st.st_mode & stat.S_IWUSR)
    except OSError:
        is_ro = True

    if is_ro:
        print(
            f"Error: Target '{target}' is read-only. Producer roles can only submit their own read-write targets."
        )
        return 1

    # 2. Enforce active directory scope matching
    active_pattern = role_def.get("src_pattern", "") if role_def else ""
    if active_pattern:
        active_dir, active_pfx, active_sfx = (
            cleanroom_workspace_tool.parse_pattern_info(active_pattern)
        )
        fname = os.path.basename(target_path)
        parent = os.path.basename(os.path.dirname(target_path))
        if parent != active_dir or not (
            fname.startswith(active_pfx) and fname.endswith(active_sfx)
        ):
            print(
                f"Error: Target '{target}' is outside active role directory scope ({active_dir}/{active_pfx}*{active_sfx})."
            )
            return 1

    summary_text = summary or f"Updated {os.path.basename(target_path)}"

    # Producer role submit: evaluate whether code body actually modified
    is_modified = src_metadata.is_code_modified(target_path)
    summary_provided = bool(summary and summary.strip())

    if is_modified and not summary_provided:
        print(
            f"Error: Target '{target}' has been modified (CODE_HASH differs), but no change summary was provided."
        )
        print(f'Usage: bin/submit {target} "<concise change summary>"')
        return 1

    if not is_modified and summary_provided:
        print(f"Error: Target '{target}' was not modified (CODE_HASH matches).")
        print("A change summary must not be provided for an unchanged file.")
        print(f"Usage to submit without changes: bin/submit {target}")
        return 1

    if is_modified:
        src_metadata.record_change(target_path, summary_text)
        print(
            f"✔ Submitted {target_path}: code modified and in-band metadata updated (CHANGE: {summary_text})"
        )
    else:
        src_metadata.mark_clean(target_path)
        print(
            f"✔ Submitted {target_path}: code unchanged, in-band metadata marked clean (LAST_CLEANED updated, DIRTY cleared)"
        )
    return 0


def run_blame(
    file_path: str,
    blame_dep: str,
    critique: str,
    repo_root: Optional[str] = None,
) -> int:
    """Attributes critique to blame_dep, buffering into .cleanroom_blame_buffer.json if read-only."""
    root = os.path.realpath(repo_root or find_workspace_root())
    dep_path = _resolve_target_path(blame_dep, root)

    is_readonly = False
    if os.path.exists(dep_path):
        st = os.stat(dep_path)
        is_readonly = not bool(st.st_mode & stat.S_IWUSR)
    else:
        is_readonly = True

    ws_root = os.path.realpath(find_workspace_root())
    if is_readonly:
        buffer_path = os.path.join(ws_root, BLAME_BUFFER_FILE)
        entries: List[Dict[str, Any]] = []
        if os.path.isfile(buffer_path):
            try:
                with open(buffer_path, "r", encoding="utf-8") as bf:
                    entries = json.load(bf)
            except Exception:
                entries = []
        real_dep = os.path.realpath(dep_path) if os.path.exists(dep_path) else dep_path
        rel_t = (
            os.path.relpath(real_dep, ws_root)
            if str(real_dep).startswith(ws_root)
            else blame_dep
        )
        entries.append(
            {
                "target": rel_t.strip().lstrip("/"),
                "blamed_by": file_path,
                "explanation": critique,
                "dirty_reason": f"Blamed by {file_path}: {critique}",
                "timestamp": src_metadata.current_utc_timestamp(),
            }
        )
        cleanroom_workspace_tool.write_file_with_perms(
            buffer_path, json.dumps(entries, indent=2) + "\n", readonly=False
        )
        print(
            f"Recorded blame on read-only contract {blame_dep} into {BLAME_BUFFER_FILE}."
        )
        print(
            "It will be harvested into the canonical header when 'cleanroom-sync' runs."
        )
        return 0

    if os.path.exists(dep_path):
        src_metadata.append_feedback(dep_path, critique, sender=file_path)
        print(f"Appended FEEDBACK: into {dep_path}")
        return 0

    print(f"Error: Could not locate blame target '{blame_dep}'.")
    return 1


def run_fail(
    file_path: str,
    reason: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Marks target dirty with DIRTY tag and appends failure diagnostics."""
    root = os.path.realpath(repo_root or find_workspace_root())
    full_p = _resolve_target_path(file_path, root)

    failure_reason = reason or "Verification failed"
    if not os.path.isfile(full_p):
        print(f"Error: Target '{file_path}' not found.")
        return 1

    is_ro = False
    try:
        st = os.stat(full_p)
        is_ro = not bool(st.st_mode & stat.S_IWUSR)
    except OSError:
        is_ro = True

    ws_root = os.path.realpath(find_workspace_root())
    if is_ro:
        meta = get_current_role_metadata()
        role_name = meta.get("role_name", "auditor") if meta else "auditor"
        buffer_path = os.path.join(ws_root, BLAME_BUFFER_FILE)
        entries: List[Dict[str, Any]] = []
        if os.path.isfile(buffer_path):
            try:
                with open(buffer_path, "r", encoding="utf-8") as bf:
                    entries = json.load(bf)
            except Exception:
                entries = []
        real_p = os.path.realpath(full_p)
        rel_t = (
            os.path.relpath(real_p, ws_root)
            if real_p.startswith(ws_root)
            else file_path
        )
        entries.append(
            {
                "target": rel_t.strip().lstrip("/"),
                "blamed_by": f"{role_name} verification",
                "explanation": f"Verification failed: {failure_reason}",
                "dirty_reason": failure_reason,
                "timestamp": src_metadata.current_utc_timestamp(),
            }
        )
        cleanroom_workspace_tool.write_file_with_perms(
            buffer_path, json.dumps(entries, indent=2) + "\n", readonly=False
        )
        print(
            f"Recorded verification failure on read-only target {file_path} into {BLAME_BUFFER_FILE}."
        )
        print(
            "It will be harvested into the canonical header when 'cleanroom-sync' runs."
        )
        return 0

    src_metadata.mark_dirty(full_p, reason=failure_reason)
    src_metadata.append_feedback(
        full_p, f"Verification failed: {failure_reason}", sender="verification"
    )
    print(f"Marked failure on {full_p}: added DIRTY tag and updated LAST_CLEANED.")
    return 0


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="cleanroom_role_tool",
        description="Cleanroom Role Workspace Subagent CLI Tool",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # get_work
    p_work = subparsers.add_parser(
        "get_work", help="Get ready dirty tasks in workspace scope"
    )
    p_work.add_argument("dir", nargs="?", default=None, help="Directory scope override")

    # submit
    p_submit = subparsers.add_parser(
        "submit", help="Verify and submit target with in-band header update"
    )
    p_submit.add_argument("target", help="Target file path or unit name")
    p_submit.add_argument("summary", nargs="?", default=None, help="Change summary")

    # blame
    p_blame = subparsers.add_parser(
        "blame", help="Attribute blame feedback to an upstream contract"
    )
    p_blame.add_argument("target", help="Current local file")
    p_blame.add_argument("blame_target", help="Upstream contract path")
    p_blame.add_argument("explanation", help="Critique description")

    # fail
    p_fail = subparsers.add_parser(
        "fail", help="Record verification failure and force dirty state"
    )
    p_fail.add_argument("target", help="Target file path")
    p_fail.add_argument("reason", nargs="?", default=None, help="Failure reason")

    args = parser.parse_args(raw_args)

    if args.command == "get_work":
        return run_get_work(dir_scope=args.dir)
    elif args.command == "submit":
        return run_submit(args.target, summary=args.summary)
    elif args.command == "blame":
        return run_blame(args.target, args.blame_target, args.explanation)
    elif args.command == "fail":
        return run_fail(args.target, reason=args.reason)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
