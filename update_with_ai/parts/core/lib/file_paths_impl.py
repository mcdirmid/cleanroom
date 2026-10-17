# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:58:26Z
# CHANGE: Reject empty path strings before any host filesystem operation with the exact 'Path cannot be empty' diagnostic on every construction operation, per the grounding specification
# CODE_HASH: 6fcba1cb9d25
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, system
from . import file_paths

# Requirements specified in file_paths_impl.pyi

_EMPTY_PATH_MESSAGE = "Path cannot be empty"
_NOT_ABSOLUTE_MESSAGE = "Path is not absolute: {path}"
_NOT_RELATIVE_MESSAGE = "Workspace path must be relative, got absolute: {path}"


class FilePathManager(file_paths.FilePathManager, Singleton):
    """Realizes path validation and resolution using host filesystem operations."""

    tier = system

    def __init__(self) -> None:
        pass

    def create_host_path(self, path: file_paths.PathString) -> file_paths.HostPath:
        # Contract: WHEN the supplied path string is empty, MUST raise PathValidationError("Path cannot be empty").
        if not path:
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(_EMPTY_PATH_MESSAGE)
            )
        # Contract: MUST encapsulate the supplied path string in the produced host path.
        return file_paths.HostPath(path=file_paths.PathString(path))

    def create_absolute_path(self, path: file_paths.PathString) -> file_paths.AbsolutePath:
        # Contract: WHEN the supplied path string is empty, MUST raise PathValidationError("Path cannot be empty").
        if not path:
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(_EMPTY_PATH_MESSAGE)
            )
        # Contract: WHEN the supplied path string is not absolute, MUST raise PathValidationError("Path is not absolute: {path}").
        if not os.path.isabs(path):
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(
                    _NOT_ABSOLUTE_MESSAGE.format(path=path)
                )
            )
        # Contract: MUST encapsulate normalized absolute path in AbsolutePath record.
        return file_paths.AbsolutePath(
            path=file_paths.PathString(os.path.normpath(path))
        )

    def create_workspace_path(
        self, path: file_paths.PathString
    ) -> file_paths.WorkspacePath:
        # Contract: WHEN the supplied path string is empty, MUST raise PathValidationError("Path cannot be empty").
        if not path:
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(_EMPTY_PATH_MESSAGE)
            )
        # Contract: WHEN the supplied path string has leading path separators, MUST raise PathValidationError("Workspace path must be relative, got absolute: {path}").
        if path.startswith(("/", "\\")):
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(
                    _NOT_RELATIVE_MESSAGE.format(path=path)
                )
            )
        # Contract: WHEN the supplied path string is an absolute path string, MUST raise PathValidationError.
        if os.path.isabs(path):
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(
                    _NOT_RELATIVE_MESSAGE.format(path=path)
                )
            )
        # Contract: MUST encapsulate normalized relative workspace path in WorkspacePath record.
        return file_paths.WorkspacePath(
            path=file_paths.PathString(os.path.normpath(path))
        )

    def resolve_path(
        self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath
    ) -> file_paths.AbsolutePath:
        # Contract: MUST produce combined absolute path formed by joining workspace root with relative workspace path.
        combined = os.path.join(root.path, relative.path)
        return file_paths.AbsolutePath(
            path=file_paths.PathString(os.path.normpath(combined))
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        FilePathManager,
        keys=[FilePathManager, file_paths.FilePathManager],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
