# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_001819_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-13T00:18:19.395075+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 205,541
#   Cached Inbound Tokens:   14,909,312
#   Outbound Tokens:         219,126
#   Total Tokens:            15,333,979
#   Financial Cost ($USD):   $0.2070
#   Wall Clock Duration:     1294.59s
#   Step Latencies (s):      [209.6, 485.0, 20.3, 281.1, 53.6, 196.9, 94.2, 207.1, 20.4, 20.3]
#   Role Execution Rounds:   lib: 2, pretense: 3, pretense_coverage: 2, pretense_qa: 3 (Total: 10)
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
"""Interface definitions for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

from support.lib.framework import data_type, operation
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
    """Error raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Error raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Error raised when adding a node identifier that already exists in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
    """

    node_id: str


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Error raised when an unhandled exception occurs during node action execution.

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
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.
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
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.
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
        """Validates graph consistency, completeness, and acyclicity."""
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.
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


class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        Returns:
            List of node identifiers ready for execution, ordered by priority descending.
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
            Mapping of node identifier to current NodeState, reflecting only currently registered nodes.
        """
        ...


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
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:21:34Z
# LAST_CHANGED: 2026-11-13T00:21:34Z
# CHANGE: Authored interface module: DAGError/CycleError/NodeNotFoundError/DuplicateNodeError/NodeExecutionError domain errors (non-frozen dataclasses with __str__), NodeState and FailurePolicy enums, frozen NodeDefinition/NodeResult/DAGRunReport data types, and DAG/WaveScheduler/DAGRunner service protocols inheriting Singleton[SystemTier] with operation stubs.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete services for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite

_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

_BLOCKING_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)


