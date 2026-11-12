# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_000913_deepseek-flash_dag_engine_lite_combined
# Timestamp: 2026-11-12T00:09:13.062530+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 683,912
#   Cached Inbound Tokens:   19,953,152
#   Outbound Tokens:         499,043
#   Total Tokens:            21,136,107
#   Financial Cost ($USD):   $0.4619
#   Wall Clock Duration:     2075.16s
#   Step Latencies (s):      [335.2, 484.3, 10.1, 507.8, 10.1, 273.2, 315.0, 87.4, 113.2, 10.1, 82.2, 267.5, 10.1, 117.9, 20.3, 120.5, 22.9, 156.3, 74.2, 102.8, 12.5, 10.1, 43.5, 108.1, 74.4, 20.4, 10.0, 110.0, 10.1, 74.3, 64.0, 10.1, 71.7, 115.3, 10.1, 20.3]
#   Role Execution Rounds:   coverage: 5, lib: 3, pretense: 6, pretense_coverage: 6, pretense_qa: 7, qa: 5, test: 4 (Total: 36)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       48
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Library interface for the synchronous DAG execution and wave scheduling engine."""

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
    """Precondition contract violation error raised when a dependency cycle is detected within the DAG.

    Designates an untestable checked precondition violation when caller constructs or validates a cyclic graph.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Precondition contract violation error raised when a referenced node identifier does not exist in the DAG.

    Designates an untestable checked precondition violation when caller references an unregistered node.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Precondition contract violation error raised when attempting to add a node identifier that already exists in the DAG.

    Designates an untestable checked precondition violation when caller attempts to add a duplicate node.

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

        PRECONDITIONS:
        - MUST ensure node_id is not already registered in the graph (checked precondition; raises DuplicateNodeError on caller violation).

        POSTCONDITIONS:
        - MUST register the node definition into the graph.
        - WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        - MUST defer missing dependency existence checks to validate() and topological_sort() without eagerly raising NodeNotFoundError.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        PRECONDITIONS:
        - MUST ensure upstream_id and downstream_id exist in the graph (checked precondition; raises NodeNotFoundError on caller violation).

        POSTCONDITIONS:
        - MUST establish a directed dependency edge from upstream_id to downstream_id.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        PRECONDITIONS:
        - MUST ensure node_id exists in the graph (checked precondition; raises NodeNotFoundError on caller violation).

        POSTCONDITIONS:
        - MUST remove the node and its incident edges.
        - MUST purge the node identifier from wave scheduler state tracking.
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

        PRECONDITIONS:
        - MUST ensure node_id exists in the graph (checked precondition; raises NodeNotFoundError on caller violation).

        POSTCONDITIONS:
        - MUST return the NodeDefinition matching node_id.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.

        PRECONDITIONS:
        - MUST ensure node_id exists in the graph (checked precondition; raises NodeNotFoundError on caller violation).

        POSTCONDITIONS:
        - MUST return all direct upstream dependencies.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.

        PRECONDITIONS:
        - MUST ensure node_id exists in the graph (checked precondition; raises NodeNotFoundError on caller violation).

        POSTCONDITIONS:
        - MUST return all direct downstream dependents.
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

        PRECONDITIONS:
        - MUST ensure all referenced dependencies across registered nodes exist in the graph (checked precondition; raises NodeNotFoundError on caller violation).
        - MUST ensure the graph contains no directed cycles (checked precondition; raises CycleError on caller violation).

        POSTCONDITIONS:
        - WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.

        PRECONDITIONS:
        - MUST ensure the graph contains no directed cycles (checked precondition; raises CycleError on caller violation).

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and lexicographical node_id ascending.
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
        failure_policy: FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        Args:
            node_id: Identifier of the failed node.
            failure_policy: Failure policy applied upon failure.

        POSTCONDITIONS:
        - MUST update the node state to FAILED.
        - WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        - WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution and transition blocked dependents of failed nodes to SKIPPED.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.

        POSTCONDITIONS:
        - WHEN all nodes in the DAG have reached terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED), MUST return True.
        - WHEN no ready nodes remain and unexecuted nodes are blocked by failed dependencies, MUST return True.
        - WHEN any node in the DAG remains non-terminal and eligible to execute, MUST return False.
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

        PRECONDITIONS:
        - MUST ensure node_id is registered in the scheduled DAG (checked precondition; raises NodeNotFoundError on caller violation).
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

        PRECONDITIONS:
        - MUST ensure all referenced dependencies across registered nodes exist in the graph (checked precondition; raises NodeNotFoundError on caller violation).
        - MUST ensure the graph contains no directed cycles (checked precondition; raises CycleError on caller violation).

        POSTCONDITIONS:
        - MUST validate graph invariants before commencing wave execution.
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T00:17:08Z
# LAST_CHANGED: 2026-11-12T00:17:08Z
# CHANGE: Author interface module: frozen dataclass domain records (NodeDefinition, NodeResult, DAGRunReport), contract errors (DAGError hierarchy with __str__), NodeState/FailurePolicy enums, and DAG/WaveScheduler/DAGRunner protocols inheriting Singleton[SystemTier] with operation stubs.
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

