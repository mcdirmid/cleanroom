#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents."""
from __future__ import annotations
import importlib
import json
import os
import sys


def _get_dir_scope() -> str:
    curr = os.path.dirname(os.path.realpath(__file__))
    while curr and curr != os.path.dirname(curr):
        cfg = os.path.join(curr, ".cleanroom_role.json")
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    return str(json.load(f).get("dir_scope", "") or "")
            except Exception:
                pass
            break
        curr = os.path.dirname(curr)
    return ""


def _get_roots() -> list[str]:
    roots, curr = [], os.path.dirname(os.path.realpath(__file__))
    while curr and curr != os.path.dirname(curr):
        cfg = os.path.join(curr, ".cleanroom_role.json")
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    m = json.load(f).get("main_workspace_root")
                if m and os.path.isdir(m):
                    roots.append(m)
            except Exception:
                pass
            roots.append(curr)
            break
        if os.path.isfile(os.path.join(curr, "pyproject.toml")) or os.path.isfile(os.path.join(curr, "MODULE.bazel")):
            roots.append(curr)
            break
        curr = os.path.dirname(curr)
    return roots or [os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../.."))]


_dir_scope = _get_dir_scope()
for _r in _get_roots():
    if os.path.isdir(_r) and _r not in sys.path:
        sys.path.insert(0, _r)
    try:
        for _entry in os.listdir(_r):
            if _dir_scope and _entry == _dir_scope:
                continue
            _pkg_dir = os.path.join(_r, _entry)
            if os.path.isdir(_pkg_dir) and not _entry.startswith((".", "bazel-", "venv")):
                _sup_lib = os.path.join(_pkg_dir, "support", "lib")
                if os.path.isdir(_sup_lib):
                    if _pkg_dir not in sys.path:
                        sys.path.insert(0, _pkg_dir)
                    if _sup_lib not in sys.path:
                        sys.path.insert(0, _sup_lib)
    except OSError:
        pass

workspace_tool_impl = None
for _r in _get_roots():
    if not os.path.isdir(_r):
        continue
    try:
        for _entry in os.listdir(_r):
            if _dir_scope and _entry == _dir_scope:
                continue
            if not _entry.startswith((".", "bazel-", "venv")):
                _cand_tool = os.path.join(_r, _entry, "parts", "workspace", "lib", "workspace_tool_impl.py")
                if os.path.isfile(_cand_tool) and os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                    try:
                        workspace_tool_impl = importlib.import_module(f"{_entry}.parts.workspace.lib.workspace_tool_impl")
                        break
                    except ImportError:
                        pass
    except OSError:
        pass
    if workspace_tool_impl is not None:
        break

if workspace_tool_impl is None:
    try:
        from parts.workspace.lib import workspace_tool_impl
    except ImportError:
        pass

if workspace_tool_impl is None:
    raise ImportError("Failed to locate workspace_tool_impl module across discovered Cleanroom roots")

AUDIT_BUFFER_FILE = workspace_tool_impl.AUDIT_BUFFER_FILE
BLAME_BUFFER_FILE = workspace_tool_impl.BLAME_BUFFER_FILE
PENDING_WORK_FILE = workspace_tool_impl.PENDING_WORK_FILE
write_file_with_perms = workspace_tool_impl.write_file_with_perms
copy_file_with_perms = workspace_tool_impl.copy_file_with_perms
compute_role_work_queue = workspace_tool_impl.compute_role_work_queue
get_pending_work = workspace_tool_impl.get_pending_work
set_pending_work = workspace_tool_impl.set_pending_work
clear_pending_work = workspace_tool_impl.clear_pending_work
remove_pending_target = workspace_tool_impl.remove_pending_target
is_pending_target_dirty = workspace_tool_impl.is_pending_target_dirty
find_workspace_root = workspace_tool_impl.find_workspace_root
get_current_role_metadata = workspace_tool_impl.get_current_role_metadata
is_auditor_role = workspace_tool_impl.is_auditor_role
resolve_cleanroom_log_path = workspace_tool_impl.resolve_cleanroom_log_path
append_cleanroom_log = workspace_tool_impl.append_cleanroom_log


def main(argv: list[str] | None = None) -> int:
    asm_modules = (
        "parts.systems.lib.cleanroom_asm",
        "parts.systems.lib.uv_cleanroom_asm",
        "parts.core.lib.file_paths_impl",
        "parts.control.lib.control_asm",
        "parts.tools.lib.tools_asm",
        "parts.workspace.lib.workspace_asm",
        "parts.workspace.lib.workspace_tool_impl",
    )
    for mod_name in asm_modules:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "__initialize__"):
                mod.__initialize__()
        except (ImportError, AttributeError):
            pass

    for _r in _get_roots():
        if not os.path.isdir(_r):
            continue
        try:
            for _entry in os.listdir(_r):
                if _dir_scope and _entry == _dir_scope:
                    continue
                if not _entry.startswith((".", "bazel-", "venv")):
                    if os.path.isdir(os.path.join(_r, _entry, "support", "lib")):
                        for sub in (
                            "systems.lib.cleanroom_asm",
                            "systems.lib.uv_cleanroom_asm",
                            "core.lib.file_paths_impl",
                            "control.lib.control_asm",
                            "tools.lib.tools_asm",
                            "workspace.lib.workspace_asm",
                            "workspace.lib.workspace_tool_impl",
                        ):
                            try:
                                mod = importlib.import_module(f"{_entry}.parts.{sub}")
                                if hasattr(mod, "__initialize__"):
                                    mod.__initialize__()
                            except (ImportError, AttributeError):
                                pass
        except OSError:
            pass

    assert workspace_tool_impl is not None
    return workspace_tool_impl.main(argv)


if __name__ == "__main__":
    sys.exit(main())
