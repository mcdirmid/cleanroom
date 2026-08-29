"""
lib/agent_loop_asm.py

Assembly of the AgentLoop component.

Wires ConversationHistoryImpl and LoopGuardImpl into AgentLoopImpl.
"""

from __future__ import annotations

from .agent_loop_config import AgentLoopConfig
from .agent_loop_impl import AgentLoopImpl
from .conversation_history_impl import ConversationHistoryImpl
from .loop_guard_impl import LoopGuardImpl


class AgentLoopAsm(AgentLoopImpl):
    """
    Assembles concrete subcomponents into AgentLoopImpl (configuration and assembly only).
    """

    def __init__(self, config: AgentLoopConfig) -> None:
        super().__init__(
            config=config,
            conversation_history=ConversationHistoryImpl(),
            loop_guard=LoopGuardImpl(config=config),
        )
