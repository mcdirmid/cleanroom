# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: e9730c5200ba
# --- END CLEANROOM METADATA ---

"""Agent config interface component."""

from typing import NewType, Protocol
from framework import singleton_type
from support.lib.lifecycle import InTier, SystemTier

ConversationLimit = NewType("ConversationLimit", int)
SupersedeArgKeepLimit = NewType("SupersedeArgKeepLimit", int)


@singleton_type("system")
class AgentConfig(InTier[SystemTier], Protocol):
    """Provides execution parameters for agent sessions."""

    @property
    def conversation_limit(self) -> ConversationLimit:
        """Bound on the maximum number of model interaction turns."""
        ...

    @property
    def inject_followups(self) -> bool:
        """Indicates whether the agent should inject followups to execute follow-up tool calls."""
        ...

    @property
    def is_step_mode(self) -> bool:
        """Indicates whether the agent should use step mode to communicate a guide progressively."""
        ...

    @property
    def is_startup_reads(self) -> bool:
        """Indicates whether the agent should perform startup reads to read declared files."""
        ...

    @property
    def edit_delta_output(self) -> bool:
        """Indicates whether editing tools should produce delta output."""
        ...

    @property
    def is_mcp_mode(self) -> bool:
        """Indicates whether the agent should operate in mcp mode."""
        ...

    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit:
        """Trailing character retention limit for string arguments on superseded tool calls."""
        ...
