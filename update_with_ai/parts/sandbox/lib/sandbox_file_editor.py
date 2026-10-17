# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:47Z
# CHANGE: Prune the unused Set import that the grounding specification does not declare
# CODE_HASH: 971e42e5e86b
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, NewType, Optional, Protocol, Union
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
from . import tool_provider

# Requirements specified in sandbox_file_editor.pyi

FileUpdateRevision = NewType('FileUpdateRevision', int)

LineNumber = NewType('LineNumber', int)

TargetContent = NewType('TargetContent', str)

ReplacementContent = NewType('ReplacementContent', str)

FileHash = NewType('FileHash', str)

AllowMultiple = NewType('AllowMultiple', bool)

class EditingTool(tool_provider.Tool, Protocol):
    # Contract: Name of the editing tool.
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    # Contract: Description of the editing tool.
    @property
    def description(self) -> tool_provider.ToolDescription:
        ...

    # Contract: Parameter mapping accepted by editing tool.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    # Contract: Executes editing tool with actual parameter bindings.
    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        ...


class EditManager(Protocol):
    # Contract: Exposes whether workspace file modifications occurred during the session.
    @property
    def has_modifications(self) -> bool:
        ...

    # Contract: Exposes sequential update revision for workspace files.
    @property
    def file_update_revision(self) -> FileUpdateRevision:
        ...

    # Contract: Tracks last file read or edited across the session.
    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        ...

    # Contract: Records file read event, updating last read or edited file.
    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        ...

    # Contract: Records file edit event, updating last read or edited file and advancing revision.
    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        ...

    # Contract: Computes file hash from content.
    def file_hash(self, file: agent_file_alias.FileAlias) -> FileHash:
        ...

    # Contract: Validates write access for read-write files.
    def can_write(self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        ...


class ReplaceFileContentTool(EditingTool, Protocol):
    # Contract: Installs replace file content tool into session ToolManager.
    def initialize(self) -> None:
        ...

    # Contract: Parameter identifying target read-write file.
    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        ...

    # Contract: Parameter specifying target content to replace.
    @property
    def target_content_parameter(self) -> tool_provider.ToolParameter[TargetContent, str]:
        ...

    # Contract: Parameter specifying replacement content.
    @property
    def replacement_content_parameter(self) -> tool_provider.ToolParameter[ReplacementContent, str]:
        ...

    # Contract: Parameter specifying starting line index of search window.
    @property
    def start_line_parameter(self) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        ...

    # Contract: Parameter specifying ending line index of search window.
    @property
    def end_line_parameter(self) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        ...

    # Contract: Parameter specifying whether to allow replacing multiple occurrences.
    @property
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter[AllowMultiple, bool]:
        ...

    # Contract: Replaces target content with replacement content within bounded range.
    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        ...
