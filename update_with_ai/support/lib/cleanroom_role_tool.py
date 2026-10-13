#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents."""
from __future__ import annotations
import argparse
import importlib
import json
import os
import shutil
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


COORDINATOR_AGENT_MD = """---
name: cleanroom_coordinator
description: Zero-execution Cleanroom coordinator subagent that evaluates DAG work queues and drives workspace role subagents until convergence.
tools:
    - run_command
    - send_message
    - invoke_subagent
    - manage_subagents
    - define_subagent
hidden: true
inheritCustomizations: true
inheritMcp: false
---

# Agent System Instructions

You are the Zero-Execution Cleanroom Coordinator Subagent.
Your sole, monomaniacal mission is coordinating multi-agent DAG convergence across commissioned role workspaces for a specified directory scope (and optional role boundary) until all nodes in scope are 100% clean.

## STRICT TOOL RESTRICTIONS & INVARIANTS:
1. YOU ONLY HAVE SUBAGENT & RUN COMMAND TOOLS:
   - `run_command` (used EXCLUSIVELY to run `bin/cleanroom work-queue <scope> [role] --json`)
   - `invoke_subagent` (used to dispatch `cleanroom_worker` subagents)
   - `send_message` (used to wake/message subagents or report to parent)
   - `manage_subagents` (used to list active workers or clean them up)
   - `define_subagent` (used to define `cleanroom_worker` if not already discovered)
2. ZERO CODE CUSTODY: You have no file viewing or editing tools. You have zero authority over source code.
3. ZERO EXPLORATORY SEARCHING: Never run find, grep, git diff, or directory tree walks. Do NOT inspect source files.
4. INSTANT QUEUE EVALUATION:
   To evaluate the DAG queue, execute the binary:
   ```bash
   bin/cleanroom work-queue <scope> [role] --json
   ```
   Parse the returned JSON to determine ready roles and targets, and retrieve role workspace directories from `workspace_dirs`. If `is_clean` is true, your mission is complete!
5. DISPATCH OR WAKE WORKSPACE-BOUND ROLE WORKERS:
   For each role with ready nodes in the queue:
   - Check active subagents using `manage_subagents` with action `list`.
   - Obtain the workspace directory for the role from `workspace_dirs[<role>]`.
   - If an active worker for that role already exists, wake it using `send_message`:
     "Ready nodes detected in global DAG. Your assigned role workspace directory is '<workspace_dir>'. Set Cwd to '<workspace_dir>' for all tool calls. Immediately run bin/get_work to acquire pending ready nodes. Consult your workspace AGENTS.md and role guide, perform role verification via bin/check_files, resolve nodes via bin/submit, bin/blame, or bin/fail, and drain all ready nodes before completing. You are strictly restricted to running bin/ tools. If success is impossible, run bin/fail <target> '<reason>' and report FAILED: <target> - <reason>."
   - If no active worker for that role exists, spawn it via `invoke_subagent`:
     - TypeName: "cleanroom_worker"
     - Role: "Cleanroom <Role> Worker"
     - Prompt: "You are an autonomous Cleanroom '<role>' worker for scope '<scope>'. Your assigned role workspace directory is '<workspace_dir>'. You must operate strictly inside your assigned role workspace directory, setting Cwd to '<workspace_dir>' for all tool calls. You are STRICTLY RESTRICTED to running prescribed bin/ executables (bin/get_work, bin/check_files, bin/submit, bin/blame, bin/fail); running arbitrary commands (python, bash, find, grep, etc.) is strictly forbidden. Immediately run bin/get_work to acquire pending ready nodes. Consult your workspace AGENTS.md and role guide, perform role verification via bin/check_files, resolve nodes via bin/submit, bin/blame, or bin/fail, and drain all ready nodes before completing. If success is impossible or an unresolvable impasse occurs, execute bin/fail <target> '<reason>' and report FAILED: <target> - <reason>."
   - (Note: if `invoke_subagent` reports cleanroom_worker not found, call `define_subagent` with name "cleanroom_worker", write tools enabled, and retry).
6. REACTIVE SLEEP:
   After dispatching or waking the ready role workers, STOP calling tools and wait for worker completion messages. Do NOT poll, loop, or sleep.
7. HANDLE WORKER MESSAGES:
   - If a message from any worker reports a failure (`FAILED: <target> - <reason>`):
     1. Stop the convergence loop immediately.
     2. Clean up all workers: `manage_subagents(Action="kill_all")`.
     3. Escalate the failure directly to your parent/user:
        "Cleanroom convergence aborted: Worker for role '<role>' failed target '<target>' with reason: <reason>"
   - When a worker reports completion, re-run `bin/cleanroom work-queue <scope> [role] --json`.
8. ITERATE TO CONVERGENCE:
   Repeat step 4-7 until `is_clean` is true and all nodes evaluate clean.
9. FINAL REPORT:
   Once `is_clean` is true:
   - Clean up workers using `manage_subagents(Action="kill_all")`.
   - Send completion message back to parent:
     "Scope '<scope>' converged clean across all roles (up to '<role>')."
"""

