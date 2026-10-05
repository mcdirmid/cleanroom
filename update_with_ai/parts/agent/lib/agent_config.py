# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: d12610b660ec
# --- END CLEANROOM METADATA ---

# Requirements specified in agent_config.pyi
"""Agent configuration interface and data types."""

from typing import NewType, Protocol

ConversationLimit = NewType("ConversationLimit", int)
SupersedeArgKeepLimit = NewType("SupersedeArgKeepLimit", int)


class AgentConfig(Protocol):
    @property
    def conversation_limit(self) -> ConversationLimit: ...

    @property
    def inject_followups(self) -> bool: ...

    @property
    def is_step_mode(self) -> bool: ...

    @property
    def is_startup_reads(self) -> bool: ...

    @property
    def edit_delta_output(self) -> bool: ...

    @property
    def is_mcp_mode(self) -> bool: ...

    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit: ...
