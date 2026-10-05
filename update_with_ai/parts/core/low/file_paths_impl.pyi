# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T05:42:17Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a70b56bb1d5f
# --- END CLEANROOM METADATA ---

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
