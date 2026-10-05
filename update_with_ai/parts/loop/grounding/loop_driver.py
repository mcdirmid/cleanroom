# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: af95b66ab590
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Loop driver grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from support.lib.grounding_support import InTier, AgentSessionTier
from parts.loop.grounding import loop_conversation
from parts.sandbox.grounding import tool_provider


@dataclass(frozen=True)
class LoopOutcome:
    """Final result of an agent run carrying termination outcome and conversation state.

    COVERED:
    - Encapsulates response tool response and conversation model request.
    """

    response: tool_provider.ToolResponse
    conversation: loop_conversation.ModelRequest


class LoopDriver(InTier[AgentSessionTier], Protocol):
    """Coordinates turn loops, tool dispatches, and audit telemetry for an agent session."""

    def run(self) -> LoopOutcome:
        """
        COVERED:
        - MUST produce a loop outcome upon termination.
          - Consequent knowledge: construct LoopOutcome record.

        DEFERRED:
        - MUST drive turns by sending model requests and executing requested tools.
        - MUST append model responses and correlate tool responses in conversation.
        - MUST dispatch follow-up tool calls specified by tool responses.
        - MUST record log events for interaction turns, tool executions, and turn outcomes.
        - WHEN tool execution produces a termination outcome, MUST produce a loop outcome.
        - WHEN consecutive repetitions reach the fatal threshold, MUST halt with an unexpected failure.
        - WHEN the conversation turn limit is exceeded, MUST halt with an unexpected failure.
          - Deferred to refining implementation in openai_driver_impl.py.
        """
        sample_response = tool_provider.ToolResponse(
            content="Done",
            is_failed=False,
            is_terminated=True,
        )
        sample_request = loop_conversation.ModelRequest(messages=[])
        _outcome = LoopOutcome(response=sample_response, conversation=sample_request)
        raise NotImplementedError
