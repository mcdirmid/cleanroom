# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: 487cc8aca5f3
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
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
    - Traverses active execution subgraphs by setting target nodes on DagSubgraph,
      processing topological ready batches through NodeCleaner, and enforcing visit bounds.
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
        - Grounded via DagSubgraph to compute topological ordering and deliver ready batches,
          delegating batch workloads to NodeCleaner.clean, recording visits, and halting
          on cleaner failure or concluding upon subgraph completion.

        POSTCONDITIONS:
        - MUST set target node on dag subgraph to determine dependency-first topological order.
        - MUST process ready batches of dirty nodes in topological order, recording visits for each cleaned batch.
        - WHEN node cleaner communicates that processing cannot continue, MUST halt immediately.
        - WHEN dag subgraph is complete, MUST return true.
        """
        ...
