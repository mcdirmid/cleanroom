from __future__ import annotations
from typing import Optional
from .lifecycle import LifecycleRegistry
from . import agent_conversation_history_impl
from . import agent_loop_guard_impl
from . import agent_node_cleaner_impl
from . import agent_runner_impl

CONSTITUENTS = (
    agent_runner_impl,
    agent_conversation_history_impl,
    agent_loop_guard_impl,
    agent_node_cleaner_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
