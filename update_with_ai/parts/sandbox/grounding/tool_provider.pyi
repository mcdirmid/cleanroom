from typing import Any, Mapping, Optional, Protocol, Sequence, Set, Tuple, Type, Union
from framework import data_type, operation, override, poly_type, singleton_type, variant
from dataclasses import dataclass

@poly_type
class ParameterType[ActualT, WireT](Protocol):
    """
PURPOSE:
Polymorphic service that has an actual type, a primitive wire type, and can convert a wire type value to produce a value of that actual type
"""

    @property
    def actual_type(self) -> Type[ActualT]:
        """
PURPOSE:
References the data type produced by the converter
"""
        ...

    @property
    def wire_type(self) -> Type[WireT]:
        """
PURPOSE:
Primitive wire type accepted by the converter
"""
        ...

    @operation
    def to_actual(self, value: WireT) -> ActualT:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

    @operation
    def to_wire(self, value: ActualT) -> WireT:
        """
PURPOSE:
Converts an actual type value to produce a value of that wire type
"""
        ...

    @operation
    def convert(self, wire_value: WireT) -> ActualT:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class WireType:
    """
PURPOSE:
Defined as a primitive wire type limited to string, integer, boolean, float, list, or dictionary
"""
    ...

@dataclass(frozen=True)
@variant
class String(WireType):
    """
PURPOSE:
Classifies string as an allowed primitive wire type
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Integer(WireType):
    """
PURPOSE:
Classifies integer as an allowed primitive wire type
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Boolean(WireType):
    """
PURPOSE:
Classifies boolean as an allowed primitive wire type
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Float(WireType):
    """
PURPOSE:
Classifies float as an allowed primitive wire type
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class List(WireType):
    """
PURPOSE:
Classifies list as an allowed primitive wire type
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Dictionary(WireType):
    """
PURPOSE:
Classifies dictionary as an allowed primitive wire type
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@data_type
class IdentityParameterType[T](ParameterType[T, T]):
    """
PURPOSE:
Parameter type that works for parameters where the actual and wire types are the same target type

INHERITANCE:
- ParameterType
"""
    target_type: Type[T]

    def __init__(self, target_type: Type[T]) -> None:
        ...

    @property
    @override
    def actual_type(self) -> Type[T]:
        """
PURPOSE:
References the data type produced by the converter
"""
        ...

    @property
    @override
    def wire_type(self) -> Type[T]:
        """
PURPOSE:
Primitive wire type accepted by the converter
"""
        ...

    @operation
    @override
    def to_actual(self, value: T) -> T:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

    @operation
    @override
    def to_wire(self, value: T) -> T:
        """
PURPOSE:
Converts an actual type value to produce a value of that wire type
"""
        ...

    @operation
    @override
    def convert(self, wire_value: T) -> T:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

