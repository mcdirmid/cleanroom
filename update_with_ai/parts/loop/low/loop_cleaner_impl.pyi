# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-11T03:21:22Z
# CHANGE: State the completion condition through dag subgraph completeness and ground traversal collaborators
# CODE_HASH: 34dd08a7b251
# SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
# --- END CLEANROOM METADATA ---

"""Loop cleaner implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import loop_cleaner
import loop_node_cleaner
import dag_subgraph


@singleton_type("system")
class LoopCleaner(loop_cleaner.LoopCleaner, InTier[SystemTier]):
    """Realizes dependency-first topological cleaning and visit recording using dag subgraph.

    GROUNDING:
    - Delegates subgraph scoping to the DagSubgraph collaborator, whose set_target computes
      the dependency-first topological order of reachable dependency nodes while holding the
      target node in its own internal backing state.
    - Drives cleaning by repeatedly requesting the next ready batch of dirty nodes from
      DagSubgraph.next_ready_batch, which consults DagStorage.is_dirty over the stored reachable
      nodes and returns candidates sharing a role address.
    - Retrieves target node addresses, role addresses, and dirty status through the DagStorage
      collaborator, reading the node graph structure and clean status stored for each node.
    - Submits each dirty batch to NodeCleaner.clean, whose outcome is interpreted as the
      collaborator's communication of whether processing can continue.
    - Records the submitted batch for each cleaned batch through DagSubgraph.record_visit, which
      maintains visit counts in its internal backing state and enforces execution iteration
      limits across those counts.
    - Determines conclusion only from DagSubgraph.is_complete, which reports the target subgraph
      complete exactly when the DagStorage clean status of every reachable node in the target
      subgraph is clean, rather than from batch selection alone.
    """

    @operation
    @override
    def clean(
        self, target: dag_storage.DagNode, node_cleaner: loop_node_cleaner.NodeCleaner
    ) -> bool:
        """Cleans dirty nodes in topological ready batches.

        Args:
            target: The root target node to clean.
            node_cleaner: The node cleaner service executing single-node workloads.

        Returns:
            True if all nodes in the target subgraph are clean, or False if processing halted.

        GROUNDING:
        - Scopes the run by handing target to DagSubgraph.set_target, which collects the reachable
          dependency nodes and fixes the dependency-first topological order before any batch is
          requested.
        - Pulls the next dirty batch by calling DagSubgraph.next_ready_batch in a loop that
          proceeds in the topological order fixed by set_target rather than rescanning storage.
        - Hands each returned dirty batch to node_cleaner.clean, letting NodeCleaner.clean perform
          the single-node workloads that clear the DagStorage dirty status of those nodes.
        - Records each submitted batch with DagSubgraph.record_visit before advancing, so visit
          counts stored by the DagSubgraph collaborator bound repeated cleaning of the same nodes.
        - Stops the loop as soon as node_cleaner.clean signals that processing cannot continue, and
          otherwise stops when DagSubgraph.is_complete reports the target subgraph complete.
        - Reports true only for a run concluded through the DagSubgraph.is_complete report that
          every reachable node in the target subgraph is clean in dag storage.

        POSTCONDITIONS:
        - MUST set the target node on dag subgraph to determine dependency-first topological order.
        - MUST process ready batches of dirty nodes in topological order.
        - MUST record node visits for each cleaned batch.
        - WHEN node cleaner communicates that processing cannot continue, MUST halt immediately.
        - WHEN the dag subgraph reports that the target subgraph is complete, MUST return true,
          meaning every reachable node in the target subgraph is clean in dag storage.
        """
        ...
