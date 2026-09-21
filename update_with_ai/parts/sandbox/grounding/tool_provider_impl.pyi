from typing import Any, Mapping, Set
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
- When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.
- When parameter mappings are successfully resolved, executing a tool by name executes the matching tool with the resolved actual parameter bindings and returns the tool's response.

INHERITED_REQUIREMENTS:
- [ToolManager] Executing a tool by name with wire parameter bindings produces the tool response upon resolving parameter conversions.

GROUNDING_ARGUMENT:
- Receives tool name and wire parameter bindings as arguments, looks up the tool in self.installed_tools, resolves and converts parameter values using the tool's parameter converters, and invokes the matching tool's execute_tool operation directly.
"""
        ...

    @operation
    @override
    def execute_tool_with_arguments(self, name: str, arguments: Mapping[str, Any]) -> tool_provider.Response:
        """
PURPOSE:
Executes a tool by converting raw argument mappings into wire parameter bindings and delegating to tool execution by name

FRESH_REQUIREMENTS:
- Executing a tool with arguments converts raw argument mappings into wire parameter bindings and executes the tool by name.

GROUNDING_ARGUMENT:
- Receives tool name and argument mappings, constructs WireParameterBindings, and delegates to execute_tool.
"""
        ...

    @operation
    @override
    def create_tool_callable(self, name: str) -> Any:
        """
PURPOSE:
Constructs an executable callable function with parameter signatures derived from the tool parameters

FRESH_REQUIREMENTS:
- Creating a tool callable constructs a callable function with parameter signatures derived from the tool parameters, executes the tool with supplied arguments upon invocation, and returns the response content combined with reminders when guidance is present.

GROUNDING_ARGUMENT:
- Looks up tool in installed_tools, builds an inspect.Signature from tool parameters, and creates a wrapper calling execute_tool_with_arguments returning output text.
"""
        ...
