"""
Interface LLS: dag
Provides DAG cleaning orchestration.
"""

from typing import List, Tuple, Protocol

from .dag_storage import NodeId
from .dag_clean_logic import CleanResult

# (success, result): (True, CleanResult) on success (a ChangeResult,
# FeedbackResult, or NoChangeResult); (False, FailureResult) on failure.
CleaningResult = Tuple[bool, CleanResult]


class Dag(Protocol):
    """Interface for DAG cleaning operations."""

    def clean_subgraph(self, target_node: NodeId) -> CleaningResult:
        """
        Clean all dirty nodes in the subgraph rooted at target_node until none remain.

        Preconditions:
        - target_node exists in the graph.
        - The graph topology, as provided through dag_storage, does not change
          during cleaning.
        - No concurrent calls (undefined behavior).
        - No node receives a message while being cleaned (undefined behavior).

        Postconditions:
        - All dirty nodes in the subgraph are cleaned.
        - Nodes that become dirty during cleaning are processed before completion.
        - Cleaning proceeds in topological order (dependencies before dependents).
        - A node is not cleaned while any dependency is dirty.
        - Re-evaluates dirtiness after each cleaning.
        - Each node's cleaning is atomic (it provides messages or signals
          failure, never both).
        - Change messages delivered to all known reverse dependencies of the node
          (as provided by dag_storage); feedback messages delivered to specified
          dependencies (within the subgraph).
        - Cleaning always terminates (guarded by a single total bound on clean
          operations).
        - Returns (True, CleanResult) on success (no messages, a ChangeResult,
          or a FeedbackResult); otherwise (False, FailureResult).
        - On failure: the offending node's messages remain unchanged; previously
          cleaned nodes retain changes; processing halts.

        Failure Handling:
        - If the graph topology contains a cycle, returns (False, FailureResult);
          state is unchanged (no messages deleted or routed).
        - If feedback targets a node outside the subgraph, returns
          (False, FailureResult); the offending node's messages remain unchanged
          and processing halts.

        HLS Justification: "The client may request cleaning of a subgraph rooted at a target node."
        """
        ...
