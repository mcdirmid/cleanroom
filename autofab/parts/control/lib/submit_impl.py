from __future__ import annotations
import json
import os
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple
from support.lib.lifecycle import LifecycleResolutionError, auto_initialize, get_singleton, singleton
from autofab.parts.agent.lib import file_alias, node_config, agent_session
from autofab.parts.dag.lib import dag_storage
from autofab.parts.metadata.lib import src_metadata

try:
    from support.lib import app_info
except ImportError:
    import app_info  # type: ignore
from . import submit, verification


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
        from autofab.parts.workspace.lib import role_registry

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


def _role_src_patterns(role_def: Any) -> Sequence[str]:
    if hasattr(role_def, "src_patterns") and role_def.src_patterns:
        return role_def.src_patterns
    if isinstance(role_def, dict) and role_def.get("src_patterns"):
        return role_def["src_patterns"]
    single = _role_src_pattern(role_def)
    return [single] if single else ()


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
    if isinstance(role_def, dict):
        fb = role_def.get("feedback_role_deps") or ()
        sfb = role_def.get("star_feedback_role_deps") or ()
        return tuple(dict.fromkeys(list(fb) + list(sfb)))
    fb = getattr(role_def, "feedback_role_deps", ()) or ()
    sfb = getattr(role_def, "star_feedback_role_deps", ()) or ()
    return tuple(dict.fromkeys(list(fb) + list(sfb)))


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
            if (
                hasattr(cfg, "src_file_alias_by_node")
                and cfg.src_file_alias_by_node
                and node in cfg.src_file_alias_by_node
            ):
                return str(cfg.src_file_alias_by_node[node])
            if hasattr(cfg, "blame_targets_by_node") and cfg.blame_targets_by_node:
                for bt_set in cfg.blame_targets_by_node.values():
                    for bt in bt_set:
                        if hasattr(bt, "owning_node") and bt.owning_node == node:
                            return str(
                                bt.relative_path if hasattr(bt, "relative_path") else bt
                            )
            if hasattr(cfg, "read_only_files") and cfg.read_only_files:
                for ro in cfg.read_only_files:
                    if hasattr(ro, "owning_node") and ro.owning_node == node:
                        return str(
                            ro.relative_path if hasattr(ro, "relative_path") else ro
                        )
            if hasattr(cfg, "read_write_files") and cfg.read_write_files:
                for rw in cfg.read_write_files:
                    if hasattr(rw, "owning_node") and rw.owning_node == node:
                        return str(
                            rw.relative_path if hasattr(rw, "relative_path") else rw
                        )
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

    role = (
        str(node.role_address).split(":")[-1].strip().lower()
        if node.role_address
        else ""
    )
    role_defs = _get_role_definitions()
    if role in role_defs:
        src_pat = _role_src_pattern(role_defs[role])
        if src_pat:
            formatted = (
                src_pat.replace("{unit_dir}", pkg)
                .replace("{unit_name}", unit_name)
                .strip("/")
            )
            if formatted:
                return formatted

    return f"{pkg}/{unit_name}" if pkg else unit_name


def _alias_manager_workspace_root() -> Optional[str]:
    """Resolves the session workspace root declared by the alias manager."""
    try:
        workspace_root = get_singleton(file_alias.AliasManager).workspace_root
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        return None
    if workspace_root is None:
        return None
    return (
        str(workspace_root.path if hasattr(workspace_root, "path") else workspace_root)
        or None
    )


