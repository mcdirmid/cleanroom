from typing import Dict, Optional, Set, Tuple, Type
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

class ToolManager(tool_provider.ToolManager, Singleton):
    tier = "agent_session"

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

        # Requirement: Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, and reminds the agent that required parameters of the tool must be supplied.
        actual_bindings: Set[Tuple[tool_provider.Parameter, object]] = set()
        for p_name, p in params_by_name.items():
            if p_name not in wire_dict:
                if p.is_required:
                    return tool_provider.Response(
                        is_failed=True,
                        is_terminated=False,
                        content=f"Error: Required parameter '{p_name}' missing for tool '{name}'.",
                        reminder="Required parameters of the tool must be supplied.",
                    )
            else:
                raw_val = wire_dict[p_name]
                conv_val = p.parameter_converter.convert(raw_val)
                actual_bindings.add((p, conv_val))

        # Requirement: When parameter mappings are successfully resolved, executing a tool by name delegates to the matching tool with the resolved actual parameter bindings and returns the tool's response.
        return tool.execute_tool(tool_provider.ActualParameterBindings(bindings=actual_bindings))

class StringParameterConverter(tool_provider.StringParameterConverter, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def actual_type(self) -> Type:
        return str

    @property
    def wire_type(self) -> tool_provider.WireType:
        return tool_provider.String()

    def convert(self, wire_value: str) -> str:
        # Requirement: Converting a wire type string produces that string directly as its actual value.
        return str(wire_value)

class IntegerParameterConverter(tool_provider.IntegerParameterConverter, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def actual_type(self) -> Type:
        return int

    @property
    def wire_type(self) -> tool_provider.WireType:
        return tool_provider.Integer()

    def convert(self, wire_value: int) -> int:
        # Requirement: Converting a wire type integer produces that integer directly as its actual value.
        return int(wire_value)

class BooleanParameterConverter(tool_provider.BooleanParameterConverter, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def actual_type(self) -> Type:
        return bool

    @property
    def wire_type(self) -> tool_provider.WireType:
        return tool_provider.Boolean()

    def convert(self, wire_value: bool) -> bool:
        # Requirement: Converting a wire type boolean produces that boolean directly as its actual value.
        return bool(wire_value)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ToolManager,
        keys=[ToolManager, tool_provider.ToolManager],
        tier="agent_session",
    )
    reg.register_singleton(
        StringParameterConverter,
        keys=[
            StringParameterConverter,
            tool_provider.StringParameterConverter,
            tool_provider.IdentityParameterConverter,
            tool_provider.ParameterConverter,
        ],
        tier="agent_session",
    )
    reg.register_singleton(
        IntegerParameterConverter,
        keys=[
            IntegerParameterConverter,
            tool_provider.IntegerParameterConverter,
            tool_provider.IdentityParameterConverter,
            tool_provider.ParameterConverter,
        ],
        tier="agent_session",
    )
    reg.register_singleton(
        BooleanParameterConverter,
        keys=[
            BooleanParameterConverter,
            tool_provider.BooleanParameterConverter,
            tool_provider.IdentityParameterConverter,
            tool_provider.ParameterConverter,
        ],
        tier="agent_session",
    )
