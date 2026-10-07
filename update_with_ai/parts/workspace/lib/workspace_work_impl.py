# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: implement pending target tracking and role work queue evaluation
# CODE_HASH: c123a278fab6
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_work_impl."""

from __future__ import annotations

import ast
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import control_work_scheduler, src_metadata
from . import workspace_registry, workspace_work

PENDING_WORK_FILE = ".cleanroom_pending_work.json"


def _classify_unit_type(unit_name: str) -> str:
    if unit_name.endswith("_ext"):
        return "external"
    if unit_name.endswith("_asm"):
        return "assembly"
    if unit_name.endswith("_impl"):
        return "implementation"
    return "interface"


def _is_auditor_role(role_name: str, repo_root: Optional[str] = None) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(r_def.audit_tag or not r_def.src_pattern)


def _parse_part_units(pkg_build_path: str) -> Dict[str, List[str]]:
    if not os.path.isfile(pkg_build_path):
        return {}
    try:
        with open(pkg_build_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=pkg_build_path)
    except (OSError, SyntaxError):
        return {}

    units: Dict[str, List[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            func_name = call.func.id if isinstance(call.func, ast.Name) else ""
            if func_name in ("update_python_with_ai", "update_with_ai"):
                name: Optional[str] = None
                deps: List[str] = []
                for kw in call.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = str(kw.value.value)
                    elif kw.arg in ("module_deps", "unit_deps") and isinstance(
                        kw.value, (ast.List, ast.Tuple)
                    ):
                        for elt in kw.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                deps.append(elt.value)
                if (
                    name is None
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                ):
                    name = str(call.args[0].value)
                if name:
                    units[name] = deps
    return units


def _find_part_dirs_in_scope(repo_root: str, dir_scope: str) -> List[str]:
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


def _parse_pattern_info(src_pattern: str) -> Tuple[str, str, str]:
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


def _resolve_file_role(file_path: str, repo_root: Optional[str] = None) -> str:
    norm = file_path.replace("\\", "/")
    fname = os.path.basename(norm)
    parent = os.path.basename(os.path.dirname(norm))
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    for role in reg.list_roles(repo_root=repo_root):
        if not role.src_pattern:
            continue
        d_name, pfx, sfx = _parse_pattern_info(role.src_pattern)
        if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
            return role.role_name
    raise ValueError(f"Unrecognized role for file path: {file_path}")


def _parse_unit_from_file_path(file_path: str, repo_root: str) -> Tuple[str, str, str]:
    norm_path = os.path.realpath(file_path)
    norm_root = os.path.realpath(repo_root)
    rel = (
        os.path.relpath(norm_path, norm_root).replace("\\", "/")
        if norm_path.startswith(norm_root)
        else file_path.replace("\\", "/")
    )
    fname = os.path.basename(rel)
    role_name = _resolve_file_role(rel, repo_root=repo_root)
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    role_def = reg.resolve_role_definition(role_name, repo_root=repo_root)
    _, pfx, sfx = _parse_pattern_info(role_def.src_pattern)
    unit_name = fname
    if pfx and unit_name.startswith(pfx):
        unit_name = unit_name[len(pfx) :]
    if sfx and unit_name.endswith(sfx):
        unit_name = unit_name[: -len(sfx)]
    part_dir = os.path.dirname(os.path.dirname(rel))
    return part_dir, unit_name, role_name


def get_unit_contract_files(
    target_file: str,
    ws_root: str,
    main_root: Optional[str] = None,
    role_name: Optional[str] = None,
) -> List[str]:
    """Discovers existing companion specification contracts and interface definitions for target."""
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
    if not role_def.src_pattern or role_def.audit_tag:
        dep_roles.extend([d.split(":")[-1] for d in role_def.feedback_role_deps])
        dep_roles.extend([d.split(":")[-1] for d in role_def.star_role_deps])

    for up_r in dep_roles:
        up_def = reg.resolve_role_definition(up_r, repo_root=ws_root)
        if not up_def.src_pattern:
            continue
        c1 = up_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name)
        if c1 not in candidates:
            candidates.append(c1)
        if is_impl:
            c2 = up_def.src_pattern.format(unit_dir=part_dir, unit_name=interface_stem)
            if c2 not in candidates:
                candidates.append(c2)

    if is_impl and role_def.src_pattern:
        if clean_role == "low":
            iface_c = role_def.src_pattern.format(
                unit_dir=part_dir, unit_name=interface_stem
            )
            if iface_c not in candidates:
                candidates.append(iface_c)
        elif clean_role == "test":
            cand_impl = f"{part_dir}/lib/{unit_name}.py"
            if cand_impl not in candidates:
                candidates.append(cand_impl)

    existing: List[str] = []
    norm_target = target_file.replace("\\", "/").lstrip("/")
    for c in candidates:
        norm_c = c.replace("\\", "/").lstrip("/")
        if norm_c == norm_target:
            continue
        if norm_c in existing:
            continue
        for r in roots:
            if os.path.isfile(os.path.join(r, norm_c)):
                existing.append(norm_c)
                break
    return existing


def _eval_unit_dirty(
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
    curr_ws = os.getcwd()
    curr_role = ""
    meta_p = os.path.join(curr_ws, ".cleanroom_role.json")
    if os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            curr_role = str(
                meta_data.get("role_name") or meta_data.get("role") or ""
            ).split(":")[-1].strip().lower()
        except Exception:
            pass

    if _is_auditor_role(clean_role, repo_root=main_root):
        audit_tag = role_def.audit_tag or f"{clean_role.upper()}_AUDIT"
        fb_deps = [d.split(":")[-1] for d in role_def.feedback_role_deps]
        if not fb_deps:
            return {"is_dirty": False, "reasons": []}
        primary_fb = fb_deps[0]
        fb_def = reg.resolve_role_definition(primary_fb, repo_root=main_root)
        fb_pat = fb_def.src_pattern
        if not fb_pat:
            return {"is_dirty": False, "reasons": []}
        primary_rel = fb_pat.format(unit_dir=part_dir, unit_name=unit_name)
        primary_full = os.path.join(ws_root, primary_rel)
        if curr_ws and curr_role == clean_role:
            local_p = os.path.join(curr_ws, primary_rel)
            if os.path.isfile(local_p):
                primary_full = local_p
        if not os.path.isfile(primary_full) and main_root != ws_root:
            primary_full = os.path.join(main_root, primary_rel)
        if not os.path.isfile(primary_full):
            return {
                "is_dirty": True,
                "reasons": [f"Audited target {primary_rel} does not exist"],
            }
        primary_meta = src_metadata.extract_metadata(primary_full)
        if primary_meta is None or not primary_meta.last_changed:
            return {
                "is_dirty": True,
                "reasons": [
                    f"Target {primary_rel} missing valid in-band metadata header"
                ],
            }
        audit_ts = primary_meta.audits.get(audit_tag)
        if not audit_ts:
            reasons.append(
                f"Target {primary_rel} has not been certified with {audit_tag}"
            )
        elif audit_ts < primary_meta.last_changed:
            reasons.append(
                f"Target {primary_rel} modified ({primary_meta.last_changed}) after {audit_tag} ({audit_ts})"
            )
        return {"is_dirty": bool(reasons), "reasons": reasons}

    # Producer role evaluation
    active_pat = role_def.src_pattern
    if not active_pat:
        return {"is_dirty": False, "reasons": []}
    target_rel = active_pat.format(unit_dir=part_dir, unit_name=unit_name)
    full_path = os.path.join(ws_root, target_rel)
    if curr_ws and curr_role == clean_role:
        local_t = os.path.join(curr_ws, target_rel)
        if os.path.isfile(local_t):
            full_path = local_t
    if not os.path.isfile(full_path) and main_root != ws_root:
        full_path = os.path.join(main_root, target_rel)
    if not os.path.isfile(full_path):
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
            reasons.append(f"Unacted feedback in {target_rel}: {fb}")

    # Forward dependency timestamp comparison
    dep_role_labels = [d.split(":")[-1] for d in role_def.role_deps]
    for d_name in dep_role_labels:
        if d_name == clean_role:
            continue
        d_def = reg.resolve_role_definition(d_name, repo_root=main_root)
        d_pat = d_def.src_pattern
        if not d_pat:
            continue
        d_rel = d_pat.format(unit_dir=part_dir, unit_name=unit_name)
        d_full = os.path.join(ws_root, d_rel)
        if not os.path.isfile(d_full) and main_root != ws_root:
            d_full = os.path.join(main_root, d_rel)
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


def _find_all_dirty_in_scope(
    repo_root: str, dir_scope: str = "staging", role_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    part_dirs = _find_part_dirs_in_scope(repo_root, dir_scope)
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    if role_filter:
        clean_filter = role_filter.split(":")[-1].strip().lower()
        target_roles = [reg.resolve_role_definition(clean_filter, repo_root=repo_root)]
    else:
        target_roles = list(reg.list_roles(repo_root=repo_root))
    dirty_units: List[Dict[str, Any]] = []

    for part_dir in part_dirs:
        build_file = os.path.join(repo_root, part_dir, "BUILD.bazel")
        units = _parse_part_units(build_file) if os.path.isfile(build_file) else {}
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
            ctype = _classify_unit_type(unit_name)
            for r_def in target_roles:
                if (
                    r_def.active_component_types
                    and ctype not in r_def.active_component_types
                ):
                    continue
                r_name = r_def.role_name
                eval_res = _eval_unit_dirty(
                    repo_root, part_dir, unit_name, r_name, repo_root
                )
                if eval_res["is_dirty"]:
                    src_pat = r_def.src_pattern
                    if src_pat:
                        target_file = src_pat.format(
                            unit_dir=part_dir, unit_name=unit_name
                        )
                    else:
                        fb_deps = [d.split(":")[-1] for d in r_def.feedback_role_deps]
                        if fb_deps:
                            fb_def = reg.resolve_role_definition(
                                fb_deps[0], repo_root=repo_root
                            )
                            fb_pat = fb_def.src_pattern
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
                            "dirtiness_reasons": eval_res.get(
                                "reasons", ["In-band metadata dirty"]
                            ),
                        }
                    )
    return dirty_units


def _topological_sort_units(
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


def _get_role_upstream_chain(
    role_name: str, repo_root: Optional[str] = None
) -> List[str]:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    visited: Set[str] = set()
    order: List[str] = []

    def dfs(r: str) -> None:
        r_def = reg.resolve_role_definition(r, repo_root=repo_root)
        dep_labels = list(r_def.role_deps) + list(r_def.feedback_role_deps)
        for d in dep_labels:
            d_name = d.split(":")[-1]
            if d_name != r and d_name not in visited:
                visited.add(d_name)
                dfs(d_name)
                order.append(d_name)

    dfs(clean_r)
    return order


class WorkspaceWorkManager(
    workspace_work.WorkspaceWorkManager,
    Singleton,
):
    """Realizes work discovery across directory scopes and pending buffer tracking."""

    tier = agent_session.agent_session

    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        if not os.path.isfile(p):
            return ()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return list(data.get("targets", []))
            elif isinstance(data, list):
                return list(data)
        except Exception:
            return ()
        return ()

    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        if not targets:
            self.clear_pending_work(workspace_dir)
            return
        os.makedirs(workspace_dir, exist_ok=True)
        if os.path.exists(p):
            try:
                os.chmod(p, 0o644)
            except OSError:
                pass
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "assigned_at": src_metadata.current_utc_timestamp(),
                        "targets": list(targets),
                    },
                    f,
                    indent=2,
                )
                f.write("\n")
            try:
                os.chmod(p, 0o644)
            except OSError:
                pass
        except OSError:
            pass

    def clear_pending_work(self, workspace_dir: str) -> None:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass

    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        targets = list(self.get_pending_work(workspace_dir))
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
            remaining = []
        self.set_pending_work(workspace_dir, remaining)

    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        full_ws = os.path.join(workspace_dir, target_path) if not os.path.isabs(target_path) else target_path
        part_dir, unit_name, r_name = _parse_unit_from_file_path(full_ws, workspace_dir)
        eval_role = (role_name or r_name).split(":")[-1].strip().lower()
        m_root = main_root or workspace_dir
        if not _is_auditor_role(eval_role, repo_root=m_root):
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
        res = _eval_unit_dirty(workspace_dir, part_dir, unit_name, eval_role, m_root)
        return res.get("is_dirty", False)

    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
    ) -> Tuple[Sequence[workspace_work.WorkQueueItem], Sequence[workspace_work.WorkQueueItem]]:
        clean_role = role_name.split(":")[-1].strip().lower()
        part_dirs = _find_part_dirs_in_scope(repo_root, dir_scope)
        all_units: Dict[str, str] = {}
        module_deps: Dict[str, List[str]] = {}
        raw_module_deps: Dict[str, List[str]] = {}

        for pd in part_dirs:
            bf = os.path.join(repo_root, pd, "BUILD.bazel")
            u_map = _parse_part_units(bf) if os.path.isfile(bf) else {}
            for uname, mdeps in u_map.items():
                all_units[uname] = pd
                raw_module_deps[uname] = list(mdeps)
                module_deps[uname] = [d.split(":")[-1] for d in mdeps]

        all_dirty = _find_all_dirty_in_scope(repo_root, dir_scope=dir_scope)
        dirty_lookup: Dict[Tuple[str, str], Dict[str, Any]] = {
            (item["unit_name"], item["role"]): item for item in all_dirty
        }

        reg = get_singleton(workspace_registry.WorkspaceRegistry)
        active_role_def = reg.resolve_role_definition(clean_role, repo_root=repo_root)
        upstream_roles = _get_role_upstream_chain(clean_role, repo_root=repo_root)
        is_auditor = _is_auditor_role(clean_role, repo_root=repo_root)
        feedback_roles = [
            d.split(":")[-1] for d in active_role_def.feedback_role_deps
        ]
        silent_cross = [
            d.split(":")[-1] for d in active_role_def.silent_cross_role_deps
        ]
        star_roles = [
            d.split(":")[-1] for d in active_role_def.star_role_deps
        ]

        dirty_in_role = [item for item in all_dirty if item["role"] == clean_role]
        if not dirty_in_role:
            return (), ()

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
                up_r_def = reg.resolve_role_definition(up_r, repo_root=repo_root)
                up_r_pat = up_r_def.src_pattern
                if up_r_pat and part_dir:
                    up_dir, _, _ = _parse_pattern_info(up_r_pat)
                    if not os.path.isdir(os.path.join(repo_root, part_dir, up_dir)):
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
                    r_check_def = reg.resolve_role_definition(r_check, repo_root=repo_root)
                    r_check_pat = r_check_def.src_pattern
                    if r_check_pat and dep_part:
                        r_dir, _, _ = _parse_pattern_info(r_check_pat)
                        if not os.path.isdir(os.path.join(repo_root, dep_part, r_dir)):
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

                for star_r in star_roles:
                    if star_r in silent_cross:
                        continue
                    star_def = reg.resolve_role_definition(star_r, repo_root=repo_root)
                    star_pat = star_def.src_pattern
                    if not star_pat:
                        continue
                    star_cand = star_pat.format(unit_dir=dep_pkg, unit_name=dep_u)
                    if os.path.isfile(os.path.join(repo_root, star_cand)):
                        if star_cand not in dep_files:
                            dep_files.append(star_cand)
                    elif dep_u.endswith("_impl"):
                        iface_cand = star_pat.format(unit_dir=dep_pkg, unit_name=dep_u[:-5])
                        if os.path.isfile(os.path.join(repo_root, iface_cand)):
                            if iface_cand not in dep_files:
                                dep_files.append(iface_cand)
                        elif star_cand not in dep_files:
                            dep_files.append(star_cand)
                    elif star_cand not in dep_files:
                        dep_files.append(star_cand)

            item["dependencies"] = dep_files

            if blocked_reasons:
                item["blocked_reasons"] = blocked_reasons
                blocked_candidates.append(item)
            else:
                ready_candidates.append(item)

        sorted_ready = _topological_sort_units(ready_candidates, module_deps)

        ready_items: List[workspace_work.WorkQueueItem] = [
            workspace_work.WorkQueueItem(
                target_file=item["target_file"],
                role_name=item["role"],
                dirtiness_reasons=item["reasons"],
                dependency_files=item.get("dependencies", []),
                is_ready=True,
                blocked_reasons=(),
                contract_files=get_unit_contract_files(
                    item["target_file"], repo_root, role_name=item["role"]
                ),
            )
            for item in sorted_ready
        ]
        blocked_items: List[workspace_work.WorkQueueItem] = [
            workspace_work.WorkQueueItem(
                target_file=item["target_file"],
                role_name=item["role"],
                dirtiness_reasons=item["reasons"],
                dependency_files=item.get("dependencies", []),
                is_ready=False,
                blocked_reasons=item.get("blocked_reasons", ()),
                contract_files=get_unit_contract_files(
                    item["target_file"], repo_root, role_name=item["role"]
                ),
            )
            for item in blocked_candidates
        ]
        return ready_items, blocked_items

    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
    ) -> workspace_work.WorkQueueSummary:
        clean_role = role_name.split(":")[-1].strip().lower()

        # Check pending work buffer
        if workspace_dir and not force:
            pending = self.get_pending_work(workspace_dir)
            if pending:
                still_dirty = [
                    pt
                    for pt in pending
                    if self.is_pending_target_dirty(pt, workspace_dir, role_name=clean_role)
                ]
                if still_dirty:
                    raise RuntimeError(
                        f"Pending dirty work remains in workspace: {', '.join(still_dirty)}"
                    )
                else:
                    self.clear_pending_work(workspace_dir)

        eval_root = workspace_dir or os.getcwd()
        meta_p = os.path.join(eval_root, ".cleanroom_role.json")
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                m_root = meta.get("main_workspace_root") or meta.get("repo_root")
                if m_root and os.path.isdir(m_root):
                    eval_root = os.path.realpath(m_root)
            except Exception:
                pass

        scheduler = None
        try:
            scheduler = get_singleton(control_work_scheduler.WorkScheduler)
        except Exception:
            pass

        if scheduler is not None:
            try:
                schedule = scheduler.schedule_work(dir_scope=dir_scope)
                if schedule is not None and schedule.tasks:
                    sched_ready: List[workspace_work.WorkQueueItem] = []
                    for task in schedule.tasks:
                        task_role = task.node.role_address.split(":")[-1].strip().lower()
                        if clean_role and task_role != clean_role:
                            continue
                        reasons = [m.content for m in task.feedback_messages] or ["target is dirty"]
                        target_file = str(task.node.unit_address)
                        sched_ready.append(
                            workspace_work.WorkQueueItem(
                                target_file=target_file,
                                role_name=task_role,
                                dirtiness_reasons=reasons,
                                dependency_files=task.dependency_paths,
                                is_ready=True,
                                blocked_reasons=(),
                                contract_files=get_unit_contract_files(
                                    target_file, eval_root, role_name=task_role
                                ),
                            )
                        )
                    if workspace_dir:
                        if sched_ready:
                            self.set_pending_work(workspace_dir, [item.target_file for item in sched_ready])
                        else:
                            self.clear_pending_work(workspace_dir)

                    is_clean = len(sched_ready) == 0
                    return workspace_work.WorkQueueSummary(
                        ready_items=sched_ready,
                        blocked_items=(),
                        is_clean=is_clean,
                    )
            except Exception:
                pass

        ready_items, blocked_items = self.compute_role_work_queue(
            clean_role, dir_scope, eval_root
        )

        if workspace_dir:
            if ready_items:
                self.set_pending_work(workspace_dir, [item.target_file for item in ready_items])
            else:
                self.clear_pending_work(workspace_dir)

        is_clean = len(ready_items) == 0 and len(blocked_items) == 0
        return workspace_work.WorkQueueSummary(
            ready_items=ready_items,
            blocked_items=blocked_items,
            is_clean=is_clean,
        )

    def resolve_contract_files(
        self,
        target_path: str,
        workspace_dir: str,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        return get_unit_contract_files(
            target_path, workspace_dir, role_name=role_name
        )
