#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents."""
from __future__ import annotations
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence

def _find_main_repo_root() -> str | None:
    main_root = os.environ.get("CLEANROOM_MAIN_ROOT")
    if main_root and os.path.isdir(main_root):
        return main_root
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        cfg = os.path.join(curr, ".cleanroom_role.json")
        if os.path.isfile(cfg):
            parent = os.path.dirname(curr)
            if os.path.basename(parent) == "role_workspaces":
                p_root = os.path.dirname(parent)
                ws_base = os.path.basename(curr)
                try:
                    for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                        if entry != "role_workspaces" and ws_base.startswith(f"{entry}_"):
                            cand = os.path.join(p_root, entry)
                            if os.path.isdir(cand):
                                return cand
                except OSError:
                    pass
            break
        if os.path.isfile(os.path.join(curr, "cleanroom.toml")) or os.path.isfile(os.path.join(curr, "pyproject.toml")):
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
    if repo_root:
        for pkg in ("update_with_ai", "update_python_with_ai", ""):
            cand = os.path.join(repo_root, pkg, "support", "lib", "app_info.py")
            if os.path.isfile(cand):
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("support_lib_app_info", cand)
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
            # In an isolated role workspace, curr is the sole root. Main root is isolated from sys.path.
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
                        _cand_tool = os.path.join(_r, _entry, "parts", _sub, "lib", "cli_tool_impl.py")
                        if os.path.isfile(_cand_tool) and os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                            try:
                                cli_tool_impl = importlib.import_module(f"{_entry}.parts.{_sub}.lib.cli_tool_impl")
                            except ImportError:
                                pass
                    if commands_impl is None:
                        _cand_cmds = os.path.join(_r, _entry, "parts", _sub, "lib", "commands_impl.py")
                        if os.path.isfile(_cand_cmds) and os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                            try:
                                commands_impl = importlib.import_module(f"{_entry}.parts.{_sub}.lib.commands_impl")
                            except ImportError:
                                pass
                    if pending_impl is None:
                        _cand_pend = os.path.join(_r, _entry, "parts", _sub, "lib", "pending_impl.py")
                        if os.path.isfile(_cand_pend) and os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                            try:
                                pending_impl = importlib.import_module(f"{_entry}.parts.{_sub}.lib.pending_impl")
                            except ImportError:
                                pass
                if cli_tool_impl is not None and commands_impl is not None and pending_impl is not None:
                    break
    except OSError:
        pass
    if cli_tool_impl is not None and commands_impl is not None and pending_impl is not None:
        break

if cli_tool_impl is None:
    try:
        from update_with_ai.parts.workspace_cli.lib import cli_tool_impl
    except ImportError:
        try:
            cli_tool_impl = importlib.import_module("update_with_ai.parts.workspace.lib.cli_tool_impl")
        except ImportError:
            pass

if commands_impl is None:
    try:
        from update_with_ai.parts.workspace_cli.lib import commands_impl
    except ImportError:
        pass

if pending_impl is None:
    try:
        from update_with_ai.parts.workspace_cli.lib import pending_impl
    except ImportError:
        pass

if cli_tool_impl is None:
    raise ImportError("Failed to locate cli_tool_impl module across discovered Cleanroom roots")

cleanroom_uv_runner = None
try:
    import cleanroom_uv_runner
except ImportError:
    try:
        from update_with_ai.support.lib import cleanroom_uv_runner
    except ImportError:
        try:
            from update_python_with_ai.support.lib import cleanroom_uv_runner
        except ImportError:
            pass

AUDIT_BUFFER_FILE = getattr(commands_impl, "AUDIT_BUFFER_FILE", ".cleanroom_audit_buffer.json")
BLAME_BUFFER_FILE = getattr(commands_impl, "BLAME_BUFFER_FILE", ".cleanroom_blame_buffer.json")
PENDING_WORK_FILE = getattr(commands_impl, "PENDING_WORK_FILE", ".cleanroom_pending_work.json")


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


def copy_file_with_perms(src: str, dst: str, readonly: bool = False, executable: bool = False) -> None:
    from support.lib.lifecycle import get_singleton
    from update_with_ai.parts.workspace.lib import provision
    get_singleton(provision.WorkspaceProvisioner).copy_file_with_permissions(
        src, dst, readonly=readonly, executable=executable
    )


