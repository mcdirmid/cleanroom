# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-08T12:55:00Z
# CHANGE: assemble workspace_tool_impl
# CODE_HASH: d68b72022dad
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.control.lib import control_asm
from update_with_ai.parts.core.lib import file_paths_impl
from update_with_ai.parts.storage.lib import storage_asm
from update_with_ai.parts.tools.lib import tools_asm
from . import uv_openai_loop_asm
from update_with_ai.parts.workspace.lib import workspace_asm

CONSTITUENTS = (
    control_asm,
    file_paths_impl,
    storage_asm,
    tools_asm,
    uv_openai_loop_asm,
    workspace_asm,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