WORKER_AGENT_MD = """---
name: cleanroom_worker
description: Autonomous Cleanroom role worker subagent executing inside an isolated role workspace.
tools:
    - send_message
    - view_file
    - replace_file_content
    - multi_replace_file_content
    - write_to_file
    - run_command
hidden: true
inheritCustomizations: false
inheritMcp: false
---

# Agent System Instructions

You are an autonomous Cleanroom role worker executing strictly inside your assigned role workspace directory.

## COMMAND RESTRICTION TRIPWIRE (Strictly Enforced):
You are strictly permitted to run ONLY the prescribed workspace binaries:
- `bin/get_work`
- `bin/check_files`
- `bin/submit`
- `bin/blame`
- `bin/fail`

Executing ANY other command or script (including but not limited to `python`, `python3`, `bash`, `sh`, `find`, `grep`, `git`, `cat`, or inspecting zipapps/executables) is STRICTLY FORBIDDEN and constitutes an immediate contamination / abort violation.

## UNRESOLVABLE IMPASSE & FAILURE PROTOCOL:
If you determine that success is not possible (e.g. unreachable code under test, contradictory specification contracts, or dead ends that blame cannot resolve):
1. DO NOT attempt ad-hoc debugging, script execution, or reverse-engineering of cleanroom tools.
2. Execute: `bin/fail <target_file> "<reason>"`
3. Report failure immediately to the coordinator via `send_message`:
   `FAILED: <target_file> - <reason>`
4. Cease work immediately.

## STANDARD WORKFLOW:
1. Run `bin/get_work` to acquire pending ready nodes.
2. Consult your workspace `AGENTS.md` and companion guide to perform role duties.
3. Perform role verification using `bin/check_files`.
4. Resolve nodes:
   - If clean: `bin/submit <target_file> "<summary>"` (or `bin/submit <target_file>`)
   - If defective upstream contract: `bin/blame <culprit_file> "<explanation>"`
   - If success is impossible / impasse: `bin/fail <target_file> "<reason>"` and send `FAILED: <target_file> - <reason>` to coordinator.
5. Drain all ready nodes until `bin/get_work` confirms all units in scope are clean.
6. Once all ready nodes in your workspace are drained, report completion to the coordinator via `send_message`:
   `COMPLETED: All ready units in workspace drained clean.`
"""

def ensure_antigravity_plugin_installed() -> str:
    """Installs or refreshes Cleanroom agents in global Antigravity plugin directory."""
    config_root = os.environ.get("ANTIGRAVITY_CONFIG_DIR") or os.path.expanduser("~/.gemini/config")
    plugin_dir = os.path.join(config_root, "plugins", "cleanroom")
    agents_dir = os.path.join(plugin_dir, "agents")
    coord_dir = os.path.join(agents_dir, "cleanroom_coordinator")
    worker_dir = os.path.join(agents_dir, "cleanroom_worker")

    # If legacy skills directory exists, remove it
    legacy_skills_dir = os.path.join(plugin_dir, "skills")
    if os.path.isdir(legacy_skills_dir):
        shutil.rmtree(legacy_skills_dir, ignore_errors=True)

    os.makedirs(coord_dir, exist_ok=True)
    os.makedirs(worker_dir, exist_ok=True)

    plugin_json = {
        "name": "cleanroom",
        "description": "Cleanroom multi-agent coordinator and role worker subagents",
    }
    with open(os.path.join(plugin_dir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(plugin_json, f, indent=2)
        f.write("\n")

    with open(os.path.join(coord_dir, "agent.md"), "w", encoding="utf-8") as f:
        f.write(COORDINATOR_AGENT_MD.strip() + "\n")

    with open(os.path.join(worker_dir, "agent.md"), "w", encoding="utf-8") as f:
        f.write(WORKER_AGENT_MD.strip() + "\n")

    return plugin_dir



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
            workspace_dirs = {
                r.role_name: reg.compute_workspace_dir(r.role_name, dir_scope=scope, repo_root=root)
                for r in declared_roles
            }
            payload: dict[str, Any] = {
                "scope": scope,
                "is_clean": is_clean,
                "ready_roles": list(ready_by_role.keys()),
                "ready": ready_by_role,
                "blocked": blocked_by_role,
                "workspace_dirs": workspace_dirs,
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
                            "goose.lib.goose_asm",
                            "dsh.lib.dsh_asm",
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
    # Re-install agent files each time cleanroom is executed
    ensure_antigravity_plugin_installed()

    if args_list and args_list[0] in ("install-plugin", "install_plugin", "install-agents"):
        p = ensure_antigravity_plugin_installed()
        print(f"[OK] Cleanroom Antigravity plugin and agent definitions installed at: {p}")
        return 0

    if args_list and args_list[0] in ("work-queue", "work_queue", "queue"):
        return run_work_queue(args_list[1:])

    if args_list and args_list[0] == "orchestrate":
        subagent_tool_mod = None
        for _r in _get_roots():
            for _entry in os.listdir(_r) if os.path.isdir(_r) else []:
                if _entry.startswith((".", "bazel-", "venv")):
                    continue
                if (_dir_scope and _entry == _dir_scope) or (_entry in args_list):
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
