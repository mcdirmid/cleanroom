# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T18:47:37Z
# CHANGE: Replace ellipsis defaults with valid defaults in ToolParameter, FollowUpToolCall, and ToolResponse
# CODE_HASH: 95c83c08d780
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Callable, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple, cast
from dataclasses import dataclass
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier

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

@dataclass(frozen=True)
class ParameterConversionError(ValueError):
    # TODO_ParameterConversionError_body
    message: ConversionErrorMessage


class ParameterType[ActualT, WireT](Protocol):
    @property
    def actual_type(self) -> type[ActualT]:
        # TODO_actual_type_body
        ...

    @property
    def wire_type(self) -> type[WireT]:
        # TODO_wire_type_body
        ...

    def convert(self, wire_value: WireT) -> ActualT:
        # TODO_convert_body
        ...


@dataclass(frozen=True)
class IdentityParameterType[T](ParameterType[T, T]):
    target_type: type[T]

    @property
    def actual_type(self) -> type[T]:
        return self.target_type

    @property
    def wire_type(self) -> type[T]:
        return self.target_type

    def convert(self, wire_value: T) -> T:
        return wire_value


@dataclass(frozen=True)
class ListParameterType[ItemActualT, ItemWireT](ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]):
    item_type: ParameterType[ItemActualT, ItemWireT]

    @property
    def actual_type(self) -> type[Sequence[ItemActualT]]:
        return cast(type[Sequence[ItemActualT]], Sequence)

    @property
    def wire_type(self) -> type[Sequence[ItemWireT]]:
        return cast(type[Sequence[ItemWireT]], Sequence)

    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        return [self.item_type.convert(item) for item in wire_value]


@dataclass(frozen=True)
class MappingParameterType[KeyActualT, ValActualT, ValWireT](ParameterType[Mapping[KeyActualT, ValActualT], Mapping[str, ValWireT]]):
    key_type: ParameterType[KeyActualT, str]
    value_type: ParameterType[ValActualT, ValWireT]

    @property
    def actual_type(self) -> type[Mapping[KeyActualT, ValActualT]]:
        return cast(type[Mapping[KeyActualT, ValActualT]], Mapping)

    @property
    def wire_type(self) -> type[Mapping[str, ValWireT]]:
        return cast(type[Mapping[str, ValWireT]], Mapping)

    def convert(self, wire_value: Mapping[str, ValWireT]) -> Mapping[KeyActualT, ValActualT]:
        return {
            self.key_type.convert(k): self.value_type.convert(v)
            for k, v in wire_value.items()
        }



class Tool(Protocol):
    @property
    def name(self) -> ToolName:
        # TODO_name_body
        ...

    @property
    def description(self) -> ToolDescription:
        # TODO_description_body
        ...

    @property
    def parameters(self) -> Mapping[ParameterName, ToolParameter[Any, Any]]:
        # TODO_parameters_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[ToolParameter[Any, Any], SomeParameterActualType]) -> ToolResponse:
        # TODO_execute_tool_body
        ...


@dataclass(frozen=True)
class ToolParameter[ActualT, WireT]:
    # TODO_ToolParameter_body
    name: ParameterName
    description: ParameterDescription
    parameter_type: ParameterType[ActualT, WireT]
    is_required: bool = True
    default_value: Optional[ActualT] = None
    missing_message: Optional[Callable[[Set[ParameterName]], MissingMessage]] = None


@dataclass(frozen=True)
class FollowUpToolCall:
    # TODO_FollowUpToolCall_body
    tool_name: ToolName
    wire_parameter_bindings: Mapping[ParameterName, WireType]
    reasoning_text: Optional[ReasoningText] = None


@dataclass(frozen=True)
class ToolResponse:
    # TODO_ToolResponse_body
    is_failed: bool
    is_terminated: bool
    content: ToolResponseContent
    reminder: Optional[ToolReminder] = None
    suppression_key: Optional[SuppressionKey] = None
    follow_up_tool_call: Optional[FollowUpToolCall] = None


class ToolManager(Protocol):
    @property
    def installed_tools(self) -> Mapping[ToolName, Tool]:
        # TODO_installed_tools_body
        ...

    def install_tool(self, tool: Tool) -> None:
        # TODO_install_tool_body
        ...

    def execute_tool(self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]) -> ToolResponse:
        # TODO_execute_tool_body
        ...
