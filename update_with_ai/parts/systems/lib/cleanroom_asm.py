# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-08T12:55:00Z
# CHANGE: assemble workspace_tool_impl
# CODE_HASH: d80adba04d79
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import bazel_openai_loop_asm
from update_with_ai.parts.control.lib import control_asm
from update_with_ai.parts.core.lib import file_paths_impl
from update_with_ai.parts.tools.lib import tools_asm
from update_with_ai.parts.workspace.lib import workspace_asm
from update_with_ai.parts.workspace.lib import workspace_tool_impl

CONSTITUENTS = (
    bazel_openai_loop_asm,
    control_asm,
    file_paths_impl,
    tools_asm,
    workspace_asm,
    workspace_tool_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
