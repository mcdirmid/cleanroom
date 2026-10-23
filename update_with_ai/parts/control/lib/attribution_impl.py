from __future__ import annotations
import json
import os
import shutil
import stat
import sys
import tomllib
from typing import Any, Dict, List, Optional, Sequence, Tuple
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import file_alias, node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.metadata.lib import src_metadata
from . import attribution


def _get_role_definitions() -> Dict[str, Any]:
    try:
        cfg: Any = get_singleton(node_config.NodeConfig)
        if cfg is not None and hasattr(cfg, "role_definitions"):
            r_defs = cfg.role_definitions
            if isinstance(r_defs, dict) and r_defs:
                return r_defs
    except (LifecycleResolutionError, KeyError, AttributeError, RuntimeError):
        pass
    try:
        from update_with_ai.parts.workspace.lib import role_registry
        reg = get_singleton(role_registry.WorkspaceRegistry)
        return {r.role_name: r for r in reg.list_roles()}
    except Exception:
        pass
    return {}


def _role_src_pattern(role_def: Any) -> str:
    if hasattr(role_def, "src_pattern"):
        return str(role_def.src_pattern or "")
    if isinstance(role_def, dict):
        return str(role_def.get("src_pattern") or "")
    return ""


def _role_name(role_def: Any, default: str = "") -> str:
    if hasattr(role_def, "role_name"):
        return str(role_def.role_name or default)
    if isinstance(role_def, dict):
        return str(role_def.get("role_name") or default)
    return default


def _role_audit_tag(role_def: Any) -> Optional[str]:
    if hasattr(role_def, "audit_tag"):
        return role_def.audit_tag
    if isinstance(role_def, dict):
        return role_def.get("audit_tag")
    return None


def _role_feedback_deps(role_def: Any) -> Sequence[str]:
    if hasattr(role_def, "feedback_role_deps"):
        return role_def.feedback_role_deps or ()
    if isinstance(role_def, dict):
        return role_def.get("feedback_role_deps") or ()
    return ()


def _bound_file_path(bound_file: Any) -> str:
    if hasattr(bound_file, "workspace_path") and bound_file.workspace_path is not None:
        ws_path = bound_file.workspace_path
        return str(ws_path.path if hasattr(ws_path, "path") else ws_path)
    if hasattr(bound_file, "relative_path"):
        return str(bound_file.relative_path)
    return str(bound_file)


def _node_display_alias(node: dag_storage.DagNode) -> str:
    try:
        from . import coordinate
        coord = get_singleton(coordinate.SessionCoordinator)
        if coord is not None:
            return coord.get_alias_for_node(node)
    except Exception:
        pass

    try:
        cfg = get_singleton(node_config.NodeConfig)
        if cfg is not None:
            if hasattr(cfg, "src_file_alias_by_node") and cfg.src_file_alias_by_node and node in cfg.src_file_alias_by_node:
                return str(cfg.src_file_alias_by_node[node])
            if hasattr(cfg, "blame_targets_by_node") and cfg.blame_targets_by_node:
                for bt_set in cfg.blame_targets_by_node.values():
                    for bt in bt_set:
                        if hasattr(bt, "owning_node") and bt.owning_node == node:
                            return str(bt.relative_path if hasattr(bt, "relative_path") else bt)
            if hasattr(cfg, "read_only_files") and cfg.read_only_files:
                for ro in cfg.read_only_files:
                    if hasattr(ro, "owning_node") and ro.owning_node == node:
                        return str(ro.relative_path if hasattr(ro, "relative_path") else ro)
            if hasattr(cfg, "read_write_files") and cfg.read_write_files:
                for rw in cfg.read_write_files:
                    if hasattr(rw, "owning_node") and rw.owning_node == node:
                        return str(rw.relative_path if hasattr(rw, "relative_path") else rw)
    except Exception:
        pass

    addr = str(node.unit_address).strip()
    if ":" in addr:
        pkg, unit_name = addr.split(":", 1)
        pkg = pkg.lstrip("/").strip()
    elif "/" in addr:
        pkg, unit_name = addr.rsplit("/", 1)
        pkg = pkg.lstrip("/").strip()
    else:
        pkg, unit_name = "", addr

    role = str(node.role_address).split(":")[-1].strip().lower() if node.role_address else ""
    role_defs = _get_role_definitions()
    if role in role_defs:
        src_pat = _role_src_pattern(role_defs[role])
        if src_pat:
            formatted = src_pat.replace("{unit_dir}", pkg).replace(
                "{unit_name}", unit_name
            ).strip("/")
            if formatted:
                return formatted

    return f"{pkg}/{unit_name}" if pkg else unit_name


