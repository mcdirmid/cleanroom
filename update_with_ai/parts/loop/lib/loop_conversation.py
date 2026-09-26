# Requirements specified in loop_conversation.pyi
"""Loop conversation interface and data types."""

from dataclasses import dataclass
from typing import List, Optional, Protocol
from update_with_ai.parts.sandbox.lib import tool_provider


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    reminder: Optional[str] = None
    tool_arguments: Optional[str] = None
    is_stub: bool = False


@dataclass(frozen=True)
class ModelRequest:
    messages: List[ConversationMessage]


class Conversation(Protocol):
    @property
    def messages(self) -> List[ConversationMessage]: ...

    def append_message(self, message: ConversationMessage) -> None: ...

    def append_tool_response(
        self,
        response: tool_provider.ToolResponse,
        tool_name: str,
        tool_call_id: str,
        wire_parameter_bindings: Optional[tool_provider.WireParameterBindings] = None,
    ) -> None: ...

    def get_model_request(self) -> ModelRequest: ...
