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
