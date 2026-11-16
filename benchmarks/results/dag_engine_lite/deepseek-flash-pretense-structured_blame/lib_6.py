# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_171853_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-15T17:18:53.293393+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 6
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 342,594
#   Cached Inbound Tokens:   19,579,256
#   Outbound Tokens:         339,295
#   Total Tokens:            20,261,145
#   Financial Cost ($USD):   $0.3137
#   Wall Clock Duration:     2536.52s
#   Step Latencies (s):      [342.7, 573.8, 245.7, 409.7, 112.5, 40.9, 20.3, 184.4, 53.4, 61.6, 391.8, 92.3, 20.3, 71.6, 51.0, 20.3, 81.9, 61.4, 20.3, 30.6]
#   Role Execution Rounds:   lib: 3, pretense_coverage: 4, pretense_impl: 5, pretense_intf: 2, pretense_qa: 6 (Total: 20)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface specification for the synchronous DAG execution and wave scheduling engine."""

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
class DuplicateNodeError(DAGError):
    """Raised when attempting to add a node identifier that already exists in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
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

        A duplicate node identifier is rejected with DuplicateNodeError. The
        registered definition stores a frozen dependency collection, and directed
        edges are recorded from each dependency to the new node. Dependency
        existence is deliberately not checked here; it is deferred to validation
        and topological sorting so callers may register nodes in any order.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        Both identifiers must already be registered; otherwise NodeNotFoundError
        is raised.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        The node must exist; otherwise NodeNotFoundError is raised. Incident
        edges are purged together with the scheduler state tracking for the
        removed identifier.
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

        Raises NodeNotFoundError when the identifier is not registered.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.

        Raises NodeNotFoundError when the identifier is not registered.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.

        Raises NodeNotFoundError when the identifier is not registered.
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

        Every referenced dependency must exist, otherwise NodeNotFoundError is
        raised. A directed cycle is rejected with CycleError carrying the cyclic
        node sequence. A consistent, complete, and acyclic graph validates
        without error.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority
        (descending), then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.

        Raises CycleError when the graph contains a directed cycle.
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
            estimated_durations: Optional mapping of node identifiers to duration
                weights. Defaults to 1.0 per node if omitted.

        Returns:
            Tuple of (critical path node identifiers, total path weight).

        The returned sequence forms the longest path through the DAG and the
        returned weight is that path's cumulative weight.
        """
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        Returns:
            List of node identifiers ready for execution, ordered by priority
            descending.

        Only nodes currently in READY state whose upstream dependencies have all
        succeeded are returned. Nodes are ordered by priority descending and then
        by node identifier ascending. An empty list is returned when no node is
        ready.
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

        Newly unblocked dependents are promoted to READY.
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

        Under the fail-fast policy every remaining pending node is cancelled.
        Under the skip-downstream policy all transitive dependents are skipped.
        Under the continue-on-error policy independent nodes stay eligible for
        execution while blocked dependents of failed nodes are skipped.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.

        Also returns True when no ready nodes remain and the unexecuted nodes are
        blocked by failed dependencies, and when the DAG contains no nodes.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Current NodeState.

        Raises NodeNotFoundError when the identifier is not registered in the
        scheduled DAG.
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

        Graph invariants are validated before wave execution begins; missing
        dependencies raise NodeNotFoundError and directed cycles raise
        CycleError. Ready waves execute sequentially, failed actions are retried
        up to their configured retry count, and the supplied failure policy is
        applied to the scheduler upon failure. The returned report captures all
        node states, execution durations, and the critical path.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T17:24:23Z
# LAST_CHANGED: 2026-11-15T17:24:23Z
# CHANGE: Implement interface module: error hierarchy, NodeState/FailurePolicy enums, NodeDefinition/NodeResult/DAGRunReport data types, and DAG/WaveScheduler/DAGRunner service protocols with operation contracts.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete realization of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite

# States from which a node never transitions again.
_TERMINAL_STATES: Tuple[dag_engine_lite.NodeState, ...] = (
    dag_engine_lite.NodeState.SUCCEEDED,
    dag_engine_lite.NodeState.FAILED,
    dag_engine_lite.NodeState.SKIPPED,
    dag_engine_lite.NodeState.CANCELLED,
)

