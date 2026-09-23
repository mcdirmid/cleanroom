from typing import Optional, Set, Union
from framework import operation, override, singleton_type
import agent_config
import agent_file_alias
import agent_node_config
import sandbox_file_editor
import template_format
import tool_provider

@singleton_type('agent_session')
class EditManager(sandbox_file_editor.EditManager):
    """
PURPOSE:
Implements edit manager to install editing tools and manage template materialization

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager installs the replace file content tool.
- [EditManager] Modifying a file records that workspace file modifications occurred during the session.

GROUNDING_ARGUMENT:
- As an agent_session singleton, EditManager coordinates editing tool installation and template materialization, interacting with imported tool_provider.ToolManager, agent_node_config.NodeConfig, agent_file_alias.AliasManager, and template_format.TemplateFormatter in the same session lifecycle tier.
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

    @property
    @override
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Exposes read-write files locked against modification

FRESH_REQUIREMENTS:
- The edit manager exposes read-write files locked against modification.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager exposes read-write files locked against modification.

GROUNDING_ARGUMENT:
- Set maintained on self tracking read-write files locked against modification during the session.
"""
        ...

    @operation
    @override
    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
PURPOSE:
Locks a read-write file against modification

FRESH_REQUIREMENTS:
- The edit manager supports locking individual read-write files against modification.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager supports locking individual read-write files against modification.

GROUNDING_ARGUMENT:
- Adds specified read-write file to internal set on self.
"""
        ...

    @operation
    @override
    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
PURPOSE:
Unlocks a read-write file to allow modification

FRESH_REQUIREMENTS:
- The edit manager supports unlocking individual read-write files.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager supports unlocking individual read-write files.

GROUNDING_ARGUMENT:
- Discards specified read-write file from internal set on self.
"""
        ...

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Installs the replace file content tool into the tool manager when mcp mode is inactive, and installs no editing tools when mcp mode is active

FRESH_REQUIREMENTS:
- The edit manager installs the replace file content tool into the tool manager when mcp mode is inactive, and installs no editing tools when mcp mode is active.

GROUNDING_ARGUMENT:
- Installs ReplaceFileContentTool directly into imported tool_provider.ToolManager when imported collaborator agent_config.AgentConfig.is_mcp_mode is inactive, and installs no tools when is_mcp_mode is active in the same session lifecycle tier.
"""
        ...

    @operation
    @override
    def can_write(self, path: Union[str, agent_file_alias.FileAlias]) -> tool_provider.Response:
        """
PURPOSE:
Validates modification access for a read-write file under lock state and write permissions

FRESH_REQUIREMENTS:
- Tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
- Tool execution fails if the file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.
- When an unlocked read-write file is supplied, tool execution records the file edit in the edit manager and produces a successful response indicating that modification is permitted.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager provides a can write operation validating modification access for a read-write file.

GROUNDING_ARGUMENT:
- Resolves target file from path parameter using imported agent_file_alias.AliasManager, checks if target file is a ReadWriteFile, verifies target file is not in EditManager.locked_files, records file edit in EditManager in the same session lifecycle tier, and produces Response indicating allowance or denial.
"""
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        """
PURPOSE:
Materializes templates retrieved from node config to missing target files on disk while preserving existing files and recording baselines

FRESH_REQUIREMENTS:
- Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, writes formatted template content for missing files while preserving existing files, and records initial content baselines for active read-write files.

INHERITED_REQUIREMENTS:
- [EditManager] Materializing templates populates missing read-write files with initial template content without overwriting existing files.

GROUNDING_ARGUMENT:
- Obtains template mappings and template parameters from imported agent_node_config.NodeConfig, formats template content using imported template_format.TemplateFormatter, resolves host paths using imported agent_file_alias.AliasManager workspace root in the same session lifecycle tier, writes missing files via the filesystem, and records initial content baselines for active read-write files.
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

    @property
    @override
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """
PURPOSE:
Exposes the last file read or edited during the session

FRESH_REQUIREMENTS:
- The edit manager tracks the last read or edited file alias across the session, recording file reads from the file reader and file edits from editing tools.

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager tracks the last read or edited file across the session, recording file reads from file readers and file edits from editing tools.

GROUNDING_ARGUMENT:
- Internal session attribute tracking the latest file alias read via ViewFileTool or modified via ReplaceFileContentTool.
"""
        ...

    @operation
    @override
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """
PURPOSE:
Records that a file was read by a file reader

GROUNDING_ARGUMENT:
- Sets internal attribute on self.
"""
        ...

    @operation
    @override
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
PURPOSE:
Records that a file was edited by an editing tool

GROUNDING_ARGUMENT:
- Sets internal attribute on self.
"""
        ...

    @operation
    @override
    def file_hash(self, file: agent_file_alias.FileAlias) -> str:
        """
PURPOSE:
Computes a file hash for a read-write file from its content

INHERITED_REQUIREMENTS:
- [EditManager] The edit manager computes a file hash for a read-write file from its content.

