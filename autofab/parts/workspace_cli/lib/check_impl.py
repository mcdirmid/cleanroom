"""Low-level implementation for check_impl."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import re
import shutil
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
from autofab.parts.agent.lib import node_config, session as agent_session
from autofab.parts.control.lib import submit
from autofab.parts.workspace.lib import (
    provision,
    role_registry,
    sync,
)
try:
    from support.lib import app_info
except ImportError:
    import app_info  # type: ignore
from . import (
    check,
    pending,
    work,
)


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


def is_auditor_role(role_name: str, repo_root: Optional[str] = None) -> bool:
    if not role_name:
        return False
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(role_registry.WorkspaceRegistry)
    try:
        r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
        if r_def.fused_roles:
            return False
        return bool(r_def.audit_tag or not r_def.src_pattern)
    except Exception:
        return False


def resolve_common_spec_files(
    role_name: str,
    part_dir: str,
    unit_name: Optional[str],
    ws_root: str,
    repo_root: Optional[str] = None,
) -> List[str]:
    """Resolves existing specification files for a unit from the active role's common_spec_roles."""
    if not unit_name:
        return []
    clean_r = role_name.split(":")[-1].strip().lower()
    reg = get_singleton(role_registry.WorkspaceRegistry)
    try:
        r_def = reg.resolve_role_definition(clean_r, repo_root=repo_root)
    except Exception:
        return []

    meta = get_current_role_metadata()
    spec_roles = list(
        getattr(r_def, "common_spec_roles", None)
        or (meta.get("common_spec_roles") if meta else None)
        or r_def.star_role_deps
        or []
    )
    if not spec_roles:
        return []

    resolved: List[str] = []
    base_unit = unit_name[:-5] if unit_name.endswith("_impl") else unit_name

    for s_role in spec_roles:
        try:
            s_def = reg.resolve_role_definition(s_role, repo_root=repo_root)
        except Exception:
            continue
        if not s_def.src_pattern:
            continue

        cands = [s_def.src_pattern.format(unit_dir=part_dir, unit_name=unit_name)]
        if base_unit != unit_name:
            cands.append(s_def.src_pattern.format(unit_dir=part_dir, unit_name=base_unit))

        found_any = False
        for c in cands:
            full_ws = os.path.join(ws_root, c) if not os.path.isabs(c) else c
            full_repo = os.path.join(repo_root, c) if (repo_root and not os.path.isabs(c)) else None

            if os.path.isfile(full_ws):
                rel = os.path.relpath(full_ws, ws_root)
                if rel not in resolved:
                    resolved.append(rel)
                found_any = True
            elif full_repo and os.path.isfile(full_repo):
                rel = os.path.relpath(full_repo, repo_root) if repo_root else c
                if rel not in resolved:
                    resolved.append(rel)
                found_any = True

        if not found_any and cands:
            if cands[0] not in resolved:
                resolved.append(cands[0])

    return resolved


def _is_role_writable_file(role_def: Any, file_path: str) -> bool:
    if not role_def:
        return True
    patterns = (
        (role_def.writable_file_patterns if hasattr(role_def, "writable_file_patterns") else None)
        or ()
    )
    if not patterns:
        return False
    import fnmatch
    norm_path = file_path.replace("\\", "/")
    fname = os.path.basename(norm_path)
    for pat in patterns:
        pat_norm = pat.replace("\\", "/")
        if fnmatch.fnmatch(norm_path, f"*{pat_norm}") or fnmatch.fnmatch(fname, pat_norm):
            return True
        if pat_norm.endswith("/*") and pat_norm[:-2] in norm_path:
            return True
        if "/*." in pat_norm:
            dir_part = pat_norm.split("/")[0]
            if f"/{dir_part}/" in norm_path or norm_path.startswith(f"{dir_part}/"):
                return True
    return False


