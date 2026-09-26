from dataclasses import dataclass
from typing import Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier


@dataclass(frozen=True)
@data_type
class HostPath:
    """A value record representing a filesystem path on the host operating system.

    Args:
        path: The string representing the filesystem path.
    """
    path: str


@dataclass(frozen=True)
@data_type
class AbsolutePath(HostPath):
    """An absolute filesystem path on the host operating system."""
    ...


@dataclass(frozen=True)
@data_type
class WorkspacePath(HostPath):
    """A relative filesystem path anchored to the root of a workspace without leading path separators."""
    ...


@dataclass(frozen=True)
@data_type
class DirectoryPath(AbsolutePath):
    """An absolute filesystem path representing a directory."""
    ...


@dataclass(frozen=True)
@data_type
class WorkspaceRoot(DirectoryPath):
    """An absolute filesystem path representing the root directory of a workspace."""
    ...


@singleton_type("system")
class FilePathManager(InTier[SystemTier], Protocol):
    """Validates and resolves path representations."""

    @operation
    def create_host_path(self, path: str) -> HostPath:
        """Creates a host path from a path string.

        Args:
            path: The non-empty string representing the filesystem path.

        Returns:
            A host path encapsulating the path string.

        ASSUMPTIONS:
        - The caller supplies a non-empty string.

        REQUIREMENTS:
        - MUST return a host path encapsulating the path string.

        GROUNDING_PROVISIONS:
        - action("create_host_path", HostPath): Creates a host path encapsulating the path string to satisfy requirement 5.
        """
        ...

    @operation
    def create_absolute_path(self, path: str) -> AbsolutePath:
        """Creates an absolute path from a path string.

        Args:
            path: The string representing an absolute filesystem path.

        Returns:
            An absolute path encapsulating the path string.

        ASSUMPTIONS:
        - The caller supplies a non-empty string.

        REQUIREMENTS:
        - MUST validate that the path is absolute and return an absolute path encapsulating the path string.

        GROUNDING_PROVISIONS:
        - action("create_absolute_path", AbsolutePath): Creates an absolute path from a path string to satisfy requirement 6.
        """
        ...

    @operation
    def create_workspace_path(self, path: str) -> WorkspacePath:
        """Creates a workspace path from a path string.

        Args:
            path: The string representing a relative filesystem path.

        Returns:
            A workspace path encapsulating the path string.

        ASSUMPTIONS:
        - The caller supplies a non-empty string.

        REQUIREMENTS:
        - MUST validate that the path is relative without leading separators and return a workspace path encapsulating the path string.

        GROUNDING_PROVISIONS:
        - action("create_workspace_path", WorkspacePath): Creates a workspace path from a path string to satisfy requirement 7.
        """
        ...

    @operation
    def resolve_path(self, root: AbsolutePath, relative: WorkspacePath) -> AbsolutePath:
        """Resolves a workspace path into an absolute path given the absolute path of a workspace root.

        Args:
            root: The absolute path of the workspace root.
            relative: The relative workspace path.

        Returns:
            An absolute path formed by joining the workspace root and the relative workspace path.

        REQUIREMENTS:
        - MUST return an absolute path formed by joining the workspace root and the relative workspace path.

        GROUNDING_PROVISIONS:
        - action("resolve_path", WorkspacePath): Resolves an absolute path from a workspace root and relative workspace path to satisfy requirement 8.
        """
        ...
