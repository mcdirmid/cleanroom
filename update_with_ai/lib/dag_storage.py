"""
Interface LLS: dag_storage
Provides atomic message persistence and graph access for DAG nodes.
"""

from typing import List, Protocol

NodeId = str
NodeMessage = str
PendingMessages = List[NodeMessage]
NodeDependencies = List[NodeId]
KnownReverseDependencies = List[NodeId]


class DagStorage(Protocol):
    """Interface for DAG message storage and graph access operations."""

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        """
        Retrieve all pending messages for a given node.

        Preconditions: node_id must exist in the graph.
        Postconditions: Returns list of pending messages (empty if none).
        Failure Handling: If node_id does not exist, behavior is undefined.
        HLS Justification: "The client may read pending messages for a node."
        """
        ...

    def add_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        """
        Add messages to a node's pending set.

        Preconditions: node_id must exist in the graph; messages must be valid strings.
        Postconditions: All messages are added atomically to the node's pending set.
        Failure Handling: If node_id does not exist, behavior is undefined.
                         Storage failures are not handled.
        HLS Justification: "The client may add messages to a node's pending set."
        """
        ...

    def delete_node_data(self, node_id: NodeId) -> None:
        """
        Delete a node's data: its pending messages and its known reverse dependencies.

        Preconditions: node_id must exist in the graph.
        Postconditions: The node's pending messages and known reverse
                       dependencies are deleted atomically.
        Failure Handling: If node_id does not exist, behavior is undefined.
                         Storage failures are not handled.
        HLS Justification: "The client may delete a node's data (its pending messages and its known reverse dependencies)."
        """
        ...

    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies:
        """
        Retrieve the direct dependencies of a node.

        Preconditions: node_id must exist in the graph.
        Postconditions: Returns the node's direct dependencies. Records the node
                       as a known reverse dependency of each propagating
                       dependency it provides (each propagating dependency's
                       known reverse dependencies gain the node; dependencies
                       whose changes do not propagate to the node are not
                       recorded).
        Failure Handling: If node_id does not exist, behavior is undefined.
        HLS Justification: "The client may retrieve a node's dependencies."
        """
        ...

    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies:
        """
        Retrieve the nodes recorded as depending on this node.

        Preconditions: node_id must exist in the graph.
        Postconditions: Returns the node's known reverse dependencies exactly as
                       recorded (empty if none recorded).
        Failure Handling: If node_id does not exist, behavior is undefined.
        HLS Justification: "The client may retrieve a node's known reverse dependencies."
        """
        ...
