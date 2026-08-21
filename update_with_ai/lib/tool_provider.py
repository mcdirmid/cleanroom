"""
lib/tool_provider.py

Interface definitions for the LLS Tool Provider.
"""

from typing import Any, Callable, Literal, Protocol, Union, TypeVar, Generic, Dict, List
from dataclasses import dataclass

# Type definitions
T_tool = TypeVar("T_tool")
"""
The opaque value type passed through from tool execution to the tool call
outcome. Each ToolProvider[T_tool] implementation resolves T_tool to a
concrete type. The provider does not inspect, transform, or interpret values
of this type.
"""

ToolName = str
ToolArguments = Dict[str, Any]
ToolDefinition = Dict[str, Any]  # JSON schema format
ToolResultContent = Any


@dataclass
class ToolResult:
    """The result produced by a tool execution.

    `supersedes` is True when the result supersedes the earlier non-stubbed
    result for the same file or tool command — the producing component's
    declaration; the consuming agent loop stubs that result (at most one)
    before rendering the new one. `supersedes` is False for results that
    never supersede an earlier result. `content` is rendered into the agent
    conversation. `note` carries producer-generated guidance for the model
    (e.g., the status of an operation); it is rendered into the model-visible
    message by the consuming agent loop, and does not replace `content`.
    """
    content: ToolResultContent
    supersedes: bool
    note: str = ""
    type: Literal["tool_result"] = "tool_result"


class TerminateSuccessResult(Protocol):
    """
    Abstract result carried by a successful termination signal.

    Concrete results are provided by dag_clean_logic: ChangeResult (changes
    to broadcast to reverse dependencies), FeedbackResult (feedback to
    deliver to specific dependencies), and NoChangeResult (cleaned with no
    messages). Tool providers form the relevant result for their termination
    tool and place it in TerminateAgentWithSuccess.value.
    """
    pass

@dataclass
class Continue:
    """Execution should continue."""
    type: Literal["continue"] = "continue"

@dataclass
class TerminateAgentWithSuccess:
    """The agent signals successful termination of the session, carrying the
    termination result (a TerminateSuccessResult)."""
    value: TerminateSuccessResult
    type: Literal["terminate_success"] = "terminate_success"

@dataclass
class TerminateAgentWithFailure(Generic[T_tool]):
    """The agent signals it cannot complete the task; the session terminates in failure."""
    value: T_tool
    type: Literal["terminate_failure"] = "terminate_failure"

@dataclass
class ToolFailure(Generic[T_tool]):
    """
    A failed tool call (invalid arguments, a policy violation, or a
    termination tool invoked incorrectly).

    A tool failure is not a termination and does not end the session: the
    failure value guides the agent and the loop continues. It is distinct
    from an agent-initiated termination (TerminateAgentWith*), which ends
    the session. A tool failure never carries the stub text and never
    supersedes an earlier result.
    """
    value: T_tool
    type: Literal["tool_failure"] = "tool_failure"

# Mutually exclusive outcomes
Signal = Union[
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure[T_tool],
    ToolFailure[T_tool],
]
ToolCallOutcome = Union[ToolResult, Signal[T_tool]]

# Executes a single tool call (per-tool, one call at a time, not in batches).
ToolExecutor = Callable[[ToolName, ToolArguments], ToolCallOutcome[T_tool]]


class ToolProvider(Protocol[T_tool]):
    """
    Interface for the LLS Tool Provider.

    A component that manages tool definitions and executes tool calls,
    producing either tool results or signals.
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Returns the list of all available tool definitions.

        Returns:
            List of tool definitions conforming to JSON schema format.
            May be empty.

        Always succeeds.
        """
        ...

    def execute_tool(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]:
        """
        Executes a tool call and produces either a tool result or a signal.

        Args:
            name: The name of the tool to execute
            arguments: The arguments to pass to the tool

        Returns:
            Either a ToolResult or a Signal (Continue, a TerminateAgentWith*
            signal, or ToolFailure).

        Preconditions:
            - Tool name must be valid
            - Arguments must conform to the tool's parameter schema
            - Provider must not have previously produced a termination signal

        Postconditions:
            - If valid: returns exactly one ToolCallOutcome
            - If invalid: returns ToolFailure, state unchanged
            - Termination signals are atomic and final
            - Tool failures are not terminations; the session continues
            - A result with supersedes set supersedes the earlier non-stubbed
              result for the same file or tool command (at most one); the
              consumer stubs it before rendering the new result
            - A result with supersedes unset supersedes nothing; a result
              never carries the stub text
        """
        ...
