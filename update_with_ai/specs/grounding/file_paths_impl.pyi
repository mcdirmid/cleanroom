from framework import operation, override, singleton_type
import file_paths
import filesystem_ext

@singleton_type('system')
class FilePaths(file_paths.FilePaths):
    """
PURPOSE:
The file paths implementation is a system service implementing the file paths interface.
"""

    @operation
    @override
    def create_host_path(self, path: str) -> file_paths.HostPath:
        """
PURPOSE:
Creates a host path from a path string.

INHERITED_ASSUMPTIONS:
- [FilePaths] The caller supplies a non-empty string.

INHERITED_REQUIREMENTS:
- [FilePaths] Returns a host path encapsulating the path string.

GROUNDING_ARGUMENT:
Instantiates a host path record holding the path string.
"""
        ...

    @operation
    @override
    def create_absolute_path(self, path: str) -> file_paths.AbsolutePath:
        """
PURPOSE:
Creates an absolute path from a path string.

INHERITED_ASSUMPTIONS:
- [FilePaths] The caller supplies a valid absolute path format for the host operating system.

INHERITED_REQUIREMENTS:
- [FilePaths] If the path string is absolute, returns an absolute path encapsulating the path string.
- [FilePaths] If the path string is not absolute, raises a failure.

GROUNDING_ARGUMENT:
Verifies that the path string is absolute using the host filesystem, raising ValueError if not, and instantiates an absolute path record holding the path string.
"""
        ...

    @operation
    @override
    def create_workspace_path(self, path: str) -> file_paths.WorkspacePath:
        """
PURPOSE:
Creates a workspace path from a path string.

INHERITED_ASSUMPTIONS:
- [FilePaths] The caller supplies a valid relative path format without leading separators.

INHERITED_REQUIREMENTS:
- [FilePaths] If the path string is relative, returns a workspace path encapsulating the path string.
- [FilePaths] If the path string is absolute, raises a failure.

GROUNDING_ARGUMENT:
Verifies that the path string is not absolute using the host filesystem, raising ValueError if absolute, and instantiates a workspace path record holding the path string.
"""
        ...

    @operation
    @override
    def create_directory_path(self, path: str) -> file_paths.DirectoryPath:
        """
PURPOSE:
Creates a directory path from a path string.

INHERITED_ASSUMPTIONS:
- [FilePaths] The caller supplies a valid absolute directory path format for the host operating system.

INHERITED_REQUIREMENTS:
- [FilePaths] If the path string is absolute, returns a directory path encapsulating the path string.
- [FilePaths] If the path string is not absolute, raises a failure.

GROUNDING_ARGUMENT:
Verifies that the path string is absolute using the host filesystem, raising ValueError if not, and instantiates a directory path record holding the path string.
"""
        ...

    @operation
    @override
    def get_workspace_root(self) -> file_paths.WorkspaceRoot:
        """
PURPOSE:
Gets the root directory of the workspace.

INHERITED_REQUIREMENTS:
- [FilePaths] Returns a workspace root representing the physical workspace root directory.

GROUNDING_ARGUMENT:
Checks the environment for BUILD_WORKSPACE_DIRECTORY, falling back to current working directory, and instantiates a workspace root record holding the resolved directory path.
"""
        ...

    @operation
    @override
    def resolve_directory(self, root: file_paths.WorkspaceRoot, relative: file_paths.WorkspacePath) -> file_paths.DirectoryPath:
        """
PURPOSE:
Resolves a directory path from a workspace root and relative workspace path.

INHERITED_ASSUMPTIONS:
- [FilePaths] The workspace path is a relative path within the root.

INHERITED_REQUIREMENTS:
- [FilePaths] Returns a directory path formed by joining the workspace root and the workspace path.

GROUNDING_ARGUMENT:
Joins root.path and relative.path using os.path.join and instantiates a directory path record holding the joined path.
"""
        ...

    @operation
    @override
    def resolve_path(self, root: file_paths.WorkspaceRoot, relative: file_paths.WorkspacePath) -> file_paths.AbsolutePath:
        """
PURPOSE:
Resolves an absolute path from a workspace root and relative workspace path.

INHERITED_ASSUMPTIONS:
- [FilePaths] The workspace path is a relative path within the root.

INHERITED_REQUIREMENTS:
- [FilePaths] Returns an absolute path formed by joining the workspace root and the workspace path.

GROUNDING_ARGUMENT:
Joins root.path and relative.path using os.path.join and instantiates an absolute path record holding the joined path.
"""
        ...
