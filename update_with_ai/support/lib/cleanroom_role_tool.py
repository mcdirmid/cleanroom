#!/usr/bin/env python3
"""cleanroom_role_tool.py — Role-workspace internal CLI tool for Cleanroom subagents."""
from __future__ import annotations
import json, os, sys

def _get_roots() -> list[str]:
    roots, curr = [], os.path.dirname(os.path.realpath(__file__))
    while curr and curr != os.path.dirname(curr):
        cfg = os.path.join(curr, ".cleanroom_role.json")
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    m = json.load(f).get("main_workspace_root")
                if m and os.path.isdir(m): roots.append(m)
            except Exception: pass
            roots.append(curr); break
        if os.path.isfile(os.path.join(curr, "MODULE.bazel")):
            roots.append(curr); break
        curr = os.path.dirname(curr)
    return roots or [os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../.."))]

for _r in _get_roots():
    for _p in [_r, os.path.join(_r, "update_python_with_ai"), os.path.join(_r, "update_with_ai"), os.path.join(_r, "update_with_ai/support/lib"), os.path.join(_r, "update_python_with_ai/support/lib")]:
        if os.path.isdir(_p) and _p not in sys.path: sys.path.insert(0, _p)

from update_with_ai.parts.workspace.lib import workspace_tool_impl

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
main = workspace_tool_impl.main

if __name__ == "__main__":
    sys.exit(main())
