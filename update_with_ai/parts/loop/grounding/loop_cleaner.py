# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 58d505b15aaf
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Loop cleaner grounding specification module."""

from __future__ import annotations
from typing import Protocol, Sequence
from support.lib.grounding_support import InTier, SystemTier
from parts.dag.grounding import dag_storage, dag_subgraph
from parts.loop.grounding import loop_node_cleaner


class LoopCleaner(InTier[SystemTier], Protocol):
    """Coordinates topological graph cleaning across graph storage."""

    def clean(
        self, target: dag_storage.DagNode, node_cleaner: loop_node_cleaner.NodeCleaner
    ) -> bool:
        """
        COVERED:
        - MUST clean dirty nodes in dependency-first topological order.
          - Condition knowledge: resolve DagSubgraph, set_target(target), obtain next_ready_batch().
          - Consequent knowledge: invoke node_cleaner.clean(batch).
        - MUST ensure all dependencies of a node are clean before that node is cleaned.
          - Condition knowledge: subgraph.next_ready_batch() yields nodes with clean dependencies.
        - WHEN the node cleaner communicates that processing cannot continue, MUST halt.
          - Condition knowledge: evaluate should_continue flag returned by node_cleaner.clean(batch).
          - Consequent knowledge: return False.
        - WHEN all nodes in the target subgraph are clean, MUST return true.
          - Condition knowledge: evaluate subgraph.is_complete().
          - Consequent knowledge: return True.

        DEFERRED:
        - Dynamic while loop and termination branches deferred to loop_cleaner_impl.py."""
        subgraph: dag_subgraph.DagSubgraph = self.get_singleton(
            dag_subgraph.DagSubgraph
        )
        subgraph.set_target(target)
        batch: Sequence[dag_storage.DagNode] = subgraph.next_ready_batch()
        _should_continue: bool = node_cleaner.clean(batch)
        subgraph.record_visit(batch)
        _complete: bool = subgraph.is_complete()
        raise NotImplementedError
