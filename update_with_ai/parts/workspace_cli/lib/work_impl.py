"""Low-level implementation for work_impl."""

from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.control.lib import work_scheduler
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.workspace.lib import role_registry
from . import (
    dirtiness,
    pending,
    work,
)



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
    reg = get_singleton(role_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(r_def.audit_tag or not r_def.src_pattern)


def _get_part_units(repo_root: str, part_dir: str) -> Dict[str, List[str]]:
    # Contract: __orphan__ - MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
    high_dir = os.path.join(repo_root, part_dir, "high")
    if os.path.isdir(high_dir):
        units = {}
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


# Contract: __orphan__ - MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
get_part_units = _get_part_units


def _find_part_dirs_in_scope(repo_root: str, dir_scope: str = "") -> List[str]:
    if not dir_scope:
        parts_p = os.path.join(repo_root, "parts")
        if os.path.isdir(parts_p):
            return [os.path.join("parts", d) for d in sorted(os.listdir(parts_p)) if os.path.isdir(os.path.join(parts_p, d)) and not d.startswith(".")]
        return []
    scope_p = os.path.join(repo_root, dir_scope)
    parts_p = os.path.join(scope_p, "parts")
    if os.path.isdir(parts_p):
        return [os.path.join(dir_scope, "parts", d) for d in sorted(os.listdir(parts_p)) if os.path.isdir(os.path.join(parts_p, d)) and not d.startswith(".")]
    return [dir_scope] if os.path.isdir(scope_p) else []


def _parse_dependency_label(raw: str, default_pkg: str) -> Tuple[str, str]:
    """Parses a dependency label into (package_dir, unit_name)."""
    if raw.startswith("//"):
        label = raw.lstrip("/")
        pkg, sep, dep_unit = label.partition(":")
        return pkg, dep_unit if sep else os.path.basename(pkg)
    return default_pkg, raw.lstrip(":").strip()


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


def _materialize_starter_template(target_path: str, role_name_or_address: str, workspace_dir: str) -> None:
    storage = None
    try:
        storage = get_singleton(dag_storage.DagStorage)
    except (LifecycleResolutionError, LookupError, AttributeError):
        pass
    if storage is not None and hasattr(storage, "materialize_template"):
        node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(target_path),
            role_address=dag_storage.RoleAddress(role_name_or_address),
        )
        storage.materialize_template(node)



def _find_all_dirty_in_scope(
    repo_root: str, dir_scope: str = "", role_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    part_dirs = _find_part_dirs_in_scope(repo_root, dir_scope)
    reg = get_singleton(role_registry.WorkspaceRegistry)
    dirtiness_eval = get_singleton(dirtiness.WorkspaceDirtinessEvaluator)
    if role_filter:
        clean_filter = role_filter.split(":")[-1].strip().lower()
        target_roles = [reg.resolve_role_definition(clean_filter, repo_root=repo_root)]
    else:
        target_roles = list(reg.list_roles(repo_root=repo_root))
    dirty_units: List[Dict[str, Any]] = []

    for part_dir in part_dirs:
        units = _get_part_units(repo_root, part_dir)
        for unit_name in sorted(units.keys()):
            ctype = _classify_unit_type(unit_name)
            for r_def in target_roles:
                if (
                    r_def.active_component_types
                    and ctype not in r_def.active_component_types
                ):
                    continue
                r_name = r_def.role_name
                eval_res = dirtiness_eval.evaluate_unit_dirty(
                    repo_root, part_dir, unit_name, r_name, repo_root
                )
                if eval_res.is_dirty:
                    target_file = r_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name) if r_def.src_pattern else f"{part_dir}/{r_name}/{unit_name}"
                    if not r_def.src_pattern:
                        fb_deps = [d.split(":")[-1] for d in r_def.feedback_role_deps]
                        fb_def = reg.resolve_role_definition(fb_deps[0], repo_root=repo_root) if fb_deps else None
                        if fb_def and fb_def.src_pattern:
                            target_file = fb_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name)
                    dirty_units.append(
                        {
                            "unit_name": unit_name,
                            "part_dir": part_dir,
                            "role": r_name,
                            "target_file": target_file,
                            "reasons": list(eval_res.dirtiness_reasons) or ["In-band metadata dirty"],
                            "dirtiness_reasons": list(eval_res.dirtiness_reasons) or ["In-band metadata dirty"],
                        }
                    )
    return dirty_units


