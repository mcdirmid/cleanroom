# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T03:02:02Z
# CHANGE: Remove unreachable post-normalization absolute-path check in create_workspace_path
# CODE_HASH: 5ec3e027f8c9
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import file_paths

# Requirements specified in file_paths_impl.pyi

class FilePathManager(file_paths.FilePathManager, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def create_host_path(self, path: file_paths.PathString) -> file_paths.HostPath:
        return file_paths.HostPath(path=file_paths.PathString(path))

    def create_absolute_path(self, path: file_paths.PathString) -> file_paths.AbsolutePath:
        if not os.path.isabs(path):
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(f"Path is not absolute: {path}")
            )
        return file_paths.AbsolutePath(path=file_paths.PathString(os.path.normpath(path)))

    def create_workspace_path(self, path: file_paths.PathString) -> file_paths.WorkspacePath:
        if os.path.isabs(path) or path.startswith("/") or path.startswith("\\"):
            raise file_paths.PathValidationError(
                message=file_paths.ValidationMessage(f"Workspace path must be relative, got absolute: {path}")
            )
        norm = os.path.normpath(path)
        return file_paths.WorkspacePath(path=file_paths.PathString(norm))

    def resolve_path(self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath) -> file_paths.AbsolutePath:
        combined = os.path.normpath(os.path.join(root.path, relative.path))
        return file_paths.AbsolutePath(path=file_paths.PathString(combined))


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        FilePathManager,
        keys=[FilePathManager, file_paths.FilePathManager],
        tier=system,
    )

_initialize_ = __initialize__
