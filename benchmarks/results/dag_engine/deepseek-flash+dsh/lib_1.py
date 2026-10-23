# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261021_000203_deepseek-flash_dag_engine
# Timestamp: 2026-10-21T00:02:03.807075+00:00
# Benchmark Task: dag_engine
# Model: deepseek-flash (Tier 2)
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 325,896
#   Cached Inbound Tokens:   26,421,888
#   Outbound Tokens:         295,312
#   Total Tokens:            27,043,096
#   Financial Cost ($USD):   $0.3132
#   Wall Clock Duration:     1471.81s
#   Step Latencies (s):      [190.6, 352.3, 20.1, 210.9, 110.8, 181.3, 30.1, 30.1, 20.1, 110.5, 40.3, 70.5, 80.3, 40.3, 50.4, 20.1, 100.4, 40.2, 20.1, 40.2, 40.2, 20.1, 20.1]
#   Turn Latencies (s):      [190.6, 352.3, 20.1, 210.9, 110.8, 181.3, 30.1, 30.1, 20.1, 110.5, 40.3, 70.5, 80.3, 40.3, 50.4, 20.1, 100.4, 40.2, 20.1, 40.2, 40.2, 20.1, 20.1]
#   Role Execution Rounds:   coverage: 5, lib: 4, qa: 7, test: 7 (Total: 23)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       51
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine.py ===
"""Library interface for the DAG execution and wave scheduling engine.

Realizes the abstract protocols, passive data types, error hierarchy, and
enumeration types declared in `low/dag_engine.pyi`. Concrete service behavior
lives in the paired implementation component `dag_engine_impl`.
"""

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


T = TypeVar("T")


@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __post_init__(self) -> None:
        # Preserve the diagnostic message in the underlying exception args so
        # that str(error) and error.message agree for every DAG error.
        Exception.__init__(self, self.message)


@dataclass(frozen=True)
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]


@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str


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


@dataclass(frozen=True)
class DAGTimeoutError(DAGError):
    """Raised when overall DAG execution exceeds the allocated timeout."""


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


class DAG(Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

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

    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        Args:
            node_id: Identifier to check.

        Returns:
            True if the node exists, False otherwise.
        """
        ...

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

    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        Returns:
            Set of all registered node identifiers.
        """
        ...

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

    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies).

        Returns:
            Set of root node identifiers.
        """
        ...

    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents).

        Returns:
            Set of leaf node identifiers.
        """
        ...

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


class WaveScheduler(Protocol):
    """Partitions and coordinates DAG nodes into executable waves of concurrency."""

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

    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.

        POSTCONDITIONS:
        - MUST update the node state to RUNNING.
        """
        ...

    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.

        POSTCONDITIONS:
        - MUST update the node state to SUCCEEDED.
        - MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        """
        ...

    def mark_failed(self, node_id: str) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        Args:
            node_id: Identifier of the failed node.

        POSTCONDITIONS:
        - MUST update the node state to FAILED.
        - WHEN failure policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        - WHEN failure policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        """
        ...

    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes are in terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED).
        """
        ...

    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Current NodeState.
        """
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph.

        Returns:
            Mapping of node identifier to current NodeState.
        """
        ...


class DAGRunner(Protocol):
    """Executes a DAG under concurrency limits, failure policies, and timeouts."""

    def run(self, timeout_seconds: Optional[float] = None) -> DAGRunReport:
        """Executes the entire DAG to completion or failure.

        Args:
            timeout_seconds: Optional overall execution timeout in seconds.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        Raises:
            DAGTimeoutError: If execution exceeds timeout_seconds.
            DAGCancelledError: If cancel() is invoked during execution.

        POSTCONDITIONS:
        - MUST execute ready nodes concurrently up to the configured concurrency limit.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        - WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
        - WHEN cancelled during execution, MUST mark running nodes as CANCELLED and raise DAGCancelledError.
        """
        ...

    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes.

        POSTCONDITIONS:
        - MUST set cancellation status and abort subsequent wave execution.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-21T00:07:55Z
