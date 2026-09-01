"""Node ID utility protocols and types."""

from typing import Protocol, TypeAlias
from .dag_storage import NodeId

NodeDirectory: TypeAlias = str
RawIdentifier: TypeAlias = str
ContextIdentifier: TypeAlias = str
WorkspaceRootPath: TypeAlias = str


class NodeIdUtils(Protocol):
    """Protocol for canonicalizing node IDs and resolving package directories."""

    def canonicalize_node_id(
        self, raw_id: RawIdentifier, current_context: ContextIdentifier
    ) -> NodeId:
        """Normalizes an arbitrary string identifier into a canonical NodeId."""
        ...

    def extract_node_directory(
        self, node: NodeId, workspace_root: WorkspaceRootPath
    ) -> NodeDirectory:
        """Extracts the package directory path holding the node."""
        ...
