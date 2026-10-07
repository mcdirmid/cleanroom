# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T11:45:00Z
# CHANGE: add missing imports
# CODE_HASH: 96e0e4d00495
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import json
import os
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple
from support.lib.lifecycle import Singleton, get_singleton
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from . import control_attribution, src_metadata


def _can_run_bazel(main_root: str) -> bool:
    if os.environ.get("CLEANROOM_DIRECT_MUTATION") == "1":
        return False
    if not (
        os.path.isfile(os.path.join(main_root, "MODULE.bazel"))
        or os.path.isfile(os.path.join(main_root, "WORKSPACE"))
    ):
        return False
    return shutil.which("bazel") is not None


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
    cfg = get_singleton(agent_node_config.NodeConfig)
    role_defs = getattr(cfg, "role_definitions", {})
    if not role_defs:
        raise KeyError("No role definitions available in NodeConfig")
    for role in role_defs.values():
        src_pat = getattr(role, "src_pattern", "")
        if not src_pat:
            continue
        d_name, pfx, sfx = _parse_pattern_info(src_pat)
        if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
            return getattr(role, "role_name", "")
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
    cfg = get_singleton(agent_node_config.NodeConfig)
    role_def = getattr(cfg, "role_definitions", {}).get(role_name)
    if role_def is None:
        raise KeyError(f"Role '{role_name}' not found in NodeConfig.role_definitions")
    src_pat = getattr(role_def, "src_pattern", "")
    _, pfx, sfx = _parse_pattern_info(src_pat)
    unit_name = fname
    if pfx and unit_name.startswith(pfx):
        unit_name = unit_name[len(pfx) :]
    if sfx and unit_name.endswith(sfx):
        unit_name = unit_name[: -len(sfx)]
    part_dir = os.path.dirname(os.path.dirname(rel))
    return part_dir, unit_name, role_name


