# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T05:44:58Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 30e55d74c5f1
# --- END CLEANROOM METADATA ---

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
