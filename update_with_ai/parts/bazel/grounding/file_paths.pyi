from dataclasses import dataclass
from framework import data_type, operation, override, singleton_type

@dataclass(frozen=True, init=False)
@data_type
class HostPath:
    """
PURPOSE:
A host path is a value record representing a filesystem path on the host operating system, having a path string.
"""

    @property
    def path(self) -> str:
        """
PURPOSE:
The string representing the filesystem path.
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class AbsolutePath(HostPath):
    """
PURPOSE:
An absolute path is a host path that represents an absolute filesystem path on the host operating system.
"""

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
The string representing the filesystem path.
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class WorkspacePath(HostPath):
    """
PURPOSE:
A workspace path is a host path that represents a relative filesystem path anchored to the root of a workspace without leading path separators.
"""

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
The string representing the filesystem path.
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class DirectoryPath(AbsolutePath):
    """
PURPOSE:
A directory path is an absolute path that represents a directory on the host operating system.
"""

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
The string representing the filesystem path.
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class WorkspaceRoot(DirectoryPath):
    """
PURPOSE:
A workspace root is a directory path representing the root directory of the workspace.
"""

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
The string representing the filesystem path.
"""
        ...

@singleton_type('system')
class FilePaths:
    """
PURPOSE:
The file paths service is a system service that creates, validates, and resolves path representations.
"""

    @operation
    def create_host_path(self, path: str) -> HostPath:
        """
PURPOSE:
Creates a host path from a path string.

FRESH_ASSUMPTIONS:
- The caller supplies a non-empty string.

FRESH_REQUIREMENTS:
- Returns a host path encapsulating the path string.
"""
        ...

    @operation
    def create_absolute_path(self, path: str) -> AbsolutePath:
        """
PURPOSE:
Creates an absolute path from a path string.

FRESH_ASSUMPTIONS:
- The caller supplies a valid absolute path format for the host operating system.

FRESH_REQUIREMENTS:
- If the path string is absolute, returns an absolute path encapsulating the path string.
- If the path string is not absolute, raises a failure.
"""
        ...

    @operation
    def create_workspace_path(self, path: str) -> WorkspacePath:
        """
PURPOSE:
Creates a workspace path from a path string.

FRESH_ASSUMPTIONS:
- The caller supplies a valid relative path format without leading separators.

FRESH_REQUIREMENTS:
- If the path string is relative, returns a workspace path encapsulating the path string.
- If the path string is absolute, raises a failure.
"""
        ...

    @operation
    def create_directory_path(self, path: str) -> DirectoryPath:
        """
PURPOSE:
Creates a directory path from a path string.

FRESH_ASSUMPTIONS:
- The caller supplies a valid absolute directory path format for the host operating system.

FRESH_REQUIREMENTS:
- If the path string is absolute, returns a directory path encapsulating the path string.
- If the path string is not absolute, raises a failure.
"""
        ...

    @operation
    def get_workspace_root(self) -> WorkspaceRoot:
        """
PURPOSE:
Gets the root directory of the workspace.

FRESH_REQUIREMENTS:
- Returns a workspace root representing the physical workspace root directory.
"""
        ...

    @operation
    def resolve_directory(self, root: WorkspaceRoot, relative: WorkspacePath) -> DirectoryPath:
        """
PURPOSE:
Resolves a directory path from a workspace root and relative workspace path.

FRESH_ASSUMPTIONS:
- The workspace path is a relative path within the root.

FRESH_REQUIREMENTS:
- Returns a directory path formed by joining the workspace root and the workspace path.
"""
        ...

    @operation
    def resolve_path(self, root: WorkspaceRoot, relative: WorkspacePath) -> AbsolutePath:
        """
PURPOSE:
Resolves an absolute path from a workspace root and relative workspace path.

FRESH_ASSUMPTIONS:
- The workspace path is a relative path within the root.

FRESH_REQUIREMENTS:
- Returns an absolute path formed by joining the workspace root and the workspace path.
"""
        ...
