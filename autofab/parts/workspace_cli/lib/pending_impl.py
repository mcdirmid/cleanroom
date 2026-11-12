from __future__ import annotations
import json
import os
import re
from typing import List, Optional, Sequence
from support.lib.lifecycle import LifecycleResolutionError, auto_initialize, get_singleton, singleton
from autofab.parts.agent.lib import session as agent_session
from autofab.parts.dag.lib import dag_storage
from autofab.parts.metadata.lib import src_metadata
from autofab.parts.workspace.lib import role_registry
from . import dirtiness, pending, work

try:
    from support.lib import app_info
except ImportError:
    try:
        from autofab.support.lib import app_info  # type: ignore
    except ImportError:
        import app_info  # type: ignore

# Contract: Relative filename for pending work tracking buffer.
PENDING_WORK_FILE = getattr(
    app_info, "DEFAULT_PENDING_WORK_FILE", ".autofab_pending_work.json"
)


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
        reg = get_singleton(role_registry.WorkspaceRegistry)
        actual_root = repo_root
        if actual_root:
            try:
                discovered = reg.discover_repository_root(actual_root)
                if discovered and os.path.isdir(discovered):
                    actual_root = discovered
            except Exception:
                pass
        for role in reg.list_roles(repo_root=actual_root):
            pats = (
                role.src_patterns
                if hasattr(role, "src_patterns") and role.src_patterns
                else ([role.src_pattern] if role.src_pattern else [])
            )
            for pat in pats:
                d_name, pfx, sfx = _parse_pattern_info(pat)
                if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
                    return role.role_name
    except (LifecycleResolutionError, LookupError, OSError):
        pass
    raise ValueError(f"Unrecognized role for file path: {file_path}")


def _parse_unit_from_file_path(file_path: str, repo_root: str) -> tuple[str, str, str]:
    norm_path = os.path.realpath(file_path)
    norm_root = os.path.realpath(repo_root)
    reg = None
    try:
        reg = get_singleton(role_registry.WorkspaceRegistry)
    except (LifecycleResolutionError, LookupError):
        pass
    actual_root = repo_root
    if reg is not None:
        try:
            discovered = reg.discover_repository_root(repo_root)
            if discovered and os.path.isdir(discovered):
                actual_root = discovered
        except Exception:
            pass
    rel = (
        os.path.relpath(norm_path, norm_root).replace("\\", "/")
        if norm_path.startswith(norm_root)
        else file_path.replace("\\", "/")
    )
    fname = os.path.basename(rel)
    parent = os.path.basename(os.path.dirname(rel))
    role_name = _resolve_file_role(rel, repo_root=actual_root)
    if reg is not None:
        role_def = reg.resolve_role_definition(role_name, repo_root=actual_root)
        pats = (
            role_def.src_patterns
            if hasattr(role_def, "src_patterns") and role_def.src_patterns
            else ([role_def.src_pattern] if role_def.src_pattern else [])
        )
        unit_name = fname
        for pat in pats:
            d_name, pfx, sfx = _parse_pattern_info(pat)
            if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
                u_cand = fname
                if pfx and u_cand.startswith(pfx):
                    u_cand = u_cand[len(pfx) :]
                if sfx and u_cand.endswith(sfx):
                    u_cand = u_cand[: -len(sfx)]
                unit_name = u_cand
                break
        parent_dir = os.path.dirname(os.path.dirname(rel))
        part_dir = parent_dir
        if norm_root in part_dir:
            part_dir = os.path.relpath(part_dir, norm_root).replace("\\", "/")
        return part_dir, unit_name, role_name
    return "", "", role_name


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
        storage.materialize_template(node)
        return True
    return False


