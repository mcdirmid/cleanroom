# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 6f33ec7750c9
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Tool provider low-level implementation specification."""

from typing import Mapping
from framework import operation, override, singleton_type
import tool_provider


@singleton_type("agent_session")
class ToolManager(tool_provider.ToolManager):
    """Implements tool manager as an in-memory session registry maintaining tools installed during an agent session.

    GROUNDING:
    - Maintains installed tools in an internal dictionary mapping ToolName to Tool instances within the agent session tier.
    """

    @property
    @override
    def installed_tools(self) -> Mapping[tool_provider.ToolName, tool_provider.Tool]:
        """Exposes installed tools to inform the agent of what tools it can execute.

        GROUNDING:
        - Exposes the internal dictionary mapping ToolName to Tool instances.
        """
        ...

    @operation
    @override
    def install_tool(self, tool: tool_provider.Tool) -> None:
        """Installs tools so they can be executed by the agent.

        Args:
            tool: Tool instance to install.

        GROUNDING:
        - Inserts the tool into the internal installed tools dictionary keyed by tool.name.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, name: tool_provider.ToolName, wire_parameter_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType]
    ) -> tool_provider.ToolResponse:
        """Executes an installed tool with converted actual parameter bindings.

        Args:
            name: Tool name to execute.
            wire_parameter_bindings: Wire parameter bindings.

        Returns:
            The tool response or execution failure feedback.

        POSTCONDITIONS:
        - WHEN no installed tool matches name, MUST fail with content formatted as "Error: Unknown tool '{name}'. Installed tools: {installed_tools}".
        - WHEN parameter bindings contain a name that does not match known parameters of the tool, MUST fail with content formatted as "Error: Unknown parameter '{param_name}' for tool '{tool_name}'. Valid parameters: {valid_parameters}" and reminder "Only declared parameters of the tool can be provided.".
        - WHEN a call omits a required parameter configuring a missing note evaluated against present parameters, MUST fail with content formatted as "Error: Required parameter '{param_name}' missing for tool '{tool_name}'. Note: {note}" and reminder "Required parameters of the tool must be supplied.".
        - WHEN a call omits a required parameter lacking a configured missing note, MUST fail with content formatted as "Error: Required parameter '{param_name}' missing for tool '{tool_name}'." and reminder "Required parameters of the tool must be supplied.".
        - WHEN an argument is omitted for a parameter that is not required and has a default value, MUST bind the default value as the actual parameter value.
        - WHEN parameter conversion raises ParameterConversionError, MUST fail tool execution with content formatted as "Error: Invalid argument for parameter '{param_name}': {error_message}" and reminder "Parameters must match their declared wire types.".
        - WHEN parameter mappings are successfully resolved, MUST execute the matching tool with the resolved actual parameter bindings and return the tool's response.

        GROUNDING:
        - Resolves the tool by name from the internal installed tools dictionary, validates parameters against tool.parameters, converts wire arguments via parameter type conversion, applies defaults, and dispatches execution to tool.execute.
        """
        ...
