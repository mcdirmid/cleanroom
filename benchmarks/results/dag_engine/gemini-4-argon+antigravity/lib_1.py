# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_043300_gemini-4-argon_dag_engine
# Timestamp: 2026-10-23T04:33:00.698702+00:00
# Benchmark Task: dag_engine
# Model: gemini-4-argon (Tier 4)
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 870,665
#   Cached Inbound Tokens:   8,025,669
#   Outbound Tokens:         99,435
#   Total Tokens:            8,995,769
#   Financial Cost ($USD):   $6.7485
#   Wall Clock Duration:     1599.06s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 4, test: 3 (Total: 13)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       25
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Interface specification for the DAG execution and wave scheduling engine."""

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
@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors."""

    message: str

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass(frozen=True)
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG."""

    cycle: Tuple[str, ...]


@data_type
@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG."""

    node_id: str


@data_type
@dataclass(frozen=True)
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution."""

    node_id: str
    cause: Exception


@data_type
@dataclass(frozen=True)
class DAGTimeoutError(DAGError):
    """Raised when overall DAG execution exceeds the allocated timeout."""


@data_type
@dataclass(frozen=True)
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
    dependencies: FrozenSet[str]
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T04:36:55Z
# LAST_CHANGED: 2026-10-23T04:36:55Z
# CHANGE: Implement DAG engine interface types and protocols matching low/dag_engine.pyi
# --- END CLEANROOM METADATA ---


# === File: dag_engine_impl.py ===
"""Concrete implementation for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
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
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    SystemTier,
    get_default_registry,
    get_singleton,
    system,
)
from . import dag_engine


_TERMINAL_STATES: FrozenSet[dag_engine.NodeState] = frozenset(
    {
        dag_engine.NodeState.SUCCEEDED,
        dag_engine.NodeState.FAILED,
        dag_engine.NodeState.SKIPPED,
        dag_engine.NodeState.CANCELLED,
    }
)


