from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import cleanroom_mcp_runner_impl
from update_with_ai.parts.bazel.lib import bazel_asm
from update_with_ai.parts.dag.lib import dag_asm
from update_with_ai.parts.mcp.lib import mcp_asm
from update_with_ai.parts.core.lib import runner_logger_impl
from update_with_ai.parts.sandbox.lib import sandbox_asm

CONSTITUENTS = (
    bazel_asm,
    cleanroom_mcp_runner_impl,
    dag_asm,
    mcp_asm,
    runner_logger_impl,
    sandbox_asm,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
