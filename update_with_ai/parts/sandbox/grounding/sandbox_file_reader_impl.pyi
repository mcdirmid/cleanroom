from typing import Optional, Set, Type
from framework import operation, override, singleton_type
import agent_file_alias
import filesystem_ext
import agent_node_config
import sandbox_file_editor
import sandbox_file_reader
import template_format
import tool_provider

@singleton_type('agent_session')
class ReadManager(sandbox_file_reader.ReadManager):
    """
PURPOSE:
Implements the read manager to install inspection tools, obtaining declared files and guide file from node config

FRESH_REQUIREMENTS:
- The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.

INHERITED_REQUIREMENTS:
- [ReadManager] The read manager installs the view file tool and search tool.
- [ReadManager] The read manager exposes the session's set of read-only files.
- [ReadManager] The read manager exposes the session's set of read-write files.
- [ReadManager] When step-mode is active, the read manager is configured with a guide file that is an unbound file.

GROUNDING_ARGUMENT:
- As an agent_session singleton, ReadManager coordinates file inspection tools and declared file sets, interacting with imported agent_node_config.NodeConfig and tool_provider.ToolManager in the same session lifecycle tier.
"""

    @property
    @override
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
PURPOSE:
Obtains declared read-only files from node config

GROUNDING_ARGUMENT:
- Delegated from imported collaborator agent_node_config.NodeConfig.read_only_files in the same session lifecycle tier.
"""
        ...

    @property
    @override
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Obtains declared read-write files from node config

GROUNDING_ARGUMENT:
- Delegated from imported collaborator agent_node_config.NodeConfig.read_write_files in the same session lifecycle tier.
"""
        ...

    @property
    @override
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
PURPOSE:
Obtains configured guide file from node config

GROUNDING_ARGUMENT:
- Delegated from imported collaborator agent_node_config.NodeConfig.guide_file in the same session lifecycle tier.
"""
        ...

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Provides that initialization unconditionally installs the view file tool into the tool manager and never installs the search tool

FRESH_REQUIREMENTS:
- The read manager unconditionally installs the view file tool into the tool manager and never installs the search tool.

GROUNDING_ARGUMENT:
- Installs ViewFileTool directly into imported tool_provider.ToolManager in the same session lifecycle tier, and never installs SearchTool.
"""
        ...

