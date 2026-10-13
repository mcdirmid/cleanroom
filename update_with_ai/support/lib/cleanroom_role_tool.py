#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents."""
from __future__ import annotations
import argparse
import importlib
import json
import os
import sys
from typing import Any


def _get_dir_scope() -> str:
    curr = os.path.dirname(os.path.realpath(__file__))
    while curr and curr != os.path.dirname(curr):
        cfg = os.path.join(curr, ".cleanroom_role.json")
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    return str(json.load(f).get("dir_scope", "") or "")
            except Exception:
                pass
            break
        curr = os.path.dirname(curr)
    return ""


def _get_roots() -> list[str]:
    roots, curr = [], os.path.dirname(os.path.realpath(__file__))
    while curr and curr != os.path.dirname(curr):
        cfg = os.path.join(curr, ".cleanroom_role.json")
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    m = json.load(f).get("main_workspace_root")
                if m and os.path.isdir(m):
                    roots.append(m)
            except Exception:
                pass
            roots.append(curr)
            break
        if os.path.isfile(os.path.join(curr, "pyproject.toml")) or os.path.isfile(os.path.join(curr, "cleanroom.toml")):
            roots.append(curr)
            break
        curr = os.path.dirname(curr)
    return roots or [os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../.."))]


_dir_scope = _get_dir_scope()
for _r in _get_roots():
    if os.path.isdir(_r) and _r not in sys.path:
        sys.path.insert(0, _r)
    try:
        for _entry in os.listdir(_r):
            if _dir_scope and _entry == _dir_scope:
                continue
            _pkg_dir = os.path.join(_r, _entry)
            if os.path.isdir(_pkg_dir) and not _entry.startswith((".", "bazel-", "venv")):
                _sup_lib = os.path.join(_pkg_dir, "support", "lib")
                if os.path.isdir(_sup_lib):
                    if _pkg_dir not in sys.path:
                        sys.path.insert(0, _pkg_dir)
                    if _sup_lib not in sys.path:
                        sys.path.insert(0, _sup_lib)
    except OSError:
        pass

workspace_tool_impl = None
for _r in _get_roots():
    if not os.path.isdir(_r):
        continue
    try:
        for _entry in os.listdir(_r):
            if _dir_scope and _entry == _dir_scope:
                continue
            if not _entry.startswith((".", "bazel-", "venv")):
                _cand_tool = os.path.join(_r, _entry, "parts", "workspace", "lib", "workspace_tool_impl.py")
                if os.path.isfile(_cand_tool) and os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                    try:
                        workspace_tool_impl = importlib.import_module(f"{_entry}.parts.workspace.lib.workspace_tool_impl")
                        break
                    except ImportError:
                        pass
    except OSError:
        pass
    if workspace_tool_impl is not None:
        break

if workspace_tool_impl is None:
    try:
        from update_with_ai.parts.workspace.lib import workspace_tool_impl
    except ImportError:
        try:
            workspace_tool_impl = importlib.import_module("parts.workspace.lib.workspace_tool_impl")
        except ImportError:
            pass

if workspace_tool_impl is None:
    raise ImportError("Failed to locate workspace_tool_impl module across discovered Cleanroom roots")

AUDIT_BUFFER_FILE = workspace_tool_impl.AUDIT_BUFFER_FILE
BLAME_BUFFER_FILE = workspace_tool_impl.BLAME_BUFFER_FILE
PENDING_WORK_FILE = workspace_tool_impl.PENDING_WORK_FILE
write_file_with_perms = workspace_tool_impl.write_file_with_perms
copy_file_with_perms = workspace_tool_impl.copy_file_with_perms
compute_role_work_queue = workspace_tool_impl.compute_role_work_queue
get_pending_work = workspace_tool_impl.get_pending_work
set_pending_work = workspace_tool_impl.set_pending_work
clear_pending_work = workspace_tool_impl.clear_pending_work
remove_pending_target = workspace_tool_impl.remove_pending_target
is_pending_target_dirty = workspace_tool_impl.is_pending_target_dirty
find_workspace_root = workspace_tool_impl.find_workspace_root
get_current_role_metadata = workspace_tool_impl.get_current_role_metadata
is_auditor_role = workspace_tool_impl.is_auditor_role
resolve_cleanroom_log_path = workspace_tool_impl.resolve_cleanroom_log_path
append_cleanroom_log = workspace_tool_impl.append_cleanroom_log


def run_clean_all(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="cleanroom clean-all",
        description="Verify/commission role workspaces and report dirty nodes for autonomous coordination.",
    )
    parser.add_argument(
        "scope",
        nargs="?",
        default="",
        help="Directory scope to clean (e.g. staging).",
    )
    parser.add_argument(
        "target_role",
        nargs="?",
        default="",
        help="Optional role boundary: clean up to and including this role (e.g. qa).",
    )
    parser.add_argument(
        "--scope",
        dest="scope_opt",
        default="",
        help="Directory scope (alternative flag).",
    )
    parser.add_argument(
        "--role",
        dest="role_opt",
        default="",
        help="Optional role boundary: clean up to and including this role (alternative flag).",
    )
    parser.add_argument(
        "-antigravity",
        "--antigravity",
        action="store_true",
        help="Target Google Antigravity coordinator subagent execution.",
    )
    parser.add_argument(
        "--commission-only",
        action="store_true",
        help="Only commission workspaces without checking work queues.",
    )
    parsed = parser.parse_args(argv)
    scope = parsed.scope_opt or parsed.scope or _get_dir_scope()
    if not scope:
        print("Error: Directory scope must be specified (e.g. bin/cleanroom clean-all staging).", file=sys.stderr)
        return 1

    target_role = (parsed.role_opt or parsed.target_role or "").strip().lower()

    root = find_workspace_root()
    assert workspace_tool_impl is not None

    with workspace_tool_impl.enter_phase(workspace_tool_impl.agent_session.agent_session):
        reg = workspace_tool_impl.get_singleton(workspace_tool_impl.workspace_registry.WorkspaceRegistry)
        prov = workspace_tool_impl.get_singleton(workspace_tool_impl.workspace_provision.WorkspaceProvisioner)
        work = workspace_tool_impl.get_singleton(workspace_tool_impl.workspace_work.WorkspaceWorkManager)

        declared_roles = reg.list_roles(root, dir_scope=scope)
        if not declared_roles:
            print(f"Error: No declared roles found for directory scope '{scope}'.", file=sys.stderr)
            return 1

        if target_role:
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                if r.role_name.lower() == target_role:
                    matching_idx = idx
                    break
            if matching_idx is None:
                valid_names = ", ".join(r.role_name for r in declared_roles)
                print(f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}", file=sys.stderr)
                return 1
            declared_roles = list(declared_roles[: matching_idx + 1])

        role_suffix = f" (up to role: {target_role})" if target_role else ""
        print(f"=== Cleanroom Clean-All [Scope: {scope}{role_suffix}] ===")
        print(f"Commissioning/verifying {len(declared_roles)} role workspaces...")
        commissioned_dirs = []
        for r in declared_roles:
            ws_info = prov.commission(
                role_name=r.role_name,
                dir_scope=scope,
                repo_root=root,
            )
            commissioned_dirs.append((r.role_name, ws_info.workspace_dir))
        parent_ws_dir = os.path.dirname(commissioned_dirs[0][1]) if commissioned_dirs else ""
        print(f"[OK] All {len(commissioned_dirs)} role workspaces ready in {parent_ws_dir}.")

        if parsed.commission_only:
            return 0

        ready_nodes: list[tuple[str, str, list[str]]] = []
        blocked_nodes: list[tuple[str, str, list[str]]] = []
        for r in declared_roles:
            q_ready, q_blocked = work.compute_role_work_queue(r.role_name, dir_scope=scope, repo_root=root)
            for it in q_ready:
                ready_nodes.append((r.role_name, it.target_file, list(it.dirtiness_reasons)))
            for it in q_blocked:
                blocked_nodes.append((r.role_name, it.target_file, list(it.blocked_reasons)))

        if not ready_nodes and not blocked_nodes:
            print(f"✔ CLEAN: All nodes in scope '{scope}' evaluate CLEAN{role_suffix}. No work pending.")
            return 0

        print(f"\nDirty Nodes Detected in Scope '{scope}'{role_suffix}:")
        print(f"  • {len(ready_nodes)} node(s) READY for dispatch:")
        for r_name, t_file, reasons in ready_nodes:
            r_msg = reasons[0] if reasons else "dirty"
            print(f"      [{r_name}] {t_file} -> {r_msg}")
        if blocked_nodes:
            print(f"  • {len(blocked_nodes)} node(s) BLOCKED on upstream dependencies:")
            for r_name, t_file, reasons in blocked_nodes:
                b_msg = reasons[0] if reasons else "blocked"
                print(f"      [{r_name}] {t_file} -> {b_msg}")

        role_hint = f" up to {target_role}" if target_role else ""
        queue_hint = f" {target_role}" if target_role else ""
        print("\n" + "=" * 72)
        print("AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE:")
        print(f"Instruct the assistant: 'Clean all dirty nodes in {scope}{role_hint} using cleanroom_coordinator'")
        print("The coordinator subagent will:")
        print(f"  1. Evaluate DAG ready nodes via 'bin/cleanroom work-queue {scope}{queue_hint} --json'.")
        print("  2. Wake/dispatch workspace-bound role subagents.")
        print("  3. Direct role workers to drain ready nodes via submit, blame, or fail.")
        print("  4. Converge the DAG across topological waves.")
        print("=" * 72)
        return 0


def run_work_queue(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom work-queue",
        description="Inspect Cleanroom DAG work queue for ready and blocked nodes across declared roles.",
    )
    parser.add_argument(
        "scope",
        nargs="?",
        default="",
        help="Directory scope to inspect (e.g. staging).",
    )
    parser.add_argument(
        "target_role",
        nargs="?",
        default="",
        help="Optional role boundary: inspect up to and including this role (e.g. qa).",
    )
    parser.add_argument(
        "--scope",
        dest="scope_opt",
        default="",
        help="Directory scope (alternative flag).",
    )
    parser.add_argument(
        "--role",
        dest="role_opt",
        default="",
        help="Optional role boundary: inspect up to and including this role (alternative flag).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output queue state as structured JSON.",
    )
    parsed = parser.parse_args(argv)
    scope = parsed.scope_opt or parsed.scope or _get_dir_scope()
    if not scope:
        print("Error: Directory scope must be specified (e.g. bin/cleanroom work-queue staging).", file=sys.stderr)
        return 1

    target_role = (parsed.role_opt or parsed.target_role or "").strip().lower()

    root = find_workspace_root()
    assert workspace_tool_impl is not None

    with workspace_tool_impl.enter_phase(workspace_tool_impl.agent_session.agent_session):
        reg = workspace_tool_impl.get_singleton(workspace_tool_impl.workspace_registry.WorkspaceRegistry)
        work = workspace_tool_impl.get_singleton(workspace_tool_impl.workspace_work.WorkspaceWorkManager)

        declared_roles = reg.list_roles(root, dir_scope=scope)
        if not declared_roles:
            print(f"Error: No declared roles found for directory scope '{scope}'.", file=sys.stderr)
            return 1

        if target_role:
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                if r.role_name.lower() == target_role:
                    matching_idx = idx
                    break
            if matching_idx is None:
                valid_names = ", ".join(r.role_name for r in declared_roles)
                print(f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}", file=sys.stderr)
                return 1
            declared_roles = list(declared_roles[: matching_idx + 1])

        ready_by_role: dict[str, list[dict[str, Any]]] = {}
        blocked_by_role: dict[str, list[dict[str, Any]]] = {}
        for r in declared_roles:
            q_ready, q_blocked = work.compute_role_work_queue(r.role_name, dir_scope=scope, repo_root=root)
            if q_ready:
                ready_by_role[r.role_name] = [
                    {"target": it.target_file, "reasons": list(it.dirtiness_reasons)}
                    for it in q_ready
                ]
            if q_blocked:
                blocked_by_role[r.role_name] = [
                    {"target": it.target_file, "reasons": list(it.blocked_reasons)}
                    for it in q_blocked
                ]

        is_clean = not ready_by_role and not blocked_by_role
        if parsed.json:
            import json
            payload: dict[str, Any] = {
                "scope": scope,
                "is_clean": is_clean,
                "ready_roles": list(ready_by_role.keys()),
                "ready": ready_by_role,
                "blocked": blocked_by_role,
            }
            if target_role:
                payload["up_to_role"] = target_role
            print(json.dumps(payload, indent=2))
            return 0

        if is_clean:
            print(f"CLEAN: All nodes in scope '{scope}' evaluate clean across all {len(declared_roles)} roles.")
            return 0

        print(f"DAG Work Queue for Scope '{scope}':")
        if ready_by_role:
            print(f"  READY Roles ({len(ready_by_role)}):")
            for r_name, items in ready_by_role.items():
                print(f"    • [{r_name}] {len(items)} ready target(s):")
                for it in items:
                    reason = f" ({it['reasons'][0]})" if it["reasons"] else ""
                    print(f"        - {it['target']}{reason}")
        else:
            print("  READY Roles: None")

        if blocked_by_role:
            print(f"  BLOCKED Roles ({len(blocked_by_role)}):")
            for r_name, items in blocked_by_role.items():
                print(f"    • [{r_name}] {len(items)} blocked target(s):")
                for it in items:
                    reason = f" ({it['reasons'][0]})" if it["reasons"] else ""
                    print(f"        - {it['target']}{reason}")
        return 0


def main(argv: list[str] | None = None) -> int:
    asm_modules = (
        "parts.systems.lib.uv_cleanroom_asm",
        "parts.core.lib.file_paths_impl",
        "parts.control.lib.control_asm",
        "parts.tools.lib.tools_asm",
        "parts.workspace.lib.workspace_asm",
        "parts.workspace.lib.workspace_tool_impl",
        "parts.subagent.lib.subagent_asm",
        "parts.subagent.lib.subagent_tool_impl",
    )
    for mod_name in asm_modules:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "__initialize__"):
                mod.__initialize__()
        except (ImportError, AttributeError):
            pass

    for _r in _get_roots():
        if not os.path.isdir(_r):
            continue
        try:
            for _entry in os.listdir(_r):
                if _dir_scope and _entry == _dir_scope:
                    continue
                if not _entry.startswith((".", "bazel-", "venv")):
                    if os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                        for sub in (
                            "systems.lib.uv_cleanroom_asm",
                            "core.lib.file_paths_impl",
                            "control.lib.control_asm",
                            "tools.lib.tools_asm",
                            "workspace.lib.workspace_asm",
                            "workspace.lib.workspace_tool_impl",
                            "subagent.lib.subagent_asm",
                            "subagent.lib.subagent_tool_impl",
                        ):
                            try:
                                mod = importlib.import_module(f"{_entry}.parts.{sub}")
                                if hasattr(mod, "__initialize__"):
                                    mod.__initialize__()
                            except (ImportError, AttributeError):
                                pass
        except OSError:
            pass

    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] in ("clean-all", "clean_all"):
        return run_clean_all(args_list[1:])

    if args_list and args_list[0] in ("work-queue", "work_queue", "queue"):
        return run_work_queue(args_list[1:])

    if args_list and args_list[0] == "orchestrate":
        subagent_tool_mod = None
        for _r in _get_roots():
            for _entry in os.listdir(_r) if os.path.isdir(_r) else []:
                if _entry.startswith((".", "bazel-", "venv")):
                    continue
                try:
                    subagent_tool_mod = importlib.import_module(f"{_entry}.parts.subagent.lib.subagent_tool_impl")
                    break
                except ImportError:
                    pass
            if subagent_tool_mod:
                break
        if subagent_tool_mod is None:
            try:
                from update_with_ai.parts.subagent.lib import subagent_tool_impl as subagent_tool_mod
            except ImportError:
                try:
                    subagent_tool_mod = importlib.import_module("parts.subagent.lib.subagent_tool_impl")
                except ImportError:
                    pass
        if subagent_tool_mod is not None:
            return subagent_tool_mod.main(args_list)

    assert workspace_tool_impl is not None
    return workspace_tool_impl.main(argv)


if __name__ == "__main__":
    sys.exit(main())
