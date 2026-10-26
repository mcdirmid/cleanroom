# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_203344_gemini-4-argon_dag_engine_baseline
# Timestamp: 2026-10-23T20:33:44.835433+00:00
# Benchmark Task: dag_engine
# Model: gemini-4-argon (Tier 4)
# Methodology: baseline
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 160,634
#   Cached Inbound Tokens:   2,206,462
#   Outbound Tokens:         31,253
#   Total Tokens:            2,398,349
#   Financial Cost ($USD):   $1.7370
#   Wall Clock Duration:     381.32s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       16
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Low-level interface for the DAG execution and wave scheduling engine."""

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

    pass


@data_type
@dataclass(frozen=True)
class DAGCancelledError(DAGError):
    """Raised when DAG execution is explicitly cancelled."""

    pass


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
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        timeout_seconds: Optional[float] = None,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph.

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
            timeout_seconds: Optional per-node execution timeout.
            retries: Number of permitted retry attempts upon exception.

        POSTCONDITIONS:
        - MUST register the node definition into the graph.
        - WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
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

        POSTCONDITIONS:
        - MUST establish a directed dependency edge from upstream_id to downstream_id.
        - WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph.

        POSTCONDITIONS:
        - MUST remove the node and its incident edges.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
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

        POSTCONDITIONS:
        - MUST return the NodeDefinition matching node_id.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
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

        POSTCONDITIONS:
        - MUST return all direct upstream dependencies.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
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

        POSTCONDITIONS:
        - MUST return all direct downstream dependents.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
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

        POSTCONDITIONS:
        - WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        - WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        - WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
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

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and name ascending.
        - WHEN a cycle exists, MUST raise CycleError.
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
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        Args:
            estimated_durations: Optional mapping of node identifiers to duration weights.
                Defaults to 1.0 per node if omitted.

        Returns:
            Tuple of (critical path node identifiers, total path weight).

        POSTCONDITIONS:
        - MUST return the sequence of nodes that forms the longest path through the DAG.
        - MUST return the cumulative weight of that path.
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

        POSTCONDITIONS:
        - MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        - MUST order returned nodes by priority descending, then node_id ascending.
        - WHEN no nodes are ready, MUST return an empty list.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.

        POSTCONDITIONS:
        - MUST update the node state to RUNNING.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.

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

        Args:
            node_id: Identifier of the failed node.
            failure_policy: Failure policy applied upon failure. Defaults to FAIL_FAST.

        POSTCONDITIONS:
        - MUST update the node state to FAILED.
        - WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        - WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.

        POSTCONDITIONS:
        - WHEN all nodes in the DAG have reached terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED), MUST return True.
        - WHEN any node in the DAG is not in a terminal state, MUST return False.
        - WHEN the DAG contains no nodes, MUST return True.
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
        timeout_seconds: Optional[float] = None,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> DAGRunReport:
        """Executes the entire DAG to completion or failure.

        Args:
            timeout_seconds: Optional overall execution timeout in seconds.
            failure_policy: Failure policy applied upon node action failure. Defaults to FAIL_FAST.
            max_concurrency: Maximum number of worker threads for concurrent wave execution. Defaults to 4.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        Raises:
            DAGTimeoutError: If execution exceeds timeout_seconds.
            DAGCancelledError: If cancel() is invoked during execution.

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


