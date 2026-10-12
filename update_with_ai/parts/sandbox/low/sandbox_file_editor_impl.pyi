# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T04:14:49Z
# CHANGE: Extend multiple-match failure feedback with surrounding-line and line-range guidance
# CODE_HASH: 43c41d3dd53f
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

"""Sandbox file editor implementation low-level specification."""

from typing import Any, Mapping, Optional, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_config
import agent_file_alias
import agent_node_config
import sandbox_file_editor
import src_metadata
import tool_provider


@singleton_type("agent_session")
class EditManager(sandbox_file_editor.EditManager, InTier[AgentSessionTier]):
    """Realizes workspace file modification tracking.

    GROUNDING:
    - Maintains the last-read-or-edited alias pointer, the writes-occurred flag, and the
      monotonically increasing update revision counter as private session state within the agent
      session tier.
    - Validates a supplied target against the agent_file_alias.ReadWriteFile records declared by
      agent_node_config.NodeConfig.read_write_files by comparing the
      agent_file_alias.FileAlias.relative_path and agent_file_alias.BoundFile.workspace_path members
      of those records.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        GROUNDING:
        - Evaluates the declared agent_node_config.NodeConfig.read_write_files with
          src_metadata.SourceMetadataCoordinator.is_code_modified, which compares the on-disk code
          hash of each file against the in-band code hash extracted through the src_metadata
          interface.
        """
        ...

    @property
    @override
    def file_update_revision(self) -> sandbox_file_editor.FileUpdateRevision:
        """Exposes the incremental file update revision.

        POSTCONDITIONS:
        - MUST increment whenever workspace files are updated.

        GROUNDING:
        - Exposes the private revision counter that record_file_edit advances.
        """
        ...

    @property
    @override
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """Exposes the last read or edited file.

        GROUNDING:
        - Exposes the private alias pointer holding the most recently read or edited
          agent_file_alias.FileAlias.
        """
        ...

    @operation
    @override
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """Records that a file was read during the session.

        GROUNDING:
        - Sets the private last-read-or-edited alias pointer to the supplied
          agent_file_alias.FileAlias within the agent session tier.
        """
        ...

    @operation
    @override
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Records that a file was edited during the session.

        GROUNDING:
        - Sets the private last-read-or-edited alias pointer to the supplied
          agent_file_alias.ReadWriteFile, raises the private writes-occurred flag, and advances the
          private update revision counter within the agent session tier.
        """
        ...

    @operation
    @override
    def file_hash(self, file: agent_file_alias.FileAlias) -> sandbox_file_editor.FileHash:
        """Computes the MD5 hexadecimal digest of a file.

        Args:
            file: The file alias whose content is hashed.

        Returns:
            The computed MD5 hash string.

        POSTCONDITIONS:
        - MUST return an MD5 hexadecimal digest of content read from the filesystem.

        GROUNDING:
        - Reads host content for the agent_file_alias.BoundFile.workspace_path of the supplied
          agent_file_alias.FileAlias through the pathlib filesystem operations declared by the
          filesystem_ext external boundary and returns its MD5 hexadecimal digest.
        """
        ...

    @operation
    @override
    def can_write(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """Validates write access for a target file.

        Args:
            path: The file path string or FileAlias to validate.

        Returns:
            Response indicating whether modification is permitted.

        POSTCONDITIONS:
        - WHEN the target file is not a declared read-write file, MUST fail reminding the agent that only declared read-write files can be written.
        - WHEN a declared read-write file is supplied, MUST record the file edit.
        - WHEN a declared read-write file is supplied, MUST produce a successful response indicating write access is permitted.

        GROUNDING:
        - Matches the supplied agent_file_alias.RelativePath or agent_file_alias.FileAlias against
          the agent_file_alias.ReadWriteFile records declared by
          agent_node_config.NodeConfig.read_write_files using the
          agent_file_alias.FileAlias.relative_path and
          agent_file_alias.BoundFile.workspace_path members, records the file edit through
          sandbox_file_editor.EditManager.record_file_edit for a declared read-write file, and
          returns the resulting tool_provider.ToolResponse.
        """
        ...


@singleton_type("agent_session")
class ReplaceFileContentTool(
    sandbox_file_editor.ReplaceFileContentTool, InTier[AgentSessionTier]
):
    """Realizes targeted text replacement within bounded line ranges.

    GROUNDING:
    - Coordinates replacements on the agent_file_alias.ReadWriteFile records declared by
      agent_node_config.NodeConfig.read_write_files, resolving the target through
      agent_file_alias.AliasManager.convert and matching target content within bounded line windows
      of the host content.
    - Reads and writes host content through the pathlib filesystem operations declared by the
      filesystem_ext external boundary, records successful edits through
      sandbox_file_editor.EditManager.record_file_edit, and returns tool_provider.ToolResponse
      records that share the "replace_file_content" suppression key.
    """

    @operation
    @override
    def initialize(self) -> None:
        """Installs the replace file content tool into the session environment.

        GROUNDING:
        - Registers this tool instance through tool_provider.ToolManager.install_tool under its
          tool_provider.ToolName within the agent session tier.
        """
        ...

    @property
    @override
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """Parameter identifying the target read-write file.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the agent_file_alias.FileAlias target whose
          tool_provider.ToolParameter.parameter_type is the agent_file_alias.AliasManager converting
          wire strings into file aliases.
        """
        ...

    @property
    @override
    def target_content_parameter(self) -> tool_provider.ToolParameter[sandbox_file_editor.TargetContent, str]:
        """Parameter specifying the target content to replace.

        POSTCONDITIONS:
        - MUST configure a missing note producing diagnostic feedback from the supplied parameter names.
        - WHEN line range arguments are supplied, MUST explain that start line and end line only restrict the search window.
        - WHEN line range arguments are omitted, MUST explain that target content must match existing text to append or insert content.

        GROUNDING:
        - Declares a tool_provider.ToolParameter whose tool_provider.ToolParameter.missing_message
          callable is evaluated by tool_provider.ToolManager.execute_tool against the present
          tool_provider.ParameterName set and returns a tool_provider.MissingMessage.
        """
        ...

    @property
    @override
    def replacement_content_parameter(self) -> tool_provider.ToolParameter[sandbox_file_editor.ReplacementContent, str]:
        """Parameter specifying the replacement content.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the sandbox_file_editor.ReplacementContent
          replacement text read by execute_tool from the actual parameter bindings.
        """
        ...

    @property
    @override
    def start_line_parameter(self) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        """Parameter specifying the starting line index of the search window.

        GROUNDING:
        - Declares an optional tool_provider.ToolParameter over the sandbox_file_editor.LineNumber
          start bound, restricting the search window only when a line range argument is supplied.
        """
        ...

    @property
    @override
    def end_line_parameter(self) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        """Parameter specifying the ending line index of the search window.

        GROUNDING:
        - Declares an optional tool_provider.ToolParameter over the sandbox_file_editor.LineNumber
          end bound, restricting the search window only when a line range argument is supplied.
        """
        ...

    @property
    @override
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter[sandbox_file_editor.AllowMultiple, bool]:
        """Parameter specifying whether to allow replacing multiple occurrences.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the sandbox_file_editor.AllowMultiple flag
          that execute_tool reads from the actual parameter bindings to select single or multiple
          occurrence replacement.
        """
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """Executes targeted in-place text replacement.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent.

        POSTCONDITIONS:
        - WHEN the path parameter is omitted and the last read or edited file is a read-write file, MUST bind the target file to the last read or edited file and warn the agent in the response content.
        - WHEN the path parameter is omitted and no file was read or edited, MUST fail.
        - WHEN the path parameter is omitted and the last read or edited file is not a read-write file, MUST fail.
        - WHEN the target file is not a declared read-write file, MUST fail.
        - WHEN the target file is missing from the filesystem, MUST treat its content as empty.
        - WHEN start_line is provided and is less than one, MUST fail.
        - WHEN start_line is provided and exceeds the total line count plus one, MUST fail.
        - WHEN end_line is provided and is less than one, MUST fail.
        - WHEN end_line is provided and exceeds the total line count, MUST fail.
        - WHEN both start_line and end_line are provided and start_line exceeds end_line, MUST fail.
        - MUST find target content occurrences with exact string matching.
        - WHEN exact matching finds zero occurrences and allow_multiple is false, MUST fall back to line-by-line whitespace-stripped matching.
        - WHEN allow_multiple is false, MUST treat the whitespace-stripped fallback as successful if and only if exactly one unique line window matches after stripping leading and trailing whitespace from each line.
        - WHEN allow_multiple is false and target content is not found within the search window, MUST fail.
        - WHEN allow_multiple is true and target content is not found within the search window, MUST fail.
        - WHEN allow_multiple is false, MUST replace the single matching occurrence on success.
        - WHEN allow_multiple is true, MUST replace all occurrences of target content within the search window.
        - WHEN allow_multiple is false and target content matches multiple locations within the search
          window, MUST fail indicating the first two matching line numbers to assist in narrowing the
          replacement region and directing the agent to include more surrounding lines in target
          content or to specify start line and end line.
        - WHEN target content is not found within the search window but exists elsewhere in the file, MUST fail indicating the line numbers where target content was located.
        - WHEN the edit produces no change to file content, MUST fail reminding the agent that the edit had no effect.
        - WHEN the replacement succeeds, MUST write updated content to the filesystem.
        - WHEN the replacement succeeds, MUST create missing parent directories.
        - WHEN the replacement succeeds, MUST record that workspace file writes occurred.
        - WHEN the replacement succeeds, MUST remind the agent to verify syntax and type correctness before making further writes.
        - MUST set the suppression key of produced responses to "replace_file_content".
        - WHEN delta output is configured, MUST include a diff delta representation of the change in the response content.

        GROUNDING:
        - Resolves the bound tool_provider.ToolParameter entries from actual_parameter_bindings,
          converting the path wire string through agent_file_alias.AliasManager.convert and defaulting
          an omitted path to sandbox_file_editor.EditManager.last_read_or_edited_file when that alias
          is a declared agent_file_alias.ReadWriteFile.
        - Reads host content for the agent_file_alias.BoundFile.workspace_path recorded on the target
          through the pathlib filesystem operations declared by the filesystem_ext external boundary,
          treats a missing host file as empty content, validates the supplied start line and end line
          bounds against the enumerated line count, and matches target content exactly before falling
          back to whitespace-stripped line windows.
        - Reports the enumerated host content line numbers through those same pathlib filesystem
          operations, disclosing the first two matching line numbers of an ambiguous match and the line
          numbers where target content was located outside the search window.
        - Writes the replaced content back through those same filesystem operations while creating
          missing parent directories, records the successful edit through
          sandbox_file_editor.EditManager.record_file_edit, includes a diff delta through
          agent_config.AgentConfig.edit_delta_output when that configuration is enabled, and returns
          tool_provider.ToolResponse records whose suppression key is "replace_file_content".
        """
        ...
