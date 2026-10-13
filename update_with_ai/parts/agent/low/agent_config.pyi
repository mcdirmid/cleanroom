# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:15Z
# LAST_CHANGED: 2026-10-11T03:06:34Z
# CHANGE: Align agent config typing with canonical policy properties and supersede arg keep resolution
# CODE_HASH: c3e2e7ea39f7
# SPEC_QA_AUDIT: 2026-10-13T20:42:15Z
# --- END CLEANROOM METADATA ---

"""Agent config interface component."""

from typing import NewType, Protocol
from framework import singleton_type
from support.lib.lifecycle import InTier, SystemTier

ConversationLimit = NewType("ConversationLimit", int)
SupersedeArgKeepLimit = NewType("SupersedeArgKeepLimit", int)


@singleton_type("system")
class AgentConfig(InTier[SystemTier], Protocol):
    """Provides system-level execution parameters for agent sessions governing conversation depth and tool behaviors."""

    @property
    def conversation_limit(self) -> ConversationLimit:
        """Bound on the model interaction turns permitted in an agent run."""
        ...

    @property
    def inject_followups(self) -> bool:
        """Whether the agent executes the follow-up tool calls that tool responses specify."""
        ...

    @property
    def is_step_mode(self) -> bool:
        """Whether the agent receives a guide progressively in step mode."""
        ...

    @property
    def is_startup_reads(self) -> bool:
        """Whether the agent inspects declared files at session start."""
        ...

    @property
    def edit_delta_output(self) -> bool:
        """Whether editing tools report the changes they make rather than complete file content."""
        ...

    @property
    def supersede_arg_keep(self) -> SupersedeArgKeepLimit:
        """Bound on the trailing characters of a superseded string argument retained as a recognizable hint, resolved from the agent session configuration."""
        ...