# === File: dag_engine_impl.py ===
"""Concrete implementation for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
import heapq
import threading
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
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
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


@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    - Synchronizes graph mutations and queries using threading.RLock for thread safety.
    """

    tier = system

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
            deps_frozenset = frozenset(dependencies) if dependencies is not None else frozenset()
            node_def = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=deps_frozenset,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._nodes[node_id] = node_def
            self._upstream.setdefault(node_id, set())
            self._downstream.setdefault(node_id, set())
            for dep in deps_frozenset:
                self._upstream[node_id].add(dep)
                self._downstream.setdefault(dep, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        with self._lock:
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Upstream node '{upstream_id}' not found in DAG",
                    node_id=upstream_id,
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Downstream node '{downstream_id}' not found in DAG",
                    node_id=downstream_id,
                )
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)
            old_def = self._nodes[downstream_id]
            if upstream_id not in old_def.dependencies:
                self._nodes[downstream_id] = dag_engine.NodeDefinition(
                    node_id=old_def.node_id,
                    action=old_def.action,
                    dependencies=frozenset(old_def.dependencies | {upstream_id}),
                    priority=old_def.priority,
                    timeout_seconds=old_def.timeout_seconds,
                    retries=old_def.retries,
                )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        with self._lock:
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    message=f"Node '{node_id}' not found in DAG",
                    node_id=node_id,
                )
            for up_id in list(self._upstream[node_id]):
                self._downstream[up_id].discard(node_id)
            for down_id in list(self._downstream[node_id]):
                self._upstream[down_id].discard(node_id)
                old_def = self._nodes[down_id]
                self._nodes[down_id] = dag_engine.NodeDefinition(
                    node_id=old_def.node_id,
                    action=old_def.action,
                    dependencies=frozenset(old_def.dependencies - {node_id}),
                    priority=old_def.priority,
                    timeout_seconds=old_def.timeout_seconds,
                    retries=old_def.retries,
                )
            del self._nodes[node_id]
            del self._upstream[node_id]
            del self._downstream[node_id]

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
                    message=f"Node '{node_id}' not found in DAG",
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
                    message=f"Node '{node_id}' not found in DAG",
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
                    message=f"Node '{node_id}' not found in DAG",
                    node_id=node_id,
                )
            return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        with self._lock:
            return set(self._nodes.keys())

    def _find_cycle_dfs(self) -> Optional[Tuple[str, ...]]:
        """Detects a directed cycle using DFS path tracking and returns the cycle tuple."""
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        path: List[str] = []

        def dfs(curr: str) -> Optional[Tuple[str, ...]]:
            visited.add(curr)
            in_stack.add(curr)
            path.append(curr)

            for neighbor in sorted(self._downstream.get(curr, ())):
                if neighbor in in_stack:
                    idx = path.index(neighbor)
                    return tuple(path[idx:] + [neighbor])
                if neighbor not in visited and neighbor in self._nodes:
                    res = dfs(neighbor)
                    if res is not None:
                        return res

            path.pop()
            in_stack.remove(curr)
            return None

        for node_id in sorted(self._nodes.keys()):
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle is not None:
                    return cycle
        return None

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        with self._lock:
            for node_id in sorted(self._nodes.keys()):
                for dep_id in sorted(self._upstream.get(node_id, ())):
                    if dep_id not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            message=f"Node '{node_id}' references missing dependency '{dep_id}'",
                            node_id=dep_id,
                        )
            cycle = self._find_cycle_dfs()
            if cycle is not None:
                raise dag_engine.CycleError(
                    message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                    cycle=cycle,
                )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        with self._lock:
            in_degree: Dict[str, int] = {
                node_id: len(self._upstream[node_id]) for node_id in self._nodes
            }

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
                        down_prio = self._nodes[down_id].priority
                        heapq.heappush(heap, (-down_prio, down_id))

            if len(result) < len(self._nodes):
                cycle = self._find_cycle_dfs()
                assert cycle is not None
                raise dag_engine.CycleError(
                    message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                    cycle=cycle,
                )

            return result

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if len(self._upstream[node_id]) == 0
            }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if len(self._downstream[node_id]) == 0
            }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        with self._lock:
            topo_order = self.topological_sort()
            if not topo_order:
                return ([], 0.0)

            dist: Dict[str, float] = {}
            predecessor: Dict[str, Optional[str]] = {}

            for node_id in topo_order:
                weight = (
                    float(estimated_durations.get(node_id, 1.0))
                    if estimated_durations is not None
                    else 1.0
                )
                max_prev_dist = 0.0
                best_pred: Optional[str] = None
                for up_id in sorted(self._upstream[node_id]):
                    if best_pred is None or dist[up_id] > max_prev_dist:
                        max_prev_dist = dist[up_id]
                        best_pred = up_id
                dist[node_id] = max_prev_dist + weight
                predecessor[node_id] = best_pred

            best_end_node = topo_order[0]
            max_total = dist[best_end_node]
            for node_id in topo_order[1:]:
                if dist[node_id] > max_total:
                    max_total = dist[node_id]
                    best_end_node = node_id

            path: List[str] = []
            curr: Optional[str] = best_end_node
            while curr is not None:
                path.append(curr)
                curr = predecessor[curr]
            path.reverse()
            return (path, max_total)


