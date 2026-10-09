# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:18:04Z
# CHANGE: Align with agent_session.pyi specification
# CODE_HASH: 1e6f3e698d6b
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from support.lib.lifecycle import LifecycleTier, system

# Requirements specified in agent_session.pyi

agent_session: LifecycleTier = system.create_child('agent_session')
AgentSessionTier = LifecycleTier
