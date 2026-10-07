# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 77e8d9f5fef6
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_provision_impl."""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import sys
import zipfile
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_session
from . import workspace_provision, workspace_registry


BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
ROLE_CONFIG_FILE = ".cleanroom_role.json"


def copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
    """Copies a file and applies exact read-only or read-write permissions."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o644)
        except OSError:
            pass
    shutil.copy2(src, dst)
    if executable:
        mode = 0o555 if readonly else 0o755
    else:
        mode = 0o444 if readonly else 0o644
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def package_runner_zipapps(bin_dir: str) -> None:
    """Packages runner zipapps into bin_dir with executable permissions."""
    os.makedirs(bin_dir, exist_ok=True)
    tools = {
        "get_work": "get_work",
        "submit": "submit",
        "blame": "blame",
        "fail": "fail",
        "coverage": "coverage",
    }
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
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                meta = json.load(f)
                main_root = meta.get("main_workspace_root") or meta.get("repo_root")
        except Exception as e:
            sys.stderr.write(f"Warning: Failed parsing role config '{{cfg}}': {{e}}\\n")
        break
    ws_dir = os.path.dirname(ws_dir)

search_roots = [ws_dir, curr]
if main_root:
    search_roots.append(main_root)
for root in search_roots:
    if root and os.path.isdir(root):
        for p in [
            root,
            os.path.join(root, "update_with_ai"),
            os.path.join(root, "update_python_with_ai"),
            os.path.join(root, "update_with_ai/support/lib"),
            os.path.join(root, "update_python_with_ai/support/lib"),
        ]:
            if os.path.isdir(p):
                if p in sys.path:
                    sys.path.remove(p)
                sys.path.insert(0, p)

try:
    from update_with_ai.support.lib import cleanroom_role_tool
except ImportError:
    import cleanroom_role_tool

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


