from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import auto_initialize, singleton
from . import dag_engine

# Requirements specified in dag_engine_impl.pyi

@singleton
class DAG(dag_engine.DAG):

    def __init__(self) -> None:
        # TODO___init___body
        pass

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, timeout_seconds: Optional[float]=None, retries: int=0) -> None:
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

    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
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


@singleton
class WaveScheduler(dag_engine.WaveScheduler):

    def __init__(self, dag: Optional[dag_engine.DAG] = None) -> None:
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

    def mark_failed(self, node_id: str, failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST) -> None:
        # TODO_mark_failed_body
        raise NotImplementedError

    def is_finished(self) -> bool:
        # TODO_is_finished_body
        raise NotImplementedError

    def get_state(self, node_id: str) -> dag_engine.NodeState:
        # TODO_get_state_body
        raise NotImplementedError

    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        # TODO_get_all_states_body
        raise NotImplementedError


@singleton
class DAGRunner(dag_engine.DAGRunner):

    def __init__(self, dag: Optional[dag_engine.DAG] = None, scheduler: Optional[dag_engine.WaveScheduler] = None) -> None:
        # TODO___init___body
        pass

    def run(self, timeout_seconds: Optional[float] = None, failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST, max_concurrency: int = 4) -> dag_engine.DAGRunReport:
        # TODO_run_body
        raise NotImplementedError

    def cancel(self) -> None:
        # TODO_cancel_body
        raise NotImplementedError

    def is_cancelled(self) -> bool:
        # TODO_is_cancelled_body
        raise NotImplementedError

__initialize__ = auto_initialize()
_initialize_ = __initialize__
