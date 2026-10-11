# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T03:06:36Z
# CHANGE: Add role address tie-break and unsatisfied dependency batch termination grounding
# CODE_HASH: 4a92655e8659
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""Dag subgraph implementation specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from dag_storage import DagNode
import dag_subgraph
import dag_config
import dag_storage


@singleton_type("system")
class DagSubgraph(dag_subgraph.DagSubgraph, InTier[SystemTier]):
    """Coordinates topological subgraph queries and visit bounds across graph storage.

    GROUNDING:
    - Walks DagStorage.get_dependencies from the target node to collect reachable nodes into an
      in-memory topological index, sorted in dependency-first topological order with ties broken
      by role tier depth, then unit address, then role address.
    - Selects contiguous ready dirty nodes by consulting DagStorage.is_dirty, grouped by role
      address up to DagConfig.batch_size, ending a batch before any node whose
      DagStorage.get_dependencies are neither clean nor already collected.
    - Maintains in-memory visit counters mutated for each recorded node and compared against
      DagConfig.node_visit_limit, raising an unexpected failure when the limit is exceeded.
    """

    @operation
    @override
    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node.

        Args:
            target: The target node rooting the active execution subgraph.

        GROUNDING:
        - Grounded via a DagStorage.get_dependencies graph walk that collects reachable nodes into
          the in-memory topological index, sorting that index in dependency-first topological order
          and breaking ties by role tier depth, then unit address, then role address.

        POSTCONDITIONS:
        - MUST break topological sorting ties by role tier depth first.
        - MUST break remaining topological sorting ties by unit address.
        - MUST break remaining topological sorting ties by role address.
        """
        ...

    @operation
    @override
    def is_complete(self) -> bool:
        """Reports whether all nodes in the target subgraph are clean.

        GROUNDING:
        - Grounded via DagStorage.is_dirty checks across every node retained in the in-memory
          topological index of the target subgraph.
        """
        ...

    @operation
    @override
    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean.

        Returns:
            The sequence of dirty nodes ready to be cleaned.

        GROUNDING:
        - Grounded via scanning the in-memory topological index from the earliest ready dirty node,
          reading DagStorage.is_dirty and DagStorage.get_dependencies, collecting contiguous dirty
          nodes of the same role address until a node's dependencies are neither clean nor already
          collected, bounded by DagConfig.batch_size.

        POSTCONDITIONS:
        - MUST select dirty nodes that are contiguous in topological order.
        - MUST dynamically prioritize upstream roles before downstream roles based on role dependency depth in the graph.
        - MUST start from the earliest ready dirty node in topological order.
        - WHEN a node's dependencies in the target subgraph are neither clean nor already collected into the same batch, MUST end the batch before that node.
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
        - Grounded via incrementing the in-memory visit counter of each node in the batch and
          comparing each counter against DagConfig.node_visit_limit, raising an unexpected failure
          when the limit is exceeded.

        POSTCONDITIONS:
        - MUST advance the visit count for each node in the batch.
        - WHEN any node in the batch exceeds the node visit limit obtained from configuration, MUST raise an unexpected failure.
        """
        ...
