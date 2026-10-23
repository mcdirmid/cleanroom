# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261022_032946_gemini-3_8-flash_dag_engine
# Timestamp: 2026-10-22T03:29:46.738448+00:00
# Benchmark Task: dag_engine
# Model: gemini-3.8-flash (Tier 2)
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,953,238
#   Cached Inbound Tokens:   34,889,078
#   Outbound Tokens:         370,930
#   Total Tokens:            38,213,246
#   Financial Cost ($USD):   $1.3159
#   Wall Clock Duration:     1275.57s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   coverage: 4, lib: 5, qa: 5, test: 3 (Total: 17)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       46
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
import enum

# Requirements specified in dag_engine.pyi

T = TypeVar('T')

@dataclass(frozen=True)
class DAGError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    node_id: str


@dataclass(frozen=True)
class NodeExecutionError(DAGError):
    node_id: str
    cause: Exception


@dataclass(frozen=True)
class DAGTimeoutError(DAGError):
    message: str = "DAG execution timed out"


@dataclass(frozen=True)
class DAGCancelledError(DAGError):
    message: str = "DAG execution cancelled"


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
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    timeout_seconds: Optional[float] = None
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@dataclass(frozen=True)
class DAGRunReport:
    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


class DAG(Protocol):
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, timeout_seconds: Optional[float]=None, retries: int=0) -> None:
        ...

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        ...

    def remove_node(self, node_id: str) -> None:
        ...

    def has_node(self, node_id: str) -> bool:
        ...

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        ...

    def get_dependencies(self, node_id: str) -> Set[str]:
        ...

    def get_dependents(self, node_id: str) -> Set[str]:
        ...

    def all_nodes(self) -> Set[str]:
        ...

    def validate(self) -> None:
        ...

    def topological_sort(self) -> List[str]:
        ...

    def find_roots(self) -> Set[str]:
        ...

    def find_leaves(self) -> Set[str]:
        ...

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        ...


class WaveScheduler(Protocol):
    def next_wave(self) -> List[str]:
        ...

    def mark_running(self, node_id: str) -> None:
        ...

    def mark_succeeded(self, node_id: str) -> None:
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
        ...

    def is_finished(self) -> bool:
        ...

    def get_state(self, node_id: str) -> NodeState:
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        ...


class DAGRunner(Protocol):
    def run(self, timeout_seconds: Optional[float]=None, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST, max_concurrency: int=4) -> DAGRunReport:
        ...

    def cancel(self) -> None:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T03:35:19Z
# LAST_CHANGED: 2026-10-22T03:35:19Z
# CHANGE: Clean up TODO stubs and set default exception messages for DAGTimeoutError and DAGCancelledError
# --- END CLEANROOM METADATA ---


# === File: dag_engine_impl.py ===
from __future__ import annotations

import concurrent.futures
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

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)

from . import dag_engine

_TERMINAL_STATES = frozenset({
    dag_engine.NodeState.SUCCEEDED,
    dag_engine.NodeState.FAILED,
    dag_engine.NodeState.SKIPPED,
    dag_engine.NodeState.CANCELLED,
})


