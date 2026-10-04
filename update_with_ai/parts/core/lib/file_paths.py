# Requirements specified in file_paths.pyi
from dataclasses import dataclass
from typing import NewType, Protocol

PathString = NewType("PathString", str)
ValidationMessage = NewType("ValidationMessage", str)


@dataclass(frozen=True)
class HostPath:
    path: PathString


@dataclass(frozen=True)
class AbsolutePath(HostPath):
    pass


@dataclass(frozen=True)
class WorkspacePath(HostPath):
    pass


@dataclass(frozen=True)
class WorkspaceRoot(AbsolutePath):
    pass


@dataclass(frozen=True)
class PathValidationError(ValueError):
    message: ValidationMessage


class FilePathManager(Protocol):
    def create_host_path(self, path: PathString) -> HostPath: ...

    def create_absolute_path(self, path: PathString) -> AbsolutePath: ...

    def create_workspace_path(self, path: PathString) -> WorkspacePath: ...

    def resolve_path(
        self, root: AbsolutePath, relative: WorkspacePath
    ) -> AbsolutePath: ...
