# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_164035_deepseek-flash_dag_engine_pretense
# Timestamp: 2026-11-08T16:40:35.669312+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 421,785
#   Cached Inbound Tokens:   52,058,112
#   Outbound Tokens:         424,749
#   Total Tokens:            52,904,646
#   Financial Cost ($USD):   $0.4743
#   Wall Clock Duration:     3331.88s
#   Step Latencies (s):      [277.3, 877.3, 83.4, 91.5, 124.1, 216.1, 165.0, 81.4, 10.0, 228.0, 63.4, 297.9, 185.3, 114.2, 112.0, 114.4, 101.7, 81.3, 103.9, 71.2, 20.2, 114.1, 93.9, 50.8, 53.2, 20.3, 10.1]
#   Role Execution Rounds:   lib: 6, pretense: 7, pretense_coverage: 3, pretense_qa: 11 (Total: 27)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.lifecycle import Singleton, SystemTier
from pretense.parts.pretense.lib.pretense import test_only
import enum

# Requirements specified in dag_engine.pyi

T = TypeVar('T')


class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]

    def __init__(self, message: str, cycle: Tuple[str, ...]) -> None:
        super().__init__(message)
        self.cycle = cycle


class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str

    def __init__(self, message: str, node_id: str) -> None:
        super().__init__(message)
        self.node_id = node_id


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
        super().__init__(message)
        self.node_id = node_id
        self.cause = cause


class DAGTimeoutError(DAGError):
    """Raised when overall DAG execution exceeds the allocated timeout."""


class DAGCancelledError(DAGError):
    """Raised when DAG execution is explicitly cancelled."""


class NodeState(enum.Enum):
    """Execution lifecycle state of a graph node."""
    PENDING = 'pending'
    READY = 'ready'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    SKIPPED = 'skipped'


class FailurePolicy(enum.Enum):
    """Policy governing graph execution when a node action fails."""
    FAIL_FAST = 'fail_fast'
    CONTINUE_ON_ERROR = 'continue_on_error'
    SKIP_DOWNSTREAM = 'skip_downstream'


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


class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, timeout_seconds: Optional[float], retries: int) -> None:
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

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into executable waves of concurrency."""

    def next_wave(self) -> List[str]:
        ...

    def mark_running(self, node_id: str) -> None:
        ...

    def mark_succeeded(self, node_id: str) -> None:
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        ...

    def is_finished(self) -> bool:
        ...

    def get_state(self, node_id: str) -> NodeState:
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG under concurrency limits, failure policies, and timeouts."""

    def run(self, timeout_seconds: Optional[float], failure_policy: FailurePolicy, max_concurrency: int) -> DAGRunReport:
        ...

    def cancel(self) -> None:
        ...

    @test_only
    def is_cancelled(self) -> bool:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:45:18Z
# LAST_CHANGED: 2026-11-08T16:45:18Z
# CHANGE: Initialize DAG engine interface module from low spec: implement exception classes with message/cycle/node_id/cause fields and __str__, enums, frozen domain dataclasses, and DAG/WaveScheduler/DAGRunner protocols; use package-qualified pretense import for test_only.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine
from pretense.parts.pretense.lib.pretense import test_only
import heapq
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# Requirements specified in dag_engine_impl.pyi

_TERMINAL_STATES = frozenset({
    dag_engine.NodeState.SUCCEEDED,
    dag_engine.NodeState.FAILED,
    dag_engine.NodeState.SKIPPED,
    dag_engine.NodeState.CANCELLED,
})


