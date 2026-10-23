# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261022_220840_Qwen3_6-35B-A3B-oQ6-mtp_dag_engine
# Timestamp: 2026-10-22T22:08:40.826114+00:00
# Benchmark Task: dag_engine
# Model: Qwen3.6-35B-A3B-oQ6-mtp (Tier 1)
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,108,572
#   Cached Inbound Tokens:   29,440,060
#   Outbound Tokens:         205,372
#   Total Tokens:            31,754,004
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     6006.26s
#   Step Latencies (s):      [401.4, 461.9, 140.3, 220.9, 251.1, 120.3, 120.3, 40.1, 80.2, 240.6, 140.3, 241.0, 261.1, 40.2, 50.1, 70.2, 130.3, 80.2, 80.2, 90.3, 160.5, 220.6, 80.2, 60.2, 70.2, 50.1, 90.2, 90.2, 60.1, 40.1, 60.1, 200.5, 100.3, 120.3, 170.4, 210.6, 70.2, 40.1, 130.3, 170.4, 70.2, 30.1, 280.8, 40.1, 120.4, 120.3, 220.6, 90.2, 80.3, 40.1, 50.2, 270.9]
#   Turn Latencies (s):      [401.4, 461.9, 140.3, 220.9, 251.1, 120.3, 120.3, 40.1, 80.2, 240.6, 140.3, 241.0, 261.1, 40.2, 50.1, 70.2, 130.3, 80.2, 80.2, 90.3, 160.5, 220.6, 80.2, 60.2, 70.2, 50.1, 90.2, 90.2, 60.1, 40.1, 60.1, 200.5, 100.3, 120.3, 170.4, 210.6, 70.2, 40.1, 130.3, 170.4, 70.2, 30.1, 280.8, 40.1, 120.4, 120.3, 220.6, 90.2, 80.3, 40.1, 50.2, 270.9]
#   Role Execution Rounds:   coverage: 3, lib: 21, qa: 23, test: 7 (Total: 54)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       63
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Library interface for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


# ── Data Types ──────────────────────────────────────────────────────────────

@data_type
@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """
    message: str


@data_type
@dataclass(frozen=True)
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]

    def __init__(self, message: str, cycle: Tuple[str, ...]) -> None:
        super().__init__(message=message)
        object.__setattr__(self, "cycle", cycle)


@data_type
@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str

    def __init__(self, message: str, node_id: str) -> None:
        super().__init__(message=message)
        object.__setattr__(self, "node_id", node_id)


@data_type
@dataclass(frozen=True)
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the failed node.
        cause: Underlying caught exception.
    """
    node_id: str
    cause: Exception

    def __init__(self, message: str, node_id: str, cause: Exception) -> None:
        super().__init__(message=message)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "cause", cause)


@data_type
@dataclass(frozen=True)
class DAGTimeoutError(DAGError):
    """Raised when overall DAG execution exceeds the allocated timeout."""

    def __init__(self, message: str = "DAG execution exceeded timeout") -> None:
        super().__init__(message=message)


@data_type
@dataclass(frozen=True)
class DAGCancelledError(DAGError):
    """Raised when DAG execution is explicitly cancelled."""

    def __init__(self, message: str = "DAG execution was cancelled") -> None:
        super().__init__(message=message)


# ── Enums ───────────────────────────────────────────────────────────────────

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


# ── Value Types ─────────────────────────────────────────────────────────────

@data_type
@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    """Immutable definition of a task node in the directed acyclic graph.

    Args:
        node_id: Unique identifier for the node.
        action: Callable action to execute for this node.
        dependencies: Set of node identifiers that must complete before this node can run.
        priority: Priority value used for wave ordering and tie-breaking (higher runs first).
        timeout_seconds: Optional timeout in seconds for this node action.
        retries: Number of retry attempts on failure.
    """
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    timeout_seconds: Optional[float] = None
    retries: int = 0


