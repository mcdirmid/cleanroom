# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_044805_gemini-flash_dag_engine_lite_combined
# Timestamp: 2026-11-12T04:48:05.427916+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-flash (Tier 2)
# Methodology: combined
# Harness: antigravity
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,158,172
#   Cached Inbound Tokens:   39,531,299
#   Outbound Tokens:         377,648
#   Total Tokens:            42,067,119
#   Financial Cost ($USD):   $1.3552
#   Wall Clock Duration:     2075.24s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 3, lib: 4, pretense: 8, pretense_coverage: 7, pretense_qa: 8, qa: 3, test: 2 (Total: 35)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       68
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import (
    Any,
    Callable,
    Collection,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    TypeVar,
)

from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors."""

    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Precondition contract violation error raised when a dependency cycle is detected within the DAG."""

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Precondition contract violation error raised when a referenced node identifier does not exist in the DAG."""

    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Precondition contract violation error raised when attempting to add a node identifier that already exists in the DAG."""

    node_id: str


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution."""

    node_id: str
    cause: Exception


class NodeState(enum.Enum):
    """Execution lifecycle state of a graph node."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class FailurePolicy(enum.Enum):
    """Policy governing graph execution when a node action fails."""

    FAIL_FAST = "fail_fast"
    CONTINUE_ON_ERROR = "continue_on_error"
    SKIP_DOWNSTREAM = "skip_downstream"


@data_type
@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    """Immutable definition of a task node in the directed acyclic graph."""

    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@data_type
@dataclass(frozen=True)
class NodeResult(Generic[T]):
    """Outcome record of a node execution."""

    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@data_type
@dataclass(frozen=True)
class DAGRunReport:
    """Consolidated summary report of an entire DAG execution run."""

    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


@singleton_type("system")
class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    @operation
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph."""
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        ...

    @operation
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node."""
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
        ...


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:56:09Z
# LAST_CHANGED: 2026-11-12T04:56:09Z
# CHANGE: Implement interface types, error classes, enums, definitions, and service protocols
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations

import dataclasses
import heapq
import time
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)

from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite


def _kahn_topological_sort(
    nodes: Collection[str],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    priorities: Mapping[str, float],
    cycle_error_cls: type[dag_engine_lite.CycleError],
) -> List[str]:
    """Computes deterministic topological ordering using Kahn's algorithm with max-heap priority queue."""
    node_set = set(nodes)
    in_degree: Dict[str, int] = {nid: len(upstream.get(nid, set()) & node_set) for nid in node_set}

    heap: List[Tuple[float, str]] = []
    for nid in node_set:
        if in_degree[nid] == 0:
            heapq.heappush(heap, (-priorities.get(nid, 0.0), nid))

    order: List[str] = []
    while heap:
        neg_pri, nid = heapq.heappop(heap)
        order.append(nid)
        for dep_id in downstream.get(nid, set()):
            if dep_id in in_degree:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    heapq.heappush(heap, (-priorities.get(dep_id, 0.0), dep_id))

    if len(order) != len(node_set):
        remaining = node_set - set(order)
        visited_state: Dict[str, int] = {nid: 0 for nid in remaining}
        cycle_path: List[str] = []

        def dfs(curr: str, stack: List[str]) -> bool:
            visited_state[curr] = 1
            stack.append(curr)
            for nxt in sorted(downstream.get(curr, set())):
                if nxt in remaining:
                    if visited_state[nxt] == 1:
                        idx = stack.index(nxt)
                        cycle_path.extend(stack[idx:] + [nxt])
                        return True
                    if visited_state[nxt] == 0:
                        if dfs(nxt, stack):
                            return True
            stack.pop()
            visited_state[curr] = 2
            return False

        for nid in sorted(remaining):
            if visited_state[nid] == 0:
                if dfs(nid, []):
                    break

        raise cycle_error_cls(
            message="Cycle detected in DAG",
            cycle=tuple(cycle_path) if cycle_path else tuple(sorted(remaining)),
        )

    return order


