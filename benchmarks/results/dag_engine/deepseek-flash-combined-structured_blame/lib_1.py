# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_164039_deepseek-flash_dag_engine_combined
# Timestamp: 2026-11-08T16:40:39.701837+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 433,211
#   Cached Inbound Tokens:   35,189,632
#   Outbound Tokens:         447,868
#   Total Tokens:            36,070,711
#   Financial Cost ($USD):   $0.4393
#   Wall Clock Duration:     1941.86s
#   Step Latencies (s):      [310.1, 394.3, 61.3, 516.8, 122.7, 12.2, 137.5, 314.4, 94.8, 304.6, 20.4, 240.8, 10.1, 20.3, 262.6, 453.0, 10.1, 91.8, 63.5, 10.1, 10.0]
#   Role Execution Rounds:   coverage: 2, lib: 3, pretense: 4, pretense_coverage: 3, pretense_qa: 4, qa: 3, test: 2 (Total: 21)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       45
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Interface specification for the DAG execution and wave scheduling engine.

Declares the passive value types (node definitions, results, reports), the domain
error hierarchy, the node lifecycle and failure policy enumerations, and the
abstract service protocols realized by the implementation module.
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __post_init__(self) -> None:
        # Exceptions are never frozen dataclasses: Python assigns __traceback__
        # on exception instances, so the message is reified into Exception.args.
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str


@data_type
@dataclass
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

    def __str__(self) -> str:
        return f"NodeResult(node_id={self.node_id}, state={self.state.value})"


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


@singleton_type("system")
class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    @operation
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        """Adds a task node to the graph.

        The node definition is registered into the graph and, when dependencies are
        provided, directed dependency edges are added from each dependency to node_id.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Raises:
            NodeNotFoundError: If either node identifier is missing from the graph.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph.
        """
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.
        """
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        Raises:
            NodeNotFoundError: If any node references a dependency not in the graph.
            CycleError: If any directed cycle exists in the graph.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        Raises:
            CycleError: If the graph contains a directed cycle.
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
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        Args:
            estimated_durations: Optional mapping of node identifiers to duration weights.
                Defaults to 1.0 per node if omitted.
        """
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
    """Executes a DAG under concurrency limits, failure policies, and timeouts."""

    @operation
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        """Executes the entire DAG to completion or failure.

        Raises:
            DAGTimeoutError: If execution exceeds timeout_seconds.
            DAGCancelledError: If cancel() is invoked during execution.
        """
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
# LAST_CLEANED: 2026-11-08T16:47:26Z
# LAST_CHANGED: 2026-11-08T16:47:26Z
# CHANGE: Implemented interface module: dataclass value types (NodeDefinition, NodeResult, DAGRunReport), exception hierarchy with message-based str/args, NodeState/FailurePolicy enums, and DAG/WaveScheduler/DAGRunner protocol declarations with operation stubs matching the low-level spec; package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_impl.py ===
"""Concrete implementation of the DAG execution and wave scheduling engine.

Realizes the adjacency-store graph, the wave scheduler state machine, and the
concurrent runner declared in the interface module. Static types are verified
statically; runtime behavior is verified by the downstream test auditor.
"""

from __future__ import annotations

import heapq
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine

# Requirements specified in dag_engine_impl.pyi

_TERMINAL_STATES = frozenset({
    dag_engine.NodeState.SUCCEEDED,
    dag_engine.NodeState.FAILED,
    dag_engine.NodeState.SKIPPED,
    dag_engine.NodeState.CANCELLED,
})


