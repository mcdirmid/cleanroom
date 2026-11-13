# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_163044_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-12T16:30:44.413880+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 294,569
#   Cached Inbound Tokens:   18,029,824
#   Outbound Tokens:         297,359
#   Total Tokens:            18,621,752
#   Financial Cost ($USD):   $0.2767
#   Wall Clock Duration:     1599.71s
#   Step Latencies (s):      [292.0, 553.9, 20.3, 194.1, 43.0, 124.9, 319.1, 81.7, 10.1, 73.5, 61.3, 94.3, 63.3, 10.1, 10.1]
#   Role Execution Rounds:   lib: 3, pretense: 4, pretense_coverage: 3, pretense_qa: 5 (Total: 15)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface for the synchronous DAG execution and wave scheduling engine."""

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
    """Error reported when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Error reported when a referenced node identifier is absent from the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Error reported when a node identifier is registered more than once.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
    """

    node_id: str


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Error describing an unhandled exception raised by a node action.

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
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Adds a task node to the graph.

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
            retries: Number of permitted retry attempts upon exception.

        Raises:
            DuplicateNodeError: When node_id is already registered in the graph.

        The node definition is registered, directed dependency edges are added for
        every supplied dependency, and existence checks for referenced nodes are
        deferred until validation or topological sorting.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        Raises:
            NodeNotFoundError: When either referenced identifier is absent.

        A directed dependency edge is established from upstream_id to downstream_id.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        Raises:
            NodeNotFoundError: When node_id is absent from the graph.

        The node and its incident edges are purged together with any scheduler
        tracking state that referenced the removed identifier.
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
            NodeNotFoundError: When node_id is absent from the graph.
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
            NodeNotFoundError: When node_id is absent from the graph.

        Every direct upstream dependency of the node is included in the result.
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
            NodeNotFoundError: When node_id is absent from the graph.

        Every direct downstream dependent of the node is included in the result.
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
            NodeNotFoundError: When any referenced dependency is absent from the graph.
            CycleError: When the graph contains a directed cycle.

        Valid graphs complete without error.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority
        (descending), then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.

        Raises:
            CycleError: When the graph contains a directed cycle.

        The returned ordering places every prerequisite before its dependents and
        breaks ties using priority descending then lexicographical identifier ascending.
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

        The result is the sequence of nodes forming the longest path through the DAG
        together with the cumulative weight of that path.
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

        Every READY node whose upstream dependencies have succeeded is returned,
        ordered by priority descending and then node identifier ascending; an empty
        list is returned when nothing is ready.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.

        The tracked node state becomes RUNNING.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.

        The tracked node state becomes SUCCEEDED and downstream dependents whose
        prerequisites have all succeeded are promoted to READY.
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

        The tracked node state becomes FAILED. SKIP_DOWNSTREAM transitions every
        transitive dependent to SKIPPED, FAIL_FAST cancels all remaining pending
        nodes, and CONTINUE_ON_ERROR leaves unblocked independent nodes eligible
        while skipping dependents blocked by failed nodes.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.

        Completion is reported when every node is terminal, when no ready nodes
        remain and unexecuted nodes are blocked by failed dependencies, and for an
        empty DAG. A False result indicates that some node remains eligible to run.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Current NodeState.

        Raises:
            NodeNotFoundError: When node_id is not registered in the scheduled DAG.
        """
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph.

        Returns:
            Mapping of node identifier to current NodeState, reflecting only
            currently registered nodes.
        """
        ...


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        Args:
            failure_policy: Failure policy applied upon node action failure.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        Raises:
            NodeNotFoundError: When any referenced dependency is absent from the graph.
            CycleError: When the graph contains a directed cycle.

        Graph invariants are validated before wave execution begins, ready waves run
        sequentially, failed actions are retried up to their configured retry count,
        the failure policy is applied through the scheduler, and a consolidated
        report describes every node state, duration, and the critical path.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:35:23Z
