"""Tool provider interface and tool execution types."""

from typing import Protocol, TypeAlias, Sequence, Mapping, Any, Optional, Union
from dataclasses import dataclass

AgentIdentifier: TypeAlias = str
ToolName: TypeAlias = str
ToolPurpose: TypeAlias = str
ParameterSchema: TypeAlias = Mapping[str, Any]
ToolArguments: TypeAlias = Mapping[str, Any]
ToolResultContent: TypeAlias = str
ProducerGuidance: TypeAlias = str
FailureFeedback: TypeAlias = str
FailureError: TypeAlias = str
TerminationReason: TypeAlias = str


@dataclass(frozen=True)
class ToolMetadata:
    name: ToolName
    purpose: ToolPurpose
    parameters_schema: ParameterSchema


@dataclass(frozen=True)
class ToolResult:
    content: ToolResultContent = ""
    guidance: Optional[ProducerGuidance] = None


@dataclass(frozen=True)
class ToolFailure(ToolResult):
    feedback: FailureFeedback = ""
    error: FailureError = ""
    is_failure: bool = True

    def __post_init__(self) -> None:
        if not self.content and self.feedback:
            object.__setattr__(self, "content", self.feedback)


@dataclass(frozen=True)
class TerminationOutcome(ToolResult):
    reason: TerminationReason = ""
    is_terminal: bool = True

    def __post_init__(self) -> None:
        if not self.content and self.reason:
            object.__setattr__(self, "content", self.reason)


ToolOutcome: TypeAlias = Union[ToolResult, ToolFailure, TerminationOutcome]


class Tool(Protocol):
    def get_metadata(self) -> ToolMetadata:
        ...

    def execute(self, arguments: ToolArguments) -> ToolOutcome:
        ...


class ToolProvider(Protocol):
    def get_tools(self) -> Sequence[Tool]:
        ...
