# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:50:00Z
# CHANGE: Implement scaffold_impl
# CODE_HASH: 9da3c834344a
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for scaffold_impl."""

from __future__ import annotations

import fnmatch
import json
import os
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from . import roles, scaffold


# Contract: Metadata file name matching cleanroom_files_ext.ROLE_DESCRIPTOR_FILE.
ROLE_CONFIG_FILE = ".cleanroom_role.json"


# Contract: Writes a text file and sets exact permissions, handling existing read-only files cleanly.
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
    if executable:
        mode = 0o555 if readonly else 0o755
    else:
        mode = 0o444 if readonly else 0o644
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


# Contract: Finds companion .pyi specification file for a unit stem in a part directory.
def _find_spec_pyi(
    part_path: str, stem: str, main_root: Optional[str] = None
) -> Optional[str]:
    """Finds companion .pyi specification file for a unit stem in a part directory."""
    for spec_dir in ("low", "grounding"):
        candidate = os.path.join(part_path, spec_dir, f"{stem}.pyi")
        if os.path.isfile(candidate):
            return candidate
    if main_root:
        part_name = os.path.basename(part_path)
        try:
            for entry in os.listdir(main_root):
                base_dir = os.path.join(main_root, entry)
                if not os.path.isdir(base_dir) or entry.startswith((".", "bazel-", "venv")):
                    continue
                for spec_dir in ("low", "grounding"):
                    candidate = os.path.join(
                        base_dir, "parts", part_name, spec_dir, f"{stem}.pyi"
                    )
                    if os.path.isfile(candidate):
                        return candidate
        except OSError:
            pass
    return None


# Contract: Reports whether a relative path matches any configured glob pattern.
def _matches_any_pattern(rel_path: str, patterns: Sequence[str]) -> bool:
    """Reports whether a relative path matches any configured glob pattern."""
    normalized = rel_path.replace("\\", "/")
    fname = os.path.basename(normalized)
    return any(
        fnmatch.fnmatch(normalized, p)
        or fnmatch.fnmatch(normalized, f"*/{p}")
        or fnmatch.fnmatch(normalized, f"*{p}")
        or fnmatch.fnmatch(fname, p)
        for p in patterns
    )


# Contract: Traverses synchronized scope discovering declared unit directories and stems from low/grounding/high specs.
def _declared_units(repo_root: str, scope_dir: str) -> List[Tuple[str, str]]:
    """Returns declared (unit_dir, unit_name) pairs beneath a synchronized scope."""
    units: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    part_dirs: List[str] = []
    parts_dir = os.path.join(scope_dir, "parts")
    if os.path.isdir(parts_dir):
        part_dirs = [
            os.path.join(parts_dir, name)
            for name in sorted(os.listdir(parts_dir))
            if os.path.isdir(os.path.join(parts_dir, name)) and not name.startswith(".")
        ]
    elif os.path.isdir(scope_dir):
        part_dirs = [
            os.path.join(scope_dir, name)
            for name in sorted(os.listdir(scope_dir))
            if os.path.isdir(os.path.join(scope_dir, name)) and not name.startswith(".")
        ]
    for part_dir in part_dirs:
        rel_part = os.path.relpath(part_dir, repo_root).replace("\\", "/")
        stems: Set[str] = set()
        for sub in ("low", "grounding", "high"):
            sub_dir = os.path.join(part_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            try:
                for fname in os.listdir(sub_dir):
                    if fname.startswith(".") or fname == "__init__.py":
                        continue
                    if not fname.endswith((".pyi", ".py", ".md")):
                        continue
                    stem = os.path.splitext(fname)[0]
                    if stem and stem != "__init__" and not stem.endswith("_ext"):
                        stems.add(stem)
            except OSError:
                pass
        for stem in sorted(stems):
            key = (rel_part, stem)
            if key not in seen:
                seen.add(key)
                units.append(key)
    return units


# Contract: Synthesizes starter skeleton content for a declared writable target file from template or spec.
def _missing_target_skeleton(
    repo_root: str,
    rel_path: str,
    unit_dir: str,
    unit_name: str,
    role_def: roles.RoleDefinition,
) -> Optional[str]:
    """Synthesizes starter skeleton content for a declared writable target file."""
    if role_def.template:
        template_path = os.path.join(repo_root, role_def.template)
        if os.path.isfile(template_path):
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    return f.read()
            except (OSError, UnicodeDecodeError):
                return None
    if not rel_path.endswith(".py"):
        return None
    pyi_path = _find_spec_pyi(
        os.path.join(repo_root, unit_dir), unit_name, main_root=repo_root
    )
    if pyi_path is None or not os.path.isfile(pyi_path):
        return None
    try:
        generate_lib_skeleton = None
        try:
            from support.lib.lib_lint import generate_lib_skeleton
        except ImportError:
            pass
        if generate_lib_skeleton is None:
            import importlib
            for entry in os.listdir(repo_root):
                pkg_dir = os.path.join(repo_root, entry)
                if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                    try:
                        mod = importlib.import_module(f"{entry}.support.lib.lib_lint")
                        generate_lib_skeleton = getattr(mod, "generate_lib_skeleton", None)
                        if generate_lib_skeleton is not None:
                            break
                    except ImportError:
                        pass
        if generate_lib_skeleton is None:
            return None
        segments = unit_dir.replace("\\", "/").split("/")
        base_pkg = ""
        if "parts" in segments and segments.index("parts") > 0:
            base_pkg = segments[segments.index("parts") - 1]
        return generate_lib_skeleton(pyi_path, unit_name, parts_base=base_pkg or None)
    except (ImportError, OSError, SyntaxError, RuntimeError, ValueError):
        return None


# Contract: Creates missing starter skeletons matching writable target patterns absent from disk.
def _create_missing_target_skeletons(
    workspace_dir: str,
    repo_root: str,
    dir_scope: str,
    role_def: roles.RoleDefinition,
) -> List[str]:
    """Creates a missing target skeleton for every declared writable target file absent from disk."""
    created: List[str] = []
    if not role_def.src_pattern or not role_def.writable_file_patterns:
        return created
    scope_dir = os.path.join(repo_root, dir_scope) if dir_scope else repo_root
    for unit_dir, unit_name in _declared_units(repo_root, scope_dir):
        rel_path = role_def.src_pattern.format(unit_dir=unit_dir, unit_name=unit_name)
        if not _matches_any_pattern(rel_path, role_def.writable_file_patterns):
            continue
        if os.path.isfile(os.path.join(workspace_dir, rel_path)) or os.path.isfile(
            os.path.join(repo_root, rel_path)
        ):
            continue
        skeleton = _missing_target_skeleton(
            repo_root, rel_path, unit_dir, unit_name, role_def
        )
        if skeleton is None:
            continue
        write_file_with_perms(
            os.path.join(workspace_dir, rel_path), skeleton, readonly=False
        )
        created.append(rel_path)
    return created


# Contract: Packages self-contained executable runner zipapps into bin_dir with 0o755 permissions and removes stale coverage script.
def package_runner_zipapps(bin_dir: str) -> None:
    """Packages runner zipapps into bin_dir with executable permissions."""
    os.makedirs(bin_dir, exist_ok=True)
    tools = {
        "get_work": "get_work",
        "check_files": "check_files",
        "submit": "submit",
        "blame": "blame",
        "feedback": "blame",
        "fail": "fail",
    }
    cov_path = os.path.join(bin_dir, "coverage")
    # Contract: Removes stale coverage script if present in bin_dir.
    if os.path.isfile(cov_path):
        try:
            os.remove(cov_path)
        except OSError:
            pass
    for tool_name, cmd in tools.items():
        tool_path = os.path.join(bin_dir, tool_name)
        runner_code = f'''import json
import os
import sys

curr = os.getcwd()
main_root = None
ws_dir = curr
while ws_dir and ws_dir != os.path.dirname(ws_dir):
    cfg = os.path.join(ws_dir, "{ROLE_CONFIG_FILE}")
    if os.path.isfile(cfg):
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) == "role_workspaces":
            p_root = os.path.dirname(parent)
            ws_base = os.path.basename(ws_dir)
            for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                if entry != "role_workspaces" and ws_base.startswith(f"{{entry}}_"):
                    cand = os.path.join(p_root, entry)
                    if os.path.isdir(cand):
                        main_root = cand
                        break
        break
    ws_dir = os.path.dirname(ws_dir)

search_roots = [ws_dir, curr]
if main_root:
    search_roots.append(main_root)
for root in search_roots:
    if root and os.path.isdir(root):
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            for entry in os.listdir(root):
                pkg_dir = os.path.join(root, entry)
                if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                    sup_lib = os.path.join(pkg_dir, "support", "lib")
                    if os.path.isdir(sup_lib):
                        if pkg_dir not in sys.path:
                            sys.path.insert(0, pkg_dir)
                        if sup_lib not in sys.path:
                            sys.path.insert(0, sup_lib)
        except OSError:
            pass

try:
    import cleanroom_role_tool
except ImportError:
    import importlib
    cleanroom_role_tool = None
    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for entry in os.listdir(root):
                pkg_dir = os.path.join(root, entry)
                if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                    if os.path.isdir(os.path.join(pkg_dir, "support", "lib")):
                        try:
                            cleanroom_role_tool = importlib.import_module(f"{{entry}}.support.lib.cleanroom_role_tool")
                            break
                        except ImportError:
                            pass
        except OSError:
            pass
        if cleanroom_role_tool is not None:
            break
    if cleanroom_role_tool is None:
        raise

if __name__ == "__main__":
    sys.exit(cleanroom_role_tool.main(["{cmd}"] + sys.argv[1:]))
'''
        with open(tool_path, "wb") as f:
            f.write(b"#!/usr/bin/env python3\n")
            with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("__main__.py", runner_code)
        try:
            os.chmod(tool_path, 0o755)
        except OSError:
            pass


# Contract: Writes role configuration metadata (.cleanroom_role.json) with 0o644 permissions.
def write_role_metadata(
    workspace_dir: str,
    role_name: str,
    dir_scope: str,
    repo_root: Optional[str] = None,
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
    max_feedback_chars: Optional[int] = None,
) -> None:
    """Writes .cleanroom_role.json in workspace root."""
    meta_path = os.path.join(workspace_dir, ROLE_CONFIG_FILE)
    data: Dict[str, Any] = {
        "role": role_name,
        "role_name": role_name,
        "parts_dir": dir_scope,
        "dir_scope": dir_scope,
    }
    if model:
        data["model"] = model
    if batch_size is not None:
        data["batch_size"] = batch_size
    if max_feedback_chars is not None:
        data["max_feedback_chars"] = max_feedback_chars
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    try:
        os.chmod(meta_path, 0o644)
    except OSError:
        pass


# Contract: Synthesizes role-tailored AGENTS.md instructions with boundary rules, tripwires, fail-stop, and workflow.
def write_role_agents_md(
    workspace_dir: str,
    role_def: roles.RoleDefinition,
    dir_scope: str,
) -> None:
    """Generates role AGENTS.md instructions in the workspace."""
    agents_path = os.path.join(workspace_dir, "AGENTS.md")
    is_auditor = not role_def.writable_file_patterns
    guide = role_def.guide_path

    if is_auditor:
        workflow = f"""1. Run `bin/get_work` to synchronize with main and inspect pending dirty units.
