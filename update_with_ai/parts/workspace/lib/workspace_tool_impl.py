# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T12:55:00Z
# LAST_CHANGED: 2026-10-08T12:55:00Z
# CHANGE: implement workspace tool runner
# CODE_HASH: f04007864808
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_tool_impl."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    enter_phase,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.control.lib import (
    control_attribution,
    control_submit,
)
from update_with_ai.parts.tools.lib import (
    tool_coverage,
)
from update_with_ai.parts.workspace.lib import (
    workspace_provision,
    workspace_registry,
    workspace_sync,
    workspace_work,
)
from . import workspace_tool

AUDIT_BUFFER_FILE = ".cleanroom_audit_buffer.json"
BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
PENDING_WORK_FILE = workspace_work.PENDING_WORK_FILE



def is_auditor_role(role_name: str, repo_root: Optional[str] = None) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(r_def.audit_tag or not r_def.src_pattern)


def write_file_with_perms(
    file_path: str,
    content: str,
    readonly: bool = False,
    executable: bool = False,
) -> None:
    """Writes content to file with specified permissions."""
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    if os.path.exists(file_path):
        try:
            os.chmod(file_path, 0o644)
        except OSError:
            pass
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    mode = (0o555 if readonly else 0o755) if executable else (0o444 if readonly else 0o644)
    try:
        os.chmod(file_path, mode)
    except OSError:
        pass


def copy_file_with_perms(
    src: str,
    dst: str,
    readonly: bool = False,
    executable: bool = False,
) -> None:
    """Copies file preserving permissions and content."""
    workspace_sync.copy_file_with_perms(src, dst)


def find_workspace_root() -> str:
    """Discovers root of commissioned role workspace or repo root."""
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, ".cleanroom_role.json")):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()


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


def _resolve_main_root(
    ws_root: str, meta: Optional[Dict[str, Any]], repo_root: Optional[str] = None
) -> str:
    if repo_root:
        return os.path.realpath(repo_root)
    if meta:
        m = meta.get("main_workspace_root") or meta.get("repo_root")
        if m:
            return os.path.realpath(m)
    reg = get_singleton(workspace_registry.WorkspaceRegistry)
    active = reg.load_active_workspaces(repo_root=ws_root)
    for ws in active:
        if os.path.realpath(ws.workspace_dir) == ws_root:
            return os.path.realpath(ws.main_repository_root)
    return os.path.realpath(reg.discover_repository_root(ws_root))


def get_pending_work(ws_root: str) -> List[str]:
    """Returns list of pending target paths assigned in previous get_work calls."""
    mgr = get_singleton(workspace_work.WorkspaceWorkManager)
    return list(mgr.get_pending_work(ws_root))


def set_pending_work(ws_root: str, targets: List[str]) -> None:
    """Records pending target paths assigned to the workspace."""
    mgr = get_singleton(workspace_work.WorkspaceWorkManager)
    mgr.set_pending_work(ws_root, targets)


def clear_pending_work(ws_root: str) -> None:
    """Clears pending work tracking file."""
    mgr = get_singleton(workspace_work.WorkspaceWorkManager)
    mgr.clear_pending_work(ws_root)


def remove_pending_target(ws_root: str, submitted_target: str) -> None:
    """Removes a submitted or resolved target from pending work."""
    mgr = get_singleton(workspace_work.WorkspaceWorkManager)
    mgr.remove_pending_target(ws_root, submitted_target)


def is_pending_target_dirty(
    pt: str, ws_root: str, main_root: str, role_name: str
) -> bool:
    """Checks whether a pending target file is still dirty in ws_root or main."""
    mgr = get_singleton(workspace_work.WorkspaceWorkManager)
    return mgr.is_pending_target_dirty(
        pt, ws_root, main_root=main_root, role_name=role_name
    )


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


