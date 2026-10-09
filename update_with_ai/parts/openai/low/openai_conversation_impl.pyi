# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: 99a0435dd51c
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""OpenAI conversation implementation low-level specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import loop_conversation
import tool_provider
import agent_config


@singleton_type("agent_session")
class Conversation(
    loop_conversation.Conversation, InTier[AgentSessionTier]
):
    """Realizes OpenAI provider role schema formatting, stubbing, and synthetic call injection.

    GROUNDING:
    - Implements conversation management conforming to OpenAI role schemas, managing
      unprompted response synthetic pairing, suppression key stubbing, and active reminder formatting.
    """

    @operation
    @override
    def initialize(
        self, initial_messages: Sequence[loop_conversation.ConversationMessage]
    ) -> None:
        """Initializes conversation history, pairing unprompted responses with synthetic calls.

        Args:
            initial_messages: Starting conversation messages.

        GROUNDING:
        - Grounded via pairing initial unprompted tool responses with synthetic antecedent assistant tool calls.

        POSTCONDITIONS:
        - MUST precede unprompted tool responses with synthetic assistant tool invocations.
        """
        ...

    @operation
    @override
    def append_message(
        self, message: loop_conversation.ConversationMessage
    ) -> None:
        """Appends a conversation message to history.

        GROUNDING:
        - Grounded via appending conversation messages directly to in-memory history.
        """
        ...

    @operation
    @override
    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: loop_conversation.ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: loop_conversation.SerializedArguments,
    ) -> None:
        """Appends tool response, replacing preceding suppressed responses with stubs.

        Args:
            tool_response: Response produced by tool execution.
            tool_call_id: Identifier correlating with originating tool call.
            tool_name: Name of the executed tool.
            tool_arguments: Serialized arguments passed to the tool.

        GROUNDING:
        - Grounded via buffer tracking per suppression key, stubbing superseded tool responses
          and correlating assistant arguments while preserving file paths and non-string values.

        POSTCONDITIONS:
        - MUST retain a buffer of up to three most recent responses sharing suppression keys.
        - MUST replace preceding responses beyond the buffer limit with stubs.
        - MUST preserve file path parameters and non-string arguments in superseded tool calls.
        - MUST replace other string arguments with a stub marker in superseded tool calls.
        - MUST retain reminders on stubs and inherit them when omitted.
        """
        ...

    @operation
    @override
    def get_model_request(self) -> loop_conversation.ModelRequest:
        """Assembles model request formatted according to OpenAI role schemas.

        Returns:
            The formatted model request.

        GROUNDING:
        - Grounded via assembling in-memory messages into an OpenAI-conforming ModelRequest,
          formatting active reminders and execution notes into visible message content.

        POSTCONDITIONS:
        - MUST format messages conforming to OpenAI role schemas.
        - MUST include active reminders and tool execution notes in visible content.
        """
        ...