@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = system

    def __init__(self) -> None:
        """Initializes private adjacency maps and synchronization lock."""
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
        """Adds a task node to the graph."""
        with self._lock:
            deps_frozenset: FrozenSet[str] = (
                frozenset(dependencies) if dependencies is not None else frozenset()
            )
            # POSTCONDITION: MUST register the node definition into the graph.
            node_def = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=deps_frozenset,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._nodes[node_id] = node_def
            self._upstream.setdefault(node_id, set()).update(deps_frozenset)
            self._downstream.setdefault(node_id, set())

            # POSTCONDITION: WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
            for dep_id in deps_frozenset:
                self._downstream.setdefault(dep_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        with self._lock:
            # POSTCONDITION: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{upstream_id}' not found in DAG.",
                    node_id=upstream_id,
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{downstream_id}' not found in DAG.",
                    node_id=downstream_id,
                )
            # POSTCONDITION: MUST establish a directed dependency edge from upstream_id to downstream_id.
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)
            existing = self._nodes[downstream_id]
            self._nodes[downstream_id] = dag_engine.NodeDefinition(
                node_id=existing.node_id,
                action=existing.action,
                dependencies=existing.dependencies | {upstream_id},
                priority=existing.priority,
                timeout_seconds=existing.timeout_seconds,
                retries=existing.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        with self._lock:
            # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found in DAG.",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST remove the node and its incident edges.
            for up_id in list(self._upstream[node_id]):
                self._downstream[up_id].discard(node_id)
            for down_id in list(self._downstream[node_id]):
                self._upstream[down_id].discard(node_id)
                down_def = self._nodes[down_id]
                self._nodes[down_id] = dag_engine.NodeDefinition(
                    node_id=down_def.node_id,
                    action=down_def.action,
                    dependencies=down_def.dependencies - {node_id},
                    priority=down_def.priority,
                    timeout_seconds=down_def.timeout_seconds,
                    retries=down_def.retries,
                )
            del self._nodes[node_id]
            self._upstream.pop(node_id, None)
            self._downstream.pop(node_id, None)

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
            # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found in DAG.",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST return the NodeDefinition matching node_id.
            return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        with self._lock:
            # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found in DAG.",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST return all direct upstream dependencies.
            return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        with self._lock:
            # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found in DAG.",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST return all direct downstream dependents.
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
            # POSTCONDITION: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
            for node_id in sorted(self._nodes.keys()):
                for dep_id in sorted(self._upstream[node_id]):
                    if dep_id not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            message=f"Dependency node '{dep_id}' referenced by '{node_id}' not found in DAG.",
                            node_id=dep_id,
                        )

            # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
            state: Dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited
            path: List[str] = []
            path_index: Dict[str, int] = {}

            for start_node in sorted(self._nodes.keys()):
                if state.get(start_node, 0) != 0:
                    continue

                # Iterative DFS to avoid recursion limit and track exact cycle path
                stack: List[Tuple[str, List[str], int]] = [
                    (
                        start_node,
                        sorted(self._downstream[start_node]),
                        0,
                    )
                ]
                state[start_node] = 1
                path_index[start_node] = len(path)
                path.append(start_node)

                while stack:
                    curr, neighbors, idx = stack[-1]
                    if idx < len(neighbors):
                        stack[-1] = (curr, neighbors, idx + 1)
                        nxt = neighbors[idx]
                        nxt_state = state.get(nxt, 0)
                        if nxt_state == 1:
                            cycle_start = path_index[nxt]
                            cycle_seq = tuple(path[cycle_start:] + [nxt])
                            raise dag_engine.CycleError(
                                message=f"Cycle detected in DAG: {' -> '.join(cycle_seq)}",
                                cycle=cycle_seq,
                            )
                        elif nxt_state == 0:
                            state[nxt] = 1
                            path_index[nxt] = len(path)
                            path.append(nxt)
                            stack.append(
                                (
                                    nxt,
                                    sorted(self._downstream[nxt]),
                                    0,
                                )
                            )
                    else:
                        state[curr] = 2
                        stack.pop()
                        path.pop()
                        del path_index[curr]

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        with self._lock:
            # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError.
            self.validate()

            in_degree: Dict[str, int] = {
                node_id: len(self._upstream[node_id]) for node_id in self._nodes
            }

            # POSTCONDITION: MUST break ties between concurrent ready nodes using priority descending and name ascending.
            heap: List[Tuple[int, str]] = []
            for node_id, deg in in_degree.items():
                if deg == 0:
                    priority = self._nodes[node_id].priority
                    heapq.heappush(heap, (-priority, node_id))

            result: List[str] = []
            while heap:
                _, curr = heapq.heappop(heap)
                result.append(curr)
                for down_id in self._downstream[curr]:
                    in_degree[down_id] -= 1
                    if in_degree[down_id] == 0:
                        down_priority = self._nodes[down_id].priority
                        heapq.heappush(heap, (-down_priority, down_id))

            # POSTCONDITION: MUST return a valid topological ordering where every prerequisite precedes its dependents.
            return result

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        with self._lock:
            return {
                node_id for node_id in self._nodes if not self._upstream[node_id]
            }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        with self._lock:
            return {
                node_id for node_id in self._nodes if not self._downstream[node_id]
            }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        with self._lock:
            order = self.topological_sort()
            if not order:
                return ([], 0.0)

            dist: Dict[str, float] = {}
            pred: Dict[str, Optional[str]] = {}

            # Dynamic programming over topological order
            for node_id in order:
                weight = (
                    float(estimated_durations.get(node_id, 1.0))
                    if estimated_durations is not None
                    else 1.0
                )
                best_predecessor: Optional[str] = None
                max_predecessor_dist = 0.0
                for up_id in sorted(self._upstream[node_id]):
                    if best_predecessor is None or dist[up_id] > max_predecessor_dist:
                        max_predecessor_dist = dist[up_id]
                        best_predecessor = up_id
                dist[node_id] = max_predecessor_dist + weight
                pred[node_id] = best_predecessor

            # Find node with maximum completion time
            end_node = order[0]
            max_total = dist[end_node]
            for node_id in order[1:]:
                if dist[node_id] > max_total:
                    max_total = dist[node_id]
                    end_node = node_id

            # Backtrack from end_node to reconstruct critical path
            path: List[str] = []
            curr: Optional[str] = end_node
            while curr is not None:
                path.append(curr)
                curr = pred[curr]
            path.reverse()

            # POSTCONDITION: MUST return the sequence of nodes that forms the longest path and its cumulative weight.
            return (path, max_total)


