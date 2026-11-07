"""Low-level implementation for scaffold_impl."""

from __future__ import annotations

import fnmatch
import json
import os
import sys
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from autofab.parts.agent.lib import session as agent_session
from . import roles, scaffold


try:
    from support.lib import app_info
    ROLE_CONFIG_FILE = app_info.DEFAULT_ROLE_DESCRIPTOR
except Exception:
    import app_info  # type: ignore
    ROLE_CONFIG_FILE = getattr(app_info, "DEFAULT_ROLE_DESCRIPTOR", ".autofab_role.json")


def write_file_with_perms(
    dst: str, content: str, readonly: bool = False, executable: bool = False
) -> None:
    """Writes a text file and sets exact permissions, handling existing read-only files cleanly."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o644)
        except OSError:
            pass
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
    if executable:
        mode = 0o555 if readonly else 0o755
    else:
        mode = 0o444 if readonly else 0o644
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def _matches_any_pattern(rel_path: str, patterns: Sequence[str]) -> bool:
    """Reports whether a relative path matches any configured glob pattern."""
    normalized = rel_path.replace("\\", "/")
    fname = os.path.basename(normalized)
    return any(
        fnmatch.fnmatch(normalized, p)
        or fnmatch.fnmatch(normalized, f"*/{p}")
        or fnmatch.fnmatch(normalized, f"*{p}")
        or fnmatch.fnmatch(fname, p)
        for p in patterns
    )


def _declared_units(repo_root: str, scope_dir: str) -> List[Tuple[str, str]]:
    """Returns declared (unit_dir, unit_name) pairs beneath a synchronized scope."""
    units: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    part_dirs: List[str] = []
    parts_dir = os.path.join(scope_dir, "parts")
    if os.path.isdir(parts_dir):
        part_dirs = [
            os.path.join(parts_dir, name)
            for name in sorted(os.listdir(parts_dir))
            if os.path.isdir(os.path.join(parts_dir, name)) and not name.startswith(".")
        ]
    elif os.path.isdir(scope_dir):
        part_dirs = [
            os.path.join(scope_dir, name)
            for name in sorted(os.listdir(scope_dir))
            if os.path.isdir(os.path.join(scope_dir, name)) and not name.startswith(".")
        ]
    for part_dir in part_dirs:
        rel_part = os.path.relpath(part_dir, repo_root).replace("\\", "/")
        stems: Set[str] = set()
        try:
            for sub in sorted(os.listdir(part_dir)):
                sub_dir = os.path.join(part_dir, sub)
                if not os.path.isdir(sub_dir) or sub.startswith((".", "venv", "bazel-", "__pycache__")) or sub in ("tests", "pretense", "ext"):
                    continue
                try:
                    for fname in os.listdir(sub_dir):
                        if fname.startswith(".") or fname == "__init__.py":
                            continue
                        if not fname.endswith((".pyi", ".py", ".md")):
                            continue
                        stem = os.path.splitext(fname)[0]
                        if stem and stem != "__init__" and not stem.endswith(("_ext", "_test", "_pretense")):
                            stems.add(stem)
                except OSError:
                    pass
        except OSError:
            pass
        for stem in sorted(stems):
            key = (rel_part, stem)
            if key not in seen:
                seen.add(key)
                units.append(key)
    return units


def _missing_target_skeleton(
    repo_root: str,
    rel_path: str,
    unit_dir: str,
    unit_name: str,
    role_def: roles.RoleDefinition,
    workspace_dir: Optional[str] = None,
) -> Optional[str]:
    """Synthesizes starter skeleton content for a declared writable target file."""
    if role_def.template:
        template_candidates: List[str] = []
        if workspace_dir:
            template_candidates.append(os.path.join(workspace_dir, role_def.template))
            template_candidates.append(
                os.path.join(workspace_dir, "templates", os.path.basename(role_def.template))
            )
        template_candidates.append(os.path.join(repo_root, role_def.template))
        template_candidates.append(
            os.path.join(repo_root, "templates", os.path.basename(role_def.template))
        )
        for tcand in template_candidates:
            if os.path.isfile(tcand):
                try:
                    with open(tcand, "r", encoding="utf-8") as f:
                        return f.read()
                except (OSError, UnicodeDecodeError):
                    pass
    return None


def _create_missing_target_skeletons(
    workspace_dir: str,
    repo_root: str,
    dir_scope: str,
    role_def: roles.RoleDefinition,
) -> List[str]:
    """Creates a missing target skeleton for every declared writable target file absent from disk."""
    created: List[str] = []
    if not role_def.src_pattern or not role_def.writable_file_patterns:
        return created
    scope_dir = os.path.join(repo_root, dir_scope) if dir_scope else repo_root
    for unit_dir, unit_name in _declared_units(repo_root, scope_dir):
        if role_def.active_component_types:
            ctype = "implementation" if unit_name.endswith("_impl") else "interface"
            if ctype not in role_def.active_component_types:
                continue
        rel_path = role_def.src_pattern.format(unit_dir=unit_dir, unit_name=unit_name)
        if not _matches_any_pattern(rel_path, role_def.writable_file_patterns):
            continue
        if os.path.isfile(os.path.join(workspace_dir, rel_path)) or os.path.isfile(
            os.path.join(repo_root, rel_path)
        ):
            continue
        dst_path = os.path.join(workspace_dir, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        if role_def.template_command:
            try:
                import subprocess
                cmd = role_def.template_command.format(
                    target_file=dst_path,
                    unit_dir=unit_dir,
                    unit_name=unit_name,
                )
                env = dict(os.environ)
                env["UV_PROJECT"] = os.path.abspath(repo_root)
                res = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=repo_root,
                    env=env,
                    capture_output=True,
                    timeout=30,
                )
                if res.returncode == 0 and os.path.isfile(dst_path) and os.path.getsize(dst_path) > 0:
                    created.append(rel_path)
                    if rel_path.endswith(".py"):
                        curr_p = os.path.dirname(dst_path)
                        ws_root_clean = os.path.abspath(workspace_dir)
                        while curr_p and curr_p != ws_root_clean and curr_p.startswith(ws_root_clean):
                            p_init = os.path.join(curr_p, "__init__.py")
                            if not os.path.isfile(p_init):
                                write_file_with_perms(p_init, "", readonly=False)
                            curr_p = os.path.dirname(curr_p)
                    continue
                elif res.returncode != 0:
                    err_msg = res.stderr.decode("utf-8", errors="replace").strip()
                    sys.stderr.write(f"Warning: template_command failed for {rel_path}: {err_msg}\n")
            except Exception as e:
                sys.stderr.write(f"Warning: template_command execution error for {rel_path}: {e}\n")
        skeleton = _missing_target_skeleton(
            repo_root, rel_path, unit_dir, unit_name, role_def, workspace_dir=workspace_dir
        )
        if skeleton is None:
            continue
        write_file_with_perms(dst_path, skeleton, readonly=False)
        created.append(rel_path)
        if rel_path.endswith(".py"):
            curr_p = os.path.dirname(dst_path)
            ws_root_clean = os.path.abspath(workspace_dir)
            while curr_p and curr_p != ws_root_clean and curr_p.startswith(ws_root_clean):
                p_init = os.path.join(curr_p, "__init__.py")
                if not os.path.isfile(p_init):
                    write_file_with_perms(p_init, "", readonly=False)
                curr_p = os.path.dirname(curr_p)
    return created


def _collect_and_compile_runner_pycs(bin_dir: str) -> dict[str, bytes]:
    """Compiles support modules to optimized .pyc bytecode for runner zipapps."""
    pycs: dict[str, bytes] = {}
    support_dirs: list[str] = []

    repo_root = os.environ.get("AUTOFAB_MAIN_ROOT")
    if not repo_root or not os.path.isdir(repo_root):
        ws_dir = os.path.dirname(bin_dir)
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) in app_info.get_role_workspaces_containers():
            p_root = os.path.dirname(parent)
            try:
                for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                    if entry not in app_info.get_role_workspaces_containers():
                        cand = os.path.join(p_root, entry)
                        if os.path.isdir(cand) and (
                            os.path.exists(os.path.join(cand, ".git"))
                            or any(
                                os.path.exists(os.path.join(cand, m))
                                for m in (*app_info.get_config_filenames(), *app_info.get_roles_filenames(), "pyproject.toml")
                            )
                        ):
                            repo_root = cand
                            break
            except OSError:
                pass
    if not repo_root or not os.path.isdir(repo_root):
        try:
            cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
            cfg_markers = app_info.get_config_filenames() + ("pyproject.toml",)
            if os.path.isdir(cand) and any(os.path.isfile(os.path.join(cand, m)) for m in cfg_markers):
                repo_root = cand
        except Exception:
            pass

    if repo_root and os.path.isdir(repo_root):
        try:
            for sub in os.listdir(repo_root):
                sl = os.path.join(repo_root, sub, "support", "lib")
                if os.path.isdir(sl) and sl not in support_dirs:
                    support_dirs.append(sl)
        except OSError:
            pass

    # From sys.path
    for p in sys.path:
        if p and os.path.isdir(p):
            try:
                for entry in os.listdir(p):
                    sl = os.path.join(p, entry, "support", "lib")
                    if os.path.isdir(sl) and sl not in support_dirs:
                        support_dirs.append(sl)
            except OSError:
                pass

    import py_compile
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        empty_init = os.path.join(td, "empty__init__.py")
        with open(empty_init, "w") as f:
            f.write("")
        empty_pyc = os.path.join(td, "empty__init__.pyc")
        py_compile.compile(empty_init, empty_pyc, optimize=2)
        with open(empty_pyc, "rb") as f:
            empty_init_bytes = f.read()

        pycs["support/__init__.pyc"] = empty_init_bytes
        pycs["support/__init__.py"] = b""
        pycs["support/lib/__init__.pyc"] = empty_init_bytes
        pycs["support/lib/__init__.py"] = b""
        for sdir in support_dirs:
            try:
                pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(sdir)))
                pkg_name = os.path.basename(pkg_dir)
                if pkg_name:
                    pycs[f"{pkg_name}/__init__.pyc"] = empty_init_bytes
                    pycs[f"{pkg_name}/__init__.py"] = b""
                    pycs[f"{pkg_name}/support/__init__.pyc"] = empty_init_bytes
                    pycs[f"{pkg_name}/support/__init__.py"] = b""
                    pycs[f"{pkg_name}/support/lib/__init__.pyc"] = empty_init_bytes
                    pycs[f"{pkg_name}/support/lib/__init__.py"] = b""
                    if os.path.isdir(os.path.join(pkg_dir, "parts")):
                        pycs[f"{pkg_name}/parts/__init__.pyc"] = empty_init_bytes
                        pycs[f"{pkg_name}/parts/__init__.py"] = b""

                for fname in os.listdir(sdir):
                    if fname.endswith(".py"):
                        mod_name = fname[:-3]
                        arcname_pyc = f"{mod_name}.pyc"
                        arcname_py = f"{mod_name}.py"
                        src_path = os.path.join(sdir, fname)
                        dst_pyc = os.path.join(td, f"{mod_name}_{len(pycs)}.pyc")
                        try:
                            py_compile.compile(src_path, dst_pyc, optimize=2, doraise=True)
                            with open(dst_pyc, "rb") as pf:
                                pyc_bytes = pf.read()
                            is_lifecycle = (fname == "lifecycle.py")
                            is_canonical_lifecycle = is_lifecycle and os.path.getsize(src_path) > 1000
                            if not is_lifecycle or is_canonical_lifecycle or arcname_py not in pycs:
                                try:
                                    with open(src_path, "rb") as sf:
                                        src_bytes = sf.read()
                                        pycs[arcname_py] = src_bytes
                                        pycs[f"support/lib/{arcname_py}"] = src_bytes
                                        if pkg_name:
                                            pycs[f"{pkg_name}/support/lib/{arcname_py}"] = src_bytes
                                except Exception:
                                    pass
                            if not is_lifecycle or is_canonical_lifecycle or arcname_pyc not in pycs:
                                pycs[arcname_pyc] = pyc_bytes
                                pycs[f"support/lib/{arcname_pyc}"] = pyc_bytes
                            if pkg_name:
                                pycs[f"{pkg_name}/support/lib/{arcname_pyc}"] = pyc_bytes
                        except Exception:
                            pass
            except OSError:
                pass

        # Collect and compile all autofab library modules
        try:
            if repo_root and os.path.isdir(repo_root):
                for p_dir in ("autofab", "autofab"):
                    parts_root = os.path.join(repo_root, p_dir, "parts")
                    if os.path.isdir(parts_root):
                        for root, _, files in os.walk(parts_root):
                            if "/lib" in root or root.endswith("/lib"):
                                rel_long = os.path.relpath(root, repo_root).replace(os.sep, "/")
                                rel_short = os.path.relpath(root, os.path.join(repo_root, p_dir)).replace(os.sep, "/")
                                long_segs = rel_long.split("/")
                                for i in range(1, len(long_segs)):
                                    k = "/".join(long_segs[:i]) + "/__init__.pyc"
                                    if k not in pycs:
                                        pycs[k] = empty_init_bytes
                                    k_py = "/".join(long_segs[:i]) + "/__init__.py"
                                    if k_py not in pycs:
                                        pycs[k_py] = b""
                                short_segs = rel_short.split("/")
                                for i in range(1, len(short_segs)):
                                    k = "/".join(short_segs[:i]) + "/__init__.pyc"
                                    if k not in pycs:
                                        pycs[k] = empty_init_bytes
                                    k_py = "/".join(short_segs[:i]) + "/__init__.py"
                                    if k_py not in pycs:
                                        pycs[k_py] = b""

                                for f in files:
                                    if f.endswith(".py"):
                                        src = os.path.join(root, f)
                                        dst_pyc = os.path.join(td, f"part_mod_{len(pycs)}.pyc")
                                        try:
                                            py_compile.compile(src, dst_pyc, optimize=2, doraise=True)
                                            with open(dst_pyc, "rb") as pf:
                                                pyc_data = pf.read()
                                                pycs[f"{rel_long}/{f}c"] = pyc_data
                                                pycs[f"{rel_short}/{f}c"] = pyc_data
                                            with open(src, "rb") as sf:
                                                py_data = sf.read()
                                                pycs[f"{rel_long}/{f}"] = py_data
                                                pycs[f"{rel_short}/{f}"] = py_data
                                        except Exception:
                                            pass
        except Exception:
            pass
    return pycs


def _find_roles_toml_content(bin_dir: str) -> Optional[bytes]:
    """Locates and reads canonical role definitions configuration content for bundling into runner zipapps."""
    repo_root = os.environ.get("AUTOFAB_MAIN_ROOT")
    if not repo_root or not os.path.isdir(repo_root):
        ws_dir = os.path.dirname(bin_dir)
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) in app_info.get_role_workspaces_containers():
            p_root = os.path.dirname(parent)
            try:
                for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                    if entry not in app_info.get_role_workspaces_containers():
                        cand = os.path.join(p_root, entry)
                        if os.path.isdir(cand) and (
                            os.path.exists(os.path.join(cand, ".git"))
                            or any(
                                os.path.exists(os.path.join(cand, m))
                                for m in (*app_info.get_config_filenames(), *app_info.get_roles_filenames(), "pyproject.toml")
                            )
                        ):
                            repo_root = cand
                            break
            except OSError:
                pass
    if not repo_root or not os.path.isdir(repo_root):
        try:
            cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
            cfg_markers = app_info.get_config_filenames() + ("pyproject.toml",)
            if os.path.isdir(cand) and any(os.path.isfile(os.path.join(cand, m)) for m in cfg_markers):
                repo_root = cand
        except Exception:
            pass

    if repo_root and os.path.isdir(repo_root):
        for fname in app_info.get_roles_filenames():
            cand = os.path.join(repo_root, fname)
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        return f.read()
                except OSError:
                    pass
        try:
            for sub in os.listdir(repo_root):
                for fname in app_info.get_roles_filenames():
                    cand = os.path.join(repo_root, sub, fname)
                    if os.path.isfile(cand):
                        try:
                            with open(cand, "rb") as f:
                                return f.read()
                        except OSError:
                            pass
        except OSError:
            pass

    for p in sys.path:
        if p and os.path.isdir(p):
            for fname in app_info.get_roles_filenames():
                cand = os.path.join(p, fname)
                if os.path.isfile(cand):
                    try:
                        with open(cand, "rb") as f:
                            return f.read()
                    except OSError:
                        pass
            try:
                for sub in os.listdir(p):
                    for fname in app_info.get_roles_filenames():
                        cand = os.path.join(p, sub, fname)
                        if os.path.isfile(cand):
                            try:
                                with open(cand, "rb") as f:
                                    return f.read()
                            except OSError:
                                pass
            except OSError:
                pass

    for fname in app_info.get_roles_filenames():
        for pkg in ("autofab_py", "autofab_python", "autofab", "support"):
            try:
                import importlib.resources
                data = importlib.resources.files(pkg).joinpath(fname).read_bytes()
                if data:
                    return data
            except Exception:
                pass

    return None


def package_runner_zipapps(
    bin_dir: str,
    can_blame: bool = True,
    role_def: Optional[roles.RoleDefinition] = None,
) -> None:
    """Packages runner zipapps into bin_dir with executable permissions."""
    os.makedirs(bin_dir, exist_ok=True)
    tools = {
        "get_work": "get_work",
        "check_files": "check_files",
        "submit": "submit",
        "fail": "fail",
        "revert": "revert",
        "checkpoint": "checkpoint",
    }
    if can_blame:
        tools["blame"] = "blame"
        tools["feedback"] = "blame"
    else:
        for b_name in ("blame", "feedback"):
            bp = os.path.join(bin_dir, b_name)
            if os.path.isfile(bp):
                try:
                    os.remove(bp)
                except OSError:
                    pass

    is_auditor = bool(role_def and (not role_def.writable_file_patterns or role_def.audit_tag))
    if is_auditor:
        tools.pop("revert", None)
        tools.pop("checkpoint", None)
        for r_name in ("revert", "checkpoint"):
            rp = os.path.join(bin_dir, r_name)
            if os.path.isfile(rp):
                try:
                    os.remove(rp)
                except OSError:
                    pass

    if role_def and role_def.fused_roles:
        for cr in role_def.fused_roles:
            tools[f"verify_{cr}"] = f"verify_{cr}"

    cov_path = os.path.join(bin_dir, "coverage")
    # Contract: Removes stale coverage script if present in bin_dir.
    if os.path.isfile(cov_path):
        try:
            os.remove(cov_path)
        except OSError:
            pass

    pycs = _collect_and_compile_runner_pycs(bin_dir)
    roles_toml_bytes = _find_roles_toml_content(bin_dir)

    pkg_repo_root = os.environ.get("AUTOFAB_MAIN_ROOT")
    if not pkg_repo_root or not os.path.isdir(pkg_repo_root):
        ws_d = os.path.dirname(bin_dir)
        p_dir = os.path.dirname(ws_d)
        if os.path.basename(p_dir) in app_info.get_role_workspaces_containers():
            p_r = os.path.dirname(p_dir)
            try:
                for entry in sorted(os.listdir(p_r), key=len, reverse=True):
                    if entry not in app_info.get_role_workspaces_containers():
                        cand = os.path.join(p_r, entry)
                        if os.path.isdir(cand) and (
                            os.path.exists(os.path.join(cand, ".git"))
                            or any(
                                os.path.exists(os.path.join(cand, m))
                                for m in (*app_info.get_config_filenames(), *app_info.get_roles_filenames(), "pyproject.toml")
                            )
                        ):
                            pkg_repo_root = cand
                            break
            except OSError:
                pass
    if not pkg_repo_root or not os.path.isdir(pkg_repo_root):
        try:
            cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
            cfg_markers = app_info.get_config_filenames() + ("pyproject.toml",)
            if os.path.isdir(cand) and any(os.path.isfile(os.path.join(cand, m)) for m in cfg_markers):
                pkg_repo_root = cand
        except Exception:
            pass

    for tool_name, cmd in tools.items():
        tool_path = os.path.join(bin_dir, tool_name)
        runner_code = f'''import json
import os
import sys

curr = os.getcwd()
main_root = None
ws_dir = curr
while ws_dir and ws_dir != os.path.dirname(ws_dir):
    cfg = os.path.join(ws_dir, "{ROLE_CONFIG_FILE}")
    if os.path.isfile(cfg):
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) in {repr(app_info.get_role_workspaces_containers())}:
            p_root = os.path.dirname(parent)
            for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                if entry not in {repr(app_info.get_role_workspaces_containers())}:
                    cand = os.path.join(p_root, entry)
                    if os.path.isdir(cand) and (
                        os.path.exists(os.path.join(cand, ".git"))
                        or any(
                            os.path.exists(os.path.join(cand, m))
                            for m in {repr((*app_info.get_config_filenames(), *app_info.get_roles_filenames(), "pyproject.toml"))}
                        )
                    ):
                        main_root = cand
                        break
        break
    ws_dir = os.path.dirname(ws_dir)

embedded_main = {repr(os.path.abspath(pkg_repo_root) if pkg_repo_root else "")}
if not main_root and embedded_main and os.path.isdir(embedded_main):
    main_root = embedded_main

if main_root:
    os.environ["AUTOFAB_MAIN_ROOT"] = main_root
    os.environ["UV_PROJECT"] = main_root

if sys.version_info[:2] != (3, 12):
    import shutil
    _cands = []
    if main_root:
        _cands.extend([
            os.path.join(main_root, ".venv", "bin", "python"),
            os.path.join(main_root, ".venv", "bin", "python3"),
            os.path.join(main_root, ".venv", "bin", "python3.12"),
        ])
    _venv = os.environ.get("VIRTUAL_ENV")
    if _venv:
        _cands.extend([
            os.path.join(_venv, "bin", "python"),
            os.path.join(_venv, "bin", "python3"),
            os.path.join(_venv, "bin", "python3.12"),
        ])
    _home = os.path.expanduser("~")
    _cands.extend([
        os.path.join(_home, ".pyenv", "shims", "python3.12"),
        os.path.join(_home, ".pyenv", "shims", "python3"),
        shutil.which("python3.12"),
    ])
    for _cand in _cands:
        if _cand and os.path.isfile(_cand) and os.access(_cand, os.X_OK):
            try:
                os.execv(_cand, [_cand] + sys.argv)
            except OSError:
                pass

if curr and os.path.isdir(curr):
    if curr not in sys.path:
        sys.path.insert(0, curr)

try:
    import autofab_role_tool as role_tool
except ImportError:
    import autofab_role_tool as role_tool

if __name__ == "__main__":
    sys.exit(role_tool.main(["{cmd}"] + sys.argv[1:]))
'''
        with open(tool_path, "wb") as f:
            f.write(b"#!/usr/bin/env python3\n")
            with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("__main__.py", runner_code)
                if roles_toml_bytes is not None:
                    roles_files = app_info.get_roles_filenames()
                    for rf in roles_files:
                        z.writestr(rf, roles_toml_bytes)
                        z.writestr(f"support/{rf}", roles_toml_bytes)
                for arcname, pyc_bytes in pycs.items():
                    z.writestr(arcname, pyc_bytes)
        try:
            os.chmod(tool_path, 0o755)
        except OSError:
            pass


# Contract: __orphan__ - writes role configuration metadata with 0o644 permissions
def write_role_metadata(
    workspace_dir: str,
    role_name: str,
    dir_scope: str,
    repo_root: Optional[str] = None,
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
    max_feedback_chars: Optional[int] = None,
    fused_roles: Optional[Sequence[str]] = None,
    common_spec_roles: Optional[Sequence[str]] = None,
) -> None:
    """Writes role descriptor in workspace root."""
    data: Dict[str, Any] = {
        "role": role_name,
        "role_name": role_name,
        "parts_dir": dir_scope,
        "dir_scope": dir_scope,
    }
    if fused_roles:
        data["fused_roles"] = list(fused_roles)
    if common_spec_roles:
        data["common_spec_roles"] = list(common_spec_roles)
    if model:
        data["model"] = model
    if batch_size is not None:
        data["batch_size"] = batch_size
    if max_feedback_chars is not None:
        data["max_feedback_chars"] = max_feedback_chars

    for fname in sorted(set(app_info.get_role_descriptors())):
        p = os.path.join(workspace_dir, fname)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        try:
            os.chmod(p, 0o644)
        except OSError:
            pass


def write_role_agents_md(
    workspace_dir: str,
    role_def: roles.RoleDefinition,
    dir_scope: str,
) -> None:
    """Generates role AGENTS.md instructions in the workspace."""
    agents_path = os.path.join(workspace_dir, "AGENTS.md")
    is_auditor = not role_def.writable_file_patterns
    can_blame = bool(role_def.feedback_role_deps or role_def.audit_tag or not role_def.writable_file_patterns)
    has_stubs = bool(role_def.stub_role_deps)
    stub_section = ""
    if has_stubs:
        stub_section = f"""
