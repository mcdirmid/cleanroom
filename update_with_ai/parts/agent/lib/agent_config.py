# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:24Z
# CHANGE: Remove generated scaffold markers so every declared configuration property is a clean protocol stub
# CODE_HASH: bbf111dbbbfc
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol

# Requirements specified in agent_config.pyi

ConversationLimit = NewType('ConversationLimit', int)

SupersedeArgKeepLimit = NewType('SupersedeArgKeepLimit', int)

class AgentConfig(Protocol):
    @property
    def conversation_limit(self) -> ConversationLimit:
        ...

    @property
    def inject_followups(self) -> bool:
        ...

    @property
    def is_step_mode(self) -> bool:
        ...

    @property
    def is_startup_reads(self) -> bool:
        ...

    @property
    def edit_delta_output(self) -> bool:
        ...

    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit:
        ...
