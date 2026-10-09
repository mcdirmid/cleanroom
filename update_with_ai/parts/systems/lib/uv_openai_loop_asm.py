from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.dag.lib import dag_asm
from update_with_ai.parts.loop.lib import loop_asm
from update_with_ai.parts.core.lib import runner_logger_impl
from update_with_ai.parts.sandbox.lib import sandbox_asm
from update_with_ai.parts.uv.lib import uv_asm
from update_with_ai.parts.uv.lib import uv_loop_impl
from update_with_ai.parts.uv.lib import uv_model_config_impl

CONSTITUENTS = (
    dag_asm,
    loop_asm,
    runner_logger_impl,
    sandbox_asm,
    uv_asm,
    uv_loop_impl,
    uv_model_config_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
