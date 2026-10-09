# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:42:30Z
# LAST_CHANGED: 2026-10-09T21:42:30Z
# CHANGE: Add initialize method to ReplaceFileContentTool protocol
# CODE_HASH: 799925910787
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, NewType, Optional, Protocol, Set, Union
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
    @property
    def name(self) -> tool_provider.ToolName:
        # TODO_name_body
        ...

    @property
    def description(self) -> tool_provider.ToolDescription:
        # TODO_description_body
        ...

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        # TODO_parameters_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class EditManager(Protocol):
    @property
    def has_modifications(self) -> bool:
        # TODO_has_modifications_body
        ...

    @property
    def file_update_revision(self) -> FileUpdateRevision:
        # TODO_file_update_revision_body
        ...

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        # TODO_last_read_or_edited_file_body
        ...

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        # TODO_record_file_read_body
        ...

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        # TODO_record_file_edit_body
        ...

    def file_hash(self, file: agent_file_alias.FileAlias) -> FileHash:
        # TODO_file_hash_body
        ...

    def can_write(self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        # TODO_can_write_body
        ...


class ReplaceFileContentTool(EditingTool, Protocol):
    def initialize(self) -> None:
        # TODO_initialize_body
        ...

    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        # TODO_path_parameter_body
        ...

    @property
    def target_content_parameter(self) -> tool_provider.ToolParameter[TargetContent, str]:
        # TODO_target_content_parameter_body
        ...

    @property
    def replacement_content_parameter(self) -> tool_provider.ToolParameter[ReplacementContent, str]:
        # TODO_replacement_content_parameter_body
        ...

    @property
    def start_line_parameter(self) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        # TODO_start_line_parameter_body
        ...

    @property
    def end_line_parameter(self) -> tool_provider.ToolParameter[Optional[LineNumber], int]:
        # TODO_end_line_parameter_body
        ...

    @property
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter[AllowMultiple, bool]:
        # TODO_allow_multiple_parameter_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...
