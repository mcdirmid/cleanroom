# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_225951_deepseek-flash_dag_engine_combined
# Timestamp: 2026-11-09T22:59:51.893690+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 653,150
#   Cached Inbound Tokens:   38,066,304
#   Outbound Tokens:         604,328
#   Total Tokens:            39,323,782
#   Financial Cost ($USD):   $0.5748
#   Wall Clock Duration:     3169.10s
#   Step Latencies (s):      [228.5, 477.3, 20.3, 663.5, 202.5, 144.2, 157.1, 84.6, 290.6, 64.1, 71.8, 12.4, 20.3, 476.9, 71.6, 12.6, 20.4, 119.4, 71.5, 12.4, 10.1, 63.8, 247.9, 83.4, 12.3, 22.6, 22.6, 143.1, 104.6, 135.2, 125.0, 268.4, 145.8, 81.7, 20.3]
#   Role Execution Rounds:   coverage: 5, lib: 6, pretense: 4, pretense_coverage: 2, pretense_qa: 9, qa: 6, test: 3 (Total: 35)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       50
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Library specification for the DAG execution and wave scheduling engine."""

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
        # Exceptions retain their diagnostic message as the primary argument.
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
    @test_only
    def is_cancelled(self) -> bool:
        """Query accessor verifying whether cancellation has been signaled.

        Returns:
            True if cancellation status has been set, False otherwise.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:08:04Z
# LAST_CHANGED: 2026-11-09T23:08:04Z
# CHANGE: Implement dag_engine interface: @data_type records/exceptions with dataclass semantics and __str__, NodeState/FailurePolicy enums, and DAG/WaveScheduler/DAGRunner singleton protocols with operation stubs and test_only is_cancelled.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_impl.py ===
"""Concrete DAG execution and wave scheduling engine implementation."""

from __future__ import annotations

import heapq
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple, cast

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dag_engine

_TERMINAL_STATES = (
    dag_engine.NodeState.SUCCEEDED,
    dag_engine.NodeState.FAILED,
    dag_engine.NodeState.SKIPPED,
    dag_engine.NodeState.CANCELLED,
)


