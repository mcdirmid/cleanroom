from framework import data_type, operation, override, singleton_type
from typing import Protocol
from dataclasses import dataclass
import dag_storage
import file_paths


@dataclass(frozen=True, init=False)
@data_type
class NodeDirectory(file_paths.WorkspacePath):
    """Filesystem path addressing the workspace package directory of a node."""

    @property
    @override
    def path(self) -> str:
        """The string representing the filesystem path."""
        ...


@singleton_type('system')
class BazelTarget(Protocol):
    """System service normalizing Bazel identifiers and directories."""

    @operation
    def normalize(self, raw_label: str) -> dag_storage.DagNode:
        """Normalizes an arbitrary Bazel target string into a canonical node.

        REQUIREMENTS:
        - The bazel target normalizes an arbitrary Bazel target identifier string into a canonical node.

        GROUNDING_PROVISIONS:
        - action("normalize", dag_storage.DagNode): Normalizes target label to canonical node.
        """
        ...

    @operation
    def extract_directory(self, node: dag_storage.DagNode) -> NodeDirectory:
        """Resolves the package directory of a node.

        REQUIREMENTS:
        - The bazel target extracts a node directory from a node.

        GROUNDING_PROVISIONS:
        - action("extract_directory", NodeDirectory): Extracts package directory.
        """
        ...
