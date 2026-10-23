# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_174512_deepseek-flash_dag_engine_lite
# Timestamp: 2026-10-23T17:45:12.586297+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 141,984
#   Cached Inbound Tokens:   4,611,456
#   Outbound Tokens:         127,453
#   Total Tokens:            4,880,893
#   Financial Cost ($USD):   $0.1116
#   Wall Clock Duration:     533.74s
#   Step Latencies (s):      [171.0, 231.3, 20.1, 180.5, 60.3, 70.6, 20.2, 20.2]
#   Turn Latencies (s):      [171.0, 231.3, 20.1, 180.5, 60.3, 70.6, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 2, lib: 2, qa: 2, test: 2 (Total: 8)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       48
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface specification for the synchronous DAG execution and wave scheduling engine."""

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
        retries: Number of retry attempts on failure.
    """

    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
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
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph.

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
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
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        Returns:
            List of node identifiers ready for execution, ordered by priority descending.

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
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        Args:
            failure_policy: Failure policy applied upon node action failure. Defaults to FAIL_FAST.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        POSTCONDITIONS:
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T17:47:52Z
# LAST_CHANGED: 2026-10-23T17:47:52Z
# CHANGE: Implement DAG engine interface: frozen data types (DAGError, CycleError, NodeNotFoundError, NodeExecutionError, NodeDefinition, NodeResult, DAGRunReport), NodeState/FailurePolicy enums, and DAG/WaveScheduler/DAGRunner system-tier Protocol stubs matching low/dag_engine_lite.pyi.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Runtime implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

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
from . import dag_engine_lite


