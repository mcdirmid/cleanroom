# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 756b563fbcfb
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Loop driver low-level interface specification."""

from dataclasses import dataclass
from typing import Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import loop_conversation
import tool_provider


@dataclass(frozen=True)
@data_type
class LoopOutcome:
    """Final result of an agent run carrying termination outcome and conversation state.

    Args:
        response: Termination response produced by tool execution.
        conversation: Final model request representing conversation state.
    """
    response: tool_provider.ToolResponse
    conversation: loop_conversation.ModelRequest


@singleton_type("agent_session")
class LoopDriver(InTier[AgentSessionTier], Protocol):
    """Coordinates turn loops, tool dispatches, and audit telemetry for an agent session."""

    @operation
    def run(self) -> LoopOutcome:
        """Drives iterative turns until tool termination or turn limit exhaustion.

        Returns:
            The loop outcome record.

        POSTCONDITIONS:
        - MUST drive turns by sending model requests and executing requested tools.
        - MUST append model responses and correlate tool responses in conversation.
        - MUST dispatch follow-up tool calls specified by tool responses.
        - MUST record log events for interaction turns, tool executions, and turn outcomes.
        - WHEN tool execution produces a termination outcome, MUST produce a loop outcome.
        - WHEN consecutive repetitions reach the fatal threshold, MUST halt with an unexpected failure.
        - WHEN the conversation turn limit is exceeded, MUST halt with an unexpected failure.
        """
        ...
