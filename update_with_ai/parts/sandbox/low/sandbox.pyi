# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: bb099a7d2bf3
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox low-level interface specification."""

from typing import Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@singleton_type("agent_session")
class Sandbox(InTier[AgentSessionTier], Protocol):
    """Coordinates session file modification tracking."""

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        POSTCONDITIONS:
        - MUST return whether workspace file modifications occurred during the session.
        """
        ...