@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine.DAG).
    - Maintains scheduling state across _dag, _states mapping, and _lock.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine.NodeState.READY and non-root nodes to dag_engine.NodeState.PENDING.
    """

    tier = system

    def __init__(self, dag: Optional[dag_engine.DAG] = None) -> None:
        self._lock = threading.RLock()
        self._dag: Optional[dag_engine.DAG] = dag
        self._states: Dict[str, dag_engine.NodeState] = {}

    def initialize(self) -> None:
        """Initializes the WaveScheduler by resolving the DAG singleton."""
        self._sync_states()

    def _get_dag(self) -> dag_engine.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        return self._dag

    def _sync_states(self) -> dag_engine.DAG:
        dag = self._get_dag()
        current_nodes = dag.all_nodes()
        roots = dag.find_roots()
        for existing_id in list(self._states.keys()):
            if existing_id not in current_nodes:
                del self._states[existing_id]
        for node_id in current_nodes:
            if node_id not in self._states:
                self._states[node_id] = (
                    dag_engine.NodeState.READY
                    if node_id in roots
                    else dag_engine.NodeState.PENDING
                )
        return dag

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        with self._lock:
            dag = self._sync_states()
            ready_candidates: List[str] = []
            for node_id, state in self._states.items():
                if state == dag_engine.NodeState.READY:
                    deps = dag.get_dependencies(node_id)
                    if all(
                        self._states.get(d) == dag_engine.NodeState.SUCCEEDED
                        for d in deps
                    ):
                        ready_candidates.append(node_id)
            ready_candidates.sort(
                key=lambda nid: (-dag.get_node(nid).priority, nid)
            )
            return ready_candidates

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
            for down_id in dag.get_dependents(node_id):
                if self._states.get(down_id) == dag_engine.NodeState.PENDING:
                    up_deps = dag.get_dependencies(down_id)
                    if all(
                        self._states.get(u) == dag_engine.NodeState.SUCCEEDED
                        for u in up_deps
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
            dag = self._sync_states()
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy == dag_engine.FailurePolicy.FAIL_FAST:
                for nid, st in list(self._states.items()):
                    if st not in _TERMINAL_STATES:
                        self._states[nid] = dag_engine.NodeState.CANCELLED
            elif failure_policy == dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                queue: deque[str] = deque(dag.get_dependents(node_id))
                visited: Set[str] = set()
                while queue:
                    curr = queue.popleft()
                    if curr in visited:
                        continue
                    visited.add(curr)
                    if self._states.get(curr) not in _TERMINAL_STATES:
                        self._states[curr] = dag_engine.NodeState.SKIPPED
                    for child in dag.get_dependents(curr):
                        queue.append(child)

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        with self._lock:
            dag = self._sync_states()
            all_nodes = dag.all_nodes()
            if not all_nodes:
                return True
            return all(
                node_id in self._states and self._states[node_id] in _TERMINAL_STATES
                for node_id in all_nodes
            )

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

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine.DAG) and WaveScheduler service via get_singleton(dag_engine.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, _cancelled event, and _results mapping.
    - Synchronizes runner state using threading.Lock.
    """

    tier = system

    def __init__(
        self,
        dag: Optional[dag_engine.DAG] = None,
        scheduler: Optional[dag_engine.WaveScheduler] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._dag: Optional[dag_engine.DAG] = dag
        self._scheduler: Optional[dag_engine.WaveScheduler] = scheduler
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}

    def initialize(self) -> None:
        """Initializes the DAGRunner by resolving DAG and WaveScheduler singletons."""
        self._get_dag()
        self._get_scheduler()

    def _get_dag(self) -> dag_engine.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine.DAG)
        return self._dag

    def _get_scheduler(self) -> dag_engine.WaveScheduler:
        if self._scheduler is None:
            self._scheduler = get_singleton(dag_engine.WaveScheduler)
        return self._scheduler

    def _cancel_non_terminal_nodes(self, scheduler: dag_engine.WaveScheduler) -> None:
        assert isinstance(scheduler, WaveScheduler)
        with scheduler._lock:
            scheduler._sync_states()
            for nid, st in list(scheduler._states.items()):
                if st not in _TERMINAL_STATES:
                    scheduler._states[nid] = dag_engine.NodeState.CANCELLED

    def _skip_non_terminal_nodes(self, scheduler: dag_engine.WaveScheduler) -> None:
        assert isinstance(scheduler, WaveScheduler)
        with scheduler._lock:
            for nid, st in list(scheduler._states.items()):
                if st not in _TERMINAL_STATES:
                    scheduler._states[nid] = dag_engine.NodeState.SKIPPED

    def _execute_single_node(
        self, node_def: dag_engine.NodeDefinition[Any]
    ) -> dag_engine.NodeResult[Any]:
        start_time = time.monotonic()
        attempts = 0
        max_retries = max(0, node_def.retries)
        while True:
            try:
                val = node_def.action()
                elapsed = time.monotonic() - start_time
                return dag_engine.NodeResult(
                    node_id=node_def.node_id,
                    state=dag_engine.NodeState.SUCCEEDED,
                    value=val,
                    error=None,
                    duration_seconds=elapsed,
                    retries_attempted=attempts,
                )
            except Exception as exc:
                if attempts < max_retries:
                    attempts += 1
                    continue
                elapsed = time.monotonic() - start_time
                return dag_engine.NodeResult(
                    node_id=node_def.node_id,
                    state=dag_engine.NodeState.FAILED,
                    value=None,
                    error=exc,
                    duration_seconds=elapsed,
                    retries_attempted=attempts,
                )

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        dag = self._get_dag()
        scheduler = self._get_scheduler()

        dag.validate()

        start_wall_clock = time.monotonic()
        with self._lock:
            self._results.clear()

        workers = max(1, max_concurrency)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while not scheduler.is_finished():
                if self._cancelled.is_set():
                    self._cancel_non_terminal_nodes(scheduler)
                    raise dag_engine.DAGCancelledError(
                        message="DAG execution was cancelled"
                    )

                if (
                    timeout_seconds is not None
                    and (time.monotonic() - start_wall_clock) > timeout_seconds
                ):
                    raise dag_engine.DAGTimeoutError(
                        message=f"DAG execution exceeded timeout of {timeout_seconds}s"
                    )

                wave = scheduler.next_wave()
                if not wave:
                    self._skip_non_terminal_nodes(scheduler)
                    break

                futures = {}
                for node_id in wave:
                    scheduler.mark_running(node_id)
                    node_def = dag.get_node(node_id)
                    futures[node_id] = executor.submit(
                        self._execute_single_node, node_def
                    )

                for node_id in wave:
                    res = futures[node_id].result()
                    if self._cancelled.is_set():
                        self._cancel_non_terminal_nodes(scheduler)
                        raise dag_engine.DAGCancelledError(
                            message="DAG execution was cancelled"
                        )
                    if (
                        timeout_seconds is not None
                        and (time.monotonic() - start_wall_clock) > timeout_seconds
                    ):
                        raise dag_engine.DAGTimeoutError(
                            message=f"DAG execution exceeded timeout of {timeout_seconds}s"
                        )

                    with self._lock:
                        self._results[node_id] = res

                    if res.state == dag_engine.NodeState.SUCCEEDED:
                        scheduler.mark_succeeded(node_id)
                    else:
                        scheduler.mark_failed(node_id, failure_policy=failure_policy)

        wall_clock_seconds = time.monotonic() - start_wall_clock
        all_states = scheduler.get_all_states()

        with self._lock:
            for nid, st in all_states.items():
                if nid not in self._results:
                    self._results[nid] = dag_engine.NodeResult(
                        node_id=nid,
                        state=st,
                        value=None,
                        error=None,
                        duration_seconds=0.0,
                        retries_attempted=0,
                    )
            results_snapshot = dict(self._results)

        durations = {
            nid: res.duration_seconds for nid, res in results_snapshot.items()
        }
        crit_path_list, _ = dag.compute_critical_path(estimated_durations=durations)

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

        return dag_engine.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(crit_path_list),
            results=results_snapshot,
        )

    @operation
    @override
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        self._cancelled.set()
        scheduler = self._get_scheduler()
        self._cancel_non_terminal_nodes(scheduler)


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