class AttributionCoordinator(control_attribution.AttributionCoordinator, Singleton):
    """Coordinates upstream blame attribution, single-paragraph validation, and failure cascades."""

    tier = agent_session.agent_session

    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[agent_file_alias.BoundFile]:
        """Matches a blame target value against configured blame targets for a node."""
        cfg = get_singleton(agent_node_config.NodeConfig)
        targets = list(cfg.blame_targets_by_node.get(node, set()))
        for bt in targets:
            bt_name = getattr(bt, "relative_path", getattr(bt, "short_name", ""))
            if val is not None and bt == val:
                return bt
            if val_str and bt_name == val_str:
                return bt
        if val_str:
            norm_v = val_str.lstrip("/")
            suffix_matches = [
                bt
                for bt in targets
                if getattr(bt, "relative_path", "").endswith("/" + norm_v)
                or norm_v.endswith("/" + getattr(bt, "relative_path", "").lstrip("/"))
            ]
            if len(suffix_matches) == 1:
                return suffix_matches[0]
            base_matches = [
                bt
                for bt in targets
                if os.path.basename(getattr(bt, "relative_path", ""))
                == os.path.basename(norm_v)
            ]
            if len(base_matches) == 1:
                return base_matches[0]
        return None

    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Attributes defect to an upstream dependency node."""
        storage = get_singleton(dag_storage.DagStorage)

        # 1. Single-paragraph critique validation
        if "\n" in explanation or "\r" in explanation:
            return control_attribution.AttributionOutcome(
                accepted=False,
                message="Error: Blame explanation must be a single paragraph without newlines.",
                affected_nodes=[],
            )

        # 2. Upstream dependency validation
        deps = storage.get_dependencies(source_node)
        upstream_nodes = {dep.node for dep in deps}
        if blame_target_node not in upstream_nodes:
            allowed = ", ".join(f"`{n.unit_address}:{n.role_address}`" for n in upstream_nodes)
            return control_attribution.AttributionOutcome(
                accepted=False,
                message=f"Error: Target '{blame_target_node.unit_address}:{blame_target_node.role_address}' is not an upstream dependency. Available: {allowed}",
                affected_nodes=[],
            )

        # 3. In-batch dependencies must be clean
        if in_batch_dependencies:
            for dep in in_batch_dependencies:
                if storage.is_dirty(dep):
                    return control_attribution.AttributionOutcome(
                        accepted=False,
                        message=f"Error: In-batch dependency '{dep.unit_address}:{dep.role_address}' must be submitted before dependent targets.",
                        affected_nodes=[],
                    )

        # 4. Inject feedback into culprit node (which marks culprit dirty per contract)
        feedback = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent(explanation.strip()),
            target=blame_target_node,
        )
        storage.add_message(feedback, to=blame_target_node)

        # 5. Mark source and fail in-batch dependents
        affected: List[dag_storage.DagNode] = [source_node]
        if in_batch_dependents:
            for dep in in_batch_dependents:
                affected.append(dep)

        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"Defect attributed to upstream dependency '{blame_target_node.unit_address}:{blame_target_node.role_address}'.",
            affected_nodes=affected,
        )

    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Records task failure and preserves dirty state on target node."""
        affected: List[dag_storage.DagNode] = [target_node]
        if in_batch_dependents:
            for dep in in_batch_dependents:
                affected.append(dep)

        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"Target '{target_node.unit_address}:{target_node.role_address}' failed: {explanation.strip()}",
            affected_nodes=affected,
        )

    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> control_attribution.AttributionOutcome:
        """Attributes defect blame to an upstream culprit file."""
        if "\n" in critique or "\r" in critique:
            return control_attribution.AttributionOutcome(
                accepted=False,
                message="Error: Critique must be a single line/paragraph without newline characters.",
                affected_nodes=[],
            )

        ws_root = os.path.realpath(workspace_root or os.getcwd())
        meta: Optional[Dict[str, Any]] = None
        meta_p = os.path.join(ws_root, ".cleanroom_role.json")
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        main_root = repo_root or (meta.get("main_workspace_root") or meta.get("repo_root") if meta else None) or ws_root
        main_root = os.path.realpath(main_root)

        dep_path = _resolve_target_path(culprit_file, main_root)
        if not os.path.exists(dep_path):
            dep_path = _resolve_target_path(culprit_file, ws_root)
        if not os.path.exists(dep_path):
            return control_attribution.AttributionOutcome(
                accepted=False,
                message=f"Error: Could not locate blame target '{culprit_file}'.",
                affected_nodes=[],
            )

        caller = caller_role or (meta.get("role_name") or meta.get("role") if meta else "") or os.environ.get("CLEANROOM_ROLE") or os.environ.get("USER") or "cleanroom"

        ref_root = main_root if dep_path.startswith(main_root) else ws_root
        part_dir, unit_name, blamed_role = _parse_unit_from_file_path(dep_path, ref_root)
        main_dep_path = os.path.join(main_root, os.path.relpath(dep_path, ref_root))

        if _can_run_bazel(main_root):
            blame_target = f"//{part_dir}:{unit_name}_{blamed_role}_blame"
            cmd = ["bazel", "run", blame_target, "--", critique]
            res = subprocess.run(cmd, cwd=main_root)
            if res.returncode != 0:
                return control_attribution.AttributionOutcome(
                    accepted=False,
                    message=f"Bazel blame target failed with exit code {res.returncode}",
                    affected_nodes=[],
                )
            if ws_root != main_root and os.path.isfile(main_dep_path):
                ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
                if os.path.exists(ws_dep):
                    _copy_file_with_perms(main_dep_path, ws_dep, readonly=True)
            return control_attribution.AttributionOutcome(
                accepted=True,
                message=f"✔ Attributed blame to {culprit_file} via Bazel {blame_target}",
                affected_nodes=[],
            )
        else:
            target_to_mutate = main_dep_path if os.path.exists(main_dep_path) else dep_path
            src_metadata.append_feedback(target_to_mutate, critique, sender=caller)
            src_metadata.mark_dirty(target_to_mutate, f"Blamed by {caller}: {critique}")
            src_metadata.update_metadata(
                target_to_mutate, last_cleaned=src_metadata.current_utc_timestamp()
            )
            if ws_root != main_root and os.path.isfile(main_dep_path):
                ws_dep = os.path.join(ws_root, os.path.relpath(dep_path, ref_root))
                if os.path.exists(ws_dep):
                    _copy_file_with_perms(main_dep_path, ws_dep, readonly=True)
            return control_attribution.AttributionOutcome(
                accepted=True,
                message=f"Appended FEEDBACK: into {target_to_mutate}",
                affected_nodes=[],
            )

    def fail_target_file(
        self,
        target_file: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> control_attribution.AttributionOutcome:
        """Records task failure for a target file."""
        ws_root = os.path.realpath(workspace_root or os.getcwd())
        meta: Optional[Dict[str, Any]] = None
        meta_p = os.path.join(ws_root, ".cleanroom_role.json")
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        main_root = repo_root or (meta.get("main_workspace_root") or meta.get("repo_root") if meta else None) or ws_root
        main_root = os.path.realpath(main_root)

        full_p = _resolve_target_path(target_file, main_root)
        if not os.path.isfile(full_p):
            full_p = _resolve_target_path(target_file, ws_root)

        failure_reason = reason or "Verification failed"
        if not os.path.isfile(full_p):
            return control_attribution.AttributionOutcome(
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

        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"Marked failure on {target_to_mutate}: added DIRTY tag and updated LAST_CLEANED.",
            affected_nodes=[],
        )
