from typing import Any, Mapping, Optional, Sequence, Set, Tuple, Type, Union
from framework import operation, override, singleton_type
import agent_config
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

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, ReadManager implements sandbox_file_reader.ReadManager, accessing singletons agent_node_config.NodeConfig, agent_file_alias.AliasManager, sandbox_file_editor.EditManager, and tool_provider.ToolManager in agent_session.
    """

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """Exposes the session read-only files.

        GROUNDING_PROVISIONS:
        - knows("agent_session", Set[agent_file_alias.ReadOnlyFile]): Exposes session read-only files to satisfy requirement 2.

        GROUNDING_ARGUMENT:
        - knows("agent_session", Self) :- knows("read_only_files", agent_node_config.NodeConfig).
        """
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Exposes the session read-write files.

        GROUNDING_PROVISIONS:
        - knows("agent_session", Set[agent_file_alias.ReadWriteFile]): Exposes session read-write files to satisfy requirement 2.

        GROUNDING_ARGUMENT:
        - knows("agent_session", Self) :- knows("read_write_files", agent_node_config.NodeConfig).
        """
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Exposes the session guide file when configured.

        GROUNDING_PROVISIONS:
        - knows("guide_file", Optional[agent_file_alias.UnboundFile]): Exposes guide file.

        GROUNDING_ARGUMENT:
        - knows("guide_file", Self) :- knows("guide_file", agent_node_config.NodeConfig).
        """
        ...

    @operation
    @override
    def can_read(
        self, path: Union[str, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """Validates read access for external file access or file alias.

        Args:
            path: The file path string or FileAlias to validate.

        Returns:
            Response indicating whether reading is permitted or providing recovery feedback.

        REQUIREMENTS:
        - WHEN path does not match any declared file workspace path, MUST produce a Response with failed set to True reminding the agent that only declared files can be read and listing readable file aliases.
        - WHEN path matches a declared file workspace path, MUST produce a successful Response indicating access is permitted.

        GROUNDING_PROVISIONS:
        - action("can_read", tool_provider.ToolResponse): Checks read access for a workspace path to satisfy requirement 4.

        GROUNDING_ARGUMENT:
        - action("can_read", Self) :- knows("agent_session", Self).
        """
        ...


@singleton_type("agent_session")
class ViewFileTool(sandbox_file_reader.ViewFileTool):
    """Executes file read across declared session files.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, ViewFileTool implements tool_provider.Tool, accessing singletons agent_config.AgentConfig in SystemTier, and agent_file_alias.AliasManager, agent_node_config.NodeConfig, sandbox_file_editor.EditManager, template_format.TemplateFormatter, and tool_provider.ToolManager in agent_session.
    """

    @operation
    def initialize(self) -> None:
        """Installs the view file tool into tool manager when mcp mode is inactive and omits search tool.

        REQUIREMENTS:
        - WHEN agent config mcp mode is inactive, MUST install the view file tool for the agent session.
        - WHEN agent config mcp mode is active, MUST install no read tools.
        - MUST omit the search tool.

        GROUNDING_REQUIREMENTS:
        - action("install", Self): Installs view file tool to satisfy requirement 1.
        - knows("mcp_mode", bool): Evaluates mcp mode branch condition to satisfy requirement 1.

        GROUNDING_ARGUMENT:
        - action("install", Self) :- action("install_tool", tool_provider.ToolManager), knows("is_mcp_mode", agent_config.AgentConfig).
        """
        ...

    @property
    @override
    def name(self) -> str:
        """Tool name identifier view_file.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Constant tool name identifier.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Tool description informing why and when to call view_file.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Constant tool description string.
        """
        ...

    @property
    @override
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter accepting the target file alias.

        GROUNDING_PROVISIONS:
        - knows("path_parameter", tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]): Parameter accepting the target file alias.

        GROUNDING_ARGUMENT:
        - knows("path_parameter", Self) :- action("convert", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Set of parameter descriptors accepted by view_file.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Set composed of self's parameter descriptors.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Reads file content with line number formatting and alias validation.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        REQUIREMENTS:
        - WHEN reading a missing read-only file, MUST produce a Response with failed set to True guiding agent recovery.
        - WHEN reading an existing file, MUST format file content with one-indexed right-aligned line numbers followed by a colon and space.
        - WHEN reading a markdown file ending with .md, MUST filter out paragraphs beginning with '> META:'.
        - WHEN reading a read-only markdown file ending with .md, MUST format content with session template parameters.
        - WHEN reading a read-write file that does not exist on disk, MUST treat file content as empty.
        - WHEN reading a read-write file, MUST set suppression key matching the file relative path.
        - WHEN reading a read-only file, MUST omit suppression key and sanitize host paths.
        - WHEN reading a file succeeds, MUST record the read file to establish the session's last read or written file.

        GROUNDING_PROVISIONS:
        - action("execute_tool", tool_provider.ToolResponse): Reads file content to satisfy requirement 3.

        GROUNDING_REQUIREMENTS:
        - action("record_last_read_write", agent_file_alias.FileAlias): Records file read to establish the session's last read or written file to satisfy requirement 3.
        - action("format_template", str): Formats markdown templates with session template parameters to satisfy requirement 3.
        - knows("template_bindings", Mapping[str, Any]): Supplies session template parameters to satisfy requirement 3.
        - action("sanitize", str): Masks host paths in output responses to satisfy requirement 3.

        GROUNDING_ARGUMENT:
        - action("execute_tool", Self) :- action("record_file_read", sandbox_file_editor.EditManager), action("format_template", template_format.TemplateFormatter), knows("template_parameters", agent_node_config.NodeConfig), action("sanitize_text", agent_file_alias.AliasManager).
        """
        ...


