# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:55:00Z
# CHANGE: Define workspace_stub_impl realization
# CODE_HASH: c7533347c172
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_stub_impl."""

from __future__ import annotations

import ast
import fnmatch
import os
import re
import shutil
from typing import Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_session
from . import workspace_registry, workspace_stub


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


def _parse_pat_to_glob(pat: str) -> Tuple[str, str, str]:
    """Decomposes a source path pattern into its directory, stem suffix, and extension."""
    if not pat:
        return "", "", ""
    parts = pat.split("/")
    d = parts[1] if len(parts) > 1 else ""
    f = parts[-1]
    stem, ext = os.path.splitext(f)
    suffix = ""
    if "_" in stem and not stem.startswith("{"):
        suffix = stem.replace("{unit_name}", "")
    return d, suffix, ext


def _is_stub_dep_file(
    rel_path: str,
    role_def: workspace_registry.RoleDefinition,
    repo_root: Optional[str] = None,
) -> bool:
    """Returns True if rel_path matches any role in stub_role_deps."""
    if not role_def.stub_role_deps:
        return False
    fname = os.path.basename(rel_path)
    if fname in ("__init__.py",):
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
            d, _, ext = _parse_pat_to_glob(stub_def.src_pattern)
            if d and (parent == d or f"/{d}/" in rel_path.replace("\\", "/")) and (not ext or fname.endswith(ext)):
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
                    if fname == "__init__.py" or not fname.endswith(".py"):
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
                for meta_f in ("__init__.py",):
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


class WorkspaceStubSynthesizer(workspace_stub.WorkspaceStubSynthesizer, Singleton):
    """Realizes AST-based test stub synthesis and dependency synchronization."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def generate_readonly_test_stub(
        self,
        pyi_path: Optional[str],
        stem: str,
        out_path: str,
        dep_dir: str = "",
        part_map: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> None:
        """Generates a read-only test stub from a .pyi specification raising NotImplementedError."""
        _generate_readonly_test_stub(
            pyi_path, stem, out_path, dep_dir=dep_dir or "lib", part_map=part_map
        )

    def sync_all_stub_deps(
        self,
        workspace_dir: str,
        main_root: str,
        role_def: workspace_registry.RoleDefinition,
        dir_scope: str = "staging",
    ) -> int:
        """Synchronizes read-only test stubs for all stub_role_deps of a role."""
        ws_scope_dir = os.path.join(workspace_dir, dir_scope) if dir_scope else workspace_dir
        main_scope_dir = os.path.join(main_root, dir_scope) if dir_scope else main_root
        return _sync_all_stub_deps(
            ws_scope_dir,
            main_scope_dir,
            role_def,
            main_root,
            dir_scope,
        )

    def is_stub_dep_file(
        self,
        rel_path: str,
        role_def: workspace_registry.RoleDefinition,
        repo_root: Optional[str] = None,
    ) -> bool:
        """Checks whether rel_path corresponds to any declared role in stub_role_deps."""
        return _is_stub_dep_file(rel_path, role_def, repo_root=repo_root)

    def is_valid_test_stub(self, file_path: str) -> bool:
        """Checks whether file_path is already a valid cleanroom test stub."""
        return _is_valid_test_stub(file_path)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceStubSynthesizer,
        keys=[workspace_stub.WorkspaceStubSynthesizer, WorkspaceStubSynthesizer],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
