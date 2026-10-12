# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T04:58:25Z
# CHANGE: Remove generated scaffold markers and document the declared path data types and manager operations from the grounding specification
# CODE_HASH: 53ff9bd18d18
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol

# Requirements specified in file_paths.pyi

PathString = NewType("PathString", str)

ValidationMessage = NewType("ValidationMessage", str)


@dataclass(frozen=True)
class HostPath:
    """A host path record encapsulating a path string naming a file or directory on the host filesystem without guaranteeing whether the path string is absolute or relative.

    Args:
        path: The path string naming a file or directory on the host filesystem.

    INVARIANTS:
    - MUST encapsulate a non-empty path string.
    """

    path: PathString


@dataclass(frozen=True)
class AbsolutePath(HostPath):
    """A host path whose path string names a location from the filesystem root.

    INVARIANTS:
    - MUST encapsulate a path string naming a location from the filesystem root.
    """

    pass


@dataclass(frozen=True)
class WorkspacePath(HostPath):
    """A host path whose path string names a location relative to the root of a workspace without a leading path separator.

    INVARIANTS:
    - MUST encapsulate a path string naming a location relative to the root of a workspace without a leading path separator.
    """

    pass


@dataclass(frozen=True)
class WorkspaceRoot(AbsolutePath):
    """An absolute path representing the root directory of a workspace.

    INVARIANTS:
    - MUST represent the root directory of a workspace.
    """

    pass


@dataclass(frozen=True)
class PathValidationError(ValueError):
    """Indicates that a path string is invalid for the target path type.

    Args:
        message: Diagnostic feedback describing the path validation failure.
    """

    message: ValidationMessage


class FilePathManager(Protocol):
    """Validates and resolves path representations."""

    def create_host_path(self, path: PathString) -> HostPath:
        """Creates a host path from a path string.

        Args:
            path: The path string naming a file or directory on the host filesystem.

        Returns:
            A host path encapsulating the path string.

        PRECONDITIONS:
        - A caller supplies a non-empty path string.

        POSTCONDITIONS:
        - MUST encapsulate the supplied path string in the produced host path.
        - WHEN the supplied path string names neither an absolute nor a workspace location, MUST create the host path directly.
        """
        ...

    def create_absolute_path(self, path: PathString) -> AbsolutePath:
        """Creates an absolute path from a path string.

        Args:
            path: The string representing an absolute filesystem path.

        Returns:
            An absolute path encapsulating the path string.

        PRECONDITIONS:
        - A caller supplies a non-empty path string.

        POSTCONDITIONS:
        - MUST validate that the supplied path string is an absolute path string.
        - WHEN the supplied path string is not absolute, MUST raise PathValidationError with diagnostic feedback formatted as "Path is not absolute: {path}".
        """
        ...

    def create_workspace_path(self, path: PathString) -> WorkspacePath:
        """Creates a workspace path from a path string.

        Args:
            path: The string representing a relative filesystem path.

        Returns:
            A workspace path encapsulating the path string.

        PRECONDITIONS:
        - A caller supplies a non-empty path string.

        POSTCONDITIONS:
        - MUST validate that the supplied path string is relative without leading path separators.
        - WHEN the supplied path string is an absolute path string, MUST raise PathValidationError with diagnostic feedback formatted as "Workspace path must be relative, got absolute: {path}".
        - WHEN the supplied path string has leading path separators, MUST raise PathValidationError with diagnostic feedback formatted as "Workspace path must be relative, got absolute: {path}".
        """
        ...

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
        - MUST produce the combined absolute path formed by joining the workspace root absolute path with the workspace path.
        """
        ...
