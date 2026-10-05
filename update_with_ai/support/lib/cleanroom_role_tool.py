#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents.

Provides role-local commands executed inside a commissioned role workspace:
- get_work: Self-synchronizing queue inspector; pulls updates from main and evaluates DAG.
- submit: Directly mutates canonical main repo via Bazel _submit target (or direct fallback).
- blame: Directly appends critique to canonical contract in main repo via Bazel _blame target.
- fail: Directly forces dirty state and appends failure diagnostics in main repo.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
    if os.path.isdir(_p):
        if _p in sys.path:
            sys.path.remove(_p)
        sys.path.insert(0, _p)

import src_metadata
import cleanroom_workspace_tool

# Retained as legacy constants for backward compatibility
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


def _resolve_main_root(
    ws_root: str,
    meta: Optional[Dict[str, Any]] = None,
    repo_root: Optional[str] = None,
) -> str:
    """Resolves canonical main workspace root via convention or metadata."""
    if repo_root:
        return os.path.realpath(repo_root)
    if meta and meta.get("main_workspace_root"):
        return os.path.realpath(meta["main_workspace_root"])
    try:
        main_cand, _, _, _ = (
            cleanroom_workspace_tool.resolve_main_workspace_from_convention(ws_root)
        )
        return os.path.realpath(main_cand)
    except Exception:
        return ws_root


def _can_run_bazel(main_root: str) -> bool:
    """Checks whether Bazel can be invoked in the main repository."""
    if os.environ.get("CLEANROOM_DIRECT_MUTATION") == "1":
        return False
    if not (
        os.path.isfile(os.path.join(main_root, "MODULE.bazel"))
        or os.path.isfile(os.path.join(main_root, "WORKSPACE"))
    ):
        return False
    return shutil.which("bazel") is not None


def _is_test_file(target: str) -> bool:
    norm = target.strip().replace("\\", "/")
    return norm.endswith("_test.py") or "/tests/" in norm or norm.startswith("tests/")


def resolve_file_role(file_path: str, repo_root: str) -> str:
    """Derives role name (e.g. 'lib', 'low', 'high') from a target file path."""
    norm = file_path.replace("\\", "/")
    parent = os.path.basename(os.path.dirname(norm))
    known_roles = [
        "high",
        "planning",
        "low",
        "grounding",
        "grounding_qa",
        "lib",
        "test",
        "qa",
        "coverage",
    ]
    if parent in known_roles:
        return parent
    if parent == "tests":
        return "test"
    roles_def = cleanroom_workspace_tool.load_defined_roles(repo_root)
    for r_name, r_def in roles_def.items():
        pat = r_def.get("src_pattern", "")
        if pat:
            d, pfx, sfx = cleanroom_workspace_tool.parse_pattern_info(pat)
            fname = os.path.basename(norm)
            if parent == d and fname.startswith(pfx) and fname.endswith(sfx):
                return r_name
    return "lib"


def parse_unit_from_file_path(file_path: str, repo_root: str) -> Tuple[str, str, str]:
    """Returns (part_dir, unit_name, role_name) from file_path relative to repo_root."""
    norm_path = os.path.realpath(file_path)
    norm_root = os.path.realpath(repo_root)
    rel = (
        os.path.relpath(norm_path, norm_root).replace("\\", "/")
        if norm_path.startswith(norm_root)
        else file_path.replace("\\", "/")
    )
    fname = os.path.basename(rel)
    unit_name = os.path.splitext(fname)[0]
    if unit_name.endswith("_test"):
        unit_name = unit_name[:-5]
    role_name = resolve_file_role(rel, repo_root)
    part_dir = os.path.dirname(os.path.dirname(rel))
    return part_dir, unit_name, role_name


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
        if stem.endswith("_test"):
            stem = stem[:-5]
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
    if stem.endswith("_test"):
        stem = stem[:-5]
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


# ==============================================================================
# Role Commands: get_work, submit, blame, fail
# ==============================================================================