@data_type
@dataclass(frozen=True)
class NodeResult(Generic[T]):
    """Outcome record of a node execution.

    Args:
        node_id: Unique identifier of the node.
        state: Final lifecycle state of the node.
        value: Return value of the action when execution succeeds.
        error: Caught exception when execution fails.
        duration_seconds: Wall-clock elapsed execution time in seconds.
        retries_attempted: Number of retries executed before final state.
    """
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@data_type
@dataclass(frozen=True)
class DAGRunReport:
    """Consolidated summary report of an entire DAG execution run.

    Args:
        total_nodes: Total count of nodes in the graph.
        succeeded_nodes: Identifiers of all nodes that completed successfully.
        failed_nodes: Identifiers of all nodes that failed.
        skipped_nodes: Identifiers of all nodes skipped due to upstream failure.
        cancelled_nodes: Identifiers of all nodes cancelled prior to execution.
        wall_clock_seconds: Total wall-clock time elapsed for the run.
        critical_path: Sequence of node identifiers forming the critical path.
        results: Mapping of node identifier to individual NodeResult outcomes.
    """
    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


# ── Service Protocols ───────────────────────────────────────────────────────

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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T22:16:13Z
# LAST_CHANGED: 2026-10-22T22:16:13Z
# CHANGE: Implemented lib/dag_engine.py: interface module with data types (DAGError, CycleError, NodeNotFoundError, NodeExecutionError, DAGTimeoutError, DAGCancelledError), enums (NodeState, FailurePolicy), value types (NodeDefinition, NodeResult, DAGRunReport), and service protocols (DAG, WaveScheduler, DAGRunner) as system-tier singletons inheriting Singleton[SystemTier] and Protocol.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_impl.py ===
"""Concrete implementation of the DAG execution and wave scheduling engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FuturesTimeoutError
from concurrent.futures.thread import _threads_queues, _worker
from threading import Thread, Thread as _ThreadType
from typing import cast, Set
import weakref

from support.lib.lifecycle import LifecycleRegistry, get_default_registry
import heapq
import threading
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier
from . import dag_engine


# ── Custom ThreadPoolExecutor with daemon worker threads ─────────────────────


class _DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor subclass that creates daemon worker threads.

    Daemon threads allow Python to exit immediately without waiting for
    orphaned worker threads (e.g. threads blocked on time.sleep during
    cancellation or timeout).

    Overrides _adjust_thread_count to mark newly created threads as daemon
    before they start. This avoids setting daemon=True on already-started
    threads (which raises RuntimeError).
    """

    def _adjust_thread_count(self) -> None:
        if self._idle_semaphore.acquire(timeout=0):
            return
        assert isinstance(self._threads, set), "Expected mutable thread set"
        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = '%s_%d' % (self._thread_name_prefix or self, num_threads)
            _work_q: Any = self._work_queue
            def weakref_cb(_: object) -> None:
                _work_q.put(None)
            t = threading.Thread(name=thread_name, target=_worker,
                                 args=(weakref.ref(self, weakref_cb),
                                       _work_q,
                                       self._initializer,
                                       self._initargs))
            t.daemon = True
            t.start()
            self._threads.add(t)
            _tqueues: Any = _threads_queues
            _tqueues[t] = _work_q


# ── DAG Implementation ──────────────────────────────────────────────────────

