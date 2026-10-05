# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 8fedda791a4c
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox grounding specification module."""

from __future__ import annotations
from typing import Protocol
from support.lib.grounding_support import InTier, AgentSessionTier


class Sandbox(InTier[AgentSessionTier], Protocol):
    """Coordinates session template materialization and file modification tracking."""

    @property
    def has_modifications(self) -> bool:
        """
        DEFERRED:
        - MUST return whether workspace file modifications occurred during the session.
        """
        raise NotImplementedError

    def materialize_templates(self) -> None:
        """
        DEFERRED:
        - MUST materialize startup templates into missing read-write files without overwriting existing files.
        - Deferred to sandbox_impl.py.
        """
        raise NotImplementedError