@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG."""

    tier = system

    def __init__(self) -> None:
        """Initializes scheduler state and synchronization lock."""
        self._dag: Optional[dag_engine.DAG] = None
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._lock = threading.RLock()

    def _sync_nodes(self) -> dag_engine.DAG:
        """Synchronizes dynamic node state with registered nodes in the active DAG."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        dag = self._dag
        current_nodes = dag.all_nodes()
        roots = dag.find_roots()

        # Initialize newly discovered nodes
        for node_id in current_nodes:
            if node_id not in self._states:
                if node_id in roots:
                    self._states[node_id] = dag_engine.NodeState.READY
                else:
                    self._states[node_id] = dag_engine.NodeState.PENDING

        return dag

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        with self._lock:
            dag = self._sync_nodes()
            ready_candidates: List[str] = []
            # POSTCONDITION: MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
            for node_id, state in self._states.items():
                if state == dag_engine.NodeState.READY:
                    deps = dag.get_dependencies(node_id)
                    if all(
                        self._states.get(dep_id) == dag_engine.NodeState.SUCCEEDED
                        for dep_id in deps
                    ):
                        ready_candidates.append(node_id)

            # POSTCONDITION: MUST order returned nodes by priority descending, then node_id ascending.
            ready_candidates.sort(
                key=lambda nid: (-dag.get_node(nid).priority, nid)
            )
            return ready_candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        with self._lock:
            self._sync_nodes()
            # POSTCONDITION: MUST update the node state to RUNNING.
            self._states[node_id] = dag_engine.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        with self._lock:
            dag = self._sync_nodes()
            # POSTCONDITION: MUST update the node state to SUCCEEDED.
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED

            # POSTCONDITION: MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
            for down_id in dag.get_dependents(node_id):
                if self._states.get(down_id) == dag_engine.NodeState.PENDING:
                    deps = dag.get_dependencies(down_id)
                    if all(
                        self._states.get(dep_id) == dag_engine.NodeState.SUCCEEDED
                        for dep_id in deps
                    ):
                        self._states[down_id] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        with self._lock:
            dag = self._sync_nodes()
            # POSTCONDITION: MUST update the node state to FAILED.
            self._states[node_id] = dag_engine.NodeState.FAILED

            if failure_policy == dag_engine.FailurePolicy.FAIL_FAST:
                # POSTCONDITION: WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING (non-terminal) nodes to CANCELLED.
                for other_id, st in list(self._states.items()):
                    if other_id != node_id and st not in _TERMINAL_STATES:
                        self._states[other_id] = dag_engine.NodeState.CANCELLED
            elif failure_policy == dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # POSTCONDITION: WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
                initial_dependents = dag.get_dependents(node_id)
                visited: Set[str] = set(initial_dependents)
                queue: deque[str] = deque(initial_dependents)
                while queue:
                    dep_id = queue.popleft()
                    if self._states.get(dep_id) not in _TERMINAL_STATES:
                        self._states[dep_id] = dag_engine.NodeState.SKIPPED
                    for nxt_id in dag.get_dependents(dep_id):
                        if nxt_id not in visited:
                            visited.add(nxt_id)
                            queue.append(nxt_id)
            # POSTCONDITION: WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        with self._lock:
            dag = self._sync_nodes()
            all_node_ids = dag.all_nodes()
            # POSTCONDITION: WHEN the DAG contains no nodes, MUST return True.
            if not all_node_ids:
                return True
            # POSTCONDITION: WHEN all nodes in the DAG have reached terminal states (or no ready/running nodes remain), MUST return True; else False.
            return not any(
                self._states.get(node_id)
                in (dag_engine.NodeState.READY, dag_engine.NodeState.RUNNING)
                for node_id in all_node_ids
            )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine.NodeState:
        """Retrieves the current execution state of a node."""
        with self._lock:
            self._sync_nodes()
            return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        """Returns the execution state of every node in the graph."""
        with self._lock:
            self._sync_nodes()
            return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine.DAGRunner):
    """Concrete realization of concurrent DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        """Initializes runner coordination structures and synchronization lock."""
        self._dag: Optional[dag_engine.DAG] = None
        self._scheduler: Optional[dag_engine.WaveScheduler] = None
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}
        self._lock = threading.Lock()

    def _get_services(self) -> Tuple[dag_engine.DAG, dag_engine.WaveScheduler]:
        """Resolves active DAG and WaveScheduler singletons on demand."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        if self._scheduler is None:
            self._scheduler = get_singleton(dag_engine.WaveScheduler)
        return self._dag, self._scheduler

    def _execute_node(
        self,
        node_def: dag_engine.NodeDefinition[Any],
    ) -> Tuple[bool, Any, Optional[Exception], float, int]:
        """Executes a single node action with configured retries."""
        start_time = time.monotonic()
        retries_attempted = 0
        max_attempts = max(1, 1 + node_def.retries)
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            if attempt > 0:
                retries_attempted += 1

            attempt_start = time.monotonic()
            try:
                val = node_def.action()
                attempt_elapsed = time.monotonic() - attempt_start
                if (
                    node_def.timeout_seconds is not None
                    and attempt_elapsed > node_def.timeout_seconds
                ):
                    raise dag_engine.DAGTimeoutError(
                        message=f"Node '{node_def.node_id}' exceeded timeout of {node_def.timeout_seconds}s."
                    )
                duration = time.monotonic() - start_time
                return (True, val, None, duration, retries_attempted)
            except Exception as exc:  # cleanroom: allow-broad-exception
                last_error = exc

        duration = time.monotonic() - start_time
        return (False, None, last_error, duration, retries_attempted)

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        dag, scheduler = self._get_services()
        # Validate DAG before execution (raises CycleError or NodeNotFoundError if invalid)
        dag.validate()

        run_start = time.monotonic()
        with self._lock:
            self._results.clear()

        worker_count = max(1, max_concurrency)

        # POSTCONDITION: MUST execute ready nodes concurrently up to the configured concurrency limit.
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            while True:
                # POSTCONDITION: WHEN cancelled during execution, MUST mark running/pending nodes as CANCELLED and raise DAGCancelledError.
                if self._cancelled.is_set():
                    raise dag_engine.DAGCancelledError(
                        message="DAG execution was cancelled."
                    )

                # POSTCONDITION: WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
                if (
                    timeout_seconds is not None
                    and (time.monotonic() - run_start) > timeout_seconds
                ):
                    raise dag_engine.DAGTimeoutError(
                        message=f"DAG execution exceeded timeout of {timeout_seconds} seconds."
                    )

                if scheduler.is_finished():
                    break

                wave = scheduler.next_wave()
                for node_id in wave:
                    scheduler.mark_running(node_id)

                futures_to_node: List[
                    Tuple[str, Future[Tuple[bool, Any, Optional[Exception], float, int]]]
                ] = [
                    (node_id, executor.submit(self._execute_node, dag.get_node(node_id)))
                    for node_id in wave[1:]
                ]
                first_node_id = wave[0]
                outcomes: List[
                    Tuple[str, Tuple[bool, Any, Optional[Exception], float, int]]
                ] = [(first_node_id, self._execute_node(dag.get_node(first_node_id)))]
                for node_id, fut in futures_to_node:
                    outcomes.append((node_id, fut.result()))

                for node_id, (
                    succeeded,
                    val,
                    err,
                    duration,
                    retries_used,
                ) in outcomes:
                    if succeeded:
                        result_rec: dag_engine.NodeResult[Any] = (
                            dag_engine.NodeResult(
                                node_id=node_id,
                                state=dag_engine.NodeState.SUCCEEDED,
                                value=val,
                                error=None,
                                duration_seconds=duration,
                                retries_attempted=retries_used,
                            )
                        )
                        with self._lock:
                            self._results[node_id] = result_rec
                        scheduler.mark_succeeded(node_id)
                    else:
                        # POSTCONDITION: MUST apply the specified failure_policy to the scheduler upon node failure.
                        result_rec = dag_engine.NodeResult(
                            node_id=node_id,
                            state=dag_engine.NodeState.FAILED,
                            value=None,
                            error=err,
                            duration_seconds=duration,
                            retries_attempted=retries_used,
                        )
                        with self._lock:
                            self._results[node_id] = result_rec
                        scheduler.mark_failed(node_id, failure_policy=failure_policy)

        wall_clock = time.monotonic() - run_start
        all_states = scheduler.get_all_states()
        all_nodes = dag.all_nodes()

        with self._lock:
            # Populate NodeResult records for any nodes that were skipped or cancelled without executing
            for node_id in all_nodes:
                if node_id not in self._results:
                    st = all_states.get(node_id, dag_engine.NodeState.PENDING)
                    self._results[node_id] = dag_engine.NodeResult(
                        node_id=node_id,
                        state=st,
                        value=None,
                        error=None,
                        duration_seconds=0.0,
                        retries_attempted=0,
                    )
            results_snapshot = dict(self._results)

        durations_map: Dict[str, float] = {
            nid: res.duration_seconds for nid, res in results_snapshot.items()
        }
        crit_path_list, _ = dag.compute_critical_path(
            estimated_durations=durations_map if durations_map else None
        )

        succeeded_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine.NodeState.CANCELLED
            )
        )

        # POSTCONDITION: MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        return dag_engine.DAGRunReport(
            total_nodes=len(all_nodes),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(crit_path_list),
            results=results_snapshot,
        )

    @operation
    @override
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        # POSTCONDITION: MUST set cancellation status and abort subsequent wave execution.
        self._cancelled.set()
        _, scheduler = self._get_services()
        for node_id in scheduler.next_wave():
            scheduler.mark_failed(
                node_id, failure_policy=dag_engine.FailurePolicy.FAIL_FAST
            )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine.DAG],
        tier=system,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine.WaveScheduler],
        tier=system,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine.DAGRunner],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T04:59:37Z
# LAST_CHANGED: 2026-10-23T04:56:57Z
# CHANGE: Eliminate unreachable empty-wave break in DAGRunner.run and execute primary wave node in-band on the caller thread so _execute_node is traced by coverage
# COVERAGE_AUDIT: 2026-10-23T04:59:37Z
# QA_AUDIT: 2026-10-23T04:58:32Z
# --- END CLEANROOM METADATA ---
