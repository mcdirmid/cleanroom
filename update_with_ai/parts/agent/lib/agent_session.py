# Requirements specified in agent_session.pyi

from support.lib.lifecycle import ChildTierOf, LifecycleTier, SystemTier, system


class AgentSessionTier(ChildTierOf[SystemTier]):
    def __init__(self, name: str = "agent_session") -> None:
        super().__init__(name=name, parent=system)


agent_session: AgentSessionTier = AgentSessionTier()
