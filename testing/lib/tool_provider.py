"""
Interface LLS: tool_provider

Defines the ToolProvider protocol and all types for the tool-provider interface.
The provider does not inspect, transform, or interpret values of type T_tool.
"""

from __future__ import annotations

from typing import Any, Protocol, Union, TypeVar, Generic, Literal, TypeAlias
from dataclasses import dataclass

T_tool = TypeVar("T_tool")

ToolName: TypeAlias = str

ToolArguments: TypeAlias = dict[str, Any]

ToolDefinition: TypeAlias = dict[str, Any]

ToolResultContent: TypeAlias = Any


@dataclass
class ToolResult:
    content: ToolResultContent
    supersedes: bool
    note: str = ""
    type: Literal["tool_result"] = "tool_result"


@dataclass
class PresentedToolResult:
    name: ToolName
    arguments: ToolArguments
    result: ToolResult
    type: Literal["presented_tool_result"] = "presented_tool_result"


class TerminateSuccessResult(Protocol):
    pass


@dataclass
class Continue:
    type: Literal["continue"] = "continue"


@dataclass
class TerminateAgentWithSuccess:
    value: TerminateSuccessResult
    type: Literal["terminate_success"] = "terminate_success"


@dataclass
class TerminateAgentWithFailure(Generic[T_tool]):
    value: T_tool
    type: Literal["terminate_failure"] = "terminate_failure"


@dataclass
class ToolFailure(Generic[T_tool]):
    value: T_tool
    type: Literal["tool_failure"] = "tool_failure"


Signal: TypeAlias = Union[
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure[T_tool],
    ToolFailure[T_tool],
]

ToolCallOutcome: TypeAlias = Union[list[ToolResult | PresentedToolResult], Signal[T_tool]]


class ToolExecutor(Protocol[T_tool]):
    def __call__(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]: ...
    def get_tool_definitions(self) -> list[ToolDefinition]: ...


class ToolProvider(Protocol[T_tool]):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]: ...
