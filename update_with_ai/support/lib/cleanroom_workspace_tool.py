#!/usr/bin/env python3
"""cleanroom_workspace_tool.py — Orchestrates subagentless Cleanroom role workspaces.

Features:
- Sets up persistent role workspaces in sibling directory (../role_workspaces/<workspace_name>_<role>).
- Generates Read-Only Interface Stubs from .pyi specifications.
- Hardens workspace with OS-level permissions (chmod 444 for specs, BUILD files, and stubs).
- Deploys helper shell scripts (bin/submit, bin/blame, bin/fail).
- Synchronizes verified submissions back to canonical repository with hash integrity checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence
import zipapp

def _find_repo_root() -> str:
    real_path = os.path.realpath(__file__)
    curr = os.path.dirname(real_path)
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "MODULE.bazel")) or os.path.exists(os.path.join(curr, ".git")):
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
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from cleanroom_mailbox import parse_completed_entries, read_and_clear, wait_for_completion
from lib_lint import generate_asm_content, generate_lib_skeleton, is_uninitialized_module
from test_lint import generate_test_skeleton, is_uninitialized_test_module
from check_build_derived import parse_part_units


def compute_file_hash(path: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _ensure_allow_empty_in_globs(content: str) -> str:
    """Ensures all glob(...) calls in BUILD content include allow_empty = True.

    This prevents Bazel package evaluation failures when specific role tiers
    are intentionally omitted in role workspaces.
    """
    import re
    content = re.sub(r'allow_empty\s*=\s*False', 'allow_empty = True', content)
    def _repl(match: re.Match) -> str:
        inner = match.group(1)
        if "allow_empty" in inner:
            return match.group(0)
        return f"glob({inner}, allow_empty = True)"
    return re.sub(r'glob\(([^)]+)\)', _repl, content)


def _normalize_workspace_part_build(content: str) -> str:
    """Normalizes part BUILD content for role workspace isolation and sandboxing."""
    return _ensure_allow_empty_in_globs(content)


def get_default_role_dir(role: str, repo_root: Optional[str] = None) -> str:
    """Returns default workspace path: ../role_workspaces/<workspace_name>_<short_role_name> relative to repo root."""
    root = os.path.abspath(repo_root or _repo_root)
    ws_name = os.path.basename(root)
    parent_dir = os.path.dirname(root)
    clean_role = role.split(":")[-1] if ":" in role else role
    return os.path.join(parent_dir, "role_workspaces", f"{ws_name}_{clean_role}")


def save_role_metadata(
    workspace_dir: str,
    role_address: str,
    role_name: str,
    parts_dirs: Optional[Sequence[str]] = None,
) -> None:
    """Saves .cleanroom_role.json in the workspace root."""
    meta_path = os.path.join(workspace_dir, ".cleanroom_role.json")
    data = {
        "role_address": role_address,
        "role_name": role_name,
        "parts_dirs": list(parts_dirs) if parts_dirs else [],
    }
    write_file_with_perms(meta_path, json.dumps(data, indent=2) + "\n", readonly=False)


def load_role_metadata(workspace_dir: str) -> Optional[Dict[str, Any]]:
    """Loads .cleanroom_role.json from a workspace directory if present."""
    meta_path = os.path.join(workspace_dir, ".cleanroom_role.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def find_existing_role_workspaces(repo_root: Optional[str] = None) -> List[tuple[str, Dict[str, Any]]]:
    """Finds all existing role workspace directories that contain .cleanroom_role.json."""
    root = os.path.abspath(repo_root or _repo_root)
    ws_name = os.path.basename(root)
    parent_dir = os.path.dirname(root)
    found: List[tuple[str, Dict[str, Any]]] = []

    # 1. Primary location: ../role_workspaces/<ws_name>_<role>
    workspaces_container = os.path.join(parent_dir, "role_workspaces")
    if os.path.isdir(workspaces_container):
        for d in sorted(os.listdir(workspaces_container)):
            if not d.startswith(f"{ws_name}_"):
                continue
            ws_dir = os.path.join(workspaces_container, d)
            if os.path.isdir(ws_dir) and not d.startswith("."):
                meta = load_role_metadata(ws_dir)
                if meta and "role_name" in meta:
                    found.append((ws_dir, meta))

    # 2. Legacy location: ../<ws_name>_workspaces/<role>
    legacy_container = os.path.join(parent_dir, f"{ws_name}_workspaces")
    if os.path.isdir(legacy_container):
        for d in sorted(os.listdir(legacy_container)):
            ws_dir = os.path.join(legacy_container, d)
            if os.path.isdir(ws_dir) and not d.startswith("."):
                meta = load_role_metadata(ws_dir)
                if meta and "role_name" in meta:
                    if not any(f[0] == ws_dir for f in found):
                        found.append((ws_dir, meta))

    # 3. Check sibling directories in parent_dir (for custom paths or backwards compatibility)
    if os.path.isdir(parent_dir):
        for d in sorted(os.listdir(parent_dir)):
            ws_dir = os.path.join(parent_dir, d)
            if ws_dir == workspaces_container or ws_dir == legacy_container or not os.path.isdir(ws_dir):
                continue
            meta = load_role_metadata(ws_dir)
            if meta and "role_name" in meta:
                if not any(f[0] == ws_dir for f in found):
                    found.append((ws_dir, meta))

    return found


def _eval_ast_node(node: Any, env: Dict[str, Any]) -> Any:
    """Evaluates an AST expression supporting constants, lists, dicts, variable lookup, and list additions."""
    import ast

    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.List):
        return [_eval_ast_node(elt, env) for elt in node.elts]
    elif isinstance(node, ast.Tuple):
        return tuple(_eval_ast_node(elt, env) for elt in node.elts)
    elif isinstance(node, ast.Dict):
        return {
            _eval_ast_node(k, env): _eval_ast_node(v, env)
            for k, v in zip(node.keys, node.values)
            if k is not None
        }
    elif isinstance(node, ast.Name):
        return env.get(node.id)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _eval_ast_node(node.left, env)
        right = _eval_ast_node(node.right, env)
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        elif isinstance(left, str) and isinstance(right, str):
            return left + right
        elif isinstance(left, dict) and isinstance(right, dict):
            merged = dict(left)
            merged.update(right)
            return merged
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def load_defined_roles(repo_root: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Parses define_role declarations from update_*_with_ai/BUILD.bazel using ast."""
    import ast

    root = os.path.abspath(repo_root or _repo_root)
    build_files: list[tuple[str, str]] = []

    candidates = ["update_python_with_ai"]
    if os.path.isdir(root):
        for entry in os.listdir(root):
            if entry.startswith("update_") and entry.endswith("_with_ai") and entry not in candidates:
                candidates.append(entry)

    for pkg_name in candidates:
        bf = os.path.join(root, pkg_name, "BUILD.bazel")
        if not os.path.isfile(bf):
            bf = os.path.join(_repo_root, pkg_name, "BUILD.bazel")
        if os.path.isfile(bf):
            build_files.append((pkg_name, bf))

    if not build_files:
        return {}

    roles: Dict[str, Dict[str, Any]] = {}
    aliases: Dict[str, str] = {}

    for pkg_name, build_file in build_files:
        with open(build_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=build_file)
            except Exception:
                continue

        env: Dict[str, Any] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        val = _eval_ast_node(node.value, env)
                        if val is not None:
                            env[target.id] = val

            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name):
                    if func.id == "define_role":
                        kwargs: Dict[str, Any] = {}
                        for kw in node.value.keywords:
                            if kw.arg:
                                kwargs[kw.arg] = _eval_ast_node(kw.value, env)
                        name = kwargs.get("name")
                        if name:
                            kwargs["pkg"] = pkg_name
                            kwargs["label"] = f"//{pkg_name}:{name}"
                            roles[name] = kwargs
                            roles[f":{name}"] = kwargs
                            roles[f"//{pkg_name}:{name}"] = kwargs
                    elif func.id == "alias":
                        kwargs = {}
                        for kw in node.value.keywords:
                            if kw.arg:
                                kwargs[kw.arg] = _eval_ast_node(kw.value, env)
                        name = kwargs.get("name")
                        actual = kwargs.get("actual")
                        if name and actual:
                            aliases[name] = actual
                            aliases[f":{name}"] = actual
                            aliases[f"//{pkg_name}:{name}"] = actual

    for alias_name, actual_target in aliases.items():
        clean_target = actual_target.lstrip(":")
        if clean_target in roles:
            roles[alias_name] = roles[clean_target]
        elif actual_target in roles:
            roles[alias_name] = roles[actual_target]

    return roles