@singleton_type('agent_session')
class ViewFileTool(sandbox_file_reader.ViewFileTool):
    """
PURPOSE:
Implements the view file tool to perform workspace file inspection

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The view file tool is named `view_file`.
- The view file tool path parameter uses the alias manager to convert a file alias.

GROUNDING_ARGUMENT:
- As an agent_session singleton, ViewFileTool executes file inspection across declared session files, interacting with imported agent_file_alias.AliasManager, agent_node_config.NodeConfig, template_format.TemplateFormatter, and tool_provider in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the view file tool is named view_file

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('view_file').
"""
        ...

    @property
    @override
    def path_parameter(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Parameter accepting the target file alias

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool on the view file tool to inspect file content with line number formatting and alias validation

FRESH_REQUIREMENTS:
- Executing the view file tool reads file content using the filesystem at the host path formed from the alias manager workspace root and bound file workspace path, returning content formatted with one-indexed right-aligned line numbers followed by a colon and space.
- When the target file does not exist on disk, view file tool execution treats a read-write file as having empty content, and fails with a response guiding agent recovery when inspecting a missing read-only file.
- Executing the view file tool with an unbound file whose relative path or qualified path addresses a module name or ends with .py and matches a declared read-only grounding specification ending with .pyi resolves to that grounding specification file alias.
- Executing the view file tool with an unbound file addressing a test file ending with _test.py fails with a response explaining that test files are not inspectable and grounding specifications serve as the contract.
- Otherwise, executing the view file tool with an unbound file fails with a response guiding agent recovery that lists available readable file aliases, and reminds the agent that only declared files can be inspected.
- When an unbound file equals the guide file configured for step-mode, the view file tool failure response indicates that `advance` must be called to read the guide instead.
- View file tool responses for read-write files carry a suppression key matching the file's relative path, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.
- On successful execution, the view file tool records the read file in the edit manager.
- When reading markdown files ending with .md, paragraphs beginning with > META: are filtered out from the returned content.
- When reading read-only markdown files ending with .md, content is formatted using the template formatter with session template parameters after filtering out paragraphs beginning with > META:.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves host paths using imported agent_file_alias.AliasManager workspace root in the same session lifecycle tier, resolves unbound .py and module requests to matching declared .pyi grounding specifications, rejects test file requests with contract-directed guidance, reads file content via the filesystem, formats lines with one-indexed right-aligned line numbers followed by a colon and space, filters > META: paragraphs for markdown files, formats read-only markdown content using imported template_format.TemplateFormatter and agent_node_config.NodeConfig.template_parameters in the same session lifecycle tier, attaches the file's relative path as a suppression key on responses for read-write files while omitting it for read-only files, masks host paths in read-only output, and records the read file in imported sandbox_file_editor.EditManager in the same session lifecycle tier.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool

GROUNDING_ARGUMENT:
- Constant tool description string.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation

GROUNDING_ARGUMENT:
- Set composed of self's constant parameter descriptors (path_parameter).
"""
        ...

@singleton_type('agent_session')
class RegexPatternParameterType(tool_provider.ParameterType[agent_file_alias.RegexPattern, str]):
    """
PURPOSE:
Defined as a parameter type for regex patterns that converts a wire type string into a regex pattern

GROUNDING_ARGUMENT:
- As an agent_session singleton, RegexPatternParameterType converts wire strings to regex patterns without requiring external singleton dependencies.
"""

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
Sets the converter actual type to regex pattern

GROUNDING_ARGUMENT:
- Constant type descriptor identifying RegexPattern.
"""
        ...

    @property
    @override
    def wire_type(self) -> Type[str]:
        """
PURPOSE:
Sets the converter wire type to string

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying str.
"""
        ...

    @operation
    @override
    def to_actual(self, value: str) -> agent_file_alias.RegexPattern:
        """
PURPOSE:
Converts a wire type string to a regex pattern

GROUNDING_ARGUMENT:
- Receives value directly as a parameter and constructs an agent_file_alias.RegexPattern record.
"""
        ...

    @operation
    @override
    def to_wire(self, value: agent_file_alias.RegexPattern) -> str:
        """
PURPOSE:
Converts a regex pattern to produce its string representation

GROUNDING_ARGUMENT:
- Extracts the string value from the agent_file_alias.RegexPattern record.
"""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> agent_file_alias.RegexPattern:
        """
PURPOSE:
Converts a wire type string to a regex pattern

FRESH_REQUIREMENTS:
- The regex pattern parameter type converts a wire type string into a regex pattern.

GROUNDING_ARGUMENT:
- Receives wire_value directly as a parameter and constructs a agent_file_alias.RegexPattern record.
"""
        ...

@singleton_type('agent_session')
class SearchTool(sandbox_file_reader.SearchTool):
    """
PURPOSE:
Implements the search tool to search pattern matches across workspace files

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The search tool is named `search_files`.
- The search tool regex pattern parameter uses the regex pattern parameter type.

INHERITED_REQUIREMENTS:
- [SearchTool] The search tool accepts a regex pattern parameter.

GROUNDING_ARGUMENT:
- As an agent_session singleton, SearchTool searches regex patterns across workspace files, coordinating with imported ReadManager, agent_file_alias.AliasManager, and tool_provider in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the search tool is named search_files

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('search_files').
"""
        ...

    @property
    @override
    def regex_pattern_parameter(self) -> tool_provider.Parameter[agent_file_alias.RegexPattern, str]:
        """
PURPOSE:
Parameter accepting the regex pattern to search

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with regex pattern converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool on the search tool to search regex pattern matches across session files

FRESH_REQUIREMENTS:
- The search tool searches for regex pattern matches across read-only files and read-write files using the filesystem.
- Executing the search tool fails when provided with an invalid regex pattern.
- On successful search tool execution, matches in read-only files provide matched line contents and line numbers sanitized by the alias manager to mask host paths.
- On successful search tool execution, matches in read-write files state that matches were found but cannot be displayed to prevent unanchored edits.

INHERITED_REQUIREMENTS:
- [SearchTool] Executing the search tool searches pattern matches across the session's read-only and read-write files.
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, queries readable file sets from ReadManager, searches file contents via filesystem, and sanitizes matched paths using imported agent_file_alias.AliasManager in the same session lifecycle tier.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool

GROUNDING_ARGUMENT:
- Constant tool description string.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation

GROUNDING_ARGUMENT:
- Set composed of self's constant parameter descriptor (regex_pattern_parameter).
"""
        ...
