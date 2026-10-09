# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T22:40:00Z
# CHANGE: Remove initial implementation modification constraint on submission
# CODE_HASH: 5d45e5406ad0
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import json
import os
import shutil
import stat
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple
from support.lib.lifecycle import Singleton, get_singleton
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from . import control_submit, control_verification, src_metadata


def _is_test_file(target: str) -> bool:
    norm = target.strip().replace("\\", "/")
    return norm.endswith("_test.py") or "/tests/" in norm or norm.startswith("tests/")


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


def _find_part_dirs(repo_root: str, dir_scope: str) -> List[str]:
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


def _resolve_submit_target(
    target: str,
    repo_root: str,
    role_name: str,
    dir_scope: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    if not dir_scope and repo_root:
        try:
            for entry in os.listdir(repo_root):
                if os.path.isdir(os.path.join(repo_root, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                    dir_scope = entry
                    break
        except OSError:
            pass
    target_str = target.strip()
    cand_path = _resolve_target_path(target_str, repo_root)
    if os.path.isfile(cand_path):
        try:
            _, u_name, _ = _parse_unit_from_file_path(cand_path, repo_root)
            return cand_path, u_name
        except (KeyError, ValueError, OSError):
            pass
        clean_role = role_name.split(":")[-1].strip().lower()
        cfg = get_singleton(agent_node_config.NodeConfig)
        role_defs = getattr(cfg, "role_definitions", {})
        role_def = role_defs.get(clean_role)
        stem = os.path.splitext(os.path.basename(cand_path))[0]
        if role_def:
            src_pat = getattr(role_def, "src_pattern", "")
            if src_pat:
                _, pfx, sfx = _parse_pattern_info(src_pat)
                sfx_no_ext = os.path.splitext(sfx)[0] if sfx else ""
                if sfx_no_ext and stem.endswith(sfx_no_ext):
                    stem = stem[: -len(sfx_no_ext)]
                if pfx and stem.startswith(pfx):
                    stem = stem[len(pfx) :]
        return cand_path, stem

    clean_role = role_name.split(":")[-1].strip().lower()
    cfg = get_singleton(agent_node_config.NodeConfig)
    role_defs = getattr(cfg, "role_definitions", {})
    role_def = role_defs.get(clean_role)
    if role_def is None:
        raise KeyError(f"Role '{clean_role}' not found in NodeConfig.role_definitions")

    stem = os.path.splitext(os.path.basename(target_str))[0]
    src_pat = getattr(role_def, "src_pattern", "")
    _, pfx, sfx = _parse_pattern_info(src_pat)
    sfx_no_ext = os.path.splitext(sfx)[0] if sfx else ""
    if sfx_no_ext and stem.endswith(sfx_no_ext):
        stem = stem[: -len(sfx_no_ext)]
    if pfx and stem.startswith(pfx):
        stem = stem[len(pfx) :]

    part_dirs = _find_part_dirs(repo_root, dir_scope)
    is_auditor = bool(getattr(role_def, "audit_tag", None) or not src_pat)

    for pd in part_dirs:
        if is_auditor:
            fb_deps = [d.split(":")[-1] for d in getattr(role_def, "feedback_role_deps", ())]
            if fb_deps:
                fb_def = role_defs.get(fb_deps[0])
                fb_pat = getattr(fb_def, "src_pattern", "") if fb_def else ""
                if fb_pat:
                    cand = os.path.realpath(
                        os.path.join(
                            repo_root,
                            fb_pat.format(unit_dir=pd, unit_name=stem),
                        )
                    )
                    if os.path.isfile(cand):
                        return cand, stem
        else:
            if src_pat:
                cand = os.path.realpath(
                    os.path.join(
                        repo_root,
                        src_pat.format(unit_dir=pd, unit_name=stem),
                    )
                )
                if os.path.isfile(cand):
                    return cand, stem
    return None, None


_is_auditor_node = control_submit.is_auditor_node



class SubmissionCoordinator(control_submit.SubmissionCoordinator, Singleton):
    """Coordinates submission gating, change summary rules, and graph status mutation."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def resolve_submit_target(
        self,
        target: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "",
    ) -> tuple[str | None, str | None]:
        return _resolve_submit_target(target, repo_root, role_name, dir_scope)

    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> tuple[str, str, str]:
        return _parse_unit_from_file_path(file_path, repo_root)



    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_submit.SubmissionOutcome:
        """Validates submission gating rules and marks target clean in graph storage."""
        # 1. Verification precondition check
        verif = get_singleton(control_verification.VerificationEvaluator)
        verif_res = verif.evaluate_verification(target_node)
        if not verif_res.passed:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message=f"Verification is failing. Diagnostic output:\n{verif_res.diagnostic_output}",
            )

        # 2. In-batch dependencies must be clean
        storage = get_singleton(dag_storage.DagStorage)
        if in_batch_dependencies:
            for dep in in_batch_dependencies:
                if storage.is_dirty(dep):
                    return control_submit.SubmissionOutcome(
                        accepted=False,
                        message=f"Error: In-batch dependency '{dep.unit_address}:{dep.role_address}' must be submitted before dependent targets.",
                    )

        # 3. Session feedback check
        cfg = get_singleton(agent_node_config.NodeConfig)
        if getattr(cfg, "feedback", None) and not has_modifications:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message="Error: Session feedback is present but no workspace files were modified.",
            )

        # 4. Auditor role check
        is_auditor = _is_auditor_node(target_node)
        summary_str = str(change_summary or "").strip()

        if is_auditor and summary_str:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message="Error: Change summaries are not permitted for audit nodes.",
            )

        # 4. Change summary rules for non-auditors
        if not is_auditor:
            if has_modifications and not summary_str:
                return control_submit.SubmissionOutcome(
                    accepted=False,
                    message="Error: Workspace files were modified but change_summary was not provided.",
                )
            if not has_modifications and summary_str:
                return control_submit.SubmissionOutcome(
                    accepted=False,
                    message="Error: Change summaries are not permitted when submitting without workspace file modifications.",
                )

        # 5. Commit clean state with change description
        change_desc = dag_storage.ChangeDescription(summary_str) if summary_str else None
        storage.mark_node_clean(target_node, change_desc)

        return control_submit.SubmissionOutcome(
            accepted=True,
            message=f"Target '{target_node.unit_address}:{target_node.role_address}' submitted successfully.",
        )

    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> control_submit.SubmissionOutcome:
        """Submits a file target after validating gating rules and updating metadata."""
        ws_root = os.path.realpath(workspace_root or os.getcwd())
        meta: Optional[Dict[str, Any]] = None
        meta_p = os.path.join(ws_root, ".cleanroom_role.json")
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        r_name = role_name or (meta.get("role_name") or meta.get("role") if meta else "") or ""
        clean_role = r_name.split(":")[-1].strip().lower()
        d_scope = (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""
        if not d_scope:
            try:
                for entry in os.listdir(ws_root):
                    if os.path.isdir(os.path.join(ws_root, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                        d_scope = entry
                        break
            except OSError:
                pass

        main_root = repo_root or (meta.get("main_workspace_root") or meta.get("repo_root") if meta else None) or ws_root
        main_root = os.path.realpath(main_root)

        cfg = get_singleton(agent_node_config.NodeConfig)
        role_defs = getattr(cfg, "role_definitions", {})
        role_def = role_defs.get(clean_role)
        if role_def is None:
            raise KeyError(f"Role '{clean_role}' not found in NodeConfig.role_definitions")
        src_pat = getattr(role_def, "src_pattern", "")
        is_auditor = bool(getattr(role_def, "audit_tag", None) or not src_pat)

        # Auditor role submit: reject direct submission of verification/test files
        if is_auditor:
            if _is_test_file(target):
                return control_submit.SubmissionOutcome(
                    accepted=False,
                    message=(
                        f"Error: Cannot submit verification/test file '{target}'.\n"
                        f"In {clean_role.upper()}, your role is auditing the implementation target.\n"
                        f"Submit the audited implementation target instead: bin/submit <impl_file> (or bin/submit <unit_name>)"
                    ),
                )

        target_path, unit_name = _resolve_submit_target(target, ws_root, clean_role, d_scope)
        if not target_path or not os.path.isfile(target_path):
            target_path, unit_name = _resolve_submit_target(target, main_root, clean_role, d_scope)

        if not target_path or not os.path.isfile(target_path):
            return control_submit.SubmissionOutcome(
                accepted=False,
                message=f"Error: Target '{target}' not found on disk.",
            )

        # --- AUDITOR ROLE SUBMIT ---
        if is_auditor:
            audit_tag = getattr(role_def, "audit_tag", None) or f"{clean_role.upper()}_AUDIT"
            ref_root = ws_root if target_path.startswith(ws_root) else main_root
            part_dir, u_name, _ = _parse_unit_from_file_path(target_path, ref_root)
            active_unit = u_name or unit_name

            targets_to_audit: List[str] = []
            for fb_role in [d.split(":")[-1] for d in getattr(role_def, "feedback_role_deps", ())]:
                fb_def = role_defs.get(fb_role)
                fb_pat = getattr(fb_def, "src_pattern", "") if fb_def else ""
                if fb_pat:
                    fb_cand = os.path.join(
                        main_root,
                        fb_pat.format(unit_dir=part_dir, unit_name=active_unit),
                    )
                    if os.path.isfile(fb_cand) and fb_cand not in targets_to_audit:
                        targets_to_audit.append(fb_cand)

            rel_path = (
                os.path.relpath(target_path, ws_root)
                if target_path.startswith(ws_root)
                else os.path.relpath(target_path, main_root)
            )

            for tf in targets_to_audit:
                if os.path.isfile(tf):
                    src_metadata.stamp_audit(tf, clean_role)
                    src_metadata.update_metadata(tf, clear_dirty=True)

            # Reflect attested audits to local role workspace if present
            if ws_root != main_root:
                for tf in targets_to_audit:
                    rel = os.path.relpath(tf, main_root)
                    wt = os.path.join(ws_root, rel)
                    if os.path.isfile(tf) and os.path.isfile(wt):
                        _copy_file_with_perms(tf, wt, readonly=True)

            return control_submit.SubmissionOutcome(
                accepted=True,
                message=f"[AUDIT] {rel_path}: {audit_tag}",
            )

        # --- PRODUCER ROLE SUBMIT ---
        # 1. Enforce that read-only files cannot be submitted
        is_ro = False
        try:
            st = os.stat(target_path)
            is_ro = not bool(st.st_mode & stat.S_IWUSR)
        except OSError:
            is_ro = True

        if is_ro:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message=f"Error: Target '{target}' is read-only. Producer roles can only submit their own read-write targets.",
            )

        # 2. Enforce active directory scope matching
        if role_def.src_pattern:
            active_dir, active_pfx, active_sfx = _parse_pattern_info(role_def.src_pattern)
            if active_dir:
                fname = os.path.basename(target_path)
                parent = os.path.basename(os.path.dirname(target_path))
                if parent != active_dir or not (
                    fname.startswith(active_pfx) and fname.endswith(active_sfx)
                ):
                    return control_submit.SubmissionOutcome(
                        accepted=False,
                        message=f"Error: Target '{target}' is outside active role directory scope ({active_dir}/{active_pfx}*{active_sfx}).",
                    )

        summary_text = summary or f"Updated {os.path.basename(target_path)}"

        # 3. Symmetric change summary validation
        is_modified = src_metadata.is_code_modified(target_path)
        summary_provided = bool(summary and summary.strip())

        if is_modified and not summary_provided:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message=(
                    f"Error: Target '{target}' has been modified (CODE_HASH differs), but no change summary was provided.\n"
                    f"Usage: bin/submit {target} \"<concise change summary>\""
                ),
            )

        if not is_modified and summary_provided:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message=(
                    f"Error: Target '{target}' was not modified (CODE_HASH matches).\n"
                    f"A change summary must not be provided for an unchanged file.\n"
                    f"Usage to submit without changes: bin/submit {target}"
                ),
            )

        # 4. Copy modified file to canonical main workspace
        rel_path = (
            os.path.relpath(target_path, ws_root)
            if target_path.startswith(ws_root)
            else os.path.relpath(target_path, main_root)
        )
        main_file = os.path.join(main_root, rel_path)
        if ws_root != main_root and os.path.isfile(target_path):
            _copy_file_with_perms(target_path, main_file, readonly=False)

        part_dir, u_name, _ = _parse_unit_from_file_path(target_path, ws_root)
        active_unit = unit_name or u_name

        if is_modified:
            src_metadata.record_change(main_file, summary_text)
            msg = f"[CHANGE] {rel_path}: {summary_text}"
        else:
            src_metadata.mark_clean(main_file)
            msg = f"[CLEAN] {rel_path}"
        if ws_root != main_root and os.path.isfile(main_file):
            _copy_file_with_perms(main_file, target_path, readonly=False)
        return control_submit.SubmissionOutcome(accepted=True, message=msg)