@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    - Synchronizes graph mutations and queries using threading.RLock for thread safety.
    """

    tier: SystemTier = SystemTier("system")

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

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
        # POSTCONDITION: register node definition with frozen dependency set
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        with self._lock:
            self._nodes[node_id] = definition
            if node_id not in self._upstream:
                self._upstream[node_id] = set()
            if node_id not in self._downstream:
                self._downstream[node_id] = set()
            # Add directed edges from each dependency to node_id
            for dep_id in deps:
                if dep_id not in self._upstream:
                    self._upstream[dep_id] = set()
                if dep_id not in self._downstream:
                    self._downstream[dep_id] = set()
                self._upstream[node_id].add(dep_id)
                self._downstream[dep_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # POSTCONDITION: verify both nodes exist before adding edge
        with self._lock:
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Upstream node '{upstream_id}' not found",
                    node_id=upstream_id,
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Downstream node '{downstream_id}' not found",
                    node_id=downstream_id,
                )
            # Update downstream set of upstream node
            if upstream_id not in self._downstream:
                self._downstream[upstream_id] = set()
            self._downstream[upstream_id].add(downstream_id)
            # Update upstream set of downstream node
            if downstream_id not in self._upstream:
                self._upstream[downstream_id] = set()
            self._upstream[downstream_id].add(upstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # POSTCONDITION: verify node exists, then remove and clean incident edges
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            # Remove from all incident upstream neighbor sets
            for dep_id in self._upstream.get(node_id, set()):
                if node_id in self._downstream.get(dep_id, set()):
                    self._downstream[dep_id].discard(node_id)
            # Remove from all incident downstream neighbor sets
            for dependent_id in self._downstream.get(node_id, set()):
                if node_id in self._upstream.get(dependent_id, set()):
                    self._upstream[dependent_id].discard(node_id)
            del self._nodes[node_id]
            del self._upstream[node_id]
            del self._downstream[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        # POSTCONDITION: check membership in _nodes
        with self._lock:
            return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        # POSTCONDITION: return NodeDefinition or raise NodeNotFoundError
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # POSTCONDITION: return copy of _upstream[node_id] or raise NodeNotFoundError
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # POSTCONDITION: return copy of _downstream[node_id] or raise NodeNotFoundError
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        # POSTCONDITION: return set copy of keys in _nodes
        with self._lock:
            return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # POSTCONDITION: check all dependencies exist, then detect cycles via DFS
        with self._lock:
            # Check all referenced dependencies exist
            for node_id, defn in self._nodes.items():
                for dep_id in defn.dependencies:
                    if dep_id not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            message=f"Dependency '{dep_id}' of node '{node_id}' not found",
                            node_id=dep_id,
                        )
            # Cycle detection via depth-first search path tracking
            visited: Set[str] = set()
            rec_stack: Set[str] = set()
            parent_map: Dict[str, Optional[str]] = {}

            def _dfs(node: str) -> Optional[List[str]]:
                visited.add(node)
                rec_stack.add(node)
                for dep in self._downstream.get(node, set()):
                    if dep not in visited:
                        parent_map[dep] = node
                        result = _dfs(dep)
                        if result is not None:
                            return result
                    elif dep in rec_stack:
                        # Reconstruct cycle
                        cycle = [dep, node]
                        current = node
                        while current != dep:
                            current = parent_map.get(current)
                            if current is None:
                                break
                            cycle.append(current)
                        cycle.reverse()
                        return list(cycle)
                rec_stack.discard(node)
                return None

            for node_id in self._nodes:
                if node_id not in visited:
                    parent_map[node_id] = None
                    cycle = _dfs(node_id)
                    if cycle is not None:
                        raise dag_engine.CycleError(
                            message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                            cycle=tuple(cycle),
                        )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # POSTCONDITION: Kahn's algorithm with (-priority, node_id) heap for deterministic ordering
        with self._lock:
            # Compute in-degrees from _upstream
            in_degree: Dict[str, int] = {nid: 0 for nid in self._nodes}
            for nid in self._nodes:
                in_degree[nid] = len(self._upstream.get(nid, set()))

            # Initialize min-heap with zero-in-degree nodes ordered by (-priority, node_id)
            heap: List[Tuple[int, str]] = []
            for nid in self._nodes:
                if in_degree[nid] == 0:
                    priority = self._nodes[nid].priority
                    heapq.heappush(heap, (-priority, nid))

            output: List[str] = []
            while heap:
                neg_pri, nid = heapq.heappop(heap)
                output.append(nid)
                # Decrement downstream in-degrees
                for dependent in self._downstream.get(nid, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        dep_priority = self._nodes[dependent].priority
                        heapq.heappush(heap, (-dep_priority, dependent))

            if len(output) != len(self._nodes):
                # Cycle detected – reconstruct
                remaining = set(self._nodes.keys()) - set(output)
                raise dag_engine.CycleError(
                    message=f"Cycle detected involving nodes: {', '.join(sorted(remaining))}",
                    cycle=tuple(sorted(remaining)),
                )

            return output

    @operation
    @override
    def find_roots(self) -> Set[str]:
        # POSTCONDITION: filter nodes whose _upstream set is empty
        with self._lock:
            return {nid for nid in self._nodes if not self._upstream.get(nid)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        # POSTCONDITION: filter nodes whose _downstream set is empty
        with self._lock:
            return {nid for nid in self._nodes if not self._downstream.get(nid)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # POSTCONDITION: topological sort + DP over topological order, backtrack from max completion
        with self._lock:
            topo = self.topological_sort()
            if not topo:
                return ([], 0.0)

            # Node weight: estimated_durations.get(node_id, 1.0) or 1.0
            def _weight(nid: str) -> float:
                if estimated_durations is not None:
                    return estimated_durations.get(nid, 1.0)
                return 1.0

            # Earliest start time and predecessor for backtracking
            earliest_start: Dict[str, float] = {nid: 0.0 for nid in topo}
            predecessor: Dict[str, Optional[str]] = {nid: None for nid in topo}

            for nid in topo:
                weight = _weight(nid)
                for dependent in self._downstream.get(nid, set()):
                    finish_time = earliest_start[nid] + weight
                    if finish_time > earliest_start[dependent]:
                        earliest_start[dependent] = finish_time
                        predecessor[dependent] = nid

            # Find node with maximum completion time
            end_node = max(topo, key=lambda nid: earliest_start[nid] + _weight(nid))
            total_weight = earliest_start[end_node] + _weight(end_node)

            # Backtrack from end_node to reconstruct critical path
            path: List[str] = []
            current: Optional[str] = end_node
            while current is not None:
                path.append(current)
                current = predecessor[current]
            path.reverse()

            return (path, total_weight)


# ── WaveScheduler Implementation ────────────────────────────────────────────

@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine.DAG).
    - Maintains scheduling state across _dag, _states mapping, and _lock.
    """

    tier: SystemTier = SystemTier("system")

    def __init__(self) -> None:
        self._dag: Any = None  # Resolved lazily via _resolve_dag()
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._lock = threading.Lock()

    def initialize(self) -> None:
        # Synchronize state by discovering registered nodes from _dag,
        # initializing root nodes to READY and non-root to PENDING
        self._sync_states()

    def _resolve_dag(self) -> dag_engine.DAG:
        from support.lib.lifecycle import get_singleton
        return cast(dag_engine.DAG, get_singleton(dag_engine.DAG))

    def _sync_states(self) -> None:
        """Synchronize _states with all nodes currently registered in _dag.all_nodes().
        Root nodes get READY, non-root nodes get PENDING.
        """
        dag = self._resolve_dag()
        all_nids = dag.all_nodes()
        roots = dag.find_roots()
        for nid in all_nids:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine.NodeState.READY
                else:
                    self._states[nid] = dag_engine.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        # POSTCONDITION: collect READY nodes whose upstream deps are all SUCCEEDED
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states()
            candidates = []
            for nid, state in self._states.items():
                if state != dag_engine.NodeState.READY:
                    continue
                deps = dag.get_dependencies(nid)
                if all(self._states.get(d) == dag_engine.NodeState.SUCCEEDED for d in deps):
                    candidates.append(nid)
            # Sort by priority descending, then node_id ascending
            candidates.sort(
                key=lambda nid: (-dag.get_node(nid).priority, nid)
            )
            return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # POSTCONDITION: update node state to RUNNING
        with self._lock:
            self._states[node_id] = dag_engine.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        # POSTCONDITION: mark SUCCEEDED, promote unblocked dependents to READY
        with self._lock:
            dag = self._resolve_dag()
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # Inspect downstream dependents
            dependents = dag.get_dependents(node_id)
            for dep_id in dependents:
                if self._states.get(dep_id) == dag_engine.NodeState.PENDING:
                    # Check if all upstream deps are SUCCEEDED
                    all_deps_succeeded = all(
                        self._states.get(d) == dag_engine.NodeState.SUCCEEDED
                        for d in dag.get_dependencies(dep_id)
                    )
                    if all_deps_succeeded:
                        self._states[dep_id] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
    ) -> None:
        # POSTCONDITION: mark FAILED, apply failure policy
        with self._lock:
            dag = self._resolve_dag()
            self._states[node_id] = dag_engine.NodeState.FAILED

            if failure_policy == dag_engine.FailurePolicy.FAIL_FAST:
                # Transition all remaining PENDING nodes to CANCELLED
                for nid in list(self._states.keys()):
                    if self._states[nid] in (dag_engine.NodeState.PENDING, dag_engine.NodeState.READY):
                        self._states[nid] = dag_engine.NodeState.CANCELLED
            elif failure_policy == dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # Traverse transitive downstream dependents and mark non-terminal as SKIPPED
                def _skip_transitive(start_nid: str) -> None:
                    stack = list(dag.get_dependents(start_nid))
                    while stack:
                        dep_id = stack.pop()
                        if self._states.get(dep_id) in (
                            dag_engine.NodeState.SUCCEEDED,
                            dag_engine.NodeState.FAILED,
                            dag_engine.NodeState.SKIPPED,
                            dag_engine.NodeState.CANCELLED,
                        ):
                            continue
                        self._states[dep_id] = dag_engine.NodeState.SKIPPED
                        stack.extend(dag.get_dependents(dep_id))
                _skip_transitive(node_id)
            elif failure_policy == dag_engine.FailurePolicy.CONTINUE_ON_ERROR:
                # Leave unblocked independent nodes eligible for execution
                pass

    @operation
    @override
    def is_finished(self) -> bool:
        # POSTCONDITION: synchronize states, check all nodes are terminal
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states()
            all_nodes = dag.all_nodes()
            if not all_nodes:
                return True
            terminal = {
                dag_engine.NodeState.SUCCEEDED,
                dag_engine.NodeState.FAILED,
                dag_engine.NodeState.SKIPPED,
                dag_engine.NodeState.CANCELLED,
            }
            return all(
                self._states.get(nid) in terminal
                for nid in all_nodes
            )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine.NodeState:
        # POSTCONDITION: return _states[node_id]
        with self._lock:
            return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        # POSTCONDITION: return shallow copy of _states
        with self._lock:
            return dict(self._states)


