from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import agent_loop_guard_impl
from . import agent_node_cleaner_impl
from update_with_ai.parts.openai.lib import openai_conversation_impl
from update_with_ai.parts.openai.lib import openai_driver_impl

CONSTITUENTS = (
    agent_loop_guard_impl,
    agent_node_cleaner_impl,
    openai_conversation_impl,
    openai_driver_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
