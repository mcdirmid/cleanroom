from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Set, Tuple, Type, Union
from framework import data_type, operation, override, poly_type, singleton_type, variant
from dataclasses import dataclass


@poly_type
class ParameterType[ActualT, WireT](Protocol):
    """Polymorphic service that converts wire type values to actual type values."""

    @property
    def actual_type(self) -> Type[ActualT]:
        """Data type produced by the converter."""
        ...

    @property
    def wire_type(self) -> Type[WireT]:
        """Primitive wire type accepted by the converter."""
        ...

    @operation
    def convert(self, wire_value: WireT) -> ActualT:
        """Converts a wire type value to produce a value of the actual type."""
        ...


@dataclass(frozen=True, init=False)
@data_type
class WireType:
    """Base class for allowed primitive wire types."""
    ...


@dataclass(frozen=True, init=False)
@variant
class WireString(WireType):
    """String wire type."""

    def __init__(self, value: str = ...) -> None:
        ...


@dataclass(frozen=True)
@variant
class WireInteger(WireType):
    """Integer wire type."""

    def __init__(self) -> None:
        ...


@dataclass(frozen=True)
@variant
class WireBoolean(WireType):
    """Boolean wire type."""

    def __init__(self) -> None:
        ...


@dataclass(frozen=True)
@variant
class WireFloat(WireType):
    """Float wire type."""

    def __init__(self) -> None:
        ...


@dataclass(frozen=True)
@variant
class WireList(WireType):
    """List wire type."""

    def __init__(self) -> None:
        ...


@dataclass(frozen=True)
@variant
class WireDictionary(WireType):
    """Dictionary wire type."""

    def __init__(self) -> None:
        ...



@dataclass(frozen=True)
@data_type
class IdentityParameterType[T](ParameterType[T, T]):
    """Identity parameter type where actual and wire types are identical."""
    target_type: Type[T]

    def __init__(self, target_type: Type[T]) -> None:
        ...

    @property
    @override
    def actual_type(self) -> Type[T]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> Type[T]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: T) -> T:
        """Converts a wire type value to actual type."""
        ...


@dataclass(frozen=True)
@data_type
class ListParameterType[ItemActualT, ItemWireT](ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]):
    """Parameter type converting a wire list to an actual list."""
    item_type: ParameterType[ItemActualT, ItemWireT]

    def __init__(self, item_type: ParameterType[ItemActualT, ItemWireT]) -> None:
        ...

    @property
    @override
    def actual_type(self) -> Type[Sequence[ItemActualT]]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> Type[Sequence[ItemWireT]]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        """Converts wire list to actual list."""
        ...


@dataclass(frozen=True)
@data_type
class DictionaryParameterType[KeyActualT, KeyWireT, ValActualT, ValWireT](ParameterType[Mapping[KeyActualT, ValActualT], Mapping[KeyWireT, ValWireT]]):
    """Parameter type converting a wire dictionary to an actual dictionary."""
    value_type: ParameterType[ValActualT, ValWireT]
    key_type: ParameterType[KeyActualT, KeyWireT] = ...

    def __init__(self, value_type: ParameterType[ValActualT, ValWireT], key_type: ParameterType[KeyActualT, KeyWireT] = ...) -> None:
        ...

    @property
    @override
    def actual_type(self) -> Type[Mapping[KeyActualT, ValActualT]]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> Type[Mapping[KeyWireT, ValWireT]]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: Mapping[KeyWireT, ValWireT]) -> Mapping[KeyActualT, ValActualT]:
        """Converts wire dictionary to actual dictionary."""
        ...


@poly_type
class Tool(Protocol):
    """Polymorphic service defining an executable action available to an agent.

    ASSUMPTIONS:
    - All parameters of a tool have unique names.
    """

    @property
    def name(self) -> str:
        """Name of the tool."""
        ...

    @property
    def description(self) -> str:
        """Description of what the tool does."""
        ...

    @property
    def parameters(self) -> Set[ToolParameter]:
        """Set of input parameters accepted by the tool."""
        ...

    @operation
    def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> ToolResponse:
        """Executes the tool with actual parameter bindings.

        REQUIREMENTS:
        - When a parameter is required, an argument must be supplied for tool execution.
        - When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

        GROUNDING_PROVISIONS:
        - action("execute_tool", ToolResponse): Executes tool.
        """
        ...


