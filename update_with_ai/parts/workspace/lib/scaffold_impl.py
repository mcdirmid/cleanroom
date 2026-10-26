"""Low-level implementation for scaffold_impl."""

from __future__ import annotations

import fnmatch
import json
import os
import sys
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from . import roles, scaffold


# Contract: Metadata file name matching cleanroom_files_ext.ROLE_DESCRIPTOR_FILE.
ROLE_CONFIG_FILE = ".cleanroom_role.json"


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


def _find_spec_pyi(
    part_path: str, stem: str, main_root: Optional[str] = None
) -> Optional[str]:
    """Finds companion .pyi specification file for a unit stem in a part directory."""
    for spec_dir in ("low", "grounding"):
        candidate = os.path.join(part_path, spec_dir, f"{stem}.pyi")
        if os.path.isfile(candidate):
            return candidate
    if main_root:
        part_name = os.path.basename(part_path)
        try:
            for entry in os.listdir(main_root):
                base_dir = os.path.join(main_root, entry)
                if not os.path.isdir(base_dir) or entry.startswith((".", "bazel-", "venv")):
                    continue
                for spec_dir in ("low", "grounding"):
                    candidate = os.path.join(
                        base_dir, "parts", part_name, spec_dir, f"{stem}.pyi"
                    )
                    if os.path.isfile(candidate):
                        return candidate
        except OSError:
            pass
    return None


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
        for sub in ("low", "grounding", "high"):
            sub_dir = os.path.join(part_dir, sub)
            if not os.path.isdir(sub_dir):
                continue
            try:
                for fname in os.listdir(sub_dir):
                    if fname.startswith(".") or fname == "__init__.py":
                        continue
                    if not fname.endswith((".pyi", ".py", ".md")):
                        continue
                    stem = os.path.splitext(fname)[0]
                    if stem and stem != "__init__" and not stem.endswith("_ext"):
                        stems.add(stem)
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
    if not rel_path.endswith(".py"):
        return None
    pyi_path = _find_spec_pyi(
        os.path.join(repo_root, unit_dir), unit_name, main_root=repo_root
    )
    if pyi_path is None or not os.path.isfile(pyi_path):
        return None
    try:
        generate_lib_skeleton = None
        try:
            from support.lib.lib_lint import generate_lib_skeleton
        except ImportError:
            pass
        if generate_lib_skeleton is None:
            import importlib
            for entry in os.listdir(repo_root):
                pkg_dir = os.path.join(repo_root, entry)
                if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv")):
                    try:
                        mod = importlib.import_module(f"{entry}.support.lib.lib_lint")
                        # Legitimate reflection: optional plugin hook discovery on dynamically imported module
                        generate_lib_skeleton = getattr(mod, "generate_lib_skeleton", None)
                        if generate_lib_skeleton is not None:
                            break
                    except ImportError:
                        pass
        if generate_lib_skeleton is None:
            return None
        segments = unit_dir.replace("\\", "/").split("/")
        base_pkg = ""
        if "parts" in segments and segments.index("parts") > 0:
            base_pkg = segments[segments.index("parts") - 1]
        return generate_lib_skeleton(pyi_path, unit_name, parts_base=base_pkg or None)
    except (ImportError, OSError, SyntaxError, RuntimeError, ValueError):
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
        rel_path = role_def.src_pattern.format(unit_dir=unit_dir, unit_name=unit_name)
        if not _matches_any_pattern(rel_path, role_def.writable_file_patterns):
            continue
        if os.path.isfile(os.path.join(workspace_dir, rel_path)) or os.path.isfile(
            os.path.join(repo_root, rel_path)
        ):
            continue
        skeleton = _missing_target_skeleton(
            repo_root, rel_path, unit_dir, unit_name, role_def, workspace_dir=workspace_dir
        )
        if skeleton is None:
            continue
        dst_path = os.path.join(workspace_dir, rel_path)
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
    """Compiles cleanroom support modules to optimized .pyc bytecode for runner zipapps."""
    pycs: dict[str, bytes] = {}
    support_dirs: list[str] = []

    repo_root = os.environ.get("CLEANROOM_MAIN_ROOT")
    if not repo_root or not os.path.isdir(repo_root):
        ws_dir = os.path.dirname(bin_dir)
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) == "role_workspaces":
            p_root = os.path.dirname(parent)
            ws_base = os.path.basename(ws_dir)
            try:
                for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                    if entry != "role_workspaces" and ws_base.startswith(f"{entry}_"):
                        cand = os.path.join(p_root, entry)
                        if os.path.isdir(cand):
                            repo_root = cand
                            break
            except OSError:
                pass
    if not repo_root or not os.path.isdir(repo_root):
        try:
            cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
            if os.path.isdir(cand) and (os.path.isfile(os.path.join(cand, "cleanroom.toml")) or os.path.isfile(os.path.join(cand, "pyproject.toml"))):
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
        pycs["support/lib/__init__.pyc"] = empty_init_bytes
        pycs["update_with_ai/__init__.pyc"] = empty_init_bytes
        pycs["update_with_ai/parts/__init__.pyc"] = empty_init_bytes
        pycs["parts/__init__.pyc"] = empty_init_bytes

        for sdir in support_dirs:
            try:
                pkg_name = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(sdir))))
                if pkg_name:
                    pycs[f"{pkg_name}/__init__.pyc"] = empty_init_bytes
                    pycs[f"{pkg_name}/support/__init__.pyc"] = empty_init_bytes
                    pycs[f"{pkg_name}/support/lib/__init__.pyc"] = empty_init_bytes

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
                                        pycs[arcname_py] = sf.read()
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

        # Collect and compile all update_with_ai library modules
        try:
            if repo_root and os.path.isdir(repo_root):
                parts_root = os.path.join(repo_root, "update_with_ai", "parts")
                if os.path.isdir(parts_root):
                    for root, _, files in os.walk(parts_root):
                        if "/lib" in root or root.endswith("/lib"):
                            rel_long = os.path.relpath(root, repo_root).replace(os.sep, "/")
                            rel_short = os.path.relpath(root, os.path.join(repo_root, "update_with_ai")).replace(os.sep, "/")
                            long_segs = rel_long.split("/")
                            for i in range(1, len(long_segs)):
                                k = "/".join(long_segs[:i]) + "/__init__.pyc"
                                if k not in pycs:
                                    pycs[k] = empty_init_bytes
                            short_segs = rel_short.split("/")
                            for i in range(1, len(short_segs)):
                                k = "/".join(short_segs[:i]) + "/__init__.pyc"
                                if k not in pycs:
                                    pycs[k] = empty_init_bytes

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
                                    except Exception:
                                        pass
        except Exception:
            pass
    return pycs