def compute_role_work_queue(role_name: str, dir_scope: str, repo_root: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = repo_root or find_workspace_root()
    from support.lib.lifecycle import get_singleton
    from update_with_ai.parts.workspace_cli.lib import work
    work = get_singleton(work.WorkspaceWorkManager)
    ready, blocked = work.compute_role_work_queue(role_name, dir_scope=dir_scope, repo_root=root)

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


def is_auditor_role(role_name: str, repo_root: str | None = None, dir_scope: str | None = None) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    from support.lib.lifecycle import get_singleton
    from update_with_ai.parts.workspace.lib import role_registry
    reg = get_singleton(role_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(r_def.audit_tag or not r_def.src_pattern)


def resolve_cleanroom_log_path(role_name: str, repo_root: str | None = None, dir_scope: str | None = None) -> str:
    assert commands_impl is not None
    return commands_impl.resolve_cleanroom_log_path(role_name, repo_root=repo_root)


def append_cleanroom_log(role_name: str, line: str, repo_root: str | None = None, dir_scope: str | None = None) -> None:
    assert commands_impl is not None
    commands_impl.append_cleanroom_log(role_name, line, repo_root=repo_root)


def _get_pending_manager():
    from update_with_ai.parts.workspace_cli.lib import pending
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
   - `run_command` (used to run `uv run cleanroom work-queue <scope> [role] --json` and `uv run cleanroom decommission <scope>`)
   - `invoke_subagent` (used to dispatch `cleanroom_worker` subagents)
   - `send_message` (used to wake/message subagents or report to parent)
   - `manage_subagents` (used to list active workers or clean them up)
   - `define_subagent` (used to define `cleanroom_worker` if not already discovered)
2. ZERO CODE CUSTODY: You have no file viewing or editing tools. You have zero authority over source code.
3. ZERO EXPLORATORY SEARCHING: Never run find, grep, git diff, or directory tree walks. Do NOT inspect source files.
4. INSTANT QUEUE EVALUATION:
   To evaluate the DAG queue, execute the binary:
   ```bash
   uv run cleanroom work-queue <scope> [role] --json
   ```
   (Note: if the prompt specifies `up to <role>`, `<scope>#<role>`, or a fused role like `baseline` or `pretense_baseline`, pass `<role>` as the second positional argument or `--role <role>`).
   Parse the returned JSON to determine ready roles and targets, and retrieve role workspace directories from `workspace_dirs`. If `is_clean` is true, proceed to step 9!
5. DISPATCH OR WAKE WORKSPACE-BOUND ROLE WORKERS:
   For each role with ready nodes in the queue:
   - Check active subagents using `manage_subagents` with action `list`.
   - Obtain the workspace directory for the role from `workspace_dirs[<role>]`.
   - If the role is a fused role (e.g. `baseline` or `pretense_baseline`), instruct the worker to run `bin/get_work` once at start, consult its workspace `AGENTS.md` and `guides/`, verify via its provisioned `bin/verify_*` micro-binaries, and report `COMPLETED` via `send_message` when done (without calling `bin/submit` or `bin/check_files`).
   - If an active worker for that role already exists, wake it using `send_message`:
     "Ready nodes detected in global DAG. Your assigned role workspace directory is '<workspace_dir>'. Set Cwd to '<workspace_dir>' for all tool calls. Immediately run bin/get_work to acquire pending ready nodes. Consult your workspace AGENTS.md and role guide, perform role verification (via bin/check_files for standard roles, or bin/verify_* micro-binaries for fused roles), resolve nodes (via bin/submit, bin/blame, or bin/fail for standard roles, or report COMPLETED for fused roles), and drain all ready nodes before completing. If success is impossible, run bin/fail <target> '<reason>' and report FAILED: <target> - <reason>."
   - If no active worker for that role exists, spawn it via `invoke_subagent`:
     - TypeName: "cleanroom_worker"
     - Role: "Cleanroom <Role> Worker"
     - Model: "<antigravity_models[<role>]>" (MUST use `antigravity_models[<role>]` from `work-queue --json`: e.g. `"flash"` when `gemini-flash` is specified, `"flash_lite"` when `flash-lite` is specified, `"pro"` when `pro` is specified, and `"inherit"` when `gemini-argon` is specified since Antigravity does not expose Argon directly for subagents)
     - Prompt: "You are an autonomous Cleanroom '<role>' worker for scope '<scope>'. Your assigned role workspace directory is '<workspace_dir>'. You must operate strictly inside your assigned role workspace directory, setting Cwd to '<workspace_dir>' for all tool calls. You may use standard shell commands (cat, grep, find, etc.) and native tools strictly within your workspace, but all target verification and round resolution must proceed through the prescribed bin/ executables in your workspace (consult AGENTS.md). Immediately run bin/get_work to acquire pending ready nodes. Consult your workspace AGENTS.md and companion guides in guides/, perform role verification (bin/check_files for standard roles; bin/verify_* micro-binaries for fused roles), resolve nodes (bin/submit, bin/blame, or bin/fail for standard roles; or report COMPLETED via send_message for fused roles without calling bin/submit), and drain all ready nodes before completing. If success is impossible or an unresolvable impasse occurs, execute bin/fail <target> '<reason>' and report FAILED: <target> - <reason>."
   - (Note: if `invoke_subagent` reports cleanroom_worker not found, call `define_subagent` with name "cleanroom_worker", write tools enabled, and retry).
6. REACTIVE SLEEP:
   After dispatching or waking the ready role workers, STOP calling tools and wait for worker completion messages. Do NOT poll, loop, or sleep.
7. HANDLE WORKER MESSAGES:
   - If a message from any worker reports a failure (`FAILED: <target> - <reason>`):
     1. Stop the convergence loop immediately.
     2. Clean up all workers: `manage_subagents(Action="kill_all")`.
     3. Escalate the failure directly to your parent/user:
        "Cleanroom convergence aborted: Worker for role '<role>' failed target '<target>' with reason: <reason>"
   - When a worker reports completion:
     - Check if the worker is executing in a fused role workspace (e.g. role is `baseline` or `pretense_baseline`, or `.cleanroom_role.json` in `workspace_dir` has `fused_roles`).
     - If it is a fused worker:
       1. Run formal verification:
          `uv run cleanroom verify-fused <workspace_dir>`
       2. If verification fails:
          Send diagnostic failure feedback to worker via `send_message`:
          "Fused verification failed:\n<diagnostics>\nPlease fix these issues in your workspace ('<workspace_dir>'), re-verify using your workspace bin/verify_* micro-binaries, and send COMPLETED when ready."
          Track retry count (enforce a hardcoded maximum of 3 retries). If failures persist after 3 retries, abort with failure.
       3. If verification passes:
          Run atomic harvest to mark all constituent targets clean:
          `uv run cleanroom harvest-fused <workspace_dir>`
     - Re-run `uv run cleanroom work-queue <scope> [role] --json`.
8. ITERATE TO CONVERGENCE:
   Repeat step 4-7 until `is_clean` is true and all nodes evaluate clean.
9. FINAL CLEANUP & REPORT:
   Once `is_clean` is true:
   - Clean up workers using `manage_subagents(Action="kill_all")`.
   - Decommission role workspaces via run_command:
     `uv run cleanroom decommission <scope> [role]`
   - Send completion message back to parent:
     "Scope '<scope>' converged clean across all roles (up to '<role>'). All provisioned role workspaces decommissioned."
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

## PERMITTED TOOLS & SHELL COMMANDS:
You are fully permitted to run standard shell utilities and scripts (`cat`, `grep`, `find`, `python`, etc.) or native tools strictly WITHIN your assigned role workspace directory (`.`) to inspect files, run local diagnostics, and complete your tasks.
Git operations (`git checkout`, `git restore`, `git reset`, etc.) and accessing files outside your workspace remain strictly prohibited.

## MANDATORY WORKFLOW BINARIES:
All Cleanroom target resolution must proceed through the prescribed workspace binaries in `bin/`:
- Standard Role Workspaces: `bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`
- Fused Role Workspaces: `bin/get_work` (call ONCE at session start), `bin/verify_*` (for each constituent role), `bin/fail`

## UNRESOLVABLE IMPASSE & FAILURE PROTOCOL:
If you determine that success is not possible (e.g. unreachable code under test, contradictory specification contracts, or dead ends that blame cannot resolve):
1. DO NOT attempt ad-hoc debugging, script execution, or reverse-engineering of cleanroom tools.
2. Execute: `bin/fail <target_file> "<reason>"`
3. Report failure immediately to the coordinator via `send_message`:
   `FAILED: <target_file> - <reason>`
4. Cease work immediately.

## RESOLVING BLAME & FEEDBACK:
- `bin/check_files` ONLY checks static syntax and types. It does NOT run tests.
- When an active node carries unacted feedback or blame from downstream roles (QA), passing `bin/check_files` does NOT mean the defect is resolved.
- You MUST inspect `low/*.pyi` and `tests/*_test.py`, modify code logic to satisfy contracts and pass tests, ensure `bin/check_files` passes, and submit with a change summary describing how the feedback was fixed.

## METADATA PROJECTION & INVIOLABILITY:
- NEVER manually edit `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools (`bin/submit`, `bin/blame`, `bin/fail`).
- Files in your role workspace are projected to intentionally omit `LAST_CLEANED`, `LAST_CHANGED`, and audit timestamps. Canonical lifecycle timestamps are maintained exclusively in the main repository and managed by `bin/submit` (or `cleanroom harvest-fused`).
- Never attempt to manually add `LAST_CLEANED` or `LAST_CHANGED` to local workspace files, and never treat missing lifecycle timestamps in local workspace files as a defect.
- If `bin/get_work` assigns a target, perform thorough semantic verification against contracts and test suites rather than assuming it is clean just because static syntax and type checks pass.

## STANDARD WORKFLOW:
1. Run `bin/get_work` to acquire pending ready nodes and review unacted feedback.
   - Note: If `bin/get_work` outputs a `[CRITICAL MODEL MISMATCH]` error (because `gemini-argon` was requested via `inherit` while Antigravity is running a different model), DO NOT proceed. Immediately send `FAILED: <scope> - <exact error message instructing the user to manually switch their model to "Gemini Argon" before requesting the run again>` to the coordinator via `send_message` and stop.
2. Consult your workspace `AGENTS.md` and companion guide(s) in `guides/` to perform role duties.
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
name: cleanroom_baseline_worker
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

You are an autonomous software developer working directly on code and test implementation within an assigned Cleanroom workspace.
Your goal is to implement required code, author comprehensive verification suites, and verify that all checks pass and code is clean—all within this single round.

## AUTHORITATIVE INSTRUCTIONS:
Your workspace contains an `AGENTS.md` file in its root directory generated specifically for your assigned role and scope.
You MUST read and follow `AGENTS.md` as your primary operational guide for target paths, verification commands, and completion protocols.

## PERMITTED TOOLS & SHELL COMMANDS:
You are equipped with standard software development tools:
- Shell / terminal commands (`run_command`) strictly WITHIN your assigned role workspace directory (`.`).
- File viewing / reading (`view_file`, `cat`, etc.)
- File editing / writing (`write_to_file`, `replace_file_content`, `multi_replace_file_content`)
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


def ensure_antigravity_plugin_installed() -> str:
    """Installs or refreshes Cleanroom agents in global Antigravity plugin directory."""
    app_info = _get_app_info()
    app_name = app_info.APP_NAME if app_info else "cleanroom"
    config_root = os.environ.get("ANTIGRAVITY_CONFIG_DIR") or os.path.expanduser("~/.gemini/config")
    plugin_dir = os.path.join(config_root, "plugins", app_name)
    agents_dir = os.path.join(plugin_dir, "agents")
    coord_dir = os.path.join(agents_dir, f"{app_name}_coordinator")
    worker_dir = os.path.join(agents_dir, f"{app_name}_worker")
    baseline_worker_dir = os.path.join(agents_dir, f"{app_name}_baseline_worker")

    # If legacy skills directory exists, remove it
    legacy_skills_dir = os.path.join(plugin_dir, "skills")
    if os.path.isdir(legacy_skills_dir):
        shutil.rmtree(legacy_skills_dir, ignore_errors=True)

    os.makedirs(coord_dir, exist_ok=True)
    os.makedirs(worker_dir, exist_ok=True)
    os.makedirs(baseline_worker_dir, exist_ok=True)

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

    with open(os.path.join(baseline_worker_dir, "agent.md"), "w", encoding="utf-8") as f:
        f.write(BASELINE_WORKER_AGENT_MD.strip() + "\n")

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

    if not agentapi_cmd:
        return False

    prompt = f"Clean all dirty nodes in {target_display} using cleanroom_coordinator."

    if mode == "message":
        if not conv_id:
            return False
        cmd = list(agentapi_cmd) + [
            "send-message",
            f"--title=Cleanroom Coordination [{target_display}]",
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
            f"--title=Cleanroom Coordinator: {target_display}",
            "--",
            prompt,
        ]
    else:
        return False

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
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
            print(f"[Antigravity Desktop IPC] Warning: agentapi failed (code {res.returncode}): {err}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[Antigravity Desktop IPC] Warning: agentapi invocation failed: {e}", file=sys.stderr)
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
    candidates.extend([
        os.path.join(home, "Library", "Application Support", "dsh-desktop", "harness", "skills"),
        os.path.join(home, ".config", "dsh-desktop", "harness", "skills"),
        os.path.join(home, ".local", "share", "dsh-desktop", "harness", "skills"),
    ])
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "dsh-desktop", "harness", "skills"))

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
   This prepares the role workspace at `../role_workspaces/<ws>_<role>_<scope>/` with its internal tools (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`).

3. **Dispatch Role Subagent**:
   Call the DSH native `subagent` tool:
   - `description`: `[<ROLE>] <scope> worker`
   - `prompt`:
     ```text
     You are the <role> worker for scope <scope>.
     Your assigned workspace is: ../role_workspaces/<ws>_<role>_<scope>
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
  uv run {app_name} orchestrate <dir_scope> [target_role] --harness dsh
  ```
- To run tests: `bin/test`
"""
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    return skill_file


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
        scope = segs[0] if segs else raw
        if not is_unit and len(segs) >= 2 and "." in segs[-1]:
            is_unit = True
            if not role and len(segs) >= 3:
                folder = segs[-2]
                folder_map = {
                    "high": "high", "planning": "planning", "scenarios": "scenario",
                    "scenario": "scenario", "low": "low", "lib": "lib",
                    "tests": "test", "test": "test",
                }
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
                folder_map = {
                    "high": "high", "planning": "planning", "scenarios": "scenario",
                    "scenario": "scenario", "low": "low", "lib": "lib",
                    "tests": "test", "test": "test"
                }
                role = folder_map.get(folder, role)
        return scope, role, is_unit

    # 3. Simple scope or scope#role
    scope = segs[0] if segs else raw
    return scope, role, False


def resolve_default_model(repo_root: str | None = None, harness: str | None = None) -> str | None:
    """Resolves default model profile name from model_configs.toml if present.
    Checks harness-specific defaults first (e.g. loop_default, antigravity_default, dsh_default),
    then falls back to the top-level 'default' key.
    """
    root = repo_root or find_workspace_root()
    import tomllib
    app_info = _get_app_info()
    candidates = [
        os.path.join(root, "model_configs.toml"),
        os.path.join(os.path.dirname(root), "model_configs.toml"),
    ]
    if app_info:
        candidates.extend([
            os.path.join(root, app_info.DEFAULT_CONFIG_FILE),
            app_info.get_user_model_config_file(),
        ])
    else:
        candidates.extend([
            os.path.join(root, "cleanroom.toml"),
            os.path.expanduser("~/.config/cleanroom/model_configs.toml"),
        ])
    for cand in candidates:
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    data = tomllib.load(f)
                    if harness:
                        h_clean = harness.strip().lower()
                        if h_clean in ("deepseek", "deepseek-harness"):
                            h_clean = "dsh"
                        val = data.get(f"{h_clean}_default") or data.get(f"default_{h_clean}")
                        if isinstance(val, str) and val.strip():
                            return val.strip()
                        defs_sec = data.get("defaults")
                        if isinstance(defs_sec, dict):
                            val = defs_sec.get(h_clean)
                            if isinstance(val, str) and val.strip():
                                return val.strip()
                    val = data.get("default")
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            except Exception:
                pass
    return None


def configure_user_environment() -> int:
    """Prepares the user environment (global ~/.config/cleanroom setup)."""
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

    print(f"\n[SUCCESS] Environment configured. You can edit credentials and model configurations in:\n  {cfg_dir}")
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
            f.write(f'# {cfg_name}\n# Project-level configuration for {app_name}\n\n')
        print(f"[OK] Initialized project configuration at: {cfg_path}")
    else:
        print(f"[INFO] Project configuration already exists at: {cfg_path}")

    gitignore_path = os.path.join(root, ".gitignore")
    patterns_to_ignore = [
        "role_workspaces/",
        ".role_workspaces/",
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
    target_role: str | None = None,
) -> str | None:
    if explicit_pretense:
        return "pretense"
    if target_role and "pretense" in target_role.lower():
        return "pretense"

    root = repo_root or find_workspace_root()

    # 1. Check active flight metadata
    flight_file = os.path.join(root, ".cleanroom", "active_flight.json")
    if os.path.isfile(flight_file):
        try:
            with open(flight_file, "r", encoding="utf-8") as f:
                fdata = json.load(f)
            if fdata.get("flight_scope") == scope:
                if fdata.get("pretense") or "pretense" in str(fdata.get("flight_id", "")):
                    return "pretense"
        except Exception:
            pass

    # 2. Check cleanroom.toml in scope or parts
    import tomllib
    scope_clean = scope.lstrip("/").rstrip("/")
    curr = os.path.join(root, scope_clean)
    for sub in ("parts", ""):
        cand_dir = os.path.join(curr, sub) if sub else curr
        cand = os.path.join(cand_dir, "cleanroom.toml")
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
    parser.add_argument(
        "--pretense",
        action="store_true",
        help="Inspect work queue for Pretense pipeline.",
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
        print("Error: Directory scope must be specified (e.g. uv run cleanroom work-queue staging or staging#qa).", file=sys.stderr)
        return 1

    scope, parsed_role, is_unit = parse_cleanroom_target(target_input)
    target_role = (parsed.role_opt or parsed.target_role or parsed_role or "").strip().lower()
    if parsed.baseline and not target_role:
        target_role = "pretense_baseline" if parsed.pretense else "baseline"

    root = parsed.repo_root or find_workspace_root()
    active_pipeline = resolve_scope_pipeline(
        scope=scope,
        repo_root=root,
        explicit_pretense=parsed.pretense,
        target_role=target_role or None,
    )
    from support.lib.lifecycle import enter_phase, get_singleton
    from update_with_ai.parts.agent.lib import session as agent_session
    from update_with_ai.parts.workspace.lib import role_registry, provision
    from update_with_ai.parts.workspace_cli.lib import work

    with enter_phase(agent_session.agent_session):
        reg = get_singleton(role_registry.WorkspaceRegistry)
        work = get_singleton(work.WorkspaceWorkManager)
        prov = get_singleton(provision.WorkspaceProvisioner)

        declared_roles = reg.list_roles(root, dir_scope=scope)
        if not declared_roles:
            print(f"Error: No declared roles found for directory scope '{scope}'.", file=sys.stderr)
            return 1

        if active_pipeline and cleanroom_uv_runner is not None:
            try:
                scope_prefix = f"{scope}/parts" if scope else "parts"
                loader = cleanroom_uv_runner.get_singleton(cleanroom_uv_runner.manifest_loader.UvManifestLoader)
                _, roles_dict = loader._get_methodology_roles(root, scope_prefix)  # type: ignore[reportAttributeAccessIssue]
                if roles_dict:
                    declared_roles = [
                        r for r in declared_roles
                        if roles_dict.get(r.role_name, {}).get("pipeline") in (None, "", active_pipeline)
                    ]
            except Exception:
                pass

        if target_role:
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                r_clean = r.role_name.split(":")[-1].strip().lower()
                if r_clean == target_role or r.role_name.lower() == target_role:
                    matching_idx = idx
                    break
            if matching_idx is None:
                try:
                    fused_r_def = reg.resolve_role_definition(target_role, repo_root=root, dir_scope=scope)
                    if fused_r_def and fused_r_def.fused_roles:
                        declared_roles = [fused_r_def]
                    else:
                        valid_names = ", ".join(r.role_name for r in declared_roles)
                        print(f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}", file=sys.stderr)
                        return 1
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    valid_names = ", ".join(r.role_name for r in declared_roles)
                    print(f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}", file=sys.stderr)
                    return 1
            else:
                declared_roles = list(declared_roles[: matching_idx + 1])

        # Auto-commission any missing role workspaces up to target_role
        default_model = resolve_default_model(root, harness="antigravity")
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
            ws_dir = reg.compute_workspace_dir(r.role_name, dir_scope=scope, repo_root=root)
            if not os.path.isdir(ws_dir) or not os.path.isdir(os.path.join(ws_dir, "bin")):
                prov.commission(role_name=r.role_name, dir_scope=scope, repo_root=root, model=default_model)
            workspace_dirs[r.role_name] = ws_dir
            ws_model = default_model or ""
            rcfg = os.path.join(ws_dir, ".cleanroom_role.json")
            if os.path.isfile(rcfg):
                try:
                    with open(rcfg, "r", encoding="utf-8") as f:
                        rdata = json.load(f)
                    if rdata.get("model"):
                        ws_model = str(rdata["model"])
                except Exception:
                    pass
            if ws_model:
                role_models[r.role_name] = ws_model
                m_low = ws_model.lower()
                if "lite" in m_low:
                    antigravity_models[r.role_name] = "flash_lite"
                elif "flash" in m_low:
                    antigravity_models[r.role_name] = "flash"
                elif "argon" in m_low:
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


def _find_subagent_tool_mod(target_scope: str | None, args_list: list[str]) -> Any:
    subagent_tool_mod = None
    for _r in _get_roots():
        for _entry in os.listdir(_r) if os.path.isdir(_r) else []:
            if _entry.startswith((".", "bazel-", "venv")):
                continue
            if (_dir_scope and _entry == _dir_scope) or (target_scope and _entry == target_scope) or (_entry in args_list):
                continue
            _cand = os.path.join(_r, _entry, "parts", "subagent", "lib", "subagent_tool_impl.py")
            if os.path.isfile(_cand) and os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
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
            pass
    return subagent_tool_mod


def run_loop_target(
    target_str: str,
    up_to_role: str | None = None,
    model: str | None = None,
    action: str = "clean",
    message: str | None = None,
    repo_root: str | None = None,
    workspace_dir: str | None = None,
    config: str | None = None,
    exclude_roles: Sequence[str] | None = None,
    pipeline: str | None = None,
) -> int:
    assert cleanroom_uv_runner is not None, "cleanroom_uv_runner module not found"
    ws = workspace_dir or repo_root
    return cleanroom_uv_runner.run_cleanroom_target(
        target_str=target_str,
        action=action,
        model=model or config,
        message=message,
        workspace_dir=ws,
        up_to_role=up_to_role,
        exclude_roles=exclude_roles,
        pipeline=pipeline,
    )


def run_mark_clean_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom mark-clean",
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
        "--pretense",
        action="store_true",
        default=False,
        help="Use pretense pipeline.",
    )
    parsed = parser.parse_args(argv)
    target = parsed.target or _get_dir_scope()
    if not target:
        print("Error: Target node, file path, or scope directory must be specified (e.g. uv run cleanroom mark-clean staging).", file=sys.stderr)
        return 1
    assert cleanroom_uv_runner is not None, "cleanroom_uv_runner module not found"
    return cleanroom_uv_runner.run_cleanroom_target(
        target_str=target,
        action="mark-clean",
        workspace_dir=parsed.workspace_dir,
        up_to_role=parsed.up_to_role,
        exclude_roles=parsed.exclude_roles,
        pipeline="pretense" if parsed.pretense else None,
    )


def run_dirty_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom dirty",
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
        print("Error: Target node, file path, or scope directory must be specified (e.g. uv run cleanroom dirty staging).", file=sys.stderr)
        return 1
    msg = parsed.msg_flag or parsed.message
    if not msg and parsed.extra_args:
        msg = " ".join(parsed.extra_args)
    if not msg:
        msg = "Marked dirty"
    assert cleanroom_uv_runner is not None, "cleanroom_uv_runner module not found"
    return cleanroom_uv_runner.run_cleanroom_target(
        target_str=target,
        action="dirty",
        message=msg,
        workspace_dir=parsed.workspace_dir,
    )


def run_change_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom change",
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
        print("Error: Target must be specified (e.g. uv run cleanroom change <target> [message]).", file=sys.stderr)
        return 1
    desc = parsed.msg_flag or parsed.message
    if not desc and parsed.extra_args:
        desc = " ".join(parsed.extra_args)
    desc = desc or "Manual change"
    assert cleanroom_uv_runner is not None, "cleanroom_uv_runner module not found"
    return cleanroom_uv_runner.run_cleanroom_target(
        target_str=target,
        action="change",
        message=desc,
        workspace_dir=parsed.workspace_dir,
    )


def run_prompt_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom prompt",
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
        print("Error: Target must be specified (e.g. uv run cleanroom prompt <target>).", file=sys.stderr)
        return 1
    assert cleanroom_uv_runner is not None, "cleanroom_uv_runner module not found"
    return cleanroom_uv_runner.run_cleanroom_target(
        target_str=target,
        action="prompt",
        workspace_dir=parsed.workspace_dir,
    )


def run_feedback_cli(argv: list[str], prog: str = "cleanroom feedback") -> int:
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
        print(f"Error: Target must be specified (e.g. uv run {prog} <target> '<critique>').", file=sys.stderr)
        return 1

    critique = parsed.msg_flag or parsed.critique
    if not critique:
        print(f"Error: feedback command requires a critique message (e.g. uv run {prog} <target> '<critique>' or -m '<critique>').", file=sys.stderr)
        return 2

    # Check if executing within an isolated role workspace or target looks like a file path
    is_role_ws = os.path.isfile(".cleanroom_role.json")
    is_target_label = target.startswith("//") or (":" in target and not os.path.exists(target))

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

    # Fallback / standalone DAG mode: add feedback message via cleanroom_uv_runner
    assert cleanroom_uv_runner is not None, "cleanroom_uv_runner module not found"
    return cleanroom_uv_runner.run_cleanroom_target(
        target_str=target,
        action="feedback",
        message=critique,
        workspace_dir=parsed.workspace_dir,
    )


def run_orchestrate(
    argv: list[str],
    default_harness: str = "antigravity",
    prog: str = "cleanroom orchestrate",
) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Cleanroom Multi-Agent Workspace Orchestrator" if "orchestrate" in prog else "Cleanroom Autonomous Convergence Tool",
    )
    parser.add_argument(
        "dir_scope",
        nargs="?",
        default="",
        help="Directory scope or target to orchestrate/clean.",
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
        "--harness",
        default=None,
        help="Subagent execution harness (loop, antigravity, dsh, simulation).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run autonomous in-process loop execution rather than external subagent harness (alias for --harness loop).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model configuration or profile name (e.g. default, deepseek-flash, gemini-flash).",
    )
    parser.add_argument(
        "--action",
        "-a",
        default="clean",
        help="Action to perform in loop execution (default: clean).",
    )
    parser.add_argument(
        "--message",
        "-m",
        default=None,
        help="Message payload for loop action.",
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
        "--pretense",
        action="store_true",
        help="Use Pretense testing pipeline (pretense, pretense_qa, pretense_coverage) instead of standard test/qa/coverage.",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Execute fused baseline role instead of multi-agent DAG.",
    )
    parser.add_argument(
        "--antigravity-dispatch",
        choices=["message", "new-conversation", "none"],
        default="message",
        help="Antigravity Desktop IPC dispatch mode when harness is antigravity.",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Additional arguments or trailing message",
    )
    parsed = parser.parse_args(argv)

    target_input = parsed.scope_opt or parsed.dir_scope or _get_dir_scope()
    if not target_input:
        print(f"Error: Directory scope or target must be specified (e.g. uv run {prog} staging or staging#qa).", file=sys.stderr)
        return 1

    scope, parsed_role, is_unit = parse_cleanroom_target(target_input)
    target_role = (parsed.role_opt or parsed.target_role or parsed_role or "").strip().lower()
    if parsed.baseline and not target_role:
        target_role = "pretense_baseline" if parsed.pretense else "baseline"

    active_pipeline = resolve_scope_pipeline(
        scope=scope,
        repo_root=parsed.repo_root,
        explicit_pretense=parsed.pretense,
        target_role=target_role or None,
    )

    active_harness = "loop" if parsed.loop else (parsed.harness or default_harness).strip().lower()

    if active_harness == "loop":
        cfg = parsed.model or resolve_default_model(parsed.repo_root, harness="loop")
        if cfg == "default":
            resolved = resolve_default_model(parsed.repo_root, harness="loop")
            if resolved:
                cfg = resolved
        msg = parsed.message
        if not msg and parsed.extra_args:
            msg = " ".join(parsed.extra_args)
        loop_target = target_input
        return run_loop_target(
            target_str=loop_target,
            up_to_role=target_role or None,
            model=cfg,
            action=parsed.action,
            message=msg,
            repo_root=parsed.repo_root,
            pipeline=active_pipeline,
        )

    # Headless / CI Mode (or dsh / simulation harnesses)
    is_headless = parsed.headless or parsed.simulation or active_harness in ("dsh", "simulation", "deepseek", "deepseek-harness")
    if is_headless:
        subagent_tool_mod = _find_subagent_tool_mod(scope, argv)
        if subagent_tool_mod is not None:
            forward_args = ["orchestrate", "--scope", scope]
            if target_role:
                forward_args.extend(["--role", target_role])
            if is_unit:
                forward_args.extend(["--target", target_input])
            forward_args.extend(["--harness", active_harness])
            h_model = parsed.model or resolve_default_model(parsed.repo_root, harness=active_harness)
            if h_model:
                forward_args.extend(["--model", h_model])
            if parsed.max_waves is not None:
                forward_args.extend(["--max-waves", str(parsed.max_waves)])
            if parsed.batch_size is not None:
                forward_args.extend(["--batch-size", str(parsed.batch_size)])
            if parsed.timeout is not None:
                forward_args.extend(["--timeout", str(parsed.timeout)])
            if parsed.max_context_tokens is not None:
                forward_args.extend(["--max-context-tokens", str(parsed.max_context_tokens)])
            if parsed.repo_root:
                forward_args.extend(["--repo-root", parsed.repo_root])
            if parsed.pretense:
                forward_args.append("--pretense")
            if parsed.simulation:
                forward_args.append("--simulation")
            return subagent_tool_mod.main(forward_args)
        print("Error: Subagent tool runner module not found for headless execution.", file=sys.stderr)
        return 1

    # In-IDE Antigravity interactive mode:
    # 1. Refresh global agent definitions
    ensure_antigravity_plugin_installed()

    root = parsed.repo_root or find_workspace_root()
    from support.lib.lifecycle import enter_phase, get_singleton
    from update_with_ai.parts.agent.lib import session as agent_session
    from update_with_ai.parts.workspace.lib import role_registry, provision
    from update_with_ai.parts.workspace_cli.lib import work

    with enter_phase(agent_session.agent_session):
        reg = get_singleton(role_registry.WorkspaceRegistry)
        work = get_singleton(work.WorkspaceWorkManager)
        prov = get_singleton(provision.WorkspaceProvisioner)

        declared_roles = reg.list_roles(root, dir_scope=scope)
        if not declared_roles:
            print(f"Error: No declared roles found for directory scope '{scope}'.", file=sys.stderr)
            return 1

        if active_pipeline and cleanroom_uv_runner is not None:
            try:
                scope_prefix = f"{scope}/parts" if scope else "parts"
                loader = cleanroom_uv_runner.get_singleton(cleanroom_uv_runner.manifest_loader.UvManifestLoader)
                _, roles_dict = loader._get_methodology_roles(root, scope_prefix)  # type: ignore[reportAttributeAccessIssue]
                if roles_dict:
                    declared_roles = [
                        r for r in declared_roles
                        if roles_dict.get(r.role_name, {}).get("pipeline") in (None, "", active_pipeline)
                    ]
            except Exception:
                pass

        if target_role:
            matching_idx = None
            for idx, r in enumerate(declared_roles):
                r_clean = r.role_name.split(":")[-1].strip().lower()
                if r_clean == target_role or r.role_name.lower() == target_role:
                    matching_idx = idx
                    break
            if matching_idx is None:
                try:
                    fused_r_def = reg.resolve_role_definition(target_role, repo_root=root, dir_scope=scope)
                    if fused_r_def and fused_r_def.fused_roles:
                        declared_roles = [fused_r_def]
                    else:
                        valid_names = ", ".join(r.role_name for r in declared_roles)
                        print(f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}", file=sys.stderr)
                        return 1
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    valid_names = ", ".join(r.role_name for r in declared_roles)
                    print(f"Error: Unknown role '{target_role}' for scope '{scope}'. Valid roles are: {valid_names}", file=sys.stderr)
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
                ready_nodes.append((r.role_name, it.target_file, list(it.dirtiness_reasons)))
            for it in q_blocked:
                blocked_nodes.append((r.role_name, it.target_file, list(it.blocked_reasons)))

        role_suffix = f" (up to role: {target_role})" if target_role else ""
        if not ready_nodes and not blocked_nodes:
            deleted = decommission_workspaces(scope, target_role=target_role, repo_root=root)
            cleanup_msg = f" Decommissioned {deleted} role workspace(s)." if deleted else ""
            print(f"✔ CLEAN: All nodes in scope '{scope}' evaluate CLEAN{role_suffix}.{cleanup_msg} No work pending.")
            return 0

        harness = active_harness
        model_to_bind = parsed.model or resolve_default_model(root, harness=harness)
        if model_to_bind == "default":
            resolved = resolve_default_model(root, harness=harness)
            if resolved:
                model_to_bind = resolved
        model_hint = f" (model: {model_to_bind})" if model_to_bind else ""
        action_title = "Clean" if "clean" in prog.split() else "Orchestrate"
        print(f"=== Cleanroom {action_title} Pre-flight [Scope: {scope}{role_suffix}] ===")
        print(f"Commissioning/verifying {len(declared_roles)} role workspaces{model_hint}...")
        commissioned_dirs = []
        for r in declared_roles:
            ws_info = prov.commission(
                role_name=r.role_name,
                dir_scope=scope,
                repo_root=root,
                model=model_to_bind,
                reset=True,
            )
            commissioned_dirs.append((r.role_name, ws_info.workspace_dir))
        parent_ws_dir = os.path.dirname(commissioned_dirs[0][1]) if commissioned_dirs else ""
        print(f"[OK] All {len(commissioned_dirs)} role workspaces ready in {parent_ws_dir}.")

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
        target_display = f"{target_input}#{target_role}" if (is_unit and target_role) else (target_input if is_unit else f"{scope}{role_hint}")
        queue_hint = f" {target_input} {target_role}" if (is_unit and target_role) else (f" {target_input}" if is_unit else (f" {target_role}" if target_role else ""))

        # Attempt Antigravity Desktop IPC dispatch
        dispatch_mode = getattr(parsed, "antigravity_dispatch", "message")
        if dispatch_mode != "none":
            dispatch_antigravity_coordination(
                target_display=target_display,
                mode=dispatch_mode,
                model=model_to_bind or "flash",
            )

        ag_coord_model = "inherit"
        if model_to_bind:
            m_low = model_to_bind.lower()
            if "lite" in m_low:
                ag_coord_model = "flash_lite"
            elif "flash" in m_low:
                ag_coord_model = "flash"
            elif "argon" in m_low:
                ag_coord_model = "inherit"
            elif "pro" in m_low:
                ag_coord_model = "pro"

        print("\n" + "=" * 72)
        print("AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE:")
        print("The 'cleanroom_coordinator' subagent definition is installed and ready.")
        print("Immediately invoke the coordinator subagent in this step:")
        print("  invoke_subagent(")
        print("    Subagents=[{")
        print('      "TypeName": "cleanroom_coordinator",')
        print('      "Role": "Cleanroom Coordinator",')
        print(f'      "Model": "{ag_coord_model}",')
        print(f'      "Prompt": "Clean all dirty nodes in {target_display} using cleanroom_coordinator."')
        print("    }]")
        print("  )")
        print("\nCoordinator execution steps:")
        print(f"  1. Evaluate DAG ready nodes via 'uv run cleanroom work-queue {scope}{queue_hint} --json'.")
        print("  2. Wake/dispatch workspace-bound role subagents (TypeName: 'cleanroom_worker').")
        print("  3. Direct role workers to drain ready nodes via submit, blame, or fail.")
        print("  4. Converge the DAG across topological waves.")
        print("  5. Decommission role workspaces upon clean convergence.")
        print("=" * 72)
        return 0


def run_clean_cli(argv: list[str]) -> int:
    return run_orchestrate(argv, default_harness="loop", prog="cleanroom clean")


def main_clean(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if "--repo-root" in args_list:
        try:
            rr_idx = args_list.index("--repo-root")
            if rr_idx + 1 < len(args_list):
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(args_list[rr_idx + 1])
        except (ValueError, IndexError):
            pass
    return run_clean_cli(args_list)


def main_orchestrate(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if "--repo-root" in args_list:
        try:
            rr_idx = args_list.index("--repo-root")
            if rr_idx + 1 < len(args_list):
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(args_list[rr_idx + 1])
        except (ValueError, IndexError):
            pass
    return run_orchestrate(args_list)


def run_benchmark_cli(argv: list[str]) -> int:
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
                cand = os.path.join(r, entry, "parts", "benchmark", "lib", "benchmark_impl.py")
                if os.path.isfile(cand):
                    mod = importlib.import_module(f"{entry}.parts.benchmark.lib.benchmark_impl")
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
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(args_list[rr_idx + 1])
        except (ValueError, IndexError):
            pass
    return run_benchmark_cli(args_list)


def run_commission_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom commission",
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
        "--harness",
        default="antigravity",
        help="Subagent execution harness to tailor the workspace for (antigravity, dsh, simulation).",
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
                dir_scope and (
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
                if os.path.isdir(os.path.join(root, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                    dir_scope = entry
                    break
        except OSError:
            pass

    if not dir_scope:
        print("Error: Directory scope must be specified (e.g. uv run cleanroom commission --all staging or staging#qa).", file=sys.stderr)
        return 1

    from support.lib.lifecycle import enter_phase, get_singleton
    from update_with_ai.parts.agent.lib import session as agent_session
    from update_with_ai.parts.workspace.lib import role_registry, provision

    with enter_phase(agent_session.agent_session):
        prov = get_singleton(provision.WorkspaceProvisioner)
        reg = get_singleton(role_registry.WorkspaceRegistry)

        if all_roles:
            declared = reg.list_roles(root, dir_scope=dir_scope)
            if not declared:
                print(f"Error: No declared roles found for directory scope '{dir_scope}'.", file=sys.stderr)
                return 1
            roles_to_commission = [r.role_name for r in declared]
        else:
            if not role_name:
                print(f"Error: Role must be specified using <scope>#<role> syntax (e.g. uv run cleanroom commission {dir_scope}#qa) or use --all.", file=sys.stderr)
                return 1
            roles_to_commission = [role_name]

        harness = (parsed.harness or "antigravity").strip().lower()
        if harness == "antigravity":
            ensure_antigravity_plugin_installed()

        bound_model = parsed.model or resolve_default_model(root, harness=harness)
        if bound_model == "default":
            resolved = resolve_default_model(root, harness=harness)
            if resolved:
                bound_model = resolved

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
                    from update_with_ai.parts.dsh.lib import dsh_workspace
                    from update_with_ai.parts.agent.lib import session as agent_session
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

            # Record harness in .cleanroom_role.json
            role_cfg_path = os.path.join(desc.workspace_dir, ".cleanroom_role.json")
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
            print(f"✔ Commissioned workspace for role '{r}'{harness_label}{model_label} at: {desc.workspace_dir}")

        return 0


def decommission_workspaces(
    dir_scope: str,
    target_role: str | None = None,
    repo_root: str | None = None,
) -> int:
    """Decommissions and deletes role workspaces for a scope (and optional role boundary)."""
    root = repo_root or find_workspace_root()
    from support.lib.lifecycle import enter_phase, get_singleton
    from update_with_ai.parts.agent.lib import session as agent_session
    from update_with_ai.parts.workspace.lib import role_registry

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
                    fused_r_def = reg.resolve_role_definition(target_clean, repo_root=root, dir_scope=dir_scope)
                    if fused_r_def and fused_r_def.fused_roles:
                        declared_roles = [fused_r_def]
                except Exception:
                    pass

        deleted_count = 0
        deleted_paths: set[str] = set()

        def _delete_dir(path: str) -> None:
            if not os.path.isdir(path):
                return
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                for d in dirs:
                    dp = os.path.join(dirpath, d)
                    if not os.path.islink(dp):
                        try:
                            os.chmod(dp, 0o755)
                        except OSError:
                            pass
                for f in files:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        try:
                            os.chmod(fp, 0o644)
                        except OSError:
                            pass
            shutil.rmtree(path, ignore_errors=True)

        for r in declared_roles:
            ws_dir = reg.compute_workspace_dir(r.role_name, dir_scope=dir_scope, repo_root=root)
            if os.path.isdir(ws_dir):
                _delete_dir(ws_dir)
                reg.unregister_workspace(ws_dir, repo_root=root)
                deleted_count += 1
                deleted_paths.add(os.path.abspath(ws_dir))

        # Also sweep any orphaned workspaces in role_workspaces associated with dir_scope
        parent_dir = os.path.dirname(root)
        rw_dir = os.path.join(parent_dir, "role_workspaces")
        if os.path.isdir(rw_dir):
            clean_scope = dir_scope.strip("/").split("/")[0]
            for item in os.listdir(rw_dir):
                item_path = os.path.join(rw_dir, item)
                if not os.path.isdir(item_path) or os.path.abspath(item_path) in deleted_paths:
                    continue
                role_cfg = os.path.join(item_path, ".cleanroom_role.json")
                should_delete = False
                if os.path.isfile(role_cfg):
                    try:
                        with open(role_cfg, "r", encoding="utf-8") as f:
                            cdata = json.load(f)
                        cfg_scope = str(cdata.get("dir_scope") or cdata.get("parts_dir") or "")
                        if clean_scope in cfg_scope.split("/") or cfg_scope.startswith(clean_scope) or cfg_scope.startswith(f"//{clean_scope}"):
                            r_role = str(cdata.get("role_name") or cdata.get("role") or "").lower()
                            if not target_role or r_role in [r.role_name.lower() for r in declared_roles]:
                                should_delete = True
                    except Exception:
                        pass
                if not should_delete and (f"_{clean_scope}_" in item or item.endswith(f"_{clean_scope}")):
                    should_delete = True

                if should_delete:
                    _delete_dir(item_path)
                    reg.unregister_workspace(item_path, repo_root=root)
                    deleted_count += 1
                    deleted_paths.add(os.path.abspath(item_path))

        return deleted_count


def run_decommission_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cleanroom decommission",
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
        print("Error: Directory scope must be specified (e.g. uv run cleanroom decommission staging or staging#qa).", file=sys.stderr)
        return 1
    scope, parsed_role, _ = parse_cleanroom_target(target_input)
    target_role = (parsed.role_opt or parsed.target_role or parsed_role or "").strip().lower()
    deleted = decommission_workspaces(scope, target_role=target_role or None, repo_root=parsed.repo_root)
    print(f"✔ Decommissioned {deleted} role workspace(s) for scope '{scope}'.")
    return 0


def print_cleanroom_help() -> None:
    print("""usage: cleanroom [-h] <command> ...

Cleanroom Multi-Agent Workspace & Role Tool

positional arguments:
  <command>
    clean               Converge targets or scope clean (default: --harness loop)
    orchestrate         Orchestrate Cleanroom multi-agent convergence across role workspaces
    benchmark           Run empirical model efficiency and verification benchmark suites
    work-queue (queue)  Inspect Cleanroom DAG work queue for ready and blocked nodes
    dirty               Mark target or scope dirty in DAG storage
    mark-clean          Mark target or scope clean in DAG metadata without running LLM loop
    commission          Commission an isolated role workspace
    decommission        Decommission and delete provisioned role workspaces
    refresh-sys         Refresh system files, tools, configs, and guides across role workspaces
    get_work            Get ready dirty tasks in workspace scope
    submit              Verify and submit target with in-band header update
    feedback (blame)    Attribute feedback or blame critique to a target node or culprit file
    fail                Record verification failure and force dirty state
    coverage            Evaluate statement test coverage for a module
    check_files         Run role-specific verification checks on target files
    change              Record a change description on a target node or scope
    prompt              Print task prompt for a target node or scope
    configure           Configure global user environment (~/.config/cleanroom, model_configs.toml, credentials)
    install (init)      Prepare current workspace/repository for cleanroom execution
    install-plugin      Install/refresh Cleanroom Antigravity plugin and agent definitions

options:
  -h, --help            show this help message and exit
  --harness HARNESS     Subagent execution harness (loop, antigravity, dsh, simulation)
  --loop                Run autonomous in-process loop execution (alias for --harness loop)
""")


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
    if unit_name.endswith("_test"):
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


def _resolve_role_def_dynamically(role_name: str, ws_root: str, main_root: str | None) -> Any:
    # First attempt: WorkspaceRegistry via lifecycle
    for cand_mod in (
        "update_with_ai.parts.workspace.lib.role_registry",
        "parts.workspace.lib.role_registry",
        "role_registry",
    ):
        try:
            mod = importlib.import_module(cand_mod)
            from support.lib.lifecycle import enter_phase, get_singleton
            from update_with_ai.parts.agent.lib import session as agent_session
            with enter_phase(agent_session.agent_session):
                reg = get_singleton(mod.WorkspaceRegistry)
                r_def = reg.resolve_role_definition(role_name, repo_root=main_root or ws_root)
                if r_def and r_def.verify_template:
                    return r_def
        except Exception:
            pass

    # Fallback: parse cleanroom_roles.toml directly from workspace or repo root
    for root_cand in (ws_root, main_root):
        if not root_cand:
            continue
        for toml_path in (
            os.path.join(root_cand, "cleanroom_roles.toml"),
            os.path.join(root_cand, "update_with_ai", "cleanroom_roles.toml"),
            os.path.join(root_cand, "update_python_with_ai", "cleanroom_roles.toml"),
        ):
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
                            active_component_types=r_sec.get("active_component_types", []),
                            src_pattern=r_sec.get("src_pattern", ""),
                            fused_roles=r_sec.get("fused_roles", []),
                            common_spec_roles=r_sec.get("common_spec_roles", []),
                            star_role_deps=r_sec.get("star_role_deps", []),
                        )
                except Exception:
                    pass
    return None


def run_verify_micro_binary(role_name: str, argv: list[str]) -> int:
    ws_root = os.getcwd()
    main_root = _find_main_repo_root()
    meta_p = os.path.join(ws_root, ".cleanroom_role.json")
    fused_roles: list[str] = []
    d_scope = ""
    if os.path.isfile(meta_p):
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
        elif arg.startswith("--impl=") or arg.startswith("--test=") or arg.startswith("--pretense="):
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
                        if fd.endswith((".py", ".pyi")) and not fd.startswith(".") and fd != "__init__.py":
                            u_info = _extract_unit_info(os.path.join(root_d, fd), ws_root)
                            if u_info and u_info not in target_units:
                                target_units.append(u_info)
            else:
                u_info = _extract_unit_info(rt, ws_root)
                if u_info and u_info not in target_units:
                    target_units.append(u_info)
    else:
        parts_p = os.path.join(ws_root, d_scope, "parts") if d_scope else os.path.join(ws_root, "parts")
        if not os.path.isdir(parts_p) and os.path.isdir(os.path.join(ws_root, "parts")):
            parts_p = os.path.join(ws_root, "parts")
        if os.path.isdir(parts_p):
            for p_dir in sorted(os.listdir(parts_p)):
                p_full = os.path.join(parts_p, p_dir)
                if not os.path.isdir(p_full) or p_dir.startswith("."):
                    continue
                part_rel = os.path.relpath(p_full, ws_root).replace(os.sep, "/")
                cand_files: set[str] = set()
                for sub in ("low", "lib", "tests", "pretense"):
                    sub_d = os.path.join(p_full, sub)
                    if os.path.isdir(sub_d):
                        for f in os.listdir(sub_d):
                            if f.endswith((".py", ".pyi")) and not f.startswith(".") and f != "__init__.py":
                                cand_files.add(f)
                for f in sorted(cand_files):
                    base = os.path.splitext(f)[0]
                    if base.endswith("_test"):
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
        r_def = _resolve_role_def_dynamically(f"pretense_{role_name}", ws_root, main_root)
    if not r_def and any("test" in r for r in fused_roles) and role_name == "pretense":
        r_def = _resolve_role_def_dynamically("test", ws_root, main_root)

    if not r_def:
        print(f"Error: Unknown role verification definition for '{role_name}'.", file=sys.stderr)
        return 1

    cmd_tmpl = getattr(r_def, "verify_template", "") or ""
    if not cmd_tmpl or cmd_tmpl.strip().startswith("#"):
        print(f"[OK] No verification check required for role '{role_name}'.")
        return 0

    active_types = getattr(r_def, "active_component_types", []) or []
    src_pattern = getattr(r_def, "src_pattern", "") or ""

    env = dict(os.environ)
    env["BUILD_WORKSPACE_DIRECTORY"] = ws_root
    if "UV_PROJECT" not in env and main_root and os.path.isdir(main_root):
        env["UV_PROJECT"] = main_root
    pypaths = [ws_root]
    sup_lib = os.path.join(ws_root, "support", "lib")
    if os.path.isdir(sup_lib):
        pypaths.append(sup_lib)
    if main_root and os.path.isdir(main_root):
        pypaths.append(main_root)
        for cand_sup in (
            os.path.join(main_root, "support", "lib"),
            os.path.join(main_root, "update_with_ai"),
            os.path.join(main_root, "update_python_with_ai"),
        ):
            if os.path.isdir(cand_sup) and cand_sup not in pypaths:
                pypaths.append(cand_sup)
    if "PYTHONPATH" in env:
        pypaths.extend(p for p in env["PYTHONPATH"].split(os.pathsep) if p and p not in pypaths)
    env["PYTHONPATH"] = os.pathsep.join(pypaths)

    verified_count = 0
    for part_dir, unit_name in target_units:
        # Classify component type: _impl is implementation, else interface
        ctype = "implementation" if unit_name.endswith("_impl") else "interface"
        if active_types and ctype not in active_types:
            continue

        if src_pattern:
            expected_file = os.path.join(ws_root, src_pattern.format(unit_dir=part_dir, unit_name=unit_name))
            if not os.path.isfile(expected_file):
                continue

        formatted_cmd = cmd_tmpl.format(
            unit_dir=part_dir,
            unit_name=unit_name,
            max_failures=1,
            maxfail_arg="--maxfail=1",
        )

        target_display = f"{part_dir}/{unit_name}"
        print(f"=== Verifying {role_name} on {target_display} ===")
        res = subprocess.run(formatted_cmd, shell=True, cwd=ws_root, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[FAIL] Verification failed for {target_display} ({role_name}):\n{res.stdout}\n{res.stderr}".strip())
            spec_roles = list(getattr(r_def, "common_spec_roles", None) or getattr(r_def, "star_role_deps", None) or [])
            resolved_specs: list[str] = []
            base_unit = unit_name[:-5] if unit_name.endswith("_impl") else unit_name
            for s_role in spec_roles:
                s_def = _resolve_role_def_dynamically(s_role, ws_root, main_root)
                if not s_def or not getattr(s_def, "src_pattern", ""):
                    continue
                cands = [s_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name)]
                if base_unit != unit_name:
                    cands.append(s_def.src_pattern.format(unit_dir=part_dir, unit_name=base_unit))
                found_any = False
                for c in cands:
                    full_ws = os.path.join(ws_root, c) if not os.path.isabs(c) else c
                    full_repo = os.path.join(main_root, c) if (main_root and not os.path.isabs(c)) else None
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

            spec_desc = ", ".join(resolved_specs) if resolved_specs else "the common specification"

            if "coverage" in role_name:
                print(
                    "\n" + "=" * 80 + "\n"
                    "[COVERAGE ARBITER REMINDER - EXPLAIN FEEDBACK IN TERMS OF SPECIFICATION]\n"
                    f"• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification ({spec_desc}).\n"
                    "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
                    "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
                    "• Translate uncovered statements and branches into missing specification requirements or scenario cases.\n"
                    "• If an uncovered branch is an unreachable defensive check or caller assumption guaranteed by the specification, instruct the implementation author to prune it or mark it as unreachable according to the methodology.\n"
                    + "=" * 80
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
                    + "=" * 80
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
    ws_dir = os.path.abspath(argv[0] if argv else os.getcwd())
    meta_p = os.path.join(ws_dir, ".cleanroom_role.json")
    if not os.path.isfile(meta_p):
        print(f"Error: Not a cleanroom role workspace: {ws_dir}", file=sys.stderr)
        return 1

    with open(meta_p, "r", encoding="utf-8") as f:
        meta = json.load(f)

    fused_roles = meta.get("fused_roles") or []
    if not fused_roles:
        print(f"Error: Workspace at {ws_dir} is not a fused role workspace.", file=sys.stderr)
        return 1

    for r in fused_roles:
        print(f"[VERIFY-FUSED] Verifying constituent role '{r}' in {ws_dir}...")
        orig_cwd = os.getcwd()
        try:
            os.chdir(ws_dir)
            code = run_verify_micro_binary(r, [])
            if code != 0:
                print(f"[FAIL] Fused verification failed for role '{r}' in {ws_dir}.", file=sys.stderr)
                return code
        finally:
            os.chdir(orig_cwd)

    print(f"[OK] All fused role verifications passed in {ws_dir}.")
    return 0


def run_harvest_fused_cli(argv: list[str]) -> int:
    ws_dir = os.path.abspath(argv[0] if argv else os.getcwd())
    meta_p = os.path.join(ws_dir, ".cleanroom_role.json")
    if not os.path.isfile(meta_p):
        print(f"Error: Not a cleanroom role workspace: {ws_dir}", file=sys.stderr)
        return 1

    with open(meta_p, "r", encoding="utf-8") as f:
        meta = json.load(f)

    fused_roles = meta.get("fused_roles") or []
    dir_scope = meta.get("dir_scope") or meta.get("parts_dir", "")
    main_root = _find_main_repo_root()
    if not main_root or main_root == ws_dir:
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) == "role_workspaces":
            main_root = os.path.dirname(parent)
        else:
            main_root = os.getcwd()

    parts_p = os.path.join(ws_dir, dir_scope, "parts") if dir_scope else os.path.join(ws_dir, "parts")
    if not os.path.isdir(parts_p) and os.path.isdir(os.path.join(ws_dir, "parts")):
        parts_p = os.path.join(ws_dir, "parts")

    harvested_files: list[str] = []
    if os.path.isdir(parts_p):
        for root, dirs, files in os.walk(parts_p):
            for f in files:
                if f.endswith((".py", ".pyi", ".md")) and not f.startswith("."):
                    rel = os.path.relpath(os.path.join(root, f), ws_dir).replace(os.sep, "/")
                    is_constituent = False
                    for r in fused_roles:
                        if f"/{r}/" in f"/{rel}/" or (r == "test" and "/tests/" in f"/{rel}/"):
                            is_constituent = True
                            break
                    if not is_constituent and ("lib/" in rel or "tests/" in rel or "pretense/" in rel):
                        is_constituent = True

                    if is_constituent:
                        src_f = os.path.join(ws_dir, rel)
                        dst_f = os.path.join(main_root, rel)
                        os.makedirs(os.path.dirname(dst_f), exist_ok=True)
                        shutil.copy2(src_f, dst_f)
                        os.chmod(dst_f, 0o644)

                        if f != "__init__.py":
                            src_metadata = None
                            for mod_cand in (
                                "update_with_ai.parts.metadata.lib.src_metadata",
                                "parts.metadata.lib.src_metadata",
                                "src_metadata",
                            ):
                                try:
                                    src_metadata = importlib.import_module(mod_cand)
                                    break
                                except Exception:
                                    pass

                            if src_metadata:
                                src_metadata.record_change(dst_f, "Fused role implementation and verification")
                                for c_role in fused_roles:
                                    if "qa" in c_role or "coverage" in c_role:
                                        src_metadata.stamp_audit(dst_f, c_role)
                                if "qa" in fused_roles or "pretense_qa" in fused_roles:
                                    src_metadata.stamp_audit(dst_f, "qa")
                                if "coverage" in fused_roles or "pretense_coverage" in fused_roles:
                                    src_metadata.stamp_audit(dst_f, "coverage")
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

    for _pkg in list(dict.fromkeys(discovered_pkgs + ["update_with_ai", "parts"])):
        for sub in (
            "systems.lib.cleanroom_asm",
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
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = os.path.abspath(args_list[rr_idx + 1])
        except (ValueError, IndexError):
            pass
    # Re-install agent files each time cleanroom is executed at repo/CLI level
    # Skip inside isolated role workspaces or when running worker verification tools
    is_role_ws = bool(
        os.path.isfile(os.path.join(os.getcwd(), ".cleanroom_role.json"))
        or os.environ.get("CLEANROOM_ROLE_WORKSPACE")
    )
    cmd_0 = args_list[0] if args_list else ""
    is_worker_cmd = bool(
        cmd_0 in (
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
        )
        or cmd_0.startswith("verify_")
        or cmd_0.startswith("verify-")
    )
    if not is_role_ws and not is_worker_cmd:
        try:
            ensure_antigravity_plugin_installed()
        except Exception:
            pass

    if not args_list or args_list[0] in ("-h", "--help", "help"):
        print_cleanroom_help()
        return 0 if args_list else 1

    if args_list[0] in ("configure", "config"):
        return configure_user_environment()

    if args_list[0] in ("install", "init"):
        return install_workspace()

    if args_list[0] in ("install-plugin", "install_plugin", "install-agents"):
        p = ensure_antigravity_plugin_installed()
        print(f"[OK] Cleanroom Antigravity plugin and agent definitions installed at: {p}")
        return 0

    if args_list[0] in ("work-queue", "work_queue", "queue"):
        return run_work_queue(args_list[1:])

    if args_list[0] in ("dirty",):
        return run_dirty_cli(args_list[1:])

    if args_list[0] in ("mark-clean", "mark_clean"):
        return run_mark_clean_cli(args_list[1:])

    if args_list[0] in ("change",):
        return run_change_cli(args_list[1:])

    if args_list[0] in ("prompt",):
        return run_prompt_cli(args_list[1:])

    if args_list[0] in ("feedback", "blame"):
        return run_feedback_cli(args_list[1:], prog=f"cleanroom {args_list[0]}")

    if args_list[0] == "clean":
        return run_clean_cli(args_list[1:])

    if args_list[0] == "orchestrate":
        return run_orchestrate(args_list[1:])

    if args_list[0] in ("benchmark", "evaluate"):
        return run_benchmark_cli(args_list[1:])

    if args_list[0] in ("commission",):
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

    if "--loop" in args_list:
        clean_args = [a for a in args_list if a != "--loop"]
        if clean_args and clean_args[0] == "clean":
            clean_args = clean_args[1:]
        return run_clean_cli(clean_args)

    if any(a.startswith("--harness") for a in args_list):
        return run_clean_cli(args_list)

    assert cli_tool_impl is not None
    return cli_tool_impl.main(argv)


if __name__ == "__main__":
    sys.exit(main())
