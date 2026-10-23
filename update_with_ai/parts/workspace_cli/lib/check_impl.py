"""Low-level implementation for check_impl."""

from __future__ import annotations

import json
import os
import re
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
from update_with_ai.parts.agent.lib import node_config, session as agent_session
from update_with_ai.parts.control.lib import submit
from update_with_ai.parts.workspace.lib import (
    provision,
    role_registry,
    sync,
)
from . import (
    check,
    pending,
    work,
)


def is_auditor_role(role_name: str, repo_root: Optional[str] = None) -> bool:
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(role_registry.WorkspaceRegistry)
    r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    return bool(r_def.audit_tag or not r_def.src_pattern)


def record_check_executed(ws_root: str, target_path: str, passed: bool) -> None:
    """Records file verification execution and content hash in .cleanroom/.last_check_files.json."""
    cleanroom_dir = os.path.join(ws_root, ".cleanroom")
    os.makedirs(cleanroom_dir, exist_ok=True)
    rec_file = os.path.join(cleanroom_dir, ".last_check_files.json")
    records: Dict[str, Any] = {}
    if os.path.isfile(rec_file):
        try:
            with open(rec_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, json.JSONDecodeError):
            records = {}
    norm_path = os.path.realpath(target_path)
    mtime = os.path.getmtime(target_path) if os.path.isfile(target_path) else 0.0
    import hashlib
    content_hash = ""
    if os.path.isfile(target_path):
        try:
            with open(target_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            content_hash = ""
    rec = {
        "mtime": mtime,
        "content_hash": content_hash,
        "passed": passed,
    }
    records[norm_path] = rec
    try:
        rel_path = os.path.relpath(norm_path, ws_root)
        records[rel_path] = rec
    except ValueError:
        pass
    try:
        with open(rec_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except OSError:
        pass


def _is_checked_since_modification(ws_root: str, target_path: str) -> bool:
    """Returns True if the target has been checked via check_files since its last modification."""
    rec_file = os.path.join(ws_root, ".cleanroom", ".last_check_files.json")
    if not os.path.isfile(rec_file):
        return False
    try:
        with open(rec_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    norm_path = os.path.realpath(target_path)
    rel_path = ""
    try:
        rel_path = os.path.relpath(norm_path, ws_root)
    except ValueError:
        pass
    rec = records.get(norm_path) or (records.get(rel_path) if rel_path else None)
    if not rec:
        return False
    if not os.path.isfile(target_path):
        return True
    import hashlib
    try:
        with open(target_path, "rb") as f:
            cur_hash = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return False
    rec_hash = rec.get("content_hash", "")
    if rec_hash:
        return bool(cur_hash == rec_hash)
    cur_mtime = os.path.getmtime(target_path)
    return bool(cur_mtime <= rec.get("mtime", 0.0))


def _extract_unacted_feedback(file_path: str) -> List[str]:
    """Extracts unacted feedback lines from a target file's cleanroom metadata header."""
    if not file_path or not os.path.isfile(file_path):
        return []
    feedback_items: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            in_header = False
            in_feedback = False
            for line in f:
                stripped = line.strip()
                if "CLEANROOM METADATA" in stripped:
                    in_header = True
                    continue
                if "END CLEANROOM METADATA" in stripped or (in_header and stripped == "-->"):
                    break
                if not in_header:
                    continue
                if stripped.startswith("#"):
                    stripped = stripped.lstrip("#").strip()
                if stripped.startswith("FEEDBACK:"):
                    in_feedback = True
                    continue
                if in_feedback:
                    if stripped.startswith("-"):
                        item = stripped.lstrip("-").strip()
                        clean_item = re.sub(r"^\[.*?\]:\s*", "", item)
                        feedback_items.append(clean_item)
                    elif stripped and not stripped.startswith("-"):
                        in_feedback = False
    except OSError:
        pass
    return feedback_items


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
    reg = get_singleton(role_registry.WorkspaceRegistry)
    return os.path.realpath(reg.discover_repository_root(ws_root))


def _compute_role_work_queue(
    role_name: str,
    dir_scope: str,
    repo_root: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Computes ready and blocked dirty work items for a role."""
    mgr = get_singleton(work.WorkspaceWorkManager)
    ready_items, blocked_items = mgr.compute_role_work_queue(
        role_name, dir_scope, repo_root
    )

    def _to_dict(it: Any) -> Dict[str, Any]:
        if isinstance(it, dict):
            return it
        stem = os.path.splitext(os.path.basename(it.target_file))[0]
        if stem.endswith("_test"):
            stem = stem[:-5]
        dirtiness_reasons = (
            it.dirtiness_reasons
            if hasattr(it, "dirtiness_reasons")
            else (it.reasons if hasattr(it, "reasons") else ())
        )
        dependency_files = (
            it.dependency_files
            if hasattr(it, "dependency_files")
            else (it.dependencies if hasattr(it, "dependencies") else ())
        )
        contract_files = it.contract_files if hasattr(it, "contract_files") else ()
        return {
            "unit_name": stem,
            "role": it.role_name,
            "target_file": it.target_file,
            "reasons": list(dirtiness_reasons or ()),
            "contract_files": list(contract_files or ()),
            "dependencies": list(dependency_files or ()),
        }

    return [_to_dict(it) for it in ready_items], [_to_dict(it) for it in blocked_items]


def _find_agent_node_config_module() -> Any:
    for k, m in list(sys.modules.items()):
        if k in ("node_config", "agent_node_config") or k.endswith(".node_config") or k.endswith(".agent_node_config"):
            if hasattr(m, "NodeConfig"):
                return m
    try:
        import importlib
        try:
            return importlib.import_module("update_with_ai.parts.agent.lib.node_config")
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
    ws_reg = get_singleton(role_registry.WorkspaceRegistry)
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


def _resolve_active_model_entry(
    meta: Optional[Dict[str, Any]],
    ws_root: str,
    main_root: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolves active model configuration entry from model_configs.toml."""
    search_roots = [main_root, ws_root] if main_root else [ws_root]
    for s_root in search_roots:
        if not s_root:
            continue
        model_cfg_path = os.path.join(s_root, "model_configs.toml")
        if os.path.isfile(model_cfg_path):
            try:
                import tomllib
                with open(model_cfg_path, "rb") as mf:
                    m_data = tomllib.load(mf)
                target_model = (meta.get("model") if meta else None) or m_data.get("default")
                if target_model and "models" in m_data and target_model in m_data["models"]:
                    return m_data["models"][target_model]
            except Exception:
                pass
    return None


def _resolve_effective_max_failures(
    meta: Optional[Dict[str, Any]],
    ws_root: str,
    main_root: Optional[str] = None,
) -> int:
    """Resolves effective max test failures threshold, defaulting to 5 for local engines and 100 for non-local."""
    if meta and meta.get("max_failures") is not None:
        try:
            return int(meta["max_failures"])
        except (ValueError, TypeError):
            pass

    m_entry = _resolve_active_model_entry(meta, ws_root, main_root)
    if m_entry is not None:
        mf_val = m_entry.get("max_failures")
        if mf_val is not None:
            try:
                return int(mf_val)
            except (ValueError, TypeError):
                pass
        tier_val = m_entry.get("tier")
        prov = str(m_entry.get("provider", "")).lower()
        base_url = str(m_entry.get("base_url", "")).lower()
        is_local = tier_val == 1 or prov == "mlx" or "8000" in base_url or "localhost" in base_url
        return 5 if is_local else 100

    tier_val = meta.get("tier") if meta else None
    is_local = tier_val == 1
    return 5 if is_local else 100


# Contract: Realizes work discovery and file verification for role workspaces in agent_session tier.
class WorkspaceChecker(check.WorkspaceChecker):
    """Executes work discovery and file verification for role workspaces."""

    tier = agent_session.agent_session

    # Contract: Evaluates dirty work in local workspace and prints ready tasks, synchronizing from main repository and respecting batch_size and max_feedback_chars.
    def run_get_work(
        self,

        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        ws_root = os.path.realpath(find_workspace_root())
        meta = get_current_role_metadata()
        role_name = (
            str((meta.get("role_name") or meta.get("role") or "") if meta else "")
            .split(":")[-1]
            .strip()
            .lower()
        )
        d_scope = (
            dir_scope
            or ((meta.get("dir_scope") or meta.get("parts_dir", "")) if meta else "")
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
        work_mgr = get_singleton(work.WorkspaceWorkManager)
        pending_mgr = get_singleton(pending.WorkspacePendingManager)

        if main_root and os.path.isdir(main_root) and main_root != ws_root:
            try:
                sync_svc = get_singleton(sync.WorkspaceSynchronizer)
                sync_svc.pull(ws_root, main_root, role_name, dir_scope=d_scope, silent=True)
                sync_svc.refresh_system_files(
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

        reg = get_singleton(role_registry.WorkspaceRegistry)
        role_guide_path: Optional[str] = None
        if role_name:
            try:
                r_def = reg.resolve_role_definition(role_name, repo_root=main_root)
                if r_def and r_def.guide_path:
                    role_guide_path = r_def.guide_path
            except Exception:
                pass

        if meta and not force:
            pending_targets = pending_mgr.get_pending_work(ws_root)
            if pending_targets:
                still_dirty = [
                    pt
                    for pt in pending_targets
                    if pending_mgr.is_pending_target_dirty(
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
                        if role_guide_path:
                            print(f"      Companion Guide to Follow:")
                            print(f"        - {role_guide_path}")
                        contracts = work_mgr.resolve_contract_files(
                            pt, ws_root, role_name=role_name
                        )
                        if contracts:
                            print(f"      Contracts / Specifications to Read:")
                            for c in contracts:
                                print(f"        - {c}")
                    print(
                        f"\n MANDATORY ACTION REQUIRED:\n"
                        f"Every pending target MUST be resolved using one of the following commands before calling get_work or concluding the round.\n"
                        f"Outputting conversational commentary, complaining that check_files did not change, or repeating checks without resolving targets is prohibited.\n"
                    )
                    if is_auditor_role(role_name):
                        print(
                            f"1. When verification checks pass and contracts are certified:\n"
                            f"     bin/submit <target_file> (attests {role_name.upper()}_AUDIT)\n"
                            f"2. When verification fails or code/tests violate contracts:\n"
                            f"     bin/blame <culprit_file> \"<actionable critique>\"\n"
                            f"     (e.g., blame the library module or test module for the failure)\n"
                            f"3. When an unresolvable impasse is reached or success is impossible:\n"
                            f"     bin/fail <target_file> \"<reason>\"\n"
                        )
                    else:
                        print(
                            f"1. When implementation/test is complete and verification passes:\n"
                            f"     bin/submit <target_file> \"<change summary>\" (or bin/submit <target_file> if unmodified)\n"
                            f"2. When an upstream contract or specification is defective/contradictory:\n"
                            f"     bin/blame <culprit_contract> \"<actionable critique>\"\n"
                            f"3. When an unresolvable impasse is reached or success is impossible:\n"
                            f"     bin/fail <target_file> \"<reason>\"\n"
                        )
                    return 1
                else:
                    pending_mgr.clear_pending_work(ws_root)

        eval_root = (
            main_root if (meta and main_root and os.path.isdir(main_root)) else ws_root
        )
        ready_items, blocked_items = _compute_role_work_queue(
            role_name, d_scope, eval_root
        )

        print(
            f"\n=== Cleanroom Work Queue [Role: {(role_name or 'ALL').upper()} | Scope: {d_scope}] ==="
        )
        if not ready_items and not blocked_items:
            if meta:
                pending_mgr.clear_pending_work(ws_root)
            print(
                f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
            )
            return 0

        effective_batch_size = batch_size
        if effective_batch_size is None and meta and meta.get("batch_size"):
            try:
                effective_batch_size = int(meta["batch_size"])
            except (ValueError, TypeError):
                pass
        effective_max_feedback_chars: Optional[int] = None
        if meta and meta.get("max_feedback_chars"):
            try:
                effective_max_feedback_chars = int(meta["max_feedback_chars"])
            except (ValueError, TypeError):
                pass
        m_entry = _resolve_active_model_entry(meta, ws_root, main_root)
        if m_entry is not None:
            if effective_batch_size is None:
                b_val = m_entry.get("batch_size")
                if b_val is not None:
                    effective_batch_size = int(b_val)
            if effective_max_feedback_chars is None:
                fb_chars = m_entry.get("max_feedback_chars")
                if fb_chars is not None:
                    effective_max_feedback_chars = int(fb_chars)

        total_ready = len(ready_items)
        remaining_count = 0
        if effective_batch_size is not None and effective_batch_size > 0 and len(ready_items) > effective_batch_size:
            remaining_count = len(ready_items) - effective_batch_size
            presented_items = ready_items[:effective_batch_size]
        else:
            presented_items = ready_items

        if meta and presented_items:
            pending_mgr.set_pending_work(
                ws_root, [it["target_file"] for it in presented_items]
            )

        if presented_items:
            print("  READY FOR EXECUTION (Prerequisites satisfied):")
            for item in presented_items:
                print(f"    • {item['target_file']} ({item['role']})")
                item_guide = role_guide_path
                if item.get("role") and item["role"] != role_name:
                    try:
                        ir_def = reg.resolve_role_definition(item["role"], repo_root=main_root)
                        if ir_def and ir_def.guide_path:
                            item_guide = ir_def.guide_path
                    except Exception:
                        pass
                if item_guide:
                    print(f"      Companion Guide to Follow:")
                    print(f"        - {item_guide}")
                if item.get("reasons"):
                    print("      Dirty Reasons:")
                    for r in item["reasons"]:
                        display_reason = r
                        if effective_max_feedback_chars is not None and len(display_reason) > effective_max_feedback_chars:
                            display_reason = display_reason[:effective_max_feedback_chars] + f"... [truncated: total {len(r)} chars]"
                        print(f"        - {display_reason}")
                if item.get("contract_files"):
                    print("      Contracts / Specifications to Read:")
                    for c in item["contract_files"]:
                        print(f"        - {c}")
                if item.get("dependencies"):
                    print("      Dependencies:")
                    for dep in item["dependencies"]:
                        print(f"        - {dep}")

        if remaining_count > 0:
            print(
                f"\n  ℹ NOTE: {remaining_count} additional ready unit(s) are deferred to subsequent batches."
            )

        if not presented_items and blocked_items:
            print("  BLOCKED (Waiting on prerequisites):")
            for item in blocked_items:
                print(f"    • {item['target_file']} ({item['role']})")
                if item.get("reasons"):
                    print("      Dirty Reasons:")
                    for r in item["reasons"]:
                        print(f"        - {r}")
                if item.get("blocked_reasons"):
                    print("      Blocked By:")
                    for br in item["blocked_reasons"]:
                        print(f"        - {br}")
                if item.get("dependencies"):
                    print("      Dependencies:")
                    for dep in item["dependencies"]:
                        print(f"        - {dep}")

        has_feedback = False
        if role_name:
            try:
                reg = get_singleton(role_registry.WorkspaceRegistry)
                r_def = reg.resolve_role_definition(role_name, repo_root=main_root)
                has_feedback = bool(r_def.feedback_role_deps if hasattr(r_def, "feedback_role_deps") else ())
            except Exception:
                has_feedback = is_auditor_role(role_name)

        if not presented_items and blocked_items:
            print(
                "\nACTIONABLE NEXT STEP: All ready targets for this role round are resolved or waiting on upstream prerequisites. Conclude your round immediately without executing additional tools.\n"
            )
        elif not presented_items and not ready_items:
            print(
                "\nACTIONABLE NEXT STEP: No targets are currently pending or ready for this role. Conclude your round immediately without executing additional tools.\n"
            )
        elif is_auditor_role(role_name):
            blame_clause = "; if defects exist, run 'bin/blame <culprit_file> \"<critique>\"'" if has_feedback else ""
            print(
                f"\nACTIONABLE NEXT STEP: Run 'bin/check_files' immediately to verify targets. If clean, run 'bin/submit <target_file>' to attest {role_name.upper()}_AUDIT{blame_clause} (or 'bin/fail <target_file> \"<reason>\"' on unresolvable impasse).\n"
            )
        else:
            blame_clause = " (or 'bin/blame <culprit_contract> \"<critique>\"' if upstream contract is defective)" if has_feedback else " (or 'bin/submit <file>' if no changes)"
            print(
                f"\nACTIONABLE NEXT STEP: Read contracts and companion guide, implement changes, verify with 'bin/check_files', then run 'bin/submit <file> \"<summary>\"'{blame_clause} (or 'bin/fail <target_file> \"<reason>\"' on unresolvable impasse).\n"
            )
        return 1 if ready_items else 0

    # Contract: Executes role-specific verification checks, linters, and type checking for targets, regenerating if missing.
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
            pending_mgr = get_singleton(pending.WorkspacePendingManager)
            pending_targets = pending_mgr.get_pending_work(ws_root)
            if pending_targets:
                targets_to_check.extend(pending_targets)

        if not targets_to_check:
            print("No pending or specified targets to check.")
            return 0

        failed_count = 0
        effective_max_failures = _resolve_effective_max_failures(meta, ws_root, main_root)
        submit_coord = get_singleton(submit.SubmissionCoordinator)
        for cand in targets_to_check:
            target_path, unit_name = submit_coord.resolve_submit_target(
                cand, ws_root, role_name, d_scope
            )
            if not target_path or not os.path.isfile(target_path):
                target_path, unit_name = submit_coord.resolve_submit_target(
                    cand, main_root, role_name, d_scope
                )

            if not target_path or not os.path.isfile(target_path):
                regen_reg = get_singleton(role_registry.WorkspaceRegistry)
                regen_def = regen_reg.resolve_role_definition(
                    role_name, repo_root=main_root
                )
                if regen_def.template or regen_def.template_command:
                    regen_mgr = get_singleton(work.WorkspaceWorkManager)
                    regen_mgr.compute_role_work_queue(role_name, d_scope, ws_root)
                    target_path, unit_name = submit_coord.resolve_submit_target(
                        cand, ws_root, role_name, d_scope
                    )

            if not target_path or not os.path.isfile(target_path):
                print(f"Error: Target '{cand}' not found on disk.")
                failed_count += 1
                continue


            ref_root = ws_root if target_path.startswith(ws_root) else main_root
            part_dir, u_name, _ = submit_coord.parse_unit_from_file_path(
                target_path, ref_root
            )

            active_unit = u_name or unit_name

            print(f"=== Checking {active_unit} (role: {role_name}, part: {part_dir}) ===")
            unit_failed = False

            reg = get_singleton(role_registry.WorkspaceRegistry)
            r_def = reg.resolve_role_definition(role_name, repo_root=main_root)
            cmd_tmpl = r_def.verify_template
            if not cmd_tmpl or cmd_tmpl.strip().startswith("#"):
                print(f"[OK] No verification check required for {active_unit} in role {role_name}.")
            else:
                formatted_cmd = cmd_tmpl.format(
                    unit_dir=part_dir,
                    unit_name=active_unit,
                    max_failures=effective_max_failures,
                    maxfail_arg=f"--maxfail={effective_max_failures}",
                )
                env = dict(os.environ)
                if "pytest" in cmd_tmpl or "pytest" in formatted_cmd:
                    existing_addopts = env.get("PYTEST_ADDOPTS", "")
                    if "--maxfail" not in existing_addopts and "--maxfail" not in formatted_cmd:
                        env["PYTEST_ADDOPTS"] = (
                            f"{existing_addopts} --maxfail={effective_max_failures}".strip()
                        )
                env["BUILD_WORKSPACE_DIRECTORY"] = ws_root
                if "UV_PROJECT" not in env and main_root:
                    env["UV_PROJECT"] = main_root
                # Dynamic PYTHONPATH assembly strictly bounded to role workspace, isolating from canonical root.
                pypaths: list[str] = []
                for root_cand in (ws_root,):
                    if not root_cand or not os.path.isdir(root_cand):
                        continue
                    if root_cand not in pypaths:
                        pypaths.append(root_cand)
                    try:
                        for entry in os.listdir(root_cand):
                            pkg_dir = os.path.join(root_cand, entry)
                            if main_root:
                                mr_clean = os.path.abspath(main_root)
                                pd_clean = os.path.abspath(pkg_dir)
                                if pd_clean == mr_clean or pd_clean.startswith(mr_clean + os.sep):
                                    continue
                            if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv", "__pycache__")):
                                if pkg_dir not in pypaths:
                                    pypaths.append(pkg_dir)
                                sup_lib = os.path.join(pkg_dir, "support", "lib")
                                if os.path.isdir(sup_lib) and sup_lib not in pypaths:
                                    pypaths.append(sup_lib)
                    except OSError:
                        pass
                if "PYTHONPATH" in env:
                    for p in env["PYTHONPATH"].split(os.pathsep):
                        p_clean = os.path.abspath(p)
                        if main_root:
                            mr_clean = os.path.abspath(main_root)
                            if p_clean == mr_clean or p_clean.startswith(mr_clean + os.sep):
                                continue
                        if p and p not in pypaths:
                            pypaths.append(p)
                env["PYTHONPATH"] = os.pathsep.join(pypaths)
                env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")


                cmd_timeout = float(os.environ.get("CLEANROOM_VERIFY_TIMEOUT", "60.0"))
                try:
                    res = subprocess.run(
                        formatted_cmd,
                        shell=True,
                        cwd=ws_root,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=cmd_timeout,
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
                except subprocess.TimeoutExpired as exc:
                    out_text = (exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
                    err_text = (exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
                    print(
                        f"[FAIL] Verification timed out after {cmd_timeout:.1f}s for {active_unit}:\n{out_text}\n{err_text}".strip()
                    )
                    unit_failed = True

            if unit_failed:
                failed_count += 1
                record_check_executed(ws_root, target_path, passed=False)
            else:
                record_check_executed(ws_root, target_path, passed=True)
                print(f"[PASSED] All verification checks passed for '{active_unit}'.")
                unacted_fb = _extract_unacted_feedback(target_path)
                if unacted_fb:
                    print(
                        f"\n[ATTENTION] Target has {len(unacted_fb)} pending unacted feedback item(s):\n"
                        + "\n".join(f"  • {item}" for item in unacted_fb)
                        + "\nNotice: Static verification passed, but it does NOT verify that runtime feedback was fixed."
                        + "\nYou MUST verify that your code logic satisfies the contract and resolves the defect before calling bin/submit!\n"
                    )

        return 1 if failed_count > 0 else 0

    # Contract: Returns True if the target has been checked via check_files since its last modification.
    def is_checked_since_modification(
        self,
        ws_root: str,
        target_path: str,
    ) -> bool:
        return _is_checked_since_modification(ws_root, target_path)

    # Contract: Records file verification execution and content hash in .cleanroom/.last_check_files.json.
    def record_check_executed(
        self,
        ws_root: str,
        target_path: str,
        passed: bool,
    ) -> None:
        record_check_executed(ws_root, target_path, passed)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-18T19:13:51Z
# LAST_CHANGED: 2026-10-20T21:10:00Z
# CHANGE: Direct immediate round conclusion in actionable next step when only blocked targets remain
# COVERAGE_AUDIT: 2026-10-18T19:13:51Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceChecker,
        keys=[check.WorkspaceChecker, WorkspaceChecker],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
