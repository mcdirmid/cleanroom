# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-08T18:30:00Z
# CHANGE: synthesize read-only test stubs for stub role dependencies
# CODE_HASH: 0cf1f1da29d6
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_provision_impl."""

from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
import shutil
import sys
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_session
from . import workspace_provision, workspace_registry


BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
ROLE_CONFIG_FILE = ".cleanroom_role.json"


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


def _is_stub_dep_file(
    rel_path: str,
    role_def: workspace_registry.RoleDefinition,
    repo_root: Optional[str] = None,
) -> bool:
    """Returns True if rel_path matches any role in stub_role_deps."""
    if not role_def.stub_role_deps:
        return False
    fname = os.path.basename(rel_path)
    if fname in ("BUILD.bazel", "__init__.py"):
        return False
    registry = get_singleton(workspace_registry.WorkspaceRegistry)
    root = repo_root or "."
    for stub_target in role_def.stub_role_deps:
        try:
            stub_def = registry.resolve_role_definition(stub_target, root)
        except (KeyError, ValueError, RuntimeError, OSError):
            continue
        parent = os.path.basename(os.path.dirname(rel_path))
        if stub_def.writable_file_patterns:
            for pat in stub_def.writable_file_patterns:
                if (
                    fnmatch.fnmatch(rel_path, pat)
                    or fnmatch.fnmatch(rel_path, f"*/{pat}")
                    or fnmatch.fnmatch(rel_path, f"*{pat}")
                    or fnmatch.fnmatch(fname, pat)
                ):
                    return True
        if stub_def.src_pattern:
            if "{unit_dir}/lib/" in stub_def.src_pattern and parent == "lib" and fname.endswith(".py"):
                return True
    return False


def _get_part_module_map(
    repo_root: str,
    parts_bases: Sequence[str],
) -> Dict[str, Tuple[str, str]]:
    """Maps module name -> (part_name, base_dir) across specified parts directories."""
    mapping: Dict[str, Tuple[str, str]] = {}
    for base in parts_bases:
        parts_dir = (
            os.path.join(repo_root, base, "parts")
            if not base.endswith("parts")
            else os.path.join(repo_root, base)
        )
        if not os.path.isdir(parts_dir):
            continue
        try:
            for p in os.listdir(parts_dir):
                p_dir = os.path.join(parts_dir, p)
                if not os.path.isdir(p_dir) or p.startswith("."):
                    continue
                try:
                    with os.scandir(p_dir) as it:
                        for entry in it:
                            if (
                                entry.is_dir()
                                and not entry.name.startswith(".")
                                and not entry.name.startswith("_")
                            ):
                                try:
                                    for f in os.listdir(entry.path):
                                        if f.endswith(".py") or f.endswith(".pyi"):
                                            mod_name = f.rsplit(".", 1)[0]
                                            mapping[mod_name] = (p, base)
                                except OSError:
                                    pass
                except OSError:
                    pass
        except OSError:
            pass
    return mapping


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
        for base in ("update_with_ai", "update_python_with_ai"):
            for spec_dir in ("low", "grounding"):
                candidate = os.path.join(
                    main_root, base, "parts", part_name, spec_dir, f"{stem}.pyi"
                )
                if os.path.isfile(candidate):
                    return candidate
    return None


def _is_valid_test_stub(file_path: str) -> bool:
    """Checks whether file_path is already a valid cleanroom test stub."""
    if not os.path.isfile(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(500)
            return "CLEANROOM TEST STUB v4" in content
    except OSError:
        return False


def _generate_readonly_test_stub(
    pyi_path: Optional[str],
    stem: str,
    out_path: str,
    dep_dir: str = "lib",
    part_map: Optional[Dict[str, Tuple[str, str]]] = None,
) -> None:
    """Generates a read-only dependency stub from a .pyi specification."""
    parts_split = out_path.split(os.sep)
    current_base = "update_with_ai"
    current_part = ""
    if "parts" in parts_split:
        idx = parts_split.index("parts")
        if idx > 0:
            current_base = parts_split[idx - 1]
        if idx + 1 < len(parts_split):
            current_part = parts_split[idx + 1]

    skeleton: Optional[str] = None
    if pyi_path and os.path.isfile(pyi_path):
        try:
            try:
                from update_python_with_ai.support.lib.lib_lint import generate_lib_skeleton
            except ImportError:
                try:
                    from support.lib.lib_lint import generate_lib_skeleton
                except ImportError:
                    from update_with_ai.support.lib.lib_lint import generate_lib_skeleton
            skeleton = generate_lib_skeleton(pyi_path, stem, parts_base=current_base)
        except (ImportError, OSError, SyntaxError, RuntimeError, ValueError):
            skeleton = None

    if skeleton is None:
        stub_lines = [
            "from __future__ import annotations",
            f"# Requirements specified in {stem}.pyi",
            "# CLEANROOM TEST STUB v4: Implementation details omitted. Refer strictly to companion .pyi file.",
            "",
            f'raise NotImplementedError("Cleanroom Test Stub: {stem}")\n',
        ]
        write_file_with_perms(out_path, "\n".join(stub_lines), readonly=True)
        return

    lifecycle_names: Set[str] = set()
    if pyi_path and os.path.isfile(pyi_path):
        try:
            with open(pyi_path, "r", encoding="utf-8") as f:
                pyi_tree = ast.parse(f.read(), filename=pyi_path)
            for node in pyi_tree.body:
                if isinstance(node, ast.ImportFrom) and node.module in (
                    "support.lib.lifecycle",
                    "lifecycle",
                ):
                    for a in node.names:
                        lifecycle_names.add(a.name)
        except (OSError, SyntaxError, TypeError, ValueError):
            pass

    if part_map is None:
        if f"{os.sep}parts{os.sep}" in out_path:
            root_dir = out_path.split(f"{os.sep}parts{os.sep}")[0]
            root_parent = os.path.dirname(root_dir)
            part_map = _get_part_module_map(
                root_parent, [current_base, "update_with_ai", "update_python_with_ai"]
            )
        else:
            part_map = {}

    spec_name = os.path.basename(pyi_path) if pyi_path else f"{stem}.pyi"
    stub_lines = [
        "from __future__ import annotations",
    ]
    if lifecycle_names:
        stub_lines.append(
            f"from support.lib.lifecycle import {', '.join(sorted(lifecycle_names))}"
        )
    stub_lines.extend(
        [
            f"# Requirements specified in {spec_name}",
            "# CLEANROOM TEST STUB v4: Implementation details omitted. Refer strictly to companion .pyi file.",
            "",
        ]
    )

    for line in skeleton.splitlines():
        if line.startswith("from __future__") or line.startswith("# Requirements"):
            continue
        if (
            line.strip() == "from dataclasses import dataclass"
            and ("field(" in skeleton or "field:" in skeleton)
        ):
            line = "from dataclasses import dataclass, field"
        m = re.match(
            r"^import\s+([a-zA-Z0-9_]+)(?:\s+as\s+([a-zA-Z0-9_]+))?$", line.strip()
        )
        if m:
            mod_name = m.group(1)
            alias = f" as {m.group(2)}" if m.group(2) else ""
            if mod_name in part_map:
                target_part, _ = part_map[mod_name]
                if target_part == current_part:
                    line = f"from . import {mod_name}{alias}"
                else:
                    line = f"from {current_base}.parts.{target_part}.{dep_dir} import {mod_name}{alias}"
        m_from = re.match(
            r"^from\s+([a-zA-Z0-9_]+)\s+import\s+(.+)$", line.strip()
        )
        if m_from:
            mod_name = m_from.group(1)
            names_part = m_from.group(2)
            if mod_name in part_map:
                target_part, _ = part_map[mod_name]
                if target_part == current_part:
                    line = f"from .{mod_name} import {names_part}"
                else:
                    line = f"from {current_base}.parts.{target_part}.{dep_dir}.{mod_name} import {names_part}"
        if re.search(r"\bparts\.", line):
            line = re.sub(
                r"\b(?:[a-zA-Z0-9_]+\.)?parts\.", f"{current_base}.parts.", line
            )
        if line.strip().startswith("# TODO_"):
            continue
        if line.strip() == "raise NotImplementedError":
            indent = " " * (len(line) - len(line.lstrip()))
            stub_lines.append(
                f'{indent}raise NotImplementedError("Cleanroom Test Stub: Behavior specified in .pyi")'
            )
        else:
            stub_lines.append(line)

    if pyi_path and os.path.isfile(pyi_path):
        try:
            with open(pyi_path, "r", encoding="utf-8") as f:
                pyi_tree = ast.parse(f.read(), filename=pyi_path)
            for node in pyi_tree.body:
                if isinstance(node, ast.FunctionDef):
                    fn_name = node.name
                    if not any(f"def {fn_name}" in l for l in stub_lines):
                        args_unp = ast.unparse(node.args)
                        ret_ann = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                        stub_lines.append(f"def {fn_name}({args_unp}){ret_ann}:")
                        stub_lines.append('    raise NotImplementedError("Cleanroom Test Stub: Behavior specified in .pyi")')
                        stub_lines.append("")
        except (OSError, SyntaxError, TypeError, ValueError):
            pass

    write_file_with_perms(out_path, "\n".join(stub_lines) + "\n", readonly=True)


def _sync_all_stub_deps(
    ws_scope_dir: str,
    main_scope_dir: str,
    role_def: workspace_registry.RoleDefinition,
    main_root: str,
    dir_scope: str,
    part_map: Optional[Dict[str, Tuple[str, str]]] = None,
) -> int:
    """Synchronizes read-only test stubs for all stub_role_deps."""
    if not role_def.stub_role_deps or not os.path.isdir(main_scope_dir):
        return 0
    if part_map is None:
        part_map = _get_part_module_map(
            main_root, [dir_scope, "update_with_ai", "update_python_with_ai"]
        )

    synced_count = 0
    registry = get_singleton(workspace_registry.WorkspaceRegistry)

    for stub_target in role_def.stub_role_deps:
        try:
            stub_def = registry.resolve_role_definition(stub_target, main_root)
        except (KeyError, ValueError, RuntimeError, OSError):
            continue
        dep_dir = "lib"
        if stub_def.src_pattern:
            parts = stub_def.src_pattern.split("/")
            if len(parts) >= 2:
                dep_dir = parts[-2]

        main_parts_dir = os.path.join(main_scope_dir, "parts")
        ws_parts_dir = os.path.join(ws_scope_dir, "parts")
        if not os.path.isdir(main_parts_dir):
            for cand in ("update_with_ai", "update_python_with_ai"):
                cand_p = os.path.join(main_root, cand, "parts")
                if os.path.isdir(cand_p):
                    main_parts_dir = cand_p
                    break
        if not os.path.isdir(main_parts_dir):
            continue

        if os.path.isdir(ws_parts_dir):
            for part_name in os.listdir(ws_parts_dir):
                part_ws_dep = os.path.join(ws_parts_dir, part_name, dep_dir)
                part_main = os.path.join(main_parts_dir, part_name)
                if not os.path.isdir(part_ws_dep):
                    continue
                for fname in os.listdir(part_ws_dep):
                    if fname in ("BUILD.bazel", "__init__.py") or not fname.endswith(".py"):
                        continue
                    stem = os.path.splitext(fname)[0]
                    ws_f = os.path.join(part_ws_dep, fname)
                    pyi_path = _find_spec_pyi(part_main, stem, main_root=main_root)
                    if pyi_path is None or not os.path.isfile(pyi_path):
                        try:
                            os.chmod(ws_f, 0o644)
                            os.remove(ws_f)
                            synced_count += 1
                        except OSError:
                            pass
                    else:
                        is_stub = _is_valid_test_stub(ws_f)
                        needs_gen = not is_stub
                        if is_stub:
                            try:
                                if os.path.getmtime(pyi_path) > os.path.getmtime(ws_f):
                                    needs_gen = True
                            except OSError:
                                pass
                        if needs_gen:
                            _generate_readonly_test_stub(
                                pyi_path, stem, ws_f, dep_dir=dep_dir, part_map=part_map
                            )
                            synced_count += 1

        for part_name in os.listdir(main_parts_dir):
            part_main = os.path.join(main_parts_dir, part_name)
            if not os.path.isdir(part_main) or part_name.startswith("."):
                continue
            low_dir = os.path.join(part_main, "low")
            if not os.path.isdir(low_dir):
                continue
            ws_dep_dir = os.path.join(ws_parts_dir, part_name, dep_dir)
            os.makedirs(ws_dep_dir, exist_ok=True)

            main_dep_dir = os.path.join(part_main, dep_dir)
            if os.path.isdir(main_dep_dir):
                for meta_f in ("BUILD.bazel", "__init__.py"):
                    src_meta = os.path.join(main_dep_dir, meta_f)
                    dst_meta = os.path.join(ws_dep_dir, meta_f)
                    if os.path.isfile(src_meta) and not os.path.isfile(dst_meta):
                        copy_file_with_perms(src_meta, dst_meta, readonly=True)

            for spec_f in os.listdir(low_dir):
                if not spec_f.endswith(".pyi"):
                    continue
                stem = os.path.splitext(spec_f)[0]
                if stem.endswith("_ext"):
                    continue
                pyi_path = os.path.join(low_dir, spec_f)
                dst_stub = os.path.join(ws_dep_dir, f"{stem}.py")
                if not os.path.isfile(dst_stub) or not _is_valid_test_stub(dst_stub):
                    _generate_readonly_test_stub(
                        pyi_path, stem, dst_stub, dep_dir=dep_dir, part_map=part_map
                    )
                    synced_count += 1
                else:
                    try:
                        if os.path.getmtime(pyi_path) > os.path.getmtime(dst_stub):
                            _generate_readonly_test_stub(
                                pyi_path, stem, dst_stub, dep_dir=dep_dir, part_map=part_map
                            )
                            synced_count += 1
                    except OSError:
                        pass

    return synced_count


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
        "check_files": "check_files",
        "submit": "submit",
        "blame": "blame",
        "feedback": "blame",
        "fail": "fail",
    }
    cov_path = os.path.join(bin_dir, "coverage")
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
3. Run verification checks: `bin/check_files [target_file]`
4. Submit verification stamp: `bin/submit <target_file>`
5. Blame defects if discovered: `bin/blame <culprit_file> "<explanation>"`
"""
    else:
        workflow = f"""1. Run `bin/get_work` to inspect and pull pending work.
2. Follow companion guide `{guide}` to author or update targets in scope.
3. Run verification checks: `bin/check_files [target_file]`
4. Submit completed targets: `bin/submit <target_file> "<summary>"` (or `bin/submit <target_file>` if unmodified)
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
If any cleanroom binary (`bin/get_work`, `bin/check_files`, `bin/blame`, `bin/submit`) fails due to:
- A Python exception or traceback (e.g., `ModuleNotFoundError`, `ImportError`, `AttributeError`)
- A Bazel analysis or execution failure
- A missing support file, template error, or dependency issue

**STOP IMMEDIATELY.**
- **DO NOT** attempt to fix, patch, restore, or work around the infrastructure.
- **DO NOT** create, undelete, or check out missing files.
- **DO NOT** attempt alternate execution paths outside `bin/`.
- **REPORT IMMEDIATELY**: Output the exact command that failed and its verbatim error/traceback to the user, state what dependency or file appears to be missing, and wait for human instruction.

NOTE: Verification test failures (e.g. `[FAIL] Verification failed` output from tests or linters on code under test) are NORMAL test results to be acted upon via `bin/blame` or code edits, NOT infrastructure crashes. Fail-Stop applies ONLY to internal tool crashes, tracebacks, or missing tooling/dependencies.

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
            writable_rel = _find_matching_files(
                scope_dir, role_def.writable_file_patterns
            )
            for rel in writable_rel:
                if _is_stub_dep_file(rel, role_def, resolved_root):
                    continue
                src_f = os.path.join(scope_dir, rel)
                dst_f = os.path.join(workspace_dir, dir_scope, rel)
                copy_file_with_perms(src_f, dst_f, readonly=False)

            readonly_rel = _find_matching_files(
                scope_dir, role_def.readonly_file_patterns
            )
            for rel in readonly_rel:
                if _is_stub_dep_file(rel, role_def, resolved_root):
                    continue
                src_f = os.path.join(scope_dir, rel)
                dst_f = os.path.join(workspace_dir, dir_scope, rel)
                copy_file_with_perms(src_f, dst_f, readonly=True)

            if role_def.stub_role_deps:
                _sync_all_stub_deps(
                    ws_scope_dir=os.path.join(workspace_dir, dir_scope),
                    main_scope_dir=scope_dir,
                    role_def=role_def,
                    main_root=resolved_root,
                    dir_scope=dir_scope,
                )

        if role_def.guide_path:
            guide_src = os.path.join(resolved_root, role_def.guide_path)
            if os.path.isfile(guide_src):
                guide_dst = os.path.join(workspace_dir, role_def.guide_path)
                copy_file_with_perms(guide_src, guide_dst, readonly=True)

        for cfg_name in (
            "pyproject.toml",
            "cleanroom_roles.toml",
            "cleanroom_python_roles.toml",
            "model_configs.toml",
            "uv.lock",
        ):
            cfg_src = os.path.join(resolved_root, cfg_name)
            if os.path.isfile(cfg_src):
                cfg_dst = os.path.join(workspace_dir, cfg_name)
                copy_file_with_perms(cfg_src, cfg_dst, readonly=False)

        ws_pyproject = os.path.join(workspace_dir, "pyproject.toml")
        if os.path.isfile(ws_pyproject):
            try:
                with open(ws_pyproject, "r", encoding="utf-8") as f:
                    ptext = f.read()
                ptext = re.sub(
                    r'\[tool\.pyright\][^\[]*include\s*=\s*\[[^\]]*\]',
                    '[tool.pyright]\ninclude = ["."]',
                    ptext,
                    flags=re.DOTALL,
                )
                if dir_scope:
                    clean_scope = dir_scope.strip("/").split("/")[0]
                    ptext = ptext.replace(f'"{clean_scope}",', '').replace(f'"{clean_scope}"', '')
                    ptext = ptext.replace(f'"{dir_scope}",', '').replace(f'"{dir_scope}"', '')
                ptext = re.sub(
                    r'testpaths\s*=\s*\[[^\]]*\]',
                    'testpaths = ["."]',
                    ptext,
                )
                with open(ws_pyproject, "w", encoding="utf-8") as f:
                    f.write(ptext)
                try:
                    os.chmod(ws_pyproject, 0o444)
                except OSError:
                    pass
            except OSError:
                pass

        if os.path.isdir(resolved_root):
            try:
                for entry in os.listdir(resolved_root):
                    pkg_dir = os.path.join(resolved_root, entry)
                    if not os.path.isdir(pkg_dir) or entry.startswith((".", "bazel-", "venv")):
                        continue
                    for rname in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
                        r_src = os.path.join(pkg_dir, rname)
                        if os.path.isfile(r_src):
                            r_dst = os.path.join(workspace_dir, entry, rname)
                            copy_file_with_perms(r_src, r_dst, readonly=True)
                    s_lib = os.path.join(pkg_dir, "support", "lib")
                    if os.path.isdir(s_lib):
                        d_lib = os.path.join(workspace_dir, entry, "support", "lib")
                        os.makedirs(d_lib, exist_ok=True)
                        for fname in os.listdir(s_lib):
                            if fname.endswith((".py", ".pyi", ".bzl", ".toml")):
                                sf = os.path.join(s_lib, fname)
                                df = os.path.join(d_lib, fname)
                                if os.path.isfile(sf):
                                    copy_file_with_perms(sf, df, readonly=True)
            except OSError:
                pass


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
