"""Tool provider grounding implementation module."""

from __future__ import annotations
from typing import Any, Callable, Mapping, Set, cast
from support.lib.grounding_support import key, value, only_elem
from parts.sandbox.grounding import tool_provider


class ToolManager(tool_provider.ToolManager):
    """Grounding implementation discharging state obligations for ToolManager.

    DISCHARGED:
    - installed_tools: Discharges the DEFERRED requirement from tool_provider.ToolManager via internal dictionary storage self._tools.
    - install_tool: Discharges the DEFERRED requirement from tool_provider.ToolManager by updating self._tools with the installed tool instance.
    - execute_tool: Discharges the execution, parameter validation, error formatting, and conversion obligations.
    """

    def __init__(self) -> None:
        self._tools: dict[tool_provider.ToolName, tool_provider.Tool] = {}

    @property
    def installed_tools(self) -> Mapping[tool_provider.ToolName, tool_provider.Tool]:
        """
        COVERED:
        - Discharges the installed_tools obligation with concrete internal state.
        """
        _tools: Mapping[tool_provider.ToolName, tool_provider.Tool] = self._tools
        raise NotImplementedError

    def install_tool(self, tool: tool_provider.Tool) -> None:
        """
        COVERED:
        - Discharges the install_tool obligation by updating internal state.
        """
        _name: tool_provider.ToolName = tool.name
        self._tools = {tool.name: tool}
        raise NotImplementedError

    def execute_tool(
        self,
        name: tool_provider.ToolName,
        wire_parameter_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN no installed tool matches name, MUST fail with content formatted as "Error: Unknown tool '{name}'. Installed tools: {installed_tools}".
          - Condition knowledge: test name in self._tools.
          - Consequent knowledge: format error content citing name and installed tools keys.
        - WHEN parameter bindings contain a name that does not match known parameters of the tool, MUST fail with content formatted as "Error: Unknown parameter '{param_name}' for tool '{tool_name}'. Valid parameters: {valid_parameters}" and reminder "Only declared parameters of the tool can be provided.".
          - Condition knowledge: test unknown param in wire_parameter_bindings.
          - Consequent knowledge: format error content and reminder.
        - WHEN a call omits a required parameter configuring a missing note evaluated against present parameters, MUST fail with content formatted as "Error: Required parameter '{param_name}' missing for tool '{tool_name}'. Note: {note}" and reminder "Required parameters of the tool must be supplied.".
          - Condition knowledge: test required param omitted and missing_message is not None.
          - Consequent knowledge: evaluate missing note callback against present parameters and format error content and reminder.
        - WHEN a call omits a required parameter lacking a configured missing note, MUST fail with content formatted as "Error: Required parameter '{param_name}' missing for tool '{tool_name}'." and reminder "Required parameters of the tool must be supplied.".
          - Condition knowledge: test required param omitted and missing_message is None.
          - Consequent knowledge: format error content and reminder.
        - WHEN an argument is omitted for a parameter that is not required and has a default value, MUST bind the default value as the actual parameter value.
          - Condition knowledge: test not param.is_required and param.default_value is not None.
          - Consequent knowledge: bind default value to action parameter bindings.
        - WHEN parameter conversion raises ParameterConversionError, MUST fail tool execution with content formatted as "Error: Invalid argument for parameter '{param_name}': {error_message}" and reminder "Parameters must match their declared wire types.".
          - Condition knowledge: test ParameterConversionError feedback.
          - Consequent knowledge: format error content and reminder.
        - WHEN parameter mappings are successfully resolved, MUST execute the matching tool with the resolved actual parameter bindings and return the tool's response.
          - Condition knowledge: convert wire value and construct action bindings.
          - Consequent knowledge: invoke tool.execute_tool(action_bindings) and return response.        """
        # 1. Unknown tool detection
        _is_unknown: bool = name not in self._tools
        _installed_list: str = ", ".join(self._tools.keys())
        _unknown_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Unknown tool '{name}'. Installed tools: {_installed_list}",
        )

        tool: tool_provider.Tool = self._tools[name]
        params: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = tool.parameters
        _valid_params_str: str = ", ".join(params.keys())

        # 2. Unknown parameter detection
        sample_wire_param_name: tool_provider.ParameterName = key(wire_parameter_bindings)
        _is_param_unknown: bool = sample_wire_param_name not in params
        _unknown_param_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Unknown parameter '{sample_wire_param_name}' for tool '{name}'. Valid parameters: {_valid_params_str}",
            reminder=tool_provider.ToolReminder("Only declared parameters of the tool can be provided."),
        )

        # 3. Missing required parameter with note
        sample_param: tool_provider.ToolParameter[Any, Any] = value(params)
        present_params: Set[tool_provider.ParameterName] = set(wire_parameter_bindings.keys())
        note_fn: Callable[[Set[tool_provider.ParameterName]], str] = sample_param.missing_message or (lambda s: "")
        evaluated_note: str = note_fn(present_params)
        _missing_with_note_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Required parameter '{sample_param.name}' missing for tool '{name}'. Note: {evaluated_note}",
            reminder=tool_provider.ToolReminder("Required parameters of the tool must be supplied."),
        )

        # 4. Missing required parameter without note
        _missing_without_note_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Required parameter '{sample_param.name}' missing for tool '{name}'.",
            reminder=tool_provider.ToolReminder("Required parameters of the tool must be supplied."),
        )

        # 5. Default value binding
        _has_default: bool = not sample_param.is_required and sample_param.default_value is not None
        default_actual: tool_provider.SomeParameterActualType = tool_provider.SomeParameterActualType(
            sample_param.default_value
        )
        _default_bindings = {sample_param: default_actual}

        # 6. Conversion failure
        pt = sample_param.parameter_type
        dummy_err = tool_provider.ParameterConversionError(message="bad format")
        _conv_err_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Invalid argument for parameter '{sample_param.name}': {dummy_err.message}",
            reminder=tool_provider.ToolReminder("Parameters must match their declared wire types."),
        )

        # 7. Successful conversion and execution
        sample_wire_val = wire_parameter_bindings[sample_wire_param_name]
        converted_val = pt.convert(sample_wire_val)
        actual_bindings = {
            sample_param: tool_provider.SomeParameterActualType(converted_val)
        }
        _response: tool_provider.ToolResponse = tool.execute_tool(actual_bindings)
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes the ToolManager singleton in the agent session tier."""
    _instance: ToolManager = cast(ToolManager, None)
