# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261022_214110_deepseek-flash_dag_engine
# Timestamp: 2026-10-22T21:41:10.887579+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 266,408
#   Cached Inbound Tokens:   19,357,952
#   Outbound Tokens:         307,526
#   Total Tokens:            19,931,886
#   Financial Cost ($USD):   $0.2826
#   Wall Clock Duration:     1586.81s
#   Step Latencies (s):      [301.1, 311.4, 20.0, 340.8, 80.3, 130.6, 20.0, 100.2, 60.3, 100.4, 20.0, 150.3, 70.2, 50.1, 80.2, 20.1, 40.1, 80.2, 20.1, 20.0]
#   Turn Latencies (s):      [301.1, 311.4, 20.0, 340.8, 80.3, 130.6, 20.0, 100.2, 60.3, 100.4, 20.0, 150.3, 70.2, 50.1, 80.2, 20.1, 40.1, 80.2, 20.1, 20.0]
#   Role Execution Rounds:   coverage: 5, lib: 4, qa: 6, test: 5 (Total: 20)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       57
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


@data_type
@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """
    message: str

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


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
    ...


@data_type
@dataclass(frozen=True)
class DAGCancelledError(DAGError):
    """Raised when DAG execution is explicitly cancelled."""
    ...


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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T21:46:20Z
# LAST_CHANGED: 2026-10-22T21:46:20Z
# CHANGE: Implement DAG interface protocols (DAG, WaveScheduler, DAGRunner), node/result data types, error hierarchy, and scheduling enums per low/dag_engine.pyi
# --- END CLEANROOM METADATA ---


# === File: dag_engine_impl.py ===
"""Library implementation for the DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton
from . import dag_engine

_TERMINAL_STATES: FrozenSet[dag_engine.NodeState] = frozenset(
    {
        dag_engine.NodeState.SUCCEEDED,
        dag_engine.NodeState.FAILED,
        dag_engine.NodeState.SKIPPED,
        dag_engine.NodeState.CANCELLED,
    }
)

_RETRY_BACKOFF_SECONDS = 0.01

_POLL_INTERVAL_SECONDS = 0.05