@singleton
class DAG(dag_engine_lite.DAG):
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
        # Reject duplicate identifiers before mutating any graph storage.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )
        # Freeze the requested upstream identifiers without verifying that they exist yet.
        dependency_set: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
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
        # Record an incoming edge per dependency, deferring existence checks to validation.
        for dependency_id in dependency_set:
            self._downstream.setdefault(dependency_id, set()).add(node_id)
            self._upstream[node_id].add(dependency_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Both endpoints must already be registered nodes.
        for required_id in (upstream_id, downstream_id):
            if required_id not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    message=f"Node '{required_id}' is not registered in the DAG",
                    node_id=required_id,
                )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        # Detach the node from every neighbor before dropping its own bookkeeping entries.
        for upstream_id in tuple(self._upstream.get(node_id, set())):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in tuple(self._downstream.get(node_id, set())):
            self._upstream.get(downstream_id, set()).discard(node_id)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)
        del self._nodes[node_id]

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
        # Hand out a copy so callers cannot mutate internal adjacency state.
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
        # Every referenced dependency must be a registered node.
        for node_id in sorted(self._nodes):
            for dependency_id in sorted(self._upstream.get(node_id, set())):
                if dependency_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' depends on unknown node '{dependency_id}'"
                        ),
                        node_id=dependency_id,
                    )
        # Depth-first sweep over incoming edges, tracking the active recursion path so a
        # repeated node on that path isolates the cyclic identifier sequence.
        visited: Set[str] = set()
        active_path: List[str] = []

        def visit(node_id: str) -> None:
            if node_id in active_path:
                start = active_path.index(node_id)
                cycle: Tuple[str, ...] = tuple(active_path[start:] + [node_id])
                raise dag_engine_lite.CycleError(
                    message="Cycle detected in DAG",
                    cycle=cycle,
                )
            if node_id in visited:
                return
            active_path.append(node_id)
            for dependency_id in sorted(self._upstream.get(node_id, set())):
                if dependency_id in self._nodes:
                    visit(dependency_id)
            active_path.pop()
            visited.add(node_id)

        for node_id in sorted(self._nodes):
            visit(node_id)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        node_ids = set(self._nodes)
        # Count unresolved prerequisites, ignoring identifiers outside the registered set.
        in_degree: Dict[str, int] = {node_id: 0 for node_id in node_ids}
        for node_id in node_ids:
            for dependency_id in self._upstream.get(node_id, set()):
                if dependency_id in node_ids:
                    in_degree[node_id] += 1
        # Max-heap keyed by negated priority, then lexicographically ascending identifier.
        ready: List[Tuple[int, str]] = []
        for node_id in node_ids:
            if in_degree[node_id] == 0:
                heapq.heappush(ready, (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while ready:
            _neg_priority, node_id = heapq.heappop(ready)
            order.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                if dependent_id in in_degree:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        heapq.heappush(
                            ready,
                            (-self._nodes[dependent_id].priority, dependent_id),
                        )
        if len(order) != len(node_ids):
            # Nodes left unplaced participate in at least one directed cycle.
            remaining = node_ids - set(order)
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=self._reconstruct_cycle(remaining),
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id, set())
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not self._downstream.get(node_id, set())
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return [], 0.0
        # Accumulate earliest completion times along the topological order.
        earliest_finish: Dict[str, float] = {}
        best_parent: Dict[str, Optional[str]] = {}
        for node_id in order:
            duration = (
                estimated_durations.get(node_id, 1.0)
                if estimated_durations is not None
                else 1.0
            )
            predecessors = {
                predecessor_id
                for predecessor_id in self._upstream.get(node_id, set())
                if predecessor_id in self._nodes
            }
            if not predecessors:
                earliest_finish[node_id] = duration
                best_parent[node_id] = None
            else:
                chosen_parent = max(
                    predecessors,
                    key=lambda predecessor_id: (
                        earliest_finish.get(predecessor_id, 0.0),
                        predecessor_id,
                    ),
                )
                earliest_finish[node_id] = (
                    earliest_finish.get(chosen_parent, 0.0) + duration
                )
                best_parent[node_id] = chosen_parent
        # The most expensive terminal node anchors the backtracking reconstruction.
        terminal_id = max(
            order,
            key=lambda node_id: (earliest_finish[node_id], node_id),
        )
        total_weight = earliest_finish[terminal_id]
        path: List[str] = []
        current_id: Optional[str] = terminal_id
        while current_id is not None:
            path.append(current_id)
            current_id = best_parent.get(current_id)
        path.reverse()
        return path, total_weight

    def _reconstruct_cycle(self, remaining: Set[str]) -> Tuple[str, ...]:
        # Depth-first sweep restricted to unplaced nodes, recording the back-edge path.
        state: Dict[str, int] = {node_id: 0 for node_id in remaining}
        path: List[str] = []

        def visit(node_id: str) -> bool:
            state[node_id] = 1
            path.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                # The unplaced remainder is closed under downstream traversal.
                if dependent_id not in remaining:
                    with unreachable:
                        continue
                if state[dependent_id] == 1:
                    start = path.index(dependent_id)
                    cycle = path[start:] + [dependent_id]
                    path.clear()
                    path.extend(cycle)
                    return True
                if state[dependent_id] == 0 and visit(dependent_id):
                    return True
            path.pop()
            state[node_id] = 2
            return False

        for node_id in sorted(remaining):
            if state[node_id] == 0 and visit(node_id):
                return tuple(path)
        # Any unplaced remainder necessarily contains a directed cycle to report.
        with unreachable:
            return tuple(sorted(remaining))


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = "system"

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._active_dag()
        self._synchronize(dag)
        # Promote any pending node whose upstream dependencies have all succeeded.
        for node_id in sorted(self._states):
            if self._states[node_id] is not dag_engine_lite.NodeState.PENDING:
                continue
            if self._dependencies_succeeded(dag, node_id):
                self._states[node_id] = dag_engine_lite.NodeState.READY
        candidates: List[str] = []
        for node_id in sorted(self._states):
            if self._states[node_id] is not dag_engine_lite.NodeState.READY:
                continue
            if self._dependencies_succeeded(dag, node_id):
                candidates.append(node_id)
        candidates.sort(
            key=lambda node_id: (-dag.get_node(node_id).priority, node_id)
        )
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        dag = self._active_dag()
        self._synchronize(dag)
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        dag = self._active_dag()
        self._synchronize(dag)
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Release pending dependents whose upstream prerequisites are now all satisfied.
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
        dag = self._active_dag()
        self._synchronize(dag)
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Abandon every remaining node that has not reached a terminal state.
            for candidate_id in sorted(self._states):
                if self._states[candidate_id] in _TERMINAL_STATES:
                    continue
                self._states[candidate_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # Skip every transitive dependent of the failed node.
            for dependent_id in sorted(self._transitive_dependents(dag, node_id)):
                if self._states.get(dependent_id) in _TERMINAL_STATES:
                    continue
                self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
        else:
            # Keep independent branches runnable while skipping dependents blocked by failure.
            self._skip_blocked(dag)

    @operation
    @override
    def is_finished(self) -> bool:
        dag = self._active_dag()
        self._synchronize(dag)
        if not self._states:
            return True
        if all(state in _TERMINAL_STATES for state in self._states.values()):
            return True
        # A non-terminal node without a blocked prerequisite can still execute.
        for node_id, state in self._states.items():
            if state in _TERMINAL_STATES:
                continue
            if not self._blocked(dag, node_id):
                return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        dag = self._active_dag()
        if node_id not in dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        self._synchronize(dag)
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._active_dag()
        self._synchronize(dag)
        registered = dag.all_nodes()
        return {
            node_id: self._states[node_id]
            for node_id in sorted(registered)
            if node_id in self._states
        }

    def _active_dag(self) -> dag_engine_lite.DAG:
        dag = get_singleton(dag_engine_lite.DAG)
        self._dag = dag
        return dag

    def _synchronize(self, dag: dag_engine_lite.DAG) -> None:
        # Drop tracking state for nodes that were removed from the graph.
        registered = dag.all_nodes()
        for node_id in sorted(self._states):
            if node_id not in registered:
                del self._states[node_id]
        # Discover newly registered nodes, seeding roots as ready and others as pending.
        for node_id in sorted(registered):
            if node_id in self._states:
                continue
            if dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine_lite.NodeState.READY

    def _dependencies_succeeded(self, dag: dag_engine_lite.DAG, node_id: str) -> bool:
        return all(
            self._states.get(dependency_id)
            is dag_engine_lite.NodeState.SUCCEEDED
            for dependency_id in dag.get_dependencies(node_id)
        )

    def _blocked(self, dag: dag_engine_lite.DAG, node_id: str) -> bool:
        return any(
            self._states.get(dependency_id) in _BLOCKING_STATES
            for dependency_id in dag.get_dependencies(node_id)
        )

    def _skip_blocked(self, dag: dag_engine_lite.DAG) -> None:
        # Iterate to a fixpoint so skipping one node also blocks its downstream dependents.
        changed = True
        while changed:
            changed = False
            for node_id in sorted(self._states):
                if self._states[node_id] in _TERMINAL_STATES:
                    continue
                if self._blocked(dag, node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.SKIPPED
                    changed = True

    def _transitive_dependents(self, dag: dag_engine_lite.DAG, node_id: str) -> Set[str]:
        found: Set[str] = set()
        frontier: List[str] = sorted(dag.get_dependents(node_id))
        while frontier:
            current_id = frontier.pop()
            if current_id in found:
                continue
            found.add(current_id)
            frontier.extend(sorted(dag.get_dependents(current_id)))
        return found


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    tier = "system"

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler
        # Surface missing dependencies or cycles before any node action executes.
        dag.validate()
        self._results = {}
        start_time = time.monotonic()
        halted = False
        while not halted and not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                node_start = time.monotonic()
                retries_attempted = 0
                value: Any = None
                error: Optional[Exception] = None
                # Attempt the action once plus one attempt per permitted retry.
                while True:
                    try:
                        value = definition.action()
                        error = None
                        break
                    except Exception as caught:
                        error = caught
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        break
                duration_seconds = time.monotonic() - node_start
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult[Any](
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    # Reify the caught failure into a contracted node outcome.
                    self._results[node_id] = dag_engine_lite.NodeResult[Any](
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=error,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
        # Materialize outcome records for nodes the scheduler terminated without executing.
        for node_id, state in sorted(scheduler.get_all_states().items()):
            if node_id in self._results:
                continue
            if state not in _TERMINAL_STATES:
                continue
            self._results[node_id] = dag_engine_lite.NodeResult[Any](
                node_id=node_id,
                state=state,
            )
        critical_path, _critical_weight = dag.compute_critical_path(None)
        wall_clock_seconds = time.monotonic() - start_time
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
# LAST_CLEANED: 2026-11-13T00:39:42Z
# LAST_CHANGED: 2026-11-13T00:31:58Z
# CHANGE: Quarantined pretense-coverage unreachable facets in cycle reconstruction: the downstream-closed membership filter and the defensive no-cycle fallback are now wrapped in 'with unreachable:' per the companion guide, preserving the defensive logic while marking it unreachable.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:39:42Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:39:18Z
# --- END AUTOFAB METADATA ---
