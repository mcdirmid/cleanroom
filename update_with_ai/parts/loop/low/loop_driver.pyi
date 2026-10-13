# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-11T03:19:48Z
# CHANGE: Align loop driver turn, correlation, reminder, and termination contracts
# CODE_HASH: d64f6418d1e5
# SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
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
    """Coordinates the turn loop, model request dispatch, and tool execution for an agent session."""

    @operation
    def run(self) -> LoopOutcome:
        """Drives iterative turns until tool termination or conversation limit exhaustion.

        Returns:
            The loop outcome record carrying the termination outcome and the final conversation state.

        POSTCONDITIONS:
        - MUST drive turns by sending model requests and executing requested tools.
        - MUST append model responses and correlate tool responses with their originating tool call identifiers.
        - MUST dispatch follow-up tool calls specified by tool responses.
        - MUST record follow-up executions in the conversation.
        - MUST evaluate tool executions for consecutive repetition.
        - WHEN repetition is detected, MUST inject loop reminders into the conversation.
        - WHEN a model response contains no tool executions, MUST inject a tool reminder into the conversation stating that session progress and conclusion require executing tools.
        - WHEN a model response contains no tool executions, MUST continue the turn loop.
        - WHEN tool execution produces a termination outcome, MUST conclude atomically and produce a loop outcome carrying the final conversation state.
        - WHEN the termination outcome indicates a failing outcome, MUST halt with an unexpected failure.
        - WHEN consecutive repetitions reach the fatal threshold, MUST halt with an unexpected failure.
        - WHEN the conversation limit is exceeded, MUST halt with an unexpected failure.
        """
        ...