def _compute_critical_path_dp(
    topological_order: Sequence[str],
    upstream: Mapping[str, Set[str]],
    durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    """Computes the longest weighted critical path through a DAG."""
    if not topological_order:
        return [], 0.0

    earliest_finish: Dict[str, float] = {}
    best_parent: Dict[str, Optional[str]] = {}

    for nid in topological_order:
        dur = durations.get(nid, 1.0) if durations is not None else 1.0
        preds = upstream.get(nid, set())
        if not preds:
            earliest_finish[nid] = dur
            best_parent[nid] = None
        else:
            best_p = max(preds, key=lambda p: (earliest_finish.get(p, 0.0), p))
            earliest_finish[nid] = earliest_finish.get(best_p, 0.0) + dur
            best_parent[nid] = best_p

    max_leaf = max(topological_order, key=lambda n: (earliest_finish[n], n))
    max_duration = earliest_finish[max_leaf]

    path: List[str] = []
    curr: Optional[str] = max_leaf
    while curr is not None:
        path.append(curr)
        curr = best_parent.get(curr)
    path.reverse()

    return path, max_duration


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = "system"

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    @operation
    @override
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph."""
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' already exists in DAG",
                node_id=node_id,
            )

        dep_set = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dep_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition

        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        for dep in dep_set:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found in DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found in DAG",
                node_id=downstream_id,
            )

        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

        downstream_def = self._nodes[downstream_id]
        if upstream_id not in downstream_def.dependencies:
            self._nodes[downstream_id] = dataclasses.replace(
                downstream_def,
                dependencies=downstream_def.dependencies | {upstream_id},
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        for u in list(self._upstream.get(node_id, set())):
            if u in self._downstream:
                self._downstream[u].discard(node_id)

        for d in list(self._downstream.get(node_id, set())):
            if d in self._upstream:
                self._upstream[d].discard(node_id)
            if d in self._nodes:
                d_def = self._nodes[d]
                if node_id in d_def.dependencies:
                    self._nodes[d] = dataclasses.replace(
                        d_def,
                        dependencies=frozenset(d_def.dependencies - {node_id}),
                    )

        self._nodes.pop(node_id, None)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        if isinstance(scheduler, WaveScheduler):
            scheduler._states.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        for nid, node_def in self._nodes.items():
            for dep in node_def.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep}' referenced by node '{nid}' not found in DAG",
                        node_id=dep,
                    )

        visited_state: Dict[str, int] = {nid: 0 for nid in self._nodes}
        cycle_path: List[str] = []

        def dfs(curr: str, stack: List[str]) -> bool:
            visited_state[curr] = 1
            stack.append(curr)
            for nxt in sorted(self._downstream.get(curr, set())):
                if nxt in self._nodes:
                    if visited_state[nxt] == 1:
                        idx = stack.index(nxt)
                        cycle_path.extend(stack[idx:] + [nxt])
                        return True
                    if visited_state[nxt] == 0:
                        if dfs(nxt, stack):
                            return True
            stack.pop()
            visited_state[curr] = 2
            return False

        for nid in sorted(self._nodes.keys()):
            if visited_state[nid] == 0:
                if dfs(nid, []):
                    break

        if cycle_path:
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=tuple(cycle_path),
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        for nid, node_def in self._nodes.items():
            for dep in node_def.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep}' referenced by node '{nid}' not found in DAG",
                        node_id=dep,
                    )

        priorities = {nid: float(self._nodes[nid].priority) for nid in self._nodes}
        return _kahn_topological_sort(
            nodes=self._nodes.keys(),
            upstream=self._upstream,
            downstream=self._downstream,
            priorities=priorities,
            cycle_error_cls=dag_engine_lite.CycleError,
        )

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {nid for nid in self._nodes if not self._upstream.get(nid, set())}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {nid for nid in self._nodes if not self._downstream.get(nid, set())}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        order = self.topological_sort()
        return _compute_critical_path_dp(
            topological_order=order,
            upstream=self._upstream,
            durations=estimated_durations,
        )


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = "system"

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _sync_states(self) -> None:
        for nid in self._dag.all_nodes():
            if nid not in self._states:
                deps = self._dag.get_dependencies(nid)
                if not deps:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    def _reset_states(self) -> None:
        self._states.clear()
        self._sync_states()

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = self._dag.get_dependencies(nid)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    candidates.append(nid)

        candidates.sort(key=lambda n: (-self._dag.get_node(n).priority, n))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dep_id in self._dag.get_dependents(node_id):
            if dep_id in self._states and self._states[dep_id] == dag_engine_lite.NodeState.PENDING:
                upstream = self._dag.get_dependencies(dep_id)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid, st in list(self._states.items()):
                if st not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED

        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            queue: List[str] = list(self._dag.get_dependents(node_id))
            visited: Set[str] = set(queue)
            while queue:
                curr = queue.pop(0)
                for d in self._dag.get_dependents(curr):
                    if d not in visited:
                        visited.add(d)
                        queue.append(d)

            for d in visited:
                if d in self._states and self._states[d] not in terminal_states:
                    self._states[d] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        current_nodes = self._dag.all_nodes()
        if not current_nodes:
            return True
        self._sync_states()

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if all(self._states.get(nid) in terminal_states for nid in current_nodes):
            return True

        return not any(
            self._states.get(nid) in (dag_engine_lite.NodeState.READY, dag_engine_lite.NodeState.RUNNING)
            for nid in current_nodes
        )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        if not self._dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduled DAG",
                node_id=node_id,
            )
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        current_nodes = self._dag.all_nodes()
        return {nid: self._states[nid] for nid in current_nodes if nid in self._states}


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = "system"

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    @property
    def _scheduler(self) -> dag_engine_lite.WaveScheduler:
        return get_singleton(dag_engine_lite.WaveScheduler)

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        self._dag.validate()

        start_time = time.perf_counter()
        self._results.clear()
        if isinstance(self._scheduler, WaveScheduler):
            self._scheduler._reset_states()

        fail_fast_stopped = False
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            for node_id in wave:
                self._scheduler.mark_running(node_id)
                node_def = self._dag.get_node(node_id)
                retries_left = node_def.retries
                retries_attempted = 0
                action_start = time.perf_counter()
                succeeded = False
                result_val: Any = None
                caught_err: Optional[Exception] = None

                while True:
                    try:
                        result_val = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        caught_err = exc
                        if retries_left > 0:
                            retries_left -= 1
                            retries_attempted += 1
                        else:
                            break

                action_duration = time.perf_counter() - action_start

                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=result_val,
                        error=None,
                        duration_seconds=action_duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=caught_err,
                        duration_seconds=action_duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        fail_fast_stopped = True
                        break

            if fail_fast_stopped:
                break

        all_states = self._scheduler.get_all_states()
        for nid, st in all_states.items():
            if nid not in self._results:
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=st,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        durations = {nid: res.duration_seconds for nid, res in self._results.items()}
        crit_path_list, _ = self._dag.compute_critical_path(durations)

        total_nodes = len(self._dag.all_nodes())
        succeeded_nodes = tuple(
            sorted(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.SUCCEEDED)
        )
        failed_nodes = tuple(
            sorted(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.FAILED)
        )
        skipped_nodes = tuple(
            sorted(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.SKIPPED)
        )
        cancelled_nodes = tuple(
            sorted(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.CANCELLED)
        )
        wall_clock = time.perf_counter() - start_time

        return dag_engine_lite.DAGRunReport(
            total_nodes=total_nodes,
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(crit_path_list),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T05:22:37Z
# LAST_CHANGED: 2026-11-12T05:10:16Z
# CHANGE: Prune redundant exception suppression in remove_node, remove redundant fallback in is_finished, delegate empty critical path check to helper, and prune redundant empty wave break in run
# COVERAGE_AUDIT: 2026-11-12T05:11:07Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T05:22:37Z
# PRETENSE_QA_AUDIT: 2026-11-12T05:22:03Z
# QA_AUDIT: 2026-11-12T05:10:44Z
# --- END AUTOFAB METADATA ---