# Terminal states that make every dependent node unrunnable.
_BLOCKING_STATES: Tuple[dag_engine_lite.NodeState, ...] = (
    dag_engine_lite.NodeState.FAILED,
    dag_engine_lite.NodeState.SKIPPED,
    dag_engine_lite.NodeState.CANCELLED,
)


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = "system"

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def _link(self, upstream_id: str, downstream_id: str) -> None:
        # Record a directed dependency edge in both adjacency directions.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    def _kahn_order(self) -> Tuple[List[str], Set[str]]:
        # Deterministic Kahn ordering; also returns nodes left unplaced by cycles.
        node_ids = set(self._nodes.keys())
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()) & node_ids) for node_id in node_ids
        }
        heap: List[Tuple[int, str]] = []
        for node_id in node_ids:
            if in_degree[node_id] == 0:
                definition = self._nodes[node_id]
                heapq.heappush(heap, (-definition.priority, node_id))

        order: List[str] = []
        while heap:
            _negated_priority, node_id = heapq.heappop(heap)
            order.append(node_id)
            for dependent_id in self._downstream.get(node_id, set()):
                # Recorded dependents always belong to the registered node set.
                if dependent_id not in in_degree:
                    unreachable("recorded dependents are always registered nodes")
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    definition = self._nodes[dependent_id]
                    heapq.heappush(heap, (-definition.priority, dependent_id))

        return order, node_ids - set(order)

    def _cycle_sequence(self, candidates: Set[str]) -> Tuple[str, ...]:
        # Reconstruct a concrete cyclic node sequence via depth-first search.
        visit_state: Dict[str, int] = {node_id: 0 for node_id in candidates}
        stack: List[str] = []
        sequence: Tuple[str, ...] = tuple(sorted(candidates))

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            visit_state[node_id] = 1
            stack.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                # A dependent of an unplaced node is itself unplaced.
                if dependent_id not in candidates:
                    unreachable("dependents of unplaced nodes are unplaced")
                if visit_state[dependent_id] == 1:
                    start = stack.index(dependent_id)
                    return tuple(stack[start:] + [dependent_id])
                if visit_state[dependent_id] == 0:
                    found = visit(dependent_id)
                    if found is not None:
                        return found
            stack.pop()
            visit_state[node_id] = 2
            return None

        for node_id in sorted(candidates):
            if visit_state[node_id] != 0:
                continue
            found = visit(node_id)
            if found is not None:
                sequence = found
                break

        return sequence

    def _cycle_error(self, remaining: Set[str]) -> dag_engine_lite.CycleError:
        cycle = self._cycle_sequence(remaining)
        return dag_engine_lite.CycleError(
            message="Cycle detected in DAG",
            cycle=cycle,
        )

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
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )

        dependency_set = frozenset(dependencies) if dependencies is not None else frozenset()
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # Dependency existence checks are deferred; edges are recorded eagerly.
        for dependency in dependency_set:
            self._link(dependency, node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        for node_id in (upstream_id, downstream_id):
            if node_id not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    message=f"Node '{node_id}' is not registered in the DAG",
                    node_id=node_id,
                )
        self._link(upstream_id, downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )

        for upstream_id in self._upstream.get(node_id, set()):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self._downstream.get(node_id, set()):
            self._upstream.get(downstream_id, set()).discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Every registered dependency edge must name a registered node.
        for node_id in self._nodes:
            for dependency in self._upstream.get(node_id, set()):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' depends on unregistered node "
                            f"'{dependency}'"
                        ),
                        node_id=dependency,
                    )

        _order, remaining = self._kahn_order()
        if remaining:
            raise self._cycle_error(remaining)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        order, remaining = self._kahn_order()
        if remaining:
            raise self._cycle_error(remaining)
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return [], 0.0

        earliest_finish: Dict[str, float] = {}
        best_predecessor: Dict[str, Optional[str]] = {}
        for node_id in order:
            if estimated_durations is not None:
                duration = estimated_durations.get(node_id, 1.0)
            else:
                duration = 1.0
            predecessors = [
                upstream_id
                for upstream_id in self._upstream.get(node_id, set())
                if upstream_id in self._nodes
            ]
            if not predecessors:
                earliest_finish[node_id] = duration
                best_predecessor[node_id] = None
                continue
            # Accumulate the largest upstream completion time to extend the path.
            best = max(predecessors, key=lambda p: (earliest_finish.get(p, 0.0), p))
            earliest_finish[node_id] = earliest_finish.get(best, 0.0) + duration
            best_predecessor[node_id] = best

        terminal = max(order, key=lambda n: (earliest_finish[n], n))
        total_weight = earliest_finish[terminal]
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = best_predecessor.get(current)
        path.reverse()
        return path, total_weight


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of the sequential wave scheduler."""

    tier = "system"

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        dag = get_singleton(dag_engine_lite.DAG)
        if self._dag is not dag:
            # A newly resolved graph invalidates all previously tracked node states.
            self._dag = dag
            self._states = {}
        return dag

    def _synchronize(self) -> Set[str]:
        # Reconcile tracked states with the nodes currently registered in the DAG.
        dag = self._resolve_dag()
        node_ids = dag.all_nodes()
        for tracked_id in list(self._states.keys()):
            if tracked_id not in node_ids:
                del self._states[tracked_id]
        for node_id in node_ids:
            if node_id in self._states:
                continue
            if dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine_lite.NodeState.READY
        # Nodes registered after their prerequisites completed are ready at once.
        self._promote_ready()
        return node_ids

    def _promote_ready(self) -> None:
        # Promote pending nodes whose upstream prerequisites have all succeeded.
        dag = self._resolve_dag()
        promoted = True
        while promoted:
            promoted = False
            for node_id, state in self._states.items():
                if state is not dag_engine_lite.NodeState.PENDING:
                    continue
                dependencies = dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    self._states[node_id] = dag_engine_lite.NodeState.READY
                    promoted = True

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        dag = self._resolve_dag()
        discovered: Set[str] = set()
        pending: List[str] = [node_id]
        while pending:
            current = pending.pop()
            for dependent_id in dag.get_dependents(current):
                if dependent_id in discovered:
                    continue
                discovered.add(dependent_id)
                pending.append(dependent_id)
        return discovered

    def _blocked_by_failure(self) -> Set[str]:
        # Find every unexecuted node invalidated by a failed or skipped node.
        dag = self._resolve_dag()
        blocked: Set[str] = set()
        changed = True
        while changed:
            changed = False
            for node_id, state in self._states.items():
                if state in _TERMINAL_STATES or node_id in blocked:
                    continue
                for dependency in dag.get_dependencies(node_id):
                    dependency_state = self._states.get(dependency)
                    if (
                        dependency in blocked
                        or dependency_state is None
                        or dependency_state in _BLOCKING_STATES
                    ):
                        blocked.add(node_id)
                        changed = True
                        break
        return blocked

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._resolve_dag()
        self._synchronize()
        ready: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                ready.append(node_id)
        # Highest priority first, breaking ties by ascending node identifier.
        ready.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        return ready

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        self._promote_ready()

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Abandon every node that has not reached a terminal state yet.
            for tracked_id, state in list(self._states.items()):
                if state not in _TERMINAL_STATES:
                    self._states[tracked_id] = dag_engine_lite.NodeState.CANCELLED
            return

        if failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # Skip the full downstream closure of the failed node.
            for dependent_id in self._transitive_dependents(node_id):
                if self._states.get(dependent_id) not in _TERMINAL_STATES:
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
            return

        # Continue-on-error: keep independent work eligible and skip the rest.
        blocked = self._blocked_by_failure()
        for tracked_id, state in list(self._states.items()):
            if state in _TERMINAL_STATES or tracked_id not in blocked:
                continue
            self._states[tracked_id] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        self._synchronize()
        remaining = [
            node_id
            for node_id, state in self._states.items()
            if state not in _TERMINAL_STATES
        ]
        if not remaining:
            return True
        # Work that is still in flight or eligible to execute keeps the run alive.
        if any(
            self._states[node_id]
            in (dag_engine_lite.NodeState.READY, dag_engine_lite.NodeState.RUNNING)
            for node_id in remaining
        ):
            return False
        # Synchronization leaves no ready node to rediscover at this point.
        if self.next_wave():
            unreachable("synchronization leaves no ready node behind")
        blocked = self._blocked_by_failure()
        return all(node_id in blocked for node_id in remaining)

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        node_ids = self._synchronize()
        if node_id not in node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the scheduled DAG",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        node_ids = self._synchronize()
        return {
            node_id: state
            for node_id, state in self._states.items()
            if node_id in node_ids
        }


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of the sequential DAG execution runner."""

    tier = "system"

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _execute(
        self,
        definition: dag_engine_lite.NodeDefinition[Any],
    ) -> Tuple[Any, Optional[Exception], int, float]:
        # Run the node action, retrying the configured number of times on error.
        started = time.perf_counter()
        retries_attempted = 0
        while True:
            try:
                value = definition.action()
            except Exception as exc:  # reified into the node result record
                if retries_attempted < definition.retries:
                    retries_attempted += 1
                    continue
                elapsed = time.perf_counter() - started
                return None, exc, retries_attempted, elapsed
            elapsed = time.perf_counter() - started
            return value, None, retries_attempted, elapsed

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)

        # Graph invariants are validated before any wave executes.
        dag.validate()

        started = time.perf_counter()
        self._results = {}
        failed = False
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                if failed and failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                    break
                # A node abandoned by the failure policy is never dispatched.
                if scheduler.get_state(node_id) in _TERMINAL_STATES:
                    unreachable("ready wave nodes are never terminal")
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                value, error, retries_attempted, elapsed = self._execute(definition)
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=elapsed,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=elapsed,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    failed = True

        # Record default outcomes for nodes abandoned by the failure policy.
        for node_id in sorted(dag.all_nodes()):
            if node_id in self._results:
                continue
            state = scheduler.get_state(node_id)
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )

        critical_path, _total_weight = dag.compute_critical_path(None)
        states = scheduler.get_all_states()
        succeeded_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                node_id
                for node_id, state in states.items()
                if state is dag_engine_lite.NodeState.CANCELLED
            )
        )
        wall_clock_seconds = time.perf_counter() - started
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
# LAST_CLEANED: 2026-11-15T18:00:57Z
# LAST_CHANGED: 2026-11-15T17:54:41Z
# CHANGE: Replace unconditional 'with unreachable:' quarantine blocks (entered on every traversal step, tripping during ordinary validate) with conditional unreachable(...) tripwires inside each impossible branch, so the guard logic stays preserved but only fires when the impossible condition actually holds.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T18:00:57Z
# PRETENSE_QA_AUDIT: 2026-11-15T18:00:29Z
# --- END AUTOFAB METADATA ---
