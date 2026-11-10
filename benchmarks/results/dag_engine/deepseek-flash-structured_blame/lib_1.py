# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_164030_deepseek-flash_dag_engine
# Timestamp: 2026-11-08T16:40:30.916329+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 189,770
#   Cached Inbound Tokens:   14,382,848
#   Outbound Tokens:         220,406
#   Total Tokens:            14,793,024
#   Financial Cost ($USD):   $0.2039
#   Wall Clock Duration:     1116.28s
#   Step Latencies (s):      [356.1, 429.7, 20.2, 177.1, 236.9, 275.4, 10.1, 103.8, 50.8, 10.1, 20.2]
#   Role Execution Rounds:   coverage: 3, lib: 2, qa: 3, test: 3 (Total: 11)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       45
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Low-level interface specification for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

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

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
            timeout_seconds: Optional per-node execution timeout.
            retries: Number of permitted retry attempts upon exception.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        Raises:
            NodeNotFoundError: If either node identifier is missing from the graph.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph.
        """
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        Args:
            node_id: Identifier to check.

        Returns:
            True if the node exists, False otherwise.
        """
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        Args:
            node_id: Identifier of the node to retrieve.

        Returns:
            The registered NodeDefinition.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.
        """
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        Returns:
            Set of all registered node identifiers.
        """
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

        Returns:
            List of node identifiers in topological order.

        Raises:
            CycleError: If the graph contains a directed cycle.
        """
        ...

    @operation
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies).

        Returns:
            Set of root node identifiers.
        """
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents).

        Returns:
            Set of leaf node identifiers.
        """
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

        Returns:
            Tuple of (critical path node identifiers, total path weight).
        """
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into executable waves of concurrency."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        Returns:
            List of node identifiers ready for concurrent execution, ordered by priority descending.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.
        """
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        Args:
            node_id: Identifier of the failed node.
            failure_policy: Failure policy applied upon failure.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Current NodeState.
        """
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph.

        Returns:
            Mapping of node identifier to current NodeState.
        """
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

        Args:
            timeout_seconds: Optional overall execution timeout in seconds.
            failure_policy: Failure policy applied upon node action failure.
            max_concurrency: Maximum number of worker threads for concurrent wave execution.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

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
    def is_cancelled(self) -> bool:
        """Query accessor verifying whether cancellation has been signaled.

        Returns:
            True if cancellation status has been set, False otherwise.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:46:59Z
