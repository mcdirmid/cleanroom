from typing import Protocol, Type
from framework import data_type, operation, override, singleton_type, variant
from dataclasses import dataclass
import dag_storage
import file_paths
import tool_provider

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
class AliasManager(tool_provider.ParameterType['FileAlias', str], Protocol):
    """
PURPOSE:
Defined as an agent session service configured with a workspace root that sanitizes output text

INHERITANCE:
- tool_provider.ParameterType: Established that the alias manager is a parameter type for file aliases, allowing file aliases to be used as tool parameters
"""

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
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
    def wire_type(self) -> Type[str]:
        """
PURPOSE:
Sets the converter wire type for the alias manager to string
"""
        ...

    @operation
    @override
    def convert(self, wire_value: str) -> 'FileAlias':
        """
PURPOSE:
Converts a wire type string to a file alias, producing an unbound file if the relative path is not found or is ambiguous

FRESH_REQUIREMENTS:
- Converting a wire type string produces the matching file alias if its relative path is found, or if its short name unambiguously resolves to a single declared bound file, and produces an unbound file if the relative path is not found or is ambiguous.
"""
        ...

    @operation
    def sanitize_text(self, text: str) -> str:
        """
PURPOSE:
Provides that the alias manager sanitizes text by masking occurrences of relative workspace paths and preceding path prefixes with relative paths

FRESH_REQUIREMENTS:
- Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias relative paths.
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class FileAlias:
    """
PURPOSE:
Defined to represent a session file, hiding physical filesystem details and paths from the agent

FRESH_REQUIREMENTS:
- A file alias displays itself by its relative path when converted to a string.
"""

    @property
    def relative_path(self) -> str:
        """
PURPOSE:
Established that each file alias has a relative path that identifies the file within an agent session
"""
        ...

@dataclass(frozen=True, init=False)
@variant
class BoundFile(FileAlias):
    """
PURPOSE:
Classifies bound file as a file alias mapped to an actual workspace file

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its relative path when converted to a string.
"""

    @property
    def workspace_path(self) -> file_paths.WorkspacePath:
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
    def relative_path(self) -> str:
        """
PURPOSE:
Established that each file alias has a relative path that identifies the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class ReadOnlyFile(BoundFile):
    """
PURPOSE:
Classifies read-only file as a bound file restricted to inspection

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its relative path when converted to a string.
"""

    def __init__(self, relative_path: str, workspace_path: file_paths.WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    @override
    def workspace_path(self) -> file_paths.WorkspacePath:
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
    def relative_path(self) -> str:
        """
PURPOSE:
Established that each file alias has a relative path that identifies the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class ReadWriteFile(BoundFile):
    """
PURPOSE:
Classifies read-write file as a bound file permitted for inspection and modification

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its relative path when converted to a string.
"""

    def __init__(self, relative_path: str, workspace_path: file_paths.WorkspacePath, owning_node: dag_storage.Node) -> None:
        ...

    @property
    @override
    def workspace_path(self) -> file_paths.WorkspacePath:
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
    def relative_path(self) -> str:
        """
PURPOSE:
Established that each file alias has a relative path that identifies the file within an agent session
"""
        ...

@dataclass(frozen=True)
@variant
class UnboundFile(FileAlias):
    """
PURPOSE:
Classifies unbound file as a file alias that is not mapped to an actual file

INHERITED_REQUIREMENTS:
- [FileAlias] A file alias displays itself by its relative path when converted to a string.
"""

    def __init__(self, relative_path: str) -> None:
        ...

    @property
    @override
    def relative_path(self) -> str:
        """
PURPOSE:
Established that each file alias has a relative path that identifies the file within an agent session
"""
        ...
