"""File paths service implementation."""

import os
from typing import Optional
from .file_paths import (
    FilePaths as FilePathsInterface,
    HostPath,
    AbsolutePath,
    WorkspacePath,
    DirectoryPath,
    WorkspaceRoot,
)
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry


def _make_host_path(cls, path: str):
    obj = object.__new__(cls)
    object.__setattr__(obj, "path", path)
    return obj


class FilePaths(FilePathsInterface, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def create_host_path(self, path: str) -> HostPath:
        # Requirement: [FilePaths] Returns a host path encapsulating the path string.
        if not path:
            raise ValueError("Host path cannot be empty")
        return _make_host_path(HostPath, path)

    def create_absolute_path(self, path: str) -> AbsolutePath:
        if not os.path.isabs(path):
            # Requirement: [FilePaths] If the path string is not absolute, raises a failure.
            raise ValueError(f"Path is not absolute: {path}")
        # Requirement: [FilePaths] If the path string is absolute, returns an absolute path encapsulating the path string.
        return _make_host_path(AbsolutePath, os.path.normpath(path))

    def create_workspace_path(self, path: str) -> WorkspacePath:
        if os.path.isabs(path):
            # Requirement: [FilePaths] If the path string is absolute, raises a failure.
            raise ValueError(f"Workspace path must be relative, got absolute: {path}")
        norm = os.path.normpath(path)
        # Requirement: [FilePaths] If the path string is relative, returns a workspace path encapsulating the path string.
        return _make_host_path(WorkspacePath, norm)

    def create_directory_path(self, path: str) -> DirectoryPath:
        if not os.path.isabs(path):
            # Requirement: [FilePaths] If the path string is not absolute, raises a failure.
            raise ValueError(f"Directory path must be absolute: {path}")
        # Requirement: [FilePaths] If the path string is absolute, returns a directory path encapsulating the path string.
        return _make_host_path(DirectoryPath, os.path.normpath(path))

    def get_workspace_root(self) -> WorkspaceRoot:
        # Requirement: [FilePaths] Returns a workspace root representing the physical workspace root directory.
        env_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        if env_root and os.path.isabs(env_root):
            root_path = env_root
        else:
            root_path = os.getcwd()
        return _make_host_path(WorkspaceRoot, os.path.normpath(root_path))

    def resolve_directory(
        self, root: WorkspaceRoot, relative: WorkspacePath
    ) -> DirectoryPath:
        # Requirement: [FilePaths] Returns a directory path formed by joining the workspace root and the workspace path.
        joined = os.path.join(root.path, relative.path)
        return _make_host_path(DirectoryPath, os.path.normpath(joined))

    def resolve_path(
        self, root: WorkspaceRoot, relative: WorkspacePath
    ) -> AbsolutePath:
        # Requirement: [FilePaths] Returns an absolute path formed by joining the workspace root and the workspace path.
        joined = os.path.join(root.path, relative.path)
        return _make_host_path(AbsolutePath, os.path.normpath(joined))


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        FilePaths,
        keys=[FilePaths, FilePathsInterface],
        tier="system",
    )
