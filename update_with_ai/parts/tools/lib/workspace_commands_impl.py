# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Define workspace_commands_impl realization
# CODE_HASH: 3ad33f76279d
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_commands_impl."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import (
    control_attribution,
    control_submit,
)
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_registry,
    workspace_sync,
)
from . import (
    tool_coverage,
    workspace_check,
    workspace_commands,
    workspace_pending,
)

# Contract: Discovers root of commissioned role workspace or repo root by checking for .cleanroom_role.json.
def find_workspace_root() -> str:
    """Discovers root of commissioned role workspace or repo root."""
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, ".cleanroom_role.json")):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()


# Contract: Loads .cleanroom_role.json from current workspace if present.
def get_current_role_metadata() -> Optional[Dict[str, Any]]:
    """Loads .cleanroom_role.json from current workspace if present."""
    ws_root = find_workspace_root()
    p = os.path.join(ws_root, ".cleanroom_role.json")
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


# Contract: Resolves main repository root from explicit repo_root or workspace_registry.discover_repository_root.
def _resolve_main_root(
    ws_root: str, meta: Optional[Dict[str, Any]], repo_root: Optional[str] = None
) -> str:
    if repo_root:
        return os.path.realpath(repo_root)
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    return os.path.realpath(reg.discover_repository_root(ws_root))


# Contract: Resolves path to .cleanroom.log in the directory containing parts.
def resolve_cleanroom_log_path(
    target_or_path: str, repo_root: Optional[str] = None
) -> str:
    """Resolves path to .cleanroom.log in the directory containing parts."""
    root = os.path.realpath(repo_root or find_workspace_root())
    norm_path = (
        target_or_path
        if os.path.isabs(target_or_path)
        else os.path.join(root, target_or_path)
    )
    norm_path = os.path.normpath(norm_path)

    curr = norm_path
    while curr and curr != os.path.dirname(curr):
        parent = os.path.dirname(curr)
        if os.path.basename(curr) == "parts":
            return os.path.join(parent, ".cleanroom.log")
        curr = parent

    if os.path.isdir(os.path.join(root, "parts")):
        return os.path.join(root, ".cleanroom.log")
    meta = get_current_role_metadata()
    if meta and meta.get("parts_dir"):
        parts_parent = os.path.join(root, meta["parts_dir"])
        return os.path.join(parts_parent, ".cleanroom.log")

    return os.path.join(root, ".cleanroom.log")


# Contract: Appends action record message to .cleanroom.log in directory containing parts.
def append_cleanroom_log(
    target_or_path: str,
    message: str,
    repo_root: Optional[str] = None,
) -> str:
    """Appends action record message to .cleanroom.log in directory containing parts."""
    log_path = resolve_cleanroom_log_path(target_or_path, repo_root=repo_root)
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message.rstrip("\n") + "\n")
    return log_path


def _find_agent_node_config_module() -> Any:
    for k, m in list(sys.modules.items()):
        if k == "agent_node_config" or k.endswith(".agent_node_config"):
            if hasattr(m, "NodeConfig"):
                return m
    try:
        import importlib
        return importlib.import_module("agent_node_config")
    except ImportError:
        pass
    return None


def _ensure_cli_node_config(main_root: Optional[str] = None) -> None:
    node_cfg_mod = _find_agent_node_config_module()
    node_cfg_cls = getattr(node_cfg_mod, "NodeConfig", None) if node_cfg_mod else None
    cfg = None
    if node_cfg_cls is not None:
        try:
            cfg = get_singleton(node_cfg_cls)
        except (KeyError, LifecycleResolutionError):
            cfg = None

    reg = get_default_registry()
    ws_reg = get_singleton(workspace_registry.WorkspaceRegistry)
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
        keys: List[Any] = [CliNodeConfig]
        if node_cfg_cls is not None:
            keys.append(node_cfg_cls)
        reg.register_instance(
            cli_cfg,
            keys=keys,
            tier=agent_session.agent_session,
        )
    else:
        if not hasattr(cfg, "role_definitions") or not getattr(cfg, "role_definitions", None):
            setattr(cfg, "role_definitions", role_defs)



# Contract: Realizes substantive domain operations for Cleanroom role workspaces in agent_session tier.
class WorkspaceCommandHandler(workspace_commands.WorkspaceCommandHandler, Singleton):
    """Realizes substantive domain operations for Cleanroom role workspaces."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def _checker(self) -> workspace_check.WorkspaceChecker:
        return get_singleton(workspace_check.WorkspaceChecker)

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

    # Contract: Validates target, executes verification unless bypassed, delegates to SubmissionCoordinator, logs to cleanroom log, and removes from pending work.
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
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)

        if not no_verify:
            check_exit = self.run_check_files(target=target, repo_root=main_root)
            if check_exit != 0:
                print(f"[FAIL] Verification checks failed for '{target}'. Submission rejected.")
                return 1

        sub_coord = get_singleton(control_submit.SubmissionCoordinator)
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
                append_cleanroom_log(target, outcome.message, repo_root=main_root)
                if ws_root != main_root:
                    try:
                        append_cleanroom_log(target, outcome.message, repo_root=ws_root)
                    except OSError:
                        pass
            if meta:
                pending_mgr = get_singleton(workspace_pending.WorkspacePendingManager)
                pending_mgr.remove_pending_target(ws_root, target)
            return 0
        return 1

    # Contract: Delegates blame attribution to AttributionCoordinator, logs to cleanroom log, and removes from pending work.
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

        attr_coord = get_singleton(control_attribution.AttributionCoordinator)
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
            append_cleanroom_log(culprit_file, blame_msg, repo_root=main_root)
            if ws_root != main_root:
                try:
                    append_cleanroom_log(culprit_file, blame_msg, repo_root=ws_root)
                except OSError:
                    pass
            if meta:
                pending_mgr = get_singleton(workspace_pending.WorkspacePendingManager)
                pending_mgr.remove_pending_target(ws_root, culprit_file)
            return 0
        return 1

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

        attr_coord = get_singleton(control_attribution.AttributionCoordinator)
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
                pending_mgr = get_singleton(workspace_pending.WorkspacePendingManager)
                pending_mgr.remove_pending_target(ws_root, file_path)
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

        evaluator = get_singleton(tool_coverage.CoverageEvaluator)

        target_or_impl = impl or target
        if not target_or_impl:
            print("Error: Specify target or both --impl and --test.", file=sys.stderr)
            return 1

        target_root = ws_root
        if target_or_impl and not os.path.isabs(target_or_impl):
            if not os.path.exists(os.path.join(ws_root, target_or_impl)) and os.path.exists(
                os.path.join(main_root, target_or_impl)
            ):
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
                    if os.path.isdir(os.path.join(root_cand, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                        dir_scope = entry
                        break
            except OSError:
                pass

        if not dir_scope:
            print("Error: directory scope must be specified or detected from the active workspace.")
            return 1

        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        reg = get_singleton(workspace_registry.WorkspaceRegistry)

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
                print(f"✔ Commissioned workspace for role '{r_def.role_name}' at: {desc.workspace_dir}")
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
        print(f"✔ Commissioned workspace for role '{role_name}' at: {desc.workspace_dir}")
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
        reg = get_singleton(workspace_registry.WorkspaceRegistry)
        active_workspaces = reg.load_active_workspaces(repo_root=root)
        sync = get_singleton(workspace_sync.WorkspaceSynchronizer)

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
                    sync.refresh_system_files(
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



# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceCommandHandler,
        keys=[workspace_commands.WorkspaceCommandHandler, WorkspaceCommandHandler],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
