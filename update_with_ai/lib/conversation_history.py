"""Conversation history interface and message models."""

from typing import Protocol, TypeAlias, Sequence, Mapping, Any, Optional, Union
from dataclasses import dataclass
from .tool_provider import ToolResult, Tool

MessageRole: TypeAlias = str
MessageContent: TypeAlias = str
MetadataField: TypeAlias = str
MetadataContent: TypeAlias = Any
MetadataMapping: TypeAlias = Mapping[MetadataField, MetadataContent]


@dataclass(frozen=True)
class HistoryMessage:
    role: MessageRole
    content: MessageContent
    metadata: Optional[MetadataMapping] = None


@dataclass(frozen=True)
class HistoryStub(HistoryMessage):
    role: MessageRole = "tool"
    content: MessageContent = "..."


@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[HistoryMessage]
    tools: Optional[Sequence[Tool]] = None


class ConversationHistory(Protocol):
    def initialize(self, initial_messages: Sequence[HistoryMessage]) -> None:
        ...

    def append(self, item: Union[HistoryMessage, ToolResult]) -> None:
        ...

    def get_model_request(self) -> ModelRequest:
        ...

    def get_messages(self) -> Sequence[HistoryMessage]:
        ...


class ConversationHistoryFactory(Protocol):
    def create_conversation_history(self) -> ConversationHistory:
        ...
