"""Low-level implementation for commands_impl."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleResolutionError, auto_initialize, get_default_registry, get_singleton, singleton
from autofab.parts.agent.lib import node_config, session as agent_session
from autofab.parts.control.lib import (
    attribution,
    submit,
)
from autofab.parts.workspace.lib import (
    provision,
    role_registry,
    sync,
)

try:
    from support.lib import app_info, structured_blame
except ImportError:
    import app_info  # type: ignore
    import structured_blame  # type: ignore
from . import (
    coverage,
    check,
    commands,
    pending,
)
from autofab.parts.metadata.lib import src_metadata

BLAME_BUFFER_FILE = getattr(
    app_info, "DEFAULT_BLAME_BUFFER_FILE", ".autofab_blame_buffer.json"
)
STAGED_BLAME_FILE = ".autofab_staged_blame.json"


def _load_staged_blames(ws_root: str) -> List[Dict[str, Any]]:
    buf_path = os.path.join(ws_root, STAGED_BLAME_FILE)
    if os.path.isfile(buf_path):
        try:
            with open(buf_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [e for e in data if isinstance(e, dict)]
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _save_staged_blames(ws_root: str, entries: List[Dict[str, Any]]) -> None:
    buf_path = os.path.join(ws_root, STAGED_BLAME_FILE)
    try:
        with open(buf_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
    except OSError:
        pass


def _clear_staged_blames(ws_root: str) -> None:
    buf_path = os.path.join(ws_root, STAGED_BLAME_FILE)
    if os.path.isfile(buf_path):
        try:
            os.remove(buf_path)
        except OSError:
            pass


def _record_blame_buffer(
    ws_root: str,
    culprit_file: str,
    critique: str = "",
    caller: str = "",
    missing_spans: Optional[List[Any]] = None,
) -> None:
    """Records blamed target entry into workspace blame buffer."""
    culprit_rel = culprit_file.lstrip("/")
    entry: Dict[str, Any] = {
        "target": culprit_rel,
        "explanation": critique,
        "blamed_by": caller or "role workspace",
    }
    if missing_spans is not None:
        entry["missing_spans"] = missing_spans
    candidate_buffers = app_info.get_blame_buffer_filenames()
    for bname in sorted(candidate_buffers):
        buf_path = os.path.join(ws_root, bname)
        entries: List[Dict[str, Any]] = []
        if os.path.isfile(buf_path):
            try:
                with open(buf_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        entries = [e for e in data if isinstance(e, dict)]
            except (OSError, json.JSONDecodeError):
                entries = []
        if not any(
            e.get("target") == culprit_rel and e.get("missing_spans") == missing_spans
            for e in entries
        ):
            entries.append(entry)
        try:
            with open(buf_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except OSError:
            pass


def _is_auditor_role(role_name: str, repo_root: Optional[str] = None) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    try:
        reg = get_singleton(role_registry.WorkspaceRegistry)
        r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
        return bool(
            r_def.audit_tag or not r_def.src_pattern or not r_def.writable_file_patterns
        )
    except Exception:
        return (
            clean_r.endswith(("_qa", "_coverage", "_audit", "auditor", "audit"))
            or "qa" in clean_r
            or "audit" in clean_r
        )


def _is_role_writable_file(role_def: Any, file_path: str) -> bool:
    if not role_def:
        return True
    patterns = (
        role_def.writable_file_patterns
        if hasattr(role_def, "writable_file_patterns")
        else None
    ) or ()
    if not patterns:
        return False
    import fnmatch

    norm_path = file_path.replace("\\", "/")
    fname = os.path.basename(norm_path)
    for pat in patterns:
        pat_norm = pat.replace("\\", "/")
        if fnmatch.fnmatch(norm_path, f"*{pat_norm}") or fnmatch.fnmatch(
            fname, pat_norm
        ):
            return True
        if pat_norm.endswith("/*") and pat_norm[:-2] in norm_path:
            return True
        if "/*." in pat_norm:
            dir_part = pat_norm.split("/")[0]
            if f"/{dir_part}/" in norm_path or norm_path.startswith(f"{dir_part}/"):
                return True
    return False


# Contract: __orphan__ - discovers root of commissioned role workspace or repo root
def find_workspace_root() -> str:
    """Discovers root of commissioned role workspace or repo root."""
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        if any(
            os.path.isfile(os.path.join(curr, d))
            for d in app_info.get_role_descriptors()
        ):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()


# Contract: __orphan__ - loads role metadata from current workspace
def get_current_role_metadata() -> Optional[Dict[str, Any]]:
    """Loads role descriptor from current workspace if present."""
    ws_root = find_workspace_root()
    for d in app_info.get_role_descriptors():
        p = os.path.join(ws_root, d)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
    return None


def _resolve_main_root(
    ws_root: str, meta: Optional[Dict[str, Any]], repo_root: Optional[str] = None
) -> str:
    if repo_root:
        return os.path.realpath(repo_root)
    try:
        reg = get_singleton(role_registry.WorkspaceRegistry)
        return os.path.realpath(reg.discover_repository_root(ws_root))
    except (KeyError, LifecycleResolutionError):
        if meta and meta.get("main_repository_root"):
            return os.path.realpath(meta["main_repository_root"])
        env_main = app_info.get_main_root()
        if env_main and os.path.isdir(env_main):
            return os.path.realpath(env_main)
        curr = os.path.abspath(ws_root or os.getcwd())
        check_role = curr
        while check_role and check_role != os.path.dirname(check_role):
            if any(
                os.path.isfile(os.path.join(check_role, d))
                for d in app_info.get_role_descriptors()
            ):
                parent_dir = os.path.dirname(check_role)
                if (
                    os.path.basename(parent_dir)
                    in app_info.get_role_workspaces_containers()
                ):
                    return os.path.realpath(os.path.dirname(parent_dir))
                return os.path.realpath(parent_dir)
            check_role = os.path.dirname(check_role)
        return os.path.realpath(curr)


# Contract: __orphan__ - resolves path to log file in the directory containing parts
def resolve_log_path(target_or_path: str, repo_root: Optional[str] = None) -> str:
    """Resolves path to log file in the directory containing parts."""
    return app_info.resolve_log_path(
        target_or_path, repo_root=repo_root or find_workspace_root()
    )


# Contract: __orphan__ - appends action record message to log file in directory containing parts
def append_log(
    target_or_path: str,
    message: str,
    repo_root: Optional[str] = None,
) -> str:
    """Appends action record message to log file in directory containing parts."""
    return app_info.append_log(
        target_or_path, message, repo_root=repo_root or find_workspace_root()
    )


def _find_agent_node_config_module() -> Any:
    for k, m in list(sys.modules.items()):
        if (
            k in ("node_config", "agent_node_config")
            or k.endswith(".node_config")
            or k.endswith(".agent_node_config")
        ):
            if hasattr(m, "NodeConfig"):
                return m
    try:
        import importlib

        try:
            return importlib.import_module("autofab.parts.agent.lib.node_config")
        except ImportError:
            return importlib.import_module("node_config")
    except ImportError:
        pass
    return None


def _ensure_cli_node_config(main_root: Optional[str] = None) -> None:
    node_cfg_cls = node_config.NodeConfig
    cfg = None
    if node_cfg_cls is not None:
        try:
            cfg = get_singleton(node_cfg_cls)
        except (KeyError, LifecycleResolutionError):
            cfg = None

    reg = get_default_registry()
    try:
        ws_reg = get_singleton(role_registry.WorkspaceRegistry)
    except (KeyError, LifecycleResolutionError):
        try:
            from autofab.parts.workspace.lib import workspace_asm

            workspace_asm.__initialize__()
            ws_reg = get_singleton(role_registry.WorkspaceRegistry)
        except Exception:
            return
    ws_root = find_workspace_root()
    meta = get_current_role_metadata()
    resolved_main = _resolve_main_root(ws_root, meta, repo_root=main_root)
    roles = ws_reg.list_roles(repo_root=resolved_main)
    role_defs = {r.role_name: r for r in roles}

    if cfg is None:

        class CliNodeConfig:
            tier = agent_session.agent_session

            def __init__(self, r_defs: Dict[str, Any]) -> None:
                self.role_definitions = r_defs
                self.read_only_files = set()
                self.read_write_files = set()
                self.allows_step_mode = False
                self.is_step_mode = False
                self.guide_file = None
                self.templates = {}
                self.template_parameters = {}
                self.guide = None
                self.blame_targets_by_node = {}
                self.verification_checks = ()
                self.verification_checks_by_node = {}
                self.src_file_alias_by_node = {}
                self.verification_success_message = None
                self.feedback = ()
                self.per_node_info_by_node = {}

        cli_cfg = CliNodeConfig(role_defs)
        keys: List[Any] = [CliNodeConfig, node_config.NodeConfig]
        reg.register_instance(
            cli_cfg,
            keys=keys,
            tier=agent_session.agent_session,
        )
    else:
        cfg_any: Any = cfg
        if not hasattr(cfg_any, "role_definitions") or not cfg_any.role_definitions:
            setattr(cfg_any, "role_definitions", role_defs)


# Contract: Realizes substantive domain operations for Autofab role workspaces in agent_session tier.
@singleton
class WorkspaceCommandHandler(commands.WorkspaceCommandHandler):
    """Realizes substantive domain operations for Autofab role workspaces."""


    def __init__(self) -> None:
        pass

    def _checker(self) -> check.WorkspaceChecker:
        return get_singleton(check.WorkspaceChecker)

    # Contract: Delegates work discovery directly to WorkspaceChecker.run_get_work.
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        return self._checker().run_get_work(
            dir_scope=dir_scope,
            repo_root=repo_root,
            force=force,
            batch_size=batch_size,
        )

    # Contract: Delegates file verification directly to WorkspaceChecker.run_check_files.
    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        return self._checker().run_check_files(
            target=target,
            repo_root=repo_root,
        )

    # Contract: Validates target, executes verification unless bypassed, delegates to SubmissionCoordinator, logs to event log, and removes from pending work.
    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        no_verify: bool = False,
    ) -> int:
        """Verifies target and stamps in-band metadata or <ROLE>_AUDIT directly in main."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        role_name = str(meta.get("role_name") or meta.get("role") or "") if meta else ""
        clean_role = role_name.split(":")[-1].strip().lower() if role_name else ""
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)

        # Check for staged blame
        staged_blames = _load_staged_blames(ws_root)
        if staged_blames:
            attr_coord = get_singleton(attribution.AttributionCoordinator)
            committed_count = 0
            for item in staged_blames:
                c_file = item["culprit_file"]
                c_critique = item["critique"]
                c_caller = item.get("caller") or role_name
                outcome = attr_coord.blame_culprit_file(
                    culprit_file=c_file,
                    critique=c_critique,
                    repo_root=main_root,
                    workspace_root=ws_root,
                    caller_role=c_caller,
                )
                if outcome.message:
                    print(outcome.message)
                if outcome.accepted:
                    blame_msg = outcome.message or f"✔ Blamed {c_file}"
                    if c_critique and c_critique not in blame_msg:
                        blame_msg = f"{blame_msg}: {c_critique}"
                    append_log(c_file, blame_msg, repo_root=main_root)
                    if ws_root != main_root:
                        try:
                            append_log(c_file, blame_msg, repo_root=ws_root)
                        except OSError:
                            pass
                    _record_blame_buffer(
                        ws_root,
                        c_file,
                        critique=c_critique,
                        caller=c_caller,
                        missing_spans=item.get("missing_spans"),
                    )
                    committed_count += 1
            _clear_staged_blames(ws_root)
            remaining_work: List[str] = []
            if meta:
                pending_mgr = get_singleton(pending.WorkspacePendingManager)
                pending_targets = list(pending_mgr.get_pending_work(ws_root))
                pending_mgr.remove_pending_target(ws_root, target)
                if (
                    len(pending_targets) == 1
                    and list(pending_mgr.get_pending_work(ws_root)) == pending_targets
                ):
                    pending_mgr.remove_pending_target(ws_root, pending_targets[0])
                remaining_work = list(pending_mgr.get_pending_work(ws_root))
            next_step_msg = (
                "MANDATORY: Run 'bin/get_work' now to inspect remaining units."
                if remaining_work
                else "[ROUND CONCLUSION DIRECTIVE] All assigned targets are resolved. Conclude your round immediately with summary text and ZERO further tool calls (do NOT run 'bin/get_work' or 'bin/check_files')."
            )
            print(
                f"[BLAME DELIVERED] Committed {committed_count} blame item(s) for '{target}' and returned to upstream author(s).\n"
                "Your work on this target is 100% COMPLETE.\n"
                f"{next_step_msg}\n"
                "DO NOT re-run 'bin/check_files' or attempt to debug the author's code."
            )
            return 0 if committed_count > 0 else 1

        is_auditor = (
            _is_auditor_role(clean_role, repo_root=main_root) if clean_role else False
        )
        if not no_verify and not is_auditor:
            sub_coord = get_singleton(submit.SubmissionCoordinator)
            d_scope = (
                (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""
            )
            target_path, _ = sub_coord.resolve_submit_target(
                target, ws_root, clean_role, d_scope
            )
            if (
                target_path
                and os.path.isfile(target_path)
                and src_metadata.is_code_modified(target_path)
            ):
                checker = get_singleton(check.WorkspaceChecker)
                if not checker.is_checked_since_modification(ws_root, target_path):
                    print(
                        f"Error: Target '{target}' has been modified, but 'bin/check_files' has not been run since the latest modifications.\n"
                        f"Run 'bin/check_files {target}' to verify errors before calling submit."
                    )
                    return 1

        if not no_verify:
            check_exit = self.run_check_files(target=target, repo_root=main_root)
            if check_exit != 0:
                is_auditor = (
                    _is_auditor_role(clean_role, repo_root=main_root)
                    if clean_role
                    else False
                )
                if is_auditor:
                    print(
                        f"Error: Cannot submit target '{target}' without preceding blame.\n"
                        f"In auditor roles, manual submission is only permitted to commit staged blame feedback after running 'bin/blame <culprit> \"<critique>\"', or run 'bin/fail {target} \"<reason>\"'."
                    )
                else:
                    print(
                        f"[FAIL] Verification checks failed for '{target}'. Submission rejected."
                    )
                return 1

        sub_coord = get_singleton(submit.SubmissionCoordinator)
        outcome = sub_coord.submit_target_file(
            target=target,
            summary=summary,
            repo_root=main_root,
            workspace_root=ws_root,
            role_name=role_name,
        )
        if outcome.message:
            print(outcome.message)

        if outcome.accepted:
            if outcome.message:
                append_log(target, outcome.message, repo_root=main_root)
                if ws_root != main_root:
                    try:
                        append_log(target, outcome.message, repo_root=ws_root)
                    except OSError:
                        pass
            remaining_work: List[str] = []
            if meta:
                pending_mgr = get_singleton(pending.WorkspacePendingManager)
                pending_mgr.remove_pending_target(ws_root, target)
                remaining_work = list(pending_mgr.get_pending_work(ws_root))
            try:
                prov = get_singleton(provision.WorkspaceProvisioner)
                prov.unlock_workspace_directories(ws_root)
            except Exception:
                pass
            next_step_msg = (
                "Run 'bin/get_work' now to inspect remaining units."
                if remaining_work
                else "[ROUND CONCLUSION DIRECTIVE] All assigned targets are resolved. Conclude your round immediately with summary text and ZERO further tool calls (do NOT run 'bin/get_work' or 'bin/check_files')."
            )
            print(
                f"[SUBMIT DELIVERED] Target '{target}' submitted successfully.\n"
                f"{next_step_msg}"
            )
            return 0
        return 1

    # Contract: Delegates blame attribution to AttributionCoordinator, logs to event log, and removes from pending work.
    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes critique directly to upstream contract or culprit file in main."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)
        caller = (meta.get("role_name") or meta.get("role", "")) if meta else ""
        clean_caller = caller.split(":")[-1].strip().lower() if caller else ""

        if "\n" in critique or "\r" in critique:
            critique = " ".join(
                line.strip() for line in critique.splitlines() if line.strip()
            )
        if not critique.strip():
            print("Error: Critique cannot be empty.")
            return 1

        if structured_blame.is_structured_blame_active():
            parsed_blame, parse_errs = structured_blame.parse_structured_blame(critique)
            if parse_errs or parsed_blame is None:
                print(f"[STRUCTURED BLAME REJECTED]", file=sys.stderr)
                for err in parse_errs:
                    print(f"Error: {err}", file=sys.stderr)
                return 1

            val_errs = structured_blame.validate_structured_blame(
                parsed_blame,
                culprit_file=culprit_file,
                repo_root=main_root,
                workspace_root=ws_root,
                caller_role=caller,
            )
            if val_errs:
                print(f"[STRUCTURED BLAME REJECTED]", file=sys.stderr)
                for err in val_errs:
                    print(f"Error: {err}", file=sys.stderr)
                return 1

            critique = parsed_blame.to_critique_string()

        is_auditor = (
            _is_auditor_role(clean_caller, repo_root=main_root)
            if clean_caller
            else False
        )
        if not is_auditor:
            reg = get_singleton(role_registry.WorkspaceRegistry)
            r_def = None
            try:
                r_def = reg.resolve_role_definition(clean_caller, repo_root=main_root)
            except Exception:
                pass
            pending_mgr = get_singleton(pending.WorkspacePendingManager)
            pending_targets = pending_mgr.get_pending_work(ws_root)
            sub_coord = get_singleton(submit.SubmissionCoordinator)
            d_scope = (
                (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""
            )
            for pt in pending_targets:
                pt_path, _ = sub_coord.resolve_submit_target(
                    pt, ws_root, clean_caller, d_scope
                )
                if (
                    pt_path
                    and os.path.isfile(pt_path)
                    and _is_role_writable_file(r_def, pt_path)
                ):
                    if src_metadata.is_code_modified(pt_path):
                        checker = get_singleton(check.WorkspaceChecker)
                        if not checker.is_checked_since_modification(ws_root, pt_path):
                            print(
                                f"Error: Workspace target '{pt}' has been modified, but 'bin/check_files' has not been run since the latest modifications.\n"
                                f"Run 'bin/check_files {pt}' to verify errors before calling blame."
                            )
                            return 1

        is_cov_role = bool("coverage" in clean_caller)
        cov_status_path = os.path.join(ws_root, ".coverage_spans.json")
        cov_status: Optional[Dict[str, Any]] = None
        if is_cov_role and os.path.isfile(cov_status_path):
            try:
                with open(cov_status_path, "r", encoding="utf-8") as csf:
                    cov_status = json.load(csf)
            except Exception:
                cov_status = None

        if is_cov_role and cov_status and cov_status.get("missing_spans"):
            current_spans = cov_status.get("missing_spans")
            norm_culprit = culprit_file.replace("\\", "/").lower()
            cov_lib = str(cov_status.get("file_path", "")).replace("\\", "/").lower()
            cov_test = str(cov_status.get("test_path", "")).replace("\\", "/").lower()
            is_relevant_target = (
                not cov_lib
                or norm_culprit in cov_lib
                or cov_lib in norm_culprit
                or norm_culprit in cov_test
                or cov_test in norm_culprit
                or norm_culprit.endswith(("_test.py", "_pretense.py"))
            )
            if is_relevant_target:
                is_test_culprit = (
                    "/tests/" in norm_culprit
                    or "/pretense/" in norm_culprit
                    or norm_culprit.endswith(("_test.py", "_pretense.py"))
                )
                if cov_status.get("all_lib_pragma_required") and is_test_culprit:
                    print(
                        "Error: misattribution: no test-owned spans in this deficit. "
                        "All uncovered spans are [LIB-PRAGMA-REQUIRED] (raises *Error or precondition guard). "
                        "Blame the library module to wrap in 'with unreachable:' or use 'unreachable()' or restructure.",
                        file=sys.stderr,
                    )
                    return 1

                buf_path = os.path.join(ws_root, BLAME_BUFFER_FILE)
                if os.path.isfile(buf_path):
                    try:
                        with open(buf_path, "r", encoding="utf-8") as bf:
                            prev_entries = json.load(bf)
                        if isinstance(prev_entries, list):
                            culprit_rel = culprit_file.lstrip("/")
                            for pe in prev_entries:
                                if (
                                    isinstance(pe, dict)
                                    and pe.get("target") == culprit_rel
                                ):
                                    if pe.get("missing_spans") == current_spans:
                                        print(
                                            "Error: repeating identical blame against the same uncovered span set is prohibited. "
                                            "Previous feedback failed to achieve coverage; reclassify open spans or evaluate whether library code is unreachable.",
                                            file=sys.stderr,
                                        )
                                        return 1
                    except Exception:
                        pass

        # Validate that culprit file can be located
        c_path = None
        if clean_caller:
            try:
                sub_coord = get_singleton(submit.SubmissionCoordinator)
                d_scope = (
                    (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""
                )
                c_path, _ = sub_coord.resolve_submit_target(
                    culprit_file, ws_root, clean_caller, d_scope
                )
                if not c_path or not os.path.exists(c_path):
                    c_path, _ = sub_coord.resolve_submit_target(
                        culprit_file, main_root, clean_caller, d_scope
                    )
            except Exception:
                c_path = None
        if not c_path or not os.path.exists(c_path):
            cand_ws = os.path.join(ws_root, culprit_file.lstrip("/"))
            cand_main = os.path.join(main_root, culprit_file.lstrip("/"))
            if os.path.exists(cand_ws):
                c_path = cand_ws
            elif os.path.exists(cand_main):
                c_path = cand_main
            elif os.path.exists(culprit_file):
                c_path = culprit_file

        if not c_path or not os.path.exists(c_path):
            print(
                f"Error: Could not locate blame target '{culprit_file}'.",
                file=sys.stderr,
            )
            return 1

        if not meta:
            attr_coord = get_singleton(attribution.AttributionCoordinator)
            outcome = attr_coord.blame_culprit_file(
                culprit_file=culprit_file,
                critique=critique,
                repo_root=main_root,
                workspace_root=ws_root,
                caller_role=caller,
            )
            if outcome.message:
                print(outcome.message)
            if outcome.accepted:
                blame_msg = outcome.message or f"✔ Blamed {culprit_file}"
                if critique and critique not in blame_msg:
                    blame_msg = f"{blame_msg}: {critique}"
                append_log(culprit_file, blame_msg, repo_root=main_root)
                _record_blame_buffer(
                    ws_root,
                    culprit_file,
                    critique=critique,
                    caller=caller,
                    missing_spans=cov_status.get("missing_spans")
                    if cov_status
                    else None,
                )
                try:
                    prov = get_singleton(provision.WorkspaceProvisioner)
                    prov.unlock_workspace_directories(ws_root)
                except Exception:
                    pass
                return 0
            return 1

        # In role workspaces, validate that caller is configured to deliver feedback to culprit's role
        culprit_role = None
        try:
            reg = get_singleton(role_registry.WorkspaceRegistry)
            norm_c = (c_path or culprit_file).replace("\\", "/")
            c_fname = os.path.basename(norm_c)
            c_parent = os.path.basename(os.path.dirname(norm_c))
            for role in reg.list_roles(repo_root=main_root):
                pats = (
                    role.src_patterns
                    if hasattr(role, "src_patterns") and role.src_patterns
                    else ([role.src_pattern] if role.src_pattern else [])
                )
                for pat in pats:
                    clean = pat.replace("{unit_dir}/", "").replace("{unit_dir}\\", "")
                    if "/" in clean:
                        d_name, file_pattern = clean.split("/", 1)
                    else:
                        d_name, file_pattern = "", clean
                    if "{unit_name}" in file_pattern:
                        pfx, sfx = file_pattern.split("{unit_name}", 1)
                    elif "*" in file_pattern:
                        pfx, sfx = file_pattern.split("*", 1)
                    else:
                        pfx, sfx = "", file_pattern
                    if (
                        c_parent == d_name
                        and c_fname.startswith(pfx)
                        and c_fname.endswith(sfx)
                    ):
                        culprit_role = role.role_name
                        break
                if culprit_role:
                    break
        except Exception:
            pass

        if clean_caller and culprit_role:
            try:
                reg = get_singleton(role_registry.WorkspaceRegistry)
                r_def = reg.resolve_role_definition(clean_caller, repo_root=main_root)
                if r_def:
                    raw_fb = list(
                        getattr(r_def, "feedback_role_deps", ()) or ()
                    ) + list(getattr(r_def, "star_feedback_role_deps", ()) or ())
                    fb_deps = [d.split(":")[-1].strip().lower() for d in raw_fb]
                    blamed_clean = str(culprit_role).split(":")[-1].strip().lower()
                    if blamed_clean not in fb_deps:
                        print(
                            f"Error: Role '{caller}' is not configured to deliver feedback to role '{culprit_role}'.",
                            file=sys.stderr,
                        )
                        return 1
            except Exception:
                pass

        staged_entries = _load_staged_blames(ws_root)
        current_spans = cov_status.get("missing_spans") if cov_status else None
        staged_entries.append(
            {
                "culprit_file": culprit_file,
                "critique": critique,
                "caller": caller,
                "missing_spans": current_spans,
            }
        )
        _save_staged_blames(ws_root, staged_entries)
        print(
            f"[BLAME STAGED] Blame staged for '{culprit_file}'.\n"
            f"Critique: {critique}\n"
            f"Total staged blame item(s): {len(staged_entries)}.\n"
            "Run 'bin/blame <culprit_file> \"<critique>\"' to stage additional blame, or run 'bin/submit <target>' to commit blame and conclude."
        )
        return 0

    # Contract: Rejects active feedback on an unmodified target file and scrubs feedback from header.
    def run_reject(
        self,
        file_path: str,
        reason: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Rejects active feedback on an unmodified target file and scrubs feedback from header."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)
        caller = (meta.get("role_name") or meta.get("role", "")) if meta else ""
        clean_caller = caller.split(":")[-1].strip().lower() if caller else ""

        if not reason or not reason.strip():
            print("Error: Rejection reason cannot be empty.")
            return 1

        sub_coord = get_singleton(submit.SubmissionCoordinator)
        d_scope = (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""
        target_path, _ = sub_coord.resolve_submit_target(
            file_path, ws_root, clean_caller, d_scope
        )
        if not target_path or not os.path.isfile(target_path):
            target_path, _ = sub_coord.resolve_submit_target(
                file_path, main_root, clean_caller, d_scope
            )
        if not target_path or not os.path.isfile(target_path):
            cand_ws = os.path.join(ws_root, file_path.lstrip("/"))
            cand_main = os.path.join(main_root, file_path.lstrip("/"))
            if os.path.isfile(cand_ws):
                target_path = cand_ws
            elif os.path.isfile(cand_main):
                target_path = cand_main
            elif os.path.isfile(file_path):
                target_path = file_path

        if not target_path or not os.path.isfile(target_path):
            print(f"Error: Could not locate target '{file_path}'.")
            return 1

        # Strict Unchanged File Invariant
        if src_metadata.is_code_modified(target_path):
            print(
                f"Error: Cannot reject feedback on a modified file.\n"
                f"If you made code changes to '{file_path}', use 'bin/submit'. "
                f"Rejecting feedback asserts that your existing code is already compliant with the specification."
            )
            return 1

        # Must have active feedback to reject
        target_meta = src_metadata.extract_metadata(target_path)
        if not target_meta or not target_meta.feedback:
            print(
                f"Error: Target '{file_path}' does not have any active feedback to reject."
            )
            return 1

        # Scrub feedback from file header
        src_metadata.update_metadata(target_path, clear_feedback=True, clear_dirty=True)
        if ws_root != main_root and target_path.startswith(ws_root):
            rel = os.path.relpath(target_path, ws_root)
            main_p = os.path.join(main_root, rel)
            if os.path.isfile(main_p):
                src_metadata.update_metadata(
                    main_p, clear_feedback=True, clear_dirty=True
                )

        # Record rejection contest rationale out-of-band
        rejection_critique = f"[REJECTED] {reason.strip()}"
        _record_blame_buffer(
            ws_root,
            file_path,
            critique=rejection_critique,
            caller=caller,
        )
        append_log(file_path, rejection_critique, repo_root=main_root)
        if ws_root != main_root:
            try:
                append_log(file_path, rejection_critique, repo_root=ws_root)
            except OSError:
                pass

        # Clear from pending work
        if meta:
            pending_mgr = get_singleton(pending.WorkspacePendingManager)
            pending_targets = list(pending_mgr.get_pending_work(ws_root))
            pending_mgr.remove_pending_target(ws_root, file_path)
            if (
                len(pending_targets) == 1
                and list(pending_mgr.get_pending_work(ws_root)) == pending_targets
            ):
                pending_mgr.remove_pending_target(ws_root, pending_targets[0])

        try:
            prov = get_singleton(provision.WorkspaceProvisioner)
            prov.unlock_workspace_directories(ws_root)
        except Exception:
            pass

        print(
            f"[REJECT DELIVERED] Feedback rejected for '{file_path}'.\n"
            f"Reason: {reason.strip()}\n"
            "The active feedback block has been scrubbed from the file header.\n"
            "Run 'bin/get_work' now to inspect remaining units.\n"
            "If all ready targets are resolved, conclude your round immediately with summary text and ZERO further tool calls."
        )
        return 0

    # Contract: Delegates failure marking to AttributionCoordinator and removes from pending work.
    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty with DIRTY tag and appends failure diagnostics in main."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)
        caller = (meta.get("role_name") or meta.get("role", "")) if meta else ""
        clean_caller = caller.split(":")[-1].strip().lower() if caller else ""

        is_auditor = (
            _is_auditor_role(clean_caller, repo_root=main_root)
            if clean_caller
            else False
        )
        if not is_auditor:
            sub_coord = get_singleton(submit.SubmissionCoordinator)
            d_scope = (
                (meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else ""
            )
            target_path, _ = sub_coord.resolve_submit_target(
                file_path, ws_root, clean_caller, d_scope
            )
            if (
                target_path
                and os.path.isfile(target_path)
                and src_metadata.is_code_modified(target_path)
            ):
                checker = get_singleton(check.WorkspaceChecker)
                if not checker.is_checked_since_modification(ws_root, target_path):
                    print(
                        f"Error: Target '{file_path}' has been modified, but 'bin/check_files' has not been run since the latest modifications.\n"
                        f"Run 'bin/check_files {file_path}' to verify errors before calling fail."
                    )
                    return 1

        attr_coord = get_singleton(attribution.AttributionCoordinator)
        outcome = attr_coord.fail_target_file(
            target_file=file_path,
            reason=reason,
            repo_root=main_root,
            workspace_root=ws_root,
        )
        if outcome.message:
            print(outcome.message)

        if outcome.accepted:
            if meta:
                pending_mgr = get_singleton(pending.WorkspacePendingManager)
                pending_targets = list(pending_mgr.get_pending_work(ws_root))
                pending_mgr.remove_pending_target(ws_root, file_path)
                if (
                    len(pending_targets) == 1
                    and list(pending_mgr.get_pending_work(ws_root)) == pending_targets
                ):
                    pending_mgr.remove_pending_target(ws_root, pending_targets[0])
            try:
                prov = get_singleton(provision.WorkspaceProvisioner)
                prov.unlock_workspace_directories(ws_root)
            except Exception:
                pass
            print(
                "[FAIL RECORDED] Target marked failed due to unresolvable impasse.\n"
                "Your work on this target is 100% COMPLETE. Run 'bin/get_work' to check for other units,\n"
                "or conclude your round immediately with summary text and ZERO further tool calls."
            )
            return 0
        return 1

    # Contract: Evaluates statement test coverage via CoverageEvaluator using workspace files.
    def run_coverage(
        self,
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
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        main_root = _resolve_main_root(ws_root, meta, repo_root)

        evaluator = get_singleton(coverage.CoverageEvaluator)

        target_or_impl = impl or target
        if not target_or_impl:
            print("Error: Specify target or both --impl and --test.", file=sys.stderr)
            return 1

        target_root = ws_root
        if target_or_impl and not os.path.isabs(target_or_impl):
            if not os.path.exists(
                os.path.join(ws_root, target_or_impl)
            ) and os.path.exists(os.path.join(main_root, target_or_impl)):
                target_root = main_root

        try:
            cov = evaluator.evaluate_coverage(
                target_or_impl=target_or_impl,
                test_path=test,
                repo_root=target_root,
                threshold=threshold,
                update_log=update_log,
                max_spans=max_spans,
            )
        except (FileNotFoundError, ValueError) as err:
            print(f"Error: {err}", file=sys.stderr)
            return 1

        if json_output:
            import dataclasses

            print(json.dumps(dataclasses.asdict(cov), indent=2))
            return 0 if (cov.test_passed and cov.coverage_pct >= threshold) else 1

        report = evaluator.format_coverage_report(cov, threshold, max_spans=max_spans)
        print(report)
        if not cov.test_passed or cov.coverage_pct < threshold:
            return 1
        return 0

    # Contract: Commissions an isolated role workspace or all workspaces in a directory scope.
    def run_commission(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        all_roles: bool = False,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace or all workspaces in a directory scope."""
        if all_roles and not dir_scope and role_name:
            dir_scope = role_name
            role_name = None

        if not dir_scope:
            root_cand = repo_root or find_workspace_root() or os.getcwd()
            try:
                for entry in os.listdir(root_cand):
                    if os.path.isdir(
                        os.path.join(root_cand, entry, "parts")
                    ) and not entry.startswith((".", "bazel-", "venv")):
                        dir_scope = entry
                        break
            except OSError:
                pass

        if not dir_scope:
            print(
                "Error: directory scope must be specified or detected from the active workspace."
            )
            return 1

        prov = get_singleton(provision.WorkspaceProvisioner)
        reg = get_singleton(role_registry.WorkspaceRegistry)

        if all_roles:
            all_r_defs = reg.list_roles(repo_root=repo_root, dir_scope=dir_scope)
            for r_def in all_r_defs:
                desc = prov.commission(
                    r_def.role_name,
                    dir_scope,
                    repo_root=repo_root,
                    custom_dest=custom_dest,
                    reset=reset,
                    model=model,
                )
                print(
                    f"✔ Commissioned workspace for role '{r_def.role_name}' at: {desc.workspace_dir}"
                )
            return 0

        if not role_name:
            print("Error: role_name is required when --all is not specified.")
            return 1

        desc = prov.commission(
            role_name,
            dir_scope,
            repo_root=repo_root,
            custom_dest=custom_dest,
            reset=reset,
            model=model,
        )
        print(
            f"✔ Commissioned workspace for role '{role_name}' at: {desc.workspace_dir}"
        )
        return 0

    # Contract: Refreshes system files, bin tools, configs, and guides across role workspaces via WorkspaceSynchronizer.
    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, tools, configs, and guides across role workspaces."""
        root = repo_root or find_workspace_root() or os.getcwd()
        reg = get_singleton(role_registry.WorkspaceRegistry)
        active_workspaces = reg.load_active_workspaces(repo_root=root)
        sync_svc = get_singleton(sync.WorkspaceSynchronizer)

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
                    sync_svc.refresh_system_files(
                        ws.workspace_dir,
                        root,
                        ws.role_definition.role_name,
                        ws.directory_scope,
                        silent=False,
                    )
                    count += 1
                except (OSError, RuntimeError) as e:
                    sys.stderr.write(
                        f"Warning: Failed to refresh system files for {ws.role_definition.role_name} in '{ws.workspace_dir}': {e}\n"
                    )
        print(f"Refreshed system files across {count} role workspace(s).")
        return 0


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T11:00:00Z
# LAST_CHANGED: 2026-11-03T20:40:00Z
# CHANGE: Prohibit bypassing verification via no_verify in active role workspaces and validate blame attribution
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

__initialize__ = auto_initialize()
_initialize_ = __initialize__
