#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents.

Provides role-local commands executed inside a commissioned role workspace:
- get_work: Self-synchronizing queue inspector; pulls updates from main and evaluates DAG.
- submit: Directly mutates canonical main repo via Bazel _submit target (or direct fallback).
- blame: Directly appends critique to canonical contract in main repo via Bazel _blame target.
- fail: Directly forces dirty state and appends failure diagnostics in main repo.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple


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
    if os.path.isdir(_p):
        if _p in sys.path:
            sys.path.remove(_p)
        sys.path.insert(0, _p)

from support.lib.lifecycle import enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import (
    control_asm,
    control_attribution,
    control_submit,
    control_work_scheduler,
    src_metadata,
)
from update_with_ai.parts.tools.lib import (
    tool_coverage,
    tools_asm,
)
try:
    from update_with_ai.support.lib.build_lint_common import parse_part_units
except ImportError:
    try:
        from update_python_with_ai.support.lib.build_lint_common import parse_part_units
    except ImportError:
        import build_lint_common
        parse_part_units = build_lint_common.parse_part_units
from update_with_ai.parts.workspace.lib import (
    workspace_asm,
    workspace_provision_impl,
    workspace_registry,
    workspace_registry_impl,
    workspace_sync_impl,
    workspace_work_impl,
)

STANDARD_ROLE_TYPES: Dict[str, List[str]] = {
    "high": ["implementation", "assembly", "interface", "external"],
    "planning": ["implementation", "assembly", "interface", "external"],
    "spec_qa": ["implementation", "assembly", "interface", "external"],
    "low": ["implementation", "assembly", "interface", "external"],
    "low_qa": ["implementation", "assembly", "interface", "external"],
    "grounding": ["implementation", "assembly", "interface", "external"],
    "grounding_qa": ["implementation", "assembly", "interface"],
    "lib": ["implementation", "assembly", "interface"],
    "test": ["implementation"],
    "qa": ["implementation"],
    "coverage": ["implementation"],
}


def classify_unit_type(unit_name: str) -> str:
    """Classifies a Cleanroom unit name into its component type."""
    if unit_name.endswith("_ext"):
        return "external"
    if unit_name.endswith("_asm"):
        return "assembly"
    if unit_name.endswith("_impl"):
        return "implementation"
    return "interface"


# Retained as legacy constants for backward compatibility
BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
AUDIT_BUFFER_FILE = ".cleanroom_audit_buffer.json"

AUDITOR_ROLE_TAGS: Dict[str, str] = {
    "grounding_qa": "GROUNDING_QA_AUDIT",
    "qa": "QA_AUDIT",
    "coverage": "COVERAGE_AUDIT",
}


def load_role_metadata(ws_root: str) -> Optional[Dict[str, Any]]:
    meta_p = os.path.join(ws_root, ".cleanroom_role.json")
    if os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def resolve_main_workspace_from_convention(ws_root: str) -> Tuple[str, str, str, str]:
    reg = workspace_registry_impl.WorkspaceRegistry()
    root = reg.discover_repository_root(ws_root)
    return root, "", "", ""


def _format_unit_pattern(pat: str) -> str:
    if not pat:
        return ""
    if "{unit_dir}" in pat or "{unit_name}" in pat:
        return pat
    d, pfx, sfx = parse_pattern_info(pat)
    if d:
        return f"{{unit_dir}}/{d}/{pfx}{{unit_name}}{sfx}"
    return f"{{unit_dir}}/{pfx}{{unit_name}}{sfx}"


def load_defined_roles(repo_root: str) -> Dict[str, Any]:
    return {
        name: {
            "name": r.role_name,
            "guide": r.guide_path,
            "src_pattern": _format_unit_pattern(r.writable_file_patterns[0] if r.writable_file_patterns else ""),
            "writable_file_patterns": r.writable_file_patterns,
            "readonly_file_patterns": r.readonly_file_patterns,
            "role_deps": list(r.feedback_role_deps),
            "feedback_role_deps": r.feedback_role_deps,
            "audit_tag": r.audit_tag,
            "active_component_types": STANDARD_ROLE_TYPES.get(
                name.split(":")[-1].strip().lower(),
                ["implementation", "assembly", "interface", "external"],
            ),
        }
        for name, r in workspace_registry_impl.STANDARD_ROLES.items()
    }


def parse_pattern_info(src_pattern: str) -> Tuple[str, str, str]:
    if not src_pattern:
        return "", "", ""
    clean = src_pattern.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
    if "/" in clean:
        dir_name, file_pattern = clean.split("/", 1)
    else:
        dir_name = ""
        file_pattern = clean

    if "{unit_name}" in file_pattern:
        prefix, suffix = file_pattern.split("{unit_name}", 1)
    elif "*" in file_pattern:
        prefix, suffix = file_pattern.split("*", 1)
    else:
        prefix, suffix = "", file_pattern

    return dir_name, prefix, suffix


def resolve_role_definition(role_name: str, repo_root: str) -> Dict[str, Any]:
    reg = workspace_registry_impl.WorkspaceRegistry()
    r = reg.resolve_role_definition(role_name, repo_root)
    clean_name = r.role_name.split(":")[-1].strip().lower()
    return {
        "name": r.role_name,
        "guide": r.guide_path,
        "src_pattern": _format_unit_pattern(r.writable_file_patterns[0] if r.writable_file_patterns else ""),
        "writable_file_patterns": r.writable_file_patterns,
        "readonly_file_patterns": r.readonly_file_patterns,
        "role_deps": list(r.feedback_role_deps),
        "feedback_role_deps": r.feedback_role_deps,
        "audit_tag": r.audit_tag,
        "active_component_types": STANDARD_ROLE_TYPES.get(
            clean_name,
            ["implementation", "assembly", "interface", "external"],
        ),
    }


def is_auditor_role(role_name: str) -> bool:
    r = role_name.split(":")[-1].strip().lower()
    return r in ("qa", "coverage", "grounding_qa")


def write_file_with_perms(
    dst: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o644)
        except OSError:
            pass
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
    mode = (0o555 if readonly else 0o755) if executable else (0o444 if readonly else 0o644)
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
    workspace_provision_impl.copy_file_with_perms(src, dst, readonly=readonly, executable=executable)


def find_part_dirs_in_scope(repo_root: str, dir_scope: str) -> List[str]:
    scope_p = os.path.join(repo_root, dir_scope)
    if not os.path.isdir(scope_p):
        return []
    parts_p = os.path.join(scope_p, "parts")
    if os.path.isdir(parts_p):
        return [
            os.path.join(dir_scope, "parts", d)
            for d in sorted(os.listdir(parts_p))
            if os.path.isdir(os.path.join(parts_p, d)) and not d.startswith(".")
        ]
    return [dir_scope]


