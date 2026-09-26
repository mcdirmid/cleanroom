from typing import Any, Mapping, Set, Self
from framework import operation, override, singleton_type
import tool_provider


@singleton_type("agent_session")
class ToolManager(tool_provider.ToolManager):
    """Implements tool manager as an in-memory session registry maintaining tools installed during an agent session.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, ToolManager maintains the active session registry of installed tools and handles dynamic tool lookup and execution without external singleton dependencies.
    """

    @property
    @override
    def installed_tools(self) -> Set[tool_provider.Tool]:
        """Exposes installed tools to inform the agent of what tools it can execute.

        GROUNDING_IMPLEMENTS:
        - knows("installed_tools", Set[tool_provider.Tool]): Tracks installed tools in session registry.
        """
        ...

    @operation
    @override
    def install_tool(self, tool: tool_provider.Tool) -> None:
        """Installs tools so they can be executed by the agent.

        Args:
            tool: Tool instance to install.

        GROUNDING_IMPLEMENTS:
        - action("install_tool", None): Registers tool in session registry.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, name: str, wire_parameter_bindings: tool_provider.WireParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executes an installed tool with converted actual parameter bindings.

        Args:
            name: Tool name to execute.
            wire_parameter_bindings: Wire parameter bindings.

        Returns:
            The tool response or execution failure feedback.

        REQUIREMENTS:
        - Executing a tool by name fails if no installed tool matches the requested name.
        - Executing a tool by name fails if a parameter name does not match any parameter of the tool, and reminds the agent that only declared parameters of the tool can be provided.
        - Executing a tool by name fails if an argument is not supplied for a required parameter of the tool, incorporating the parameter's missing message function evaluated with the set of supplied parameter names when configured, and reminds the agent that required parameters of the tool must be supplied.
        - When an argument is omitted for a parameter that is not required and has a default value, the tool manager binds the default value as the actual parameter value.
        - When parameter mappings are successfully resolved, executing a tool by name executes the matching tool with the resolved actual parameter bindings and returns the tool's response.

        GROUNDING_PROVISIONS:
        - action("execute_tool", tool_provider.ToolResponse): Executes tool by name to satisfy requirements 1, 2, 3, 4, and 5.

        GROUNDING_ARGUMENT:
        - action("execute_tool", Self) :- knows("installed_tools", Self), action("execute_tool", tool_provider.Tool).
        """
        ...

    @operation
    @override
    def execute_tool_with_arguments(
        self, name: str, arguments: Mapping[str, Any]
    ) -> tool_provider.ToolResponse:
        """Executes a tool by converting raw argument mappings into wire parameter bindings.

        Args:
            name: Tool name to execute.
            arguments: Raw argument dictionary.

        Returns:
            The tool response.

        REQUIREMENTS:
        - Executing a tool with arguments converts raw argument mappings into wire parameter bindings and executes the tool by name.

        GROUNDING_PROVISIONS:
        - action("execute_tool_with_arguments", tool_provider.ToolResponse): Converts raw arguments and executes tool to satisfy requirement 6.

        GROUNDING_ARGUMENT:
        - action("execute_tool_with_arguments", Self) :- action("execute_tool", Self).
        """
        ...