# ── DAGRunner Implementation ────────────────────────────────────────────────

@singleton_type("system")
class DAGRunner(dag_engine.DAGRunner):
    """Concrete realization of concurrent DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine.DAG) and WaveScheduler service via get_singleton(dag_engine.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, _cancelled event, and _results mapping.
    - Synchronizes runner state using threading.Lock.
    """

    tier: SystemTier = SystemTier("system")

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._lock = threading.Lock()

    def _resolve_dag(self) -> dag_engine.DAG:
        from support.lib.lifecycle import get_singleton
        return cast(dag_engine.DAG, get_singleton(dag_engine.DAG))

    def _resolve_scheduler(self) -> dag_engine.WaveScheduler:
        from support.lib.lifecycle import get_singleton
        return cast(dag_engine.WaveScheduler, get_singleton(dag_engine.WaveScheduler))

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        # Validate DAG before execution
        dag = self._resolve_dag()
        dag.validate()

        # Initialize scheduler and collect results
        scheduler = self._resolve_scheduler()
        results: Dict[str, dag_engine.NodeResult[Any]] = {}

        start_time = time.monotonic()
        from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FuturesTimeoutError

        # Check if already cancelled before starting (e.g. cancel() called before run())
        if self._cancelled.is_set():
            ws = cast(WaveScheduler, scheduler)
            ws._sync_states()
            with ws._lock:
                for nid in dag.all_nodes():
                    state = ws._states.get(nid)
                    if state in (dag_engine.NodeState.PENDING, dag_engine.NodeState.READY):
                        ws._states[nid] = dag_engine.NodeState.CANCELLED

        _early_exit = False
        _exit_due_to_timeout = False

        while not scheduler.is_finished():
            # Check cancellation
            if self._cancelled.is_set():
                # Mark pending nodes as CANCELLED
                ws = cast(WaveScheduler, scheduler)
                ws._sync_states()
                with ws._lock:
                    for nid in dag.all_nodes():
                        state = ws._states.get(nid)
                        if state in (dag_engine.NodeState.PENDING, dag_engine.NodeState.READY):
                            ws._states[nid] = dag_engine.NodeState.CANCELLED
                _early_exit = True
                break

            # Check timeout
            if timeout_seconds is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout_seconds:
                    _early_exit = True
                    _exit_due_to_timeout = True
                    break

            # Get next wave of ready nodes
            wave = scheduler.next_wave()
            if not wave:
                # If nothing is ready and not finished, we may have an issue
                # Check if all non-terminal nodes should be cancelled
                all_nids = dag.all_nodes()
                terminal_states = {
                    dag_engine.NodeState.SUCCEEDED,
                    dag_engine.NodeState.FAILED,
                    dag_engine.NodeState.SKIPPED,
                    dag_engine.NodeState.CANCELLED,
                }
                for nid in all_nids:
                    st = scheduler.get_state(nid)
                    if st not in terminal_states:
                        # Mark stuck non-terminal nodes as CANCELLED
                        ws = cast(WaveScheduler, scheduler)
                        ws._sync_states()
                        with ws._lock:
                            ws._states[nid] = dag_engine.NodeState.CANCELLED
                continue

            # Dispatch wave to ThreadPoolExecutor
            executor: Optional[ThreadPoolExecutor] = None
            futures: Dict[Future[Any], str] = {}
            try:
                executor = _DaemonThreadPoolExecutor(max_workers=max_concurrency)
                for nid in wave:
                    scheduler.mark_running(nid)
                    defn = dag.get_node(nid)

                    def _execute(defn=defn) -> Any:
                        return defn.action()

                    future = executor.submit(_execute)
                    futures[future] = nid

                for future in futures:
                    if self._cancelled.is_set():
                        future.cancel()
                        for other_future, other_nid in futures.items():
                            if other_future == future:
                                continue
                            other_future.cancel()
                            ws = cast(WaveScheduler, scheduler)
                            ws._sync_states()
                            with ws._lock:
                                ws._states[other_nid] = dag_engine.NodeState.CANCELLED
                            results[other_nid] = dag_engine.NodeResult(
                                node_id=other_nid,
                                state=dag_engine.NodeState.CANCELLED,
                            )
                        _early_exit = True
                        break

                    node_id = futures[future]

                    # Retry logic — resubmit action to executor on each attempt
                    result_defn = dag.get_node(node_id)
                    max_attempts = result_defn.retries + 1
                    attempt = 0
                    caught_exception: Optional[Exception] = None
                    node_start = time.monotonic()
                    value: Optional[Any] = None
                    cur_future: Future[Any] = future

                    def _make_execute(defn=result_defn) -> Callable[[], Any]:
                        def _action() -> Any:
                            return defn.action()
                        return _action

                    while attempt < max_attempts:
                        if self._cancelled.is_set():
                            cur_future.cancel()
                            # Mark current node (B) as CANCELLED
                            ws = cast(WaveScheduler, scheduler)
                            ws._sync_states()
                            with ws._lock:
                                ws._states[node_id] = dag_engine.NodeState.CANCELLED
                            results[node_id] = dag_engine.NodeResult(
                                node_id=node_id,
                                state=dag_engine.NodeState.CANCELLED,
                            )
                            # Cancel remaining futures in this wave
                            for remaining_fut, remaining_nid in futures.items():
                                if remaining_fut == cur_future:
                                    continue
                                remaining_fut.cancel()
                                ws = cast(WaveScheduler, scheduler)
                                ws._sync_states()
                                with ws._lock:
                                    ws._states[remaining_nid] = dag_engine.NodeState.CANCELLED
                                results[remaining_nid] = dag_engine.NodeResult(
                                    node_id=remaining_nid,
                                    state=dag_engine.NodeState.CANCELLED,
                                )
                            _early_exit = True
                            break
                        try:
                            # Compute remaining timeout for this future.result() call
                            if timeout_seconds is not None:
                                elapsed = time.monotonic() - start_time
                                remaining = max(0.0, timeout_seconds - elapsed)
                                if remaining <= 0:
                                    _early_exit = True
                                    _exit_due_to_timeout = True
                                    break
                                # Cap each result() call to a small interval so
                                # _cancelled is rechecked frequently (≤ 0.5 s)
                                # instead of blocking for the full remaining time.
                                result_timeout = min(remaining, 0.5)
                                value = cur_future.result(timeout=result_timeout)
                            else:
                                # No overall timeout; still use a bounded future.result()
                                # timeout so cancellation checks periodically interrupt
                                # blocking threads.  This way _cancelled.is_set() can
                                # wake us up instead of staying stuck in result().
                                value = cur_future.result(timeout=0.5)
                            caught_exception = None
                            break
                        except FuturesTimeoutError:
                            # Timeout expired during future.result(timeout=...)
                            # Check wall-clock to confirm before setting early_exit
                            elapsed = time.monotonic() - start_time
                            if timeout_seconds is not None and elapsed >= timeout_seconds:
                                _early_exit = True
                                _exit_due_to_timeout = True
                                break
                            else:
                                # Didn't actually exceed timeout yet; retry the action
                                attempt += 1
                                if attempt < max_attempts:
                                    time.sleep(0.01)
                                    cur_future = executor.submit(_make_execute())
                                else:
                                    if self._cancelled.is_set():
                                        _early_exit = True
                                        # Mark B as CANCELLED before breaking
                                        ws = cast(WaveScheduler, scheduler)
                                        ws._sync_states()
                                        with ws._lock:
                                            ws._states[node_id] = dag_engine.NodeState.CANCELLED
                                        results[node_id] = dag_engine.NodeResult(
                                            node_id=node_id,
                                            state=dag_engine.NodeState.CANCELLED,
                                        )
                                        break
                                    caught_exception = dag_engine.DAGTimeoutError()
                                    attempt = max_attempts
                        except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                            caught_exception = exc
                            attempt += 1
                            if attempt < max_attempts:
                                time.sleep(0.01)  # Brief backoff before retry
                                # Resubmit the action for the next attempt
                                cur_future = executor.submit(_make_execute())
                            else:
                                # Last attempt failed — will record as failure below
                                pass

                        if _early_exit:
                            break

                    if _early_exit:
                        break

                    duration = time.monotonic() - node_start
                    retries_attempted = attempt

                    if caught_exception is None:
                        # Success
                        results[node_id] = dag_engine.NodeResult(
                            node_id=node_id,
                            state=dag_engine.NodeState.SUCCEEDED,
                            value=value,
                            duration_seconds=duration,
                            retries_attempted=retries_attempted,
                        )
                        scheduler.mark_succeeded(node_id)
                    else:
                        # Failure after all retries
                        results[node_id] = dag_engine.NodeResult(
                            node_id=node_id,
                            state=dag_engine.NodeState.FAILED,
                            error=caught_exception,
                            duration_seconds=duration,
                            retries_attempted=retries_attempted,
                        )
                        scheduler.mark_failed(node_id, failure_policy)
            except dag_engine.DAGTimeoutError:
                # Prevent ThreadPoolExecutor.__exit__ from hanging on shutdown(wait=True)
                if executor is not None:
                    executor.shutdown(wait=False)
                    executor = None  # Avoid __del__ re-shutdown hanging on abandoned threads
                # Cancel any still-running futures
                for fut in futures:
                    fut.cancel()
                raise

            except dag_engine.DAGCancelledError:
                if executor is not None:
                    executor.shutdown(wait=False)
                    executor = None  # Avoid __del__ re-shutdown hanging on abandoned threads
                for fut in futures:
                    fut.cancel()
                _early_exit = True
            # Normal path — shut down executor properly
            if _early_exit:
                # Worker threads may still be running; use fast shutdown to avoid blocking
                if executor is not None:
                    executor.shutdown(wait=False)
                    executor = None
                if _exit_due_to_timeout:
                    raise dag_engine.DAGTimeoutError()
            elif executor is not None:
                executor.shutdown(wait=True)

        # Compute critical path
        critical_path_nodes, _ = dag.compute_critical_path()

        # Gather final state info
        all_states = scheduler.get_all_states()
        succeeded = tuple(
            nid for nid, st in all_states.items()
            if st == dag_engine.NodeState.SUCCEEDED
        )
        failed = tuple(
            nid for nid, st in all_states.items()
            if st == dag_engine.NodeState.FAILED
        )
        skipped = tuple(
            nid for nid, st in all_states.items()
            if st == dag_engine.NodeState.SKIPPED
        )
        cancelled = tuple(
            nid for nid, st in all_states.items()
            if st == dag_engine.NodeState.CANCELLED
        )

        wall_clock = time.monotonic() - start_time

        return dag_engine.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(critical_path_nodes),
            results=results,
        )

    @operation
    @override
    def cancel(self) -> None:
        # POSTCONDITION: set cancelled event, mark pending/ready nodes CANCELLED via scheduler
        self._cancelled.set()
        scheduler = self._resolve_scheduler()
        dag = self._resolve_dag()
        # Sync scheduler states first, then mark unstarted nodes as CANCELLED
        # Cast to concrete WaveScheduler to access internal _states/_lock
        ws = cast(WaveScheduler, scheduler)
        ws._sync_states()
        with ws._lock:
            for nid in dag.all_nodes():
                state = ws._states.get(nid)
                if state in (dag_engine.NodeState.PENDING, dag_engine.NodeState.READY):
                    ws._states[nid] = dag_engine.NodeState.CANCELLED


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine.DAG],
        tier=DAG.tier,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine.WaveScheduler],
        tier=WaveScheduler.tier,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine.DAGRunner],
        tier=DAGRunner.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T23:48:29Z
