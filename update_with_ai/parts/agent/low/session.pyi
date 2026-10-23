"""Agent session lifecycle tier component."""

from support.lib.framework import singleton_type
from support.lib.lifecycle import ChildTierOf, LifecycleTier, SystemTier


@singleton_type("system")
class AgentSessionTier(ChildTierOf[SystemTier]):
    """Lifecycle tier bounding the execution, conversation, and ephemeral state of an agent under the system lifecycle tier."""
    ...


agent_session: LifecycleTier
session: LifecycleTier


def __orphan__() -> None:
    """Orphan contracts for agent session tier instances.

    POSTCONDITIONS:
    - MUST provide agent_session and session as LifecycleTier child tiers of the system lifecycle tier.
    """
    ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:06:35Z
# CHANGE: Align agent session tier with the simplified agent definition and system tier relationship
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
