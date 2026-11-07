"""Low-level implementation for sync_impl."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import stat
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
try:
    from support.lib import app_info
except Exception:
    import app_info  # type: ignore
from autofab.parts.agent.lib import session as agent_session
from autofab.parts.metadata.lib import src_metadata
from . import provision, role_registry, sync


def _find_methodology_for_scope(root: str, dir_scope: str) -> Optional[str]:
    """Finds methodology binding from configuration files within dir_scope or upward."""
    if not dir_scope:
        return None
    scope_dir = os.path.join(root, dir_scope)
    root_abs = os.path.abspath(root)

    cfg_filenames = app_info.get_config_filenames()
    import tomllib
    for fname in cfg_filenames:
        cand = os.path.join(scope_dir, fname)
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    data = tomllib.load(f)
                meth = data.get("methodology")
                if meth and isinstance(meth, str):
                    return meth.strip()
            except (OSError, tomllib.TOMLDecodeError):
                pass

    if os.path.isdir(scope_dir):
        try:
            for entry in os.listdir(scope_dir):
                sub = os.path.join(scope_dir, entry)
                if os.path.isdir(sub) and not entry.startswith((".", "bazel-", "venv")):
                    for fname in cfg_filenames:
                        sub_cand = os.path.join(sub, fname)
                        if os.path.isfile(sub_cand):
                            try:
                                with open(sub_cand, "rb") as f:
                                    data = tomllib.load(f)
                                meth = data.get("methodology")
                                if meth and isinstance(meth, str):
                                    return meth.strip()
                            except (OSError, tomllib.TOMLDecodeError):
                                pass
        except OSError:
            pass

    curr = os.path.abspath(scope_dir)
    while curr and curr.startswith(root_abs) and curr != root_abs:
        for fname in cfg_filenames:
            cand = os.path.join(curr, fname)
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        data = tomllib.load(f)
                    meth = data.get("methodology")
                    if meth and isinstance(meth, str):
                        return meth.strip()
                except (OSError, tomllib.TOMLDecodeError):
                    pass
        curr_parent = os.path.dirname(curr)
        if curr == curr_parent:
            break
        curr = curr_parent

    return None


def _resolve_active_methodology_pkg(
    resolved_root: str,
    dir_scope: str,
    role_def: Optional[Any] = None,
) -> Optional[str]:
    """Dynamically resolves the active methodology package directory name without hardcoding."""
    meth = _find_methodology_for_scope(resolved_root, dir_scope)
    if meth:
        clean = meth.lstrip("./").lstrip("/")
        if os.path.isdir(os.path.join(resolved_root, clean)):
            return clean

    if role_def and hasattr(role_def, "guide_path") and role_def.guide_path:
        for seg in role_def.guide_path.replace("\\", "/").split("/"):
            if seg and seg != "guides" and os.path.isdir(os.path.join(resolved_root, seg)):
                return seg
            if seg == "guides":
                break

    if role_def and hasattr(role_def, "template") and role_def.template:
        for seg in role_def.template.replace("\\", "/").split("/"):
            if seg and seg != "templates" and os.path.isdir(os.path.join(resolved_root, seg)):
                return seg
            if seg == "templates":
                break

    if dir_scope:
        top_scope = dir_scope.strip("/").split("/")[0]
        cand_pkg = os.path.join(resolved_root, top_scope)
        if os.path.isdir(cand_pkg) and (
            os.path.isdir(os.path.join(cand_pkg, "support"))
            or os.path.isdir(os.path.join(cand_pkg, "guides"))
            or os.path.isdir(os.path.join(cand_pkg, "templates"))
        ):
            return top_scope

    return None


# Buffer and descriptor filenames derived dynamically from app_info
BLAME_BUFFER_FILE: str = getattr(app_info, "DEFAULT_BLAME_BUFFER_FILE", ".autofab_blame_buffer.json")
AUDIT_BUFFER_FILE: str = getattr(app_info, "DEFAULT_AUDIT_BUFFER_FILE", ".autofab_audit_buffer.json")
ROLE_CONFIG_FILE: str = getattr(app_info, "DEFAULT_ROLE_DESCRIPTOR", ".autofab_role.json")


def _compute_file_sha256(path: str) -> Optional[str]:
    """Computes SHA-256 hash of a file on disk."""
    if not os.path.isfile(path):
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _get_pull_manifest_path(workspace_dir: str) -> str:
    """Returns absolute path to pull_manifest.json in the workspace state directory."""
    state_dir = app_info.resolve_state_dir(workspace_dir)
    return os.path.join(state_dir, "pull_manifest.json")


def _load_pull_manifest(workspace_dir: str) -> Dict[str, Dict[str, str]]:
    """Loads recorded inbound pull manifest from workspace state directory."""
    manifest_path = _get_pull_manifest_path(workspace_dir)
    if not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                files = data.get("files")
                if isinstance(files, dict):
                    return files
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_pull_manifest(workspace_dir: str, manifest: Dict[str, Dict[str, str]]) -> None:
    """Saves recorded inbound pull manifest to workspace state directory."""
    manifest_path = _get_pull_manifest_path(workspace_dir)
    try:
        state_dir = os.path.dirname(manifest_path)
        os.makedirs(state_dir, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "files": manifest}, f, indent=2)
    except OSError:
        pass


def write_file_with_perms(
    dst: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    """Writes a text file and sets exact permissions, delegating to WorkspaceProvisioner."""
    get_singleton(provision.WorkspaceProvisioner).write_file_with_permissions(
        dst, content, readonly=readonly, executable=executable
    )


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


def _is_runtime_support_library(fname: str) -> bool:
    """Returns True if file is a user-facing runtime API or type stub, excluding internal oracles."""
    base = fname.lower()
    if "lint" in base or "tool" in base or "runner" in base or base.startswith("app_info"):
        return False
    return fname.endswith((".py", ".pyi", ".bzl", ".toml"))


def _copy_projected_file(src: str, dst: str, is_writable: bool) -> None:
    """Copies a file into a role workspace, projecting metadata headers with ephemeral code hashes on writable files."""
    try:
        with open(src, "r", encoding="utf-8") as f:
            content = f.read()
        projected = _project_for_role_workspace(content, os.path.basename(src), is_writable=is_writable)
        write_file_with_perms(dst, projected, readonly=not is_writable)
    except (UnicodeDecodeError, OSError):
        copy_file_with_perms(src, dst, readonly=not is_writable)


def _parse_pat_to_glob(pat: str) -> Tuple[str, str, str]:
    """Decomposes a source path pattern into its directory, stem suffix, and extension."""
    if not pat:
        return "", "", ""
    parts = pat.split("/")
    d = parts[1] if len(parts) > 1 else ""
    f = parts[-1]
    stem, ext = os.path.splitext(f)
    suffix = ""
    if "_" in stem and not stem.startswith("{"):
        suffix = stem.replace("{unit_name}", "")
    return d, suffix, ext


def _is_stub_dep_file(
    rel_path: str,
    role_def: role_registry.RoleDefinition,
    repo_root: Optional[str] = None,
) -> bool:
    """Returns True if rel_path matches any role in stub_role_deps."""
    if not role_def.stub_role_deps:
        return False
    fname = os.path.basename(rel_path)
    if fname in ("__init__.py",):
        return False
    registry = get_singleton(role_registry.WorkspaceRegistry)
    root = repo_root or "."
    for stub_target in role_def.stub_role_deps:
        try:
            stub_def = registry.resolve_role_definition(stub_target, root)
        except (KeyError, ValueError, RuntimeError, OSError):
            continue
        parent = os.path.basename(os.path.dirname(rel_path))
        if stub_def.writable_file_patterns:
            for pat in stub_def.writable_file_patterns:
                if (
                    fnmatch.fnmatch(rel_path, pat)
                    or fnmatch.fnmatch(rel_path, f"*/{pat}")
                    or fnmatch.fnmatch(rel_path, f"*{pat}")
                    or fnmatch.fnmatch(fname, pat)
                ):
                    return True
        if stub_def.src_pattern:
            d, _, ext = _parse_pat_to_glob(stub_def.src_pattern)
            if d and (parent == d or f"/{d}/" in rel_path.replace("\\", "/")) and (not ext or fname.endswith(ext)):
                return True
    return False


def copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
    """Copies a file and applies exact permissions, delegating to WorkspaceProvisioner."""
    get_singleton(provision.WorkspaceProvisioner).copy_file_with_permissions(
        src, dst, readonly=readonly, executable=executable
    )


def _find_matching_files(root_dir: str, patterns: Sequence[str]) -> List[str]:
    """Finds relative file paths matching glob patterns within root_dir."""
    results: List[str] = []
    if not os.path.isdir(root_dir):
        return results
    for r, _, files in os.walk(root_dir):
        for f in files:
            full_path = os.path.join(r, f)
            rel_path = os.path.relpath(full_path, root_dir)
            if "support" in rel_path.split(os.sep)[:-1]:
                continue
            if any(
                fnmatch.fnmatch(rel_path, p)
                or fnmatch.fnmatch(rel_path, f"*/{p}")
                or fnmatch.fnmatch(rel_path, f"*{p}")
                or fnmatch.fnmatch(f, p)
                for p in patterns
            ):
                results.append(rel_path)
    return results


# Contract: Realizes sync.WorkspaceSynchronizer singleton.
class WorkspaceSynchronizer(sync.WorkspaceSynchronizer):
    """Realizes two-phase harvesting, inbound pulling, and blame flushing."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    # Contract: Pulls updated upstream contracts and source files into role workspace, enforcing 0o444 permissions.
    def pull(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
        delete_missing: bool = True,
    ) -> int:
        registry = get_singleton(
            role_registry.WorkspaceRegistry
        )
        role_def = registry.resolve_role_definition(role_name, main_root)

        main_scope_dir = os.path.join(main_root, dir_scope)
        ws_scope_dir = os.path.join(workspace_dir, dir_scope)
        if not os.path.isdir(main_scope_dir):
            return 0

        pulled_count = 0
        if role_def.stub_role_deps:
            provisioner = get_singleton(provision.WorkspaceProvisioner)
            pulled_count += provisioner.sync_test_stubs(
                workspace_dir=workspace_dir,
                role_name=role_name,
                dir_scope=dir_scope,
                repo_root=main_root,
            )

        all_patterns = list(role_def.writable_file_patterns) + list(
            role_def.readonly_file_patterns
        )
        main_files = _find_matching_files(main_scope_dir, all_patterns)
        main_files_set = set(main_files)

        pending_targets: set[str] = set()
        pending_candidates = app_info.get_pending_work_filenames()
        for cand_name in pending_candidates:
            pending_file = os.path.join(workspace_dir, cand_name)
            if os.path.isfile(pending_file):
                try:
                    with open(pending_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        pending_targets = set(data.get("targets", []))
                    elif isinstance(data, list):
                        pending_targets = set(data)
                except (OSError, json.JSONDecodeError):
                    pass
                break

        pull_manifest = _load_pull_manifest(workspace_dir)

        if delete_missing and os.path.isdir(ws_scope_dir):
            ws_files = _find_matching_files(ws_scope_dir, all_patterns)
            for rel in ws_files:
                if rel not in main_files_set:
                    dst_f = os.path.join(ws_scope_dir, rel)
                    rel_from_ws = os.path.relpath(dst_f, workspace_dir).replace("\\", "/")
                    is_pending = (
                        rel in pending_targets
                        or rel_from_ws in pending_targets
                        or any(pt.endswith(f"/{rel}") or rel.endswith(f"/{pt}") for pt in pending_targets)
                    )
                    if is_pending:
                        continue
                    try:
                        os.chmod(dst_f, 0o644)
                    except OSError:
                        pass
                    try:
                        os.remove(dst_f)
                        pull_manifest.pop(rel, None)
                    except OSError:
                        pass

            for r, _, files in os.walk(ws_scope_dir):
                if "__init__.py" in files:
                    init_ws = os.path.join(r, "__init__.py")
                    rel_init = os.path.relpath(init_ws, ws_scope_dir)
                    init_main = os.path.join(main_scope_dir, rel_init)
                    if not os.path.isfile(init_main):
                        try:
                            os.chmod(init_ws, 0o644)
                            os.remove(init_ws)
                        except OSError:
                            pass

        for rel in main_files:
            if _is_stub_dep_file(rel, role_def, main_root):
                continue
            src_f = os.path.join(main_scope_dir, rel)
            dst_f = os.path.join(ws_scope_dir, rel)
            is_writable = any(
                fnmatch.fnmatch(rel, p)
                or fnmatch.fnmatch(rel, f"*/{p}")
                or fnmatch.fnmatch(rel, f"*{p}")
                or fnmatch.fnmatch(os.path.basename(rel), p)
                for p in role_def.writable_file_patterns
            )

            current_src_hash = _compute_file_sha256(src_f)
            if current_src_hash is None:
                continue

            manifest_entry = pull_manifest.get(rel)
            needs_copy = False
            if not os.path.isfile(dst_f):
                rel_from_ws = os.path.relpath(dst_f, workspace_dir).replace("\\", "/")
                is_pending_target = (
                    rel in pending_targets
                    or rel_from_ws in pending_targets
                    or any(pt.endswith(f"/{rel}") or rel.endswith(f"/{pt}") for pt in pending_targets)
                )
                can_regenerate = bool(role_def and role_def.src_pattern and role_def.role_deps)
                if is_writable and is_pending_target and can_regenerate:
                    needs_copy = False
                else:
                    needs_copy = True
            else:
                current_ws_hash = _compute_file_sha256(dst_f)

                if manifest_entry is not None:
                    prev_src_hash = manifest_entry.get("main_hash")
                    src_changed_upstream = (prev_src_hash != current_src_hash)

                    if not src_changed_upstream:
                        # Canonical file has not changed since last pull. Never pull or clobber workspace file!
                        needs_copy = False
                    else:
                        # Canonical file changed upstream. Check whether subagent modified dst_f locally:
                        if is_writable:
                            local_code_mod = False
                            try:
                                local_code_mod = src_metadata.is_code_modified(dst_f)
                            except OSError:
                                local_code_mod = False

                            meta = src_metadata.extract_metadata(dst_f)
                            ws_base_code_h = meta.code_hash if meta else None
                            src_code_h = src_metadata.compute_file_code_hash(src_f)
                            upstream_code_changed = bool(
                                ws_base_code_h and src_code_h and src_code_h != ws_base_code_h
                            )

                            if local_code_mod and upstream_code_changed:
                                raise RuntimeError(
                                    f"Conflict detected during pull: upstream '{rel}' code was modified concurrently with local uncommitted edits."
                                )
                            elif local_code_mod:
                                # Upstream only modified metadata, local code has uncommitted edits: keep local edits
                                needs_copy = False
                                pull_manifest[rel] = {
                                    "main_hash": current_src_hash,
                                    "ws_hash": current_ws_hash or "",
                                }
                            else:
                                # Local code is clean: pull updated upstream version
                                needs_copy = True
                        else:
                            # Read-only upstream dependency or audited target changed in main: always pull updated version
                            needs_copy = True
                else:
                    # Unmanifested workspace (e.g. preexisting workspace or unit test baseline)
                    local_modified = False
                    if is_writable:
                        try:
                            local_modified = src_metadata.is_code_modified(dst_f)
                        except OSError:
                            local_modified = False

                    if local_modified:
                        # Preserving subagent edits: do NOT clobber! Record baseline so future pulls track changes from now on.
                        pull_manifest[rel] = {
                            "main_hash": current_src_hash,
                            "ws_hash": current_ws_hash or "",
                        }
                        needs_copy = False
                    else:
                        try:
                            with open(src_f, "r", encoding="utf-8") as sf, open(dst_f, "r", encoding="utf-8") as df:
                                src_content = sf.read()
                                dst_content = df.read()
                            src_projected = _project_for_role_workspace(src_content, os.path.basename(src_f), is_writable=is_writable)
                            if src_projected != dst_content:
                                needs_copy = True
                        except (UnicodeDecodeError, OSError):
                            try:
                                with open(src_f, "rb") as sf, open(dst_f, "rb") as df:
                                    if sf.read() != df.read():
                                        needs_copy = True
                            except OSError:
                                needs_copy = True

                        if not needs_copy:
                            pull_manifest[rel] = {
                                "main_hash": current_src_hash,
                                "ws_hash": current_ws_hash or "",
                            }

            if needs_copy:
                _copy_projected_file(src_f, dst_f, is_writable=is_writable)
                pulled_count += 1
                pull_manifest[rel] = {
                    "main_hash": current_src_hash,
                    "ws_hash": _compute_file_sha256(dst_f) or "",
                }
            else:
                if is_writable:
                    try:
                        st = os.stat(dst_f)
                        if not bool(st.st_mode & stat.S_IWUSR):
                            os.chmod(dst_f, 0o644)
                    except OSError:
                        pass

        _save_pull_manifest(workspace_dir, pull_manifest)
        return pulled_count

    # Contract: Refreshes non-parts system files into role workspace without altering writable targets.
    def refresh_system_files(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
        silent: bool = False,
    ) -> int:
        registry = get_singleton(
            role_registry.WorkspaceRegistry
        )
        # Resolve the canonical repository root and the role context of the
        # synchronized workspace before recopying system files from that root.
        canonical_root = registry.discover_repository_root(main_root)
        if not os.path.isdir(canonical_root):
            canonical_root = main_root
        descriptor: Optional[role_registry.WorkspaceDescriptor] = None
        target_ws = os.path.realpath(workspace_dir)
        for active in registry.load_active_workspaces(repo_root=canonical_root):
            if os.path.realpath(active.workspace_dir) == target_ws:
                descriptor = active
                break
        if descriptor is not None:
            role_name = descriptor.role_definition.role_name
            dir_scope = descriptor.directory_scope
            role_def = descriptor.role_definition
        else:
            role_def = registry.resolve_role_definition(role_name, canonical_root)
        main_root = canonical_root
        refreshed_count = 0

        active_pkg = _resolve_active_methodology_pkg(canonical_root, dir_scope, role_def)

        if role_def.guide_path:
            guide_candidates = [
                os.path.join(main_root, role_def.guide_path),
            ]
            if active_pkg:
                guide_candidates.append(os.path.join(main_root, active_pkg, role_def.guide_path))
                guide_candidates.append(os.path.join(main_root, active_pkg, "guides", os.path.basename(role_def.guide_path)))
            guide_src = next((c for c in guide_candidates if os.path.isfile(c)), None)
            if guide_src:
                root_guide_dst = os.path.join(workspace_dir, "guides", os.path.basename(role_def.guide_path))
                copy_file_with_perms(guide_src, root_guide_dst, readonly=True)
                refreshed_count += 1

        for cfg_name in (
            "pyproject.toml",
            "model_configs.toml",
            "uv.lock",
            ".python-version",
        ):
            cfg_src = os.path.join(main_root, cfg_name)
            if os.path.isfile(cfg_src):
                cfg_dst = os.path.join(workspace_dir, cfg_name)
                copy_file_with_perms(cfg_src, cfg_dst, readonly=False)
                refreshed_count += 1

        ws_pyproject = os.path.join(workspace_dir, "pyproject.toml")
        if os.path.isfile(ws_pyproject):
            try:
                with open(ws_pyproject, "r", encoding="utf-8") as f:
                    ptext = f.read()
                ptext = re.sub(
                    r'\[tool\.pyright\][^\[]*include\s*=\s*\[[^\]]*\]',
                    '[tool.pyright]\ninclude = ["."]',
                    ptext,
                    flags=re.DOTALL,
                )
                if dir_scope:
                    clean_scope = dir_scope.strip("/").split("/")[0]
                    ptext = ptext.replace(f'"{clean_scope}",', '').replace(f'"{clean_scope}"', '')
                    ptext = ptext.replace(f'"{dir_scope}",', '').replace(f'"{dir_scope}"', '')
                ptext = re.sub(
                    r'testpaths\s*=\s*\[[^\]]*\]',
                    'testpaths = ["."]',
                    ptext,
                )
                pypaths_cfg = ['"."']
                if dir_scope:
                    clean_scope = dir_scope.strip("/").split("/")[0]
                    pypaths_cfg.append(f'"{clean_scope}"')
                    pypaths_cfg.append(f'"{clean_scope}/parts"')
                pypaths_str = f'pythonpath = [{", ".join(pypaths_cfg)}]'
                if "pythonpath" in ptext:
                    ptext = re.sub(
                        r'pythonpath\s*=\s*\[[^\]]*\]',
                        pypaths_str,
                        ptext,
                    )
                elif "[tool.pytest.ini_options]" in ptext:
                    ptext = ptext.replace(
                        "[tool.pytest.ini_options]",
                        f'[tool.pytest.ini_options]\n{pypaths_str}',
                    )
                # Contract: MUST strip readme declaration attributes from refreshed pyproject.toml to prevent build backend failures.
                ptext = re.sub(r'(?m)^\s*readme\s*=.*$\n?', '', ptext)
                with open(ws_pyproject, "w", encoding="utf-8") as f:
                    f.write(ptext)
                try:
                    os.chmod(ws_pyproject, 0o444)
                except OSError:
                    pass
            except OSError:
                pass

        target_pkgs = [active_pkg] if active_pkg else []

        for entry in target_pkgs:
            pkg_dir = os.path.join(main_root, entry)
            if not os.path.isdir(pkg_dir):
                continue
            s_lib = os.path.join(pkg_dir, "support", "lib")
            if os.path.isdir(s_lib):
                d_support = os.path.join(workspace_dir, "support")
                d_lib = os.path.join(d_support, "lib")
                os.makedirs(d_lib, exist_ok=True)
                s_init = os.path.join(pkg_dir, "support", "__init__.py")
                if os.path.isfile(s_init):
                    copy_file_with_perms(s_init, os.path.join(d_support, "__init__.py"), readonly=True)
                lib_init = os.path.join(s_lib, "__init__.py")
                if os.path.isfile(lib_init):
                    copy_file_with_perms(lib_init, os.path.join(d_lib, "__init__.py"), readonly=True)
                for fname in os.listdir(s_lib):
                    sf = os.path.join(s_lib, fname)
                    if not os.path.isfile(sf):
                        continue
                    if _is_runtime_support_library(fname):
                        df = os.path.join(d_lib, fname)
                        if os.path.isfile(sf):
                            copy_file_with_perms(sf, df, readonly=True)
                            refreshed_count += 1

        bin_dir = os.path.join(workspace_dir, "bin")
        provisioner = get_singleton(provision.WorkspaceProvisioner)
        provisioner.deploy_runner_zipapps(bin_dir)
        provisioner.write_role_agents_guide(
            workspace_dir=workspace_dir,
            role_name=role_name,
            dir_scope=dir_scope,
            repo_root=canonical_root,
        )
        refreshed_count += 6

        meta_path = os.path.join(workspace_dir, ROLE_CONFIG_FILE)
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                meta_data.pop("main_workspace_root", None)
                meta_data.pop("repo_root", None)
                if not meta_data.get("role"):
                    meta_data["role"] = role_name
                if not meta_data.get("dir_scope"):
                    meta_data["dir_scope"] = dir_scope
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, indent=2)
                    f.write("\n")
                refreshed_count += 1
            except (OSError, json.JSONDecodeError):
                pass

        if role_def.stub_role_deps:
            refreshed_count += provisioner.sync_test_stubs(
                workspace_dir=workspace_dir,
                role_name=role_name,
                dir_scope=dir_scope,
                repo_root=canonical_root,
            )

        return refreshed_count

    # Contract: Flushes buffered blame feedback entries from workspace into main repository.
    def flush_blame_buffer(
        self, workspace_dir: str, main_root: str
    ) -> Sequence[str]:
        blame_candidates = app_info.get_blame_buffer_filenames()
        blame_path = None
        for cand_name in blame_candidates:
            cand_p = os.path.join(workspace_dir, cand_name)
            if os.path.isfile(cand_p):
                blame_path = cand_p
                break
        if not blame_path or not os.path.isfile(blame_path):
            return ()

        try:
            with open(blame_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (OSError, json.JSONDecodeError):
            return ()

        if not isinstance(entries, list) or not entries:
            return ()

        flushed: List[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            target = entry.get("target", "").lstrip("/")
            explanation = entry.get("explanation", "")
            blamed_by = entry.get("blamed_by", "role workspace")
            dirty_reason = entry.get("dirty_reason")

            target_path = os.path.join(main_root, target)

            if os.path.isfile(target_path):
                if dirty_reason:
                    src_metadata.mark_dirty(target_path, reason=dirty_reason)
                src_metadata.append_feedback(target_path, explanation, sender=blamed_by)
                flushed.append(target)

        try:
            os.remove(blame_path)
        except OSError:
            pass

        return flushed

    # Contract: Harvests modified targets, stamps audits, and flushes blame back to main.
    def harvest(
        self,
        workspace_dir: str,
        main_root: str,
        role_name: str,
        dir_scope: str,
    ) -> sync.SyncResult:
        registry = get_singleton(
            role_registry.WorkspaceRegistry
        )
        role_def = registry.resolve_role_definition(role_name, main_root)

        flushed_blames = list(self.flush_blame_buffer(workspace_dir, main_root))
        stamped_audits: List[str] = []
        harvested_count = 0

        audit_candidates = app_info.get_audit_buffer_filenames()
        audit_path = None
        for cand_name in audit_candidates:
            cand_p = os.path.join(workspace_dir, cand_name)
            if os.path.isfile(cand_p):
                audit_path = cand_p
                break
        if audit_path and os.path.isfile(audit_path):
            try:
                with open(audit_path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            t = entry.get("target", "").lstrip("/")
                            t_path = os.path.join(main_root, t)
                            if os.path.isfile(t_path):
                                tag = entry.get("audit_tag") or role_def.audit_tag or role_name
                                src_metadata.stamp_audit(t_path, tag)
                                stamped_audits.append(t)
                with open(audit_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                    f.write("\n")
            except (OSError, json.JSONDecodeError):
                pass

        ws_scope_dir = os.path.join(workspace_dir, dir_scope)
        main_scope_dir = os.path.join(main_root, dir_scope)

        if os.path.isdir(ws_scope_dir):
            writable_files = _find_matching_files(
                ws_scope_dir, role_def.writable_file_patterns
            )
            for rel in writable_files:
                ws_f = os.path.join(ws_scope_dir, rel)
                main_f = os.path.join(main_scope_dir, rel)

                is_modified = False
                if not os.path.isfile(main_f):
                    is_modified = True
                else:
                    is_modified = src_metadata.is_code_modified(ws_f)

                if is_modified:
                    ws_meta = src_metadata.extract_metadata(ws_f)
                    baseline_hash = ws_meta.code_hash if ws_meta else None
                    main_hash = (
                        src_metadata.compute_file_code_hash(main_f)
                        if os.path.isfile(main_f)
                        else None
                    )
                    # Contract: Postcondition - MUST validate canonical main target baselines against workspace baseline hashes before committing harvested files.
                    if baseline_hash and main_hash and baseline_hash != main_hash:
                        raise RuntimeError(
                            f"Conflict detected during harvest: canonical '{rel}' was modified concurrently with local uncommitted edits."
                        )
                    copy_file_with_perms(ws_f, main_f, readonly=False)
                    meta = src_metadata.extract_metadata(ws_f)
                    change = meta.change_summary if meta else "harvested changes"
                    src_metadata.record_change(main_f, change)
                    src_metadata.mark_clean(main_f)
                    src_metadata.update_metadata(main_f, clear_code_hash=True)
                    if role_def.audit_tag:
                        src_metadata.stamp_audit(main_f, role_def.audit_tag)
                        stamped_audits.append(rel)
                    _copy_projected_file(main_f, ws_f, is_writable=True)
                    harvested_count += 1

            if harvested_count > 0:
                pull_manifest = _load_pull_manifest(workspace_dir)
                for rel in writable_files:
                    ws_f = os.path.join(ws_scope_dir, rel)
                    main_f = os.path.join(main_scope_dir, rel)
                    if os.path.isfile(main_f) and os.path.isfile(ws_f):
                        mh = _compute_file_sha256(main_f)
                        wh = _compute_file_sha256(ws_f)
                        if mh and wh:
                            pull_manifest[rel] = {"main_hash": mh, "ws_hash": wh}
                _save_pull_manifest(workspace_dir, pull_manifest)

        return sync.SyncResult(
            pulled_files=0,
            harvested_files=harvested_count,
            stamped_audits=stamped_audits,
            flushed_blames=flushed_blames,
        )
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-06T20:48:04Z
# LAST_CHANGED: 2026-11-06T20:48:04Z
# CHANGE: Always overwrite read-only upstream files on pull when canonical version changes in main
# COVERAGE_AUDIT: 2026-11-06T20:48:05Z
# QA_AUDIT: 2026-11-06T20:48:05Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceSynchronizer,
        keys=[sync.WorkspaceSynchronizer, WorkspaceSynchronizer],
        tier=agent_session.agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