def _topological_sort_units(
    units_list: List[Dict[str, Any]],
    module_deps: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    unit_items: Dict[str, List[Dict[str, Any]]] = {}
    for item in units_list:
        unit_items.setdefault(item["unit_name"], []).append(item)
    visited: Set[str] = set()
    temp_mark: Set[str] = set()
    order: List[Dict[str, Any]] = []

    def visit(uname: str) -> None:
        if uname in visited or uname in temp_mark:
            return
        temp_mark.add(uname)
        for dep in sorted(module_deps.get(uname, [])):
            if dep in unit_items:
                visit(dep)
        temp_mark.remove(uname)
        visited.add(uname)
        order.extend(unit_items[uname])

    for item in sorted(units_list, key=lambda x: str(x.get("unit_name", ""))):
        uname = str(item.get("unit_name", ""))
        if uname not in visited:
            visit(uname)

    return order


def _get_role_upstream_chain(
    role_name: str, repo_root: Optional[str] = None
) -> List[str]:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(role_registry.WorkspaceRegistry)
    visited: Set[str] = set()
    order: List[str] = []

    def dfs(r: str) -> None:
        r_def = reg.resolve_role_definition(r, repo_root=repo_root)
        dep_labels = (
            list(r_def.role_deps)
            + list(r_def.feedback_role_deps)
            + list(r_def.star_role_deps)
            + list(r_def.silent_role_deps)
        )
        for d in dep_labels:
            d_name = d.split(":")[-1]
            if d_name != r and d_name not in visited:
                visited.add(d_name)
                dfs(d_name)
                order.append(d_name)

    dfs(clean_r)
    return order



# Contract: WorkspaceWorkManager realizes work discovery across directory scopes and pending buffer tracking in agent_session tier.
class WorkspaceWorkManager(work.WorkspaceWorkManager):
    """Realizes work discovery across directory scopes and pending buffer tracking."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def _pending(self) -> pending.WorkspacePendingManager:
        return get_singleton(pending.WorkspacePendingManager)

    def _dirtiness(self) -> dirtiness.WorkspaceDirtinessEvaluator:
        return get_singleton(dirtiness.WorkspaceDirtinessEvaluator)

    # Contract: Delegates reading pending target paths to WorkspacePendingManager.
    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        return self._pending().get_pending_work(workspace_dir)

    # Contract: Delegates recording pending target paths to WorkspacePendingManager.
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        self._pending().set_pending_work(workspace_dir, targets)

    # Contract: Delegates removing local pending work buffer to WorkspacePendingManager.
    def clear_pending_work(self, workspace_dir: str) -> None:
        self._pending().clear_pending_work(workspace_dir)

    # Contract: Delegates removing submitted target from pending buffer to WorkspacePendingManager.
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        self._pending().remove_pending_target(workspace_dir, submitted_target)

    # Contract: Delegates checking if pending target is dirty to WorkspacePendingManager.
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        return self._pending().is_pending_target_dirty(target_path, workspace_dir, main_root, role_name)

    def _eval_unit_dirty(
        self,
        ws_root: str,
        part_dir: str,
        unit_name: str,
        eval_role: str,
        repo_root: Optional[str] = None,
    ) -> bool:
        res = self._dirtiness().evaluate_unit_dirty(ws_root, part_dir, unit_name, eval_role, repo_root)
        return res.is_dirty

    # Contract: Computes ready and blocked dirty units directly from build manifests and metadata.
    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
        target_unit: Optional[str] = None,
    ) -> Tuple[Sequence[work.WorkQueueItem], Sequence[work.WorkQueueItem]]:

        clean_role = role_name.split(":")[-1].strip().lower()
        part_dirs = _find_part_dirs_in_scope(repo_root, dir_scope)
        all_units: Dict[str, str] = {}
        module_deps: Dict[str, List[str]] = {}
        raw_module_deps: Dict[str, List[str]] = {}

        for pd in part_dirs:
            for uname, mdeps in _get_part_units(repo_root, pd).items():
                all_units[uname] = pd
                raw_module_deps[uname] = list(mdeps)
                module_deps[uname] = [d.split(":")[-1] for d in mdeps]

        all_dirty = _find_all_dirty_in_scope(repo_root, dir_scope=dir_scope)
        dirty_lookup: Dict[Tuple[str, str], Dict[str, Any]] = {
            (item["unit_name"], item["role"]): item for item in all_dirty
        }
        dirty_part_lookup: Dict[Tuple[str, str, str], Dict[str, Any]] = {
            (item.get("part_dir", ""), item["unit_name"], item["role"]): item
            for item in all_dirty
        }

        reg = get_singleton(role_registry.WorkspaceRegistry)
        active_role_def = reg.resolve_role_definition(clean_role, repo_root=repo_root)
        fused_roles_set = set(active_role_def.fused_roles) if active_role_def.fused_roles else set()

        if fused_roles_set:
            dirty_in_role = [item for item in all_dirty if item["role"] in fused_roles_set]
        else:
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

        if target_unit:
            target_clean = target_unit.split("#")[0]
            if ":" in target_clean:
                target_clean = target_clean.split(":")[-1]
            elif "/" in target_clean:
                target_clean = os.path.basename(target_clean).split(".")[0]
            target_clean = target_clean.strip()
            if target_clean:
                allowed_units = {target_clean} | get_transitive_deps(target_clean)
                dirty_in_role = [item for item in dirty_in_role if item["unit_name"] in allowed_units]
                if not dirty_in_role:
                    return (), ()

        ready_candidates: List[Dict[str, Any]] = []
        blocked_candidates: List[Dict[str, Any]] = []

        for item in dirty_in_role:
            uname = item["unit_name"]
            item_role = item["role"]
            item_role_def = reg.resolve_role_definition(item_role, repo_root=repo_root)
            item_upstream_roles = _get_role_upstream_chain(item_role, repo_root=repo_root)
            item_is_auditor = _is_auditor_role(item_role, repo_root=repo_root)
            item_feedback_roles = [d.split(":")[-1] for d in item_role_def.feedback_role_deps]
            item_silent_cross = [d.split(":")[-1] for d in item_role_def.silent_cross_role_deps]
            item_star_roles = [d.split(":")[-1] for d in item_role_def.star_role_deps]

            part_dir = item.get("part_dir", "") or all_units.get(uname, "")
            blocked_reasons: List[str] = []

            # Check 1: Intra-unit upstream roles
            u_ctype = _classify_unit_type(uname)
            for up_r in item_upstream_roles:
                if fused_roles_set and up_r in fused_roles_set:
                    continue
                up_r_def = reg.resolve_role_definition(up_r, repo_root=repo_root)
                if up_r_def.active_component_types and u_ctype not in up_r_def.active_component_types:
                    continue
                up_r_pat = up_r_def.src_pattern
                if up_r_pat and part_dir and not os.path.isdir(os.path.join(repo_root, part_dir, _parse_pattern_info(up_r_pat)[0])):
                    continue
                if (part_dir, uname, up_r) in dirty_part_lookup or (not part_dir and (uname, up_r) in dirty_lookup):
                    blocked_reasons.append(
                        f"Upstream role '{up_r}' is dirty for unit '{uname}'"
                    )

            # Check 2: Auditor feedback dependencies
            if item_is_auditor:
                for fb_r in item_feedback_roles:
                    if fused_roles_set and fb_r in fused_roles_set:
                        continue
                    fb_r_def = reg.resolve_role_definition(fb_r, repo_root=repo_root)
                    if fb_r_def.active_component_types and u_ctype not in fb_r_def.active_component_types:
                        continue
                    if (part_dir, uname, fb_r) in dirty_part_lookup or (not part_dir and (uname, fb_r) in dirty_lookup):
                        blocked_reasons.append(
                            f"Feedback target '{fb_r}' is dirty or has unacted feedback for unit '{uname}'"
                        )

            # Check 3: Inter-unit module dependencies
            transitive_deps = get_transitive_deps(uname)
            roles_to_check = [r for r in item_upstream_roles if not _is_auditor_role(r, repo_root=repo_root)]
            for dep_u in sorted(transitive_deps):
                dep_part = all_units.get(dep_u, part_dir)
                dep_ctype = _classify_unit_type(dep_u)
                for r_check in roles_to_check:
                    if fused_roles_set and r_check in fused_roles_set:
                        continue
                    r_check_def = reg.resolve_role_definition(r_check, repo_root=repo_root)
                    if r_check_def.active_component_types and dep_ctype not in r_check_def.active_component_types:
                        continue
                    r_check_pat = r_check_def.src_pattern
                    if r_check_pat and dep_part and not os.path.isdir(os.path.join(repo_root, dep_part, _parse_pattern_info(r_check_pat)[0])):
                        continue
                    if (dep_part, dep_u, r_check) in dirty_part_lookup or (not dep_part and (dep_u, r_check) in dirty_lookup):
                        blocked_reasons.append(
                            f"Prerequisite unit '{dep_u}' is dirty in role '{r_check}'"
                        )

            raw_deps = raw_module_deps.get(uname, [])
            dep_files: List[str] = []
            for dep in raw_deps:
                dep_pkg, dep_u = _parse_dependency_label(dep, all_units.get(dep.lstrip(":"), part_dir))
                if not dep.startswith("//"):
                    dep_pkg = all_units.get(dep_u, part_dir)

                for star_r in item_star_roles:
                    if star_r in item_silent_cross:
                        continue
                    star_def = reg.resolve_role_definition(star_r, repo_root=repo_root)
                    star_pat = star_def.src_pattern
                    if not star_pat:
                        continue
                    star_cand = star_pat.format(unit_dir=dep_pkg, unit_name=dep_u)
                    cand = star_cand
                    # Contract: Resolves companion interface contracts without the _impl suffix for any implementation unit ending in _impl when expanding star role dependencies.
                    if not os.path.isfile(os.path.join(repo_root, star_cand)) and dep_u.endswith("_impl"):
                        iface_cand = star_pat.format(unit_dir=dep_pkg, unit_name=dep_u[:-5])
                        if os.path.isfile(os.path.join(repo_root, iface_cand)):
                            cand = iface_cand
                    if cand not in dep_files:
                        dep_files.append(cand)

            item["dependencies"] = dep_files

            if blocked_reasons:
                item["blocked_reasons"] = blocked_reasons
                blocked_candidates.append(item)
            else:
                ready_candidates.append(item)

        sorted_ready = _topological_sort_units(ready_candidates, module_deps)

        for item in sorted_ready:
            item_role = item["role"]
            r_def = reg.resolve_role_definition(item_role, repo_root=repo_root) if reg else None
            if r_def and r_def.src_pattern:
                target_file = item["target_file"]
                full_target = os.path.join(repo_root, target_file)
                if not os.path.isfile(full_target):
                    _materialize_starter_template(target_file, item_role, repo_root)

        def _to_queue_item(item: Dict[str, Any], ready: bool) -> work.WorkQueueItem:
            return work.WorkQueueItem(
                target_file=item["target_file"],
                role_name=item["role"],
                dirtiness_reasons=item["reasons"],
                dependency_files=item.get("dependencies", []),
                is_ready=ready,
                blocked_reasons=() if ready else item.get("blocked_reasons", ()),
                contract_files=self._dirtiness().resolve_contract_files(
                    item["target_file"], repo_root, role_name=item["role"]
                ),
            )
        ready_items = [_to_queue_item(item, True) for item in sorted_ready]
        blocked_items = [_to_queue_item(item, False) for item in blocked_candidates]
        return ready_items, blocked_items

    # Contract: Evaluates dirty units in scope, manages pending work buffer, and returns WorkQueueSummary.
    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> work.WorkQueueSummary:
        clean_role = role_name.split(":")[-1].strip().lower()

        # Check pending work buffer
        if workspace_dir and not force:
            pending_mgr = self._pending()
            pending_targets = pending_mgr.get_pending_work(workspace_dir)
            if pending_targets:
                still_dirty = [pt for pt in pending_targets if pending_mgr.is_pending_target_dirty(pt, workspace_dir, role_name=clean_role)]
                if still_dirty:
                    raise RuntimeError(f"Pending dirty work remains in workspace: {', '.join(still_dirty)}")
                pending_mgr.clear_pending_work(workspace_dir)

        eval_root = workspace_dir or os.getcwd()
        meta_p = os.path.join(eval_root, ".cleanroom_role.json")
        reg = get_singleton(role_registry.WorkspaceRegistry)
        if os.path.isfile(meta_p):
            try:
                m_root = reg.discover_repository_root(eval_root)
                if m_root and os.path.isdir(m_root) and os.path.realpath(m_root) != os.path.realpath(eval_root):
                    eval_root = os.path.realpath(m_root)
            except Exception:
                pass

        active_role_def = reg.resolve_role_definition(clean_role, repo_root=eval_root)
        fused_roles_set = set(active_role_def.fused_roles) if active_role_def.fused_roles else set()

        scheduler = None
        if not fused_roles_set:
            try:
                scheduler = get_singleton(work_scheduler.WorkScheduler)
            except (LifecycleResolutionError, LookupError, AttributeError):
                pass

        if scheduler is not None:
            try:
                schedule = scheduler.schedule_work(dir_scope=dir_scope)
                if schedule is not None and schedule.tasks:
                    sched_ready: List[work.WorkQueueItem] = []
                    for task in schedule.tasks:
                        task_role = task.node.role_address.split(":")[-1].strip().lower()
                        if clean_role and task_role != clean_role:
                            continue
                        reasons = [m.content for m in task.feedback_messages] or ["target is dirty"]
                        target_file = str(task.node.unit_address)
                        full_target = os.path.join(eval_root, target_file)
                        if not os.path.isfile(full_target):
                            _materialize_starter_template(target_file, task.node.role_address, eval_root)
                        sched_ready.append(
                            work.WorkQueueItem(
                                target_file=target_file,
                                role_name=task_role,
                                dirtiness_reasons=reasons,
                                dependency_files=task.dependency_paths,
                                is_ready=True,
                                blocked_reasons=(),
                                contract_files=self._dirtiness().resolve_contract_files(
                                    target_file, eval_root, role_name=task_role
                                ),
                            )
                        )
                    total_sched_ready = len(sched_ready)
                    remaining_count = 0
                    if batch_size is not None and batch_size > 0 and len(sched_ready) > batch_size:
                        remaining_count = len(sched_ready) - batch_size
                        sched_ready = list(sched_ready[:batch_size])

                    if workspace_dir:
                        self.set_pending_work(workspace_dir, [item.target_file for item in sched_ready]) if sched_ready else self.clear_pending_work(workspace_dir)

                    is_clean = total_sched_ready == 0
                    return work.WorkQueueSummary(
                        ready_items=sched_ready,
                        blocked_items=(),
                        is_clean=is_clean,
                        remaining_ready_count=remaining_count,
                    )
            except (RuntimeError, ValueError, AttributeError, KeyError):
                pass

        ready_items, blocked_items = self.compute_role_work_queue(
            clean_role, dir_scope, eval_root
        )

        total_ready = len(ready_items)
        remaining_count = 0
        if batch_size is not None and batch_size > 0 and len(ready_items) > batch_size:
            remaining_count = len(ready_items) - batch_size
            ready_items = list(ready_items[:batch_size])

        if workspace_dir:
            self.set_pending_work(workspace_dir, [item.target_file for item in ready_items]) if ready_items else self.clear_pending_work(workspace_dir)

        is_clean = total_ready == 0 and len(blocked_items) == 0
        return work.WorkQueueSummary(
            ready_items=ready_items,
            blocked_items=blocked_items,
            is_clean=is_clean,
            remaining_ready_count=remaining_count,
        )

    # Contract: Delegates companion specification contracts resolution to WorkspaceDirtinessEvaluator.
    def resolve_contract_files(
        self,
        target_path: str,
        workspace_dir: str,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        return self._dirtiness().resolve_contract_files(
            target_path, workspace_dir, role_name=role_name
        )

    # Contract: MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
    def get_part_units(
        self,
        repo_root: str,
        part_dir: str,
    ) -> Mapping[str, Sequence[str]]:
        return _get_part_units(repo_root, part_dir)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-19T16:30:00Z
# CHANGE: evaluate role upstream prerequisites across silent role dependencies
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceWorkManager,
        keys=[work.WorkspaceWorkManager, WorkspaceWorkManager],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