def _verify_and_revert_readonly_integrity(
    ws_root: str, main_root: str, role_name: str, dir_scope: str = ""
) -> Optional[str]:
    """Verifies that package __init__.py files have not been modified.

    If any unauthorized modification is detected, reverts the file from canonical state,
    restores read-only permissions, and returns an error description.
    """
    if not ws_root or not main_root or os.path.realpath(ws_root) == os.path.realpath(main_root):
        return None

    tampered_files: List[str] = []
    scan_root = (
        os.path.join(ws_root, dir_scope)
        if dir_scope and os.path.isdir(os.path.join(ws_root, dir_scope))
        else ws_root
    )

    for root, dirs, files in os.walk(scan_root):
        dirs[:] = [
            d for d in dirs
            if d not in ("support", ".git", ".venv", "__pycache__", ".antigravity", "bin", ".bazel", "staging_tests", "guides")
        ]
        if "__init__.py" in files:
            init_ws = os.path.join(root, "__init__.py")
            rel_p = os.path.relpath(init_ws, ws_root)
            main_init = os.path.join(main_root, rel_p)
            if os.path.isfile(main_init):
                try:
                    with open(init_ws, "rb") as f_ws, open(main_init, "rb") as f_main:
                        if f_ws.read() != f_main.read():
                            shutil.copy2(main_init, init_ws)
                            try:
                                os.chmod(init_ws, 0o444)
                            except OSError:
                                pass
                            tampered_files.append(rel_p)
                except OSError:
                    pass
            else:
                try:
                    with open(init_ws, "r", encoding="utf-8", errors="replace") as f_ws:
                        if f_ws.read().strip():
                            with open(init_ws, "w", encoding="utf-8") as f_ws_w:
                                f_ws_w.write("")
                            try:
                                os.chmod(init_ws, 0o444)
                            except OSError:
                                pass
                            tampered_files.append(rel_p)
                except OSError:
                    pass

    if tampered_files:
        unique_tampered = list(dict.fromkeys(tampered_files))
        return (
            f"Package __init__.py file(s) have been modified: "
            f"{', '.join(unique_tampered)}. "
            f"Workers are strictly prohibited from modifying package __init__.py. "
            f"Reverted to canonical repository state."
        )
    return None


def record_check_executed(ws_root: str, target_path: str, passed: bool) -> None:
    """Records file verification execution and content hash in state directory (.last_check_files.json)."""
    state_dir = app_info.resolve_state_dir(ws_root)
    rec_file = os.path.join(state_dir, ".last_check_files.json")
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
    rec_file = os.path.join(app_info.resolve_state_dir(ws_root), ".last_check_files.json")
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
    """Extracts unacted feedback lines from a target file's metadata header."""
    if not file_path or not os.path.isfile(file_path):
        return []
    feedback_items: List[str] = []
    try:
        try:
            from autofab.parts.metadata.lib import src_metadata  # type: ignore
        except ImportError:
            import src_metadata  # type: ignore
        meta = src_metadata.extract_metadata(file_path)
        if meta and meta.feedback:
            for item in meta.feedback:
                clean_item = re.sub(r"^\[.*?\]:\s*", "", item.strip())
                if clean_item and clean_item not in feedback_items:
                    feedback_items.append(clean_item)
            return feedback_items
    except Exception:
        pass
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            in_header = False
            in_feedback = False
            for line in f:
                stripped = line.strip()
                if "CLEANROOM METADATA" in stripped or "AUTOFAB METADATA" in stripped:
                    in_header = True
                    continue
                if "END CLEANROOM METADATA" in stripped or "END AUTOFAB METADATA" in stripped or (in_header and stripped == "-->"):
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
                        if clean_item and clean_item not in feedback_items:
                            feedback_items.append(clean_item)
                    elif stripped and not stripped.startswith("-"):
                        in_feedback = False
    except OSError:
        pass
    return feedback_items


def _extract_last_change_comment(file_path: str) -> Optional[str]:
    """Extracts the latest # CHANGE: comment from the file metadata header or file comments."""
    if not file_path or not os.path.isfile(file_path):
        return None
    try:
        try:
            from autofab.parts.metadata.lib import src_metadata  # type: ignore
        except ImportError:
            import src_metadata  # type: ignore
        meta = src_metadata.extract_metadata(file_path)
        if meta and meta.change_summary:
            return meta.change_summary
    except Exception:
        pass
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if "CHANGE:" in stripped:
                    m = re.search(r"CHANGE:\s*(.*)", stripped)
                    if m:
                        change_text = m.group(1).strip()
                        if change_text.endswith("-->"):
                            change_text = change_text[:-3].strip()
                        if change_text:
                            return change_text
    except OSError:
        pass
    return None


