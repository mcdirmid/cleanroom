# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T03:48:24Z
# CHANGE: Import file_paths and cite its real path resolution members in read realizations
# CODE_HASH: 3dc6e437ac6d
# SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
# --- END CLEANROOM METADATA ---

"""Sandbox file reader implementation low-level specification."""

from typing import Any, Mapping, Set, Type, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import file_paths
import sandbox_file_editor
import sandbox_file_reader
import template_format
import tool_provider


@singleton_type("agent_session")
class ReadManager(sandbox_file_reader.ReadManager):
    """Regulates file reading across session files.

    GROUNDING:
    - Reads the declared files from agent_node_config.NodeConfig.read_only_files and
      agent_node_config.NodeConfig.read_write_files, matching a supplied path against the
      agent_file_alias.BoundFile.relative_path and workspace_path members of the collected
      agent_file_alias.ReadOnlyFile and agent_file_alias.ReadWriteFile records.
    - Reports the available file aliases by projecting relative_path from those collected records
      within the agent session tier.
    - Validates and resolves the workspace path recorded on each matched
      agent_file_alias.BoundFile through the file_paths.FilePathManager.create_workspace_path and
      file_paths.FilePathManager.resolve_path operations before reporting read access.
    """

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """Exposes session read-only files.

        GROUNDING:
        - Exposes the agent_file_alias.ReadOnlyFile records held by
          agent_node_config.NodeConfig.read_only_files without mutating the declared collection.
        """
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Exposes session read-write files.

        GROUNDING:
        - Exposes the agent_file_alias.ReadWriteFile records held by
          agent_node_config.NodeConfig.read_write_files without mutating the declared collection.
        """
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

        GROUNDING:
        - Matches path against the agent_file_alias.BoundFile.relative_path and workspace_path members
          of the agent_file_alias.ReadOnlyFile and agent_file_alias.ReadWriteFile records exposed by
          agent_node_config.NodeConfig, lists the projected relative paths as available files when
          no declared file matches, and returns the resulting tool_provider.ToolResponse.
        """
        ...


@singleton_type("agent_session")
class ViewFileTool(sandbox_file_reader.ViewFileTool):
    """Executes file read across declared session files.

    GROUNDING:
    - Resolves host file content through the pathlib filesystem operations declared by the
      filesystem_ext external boundary, reads the workspace path recorded on the resolved
      agent_file_alias.BoundFile of the agent_file_alias.ReadOnlyFile or
      agent_file_alias.ReadWriteFile, and realizes read-only formatting with
      template_format.TemplateFormatter.format_template projected over
      agent_node_config.NodeConfig.template_parameters.
    - Resolves the workspace path recorded on the bound file against the agent_file_alias.AliasManager
      workspace root through the file_paths.FilePathManager.resolve_path operation to obtain the
      host path read for the tool response.
    - Applies the agent_file_alias.AliasManager.sanitize_text masking of host paths for read-only
      responses, carries the alias relative path as the tool_provider.SuppressionKey value for
      read-write responses, and records successful reads by mutating session edit state through
      sandbox_file_editor.EditManager.record_file_read.
    """

    @operation
    def initialize(self) -> None:
        """Installs the view file tool into the session environment.

        POSTCONDITIONS:
        - MUST install the view file tool for the agent session.

        GROUNDING:
        - Registers this view file tool instance through tool_provider.ToolManager.install_tool so
          the agent session can execute it by tool_provider.ToolName.
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

        GROUNDING:
        - Resolves the bound target file through agent_file_alias.AliasManager.convert, reads host
          content with the pathlib filesystem operations declared by the filesystem_ext external
          boundary for the workspace path recorded on the bound file, and enumerates the content
          one-indexed with right-aligned numbering.
        - Passes read-only markdown content through
          template_format.TemplateFormatter.format_template with the bindings of
          agent_node_config.NodeConfig.template_parameters, drops '> META:' paragraphs, masks host
          paths through agent_file_alias.AliasManager.sanitize_text, sets the suppressed
          tool_provider.ToolResponse.suppression_key from the alias relative path for read-write
          files, and mutates session edit state through
          sandbox_file_editor.EditManager.record_file_read on success.
        """
        ...


@singleton_type("agent_session")
class RegexPatternParameterType(
    tool_provider.ParameterType[agent_file_alias.RegexPattern, str],
    InTier[AgentSessionTier],
):
    """Converts wire type string into regex pattern.

    GROUNDING:
    - Compiles the wire string with re.compile, catching re.error and raising
      tool_provider.ParameterConversionError for the tool_provider.ParameterType.convert contract.
    - Applies the converted agent_file_alias.RegexPattern to the workspace paths resolved by
      file_paths.FilePathManager.resolve_path when the regex pattern parameter type is used by the
      search tool.
    """

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

        GROUNDING:
        - Uses re.compile to parse the pattern, returning the constructed
          agent_file_alias.RegexPattern wire text or raising
          tool_provider.ParameterConversionError on regex syntax error.
        """
        ...


@singleton_type("agent_session")
class SearchTool(sandbox_file_reader.SearchTool):
    """Searches regex patterns across workspace files.

    GROUNDING:
    - Iterates the agent_file_alias.ReadOnlyFile and agent_file_alias.ReadWriteFile records exposed
      by agent_node_config.NodeConfig.read_only_files and
      agent_node_config.NodeConfig.read_write_files, scanning host content read for the recorded
      workspace path through the pathlib filesystem operations declared by the filesystem_ext
      external boundary.
    - Matches lines with the compiled agent_file_alias.RegexPattern parameter, reports the sanitized
      one-indexed line numbers and line contents produced by
      agent_file_alias.AliasManager.sanitize_text for read-only files, and withholds line contents
      for read-write files within the agent session tier.
    - Resolves each declared file workspace path recorded on the iterated
      agent_file_alias.ReadOnlyFile and agent_file_alias.ReadWriteFile records into a host path
      through the file_paths.FilePathManager.resolve_path operation before scanning the file
      content.
    """

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

        GROUNDING:
        - Resolves the compiled agent_file_alias.RegexPattern from the invocation bindings, scans the
          host content of the declared read-only and read-write files for the recorded workspace
          path, sanitizes read-only matched lines through
          agent_file_alias.AliasManager.sanitize_text, and withholds read-write line contents while
          reporting the agent_file_alias.FileAlias.relative_path of each matching file.
        """
        ...