@singleton_type("system")
class DAG(dag_engine.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    - Synchronizes graph mutations and queries using threading.RLock for thread safety.
    """

    tier = "system"

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
        """Adds a task node to the graph.

        GROUNDING:
        - Acquires _lock, constructs immutable dag_engine.NodeDefinition with frozen dependency set.
        - Inserts definition into _nodes, registering empty neighbor sets in _upstream and _downstream if absent.
        - Adds directed edges from each dependency to node_id.
        """
        with self._lock:
            definition = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=frozenset(dependencies or ()),
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            # POSTCONDITION: register the node definition into the graph.
            self._nodes[node_id] = definition
            self._upstream.setdefault(node_id, set())
            self._downstream.setdefault(node_id, set())
            # POSTCONDITION: add directed dependency edges from each dependency to node_id.
            for dependency in definition.dependencies:
                self._upstream[node_id].add(dependency)
                self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        GROUNDING:
        - Acquires _lock, verifies presence of upstream_id and downstream_id in _nodes.
        - Raises dag_engine.NodeNotFoundError if either identifier is missing.
        - Updates _upstream and _downstream sets.
        """
        with self._lock:
            # WHEN either node identifier is missing, MUST raise NodeNotFoundError.
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Upstream node '{upstream_id}' not found", upstream_id
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Downstream node '{downstream_id}' not found", downstream_id
                )
            # POSTCONDITION: establish a directed dependency edge upstream -> downstream.
            self._upstream.setdefault(downstream_id, set()).add(upstream_id)
            self._downstream.setdefault(upstream_id, set()).add(downstream_id)
            definition = self._nodes[downstream_id]
            self._nodes[downstream_id] = dag_engine.NodeDefinition(
                node_id=definition.node_id,
                action=definition.action,
                dependencies=frozenset(self._upstream[downstream_id]),
                priority=definition.priority,
                timeout_seconds=definition.timeout_seconds,
                retries=definition.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        GROUNDING:
        - Acquires _lock, verifies presence of node_id in _nodes.
        - Raises dag_engine.NodeNotFoundError if absent.
        - Removes node_id from all incident upstream and downstream neighbor sets.
        - Deletes node_id from _nodes, _upstream, and _downstream.
        """
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found", node_id
                )
            # POSTCONDITION: remove the node and its incident edges.
            for dependency in self._upstream.get(node_id, set()):
                self._downstream.get(dependency, set()).discard(node_id)
            for dependent in self._downstream.get(node_id, set()):
                self._upstream.get(dependent, set()).discard(node_id)
            self._nodes.pop(node_id, None)
            self._upstream.pop(node_id, None)
            self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        GROUNDING:
        - Acquires _lock, checks membership of node_id in _nodes.
        """
        with self._lock:
            return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        GROUNDING:
        - Acquires _lock, looks up node_id in _nodes.
        - Raises dag_engine.NodeNotFoundError if node_id is not present.
        """
        with self._lock:
            # POSTCONDITION: return the NodeDefinition matching node_id.
            if node_id not in self._nodes:
                # WHEN node_id is absent, MUST raise NodeNotFoundError.
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found", node_id
                )
            return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        GROUNDING:
        - Acquires _lock, verifies node_id in _nodes, raising dag_engine.NodeNotFoundError if missing.
        - Returns a copy of _upstream[node_id].
        """
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found", node_id
                )
            # POSTCONDITION: return all direct upstream dependencies.
            return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        GROUNDING:
        - Acquires _lock, verifies node_id in _nodes, raising dag_engine.NodeNotFoundError if missing.
        - Returns a copy of _downstream[node_id].
        """
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' not found", node_id
                )
            # POSTCONDITION: return all direct downstream dependents.
            return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        GROUNDING:
        - Acquires _lock, returns a set copy of keys in _nodes.
        """
        with self._lock:
            return set(self._nodes)

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        GROUNDING:
        - Acquires _lock.
        - Checks that all referenced dependencies exist in _nodes; raises dag_engine.NodeNotFoundError on first missing dependency.
        - Detects cycles using depth-first search path tracking.
        - On cycle detection, constructs the cyclic node sequence and raises dag_engine.CycleError.
        """
        with self._lock:
            # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
            for node_id in sorted(self._nodes):
                for dependency in sorted(self._upstream.get(node_id, set())):
                    if dependency not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            f"Node '{node_id}' depends on missing node '{dependency}'",
                            dependency,
                        )
            # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
            cycle = self._find_cycle()
            if cycle is not None:
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}", tuple(cycle)
                )

    def _find_cycle(self) -> Optional[List[str]]:
        """Detects a directed cycle using depth-first search path tracking."""
        visited: Set[str] = set()
        path: List[str] = []
        on_path: Set[str] = set()

        def visit(node_id: str) -> Optional[List[str]]:
            if node_id in on_path:
                start = path.index(node_id)
                return path[start:] + [node_id]
            if node_id in visited:
                return None
            visited.add(node_id)
            path.append(node_id)
            on_path.add(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                found = visit(dependency)
                if found is not None:
                    return found
            path.pop()
            on_path.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            found = visit(node_id)
            if found is not None:
                return found
        return None

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        GROUNDING:
        - Acquires _lock.
        - Computes in-degrees for all nodes from _upstream.
        - Initializes min-heap or sorted ready queue of zero-in-degree nodes ordered by (-priority, node_id).
        - Dequeues nodes iteratively, appending to output list and decrementing downstream in-degrees.
        - If output length is less than total nodes, raises dag_engine.CycleError with detected cycle.
        """
        # Raises NodeNotFoundError for dangling dependencies and CycleError for cycles.
        self.validate()
        with self._lock:
            in_degree: Dict[str, int] = {
                node_id: len(self._upstream.get(node_id, set()))
                for node_id in self._nodes
            }
            ready: List[Tuple[int, str]] = [
                (-definition.priority, node_id)
                for node_id, definition in self._nodes.items()
                if in_degree[node_id] == 0
            ]
            heapq.heapify(ready)
            ordered: List[str] = []
            while ready:
                _, node_id = heapq.heappop(ready)
                ordered.append(node_id)
                for dependent in sorted(self._downstream.get(node_id, set())):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        heapq.heappush(
                            ready,
                            (-self._nodes[dependent].priority, dependent),
                        )
            # POSTCONDITION: every prerequisite precedes its dependents, ties broken by
            # priority descending then node_id ascending. validate() already rejected
            # cycles and dangling dependencies, so every node is emitted exactly once.
            return ordered

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies).

        GROUNDING:
        - Acquires _lock, filters nodes whose _upstream set is empty.
        """
        with self._lock:
            return {
                node_id
                for node_id in self._nodes
                if not self._upstream.get(node_id)
            }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents).

        GROUNDING:
        - Acquires _lock, filters nodes whose _downstream set is empty.
        """
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
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        GROUNDING:
        - Performs topological sort.
        - Resolves node weight as estimated_durations.get(node_id, 1.0) if estimated_durations is provided, else 1.0.
        - Applies dynamic programming over topological order computing earliest start time and max predecessor.
        - Backtracks from the node with the maximum completion time to reconstruct the critical path list.
        - Returns tuple of (critical path node identifiers, total path weight).
        """
        ordered = self.topological_sort()
        if not ordered:
            # POSTCONDITION: empty graph yields an empty path and zero cumulative weight.
            return [], 0.0
        with self._lock:
            completion: Dict[str, float] = {}
            predecessor: Dict[str, Optional[str]] = {}
            for node_id in ordered:
                weight = (
                    estimated_durations.get(node_id, 1.0)
                    if estimated_durations is not None
                    else 1.0
                )
                upstream = [
                    dependency
                    for dependency in self._upstream.get(node_id, set())
                    if dependency in completion
                ]
                if upstream:
                    # Earliest start is the maximum completion time of all predecessors.
                    best = max(upstream, key=lambda dependency: (completion[dependency], dependency))
                    completion[node_id] = completion[best] + weight
                    predecessor[node_id] = best
                else:
                    completion[node_id] = weight
                    predecessor[node_id] = None
            end = max(ordered, key=lambda node_id: (completion[node_id], node_id))
            path: List[str] = []
            cursor: Optional[str] = end
            while cursor is not None:
                path.append(cursor)
                cursor = predecessor[cursor]
            path.reverse()
            # POSTCONDITION: return the longest path and its cumulative weight.
            return path, completion[end]


@singleton_type("system")
class WaveScheduler(dag_engine.WaveScheduler):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine.DAG).
    - Maintains scheduling state across _dag, _states mapping, and _lock.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine.NodeState.READY and non-root nodes to dag_engine.NodeState.PENDING.
    """

    tier = "system"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._dag: dag_engine.DAG = get_singleton(dag_engine.DAG)
        self._states: Dict[str, dag_engine.NodeState] = {}

    def _sync_states(self) -> None:
        """Discovers newly registered DAG nodes and prunes removed ones."""
        registered = self._dag.all_nodes()
        for node_id in registered:
            if node_id in self._states:
                continue
            if self._dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine.NodeState.READY
        for stale in set(self._states) - registered:
            del self._states[stale]

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        GROUNDING:
        - Acquires _lock.
        - Collects all nodes in dag_engine.NodeState.READY.
        - Verifies that all upstream dependencies for each candidate are in dag_engine.NodeState.SUCCEEDED.
        - Sorts candidate nodes by definition priority descending, then node_id ascending.
        - Returns ordered list of ready node identifiers.
        """
        with self._lock:
            self._sync_states()
            candidates: List[str] = []
            for node_id, state in self._states.items():
                if state is not dag_engine.NodeState.READY:
                    continue
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in self._dag.get_dependencies(node_id)
                ):
                    candidates.append(node_id)
            # POSTCONDITION: order candidates by priority descending, node_id ascending.
            candidates.sort(
                key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id)
            )
            # POSTCONDITION: return all READY nodes whose dependencies SUCCEEDED, else empty list.
            return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        GROUNDING:
        - Acquires _lock, sets _states[node_id] to dag_engine.NodeState.RUNNING.
        """
        with self._lock:
            # POSTCONDITION: update the node state to RUNNING.
            self._states[node_id] = dag_engine.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        GROUNDING:
        - Acquires _lock, sets _states[node_id] to dag_engine.NodeState.SUCCEEDED.
        - Inspects downstream dependents of node_id.
        - Promotes any dependent currently in dag_engine.NodeState.PENDING to dag_engine.NodeState.READY if all its upstream dependencies are dag_engine.NodeState.SUCCEEDED.
        """
        with self._lock:
            # POSTCONDITION: update the node state to SUCCEEDED.
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # POSTCONDITION: promote newly unblocked dependents to READY.
            for dependent in self._dag.get_dependents(node_id):
                if self._states.get(dependent) is not dag_engine.NodeState.PENDING:
                    continue
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in self._dag.get_dependencies(dependent)
                ):
                    self._states[dependent] = dag_engine.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        GROUNDING:
        - Acquires _lock, sets _states[node_id] to dag_engine.NodeState.FAILED.
        - Transitions all non-terminal nodes to dag_engine.NodeState.CANCELLED if failure_policy is dag_engine.FailurePolicy.FAIL_FAST.
        - Traverses transitive downstream dependents and marks non-terminal dependents as dag_engine.NodeState.SKIPPED if failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM.
        - Retains non-terminal states for unblocked independent nodes if failure_policy is dag_engine.FailurePolicy.CONTINUE_ON_ERROR.
        """
        with self._lock:
            self._sync_states()
            # POSTCONDITION: update the failed node state to FAILED.
            self._states[node_id] = dag_engine.NodeState.FAILED
            if failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # POSTCONDITION: skip every non-terminal transitive dependent.
                for dependent in self._transitive_dependents(node_id):
                    if self._states.get(dependent) not in _TERMINAL_STATES:
                        self._states[dependent] = dag_engine.NodeState.SKIPPED
            elif failure_policy is dag_engine.FailurePolicy.FAIL_FAST:
                # POSTCONDITION: cancel all remaining non-terminal nodes.
                for candidate, state in list(self._states.items()):
                    if state not in _TERMINAL_STATES:
                        self._states[candidate] = dag_engine.NodeState.CANCELLED
            # POSTCONDITION: CONTINUE_ON_ERROR leaves unblocked independent nodes untouched.

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        """Collects all transitive downstream dependents of a node."""
        seen: Set[str] = set()
        stack: List[str] = list(self._dag.get_dependents(node_id))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._dag.get_dependents(current))
        return seen

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        GROUNDING:
        - Acquires _lock.
        - Synchronizes _states with all nodes currently registered in _dag.all_nodes().
        - Checks whether every node in the DAG is present in _states and in a terminal state (SUCCEEDED, FAILED, SKIPPED, CANCELLED).
        - Returns True if all registered DAG nodes have reached terminal states or if DAG is empty, False otherwise.
        """
        with self._lock:
            self._sync_states()
            nodes = self._dag.all_nodes()
            # POSTCONDITION: an empty DAG is finished.
            if not nodes:
                return True
            # POSTCONDITION: True only when every node reached a terminal state.
            return all(
                self._states.get(node_id) in _TERMINAL_STATES for node_id in nodes
            )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine.NodeState:
        """Retrieves the current execution state of a node.

        GROUNDING:
        - Acquires _lock, returns _states[node_id].
        """
        with self._lock:
            self._sync_states()
            return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        """Returns the execution state of every node in the graph.

        GROUNDING:
        - Acquires _lock, returns a shallow copy of _states mapping.
        """
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

    tier = "system"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dag: dag_engine.DAG = get_singleton(dag_engine.DAG)
        self._scheduler: dag_engine.WaveScheduler = get_singleton(
            dag_engine.WaveScheduler
        )
        self._cancelled = threading.Event()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        timeout_seconds: Optional[float] = None,
        failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST,
        max_concurrency: int = 4,
    ) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure.

        GROUNDING:
        - Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately.
        - Initializes start wall-clock time and empty _results mapping.
        - Loops while _scheduler.is_finished() is False using ThreadPoolExecutor with max_concurrency workers.
        - In each iteration, checks _cancelled event and raises dag_engine.DAGCancelledError if set after marking pending nodes CANCELLED.
        - In each iteration, checks wall-clock elapsed time against timeout_seconds and raises dag_engine.DAGTimeoutError if exceeded.
        - Dispatches ready nodes from _scheduler.next_wave() to worker threads, marking each RUNNING.
        - Executes node action with retry backoff up to definition.retries upon failure.
        - Records dag_engine.NodeResult(SUCCEEDED) and marks SUCCEEDED in _scheduler on success.
        - Records dag_engine.NodeResult(FAILED) and marks FAILED in _scheduler with failure_policy on failure after retries.
        - Computes critical path using _dag.compute_critical_path().
        - Gathers succeeded, failed, skipped, and cancelled node tuples from _results and _scheduler states.
        - Returns consolidated dag_engine.DAGRunReport.
        """
        # Cycle and dangling dependency errors propagate immediately.
        self._dag.validate()
        with self._lock:
            self._cancelled.clear()
            self._results = {}
        scheduler = self._scheduler
        dag = self._dag
        started = time.monotonic()
        deadline = (
            started + timeout_seconds if timeout_seconds is not None else None
        )
        executor = ThreadPoolExecutor(max_workers=max(1, max_concurrency))
        try:
            while True:
                # WHEN cancel() is invoked, cancel remaining nodes and abort. The guard
                # precedes the finished test so cancellation is observed even when it
                # already drove every non-terminal node to CANCELLED.
                if self._cancelled.is_set():
                    self._set_non_terminal_state(dag_engine.NodeState.CANCELLED)
                    raise dag_engine.DAGCancelledError(
                        "DAG execution was cancelled during wave execution"
                    )
                if scheduler.is_finished():
                    break
                # WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
                if self._deadline_exceeded(deadline):
                    raise dag_engine.DAGTimeoutError(
                        "DAG execution exceeded the configured timeout"
                    )
                wave = scheduler.next_wave()
                if not wave:
                    # No runnable nodes remain: blocked dependents of failed nodes are skipped.
                    self._set_non_terminal_state(dag_engine.NodeState.SKIPPED)
                    break
                # Dispatch only the bare node action off-thread; all bookkeeping below
                # runs on the calling thread.
                dispatched: List[Tuple[str, Future[Any]]] = []
                for node_id in wave:
                    scheduler.mark_running(node_id)
                    dispatched.append(
                        (node_id, executor.submit(dag.get_node(node_id).action))
                    )
                outcomes: List[dag_engine.NodeResult[Any]] = []
                for node_id, first_attempt in dispatched:
                    try:
                        outcomes.append(
                            self._execute_node(
                                dag.get_node(node_id),
                                first_attempt,
                                executor,
                                deadline,
                            )
                        )
                    except dag_engine.NodeExecutionError as failure:
                        # A node action failed after all retries; record its outcome.
                        outcomes.append(self._results[failure.node_id])
                # WHEN cancellation signalled while a node was RUNNING, cancel() has
                # already transitioned that node to CANCELLED; its in-flight outcome
                # must never resurrect it to SUCCEEDED or FAILED.
                applied: List[dag_engine.NodeResult[Any]] = [
                    result
                    for result in outcomes
                    if scheduler.get_state(result.node_id)
                    is not dag_engine.NodeState.CANCELLED
                ]
                # Apply successes before failures so completed work is never cancelled.
                for result in applied:
                    if result.state is dag_engine.NodeState.SUCCEEDED:
                        self._results[result.node_id] = result
                        scheduler.mark_succeeded(result.node_id)
                for result in applied:
                    if result.state is dag_engine.NodeState.FAILED:
                        self._results[result.node_id] = result
                        scheduler.mark_failed(result.node_id, failure_policy)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        wall_clock_seconds = time.monotonic() - started
        nodes = dag.all_nodes()
        states = scheduler.get_all_states()
        results = dict(self._results)
        for node_id in nodes:
            if node_id not in results:
                results[node_id] = dag_engine.NodeResult(
                    node_id, states.get(node_id, dag_engine.NodeState.PENDING)
                )
        critical_path, _ = dag.compute_critical_path()
        # POSTCONDITION: return a consolidated report capturing all node outcomes.
        return dag_engine.DAGRunReport(
            total_nodes=len(nodes),
            succeeded_nodes=tuple(
                sorted(
                    node_id
                    for node_id in nodes
                    if states.get(node_id) is dag_engine.NodeState.SUCCEEDED
                )
            ),
            failed_nodes=tuple(
                sorted(
                    node_id
                    for node_id in nodes
                    if states.get(node_id) is dag_engine.NodeState.FAILED
                )
            ),
            skipped_nodes=tuple(
                sorted(
                    node_id
                    for node_id in nodes
                    if states.get(node_id) is dag_engine.NodeState.SKIPPED
                )
            ),
            cancelled_nodes=tuple(
                sorted(
                    node_id
                    for node_id in nodes
                    if states.get(node_id) is dag_engine.NodeState.CANCELLED
                )
            ),
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path),
            results=results,
        )

    @operation
    @override
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes.

        GROUNDING:
        - Sets _cancelled event flag.
        - Marks unstarted ready and pending nodes as CANCELLED via _scheduler.
        """
        # POSTCONDITION: set cancellation status and abort subsequent wave execution.
        self._cancelled.set()
        self._set_non_terminal_state(dag_engine.NodeState.CANCELLED)

    def _execute_node(
        self,
        definition: dag_engine.NodeDefinition[Any],
        first_attempt: Future[Any],
        executor: ThreadPoolExecutor,
        deadline: Optional[float],
    ) -> dag_engine.NodeResult[Any]:
        """Drives one node action to completion on the calling thread.

        The worker pool runs only the bare node action; retry accounting, per-node
        timeout enforcement, and success or failure result recording all happen here
        on the calling thread.
        """
        retries_attempted = 0
        first_started = time.monotonic()
        attempt_started = first_started
        current = first_attempt
        while True:
            timeout_seconds = definition.timeout_seconds
            # Poll so cancellation and the overall deadline stay responsive.
            while not current.done():
                now = time.monotonic()
                if timeout_seconds is not None and now - attempt_started >= timeout_seconds:
                    break
                poll = _POLL_INTERVAL_SECONDS
                if deadline is not None:
                    remaining = deadline - now
                    if remaining <= 0.0:
                        # WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
                        raise dag_engine.DAGTimeoutError(
                            "DAG execution exceeded the configured timeout"
                        )
                    poll = min(poll, remaining)
                wait({current}, timeout=poll)
                # WHEN cancellation is requested, mark running nodes CANCELLED and abort.
                if self._cancelled.is_set():
                    self._set_non_terminal_state(dag_engine.NodeState.CANCELLED)
                    raise dag_engine.DAGCancelledError(
                        "DAG execution was cancelled during wave execution"
                    )
            try:
                if not current.done():
                    # Per-node timeout expired while the action was still running.
                    raise TimeoutError(
                        f"Node '{definition.node_id}' exceeded timeout of "
                        f"{timeout_seconds} seconds"
                    )
                value = current.result()
            except Exception as error:
                if retries_attempted < definition.retries:
                    # Retry with a short backoff up to the configured retry count.
                    retries_attempted += 1
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                    attempt_started = time.monotonic()
                    current = executor.submit(definition.action)
                    continue
                # Record the failure outcome, then surface it as a DAG domain error.
                self._results[definition.node_id] = dag_engine.NodeResult(
                    definition.node_id,
                    dag_engine.NodeState.FAILED,
                    error=error,
                    duration_seconds=time.monotonic() - first_started,
                    retries_attempted=retries_attempted,
                )
                raise dag_engine.NodeExecutionError(
                    f"Node '{definition.node_id}' action raised "
                    f"{type(error).__name__}: {error}",
                    definition.node_id,
                    error,
                ) from error
            # POSTCONDITION: successful actions record a SUCCEEDED outcome.
            return dag_engine.NodeResult(
                definition.node_id,
                dag_engine.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=time.monotonic() - first_started,
                retries_attempted=retries_attempted,
            )

    def _deadline_exceeded(self, deadline: Optional[float]) -> bool:
        """Returns True when the overall execution deadline has elapsed."""
        return deadline is not None and time.monotonic() >= deadline

    def _set_non_terminal_state(self, state: dag_engine.NodeState) -> None:
        """Forces all non-terminal scheduler states to the supplied state."""
        scheduler = self._scheduler
        if not isinstance(scheduler, WaveScheduler):  # pragma: no cover (assumption: the system tier registers the concrete WaveScheduler)
            return
        with scheduler._lock:
            for node_id in self._dag.all_nodes():
                if scheduler._states.get(node_id) not in _TERMINAL_STATES:
                    scheduler._states[node_id] = state


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
# LAST_CLEANED: 2026-10-22T22:07:29Z
# LAST_CHANGED: 2026-10-22T22:04:27Z
# CHANGE: Resolve cancellation defect: wave outcome bookkeeping now filters out any node that cancel() already drove to CANCELLED while it was RUNNING, so its in-flight SUCCEEDED/FAILED result can no longer resurrect it; the wave-entry guard then raises DAGCancelledError with the cancelled running node's state retained as CANCELLED per low/dag_engine.pyi:507 and 512-516. Verified 30 repeated in-node cancellation runs (all raise DAGCancelledError with every node CANCELLED, zero SUCCEEDED resurrected), mid-wave cancel of a RUNNING node, plus success/retry, failure policies, and timeout regressions
# COVERAGE_AUDIT: 2026-10-22T22:07:29Z
# QA_AUDIT: 2026-10-22T22:07:05Z
# --- END CLEANROOM METADATA ---
