# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261114_180540_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-14T18:05:40.776161+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 309,921
#   Cached Inbound Tokens:   22,365,952
#   Outbound Tokens:         396,216
#   Total Tokens:            23,072,089
#   Financial Cost ($USD):   $0.3513
#   Wall Clock Duration:     2282.95s
#   Step Latencies (s):      [322.0, 792.1, 132.9, 61.3, 20.3, 393.0, 104.9, 225.6, 276.2, 51.1, 133.0, 143.3, 20.3, 20.3]
#   Role Execution Rounds:   lib: 4, pretense: 3, pretense_coverage: 2, pretense_qa: 5 (Total: 14)
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
"""Interface protocols and data records for the synchronous DAG execution and wave scheduling engine."""

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

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

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


@singleton_type("system")
class DAG(Singleton[SystemTier], Protocol):
    """Directed acyclic graph holding task nodes and directed dependency edges."""

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
            DuplicateNodeError: If node_id is already registered in the graph.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        Raises:
            NodeNotFoundError: If either identifier is not registered in the graph.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        Raises:
            NodeNotFoundError: If node_id is not registered in the graph.
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
            The registered node definition.

        Raises:
            NodeNotFoundError: If node_id is not registered in the graph.
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
            NodeNotFoundError: If node_id is not registered in the graph.
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
            NodeNotFoundError: If node_id is not registered in the graph.
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
            NodeNotFoundError: If a referenced dependency is not registered in the graph.
            CycleError: If the graph contains a directed cycle.
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
            Current node state.

        Raises:
            NodeNotFoundError: If node_id is not registered in the scheduled DAG.
        """
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph.

        Returns:
            Mapping of node identifier to current node state, reflecting only currently registered nodes.
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
            Consolidated report recording all node outcomes and metrics.

        Raises:
            NodeNotFoundError: If a referenced dependency is not registered in the graph.
            CycleError: If the graph contains a directed cycle.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T18:10:50Z
# LAST_CHANGED: 2026-11-14T18:10:50Z
# CHANGE: Implement DAG engine interface: error records (duplicate/not-found/cycle/execution), NodeState and FailurePolicy enums, NodeDefinition/NodeResult/DAGRunReport frozen data types, and DAG, WaveScheduler, DAGRunner service protocols with tier scoping.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, Iterator, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite

# States from which a node never transitions again.
_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.CANCELLED,
        dag_engine_lite.NodeState.SKIPPED,
    }
)


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete directed acyclic graph backed by adjacency dictionaries."""

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
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        # A repeated identifier is a caller precondition violation.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the graph",
                node_id=node_id,
            )
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
        # Dependency edges are recorded without checking that the upstream node exists.
        for dependency_id in dependency_set:
            self._upstream[node_id].add(dependency_id)
            self._downstream.setdefault(dependency_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        for candidate_id in (upstream_id, downstream_id):
            if candidate_id not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    message=f"Node '{candidate_id}' is not registered in the graph",
                    node_id=candidate_id,
                )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        # Detach the node from every incident edge before dropping its record.
        for upstream_id in tuple(self._upstream.get(node_id, set())):
            downstream_ids = self._downstream.get(upstream_id)
            if downstream_ids is not None:
                downstream_ids.discard(node_id)
        for downstream_id in tuple(self._downstream.get(node_id, set())):
            upstream_ids = self._upstream.get(downstream_id)
            if upstream_ids is not None:
                upstream_ids.discard(node_id)
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
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
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
        # Every dependency declared by a node definition must be a registered node. Immutable
        # definitions retain their declared dependencies even after incident edges are pruned,
        # so validation inspects definitions rather than adjacency alone.
        for node_id, definition in self._nodes.items():
            for dependency_id in definition.dependencies:
                if dependency_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dependency_id}' of node '{node_id}' is not registered in the graph",
                        node_id=dependency_id,
                    )
        # A non-empty residual cycle trace means the graph is not acyclic.
        cycle = self._find_cycle(set(self._nodes))
        if cycle:
            raise dag_engine_lite.CycleError(message="Cycle detected in DAG", cycle=cycle)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        node_ids = set(self._nodes)
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()) & node_ids) for node_id in node_ids
        }
        # A max-heap keyed by negated priority with lexical tie-breaking.
        heap: List[Tuple[int, str]] = []
        for node_id in node_ids:
            if in_degree[node_id] == 0:
                heapq.heappush(heap, (-self._priority(node_id), node_id))
        order: List[str] = []
        while heap:
            _priority, node_id = heapq.heappop(heap)
            order.append(node_id)
            for dependent_id in self._downstream.get(node_id, set()):
                # Every edge endpoint is a registered node, so the index always carries its key.
                if dependent_id not in in_degree:
                    with unreachable:
                        continue
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    heapq.heappush(heap, (-self._priority(dependent_id), dependent_id))
        if len(order) != len(node_ids):
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=self._find_cycle(node_ids - set(order)),
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id, set())}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id, set())}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return [], 0.0
        node_ids = set(order)
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        # Forward accumulation of earliest completion times along the topological order.
        for node_id in order:
            duration = estimated_durations.get(node_id, 1.0) if estimated_durations is not None else 1.0
            upstream_ids = self._upstream.get(node_id, set()) & node_ids
            if not upstream_ids:
                earliest[node_id] = duration
                predecessor[node_id] = None
                continue
            best_upstream = max(upstream_ids, key=lambda candidate: (earliest.get(candidate, 0.0), candidate))
            earliest[node_id] = earliest.get(best_upstream, 0.0) + duration
            predecessor[node_id] = best_upstream
        terminal_id = max(order, key=lambda candidate: (earliest[candidate], candidate))
        total_weight = earliest[terminal_id]
        # Backtrack from the terminal node along recorded predecessors.
        path: List[str] = []
        current: Optional[str] = terminal_id
        while current is not None:
            path.append(current)
            current = predecessor.get(current)
        path.reverse()
        return path, total_weight

    def _priority(self, node_id: str) -> int:
        return self._nodes[node_id].priority

    def _find_cycle(self, candidates: Set[str]) -> Tuple[str, ...]:
        # Iterative depth-first search retaining the active recursion path.
        visited: Dict[str, int] = {node_id: 0 for node_id in candidates}
        for start_id in sorted(candidates):
            if visited.get(start_id, 0) != 0:
                continue
            path: List[str] = [start_id]
            positions: Dict[str, int] = {start_id: 0}
            visited[start_id] = 1
            stack: List[Tuple[str, Iterator[str]]] = [
                (start_id, iter(sorted(self._downstream.get(start_id, set()) & candidates)))
            ]
            while stack:
                node_id, neighbors = stack[-1]
                descended = False
                for neighbor_id in neighbors:
                    state = visited.get(neighbor_id, 0)
                    if state == 1:
                        return tuple(path[positions[neighbor_id] :] + [neighbor_id])
                    if state == 0:
                        visited[neighbor_id] = 1
                        positions[neighbor_id] = len(path)
                        path.append(neighbor_id)
                        stack.append(
                            (neighbor_id, iter(sorted(self._downstream.get(neighbor_id, set()) & candidates)))
                        )
                        descended = True
                        break
                if not descended:
                    visited[node_id] = 2
                    stack.pop()
                    path.pop()
                    positions.pop(node_id, None)
        return ()


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete sequential wave scheduler tracking node lifecycle states."""

    tier = "system"

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._synchronize()
        ready: List[str] = []
        for node_id in dag.all_nodes():
            state = self._states[node_id]
            if state in _TERMINAL_STATES or state == dag_engine_lite.NodeState.RUNNING:
                continue
            dependencies = dag.get_dependencies(node_id)
            if not all(self._states.get(dependency_id) == dag_engine_lite.NodeState.SUCCEEDED for dependency_id in dependencies):
                continue
            # Nodes whose prerequisites just completed are promoted as the wave is assembled.
            self._states[node_id] = dag_engine_lite.NodeState.READY
            ready.append(node_id)
        # Priority descending, then node identifier ascending.
        ready.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        return ready

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        dag = self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Callers only complete nodes that remain registered in the graph.
        if not dag.has_node(node_id):
            with unreachable:
                return
        # Unlock dependents whose prerequisites have now all succeeded.
        for dependent_id in dag.get_dependents(node_id):
            if self._states.get(dependent_id) != dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = dag.get_dependencies(dependent_id)
            if all(self._states.get(dependency_id) == dag_engine_lite.NodeState.SUCCEEDED for dependency_id in dependencies):
                self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy) -> None:
        dag = self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        blocked_dependents = self._transitive_dependents(dag, node_id)
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Every node that has not yet started is cancelled.
            for candidate_id, state in list(self._states.items()):
                if state in (dag_engine_lite.NodeState.PENDING, dag_engine_lite.NodeState.READY):
                    self._states[candidate_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # Dependent nodes can no longer run once an upstream prerequisite failed.
        for dependent_id in blocked_dependents:
            state = self._states.get(dependent_id)
            if state is not None and state not in _TERMINAL_STATES:
                self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        dag = self._synchronize()
        node_ids = dag.all_nodes()
        if not node_ids:
            return True
        # A non-terminal node keeps the run alive only while every prerequisite succeeded;
        # nodes whose prerequisites failed, were skipped, or are missing stay blocked.
        for node_id in node_ids:
            state = self._states[node_id]
            if state in _TERMINAL_STATES:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(self._states.get(dependency_id) == dag_engine_lite.NodeState.SUCCEEDED for dependency_id in dependencies):
                return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        dag = self._synchronize()
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        state = self._states.get(node_id)
        # Synchronization installs a state entry for every registered node.
        if state is None:
            with unreachable:
                state = dag_engine_lite.NodeState.PENDING
                self._states[node_id] = state
        return state

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._synchronize()
        node_ids = dag.all_nodes()
        return {node_id: state for node_id, state in self._states.items() if node_id in node_ids}

    def _synchronize(self) -> dag_engine_lite.DAG:
        dag = get_singleton(dag_engine_lite.DAG)
        node_ids = dag.all_nodes()
        for node_id in node_ids:
            if node_id in self._states:
                continue
            # Roots start ready; every other node waits for its prerequisites.
            if dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine_lite.NodeState.READY
        # States for nodes that left the graph are purged.
        for node_id in list(self._states.keys()):
            if node_id not in node_ids:
                del self._states[node_id]
        return dag

    def _transitive_dependents(self, dag: dag_engine_lite.DAG, node_id: str) -> Set[str]:
        collected: Set[str] = set()
        pending: List[str] = [node_id]
        while pending:
            current_id = pending.pop()
            # Traversal remains inside the registered graph.
            if not dag.has_node(current_id):
                with unreachable:
                    continue
            for dependent_id in dag.get_dependents(current_id):
                if dependent_id in collected:
                    continue
                collected.add(dependent_id)
                pending.append(dependent_id)
        return collected


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete sequential runner driving the DAG through ready waves."""

    tier = "system"

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(self, failure_policy: dag_engine_lite.FailurePolicy) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        # Graph invariants are verified before any wave executes.
        dag.validate()
        started = time.monotonic()
        self._results = {}
        halted = False
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            # An unfinished run always exposes at least one ready node.
            if not wave:
                with unreachable:
                    break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                node_started = time.monotonic()
                attempts = 0
                value: Any = None
                failure: Optional[Exception] = None
                succeeded = False
                while True:
                    try:
                        value = definition.action()
                    except Exception as exc:  # reified into the node outcome record below
                        failure = exc
                        if attempts >= definition.retries:
                            break
                        attempts += 1
                    else:
                        succeeded = True
                        break
                duration = time.monotonic() - node_started
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_succeeded(node_id)
                    continue
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=dag_engine_lite.NodeState.FAILED,
                    error=failure,
                    duration_seconds=duration,
                    retries_attempted=attempts,
                )
                scheduler.mark_failed(node_id, failure_policy)
                if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                    halted = True
                    break
            if halted:
                break
        node_ids = dag.all_nodes()
        states = scheduler.get_all_states()
        # Nodes terminated without executing still receive outcome records.
        for node_id in node_ids:
            if node_id in self._results:
                continue
            state = states.get(node_id)
            # Every unexecuted node has already reached a terminal state.
            if state is None or state not in _TERMINAL_STATES:
                with unreachable:
                    state = dag_engine_lite.NodeState.SKIPPED
            self._results[node_id] = dag_engine_lite.NodeResult(node_id=node_id, state=state)
        # The graph is not mutated while a run executes, so every row is current.
        for node_id in list(self._results.keys()):
            if node_id not in node_ids:
                with unreachable:
                    del self._results[node_id]
        critical_path, _ = dag.compute_critical_path(None)
        elapsed = time.monotonic() - started
        succeeded_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state == dag_engine_lite.NodeState.SUCCEEDED)
        )
        failed_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state == dag_engine_lite.NodeState.FAILED)
        )
        skipped_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state == dag_engine_lite.NodeState.SKIPPED)
        )
        cancelled_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state == dag_engine_lite.NodeState.CANCELLED)
        )
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(node_ids),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T18:43:37Z
# LAST_CHANGED: 2026-11-14T18:42:48Z
# CHANGE: Separate state promotion from observation: _synchronize now only initializes roots READY and non-roots PENDING (plus purges departed nodes) so observers no longer promote PENDING nodes; next_wave performs the promotion of newly unblocked nodes as it assembles the wave (fixing the missing late-registered ready node); mark_failed no longer promotes pending nodes (policy merely retains unblocked states); is_finished is now eligibility-based, treating non-terminal nodes whose prerequisites did not all succeed as blocked so a READY node behind a FAILED dependency completes the run.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T18:43:37Z
# PRETENSE_QA_AUDIT: 2026-11-14T18:43:11Z
# --- END AUTOFAB METADATA ---