def _find_roles_toml_content(bin_dir: str) -> Optional[bytes]:
    """Locates and reads canonical cleanroom_roles.toml content for bundling into runner zipapps."""
    repo_root = os.environ.get("CLEANROOM_MAIN_ROOT")
    if not repo_root or not os.path.isdir(repo_root):
        ws_dir = os.path.dirname(bin_dir)
        parent = os.path.dirname(ws_dir)
        if os.path.basename(parent) == "role_workspaces":
            p_root = os.path.dirname(parent)
            ws_base = os.path.basename(ws_dir)
            try:
                for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                    if entry != "role_workspaces" and ws_base.startswith(f"{entry}_"):
                        cand = os.path.join(p_root, entry)
                        if os.path.isdir(cand):
                            repo_root = cand
                            break
            except OSError:
                pass
    if not repo_root or not os.path.isdir(repo_root):
        try:
            cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
            if os.path.isdir(cand) and (
                os.path.isfile(os.path.join(cand, "cleanroom.toml"))
                or os.path.isfile(os.path.join(cand, "pyproject.toml"))
            ):
                repo_root = cand
        except Exception:
            pass

    if repo_root and os.path.isdir(repo_root):
        cand = os.path.join(repo_root, "cleanroom_roles.toml")
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    return f.read()
            except OSError:
                pass
        try:
            for sub in os.listdir(repo_root):
                cand = os.path.join(repo_root, sub, "cleanroom_roles.toml")
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
            cand = os.path.join(p, "cleanroom_roles.toml")
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        return f.read()
                except OSError:
                    pass
            try:
                for sub in os.listdir(p):
                    cand = os.path.join(p, sub, "cleanroom_roles.toml")
                    if os.path.isfile(cand):
                        try:
                            with open(cand, "rb") as f:
                                return f.read()
                        except OSError:
                            pass
            except OSError:
                pass

    try:
        import importlib.resources
        data = importlib.resources.files("update_python_with_ai").joinpath("cleanroom_roles.toml").read_bytes()
        if data:
            return data
    except Exception:
        pass

    return None


