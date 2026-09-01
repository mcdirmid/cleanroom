"""Conversation history implementation storing ordered message history."""

from typing import Sequence, Union, Optional
from .tool_provider import ToolResult
from .conversation_history import (
    ConversationHistory,
    ConversationHistoryFactory,
    HistoryMessage,
    HistoryStub,
    ModelRequest,
)


class ConversationHistoryFactoryImpl(ConversationHistoryFactory):
    def create_conversation_history(self) -> ConversationHistory:
        return _ConversationHistoryImpl()


class _ConversationHistoryImpl(ConversationHistory):
    def __init__(self) -> None:
        self._messages: list[HistoryMessage] = []

    def initialize(self, initial_messages: Sequence[HistoryMessage]) -> None:
        self._messages = list(initial_messages)

    def append(self, item: Union[HistoryMessage, ToolResult]) -> None:
        if isinstance(item, HistoryMessage):
            if item.role == "tool" and (not self._messages or self._messages[-1].role != "assistant"):
                func_name = str(item.metadata.get("name", "read_file")) if item.metadata else "read_file"
                call_id = str(item.metadata.get("tool_call_id", "call_start")) if item.metadata else "call_start"
                self._messages.append(
                    HistoryMessage(
                        role="assistant",
                        content="",
                        metadata={"tool_calls": [{"id": call_id, "type": "function", "function": {"name": func_name, "arguments": "{}"}}]},
                    )
                )
            self._messages.append(item)
        elif isinstance(item, ToolResult):
            # Supersede earlier tool results in-place with static stub markers
            for idx, msg in enumerate(self._messages):
                if msg.role == "tool":
                    self._messages[idx] = HistoryStub(role="tool", content="...", metadata=msg.metadata)

            if not self._messages or self._messages[-1].role != "assistant":
                func_name = "advance" if item.guidance else "read_file"
                self._messages.append(
                    HistoryMessage(
                        role="assistant",
                        content="",
                        metadata={"tool_calls": [{"id": "call_start", "type": "function", "function": {"name": func_name, "arguments": "{}"}}]},
                    )
                )
            meta = {"guidance": item.guidance} if item.guidance else None
            self._messages.append(HistoryMessage(role="tool", content=item.content, metadata=meta))

    def get_model_request(self) -> ModelRequest:
        cleaned_messages: list[HistoryMessage] = []
        for msg in self._messages:
            if msg.metadata:
                cleaned_meta = {k: v for k, v in msg.metadata.items() if not k.startswith("_")}
                cleaned_messages.append(
                    HistoryMessage(role=msg.role, content=msg.content, metadata=cleaned_meta if cleaned_meta else None)
                )
            else:
                cleaned_messages.append(msg)
        return ModelRequest(messages=cleaned_messages)

    def get_messages(self) -> Sequence[HistoryMessage]:
        return list(self._messages)