## {app_info.APP_TITLE} Compilation Stubs (DO NOT Edit or Assert Stub Errors)
Any library files under `lib/*.py` imported from role dependencies in this workspace are intentional {app_info.APP_TITLE} compilation stubs (`{app_info.get_stub_marker()}`).
- **Read-Only Stubs for Type-Checking**: These stubs exist solely to provide method signatures and symbols so that your code passes static type-checking and syntax verification via `bin/check_files`.
- **Stub Errors are Normal in This Workspace**: Stubs raise `NotImplementedError` when called because the actual implementation executes in downstream verification, NOT in this workspace.
- **DO NOT EDIT STUBS**: You are strictly prohibited from editing or attempting to implement `lib/*.py`.
- **DO NOT ASSERT STUB ERRORS**: Never write tests expecting or asserting `NotImplementedError` or stub error outcomes. Author tests that verify the real behavioral contracts, postconditions, and invariants specified in `low/*.pyi`.
"""
    guide = role_def.guide_path
    if role_def.guide_path:
        promoted_guide = os.path.join(workspace_dir, "guides", os.path.basename(role_def.guide_path))
        if os.path.isfile(promoted_guide):
            guide = f"guides/{os.path.basename(role_def.guide_path)}"
        elif os.path.isfile(os.path.join(workspace_dir, role_def.guide_path)):
            guide = role_def.guide_path
        else:
            guide = f"guides/{os.path.basename(role_def.guide_path)}"

    meta_path = None
    for desc in app_info.get_role_descriptors():
        cand = os.path.join(workspace_dir, desc)
        if os.path.isfile(cand):
            meta_path = cand
            break
    is_constrained = False
    if meta_path and os.path.isfile(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            model_val = str(meta_data.get("model", "")).lower()
            if any(k in model_val for k in ("qwen", "mlx", "local", "ollama")):
                is_constrained = True
        except Exception:
            pass

    constrained_bullet = ""
    if is_constrained:
        constrained_bullet = (
            "- **Incremental Authoring (Output Token Ceiling Protection)**: Your engine enforces a strict output token ceiling (e.g. 8K tokens). Emitting a massive monolithic file (>400 lines or >4,000 tokens) in a single tool call truncates output mid-generation, corrupting tool envelopes and causing fatal harness crashes. You MUST author extensive implementations or test suites incrementally in staged passes: write a minimal skeleton with core tests/methods first, verify with `bin/check_files`, and then incrementally append or edit remaining tests or methods in separate focused steps.\n"
        )

    if role_def.fused_roles:
        fused_bins = [f"verify_{cr}" for cr in role_def.fused_roles]
        fused_bins_bullets = "\n".join(
            f"- `bin/{b}` — Run verification for {b.removeprefix('verify_')}." for b in fused_bins
        )
        fused_bins_cmds = ", ".join(f"`bin/{b}`" for b in fused_bins)
        workflow = f"""1. Run `bin/get_work` ONCE at session start to inspect assigned ready targets across constituent roles.
