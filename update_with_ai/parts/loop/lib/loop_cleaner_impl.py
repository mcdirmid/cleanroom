# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-11T04:57:57Z
# CHANGE: Call DagSubgraph.is_complete directly instead of a defensive attribute shim, realizing the grounded completion check
# CODE_HASH: 501418d227e0
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

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
        self, target: dag_storage.DagNode, node_cleaner: loop_node_cleaner.NodeCleaner
    ) -> bool:
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        subgraph.set_target(target)

        while not subgraph.is_complete():
            batch = subgraph.next_ready_batch()
            if (
                not batch
            ):  # pragma: no cover (assumption: acyclic graph progress guaranteed)
                break
            should_continue = node_cleaner.clean(batch)
            subgraph.record_visit(batch)
            if not should_continue:
                return False

        return subgraph.is_complete()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopCleaner,
        keys=[LoopCleaner, loop_cleaner.LoopCleaner],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
