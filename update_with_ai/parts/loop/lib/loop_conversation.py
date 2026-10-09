# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: d3ff4aa0c274
# --- END CLEANROOM METADATA ---

# Requirements specified in loop_conversation.pyi
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Sequence
from update_with_ai.parts.sandbox.lib import tool_provider

ToolCallId = NewType("ToolCallId", str)
MessageRole = NewType("MessageRole", str)
ConversationContent = NewType("ConversationContent", str)
SerializedArguments = NewType("SerializedArguments", str)


@dataclass(frozen=True)
class ConversationMessage:
    role: MessageRole
    content: ConversationContent
    tool_call_id: Optional[ToolCallId] = None
    tool_name: Optional[tool_provider.ToolName] = None
    reminder: Optional[tool_provider.ToolReminder] = None
    tool_arguments: Optional[SerializedArguments] = None
    is_stub: bool = False


@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[ConversationMessage]


class Conversation(Protocol):
    def initialize(self, initial_messages: Sequence[ConversationMessage]) -> None: ...

    def append_message(self, message: ConversationMessage) -> None: ...

    def append_tool_response(
        self,
        tool_response: tool_provider.ToolResponse,
        tool_call_id: ToolCallId,
        tool_name: tool_provider.ToolName,
        tool_arguments: SerializedArguments,
    ) -> None: ...

    def get_model_request(self) -> ModelRequest: ...