@dataclass(frozen=True)
@data_type
class ToolParameter[ActualT, WireT]:
    """Describes an input parameter accepted by a tool."""

    def __init__(self, name: str, description: str, parameter_type: ParameterType[ActualT, WireT], is_required: bool = ..., default_value: Optional[ActualT] = ..., missing_message: Optional[Callable[[Set[str]], str]] = ...) -> None:
        ...

    @property
    def name(self) -> str:
        """Parameter name."""
        ...

    @property
    def description(self) -> str:
        """Parameter description."""
        ...

    @property
    def parameter_type(self) -> ParameterType[ActualT, WireT]:
        """Parameter type specifying types and conversion."""
        ...

    @property
    def parameter_converter(self) -> ParameterType[ActualT, WireT]:
        """Alias for parameter_type."""
        ...

    @property
    def is_required(self) -> bool:
        """Whether argument is required."""
        ...

    @property
    def default_value(self) -> Optional[ActualT]:
        """Default value when omitted."""
        ...

    @property
    def missing_message(self) -> Optional[Callable[[Set[str]], str]]:
        """Optional function producing diagnostic message when omitted."""
        ...


@dataclass(frozen=True)
@data_type
class ActualParameterBindings:
    """Maps parameters to resolved values of their actual types."""

    def __init__(self, bindings: Set[Tuple[ToolParameter, Any]]) -> None:
        ...

    @property
    def bindings(self) -> Set[Tuple[ToolParameter, Any]]:
        """Set of parameter to value bindings."""
        ...


@dataclass(frozen=True)
@data_type
class WireParameterBindings:
    """Maps parameter names to values of their wire types."""

    def __init__(self, bindings: Set[Tuple[str, Any]]) -> None:
        ...

    @property
    def bindings(self) -> Set[Tuple[str, Any]]:
        """Set of parameter name to wire value bindings."""
        ...


@dataclass(frozen=True)
@data_type
class FollowUpToolCall:
    """Specifies a follow-up tool call."""

    def __init__(self, tool_name: str, wire_parameter_bindings: WireParameterBindings, reasoning_text: Optional[str] = None) -> None:
        ...

    @property
    def tool_name(self) -> str:
        """Tool name to call."""
        ...

    @property
    def wire_parameter_bindings(self) -> WireParameterBindings:
        """Wire parameter bindings."""
        ...

    @property
    def reasoning_text(self) -> Optional[str]:
        """Model reasoning text."""
        ...


@dataclass(frozen=True)
@data_type
class ToolResponse:
    """Communicates tool execution results to the agent."""

    def __init__(self, is_failed: bool, is_terminated: bool, content: str, reminder: Optional[str] = ..., suppression_key: Optional[str] = ..., follow_up_tool_call: Optional[FollowUpToolCall] = ...) -> None:
        ...

    @property
    def is_failed(self) -> bool:
        """Whether tool execution failed."""
        ...

    @property
    def is_terminated(self) -> bool:
        """Whether session should terminate."""
        ...

    @property
    def content(self) -> str:
        """Execution output or diagnostic message."""
        ...

    @property
    def reminder(self) -> Optional[str]:
        """Advisory guidance for agent."""
        ...

    @property
    def suppression_key(self) -> Optional[str]:
        """Key identifying prior response to supersede."""
        ...

    @property
    def follow_up_tool_call(self) -> Optional[FollowUpToolCall]:
        """Follow-up tool call to execute."""
        ...


@singleton_type('agent_session')
class ToolManager(Protocol):
    """Session service that maintains and executes tools."""

    @property
    def installed_tools(self) -> Set[Tool]:
        """Exposes installed tools."""
        ...

    @operation
    def install_tool(self, tool: Tool) -> None:
        """Installs tools so they can be executed.

        ASSUMPTIONS:
        - All installed tools in a tool manager have unique names.

        GROUNDING_PROVISIONS:
        - action("install_tool", None): Installs tool.
        """
        ...

    @operation
    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> ToolResponse:
        """Executes a tool by name with wire parameter bindings.

        REQUIREMENTS:
        - Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.

        GROUNDING_PROVISIONS:
        - action("execute_tool", ToolResponse): Executes tool by name.
        """
        ...

    @operation
    def execute_tool_with_arguments(self, name: str, arguments: Mapping[str, Any]) -> ToolResponse:
        """Executes a tool by name with raw argument dictionary.

        GROUNDING_PROVISIONS:
        - action("execute_tool_with_arguments", ToolResponse): Executes tool with arguments.
        """
        ...


