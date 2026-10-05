# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 7b018032d267
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

# Requirements specified in tool_provider_impl.pyi
from typing import Any, Dict, Mapping, Optional, Set
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from update_with_ai.parts.agent.lib.agent_session import agent_session


class ToolManager(tool_provider.ToolManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._tools: Dict[tool_provider.ToolName, tool_provider.Tool] = {}

    @property
    def installed_tools(self) -> Mapping[tool_provider.ToolName, tool_provider.Tool]:
        return dict(self._tools)

    def install_tool(self, tool: tool_provider.Tool) -> None:
        self._tools[tool_provider.ToolName(tool.name)] = tool

    def execute_tool(
        self,
        name: tool_provider.ToolName,
        wire_parameter_bindings: Mapping[
            tool_provider.ParameterName, tool_provider.WireType
        ],
    ) -> tool_provider.ToolResponse:
        tool = self._tools.get(name)
        if tool is None:
            installed = ", ".join(self._tools.keys())
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Unknown tool '{name}'. Installed tools: {installed}"
                ),
            )

        raw_wire: Any = wire_parameter_bindings
        if isinstance(raw_wire, Mapping):
            wire_dict = {str(k): v for k, v in raw_wire.items()}
        elif hasattr(
            raw_wire, "bindings"
        ):  # pragma: no cover (assumption: arguments conform to Mapping interface)
            wire_dict = {str(k): v for k, v in getattr(raw_wire, "bindings")}
        elif hasattr(
            raw_wire, "items"
        ):  # pragma: no cover (assumption: arguments conform to Mapping interface)
            items_fn: Any = getattr(raw_wire, "items")
            raw_items: Any = items_fn() if callable(items_fn) else items_fn
            wire_dict = {str(k): v for k, v in list(raw_items)}
        else:  # pragma: no cover (assumption: arguments conform to Mapping interface)
            wire_dict = {}

        params_by_name: dict[
            tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
        ] = {}
        for k, v in tool.parameters.items():
            params_by_name[tool_provider.ParameterName(k)] = v

        for p_name in wire_dict:
            if p_name not in params_by_name:
                valid_params = ", ".join(params_by_name.keys())
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: Unknown parameter '{p_name}' for tool '{name}'. Valid parameters: {valid_params}"
                    ),
                    reminder=tool_provider.ToolReminder(
                        "Only declared parameters of the tool can be provided."
                    ),
                )

        actual_bindings: dict[tool_provider.ToolParameter[Any, Any], Any] = {}
        for p_name, p in params_by_name.items():
            if p_name not in wire_dict:
                if p.is_required:
                    note = ""
                    if p.missing_message is not None:
                        note = p.missing_message(
                            {tool_provider.ParameterName(k) for k in wire_dict.keys()}
                        )
                    if note:
                        content = f"Error: Required parameter '{p_name}' missing for tool '{name}'. Note: {note}"
                    else:
                        content = f"Error: Required parameter '{p_name}' missing for tool '{name}'."
                    return tool_provider.ToolResponse(
                        is_failed=True,
                        is_terminated=False,
                        content=tool_provider.ToolResponseContent(content),
                        reminder=tool_provider.ToolReminder(
                            "Required parameters of the tool must be supplied."
                        ),
                    )
                if p.default_value is not None:
                    actual_bindings[p] = p.default_value
            else:
                raw_val = wire_dict[p_name]
                try:
                    conv_val = p.parameter_type.convert(raw_val)
                except tool_provider.ParameterConversionError as e:
                    return tool_provider.ToolResponse(
                        is_failed=True,
                        is_terminated=False,
                        content=tool_provider.ToolResponseContent(
                            f"Error: Invalid argument for parameter '{p_name}': {e.message}"
                        ),
                        reminder=tool_provider.ToolReminder(
                            "Parameters must match their declared wire types."
                        ),
                    )
                actual_bindings[p] = conv_val

        return tool.execute_tool(
            tool_provider._ActionParameterBindings(
                actual_bindings,
                parameters_by_name=params_by_name,
            )
        )

    def execute_tool_with_arguments(
        self,
        name: tool_provider.ToolName,
        arguments: Mapping[tool_provider.ParameterName, tool_provider.WireType],
    ) -> tool_provider.ToolResponse:
        bindings = tool_provider._WireParameterBindings(arguments)
        return self.execute_tool(name, bindings)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ToolManager,
        keys=[ToolManager, tool_provider.ToolManager],
        tier=agent_session,
    )
    str_type = tool_provider.IdentityParameterType(str)
    reg.register_instance(
        str_type,
        keys=[
            tool_provider.IdentityParameterType,
            tool_provider.ParameterType,
        ],
        tier=agent_session,
    )
    int_type = tool_provider.IdentityParameterType(int)
    reg.register_instance(
        int_type,
        keys=[
            tool_provider.IdentityParameterType,
        ],
        tier=agent_session,
    )
    bool_type = tool_provider.IdentityParameterType(bool)
    reg.register_instance(
        bool_type,
        keys=[
            tool_provider.IdentityParameterType,
        ],
        tier=agent_session,
    )
    float_type = tool_provider.IdentityParameterType(float)
    reg.register_instance(
        float_type,
        keys=[
            tool_provider.IdentityParameterType,
        ],
        tier=agent_session,
    )