def _is_terminal(state: dag_engine_lite.NodeState) -> bool:
    """Returns whether a node state is a terminal lifecycle state."""
    return state in (
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    )


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """

    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
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
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph."""
        # POSTCONDITION: register the immutable node definition into the graph.
        dependency_set: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        definition = dag_engine_lite.NodeDefinition[Any](
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())

        # POSTCONDITION: WHEN dependencies are provided, add directed edges dependency -> node_id.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        # POSTCONDITION: WHEN either identifier does not exist, raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{upstream_id}' not found in DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{downstream_id}' not found in DAG",
                node_id=downstream_id,
            )

        # POSTCONDITION: establish a directed dependency edge upstream_id -> downstream_id.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        # POSTCONDITION: WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        # POSTCONDITION: remove the node and every incident edge.
        for upstream_id in self._upstream.get(node_id, set()):
            dependents = self._downstream.get(upstream_id)
            if dependents is not None:
                dependents.discard(node_id)
        for downstream_id in self._downstream.get(node_id, set()):
            dependencies = self._upstream.get(downstream_id)
            if dependencies is not None:
                dependencies.discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        # POSTCONDITION: WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        # POSTCONDITION: return the NodeDefinition matching node_id.
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        # POSTCONDITION: WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        # POSTCONDITION: return all direct upstream dependencies (defensive copy).
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        # POSTCONDITION: WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        # POSTCONDITION: return all direct downstream dependents (defensive copy).
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        # POSTCONDITION: WHEN a dependency node is missing, raise NodeNotFoundError.
        for node_id, definition in self._nodes.items():
            for dependency in definition.dependencies:
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' depends on missing node '{dependency}'"
                        ),
                        node_id=dependency,
                    )

        # POSTCONDITION: WHEN a cycle exists, raise CycleError containing the cycle sequence.
        visiting: Set[str] = set()
        visited: Set[str] = set()
        path: List[str] = []

        def _visit(node_id: str) -> None:
            visiting.add(node_id)
            path.append(node_id)
            # The completeness pass above guarantees every upstream dependency is
            # registered, so the traversal only ever follows existing nodes.
            for dependency in sorted(self._upstream.get(node_id, set())):
                if dependency in visiting:
                    cycle_start = path.index(dependency)
                    cycle = tuple(path[cycle_start:])
                    raise dag_engine_lite.CycleError(
                        message=f"Cycle detected involving nodes: {' -> '.join(cycle)}",
                        cycle=cycle,
                    )
                if dependency not in visited:
                    _visit(dependency)
            path.pop()
            visiting.discard(node_id)
            visited.add(node_id)

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                _visit(node_id)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        import heapq

        # Compute in-degree counts from the upstream dependency mapping.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()))
            for node_id in self._nodes
        }
        # Initialize the ready heap ordered by priority descending, then name ascending.
        ready: List[Tuple[int, str]] = [
            (-self._nodes[node_id].priority, node_id)
            for node_id, degree in in_degree.items()
            if degree == 0
        ]
        heapq.heapify(ready)

        order: List[str] = []
        while ready:
            _, node_id = heapq.heappop(ready)
            order.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(
                        ready, (-self._nodes[dependent].priority, dependent)
                    )

        # POSTCONDITION: WHEN a cycle exists, raise CycleError containing the cycle sequence.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle(in_degree)
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected involving nodes: {' -> '.join(cycle)}",
                cycle=cycle,
            )
        return order

    def _find_cycle(self, in_degree: Mapping[str, int]) -> Tuple[str, ...]:
        """Locates a directed cycle among nodes that could not be ordered."""
        remaining = {node_id for node_id, degree in in_degree.items() if degree > 0}
        # Every node with residual non-zero in-degree retains at least one
        # unresolved upstream dependency inside the residual set. Walking those
        # dependencies from any residual node must therefore revisit a node and
        # close a cycle, so the walk always terminates on a repeated identifier.
        path: List[str] = []
        positions: Dict[str, int] = {}
        current = min(remaining)
        while current not in positions:
            positions[current] = len(path)
            path.append(current)
            current = next(
                dependency
                for dependency in sorted(self._upstream.get(current, set()))
                if dependency in remaining
            )
        return tuple(path[positions[current]:])

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id)
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
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
        """Computes the longest weighted dependency path through the graph."""
        order = self.topological_sort()
        if not order:
            return ([], 0.0)

        # Resolve duration weights, defaulting to 1.0 for unspecified nodes.
        durations: Dict[str, float] = {
            node_id: (
                estimated_durations.get(node_id, 1.0)
                if estimated_durations is not None
                else 1.0
            )
            for node_id in self._nodes
        }

        # Dynamic programming over earliest completion times.
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for node_id in order:
            best_time = 0.0
            best_predecessor: Optional[str] = None
            for dependency in sorted(self._upstream.get(node_id, set())):
                candidate = earliest.get(dependency, 0.0)
                if candidate > best_time or (
                    candidate == best_time
                    and best_predecessor is not None
                    and dependency < best_predecessor
                ):
                    best_time = candidate
                    best_predecessor = dependency
            earliest[node_id] = best_time + durations.get(node_id, 1.0)
            predecessor[node_id] = best_predecessor

        # Identify the terminal node with the maximum completion time.
        terminal = max(order, key=lambda node_id: (earliest[node_id], node_id))

        # Backtrack through upstream dependencies to reconstruct the path.
        path: List[str] = [terminal]
        current: Optional[str] = terminal
        while current is not None:
            previous = predecessor.get(current)
            if previous is None:
                break
            current = previous
            path.append(current)
        path.reverse()
        return (path, earliest[terminal])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine_lite.NodeState.READY and non-root nodes to dag_engine_lite.NodeState.PENDING.
    """

    tier = system

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _synchronize(self, dag: dag_engine_lite.DAG) -> None:
        """Ensures scheduling state covers every node currently registered in the DAG."""
        for node_id in dag.all_nodes():
            if node_id not in self._states:
                if dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._synchronize(dag)

        # POSTCONDITION: return all READY nodes whose upstream dependencies are SUCCEEDED.
        candidates: List[str] = [
            node_id
            for node_id, state in self._states.items()
            if state == dag_engine_lite.NodeState.READY
            and all(
                self._states.get(dependency) == dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dag.get_dependencies(node_id)
            )
        ]
        # POSTCONDITION: order by priority descending, then node_id ascending.
        candidates.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        # POSTCONDITION: update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        dag = get_singleton(dag_engine_lite.DAG)
        # POSTCONDITION: update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED

        # POSTCONDITION: promote newly unblocked dependents from PENDING to READY.
        for dependent in dag.get_dependents(node_id):
            if self._states.get(dependent) != dag_engine_lite.NodeState.PENDING:
                continue
            if all(
                self._states.get(dependency) == dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dag.get_dependencies(dependent)
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        dag = get_singleton(dag_engine_lite.DAG)
        # POSTCONDITION: update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # POSTCONDITION: cancel every remaining non-terminal node.
            for other_id, state in list(self._states.items()):
                if other_id != node_id and not _is_terminal(state):
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # POSTCONDITION: skip every transitive downstream dependent.
            visited: Set[str] = set()
            pending: List[str] = list(dag.get_dependents(node_id))
            while pending:
                dependent = pending.pop()
                if dependent in visited:
                    continue
                visited.add(dependent)
                state = self._states.get(dependent)
                if state is None or not _is_terminal(state):
                    self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
                pending.extend(dag.get_dependents(dependent))
        # CONTINUE_ON_ERROR: leave unblocked independent nodes eligible for execution.

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._synchronize(dag)

        # POSTCONDITION: WHEN the DAG contains no nodes, return True.
        node_ids = dag.all_nodes()
        if not node_ids:
            return True
        # POSTCONDITION: only True when every registered node is in a terminal state.
        return all(
            _is_terminal(self._states[node_id])
            for node_id in node_ids
            if node_id in self._states
        ) and all(node_id in self._states for node_id in node_ids)

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._synchronize(dag)
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._synchronize(dag)
        return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier = system

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)

        # Validate the graph; cycle or missing dependency exceptions propagate.
        dag.validate()

        start = time.perf_counter()
        self._results = {}

        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break

            failed_in_wave = False
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                node_start = time.perf_counter()
                retries_attempted = 0

                while True:
                    try:
                        value = definition.action()
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        # Retry the action while attempts remain; otherwise record failure.
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        duration = time.perf_counter() - node_start
                        self._results[node_id] = dag_engine_lite.NodeResult[Any](
                            node_id=node_id,
                            state=dag_engine_lite.NodeState.FAILED,
                            error=exc,
                            duration_seconds=duration,
                            retries_attempted=retries_attempted,
                        )
                        scheduler.mark_failed(node_id, failure_policy)
                        failed_in_wave = True
                        break
                    else:
                        duration = time.perf_counter() - node_start
                        self._results[node_id] = dag_engine_lite.NodeResult[Any](
                            node_id=node_id,
                            state=dag_engine_lite.NodeState.SUCCEEDED,
                            value=value,
                            duration_seconds=duration,
                            retries_attempted=retries_attempted,
                        )
                        scheduler.mark_succeeded(node_id)
                        break

                # POSTCONDITION: halt wave execution when FAIL_FAST and a node failed.
                if failed_in_wave and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                    break

            if failed_in_wave and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        # Populate default outcome records for unexecuted terminal nodes.
        states = scheduler.get_all_states()
        for node_id, state in states.items():
            if node_id in self._results:
                continue
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult[Any](
                    node_id=node_id,
                    state=state,
                )

        critical_path, _weight = dag.compute_critical_path()
        wall_clock_seconds = time.perf_counter() - start

        succeeded_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state == dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state == dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state == dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state == dag_engine_lite.NodeState.CANCELLED
            )
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine_lite.DAG],
        tier=DAG.tier,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine_lite.WaveScheduler],
        tier=WaveScheduler.tier,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine_lite.DAGRunner],
        tier=DAGRunner.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T17:53:59Z
# LAST_CHANGED: 2026-10-23T17:53:33Z
# CHANGE: Eliminate unreachable defensive branches flagged by feedback: remove the validate DFS missing-dependency guard (the completeness pass already raises NodeNotFoundError for every missing dependency), remove the topological-sort dependent-membership guard (every dependent is a registered node by construction and present in the in-degree map), replace the recursive cycle locator with a deterministic residual-graph walk that always closes a cycle and has no unreachable fallback return, and remove the run wave-loop READY-state guard (FAIL_FAST halts the wave immediately and success only promotes PENDING dependents outside the current wave, so every later wave member remains READY). Behavioral contracts and runtime results are unchanged.
# COVERAGE_AUDIT: 2026-10-23T17:53:59Z
# QA_AUDIT: 2026-10-23T17:53:43Z
# --- END CLEANROOM METADATA ---
