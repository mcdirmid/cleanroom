# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_220103_gemini-argon_dag_engine_lite_pretense
# Timestamp: 2026-11-13T22:01:03.643422+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-argon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 797,946
#   Cached Inbound Tokens:   8,034,332
#   Outbound Tokens:         183,531
#   Total Tokens:            9,015,809
#   Financial Cost ($USD):   $7.4484
#   Wall Clock Duration:     2042.72s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 7, pretense: 4, pretense_coverage: 3, pretense_qa: 5 (Total: 19)
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

# === File: dag_engine_lite.py ===
"""Interface definitions for the synchronous DAG execution and wave scheduling engine."""

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
    """Precondition violation error raised when a dependency cycle is detected within the DAG."""

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Precondition violation error raised when a referenced node identifier does not exist in the DAG."""

    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Precondition violation error raised when attempting to add a node identifier that already exists in the DAG."""

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
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:08:48Z
# LAST_CHANGED: 2026-11-13T22:08:48Z
# CHANGE: Implement DAG engine lite interface definitions, data types, enums, and exception classes
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)
from support.lib.framework import operation, override, singleton_type, unreachable
from support.lib.lifecycle import get_singleton, singleton
from . import dag_engine_lite

_TERMINAL_STATES = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)


@singleton
@singleton_type("system")
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
        # Reject duplicate node registrations.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )

        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())

        # Register directed dependency edges without eagerly checking missing upstream nodes.
        for dep_id in deps:
            self._upstream[node_id].add(dep_id)
            self._downstream.setdefault(dep_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        # Ensure both endpoint nodes are registered before adding the edge.
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

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        # Verify the target node exists prior to removal.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        for up_id in list(self._upstream.get(node_id, set())):
            self._downstream.get(up_id, set()).discard(node_id)

        for down_id in list(self._downstream.get(node_id, set())):
            self._upstream.get(down_id, set()).discard(node_id)

        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        # Purge removed node from wave scheduler state tracking.
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
        return set(self._downstream.get(node_id, set()) & set(self._nodes.keys()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        # Verify that all referenced dependencies exist in the registered node set.
        for node_id in sorted(self._nodes):
            for dep_id in sorted(self._upstream.get(node_id, set())):
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep_id}' referenced by '{node_id}' does not exist in DAG",
                        node_id=dep_id,
                    )

        # Verify graph acyclicity through topological sort.
        self.topological_sort()

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        node_set = set(self._nodes.keys())
        in_degree: Dict[str, int] = {
            nid: len(self._upstream.get(nid, set()) & node_set) for nid in node_set
        }

        heap: List[Tuple[int, str]] = []
        for nid in node_set:
            if in_degree[nid] == 0:
                heapq.heappush(heap, (-self._nodes[nid].priority, nid))

        order: List[str] = []
        while heap:
            _, nid = heapq.heappop(heap)
            order.append(nid)
            for dep_id in self._downstream.get(nid, set()):
                if dep_id in in_degree:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        heapq.heappush(heap, (-self._nodes[dep_id].priority, dep_id))

        # Reconstruct cycle sequence when topological ordering cannot place all nodes.
        if len(order) != len(node_set):
            remaining = node_set - set(order)
            curr = min(remaining)
            visited_idx: Dict[str, int] = {}
            walk: List[str] = []
            while curr not in visited_idx:
                visited_idx[curr] = len(walk)
                walk.append(curr)
                curr = min(self._upstream[curr] & remaining)
            cycle_upstream = walk[visited_idx[curr] :] + [curr]
            cycle_forward = tuple(reversed(cycle_upstream))
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=cycle_forward,
            )

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {nid for nid in self._nodes if not self._upstream.get(nid)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        node_set = set(self._nodes.keys())
        return {
            nid
            for nid in self._nodes
            if not (self._downstream.get(nid, set()) & node_set)
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        topological_order = self.topological_sort()
        if not topological_order:
            return [], 0.0

        node_set = set(self._nodes.keys())
        earliest_finish: Dict[str, float] = {}
        best_parent: Dict[str, Optional[str]] = {}

        for nid in topological_order:
            dur = (
                float(estimated_durations.get(nid, 1.0))
                if estimated_durations is not None
                else 1.0
            )
            preds = self._upstream.get(nid, set()) & node_set
            if not preds:
                earliest_finish[nid] = dur
                best_parent[nid] = None
            else:
                best_p = max(preds, key=lambda p: (earliest_finish[p], p))
                earliest_finish[nid] = earliest_finish[best_p] + dur
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
@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = "system"

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronizes internal state map with currently registered DAG nodes."""
        self._dag = get_singleton(dag_engine_lite.DAG)
        all_nodes = self._dag.all_nodes()
        roots = self._dag.find_roots()
        for stale_id in list(self._states.keys()):
            if stale_id not in all_nodes:
                with unreachable:
                    del self._states[stale_id]
        for nid in all_nodes:
            if nid not in self._states:
                self._states[nid] = (
                    dag_engine_lite.NodeState.READY
                    if nid in roots
                    else dag_engine_lite.NodeState.PENDING
                )

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        ready_candidates = [
            nid
            for nid in self._dag.all_nodes()
            if self._states.get(nid) == dag_engine_lite.NodeState.READY
            and all(
                self._states.get(dep_id) == dag_engine_lite.NodeState.SUCCEEDED
                for dep_id in self._dag.get_dependencies(nid)
            )
        ]
        ready_candidates.sort(
            key=lambda nid: (-self._dag.get_node(nid).priority, nid)
        )
        return ready_candidates

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
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING and all(
                self._states.get(up_id) == dag_engine_lite.NodeState.SUCCEEDED
                for up_id in self._dag.get_dependencies(dep_id)
            ):
                self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        # Apply the configured failure policy across remaining graph nodes.
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid in list(self._states.keys()):
                self._states[nid] = (
                    self._states[nid]
                    if self._states[nid] in _TERMINAL_STATES
                    else dag_engine_lite.NodeState.CANCELLED
                )
        else:
            queue: List[str] = sorted(self._dag.get_dependents(node_id))
            visited: Set[str] = set(queue)
            while queue:
                curr = queue.pop(0)
                self._states[curr] = (
                    self._states[curr]
                    if self._states.get(curr) in _TERMINAL_STATES
                    else dag_engine_lite.NodeState.SKIPPED
                )
                new_deps = self._dag.get_dependents(curr) - visited
                visited.update(new_deps)
                queue.extend(sorted(new_deps))

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        has_running = any(
            self._states.get(nid) == dag_engine_lite.NodeState.RUNNING
            for nid in self._dag.all_nodes()
        )
        return not has_running and not self.next_wave()

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        self._sync_states()
        if node_id not in self._dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduled DAG",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        return {nid: self._states[nid] for nid in all_nodes}


@singleton
@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = "system"

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(
            dag_engine_lite.WaveScheduler
        )
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        self._dag = get_singleton(dag_engine_lite.DAG)
        self._scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag.validate()

        run_start = time.perf_counter()
        self._results = {}

        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            for node_id in wave:
                node_def = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_start = time.perf_counter()
                attempts = 0
                max_retries = node_def.retries
                succeeded = False
                value: Any = None
                last_error: Optional[Exception] = None

                while True:
                    try:
                        value = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempts >= max_retries:
                            break
                        attempts += 1

                duration = time.perf_counter() - node_start
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_error,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

        all_states = self._scheduler.get_all_states()
        for nid, state in all_states.items():
            if nid not in self._results:
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        critical_path_list, _ = self._dag.compute_critical_path(None)
        wall_clock = time.perf_counter() - run_start

        succeeded_nodes = tuple(
            sorted(
                nid
                for nid, state in all_states.items()
                if state == dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                nid
                for nid, state in all_states.items()
                if state == dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                nid
                for nid, state in all_states.items()
                if state == dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                nid
                for nid, state in all_states.items()
                if state == dag_engine_lite.NodeState.CANCELLED
            )
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(all_states),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(critical_path_list),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:35:04Z
# LAST_CHANGED: 2026-11-13T22:32:29Z
# CHANGE: Quarantine unreachable stale_id not in all_nodes branch in _sync_states with unreachable
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:35:04Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:34:36Z
# --- END AUTOFAB METADATA ---
