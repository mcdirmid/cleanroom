# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 40113c5ac1a9
# --- END CLEANROOM METADATA ---

"""Sandbox file reader implementation low-level specification."""

from typing import Any, Mapping, Optional, Set, Type, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import sandbox_file_reader
import tool_provider


@singleton_type("agent_session")
class ReadManager(sandbox_file_reader.ReadManager):
    """Regulates file reading across session files."""

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        ...

    @operation
    @override
    def can_read(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """Validates read access for external file access or file alias.

        Args:
            path: The file path string or FileAlias to validate.

        Returns:
            Response indicating whether reading is permitted or providing recovery feedback.

        POSTCONDITIONS:
        - WHEN path does not match any declared file workspace path, MUST produce a ToolResponse with failed set to True, content starting with "Error: Unknown file '{path}'. Available files: ", and reminder "Only declared files can be inspected.".
        - WHEN path matches a declared file workspace path, MUST produce a successful ToolResponse indicating access is permitted with content "Access permitted for '{path}'.".
        """
        ...


@singleton_type("agent_session")
class ViewFileTool(sandbox_file_reader.ViewFileTool):
    """Executes file read across declared session files."""

    @operation
    def initialize(self) -> None:
        """Installs the view file tool into the session environment and omits search tool.

        POSTCONDITIONS:
        - MUST install the view file tool for the agent session.
        - MUST omit the search tool.
        """
        ...

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        ...

    @property
    @override
    def description(self) -> tool_provider.ToolDescription:
        ...

    @property
    @override
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        ...

    @property
    @override
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """Reads file content with line number formatting and alias validation.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        POSTCONDITIONS:
        - WHEN target_file is an undeclared unbound file, MUST produce a ToolResponse with failed set to True, content starting with "Error: Unknown file '{path}'. Available files: ", and reminder "Only declared files can be inspected.".
        - WHEN reading a missing read-only file, MUST produce a ToolResponse with failed set to True, content "Error: File '{path}' does not exist on disk.", and reminder "Only declared files can be inspected.".
        - WHEN reading an existing file, MUST format file content with one-indexed right-aligned line numbers followed by a colon and space.
        - WHEN reading a markdown file ending with .md, MUST filter out paragraphs beginning with '> META:'.
        - WHEN reading a read-only markdown file ending with .md, MUST format content with session template parameters.
        - WHEN reading a read-write file that does not exist on disk, MUST treat file content as empty.
        - WHEN reading a read-write file, MUST set suppression key matching the file relative path.
        - WHEN reading a read-only file, MUST omit suppression key and sanitize host paths.
        - WHEN reading a file succeeds, MUST record the read file to establish the session's last read or written file.
        """
        ...


@singleton_type("agent_session")
class RegexPatternParameterType(
    tool_provider.ParameterType[agent_file_alias.RegexPattern, str],
    InTier[AgentSessionTier],
):
    """Converts wire type string into regex pattern."""

    @property
    @override
    def actual_type(self) -> Type[agent_file_alias.RegexPattern]:
        ...

    @property
    @override
    def wire_type(self) -> Type[str]:
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> agent_file_alias.RegexPattern:
        """Converts wire string to regex pattern.

        Args:
            wire_value: The wire string to convert into a regex pattern.

        Returns:
            The constructed RegexPattern.

        POSTCONDITIONS:
        - WHEN wire_value is not a valid regular expression pattern, MUST raise tool_provider.ParameterConversionError with message formatted as "Invalid regex pattern '{wire_value}': {error}".
        - WHEN wire_value is a valid regular expression pattern, MUST return the constructed RegexPattern.
        """
        ...


@singleton_type("agent_session")
class SearchTool(sandbox_file_reader.SearchTool):
    """Searches regex patterns across workspace files."""

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        ...

    @property
    @override
    def description(self) -> tool_provider.ToolDescription:
        ...

    @property
    @override
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        ...

    @property
    @override
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """Searches regex pattern matches across session files.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        POSTCONDITIONS:
        - WHEN regex pattern is invalid, MUST return a ToolResponse with failed set to True and content starting with "Error: Invalid regex pattern ".
        - WHEN matches are found for read-only files, MUST return matched line contents and line numbers sanitized to mask host paths.
        - WHEN matches are found for read-write files, MUST state that matches were found with "{relative_path}: matches found (details hidden to prevent unanchored edits)".
        """
        ...