class DAG(dag_engine.DAG):
    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}
        self._incarnations: Dict[str, int] = {}
        self._next_incarnation = 0
        self._lock = threading.RLock()

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, timeout_seconds: Optional[float], retries: int) -> None:
        with self._lock:
            # POSTCONDITION register_definition: store the immutable node definition.
            if node_id not in self._incarnations:
                # A registration that never left the graph keeps its incarnation token;
                # only a node that ceased to be registered starts a new incarnation.
                self._incarnations[node_id] = self._next_incarnation
                self._next_incarnation += 1
            dependency_set: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
            definition = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=dependency_set,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._nodes[node_id] = definition
            self._upstream.setdefault(node_id, set())
            self._downstream.setdefault(node_id, set())
            # POSTCONDITION directed_dependencies: add an edge from each dependency to node_id.
            for dependency in dependency_set:
                self._upstream[node_id].add(dependency)
                self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        with self._lock:
            # PRECONDITION nodes_must_exist: both endpoints must already be registered.
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Upstream node '{upstream_id}' does not exist",
                    upstream_id,
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Downstream node '{downstream_id}' does not exist",
                    downstream_id,
                )
            # POSTCONDITION directed_edge: establish the directed dependency edge.
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            # PRECONDITION node_must_exist: the node must be present.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist",
                    node_id,
                )
            # POSTCONDITION purge_incident_edges: drop all incident dependency edges.
            for dependency in self._upstream.get(node_id, set()):
                self._downstream.get(dependency, set()).discard(node_id)
            for dependent in self._downstream.get(node_id, set()):
                self._upstream.get(dependent, set()).discard(node_id)
            self._nodes.pop(node_id, None)
            self._upstream.pop(node_id, None)
            self._downstream.pop(node_id, None)
            self._incarnations.pop(node_id, None)

    def _node_incarnation(self, node_id: str) -> int:
        with self._lock:
            return self._incarnations[node_id]

    def has_node(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        with self._lock:
            # PRECONDITION node_must_exist: raise when the node is absent.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist",
                    node_id,
                )
            # POSTCONDITION return_definition: return the stored definition.
            return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist",
                    node_id,
                )
            # POSTCONDITION return_upstream: return a defensive copy of upstream dependencies.
            return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' does not exist",
                    node_id,
                )
            # POSTCONDITION return_downstream: return a defensive copy of downstream dependents.
            return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        with self._lock:
            return set(self._nodes)

    def validate(self) -> None:
        with self._lock:
            # PRECONDITION dependencies_exist: every referenced dependency must be registered.
            for node_id in self._nodes:
                for dependency in self._upstream.get(node_id, set()):
                    if dependency not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            f"Node '{node_id}' depends on missing node '{dependency}'",
                            dependency,
                        )
            # PRECONDITION acyclic_graph: raise CycleError when a directed cycle exists.
            cycle = self._detect_cycle()
            if cycle is not None:
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle,
                )
            # POSTCONDITION complete_valid: a consistent acyclic graph returns silently.

    def topological_sort(self) -> List[str]:
        with self._lock:
            # In-degree over upstream edges; ready nodes ordered by priority then name.
            in_degree: Dict[str, int] = {
                node_id: len(self._upstream.get(node_id, set()))
                for node_id in self._nodes
            }
            heap: List[Tuple[int, str]] = [
                (-self._nodes[node_id].priority, node_id)
                for node_id in self._nodes
                if in_degree[node_id] == 0
            ]
            heapq.heapify(heap)
            ordered: List[str] = []
            while heap:
                _neg_priority, node_id = heapq.heappop(heap)
                ordered.append(node_id)
                for dependent in self._downstream.get(node_id, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        heapq.heappush(
                            heap,
                            (-self._nodes[dependent].priority, dependent),
                        )
            # POSTCONDITION dependency_order: every prerequisite precedes its dependents.
            if len(ordered) < len(self._nodes):
                cycle = self._detect_cycle()
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle or ())}",
                    cycle or (),
                )
            return ordered

    def find_roots(self) -> Set[str]:
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._upstream.get(node_id, set())
            }

    def find_leaves(self) -> Set[str]:
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._downstream.get(node_id, set())
            }

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        with self._lock:
            ordered = self.topological_sort()
            if not ordered:
                return [], 0.0
            weights: Dict[str, float] = {
                node_id: (
                    estimated_durations.get(node_id, 1.0)
                    if estimated_durations is not None
                    else 1.0
                )
                for node_id in ordered
            }
            # Dynamic programming over the topological order.
            best: Dict[str, float] = {node_id: weights[node_id] for node_id in ordered}
            predecessor: Dict[str, Optional[str]] = {node_id: None for node_id in ordered}
            for node_id in ordered:
                for dependent in self._downstream.get(node_id, set()):
                    candidate = best[node_id] + weights[dependent]
                    if candidate > best[dependent]:
                        best[dependent] = candidate
                        predecessor[dependent] = node_id
            # Backtrack from the node with the maximum completion weight.
            end_node = ordered[0]
            for node_id in ordered:
                if best[node_id] > best[end_node] or (
                    best[node_id] == best[end_node] and node_id < end_node
                ):
                    end_node = node_id
            path: List[str] = []
            cursor: Optional[str] = end_node
            while cursor is not None:
                path.append(cursor)
                cursor = predecessor[cursor]
            path.reverse()
            # POSTCONDITIONS longest_path / cumulative_weight.
            return path, best[end_node]

    def _detect_cycle(self) -> Optional[Tuple[str, ...]]:
        color: Dict[str, int] = {node_id: 0 for node_id in self._nodes}
        stack: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            color[node_id] = 1
            stack.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                if color[dependency] == 1:
                    start = stack.index(dependency)
                    return tuple(stack[start:])
                if color[dependency] == 0:
                    found = visit(dependency)
                    if found is not None:
                        return found
            stack.pop()
            color[node_id] = 2
            return None

        for node_id in sorted(self._nodes):
            if color[node_id] == 0:
                found = visit(node_id)
                if found is not None:
                    return found
        return None


