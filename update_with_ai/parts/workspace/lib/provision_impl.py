"""Low-level implementation for provision_impl."""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from typing import List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.metadata.lib import src_metadata
from . import provision, role_registry, roles, scaffold, stub


def _find_methodology_for_scope(root: str, dir_scope: str) -> Optional[str]:
    """Finds methodology binding from cleanroom.toml within dir_scope or upward."""
    if not dir_scope:
        return None
    scope_dir = os.path.join(root, dir_scope)
    root_abs = os.path.abspath(root)

    import tomllib
    cand = os.path.join(scope_dir, "cleanroom.toml")
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
                    sub_cand = os.path.join(sub, "cleanroom.toml")
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
        cand = os.path.join(curr, "cleanroom.toml")
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
    role_def: Optional[roles.RoleDefinition] = None,
) -> Optional[str]:
    """Dynamically resolves the active methodology package directory name without hardcoding."""
    meth = _find_methodology_for_scope(resolved_root, dir_scope)
    if meth:
        clean = meth.lstrip("./").lstrip("/")
        if os.path.isdir(os.path.join(resolved_root, clean)):
            return clean

    if role_def and role_def.guide_path:
        for seg in role_def.guide_path.replace("\\", "/").split("/"):
            if seg and seg != "guides" and os.path.isdir(os.path.join(resolved_root, seg)):
                return seg
            if seg == "guides":
                break

    if role_def and role_def.template:
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
        projected = _project_for_role_workspace(content, os.path.basename(src), is_writable=is_writable)
        _write_file_with_perms(dst, projected, readonly=not is_writable)
    except (UnicodeDecodeError, OSError):
        copy_file_with_perms(src, dst, readonly=not is_writable)


BLAME_BUFFER_FILE = ".cleanroom_blame_buffer.json"
PENDING_WORK_FILE = ".cleanroom_pending_work.json"


def _is_runtime_support_library(fname: str) -> bool:
    """Returns True if file is a user-facing runtime API or type stub, excluding internal oracles."""
    base = fname.lower()
    if "lint" in base or "tool" in base or "runner" in base or base.startswith("app_info"):
        return False
    return fname.endswith((".py", ".pyi", ".bzl", ".toml"))