def pull_workspace_from_main(
    ws_dir: str, main_root: str, role_name: str, dir_scope: str = "staging", silent: bool = True
) -> int:
    sync = workspace_sync_impl.WorkspaceSynchronizer()
    return sync.pull(ws_dir, main_root, role_name, dir_scope, silent=silent)


def refresh_system_files_fast(
    ws_dir: str, main_root: str, role_name: str, dir_scope: str = "staging", silent: bool = True
) -> int:
    sync = workspace_sync_impl.WorkspaceSynchronizer()
    return sync.refresh_system_files(ws_dir, main_root, role_name, dir_scope, silent=silent)


def eval_unit_dirty(
    ws_root: str, part_dir: str, unit_name: str, eval_role: str, role_def: Dict[str, Any]
) -> Dict[str, Any]:
    active_types = role_def.get("active_component_types")
    if active_types is not None and classify_unit_type(unit_name) not in active_types:
        return {"is_dirty": False, "reasons": []}

    curr_ws = find_workspace_root()
    meta_ws = get_current_role_metadata()
    curr_role = (meta_ws.get("role_name") or meta_ws.get("role", "")) if meta_ws else ""

    reasons: List[str] = []
    if is_auditor_role(eval_role):
        audit_tag = role_def.get("audit_tag") or f"{eval_role.upper()}_AUDIT"
        fb_deps = role_def.get("feedback_role_deps", [])
        if not fb_deps:
            return {"is_dirty": False, "reasons": []}
        primary_fb = fb_deps[0]
        fb_def = resolve_role_definition(primary_fb, ws_root)
        fb_pat = fb_def.get("src_pattern", "")
        if not fb_pat:
            return {"is_dirty": False, "reasons": []}
        primary_rel = (
            fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
            if "{unit_dir}" in fb_pat
            else os.path.join(
                part_dir,
                fb_pat.replace("*.py", f"{unit_name}.py")
                .replace("*.pyi", f"{unit_name}.pyi")
                .replace("*.md", f"{unit_name}.md"),
            )
        )
        primary_full = os.path.join(ws_root, primary_rel)
        if curr_ws and meta_ws and curr_role == eval_role:
            local_p = os.path.join(curr_ws, primary_rel)
            if os.path.isfile(local_p):
                primary_full = local_p
        if not os.path.isfile(primary_full):
            main_r = _resolve_main_root(ws_root, meta_ws)
            if main_r and main_r != ws_root:
                primary_full = os.path.join(main_r, primary_rel)
        if not os.path.isfile(primary_full):
            return {"is_dirty": True, "reasons": [f"Audited target {primary_rel} does not exist"]}
        primary_meta = src_metadata.extract_metadata(primary_full)
        if primary_meta is None or not primary_meta.last_changed:
            return {"is_dirty": True, "reasons": [f"Target {primary_rel} missing valid in-band metadata header"]}
        audit_ts = primary_meta.audits.get(audit_tag)
        if not audit_ts:
            reasons.append(f"Target {primary_rel} has not been certified with {audit_tag}")
        elif audit_ts < primary_meta.last_changed:
            reasons.append(
                f"Target {primary_rel} modified ({primary_meta.last_changed}) after {audit_tag} ({audit_ts})"
            )
        return {"is_dirty": bool(reasons), "reasons": reasons}

    # Producer role evaluation
    active_pat = role_def.get("src_pattern", "")
    if not active_pat:
        return {"is_dirty": False, "reasons": []}
    target_rel = (
        active_pat.format(unit_dir=part_dir, unit_name=unit_name)
        if "{unit_dir}" in active_pat
        else os.path.join(
            part_dir,
            active_pat.replace("*.py", f"{unit_name}.py")
            .replace("*.pyi", f"{unit_name}.pyi")
            .replace("*.md", f"{unit_name}.md"),
        )
    )
    full_path = os.path.join(ws_root, target_rel)
    if curr_ws and meta_ws and curr_role == eval_role:
        local_t = os.path.join(curr_ws, target_rel)
        if os.path.isfile(local_t):
            full_path = local_t
    if not os.path.isfile(full_path):
        main_r = _resolve_main_root(ws_root, meta_ws)
        if main_r and main_r != ws_root:
            full_path = os.path.join(main_r, target_rel)
    if not os.path.isfile(full_path):
        return {"is_dirty": True, "reasons": [f"Source file {target_rel} does not exist"]}
    meta = src_metadata.extract_metadata(full_path)
    if not meta or not meta.last_cleaned:
        return {"is_dirty": True, "reasons": [f"Header missing LAST_CLEANED in {target_rel}"]}
    if meta.dirty:
        reasons.append(f"Target explicitly marked DIRTY: {meta.dirty}")
    if meta.feedback:
        for fb in meta.feedback:
            reasons.append(f"Unacted feedback in {target_rel}: {fb}")

    # Forward dependency timestamp comparison
    dep_role_labels: List[str] = []
    for k in ["role_deps", "star_role_deps", "feedback_role_deps"]:
        for d in role_def.get(k, []):
            if d not in dep_role_labels:
                dep_role_labels.append(d)
    for d_label in dep_role_labels:
        d_name = d_label.split(":")[-1]
        if d_name == eval_role:
            continue
        d_def = resolve_role_definition(d_label, ws_root)
        d_pat = d_def.get("src_pattern", "")
        if not d_pat:
            continue
        d_rel = (
            d_pat.format(unit_dir=part_dir, unit_name=unit_name)
            if "{unit_dir}" in d_pat
            else os.path.join(
                part_dir,
                d_pat.replace("*.py", f"{unit_name}.py")
                .replace("*.pyi", f"{unit_name}.pyi")
                .replace("*.md", f"{unit_name}.md"),
            )
        )
        d_full = os.path.join(ws_root, d_rel)
        if not os.path.isfile(d_full):
            meta_ws = get_current_role_metadata()
            main_r = _resolve_main_root(ws_root, meta_ws)
            if main_r and main_r != ws_root:
                d_full = os.path.join(main_r, d_rel)
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
    repo_root: str, dir_scope: str = "staging", role_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    part_dirs = find_part_dirs_in_scope(repo_root, dir_scope)
    roles_dict = load_defined_roles(repo_root)

    target_roles = (
        {role_filter: roles_dict[role_filter]}
        if (role_filter and role_filter in roles_dict)
        else roles_dict
    )
    dirty_units: List[Dict[str, Any]] = []

    for part_dir in part_dirs:
        build_file = os.path.join(repo_root, part_dir, "BUILD.bazel")
        units = parse_part_units(build_file) if os.path.isfile(build_file) else {}
        if not units:
            full_part = os.path.join(repo_root, part_dir)
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
                eval_res = eval_unit_dirty(repo_root, part_dir, unit_name, r_name, r_def)
                if eval_res["is_dirty"]:
                    src_pat = r_def.get("src_pattern", "")
                    if src_pat:
                        target_file = src_pat.format(
                            unit_dir=part_dir, unit_name=unit_name
                        )
                    else:
                        fb_deps = r_def.get("feedback_role_deps", [])
                        if fb_deps:
                            fb_def = resolve_role_definition(fb_deps[0], repo_root)
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
                            "unit_name": unit_name,
                            "part_dir": part_dir,
                            "role": r_name,
                            "target_file": target_file,
                            "reasons": eval_res.get("reasons", ["In-band metadata dirty"]),
                            "dirtiness_reasons": eval_res.get("reasons", ["In-band metadata dirty"]),
                        }
                    )
    return dirty_units