def _copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o644)
        except OSError:
            pass
    shutil.copy2(src, dst)
    mode = (0o555 if readonly else 0o755) if executable else (0o444 if readonly else 0o644)
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def _resolve_target_path(target: str, repo_root: str) -> str:
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
    role_defs = _get_role_definitions()
    if not role_defs:
        raise KeyError("No role definitions available in NodeConfig")
    for role in role_defs.values():
        src_pat = _role_src_pattern(role)
        if not src_pat:
            continue
        d_name, pfx, sfx = _parse_pattern_info(src_pat)
        if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
            return _role_name(role)
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
    role_defs = _get_role_definitions()
    role_def = role_defs.get(role_name)
    if role_def is None:
        raise KeyError(f"Role '{role_name}' not found in NodeConfig.role_definitions")
    src_pat = _role_src_pattern(role_def)
    _, pfx, sfx = _parse_pattern_info(src_pat)
    unit_name = fname
    if pfx and unit_name.startswith(pfx):
        unit_name = unit_name[len(pfx) :]
    if sfx and unit_name.endswith(sfx):
        unit_name = unit_name[: -len(sfx)]
    part_dir = os.path.dirname(os.path.dirname(rel))
    return part_dir, unit_name, role_name


def _resolve_bound_file_path(blame_string: str) -> Optional[str]:
    """Resolves a blame string to its workspace host path through the alias manager."""
    try:
        alias = get_singleton(file_alias.AliasManager).to_alias(blame_string)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        return None
    if isinstance(alias, file_alias.BoundFile):
        return _bound_file_path(alias)
    return None


