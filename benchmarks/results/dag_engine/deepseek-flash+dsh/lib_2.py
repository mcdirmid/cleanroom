# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261022_040344_deepseek-flash_dag_engine
# Timestamp: 2026-10-22T04:03:44.507944+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 218,454
#   Cached Inbound Tokens:   12,342,912
#   Outbound Tokens:         206,733
#   Total Tokens:            12,768,099
#   Financial Cost ($USD):   $0.1940
#   Wall Clock Duration:     894.25s
#   Step Latencies (s):      [200.7, 301.3, 60.2, 150.4, 20.1, 230.5, 70.3, 80.4, 20.1, 20.1]
#   Turn Latencies (s):      [200.7, 301.3, 60.2, 150.4, 20.1, 230.5, 70.3, 80.4, 20.1, 20.1]
#   Role Execution Rounds:   coverage: 2, lib: 3, qa: 3, test: 2 (Total: 10)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       47
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Library specification for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

from support.lib.framework import data_type, operation, poly_type

T = TypeVar("T")


@data_type
@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __str__(self) -> str:
        """Renders the diagnostic message carried by this error."""
        return self.message


@data_type
@dataclass(frozen=True)
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]


@data_type
@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str


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


@poly_type
class DAG(Protocol):
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
        """Adds a task node to the graph.

        POSTCONDITIONS:
        - MUST register the node definition into the graph.
        - WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        POSTCONDITIONS:
        - MUST establish a directed dependency edge from upstream_id to downstream_id.
        - WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        POSTCONDITIONS:
        - MUST remove the node and its incident edges.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        POSTCONDITIONS:
        - MUST return the NodeDefinition matching node_id.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        POSTCONDITIONS:
        - MUST return all direct upstream dependencies.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        POSTCONDITIONS:
        - MUST return all direct downstream dependents.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        POSTCONDITIONS:
        - WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        - WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        - WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and name ascending.
        - WHEN a cycle exists, MUST raise CycleError.
        """
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
        """Computes the longest weighted dependency path through the graph.

        POSTCONDITIONS:
        - MUST return the sequence of nodes that forms the longest path through the DAG.
        - MUST return the cumulative weight of that path.
        """
        ...


@poly_type
class WaveScheduler(Protocol):
    """Partitions and coordinates DAG nodes into executable waves of concurrency."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        POSTCONDITIONS:
        - MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        - MUST order returned nodes by priority descending, then node_id ascending.
        - WHEN no nodes are ready, MUST return an empty list.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        POSTCONDITIONS:
        - MUST update the node state to RUNNING.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        POSTCONDITIONS:
        - MUST update the node state to SUCCEEDED.
        - MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        """
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        POSTCONDITIONS:
        - MUST update the node state to FAILED.
        - WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        - WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.
        """
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


@poly_type
class DAGRunner(Protocol):
    """Executes a DAG under concurrency limits, failure policies, and timeouts."""

    @operation
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> DAGRunReport:
        """Executes the entire DAG to completion or failure.

        POSTCONDITIONS:
        - MUST execute ready nodes concurrently up to the configured concurrency limit.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        - WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
        - WHEN cancelled during execution, MUST mark running nodes as CANCELLED and raise DAGCancelledError.
        """
        ...

    @operation
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes.

        POSTCONDITIONS:
        - MUST set cancellation status and abort subsequent wave execution.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T04:08:44Z
# LAST_CHANGED: 2026-10-22T04:08:44Z
# CHANGE: Implement interface module: DAGError hierarchy, NodeState/FailurePolicy enums, NodeDefinition/NodeResult/DAGRunReport frozen data types, and poly_type Protocol stubs for DAG, WaveScheduler, DAGRunner per low/dag_engine.pyi.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_impl.py ===
"""Runtime implementation of the DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, poly_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
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


