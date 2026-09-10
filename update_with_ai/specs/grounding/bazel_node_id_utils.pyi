from framework import data_type, operation, override, singleton_type
from typing import Protocol
from dataclasses import dataclass
import dag_storage
import file_paths

@dataclass(frozen=True, init=False)
@data_type
class NodeDirectory(file_paths.WorkspacePath):
    """
PURPOSE:
Filesystem path addressing the workspace package directory of a node
"""

    @property
    @override
    def path(self) -> str:
        """
PURPOSE:
The string representing the filesystem path.
"""
        ...

@singleton_type('system')
class BazelNodeIdentifierUtility(Protocol):
    """
PURPOSE:
Defined as a system service normalizing Bazel identifiers and directories
"""

    @operation
    def normalize(self, raw_label: str) -> dag_storage.Node:
        """
PURPOSE:
Normalizes an arbitrary Bazel target string into a canonical node

FRESH_REQUIREMENTS:
- The bazel node identifier utility normalizes an arbitrary target identifier string into a canonical node.
"""
        ...

    @operation
    def extract_directory(self, node: dag_storage.Node) -> NodeDirectory:
        """
PURPOSE:
Resolves the package directory of a node

FRESH_REQUIREMENTS:
- The bazel node identifier utility extracts a node directory from a node.
"""
        ...
