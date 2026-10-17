# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:46Z
# CHANGE: Name the installed tool registry per the grounding, copy it for the installed-tools view, list installed tools in stable sorted order, and report conversion diagnostics from the declared message member
# CODE_HASH: 9c506123a9e3
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Dict, Mapping, Optional, Set, cast
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from update_with_ai.parts.agent.lib.agent_session import agent_session
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
from . import tool_provider

# Requirements specified in tool_provider_impl.pyi

class ToolManager(tool_provider.ToolManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._installed_tools: Dict[tool_provider.ToolName, tool_provider.Tool] = {}

    # Contract: ToolManager.installed_tools - exposes installed tools dictionary.
    @property
    def installed_tools(self) -> Mapping[tool_provider.ToolName, tool_provider.Tool]:
        return dict(self._installed_tools)

    # Contract: ToolManager.install_tool - installs tool under tool.name.
    def install_tool(self, tool: tool_provider.Tool) -> None:
        self._installed_tools[tool.name] = tool

    # Contract: ToolManager.execute_tool - validates tool name, parameters, missing required parameters, converts wire types, binds defaults, and dispatches to tool.execute_tool.
    def execute_tool(
        self,
        name: tool_provider.ToolName,
        wire_parameter_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType],
    ) -> tool_provider.ToolResponse:
        if name not in self._installed_tools:
            installed = ", ".join(sorted(str(installed_name) for installed_name in self._installed_tools))
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Unknown tool '{name}'. Installed tools: {installed}"
                ),
            )

        tool = self._installed_tools[name]
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
                    error_msg = str(e.message)
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


class AliasManagerType(tool_provider.AliasManagerType, Singleton):
    tier = agent_session

    # Contract: ParameterType.actual_type - returns FileAlias type.
    @property
    def actual_type(self) -> type[agent_file_alias.FileAlias]:
        return agent_file_alias.FileAlias

    # Contract: ParameterType.wire_type - returns str wire type.
    @property
    def wire_type(self) -> type[str]:
        return str

    # Contract: AliasManagerType.convert - converts wire string to FileAlias via AliasManager.
    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for file alias, got {type(wire_value).__name__}"
                )
            )
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return alias_mgr.to_alias(wire_value)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ToolManager,
        keys=[ToolManager, tool_provider.ToolManager],
        tier=agent_session,
    )
    reg.register_singleton(
        AliasManagerType,
        keys=[AliasManagerType, tool_provider.AliasManagerType],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
