"""File paths implementation low-level specification."""

from framework import operation, override, singleton_type
import file_paths


@singleton_type("system")
class FilePathManager(file_paths.FilePathManager):
    """Realizes path validation and resolution using host filesystem operations."""

    @operation
    @override
    def create_host_path(self, path: file_paths.PathString) -> file_paths.HostPath:
        ...

    @operation
    @override
    def create_absolute_path(self, path: file_paths.PathString) -> file_paths.AbsolutePath:
        ...

    @operation
    @override
    def create_workspace_path(self, path: file_paths.PathString) -> file_paths.WorkspacePath:
        ...

    @operation
    @override
    def resolve_path(
        self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath
    ) -> file_paths.AbsolutePath:
        ...
