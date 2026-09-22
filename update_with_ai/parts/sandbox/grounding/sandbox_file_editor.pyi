from typing import Optional, Protocol, Set, Union
from framework import data_type, operation, override, poly_type, singleton_type
import agent_file_alias
import tool_provider

@data_type
class Template(agent_file_alias.FileContent):
    """
PURPOSE:
Introduces template as initial file content for a read-write file
"""
    ...

@poly_type
class EditingTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Polymorphic tool that modifies a read-write file

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...

@singleton_type('agent_session')
class EditManager(Protocol):
    """
PURPOSE:
Defined as an agent session service that installs editing tools and tracks session modifications

FRESH_REQUIREMENTS:
- The edit manager installs the replace file content tool.
- Modifying a file records that workspace file modifications occurred during the session.
"""

    @property
    def has_modifications(self) -> bool:
        """
PURPOSE:
Exposes whether workspace file modifications occurred during the session

FRESH_REQUIREMENTS:
- The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.
"""
        ...

    @property
    def file_update_revision(self) -> int:
        """
PURPOSE:
Exposes a file update revision that tracks sequential updates made to workspace files

FRESH_REQUIREMENTS:
- The edit manager exposes a file update revision that tracks sequential updates made to workspace files.
"""
        ...

    @property
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Exposes read-write files locked against modification

FRESH_REQUIREMENTS:
- The edit manager exposes read-write files locked against modification.
"""
        ...

    @operation
    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
PURPOSE:
Locks a read-write file against modification

FRESH_REQUIREMENTS:
- The edit manager supports locking individual read-write files against modification.
"""
        ...

    @operation
    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
PURPOSE:
Unlocks a read-write file to allow modification

FRESH_REQUIREMENTS:
- The edit manager supports unlocking individual read-write files.
"""
        ...

    @operation
    def materialize_templates(self) -> None:
        """
PURPOSE:
Materializes templates into missing read-write files at session start without overwriting existing files

FRESH_REQUIREMENTS:
- Materializing templates populates missing read-write files with initial template content without overwriting existing files.
"""
        ...

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """
PURPOSE:
Tracks the last file read or edited across the session

FRESH_REQUIREMENTS:
- The edit manager tracks the last read or edited file across the session, recording file reads from file readers and file edits from editing tools.
"""
        ...

    @operation
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """
PURPOSE:
Records that a file was read by a file reader
"""
        ...

    @operation
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
PURPOSE:
Records that a file was edited by an editing tool
"""
        ...

    @operation
    def file_hash(self, file: agent_file_alias.FileAlias) -> str:
        """
PURPOSE:
Computes a file hash for a read-write file from its content

FRESH_REQUIREMENTS:
- The edit manager computes a file hash for a read-write file from its content.
"""
        ...

    @operation
    def can_write(self, path: Union[str, agent_file_alias.FileAlias]) -> tool_provider.Response:
        """
PURPOSE:
Validates modification access for a read-write file under lock state and write permissions

FRESH_REQUIREMENTS:
- The edit manager provides a can write operation validating modification access for a read-write file.
"""
        ...

@singleton_type('agent_session')
class ReplaceFileContentTool(EditingTool, Protocol):
    """
PURPOSE:
Defined as an editing tool that replaces target content in a read-write file within an optional line range

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target read-write file
"""
        ...

    @property
    def target_content_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the target content to replace within the file or designated search window
"""
        ...

    @property
    def replacement_content_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the replacement content
"""
        ...

    @property
    def start_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the starting line index of the search window
"""
        ...

    @property
    def end_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the ending line index of the search window
"""
        ...

    @property
    def allow_multiple_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying whether to allow replacing multiple occurrences
"""
        ...

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...
