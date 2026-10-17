# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:15:00Z
# CHANGE: Implement workspace_dirtiness_impl
# CODE_HASH: a224534e93bf
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_dirtiness_impl."""

from __future__ import annotations

import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.storage.lib import src_metadata
from update_with_ai.parts.workspace.lib import workspace_registry
from . import workspace_dirtiness

# Contract: Cache mapping unit names to their part directory within a repo root.
_UNIT_PART_MAP_CACHE: Dict[str, Dict[str, str]] = {}


# Contract: Classifies unit type by suffix (_ext, _asm, _impl, interface).
def _classify_unit_type(unit_name: str) -> str:
    if unit_name.endswith("_ext"):
        return "external"
    if unit_name.endswith("_asm"):
        return "assembly"
    if unit_name.endswith("_impl"):
        return "implementation"
    return "interface"


# Contract: Checks whether role is an auditor role based on audit_tag or absence of src_pattern.
def _is_auditor_role(role_name: str, repo_root: Optional[str] = None) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(r_def.audit_tag or not r_def.src_pattern)


# Contract: Parses high-level markdown specifications to extract unit names and dependencies.
def _get_part_units(repo_root: str, part_dir: str) -> Dict[str, List[str]]:
    high_dir = os.path.join(repo_root, part_dir, "high")
    if os.path.isdir(high_dir):
        units: Dict[str, List[str]] = {}
        for fname in sorted(os.listdir(high_dir)):
            if not fname.endswith(".md") or fname.startswith(".") or fname == "__init__.md":
                continue
            unit_name = fname[:-3]
            deps: List[str] = []
            try:
                with open(os.path.join(high_dir, fname), "r", encoding="utf-8") as f:
                    for line in f:
                        s = line.strip()
                        for pfx in ("imports:", "implements:", "assembles:"):
                            if s.startswith(pfx):
                                deps.extend(x.strip() for x in s[len(pfx) :].split(",") if x.strip())
                        if s.startswith("## "):
                            break
            except (OSError, UnicodeDecodeError):
                pass
            seen: Set[str] = set()
            ordered: List[str] = []
            for d in deps:
                if d and d not in seen:
                    seen.add(d)
                    ordered.append(d)
            units[unit_name] = ordered
        if units:
            return units

    full_part = os.path.join(repo_root, part_dir)
    if os.path.isdir(full_part):
        stems: Set[str] = set()
        for sub in os.listdir(full_part):
            sub_path = os.path.join(full_part, sub)
            if os.path.isdir(sub_path) and not sub.startswith("."):
                for sf in os.listdir(sub_path):
                    if not sf.startswith(".") and sf.endswith((".py", ".pyi", ".md")):
                        stems.add(os.path.splitext(sf)[0])
        return {stem: [] for stem in sorted(stems) if stem != "__init__"}
    return {}


# Contract: Discovers part directories within repository or directory scope.
def _find_part_dirs_in_scope(repo_root: str, dir_scope: str = "") -> List[str]:
    if not dir_scope:
        parts_p = os.path.join(repo_root, "parts")
        if os.path.isdir(parts_p):
            return [
                os.path.join("parts", d)
                for d in sorted(os.listdir(parts_p))
                if os.path.isdir(os.path.join(parts_p, d)) and not d.startswith(".")
            ]
        return []
    scope_p = os.path.join(repo_root, dir_scope)
    parts_p = os.path.join(scope_p, "parts")
    if os.path.isdir(parts_p):
        return [
            os.path.join(dir_scope, "parts", d)
            for d in sorted(os.listdir(parts_p))
            if os.path.isdir(os.path.join(parts_p, d)) and not d.startswith(".")
        ]
    return [dir_scope] if os.path.isdir(scope_p) else []


# Contract: Checks if a relative path matches any glob pattern.
def _matches_any_pattern(rel_path: str, patterns: Sequence[str]) -> bool:
    normalized = rel_path.replace("\\", "/")
    fname = os.path.basename(normalized)
    return any(
        fnmatch.fnmatch(normalized, p)
        or fnmatch.fnmatch(normalized, f"*/{p}")
        or fnmatch.fnmatch(fname, p)
        for p in patterns
    )


# Contract: Builds or retrieves cached map of unit names to part directories.
def _unit_part_map(repo_root: str) -> Dict[str, str]:
    cached = _UNIT_PART_MAP_CACHE.get(repo_root)
    if cached is not None:
        return cached
    mapping: Dict[str, str] = {}
    if os.path.isdir(repo_root):
        for pd in _find_part_dirs_in_scope(repo_root, ""):
            for declared_unit in _get_part_units(repo_root, pd):
                mapping.setdefault(declared_unit, pd)
    _UNIT_PART_MAP_CACHE[repo_root] = mapping
    return mapping


# Contract: Parses a dependency label into (package_dir, unit_name).
def _parse_dependency_label(raw: str, default_pkg: str) -> Tuple[str, str]:
    if raw.startswith("//"):
        label = raw.lstrip("/")
        pkg, sep, dep_unit = label.partition(":")
        return pkg, dep_unit if sep else os.path.basename(pkg)
    return default_pkg, raw.lstrip(":").strip()


# Contract: Resolves declared cross-unit dependencies of a unit into (part_dir, unit_name) pairs.
def _cross_unit_dependencies(
    repo_root: str, part_dir: str, unit_name: str
) -> List[Tuple[str, str]]:
    raw_deps = _get_part_units(repo_root, part_dir).get(unit_name, [])
    if not raw_deps:
        return []

    unit_parts: Dict[str, str] = {}
    if any(not raw.startswith("//") for raw in raw_deps):
        unit_parts = _unit_part_map(repo_root)

    deps: List[Tuple[str, str]] = []
    for raw in raw_deps:
        dep_part, dep_unit = _parse_dependency_label(raw, part_dir)
        if not raw.startswith("//"):
            dep_part = unit_parts.get(dep_unit, part_dir)
        if dep_unit:
            deps.append((dep_part, dep_unit))
    return deps


# Contract: Parses pattern format string into directory name, prefix, and suffix.
def _parse_pattern_info(src_pattern: str) -> Tuple[str, str, str]:
    if not src_pattern:
        return "", "", ""
    clean = src_pattern.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
    dir_name, file_pattern = clean.split("/", 1) if "/" in clean else ("", clean)
    if "{unit_name}" in file_pattern:
        prefix, suffix = file_pattern.split("{unit_name}", 1)
    elif "*" in file_pattern:
        prefix, suffix = file_pattern.split("*", 1)
    else:
        prefix, suffix = "", file_pattern
    return dir_name, prefix, suffix


# Contract: Discovers role matching a file path based on directory and file patterns.
def _resolve_file_role(file_path: str, repo_root: Optional[str] = None) -> str:
    norm = file_path.replace("\\", "/")
    fname, parent = os.path.basename(norm), os.path.basename(os.path.dirname(norm))
    try:
        reg = get_singleton(workspace_registry.WorkspaceRegistry)
        for role in reg.list_roles(repo_root=repo_root):
            if not role.src_pattern:
                continue
            d_name, pfx, sfx = _parse_pattern_info(role.src_pattern)
            if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
                return role.role_name
    except (LifecycleResolutionError, LookupError):
        pass
    raise ValueError(f"Unrecognized role for file path: {file_path}")


# Contract: Resolves part directory, unit name, and role name from file path.
def _parse_unit_from_file_path(file_path: str, repo_root: str) -> Tuple[str, str, str]:
    norm_path, norm_root = os.path.realpath(file_path), os.path.realpath(repo_root)
    rel = (
        os.path.relpath(norm_path, norm_root).replace("\\", "/")
        if norm_path.startswith(norm_root)
        else file_path.replace("\\", "/")
    )
    fname, role_name = os.path.basename(rel), _resolve_file_role(rel, repo_root=repo_root)
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    role_def = reg.resolve_role_definition(role_name, repo_root=repo_root)
    _, pfx, sfx = _parse_pattern_info(role_def.src_pattern)
    unit_name = fname
    if pfx and unit_name.startswith(pfx):
        unit_name = unit_name[len(pfx) :]
    if sfx and unit_name.endswith(sfx):
        unit_name = unit_name[: -len(sfx)]
    return os.path.dirname(os.path.dirname(rel)), unit_name, role_name



# Contract: Discovers existing companion specification contracts and interface definitions for target.
# Suffix heuristic stripping '_impl' to expand interface companion contracts for implementation units.
def _get_unit_contract_files(
    target_file: str,
    ws_root: str,
    main_root: Optional[str] = None,
    role_name: Optional[str] = None,
) -> List[str]:
    full_target = (
        os.path.join(ws_root, target_file)
        if not os.path.isabs(target_file)
        else target_file
    )
    part_dir, unit_name, resolved_role = _parse_unit_from_file_path(
        full_target, ws_root
    )
    clean_role = (role_name or resolved_role).split(":")[-1].strip().lower()
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    role_def = reg.resolve_role_definition(clean_role, repo_root=ws_root)

    m_root = main_root or ws_root
    roots = [ws_root]
    if m_root and os.path.realpath(m_root) != os.path.realpath(ws_root):
        roots.append(m_root)

    candidates: List[str] = []
    is_impl = unit_name.endswith("_impl")
    interface_stem = unit_name[:-5] if is_impl else unit_name

    dep_roles = [d.split(":")[-1] for d in role_def.role_deps]
    for d in list(role_def.feedback_role_deps) + list(role_def.star_role_deps):
        clean_d = d.split(":")[-1]
        if clean_d not in dep_roles:
            dep_roles.append(clean_d)

    for up_r in dep_roles:
        up_def = reg.resolve_role_definition(up_r, repo_root=ws_root)
        if up_def.src_pattern:
            for stem in ([unit_name, interface_stem] if is_impl else [unit_name]):
                c = up_def.src_pattern.format(unit_dir=part_dir, unit_name=stem)
                if c not in candidates:
                    candidates.append(c)

    if is_impl and role_def.src_pattern:
        clean_star_deps = [d.split(":")[-1] for d in role_def.star_role_deps]
        if clean_role in clean_star_deps:
            iface_c = role_def.src_pattern.format(
                unit_dir=part_dir, unit_name=interface_stem
            )
            if iface_c not in candidates:
                candidates.append(iface_c)

    silent_cross_roles = [d.split(":")[-1] for d in role_def.silent_cross_role_deps]
    for dep_part, dep_unit in _cross_unit_dependencies(m_root, part_dir, unit_name):
        for star_r in (d.split(":")[-1] for d in role_def.star_role_deps):
            if star_r in silent_cross_roles:
                continue
            star_def = reg.resolve_role_definition(star_r, repo_root=ws_root)
            if not star_def.src_pattern:
                continue
            stems = [dep_unit, dep_unit[:-5]] if dep_unit.endswith("_impl") else [dep_unit]
            for s in stems:
                dep_cand = star_def.src_pattern.format(unit_dir=dep_part, unit_name=s)
                if dep_cand not in candidates:
                    candidates.append(dep_cand)

    suppressed_patterns: List[str] = []
    for silent_r in silent_cross_roles:
        silent_def = reg.resolve_role_definition(silent_r, repo_root=ws_root)
        suppressed_patterns.extend(silent_def.writable_file_patterns)
    if suppressed_patterns:
        candidates = [
            c for c in candidates if not _matches_any_pattern(c, suppressed_patterns)
        ]

    existing: List[str] = []
    norm_target = target_file.replace("\\", "/").lstrip("/")
    for c in candidates:
        norm_c = c.replace("\\", "/").lstrip("/")
        if norm_c != norm_target and norm_c not in existing:
            if any(os.path.isfile(os.path.join(r, norm_c)) for r in roots):
                existing.append(norm_c)
    return existing


# Contract: Resolves file path across workspace root and main root.
def _resolve_scope_file(
    rel_path: str,
    ws_root: str,
    main_root: str,
) -> Optional[str]:
    for root in (ws_root, main_root) if main_root != ws_root else (ws_root,):
        cand = os.path.join(root, rel_path)
        if os.path.isfile(cand):
            return cand
    return None


# Contract: Checks if file's LAST_CHANGED timestamp in metadata is after reference timestamp.
def _is_modified_after(file_path: str, ref_timestamp: str) -> Optional[str]:
    d_meta = src_metadata.extract_metadata(file_path)
    if d_meta and d_meta.last_changed and ref_timestamp < d_meta.last_changed:
        return d_meta.last_changed
    return None


# Contract: Traverses upstream role dependency chain.
def _get_role_upstream_chain(
    role_name: str, repo_root: Optional[str] = None
) -> List[str]:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    visited: Set[str] = set()
    order: List[str] = []

    def visit(r: str) -> None:
        if r in visited:
            return
        visited.add(r)
        try:
            r_def = reg.resolve_role_definition(r, repo_root=repo_root)
            all_deps = list(r_def.role_deps) + list(r_def.star_role_deps)
            for d in all_deps:
                visit(d.split(":")[-1].strip().lower())
        except (LifecycleResolutionError, LookupError):
            pass
        if r not in order:
            order.append(r)

    visit(clean_r)
    return [r for r in order if r != clean_r]


# Contract: Evaluates whether a unit is dirty across auditor and producer role specifications.
def _eval_unit_dirty_internal(
    ws_root: str,
    part_dir: str,
    unit_name: str,
    eval_role: str,
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    clean_role = eval_role.split(":")[-1].strip().lower()
    main_root = repo_root or ws_root
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    role_def = reg.resolve_role_definition(clean_role, repo_root=main_root)

    active_types = role_def.active_component_types
    if active_types and _classify_unit_type(unit_name) not in active_types:
        return {"is_dirty": False, "reasons": []}

    reasons: List[str] = []

    if _is_auditor_role(clean_role, repo_root=main_root):
        audit_tag = role_def.audit_tag or f"{clean_role.upper()}_AUDIT"
        fb_deps = [d.split(":")[-1] for d in role_def.feedback_role_deps]
        if not fb_deps:
            return {"is_dirty": False, "reasons": []}

        ctype = _classify_unit_type(unit_name)
        fb_dep_set = set(fb_deps)
        silent_deps = set(d.split(":")[-1] for d in role_def.silent_role_deps)
        contract_dep_roles: List[str] = []
        for d_lbl in list(role_def.role_deps) + list(role_def.star_role_deps):
            clean_d = d_lbl.split(":")[-1]
            if clean_d not in fb_dep_set and clean_d not in silent_deps and clean_d not in contract_dep_roles:
                contract_dep_roles.append(clean_d)

        audited_targets_count = 0
        for fb_role in fb_deps:
            fb_def = reg.resolve_role_definition(fb_role, repo_root=main_root)
            if fb_def.active_component_types and ctype not in fb_def.active_component_types:
                continue
            fb_pat = fb_def.src_pattern
            if not fb_pat:
                continue
            audited_targets_count += 1
            fb_rel = fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
            fb_full = _resolve_scope_file(fb_rel, ws_root, main_root)
            if not fb_full:
                reasons.append(f"Audited target {fb_rel} does not exist")
                continue
            fb_meta = src_metadata.extract_metadata(fb_full)
            if fb_meta is None or not fb_meta.last_changed:
                reasons.append(
                    f"Target {fb_rel} missing valid in-band metadata header"
                )
                continue
            if fb_meta.feedback:
                for fb in fb_meta.feedback:
                    reasons.append(f"Unacted feedback in {fb_rel}: {fb}")
            audit_ts = fb_meta.audits.get(audit_tag)
            if not audit_ts:
                reasons.append(
                    f"Target {fb_rel} has not been certified with {audit_tag}"
                )
            elif audit_ts < fb_meta.last_changed:
                reasons.append(
                    f"Target {fb_rel} modified ({fb_meta.last_changed}) after {audit_tag} ({audit_ts})"
                )
            else:
                for c_name in contract_dep_roles:
                    c_def = reg.resolve_role_definition(c_name, repo_root=main_root)
                    if c_def.active_component_types and ctype not in c_def.active_component_types:
                        continue
                    if not c_def.src_pattern:
                        continue
                    c_rel = c_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name)
                    c_full = _resolve_scope_file(c_rel, ws_root, main_root)
                    if c_full:
                        last_ch = _is_modified_after(c_full, audit_ts)
                        if last_ch:
                            reasons.append(
                                f"Upstream contract {c_rel} modified ({last_ch}) after {audit_tag} ({audit_ts}) on {fb_rel}"
                            )

        if audited_targets_count == 0:
            return {"is_dirty": False, "reasons": []}
        return {"is_dirty": bool(reasons), "reasons": reasons}

    # Producer role evaluation
    active_pat = role_def.src_pattern
    if not active_pat:
        return {"is_dirty": False, "reasons": []}
    target_rel = active_pat.format(unit_dir=part_dir, unit_name=unit_name)
    full_path = _resolve_scope_file(target_rel, ws_root, main_root)
    if not full_path:
        return {
            "is_dirty": True,
            "reasons": [f"Source file {target_rel} does not exist"],
        }
    meta = src_metadata.extract_metadata(full_path)
    if not meta or not meta.last_cleaned:
        return {
            "is_dirty": True,
            "reasons": [f"Header missing LAST_CLEANED in {target_rel}"],
        }
    if meta.dirty:
        reasons.append(f"Target explicitly marked DIRTY: {meta.dirty}")
    if meta.feedback:
        for fb in meta.feedback:
            clean_fb = re.sub(r"^\[.*?\]:\s*", "", fb.strip())
            reasons.append(f"Unacted feedback in {target_rel}: {clean_fb}")

    ctype = _classify_unit_type(unit_name)
    is_impl = unit_name.endswith("_impl")
    interface_stem = unit_name[:-5] if is_impl else unit_name

    dep_role_labels = [d.split(":")[-1] for d in role_def.role_deps]
    for d in list(role_def.feedback_role_deps) + list(role_def.star_role_deps):
        clean_d = d.split(":")[-1]
        if clean_d not in dep_role_labels:
            dep_role_labels.append(clean_d)

    effective_dep_roles: List[str] = []
    for d_name in dep_role_labels:
        if d_name == clean_role:
            continue
        d_def = reg.resolve_role_definition(d_name, repo_root=main_root)
        if d_def.active_component_types and ctype not in d_def.active_component_types:
            chain = _get_role_upstream_chain(d_name, repo_root=main_root)
            for anc in reversed(chain):
                anc_def = reg.resolve_role_definition(anc, repo_root=main_root)
                if not anc_def.active_component_types or ctype in anc_def.active_component_types:
                    if anc not in effective_dep_roles:
                        effective_dep_roles.append(anc)
                    break
        else:
            if d_name not in effective_dep_roles:
                effective_dep_roles.append(d_name)

    for d_name in effective_dep_roles:
        d_def = reg.resolve_role_definition(d_name, repo_root=main_root)
        d_pat = d_def.src_pattern
        if not d_pat:
            continue
        d_rel = d_pat.format(unit_dir=part_dir, unit_name=unit_name)
        d_full = _resolve_scope_file(d_rel, ws_root, main_root)
        if d_full:
            last_ch = _is_modified_after(d_full, meta.last_cleaned)
            if last_ch:
                reasons.append(
                    f"Upstream contract {d_rel} modified ({last_ch}) after local LAST_CLEANED ({meta.last_cleaned})"
                )
        if is_impl:
            d_iface_rel = d_pat.format(unit_dir=part_dir, unit_name=interface_stem)
            if d_iface_rel != d_rel:
                d_iface_full = _resolve_scope_file(d_iface_rel, ws_root, main_root)
                if d_iface_full:
                    last_ch = _is_modified_after(d_iface_full, meta.last_cleaned)
                    if last_ch:
                        reasons.append(
                            f"Upstream contract {d_iface_rel} modified ({last_ch}) after local LAST_CLEANED ({meta.last_cleaned})"
                        )

    star_roles = [d.split(":")[-1] for d in role_def.star_role_deps]
    if star_roles:
        part_units = _get_part_units(main_root, part_dir)
        unit_deps = list(part_units.get(unit_name, []))
        if is_impl and interface_stem not in unit_deps and interface_stem != unit_name:
            unit_deps.insert(0, interface_stem)

        for star_r in star_roles:
            star_def = reg.resolve_role_definition(star_r, repo_root=main_root)
            star_pat = star_def.src_pattern
            if not star_pat:
                continue

            if is_impl:
                s_iface_rel = star_pat.format(unit_dir=part_dir, unit_name=interface_stem)
                if s_iface_rel != target_rel:
                    s_iface_full = _resolve_scope_file(s_iface_rel, ws_root, main_root)
                    if s_iface_full:
                        last_ch = _is_modified_after(s_iface_full, meta.last_cleaned)
                        if last_ch:
                            reason_msg = f"Star dependency {s_iface_rel} modified ({last_ch}) after local LAST_CLEANED ({meta.last_cleaned})"
                            if reason_msg not in reasons:
                                reasons.append(reason_msg)

            for dep in unit_deps:
                dep_pkg, dep_u = _parse_dependency_label(dep, part_dir)
                for cand_u in [dep_u, dep_u[:-5] if dep_u.endswith("_impl") else None]:
                    if not cand_u:
                        continue
                    s_dep_rel = star_pat.format(unit_dir=dep_pkg, unit_name=cand_u)
                    if s_dep_rel == target_rel:
                        continue
                    s_dep_full = _resolve_scope_file(s_dep_rel, ws_root, main_root)
                    if s_dep_full:
                        last_ch = _is_modified_after(s_dep_full, meta.last_cleaned)
                        if last_ch:
                            reason_msg = f"Star dependency {s_dep_rel} modified ({last_ch}) after local LAST_CLEANED ({meta.last_cleaned})"
                            if reason_msg not in reasons:
                                reasons.append(reason_msg)
                            break
    return {"is_dirty": bool(reasons), "reasons": reasons}


# Contract: Realizes workspace_dirtiness.WorkspaceDirtinessEvaluator in agent_session tier.
class WorkspaceDirtinessEvaluator:
    """Evaluates unit dirtiness, resolves companion contracts, and extracts cross-unit dependencies."""

    # Contract: Evaluates whether a unit is dirty in directory scope and returns dirty status and reasons.
    def evaluate_unit_dirty(
        self,
        ws_root: str,
        part_dir: str,
        unit_name: str,
        eval_role: str,
        repo_root: Optional[str] = None,
    ) -> workspace_dirtiness.UnitDirtinessResult:
        res = _eval_unit_dirty_internal(
            ws_root, part_dir, unit_name, eval_role, repo_root
        )
        return workspace_dirtiness.UnitDirtinessResult(
            is_dirty=bool(res.get("is_dirty", False)),
            dirtiness_reasons=tuple(res.get("reasons", ())),
        )

    # Contract: Discovers existing companion specification contracts and interface definitions for target.
    def resolve_contract_files(
        self,
        target_file: str,
        ws_root: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        return _get_unit_contract_files(
            target_file, ws_root, main_root, role_name
        )

    # Contract: Resolves declared cross-unit dependencies of a unit to (part_dir, unit_name) pairs.
    def extract_cross_unit_dependencies(
        self,
        repo_root: str,
        part_dir: str,
        unit_name: str,
    ) -> Sequence[Tuple[str, str]]:
        return _cross_unit_dependencies(repo_root, part_dir, unit_name)



# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceDirtinessEvaluator,
        keys=[
            workspace_dirtiness.WorkspaceDirtinessEvaluator,
            WorkspaceDirtinessEvaluator,
        ],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
