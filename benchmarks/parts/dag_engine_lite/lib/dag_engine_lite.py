from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.lifecycle import Singleton, SystemTier, system
import enum

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')

@dataclass(frozen=True)
class DAGError(Exception):
    # TODO_DAGError_body
    message: str


@dataclass(frozen=True)
class CycleError(DAGError):
    # TODO_CycleError_body
    cycle: Tuple[str, ...]


@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    # TODO_NodeNotFoundError_body
    node_id: str


@dataclass(frozen=True)
class NodeExecutionError(DAGError):
    # TODO_NodeExecutionError_body
    node_id: str
    cause: Exception


class NodeState(enum.Enum):
    PENDING = 'pending'
    READY = 'ready'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    SKIPPED = 'skipped'


class FailurePolicy(enum.Enum):
    FAIL_FAST = 'fail_fast'
    CONTINUE_ON_ERROR = 'continue_on_error'
    SKIP_DOWNSTREAM = 'skip_downstream'


@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    # TODO_NodeDefinition_body
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    # TODO_NodeResult_body
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@dataclass(frozen=True)
class DAGRunReport:
    # TODO_DAGRunReport_body
    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


class DAG(Singleton[SystemTier], Protocol):
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        # TODO_add_node_body
        ...

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # TODO_add_edge_body
        ...

    def remove_node(self, node_id: str) -> None:
        # TODO_remove_node_body
        ...

    def has_node(self, node_id: str) -> bool:
        # TODO_has_node_body
        ...

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        # TODO_get_node_body
        ...

    def get_dependencies(self, node_id: str) -> Set[str]:
        # TODO_get_dependencies_body
        ...

    def get_dependents(self, node_id: str) -> Set[str]:
        # TODO_get_dependents_body
        ...

    def all_nodes(self) -> Set[str]:
        # TODO_all_nodes_body
        ...

    def validate(self) -> None:
        # TODO_validate_body
        ...

    def topological_sort(self) -> List[str]:
        # TODO_topological_sort_body
        ...

    def find_roots(self) -> Set[str]:
        # TODO_find_roots_body
        ...

    def find_leaves(self) -> Set[str]:
        # TODO_find_leaves_body
        ...

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        # TODO_compute_critical_path_body
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    def next_wave(self) -> List[str]:
        # TODO_next_wave_body
        ...

    def mark_running(self, node_id: str) -> None:
        # TODO_mark_running_body
        ...

    def mark_succeeded(self, node_id: str) -> None:
        # TODO_mark_succeeded_body
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
        # TODO_mark_failed_body
        ...

    def is_finished(self) -> bool:
        # TODO_is_finished_body
        ...

    def get_state(self, node_id: str) -> NodeState:
        # TODO_get_state_body
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        # TODO_get_all_states_body
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    def run(self, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> DAGRunReport:
        # TODO_run_body
        ...