2. Low-Level Specification Grounding: Inspect `low/*.pyi` to understand all protocols, method contracts, and invariant postconditions.
3. Author targets in scope following their companion guides in `guides/`:
   - Contract Respect: Implement and test strictly against the contracts in `low/*.pyi`. NEVER pass `None` or invalid types into strictly-typed non-optional parameters unless explicitly contracted in specifications.
   - Non-Concerns as Undefined Behavior: If an anomalous condition or failure mode is uncontracted in the specification, it is undefined behavior; testing it is strictly prohibited.
   - Public Attribution Purity: Do NOT couple tests or assertions to synthetic internal placeholders or private attributes.
   - Targeted Reads Over Full Dumps: Never dump or read entire large files repeatedly. Avoid sequential micro-reading loops. Use grep or read targeted chunks (100-200 lines) around target symbols.
4. Continuous Micro-Binary Verification:
   - Run {fused_bins_cmds} to verify syntax, typing, tests, and coverage across all constituent roles.
5. Arbiter Self-Audits:
   - Audit test suites against QA companion guides: verify tests test genuine behavioral contracts from `low/*.pyi` and pass all property fuzzing.
   - Audit coverage against coverage companion guides: prune uncontracted dead defensive code rather than writing synthetic tests to artificially cover it. Ensure 100% statement and branch coverage.
