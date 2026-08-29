"""
lib/conversation_history.py

Conversation History Interface Protocol.
"""

from __future__ import annotations

from typing import Any, Callable, List, Literal, Optional, Protocol, TypeAlias
from .tool_provider import ToolResult, PresentedToolResult, ToolCall

HistoryEntry: TypeAlias = dict[str, Any]

LogEvent: TypeAlias = Literal[
    "message_added",
    "message_stubbed",
    "tool_called",
    "tool_result",
    "api_response",
    "response_truncated",
    "run_terminated",
    "reminder_injected",
    "error",
]

LoggerCallback: TypeAlias = Callable[[LogEvent, dict[str, Any]], None]

RenderedMessage: TypeAlias = dict[str, Any]

StubMapping: TypeAlias = dict[tuple[str, str], int]


class ConversationHistory(Protocol):
    """
    Protocol for managing the conversation message history and rendering
    formatted messages for language model requests.
    """

    def reset(self) -> None:
        """Reset history, stub mappings, and counters to an empty state."""
        ...

    def initialize(
        self,
        prompt: str,
        session_start_results: Optional[List[PresentedToolResult]] = None,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        """Initialize conversation with prompt and session-start results."""
        ...

    def append_message(
        self,
        message: HistoryEntry,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        """Append a message entry to the conversation and notify the logger."""
        ...

    def add_tool_result(
        self,
        tool_call: Optional[ToolCall],
        result: ToolResult | PresentedToolResult,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        """Append a tool result and apply in-place stubbing if superseding."""
        ...

    def get_history(self) -> List[HistoryEntry]:
        """Return the full conversation history list in chronological order."""
        ...

    def get_rendered_messages(
        self,
        system_prompt: Optional[str] = None,
    ) -> List[RenderedMessage]:
        """Format and return rendered messages ready for model requests."""
        ...