2. Read the `# CHANGE:` metadata header in the target file (`lib/*.py` or `tests/*_test.py`) using host file-reading tools to inspect what the author attempted to fix.
3. Follow companion guide `{guide}` to verify target compliance against `low/*.pyi` contracts.
4. Run verification checks: `bin/check_files [target_file]`
5. If checks pass: Submit verification stamp via `bin/submit <target_file>`.
6. If checks fail: Deliver blame attribution via `bin/blame <culprit_file> "<explanation>"`. Your critique MUST reference the author's `# CHANGE:` attempt and explain specifically why the attempted fix did not resolve the defect or what remains broken (DO NOT merely complain in chat without blaming, and DO NOT recycle identical blame text without considering what changed).
7. If target cannot be certified or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
8. Immediately call `bin/get_work` again to drain remaining units until the queue is empty.
"""
        feedback_section = """## Delivering Blame & Feedback (Auditor Role Requirements)
- **Inspect `# CHANGE:` Commit Headers**: Before delivering blame, you MUST inspect the `# CHANGE:` metadata header at the top of the target file (`lib/*.py` or `tests/*_test.py`) using your file-reading tools. The `# CHANGE:` header explains what the author attempted to fix in response to previous feedback.
- **Evaluate Attempted Fixes Against Actual Failures**: Compare what the author attempted against the failures observed in `bin/check_files`. Evaluate whether the attempted fix addressed the cited defect or whether the defect persists under different conditions.
- **Tailor Blame Critiques (DO NOT Blindly Recycle Feedback)**:
  - Your blame explanation MUST explicitly reference the author's `# CHANGE:` attempt.
  - Explain why the attempted fix did not resolve the defect or what remains broken despite the attempt.
  - NEVER recycle identical blame critiques across verification rounds without examining what changed. Tailor your feedback to what remains unaddressed.
