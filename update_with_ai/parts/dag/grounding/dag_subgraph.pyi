from framework import operation, singleton_type
from typing import List, Protocol, Sequence
import dag_storage


@singleton_type("system")
class DagSubgraph(Protocol):
    """Models an active execution subgraph rooted at a target node in dag storage."""

    @operation
    def set_target(self, root: dag_storage.DagNode) -> None:
        """Sets the target node, collecting reachable nodes and computing dependency-first topological order.

        Args:
            root: Root target node in dag storage.

        REQUIREMENTS:
        - Setting a target collects all reachable dependency nodes from the target node in dag storage and computes their dependency-first topological order.

        GROUNDING_PROVISIONS:
        - action("set_target", dag_storage.DagNode): Sets active target subgraph to satisfy requirement 1.
        """
        ...

    @property
    def is_complete(self) -> bool:
        """Reports whether all reachable nodes in the target subgraph are clean.

        REQUIREMENTS:
        - The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.

        GROUNDING_PROVISIONS:
        - knows("subgraph_complete", bool): Reports whether target subgraph is complete to satisfy requirement 2.
        """
        ...

    @operation
    def next_ready_batch(self) -> List[dag_storage.DagNode]:
        """Provides the next batch of ready dirty nodes to clean.

        REQUIREMENTS:
        - When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.

        GROUNDING_PROVISIONS:
        - action("next_ready_batch", List[dag_storage.DagNode]): Provides next ready batch of dirty nodes to satisfy requirement 3.
        """
        ...

    @operation
    def record_visit(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Records an execution visit for a batch of nodes being cleaned, enforcing iteration limits.

        Args:
            nodes: The batch of nodes visited.

        REQUIREMENTS:
        - Recording a visit increments the visit count for each node in the batch and raises an unexpected failure if visiting any node exceeds the node visit limit.

        GROUNDING_PROVISIONS:
        - action("record_visit", Sequence[dag_storage.DagNode]): Increments visit counts and enforces limit to satisfy requirement 4.
        """
        ...