def run_get_work(
    dir_scope: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Evaluates dirtiness in local workspace scope and prints next ready tasks for this role."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    role_name = meta.get("role_name", "") if meta else ""
    d_scope = dir_scope or (meta.get("parts_dir", "staging") if meta else "staging")

    main_root = _resolve_main_root(ws_root, meta, repo_root)

    # 1 & 2: Inbound pull and fast system refresh from main if in a distinct role workspace
    if main_root and os.path.isdir(main_root) and main_root != ws_root:
        try:
            cleanroom_workspace_tool.pull_workspace_from_main(
                ws_root, main_root, role_name, dir_scope=d_scope, silent=True
            )
            cleanroom_workspace_tool.refresh_system_files_fast(
                ws_root, main_root, role_name, dir_scope=d_scope, silent=True
            )
        except Exception:
            pass

    # 3: Scope-wide dependency evaluation on the build graph
    eval_root = ws_root if (not repo_root and os.path.isdir(ws_root)) else main_root
    ready_items, blocked_items = cleanroom_workspace_tool.compute_role_work_queue(
        role_name, d_scope, eval_root
    )

    print(
        f"\n=== Cleanroom Work Queue [Role: {(role_name or 'ALL').upper()} | Scope: {d_scope}] ==="
    )
    if not ready_items and not blocked_items:
        print(
            f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
        )
        return 0

    total_dirty = len(ready_items) + len(blocked_items)
    print(f"Found {total_dirty} dirty unit(s) ({len(ready_items)} ready to clean):")
    for item in ready_items:
        print(f"\n  • [READY - {item['role'].upper()}] {item['target_file']}")
        for r in item["reasons"]:
            print(f"      - {r}")

    if blocked_items:
        print(f"\nBlocked unit(s) ({len(blocked_items)} waiting on prerequisites):")
        for item in blocked_items:
            print(f"\n  • [BLOCKED - {item['role'].upper()}] {item['target_file']}")
            for br in item.get("blocked_reasons", []):
                print(f"      - {br}")

    if cleanroom_workspace_tool.is_auditor_role(role_name):
        print(
            f"\nACTIONABLE NEXT STEP: Execute verification suite for target, then run 'bin/submit <target_file>' to attest {role_name.upper()}_AUDIT.\n"
        )
    else:
        print(
            "\nACTIONABLE NEXT STEP: Implement or verify target, then run 'bin/submit <file> \"<summary>\"' (or 'bin/submit <file>' if no changes).\n"
        )
    return 1 if ready_items else 0


def run_submit(
    target: str,
    summary: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Verifies target and stamps in-band metadata or <ROLE>_AUDIT directly in main."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    role_name = str(meta.get("role_name") or "") if meta else ""
    main_root = _resolve_main_root(ws_root, meta, repo_root)

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

    target_path, unit_name = resolve_submit_target(target, ws_root, role_name, meta)
    if not target_path or not os.path.isfile(target_path):
        target_path, unit_name = resolve_submit_target(
            target, main_root, role_name, meta
        )

    if not target_path or not os.path.isfile(target_path):
        print(f"Error: Target '{target}' not found on disk.")
        return 1

    role_def = cleanroom_workspace_tool.resolve_role_definition(role_name, main_root)

    # --- AUDITOR ROLE SUBMIT ---
    if cleanroom_workspace_tool.is_auditor_role(role_name):
        audit_tag = cleanroom_workspace_tool.AUDITOR_ROLE_TAGS.get(
            role_name, f"{role_name.upper()}_AUDIT"
        )

        ref_root = ws_root if target_path.startswith(ws_root) else main_root
        part_dir, u_name, _ = parse_unit_from_file_path(target_path, ref_root)
        active_unit = unit_name or u_name
        targets_to_audit = [
            os.path.join(main_root, part_dir, "lib", f"{active_unit}.py")
        ]
        fb_deps = role_def.get("feedback_role_deps", [])
        for fb_label in fb_deps:
            fb_def = cleanroom_workspace_tool.resolve_role_definition(
                fb_label, main_root
            )
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat:
                fb_full = os.path.join(
                    main_root,
                    fb_pat.format(unit_dir=part_dir, unit_name=active_unit),
                )
                if os.path.isfile(fb_full) and fb_full not in targets_to_audit:
                    targets_to_audit.append(fb_full)

        companion_test = os.path.join(
            main_root, part_dir, "tests", f"{active_unit}_test.py"
        )
        if os.path.isfile(companion_test) and companion_test not in targets_to_audit:
            targets_to_audit.append(companion_test)

        if _can_run_bazel(main_root):
            submit_target = f"//{part_dir}:{active_unit}_{role_name}_submit"
            cmd = ["bazel", "run", submit_target]
            res = subprocess.run(cmd, cwd=main_root)
            if res.returncode != 0:
                return res.returncode
        else:
            # Direct mutation on main_root
            stamped = []
            for tf in targets_to_audit:
                if os.path.isfile(tf):
                    src_metadata.stamp_audit(tf, role_name)
                    src_metadata.update_metadata(tf, clear_dirty=True)
                    stamped.append(os.path.relpath(tf, main_root))

            if stamped:
                print(
                    f"✔ Audited target stamped: {', '.join(stamped)} (Tagged: {audit_tag})"
                )

        # Reflect attested audits to local role workspace if present
        if ws_root != main_root:
            for tf in targets_to_audit:
                rel = os.path.relpath(tf, main_root)
                wt = os.path.join(ws_root, rel)
                if os.path.isfile(tf) and os.path.isfile(wt):
                    cleanroom_workspace_tool.copy_file_with_perms(tf, wt, readonly=True)

        return 0

    # --- PRODUCER ROLE SUBMIT ---
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

    # 3. Symmetric change summary validation
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

    # 4. Copy modified file to canonical main workspace
    rel_path = (
        os.path.relpath(target_path, ws_root)
        if target_path.startswith(ws_root)
        else os.path.relpath(target_path, main_root)
    )
    main_file = os.path.join(main_root, rel_path)
    if ws_root != main_root and os.path.isfile(target_path):
        cleanroom_workspace_tool.copy_file_with_perms(
            target_path, main_file, readonly=False
        )

    part_dir, u_name, _ = parse_unit_from_file_path(target_path, ws_root)
    active_unit = unit_name or u_name

    if _can_run_bazel(main_root):
        submit_target = f"//{part_dir}:{active_unit}_{role_name}_submit"
        cmd = ["bazel", "run", submit_target]
        if summary_provided:
            cmd.extend(["--", summary_text])
        else:
            cmd.append("--")
        res = subprocess.run(cmd, cwd=main_root)
        if res.returncode != 0:
            return res.returncode
        if ws_root != main_root and os.path.isfile(main_file):
            cleanroom_workspace_tool.copy_file_with_perms(
                main_file, target_path, readonly=False
            )
        return 0
    else:
        # Direct mutation on main_file
        if is_modified:
            src_metadata.record_change(main_file, summary_text)
            print(
                f"✔ Submitted {target_path}: code modified and in-band metadata updated (CHANGE: {summary_text})"
            )
        else:
            src_metadata.mark_clean(main_file)
            print(
                f"✔ Submitted {target_path}: code unchanged, in-band metadata marked clean (LAST_CLEANED updated, DIRTY cleared)"
            )
        if ws_root != main_root and os.path.isfile(main_file):
            cleanroom_workspace_tool.copy_file_with_perms(
                main_file, target_path, readonly=False
            )
        return 0


def run_blame(
    culprit_file: str,
    critique: str,
    repo_root: Optional[str] = None,
) -> int:
    """Attributes critique directly to upstream contract or culprit file in main."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    main_root = _resolve_main_root(ws_root, meta, repo_root)

    dep_path = _resolve_target_path(culprit_file, main_root)
    if not os.path.exists(dep_path):
        dep_path = _resolve_target_path(culprit_file, ws_root)
    if not os.path.exists(dep_path):
        print(f"Error: Could not locate blame target '{culprit_file}'.")
        return 1

    caller = meta.get("role_name", "") if meta else ""
    if not caller:
        caller = (
            os.environ.get("CLEANROOM_ROLE") or os.environ.get("USER") or "cleanroom"
        )

    ref_root = main_root if dep_path.startswith(main_root) else ws_root
    part_dir, unit_name, blamed_role = parse_unit_from_file_path(dep_path, ref_root)
    main_dep_path = os.path.join(main_root, os.path.relpath(dep_path, ref_root))

    if _can_run_bazel(main_root):
        blame_target = f"//{part_dir}:{unit_name}_{blamed_role}_blame"
        cmd = ["bazel", "run", blame_target, "--", critique]
        res = subprocess.run(cmd, cwd=main_root)
        if res.returncode != 0:
            return res.returncode
        if ws_root != main_root and os.path.isfile(main_dep_path):
            ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
            if os.path.exists(ws_dep):
                cleanroom_workspace_tool.copy_file_with_perms(
                    main_dep_path, ws_dep, readonly=True
                )
        return 0
    else:
        target_to_mutate = main_dep_path if os.path.exists(main_dep_path) else dep_path
        src_metadata.append_feedback(target_to_mutate, critique, sender=caller)
        src_metadata.mark_dirty(target_to_mutate, f"Blamed by {caller}: {critique}")
        src_metadata.update_metadata(
            target_to_mutate, last_cleaned=src_metadata.current_utc_timestamp()
        )
        print(f"Appended FEEDBACK: into {target_to_mutate}")
        if ws_root != main_root and os.path.isfile(main_dep_path):
            ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
            if os.path.exists(ws_dep):
                cleanroom_workspace_tool.copy_file_with_perms(
                    main_dep_path, ws_dep, readonly=True
                )
        return 0


def run_fail(
    file_path: str,
    reason: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Marks target dirty with DIRTY tag and appends failure diagnostics in main."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    main_root = _resolve_main_root(ws_root, meta, repo_root)

    full_p = _resolve_target_path(file_path, main_root)
    if not os.path.isfile(full_p):
        full_p = _resolve_target_path(file_path, ws_root)

    failure_reason = reason or "Verification failed"
    if not os.path.isfile(full_p):
        print(f"Error: Target '{file_path}' not found.")
        return 1

    ref_root = main_root if full_p.startswith(main_root) else ws_root
    rel_p = os.path.relpath(full_p, ref_root)
    main_p = os.path.join(main_root, rel_p)
    target_to_mutate = main_p if os.path.exists(main_p) else full_p

    src_metadata.mark_dirty(target_to_mutate, reason=failure_reason)
    src_metadata.append_feedback(
        target_to_mutate,
        f"Verification failed: {failure_reason}",
        sender="verification",
    )
    print(
        f"Marked failure on {target_to_mutate}: added DIRTY tag and updated LAST_CLEANED."
    )

    if ws_root != main_root and os.path.isfile(main_p):
        ws_p = os.path.join(ws_root, rel_p)
        if os.path.exists(ws_p):
            is_ro = not bool(os.stat(ws_p).st_mode & stat.S_IWUSR)
            cleanroom_workspace_tool.copy_file_with_perms(main_p, ws_p, readonly=is_ro)

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
        "blame",
        help="Attribute blame feedback to a culprit file or upstream contract",
        description="Attributes actionable critique to a culprit specification, code, or test file.",
    )
    p_blame.add_argument(
        "culprit_file",
        metavar="<culprit-file>",
        help="Path to the culprit file receiving blame",
    )
    p_blame.add_argument(
        "critique",
        metavar="<actionable-critique>",
        help="Actionable critique message without newlines",
    )

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
        return run_blame(args.culprit_file, args.critique)
    elif args.command == "fail":
        return run_fail(args.target, reason=args.reason)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