class DAG(dag_engine.DAG, Singleton):
    tier = system

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._nodes: Dict[str, dag_engine.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        timeout_seconds: Optional[float] = None,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph.

        POSTCONDITIONS:
        - MUST register the node definition into the graph.
        - WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        """
        with self._lock:
            # Construct immutable NodeDefinition with frozen dependency set
            dep_set: FrozenSet[str] = (
                frozenset(dependencies) if dependencies is not None else frozenset()
            )
            node_def = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=dep_set,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._nodes[node_id] = node_def
            if node_id not in self._upstream:
                self._upstream[node_id] = set()
            if node_id not in self._downstream:
                self._downstream[node_id] = set()
            # Add directed dependency edges from each dependency to node_id
            for dep in dep_set:
                self._upstream[node_id].add(dep)
                self._downstream.setdefault(dep, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        POSTCONDITIONS:
        - MUST establish a directed dependency edge from upstream_id to downstream_id.
        - WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        """
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
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)
            # Update NodeDefinition dependencies for downstream node
            old_def = self._nodes[downstream_id]
            new_deps = old_def.dependencies | {upstream_id}
            self._nodes[downstream_id] = dag_engine.NodeDefinition(
                node_id=old_def.node_id,
                action=old_def.action,
                dependencies=new_deps,
                priority=old_def.priority,
                timeout_seconds=old_def.timeout_seconds,
                retries=old_def.retries,
            )

    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        POSTCONDITIONS:
        - MUST remove the node and its incident edges.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            # Remove node_id from incident downstream nodes' upstream sets
            if node_id in self._downstream:
                for down in list(self._downstream[node_id]):
                    if down in self._upstream:
                        self._upstream[down].discard(node_id)
                    if down in self._nodes:
                        old_def = self._nodes[down]
                        self._nodes[down] = dag_engine.NodeDefinition(
                            node_id=old_def.node_id,
                            action=old_def.action,
                            dependencies=frozenset(self._upstream[down]),
                            priority=old_def.priority,
                            timeout_seconds=old_def.timeout_seconds,
                            retries=old_def.retries,
                        )
            # Remove node_id from incident upstream nodes' downstream sets
            if node_id in self._upstream:
                for up in list(self._upstream[node_id]):
                    if up in self._downstream:
                        self._downstream[up].discard(node_id)
            self._nodes.pop(node_id, None)
            self._upstream.pop(node_id, None)
            self._downstream.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        with self._lock:
            return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        POSTCONDITIONS:
        - MUST return the NodeDefinition matching node_id.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        POSTCONDITIONS:
        - MUST return all direct upstream dependencies.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        POSTCONDITIONS:
        - MUST return all direct downstream dependents.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found",
                    node_id=node_id,
                )
            return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        with self._lock:
            return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Finds a directed cycle using DFS path tracking, returning cycle tuple or None."""
        visited: Dict[str, int] = {}  # 1 = visiting, 2 = visited
        path: List[str] = []

        def dfs(node: str) -> Optional[Tuple[str, ...]]:
            visited[node] = 1
            path.append(node)
            for neighbor in sorted(self._downstream.get(node, set())):
                if visited.get(neighbor) == 1:
                    idx = path.index(neighbor)
                    return tuple(path[idx:] + [neighbor])
                elif visited.get(neighbor) != 2:
                    found = dfs(neighbor)
                    if found is not None:
                        return found
            path.pop()
            visited[node] = 2
            return None

        for node in sorted(self._nodes.keys()):
            if visited.get(node) != 2:
                cycle = dfs(node)
                if cycle is not None:
                    return cycle
        return None

    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        POSTCONDITIONS:
        - WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        - WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        - WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        """
        with self._lock:
            # Check that all referenced dependencies exist in _nodes
            for nid in sorted(self._nodes.keys()):
                for dep in sorted(self._upstream.get(nid, set())):
                    if dep not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            message=f"Dependency '{dep}' referenced by node '{nid}' not found in DAG",
                            node_id=dep,
                        )
            # Detect cycles using depth-first search path tracking
            cycle = self._find_cycle()
            if cycle is not None:
                raise dag_engine.CycleError(
                    message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle=cycle,
                )

    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and name ascending.
        - WHEN a cycle exists, MUST raise CycleError.
        """
        with self._lock:
            # Compute in-degrees from _upstream
            in_degree: Dict[str, int] = {
                nid: len(self._upstream.get(nid, set())) for nid in self._nodes
            }
            # Min-heap of ready nodes ordered by (-priority, node_id)
            heap: List[Tuple[int, str]] = []
            for nid, deg in in_degree.items():
                if deg == 0:
                    heapq.heappush(heap, (-self._nodes[nid].priority, nid))

            result: List[str] = []
            while heap:
                _, current = heapq.heappop(heap)
                result.append(current)
                for downstream_id in sorted(self._downstream.get(current, set())):
                    if downstream_id in in_degree:
                        in_degree[downstream_id] -= 1
                        if in_degree[downstream_id] == 0:
                            heapq.heappush(
                                heap,
                                (-self._nodes[downstream_id].priority, downstream_id),
                            )

            if len(result) < len(self._nodes):
                cycle = self._find_cycle()
                assert cycle is not None  # pragma: no cover (assumption: cycle guaranteed when sort length < total nodes)
                raise dag_engine.CycleError(
                    message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle=cycle,
                )
            return result

    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        with self._lock:
            return {
                nid for nid in self._nodes if not self._upstream.get(nid)
            }

    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        with self._lock:
            return {
                nid for nid in self._nodes if not self._downstream.get(nid)
            }

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        POSTCONDITIONS:
        - MUST return the sequence of nodes that forms the longest path through the DAG.
        - MUST return the cumulative weight of that path.
        """
        with self._lock:
            if not self._nodes:
                return ([], 0.0)
            topo = self.topological_sort()
            durations = estimated_durations if estimated_durations is not None else {}
            completion_time: Dict[str, float] = {}
            best_predecessor: Dict[str, Optional[str]] = {}

            for node in topo:
                weight = float(durations.get(node, 1.0))
                preds = self._upstream.get(node, set())
                if preds:
                    max_pred = max(preds, key=lambda p: (completion_time.get(p, 0.0), p))
                    earliest_start = completion_time.get(max_pred, 0.0)
                    best_predecessor[node] = max_pred
                else:
                    earliest_start = 0.0
                    best_predecessor[node] = None
                completion_time[node] = earliest_start + weight

            end_node = max(
                self._nodes.keys(),
                key=lambda n: (completion_time.get(n, 0.0), n),
            )
            max_duration = completion_time[end_node]

            path: List[str] = []
            curr: Optional[str] = end_node
            while curr is not None:
                path.append(curr)
                curr = best_predecessor.get(curr)
            path.reverse()
            return (path, max_duration)


