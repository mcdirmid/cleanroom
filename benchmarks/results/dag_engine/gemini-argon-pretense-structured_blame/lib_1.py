# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_225041_gemini-argon_dag_engine_pretense
# Timestamp: 2026-11-13T22:50:41.835890+00:00
# Benchmark Task: dag_engine
# Model: gemini-argon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,189,911
#   Cached Inbound Tokens:   16,515,683
#   Outbound Tokens:         274,263
#   Total Tokens:            17,979,857
#   Financial Cost ($USD):   $13.3803
#   Wall Clock Duration:     3350.61s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 3, pretense: 9, pretense_coverage: 3, pretense_qa: 6 (Total: 21)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Library interface definitions for the DAG execution and wave scheduling engine."""

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

from pretense import test_only
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
    """Raised when a dependency cycle is detected within the DAG."""

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG."""

    node_id: str


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution."""

    node_id: str
    cause: Exception


@data_type
@dataclass
class DAGTimeoutError(DAGError):
    """Raised when overall DAG execution exceeds the allocated timeout."""


@data_type
@dataclass
class DAGCancelledError(DAGError):
    """Raised when DAG execution is explicitly cancelled."""


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
    dependencies: FrozenSet[str] = frozenset()
    priority: int = 0
    timeout_seconds: Optional[float] = None
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
        timeout_seconds: Optional[float] = None,
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
        """Returns all root nodes with in-degree zero (no dependencies)."""
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
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
    """Partitions and coordinates DAG nodes into executable waves of concurrency."""

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
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
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
    """Executes a DAG under concurrency limits, failure policies, and timeouts."""

    @operation
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        ...

    @operation
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        ...

    @operation
    @test_only
    def is_cancelled(self) -> bool:
        """Query accessor verifying whether cancellation has been signaled."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:02:26Z
# LAST_CHANGED: 2026-11-13T23:02:26Z
# CHANGE: Implement DAG engine interface protocols, data types, and exceptions
# --- END AUTOFAB METADATA ---


# === File: dag_engine_impl.py ===
"""Concrete library implementation for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import heapq
import threading
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

from pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine

_TERMINAL_STATES: FrozenSet[dag_engine.NodeState] = frozenset(
    {
        dag_engine.NodeState.SUCCEEDED,
        dag_engine.NodeState.FAILED,
        dag_engine.NodeState.SKIPPED,
        dag_engine.NodeState.CANCELLED,
    }
)


