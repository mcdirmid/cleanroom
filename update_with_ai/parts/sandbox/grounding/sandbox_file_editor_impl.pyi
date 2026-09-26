from typing import Optional, Set, Union, Self
from framework import operation, override, singleton_type
import agent_config
import agent_file_alias
import agent_node_config
import sandbox_file_editor
import template_format
import tool_provider


@singleton_type("agent_session")
class EditManager(sandbox_file_editor.EditManager):
    """Implements edit manager to install editing tools and manage template materialization.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, EditManager coordinates editing tool installation and template materialization, interacting with imported tool_provider.ToolManager, agent_node_config.NodeConfig, agent_file_alias.AliasManager, and template_format.TemplateFormatter in the same session lifecycle tier.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Tracks whether workspace files were modified during the session.

        REQUIREMENTS:
        - The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing.

        GROUNDING_IMPLEMENTS:
        - knows("has_modifications", bool): Tracks workspace file modifications during session.
        """
        ...

    @property
    @override
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Exposes read-write files locked against modification.

        REQUIREMENTS:
        - The edit manager exposes read-write files locked against modification.

        GROUNDING_IMPLEMENTS:
        - knows("locked_files", Set[agent_file_alias.ReadWriteFile]): Tracks locked read-write files during session.
        """
        ...

    @operation
    @override
    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Locks a read-write file against modification.

        Args:
            file: The read-write file to lock.

        REQUIREMENTS:
        - The edit manager supports locking individual read-write files against modification.

        GROUNDING_IMPLEMENTS:
        - action("lock_file", None): Locks file against modification.
        """
        ...

    @operation
    @override
    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Unlocks a read-write file to allow modification.

        Args:
            file: The read-write file to unlock.

        REQUIREMENTS:
        - The edit manager supports unlocking individual read-write files.

        GROUNDING_IMPLEMENTS:
        - action("unlock_file", None): Unlocks file to allow modification.
        """
        ...

    @operation
    def initialize(self) -> None:
        """Installs editing tools based on mcp mode configuration.

        REQUIREMENTS:
        - The edit manager installs the replace file content tool into the tool manager when mcp mode is inactive, and installs no editing tools when mcp mode is active.

        GROUNDING_PROVISIONS:
        - action("initialize_edit_tools", None): Configures editing tools to satisfy requirements 1 and 2.

        GROUNDING_ARGUMENT:
        - action("initialize_edit_tools", Self) :- action("install_tool", tool_provider.ToolManager), knows("is_mcp_mode", agent_config.AgentConfig).
        """
        ...

    @operation
    @override
    def can_write(self, path: Union[str, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        """Validates modification access for a read-write file under lock state and write permissions.

        Args:
            path: Target file path or alias.

        Returns:
            Response indicating whether modification is permitted.

        REQUIREMENTS:
        - Tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
        - Tool execution fails if the file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.
        - When an unlocked read-write file is supplied, tool execution records the file edit in the edit manager and produces a successful response indicating that modification is permitted.

        GROUNDING_PROVISIONS:
        - action("can_write", tool_provider.ToolResponse): Validates write access to satisfy requirement 3.

        GROUNDING_ARGUMENT:
        - action("can_write", Self) :- action("convert", agent_file_alias.AliasManager), knows("locked_files", Self), action("record_file_edit", Self).
        """
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        """Materializes templates retrieved from node config to missing target files on disk.

        REQUIREMENTS:
        - Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, writes formatted template content for missing files while preserving existing files, and records initial content baselines for active read-write files.

        GROUNDING_PROVISIONS:
        - action("materialize_templates", None): Populates missing files to satisfy requirement 4.

        GROUNDING_ARGUMENT:
        - action("materialize_templates", Self) :- knows("templates", agent_node_config.NodeConfig), knows("template_parameters", agent_node_config.NodeConfig), action("format_template", template_format.TemplateFormatter), knows("workspace_root", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def file_update_revision(self) -> int:
        """Exposes a file update revision that tracks sequential updates made to workspace files.

        REQUIREMENTS:
        - The edit manager tracks a file update revision that increments whenever workspace files are updated.

        GROUNDING_IMPLEMENTS:
        - knows("file_update_revision", int): Tracks sequential updates made to workspace files.
        """
        ...

    @property
    @override
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """Exposes the last file read or edited during the session.

        REQUIREMENTS:
        - The edit manager tracks the last read or edited file alias across the session, recording file reads from the file reader and file edits from editing tools.

        GROUNDING_IMPLEMENTS:
        - knows("last_read_or_edited_file", Optional[agent_file_alias.FileAlias]): Tracks last read or edited file across session.
        """
        ...

    @operation
    @override
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """Records that a file was read by a file reader.

        Args:
            file: The file alias that was read.

        GROUNDING_IMPLEMENTS:
        - action("record_file_read", None): Updates last read file.
        """
        ...

    @operation
    @override
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Records that a file was edited by an editing tool.

        Args:
            file: The read-write file that was edited.

        GROUNDING_IMPLEMENTS:
        - action("record_file_edit", None): Updates last edited file and increments revision counter.
        """
        ...

    @operation
    @override
    def file_hash(self, file: agent_file_alias.FileAlias) -> str:
        """Computes a file hash for a read-write file from its content.

        Args:
            file: The file alias to compute the hash for.

        Returns:
            The hex digest of the file hash.

        GROUNDING_IMPLEMENTS:
        - action("file_hash", str): Computes SHA-256 hash digest of file content.
        """
        ...


@singleton_type("agent_session")
class ReplaceFileContentTool(sandbox_file_editor.ReplaceFileContentTool):
    """Implements replace file content tool to replace target content in a read-write file within an optional line range.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, ReplaceFileContentTool performs content replacements on declared read-write files, coordinating with imported agent_file_alias.AliasManager, EditManager, agent_config.AgentConfig, and tool_provider in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Establishes that the replace file content tool is named replace_file_content.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Constant tool name identifier.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Establishes tool description informing why and when to use the tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Constant tool description.
        """
        ...

    @property
    @override
    def file_alias_parameter(self) -> tool_provider.ToolParameter:
        """Parameter identifying the target read-write file.

        GROUNDING_PROVISIONS:
        - knows("file_alias_parameter", tool_provider.ToolParameter): Exposes path parameter to satisfy requirement 16.

        GROUNDING_ARGUMENT:
        - knows("file_alias_parameter", Self) :- action("convert", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def target_content_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the target content to replace within the file or designated search window.

        GROUNDING_IMPLEMENTS:
        - knows("target_content_parameter", tool_provider.ToolParameter): Target content parameter definition.
        """
        ...

    @property
    @override
    def replacement_content_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the replacement content.

        GROUNDING_IMPLEMENTS:
        - knows("replacement_content_parameter", tool_provider.ToolParameter): Replacement content parameter definition.
        """
        ...

    @property
    @override
    def start_line_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the starting line index of the search window.

        GROUNDING_IMPLEMENTS:
        - knows("start_line_parameter", tool_provider.ToolParameter): Start line parameter definition.
        """
        ...

    @property
    @override
    def end_line_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the ending line index of the search window.

        GROUNDING_IMPLEMENTS:
        - knows("end_line_parameter", tool_provider.ToolParameter): End line parameter definition.
        """
        ...

    @property
    @override
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying whether to allow replacing multiple occurrences.

        GROUNDING_IMPLEMENTS:
        - knows("allow_multiple_parameter", tool_provider.ToolParameter): Allow multiple parameter definition.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Defines input parameters accepted for tool invocation.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Parameters accepted by the tool.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Implements execute_tool to replace matching content within a read-write file.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool response or failure feedback.

        REQUIREMENTS:
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

        GROUNDING_PROVISIONS:
        - action("execute_replace_tool", tool_provider.ToolResponse): Executes text replacement on file to satisfy requirements 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, and 24.

        GROUNDING_ARGUMENT:
        - action("execute_replace_tool", Self) :- action("can_write", sandbox_file_editor.EditManager), knows("last_read_or_edited_file", sandbox_file_editor.EditManager), knows("edit_delta_output", agent_config.AgentConfig), action("record_file_edit", sandbox_file_editor.EditManager).
        """
        ...
