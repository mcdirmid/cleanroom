from typing import Dict, Optional, Set, Tuple, Type
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry

class ToolManager(tool_provider.ToolManager, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._tools: Dict[str, tool_provider.Tool] = {}

    @property
    def installed_tools(self) -> Set[tool_provider.Tool]:
        # Requirement: Expose installed tools to inform the agent of what tools it can execute
        return set(self._tools.values())

    def install_tool(self, tool: tool_provider.Tool) -> None:
        # Requirement: Register tool in installed tools set
        self._tools[tool.name] = tool

    def execute_tool(
        self, name: str, wire_parameter_bindings: tool_provider.WireParameterBindings
    ) -> tool_provider.Response:
        # Requirement: Fail if no installed tool matches the requested name
        tool = self._tools.get(name)
        if tool is None:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Unknown tool '{name}'. Installed tools: {', '.join(self._tools.keys())}",
            )

        wire_dict = dict(wire_parameter_bindings.bindings)
        params_by_name = {p.name: p for p in tool.parameters}

        # Requirement: Fail if a parameter name does not match any parameter of the tool
        for p_name in wire_dict:
            if p_name not in params_by_name:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: Unknown parameter '{p_name}' for tool '{name}'. Valid parameters: {', '.join(params_by_name.keys())}",
                )

        # Requirement: Fail if an argument is not supplied for a required parameter of the tool
        actual_bindings: Set[Tuple[tool_provider.Parameter, object]] = set()
        for p_name, p in params_by_name.items():
            if p_name not in wire_dict:
                if p.is_required:
                    return tool_provider.Response(
                        is_failed=True,
                        is_terminated=False,
                        content=f"Error: Required parameter '{p_name}' missing for tool '{name}'.",
                    )
            else:
                raw_val = wire_dict[p_name]
                conv_val = p.parameter_converter.convert(raw_val)
                actual_bindings.add((p, conv_val))

        # Requirement: Delegate to matching tool with resolved actual parameter bindings and return tool response
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
        # Requirement: Convert wire type string directly as its actual value
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
        # Requirement: Convert wire type integer directly as its actual value
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
        # Requirement: Convert wire type boolean directly as its actual value
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
