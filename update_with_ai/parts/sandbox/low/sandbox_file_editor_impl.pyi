"""Sandbox file editor implementation low-level specification."""

from typing import Any, Mapping, Optional, Set, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import sandbox_file_editor
import tool_provider


@singleton_type("agent_session")
class EditManager(sandbox_file_editor.EditManager, InTier[AgentSessionTier]):
    """Realizes workspace file modification tracking, write locking, and template materialization."""

    @property
    @override
    def has_modifications(self) -> bool:
        ...

    @property
    @override
    def file_update_revision(self) -> sandbox_file_editor.FileUpdateRevision:
        """Exposes the incremental file update revision.

        POSTCONDITIONS:
        - MUST increment the file update revision whenever workspace files are updated.
        """
        ...

    @property
    @override
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        ...

    @property
    @override
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        ...

    @operation
    @override
    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Locks a read-write file against modification.

        Args:
            file: The read-write file to lock.

        POSTCONDITIONS:
        - MUST lock the read-write file against modification.
        """
        ...

    @operation
    @override
    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Unlocks a read-write file to allow modification.

        Args:
            file: The read-write file to unlock.

        POSTCONDITIONS:
        - MUST unlock the read-write file to allow modification.
        """
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        """Materializes configured templates into missing read-write files.

        POSTCONDITIONS:
        - MUST format initial template content using session template parameters.
        - MUST write formatted template content for missing read-write files while preserving existing files.
        - MUST record initial content baselines for active read-write files.
        """
        ...

    @operation
    @override
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        ...

    @operation
    @override
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
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
        - WHEN the target file is locked against write, MUST fail reminding the agent that files targeted by submit, fail, or blame cannot be written.
        - WHEN an unlocked read-write file is supplied, MUST record the file edit and confirm write access.
        """
        ...


@singleton_type("agent_session")
class ReplaceFileContentTool(
    sandbox_file_editor.ReplaceFileContentTool, InTier[AgentSessionTier]
):
    """Realizes targeted text replacement within bounded line ranges."""

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
        - WHEN the path parameter is omitted and the last read or edited file is a read-write file, MUST bind the target file to the last read or edited file and include a warning.
        - WHEN the path parameter is omitted and no valid read-write file history exists, MUST fail.
        - WHEN start_line is provided and is less than one or exceeds total line count plus one, MUST fail.
        - WHEN end_line is provided and is less than one or exceeds total line count, MUST fail.
        - WHEN both start_line and end_line are provided and start_line exceeds end_line, MUST fail.
        - WHEN exact matching finds zero occurrences and allow_multiple is false, MUST fall back to whitespace-stripped line matching.
        - WHEN allow_multiple is false and target content matches multiple locations, MUST fail indicating the first two matching line numbers.
        - WHEN target content is not found in the search window but exists elsewhere, MUST fail indicating the line numbers where target content was located.
        - WHEN the edit produces no change to file content, MUST fail reminding the agent that no-op edits will fail.
        - WHEN the replacement succeeds, MUST write updated content creating missing parent directories and record workspace file writes.
        """
        ...
