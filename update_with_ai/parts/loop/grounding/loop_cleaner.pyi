from framework import operation, singleton_type
from typing import Protocol
import loop_node_cleaner
import dag_storage

@singleton_type('system')
class LoopCleaner(Protocol):
    """
PURPOSE:
Defined as a system service that coordinates topological graph cleaning across a dag storage
"""

    @operation
    def clean(self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner) -> None:
        """
PURPOSE:
Provides that a loop cleaner can clean a target node accepting a node cleaner

FRESH_ASSUMPTIONS:
- It is assumed that the node roots an acyclic subgraph.

FRESH_REQUIREMENTS:
- Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
- Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
- Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
"""
        ...
