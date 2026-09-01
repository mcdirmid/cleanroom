"""Bazel-specific node ID utilities protocol."""

from typing import Protocol
from .node_id_utils import (
    NodeIdUtils,
    NodeDirectory,
    RawIdentifier,
    ContextIdentifier,
    WorkspaceRootPath,
)
from .dag_storage import NodeId


class BazelNodeIdUtils(NodeIdUtils, Protocol):
    """Bazel-specialized node ID utility protocol."""

    def canonicalize_node_id(
        self, raw_id: RawIdentifier, current_context: ContextIdentifier
    ) -> NodeId:
        """Normalizes a raw Bazel target label into a canonical NodeId."""
        ...

    def extract_node_directory(
        self, node: NodeId, workspace_root: WorkspaceRootPath
    ) -> NodeDirectory:
        """Resolves the workspace package directory path for a Bazel node."""
        ...
