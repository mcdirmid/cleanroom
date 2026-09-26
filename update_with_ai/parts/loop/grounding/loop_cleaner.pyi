from framework import operation, singleton_type
from typing import Protocol
import loop_node_cleaner
import dag_storage


@singleton_type('system')
class LoopCleaner(Protocol):
    """System service that coordinates topological graph cleaning across a dag storage."""

    @operation
    def clean(self, node: dag_storage.DagNode, cleaner: loop_node_cleaner.NodeCleaner) -> None:
        """Coordinates cleaning of dirty nodes in the subgraph rooted at a target node.

        ASSUMPTIONS:
        - It is assumed that the node roots an acyclic subgraph.

        REQUIREMENTS:
        - Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
        - Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
        - Cleaning concludes when all nodes in the subgraph rooted at the node are clean.

        GROUNDING_PROVISIONS:
        - action("clean", None): Coordinates cleaning of dirty nodes in subgraph.
        """
        ...