6. Completion Protocol:
   - When all checks pass with 0 errors, 100% test pass, 100% coverage, and both arbiter self-audits are completed:
   - Report completion by sending: `COMPLETED: All targets and verification passing for <scope>.`
   - DO NOT run `bin/submit`. The coordinator executes verification and atomically harvests and marks all nodes clean.
"""
        feedback_section = """## Arbiter Self-Audit Directives (Fused Role Requirements)
- **QA Arbiter Contract Fidelity Audit**:
  - Type Contract Respect: Tests must respect static type contracts; never pass `None` or invalid types to strictly-typed non-optional parameters unless contracted.
  - Non-Concerns as Undefined Behavior: If behavior during a failure mode or anomalous input is uncontracted, it is undefined behavior; testing it is strictly prohibited.
  - Public Attribution Purity: Verify tests assert public postconditions and invariant properties without coupling to private attributes or synthetic internal graph nodes.
- **Coverage Arbiter Semantic Closure Audit**:
  - Never write synthetic tests solely to exercise defensive branches that are unreachable under valid contract inputs.
  - When unreachable defensive code exists, delete the dead code from the implementation.
  - Only annotate legitimately unreachable platform or fatal conditions with `# pragma: no cover`."""
        resolution_rules = f"""- **Verification on All Constituent Gates**: You MUST run {fused_bins_cmds} until all checks pass with 100% statement and branch coverage.
