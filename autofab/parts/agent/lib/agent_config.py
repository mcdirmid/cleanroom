from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier
from typing import NewType, Protocol

# Requirements specified in agent_config.pyi

ConversationLimit = NewType('ConversationLimit', int)

SupersedeArgKeepLimit = NewType('SupersedeArgKeepLimit', int)

class AgentConfig(Singleton[SystemTier], Protocol):
    # Contract: Bound on the model interaction turns permitted in an agent run.
    @property
    def conversation_limit(self) -> ConversationLimit:
        ...

    # Contract: Whether the agent executes follow-up tool calls specified by tool responses.
    @property
    def inject_followups(self) -> bool:
        ...

    # Contract: Whether the agent receives a guide progressively in step mode.
    @property
    def is_step_mode(self) -> bool:
        ...

    # Contract: Whether the agent inspects declared files at session start.
    @property
    def is_startup_reads(self) -> bool:
        ...

    # Contract: Whether editing tools report changes made rather than complete file content.
    @property
    def edit_delta_output(self) -> bool:
        ...

    # Contract: Bound on trailing characters of a superseded string argument retained as a recognizable hint.
    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:24Z
# CHANGE: Remove generated scaffold markers so every declared configuration property is a clean protocol stub
# --- END CLEANROOM METADATA ---
