# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:19:06Z
# CHANGE: Fix bare import of agent_session
# CODE_HASH: f5de62c66d78
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Protocol
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier

# Requirements specified in sandbox.pyi

class Sandbox(Protocol):
    @property
    def has_modifications(self) -> bool:
        # TODO_has_modifications_body
        ...
