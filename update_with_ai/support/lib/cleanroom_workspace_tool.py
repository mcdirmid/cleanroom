#!/usr/bin/env python3
"""cleanroom_workspace_tool.py — Orchestrates subagentless Cleanroom role workspaces.

Features:
- Provisions directory-scoped role workspaces: ../role_workspaces/<workspace_name>_<role>_<sanitized_dir>.
- Native In-Band Source Metadata tracking via src_metadata.py (no out-of-band textproto or mailboxes).
- Dynamic forward dirtiness evaluation and logless auditor certification (<ROLE>_AUDIT).
- Read-only upstream contracts (chmod 444) and synthesized interface stubs.
- Lockless blame buffering (.cleanroom_blame_buffer.json) for read-only upstream defect attribution.
- Omni-directional cascading synchronization (Inbound Harvest -> Outbound Cascade -> Conflict Detection).
"""

from __future__ import annotations

import argparse
import ast
import copy
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import zipfile


def _find_repo_root() -> str:
    real_path = os.path.realpath(__file__)
    curr = os.path.dirname(real_path)
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "MODULE.bazel")) or os.path.exists(
            os.path.join(curr, ".git")
        ):
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

import src_metadata
from lib_lint import (
    generate_asm_content,
    generate_lib_skeleton,
    is_uninitialized_module,
)
from test_lint import generate_test_skeleton, is_uninitialized_test_module
from build_lint_common import parse_part_units

AUDITOR_ROLE_TAGS: Dict[str, str] = {
    "grounding_qa": "GROUNDING_QA_AUDIT",
    "qa": "QA_AUDIT",
    "coverage": "COVERAGE_AUDIT",
}

BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
AUDIT_BUFFER_FILE = ".cleanroom_audit_buffer.json"


def is_auditor_role(role_name: str) -> bool:
    """Checks whether the role is a logless verification auditor."""
    return role_name.strip().lstrip(":") in AUDITOR_ROLE_TAGS


def classify_unit_type(unit_name: str) -> str:
    """Classifies a unit as external, assembly, implementation, or interface (default)."""
    if unit_name.endswith("_ext"):
        return "external"
    if unit_name.endswith("_asm"):
        return "assembly"
    if unit_name.endswith("_impl"):
        return "implementation"
    return "interface"


