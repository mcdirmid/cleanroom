# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: a70b56bb1d5f
# --- END CLEANROOM METADATA ---

"""File paths implementation low-level specification."""

from framework import operation, override, singleton_type
import file_paths


@singleton_type("system")
class FilePathManager(file_paths.FilePathManager):
    """Realizes path validation and resolution using host filesystem operations.

    GROUNDING:
    - Provides strongly typed path construction, syntactic validation, and
      normalization by validating path segments against native host filesystem mechanics.
    """

    @operation
    @override
    def create_host_path(self, path: file_paths.PathString) -> file_paths.HostPath:
        """Creates a host path record from a path string.

        GROUNDING:
        - Grounded via non-empty string validation and HostPath construction.
        """
        ...

    @operation
    @override
    def create_absolute_path(self, path: file_paths.PathString) -> file_paths.AbsolutePath:
        """Creates an absolute path record from a path string.

        GROUNDING:
        - Grounded via os.path.isabs verification and os.path.normpath normalization.
        """
        ...

    @operation
    @override
    def create_workspace_path(self, path: file_paths.PathString) -> file_paths.WorkspacePath:
        """Creates a relative workspace path record without leading separators.

        GROUNDING:
        - Grounded via rejecting leading separators, verifying relative path nature,
          and normalizing redundant segments.
        """
        ...

    @operation
    @override
    def resolve_path(
        self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath
    ) -> file_paths.AbsolutePath:
        """Combines a workspace root with a relative workspace path into an absolute path.

        GROUNDING:
        - Grounded via os.path.join and os.path.normpath combining root and workspace paths.
        """
        ...