GROUNDING_ARGUMENT:
- Reads file content from filesystem_ext at resolved host path and returns MD5 digest.
"""
        ...

@singleton_type('agent_session')
class ReplaceFileContentTool(sandbox_file_editor.ReplaceFileContentTool):
    """
PURPOSE:
Implements replace file content tool to replace target content in a read-write file within an optional line range

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The replace file content tool is named `replace_file_content`.
- The replace file content tool path parameter uses the alias manager to convert a file alias.
- The replace file content tool target content parameter uses a string parameter converter to accept text.
- The replace file content tool replacement content parameter uses a string parameter converter to accept text.
- The replace file content tool start line parameter uses an integer parameter converter to accept an integer.
- The replace file content tool end line parameter uses an integer parameter converter to accept an integer.
- The replace file content tool allow multiple parameter uses a boolean parameter converter to accept a boolean.

GROUNDING_ARGUMENT:
- As an agent_session singleton, ReplaceFileContentTool performs content replacements on declared read-write files, coordinating with imported agent_file_alias.AliasManager, EditManager, agent_config.AgentConfig, and tool_provider in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the replace file content tool is named replace_file_content

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('replace_file_content').
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
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target read-write file

GROUNDING_ARGUMENT:
- Constant optional parameter descriptor configured with alias manager converter and named 'path'.
"""
        ...

    @property
    @override
    def target_content_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the target content to replace within the file or designated search window

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter, named 'target_content', and configuring a missing message function that evaluates supplied parameter names to guide search window and append constraints.
"""
        ...

    @property
    @override
    def replacement_content_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the replacement content

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter and named 'replacement_content'.
"""
        ...

    @property
    @override
    def start_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the starting line index of the search window

GROUNDING_ARGUMENT:
- Constant optional parameter descriptor configured with integer parameter converter and named 'start_line'.
"""
        ...

    @property
    @override
    def end_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the ending line index of the search window

GROUNDING_ARGUMENT:
- Constant optional parameter descriptor configured with integer parameter converter and named 'end_line'.
"""
        ...

    @property
    @override
    def allow_multiple_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying whether to allow replacing multiple occurrences

GROUNDING_ARGUMENT:
- Constant optional parameter descriptor configured with boolean parameter converter and named 'allow_multiple'.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation

GROUNDING_ARGUMENT:
- Set composed of self's constant parameter descriptors in sequence (file_alias_parameter, start_line_parameter, end_line_parameter, allow_multiple_parameter, target_content_parameter, replacement_content_parameter).
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to replace matching content within a read-write file

FRESH_REQUIREMENTS:
- Editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
- Editing tool execution fails if the file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.
- Editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.
- On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and reminds the agent to call the check file tool to verify syntax and type correctness before making further modifications.
- When configured to produce delta output, successful editing tool execution includes a diff delta representation in the response content.
- Tool execution implicitly binds the target file to the last file read or edited in the edit manager if that file is a read-write file, informs the agent with a warning in the response content that the path was implicitly bound while allowing the tool execution to proceed, or fails if no file has been read or edited or if the last read or edited file is not a read-write file, when the path parameter is omitted.
- Tool execution reads the file content from the filesystem, treating missing files as empty.
- Tool execution fails if the start line is less than one or exceeds the total line count plus one, when a start line is provided.
- Tool execution fails if the end line is less than one or exceeds the total line count, when an end line is provided.
- Tool execution fails if the start line exceeds the end line, when both start line and end line are provided.
- Tool execution matches target content using exact matching, or falls back to line-by-line whitespace-stripped matching across the search window when exact matching finds zero occurrences and allow multiple is false or not set, succeeding if and only if exactly one unique line window matches after stripping leading and trailing whitespace from each line; fails if the target content is not found within the designated line range or matches multiple locations within the designated line range, and on success replaces the single matching occurrence, when allow multiple is not set or false.
- Tool execution fails if the target content is not found within the designated line range, and replaces all occurrences of the target content within the designated line range, when allow multiple is true.
- Tool execution provides failure feedback indicating the first two matching line numbers to assist in narrowing the replacement region and instructs the agent to include more surrounding lines in target_content or specify start_line and end_line, when target content matches multiple locations in the file and allow multiple is false.
- Tool execution provides failure feedback indicating the line numbers where the target content was located, when target content is not found within the designated line range but exists elsewhere in the file.
- Tool execution writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file modifications occurred on success.
- Editing tool responses share a constant suppression key replace_file_content.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves the target read-write file via path parameter or implicitly from EditManager.last_read_or_edited_file, informs with a warning in content when implicitly bound, inspects and updates file content using the filesystem, scans file content for out-of-bounds line occurrences when target content is missing from designated line ranges, checks configuration via imported agent_config.AgentConfig, attaches a reminder to call check_files to verify syntax and type correctness on successful execution, attaches suppression key 'replace_file_content', and notifies EditManager in the same session lifecycle tier that workspace files were modified.
"""
        ...