_TERMINAL_STATES = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

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
        # Contract: duplicate node identifiers are rejected before registration.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                f"Node '{node_id}' is already registered in the DAG", node_id
            )
        dependency_set = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        # Contract: the immutable definition is registered for the node identifier.
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # Contract: each declared dependency becomes a directed edge. Unknown
        # dependencies are recorded without raising; validate() reports them later.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Contract: both endpoints must already be registered.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{upstream_id}' is not registered in the DAG", upstream_id
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{downstream_id}' is not registered in the DAG", downstream_id
            )
        # Contract: the directed edge is recorded in both adjacency directions.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # Contract: the removed node identifier must be registered.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG", node_id
            )
        # Contract: incident edges are purged from both adjacency directions.
        for upstream_id in self._upstream.get(node_id, set()):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self._downstream.get(node_id, set()):
            self._upstream.get(downstream_id, set()).discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)
        # Contract: scheduler state tracking is purged because WaveScheduler
        # resynchronizes against all_nodes() on every operation.

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # Contract: a missing node identifier is rejected.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG", node_id
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # Contract: a missing node identifier is rejected.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG", node_id
            )
        # Contract: return a defensive copy of the direct upstream identifiers.
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # Contract: a missing node identifier is rejected.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG", node_id
            )
        # Contract: return a defensive copy of the direct downstream identifiers.
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        # Contract: return a defensive copy of all registered identifiers.
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Contract: every dependency referenced by a registered node must itself be
        # registered, otherwise NodeNotFoundError is raised.
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._upstream[node_id]):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{dependency}' referenced by '{node_id}' is not registered in the DAG",
                        dependency,
                    )
        # Contract: the graph must be acyclic, otherwise CycleError is raised.
        order = self._topological_order()
        if len(order) != len(self._nodes):
            cycle = self._cycle_sequence()
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}", cycle
            )
        # Contract: a complete valid graph validates without error.

    @operation
    @override
    def topological_sort(self) -> List[str]:
        order = self._topological_order()
        # Contract: cyclic graphs are rejected.
        if len(order) != len(self._nodes):
            cycle = self._cycle_sequence()
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}", cycle
            )
        # Contract: Kahn ordering with priority-descending / node_id-ascending
        # tie-breaking delivered by the ready heap.
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id for node_id in self._nodes if not self._upstream[node_id]
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id for node_id in self._nodes if not self._downstream[node_id]
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # Contract: dynamic programming over the topological order derives the
        # longest weighted dependency path.
        durations = estimated_durations if estimated_durations is not None else {}
        order = self.topological_sort()
        earliest: Dict[str, float] = {}
        for node_id in order:
            predecessor_weight = 0.0
            for dependency in self._upstream[node_id]:
                if dependency in earliest and earliest[dependency] > predecessor_weight:
                    predecessor_weight = earliest[dependency]
            earliest[node_id] = predecessor_weight + durations.get(node_id, 1.0)
        if not earliest:
            return [], 0.0
        terminals = [node_id for node_id in order if not self._downstream[node_id]]
        # Contract: a non-empty acyclic order always retains at least one sink.
        if not terminals:
            with unreachable:
                terminals = list(order)
        terminal = min(terminals, key=lambda node_id: (-earliest[node_id], node_id))
        path: List[str] = [terminal]
        current = terminal
        # Contract: backtrack through the predecessor maximizing earliest completion.
        while True:
            candidates = [
                dependency
                for dependency in self._upstream[current]
                if dependency in earliest
            ]
            if not candidates:
                break
            predecessor = min(
                candidates, key=lambda node_id: (-earliest[node_id], node_id)
            )
            path.append(predecessor)
            current = predecessor
        path.reverse()
        # Contract: return the path and its cumulative duration weight.
        return path, earliest[terminal]

    def _topological_order(self) -> List[str]:
        """Kahn sweep ordering by priority descending then node_id ascending."""
        in_degree: Dict[str, int] = {}
        for node_id in self._nodes:
            in_degree[node_id] = sum(
                1 for dependency in self._upstream[node_id] if dependency in self._nodes
            )
        ready: List[Tuple[int, str]] = []
        for node_id, degree in in_degree.items():
            if degree == 0:
                heapq.heappush(ready, (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while ready:
            _, node_id = heapq.heappop(ready)
            order.append(node_id)
            for dependent in sorted(self._downstream[node_id]):
                # Contract: every recorded dependent is a registered node.
                if dependent not in in_degree:
                    with unreachable:
                        continue
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(
                        ready, (-self._nodes[dependent].priority, dependent)
                    )
        return order

    def _cycle_sequence(self) -> Tuple[str, ...]:
        """Extracts one deterministic directed cycle from nodes left unorderable."""
        ordered = set(self._topological_order())
        remaining = [
            node_id for node_id in sorted(self._nodes) if node_id not in ordered
        ]
        # Contract: an unorderable residue exists whenever a cycle is present.
        if not remaining:
            with unreachable:
                return ()
        remaining_set = set(remaining)
        walk: List[str] = []
        position: Dict[str, int] = {}
        current = remaining[0]
        # Every leftover node still has a leftover predecessor, so walking upstream
        # must eventually revisit a node and thereby reveal the cycle.
        while current not in position:
            position[current] = len(walk)
            walk.append(current)
            candidates = sorted(
                dependency
                for dependency in self._upstream[current]
                if dependency in remaining_set
            )
            # Contract: each residual node retains a residual predecessor.
            if not candidates:
                with unreachable:
                    return ()
            current = candidates[0]
        # The upstream walk is the reverse of the dependency direction; reverse the
        # cycle segment and rotate it to the smallest identifier for determinism.
        cycle = list(reversed(walk[position[current]:]))
        start_index = cycle.index(min(cycle))
        cycle = cycle[start_index:] + cycle[:start_index]
        return tuple(cycle)


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of the sequential wave scheduler."""

    tier = "system"

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}
        self._dag: Optional[dag_engine_lite.DAG] = None

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._sync_states()
        # Contract: return all READY nodes whose upstream dependencies succeeded.
        candidates: List[str] = []
        for node_id, state in self._states.items():
            if state != dag_engine_lite.NodeState.READY:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency) == dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                candidates.append(node_id)
        # Contract: order by priority descending then node_id ascending.
        candidates.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        # Contract: no ready candidates yields an empty list.
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        # Contract: the node transitions to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        dag = self._sync_states()
        # Contract: the node transitions to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Contract: downstream dependents unblocked by this success become READY.
        for dependent in sorted(dag.get_dependents(node_id)):
            if self._states.get(dependent) != dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = dag.get_dependencies(dependent)
            if all(
                self._states.get(dependency) == dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        dag = self._sync_states()
        # Contract: the node transitions to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Contract: every remaining non-terminal node is cancelled.
            for other_id in list(self._states):
                if self._states[other_id] not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # Contract: for SKIP_DOWNSTREAM and CONTINUE_ON_ERROR, transitive downstream
        # dependents blocked by the failure become SKIPPED while independent nodes
        # retain their non-terminal states and remain eligible for execution.
        for dependent in sorted(self._blocked_dependents(dag, node_id)):
            # Contract: an acyclic graph never contains a self-dependent node.
            if dependent == node_id:
                with unreachable:
                    continue
            if self._states.get(dependent) not in _TERMINAL_STATES:
                self._states[dependent] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        dag = self._sync_states()
        nodes = dag.all_nodes()
        # Contract: an empty DAG is finished.
        if not nodes:
            return True
        for node_id in sorted(nodes):
            state = self._states[node_id]
            if state in _TERMINAL_STATES:
                continue
            # Contract: eligibly executable work remaining means not finished.
            if state in (
                dag_engine_lite.NodeState.READY,
                dag_engine_lite.NodeState.RUNNING,
            ):
                return False
            if state == dag_engine_lite.NodeState.PENDING:
                dependencies = dag.get_dependencies(node_id)
                # Contract: a pending node whose upstream dependencies all succeeded
                # represents executable work that has not yet been dispatched.
                if all(
                    self._states.get(dependency)
                    == dag_engine_lite.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    return False
        # Contract: all nodes terminal or blocked by failed dependencies is finished.
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        dag = self._sync_states()
        # Contract: an unregistered node identifier is rejected.
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG", node_id
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._sync_states()
        nodes = dag.all_nodes()
        # Contract: shallow copy filtered to nodes currently present in the DAG.
        return {
            node_id: state
            for node_id, state in self._states.items()
            if node_id in nodes
        }

    def _dag_service(self) -> dag_engine_lite.DAG:
        """Resolves the active DAG collaborator on demand."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._dag = dag
        return dag

    def _sync_states(self) -> dag_engine_lite.DAG:
        """Synchronizes scheduled states with the nodes currently registered in the DAG."""
        dag = self._dag_service()
        nodes = dag.all_nodes()
        roots = dag.find_roots()
        for known_id in list(self._states):
            if known_id not in nodes:
                del self._states[known_id]
        # Discover newly registered nodes: roots start READY, every dependency-bearing
        # node starts PENDING regardless of the current states of its dependencies.
        for node_id in sorted(nodes):
            if node_id not in self._states:
                self._states[node_id] = (
                    dag_engine_lite.NodeState.READY
                    if node_id in roots
                    else dag_engine_lite.NodeState.PENDING
                )
        # Promotion of pending nodes is driven exclusively by upstream completion in
        # mark_succeeded; synchronization only discovers and initializes nodes.
        return dag

    def _blocked_dependents(
        self, dag: dag_engine_lite.DAG, node_id: str
    ) -> Set[str]:
        """Collects all transitive downstream dependents of a failed node."""
        collected: Set[str] = set()
        frontier: List[str] = sorted(dag.get_dependents(node_id))
        while frontier:
            current = frontier.pop()
            if current in collected:
                continue
            collected.add(current)
            for dependent in sorted(dag.get_dependents(current)):
                if dependent not in collected:
                    frontier.append(dependent)
        return collected


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of the sequential DAG execution runner."""

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
        # Contract: graph invariants are validated before any wave runs, so missing
        # dependencies or cycles raise before execution begins.
        dag.validate()
        self._results = {}
        start_time = time.perf_counter()
        should_stop = False
        # Contract: ready waves execute sequentially until completion or failure.
        while not should_stop and not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                retries_attempted = 0
                value: Any = None
                error: Optional[Exception] = None
                succeeded = False
                node_start = time.perf_counter()
                while True:
                    try:
                        value = definition.action()
                        succeeded = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        error = exc
                        # Contract: failed actions retry up to the configured count.
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        break
                duration_seconds = time.perf_counter() - node_start
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    # Contract: the configured failure policy is applied immediately.
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        should_stop = True
                        break
            if should_stop:
                break
        wall_clock_seconds = time.perf_counter() - start_time
        states = scheduler.get_all_states()
        # Contract: unexecuted terminal skipped/cancelled nodes receive default records.
        for node_id in sorted(states):
            if node_id in self._results:
                continue
            state = states[node_id]
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id, state=state
                )
        # Contract: consolidate outcome tuples from recorded results and states.
        state_by_node: Dict[str, dag_engine_lite.NodeState] = {
            node_id: result.state for node_id, result in self._results.items()
        }
        for node_id, state in states.items():
            state_by_node.setdefault(node_id, state)
        critical_path, _ = dag.compute_critical_path(None)
        # Contract: return the consolidated run report.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in state_by_node.items()
                    if state == dag_engine_lite.NodeState.SUCCEEDED
                )
            ),
            failed_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in state_by_node.items()
                    if state == dag_engine_lite.NodeState.FAILED
                )
            ),
            skipped_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in state_by_node.items()
                    if state == dag_engine_lite.NodeState.SKIPPED
                )
            ),
            cancelled_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in state_by_node.items()
                    if state == dag_engine_lite.NodeState.CANCELLED
                )
            ),
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T00:43:34Z
# LAST_CHANGED: 2026-11-12T00:34:02Z
# CHANGE: Removed eager PENDING->READY promotion from WaveScheduler._sync_states so synchronization only discovers nodes and initializes roots READY / dependency-bearing nodes PENDING; downstream promotion now occurs exclusively in mark_succeeded. Restored the is_finished PENDING eligibility recheck (newly registered dependency-bearing node with SUCCEEDED deps is executable work => return False) instead of quarantining it as unreachable. Static checks pass.
# COVERAGE_AUDIT: 2026-11-12T00:37:05Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T00:43:34Z
# PRETENSE_QA_AUDIT: 2026-11-12T00:43:21Z
# QA_AUDIT: 2026-11-12T00:36:42Z
# --- END AUTOFAB METADATA ---
