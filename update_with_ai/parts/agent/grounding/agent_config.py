# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: c97e7918baa2
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Agent config grounding specification module."""

from __future__ import annotations
from typing import NewType, Protocol
from support.lib.grounding_support import InTier, SystemTier

ConversationLimit = NewType("ConversationLimit", int)
SupersedeArgKeepLimit = NewType("SupersedeArgKeepLimit", int)


class AgentConfig(InTier[SystemTier], Protocol):
    """Provides execution parameters for agent sessions."""

    @property
    def conversation_limit(self) -> ConversationLimit:
        """
        DEFERRED:
        - Bound on the maximum number of model interaction turns.
        """
        raise NotImplementedError

    @property
    def inject_followups(self) -> bool:
        """
        DEFERRED:
        - Indicates whether the agent should inject followups to execute follow-up tool calls.
        """
        raise NotImplementedError

    @property
    def is_step_mode(self) -> bool:
        """
        DEFERRED:
        - Indicates whether the agent should use step mode to communicate a guide progressively.
        """
        raise NotImplementedError

    @property
    def is_startup_reads(self) -> bool:
        """
        DEFERRED:
        - Indicates whether the agent should perform startup reads to read declared files.
        """
        raise NotImplementedError

    @property
    def edit_delta_output(self) -> bool:
        """
        DEFERRED:
        - Indicates whether editing tools should produce delta output.
        """
        raise NotImplementedError

    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit:
        """
        DEFERRED:
        - Trailing character retention limit for string arguments on superseded tool calls.
        """
        raise NotImplementedError
