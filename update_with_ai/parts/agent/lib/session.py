from __future__ import annotations
from support.lib.lifecycle import ChildTierOf, LifecycleTier, SystemTier, system

# Contract: Lifecycle tier bounding execution, conversation, and ephemeral state of an agent under the system lifecycle tier.
class AgentSessionTier(ChildTierOf[SystemTier]):
    """Lifecycle tier bounding the execution, conversation, and ephemeral state of an agent under the system lifecycle tier."""


# Contract: __orphan__ - MUST provide agent_session and session as LifecycleTier child tiers of the system lifecycle tier.
agent_session: LifecycleTier = system.create_child('agent_session')
session = agent_session

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:27Z
# CHANGE: Declare the agent session tier as a real child tier type of the system tier while retaining the runtime agent_session tier constant used across the workspace
# --- END CLEANROOM METADATA ---
