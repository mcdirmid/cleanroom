# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: b04e08a04102
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Tool provider grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    NewType,
    Optional,
    Protocol,
    Sequence,
    Set,
    cast,
)
from support.lib.grounding_support import (
    AgentSessionTier,
    InTier,
    SystemTier,
    key,
    only_elem,
    value,
)

ToolName = NewType("ToolName", str)
ToolDescription = NewType("ToolDescription", str)
ParameterName = NewType("ParameterName", str)
type WireType = str | int | float | bool | Mapping[str, WireType] | Sequence[WireType]
SomeParameterActualType = NewType("SomeParameterActualType", object)


@dataclass(frozen=True)
class ParameterConversionError(ValueError):
    """Raised when wire value conversion to an actual type fails."""

    message: str


class ParameterType[ActualT, WireT](Protocol):
    """Polymorphic service converting wire type values to actual type values."""

    @property
    def actual_type(self) -> type[ActualT]:
        """
        DEFERRED:
        - Actual python type expected by the tool parameter.
        """
        raise NotImplementedError

    @property
    def wire_type(self) -> type[WireT]:
        """
        DEFERRED:
        - Wire format type accepted over the wire.
        """
        raise NotImplementedError

    def convert(self, wire_value: WireT) -> ActualT:
        """
        DEFERRED:
        - MUST convert wire type values to python type values.
        - WHEN conversion fails, MUST raise ParameterConversionError with diagnostic feedback.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class IdentityParameterType[T](ParameterType[T, T]):
    """Identity parameter type where actual and wire types are identical."""

    target_type: type[T]

    @property
    def actual_type(self) -> type[T]:
        """
        COVERED:
        - Actual type is identical to target type.
        """
        _target: type[T] = self.target_type
        raise NotImplementedError

    @property
    def wire_type(self) -> type[T]:
        """
        COVERED:
        - Wire type is identical to target type.
        """
        _target: type[T] = self.target_type
        raise NotImplementedError

    def convert(self, wire_value: T) -> T:
        """
        COVERED:
        - MUST convert wire values to python values without failure.
        - MUST never raise ParameterConversionError.
        """
        _val: T = wire_value
        raise NotImplementedError


@dataclass(frozen=True)
class SimpleParameterType[ActualT, WireT](ParameterType[ActualT, WireT]):
    """General parameter type for grounding proofs."""

    @property
    def actual_type(self) -> type[ActualT]:
        """
        COVERED:
        - Returns actual type representation.
        """
        _actual: type[ActualT] = cast(type[ActualT], object)
        raise NotImplementedError

    @property
    def wire_type(self) -> type[WireT]:
        """
        COVERED:
        - Returns wire type representation.
        """
        _wire: type[WireT] = cast(type[WireT], object)
        raise NotImplementedError

    def convert(self, wire_value: WireT) -> ActualT:
        """
        COVERED:
        - Casts wire value to actual type.
        """
        _val: ActualT = cast(ActualT, wire_value)
        raise NotImplementedError


@dataclass(frozen=True)
class ListParameterType[ItemActualT, ItemWireT](
    ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]
):
    """Parameter type converting a wire list to an actual list."""

    item_type: ParameterType[ItemActualT, ItemWireT]

    @property
    def actual_type(self) -> type[Sequence[ItemActualT]]:
        """
        COVERED:
        - Returns list type for actual type.
        """
        _actual: type[Sequence[ItemActualT]] = cast(type[Sequence[ItemActualT]], list)
        raise NotImplementedError

    @property
    def wire_type(self) -> type[Sequence[ItemWireT]]:
        """
        COVERED:
        - Returns list type for wire type.
        """
        _wire: type[Sequence[ItemWireT]] = cast(type[Sequence[ItemWireT]], list)
        raise NotImplementedError

    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        """
        COVERED:
        - MUST convert lists using an element parameter type.
        - WHEN constituent conversion fails, MUST propagate ParameterConversionError.
        """
        sample_wire: ItemWireT = only_elem(wire_value)
        sample_actual: ItemActualT = self.item_type.convert(sample_wire)
        _err: ParameterConversionError = ParameterConversionError(
            message="Constituent conversion failed"
        )
        _out: Sequence[ItemActualT] = [sample_actual]
        raise NotImplementedError


@dataclass(frozen=True)
class MappingParameterType[KeyActualT, ValActualT, ValWireT](
    ParameterType[Mapping[KeyActualT, ValActualT], Mapping[str, ValWireT]]
):
    """Parameter type converting a wire mapping to an actual mapping."""

    key_type: ParameterType[KeyActualT, str]
    value_type: ParameterType[ValActualT, ValWireT]

    @property
    def actual_type(self) -> type[Mapping[KeyActualT, ValActualT]]:
        """
        COVERED:
        - Returns dict type for actual type.
        """
        _actual: type[Mapping[KeyActualT, ValActualT]] = cast(
            type[Mapping[KeyActualT, ValActualT]], dict
        )
        raise NotImplementedError

    @property
    def wire_type(self) -> type[Mapping[str, ValWireT]]:
        """
        COVERED:
        - Returns dict type for wire type.
        """
        _wire: type[Mapping[str, ValWireT]] = cast(type[Mapping[str, ValWireT]], dict)
        raise NotImplementedError

    def convert(
        self, wire_value: Mapping[str, ValWireT]
    ) -> Mapping[KeyActualT, ValActualT]:
        """
        COVERED:
        - MUST convert mapping keys with a key parameter type.
        - MUST convert mapping values with an element parameter type.
        - WHEN constituent conversion fails, MUST propagate ParameterConversionError.
        """
        sample_wire_k: str = key(wire_value)
        sample_wire_v: ValWireT = value(wire_value)
        sample_actual_k: KeyActualT = self.key_type.convert(sample_wire_k)
        sample_actual_v: ValActualT = self.value_type.convert(sample_wire_v)
        _err: ParameterConversionError = ParameterConversionError(
            message="Constituent conversion failed"
        )
        _out: Mapping[KeyActualT, ValActualT] = {sample_actual_k: sample_actual_v}
        raise NotImplementedError


@dataclass(frozen=True)
class ToolParameter[ActualT, WireT]:
    """Describes an input parameter accepted by a tool."""

    name: ParameterName
    description: str
    parameter_type: ParameterType[ActualT, WireT]
    is_required: bool = True
    default_value: Optional[ActualT] = None
    missing_message: Optional[Callable[[Set[ParameterName]], str]] = None


@dataclass(frozen=True)
class FollowUpToolCall:
    """Specifies a follow-up tool call."""

    tool_name: ToolName
    wire_parameter_bindings: Mapping[ParameterName, WireType]
    reasoning_text: Optional[str] = None


ToolReminder = NewType("ToolReminder", str)
SuppressionKey = NewType("SuppressionKey", str)


@dataclass(frozen=True)
class ToolResponse:
    """Communicates tool execution results to the agent."""

    is_failed: bool
    is_terminated: bool
    content: str
    reminder: Optional[ToolReminder] = None
    suppression_key: Optional[SuppressionKey] = None
    follow_up_tool_call: Optional[FollowUpToolCall] = None


class Tool(Protocol):
    """Polymorphic service defining an executable action available to an agent."""

    @property
    def name(self) -> ToolName:
        """
        DEFERRED:
        - Unique name identifying the tool.
        """
        raise NotImplementedError

    @property
    def description(self) -> ToolDescription:
        """
        DEFERRED:
        - Human-readable description of what the tool accomplishes.
        """
        raise NotImplementedError

    @property
    def parameters(self) -> Mapping[ParameterName, ToolParameter[Any, Any]]:
        """
        DEFERRED:
        - Specification of parameters accepted by the tool.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            ToolParameter[Any, Any], SomeParameterActualType
        ],
    ) -> ToolResponse:
        """
        DEFERRED:
        - WHEN tool-specific execution conditions fail, MUST indicate failure status in the tool response with diagnostic feedback.
        """
        raise NotImplementedError


