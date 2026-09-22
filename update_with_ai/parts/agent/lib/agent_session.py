# Requirements specified in agent_session.pyi

from support.lib.lifecycle import LifecycleTier, system

agent_session: LifecycleTier = system.create_child("agent_session")

