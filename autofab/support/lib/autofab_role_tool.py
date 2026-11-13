#!/usr/bin/env python3
"""autofab_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents."""

from __future__ import annotations
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Sequence


def _find_main_repo_root() -> str | None:
    main_root = os.environ.get("AUTOFAB_MAIN_ROOT") or os.environ.get(
        "CLEANROOM_MAIN_ROOT"
    )
    if main_root and os.path.isdir(main_root):
        return main_root
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        try:
            from support.lib import app_info as _ai
        except Exception:
            try:
                import app_info as _ai
            except Exception:
                _ai = None
        descriptors = (
            _ai.get_role_descriptors()
            if _ai
            else (".autofab_role.json", ".cleanroom_role.json")
        )
        ws_containers = (
            _ai.get_role_workspaces_containers()
            if _ai
            else ("autofab_role_workspaces", "role_workspaces")
        )
        config_filenames = (
            (_ai.get_config_filenames() + ("pyproject.toml",))
            if _ai
            else ("autofab.toml", "cleanroom.toml", "pyproject.toml")
        )

        for desc in descriptors:
            cfg = os.path.join(curr, desc)
            if os.path.isfile(cfg):
                try:
                    with open(cfg, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    root = data.get("main_repository_root")
                    if root and os.path.isdir(root):
                        return root
                except Exception:
                    pass
                parent = os.path.dirname(curr)
                if os.path.basename(parent) in ws_containers:
                    p_root = os.path.dirname(parent)
                    try:
                        for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                            if entry not in ws_containers:
                                cand = os.path.join(p_root, entry)
                                if os.path.isdir(cand) and (
                                    os.path.exists(os.path.join(cand, ".git"))
                                    or any(
                                        os.path.exists(os.path.join(cand, m))
                                        for m in config_filenames
                                    )
                                ):
                                    return cand
                    except OSError:
                        pass
                break
        if any(os.path.isfile(os.path.join(curr, m)) for m in config_filenames):
            return curr
        curr = os.path.dirname(curr)
    return None


def _get_app_info() -> Any:
    """Safely resolves app_info module, preventing collisions with workspace support directories."""
    try:
        from support.lib import app_info

        if hasattr(app_info, "APP_NAME"):
            return app_info
    except Exception:
        pass
    try:
        import app_info

        if hasattr(app_info, "APP_NAME"):
            return app_info
    except Exception:
        pass
    repo_root = _find_main_repo_root()
    if repo_root and os.path.isdir(repo_root):
        cand_roots = [""]
        try:
            cand_roots.extend(
                [
                    entry
                    for entry in os.listdir(repo_root)
                    if os.path.isdir(os.path.join(repo_root, entry))
                    and not entry.startswith((".", "venv", "bazel-"))
                ]
            )
        except OSError:
            pass
        for pkg in cand_roots:
            cand = os.path.join(repo_root, pkg, "support", "lib", "app_info.py")
            if os.path.isfile(cand):
                try:
                    import importlib.util

                    spec = importlib.util.spec_from_file_location(
                        "support_lib_app_info", cand
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        return mod
                except Exception:
                    pass
    return None


try:
    import dotenv

    dotenv.load_dotenv()
    _app_info = _get_app_info()
    if _app_info and hasattr(_app_info, "get_user_config_dir"):
        _user_env = os.path.join(_app_info.get_user_config_dir(), ".env")
        if os.path.isfile(_user_env):
            dotenv.load_dotenv(_user_env)
except Exception:
    pass


def _get_dir_scope() -> str:
    curr = os.path.dirname(os.path.realpath(__file__))
    app_inf = _get_app_info()
    descriptors = (
        app_inf.get_role_descriptors()
        if hasattr(app_inf, "get_role_descriptors")
        else (".cleanroom_role.json",)
    )
    while curr and curr != os.path.dirname(curr):
        for desc in descriptors:
            cfg = os.path.join(curr, desc)
            if os.path.isfile(cfg):
                try:
                    with open(cfg, "r", encoding="utf-8") as f:
                        return str(json.load(f).get("dir_scope", "") or "")
                except Exception:
                    pass
                return ""
        curr = os.path.dirname(curr)
    return ""


def _get_roots() -> list[str]:
    roots, curr = [], os.path.dirname(os.path.realpath(__file__))
    app_inf = _get_app_info()
    descriptors = (
        app_inf.get_role_descriptors()
        if hasattr(app_inf, "get_role_descriptors")
        else (".cleanroom_role.json",)
    )
    cfg_names = (
        app_inf.get_config_filenames() + ("pyproject.toml",)
        if hasattr(app_inf, "get_config_filenames")
        else ("cleanroom.toml", "pyproject.toml")
    )
    while curr and curr != os.path.dirname(curr):
        if any(os.path.isfile(os.path.join(curr, desc)) for desc in descriptors):
            # In an isolated role workspace, curr is the sole root. Main root is isolated from sys.path.
            roots.append(curr)
            break
        if any(os.path.isfile(os.path.join(curr, m)) for m in cfg_names):
            roots.append(curr)
            break
        curr = os.path.dirname(curr)
    return roots or [
        os.path.abspath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../..")
        )
    ]


_dir_scope = _get_dir_scope()
for _r in _get_roots():
    if os.path.isdir(_r) and _r not in sys.path:
        sys.path.insert(0, _r)
    try:
        for _entry in os.listdir(_r):
            if _dir_scope and _entry == _dir_scope:
                continue
            _pkg_dir = os.path.join(_r, _entry)
            if os.path.isdir(_pkg_dir) and not _entry.startswith(
                (".", "bazel-", "venv")
            ):
                _sup_lib = os.path.join(_pkg_dir, "support", "lib")
                if os.path.isdir(_sup_lib):
                    if _pkg_dir not in sys.path:
                        sys.path.insert(0, _pkg_dir)
                    if _sup_lib not in sys.path:
                        sys.path.insert(0, _sup_lib)
    except OSError:
        pass

cli_tool_impl = None
commands_impl = None
pending_impl = None

for _r in _get_roots():
    if not os.path.isdir(_r):
        continue
    try:
        for _entry in os.listdir(_r):
            if _dir_scope and _entry == _dir_scope:
                continue
            if not _entry.startswith((".", "bazel-", "venv")):
                for _sub in ("workspace_cli", "tools", "workspace"):
                    if cli_tool_impl is None:
                        _cand_tool = os.path.join(
                            _r, _entry, "parts", _sub, "lib", "cli_tool_impl.py"
                        )
                        if os.path.isfile(_cand_tool) and os.path.isdir(
                            os.path.join(_r, _entry, "support", "lib")
                        ):
                            try:
                                cli_tool_impl = importlib.import_module(
                                    f"{_entry}.parts.{_sub}.lib.cli_tool_impl"
                                )
                            except ImportError:
                                pass
                    if commands_impl is None:
                        _cand_cmds = os.path.join(
                            _r, _entry, "parts", _sub, "lib", "commands_impl.py"
                        )
                        if os.path.isfile(_cand_cmds) and os.path.isdir(
                            os.path.join(_r, _entry, "support", "lib")
                        ):
                            try:
                                commands_impl = importlib.import_module(
                                    f"{_entry}.parts.{_sub}.lib.commands_impl"
                                )
                            except ImportError:
                                pass
                    if pending_impl is None:
                        _cand_pend = os.path.join(
                            _r, _entry, "parts", _sub, "lib", "pending_impl.py"
                        )
                        if os.path.isfile(_cand_pend) and os.path.isdir(
                            os.path.join(_r, _entry, "support", "lib")
                        ):
                            try:
                                pending_impl = importlib.import_module(
                                    f"{_entry}.parts.{_sub}.lib.pending_impl"
                                )
                            except ImportError:
                                pass
                if (
                    cli_tool_impl is not None
                    and commands_impl is not None
                    and pending_impl is not None
                ):
                    break
    except OSError:
        pass
    if (
        cli_tool_impl is not None
        and commands_impl is not None
        and pending_impl is not None
    ):
        break

if cli_tool_impl is None:
    try:
        from autofab.parts.workspace_cli.lib import cli_tool_impl
    except ImportError:
        try:
            cli_tool_impl = importlib.import_module(
                "autofab.parts.workspace.lib.cli_tool_impl"
            )
        except ImportError:
            pass

if commands_impl is None:
    try:
        from autofab.parts.workspace_cli.lib import commands_impl
    except ImportError:
        pass

if pending_impl is None:
    try:
        from autofab.parts.workspace_cli.lib import pending_impl
    except ImportError:
        pass

if cli_tool_impl is None:
    raise ImportError(
        "Failed to locate cli_tool_impl module across discovered Cleanroom roots"
    )

AUDIT_BUFFER_FILE = getattr(
    commands_impl, "AUDIT_BUFFER_FILE", ".cleanroom_audit_buffer.json"
)
BLAME_BUFFER_FILE = getattr(
    commands_impl, "BLAME_BUFFER_FILE", ".cleanroom_blame_buffer.json"
)
PENDING_WORK_FILE = getattr(
    commands_impl, "PENDING_WORK_FILE", ".cleanroom_pending_work.json"
)


def write_file_with_perms(
    dst: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    """Writes a text file and sets exact permissions, handling existing read-only files cleanly."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o644)
        except OSError:
            pass
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
    mode = 0o555 if executable else (0o444 if readonly else 0o644)
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
    from support.lib.lifecycle import get_singleton
    from autofab.parts.workspace.lib import provision

    get_singleton(provision.WorkspaceProvisioner).copy_file_with_permissions(
        src, dst, readonly=readonly, executable=executable
    )


def unlock_workspace_directories(workspace_dir: str) -> None:
    """Restores write permissions (0o755) on all directories within a workspace."""
    if not os.path.isdir(workspace_dir):
        return
    try:
        os.chmod(workspace_dir, 0o755)
    except OSError:
        pass
    for dirpath, dirs, _ in os.walk(workspace_dir, followlinks=False):
        for d in dirs:
            dp = os.path.join(dirpath, d)
            if not os.path.islink(dp):
                try:
                    os.chmod(dp, 0o755)
                except OSError:
                    pass


def lock_workspace_directories(
    workspace_dir: str,
    role_name: str | None = None,
    dir_scope: str = "",
    repo_root: str | None = None,
) -> None:
    """Locks non-writable directories in a workspace to 0o555 while preserving 0o755 on target directories."""
    try:
        from support.lib.lifecycle import get_singleton
        from autofab.parts.workspace.lib import provision

        prov = get_singleton(provision.WorkspaceProvisioner)
        prov.lock_workspace_directories(
            workspace_dir, role_name=role_name, dir_scope=dir_scope, repo_root=repo_root
        )
    except Exception:
        pass


def compute_role_work_queue(
    role_name: str, dir_scope: str, repo_root: str | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = repo_root or find_workspace_root()
    from support.lib.lifecycle import get_singleton
    from autofab.parts.workspace_cli.lib import work

    work = get_singleton(work.WorkspaceWorkManager)
    ready, blocked = work.compute_role_work_queue(
        role_name, dir_scope=dir_scope, repo_root=root
    )

    def _to_dict(it: Any) -> dict[str, Any]:
        if isinstance(it, dict):
            return it
        stem = os.path.splitext(os.path.basename(it.target_file))[0]
        if stem.endswith("_test"):
            stem = stem[:-5]
        return {
            "target": it.target_file,
            "target_file": it.target_file,
            "role": it.role_name,
            "reasons": list(it.dirtiness_reasons),
            "blocked_reasons": list(it.blocked_reasons),
            "dependencies": list(it.dependency_files),
            "contract_files": list(it.contract_files),
            "unit": stem,
            "unit_name": stem,
        }

    return ([_to_dict(x) for x in ready], [_to_dict(x) for x in blocked])


def find_workspace_root() -> str:
    assert commands_impl is not None
    return commands_impl.find_workspace_root()


def get_current_role_metadata(workspace_dir: str | None = None) -> dict[str, Any]:
    assert commands_impl is not None
    return commands_impl.get_current_role_metadata() or {}


def is_auditor_role(
    role_name: str, repo_root: str | None = None, dir_scope: str | None = None
) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    from support.lib.lifecycle import get_singleton
    from autofab.parts.workspace.lib import role_registry

    reg = get_singleton(role_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(
        r_def.audit_tag
        or not (
            r_def.src_pattern or (hasattr(r_def, "src_patterns") and r_def.src_patterns)
        )
    )


def resolve_autofab_log_path(
    role_name: str, repo_root: str | None = None, dir_scope: str | None = None
) -> str:
    assert commands_impl is not None
    return commands_impl.resolve_log_path(role_name, repo_root=repo_root)


def append_autofab_log(
    role_name: str,
    line: str,
    repo_root: str | None = None,
    dir_scope: str | None = None,
) -> None:
    assert commands_impl is not None
    commands_impl.append_log(role_name, line, repo_root=repo_root)


def _get_pending_manager():
    from autofab.parts.workspace_cli.lib import pending
    from support.lib.lifecycle import get_singleton

    return get_singleton(pending.WorkspacePendingManager)


def get_pending_work(workspace_dir: str) -> list[str]:
    return list(_get_pending_manager().get_pending_work(workspace_dir))


def set_pending_work(workspace_dir: str, targets: Sequence[str]) -> None:
    _get_pending_manager().set_pending_work(workspace_dir, targets)


def clear_pending_work(workspace_dir: str) -> None:
    _get_pending_manager().clear_pending_work(workspace_dir)


def remove_pending_target(workspace_dir: str, target: str) -> None:
    _get_pending_manager().remove_pending_target(workspace_dir, target)


def is_pending_target_dirty(
    workspace_dir: str,
    rel_path: str,
    repo_root: str | None = None,
    role_name: str | None = None,
) -> bool:
    return _get_pending_manager().is_pending_target_dirty(
        target_path=rel_path,
        workspace_dir=workspace_dir,
        main_root=repo_root,
        role_name=role_name,
    )


COORDINATOR_AGENT_MD = """---
name: autofab_coordinator
description: Zero-execution Autofab coordinator subagent that evaluates DAG work queues and drives workspace role subagents until convergence.
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

You are the Zero-Execution Autofab Coordinator Subagent.
Your sole, monomaniacal mission is coordinating multi-agent DAG convergence across commissioned role workspaces for a specified directory scope (and optional role boundary) until all nodes in scope are 100% clean.

## STRICT TOOL RESTRICTIONS & INVARIANTS:
1. YOU ONLY HAVE SUBAGENT & RUN COMMAND TOOLS:
   - `run_command` (used to run `uv run autofab work-queue <scope> [role] --json`, `uv run autofab verify-fused <workspace_dir>`, `uv run autofab harvest-fused <workspace_dir>`, and `uv run autofab decommission <scope> [role]`)
   - `invoke_subagent` (used to dispatch `autofab_worker` or `autofab_baseline_worker` subagents)
   - `send_message` (used to wake/message subagents or report to parent)
   - `manage_subagents` (used to list active workers or clean them up)
   - `define_subagent` (used to define worker subagents if not already discovered)
2. ZERO CODE CUSTODY: You have no file viewing or editing tools. You have zero authority over source code.
3. ZERO EXPLORATORY SEARCHING: Never run find, grep, git diff, or directory tree walks. Do NOT inspect source files.
4. INSTANT QUEUE EVALUATION:
   To evaluate the DAG queue, execute the binary:
   ```bash
   uv run autofab work-queue <scope> [role] --json
   ```
   (Note: if the prompt specifies `up to <role>`, `<scope>#<role>`, or a fused role like `baseline` or `pretense_baseline`, pass `<role>` as the second positional argument or `--role <role>`).
   Parse the returned JSON to determine ready roles and targets, and retrieve role workspace directories from `workspace_dirs`. If `is_clean` is true, proceed to step 9!
5. DISPATCH OR WAKE WORKSPACE-BOUND ROLE WORKERS:
   For each role with ready nodes in the queue:
   - Check active subagents using `manage_subagents` with action `list`.
   - Obtain the workspace directory for the role from `workspace_dirs[<role>]`.
   - If an active worker for that role already exists, wake it using `send_message`:
     - For standard roles:
       "Ready nodes detected in scope '<scope>'. Assigned workspace: '<workspace_dir>'. Run 'bin/get_work' to pull ready targets, author changes in place, verify with 'bin/check_files <target>', submit via 'bin/submit <target> \"<summary>\"' (or bin/blame/fail), and drain all ready nodes before completing."
     - For fused roles:
       "Ready nodes detected in scope '<scope>'. Assigned workspace: '<workspace_dir>'. Run 'bin/get_work' once at session start, verify with 'bin/verify_*' micro-binaries until all pass, and send 'COMPLETED' via send_message when done."
   - If no active worker for that role exists, spawn it via `invoke_subagent`:
     - TypeName: "autofab_worker" (or "autofab_baseline_worker" if role is a fused role like baseline or pretense_baseline)
     - Role: "Autofab <Role> Worker"
     - Model: "<antigravity_models[<role>]>" (MUST use `antigravity_models[<role>]` from `work-queue --json`: e.g. `"flash"` when `gemini-flash` is specified, `"flash_lite"` when `flash-lite` is specified, `"pro"` when `pro` is specified, and `"inherit"` when `gemini-argon` or `gemini-carbon` is specified since Antigravity does not expose Argon or Carbon directly for subagents)
     - Prompt:
       - For standard roles:
         "You are an autonomous Autofab '<role>' worker for scope '<scope>'. Your assigned role workspace directory is '<workspace_dir>'. Operate strictly inside your assigned workspace directory. Because shell working directory does not persist across tool calls, prefix all shell commands with 'cd <workspace_dir> && ' (e.g. 'cd <workspace_dir> && bin/get_work') and use absolute paths under '<workspace_dir>' for file tools. All target verification and round resolution must proceed through the prescribed bin/ executables in your workspace (consult AGENTS.md). 1. Immediately run 'cd <workspace_dir> && bin/get_work' to acquire pending ready nodes. 2. Consult your workspace AGENTS.md and companion guides in guides/ (e.g. 'guides/<guide_name>.md' located directly under your workspace root; do not prefix with scope), author target files directly in place (authoring in scratch/ or external folders is strictly prohibited). 3. Perform role verification ('cd <workspace_dir> && bin/check_files <target>'). 4. Resolve nodes ('bin/submit <target> \"<summary>\"', 'bin/blame', or 'bin/fail'). 5. When bin/get_work confirms all ready targets are resolved, conclude your round immediately with summary text and ZERO tool calls. If success is impossible or an unresolvable impasse occurs, execute 'cd <workspace_dir> && bin/fail <target> \"<reason>\"' and report FAILED: <target> - <reason>."
       - For fused roles (e.g. baseline or pretense_baseline):
         "You are an autonomous Autofab fused '<role>' worker for scope '<scope>'. Your assigned role workspace directory is '<workspace_dir>'. Operate strictly inside your assigned workspace directory. Prefix all shell commands with 'cd <workspace_dir> && ' and use absolute paths under '<workspace_dir>' for file tools. All operational rules and constraints are defined in your workspace AGENTS.md. 1. Run 'cd <workspace_dir> && bin/get_work' ONCE at session start. 2. Implement library and tests consulting companion guides in 'guides/' directly in place. 3. Perform Arbiter self-audits (QA contract fidelity and Coverage semantic closure). 4. Verify with provisioned 'bin/verify_*' micro-binaries until all pass with 100% coverage. 5. Do NOT call bin/submit. When verified clean, report completion via send_message: 'COMPLETED: All targets passing for <scope>'."
   - (Note: if `invoke_subagent` reports autofab_worker not found, call `define_subagent` with name "autofab_worker", write tools enabled, and retry).
6. REACTIVE SLEEP:
   After dispatching or waking the ready role workers, STOP calling tools and wait for worker completion messages. Do NOT poll, loop, or sleep.
7. HANDLE WORKER MESSAGES:
   - If a message from any worker reports a failure (`FAILED: <target> - <reason>`):
     1. Stop the convergence loop immediately.
     2. Clean up all workers: `manage_subagents(Action="kill_all")`.
     3. Escalate the failure directly to your parent/user:
        "Autofab convergence aborted: Worker for role '<role>' failed target '<target>' with reason: <reason>"
   - When a worker reports completion:
     - Check if the worker is executing in a fused role workspace (e.g. role is `baseline` or `pretense_baseline`, or `.cleanroom_role.json` in `workspace_dir` has `fused_roles`).
     - If it is a fused worker:
       1. Run formal verification:
          `uv run autofab verify-fused <workspace_dir>`
       2. If verification fails:
          Send diagnostic failure feedback to worker via `send_message`:
          "Fused verification failed:\n<diagnostics>\nPlease fix these issues in your workspace ('<workspace_dir>'), re-verify using your workspace bin/verify_* micro-binaries, and send COMPLETED when ready."
          Track retry count (enforce a hardcoded maximum of 3 retries). If failures persist after 3 retries, abort with failure.
       3. If verification passes:
          Run atomic harvest to mark all constituent targets clean:
          `uv run autofab harvest-fused <workspace_dir>`
     - Re-run `uv run autofab work-queue <scope> [role] --json`.
8. ITERATE TO CONVERGENCE:
   Repeat step 4-7 until `is_clean` is true and all nodes evaluate clean.
9. FINAL CLEANUP & REPORT:
   Once `is_clean` is true:
   - Clean up workers using `manage_subagents(Action="kill_all")`.
   - Decommission role workspaces via run_command:
     `uv run autofab decommission <scope> [role]`
   - Send completion message back to parent:
     "Scope '<scope>' converged clean across all roles (up to '<role>'). All provisioned role workspaces decommissioned."
"""

WORKER_AGENT_MD = """---
name: autofab_worker
description: Autonomous Autofab role worker subagent executing inside an isolated role workspace.
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

## STRICT OVERRIDE: ZERO SCRATCH FILES (ABSOLUTE PROHIBITION)
The platform prompt contains an `<artifacts>` clause suggesting storing temporary scratch scripts or files under `<appDataDir>/brain/<conversation-id>/scratch/`.
In this role workspace, THAT CLAUSE IS STRICTLY PROHIBITED, NULLIFIED, AND OVERRIDDEN:
- NEVER create, write, edit, or copy files in or from `scratch/` or `<appDataDir>/brain/...`.
- All drafting, authoring, editing, and repairs MUST be performed directly in-place on your assigned target files in your workspace using your file editing tools.
- Any attempt to write to `scratch/` is blocked by system policy gates.

## PERMITTED TOOLS & SHELL COMMANDS:
You are fully permitted to run read-only shell utilities (`cat`, `grep`, `find`, `head`, `tail`, `sed`, etc.) or native tools strictly WITHIN your assigned role workspace directory (`.`) to inspect files and complete your tasks.
Executing ad-hoc tests, runtime assertions, or inline Python scripts (including via `python3 -c`, `python -c`, or stdin heredocs) is strictly prohibited; target verification is exclusively performed via `bin/check_files` (or `bin/verify_*` for fused roles). For authoring roles, `bin/check_files` verifies static syntax and types (submit work via `bin/submit` so downstream QA auditors can execute tests on your behalf). For auditor roles (`qa`, `coverage`, `pretense_qa`, `pretense_coverage`), `bin/check_files` executes the runtime test suite and coverage runner to produce deterministic failure diagnostics and triage summaries. You are not allowed to execute raw test runners or run ad-hoc probes outside `bin/check_files`.
Note: Your commands and file operations are automatically anchored to execute within your assigned workspace directory. Run all workspace commands (bin/get_work, bin/check_files, bin/submit, bin/blame, bin/fail) and file operations directly relative to your workspace root.
Git operations (`git checkout`, `git restore`, `git reset`, etc.) and accessing files outside your workspace remain strictly prohibited.

## MANDATORY WORKFLOW BINARIES:
All Cleanroom target resolution must proceed through the prescribed workspace binaries in `bin/`:
- Standard Role Workspaces: `bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`
- Fused Role Workspaces: `bin/get_work` (call ONCE at session start), `bin/verify_*` (for each constituent role), `bin/fail`

## UNRESOLVABLE IMPASSE & FAILURE PROTOCOL:
If you determine that success is not possible (e.g. unreachable code under test, contradictory specification contracts, or dead ends that blame cannot resolve):
1. DO NOT attempt ad-hoc debugging, script execution, or reverse-engineering of autofab tools.
2. Execute: `bin/fail <target_file> "<reason>"`
3. Report failure immediately to the coordinator via `send_message`:
   `FAILED: <target_file> - <reason>`
4. Cease work immediately.

## TARGET VERIFICATION & BLAME RESOLUTION:
- For author roles: `bin/check_files` ONLY checks static syntax and types. It does NOT run tests. When an active node carries unacted feedback or blame from downstream roles (QA), passing `bin/check_files` does NOT mean the defect is resolved. You MUST inspect `low/*.pyi` and `tests/*_test.py`, modify code logic to satisfy contracts and pass tests, ensure `bin/check_files` passes, and submit with a change summary describing how the feedback was fixed.
- For auditor roles (QA, Coverage, Pretense QA, Pretense Coverage): Running `bin/check_files <target>` executes the runtime test suite and coverage analysis, producing structured failure diagnostics and triage summaries. Code files in the workspace are strictly read-only. When verification checks pass, submit the target; when verification checks fail, stage blame via `bin/blame <culprit_file> "<critique>"` and commit blame via `bin/submit <target>`.

## METADATA PROJECTION & INVIOLABILITY:
- NEVER manually edit `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools (`bin/submit`, `bin/blame`, `bin/fail`).
- Files in your role workspace are projected to intentionally omit `LAST_CLEANED`, `LAST_CHANGED`, and audit timestamps. Canonical lifecycle timestamps are maintained exclusively in the main repository and managed by `bin/submit` (or `autofab harvest-fused`).
- Never attempt to manually add `LAST_CLEANED` or `LAST_CHANGED` to local workspace files, and never treat missing lifecycle timestamps in local workspace files as a defect.
- If `bin/get_work` assigns a target, perform thorough semantic verification against contracts and test suites rather than assuming it is clean just because static syntax and type checks pass.

## STANDARD WORKFLOW:
1. Run `bin/get_work` to acquire pending ready nodes and review unacted feedback.
   - Note: If `bin/get_work` outputs a `[CRITICAL MODEL MISMATCH]` error (because `gemini-argon` or `gemini-carbon` was requested via `inherit` while Antigravity is running a different model), DO NOT proceed. Immediately send `FAILED: <scope> - <exact error message instructing the user to manually switch their model to "Gemini Argon" or "Gemini Carbon" before requesting the run again>` to the coordinator via `send_message` and stop.
2. Consult your workspace `AGENTS.md` and companion guide(s) in `guides/` (located directly under your workspace root: `guides/<basename>`; do not prefix with scope) to perform role duties.
3. For standard roles:
   - Perform role verification using `bin/check_files`.
   - Resolve nodes via `bin/submit <target_file> "<summary>"`, `bin/blame <culprit_file> "<explanation>"`, or `bin/fail <target_file> "<reason>"`.
   - Drain all ready nodes until `bin/get_work` confirms all units in scope are clean, then report `COMPLETED: All ready units in workspace drained clean.` via `send_message`.
4. For fused roles (`baseline` / `pretense_baseline`):
   - Call `bin/get_work` ONCE at session start.
   - Implement `lib/*.py` and author `tests/*_test.py` (or `pretense/*_pretense.py`) consulting `guides/`.
   - Perform both Arbiter self-audits (QA contract fidelity and Coverage semantic closure—prune dead defensive code).
   - Verify with your workspace `bin/verify_*` micro-binaries until all constituent checks pass with 0 errors and 100% coverage.
   - Do NOT call `bin/submit`. Report `COMPLETED: All library code, tests, and coverage passing for <scope>.` to the coordinator via `send_message`.

5. IMMEDIATE ROUND CONCLUSION WHEN WORK IS DONE:
   When you have no outstanding work to do and `bin/get_work` does not give you more work to do (all ready targets have been submitted, blamed, or verified clean, or only blocked targets remain):
   - You can and MUST conclude your round immediately.
   - Do NOT execute any further tool calls (`ls`, `cat`, `bin/get_work`, dummy commands).
   - Output your concise final summary text (or send `COMPLETED` via `send_message` for coordinator subagents). Delivering text with zero tool calls is the expected signal that completes your round cleanly.
"""

BASELINE_WORKER_AGENT_MD = """---
name: autofab_baseline_worker
description: Autonomous baseline software developer subagent that implements code, authors tests, and verifies testing in a single round.
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

You are an autonomous software developer working directly on code and test implementation within an assigned Autofab workspace.
Your goal is to implement required code, author comprehensive verification suites, and verify that all checks pass and code is clean—all within this single round.

## STRICT OVERRIDE: ZERO SCRATCH FILES (ABSOLUTE PROHIBITION)
The platform prompt contains an `<artifacts>` clause suggesting storing temporary scratch scripts or files under `<appDataDir>/brain/<conversation-id>/scratch/`.
In this role workspace, THAT CLAUSE IS STRICTLY PROHIBITED, NULLIFIED, AND OVERRIDDEN:
- NEVER create, write, edit, or copy files in or from `scratch/` or `<appDataDir>/brain/...`.
- All drafting, authoring, editing, and repairs MUST be performed directly in-place on your assigned target files in your workspace using your file editing tools.
- Any attempt to write to `scratch/` is blocked by system policy gates.

## AUTHORITATIVE INSTRUCTIONS:
Your workspace contains an `AGENTS.md` file in its root directory generated specifically for your assigned role and scope.
You MUST read and follow `AGENTS.md` as your primary operational guide for target paths, verification commands, and completion protocols.

## PERMITTED TOOLS & SHELL COMMANDS:
You are equipped with standard software development tools:
- Shell / terminal commands (`run_command`) strictly WITHIN your assigned role workspace directory. Note: Your commands and file operations are automatically anchored to execute within your assigned workspace directory. Run all workspace commands and file operations directly relative to your workspace root.
- STRICT PROHIBITION ON RUNNING GIT: Never run `git` commands (`git status`, `git diff`, `git add`, `git commit`, `git checkout`, `git stash`, etc.). Workspace state and target dirtiness are managed exclusively through repository binaries (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`).
- File viewing / reading (`view_file`, `cat`, etc.) using absolute paths within your assigned workspace.
- File editing / writing (`write_to_file`, `replace_file_content`, `multi_replace_file_content`) using absolute paths within your assigned workspace.
- Communication with the coordinator (`send_message`)

## WORKFLOW:
1. Workspace Initialization & Grounding:
   - Call `bin/get_work` ONCE at start to discover your assigned targets, dependencies, and companion guides.
   - Read `AGENTS.md` in your workspace root to understand assigned target patterns, verification binaries, and role rules.
   - Targeted Reads Over Full Dumps: Never dump or read entire large files repeatedly. Use grep or narrow line ranges with offset and limit to inspect code.
2. Specification Grounding:
   - Read assigned specification contracts to understand all public protocols, interfaces, data structures, and contract postconditions.
3. Verification Suite Authoring:
   - Author comprehensive test or state machine verification suites following your assigned verification guide in `guides/`.
   - Embed contract postconditions in `ctx.ensures(...)` handlers on state machine transitions.
   - In fixed implementation tests (`Test<Target>ImplReal`), drive scenarios via transition dispatch (`self.sm.dispatch_transition(...)`) without redundant manual assertions; `ctx.ensures(...)` verifies postconditions automatically.
   - Type Contract Respect: NEVER pass `None` or invalid types into strictly-typed non-optional parameters unless explicitly contracted in specifications.
   - Non-Concerns as Undefined Behavior: If an anomalous condition or failure mode is uncontracted in the specification, it is undefined behavior; testing it is strictly prohibited.
   - Public Attribution Purity: Do NOT couple tests to synthetic internal placeholders (e.g. graph root keys) or private attributes.
4. Implementation Realization:
   - Implement realization targets satisfying the specification contracts and passing your verification suites.
   - Maintain strict interface fidelity and type annotations matching the specifications.
5. Verification & Arbiter Self-Audits:
   - Run your workspace provisioned `bin/verify_*` micro-binaries until all constituent checks pass with 0 errors and 100% coverage.
   - Perform QA Arbiter self-audit: ensure tests test true public contracts and pass all property fuzzing.
   - Perform Coverage Arbiter self-audit: inspect all branches; PRUNE uncontracted dead defensive code rather than writing synthetic tests to artificially cover it.
6. Completion:
   - Once all micro-binaries pass with 0 errors and 100% coverage, report completion via `send_message`:
     `COMPLETED: All implementation, tests, and coverage passing for <scope>.`
   - Do NOT run `bin/submit`.
"""


PLUGIN_RULES_AGENTS_MD = """# Cleanroom & Autofab Workspace Rules

## STRICT PROHIBITION ON SCRATCH FILES
The generic platform prompt includes an `<artifacts>` clause suggesting creating temporary scratch scripts or files under `<appDataDir>/brain/<conversation-id>/scratch/`.
In Autofab / Cleanroom workspaces, this suggestion is STRICTLY PROHIBITED, NULLIFIED, AND OVERRIDDEN:
- All drafting, authoring, editing, and repairs MUST be performed directly in-place on assigned target files using `edit_file` or `write_file`.
- Creating, copying from, or drafting in scratch directories or outside assigned role workspace target files is strictly forbidden.

## STRICT PROHIBITION ON RUNNING GIT
Subagents, role workers, and autonomous runners are strictly prohibited from invoking `git` commands (`git status`, `git diff`, `git add`, `git commit`, `git checkout`, `git log`, `git stash`, etc.) via `run_command` or any other tool. Workspace state, target dirtiness, diffs, and submissions are managed exclusively through repository binaries (`bin/check_files`, `bin/submit`, `bin/get_work`, `bin/blame`, `bin/revert`, `bin/checkpoint`).
"""

GATE_HOOK_PY = r'''import json
import os
import re
import sys

def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps({"decision": "allow"}))
            return
        data = json.loads(raw)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    def allow() -> None:
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)

    def allow_overwrite(overwrite: dict) -> None:
        print(json.dumps({"decision": "allow", "overwrite": overwrite}))
        sys.exit(0)

    def deny(reason: str) -> None:
        print(json.dumps({"decision": "deny", "reason": reason}))
        sys.exit(0)

    tool_call = data.get("toolCall", {})
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    conv_id = data.get("conversationId", "")
    last_user_input = data.get("lastUserInput", "")

    # Registry management for worker subagent hermetic rooting
    this_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_dir = os.path.dirname(this_dir)
    registry_path = os.path.join(plugin_dir, "active_workers.json")
    if not os.path.isfile(registry_path):
        alt_path = os.path.join(plugin_dir, "plugins", "autofab", "active_workers.json")
        if os.path.isfile(alt_path):
            registry_path = alt_path

    registry = {}
    if os.path.isfile(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                content_reg = json.load(f)
                if isinstance(content_reg, dict):
                    registry = content_reg
        except Exception:
            registry = {}

    # Stale pruning
    pruned = False
    for cid in list(registry.keys()):
        entry = registry[cid]
        if not isinstance(entry, dict) or not os.path.isdir(entry.get("workspace_dir", "")):
            del registry[cid]
            pruned = True

    ws_pattern = re.compile(
        r"(?:assigned\s+(?:role\s+)?workspace(?:\s+directory)?\s+(?:is\s*[:=]?\s*|:\s*)|workspace:\s*)[\x27\x22](?P<ws>[^\x27\x22]+)[\x27\x22]",
        re.IGNORECASE,
    )
    role_pattern = re.compile(
        r"autonomous\s+Autofab\s+(?:fused\s+)?[\x27\x22]?(?P<role>[a-zA-Z0-9_-]+)[\x27\x22]?\s+worker",
        re.IGNORECASE,
    )

    ws_dir = None
    if conv_id and conv_id in registry:
        ws_dir = registry[conv_id].get("workspace_dir")

    if not ws_dir and conv_id:
        candidates = []
        tpath = data.get("transcriptPath")
        if tpath and os.path.isfile(tpath):
            candidates.append(tpath)
        brain_tpath = os.path.expanduser(f"~/.gemini/antigravity/brain/{conv_id}/.system_generated/logs/transcript.jsonl")
        if brain_tpath not in candidates and os.path.isfile(brain_tpath):
            candidates.append(brain_tpath)

        for c_file in candidates:
            try:
                with open(c_file, "r", encoding="utf-8") as fp:
                    for _ in range(5):
                        line_str = fp.readline()
                        if not line_str:
                            break
                        rec = json.loads(line_str)
                        text = rec.get("content", "")
                        m = ws_pattern.search(text)
                        if m:
                            cand = m.group("ws").strip()
                            if os.path.isdir(cand):
                                ws_dir = cand
                                rm = role_pattern.search(text)
                                role = rm.group("role") if rm else "worker"
                                registry[conv_id] = {
                                    "role": role,
                                    "workspace_dir": ws_dir,
                                }
                                pruned = True
                                break
                    if ws_dir:
                        break
            except Exception:
                pass

    if not ws_dir and last_user_input:
        m = ws_pattern.search(last_user_input)
        if m:
            cand = m.group("ws").strip()
            if os.path.isdir(cand):
                ws_dir = cand
                if conv_id:
                    rm = role_pattern.search(last_user_input)
                    role = rm.group("role") if rm else "worker"
                    registry[conv_id] = {
                        "role": role,
                        "workspace_dir": ws_dir,
                    }
                    pruned = True

    if pruned:
        try:
            tmp_path = f"{registry_path}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
                f.write(chr(10))
            os.replace(tmp_path, registry_path)
        except Exception:
            pass

    # If this is NOT an active worker subagent assigned to a role workspace, ALLOW IMMEDIATELY!
    # Non-worker conversations (coordinator, parent chats, other workspaces) must NEVER be restricted.
    if not ws_dir:
        allow()

    canonical_ws = os.path.realpath(os.path.abspath(ws_dir))

    # All restrictions below apply EXCLUSIVELY to registered Autofab role workers inside their assigned role workspace

    # 1. Scratch path prohibition for role workers
    if name in ("write_file", "edit_file", "view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        path = (args.get("Path") or args.get("path") or "").strip().strip("'").strip('"')
        if "/scratch/" in path or path.endswith("/scratch"):
            deny(
                "STRICT POLICY VIOLATION: Authoring files in scratch/ directories is strictly prohibited. "
                "Author and edit assigned target files directly in place within your workspace."
            )

    # 2. Command restrictions for role workers
    if name == "run_command":
        cmd = (args.get("CommandLine") or "").strip().strip("'").strip('"')

        # Block referencing canonical host repository outside workspace
        if "/projects/cleanroom" in cmd or "/cleanroom/" in cmd:
            deny(
                f"STRICT BOUNDARY VIOLATION: Referencing host repository paths outside your role workspace is strictly prohibited. "
                f"You are confined exclusively to your assigned role workspace: '{ws_dir}'."
            )

        # Direct git commands and inspecting .git/ directories
        if re.search(r"(?:^|[\s;&|`$()])git(?:\.exe)?(?:\s|$)", cmd) or re.search(
            r"(?:^|[\s;&|`$()])(?:\.git/|cat\s+.*\.git|tail\s+.*\.git|head\s+.*\.git|ls\s+.*\.git)",
            cmd,
        ):
            deny(
                "STRICT POLICY VIOLATION: Direct git commands and inspecting .git/ directories are strictly prohibited in Autofab workspaces. "
                "Workspace state and submissions are managed exclusively through repository binaries "
                "(bin/check_files, bin/submit, bin/blame). To revert broken edits, use bin/revert."
            )

        # Unzipping runner binaries or inspecting internal tool archives
        if re.search(r"(?:^|[\s;&|`$()])unzip(?:\s|$)", cmd):
            deny(
                "STRICT POLICY VIOLATION: Unzipping runner binaries or inspecting internal tool archives is strictly prohibited. "
                "Consult your companion guide in guides/ for all required structures and conventions."
            )

        # Prohibit ad-hoc python execution, inline scripts, test runners, or typecheckers by worker subagents
        probe_pattern = re.compile(
            r"(?:^|[;&|`()]\s*|\$\(\s*)"
            r"(?:(?:sudo|env|time|nohup)\s+)*"
            r"(?:python[0-9.]*|pytest|pyright|mypy|ruff|ipython|uv\s+run)(?:\.exe)?(?:\s|$)",
            re.IGNORECASE,
        )
        if probe_pattern.search(cmd):
            deny(
                "STRICT POLICY VIOLATION: Role workers are strictly prohibited from executing ad-hoc Python probes, "
                "inline scripts (python -c), test runners (pytest), or typecheckers directly. "
                "Target verification relies exclusively on 'bin/check_files <target>'."
            )

        # Prohibit internal cd navigation
        cd_re = re.compile(
            r"(?:^|[;&|`()]\s*|\$\(\s*)\s*cd(?:\s+([^;&|`$()]+|[\x27\x22][^\x27\x22]+[\x27\x22]))?"
        )
        for m in cd_re.finditer(cmd):
            target = m.group(1)
            if not target:
                deny(
                    f"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('{ws_dir}'). "
                    f"Changing directories (cd) into subdirectories (e.g. guides/) or external paths is strictly prohibited. "
                    f"Run all tools (bin/get_work, bin/check_files, bin/submit) directly from the workspace root."
                )
            clean_target = target.strip().strip("'").strip('"')
            if clean_target in (".", "./"):
                continue
            try:
                target_canonical = os.path.realpath(os.path.abspath(clean_target))
            except Exception:
                target_canonical = ""
            if target_canonical == canonical_ws or clean_target == ws_dir:
                continue
            deny(
                f"STRICT BOUNDARY VIOLATION: Subagents are permanently rooted in their workspace directory ('{ws_dir}'). "
                f"Changing directories (cd) into subdirectories (e.g. guides/) or external paths is strictly prohibited. "
                f"Run all tools (bin/get_work, bin/check_files, bin/submit) directly from the workspace root."
            )

        # Transparent command auto-rooting via overwrite
        pattern_escaped = re.escape(ws_dir)
        canonical_escaped = re.escape(canonical_ws)
        prefix_re = re.compile(
            rf"^\s*cd\s+[\x27\x22]?(?:{pattern_escaped}|{canonical_escaped})[\x27\x22]?\s*&&\s*",
            re.IGNORECASE,
        )
        if not prefix_re.search(cmd):
            new_cmd = f"cd {ws_dir} && ({cmd})"
            allow_overwrite({"CommandLine": new_cmd})
        elif (args.get("CommandLine") or "") != cmd:
            allow_overwrite({"CommandLine": cmd})
        else:
            allow()

    # 3. Path confinement for role workers
    elif name in ("read_file", "write_file", "edit_file", "view_file", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        raw_path = args.get("Path") or args.get("path") or ""
        path = raw_path.strip().strip("'").strip('"')
        path_key = "Path" if "Path" in args else "path"

        # Also normalize Overwrite boolean if passed as a string
        overwrite_patch = {}
        for ok in ("Overwrite", "overwrite"):
            if ok in args and isinstance(args[ok], str):
                overwrite_patch[ok] = args[ok].lower() == "true"

        if not os.path.isabs(path):
            resolved = os.path.normpath(os.path.join(ws_dir, path))
            canonical_resolved = os.path.realpath(resolved)
            if canonical_resolved == canonical_ws or canonical_resolved.startswith(canonical_ws + os.sep):
                patch = {path_key: resolved, **overwrite_patch}
                allow_overwrite(patch)
            else:
                deny(f"STRICT BOUNDARY VIOLATION: Path traversal '{path}' escapes assigned workspace.")
        else:
            canonical_path = os.path.realpath(os.path.normpath(path))
            if canonical_path == canonical_ws or canonical_path.startswith(canonical_ws + os.sep):
                if raw_path != path or overwrite_patch:
                    patch = {path_key: path, **overwrite_patch}
                    allow_overwrite(patch)
                else:
                    allow()
            else:
                deny(
                    f"STRICT BOUNDARY VIOLATION: Access to path '{path}' is strictly prohibited. "
                    f"You are confined exclusively to your assigned role workspace: '{ws_dir}'."
                )

    allow()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)
'''


def ensure_antigravity_plugin_installed(target_dir: str | None = None) -> str:
    """Installs or refreshes Cleanroom agents and safety gate hooks in workspace Antigravity directory."""
    app_info = _get_app_info()
    app_name = app_info.APP_NAME if app_info else "cleanroom"

    if target_dir:
        plugin_dir = target_dir
        ws_root = os.path.dirname(os.path.dirname(os.path.dirname(plugin_dir)))
    elif os.environ.get("ANTIGRAVITY_CONFIG_DIR"):
        config_root = os.environ["ANTIGRAVITY_CONFIG_DIR"]
        plugin_dir = os.path.join(config_root, "plugins", app_name)
        ws_root = find_workspace_root()
    else:
        ws_root = find_workspace_root()
        plugin_dir = os.path.join(ws_root, ".agents", "plugins", app_name)

    agents_dir = os.path.join(plugin_dir, "agents")
    coord_dir = os.path.join(agents_dir, f"{app_name}_coordinator")
    worker_dir = os.path.join(agents_dir, f"{app_name}_worker")
    baseline_worker_dir = os.path.join(agents_dir, f"{app_name}_baseline_worker")
    rules_dir = os.path.join(plugin_dir, "rules")
    hooks_dir = os.path.join(plugin_dir, "hooks")

    # If legacy skills directory exists, remove it
    legacy_skills_dir = os.path.join(plugin_dir, "skills")
    if os.path.isdir(legacy_skills_dir):
        shutil.rmtree(legacy_skills_dir, ignore_errors=True)

    os.makedirs(coord_dir, exist_ok=True)
    os.makedirs(worker_dir, exist_ok=True)
    os.makedirs(baseline_worker_dir, exist_ok=True)
    os.makedirs(rules_dir, exist_ok=True)
    os.makedirs(hooks_dir, exist_ok=True)

    plugin_json = {
        "name": app_name,
        "description": f"{app_name} multi-agent coordinator and role worker subagents",
    }
    with open(os.path.join(plugin_dir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(plugin_json, f, indent=2)
        f.write("\n")

    with open(os.path.join(coord_dir, "agent.md"), "w", encoding="utf-8") as f:
        f.write(COORDINATOR_AGENT_MD.strip() + "\n")

    with open(os.path.join(worker_dir, "agent.md"), "w", encoding="utf-8") as f:
        f.write(WORKER_AGENT_MD.strip() + "\n")

    with open(
        os.path.join(baseline_worker_dir, "agent.md"), "w", encoding="utf-8"
    ) as f:
        f.write(BASELINE_WORKER_AGENT_MD.strip() + "\n")

    with open(os.path.join(rules_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
        f.write(PLUGIN_RULES_AGENTS_MD.strip() + "\n")

    hooks_json = {
        f"{app_name}-safety-gate": {
            "PreToolUse": [
                {
                    "matcher": "run_command|read_file|write_file|edit_file|view_file|write_to_file|replace_file_content|multi_replace_file_content",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 hooks/gate.py || echo '{\"decision\": \"allow\"}'",
                            "timeout": 10,
                        }
                    ],
                }
            ]
        }
    }
    with open(os.path.join(plugin_dir, "hooks.json"), "w", encoding="utf-8") as f:
        json.dump(hooks_json, f, indent=2)
        f.write("\n")

    with open(os.path.join(hooks_dir, "gate.py"), "w", encoding="utf-8") as f:
        f.write(GATE_HOOK_PY.strip() + "\n")

    # If installed under workspace .agents/, also configure root .agents/ links/manifests for maximum compatibility
    dot_agents = os.path.join(ws_root, ".agents")
    if os.path.isdir(dot_agents):
        # 1. plugins.json manifest
        plugins_json = {
            "entries": [
                {"path": "plugins"}
            ]
        }
        with open(os.path.join(dot_agents, "plugins.json"), "w", encoding="utf-8") as f:
            json.dump(plugins_json, f, indent=2)
            f.write("\n")

        # 2. Standalone agents directory in .agents/agents
        standalone_agents_dir = os.path.join(dot_agents, "agents")
        for sub_name, md_content in [
            (f"{app_name}_coordinator", COORDINATOR_AGENT_MD),
            (f"{app_name}_worker", WORKER_AGENT_MD),
            (f"{app_name}_baseline_worker", BASELINE_WORKER_AGENT_MD),
        ]:
            sub_d = os.path.join(standalone_agents_dir, sub_name)
            os.makedirs(sub_d, exist_ok=True)
            with open(os.path.join(sub_d, "agent.md"), "w", encoding="utf-8") as f:
                f.write(md_content.strip() + "\n")

        # 3. Direct .agents/hooks.json pointing to plugin gate.py
        ws_hooks_json = {
            f"{app_name}-safety-gate": {
                "PreToolUse": [
                    {
                        "matcher": "run_command|read_file|write_file|edit_file|view_file|write_to_file|replace_file_content|multi_replace_file_content",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python3 plugins/{app_name}/hooks/gate.py || echo '{{\"decision\": \"allow\"}}'",
                                "timeout": 10,
                            }
                        ],
                    }
                ]
            }
        }
        with open(os.path.join(dot_agents, "hooks.json"), "w", encoding="utf-8") as f:
            json.dump(ws_hooks_json, f, indent=2)
            f.write("\n")

        # Also write root .agents/hooks/gate.py for direct .agents/hooks execution
        root_hooks_dir = os.path.join(dot_agents, "hooks")
        os.makedirs(root_hooks_dir, exist_ok=True)
        with open(os.path.join(root_hooks_dir, "gate.py"), "w", encoding="utf-8") as f:
            f.write(GATE_HOOK_PY.strip() + "\n")

    return plugin_dir


def dispatch_antigravity_coordination(
    target_display: str,
    mode: str = "message",
    model: str = "flash",
    baseline: bool = False,
) -> bool:
    """Dispatches coordination to the Antigravity Desktop App via agentapi.

    If mode == "message", sends a high-priority reactive message to the active
    conversation (via ANTIGRAVITY_CONVERSATION_ID).
    If mode == "new-conversation", spawns a dedicated conversation tab in the desktop app.

    Returns True if successfully dispatched via agentapi, False otherwise.
    """
    if mode == "none":
        return False

    try:
        ensure_antigravity_plugin_installed()
    except Exception:
        pass

    exe = os.environ.get("ANTIGRAVITY_AGENTAPI_EXE")
    conv_id = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")

    # Resolve agentapi executable
    agentapi_cmd: list[str] = []
    if exe:
        agentapi_cmd = [exe, "agentapi"]
    else:
        found = shutil.which("agentapi")
        if not found:
            for cand in [
                Path.home() / ".gemini" / "antigravity" / "bin" / "agentapi",
                Path.home() / ".gemini" / "antigravity-ide" / "bin" / "agentapi",
            ]:
                if cand.is_file() and os.access(cand, os.X_OK):
                    found = str(cand)
                    break
        if found:
            agentapi_cmd = [found]
        else:
            for cand_server in [
                Path(
                    "/Applications/Antigravity.app/Contents/Resources/bin/language_server"
                ),
                Path(
                    "/Applications/Antigravity IDE.app/Contents/Resources/bin/language_server"
                ),
            ]:
                if cand_server.is_file() and os.access(cand_server, os.X_OK):
                    agentapi_cmd = [str(cand_server), "agentapi"]
                    break

    if not agentapi_cmd:
        return False

    ag_coord_model = "inherit"
    if model:
        m_low = model.lower()
        if "lite" in m_low:
            ag_coord_model = "flash_lite"
        elif "flash" in m_low:
            ag_coord_model = "flash"
        elif "pro" in m_low:
            ag_coord_model = "pro"

    prompt = f"Clean all dirty nodes in {target_display} using autofab_coordinator (Model: {ag_coord_model})."

    if mode == "message":
        if not conv_id:
            return False
        cmd = list(agentapi_cmd) + [
            "send-message",
            f"--title=Autofab Coordination [{target_display}]",
            conv_id,
            prompt,
        ]
    elif mode == "new-conversation":
        tier = "flash"
        if "pro" in model.lower():
            tier = "pro"
        elif "lite" in model.lower():
            tier = "flash_lite"
        cmd = list(agentapi_cmd) + [
            "new-conversation",
            f"--model={tier}",
            f"--title=Autofab Coordinator: {target_display}",
            "--",
            prompt,
        ]
    else:
        return False

    def _execute_agentapi() -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15)

    try:
        res = _execute_agentapi()
        if (
            res.returncode != 0
            and mode == "new-conversation"
            and sys.platform == "darwin"
        ):
            # If agentapi failed and we are on macOS, Antigravity Desktop might not be running.
            # Attempt to launch Antigravity Desktop and retry once.
            app_path = None
            for cand_app in [
                Path("/Applications/Antigravity.app"),
                Path("/Applications/Antigravity IDE.app"),
            ]:
                if cand_app.exists():
                    app_path = cand_app
                    break
            if app_path:
                print(
                    f"[Antigravity Desktop IPC] Antigravity Desktop not responding. Launching {app_path.name}..."
                )
                subprocess.run(["open", "-a", str(app_path)], check=False)
                time.sleep(3)
                res = _execute_agentapi()

        if res.returncode == 0:
            action_desc = (
                f"Reactive wakeup message sent to conversation {conv_id}"
                if mode == "message"
                else "New coordinator conversation spawned"
            )
            print(f"[Antigravity Desktop IPC] {action_desc}.")
            return True
        else:
            err = res.stderr.strip() or res.stdout.strip()
            print(
                f"[Antigravity Desktop IPC] Warning: agentapi failed (code {res.returncode}): {err}",
                file=sys.stderr,
            )
            return False
    except Exception as e:
        print(
            f"[Antigravity Desktop IPC] Warning: agentapi invocation failed: {e}",
            file=sys.stderr,
        )
        return False


def ensure_dsh_skill_installed() -> str | None:
    """Installs or refreshes Cleanroom coordinator skill in DSH harness skills directory if present."""
    app_info = _get_app_info()
    app_name = app_info.APP_NAME if app_info else "cleanroom"
    dsh_home = os.environ.get("DSH_HOME")
    candidates = []
    if dsh_home and dsh_home.strip():
        candidates.append(os.path.join(dsh_home.strip(), "harness", "skills"))
        candidates.append(os.path.join(dsh_home.strip(), "skills"))

    home = os.path.expanduser("~")
    candidates.append(os.path.join(home, ".dsh", "skills"))
    candidates.append(os.path.join(home, ".dsh", "harness", "skills"))

    target_skills_dir = None
    for cand in candidates:
        if os.path.isdir(cand) or os.path.isdir(os.path.dirname(cand)):
            target_skills_dir = cand
            break

    if not target_skills_dir:
        return None

    skill_dir = os.path.join(target_skills_dir, app_name)
    os.makedirs(skill_dir, exist_ok=True)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    content = f"""---
name: {app_name}
description: Autonomous {app_name} role workspace coordinator, work queue inspector, and subagent fleet manager.
whenToUse: Use when the user types /{app_name}, asks to orchestrate, or asks to run {app_name} roles for a scope.
---

# {app_name.capitalize()} Autonomous Coordinator

When the user invokes `/{app_name} [scope] [target_role]` (e.g., `/{app_name} staging qa` or `orchestrate staging`):
**You are the Master Coordinator.** Immediately and autonomously execute the {app_name.capitalize()} DAG using DSH native subagents:

## Autonomous Execution Loop

1. **Inspect Ready Roles in the DAG**:
   Run:
   ```bash
   uv run {app_name} work-queue <dir_scope> [target_role] --json
   ```
   Check which roles currently have ready targets. If all roles in scope are clean, report convergence to the user and stop.

2. **Commission Workspace**:
   For the first ready role, commission its workspace:
   ```bash
   uv run {app_name} commission <role> <dir_scope>
   ```
   This prepares the role workspace at `../autofab_role_workspaces/<role>_<scope>/` with its internal tools (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`).

3. **Dispatch Role Subagent**:
   Call the DSH native `subagent` tool:
   - `description`: `[<ROLE>] <scope> worker`
   - `prompt`:
     ```text
     You are the <role> worker for scope <scope>.
     Your assigned workspace is: ../autofab_role_workspaces/<role>_<scope>
     1. Change directory to your workspace.
     2. Run `bin/get_work` to view the pending tasks and contract guidelines.
     3. Make the necessary code/spec edits in your workspace.
     4. Run `bin/check_files` to ensure all checks pass.
     5. Run `bin/submit` to submit your work, or `bin/blame` if upstream defects are discovered.
     ```

4. **Iterate Until Clean Convergence**:
   When the child subagent finishes, re-run `uv run {app_name} work-queue <dir_scope> [target_role] --json`.
   Repeat steps 2–3 for subsequent ready roles until all roles in scope are clean.
   Once clean, report: `{app_name.capitalize()} orchestration for <scope> converged successfully!`

---

## Alternative Options

- If the user explicitly asks to run via the automated CLI script instead of subagents, run:
  ```bash
  uv run {app_name} orchestrate <dir_scope> [target_role]
  ```
- To run tests: `bin/test`
"""
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    return skill_file


_FOLDER_TO_ROLE_CACHE: dict[str, str] = {}


def _get_folder_to_role_map(ws_root: str | None = None) -> dict[str, str]:
    global _FOLDER_TO_ROLE_CACHE
    if _FOLDER_TO_ROLE_CACHE:
        return _FOLDER_TO_ROLE_CACHE
    mapping: dict[str, str] = {}
    root = ws_root or find_workspace_root()
    cand_toml_paths: list[str] = []
    app_inf = _get_app_info()
    role_files = (
        app_inf.get_roles_filenames()
        if app_inf
        else ("autofab_roles.toml", "cleanroom_roles.toml")
    )
    for rname in role_files:
        direct = os.path.join(root, rname)
        if os.path.isfile(direct):
            cand_toml_paths.append(direct)
        try:
            for sub in os.listdir(root):
                sub_cand = os.path.join(root, sub, rname)
                if os.path.isfile(sub_cand):
                    cand_toml_paths.append(sub_cand)
        except OSError:
            pass
    for toml_path in cand_toml_paths:
        try:
            import tomllib

            with open(toml_path, "rb") as tf:
                tdata = tomllib.load(tf)
            for rname, rdata in tdata.get("roles", {}).items():
                mapping[rname] = rname
                src_pattern = rdata.get("src_pattern", "")
                pats = rdata.get("src_patterns") or (
                    [src_pattern] if src_pattern else []
                )
                for pat in pats:
                    if "/" in pat:
                        parts = pat.split("/")
                        folder = parts[-2]
                        if "{" not in folder and "}" not in folder:
                            mapping[folder] = rname
        except Exception:
            pass
    _FOLDER_TO_ROLE_CACHE = mapping
    return mapping


def parse_cleanroom_target(target_str: str) -> tuple[str, str | None, bool]:
    """Uniformly parses any target representation into (scope, role, is_unit_target).

    Accepts:
      - Canonical DAG label: //staging/parts/agent:config#lib or //staging/parts/agent:config
      - File path: staging/parts/agent/lib/config.py or ...#lib
      - Scope + role: staging#qa
      - Part + role: staging/parts/agent#qa
      - Scope: staging
    """
    raw = target_str.strip()
    role: str | None = None
    if "#" in raw:
        raw, role_part = raw.split("#", 1)
        role = role_part.strip().lower() or None

    if raw.startswith("@@//"):
        raw = raw[2:]
    elif raw.startswith("@//"):
        raw = raw[1:]

    is_unit = False

    # 1. Canonical DAG label e.g. //staging/parts/agent:config
    if raw.startswith("//"):
        norm = raw.lstrip("/")
        if ":" in norm:
            pkg_part, _ = norm.split(":", 1)
            is_unit = True
        else:
            pkg_part = norm
        segs = pkg_part.split("/")
        if "parts" in segs:
            p_idx = segs.index("parts")
            scope = "/".join(segs[:p_idx])
        else:
            scope = pkg_part
        if not is_unit and len(segs) >= 2 and "." in segs[-1]:
            is_unit = True
            if not role and len(segs) >= 3:
                folder = segs[-2]
                folder_map = _get_folder_to_role_map()
                role = folder_map.get(folder, role)
        return scope, role, is_unit

    # 2. Filesystem path containing /parts/
    norm_path = raw.replace("\\", "/").strip("/")
    segs = norm_path.split("/")
    if "parts" in segs:
        p_idx = segs.index("parts")
        scope = "/".join(segs[:p_idx]) if p_idx > 0 else segs[0]
        if len(segs) > p_idx + 2 and "." in segs[-1]:
            is_unit = True
            if not role:
                folder = segs[-2]
                folder_map = _get_folder_to_role_map()
                role = folder_map.get(folder, role)
        return scope, role, is_unit

    # 3. Simple scope or scope#role
    scope = norm_path if norm_path else raw
    return scope, role, False


def resolve_default_model(
    repo_root: str | None = None, harness: str | None = None
) -> str | None:
    """Resolves default model profile name from model_configs.toml if present.
    Returns the value of the top-level 'default' key.
    """
    root = repo_root or find_workspace_root()
    import tomllib

    app_info = _get_app_info()
    candidates = [
        os.path.join(root, "model_configs.toml"),
        os.path.join(os.path.dirname(root), "model_configs.toml"),
    ]
    if app_info:
        candidates.extend(
            [
                os.path.join(root, app_info.DEFAULT_CONFIG_FILE),
                app_info.get_user_model_config_file(),
                app_info.get_template_model_config_file(),
            ]
        )
    else:
        candidates.extend(
            [
                os.path.join(root, "autofab.toml"),
                os.path.expanduser("~/.config/autofab/model_configs.toml"),
            ]
        )
    for cand in candidates:
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    data = tomllib.load(f)
                    val = data.get("default")
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            except Exception:
                pass
    return None


def resolve_model_harness(
    model_name: str | None = None, repo_root: str | None = None
) -> str:
    """Resolves runtime harness name for a given model (or default model) from model_configs.toml.
    The harness is derived directly from the model profile entry in [models.<name>].
    Defaults to 'antigravity' for gemini models and 'dsh' for other models.
    """
    root = repo_root or find_workspace_root()
    import tomllib

    app_info = _get_app_info()

    effective_model = model_name
    if not effective_model or effective_model == "default":
        effective_model = resolve_default_model(root)

    candidates = [
        os.path.join(root, "model_configs.toml"),
        os.path.join(os.path.dirname(root), "model_configs.toml"),
    ]
    if app_info:
        candidates.extend(
            [
                os.path.join(root, app_info.DEFAULT_CONFIG_FILE),
                app_info.get_user_model_config_file(),
                app_info.get_template_model_config_file(),
            ]
        )
    else:
        candidates.extend(
            [
                os.path.join(root, "autofab.toml"),
                os.path.expanduser("~/.config/autofab/model_configs.toml"),
            ]
        )

    def _find_model_entry(
        models_dict: dict[str, Any], target: str
    ) -> dict[str, Any] | None:
        if target in models_dict and isinstance(models_dict[target], dict):
            return models_dict[target]
        for k, v in models_dict.items():
            if isinstance(v, dict):
                if v.get("model") == target or v.get("model_name") == target:
                    return v
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, dict):
                        if f"{k}.{sub_k}" == target:
                            return sub_v
                        if (
                            sub_v.get("model") == target
                            or sub_v.get("model_name") == target
                        ):
                            return sub_v
        return None

    for cand in candidates:
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    data = tomllib.load(f)

                # Check model-specific harness
                if effective_model:
                    models = data.get("models")
                    m_entry = None
                    if isinstance(models, dict):
                        m_entry = _find_model_entry(models, effective_model)

                    if (
                        m_entry is None
                        and effective_model in data
                        and isinstance(data[effective_model], dict)
                    ):
                        m_entry = data[effective_model]

                    if m_entry is not None:
                        h = m_entry.get("harness") or m_entry.get("default_harness")
                        if isinstance(h, str) and h.strip():
                            h_clean = h.strip().lower()
                            if h_clean in ("deepseek", "deepseek-harness"):
                                return "dsh"
                            return h_clean
            except Exception:
                pass

    if effective_model:
        m_lower = effective_model.lower()
        if "gemini" in m_lower:
            return "antigravity"

    return "dsh"


def configure_user_environment() -> int:
    """Prepares the user environment (global ~/.config/autofab setup)."""
    app_info = _get_app_info()
    if not app_info:
        print("Error: app_info module not available.", file=sys.stderr)
        return 1
    cfg_dir = app_info.get_user_config_dir()
    os.makedirs(cfg_dir, exist_ok=True)

    model_cfg = app_info.get_user_model_config_file()
    if not os.path.isfile(model_cfg):
        with open(model_cfg, "w", encoding="utf-8") as f:
            f.write(app_info.DEFAULT_USER_MODEL_CONFIGS_TOML)
        print(f"[OK] Created user model configuration at: {model_cfg}")
    else:
        print(f"[INFO] User model configuration already exists at: {model_cfg}")

    creds_file = app_info.get_user_credentials_file()
    if not os.path.isfile(creds_file):
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(creds_file, flags, 0o600)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(app_info.DEFAULT_USER_CREDENTIALS_TOML)
        print(f"[OK] Created user credentials template (mode 0600) at: {creds_file}")
    else:
        print(f"[INFO] User credentials file already exists at: {creds_file}")

    p = ensure_antigravity_plugin_installed()
    print(f"[OK] Antigravity plugin and agent definitions refreshed at: {p}")

    dsh_p = ensure_dsh_skill_installed()
    if dsh_p:
        print(f"[OK] DeepSeek Harness skill refreshed at: {dsh_p}")

    print(
        f"\n[SUCCESS] Environment configured. You can edit credentials and model configurations in:\n  {cfg_dir}"
    )
    return 0


def install_workspace(repo_root: str | None = None) -> int:
    """Prepares a workspace/project to use Cleanroom."""
    app_info = _get_app_info()
    app_name = app_info.APP_NAME if app_info else "cleanroom"
    cfg_name = app_info.DEFAULT_CONFIG_FILE if app_info else "cleanroom.toml"
    root = repo_root or find_workspace_root()

    cfg_path = os.path.join(root, cfg_name)
    if not os.path.isfile(cfg_path):
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(f"# {cfg_name}\n# Project-level configuration for {app_name}\n\n")
        print(f"[OK] Initialized project configuration at: {cfg_path}")
    else:
        print(f"[INFO] Project configuration already exists at: {cfg_path}")

    gitignore_path = os.path.join(root, ".gitignore")
    app_inf = _get_app_info()
    patterns_to_ignore = [
        *(f"{c}/" for c in app_inf.get_role_workspaces_containers()),
        *(f".{c}/" for c in app_inf.get_role_workspaces_containers()),
        f".{app_name}_*",
        "staging/",
    ]
    existing = ""
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            existing = f.read()

    to_add = [p for p in patterns_to_ignore if p not in existing]
    if to_add:
        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(f"\n# {app_name} ephemeral files\n" + "\n".join(to_add) + "\n")
        print(f"[OK] Added ephemeral workspace patterns to {gitignore_path}")

    print(f"\n[SUCCESS] Workspace {root} prepared for {app_name}.")
    return 0


def resolve_scope_pipeline(
    scope: str,
    repo_root: str | None = None,
    explicit_pretense: bool = False,
    explicit_pipeline: str | None = None,
    target_role: str | None = None,
) -> str | None:
    if explicit_pipeline:
        return explicit_pipeline.strip().lower()
    if explicit_pretense:
        return "pretense"
    if target_role:
        tr = target_role.strip().lower()
        if "pretense" in tr:
            return "pretense"

    root = repo_root or find_workspace_root()

    # 1. Check active flight metadata
    app_inf = _get_app_info()
    state_dirs = [os.path.join(root, ".cleanroom"), os.path.join(root, ".autofab")]
    if app_inf and hasattr(app_inf, "resolve_state_dir"):
        state_dirs.insert(0, app_inf.resolve_state_dir(root))
    for state_dir in state_dirs:
        flight_file = os.path.join(state_dir, "active_flight.json")
        if os.path.isfile(flight_file):
            try:
                with open(flight_file, "r", encoding="utf-8") as f:
                    fdata = json.load(f)
                if fdata.get("flight_scope") == scope:
                    if fdata.get("pipeline"):
                        return str(fdata.get("pipeline")).strip().lower()
                    if fdata.get("method"):
                        return str(fdata.get("method")).strip().lower()
                    if fdata.get("pretense") or "pretense" in str(
                        fdata.get("flight_id", "")
                    ):
                        return "pretense"
            except Exception:
                pass

    # 2. Check configuration files in scope or parts
    import tomllib

    scope_clean = scope.lstrip("/").rstrip("/")
    curr = os.path.join(root, scope_clean)
    cfg_files = _get_app_info().get_config_filenames()
    for sub in ("parts", ""):
        cand_dir = os.path.join(curr, sub) if sub else curr
        for fname in cfg_files:
            cand = os.path.join(cand_dir, fname)
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        data = tomllib.load(f)
                    pipe = data.get("pipeline")
                    if pipe and isinstance(pipe, str):
                        return pipe.strip().lower()
                except Exception:
                    pass

    return "standard" if not target_role else None


def run_work_queue(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab work-queue",
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
    parser.add_argument(
        "--pipeline",
        "--method",
        dest="pipeline",
        choices=["standard", "pretense", "combined"],
        default=None,
        help="Target methodology / pipeline for work queue inspection.",
    )
    parser.add_argument(
        "--standard",
        dest="pipeline",
        action="store_const",
        const="standard",
        help="Inspect work queue for standard pipeline.",
    )
    parser.add_argument(
        "--pretense",
        dest="pipeline",
        action="store_const",
        const="pretense",
        help="Inspect work queue for Pretense pipeline.",
    )
    parser.add_argument(
        "--combined",
        dest="pipeline",
        action="store_const",
        const="combined",
        help="Inspect work queue for combined pipeline.",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Inspect work queue for fused baseline role.",
    )
    parser.add_argument(
        "--repo-root",
        dest="repo_root",
        default=None,
        help="Repository root directory.",
    )
    parsed = parser.parse_args(argv)
    target_input = parsed.scope_opt or parsed.scope or _get_dir_scope()
    if not target_input:
        print(
            "Error: Directory scope must be specified (e.g. uv run autofab work-queue staging or staging#qa).",
            file=sys.stderr,
        )
        return 1

    scope, parsed_role, is_unit = parse_cleanroom_target(target_input)
    target_role = (
        (parsed.role_opt or parsed.target_role or parsed_role or "").strip().lower()
    )
    if parsed.baseline and not target_role:
        if parsed.pipeline == "combined":
            target_role = "combined_baseline"
        elif parsed.pipeline == "pretense":
            target_role = "pretense_baseline"
        else:
            target_role = "baseline"

    root = parsed.repo_root or find_workspace_root()
    if parsed.repo_root:
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(parsed.repo_root)
    active_pipeline = resolve_scope_pipeline(
        scope=scope,
        repo_root=root,
        explicit_pretense=(parsed.pipeline == "pretense"),
        explicit_pipeline=parsed.pipeline,
        target_role=target_role or None,
    )
    from support.lib.lifecycle import enter_phase, get_singleton
    from autofab.parts.agent.lib import session as agent_session
    from autofab.parts.workspace.lib import role_registry, provision
    from autofab.parts.workspace_cli.lib import work

    with enter_phase(agent_session.agent_session):
        reg = get_singleton(role_registry.WorkspaceRegistry)
        work = get_singleton(work.WorkspaceWorkManager)
        prov = get_singleton(provision.WorkspaceProvisioner)

        declared_roles = reg.list_roles(root, dir_scope=scope)
        if not declared_roles:
            print(
                f"Error: No declared roles found for directory scope '{scope}'.",
                file=sys.stderr,
            )
            return 1

        if active_pipeline == "combined":
            declared_roles = [
                r
                for r in declared_roles
                if r.pipeline in (None, "", "standard", "pretense")
            ]
        elif active_pipeline:
            declared_roles = [
                r for r in declared_roles if r.pipeline in (None, "", active_pipeline)
            ]

        if target_role:
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                r_clean = r.role_name.split(":")[-1].strip().lower()
                if r_clean == target_role or r.role_name.lower() == target_role:
                    matching_idx = idx
                    break
            if matching_idx is None:
                try:
                    fused_r_def = reg.resolve_role_definition(
                        target_role, repo_root=root, dir_scope=scope
                    )
                    if fused_r_def and fused_r_def.fused_roles:
                        fused_names = {
                            f.split(":")[-1].strip().lower()
                            for f in fused_r_def.fused_roles
                        }
                        upstream_roles = []
                        for r in declared_roles:
                            r_c = r.role_name.split(":")[-1].strip().lower()
                            if r_c in fused_names:
                                break
                            upstream_roles.append(r)
                        declared_roles = upstream_roles + [fused_r_def]
                    else:
                        valid_names = ", ".join(r.role_name for r in declared_roles)
                        print(
                            f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}",
                            file=sys.stderr,
                        )
                        return 1
                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    valid_names = ", ".join(r.role_name for r in declared_roles)
                    print(
                        f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}",
                        file=sys.stderr,
                    )
                    return 1
            else:
                declared_roles = list(declared_roles[: matching_idx + 1])

        # Auto-commission any missing role workspaces up to target_role
        app_inf = _get_app_info()
        default_model = resolve_default_model(root)
        flight_file = os.path.join(root, ".cleanroom", "active_flight.json")
        if os.path.isfile(flight_file):
            try:
                with open(flight_file, "r", encoding="utf-8") as f:
                    fdata = json.load(f)
                if fdata.get("flight_scope") == scope and fdata.get("model"):
                    default_model = str(fdata["model"])
            except Exception:
                pass
        workspace_dirs: dict[str, str] = {}
        role_models: dict[str, str] = {}
        antigravity_models: dict[str, str] = {}
        for r in declared_roles:
            ws_dir = reg.compute_workspace_dir(
                r.role_name, dir_scope=scope, repo_root=root
            )
            workspace_dirs[r.role_name] = ws_dir
            if not os.path.isdir(ws_dir):
                try:
                    prov.commission(
                        r.role_name,
                        dir_scope=scope,
                        repo_root=root,
                        model=default_model,
                    )
                except Exception:
                    pass
            ws_model = default_model or ""
            for desc_name in app_inf.get_role_descriptors():
                rcfg = os.path.join(ws_dir, desc_name)
                if os.path.isfile(rcfg):
                    try:
                        with open(rcfg, "r", encoding="utf-8") as f:
                            rdata = json.load(f)
                        if rdata.get("model"):
                            ws_model = str(rdata["model"])
                    except Exception:
                        pass
                    break
            if ws_model:
                role_models[r.role_name] = ws_model
                m_low = ws_model.lower()
                if "lite" in m_low:
                    antigravity_models[r.role_name] = "flash_lite"
                elif "flash" in m_low:
                    antigravity_models[r.role_name] = "flash"
                elif "argon" in m_low or "carbon" in m_low:
                    antigravity_models[r.role_name] = "inherit"
                elif "pro" in m_low:
                    antigravity_models[r.role_name] = "pro"
                else:
                    antigravity_models[r.role_name] = "inherit"

        ready_by_role: dict[str, list[dict[str, Any]]] = {}
        blocked_by_role: dict[str, list[dict[str, Any]]] = {}
        for r in declared_roles:
            q_ready, q_blocked = work.compute_role_work_queue(
                r.role_name,
                dir_scope=scope,
                repo_root=root,
                target_unit=target_input if is_unit else None,
            )
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
            payload: dict[str, Any] = {
                "scope": scope,
                "is_clean": is_clean,
                "ready_roles": list(ready_by_role.keys()),
                "ready": ready_by_role,
                "blocked": blocked_by_role,
                "workspace_dirs": workspace_dirs,
                "role_models": role_models,
                "antigravity_models": antigravity_models,
            }
            if target_role:
                payload["up_to_role"] = target_role
            print(json.dumps(payload, indent=2))
            return 0

        if is_clean:
            print(
                f"CLEAN: All nodes in scope '{scope}' evaluate clean across all {len(declared_roles)} roles."
            )
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


def _find_subagent_tool_mod(target_scope: str | None, args_list: list[str]) -> Any:
    subagent_tool_mod = None
    for _r in _get_roots():
        for _entry in os.listdir(_r) if os.path.isdir(_r) else []:
            if _entry.startswith((".", "bazel-", "venv")):
                continue
            if (
                (_dir_scope and _entry == _dir_scope)
                or (target_scope and _entry == target_scope)
                or (_entry in args_list)
            ):
                continue
            _cand = os.path.join(
                _r, _entry, "parts", "subagent", "lib", "subagent_tool_impl.py"
            )
            if os.path.isfile(_cand) and os.path.isdir(
                os.path.join(_r, _entry, "support", "lib")
            ):
                try:
                    subagent_tool_mod = importlib.import_module(
                        f"{_entry}.parts.subagent.lib.subagent_tool_impl"
                    )
                    break
                except ImportError:
                    pass
        if subagent_tool_mod:
            break
    if subagent_tool_mod is None:
        try:
            from autofab.parts.subagent.lib import (
                subagent_tool_impl as subagent_tool_mod,
            )
        except ImportError:
            pass
    return subagent_tool_mod


def _compute_role_depths(roles_map: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Ranks roles by dependency depth so that upstream roles precede downstream roles."""
    depths: dict[str, int] = {}
    resolving: set[str] = set()

    def _depth(role: str) -> int:
        if role in depths:
            return depths[role]
        if role in resolving:
            return 0
        resolving.add(role)
        rcfg = roles_map.get(role, {})
        upstream: set[str] = set()
        for k in (
            "role_deps",
            "star_role_deps",
            "feedback_role_deps",
            "star_feedback_role_deps",
            "silent_role_deps",
            "silent_cross_role_deps",
            "stub_role_deps",
        ):
            for d in rcfg.get(k) or []:
                upstream.add(d.split(":")[-1].strip().lower())
        val = (
            1 + max((_depth(u) for u in upstream if u in roles_map), default=-1)
            if upstream
            else 0
        )
        resolving.discard(role)
        depths[role] = val
        return val

    for r in roles_map:
        _depth(r)
    return depths


def resolve_scope_nodes(
    target_str: str,
    root_dir: str,
    loader: Any,
    up_to_role: str | None = None,
    exclude_roles: Sequence[str] | None = None,
    pipeline: str | None = None,
) -> list[Any] | None:
    """Resolves a filesystem path or scope string to an ordered list of DagNodes.

    Returns None if target_str is not a directory/path scope (e.g. is a specific Bazel target label).
    """
    from autofab.parts.dag.lib import dag_storage

    raw_str = target_str.strip()
    if raw_str.startswith("//") and ":" in raw_str:
        return None

    explicit_role = None
    if "#" in raw_str:
        raw_str, explicit_role = raw_str.split("#", 1)

    clean_path = raw_str.lstrip("/").rstrip("/")
    abs_cand = os.path.abspath(os.path.join(root_dir, clean_path))
    if not os.path.exists(abs_cand):
        abs_cand = os.path.abspath(clean_path)
        if not os.path.exists(abs_cand):
            for entry in sorted(os.listdir(root_dir)):
                if not entry.startswith((".", "bazel-", "venv")):
                    cand_pkg = os.path.join(root_dir, entry, clean_path)
                    if os.path.exists(cand_pkg):
                        abs_cand = os.path.abspath(cand_pkg)
                        break
            if not os.path.exists(abs_cand):
                return None

    try:
        norm_rel = os.path.relpath(abs_cand, root_dir).replace("\\", "/")
    except ValueError:
        return None

    if norm_rel == ".":
        return None

    segs = norm_rel.split("/")
    dir_scope = ""
    part_filter = None
    role_filter = explicit_role
    unit_filter = None

    if "parts" in segs:
        p_idx = segs.index("parts")
        dir_scope = "/".join(segs[:p_idx]) if p_idx > 0 else ""
        if len(segs) > p_idx + 1:
            part_filter = segs[p_idx + 1]
    else:
        dir_scope = segs[0]

    if dir_scope:
        parts_base = os.path.join(root_dir, dir_scope, "parts")
    else:
        parts_base = os.path.join(root_dir, "parts")
        if not os.path.isdir(parts_base):
            for entry in os.listdir(root_dir):
                cand = os.path.join(root_dir, entry, "parts")
                if os.path.isdir(cand) and not entry.startswith(
                    (".", "bazel-", "venv")
                ):
                    parts_base = cand
                    dir_scope = entry
                    break

    if not os.path.isdir(parts_base):
        return None

    scope_prefix = f"{dir_scope}/parts" if dir_scope else "parts"
    canon_meth, roles_dict = loader._get_methodology_roles(root_dir, scope_prefix)
    if not roles_dict:
        raise ValueError(
            f"No roles declared in methodology '{canon_meth}' for scope '{target_str}'"
        )

    dir_to_role: dict[str, str] = {}
    for rname, rcfg in roles_dict.items():
        src_pats = rcfg.get("src_patterns") or (
            [rcfg.get("src_pattern")] if rcfg.get("src_pattern") else []
        )
        for src_pat in src_pats:
            if src_pat:
                clean_pat = src_pat.replace("{unit_dir}/", "").replace(
                    "{unit_dir}\\", ""
                )
                if "/" in clean_pat:
                    layout_d = clean_pat.split("/", 1)[0]
                    dir_to_role[layout_d] = rname
                    if layout_d.endswith("s"):
                        dir_to_role[layout_d[:-1]] = rname
                    else:
                        dir_to_role[layout_d + "s"] = rname

    if "parts" in segs:
        p_idx = segs.index("parts")
        if len(segs) > p_idx + 2:
            tier_or_file = segs[p_idx + 2]
            if tier_or_file in dir_to_role:
                if not role_filter:
                    role_filter = dir_to_role[tier_or_file]
                if len(segs) > p_idx + 3:
                    f_name = segs[p_idx + 3]
                    stem = os.path.splitext(f_name)[0]
                    if stem.endswith("_test"):
                        unit_filter = stem[:-5]
                    else:
                        unit_filter = stem

    if part_filter:
        parts_to_scan = [part_filter]
    else:
        parts_to_scan = sorted(
            [
                d
                for d in os.listdir(parts_base)
                if os.path.isdir(os.path.join(parts_base, d)) and not d.startswith(".")
            ]
        )

    depths = _compute_role_depths(roles_dict)
    ordered_roles = sorted(roles_dict.keys(), key=lambda r: (depths.get(r, 0), r))

    if role_filter:
        roles_to_scan = [role_filter]
    elif up_to_role:
        target_clean = up_to_role.strip().lower()
        matching_idx = None
        for idx, r in enumerate(ordered_roles):
            if (
                r.lower() == target_clean
                or r.split(":")[-1].strip().lower() == target_clean
            ):
                matching_idx = idx
                break
        if matching_idx is not None:
            roles_to_scan = ordered_roles[: matching_idx + 1]
        else:
            roles_to_scan = ordered_roles
    else:
        roles_to_scan = ordered_roles

    if pipeline:
        pipe_clean = pipeline.strip().lower()
        if pipe_clean == "combined":
            roles_to_scan = [
                r
                for r in roles_to_scan
                if roles_dict.get(r, {}).get("pipeline")
                in (None, "", "standard", "pretense")
            ]
        else:
            roles_to_scan = [
                r
                for r in roles_to_scan
                if roles_dict.get(r, {}).get("pipeline") in (None, "", pipe_clean)
            ]

    if exclude_roles:
        exclude_set = {r.strip().lower() for r in exclude_roles}
        roles_to_scan = [
            r
            for r in roles_to_scan
            if r.strip().lower() not in exclude_set
            and r.split(":")[-1].strip().lower() not in exclude_set
        ]

    nodes: list[Any] = []

    for role_name in roles_to_scan:
        for p_name in parts_to_scan:
            p_dir = os.path.join(parts_base, p_name)
            high_dir = os.path.join(p_dir, "high")
            if not os.path.isdir(high_dir):
                continue

            scope_prefix = (
                f"{dir_scope}/parts/{p_name}" if dir_scope else f"parts/{p_name}"
            )
            try:
                _, roles_dict = loader._get_methodology_roles(  # type: ignore[reportPrivateUsage]
                    root_dir, scope_prefix
                )
            except Exception:
                roles_dict = {}

            role_cfg = roles_dict.get(role_name, {})
            active_types = role_cfg.get("active_component_types", ["implementation"])

            for hls_file in sorted(os.listdir(high_dir)):
                if not hls_file.endswith(".md"):
                    continue
                uname = hls_file[:-3]
                if unit_filter and uname != unit_filter:
                    continue

                hls_path = os.path.join(high_dir, hls_file)
                try:
                    hls_info = loader._parse_hls(hls_path)  # type: ignore[reportPrivateUsage]
                    comp_type = hls_info.get("component_type", "implementation")
                except Exception:
                    comp_type = "implementation"

                unit_prefix = (
                    f"//{dir_scope}/parts/{p_name}:{uname}"
                    if dir_scope
                    else f"//parts/{p_name}:{uname}"
                )
                if comp_type in active_types:
                    nodes.append(
                        dag_storage.DagNode(
                            unit_address=dag_storage.UnitAddress(unit_prefix),
                            role_address=dag_storage.RoleAddress(role_name),
                        )
                    )

    return nodes if nodes else None


def run_target_action(
    target_str: str,
    action: str = "mark-clean",
    message: str | None = None,
    workspace_dir: str | None = None,
    up_to_role: str | None = None,
    exclude_roles: Sequence[str] | None = None,
    pipeline: str | None = None,
) -> int:
    if workspace_dir and os.path.isdir(workspace_dir):
        os.chdir(workspace_dir)

    curr = os.path.dirname(os.path.realpath(__file__))
    repo_root = (
        os.path.abspath(workspace_dir)
        if workspace_dir and os.path.isdir(workspace_dir)
        else (
            os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            or os.path.abspath(os.path.join(curr, "../../.."))
        )
    )

    from autofab.parts.systems.lib import autofab_asm
    from autofab.parts.uv.lib import manifest_loader, target
    from autofab.parts.dag.lib import dag_storage
    from support.lib.lifecycle import get_singleton

    autofab_asm.__initialize__()
    loader = get_singleton(manifest_loader.UvManifestLoader)
    storage = get_singleton(dag_storage.DagStorage)

    scope_nodes = resolve_scope_nodes(
        target_str,
        repo_root,
        loader,
        up_to_role=up_to_role,
        exclude_roles=exclude_roles,
        pipeline=pipeline,
    )

    if scope_nodes is not None:
        if action == "mark-clean":
            count = 0
            for n in scope_nodes:
                loader.load_manifest(n)
                if hasattr(storage, "is_dirty") and not storage.is_dirty(n):
                    continue
                if hasattr(storage, "materialize_template"):
                    storage.materialize_template(n)
                if hasattr(storage, "mark_node_clean"):
                    storage.mark_node_clean(n)
                elif hasattr(storage, "mark_subgraph_clean"):
                    storage.mark_subgraph_clean(n)
                count += 1
            print(f"✔ Marked {count} target(s) clean across {target_str}")
            return 0

        elif action == "dirty":
            reason = message or "Marked dirty"
            for n in scope_nodes:
                loader.load_manifest(n)
                if hasattr(storage, "mark_node_dirty"):
                    storage.mark_node_dirty(n, reason=reason)
                else:
                    msg = dag_storage.ChangeMessage(
                        content=dag_storage.MessageContent(reason)
                    )
                    storage.add_message(msg, to=n)
            print(
                f"✔ Marked {len(scope_nodes)} target(s) dirty across {target_str} ({reason})"
            )
            return 0

        elif action == "change":
            desc = message or "Manual change"
            for n in scope_nodes:
                loader.load_manifest(n)
                storage.mark_node_clean(n, dag_storage.ChangeDescription(desc))
            print(
                f"✔ Recorded change for {len(scope_nodes)} target(s) across {target_str}: {desc}"
            )
            return 0

        elif action == "prompt":
            for n in scope_nodes:
                loader.load_manifest(n)
                get_defn = getattr(storage, "get_node_definition", None)
                defn = get_defn(n) if callable(get_defn) else None
                prompt = getattr(defn, "task_prompt", None) if defn else None
                if prompt:
                    print(f"=== {n.unit_address}#{n.role_address} ===\n{prompt}\n")
            return 0

        else:
            print(
                f"Error: Action '{action}' cannot be run across multiple targets in scope '{target_str}' ({len(scope_nodes)} nodes). Specify a single target.",
                file=sys.stderr,
            )
            return 2
    else:
        target_util = get_singleton(target.UvTarget)
        node = target_util.normalize_target(target.TargetIdentifier(target_str))
        if not node.role_address:
            node = dag_storage.DagNode(
                unit_address=node.unit_address,
                role_address=dag_storage.RoleAddress("lib"),
            )

        manifest = loader.retrieve_manifest(node)
        if manifest is None:
            print(
                f"Error: Target '{target_str}' not found (no specification found for '{node.unit_address}')",
                file=sys.stderr,
            )
            return 1

        loader.load_manifest(node)

    if action == "mark-clean":
        if hasattr(storage, "get_dependencies"):
            visited: set[Any] = set()
            order: list[Any] = []

            def dfs(n: Any) -> None:
                if n in visited:
                    return
                visited.add(n)
                loader.load_manifest(n)
                for dep in storage.get_dependencies(n):
                    dfs(dep.node)
                order.append(n)

            dfs(node)
            count = 0
            for n in order:
                if hasattr(storage, "is_dirty") and not storage.is_dirty(n):
                    continue
                if hasattr(storage, "materialize_template"):
                    storage.materialize_template(n)
                if hasattr(storage, "mark_node_clean"):
                    storage.mark_node_clean(n)
                elif hasattr(storage, "mark_subgraph_clean"):
                    storage.mark_subgraph_clean(n)
                count += 1
            if count == 0:
                print(
                    f"✔ Target is already clean: {node.unit_address}#{node.role_address}"
                )
            else:
                print(
                    f"✔ Marked {count} target(s) clean: {node.unit_address}#{node.role_address}"
                )
            return 0
        else:
            if hasattr(storage, "is_dirty") and not storage.is_dirty(node):
                print(
                    f"✔ Target is already clean: {node.unit_address}#{node.role_address}"
                )
                return 0
            if hasattr(storage, "materialize_template"):
                storage.materialize_template(node)
            if hasattr(storage, "mark_node_clean"):
                storage.mark_node_clean(node)
            elif hasattr(storage, "mark_subgraph_clean"):
                storage.mark_subgraph_clean(node)
            print(f"✔ Marked target clean: {node.unit_address}#{node.role_address}")
            return 0

    elif action == "change":
        desc = message or "Manual change"
        storage.mark_node_clean(node, dag_storage.ChangeDescription(desc))
        print(f"✔ Recorded change for {node.unit_address}#{node.role_address}: {desc}")
        return 0

    elif action == "feedback":
        if not message:
            print("Error: feedback action requires a critique message", file=sys.stderr)
            return 2
        fb_msg = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent(message)
        )
        if hasattr(storage, "add_feedback_message"):
            storage.add_feedback_message(node, fb_msg)
        else:
            storage.add_message(fb_msg, to=node)
        print(f"✔ Added feedback to {node.unit_address}#{node.role_address}: {message}")
        return 0

    elif action == "dirty":
        reason = message or "Marked dirty"
        if hasattr(storage, "mark_node_dirty"):
            storage.mark_node_dirty(node, reason=reason)
        else:
            msg = dag_storage.ChangeMessage(content=dag_storage.MessageContent(reason))
            storage.add_message(msg, to=node)
        print(
            f"✔ Marked target dirty: {node.unit_address}#{node.role_address} ({reason})"
        )
        return 0

    elif action == "prompt":
        get_defn = getattr(storage, "get_node_definition", None)
        defn = get_defn(node) if callable(get_defn) else None
        prompt = getattr(defn, "task_prompt", None) if defn else None
        if prompt:
            print(f"=== {node.unit_address}#{node.role_address} ===\n{prompt}\n")
        return 0

    else:
        print(f"Error: Unknown action '{action}'", file=sys.stderr)
        return 2


def run_mark_clean_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab mark-clean",
        description="Mark target or scope clean in DAG metadata without running LLM loop.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target node, file path, or scope directory.",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w",
        default=None,
        help="Custom workspace directory (default: current working directory).",
    )
    parser.add_argument(
        "--up-to-role",
        "--up-to",
        default=None,
        help="Only mark roles up to the specified role clean.",
    )
    parser.add_argument(
        "--exclude-roles",
        nargs="+",
        default=None,
        help="Roles to exclude from marking clean.",
    )
    parser.add_argument(
        "--pipeline",
        "--method",
        dest="pipeline",
        choices=["standard", "pretense", "combined"],
        default=None,
        help="Pipeline to mark clean.",
    )
    parser.add_argument(
        "--standard",
        dest="pipeline",
        action="store_const",
        const="standard",
        help="Use standard pipeline.",
    )
    parser.add_argument(
        "--pretense",
        dest="pipeline",
        action="store_const",
        const="pretense",
        help="Use pretense pipeline.",
    )
    parser.add_argument(
        "--combined",
        dest="pipeline",
        action="store_const",
        const="combined",
        help="Use combined pipeline.",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target or _get_dir_scope()
    if not target:
        print(
            "Error: Target node, file path, or scope directory must be specified (e.g. uv run autofab mark-clean staging).",
            file=sys.stderr,
        )
        return 1
    return run_target_action(
        target_str=target,
        action="mark-clean",
        workspace_dir=parsed.workspace_dir,
        up_to_role=parsed.up_to_role,
        exclude_roles=parsed.exclude_roles,
        pipeline=parsed.pipeline,
    )


def run_mark_dirty_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab mark-dirty",
        description="Mark target or scope dirty in DAG storage.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target node, file path, or scope directory.",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Optional reason why the target is marked dirty.",
    )
    parser.add_argument(
        "-m",
        "--message",
        dest="msg_flag",
        default=None,
        help="Reason why the target is marked dirty.",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w",
        default=None,
        help="Custom workspace directory (default: current working directory).",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Additional arguments or trailing message",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target or _get_dir_scope()
    if not target:
        print(
            "Error: Target node, file path, or scope directory must be specified (e.g. uv run autofab mark-dirty staging).",
            file=sys.stderr,
        )
        return 1
    msg = parsed.msg_flag or parsed.message
    if not msg and parsed.extra_args:
        msg = " ".join(parsed.extra_args)
    if not msg:
        msg = "Marked dirty"
    return run_target_action(
        target_str=target,
        action="dirty",
        message=msg,
        workspace_dir=parsed.workspace_dir,
    )


run_dirty_cli = run_mark_dirty_cli


def run_change_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab change",
        description="Record a change description on a target node or scope.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target node, file path, or scope directory.",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Change description.",
    )
    parser.add_argument(
        "-m",
        "--message",
        dest="msg_flag",
        default=None,
        help="Change description.",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w",
        default=None,
        help="Custom workspace directory.",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Additional arguments or trailing message",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target or _get_dir_scope()
    if not target:
        print(
            "Error: Target must be specified (e.g. uv run autofab change <target> [message]).",
            file=sys.stderr,
        )
        return 1
    desc = parsed.msg_flag or parsed.message
    if not desc and parsed.extra_args:
        desc = " ".join(parsed.extra_args)
    desc = desc or "Manual change"
    return run_target_action(
        target_str=target,
        action="change",
        message=desc,
        workspace_dir=parsed.workspace_dir,
    )


def run_prompt_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab prompt",
        description="Print task prompt for a target node or scope.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target node, file path, or scope directory.",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w",
        default=None,
        help="Custom workspace directory.",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target or _get_dir_scope()
    if not target:
        print(
            "Error: Target must be specified (e.g. uv run autofab prompt <target>).",
            file=sys.stderr,
        )
        return 1
    return run_target_action(
        target_str=target,
        action="prompt",
        workspace_dir=parsed.workspace_dir,
    )


def run_blame_cli(argv: list[str], prog: str = "autofab blame") -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Attribute feedback or blame critique to a target node or culprit file.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target node or culprit file path receiving feedback.",
    )
    parser.add_argument(
        "critique",
        nargs="?",
        default=None,
        help="Actionable critique message.",
    )
    parser.add_argument(
        "-m",
        "--message",
        dest="msg_flag",
        default=None,
        help="Actionable critique message.",
    )
    parser.add_argument(
        "--slug",
        "--spec-slug",
        dest="slug",
        default=None,
        help="Specification contract slug declared in low/*.pyi",
    )
    parser.add_argument(
        "--viol",
        "--violation",
        dest="viol",
        default=None,
        help="Taxonomy violation code (e.g. [viol:post.wrong_return])",
    )
    parser.add_argument(
        "--facet",
        "--facets",
        dest="facet",
        default=None,
        help="Constrained noun phrase facet (max 8 words, max 120 chars)",
    )
    parser.add_argument(
        "--lines",
        "--line",
        dest="lines",
        default=None,
        help="Line number or line range within culprit file",
    )
    parser.add_argument(
        "--witness",
        dest="witness",
        default=None,
        help="Context-free input/output witness values",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path to canonical repository root.",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w",
        default=None,
        help="Custom workspace directory.",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target
    if not target:
        print(
            f"Error: Target must be specified (e.g. uv run {prog} <target> '<critique>').",
            file=sys.stderr,
        )
        return 1

    critique = parsed.msg_flag or parsed.critique
    if not critique and (parsed.slug or parsed.viol or parsed.facet):
        slug_val = parsed.slug or ""
        if slug_val and not slug_val.startswith("[slug:"):
            slug_val = f"[slug:{slug_val.strip('[]')}]"
        viol_val = parsed.viol or ""
        if viol_val and not viol_val.startswith("[viol:"):
            viol_val = f"[viol:{viol_val.strip('[]')}]"
        facet_val = parsed.facet or ""
        critique = f"{slug_val} {viol_val} Facet: {facet_val}".strip()
        if getattr(parsed, "lines", None):
            critique += f" Lines: {parsed.lines}"
        if parsed.witness:
            critique += f" Witness: {parsed.witness}"
    if not critique:
        print(
            f"Error: blame command requires a critique message (e.g. uv run {prog} <target> '<critique>' or -m '<critique>').",
            file=sys.stderr,
        )
        return 2

    # Check if executing within an isolated role workspace or target looks like a file path
    is_role_ws = any(
        os.path.isfile(desc) for desc in _get_app_info().get_role_descriptors()
    )
    is_target_label = target.startswith("//") or (
        ":" in target and not os.path.exists(target)
    )

    if (is_role_ws or not is_target_label) and cli_tool_impl is not None:
        cmd_args = ["blame", target, critique]
        if parsed.repo_root:
            cmd_args.extend(["--repo-root", parsed.repo_root])
        try:
            ret = cli_tool_impl.main(cmd_args)
            if ret == 0 or is_role_ws:
                return ret
        except Exception:
            if is_role_ws:
                raise

    # Fallback / standalone DAG mode: add feedback message via run_target_action
    return run_target_action(
        target_str=target,
        action="feedback",
        message=critique,
        workspace_dir=parsed.workspace_dir,
    )


run_feedback_cli = run_blame_cli


def run_reject_cli(argv: list[str], prog: str = "autofab reject") -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Reject active feedback on an unmodified target file and scrub feedback from header.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target file path receiving feedback.",
    )
    parser.add_argument(
        "reason",
        nargs="?",
        default=None,
        help="Actionable contest reason explaining why existing code is already compliant.",
    )
    parser.add_argument(
        "-m",
        "--message",
        dest="msg_flag",
        default=None,
        help="Actionable contest reason explaining why existing code is already compliant.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path to canonical repository root.",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target
    if not target:
        print(
            f"Error: Target must be specified (e.g. uv run {prog} <target> '<reason>').",
            file=sys.stderr,
        )
        return 1

    reason = parsed.msg_flag or parsed.reason
    if not reason:
        print(
            f"Error: reject command requires a reason message (e.g. uv run {prog} <target> '<reason>').",
            file=sys.stderr,
        )
        return 2

    if cli_tool_impl is not None:
        cmd_args = ["reject", target, reason]
        if parsed.repo_root:
            cmd_args.extend(["--repo-root", parsed.repo_root])
        return cli_tool_impl.main(cmd_args)

    print("Error: cli_tool_impl not available for reject execution.", file=sys.stderr)
    return 1


def run_clean(
    argv: list[str],
    default_harness: str | None = None,
    prog: str = "autofab clean",
) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Autofab Multi-Agent Workspace Convergence Tool",
    )
    parser.add_argument(
        "dir_scope",
        nargs="?",
        default="",
        help="Directory scope or target to clean.",
    )
    parser.add_argument(
        "target_role",
        nargs="?",
        default=None,
        help="Optional target role boundary to execute up to.",
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
        default=None,
        help="Target role boundary (alternative flag).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model configuration or profile name (e.g. default, deepseek-flash, gemini-flash).",
    )
    parser.add_argument(
        "--max-waves",
        type=int,
        default=100,
        help="Maximum execution wave iterations (default: 100).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Maximum targets dispatched per role round.",
    )
    parser.add_argument(
        "--concurrent-subagents",
        type=int,
        default=None,
        help="Maximum concurrent subagents running at a time (allowed value: 1).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum execution timeout in seconds for subagent processes (default: no timeout).",
    )
    parser.add_argument(
        "--max-context-tokens",
        type=int,
        default=None,
        help="Context token compaction limit for subagent processes.",
    )
    parser.add_argument(
        "--repo-root",
        "--workspace-dir",
        "-w",
        dest="repo_root",
        default=None,
        help="Repository root or workspace directory.",
    )
    parser.add_argument(
        "--simulation",
        "--simulate",
        dest="simulation",
        action="store_true",
        help="Run in simulation mode without external subprocesses.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Force headless execution even on antigravity harness.",
    )
    parser.add_argument(
        "--dsh-web",
        action="store_true",
        help="Use DeepSeek Harness Web loopback bridge instead of Electron Desktop RPC.",
    )
    parser.add_argument(
        "--pipeline",
        "--method",
        dest="pipeline",
        choices=["standard", "pretense", "combined"],
        default=None,
        help="Use specified testing pipeline ('standard', 'pretense', or 'combined').",
    )
    parser.add_argument(
        "--standard",
        dest="pipeline",
        action="store_const",
        const="standard",
        help="Use standard testing pipeline.",
    )
    parser.add_argument(
        "--pretense",
        dest="pipeline",
        action="store_const",
        const="pretense",
        help="Use Pretense testing pipeline (pretense, pretense_qa, pretense_coverage) instead of standard test/qa/coverage.",
    )
    parser.add_argument(
        "--combined",
        dest="pipeline",
        action="store_const",
        const="combined",
        help="Use combined testing pipeline (standard + pretense).",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Execute fused baseline role instead of multi-agent DAG.",
    )
    parser.add_argument(
        "--antigravity-dispatch",
        choices=["message", "new-conversation", "none"],
        default=None,
        help="Antigravity Desktop IPC dispatch mode when harness is antigravity.",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        help="Active experiment identifier (e.g. structured_blame).",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Additional arguments or trailing message",
    )
    parsed = parser.parse_args(argv)

    if parsed.experiment:
        os.environ["AUTOFAB_EXPERIMENT"] = parsed.experiment
        try:
            from support.lib import experiments

            experiments.set_active_experiments(parsed.experiment)
        except Exception:
            try:
                from autofab.support.lib import experiments

                experiments.set_active_experiments(parsed.experiment)
            except Exception:
                pass

    target_input = parsed.scope_opt or parsed.dir_scope or _get_dir_scope()
    if not target_input:
        print(
            f"Error: Directory scope or target must be specified (e.g. uv run {prog} staging or staging#qa).",
            file=sys.stderr,
        )
        return 1

    scope, parsed_role, is_unit = parse_cleanroom_target(target_input)
    target_role = (
        (parsed.role_opt or parsed.target_role or parsed_role or "").strip().lower()
    )
    if parsed.baseline and not target_role:
        if parsed.pipeline == "combined":
            target_role = "combined_baseline"
        elif parsed.pipeline == "pretense":
            target_role = "pretense_baseline"
        else:
            target_role = "baseline"

    active_pipeline = resolve_scope_pipeline(
        scope=scope,
        repo_root=parsed.repo_root,
        explicit_pretense=(parsed.pipeline == "pretense"),
        explicit_pipeline=parsed.pipeline,
        target_role=target_role or None,
    )

    bound_model = parsed.model or resolve_default_model(parsed.repo_root)
    if bound_model == "default":
        resolved_m = resolve_default_model(parsed.repo_root)
        if resolved_m:
            bound_model = resolved_m

    if parsed.simulation:
        active_harness = "simulation"
    else:
        active_harness = resolve_model_harness(bound_model, repo_root=parsed.repo_root)

    if parsed.headless:
        print(
            "Error: Headless execution is banned. Crash immediately.", file=sys.stderr
        )
        return 1

    # Autonomous DSH / Simulation execution
    is_autonomous = parsed.simulation or active_harness in (
        "dsh",
        "simulation",
        "deepseek",
        "deepseek-harness",
    )
    if is_autonomous:
        subagent_tool_mod = _find_subagent_tool_mod(scope, argv)
        if subagent_tool_mod is not None:
            print("\n" + "=" * 72)
            print("AUTONOMOUS DSH COORDINATION INITIATED:")
            print(f"Harness: {active_harness} (DSH Server Bridge)")
            print(f"Target Scope: {scope}")
            print("Status: Dispatching to live DSH Web/Desktop server.")
            print(
                "Action: None required. Do NOT invoke coordinator or interfere with workspaces."
            )
            print("=" * 72 + "\n", flush=True)
            forward_args = ["clean", "--scope", scope]
            if target_role:
                forward_args.extend(["--role", target_role])
            if is_unit:
                forward_args.extend(["--target", target_input])
            forward_args.extend(["--harness", active_harness])
            h_model = bound_model
            if h_model:
                forward_args.extend(["--model", h_model])
            if parsed.max_waves is not None:
                forward_args.extend(["--max-waves", str(parsed.max_waves)])
            if parsed.batch_size is not None:
                forward_args.extend(["--batch-size", str(parsed.batch_size)])
            if getattr(parsed, "concurrent_subagents", None) is not None:
                forward_args.extend(
                    ["--concurrent-subagents", str(parsed.concurrent_subagents)]
                )
            if parsed.timeout is not None:
                forward_args.extend(["--timeout", str(parsed.timeout)])
            if parsed.max_context_tokens is not None:
                forward_args.extend(
                    ["--max-context-tokens", str(parsed.max_context_tokens)]
                )
            if parsed.repo_root:
                forward_args.extend(["--repo-root", parsed.repo_root])
            if parsed.pipeline == "pretense":
                forward_args.append("--pretense")
            if parsed.simulation:
                forward_args.append("--simulation")
            if parsed.experiment:
                forward_args.extend(["--experiment", parsed.experiment])
            if getattr(parsed, "dsh_web", False):
                os.environ["AUTOFAB_DSH_WEB"] = "1"
                forward_args.append("--dsh-web")
            else:
                app_info = _get_app_info()
                if app_info and app_info.resolve_default_dsh_web(parsed.repo_root):
                    os.environ["AUTOFAB_DSH_WEB"] = "1"
                    forward_args.append("--dsh-web")
            return subagent_tool_mod.main(forward_args)
        print(
            "Error: Subagent tool runner module not found for headless execution.",
            file=sys.stderr,
        )
        return 1

    # In-IDE Antigravity interactive mode:
    # 1. Refresh global agent definitions
    ensure_antigravity_plugin_installed()

    root = parsed.repo_root or find_workspace_root()
    if parsed.repo_root:
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(parsed.repo_root)
    from support.lib.lifecycle import enter_phase, get_singleton
    from autofab.parts.agent.lib import session as agent_session
    from autofab.parts.workspace.lib import role_registry, provision
    from autofab.parts.workspace_cli.lib import work

    with enter_phase(agent_session.agent_session):
        reg = get_singleton(role_registry.WorkspaceRegistry)
        work = get_singleton(work.WorkspaceWorkManager)
        prov = get_singleton(provision.WorkspaceProvisioner)

        declared_roles = reg.list_roles(root, dir_scope=scope)
        if not declared_roles:
            print(
                f"Error: No declared roles found for directory scope '{scope}'.",
                file=sys.stderr,
            )
            return 1

        if active_pipeline == "combined":
            declared_roles = [
                r
                for r in declared_roles
                if r.pipeline in (None, "", "standard", "pretense")
            ]
        elif active_pipeline:
            declared_roles = [
                r for r in declared_roles if r.pipeline in (None, "", active_pipeline)
            ]

        if target_role:
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                r_clean = r.role_name.split(":")[-1].strip().lower()
                if r_clean == target_role or r.role_name.lower() == target_role:
                    matching_idx = idx
                    break
            if matching_idx is None:
                try:
                    fused_r_def = reg.resolve_role_definition(
                        target_role, repo_root=root, dir_scope=scope
                    )
                    if fused_r_def and fused_r_def.fused_roles:
                        fused_names = {
                            f.split(":")[-1].strip().lower()
                            for f in fused_r_def.fused_roles
                        }
                        upstream_roles = []
                        for r in declared_roles:
                            r_c = r.role_name.split(":")[-1].strip().lower()
                            if r_c in fused_names:
                                break
                            upstream_roles.append(r)
                        declared_roles = upstream_roles + [fused_r_def]
                    else:
                        valid_names = ", ".join(r.role_name for r in declared_roles)
                        print(
                            f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}",
                            file=sys.stderr,
                        )
                        return 1
                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    valid_names = ", ".join(r.role_name for r in declared_roles)
                    print(
                        f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}",
                        file=sys.stderr,
                    )
                    return 1
            else:
                declared_roles = list(declared_roles[: matching_idx + 1])

        # Check DAG readiness across declared roles
        ready_nodes: list[tuple[str, str, list[str]]] = []
        blocked_nodes: list[tuple[str, str, list[str]]] = []
        for r in declared_roles:
            q_ready, q_blocked = work.compute_role_work_queue(
                r.role_name,
                dir_scope=scope,
                repo_root=root,
                target_unit=target_input if is_unit else None,
            )
            for it in q_ready:
                ready_nodes.append(
                    (r.role_name, it.target_file, list(it.dirtiness_reasons))
                )
            for it in q_blocked:
                blocked_nodes.append(
                    (r.role_name, it.target_file, list(it.blocked_reasons))
                )

        role_suffix = f" (up to role: {target_role})" if target_role else ""
        if not ready_nodes and not blocked_nodes:
            deleted = decommission_workspaces(
                scope, target_role=target_role, repo_root=root
            )
            cleanup_msg = (
                f" Decommissioned {deleted} role workspace(s)." if deleted else ""
            )
            print(
                f"✔ CLEAN: All nodes in scope '{scope}' evaluate CLEAN{role_suffix}.{cleanup_msg} No work pending."
            )
            return 0

        # Auto-provision role workspaces on demand for ready roles
        if ready_nodes:
            prov = get_singleton(provision.WorkspaceProvisioner)
            ready_role_names = {r_name for r_name, _, _ in ready_nodes}
            for r_name in ready_role_names:
                prov.commission(
                    r_name,
                    dir_scope=scope,
                    repo_root=root,
                    model=bound_model,
                )

        in_antigravity = bool(os.environ.get("ANTIGRAVITY_AGENT")) or bool(
            os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
        )

        harness = active_harness
        model_to_bind = bound_model
        model_hint = f" (model: {model_to_bind})" if model_to_bind else ""
        print(f"=== Autofab Clean Pre-flight [Scope: {scope}{role_suffix}] ===")
        print(f"Verified {len(declared_roles)} declared roles{model_hint}.")

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
        target_display = (
            f"{target_input}#{target_role}"
            if (is_unit and target_role)
            else (target_input if is_unit else f"{scope}{role_hint}")
        )
        queue_hint = (
            f" {target_input} {target_role}"
            if (is_unit and target_role)
            else (
                f" {target_input}"
                if is_unit
                else (f" {target_role}" if target_role else "")
            )
        )

        # Determine Antigravity dispatch mode:
        # (a) When called in Antigravity: default to "message" (reactive wakeup to current conversation)
        #     and print directive directly.
        # (b) When called outside Antigravity: default to "new-conversation" (spawn tab in Desktop app).
        raw_dispatch = getattr(parsed, "antigravity_dispatch", None)
        if raw_dispatch == "none":
            dispatch_mode = "none"
        elif raw_dispatch in ("message", "new-conversation"):
            dispatch_mode = raw_dispatch
        elif in_antigravity:
            dispatch_mode = "message"
        else:
            dispatch_mode = "new-conversation"

        if dispatch_mode != "none":
            dispatched = dispatch_antigravity_coordination(
                target_display=target_display,
                mode=dispatch_mode,
                model=model_to_bind or "flash",
            )
            if not in_antigravity and dispatch_mode == "new-conversation":
                if not dispatched:
                    print(
                        f"\nError: Target model '{bound_model}' is configured for harness 'antigravity', "
                        f"but could not dispatch to Antigravity Desktop via agentapi.\n"
                        f"Please ensure Antigravity Desktop is installed and running, or execute inside the Antigravity agentic environment.",
                        file=sys.stderr,
                    )
                    return 1
                print("\n" + "=" * 72)
                print("ANTIGRAVITY DESKTOP COORDINATION DISPATCHED:")
                print(
                    f"✔ Dedicated conversation opened in Antigravity Desktop for {target_display}."
                )
                print(
                    "The Antigravity coordinator subagent will execute DAG convergence in the desktop app."
                )
                print("=" * 72)
                return 0

        ag_coord_model = "inherit"
        if model_to_bind:
            m_low = model_to_bind.lower()
            if "lite" in m_low:
                ag_coord_model = "flash_lite"
            elif "flash" in m_low:
                ag_coord_model = "flash"
            elif "pro" in m_low:
                ag_coord_model = "pro"

        print("\n" + "=" * 72)
        print("AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE:")
        print("The 'autofab_coordinator' subagent definition is installed and ready.")
        print("Immediately invoke the coordinator subagent in this step:")
        print("  invoke_subagent(")
        print('    TypeName="autofab_coordinator",')
        print('    Role="Autofab Coordinator",')
        print(f'    Model="{ag_coord_model}",')
        print(
            f'    Prompt="Clean all dirty nodes in {target_display} using autofab_coordinator."'
        )
        print("  )")
        print("\nCoordinator execution steps:")
        print(
            f"  1. Evaluate DAG ready nodes via 'uv run autofab work-queue {scope}{queue_hint} --json'."
        )
        print(
            "  2. Wake/dispatch workspace-bound role subagents (TypeName: 'autofab_worker')."
        )
        print(
            "  3. Direct role workers to drain ready nodes via submit, blame, or fail."
        )
        print("  4. Converge the DAG across topological waves.")
        print("  5. Decommission role workspaces upon clean convergence.")
        print("=" * 72)
        return 0


run_orchestrate = run_clean


def run_clean_cli(argv: list[str]) -> int:
    return run_clean(argv, prog="autofab clean")


def main_clean(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if "--repo-root" in args_list:
        try:
            rr_idx = args_list.index("--repo-root")
            if rr_idx + 1 < len(args_list):
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(
                    args_list[rr_idx + 1]
                )
        except (ValueError, IndexError):
            pass
    return run_clean(args_list, prog="autofab clean")


def main_orchestrate(argv: list[str] | None = None) -> int:
    return main_clean(argv)


def run_benchmark_cli(argv: list[str]) -> int:
    model_flags: list[str] = []
    suite_flags: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith(("--model=", "--models=")):
            model_flags.append(arg.split("=", 1)[1])
        elif arg in ("--model", "--models") and i + 1 < len(argv):
            model_flags.append(argv[i + 1])
            i += 1
        elif arg.startswith(("--suite=", "--suites=")):
            suite_flags.append(arg.split("=", 1)[1])
        elif arg in ("--suite", "--suites") and i + 1 < len(argv):
            suite_flags.append(argv[i + 1])
            i += 1
        i += 1

    if len(model_flags) > 1:
        print(
            f"Error: Multiple --model flags specified ({model_flags}). A benchmark flight accepts exactly one model.",
            file=sys.stderr,
        )
        return 1

    if len(suite_flags) > 1:
        print(
            f"Error: Multiple --suite flags specified ({suite_flags}). A benchmark flight accepts exactly one suite.",
            file=sys.stderr,
        )
        return 1

    known_suites = {
        "dag_engine",
        "dag_engine_lite",
        "ring_buffer",
        "semver_solver",
        "task_queue",
        "lru_cache",
        "heapq",
        "graphlib",
    }
    if model_flags:
        m_val = model_flags[0].strip().lower()
        if m_val in known_suites:
            print(
                f"Error: '{m_val}' is a benchmark suite name, not a model profile. Did you mean --suite {m_val}?",
                file=sys.stderr,
            )
            return 1

    for idx, arg in enumerate(argv):
        if arg.startswith("--experiment="):
            os.environ["AUTOFAB_EXPERIMENT"] = arg.split("=", 1)[1]
        elif arg == "--experiment" and idx + 1 < len(argv):
            os.environ["AUTOFAB_EXPERIMENT"] = argv[idx + 1]
    if "--dsh-web" in argv:
        os.environ["AUTOFAB_DSH_WEB"] = "1"
    else:
        app_info = _get_app_info()
        if app_info and app_info.resolve_default_dsh_web():
            os.environ["AUTOFAB_DSH_WEB"] = "1"
    normalized_argv: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--model="):
            normalized_argv.append("--models=" + arg.split("=", 1)[1])
        elif arg == "--model" and i + 1 < len(argv):
            normalized_argv.append("--models")
            normalized_argv.append(argv[i + 1])
            i += 1
        else:
            normalized_argv.append(arg)
        i += 1

    for r in _get_roots():
        if not os.path.isdir(r):
            continue
        try:
            for entry in os.listdir(r):
                if entry.startswith((".", "bazel-", "venv")):
                    continue
                cand = os.path.join(
                    r, entry, "parts", "benchmark", "lib", "benchmark_impl.py"
                )
                if os.path.isfile(cand):
                    mod = importlib.import_module(
                        f"{entry}.parts.benchmark.lib.benchmark_impl"
                    )
                    if hasattr(mod, "main"):
                        return int(mod.main(normalized_argv))
        except OSError:
            pass

    print(
        "Error: Failed to locate benchmark component (parts/benchmark/lib/benchmark_impl.py) across discovered Cleanroom package roots.",
        file=sys.stderr,
    )
    return 1


def main_benchmark(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if "--repo-root" in args_list:
        try:
            rr_idx = args_list.index("--repo-root")
            if rr_idx + 1 < len(args_list):
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(
                    args_list[rr_idx + 1]
                )
        except (ValueError, IndexError):
            pass
    return run_benchmark_cli(args_list)


def run_commission_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab commission",
        description="Commission and initialize isolated role workspaces with model and harness bindings.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target scope or role target (e.g. staging#qa, or staging with --all).",
    )
    parser.add_argument(
        "secondary_target",
        nargs="?",
        default=None,
        help=argparse.SUPPRESS,
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
        default=None,
        help="Role name (alternative flag).",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Commission workspaces for all declared roles in scope.",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Model profile to bind (e.g. default, deepseek-flash, gemini-flash).",
    )
    parser.add_argument(
        "--reset",
        "-r",
        action="store_true",
        help="Reset workspace to clean state, clearing stale work buffers.",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Custom destination directory.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Root of canonical repository.",
    )
    parsed = parser.parse_args(argv)

    root = parsed.repo_root or find_workspace_root()
    if parsed.repo_root:
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(parsed.repo_root)

    target = parsed.target
    secondary = parsed.secondary_target
    role_name = parsed.role_opt
    dir_scope = parsed.scope_opt
    all_roles = parsed.all

    if target:
        p_scope, p_role, _ = parse_cleanroom_target(target)
        if not dir_scope:
            dir_scope = p_scope
        if not role_name and p_role:
            role_name = p_role

    if secondary:
        s_scope, s_role, _ = parse_cleanroom_target(secondary)
        if not role_name and s_role:
            role_name = s_role
        elif not role_name:
            is_dir_target = bool(
                dir_scope
                and (
                    os.path.isdir(os.path.join(root, dir_scope, "parts"))
                    or os.path.isdir(os.path.join(root, dir_scope))
                )
            )
            if is_dir_target:
                role_name = s_scope
            else:
                role_name = dir_scope
                dir_scope = s_scope

    if not dir_scope:
        dir_scope = _get_dir_scope()

    if not dir_scope:
        try:
            for entry in os.listdir(root):
                if os.path.isdir(
                    os.path.join(root, entry, "parts")
                ) and not entry.startswith((".", "bazel-", "venv")):
                    dir_scope = entry
                    break
        except OSError:
            pass

    if not dir_scope:
        print(
            "Error: Directory scope must be specified (e.g. uv run autofab commission --all staging or staging#qa).",
            file=sys.stderr,
        )
        return 1

    from support.lib.lifecycle import enter_phase, get_singleton
    from autofab.parts.agent.lib import session as agent_session
    from autofab.parts.workspace.lib import role_registry, provision

    with enter_phase(agent_session.agent_session):
        prov = get_singleton(provision.WorkspaceProvisioner)
        reg = get_singleton(role_registry.WorkspaceRegistry)

        if all_roles:
            declared = reg.list_roles(root, dir_scope=dir_scope)
            if not declared:
                print(
                    f"Error: No declared roles found for directory scope '{dir_scope}'.",
                    file=sys.stderr,
                )
                return 1
            roles_to_commission = [r.role_name for r in declared]
        else:
            if not role_name:
                print(
                    f"Error: Role must be specified using <scope>#<role> syntax (e.g. uv run autofab commission {dir_scope}#qa) or use --all.",
                    file=sys.stderr,
                )
                return 1
            roles_to_commission = [role_name]

        bound_model = parsed.model or resolve_default_model(root)
        if bound_model == "default":
            resolved = resolve_default_model(root)
            if resolved:
                bound_model = resolved

        harness = resolve_model_harness(bound_model, repo_root=root)
        if harness == "antigravity":
            ensure_antigravity_plugin_installed()

        for r in roles_to_commission:
            desc = prov.commission(
                role_name=r,
                dir_scope=dir_scope,
                repo_root=root,
                custom_dest=parsed.dest,
                reset=parsed.reset,
                model=bound_model,
            )

            # Harness-specific tailoring
            if harness in ("dsh", "deepseek", "deepseek-harness"):
                try:
                    from autofab.parts.dsh.lib import dsh_workspace
                    from autofab.parts.agent.lib import session as agent_session
                    from support.lib.lifecycle import enter_phase

                    with enter_phase(agent_session.agent_session):
                        ws_cfg = get_singleton(dsh_workspace.DshWorkspaceConfigurer)
                        ws_cfg.configure_role_workspace(
                            workspace_dir=desc.workspace_dir,
                            role_name=r,
                            model_name=bound_model,
                        )
                except Exception:
                    pass

            # Record harness in role configuration descriptor
            app_inf = _get_app_info()
            for desc_name in app_inf.get_role_descriptors():
                role_cfg_path = os.path.join(desc.workspace_dir, desc_name)
                if os.path.isfile(role_cfg_path):
                    try:
                        with open(role_cfg_path, "r", encoding="utf-8") as rf:
                            role_data = json.load(rf)
                        role_data["harness"] = harness
                        if bound_model:
                            role_data["model"] = bound_model
                        with open(role_cfg_path, "w", encoding="utf-8") as wf:
                            json.dump(role_data, wf, indent=2)
                    except Exception:
                        pass

            harness_label = f" [harness: {harness}]" if harness != "antigravity" else ""
            model_label = f" [model: {bound_model}]" if bound_model else ""
            print(
                f"✔ Commissioned workspace for role '{r}'{harness_label}{model_label} at: {desc.workspace_dir}"
            )

        return 0


def decommission_workspaces(
    dir_scope: str,
    target_role: str | None = None,
    repo_root: str | None = None,
) -> int:
    """Decommissions and deletes role workspaces for a scope (and optional role boundary)."""
    root = repo_root or find_workspace_root()
    from support.lib.lifecycle import enter_phase, get_singleton
    from autofab.parts.agent.lib import session as agent_session
    from autofab.parts.workspace.lib import role_registry

    with enter_phase(agent_session.agent_session):
        reg = get_singleton(role_registry.WorkspaceRegistry)
        declared_roles = reg.list_roles(root, dir_scope=dir_scope)
        if target_role:
            target_clean = target_role.split(":")[-1].strip().lower()
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                r_clean = r.role_name.split(":")[-1].strip().lower()
                if r_clean == target_clean or r.role_name.lower() == target_clean:
                    matching_idx = idx
                    break
            if matching_idx is not None:
                declared_roles = list(declared_roles[: matching_idx + 1])
            else:
                try:
                    fused_r_def = reg.resolve_role_definition(
                        target_clean, repo_root=root, dir_scope=dir_scope
                    )
                    if fused_r_def and fused_r_def.fused_roles:
                        fused_names = {
                            f.split(":")[-1].strip().lower()
                            for f in fused_r_def.fused_roles
                        }
                        upstream_roles = []
                        for r in declared_roles:
                            r_c = r.role_name.split(":")[-1].strip().lower()
                            if r_c in fused_names:
                                break
                            upstream_roles.append(r)
                        declared_roles = upstream_roles + [fused_r_def]
                except Exception:
                    pass

        deleted_count = 0
        deleted_paths: set[str] = set()

        def _delete_dir(path: str) -> None:
            if not os.path.exists(path):
                return
            try:
                os.chmod(path, 0o777)
            except OSError:
                pass
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                for d in dirs:
                    dp = os.path.join(dirpath, d)
                    if not os.path.islink(dp):
                        try:
                            os.chmod(dp, 0o777)
                        except OSError:
                            pass
                for f in files:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        try:
                            os.chmod(fp, 0o666)
                        except OSError:
                            pass

            def _onexc(func: Any, p: str, exc_info: Any) -> None:
                try:
                    os.chmod(p, 0o777)
                    func(p)
                except OSError:
                    pass

            try:
                shutil.rmtree(path, onexc=_onexc)
            except TypeError:
                shutil.rmtree(path, ignore_errors=True)

        for r in declared_roles:
            ws_dir = reg.compute_workspace_dir(
                r.role_name, dir_scope=dir_scope, repo_root=root
            )
            if os.path.isdir(ws_dir):
                _delete_dir(ws_dir)
                reg.unregister_workspace(ws_dir, repo_root=root)
                deleted_count += 1
                deleted_paths.add(os.path.abspath(ws_dir))

        # Also sweep any orphaned workspaces in role workspace containers associated with dir_scope
        parent_dir = os.path.dirname(root)
        app_inf = _get_app_info()
        for ws_container in app_inf.get_role_workspaces_containers():
            rw_dir = os.path.join(parent_dir, ws_container)
            if os.path.isdir(rw_dir):
                clean_scope = dir_scope.strip("/").lstrip("/")
                sanitized_scope = clean_scope.replace("/", "_").replace(".", "_")
                for item in os.listdir(rw_dir):
                    item_path = os.path.join(rw_dir, item)
                    if (
                        not os.path.isdir(item_path)
                        or os.path.abspath(item_path) in deleted_paths
                    ):
                        continue
                    should_delete = False
                    for desc_name in app_inf.get_role_descriptors():
                        role_cfg = os.path.join(item_path, desc_name)
                        if os.path.isfile(role_cfg):
                            try:
                                with open(role_cfg, "r", encoding="utf-8") as f:
                                    cdata = json.load(f)
                                cfg_scope = str(
                                    cdata.get("dir_scope")
                                    or cdata.get("parts_dir")
                                    or ""
                                ).strip("/").lstrip("/")
                                if (
                                    cfg_scope == clean_scope
                                    or cfg_scope == f"//{clean_scope}"
                                    or cfg_scope.startswith(f"{clean_scope}/")
                                    or cfg_scope.startswith(f"//{clean_scope}/")
                                ):
                                    r_role = str(
                                        cdata.get("role_name")
                                        or cdata.get("role")
                                        or ""
                                    ).lower()
                                    if not target_role or r_role in [
                                        r.role_name.lower() for r in declared_roles
                                    ]:
                                        should_delete = True
                            except Exception:
                                pass
                            break
                    if not should_delete and (
                        item == sanitized_scope
                        or item.endswith(f"_{sanitized_scope}")
                    ):
                        should_delete = True

                    if should_delete:
                        _delete_dir(item_path)
                        reg.unregister_workspace(item_path, repo_root=root)
                        deleted_count += 1
                        deleted_paths.add(os.path.abspath(item_path))

        return deleted_count


def run_decommission_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="autofab decommission",
        description="Decommission and delete provisioned Cleanroom role workspaces for a scope.",
    )
    parser.add_argument(
        "scope",
        nargs="?",
        default="",
        help="Directory scope (e.g. staging).",
    )
    parser.add_argument(
        "target_role",
        nargs="?",
        default=None,
        help="Optional role boundary (e.g. qa).",
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
        default=None,
        help="Optional role boundary (alternative flag).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root directory.",
    )
    parsed = parser.parse_args(argv)
    target_input = parsed.scope_opt or parsed.scope or _get_dir_scope()
    if not target_input:
        print(
            "Error: Directory scope must be specified (e.g. uv run autofab decommission staging or staging#qa).",
            file=sys.stderr,
        )
        return 1
    scope, parsed_role, _ = parse_cleanroom_target(target_input)
    target_role = (
        (parsed.role_opt or parsed.target_role or parsed_role or "").strip().lower()
    )
    deleted = decommission_workspaces(
        scope, target_role=target_role or None, repo_root=parsed.repo_root
    )
    print(f"✔ Decommissioned {deleted} role workspace(s) for scope '{scope}'.")
    return 0


def print_autofab_help() -> None:
    print("""usage: autofab [-h] <command> ...

Autofab Multi-Agent Workspace & Role Tool

primary commands:
  clean                       Converge targets or scope clean using autonomous subagents
  mark-dirty                  Mark target or scope dirty in DAG storage

advanced & internal subagent tooling:
  work-queue                  Inspect DAG work queue for ready and blocked nodes
  mark-clean                  Mark target or scope clean in DAG metadata
  commission                  Commission an isolated role workspace
  decommission                Decommission and delete provisioned role workspaces
  refresh-sys                 Refresh system files, tools, configs, and guides across role workspaces
  get_work                    Get ready dirty tasks in workspace scope
  submit                      Verify and submit target with in-band header update
  blame                       Attribute feedback or blame critique to a target node or culprit file
  fail                        Record verification failure and force dirty state
  coverage                    Evaluate statement test coverage for a module
  check_files                 Run role-specific verification checks on target files
  change                      Record a change description on a target node or scope
  prompt                      Print task prompt for a target node or scope
  configure                   Configure global user environment (~/.config/autofab, model_configs.toml, credentials)
  install                     Prepare current workspace/repository for autofab execution
  install-antigravity-plugin  Install/refresh Autofab Antigravity plugin and agent definitions
  benchmark                   Run empirical model efficiency and verification benchmark suites

options:
  -h, --help                  show this help message and exit
""")


print_cleanroom_help = print_autofab_help


def _extract_unit_info(target_str: str, ws_root: str) -> tuple[str, str] | None:
    clean = target_str.replace("\\", "/").lstrip("/")
    if os.path.isabs(target_str):
        try:
            clean = os.path.relpath(target_str, ws_root).replace("\\", "/")
        except ValueError:
            pass
    parts = clean.split("/")
    base = os.path.splitext(os.path.basename(clean))[0]
    if base == "__init__":
        return None
    unit_name = base
    if unit_name.endswith("_fixed_test"):
        unit_name = unit_name[:-11]
    elif unit_name.endswith("_test"):
        unit_name = unit_name[:-5]
    elif unit_name.endswith("_pretense"):
        unit_name = unit_name[:-9]

    part_dir = ""
    if "parts" in parts:
        idx = parts.index("parts")
        if idx + 1 < len(parts):
            part_dir = "/".join(parts[: idx + 2])
    if not part_dir:
        part_dir = os.path.dirname(os.path.dirname(clean)) or "."
    return (part_dir, unit_name)


def _resolve_role_def_dynamically(
    role_name: str, ws_root: str, main_root: str | None
) -> Any:
    # First attempt: WorkspaceRegistry via lifecycle
    for cand_mod in (
        "autofab.parts.workspace.lib.role_registry",
        "parts.workspace.lib.role_registry",
        "role_registry",
    ):
        try:
            mod = importlib.import_module(cand_mod)
            from support.lib.lifecycle import enter_phase, get_singleton
            from autofab.parts.agent.lib import session as agent_session

            with enter_phase(agent_session.agent_session):
                reg = get_singleton(mod.WorkspaceRegistry)
                r_def = reg.resolve_role_definition(
                    role_name, repo_root=main_root or ws_root
                )
                if r_def and r_def.verify_template:
                    return r_def
        except Exception:
            pass

    # Fallback: parse roles configuration directly from workspace or repo root
    for root_cand in (ws_root, main_root):
        if not root_cand or not os.path.isdir(root_cand):
            continue
        cand_toml_paths: list[str] = []
        app_inf = _get_app_info()
        role_files = (
            app_inf.get_roles_filenames()
            if app_inf
            else ("autofab_roles.toml", "cleanroom_roles.toml")
        )
        for rname in role_files:
            direct = os.path.join(root_cand, rname)
            if os.path.isfile(direct):
                cand_toml_paths.append(direct)
            try:
                for sub in os.listdir(root_cand):
                    sub_cand = os.path.join(root_cand, sub, rname)
                    if os.path.isfile(sub_cand):
                        cand_toml_paths.append(sub_cand)
            except OSError:
                pass
        for toml_path in cand_toml_paths:
            if os.path.isfile(toml_path):
                try:
                    import tomllib

                    with open(toml_path, "rb") as tf:
                        tdata = tomllib.load(tf)
                    r_sec = tdata.get("roles", {}).get(role_name)
                    if r_sec:
                        from types import SimpleNamespace

                        return SimpleNamespace(
                            name=r_sec.get("name", role_name),
                            verify_template=r_sec.get("verify_template", ""),
                            active_component_types=r_sec.get(
                                "active_component_types", []
                            ),
                            src_pattern=r_sec.get("src_pattern", "")
                            or (
                                r_sec.get("src_patterns", [""])[0]
                                if r_sec.get("src_patterns")
                                else ""
                            ),
                            src_patterns=r_sec.get("src_patterns", []),
                            fused_roles=r_sec.get("fused_roles", []),
                            common_spec_roles=r_sec.get("common_spec_roles", []),
                            star_role_deps=r_sec.get("star_role_deps", []),
                            star_feedback_role_deps=r_sec.get(
                                "star_feedback_role_deps", []
                            ),
                            feedback_role_deps=r_sec.get("feedback_role_deps", []),
                        )
                except Exception:
                    pass
    return None


def run_verify_micro_binary(role_name: str, argv: list[str]) -> int:
    ws_root = os.getcwd()
    main_root = _find_main_repo_root()
    app_inf = _get_app_info()
    meta_p = None
    for desc_name in app_inf.get_role_descriptors():
        cand = os.path.join(ws_root, desc_name)
        if os.path.isfile(cand):
            meta_p = cand
            break
    fused_roles: list[str] = []
    d_scope = ""
    if meta_p and os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f)
                fused_roles = meta.get("fused_roles") or []
                d_scope = meta.get("dir_scope") or ""
        except Exception:
            pass

    raw_targets: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--threshold", "--pyi"):
            i += 2
            continue
        elif arg.startswith("--threshold=") or arg.startswith("--pyi="):
            i += 1
            continue
        elif arg in ("--impl", "--test", "--pretense"):
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                raw_targets.append(argv[i + 1])
                i += 2
                continue
            i += 1
            continue
        elif (
            arg.startswith("--impl=")
            or arg.startswith("--test=")
            or arg.startswith("--pretense=")
        ):
            raw_targets.append(arg.split("=", 1)[1])
            i += 1
            continue
        elif arg.startswith("-"):
            i += 1
            continue
        else:
            raw_targets.append(arg)
            i += 1

    target_units: list[tuple[str, str]] = []
    if raw_targets:
        for rt in raw_targets:
            full_rt = os.path.join(ws_root, rt) if not os.path.isabs(rt) else rt
            if os.path.isdir(full_rt):
                for root_d, _, files_d in os.walk(full_rt):
                    for fd in sorted(files_d):
                        if (
                            fd.endswith((".py", ".pyi"))
                            and not fd.startswith(".")
                            and fd != "__init__.py"
                        ):
                            u_info = _extract_unit_info(
                                os.path.join(root_d, fd), ws_root
                            )
                            if u_info and u_info not in target_units:
                                target_units.append(u_info)
            else:
                u_info = _extract_unit_info(rt, ws_root)
                if u_info and u_info not in target_units:
                    target_units.append(u_info)
    else:
        parts_p = (
            os.path.join(ws_root, d_scope, "parts")
            if d_scope
            else os.path.join(ws_root, "parts")
        )
        if not os.path.isdir(parts_p) and os.path.isdir(os.path.join(ws_root, "parts")):
            parts_p = os.path.join(ws_root, "parts")
        if os.path.isdir(parts_p):
            for p_dir in sorted(os.listdir(parts_p)):
                p_full = os.path.join(parts_p, p_dir)
                if not os.path.isdir(p_full) or p_dir.startswith("."):
                    continue
                part_rel = os.path.relpath(p_full, ws_root).replace(os.sep, "/")
                cand_files: set[str] = set()
                for sub in (
                    "low",
                    "lib",
                    "tests",
                    "pretense",
                    "lib_a",
                    "tests_a",
                    "lib_b",
                    "tests_b",
                ):
                    sub_d = os.path.join(p_full, sub)
                    if os.path.isdir(sub_d):
                        for f in os.listdir(sub_d):
                            if (
                                f.endswith((".py", ".pyi"))
                                and not f.startswith(".")
                                and f != "__init__.py"
                            ):
                                cand_files.add(f)
                for f in sorted(cand_files):
                    base = os.path.splitext(f)[0]
                    if base.endswith("_fixed_test"):
                        base = base[:-11]
                    elif base.endswith("_test"):
                        base = base[:-5]
                    elif base.endswith("_pretense"):
                        base = base[:-9]
                    pair = (part_rel, base)
                    if pair not in target_units:
                        target_units.append(pair)

    if not target_units:
        print(f"[OK] No targets found to verify for role '{role_name}'.")
        return 0

    # Resolve role definition dynamically
    r_def = _resolve_role_def_dynamically(role_name, ws_root, main_root)
    if not r_def and f"pretense_{role_name}" in fused_roles:
        r_def = _resolve_role_def_dynamically(
            f"pretense_{role_name}", ws_root, main_root
        )
    if not r_def and any("test" in r for r in fused_roles) and role_name == "pretense":
        r_def = _resolve_role_def_dynamically("test", ws_root, main_root)

    if not r_def:
        print(
            f"Error: Unknown role verification definition for '{role_name}'.",
            file=sys.stderr,
        )
        return 1

    cmd_tmpl = getattr(r_def, "verify_template", "") or ""
    if not cmd_tmpl or cmd_tmpl.strip().startswith("#"):
        print(f"[OK] No verification check required for role '{role_name}'.")
        return 0

    active_types = getattr(r_def, "active_component_types", []) or []
    src_pattern = getattr(r_def, "src_pattern", "") or ""
    src_patterns = getattr(r_def, "src_patterns", []) or (
        [src_pattern] if src_pattern else []
    )

    env = dict(os.environ)
    env["BUILD_WORKSPACE_DIRECTORY"] = ws_root
    if "UV_PROJECT" not in env and main_root and os.path.isdir(main_root):
        env["UV_PROJECT"] = main_root
    if "UV_CACHE_DIR" not in env:
        env["UV_CACHE_DIR"] = "/tmp/uv_cache"
    app_inf = _get_app_info()
    if app_inf and hasattr(app_inf, "assemble_cleanroom_pythonpath_str"):
        env["PYTHONPATH"] = app_inf.assemble_cleanroom_pythonpath_str(
            repo_root=main_root,
            ws_root=ws_root,
            existing_pythonpath=env.get("PYTHONPATH"),
        )
    else:
        pypaths = [ws_root]
        sup_lib = os.path.join(ws_root, "support", "lib")
        if os.path.isdir(sup_lib):
            pypaths.append(sup_lib)
        if main_root and os.path.isdir(main_root):
            pypaths.append(main_root)
        if "PYTHONPATH" in env:
            pypaths.extend(
                p for p in env["PYTHONPATH"].split(os.pathsep) if p and p not in pypaths
            )
        env["PYTHONPATH"] = os.pathsep.join(pypaths)

    verified_count = 0
    for part_dir, unit_name in target_units:
        # Classify component type: _impl is implementation, else interface
        ctype = "implementation" if unit_name.endswith("_impl") else "interface"
        if active_types and ctype not in active_types:
            continue

        target_display = f"{part_dir}/{unit_name}"
        if src_patterns:
            all_exist = True
            missing_files: list[str] = []
            for sp in src_patterns:
                expected_file = os.path.join(
                    ws_root, sp.format(unit_dir=part_dir, unit_name=unit_name)
                )
                if not os.path.isfile(expected_file):
                    all_exist = False
                    missing_files.append(
                        os.path.relpath(expected_file, ws_root).replace(os.sep, "/")
                    )
            if not all_exist:
                if len(missing_files) < len(src_patterns):
                    print(f"=== Verifying {role_name} on {target_display} ===")
                    print(
                        f"[FAIL] Missing companion file(s) for {target_display}: {', '.join(missing_files)}"
                    )
                    return 1
                continue

        formatted_cmd = cmd_tmpl.format(
            unit_dir=part_dir,
            unit_name=unit_name,
            max_failures=1,
            maxfail_arg="--maxfail=1",
        )
        if "run_cross_tests.py" in formatted_cmd and not os.path.isfile(
            os.path.join(ws_root, "bin", "run_cross_tests.py")
        ):
            cand_cross = (
                os.path.join(main_root, "bin", "run_cross_tests.py")
                if main_root
                else ""
            )
            if cand_cross and os.path.isfile(cand_cross):
                os.makedirs(os.path.join(ws_root, "bin"), exist_ok=True)
                shutil.copy2(
                    cand_cross, os.path.join(ws_root, "bin", "run_cross_tests.py")
                )
        print(f"=== Verifying {role_name} on {target_display} ===")
        res = subprocess.run(
            formatted_cmd,
            shell=True,
            cwd=ws_root,
            env=env,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(
                f"[FAIL] Verification failed for {target_display} ({role_name}):\n{res.stdout}\n{res.stderr}".strip()
            )
            spec_roles = list(
                getattr(r_def, "common_spec_roles", None)
                or getattr(r_def, "star_role_deps", None)
                or []
            )
            resolved_specs: list[str] = []
            base_unit = unit_name[:-5] if unit_name.endswith("_impl") else unit_name
            for s_role in spec_roles:
                s_def = _resolve_role_def_dynamically(s_role, ws_root, main_root)
                if not s_def or not getattr(s_def, "src_pattern", ""):
                    continue
                cands = [
                    s_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name)
                ]
                if base_unit != unit_name:
                    cands.append(
                        s_def.src_pattern.format(unit_dir=part_dir, unit_name=base_unit)
                    )
                found_any = False
                for c in cands:
                    full_ws = os.path.join(ws_root, c) if not os.path.isabs(c) else c
                    full_repo = (
                        os.path.join(main_root, c)
                        if (main_root and not os.path.isabs(c))
                        else None
                    )
                    if os.path.isfile(full_ws):
                        rel = os.path.relpath(full_ws, ws_root)
                        if rel not in resolved_specs:
                            resolved_specs.append(rel)
                        found_any = True
                    elif full_repo and os.path.isfile(full_repo):
                        rel = os.path.relpath(full_repo, main_root) if main_root else c
                        if rel not in resolved_specs:
                            resolved_specs.append(rel)
                        found_any = True
                if not found_any and cands:
                    if cands[0] not in resolved_specs:
                        resolved_specs.append(cands[0])

            spec_desc = (
                ", ".join(resolved_specs)
                if resolved_specs
                else "the common specification"
            )

            if "coverage" in role_name:
                print(
                    "\n" + "=" * 80 + "\n"
                    "[COVERAGE ARBITER REMINDER - EXPLAIN FEEDBACK IN TERMS OF SPECIFICATION]\n"
                    f"• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification ({spec_desc}).\n"
                    "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
                    "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
                    "• Translate uncovered statements and branches into missing specification requirements or scenario cases.\n"
                    "• If an uncovered branch is an unreachable defensive check or caller assumption guaranteed by the specification, instruct the implementation author to prune it or mark it as unreachable according to the methodology.\n"
                    + "="
                    * 80
                )
            elif "qa" in role_name:
                print(
                    "\n" + "=" * 80 + "\n"
                    "[QA ARBITER REMINDER - EXPLAIN DEFECTS IN TERMS OF SPECIFICATION]\n"
                    f"• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification ({spec_desc}).\n"
                    "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
                    "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
                    "• Frame test failures strictly as contract discrepancies against the specification.\n"
                    "• Explain the expected postcondition outcome versus the observed behavior.\n"
                    "• Checked preconditions raising contracted errors (*Error) MUST be tested (via assertRaises in tests or self.checked.violating() in pretense scenarios) to verify the error is raised. However, tests must never assert graceful returns on precondition violations, and cannot assert state after an error because system state after an exception is undefined. Preconditions without errors define undefined behavior and are untestable.\n"
                    + "="
                    * 80
                )
            return res.returncode
        else:
            if res.stdout.strip():
                print(res.stdout.strip())
            print(f"[OK] Verification passed for {target_display} ({role_name}).")
            verified_count += 1

    if verified_count == 0:
        print(f"[OK] No applicable component targets to verify for role '{role_name}'.")
    return 0


def run_verify_fused_cli(argv: list[str]) -> int:
    app_inf = _get_app_info()
    if argv and argv[0] in ("-h", "--help"):
        print(
            f"usage: {app_inf.APP_NAME} verify-fused [workspace_dir]\n\nVerify all constituent roles in a fused role workspace."
        )
        return 0
    ws_dir = os.path.abspath(argv[0] if argv else os.getcwd())
    meta_p = None
    for desc_name in app_inf.get_role_descriptors():
        cand = os.path.join(ws_dir, desc_name)
        if os.path.isfile(cand):
            meta_p = cand
            break
    if not meta_p:
        print(f"Error: Not a role workspace: {ws_dir}", file=sys.stderr)
        return 1

    with open(meta_p, "r", encoding="utf-8") as f:
        meta = json.load(f)

    fused_roles = meta.get("fused_roles") or []
    if not fused_roles:
        print(
            f"Error: Workspace at {ws_dir} is not a fused role workspace.",
            file=sys.stderr,
        )
        return 1

    for r in fused_roles:
        print(f"[VERIFY-FUSED] Verifying constituent role '{r}' in {ws_dir}...")
        orig_cwd = os.getcwd()
        try:
            os.chdir(ws_dir)
            code = run_verify_micro_binary(r, [])
            if code != 0:
                print(
                    f"[FAIL] Fused verification failed for role '{r}' in {ws_dir}.",
                    file=sys.stderr,
                )
                return code
        finally:
            os.chdir(orig_cwd)

    print(f"[OK] All fused role verifications passed in {ws_dir}.")
    return 0


def run_harvest_fused_cli(argv: list[str]) -> int:
    app_inf = _get_app_info()
    if argv and argv[0] in ("-h", "--help"):
        print(
            f"usage: {app_inf.APP_NAME} harvest-fused [workspace_dir]\n\nHarvest verified implementation files from a fused role workspace into the main repository."
        )
        return 0
    ws_dir = os.path.abspath(argv[0] if argv else os.getcwd())
    meta_p = None
    for desc_name in app_inf.get_role_descriptors():
        cand = os.path.join(ws_dir, desc_name)
        if os.path.isfile(cand):
            meta_p = cand
            break
    if not meta_p:
        print(f"Error: Not a role workspace: {ws_dir}", file=sys.stderr)
        return 1

    with open(meta_p, "r", encoding="utf-8") as f:
        meta = json.load(f)

    fused_roles = meta.get("fused_roles") or []
    dir_scope = meta.get("dir_scope") or meta.get("parts_dir", "")
    main_root = _find_main_repo_root()
    if not main_root or main_root == ws_dir:
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) in app_inf.get_role_workspaces_containers():
            main_root = os.path.dirname(parent)
        else:
            main_root = os.getcwd()

    parts_p = (
        os.path.join(ws_dir, dir_scope, "parts")
        if dir_scope
        else os.path.join(ws_dir, "parts")
    )
    if not os.path.isdir(parts_p) and os.path.isdir(os.path.join(ws_dir, "parts")):
        parts_p = os.path.join(ws_dir, "parts")

    harvested_files: list[str] = []
    if os.path.isdir(parts_p):
        for root, dirs, files in os.walk(parts_p):
            for f in files:
                if f.endswith((".py", ".pyi", ".md")) and not f.startswith("."):
                    rel = os.path.relpath(os.path.join(root, f), ws_dir).replace(
                        os.sep, "/"
                    )
                    is_constituent = False
                    for r in fused_roles:
                        if f"/{r}/" in f"/{rel}/" or (
                            r == "test" and "/tests/" in f"/{rel}/"
                        ):
                            is_constituent = True
                            break
                    if not is_constituent and (
                        "lib/" in rel
                        or "tests/" in rel
                        or "pretense/" in rel
                        or "lib_a/" in rel
                        or "tests_a/" in rel
                        or "lib_b/" in rel
                        or "tests_b/" in rel
                    ):
                        is_constituent = True

                    if is_constituent:
                        src_f = os.path.join(ws_dir, rel)
                        main_scope = str(meta.get("main_dir_scope") or "").strip("/")
                        ws_scope = str(meta.get("dir_scope") or "").strip("/")
                        main_rel = rel
                        if (
                            main_scope
                            and ws_scope
                            and main_scope != ws_scope
                            and rel.startswith(ws_scope + "/")
                        ):
                            main_rel = main_scope + "/" + rel[len(ws_scope) + 1 :]
                        dst_f = os.path.join(main_root, main_rel)
                        os.makedirs(os.path.dirname(dst_f), exist_ok=True)
                        shutil.copy2(src_f, dst_f)
                        os.chmod(dst_f, 0o644)

                        if f != "__init__.py":
                            src_metadata = None
                            for mod_cand in (
                                "autofab.parts.metadata.lib.src_metadata",
                                "parts.metadata.lib.src_metadata",
                                "src_metadata",
                            ):
                                try:
                                    src_metadata = importlib.import_module(mod_cand)
                                    break
                                except Exception:
                                    pass

                            if src_metadata:
                                src_metadata.record_change(
                                    dst_f, "Fused role implementation and verification"
                                )
                                for c_role in fused_roles:
                                    if (
                                        "qa" in c_role
                                        or "coverage" in c_role
                                        or "audit" in c_role
                                    ):
                                        src_metadata.stamp_audit(dst_f, c_role)
                                src_metadata.mark_clean(dst_f)
                                src_metadata.update_metadata(dst_f, clear_dirty=True)
                            harvested_files.append(rel)

    print(f"[OK] Harvested {len(harvested_files)} files from {ws_dir} to {main_root}:")
    for hf in harvested_files:
        print(f"  - {hf}")
    return 0


def main(argv: list[str] | None = None) -> int:
    discovered_pkgs: list[str] = []
    for _r in _get_roots():
        if not os.path.isdir(_r):
            continue
        try:
            for _entry in os.listdir(_r):
                if _dir_scope and _entry == _dir_scope:
                    continue
                if not _entry.startswith((".", "bazel-", "venv")):
                    if os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                        if _entry not in discovered_pkgs:
                            discovered_pkgs.append(_entry)
        except OSError:
            pass

    for _pkg in list(dict.fromkeys(discovered_pkgs + ["autofab", "parts"])):
        for sub in (
            "systems.lib.autofab_asm",
            "core.lib.file_paths_impl",
            "control.lib.control_asm",
            "metadata.lib.metadata_asm",
            "workspace_cli.lib.workspace_cli_asm",
            "workspace_cli.lib.cli_tool_impl",
            "workspace.lib.workspace_asm",
            "subagent.lib.subagent_asm",
            "subagent.lib.subagent_tool_impl",
            "antigravity.lib.antigravity_asm",
            "dsh.lib.dsh_asm",
        ):
            for mod_path in (f"{_pkg}.parts.{sub}", f"parts.{sub}"):
                try:
                    mod = importlib.import_module(mod_path)
                    if hasattr(mod, "__initialize__"):
                        mod.__initialize__()
                except Exception:
                    pass

    args_list = list(argv) if argv is not None else sys.argv[1:]
    if "--repo-root" in args_list:
        try:
            rr_idx = args_list.index("--repo-root")
            if rr_idx + 1 < len(args_list):
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(
                    args_list[rr_idx + 1]
                )
        except (ValueError, IndexError):
            pass
    # Re-install agent files each time CLI is executed at repo level
    # Skip inside isolated role workspaces or when running worker verification tools
    app_inf = _get_app_info()
    is_role_ws = bool(
        any(
            os.path.isfile(os.path.join(os.getcwd(), desc))
            for desc in app_inf.get_role_descriptors()
        )
        or os.environ.get(f"{app_inf.ENV_PREFIX}_ROLE_WORKSPACE")
        or os.environ.get("CLEANROOM_ROLE_WORKSPACE")
    )
    cmd_0 = args_list[0] if args_list else ""
    is_worker_cmd = bool(
        cmd_0
        in (
            "coverage",
            "check_files",
            "check-files",
            "get_work",
            "get-work",
            "submit",
            "blame",
            "fail",
            "status",
            "verify-fused",
            "verify_fused",
            "harvest-fused",
            "harvest_fused",
            "revert",
            "checkpoint",
        )
        or cmd_0.startswith("verify_")
        or cmd_0.startswith("verify-")
    )

    if not args_list or args_list[0] in ("-h", "--help", "help"):
        print_autofab_help()
        return 0 if args_list else 1

    if args_list[0] == "configure":
        return configure_user_environment()

    if args_list[0] == "install":
        return install_workspace()

    if args_list[0] == "install-antigravity-plugin":
        p = ensure_antigravity_plugin_installed()
        print(
            f"[OK] Autofab Antigravity plugin and agent definitions installed at: {p}"
        )
        return 0

    if args_list[0] == "work-queue":
        return run_work_queue(args_list[1:])

    if args_list[0] == "mark-dirty":
        return run_mark_dirty_cli(args_list[1:])

    if args_list[0] == "mark-clean":
        return run_mark_clean_cli(args_list[1:])

    if args_list[0] == "change":
        return run_change_cli(args_list[1:])

    if args_list[0] == "prompt":
        return run_prompt_cli(args_list[1:])

    if args_list[0] == "blame":
        return run_blame_cli(args_list[1:], prog="autofab blame")

    if args_list[0] == "reject":
        return run_reject_cli(args_list[1:], prog="autofab reject")

    if args_list[0] == "clean":
        return run_clean(args_list[1:])

    if args_list[0] == "benchmark":
        return run_benchmark_cli(args_list[1:])

    if args_list[0] == "commission":
        return run_commission_cli(args_list[1:])

    if args_list[0] == "decommission":
        return run_decommission_cli(args_list[1:])

    if args_list[0] in ("verify-fused", "verify_fused"):
        return run_verify_fused_cli(args_list[1:])

    if args_list[0] in ("harvest-fused", "harvest_fused"):
        return run_harvest_fused_cli(args_list[1:])

    if args_list[0].startswith("verify_") or args_list[0].startswith("verify-"):
        sub_role = args_list[0][7:]
        if sub_role not in ("fused",):
            return run_verify_micro_binary(sub_role, args_list[1:])

    assert cli_tool_impl is not None
    try:
        from autofab.parts.workspace.lib import workspace_asm

        workspace_asm.__initialize__()
    except Exception:
        try:
            from parts.workspace.lib import workspace_asm

            workspace_asm.__initialize__()
        except Exception:
            pass
    return cli_tool_impl.main(argv)


if __name__ == "__main__":
    sys.exit(main())