class ToolManager(InTier[AgentSessionTier], Protocol):
    """Session service that maintains and executes tools."""

    @property
    def installed_tools(self) -> Mapping[ToolName, Tool]:
        """
        DEFERRED:
        - Exposes installed tools as a mapping.
        - Deferred to refining subtype ToolManager in tool_provider_impl.py (requires concrete registry storage).
        """
        raise NotImplementedError

    def install_tool(self, tool: Tool) -> None:
        """
        DEFERRED:
        - MUST install the tool for the agent session.
        - Deferred to refining subtype ToolManager in tool_provider_impl.py (requires internal state mutation).
        """
        raise NotImplementedError

    def execute_tool(
        self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]
    ) -> ToolResponse:
        """
        COVERED:
        - WHEN calling a tool whose name does not match any installed tool, MUST fail with feedback citing the unknown tool and listing installed tools.
          - Condition knowledge: name not in tools.
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Unknown tool '{name}'. Available tools: {', '.join(tools.keys())}").
        - WHEN a call omits a required parameter lacking a missing note, MUST fail with feedback citing the missing parameter.
          - Condition knowledge: param.is_required, sample_param_name not in wire_parameter_bindings, param.missing_message is None.
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Missing required parameter '{sample_param_name}'").
        - WHEN a call omits a required parameter specifying a missing note evaluated against present parameters, MUST fail with feedback citing the missing parameter and missing note.
          - Condition knowledge: param.is_required, sample_param_name not in wire_parameter_bindings, param.missing_message is not None, present_params = set(wire_parameter_bindings.keys()), note_fn(present_params).
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Missing required parameter '{sample_param_name}': {evaluated_note}").
        - WHEN a call omits a non-required parameter specifying a default value, MUST bind the default value for the call.
          - Condition knowledge: not param.is_required, param.default_value is not None.
          - Consequent knowledge: action_bindings = {param: SomeParameterActualType(param.default_value)}.
        - WHEN wire conversion fails for a parameter, MUST fail with feedback citing the parameter name and the conversion failure feedback.
          - Condition knowledge: ParameterConversionError(message=...).message.
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Parameter '{sample_param_name}' conversion failed: {err.message}").
        - WHEN all parameter symbols resolve, required parameters are present, defaults are applied, and wire conversions succeed, MUST call the tool with action parameter bindings and return its tool response.
          - Condition knowledge: pt.convert(sample_wire_val), action_bindings = {param: actual_val}.
          - Consequent knowledge: tool.execute_tool(action_bindings)."""
        # 1. Postcondition: Unknown tool detection and diagnostic failure response
        tools: Mapping[ToolName, Tool] = self.installed_tools
        _is_unknown_tool: bool = name not in tools
        _installed_list: str = ", ".join(tools.keys())
        _unknown_tool_resp: ToolResponse = ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Unknown tool '{name}'. Available tools: {_installed_list}",
        )

        tool: Tool = tools[name]
        _tool_name: ToolName = tool.name
        _tool_desc: ToolDescription = tool.description

        # 2. Access tool parameters and representative parameter
        params: Mapping[ParameterName, ToolParameter[Any, Any]] = tool.parameters
        _param_names: Iterable[ParameterName] = params.keys()
        sample_param_name: ParameterName = key(params)
        param: ToolParameter[Any, Any] = params[sample_param_name]
        _param_name: ParameterName = param.name
        _param_desc: str = param.description

        # 3. Postcondition: Missing required parameter lacking missing note
        _is_omitted: bool = sample_param_name not in wire_parameter_bindings
        _is_req: bool = param.is_required
        _lacks_note: bool = param.missing_message is None
        _missing_no_note_resp: ToolResponse = ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Missing required parameter '{sample_param_name}'",
        )

        # 4. Postcondition: Missing required parameter specifying missing note
        _has_note: bool = param.missing_message is not None
        present_params: Set[ParameterName] = set(wire_parameter_bindings.keys())
        note_fn: Callable[[Set[ParameterName]], str] = param.missing_message or (
            lambda s: ""
        )
        evaluated_note: str = note_fn(present_params)
        _missing_with_note_resp: ToolResponse = ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Missing required parameter '{sample_param_name}': {evaluated_note}",
        )

        # 5. Postcondition: Non-required parameter specifying default value
        _is_defaultable: bool = (
            not param.is_required and param.default_value is not None
        )
        default_actual_val: SomeParameterActualType = SomeParameterActualType(
            param.default_value
        )
        _default_action_bindings: Mapping[
            ToolParameter[Any, Any], SomeParameterActualType
        ] = {param: default_actual_val}

        # 6. Postcondition: Wire conversion failure with diagnostic feedback
        pt: ParameterType[Any, Any] = param.parameter_type
        _actual_t: type[Any] = pt.actual_type
        _wire_t: type[Any] = pt.wire_type
        dummy_conv_err: ParameterConversionError = ParameterConversionError(
            message="Invalid wire format"
        )
        _conv_err_feedback: str = dummy_conv_err.message
        _conv_failure_resp: ToolResponse = ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Parameter '{sample_param_name}' conversion failed: {_conv_err_feedback}",
        )

        # 7. Postcondition: Successful conversion, binding, and tool execution
        sample_wire_name: ParameterName = key(wire_parameter_bindings)
        sample_wire_val: WireType = wire_parameter_bindings[sample_wire_name]
        converted_val: Any = pt.convert(sample_wire_val)
        actual_val: SomeParameterActualType = SomeParameterActualType(converted_val)
        action_bindings: Mapping[ToolParameter[Any, Any], SomeParameterActualType] = {
            param: actual_val
        }
        response: ToolResponse = tool.execute_tool(action_bindings)

        # 8. Access response status and diagnostic attributes
        _is_failed: bool = response.is_failed
        _is_terminated: bool = response.is_terminated
        _content: str = response.content
        _reminder: Optional[str] = response.reminder
        _suppression: Optional[str] = response.suppression_key
        _follow_up: Optional[FollowUpToolCall] = response.follow_up_tool_call

        _result: ToolResponse = response
        raise NotImplementedError
