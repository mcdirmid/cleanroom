from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi

class DAG(dag_engine_lite.DAG):
    tier = system

    def __init__(self) -> None:
        # TODO___init___body
        pass

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        # TODO_add_node_body
        raise NotImplementedError

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # TODO_add_edge_body
        raise NotImplementedError

    def remove_node(self, node_id: str) -> None:
        # TODO_remove_node_body
        raise NotImplementedError

    def has_node(self, node_id: str) -> bool:
        # TODO_has_node_body
        raise NotImplementedError

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # TODO_get_node_body
        raise NotImplementedError

    def get_dependencies(self, node_id: str) -> Set[str]:
        # TODO_get_dependencies_body
        raise NotImplementedError

    def get_dependents(self, node_id: str) -> Set[str]:
        # TODO_get_dependents_body
        raise NotImplementedError

    def all_nodes(self) -> Set[str]:
        # TODO_all_nodes_body
        raise NotImplementedError

    def validate(self) -> None:
        # TODO_validate_body
        raise NotImplementedError

    def topological_sort(self) -> List[str]:
        # TODO_topological_sort_body
        raise NotImplementedError

    def find_roots(self) -> Set[str]:
        # TODO_find_roots_body
        raise NotImplementedError

    def find_leaves(self) -> Set[str]:
        # TODO_find_leaves_body
        raise NotImplementedError

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        # TODO_compute_critical_path_body
        raise NotImplementedError


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        # TODO___init___body
        pass

    def next_wave(self) -> List[str]:
        # TODO_next_wave_body
        raise NotImplementedError

    def mark_running(self, node_id: str) -> None:
        # TODO_mark_running_body
        raise NotImplementedError

    def mark_succeeded(self, node_id: str) -> None:
        # TODO_mark_succeeded_body
        raise NotImplementedError

    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy=dag_engine_lite.FailurePolicy.FAIL_FAST) -> None:
        # TODO_mark_failed_body
        raise NotImplementedError

    def is_finished(self) -> bool:
        # TODO_is_finished_body
        raise NotImplementedError

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # TODO_get_state_body
        raise NotImplementedError

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        # TODO_get_all_states_body
        raise NotImplementedError


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        # TODO___init___body
        pass

    def run(self, failure_policy: dag_engine_lite.FailurePolicy=dag_engine_lite.FailurePolicy.FAIL_FAST) -> dag_engine_lite.DAGRunReport:
        # TODO_run_body
        raise NotImplementedError


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine_lite.DAG],
        tier=system,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine_lite.WaveScheduler],
        tier=system,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine_lite.DAGRunner],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
