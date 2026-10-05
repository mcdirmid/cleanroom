# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 721022d94d57
# --- END CLEANROOM METADATA ---

# Requirements specified in agent_session.pyi

from support.lib.lifecycle import ChildTierOf, LifecycleTier, SystemTier, system


class AgentSessionTier(ChildTierOf[SystemTier]):
    def __init__(self, name: str = "agent_session") -> None:
        super().__init__(name=name, parent=system)


agent_session: AgentSessionTier = AgentSessionTier()