def write_role_metadata(
    workspace_dir: str, role_name: str, dir_scope: str, repo_root: str
) -> None:
    """Writes .cleanroom_role.json in workspace root."""
    meta_path = os.path.join(workspace_dir, ROLE_CONFIG_FILE)
    data = {
        "role": role_name,
        "role_name": role_name,
        "parts_dir": dir_scope,
        "dir_scope": dir_scope,
        "main_workspace_root": repo_root,
        "repo_root": repo_root,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    try:
        os.chmod(meta_path, 0o644)
    except OSError:
        pass


def write_role_agents_md(
    workspace_dir: str,
    role_def: workspace_registry.RoleDefinition,
    dir_scope: str,
) -> None:
    """Generates role AGENTS.md instructions in the workspace."""
    agents_path = os.path.join(workspace_dir, "AGENTS.md")
    is_auditor = not role_def.writable_file_patterns
    guide = role_def.guide_path

    if is_auditor:
        workflow = f"""1. Run `bin/get_work` to synchronize with main and inspect pending dirty units.
2. Follow companion guide `{guide}` to verify target compliance.
3. Submit verification stamp: `bin/submit <target_file>`
4. Blame defects if discovered: `bin/blame <culprit_file> "<explanation>"`
"""
    else:
        workflow = f"""1. Run `bin/get_work` to inspect and pull pending work.
2. Follow companion guide `{guide}` to author or update targets in scope.
3. Run verification suite to validate changes.
4. Submit completed targets: `bin/submit <target_file>`
5. If upstream contracts are defective: `bin/blame <culprit_contract> "<explanation>"`
"""

    content = f"""# Cleanroom Role Instructions: {role_def.role_name.capitalize()}

## Scope & Constraints
- Role: `{role_def.role_name}`
- Directory Scope: `{dir_scope}`
- Companion Guide: `{guide}`

## Strict Boundary Rules (Zero Exceptions)
1. **Workspace Boundary**: All commands and tool invocations MUST execute strictly within this workspace directory (`.`). You are strictly prohibited from passing any other directory (such as `main_workspace_root` or `../cleanroom`) as `Cwd` or running commands outside this workspace.
2. **Git Operations Prohibited**: This is a projected cleanroom workspace, not a git repository. Never invoke `git` commands (`git checkout`, `git restore`, `git reset`, etc.) under any circumstances.
3. **Main Repository Inviolability**: The main workspace is strictly read-only and off-limits to direct agent actions. All interaction with main occurs exclusively through the prescribed `bin/` tools.

## Fail-Stop & Reporting Protocol (Do NOT Self-Heal)
If any cleanroom binary (`bin/get_work`, `bin/coverage`, `bin/blame`, `bin/submit`) fails due to:
- A Python exception or traceback (e.g., `ModuleNotFoundError`, `ImportError`, `AttributeError`)
- A Bazel analysis or execution failure
- A missing support file, template error, or dependency issue

**STOP IMMEDIATELY.**
- **DO NOT** attempt to fix, patch, restore, or work around the infrastructure.
- **DO NOT** create, undelete, or check out missing files.
- **DO NOT** attempt alternate execution paths outside `bin/`.
- **REPORT IMMEDIATELY**: Output the exact command that failed and its verbatim error/traceback to the user, state what dependency or file appears to be missing, and wait for human instruction.

## Standard Workflow
{workflow}
"""
    with open(agents_path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(agents_path, 0o644)
    except OSError:
        pass


def _find_matching_files(root_dir: str, patterns: Sequence[str]) -> List[str]:
    """Finds relative file paths matching glob patterns within root_dir."""
    results: List[str] = []
    if not os.path.isdir(root_dir):
        return results
    for r, _, files in os.walk(root_dir):
        for f in files:
            full_path = os.path.join(r, f)
            rel_path = os.path.relpath(full_path, root_dir)
            if any(
                fnmatch.fnmatch(rel_path, p)
                or fnmatch.fnmatch(rel_path, f"*/{p}")
                or fnmatch.fnmatch(rel_path, f"*{p}")
                or fnmatch.fnmatch(f, p)
                for p in patterns
            ):
                results.append(rel_path)
    return results


class WorkspaceProvisioner(
    workspace_provision.WorkspaceProvisioner,
    Singleton,
):
    """Realizes role workspace directory provisioning, permissions, and runner deployment."""

    tier = agent_session.agent_session

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> workspace_registry.WorkspaceDescriptor:
        registry = get_singleton(
            workspace_registry.WorkspaceRegistry
        )
        resolved_root = registry.discover_repository_root(repo_root)
        role_def = registry.resolve_role_definition(role_name, resolved_root)
        workspace_dir = registry.compute_workspace_dir(
            role_name, dir_scope, resolved_root, custom_dest
        )

        os.makedirs(workspace_dir, exist_ok=True)
        bin_dir = os.path.join(workspace_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)

        scope_dir = os.path.join(resolved_root, dir_scope)
        if os.path.isdir(scope_dir):
            for dirpath, _, filenames in os.walk(scope_dir):
                rel_d = os.path.relpath(dirpath, scope_dir)
                ws_d = (
                    os.path.join(workspace_dir, dir_scope, rel_d)
                    if rel_d != "."
                    else os.path.join(workspace_dir, dir_scope)
                )
                os.makedirs(ws_d, exist_ok=True)
                if "BUILD.bazel" in filenames:
                    copy_file_with_perms(
                        os.path.join(dirpath, "BUILD.bazel"),
                        os.path.join(ws_d, "BUILD.bazel"),
                        readonly=True,
                    )
            writable_rel = _find_matching_files(
                scope_dir, role_def.writable_file_patterns
            )
            for rel in writable_rel:
                src_f = os.path.join(scope_dir, rel)
                dst_f = os.path.join(workspace_dir, dir_scope, rel)
                copy_file_with_perms(src_f, dst_f, readonly=False)

            readonly_rel = _find_matching_files(
                scope_dir, role_def.readonly_file_patterns
            )
            for rel in readonly_rel:
                src_f = os.path.join(scope_dir, rel)
                dst_f = os.path.join(workspace_dir, dir_scope, rel)
                copy_file_with_perms(src_f, dst_f, readonly=True)

        if role_def.guide_path:
            guide_src = os.path.join(resolved_root, role_def.guide_path)
            if os.path.isfile(guide_src):
                guide_dst = os.path.join(workspace_dir, role_def.guide_path)
                copy_file_with_perms(guide_src, guide_dst, readonly=True)

        for cfg_name in ("MODULE.bazel", "BUILD.bazel", ".bazelversion", "pyrightconfig.json"):
            cfg_src = os.path.join(resolved_root, cfg_name)
            if os.path.isfile(cfg_src):
                cfg_dst = os.path.join(workspace_dir, cfg_name)
                copy_file_with_perms(cfg_src, cfg_dst, readonly=True)

        package_runner_zipapps(bin_dir)
        write_role_metadata(workspace_dir, role_def.role_name, dir_scope, resolved_root)
        write_role_agents_md(workspace_dir, role_def, dir_scope)

        descriptor = workspace_registry.WorkspaceDescriptor(
            workspace_dir=workspace_dir,
            main_repository_root=resolved_root,
            directory_scope=dir_scope,
            role_definition=role_def,
        )
        registry.record_workspace(descriptor, resolved_root)
        return descriptor

    def decommission(
        self,
        role_name_or_dir: str,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        registry = get_singleton(
            workspace_registry.WorkspaceRegistry
        )
        resolved_root = registry.discover_repository_root(repo_root)

        if os.path.isabs(role_name_or_dir) or os.path.isdir(role_name_or_dir):
            workspace_dir = os.path.abspath(role_name_or_dir)
        else:
            workspace_dir = registry.compute_workspace_dir(
                role_name_or_dir,
                dir_scope or "staging",
                resolved_root,
                custom_dest,
            )

        if not os.path.exists(workspace_dir):
            registry.unregister_workspace(workspace_dir, resolved_root)
            return True

        if not force:
            blame_buf = os.path.join(workspace_dir, BLAME_BUFFER_FILE)
            if os.path.isfile(blame_buf) and os.path.getsize(blame_buf) > 0:
                try:
                    with open(blame_buf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        raise RuntimeError(
                            f"Refusing to decommission dirty workspace: unharvested blame entries in {blame_buf}"
                        )
                except json.JSONDecodeError:
                    pass

            for r, _, files in os.walk(workspace_dir):
                for f in files:
                    ws_f = os.path.join(r, f)
                    rel = os.path.relpath(ws_f, workspace_dir)
                    if (
                        f.startswith(".")
                        or f == "AGENTS.md"
                        or f == "BUILD.bazel"
                        or rel.startswith("bin" + os.sep)
                        or rel == "bin"
                    ):
                        continue
                    main_f = os.path.join(resolved_root, rel)
                    if not os.path.isfile(main_f):
                        raise RuntimeError(
                            f"Refusing to decommission dirty workspace: untracked file {rel}"
                        )
                    try:
                        with open(ws_f, "rb") as wf, open(main_f, "rb") as mf:
                            if wf.read() != mf.read():
                                raise RuntimeError(
                                    f"Refusing to decommission dirty workspace: unharvested modifications in {rel}"
                                )
                    except OSError:
                        pass

        for r, dirs, files in os.walk(workspace_dir):
            for d in dirs:
                try:
                    os.chmod(os.path.join(r, d), 0o755)
                except OSError:
                    pass
            for f in files:
                try:
                    os.chmod(os.path.join(r, f), 0o644)
                except OSError:
                    pass

        shutil.rmtree(workspace_dir, ignore_errors=True)
        registry.unregister_workspace(workspace_dir, resolved_root)
        return True
