# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 823352c0dab1
# --- END CLEANROOM METADATA ---

# Requirements specified in agent_file_alias.pyi
from __future__ import annotations

from dataclasses import dataclass
from typing import NewType, Protocol, Type
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.sandbox.lib import tool_provider

from update_with_ai.parts.core.lib.file_paths import (
    HostPath,
    AbsolutePath,
    WorkspacePath,
    WorkspaceRoot,
)

FileContent = NewType("FileContent", str)
RegexPattern = NewType("RegexPattern", str)
RelativePath = NewType("RelativePath", str)
UnsanitizedText = NewType("UnsanitizedText", str)
SanitizedText = NewType("SanitizedText", str)


@dataclass(frozen=True)
class FileAlias:
    relative_path: RelativePath

    def __str__(self) -> str:
        return self.relative_path


@dataclass(frozen=True)
class BoundFile(FileAlias):
    workspace_path: WorkspacePath
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
    def workspace_root(self) -> WorkspaceRoot: ...

    @property
    def actual_type(self) -> Type[FileAlias]: ...

    @property
    def wire_type(self) -> Type[str]: ...

    def convert(self, wire_value: str) -> FileAlias: ...

    def sanitize_text(self, text: UnsanitizedText) -> SanitizedText: ...
