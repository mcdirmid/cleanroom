# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-11T04:59:21Z
# CHANGE: Remove generated scaffold markers and document the declared subgraph operations with their conditional postconditions
# CODE_HASH: e7cd5665aee4
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import Protocol, Sequence

from .dag_storage import DagNode

# Requirements specified in dag_subgraph.pyi


class DagSubgraph(Protocol):
    """System service modeling an active execution subgraph rooted at a target node."""

    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node.

        Args:
            target: The target node rooting the active execution subgraph.

        POSTCONDITIONS:
        - MUST collect reachable dependency nodes from the target node in graph storage.
        - MUST compute the dependency-first topological order of reachable dependency nodes.
        - MUST order nodes that no dependency orders relative to one another by role tier depth first.
        - MUST order nodes that no dependency orders relative to one another by unit address second.
        """
        ...

    def is_complete(self) -> bool:
        """Indicates whether all reachable nodes in the target subgraph are clean.

        Returns:
            True if all reachable nodes in the target subgraph are clean.

        POSTCONDITIONS:
        - MUST return true if, but only if, all reachable nodes in the target subgraph are clean in graph storage.
        """
        ...

    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean.

        Returns:
            The sequence of dirty nodes ready to be cleaned.

        POSTCONDITIONS:
        - MUST select uncleaned dirty nodes prioritized by role tier precedence.
        - MUST ensure dependencies in the target subgraph for each selected dirty node are clean or present in the same ready batch.
        - WHEN no dirty node in the target subgraph has all of its dependencies in the target subgraph clean in graph storage, MUST return an empty sequence.
        - MUST ensure selected dirty nodes share the same role address.
        - MUST bound the batch size up to the maximum batch size.
        """
        ...

    def record_visit(self, batch: Sequence[DagNode]) -> None:
        """Records a visit for a batch of nodes being cleaned.

        Args:
            batch: The batch of nodes whose visit count is recorded.

        POSTCONDITIONS:
        - MUST increment visit counts for each node in the recorded batch.
        - MUST enforce execution iteration limits across recorded node visits.
        """
        ...
