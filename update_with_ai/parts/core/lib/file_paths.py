# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:18:03Z
# CHANGE: Align with file_paths.pyi specification
# CODE_HASH: b71ef9f4ff41
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol
from dataclasses import dataclass

# Requirements specified in file_paths.pyi

PathString = NewType('PathString', str)

ValidationMessage = NewType('ValidationMessage', str)

@dataclass(frozen=True)
class HostPath:
    # TODO_HostPath_body
    path: PathString


@dataclass(frozen=True)
class AbsolutePath(HostPath):
    # TODO_AbsolutePath_body
    pass


@dataclass(frozen=True)
class WorkspacePath(HostPath):
    # TODO_WorkspacePath_body
    pass


@dataclass(frozen=True)
class WorkspaceRoot(AbsolutePath):
    # TODO_WorkspaceRoot_body
    pass


@dataclass(frozen=True)
class PathValidationError(ValueError):
    # TODO_PathValidationError_body
    message: ValidationMessage


class FilePathManager(Protocol):
    def create_host_path(self, path: PathString) -> HostPath:
        # TODO_create_host_path_body
        ...

    def create_absolute_path(self, path: PathString) -> AbsolutePath:
        # TODO_create_absolute_path_body
        ...

    def create_workspace_path(self, path: PathString) -> WorkspacePath:
        # TODO_create_workspace_path_body
        ...

    def resolve_path(self, root: AbsolutePath, relative: WorkspacePath) -> AbsolutePath:
        # TODO_resolve_path_body
        ...