def resolve_role_definition(role_str: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Resolves a role target label or short name to its define_role metadata."""
    roles = load_defined_roles(repo_root)
    s = role_str.strip()
    if s in roles:
        return dict(roles[s])
    short = s.split(":")[-1]
    if short in roles:
        return dict(roles[short])
    if roles:
        known = sorted([k for k in roles.keys() if not k.startswith(":") and not k.startswith("//")])
        raise ValueError(f"Unknown Cleanroom role '{role_str}'. Defined roles in update_python_with_ai/BUILD.bazel: {known}")
    return {
        "name": short,
        "label": f"//update_python_with_ai:{short}",
        "src_pattern": f"{{unit_dir}}/{short}/{{unit_name}}.py",
        "guide": f"//update_python_with_ai/guides:{short}",
        "role_deps": [],
        "star_role_deps": [],
        "stub_role_deps": [],
        "verify_template": "",
    }


def normalize_role_arg(role: Optional[str]) -> Optional[str]:
    """Normalizes role argument string into short role name (e.g. '//pkg:role' -> 'role')."""
    if not role:
        return None
    s = role.strip()
    if ":" in s:
        return s.split(":")[-1]
    return s


def normalize_parts_dirs(
    repo_root: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
) -> List[str]:
    """Resolves and normalizes parts directory bases (e.g. 'update_with_ai', 'staging').

    Handles inputs like:
      - None -> discovers all existing bases with a 'parts' subfolder (e.g. ['update_with_ai', 'staging'])
      - ['staging'] -> ['staging']
      - ['update_with_ai'] -> ['update_with_ai']
      - ['staging/parts'] -> ['staging']
      - ['update_with_ai,staging'] -> ['update_with_ai', 'staging']
    """
    root = os.path.abspath(repo_root or _repo_root)

    if not parts_dirs:
        candidates = ["update_with_ai", "staging", "testing"]
        discovered = []
        for c in candidates:
            if os.path.isdir(os.path.join(root, c, "parts")):
                discovered.append(c)
        return discovered or ["update_with_ai"]

    raw_items: List[str] = []
    for item in parts_dirs:
        if isinstance(item, str):
            for sub_item in item.split(","):
                s = sub_item.strip()
                if s:
                    raw_items.append(s)
        elif hasattr(item, "__iter__"):
            for sub in item:
                s = str(sub).strip()
                if s:
                    raw_items.append(s)

    normalized: List[str] = []
    for item in raw_items:
        clean = item.strip().strip("/")
        if clean.endswith("/parts"):
            clean = clean[:-6]
        elif clean.endswith(os.sep + "parts"):
            clean = clean[: -len(os.sep + "parts")]
        if clean not in normalized:
            normalized.append(clean)

    return normalized


def get_part_module_map(
    repo_root: Optional[str] = None,
    parts_bases: Optional[Sequence[str]] = None,
) -> Dict[str, tuple[str, str]]:
    """Maps module name -> (part_name, base_dir) across specified parts directories."""
    root = os.path.abspath(repo_root or _repo_root)
    bases = normalize_parts_dirs(root, parts_dirs=parts_bases)
    mapping: Dict[str, tuple[str, str]] = {}
    for base in bases:
        parts_dir = os.path.join(root, base, "parts")
        if not os.path.isdir(parts_dir):
            continue
        for p in os.listdir(parts_dir):
            p_dir = os.path.join(parts_dir, p)
            if not os.path.isdir(p_dir) or p.startswith("."):
                continue
            with os.scandir(p_dir) as it:
                for entry in it:
                    if entry.is_dir() and not entry.name.startswith(".") and not entry.name.startswith("_"):
                        for f in os.listdir(entry.path):
                            if f.endswith(".py") or f.endswith(".pyi"):
                                mod_name = f.rsplit(".", 1)[0]
                                mapping[mod_name] = (p, base)
    return mapping


def parse_pattern_info(src_pattern: str) -> tuple[str, str, str]:
    """Extracts (directory, prefix, suffix) from a src_pattern.

    Examples:
      "{unit_dir}/{dir}/{unit_name}.ext" -> ("{dir}", "", ".ext")
      "{unit_dir}/{dir}/{unit_name}_suffix.ext" -> ("{dir}", "", "_suffix.ext")
    """
    clean = src_pattern.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
    if "/" in clean:
        dir_name, file_pattern = clean.split("/", 1)
    else:
        dir_name = ""
        file_pattern = clean

    if "{unit_name}" in file_pattern:
        prefix, suffix = file_pattern.split("{unit_name}", 1)
    else:
        prefix, suffix = "", file_pattern

    return dir_name, prefix, suffix


def generate_readonly_test_stub(
    pyi_path: str,
    stem: str,
    out_path: str,
    dep_dir: str = "lib",
    part_map: Optional[Dict[str, tuple[str, str]]] = None,
) -> None:
    """Generates a read-only dependency stub from a .pyi specification."""
    # Identify current base and current part name from out_path
    parts_split = out_path.split(os.sep)
    current_base = "update_with_ai"
    current_part = ""
    if "parts" in parts_split:
        idx = parts_split.index("parts")
        if idx > 0:
            current_base = parts_split[idx - 1]
        if idx + 1 < len(parts_split):
            current_part = parts_split[idx + 1]

    skeleton = generate_lib_skeleton(pyi_path, stem, parts_base=current_base)

    # Parse pyi to preserve specific lifecycle imports (e.g. ChildTierOf, SystemTier)
    import ast
    import re

    with open(pyi_path, "r", encoding="utf-8") as f:
        pyi_tree = ast.parse(f.read(), filename=pyi_path)

    lifecycle_names: set[str] = set()
    for node in pyi_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in ("support.lib.lifecycle", "lifecycle"):
            for a in node.names:
                lifecycle_names.add(a.name)

    if part_map is None:
        part_map = get_part_module_map(parts_bases=[current_base])

    # Transform skeleton bodies into cleanroom test stubs that raise NotImplementedError
    stub_lines: list[str] = [
        "from __future__ import annotations",
    ]
    if lifecycle_names:
        stub_lines.append(f"from support.lib.lifecycle import {', '.join(sorted(lifecycle_names))}")

    stub_lines.extend([
        f"# Requirements specified in {os.path.basename(pyi_path)}",
        "# CLEANROOM TEST STUB: Implementation details omitted. Refer strictly to companion .pyi file.",
        "",
    ])

    for line in skeleton.splitlines():
        if line.startswith("from __future__") or line.startswith("# Requirements"):
            continue

        # Sibling or cross-package import rewriting
        m = re.match(r"^import\s+([a-zA-Z0-9_]+)(?:\s+as\s+([a-zA-Z0-9_]+))?$", line.strip())
        if m:
            mod_name = m.group(1)
            alias = f" as {m.group(2)}" if m.group(2) else ""
            if mod_name in part_map:
                target_part, target_base = part_map[mod_name]
                if target_part == current_part and target_base == current_base:
                    line = f"from . import {mod_name}{alias}"
                else:
                    line = f"from {target_base}.parts.{target_part}.{dep_dir} import {mod_name}{alias}"

        # Rewrite any cross-parts import prefix to current_base.parts.
        if ".parts." in line:
            line = re.sub(r'\b[a-zA-Z0-9_]+\.parts\.', f"{current_base}.parts.", line)

        # Constructors (__init__) should pass so classes can be instantiated for type checks
        if line.strip().startswith("# TODO_"):
            continue

        if line.strip() == "raise NotImplementedError":
            indent = " " * (len(line) - len(line.lstrip()))
            stub_lines.append(f'{indent}raise NotImplementedError("Cleanroom Test Stub: Behavior specified in .pyi")')
        else:
            stub_lines.append(line)

    write_file_with_perms(out_path, "\n".join(stub_lines) + "\n", readonly=True)


def write_file_with_perms(dst: str, content: str, readonly: bool = False, executable: bool = False) -> None:
    """Writes a text file and sets exact permissions, cleanly handling existing read-only files."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.chmod(dst, 0o644)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
    mode = 0o755 if executable else (0o444 if readonly else 0o644)
    os.chmod(dst, mode)


def copy_file_with_perms(src: str, dst: str, readonly: bool = False, executable: bool = False) -> None:
    """Copies a file and applies exact read-only (444/555) or read-write (644/755) permissions."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.chmod(dst, 0o644)
    shutil.copy2(src, dst)
    if executable:
        mode = 0o555 if readonly else 0o755
    else:
        mode = 0o444 if readonly else 0o644
    os.chmod(dst, mode)


def find_spec_pyi(part_path: str, stem: str, repo_root: Optional[str] = None) -> Optional[str]:
    """Finds companion .pyi specification file for a unit stem in a part directory."""
    if os.path.isdir(part_path):
        with os.scandir(part_path) as it:
            for entry in it:
                if entry.is_dir() and not entry.name.startswith(".") and not entry.name.startswith("_"):
                    candidate = os.path.join(entry.path, f"{stem}.pyi")
                    if os.path.isfile(candidate):
                        return candidate
    return None


def resolve_template_path(template_ref: str, repo_root: Optional[str] = None) -> Optional[str]:
    """Resolves a template reference (label or path) to an absolute file path."""
    root = repo_root or _repo_root
    clean_ref = template_ref.strip().lstrip("/")
    direct = os.path.join(root, clean_ref)
    if os.path.isfile(direct):
        return direct

    if ":" in clean_ref:
        pkg, target = clean_ref.split(":", 1)
        pkg_dir = os.path.join(root, pkg)
        if os.path.isdir(pkg_dir):
            for candidate in [
                os.path.join(pkg_dir, target),
                os.path.join(pkg_dir, f"{target}_template.py"),
                os.path.join(pkg_dir, f"{target}_template.md"),
                os.path.join(pkg_dir, f"{target}_template.txt"),
                os.path.join(pkg_dir, f"{target}.py"),
                os.path.join(pkg_dir, f"{target}.md"),
            ]:
                if os.path.isfile(candidate):
                    return candidate
            build_file = os.path.join(pkg_dir, "BUILD.bazel")
            if os.path.isfile(build_file):
                try:
                    with open(build_file, "r", encoding="utf-8") as bf:
                        tree = ast.parse(bf.read(), filename=build_file)
                    for node in tree.body:
                        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                            func = node.value.func
                            if isinstance(func, ast.Name) and func.id == "filegroup":
                                fg_name = None
                                fg_srcs = []
                                for kw in node.value.keywords:
                                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                        fg_name = kw.value.value
                                    elif kw.arg == "srcs" and isinstance(kw.value, ast.List):
                                        fg_srcs = [
                                            elt.value for elt in kw.value.elts if isinstance(elt, ast.Constant)
                                        ]
                                if fg_name == target and fg_srcs:
                                    src_path = os.path.join(pkg_dir, fg_srcs[0])
                                    if os.path.isfile(src_path):
                                        return src_path
                except Exception:
                    pass
    return None


def resolve_node_dep_src(
    node_dep_ref: str,
    repo_root: Optional[str] = None,
    default_pkg: str = "update_python_with_ai",
) -> Optional[str]:
    """Resolves a node dependency reference (label or path) to its repo-relative source path."""
    import ast
    root = repo_root or _repo_root
    clean_ref = node_dep_ref.strip().lstrip("/")
    if ":" in clean_ref:
        pkg, target = clean_ref.split(":", 1)
    elif clean_ref.startswith(":"):
        pkg = default_pkg
        target = clean_ref[1:]
    else:
        pkg = default_pkg
        target = clean_ref

    # 1. Check if manifest exists and declares src
    manifest_candidates = [
        os.path.join(root, pkg, f"{target}_manifest.json"),
        os.path.join(root, pkg, f".{target}_manifest.json"),
        os.path.join(root, "bazel-bin", pkg, f"{target}_manifest.json"),
    ]
    for mf in manifest_candidates:
        if os.path.isfile(mf):
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                src = data.get("src") or data.get("source_file")
                if src:
                    src_clean = str(src).lstrip("/")
                    if src_clean.startswith(pkg.strip("/") + "/"):
                        return src_clean
                    return os.path.normpath(os.path.join(pkg, src_clean))
            except Exception:
                pass

    # 2. Check BUILD.bazel for update_with_ai rule calls
    build_file = os.path.join(root, pkg, "BUILD.bazel")
    if not os.path.isfile(build_file):
        build_file = os.path.join(_repo_root, pkg, "BUILD.bazel")
    if os.path.isfile(build_file):
        try:
            with open(build_file, "r", encoding="utf-8") as bf:
                tree = ast.parse(bf.read(), filename=build_file)
            for node in tree.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    func = node.value.func
                    func_name = getattr(func, "id", None) or getattr(func, "attr", None)
                    if func_name in ("update_with_ai", "update_guide_with_ai"):
                        call_name = None
                        call_src = None
                        for kw in node.value.keywords:
                            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                call_name = kw.value.value
                            elif kw.arg == "src" and isinstance(kw.value, ast.Constant):
                                call_src = kw.value.value
                        if call_name == target and call_src:
                            src_clean = str(call_src).lstrip("/")
                            if src_clean.startswith(pkg.strip("/") + "/"):
                                return src_clean
                            return os.path.normpath(os.path.join(pkg, src_clean))
        except Exception:
            pass

    # 3. Candidate files based on target name
    base_name = target[:-5] if target.endswith("_spec") else target
    for cand in [
        f"{base_name}.pyi",
        f"{target}.pyi",
        f"{base_name}.py",
        f"{target}.py",
        f"{base_name}.md",
        f"{target}.md",
    ]:
        rel = os.path.join(pkg, cand)
        if os.path.isfile(os.path.join(root, rel)) or os.path.isfile(os.path.join(_repo_root, rel)):
            return rel

    return None


def ensure_role_templates_in_place(
    part_path: str, role_def: Dict[str, Any], repo_root: Optional[str] = None
) -> list[str]:
    """Ensures empty or missing source files for active units have skeletons/templates materialized from specs."""
    parent_build = os.path.join(part_path, "BUILD.bazel")
    if not os.path.isfile(parent_build):
        return []
    units = parse_part_units(parent_build)
    if not units:
        return []

    src_pattern = role_def.get("src_pattern", "")
    if not src_pattern:
        return []

    active_types = role_def.get("active_component_types")
    allowed_types = set(active_types) if active_types else None

    def get_comp_type(name: str) -> str:
        if name.endswith("_ext"):
            return "external"
        if name.endswith("_asm"):
            return "assembly"
        if name.endswith("_impl"):
            return "implementation"
        return "interface"

    materialized: list[str] = []

    # Check if role specifies stub_role_deps (indicating it tests or interacts with a stubbed dependency)
    stub_targets = role_def.get("stub_role_deps", [])
    tested_pkg = None
    if stub_targets:
        stub_def = resolve_role_definition(stub_targets[0], repo_root)
        s_pattern = stub_def.get("src_pattern", "")
        s_dir, _, _ = parse_pattern_info(s_pattern)
        if s_dir:
            tested_pkg = os.path.join(part_path, s_dir)

    tmpl_ref = role_def.get("template")
    tmpl_path = resolve_template_path(tmpl_ref, repo_root=repo_root) if tmpl_ref else None
    raw_template_content = None
    if tmpl_path and os.path.isfile(tmpl_path):
        try:
            with open(tmpl_path, "r", encoding="utf-8") as tf:
                raw_template_content = tf.read()
        except OSError:
            raw_template_content = None

    for stem, raw_deps in units.items():
        if stem.endswith("_ext"):
            continue
        if allowed_types is not None and get_comp_type(stem) not in allowed_types:
            continue
        file_path = src_pattern.format(unit_dir=part_path, unit_name=stem)
        mod_exists = os.path.isfile(file_path)
        mod_content = ""
        if mod_exists:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    mod_content = f.read()
            except OSError:
                pass

        if mod_exists:
            if file_path.endswith("_test.py") and is_uninitialized_test_module and not is_uninitialized_test_module(mod_content):
                continue
            elif not file_path.endswith("_test.py") and is_uninitialized_module and not is_uninitialized_module(mod_content):
                continue

        dir_path = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(dir_path, exist_ok=True)
        try:
            if stem.endswith("_asm") and generate_asm_content:
                asm_content = generate_asm_content(dir_path, raw_deps)
                write_file_with_perms(file_path, asm_content, readonly=False)
                materialized.append(file_path)
            elif tested_pkg and generate_test_skeleton:
                pyi_path = find_spec_pyi(part_path, stem, repo_root=repo_root)
                if pyi_path and os.path.isfile(pyi_path):
                    test_stem = os.path.splitext(os.path.basename(file_path))[0]
                    test_skeleton = generate_test_skeleton(pyi_path, test_stem, stem, tested_pkg)
                    write_file_with_perms(file_path, test_skeleton, readonly=False)
                    materialized.append(file_path)
                else:
                    tmpl_content = raw_template_content if raw_template_content is not None else f"from __future__ import annotations\n\n# Tests for {stem}\n"
                    write_file_with_perms(file_path, tmpl_content, readonly=False)
                    materialized.append(file_path)
            else:
                pyi_path = find_spec_pyi(part_path, stem, repo_root=repo_root)
                if pyi_path and os.path.isfile(pyi_path) and generate_lib_skeleton:
                    skeleton = generate_lib_skeleton(pyi_path, stem)
                    write_file_with_perms(file_path, skeleton, readonly=False)
                    materialized.append(file_path)
                else:
                    tmpl_content = raw_template_content if raw_template_content is not None else f"from __future__ import annotations\n\n# Requirements specified in {stem}.pyi\n"
                    write_file_with_perms(file_path, tmpl_content, readonly=False)
                    materialized.append(file_path)
        except (PermissionError, OSError):
            pass

    return materialized


def prepare_role_artifacts(
    role_def: Dict[str, Any], repo_root: str, parts_bases: Sequence[str]
) -> None:
    """Prepares role artifacts declaratively based on define_role specification."""
    has_template = bool(role_def.get("template"))
    derive_build_cmd = role_def.get("derive_build_template", "")

    if not has_template and not derive_build_cmd:
        return

    bases = normalize_parts_dirs(repo_root, parts_dirs=parts_bases)
    for base in bases:
        parts_root = os.path.join(repo_root, base, "parts")
        if not os.path.isdir(parts_root):
            continue
        for part_name in sorted(os.listdir(parts_root)):
            part_path = os.path.join(parts_root, part_name)
            if not os.path.isdir(part_path) or part_name.startswith("."):
                continue
            parent_build = os.path.join(part_path, "BUILD.bazel")
            if not os.path.isfile(parent_build):
                continue

            rel_part = os.path.relpath(part_path, repo_root)

            # 1. Put templates in place for empty or missing files if role declares a template
            if has_template:
                materialized = ensure_role_templates_in_place(part_path, role_def, repo_root=repo_root)
                if materialized:
                    print(f"Materialized {len(materialized)} template(s) in {rel_part}")

            # 2. Derive/update BUILD.bazel if declared by role's derive_build_template
            if derive_build_cmd:
                cmd = derive_build_cmd.format(unit_dir=rel_part)
                env = dict(os.environ)
                env.pop("TEST_SRCDIR", None)
                env.pop("TEST_WORKSPACE", None)
                if _repo_root not in env.get("PYTHONPATH", ""):
                    env["PYTHONPATH"] = f"{_repo_root}:{env.get('PYTHONPATH', '')}".rstrip(":")
                tokens = cmd.split()
                if len(tokens) >= 2 and tokens[0] == "python3" and not os.path.isabs(tokens[1]):
                    script_path = os.path.join(repo_root, tokens[1])
                    if not os.path.exists(script_path):
                        script_path = os.path.join(_repo_root, tokens[1])
                    if os.path.exists(script_path):
                        tokens[1] = script_path
                        cmd = " ".join(tokens)

                try:
                    res = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=repo_root,
                        env=env,
                        capture_output=True,
                        text=True,
                    )
                    if res.returncode != 0:
                        print(f"Warning: derive_build_template failed for {rel_part}: {res.stderr.strip()}")
                    elif "UPDATED:" in res.stdout:
                        for line in res.stdout.splitlines():
                            if "UPDATED:" in line:
                                print(f"  {line.strip()}")
                except Exception as e:
                    print(f"Warning: could not run derive_build_template for {rel_part}: {e}")


def find_read_write_files(
    base_dir: str,
    role_def: Dict[str, Any],
    parts_bases: Optional[Sequence[str]] = None,
) -> List[str]:
    """Finds all relative paths of read-write files for this role in base_dir."""
    active_pattern = role_def.get("src_pattern", "")
    if not active_pattern:
        return []
    active_dir, active_prefix, active_suffix = parse_pattern_info(active_pattern)
    if not active_dir:
        return []

    active_types = role_def.get("active_component_types")
    allowed_types = set(active_types) if active_types else None

    def get_comp_type(name: str) -> str:
        if name.endswith("_ext"):
            return "external"
        if name.endswith("_asm"):
            return "assembly"
        if name.endswith("_impl"):
            return "implementation"
        return "interface"

    bases = normalize_parts_dirs(base_dir, parts_dirs=parts_bases)
    files_found: List[str] = []

    for base in bases:
        parts_root = os.path.join(base_dir, base, "parts")
        if not os.path.isdir(parts_root):
            continue
        for part_name in sorted(os.listdir(parts_root)):
            part_dir = os.path.join(parts_root, part_name)
            if not os.path.isdir(part_dir) or part_name.startswith("."):
                continue
            act_dir = os.path.join(part_dir, active_dir)
            if not os.path.isdir(act_dir):
                continue
            for r, _, files in os.walk(act_dir):
                for f in sorted(files):
                    if f.startswith(".") or f == "BUILD.bazel" or f == "__init__.py":
                        continue
                    if f.startswith(active_prefix) and f.endswith(active_suffix):
                        stem = f[len(active_prefix) : -len(active_suffix)] if active_suffix else f[len(active_prefix) :]
                        if allowed_types is not None and get_comp_type(stem) not in allowed_types:
                            continue
                        full_p = os.path.join(r, f)
                        rel_p = os.path.relpath(full_p, base_dir)
                        files_found.append(rel_p)

    return files_found


def write_role_agents_md(workspace_dir: str, role_or_def: Any, repo_root: Optional[str] = None) -> None:
    """Generates custom AGENTS.md at the workspace root from define_role metadata."""
    root = repo_root or _repo_root
    if isinstance(role_or_def, dict):
        role_def = role_or_def
        role = role_def.get("name", "role")
    else:
        role = str(role_or_def).split(":")[-1]
        role_def = resolve_role_definition(role, root)

    agents_path = os.path.join(workspace_dir, "AGENTS.md")
    role_label = role_def.get("label", f":{role}")
    persona = role_def.get("persona", f"{role.capitalize()} Engineer")
    guide_target = role_def.get("guide", "")
    guide_rel = ""
    if guide_target:
        gt = guide_target.lstrip("/")
        if ":" in gt:
            g_pkg, g_name = gt.split(":", 1)
            guide_rel = f"{g_pkg}/{g_name}.md"
        else:
            guide_rel = f"{gt}.md"

    active_pattern = role_def.get("src_pattern", "")
    active_dir, _, _ = parse_pattern_info(active_pattern)

    verify_cmd = role_def.get("verify_template", "").replace("cd $BUILD_WORKSPACE_DIRECTORY && ", "").strip()
    if not verify_cmd:
        verify_cmd = f"# Verify work in {active_dir}/"

    if active_pattern.endswith(".log"):
        scope_clause = "- **Strict Read-Only Mode**: All code files in this workspace are read-only contracts. You must NOT edit any code files."
    else:
        scope_clause = f"- **Strict Scope**: You are ONLY permitted to create or modify files inside `{active_dir}/`. Never attempt to edit other files, contracts, or configurations."

    # Derive deterministic upstream contract patterns
    dep_targets = list(role_def.get("role_deps", []))
    for st in role_def.get("star_role_deps", []):
        if st not in dep_targets and st != f":{role}":
            dep_targets.append(st)
    for fb in role_def.get("feedback_role_deps", []):
        if fb not in dep_targets and fb != f":{role}":
            dep_targets.append(fb)

    upstream_contract_lines: list[str] = []
    for d_target in dep_targets:
        d_name = d_target.split(":")[-1]
        if d_name == role:
            continue
        try:
            d_def = resolve_role_definition(d_target, root)
            d_pat = d_def.get("src_pattern", "")
            if d_pat:
                rel_pat = d_pat.replace("{unit_dir}/", "").replace("{unit_name}", "<name>")
                upstream_contract_lines.append(f"- `<parts_dir>/parts/<unit>/{rel_pat}` ({d_name})")
        except Exception:
            pass

    if upstream_contract_lines:
        upstream_contract_str = "\n".join(f"  {line}" for line in upstream_contract_lines)
        upstream_clause = f"""- **Deterministic Upstream Contracts**: For target `<parts_dir>/parts/<unit>/{active_dir}/<name>.<ext>`, the upstream contract is strictly:
{upstream_contract_str}
  Inspect strictly this file and the role guide (`{guide_rel}`). Do not search, crawl, or grep other components."""
        step2 = f"2. Call `view_file` on **both** the paired upstream contract and the target file (`{active_dir}/<name>.<ext>` if it exists), and review the companion role guide (`{guide_rel}`)."
        inspection_mandate = "- **Individual Inspection Mandate**: You must never submit any target file via `bin/submit` without having called `view_file` on both its upstream contract and the target file itself (if it exists). Batch-submitting uninspected files via shell loops or scripts is strictly forbidden."
    else:
        upstream_clause = f"- **Root Specification**: This role has no upstream contracts. Author specifications directly according to user instructions and the role guide (`{guide_rel}`)."
        step2 = f"2. Call `view_file` on the target file (`{active_dir}/<name>.<ext>` if it exists) and review user instructions and the companion role guide (`{guide_rel}`)."
        inspection_mandate = "- **Individual Inspection Mandate**: You must never submit any target file via `bin/submit` without having called `view_file` on the target file itself (if it exists) to inspect its content against the role guide. Batch-submitting uninspected files via shell loops or scripts is strictly forbidden."

    blame_entry = ""
    blame_seq = ""
    feedback_deps = role_def.get("feedback_role_deps", [])
    if feedback_deps:
        blame_targets_str = ", ".join(feedback_deps)
        blame_entry = f"\n   - If an upstream contract defect is identified in declared feedback dependencies ({blame_targets_str}), run `bin/blame <target> <blame_target> \"<explanation>\"`."
        blame_seq = "\n   (or run `bin/blame <target> <blame_target> \"<explanation>\"` if an upstream contract defect is discovered)"

    if active_dir == "logs":
        tool_sequence = f"""1. `view_file` on `WORK_ORDER.md` to identify pending targets under `CLEAN <target>`.
2. {step2}
3. `run_command` to execute verification:
   `{verify_cmd}`
4. `run_command` to submit verification logs or blame:
   `bin/submit <target> "<concise verification summary>"`{blame_seq}
   (or run `bin/fail <target> "<reason>"` if an unresolvable error occurs).
5. Stop calling tools and terminate your turn immediately upon submission."""
    else:
        tool_sequence = f"""1. `view_file` on `WORK_ORDER.md` to identify pending targets under `CLEAN <target>` (or identify targets from user instructions). Process targets systematically file-by-file.
2. {step2}
3. Compare the content semantically against the role guide rules. Author or update the target file in `{active_dir}/` using file editing tools (`replace_file_content` or `write_to_file`) to resolve discrepancies.
4. `run_command` to verify your work:
   `{verify_cmd}`
5. `run_command` to submit your work:
   `bin/submit <target> "<concise change summary>"`{blame_seq}
   (or run `bin/fail <target> "<reason>"` if an unresolvable error occurs).
6. Stop calling tools and terminate your turn immediately upon submission."""

    content = f"""# Cleanroom Role: {persona} ({role_label})

## Mandatory Behavioral Constraints & Role Boundaries
- **Role Persona**: You are the {persona}.
- **Contract & Guidance**: You author and maintain files adhering strictly to the role guide (`{guide_rel}`).
{scope_clause}
- **No Exploratory Reconnaissance**: Never run directory listings (`ls`, `dir`), filesystem crawls (`find`, `tree`), or global text searches (`grep`, `rg`). All target paths and guide paths are fully specified; proceed directly to reading them.
- **No Version Control Commands**: This workspace is an isolated cleanroom that does not use `git`. Never execute `git status`, `git diff`, `git log`, etc.
{upstream_clause}
- **Role of Tooling and Scripts**: Programmatic checks, linters, and python scripts are permitted and encouraged as auxiliary verification tools to catch syntax, formatting, or broken citations. However, **scripts must be run in addition to, never in place of, the actual cognitive engineering task**. Passing automated checks is a prerequisite, not proof of semantic alignment.
{inspection_mandate}
- **Direct Unit Alignment**: The user may also ask you to align units directly, alignment is for files in `<parts-dir>/parts/{active_dir}` and should be done according to `{guide_rel}`.
- **Strict Confinement**: You are strictly confined to this workspace directory. Never inspect parent directories or outside paths.
- **Strict Permission Rule**: You are strictly forbidden from executing `chmod`, changing file permissions, or attempting to write to read-only files. Any tampering with file permissions will cause automated rejection.

## Work Order Semantics
When reading `WORK_ORDER.md`:
- `REASON: Change: check`: Signifies an alignment audit — verify and align the target file against its paired upstream contract and role guide rules.
- `REASON: Change: <summary>`: An upstream contract was modified with the given summary — update the target file to reflect those modifications.
- `REASON: Feedback: <explanation>`: Specific defect or blame feedback was reported — address the issue described in the explanation.

## Prescribed Tool Sequence
Your turn should consist strictly of:
{tool_sequence}
"""
    write_file_with_perms(agents_path, content, readonly=False)


def copy_readonly_files_and_stubs(
    workspace_dir: str,
    repo_root: str,
    role_def: Dict[str, Any],
    parts_bases: Sequence[str],
) -> None:
    """Copies all read-only files (tools, configs, guides, dependency specs, stubs, build files) to role workspace."""
    root = repo_root
    role_name = role_def["name"]

    # 1. Determine if this role uses a build system (e.g. Bazel)
    workspace_entries: list[str] = []
    for entry in (role_def.get("workspace_files") or []) + (role_def.get("tools") or []):
        if entry and entry not in workspace_entries:
            workspace_entries.append(entry)

    is_build_enabled = any(
        w in ("BUILD.bazel", "MODULE.bazel", ".bazelversion") or w.endswith("BUILD.bazel")
        for w in workspace_entries
    )

    # 2. Copy workspace_files and tools declared in define_role (read-only)
    for entry_rel in workspace_entries:
        entry_rel = entry_rel.rstrip("/")
        src = os.path.join(root, entry_rel)
        if not os.path.exists(src):
            src = os.path.join(_repo_root, entry_rel)
        if not os.path.exists(src):
            continue
        dst = os.path.join(workspace_dir, entry_rel)
        if os.path.isfile(src):
            is_exec = os.access(src, os.X_OK) or entry_rel.startswith("bin/") or entry_rel.endswith(".sh")
            copy_file_with_perms(src, dst, readonly=True, executable=is_exec)
        elif os.path.isdir(src):
            for t_root, _, t_files in os.walk(src):
                for tf in t_files:
                    src_f = os.path.join(t_root, tf)
                    rel_f = os.path.relpath(src_f, src)
                    dst_f = os.path.join(dst, rel_f)
                    is_exec = os.access(src_f, os.X_OK) or rel_f.startswith("bin/") or rel_f.endswith(".sh")
                    copy_file_with_perms(src_f, dst_f, readonly=True, executable=is_exec)

    # 2b. Copy node_deps declared in define_role (read-only)
    for entry in role_def.get("node_deps") or []:
        dep_src_rel = resolve_node_dep_src(entry, root, default_pkg=role_def.get("pkg", "update_python_with_ai"))
        if dep_src_rel:
            src = os.path.join(root, dep_src_rel)
            if not os.path.exists(src):
                src = os.path.join(_repo_root, dep_src_rel)
            if os.path.isfile(src):
                dst = os.path.join(workspace_dir, dep_src_rel)
                copy_file_with_perms(src, dst, readonly=True)

    # Helper script dependencies: ensure cleanroom_mailbox.py is present in bin/ and support/lib/
    mb_src = os.path.join(root, "update_with_ai/support/lib/cleanroom_mailbox.py")
    if not os.path.exists(mb_src):
        mb_src = os.path.join(_repo_root, "update_with_ai/support/lib/cleanroom_mailbox.py")
    if os.path.isfile(mb_src):
        copy_file_with_perms(mb_src, os.path.join(workspace_dir, "bin/cleanroom_mailbox.py"), readonly=True)
        copy_file_with_perms(mb_src, os.path.join(workspace_dir, "update_with_ai/support/lib/cleanroom_mailbox.py"), readonly=True)

    # 3. Copy role guide (read-only)
    guide_target = role_def.get("guide", "")
    if guide_target:
        gt = guide_target.lstrip("/")
        if ":" in gt:
            g_pkg, g_name = gt.split(":", 1)
            guide_rel = f"{g_pkg}/{g_name}.md"
        else:
            guide_rel = f"{gt}.md"
        g_src = os.path.join(root, guide_rel)
        if not os.path.exists(g_src):
            g_src = os.path.join(_repo_root, guide_rel)
        if os.path.isfile(g_src):
            copy_file_with_perms(g_src, os.path.join(workspace_dir, guide_rel), readonly=True)

    # 4. Resolve active and dependency roles from define_role
    active_pattern = role_def.get("src_pattern", "")
    active_dir, active_prefix, active_suffix = parse_pattern_info(active_pattern)

    dep_targets: list[str] = []
    for dep_key in [
        "role_deps",
        "star_role_deps",
        "silent_role_deps",
        "silent_cross_role_deps",
        "feedback_role_deps",
        "stub_role_deps",
    ]:
        for target in role_def.get(dep_key, []):
            if target not in dep_targets:
                dep_targets.append(target)

    stub_deps_raw = role_def.get("stub_role_deps", [])
    stub_deps = {s.split(":")[-1] for s in stub_deps_raw}

    dep_infos: list[tuple[str, str, str, str, bool]] = []
    for d_target in dep_targets:
        d_name = d_target.split(":")[-1]
        if d_name == role_name:
            continue
        d_def = resolve_role_definition(d_target, root)
        d_pattern = d_def.get("src_pattern", "")
        if not d_pattern:
            continue
        d_dir, d_prefix, d_suffix = parse_pattern_info(d_pattern)
        is_stub = (d_name in stub_deps)
        dep_infos.append((d_name, d_dir, d_prefix, d_suffix, is_stub))

    part_map = get_part_module_map(repo_root=root, parts_bases=parts_bases)

    # 5. Provision parts directories
    for base in parts_bases:
        if is_build_enabled:
            for b_rel in [f"{base}/BUILD.bazel", f"{base}/parts/BUILD.bazel", f"{base}/support/BUILD.bazel"]:
                s_b = os.path.join(root, b_rel)
                d_b = os.path.join(workspace_dir, b_rel)
                if os.path.isfile(s_b):
                    with open(s_b, "r", encoding="utf-8") as f:
                        s_content = f.read()
                    write_file_with_perms(d_b, _ensure_allow_empty_in_globs(s_content), readonly=True)
                elif b_rel.endswith("BUILD.bazel"):
                    write_file_with_perms(d_b, "# Cleanroom empty package definition\n", readonly=True)

        for init_rel in [f"{base}/__init__.py", f"{base}/parts/__init__.py"]:
            s_init = os.path.join(root, init_rel)
            d_init = os.path.join(workspace_dir, init_rel)
            if os.path.exists(s_init):
                copy_file_with_perms(s_init, d_init, readonly=True)
            elif is_build_enabled:
                write_file_with_perms(d_init, "", readonly=True)

        parts_dir = os.path.join(root, base, "parts")
        if not os.path.exists(parts_dir):
            continue

        for part_name in os.listdir(parts_dir):
            part_path = os.path.join(parts_dir, part_name)
            if not os.path.isdir(part_path) or part_name.startswith("."):
                continue

            if is_build_enabled:
                part_b_src = os.path.join(part_path, "BUILD.bazel")
                part_b_dst = os.path.join(workspace_dir, base, "parts", part_name, "BUILD.bazel")
                if os.path.isfile(part_b_src):
                    with open(part_b_src, "r", encoding="utf-8") as f:
                        b_content = f.read()
                    write_file_with_perms(part_b_dst, _normalize_workspace_part_build(b_content), readonly=True)
                else:
                    write_file_with_perms(part_b_dst, "# Cleanroom empty package definition\n", readonly=True)

            init_file = os.path.join(part_path, "__init__.py")
            if os.path.exists(init_file):
                copy_file_with_perms(init_file, os.path.join(workspace_dir, base, "parts", part_name, "__init__.py"), readonly=True)

            # Active dir BUILD.bazel (read-only)
            if active_dir and is_build_enabled:
                active_src_dir = os.path.join(part_path, active_dir)
                b_file = os.path.join(active_src_dir, "BUILD.bazel")
                if os.path.exists(b_file):
                    copy_file_with_perms(b_file, os.path.join(workspace_dir, base, "parts", part_name, active_dir, "BUILD.bazel"), readonly=True)

            # Dependency files (read-only or stubs)
            for d_name, d_dir, d_prefix, d_suffix, is_stub in dep_infos:
                dep_src_dir = os.path.join(part_path, d_dir)
                ws_dep_dir = os.path.join(workspace_dir, base, "parts", part_name, d_dir)

                if is_stub:
                    os.makedirs(ws_dep_dir, exist_ok=True)
                    if is_build_enabled:
                        ws_dep_build = os.path.join(ws_dep_dir, "BUILD.bazel")
                        dep_build = os.path.join(dep_src_dir, "BUILD.bazel")
                        if os.path.exists(dep_build):
                            copy_file_with_perms(dep_build, ws_dep_build, readonly=True)

                    # Generate stubs for all units in parent BUILD.bazel from their .pyi specs
                    units = parse_part_units(part_b_src) if os.path.exists(part_b_src) else {}
                    for stem in units:
                        if stem.endswith("_ext"):
                            continue
                        d_f = os.path.join(ws_dep_dir, f"{stem}.py")
                        pyi_path = find_spec_pyi(part_path, stem, repo_root=root)
                        if pyi_path and os.path.exists(pyi_path):
                            try:
                                generate_readonly_test_stub(pyi_path, stem, d_f, dep_dir=d_dir, part_map=part_map)
                            except Exception as e:
                                print(f"Warning: could not generate stub for {stem}: {e}")
                                s_f = os.path.join(dep_src_dir, f"{stem}.py")
                                if os.path.exists(s_f):
                                    copy_file_with_perms(s_f, d_f, readonly=True)
                        else:
                            s_f = os.path.join(dep_src_dir, f"{stem}.py")
                            if os.path.exists(s_f):
                                copy_file_with_perms(s_f, d_f, readonly=True)
                else:
                    if not os.path.exists(dep_src_dir):
                        continue

                    if is_build_enabled:
                        dep_build = os.path.join(dep_src_dir, "BUILD.bazel")
                        if os.path.exists(dep_build):
                            copy_file_with_perms(dep_build, os.path.join(ws_dep_dir, "BUILD.bazel"), readonly=True)

                    for f in os.listdir(dep_src_dir):
                        if f.startswith(".") or f == "BUILD.bazel" or f == "__init__.py":
                            continue
                        if d_dir == active_dir:
                            continue
                        if f.startswith(d_prefix) and f.endswith(d_suffix):
                            s_f = os.path.join(dep_src_dir, f)
                            d_f = os.path.join(ws_dep_dir, f)
                            copy_file_with_perms(s_f, d_f, readonly=True)

    # 6. Deploy helper scripts to bin/ in workspace
    helper_bin_dir = os.path.join(workspace_dir, "bin")
    os.makedirs(helper_bin_dir, exist_ok=True)

    submit_sh = os.path.join(helper_bin_dir, "submit")
    write_file_with_perms(
        submit_sh,
        "#!/usr/bin/env bash\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nif [ -f \"$SCRIPT_DIR/cleanroom_mailbox.py\" ]; then\n    python3 \"$SCRIPT_DIR/cleanroom_mailbox.py\" submit \"$1\" \"$2\" --mailbox-dir .\nelse\n    python3 update_with_ai/support/lib/cleanroom_mailbox.py submit \"$1\" \"$2\" --mailbox-dir .\nfi\n",
        executable=True,
    )

    fail_sh = os.path.join(helper_bin_dir, "fail")
    write_file_with_perms(
        fail_sh,
        "#!/usr/bin/env bash\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nif [ -f \"$SCRIPT_DIR/cleanroom_mailbox.py\" ]; then\n    python3 \"$SCRIPT_DIR/cleanroom_mailbox.py\" fail \"$1\" \"$2\" --mailbox-dir .\nelse\n    python3 update_with_ai/support/lib/cleanroom_mailbox.py fail \"$1\" \"$2\" --mailbox-dir .\nfi\n",
        executable=True,
    )

    blame_sh = os.path.join(helper_bin_dir, "blame")
    if role_def.get("feedback_role_deps"):
        write_file_with_perms(
            blame_sh,
            "#!/usr/bin/env bash\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nif [ -f \"$SCRIPT_DIR/cleanroom_mailbox.py\" ]; then\n    python3 \"$SCRIPT_DIR/cleanroom_mailbox.py\" blame \"$1\" \"$2\" \"$3\" --mailbox-dir .\nelse\n    python3 update_with_ai/support/lib/cleanroom_mailbox.py blame \"$1\" \"$2\" \"$3\" --mailbox-dir .\nfi\n",
            executable=True,
        )
    elif os.path.exists(blame_sh):
        os.remove(blame_sh)

    # 7. Write Role-Tailored AGENTS.md
    write_role_agents_md(workspace_dir, role_def, repo_root=root)


def update_workspace_work_order(
    workspace_dir: str,
    repo_root: str,
    role_name: str,
    parts_bases: Sequence[str],
) -> None:
    """Updates WORK_ORDER.md in the workspace according to .update_with_ai.textproto in repo."""
    work_order_path = os.path.join(workspace_dir, "WORK_ORDER.md")
    all_dirty = find_all_dirty_nodes(repo_root, parts_dirs=parts_bases)
    ready_nodes = get_ready_dirty_nodes(all_dirty)
    role_nodes = [n for n in ready_nodes if n["role"] == role_name]

    if role_nodes:
        wo_lines = ["# Cleanroom Work Orders", ""]
        for node in role_nodes:
            wo_lines.append(f"CLEAN {node['target_file']}")
            for reason in node["reasons"]:
                wo_lines.append(f"REASON: {reason}")
            wo_lines.append("")
        write_file_with_perms(work_order_path, "\n".join(wo_lines) + "\n", readonly=False)
        print(f"Updated WORK_ORDER.md with {len(role_nodes)} pending task(s) for role '{role_name}'.")
    else:
        write_file_with_perms(work_order_path, "# Cleanroom Work Orders\n\nNo pending tasks.\n", readonly=False)


def setup_workspace(
    role: str,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
) -> str:
    """Sets up or updates a persistent role workspace using its define_role specification."""
    root = os.path.abspath(repo_root or _repo_root)
    clean_role = normalize_role_arg(role) or role
    role_def = resolve_role_definition(clean_role, root)
    role_name = role_def["name"]
    role_label = role_def.get("label", f"//update_python_with_ai:{role_name}")
    workspace_dir = os.path.abspath(dest or get_default_role_dir(role_name, repo_root=root))
    os.makedirs(workspace_dir, exist_ok=True)
    parts_bases = normalize_parts_dirs(root, parts_dirs=parts_dirs)

    print(f"Setting up Cleanroom role workspace for '{role_label}' ({role_name}) at: {workspace_dir} (parts: {', '.join(parts_bases)})")

    # 0. Declaratively prepare role artifacts (materialize templates & update derived BUILD files)
    prepare_role_artifacts(role_def, root, parts_bases)

    # 1. Copy all read-only files, tools, guides, build files, stubs, and scripts
    copy_readonly_files_and_stubs(workspace_dir, root, role_def, parts_bases)

    # 2. Copy initial active files (read-write) from canonical repo
    active_rw_files = find_read_write_files(root, role_def, parts_bases)
    for rel_path in active_rw_files:
        src_f = os.path.join(root, rel_path)
        dst_f = os.path.join(workspace_dir, rel_path)
        if not os.path.exists(dst_f):
            copy_file_with_perms(src_f, dst_f, readonly=False)

    # 3. Create Mailbox Files and populate WORK_ORDER.md
    update_workspace_work_order(workspace_dir, root, role_name, parts_bases)
    completed_path = os.path.join(workspace_dir, "COMPLETED.md")
    if not os.path.exists(completed_path):
        write_file_with_perms(completed_path, "", readonly=False)

    # 4. Save baseline read-only hashes for sync validation
    record_baseline_hashes(workspace_dir)

    # 5. Persist role metadata
    save_role_metadata(workspace_dir, role_label, role_name, parts_bases)

    print(f"Workspace setup complete: {workspace_dir}")
    print(f"To open in Antigravity: antigravity {workspace_dir}")
    return workspace_dir



def record_baseline_hashes(workspace_dir: str) -> None:
    """Records SHA-256 hashes of all read-only files for subsequent tamper checks."""
    hashes: Dict[str, str] = {}
    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if not d.startswith("bazel-") and d != ".git"]
        for f in files:
            p = os.path.join(root, f)
            try:
                st = os.stat(p)
                if not (st.st_mode & stat.S_IWUSR):  # read-only file
                    rel = os.path.relpath(p, workspace_dir)
                    hashes[rel] = compute_file_hash(p)
            except OSError:
                pass

    hash_file = os.path.join(workspace_dir, ".cleanroom_readonly_hashes.json")
    write_file_with_perms(hash_file, json.dumps(hashes, indent=2), readonly=False)


def verify_integrity(workspace_dir: str) -> None:
    """Verifies that no read-only files in the role workspace were modified."""
    hash_file = os.path.join(workspace_dir, ".cleanroom_readonly_hashes.json")
    if not os.path.exists(hash_file):
        return

    with open(hash_file, "r", encoding="utf-8") as f:
        baseline: Dict[str, str] = json.load(f)

    violations: list[str] = []
    for rel_path, expected_hash in baseline.items():
        actual_path = os.path.join(workspace_dir, rel_path)
        if not os.path.exists(actual_path):
            violations.append(f"Deleted read-only contract: {rel_path}")
            continue
        actual_hash = compute_file_hash(actual_path)
        if actual_hash != expected_hash:
            violations.append(f"Tampered read-only contract: {rel_path}")

    if violations:
        raise PermissionError(
            "Cleanroom Integrity Violation Detected! Read-only files were modified:\n"
            + "\n".join(f" - {v}" for v in violations)
        )


# ==============================================================================
# Canonical .update_with_ai.textproto Persistence & Dirty Node Discovery
# ==============================================================================


def load_package_textproto(textproto_path: str) -> Dict[str, Dict[str, Any]]:
    """Loads node records from .update_with_ai.textproto file."""
    if not os.path.isfile(textproto_path):
        return {}
    try:
        with open(textproto_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    nodes: Dict[str, Dict[str, Any]] = {}
    current_node_id: Optional[str] = None
    current_messages: List[Dict[str, str]] = []
    current_rev_deps: List[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("node_id:"):
            current_node_id = stripped.split(":", 1)[1].strip().strip('"')
            current_messages = []
            current_rev_deps = []
            nodes[current_node_id] = {
                "messages": current_messages,
                "reverse_dependencies": current_rev_deps,
            }
        elif stripped.startswith("reverse_dependencies:"):
            rev_dep = stripped.split(":", 1)[1].strip().strip('"')
            current_rev_deps.append(rev_dep)
        elif stripped.startswith("kind:"):
            kind = stripped.split(":", 1)[1].strip().strip('"')
            current_messages.append({"kind": kind, "content": "", "sender": ""})
        elif stripped.startswith("content:") and current_messages:
            content_val = stripped.split(":", 1)[1].strip().strip('"')
            current_messages[-1]["content"] = content_val
        elif stripped.startswith("sender:") and current_messages:
            sender_val = stripped.split(":", 1)[1].strip().strip('"')
            current_messages[-1]["sender"] = sender_val

    return nodes


def save_package_textproto(
    textproto_path: str, node_records: Dict[str, Dict[str, Any]]
) -> bool:
    """Writes package node messages and reverse dependencies to .update_with_ai.textproto."""
    lines: List[str] = []
    for node_id in sorted(node_records.keys()):
        record = node_records[node_id]
        lines.append("node {")
        lines.append(f'  node_id: "{node_id}"')

        for msg in record.get("messages", []):
            lines.append("  messages {")
            lines.append(f'    kind: "{msg.get("kind", "change")}"')
            lines.append(f'    content: "{msg.get("content", "")}"')
            if msg.get("sender"):
                lines.append(f'    sender: "{msg.get("sender")}"')
            lines.append("  }")

        for rev_dep in sorted(record.get("reverse_dependencies", [])):
            lines.append(f'  reverse_dependencies: "{rev_dep}"')

        lines.append("}")

    content = "\n".join(lines) + "\n"
    try:
        os.makedirs(os.path.dirname(textproto_path), exist_ok=True)
        with open(textproto_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except OSError:
        return False


def find_all_textprotos(
    repo_root: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
) -> List[str]:
    """Finds all .update_with_ai.textproto files across canonical directories."""
    root = os.path.abspath(repo_root or _repo_root)
    bases = normalize_parts_dirs(root, parts_dirs=parts_dirs)
    found: List[str] = []
    search_dirs = [os.path.join(root, b) for b in bases]
    py_ai = os.path.join(root, "update_python_with_ai")
    if os.path.exists(py_ai) and py_ai not in search_dirs:
        search_dirs.append(py_ai)

    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue
        for r, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if not d.startswith("bazel-") and d != ".git"]
            if ".update_with_ai.textproto" in files:
                found.append(os.path.join(r, ".update_with_ai.textproto"))
    return sorted(found)


def parse_node_id(node_id: str, repo_root: Optional[str] = None) -> tuple[str, str, str]:
    """Parses node_id into (pkg, unit_name, role).

    Example formats:
      //path/to/part:component#//role_package:role_name
      //path/to/part:component_role_name
    """
    s = node_id.strip()
    if "#" in s:
        unit_part, role_part = s.split("#", 1)
        role = role_part.split(":")[-1]
        unit_str = unit_part.lstrip("/")
        pkg, unit_name = unit_str.split(":", 1) if ":" in unit_str else (unit_str, "")
    else:
        unit_str = s.lstrip("/")
        pkg, target_name = unit_str.split(":", 1) if ":" in unit_str else ("", unit_str)
        role = ""
        root = repo_root or _repo_root
        roles_dict = load_defined_roles(root)
        known_roles = sorted(
            [d["name"] for d in roles_dict.values() if isinstance(d, dict) and "name" in d],
            key=len,
            reverse=True,
        )
        for r_name in known_roles:
            if target_name.endswith(f"_{r_name}"):
                role = r_name
                unit_name = target_name[: -len(r_name) - 1]
                break
        if not role:
            unit_name = target_name

    return pkg, unit_name, role


def node_to_target_path(repo_root: str, pkg: str, unit_name: str, role: str) -> str:
    """Derives canonical repo relative target file path from node coordinates."""
    role_def = resolve_role_definition(role, repo_root)
    src_pattern = role_def.get("src_pattern", "")
    if src_pattern:
        return src_pattern.replace("{unit_dir}", pkg).replace("{unit_name}", unit_name)
    return f"{pkg}/{role}/{unit_name}.py"


def target_path_to_node_info(repo_root: str, rel_path: str) -> tuple[str, str, str, str, str]:
    """Maps a repo-relative file path to (pkg, unit_name, role, node_id, textproto_path)."""
    norm_path = rel_path.strip().lstrip("/")
    parts = norm_path.split("/")

    defined_roles = load_defined_roles(repo_root)
    unique_roles = {d["name"]: d for d in defined_roles.values() if isinstance(d, dict) and "name" in d}

    matched_role = None
    matched_pkg = ""
    matched_unit = ""

    for role_name, rdef in unique_roles.items():
        src_pattern = rdef.get("src_pattern", "")
        if not src_pattern:
            continue
        dir_name, prefix, suffix = parse_pattern_info(src_pattern)
        if not dir_name:
            continue
        if f"/{dir_name}/" in f"/{norm_path}":
            idx = parts.index(dir_name)
            candidate_pkg = "/".join(parts[:idx])
            base = parts[-1]
            if base.startswith(prefix) and (base.endswith(suffix) or not suffix):
                stem = base[len(prefix) : -len(suffix)] if suffix else base[len(prefix) :]
                matched_role = role_name
                matched_pkg = candidate_pkg
                matched_unit = stem
                break

    if not matched_role:
        matched_pkg = os.path.dirname(norm_path)
        matched_unit = os.path.splitext(os.path.basename(norm_path))[0]
        matched_role = ""

    textproto_path = os.path.join(repo_root, matched_pkg, ".update_with_ai.textproto")

    matched_node_id = None
    if os.path.exists(textproto_path):
        data = load_package_textproto(textproto_path)
        for n_id in data.keys():
            p, u, r = parse_node_id(n_id)
            if u == matched_unit and r == matched_role:
                matched_node_id = n_id
                break

    if not matched_node_id:
        r_label = unique_roles[matched_role].get("label") if matched_role in unique_roles else f":{matched_role}"
        matched_node_id = f"//{matched_pkg}:{matched_unit}#{r_label}"

    return matched_pkg, matched_unit, matched_role, matched_node_id, textproto_path


def find_all_dirty_nodes(
    repo_root: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Discovers all dirty nodes across .update_with_ai.textproto files."""
    root = os.path.abspath(repo_root or _repo_root)
    textprotos = find_all_textprotos(root, parts_dirs=parts_dirs)
    dirty_nodes: List[Dict[str, Any]] = []

    for tp in textprotos:
        rel_pkg = os.path.relpath(os.path.dirname(tp), root).replace(os.sep, "/")
        data = load_package_textproto(tp)
        for node_id, record in data.items():
            messages = record.get("messages", [])
            if not messages:
                continue
            parsed_pkg, unit_name, role = parse_node_id(node_id)
            pkg = rel_pkg if rel_pkg and rel_pkg != "." else parsed_pkg
            target_path = node_to_target_path(root, pkg, unit_name, role)

            reasons: List[str] = []
            for msg in messages:
                kind = msg.get("kind", "change").capitalize()
                sender = msg.get("sender")
                content = msg.get("content", "")
                if sender:
                    reasons.append(f"{kind} from {sender}: {content}")
                else:
                    reasons.append(f"{kind}: {content}")

            dirty_nodes.append({
                "node_id": node_id,
                "pkg": pkg,
                "unit_name": unit_name,
                "role": role,
                "target_file": target_path,
                "messages": messages,
                "reasons": reasons,
                "reverse_dependencies": record.get("reverse_dependencies", []),
                "textproto_path": tp,
            })

    return dirty_nodes


def compute_role_phase_order(repo_root: Optional[str] = None) -> Dict[str, int]:
    """Dynamically computes phase ordering ranks for all defined roles from their dependency graph."""
    root = repo_root or _repo_root
    roles = load_defined_roles(root)
    unique_roles: Dict[str, Dict[str, Any]] = {}
    for r in roles.values():
        if isinstance(r, dict) and "name" in r:
            unique_roles[r["name"]] = r

    if not unique_roles:
        return {}

    deps_map: Dict[str, set[str]] = {name: set() for name in unique_roles}
    for name, rdef in unique_roles.items():
        candidates: list[str] = []
        candidates.extend(rdef.get("role_deps", []))
        candidates.extend(rdef.get("star_role_deps", []))
        candidates.extend(rdef.get("feedback_role_deps", []))
        candidates.extend(rdef.get("silent_role_deps", []))

        stub_deps = {s.split(":")[-1] for s in rdef.get("stub_role_deps", [])}

        for dep_label in candidates:
            dep_name = dep_label.split(":")[-1]
            if dep_name == name:
                continue
            if dep_name in stub_deps:
                continue
            if dep_name in unique_roles:
                deps_map[name].add(dep_name)

    ranks: Dict[str, int] = {}
    visited: set[str] = set()

    def get_rank(r: str) -> int:
        if r in ranks:
            return ranks[r]
        if r in visited:
            return 0
        visited.add(r)
        prereqs = deps_map.get(r, set())
        if not prereqs:
            ranks[r] = 0
        else:
            ranks[r] = 1 + max(get_rank(p) for p in prereqs)
        visited.remove(r)
        return ranks[r]

    for name in unique_roles:
        get_rank(name)

    return ranks


ROLE_PHASE_ORDER = compute_role_phase_order()


def get_ready_dirty_nodes(
    dirty_nodes: List[Dict[str, Any]], repo_root: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filters dirty nodes to those that are ready to clean according to Cleanroom phase ordering.

    Computes phase order dynamically from define_role dependency graph.
    """
    phase_order = compute_role_phase_order(repo_root=repo_root)
    by_unit: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for node in dirty_nodes:
        key = (node["pkg"], node["unit_name"])
        by_unit.setdefault(key, []).append(node)

    ready_nodes: List[Dict[str, Any]] = []
    for (pkg, unit_name), u_nodes in by_unit.items():
        min_phase = min(phase_order.get(n["role"], 99) for n in u_nodes)
        for n in u_nodes:
            if phase_order.get(n["role"], 99) == min_phase:
                ready_nodes.append(n)

    return ready_nodes


def assign_task(
    role: str,
    target: str,
    reason: str,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> None:
    """Appends a CLEAN task to WORK_ORDER.md and injects a message into .update_with_ai.textproto."""
    root = os.path.abspath(repo_root or _repo_root)
    workspace_dir = os.path.abspath(dest or get_default_role_dir(role))
    work_order_path = os.path.join(workspace_dir, "WORK_ORDER.md")
    os.makedirs(workspace_dir, exist_ok=True)

    # 1. Update WORK_ORDER.md
    with open(work_order_path, "a", encoding="utf-8") as f:
        f.write(f"CLEAN {target.strip()}\nREASON: {reason.strip()}\n\n")

    # 2. Mirror into canonical .update_with_ai.textproto
    pkg, unit_name, r_name, node_id, tp_path = target_path_to_node_info(root, target)
    if os.path.exists(tp_path):
        data = load_package_textproto(tp_path)
        rec = data.setdefault(node_id, {"messages": [], "reverse_dependencies": []})
        rec["messages"].append({"kind": "change", "content": reason.strip(), "sender": "manual"})
        save_package_textproto(tp_path, data)

    print(f"Assigned to {role}: {target}")


def remove_completed_work_order(workspace_dir: str, target: str) -> None:
    """Removes a completed target block from WORK_ORDER.md."""
    wo_path = os.path.join(workspace_dir, "WORK_ORDER.md")
    if not os.path.exists(wo_path):
        return
    with open(wo_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.split("CLEAN ")
    new_blocks = [blocks[0]]
    norm_t = target.strip().lstrip("/")

    for b in blocks[1:]:
        first_line = b.splitlines()[0].strip().lstrip("/")
        if first_line == norm_t:
            continue
        new_blocks.append("CLEAN " + b)

    new_content = "".join(new_blocks).strip()
    if not new_content or new_content == "# Cleanroom Work Orders":
        new_content = "# Cleanroom Work Orders\n\nNo pending tasks.\n"
    else:
        new_content = new_content + "\n"

    write_file_with_perms(wo_path, new_content, readonly=False)


def find_modified_read_write_files(
    workspace_dir: str,
    repo_root: str,
    role_def: Dict[str, Any],
    parts_bases: Optional[Sequence[str]] = None,
) -> List[str]:
    """Finds all read-write files in the role workspace that are new or modified compared to canonical."""
    active_pattern = role_def.get("src_pattern", "")
    if not active_pattern:
        return []
    active_dir, active_prefix, active_suffix = parse_pattern_info(active_pattern)
    if not active_dir:
        return []

    bases = normalize_parts_dirs(repo_root, parts_dirs=parts_bases)
    modified: List[str] = []

    for base in bases:
        ws_parts = os.path.join(workspace_dir, base, "parts")
        if not os.path.isdir(ws_parts):
            continue
        for part_name in sorted(os.listdir(ws_parts)):
            ws_part_dir = os.path.join(ws_parts, part_name)
            if not os.path.isdir(ws_part_dir) or part_name.startswith("."):
                continue
            ws_active_dir = os.path.join(ws_part_dir, active_dir)
            if not os.path.isdir(ws_active_dir):
                continue
            for root_dir, _, files in os.walk(ws_active_dir):
                for f in sorted(files):
                    if f.startswith(".") or f == "BUILD.bazel" or f == "__init__.py":
                        continue
                    if not (f.startswith(active_prefix) and f.endswith(active_suffix)):
                        continue
                    src_file = os.path.join(root_dir, f)
                    try:
                        st = os.stat(src_file)
                        if not (st.st_mode & stat.S_IWUSR):
                            continue
                    except OSError:
                        continue
                    rel_path = os.path.relpath(src_file, workspace_dir)
                    dst_file = os.path.join(repo_root, rel_path)
                    if not os.path.exists(dst_file):
                        modified.append(rel_path)
                    else:
                        if compute_file_hash(src_file) != compute_file_hash(dst_file):
                            modified.append(rel_path)

    return modified


def run_bazel_target(repo_root: str, target: str, args: Optional[Sequence[str]] = None) -> bool:
    """Executes a bazel run target, returning True if successful."""
    cmd = ["bazel", "run", target]
    if args:
        cmd.append("--")
        cmd.extend(args)
    try:
        res = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode == 0:
            return True
        print(f"Notice: 'bazel run {target}' exited with {res.returncode}; falling back to direct state persistence.")
        return False
    except Exception as e:
        print(f"Notice: could not execute 'bazel run {target}': {e}; falling back to direct state persistence.")
        return False


def mark_node_clean(repo_root: str, target_rel_path: str) -> None:
    """Clears messages for the node using bazel run <target>_mark_clean (with textproto fallback)."""
    pkg, unit_name, role, node_id, tp_path = target_path_to_node_info(repo_root, target_rel_path)
    bazel_target = f"//{pkg}:{unit_name}_{role}_mark_clean"
    success = run_bazel_target(repo_root, bazel_target)
    if not success and os.path.exists(tp_path):
        data = load_package_textproto(tp_path)
        if node_id in data:
            data[node_id]["messages"] = []
            save_package_textproto(tp_path, data)
            print(f"CLEARED MESSAGES (fallback) for {node_id} in {tp_path}")


def broadcast_node_change(repo_root: str, target_rel_path: str, summary: str) -> None:
    """Broadcasts a change message to reverse dependencies using bazel run <target>_change (with textproto fallback)."""
    pkg, unit_name, role, node_id, tp_path = target_path_to_node_info(repo_root, target_rel_path)
    bazel_target = f"//{pkg}:{unit_name}_{role}_change"
    success = run_bazel_target(repo_root, bazel_target, [summary])
    if not success and os.path.exists(tp_path):
        data = load_package_textproto(tp_path)
        if node_id in data:
            record = data[node_id]
            rev_deps = list(record.get("reverse_dependencies", []))
            record["messages"] = []
            record["reverse_dependencies"] = []
            save_package_textproto(tp_path, data)
            print(f"CLEARED MESSAGES AND DEPENDENTS (fallback) for {node_id} in {tp_path}")

            for rev_dep in rev_deps:
                r_pkg, r_unit, r_role = parse_node_id(rev_dep)
                r_tp = os.path.join(repo_root, r_pkg, ".update_with_ai.textproto")
                if os.path.exists(r_tp):
                    r_data = load_package_textproto(r_tp)
                    r_rec = r_data.setdefault(rev_dep, {"messages": [], "reverse_dependencies": []})
                    r_rec["messages"].append({
                        "kind": "change",
                        "content": f"Upstream change in {target_rel_path}: {summary}",
                        "sender": node_id,
                    })
                    save_package_textproto(r_tp, r_data)
                    print(f"PROPAGATED CHANGE (fallback) to {rev_dep} in {r_tp}")


def mark_node_dirty(repo_root: str, target_rel_path: str, change: str = "check") -> None:
    """Marks a node dirty and registers it as a dependent on all its dependencies using bazel run <target>_dirty (with textproto fallback)."""
    pkg, unit_name, role, node_id, tp_path = target_path_to_node_info(repo_root, target_rel_path)
    bazel_target = f"//{pkg}:{unit_name}_{role}_dirty"
    success = run_bazel_target(repo_root, bazel_target, [change])
    if not success and os.path.exists(tp_path):
        data = load_package_textproto(tp_path)
        rec = data.setdefault(node_id, {"messages": [], "reverse_dependencies": []})
        rec["messages"].append({
            "kind": "change",
            "content": change,
        })
        save_package_textproto(tp_path, data)
        # Register node_id as reverse dependency on non-silent role dependencies
        role_def = resolve_role_definition(role, repo_root)
        dep_roles = list(role_def.get("role_deps", [])) + list(role_def.get("star_role_deps", [])) + list(role_def.get("feedback_role_deps", []))
        for r_dep in dep_roles:
            r_name = r_dep.split(":")[-1]
            if r_name == role:
                continue
            r_def = resolve_role_definition(r_dep, repo_root)
            r_label = r_def.get("label", r_dep)
            dep_node_id = f"//{pkg}:{unit_name}#{r_label}"
            d_rec = data.setdefault(dep_node_id, {"messages": [], "reverse_dependencies": []})
            if node_id not in d_rec["reverse_dependencies"]:
                d_rec["reverse_dependencies"].append(node_id)
                d_rec["reverse_dependencies"].sort()
                save_package_textproto(tp_path, data)
        print(f"MARKED DIRTY AND REGISTERED DEPENDENT (fallback) for {node_id} in {tp_path}")


def deliver_node_feedback(repo_root: str, blame_target_rel_path: str, explanation: str, sender: str = "") -> None:
    """Delivers feedback to a blame target using bazel run <target>_feedback (with textproto fallback)."""
    b_pkg, b_unit, b_role, b_node_id, b_tp = target_path_to_node_info(repo_root, blame_target_rel_path)
    bazel_target = f"//{b_pkg}:{b_unit}_{b_role}_feedback"
    success = run_bazel_target(repo_root, bazel_target, [explanation])
    if not success and os.path.exists(b_tp):
        b_data = load_package_textproto(b_tp)
        b_rec = b_data.setdefault(b_node_id, {"messages": [], "reverse_dependencies": []})
        b_rec["messages"].append({
            "kind": "feedback",
            "content": f"Feedback from {sender or 'role'} ({blame_target_rel_path}): {explanation}",
            "sender": sender or blame_target_rel_path,
        })
        save_package_textproto(b_tp, b_data)
        print(f"RECORDED FEEDBACK (fallback) on {b_node_id} in {b_tp}")


def converge_role_workspace(
    workspace_dir: str,
    repo_root: str,
    role: str,
    parts_dirs: Optional[Sequence[str]] = None,
    sync_all: bool = False,
) -> List[Dict[str, Any]]:
    """Runs the unified convergence lifecycle for a role workspace."""
    root = repo_root
    clean_role = normalize_role_arg(role) or role
    role_def = resolve_role_definition(clean_role, root)
    role_name = role_def["name"]
    role_label = role_def.get("label", f"//update_python_with_ai:{role_name}")
    parts_bases = normalize_parts_dirs(root, parts_dirs=parts_dirs)

    # 1. Verify read-only file integrity (anti-chmod protection)
    verify_integrity(workspace_dir)

    synced_events: List[Dict[str, Any]] = []

    # 2. Inbound sync & COMPLETED.md processing
    if sync_all:
        # --all mode: strictly goes by edit time; does NOT modify .update_with_ai.textproto
        rw_role_files = find_read_write_files(workspace_dir, role_def, parts_bases)
        for rel_path in rw_role_files:
            src_f = os.path.join(workspace_dir, rel_path)
            dst_f = os.path.join(root, rel_path)
            if not os.path.exists(dst_f) or os.path.getmtime(src_f) > os.path.getmtime(dst_f):
                copy_file_with_perms(src_f, dst_f, readonly=False)
                print(f"SYNCED (--all) [{role_name}]: {rel_path} -> {dst_f}")
                synced_events.append({"type": "ALL", "target": rel_path})
    else:
        # Standard mode: process COMPLETED.md first
        entries = read_and_clear(workspace_dir)
        for entry in entries:
            t_type = entry.get("type")
            target = entry.get("target", "").lstrip("/")

            if t_type == "SUBMIT":
                src_f = os.path.join(workspace_dir, target)
                dst_f = os.path.join(root, target)
                if os.path.exists(src_f) and not target.endswith(".log"):
                    copy_file_with_perms(src_f, dst_f, readonly=False)
                    print(f"SYNCED [{role_name}]: {target} -> {dst_f}")
                else:
                    print(f"RECORDED [{role_name}]: {target} (Summary: {entry.get('change', '')})")

                summary = entry.get("change", "Updated specification")
                # Clear origin node messages and broadcast changes to reverse dependencies
                mark_node_clean(root, target)
                if summary:
                    broadcast_node_change(root, target, summary)
                synced_events.append(entry)

            elif t_type == "BLAME":
                # Copy submit target from role workspace to canonical repo
                src_f = os.path.join(workspace_dir, target)
                dst_f = os.path.join(root, target)
                if os.path.exists(src_f) and not target.endswith(".log"):
                    copy_file_with_perms(src_f, dst_f, readonly=False)
                    print(f"SYNCED (blame submit target) [{role_name}]: {target} -> {dst_f}")

                blame_target = entry.get("blame_target", "")
                explanation = entry.get("blame_explanation", "")
                allowed_fb_roles = {r.split(":")[-1] for r in role_def.get("feedback_role_deps", [])}
                if allowed_fb_roles:
                    try:
                        _, _, b_role, _, _ = target_path_to_node_info(root, blame_target)
                        if b_role not in allowed_fb_roles:
                            print(f"WARNING: [{role_name}] blamed {blame_target} (role '{b_role}'), but declared feedback_role_deps are {allowed_fb_roles}")
                    except Exception:
                        pass
                print(f"BLAME REPORTED [{role_name}]: {target} blames {blame_target}: {explanation}")
                deliver_node_feedback(root, blame_target, explanation, sender=f"{role_name} ({target})")
                synced_events.append(entry)

            elif t_type == "FAIL":
                print(f"FAILURE REPORTED [{role_name}]: {target} (Reason: {entry.get('reason')})")
                synced_events.append(entry)

    # 3. Declaratively prepare role artifacts before syncing read-only files
    prepare_role_artifacts(role_def, root, parts_bases)
    copy_readonly_files_and_stubs(workspace_dir, root, role_def, parts_bases)
    write_role_agents_md(workspace_dir, role_def, repo_root=root)

    # 4. Outbound read-write sync: if canonical workspace file is newer than role file, copy it over
    rw_ws_files = find_read_write_files(root, role_def, parts_bases)
    for rel_path in rw_ws_files:
        src_f = os.path.join(root, rel_path)
        dst_f = os.path.join(workspace_dir, rel_path)
        if not os.path.exists(dst_f) or os.path.getmtime(src_f) > os.path.getmtime(dst_f):
            copy_file_with_perms(src_f, dst_f, readonly=False)
            print(f"OUTBOUND SYNC [{role_name}]: {rel_path} -> {dst_f}")

    # 5. Update WORK_ORDER.md according to .update_with_ai.textproto in workspace
    update_workspace_work_order(workspace_dir, root, role_name, parts_bases)

    # 6. Record baseline hashes and save role metadata
    record_baseline_hashes(workspace_dir)
    save_role_metadata(workspace_dir, role_label, role_name, parts_bases)

    return synced_events


def sync_workspace(
    role: str,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
    sync_all: bool = False,
) -> List[Dict[str, Any]]:
    """Backward-compatible wrapper around converge_role_workspace."""
    root = os.path.abspath(repo_root or _repo_root)
    clean_role = normalize_role_arg(role) or role
    role_def = resolve_role_definition(clean_role, root)
    workspace_dir = os.path.abspath(dest or get_default_role_dir(role_def["name"], repo_root=root))
    if not os.path.exists(workspace_dir):
        print(f"Workspace not found: {workspace_dir}")
        return []
    return converge_role_workspace(
        workspace_dir=workspace_dir,
        repo_root=root,
        role=clean_role,
        parts_dirs=parts_dirs,
        sync_all=sync_all,
    )


def cleanroom_sync(
    role: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
    sync_all: bool = False,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Unified Cleanroom sync command: creates/converges role workspace or syncs all existing role workspaces."""
    root = os.path.abspath(repo_root or _repo_root)

    if role:
        clean_role = normalize_role_arg(role) or role
        role_def = resolve_role_definition(clean_role, root)
        role_name = role_def["name"]
        workspace_dir = os.path.abspath(dest or get_default_role_dir(role_name, repo_root=root))

        if not os.path.exists(workspace_dir):
            print(f"Role workspace '{role_name}' does not exist. Initializing at: {workspace_dir}")
            setup_workspace(role=clean_role, dest=workspace_dir, repo_root=root, parts_dirs=parts_dirs)

        converge_role_workspace(
            workspace_dir=workspace_dir,
            repo_root=root,
            role=clean_role,
            parts_dirs=parts_dirs,
            sync_all=sync_all,
        )
        return 0

    # If role is NOT specified: sync all existing role workspaces discovered in parent dir
    existing_workspaces = find_existing_role_workspaces(repo_root=root)
    if not existing_workspaces:
        print("No existing role workspaces found. Specify --role to set up and sync a new workspace.")
        return 0

    print(f"Found {len(existing_workspaces)} existing role workspace(s) to sync.")

    def _phase_key(item: tuple[str, Dict[str, Any]]) -> int:
        role_n = item[1].get("role_name", "")
        return ROLE_PHASE_ORDER.get(role_n, 99)

    sorted_workspaces = sorted(existing_workspaces, key=_phase_key)

    for ws_dir, meta in sorted_workspaces:
        role_addr = meta.get("role_address") or meta.get("role_name")
        ws_parts = parts_dirs if parts_dirs else meta.get("parts_dirs")
        print(f"\n>>> Converging existing workspace: {ws_dir} (role: {role_addr})")
        converge_role_workspace(
            workspace_dir=ws_dir,
            repo_root=root,
            role=role_addr,
            parts_dirs=ws_parts,
            sync_all=sync_all,
        )

    return 0


def wait_workspace(role: str, dest: Optional[str] = None, timeout: Optional[float] = None) -> int:
    """Blocks until submissions exist in the role workspace, then returns 0."""
    workspace_dir = os.path.abspath(dest or get_default_role_dir(role))
    ready = wait_for_completion(workspace_dir, timeout_sec=timeout)
    if ready:
        print(f"Submissions ready in {role} workspace.")
        return 0
    else:
        print(f"Timed out waiting for {role} workspace.")
        return 1


def dispatch_dirty_work(
    role_filter: Optional[str] = None,
    target_filter: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
    wait: bool = False,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Dispatches ready dirty nodes from .update_with_ai.textproto to their role workspaces."""
    root = os.path.abspath(repo_root or _repo_root)
    all_dirty = find_all_dirty_nodes(root, parts_dirs=parts_dirs)

    if not all_dirty:
        print("Cleanroom Complete: No dirty nodes found across .update_with_ai.textproto files.")
        return 0

    if target_filter:
        tf = target_filter.strip()
        all_dirty = [
            n for n in all_dirty
            if tf in n["node_id"] or tf in n["target_file"] or tf in n["unit_name"]
        ]
        if not all_dirty:
            print(f"No dirty nodes matching target filter '{target_filter}'.")
            return 0

    ready_nodes = get_ready_dirty_nodes(all_dirty)

    if role_filter:
        clean_role_filter = normalize_role_arg(role_filter)
        ready_nodes = [n for n in ready_nodes if n["role"] == clean_role_filter]
        if not ready_nodes:
            print(f"No ready dirty nodes for role '{role_filter}'.")
            return 0

    by_role: Dict[str, List[Dict[str, Any]]] = {}
    for n in ready_nodes:
        by_role.setdefault(n["role"], []).append(n)

    for role_name, nodes in by_role.items():
        ws_dir = setup_workspace(role_name, dest=dest, repo_root=root, parts_dirs=parts_dirs)
        work_order_path = os.path.join(ws_dir, "WORK_ORDER.md")

        wo_lines = ["# Cleanroom Work Orders", ""]
        for node in nodes:
            wo_lines.append(f"CLEAN {node['target_file']}")
            for reason in node["reasons"]:
                wo_lines.append(f"REASON: {reason}")
            wo_lines.append("")

        write_file_with_perms(work_order_path, "\n".join(wo_lines) + "\n", readonly=False)

        print("\n" + "=" * 65)
        print(f"CLEANROOM WORK DISPATCHED -> ROLE: {role_name.upper()}")
        print(f"Workspace Location: {ws_dir}")
        print("Assigned Work Orders:")
        for node in nodes:
            print(f"  - {node['target_file']} ({len(node['reasons'])} reasons)")
        print("\nInstructions:")
        print(f"  1. In conversation chat for workspace '{ws_dir}', execute assigned tasks.")
        print("  2. Workers verify locally and submit using: bin/submit <target> \"<summary>\"")
        print(f"  3. In main workspace, run: cleanroom-sync --role {role_name}")
        print("=" * 65 + "\n")

    if wait and len(by_role) == 1:
        single_role = list(by_role.keys())[0]
        print(f"Waiting for {single_role} submissions...")
        res = wait_workspace(single_role, dest=dest)
        if res == 0:
            cleanroom_sync(role=single_role, dest=dest, repo_root=root, parts_dirs=parts_dirs)
        return res

    return 0


def verify_target(target: str) -> int:
    """Runs Bazel test for target with mandatory Cleanroom verification flags."""
    cmd = [
        "bazel",
        "test",
        target,
        "--test_output=errors",
        "--test_timeout=100",
        "--noshow_progress",
        "--noshow_loading_progress",
    ]
    print(f"Executing Cleanroom verification: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=_repo_root)
    return res.returncode


def show_status(
    role: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> None:
    """Displays current dirty nodes across textproto files and workspace status."""
    root = os.path.abspath(repo_root or _repo_root)
    all_dirty = find_all_dirty_nodes(root, parts_dirs=parts_dirs)

    print("\n" + "=" * 65)
    print("CLEANROOM CANONICAL STATUS (.update_with_ai.textproto)")
    print("=" * 65)
    if not all_dirty:
        print("  All nodes clean! No pending messages.")
    else:
        print(f"  Found {len(all_dirty)} dirty node(s):")
        for dn in all_dirty:
            print(f"  - [{dn['role'].upper()}] {dn['target_file']} ({dn['node_id']})")
            for r in dn["reasons"]:
                print(f"      • {r}")

    print("\n" + "=" * 65)
    print("CLEANROOM ROLE WORKSPACE STATUS")
    if role:
        roles = [role]
    else:
        defined = load_defined_roles(root)
        phase_order = compute_role_phase_order(repo_root=root)
        unique_names = list({d["name"] for d in defined.values() if isinstance(d, dict) and "name" in d})
        roles = sorted(unique_names, key=lambda r: (phase_order.get(r, 99), r))
    for r in roles:
        ws_dir = os.path.abspath(dest or get_default_role_dir(r))
        if not os.path.exists(ws_dir):
            continue
        print(f"\n--- Role: {r.upper()} ({ws_dir}) ---")
        wo_path = os.path.join(ws_dir, "WORK_ORDER.md")
        if os.path.exists(wo_path):
            with open(wo_path, "r", encoding="utf-8") as f:
                wo_content = f.read().strip()
            print("Pending Work Orders:")
            print("  " + "\n  ".join(wo_content.splitlines()[:10]))
            if len(wo_content.splitlines()) > 10:
                print("  ... [truncated]")
        comp_path = os.path.join(ws_dir, "COMPLETED.md")
        if os.path.exists(comp_path):
            with open(comp_path, "r", encoding="utf-8") as f:
                comp_content = f.read().strip()
            print("Pending Submissions:")
            if comp_content:
                print("  " + "\n  ".join(comp_content.splitlines()[:10]))
            else:
                print("  (None)")
        r_def = resolve_role_definition(r, root)
        modified_files = find_modified_read_write_files(ws_dir, root, r_def, parts_bases=parts_dirs)
        if modified_files:
            print(f"Modified Read-Write Files (out-of-band changes, {len(modified_files)}):")
            for mf in modified_files[:10]:
                print(f"  * {mf}")
            if len(modified_files) > 10:
                print("  ... [truncated]")
    print("=" * 65 + "\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    subcommands = {"setup", "assign", "sync", "wait", "dispatch", "verify", "status"}

    # If first arg is a known subcommand, use subcommand parser
    if raw_args and raw_args[0] in subcommands:
        parser = argparse.ArgumentParser(description="Cleanroom Role Workspace Management Tool")
        subparsers = parser.add_subparsers(dest="command", required=True)

        # setup
        p_setup = subparsers.add_parser("setup", help="Set up or update a role workspace")
        p_setup.add_argument("--role", required=True, help="Role name or target label (e.g. '//pkg:role', 'role')")
        p_setup.add_argument("--dest", help="Custom destination directory")
        p_setup.add_argument("--parts-dir", "--parts-dirs", dest="parts_dirs", nargs="+", help="Directories whose parts to work with (e.g. 'staging', 'update_with_ai')")

        # assign
        p_assign = subparsers.add_parser("assign", help="Assign a CLEAN task to a role workspace")
        p_assign.add_argument("--role", required=True, help="Role name or target label")
        p_assign.add_argument("--target", required=True, help="Target file path")
        p_assign.add_argument("--reason", default="Upstream change detected", help="Reason for cleaning")
        p_assign.add_argument("--dest", help="Custom destination directory")

        # sync
        p_sync = subparsers.add_parser("sync", help="Synchronize submissions from role workspace to canonical repo")
        p_sync.add_argument("--role", help="Role Bazel target or name (e.g. '//pkg:role', 'role')")
        sync_mode = p_sync.add_mutually_exclusive_group()
        sync_mode.add_argument("--all", action="store_true", help="Sync all modified read-write files by edit time without textproto changes")
        sync_mode.add_argument("--submitted", action="store_true", default=False, help="Sync only submitted files from COMPLETED.md (default)")
        p_sync.add_argument("--dest", help="Custom destination directory")
        p_sync.add_argument("--parts-dir", "--parts-dirs", dest="parts_dirs", nargs="+", help="Filter synchronization by parts directory")

        # wait
        p_wait = subparsers.add_parser("wait", help="Wait for role submissions to complete (background task friendly)")
        p_wait.add_argument("--role", required=True, help="Role name or target label")
        p_wait.add_argument("--timeout", type=float, default=None, help="Timeout in seconds")
        p_wait.add_argument("--dest", help="Custom destination directory")

        # dispatch
        p_dispatch = subparsers.add_parser("dispatch", help="Dispatch ready dirty nodes to role workspace")
        p_dispatch.add_argument("--role", help="Optional role filter (e.g. '//pkg:role', 'role')")
        p_dispatch.add_argument("--target", help="Optional target filter (matches node_id or target path)")
        p_dispatch.add_argument("--parts-dir", "--parts-dirs", dest="parts_dirs", nargs="+", help="Directories whose parts to work with (e.g. 'staging', 'update_with_ai')")
        p_dispatch.add_argument("--wait", action="store_true", help="Wait for role completion and sync automatically")
        p_dispatch.add_argument("--dest", help="Custom destination directory")

        # verify
        p_verify = subparsers.add_parser("verify", help="Run Bazel test with Cleanroom flags")
        p_verify.add_argument("--target", required=True, help="Bazel test target")

        # status
        p_status = subparsers.add_parser("status", help="Show work order and submission status")
        p_status.add_argument("--role", help="Filter by role name or target label")
        p_status.add_argument("--parts-dir", "--parts-dirs", dest="parts_dirs", nargs="+", help="Filter status by parts directory")
        p_status.add_argument("--dest", help="Custom destination directory")

        args = parser.parse_args(raw_args)

        if args.command == "setup":
            setup_workspace(args.role, dest=args.dest, parts_dirs=args.parts_dirs)
            return 0
        elif args.command == "assign":
            assign_task(normalize_role_arg(args.role) or args.role, args.target, args.reason, dest=args.dest)
            return 0
        elif args.command == "sync":
            return cleanroom_sync(role=args.role, parts_dirs=args.parts_dirs, sync_all=args.all, dest=args.dest)
        elif args.command == "wait":
            return wait_workspace(normalize_role_arg(args.role) or args.role, dest=args.dest, timeout=args.timeout)
        elif args.command == "dispatch":
            return dispatch_dirty_work(
                role_filter=args.role,
                target_filter=args.target,
                parts_dirs=args.parts_dirs,
                wait=args.wait,
                dest=args.dest,
            )
        elif args.command == "verify":
            return verify_target(args.target)
        elif args.command == "status":
            show_status(role=normalize_role_arg(args.role) or args.role, parts_dirs=args.parts_dirs, dest=args.dest)
            return 0

    # Unified cleanroom-sync CLI
    sync_parser = argparse.ArgumentParser(prog="cleanroom-sync", description="Cleanroom Workspace Sync Tool")
    sync_parser.add_argument("--role", help="Role name or target label (e.g. '//pkg:role', 'role')")
    sync_parser.add_argument("--parts-dir", "--parts-dirs", dest="parts_dirs", nargs="+", help="Filter by parts directory (e.g. 'staging')")
    sync_parser.add_argument("--all", action="store_true", help="Sync all modified read-write files by edit time without textproto changes")
    sync_parser.add_argument("--dest", help="Custom destination directory")

    args = sync_parser.parse_args(raw_args)
    return cleanroom_sync(
        role=args.role,
        parts_dirs=args.parts_dirs,
        sync_all=args.all,
        dest=args.dest,
    )


if __name__ == "__main__":
    sys.exit(main())
