# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 6773da74fc0b
# --- END CLEANROOM METADATA ---

"""Loop conversation low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import tool_provider

ToolCallId = NewType("ToolCallId", str)
MessageRole = NewType("MessageRole", str)
ConversationContent = NewType("ConversationContent", str)
SerializedArguments = NewType("SerializedArguments", str)


@dataclass(frozen=True)
@data_type
class ConversationMessage:
    """An entry in an agent conversation.

    Args:
        role: The participant role of the message.
        content: Text content of the message.
        tool_call_id: Correlation identifier for tool invocations and responses.
        tool_name: Name of the associated tool.
        reminder: Guidance advising the agent on future actions and constraints.
        tool_arguments: Serialized tool arguments.
        is_stub: Whether the message is a stub replacing superseded content.
    """
    role: MessageRole
    content: ConversationContent
    tool_call_id: Optional[ToolCallId] = ...
    tool_name: Optional[tool_provider.ToolName] = ...
    reminder: Optional[tool_provider.ToolReminder] = ...
    tool_arguments: Optional[SerializedArguments] = ...
    is_stub: bool = ...


@dataclass(frozen=True)
@data_type
class ModelRequest:
    """Formatted sequence of messages prepared for language model transmission.

    Args:
        messages: The sequence of conversation messages.
    """
    messages: Sequence[ConversationMessage]


@singleton_type("agent_session")
class Conversation(InTier[AgentSessionTier], Protocol):
    """Session service maintaining chronological messages and stubbing superseded results."""

    @operation
    def initialize(self, initial_messages: Sequence[ConversationMessage]) -> None:
        """Initializes conversation with initial task messages.

        Args:
            initial_messages: The starting sequence of conversation messages.

        POSTCONDITIONS:
        - MUST initialize conversation history with task instructions.
        """
        ...

    @operation
    def append_message(self, message: ConversationMessage) -> None:
        """Appends a conversation message.

        Args:
            message: The message to append.

        POSTCONDITIONS:
        - MUST append the message to the conversation.
        """
        ...

    @operation
    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: SerializedArguments,
    ) -> None:
        """Appends a tool execution response and stubs previous suppressed entries.

        Args:
            tool_response: Response produced by tool execution.
            tool_call_id: Identifier correlating with the originating tool call.
            tool_name: Name of the executed tool.
            tool_arguments: Serialized arguments passed to the tool.

        POSTCONDITIONS:
        - MUST append the tool response to the conversation.
        - MUST stub previous responses and correlating arguments matching suppression keys.
        """
        ...

    @operation
    def get_model_request(self) -> ModelRequest:
        """Constructs a formatted model request for transmission.

        Returns:
            The formatted model request record.

        POSTCONDITIONS:
        - MUST return a formatted model request for language model transmission.
        """
        ...