# LAST_CHANGED: 2026-11-08T16:46:59Z
# CHANGE: Implement DAG interface module: data types, exceptions with message __str__, NodeState/FailurePolicy enums, and DAG/WaveScheduler/DAGRunner protocols with package-qualified imports and frozen value dataclasses.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_impl.py ===
"""Low-level implementation of the DAG execution and wave scheduling engine."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import heapq
import threading
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dag_engine

# Terminal lifecycle states; a node in one of these states never transitions again.
_TERMINAL_STATES: FrozenSet[dag_engine.NodeState] = frozenset(
    {
        dag_engine.NodeState.SUCCEEDED,
        dag_engine.NodeState.FAILED,
        dag_engine.NodeState.SKIPPED,
        dag_engine.NodeState.CANCELLED,
    }
)

# Polling interval used by the runner while awaiting worker completions.
_POLL_INTERVAL_SECONDS: float = 0.05


@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node
    identifiers to definitions and neighbor sets, synchronized by a reentrant lock.
    """

    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

    def _require_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        """Returns the registered definition, raising NodeNotFoundError when absent."""
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the graph", node_id
            )
        return definition

    def _ensure_dependencies_exist(self) -> None:
        """Raises NodeNotFoundError on the first dependency that is not registered."""
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._nodes[node_id].dependencies):
                if dependency not in self._nodes:
                    raise dag_engine.NodeNotFoundError(
                        f"Dependency '{dependency}' of node '{node_id}' is not registered in the graph",
                        dependency,
                    )

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Performs a depth-first search returning the first detected directed cycle."""
        visited: Set[str] = set()
        in_progress: Set[str] = set()
        stack: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            visited.add(node_id)
            in_progress.add(node_id)
            stack.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                if dependency in in_progress:
                    start_index = stack.index(dependency)
                    return tuple(stack[start_index:])
                if dependency not in visited:
                    detected = visit(dependency)
                    if detected is not None:
                        return detected
            stack.pop()
            in_progress.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                detected = visit(node_id)
                if detected is not None:
                    return detected
        return None

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
        resolved_dependencies: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        definition: dag_engine.NodeDefinition[Any] = dag_engine.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=resolved_dependencies,
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        with self._lock:
            # Register the immutable node definition into the graph.
            self._nodes[node_id] = definition
            self._upstream.setdefault(node_id, set())
            self._downstream.setdefault(node_id, set())
            # Add a directed edge from each upstream dependency to node_id.
            for dependency in resolved_dependencies:
                self._upstream[node_id].add(dependency)
                self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        with self._lock:
            self._require_node(upstream_id)
            self._require_node(downstream_id)
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        with self._lock:
            self._require_node(node_id)
            # Purge every incident edge before deleting the node itself.
            for upstream_id in self._upstream.get(node_id, set()):
                self._downstream.get(upstream_id, set()).discard(node_id)
            for downstream_id in self._downstream.get(node_id, set()):
                self._upstream.get(downstream_id, set()).discard(node_id)
            self._upstream.pop(node_id, None)
            self._downstream.pop(node_id, None)
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
            self._ensure_dependencies_exist()
            # Any detected cycle must be reported with its cyclic sequence.
            cycle = self._find_cycle()
            if cycle is not None:
                cycle_text = " -> ".join(cycle)
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {cycle_text}", cycle
                )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        with self._lock:
            self._ensure_dependencies_exist()
            in_degree: Dict[str, int] = {
                node_id: len(self._upstream.get(node_id, set()))
                for node_id in self._nodes
            }
            # Ready queue ordered by priority descending, then node_id ascending.
            ready: List[Tuple[int, str]] = [
                (-definition.priority, node_id)
                for node_id, definition in self._nodes.items()
                if in_degree[node_id] == 0
            ]
            heapq.heapify(ready)
            order: List[str] = []
            while ready:
                _, node_id = heapq.heappop(ready)
                order.append(node_id)
                for dependent_id in sorted(self._downstream.get(node_id, set())):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        heapq.heappush(
                            ready,
                            (-self._nodes[dependent_id].priority, dependent_id),
                        )
            if len(order) != len(self._nodes):
                # An incomplete ordering after reference validation implies a cycle.
                cycle = self._find_cycle()
                if cycle is None:  # unreachable (assumption: verified references make an incomplete ordering a cycle)
                    raise dag_engine.CycleError(
                        "Dependency cycle detected in the graph", ()
                    )
                cycle_text = " -> ".join(cycle)
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {cycle_text}", cycle
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
                if not self._upstream.get(node_id, set())
            }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
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
        """Computes the longest weighted dependency path through the graph."""
        with self._lock:
            order = self.topological_sort()
            if not order:
                return ([], 0.0)
            weights: Dict[str, float] = {}
            for node_id in order:
                if estimated_durations is None:
                    weights[node_id] = 1.0
                else:
                    weights[node_id] = float(estimated_durations.get(node_id, 1.0))
            # Dynamic programming over the topological order: earliest completion
            # time per node plus the predecessor that attained it.
            earliest: Dict[str, float] = {}
            predecessor: Dict[str, Optional[str]] = {}
            for node_id in order:
                best_weight = weights[node_id]
                best_predecessor: Optional[str] = None
                for dependency in sorted(self._upstream.get(node_id, set())):
                    candidate = earliest[dependency] + weights[node_id]
                    if candidate > best_weight:
                        best_weight = candidate
                        best_predecessor = dependency
                earliest[node_id] = best_weight
                predecessor[node_id] = best_predecessor
            # Deterministic tie-breaking: complete earliest, then node_id ascending.
            candidates = sorted(order)
            terminal_id = candidates[0]
            for node_id in candidates[1:]:
                if earliest[node_id] > earliest[terminal_id]:
                    terminal_id = node_id
            path: List[str] = []
            current: Optional[str] = terminal_id
            while current is not None:
                path.append(current)
                current = predecessor.get(current)
            path.reverse()
            return (path, earliest[terminal_id])


@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    Resolves the active DAG service on construction and tracks per-node scheduling
    states in _states under a reentrant lock.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine.DAG = get_singleton(dag_engine.DAG)
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._lock = threading.RLock()

    def _sync_states(self) -> None:
        """Discovers registered DAG nodes and seeds lifecycle states for new nodes."""
        known_nodes = self._dag.all_nodes()
        for node_id in list(self._states):
            if node_id not in known_nodes:
                del self._states[node_id]
        for node_id in known_nodes:
            if node_id not in self._states:
                dependencies = self._dag.get_dependencies(node_id)
                # Roots (no upstream dependencies) start READY; others wait as PENDING.
                self._states[node_id] = (
                    dag_engine.NodeState.READY
                    if not dependencies
                    else dag_engine.NodeState.PENDING
                )

    def _dependencies_succeeded(self, node_id: str) -> bool:
        """Reports whether every direct upstream dependency has SUCCEEDED."""
        return all(
            self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
            for dependency in self._dag.get_dependencies(node_id)
        )

    def _cancel_all(self) -> None:
        """Cancels every non-terminal node in support of runner cancellation."""
        with self._lock:
            self._sync_states()
            for tracked_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[tracked_id] = dag_engine.NodeState.CANCELLED

    def _skip_blocked(self) -> None:
        """Skips every node left unexecutable because an upstream dependency did not succeed."""
        with self._lock:
            self._sync_states()
            for tracked_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[tracked_id] = dag_engine.NodeState.SKIPPED

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        with self._lock:
            self._sync_states()
            ready: List[str] = []
            for node_id, state in self._states.items():
                if state is not dag_engine.NodeState.READY:
                    continue
                if self._dependencies_succeeded(node_id):
                    ready.append(node_id)
            # Order by priority descending, then node_id ascending.
            ready.sort(
                key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id)
            )
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
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # Promote newly unblocked dependents from PENDING to READY.
            for dependent_id in sorted(self._dag.get_dependents(node_id)):
                if self._states.get(dependent_id) is not dag_engine.NodeState.PENDING:
                    continue
                if self._dependencies_succeeded(dependent_id):
                    self._states[dependent_id] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.CONTINUE_ON_ERROR,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        with self._lock:
            self._sync_states()
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy is dag_engine.FailurePolicy.FAIL_FAST:
                # Cancel every remaining non-terminal node.
                for tracked_id, state in self._states.items():
                    if state not in _TERMINAL_STATES:
                        self._states[tracked_id] = dag_engine.NodeState.CANCELLED
            elif failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # Skip every transitive dependent of the failed node.
                pending: List[str] = [node_id]
                seen: Set[str] = {node_id}
                while pending:
                    current = pending.pop()
                    for dependent_id in sorted(self._dag.get_dependents(current)):
                        if dependent_id in seen:
                            continue
                        seen.add(dependent_id)
                        if self._states.get(dependent_id) not in _TERMINAL_STATES:
                            self._states[dependent_id] = dag_engine.NodeState.SKIPPED
                        pending.append(dependent_id)
            # CONTINUE_ON_ERROR: retain non-terminal states so independent nodes run.

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

    Resolves the active DAG and WaveScheduler services on construction and coordinates
    execution through a cancellation event and per-node outcome records.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine.DAG = get_singleton(dag_engine.DAG)
        self._scheduler: dag_engine.WaveScheduler = get_singleton(dag_engine.WaveScheduler)
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}
        self._lock = threading.Lock()

    def _record(
        self,
        node_id: str,
        state: dag_engine.NodeState,
        value: Any,
        error: Optional[Exception],
        duration_seconds: float,
        retries_attempted: int,
    ) -> None:
        """Records the consolidated outcome of a single node execution."""
        record: dag_engine.NodeResult[Any] = dag_engine.NodeResult(
            node_id=node_id,
            state=state,
            value=value,
            error=error,
            duration_seconds=duration_seconds,
            retries_attempted=retries_attempted,
        )
        with self._lock:
            self._results[node_id] = record

    def _mark_remaining_cancelled(self) -> None:
        """Cancels every non-terminal node through the active scheduler."""
        scheduler = self._scheduler
        if isinstance(scheduler, WaveScheduler):
            scheduler._cancel_all()

    def _mark_remaining_skipped(self) -> None:
        """Skips nodes left unexecutable by upstream failure through the active scheduler."""
        scheduler = self._scheduler
        if isinstance(scheduler, WaveScheduler):
            scheduler._skip_blocked()

    def _node_timeout_error(
        self, definition: dag_engine.NodeDefinition[Any], attempt_seconds: float
    ) -> Optional[Exception]:
        """Returns a timeout error when a single attempt overruns the node timeout."""
        if (
            definition.timeout_seconds is not None
            and attempt_seconds > definition.timeout_seconds
        ):
            return dag_engine.DAGTimeoutError(
                f"Node '{definition.node_id}' exceeded its {definition.timeout_seconds} second timeout"
            )
        return None

    def _execute_node(
        self, definition: dag_engine.NodeDefinition[Any]
    ) -> Tuple[Any, Optional[Exception], float, int]:
        """Runs one node action with retry attempts, reifying any failure as a value."""
        started_at = time.monotonic()
        retries_attempted = 0
        while True:
            attempt_started = time.monotonic()
            try:
                value = definition.action()
            except Exception as error:  # cleanroom: allow-broad-exception
                # Reify the caught exception into the reported node outcome.
                duration = time.monotonic() - started_at
                timeout_error = self._node_timeout_error(
                    definition, time.monotonic() - attempt_started
                )
                if timeout_error is not None:
                    return (None, timeout_error, duration, retries_attempted)
                if retries_attempted < definition.retries:
                    retries_attempted += 1
                    time.sleep(min(0.1, 0.01 * (2 ** (retries_attempted - 1))))
                    continue
                return (None, error, time.monotonic() - started_at, retries_attempted)
            else:
                duration = time.monotonic() - started_at
                timeout_error = self._node_timeout_error(
                    definition, time.monotonic() - attempt_started
                )
                if timeout_error is not None:
                    return (None, timeout_error, duration, retries_attempted)
                return (value, None, duration, retries_attempted)

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 1,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        # Graph validity is a precondition of execution: cycles and dangling
        # dependencies surface immediately.
        self._dag.validate()
        started_at = time.monotonic()
        with self._lock:
            self._results = {}
        workers = max(1, max_concurrency)
        executor = ThreadPoolExecutor(max_workers=workers)
        running: Dict[Future[Tuple[Any, Optional[Exception], float, int]], str] = {}
        try:
            while True:
                # Abort on cancellation, cancelling all non-terminal nodes.
                if self._cancelled.is_set():
                    self._mark_remaining_cancelled()
                    raise dag_engine.DAGCancelledError("DAG execution was cancelled")
                # Enforce the overall execution timeout.
                elapsed = time.monotonic() - started_at
                if timeout_seconds is not None and elapsed > timeout_seconds:
                    raise dag_engine.DAGTimeoutError(
                        f"DAG execution exceeded the {timeout_seconds} second timeout"
                    )
                ready = self._scheduler.next_wave()
                capacity = workers - len(running)
                for node_id in ready[:capacity]:
                    self._scheduler.mark_running(node_id)
                    definition = self._dag.get_node(node_id)
                    running[executor.submit(self._execute_node, definition)] = node_id
                if not running:
                    # Nothing is executing and nothing else can become ready.
                    break
                wait_seconds = _POLL_INTERVAL_SECONDS
                if timeout_seconds is not None:
                    remaining = timeout_seconds - (time.monotonic() - started_at)
                    wait_seconds = max(0.0, min(wait_seconds, remaining))
                done, _pending = wait(
                    set(running.keys()),
                    return_when=FIRST_COMPLETED,
                    timeout=wait_seconds,
                )
                for future in done:
                    node_id = running.pop(future)
                    value, error, duration, retries_attempted = future.result()
                    if self._scheduler.get_state(node_id) is dag_engine.NodeState.CANCELLED:
                        # A failure policy cancelled the node while it was running.
                        self._record(
                            node_id,
                            dag_engine.NodeState.CANCELLED,
                            value,
                            None,
                            duration,
                            retries_attempted,
                        )
                        continue
                    if error is None:
                        self._record(
                            node_id,
                            dag_engine.NodeState.SUCCEEDED,
                            value,
                            None,
                            duration,
                            retries_attempted,
                        )
                        self._scheduler.mark_succeeded(node_id)
                    else:
                        self._record(
                            node_id,
                            dag_engine.NodeState.FAILED,
                            None,
                            error,
                            duration,
                            retries_attempted,
                        )
                        self._scheduler.mark_failed(node_id, failure_policy)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        # Nodes left unexecutable (typically downstream of a failure under
        # CONTINUE_ON_ERROR) reach the SKIPPED terminal state.
        self._mark_remaining_skipped()
        finished_at = time.monotonic()
        states = self._scheduler.get_all_states()
        succeeded = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine.NodeState.SUCCEEDED
            )
        )
        failed = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine.NodeState.FAILED
            )
        )
        skipped: Set[str] = {
            node_id
            for node_id, state in states.items()
            if state is dag_engine.NodeState.SKIPPED
        }
        cancelled = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine.NodeState.CANCELLED
            )
        )
        critical_path, _weight = self._dag.compute_critical_path(None)
        with self._lock:
            results = dict(self._results)
        return dag_engine.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=tuple(sorted(skipped)),
            cancelled_nodes=cancelled,
            wall_clock_seconds=finished_at - started_at,
            critical_path=tuple(critical_path),
            results=results,
        )

    @operation
    @override
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        with self._lock:
            self._cancelled.set()
        self._mark_remaining_cancelled()

    @operation
    @override
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
# LAST_CLEANED: 2026-11-08T16:58:54Z
# LAST_CHANGED: 2026-11-08T16:55:01Z
# CHANGE: Prune unreachable post-run skipped-node reclassification (span 678-682) since blocked nodes now reach the SKIPPED terminal state in run finalization, resolving the cov.unreachable_under_spec feedback for dag.runner.run.consolidated_report.
# COVERAGE_AUDIT: 2026-11-08T16:58:54Z
# QA_AUDIT: 2026-11-08T16:58:41Z
# --- END AUTOFAB METADATA ---