@singleton
@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = "system"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, dag_engine.NodeDefinition[Any]] = {}
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
        timeout_seconds: Optional[float] = None,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph."""
        with self._lock:
            # Normalize upstream dependencies into an immutable set for the node definition.
            deps = frozenset(dependencies or ())
            definition = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=deps,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._nodes[node_id] = definition
            self._upstream.setdefault(node_id, set()).update(deps)
            self._downstream.setdefault(node_id, set())
            for dep_id in deps:
                self._downstream.setdefault(dep_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        with self._lock:
            # Verify both endpoints are registered before linking.
            for nid in (upstream_id, downstream_id):
                if nid not in self._nodes:
                    raise dag_engine.NodeNotFoundError(
                        f"Node '{nid}' does not exist in the graph.",
                        node_id=nid,
                    )
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)
            self._nodes[downstream_id] = replace(
                self._nodes[downstream_id],
                dependencies=frozenset(self._upstream[downstream_id]),
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        with self._lock:
            # Ensure target node exists prior to removal.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist in the graph.",
                    node_id=node_id,
                )
            for up_id in self._upstream.pop(node_id, set()):
                self._downstream.get(up_id, set()).discard(node_id)
            for down_id in self._downstream.pop(node_id, set()):
                self._upstream.get(down_id, set()).discard(node_id)
                self._nodes[down_id] = replace(
                    self._nodes[down_id],
                    dependencies=frozenset(self._upstream[down_id]),
                )
            del self._nodes[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        with self._lock:
            return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist in the graph.",
                    node_id=node_id,
                )
            return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist in the graph.",
                    node_id=node_id,
                )
            return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist in the graph.",
                    node_id=node_id,
                )
            return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        with self._lock:
            return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        with self._lock:
            # Verify that every declared dependency references a registered node.
            for node_id in sorted(self._nodes):
                for dep_id in sorted(self._upstream[node_id]):
                    if dep_id not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            f"Dependency node '{dep_id}' referenced by '{node_id}' does not exist.",
                            node_id=dep_id,
                        )
            # Delegate cycle verification to topological sort.
            self.topological_sort()

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        with self._lock:
            in_degree: Dict[str, int] = {
                nid: len([d for d in self._upstream[nid] if d in self._nodes])
                for nid in self._nodes
            }
            ready_heap: List[Tuple[int, str]] = [
                (-self._nodes[nid].priority, nid)
                for nid, deg in in_degree.items()
                if deg == 0
            ]
            heapq.heapify(ready_heap)
            order: List[str] = []
            while ready_heap:
                _, curr = heapq.heappop(ready_heap)
                order.append(curr)
                for down_id in self._downstream.get(curr, set()):
                    in_degree[down_id] -= 1
                    if in_degree[down_id] == 0:
                        heapq.heappush(ready_heap, (-self._nodes[down_id].priority, down_id))
            # Reconstruct the directed cycle when not all nodes could be ordered.
            if len(order) < len(self._nodes):
                remaining = {nid for nid, deg in in_degree.items() if deg > 0}
                curr_node = min(remaining)
                visited_path: List[str] = []
                while curr_node not in visited_path:
                    visited_path.append(curr_node)
                    curr_node = min(u for u in self._upstream[curr_node] if u in remaining)
                cycle_start = visited_path.index(curr_node)
                cycle_nodes = list(reversed(visited_path[cycle_start:]))
                cycle = tuple([curr_node] + cycle_nodes)
                raise dag_engine.CycleError(
                    f"Cycle detected in DAG: {' -> '.join(cycle)}",
                    cycle=cycle,
                )
            return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        with self._lock:
            return {nid for nid in self._nodes if not self._upstream.get(nid)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        with self._lock:
            return {nid for nid in self._nodes if not self._downstream.get(nid)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        with self._lock:
            topo_order = self.topological_sort()
            durations = estimated_durations or {}
            dist: Dict[str, Tuple[float, int]] = {}
            pred: Dict[str, Optional[str]] = {}
            for node_id in topo_order:
                weight = float(durations.get(node_id, 1.0))
                upstreams = [u for u in self._upstream[node_id] if u in dist]
                best_u = max(upstreams, key=lambda u: dist[u], default=None)
                base_weight, base_len = dist[best_u] if best_u is not None else (0.0, 0)
                dist[node_id] = (base_weight + weight, base_len + 1)
                pred[node_id] = best_u
            end_node = max(topo_order, key=lambda nid: dist[nid], default=None)
            path: List[str] = []
            curr: Optional[str] = end_node
            while curr is not None:
                path.append(curr)
                curr = pred[curr]
            path.reverse()
            total_weight = dist[end_node][0] if end_node is not None else 0.0
            return path, total_weight


@singleton
@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG."""

    tier = "system"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._dag: Optional[dag_engine.DAG] = None
        self._states: Dict[str, dag_engine.NodeState] = {}

    def _sync_states(self) -> dag_engine.DAG:
        dag = get_singleton(dag_engine.DAG)
        self._dag = dag
        roots = dag.find_roots()
        for node_id in dag.all_nodes():
            self._states.setdefault(
                node_id,
                dag_engine.NodeState.READY if node_id in roots else dag_engine.NodeState.PENDING,
            )
        return dag

    def _cancel_non_terminal(self) -> None:
        with self._lock:
            self._sync_states()
            non_terminal = [
                nid for nid, st in self._states.items() if st not in _TERMINAL_STATES
            ]
            for nid in non_terminal:
                self._states[nid] = dag_engine.NodeState.CANCELLED

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        with self._lock:
            dag = self._sync_states()
            ready_nodes = [
                node_id
                for node_id, state in self._states.items()
                if state == dag_engine.NodeState.READY
                and all(
                    self._states.get(dep) == dag_engine.NodeState.SUCCEEDED
                    for dep in dag.get_dependencies(node_id)
                )
            ]
            ready_nodes.sort(key=lambda nid: (-dag.get_node(nid).priority, nid))
            return ready_nodes

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        with self._lock:
            self._sync_states()
            self._states[node_id] = dag_engine.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        with self._lock:
            dag = self._sync_states()
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            unblocked = [
                dep_id
                for dep_id in dag.get_dependents(node_id)
                if self._states.get(dep_id) == dag_engine.NodeState.PENDING
                and all(
                    self._states.get(u) == dag_engine.NodeState.SUCCEEDED
                    for u in dag.get_dependencies(dep_id)
                )
            ]
            for dep_id in unblocked:
                self._states[dep_id] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        with self._lock:
            dag = self._sync_states()
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy == dag_engine.FailurePolicy.FAIL_FAST:
                non_terminal = [
                    nid for nid, st in self._states.items() if st not in _TERMINAL_STATES
                ]
                for nid in non_terminal:
                    self._states[nid] = dag_engine.NodeState.CANCELLED
            elif failure_policy == dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                queue = [
                    d
                    for d in dag.get_dependents(node_id)
                    if self._states.get(d) not in _TERMINAL_STATES
                ]
                while queue:
                    curr = queue.pop(0)
                    self._states[curr] = dag_engine.NodeState.SKIPPED
                    queue.extend(
                        d
                        for d in dag.get_dependents(curr)
                        if self._states.get(d) not in _TERMINAL_STATES and d not in queue
                    )

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        with self._lock:
            dag = self._sync_states()
            return all(self._states.get(nid) in _TERMINAL_STATES for nid in dag.all_nodes())

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine.NodeState:
        """Retrieves the current execution state of a node."""
        with self._lock:
            self._sync_states()
            return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        """Returns the execution state of every node in the graph."""
        with self._lock:
            self._sync_states()
            return dict(self._states)


