# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_192433_deepseek-flash_dag_engine_lite_baseline
# Timestamp: 2026-10-23T19:24:33.221957+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 102,828
#   Cached Inbound Tokens:   3,843,584
#   Outbound Tokens:         69,443
#   Total Tokens:            4,015,855
#   Financial Cost ($USD):   $0.0877
#   Wall Clock Duration:     346.04s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       61
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Low-level specification for the synchronous DAG execution and wave scheduling engine."""

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

    def __str__(self) -> str:
        return self.message


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
"""Low-level implementation specification for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dag_engine_lite


_TERMINAL_STATES = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
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
        # POSTCONDITION: MUST register the node definition into the graph.
        dependency_set = frozenset(dependencies) if dependencies is not None else frozenset()
        self._nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # POSTCONDITION: WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        for dependency_id in dependency_set:
            self._upstream.setdefault(dependency_id, set())
            self._downstream.setdefault(dependency_id, set())
            self._upstream[node_id].add(dependency_id)
            self._downstream[dependency_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # POSTCONDITION: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found in graph",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found in graph",
                node_id=downstream_id,
            )
        # POSTCONDITION: MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        definition = self._nodes[downstream_id]
        self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
            node_id=definition.node_id,
            action=definition.action,
            dependencies=definition.dependencies | {upstream_id},
            priority=definition.priority,
            retries=definition.retries,
        )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # POSTCONDITION: MUST remove the node and its incident edges.
        for upstream_id in list(self._upstream[node_id]):
            self._downstream[upstream_id].discard(node_id)
        for downstream_id in list(self._downstream[node_id]):
            self._upstream[downstream_id].discard(node_id)
            definition = self._nodes[downstream_id]
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=definition.node_id,
                action=definition.action,
                dependencies=definition.dependencies - {node_id},
                priority=definition.priority,
                retries=definition.retries,
            )
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # POSTCONDITION: MUST return the NodeDefinition matching node_id.
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # POSTCONDITION: MUST return all direct upstream dependencies.
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # POSTCONDITION: MUST return all direct downstream dependents.
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # POSTCONDITION: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for node_id, definition in self._nodes.items():
            for dependency_id in definition.dependencies:
                if dependency_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Dependency '{dependency_id}' of node '{node_id}' "
                            "not found in graph"
                        ),
                        node_id=dependency_id,
                    )
        # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=tuple(cycle),
            )
        # POSTCONDITION: WHEN all referenced nodes exist and no cycle exists, MUST complete without error.

    def _find_cycle(self) -> Optional[List[str]]:
        """Depth-first traversal with active path recursion tracking."""
        visited: Set[str] = set()
        active: List[str] = []
        active_set: Set[str] = set()

        def visit(node_id: str) -> Optional[List[str]]:
            visited.add(node_id)
            active.append(node_id)
            active_set.add(node_id)
            for dependent_id in sorted(self._downstream[node_id]):
                if dependent_id in active_set:
                    start = active.index(dependent_id)
                    return active[start:] + [dependent_id]
                if dependent_id not in visited:
                    cycle = visit(dependent_id)
                    if cycle is not None:
                        return cycle
            active.pop()
            active_set.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                cycle = visit(node_id)
                if cycle is not None:
                    return cycle
        return None

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # POSTCONDITION: MUST return a valid topological ordering where every prerequisite precedes its dependents.
        # POSTCONDITION: MUST break ties between concurrent ready nodes using priority descending and name ascending.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream[node_id]) for node_id in self._nodes
        }
        ready: List[str] = [
            node_id for node_id, degree in in_degree.items() if degree == 0
        ]
        ready.sort(key=lambda node_id: (-self._nodes[node_id].priority, node_id))

        order: List[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for dependent_id in self._downstream[node_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    ready.append(dependent_id)
            ready.sort(key=lambda ready_id: (-self._nodes[ready_id].priority, ready_id))

        # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle() or []
            raise dag_engine_lite.CycleError(
                message="Cycle detected during topological sort",
                cycle=tuple(cycle),
            )
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
        # POSTCONDITION: MUST return the sequence of nodes that forms the longest path through the DAG.
        # POSTCONDITION: MUST return the cumulative weight of that path.
        if not self._nodes:
            return ([], 0.0)
        durations = estimated_durations or {}
        order = self.topological_sort()

        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for node_id in order:
            duration = durations.get(node_id, 1.0)
            upstream = self._upstream[node_id]
            if upstream:
                best_upstream = max(
                    upstream, key=lambda upstream_id: (earliest[upstream_id], upstream_id)
                )
                earliest[node_id] = earliest[best_upstream] + duration
                predecessor[node_id] = best_upstream
            else:
                earliest[node_id] = duration
                predecessor[node_id] = None

        terminal_id = max(earliest, key=lambda node_id: (earliest[node_id], node_id))
        total = earliest[terminal_id]

        path: List[str] = []
        current: Optional[str] = terminal_id
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        return (path, total)


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
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronizes the state index with all nodes currently registered in the DAG."""
        registered = self._dag.all_nodes()
        for node_id in list(self._states.keys()):
            if node_id not in registered:
                del self._states[node_id]
        for node_id in registered:
            if node_id not in self._states:
                if self._dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def next_wave(self) -> List[str]:
        # POSTCONDITIONS:
        # - MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        # - MUST order returned nodes by priority descending, then node_id ascending.
        # - WHEN no nodes are ready, MUST return an empty list.
        self._sync_states()
        ready: List[str] = [
            node_id
            for node_id, state in self._states.items()
            if state == dag_engine_lite.NodeState.READY
            and all(
                self._states.get(dependency_id) == dag_engine_lite.NodeState.SUCCEEDED
                for dependency_id in self._dag.get_dependencies(node_id)
            )
        ]
        ready.sort(
            key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id)
        )
        return ready

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # POSTCONDITION: MUST update the node state to RUNNING.
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        # POSTCONDITIONS:
        # - MUST update the node state to SUCCEEDED.
        # - MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dependent_id in self._dag.get_dependents(node_id):
            if self._states.get(dependent_id) == dag_engine_lite.NodeState.PENDING:
                if all(
                    self._states.get(dependency_id)
                    == dag_engine_lite.NodeState.SUCCEEDED
                    for dependency_id in self._dag.get_dependencies(dependent_id)
                ):
                    self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        # POSTCONDITIONS:
        # - MUST update the node state to FAILED.
        # - WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        # - WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        # - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for other_id in self._states:
                if (
                    other_id != node_id
                    and self._states[other_id] not in _TERMINAL_STATES
                ):
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            self._skip_transitive_dependents(node_id)

    def _skip_transitive_dependents(self, node_id: str) -> None:
        """Marks all transitive downstream dependents as SKIPPED."""
        queue: List[str] = list(self._dag.get_dependents(node_id))
        visited: Set[str] = set()
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            if self._states.get(current_id) not in _TERMINAL_STATES:
                self._states[current_id] = dag_engine_lite.NodeState.SKIPPED
                queue.extend(self._dag.get_dependents(current_id))

    @operation
    @override
    def is_finished(self) -> bool:
        # POSTCONDITIONS:
        # - WHEN all nodes in the DAG have reached terminal states, MUST return True.
        # - WHEN any node in the DAG is not in a terminal state, MUST return False.
        # - WHEN the DAG contains no nodes, MUST return True.
        self._sync_states()
        registered = self._dag.all_nodes()
        if not registered:
            return True
        return all(
            self._states.get(node_id) in _TERMINAL_STATES for node_id in registered
        )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler states",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
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
        # POSTCONDITIONS:
        # - MUST execute ready waves sequentially.
        # - MUST execute retries up to the configured retry count for failed node actions.
        # - MUST apply the specified failure_policy to the scheduler upon node failure.
        # - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        self._dag.validate()
        start_time = time.time()
        self._results = {}

        halt = False
        while not halt and not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                self._scheduler.mark_running(node_id)
                definition = self._dag.get_node(node_id)
                result = self._execute_with_retries(node_id, definition)
                self._results[node_id] = result
                if result.state == dag_engine_lite.NodeState.SUCCEEDED:
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halt = True
                        break

        all_states = self._scheduler.get_all_states()
        for node_id, state in all_states.items():
            if node_id not in self._results and state in _TERMINAL_STATES:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )

        critical_path, _ = self._dag.compute_critical_path()
        elapsed = time.time() - start_time

        succeeded = tuple(
            node_id
            for node_id, result in self._results.items()
            if result.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed = tuple(
            node_id
            for node_id, result in self._results.items()
            if result.state == dag_engine_lite.NodeState.FAILED
        )
        skipped = tuple(
            node_id
            for node_id, result in self._results.items()
            if result.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled = tuple(
            node_id
            for node_id, result in self._results.items()
            if result.state == dag_engine_lite.NodeState.CANCELLED
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

    def _execute_with_retries(
        self,
        node_id: str,
        definition: dag_engine_lite.NodeDefinition[Any],
    ) -> dag_engine_lite.NodeResult[Any]:
        """Executes a node action, retrying up to the definition's retry count."""
        max_attempts = definition.retries + 1
        start_time = time.time()
        last_error: Optional[Exception] = None
        for attempt in range(max_attempts):
            try:
                value = definition.action()
            except Exception as exc:
                last_error = exc
            else:
                return dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=dag_engine_lite.NodeState.SUCCEEDED,
                    value=value,
                    duration_seconds=time.time() - start_time,
                    retries_attempted=attempt,
                )
        return dag_engine_lite.NodeResult(
            node_id=node_id,
            state=dag_engine_lite.NodeState.FAILED,
            error=last_error,
            duration_seconds=time.time() - start_time,
            retries_attempted=max_attempts - 1,
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
