"""File paths low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier

PathString = NewType("PathString", str)
ValidationMessage = NewType("ValidationMessage", str)


@dataclass(frozen=True)
@data_type
class HostPath:
    """A value record representing a filesystem path on the host operating system.

    Args:
        path: The string representing the filesystem path.

    INVARIANTS:
    - The path string is non-empty.
    """
    path: PathString


@dataclass(frozen=True)
@data_type
class AbsolutePath(HostPath):
    """An absolute filesystem path on the host operating system.

    INVARIANTS:
    - The path is an absolute filesystem path.
    """
    ...


@dataclass(frozen=True)
@data_type
class WorkspacePath(HostPath):
    """A relative filesystem path anchored to the root of a workspace without leading path separators.

    INVARIANTS:
    - The path is a relative filesystem path anchored to a workspace root without leading path separators.
    """
    ...


@dataclass(frozen=True)
@data_type
class WorkspaceRoot(AbsolutePath):
    """An absolute filesystem path representing the root directory of a workspace.

    INVARIANTS:
    - The path represents the root directory of a workspace.
    """
    ...


@dataclass(frozen=True)
@data_type
class PathValidationError(ValueError):
    """Raised when path validation fails.

    Args:
        message: Diagnostic feedback describing the path validation failure.
    """
    message: ValidationMessage


@singleton_type("system")
class FilePathManager(InTier[SystemTier], Protocol):
    """Validates and resolves path representations."""

    @operation
    def create_host_path(self, path: PathString) -> HostPath:
        """Creates a host path from a path string.

        Args:
            path: The string representing the filesystem path.

        Returns:
            A host path encapsulating the path string.

        PRECONDITIONS:
        - A caller supplies a non-empty path string.

        POSTCONDITIONS:
        - MUST return a host path encapsulating the path string.
        """
        ...

    @operation
    def create_absolute_path(self, path: PathString) -> AbsolutePath:
        """Creates an absolute path from a path string.

        Args:
            path: The string representing an absolute filesystem path.

        Returns:
            An absolute path encapsulating the path string.

        PRECONDITIONS:
        - A caller supplies a non-empty path string.

        POSTCONDITIONS:
        - MUST validate that the path is absolute and return an absolute path encapsulating the path string.
        - WHEN the path is not absolute, MUST raise PathValidationError with diagnostic feedback formatted as "Path is not absolute: {path}".
        """
        ...

    @operation
    def create_workspace_path(self, path: PathString) -> WorkspacePath:
        """Creates a workspace path from a path string.

        Args:
            path: The string representing a relative filesystem path.

        Returns:
            A workspace path encapsulating the path string.

        PRECONDITIONS:
        - A caller supplies a non-empty path string.

        POSTCONDITIONS:
        - MUST validate that the path is relative without leading path separators and return a workspace path encapsulating the path string.
        - WHEN the path is absolute or has leading path separators, MUST raise PathValidationError with diagnostic feedback formatted as "Workspace path must be relative, got absolute: {path}".
        """
        ...

    @operation
    def resolve_path(
        self, root: AbsolutePath, relative: WorkspacePath
    ) -> AbsolutePath:
        """Resolves a workspace path into an absolute path given the absolute path of a workspace root.

        Args:
            root: The absolute path of the workspace root.
            relative: The relative workspace path.

        Returns:
            An absolute path formed by joining the workspace root and the relative workspace path.

        PRECONDITIONS:
        - A caller supplies a workspace path.
        - A caller supplies a workspace root absolute path.

        POSTCONDITIONS:
        - MUST produce the combined absolute path formed by joining the workspace root and the relative workspace path.
        """
        ...
