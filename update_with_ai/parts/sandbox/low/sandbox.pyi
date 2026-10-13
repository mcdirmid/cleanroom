# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-11T03:21:33Z
# CHANGE: Drop stale operation content and redundant modification postcondition
# CODE_HASH: 66282bd5d6ce
# SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
# --- END CLEANROOM METADATA ---

"""Sandbox low-level interface specification."""

from typing import Protocol
from framework import singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@singleton_type("agent_session")
class Sandbox(InTier[AgentSessionTier], Protocol):
    """Coordinates session file modification tracking."""

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session."""
        ...
