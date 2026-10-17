# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:48:24Z
# CHANGE: Realize delegation of tools with argument mappings to by-name execution
# CODE_HASH: f235aa3793da
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Tool provider low-level implementation specification."""

from typing import Mapping
from framework import operation, override, singleton_type
import file_alias
import tool_provider


@singleton_type("agent_session")
class ToolManager(tool_provider.ToolManager):
    """Implements tool manager as an in-memory session registry maintaining tools installed during an agent session.

    GROUNDING:
    - Maintains the private `_installed_tools` registry dictionary mapping tool_provider.ToolName to
      installed tool_provider.Tool instances within the agent session tier, satisfying the deferred
      backing collection and private mutation provisions of tool_provider_impl planning.
    - Resolves execution by name against that registry, converts wire values through
      tool_provider.ParameterType.convert, and returns tool_provider.ToolResponse records produced
      by tool_provider.Tool.execute_tool.
    - Delegates execution of a tool supplied with argument mappings to execute by name with wire
      parameter bindings, realizing tool_provider.ToolManager.execute_tool by dispatching over the
      `_installed_tools` registry to the matched tool_provider.Tool.execute_tool.
    """

    @property
    @override
    def installed_tools(self) -> Mapping[tool_provider.ToolName, tool_provider.Tool]:
        """Exposes installed tools to inform the agent of what tools it can execute.

        GROUNDING:
        - Exposes the private `_installed_tools` dictionary mapping tool_provider.ToolName to
          tool_provider.Tool instances to callers without copying or mutating backing state.
        """
        ...

    @operation
    @override
    def install_tool(self, tool: tool_provider.Tool) -> None:
        """Installs tools so they can be executed by the agent.

        Args:
            tool: Tool instance to install.

        GROUNDING:
        - Mutates the private `_installed_tools` dictionary by inserting the supplied
          tool_provider.Tool under the key read from tool_provider.Tool.name.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, name: tool_provider.ToolName, wire_parameter_bindings: Mapping[tool_provider.ParameterName, tool_provider.WireType]
    ) -> tool_provider.ToolResponse:
        """Executes a tool with argument mappings by delegating execution to execute by name with wire parameter bindings.

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
        - WHEN parameter conversion raises tool_provider.ParameterConversionError, MUST fail tool execution with content formatted as "Error: Invalid argument for parameter '{param_name}': {error_message}" and reminder "Parameters must match their declared wire types.".
        - WHEN a call supplies argument mappings, MUST delegate execution to execute by name with wire parameter bindings.
        - WHEN parameter mappings are successfully resolved, MUST delegate execution by name with the resolved actual parameter bindings and return the response the tool produces.

        GROUNDING:
        - Resolves name in the private `_installed_tools` dictionary, validates supplied binding keys
          against the keys of tool_provider.Tool.parameters, converts each wire value through the
          bound tool_provider.ToolParameter.parameter_type using
          tool_provider.ParameterType.convert, binds tool_provider.ToolParameter.default_value as the
          actual parameter value for omitted non-required parameters, evaluates
          tool_provider.ToolParameter.missing_message against the present
          tool_provider.ParameterName set for omitted required parameters, then dispatches execution
          through tool_provider.Tool.execute_tool and returns its tool_provider.ToolResponse,
          translating a raised tool_provider.ParameterConversionError into failed response content
          and reminder.
        - Delegates execution of a tool with argument mappings to execute by name with wire parameter
          bindings, resolving the name against the `_installed_tools` registry and dispatching to
          tool_provider.Tool.execute_tool on the matched tool_provider.Tool.
        """
        ...


@singleton_type("agent_session")
class AliasManagerType(tool_provider.AliasManagerType):
    """Realizes the alias manager parameter type adapter within the agent session tier.

    GROUNDING:
    - Resolves file_alias.AliasManager from the agent session tier, converts wire strings via
      file_alias.AliasManager.to_alias, and validates wire value types.
    """

    @property
    @override
    def actual_type(self) -> type[file_alias.FileAlias]:
        """Data type produced by converter."""
        ...

    @property
    @override
    def wire_type(self) -> type[str]:
        """Primitive wire type accepted by converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> file_alias.FileAlias:
        """Converts wire string to file alias using the session alias manager.

        Args:
            wire_value: The wire string to convert into a file alias.

        Returns:
            The resolved FileAlias.

        POSTCONDITIONS:
        - MUST convert wire strings to file aliases via the session alias manager.
        """
        ...