def _extract_primary_failure(stdout: str, stderr: str, is_timeout: bool = False, timeout_sec: Optional[float] = None) -> str:
    """Extracts the primary failure exception, assertion, or error diagnostic from command output."""
    if is_timeout:
        return f"Execution timed out after {timeout_sec or 0:.1f}s (possible infinite loop or deadlock detected in code under test)."
    combined = (stdout + "\n" + stderr).strip()
    if not combined:
        return "Verification failed with non-zero exit status."

    failed_lines = [line.strip() for line in combined.splitlines() if line.strip().startswith("FAILED ")]
    e_lines = [
        line.strip()
        for line in combined.splitlines()
        if re.match(r"^E\s+([A-Za-z_]+Error:|assert )", line.strip())
        or re.match(r"^[A-Za-z_]+Error:", line.strip())
    ]
    if failed_lines:
        if e_lines:
            return f"{failed_lines[0]} ({e_lines[0]})"
        return failed_lines[0]
    if e_lines:
        return e_lines[0]

    err_lines = [
        line.strip()
        for line in combined.splitlines()
        if "error:" in line.lower() or "fail" in line.lower()
    ]
    if err_lines:
        return err_lines[0]

    non_empty = [line.strip() for line in combined.splitlines() if line.strip()]
    return non_empty[-1] if non_empty else "Verification failed."


def _strip_arbiter_reminders(text: str) -> str:
    """Strips redundant arbiter reminder banners from child process output."""
    if not text:
        return text
    patterns = [
        r"(?:\n|^)(?:={40,}\n)?\[(?:QA|PRETENSE QA|COVERAGE) ARBITER REMINDER[^\]]*\].*?(?:={40,}|\Z)",
        r"(?:\n|^)AGENT GUIDANCE / COVERAGE ARBITER REMINDER.*?(?:={40,}|\Z)",
    ]
    cleaned = text
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def _print_triage_summary(
    ws_root: str,
    target_path: str,
    active_unit: Optional[str],
    part_dir: str,
    role_name: str,
    stdout: str,
    stderr: str,
    is_timeout: bool = False,
    timeout_sec: Optional[float] = None,
    main_root: Optional[str] = None,
) -> None:
    """Prints the structured triage summary and specification grounding reminders."""
    target_rel = os.path.relpath(target_path, ws_root) if ws_root and target_path.startswith(ws_root) else target_path
    change_header = _extract_last_change_comment(target_path) or "(None recorded)"
    primary_failure = _extract_primary_failure(stdout, stderr, is_timeout=is_timeout, timeout_sec=timeout_sec)
    candidate_culprit = target_rel

    spec_files = resolve_common_spec_files(role_name, part_dir, active_unit, ws_root, repo_root=main_root)
    spec_desc = ", ".join(spec_files) if spec_files else "the common specification"

    print("\n" + "=" * 80)
    print(f"======================= {app_info.get_app_title()} Triage Summary =======================")
    print(f"Target: {target_rel}")
    print(f"Author's Latest # CHANGE: \"{change_header}\"")
    print(f"Primary Failure: {primary_failure}")
    print(f"Candidate Culprit: {candidate_culprit} (or companion test/pretense module)")
    print("\nACTION REQUIRED:")
    print("• You are an AUDITOR, not an author. Do NOT write debug scripts.")
    print(f"• Audit the failure against the specification ({spec_desc}).")
    print(f"• Determine the culprit file: the library module ({target_rel}) if implementation violates contracts, or the companion test/pretense module if tests violate preconditions or assert unmandated behavior.")
    print("• Deliver attribution via: bin/blame <culprit_file> \"<critique>\"")
    print("• After blaming, run 'bin/get_work' to inspect remaining units and conclude.")
    print("=" * 80)

    if "coverage" in role_name:
        print(
            "\n[COVERAGE ARBITER REMINDER - EXPLAIN FEEDBACK IN TERMS OF SPECIFICATION]\n"
            f"• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification ({spec_desc}).\n"
            "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
            "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
            "• Translate uncovered statements and branches into missing specification requirements or scenario cases.\n"
            "• If an uncovered branch is an unreachable defensive check or caller assumption guaranteed by the specification, instruct the implementation author to prune it or mark it as unreachable according to the methodology.\n"
            "• If an uncovered line persists after tests were updated or across multiple rounds, examine the library implementation closely: trace control flow and invariants to verify whether the line is structurally unreachable or defensive dead code; if unreachable, blame the library (prune, unreachable(), or # pragma: no cover)."
        )
    elif "pretense" in role_name:
        print(
            "\n[PRETENSE QA ARBITER REMINDER - RULES ON ERRORS AND PRECONDITIONS]\n"
            f"• Blame feedback MUST be provided in terms of how the blamed file violates the specification ({spec_desc}).\n"
            "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
            "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
            "• Frame test failures strictly as contract discrepancies against the specification.\n"
            "• Checked preconditions (*Error, e.g. NodeNotFoundError, CycleError) CANNOT be tested:\n"
            "  - NEVER blame the library for raising an *Error on invalid caller inputs.\n"
            "  - NEVER wrap *Error in with raises() or try/except in test or pretense code.\n"
            "  - If Hypothesis crashes on *Error, blame the interface state machine (pretense/<iface>_pretense.py) for failing to gate inputs with require(self.state.<cond>).\n"
            "  - Precondition guards in require(...) MUST ONLY check self.state (rule PN009), NEVER target (SUT).\n"
            "• Operational postconditions: only contracted runtime failures from seeded conditions use with raises(ExpectedException).\n"
            "• Single-paragraph blame: exactly 2 arguments (bin/blame <culprit_file> \"<critique>\"), no newlines."
        )
    else:
        print(
            "\n[QA ARBITER REMINDER - EXPLAIN DEFECTS IN TERMS OF SPECIFICATION]\n"
            f"• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification ({spec_desc}).\n"
            "• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
            "• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
            "• Frame test failures strictly as contract discrepancies against the specification.\n"
            "• Explain the expected postcondition outcome versus the observed behavior.\n"
            "• Preconditions cannot be tested: *Error exceptions designate contract violations and must never be tested or expected with raises(). If an *Error occurs, blame the test module for violating preconditions, NEVER the library."
        )
    print("=" * 80 + "\n")


