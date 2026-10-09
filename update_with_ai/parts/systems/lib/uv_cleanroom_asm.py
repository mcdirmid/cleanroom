# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T12:55:00Z
# LAST_CHANGED: 2026-10-08T12:55:00Z
# CHANGE: assemble workspace_tool_impl
# CODE_HASH: 982696b1fe1a
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.control.lib import control_asm
from update_with_ai.parts.dag.lib import dag_asm
from update_with_ai.parts.core.lib import file_paths_impl
from update_with_ai.parts.loop.lib import loop_asm
from update_with_ai.parts.core.lib import runner_logger_impl
from update_with_ai.parts.sandbox.lib import sandbox_asm
from update_with_ai.parts.tools.lib import tools_asm
from update_with_ai.parts.uv.lib import uv_asm
from update_with_ai.parts.uv.lib import uv_loop_impl
from update_with_ai.parts.uv.lib import uv_model_config_impl
from . import uv_openai_loop_asm
from update_with_ai.parts.workspace.lib import workspace_asm
from update_with_ai.parts.workspace.lib import workspace_tool_impl

CONSTITUENTS = (
    control_asm,
    dag_asm,
    file_paths_impl,
    loop_asm,
    runner_logger_impl,
    sandbox_asm,
    tools_asm,
    uv_asm,
    uv_loop_impl,
    uv_model_config_impl,
    uv_openai_loop_asm,
    workspace_asm,
    workspace_tool_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