@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    Maintains the node definitions plus the upstream and downstream adjacency
    maps under a reentrant lock so that concurrent scheduling queries and graph
    mutations observe a consistent edge structure.
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
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        with self._lock:
            dependency_set = set(dependencies) if dependencies is not None else set()
            definition: dag_engine.NodeDefinition[Any] = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=frozenset(dependency_set),
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            # Node identifiers are unique, so the definition is registered directly.
            self._nodes[node_id] = definition
            # Re-registering an existing node must not discard edges that were
            # accumulated earlier (declared dependencies or explicit add_edge
            # calls).  The existing upstream adjacency is therefore retained and
            # merged with the newly declared dependency set instead of replaced.
            self._upstream.setdefault(node_id, set()).update(dependency_set)
            self._downstream.setdefault(node_id, set())
            # Each declared dependency contributes a directed edge to this node.
            for dependency in dependency_set:
                self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        with self._lock:
            # Both endpoints must already be registered in the graph.
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Upstream node '{upstream_id}' not found in DAG", upstream_id
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Downstream node '{downstream_id}' not found in DAG", downstream_id
                )
            # Only the adjacency maps change; registered definitions stay untouched.
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found in DAG", node_id
                )
            # Purge every incident edge before dropping the node itself.
            for upstream in self._upstream.get(node_id, set()):
                self._downstream.get(upstream, set()).discard(node_id)
            for downstream in self._downstream.get(node_id, set()):
                self._upstream.get(downstream, set()).discard(node_id)
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
        with self._lock:
            definition = self._nodes.get(node_id)
            if definition is None:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found in DAG", node_id
                )
            return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found in DAG", node_id
                )
            return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found in DAG", node_id
                )
            return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        with self._lock:
            return set(self._nodes.keys())

    def _find_cycle(self) -> List[str]:
        """Depth-first search returning the node sequence of the first cycle found."""
        registered = set(self._nodes)
        colors: Dict[str, int] = {node_id: 0 for node_id in registered}
        path: List[str] = []

        def visit(node_id: str) -> List[str]:
            colors[node_id] = 1
            path.append(node_id)
            # Only registered nodes participate in cycle detection traversal.
            for dependency in sorted(self._upstream.get(node_id, set()) & registered):
                if colors[dependency] == 1:
                    return list(path[path.index(dependency):])
                if colors[dependency] == 0:
                    cycle = visit(dependency)
                    if cycle:
                        return cycle
            path.pop()
            colors[node_id] = 2
            return []

        for node_id in sorted(self._nodes):
            if colors[node_id] == 0:
                cycle = visit(node_id)
                if cycle:
                    return cycle
        return []

    @operation
    @override
    def validate(self) -> None:
        with self._lock:
            # Every referenced dependency must be a registered node.
            for node_id in sorted(self._nodes):
                for dependency in sorted(self._upstream.get(node_id, set())):
                    if dependency not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            f"Node '{dependency}' referenced by '{node_id}' not found in DAG",
                            dependency,
                        )
            # A consistent graph ordered by the depth-first search must be acyclic.
            cycle = self._find_cycle()
            if cycle:
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}", tuple(cycle)
                )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        with self._lock:
            in_degree: Dict[str, int] = {}
            for node_id in self._nodes:
                in_degree[node_id] = sum(
                    1
                    for dependency in self._upstream.get(node_id, set())
                    if dependency in self._nodes
                )
            # Ready nodes are ordered by priority descending, then identifier ascending.
            ready: List[Tuple[int, str]] = [
                (-self._nodes[node_id].priority, node_id)
                for node_id in self._nodes
                if in_degree[node_id] == 0
            ]
            heapq.heapify(ready)
            registered = set(in_degree)
            ordered: List[str] = []
            while ready:
                _, node_id = heapq.heappop(ready)
                ordered.append(node_id)
                # Dependents of a registered node are themselves registered.
                for downstream in sorted(self._downstream.get(node_id, set()) & registered):
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        heapq.heappush(
                            ready, (-self._nodes[downstream].priority, downstream)
                        )
            if len(ordered) != len(self._nodes):
                cycle = self._find_cycle()
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}", tuple(cycle)
                )
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
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        with self._lock:
            ordered = self.topological_sort()
            if not ordered:
                return ([], 0.0)
            weight: Dict[str, float] = {}
            for node_id in ordered:
                if estimated_durations is None:
                    weight[node_id] = 1.0
                else:
                    weight[node_id] = estimated_durations.get(node_id, 1.0)
            finish: Dict[str, float] = {}
            predecessor: Dict[str, Optional[str]] = {}
            for node_id in ordered:
                best_finish = 0.0
                best_predecessor: Optional[str] = None
                # Predecessors already finished in topological order are path candidates.
                for dependency in sorted(self._upstream.get(node_id, set()) & set(finish)):
                    if best_predecessor is None or finish[dependency] > best_finish:
                        best_finish = finish[dependency]
                        best_predecessor = dependency
                finish[node_id] = best_finish + weight[node_id]
                predecessor[node_id] = best_predecessor
            terminal = ordered[0]
            total = finish[terminal]
            for node_id in ordered:
                if finish[node_id] > total:
                    total = finish[node_id]
                    terminal = node_id
            path: List[str] = []
            cursor: Optional[str] = terminal
            while cursor is not None:
                path.append(cursor)
                cursor = predecessor[cursor]
            path.reverse()
            return (path, total)


