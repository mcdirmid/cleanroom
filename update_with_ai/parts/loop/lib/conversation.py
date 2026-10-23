from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
# Requirements specified in conversation.pyi
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from update_with_ai.parts.sandbox.lib import tool_provider

ToolCallId = NewType("ToolCallId", str)
MessageRole = NewType("MessageRole", str)
ConversationContent = NewType("ConversationContent", str)
SerializedArguments = NewType("SerializedArguments", str)


# Contract: ConversationMessage represents an entry in an agent conversation.
@dataclass(frozen=True)
class ConversationMessage:
    role: MessageRole
    content: ConversationContent
    tool_call_id: Optional[ToolCallId] = None
    tool_name: Optional[tool_provider.ToolName] = None
    reminder: Optional[tool_provider.ToolReminder] = None
    tool_arguments: Optional[SerializedArguments] = None
    is_stub: bool = False


# Contract: ModelRequest represents a formatted sequence of messages prepared for language model transmission.
@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[ConversationMessage]


# Contract: Conversation maintains chronological messages and stubs superseded results in the agent session tier.
class Conversation(Singleton[AgentSessionTier], Protocol):
    # Contract: Conversation.initialize - initializes conversation history with task instructions.
    def initialize(self, initial_messages: Sequence[ConversationMessage]) -> None: ...

    # Contract: Conversation.append_message - appends the message to the conversation.
    def append_message(self, message: ConversationMessage) -> None: ...

    # Contract: Conversation.append_tool_response - appends the tool response and stubs previous responses and arguments matching suppression key.
    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: SerializedArguments,
    ) -> None: ...

    # Contract: Conversation.get_model_request - exports formatted conversation history as a model request.
    def get_model_request(self) -> ModelRequest: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
