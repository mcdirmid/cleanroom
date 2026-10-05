# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 2e227bdb054e
# --- END CLEANROOM METADATA ---

"""Agent file alias low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Protocol, Type
from framework import data_type, operation, override, singleton_type, variant
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import dag_storage
import file_paths
import tool_provider

FileContent = NewType("FileContent", str)
RegexPattern = NewType("RegexPattern", str)
RelativePath = NewType("RelativePath", str)
UnsanitizedText = NewType("UnsanitizedText", str)
SanitizedText = NewType("SanitizedText", str)


@dataclass(frozen=True, init=False)
@data_type
class FileAlias:
    """Represents a session file, hiding physical filesystem details and paths from the agent.

    Args:
        relative_path: The relative path identifying the file within an agent session.
    """
    relative_path: RelativePath = ...


@dataclass(frozen=True, init=False)
@variant
class BoundFile(FileAlias):
    """A file alias mapped to an actual workspace file.

    Args:
        workspace_path: The workspace path of the actual file.
        owning_node: The graph node that owns this bound file.
    """
    workspace_path: file_paths.WorkspacePath = ...
    owning_node: dag_storage.DagNode = ...


@dataclass(frozen=True)
@variant
class ReadOnlyFile(BoundFile):
    """A bound file restricted to read access."""
    ...


@dataclass(frozen=True)
@variant
class ReadWriteFile(BoundFile):
    """A bound file permitted for read and write access."""
    ...


@dataclass(frozen=True)
@variant
class UnboundFile(FileAlias):
    """A file alias that is not mapped to an actual file."""
    ...


@singleton_type("agent_session")
class AliasManager(tool_provider.ParameterType[FileAlias, str], InTier[AgentSessionTier], Protocol):
    """Configured with a workspace root, sanitizes text and converts string parameters to file aliases."""

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """The workspace root directory for the agent session."""
        ...

    @property
    @override
    def actual_type(self) -> Type[FileAlias]:
        """Data type produced by the converter."""
        ...

    @property
    @override
    def wire_type(self) -> Type[str]:
        """Primitive wire type accepted by the converter."""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> FileAlias:
        """Converts a wire type string to a file alias.

        Args:
            wire_value: The wire string to convert into a file alias.

        Returns:
            The resolved FileAlias (BoundFile if matched, UnboundFile otherwise).

        POSTCONDITIONS:
        - MUST convert wire type strings to file aliases without failure.
        - WHEN a wire string matches a declared bound file, MUST produce that read-only or read-write file.
        - WHEN a wire string does not match any declared bound file, MUST produce an unbound file.
        """
        ...

    @operation
    def sanitize_text(self, text: UnsanitizedText) -> SanitizedText:
        """Sanitizes text by masking occurrences of relative workspace paths.

        Args:
            text: The input text containing potential workspace paths.

        Returns:
            The sanitized text with workspace paths masked by relative alias paths.

        POSTCONDITIONS:
        - MUST sanitize text by masking occurrences of relative workspace paths and preceding path prefixes with file alias relative paths.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for agent file alias.

    POSTCONDITIONS:
    - MUST display itself by its relative path when converted to a string.
    """
    ...