- **Actionable Attribution**: Blame the exact culprit file (`lib/*.py` or `tests/*_test.py`). If both implementation and tests are defective, blame each culprit file with specific critiques."""
    else:
        workflow = f"""1. Run `bin/get_work` to inspect and pull pending work and review any unacted feedback.
2. Follow companion guide `{guide}` to author or update targets in scope, resolving any feedback.
3. Run verification checks: `bin/check_files [target_file]`
4. If checks pass and all feedback is resolved: Submit completed targets via `bin/submit <target_file> "<summary>"` (or `bin/submit <target_file>` if unmodified).
5. If upstream contracts are defective: Deliver blame attribution via `bin/blame <culprit_contract> "<explanation>"`.
6. If success is impossible or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
7. Immediately call `bin/get_work` again to drain remaining units until the queue is empty.
"""
        feedback_section = """## Acting on Blame & Feedback (Author Role Requirements)
- **`bin/check_files` ONLY verifies static types and syntax**: It does NOT execute tests or verify runtime logic.
- **Feedback represents runtime test failures or broken behavioral contracts**: Downstream roles (QA, Test, etc.) blame your code when runtime execution or assertions fail.
- **Passing `bin/check_files` does NOT mean the defect is gone**: Never assume that because `bin/check_files` succeeds, the runtime problem cited in feedback "no longer exists" or is "QA's problem later". If you submit without fixing the underlying logic, downstream verification will immediately fail and blame your file again.
- **How to resolve feedback**:
  1. Read the feedback critique in `bin/get_work` carefully to identify the runtime defect.
  2. Inspect the low-level contracts (`low/*.pyi`) and the failing test cases (`tests/*_test.py`) to examine expected behaviors, assertions, and mocks.
  3. Modify the code in `lib/*.py` so that runtime execution satisfies the contracts and passes the tests.
  4. Run `bin/check_files` to verify clean static compilation and typing.
  5. Submit via `bin/submit <target_file> "<summary>"` with a clear change summary explaining how the fix resolves the feedback."""

    content = f"""# Cleanroom Role Instructions: {role_def.role_name.capitalize()}

