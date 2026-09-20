"""File alias interface and data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Type
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.sandbox.lib import tool_provider

# Re-export path types from file_paths for backwards compatibility
from update_with_ai.parts.bazel.lib.file_paths import (
    HostPath,
    AbsolutePath,
    WorkspacePath,
    DirectoryPath,
    WorkspaceRoot,
)

FileContent = str
RegexPattern = str


@dataclass(frozen=True, init=False)
class FileAlias:
    relative_path: str

    def __str__(self) -> str:
        return self.relative_path


@dataclass(frozen=True, init=False)
class BoundFile(FileAlias):
    workspace_path: WorkspacePath
    owning_node: dag_storage.Node


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    def __init__(
        self,
        relative_path: str,
        workspace_path: WorkspacePath,
        owning_node: dag_storage.Node,
    ) -> None:
        object.__setattr__(self, "relative_path", relative_path)
        object.__setattr__(self, "workspace_path", workspace_path)
        object.__setattr__(self, "owning_node", owning_node)


@dataclass(frozen=True)
class ReadWriteFile(BoundFile):
    def __init__(
        self,
        relative_path: str,
        workspace_path: WorkspacePath,
        owning_node: dag_storage.Node,
    ) -> None:
        object.__setattr__(self, "relative_path", relative_path)
        object.__setattr__(self, "workspace_path", workspace_path)
        object.__setattr__(self, "owning_node", owning_node)


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    def __init__(self, relative_path: str) -> None:
        object.__setattr__(self, "relative_path", relative_path)


class AliasManager(tool_provider.ParameterType[FileAlias, str], Protocol):
    @property
    def workspace_root(self) -> WorkspaceRoot: ...

    @property
    def actual_type(self) -> Type[FileAlias]: ...

    @property
    def wire_type(self) -> Type[str]: ...

    def to_actual(self, value: str) -> FileAlias: ...

    def to_wire(self, value: FileAlias) -> str: ...

    def convert(self, wire_value: str) -> FileAlias: ...

    def sanitize_text(self, text: str) -> str: ...