# LAST_CHANGED: 2026-11-12T16:35:23Z
# CHANGE: Author interface module: frozen dataclass records (NodeDefinition, NodeResult, DAGRunReport), non-frozen exception hierarchy with message rendering, NodeState/FailurePolicy enums, and abstract DAG/WaveScheduler/DAGRunner protocols with Singleton[SystemTier] tier inheritance and stub operations.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
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
    Set,
    Tuple,
)

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite

_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.CANCELLED,
        dag_engine_lite.NodeState.SKIPPED,
    }
)

_UNSUCCESSFUL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.CANCELLED,
        dag_engine_lite.NodeState.SKIPPED,
    }
)


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the directed acyclic graph.

    Adjacency dictionaries map node identifiers to their definitions and to their
    upstream and downstream neighbor sets. Deterministic ordering uses Kahn's
    algorithm over a priority-ordered heap, while longest-path analysis uses
    dynamic programming along the computed topological order.
    """

    tier = "system"

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
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Adds a task node to the graph."""
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )
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
        # Register the definition and its adjacency slots before wiring the edges.
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            # Missing dependency identifiers stay unreported until validation.
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        missing_id: Optional[str] = None
        if upstream_id not in self._nodes:
            missing_id = upstream_id
        elif downstream_id not in self._nodes:
            missing_id = downstream_id
        if missing_id is not None:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{missing_id}' is not registered in the DAG",
                node_id=missing_id,
            )
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        for upstream_id in list(self._upstream.get(node_id, set())):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in list(self._downstream.get(node_id, set())):
            self._upstream.get(downstream_id, set()).discard(node_id)
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
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
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
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._nodes[node_id].dependencies):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' declares unknown dependency "
                            f"'{dependency}'"
                        ),
                        node_id=dependency,
                    )
        cycle = self._find_cycle(self._nodes)
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        node_ids = set(self._nodes)
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()) & node_ids)
            for node_id in node_ids
        }
        priorities: Dict[str, float] = {
            node_id: float(self._nodes[node_id].priority) for node_id in node_ids
        }
        # Seed the heap with all currently unconstrained nodes; ties fall back to
        # the lexicographically smallest identifier because entries are tuples.
        heap: List[Tuple[float, str]] = []
        for node_id in node_ids:
            if in_degree[node_id] == 0:
                heapq.heappush(heap, (-priorities[node_id], node_id))
        order: List[str] = []
        while heap:
            _negated_priority, node_id = heapq.heappop(heap)
            order.append(node_id)
            for downstream_id in sorted(self._downstream.get(node_id, set())):
                if downstream_id in in_degree:
                    in_degree[downstream_id] -= 1
                    if in_degree[downstream_id] == 0:
                        heapq.heappush(
                            heap,
                            (-priorities[downstream_id], downstream_id),
                        )
        if len(order) != len(node_ids):
            remaining = node_ids - set(order)
            cycle = self._find_cycle(remaining)
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=cycle if cycle is not None else tuple(sorted(remaining)),
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if not (self._upstream.get(node_id, set()) & set(self._nodes))
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if not (self._downstream.get(node_id, set()) & set(self._nodes))
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        order = self.topological_sort()
        if not order:
            return [], 0.0
        node_ids = set(order)
        earliest_finish: Dict[str, float] = {}
        best_parent: Dict[str, Optional[str]] = {}
        for node_id in order:
            if estimated_durations is not None:
                duration = estimated_durations.get(node_id, 1.0)
            else:
                duration = 1.0
            predecessors = {
                dependency
                for dependency in self._upstream.get(node_id, set())
                if dependency in node_ids
            }
            if not predecessors:
                earliest_finish[node_id] = duration
                best_parent[node_id] = None
            else:
                # The predecessor finishing latest determines the earliest start;
                # the identifier order makes the choice deterministic.
                best_predecessor = max(
                    predecessors,
                    key=lambda predecessor: (
                        earliest_finish.get(predecessor, 0.0),
                        predecessor,
                    ),
                )
                earliest_finish[node_id] = (
                    earliest_finish.get(best_predecessor, 0.0) + duration
                )
                best_parent[node_id] = best_predecessor
        terminal_id = max(
            order, key=lambda node_id: (earliest_finish[node_id], node_id)
        )
        total_weight = earliest_finish[terminal_id]
        path: List[str] = []
        current: Optional[str] = terminal_id
        while current is not None:
            path.append(current)
            current = best_parent.get(current)
        path.reverse()
        return path, total_weight

    def _find_cycle(self, candidates: Collection[str]) -> Optional[Tuple[str, ...]]:
        """Traces a directed cycle among the candidate nodes, if one exists."""
        remaining = set(candidates)
        visited: Set[str] = set()
        active: List[str] = []
        for start in sorted(remaining):
            if start in visited:
                continue
            visited.add(start)
            active.append(start)
            stack: List[Tuple[str, List[str]]] = [
                (start, sorted(self._downstream.get(start, set()) & remaining))
            ]
            while stack:
                current, pending = stack[-1]
                if not pending:
                    stack.pop()
                    active.pop()
                    continue
                neighbor = pending.pop(0)
                if neighbor in active:
                    index = active.index(neighbor)
                    return tuple(active[index:] + [neighbor])
                if neighbor not in visited:
                    visited.add(neighbor)
                    active.append(neighbor)
                    stack.append(
                        (
                            neighbor,
                            sorted(
                                self._downstream.get(neighbor, set()) & remaining
                            ),
                        )
                    )
        return None


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of the sequential wave scheduler.

    Tracks the execution state of every node discovered in the active DAG,
    initializing roots as ready and dependent nodes as pending, and promotes
    dependents when their prerequisites succeed.
    """

    tier = "system"

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        dag = self._sync_states()
        # Only nodes already promoted to READY are candidates; promotion itself
        # belongs to the success transition, so this selection never mutates state.
        candidates = [
            node_id
            for node_id, state in self._states.items()
            if state is dag_engine_lite.NodeState.READY
            and self._dependencies_succeeded(dag, node_id)
        ]
        candidates.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks dependents."""
        dag = self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dependent_id in sorted(dag.get_dependents(node_id)):
            if self._states.get(dependent_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            if self._dependencies_succeeded(dag, dependent_id):
                self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        dag = self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        node_ids = dag.all_nodes()
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # No further work may start once a failure is observed.
            for other_id in sorted(node_ids):
                if self._states.get(other_id) not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # Every transitive dependent can no longer satisfy its prerequisites.
            for dependent_id in self._collect_dependents(dag, node_id):
                if self._states.get(dependent_id) not in _TERMINAL_STATES:
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
        else:
            # Independent nodes stay eligible while nodes blocked by any failed
            # prerequisite are skipped.
            for other_id in sorted(node_ids):
                if self._states.get(other_id) in _TERMINAL_STATES:
                    continue
                if self._blocked_by_failure(dag, other_id, node_ids):
                    self._states[other_id] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        dag = self._sync_states()
        node_ids = dag.all_nodes()
        if not node_ids:
            return True
        for node_id in sorted(node_ids):
            if self._states.get(node_id) in _TERMINAL_STATES:
                continue
            if not self._blocked_by_failure(dag, node_id, node_ids):
                return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        dag = self._sync_states()
        if node_id not in dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        state = self._states.get(node_id)
        if state is None:
            # Synchronization seeds every registered node, so this fallback is
            # retained only as a defensive tripwire.
            with unreachable():
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        dag = self._sync_states()
        node_ids = dag.all_nodes()
        return {
            node_id: self._states[node_id]
            for node_id in node_ids
            if node_id in self._states
        }

    def _sync_states(self) -> dag_engine_lite.DAG:
        """Aligns tracked node state with the nodes currently registered in the DAG."""
        dag = get_singleton(dag_engine_lite.DAG)
        node_ids = dag.all_nodes()
        for node_id in node_ids:
            if node_id in self._states:
                continue
            # Roots begin ready; nodes with prerequisites wait for promotion.
            if dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine_lite.NodeState.READY
        for node_id in list(self._states):
            if node_id not in node_ids:
                del self._states[node_id]
        return dag

    def _dependencies_succeeded(
        self, dag: dag_engine_lite.DAG, node_id: str
    ) -> bool:
        """Reports whether every direct prerequisite of the node has succeeded."""
        for dependency in dag.get_dependencies(node_id):
            if self._states.get(dependency) is not dag_engine_lite.NodeState.SUCCEEDED:
                return False
        return True

    def _collect_dependents(
        self, dag: dag_engine_lite.DAG, node_id: str
    ) -> List[str]:
        """Collects all transitive dependents reachable from the given node."""
        collected: Set[str] = set()
        pending: List[str] = [node_id]
        while pending:
            current = pending.pop()
            for dependent_id in dag.get_dependents(current):
                if dependent_id in collected:
                    continue
                collected.add(dependent_id)
                pending.append(dependent_id)
        return sorted(collected)

    def _blocked_by_failure(
        self,
        dag: dag_engine_lite.DAG,
        node_id: str,
        node_ids: Set[str],
    ) -> bool:
        """Reports whether the node or any transitive prerequisite is failed."""
        seen: Set[str] = set()
        pending: List[str] = [node_id]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if self._states.get(current) in _UNSUCCESSFUL_STATES:
                return True
            if current not in node_ids:
                continue
            pending.extend(dag.get_dependencies(current))
        return False


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of the sequential DAG execution runner.

    Validates the graph, drains ready waves one node at a time, retries failing
    actions according to their configured retry counts, applies the requested
    failure policy, and consolidates every outcome into a run report.
    """

    tier = "system"

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        # Missing dependencies and cycles abort the run before any action executes.
        dag.validate()
        self._results = {}
        start_time = time.perf_counter()
        halted = False
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                if halted:
                    break
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                action_start = time.perf_counter()
                attempts = 0
                value: Any = None
                error: Optional[Exception] = None
                while True:
                    try:
                        value = definition.action()
                        error = None
                        break
                    except Exception as exc:
                        # Failures are captured and accounted for by the report.
                        error = exc
                        if attempts < definition.retries:
                            attempts += 1
                            continue
                        break
                duration_seconds = time.perf_counter() - action_start
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult[Any](
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration_seconds,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    failure = dag_engine_lite.NodeExecutionError(
                        message=f"Node '{node_id}' failed: {error}",
                        node_id=node_id,
                        cause=error,
                    )
                    self._results[node_id] = dag_engine_lite.NodeResult[Any](
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=failure,
                        duration_seconds=duration_seconds,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
        # Record default outcomes for nodes that never executed.
        for node_id, state in scheduler.get_all_states().items():
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
        critical_path, _critical_weight = dag.compute_critical_path(None)
        wall_clock_seconds = time.perf_counter() - start_time
        succeeded_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.CANCELLED
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:57:20Z
# LAST_CHANGED: 2026-11-12T16:52:06Z
# CHANGE: Fix pretense QA postcondition divergence for next_wave.ready_nodes: next_wave no longer promotes PENDING dependents to READY while selecting the wave. It now purely gathers nodes already in READY state whose upstream dependencies succeeded, leaving readiness promotion exclusively to mark_succeeded as the contract requires, so a dependent such as beta whose prerequisite alpha has not succeeded remains PENDING.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T16:57:20Z
# PRETENSE_QA_AUDIT: 2026-11-12T16:57:07Z
# --- END AUTOFAB METADATA ---