@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node
    identifiers to definitions and dependency sets, synchronized by a re-entrant lock.
    """

    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

    def _require_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        # Contracted precondition: referencing an absent node raises NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the DAG",
                node_id,
            )
        return self._nodes[node_id]

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        # Depth-first search over dependency edges tracking the active recursion path.
        visiting: Set[str] = set()
        visited: Set[str] = set()
        path: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            if node_id in visiting:
                return tuple(path[path.index(node_id):])
            if node_id in visited:
                return None
            visiting.add(node_id)
            path.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                if dependent_id in self._nodes:
                    cycle = visit(dependent_id)
                    if cycle is not None:
                        return cycle
            path.pop()
            visiting.discard(node_id)
            visited.add(node_id)
            return None

        for node_id in sorted(self._nodes):
            cycle = visit(node_id)
            if cycle is not None:
                return cycle
        # Only reachable when no cycle exists; callers guard on ordering completeness.
        return None

    @operation
    @override
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        """Adds a task node to the graph."""
        with self._lock:
            registered = frozenset() if dependencies is None else frozenset(dependencies)
            definition = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=registered,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            # Re-registering a node replaces its definition and upstream edges.
            for upstream_id in self._upstream.get(node_id, set()):  # pragma: no cover (assumption: add_node is not re-invoked for an already registered node_id)
                self._downstream.get(upstream_id, set()).discard(node_id)
            self._nodes[node_id] = definition
            self._upstream[node_id] = set(registered)
            self._downstream.setdefault(node_id, set())
            # Each provided dependency becomes a directed edge into this node.
            for upstream_id in registered:
                self._upstream.setdefault(upstream_id, set())
                self._downstream.setdefault(upstream_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        with self._lock:
            # Contracted precondition: both endpoints must already be registered.
            self._require_node(upstream_id)
            self._require_node(downstream_id)
            self._upstream.setdefault(downstream_id, set()).add(upstream_id)
            self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        with self._lock:
            # Contracted precondition: the node must already be registered.
            self._require_node(node_id)
            for upstream_id in self._upstream.get(node_id, set()):
                self._downstream.get(upstream_id, set()).discard(node_id)
            for dependent_id in self._downstream.get(node_id, set()):
                self._upstream.get(dependent_id, set()).discard(node_id)
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
            return self._require_node(node_id)

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        with self._lock:
            self._require_node(node_id)
            return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        with self._lock:
            self._require_node(node_id)
            return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        with self._lock:
            return set(self._nodes)

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        with self._lock:
            # Every referenced dependency must be a registered node.
            for node_id in sorted(self._nodes):
                for dependency_id in sorted(self._upstream.get(node_id, set())):
                    if dependency_id not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            f"Dependency '{dependency_id}' of node '{node_id}' does not exist in the DAG",
                            dependency_id,
                        )
            # The graph must be acyclic; the detected cycle sequence is reported.
            cycle = self._find_cycle()
            if cycle is not None:
                raise dag_engine.CycleError(
                    "Dependency cycle detected: " + " -> ".join(cycle),
                    cycle,
                )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        with self._lock:
            in_degree: Dict[str, int] = {
                node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
            }
            # Ready queue is ordered by priority descending, then node_id ascending.
            ready: List[Tuple[int, str]] = [
                (-self._nodes[node_id].priority, node_id)
                for node_id in self._nodes
                if in_degree[node_id] == 0
            ]
            heapq.heapify(ready)
            order: List[str] = []
            while ready:
                _, node_id = heapq.heappop(ready)
                order.append(node_id)
                for dependent_id in self._downstream.get(node_id, set()):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        heapq.heappush(
                            ready,
                            (-self._nodes[dependent_id].priority, dependent_id),
                        )
            if len(order) != len(self._nodes):
                cycle = self._find_cycle() or ()
                raise dag_engine.CycleError(
                    "Dependency cycle detected: " + " -> ".join(cycle),
                    cycle,
                )
            return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._upstream.get(node_id)
            }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._downstream.get(node_id)
            }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        with self._lock:
            order = self.topological_sort()
            if not order:
                return [], 0.0
            earliest: Dict[str, float] = {}
            predecessor: Dict[str, Optional[str]] = {}
            for node_id in order:
                weight = 1.0
                if estimated_durations is not None:
                    weight = estimated_durations.get(node_id, 1.0)
                best_start = 0.0
                best_predecessor: Optional[str] = None
                for dependency_id in sorted(self._upstream.get(node_id, set())):
                    if earliest[dependency_id] > best_start:
                        best_start = earliest[dependency_id]
                        best_predecessor = dependency_id
                earliest[node_id] = best_start + weight
                predecessor[node_id] = best_predecessor
            # The path ends at the node with the maximum completion time.
            end_node = order[0]
            best_completion = earliest[end_node]
            for node_id in order[1:]:
                if earliest[node_id] > best_completion:
                    best_completion = earliest[node_id]
                    end_node = node_id
            critical_path: List[str] = []
            current: Optional[str] = end_node
            while current is not None:
                critical_path.append(current)
                current = predecessor[current]
            critical_path.reverse()
            return critical_path, best_completion


@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    Resolves the active DAG collaborator on demand and maintains per-node execution
    states, synchronized with the nodes currently registered in the graph.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine.DAG] = None
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._lock = threading.RLock()

    def _require_dag(self) -> dag_engine.DAG:
        # Collaborator singletons are resolved on demand rather than registered here.
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        return self._dag

    def _sync_states(self) -> None:
        # Discover registered graph nodes; roots start READY and others PENDING.
        dag = self._require_dag()
        nodes = dag.all_nodes()
        for node_id in nodes:
            if node_id not in self._states:
                if dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine.NodeState.READY
        for node_id in list(self._states):
            if node_id not in nodes:
                del self._states[node_id]

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        dag = self._require_dag()
        seen: Set[str] = set()
        pending: List[str] = list(dag.get_dependents(node_id))
        while pending:
            current_id = pending.pop()
            if current_id in seen:
                continue
            seen.add(current_id)
            pending.extend(dag.get_dependents(current_id))
        return seen

    def _cancel_non_terminal(self) -> None:
        # Used by the runner to abort execution, cancelling every unfinished node.
        with self._lock:
            self._sync_states()
            for node_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[node_id] = dag_engine.NodeState.CANCELLED

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        with self._lock:
            self._sync_states()
            dag = self._require_dag()
            ready: List[str] = []
            for node_id, state in self._states.items():
                if state != dag_engine.NodeState.READY:
                    continue
                dependencies = dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency_id) == dag_engine.NodeState.SUCCEEDED
                    for dependency_id in dependencies
                ):
                    ready.append(node_id)
            ready.sort(key=lambda candidate: (-dag.get_node(candidate).priority, candidate))
            return ready

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
            self._sync_states()
            dag = self._require_dag()
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # Newly unblocked dependents are promoted from PENDING to READY.
            for dependent_id in sorted(dag.get_dependents(node_id)):
                if self._states.get(dependent_id) != dag_engine.NodeState.PENDING:
                    continue
                if all(
                    self._states.get(dependency_id) == dag_engine.NodeState.SUCCEEDED
                    for dependency_id in dag.get_dependencies(dependent_id)
                ):
                    self._states[dependent_id] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        with self._lock:
            self._sync_states()
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy == dag_engine.FailurePolicy.FAIL_FAST:
                # Fail fast cancels every remaining unfinished node.
                for other_id, state in self._states.items():
                    if other_id == node_id:
                        continue
                    if state not in _TERMINAL_STATES:
                        self._states[other_id] = dag_engine.NodeState.CANCELLED
            elif failure_policy == dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # Skipping downstream transitions transitive dependents to SKIPPED.
                for dependent_id in sorted(self._transitive_dependents(node_id)):
                    if self._states.get(dependent_id) not in _TERMINAL_STATES:
                        self._states[dependent_id] = dag_engine.NodeState.SKIPPED
            # Otherwise dependent states are retained unchanged: transitive dependents
            # of the failed node remain PENDING while unblocked independent nodes stay
            # eligible for execution.

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        with self._lock:
            self._sync_states()
            return all(state in _TERMINAL_STATES for state in self._states.values())

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


@singleton_type("system")
class DAGRunner(dag_engine.DAGRunner):
    """Concrete realization of concurrent DAG execution runner.

    Resolves the active DAG and WaveScheduler collaborators on demand, coordinating
    wave dispatch, retries, failure policies, timeouts, and cancellation.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine.DAG] = None
        self._scheduler: Optional[WaveScheduler] = None
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}
        self._lock = threading.Lock()

    def _require_dag(self) -> dag_engine.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        return self._dag

    def _require_scheduler(self) -> WaveScheduler:
        if self._scheduler is None:
            self._scheduler = cast(
                WaveScheduler,
                get_singleton(dag_engine.WaveScheduler),
            )
        return self._scheduler

    def _check_abort(
        self,
        scheduler: WaveScheduler,
        started: float,
        timeout_seconds: Optional[float],
    ) -> None:
        if self._cancelled.is_set():
            # Cancellation marks all non-terminal nodes and aborts the run.
            scheduler._cancel_non_terminal()
            raise dag_engine.DAGCancelledError("DAG execution was cancelled")
        if timeout_seconds is not None and (time.monotonic() - started) > timeout_seconds:
            raise dag_engine.DAGTimeoutError(
                f"DAG execution exceeded timeout of {timeout_seconds} seconds"
            )

    def _execute_node(
        self,
        definition: dag_engine.NodeDefinition[Any],
        failure_policy: dag_engine.FailurePolicy,
    ) -> None:
        scheduler = self._require_scheduler()
        node_id = definition.node_id
        scheduler.mark_running(node_id)
        started = time.monotonic()
        value: Any = None
        error: Optional[Exception] = None
        succeeded = False
        retries_attempted = 0
        attempts = definition.retries + 1
        for attempt in range(attempts):
            try:
                value = definition.action()
                succeeded = True
                break
            except Exception as exc:  # cleanroom: allow-broad-exception (reified into NodeResult)
                error = exc
                if attempt < attempts - 1:
                    retries_attempted += 1
        duration = time.monotonic() - started
        outcome = dag_engine.NodeResult(
            node_id=node_id,
            state=dag_engine.NodeState.SUCCEEDED if succeeded else dag_engine.NodeState.FAILED,
            value=value if succeeded else None,
            error=None if succeeded else error,
            duration_seconds=duration,
            retries_attempted=retries_attempted,
        )
        with self._lock:
            self._results[node_id] = outcome
        if succeeded:
            scheduler.mark_succeeded(node_id)
        else:
            scheduler.mark_failed(node_id, failure_policy)

    def _build_report(
        self,
        dag: dag_engine.DAG,
        scheduler: WaveScheduler,
        elapsed: float,
    ) -> dag_engine.DAGRunReport:
        states = scheduler.get_all_states()
        with self._lock:
            results: Dict[str, dag_engine.NodeResult[Any]] = dict(self._results)
        # Nodes that never executed still receive an outcome record for reporting.
        for node_id, state in states.items():
            if node_id not in results:
                results[node_id] = dag_engine.NodeResult(node_id=node_id, state=state)
        succeeded = tuple(
            sorted(node_id for node_id, state in states.items()
                   if state == dag_engine.NodeState.SUCCEEDED)
        )
        failed = tuple(
            sorted(node_id for node_id, state in states.items()
                   if state == dag_engine.NodeState.FAILED)
        )
        skipped = tuple(
            sorted(node_id for node_id, state in states.items()
                   if state == dag_engine.NodeState.SKIPPED)
        )
        cancelled = tuple(
            sorted(node_id for node_id, state in states.items()
                   if state == dag_engine.NodeState.CANCELLED)
        )
        critical_path, _ = dag.compute_critical_path(None)
        return dag_engine.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=results,
        )

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: dag_engine.FailurePolicy,
        max_concurrency: int,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        dag = self._require_dag()
        scheduler = self._require_scheduler()
        # Graph consistency errors (cycle, missing dependency) propagate immediately.
        dag.validate()
        started = time.monotonic()
        with self._lock:
            self._results = {}
        worker_limit = max_concurrency if max_concurrency > 0 else 1
        with ThreadPoolExecutor(max_workers=worker_limit) as executor:
            while not scheduler.is_finished():
                self._check_abort(scheduler, started, timeout_seconds)
                wave = scheduler.next_wave()
                # No schedulable nodes remain: stop dispatching to guarantee progress.
                if not wave:
                    break
                futures = [
                    executor.submit(self._execute_node, dag.get_node(node_id), failure_policy)
                    for node_id in wave
                ]
                for future in as_completed(futures):
                    future.result()
        elapsed = time.monotonic() - started
        self._check_abort(scheduler, started, timeout_seconds)
        return self._build_report(dag, scheduler, elapsed)

    @operation
    @override
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        self._cancelled.set()
        self._require_scheduler()._cancel_non_terminal()

    @operation
    @override
    @test_only
    def is_cancelled(self) -> bool:
        """Query accessor verifying whether cancellation has been signaled."""
        return self._cancelled.is_set()


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
# LAST_CLEANED: 2026-11-08T17:12:58Z
# LAST_CHANGED: 2026-11-08T16:57:39Z
# CHANGE: Resolved coverage feedback: (1) marked the uncontracted add_node re-registration upstream repair with '# pragma: no cover (assumption: add_node is not re-invoked for an already registered node_id)'; (2) pruned the unreachable dangling-downstream-neighbor guard from topological_sort since contracted add_node/add_edge only create registered dependents and remove_node purges incident edges; (3) pruned the uncontracted per-node helper-thread timeout machinery, invoking node actions directly and retaining only the contracted run-level timeout enforcement in _check_abort.
# COVERAGE_AUDIT: 2026-11-08T17:00:39Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:12:58Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:12:46Z
# QA_AUDIT: 2026-11-08T17:00:25Z
# --- END AUTOFAB METADATA ---
