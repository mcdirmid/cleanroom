# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T03:19:47Z
# CHANGE: Align loop cleaner acyclic caller guarantee, halt, and conclusion contracts
# CODE_HASH: c7bc8c8c4d92
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

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
            True if all nodes in the subgraph rooted at the target node are clean, or False if processing halted.

        PRECONDITIONS:
        - A caller guarantees that the target node roots an acyclic subgraph.

        POSTCONDITIONS:
        - MUST clean dirty nodes in dependency-first topological order.
        - MUST ensure all dependencies of a node are clean before that node is cleaned.
        - WHEN the supplied node cleaner communicates that processing cannot continue, MUST halt.
        - WHEN all nodes in the subgraph rooted at the target node are clean, MUST return true.
        """
        ...
