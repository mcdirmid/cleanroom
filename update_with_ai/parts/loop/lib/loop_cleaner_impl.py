from typing import Optional
from . import loop_cleaner
from . import loop_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib import dag_subgraph
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class LoopCleaner(loop_cleaner.LoopCleaner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def clean(
        self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner
    ) -> None:
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        # Requirement: Target node initialization sets the target on the dag subgraph to collect reachable nodes and determine their topological order.
        subgraph.set_target(node)

        # Requirement: Cleaning loops while the dag subgraph is not complete, obtaining the next ready batch of dirty nodes from the dag subgraph, recording the visit on the dag subgraph, and delegating cleaning to the node cleaner.
        # Requirement: [LoopCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
        # Requirement: Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.
        while not subgraph.is_complete:
            # Requirement: [LoopCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
            batch = subgraph.next_ready_batch()
            if not batch:
                break
            subgraph.record_visit(batch)
            # Requirement: [LoopCleaner] When cleaning a dirty node using the node cleaner, cleaning delegates to the node cleaner.
            should_continue = cleaner.clean(batch)
            # Requirement: If the node cleaner communicates that processing cannot continue, cleaning halts immediately.
            # Requirement: [LoopCleaner] If the node cleaner communicates that processing cannot continue, cleaning halts.
            if not should_continue:
                return


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopCleaner,
        keys=[LoopCleaner, loop_cleaner.LoopCleaner],
        tier="system",
    )
