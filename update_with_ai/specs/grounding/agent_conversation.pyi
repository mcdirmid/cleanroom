from typing import List, Optional, Protocol
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
import tool_provider

@dataclass(frozen=True)
@data_type
class Message:
    """
PURPOSE:
Entry in an agent conversation
"""

    def __init__(self, role: str, content: str, tool_call_id: Optional[str]=..., tool_name: Optional[str]=..., reminder: Optional[str]=..., tool_arguments: Optional[str]=..., is_stub: bool=...) -> None:
        ...

    @property
    def role(self) -> str:
        """
PURPOSE:
Role identifying the speaker, such as system, user, assistant, or tool
"""
        ...

    @property
    def content(self) -> str:
        """
PURPOSE:
Text content of the message
"""
        ...

    @property
    def tool_call_id(self) -> Optional[str]:
        """
PURPOSE:
Tool call identifier when correlating tool invocations and responses
"""
        ...

    @property
    def tool_name(self) -> Optional[str]:
        """
PURPOSE:
Tool name associated with a tool invocation or response
"""
        ...

    @property
    def reminder(self) -> Optional[str]:
        """
PURPOSE:
Advises the agent on future actions and constraints
"""
        ...

    @property
    def tool_arguments(self) -> Optional[str]:
        """
PURPOSE:
Serialized argument parameters for a tool invocation
"""
        ...

    @property
    def is_stub(self) -> bool:
        """
PURPOSE:
Whether the message is a stub replacing superseded content
"""
        ...

@dataclass(frozen=True)
@data_type
class ModelRequest:
    """
PURPOSE:
Formatted sequence of messages prepared for transmission to a model
"""

    def __init__(self, messages: List[Message]) -> None:
        ...

    @property
    def messages(self) -> List[Message]:
        """
PURPOSE:
Ordered sequence of formatted messages
"""
        ...

@singleton_type('agent_session')
class Conversation(Protocol):
    """
PURPOSE:
Defined as an agent session service maintaining chronological messages

FRESH_REQUIREMENTS:
- Initial messages can seed the conversation at session start.
- Appending messages and tool responses adds them in chronological order.
"""

    @property
    def messages(self) -> List[Message]:
        """
PURPOSE:
Current sequence of messages in the session
"""
        ...

    @operation
    def append_message(self, message: Message) -> None:
        """
PURPOSE:
Appends a message to the conversation
"""
        ...

    @operation
    def append_tool_response(self, response: tool_provider.Response, tool_name: str, tool_call_id: str, wire_parameter_bindings: Optional[tool_provider.WireParameterBindings]=...) -> None:
        """
PURPOSE:
Appends a tool execution response, stubbing superseded results

FRESH_REQUIREMENTS:
- Stubs previous responses identified by a suppression key.
"""
        ...

    @operation
    def get_model_request(self) -> ModelRequest:
        """
PURPOSE:
Produces a formatted model request for transmission

FRESH_REQUIREMENTS:
- The conversation produces a model request prepared for transmission to a language model.
"""
        ...
