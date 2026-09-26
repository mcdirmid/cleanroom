from typing import List, Optional, Protocol
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
import tool_provider


@dataclass(frozen=True)
@data_type
class ConversationMessage:
    """Entry in an agent conversation."""

    def __init__(self, role: str, content: str, tool_call_id: Optional[str] = ..., tool_name: Optional[str] = ..., reminder: Optional[str] = ..., tool_arguments: Optional[str] = ..., is_stub: bool = ...) -> None:
        ...

    @property
    def role(self) -> str:
        """Role identifying speaker."""
        ...

    @property
    def content(self) -> str:
        """Text content of the message."""
        ...

    @property
    def tool_call_id(self) -> Optional[str]:
        """Tool call identifier when correlating tool invocations and responses."""
        ...

    @property
    def tool_name(self) -> Optional[str]:
        """Tool name associated with a tool invocation or response."""
        ...

    @property
    def reminder(self) -> Optional[str]:
        """Advises the agent on future actions and constraints."""
        ...

    @property
    def tool_arguments(self) -> Optional[str]:
        """Serialized argument parameters for a tool invocation."""
        ...

    @property
    def is_stub(self) -> bool:
        """Whether the message is a stub replacing superseded content."""
        ...


@dataclass(frozen=True)
@data_type
class ModelRequest:
    """Formatted sequence of messages prepared for transmission to a model."""

    def __init__(self, messages: List[ConversationMessage]) -> None:
        ...

    @property
    def messages(self) -> List[ConversationMessage]:
        """Ordered sequence of formatted messages."""
        ...


@singleton_type('agent_session')
class Conversation(Protocol):
    """Session service maintaining chronological messages.

    REQUIREMENTS:
    - Initial messages can seed the conversation at session start.
    - Appending messages and tool responses adds them in chronological order.
    """

    @property
    def messages(self) -> List[ConversationMessage]:
        """Current sequence of messages in the session."""
        ...

    @operation
    def append_message(self, message: ConversationMessage) -> None:
        """Appends a message to the conversation."""
        ...

    @operation
    def append_tool_response(self, response: tool_provider.ToolResponse, tool_name: str, tool_call_id: str, wire_parameter_bindings: Optional[tool_provider.WireParameterBindings] = ...) -> None:
        """Appends a tool execution response, stubbing superseded results.

        REQUIREMENTS:
        - Stubs previous responses and correlating tool arguments identified by a suppression key.

        GROUNDING_PROVISIONS:
        - action("append_tool_response", None): Appends tool response and stubs previous.
        """
        ...

    @operation
    def get_model_request(self) -> ModelRequest:
        """Produces a formatted model request for transmission.

        REQUIREMENTS:
        - The conversation produces a model request prepared for transmission to a language model.

        GROUNDING_PROVISIONS:
        - action("get_model_request", ModelRequest): Produces model request.
        """
        ...