@singleton
@singleton_type("system")
class DAGRunner(dag_engine.DAGRunner):
    """Concrete realization of concurrent DAG execution runner."""

    tier = "system"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dag: Optional[dag_engine.DAG] = None
        self._scheduler: Optional[dag_engine.WaveScheduler] = None
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}

    def _execute_node(
        self,
        definition: dag_engine.NodeDefinition[Any],
    ) -> dag_engine.NodeResult[Any]:
        node_start = time.monotonic()
        attempts = 0
        last_error: Optional[Exception] = None
        while attempts <= definition.retries:
            try:
                value = definition.action()
                duration = time.monotonic() - node_start
                return dag_engine.NodeResult(
                    node_id=definition.node_id,
                    state=dag_engine.NodeState.SUCCEEDED,
                    value=value,
                    error=None,
                    duration_seconds=duration,
                    retries_attempted=attempts,
                )
            except Exception as exc:
                last_error = exc
                attempts += 1
        duration = time.monotonic() - node_start
        return dag_engine.NodeResult(
            node_id=definition.node_id,
            state=dag_engine.NodeState.FAILED,
            value=None,
            error=last_error,
            duration_seconds=duration,
            retries_attempted=definition.retries,
        )

    def _cancel_non_terminal(self) -> None:
        scheduler = get_singleton(dag_engine.WaveScheduler)
        self._scheduler = scheduler
        cancel_fn = getattr(scheduler, "_cancel_non_terminal", lambda: None)
        cancel_fn()

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        dag = get_singleton(dag_engine.DAG)
        scheduler = get_singleton(dag_engine.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler
        dag.validate()
        start_time = time.monotonic()
        with self._lock:
            self._results = {}
        with ThreadPoolExecutor(max_workers=max(1, max_concurrency)) as executor:
            while self._cancelled.is_set() or (
                not scheduler.is_finished() and bool(scheduler.next_wave())
            ):
                wave = scheduler.next_wave()
                for nid in wave:
                    scheduler.mark_running(nid)
                futures = {
                    executor.submit(self._execute_node, dag.get_node(nid)): nid
                    for nid in wave
                }
                wave_results = {nid: fut.result() for fut, nid in futures.items()}
                if self._cancelled.is_set():
                    self._cancel_non_terminal()
                    raise dag_engine.DAGCancelledError("DAG execution was cancelled.")
                if (
                    timeout_seconds is not None
                    and (time.monotonic() - start_time) >= timeout_seconds
                ):
                    raise dag_engine.DAGTimeoutError(
                        f"DAG execution exceeded timeout of {timeout_seconds} seconds."
                    )
                for nid in wave:
                    res = wave_results[nid]
                    with self._lock:
                        self._results[nid] = res
                    if res.state == dag_engine.NodeState.SUCCEEDED:
                        scheduler.mark_succeeded(nid)
                    else:
                        scheduler.mark_failed(nid, failure_policy)
        wall_clock_seconds = time.monotonic() - start_time
        critical_path_list, _ = dag.compute_critical_path(None)
        all_states = scheduler.get_all_states()
        with self._lock:
            for nid, st in all_states.items():
                self._results.setdefault(nid, dag_engine.NodeResult(node_id=nid, state=st))
            results_snapshot = dict(self._results)
        succeeded_nodes = tuple(
            sorted(nid for nid, st in all_states.items() if st == dag_engine.NodeState.SUCCEEDED)
        )
        failed_nodes = tuple(
            sorted(nid for nid, st in all_states.items() if st == dag_engine.NodeState.FAILED)
        )
        skipped_nodes = tuple(
            sorted(nid for nid, st in all_states.items() if st == dag_engine.NodeState.SKIPPED)
        )
        cancelled_nodes = tuple(
            sorted(nid for nid, st in all_states.items() if st == dag_engine.NodeState.CANCELLED)
        )
        return dag_engine.DAGRunReport(
            total_nodes=len(all_states),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path_list),
            results=results_snapshot,
        )

    @operation
    @override
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        with self._lock:
            self._cancelled.set()
        self._cancel_non_terminal()

    @operation
    @override
    @test_only
    def is_cancelled(self) -> bool:
        """Query accessor verifying whether cancellation has been signaled."""
        with self._lock:
            return self._cancelled.is_set()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:46:29Z
# LAST_CHANGED: 2026-11-13T23:02:31Z
# CHANGE: Implement concrete DAG, WaveScheduler, and DAGRunner services
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T23:46:29Z
# PRETENSE_QA_AUDIT: 2026-11-13T23:46:01Z
# --- END AUTOFAB METADATA ---
