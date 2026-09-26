from typing import Optional, Protocol, Set, Union
from framework import data_type, operation, override, poly_type, singleton_type
import agent_file_alias
import tool_provider


@data_type
class FileTemplate(agent_file_alias.FileContent):
    """Introduces file template as initial file content for a read-write file.

    REQUIREMENTS:
    - A file template is file content representing initial boilerplate for a read-write file.
    """
    ...


@poly_type
class EditingTool(tool_provider.Tool, Protocol):
    """Polymorphic tool that modifies a read-write file."""

    @property
    @override
    def name(self) -> str:
        """Tool name used to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Tool description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted by the editing tool."""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a tool response."""
        ...


@singleton_type('agent_session')
class EditManager(Protocol):
    """Agent session service that installs editing tools and tracks session modifications.

    REQUIREMENTS:
    - The edit manager installs the replace file content tool.
    - Modifying a file records that workspace file modifications occurred during the session.
    """

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        REQUIREMENTS:
        - The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.

        GROUNDING_PROVISIONS:
        - knows("has_modifications", bool): Exposes whether file modifications occurred.
        """
        ...

    @property
    def file_update_revision(self) -> int:
        """Exposes a file update revision that tracks sequential updates made to workspace files.

        REQUIREMENTS:
        - The edit manager exposes a file update revision that tracks sequential updates made to workspace files.

        GROUNDING_PROVISIONS:
        - knows("file_update_revision", int): Exposes sequential file update revision count.
        """
        ...

    @property
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Exposes read-write files locked against modification.

        REQUIREMENTS:
        - The edit manager exposes read-write files locked against modification.

        GROUNDING_PROVISIONS:
        - knows("locked_files", Set[agent_file_alias.ReadWriteFile]): Exposes locked read-write files.
        """
        ...

    @operation
    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Locks a read-write file against modification.

        REQUIREMENTS:
        - The edit manager supports locking individual read-write files against modification.

        GROUNDING_PROVISIONS:
        - action("lock_file", None): Locks a read-write file.
        """
        ...

    @operation
    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Unlocks a read-write file to allow modification.

        REQUIREMENTS:
        - The edit manager supports unlocking individual read-write files.

        GROUNDING_PROVISIONS:
        - action("unlock_file", None): Unlocks a read-write file.
        """
        ...

    @operation
    def materialize_templates(self) -> None:
        """Materializes templates into missing read-write files at session start.

        REQUIREMENTS:
        - Materializing templates populates missing read-write files with initial template content without overwriting existing files.

        GROUNDING_PROVISIONS:
        - action("materialize_templates", None): Materializes missing files with template content.
        """
        ...

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """Tracks the last file read or edited across the session.

        REQUIREMENTS:
        - The edit manager tracks the last read or edited file across the session, recording file reads from file readers and file edits from editing tools.

        GROUNDING_PROVISIONS:
        - knows("last_read_or_edited_file", Optional[agent_file_alias.FileAlias]): Tracks last read or edited file.
        """
        ...

    @operation
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """Records that a file was read by a file reader.

        GROUNDING_PROVISIONS:
        - action("record_file_read", None): Records file read.
        """
        ...

    @operation
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """Records that a file was edited by an editing tool.

        GROUNDING_PROVISIONS:
        - action("record_file_edit", None): Records file edit.
        """
        ...

    @operation
    def file_hash(self, file: agent_file_alias.FileAlias) -> str:
        """Computes a file hash for a read-write file from its content.

        REQUIREMENTS:
        - The edit manager computes a file hash for a read-write file from its content.

        GROUNDING_PROVISIONS:
        - action("file_hash", str): Computes file content hash.
        """
        ...

    @operation
    def can_write(self, path: Union[str, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        """Validates modification access for a read-write file.

        REQUIREMENTS:
        - The edit manager provides a can write operation validating modification access for a read-write file.

        GROUNDING_PROVISIONS:
        - action("can_write", tool_provider.ToolResponse): Validates file write permission and lock state.
        """
        ...


@singleton_type('agent_session')
class ReplaceFileContentTool(EditingTool, Protocol):
    """Editing tool that replaces target content in a read-write file."""

    @property
    def file_alias_parameter(self) -> tool_provider.ToolParameter:
        """Parameter identifying the target read-write file."""
        ...

    @property
    def target_content_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the target content to replace."""
        ...

    @property
    def replacement_content_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the replacement content."""
        ...

    @property
    def start_line_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the starting line index of the search window."""
        ...

    @property
    def end_line_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying the ending line index of the search window."""
        ...

    @property
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter:
        """Parameter specifying whether to allow replacing multiple occurrences."""
        ...

    @property
    @override
    def name(self) -> str:
        """Name of the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description of the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Parameters accepted by the tool."""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.ToolResponse:
        """Executes tool with actual parameter bindings."""
        ...
