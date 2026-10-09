# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 682315c696aa
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Dag subgraph low-level interface specification."""

from typing import Protocol, Sequence
from framework import operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
from dag_storage import DagNode


@singleton_type("system")
class DagSubgraph(InTier[SystemTier], Protocol):
    """System service modeling an active execution subgraph rooted at a target node."""

    @operation
    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node.

        Args:
            target: The target node rooting the active execution subgraph.

        POSTCONDITIONS:
        - MUST collect reachable dependency nodes from the target node in graph storage.
        - MUST compute the dependency-first topological order of reachable dependency nodes.
        """
        ...

    @operation
    def is_complete(self) -> bool:
        """Indicates whether all reachable nodes in the target subgraph are clean.

        Returns:
            True if all reachable nodes in the target subgraph are clean.

        POSTCONDITIONS:
        - MUST return whether the target subgraph is complete.
        - MUST return true if, but only if, all reachable nodes in the target subgraph are clean.
        """
        ...

    @operation
    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean.

        Returns:
            The sequence of dirty nodes ready to be cleaned.

        POSTCONDITIONS:
        - MUST return the next ready batch of dirty nodes to clean.
        - MUST select uncleaned dirty nodes prioritized by role tier precedence.
        - MUST ensure dependencies in the target subgraph for each selected dirty node are clean or present in the same ready batch.
        - MUST ensure selected dirty nodes share the same role address.
        - MUST bound the batch size up to the maximum batch size.
        """
        ...

    @operation
    def record_visit(self, batch: Sequence[DagNode]) -> None:
        """Records a visit for a batch of nodes being cleaned.

        Args:
            batch: The batch of nodes whose visit count is recorded.

        POSTCONDITIONS:
        - MUST increment visit counts for each node in the recorded batch.
        - MUST enforce execution iteration limits across recorded node visits.
        """
        ...