def compute_role_work_queue(
    role_name: str,
    dir_scope: str,
    repo_root: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Computes ready and blocked dirty work items for a role."""
    mgr = get_singleton(workspace_work.WorkspaceWorkManager)
    ready_items, blocked_items = mgr.compute_role_work_queue(
        role_name, dir_scope, repo_root
    )


    def _to_dict(it: workspace_work.WorkQueueItem) -> Dict[str, Any]:
        stem = os.path.splitext(os.path.basename(it.target_file))[0]
        if stem.endswith("_test"):
            stem = stem[:-5]
        return {
            "unit_name": stem,
            "role": it.role_name,
            "target_file": it.target_file,
            "reasons": list(it.dirtiness_reasons),
            "dependencies": list(it.dependency_files),
            "contract_files": list(it.contract_files),
            "blocked_reasons": list(it.blocked_reasons),
        }

    return [_to_dict(it) for it in ready_items], [_to_dict(it) for it in blocked_items]


def _find_agent_node_config_module() -> Any:
    for k, m in list(sys.modules.items()):
        if k.endswith(".parts.agent.lib.agent_node_config") or k == "parts.agent.lib.agent_node_config":
            if hasattr(m, "NodeConfig"):
                return m
    ws_root = find_workspace_root()
    roots = [ws_root]
    meta = get_current_role_metadata()
    main_r = _resolve_main_root(ws_root, meta)
    if main_r and main_r not in roots:
        roots.append(main_r)
    for r in roots:
        if not os.path.isdir(r):
            continue
        try:
            for entry in os.listdir(r):
                if entry.startswith((".", "bazel-", "venv")):
                    continue
                cand = os.path.join(r, entry, "parts", "agent", "lib", "agent_node_config.py")
                if os.path.isfile(cand) and os.path.isdir(os.path.join(r, entry, "support", "lib")):
                    try:
                        import importlib
                        return importlib.import_module(f"{entry}.parts.agent.lib.agent_node_config")
                    except ImportError:
                        pass
        except OSError:
            pass
    try:
        import importlib
        return importlib.import_module("parts.agent.lib.agent_node_config")
    except ImportError:
        return None


def _ensure_cli_node_config(main_root: Optional[str] = None) -> None:
    node_cfg_mod = _find_agent_node_config_module()
    node_cfg_cls = getattr(node_cfg_mod, "NodeConfig", None) if node_cfg_mod else None
    cfg = None
    if node_cfg_cls is not None:
        try:
            cfg = get_singleton(node_cfg_cls)
        except (KeyError, LifecycleResolutionError, Exception):
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


class WorkspaceToolRunner(workspace_tool.WorkspaceToolRunner, Singleton):
    """Realizes command-line subagent tool execution for role workspaces."""

    tier = agent_session.agent_session

    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
    ) -> int:
        """Evaluates dirtiness in local workspace scope and prints next ready tasks for this role."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        role_name = (meta.get("role_name") or meta.get("role", "")) if meta else ""
        d_scope = dir_scope or (
            (meta.get("dir_scope") or meta.get("parts_dir", ""))
            if meta
            else ""
        )
        if not d_scope:
            try:
                for entry in os.listdir(ws_root):
                    if os.path.isdir(os.path.join(ws_root, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                        d_scope = entry
                        break
            except OSError:
                pass

        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)
        work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)

        if main_root and os.path.isdir(main_root) and main_root != ws_root:
            try:
                sync = get_singleton(workspace_sync.WorkspaceSynchronizer)

                sync.pull(ws_root, main_root, role_name, dir_scope=d_scope, silent=True)
                sync.refresh_system_files(
                    ws_root, main_root, role_name, dir_scope=d_scope, silent=True
                )
            except (OSError, RuntimeError) as e:
                sys.stderr.write(f"Warning: automatic sync from main failed: {e}\n")
        elif meta and main_root == ws_root:
            sys.stderr.write(
                f"Warning: In role workspace '{ws_root}' but canonical main workspace could not be resolved. Inbound sync skipped.\n"
            )
        elif main_root and not os.path.isdir(main_root):
            sys.stderr.write(
                f"Warning: Canonical main workspace '{main_root}' is not an accessible directory. Inbound sync skipped.\n"
            )

        if meta and not force:
            pending = work_mgr.get_pending_work(ws_root)
            if pending:
                still_dirty = [
                    pt
                    for pt in pending
                    if work_mgr.is_pending_target_dirty(
                        pt, ws_root, main_root=main_root, role_name=role_name
                    )
                ]
                if still_dirty:
                    print(
                        f"\nError: Cannot call get_work while work is pending in this role workspace."
                    )
                    print(f"Pending dirty target(s) from previous get_work call:")
                    for pt in still_dirty:
                        print(f"  • {pt}")
                        contracts = work_mgr.resolve_contract_files(
                            pt, ws_root, role_name=role_name
                        )
                        if contracts:
                            print(f"      Contracts / Specifications to Read:")
                            for c in contracts:
                                print(f"        - {c}")
                    if is_auditor_role(role_name):
                        print(
                            f"\nComplete the pending work before getting new work:\n"
                            f"  bin/submit <target_file> (attests {role_name.upper()}_AUDIT)\n"
                            f"Or attribute defect to an upstream contract:\n"
                            f"  bin/blame <culprit-file> \"<actionable critique>\"\n"
                        )
                    else:
                        print(
                            f"\nComplete the pending work before getting new work:\n"
                            f"  bin/submit <target_file> \"<summary>\" (or bin/submit <target_file> if no changes)\n"
                            f"Or attribute defect to an upstream contract:\n"
                            f"  bin/blame <culprit-file> \"<actionable critique>\"\n"
                        )
                    return 1
                else:
                    work_mgr.clear_pending_work(ws_root)

        eval_root = (
            main_root if (meta and main_root and os.path.isdir(main_root)) else ws_root
        )
        ready_items, blocked_items = compute_role_work_queue(
            role_name, d_scope, eval_root
        )

        print(
            f"\n=== Cleanroom Work Queue [Role: {(role_name or 'ALL').upper()} | Scope: {d_scope}] ==="
        )
        if not ready_items and not blocked_items:
            if meta:
                work_mgr.clear_pending_work(ws_root)
            print(
                f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
            )
            return 0

        if ready_items and meta:
            work_mgr.set_pending_work(
                ws_root, [item["target_file"] for item in ready_items]
            )
        elif meta:
            work_mgr.clear_pending_work(ws_root)

        total_dirty = len(ready_items) + len(blocked_items)
        print(f"Found {total_dirty} dirty unit(s) ({len(ready_items)} ready to clean):")
        for item in ready_items:
            print(f"\n  • [READY - {item['role'].upper()}] {item['target_file']}")
            if item.get("contract_files"):
                print("      Contracts / Specifications to Read:")
                for c in item["contract_files"]:
                    print(f"        - {c}")
            print("      Reasons:")
            for r in item["reasons"]:
                print(f"        - {r}")
            if item.get("dependencies"):
                print("      Dependencies:")
                for dep in item["dependencies"]:
                    print(f"        - {dep}")

        if blocked_items:
            print(f"\nBlocked unit(s) ({len(blocked_items)} waiting on prerequisites):")
            for item in blocked_items:
                print(f"\n  • [BLOCKED - {item['role'].upper()}] {item['target_file']}")
                if item.get("contract_files"):
                    print("      Contracts / Specifications to Read:")
                    for c in item["contract_files"]:
                        print(f"        - {c}")
                print("      Blocked Reasons:")
                for br in item.get("blocked_reasons", []):
                    print(f"        - {br}")
                if item.get("dependencies"):
                    print("      Dependencies:")
                    for dep in item["dependencies"]:
                        print(f"        - {dep}")

        if is_auditor_role(role_name):
            print(
                f"\nACTIONABLE NEXT STEP: Run 'bin/check_files' to verify target, then run 'bin/submit <target_file>' to attest {role_name.upper()}_AUDIT.\n"
            )
        else:
            print(
                "\nACTIONABLE NEXT STEP: Implement changes, verify with 'bin/check_files', then run 'bin/submit <file> \"<summary>\"' (or 'bin/submit <file>' if no changes).\n"
            )
        return 1 if ready_items else 0

    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Executes role-specific verification checks, linters, and type checking for targets."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        if not meta or not (meta.get("role_name") or meta.get("role")):
            if target:
                raise ValueError(f"Cannot run check_files: no cleanroom role defined for workspace '{ws_root}'.")
            print("No pending or specified targets to check.")
            return 0
        role_name = (
            str(meta.get("role_name") or meta.get("role") or "")
            .split(":")[-1]
            .strip()
            .lower()
        )
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)
        d_scope = (
            meta.get("dir_scope") or meta.get("parts_dir", "")
        ) if meta else ""
        if not d_scope:
            try:
                for entry in os.listdir(ws_root):
                    if os.path.isdir(os.path.join(ws_root, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                        d_scope = entry
                        break
            except OSError:
                pass

        targets_to_check: List[str] = []
        if target:
            targets_to_check.append(target)
        else:
            pending = get_pending_work(ws_root)
            if pending:
                targets_to_check.extend(pending)

        if not targets_to_check:
            print("No pending or specified targets to check.")
            return 0

        failed_count = 0
        for cand in targets_to_check:
            target_path, unit_name = control_submit.resolve_submit_target(
                cand, ws_root, role_name, d_scope
            )
            if not target_path or not os.path.isfile(target_path):
                target_path, unit_name = control_submit.resolve_submit_target(
                    cand, main_root, role_name, d_scope
                )

            if not target_path or not os.path.isfile(target_path):
                print(f"Error: Target '{cand}' not found on disk.")
                failed_count += 1
                continue

            if ws_root != main_root and target_path.startswith(main_root):
                rel = os.path.relpath(target_path, main_root)
                ws_file = os.path.join(ws_root, rel)
                if not os.path.isfile(ws_file):
                    copy_file_with_perms(target_path, ws_file, readonly=False)
                target_path = ws_file

            ref_root = ws_root if target_path.startswith(ws_root) else main_root
            part_dir, u_name, _ = control_submit.parse_unit_from_file_path(
                target_path, ref_root
            )

            active_unit = u_name or unit_name

            print(f"=== Checking {active_unit} (role: {role_name}, part: {part_dir}) ===")
            unit_failed = False

            reg = get_singleton(workspace_registry.WorkspaceRegistry)
            r_def = reg.resolve_role_definition(role_name, repo_root=main_root)
            cmd_tmpl = r_def.verify_template
            if not cmd_tmpl or cmd_tmpl.strip().startswith("#"):
                print(f"[OK] No verification check required for {active_unit} in role {role_name}.")
            else:
                formatted_cmd = cmd_tmpl.format(unit_dir=part_dir, unit_name=active_unit)
                env = dict(os.environ)
                env["BUILD_WORKSPACE_DIRECTORY"] = ws_root
                if "UV_PROJECT" not in env and main_root:
                    env["UV_PROJECT"] = main_root
                pypaths = [ws_root, main_root]
                for root_cand in (main_root, ws_root):
                    if not root_cand or not os.path.isdir(root_cand):
                        continue
                    if part_dir:
                        pd_full = os.path.join(root_cand, part_dir)
                        if os.path.isdir(pd_full):
                            pypaths.append(pd_full)
                    try:
                        for entry in os.listdir(root_cand):
                            pkg_dir = os.path.join(root_cand, entry)
                            if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv", "__pycache__")):
                                sup_lib = os.path.join(pkg_dir, "support", "lib")
                                if os.path.isdir(sup_lib):
                                    pypaths.append(pkg_dir)
                                    pypaths.append(sup_lib)
                    except OSError:
                        pass
                if "PYTHONPATH" in env:
                    pypaths.append(env["PYTHONPATH"])
                env["PYTHONPATH"] = os.pathsep.join(pypaths)
                env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")

                res = subprocess.run(
                    formatted_cmd,
                    shell=True,
                    cwd=ws_root,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0:
                    print(
                        f"[FAIL] Verification failed for {active_unit}:\n{res.stdout}\n{res.stderr}".strip()
                    )
                    unit_failed = True
                else:
                    if r_def.verification_success_message:
                        try:
                            msg = r_def.verification_success_message.format(
                                unit_name=active_unit, unit_dir=part_dir
                            )
                        except (KeyError, ValueError, IndexError):
                            msg = r_def.verification_success_message
                        print(f"[OK] {msg}")
                    else:
                        print(f"[OK] Verification passed for {active_unit}")

            if unit_failed:
                failed_count += 1
            else:
                print(f"[PASSED] All verification checks passed for '{active_unit}'.")

        return 1 if failed_count > 0 else 0

    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Verifies target and stamps in-band metadata or <ROLE>_AUDIT directly in main."""
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        role_name = str(meta.get("role_name") or meta.get("role") or "") if meta else ""
        main_root = _resolve_main_root(ws_root, meta, repo_root)
        _ensure_cli_node_config(main_root)

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
                work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
                work_mgr.remove_pending_target(ws_root, target)
            return 0
        return 1

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
                work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
                work_mgr.remove_pending_target(ws_root, culprit_file)
            return 0
        return 1

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
                work_mgr = get_singleton(workspace_work.WorkspaceWorkManager)
                work_mgr.remove_pending_target(ws_root, file_path)
            return 0
        return 1


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

        evaluator = tool_coverage.get_coverage_evaluator()

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

    def run_commission(
        self,
        role_name: str,
        dir_scope: str = "",
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace."""
        if not dir_scope:
            root_cand = repo_root or find_workspace_root() or os.getcwd()
            try:
                for entry in os.listdir(root_cand):
                    if os.path.isdir(os.path.join(root_cand, entry, "parts")) and not entry.startswith((".", "bazel-", "venv")):
                        dir_scope = entry
                        break
            except OSError:
                pass
        prov = get_singleton(workspace_provision.WorkspaceProvisioner)
        desc = prov.commission(
            role_name, dir_scope, repo_root=repo_root, custom_dest=custom_dest
        )
        print(f"✔ Commissioned workspace for role '{role_name}' at: {desc.workspace_dir}")
        return 0

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

    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches CLI subcommand execution."""
        parser = argparse.ArgumentParser(
            prog="cleanroom_role_tool",
            description="Cleanroom Role Workspace Subagent CLI Tool",
        )
        subparsers = parser.add_subparsers(dest="command", metavar="<command>")

        # commission
        p_comm = subparsers.add_parser(
            "commission", help="Commission an isolated role workspace"
        )
        p_comm.add_argument("role", help="Role name to commission (e.g. high, planning, low, lib, test, qa, coverage)")
        p_comm.add_argument("dir", nargs="?", default="", help="Directory scope")
        p_comm.add_argument("--repo-root", default=None, help="Root of canonical repository")
        p_comm.add_argument("--dest", default=None, help="Custom destination directory")

        # refresh-sys
        p_ref = subparsers.add_parser(
            "refresh-sys",
            aliases=["refresh_sys"],
            help="Refresh system files, tools, configs, and guides across role workspaces",
        )
        p_ref.add_argument("role", nargs="?", default=None, help="Optional role name to filter")
        p_ref.add_argument("dir", nargs="?", default=None, help="Optional directory scope to filter")
        p_ref.add_argument("--repo-root", default=None, help="Root of canonical repository")

        # get_work
        p_work = subparsers.add_parser(
            "get_work", help="Get ready dirty tasks in workspace scope"
        )
        p_work.add_argument("dir", nargs="?", default=None, help="Directory scope override")
        p_work.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Force get_work even if work is pending",
        )

        # submit
        p_submit = subparsers.add_parser(
            "submit", help="Verify and submit target with in-band header update"
        )
        p_submit.add_argument("target", help="Target file path or unit name")
        p_submit.add_argument("summary", nargs="?", default=None, help="Change summary")

        # blame / feedback
        p_blame = subparsers.add_parser(
            "blame",
            aliases=["feedback"],
            help="Attribute blame feedback to a culprit file or upstream contract",
            description="Attributes actionable critique to a culprit specification, code, or test file.",
        )
        p_blame.add_argument(
            "culprit_file",
            metavar="<culprit-file>",
            help="Path to the culprit file receiving blame",
        )
        p_blame.add_argument(
            "critique",
            metavar="<actionable-critique>",
            help="Actionable critique message without newlines",
        )

        # fail
        p_fail = subparsers.add_parser(
            "fail", help="Record verification failure and force dirty state"
        )
        p_fail.add_argument("target", help="Target file path")
        p_fail.add_argument("reason", nargs="?", default=None, help="Failure reason")

        # coverage
        p_cov = subparsers.add_parser(
            "coverage", help="Evaluate statement test coverage for a module"
        )
        p_cov.add_argument("target", nargs="?", default=None, help="Target or module name")
        p_cov.add_argument("--impl", help="Path to implementation file")
        p_cov.add_argument("--test", help="Path to test file")
        p_cov.add_argument(
            "--threshold",
            "-t",
            type=float,
            default=0.0,
            help="Minimum coverage percentage required to exit successfully",
        )
        p_cov.add_argument(
            "--update-log", help="Path to coverage log file to update"
        )
        p_cov.add_argument(
            "--max-spans",
            type=int,
            default=None,
            help="Maximum non-continuous spans to present",
        )
        p_cov.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Output coverage metrics in JSON format",
        )

        # check_files
        p_check = subparsers.add_parser(
            "check_files", help="Run role-specific verification checks on target files"
        )
        p_check.add_argument(
            "target",
            nargs="?",
            default=None,
            help="Target file or unit name (defaults to pending work)",
        )
        p_check.add_argument(
            "--repo-root",
            default=None,
            help="Path to canonical repository root",
        )

        args = parser.parse_args(list(argv))

        if args.command == "commission":
            return self.run_commission(
                args.role,
                dir_scope=args.dir,
                repo_root=args.repo_root,
                custom_dest=args.dest,
            )
        elif args.command in ("refresh-sys", "refresh_sys"):
            return self.run_refresh_sys(
                role_name=args.role,
                dir_scope=args.dir,
                repo_root=args.repo_root,
            )
        elif args.command == "get_work":
            return self.run_get_work(dir_scope=args.dir, force=args.force)
        elif args.command in ("check_files", "check-files"):
            return self.run_check_files(target=args.target, repo_root=args.repo_root)
        elif args.command == "submit":
            return self.run_submit(args.target, summary=args.summary)
        elif args.command in ("blame", "feedback"):
            return self.run_blame(args.culprit_file, args.critique)
        elif args.command == "fail":
            return self.run_fail(args.target, reason=args.reason)
        elif args.command == "coverage":
            return self.run_coverage(
                target=args.target,
                impl=args.impl,
                test=args.test,
                threshold=args.threshold,
                update_log=args.update_log,
                max_spans=args.max_spans,
                json_output=args.json_output,
            )

        parser.print_help()
        return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI Entrypoint executing within agent_session lifecycle phase."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    with enter_phase(agent_session.agent_session):
        try:
            get_singleton(workspace_registry.WorkspaceRegistry)
        except (KeyError, LifecycleResolutionError):
            for k, m in list(sys.modules.items()):
                if (k.endswith(".parts.workspace.lib.workspace_asm") or k == "parts.workspace.lib.workspace_asm") and hasattr(m, "__initialize__"):
                    m.__initialize__()
                    break
            else:
                try:
                    import importlib
                    for p in sys.path:
                        cand = os.path.join(p, "parts", "workspace", "lib", "workspace_asm.py")
                        if os.path.isfile(cand):
                            pkg = os.path.basename(p)
                            mod_name = f"{pkg}.parts.workspace.lib.workspace_asm" if pkg else "parts.workspace.lib.workspace_asm"
                            try:
                                mod = importlib.import_module(mod_name)
                                if hasattr(mod, "__initialize__"):
                                    mod.__initialize__()
                                break
                            except ImportError:
                                pass
                except (ImportError, AttributeError, OSError):
                    pass
        runner = WorkspaceToolRunner()
        return runner.execute_command(raw_args)


def get_workspace_tool_runner() -> workspace_tool.WorkspaceToolRunner:
    """Returns singleton WorkspaceToolRunner instance."""
    return get_singleton(workspace_tool.WorkspaceToolRunner)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = registry or get_default_registry()
    reg.register_singleton(
        WorkspaceToolRunner,
        keys=[
            workspace_tool.WorkspaceToolRunner,
            WorkspaceToolRunner,
        ],
        tier=agent_session.agent_session,
    )