class AttributionCoordinator(attribution.AttributionCoordinator):
    """Coordinates upstream blame attribution, single-paragraph validation, and failure cascades."""

    tier = agent_session.agent_session

    # Contract: Converts value through AliasManager.to_alias and intersects resulting alias with blame_targets_by_node for the supplied node.
    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[file_alias.BoundFile]:
        """Matches a blame target value against configured blame targets for a node."""
        cfg = get_singleton(node_config.NodeConfig)
        targets = list(cfg.blame_targets_by_node.get(node, set()))
        try:
            alias = get_singleton(file_alias.AliasManager).to_alias(val_str)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            alias = None
        alias_path = str(alias.relative_path if hasattr(alias, "relative_path") else "") if alias is not None else ""
        for bound in targets:
            bound_path = str(bound.relative_path if hasattr(bound, "relative_path") else "")
            if val is not None and bound == val:
                return bound
            if alias is not None and bound == alias:
                return bound
            if alias_path and bound_path == alias_path:
                return bound
        # Suffix-matching and basename-matching when alias intersection fails.
        if val_str:
            norm_v = val_str.lstrip("/")
            suffix_matches = [
                bound
                for bound in targets
                if (
                    str(bound.relative_path if hasattr(bound, "relative_path") else "").endswith("/" + norm_v)
                    or norm_v.endswith("/" + str(bound.relative_path if hasattr(bound, "relative_path") else "").lstrip("/"))
                )
            ]
            if len(suffix_matches) == 1:
                return suffix_matches[0]
            base_matches = [
                bound
                for bound in targets
                if os.path.basename(str(bound.relative_path if hasattr(bound, "relative_path") else ""))
                == os.path.basename(norm_v)
            ]
            if len(base_matches) == 1:
                return base_matches[0]
        return None

    # Contract: Rejects if newline in explanation, not upstream dependency, role not configured for feedback, or in-batch dependencies not clean; on acceptance, records feedback, marks culprit dirty, and marks dependents failed.
    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> attribution.AttributionOutcome:
        """Attributes defect to an upstream dependency node."""
        storage = get_singleton(dag_storage.DagStorage)

        # 1. Single-paragraph critique validation
        if "\n" in explanation or "\r" in explanation:
            return attribution.AttributionOutcome(
                accepted=False,
                message="Error: Blame explanation must be a single paragraph without newlines.",
                affected_nodes=[],
            )

        # 2. Upstream dependency validation
        deps = storage.get_dependencies(source_node)
        upstream_nodes = {dep.node for dep in deps}
        if blame_target_node not in upstream_nodes:
            try:
                cfg = get_singleton(node_config.NodeConfig)
                targets = list(cfg.blame_targets_by_node.get(source_node, set()) if (cfg and hasattr(cfg, "blame_targets_by_node")) else set())
            except Exception:
                targets = []
            if targets:
                allowed = ", ".join(f"`{t.relative_path if hasattr(t, 'relative_path') else t}`" for t in targets)
            else:
                allowed = ", ".join(f"`{_node_display_alias(n)}`" for n in upstream_nodes)
            return attribution.AttributionOutcome(
                accepted=False,
                message=f"Error: Target '{_node_display_alias(blame_target_node)}' is not an upstream dependency. Available: {allowed}",
                affected_nodes=[],
            )

        # 2b. Feedback configuration validation
        role_defs = _get_role_definitions()
        src_role = str(source_node.role_address).split(":")[-1].strip().lower()
        tgt_role = str(blame_target_node.role_address).split(":")[-1].strip().lower()
        if role_defs and src_role in role_defs:
            src_def = role_defs[src_role]
            raw_fb = _role_feedback_deps(src_def)
            fb_deps = [
                d.split(":")[-1].strip().lower()
                for d in (raw_fb or ())
            ]
            if tgt_role not in fb_deps:
                return attribution.AttributionOutcome(
                    accepted=False,
                    message=f"Error: Role '{src_role}' is not configured to deliver feedback to role '{tgt_role}'.",
                    affected_nodes=[],
                )

        # 3. In-batch dependencies must be clean
        if in_batch_dependencies:
            for dep in in_batch_dependencies:
                if storage.is_dirty(dep):
                    return attribution.AttributionOutcome(
                        accepted=False,
                        message=f"Error: In-batch dependency '{_node_display_alias(dep)}' must be submitted before dependent targets.",
                        affected_nodes=[],
                    )

        # 4. Record the feedback on the culprit node and mark it dirty in graph storage
        feedback = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent(explanation.strip()),
            target=blame_target_node,
        )
        storage.add_feedback_message(blame_target_node, feedback)
        storage.mark_node_dirty(blame_target_node, explanation.strip())

        # 5. Mark source and fail in-batch dependents
        affected: List[dag_storage.DagNode] = [source_node]
        if in_batch_dependents:
            for dep in in_batch_dependents:
                affected.append(dep)

        return attribution.AttributionOutcome(
            accepted=True,
            message=f"Defect attributed to upstream dependency '{_node_display_alias(blame_target_node)}'.",
            affected_nodes=affected,
        )

    # Contract: Records failure diagnostic on target node, preserves dirty status in graph storage, and marks in-batch dependent nodes as failed.
    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> attribution.AttributionOutcome:
        """Records task failure and preserves dirty state on target node."""
        storage = get_singleton(dag_storage.DagStorage)
        reason = explanation.strip()
        storage.add_feedback_message(
            target_node,
            dag_storage.FeedbackMessage(
                content=dag_storage.MessageContent(reason),
                target=target_node,
            ),
        )
        storage.mark_node_dirty(target_node, reason)

        affected: List[dag_storage.DagNode] = [target_node]
        if in_batch_dependents:
            for dep in in_batch_dependents:
                affected.append(dep)

        return attribution.AttributionOutcome(
            accepted=True,
            message=f"Target '{_node_display_alias(target_node)}' failed: {reason}",
            affected_nodes=affected,
        )

    # Contract: Rejects if critique has newlines, exceeds max length, culprit unresolved, or caller role not allowed; on acceptance, records feedback in metadata, updates metadata, and syncs workspace copy.
    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> attribution.AttributionOutcome:
        """Attributes defect blame to an upstream culprit file."""
        if "\n" in critique or "\r" in critique:
            return attribution.AttributionOutcome(
                accepted=False,
                message="Error: Critique must be a single line/paragraph without newline characters.",
                affected_nodes=[],
            )

        ws_root = os.path.realpath(workspace_root or os.getcwd())
        meta: Optional[Dict[str, Any]] = None
        meta_p = os.path.join(ws_root, ".cleanroom_role.json")
        # Reads .cleanroom_role.json from ws_root to discover max_feedback_chars and model parameters.
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        if repo_root:
            main_root = os.path.realpath(repo_root)
        else:
            try:
                import importlib
                ws_reg_mod = importlib.import_module("role_registry")
                ws_reg = get_singleton(ws_reg_mod.WorkspaceRegistry)  # type: ignore
                main_root = os.path.realpath(ws_reg.discover_repository_root(ws_root))
            except Exception:
                main_root = os.path.realpath(ws_root)

        max_feedback_chars = None
        if meta and meta.get("max_feedback_chars"):
            try:
                max_feedback_chars = int(meta["max_feedback_chars"])
            except (ValueError, TypeError):
                pass
        # Parses model_configs.toml to extract max_feedback_chars threshold.
        if max_feedback_chars is None:
            m_cfg_file = os.path.join(main_root, "model_configs.toml")
            if os.path.isfile(m_cfg_file):
                try:
                    with open(m_cfg_file, "rb") as mf:
                        m_data = tomllib.load(mf)
                    role_model = meta.get("model") if meta else None
                    models_sec = m_data.get("models", {})
                    target_cfg = None
                    if role_model and role_model in models_sec:
                        target_cfg = models_sec[role_model]
                    elif not role_model and m_data.get("default") in models_sec:
                        target_cfg = models_sec[m_data["default"]]
                    if target_cfg and "max_feedback_chars" in target_cfg:
                        max_feedback_chars = int(target_cfg["max_feedback_chars"])
                except Exception:
                    pass

        if max_feedback_chars and len(critique) > max_feedback_chars:
            return attribution.AttributionOutcome(
                accepted=False,
                message=(
                    f"Error: Critique exceeds maximum length of {max_feedback_chars} characters "
                    f"({len(critique)} provided); you might prioritize contract discrepancies "
                    "to report so the authoring role can make progress."
                ),
                affected_nodes=[],
            )

        bound_path = _resolve_bound_file_path(culprit_file)
        if bound_path and os.path.exists(bound_path):
            dep_path = bound_path
        else:
            dep_path = _resolve_target_path(culprit_file, main_root)
            if not os.path.exists(dep_path):
                dep_path = _resolve_target_path(culprit_file, ws_root)
        if not os.path.exists(dep_path):
            return attribution.AttributionOutcome(
                accepted=False,
                message=f"Error: Could not locate blame target '{culprit_file}'.",
                affected_nodes=[],
            )

        # Falls back to environment variables CLEANROOM_ROLE, USER, or 'cleanroom' for caller identity.
        caller = caller_role or (meta.get("role_name") or meta.get("role") if meta else "") or os.environ.get("CLEANROOM_ROLE") or os.environ.get("USER") or "cleanroom"

        ref_root = main_root if dep_path.startswith(main_root) else ws_root
        part_dir, unit_name, blamed_role = _parse_unit_from_file_path(dep_path, ref_root)
        main_dep_path = os.path.join(main_root, os.path.relpath(dep_path, ref_root))

        # Validate that caller is configured to deliver feedback to blamed_role
        role_defs = _get_role_definitions()
        caller_clean = str(caller).split(":")[-1].strip().lower()
        blamed_clean = str(blamed_role).split(":")[-1].strip().lower()
        if role_defs and caller_clean in role_defs:
            c_def = role_defs[caller_clean]
            raw_fb = _role_feedback_deps(c_def)
            fb_deps = [
                d.split(":")[-1].strip().lower()
                for d in (raw_fb or ())
            ]
            if blamed_clean not in fb_deps:
                return attribution.AttributionOutcome(
                    accepted=False,
                    message=f"Error: Role '{caller}' is not configured to deliver feedback to role '{blamed_role}'.",
                    affected_nodes=[],
                )

        target_to_mutate = main_dep_path if os.path.exists(main_dep_path) else dep_path
        src_metadata.append_feedback(target_to_mutate, critique, sender=caller)
        src_metadata.update_metadata(
            target_to_mutate, last_cleaned=src_metadata.current_utc_timestamp()
        )
        if ws_root != main_root and os.path.isfile(main_dep_path):
            ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
            if os.path.exists(ws_dep):
                _copy_file_with_perms(main_dep_path, ws_dep, readonly=True)
        culprit_rel = os.path.relpath(target_to_mutate, main_root)
        return attribution.AttributionOutcome(
            accepted=True,
            message=f"[BLAME] {culprit_rel}: {critique}",
            affected_nodes=[],
        )

    # Contract: Resolves target file; appends feedback diagnostic, marks dirty in metadata, and synchronizes workspace copy.
    def fail_target_file(
        self,
        target_file: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> attribution.AttributionOutcome:
        """Records task failure for a target file."""
        ws_root = os.path.realpath(workspace_root or os.getcwd())
        meta: Optional[Dict[str, Any]] = None
        meta_p = os.path.join(ws_root, ".cleanroom_role.json")
        # Reads .cleanroom_role.json from ws_root to inspect role context.
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        if repo_root:
            main_root = os.path.realpath(repo_root)
        else:
            try:
                import importlib
                ws_reg_mod = importlib.import_module("role_registry")
                ws_reg = get_singleton(ws_reg_mod.WorkspaceRegistry)  # type: ignore
                main_root = os.path.realpath(ws_reg.discover_repository_root(ws_root))
            except Exception:
                main_root = os.path.realpath(ws_root)

        bound_path = _resolve_bound_file_path(target_file)
        if bound_path and os.path.isfile(bound_path):
            full_p = bound_path
        else:
            full_p = _resolve_target_path(target_file, main_root)
            if not os.path.isfile(full_p):
                full_p = _resolve_target_path(target_file, ws_root)

        failure_reason = reason or "Verification failed"
        if not os.path.isfile(full_p):
            return attribution.AttributionOutcome(
                accepted=False,
                message=f"Error: Target '{target_file}' not found.",
                affected_nodes=[],
            )

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

        if ws_root != main_root and os.path.isfile(main_p):
            ws_p = os.path.join(ws_root, rel_p)
            if os.path.exists(ws_p):
                is_ro = not bool(os.stat(ws_p).st_mode & stat.S_IWUSR)
                _copy_file_with_perms(main_p, ws_p, readonly=is_ro)

        return attribution.AttributionOutcome(
            accepted=True,
            message=f"Marked failure on {target_to_mutate}: added DIRTY tag and updated LAST_CLEANED.",
            affected_nodes=[],
        )
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:55Z
# CHANGE: Record failure diagnostics and force dirty state through graph storage in fail_target, mark blamed culprits dirty in blame_target, resolve culprit files through the alias manager, and synchronize blamed source metadata headers
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        AttributionCoordinator,
        keys=[AttributionCoordinator, attribution.AttributionCoordinator],
        tier=AttributionCoordinator.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