# LAST_CHANGED: 2026-10-21T00:07:55Z
# CHANGE: Implement DAG engine library interfaces: frozen dataclass error hierarchy (DAGError/CycleError/NodeNotFoundError/NodeExecutionError/DAGTimeoutError/DAGCancelledError) with exception args preserved, NodeState/FailurePolicy enums, immutable NodeDefinition/NodeResult/DAGRunReport records, and abstract DAG/WaveScheduler/DAGRunner protocols matching low/dag_engine.pyi.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_impl.py ===
"""Library implementation of the DAG execution and wave scheduling engine.

Realizes the concrete services declared in `low/dag_engine_impl.pyi` against the
protocols, error hierarchy, and data records in `lib/dag_engine.py`.
"""

from __future__ import annotations

from dataclasses import replace
import heapq
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
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

# Terminal lifecycle states: a node in one of these states will not transition again.
_TERMINAL_STATES: FrozenSet[dag_engine.NodeState] = frozenset(
    {
        dag_engine.NodeState.SUCCEEDED,
        dag_engine.NodeState.FAILED,
        dag_engine.NodeState.SKIPPED,
        dag_engine.NodeState.CANCELLED,
    }
)

# States that represent work that has not started yet.
_UNSTARTED_STATES: FrozenSet[dag_engine.NodeState] = frozenset(
    {dag_engine.NodeState.PENDING, dag_engine.NodeState.READY}
)

# Outstanding worker record: node definition, retries attempted, attempt deadline, node start time.
_NodeAttempt = Tuple[dag_engine.NodeDefinition[Any], int, Optional[float], float]


