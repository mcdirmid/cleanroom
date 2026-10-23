from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.dag.lib import dag_asm
from update_with_ai.parts.loop.lib import loop_asm
from update_with_ai.parts.openai.lib import conversation_impl
from update_with_ai.parts.openai.lib import driver_impl
from update_with_ai.parts.loop.lib import logger_impl
from update_with_ai.parts.sandbox.lib import sandbox_asm
from update_with_ai.parts.uv.lib import uv_asm
from update_with_ai.parts.uv.lib import loop_impl
from update_with_ai.parts.uv.lib import model_config_impl

# Contract: Declared constituents forming the complete Cleanroom UV OpenAI loop root system assembly.
CONSTITUENTS = (
    dag_asm,
    loop_asm,
    conversation_impl,
    driver_impl,
    logger_impl,
    sandbox_asm,
    uv_asm,
    loop_impl,
    model_config_impl,
)


# Contract: Aggregates declared constituents into the complete Cleanroom UV OpenAI loop root system assembly.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T21:19:01Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
