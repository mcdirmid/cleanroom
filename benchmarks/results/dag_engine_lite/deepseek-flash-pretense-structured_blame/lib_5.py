# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_005423_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-15T00:54:23.560869+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 315,649
#   Cached Inbound Tokens:   29,045,248
#   Outbound Tokens:         353,996
#   Total Tokens:            29,714,893
#   Financial Cost ($USD):   $0.3469
#   Wall Clock Duration:     2391.35s
#   Step Latencies (s):      [280.6, 848.7, 20.3, 186.1, 227.4, 20.4, 300.8, 43.0, 268.6, 114.7, 112.6, 32.7, 20.4, 124.8, 112.8, 20.3, 20.3]
#   Role Execution Rounds:   lib: 2, pretense: 6, pretense_coverage: 4, pretense_qa: 5 (Total: 17)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       7
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface library for the synchronous DAG execution and wave scheduling engine."""

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
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T00:58:55Z
# LAST_CHANGED: 2026-11-15T00:58:55Z
# CHANGE: Implement interface library: DAGError hierarchy, NodeState/FailurePolicy enums, NodeDefinition/NodeResult/DAGRunReport frozen data types, and DAG/WaveScheduler/DAGRunner singleton protocols with contracted signatures
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the directed acyclic graph."""

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
        # Reject identifiers that are already registered in the graph.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies) if dependencies is not None else frozenset(),
            priority=priority,
            retries=retries,
        )
        # Register the definition and its empty neighbor sets.
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # Record directed dependency edges without validating existence eagerly.
        for dependency in definition.dependencies:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Both endpoints must already be registered in the graph.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{upstream_id}' is not registered in the DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{downstream_id}' is not registered in the DAG",
                node_id=downstream_id,
            )
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # The referenced node must be registered before it can be removed.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        # Purge every incident edge from the neighboring adjacency sets.
        for upstream_id in list(self._upstream.get(node_id, set())):
            if upstream_id in self._downstream:
                self._downstream[upstream_id].discard(node_id)
        for downstream_id in list(self._downstream.get(node_id, set())):
            if downstream_id in self._upstream:
                self._upstream[downstream_id].discard(node_id)
        self._nodes.pop(node_id, None)
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
        # Every declared dependency must reference a registered node.
        for node_id in self._nodes:
            for dependency in self._nodes[node_id].dependencies:
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Node '{node_id}' depends on unregistered node '{dependency}'",
                        node_id=dependency,
                    )
        # A directed cycle anywhere in the graph violates acyclicity.
        cycle = self._find_cycle(set(self._nodes))
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        node_ids = set(self._nodes)
        # In-degree counts only previously registered prerequisites.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()) & node_ids) for node_id in node_ids
        }
        heap: List[Tuple[int, str]] = []
        for node_id in node_ids:
            if in_degree[node_id] == 0:
                heapq.heappush(heap, (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while heap:
            _, node_id = heapq.heappop(heap)
            order.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                # Dangling identifiers never participate in the ordering sweep.
                if dependent_id not in in_degree:
                    with unreachable:
                        continue
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    heapq.heappush(heap, (-self._nodes[dependent_id].priority, dependent_id))
        # Unordered nodes remain because they participate in a directed cycle.
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
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id, set())}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id, set())}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        if not self._nodes:
            return [], 0.0
        order = self.topological_sort()
        registered = set(self._nodes)
        earliest: Dict[str, float] = {}
        parent: Dict[str, Optional[str]] = {}
        # Accumulate earliest completion times along the topological order.
        for node_id in order:
            duration = 1.0 if estimated_durations is None else estimated_durations.get(node_id, 1.0)
            predecessors = self._upstream.get(node_id, set()) & registered
            if not predecessors:
                earliest[node_id] = duration
                parent[node_id] = None
                continue
            best = max(predecessors, key=lambda predecessor: (earliest.get(predecessor, 0.0), predecessor))
            earliest[node_id] = earliest.get(best, 0.0) + duration
            parent[node_id] = best
        # The terminal node with the greatest completion time ends the critical path.
        terminal = max(order, key=lambda node_id: (earliest[node_id], node_id))
        total = earliest[terminal]
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = parent.get(current)
        path.reverse()
        return path, total

    def _find_cycle(self, candidates: Set[str]) -> Optional[Tuple[str, ...]]:
        state: Dict[str, int] = {node_id: 0 for node_id in candidates}
        path: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            state[node_id] = 1
            path.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                # Only candidates already inside the cycle search are traversed.
                if dependent_id not in state:
                    with unreachable:
                        continue
                if state[dependent_id] == 1:
                    index = path.index(dependent_id)
                    return tuple(path[index:] + [dependent_id])
                if state[dependent_id] == 0:
                    found = visit(dependent_id)
                    if found is not None:
                        return found
            path.pop()
            state[node_id] = 2
            return None

        for node_id in sorted(candidates):
            if state[node_id] == 0:
                found = visit(node_id)
                if found is not None:
                    return found
        return None


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of the sequential wave scheduler."""

    tier = "system"

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._dag()
        self._synchronize()
        ready: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            if self._dependencies_satisfied(node_id):
                ready.append(node_id)
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
        dag = self._dag()
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # A completed node is always registered in the scheduled graph.
        if not dag.has_node(node_id):
            with unreachable:
                return
        # Promote dependents whose prerequisites have now all succeeded.
        for dependent_id in dag.get_dependents(node_id):
            if self._states.get(dependent_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            if self._dependencies_satisfied(dependent_id):
                self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Cancel every node that has not yet reached a terminal state.
            for candidate_id, state in list(self._states.items()):
                if state not in terminal:
                    self._states[candidate_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # Skip transitive dependents that can no longer execute after the failure.
        for dependent_id in self._transitive_dependents(node_id):
            if self._states.get(dependent_id) not in terminal:
                self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        self._synchronize()
        if not self._states:
            return True
        terminal = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        # Every node reaching a terminal state finishes the schedule.
        if all(state in terminal for state in self._states.values()):
            return True
        # A node in flight keeps the schedule open.
        if any(state is dag_engine_lite.NodeState.RUNNING for state in self._states.values()):
            return False
        # Any executable node blocked only by unfinished prerequisites keeps it open.
        for node_id, state in self._states.items():
            if state in terminal:
                continue
            if not self._blocked(node_id):
                return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        dag = self._dag()
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        self._synchronize()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._synchronize()
        return dict(self._states)

    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _synchronize(self) -> None:
        dag = self._dag()
        registered = dag.all_nodes()
        # Discover newly registered nodes: roots and already unblocked nodes are READY.
        for node_id in registered:
            if node_id in self._states:
                continue
            if self._dependencies_satisfied(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.READY
            else:
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
        # Purge tracking state for nodes removed from the graph.
        for node_id in list(self._states):
            if node_id not in registered:
                del self._states[node_id]

    def _dependencies_satisfied(self, node_id: str) -> bool:
        for dependency in self._dag().get_dependencies(node_id):
            if self._states.get(dependency) is not dag_engine_lite.NodeState.SUCCEEDED:
                return False
        return True

    def _blocked(self, node_id: str) -> bool:
        dag = self._dag()
        blocking = {
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        pending: List[str] = []
        if dag.has_node(node_id):
            pending.extend(dag.get_dependencies(node_id))
        visited: Set[str] = set()
        while pending:
            dependency = pending.pop()
            if dependency in visited:
                continue
            visited.add(dependency)
            if self._states.get(dependency) in blocking:
                return True
            if dag.has_node(dependency):
                pending.extend(dag.get_dependencies(dependency))
        return False

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        dag = self._dag()
        discovered: Set[str] = set()
        pending: List[str] = []
        if dag.has_node(node_id):
            pending.extend(dag.get_dependents(node_id))
        while pending:
            dependent_id = pending.pop()
            if dependent_id in discovered:
                continue
            discovered.add(dependent_id)
            if dag.has_node(dependent_id):
                pending.extend(dag.get_dependents(dependent_id))
        return discovered


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of the sequential DAG execution runner."""

    tier = "system"

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        # Graph invariants must hold before any wave is scheduled.
        dag.validate()
        started_at = time.perf_counter()
        self._results = {}
        halted = False
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                # A halted run never re-enters the dispatch loop for another wave.
                if halted:
                    with unreachable:
                        break
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                node_started_at = time.perf_counter()
                retries_attempted = 0
                value: Any = None
                failure: Optional[Exception] = None
                # Execute the action, retrying up to the configured allowance.
                while True:
                    try:
                        value = definition.action()
                    except Exception as exc:
                        failure = exc
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        break
                    else:
                        failure = None
                        break
                duration = time.perf_counter() - node_started_at
                if failure is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                    continue
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=dag_engine_lite.NodeState.FAILED,
                    value=None,
                    error=failure,
                    duration_seconds=duration,
                    retries_attempted=retries_attempted,
                )
                scheduler.mark_failed(node_id, failure_policy)
                if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                    halted = True
                    break
        # Record outcomes for nodes that never executed, preserving their states.
        for node_id in sorted(dag.all_nodes()):
            if node_id in self._results:
                continue
            self._results[node_id] = dag_engine_lite.NodeResult(
                node_id=node_id,
                state=scheduler.get_state(node_id),
                value=None,
                error=None,
                duration_seconds=0.0,
                retries_attempted=0,
            )
        critical_path, _ = dag.compute_critical_path(None)
        succeeded_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.SUCCEEDED)
        )
        failed_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.FAILED)
        )
        skipped_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.SKIPPED)
        )
        cancelled_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.CANCELLED)
        )
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=time.perf_counter() - started_at,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T01:34:07Z
# LAST_CHANGED: 2026-11-15T01:21:34Z
# CHANGE: Quarantine four coverage-flagged unreachable guards with 'with unreachable:' tripwires instead of deleting logic: unregistered dependent guard in topological-sort traversal, candidate-closure guard in cycle traversal, untracked-node guard in mark_succeeded promotion, and halted reentry guard in runner wave dispatch
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T01:34:07Z
# PRETENSE_QA_AUDIT: 2026-11-15T01:33:41Z
# --- END AUTOFAB METADATA ---