def find_workspace_root() -> str:
    """Discovers root of commissioned role workspace or repo root."""
    curr = os.getcwd()
    while curr and curr != os.path.dirname(curr):
        if any(os.path.isfile(os.path.join(curr, d)) for d in app_info.get_role_descriptors()):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()


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
            if any(os.path.isfile(os.path.join(check_role, d)) for d in app_info.get_role_descriptors()):
                parent_dir = os.path.dirname(check_role)
                if os.path.basename(parent_dir) in app_info.get_role_workspaces_containers():
                    return os.path.realpath(os.path.dirname(parent_dir))
                return os.path.realpath(parent_dir)
            check_role = os.path.dirname(check_role)
        return os.path.realpath(curr)


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
        elif stem.endswith("_pretense"):
            stem = stem[:-9]
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


def _resolve_workspace_guide_path(ws_root: str, guide_path: Optional[str]) -> Optional[str]:
    """Resolves a role definition guide path to its workspace-relative path ('guides/<basename>')."""
    if not guide_path:
        return None
    ws_guide = f"guides/{os.path.basename(guide_path)}"
    if os.path.isfile(os.path.join(ws_root, ws_guide)):
        return ws_guide
    if os.path.isfile(os.path.join(ws_root, guide_path)):
        return guide_path
    return ws_guide