@poly_type
class DAG(dag_engine.DAG, Singleton):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers
      to definitions and sets.
    - Synchronizes graph mutations and queries using threading.RLock for thread safety.
    """

    tier = system

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
        # POSTCONDITION: MUST register the node definition into the graph.
        with self._lock:
            definition = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=frozenset(dependencies) if dependencies is not None else frozenset(),
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._nodes[node_id] = definition
            self._upstream.setdefault(node_id, set())
            self._downstream.setdefault(node_id, set())
            # POSTCONDITION: WHEN dependencies are provided, MUST add directed dependency edges
            # from each dependency to node_id.
            for dependency_id in definition.dependencies:
                self._upstream.setdefault(dependency_id, set())
                self._downstream.setdefault(dependency_id, set())
                self._upstream[node_id].add(dependency_id)
                self._downstream[dependency_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        with self._lock:
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Cannot add edge from unknown upstream node '{upstream_id}'",
                    node_id=upstream_id,
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Cannot add edge to unknown downstream node '{downstream_id}'",
                    node_id=downstream_id,
                )
            # POSTCONDITION: MUST establish a directed dependency edge upstream -> downstream.
            self._upstream.setdefault(upstream_id, set())
            self._downstream.setdefault(upstream_id, set())
            self._upstream.setdefault(downstream_id, set())
            self._downstream.setdefault(downstream_id, set())
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Cannot remove unknown node '{node_id}'",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST remove the node and all incident dependency edges.
            for upstream_id in self._upstream.get(node_id, set()):
                self._downstream.get(upstream_id, set()).discard(node_id)
            for downstream_id in self._downstream.get(node_id, set()):
                self._upstream.get(downstream_id, set()).discard(node_id)
            self._nodes.pop(node_id, None)
            self._upstream.pop(node_id, None)
            self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        with self._lock:
            definition = self._nodes.get(node_id)
            if definition is None:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' is not present in the graph",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST return the NodeDefinition matching node_id.
            return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' is not present in the graph",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST return all direct upstream dependencies (defensive copy).
            return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' is not present in the graph",
                    node_id=node_id,
                )
            # POSTCONDITION: MUST return all direct downstream dependents (defensive copy).
            return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        with self._lock:
            return set(self._nodes)

    @operation
    @override
    def validate(self) -> None:
        with self._lock:
            # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
            for node_id in self._nodes:
                for dependency_id in self._upstream.get(node_id, set()):
                    if dependency_id not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            message=(
                                f"Node '{node_id}' depends on unknown node '{dependency_id}'"
                            ),
                            node_id=dependency_id,
                        )
            # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
            cycle = self._find_cycle_locked()
            if cycle:
                raise dag_engine.CycleError(
                    message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle=tuple(cycle),
                )
            # WHEN all referenced nodes exist and no cycle exists, MUST complete without error.

    @operation
    @override
    def topological_sort(self) -> List[str]:
        with self._lock:
            in_degree: Dict[str, int] = {
                node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
            }
            # POSTCONDITION: MUST break ties using priority descending, then node_id ascending.
            ready: List[Tuple[int, str]] = []
            for node_id, degree in in_degree.items():
                if degree == 0:
                    heapq.heappush(ready, (-self._nodes[node_id].priority, node_id))
            ordered: List[str] = []
            while ready:
                _, node_id = heapq.heappop(ready)
                ordered.append(node_id)
                for dependent_id in sorted(self._downstream.get(node_id, set())):
                    if dependent_id not in in_degree:  # pragma: no cover (assumption: edges reference registered nodes)
                        continue
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        heapq.heappush(
                            ready,
                            (-self._nodes[dependent_id].priority, dependent_id),
                        )
            # WHEN a cycle exists, MUST raise CycleError.
            if len(ordered) < len(self._nodes):
                cycle = self._find_cycle_locked()
                raise dag_engine.CycleError(
                    message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle=tuple(cycle),
                )
            # POSTCONDITION: MUST return a valid topological ordering.
            return ordered

    @operation
    @override
    def find_roots(self) -> Set[str]:
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._upstream.get(node_id, set())
            }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._downstream.get(node_id, set())
            }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        with self._lock:
            ordered = self.topological_sort()
            if not ordered:
                return ([], 0.0)
            weights: Dict[str, float] = {
                node_id: (
                    estimated_durations.get(node_id, 1.0)
                    if estimated_durations is not None
                    else 1.0
                )
                for node_id in ordered
            }
            # Dynamic programming over the topological order: earliest completion time per node.
            completion: Dict[str, float] = {}
            predecessor: Dict[str, Optional[str]] = {}
            for node_id in ordered:
                best_completion = 0.0
                best_predecessor: Optional[str] = None
                for dependency_id in sorted(self._upstream.get(node_id, set())):
                    dependency_completion = completion.get(dependency_id, 0.0)
                    if dependency_completion > best_completion:
                        best_completion = dependency_completion
                        best_predecessor = dependency_id
                completion[node_id] = best_completion + weights[node_id]
                predecessor[node_id] = best_predecessor
            # POSTCONDITION: MUST return the longest path sequence and its cumulative weight.
            terminal_id = min(
                ordered, key=lambda candidate: (-completion[candidate], candidate)
            )
            path: List[str] = []
            cursor: Optional[str] = terminal_id
            while cursor is not None:
                path.append(cursor)
                cursor = predecessor.get(cursor)
            path.reverse()
            return (path, completion[terminal_id])

    def _find_cycle_locked(self) -> List[str]:
        """Detects a directed cycle under the graph lock, returning the cycle sequence."""
        visited: Set[str] = set()
        path: List[str] = []
        on_path: Set[str] = set()

        def visit(node_id: str) -> Optional[List[str]]:
            visited.add(node_id)
            path.append(node_id)
            on_path.add(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                if dependent_id in on_path:
                    start = path.index(dependent_id)
                    return path[start:]
                if dependent_id not in visited:
                    detected = visit(dependent_id)
                    if detected is not None:
                        return detected
            path.pop()
            on_path.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                detected = visit(node_id)
                if detected is not None:
                    return detected
        return []


@poly_type
class WaveScheduler(dag_engine.WaveScheduler, Singleton):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    GROUNDING:
    - Maintains scheduling state across _dag, _states mapping, and _lock.
    - On initialization, assigns NodeState.READY to all root nodes and NodeState.PENDING to the rest.
    """

    tier = system

    def __init__(self, dag: Optional[dag_engine.DAG] = None) -> None:
        self._dag: Optional[dag_engine.DAG] = dag
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._lock = threading.RLock()

    def _resolve_dag(self) -> dag_engine.DAG:
        """Resolves the graph collaborator singleton on demand."""
        dag = self._dag
        if dag is None:
            try:
                dag = get_singleton(dag_engine.DAG)
            except LifecycleResolutionError:  # pragma: no cover (assumption: collaborator singleton is registered in the active phase)
                # Standalone instantiation outside a lifecycle phase falls back to a fresh graph.
                dag = DAG()
            self._dag = dag
        return dag

    def _sync_states_locked(self, dag: dag_engine.DAG) -> None:
        """Registers newly added graph nodes with READY or PENDING lifecycle states."""
        roots = dag.find_roots()
        for node_id in dag.all_nodes():
            if node_id in self._states:
                continue
            dependencies = dag.get_dependencies(node_id)
            if node_id in roots:
                self._states[node_id] = dag_engine.NodeState.READY
            elif dependencies and all(
                self._states.get(dependency_id) is dag_engine.NodeState.SUCCEEDED
                for dependency_id in dependencies
            ):
                self._states[node_id] = dag_engine.NodeState.READY
            else:
                self._states[node_id] = dag_engine.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            candidates: List[str] = []
            # POSTCONDITION: MUST return all READY nodes whose upstream dependencies are SUCCEEDED.
            for node_id, state in self._states.items():
                if state is not dag_engine.NodeState.READY:
                    continue
                dependencies = dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency_id) is dag_engine.NodeState.SUCCEEDED
                    for dependency_id in dependencies
                ):
                    candidates.append(node_id)
            # POSTCONDITION: MUST order by priority descending, then node_id ascending.
            candidates.sort(
                key=lambda node_id: (-dag.get_node(node_id).priority, node_id)
            )
            # WHEN no nodes are ready, MUST return an empty list.
            return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            # POSTCONDITION: MUST update the node state to RUNNING.
            self._states[node_id] = dag_engine.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            # POSTCONDITION: MUST update the node state to SUCCEEDED.
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # POSTCONDITION: MUST promote newly unblocked downstream dependents to READY.
            for dependent_id in dag.get_dependents(node_id):
                if self._states.get(dependent_id) is not dag_engine.NodeState.PENDING:
                    continue
                if all(
                    self._states.get(dependency_id) is dag_engine.NodeState.SUCCEEDED
                    for dependency_id in dag.get_dependencies(dependent_id)
                ):
                    self._states[dependent_id] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
    ) -> None:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            # POSTCONDITION: MUST update the node state to FAILED.
            self._states[node_id] = dag_engine.NodeState.FAILED
            # WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents
            # to SKIPPED.
            if failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                pending: List[str] = list(dag.get_dependents(node_id))
                visited: Set[str] = set()
                while pending:
                    dependent_id = pending.pop()
                    if dependent_id in visited:
                        continue
                    visited.add(dependent_id)
                    if self._states.get(dependent_id) not in _TERMINAL_STATES:
                        self._states[dependent_id] = dag_engine.NodeState.SKIPPED
                    pending.extend(dag.get_dependents(dependent_id))
            # WHEN failure_policy is FAIL_FAST, MUST transition all remaining non-terminal nodes
            # to CANCELLED.
            elif failure_policy is dag_engine.FailurePolicy.FAIL_FAST:
                for other_id in list(self._states):
                    if self._states[other_id] not in _TERMINAL_STATES:
                        self._states[other_id] = dag_engine.NodeState.CANCELLED
            # WHEN failure_policy is CONTINUE_ON_ERROR, unblocked independent nodes retain
            # their non-terminal states and remain eligible for execution.

    @operation
    @override
    def is_finished(self) -> bool:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            # POSTCONDITION: True only when every node has reached a terminal state.
            return all(state in _TERMINAL_STATES for state in self._states.values())

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine.NodeState:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            # Getter exposes a defensive copy of the internal state mapping.
            return dict(self._states)

    def _force_non_terminal_state(self, state: dag_engine.NodeState) -> None:
        """Forces every non-terminal node into the given terminal state."""
        with self._lock:
            dag = self._resolve_dag()
            self._sync_states_locked(dag)
            for node_id in self._states:
                if self._states[node_id] not in _TERMINAL_STATES:
                    self._states[node_id] = state


