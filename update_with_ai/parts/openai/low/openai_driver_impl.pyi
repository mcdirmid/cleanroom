# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 82f8ca4b0009
# --- END CLEANROOM METADATA ---

"""OpenAI driver implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import loop_driver


@singleton_type("agent_session")
class LoopDriver(
    loop_driver.LoopDriver, InTier[AgentSessionTier]
):
    """Realizes language model completion requests, tool dispatch, output continuation, and termination handling."""

    @operation
    @override
    def run(self) -> loop_driver.LoopOutcome:
        """Drives iterative turns using OpenAI completion requests.

        Returns:
            The final loop outcome.

        POSTCONDITIONS:
        - MUST transmit completion requests following OpenAI conventions with model parameters from configuration.
        - MUST order tools and parameters deterministically.
        - WHEN a model response is truncated, MUST recover by repairing partial replace file content payloads with indented sentinels or terminate with failure responses before resuming generation.
        - WHEN a model completion response fails with an incomplete tool call error, MUST append an actionable recovery notice directing smaller edits and continue the turn loop or halt upon repeated failures.
        - MUST stream turn events and summaries to runner logger.
        - WHEN loop guard produces a loop reminder, MUST append reminder to the conversation.
        - WHEN loop guard produces loop failure, MUST halt with an unexpected failure.
        - WHEN tool execution produces a non-terminating failure response, MUST append failure feedback to the conversation.
        - WHEN a model response produces no tool executions, MUST append a prompt reminding that progress requires invoking tools.
        - WHEN tool responses specify followups, MUST execute designated tool calls.
        """
        ...
