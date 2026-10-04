"""OpenAI conversation implementation low-level specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import loop_conversation
import tool_provider


@singleton_type("agent_session")
class Conversation(
    loop_conversation.Conversation, InTier[AgentSessionTier]
):
    """Realizes OpenAI provider role schema formatting, stubbing, and synthetic call injection."""

    @operation
    @override
    def initialize(
        self, initial_messages: Sequence[loop_conversation.ConversationMessage]
    ) -> None:
        """Initializes conversation history, pairing unprompted responses with synthetic calls.

        Args:
            initial_messages: Starting conversation messages.

        POSTCONDITIONS:
        - MUST precede unprompted tool responses with synthetic assistant tool invocations.
        """
        ...

    @operation
    @override
    def append_message(
        self, message: loop_conversation.ConversationMessage
    ) -> None:
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

        POSTCONDITIONS:
        - MUST format messages conforming to OpenAI role schemas.
        - MUST include active reminders and tool execution notes in visible content.
        """
        ...
