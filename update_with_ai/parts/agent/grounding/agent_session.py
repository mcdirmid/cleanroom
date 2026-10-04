"""Agent session lifecycle grounding component."""

from __future__ import annotations
from support.lib.grounding_support import (
    AgentSessionTier as SupportAgentSessionTier,
    InTier,
    SystemTier,
)


class AgentSessionTier(SupportAgentSessionTier):
    """Lifecycle tier governing per-session agent execution subordinate to the system tier.

    COVERED:
    - The agent session lifecycle tier is defined under the system lifecycle tier.
      - Capability knowledge: InTier[AgentSessionTier] permits resolving SystemTier singletons in grounding proofs.
    """
    pass


__all__ = [
    "AgentSessionTier",
    "InTier",
    "SystemTier",
]
