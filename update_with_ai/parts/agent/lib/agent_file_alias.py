# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:25Z
# CHANGE: Realize the orphan postcondition that a file alias displays itself by its relative path, and drop the dead tier import and scaffold markers
# CODE_HASH: b6d1964c53b4
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol, Type
from dataclasses import dataclass
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
import update_with_ai.parts.core.lib.file_paths as file_paths

# Requirements specified in agent_file_alias.pyi

FileContent = NewType('FileContent', str)

RegexPattern = NewType('RegexPattern', str)

RelativePath = NewType('RelativePath', str)

UnsanitizedText = NewType('UnsanitizedText', str)

SanitizedText = NewType('SanitizedText', str)

@dataclass(frozen=True)
class FileAlias:
    relative_path: RelativePath

    # Contract: MUST display itself by its relative path when converted to a string.
    def __str__(self) -> str:
        """Displays the file alias by its relative path in the agent session."""
        return str(self.relative_path)


@dataclass(frozen=True)
class BoundFile(FileAlias):
    workspace_path: file_paths.WorkspacePath
    owning_node: dag_storage.DagNode


@dataclass(frozen=True)
class ReadOnlyFile(BoundFile):
    pass


@dataclass(frozen=True)
class ReadWriteFile(BoundFile):
    pass


@dataclass(frozen=True)
class UnboundFile(FileAlias):
    pass


class AliasManager(Protocol):
    # Contract: The workspace root directory for the agent session.
    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        ...

    # Contract: MUST convert path strings to file aliases (BoundFile if matched, UnboundFile otherwise).
    def to_alias(self, path: str) -> FileAlias:
        ...

    # Contract: MUST sanitize text by masking occurrences of relative workspace paths with file alias relative paths.
    def sanitize_text(self, text: UnsanitizedText) -> SanitizedText:
        ...