- **Arbiter Self-Audit**: Before concluding, you MUST audit your implementation and tests against the QA and Coverage guides in `guides/` (zero uncontracted defensive branches, zero unmandated test assertions).
- **Prune Uncontracted Defensive Code**: When verification reports missing coverage on defensive branches, fallback checks, or error paths for uncontracted conditions, prune and delete the unreachable defensive code from your implementation rather than writing elaborate uncontracted tests.
- **Conclude Without `bin/submit`**: Do NOT call `bin/submit` or `bin/check_files`; the coordinator harvests and marks all targets clean after running formal verification.
- **Fail on Impasse**: If you reach an unresolvable impasse where success is impossible, execute `bin/fail <target_file> "<reason>"` immediately."""
        resolution_methods = f"(via {fused_bins_cmds}, or `bin/fail`)"
        workflow_binaries_blame = ""
        round_res_line = "Never attempt to manually commit, push, or copy files across workspace boundaries; the coordinator handles atomic harvest after verifying your workspace."
        runner_tools_list = ", ".join([f"`{b}`" for b in ["get_work"] + fused_bins + ["fail", "revert", "checkpoint"]])
        fail_stop_tools = ", ".join([f"`bin/{b}`" for b in ["get_work"] + fused_bins + ["fail", "revert", "checkpoint"]])
        metadata_tools = "(`bin/fail` or coordinator harvest)"
        test_failure_action = "code edits or `bin/fail`"
        workflow_binaries_section = f"""## Mandatory {app_info.APP_TITLE} Workflow Binaries
All {app_info.APP_TITLE} verification and resolution in this fused role workspace must proceed through the prescribed micro-binaries:
- `bin/get_work` — Discover pending units and tasks across constituent roles (call ONCE at session start).
{fused_bins_bullets}
- `bin/revert` — Revert broken edits or file truncations to the last checkpoint (`bin/revert [target]`).
- `bin/checkpoint` — Record a git commit snapshot of active workspace state (`bin/checkpoint [label]`).
- `bin/fail` — Report an unresolvable impasse."""
        ground_truth_bullet = f"- **Ground Truth First (Oracle Diagnostics Over Prose)**: Always run {fused_bins_cmds} to establish deterministic ground truth errors. Do NOT speculate, guess, or infer defects from prose descriptions before checking oracle output."
    elif can_blame:
        if is_auditor:
            workflow = f"""1. Run `bin/get_work` to evaluate assigned dirty units and synchronize with main.