@dataclass(frozen=True)
@data_type
class ListParameterType[ItemActualT, ItemWireT](ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]):
    """
PURPOSE:
Parameter type that converts a wire type list to an actual type list, having an item parameter type that converts individual elements

INHERITANCE:
- ParameterType
"""
    item_type: ParameterType[ItemActualT, ItemWireT]

    def __init__(self, item_type: ParameterType[ItemActualT, ItemWireT]) -> None:
        ...

    @property
    @override
    def actual_type(self) -> Type[Sequence[ItemActualT]]:
        """
PURPOSE:
References the data type produced by the converter
"""
        ...

    @property
    @override
    def wire_type(self) -> Type[Sequence[ItemWireT]]:
        """
PURPOSE:
Primitive wire type accepted by the converter
"""
        ...

    @operation
    @override
    def to_actual(self, value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

    @operation
    @override
    def to_wire(self, value: Sequence[ItemActualT]) -> Sequence[ItemWireT]:
        """
PURPOSE:
Converts an actual type value to produce a value of that wire type
"""
        ...

    @operation
    @override
    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

@dataclass(frozen=True)
@data_type
class DictionaryParameterType[KeyActualT, KeyWireT, ValActualT, ValWireT](ParameterType[Mapping[KeyActualT, ValActualT], Mapping[KeyWireT, ValWireT]]):
    """
PURPOSE:
Parameter type that converts a wire type dictionary to an actual type dictionary, having a key parameter type that converts dictionary keys and a value parameter type that converts dictionary values

INHERITANCE:
- ParameterType
"""
    value_type: ParameterType[ValActualT, ValWireT]
    key_type: ParameterType[KeyActualT, KeyWireT] = ...

    def __init__(self, value_type: ParameterType[ValActualT, ValWireT], key_type: ParameterType[KeyActualT, KeyWireT]=...) -> None:
        ...

    @property
    @override
    def actual_type(self) -> Type[Mapping[KeyActualT, ValActualT]]:
        """
PURPOSE:
References the data type produced by the converter
"""
        ...

    @property
    @override
    def wire_type(self) -> Type[Mapping[KeyWireT, ValWireT]]:
        """
PURPOSE:
Primitive wire type accepted by the converter
"""
        ...

    @operation
    @override
    def to_actual(self, value: Mapping[KeyWireT, ValWireT]) -> Mapping[KeyActualT, ValActualT]:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

    @operation
    @override
    def to_wire(self, value: Mapping[KeyActualT, ValActualT]) -> Mapping[KeyWireT, ValWireT]:
        """
PURPOSE:
Converts an actual type value to produce a value of that wire type
"""
        ...

    @operation
    @override
    def convert(self, wire_value: Mapping[KeyWireT, ValWireT]) -> Mapping[KeyActualT, ValActualT]:
        """
PURPOSE:
Converts a wire type value to produce a value of that actual type
"""
        ...

@poly_type
class Tool(Protocol):
    """
PURPOSE:
Polymorphic service that defines an executable action available to an agent

FRESH_ASSUMPTIONS:
- All parameters of a tool have unique names.
"""

    @property
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    def parameters(self) -> Set[Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

FRESH_REQUIREMENTS:
- When a parameter is required, an argument must be supplied for tool execution.
- When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...

@dataclass(frozen=True)
@data_type
class Parameter[ActualT, WireT]:
    """
PURPOSE:
Describes an input accepted by a tool
"""

    def __init__(self, name: str, description: str, parameter_type: ParameterType[ActualT, WireT], is_required: bool=..., default_value: Optional[ActualT]=...) -> None:
        ...

    @property
    def name(self) -> str:
        """
PURPOSE:
Established that each parameter has a name for the agent's benefit guiding how arguments are supplied
"""
        ...

    @property
    def description(self) -> str:
        """
PURPOSE:
Established that each parameter has a description for the agent's benefit guiding how arguments are supplied
"""
        ...

    @property
    def parameter_type(self) -> ParameterType[ActualT, WireT]:
        """
PURPOSE:
Established that each parameter has a parameter type specifying its types and performing conversion
"""
        ...

    @property
    def parameter_converter(self) -> ParameterType[ActualT, WireT]:
        ...

    @property
    def is_required(self) -> bool:
        """
PURPOSE:
Indicates that an argument must be supplied for tool execution
"""
        ...

    @property
    def default_value(self) -> Optional[ActualT]:
        """
PURPOSE:
Represents the value used when an argument is omitted during tool execution
"""
        ...

@dataclass(frozen=True)
@data_type
class ActualParameterBindings:
    """
PURPOSE:
Maps parameters to resolved values of their actual types
"""

    def __init__(self, bindings: Set[Tuple[Parameter, Any]]) -> None:
        ...

    @property
    def bindings(self) -> Set[Tuple[Parameter, Any]]:
        """
PURPOSE:
Set mapping parameters to resolved values of their actual types
"""
        ...

    @operation
    def get_value(self, name: str, default: Optional[Any]=...) -> Any:
        ...

@dataclass(frozen=True)
@data_type
class WireParameterBindings:
    """
PURPOSE:
Maps parameter names to values of their wire types
"""

    def __init__(self, bindings: Set[Tuple[str, Any]]) -> None:
        ...

    @property
    def bindings(self) -> Set[Tuple[str, Any]]:
        """
PURPOSE:
Set mapping parameter names to values of their wire types
"""
        ...

@dataclass(frozen=True)
@data_type
class FollowUpToolCall:
    """
PURPOSE:
Specifies a tool name, wire parameter bindings of that tool, and reasoning text representing injected model thought in the first-person perspective on why the follow-up tool is being called
"""

    def __init__(self, tool_name: str, wire_parameter_bindings: WireParameterBindings, reasoning_text: Optional[str]=None) -> None:
        ...

    @property
    def tool_name(self) -> str:
        """
PURPOSE:
Identifies the tool to be called
"""
        ...

    @property
    def wire_parameter_bindings(self) -> WireParameterBindings:
        """
PURPOSE:
Maps parameter names to values of their wire types for the follow-up tool
"""
        ...

    @property
    def reasoning_text(self) -> Optional[str]:
        """
PURPOSE:
Injected model thought on why the follow up tool is being called
"""
        ...

@dataclass(frozen=True)
@data_type
class Response:
    """
PURPOSE:
Communicates tool execution results to the agent
"""

    def __init__(self, is_failed: bool, is_terminated: bool, content: str, reminder: Optional[str]=..., suppression_key: Optional[str]=..., follow_up_tool_call: Optional[FollowUpToolCall]=...) -> None:
        ...

    @property
    def is_failed(self) -> bool:
        """
PURPOSE:
Communicates whether tool execution failed
"""
        ...

    @property
    def is_terminated(self) -> bool:
        """
PURPOSE:
Communicates whether the agent session should terminate
"""
        ...

    @property
    def content(self) -> str:
        """
PURPOSE:
Includes underlying tool execution output and error diagnostics on failure
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
    def suppression_key(self) -> Optional[str]:
        """
PURPOSE:
Identifies a previous conversation response content to be superseded by this execution
"""
        ...

    @property
    def follow_up_tool_call(self) -> Optional[FollowUpToolCall]:
        """
PURPOSE:
Specifies a tool name and wire parameter bindings of a follow-up tool to execute
"""
        ...

@singleton_type('agent_session')
class ToolManager(Protocol):
    """
PURPOSE:
Defined as an agent session service that maintains tools for an agent session
"""

    @property
    def installed_tools(self) -> Set[Tool]:
        """
PURPOSE:
Exposes installed tools to the session
"""
        ...

    @operation
    def install_tool(self, tool: Tool) -> None:
        """
PURPOSE:
Installs tools so they can be executed by the agent

FRESH_ASSUMPTIONS:
- All installed tools in a tool manager have unique names.
"""
        ...

    @operation
    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> Response:
        """
PURPOSE:
Executes tools by name with wire parameter bindings at the request of the agent

FRESH_REQUIREMENTS:
- Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.
"""
        ...

    @operation
    def execute_tool_with_arguments(self, name: str, arguments: Mapping[str, Any]) -> Response:
        """
PURPOSE:
Executes tools with arguments by name with raw argument mappings from parameter names to arguments
"""
        ...

    @operation
    def create_tool_callable(self, name: str) -> Any:
        """
PURPOSE:
Creates tool callables producing executable callable routines configured with parameter signatures and documentation for external server registration
"""
        ...
ParameterConverter: Type[Any] = ...
IdentityParameterConverter: Type[Any] = ...
StringParameterType: Type[Any] = ...
StringParameterConverter: Type[Any] = ...
IntegerParameterType: Type[Any] = ...
IntegerParameterConverter: Type[Any] = ...
BooleanParameterType: Type[Any] = ...
BooleanParameterConverter: Type[Any] = ...
FloatParameterType: Type[Any] = ...
FloatParameterConverter: Type[Any] = ...
ListParameterConverter: Type[Any] = ...
DictionaryParameterConverter: Type[Any] = ...
