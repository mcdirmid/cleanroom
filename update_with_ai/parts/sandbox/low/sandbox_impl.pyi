"""Sandbox implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import sandbox


@singleton_type("agent_session")
class Sandbox(sandbox.Sandbox, InTier[AgentSessionTier]):
    """Realizes session template materialization and file modification tracking."""

    @property
    @override
    def has_modifications(self) -> bool:
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        ...
