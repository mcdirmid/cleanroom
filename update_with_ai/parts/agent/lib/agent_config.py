# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:17:58Z
# CHANGE: Align with agent_config.pyi specification
# CODE_HASH: 256a43d5c70d
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol

# Requirements specified in agent_config.pyi

ConversationLimit = NewType('ConversationLimit', int)

SupersedeArgKeepLimit = NewType('SupersedeArgKeepLimit', int)

class AgentConfig(Protocol):
    @property
    def conversation_limit(self) -> ConversationLimit:
        # TODO_conversation_limit_body
        ...

    @property
    def inject_followups(self) -> bool:
        # TODO_inject_followups_body
        ...

    @property
    def is_step_mode(self) -> bool:
        # TODO_is_step_mode_body
        ...

    @property
    def is_startup_reads(self) -> bool:
        # TODO_is_startup_reads_body
        ...

    @property
    def edit_delta_output(self) -> bool:
        # TODO_edit_delta_output_body
        ...

    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit:
        # TODO_supersede_arg_keep_body
        ...
