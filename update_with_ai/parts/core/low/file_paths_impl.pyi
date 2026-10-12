# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T03:06:14Z
# CHANGE: Ground path mechanics on host filesystem operations and contract empty path rejection
# CODE_HASH: a36b48ae4048
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

"""File paths implementation low-level specification."""

import os
from framework import operation, override, singleton_type
import file_paths


@singleton_type("system")
class FilePathManager(file_paths.FilePathManager):
    """Realizes path validation and resolution using host filesystem operations.

    GROUNDING:
    - Provides strongly typed host, absolute, and workspace path construction, syntactic
      validation, and separator normalization by invoking the filesystem_ext host path
      operations os.path.isabs, os.path.normpath, and os.path.join on caller-supplied path
      strings and encapsulating the resulting strings in file_paths.HostPath,
      file_paths.AbsolutePath, and file_paths.WorkspacePath records.
    - Rejects empty path strings on every construction operation by inspecting the
      caller-supplied argument before any host filesystem operation and raising
      file_paths.PathValidationError.
    """

    @operation
    @override
    def create_host_path(self, path: file_paths.PathString) -> file_paths.HostPath:
        """Creates a host path record from a path string.

        GROUNDING:
        - Detects empty caller-supplied path strings before construction and raises
          file_paths.PathValidationError, then constructs file_paths.HostPath directly from
          the supplied path string for strings naming neither an absolute nor a workspace
          location.

        POSTCONDITIONS:
        - WHEN the supplied path string is empty, MUST raise file_paths.PathValidationError with diagnostic feedback formatted as "Path cannot be empty".
        """
        ...

    @operation
    @override
    def create_absolute_path(self, path: file_paths.PathString) -> file_paths.AbsolutePath:
        """Creates an absolute path record from a path string.

        GROUNDING:
        - Verifies absoluteness through the filesystem_ext host path operation
          os.path.isabs on the caller-supplied path string, raising
          file_paths.PathValidationError when the string is relative, then normalizes
          redundant separators and relative directory segments with os.path.normpath and
          encapsulates the normalized string in a file_paths.AbsolutePath record.
        """
        ...

    @operation
    @override
    def create_workspace_path(self, path: file_paths.PathString) -> file_paths.WorkspacePath:
        """Creates a relative workspace path record without leading separators.

        GROUNDING:
        - Inspects the caller-supplied path string for leading separators and delegates
          absoluteness verification to the filesystem_ext host path operation
          os.path.isabs, raising file_paths.PathValidationError on either rejection, then
          normalizes redundant separators and relative directory segments with
          os.path.normpath and encapsulates the normalized string in a
          file_paths.WorkspacePath record.
        """
        ...

    @operation
    @override
    def resolve_path(
        self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath
    ) -> file_paths.AbsolutePath:
        """Combines a workspace root with a relative workspace path into an absolute path.

        GROUNDING:
        - Joins the workspace root and workspace path strings through the filesystem_ext host
          path operation os.path.join, normalizes the combined result with os.path.normpath,
          and encapsulates the normalized result in a file_paths.AbsolutePath record.
        """
        ...
