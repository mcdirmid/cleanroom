# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:40:00Z
# CHANGE: Implement workspace_pending_impl
# CODE_HASH: b3a44a466a4c
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import json
import os
from typing import Optional, Sequence
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.storage.lib import src_metadata
from update_with_ai.parts.workspace.lib import workspace_registry
from . import workspace_pending, workspace_work

PENDING_WORK_FILE = ".cleanroom_pending_work.json"


def _find_part_dirs_in_scope(repo_root: str, dir_scope: str = "") -> list[str]:
    if not dir_scope:
        parts_p = os.path.join(repo_root, "parts")
        if os.path.isdir(parts_p):
            return [
                os.path.join("parts", d)
                for d in sorted(os.listdir(parts_p))
                if os.path.isdir(os.path.join(parts_p, d)) and not d.startswith(".")
            ]
        for entry in sorted(os.listdir(repo_root)):
            cand = os.path.join(repo_root, entry, "parts")
            if os.path.isdir(cand) and not entry.startswith((".", "bazel-", "venv")):
                dir_scope = entry
                break
    if not dir_scope:
        return []
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


def check_pending_work_clean(
    workspace_dir: str,
    role_name: str,
    manager: Optional[workspace_pending.WorkspacePendingManager] = None,
) -> None:
    mgr = manager or get_singleton(workspace_pending.WorkspacePendingManager)
    pending = mgr.get_pending_work(workspace_dir)
    if pending:
        still_dirty = [
            pt
            for pt in pending
            if mgr.is_pending_target_dirty(pt, workspace_dir, role_name=role_name)
        ]
        if still_dirty:
            raise RuntimeError(
                f"Pending dirty work remains in workspace: {', '.join(still_dirty)}"
            )
        mgr.clear_pending_work(workspace_dir)



def _parse_pattern_info(src_pattern: str) -> tuple[str, str, str]:
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


def _parse_unit_from_file_path(file_path: str, repo_root: str) -> tuple[str, str, str]:
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


def materialize_starter_template(
    target_path: str,
    role_name: str,
    workspace_dir: str,
) -> bool:
    """Materializes a starter template via graph storage for a missing target file."""
    storage = None
    try:
        storage = get_singleton(dag_storage.DagStorage)
    except (LifecycleResolutionError, LookupError, AttributeError):
        pass
    if storage is not None and hasattr(storage, "materialize_template"):
        node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress(target_path),
            role_address=dag_storage.RoleAddress(role_name),
        )
        old_bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        try:
            os.environ["BUILD_WORKSPACE_DIRECTORY"] = workspace_dir
            storage.materialize_template(node)
            return True
        finally:
            if old_bwd is not None:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_bwd
            elif "BUILD_WORKSPACE_DIRECTORY" in os.environ:
                del os.environ["BUILD_WORKSPACE_DIRECTORY"]
    return False


class WorkspacePendingManager(workspace_pending.WorkspacePendingManager, Singleton):
    """Realizes pending buffer tracking, target removal, and dirty checks."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

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
        except (OSError, json.JSONDecodeError):
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
        self.set_pending_work(workspace_dir, remaining)

    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        full_ws = os.path.join(workspace_dir, target_path) if not os.path.isabs(target_path) else target_path
        part_dir = ""
        unit_name = ""
        r_name = ""
        try:
            part_dir, unit_name, r_name = _parse_unit_from_file_path(full_ws, workspace_dir)
        except (ValueError, KeyError, OSError, LifecycleResolutionError):
            pass
        eval_role = (role_name or r_name).split(":")[-1].strip().lower()
        m_root = main_root or workspace_dir
        reg = None
        try:
            reg = get_singleton(workspace_registry.WorkspaceRegistry)
        except (LifecycleResolutionError, LookupError):
            pass
        role_def = reg.resolve_role_definition(eval_role, repo_root=m_root) if reg and eval_role else None

        if not unit_name and role_def and role_def.src_pattern:
            d_name, pfx, sfx = _parse_pattern_info(role_def.src_pattern)
            sfx_no_ext = os.path.splitext(sfx)[0] if sfx else ""
            stem = os.path.splitext(os.path.basename(target_path))[0]
            if sfx_no_ext and stem.endswith(sfx_no_ext):
                stem = stem[:-len(sfx_no_ext)]
            if pfx and stem.startswith(pfx):
                stem = stem[len(pfx):]
            unit_name = stem
            part_dirs = [d for d in os.listdir(os.path.join(m_root, "parts")) if os.path.isdir(os.path.join(m_root, "parts", d))] if os.path.isdir(os.path.join(m_root, "parts")) else []
            for pd in part_dirs:
                cand_rel = role_def.src_pattern.format(unit_dir=os.path.join("parts", pd), unit_name=unit_name)
                part_dir = os.path.join("parts", pd)
                target_path = cand_rel
                full_ws = os.path.join(workspace_dir, cand_rel)
                break

        is_auditor = bool(role_def and (role_def.audit_tag or not role_def.src_pattern)) if role_def else False
        if not is_auditor:
            if not os.path.isfile(full_ws):
                has_upstream_deps = bool(
                    role_def
                    and (
                        role_def.role_deps
                        or role_def.feedback_role_deps
                        or any(s.split(":")[-1] != eval_role for s in role_def.star_role_deps)
                    )
                )
                can_regenerate = bool(
                    role_def
                    and role_def.src_pattern
                    and has_upstream_deps
                )
                if can_regenerate:
                    materialize_starter_template(target_path, eval_role, workspace_dir)
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

        try:
            work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
            eval_fn = getattr(work_mgr, "_eval_unit_dirty", None)
            if callable(eval_fn):
                return bool(eval_fn(workspace_dir, part_dir, unit_name, eval_role, m_root))
        except (LifecycleResolutionError, LookupError):
            pass
        return False


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspacePendingManager,
        keys=[
            WorkspacePendingManager,
            workspace_pending.WorkspacePendingManager,
        ],
    )


_initialize_ = __initialize__
