# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: remove dependency on workspace_provision_impl
# CODE_HASH: 181162630951
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_sync_impl."""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import zipfile
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import src_metadata
from . import workspace_registry, workspace_sync


BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
AUDIT_BUFFER_FILE = ".cleanroom_audit_buffer.json"
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


def _package_runner_zipapps(bin_dir: str) -> None:
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


def _write_role_agents_md(
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


class WorkspaceSynchronizer(
    workspace_sync.WorkspaceSynchronizer,
    Singleton,
):
    """Realizes two-phase harvesting, inbound pulling, and blame flushing."""

    tier = agent_session.agent_session

    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        registry = get_singleton(
            workspace_registry.WorkspaceRegistry
        )
        role_def = registry.resolve_role_definition(role_name, main_root)

        main_scope_dir = os.path.join(main_root, dir_scope)
        ws_scope_dir = os.path.join(workspace_dir, dir_scope)
        if not os.path.isdir(main_scope_dir):
            return 0

        pulled_count = 0
        all_patterns = list(role_def.writable_file_patterns) + list(
            role_def.readonly_file_patterns
        )
        main_files = _find_matching_files(main_scope_dir, all_patterns)

        for rel in main_files:
            src_f = os.path.join(main_scope_dir, rel)
            dst_f = os.path.join(ws_scope_dir, rel)
            is_writable = any(
                fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(os.path.basename(rel), p)
                for p in role_def.writable_file_patterns
            )

            needs_copy = False
            if not os.path.isfile(dst_f):
                needs_copy = True
            else:
                try:
                    with open(src_f, "rb") as sf, open(dst_f, "rb") as df:
                        if sf.read() != df.read():
                            needs_copy = True
                except OSError:
                    needs_copy = True

            if needs_copy:
                copy_file_with_perms(src_f, dst_f, readonly=not is_writable)
                pulled_count += 1

        return pulled_count

    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        registry = get_singleton(
            workspace_registry.WorkspaceRegistry
        )
        role_def = registry.resolve_role_definition(role_name, main_root)
        refreshed_count = 0

        for cfg_name in ("MODULE.bazel", "BUILD.bazel", ".bazelversion", "pyrightconfig.json"):
            cfg_src = os.path.join(main_root, cfg_name)
            if os.path.isfile(cfg_src):
                cfg_dst = os.path.join(workspace_dir, cfg_name)
                copy_file_with_perms(cfg_src, cfg_dst, readonly=True)
                refreshed_count += 1

        if role_def.guide_path:
            guide_src = os.path.join(main_root, role_def.guide_path)
            if os.path.isfile(guide_src):
                guide_dst = os.path.join(workspace_dir, role_def.guide_path)
                copy_file_with_perms(guide_src, guide_dst, readonly=True)
                refreshed_count += 1

        bin_dir = os.path.join(workspace_dir, "bin")
        _package_runner_zipapps(bin_dir)
        _write_role_agents_md(workspace_dir, role_def, dir_scope)
        refreshed_count += 6

        meta_path = os.path.join(workspace_dir, ROLE_CONFIG_FILE)
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                meta_data["main_workspace_root"] = main_root
                meta_data["repo_root"] = main_root
                if not meta_data.get("role"):
                    meta_data["role"] = role_name
                if not meta_data.get("dir_scope"):
                    meta_data["dir_scope"] = dir_scope
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)
                    f.write("\n")
                refreshed_count += 1
            except Exception:
                pass

        return refreshed_count

    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]:
        blame_path = os.path.join(workspace_dir, BLAME_BUFFER_FILE)
        if not os.path.isfile(blame_path):
            return ()

        try:
            with open(blame_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            return ()

        if not isinstance(entries, list) or not entries:
            return ()

        flushed: List[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            target = entry.get("target", "").lstrip("/")
            explanation = entry.get("explanation", "")
            blamed_by = entry.get("blamed_by", "role workspace")
            dirty_reason = entry.get("dirty_reason") or f"Blamed by {blamed_by}: {explanation}"

            target_path = os.path.join(main_root, target)
            if not os.path.isfile(target_path):
                # Search within subdirectories of main_root
                found = None
                for r, _, files in os.walk(main_root):
                    if os.path.basename(target) in files:
                        cand = os.path.join(r, os.path.basename(target))
                        if cand.endswith(target):
                            found = cand
                            break
                if found:
                    target_path = found

            if os.path.isfile(target_path):
                src_metadata.mark_dirty(target_path, reason=dirty_reason)
                src_metadata.append_feedback(target_path, explanation, sender=blamed_by)
                flushed.append(target)

        try:
            with open(blame_path, "w", encoding="utf-8") as f:
                json.dump([], f)
                f.write("\n")
        except OSError:
            pass

        return flushed

    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> workspace_sync.SyncResult:
        registry = get_singleton(
            workspace_registry.WorkspaceRegistry
        )
        role_def = registry.resolve_role_definition(role_name, main_root)

        flushed_blames = list(self.flush_blame_buffer(workspace_dir, main_root))
        stamped_audits: List[str] = []
        harvested_count = 0

        audit_path = os.path.join(workspace_dir, AUDIT_BUFFER_FILE)
        if os.path.isfile(audit_path):
            try:
                with open(audit_path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            t = entry.get("target", "").lstrip("/")
                            t_path = os.path.join(main_root, t)
                            if os.path.isfile(t_path):
                                tag = entry.get("audit_tag") or role_def.audit_tag or role_name
                                src_metadata.stamp_audit(t_path, tag)
                                stamped_audits.append(t)
                with open(audit_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                    f.write("\n")
            except Exception:
                pass

        ws_scope_dir = os.path.join(workspace_dir, dir_scope)
        main_scope_dir = os.path.join(main_root, dir_scope)

        if os.path.isdir(ws_scope_dir):
            writable_files = _find_matching_files(
                ws_scope_dir, role_def.writable_file_patterns
            )
            for rel in writable_files:
                ws_f = os.path.join(ws_scope_dir, rel)
                main_f = os.path.join(main_scope_dir, rel)

                is_modified = False
                if not os.path.isfile(main_f):
                    is_modified = True
                else:
                    try:
                        with open(ws_f, "rb") as wf, open(main_f, "rb") as mf:
                            if wf.read() != mf.read():
                                is_modified = True
                    except OSError:
                        is_modified = True

                if is_modified:
                    copy_file_with_perms(ws_f, main_f, readonly=False)
                    meta = src_metadata.extract_metadata(ws_f)
                    change = meta.change_summary if meta else "harvested changes"
                    src_metadata.record_change(main_f, change)
                    src_metadata.mark_clean(main_f)
                    if role_def.audit_tag:
                        src_metadata.stamp_audit(main_f, role_def.audit_tag)
                        stamped_audits.append(rel)
                    harvested_count += 1

        return workspace_sync.SyncResult(
            pulled_files=0,
            harvested_files=harvested_count,
            stamped_audits=stamped_audits,
            flushed_blames=flushed_blames,
        )