# LAST_CHANGED: 2026-10-22T23:43:11Z
# CHANGE: Fix: In the FuturesTimeoutError exhausted-retries handler, when _cancelled.is_set() is detected, mark B's node_id as CANCELLED in ws._states and record it in results before breaking. This ensures get_all_states() reports B as CANCELLED even when cancellation arrives after future.result(timeout=0.5) starts.
# QA_AUDIT: 2026-10-22T23:44:09Z
# FEEDBACK:
# - The implementation contains unreachable defensive code that cannot be exercised under the specification: (1) In DAG.add_edge, the initialization of default empty adjacency sets when the upstream or downstream adjacency key is absent is dead code because DAG.add_node already initializes these entries whenever a node is registered, making the lazy initialization in add_edge impossible to reach; annotate with pragma: no cover (assumption: add_node always initializes adjacency entries) or remove the dead code; (2) In DAG.remove_node, the defensive branch that discards the removed node identifier from a neighbor adjacency set only when the neighbor set contains it is unreachable because the graph invariants guaranteed by add_node and add_edge ensure bidirectional consistency, making the defensive discard branch dead code; annotate with pragma: no cover (assumption: graph consistency invariant maintained by add_node and add_edge) or remove the dead code; (3) In DAG.validate DFS cycle reconstruction, the break statement when the parent map lookup returns None is unreachable because the DFS traversal guarantees the current node has a parent entry when reconstructing a cycle path — annotate with pragma: no cover (assumption: DFS cycle reconstruction always finds valid parent) or remove the dead code.
# - The CHANGE header describes a fix in the FuturesTimeoutError exhausted-retries handler to mark a node as CANCELLED when cancellation arrives after future.result() starts, but this does not address the three unreachable defensive code spans that persist from the DAG class. Spans 1-2 in DAG.add_edge initialize default empty adjacency sets when the upstream or downstream adjacency key is absent — this is dead code because DAG.add_node already initializes these entries whenever a node is registered, making the lazy initialization in add_edge impossible to reach; annotate with pragma: no cover (assumption: add_node always initializes adjacency entries) or remove the dead code. Span 3 in DAG.validate DFS cycle reconstruction breaks when the parent map lookup returns None during cycle path assembly — this is unreachable because the DFS traversal guarantees the current node has a parent entry when reconstructing a cycle path; annotate with pragma: no cover (assumption: DFS cycle reconstruction always finds valid parent) or remove the dead code. Span 4 in DAG.remove_node discards a node identifier from a neighbor adjacency set only when the neighbor set contains it — this is unreachable because the graph invariants from add_node and add_edge ensure bidirectional consistency; annotate with pragma: no cover (assumption: graph consistency invariant maintained by add_node and add_edge) or remove the dead code.
# --- END CLEANROOM METADATA ---
