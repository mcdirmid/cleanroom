# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: c3337f9edbc0
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Dag subgraph implementation specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from dag_storage import DagNode
import dag_subgraph
import dag_config


@singleton_type("system")
class DagSubgraph(dag_subgraph.DagSubgraph, InTier[SystemTier]):
    """Coordinates topological subgraph queries and visit bounds across graph storage.

    GROUNDING:
    - Queries active execution subgraphs rooted at a target node, sorting nodes into
      dependency-first topological order, scheduling batches of uncleaned dirty nodes
      by role precedence, and bounding visitation limits via DagConfig and DagStorage.
    """

    @operation
    @override
    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node.

        Args:
            target: The target node rooting the active execution subgraph.

        GROUNDING:
        - Grounded via DagStorage.dependencies graph walk collecting reachable nodes,
          topological sorting breaking ties by role tier depth and unit address.

        POSTCONDITIONS:
        - MUST break topological sorting ties by role tier depth first.
        - MUST break remaining topological sorting ties by unit address.
        """
        ...

    @operation
    @override
    def is_complete(self) -> bool:
        """Reports whether all nodes in the target subgraph are clean.

        GROUNDING:
        - Grounded via DagStorage.is_dirty checks across all reachable subgraph nodes.
        """
        ...

    @operation
    @override
    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean.

        Returns:
            The sequence of dirty nodes ready to be cleaned.

        GROUNDING:
        - Grounded via selecting earliest contiguous ready dirty nodes of identical role
          prioritized by dynamic role tier precedence up to DagConfig.batch_size.

        POSTCONDITIONS:
        - MUST select dirty nodes that are contiguous in topological order.
        - MUST dynamically prioritize upstream roles before downstream roles based on role dependency depth in the graph.
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

        GROUNDING:
        - Grounded via incrementing in-memory visit counters and comparing against
          DagConfig.node_visit_limit, raising an unexpected failure on overflow.

        POSTCONDITIONS:
        - MUST advance the visit count for each node in the batch.
        - WHEN any node in the batch exceeds the node visit limit obtained from configuration, MUST raise an unexpected failure.
        """
        ...
