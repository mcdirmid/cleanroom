from framework import operation, override, singleton_type
import loop_cleaner
import loop_node_cleaner
import dag_storage
import dag_subgraph

@singleton_type('system')
class LoopCleaner(loop_cleaner.LoopCleaner):
    """
PURPOSE:
Implements loop cleaner to coordinate topological graph cleaning across a dag storage

GROUNDING_ARGUMENT:
- As a system singleton, LoopCleaner coordinates topological traversal and node cleaning passes, interacting with imported dag_storage and dag_subgraph in the same system lifecycle tier and the polymorphic loop_node_cleaner.NodeCleaner.
"""

    @operation
    @override
    def clean(self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner) -> None:
        """
PURPOSE:
Implements clean to execute dirty nodes in topological order using dag subgraph

INHERITED_ASSUMPTIONS:
- [LoopCleaner] It is assumed that the node roots an acyclic subgraph.

FRESH_REQUIREMENTS:
- Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.
- Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.
- Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.

INHERITED_REQUIREMENTS:
- [LoopCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
- [LoopCleaner] Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
- [LoopCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.

GROUNDING_ARGUMENT:
- Receives node and cleaner as parameters, sets target on imported dag_subgraph.DagSubgraph in the same system lifecycle tier, records visits on dag_subgraph, and invokes cleaner.clean on ready dirty batches until dag_subgraph is complete or processing halts.
"""
        ...