def _normalize_unit_stem(name: str) -> str:
    norm = name.strip().lstrip("/").replace("\\", "/")
    stem = os.path.splitext(os.path.basename(norm))[0]
    changed = True
    while changed:
        changed = False
        for suffix in ("_pretense", "_test", "_impl"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                changed = True
                break
    return stem


# Contract: Realizes pending buffer tracking, target removal, and dirty checks in agent_session tier.
@singleton
class WorkspacePendingManager(pending.WorkspacePendingManager):
    """Realizes pending buffer tracking, target removal, and dirty checks."""


    def __init__(self) -> None:
        pass

    # Contract: Reads target paths from local pending work buffer.
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

    # Contract: Records pending target paths into local buffer file.
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        marker = os.path.join(
            app_info.resolve_state_dir(workspace_dir), ".no_pending_work"
        )
        if not targets:
            self.clear_pending_work(workspace_dir)
            try:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("0\n")
            except OSError:
                pass
            return

        if os.path.isfile(marker):
            try:
                os.remove(marker)
            except OSError:
                pass

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

    # Contract: Removes local pending work buffer file if present.
    def clear_pending_work(self, workspace_dir: str) -> None:
        p = os.path.join(workspace_dir, PENDING_WORK_FILE)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass

    # Contract: Removes a submitted target from local pending work buffer.
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        targets = list(self.get_pending_work(workspace_dir))
        if not targets:
            return
        norm_sub = submitted_target.strip().lstrip("/")
        sub_stem = _normalize_unit_stem(norm_sub)
        remaining = []
        for t in targets:
            norm_t = t.strip().lstrip("/")
            t_stem = _normalize_unit_stem(norm_t)
            if (
                norm_t == norm_sub
                or norm_t.endswith(f"/{norm_sub}")
                or norm_sub.endswith(f"/{norm_t}")
                or (sub_stem and t_stem and t_stem == sub_stem)
            ):
                continue
            remaining.append(t)
        self.set_pending_work(workspace_dir, remaining)

    # Contract: Checks whether a pending target file is still dirty across local workspace and main repository.
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        full_ws = (
            os.path.join(workspace_dir, target_path)
            if not os.path.isabs(target_path)
            else target_path
        )
        m_root = main_root
        reg = None
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
        except (LifecycleResolutionError, LookupError):
            pass
        if not m_root or not os.path.isdir(m_root):
            if reg is not None:
                try:
                    discovered = reg.discover_repository_root(workspace_dir)
                    if discovered and os.path.isdir(discovered):
                        m_root = discovered
                except Exception:
                    pass
        m_root = m_root or workspace_dir
        part_dir = ""
        unit_name = ""
        r_name = ""
        try:
            part_dir, unit_name, r_name = _parse_unit_from_file_path(full_ws, m_root)
        except (ValueError, KeyError, OSError, LifecycleResolutionError):
            try:
                part_dir, unit_name, r_name = _parse_unit_from_file_path(
                    full_ws, workspace_dir
                )
            except (ValueError, KeyError, OSError, LifecycleResolutionError):
                pass
        eval_role = (role_name or r_name).split(":")[-1].strip().lower()
        role_def = (
            reg.resolve_role_definition(eval_role, repo_root=m_root)
            if reg and eval_role
            else None
        )
        if role_def and role_def.fused_roles and r_name:
            eval_role = r_name
            role_def = (
                reg.resolve_role_definition(eval_role, repo_root=m_root)
                if reg
                else None
            )

        is_auditor = (
            bool(role_def and (role_def.audit_tag or not role_def.src_pattern))
            if role_def
            else False
        )
        if not is_auditor:
            if not os.path.isfile(full_ws):
                has_upstream_deps = bool(
                    role_def
                    and (
                        role_def.role_deps
                        or role_def.feedback_role_deps
                        or getattr(role_def, "star_feedback_role_deps", ())
                        or any(
                            s.split(":")[-1] != eval_role
                            for s in role_def.star_role_deps
                        )
                    )
                )
                can_regenerate = bool(
                    role_def and role_def.src_pattern and has_upstream_deps
                )
                if can_regenerate:
                    materialize_starter_template(target_path, eval_role, workspace_dir)
                return True

            # Check candidate metadata across main repository and workspace
            target_meta = None
            if m_root != workspace_dir:
                rel_target = (
                    os.path.relpath(full_ws, workspace_dir)
                    if full_ws.startswith(workspace_dir)
                    else target_path
                )
                full_main = os.path.join(m_root, rel_target)
                if os.path.isfile(full_main):
                    target_meta = src_metadata.extract_metadata(full_main)
            if target_meta is None:
                target_meta = src_metadata.extract_metadata(full_ws)

            meta_ws = src_metadata.extract_metadata(full_ws)
            if (
                meta_ws is None
                or meta_ws.dirty
                or meta_ws.feedback
                or target_meta is None
                or not target_meta.last_cleaned
                or target_meta.dirty
                or target_meta.feedback
            ):
                return True

        if not unit_name:
            return False

        try:
            dirt_mgr = get_singleton(dirtiness.WorkspaceDirtinessEvaluator)
            return dirt_mgr.evaluate_unit_dirty(
                workspace_dir, part_dir, unit_name, eval_role, m_root
            ).is_dirty
        except (LifecycleResolutionError, LookupError):
            pass
        return False

    # Contract: Evaluates and returns reasons why a pending target is dirty, including unacted feedback.
    def get_pending_target_reasons(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        full_ws = (
            os.path.join(workspace_dir, target_path)
            if not os.path.isabs(target_path)
            else target_path
        )
        m_root = main_root
        reg = None
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
        except (LifecycleResolutionError, LookupError):
            pass
        if not m_root or not os.path.isdir(m_root):
            if reg is not None:
                try:
                    discovered = reg.discover_repository_root(workspace_dir)
                    if discovered and os.path.isdir(discovered):
                        m_root = discovered
                except Exception:
                    pass
        m_root = m_root or workspace_dir
        part_dir = ""
        unit_name = ""
        r_name = ""
        try:
            part_dir, unit_name, r_name = _parse_unit_from_file_path(full_ws, m_root)
        except (ValueError, KeyError, OSError, LifecycleResolutionError):
            try:
                part_dir, unit_name, r_name = _parse_unit_from_file_path(
                    full_ws, workspace_dir
                )
            except (ValueError, KeyError, OSError, LifecycleResolutionError):
                pass
        eval_role = (role_name or r_name).split(":")[-1].strip().lower()
        role_def = (
            reg.resolve_role_definition(eval_role, repo_root=m_root)
            if reg and eval_role
            else None
        )
        if role_def and role_def.fused_roles and r_name:
            eval_role = r_name
            role_def = (
                reg.resolve_role_definition(eval_role, repo_root=m_root)
                if reg
                else None
            )

        reasons: List[str] = []
        is_auditor = (
            bool(role_def and (role_def.audit_tag or not role_def.src_pattern))
            if role_def
            else False
        )
        if not is_auditor:
            if not os.path.isfile(full_ws):
                reasons.append(f"Source file {target_path} does not exist")
            else:
                target_meta = None
                if m_root != workspace_dir:
                    rel_target = (
                        os.path.relpath(full_ws, workspace_dir)
                        if full_ws.startswith(workspace_dir)
                        else target_path
                    )
                    full_main = os.path.join(m_root, rel_target)
                    if os.path.isfile(full_main):
                        target_meta = src_metadata.extract_metadata(full_main)
                if target_meta is None:
                    target_meta = src_metadata.extract_metadata(full_ws)
                meta_ws = src_metadata.extract_metadata(full_ws)
                for m in (target_meta, meta_ws):
                    if m and m.dirty:
                        msg = f"Target explicitly marked DIRTY: {m.dirty}"
                        if msg not in reasons:
                            reasons.append(msg)
                    if m and m.feedback:
                        for fb in m.feedback:
                            clean_fb = re.sub(r"^\[.*?\]:\s*", "", fb.strip())
                            msg = f"Unacted feedback in {target_path}: {clean_fb}"
                            if msg not in reasons:
                                reasons.append(msg)
                if (meta_ws and not meta_ws.last_cleaned) or (
                    target_meta and not target_meta.last_cleaned
                ):
                    msg = f"Target has not been cleaned ({target_path})"
                    if msg not in reasons:
                        reasons.append(msg)

        if unit_name:
            try:
                dirt_mgr = get_singleton(dirtiness.WorkspaceDirtinessEvaluator)
                res = dirt_mgr.evaluate_unit_dirty(
                    workspace_dir, part_dir, unit_name, eval_role, m_root
                )
                for r in res.dirtiness_reasons:
                    if r not in reasons:
                        reasons.append(r)
            except (LifecycleResolutionError, LookupError):
                pass

        if not reasons and self.is_pending_target_dirty(
            target_path, workspace_dir, main_root, role_name
        ):
            reasons.append(f"Target is dirty ({target_path})")

        return tuple(reasons)


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-31T02:00:00Z
# CHANGE: Add get_pending_target_reasons implementation
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

__initialize__ = auto_initialize()
_initialize_ = __initialize__
