# Requirements specified in tool_provider_impl.pyi
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Set, Tuple, Type
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from update_with_ai.parts.agent.lib.agent_session import agent_session


class ToolManager(tool_provider.ToolManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._tools: Dict[str, tool_provider.Tool] = {}

    @property
    def installed_tools(self) -> Set[tool_provider.Tool]:
        return set(self._tools.values())

    def install_tool(self, tool: tool_provider.Tool) -> None:
        self._tools[tool.name] = tool

    def execute_tool(
        self, name: str, wire_parameter_bindings: tool_provider.WireParameterBindings
    ) -> tool_provider.Response:
        # Requirement: Executing a tool by name fails if no installed tool matches the requested name.
        tool = self._tools.get(name)
        if tool is None:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Unknown tool '{name}'. Installed tools: {', '.join(self._tools.keys())}",
            )

        wire_dict = dict(wire_parameter_bindings.bindings)
        params_by_name = {p.name: p for p in tool.parameters}

        # Requirement: Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
        for p_name in wire_dict:
            if p_name not in params_by_name:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: Unknown parameter '{p_name}' for tool '{name}'. Valid parameters: {', '.join(params_by_name.keys())}",
                    reminder="Only declared parameters of the tool can be provided.",
                )

        # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
        actual_bindings: Set[Tuple[tool_provider.Parameter, object]] = set()
        for p_name, p in params_by_name.items():
            if p_name not in wire_dict:
                if p.is_required:
                    content = f"Error: Required parameter '{p_name}' missing for tool '{name}'."
                    if p.missing_message is not None:
                        note = p.missing_message(set(wire_dict.keys()))
                        if note:
                            content += f" Note: {note}"
                    return tool_provider.Response(
                        is_failed=True,
                        is_terminated=False,
                        content=content,
                        reminder="Required parameters of the tool must be supplied.",
                    )
                # Requirement: When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.
                if p.default_value is not None:
                    actual_bindings.add((p, p.default_value))
            else:
                raw_val = wire_dict[p_name]
                conv_val = p.parameter_type.convert(raw_val)
                actual_bindings.add((p, conv_val))

        # Requirement: When parameter mappings are successfully resolved, executing a tool by name executes the matching tool with the resolved actual parameter bindings and returns the tool's response.
        # Requirement: [ToolManager] Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.
        return tool.execute_tool(
            tool_provider.ActualParameterBindings(bindings=actual_bindings)
        )

    def execute_tool_with_arguments(
        self, name: str, arguments: Mapping[str, Any]
    ) -> tool_provider.Response:
        # Requirement: Executing a tool with arguments converts raw argument mappings into wire parameter bindings and executes the tool by name.
        wire_bindings = tool_provider.WireParameterBindings.from_dict(arguments)
        return self.execute_tool(name, wire_bindings)


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
            getattr(tool_provider, "StringParameterType", tool_provider.IdentityParameterType),
            getattr(tool_provider, "StringParameterConverter", tool_provider.IdentityParameterType),
            tool_provider.ParameterType,
        ],
        tier=agent_session,
    )
    int_type = tool_provider.IdentityParameterType(int)
    reg.register_instance(
        int_type,
        keys=[
            getattr(tool_provider, "IntegerParameterType", tool_provider.IdentityParameterType),
            getattr(tool_provider, "IntegerParameterConverter", tool_provider.IdentityParameterType),
        ],
        tier=agent_session,
    )
    bool_type = tool_provider.IdentityParameterType(bool)
    reg.register_instance(
        bool_type,
        keys=[
            getattr(tool_provider, "BooleanParameterType", tool_provider.IdentityParameterType),
            getattr(tool_provider, "BooleanParameterConverter", tool_provider.IdentityParameterType),
        ],
        tier=agent_session,
    )
    float_type = tool_provider.IdentityParameterType(float)
    reg.register_instance(
        float_type,
        keys=[
            getattr(tool_provider, "FloatParameterType", tool_provider.IdentityParameterType),
            getattr(tool_provider, "FloatParameterConverter", tool_provider.IdentityParameterType),
        ],
        tier=agent_session,
    )

