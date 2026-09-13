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
    short_name: str

    def __str__(self) -> str:
        return self.short_name


@dataclass(frozen=True, init=False)
class BoundFile(FileAlias):
    workspace_path: WorkspacePath
    owning_node: dag_storage.Node


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    def __init__(
        self,
        short_name: str,
        workspace_path: WorkspacePath,
        owning_node: dag_storage.Node,
    ) -> None:
        object.__setattr__(self, "short_name", short_name)
        object.__setattr__(self, "workspace_path", workspace_path)
        object.__setattr__(self, "owning_node", owning_node)


@dataclass(frozen=True)
class ReadWriteFile(BoundFile):
    def __init__(
        self,
        short_name: str,
        workspace_path: WorkspacePath,
        owning_node: dag_storage.Node,
    ) -> None:
        object.__setattr__(self, "short_name", short_name)
        object.__setattr__(self, "workspace_path", workspace_path)
        object.__setattr__(self, "owning_node", owning_node)


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    def __init__(self, short_name: str) -> None:
        object.__setattr__(self, "short_name", short_name)


class AliasManager(tool_provider.ParameterConverter, Protocol):
    @property
    def workspace_root(self) -> WorkspaceRoot: ...

    @property
    def actual_type(self) -> Type: ...

    @property
    def wire_type(self) -> tool_provider.WireType: ...

    def convert(self, wire_value: Any) -> FileAlias: ...

    def sanitize_text(self, text: str) -> str: ...
