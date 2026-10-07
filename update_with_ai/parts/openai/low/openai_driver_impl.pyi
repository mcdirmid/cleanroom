# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: 0917cf702a1f
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
    """Realizes language model completion requests, tool dispatch, output continuation, and termination handling.

    GROUNDING:
    - Realizes iterative model execution loops by dispatching completions to OpenAI endpoints,
      executing model-invoked tools, recovering truncated edits with indented sentinels,
      evaluating loop guards, and streaming logs to RunnerLogger.
    """

    @operation
    @override
    def run(self) -> loop_driver.LoopOutcome:
        """Drives iterative turns using OpenAI completion requests.

        Returns:
            The final loop outcome.

        GROUNDING:
        - Grounded via transmitting chat completion requests to OpenAI endpoints, parsing tool calls,
          repairing truncated replace_file_content calls using indented NotImplementedError sentinels,
          dispatching tools through tool_provider, monitoring repetitive execution via LoopGuard,
          and returning a successful LoopOutcome upon tool termination.

        POSTCONDITIONS:
        - MUST transmit completion requests following OpenAI conventions with model parameters from configuration.
        - MUST order tools and parameters deterministically.
        - WHEN a model response is truncated, MUST recover by repairing partial replace file content payloads with indented sentinels or terminate with failure responses before resuming generation with a continuation turn.
        - WHEN a model completion response fails with an incomplete tool call error, MUST append an actionable recovery notice directing smaller edits.
        - WHEN handling an incomplete tool call error, MUST resume generation with a continuation turn.
        - WHEN repeated consecutive truncation failures occur, MUST halt execution with an unexpected failure.
        - MUST stream turn events and summaries to runner logger.
        - WHEN loop guard produces a loop reminder, MUST append reminder to the conversation.
        - WHEN loop guard produces loop failure, MUST halt with an unexpected failure.
        - WHEN tool execution produces a non-terminating failure response, MUST append failure feedback to the conversation.
        - WHEN tool execution produces a terminating failure response, MUST halt execution with an unexpected failure.
        - WHEN tool execution produces a successful termination response, MUST return a successful loop outcome.
        - WHEN a model response produces no tool executions, MUST append a prompt reminding that progress requires invoking tools.
        - WHEN tool responses specify followups, MUST execute designated tool calls.
        - WHEN interaction turns reach the conversation limit from agent config, MUST halt execution with an unexpected failure indicating that the conversation limit was reached.
        """
        ...
