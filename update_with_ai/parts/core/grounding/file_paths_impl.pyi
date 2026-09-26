from framework import operation, override, singleton_type
import file_paths
import filesystem_ext


@singleton_type("system")
class FilePathManager(file_paths.FilePathManager):
    """Realizes path validation and resolution using host filesystem operations.

    GROUNDING_ARGUMENT:
    - As a system singleton, FilePathManager provides path creation and resolution services, interacting with imported filesystem_ext.
    """

    @operation
    @override
    def create_host_path(self, path: str) -> file_paths.HostPath:
        """Creates a host path encapsulating a path string.

        Args:
            path: The non-empty string representing the filesystem path.

        Returns:
            A host path encapsulating the path string.

        REQUIREMENTS:
        - MUST return a host path encapsulating the path string.

        GROUNDING_PROVISIONS:
        - action("create_host_path", file_paths.HostPath): Creates a host path encapsulating the path string to satisfy requirement 5.

        GROUNDING_ARGUMENT:
        - Instantiates a host path record holding the path string.
        """
        ...

    @operation
    @override
    def create_absolute_path(self, path: str) -> file_paths.AbsolutePath:
        """Creates an absolute path after validating that the string is absolute.

        Args:
            path: The string representing an absolute filesystem path.

        Returns:
            An absolute path encapsulating the path string.

        REQUIREMENTS:
        - MUST validate that the path is absolute and return an absolute path encapsulating the path string.

        GROUNDING_PROVISIONS:
        - action("create_absolute_path", file_paths.AbsolutePath): Creates an absolute path from a path string to satisfy requirement 6.

        GROUNDING_ARGUMENT:
        - Verifies that the path string is absolute using imported filesystem_ext and instantiates an absolute path record holding the path string.
        """
        ...

    @operation
    @override
    def create_workspace_path(self, path: str) -> file_paths.WorkspacePath:
        """Creates a workspace path after validating that the string is relative.

        Args:
            path: The string representing a relative filesystem path.

        Returns:
            A workspace path encapsulating the path string.

        REQUIREMENTS:
        - MUST validate that the path is relative without leading separators and return a workspace path encapsulating the path string.

        GROUNDING_PROVISIONS:
        - action("create_workspace_path", file_paths.WorkspacePath): Creates a workspace path from a path string to satisfy requirement 7.

        GROUNDING_ARGUMENT:
        - Verifies that the path string is relative without leading separators and instantiates a workspace path record holding the path string.
        """
        ...

    @operation
    @override
    def resolve_path(self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath) -> file_paths.AbsolutePath:
        """Resolves a workspace path into an absolute path given a workspace root.

        Args:
            root: The absolute path of the workspace root.
            relative: The relative workspace path.

        Returns:
            An absolute path formed by joining the workspace root and the relative workspace path.

        REQUIREMENTS:
        - MUST return an absolute path formed by joining the workspace root and the relative workspace path.

        GROUNDING_PROVISIONS:
        - action("resolve_path", file_paths.WorkspacePath): Resolves an absolute path from a workspace root and relative workspace path to satisfy requirement 8.

        GROUNDING_ARGUMENT:
        - Joins root.path and relative.path using imported filesystem_ext and instantiates an absolute path record holding the joined path.
        """
        ...



