# Requirements specified in loop_cleaner_impl.pyi
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
    system,
)


class LoopCleaner(loop_cleaner.LoopCleaner, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def clean(
        self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner
    ) -> None:
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        # Requirement: Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.
        subgraph.set_target(node)

        # Requirement: Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.
        # Requirement: [LoopCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
        # Requirement: Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.
        while not subgraph.is_complete:
            # Requirement: [LoopCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
            batch = subgraph.next_ready_batch()
            if not batch:  # pragma: no cover (assumption: acyclic subgraph guarantees non-empty batch when incomplete)
                break  # pragma: no cover (assumption: acyclic subgraph guarantees non-empty batch when incomplete)
            subgraph.record_visit(batch)
            should_continue = cleaner.clean(batch)
            # Requirement: [LoopCleaner] Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
            if not should_continue:
                return


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopCleaner,
        keys=[LoopCleaner, loop_cleaner.LoopCleaner],
        tier=system,
    )