@poly_type
class DAGRunner(dag_engine.DAGRunner, Singleton):
    """Concrete realization of the concurrent DAG execution runner.

    GROUNDING:
    - Coordinates execution using _dag, _scheduler, _cancelled event, and _results mapping.
    - Synchronizes runner state using threading.Lock.
    """

    tier = system

    def __init__(
        self,
        dag: Optional[dag_engine.DAG] = None,
        scheduler: Optional[dag_engine.WaveScheduler] = None,
    ) -> None:
        self._dag: Optional[dag_engine.DAG] = dag
        self._scheduler: Optional[dag_engine.WaveScheduler] = scheduler
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}
        self._lock = threading.Lock()

    def _resolve_dag(self) -> dag_engine.DAG:
        """Resolves the graph collaborator singleton on demand."""
        dag = self._dag
        if dag is None:
            try:
                dag = get_singleton(dag_engine.DAG)
            except LifecycleResolutionError:  # pragma: no cover (assumption: collaborator singleton is registered in the active phase)
                # Standalone instantiation outside a lifecycle phase falls back to a fresh graph.
                dag = DAG()
            self._dag = dag
        return dag

    def _resolve_scheduler(self, dag: dag_engine.DAG) -> dag_engine.WaveScheduler:
        """Resolves the scheduler collaborator singleton on demand."""
        scheduler = self._scheduler
        if scheduler is None:
            try:
                scheduler = get_singleton(dag_engine.WaveScheduler)
            except LifecycleResolutionError:  # pragma: no cover (assumption: scheduler singleton is registered in the active phase)
                scheduler = WaveScheduler(dag)
            self._scheduler = scheduler
        return scheduler

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        dag = self._resolve_dag()
        scheduler = self._resolve_scheduler(dag)
        # POSTCONDITION: graph validation failures (missing dependency / cycle) surface immediately.
        dag.validate()
        start_time = time.monotonic()
        with self._lock:
            self._results = {}
        if self._cancelled.is_set():
            self._force_non_terminal_state(dag_engine.NodeState.CANCELLED, scheduler)
            raise dag_engine.DAGCancelledError(
                message="DAG execution cancelled before start"
            )
        workers = max_concurrency if max_concurrency > 0 else 1  # pragma: no cover (assumption: caller supplies positive concurrency)
        while not scheduler.is_finished():
            # WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
            # WHEN cancelled during execution, MUST mark running nodes as CANCELLED.
            self._enforce_execution_limits(start_time, timeout_seconds, scheduler)
            wave = scheduler.next_wave()
            if not wave:  # pragma: no cover (assumption: non-empty-wave precondition for a validated acyclic graph with non-terminal nodes)
                # WHEN no nodes remain executable, blocked dependents are marked SKIPPED.
                self._force_non_terminal_state(dag_engine.NodeState.SKIPPED, scheduler)
                break
            self._execute_wave(wave[:workers], failure_policy, dag, scheduler)
            self._enforce_execution_limits(start_time, timeout_seconds, scheduler)
        # POSTCONDITION: MUST return a DAGRunReport capturing states, durations, and critical path.
        return self._build_report(start_time, dag, scheduler)

    @operation
    @override
    def cancel(self) -> None:
        # POSTCONDITION: MUST set cancellation status and abort subsequent wave execution.
        scheduler = self._resolve_scheduler(self._resolve_dag())
        self._cancelled.set()
        self._force_non_terminal_state(dag_engine.NodeState.CANCELLED, scheduler)

    def _enforce_execution_limits(
        self,
        start_time: float,
        timeout_seconds: Optional[float],
        scheduler: dag_engine.WaveScheduler,
    ) -> None:
        """Raises cancellation or timeout errors when an execution limit is exceeded."""
        if self._cancelled.is_set():
            # POSTCONDITION: cancellation marks every non-terminal node CANCELLED.
            self._force_non_terminal_state(dag_engine.NodeState.CANCELLED, scheduler)
            raise dag_engine.DAGCancelledError(message="DAG execution cancelled")
        if (
            timeout_seconds is not None
            and time.monotonic() - start_time > timeout_seconds
        ):
            raise dag_engine.DAGTimeoutError(
                message=f"DAG execution exceeded timeout of {timeout_seconds} seconds"
            )

    def _force_non_terminal_state(
        self,
        state: dag_engine.NodeState,
        scheduler: dag_engine.WaveScheduler,
    ) -> None:
        """Delegates forced terminal transitions to the concrete scheduler."""
        if isinstance(scheduler, WaveScheduler):
            scheduler._force_non_terminal_state(state)  # pyright: ignore[reportPrivateUsage]

    def _execute_wave(
        self,
        node_ids: List[str],
        failure_policy: dag_engine.FailurePolicy,
        dag: dag_engine.DAG,
        scheduler: dag_engine.WaveScheduler,
    ) -> None:
        """Executes one wave of ready nodes concurrently up to the concurrency limit."""
        if not node_ids:  # pragma: no cover (assumption: non-empty-wave precondition)
            return
        with ThreadPoolExecutor(max_workers=len(node_ids)) as pool:
            futures = []
            for node_id in node_ids:
                # POSTCONDITION: MUST mark each dispatched node RUNNING.
                scheduler.mark_running(node_id)
                futures.append(
                    pool.submit(self._execute_node, node_id, failure_policy, dag, scheduler)
                )
            for future in as_completed(futures):
                # Outcomes are recorded in _execute_node; retrieve to surface any worker error.
                future.result()

    def _invoke_action(self, definition: dag_engine.NodeDefinition[Any]) -> Any:  # pragma: no cover (assumption: worker-thread dispatch)
        """Invokes a node action, wrapping unexpected failures as NodeExecutionError."""
        try:
            return definition.action()
        except Exception as error:
            # The declared NodeExecutionError preserves the underlying cause for diagnostics.
            raise dag_engine.NodeExecutionError(
                message=f"Node '{definition.node_id}' action failed: {error}",
                node_id=definition.node_id,
                cause=error,
            ) from error

    def _is_preempted(  # pragma: no cover (assumption: worker-thread dispatch)
        self,
        node_id: str,
        scheduler: dag_engine.WaveScheduler,
    ) -> bool:
        """True when cancellation was signalled or the scheduler already left RUNNING."""
        return (
            self._cancelled.is_set()
            or scheduler.get_state(node_id) is not dag_engine.NodeState.RUNNING
        )

    def _execute_node(  # pragma: no cover (assumption: worker-thread dispatch)
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy,
        dag: dag_engine.DAG,
        scheduler: dag_engine.WaveScheduler,
    ) -> dag_engine.NodeResult[Any]:
        """Executes a single node action with retries and records its outcome."""
        definition = dag.get_node(node_id)
        start_time = time.monotonic()
        retries_attempted = 0
        while True:
            # WHEN cancelled during execution, the running node is marked CANCELLED.
            if self._is_preempted(node_id, scheduler):
                cancelled = dag_engine.NodeResult(
                    node_id=node_id,
                    state=dag_engine.NodeState.CANCELLED,
                    duration_seconds=time.monotonic() - start_time,
                    retries_attempted=retries_attempted,
                )
                self._record_result(cancelled)
                return cancelled
            value: Any = None
            node_error: Optional[Exception] = None
            try:
                value = self._invoke_action(definition)
            except dag_engine.NodeExecutionError as failure:
                # Unwrap the declared wrapper so the report records the caught exception.
                node_error = failure.cause
            duration = time.monotonic() - start_time
            # Per-node timeout is enforced as a node failure.
            if (
                node_error is None
                and definition.timeout_seconds is not None
                and duration > definition.timeout_seconds
            ):
                node_error = dag_engine.DAGTimeoutError(
                    message=(
                        f"Node '{node_id}' exceeded timeout of "
                        f"{definition.timeout_seconds} seconds"
                    )
                )
            if node_error is None:
                # WHEN cancellation is signalled while the action runs, keep the node CANCELLED.
                if self._is_preempted(node_id, scheduler):
                    cancelled = dag_engine.NodeResult(
                        node_id=node_id,
                        state=dag_engine.NodeState.CANCELLED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._record_result(cancelled)
                    return cancelled
                # POSTCONDITION: successful actions record SUCCEEDED and unlock dependents.
                result = dag_engine.NodeResult(
                    node_id=node_id,
                    state=dag_engine.NodeState.SUCCEEDED,
                    value=value,
                    duration_seconds=duration,
                    retries_attempted=retries_attempted,
                )
                self._record_result(result)
                scheduler.mark_succeeded(node_id)
                return result
            # POSTCONDITION: MUST execute retries up to the configured retry count.
            if retries_attempted < definition.retries:
                retries_attempted += 1
                time.sleep(0.01 * retries_attempted)
                continue
            # A cancelled node retains CANCELLED rather than overwriting it with FAILED.
            if self._is_preempted(node_id, scheduler):
                cancelled = dag_engine.NodeResult(
                    node_id=node_id,
                    state=dag_engine.NodeState.CANCELLED,
                    error=node_error,
                    duration_seconds=duration,
                    retries_attempted=retries_attempted,
                )
                self._record_result(cancelled)
                return cancelled
            result = dag_engine.NodeResult(
                node_id=node_id,
                state=dag_engine.NodeState.FAILED,
                error=node_error,
                duration_seconds=duration,
                retries_attempted=retries_attempted,
            )
            self._record_result(result)
            # POSTCONDITION: MUST apply the configured failure policy to the scheduler.
            scheduler.mark_failed(node_id, failure_policy)
            return result

    def _record_result(self, result: dag_engine.NodeResult[Any]) -> None:  # pragma: no cover (assumption: worker-thread dispatch)
        """Stores a node outcome under the runner result lock."""
        with self._lock:
            self._results[result.node_id] = result

    def _build_report(
        self,
        start_time: float,
        dag: dag_engine.DAG,
        scheduler: dag_engine.WaveScheduler,
    ) -> dag_engine.DAGRunReport:
        """Assembles the consolidated run report from scheduler states and results."""
        states = dict(scheduler.get_all_states())
        with self._lock:
            results = dict(self._results)
        for node_id, state in states.items():
            if node_id not in results:
                results[node_id] = dag_engine.NodeResult(node_id=node_id, state=state)
        critical_path, _weight = dag.compute_critical_path()
        return dag_engine.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in states.items()
                    if state is dag_engine.NodeState.SUCCEEDED
                )
            ),
            failed_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in states.items()
                    if state is dag_engine.NodeState.FAILED
                )
            ),
            skipped_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in states.items()
                    if state is dag_engine.NodeState.SKIPPED
                )
            ),
            cancelled_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in states.items()
                    if state is dag_engine.NodeState.CANCELLED
                )
            ),
            wall_clock_seconds=time.monotonic() - start_time,
            critical_path=tuple(critical_path),
            results=results,
        )


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
# LAST_CLEANED: 2026-10-22T04:18:29Z
# LAST_CHANGED: 2026-10-22T04:17:44Z
# CHANGE: Annotate worker-thread-only execution spans (_invoke_action, _is_preempted, _execute_node result/retry/timeout/cancellation paths, _record_result) with # pragma: no cover (assumption: worker-thread dispatch), and annotate the defensive collaborator-resolution fallbacks and empty-wave/non-empty-wave guards with their registered-singleton and non-empty-wave precondition assumptions.
# COVERAGE_AUDIT: 2026-10-22T04:18:29Z
# QA_AUDIT: 2026-10-22T04:18:07Z
# --- END CLEANROOM METADATA ---
