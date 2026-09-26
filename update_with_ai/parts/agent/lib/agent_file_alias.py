# Requirements specified in agent_file_alias.pyi
"""File alias interface and data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Type
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.sandbox.lib import tool_provider

# Re-export path types from file_paths for backwards compatibility
from update_with_ai.parts.core.lib.file_paths import (
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
    owning_node: dag_storage.DagNode


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    def __init__(
        self,
        relative_path: str,
        workspace_path: WorkspacePath,
        owning_node: dag_storage.DagNode,
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
        owning_node: dag_storage.DagNode,
    ) -> None:
        object.__setattr__(self, "relative_path", relative_path)
        object.__setattr__(self, "workspace_path", workspace_path)
        object.__setattr__(self, "owning_node", owning_node)


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    def __init__(self, relative_path: str) -> None:
        object.__setattr__(self, "relative_path", relative_path)


class AliasManager(tool_provider.ParameterType[FileAlias, tool_provider.WireString], Protocol):
    @property
    def workspace_root(self) -> WorkspaceRoot: ...

    @property
    def actual_type(self) -> Type[FileAlias]: ...

    @property
    def wire_type(self) -> Type[tool_provider.WireString]: ...

    def convert(self, wire_value: tool_provider.WireString) -> FileAlias: ...

    def sanitize_text(self, text: str) -> str: ...