class WaveScheduler(dag_engine.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._dag = cast(DAG, get_singleton(dag_engine.DAG))
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._incarnations: Dict[str, int] = {}
        self._lock = threading.RLock()

    def next_wave(self) -> List[str]:
        with self._lock:
            self._sync_states()
            ready: List[str] = []
            for node_id, state in self._states.items():
                if state is not dag_engine.NodeState.READY:
                    continue
                dependencies = self._dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    ready.append(node_id)
            # POSTCONDITION priority_order: priority descending, then node_id ascending.
            ready.sort(key=lambda candidate: (-self._dag.get_node(candidate).priority, candidate))
            # POSTCONDITION empty_when_no_ready: an empty list when nothing is ready.
            return ready

    def mark_running(self, node_id: str) -> None:
        with self._lock:
            # Reconcile so the current registration is recorded before transitioning.
            self._sync_states()
            # POSTCONDITION state_transition: RUNNING.
            self._states[node_id] = dag_engine.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        with self._lock:
            # Reconcile with every node registered in the DAG before unlocking dependents.
            self._sync_states()
            # POSTCONDITION state_transition: SUCCEEDED.
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # POSTCONDITION promote_dependents: unblock newly satisfiable dependents.
            for dependent in self._dag.get_dependents(node_id):
                if self._states.get(dependent) is not dag_engine.NodeState.PENDING:
                    continue
                dependencies = self._dag.get_dependencies(dependent)
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    self._states[dependent] = dag_engine.NodeState.READY

    def mark_failed(self, node_id: str, failure_policy: dag_engine.FailurePolicy) -> None:
        with self._lock:
            # Reconcile with every node registered in the DAG so policy effects are total.
            self._sync_states()
            # POSTCONDITION state_transition: FAILED.
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy is dag_engine.FailurePolicy.FAIL_FAST:
                # POSTCONDITION fail_fast: cancel every remaining non-terminal node.
                for other_id, state in self._states.items():
                    if state not in _TERMINAL_STATES:
                        self._states[other_id] = dag_engine.NodeState.CANCELLED
            elif failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # POSTCONDITION skip_downstream: skip all transitive dependents.
                pending: List[str] = list(self._dag.get_dependents(node_id))
                visited: Set[str] = set()
                while pending:
                    dependent = pending.pop()
                    if dependent in visited:
                        continue
                    visited.add(dependent)
                    if self._states.get(dependent) not in _TERMINAL_STATES:
                        self._states[dependent] = dag_engine.NodeState.SKIPPED
                    pending.extend(self._dag.get_dependents(dependent))
            # POSTCONDITION continue_on_error: independent nodes remain eligible.

    def is_finished(self) -> bool:
        with self._lock:
            self._sync_states()
            # POSTCONDITIONS all_terminal / empty_dag / non_terminal_remaining.
            return all(state in _TERMINAL_STATES for state in self._states.values())

    def get_state(self, node_id: str) -> dag_engine.NodeState:
        with self._lock:
            # Reconcile with the DAG's registered nodes before reporting a state.
            self._sync_states()
            return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        with self._lock:
            # Reconcile with the DAG's registered nodes before reporting states.
            self._sync_states()
            return dict(self._states)

    def _sync_states(self) -> None:
        present = self._dag.all_nodes()
        for node_id in list(self._states):
            if node_id not in present:
                del self._states[node_id]
        for node_id in list(self._incarnations):
            if node_id not in present:
                del self._incarnations[node_id]
        for node_id in present:
            incarnation = self._dag._node_incarnation(node_id)
            dependencies = self._dag.get_dependencies(node_id)
            satisfied = all(
                self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                for dependency in dependencies
            )
            if self._incarnations.get(node_id) != incarnation:
                # Only a node that ceased to be registered starts a fresh incarnation
                # with no execution history; in-place definition replacement preserves it.
                self._incarnations[node_id] = incarnation
                state: Optional[dag_engine.NodeState] = None
            else:
                state = self._states.get(node_id)
            if state is None:
                # Newly visible node: READY only when every prerequisite is satisfied.
                self._states[node_id] = (
                    dag_engine.NodeState.READY
                    if satisfied
                    else dag_engine.NodeState.PENDING
                )
            elif state is dag_engine.NodeState.READY and not satisfied:
                # A new edge introduced an unsatisfied prerequisite for a cached node.
                self._states[node_id] = dag_engine.NodeState.PENDING
            elif state is dag_engine.NodeState.PENDING and satisfied:
                # Every prerequisite completed before this node was observed.
                self._states[node_id] = dag_engine.NodeState.READY

    def _cancel_non_terminal(self) -> None:
        with self._lock:
            self._sync_states()
            for other_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine.NodeState.CANCELLED


class DAGRunner(dag_engine.DAGRunner):
    tier = system

    def __init__(self) -> None:
        self._dag = get_singleton(dag_engine.DAG)
        self._scheduler = cast(WaveScheduler, get_singleton(dag_engine.WaveScheduler))
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}
        self._lock = threading.Lock()

    def run(self, timeout_seconds: Optional[float], failure_policy: dag_engine.FailurePolicy, max_concurrency: int) -> dag_engine.DAGRunReport:
        # Validate first so missing dependencies and cycles surface immediately.
        self._dag.validate()
        start_time = time.monotonic()
        with self._lock:
            self._results = {}
        workers = max(1, max_concurrency)
        while True:
            if self._cancelled.is_set():
                # PRECONDITION abort_on_cancel: cancel remaining nodes then abort.
                self._scheduler._cancel_non_terminal()
                raise dag_engine.DAGCancelledError("DAG execution was cancelled")
            if self._scheduler.is_finished():
                break
            if timeout_seconds is not None and (time.monotonic() - start_time) > timeout_seconds:
                # PRECONDITION timeout_limit: abort when the overall timeout elapses.
                raise dag_engine.DAGTimeoutError("DAG execution exceeded the configured timeout")
            wave = self._scheduler.next_wave()
            if not wave:
                # No runnable nodes remain; blocked nodes cannot make further progress.
                break
            with ThreadPoolExecutor(max_workers=min(workers, len(wave))) as executor:
                futures = [
                    executor.submit(self._execute_node, node_id, failure_policy)
                    for node_id in wave
                ]
                for future in futures:
                    future.result()
        elapsed = time.monotonic() - start_time
        states = self._scheduler.get_all_states()
        succeeded = tuple(
            sorted(node_id for node_id, state in states.items() if state is dag_engine.NodeState.SUCCEEDED)
        )
        failed = tuple(
            sorted(node_id for node_id, state in states.items() if state is dag_engine.NodeState.FAILED)
        )
        skipped = tuple(
            sorted(node_id for node_id, state in states.items() if state is dag_engine.NodeState.SKIPPED)
        )
        cancelled = tuple(
            sorted(node_id for node_id, state in states.items() if state is dag_engine.NodeState.CANCELLED)
        )
        critical_path, _weight = self._dag.compute_critical_path(None)
        with self._lock:
            results = dict(self._results)
        # POSTCONDITION consolidated_report: capture all states, durations, and the critical path.
        return dag_engine.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=results,
        )

    def cancel(self) -> None:
        # POSTCONDITION abort_execution: signal cancellation and cancel non-terminal nodes.
        self._cancelled.set()
        self._scheduler._cancel_non_terminal()

    @test_only
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def _execute_node(self, node_id: str, failure_policy: dag_engine.FailurePolicy) -> None:
        definition = self._dag.get_node(node_id)
        self._scheduler.mark_running(node_id)
        attempts = 0
        node_start = time.monotonic()
        while True:
            try:
                value = definition.action()
            except Exception as exc:
                # POSTCONDITION retry_failures: retry up to the configured retry count.
                if attempts < definition.retries:
                    attempts += 1
                    continue
                duration = time.monotonic() - node_start
                result = dag_engine.NodeResult(
                    node_id=node_id,
                    state=dag_engine.NodeState.FAILED,
                    error=exc,
                    duration_seconds=duration,
                    retries_attempted=attempts,
                )
                with self._lock:
                    self._results[node_id] = result
                # POSTCONDITION apply_failure_policy: defer downstream effects to the scheduler.
                self._scheduler.mark_failed(node_id, failure_policy)
                return
            duration = time.monotonic() - node_start
            result = dag_engine.NodeResult(
                node_id=node_id,
                state=dag_engine.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=duration,
                retries_attempted=attempts,
            )
            with self._lock:
                self._results[node_id] = result
            self._scheduler.mark_succeeded(node_id)
            return


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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:36:04Z
# LAST_CHANGED: 2026-11-08T17:30:13Z
# CHANGE: Distinguish in-place definition replacement from genuine re-registration using per-node incarnation tokens maintained by DAG: add_node retains the incarnation while the id stays registered (so FAILED/CANCELLED/SUCCEEDED history is preserved), while remove_node clears it so a later add_node assigns a new incarnation. WaveScheduler tracks incarnation tokens and only discards execution state when the token changes, so in-place re-registration keeps terminal states while remove-then-readd starts fresh at READY/PENDING.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:36:04Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:35:42Z
# --- END AUTOFAB METADATA ---