def _verify_antigravity_argon_model(ws_root: str, meta: Optional[Dict[str, Any]]) -> Optional[str]:
    """Verifies when gemini-argon is configured on antigravity that the active subagent is actually using gemini-argon."""
    if not meta:
        return None
    cfg_model = str(meta.get("model") or "").strip().lower()
    if "argon" not in cfg_model:
        return None
    harness = str(meta.get("harness") or "antigravity").strip().lower()
    if harness not in ("antigravity", ""):
        return None

    ag_dir = os.environ.get("ANTIGRAVITY_BRAIN_DIR") or os.path.expanduser("~/.gemini/antigravity")
    brain_dir = os.path.join(ag_dir, "brain")
    conv_dir = os.path.join(ag_dir, "conversations")
    if not os.path.isdir(brain_dir) or not os.path.isdir(conv_dir):
        return None

    ws_name = os.path.basename(ws_root)
    candidate_cids: List[Tuple[float, str]] = []
    try:
        for entry in os.listdir(brain_dir):
            if entry.startswith("."):
                continue
            t_file = os.path.join(brain_dir, entry, ".system_generated", "logs", "transcript.jsonl")
            if not os.path.isfile(t_file):
                continue
            try:
                mtime = os.path.getmtime(t_file)
                with open(t_file, "r", encoding="utf-8", errors="replace") as f:
                    head = "".join(f.readline() for _ in range(4))
                if ws_root in head or ws_name in head:
                    candidate_cids.append((mtime, entry))
            except OSError:
                continue
    except OSError:
        return None

    if not candidate_cids:
        return None

    candidate_cids.sort(key=lambda x: x[0], reverse=True)
    cid = candidate_cids[0][1]
    db_path = os.path.join(conv_dir, f"{cid}.db")
    if not os.path.isfile(db_path):
        return None

    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = conn.cursor()
            cur.execute("SELECT data FROM gen_metadata ORDER BY idx DESC LIMIT 3")
            rows = cur.fetchall()
        finally:
            conn.close()
        for (blob,) in rows:
            if not isinstance(blob, (bytes, bytearray)):
                continue
            text = blob.decode("utf-8", errors="ignore").lower()
            if "argon" in text:
                return None
            m = re.search(r"(gemini-[a-z0-9\.\-]+|claude-[a-z0-9\.\-]+)", text)
            if m:
                actual_model = m.group(1)
                return (
                    f"Error: Model '{meta.get('model')}' was specified (which requires 'inherit' in Antigravity), "
                    f"but the active conversation is executing on '{actual_model}' instead of Gemini Argon.\n"
                    f"Please manually switch your model in Antigravity to 'Gemini Argon' before requesting the run again."
                )
    except Exception:
        return None
    return None


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
        argon_err = _verify_antigravity_argon_model(ws_root, meta)
        if argon_err:
            print(f"\n[CRITICAL MODEL MISMATCH] {argon_err}", file=sys.stderr)
            print(f"\n[CRITICAL MODEL MISMATCH] {argon_err}")
            return 1
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

        reg = get_singleton(role_registry.WorkspaceRegistry)
        role_guide_path: Optional[str] = None
        is_fused = bool(meta and meta.get("fused_roles"))
        if role_name:
            try:
                r_def = reg.resolve_role_definition(role_name, repo_root=main_root)
                if r_def and r_def.guide_path:
                    role_guide_path = _resolve_workspace_guide_path(ws_root, r_def.guide_path)
                if r_def and r_def.fused_roles:
                    is_fused = True
            except Exception:
                pass

        if main_root and os.path.isdir(main_root) and main_root != ws_root:
            try:
                sync_svc = get_singleton(sync.WorkspaceSynchronizer)
                if not is_fused:
                    sync_svc.pull(
                        ws_root,
                        main_root,
                        role_name,
                        dir_scope=d_scope,
                        silent=True,
                        delete_missing=False,
                    )
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

        effective_max_feedback_chars: Optional[int] = None
        if meta and meta.get("max_feedback_chars"):
            try:
                effective_max_feedback_chars = int(meta["max_feedback_chars"])
            except (ValueError, TypeError):
                pass
        m_entry = _resolve_active_model_entry(meta, ws_root, main_root)
        if m_entry is not None and effective_max_feedback_chars is None:
            fb_chars = m_entry.get("max_feedback_chars")
            if fb_chars is not None:
                effective_max_feedback_chars = int(fb_chars)

        is_auditor = is_auditor_role(role_name, repo_root=main_root) if role_name else False
        ready_items: List[Dict[str, Any]] = []
        blocked_items: List[Dict[str, Any]] = []
        is_pending_relist = False

        if meta and not force and not is_fused and not is_auditor:
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
                    is_pending_relist = True
                    for pt in still_dirty:
                        pt_reasons = list(
                            pending_mgr.get_pending_target_reasons(
                                pt, ws_root, main_root=main_root, role_name=role_name
                            )
                        )
                        contracts = list(
                            work_mgr.resolve_contract_files(
                                pt, ws_root, role_name=role_name
                            )
                        )
                        ready_items.append({
                            "unit_name": os.path.splitext(os.path.basename(pt))[0],
                            "role": role_name,
                            "target_file": pt,
                            "reasons": pt_reasons,
                            "contract_files": contracts,
                            "dependencies": [],
                        })
                else:
                    pending_mgr.clear_pending_work(ws_root)

        if not ready_items:
            eval_root = (
                main_root if (meta and main_root and os.path.isdir(main_root)) else ws_root
            )
            ready_items, blocked_items = _compute_role_work_queue(
                role_name, d_scope, eval_root
            )

        if is_auditor and ready_items:
            marker = os.path.join(app_info.resolve_state_dir(ws_root), ".no_pending_work")
            if os.path.isfile(marker):
                try:
                    os.remove(marker)
                except OSError:
                    pass

            pending_mgr.set_pending_work(ws_root, [it["target_file"] for it in ready_items])
            sub_coord = get_singleton(submit.SubmissionCoordinator)
            failing_items: List[Dict[str, Any]] = []
            for it in ready_items:
                target_cand = it["target_file"]
                buf_out = io.StringIO()
                buf_err = io.StringIO()
                with redirect_stdout(buf_out), redirect_stderr(buf_err):
                    check_exit = self.run_check_files(target=target_cand, repo_root=main_root)
                if check_exit == 0:
                    outcome = sub_coord.submit_target_file(
                        target=target_cand,
                        repo_root=main_root,
                        workspace_root=ws_root,
                        role_name=role_name,
                    )
                    if outcome.accepted:
                        if outcome.message:
                            if hasattr(app_info, "append_log"):
                                app_info.append_log(target_cand, outcome.message, repo_root=main_root)
                                if ws_root != main_root:
                                    try:
                                        app_info.append_log(target_cand, outcome.message, repo_root=ws_root)
                                    except OSError:
                                        pass
                        print(f"✔ [AUTO-SUBMIT] Pre-verification passed for '{target_cand}'. Automatically recorded {role_name.upper()} audit approval.")
                    pending_mgr.remove_pending_target(ws_root, target_cand)
                else:
                    failing_items.append(it)

            ready_items = failing_items
            if ready_items:
                pending_mgr.set_pending_work(ws_root, [it["target_file"] for it in ready_items])
            else:
                pending_mgr.clear_pending_work(ws_root)

        print(
            f"\n=== {app_info.get_app_title()} Work Queue [Role: {(role_name or 'ALL').upper()} | Scope: {d_scope}] ==="
        )
        if not ready_items and not blocked_items:
            if meta:
                pending_mgr.clear_pending_work(ws_root)
            marker = os.path.join(app_info.resolve_state_dir(ws_root), ".no_pending_work")
            try:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("0\n")
            except OSError:
                pass
            print(
                f"✔ CLEAN: All units in scope '{d_scope}' are clean for role '{role_name}'.\n"
            )
            print(
                "[ROUND CONCLUSION DIRECTIVE]\n"
                "You have 0 ready targets. All work assigned to your role in this round is resolved.\n"
                "CRITICAL ACTION: You MUST conclude your round immediately.\n"
                "DO NOT invoke any further tool calls (no bin/get_work, no ls, no dummy commands).\n"
                "Delivering text with zero tool calls is the required signal that completes your round.\n"
            )
            return 0

        effective_batch_size = batch_size
        if effective_batch_size is None and meta and meta.get("batch_size"):
            try:
                effective_batch_size = int(meta["batch_size"])
            except (ValueError, TypeError):
                pass
        if effective_max_feedback_chars is None and meta and meta.get("max_feedback_chars"):
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
        if is_pending_relist:
            presented_items = ready_items
        elif effective_batch_size is not None and effective_batch_size > 0 and len(ready_items) > effective_batch_size:
            remaining_count = len(ready_items) - effective_batch_size
            presented_items = ready_items[:effective_batch_size]
        else:
            presented_items = ready_items

        if meta:
            if presented_items:
                pending_mgr.set_pending_work(
                    ws_root, [it["target_file"] for it in presented_items]
                )
            else:
                pending_mgr.clear_pending_work(ws_root)

        if presented_items:
            print("  READY FOR EXECUTION (Prerequisites satisfied):")
            for item in presented_items:
                print(f"    • {item['target_file']} ({item['role']})")
                item_guide = role_guide_path
                if item.get("role") and item["role"] != role_name:
                    try:
                        ir_def = reg.resolve_role_definition(item["role"], repo_root=main_root)
                        if ir_def and ir_def.guide_path:
                            item_guide = _resolve_workspace_guide_path(ws_root, ir_def.guide_path)
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

        marker = os.path.join(app_info.resolve_state_dir(ws_root), ".no_pending_work")
        if not presented_items:
            try:
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("0\n")
            except OSError:
                pass
            if blocked_items:
                print(
                    "\n[ROUND CONCLUSION DIRECTIVE]\n"
                    "All targets are blocked waiting on upstream prerequisites and you have 0 ready targets.\n"
                    "CRITICAL ACTION: You MUST conclude your round immediately.\n"
                    "DO NOT invoke any further tool calls (no bin/get_work, no ls, no dummy commands).\n"
                    "Delivering text with zero tool calls is the required signal that completes your round.\n"
                )
            else:
                print(
                    "\n[ROUND CONCLUSION DIRECTIVE]\n"
                    "You have 0 ready targets. All work assigned to your role in this round is resolved.\n"
                    "CRITICAL ACTION: You MUST conclude your round immediately.\n"
                    "DO NOT invoke any further tool calls (no bin/get_work, no ls, no dummy commands).\n"
                    "Delivering text with zero tool calls is the required signal that completes your round.\n"
                )
        else:
            if os.path.isfile(marker):
                try:
                    os.remove(marker)
                except OSError:
                    pass
            if is_fused:
                fused_roles = (meta.get("fused_roles") or []) if meta else []
                fused_cmds = ", ".join(f"'bin/verify_{r}'" for r in fused_roles) if fused_roles else "prescribed 'bin/verify_*' micro-binaries"
                print(
                    f"\nACTIONABLE NEXT STEP: Read contracts and companion guides, implement targets, "
                    f"verify with {fused_cmds}, complete arbiter self-audits, and report completion when all checks pass (do NOT run bin/submit).\n"
                )
            elif is_auditor:
                blame_clause = "; deliver blame attribution via 'bin/blame <culprit_file> \"<critique>\"'" if has_feedback else ""
                print(
                    f"\nACTIONABLE NEXT STEP: Verification checks failed above. Inspect the triage summary and failure diagnostics{blame_clause} (or 'bin/fail <target_file> \"<reason>\"' on unresolvable impasse). After blaming, run 'bin/get_work' to conclude.\n"
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
                raise ValueError(f"Cannot run check_files: no role defined for workspace '{ws_root}'.")
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

        is_fused = bool(meta and meta.get("fused_roles"))
        pending_mgr = get_singleton(pending.WorkspacePendingManager)
        pending_targets = list(pending_mgr.get_pending_work(ws_root))
        marker = os.path.join(app_info.resolve_state_dir(ws_root), ".no_pending_work")
        has_no_work_marker = os.path.isfile(marker)

        if not is_fused:
            if has_no_work_marker:
                print(
                    "Error: No pending work assigned to this role workspace.\n"
                    "Call bin/get_work first to acquire work, or conclude the round if all work is resolved."
                )
                return 1

            if pending_targets:
                if target:
                    norm_tgt = target.strip().lstrip("/").replace("\\", "/")
                    tgt_stem = _normalize_unit_stem(norm_tgt)
                    matched = any(
                        norm_tgt == pt.strip().lstrip("/").replace("\\", "/")
                        or norm_tgt.endswith(f"/{pt.strip().lstrip('/').replace('\\', '/')}")
                        or pt.strip().lstrip("/").replace("\\", "/").endswith(f"/{norm_tgt}")
                        or (tgt_stem and _normalize_unit_stem(pt) == tgt_stem)
                        for pt in pending_targets
                    )
                    if not matched:
                        print(
                            f"Error: Target '{target}' is not in the assigned pending work for this role workspace.\n"
                            f"Call bin/get_work to view assigned pending targets."
                        )
                        return 1
            elif not target:
                print("No pending or specified targets to check.")
                return 0

        targets_to_check: List[str] = []
        if target:
            targets_to_check.append(target)
        else:
            targets_to_check.extend(pending_targets)

        if not targets_to_check:
            print("No pending or specified targets to check.")
            return 0

        # Pull inbound changes from canonical main repository before running checks
        if main_root and os.path.isdir(main_root) and main_root != ws_root:
            try:
                sync_svc = get_singleton(sync.WorkspaceSynchronizer)
                if not is_fused:
                    sync_svc.pull(
                        ws_root,
                        main_root,
                        role_name,
                        dir_scope=d_scope,
                        silent=True,
                        delete_missing=False,
                    )
                sync_svc.refresh_system_files(
                    ws_root, main_root, role_name, dir_scope=d_scope, silent=True
                )
            except (OSError, RuntimeError) as e:
                sys.stderr.write(f"Warning: automatic sync from main failed: {e}\n")

        failed_count = 0
        effective_max_failures = _resolve_effective_max_failures(meta, ws_root, main_root)

        integrity_err = _verify_and_revert_readonly_integrity(
            ws_root, main_root, role_name, dir_scope=d_scope
        )
        if integrity_err:
            print(f"[FAIL] Workspace integrity check failed:\n  {integrity_err}")
            return 1

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
                if "run_cross_tests.py" in formatted_cmd and not os.path.isfile(os.path.join(ws_root, "bin", "run_cross_tests.py")):
                    cand_cross = os.path.join(main_root, "bin", "run_cross_tests.py") if main_root else ""
                    if cand_cross and os.path.isfile(cand_cross):
                        os.makedirs(os.path.join(ws_root, "bin"), exist_ok=True)
                        shutil.copy2(cand_cross, os.path.join(ws_root, "bin", "run_cross_tests.py"))
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
                if hasattr(app_info, "assemble_pythonpath_str"):
                    env["PYTHONPATH"] = app_info.assemble_pythonpath_str(
                        repo_root=main_root,
                        ws_root=ws_root,
                        existing_pythonpath=env.get("PYTHONPATH"),
                        isolate_from_repo_root=bool(main_root),
                    )
                else:
                    pypaths: list[str] = [ws_root] if ws_root else []
                    if "PYTHONPATH" in env:
                        pypaths.extend(p for p in env["PYTHONPATH"].split(os.pathsep) if p and p not in pypaths)
                    env["PYTHONPATH"] = os.pathsep.join(pypaths)
                env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")


                cmd_timeout = getattr(app_info, "get_verify_timeout", lambda: 60.0)()
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
                        clean_out = _strip_arbiter_reminders(res.stdout)
                        clean_err = _strip_arbiter_reminders(res.stderr)
                        combined_output = f"{clean_out}\n{clean_err}".strip()
                        if combined_output:
                            print(
                                f"[FAIL] Verification failed for {active_unit}:\n{combined_output}"
                            )
                        else:
                            print(f"[FAIL] Verification failed for {active_unit}")
                        unit_failed = True
                        if is_auditor_role(role_name, repo_root=main_root) or "coverage" in role_name or "qa" in role_name:
                            _print_triage_summary(
                                ws_root=ws_root,
                                target_path=target_path,
                                active_unit=active_unit,
                                part_dir=part_dir,
                                role_name=role_name,
                                stdout=res.stdout,
                                stderr=res.stderr,
                                is_timeout=False,
                                main_root=main_root,
                            )
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
                    out_text = (exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
                    err_text = (exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
                    clean_out = _strip_arbiter_reminders(out_text)
                    clean_err = _strip_arbiter_reminders(err_text)
                    diagnostic_parts = [
                        f"[FAIL] Verification timed out after {cmd_timeout:.1f}s for {active_unit} (possible infinite loop or deadlock detected in code under test).",
                        "NOTE: This execution timeout is a verification failure in the library or test code, NOT an infrastructure error.",
                        "Action: Diagnose the hanging method or infinite loop and issue a blame against the culprit file.",
                    ]
                    if clean_out:
                        diagnostic_parts.append(f"STDOUT:\n{clean_out}")
                    if clean_err:
                        diagnostic_parts.append(f"STDERR:\n{clean_err}")
                    print("\n".join(diagnostic_parts))
                    unit_failed = True
                    if is_auditor_role(role_name, repo_root=main_root) or "coverage" in role_name or "qa" in role_name:
                        _print_triage_summary(
                            ws_root=ws_root,
                            target_path=target_path,
                            active_unit=active_unit,
                            part_dir=part_dir,
                            role_name=role_name,
                            stdout=out_text,
                            stderr=err_text,
                            is_timeout=True,
                            timeout_sec=cmd_timeout,
                            main_root=main_root,
                        )

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

        if failed_count == 0 and os.path.isdir(os.path.join(ws_root, ".git")) and not is_auditor_role(role_name, repo_root=main_root):
            try:
                subprocess.run(["git", "add", "-A"], cwd=ws_root, check=True, capture_output=True, text=True)
                status_res = subprocess.run(["git", "status", "--porcelain"], cwd=ws_root, check=True, capture_output=True, text=True)
                if status_res.stdout.strip():
                    checked_label = ", ".join(targets_to_check)
                    subprocess.run(["git", "commit", "-m", f"Checkpoint: verified {checked_label}"], cwd=ws_root, check=True, capture_output=True, text=True)
            except Exception:
                pass

        return 1 if failed_count > 0 else 0

    # Contract: Returns True if the target has been checked via check_files since its last modification.
    def is_checked_since_modification(
        self,
        ws_root: str,
        target_path: str,
    ) -> bool:
        return _is_checked_since_modification(ws_root, target_path)

    # Contract: Records file verification execution and content hash in state directory (.last_check_files.json).
    def record_check_executed(
        self,
        ws_root: str,
        target_path: str,
        passed: bool,
    ) -> None:
        record_check_executed(ws_root, target_path, passed)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T11:00:00Z
# LAST_CHANGED: 2026-11-03T23:45:00Z
# CHANGE: Instruct coverage auditor when uncovered lines persist to examine library implementation for unreachable code
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
