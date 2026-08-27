"""
Interface LLS: agent_loop — defines the AgentLoop Protocol and associated types
for the agent execution loop. The loop runs until a tool signals termination or
a failure occurs; termination values pass through unchanged.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Union, Protocol, TypeAlias
from tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    Signal,
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
    ToolExecutor,
    T_tool,
)

ToolCall: TypeAlias = dict[str, Any]

Usage: TypeAlias = dict[str, int]

CumulativeUsage: TypeAlias = dict[str, int]

HistoryEntry: TypeAlias = dict[str, Any]

ConversationHistory: TypeAlias = list[HistoryEntry]

AgentResult: TypeAlias = Union[
    tuple[TerminateAgentWithSuccess, ConversationHistory],
    tuple[TerminateAgentWithFailure[T_tool], ConversationHistory],
    tuple[str, ConversationHistory],
]

LogEvent: TypeAlias = Literal[
    "message_added",
    "message_stubbed",
    "tool_called",
    "tool_result",
    "api_response",
    "response_truncated",
    "reminder_injected",
    "run_terminated",
    "error",
]
LoggerCallback: TypeAlias = Callable[[LogEvent, dict[str, Any]], None]
TerminationReminderGenerator: TypeAlias = Callable[[], str]


class AgentLoop(Protocol):
    def run_agent(
        self,
        prompt: str,
        tools: list[ToolDefinition],
        tool_executor: ToolExecutor[T_tool],
        system_prompt: str | None = None,
        session_start_results: list[PresentedToolResult] | None = None,
        logger: LoggerCallback | None = None,
    ) -> AgentResult: ...
