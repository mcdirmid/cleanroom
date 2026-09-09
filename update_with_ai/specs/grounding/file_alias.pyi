from typing import Protocol, Type
from framework import data_type, operation, override, singleton_type, variant
from dataclasses import dataclass
import dag_storage
import tool_provider

@dataclass(frozen=True)
@data_type
class HostPath:
    """
PURPOSE:
Introduces a host path to represent a path on the local filesystem
"""

    def __init__(self, path: str) -> None:
        ...

    @property
    def path(self) -> str:
        """
PURPOSE:
Path string on the filesystem
"""
        ...

@dataclass(frozen=True)
@variant
class AbsolutePath(HostPath):
    """
PURPOSE:
Classifies absolute path as a host path on the local filesystem
"""

    def __init__(self, path: str) -> None:
        ...

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
Path string on the filesystem
"""
        ...

@dataclass(frozen=True)
@variant
class WorkspacePath(HostPath):
    """
PURPOSE:
Classifies workspace path as a host path that is relative to the root of the workspace
"""

    def __init__(self, path: str) -> None:
        ...

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
Path string on the filesystem
"""
        ...

@dataclass(frozen=True)
@data_type
class DirectoryPath(AbsolutePath):
    """
PURPOSE:
Established as a host path designating a directory, acting as an absolute path on the local filesystem
"""

    def __init__(self, path: str) -> None:
        ...

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
Path string on the filesystem
"""
        ...

@dataclass(frozen=True)
@data_type
class WorkspaceRoot(DirectoryPath):
    """
PURPOSE:
Introduces workspace root as a directory path such that concatenating it with a workspace path produces an absolute path
"""

    def __init__(self, path: str) -> None:
        ...

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
Path string on the filesystem
"""
        ...

@data_type
class FileContent(str):
    """
PURPOSE:
Introduces file content to represent data read from or stored in a file
"""
    ...

@data_type
class RegexPattern(str):
    """
PURPOSE:
Introduces regex pattern as the pattern used to search in files
"""
    ...

@singleton_type('agent_session')
class AliasManager(tool_provider.ParameterConverter, Protocol):
    """
PURPOSE:
Defined as an agent session service configured with a workspace root that sanitizes output text

INHERITANCE:
- tool_provider.ParameterConverter: Established that the alias manager is a parameter converter for file aliases, allowing file aliases to be used as tool parameters
"""

    @property
    def workspace_root(self) -> DirectoryPath:
        """
PURPOSE:
Established that the alias manager is configured with a workspace root
"""
        ...

    @property
    @override
    def actual_type(self) -> Type:
        """
PURPOSE:
Sets the converter actual type for the alias manager to file alias
"""
        ...

    @property
    @override
    def wire_type(self) -> tool_provider.WireType:
        """
PURPOSE:
Sets the converter wire type for the alias manager to string
"""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> FileAlias:
        """
PURPOSE:
Converts a wire type string to a file alias, producing an unbound file if the short name is not found

FRESH_REQUIREMENTS:
- Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.
"""
        ...

    @operation
    def sanitize_text(self, text: str) -> str:
        """
PURPOSE:
Provides that the alias manager sanitizes text by masking occurrences of host paths with short names

FRESH_REQUIREMENTS:
- Sanitizing text masks occurrences of host paths with the corresponding file alias short names.
"""
        ...

@dataclass(frozen=True)
@data_type
class FileAlias:
    """
PURPOSE:
Defined to represent a session file, hiding physical filesystem details and paths from the agent

FRESH_ASSUMPTIONS:
- The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

FRESH_REQUIREMENTS:
- A file alias displays itself by its short name when converted to a string.
"""

    def __init__(self, short_name: str) -> None:
        ...

    @property
    def short_name(self) -> str:
        """
PURPOSE:
Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class BoundFile(FileAlias):
    """
PURPOSE:
Classifies bound file as a file alias mapped to an actual workspace file

INHERITED_ASSUMPTIONS:
- [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its short name when converted to a string.
"""

    def __init__(self, short_name: str, workspace_path: WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    def workspace_path(self) -> WorkspacePath:
        """
PURPOSE:
Established that each bound file has a workspace path
"""
        ...

    @property
    def owning_node(self) -> dag_storage.Node:
        """
PURPOSE:
Established that each bound file has an owning node
"""
        ...

    @property
    @override
    def short_name(self) -> str:
        """
PURPOSE:
Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class ReadOnlyFile(BoundFile):
    """
PURPOSE:
Classifies read-only file as a bound file restricted to inspection

INHERITED_ASSUMPTIONS:
- [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its short name when converted to a string.
"""

    def __init__(self, short_name: str, workspace_path: WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    @override
    def workspace_path(self) -> WorkspacePath:
        """
PURPOSE:
Established that each bound file has a workspace path
"""
        ...

    @property
    @override
    def owning_node(self) -> dag_storage.Node:
        """
PURPOSE:
Established that each bound file has an owning node
"""
        ...

    @property
    @override
    def short_name(self) -> str:
        """
PURPOSE:
Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class ReadWriteFile(BoundFile):
    """
PURPOSE:
Classifies read-write file as a bound file permitted for inspection and modification

INHERITED_ASSUMPTIONS:
- [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its short name when converted to a string.
"""

    def __init__(self, short_name: str, workspace_path: WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    @override
    def workspace_path(self) -> WorkspacePath:
        """
PURPOSE:
Established that each bound file has a workspace path
"""
        ...

    @property
    @override
    def owning_node(self) -> dag_storage.Node:
        """
PURPOSE:
Established that each bound file has an owning node
"""
        ...

    @property
    @override
    def short_name(self) -> str:
        """
PURPOSE:
Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class UnboundFile(FileAlias):
    """
PURPOSE:
Classifies unbound file as a file alias that is not mapped to an actual file

INHERITED_ASSUMPTIONS:
- [FileAlias] The short name of a file alias is assumed to be a minimal unambiguous relative path identifying the file within an agent session.

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its short name when converted to a string.
"""

    def __init__(self, short_name: str) -> None:
        ...

    @property
    @override
    def short_name(self) -> str:
        """
PURPOSE:
Established that each file alias has a short name that is a minimal unambiguous relative path identifying the file within an agent session
"""
        ...
