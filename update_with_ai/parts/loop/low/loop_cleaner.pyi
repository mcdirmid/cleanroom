"""Loop cleaner low-level interface specification."""

from typing import Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import loop_node_cleaner


@singleton_type("system")
class LoopCleaner(InTier[SystemTier], Protocol):
    """Coordinates topological graph cleaning across graph storage."""

    @operation
    def clean(
        self, target: dag_storage.DagNode, node_cleaner: loop_node_cleaner.NodeCleaner
    ) -> bool:
        """Cleans dirty nodes rooted at the target node in dependency-first topological order.

        Args:
            target: The root target node to clean.
            node_cleaner: The node cleaner service executing single-node workloads.

        Returns:
            True if all nodes in the target subgraph are clean, or False if processing halted.

        POSTCONDITIONS:
        - MUST clean dirty nodes in dependency-first topological order.
        - MUST ensure all dependencies of a node are clean before that node is cleaned.
        - WHEN the node cleaner communicates that processing cannot continue, MUST halt.
        - WHEN all nodes in the target subgraph are clean, MUST return true.
        """
        ...
