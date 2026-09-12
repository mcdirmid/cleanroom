from typing import Set
from framework import operation, override, singleton_type
import file_alias
import filesystem_ext
import node_config
import sandbox_file_editor
import template_format
import tool_provider

@singleton_type('agent_session')
class EditManager(sandbox_file_editor.EditManager):
    """
PURPOSE:
Implements edit manager to install editing tools and manage template materialization

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager installs the text replacement tool and line update tool.
- [EditManager] Modifying a file records that workspace file modifications occurred during the session.

GROUNDING_ARGUMENT:
- As an agent_session singleton, EditManager coordinates editing tool installation and template materialization, interacting with imported tool_provider.ToolManager, node_config.NodeConfig, file_alias.AliasManager, and template_format.TemplateFormatter in the same session lifecycle tier.
"""

    @property
    @override
    def has_modifications(self) -> bool:
        """
PURPOSE:
Tracks whether workspace files were modified during the session

FRESH_REQUIREMENTS:
- The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.

GROUNDING_ARGUMENT:
- Internal session state comparing current file content against initial content recorded before editing tools modify workspace files.
"""
        ...

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Unconditionally installs the text replacement tool and line update tool into the tool manager

FRESH_REQUIREMENTS:
- The edit manager unconditionally installs the text replacement tool and line update tool into the tool manager.

GROUNDING_ARGUMENT:
- Installs TextReplacementTool and LineUpdateTool directly into imported tool_provider.ToolManager in the same session lifecycle tier.
"""
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        """
PURPOSE:
Materializes templates retrieved from node config to missing target files on disk while preserving existing files

FRESH_REQUIREMENTS:
- Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes formatted template content for missing files while preserving existing files.

INHERITED_REQUIREMENTS:
- [EditManager] Materializing templates populates missing read-write files with initial template content without overwriting existing files.

GROUNDING_ARGUMENT:
- Obtains template mappings and template parameters from imported node_config.NodeConfig, formats template content using imported template_format.TemplateFormatter, resolves host paths using imported file_alias.AliasManager workspace root in the same session lifecycle tier, and writes missing files via the filesystem.
"""
        ...

    @property
    @override
    def file_update_revision(self) -> int:
        """
PURPOSE:
Exposes a file update revision that tracks sequential updates made to workspace files

FRESH_REQUIREMENTS:
- The edit manager tracks a file update revision that increments whenever workspace files are updated.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager exposes a file update revision that tracks sequential updates made to workspace files.

GROUNDING_ARGUMENT:
- Internal session counter on self incremented whenever editing tools successfully update workspace files.
"""
        ...

@singleton_type('agent_session')
class TextReplacementTool(sandbox_file_editor.TextReplacementTool):
    """
PURPOSE:
Implements text replacement tool to replace unique matching text

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The text replacement tool is named `replace`.
- The text replacement tool file parameter uses the alias manager to convert a file alias.
- The text replacement tool target text parameter uses a string parameter converter to accept text.
- The text replacement tool replacement text parameter uses a string parameter converter to accept text.

GROUNDING_ARGUMENT:
- As an agent_session singleton, TextReplacementTool performs text replacements on declared read-write files, coordinating with imported file_alias.AliasManager, EditManager, and tool_provider in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the text replacement tool is named replace

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('replace').
"""
        ...

    @property
    @override
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target read-write file

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def target_text_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the exact text to replace

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
"""
        ...

    @property
    @override
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the replacement content

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to replace unique matching text with size validation

FRESH_REQUIREMENTS:
- Before modifying a file, editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
- Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that their edit had no effect and such edits will fail.
- On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.
- Executing the text replacement tool reads file content using the filesystem.
- Executing the text replacement tool fails if the target text exceeds 100,000 characters, and reminds the agent that target text for replacement must not exceed 100,000 characters.
- Executing the text replacement tool fails if the target text is not found in the file content.
- Executing the text replacement tool fails if the target text matches multiple locations in the file.
- On successful text replacement tool execution, the unique occurrence of the target text is replaced with the replacement text, written using the filesystem, and file modifications are recorded.
- Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves the target read-write file via imported file_alias.AliasManager, inspects and updates file content using the filesystem, attaches the read-write file's short name as a suppression key on successful responses, and notifies EditManager in the same session lifecycle tier that workspace files were modified.
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
- Set composed of self's constant parameter descriptors (file_alias_parameter, target_text_parameter, replacement_text_parameter).
"""
        ...

@singleton_type('agent_session')
class LineUpdateTool(sandbox_file_editor.LineUpdateTool):
    """
PURPOSE:
Implements line update tool to update or insert lines

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The line update tool is named `update_lines`.
- The line update tool file parameter uses the alias manager to convert a file alias.
- The line update tool start line parameter uses an integer parameter converter to accept an integer.
- The line update tool end line parameter uses an integer parameter converter to accept an integer.
- The line update tool replacement text parameter uses a string parameter converter to accept text.

GROUNDING_ARGUMENT:
- As an agent_session singleton, LineUpdateTool performs line replacements and insertions on declared read-write files, coordinating with imported file_alias.AliasManager, EditManager, and tool_provider in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the line update tool is named update_lines

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('update_lines').
"""
        ...

    @property
    @override
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target read-write file

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def start_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the starting line index

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with integer parameter converter.
"""
        ...

    @property
    @override
    def end_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the ending line index

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with integer parameter converter.
"""
        ...

    @property
    @override
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the replacement content

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to update or insert lines within valid line boundaries

FRESH_REQUIREMENTS:
- Before modifying a file, editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
- Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that their edit had no effect and such edits will fail.
- On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.
- Executing the line update tool reads file content using the filesystem.
- Executing the line update tool fails if the start line is less than one or exceeds the total line count plus one.
- When the start line is less than or equal to the end line, executing the line update tool fails if the end line exceeds the total line count.
- When the start line is less than or equal to the end line, successful execution replaces lines within the range, writes using the filesystem, and records file modifications.
- When the start line exceeds the end line, successful execution inserts the replacement lines before the start line, writes using the filesystem, and records file modifications.
- Replacing or inserting lines treats each replacement line as a complete newline-terminated line, preserving subsequent line boundaries when replacement text lacks a trailing newline.
- Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves the target read-write file via imported file_alias.AliasManager, reads and updates file content using the filesystem, attaches the read-write file's short name as a suppression key on successful responses, and notifies EditManager in the same session lifecycle tier that workspace files were modified.
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
- Set composed of self's constant parameter descriptors (file_alias_parameter, start_line_parameter, end_line_parameter, replacement_text_parameter).
"""
        ...
