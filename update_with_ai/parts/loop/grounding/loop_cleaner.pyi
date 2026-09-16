from framework import operation, singleton_type
from typing import Protocol
import loop_node_cleaner
import dag_storage

@singleton_type('system')
class LoopCleaner(Protocol):
    """
PURPOSE:
Defined as a system service that coordinates topological graph cleaning across a dag storage using a node cleaner
"""

    @operation
    def clean(self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner) -> None:
        """
PURPOSE:
Provides that a loop cleaner can clean a target node using a node cleaner

FRESH_ASSUMPTIONS:
- It is assumed that the node roots an acyclic subgraph.

FRESH_REQUIREMENTS:
- Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
- When cleaning a dirty node using the node cleaner, cleaning delegates to the node cleaner.
- If the node cleaner communicates that processing cannot continue, cleaning halts.
- Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
"""
        ...
