# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: c54027ae5195
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

# Requirements specified in file_paths_impl.pyi
import os
from typing import Optional
from . import file_paths
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)


class FilePathManager(file_paths.FilePathManager, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def create_host_path(self, path: file_paths.PathString) -> file_paths.HostPath:
        return file_paths.HostPath(path=path)

    def create_absolute_path(
        self, path: file_paths.PathString
    ) -> file_paths.AbsolutePath:
        if not os.path.isabs(path):
            raise file_paths.PathValidationError(
                file_paths.ValidationMessage(f"Path is not absolute: {path}")
            )
        return file_paths.AbsolutePath(file_paths.PathString(os.path.normpath(path)))

    def create_workspace_path(
        self, path: file_paths.PathString
    ) -> file_paths.WorkspacePath:
        if os.path.isabs(path) or path.startswith("/") or path.startswith("\\"):
            raise file_paths.PathValidationError(
                file_paths.ValidationMessage(
                    f"Workspace path must be relative, got absolute: {path}"
                )
            )
        return file_paths.WorkspacePath(file_paths.PathString(os.path.normpath(path)))

    def resolve_path(
        self, root: file_paths.AbsolutePath, relative: file_paths.WorkspacePath
    ) -> file_paths.AbsolutePath:
        joined = os.path.join(root.path, relative.path)
        return file_paths.AbsolutePath(file_paths.PathString(os.path.normpath(joined)))


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        FilePathManager,
        keys=[FilePathManager, file_paths.FilePathManager],
        tier=system,
    )
