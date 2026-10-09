# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a81448edae42
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox_file_editor.pyi
from typing import Any, Mapping, NewType, Optional, Protocol, Set, Union
from update_with_ai.parts.agent.lib import agent_file_alias
from . import tool_provider

FileUpdateRevision = NewType("FileUpdateRevision", int)
LineNumber = NewType("LineNumber", int)
TargetContent = NewType("TargetContent", str)
ReplacementContent = NewType("ReplacementContent", str)
FileHash = NewType("FileHash", str)
AllowMultiple = NewType("AllowMultiple", bool)


class EditingTool(tool_provider.Tool, Protocol):
    @property
    def name(self) -> tool_provider.ToolName: ...

    @property
    def description(self) -> tool_provider.ToolDescription: ...

    @property
    def parameters(
        self,
    ) -> Mapping[
        tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
    ]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class EditManager(Protocol):
    @property
    def has_modifications(self) -> bool: ...

    @property
    def file_update_revision(self) -> FileUpdateRevision: ...

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]: ...

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None: ...

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None: ...

    def file_hash(self, file: agent_file_alias.FileAlias) -> FileHash: ...

    def can_write(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse: ...


class ReplaceFileContentTool(EditingTool, Protocol):
    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]: ...

    @property
    def target_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[TargetContent, str]: ...

    @property
    def replacement_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[ReplacementContent, str]: ...

    @property
    def start_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[LineNumber], int]: ...

    @property
    def end_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[LineNumber], int]: ...

    @property
    def allow_multiple_parameter(
        self,
    ) -> tool_provider.ToolParameter[AllowMultiple, bool]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...
