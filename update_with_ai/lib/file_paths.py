"""File paths interface and data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, init=False)
class HostPath:
    path: str

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r})"


@dataclass(frozen=True, init=False)
class AbsolutePath(HostPath):
    pass


@dataclass(frozen=True, init=False)
class WorkspacePath(HostPath):
    pass


@dataclass(frozen=True, init=False)
class DirectoryPath(AbsolutePath):
    pass


@dataclass(frozen=True, init=False)
class WorkspaceRoot(DirectoryPath):
    pass


class FilePaths(ABC):
    @abstractmethod
    def create_host_path(self, path: str) -> HostPath:
        pass

    @abstractmethod
    def create_absolute_path(self, path: str) -> AbsolutePath:
        pass

    @abstractmethod
    def create_workspace_path(self, path: str) -> WorkspacePath:
        pass

    @abstractmethod
    def create_directory_path(self, path: str) -> DirectoryPath:
        pass

    @abstractmethod
    def get_workspace_root(self) -> WorkspaceRoot:
        pass

    @abstractmethod
    def resolve_directory(self, root: WorkspaceRoot, relative: WorkspacePath) -> DirectoryPath:
        pass

    @abstractmethod
    def resolve_path(self, root: WorkspaceRoot, relative: WorkspacePath) -> AbsolutePath:
        pass
