from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
from dataclasses import dataclass
from typing import Protocol
from . import conversation
from update_with_ai.parts.sandbox.lib import tool_provider


# Contract: LoopOutcome represents the final result of an agent run carrying termination outcome and conversation state.
@dataclass(frozen=True)
class LoopOutcome:
    response: tool_provider.ToolResponse
    conversation: conversation.ModelRequest


# Contract: LoopDriver coordinates the turn loop, model request dispatch, and tool execution for an agent session.
class LoopDriver(Singleton[AgentSessionTier], Protocol):
    # Contract: LoopDriver.run - drives iterative turns until tool termination or conversation limit exhaustion.
    def run(self) -> LoopOutcome: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
