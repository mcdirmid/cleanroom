# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:45Z
# CHANGE: Make the follow-up tool call reasoning text a required member as the grounding specification declares
# CODE_HASH: fa1eb422d183
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Callable, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple, cast
from dataclasses import dataclass
from update_with_ai.parts.agent.lib.session import AgentSessionTier
import update_with_ai.parts.agent.lib.file_alias as file_alias

# Requirements specified in tool_provider.pyi

ToolName = NewType('ToolName', str)

ToolDescription = NewType('ToolDescription', str)

ParameterName = NewType('ParameterName', str)

ParameterDescription = NewType('ParameterDescription', str)

MissingMessage = NewType('MissingMessage', str)

ToolResponseContent = NewType('ToolResponseContent', str)

ToolReminder = NewType('ToolReminder', str)

SuppressionKey = NewType('SuppressionKey', str)

ReasoningText = NewType('ReasoningText', str)

ConversionErrorMessage = NewType('ConversionErrorMessage', str)

type WireType = str | int | float | bool | Mapping[str, WireType] | Sequence[WireType]

SomeParameterActualType = NewType('SomeParameterActualType', object)

# Contract: ParameterConversionError - raised when wire value conversion to an actual type fails.
@dataclass(frozen=True)
class ParameterConversionError(ValueError):
    # TODO_ParameterConversionError_body
    message: ConversionErrorMessage


# Contract: ParameterType protocol - converts wire type values to actual type values.
class ParameterType[ActualT, WireT](Protocol):
    # Contract: Data type produced by the converter.
    @property
    def actual_type(self) -> type[ActualT]:
        # TODO_actual_type_body
        ...

    # Contract: Primitive wire type accepted by the converter.
    @property
    def wire_type(self) -> type[WireT]:
        # TODO_wire_type_body
        ...

    # Contract: Converts a wire type value to produce a value of the actual type.
    def convert(self, wire_value: WireT) -> ActualT:
        # TODO_convert_body
        ...


# Contract: IdentityParameterType - parameter type where actual and wire types are identical.
@dataclass(frozen=True)
class IdentityParameterType[T](ParameterType[T, T]):
    target_type: type[T]

    # Contract: Data type produced by converter.
    @property
    def actual_type(self) -> type[T]:
        return self.target_type

    # Contract: Primitive wire type accepted by converter.
    @property
    def wire_type(self) -> type[T]:
        return self.target_type

    # Contract: Converts a wire type value to actual type.
    def convert(self, wire_value: T) -> T:
        return wire_value


# Contract: ListParameterType - parameter type converting a wire list to an actual list.
@dataclass(frozen=True)
class ListParameterType[ItemActualT, ItemWireT](ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]):
    item_type: ParameterType[ItemActualT, ItemWireT]

    # Contract: Data type produced by converter.
    @property
    def actual_type(self) -> type[Sequence[ItemActualT]]:
        return cast(type[Sequence[ItemActualT]], Sequence)

    # Contract: Primitive wire type accepted by converter.
    @property
    def wire_type(self) -> type[Sequence[ItemWireT]]:
        return cast(type[Sequence[ItemWireT]], Sequence)

    # Contract: Converts wire list to actual list.
    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        return [self.item_type.convert(item) for item in wire_value]


# Contract: MappingParameterType - parameter type converting a wire mapping to an actual mapping.
@dataclass(frozen=True)
class MappingParameterType[KeyActualT, ValActualT, ValWireT](ParameterType[Mapping[KeyActualT, ValActualT], Mapping[str, ValWireT]]):
    key_type: ParameterType[KeyActualT, str]
    value_type: ParameterType[ValActualT, ValWireT]

    # Contract: Data type produced by converter.
    @property
    def actual_type(self) -> type[Mapping[KeyActualT, ValActualT]]:
        return cast(type[Mapping[KeyActualT, ValActualT]], Mapping)

    # Contract: Primitive wire type accepted by converter.
    @property
    def wire_type(self) -> type[Mapping[str, ValWireT]]:
        return cast(type[Mapping[str, ValWireT]], Mapping)

    # Contract: Converts wire mapping to actual mapping.
    def convert(self, wire_value: Mapping[str, ValWireT]) -> Mapping[KeyActualT, ValActualT]:
        return {
            self.key_type.convert(k): self.value_type.convert(v)
            for k, v in wire_value.items()
        }


# Contract: AliasManagerType protocol - adapts session alias manager to provide file alias parameter conversion.
class AliasManagerType(ParameterType[file_alias.FileAlias, str], Protocol):
    # Contract: Data type produced by the converter.
    @property
    def actual_type(self) -> type[file_alias.FileAlias]:
        ...

    # Contract: Primitive wire type accepted by the converter.
    @property
    def wire_type(self) -> type[str]:
        ...

    # Contract: Converts wire string to file alias using the session alias manager.
    def convert(self, wire_value: str) -> file_alias.FileAlias:
        ...




# Contract: Tool protocol - polymorphic service defining an executable action available to an agent.
class Tool(Protocol):
    # Contract: Name of the tool.
    @property
    def name(self) -> ToolName:
        # TODO_name_body
        ...

    # Contract: Description of what the tool does.
    @property
    def description(self) -> ToolDescription:
        # TODO_description_body
        ...

    # Contract: Input parameters accepted by the tool.
    @property
    def parameters(self) -> Mapping[ParameterName, ToolParameter[Any, Any]]:
        # TODO_parameters_body
        ...

    # Contract: Executes the tool with action parameter bindings.
    def execute_tool(self, actual_parameter_bindings: Mapping[ToolParameter[Any, Any], SomeParameterActualType]) -> ToolResponse:
        # TODO_execute_tool_body
        ...


# Contract: ToolParameter - describes an input parameter accepted by a tool.
@dataclass(frozen=True)
class ToolParameter[ActualT, WireT]:
    # TODO_ToolParameter_body
    name: ParameterName
    description: ParameterDescription
    parameter_type: ParameterType[ActualT, WireT]
    is_required: bool = True
    default_value: Optional[ActualT] = None
    missing_message: Optional[Callable[[Set[ParameterName]], MissingMessage]] = None


# Contract: FollowUpToolCall - specifies a follow-up tool call.
@dataclass(frozen=True)
class FollowUpToolCall:
    # TODO_FollowUpToolCall_body
    tool_name: ToolName
    wire_parameter_bindings: Mapping[ParameterName, WireType]
    reasoning_text: ReasoningText


# Contract: ToolResponse - communicates tool execution results to the agent.
@dataclass(frozen=True)
class ToolResponse:
    # TODO_ToolResponse_body
    is_failed: bool
    is_terminated: bool
    content: ToolResponseContent
    reminder: Optional[ToolReminder] = None
    suppression_key: Optional[SuppressionKey] = None
    follow_up_tool_call: Optional[FollowUpToolCall] = None


# Contract: ToolManager protocol - session service that maintains and executes tools.
class ToolManager(Protocol):
    # Contract: Exposes installed tools as a mapping.
    @property
    def installed_tools(self) -> Mapping[ToolName, Tool]:
        # TODO_installed_tools_body
        ...

    # Contract: Installs tools so they can be executed.
    def install_tool(self, tool: Tool) -> None:
        # TODO_install_tool_body
        ...

    # Contract: Executes a tool by name with wire parameter bindings.
    def execute_tool(self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]) -> ToolResponse:
        # TODO_execute_tool_body
        ...
