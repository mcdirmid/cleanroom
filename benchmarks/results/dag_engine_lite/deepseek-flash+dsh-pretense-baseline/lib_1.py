# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_182637_deepseek-flash_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-26T18:26:37.668453+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 98,566
#   Cached Inbound Tokens:   8,452,864
#   Outbound Tokens:         101,299
#   Total Tokens:            8,652,729
#   Financial Cost ($USD):   $0.1605
#   Wall Clock Duration:     542.18s
#   Step Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       35
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Low-level interface for the synchronous DAG execution and wave scheduling engine.

This module mirrors the contracts declared in ``low/dag_engine_lite.pyi``. It
provides the immutable value types, lifecycle states, failure policies, and the
``DAG``, ``WaveScheduler``, and ``DAGRunner`` protocol families that concrete
implementations realize.
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


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine.

Realizes the protocols declared in :mod:`dag_engine_lite` with adjacency-map
graph storage, depth-first cycle detection, deterministic Kahn topological
sorting, dynamic-programming critical path analysis, wave-based scheduler state
transitions, and a sequential retry-aware execution runner.
"""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dag_engine_lite

_TERMINAL_STATES = (
    dag_engine_lite.NodeState.SUCCEEDED,
    dag_engine_lite.NodeState.FAILED,
    dag_engine_lite.NodeState.SKIPPED,
    dag_engine_lite.NodeState.CANCELLED,
)


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node
      identifiers to definitions and sets.
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
        dependency_set = frozenset(dependencies) if dependencies is not None else frozenset()
        # Contract: reject unregistered dependencies with NodeNotFoundError before mutating.
        for dependency in sorted(dependency_set):
            if dependency not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    f"Node '{node_id}' references missing dependency '{dependency}'",
                    dependency,
                )

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
        for dependency in dependency_set:
            self.add_edge(dependency, node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Cannot add edge: upstream node '{upstream_id}' is not registered",
                upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Cannot add edge: downstream node '{downstream_id}' is not registered",
                downstream_id,
            )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Cannot remove node: '{node_id}' is not registered",
                node_id,
            )
        for upstream_id in self._upstream[node_id]:
            self._downstream[upstream_id].discard(node_id)
        for downstream_id in self._downstream[node_id]:
            self._upstream[downstream_id].discard(node_id)
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered", node_id
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered", node_id
            )
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered", node_id
            )
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Depth-first search returning the first directed cycle discovered."""
        visited: Set[str] = set()
        path: List[str] = []
        path_set: Set[str] = set()

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            if node_id in path_set:
                index = path.index(node_id)
                return tuple(path[index:] + [node_id])
            if node_id in visited:
                return None
            visited.add(node_id)
            path.append(node_id)
            path_set.add(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                cycle = visit(dependent_id)
                if cycle is not None:
                    return cycle
            path.pop()
            path_set.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                cycle = visit(node_id)
                if cycle is not None:
                    return cycle
        return None

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        for node_id in sorted(self._nodes):
            definition = self._nodes[node_id]
            for dependency in sorted(definition.dependencies):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' references missing dependency '{dependency}'",
                        dependency,
                    )
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                f"Cycle detected: {' -> '.join(cycle)}", cycle
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream[node_id]) for node_id in self._nodes
        }
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
            for dependent_id in self._downstream[node_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    heapq.heappush(
                        ready,
                        (-self._nodes[dependent_id].priority, dependent_id),
                    )
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            sequence = cycle if cycle is not None else tuple(sorted(self._nodes))
            raise dag_engine_lite.CycleError(
                f"Cycle detected: {' -> '.join(sequence)}", sequence
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            node_id for node_id in self._nodes if not self._upstream[node_id]
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {
            node_id for node_id in self._nodes if not self._downstream[node_id]
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

        earliest: Dict[str, float] = {}
        for node_id in order:
            duration = (
                estimated_durations.get(node_id, 1.0)
                if estimated_durations is not None
                else 1.0
            )
            upstream_weight = max(
                (earliest[upstream_id] for upstream_id in self._upstream[node_id]),
                default=0.0,
            )
            earliest[node_id] = upstream_weight + duration

        terminal_id = max(order, key=lambda candidate: earliest[candidate])
        path: List[str] = []
        current: Optional[str] = terminal_id
        while current is not None:
            path.append(current)
            upstream_ids = self._upstream[current]
            if upstream_ids:
                current = max(
                    sorted(upstream_ids),
                    key=lambda candidate: earliest[candidate],
                )
            else:
                current = None
        path.reverse()
        return (path, earliest[terminal_id])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers
      to dag_engine_lite.NodeState.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _synchronize(self) -> None:
        """Discovers registered nodes and initializes missing scheduling state."""
        registered = self._dag.all_nodes()
        for stale_id in [node_id for node_id in self._states if node_id not in registered]:
            del self._states[stale_id]
        for node_id in registered:
            if node_id not in self._states:
                if self._dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._synchronize()
        candidates = [
            node_id
            for node_id, node_state in self._states.items()
            if node_state is dag_engine_lite.NodeState.READY
            and all(
                self._states.get(dependency)
                is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in self._dag.get_dependencies(node_id)
            )
        ]
        candidates.sort(
            key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id)
        )
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dependent_id in self._dag.get_dependents(node_id):
            if self._states.get(dependent_id) is dag_engine_lite.NodeState.PENDING and all(
                self._states.get(dependency)
                is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in self._dag.get_dependencies(dependent_id)
            ):
                self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            for tracked_id, tracked_state in self._states.items():
                if tracked_state not in _TERMINAL_STATES:
                    self._states[tracked_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            pending = list(self._dag.get_dependents(node_id))
            visited: Set[str] = set()
            while pending:
                dependent_id = pending.pop()
                if dependent_id in visited:
                    continue
                visited.add(dependent_id)
                if self._states.get(dependent_id) not in _TERMINAL_STATES:
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
                pending.extend(self._dag.get_dependents(dependent_id))

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._synchronize()
        return all(
            self._states.get(node_id) in _TERMINAL_STATES
            for node_id in self._dag.all_nodes()
        )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        self._synchronize()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._synchronize()
        return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler
      service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(
            dag_engine_lite.WaveScheduler
        )
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        self._dag.validate()
        started_at = time.perf_counter()
        self._results = {}
        failed_in_run = False

        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_started_at = time.perf_counter()
                value: Any = None
                error: Optional[Exception] = None
                attempts = 0
                while True:
                    try:
                        value = definition.action()
                        error = None
                        break
                    except Exception as exc:  # noqa: BLE001 - captured into NodeResult
                        error = exc
                        if attempts < definition.retries:
                            attempts += 1
                            continue
                        break
                duration = time.perf_counter() - node_started_at
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    failed_in_run = True
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break
            if failed_in_run and failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        states = self._scheduler.get_all_states()
        for node_id, node_state in states.items():
            if (
                node_state
                in (
                    dag_engine_lite.NodeState.SKIPPED,
                    dag_engine_lite.NodeState.CANCELLED,
                )
                and node_id not in self._results
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id, state=node_state
                )

        critical_path, _critical_weight = self._dag.compute_critical_path()
        succeeded_nodes = tuple(
            sorted(
                {nid for nid, res in self._results.items() if res.state is dag_engine_lite.NodeState.SUCCEEDED}
                | {nid for nid, state in states.items() if state is dag_engine_lite.NodeState.SUCCEEDED}
            )
        )
        failed_nodes = tuple(
            sorted(
                {nid for nid, res in self._results.items() if res.state is dag_engine_lite.NodeState.FAILED}
                | {nid for nid, state in states.items() if state is dag_engine_lite.NodeState.FAILED}
            )
        )
        skipped_nodes = tuple(
            sorted(
                nid for nid, state in states.items() if state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                nid for nid, state in states.items() if state is dag_engine_lite.NodeState.CANCELLED
            )
        )
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=time.perf_counter() - started_at,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine_lite.DAG],
        tier=system,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine_lite.WaveScheduler],
        tier=system,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine_lite.DAGRunner],
        tier=system,
    )


_initialize_ = __initialize__
