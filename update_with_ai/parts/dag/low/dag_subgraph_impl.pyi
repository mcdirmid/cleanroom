# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 0f01cb9894fd
# --- END CLEANROOM METADATA ---

"""Dag subgraph implementation specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from dag_storage import DagNode
import dag_subgraph


@singleton_type("system")
class DagSubgraph(dag_subgraph.DagSubgraph, InTier[SystemTier]):
    """Coordinates topological subgraph queries and visit bounds across graph storage."""

    @operation
    @override
    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node.

        Args:
            target: The target node rooting the active execution subgraph.

        POSTCONDITIONS:
        - MUST break topological sorting ties by role tier depth first.
        - MUST break remaining topological sorting ties by unit address.
        """
        ...

    @operation
    @override
    def is_complete(self) -> bool:
        ...

    @operation
    @override
    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean.

        Returns:
            The sequence of dirty nodes ready to be cleaned.

        POSTCONDITIONS:
        - MUST select dirty nodes that are contiguous in topological order.
        - MUST prioritize lib before test in role tier precedence.
        - MUST prioritize test before qa in role tier precedence.
        - MUST start from the earliest ready dirty node in topological order.
        - MUST bound batch size to the limit obtained from configuration.
        - WHEN no dirty node in the target subgraph has all its dependencies clean, MUST return an empty sequence.
        """
        ...

    @operation
    @override
    def record_visit(self, batch: Sequence[DagNode]) -> None:
        """Records a visit for a batch of nodes being cleaned.

        Args:
            batch: The batch of nodes whose visit count is recorded.

        POSTCONDITIONS:
        - MUST advance the visit count for each node in the batch.
        - WHEN any node in the batch exceeds the node visit limit obtained from configuration, MUST raise an unexpected failure.
        """
        ...