def topological_sort_units(
    units_list: List[Dict[str, Any]],
    module_deps: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    unit_map = {item["unit_name"]: item for item in units_list}
    visited: Set[str] = set()
    temp_mark: Set[str] = set()
    order: List[Dict[str, Any]] = []

    def visit(uname: str) -> None:
        if uname in visited or uname in temp_mark:
            return
        temp_mark.add(uname)
        for dep in sorted(module_deps.get(uname, [])):
            if dep in unit_map:
                visit(dep)
        temp_mark.remove(uname)
        visited.add(uname)
        order.append(unit_map[uname])

    for item in sorted(units_list, key=lambda x: str(x.get("unit_name", ""))):
        uname = str(item.get("unit_name", ""))
        if uname not in visited:
            visit(uname)

    return order


def get_role_upstream_chain(role_name: str, roles_def: Dict[str, Any]) -> List[str]:
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
    *args: Any,
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Computes ready and blocked dirty units directly from the build graph without requiring a DagStorage subgraph."""
    if len(args) >= 3:
        if args[0] in ("high", "planning", "low", "lib", "test", "qa", "coverage") or ":" in str(args[0]) or "//" in str(args[0]):
            role_name, dir_scope, main_repo_root = str(args[0]), str(args[1]), str(args[2])
        else:
            main_repo_root, dir_scope, role_name = str(args[0]), str(args[1]), str(args[2])
    else:
        role_name = str(kwargs.get("role_name", ""))
        dir_scope = str(kwargs.get("dir_scope", "staging"))
        main_repo_root = str(kwargs.get("main_repo_root") or kwargs.get("main_root", ""))

    clean_role = role_name.split(":")[-1].strip().lower()
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
        roles_to_check = upstream_roles
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

            dep_file = os.path.join(dep_pkg, "lib", f"{dep_u}.py")
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


def find_workspace_root() -> str:
    """Finds the root of the current role workspace containing .cleanroom_role.json."""
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, ".cleanroom_role.json")):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()


def get_current_role_metadata() -> Optional[Dict[str, Any]]:
    """Loads metadata for current role workspace."""
    ws_root = find_workspace_root()
    return load_role_metadata(ws_root)


def _resolve_main_root(
    ws_root: str,
    meta: Optional[Dict[str, Any]] = None,
    repo_root: Optional[str] = None,
) -> str:
    """Resolves canonical main workspace root via convention or metadata."""
    if repo_root:
        return os.path.realpath(repo_root)
    if meta:
        m_root = meta.get("main_workspace_root") or meta.get("repo_root")
        if m_root and os.path.isdir(m_root):
            return os.path.realpath(m_root)
    try:
        main_cand, _, _, _ = (
            resolve_main_workspace_from_convention(ws_root)
        )
        if main_cand and main_cand != ws_root and os.path.isdir(main_cand):
            return os.path.realpath(main_cand)
    except Exception as e:
        if meta:
            sys.stderr.write(
                f"Warning: could not resolve canonical main workspace for '{ws_root}': {e}\n"
            )
    return ws_root


def _can_run_bazel(main_root: str) -> bool:
    """Checks whether Bazel can be invoked in the main repository."""
    if os.environ.get("CLEANROOM_DIRECT_MUTATION") == "1":
        return False
    if not (
        os.path.isfile(os.path.join(main_root, "MODULE.bazel"))
        or os.path.isfile(os.path.join(main_root, "WORKSPACE"))
    ):
        return False
    return shutil.which("bazel") is not None


def _is_test_file(target: str) -> bool:
    norm = target.strip().replace("\\", "/")
    return norm.endswith("_test.py") or "/tests/" in norm or norm.startswith("tests/")


def resolve_file_role(file_path: str, repo_root: str) -> str:
    """Derives role name (e.g. 'lib', 'low', 'high') from a target file path."""
    norm = file_path.replace("\\", "/")
    parent = os.path.basename(os.path.dirname(norm))
    known_roles = [
        "high",
        "planning",
        "low",
        "grounding",
        "grounding_qa",
        "lib",
        "test",
        "qa",
        "coverage",
    ]
    if parent in known_roles:
        return parent
    if parent == "tests":
        return "test"
    roles_def = load_defined_roles(repo_root)
    for r_name, r_def in roles_def.items():
        pat = r_def.get("src_pattern", "")
        if pat:
            d, pfx, sfx = parse_pattern_info(pat)
            fname = os.path.basename(norm)
            if parent == d and fname.startswith(pfx) and fname.endswith(sfx):
                return r_name
    return "lib"


def parse_unit_from_file_path(file_path: str, repo_root: str) -> Tuple[str, str, str]:
    """Returns (part_dir, unit_name, role_name) from file_path relative to repo_root."""
    norm_path = os.path.realpath(file_path)
    norm_root = os.path.realpath(repo_root)
    rel = (
        os.path.relpath(norm_path, norm_root).replace("\\", "/")
        if norm_path.startswith(norm_root)
        else file_path.replace("\\", "/")
    )
    fname = os.path.basename(rel)
    unit_name = os.path.splitext(fname)[0]
    if unit_name.endswith("_test"):
        unit_name = unit_name[:-5]
    role_name = resolve_file_role(rel, repo_root)
    part_dir = os.path.dirname(os.path.dirname(rel))
    return part_dir, unit_name, role_name


def _resolve_target_path(target: str, repo_root: str) -> str:
    """Resolves target path cleanly handling absolute and relative paths."""
    target_str = target.strip()
    norm_root = os.path.realpath(repo_root)
    if os.path.isabs(target_str):
        return os.path.realpath(target_str)
    cand1 = os.path.realpath(target_str)
    if os.path.exists(cand1):
        return cand1
    cand2 = os.path.realpath(os.path.join(norm_root, target_str.lstrip("/")))
    if os.path.exists(cand2):
        return cand2
    return cand1


def resolve_submit_target(
    target: str,
    repo_root: str,
    role_name: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolves target path and unit name for submit command."""
    target_str = target.strip()

    # 1. Direct path check
    cand_path = _resolve_target_path(target_str, repo_root)
    if os.path.isfile(cand_path):
        stem = os.path.splitext(os.path.basename(cand_path))[0]
        if stem.endswith("_test"):
            stem = stem[:-5]
        return cand_path, stem

    role_def = resolve_role_definition(role_name, repo_root)

    # 2. Check virtual role target, e.g. <part_dir>/qa/<unit_name>
    target_norm = target_str.replace("\\", "/").strip("/")
    if f"/{role_name}/" in target_norm:
        part_dir, _, unit_name = target_norm.partition(f"/{role_name}/")
        unit_name = unit_name.strip()
        fb_deps = role_def.get("feedback_role_deps", [])
        if fb_deps:
            fb_def = resolve_role_definition(
                fb_deps[0], repo_root
            )
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat:
                cand = os.path.realpath(
                    os.path.join(
                        repo_root, fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
                    )
                )
                if os.path.isfile(cand):
                    return cand, unit_name

    # 3. Check bare unit name or stem across parts in scope
    stem = os.path.splitext(os.path.basename(target_str))[0]
    if stem.endswith("_test"):
        stem = stem[:-5]
    d_scope = (meta.get("dir_scope") or meta.get("parts_dir", "staging")) if meta else "staging"
    part_dirs = find_part_dirs_in_scope(repo_root, d_scope)

    if is_auditor_role(role_name):
        fb_deps = role_def.get("feedback_role_deps", [])
        if fb_deps:
            fb_def = resolve_role_definition(
                fb_deps[0], repo_root
            )
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat:
                for pd in part_dirs:
                    cand = os.path.realpath(
                        os.path.join(
                            repo_root, fb_pat.format(unit_dir=pd, unit_name=stem)
                        )
                    )
                    if os.path.isfile(cand):
                        return cand, stem
    else:
        src_pat = role_def.get("src_pattern", "")
        if src_pat:
            for pd in part_dirs:
                cand = os.path.realpath(
                    os.path.join(repo_root, src_pat.format(unit_dir=pd, unit_name=stem))
                )
                if os.path.isfile(cand):
                    return cand, stem

    return None, None


PENDING_WORK_FILE = ".cleanroom_pending_work.json"


def get_pending_work(ws_root: str) -> List[str]:
    """Returns list of pending target paths assigned in previous get_work calls."""
    p = os.path.join(ws_root, PENDING_WORK_FILE)
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return list(data.get("targets", []))
            elif isinstance(data, list):
                return list(data)
        except Exception as e:
            sys.stderr.write(f"Warning: Failed reading pending work file '{p}': {e}\n")
    return []


def set_pending_work(ws_root: str, targets: List[str]) -> None:
    """Records pending target paths assigned to the workspace."""
    p = os.path.join(ws_root, PENDING_WORK_FILE)
    if not targets:
        clear_pending_work(ws_root)
        return
    try:
        write_file_with_perms(
            p,
            json.dumps(
                {
                    "assigned_at": src_metadata.current_utc_timestamp(),
                    "targets": targets,
                },
                indent=2,
            )
            + "\n",
            readonly=False,
        )
    except Exception as e:
        sys.stderr.write(f"Warning: Failed saving pending work file '{p}': {e}\n")


def clear_pending_work(ws_root: str) -> None:
    """Clears pending work tracking file."""
    p = os.path.join(ws_root, PENDING_WORK_FILE)
    if os.path.isfile(p):
        try:
            os.remove(p)
        except OSError as e:
            sys.stderr.write(f"Warning: Failed removing pending work file '{p}': {e}\n")


def remove_pending_target(ws_root: str, submitted_target: str) -> None:
    """Removes a submitted or resolved target from pending work."""
    targets = get_pending_work(ws_root)
    if not targets:
        return
    norm_sub = submitted_target.strip().lstrip("/")
    sub_stem = os.path.splitext(os.path.basename(norm_sub))[0]
    if sub_stem.endswith("_test"):
        sub_stem = sub_stem[:-5]
    remaining = []
    for t in targets:
        norm_t = t.strip().lstrip("/")
        t_stem = os.path.splitext(os.path.basename(norm_t))[0]
        if t_stem.endswith("_test"):
            t_stem = t_stem[:-5]
        if (
            norm_t == norm_sub
            or norm_t.endswith(f"/{norm_sub}")
            or norm_sub.endswith(f"/{norm_t}")
            or t_stem == sub_stem
        ):
            continue
        remaining.append(t)
    if len(remaining) == len(targets) and len(targets) == 1:
        # If single target was pending and didn't match stem (e.g. cross-unit blame/resolution), clear it
        remaining = []
    set_pending_work(ws_root, remaining)


def is_pending_target_dirty(
    pt: str, ws_root: str, main_root: str, role_name: str
) -> bool:
    """Checks whether a pending target file is still dirty in ws_root or main."""
    full_ws = os.path.join(ws_root, pt) if not os.path.isabs(pt) else pt
    ref_root = ws_root
    part_dir, unit_name, r_name = parse_unit_from_file_path(full_ws, ref_root)
    eval_role = role_name or r_name
    role_def = resolve_role_definition(
        eval_role, main_root or ws_root
    )
    if not is_auditor_role(eval_role):
        if not os.path.isfile(full_ws):
            return True
        meta_ws = src_metadata.extract_metadata(full_ws)
        if (
            meta_ws is None
            or not meta_ws.last_cleaned
            or meta_ws.dirty
            or meta_ws.feedback
        ):
            return True
    if not unit_name:
        return False
    res = eval_unit_dirty(
        ws_root, part_dir, unit_name, eval_role, role_def
    )
    return res.get("is_dirty", False)


# ==============================================================================
# Role Commands: get_work, submit, blame, fail
# ==============================================================================


def run_get_work(
    dir_scope: Optional[str] = None,
    repo_root: Optional[str] = None,
    force: bool = False,
) -> int:
    """Evaluates dirtiness in local workspace scope and prints next ready tasks for this role."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    role_name = (meta.get("role_name") or meta.get("role", "")) if meta else ""
    d_scope = dir_scope or (
        (meta.get("dir_scope") or meta.get("parts_dir", "staging"))
        if meta
        else "staging"
    )

    main_root = _resolve_main_root(ws_root, meta, repo_root)

    # Check if pending work exists from a previous get_work call
    if meta and not force:
        pending = get_pending_work(ws_root)
        if pending:
            still_dirty = [
                pt
                for pt in pending
                if is_pending_target_dirty(pt, ws_root, main_root, role_name)
            ]
            if still_dirty:
                print(
                    f"\nError: Cannot call get_work while work is pending in this role workspace."
                )
                print(f"Pending dirty target(s) from previous get_work call:")
                for pt in still_dirty:
                    print(f"  • {pt}")
                if is_auditor_role(role_name):
                    print(
                        f"\nComplete the pending work before getting new work:\n"
                        f"  bin/submit <target_file> (attests {role_name.upper()}_AUDIT)\n"
                        f"Or attribute defect to an upstream contract:\n"
                        f"  bin/blame <culprit-file> \"<actionable critique>\"\n"
                    )
                else:
                    print(
                        f"\nComplete the pending work before getting new work:\n"
                        f"  bin/submit <target_file> \"<summary>\" (or bin/submit <target_file> if no changes)\n"
                        f"Or attribute defect to an upstream contract:\n"
                        f"  bin/blame <culprit-file> \"<actionable critique>\"\n"
                    )
                return 1
            else:
                clear_pending_work(ws_root)

    # 1 & 2: Inbound pull and fast system refresh from main if in a distinct role workspace
    if main_root and os.path.isdir(main_root) and main_root != ws_root:
        try:
            pull_workspace_from_main(
                ws_root, main_root, role_name, dir_scope=d_scope, silent=True
            )
            refresh_system_files_fast(
                ws_root, main_root, role_name, dir_scope=d_scope, silent=True
            )
        except Exception as e:
            sys.stderr.write(f"Warning: automatic sync from main failed: {e}\n")
    elif meta and main_root == ws_root:
        sys.stderr.write(
            f"Warning: In role workspace '{ws_root}' but canonical main workspace could not be resolved. Inbound sync skipped.\n"
        )
    elif main_root and not os.path.isdir(main_root):
        sys.stderr.write(
            f"Warning: Canonical main workspace '{main_root}' is not an accessible directory. Inbound sync skipped.\n"
        )

    # 3: Scope-wide dependency evaluation on the build graph
    eval_root = (
        main_root if (meta and main_root and os.path.isdir(main_root)) else ws_root
    )
    ready_items, blocked_items = compute_role_work_queue(
        role_name, d_scope, eval_root
    )

    print(
        f"\n=== Cleanroom Work Queue [Role: {(role_name or 'ALL').upper()} | Scope: {d_scope}] ==="
    )
    if not ready_items and not blocked_items:
        if meta:
            clear_pending_work(ws_root)
        print(
            f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
        )
        return 0

    if ready_items and meta:
        set_pending_work(ws_root, [item["target_file"] for item in ready_items])
    elif meta:
        clear_pending_work(ws_root)

    total_dirty = len(ready_items) + len(blocked_items)
    print(f"Found {total_dirty} dirty unit(s) ({len(ready_items)} ready to clean):")
    for item in ready_items:
        print(f"\n  • [READY - {item['role'].upper()}] {item['target_file']}")
        for r in item["reasons"]:
            print(f"      - {r}")
        if item.get("dependencies"):
            print("      Dependencies:")
            for dep in item["dependencies"]:
                print(f"        - {dep}")

    if blocked_items:
        print(f"\nBlocked unit(s) ({len(blocked_items)} waiting on prerequisites):")
        for item in blocked_items:
            print(f"\n  • [BLOCKED - {item['role'].upper()}] {item['target_file']}")
            for br in item.get("blocked_reasons", []):
                print(f"      - {br}")
            if item.get("dependencies"):
                print("      Dependencies:")
                for dep in item["dependencies"]:
                    print(f"        - {dep}")

    if is_auditor_role(role_name):
        print(
            f"\nACTIONABLE NEXT STEP: Execute verification suite for target, then run 'bin/submit <target_file>' to attest {role_name.upper()}_AUDIT.\n"
        )
    else:
        print(
            "\nACTIONABLE NEXT STEP: Implement or verify target, then run 'bin/submit <file> \"<summary>\"' (or 'bin/submit <file>' if no changes).\n"
        )
    return 1 if ready_items else 0


def run_submit(
    target: str,
    summary: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Verifies target and stamps in-band metadata or <ROLE>_AUDIT directly in main."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    role_name = str(meta.get("role_name") or meta.get("role") or "") if meta else ""
    main_root = _resolve_main_root(ws_root, meta, repo_root)

    # Auditor role submit: reject direct submission of feedback/test files
    if is_auditor_role(role_name):
        if _is_test_file(target):
            print(f"Error: Cannot submit verification/test file '{target}'.")
            print(
                f"In {role_name.upper()}, your role is auditing the implementation target."
            )
            print(
                f"Submit the audited implementation target instead: bin/submit <impl_file> (or bin/submit <unit_name>)"
            )
            return 1

    target_path, unit_name = resolve_submit_target(target, ws_root, role_name, meta)
    if not target_path or not os.path.isfile(target_path):
        target_path, unit_name = resolve_submit_target(
            target, main_root, role_name, meta
        )

    if not target_path or not os.path.isfile(target_path):
        print(f"Error: Target '{target}' not found on disk.")
        return 1

    role_def = resolve_role_definition(role_name, main_root)

    # --- AUDITOR ROLE SUBMIT ---
    if is_auditor_role(role_name):
        audit_tag = AUDITOR_ROLE_TAGS.get(
            role_name, f"{role_name.upper()}_AUDIT"
        )

        ref_root = ws_root if target_path.startswith(ws_root) else main_root
        part_dir, u_name, _ = parse_unit_from_file_path(target_path, ref_root)
        active_unit = unit_name or u_name
        targets_to_audit = [
            os.path.join(main_root, part_dir, "lib", f"{active_unit}.py")
        ]
        fb_deps = role_def.get("feedback_role_deps", [])
        for fb_label in fb_deps:
            fb_def = resolve_role_definition(
                fb_label, main_root
            )
            fb_pat = fb_def.get("src_pattern", "")
            if fb_pat:
                fb_full = os.path.join(
                    main_root,
                    fb_pat.format(unit_dir=part_dir, unit_name=active_unit),
                )
                if os.path.isfile(fb_full) and fb_full not in targets_to_audit:
                    targets_to_audit.append(fb_full)

        companion_test = os.path.join(
            main_root, part_dir, "tests", f"{active_unit}_test.py"
        )
        if os.path.isfile(companion_test) and companion_test not in targets_to_audit:
            targets_to_audit.append(companion_test)

        if _can_run_bazel(main_root):
            submit_target = f"//{part_dir}:{active_unit}_{role_name}_submit"
            cmd = ["bazel", "run", submit_target]
            res = subprocess.run(cmd, cwd=main_root)
            if res.returncode != 0:
                return res.returncode
        else:
            # Direct mutation on main_root
            stamped = []
            for tf in targets_to_audit:
                if os.path.isfile(tf):
                    src_metadata.stamp_audit(tf, role_name)
                    src_metadata.update_metadata(tf, clear_dirty=True)
                    stamped.append(os.path.relpath(tf, main_root))

            if stamped:
                print(
                    f"✔ Audited target stamped: {', '.join(stamped)} (Tagged: {audit_tag})"
                )

        # Reflect attested audits to local role workspace if present
        if ws_root != main_root:
            for tf in targets_to_audit:
                rel = os.path.relpath(tf, main_root)
                wt = os.path.join(ws_root, rel)
                if os.path.isfile(tf) and os.path.isfile(wt):
                    copy_file_with_perms(tf, wt, readonly=True)

        if meta:
            remove_pending_target(ws_root, target)
            if target_path:
                remove_pending_target(ws_root, target_path)
            if active_unit:
                remove_pending_target(ws_root, active_unit)

        return 0

    # --- PRODUCER ROLE SUBMIT ---
    # 1. Enforce that read-only files cannot be submitted
    is_ro = False
    try:
        st = os.stat(target_path)
        is_ro = not bool(st.st_mode & stat.S_IWUSR)
    except OSError:
        is_ro = True

    if is_ro:
        print(
            f"Error: Target '{target}' is read-only. Producer roles can only submit their own read-write targets."
        )
        return 1

    # 2. Enforce active directory scope matching
    active_pattern = role_def.get("src_pattern", "") if role_def else ""
    if active_pattern:
        active_dir, active_pfx, active_sfx = (
            parse_pattern_info(active_pattern)
        )
        fname = os.path.basename(target_path)
        parent = os.path.basename(os.path.dirname(target_path))
        if parent != active_dir or not (
            fname.startswith(active_pfx) and fname.endswith(active_sfx)
        ):
            print(
                f"Error: Target '{target}' is outside active role directory scope ({active_dir}/{active_pfx}*{active_sfx})."
            )
            return 1

    summary_text = summary or f"Updated {os.path.basename(target_path)}"

    # 3. Symmetric change summary validation
    is_modified = src_metadata.is_code_modified(target_path)
    summary_provided = bool(summary and summary.strip())

    if is_modified and not summary_provided:
        print(
            f"Error: Target '{target}' has been modified (CODE_HASH differs), but no change summary was provided."
        )
        print(f'Usage: bin/submit {target} "<concise change summary>"')
        return 1

    if not is_modified and summary_provided:
        print(f"Error: Target '{target}' was not modified (CODE_HASH matches).")
        print("A change summary must not be provided for an unchanged file.")
        print(f"Usage to submit without changes: bin/submit {target}")
        return 1

    # 4. Copy modified file to canonical main workspace
    rel_path = (
        os.path.relpath(target_path, ws_root)
        if target_path.startswith(ws_root)
        else os.path.relpath(target_path, main_root)
    )
    main_file = os.path.join(main_root, rel_path)
    if ws_root != main_root and os.path.isfile(target_path):
        copy_file_with_perms(
            target_path, main_file, readonly=False
        )

    part_dir, u_name, _ = parse_unit_from_file_path(target_path, ws_root)
    active_unit = unit_name or u_name

    if _can_run_bazel(main_root):
        submit_target = f"//{part_dir}:{active_unit}_{role_name}_submit"
        cmd = ["bazel", "run", submit_target]
        if summary_provided:
            cmd.extend(["--", summary_text])
        else:
            cmd.append("--")
        res = subprocess.run(cmd, cwd=main_root)
        if res.returncode != 0:
            return res.returncode
        if ws_root != main_root and os.path.isfile(main_file):
            copy_file_with_perms(
                main_file, target_path, readonly=False
            )
        if meta:
            remove_pending_target(ws_root, target)
            if target_path:
                remove_pending_target(ws_root, target_path)
            if active_unit:
                remove_pending_target(ws_root, active_unit)
        return 0
    else:
        # Direct mutation on main_file
        if is_modified:
            src_metadata.record_change(main_file, summary_text)
            print(
                f"✔ Submitted {target_path}: code modified and in-band metadata updated (CHANGE: {summary_text})"
            )
        else:
            src_metadata.mark_clean(main_file)
            print(
                f"✔ Submitted {target_path}: code unchanged, in-band metadata marked clean (LAST_CLEANED updated, DIRTY cleared)"
            )
        if ws_root != main_root and os.path.isfile(main_file):
            copy_file_with_perms(
                main_file, target_path, readonly=False
            )
        if meta:
            remove_pending_target(ws_root, target)
            if target_path:
                remove_pending_target(ws_root, target_path)
            if active_unit:
                remove_pending_target(ws_root, active_unit)
        return 0


def run_blame(
    culprit_file: str,
    critique: str,
    repo_root: Optional[str] = None,
) -> int:
    """Attributes critique directly to upstream contract or culprit file in main."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    main_root = _resolve_main_root(ws_root, meta, repo_root)

    dep_path = _resolve_target_path(culprit_file, main_root)
    if not os.path.exists(dep_path):
        dep_path = _resolve_target_path(culprit_file, ws_root)
    if not os.path.exists(dep_path):
        print(f"Error: Could not locate blame target '{culprit_file}'.")
        return 1

    caller = (meta.get("role_name") or meta.get("role", "")) if meta else ""
    if not caller:
        caller = (
            os.environ.get("CLEANROOM_ROLE") or os.environ.get("USER") or "cleanroom"
        )

    ref_root = main_root if dep_path.startswith(main_root) else ws_root
    part_dir, unit_name, blamed_role = parse_unit_from_file_path(dep_path, ref_root)
    main_dep_path = os.path.join(main_root, os.path.relpath(dep_path, ref_root))

    if _can_run_bazel(main_root):
        blame_target = f"//{part_dir}:{unit_name}_{blamed_role}_blame"
        cmd = ["bazel", "run", blame_target, "--", critique]
        res = subprocess.run(cmd, cwd=main_root)
        if res.returncode != 0:
            return res.returncode
        if ws_root != main_root and os.path.isfile(main_dep_path):
            ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
            if os.path.exists(ws_dep):
                copy_file_with_perms(
                    main_dep_path, ws_dep, readonly=True
                )
        if meta:
            remove_pending_target(ws_root, culprit_file)
        return 0
    else:
        target_to_mutate = main_dep_path if os.path.exists(main_dep_path) else dep_path
        src_metadata.append_feedback(target_to_mutate, critique, sender=caller)
        src_metadata.mark_dirty(target_to_mutate, f"Blamed by {caller}: {critique}")
        src_metadata.update_metadata(
            target_to_mutate, last_cleaned=src_metadata.current_utc_timestamp()
        )
        print(f"Appended FEEDBACK: into {target_to_mutate}")
        if ws_root != main_root and os.path.isfile(main_dep_path):
            ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
            if os.path.exists(ws_dep):
                copy_file_with_perms(
                    main_dep_path, ws_dep, readonly=True
                )
        if meta:
            remove_pending_target(ws_root, culprit_file)
        return 0


def run_fail(
    file_path: str,
    reason: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Marks target dirty with DIRTY tag and appends failure diagnostics in main."""
    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    main_root = _resolve_main_root(ws_root, meta, repo_root)

    full_p = _resolve_target_path(file_path, main_root)
    if not os.path.isfile(full_p):
        full_p = _resolve_target_path(file_path, ws_root)

    failure_reason = reason or "Verification failed"
    if not os.path.isfile(full_p):
        print(f"Error: Target '{file_path}' not found.")
        return 1

    ref_root = main_root if full_p.startswith(main_root) else ws_root
    rel_p = os.path.relpath(full_p, ref_root)
    main_p = os.path.join(main_root, rel_p)
    target_to_mutate = main_p if os.path.exists(main_p) else full_p

    src_metadata.mark_dirty(target_to_mutate, reason=failure_reason)
    src_metadata.append_feedback(
        target_to_mutate,
        f"Verification failed: {failure_reason}",
        sender="verification",
    )
    print(
        f"Marked failure on {target_to_mutate}: added DIRTY tag and updated LAST_CLEANED."
    )

    if ws_root != main_root and os.path.isfile(main_p):
        ws_p = os.path.join(ws_root, rel_p)
        if os.path.exists(ws_p):
            is_ro = not bool(os.stat(ws_p).st_mode & stat.S_IWUSR)
            copy_file_with_perms(main_p, ws_p, readonly=is_ro)

    if meta:
        remove_pending_target(ws_root, file_path)

    return 0


def run_coverage(
    target: Optional[str] = None,
    impl: Optional[str] = None,
    test: Optional[str] = None,
    threshold: float = 0.0,
    update_log: Optional[str] = None,
    max_spans: Optional[int] = None,
    json_output: bool = False,
    repo_root: Optional[str] = None,
) -> int:
    """Evaluates statement test coverage for a library module or target."""
    from pathlib import Path

    ws_root = os.path.realpath(find_workspace_root())
    meta = get_current_role_metadata()
    main_root = _resolve_main_root(ws_root, meta, repo_root)
    root = Path(main_root if os.path.isdir(main_root) else ws_root)

    evaluator = tool_coverage.get_coverage_evaluator()

    if impl and test:
        impl_path = Path(impl)
        if not impl_path.is_absolute():
            impl_path = (root / impl_path).resolve()
        test_path = Path(test)
        if not test_path.is_absolute():
            test_path = (root / test_path).resolve()
        if not impl_path.is_file():
            print(f"Error: Implementation file not found: {impl_path}", file=sys.stderr)
            return 1
        if not test_path.is_file():
            print(f"Error: Test file not found: {test_path}", file=sys.stderr)
            return 1
        cov = evaluator.measure_single_target_coverage(impl_path, test_path)
    elif target:
        target_map = evaluator.get_available_targets(root)
        query = evaluator.normalize_target_query(target)
        if query not in target_map:
            print(f"Error: Unrecognized target '{target}'.", file=sys.stderr)
            return 1
        impl_path, test_path = target_map[query]
        cov = evaluator.measure_single_target_coverage(impl_path, test_path)
    else:
        print("Error: Specify target or both --impl and --test.", file=sys.stderr)
        return 1

    if json_output:
        import dataclasses

        print(json.dumps(dataclasses.asdict(cov), indent=2))
        return 0 if (cov.test_passed and cov.coverage_pct >= threshold) else 1

    report = evaluator.format_coverage_report(cov, threshold, max_spans=max_spans)
    if update_log:
        log_p = Path(update_log)
        if not log_p.is_absolute():
            log_p = root / log_p
        log_p.parent.mkdir(parents=True, exist_ok=True)
        if cov.test_passed and cov.missed == 0:
            with open(log_p, "w", encoding="utf-8") as f:
                pass
        else:
            with open(log_p, "w", encoding="utf-8") as f:
                f.write(report)

    print(report)
    if not cov.test_passed or cov.coverage_pct < threshold:
        return 1
    return 0


def run_commission(
    role_name: str,
    dir_scope: str = "staging",
    repo_root: Optional[str] = None,
    custom_dest: Optional[str] = None,
) -> int:
    """Commissions an isolated role workspace."""
    from support.lib.lifecycle import enter_phase
    from update_with_ai.parts.agent.lib import agent_session
    from update_with_ai.parts.control.lib import control_asm
    from update_with_ai.parts.workspace.lib import workspace_asm

    workspace_asm.__initialize__()
    control_asm.__initialize__()
    with enter_phase(agent_session.agent_session):
        prov = workspace_provision_impl.WorkspaceProvisioner()
        desc = prov.commission(
            role_name, dir_scope, repo_root=repo_root, custom_dest=custom_dest
        )
        print(f"✔ Commissioned workspace for role '{role_name}' at: {desc.workspace_dir}")
        return 0


def run_decommission(
    role_name_or_dir: str,
    dir_scope: Optional[str] = None,
    repo_root: Optional[str] = None,
    custom_dest: Optional[str] = None,
    force: bool = False,
) -> int:
    """Decommissions a role workspace."""
    from support.lib.lifecycle import enter_phase
    from update_with_ai.parts.agent.lib import agent_session
    from update_with_ai.parts.control.lib import control_asm
    from update_with_ai.parts.workspace.lib import workspace_asm

    workspace_asm.__initialize__()
    control_asm.__initialize__()
    with enter_phase(agent_session.agent_session):
        prov = workspace_provision_impl.WorkspaceProvisioner()
        success = prov.decommission(
            role_name_or_dir,
            dir_scope=dir_scope,
            repo_root=repo_root,
            custom_dest=custom_dest,
            force=force,
        )
        if success:
            print(f"✔ Decommissioned workspace: {role_name_or_dir}")
            return 0
        else:
            print(f"Failed to decommission workspace: {role_name_or_dir}", file=sys.stderr)
            return 1


def run_refresh_sys(
    role_name: Optional[str] = None,
    dir_scope: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> int:
    """Refreshes system files, tools, configs, and guides across role workspaces."""
    from support.lib.lifecycle import enter_phase
    from update_with_ai.parts.agent.lib import agent_session
    from update_with_ai.parts.control.lib import control_asm
    from update_with_ai.parts.workspace.lib import workspace_asm

    workspace_asm.__initialize__()
    control_asm.__initialize__()
    with enter_phase(agent_session.agent_session):
        root = repo_root or find_workspace_root() or os.getcwd()
        reg = workspace_registry_impl.WorkspaceRegistry()
        active_workspaces = reg.load_active_workspaces(repo_root=root)
        sync = workspace_sync_impl.WorkspaceSynchronizer()
        target_role = role_name.split(":")[-1].strip().lower() if role_name else None
        count = 0
        for ws in active_workspaces:
            r_name = ws.role_definition.role_name.split(":")[-1].strip().lower()
            if target_role and r_name != target_role:
                continue
            if dir_scope and ws.directory_scope != dir_scope:
                continue
            if os.path.isdir(ws.workspace_dir):
                try:
                    sync.refresh_system_files(
                        ws.workspace_dir, root, ws.role_definition.role_name, ws.directory_scope, silent=False
                    )
                    count += 1
                except Exception as e:
                    sys.stderr.write(
                        f"Warning: Failed to refresh system files for {ws.role_definition.role_name} in '{ws.workspace_dir}': {e}\n"
                    )
        print(f"Refreshed system files across {count} role workspace(s).")
        return 0


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="cleanroom_role_tool",
        description="Cleanroom Role Workspace Subagent CLI Tool",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # commission
    p_comm = subparsers.add_parser(
        "commission", help="Commission an isolated role workspace"
    )
    p_comm.add_argument("role", help="Role name to commission (e.g. high, planning, low, lib, test, qa, coverage)")
    p_comm.add_argument("dir", nargs="?", default="staging", help="Directory scope (default: staging)")
    p_comm.add_argument("--repo-root", default=None, help="Root of canonical repository")
    p_comm.add_argument("--dest", default=None, help="Custom destination directory")

    # decommission
    p_decomm = subparsers.add_parser(
        "decommission", help="Decommission a role workspace"
    )
    p_decomm.add_argument("target", help="Role name or workspace directory to decommission")
    p_decomm.add_argument("dir", nargs="?", default=None, help="Directory scope")
    p_decomm.add_argument("--repo-root", default=None, help="Root of canonical repository")
    p_decomm.add_argument("--dest", default=None, help="Custom destination directory")
    p_decomm.add_argument("--force", "-f", action="store_true", help="Force decommission")

    # refresh-sys
    p_ref = subparsers.add_parser(
        "refresh-sys",
        aliases=["refresh_sys"],
        help="Refresh system files, tools, configs, and guides across role workspaces",
    )
    p_ref.add_argument("role", nargs="?", default=None, help="Optional role name to filter")
    p_ref.add_argument("dir", nargs="?", default=None, help="Optional directory scope to filter")
    p_ref.add_argument("--repo-root", default=None, help="Root of canonical repository")

    # get_work
    p_work = subparsers.add_parser(
        "get_work", help="Get ready dirty tasks in workspace scope"
    )
    p_work.add_argument("dir", nargs="?", default=None, help="Directory scope override")
    p_work.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force get_work even if work is pending",
    )

    # submit
    p_submit = subparsers.add_parser(
        "submit", help="Verify and submit target with in-band header update"
    )
    p_submit.add_argument("target", help="Target file path or unit name")
    p_submit.add_argument("summary", nargs="?", default=None, help="Change summary")

    # blame
    p_blame = subparsers.add_parser(
        "blame",
        help="Attribute blame feedback to a culprit file or upstream contract",
        description="Attributes actionable critique to a culprit specification, code, or test file.",
    )
    p_blame.add_argument(
        "culprit_file",
        metavar="<culprit-file>",
        help="Path to the culprit file receiving blame",
    )
    p_blame.add_argument(
        "critique",
        metavar="<actionable-critique>",
        help="Actionable critique message without newlines",
    )

    # fail
    p_fail = subparsers.add_parser(
        "fail", help="Record verification failure and force dirty state"
    )
    p_fail.add_argument("target", help="Target file path")
    p_fail.add_argument("reason", nargs="?", default=None, help="Failure reason")

    # coverage
    p_cov = subparsers.add_parser(
        "coverage", help="Evaluate statement test coverage for a module"
    )
    p_cov.add_argument("target", nargs="?", default=None, help="Target or module name")
    p_cov.add_argument("--impl", help="Path to implementation file")
    p_cov.add_argument("--test", help="Path to test file")
    p_cov.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.0,
        help="Minimum coverage percentage required to exit successfully",
    )
    p_cov.add_argument(
        "--update-log", help="Path to coverage log file to update"
    )
    p_cov.add_argument(
        "--max-spans",
        type=int,
        default=None,
        help="Maximum non-continuous spans to present",
    )
    p_cov.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output coverage metrics in JSON format",
    )

    args = parser.parse_args(raw_args)

    workspace_asm.__initialize__()
    control_asm.__initialize__()
    tools_asm.__initialize__()
    with enter_phase(agent_session.agent_session):
        if args.command == "commission":
            return run_commission(
                args.role,
                dir_scope=args.dir,
                repo_root=args.repo_root,
                custom_dest=args.dest,
            )
        elif args.command == "decommission":
            return run_decommission(
                args.target,
                dir_scope=args.dir,
                repo_root=args.repo_root,
                custom_dest=args.dest,
                force=args.force,
            )
        elif args.command in ("refresh-sys", "refresh_sys"):
            return run_refresh_sys(
                role_name=args.role,
                dir_scope=args.dir,
                repo_root=args.repo_root,
            )
        elif args.command == "get_work":
            return run_get_work(dir_scope=args.dir, force=args.force)
        elif args.command == "submit":
            return run_submit(args.target, summary=args.summary)
        elif args.command == "blame":
            return run_blame(args.culprit_file, args.critique)
        elif args.command == "fail":
            return run_fail(args.target, reason=args.reason)
        elif args.command == "coverage":
            return run_coverage(
                target=args.target,
                impl=args.impl,
                test=args.test,
                threshold=args.threshold,
                update_log=args.update_log,
                max_spans=args.max_spans,
                json_output=args.json_output,
            )

        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