class DAG(dag_engine.DAG, Singleton):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    - Synchronizes graph mutations and queries using threading.RLock for thread safety.
    """

    tier = system

    def __init__(self) -> None:
        super().__init__()
        # Concrete private backing state: node definitions plus both edge directions.
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
        """Adds a task node to the graph."""
        with self._lock:
            dependency_set = frozenset(dependencies) if dependencies is not None else frozenset()
            # MUST register the immutable node definition into the graph.
            self._nodes[node_id] = dag_engine.NodeDefinition(
                node_id=node_id,
                action=action,
                dependencies=dependency_set,
                priority=priority,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            self._upstream[node_id] = set()
            self._downstream.setdefault(node_id, set())
            # WHEN dependencies are provided, MUST add directed edges from each
            # dependency to node_id. Missing dependencies are recorded and are
            # reported later by validate().
            for dependency in dependency_set:
                self._upstream[node_id].add(dependency)
                self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        with self._lock:
            # WHEN either identifier is absent, MUST raise NodeNotFoundError.
            if upstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Cannot add edge: upstream node '{upstream_id}' is not in the graph",
                    upstream_id,
                )
            if downstream_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Cannot add edge: downstream node '{downstream_id}' is not in the graph",
                    downstream_id,
                )
            # MUST establish a directed dependency edge from upstream to downstream.
            self._upstream[downstream_id].add(upstream_id)
            self._downstream[upstream_id].add(downstream_id)
            # Keep the immutable definition's dependency set in sync with the edge.
            definition = self._nodes[downstream_id]
            if upstream_id not in definition.dependencies:
                self._nodes[downstream_id] = replace(
                    definition,
                    dependencies=definition.dependencies | frozenset({upstream_id}),
                )

    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Cannot remove node: node '{node_id}' is not in the graph",
                    node_id,
                )
            # MUST remove the node and its incident edges.
            self._remove_node_locked(node_id)

    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        with self._lock:
            return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' is not in the graph",
                    node_id,
                )
            # MUST return the NodeDefinition matching node_id.
            return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' is not in the graph",
                    node_id,
                )
            # MUST return all direct upstream dependencies (as a defensive copy).
            return set(self._upstream.get(node_id, ()))

    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        with self._lock:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            if node_id not in self._nodes:
                raise dag_engine.NodeNotFoundError(
                    f"Node '{node_id}' is not in the graph",
                    node_id,
                )
            # MUST return all direct downstream dependents (as a defensive copy).
            return set(self._downstream.get(node_id, ()))

    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        with self._lock:
            return set(self._nodes)

    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        with self._lock:
            # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
            for node_id in sorted(self._nodes):
                for dependency in sorted(self._nodes[node_id].dependencies):
                    if dependency not in self._nodes:
                        raise dag_engine.NodeNotFoundError(
                            f"Node '{node_id}' depends on missing node '{dependency}'",
                            dependency,
                        )
            # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
            cycle = self._find_cycle_locked()
            if cycle is not None:
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}",
                    tuple(cycle),
                )
            # WHEN all referenced nodes exist and no cycle exists, MUST complete
            # without error (implicit fall-through).

    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        with self._lock:
            # Compute in-degrees over dependencies that are actually registered.
            in_degree: Dict[str, int] = {
                node_id: sum(
                    1 for dependency in self._upstream.get(node_id, ()) if dependency in self._nodes
                )
                for node_id in self._nodes
            }
            # Deterministic ready queue ordered by priority descending then name ascending.
            ready: List[Tuple[int, str]] = [
                (-self._nodes[node_id].priority, node_id)
                for node_id, degree in in_degree.items()
                if degree == 0
            ]
            heapq.heapify(ready)
            ordering: List[str] = []
            while ready:
                _, node_id = heapq.heappop(ready)
                ordering.append(node_id)
                for dependent in self._downstream.get(node_id, ()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        heapq.heappush(
                            ready,
                            (-self._nodes[dependent].priority, dependent),
                        )
            # WHEN a cycle exists, MUST raise CycleError.
            if len(ordering) < len(self._nodes):
                cycle = self._find_cycle_locked()
                assert cycle is not None
                raise dag_engine.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}",
                    tuple(cycle),
                )
            return ordering

    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        with self._lock:
            return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        with self._lock:
            return {node_id for node_id in self._nodes if not self._downstream.get(node_id)}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        with self._lock:
            ordering = self.topological_sort()
            if not ordering:
                return ([], 0.0)
            durations: Mapping[str, float] = (
                estimated_durations if estimated_durations is not None else {}
            )
            # Dynamic programming over the topological order: earliest completion
            # time per node together with the best predecessor chain.
            best_weight: Dict[str, float] = {}
            best_path: Dict[str, List[str]] = {}
            for node_id in ordering:
                weight = durations.get(node_id, 1.0)
                predecessor: Optional[str] = None
                for dependency in sorted(
                    dep for dep in self._upstream.get(node_id, ()) if dep in self._nodes
                ):
                    if predecessor is None:
                        predecessor = dependency
                        continue
                    # Deterministic tie-break: heavier path wins, then smaller name.
                    if best_weight[dependency] > best_weight[predecessor] or (
                        best_weight[dependency] == best_weight[predecessor]
                        and dependency < predecessor
                    ):
                        predecessor = dependency
                if predecessor is None:
                    best_weight[node_id] = weight
                    best_path[node_id] = [node_id]
                else:
                    best_weight[node_id] = best_weight[predecessor] + weight
                    best_path[node_id] = best_path[predecessor] + [node_id]
            # Backtrack from the node with the maximum completion time.
            endpoint = ordering[0]
            for node_id in ordering:
                if best_weight[node_id] > best_weight[endpoint] or (
                    best_weight[node_id] == best_weight[endpoint] and node_id < endpoint
                ):
                    endpoint = node_id
            return (list(best_path[endpoint]), best_weight[endpoint])

    def _remove_node_locked(self, node_id: str) -> None:
        """Removes a node and detaches every incident edge (caller holds the lock)."""
        for upstream_id in self._upstream.pop(node_id, set()):
            dependents = self._downstream.get(upstream_id)
            if dependents is not None:
                dependents.discard(node_id)
        for downstream_id in self._downstream.pop(node_id, set()):
            dependencies = self._upstream.get(downstream_id)
            if dependencies is not None:
                dependencies.discard(node_id)
            dependent_definition = self._nodes.get(downstream_id)
            if dependent_definition is not None and node_id in dependent_definition.dependencies:
                self._nodes[downstream_id] = replace(
                    dependent_definition,
                    dependencies=dependent_definition.dependencies - frozenset({node_id}),
                )
        self._nodes.pop(node_id, None)

    def _find_cycle_locked(self) -> Optional[List[str]]:
        """Finds one directed dependency cycle, if any (caller holds the lock)."""
        white, gray, black = 0, 1, 2
        colors: Dict[str, int] = {node_id: white for node_id in self._nodes}
        path: List[str] = []

        def visit(node_id: str) -> Optional[List[str]]:
            colors[node_id] = gray
            path.append(node_id)
            for dependency in sorted(
                dep for dep in self._upstream.get(node_id, ()) if dep in self._nodes
            ):
                color = colors[dependency]
                if color == gray:
                    # Close the cycle at the first occurrence of the repeated node.
                    start = path.index(dependency)
                    return path[start:] + [dependency]
                if color == white:
                    found = visit(dependency)
                    if found is not None:
                        return found
            path.pop()
            colors[node_id] = black
            return None

        for node_id in sorted(self._nodes):
            if colors[node_id] == white:
                found = visit(node_id)
                if found is not None:
                    return found
        return None


def _resolve_dag(dag: Optional[dag_engine.DAG]) -> dag_engine.DAG:
    """Resolves the graph collaborator, using lifecycle resolution when omitted."""
    # Collaborator singletons are resolved on demand via get_singleton(...).
    return get_singleton(dag_engine.DAG) if dag is None else dag


class WaveScheduler(dag_engine.WaveScheduler, Singleton):
    """Concrete realization of wave-based concurrent scheduling across a DAG.

    GROUNDING:
    - Maintains scheduling state across _dag, _failure_policy, _states mapping, and _lock.
    - On initialization, assigns dag_engine.NodeState.READY to all root nodes, and dag_engine.NodeState.PENDING to remaining nodes.
    """

    tier = system

    def __init__(
        self,
        dag: Optional[dag_engine.DAG] = None,
        failure_policy: Optional[dag_engine.FailurePolicy] = None,
    ) -> None:
        super().__init__()
        # Concrete private backing state: graph reference, policy, and per-node states.
        self._dag: dag_engine.DAG = _resolve_dag(dag)
        self._failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST if failure_policy is None else failure_policy
        self._lock = threading.RLock()
        self._states: Dict[str, dag_engine.NodeState] = {}
        # On initialization, roots start READY and every other node starts PENDING.
        self._reseed_states()

    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        with self._lock:
            self._sync_states()
            candidates: List[str] = []
            # MUST return all READY nodes whose upstream dependencies are SUCCEEDED.
            for node_id, state in self._states.items():
                if state is not dag_engine.NodeState.READY:
                    continue
                dependencies = self._dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    candidates.append(node_id)
            # MUST order returned nodes by priority descending, then node_id ascending.
            candidates.sort(key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id))
            # WHEN no nodes are ready, MUST return an empty list.
            return candidates

    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        with self._lock:
            self._sync_states()
            # MUST update the node state to RUNNING.
            self._states[node_id] = dag_engine.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        with self._lock:
            self._sync_states()
            # MUST update the node state to SUCCEEDED.
            self._states[node_id] = dag_engine.NodeState.SUCCEEDED
            # MUST promote newly unblocked PENDING dependents to READY.
            for dependent in self._dag.get_dependents(node_id):
                if self._states.get(dependent) is not dag_engine.NodeState.PENDING:
                    continue
                dependencies = self._dag.get_dependencies(dependent)
                if all(
                    self._states.get(dependency) is dag_engine.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    self._states[dependent] = dag_engine.NodeState.READY

    def mark_failed(self, node_id: str) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        with self._lock:
            self._sync_states()
            # MUST update the node state to FAILED.
            self._states[node_id] = dag_engine.NodeState.FAILED
            if self._failure_policy is dag_engine.FailurePolicy.SKIP_DOWNSTREAM:
                # WHEN failure policy is SKIP_DOWNSTREAM, MUST transition all
                # transitive dependents to SKIPPED.
                pending = list(self._dag.get_dependents(node_id))
                visited: Set[str] = set()
                while pending:
                    dependent = pending.pop()
                    if dependent in visited:
                        continue
                    visited.add(dependent)
                    # Traverse through already-terminal dependents too, so a
                    # non-terminal dependent reachable only through a terminal
                    # dependent is still transitioned to SKIPPED.
                    if self._states.get(dependent) not in _TERMINAL_STATES:
                        self._states[dependent] = dag_engine.NodeState.SKIPPED
                    pending.extend(self._dag.get_dependents(dependent))
            elif self._failure_policy is dag_engine.FailurePolicy.FAIL_FAST:
                # WHEN failure policy is FAIL_FAST, MUST transition all remaining
                # non-terminal nodes to CANCELLED.
                for other_id, state in self._states.items():
                    if other_id == node_id or state in _TERMINAL_STATES:
                        continue
                    self._states[other_id] = dag_engine.NodeState.CANCELLED
            # CONTINUE_ON_ERROR retains non-terminal states for independent nodes.

    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        with self._lock:
            self._sync_states()
            return all(state in _TERMINAL_STATES for state in self._states.values())

    def get_state(self, node_id: str) -> dag_engine.NodeState:
        """Retrieves the current execution state of a node."""
        with self._lock:
            self._sync_states()
            return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine.NodeState]:
        """Returns the execution state of every node in the graph."""
        with self._lock:
            self._sync_states()
            return dict(self._states)

    def _sync_states(self) -> None:
        """Reconciles tracked states with the nodes currently present in the graph."""
        with self._lock:
            node_ids = self._dag.all_nodes()
            roots = self._dag.find_roots()
            for node_id in node_ids:
                if node_id not in self._states:
                    self._states[node_id] = (
                        dag_engine.NodeState.READY
                        if node_id in roots
                        else dag_engine.NodeState.PENDING
                    )
            for tracked_id in list(self._states):
                if tracked_id not in node_ids:
                    del self._states[tracked_id]

    def _reseed_states(self) -> None:
        """Assigns READY to roots and PENDING to the remaining graph nodes."""
        with self._lock:
            roots = self._dag.find_roots()
            self._states = {
                node_id: (
                    dag_engine.NodeState.READY
                    if node_id in roots
                    else dag_engine.NodeState.PENDING
                )
                for node_id in self._dag.all_nodes()
            }

    def _cancel_unstarted(self) -> None:
        """Marks PENDING and READY nodes as CANCELLED (caller-safe)."""
        with self._lock:
            self._sync_states()
            for node_id, state in self._states.items():
                if state in _UNSTARTED_STATES:
                    self._states[node_id] = dag_engine.NodeState.CANCELLED

    def _cancel_running(self) -> None:
        """Marks in-flight RUNNING nodes as CANCELLED."""
        with self._lock:
            self._sync_states()
            for node_id, state in self._states.items():
                if state is dag_engine.NodeState.RUNNING:
                    self._states[node_id] = dag_engine.NodeState.CANCELLED


class DAGRunner(dag_engine.DAGRunner, Singleton):
    """Concrete realization of concurrent DAG execution runner.

    GROUNDING:
    - Coordinates execution using _dag, _scheduler, _max_concurrency, _failure_policy, _cancelled event, and _results mapping.
    - Synchronizes runner state using threading.Lock.
    """

    tier = system

    def __init__(
        self,
        dag: Optional[dag_engine.DAG] = None,
        max_concurrency: Optional[int] = None,
        failure_policy: Optional[dag_engine.FailurePolicy] = None,
        scheduler: Optional[dag_engine.WaveScheduler] = None,
    ) -> None:
        super().__init__()
        # Concrete private backing state: graph, scheduler, limits, and results.
        resolved_dag = _resolve_dag(dag)
        self._dag: dag_engine.DAG = resolved_dag
        self._max_concurrency: int = 4 if max_concurrency is None else max_concurrency
        self._failure_policy: dag_engine.FailurePolicy = dag_engine.FailurePolicy.FAIL_FAST if failure_policy is None else failure_policy
        self._scheduler: dag_engine.WaveScheduler = WaveScheduler(dag=resolved_dag, failure_policy=self._failure_policy) if scheduler is None else scheduler
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._results: Dict[str, dag_engine.NodeResult[Any]] = {}

    def run(self, timeout_seconds: Optional[float] = None) -> dag_engine.DAGRunReport:
        """Executes the entire DAG to completion or failure."""
        # Validate the graph first so cycle/missing-node errors surface immediately.
        self._dag.validate()
        # Refresh scheduling state so a runner built before its graph executes every node.
        scheduler = self._scheduler
        if isinstance(scheduler, WaveScheduler):
            scheduler._sync_states()
        start_time = time.monotonic()
        with self._lock:
            self._results = {}
        # A cancellation requested before execution aborts immediately.
        if self._cancelled.is_set():
            self._mark_cancelled_nodes()
            raise dag_engine.DAGCancelledError("DAG execution was cancelled before it started")
        executor = ThreadPoolExecutor(max_workers=self._max_concurrency)
        # Future -> (definition, retries attempted, attempt deadline, node start time)
        pending: Dict[Future[Any], _NodeAttempt] = {}
        try:
            while True:
                # Single abort guard, re-evaluated on every attempt until completion.
                self._check_abort(timeout_seconds, start_time)
                if self._scheduler.is_finished():
                    break
                # MUST dispatch ready nodes concurrently up to the concurrency limit.
                available = self._max_concurrency - len(pending)
                for node_id in self._scheduler.next_wave()[:available]:
                    definition = self._dag.get_node(node_id)
                    self._scheduler.mark_running(node_id)
                    pending[executor.submit(definition.action)] = (definition, 0, self._deadline(definition), time.monotonic())
                if not pending:
                    # No runnable node remains and no terminal state can be
                    # reached: stop instead of spinning on blocked dependents.
                    break
                slice_timeout = 0.05
                if timeout_seconds is not None:
                    remaining = timeout_seconds - (time.monotonic() - start_time)
                    slice_timeout = min(slice_timeout, max(0.0, remaining))
                finished, _not_done = wait(set(pending), timeout=slice_timeout)
                for future in finished:
                    self._handle_finished(future, pending, executor)
                self._handle_node_timeouts(pending, executor)
        finally:
            # Normal completion has no in-flight work; timeout/cancel paths must
            # not block on abandoned actions while reporting the abort.
            executor.shutdown(wait=False)
        return self._build_report(start_time)

    def _check_abort(self, timeout_seconds: Optional[float], start_time: float) -> None:
        """Raises when cancellation or the overall timeout aborts the run."""
        # WHEN cancelled during execution, MUST mark running nodes as
        # CANCELLED and raise DAGCancelledError.
        if self._cancelled.is_set():
            self._mark_cancelled_nodes()
            raise dag_engine.DAGCancelledError("DAG execution was cancelled during execution")
        # WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
        if timeout_seconds is not None and time.monotonic() - start_time >= timeout_seconds:
            raise dag_engine.DAGTimeoutError(f"DAG execution exceeded the timeout of {timeout_seconds} seconds")

    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes."""
        # MUST set the cancellation status and abort subsequent wave execution.
        self._cancelled.set()
        self._mark_cancelled_nodes()

    def _handle_finished(
        self,
        future: Future[Any],
        pending: Dict[Future[Any], _NodeAttempt],
        executor: ThreadPoolExecutor,
    ) -> None:
        """Records one completed node action, retrying it when configured."""
        definition, retries_attempted, _deadline, started_at = pending.pop(future)
        try:
            value = self._action_value(future, definition)
        except dag_engine.NodeExecutionError as failure:
            self._record_failure(definition, retries_attempted, started_at, failure.cause, pending, executor)
            return
        self._record_result(
            dag_engine.NodeResult(
                node_id=definition.node_id,
                state=dag_engine.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=time.monotonic() - started_at,
                retries_attempted=retries_attempted,
            )
        )

    def _handle_node_timeouts(
        self,
        pending: Dict[Future[Any], _NodeAttempt],
        executor: ThreadPoolExecutor,
    ) -> None:
        """Fails actions that exceeded their per-node timeout."""
        now = time.monotonic()
        expired = [
            future
            for future, (_definition, _retries, deadline, _started) in pending.items()
            if deadline is not None and now >= deadline
        ]
        for future in expired:
            definition, retries_attempted, _deadline, started_at = pending.pop(future)
            future.cancel()
            failure = TimeoutError(
                f"Node '{definition.node_id}' exceeded its action timeout of {definition.timeout_seconds} seconds"
            )
            self._record_failure(definition, retries_attempted, started_at, failure, pending, executor)

    def _record_failure(
        self,
        definition: dag_engine.NodeDefinition[Any],
        retries_attempted: int,
        started_at: float,
        error: Exception,
        pending: Dict[Future[Any], _NodeAttempt],
        executor: ThreadPoolExecutor,
    ) -> None:
        """Retries a failed node action or records its failed outcome."""
        if retries_attempted < definition.retries:
            # MUST execute retries up to the configured retry count.
            time.sleep(min(0.01 * (retries_attempted + 1), 0.1))
            pending[executor.submit(definition.action)] = (
                definition,
                retries_attempted + 1,
                self._deadline(definition),
                started_at,
            )
            return
        self._record_result(
            dag_engine.NodeResult(
                node_id=definition.node_id,
                state=dag_engine.NodeState.FAILED,
                error=error,
                duration_seconds=time.monotonic() - started_at,
                retries_attempted=retries_attempted,
            )
        )

    def _deadline(self, definition: dag_engine.NodeDefinition[Any]) -> Optional[float]:
        """Computes the per-attempt deadline for a node action, if it declares one."""
        if definition.timeout_seconds is None:
            return None
        return time.monotonic() + definition.timeout_seconds

    def _action_value(
        self, future: Future[Any], definition: dag_engine.NodeDefinition[Any]
    ) -> Any:
        """Returns the action result or raises NodeExecutionError for action failures."""
        try:
            return future.result()
        except Exception as error:
            # Contract: an unhandled action exception becomes a NodeExecutionError
            # carrying the failed node identifier and the underlying cause.
            raise dag_engine.NodeExecutionError(
                f"Node '{definition.node_id}' action failed: {error}",
                definition.node_id,
                error,
            ) from error

    def _record_result(self, result: dag_engine.NodeResult[Any]) -> None:
        """Stores a node outcome and applies it to the scheduler."""
        with self._lock:
            self._results[result.node_id] = result
        if result.state is dag_engine.NodeState.SUCCEEDED:
            self._scheduler.mark_succeeded(result.node_id)
        else:
            self._scheduler.mark_failed(result.node_id)

    def _mark_cancelled_nodes(self) -> None:
        """Marks unstarted and in-flight nodes CANCELLED when the scheduler allows."""
        scheduler = self._scheduler
        if isinstance(scheduler, WaveScheduler):
            scheduler._cancel_unstarted()
            scheduler._cancel_running()

    def _build_report(self, start_time: float) -> dag_engine.DAGRunReport:
        """Assembles the consolidated run report from scheduler and result state."""
        states = self._scheduler.get_all_states()
        succeeded = tuple(sorted(node for node, state in states.items() if state is dag_engine.NodeState.SUCCEEDED))
        failed = tuple(sorted(node for node, state in states.items() if state is dag_engine.NodeState.FAILED))
        skipped = tuple(sorted(node for node, state in states.items() if state is dag_engine.NodeState.SKIPPED))
        cancelled = tuple(sorted(node for node, state in states.items() if state is dag_engine.NodeState.CANCELLED))
        critical_path, _weight = self._dag.compute_critical_path()
        with self._lock:
            results = dict(self._results)
        return dag_engine.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
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
# LAST_CLEANED: 2026-10-21T00:26:26Z
# LAST_CHANGED: 2026-10-21T00:21:06Z
# CHANGE: Fix SKIP_DOWNSTREAM transitive traversal: mark_failed now continues traversing downstream dependents even when an intermediate dependent is already terminal, marking only non-terminal dependents SKIPPED, so a non-terminal transitive dependent reachable solely through an already-SUCCEEDED node is no longer left READY.
# COVERAGE_AUDIT: 2026-10-21T00:26:26Z
# QA_AUDIT: 2026-10-21T00:26:03Z
# --- END CLEANROOM METADATA ---
