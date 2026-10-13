# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-11T04:59:25Z
# CHANGE: Realize the orphan postcondition that a file alias displays itself by its relative path, and drop the dead tier import and scaffold markers
# CODE_HASH: ebf96e1b0ba3
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol, Type
from dataclasses import dataclass
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
    relative_path: RelativePath

    def __str__(self) -> str:
        """Displays the file alias by its relative path in the agent session."""
        return str(self.relative_path)


@dataclass(frozen=True)
class BoundFile(FileAlias):
    workspace_path: file_paths.WorkspacePath
    owning_node: dag_storage.DagNode


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    pass


@dataclass(frozen=True)
class ReadWriteFile(BoundFile):
    pass


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    pass


class AliasManager(tool_provider.ParameterType[FileAlias, str], Protocol):
    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        ...

    @property
    def actual_type(self) -> Type[FileAlias]:
        ...

    @property
    def wire_type(self) -> Type[str]:
        ...

    def convert(self, wire_value: str) -> FileAlias:
        ...

    def sanitize_text(self, text: UnsanitizedText) -> SanitizedText:
        ...
