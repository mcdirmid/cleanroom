"""
Interface LLS: dag_storage

The DAG storage interface defines the contract for storing and retrieving
node messages, dependencies, and reverse dependencies in a DAG-based
dependency graph used for incremental computation.
"""

from __future__ import annotations

from typing import Protocol, TypeAlias, Literal
from dataclasses import dataclass


NodeId: TypeAlias = str

MessageKind: TypeAlias = Literal["change", "feedback"]


@dataclass
class NodeMessage:
    kind: MessageKind
    text: str


PendingMessages: TypeAlias = list[NodeMessage]

NodeDependencies: TypeAlias = list[NodeId]

KnownReverseDependencies: TypeAlias = list[NodeId]


class DagStorage(Protocol):
    """DAG storage protocol for node messages and dependency tracking."""

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        """Retrieve all pending messages for a given node.

        Preconditions: node_id must exist in the graph.
        Postconditions: Provides list of pending messages (empty if none).
        """
        ...

    def add_messages(self, node_id: NodeId, messages: list[NodeMessage]) -> None:
        """Add messages to a node's pending set.

        Preconditions: node_id must exist in the graph; messages must be valid.
        Postconditions: All messages are added atomically to the node's pending set.
        """
        ...

    def clear_pending_messages(self, node_id: NodeId) -> None:
        """Clear a node's pending messages, leaving its known reverse dependencies.

        Preconditions: node_id must exist in the graph.
        Postconditions: The node's pending messages are removed atomically;
        known reverse dependencies remain.
        """
        ...

    def delete_node_data(self, node_id: NodeId) -> None:
        """Delete a node's data: pending messages and known reverse dependencies.

        Preconditions: node_id must exist in the graph.
        Postconditions: Pending messages and known reverse dependencies are
        deleted atomically.
        """
        ...

    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies:
        """Retrieve the direct dependencies of a node.

        Preconditions: node_id must exist in the graph.
        Postconditions: Provides the node's direct dependencies. Records the
        node as a known reverse dependency of each propagating dependency,
        at most once per dependency. Dependencies whose changes do not
        propagate are not recorded.
        """
        ...

    def get_known_reverse_dependencies(
        self, node_id: NodeId
    ) -> KnownReverseDependencies:
        """Retrieve the nodes recorded as depending on this node.

        Preconditions: node_id must exist in the graph.
        Postconditions: Provides the node's known reverse dependencies exactly
        as recorded (empty if none recorded).
        """
        ...