def _alias_manager_bound_path(target: str) -> Optional[str]:
    """Resolves a target string to a declared session bound file workspace path."""
    try:
        alias = get_singleton(file_alias.AliasManager).to_alias(target)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        return None
    if isinstance(alias, file_alias.BoundFile):
        return _bound_file_path(alias)
    return None


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
    mode = (
        (0o555 if readonly else 0o755) if executable else (0o444 if readonly else 0o644)
    )
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def _write_file_with_perms(
    path: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    mode = (
        (0o555 if readonly else 0o755) if executable else (0o444 if readonly else 0o644)
    )
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _project_for_role_workspace(content: str, filename: str, is_writable: bool) -> str:
    """Projects in-band metadata for role workspace: only change, feedback, and ephemeral code hash."""
    meta = src_metadata.extract_metadata_from_text(content, filename)
    if meta is None:
        return content
    code_hash = None
    if is_writable:
        code_hash = src_metadata.compute_code_hash(content, filename)
    return src_metadata.rewrite_metadata_in_text(
        content,
        filename,
        clear_last_cleaned=True,
        last_changed="",
        clear_audits=True,
        clear_dirty=True,
        code_hash=code_hash,
        clear_code_hash=not is_writable,
    )


def _copy_projected_file(src: str, dst: str, is_writable: bool) -> None:
    """Copies a file into a role workspace, projecting metadata headers with ephemeral code hashes on writable files."""
    try:
        with open(src, "r", encoding="utf-8") as f:
            content = f.read()
        projected = _project_for_role_workspace(
            content, os.path.basename(src), is_writable=is_writable
        )
        _write_file_with_perms(dst, projected, readonly=not is_writable)
    except (UnicodeDecodeError, OSError):
        _copy_file_with_perms(src, dst, readonly=not is_writable)


def _file_sha256(path: str) -> Optional[str]:
    import hashlib

    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _update_pull_manifest(
    workspace_dir: str, rel_path: str, main_file: str, ws_file: str
) -> None:
    try:
        state_dir = app_info.resolve_state_dir(workspace_dir)
        manifest_path = os.path.join(state_dir, "pull_manifest.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                p_manifest = json.load(f)
            p_files = p_manifest.setdefault("files", {})
            mh = _file_sha256(main_file)
            wh = _file_sha256(ws_file)
            if mh and wh:
                p_files[rel_path] = {"main_hash": mh, "ws_hash": wh}
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(p_manifest, f, indent=2)
    except Exception:
        pass


def _resolve_target_path(target: str, repo_root: str, dir_scope: str = "") -> str:
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
    if dir_scope:
        cand3 = os.path.realpath(
            os.path.join(norm_root, dir_scope, target_str.lstrip("/"))
        )
        if os.path.exists(cand3):
            return cand3
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


def _check_readonly_integrity(
    ws_root: str, main_root: str, dir_scope: str = ""
) -> Optional[str]:
    if (
        not ws_root
        or not main_root
        or os.path.realpath(ws_root) == os.path.realpath(main_root)
    ):
        return None
    scan_root = (
        os.path.join(ws_root, dir_scope)
        if dir_scope and os.path.isdir(os.path.join(ws_root, dir_scope))
        else ws_root
    )
    has_git = os.path.isdir(os.path.join(ws_root, ".git"))
    for root, dirs, files in os.walk(scan_root):
        dirs[:] = [
            d
            for d in dirs
            if d
            not in (
                "support",
                ".git",
                ".venv",
                "__pycache__",
                ".antigravity",
                "bin",
                ".bazel",
                "staging_tests",
                "guides",
            )
        ]
        if "__init__.py" in files:
            init_ws = os.path.join(root, "__init__.py")
            rel_p = os.path.relpath(init_ws, ws_root)

            # 1. If ws_root is a git repository, check whether rel_p is clean relative to HEAD
            if has_git:
                try:
                    res = subprocess.run(
                        ["git", "diff", "--quiet", "HEAD", "--", rel_p],
                        cwd=ws_root,
                        capture_output=True,
                    )
                    if res.returncode == 0:
                        continue
                except Exception:
                    pass

            # 2. Locate main_init across multiple potential layouts in main_root
            main_init = os.path.join(main_root, rel_p)
            if not os.path.isfile(main_init):
                for candidate_prefix in (
                    dir_scope,
                    os.path.join("benchmarks", "runs", dir_scope) if dir_scope else "",
                    os.path.join("benchmarks", "runs"),
                    os.path.join("benchmarks", "parts"),
                    "benchmarks",
                ):
                    if not candidate_prefix:
                        continue
                    cand = os.path.join(main_root, candidate_prefix, rel_p)
                    if os.path.isfile(cand):
                        main_init = cand
                        break

            if os.path.isfile(main_init):
                try:
                    with open(init_ws, "rb") as f_ws, open(main_init, "rb") as f_main:
                        if f_ws.read() != f_main.read():
                            return (
                                f"Read-only package file '{rel_p}' has been modified."
                            )
                except OSError:
                    pass
            elif not has_git:
                try:
                    with open(init_ws, "r", encoding="utf-8", errors="replace") as f_ws:
                        if f_ws.read().strip():
                            return (
                                f"Read-only package file '{rel_p}' has been populated."
                            )
                except OSError:
                    pass
    return None


def _resolve_file_role(file_path: str, repo_root: Optional[str] = None) -> str:
    norm = file_path.replace("\\", "/")
    fname = os.path.basename(norm)
    parent = os.path.basename(os.path.dirname(norm))
    role_defs = _get_role_definitions()
    if not role_defs:
        raise KeyError("No role definitions available in NodeConfig")
    for role in role_defs.values():
        src_pats = _role_src_patterns(role)
        for pat in src_pats:
            d_name, pfx, sfx = _parse_pattern_info(pat)
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
    parent = os.path.basename(os.path.dirname(rel))
    role_name = _resolve_file_role(rel, repo_root=repo_root)
    role_defs = _get_role_definitions()
    role_def = role_defs.get(role_name)
    if role_def is None:
        raise KeyError(f"Role '{role_name}' not found in NodeConfig.role_definitions")
    src_pats = _role_src_patterns(role_def)
    unit_name = fname
    for pat in src_pats:
        d_name, pfx, sfx = _parse_pattern_info(pat)
        if parent == d_name and fname.startswith(pfx) and fname.endswith(sfx):
            u_cand = fname
            if pfx and u_cand.startswith(pfx):
                u_cand = u_cand[len(pfx) :]
            if sfx and u_cand.endswith(sfx):
                u_cand = u_cand[: -len(sfx)]
            unit_name = u_cand
            break
    part_dir = os.path.dirname(os.path.dirname(rel))
    return part_dir, unit_name, role_name


def _resolve_submit_target(
    target: str,
    repo_root: str,
    role_name: str,
    dir_scope: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    target_str = target.strip()
    cand_path = _resolve_target_path(target_str, repo_root, dir_scope)
    if os.path.isfile(cand_path):
        try:
            _, u_name, _ = _parse_unit_from_file_path(cand_path, repo_root)
            return cand_path, u_name
        except (KeyError, ValueError, OSError):
            pass
        clean_role = role_name.split(":")[-1].strip().lower()
        role_defs = _get_role_definitions()
        role_def = role_defs.get(clean_role)
        stem = os.path.splitext(os.path.basename(cand_path))[0]
        if role_def:
            src_pat = _role_src_pattern(role_def)
            if src_pat:
                _, pfx, sfx = _parse_pattern_info(src_pat)
                sfx_no_ext = os.path.splitext(sfx)[0] if sfx else ""
                if sfx_no_ext and stem.endswith(sfx_no_ext):
                    stem = stem[: -len(sfx_no_ext)]
                if pfx and stem.startswith(pfx):
                    stem = stem[len(pfx) :]
        return cand_path, stem

    clean_role = role_name.split(":")[-1].strip().lower()
    role_defs = _get_role_definitions()
    role_def = role_defs.get(clean_role)
    if role_def is None:
        raise KeyError(f"Role '{clean_role}' not found in NodeConfig.role_definitions")

    stem = os.path.splitext(os.path.basename(target_str))[0]
    src_pat = _role_src_pattern(role_def)
    _, pfx, sfx = _parse_pattern_info(src_pat)
    sfx_no_ext = os.path.splitext(sfx)[0] if sfx else ""
    if sfx_no_ext and stem.endswith(sfx_no_ext):
        stem = stem[: -len(sfx_no_ext)]
    if pfx and stem.startswith(pfx):
        stem = stem[len(pfx) :]

    part_dirs = _find_part_dirs(repo_root, dir_scope)
    is_auditor = bool(_role_audit_tag(role_def) or not src_pat)

    for pd in part_dirs:
        if is_auditor:
            raw_fb = _role_feedback_deps(role_def)
            fb_deps = [d.split(":")[-1] for d in (raw_fb or ())]
            if fb_deps:
                fb_def = role_defs.get(fb_deps[0])
                fb_pat = _role_src_pattern(fb_def) if fb_def else ""
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
            for pat in _role_src_patterns(role_def):
                cand = os.path.realpath(
                    os.path.join(
                        repo_root,
                        pat.format(unit_dir=pd, unit_name=stem),
                    )
                )
                if os.path.isfile(cand):
                    return cand, stem
    return None, None


def _is_auditor_node(node: dag_storage.DagNode) -> bool:
    """Checks whether the node's role is classified as an auditor role."""
    role_clean = node.role_address.split(":")[-1].strip().lower()
    return src_metadata.is_auditor_role(role_clean)


@singleton
class SubmissionCoordinator(submit.SubmissionCoordinator):
    """Coordinates submission gating, change summary rules, and graph status mutation."""


    def __init__(self) -> None:
        pass

    # Contract: Resolves a target specification to a canonical or workspace file path and unit name.
    def resolve_submit_target(
        self,
        target: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "",
    ) -> tuple[str | None, str | None]:
        return _resolve_submit_target(target, repo_root, role_name, dir_scope)

    # Contract: Parses part directory, unit name, and role name from file path.
    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> tuple[str, str, str]:
        return _parse_unit_from_file_path(file_path, repo_root)

    # Contract: Validates verification passes, in-batch dependencies clean, session feedback resolved, and change summary matches role and modifications; commits clean state.
    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> submit.SubmissionOutcome:
        """Validates submission gating rules and marks target clean in graph storage."""
        # 1. Verification precondition check
        verif = get_singleton(verification.VerificationEvaluator)
        verif_res = verif.evaluate_verification(target_node)
        if not verif_res.passed:
            return submit.SubmissionOutcome(
                accepted=False,
                message=f"Verification is failing. Diagnostic output:\n{verif_res.diagnostic_output}",
            )

        # 2. In-batch dependencies must be clean
        storage = get_singleton(dag_storage.DagStorage)
        if in_batch_dependencies:
            for dep in in_batch_dependencies:
                if storage.is_dirty(dep):
                    return submit.SubmissionOutcome(
                        accepted=False,
                        message=f"Error: In-batch dependency '{_node_display_alias(dep)}' must be submitted before dependent targets.",
                    )

        # 3. Session feedback check
        cfg = get_singleton(node_config.NodeConfig)
        has_feedback = bool(cfg.feedback) if hasattr(cfg, "feedback") else False
        if has_feedback and not has_modifications:
            return submit.SubmissionOutcome(
                accepted=False,
                message="Error: Session feedback is present but no workspace files were modified. You must modify workspace files to address feedback before submitting, or call fail if the feedback cannot be resolved.",
            )

        # 4. Auditor role check
        is_auditor = _is_auditor_node(target_node)
        summary_str = str(change_summary or "").strip()

        if is_auditor and summary_str:
            return submit.SubmissionOutcome(
                accepted=False,
                message="Error: Change summaries are not permitted for audit nodes.",
            )

        # 4. Change summary rules for non-auditors
        if not is_auditor:
            if has_modifications and not summary_str:
                return submit.SubmissionOutcome(
                    accepted=False,
                    message="Error: Workspace files were modified but change_summary was not provided.",
                )
            if not has_modifications and summary_str:
                return submit.SubmissionOutcome(
                    accepted=False,
                    message="Error: Change summaries are not permitted when submitting without workspace file modifications.",
                )

        # 5. Commit clean state with change description
        change_desc = (
            dag_storage.ChangeDescription(summary_str) if summary_str else None
        )
        storage.mark_node_clean(target_node, change_desc)

        return submit.SubmissionOutcome(
            accepted=True,
            message=f"Target '{_node_display_alias(target_node)}' submitted successfully.",
        )

    # Contract: Submits file target; validates role targets, write permissions, scope, and modification/summary rules; updates in-band metadata and reflects to workspace.
    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> submit.SubmissionOutcome:
        """Submits a file target after validating gating rules and updating metadata."""
        ws_root = os.path.realpath(
            workspace_root or _alias_manager_workspace_root() or os.getcwd()
        )
        meta: Optional[Dict[str, Any]] = None
        for desc_name in app_info.get_role_descriptors():
            meta_p = os.path.join(ws_root, desc_name)
            if os.path.isfile(meta_p):
                try:
                    with open(meta_p, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    break
                except (json.JSONDecodeError, OSError):
                    pass

        r_name = (
            role_name
            or (meta.get("role_name") or meta.get("role") if meta else "")
            or ""
        )
        main_scope = str(meta.get("main_dir_scope") or "").strip("/") if meta else ""
        ws_scope = str(meta.get("dir_scope") or "").strip("/") if meta else ""
        clean_role = r_name.split(":")[-1].strip().lower()
        d_scope = (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""

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

        integrity_violation = _check_readonly_integrity(
            ws_root, main_root, dir_scope=d_scope
        )
        if integrity_violation:
            return submit.SubmissionOutcome(
                accepted=False,
                message=(
                    f"Error: Workspace integrity check failed: {integrity_violation}\n"
                    f"Workers are strictly prohibited from modifying package __init__.py or files outside their role's declared src_patterns."
                ),
            )

        role_defs = _get_role_definitions()
        role_def = role_defs.get(clean_role)
        if role_def is None:
            raise KeyError(
                f"Role '{clean_role}' not found in NodeConfig.role_definitions"
            )
        src_pat = _role_src_pattern(role_def)
        role_audit_tag = _role_audit_tag(role_def)
        is_auditor = bool(role_audit_tag or not src_pat)

        # Auditor role submit: reject direct submission of verification/test files
        if is_auditor:
            if _is_test_file(target):
                return submit.SubmissionOutcome(
                    accepted=False,
                    message=(
                        f"Error: Cannot submit verification/test file '{target}'.\n"
                        f"In {clean_role.upper()}, your role is auditing the implementation target.\n"
                        f"Submit the audited implementation target instead: bin/submit <impl_file> (or bin/submit <unit_name>)"
                    ),
                )

        target_path, unit_name = _resolve_submit_target(
            target, ws_root, clean_role, d_scope
        )
        if not target_path or not os.path.isfile(target_path):
            target_path, unit_name = _resolve_submit_target(
                target, main_root, clean_role, d_scope
            )

        if not target_path or not os.path.isfile(target_path):
            bound_path = _alias_manager_bound_path(target)
            if bound_path and os.path.isfile(bound_path):
                target_path = bound_path
                try:
                    _, unit_name, _ = _parse_unit_from_file_path(
                        bound_path,
                        main_root if bound_path.startswith(main_root) else ws_root,
                    )
                except (KeyError, ValueError, OSError):
                    pass

        if not target_path or not os.path.isfile(target_path):
            return submit.SubmissionOutcome(
                accepted=False,
                message=f"Error: Target '{target}' not found on disk.",
            )

        # --- AUDITOR ROLE SUBMIT ---
        if is_auditor:
            audit_tag = _role_audit_tag(role_def) or f"{clean_role.upper()}_AUDIT"
            ref_root = ws_root if target_path.startswith(ws_root) else main_root
            part_dir, u_name, _ = _parse_unit_from_file_path(target_path, ref_root)
            active_unit = u_name or unit_name

            targets_to_audit: List[str] = []
            role_fb_deps = _role_feedback_deps(role_def)
            for fb_role in [d.split(":")[-1] for d in role_fb_deps]:
                fb_def = role_defs.get(fb_role)
                fb_pat = _role_src_pattern(fb_def) if fb_def else ""
                if fb_pat:
                    main_part_dir = part_dir
                    if (
                        main_scope
                        and ws_scope
                        and main_scope != ws_scope
                        and part_dir.startswith(ws_scope + "/")
                    ):
                        main_part_dir = main_scope + "/" + part_dir[len(ws_scope) + 1 :]
                    fb_cand = os.path.join(
                        main_root,
                        fb_pat.format(unit_dir=main_part_dir, unit_name=active_unit),
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
                    rel = os.path.relpath(tf, main_root).replace("\\", "/")
                    ws_rel = rel
                    if (
                        main_scope
                        and ws_scope
                        and main_scope != ws_scope
                        and rel.startswith(main_scope + "/")
                    ):
                        ws_rel = ws_scope + "/" + rel[len(main_scope) + 1 :]
                    wt = os.path.join(ws_root, ws_rel)
                    if os.path.isfile(tf) and os.path.isfile(wt):
                        _copy_file_with_perms(tf, wt, readonly=True)

            return submit.SubmissionOutcome(
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
            return submit.SubmissionOutcome(
                accepted=False,
                message=f"Error: Target '{target}' is read-only. Producer roles can only submit their own read-write targets.",
            )

        # 2. Enforce active directory scope matching
        src_pats = _role_src_patterns(role_def)
        if src_pats:
            fname = os.path.basename(target_path)
            parent = os.path.basename(os.path.dirname(target_path))
            matched_any = False
            for pat in src_pats:
                active_dir, active_pfx, active_sfx = _parse_pattern_info(pat)
                if not active_dir or (
                    parent == active_dir
                    and fname.startswith(active_pfx)
                    and fname.endswith(active_sfx)
                ):
                    matched_any = True
                    break
            if not matched_any:
                scopes_desc = ", ".join(
                    f"{_parse_pattern_info(p)[0]}/{_parse_pattern_info(p)[1]}*{_parse_pattern_info(p)[2]}"
                    for p in src_pats
                )
                return submit.SubmissionOutcome(
                    accepted=False,
                    message=f"Error: Target '{target}' is outside active role directory scope ({scopes_desc}).",
                )

        summary_text = summary or f"Updated {os.path.basename(target_path)}"

        # 3. Symmetric change summary validation
        is_modified = src_metadata.is_code_modified(target_path)
        summary_provided = bool(summary and summary.strip())

        if is_modified and not summary_provided:
            return submit.SubmissionOutcome(
                accepted=False,
                message=(
                    f"Error: Target '{target}' has been modified (CODE_HASH differs), but no change summary was provided.\n"
                    f'Usage: bin/submit {target} "<concise change summary>"'
                ),
            )

        if not is_modified and summary_provided:
            return submit.SubmissionOutcome(
                accepted=False,
                message=(
                    f"Error: Target '{target}' was not modified (CODE_HASH matches).\n"
                    f"A change summary must not be provided for an unchanged file.\n"
                    f"Usage to submit without changes: bin/submit {target}"
                ),
            )

        # 4. Copy modified file to canonical main workspace
        rel_path = (
            os.path.relpath(target_path, ws_root).replace("\\", "/")
            if target_path.startswith(ws_root)
            else os.path.relpath(target_path, main_root).replace("\\", "/")
        )
        main_rel_path = rel_path
        if (
            main_scope
            and ws_scope
            and main_scope != ws_scope
            and rel_path.startswith(ws_scope + "/")
        ):
            main_rel_path = main_scope + "/" + rel_path[len(ws_scope) + 1 :]
        main_file = os.path.join(main_root, main_rel_path)
        part_dir, u_name, _ = _parse_unit_from_file_path(target_path, ws_root)
        active_unit = unit_name or u_name

        if is_modified:
            if ws_root != main_root and os.path.isfile(target_path):
                _copy_file_with_perms(target_path, main_file, readonly=False)
            src_metadata.record_change(main_file, summary_text)
            src_metadata.update_metadata(main_file, clear_code_hash=True)
            msg = f"[CHANGE] {rel_path}: {summary_text}"
        else:
            src_metadata.mark_clean(main_file)
            src_metadata.update_metadata(main_file, clear_code_hash=True)
            msg = f"[CLEAN] {rel_path}"
        if ws_root != main_root and os.path.isfile(main_file):
            _copy_projected_file(main_file, target_path, is_writable=True)
            _update_pull_manifest(ws_root, rel_path, main_file, target_path)

        # Synchronize any companion files declared in src_pats for this unit
        if src_pats and part_dir and active_unit:
            for pat in src_pats:
                comp_rel = pat.format(unit_dir=part_dir, unit_name=active_unit)
                ws_comp = os.path.join(ws_root, comp_rel)
                main_comp_rel = comp_rel
                if (
                    main_scope
                    and ws_scope
                    and main_scope != ws_scope
                    and comp_rel.startswith(ws_scope + "/")
                ):
                    main_comp_rel = main_scope + "/" + comp_rel[len(ws_scope) + 1 :]
                main_comp = os.path.join(main_root, main_comp_rel)
                if os.path.abspath(ws_comp) == os.path.abspath(target_path):
                    continue
                if os.path.isfile(ws_comp):
                    comp_mod = src_metadata.is_code_modified(ws_comp)
                    if ws_root != main_root:
                        _copy_file_with_perms(ws_comp, main_comp, readonly=False)
                    if comp_mod:
                        src_metadata.record_change(main_comp, summary_text)
                        src_metadata.update_metadata(main_comp, clear_code_hash=True)
                    else:
                        src_metadata.mark_clean(main_comp)
                        src_metadata.update_metadata(main_comp, clear_code_hash=True)
                    if ws_root != main_root and os.path.isfile(main_comp):
                        _copy_projected_file(main_comp, ws_comp, is_writable=True)
                        _update_pull_manifest(ws_root, comp_rel, main_comp, ws_comp)

        return submit.SubmissionOutcome(accepted=True, message=msg)


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-31T22:35:00Z
# CHANGE: Synchronize all declared companion source pattern files on producer submission
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

__initialize__ = auto_initialize()
_initialize_ = __initialize__
