from typing import Set, Type
from framework import operation, override, singleton_type
import tool_provider

@singleton_type('agent_session')
class ToolManager(tool_provider.ToolManager):
    """
PURPOSE:
Implements tool manager as an in-memory session registry maintaining tools installed during an agent session

GROUNDING_ARGUMENT:
- As an agent_session singleton, ToolManager maintains the active session registry of installed tools and handles dynamic tool lookup and execution without external singleton dependencies.
"""

    @property
    @override
    def installed_tools(self) -> Set[tool_provider.Tool]:
        """
PURPOSE:
Exposes installed tools to inform the agent of what tools it can execute

GROUNDING_ARGUMENT:
- Internal registry set maintained within the agent_session singleton, initialized empty and populated via mutable operation install_tool.
"""
        ...

    @operation
    @override
    def install_tool(self, tool: tool_provider.Tool) -> None:
        """
PURPOSE:
Installs tools so they can be executed by the agent

INHERITED_ASSUMPTIONS:
- [ToolManager] All installed tools in a tool manager have unique names.

GROUNDING_ARGUMENT:
- Receives tool directly as a parameter and registers it in self.installed_tools.
"""
        ...

    @operation
    @override
    def execute_tool(self, name: str, wire_parameter_bindings: tool_provider.WireParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executes an installed tool with converted actual parameter bindings, failing if the tool is uninstalled or parameter mappings cannot be resolved

FRESH_REQUIREMENTS:
- Executing a tool by name fails if no installed tool matches the requested name.
- Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
- Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, and reminds the agent that required parameters of the tool must be supplied.
- When parameter mappings are successfully resolved, executing a tool by name delegates to the matching tool with the resolved actual parameter bindings and returns the tool's response.

INHERITED_REQUIREMENTS:
- [ToolManager] Executing a tool by name with wire parameter bindings produces the same response as executing the tool directly.

GROUNDING_ARGUMENT:
- Receives tool name and wire parameter bindings as arguments, looks up the tool in self.installed_tools, resolves and converts parameter values using the tool's parameter converters, and invokes the matching tool's execute_tool operation directly.
"""
        ...

@singleton_type('agent_session')
class StringParameterConverter(tool_provider.StringParameterConverter):
    """
PURPOSE:
Implements string parameter converter for identity string parameter conversion

GROUNDING_ARGUMENT:
- As an agent_session singleton, StringParameterConverter performs identity string parameter conversion without external dependencies.
"""

    @operation
    @override
    def convert(self, wire_value: str) -> str:
        """
PURPOSE:
Returns the wire string directly as its actual value

FRESH_REQUIREMENTS:
- Converting a wire type string produces that string directly as its actual value.

GROUNDING_ARGUMENT:
- Receives wire_value directly as a parameter and returns the string value unchanged.
"""
        ...

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
Sets the converter actual type to string

GROUNDING_ARGUMENT:
- Constant type descriptor identifying str.
"""
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
Sets the converter wire type to string

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying WireType.STRING.
"""
        ...

@singleton_type('agent_session')
class IntegerParameterConverter(tool_provider.IntegerParameterConverter):
    """
PURPOSE:
Implements integer parameter converter for identity integer parameter conversion

GROUNDING_ARGUMENT:
- As an agent_session singleton, IntegerParameterConverter performs identity integer parameter conversion without external dependencies.
"""

    @operation
    @override
    def convert(self, wire_value: int) -> int:
        """
PURPOSE:
Returns the wire integer directly as its actual value

FRESH_REQUIREMENTS:
- Converting a wire type integer produces that integer directly as its actual value.

GROUNDING_ARGUMENT:
- Receives wire_value directly as a parameter and returns the integer value unchanged.
"""
        ...

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
Sets the converter actual type to integer

GROUNDING_ARGUMENT:
- Constant type descriptor identifying int.
"""
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
Sets the converter wire type to integer

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying WireType.INTEGER.
"""
        ...

@singleton_type('agent_session')
class BooleanParameterConverter(tool_provider.BooleanParameterConverter):
    """
PURPOSE:
Implements boolean parameter converter for identity boolean parameter conversion

GROUNDING_ARGUMENT:
- As an agent_session singleton, BooleanParameterConverter performs identity boolean parameter conversion without external dependencies.
"""

    @operation
    @override
    def convert(self, wire_value: bool) -> bool:
        """
PURPOSE:
Returns the wire boolean directly as its actual value

FRESH_REQUIREMENTS:
- Converting a wire type boolean produces that boolean directly as its actual value.

GROUNDING_ARGUMENT:
- Receives wire_value directly as a parameter and returns the boolean value unchanged.
"""
        ...

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
Sets the converter actual type to boolean

GROUNDING_ARGUMENT:
- Constant type descriptor identifying bool.
"""
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
Sets the converter wire type to boolean

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying WireType.BOOLEAN.
"""
        ...