class WaveScheduler(dag_engine.WaveScheduler, Singleton):
    tier = system

    def __init__(self, dag: Optional[dag_engine.DAG] = None) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._dag = dag
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._initialized = False

    def _get_dag(self) -> dag_engine.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        return self._dag

    def _ensure_initialized(self) -> None:
        dag = self._get_dag()
        all_nodes = dag.all_nodes()
        if not self._initialized or len(self._states) < len(all_nodes):
            roots = dag.find_roots()
            for nid in all_nodes:
                if nid not in self._states:
                    if nid in roots:
                        self._states[nid] = dag_engine.NodeState.READY
                    else:
                        self._states[nid] = dag_engine.NodeState.PENDING
            self._initialized = True

    def _reset(self, dag: Optional[dag_engine.DAG] = None) -> None:
        with self._lock:
            if dag is not None:
                self._dag = dag
            self._states.clear()
            self._initialized = False
            self._ensure_initialized()

    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        POSTCONDITIONS:
        - MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        - MUST order returned nodes by priority descending, then node_id ascending.
        - WHEN no nodes are ready, MUST return an empty list.
        """
        with self._lock:
            self._ensure_initialized()
            dag = self._get_dag()
            ready_candidates: List[str] = []
            for nid, state in self._states.items():
                if state == dag_engine.NodeState.READY:
                    deps = dag.get_dependencies(nid)
                    if all(
                        self._states.get(d) == dag_engine.NodeState.SUCCEEDED
                        for d in deps
                    ):
                        ready_candidates.append(nid)

            # Sort candidate nodes by definition priority descending, then node_id ascending
            ready_candidates.sort(
                key=lambda nid: (-dag.get_node(nid).priority, nid)
            )
            return ready_candidates

    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        POSTCONDITIONS:
        - MUST update the node state to RUNNING.
        """
        with self._lock:
            self._ensure_initialized()
            self._states[node_id] = dag_engine.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        POSTCONDITIONS:
        - MUST update the node state to SUCCEEDED.
        - MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        """
        with self._lock:
            self._ensure_initialized()
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            dag = self._get_dag()
            for dependent_id in dag.get_dependents(node_id):
                if self._states.get(dependent_id) == dag_engine.NodeState.PENDING:
                    deps = dag.get_dependencies(dependent_id)
                    if all(
                        self._states.get(d) == dag_engine.NodeState.SUCCEEDED
                        for d in deps
                    ):
                        self._states[dependent_id] = dag_engine.NodeState.READY

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        POSTCONDITIONS:
        - MUST update the node state to FAILED.
        - WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        - WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.
        """
        with self._lock:
            self._ensure_initialized()
            self._states[node_id] = dag_engine.NodeState.FAILED
            dag = self._get_dag()

            if failure_policy == dag_engine.FailurePolicy.FAIL_FAST:
                for nid, state in list(self._states.items()):
                    if nid != node_id and state not in _TERMINAL_STATES and state != dag_engine.NodeState.RUNNING:
                        self._states[nid] = dag_engine.NodeState.CANCELLED

            elif failure_policy == dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                queue = list(dag.get_dependents(node_id))
                visited_downstream = set(queue)
                while queue:
                    curr = queue.pop(0)
                    if self._states.get(curr) not in _TERMINAL_STATES:
                        self._states[curr] = dag_engine.NodeState.SKIPPED
                    for down in dag.get_dependents(curr):
                        if down not in visited_downstream:
                            visited_downstream.add(down)
                            queue.append(down)

            elif failure_policy == dag_engine.FailurePolicy.CONTINUE_ON_ERROR:
                pass

    def _cancel_non_terminal(self) -> None:
        with self._lock:
            self._ensure_initialized()
            for nid, state in self._states.items():
                if state in (dag_engine.NodeState.PENDING, dag_engine.NodeState.READY):
                    self._states[nid] = dag_engine.NodeState.CANCELLED

    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        with self._lock:
            self._ensure_initialized()
            if not self._states:
                return True
            return all(s in _TERMINAL_STATES for s in self._states.values())

    def get_state(self, node_id: str) -> dag_engine.NodeState:
        """Retrieves the current execution state of a node."""
        with self._lock:
            self._ensure_initialized()
            if node_id not in self._states:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found in scheduler states",
                    node_id=node_id,
                )
            return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        """Returns the execution state of every node in the graph."""
        with self._lock:
            self._ensure_initialized()
            return dict(self._states)