def compute_file_hash(path: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _ensure_allow_empty_in_globs(content: str) -> str:
    """Ensures all glob(...) calls in BUILD content include allow_empty = True."""
    content = re.sub(r"allow_empty\s*=\s*False", "allow_empty = True", content)

    def _repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        if "allow_empty" in inner:
            return match.group(0)
        return f"glob({inner}, allow_empty = True)"

    return re.sub(r"glob\(([^)]+)\)", _repl, content)


def _normalize_workspace_part_build(content: str) -> str:
    """Normalizes part BUILD content for role workspace isolation and sandboxing."""
    return _ensure_allow_empty_in_globs(content)


def sanitize_dir_scope(dir_scope: str) -> str:
    """Sanitizes directory scope for directory naming (e.g. 'update_with_ai/parts/agent' -> 'update_with_ai_parts_agent')."""
    clean = dir_scope.strip().strip("/").replace("\\", "/")
    return clean.replace("/", "_") or "root"


def get_default_role_dir(
    role: str,
    dir_scope: str = "staging",
    repo_root: Optional[str] = None,
) -> str:
    """Returns default workspace path: ../role_workspaces/<ws_name>_<role>_<sanitized_dir>."""
    root = os.path.abspath(repo_root or _repo_root)
    ws_name = os.path.basename(root)
    parent_dir = os.path.dirname(root)
    clean_role = role.split(":")[-1] if ":" in role else role
    sanitized_dir = sanitize_dir_scope(dir_scope)
    return os.path.join(
        parent_dir, "role_workspaces", f"{ws_name}_{clean_role}_{sanitized_dir}"
    )


def resolve_main_workspace_from_convention(
    cwd: Optional[str] = None,
) -> Tuple[str, str, str, str]:
    """Resolves (main_workspace_root, workspace_name, role_address, dir_scope) from convention and descriptor."""
    curr = os.path.realpath(cwd or os.getcwd())

    # 1. Climb up to find the role workspace directory inside 'role_workspaces'
    role_ws_dir = curr
    while role_ws_dir and role_ws_dir != os.path.dirname(role_ws_dir):
        parent = os.path.dirname(role_ws_dir)
        if os.path.basename(parent) == "role_workspaces":
            break
        role_ws_dir = parent
    else:
        # Fallback: check if curr or any ancestor contains .cleanroom_role.json
        cand = curr
        found_ws = None
        while cand and cand != os.path.dirname(cand):
            if os.path.isfile(os.path.join(cand, ".cleanroom_role.json")):
                found_ws = cand
                break
            cand = os.path.dirname(cand)
        if found_ws:
            role_ws_dir = found_ws
        else:
            raise RuntimeError(
                f"Current workspace '{curr}' is not located inside a 'role_workspaces' directory and contains no .cleanroom_role.json."
            )

    role_ws_name = os.path.basename(role_ws_dir)
    parent_dir = os.path.dirname(role_ws_dir)

    # 2. Read pathless descriptor if present
    cfg_file = os.path.join(role_ws_dir, ".cleanroom_role.json")
    role_address = ""
    dir_scope = ""
    legacy_main_root = None
    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                role_address = data.get("role_address", "")
                dir_scope = data.get("parts_dir", "")
                legacy_main_root = data.get("main_workspace_root")
        except Exception as e:
            sys.stderr.write(
                f"Warning: Failed to parse role descriptor '{cfg_file}': {e}\n"
            )

    # 3. Match candidate main workspace directories in projects_root
    main_root: Optional[str] = None
    workspace_name: str = ""
    remainder: str = ""

    if os.path.basename(parent_dir) == "role_workspaces":
        projects_root = os.path.dirname(parent_dir)
        if os.path.isdir(projects_root):
            for entry in sorted(os.listdir(projects_root)):
                cand_main = os.path.join(projects_root, entry)
                if os.path.isdir(cand_main) and entry != "role_workspaces":
                    prefix = f"{entry}_"
                    if role_ws_name.startswith(prefix):
                        main_root = cand_main
                        workspace_name = entry
                        remainder = role_ws_name[len(prefix) :]
                        break
        if not main_root:
            if legacy_main_root and os.path.isdir(legacy_main_root):
                main_root = legacy_main_root
                workspace_name = os.path.basename(legacy_main_root)
            else:
                raise RuntimeError(
                    f"Could not locate matching main workspace for '{role_ws_name}' in '{projects_root}'."
                )
    else:
        # Non-standard or test directory
        if legacy_main_root and os.path.isdir(legacy_main_root):
            main_root = legacy_main_root
            workspace_name = os.path.basename(legacy_main_root)
        else:
            # Check siblings in parent_dir
            for entry in sorted(os.listdir(parent_dir)):
                cand_main = os.path.join(parent_dir, entry)
                if os.path.isdir(cand_main) and cand_main != role_ws_dir:
                    prefix = f"{entry}_"
                    if role_ws_name.startswith(prefix):
                        main_root = cand_main
                        workspace_name = entry
                        remainder = role_ws_name[len(prefix) :]
                        break
            if not main_root:
                main_root = parent_dir
                workspace_name = os.path.basename(parent_dir)

    # 4. Fallback role parsing if descriptor was missing
    if not role_address and main_root:
        roles_dict = load_defined_roles(main_root)
        known_roles = [
            r["name"]
            for r in roles_dict.values()
            if isinstance(r, dict) and "name" in r
        ]
        for r in sorted(known_roles, key=len, reverse=True):
            if remainder == r or remainder.startswith(f"{r}_"):
                role_address = f"//update_python_with_ai:{r}"
                if not dir_scope:
                    dir_scope = remainder[len(r) :].lstrip("_") or "staging"
                break

    return main_root, workspace_name, role_address, dir_scope or "staging"


def save_role_metadata(
    workspace_dir: str,
    role_address: str,
    role_name: str,
    parts_dirs: Optional[Sequence[str]] = None,
    dir_scope: Optional[str] = None,
    commissioned_at: Optional[str] = None,
    last_sync_timestamp: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> None:
    """Saves pathless .cleanroom_role.json in the workspace root."""
    meta_path = os.path.join(workspace_dir, ".cleanroom_role.json")
    now = src_metadata.current_utc_timestamp()

    # Determine parts_dir string
    primary_dir = dir_scope
    if not primary_dir and parts_dirs:
        primary_dir = parts_dirs[0]
    if not primary_dir:
        primary_dir = "staging"

    # Normalize role_address to full label if short name was provided
    if not role_address.startswith("//") and not role_address.startswith(":"):
        role_address = f"//update_python_with_ai:{role_address}"

    existing = load_role_metadata(workspace_dir) or {}
    data: Dict[str, Any] = {
        "role_address": role_address,
        "role_name": role_name,
        "parts_dir": primary_dir,
        "commissioned_at": commissioned_at or existing.get("commissioned_at") or now,
        "last_sync_timestamp": last_sync_timestamp
        or existing.get("last_sync_timestamp")
        or now,
    }
    # Keep parts_dirs for backward compatibility if present
    if parts_dirs:
        data["parts_dirs"] = list(parts_dirs)

    write_file_with_perms(meta_path, json.dumps(data, indent=2) + "\n", readonly=False)


def load_role_metadata(workspace_dir: str) -> Optional[Dict[str, Any]]:
    """Loads .cleanroom_role.json from a workspace directory if present, resolving main workspace convention."""
    meta_path = os.path.join(workspace_dir, ".cleanroom_role.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "main_workspace_root" not in data:
                try:
                    main_root, ws_name, _, _ = resolve_main_workspace_from_convention(
                        workspace_dir
                    )
                    data["main_workspace_root"] = main_root
                    data["main_workspace"] = ws_name
                except Exception as e:
                    sys.stderr.write(
                        f"Warning: Could not resolve main workspace by convention for '{workspace_dir}': {e}\n"
                    )
            return data
        except Exception as e:
            sys.stderr.write(
                f"Warning: Failed loading role metadata from '{meta_path}': {e}\n"
            )
            return None
    return None


WORKSPACES_REGISTRY_FILE = ".cleanroom_workspaces.json"


def get_workspaces_registry_path(repo_root: Optional[str] = None) -> str:
    """Returns absolute path to the .cleanroom_workspaces.json registry file."""
    root = os.path.abspath(repo_root or _repo_root)
    return os.path.join(root, WORKSPACES_REGISTRY_FILE)


def load_registered_workspaces(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads active commissioned workspaces from .cleanroom_workspaces.json."""
    path = get_workspaces_registry_path(repo_root)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "workspaces" in data:
                return list(data["workspaces"])
            elif isinstance(data, list):
                return list(data)
        except Exception as e:
            sys.stderr.write(
                f"Warning: Failed reading registered workspaces from '{path}': {e}\n"
            )
    return []


def save_registered_workspaces(
    workspaces: List[Dict[str, Any]], repo_root: Optional[str] = None
) -> None:
    """Saves active commissioned workspaces to .cleanroom_workspaces.json."""
    try:
        path = get_workspaces_registry_path(repo_root)
        content = json.dumps({"workspaces": workspaces}, indent=2) + "\n"
        write_file_with_perms(path, content, readonly=False)
    except (PermissionError, OSError) as e:
        sys.stderr.write(
            f"Warning: Failed saving registered workspaces to '{path}': {e}\n"
        )


def record_commissioned_workspace(
    role: str, dir_scope: str, workspace_dir: str, repo_root: Optional[str] = None
) -> None:
    """Records a commissioned role workspace in .cleanroom_workspaces.json."""
    workspaces = load_registered_workspaces(repo_root)
    clean_role = normalize_role_arg(role) or role
    norm_ws = os.path.abspath(workspace_dir)
    for entry in workspaces:
        if entry.get("role") == clean_role and entry.get("dir") == dir_scope:
            entry["workspace_dir"] = norm_ws
            save_registered_workspaces(workspaces, repo_root)
            return
    workspaces.append(
        {
            "role": clean_role,
            "dir": dir_scope,
            "workspace_dir": norm_ws,
        }
    )
    save_registered_workspaces(workspaces, repo_root)


def unrecord_commissioned_workspace(
    role: str, dir_scope: str, repo_root: Optional[str] = None
) -> None:
    """Removes a decommissioned workspace from .cleanroom_workspaces.json."""
    workspaces = load_registered_workspaces(repo_root)
    clean_role = normalize_role_arg(role) or role
    filtered = [
        w
        for w in workspaces
        if not (w.get("role") == clean_role and w.get("dir") == dir_scope)
    ]
    save_registered_workspaces(filtered, repo_root)


def find_existing_role_workspaces(
    repo_root: Optional[str] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Finds all existing role workspace directories containing .cleanroom_role.json."""
    root = os.path.abspath(repo_root or _repo_root)
    ws_name = os.path.basename(root)
    parent_dir = os.path.dirname(root)
    found: List[Tuple[str, Dict[str, Any]]] = []
    seen_dirs: Set[str] = set()

    # 1. Primary fast check: registered workspaces in .cleanroom_workspaces.json
    registered = load_registered_workspaces(root)
    active_registered: List[Dict[str, Any]] = []
    for reg in registered:
        ws_dir = reg.get("workspace_dir")
        if ws_dir and os.path.isdir(ws_dir):
            meta = load_role_metadata(ws_dir)
            if meta and "role_name" in meta:
                found.append((ws_dir, meta))
                seen_dirs.add(ws_dir)
                active_registered.append(reg)
    if len(active_registered) != len(registered):
        save_registered_workspaces(active_registered, root)

    # 2. Check ../role_workspaces/<ws_name>_* for unrecorded workspaces
    workspaces_container = os.path.join(parent_dir, "role_workspaces")
    if os.path.isdir(workspaces_container):
        for d in sorted(os.listdir(workspaces_container)):
            if not d.startswith(f"{ws_name}_") and not d.startswith("."):
                continue
            ws_dir = os.path.join(workspaces_container, d)
            if ws_dir not in seen_dirs and os.path.isdir(ws_dir):
                meta = load_role_metadata(ws_dir)
                if meta and "role_name" in meta:
                    found.append((ws_dir, meta))
                    seen_dirs.add(ws_dir)
                    record_commissioned_workspace(
                        meta["role_name"],
                        meta.get("parts_dir", "staging"),
                        ws_dir,
                        repo_root=root,
                    )

    # 3. Check legacy or sibling directories in parent_dir
    legacy_container = os.path.join(parent_dir, f"{ws_name}_workspaces")
    if os.path.isdir(legacy_container):
        for d in sorted(os.listdir(legacy_container)):
            ws_dir = os.path.join(legacy_container, d)
            if ws_dir not in seen_dirs and os.path.isdir(ws_dir):
                meta = load_role_metadata(ws_dir)
                if meta and "role_name" in meta:
                    found.append((ws_dir, meta))
                    seen_dirs.add(ws_dir)

    return found


def _eval_ast_node(node: Any, env: Dict[str, Any]) -> Any:
    """Evaluates an AST expression supporting constants, lists, dicts, variable lookup, and list additions."""
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


DEFAULT_ROLE_SPEC: Dict[str, Any] = {
    "src_pattern": "",
    "template": None,
    "prompt_template": "",
    "guide": None,
    "allows_step_mode": True,
    "node_deps": [],
    "role_deps": [],
    "silent_role_deps": [],
    "stub_role_deps": [],
    "star_role_deps": [],
    "silent_cross_role_deps": [],
    "feedback_role_deps": [],
    "active_component_types": [
        "implementation",
        "assembly",
        "interface",
        "external",
    ],
    "verify_template": "",
    "verification_success_message": "",
    "persona": "",
    "workspace_files": [],
    "tools": [],
    "derive_build_template": "",
}


def load_defined_roles(repo_root: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Parses define_role declarations from update_*_with_ai/BUILD.bazel using ast."""
    root = os.path.abspath(repo_root or _repo_root)
    build_files: List[Tuple[str, str]] = []

    candidates = ["update_python_with_ai"]
    if os.path.isdir(root):
        for entry in os.listdir(root):
            if (
                entry.startswith("update_")
                and entry.endswith("_with_ai")
                and entry not in candidates
            ):
                candidates.append(entry)

    for pkg_name in candidates:
        bf = os.path.join(root, pkg_name, "BUILD.bazel")
        if not os.path.isfile(bf):
            bf = os.path.join(_repo_root, pkg_name, "BUILD.bazel")
        if os.path.isfile(bf):
            build_files.append((pkg_name, bf))

    roles: Dict[str, Dict[str, Any]] = {}

    if not build_files:
        return roles

    aliases: Dict[str, str] = {}

    for pkg_name, build_file in build_files:
        with open(build_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=build_file)
            except Exception as e:
                sys.stderr.write(
                    f"Warning: Failed parsing BUILD file '{build_file}': {e}\n"
                )
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
                            base_def = copy.deepcopy(DEFAULT_ROLE_SPEC)
                            base_def.update(kwargs)
                            roles[name] = base_def
                            roles[f":{name}"] = base_def
                            roles[f"//{pkg_name}:{name}"] = base_def
                    elif func.id == "alias":
                        kwargs = {}
                        for kw in node.value.keywords:
                            if kw.arg:
                                kwargs[kw.arg] = _eval_ast_node(kw.value, env)
                        name = kwargs.get("name")
                        actual = kwargs.get("actual")
                        if name and actual:
                            aliases[name] = str(actual)
                            aliases[f":{name}"] = str(actual)
                            aliases[f"//{pkg_name}:{name}"] = str(actual)

    for alias_name, actual_target in aliases.items():
        clean_target = actual_target.lstrip(":")
        if clean_target in roles:
            roles[alias_name] = roles[clean_target]
        elif actual_target in roles:
            roles[alias_name] = roles[actual_target]

    return roles


def resolve_role_definition(
    role_str: str, repo_root: Optional[str] = None
) -> Dict[str, Any]:
    """Resolves a role target label or short name to its define_role metadata."""
    roles = load_defined_roles(repo_root)
    s = role_str.strip()
    if s in roles:
        return dict(roles[s])
    short = s.split(":")[-1]
    if short in roles:
        return dict(roles[short])
    if roles:
        known = sorted(
            [
                k
                for k in roles.keys()
                if not k.startswith(":") and not k.startswith("//")
            ]
        )
        raise ValueError(f"Unknown Cleanroom role '{role_str}'. Defined roles: {known}")
    raise ValueError(
        f"No Cleanroom roles defined in workspace. Could not resolve '{role_str}'."
    )


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
    """Resolves and normalizes parts directory bases (e.g. 'staging', 'update_with_ai')."""
    root = os.path.abspath(repo_root or _repo_root)

    if not parts_dirs:
        candidates = ["update_with_ai", "staging", "testing"]
        discovered: List[str] = []
        for c in candidates:
            if os.path.isdir(os.path.join(root, c, "parts")) or os.path.isdir(
                os.path.join(root, c)
            ):
                discovered.append(c)
        return discovered or ["staging"]

    raw_items: List[str] = []
    for item in parts_dirs:
        for sub_item in item.split(","):
            s = sub_item.strip()
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
) -> Dict[str, Tuple[str, str]]:
    """Maps module name -> (part_name, base_dir) across specified parts directories."""
    root = os.path.abspath(repo_root or _repo_root)
    bases = normalize_parts_dirs(root, parts_dirs=parts_bases)
    mapping: Dict[str, Tuple[str, str]] = {}
    for base in bases:
        parts_dir = (
            os.path.join(root, base, "parts")
            if not base.endswith("parts")
            else os.path.join(root, base)
        )
        if not os.path.isdir(parts_dir):
            continue
        for p in os.listdir(parts_dir):
            p_dir = os.path.join(parts_dir, p)
            if not os.path.isdir(p_dir) or p.startswith("."):
                continue
            with os.scandir(p_dir) as it:
                for entry in it:
                    if (
                        entry.is_dir()
                        and not entry.name.startswith(".")
                        and not entry.name.startswith("_")
                    ):
                        for f in os.listdir(entry.path):
                            if f.endswith(".py") or f.endswith(".pyi"):
                                mod_name = f.rsplit(".", 1)[0]
                                mapping[mod_name] = (p, base)
    return mapping


def parse_pattern_info(src_pattern: str) -> Tuple[str, str, str]:
    """Extracts (directory, prefix, suffix) from a src_pattern."""
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

    skeleton = generate_lib_skeleton(pyi_path, stem, parts_base=current_base)

    with open(pyi_path, "r", encoding="utf-8") as f:
        pyi_tree = ast.parse(f.read(), filename=pyi_path)

    lifecycle_names: Set[str] = set()
    for node in pyi_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in (
            "support.lib.lifecycle",
            "lifecycle",
        ):
            for a in node.names:
                lifecycle_names.add(a.name)

    if part_map is None:
        part_map = get_part_module_map(parts_bases=[current_base])

    stub_lines: List[str] = [
        "from __future__ import annotations",
    ]
    if lifecycle_names:
        stub_lines.append(
            f"from support.lib.lifecycle import {', '.join(sorted(lifecycle_names))}"
        )

    stub_lines.extend(
        [
            f"# Requirements specified in {os.path.basename(pyi_path)}",
            "# CLEANROOM TEST STUB: Implementation details omitted. Refer strictly to companion .pyi file.",
            "",
        ]
    )

    for line in skeleton.splitlines():
        if line.startswith("from __future__") or line.startswith("# Requirements"):
            continue

        m = re.match(
            r"^import\s+([a-zA-Z0-9_]+)(?:\s+as\s+([a-zA-Z0-9_]+))?$", line.strip()
        )
        if m:
            mod_name = m.group(1)
            alias = f" as {m.group(2)}" if m.group(2) else ""
            if mod_name in part_map:
                target_part, target_base = part_map[mod_name]
                if target_part == current_part and target_base == current_base:
                    line = f"from . import {mod_name}{alias}"
                else:
                    line = f"from {target_base}.parts.{target_part}.{dep_dir} import {mod_name}{alias}"

        if ".parts." in line:
            line = re.sub(r"\b[a-zA-Z0-9_]+\.parts\.", f"{current_base}.parts.", line)

        if line.strip().startswith("# TODO_"):
            continue

        if line.strip() == "raise NotImplementedError":
            indent = " " * (len(line) - len(line.lstrip()))
            stub_lines.append(
                f'{indent}raise NotImplementedError("Cleanroom Test Stub: Behavior specified in .pyi")'
            )
        else:
            stub_lines.append(line)

    write_file_with_perms(out_path, "\n".join(stub_lines) + "\n", readonly=True)


def is_stub_dep_file(
    rel_path: str,
    role_def: Dict[str, Any],
    repo_root: Optional[str] = None,
) -> bool:
    """Returns True if rel_path matches any role in stub_role_deps."""
    stub_deps_raw = role_def.get("stub_role_deps", [])
    if not stub_deps_raw:
        return False
    root = repo_root or _repo_root
    for stub_target in stub_deps_raw:
        stub_def = resolve_role_definition(stub_target, root)
        stub_pat = stub_def.get("src_pattern", "")
        if stub_pat:
            s_dir, s_pfx, s_sfx = parse_pattern_info(stub_pat)
            fname = os.path.basename(rel_path)
            parent = os.path.basename(os.path.dirname(rel_path))
            if (
                parent == s_dir
                and fname.startswith(s_pfx)
                and fname.endswith(s_sfx)
                and fname not in ("BUILD.bazel", "__init__.py")
            ):
                return True
    return False


def sync_stub_dep_file(
    rel_path: str,
    workspace_dir: str,
    main_repo_root: str,
    role_def: Dict[str, Any],
    part_map: Optional[Dict[str, Tuple[str, str]]] = None,
) -> bool:
    """Ensures rel_path is maintained as a read-only test stub in workspace_dir.

    Returns True if the stub was created or regenerated.
    """
    ws_f = os.path.join(workspace_dir, rel_path)
    main_f = os.path.join(main_repo_root, rel_path)

    parts = rel_path.split(os.sep)
    if "parts" not in parts:
        return False
    parts_idx = parts.index("parts")
    if len(parts) < parts_idx + 4:
        return False
    base_dir = os.sep.join(parts[:parts_idx])
    part_name = parts[parts_idx + 1]
    dep_dir = parts[parts_idx + 2]
    fname = parts[parts_idx + 3]
    stem = os.path.splitext(fname)[0]

    part_path = (
        os.path.join(main_repo_root, base_dir, "parts", part_name)
        if base_dir
        else os.path.join(main_repo_root, "parts", part_name)
    )
    pyi_path = find_spec_pyi(part_path, stem, repo_root=main_repo_root)

    # Check if ws_f is already a valid cleanroom test stub
    is_valid_stub = False
    if os.path.isfile(ws_f):
        try:
            with open(ws_f, "r", encoding="utf-8") as f:
                content = f.read(500)
                if "CLEANROOM TEST STUB" in content:
                    is_valid_stub = True
        except OSError as e:
            sys.stderr.write(f"Warning: Failed reading stub '{ws_f}': {e}\n")

    # Check if pyi changed since stub was generated
    needs_generation = not is_valid_stub
    if is_valid_stub and pyi_path and os.path.isfile(pyi_path):
        try:
            if os.path.getmtime(pyi_path) > os.path.getmtime(ws_f):
                needs_generation = True
        except OSError as e:
            sys.stderr.write(
                f"Warning: Failed checking stub timestamp for '{ws_f}': {e}\n"
            )

    if needs_generation:
        os.makedirs(os.path.dirname(ws_f), exist_ok=True)
        if pyi_path and os.path.isfile(pyi_path):
            try:
                generate_readonly_test_stub(
                    pyi_path,
                    stem,
                    ws_f,
                    dep_dir=dep_dir,
                    part_map=part_map,
                )
                return True
            except Exception as e:
                print(f"Warning: could not generate stub for {stem}: {e}")
        # Fallback: synthesize minimal stub if pyi not found, NEVER copy main_f
        stub_lines = [
            "from __future__ import annotations",
            f"# Requirements specified in {stem}.pyi",
            "# CLEANROOM TEST STUB: Implementation details omitted. Refer strictly to companion .pyi file.",
            "",
            f"raise NotImplementedError('Cleanroom Test Stub: {stem}')\n",
        ]
        write_file_with_perms(ws_f, "\n".join(stub_lines), readonly=True)
        return True
    return False


def write_file_with_perms(
    dst: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    """Writes a text file and sets exact permissions, handling existing read-only files cleanly."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.chmod(dst, 0o644)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
    mode = 0o755 if executable else (0o444 if readonly else 0o644)
    os.chmod(dst, mode)


def copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
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


def find_spec_pyi(
    part_path: str, stem: str, repo_root: Optional[str] = None
) -> Optional[str]:
    """Finds companion .pyi specification file for a unit stem in a part directory."""
    if os.path.isdir(part_path):
        with os.scandir(part_path) as it:
            for entry in it:
                if (
                    entry.is_dir()
                    and not entry.name.startswith(".")
                    and not entry.name.startswith("_")
                ):
                    candidate = os.path.join(entry.path, f"{stem}.pyi")
                    if os.path.isfile(candidate):
                        return candidate
    return None


def resolve_template_path(
    template_ref: str, repo_root: Optional[str] = None
) -> Optional[str]:
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
    return None


def resolve_node_dep_src(
    node_dep_ref: str,
    repo_root: Optional[str] = None,
    default_pkg: str = "update_python_with_ai",
) -> Optional[str]:
    """Resolves a node dependency reference (label or path) to its repo-relative source path."""
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
        if os.path.isfile(os.path.join(root, rel)) or os.path.isfile(
            os.path.join(_repo_root, rel)
        ):
            return rel

    return None


def ensure_role_templates_in_place(
    part_path: str, role_def: Dict[str, Any], repo_root: Optional[str] = None
) -> List[str]:
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

    materialized: List[str] = []

    stub_targets = role_def.get("stub_role_deps", [])
    tested_pkg = None
    if stub_targets:
        stub_def = resolve_role_definition(stub_targets[0], repo_root)
        s_pattern = stub_def.get("src_pattern", "")
        s_dir, _, _ = parse_pattern_info(s_pattern)
        if s_dir:
            tested_pkg = os.path.join(part_path, s_dir)

    tmpl_ref = role_def.get("template")
    tmpl_path = (
        resolve_template_path(tmpl_ref, repo_root=repo_root) if tmpl_ref else None
    )
    raw_template_content = None
    if tmpl_path and os.path.isfile(tmpl_path):
        try:
            with open(tmpl_path, "r", encoding="utf-8") as tf:
                raw_template_content = tf.read()
        except OSError as e:
            sys.stderr.write(
                f"Warning: Failed reading template '{tmpl_path}': {e}\n"
            )
            raw_template_content = None

    for stem, raw_deps in units.items():
        if stem.endswith("_ext"):
            continue
        if allowed_types is not None and classify_unit_type(stem) not in allowed_types:
            continue
        file_path = src_pattern.format(unit_dir=part_path, unit_name=stem)
        mod_exists = os.path.isfile(file_path)
        mod_content = ""
        if mod_exists:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    mod_content = f.read()
            except OSError as e:
                sys.stderr.write(
                    f"Warning: Failed reading file '{file_path}': {e}\n"
                )

        if mod_exists and mod_content.strip():
            continue

        dir_path = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(dir_path, exist_ok=True)
        try:
            new_content = ""
            if stem.endswith("_asm") and generate_asm_content:
                new_content = generate_asm_content(dir_path, raw_deps)
            elif tested_pkg and generate_test_skeleton:
                pyi_path = find_spec_pyi(part_path, stem, repo_root=repo_root)
                if pyi_path and os.path.isfile(pyi_path):
                    test_stem = os.path.splitext(os.path.basename(file_path))[0]
                    new_content = generate_test_skeleton(
                        pyi_path, test_stem, stem, tested_pkg
                    )
                else:
                    new_content = (
                        raw_template_content
                        if raw_template_content is not None
                        else f"from __future__ import annotations\n\n# Tests for {stem}\n"
                    )
            else:
                pyi_path = find_spec_pyi(part_path, stem, repo_root=repo_root)
                if pyi_path and os.path.isfile(pyi_path) and generate_lib_skeleton:
                    new_content = generate_lib_skeleton(pyi_path, stem)
                else:
                    new_content = (
                        raw_template_content
                        if raw_template_content is not None
                        else f"from __future__ import annotations\n\n# Requirements specified in {stem}.pyi\n"
                    )

            if mod_content:
                old_meta = src_metadata.extract_metadata_from_text(
                    mod_content, file_path
                )
                if old_meta and (
                    old_meta.last_cleaned
                    or old_meta.last_changed
                    or old_meta.feedback
                    or old_meta.audits
                ):
                    new_content = src_metadata.rewrite_metadata_in_text(
                        content=new_content,
                        filename_or_ext=file_path,
                        last_cleaned=old_meta.last_cleaned,
                        last_changed=old_meta.last_changed,
                        change_summary=old_meta.change_summary,
                        audits=old_meta.audits,
                    )

            write_file_with_perms(file_path, new_content, readonly=False)
            materialized.append(file_path)
        except (PermissionError, OSError) as e:
            sys.stderr.write(
                f"Warning: Failed materializing template to '{file_path}': {e}\n"
            )

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
        parts_root = (
            os.path.join(repo_root, base, "parts")
            if not base.endswith("parts")
            else os.path.join(repo_root, base)
        )
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

            if has_template:
                materialized = ensure_role_templates_in_place(
                    part_path, role_def, repo_root=repo_root
                )
                if materialized:
                    print(f"Materialized {len(materialized)} template(s) in {rel_part}")

            if derive_build_cmd:
                cmd = derive_build_cmd.format(unit_dir=rel_part)
                env = dict(os.environ)
                env.pop("TEST_SRCDIR", None)
                env.pop("TEST_WORKSPACE", None)
                if _repo_root not in env.get("PYTHONPATH", ""):
                    env["PYTHONPATH"] = (
                        f"{_repo_root}:{env.get('PYTHONPATH', '')}".rstrip(":")
                    )
                tokens = cmd.split()
                if (
                    len(tokens) >= 2
                    and tokens[0] == "python3"
                    and not os.path.isabs(tokens[1])
                ):
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
                        print(
                            f"Warning: derive_build_template failed for {rel_part}: {res.stderr.strip()}"
                        )
                except Exception as e:
                    print(
                        f"Warning: could not run derive_build_template for {rel_part}: {e}"
                    )


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

    bases = normalize_parts_dirs(base_dir, parts_dirs=parts_bases)
    files_found: List[str] = []

    for base in bases:
        parts_root = (
            os.path.join(base_dir, base, "parts")
            if not base.endswith("parts")
            else os.path.join(base_dir, base)
        )
        if not os.path.isdir(parts_root):
            # Check if base itself is the parts directory or part package
            if os.path.isdir(os.path.join(base_dir, base, active_dir)):
                for r, _, files in os.walk(os.path.join(base_dir, base, active_dir)):
                    for f in sorted(files):
                        if (
                            f.startswith(".")
                            or f == "BUILD.bazel"
                            or f == "__init__.py"
                        ):
                            continue
                        if f.startswith(active_prefix) and f.endswith(active_suffix):
                            full_p = os.path.join(r, f)
                            files_found.append(os.path.relpath(full_p, base_dir))
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
                        stem = (
                            f[len(active_prefix) : -len(active_suffix)]
                            if active_suffix
                            else f[len(active_prefix) :]
                        )
                        if (
                            allowed_types is not None
                            and classify_unit_type(stem) not in allowed_types
                        ):
                            continue
                        full_p = os.path.join(r, f)
                        rel_p = os.path.relpath(full_p, base_dir)
                        files_found.append(rel_p)

    return files_found


def write_role_agents_md(
    workspace_dir: str, role_or_def: Any, repo_root: Optional[str] = None
) -> None:
    """Generates custom AGENTS.md at the workspace root without legacy mailboxes."""
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
    is_auditor = is_auditor_role(role) or not active_pattern

    verify_cmd = (
        role_def.get("verify_template", "")
        .replace("cd $BUILD_WORKSPACE_DIRECTORY && ", "")
        .strip()
    )
    if not verify_cmd:
        verify_cmd = (
            f"# Verify work in {active_dir}/"
            if active_dir
            else "# Run verification suite"
        )

    if is_auditor:
        scope_clause = "- **Auditor Attestation Mode**: You do not author code or specification files. Your responsibility is running tests, auditing compliance, and stamping audit attestations."
        tool_sequence = f"""1. Run `bin/get_work` to synchronize with main and inspect pending dirty units requiring audit.
   - **Always Run `bin/get_work` First (Even for Out-of-Band Work)**: Even if you are specifically instructed to audit a unit out-of-band, **always run `bin/get_work` first**. In this zero-sync architecture, `bin/get_work` pulls the latest files from the canonical main workspace so you do not audit stale code.
   - **Early Exit**: If `bin/get_work` reports that all units are clean (or exits with code 0 and no dirty units) and you have not been given an explicit out-of-band task, **IMMEDIATELY STOP**. Report to the user that all units in scope are clean and terminate your turn. Do NOT run further commands, query test suites, or inspect unrelated files.
2. Select the target unit (either the first ready unit from `bin/get_work` or the specific unit requested out-of-band). Follow the companion guide (`{guide_rel}`) to perform verification and auditing.
3. Execute verification suite:
   `{verify_cmd}`
4. If checks pass 100%, submit verification audit attestation:
   `bin/submit <target_file>`
5. If defects or verification failures are discovered, attribute blame or report failure per `{guide_rel}`:
   `bin/blame <culprit-file> "<actionable critique>"`
   - If defects span multiple roles (e.g. both library implementation and test suite), blame each culprit file directly within the turn.
   (or run `bin/fail <target_file> "<reason>"` if verification failed)
6. Loop over remaining ready units:
   - After submitting or blaming the current unit, repeat steps 1–5 for each remaining ready unit returned by `bin/get_work`.
   - Re-run `bin/get_work` after each submission to inspect newly ready or remaining units.
   - Continue until `bin/get_work` reports that all units in scope are clean (or no ready units remain), then report your completed work and terminate your turn."""
    else:
        scope_clause = f"- **Strict Scope**: You are ONLY permitted to create or modify files inside `{active_dir}/`. Never attempt to edit read-only upstream contracts or configurations."
        tool_sequence = f"""1. Run `bin/get_work` to synchronize with main, inspect dirty units requiring work, and check unacted feedback.
   - **Always Run `bin/get_work` First (Even for Out-of-Band Work)**: Even if you are specifically instructed to work on a unit out-of-band, **always run `bin/get_work` first**. In this zero-sync architecture, `bin/get_work` pulls the latest upstream contracts and code from the canonical main workspace so you do not work against stale contracts.
   - **Early Exit**: If `bin/get_work` reports that all units are clean (or exits with code 0 and no dirty units) and you have not been given an explicit out-of-band task, **IMMEDIATELY STOP**. Report to the user that all units in scope are clean and terminate your turn. Do NOT run further commands, query test suites, or inspect unrelated files.
2. Select the target unit (either the first ready unit from `bin/get_work` or the specific unit requested out-of-band). Follow the companion guide (`{guide_rel}`) to review upstream contracts and inspect or author the target file (`{active_dir}/<name>.<ext>`).
3. Author or update the target file using file editing tools (`replace_file_content` or `write_to_file`).
4. Run local verification:
   `{verify_cmd}`
5. Submit your verified work:
   - If workspace files were modified: `bin/submit <target_file> "<concise change summary>"`
   - If no workspace files were modified: `bin/submit <target_file>`
   (or run `bin/blame <culprit-file> "<critique>"` if an upstream specification defect is discovered)
   (or run `bin/fail <target_file> "<reason>"` if unresolved test failure)
6. Loop over remaining ready units:
   - After submitting or resolving the current unit, repeat steps 1–5 for each remaining ready unit.
   - Re-run `bin/get_work` after each submission to inspect newly ready or remaining units.
   - Continue processing ready units until `bin/get_work` reports that all units in scope are clean (or no ready units remain), then report your completed work and terminate your turn."""

    content = f"""# Cleanroom Role: {persona} ({role_label})

## Mandatory Behavioral Constraints & Role Boundaries
- **Role Persona**: You are the {persona}.
- **Contract & Guidance**: You author and maintain files adhering strictly to the role guide (`{guide_rel}`).
{scope_clause}
- **In-Band Source Metadata**: State is stored directly in source file comment headers (`LAST_CLEANED`, `LAST_CHANGED`, `CHANGE:`, `FEEDBACK:`). There are no external task queue files.
- **No Version Control Commands**: This workspace is an isolated cleanroom that does not use `git`. Never execute `git status`, `git diff`, `git log`, etc.
- **Strict Confinement**: You are strictly confined to this directory scope. Never inspect outside paths.
- **Strict Permission Rule**: You are strictly forbidden from executing `chmod`, changing file permissions, or attempting to write to read-only (`chmod 444`) files.
- **Always Run `bin/get_work` First (Even for Out-of-Band Work)**: You MUST run `bin/get_work` at the start of every turn before taking any other action. Even if you receive explicit instructions to perform out-of-band work on a specific unit, running `bin/get_work` is mandatory because it synchronizes your workspace with the latest upstream contracts, code, and system files from the canonical main workspace. Without running `bin/get_work`, your workspace files will be stale.
- **Process All Ready Units**: When multiple ready units are reported by `bin/get_work`, work through, verify, and submit all ready units sequentially within your turn. Do not stop after completing only one unit unless blocked by an unresolvable prerequisite or explicit user instruction.
- **No Unsolicited Work Discovery**: `bin/get_work` is the sole source of truth for work items. If it reports no work, do not attempt to find work by running wildcard builds/tests (e.g., `bazel test //...`), inspecting tool scripts, or checking other roles/scopes.

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

    workspace_entries: List[str] = []
    for entry in (role_def.get("workspace_files") or []) + (
        role_def.get("tools") or []
    ):
        if entry and entry not in workspace_entries:
            workspace_entries.append(entry)

    is_build_enabled = any(
        w in ("BUILD.bazel", "MODULE.bazel", ".bazelversion")
        or w.endswith("BUILD.bazel")
        for w in workspace_entries
    ) or ("bazel test" in (role_def.get("verify_template") or ""))

    if is_build_enabled:
        for b_rel in ["bin/BUILD.bazel", "bin/pyright_library.bzl"]:
            if b_rel not in workspace_entries:
                workspace_entries.append(b_rel)

    for entry_rel in workspace_entries:
        entry_rel = entry_rel.rstrip("/")
        src = os.path.join(root, entry_rel)
        if not os.path.exists(src):
            src = os.path.join(_repo_root, entry_rel)
        if not os.path.exists(src):
            continue
        dst = os.path.join(workspace_dir, entry_rel)
        if os.path.isfile(src):
            is_exec = (
                os.access(src, os.X_OK)
                or entry_rel.startswith("bin/")
                or entry_rel.endswith(".sh")
            ) and not entry_rel.endswith((".bazel", ".bzl", ".json", ".txt"))
            copy_file_with_perms(src, dst, readonly=True, executable=is_exec)
        elif os.path.isdir(src):
            for t_root, t_dirs, t_files in os.walk(src):
                t_dirs[:] = [
                    d
                    for d in t_dirs
                    if d != "__pycache__"
                    and not d.startswith(".")
                    and not d.startswith("bazel-")
                ]
                for tf in t_files:
                    if tf.endswith((".pyc", ".pyo")):
                        continue
                    src_f = os.path.join(t_root, tf)
                    rel_f = os.path.relpath(src_f, src)
                    dst_f = os.path.join(dst, rel_f)
                    is_exec = (
                        os.access(src_f, os.X_OK)
                        or rel_f.startswith("bin/")
                        or rel_f.endswith(".sh")
                    ) and not rel_f.endswith((".bazel", ".bzl", ".json", ".txt"))
                    copy_file_with_perms(
                        src_f, dst_f, readonly=True, executable=is_exec
                    )

    for entry in role_def.get("node_deps") or []:
        dep_src_rel = resolve_node_dep_src(
            entry, root, default_pkg=role_def.get("pkg", "update_python_with_ai")
        )
        if dep_src_rel:
            src = os.path.join(root, dep_src_rel)
            if not os.path.exists(src):
                src = os.path.join(_repo_root, dep_src_rel)
            if os.path.isfile(src):
                dst = os.path.join(workspace_dir, dep_src_rel)
                copy_file_with_perms(src, dst, readonly=True)

    # Ensure cleanroom_workspace_tool is present in support/lib
    cwt_src = os.path.join(
        root, "update_with_ai/support/lib/cleanroom_workspace_tool.py"
    )
    if not os.path.exists(cwt_src):
        cwt_src = os.path.join(
            _repo_root, "update_with_ai/support/lib/cleanroom_workspace_tool.py"
        )
    if os.path.isfile(cwt_src):
        copy_file_with_perms(
            cwt_src,
            os.path.join(
                workspace_dir, "update_with_ai/support/lib/cleanroom_workspace_tool.py"
            ),
            readonly=True,
        )

    # Ensure cleanroom_role_tool is present in support/lib
    crt_src = os.path.join(root, "update_with_ai/support/lib/cleanroom_role_tool.py")
    if not os.path.exists(crt_src):
        crt_src = os.path.join(
            _repo_root, "update_with_ai/support/lib/cleanroom_role_tool.py"
        )
    if os.path.isfile(crt_src):
        copy_file_with_perms(
            crt_src,
            os.path.join(
                workspace_dir, "update_with_ai/support/lib/cleanroom_role_tool.py"
            ),
            readonly=True,
        )

    # Copy src_metadata to support/lib
    sm_src = os.path.join(root, "update_with_ai/support/lib/src_metadata.py")
    if not os.path.exists(sm_src):
        sm_src = os.path.join(_repo_root, "update_with_ai/support/lib/src_metadata.py")
    if os.path.isfile(sm_src):
        copy_file_with_perms(
            sm_src,
            os.path.join(workspace_dir, "update_with_ai/support/lib/src_metadata.py"),
            readonly=True,
        )
        copy_file_with_perms(
            sm_src,
            os.path.join(
                workspace_dir, "update_python_with_ai/support/lib/src_metadata.py"
            ),
            readonly=True,
        )

    # Copy role guide (read-only)
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
            copy_file_with_perms(
                g_src, os.path.join(workspace_dir, guide_rel), readonly=True
            )

    active_pattern = role_def.get("src_pattern", "")
    active_dir, active_prefix, active_suffix = parse_pattern_info(active_pattern)

    dep_targets: List[str] = []
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
    is_auditor = is_auditor_role(role_name)
    fb_deps_raw = role_def.get("feedback_role_deps", [])
    fb_deps = {f.split(":")[-1] for f in fb_deps_raw}

    dep_infos: List[Tuple[str, str, str, str, bool, bool]] = []
    for d_target in dep_targets:
        d_name = d_target.split(":")[-1]
        if d_name == role_name:
            continue
        d_def = resolve_role_definition(d_target, root)
        d_pattern = d_def.get("src_pattern", "")
        if not d_pattern:
            continue
        d_dir, d_prefix, d_suffix = parse_pattern_info(d_pattern)
        is_stub = d_name in stub_deps
        is_fb_audited = is_auditor and d_name in fb_deps
        dep_infos.append((d_name, d_dir, d_prefix, d_suffix, is_stub, is_fb_audited))

    part_map = get_part_module_map(repo_root=root, parts_bases=parts_bases)

    for base in parts_bases:
        for init_rel in [f"{base}/__init__.py", f"{base}/parts/__init__.py"]:
            s_init = os.path.join(root, init_rel)
            d_init = os.path.join(workspace_dir, init_rel)
            if os.path.exists(s_init):
                copy_file_with_perms(s_init, d_init, readonly=True)
            elif is_build_enabled:
                write_file_with_perms(d_init, "", readonly=True)

        parts_dir = (
            os.path.join(root, base, "parts")
            if not base.endswith("parts")
            else os.path.join(root, base)
        )
        if not os.path.exists(parts_dir):
            continue

        for part_name in os.listdir(parts_dir):
            part_path = os.path.join(parts_dir, part_name)
            if not os.path.isdir(part_path) or part_name.startswith("."):
                continue

            part_b_src = os.path.join(part_path, "BUILD.bazel")
            if is_build_enabled and os.path.exists(part_b_src):
                copy_file_with_perms(
                    part_b_src,
                    os.path.join(
                        workspace_dir, base, "parts", part_name, "BUILD.bazel"
                    ),
                    readonly=True,
                )

            init_file = os.path.join(part_path, "__init__.py")
            if os.path.exists(init_file):
                copy_file_with_perms(
                    init_file,
                    os.path.join(
                        workspace_dir, base, "parts", part_name, "__init__.py"
                    ),
                    readonly=True,
                )

            if active_dir and is_build_enabled:
                active_src_dir = os.path.join(part_path, active_dir)
                b_file = os.path.join(active_src_dir, "BUILD.bazel")
                if os.path.exists(b_file):
                    copy_file_with_perms(
                        b_file,
                        os.path.join(
                            workspace_dir,
                            base,
                            "parts",
                            part_name,
                            active_dir,
                            "BUILD.bazel",
                        ),
                        readonly=True,
                    )

            for d_name, d_dir, d_prefix, d_suffix, is_stub, is_fb_audited in dep_infos:
                dep_src_dir = os.path.join(part_path, d_dir)
                ws_dep_dir = os.path.join(
                    workspace_dir, base, "parts", part_name, d_dir
                )

                if is_stub:
                    os.makedirs(ws_dep_dir, exist_ok=True)
                    if is_build_enabled:
                        ws_dep_build = os.path.join(ws_dep_dir, "BUILD.bazel")
                        dep_build = os.path.join(dep_src_dir, "BUILD.bazel")
                        if os.path.exists(dep_build):
                            copy_file_with_perms(dep_build, ws_dep_build, readonly=True)

                    units = (
                        parse_part_units(part_b_src)
                        if os.path.exists(part_b_src)
                        else {}
                    )
                    for stem in units:
                        if stem.endswith("_ext"):
                            continue
                        d_f = os.path.join(ws_dep_dir, f"{stem}.py")
                        pyi_path = find_spec_pyi(part_path, stem, repo_root=root)
                        if pyi_path and os.path.exists(pyi_path):
                            try:
                                generate_readonly_test_stub(
                                    pyi_path,
                                    stem,
                                    d_f,
                                    dep_dir=d_dir,
                                    part_map=part_map,
                                )
                            except Exception as e:
                                print(
                                    f"Warning: could not generate stub for {stem}: {e}"
                                )
                                stub_lines = [
                                    "from __future__ import annotations",
                                    f"# Requirements specified in {stem}.pyi",
                                    "# CLEANROOM TEST STUB: Implementation details omitted. Refer strictly to companion .pyi file.",
                                    "",
                                    f"raise NotImplementedError('Cleanroom Test Stub: {stem}')\n",
                                ]
                                write_file_with_perms(
                                    d_f, "\n".join(stub_lines), readonly=True
                                )
                        else:
                            stub_lines = [
                                "from __future__ import annotations",
                                f"# Requirements specified in {stem}.pyi",
                                "# CLEANROOM TEST STUB: Implementation details omitted. Refer strictly to companion .pyi file.",
                                "",
                                f"raise NotImplementedError('Cleanroom Test Stub: {stem}')\n",
                            ]
                            write_file_with_perms(
                                d_f, "\n".join(stub_lines), readonly=True
                            )
                else:
                    if not os.path.exists(dep_src_dir):
                        continue

                    if is_build_enabled and is_fb_audited:
                        os.makedirs(ws_dep_dir, exist_ok=True)
                        ws_dep_build = os.path.join(ws_dep_dir, "BUILD.bazel")
                        dep_build = os.path.join(dep_src_dir, "BUILD.bazel")
                        if os.path.exists(dep_build):
                            copy_file_with_perms(dep_build, ws_dep_build, readonly=True)

                    for f in os.listdir(dep_src_dir):
                        if (
                            f.startswith(".")
                            or f == "BUILD.bazel"
                            or f == "__init__.py"
                        ):
                            continue
                        if d_dir == active_dir:
                            continue
                        if f.startswith(d_prefix) and f.endswith(d_suffix):
                            s_f = os.path.join(dep_src_dir, f)
                            d_f = os.path.join(ws_dep_dir, f)
                            copy_file_with_perms(s_f, d_f, readonly=True)

        prune_out_of_scope_files(workspace_dir, base, role_def, repo_root=root)

    deploy_workspace_bin_tools(workspace_dir)
    write_role_agents_md(workspace_dir, role_def, repo_root=root)


def deploy_workspace_bin_tools(workspace_dir: str) -> None:
    """Deploys role-local helper executables (bin/get_work, bin/submit, bin/blame, bin/fail) as opaque zipapps."""
    bin_dir = os.path.join(workspace_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)

    tools = {
        "get_work": "get_work",
        "submit": "submit",
        "blame": "blame",
        "fail": "fail",
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
    cfg = os.path.join(ws_dir, ".cleanroom_role.json")
    if os.path.isfile(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                meta = json.load(f)
                main_root = meta.get("main_workspace_root") or meta.get("repo_root")
        except Exception as e:
            sys.stderr.write(f"Warning: Failed parsing role config '{{cfg}}': {{e}}\\n")
        break
    ws_dir = os.path.dirname(ws_dir)

if not main_root and ws_dir:
    parent_dir = os.path.dirname(ws_dir)
    if os.path.basename(parent_dir) == "role_workspaces":
        projects_root = os.path.dirname(parent_dir)
        role_ws_name = os.path.basename(ws_dir)
        if os.path.isdir(projects_root):
            for entry in os.listdir(projects_root):
                cand = os.path.join(projects_root, entry)
                if os.path.isdir(cand) and entry != "role_workspaces" and role_ws_name.startswith(f"{{entry}}_"):
                    main_root = cand
                    break

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
        os.chmod(tool_path, 0o755)

    # Clean up non-tool files from bin_dir so agents cannot sniff on scripts,
    # but preserve Bazel package files (BUILD.bazel and pyright_library.bzl) required for builds.
    allowed_tools = set(tools.keys()) | {"BUILD.bazel", "pyright_library.bzl"}
    for entry in os.listdir(bin_dir):
        if entry not in allowed_tools:
            p = os.path.join(bin_dir, entry)
            try:
                if os.path.isfile(p) or os.path.islink(p):
                    os.chmod(p, 0o644)
                    os.unlink(p)
                elif os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
            except OSError as e:
                sys.stderr.write(
                    f"Warning: Failed cleaning non-tool file '{p}': {e}\n"
                )


def refresh_system_files(
    workspace_dir: str,
    repo_root: str,
    role_def: Dict[str, Any],
    dir_scope: str = "staging",
) -> None:
    """Recopies all non-parts files (tools, guides, configs, support libs) from main into the role workspace."""
    root = repo_root
    parts_bases = [dir_scope]

    # 1. Recopy read-only files, configs, guides, and stubs
    copy_readonly_files_and_stubs(workspace_dir, root, role_def, parts_bases)

    # 2. Re-deploy opaque bin tools
    deploy_workspace_bin_tools(workspace_dir)

    # 3. Refresh AGENTS.md
    write_role_agents_md(workspace_dir, role_def, repo_root=root)

    # 4. Re-record baseline hashes for the refreshed system files
    record_baseline_hashes(workspace_dir)
    print(
        f"Refreshed system files, opaque bin tools, and AGENTS.md in: {workspace_dir}"
    )


def record_baseline_hashes(workspace_dir: str) -> None:
    """No-op: Baseline hashes are retired. Cleans up legacy hash file if present."""
    hash_file = os.path.join(workspace_dir, ".cleanroom_readonly_hashes.json")
    if os.path.isfile(hash_file):
        try:
            os.unlink(hash_file)
        except OSError as e:
            sys.stderr.write(
                f"Warning: Could not remove legacy hash file '{hash_file}': {e}\n"
            )


def verify_integrity(workspace_dir: str) -> None:
    """No-op: Tamper checks are retired. Read-only contracts are protected by OS permissions and unidirectional sync."""
    pass


def compute_role_phase_order(repo_root: Optional[str] = None) -> Dict[str, int]:
    """Dynamically computes phase ordering ranks for all defined roles."""
    root = repo_root or _repo_root
    roles = load_defined_roles(root)
    unique_roles: Dict[str, Dict[str, Any]] = {}
    for r in roles.values():
        if isinstance(r, dict) and "name" in r:
            unique_roles[r["name"]] = r

    if not unique_roles:
        return {}

    deps_map: Dict[str, Set[str]] = {name: set() for name in unique_roles}
    for name, rdef in unique_roles.items():
        candidates: List[str] = []
        candidates.extend(rdef.get("role_deps", []))
        candidates.extend(rdef.get("star_role_deps", []))
        candidates.extend(rdef.get("feedback_role_deps", []))
        candidates.extend(rdef.get("silent_role_deps", []))

        stub_deps = {s.split(":")[-1] for s in rdef.get("stub_role_deps", [])}

        for dep_label in candidates:
            dep_name = dep_label.split(":")[-1]
            if dep_name == name or dep_name in stub_deps:
                continue
            if dep_name in unique_roles:
                deps_map[name].add(dep_name)

    ranks: Dict[str, int] = {}
    visited: Set[str] = set()

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
    """Filters dirty nodes to those that are ready to clean according to Cleanroom phase ordering."""
    phase_order = compute_role_phase_order(repo_root=repo_root)
    by_unit: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for node in dirty_nodes:
        key = (node.get("pkg", ""), node.get("unit_name", ""))
        by_unit.setdefault(key, []).append(node)

    ready_nodes: List[Dict[str, Any]] = []
    for (pkg, unit_name), u_nodes in by_unit.items():
        min_phase = min(phase_order.get(n["role"], 99) for n in u_nodes)
        for n in u_nodes:
            if phase_order.get(n["role"], 99) == min_phase:
                ready_nodes.append(n)

    return ready_nodes


def topological_sort_units(
    units_list: List[Dict[str, Any]],
    module_deps: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """Topologically sorts unit dicts such that prerequisites appear before dependents."""
    unit_map = {item["unit_name"]: item for item in units_list}
    visited: Set[str] = set()
    temp_mark: Set[str] = set()
    order: List[Dict[str, Any]] = []

    def visit(uname: str) -> None:
        if uname in visited:
            return
        if uname in temp_mark:
            return
        temp_mark.add(uname)
        for dep in sorted(module_deps.get(uname, [])):
            if dep in unit_map:
                visit(dep)
        temp_mark.remove(uname)
        visited.add(uname)
        order.append(unit_map[uname])

    for item in sorted(units_list, key=lambda x: x["unit_name"]):
        if item["unit_name"] not in visited:
            visit(item["unit_name"])

    return order


def get_role_upstream_chain(role_name: str, roles_def: Dict[str, Any]) -> List[str]:
    """Returns transitive upstream role names that role_name depends on."""
    visited: Set[str] = set()
    order: List[str] = []

    def dfs(r: str) -> None:
        r_def = roles_def.get(r, {})
        dep_labels = (
            r_def.get("role_deps", [])
            + r_def.get("star_role_deps", [])
            + r_def.get("feedback_role_deps", [])
        )
        for d in dep_labels:
            d_name = d.split(":")[-1]
            if d_name != r and d_name in roles_def and d_name not in visited:
                visited.add(d_name)
                dfs(d_name)
                order.append(d_name)

    dfs(role_name)
    return order


def compute_role_work_queue(
    role_name: str,
    dir_scope: str,
    main_repo_root: str,
    allow_intra_role_deps: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Computes ready and blocked dirty nodes for a role from the repository build graph."""
    part_dirs = find_part_dirs_in_scope(main_repo_root, dir_scope)
    all_units: Dict[str, str] = {}
    module_deps: Dict[str, List[str]] = {}
    raw_module_deps: Dict[str, List[str]] = {}

    for pd in part_dirs:
        bf = os.path.join(main_repo_root, pd, "BUILD.bazel")
        u_map = parse_part_units(bf) if os.path.isfile(bf) else {}
        for uname, mdeps in u_map.items():
            all_units[uname] = pd
            raw_module_deps[uname] = list(mdeps)
            module_deps[uname] = [d.split(":")[-1] for d in mdeps]

    all_dirty = find_all_dirty_in_scope(main_repo_root, dir_scope=dir_scope)
    dirty_lookup: Dict[Tuple[str, str], Dict[str, Any]] = {
        (item["unit_name"], item["role"]): item for item in all_dirty
    }

    roles_def = load_defined_roles(main_repo_root)
    clean_role = normalize_role_arg(role_name) or role_name
    active_role_def = roles_def.get(clean_role, {})
    upstream_roles = get_role_upstream_chain(clean_role, roles_def)
    is_auditor = is_auditor_role(clean_role)
    feedback_roles = [
        d.split(":")[-1] for d in active_role_def.get("feedback_role_deps", [])
    ]

    dirty_in_role = [item for item in all_dirty if item["role"] == clean_role]
    if not dirty_in_role:
        return [], []

    def get_transitive_deps(u: str) -> Set[str]:
        visited: Set[str] = set()
        queue = list(module_deps.get(u, []))
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                queue.extend(module_deps.get(curr, []))
        return visited

    ready_candidates: List[Dict[str, Any]] = []
    blocked_candidates: List[Dict[str, Any]] = []

    for item in dirty_in_role:
        uname = item["unit_name"]
        part_dir = item.get("part_dir", "") or all_units.get(uname, "")
        blocked_reasons: List[str] = []

        # Check 1: Intra-unit upstream roles
        for up_r in upstream_roles:
            up_r_def = roles_def.get(up_r, {})
            up_r_pat = up_r_def.get("src_pattern", "")
            if up_r_pat and part_dir:
                up_dir, _, _ = parse_pattern_info(up_r_pat)
                # If this part does not have the upstream role's directory, it's not defined for this part
                if not os.path.isdir(os.path.join(main_repo_root, part_dir, up_dir)):
                    continue
            if (uname, up_r) in dirty_lookup:
                blocked_reasons.append(
                    f"Upstream role '{up_r}' is dirty for unit '{uname}'"
                )

        # Check 2: Auditor feedback dependencies
        if is_auditor:
            for fb_r in feedback_roles:
                if (uname, fb_r) in dirty_lookup:
                    blocked_reasons.append(
                        f"Feedback target '{fb_r}' is dirty or has unacted feedback for unit '{uname}'"
                    )

        # Check 3: Inter-unit module dependencies
        transitive_deps = get_transitive_deps(uname)
        roles_to_check = (
            upstream_roles if allow_intra_role_deps else (upstream_roles + [clean_role])
        )
        for dep_u in sorted(transitive_deps):
            dep_part = all_units.get(dep_u, part_dir)
            for r_check in roles_to_check:
                r_check_def = roles_def.get(r_check, {})
                r_check_pat = r_check_def.get("src_pattern", "")
                if r_check_pat and dep_part:
                    r_dir, _, _ = parse_pattern_info(r_check_pat)
                    if not os.path.isdir(os.path.join(main_repo_root, dep_part, r_dir)):
                        continue
                if (dep_u, r_check) in dirty_lookup:
                    blocked_reasons.append(
                        f"Prerequisite unit '{dep_u}' is dirty in role '{r_check}'"
                    )

        raw_deps = raw_module_deps.get(uname, [])
        dep_files: List[str] = []
        for dep in raw_deps:
            if dep.startswith("//"):
                dep_label = dep.lstrip("/")
                parts = dep_label.split(":")
                dep_pkg = parts[0]
                dep_u = parts[1] if len(parts) > 1 else os.path.basename(dep_pkg)
            else:
                dep_u = dep.lstrip(":")
                dep_pkg = all_units.get(dep_u, part_dir)

            if dir_scope == "staging" and dep_pkg.startswith("update_with_ai/"):
                dep_pkg = f"staging/{dep_pkg[len('update_with_ai/'):]}"
            elif dir_scope == "update_with_ai" and dep_pkg.startswith("staging/"):
                dep_pkg = f"update_with_ai/{dep_pkg[len('staging/'):]}"

            if clean_role == "high" and os.path.isfile(
                os.path.join(main_repo_root, dep_pkg, "high", f"{dep_u}.md")
            ):
                dep_file = os.path.join(dep_pkg, "high", f"{dep_u}.md")
            elif clean_role == "planning" and os.path.isfile(
                os.path.join(main_repo_root, dep_pkg, "planning", f"{dep_u}.md")
            ):
                dep_file = os.path.join(dep_pkg, "planning", f"{dep_u}.md")
            else:
                dep_file = os.path.join(dep_pkg, "low", f"{dep_u}.pyi")

            if dep_file not in dep_files:
                dep_files.append(dep_file)

        item["dependencies"] = dep_files

        if blocked_reasons:
            item["blocked_reasons"] = blocked_reasons
            blocked_candidates.append(item)
        else:
            ready_candidates.append(item)

    sorted_ready = topological_sort_units(ready_candidates, module_deps)
    return sorted_ready, blocked_candidates


# ==============================================================================
# In-Band Dynamic Dirty Evaluation
# ==============================================================================


def find_part_dirs_in_scope(repo_root: str, dir_scope: str) -> List[str]:
    """Finds all component part directories containing BUILD.bazel or role subdirectories within dir_scope."""
    scope_full = os.path.join(repo_root, dir_scope)
    if not os.path.exists(scope_full):
        return []

    meta = load_role_metadata(repo_root)
    main_root = meta.get("main_workspace_root") if meta else None

    # Case 1: dir_scope is itself a part directory with units
    build_file = os.path.join(scope_full, "BUILD.bazel")
    if os.path.isfile(build_file) and parse_part_units(build_file):
        return [dir_scope]
    if main_root:
        m_bf = os.path.join(main_root, dir_scope, "BUILD.bazel")
        if os.path.isfile(m_bf) and parse_part_units(m_bf):
            return [dir_scope]

    part_dirs: List[str] = []
    # Case 2: dir_scope contains a parts/ subdirectory
    parts_sub = os.path.join(scope_full, "parts")
    if os.path.isdir(parts_sub):
        for entry in sorted(os.listdir(parts_sub)):
            cand = os.path.join(parts_sub, entry)
            if os.path.isdir(cand) and not entry.startswith("."):
                bf = os.path.join(cand, "BUILD.bazel")
                if os.path.isfile(bf) and parse_part_units(bf):
                    part_dirs.append(os.path.relpath(cand, repo_root))
                elif main_root and os.path.isfile(
                    os.path.join(main_root, dir_scope, "parts", entry, "BUILD.bazel")
                ):
                    m_bf = os.path.join(
                        main_root, dir_scope, "parts", entry, "BUILD.bazel"
                    )
                    if parse_part_units(m_bf):
                        part_dirs.append(os.path.relpath(cand, repo_root))
                else:
                    has_role_sub = any(
                        os.path.isdir(os.path.join(cand, sub))
                        and not sub.startswith(".")
                        for sub in os.listdir(cand)
                    )
                    if has_role_sub:
                        part_dirs.append(os.path.relpath(cand, repo_root))
        if part_dirs:
            return part_dirs

    # Case 3: scan recursively for any subfolder with units
    for r, dirs, files in os.walk(scope_full):
        dirs[:] = [
            d for d in dirs if not d.startswith(".") and not d.startswith("bazel-")
        ]
        if "BUILD.bazel" in files:
            bf = os.path.join(r, "BUILD.bazel")
            if parse_part_units(bf):
                part_dirs.append(os.path.relpath(r, repo_root))

    return sorted(part_dirs)


def eval_unit_dirty(
    repo_root: str,
    part_dir: str,
    unit_name: str,
    role_name: str,
    role_def: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluates whether a specific unit is dirty for a given role via in-band headers."""
    active_types = role_def.get("active_component_types")
    allowed_types = set(active_types) if active_types else None

    if allowed_types is not None and classify_unit_type(unit_name) not in allowed_types:
        return {"is_dirty": False, "reasons": []}

    reasons: List[str] = []

    # --- AUDITOR ROLE EVALUATION ---
    if is_auditor_role(role_name):
        audit_tag = AUDITOR_ROLE_TAGS.get(role_name, f"{role_name.upper()}_AUDIT")
        fb_deps = role_def.get("feedback_role_deps", [])
        if not fb_deps:
            return {"is_dirty": False, "reasons": []}

        # Primary audited target is the first feedback dependency (e.g. :lib for qa/coverage, :grounding for grounding_qa)
        primary_fb = fb_deps[0]
        fb_def = resolve_role_definition(primary_fb, repo_root)
        fb_pat = fb_def.get("src_pattern", "")
        if not fb_pat:
            return {"is_dirty": False, "reasons": []}

        primary_rel = fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
        primary_full = os.path.join(repo_root, primary_rel)

        if not os.path.isfile(primary_full):
            reasons.append(f"Audited target {primary_rel} does not exist")
            return {"is_dirty": True, "reasons": reasons}

        primary_meta = src_metadata.extract_metadata(primary_full)
        if primary_meta is None or not primary_meta.last_changed:
            reasons.append(
                f"Target {primary_rel} missing valid in-band metadata header"
            )
            return {"is_dirty": True, "reasons": reasons}

        audit_ts = primary_meta.audits.get(audit_tag)
        if not audit_ts:
            reasons.append(
                f"Target {primary_rel} has not been certified with {audit_tag}"
            )
        elif audit_ts < primary_meta.last_changed:
            reasons.append(
                f"Target {primary_rel} modified ({primary_meta.last_changed}) after {audit_tag} ({audit_ts})"
            )

        # Evaluate companion verification dependencies (e.g. :test for qa/coverage)
        for comp_label in fb_deps[1:]:
            comp_def = resolve_role_definition(comp_label, repo_root)
            comp_pat = comp_def.get("src_pattern", "")
            if not comp_pat:
                continue
            comp_rel = comp_pat.format(unit_dir=part_dir, unit_name=unit_name)
            comp_full = os.path.join(repo_root, comp_rel)

            if not os.path.isfile(comp_full):
                reasons.append(f"Companion test {comp_rel} does not exist")
                continue

            comp_meta = src_metadata.extract_metadata(comp_full)
            if comp_meta is None or not comp_meta.last_changed:
                reasons.append(
                    f"Companion test {comp_rel} missing valid in-band metadata header"
                )
                continue

            comp_audit_ts = comp_meta.audits.get(audit_tag)
            if audit_ts and not comp_audit_ts:
                reasons.append(
                    f"Companion test {comp_rel} has not been certified with {audit_tag}"
                )
            elif (
                audit_ts
                and comp_meta.last_changed
                and audit_ts < comp_meta.last_changed
            ):
                reasons.append(
                    f"Companion test {comp_rel} modified ({comp_meta.last_changed}) after {audit_tag} ({audit_ts})"
                )

        # Check governing upstream contracts
        contract_roles = [
            r for r in role_def.get("star_role_deps", []) if r not in fb_deps
        ]
        for c_label in contract_roles:
            c_def = resolve_role_definition(c_label, repo_root)
            c_pat = c_def.get("src_pattern", "")
            if not c_pat:
                continue
            c_rel = c_pat.format(unit_dir=part_dir, unit_name=unit_name)
            c_full = os.path.join(repo_root, c_rel)
            if os.path.isfile(c_full):
                c_meta = src_metadata.extract_metadata(c_full)
                if c_meta and c_meta.last_changed:
                    if audit_ts and audit_ts < c_meta.last_changed:
                        reasons.append(
                            f"Contract {c_rel} modified ({c_meta.last_changed}) after {audit_tag} ({audit_ts})"
                        )

        return {"is_dirty": bool(reasons), "reasons": reasons}

    # --- PRODUCER ROLE EVALUATION ---
    src_pat = role_def.get("src_pattern", "")
    if not src_pat:
        return {"is_dirty": False, "reasons": []}

    src_rel = src_pat.format(unit_dir=part_dir, unit_name=unit_name)
    src_full = os.path.join(repo_root, src_rel)

    if not os.path.isfile(src_full):
        return {"is_dirty": True, "reasons": [f"Source file {src_rel} does not exist"]}

    meta = src_metadata.extract_metadata(src_full)
    if meta is None or not meta.last_cleaned:
        return {
            "is_dirty": True,
            "reasons": [f"Header missing LAST_CLEANED in {src_rel}"],
        }

    if meta.dirty:
        reasons.append(f"Target explicitly marked DIRTY: {meta.dirty}")

    if meta.feedback:
        for fb in meta.feedback:
            reasons.append(f"Unacted feedback in {src_rel}: {fb}")

    # Forward dependency timestamp comparison
    dep_role_labels: List[str] = []
    for k in ["role_deps", "star_role_deps"]:
        for d in role_def.get(k, []):
            if d not in dep_role_labels:
                dep_role_labels.append(d)

    for d_label in dep_role_labels:
        d_name = d_label.split(":")[-1]
        if d_name == role_name:
            continue
        d_def = resolve_role_definition(d_label, repo_root)
        d_pat = d_def.get("src_pattern", "")
        if not d_pat:
            continue
        d_rel = d_pat.format(unit_dir=part_dir, unit_name=unit_name)
        d_full = os.path.join(repo_root, d_rel)
        if os.path.isfile(d_full):
            d_meta = src_metadata.extract_metadata(d_full)
            if (
                d_meta
                and d_meta.last_changed
                and meta.last_cleaned < d_meta.last_changed
            ):
                reasons.append(
                    f"Upstream contract {d_rel} modified ({d_meta.last_changed}) after local LAST_CLEANED ({meta.last_cleaned})"
                )

    return {"is_dirty": bool(reasons), "reasons": reasons}


def find_all_dirty_in_scope(
    repo_root: Optional[str] = None,
    dir_scope: str = "staging",
    role_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Evaluates all units in dir_scope across roles and returns dirty records."""
    root = os.path.abspath(repo_root or _repo_root)
    part_dirs = find_part_dirs_in_scope(root, dir_scope)
    roles_dict = load_defined_roles(root)

    unique_roles: Dict[str, Dict[str, Any]] = {}
    for r in roles_dict.values():
        if isinstance(r, dict) and "name" in r:
            unique_roles[r["name"]] = r

    target_roles: Dict[str, Dict[str, Any]] = {}
    if role_filter:
        clean_rf = normalize_role_arg(role_filter)
        if clean_rf in unique_roles:
            target_roles[clean_rf] = unique_roles[clean_rf]
    else:
        phase_order = compute_role_phase_order(root)
        for r_name in sorted(
            unique_roles.keys(), key=lambda r: (phase_order.get(r, 99), r)
        ):
            target_roles[r_name] = unique_roles[r_name]

    dirty_units: List[Dict[str, Any]] = []

    for part_dir in part_dirs:
        build_file = os.path.join(root, part_dir, "BUILD.bazel")
        units = parse_part_units(build_file) if os.path.isfile(build_file) else {}
        if not units:
            meta = load_role_metadata(root)
            main_root = meta.get("main_workspace_root") if meta else None
            if main_root:
                m_bf = os.path.join(main_root, part_dir, "BUILD.bazel")
                if os.path.isfile(m_bf):
                    units = parse_part_units(m_bf)
        if not units:
            full_part = os.path.join(root, part_dir)
            if os.path.isdir(full_part):
                discovered_stems: Set[str] = set()
                for sub in os.listdir(full_part):
                    sub_path = os.path.join(full_part, sub)
                    if os.path.isdir(sub_path) and not sub.startswith("."):
                        for sf in os.listdir(sub_path):
                            if sf.startswith("."):
                                continue
                            if sf.endswith(".py"):
                                discovered_stems.add(sf[:-3])
                            elif sf.endswith(".pyi"):
                                discovered_stems.add(sf[:-4])
                            elif sf.endswith(".md"):
                                discovered_stems.add(sf[:-3])
                units = {
                    stem: [] for stem in sorted(discovered_stems) if stem != "__init__"
                }
        for unit_name in sorted(units.keys()):
            for r_name, r_def in target_roles.items():
                eval_res = eval_unit_dirty(root, part_dir, unit_name, r_name, r_def)
                if eval_res["is_dirty"]:
                    src_pat = r_def.get("src_pattern", "")
                    if src_pat:
                        target_file = src_pat.format(
                            unit_dir=part_dir, unit_name=unit_name
                        )
                    else:
                        fb_deps = r_def.get("feedback_role_deps", [])
                        if fb_deps:
                            fb_def = resolve_role_definition(fb_deps[0], root)
                            fb_pat = fb_def.get("src_pattern", "")
                            target_file = (
                                fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
                                if fb_pat
                                else f"{part_dir}/{r_name}/{unit_name}"
                            )
                        else:
                            target_file = f"{part_dir}/{r_name}/{unit_name}"
                    dirty_units.append(
                        {
                            "part_dir": part_dir,
                            "unit_name": unit_name,
                            "role": r_name,
                            "target_file": target_file,
                            "reasons": eval_res["reasons"],
                        }
                    )

    return dirty_units


# ==============================================================================
# Commissioning & Decommissioning Lifecycle
# ==============================================================================


def commission_workspace(
    role: str,
    dir_scope: str = "staging",
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> str:
    """Commissions a directory-scoped role workspace: ../role_workspaces/<ws>_<role>_<sanitized_dir>."""
    root = os.path.abspath(repo_root or _repo_root)
    clean_role = normalize_role_arg(role) or role
    role_def = resolve_role_definition(clean_role, root)
    role_name = role_def["name"]
    role_label = role_def.get("label", f"//update_python_with_ai:{role_name}")

    workspace_dir = os.path.abspath(
        dest or get_default_role_dir(role_name, dir_scope=dir_scope, repo_root=root)
    )
    os.makedirs(workspace_dir, exist_ok=True)
    parts_bases = [dir_scope]

    print(
        f"Commissioning role workspace for '{role_label}' ({role_name}) scoped to '{dir_scope}' at: {workspace_dir}"
    )

    # Prepare role artifacts (stubs/templates)
    prepare_role_artifacts(role_def, root, parts_bases)

    # Copy read-only files, tools, guides, build files, stubs
    copy_readonly_files_and_stubs(workspace_dir, root, role_def, parts_bases)

    # Copy initial active files (read-write) from canonical repo
    active_rw_files = find_read_write_files(root, role_def, parts_bases)
    for rel_path in active_rw_files:
        src_f = os.path.join(root, rel_path)
        dst_f = os.path.join(workspace_dir, rel_path)
        if not os.path.exists(dst_f):
            copy_file_with_perms(src_f, dst_f, readonly=False)

    record_baseline_hashes(workspace_dir)
    save_role_metadata(
        workspace_dir,
        role_label,
        role_name,
        parts_dirs=parts_bases,
        dir_scope=dir_scope,
        repo_root=root,
    )
    record_commissioned_workspace(role_name, dir_scope, workspace_dir, repo_root=root)

    print(f"Workspace commissioned: {workspace_dir}")
    return workspace_dir


def decommission_workspace(
    role: str,
    dir_scope: str = "staging",
    dest: Optional[str] = None,
    force: bool = False,
    repo_root: Optional[str] = None,
) -> bool:
    """Decommissions and safely removes a role workspace if clean or forced."""
    root = os.path.abspath(repo_root or _repo_root)
    clean_role = normalize_role_arg(role) or role
    workspace_dir = os.path.abspath(
        dest or get_default_role_dir(clean_role, dir_scope=dir_scope, repo_root=root)
    )

    if not os.path.exists(workspace_dir):
        print(f"Workspace does not exist: {workspace_dir}")
        unrecord_commissioned_workspace(clean_role, dir_scope, repo_root=root)
        return True

    # Check for unharvested blame buffer
    buffer_path = os.path.join(workspace_dir, BLAME_BUFFER_FILE)
    has_buffer = os.path.isfile(buffer_path) and os.path.getsize(buffer_path) > 0

    # Check for uncommitted modified files
    role_def = resolve_role_definition(clean_role, root)
    modified_files = find_modified_read_write_files(
        workspace_dir, root, role_def, parts_bases=[dir_scope]
    )

    if (has_buffer or modified_files) and not force:
        print(f"Refusing to decommission dirty workspace: {workspace_dir}")
        if has_buffer:
            print("  - Unharvested blame entries in .cleanroom_blame_buffer.json")
        if modified_files:
            print(f"  - {len(modified_files)} uncommitted/un-synced modified files:")
            for mf in modified_files[:5]:
                print(f"      • {mf}")
        print(
            "Run 'bin/cleanroom refresh' first or pass '--force' to discard uncommitted work."
        )
        return False

    # Restore write permissions so cleanup succeeds
    for r, dirs, files in os.walk(workspace_dir):
        for d in dirs:
            try:
                os.chmod(os.path.join(r, d), 0o755)
            except OSError as e:
                sys.stderr.write(
                    f"Warning: Failed to restore write permissions for dir '{os.path.join(r, d)}': {e}\n"
                )
        for f in files:
            try:
                os.chmod(os.path.join(r, f), 0o644)
            except OSError as e:
                sys.stderr.write(
                    f"Warning: Failed to restore write permissions for file '{os.path.join(r, f)}': {e}\n"
                )

    shutil.rmtree(workspace_dir, ignore_errors=True)
    unrecord_commissioned_workspace(clean_role, dir_scope, repo_root=root)
    print(f"Successfully decommissioned role workspace: {workspace_dir}")
    return True


def setup_workspace(
    role: str,
    dest: Optional[str] = None,
    repo_root: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
) -> str:
    """Backward-compatible wrapper delegating to commission_workspace."""
    bases = normalize_parts_dirs(repo_root=repo_root, parts_dirs=parts_dirs)
    primary_scope = bases[0] if bases else "staging"
    return commission_workspace(
        role=role, dir_scope=primary_scope, dest=dest, repo_root=repo_root
    )


# ==============================================================================
# Omni-Directional Cascading Sync
# ==============================================================================


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
        ws_parts = (
            os.path.join(workspace_dir, base, "parts")
            if not base.endswith("parts")
            else os.path.join(workspace_dir, base)
        )
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
                    except OSError as e:
                        sys.stderr.write(
                            f"Warning: Failed to stat '{src_file}': {e}\n"
                        )
                        continue
                    rel_path = os.path.relpath(src_file, workspace_dir)
                    dst_file = os.path.join(repo_root, rel_path)
                    if not os.path.exists(dst_file):
                        modified.append(rel_path)
                    else:
                        if compute_file_hash(src_file) != compute_file_hash(dst_file):
                            modified.append(rel_path)

    return modified


def find_scoped_source_files(
    base_dir: str,
    dir_scope: str,
    role_def: Optional[Dict[str, Any]] = None,
    repo_root: Optional[str] = None,
) -> Set[str]:
    """Efficiently discovers source and spec files strictly within dir_scope.

    When role_def is supplied, restricts discovery strictly to:
      1. Active role files and active role BUILD.bazel
      2. stub_role_deps files and stub_role_deps BUILD.bazel
      3. role_deps and star_role_deps files (without BUILD.bazel)
    """
    target_dir = os.path.join(base_dir, dir_scope)
    if not os.path.isdir(target_dir):
        return set()

    if not role_def:
        found: Set[str] = set()
        for root_dir, dirs, files in os.walk(target_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("__pycache__", "bazel-bin", "bazel-out", "bazel-testlogs")
            ]
            for f in files:
                if f.startswith(".") or f.endswith(".pyc"):
                    continue
                if f.endswith((".py", ".pyi", ".md")) or f == "BUILD.bazel":
                    full_p = os.path.join(root_dir, f)
                    found.add(os.path.relpath(full_p, base_dir))
        return found

    root = repo_root or _repo_root
    role_name = role_def.get("name", "")
    active_pattern = role_def.get("src_pattern", "")
    active_dir, active_pfx, active_sfx = parse_pattern_info(active_pattern)

    dep_targets: List[str] = []
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
    is_auditor = is_auditor_role(role_name)
    fb_deps_raw = role_def.get("feedback_role_deps", [])
    fb_deps = {f.split(":")[-1] for f in fb_deps_raw}

    dep_infos: List[Tuple[str, str, str, str, bool, bool]] = []
    for d_target in dep_targets:
        d_name = d_target.split(":")[-1]
        if d_name == role_name:
            continue
        d_def = resolve_role_definition(d_target, root)
        d_pattern = d_def.get("src_pattern", "")
        if not d_pattern:
            continue
        d_dir, d_prefix, d_suffix = parse_pattern_info(d_pattern)
        is_stub = d_name in stub_deps
        is_fb_audited = is_auditor and d_name in fb_deps
        dep_infos.append((d_name, d_dir, d_prefix, d_suffix, is_stub, is_fb_audited))

    parts_root = (
        os.path.join(target_dir, "parts")
        if not dir_scope.endswith("parts")
        else target_dir
    )
    if not os.path.isdir(parts_root):
        return set()

    found_files: Set[str] = set()

    for part_name in sorted(os.listdir(parts_root)):
        part_dir = os.path.join(parts_root, part_name)
        if not os.path.isdir(part_dir) or part_name.startswith("."):
            continue

        # 1. Active directory: source files, BUILD.bazel, __init__.py
        if active_dir:
            act_path = os.path.join(part_dir, active_dir)
            if os.path.isdir(act_path):
                for f in os.listdir(act_path):
                    if f.startswith(".") or f.endswith((".pyc", ".pyo")):
                        continue
                    if f == "BUILD.bazel":
                        found_files.add(
                            os.path.relpath(os.path.join(act_path, f), base_dir)
                        )
                    elif f == "__init__.py":
                        found_files.add(
                            os.path.relpath(os.path.join(act_path, f), base_dir)
                        )
                    elif f.startswith(active_pfx) and f.endswith(active_sfx):
                        found_files.add(
                            os.path.relpath(os.path.join(act_path, f), base_dir)
                        )

        # 2. Dependency directories:
        #    stub_role_deps gets source files/stubs AND BUILD.bazel
        #    feedback_role_deps for auditor roles gets source files AND BUILD.bazel
        #    role_deps / star_role_deps gets source files ONLY (no BUILD.bazel)
        for d_name, d_dir, d_prefix, d_suffix, is_stub, is_fb_audited in dep_infos:
            dep_path = os.path.join(part_dir, d_dir)
            if os.path.isdir(dep_path):
                for f in os.listdir(dep_path):
                    if f.startswith(".") or f.endswith((".pyc", ".pyo")):
                        continue
                    if f == "BUILD.bazel":
                        if is_stub or is_fb_audited:
                            found_files.add(
                                os.path.relpath(os.path.join(dep_path, f), base_dir)
                            )
                    elif f == "__init__.py":
                        found_files.add(
                            os.path.relpath(os.path.join(dep_path, f), base_dir)
                        )
                    elif f.startswith(d_prefix) and f.endswith(d_suffix):
                        found_files.add(
                            os.path.relpath(os.path.join(dep_path, f), base_dir)
                        )

        init_file = os.path.join(part_dir, "__init__.py")
        if os.path.isfile(init_file):
            found_files.add(os.path.relpath(init_file, base_dir))

    return found_files


def prune_out_of_scope_files(
    workspace_dir: str,
    dir_scope: str,
    role_def: Dict[str, Any],
    repo_root: Optional[str] = None,
) -> List[str]:
    """Removes out-of-scope files and directories from role workspace dir_scope."""
    allowed = find_scoped_source_files(
        workspace_dir, dir_scope, role_def=role_def, repo_root=repo_root
    )
    allowed.add(f"{dir_scope}/__init__.py")
    allowed.add(f"{dir_scope}/parts/__init__.py")

    target_dir = os.path.join(workspace_dir, dir_scope)
    if not os.path.isdir(target_dir):
        return []

    pruned: List[str] = []
    for root_dir, dirs, files in os.walk(target_dir, topdown=False):
        for f in files:
            full_p = os.path.join(root_dir, f)
            rel_p = os.path.relpath(full_p, workspace_dir)
            if rel_p not in allowed:
                try:
                    os.chmod(full_p, 0o644)
                except OSError as e:
                    sys.stderr.write(
                        f"Warning: Failed to chmod untracked file '{full_p}': {e}\n"
                    )
                try:
                    os.remove(full_p)
                    pruned.append(rel_p)
                except OSError as e:
                    sys.stderr.write(
                        f"Warning: Failed to remove untracked file '{full_p}': {e}\n"
                    )
        if root_dir != target_dir:
            try:
                os.rmdir(root_dir)
            except OSError as e:
                if getattr(e, "errno", None) not in (errno.ENOTEMPTY, errno.EEXIST):
                    sys.stderr.write(
                        f"Warning: Failed removing directory '{root_dir}': {e}\n"
                    )
    return pruned


def converge_role_workspace(
    workspace_dir: str,
    repo_root: str,
    role: str,
    parts_dirs: Optional[Sequence[str]] = None,
    sync_all: bool = False,
    phase: str = "both",
) -> List[Dict[str, Any]]:
    """Executes high-efficiency synchronization between role workspace and main.

    Args:
        workspace_dir: Path to role workspace.
        repo_root: Root of main workspace.
        role: Role name or address.
        parts_dirs: Scoped directories.
        sync_all: Whether to sync all files.
        phase: 'harvest' (inbound only: buffers, edits, local dirty tags to main),
               'cascade' (outbound only: main specs, stubs, feedback, dirty tags to ws),
               or 'both' (default, two-way convergence).
    """
    root = repo_root
    clean_role = normalize_role_arg(role) or role
    role_def = resolve_role_definition(clean_role, root)
    role_name = role_def["name"]
    meta = load_role_metadata(workspace_dir) or {}
    dir_scope = meta.get("parts_dir") or (parts_dirs[0] if parts_dirs else "staging")
    last_sync = meta.get("last_sync_timestamp", "")

    verify_integrity(workspace_dir)
    synced_events: List[Dict[str, Any]] = []

    is_harvest = phase in ("harvest", "both")
    is_cascade = phase in ("cascade", "both")

    # Determine which files in dir_scope are role-writable vs read-only
    active_pattern = role_def.get("src_pattern", "")
    active_dir, active_pfx, active_sfx = parse_pattern_info(active_pattern)

    def _is_role_writable(rel_p: str) -> bool:
        if not active_dir:
            return False
        fname = os.path.basename(rel_p)
        parent = os.path.basename(os.path.dirname(rel_p))
        return (
            parent == active_dir
            and fname.startswith(active_pfx)
            and fname.endswith(active_sfx)
            and fname != "BUILD.bazel"
        )

    # =========================================================================
    # PHASE 1: INBOUND HARVEST (Role Workspace -> Main)
    # =========================================================================
    if is_harvest:
        # 1. Harvest .cleanroom_blame_buffer.json into canonical contracts in main
        blame_buffer_path = os.path.join(workspace_dir, BLAME_BUFFER_FILE)
        if os.path.isfile(blame_buffer_path):
            try:
                with open(blame_buffer_path, "r", encoding="utf-8") as bf:
                    buffer_entries = json.load(bf)
                if isinstance(buffer_entries, list) and buffer_entries:
                    for b_item in buffer_entries:
                        b_target = b_item.get("target", "").lstrip("/")
                        b_sender = b_item.get("blamed_by", f"{role_name} workspace")
                        b_explanation = b_item.get("explanation", "")
                        dirty_reason = (
                            b_item.get("dirty_reason")
                            or f"Blamed by {b_sender}: {b_explanation}"
                        )
                        target_canonical = os.path.join(root, b_target)
                        if not os.path.isfile(target_canonical):
                            alt = os.path.join(root, dir_scope, b_target)
                            if os.path.isfile(alt):
                                target_canonical = alt
                        if os.path.isfile(target_canonical):
                            src_metadata.mark_dirty(
                                target_canonical, reason=dirty_reason
                            )
                            src_metadata.append_feedback(
                                target_canonical, b_explanation, sender=b_sender
                            )
                            print(
                                f"HARVESTED FEEDBACK [{role_name}]: Appended blame to {b_target}"
                            )
                            synced_events.append(
                                {
                                    "type": "BLAME",
                                    "target": b_target,
                                    "explanation": b_explanation,
                                }
                            )
                write_file_with_perms(blame_buffer_path, "[]\n", readonly=False)
            except Exception as e:
                print(
                    f"Warning: could not process blame buffer {blame_buffer_path}: {e}"
                )

        # 1b. Harvest .cleanroom_audit_buffer.json into canonical contracts in main
        audit_buffer_path = os.path.join(workspace_dir, AUDIT_BUFFER_FILE)
        if os.path.isfile(audit_buffer_path):
            try:
                with open(audit_buffer_path, "r", encoding="utf-8") as abf:
                    audit_entries = json.load(abf)
                if isinstance(audit_entries, list) and audit_entries:
                    for a_item in audit_entries:
                        a_target = a_item.get("target", "").lstrip("/")
                        a_tag = a_item.get("audit_tag", "")
                        a_ts = (
                            a_item.get("timestamp")
                            or src_metadata.current_utc_timestamp()
                        )
                        target_canonical = os.path.join(root, a_target)
                        if not os.path.isfile(target_canonical):
                            alt = os.path.join(root, dir_scope, a_target)
                            if os.path.isfile(alt):
                                target_canonical = alt
                        if os.path.isfile(target_canonical):
                            meta_f = src_metadata.extract_metadata(target_canonical)
                            curr_audits = dict(meta_f.audits) if meta_f else {}
                            curr_audits[a_tag] = a_ts
                            src_metadata.update_metadata(
                                target_canonical, audits=curr_audits, last_cleaned=a_ts
                            )
                            print(
                                f"HARVESTED AUDIT [{role_name}]: {a_tag} on {a_target}"
                            )
                            synced_events.append(
                                {"type": "AUDIT", "target": a_target, "dest": "main"}
                            )
                write_file_with_perms(audit_buffer_path, "[]\n", readonly=False)
            except Exception as e:
                print(
                    f"Warning: could not process audit buffer {audit_buffer_path}: {e}"
                )

        # 2. Harvest role-writable source files and local audits into main
        ws_files = find_scoped_source_files(
            workspace_dir, dir_scope, role_def=role_def, repo_root=root
        )
        main_files = find_scoped_source_files(
            root, dir_scope, role_def=role_def, repo_root=root
        )
        all_rel_files = sorted(ws_files | main_files)

        for rel_path in all_rel_files:
            if is_stub_dep_file(rel_path, role_def, repo_root=root):
                continue
            ws_f = os.path.join(workspace_dir, rel_path)
            main_f = os.path.join(root, rel_path)
            role_writable = _is_role_writable(rel_path)

            ws_exists = os.path.isfile(ws_f)
            main_exists = os.path.isfile(main_f)

            if ws_exists and not main_exists:
                if role_writable:
                    copy_file_with_perms(ws_f, main_f, readonly=False)
                    print(f"COLLECTED NEW [{role_name}]: {rel_path} -> main")
                    synced_events.append(
                        {"type": "NEW_FILE", "target": rel_path, "dest": "main"}
                    )
                continue

            if not (ws_exists and main_exists):
                continue

            ws_meta = src_metadata.extract_metadata(ws_f)
            main_meta = src_metadata.extract_metadata(main_f)

            ws_cleaned = (ws_meta.last_cleaned if ws_meta else None) or ""
            main_cleaned = (main_meta.last_cleaned if main_meta else None) or ""
            ws_ts = (ws_meta.last_changed if ws_meta else None) or ""
            main_ts = (main_meta.last_changed if main_meta else None) or ""
            ws_dirty = ws_meta.dirty if ws_meta else None
            main_dirty = main_meta.dirty if main_meta else None
            ws_audits = dict(ws_meta.audits) if ws_meta else {}
            main_audits = dict(main_meta.audits) if main_meta else {}

            # Conflict check if both were modified after last sync with differing timestamps
            if last_sync and ws_ts and main_ts:
                if ws_ts > last_sync and main_ts > last_sync and ws_ts != main_ts:
                    print(
                        f"CONFLICT DETECTED: Both {rel_path} in role workspace and canonical main were modified after last sync ({last_sync}). Skipping!"
                    )
                    continue

            ws_event = max(ws_ts, ws_cleaned)
            main_event = max(main_ts, main_cleaned)

            if role_writable:
                if ws_event > main_event:
                    copy_file_with_perms(ws_f, main_f, readonly=False)
                    print(
                        f"COLLECTED [{role_name}]: {rel_path} -> main (Role: {ws_event} > Main: {main_event})"
                    )
                    synced_events.append(
                        {
                            "type": "SUBMIT",
                            "target": rel_path,
                            "change": ws_meta.change_summary if ws_meta else "",
                        }
                    )
                elif ws_event == main_event:
                    if main_dirty and not ws_dirty:
                        # Workspace was cleaned (DIRTY cleared in workspace): collect into main
                        copy_file_with_perms(ws_f, main_f, readonly=False)
                        print(
                            f"COLLECTED [{role_name}]: {rel_path} -> main (DIRTY tag cleared in workspace)"
                        )
                        synced_events.append(
                            {
                                "type": "SUBMIT",
                                "target": rel_path,
                                "change": ws_meta.change_summary if ws_meta else "",
                            }
                        )
                    elif ws_dirty and not main_dirty:
                        copy_file_with_perms(ws_f, main_f, readonly=False)
                        print(
                            f"DIRTIED [main]: {rel_path} -> main (Propagated DIRTY tag from workspace)"
                        )
                        synced_events.append(
                            {"type": "DIRTIED", "target": rel_path, "dest": "main"}
                        )
                    elif (
                        not ws_cleaned
                        and main_cleaned
                        and (not last_sync or main_cleaned <= last_sync)
                    ):
                        src_metadata.delete_last_cleaned(main_f)
                        print(
                            f"DIRTIED [main]: Cleared LAST_CLEANED in {rel_path} (propagated from {role_name} workspace)"
                        )
                        synced_events.append(
                            {"type": "DIRTIED", "target": rel_path, "dest": "main"}
                        )
                    elif ws_meta is None or main_meta is None:
                        ws_stat = os.stat(ws_f)
                        main_stat = os.stat(main_f)
                        if ws_stat.st_mtime > main_stat.st_mtime:
                            copy_file_with_perms(ws_f, main_f, readonly=False)

            # Harvest direct auditor certifications
            role_audit_tag = (
                f"{role_name.upper()}_AUDIT" if is_auditor_role(role_name) else None
            )
            if role_audit_tag:
                t_ws = ws_audits.get(role_audit_tag, "")
                t_main = main_audits.get(role_audit_tag, "")
                if t_ws and t_ws > last_sync and t_ws > t_main:
                    main_audits[role_audit_tag] = t_ws
                    src_metadata.update_metadata(main_f, audits=main_audits)
                    print(
                        f"AUDIT HARVESTED [{role_name}]: {rel_path} (Tagged: {role_audit_tag})"
                    )
                    synced_events.append(
                        {"type": "AUDIT", "target": rel_path, "dest": "main"}
                    )

    if not is_cascade:
        return synced_events

    # =========================================================================
    # PHASE 2: OUTBOUND CASCADE (Main -> Role Workspace)
    # =========================================================================
    # Reconstitute any missing active files in main from templates/specs first
    prepare_role_artifacts(role_def, root, [dir_scope])

    ws_files = find_scoped_source_files(
        workspace_dir, dir_scope, role_def=role_def, repo_root=root
    )
    main_files = find_scoped_source_files(
        root, dir_scope, role_def=role_def, repo_root=root
    )
    all_rel_files = sorted(ws_files | main_files)

    part_map = get_part_module_map(repo_root=root, parts_bases=[dir_scope])

    for rel_path in all_rel_files:
        ws_f = os.path.join(workspace_dir, rel_path)
        main_f = os.path.join(root, rel_path)
        role_writable = _is_role_writable(rel_path)

        if is_stub_dep_file(rel_path, role_def, repo_root=root):
            if sync_stub_dep_file(
                rel_path, workspace_dir, root, role_def, part_map=part_map
            ):
                synced_events.append(
                    {"type": "STUB_SYNC", "target": rel_path, "dest": "workspace"}
                )
            continue

        ws_exists = os.path.isfile(ws_f)
        main_exists = os.path.isfile(main_f)

        if main_exists and not ws_exists:
            copy_file_with_perms(main_f, ws_f, readonly=not role_writable)
            print(f"PUSHED NEW [{role_name}]: {rel_path} -> workspace")
            synced_events.append(
                {"type": "NEW_FILE", "target": rel_path, "dest": "workspace"}
            )
            continue

        if not (ws_exists and main_exists):
            continue

        ws_meta = src_metadata.extract_metadata(ws_f)
        main_meta = src_metadata.extract_metadata(main_f)

        ws_cleaned = (ws_meta.last_cleaned if ws_meta else None) or ""
        main_cleaned = (main_meta.last_cleaned if main_meta else None) or ""
        ws_ts = (ws_meta.last_changed if ws_meta else None) or ""
        main_ts = (main_meta.last_changed if main_meta else None) or ""
        ws_dirty = ws_meta.dirty if ws_meta else None
        main_dirty = main_meta.dirty if main_meta else None
        ws_audits = dict(ws_meta.audits) if ws_meta else {}
        main_audits = dict(main_meta.audits) if main_meta else {}
        ws_feedback = list(ws_meta.feedback) if ws_meta else []
        main_feedback = list(main_meta.feedback) if main_meta else []
        ws_code_hash = ws_meta.code_hash if ws_meta else None
        main_code_hash = main_meta.code_hash if main_meta else None

        # Short-circuit: identical timestamps, dirty flags, audits, feedback, and code_hash
        if ws_meta and main_meta:
            if (
                ws_ts == main_ts
                and ws_cleaned == main_cleaned
                and ws_dirty == main_dirty
                and ws_audits == main_audits
                and ws_feedback == main_feedback
                and ws_code_hash == main_code_hash
            ):
                continue

        ws_event = max(ws_ts, ws_cleaned)
        main_event = max(main_ts, main_cleaned)

        if role_writable:
            if main_event > ws_event:
                copy_file_with_perms(main_f, ws_f, readonly=False)
                print(
                    f"PUSHED [{role_name}]: {rel_path} -> workspace (Main: {main_event} > Role: {ws_event})"
                )
                synced_events.append(
                    {
                        "type": "CASCADE",
                        "target": rel_path,
                        "change": main_meta.change_summary if main_meta else "",
                    }
                )
            elif ws_event == main_event:
                if (main_dirty and not ws_dirty) or (main_feedback != ws_feedback):
                    copy_file_with_perms(main_f, ws_f, readonly=False)
                    print(
                        f"PUSHED [{role_name}]: {rel_path} -> workspace (Dirty/Feedback update from main)"
                    )
                    synced_events.append(
                        {
                            "type": "CASCADE",
                            "target": rel_path,
                            "change": "Dirty/Feedback update",
                        }
                    )
                elif not main_dirty and ws_dirty:
                    copy_file_with_perms(main_f, ws_f, readonly=False)
                    print(
                        f"PUSHED [{role_name}]: {rel_path} -> workspace (Cleaned in main)"
                    )
                    synced_events.append(
                        {
                            "type": "CASCADE",
                            "target": rel_path,
                            "change": "Cleaned in main",
                        }
                    )
                elif (
                    main_meta
                    and ws_meta
                    and main_meta.code_hash
                    and main_meta.code_hash != ws_meta.code_hash
                ):
                    copy_file_with_perms(main_f, ws_f, readonly=False)
                    print(
                        f"PUSHED [{role_name}]: {rel_path} -> workspace (Updated CODE_HASH: {rel_path})"
                    )
                    synced_events.append(
                        {
                            "type": "CASCADE",
                            "target": rel_path,
                            "change": "Updated CODE_HASH",
                        }
                    )
                elif ws_meta is None or main_meta is None:
                    main_stat = os.stat(main_f)
                    ws_stat = os.stat(ws_f)
                    if main_stat.st_mtime > ws_stat.st_mtime:
                        copy_file_with_perms(main_f, ws_f, readonly=False)
        else:
            # Read-only files in role workspace: Main is always authoritative
            if main_event > ws_event or (
                main_meta
                and ws_meta
                and (
                    main_dirty != ws_dirty
                    or main_audits != ws_audits
                    or main_feedback != ws_feedback
                    or main_meta.code_hash != ws_meta.code_hash
                )
            ):
                copy_file_with_perms(main_f, ws_f, readonly=True)
                print(
                    f"PUSHED [{role_name}]: {rel_path} -> workspace (Main: {main_event} >= Role: {ws_event})"
                )
                synced_events.append(
                    {
                        "type": "CASCADE",
                        "target": rel_path,
                        "change": main_meta.change_summary if main_meta else "",
                    }
                )
            elif ws_meta is None and main_meta is None:
                try:
                    if compute_file_hash(main_f) != compute_file_hash(ws_f):
                        copy_file_with_perms(main_f, ws_f, readonly=True)
                        print(
                            f"PUSHED [{role_name}]: {rel_path} -> workspace (Updated {os.path.basename(rel_path)})"
                        )
                        synced_events.append(
                            {
                                "type": "CASCADE",
                                "target": rel_path,
                                "change": f"Updated {os.path.basename(rel_path)}",
                            }
                        )
                except Exception as e:
                    sys.stderr.write(
                        f"Warning: Failed pushing non-metadata file '{rel_path}' to workspace: {e}\n"
                    )

        # Propagate lack of LAST_CLEANED when timestamps match
        if ws_ts == main_ts:
            if (
                not main_cleaned
                and ws_cleaned
                and (not last_sync or ws_cleaned <= last_sync)
            ):
                is_ro = not role_writable
                if is_ro:
                    os.chmod(ws_f, 0o644)
                src_metadata.delete_last_cleaned(ws_f)
                if is_ro:
                    os.chmod(ws_f, 0o444)
                print(
                    f"DIRTIED [{role_name}]: Cleared LAST_CLEANED in {rel_path} (propagated from main)"
                )
                synced_events.append(
                    {"type": "DIRTIED", "target": rel_path, "dest": "workspace"}
                )

        # AUDIT Timestamps Synchronization
        role_audit_tag = (
            f"{role_name.upper()}_AUDIT" if is_auditor_role(role_name) else None
        )

        if role_audit_tag:
            t_ws = ws_audits.get(role_audit_tag, "")
            t_main = main_audits.get(role_audit_tag, "")
            if t_ws:
                if not t_main and t_ws <= last_sync:
                    del ws_audits[role_audit_tag]
                    is_ro = not role_writable
                    if is_ro:
                        os.chmod(ws_f, 0o644)
                    src_metadata.update_metadata(ws_f, audits=ws_audits)
                    if is_ro:
                        os.chmod(ws_f, 0o444)
                    print(
                        f"AUDIT CLEARED [{role_name}]: Removed {role_audit_tag} from {rel_path} (propagated from main)"
                    )
                    synced_events.append(
                        {
                            "type": "AUDIT_CLEARED",
                            "target": rel_path,
                            "dest": "workspace",
                        }
                    )
            else:
                if t_main:
                    ws_audits[role_audit_tag] = t_main
                    is_ro = not role_writable
                    if is_ro:
                        os.chmod(ws_f, 0o644)
                    src_metadata.update_metadata(ws_f, audits=ws_audits)
                    if is_ro:
                        os.chmod(ws_f, 0o444)
                    print(
                        f"AUDIT PUSHED [{role_name}]: {role_audit_tag} on {rel_path} -> workspace"
                    )
                    synced_events.append(
                        {"type": "AUDIT", "target": rel_path, "dest": "workspace"}
                    )

        updated_ws_audits = False
        for tag in list(ws_audits.keys()):
            if tag != role_audit_tag and tag not in main_audits:
                del ws_audits[tag]
                updated_ws_audits = True
        for tag, m_val in main_audits.items():
            if tag != role_audit_tag and ws_audits.get(tag) != m_val:
                ws_audits[tag] = m_val
                updated_ws_audits = True

        if updated_ws_audits:
            is_ro = not role_writable
            if is_ro:
                os.chmod(ws_f, 0o644)
            src_metadata.update_metadata(ws_f, audits=ws_audits)
            if is_ro:
                os.chmod(ws_f, 0o444)
            print(f"AUDIT SYNCHRONIZED [{role_name}]: {rel_path}")

    # 3. Outbound cascade stubs/guides if upstream contracts changed
    copy_readonly_files_and_stubs(workspace_dir, root, role_def, [dir_scope])
    write_role_agents_md(workspace_dir, role_def, repo_root=root)

    # 4. Update last_sync_timestamp and re-record baseline hashes
    now = src_metadata.current_utc_timestamp()
    save_role_metadata(
        workspace_dir,
        role_def.get("label", f"//update_python_with_ai:{role_name}"),
        role_name,
        parts_dirs=[dir_scope],
        dir_scope=dir_scope,
        last_sync_timestamp=now,
        repo_root=root,
    )
    record_baseline_hashes(workspace_dir)

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
    workspace_dir = os.path.abspath(
        dest or get_default_role_dir(role_def["name"], repo_root=root)
    )
    if not os.path.exists(workspace_dir):
        print(f"Workspace not found: {workspace_dir}")
        return []
    return converge_role_workspace(
        workspace_dir=workspace_dir,
        repo_root=root,
        role=clean_role,
        parts_dirs=parts_dirs,
        sync_all=sync_all,
        phase="both",
    )


def pull_workspace_from_main(
    workspace_dir: str,
    main_repo_root: str,
    role_name: str,
    dir_scope: str = "staging",
    silent: bool = True,
) -> List[Dict[str, Any]]:
    """Silently pulls updated files in dir_scope from main into workspace_dir (one-way push)."""
    if not os.path.isdir(main_repo_root):
        raise ValueError(
            f"main_repo_root does not exist or is not a directory: {main_repo_root}"
        )
    if not os.path.isdir(workspace_dir):
        raise ValueError(
            f"workspace_dir does not exist or is not a directory: {workspace_dir}"
        )
    clean_role = normalize_role_arg(role_name) or role_name
    role_def = resolve_role_definition(clean_role, main_repo_root)
    active_pattern = role_def.get("src_pattern", "")
    active_dir, active_pfx, active_sfx = parse_pattern_info(active_pattern)

    prepare_role_artifacts(role_def, main_repo_root, [dir_scope])

    def _is_role_writable(rel_p: str) -> bool:
        if is_auditor_role(clean_role):
            return False
        fname = os.path.basename(rel_p)
        parent = os.path.basename(os.path.dirname(rel_p))
        return (
            parent == active_dir
            and fname.startswith(active_pfx)
            and fname.endswith(active_sfx)
            and fname != "BUILD.bazel"
        )

    main_files = find_scoped_source_files(
        main_repo_root, dir_scope, role_def=role_def, repo_root=main_repo_root
    )
    ws_files = find_scoped_source_files(
        workspace_dir, dir_scope, role_def=role_def, repo_root=main_repo_root
    )
    all_rel = sorted(main_files | ws_files)
    synced: List[Dict[str, Any]] = []

    part_map = get_part_module_map(repo_root=main_repo_root, parts_bases=[dir_scope])

    for rel in all_rel:
        main_f = os.path.join(main_repo_root, rel)
        ws_f = os.path.join(workspace_dir, rel)
        if not os.path.isfile(main_f):
            if os.path.isfile(ws_f) or os.path.islink(ws_f):
                try:
                    os.chmod(ws_f, 0o644)
                except OSError as e:
                    sys.stderr.write(
                        f"Warning: Failed to chmod '{ws_f}' before removal: {e}\n"
                    )
                try:
                    os.remove(ws_f)
                    synced.append(
                        {"type": "DELETE", "target": rel, "dest": "workspace"}
                    )
                except OSError as e:
                    sys.stderr.write(
                        f"Warning: Failed to remove deleted file '{ws_f}' from role workspace: {e}\n"
                    )
            continue
        role_writable = _is_role_writable(rel)

        if is_stub_dep_file(rel, role_def, repo_root=main_repo_root):
            if sync_stub_dep_file(
                rel, workspace_dir, main_repo_root, role_def, part_map=part_map
            ):
                synced.append({"type": "STUB_SYNC", "target": rel, "dest": "workspace"})
            continue

        if not os.path.isfile(ws_f):
            copy_file_with_perms(main_f, ws_f, readonly=not role_writable)
            synced.append({"type": "NEW_FILE", "target": rel, "dest": "workspace"})
            continue

        main_meta = src_metadata.extract_metadata(main_f)
        ws_meta = src_metadata.extract_metadata(ws_f)
        main_ts = (main_meta.last_changed if main_meta else "") or ""
        main_cl = (main_meta.last_cleaned if main_meta else "") or ""
        ws_ts = (ws_meta.last_changed if ws_meta else "") or ""
        ws_cl = (ws_meta.last_cleaned if ws_meta else "") or ""
        main_ev = max(main_ts, main_cl)
        ws_ev = max(ws_ts, ws_cl)

        needs_pull = False
        if not main_ev or not ws_ev:
            try:
                if os.path.getmtime(main_f) > os.path.getmtime(ws_f):
                    needs_pull = True
            except OSError as e:
                sys.stderr.write(
                    f"Warning: Failed checking mtimes for '{rel}': {e}\n"
                )
        elif main_ev > ws_ev:
            needs_pull = True
        elif not role_writable and ws_meta and main_meta:
            if (
                main_meta.dirty != ws_meta.dirty
                or main_meta.audits != ws_meta.audits
                or main_meta.feedback != ws_meta.feedback
                or main_meta.code_hash != ws_meta.code_hash
            ):
                needs_pull = True

        if needs_pull:
            copy_file_with_perms(main_f, ws_f, readonly=not role_writable)
            synced.append({"type": "PULL", "target": rel, "dest": "workspace"})

    # Ensure role templates/skeletons are materialized in the role workspace if missing
    prepare_role_artifacts(role_def, workspace_dir, [dir_scope])

    # Update last_sync_timestamp
    save_role_metadata(
        workspace_dir,
        role_address=role_def.get("label", f"//update_python_with_ai:{clean_role}"),
        role_name=clean_role,
        dir_scope=dir_scope,
        last_sync_timestamp=src_metadata.current_utc_timestamp(),
    )
    return synced


def refresh_system_files_fast(
    workspace_dir: str,
    main_repo_root: str,
    role_name: str,
    dir_scope: str = "staging",
    silent: bool = True,
) -> None:
    """Performs fast mtime refresh of system files (configs, tools, guides, build rules) into workspace."""
    if not os.path.isdir(main_repo_root) or not os.path.isdir(workspace_dir):
        return

    clean_role = normalize_role_arg(role_name) or role_name
    role_def = resolve_role_definition(clean_role, main_repo_root)

    # 1. Package build files in scope
    part_dirs = find_part_dirs_in_scope(main_repo_root, dir_scope)
    for pd in part_dirs:
        for sub in ["", "lib", "tests", "low", "high", "planning", "grounding"]:
            bf_rel = (
                os.path.join(pd, sub, "BUILD.bazel")
                if sub
                else os.path.join(pd, "BUILD.bazel")
            )
            s_bf = os.path.join(main_repo_root, bf_rel)
            d_bf = os.path.join(workspace_dir, bf_rel)
            if os.path.isfile(s_bf):
                if not os.path.exists(d_bf) or os.path.getmtime(
                    s_bf
                ) > os.path.getmtime(d_bf):
                    copy_file_with_perms(s_bf, d_bf, readonly=True)

    # 2. Configs and rules
    for cfg in [
        "pyrightconfig.json",
        ".bazelrc",
        "MODULE.bazel",
        "WORKSPACE",
        "update_with_ai/support/lib/cleanroom_workspace_tool.py",
        "update_with_ai/support/lib/cleanroom_role_tool.py",
        "update_with_ai/support/lib/src_metadata.py",
        "update_python_with_ai/support/lib/src_metadata.py",
        "update_python_with_ai/BUILD.bazel",
    ]:
        s = os.path.join(main_repo_root, cfg)
        d = os.path.join(workspace_dir, cfg)
        if os.path.isfile(s):
            if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
                copy_file_with_perms(s, d, readonly=True)

    for wf in role_def.get("workspace_files") or []:
        s = os.path.join(main_repo_root, wf)
        d = os.path.join(workspace_dir, wf)
        if os.path.isfile(s):
            if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
                copy_file_with_perms(s, d, readonly=True)

    # 3. Role tools
    for tool_rel in role_def.get("tools", []):
        s = os.path.join(main_repo_root, tool_rel)
        d = os.path.join(workspace_dir, tool_rel)
        if os.path.isfile(s):
            if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
                copy_file_with_perms(s, d, readonly=True)

    # 4. Guide
    guide_target = role_def.get("guide", "")
    if guide_target:
        guide_rel = guide_target.split(":")[-1]
        for g_cand in [
            f"update_python_with_ai/guides/{guide_rel}.md",
            f"update_with_ai/guides/{guide_rel}.md",
        ]:
            s = os.path.join(main_repo_root, g_cand)
            d = os.path.join(workspace_dir, g_cand)
            if os.path.isfile(s):
                if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
                    copy_file_with_perms(s, d, readonly=True)

    # 5. Opaque bin tools
    deploy_workspace_bin_tools(workspace_dir)

    # 6. Refresh AGENTS.md
    write_role_agents_md(workspace_dir, role_def, repo_root=main_repo_root)


def cleanroom_sync(
    repo_root: Optional[str] = None,
    role: Optional[str] = None,
    parts_dirs: Optional[Sequence[str]] = None,
    sync_all: bool = False,
    dest: Optional[str] = None,
    sys_refresh: bool = False,
) -> int:
    """Cleanroom sync command: two-phase 'one and done' synchronization across all commissioned workspaces."""
    root = os.path.abspath(repo_root or _repo_root)

    if role:
        clean_role = normalize_role_arg(role) or role
        role_def = resolve_role_definition(clean_role, root)
        role_name = role_def["name"]
        primary_dir = parts_dirs[0] if parts_dirs else "staging"
        workspace_dir = os.path.abspath(
            dest
            or get_default_role_dir(role_name, dir_scope=primary_dir, repo_root=root)
        )
        if not os.path.exists(workspace_dir):
            commission_workspace(
                role=clean_role,
                dir_scope=primary_dir,
                dest=workspace_dir,
                repo_root=root,
            )
        if sys_refresh:
            refresh_system_files(workspace_dir, root, role_def, dir_scope=primary_dir)
        converge_role_workspace(
            workspace_dir=workspace_dir,
            repo_root=root,
            role=clean_role,
            parts_dirs=[primary_dir],
            phase="both",
        )
        return 0

    existing_workspaces = find_existing_role_workspaces(repo_root=root)
    if not existing_workspaces:
        print(
            "No commissioned role workspaces found. Commission one using: bin/cleanroom commission <ROLE> [DIR]"
        )
        return 0

    print(
        f"Found {len(existing_workspaces)} commissioned role workspace(s) for two-phase synchronization."
    )

    phase_order = compute_role_phase_order(root)

    def _phase_key(item: Tuple[str, Dict[str, Any]]) -> int:
        role_n = item[1].get("role_name", "")
        return phase_order.get(role_n, 99)

    sorted_workspaces = sorted(existing_workspaces, key=_phase_key)

    if sys_refresh:
        for ws_dir, meta in sorted_workspaces:
            r_name = meta.get("role_name", "")
            r_addr = meta.get("role_address") or r_name
            d_scope = meta.get("parts_dir", "staging")
            role_def = resolve_role_definition(r_addr, root)
            refresh_system_files(ws_dir, root, role_def, dir_scope=d_scope)

    # Phase 1: Inbound Harvest across ALL commissioned workspaces
    # Pulls blame buffers, audit buffers, submissions, and local dirty flags from all workspaces into main
    print(
        f"\n--- Phase 1: Inbound Harvest across {len(sorted_workspaces)} workspace(s) ---"
    )
    for ws_dir, meta in sorted_workspaces:
        r_name = meta.get("role_name", "")
        r_addr = meta.get("role_address") or r_name
        d_scope = meta.get("parts_dir", "staging")
        print(
            f">>> Harvesting from workspace: {ws_dir} (Role: {r_name}, Scope: {d_scope})"
        )
        converge_role_workspace(
            workspace_dir=ws_dir,
            repo_root=root,
            role=r_addr,
            parts_dirs=[d_scope],
            phase="harvest",
        )

    # Phase 2: Outbound Cascade from main out to ALL commissioned workspaces
    # Redistributes harvested feedback, dirty flags, updated specs, stubs, and audit tags to workspaces
    print(
        f"\n--- Phase 2: Outbound Cascade across {len(sorted_workspaces)} workspace(s) ---"
    )
    for ws_dir, meta in sorted_workspaces:
        r_name = meta.get("role_name", "")
        r_addr = meta.get("role_address") or r_name
        d_scope = meta.get("parts_dir", "staging")
        print(
            f">>> Cascading to workspace: {ws_dir} (Role: {r_name}, Scope: {d_scope})"
        )
        converge_role_workspace(
            workspace_dir=ws_dir,
            repo_root=root,
            role=r_addr,
            parts_dirs=[d_scope],
            phase="cascade",
        )

    return 0


# ==============================================================================
# Local Commands: dirty and blame helper
# ==============================================================================


def mark_node_dirty(
    part_dir: str,
    unit_name: str,
    role_name: str,
    repo_root: Optional[str] = None,
    reason: str = "manual dirty",
) -> bool:
    """Marks a node dirty in the repo.

    For producer roles: stamps DIRTY tag and advances LAST_CLEANED to now.
    For auditor roles: if feedback targets are clean, deletes the role audit tag and advances LAST_CLEANED.
                       if feedback targets are already dirty, does nothing (no-op).
    """
    root = os.path.abspath(repo_root or _repo_root)
    clean_role = normalize_role_arg(role_name) or role_name
    role_def = resolve_role_definition(clean_role, root)
    r_name = role_def["name"]

    if is_auditor_role(r_name):
        audit_tag = AUDITOR_ROLE_TAGS.get(r_name, f"{r_name.upper()}_AUDIT")
        fb_deps = role_def.get("feedback_role_deps", [])
        if not fb_deps:
            return False

        # Check if feedback targets are already dirty
        any_target_clean = False
        targets_to_dirty: List[str] = []

        for fb_label in fb_deps:
            fb_def = resolve_role_definition(fb_label, root)
            fb_pat = fb_def.get("src_pattern", "")
            if not fb_pat:
                continue
            fb_rel = fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
            fb_full = os.path.join(root, fb_rel)
            if os.path.isfile(fb_full):
                targets_to_dirty.append(fb_full)
                eval_res = eval_unit_dirty(
                    root, part_dir, unit_name, fb_def["name"], fb_def
                )
                if not eval_res["is_dirty"]:
                    any_target_clean = True

        if not any_target_clean:
            print(
                f"Auditor node {r_name} on {part_dir}/{unit_name} already dirty (feedback targets dirty). No-op."
            )
            return False

        # Targets are clean: delete the audit tag and advance LAST_CLEANED
        for fb_full in targets_to_dirty:
            meta = src_metadata.extract_metadata(fb_full)
            if meta and audit_tag in meta.audits:
                new_audits = {k: v for k, v in meta.audits.items() if k != audit_tag}
                now = src_metadata.current_utc_timestamp()
                src_metadata.update_metadata(
                    fb_full, audits=new_audits, last_cleaned=now
                )
                print(
                    f"Removed {audit_tag} from {os.path.relpath(fb_full, root)} and advanced LAST_CLEANED."
                )
        return True

    # Producer role
    src_pat = role_def.get("src_pattern", "")
    if not src_pat:
        return False
    src_rel = src_pat.format(unit_dir=part_dir, unit_name=unit_name)
    src_full = os.path.join(root, src_rel)
    if os.path.isfile(src_full):
        src_metadata.mark_dirty(src_full, reason=reason)
        print(f"Marked {src_rel} dirty: added DIRTY tag and advanced LAST_CLEANED.")
        return True
    return False


def run_dirty_command(
    dir_scope: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Evaluates and reports dirty status for local workspace or specified directory scope."""
    root = os.path.abspath(repo_root or _repo_root)

    # Check if invoked inside a role workspace
    meta = load_role_metadata(".") or load_role_metadata(os.getcwd())
    if meta and not dir_scope:
        role_name = meta.get("role_name", "")
        d_scope = meta.get("parts_dir", "staging")
        dirty_items = find_all_dirty_in_scope(
            root, dir_scope=d_scope, role_filter=role_name
        )

        print(
            f"\n=== Cleanroom Dirty Status [Workspace: {role_name} | Scope: {d_scope}] ==="
        )
        if not dirty_items:
            print(
                f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
            )
            return 0
        print(f"Found {len(dirty_items)} dirty target(s):")
        for item in dirty_items:
            print(f"\n  • [DIRTY] {item['target_file']}")
            for r in item["reasons"]:
                print(f"      - {r}")
        print(
            "\nACTIONABLE NEXT STEP: Edit target file and update in-band header, then submit via 'bin/submit' or inspect with 'bin/get_work'.\n"
        )
        return 1

    scope = dir_scope or "staging"
    dirty_items = find_all_dirty_in_scope(root, dir_scope=scope)

    print(f"\n=== Cleanroom Dirty Status [Scope: {scope}] ===")
    if not dirty_items:
        print(
            f"✔ CLEAN: All units in '{scope}' are completely clean across all roles.\n"
        )
        return 0

    ready_items = get_ready_dirty_nodes(dirty_items, repo_root=root)
    print(
        f"Found {len(dirty_items)} dirty unit(s) ({len(ready_items)} ready to clean):"
    )
    for item in ready_items:
        print(f"\n  • [READY - {item['role'].upper()}] {item['target_file']}")
        for r in item["reasons"]:
            print(f"      - {r}")
    print()
    return 1


def run_blame_command(
    file_path: str,
    blame_dep: str,
    critique: str,
    repo_root: Optional[str] = None,
) -> int:
    """Buffers blame critique into .cleanroom_blame_buffer.json or appends to writable contract."""
    root = os.path.abspath(repo_root or _repo_root)
    clean_dep = blame_dep.strip().lstrip("/")
    dep_path = (
        os.path.join(os.getcwd(), clean_dep)
        if not os.path.isabs(clean_dep)
        else clean_dep
    )
    if not os.path.exists(dep_path):
        dep_path = os.path.join(root, clean_dep)

    is_readonly = False
    if os.path.exists(dep_path):
        st = os.stat(dep_path)
        is_readonly = not bool(st.st_mode & stat.S_IWUSR)
    else:
        is_readonly = True

    meta = load_role_metadata(".") or load_role_metadata(os.getcwd())
    if is_readonly and meta:
        buffer_path = os.path.join(os.getcwd(), BLAME_BUFFER_FILE)
        entries: List[Dict[str, Any]] = []
        if os.path.isfile(buffer_path):
            try:
                with open(buffer_path, "r", encoding="utf-8") as bf:
                    entries = json.load(bf)
            except Exception as e:
                sys.stderr.write(
                    f"Warning: Failed loading blame buffer '{buffer_path}': {e}\n"
                )
                entries = []
        entries.append(
            {
                "target": clean_dep,
                "blamed_by": file_path,
                "explanation": critique,
                "dirty_reason": f"Blamed by {file_path}: {critique}",
                "timestamp": src_metadata.current_utc_timestamp(),
            }
        )
        write_file_with_perms(
            buffer_path, json.dumps(entries, indent=2) + "\n", readonly=False
        )
        print(
            f"Recorded blame on read-only contract {clean_dep} into {BLAME_BUFFER_FILE}."
        )
        return 0

    if os.path.exists(dep_path):
        src_metadata.append_feedback(dep_path, critique, sender=file_path)
        print(f"Appended FEEDBACK: into {dep_path}")
        return 0

    print(f"Error: Could not locate blame target '{blame_dep}'.")
    return 1


# ==============================================================================
# Main CLI Entrypoint
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]

    # Handle bin/cleanroom-dirty invocations directly
    if raw_args and raw_args[0] == "dirty":
        d_scope = raw_args[1] if len(raw_args) > 1 else None
        return run_dirty_command(dir_scope=d_scope)

    # Zero-argument invocation defaults to sync
    if not raw_args:
        return cleanroom_sync()

    parser = argparse.ArgumentParser(
        prog="cleanroom",
        description="Cleanroom Subagentless Workspace Synchronization & Lifecycle Tool",
        epilog="""\
Commands:
  commission ROLE DIR   Commission a new role workspace (e.g. //update_python_with_ai:test staging)
  decommission ROLE [DIR]
                        Decommission an active role workspace
  refresh-sys [ROLE] [DIR]
                        Refresh system files, tools, configs, and guides across role workspaces
  dirty [DIR]           Inspect dirty targets and ready tasks in scope
  sync                  Synchronize all commissioned role workspaces with main (legacy)
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--sys",
        action="store_true",
        help="Recopy non-parts files (tools, configs, guides) from main into all role workspaces before syncing",
    )

    subparsers = parser.add_subparsers(dest="subcommand", metavar="<command>")

    # commission ROLE DIR
    p_comm = subparsers.add_parser(
        "commission",
        help="Commission a role workspace (requires ROLE and DIR)",
        description="Commissions an isolated role workspace at ../role_workspaces/<ws>_<role>_<sanitized_dir>.",
    )
    p_comm.add_argument(
        "role",
        help="Role name or label (e.g. '//update_python_with_ai:test' or 'test')",
    )
    p_comm.add_argument(
        "dir",
        help="Target directory scope (e.g. 'staging' or 'update_with_ai/parts/agent')",
    )
    p_comm.add_argument("--dest", help="Custom destination directory (optional)")

    # decommission ROLE [DIR] [--force]
    p_decomm = subparsers.add_parser(
        "decommission",
        help="Decommission an active role workspace (requires ROLE, optional DIR)",
        description="Safely decommissions and removes a role workspace if clean or forced.",
    )
    p_decomm.add_argument("role", help="Role name, label, or workspace directory name")
    p_decomm.add_argument(
        "dir", nargs="?", default=None, help="Target directory scope (optional)"
    )
    p_decomm.add_argument(
        "--force", action="store_true", help="Force decommission even if dirty"
    )
    p_decomm.add_argument("--dest", help="Custom destination directory (optional)")

    # refresh-sys [ROLE] [DIR]
    p_ref = subparsers.add_parser(
        "refresh-sys",
        help="Refresh system files across role workspaces",
        description="Recopies non-parts files (tools, configs, guides, build rules) into role workspaces.",
    )
    p_ref.add_argument(
        "role", nargs="?", default=None, help="Optional role name to filter"
    )
    p_ref.add_argument(
        "dir", nargs="?", default=None, help="Optional directory scope to filter"
    )

    # dirty [DIR]
    p_dirty = subparsers.add_parser(
        "dirty",
        help="Inspect dirty targets and ready tasks in scope",
        description="Evaluates all units in directory scope and displays ready and blocked tasks.",
    )
    p_dirty.add_argument(
        "dir", nargs="?", default="staging", help="Target directory scope"
    )

    # sync (legacy)
    p_sync = subparsers.add_parser(
        "sync",
        help="Synchronize all commissioned role workspaces with main (legacy)",
    )
    p_sync.add_argument(
        "--sys",
        action="store_true",
        help="Recopy non-parts files from main into all role workspaces before syncing",
    )

    args = parser.parse_args(raw_args)
    sys_mode = bool(getattr(args, "sys", False))

    if args.subcommand == "commission":
        commission_workspace(args.role, dir_scope=args.dir, dest=args.dest)
        return 0
    elif args.subcommand == "decommission":
        root = os.path.abspath(_repo_root)
        dir_scope = args.dir or "staging"
        if not args.dir:
            for ws in load_registered_workspaces(root):
                if (
                    ws.get("role") == normalize_role_arg(args.role)
                    or ws.get("workspace_name") == args.role
                    or ws.get("workspace_dir") == args.role
                    or os.path.basename(ws.get("workspace_dir", "")) == args.role
                ):
                    dir_scope = ws.get("dir") or ws.get("parts_dir", "staging")
                    break
        success = decommission_workspace(
            args.role, dir_scope=dir_scope, dest=args.dest, force=args.force
        )
        return 0 if success else 1
    elif args.subcommand == "refresh-sys":
        root = os.path.abspath(_repo_root)
        active_ws = load_registered_workspaces(root)
        target_role = normalize_role_arg(args.role) if args.role else None
        target_dir = args.dir
        count = 0
        for ws in active_ws:
            ws_role = ws.get("role") or ws.get("role_name", "")
            ws_dir = ws.get("dir") or ws.get("parts_dir", "staging")
            ws_path = ws.get("workspace_dir", "")
            if not ws_role and ws_path and os.path.isdir(ws_path):
                desc_path = os.path.join(ws_path, ROLE_DESCRIPTOR_FILE)
                if os.path.isfile(desc_path):
                    try:
                        with open(desc_path, "r", encoding="utf-8") as f:
                            rdata = json.load(f)
                        ws_role = rdata.get("role_name") or normalize_role_arg(
                            rdata.get("role_address", "")
                        )
                    except Exception as e:
                        sys.stderr.write(
                            f"Warning: Failed reading role descriptor '{desc_path}': {e}\n"
                        )
            if target_role and ws_role != target_role:
                continue
            if target_dir and ws_dir != target_dir:
                continue
            if ws_path and os.path.isdir(ws_path) and ws_role:
                try:
                    role_def = resolve_role_definition(ws_role, root)
                    refresh_system_files(ws_path, root, role_def, dir_scope=ws_dir)
                    count += 1
                except Exception as e:
                    sys.stderr.write(
                        f"Warning: Failed to refresh system files for {ws_role} in '{ws_path}': {e}\n"
                    )
        print(f"Refreshed system files across {count} role workspace(s).")
        return 0
    elif args.subcommand == "dirty":
        return run_dirty_command(dir_scope=args.dir)
    elif args.subcommand == "sync":
        return cleanroom_sync(sys_refresh=sys_mode)

    return cleanroom_sync(sys_refresh=sys_mode)


if __name__ == "__main__":
    sys.exit(main())
