from typing import List, Optional, Protocol
from framework import data_type, operation, override, singleton_type, variant
from dataclasses import dataclass
import tool_provider

@dataclass(frozen=True)
@data_type
class Message:
    """
PURPOSE:
Entry in an agent conversation
"""

    def __init__(self, role: str, content: str, tool_call_id: Optional[str]=..., tool_name: Optional[str]=...) -> None:
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

@dataclass(frozen=True)
@variant
class Stub(Message):
    """
PURPOSE:
Placeholder message replacing superseded content
"""

    def __init__(self, role: str=..., content: str=..., tool_call_id: Optional[str]=..., tool_name: Optional[str]=...) -> None:
        ...

    @property
    @override
    def role(self) -> str:
        """
PURPOSE:
Role identifying the speaker, such as system, user, assistant, or tool
"""
        ...

    @property
    @override
    def content(self) -> str:
        """
PURPOSE:
Text content of the message
"""
        ...

    @property
    @override
    def tool_call_id(self) -> Optional[str]:
        """
PURPOSE:
Tool call identifier when correlating tool invocations and responses
"""
        ...

    @property
    @override
    def tool_name(self) -> Optional[str]:
        """
PURPOSE:
Tool name associated with a tool invocation or response
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
class ConversationHistory(Protocol):
    """
PURPOSE:
Defined as an agent session service maintaining chronological messages

FRESH_REQUIREMENTS:
- Initial messages can seed the conversation history at session start.
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
Appends a message to the conversation history
"""
        ...

    @operation
    def append_tool_response(self, response: tool_provider.Response, tool_name: str, tool_call_id: str) -> None:
        """
PURPOSE:
Appends a tool execution response, stubbing superseded results

FRESH_REQUIREMENTS:
- When an appended tool result supersedes an earlier result for the same resource, the earlier result is replaced in place with a stub.
"""
        ...

    @operation
    def get_model_request(self) -> ModelRequest:
        """
PURPOSE:
Produces a formatted model request for transmission

FRESH_REQUIREMENTS:
- The conversation history produces a model request prepared for transmission to a language model.
"""
        ...
