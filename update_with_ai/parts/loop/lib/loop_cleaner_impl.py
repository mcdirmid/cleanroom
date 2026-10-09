# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: a5dc0c07b589
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
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

        def _is_complete() -> bool:
            comp = getattr(subgraph, "is_complete")
            return bool(comp()) if callable(comp) else bool(comp)

        while not _is_complete():
            batch = subgraph.next_ready_batch()
            if (
                not batch
            ):  # pragma: no cover (assumption: acyclic graph progress guaranteed)
                break
            should_continue = node_cleaner.clean(batch)
            subgraph.record_visit(batch)
            if not should_continue:
                return False

        return _is_complete()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopCleaner,
        keys=[LoopCleaner, loop_cleaner.LoopCleaner],
        tier=system,
    )
