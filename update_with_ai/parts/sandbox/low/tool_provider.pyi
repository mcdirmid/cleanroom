# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: e428e3f951f8
# --- END CLEANROOM METADATA ---

"""Tool provider low-level interface specification."""

from dataclasses import dataclass
from typing import Any, Callable, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple
from framework import data_type, operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier

ToolName = NewType("ToolName", str)
ToolDescription = NewType("ToolDescription", str)
ParameterName = NewType("ParameterName", str)
ParameterDescription = NewType("ParameterDescription", str)
MissingMessage = NewType("MissingMessage", str)
ToolResponseContent = NewType("ToolResponseContent", str)
ToolReminder = NewType("ToolReminder", str)
SuppressionKey = NewType("SuppressionKey", str)
ReasoningText = NewType("ReasoningText", str)
ConversionErrorMessage = NewType("ConversionErrorMessage", str)
type WireType = str | int | float | bool | Mapping[str, WireType] | Sequence[WireType]
SomeParameterActualType = NewType("SomeParameterActualType", object)


@dataclass(frozen=True)
@data_type
class ParameterConversionError(ValueError):
    """Raised when wire value conversion to an actual type fails.

    Args:
        message: Diagnostic feedback describing the conversion failure.
    """
    message: ConversionErrorMessage


@poly_type
class ParameterType[ActualT, WireT](Protocol):
    """Polymorphic service that converts wire type values to actual type values."""

    @property
    def actual_type(self) -> type[ActualT]:
        """Data type produced by the converter."""
        ...

    @property
    def wire_type(self) -> type[WireT]:
        """Primitive wire type accepted by the converter."""
        ...

    @operation
    def convert(self, wire_value: WireT) -> ActualT:
        """Converts a wire type value to produce a value of the actual type.

        Args:
            wire_value: The wire value to convert. Note, it might not be of WireT which has to be checked.

        Returns:
            The converted value of the actual type.

        POSTCONDITIONS:
        - MUST convert wire type values to python type values.
        - WHEN conversion fails, MUST raise ParameterConversionError with diagnostic feedback.
        """
        ...


@dataclass(frozen=True)
@data_type
class IdentityParameterType[T](ParameterType[T, T]):
    """Identity parameter type where actual and wire types are identical.

    Args:
        target_type: Target python and wire type.
    """
    target_type: type[T]

    @property
    @override
    def actual_type(self) -> type[T]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> type[T]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: T) -> T:
        """Converts a wire type value to actual type.

        Args:
            wire_value: The wire value to convert.

        Returns:
            The converted value of the actual type.

        POSTCONDITIONS:
        - MUST convert wire values to python values without failure.
        - MUST never raise ParameterConversionError.
        """
        ...


@dataclass(frozen=True)
@data_type
class ListParameterType[ItemActualT, ItemWireT](
    ParameterType[Sequence[ItemActualT], Sequence[ItemWireT]]
):
    """Parameter type converting a wire list to an actual list.

    Args:
        item_type: Element parameter type converter.
    """
    item_type: ParameterType[ItemActualT, ItemWireT]

    @property
    @override
    def actual_type(self) -> type[Sequence[ItemActualT]]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> type[Sequence[ItemWireT]]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: Sequence[ItemWireT]) -> Sequence[ItemActualT]:
        """Converts wire list to actual list.

        Args:
            wire_value: Sequence of wire items to convert.

        Returns:
            Sequence of converted actual items.

        POSTCONDITIONS:
        - MUST convert lists using an element parameter type.
        - WHEN constituent conversion fails, MUST propagate ParameterConversionError.
        """
        ...


@dataclass(frozen=True)
@data_type
class MappingParameterType[
    KeyActualT,
    ValActualT,
    ValWireT,
](ParameterType[Mapping[KeyActualT, ValActualT], Mapping[str, ValWireT]]):
    """Parameter type converting a wire mapping to an actual mapping.

    Args:
        key_type: Parameter type converter for keys.
        value_type: Parameter type converter for values.
    """
    key_type: ParameterType[KeyActualT, str]
    value_type: ParameterType[ValActualT, ValWireT]

    @property
    @override
    def actual_type(self) -> type[Mapping[KeyActualT, ValActualT]]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> type[Mapping[str, ValWireT]]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(
        self, wire_value: Mapping[str, ValWireT]
    ) -> Mapping[KeyActualT, ValActualT]:
        """Converts wire mapping to actual mapping.

        Args:
            wire_value: Mapping of wire keys to wire values.

        Returns:
            Mapping of converted actual keys to actual values.

        POSTCONDITIONS:
        - MUST convert mapping keys with a key parameter type.
        - MUST convert mapping values with an element parameter type.
        - WHEN constituent conversion fails, MUST propagate ParameterConversionError.
        """
        ...


