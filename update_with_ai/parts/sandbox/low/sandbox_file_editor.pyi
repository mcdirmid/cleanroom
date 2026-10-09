# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 998b60a3fe78
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Sandbox file editor low-level interface specification."""

from typing import Any, Mapping, NewType, Optional, Protocol, Set, Union
from framework import data_type, operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import tool_provider

FileUpdateRevision = NewType("FileUpdateRevision", int)
LineNumber = NewType("LineNumber", int)
TargetContent = NewType("TargetContent", str)
ReplacementContent = NewType("ReplacementContent", str)
FileHash = NewType("FileHash", str)
AllowMultiple = NewType("AllowMultiple", bool)


@poly_type
class EditingTool(tool_provider.Tool, Protocol):
    """Polymorphic tool that modifies a read-write file."""

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
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        ...


@singleton_type("agent_session")
class EditManager(InTier[AgentSessionTier], Protocol):
    """Agent session service that installs editing tools and tracks session modifications."""

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        POSTCONDITIONS:
        - WHEN workspace file contents differ from their in-band code hash, MUST return true.
        - WHEN workspace file contents match their in-band code hash, MUST return false.
        """
        ...

    @property
    def file_update_revision(self) -> FileUpdateRevision:
        """Exposes a file update revision that tracks sequential updates made to workspace files.

        POSTCONDITIONS:
        - MUST return a file update revision that tracks sequential updates made to workspace files.
        """
        ...

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """Tracks the last file read or edited across the session.

        POSTCONDITIONS:
        - MUST return the most recently read or edited file alias across the session.
        """
        ...

    @operation
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """Records that a file was read by a file reader.

        Args:
            file: The file alias that was read.

        POSTCONDITIONS:
        - MUST record that the file was read, updating the last read or edited file in the session.
        """
        ...

    @operation
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Records that a file was edited by an editing tool.

        Args:
            file: The read-write file that was edited.

        POSTCONDITIONS:
        - MUST record that the file was edited, updating the last read or edited file in the session.
        """
        ...

    @operation
    def file_hash(self, file: agent_file_alias.FileAlias) -> FileHash:
        """Computes a file hash for a read-write file from its content.

        Args:
            file: The file alias whose content is hashed.

        Returns:
            The computed file hash string.

        POSTCONDITIONS:
        - MUST return a file hash for the read-write file computed from its content.
        """
        ...

    @operation
    def can_write(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """Validates modification access for a read-write file.

        Args:
            path: The file path string or FileAlias to validate.

        Returns:
            Response indicating whether modification is permitted.

        POSTCONDITIONS:
        - WHEN checking write access for a workspace path or file alias matching a declared read-write file, MUST confirm access.
        - WHEN checking write access for a path that is not a declared read-write file, MUST fail with guidance.
        """
        ...


@singleton_type("agent_session")
class ReplaceFileContentTool(EditingTool, InTier[AgentSessionTier], Protocol):
    """Editing tool that replaces target content in a read-write file."""

    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """Parameter identifying the target read-write file."""
        ...

    @property
    def target_content_parameter(self) -> tool_provider.ToolParameter[TargetContent, str]:
        """Parameter specifying the target content to replace."""
        ...

    @property
    def replacement_content_parameter(self) -> tool_provider.ToolParameter[ReplacementContent, str]:
        """Parameter specifying the replacement content."""
        ...

    @property
    def start_line_parameter(self) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        """Parameter specifying the starting line index of the search window."""
        ...

    @property
    def end_line_parameter(self) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        """Parameter specifying the ending line index of the search window."""
        ...

    @property
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter[AllowMultiple, bool]:
        """Parameter specifying whether to allow replacing multiple occurrences."""
        ...

    @operation
    @override
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """Executes tool with actual parameter bindings.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        POSTCONDITIONS:
        - MUST replace target content with replacement content within the bounded line range.
        - WHEN multiple replacements are permitted, MUST replace multiple occurrences.
        """
        ...
