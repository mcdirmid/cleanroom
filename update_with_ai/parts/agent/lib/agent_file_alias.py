# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T18:40:48Z
# CHANGE: Remove ellipsis defaults from FileAlias and BoundFile dataclasses
# CODE_HASH: 6d018b0030f1
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol, Type
from dataclasses import dataclass
from .agent_session import AgentSessionTier
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
import update_with_ai.parts.core.lib.file_paths as file_paths
import update_with_ai.parts.sandbox.lib.tool_provider as tool_provider

# Requirements specified in agent_file_alias.pyi

FileContent = NewType('FileContent', str)

RegexPattern = NewType('RegexPattern', str)

RelativePath = NewType('RelativePath', str)

UnsanitizedText = NewType('UnsanitizedText', str)

SanitizedText = NewType('SanitizedText', str)

@dataclass(frozen=True)
class FileAlias:
    # TODO_FileAlias_body
    relative_path: RelativePath


@dataclass(frozen=True)
class BoundFile(FileAlias):
    # TODO_BoundFile_body
    workspace_path: file_paths.WorkspacePath
    owning_node: dag_storage.DagNode


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    # TODO_ReadOnlyFile_body
    pass


@dataclass(frozen=True)
class ReadWriteFile(BoundFile):
    # TODO_ReadWriteFile_body
    pass


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    # TODO_UnboundFile_body
    pass


class AliasManager(tool_provider.ParameterType[FileAlias, str], Protocol):
    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        # TODO_workspace_root_body
        ...

    @property
    def actual_type(self) -> Type[FileAlias]:
        # TODO_actual_type_body
        ...

    @property
    def wire_type(self) -> Type[str]:
        # TODO_wire_type_body
        ...

    def convert(self, wire_value: str) -> FileAlias:
        # TODO_convert_body
        ...

    def sanitize_text(self, text: UnsanitizedText) -> SanitizedText:
        # TODO_sanitize_text_body
        ...
