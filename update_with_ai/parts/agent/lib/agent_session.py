# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T04:59:27Z
# CHANGE: Declare the agent session tier as a real child tier type of the system tier while retaining the runtime agent_session tier constant used across the workspace
# CODE_HASH: e9e42491ed90
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from support.lib.lifecycle import ChildTierOf, LifecycleTier, SystemTier, system

# Requirements specified in agent_session.pyi


class AgentSessionTier(ChildTierOf[SystemTier]):
    """Lifecycle tier bounding the execution, conversation, and ephemeral state of an agent under the system lifecycle tier."""


# Runtime instance of the AgentSessionTier tier; the single runtime value an
# interface component may define (see support/lib/lifecycle.pyi).
agent_session: LifecycleTier = system.create_child('agent_session')