@poly_type
class Tool(Protocol):
    """Polymorphic service defining an executable action available to an agent."""

    @property
    def name(self) -> ToolName:
        """Name of the tool."""
        ...

    @property
    def description(self) -> ToolDescription:
        """Description of what the tool does."""
        ...

    @property
    def parameters(self) -> Mapping[ParameterName, ToolParameter[Any, Any]]:
        """Input parameters accepted by the tool."""
        ...

    @operation
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[ToolParameter[Any, Any], SomeParameterActualType],
    ) -> ToolResponse:
        """Executes the tool with action parameter bindings.

        Args:
            actual_parameter_bindings: Resolved action parameter bindings.

        Returns:
            The tool response resulting from execution.

        POSTCONDITIONS:
        - WHEN tool-specific execution conditions fail, MUST indicate failure status in the tool response with diagnostic feedback.
        """
        ...


@dataclass(frozen=True)
@data_type
class ToolParameter[ActualT, WireT]:
    """Describes an input parameter accepted by a tool.

    Args:
        name: Parameter name.
        description: Parameter description.
        parameter_type: Parameter type specifying types and conversion.
        is_required: Whether argument is required.
        default_value: Default value when omitted.
        missing_message: Optional function producing diagnostic message when omitted.
    """
    name: ParameterName
    description: ParameterDescription
    parameter_type: ParameterType[ActualT, WireT]
    is_required: bool = ...
    default_value: Optional[ActualT] = ...
    missing_message: Optional[Callable[[Set[ParameterName]], MissingMessage]] = ...


@dataclass(frozen=True)
@data_type
class FollowUpToolCall:
    """Specifies a follow-up tool call.

    Args:
        tool_name: Tool name to call.
        wire_parameter_bindings: Wire parameter bindings.
        reasoning_text: Model reasoning text.
    """
    tool_name: ToolName
    wire_parameter_bindings: Mapping[ParameterName, WireType]
    reasoning_text: Optional[ReasoningText] = ...


@dataclass(frozen=True)
@data_type
class ToolResponse:
    """Communicates tool execution results to the agent.

    Args:
        is_failed: Whether tool execution failed.
        is_terminated: Whether session should terminate.
        content: Execution output or diagnostic message.
        reminder: Advisory guidance for agent.
        suppression_key: Key identifying prior response to supersede.
        follow_up_tool_call: Follow-up tool call to execute.
    """
    is_failed: bool
    is_terminated: bool
    content: ToolResponseContent
    reminder: Optional[ToolReminder] = ...
    suppression_key: Optional[SuppressionKey] = ...
    follow_up_tool_call: Optional[FollowUpToolCall] = ...


@singleton_type("agent_session")
class ToolManager(InTier[AgentSessionTier], Protocol):
    """Session service that maintains and executes tools."""

    @property
    def installed_tools(self) -> Mapping[ToolName, Tool]:
        """Exposes installed tools as a mapping."""
        ...

    @operation
    def install_tool(self, tool: Tool) -> None:
        """Installs tools so they can be executed.

        Args:
            tool: The tool instance to install into the session environment.

        POSTCONDITIONS:
        - MUST install the tool for the agent session.
        """
        ...

    @operation
    def execute_tool(
        self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]
    ) -> ToolResponse:
        """Executes a tool by name with wire parameter bindings.

        Args:
            name: The identifier of the tool to execute.
            wire_parameter_bindings: Wire parameter bindings.

        Returns:
            The tool response resulting from execution.

        POSTCONDITIONS:
        - WHEN calling a tool whose name does not match any installed tool, MUST fail with feedback citing the unknown tool and listing installed tools.
        - WHEN a call omits a required parameter specifying a missing note evaluated against present parameters, MUST fail with feedback citing the missing parameter and missing note.
        - WHEN a call omits a required parameter lacking a missing note, MUST fail with feedback citing the missing parameter.
        - WHEN a call omits a non-required parameter specifying a default value, MUST bind the default value for the call.
        - WHEN wire conversion fails for a parameter, MUST fail with feedback citing the parameter name and the conversion failure feedback.
        - WHEN all parameter symbols resolve, required parameters are present, defaults are applied, and wire conversions succeed, MUST call the tool with action parameter bindings and return its tool response.
        """
        ...
