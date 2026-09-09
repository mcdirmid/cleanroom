"""File alias interface and data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Type
from . import dag_storage, tool_provider


@dataclass(frozen=True)
class HostPath:
    path: str


@dataclass(frozen=True)
class AbsolutePath(HostPath):
    pass


@dataclass(frozen=True)
class WorkspacePath(HostPath):
    pass


@dataclass(frozen=True)
class DirectoryPath(AbsolutePath):
    pass


@dataclass(frozen=True)
class WorkspaceRoot(DirectoryPath):
    pass


FileContent = str
RegexPattern = str


@dataclass(frozen=True)
class FileAlias:
    short_name: str

    def __str__(self) -> str:
        return self.short_name


@dataclass(frozen=True)
class BoundFile(FileAlias):
    workspace_path: WorkspacePath
    owning_node: dag_storage.Node

    def __init__(
        self,
        short_name: str,
        workspace_path: WorkspacePath,
        owning_node: dag_storage.Node,
    ) -> None:
        super().__init__(short_name)
        object.__setattr__(self, "workspace_path", workspace_path)
        object.__setattr__(self, "owning_node", owning_node)


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    pass


@dataclass(frozen=True)
class ReadWriteFile(BoundFile):
    pass


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    pass


class AliasManager(tool_provider.ParameterConverter, Protocol):
    @property
    def workspace_root(self) -> DirectoryPath: ...

    @property
    def actual_type(self) -> Type: ...

    @property
    def wire_type(self) -> tool_provider.WireType: ...

    def convert(self, wire_value: Any) -> FileAlias: ...

    def sanitize_text(self, text: str) -> str: ...