## Scope & Constraints
- Role: `{role_def.role_name}`
- Directory Scope: `{dir_scope}`
- Companion Guide: `{guide}`

## Mandatory Target Resolution (Do NOT End Turn Without Resolving)
Every pending target acquired via `bin/get_work` MUST be explicitly resolved before concluding your turn:
- **ZERO TOLERANCE FOR COMPLAINING OR IDLING IN CHAT**: When `bin/check_files` fails, stopping with conversational commentary, explaining why output did not change, or complaining without executing `bin/blame` is STRICTLY PROHIBITED. Conversational complaints do not mutate build state, and upstream authoring roles cannot inspect chat transcripts.
- **Actionable Blame Delivery**: When checks fail due to defects in library code, test code, or upstream specifications, you MUST execute `bin/blame <culprit_file> "<actionable critique>"` immediately. Auditors can blame both the lib and test files if both contain defects.
- **Submission on Success**: When checks pass, you MUST execute `bin/submit <target_file>` immediately.
- **Fail on Impasse**: If you reach an unresolvable impasse where neither submit nor blame applies, execute `bin/fail <target_file> "<reason>"` immediately.
- **Never end a turn or stop tool usage while pending units remain unresolved.**

## Strict Boundary Rules (Zero Exceptions)
1. **Workspace Boundary**: All commands and tool invocations MUST execute strictly within this workspace directory (`.`). You are strictly prohibited from passing any other directory as `Cwd` or running commands outside this workspace.
2. **Git Operations Prohibited**: This is a projected cleanroom workspace, not a git repository. Never invoke `git` commands (`git checkout`, `git restore`, `git reset`, etc.) under any circumstances.
3. **Main Repository Inviolability**: The main workspace is strictly read-only and off-limits to direct agent actions. All interaction with main occurs exclusively through the prescribed `bin/` tools.
4. **Metadata Inviolability**: DO NOT EDIT METADATA. Never manually edit `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools (`bin/submit`, `bin/blame`, `bin/fail`).

## In-Workspace File Reading & Inspection (Fully Permitted & Required)
You ARE permitted and expected to read files WITHIN your assigned role workspace directory (`.`) using your host file-reading tools (e.g. `view_file`, `read_file`, or IDE inspection):
- **Inspect Specifications**: Read low-level interface specifications (`low/*.pyi`) and guides to understand contracted behavior and requirements.
- **Inspect Test Suites**: Read test files (`tests/*_test.py`) to examine assertions, failure expectations, test structures, and mocks.
- **Inspect Implementation Code**: Read implementation code (`lib/*.py`) to triage failures, locate exact function names and defective line numbers, and inspect the `# CHANGE:` commit header to understand how the author attempted to address previous blame.
The Contamination Tripwire applies strictly to reading files OUTSIDE this workspace. Reading any file within `.` is 100% safe, encouraged, and required for thorough diagnosis.

## Command Execution Tripwire (Restricted Binaries Only)
**ZERO TOLERANCE FOR UNAPPROVED COMMANDS.**

In the terminal / shell, you are strictly permitted to run ONLY the prescribed workspace binaries:
- `bin/get_work`
- `bin/check_files`
- `bin/submit`
- `bin/blame`
- `bin/fail`

Executing ANY other command, shell script, or binary in the terminal (including but not limited to `python`, `python3`, `bash`, `sh`, `find`, `grep`, `git`, `cat`, or inspecting zipapps/executables) is STRICTLY PROHIBITED. (Note: Using your host environment's native file-viewing tool to read local files in this workspace is NOT a shell command and is fully permitted). If you execute any unapproved terminal command:
1. **YOU ARE PERMANENTLY CONTAMINATED.**
2. **ALL WORK MUST CEASE IMMEDIATELY.**
3. **IMMEDIATE ABORT**: Report the unapproved command execution to the user and stop all tool usage:
   > `CRITICAL CONTAMINATION: I executed an unapproved command outside the prescribed bin/ tools ([command]). This session is compromised and terminated.`

## Contamination Tripwire (Poison Pill)
**ZERO TOLERANCE FOR READING OUT-OF-BOUNDS FILES.**

If you read ANY file outside of your assigned role workspace (such as in `../../`, the canonical main repository, or other role workspaces via ANY tool or mechanism):
1. **YOU ARE PERMANENTLY CONTAMINATED.**
2. **ALL WORK MUST CEASE IMMEDIATELY.** You are strictly prohibited from performing any further work, authoring code, modifying files, running verification checks, or submitting targets (`bin/submit`).
3. **IMMEDIATE ABORT**: Your ONLY permitted action is to immediately report the exact contamination to the user and STOP all tool usage:
   > `CRITICAL CONTAMINATION: I read a file outside my assigned role workspace ([path]). This session is compromised and terminated.`

This is an absolute tripwire for out-of-bounds files. There are NO exceptions for debugging, diagnosing tracebacks, inspecting imports, or reading dependencies outside this workspace. (Reading files inside this workspace directory is 100% permitted).

{feedback_section}

## Fail-Stop & Reporting Protocol (Do NOT Self-Heal)
If any cleanroom binary (`bin/get_work`, `bin/check_files`, `bin/blame`, `bin/submit`, `bin/fail`) fails due to:
- A Python exception or traceback (e.g., `ModuleNotFoundError`, `ImportError`, `AttributeError`)
- A build, type check, or test execution failure
- A missing support file, template error, or dependency issue

**STOP IMMEDIATELY.**
- **DO NOT** attempt to fix, patch, restore, or work around the infrastructure.
- **DO NOT** create, undelete, or check out missing files.
- **DO NOT** attempt alternate execution paths outside `bin/`.
- **REPORT IMMEDIATELY**: Output the exact command that failed and its verbatim error/traceback to the user, state what dependency or file appears to be missing, and wait for human instruction.

NOTE: Verification test failures (e.g. `[FAIL] Verification failed` output from tests or linters on code under test) are NORMAL test results to be acted upon via `bin/blame`, `bin/fail`, or code edits, NOT infrastructure crashes. Fail-Stop applies ONLY to internal tool crashes, tracebacks, or missing tooling/dependencies.

## Unresolvable Impasse & Failure Protocol
If you determine that success is not possible (e.g. unreachable code under test, contradictory specification contracts, or dead ends that blame cannot resolve):
1. **DO NOT** attempt ad-hoc debugging, script execution, or reverse-engineering of cleanroom tools.
2. Execute: `bin/fail <target_file> "<reason>"`
3. Report failure to the coordinator via `send_message`: `FAILED: <target_file> - <reason>`
4. Cease work immediately.

## Standard Workflow
{workflow}
"""
    with open(agents_path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(agents_path, 0o644)
    except OSError:
        pass


# Contract: Realizes scaffold.WorkspaceScaffolder singleton.
class WorkspaceScaffolder(
    scaffold.WorkspaceScaffolder,
    Singleton,
):
    """Realizes runner zipapp packaging, role metadata, guide synthesis, and starter skeletons."""

    tier = agent_session.agent_session

    # Contract: Packages runner zipapps into bin_dir with executable permissions.
    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        package_runner_zipapps(bin_dir)

    # Contract: Writes role configuration metadata (.cleanroom_role.json) in workspace root.
    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
    ) -> None:
        write_role_metadata(
            workspace_dir,
            role_name,
            dir_scope,
            repo_root=repo_root,
            model=model,
            batch_size=batch_size,
            max_feedback_chars=max_feedback_chars,
        )

    # Contract: Synthesizes role-tailored AGENTS.md instructions in workspace root.
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: roles.RoleDefinition,
        dir_scope: str,
    ) -> None:
        write_role_agents_md(workspace_dir, role_def, dir_scope)

    # Contract: Creates starter skeletons for declared writable targets absent from disk.
    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: roles.RoleDefinition,
    ) -> List[str]:
        return _create_missing_target_skeletons(
            workspace_dir, repo_root, dir_scope, role_def
        )

    # Contract: Writes text content to destination file and applies exact permissions.
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        write_file_with_perms(dst, content, readonly=readonly, executable=executable)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceScaffolder,
        keys=[WorkspaceScaffolder, scaffold.WorkspaceScaffolder],
        tier=WorkspaceScaffolder.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
