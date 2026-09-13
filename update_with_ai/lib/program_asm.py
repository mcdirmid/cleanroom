from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import agent_asm
from . import bazel_asm
from . import dag_asm
from . import runner_logger_impl
from . import sandbox_asm

CONSTITUENTS = (
    agent_asm,
    bazel_asm,
    dag_asm,
    runner_logger_impl,
    sandbox_asm,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
