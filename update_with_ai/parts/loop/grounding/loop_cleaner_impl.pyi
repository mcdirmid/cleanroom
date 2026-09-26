from typing import Self
from framework import operation, override, singleton_type
import loop_cleaner
import loop_node_cleaner
import dag_storage
import dag_subgraph


@singleton_type('system')
class LoopCleaner(loop_cleaner.LoopCleaner):
    """Implements loop cleaner to coordinate topological graph cleaning across a dag storage.

    GROUNDING_ARGUMENT:
    - As a system singleton, LoopCleaner coordinates topological traversal and node cleaning passes, interacting with imported dag_storage and dag_subgraph in the same system lifecycle tier and the polymorphic loop_node_cleaner.NodeCleaner.
    """

    @operation
    @override
    def clean(self, node: dag_storage.DagNode, cleaner: loop_node_cleaner.NodeCleaner) -> None:
        """Implements clean to execute dirty nodes in topological order using dag subgraph.

        REQUIREMENTS:
        - Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.
        - Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.
        - Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.

        GROUNDING_PROVISIONS:
        - action("clean", None): Cleans dirty nodes in topological order.

        GROUNDING_ARGUMENT:
        - action("clean", Self) :- action("set_target", dag_subgraph.DagSubgraph), action("next_ready_batch", dag_subgraph.DagSubgraph), action("record_visit", dag_subgraph.DagSubgraph), action("clean", loop_node_cleaner.NodeCleaner), knows("subgraph_complete", dag_subgraph.DagSubgraph).
        """
        ...
