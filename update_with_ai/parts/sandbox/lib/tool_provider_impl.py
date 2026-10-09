# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T02:22:49Z
# CHANGE: Implement ToolManager in tool_provider_impl.py
# CODE_HASH: cb1750fb6400
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Dict, Mapping, Optional, Set, cast
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from update_with_ai.parts.agent.lib.agent_session import agent_session
from . import tool_provider

# Requirements specified in tool_provider_impl.pyi

class ToolManager(tool_provider.ToolManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._tools: Dict[tool_provider.ToolName, tool_provider.Tool] = {}

    @property
    def installed_tools(self) -> Mapping[tool_provider.ToolName, tool_provider.Tool]:
        return dict(self._tools)

    def install_tool(self, tool: tool_provider.Tool) -> None:
        self._tools[tool.name] = tool

    def execute_tool(
        self,
        name: tool_provider.ToolName,
        wire_parameter_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType],
    ) -> tool_provider.ToolResponse:
        if name not in self._tools:
            installed = ", ".join(sorted(self._tools.keys()))
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Unknown tool '{name}'. Installed tools: {installed}"
                ),
            )

        tool = self._tools[name]
        valid_parameters = ", ".join(sorted(tool.parameters.keys()))

        for param_name in wire_parameter_bindings:
            if param_name not in tool.parameters:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: Unknown parameter '{param_name}' for tool '{tool.name}'. Valid parameters: {valid_parameters}"
                    ),
                    reminder=tool_provider.ToolReminder("Only declared parameters of the tool can be provided."),
                )

        present_params: Set[tool_provider.ParameterName] = set(wire_parameter_bindings.keys())
        for param_name, param in tool.parameters.items():
            if param.is_required and param_name not in present_params:
                if param.missing_message is not None:
                    note = param.missing_message(present_params)
                    return tool_provider.ToolResponse(
                        is_failed=True,
                        is_terminated=False,
                        content=tool_provider.ToolResponseContent(
                            f"Error: Required parameter '{param_name}' missing for tool '{tool.name}'. Note: {note}"
                        ),
                        reminder=tool_provider.ToolReminder("Required parameters of the tool must be supplied."),
                    )
                else:
                    return tool_provider.ToolResponse(
                        is_failed=True,
                        is_terminated=False,
                        content=tool_provider.ToolResponseContent(
                            f"Error: Required parameter '{param_name}' missing for tool '{tool.name}'."
                        ),
                        reminder=tool_provider.ToolReminder("Required parameters of the tool must be supplied."),
                    )

        actual_bindings: Dict[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType] = {}
        for param_name, param in tool.parameters.items():
            if param_name in wire_parameter_bindings:
                wire_val = wire_parameter_bindings[param_name]
                try:
                    actual_val = param.parameter_type.convert(cast(Any, wire_val))
                except tool_provider.ParameterConversionError as e:
                    error_msg = e.message if hasattr(e, "message") else str(e)
                    return tool_provider.ToolResponse(
                        is_failed=True,
                        is_terminated=False,
                        content=tool_provider.ToolResponseContent(
                            f"Error: Invalid argument for parameter '{param_name}': {error_msg}"
                        ),
                        reminder=tool_provider.ToolReminder("Parameters must match their declared wire types."),
                    )
                actual_bindings[param] = cast(tool_provider.SomeParameterActualType, actual_val)
            elif not param.is_required and param.default_value is not None:
                actual_bindings[param] = cast(tool_provider.SomeParameterActualType, param.default_value)

        return tool.execute_tool(actual_bindings)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ToolManager,
        keys=[ToolManager, tool_provider.ToolManager],
        tier=agent_session,
    )

_initialize_ = __initialize__