def package_runner_zipapps(bin_dir: str, can_blame: bool = True) -> None:
    """Packages runner zipapps into bin_dir with executable permissions."""
    os.makedirs(bin_dir, exist_ok=True)
    tools = {
        "get_work": "get_work",
        "check_files": "check_files",
        "submit": "submit",
        "fail": "fail",
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
    cov_path = os.path.join(bin_dir, "coverage")
    # Contract: Removes stale coverage script if present in bin_dir.
    if os.path.isfile(cov_path):
        try:
            os.remove(cov_path)
        except OSError:
            pass

    pycs = _collect_and_compile_runner_pycs(bin_dir)
    roles_toml_bytes = _find_roles_toml_content(bin_dir)

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
        if os.path.basename(parent) == "role_workspaces":
            p_root = os.path.dirname(parent)
            ws_base = os.path.basename(ws_dir)
            for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                if entry != "role_workspaces" and ws_base.startswith(f"{{entry}}_"):
                    cand = os.path.join(p_root, entry)
                    if os.path.isdir(cand):
                        main_root = cand
                        break
        break
    ws_dir = os.path.dirname(ws_dir)

if main_root:
    os.environ["CLEANROOM_MAIN_ROOT"] = main_root

if curr and os.path.isdir(curr):
    if curr not in sys.path:
        sys.path.insert(0, curr)

import cleanroom_role_tool
if __name__ == "__main__":
    sys.exit(cleanroom_role_tool.main(["{cmd}"] + sys.argv[1:]))
'''
        with open(tool_path, "wb") as f:
            f.write(b"#!/usr/bin/env python3\n")
            with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("__main__.py", runner_code)
                if roles_toml_bytes is not None:
                    z.writestr("cleanroom_roles.toml", roles_toml_bytes)
                    z.writestr("support/cleanroom_roles.toml", roles_toml_bytes)
                    z.writestr("update_python_with_ai/cleanroom_roles.toml", roles_toml_bytes)
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
) -> None:
    """Writes .cleanroom_role.json in workspace root."""
    meta_path = os.path.join(workspace_dir, ROLE_CONFIG_FILE)
    data: Dict[str, Any] = {
        "role": role_name,
        "role_name": role_name,
        "parts_dir": dir_scope,
        "dir_scope": dir_scope,
    }
    if model:
        data["model"] = model
    if batch_size is not None:
        data["batch_size"] = batch_size
    if max_feedback_chars is not None:
        data["max_feedback_chars"] = max_feedback_chars
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    try:
        os.chmod(meta_path, 0o644)
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
    guide = role_def.guide_path
    if role_def.guide_path:
        promoted_guide = os.path.join(workspace_dir, "guides", os.path.basename(role_def.guide_path))
        if os.path.isfile(promoted_guide):
            guide = f"guides/{os.path.basename(role_def.guide_path)}"
        elif os.path.isfile(os.path.join(workspace_dir, role_def.guide_path)):
            guide = role_def.guide_path
        else:
            guide = f"guides/{os.path.basename(role_def.guide_path)}"

    meta_path = os.path.join(workspace_dir, ".cleanroom_role.json")
    is_constrained = False
    if os.path.isfile(meta_path):
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

    if is_auditor:
        workflow = f"""1. Run `bin/get_work` to synchronize with main and inspect pending dirty units.
2. Read the `# CHANGE:` metadata header in the target file (`lib/*.py` or `tests/*_test.py`) using host file-reading tools to inspect what the author attempted to fix.
3. Follow companion guide `{guide}` to verify target compliance against `low/*.pyi` contracts.
4. Run verification checks: `bin/check_files [target_file]`
5. If checks pass: Submit verification stamp via `bin/submit <target_file>`.
6. If checks fail: Deliver blame attribution via `bin/blame <culprit_file> "<explanation>"`. Your critique MUST reference the author's `# CHANGE:` attempt and explain specifically why the attempted fix did not resolve the defect or what remains broken (DO NOT merely complain in chat without blaming, and DO NOT recycle identical blame text without considering what changed).
7. If target cannot be certified or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
8. Call `bin/get_work` to inspect remaining units. If all ready targets are resolved or only blocked targets remain, STOP and conclude your round immediately without calling further tools.
"""
        feedback_section = """## Delivering Blame & Feedback (Auditor Role Requirements)
- **Inspect `# CHANGE:` Commit Headers**: Before delivering blame, you MUST inspect the `# CHANGE:` metadata header at the top of the target file (`lib/*.py` or `tests/*_test.py`) using your file-reading tools. The `# CHANGE:` header explains what the author attempted to fix in response to previous feedback.
- **Evaluate Attempted Fixes Against Actual Failures**: Compare what the author attempted against the failures observed in `bin/check_files`. Evaluate whether the attempted fix addressed the cited defect or whether the defect persists under different conditions.
- **Tailor Blame Critiques (DO NOT Blindly Recycle Feedback)**:
  - Your blame explanation MUST explicitly reference the author's `# CHANGE:` attempt.
  - Explain why the attempted fix did not resolve the defect or what remains broken despite the attempt.
  - NEVER recycle identical blame critiques across verification rounds without examining what changed. Tailor your feedback to what remains unaddressed.
- **Actionable Attribution**: Blame the exact culprit file (`lib/*.py` or `tests/*_test.py`). If both implementation and tests are defective, blame each culprit file with specific critiques."""
    else:
        blame_step = ""
        if can_blame:
            blame_step = "5. If upstream contracts are defective: Deliver blame attribution via `bin/blame <culprit_contract> \"<explanation>\"`.\n"
            step_fail_num = "6"
            step_stop_num = "7"
        else:
            step_fail_num = "5"
            step_stop_num = "6"

        workflow = f"""1. Run `bin/get_work` to inspect and pull pending work and review any unacted feedback.
2. Follow companion guide `{guide}` to author or update targets in scope, resolving any feedback.
3. Run verification checks: `bin/check_files [target_file]`
4. If checks pass and all feedback is resolved: Submit completed targets via `bin/submit <target_file> "<summary>"` (or `bin/submit <target_file>` if unmodified).
{blame_step}{step_fail_num}. If success is impossible or an unresolvable impasse is reached: `bin/fail <target_file> "<reason>"`
{step_stop_num}. Call `bin/get_work` to inspect remaining units. If all ready targets are resolved or only blocked targets remain, STOP and conclude your round immediately without calling further tools.
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

    stub_section = ""
    if has_stubs:
        stub_section = """
## Cleanroom Compilation Stubs (DO NOT Edit or Assert Stub Errors)
Any library files under `lib/*.py` imported from role dependencies in this workspace are intentional Cleanroom compilation stubs (`CLEANROOM TEST STUB v4`).
- **Read-Only Stubs for Type-Checking**: These stubs exist solely to provide method signatures and symbols so that your code passes static type-checking and syntax verification via `bin/check_files`.
- **Stub Errors are Normal in This Workspace**: Stubs raise `NotImplementedError` when called because the actual implementation executes in downstream verification, NOT in this workspace.
- **DO NOT EDIT STUBS**: You are strictly prohibited from editing or attempting to implement `lib/*.py`.
- **DO NOT ASSERT STUB ERRORS**: Never write tests expecting or asserting `NotImplementedError` or stub error outcomes. Author tests that verify the real behavioral contracts, postconditions, and invariants specified in `low/*.pyi`.
"""

    if can_blame:
        resolution_rules = """- **ZERO TOLERANCE FOR COMPLAINING OR IDLING IN CHAT**: When `bin/check_files` fails, stopping with conversational commentary, explaining why output did not change, or complaining without executing `bin/blame` is STRICTLY PROHIBITED. Conversational complaints do not mutate build state, and upstream authoring roles cannot inspect chat transcripts.
- **Actionable Blame Delivery**: When checks fail due to defects in library code, test code, or upstream specifications, you MUST execute `bin/blame <culprit_file> "<actionable critique>"` immediately. Auditors can blame both the lib and test files if both contain defects.
- **Submission on Success**: When checks pass, you MUST execute `bin/submit <target_file>` immediately.
- **Fail on Impasse**: If you reach an unresolvable impasse where neither submit nor blame applies, execute `bin/fail <target_file> "<reason>"` immediately.
- **Never end a round while ready targets remain unresolved. When all ready targets are resolved or only blocked targets remain, conclude your round immediately without further tool calls.**"""
        resolution_methods = "(`bin/submit`, `bin/blame`, or `bin/fail`)"
        workflow_binaries_blame = "- `bin/blame` — Attribute blame and return defective targets to upstream roles.\n"
        round_res_line = "Never attempt to manually commit, push, or copy files across workspace boundaries; round resolution must always occur via `bin/submit`, `bin/blame`, or `bin/fail`."
        runner_tools_list = "`get_work`, `check_files`, `submit`, `blame`, `fail`"
        fail_stop_tools = "`bin/get_work`, `bin/check_files`, `bin/blame`, `bin/submit`, `bin/fail`"
        metadata_tools = "(`bin/submit`, `bin/blame`, `bin/fail`)"
        test_failure_action = "`bin/blame`, `bin/fail`, or code edits"
    else:
        resolution_rules = """- **Submission on Success**: When checks pass and all feedback is addressed, you MUST execute `bin/submit <target_file> "<summary>"` immediately.
- **Fail on Impasse**: If you reach an unresolvable impasse where success is impossible, execute `bin/fail <target_file> "<reason>"` immediately.
- **Never end a round while ready targets remain unresolved. When all ready targets are resolved or only blocked targets remain, conclude your round immediately without further tool calls.**"""
        resolution_methods = "(`bin/submit` or `bin/fail`)"
        workflow_binaries_blame = ""
        round_res_line = "Never attempt to manually commit, push, or copy files across workspace boundaries; round resolution must always occur via `bin/submit` or `bin/fail`."
        runner_tools_list = "`get_work`, `check_files`, `submit`, `fail`"
        fail_stop_tools = "`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/fail`"
        metadata_tools = "(`bin/submit` or `bin/fail`)"
        test_failure_action = "code edits or `bin/fail`"

    content = f"""# Cleanroom Role Instructions: {role_def.role_name.capitalize()}

## Scope & Constraints
- Role: `{role_def.role_name}`
- Directory Scope: `{dir_scope}`
- Companion Guide: `{guide}`
{stub_section}
## Continuous Tool Execution & Operational Rules
- **Continuous Tool Execution (No Idling or Dangling Colons)**: You are an autonomous agent step runner. You must ALWAYS invoke a tool in every step. Never output conversational text, explanations, or sentences ending in colons without invoking tools in the same step. Every step MUST execute a tool call.
- **Ground Truth First (Oracle Diagnostics Over Prose)**: Always run `bin/check_files <target>` to establish deterministic ground truth errors before writing or editing code. Do NOT speculate, guess, or infer defects from prose descriptions before checking oracle output.
- **Targeted Reads Over Full Dumps**: Never dump or read entire large files repeatedly. Use grep to locate symbols, or read narrow line ranges using offset and limit parameters.
- **Restricted Targets**: Edit ONLY your assigned target files. Do NOT create scratch tests, temporary test scripts, or auxiliary test runners.
- **No Runner Binary Inspection or Linter Hunting**: Runner executables in `bin/` ({runner_tools_list}) are encapsulated self-contained tools. Do NOT search for internal linters (`*_lint.py`, `test_lint`, `build_lint`), and do NOT attempt to read, disassemble, decompile, or run inspection utilities (`file`, `strings`, `unzip`, `head`, `od`, `xxd`) on `bin/` executables. All required structural rules and conventions are documented in your Companion Guide.
- **Standard Terminology**:
  - **Step**: A single prompt ↔ tool-call interaction cycle between an agent/model and the runtime.
  - **Round**: A full Cleanroom role dispatch wave or execution pass across assigned targets until submission, blame, or exhaustion.
{constrained_bullet}
## Mandatory Target Resolution (Do NOT End Round Without Resolving)
Every ready target acquired via `bin/get_work` MUST be explicitly resolved before concluding your round:
{resolution_rules}

## Round Conclusion Protocol
Once all ready targets have been resolved {resolution_methods}, or when `bin/get_work` indicates that only blocked targets remain (or no ready targets exist):
- **STOP IMMEDIATELY**: Do NOT execute any further tool calls.
- **DO NOT CALL `bin/get_work` OR `bin/check_files` IN A LOOP**: Repeatedly running tools when there are no ready targets wastes steps and triggers impasse warnings.
- **Conclude the Round**: Output a concise summary of the resolved actions and end your round.

## Strict Boundary Rules (Zero Exceptions)
1. **Workspace Boundary**: All commands and tool invocations MUST execute strictly within this workspace directory (`.`). You are strictly prohibited from passing any other directory as `Cwd` or running commands outside this workspace.
2. **Git Operations Prohibited**: This is a projected cleanroom workspace, not a git repository. Never invoke `git` commands (`git checkout`, `git restore`, `git reset`, etc.) under any circumstances.
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
You ARE permitted to run standard shell utilities and scripts (`cat`, `grep`, `find`, `python`, etc.) or native harness tools strictly WITHIN this workspace directory (`.`) to inspect files, run local diagnostics, and complete your tasks.
Git operations (`git checkout`, `git restore`, `git reset`, etc.) and accessing files outside this workspace remain strictly prohibited.

## Mandatory Cleanroom Workflow Binaries
All Cleanroom target resolution must proceed through the prescribed workspace binaries:
- `bin/get_work` — Discover pending units and tasks.
- `bin/check_files` — Run static verification, linting, and type checking on targets.
- `bin/submit` — Submit verified targets to main.
{workflow_binaries_blame}- `bin/fail` — Report an unresolvable impasse.

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
If any cleanroom binary ({fail_stop_tools}) fails due to:
- A Python exception or traceback (e.g., `ModuleNotFoundError`, `ImportError`, `AttributeError`)
- A build, type check, or test execution failure
- A missing support file, template error, or dependency issue

**STOP IMMEDIATELY.**
- **DO NOT** attempt to fix, patch, restore, or work around the infrastructure.
- **DO NOT** create, undelete, or check out missing files.
- **DO NOT** attempt alternate execution paths outside `bin/`.
- **REPORT IMMEDIATELY**: Output the exact command that failed and its verbatim error/traceback to the user, state what dependency or file appears to be missing, and wait for human instruction.

NOTE: Verification test failures (e.g. `[FAIL] Verification failed` or `[FAIL] Verification timed out` output from tests or linters on code under test) are NORMAL test results to be acted upon via {test_failure_action}, NOT infrastructure crashes. Timeouts, process hangs, and termination by SIGTERM during test verification indicate code defects (such as infinite loops, deadlocks, live-locks, or unresolvable dependencies in the code under test), NOT infrastructure failures. When `bin/check_files` times out or receives SIGTERM, do NOT fail-stop; diagnose the hanging method/loop and issue a blame against the culprit file. Fail-Stop applies ONLY to internal tool crashes, tracebacks, or missing tooling/dependencies.

## Unresolvable Impasse & Failure Protocol
If you determine that success is not possible (e.g. unreachable code under test, contradictory specification contracts, or dead ends that blame cannot resolve):
1. **DO NOT** attempt ad-hoc debugging, script execution, or reverse-engineering of cleanroom tools.
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
        package_runner_zipapps(bin_dir, can_blame=can_blame)

    # Contract: Writes role configuration metadata (.cleanroom_role.json) in workspace root.
    def write_role_metadata(
        self,
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        max_feedback_chars: Optional[int] = None,
    ) -> None:
        write_role_metadata(
            workspace_dir,
            role_name,
            dir_scope,
            repo_root=repo_root,
            model=model,
            batch_size=batch_size,
            max_feedback_chars=max_feedback_chars,
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
# LAST_CLEANED: 2026-10-26T12:40:00Z
# LAST_CHANGED: 2026-10-26T12:40:00Z
# CHANGE: Clarify in fail-stop protocol that test execution timeouts and SIGTERM are code defects rather than infrastructure failures
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