@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    Scheduling state is synchronized on demand against the nodes currently
    registered in the collaborating DAG service.
    """

    tier = system

    def __init__(self) -> None:
        self._dag = get_singleton(dag_engine.DAG)
        self._states: Dict[str, dag_engine.NodeState] = {}
        self._lock = threading.RLock()

    def _sync_states(self) -> None:
        """Discovers registered nodes and synchronizes their scheduling states."""
        nodes = self._dag.all_nodes()
        for node_id in nodes:
            dependencies = self._dag.get_dependencies(node_id)
            satisfied = all(
                self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                for dependency in dependencies
            )
            current = self._states.get(node_id)
            # Pending and ready classifications track the current edge structure.
            if current is None or current in (
                dag_engine.NodeState.PENDING,
                dag_engine.NodeState.READY,
            ):
                if satisfied:
                    self._states[node_id] = dag_engine.NodeState.READY
                else:
                    self._states[node_id] = dag_engine.NodeState.PENDING
        for node_id in list(self._states):
            if node_id not in nodes:
                del self._states[node_id]

    def _cancel_non_terminal(self) -> None:
        """Internal helper: transitions all remaining non-terminal nodes to CANCELLED."""
        with self._lock:
            self._sync_states()
            for node_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[node_id] = dag_engine.NodeState.CANCELLED

    def _cancel_unstarted(self) -> None:
        """Internal helper: transitions only unstarted (PENDING/READY) nodes to CANCELLED.

        Nodes already in the RUNNING state stay non-terminal because an abort only
        withdraws work that has not begun yet.
        """
        with self._lock:
            self._sync_states()
            for node_id, state in self._states.items():
                if state in (
                    dag_engine.NodeState.PENDING,
                    dag_engine.NodeState.READY,
                ):
                    self._states[node_id] = dag_engine.NodeState.CANCELLED

    def _skip_non_terminal(self) -> None:
        """Internal helper: transitions stranded non-terminal nodes to SKIPPED."""
        with self._lock:
            self._sync_states()
            for node_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[node_id] = dag_engine.NodeState.SKIPPED

    @operation
    @override
    def next_wave(self) -> List[str]:
        with self._lock:
            self._sync_states()
            candidates: List[Tuple[int, str]] = []
            for node_id, state in self._states.items():
                if state is not dag_engine.NodeState.READY:
                    continue
                dependencies = self._dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    candidates.append(
                        (-self._dag.get_node(node_id).priority, node_id)
                    )
            candidates.sort()
            return [node_id for _, node_id in candidates]

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        with self._lock:
            self._sync_states()
            self._states[node_id] = dag_engine.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        with self._lock:
            self._sync_states()
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # Downstream dependents become READY once every prerequisite succeeded.
            for dependent in sorted(self._dag.get_dependents(node_id)):
                if self._states.get(dependent) is not dag_engine.NodeState.PENDING:
                    continue
                dependencies = self._dag.get_dependencies(dependent)
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    self._states[dependent] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self, node_id: str, failure_policy: dag_engine.FailurePolicy
    ) -> None:
        with self._lock:
            self._sync_states()
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy is dag_engine.FailurePolicy.FAIL_FAST:
                # Abort the run: every node that has not reached a terminal state is cancelled.
                for other_id, state in self._states.items():
                    if other_id == node_id:
                        continue
                    if state not in _TERMINAL_STATES:
                        self._states[other_id] = dag_engine.NodeState.CANCELLED
            elif failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # Skip every transitive dependent of the failed node.
                remaining = list(self._dag.get_dependents(node_id))
                visited: Set[str] = set()
                while remaining:
                    dependent = remaining.pop()
                    if dependent in visited:
                        continue
                    visited.add(dependent)
                    if self._states.get(dependent) not in _TERMINAL_STATES:
                        self._states[dependent] = dag_engine.NodeState.SKIPPED
                    remaining.extend(self._dag.get_dependents(dependent))
            # CONTINUE_ON_ERROR: independent nodes keep their current eligibility.

    @operation
    @override
    def is_finished(self) -> bool:
        with self._lock:
            self._sync_states()
            return all(state in _TERMINAL_STATES for state in self._states.values())

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine.NodeState:
        with self._lock:
            self._sync_states()
            return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        with self._lock:
            self._sync_states()
            return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine.DAGRunner):
    """Concrete realization of concurrent DAG execution runner.

    Coordinates the collaborating DAG and WaveScheduler services while recording
    node outcomes and applying failure policies and cancellation semantics.
    """

    tier = system

    def __init__(self) -> None:
        self._dag = get_singleton(dag_engine.DAG)
        # The concrete scheduler backs the internal abort and stranded-node helpers.
        self._scheduler: WaveScheduler = cast(
            WaveScheduler, get_singleton(dag_engine.WaveScheduler)
        )
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}
        self._lock = threading.Lock()

    def _execute_node(
        self, definition: dag_engine.NodeDefinition[Any]
    ) -> dag_engine.NodeResult[Any]:
        """Executes a node action, retrying failures up to the configured count."""
        started = time.monotonic()
        retries_attempted = 0
        while True:
            try:
                value = definition.action()
                return dag_engine.NodeResult(
                    node_id=definition.node_id,
                    state=dag_engine.NodeState.SUCCEEDED,
                    value=value,
                    duration_seconds=time.monotonic() - started,
                    retries_attempted=retries_attempted,
                )
            except Exception as error:  # reified into the result record below
                if retries_attempted < definition.retries:
                    retries_attempted += 1
                    time.sleep(0.01)
                    continue
                return dag_engine.NodeResult(
                    node_id=definition.node_id,
                    state=dag_engine.NodeState.FAILED,
                    error=error,
                    duration_seconds=time.monotonic() - started,
                    retries_attempted=retries_attempted,
                )

    def _cancel_remaining(self) -> None:
        """Cancels every remaining non-terminal node through the scheduler service."""
        cancel = getattr(self._scheduler, "_cancel_non_terminal", None)
        if callable(cancel):
            cancel()

    def _cancel_unstarted_remaining(self) -> None:
        """Cancels only not-yet-started nodes through the scheduler service."""
        cancel = getattr(self._scheduler, "_cancel_unstarted", None)
        if callable(cancel):
            cancel()

    def _skip_remaining(self) -> None:
        """Skips every stranded non-terminal node through the scheduler service."""
        skip = getattr(self._scheduler, "_skip_non_terminal", None)
        if callable(skip):
            skip()

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: dag_engine.FailurePolicy,
        max_concurrency: int,
    ) -> dag_engine.DAGRunReport:
        # Missing dependencies and cycles abort before any node action executes.
        self._dag.validate()
        started = time.monotonic()
        with self._lock:
            self._results.clear()
        workers = max_concurrency if max_concurrency > 0 else 1
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while True:
                if self._cancelled.is_set():
                    # Aborting marks remaining nodes cancelled before propagating.
                    self._cancel_remaining()
                    raise dag_engine.DAGCancelledError("DAG execution was cancelled")
                if (
                    timeout_seconds is not None
                    and time.monotonic() - started > timeout_seconds
                ):
                    raise dag_engine.DAGTimeoutError(
                        f"DAG execution exceeded timeout of {timeout_seconds} seconds"
                    )
                if self._scheduler.is_finished():
                    break
                wave = self._scheduler.next_wave()
                if not wave:
                    # No node can make progress; stranded nodes are skipped.
                    self._skip_remaining()
                    continue
                for node_id in wave:
                    self._scheduler.mark_running(node_id)
                futures = [
                    executor.submit(self._execute_node, self._dag.get_node(node_id))
                    for node_id in wave
                ]
                wave_results = [future.result() for future in futures]
                # A cancellation raised by a node action aborts before outcomes apply.
                if self._cancelled.is_set():
                    self._cancel_remaining()
                    raise dag_engine.DAGCancelledError("DAG execution was cancelled")
                for result in wave_results:
                    with self._lock:
                        self._results[result.node_id] = result
                    if result.state is dag_engine.NodeState.SUCCEEDED:
                        self._scheduler.mark_succeeded(result.node_id)
                    else:
                        self._scheduler.mark_failed(result.node_id, failure_policy)
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
        skipped = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine.NodeState.SKIPPED
            )
        )
        cancelled = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine.NodeState.CANCELLED
            )
        )
        critical_path, _ = self._dag.compute_critical_path(None)
        with self._lock:
            results = dict(self._results)
        return dag_engine.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=time.monotonic() - started,
            critical_path=tuple(critical_path),
            results=results,
        )

    @operation
    @override
    def cancel(self) -> None:
        # Signal the run loop to abort and withdraw only unstarted work: nodes
        # that are already RUNNING must stay non-terminal until they finish.
        self._cancelled.set()
        self._cancel_unstarted_remaining()

    @operation
    @override
    @test_only
    def is_cancelled(self) -> bool:
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
# LAST_CLEANED: 2026-11-09T23:52:28Z
# LAST_CHANGED: 2026-11-09T23:35:39Z
# CHANGE: Resolve pretense_qa cancel-scope feedback: DAGRunner.cancel now cancels only unstarted nodes (PENDING/READY) via new WaveScheduler._cancel_unstarted, leaving RUNNING nodes non-terminal so an abort withdraws only work that has not begun; run() abort paths keep _cancel_non_terminal per dag.runner.run.abort_on_cancel.
# COVERAGE_AUDIT: 2026-11-09T23:36:16Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:52:28Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:52:06Z
# QA_AUDIT: 2026-11-09T23:36:01Z
# --- END AUTOFAB METADATA ---
