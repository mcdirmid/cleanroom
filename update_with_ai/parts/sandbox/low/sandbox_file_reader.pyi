# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a8f4475e75da
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox file reader low-level interface specification."""

from typing import Any, Mapping, Optional, Protocol, Set, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import tool_provider


@singleton_type("agent_session")
class ReadManager(InTier[AgentSessionTier], Protocol):
    """Regulates workspace file reading."""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """Exposes the session read-only files.

        POSTCONDITIONS:
        - MUST expose declared read-only files from other objects.
        """
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Exposes the session read-write files.

        POSTCONDITIONS:
        - MUST expose declared read-write files from other objects.
        """
        ...

    @operation
    def can_read(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """Validates inspection access for a file path or alias.

        Args:
            path: The file path string or FileAlias to validate.

        Returns:
            Response indicating whether reading is permitted or providing recovery feedback.

        POSTCONDITIONS:
        - WHEN checking read access for a workspace path matching declared files, MUST confirm access.
        - WHEN checking read access for an undeclared workspace path, MUST fail with guidance listing readable file aliases.
        """
        ...


@singleton_type("agent_session")
class ViewFileTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Reads file content."""

    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """Parameter identifying the file alias to read.

        POSTCONDITIONS:
        - MUST specify the file alias path parameter converted using a parameter converter.
        """
        ...

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Name of the tool.

        POSTCONDITIONS:
        - MUST return 'view_file'.
        """
        ...

    @property
    @override
    def description(self) -> tool_provider.ToolDescription:
        """Description of what the tool does.

        POSTCONDITIONS:
        - MUST describe viewing workspace file content with line numbers using the file alias short name.
        """
        ...

    @property
    @override
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """Set of parameters accepted by the tool.

        POSTCONDITIONS:
        - MUST return a set containing strictly the path parameter.
        """
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """Executes the view file tool with actual parameter bindings.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        POSTCONDITIONS:
        - MUST retrieve file content for the specified file alias path.
        """
        ...


@singleton_type("agent_session")
class SearchTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Searches pattern matches across the session's read-only and read-write files."""

    @property
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        """Parameter specifying the regex pattern to search for.

        POSTCONDITIONS:
        - MUST specify the regex pattern parameter converted using a parameter converter.
        """
        ...

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Name of the tool.

        POSTCONDITIONS:
        - MUST return 'search_files'.
        """
        ...

    @property
    @override
    def description(self) -> tool_provider.ToolDescription:
        """Description of what the tool does.

        POSTCONDITIONS:
        - MUST describe searching for regex pattern matches across session files.
        """
        ...

    @property
    @override
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """Set of parameters accepted by the tool.

        POSTCONDITIONS:
        - MUST return a set containing strictly the regex pattern parameter.
        """
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """Executes the search tool with actual parameter bindings.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        POSTCONDITIONS:
        - MUST discover pattern matches across read-only and read-write files.
        """
        ...
