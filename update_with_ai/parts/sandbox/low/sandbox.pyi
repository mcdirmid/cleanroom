"""Sandbox low-level interface specification."""

from typing import Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@singleton_type("agent_session")
class Sandbox(InTier[AgentSessionTier], Protocol):
    """Coordinates session template materialization and file modification tracking."""

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        POSTCONDITIONS:
        - MUST return whether workspace file modifications occurred during the session.
        """
        ...

    @operation
    def materialize_templates(self) -> None:
        """Materializes startup templates into missing read-write files.

        POSTCONDITIONS:
        - MUST materialize startup templates into missing read-write files without overwriting existing files.
        """
        ...
