from typing import Optional, Set, Type
from framework import operation, override, singleton_type
import agent_file_alias
import filesystem_ext
import agent_node_config
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
- [ReadManager] The read manager installs the read tool and search tool.
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
Provides that initialization unconditionally installs the read tool into the tool manager and never installs the search tool

FRESH_REQUIREMENTS:
- The read manager unconditionally installs the read tool into the tool manager and never installs the search tool.

GROUNDING_ARGUMENT:
- Installs ReadTool directly into imported tool_provider.ToolManager in the same session lifecycle tier, and never installs SearchTool.
"""
        ...

    @operation
    @override
    def requires_line_numbers(self, file: agent_file_alias.FileAlias) -> bool:
        """
PURPOSE:
Identifies whether an inspected file requires line numbers to be requested when read, requiring line numbers for read-write files and source code files

FRESH_REQUIREMENTS:
- The read manager identifies that read-write files and source code files require line numbers when read.
- The read manager identifies files ending with `.py` as source code files requiring line numbers.

GROUNDING_ARGUMENT:
- Checks if the file is an instance of agent_file_alias.ReadWriteFile or if the file's short name ends with '.py'.
"""
        ...

@singleton_type('agent_session')
class ReadTool(sandbox_file_reader.ReadTool):
    """
PURPOSE:
Implements the read tool to perform workspace file inspection

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The read tool is named `read_file`.
- The read tool file parameter uses the alias manager to convert a file alias.
- The read tool line numbers parameter uses the boolean parameter converter.

GROUNDING_ARGUMENT:
- As an agent_session singleton, ReadTool executes file inspection across declared session files, interacting with imported agent_file_alias.AliasManager, agent_node_config.NodeConfig, template_format.TemplateFormatter, and tool_provider in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the read tool is named read_file

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('read_file').
"""
        ...

    @property
    @override
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter accepting the target file alias

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def line_numbers_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter that must be true when reading read-write files and source code files, and false or omitted when reading non-source read-only files

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with boolean parameter converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool on the read tool to read file content with line number formatting and alias validation

FRESH_REQUIREMENTS:
- Executing the read tool reads file content using the filesystem at the host path formed from the alias manager workspace root and bound file workspace path.
- When the target file does not exist on disk, read tool execution treats a read-write file as having empty content, and fails with a response guiding agent recovery when inspecting a missing read-only file.
- Executing the read tool fails if line numbers are not requested when reading a read-write file or source code file, reminding the agent that line numbers must be requested when reading read-write files and source code files and omitted when reading non-source read-only files, and specifying a follow-up execution of the read tool on the file with line numbers requested.
- Executing the read tool fails if line numbers are requested when reading a non-source read-only file, reminding the agent that line numbers must be requested when reading read-write files and source code files and omitted when reading non-source read-only files, and specifying a follow-up execution of the read tool on the file with line numbers omitted.
- Executing the read tool with an unbound file fails with a response guiding agent recovery that lists available readable file aliases, and reminds the agent that only declared files can be inspected.
- When an unbound file equals the guide file configured for step-mode, the read tool failure response indicates that `advance` must be called to read the guide instead.
- Read tool responses for read-write files carry a suppression key matching the file's short name, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.
- When reading markdown files ending with .md, paragraphs beginning with > META: are filtered out from the returned content.
- When reading read-only markdown files ending with .md, content is formatted using the template formatter with session template parameters after filtering out paragraphs beginning with > META:.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, queries line number requirement from ReadManager in the same session lifecycle tier, resolves host paths using imported agent_file_alias.AliasManager workspace root in the same session lifecycle tier, reads file content via the filesystem, filters > META: paragraphs for markdown files, formats read-only markdown content using imported template_format.TemplateFormatter and agent_node_config.NodeConfig.template_parameters in the same session lifecycle tier, checks line number formatting rules for read-only, read-write, and source code files, specifies follow-up read tool calls with corrected line numbers on failure, attaches the file's short name as a suppression key on responses for read-write files while omitting it for read-only files, and masks host paths in read-only output.
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
- Set composed of self's constant parameter descriptors (file_alias_parameter, line_numbers_parameter).
"""
        ...

@singleton_type('agent_session')
class RegexPatternConverter(tool_provider.ParameterConverter):
    """
PURPOSE:
Defined as a parameter converter for regex patterns that converts a wire type string into a regex pattern

GROUNDING_ARGUMENT:
- As an agent_session singleton, RegexPatternConverter converts wire strings to regex patterns without requiring external singleton dependencies.
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
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
Sets the converter wire type to string

GROUNDING_ARGUMENT:
- Constant wire type descriptor identifying WireType.STRING.
"""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> agent_file_alias.RegexPattern:
        """
PURPOSE:
Converts a wire type string to a regex pattern

FRESH_REQUIREMENTS:
- The regex pattern converter converts a wire type string into a regex pattern.

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
- The search tool regex pattern parameter uses the regex pattern converter.

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
    def regex_pattern_parameter(self) -> tool_provider.Parameter:
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