2. Follow companion guide `{guide}` for role auditing rules.
3. For auditor roles, `bin/get_work` automatically executes verification checks on each dirty target.
4. If all checks pass: `bin/get_work` automatically submits the target with audit attestation and reports 0 ready targets; conclude your round immediately with summary text and ZERO tool calls.
5. If checks fail: Inspect the structured {app_info.APP_TITLE} Triage Summary surfaced by `bin/get_work` (which extracts the author's `# CHANGE:` header and primary failure). Deliver blame attribution via `bin/blame <culprit_file> "<explanation>"`. Your critique MUST explain specifically why the author's change did not resolve the defect against the common specification.
6. If target cannot be certified or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
7. Mandatory Post-Completion: Call `bin/get_work` once to inspect remaining units. If all ready targets are resolved or only blocked targets remain, STOP and conclude your round immediately with summary text and ZERO further tool calls.
"""
            feedback_section = f"""## Delivering Blame & Feedback (Auditor Role Requirements)
- **Consult the {app_info.APP_TITLE} Triage Summary**: When `bin/check_files` fails, it automatically prints a structured {app_info.APP_TITLE} Triage Summary displaying the author's latest `# CHANGE:` commit header, the primary failure diagnostic, and candidate culprit file.
- **Auditor Constraint (Zero File Edits & No Debug Scripts)**: You are an AUDITOR, not an author. You have ZERO assigned writable files. You are STRICTLY FORBIDDEN from writing exploratory Python scripts (`python3 -c "import ..."`), modifying files, running git commands, or attempting to fix or debug the author's code.
- **Tailor Blame Critiques (DO NOT Blindly Recycle Feedback)**:
  - Your blame explanation MUST explain why the author's `# CHANGE:` attempt did not resolve the defect against the common specification.
  - Formulate blame in terms of specification non-compliance (low/*.pyi, scenarios/*.md, or high/*.md).
  - Multi-line critiques are automatically collapsed into a continuous paragraph, but keep feedback direct and focused.
- **Actionable Attribution**: Blame the exact culprit file (`lib/*.py` or `tests/*_test.py`). If both implementation and tests are defective, blame each culprit file with specific critiques.
- **Mandatory Post-Completion Protocol**: Once blame has been recorded via `bin/blame`, custody of the target is immediately returned to upstream authors. You have ZERO remaining work on that target and are STRICTLY FORBIDDEN from attempting to debug or test the author's code, executing python scripts, running dummy shell commands, or re-running `bin/check_files`. Call `bin/get_work` once; if no other ready targets exist, conclude your round immediately with a text summary and ZERO further tool calls."""
        else:
            workflow = f"""1. Run `bin/get_work` to inspect and pull pending work and review any unacted feedback.
2. Follow companion guide `{guide}` to author or update targets in scope, resolving any feedback.
3. Run verification checks: `bin/check_files [target_file]`
4. If checks pass and all feedback is resolved: Submit completed targets via `bin/submit <target_file> "<summary>"` (or `bin/submit <target_file>` if unmodified).
5. If upstream contracts are defective: Deliver blame attribution via `bin/blame <culprit_contract> "<explanation>"`.
6. If success is impossible or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
7. Call `bin/get_work` to inspect remaining units. If all ready targets are resolved or only blocked targets remain, STOP and conclude your round immediately without calling further tools.
"""
            feedback_section = """## Acting on Blame & Feedback (Author Role Requirements)
- **`bin/check_files` ONLY verifies static types and syntax**: It does NOT execute tests or verify runtime logic.
- **Feedback represents runtime test failures or broken behavioral contracts**: Downstream roles (QA, Test, etc.) blame your code when runtime execution or assertions fail.
- **Passing `bin/check_files` does NOT mean the defect is gone**: Never assume that because `bin/check_files` succeeds, the runtime problem cited in feedback "no longer exists" or is "QA's problem later". If you submit without fixing the underlying logic, downstream verification will immediately fail and blame your file again.
- **How to resolve feedback**:
  1. Read the feedback critique in `bin/get_work` carefully to identify the runtime defect.
  2. Inspect the low-level contracts (`low/*.pyi`) and the failing test cases (`tests/*_test.py`) to examine expected behaviors, assertions, and mocks.
  3. Modify your assigned target files in scope so that runtime execution satisfies the contracts and passes the tests.
  4. Run `bin/check_files` to verify clean static compilation and typing.
  5. Submit via `bin/submit <target_file> "<summary>"` with a clear change summary explaining how the fix resolves the feedback."""

        if is_auditor:
            resolution_rules = """- **ZERO TOLERANCE FOR COMPLAINING OR IDLING IN CHAT**: When `bin/check_files` fails, stopping with conversational commentary, explaining why output did not change, or complaining without executing `bin/blame` is STRICTLY PROHIBITED. Conversational complaints do not mutate build state, and upstream authoring roles cannot inspect chat transcripts.
- **Actionable Blame Delivery**: When checks fail due to defects in library code, test code, or upstream specifications, you MUST execute `bin/blame <culprit_file> "<actionable critique>"` immediately. Auditors can blame both the lib and test files if both contain defects.
- **Blame Concludes Target Custody**: Calling `bin/blame` immediately transfers custody of the target back to upstream authors. DO NOT run further diagnostic commands, scripts, or checks on blamed targets.
- **Submission on Success**: When checks pass, you MUST execute `bin/submit <target_file>` immediately.
- **Fail on Impasse**: If you reach an unresolvable impasse where neither submit nor blame applies, execute `bin/fail <target_file> "<reason>"` immediately.
- **Never end a round while ready targets remain unresolved. When all ready targets are resolved or only blocked targets remain, conclude your round immediately without further tool calls.**"""
        else:
            resolution_rules = """- **ZERO TOLERANCE FOR COMPLAINING OR IDLING IN CHAT**: When `bin/check_files` fails, stopping with conversational commentary, explaining why output did not change, or complaining without executing `bin/blame` is STRICTLY PROHIBITED. Conversational complaints do not mutate build state, and upstream authoring roles cannot inspect chat transcripts.
- **Actionable Blame Delivery**: When checks fail due to defects in library code, test code, or upstream specifications, you MUST execute `bin/blame <culprit_file> "<actionable critique>"` immediately. Auditors can blame both the lib and test files if both contain defects.
- **Submission on Success**: When checks pass, you MUST execute `bin/submit <target_file>` immediately.
- **Fail on Impasse**: If you reach an unresolvable impasse where neither submit nor blame applies, execute `bin/fail <target_file> "<reason>"` immediately.
- **Never end a round while ready targets remain unresolved. When all ready targets are resolved or only blocked targets remain, conclude your round immediately without further tool calls.**"""
        resolution_methods = "(`bin/submit`, `bin/blame`, or `bin/fail`)"
        workflow_binaries_blame = "- `bin/blame` — Attribute blame and return defective targets to upstream roles.\n"
        round_res_line = "Never attempt to manually commit, push, or copy files across workspace boundaries; round resolution must always occur via `bin/submit`, `bin/blame`, or `bin/fail`."
        if is_auditor:
            runner_tools_list = "`get_work`, `check_files`, `submit`, `blame`, `fail`"
            fail_stop_tools = "`bin/get_work`, `bin/check_files`, `bin/blame`, `bin/submit`, `bin/fail`"
            metadata_tools = "(`bin/submit`, `bin/blame`, `bin/fail`)"
            test_failure_action = "`bin/blame` or `bin/fail`"
            workflow_binaries_section = f"""## Mandatory {app_info.APP_TITLE} Workflow Binaries
All {app_info.APP_TITLE} target resolution must proceed through the prescribed workspace binaries:
- `bin/get_work` — Discover pending units and tasks.
- `bin/check_files` — Run static verification, linting, and type checking on targets.
- `bin/submit` — Submit verified targets to main.
{workflow_binaries_blame}- `bin/fail` — Report an unresolvable impasse."""
        else:
            runner_tools_list = "`get_work`, `check_files`, `submit`, `blame`, `fail`, `revert`, `checkpoint`"
            fail_stop_tools = "`bin/get_work`, `bin/check_files`, `bin/blame`, `bin/submit`, `bin/fail`, `bin/revert`, `bin/checkpoint`"
            metadata_tools = "(`bin/submit`, `bin/blame`, `bin/fail`)"
            test_failure_action = "`bin/blame`, `bin/fail`, or code edits"
            workflow_binaries_section = f"""## Mandatory {app_info.APP_TITLE} Workflow Binaries
All {app_info.APP_TITLE} target resolution must proceed through the prescribed workspace binaries:
- `bin/get_work` — Discover pending units and tasks.
- `bin/check_files` — Run static verification, linting, and type checking on targets.
- `bin/submit` — Submit verified targets to main.
{workflow_binaries_blame}- `bin/revert` — Revert broken edits or file truncations to the last checkpoint (`bin/revert [target]`).
- `bin/checkpoint` — Record a git commit snapshot of active workspace state (`bin/checkpoint [label]`).
- `bin/fail` — Report an unresolvable impasse."""
        ground_truth_bullet = "- **Ground Truth First (Oracle Diagnostics Over Prose)**: Always run `bin/check_files <target>` to establish deterministic ground truth errors before writing or editing code. Do NOT speculate, guess, or infer defects from prose descriptions before checking oracle output."
    else:
        workflow = f"""1. Run `bin/get_work` to inspect and pull pending work and review any unacted feedback.
2. Follow companion guide `{guide}` to author or update targets in scope, resolving any feedback.
3. Run verification checks: `bin/check_files [target_file]`
4. If checks pass and all feedback is resolved: Submit completed targets via `bin/submit <target_file> "<summary>"` (or `bin/submit <target_file>` if unmodified).
5. If success is impossible or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
6. Call `bin/get_work` to inspect remaining units. If all ready targets are resolved or only blocked targets remain, STOP and conclude your round immediately without calling further tools.
"""
        feedback_section = """## Acting on Blame & Feedback (Author Role Requirements)
- **`bin/check_files` ONLY verifies static types and syntax**: It does NOT execute tests or verify runtime logic.
- **Feedback represents runtime test failures or broken behavioral contracts**: Downstream roles (QA, Test, etc.) blame your code when runtime execution or assertions fail.
- **Passing `bin/check_files` does NOT mean the defect is gone**: Never assume that because `bin/check_files` succeeds, the runtime problem cited in feedback "no longer exists" or is "QA's problem later". If you submit without fixing the underlying logic, downstream verification will immediately fail and blame your file again.
- **How to resolve feedback**:
  1. Read the feedback critique in `bin/get_work` carefully to identify the runtime defect.
  2. Inspect the low-level contracts (`low/*.pyi`) and the failing test cases (`tests/*_test.py`) to examine expected behaviors, assertions, and mocks.
  3. Modify your assigned target files in scope so that runtime execution satisfies the contracts and passes the tests.
  4. Run `bin/check_files` to verify clean static compilation and typing.
  5. Submit via `bin/submit <target_file> "<summary>"` with a clear change summary explaining how the fix resolves the feedback."""
        resolution_rules = """- **Submission on Success**: When checks pass and all feedback is addressed, you MUST execute `bin/submit <target_file> "<summary>"` immediately.
- **Fail on Impasse**: If you reach an unresolvable impasse where success is impossible, execute `bin/fail <target_file> "<reason>"` immediately.
- **Never end a round while ready targets remain unresolved. When all ready targets are resolved or only blocked targets remain, conclude your round immediately without further tool calls.**"""
        resolution_methods = "(`bin/submit` or `bin/fail`)"
        workflow_binaries_blame = ""
        round_res_line = "Never attempt to manually commit, push, or copy files across workspace boundaries; round resolution must always occur via `bin/submit` or `bin/fail`."
        runner_tools_list = "`get_work`, `check_files`, `submit`, `fail`, `revert`, `checkpoint`"
        fail_stop_tools = "`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/fail`, `bin/revert`, `bin/checkpoint`"
        metadata_tools = "(`bin/submit` or `bin/fail`)"
        test_failure_action = "code edits or `bin/fail`"
        workflow_binaries_section = f"""## Mandatory {app_info.APP_TITLE} Workflow Binaries
All {app_info.APP_TITLE} target resolution must proceed through the prescribed workspace binaries:
- `bin/get_work` — Discover pending units and tasks.
- `bin/check_files` — Run static verification, linting, and type checking on targets.
- `bin/submit` — Submit verified targets to main.
{workflow_binaries_blame}- `bin/revert` — Revert broken edits or file truncations to the last checkpoint (`bin/revert [target]`).
- `bin/checkpoint` — Record a git commit snapshot of active workspace state (`bin/checkpoint [label]`).
- `bin/fail` — Report an unresolvable impasse."""
        ground_truth_bullet = "- **Ground Truth First (Oracle Diagnostics Over Prose)**: Always run `bin/check_files <target>` to establish deterministic ground truth errors before writing or editing code. Do NOT speculate, guess, or infer defects from prose descriptions before checking oracle output."

    if is_auditor:
        custodian_bullet = "- **Auditor Constraint (Zero File Edits & No Debug Scripts)**: You are an auditor (inspector/verifier), NOT an author. All files in this workspace are read-only contracts and test fixtures. You have ZERO assigned writable files and are STRICTLY FORBIDDEN from editing, modifying, creating, or deleting files in this workspace. You perform verification via `bin/check_files` and provide feedback via `bin/blame`. You are STRICTLY FORBIDDEN from authoring ad-hoc python scripts (e.g. `python -c \"...\"`) to debug author code."
        undo_section = ""
        rule_2 = "2. **Git & File Modification Prohibited**: All files in this workspace are read-only contracts or oracle test fixtures. You are strictly forbidden from editing, creating, renaming, deleting, or mutating any files, and strictly forbidden from executing any git commands."
        permitted_cmds = "You ARE permitted to run read-only shell utilities (`cat`, `grep`, `find`, etc.) or native harness tools strictly WITHIN this workspace directory (`.`) to inspect files. Mutating files, running python debug scripts, and executing git commands are strictly prohibited."
    else:
        custodian_bullet = "- **Sole Custodian & Target File Ownership**: You are the sole author and custodian of your assigned target file(s). No other external agent or background process modifies your assigned target files in this workspace. Therefore, you do not need to re-read your target file repeatedly unless verifying your own edits. When feedback or blame arrives, it is provided directly to you in `bin/get_work` (and reflected in the `# FEEDBACK:` block of your target file)."
        undo_section = """## Workspace Undo & Checkpoint Architecture
This workspace is an isolated git tracking repository with automatic pre-tool checkpointing:
- **Automatic Pre-Tool Snapshots**: Before file edits (`edit_file` or `write_file`), an automatic git checkpoint is committed.
- **Milestone Snapshots**: Whenever `bin/check_files <target>` passes cleanly with 0 errors, a milestone checkpoint is committed to record the clean state.
- **Instant Rollback**: If an edit introduces syntax errors, breaks tests, or truncates a file, use `bin/revert [target]` or `git restore <target>` to restore the last verified state. Never call `bin/fail` for broken edits that can be reverted.
- **Diff Inspection**: Use `git diff [target]` to review uncommitted changes against the last checkpoint.
"""
        rule_2 = "2. **External Git Operations Prohibited (Local Rollback Permitted)**: Git operations targeting external or upstream repositories (such as git push, git fetch, or cloning) are strictly prohibited. However, local in-workspace rollback and diff commands (`git restore <target>`, `git diff <target>`, or `bin/revert [target]`) are explicitly permitted and encouraged to recover from broken edits or file truncations."
        permitted_cmds = (
            "You ARE permitted to run read-only shell utilities (`cat`, `grep`, `find`, `head`, `tail`, `sed`, etc.) "
            "or native harness tools strictly WITHIN this workspace directory (`.`) to inspect files and complete your tasks.\n"
            "Unbounded searches outside the workspace (e.g., `find /`, `grep -r /`) and Git operations against external repositories are strictly prohibited.\n"
            "Executing ad-hoc tests, runtime assertions, or inline Python scripts (including via `python3 -c`, `python -c`, or stdin heredocs `python3 - <<'EOF'`) "
            "is strictly prohibited; target verification is exclusively performed via `bin/check_files` (or `bin/verify_*` for fused roles). "
            "You are not allowed to execute the test suite or run ad-hoc probes; submit work via `bin/submit` so a downstream QA auditor can execute the test suite on your behalf.\n"
            "Package management operations (such as running `uv`, `pip`, `pip3`, `python -m pip`, `conda`, `apt`, `brew`) are strictly prohibited; the environment and dependencies are pre-configured. Never attempt to install or modify packages."
        )

    content = f"""# {app_info.APP_TITLE} Role Instructions: {role_def.role_name.capitalize()}

## Scope & Constraints
- Role: `{role_def.role_name}`
- Directory Scope: `{dir_scope}`
- Companion Guide: `{guide}`
{stub_section}
## Continuous Tool Execution & Operational Rules
- **Continuous Tool Execution (No Idling or Dangling Colons)**: You are an autonomous agent step runner. While ready targets remain unresolved, you must ALWAYS invoke a tool in every step. Never output conversational text, explanations, or sentences ending in colons without invoking tools in the same step. Every in-progress step MUST execute a tool call.
{ground_truth_bullet}
{custodian_bullet}
- **Targeted Reads Over Micro-Read Loops**: Strictly avoid sequential loops of tiny (e.g. 30-line) windowed reads. Never dump or read entire large files repeatedly. Instead, read targeted chunks of 100-200 lines around target symbols or definitions, or use grep to pinpoint locations before reading.
- **Strict Workspace Confinement**: All file inspections, searches, and commands MUST remain strictly confined within your assigned role workspace directory (`.`). Never execute unbounded filesystem searches (such as `find /` or searches across root/parent directories).
- **Ground Truth Oracle Exclusivity**: Use only `bin/check_files` (or `bin/verify_*` for fused roles) as the deterministic oracle for errors and validation. Do NOT invent custom linters or scripts.
- **Restricted Targets & Test Execution Ban**: Edit ONLY your assigned target files. Do NOT create scratch tests, temporary test scripts, or auxiliary test runners. Executing ad-hoc tests, runtime sanity checks, or test assertions (including via `python3 -c`, `python -c`, or stdin heredocs) is strictly prohibited. You are not allowed to execute the test suite or run ad-hoc probes. Rely EXCLUSIVELY on `bin/check_files` (or `bin/verify_*` for fused roles) for target verification, and submit work with `bin/submit` so a downstream QA auditor can execute the test suite on your behalf.
- **No Runner Binary Inspection or Linter Hunting**: Runner executables in `bin/` ({runner_tools_list}) are encapsulated self-contained tools. Do NOT search for internal linters (`*_lint.py`, `test_lint`, `build_lint`), and do NOT attempt to read, disassemble, decompile, or run inspection utilities (`file`, `strings`, `unzip`, `head`, `od`, `xxd`) on `bin/` executables. All required structural rules and conventions are documented in your Companion Guide.
- **Standard Terminology**:
  - **Step**: A single prompt ↔ tool-call interaction cycle between an agent/model and the runtime.
  - **Round**: A full {app_info.APP_TITLE} role dispatch wave or execution pass across assigned targets until submission, blame, or exhaustion.
{constrained_bullet}
## Mandatory Target Resolution (Do NOT End Round Without Resolving)
Every ready target acquired via `bin/get_work` MUST be explicitly resolved before concluding your round:
{resolution_rules}

## Round Conclusion Protocol
When you have no outstanding work to do and `bin/get_work` does not give you more work to do (all ready targets have been resolved {resolution_methods}, or `bin/get_work` indicates that only blocked targets remain or no ready targets exist):
- **YOU CAN AND MUST CONCLUDE IMMEDIATELY**: Your round is complete.
- **STOP IMMEDIATELY — NO FURTHER TOOL CALLS**: Do NOT execute any further tool calls (`ls`, `bin/get_work`, `cat`, `rm`, `echo`, dummy shell commands, or inspecting directories). Repeatedly running tools when there are no ready targets wastes steps and triggers impasse warnings.
- **Conclude with Text Only**: Output a concise final summary of your resolved actions and end your round. The continuous tool execution rule applies ONLY while work remains; delivering a text summary with ZERO tool calls is the expected and required signal that concludes your round cleanly in the runtime harness.

{undo_section}
## Strict Boundary Rules (Zero Exceptions)
1. **Workspace Boundary**: All commands and tool invocations MUST execute strictly within this workspace directory (`.`). You are strictly prohibited from passing any other directory as `Cwd` or running commands outside this workspace. Never execute unbounded filesystem searches (`find /`) or scans across parent directories.
{rule_2}
3. **Main Repository Inviolability**: The main workspace is strictly read-only and off-limits to direct agent actions. All interaction with main occurs exclusively through the prescribed `bin/` tools.
4. **Metadata Inviolability & Projection**: DO NOT EDIT METADATA. Never manually edit `# --- CLEANROOM METADATA ---` or `<!-- CLEANROOM METADATA -->` headers. Use only tools {metadata_tools}. In-band metadata headers in role workspace files are projected to show only change, feedback, and ephemeral code hash fields; canonical lifecycle timestamps (such as LAST_CLEANED, LAST_CHANGED, and audit tags) are maintained exclusively in the main repository and managed by `bin/submit`. Do not expect or attempt to add LAST_CLEANED or LAST_CHANGED in workspace files. Do NOT report files as "flagged for missing LAST_CLEANED" or assume they are clean just because static checks pass. When a file is dirty, perform thorough semantic verification against contracts and test suites.

## In-Workspace File Reading & Inspection (Fully Permitted & Required)
You ARE permitted and expected to read and inspect files WITHIN your assigned role workspace directory (`.`) using your host environment's native tools or standard shell commands (`cat`, `grep`, `find`, etc.):
- **Inspect Specifications**: Read low-level interface specifications (`low/*.pyi`) and contracts to understand required classes, functions, invariants, and postconditions.
- **Inspect Companion Guide**: Read your assigned companion guide (`{guide}`) for document layout, type patterns, mock structures, and required conventions. Your companion guide is your authoritative format reference—do NOT search for other files in the workspace for formatting examples.
- **Inspect Test Suites**: Read test files (`tests/*_test.py`) when diagnosing failures to examine assertions, failure expectations, and mocks.
- **Inspect Implementation Code**: Read implementation code (`lib/*.py`) to triage failures, locate exact function names and defective line numbers, and inspect the `# CHANGE:` commit header to understand how the author attempted to address previous blame.
The Contamination Tripwire applies strictly to reading files OUTSIDE this workspace. Reading any file within `.` is 100% safe, encouraged, and required for thorough diagnosis.

## In-Workspace Execution & Permitted Commands
{permitted_cmds}

{workflow_binaries_section}

{round_res_line}

## Contamination Tripwire (Poison Pill)
**ZERO TOLERANCE FOR READING OUT-OF-BOUNDS FILES.**

If you read ANY file outside of your assigned role workspace (such as in `../../`, the canonical main repository, or other role workspaces via ANY tool or mechanism):
1. **YOU ARE PERMANENTLY CONTAMINATED.**
2. **ALL WORK MUST CEASE IMMEDIATELY.** You are strictly prohibited from performing any further work, authoring code, modifying files, running verification checks, or submitting targets (`bin/submit`).
3. **IMMEDIATE ABORT**: Your ONLY permitted action is to immediately report the exact contamination to the user and STOP all tool usage:
   > `CRITICAL CONTAMINATION: I read a file outside my assigned role workspace ([path]). This session is compromised and terminated.`

This is an absolute tripwire for out-of-bounds files. There are NO exceptions for debugging, diagnosing tracebacks, inspecting imports, or reading dependencies outside this workspace. (Reading files inside this workspace directory is 100% permitted).

{feedback_section}

## Fail-Stop & Reporting Protocol (Do NOT Self-Heal)
If any {app_info.APP_NAME} binary ({fail_stop_tools}) fails due to:
- A Python exception or traceback (e.g., `ModuleNotFoundError`, `ImportError`, `AttributeError`)
- A build, type check, or test execution failure
- A missing support file, template error, or dependency issue

**STOP IMMEDIATELY.**
- **DO NOT** attempt to fix, patch, restore, or work around the infrastructure.
- **DO NOT** install, update, or modify packages (running `uv`, `pip`, or package managers is strictly prohibited).
- **DO NOT** create, undelete, or check out missing files.
- **DO NOT** attempt alternate execution paths outside `bin/`.
- **REPORT IMMEDIATELY**: Output the exact command that failed and its verbatim error/traceback to the user, state what dependency or file appears to be missing, and wait for human instruction.

NOTE: Verification test failures (e.g. `[FAIL] Verification failed` or `[FAIL] Verification timed out` output from tests or linters on code under test) are NORMAL test results to be acted upon via {test_failure_action}, NOT infrastructure crashes. Timeouts, process hangs, and termination by SIGTERM during test verification indicate code defects (such as infinite loops, deadlocks, live-locks, or unresolvable dependencies in the code under test), NOT infrastructure failures. When `bin/check_files` times out or receives SIGTERM, do NOT fail-stop; diagnose the hanging method/loop and issue a blame against the culprit file. Fail-Stop applies ONLY to internal tool crashes, tracebacks, or missing tooling/dependencies.

## Unresolvable Impasse & Failure Protocol
If you determine that success is not possible (e.g. unreachable code under test, contradictory specification contracts, or dead ends that blame cannot resolve):
1. **DO NOT** attempt ad-hoc debugging, script execution, or reverse-engineering of {app_info.APP_NAME} tools.
2. Execute: `bin/fail <target_file> "<reason>"`
3. Report failure to the coordinator via `send_message`: `FAILED: <target_file> - <reason>`
4. Cease work immediately.

## Standard Workflow
{workflow}
"""
    with open(agents_path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(agents_path, 0o644)
    except OSError:
        pass


# Contract: Realizes scaffold.WorkspaceScaffolder singleton.
class WorkspaceScaffolder(scaffold.WorkspaceScaffolder):
    """Realizes runner zipapp packaging, role metadata, guide synthesis, and starter skeletons."""

    tier = agent_session.agent_session

    # Contract: Packages runner zipapps into bin_dir with executable permissions.
    def deploy_runner_zipapps(
        self,
        bin_dir: str,
        role_def: Optional[roles.RoleDefinition] = None,
        can_blame: bool = True,
    ) -> None:
        if role_def is not None:
            can_blame = bool(role_def.feedback_role_deps or role_def.audit_tag or not role_def.writable_file_patterns)
        package_runner_zipapps(bin_dir, can_blame=can_blame, role_def=role_def)

    # Contract: Writes role configuration metadata (autofab_files_ext.ROLE_DESCRIPTOR_FILE) in workspace root.
    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
        fused_roles: Optional[Sequence[str]] = None,
        common_spec_roles: Optional[Sequence[str]] = None,
    ) -> None:
        write_role_metadata(
            workspace_dir,
            role_name,
            dir_scope,
            repo_root=repo_root,
            model=model,
            batch_size=batch_size,
            max_feedback_chars=max_feedback_chars,
            fused_roles=fused_roles,
            common_spec_roles=common_spec_roles,
        )

    # Contract: Synthesizes role-tailored AGENTS.md instructions in workspace root.
    def write_role_agents_guide(
        self,
        workspace_dir: str,
        role_def: roles.RoleDefinition,
        dir_scope: str,
    ) -> None:
        write_role_agents_md(workspace_dir, role_def, dir_scope)

    # Contract: Creates starter skeletons for declared writable targets absent from disk.
    def create_missing_target_skeletons(
        self,
        workspace_dir: str,
        repo_root: str,
        dir_scope: str,
        role_def: roles.RoleDefinition,
    ) -> List[str]:
        return _create_missing_target_skeletons(
            workspace_dir, repo_root, dir_scope, role_def
        )

    # Contract: Writes text content to destination file and applies exact permissions.
    def write_file_with_permissions(
        self,
        dst: str,
        content: str,
        readonly: bool = False,
        executable: bool = False,
    ) -> None:
        write_file_with_perms(dst, content, readonly=readonly, executable=executable)
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T11:00:00Z
# LAST_CHANGED: 2026-11-03T20:40:00Z
# CHANGE: Ground template command execution in repository environment with UV_PROJECT and bind UV_PROJECT in runner zipapps
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceScaffolder,
        keys=[WorkspaceScaffolder, scaffold.WorkspaceScaffolder],
        tier=WorkspaceScaffolder.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