def _write_file_with_perms(
    path: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    """Writes a file with specific content and permissions."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    mode = 0o444 if readonly else 0o644
    if executable:
        mode |= 0o111
    try:
        os.chmod(path, mode)
    except OSError:
        pass


write_file_with_perms = _write_file_with_perms


def copy_file_with_perms(
    src: str, dst: str, readonly: bool = False, executable: bool = False
) -> None:
    """Copies a file and applies exact read-only or read-write permissions."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o644)
        except OSError:
            pass
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while chunk := fsrc.read(1024 * 1024):
            fdst.write(chunk)
    shutil.copystat(src, dst)
    if executable:
        mode = 0o555 if readonly else 0o755
    else:
        mode = 0o444 if readonly else 0o644
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


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


class WorkspaceProvisioner(provision.WorkspaceProvisioner):
    """Realizes role workspace directory provisioning, permissions, and runner deployment."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    # Contract: Copies a file and applies exact read-only, writable, or executable permissions.
    def copy_file_with_permissions(
        self,
        src: str,
        dst: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        copy_file_with_perms(src, dst, readonly=readonly, executable=executable)

    # Contract: Writes text content to a destination file and applies exact permissions.
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        scaffolder = get_singleton(scaffold.WorkspaceScaffolder)
        scaffolder.write_file_with_permissions(
            dst, content, readonly=readonly, executable=executable
        )

    # Contract: Packages executable runner tools into the specified bin directory.
    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        scaffolder = get_singleton(scaffold.WorkspaceScaffolder)
        scaffolder.deploy_runner_zipapps(bin_dir)

    # Contract: Synthesizes role-tailored AGENTS.md instructions in the workspace root.
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> None:
        registry = get_singleton(role_registry.WorkspaceRegistry)
        root = registry.discover_repository_root(repo_root)
        role_def = registry.resolve_role_definition(
            role_name, root, dir_scope=dir_scope
        )
        scaffolder = get_singleton(scaffold.WorkspaceScaffolder)
        scaffolder.write_role_agents_guide(workspace_dir, role_def, dir_scope)

    # Contract: Synchronizes read-only test stubs for stub role dependencies.
    def sync_test_stubs(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
    ) -> int:
        registry = get_singleton(role_registry.WorkspaceRegistry)
        root = registry.discover_repository_root(repo_root)
        role_def = registry.resolve_role_definition(
            role_name, root, dir_scope=dir_scope
        )
        stub_synth = get_singleton(stub.WorkspaceStubSynthesizer)
        return stub_synth.sync_all_stub_deps(
            workspace_dir=workspace_dir,
            main_root=root,
            role_def=role_def,
            dir_scope=dir_scope,
        )

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> role_registry.WorkspaceDescriptor:
        registry = get_singleton(
            role_registry.WorkspaceRegistry
        )
        resolved_root = registry.discover_repository_root(repo_root)
        role_def = registry.resolve_role_definition(
            role_name, resolved_root, dir_scope=dir_scope
        )
        workspace_dir = registry.compute_workspace_dir(
            role_name, dir_scope, resolved_root, custom_dest
        )

        if reset and os.path.isdir(workspace_dir):
            for stale_f in (
                PENDING_WORK_FILE,
                ".cleanroom_pending_work",
                BLAME_BUFFER_FILE,
                ".cleanroom_blame_buffer.json",
            ):
                sp = os.path.join(workspace_dir, stale_f)
                if os.path.isfile(sp):
                    try:
                        os.remove(sp)
                    except OSError:
                        pass
            try:
                for fname in os.listdir(workspace_dir):
                    if fname.startswith((".cleanroom_turn_", ".dsh_prompt_")):
                        fp = os.path.join(workspace_dir, fname)
                        if os.path.isfile(fp):
                            os.remove(fp)
            except OSError:
                pass
            cleanroom_dir = os.path.join(workspace_dir, ".cleanroom")
            if os.path.isdir(cleanroom_dir):
                dsh_sess = os.path.join(cleanroom_dir, "dsh_session_id.txt")
                if os.path.isfile(dsh_sess):
                    try:
                        os.remove(dsh_sess)
                    except OSError:
                        pass

        os.makedirs(workspace_dir, exist_ok=True)
        bin_dir = os.path.join(workspace_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)

        scaffolder = get_singleton(scaffold.WorkspaceScaffolder)

        scope_dir = os.path.join(resolved_root, dir_scope)
        if os.path.isdir(scope_dir):
            for dirpath, _, filenames in os.walk(scope_dir):
                rel_d = os.path.relpath(dirpath, scope_dir)
                ws_d = (
                    os.path.join(workspace_dir, dir_scope, rel_d)
                    if rel_d != "."
                    else os.path.join(workspace_dir, dir_scope)
                )
                os.makedirs(ws_d, exist_ok=True)
            stub_synth = get_singleton(stub.WorkspaceStubSynthesizer)
            writable_rel = _find_matching_files(
                scope_dir, role_def.writable_file_patterns
            )
            for rel in writable_rel:
                if stub_synth.is_stub_dep_file(rel, role_def, resolved_root):
                    continue
                src_f = os.path.join(scope_dir, rel)
                dst_f = os.path.join(workspace_dir, dir_scope, rel)
                _copy_projected_file(src_f, dst_f, is_writable=True)

            readonly_rel = _find_matching_files(
                scope_dir, role_def.readonly_file_patterns
            )
            for rel in readonly_rel:
                if stub_synth.is_stub_dep_file(rel, role_def, resolved_root):
                    continue
                src_f = os.path.join(scope_dir, rel)
                dst_f = os.path.join(workspace_dir, dir_scope, rel)
                _copy_projected_file(src_f, dst_f, is_writable=False)

            if role_def.stub_role_deps:
                stub_synth.sync_all_stub_deps(
                    workspace_dir=workspace_dir,
                    main_root=resolved_root,
                    role_def=role_def,
                    dir_scope=dir_scope,
                )

            scaffolder.create_missing_target_skeletons(
                workspace_dir=workspace_dir,
                repo_root=resolved_root,
                dir_scope=dir_scope,
                role_def=role_def,
            )

        active_pkg = _resolve_active_methodology_pkg(resolved_root, dir_scope, role_def)

        if role_def.guide_path:
            guide_candidates = [
                os.path.join(resolved_root, role_def.guide_path),
            ]
            if active_pkg:
                guide_candidates.append(os.path.join(resolved_root, active_pkg, role_def.guide_path))
                guide_candidates.append(os.path.join(resolved_root, active_pkg, "guides", os.path.basename(role_def.guide_path)))
            guide_src = next((c for c in guide_candidates if os.path.isfile(c)), None)
            if guide_src:
                root_guide_dst = os.path.join(workspace_dir, "guides", os.path.basename(role_def.guide_path))
                copy_file_with_perms(guide_src, root_guide_dst, readonly=True)

        for cfg_name in (
            "pyproject.toml",
            "model_configs.toml",
            "uv.lock",
            ".python-version",
        ):
            cfg_src = os.path.join(resolved_root, cfg_name)
            if os.path.isfile(cfg_src):
                cfg_dst = os.path.join(workspace_dir, cfg_name)
                copy_file_with_perms(cfg_src, cfg_dst, readonly=False)

        ws_pyproject = os.path.join(workspace_dir, "pyproject.toml")
        if os.path.isfile(ws_pyproject):
            try:
                with open(ws_pyproject, "r", encoding="utf-8") as f:
                    ptext = f.read()
                # Contract: MUST configure type-checking to cover the workspace without directory exclusions.
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
                if "pythonpath" in ptext:
                    ptext = re.sub(
                        r'pythonpath\s*=\s*\[[^\]]*\]',
                        'pythonpath = ["."]',
                        ptext,
                    )
                elif "[tool.pytest.ini_options]" in ptext:
                    ptext = ptext.replace(
                        "[tool.pytest.ini_options]",
                        '[tool.pytest.ini_options]\npythonpath = ["."]',
                    )
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
            pkg_dir = os.path.join(resolved_root, entry)
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
                        copy_file_with_perms(sf, df, readonly=True)

        scaffolder.deploy_runner_zipapps(bin_dir, role_def=role_def)

        resolved_batch_size: Optional[int] = None
        resolved_max_feedback_chars: Optional[int] = None
        resolved_model_name: Optional[str] = model
        if model:
            m_cfg_file = os.path.join(resolved_root, "model_configs.toml")
            if os.path.isfile(m_cfg_file):
                try:
                    import tomllib
                    with open(m_cfg_file, "rb") as mf:
                        m_data = tomllib.load(mf)
                    models_sec = m_data.get("models", {})
                    clean_model = model.strip()
                    for prefix in ("dsh ", "antigravity ", "models."):
                        if clean_model.startswith(prefix):
                            clean_model = clean_model[len(prefix):].strip()
                    target_cfg = None
                    if clean_model in models_sec:
                        target_cfg = models_sec[clean_model]
                    else:
                        for k, v in models_sec.items():
                            if isinstance(v, dict) and (v.get("model") == clean_model or k == clean_model):
                                target_cfg = v
                                break
                    if target_cfg:
                        resolved_batch_size = target_cfg.get("subagent_batch_size") or target_cfg.get("batch_size")
                        resolved_max_feedback_chars = target_cfg.get("max_feedback_chars")
                        resolved_model_name = clean_model
                except Exception:
                    pass

        scaffolder.write_role_metadata(
            workspace_dir,
            role_def.role_name,
            dir_scope,
            resolved_root,
            model=resolved_model_name,
            batch_size=resolved_batch_size,
            max_feedback_chars=resolved_max_feedback_chars,
        )
        scaffolder.write_role_agents_guide(workspace_dir, role_def, dir_scope)

        descriptor = role_registry.WorkspaceDescriptor(
            workspace_dir=workspace_dir,
            main_repository_root=resolved_root,
            directory_scope=dir_scope,
            role_definition=role_def,
        )
        registry.record_workspace(descriptor, resolved_root)
        return descriptor
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-20T23:45:00Z
# LAST_CHANGED: 2026-10-20T23:45:00Z
# CHANGE: Promote active methodology runtime support, guides, templates, and configurations to role workspace root
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceProvisioner,
        keys=[WorkspaceProvisioner, provision.WorkspaceProvisioner],
        tier=WorkspaceProvisioner.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
