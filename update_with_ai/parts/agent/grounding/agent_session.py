# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: d9f31c151c15
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

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