@singleton_type("agent_session")
class RegexPatternParameterType(tool_provider.ParameterType[agent_file_alias.RegexPattern, tool_provider.WireString]):
    """Converts wire type string into regex pattern.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, RegexPatternParameterType implements tool_provider.ParameterType[agent_file_alias.RegexPattern, tool_provider.WireString] to convert wire strings to RegexPattern values without requiring external singleton dependencies.
    """

    @property
    @override
    def actual_type(self) -> Type[agent_file_alias.RegexPattern]:
        """Type descriptor identifying RegexPattern.

        GROUNDING_IMPLEMENTS:
        - knows("actual_type", Type[agent_file_alias.RegexPattern]): Constant type descriptor identifying RegexPattern.
        """
        ...

    @property
    @override
    def wire_type(self) -> Type[tool_provider.WireString]:
        """Wire type descriptor identifying String.

        GROUNDING_IMPLEMENTS:
        - knows("wire_type", Type[tool_provider.WireString]): Constant wire type descriptor identifying String.
        """
        ...

    @operation
    @override
    def convert(self, wire_value: tool_provider.WireString) -> agent_file_alias.RegexPattern:
        """Converts wire string to regex pattern.

        Args:
            wire_value: The wire string to convert into a regex pattern.

        Returns:
            The constructed RegexPattern.

        GROUNDING_IMPLEMENTS:
        - action("convert", tool_provider.WireString): Converts wire type string into regex pattern to satisfy requirement 5.
        """
        ...


@singleton_type("agent_session")
class SearchTool(sandbox_file_reader.SearchTool):
    """Searches regex patterns across workspace files.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, SearchTool implements tool_provider.Tool in agent_session, coordinating with imported ReadManager, agent_file_alias.AliasManager, and filesystem_ext in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Tool name identifier search_files.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Constant tool name identifier.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Tool description informing why and when to call search_files.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Constant tool description string.
        """
        ...

    @property
    @override
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, tool_provider.WireString]:
        """Parameter accepting the regex pattern to search.

        GROUNDING_PROVISIONS:
        - knows("regex_pattern_parameter", tool_provider.ToolParameter[agent_file_alias.RegexPattern, tool_provider.WireString]): Parameter accepting the regex pattern to search.

        GROUNDING_ARGUMENT:
        - knows("regex_pattern_parameter", Self) :- action("convert", sandbox_file_reader.RegexPatternParameterType).
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Set of parameter descriptors accepted by search_files.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Set composed of self's parameter descriptor.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Searches regex pattern matches across session files.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        REQUIREMENTS:
        - WHEN regex pattern is invalid, MUST return a Response with failed set to True.
        - WHEN matches are found for read-only files, MUST return matched line contents and line numbers sanitized to mask host paths.
        - WHEN matches are found for read-write files, MUST state that matches were found but cannot be displayed to prevent unanchored edits.

        GROUNDING_PROVISIONS:
        - action("execute_tool", tool_provider.ToolResponse): Searches pattern matches across files to satisfy requirement 6.

        GROUNDING_REQUIREMENTS:
        - knows("agent_session", Set[agent_file_alias.ReadOnlyFile]): Discovers read-only files to satisfy requirement 6.
        - knows("agent_session", Set[agent_file_alias.ReadWriteFile]): Discovers read-write files to satisfy requirement 6.
        - action("sanitize", str): Masks host paths in output responses to satisfy requirement 6.

        GROUNDING_ARGUMENT:
        - action("execute_tool", Self) :- knows("agent_session", sandbox_file_reader.ReadManager), action("sanitize_text", agent_file_alias.AliasManager).
        """
        ...