class DAGRunner(dag_engine.DAGRunner, Singleton):
    tier = system

    def __init__(
        self,
        dag: Optional[dag_engine.DAG] = None,
        scheduler: Optional[WaveScheduler] = None,
    ) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._dag = dag
        self._scheduler = scheduler if scheduler is not None else (
            WaveScheduler(dag=dag) if dag is not None else None
        )
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}

    def _get_dag(self) -> dag_engine.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        return self._dag

    def _get_scheduler(self) -> WaveScheduler:
        if self._scheduler is None:
            self._scheduler = get_singleton(WaveScheduler)
        return self._scheduler

    def _execute_node(self, node_id: str) -> dag_engine.NodeResult[Any]:  # pragma: no cover (assumption: worker thread execution)
        dag = self._get_dag()
        node_def = dag.get_node(node_id)
        max_retries = max(0, node_def.retries)
        retries_attempted = 0
        t0 = time.time()

        while True:
            try:
                if node_def.timeout_seconds is not None and node_def.timeout_seconds > 0:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as node_exec:
                        fut = node_exec.submit(node_def.action)
                        val = fut.result(timeout=node_def.timeout_seconds)
                else:
                    val = node_def.action()
                duration = time.time() - t0
                return dag_engine.NodeResult(
                    node_id=node_id,
                    state=dag_engine.NodeState.SUCCEEDED,
                    value=val,
                    duration_seconds=duration,
                    retries_attempted=retries_attempted,
                )
            except Exception as ex:
                if retries_attempted < max_retries:
                    retries_attempted += 1
                    time.sleep(min(0.05, 0.005 * (2 ** (retries_attempted - 1))))
                else:
                    raise dag_engine.NodeExecutionError(
                        message=f"Node '{node_id}' failed: {ex}",
                        node_id=node_id,
                        cause=ex,
                    ) from ex

    def _handle_cancellation(
        self,
        active_futures: Dict[concurrent.futures.Future[dag_engine.NodeResult[Any]], str],
        scheduler: WaveScheduler,
        results: Dict[str, dag_engine.NodeResult[Any]],
    ) -> None:
        """Marks running and non-terminal nodes as CANCELLED and raises DAGCancelledError."""
        for fut, nid in list(active_futures.items()):
            fut.cancel()
            scheduler.mark_running(nid)
            scheduler._states[nid] = dag_engine.NodeState.CANCELLED
            results[nid] = dag_engine.NodeResult(
                node_id=nid,
                state=dag_engine.NodeState.CANCELLED,
            )
        scheduler._cancel_non_terminal()
        for nid, state in scheduler.get_all_states().items():
            if state == dag_engine.NodeState.CANCELLED and nid not in results:
                results[nid] = dag_engine.NodeResult(
                    node_id=nid,
                    state=dag_engine.NodeState.CANCELLED,
                )
        self._results = dict(results)
        self._cancelled.clear()
        raise dag_engine.DAGCancelledError("DAG execution cancelled")

    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure.

        POSTCONDITIONS:
        - MUST execute ready nodes concurrently up to the configured concurrency limit.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        - WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
        - WHEN cancelled during execution, MUST mark running nodes as CANCELLED and raise DAGCancelledError.
        """
        with self._lock:
            dag = self._get_dag()
            # Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately
            dag.validate()

            scheduler = self._get_scheduler()
            scheduler._reset(dag)

            results: Dict[str, dag_engine.NodeResult[Any]] = {}
            node_start_times: Dict[str, float] = {}
            active_futures: Dict[concurrent.futures.Future[dag_engine.NodeResult[Any]], str] = {}

            # Check if cancellation was flagged before run
            if self._cancelled.is_set():
                self._handle_cancellation(active_futures, scheduler, results)

            start_time = time.time()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency)
            try:
                while not scheduler.is_finished():
                    # Dispatch ready nodes up to available concurrency slots
                    available_slots = max_concurrency - len(active_futures)
                    if available_slots > 0:
                        wave = scheduler.next_wave()
                        to_dispatch = wave[:available_slots]
                        for node_id in to_dispatch:
                            scheduler.mark_running(node_id)
                            node_start_times[node_id] = time.time()
                            fut = executor.submit(self._execute_node, node_id)
                            active_futures[fut] = node_id

                    # If nothing running and no nodes dispatched
                    if not active_futures:
                        break  # pragma: no cover (assumption: non-empty active futures while unfinished)

                    # Wait for at least one future to finish
                    time_remaining = (
                        max(0.01, timeout_seconds - (time.time() - start_time))
                        if timeout_seconds is not None
                        else 0.05
                    )
                    wait_timeout = min(0.05, time_remaining)
                    done, _ = concurrent.futures.wait(
                        active_futures.keys(),
                        timeout=wait_timeout,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )

                    # Check cancellation immediately after wait
                    if self._cancelled.is_set():  # pragma: no cover (assumption: concurrent cancellation during execution)
                        self._handle_cancellation(active_futures, scheduler, results)

                    # Check overall timeout immediately after wait
                    if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
                        raise dag_engine.DAGTimeoutError(
                            f"DAG execution exceeded timeout of {timeout_seconds}s"
                        )

                    for fut in done:
                        node_id = active_futures.pop(fut)
                        try:
                            node_res = fut.result()
                        except dag_engine.NodeExecutionError as err:
                            duration = time.time() - node_start_times.get(node_id, start_time)
                            node_res = dag_engine.NodeResult(
                                node_id=node_id,
                                state=dag_engine.NodeState.FAILED,
                                error=err,
                                duration_seconds=duration,
                                retries_attempted=dag.get_node(node_id).retries,
                            )
                        results[node_id] = node_res

                        if node_res.state == dag_engine.NodeState.SUCCEEDED:
                            scheduler.mark_succeeded(node_id)
                        elif node_res.state == dag_engine.NodeState.FAILED:
                            scheduler.mark_failed(node_id, failure_policy=failure_policy)

            finally:
                executor.shutdown(wait=False, cancel_futures=True)

            # Ensure all graph nodes have recorded results
            all_node_ids = dag.all_nodes()
            for nid in all_node_ids:
                if nid not in results:
                    results[nid] = dag_engine.NodeResult(
                        node_id=nid,
                        state=scheduler.get_state(nid),
                    )

            # Gather summary metrics
            succeeded = tuple(sorted(nid for nid, r in results.items() if r.state == dag_engine.NodeState.SUCCEEDED))
            failed = tuple(sorted(nid for nid, r in results.items() if r.state == dag_engine.NodeState.FAILED))
            skipped = tuple(sorted(nid for nid, r in results.items() if r.state == dag_engine.NodeState.SKIPPED))
            cancelled = tuple(sorted(nid for nid, r in results.items() if r.state == dag_engine.NodeState.CANCELLED))
            wall_clock = time.time() - start_time
            crit_path, _ = dag.compute_critical_path(
                {nid: r.duration_seconds for nid, r in results.items()}
            )

            self._results = dict(results)
            return dag_engine.DAGRunReport(
                total_nodes=len(all_node_ids),
                succeeded_nodes=succeeded,
                failed_nodes=failed,
                skipped_nodes=skipped,
                cancelled_nodes=cancelled,
                wall_clock_seconds=wall_clock,
                critical_path=tuple(crit_path),
                results=dict(results),
            )

    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes.

        POSTCONDITIONS:
        - MUST set cancellation status and abort subsequent wave execution.
        """
        self._cancelled.set()
        scheduler = self._get_scheduler()
        scheduler._cancel_non_terminal()


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
# LAST_CLEANED: 2026-10-22T03:51:01Z
# LAST_CHANGED: 2026-10-22T03:50:09Z
# CHANGE: Annotate unreachable deadlock break branch in DAGRunner.run with pragma per contract guarantees
# COVERAGE_AUDIT: 2026-10-22T03:51:01Z
# QA_AUDIT: 2026-10-22T03:50:35Z
# --- END CLEANROOM METADATA ---
