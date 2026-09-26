from dataclasses import dataclass
from typing import Protocol, Type
from framework import data_type, operation, override, singleton_type, variant
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import dag_storage
import file_paths
import tool_provider


@data_type
class FileContent(str):
    """Represents data read from or stored in a file."""
    ...


@data_type
class RegexPattern(str):
    """Represents a pattern used to search in files."""
    ...


@dataclass(frozen=True, init=False)
@data_type
class FileAlias:
    """Represents a session file, hiding physical filesystem details and paths from the agent.

    Args:
        relative_path: The relative path identifying the file within an agent session.

    REQUIREMENTS:
    - MUST display itself by its relative path when converted to a string.
    """
    relative_path: str = ...


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
    """A bound file restricted to read."""
    ...


@dataclass(frozen=True)
@variant
class ReadWriteFile(BoundFile):
    """A bound file permitted for read and write."""
    ...


@dataclass(frozen=True)
@variant
class UnboundFile(FileAlias):
    """A file alias that is not mapped to an actual file."""
    ...


@singleton_type("agent_session")
class AliasManager(tool_provider.ParameterType[FileAlias, tool_provider.WireString], InTier[AgentSessionTier], Protocol):
    """Configured with a workspace root, sanitizes text and converts string parameters to file aliases."""

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        """The workspace root directory for the agent session.

        GROUNDING_PROVISIONS:
        - knows("workspace_root", file_paths.WorkspaceRoot): Exposes workspace root absolute path to satisfy requirement 2.
        """
        ...

    @property
    @override
    def actual_type(self) -> Type[FileAlias]:
        ...

    @property
    @override
    def wire_type(self) -> Type[tool_provider.WireString]:
        ...

    @operation
    @override
    def convert(self, wire_value: tool_provider.WireString) -> FileAlias:
        """Converts a wire type string to a file alias.

        Args:
            wire_value: The wire string to convert into a file alias.

        Returns:
            The resolved FileAlias (BoundFile if matched, UnboundFile otherwise).

        REQUIREMENTS:
        - WHEN relative path matches a declared bound file, MUST return the matching read-only or read-write file.
        - WHEN relative path does not match a declared bound file, MUST return an unbound file.

        GROUNDING_PROVISIONS:
        - action("convert", tool_provider.WireString): Converts wire type string to file alias to satisfy requirements 3, 4, and 5.
        """
        ...

    @operation
    def sanitize_text(self, text: str) -> str:
        """Sanitizes text by masking occurrences of relative workspace paths.

        Args:
            text: The input text containing potential workspace paths.

        Returns:
            The sanitized text with workspace paths masked by relative alias paths.

        REQUIREMENTS:
        - MUST mask occurrences of relative workspace paths and preceding path prefixes with file alias relative paths.

        GROUNDING_PROVISIONS:
        - action("sanitize", str): Sanitizes text by masking workspace paths with file aliases to satisfy requirement 6.
        """
        ...
