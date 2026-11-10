# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_055639_deepseek-flash_dag_engine_lite
# Timestamp: 2026-11-08T05:56:39.417064+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 213,834
#   Cached Inbound Tokens:   10,056,704
#   Outbound Tokens:         156,542
#   Total Tokens:            10,427,080
#   Financial Cost ($USD):   $0.1562
#   Wall Clock Duration:     988.49s
#   Step Latencies (s):      [172.8, 296.9, 20.2, 146.7, 165.4, 173.3, 103.7, 50.7, 20.2, 93.6, 50.7, 10.1, 10.0]
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 4, test: 3 (Total: 13)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       47
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Low-level specification realization for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import enum
from dataclasses import dataclass
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

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Precondition contract violation error raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Precondition contract violation error raised when attempting to add a node identifier that already exists in the DAG.

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
        """Validates graph consistency, completeness, and acyclicity.

        Raises:
            NodeNotFoundError: When a referenced dependency is not registered.
            CycleError: When the graph contains a directed cycle.
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
            CycleError: When the graph contains a directed cycle.
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

        Raises:
            NodeNotFoundError: When the node is not registered in the scheduled DAG.
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

        Raises:
            NodeNotFoundError: When a referenced dependency is not registered.
            CycleError: When the graph contains a directed cycle.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:01:39Z
# LAST_CHANGED: 2026-11-08T06:01:39Z
# CHANGE: Realized low-level spec: framework-decorated @data_type records (mutable dataclass exceptions with __str__ since frozen dataclasses are invalid for exceptions), @singleton_type/@operation protocol stubs for DAG, WaveScheduler, DAGRunner with no __initialize__.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dag_engine_lite

# Terminal node states after which no further execution is possible.
_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
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

    Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping
    node identifiers to definitions and sets.
    """

    tier = system

    def __init__(self) -> None:
        # Backing state for node definitions and directed adjacency tracking.
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def _check_dependencies_exist(self) -> None:
        """Raises when a referenced dependency is not registered in the graph."""
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._upstream.get(node_id, set())):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on node '{dependency}' which is not registered in the DAG",
                        dependency,
                    )

    def _find_cycle(self) -> Tuple[str, ...]:
        """Detects a directed cycle via depth-first search with an active path stack."""
        visited: Set[str] = set()
        active: List[str] = []
        active_set: Set[str] = set()

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            if node_id in active_set:
                # Active recursion path revisited: slice the path forming the cycle.
                return tuple(active[active.index(node_id):])
            if node_id in visited:
                return None
            active_set.add(node_id)
            active.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, set())):
                if dependent in self._nodes:
                    found = visit(dependent)
                    if found is not None:
                        return found
            active.pop()
            active_set.discard(node_id)
            visited.add(node_id)
            return None

        for node_id in sorted(self._nodes):
            cycle = visit(node_id)
            if cycle:
                return cycle
        return ()

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
        # PRECONDITION duplicate_node: node_id must not already be registered.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                f"Node '{node_id}' is already registered in the DAG",
                node_id,
            )
        dependency_set: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        # POSTCONDITION register_definition: freeze the node definition into the graph.
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
        # POSTCONDITION directed_dependencies: add each directed dependency edge.
        # POSTCONDITION defer_dependency_checks: missing nodes are not eagerly rejected.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # PRECONDITION nodes_must_exist: both endpoint identifiers must be registered.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{upstream_id}' is not registered in the DAG",
                upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{downstream_id}' is not registered in the DAG",
                downstream_id,
            )
        # POSTCONDITION directed_edge: downstream depends on upstream.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # PRECONDITION node_must_exist: the identifier must be registered.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION purge_incident_edges: strip the node from every neighbor set.
        for dependency in self._upstream.get(node_id, set()):
            dependents = self._downstream.get(dependency)
            if dependents is not None:
                dependents.discard(node_id)
        for dependent in self._downstream.get(node_id, set()):
            dependencies = self._upstream.get(dependent)
            if dependencies is not None:
                dependencies.discard(node_id)
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
        # PRECONDITION node_must_exist: raise when the identifier is unknown.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION return_definition: return the registered definition.
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # PRECONDITION node_must_exist: raise when the identifier is unknown.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION return_upstream: expose a defensive copy of direct upstream nodes.
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # PRECONDITION node_must_exist: raise when the identifier is unknown.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION return_downstream: expose a defensive copy of direct downstream nodes.
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # PRECONDITION dependencies_exist: every referenced node must be registered.
        self._check_dependencies_exist()
        # PRECONDITION acyclic_graph: reject any directed cycle.
        cycle = self._find_cycle()
        if cycle:
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected in DAG: {' -> '.join(cycle)}",
                cycle,
            )
        # POSTCONDITION complete_valid: consistent graphs complete without error.

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Missing dependency existence checks are deferred from add_node to here.
        self._check_dependencies_exist()
        # In-degree counts derived from the upstream adjacency mapping.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }

        def sort_key(candidate: str) -> Tuple[int, str]:
            return (-self._nodes[candidate].priority, candidate)

        # Ready set ordered by priority descending, then node_id ascending.
        ready: List[str] = [node_id for node_id in self._nodes if in_degree[node_id] == 0]
        ready.sort(key=sort_key)
        order: List[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort(key=sort_key)
        # PRECONDITION acyclic_graph: unreached nodes imply a directed cycle.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            if not cycle:
                cycle = tuple(sorted(self._nodes))
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected in DAG: {' -> '.join(cycle)}",
                cycle,
            )
        # POSTCONDITION dependency_order / tie_breaking: every prerequisite precedes
        # its dependents with deterministic priority/lexicographical tie-breaking.
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id for node_id in self._nodes if not self._upstream.get(node_id, set())
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id for node_id in self._nodes if not self._downstream.get(node_id, set())
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return ([], 0.0)
        durations: Mapping[str, float] = (
            estimated_durations if estimated_durations is not None else {}
        )
        # Dynamic programming sweep: earliest completion time per node.
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for node_id in order:
            duration = durations.get(node_id, 1.0)
            best_predecessor: Optional[str] = None
            best_time = 0.0
            for dependency in sorted(self._upstream.get(node_id, set())):
                if best_predecessor is None or earliest[dependency] > best_time:
                    best_time = earliest[dependency]
                    best_predecessor = dependency
            earliest[node_id] = best_time + duration
            predecessor[node_id] = best_predecessor
        # Terminal (leaf) node yielding the maximum cumulative completion time.
        terminal: Optional[str] = None
        total_weight = 0.0
        for node_id in order:
            if any(
                dependent in self._nodes
                for dependent in self._downstream.get(node_id, set())
            ):
                continue
            if terminal is None or earliest[node_id] > total_weight:
                terminal = node_id
                total_weight = earliest[node_id]
        # Invariant: a non-empty acyclic graph always contains at least one leaf.
        if terminal is None:  # pragma: no cover (assumption: acyclic graph has a leaf)
            terminal = order[-1]
            total_weight = earliest[terminal]
        # POSTCONDITION longest_path: backtrack through the maximizing predecessors.
        path: List[str] = []
        current = terminal
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        # POSTCONDITION cumulative_weight: return the cumulative path weight.
        return (path, total_weight)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    Maintains scheduling state across _dag and _states mapping node identifiers
    to lifecycle states.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        """Resolves the collaborator DAG service on demand."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _sync_states(self) -> dag_engine_lite.DAG:
        """Synchronizes _states with the currently registered DAG nodes."""
        dag = self._resolve_dag()
        registered = dag.all_nodes()
        # Purge tracking state for nodes no longer registered in the graph.
        for node_id in list(self._states):
            if node_id not in registered:
                del self._states[node_id]
        for node_id in registered:
            if node_id not in self._states:
                dependencies = dag.get_dependencies(node_id)
                # Root nodes start READY; nodes with dependencies start PENDING.
                self._states[node_id] = (
                    dag_engine_lite.NodeState.READY
                    if not dependencies
                    else dag_engine_lite.NodeState.PENDING
                )
        for node_id in registered:
            if self._states[node_id] is dag_engine_lite.NodeState.PENDING:
                dependencies = dag.get_dependencies(node_id)
                if all(
                    self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    # Promote newly unblocked nodes to READY.
                    self._states[node_id] = dag_engine_lite.NodeState.READY
        return dag

    def _transitive_dependents(
        self, dag: dag_engine_lite.DAG, node_id: str
    ) -> List[str]:
        """Collects all transitive downstream dependents of a node."""
        collected: Set[str] = set()
        pending: List[str] = list(dag.get_dependents(node_id))
        while pending:
            current = pending.pop(0)
            if current in collected:
                continue
            collected.add(current)
            pending.extend(dag.get_dependents(current))
        return sorted(collected)

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._sync_states()
        candidates: List[str] = []
        for node_id, state in self._states.items():
            # POSTCONDITION ready_nodes: READY nodes whose upstream nodes all succeeded.
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                candidates.append(node_id)
        # POSTCONDITION priority_order: priority descending, then node_id ascending.
        candidates.sort(key=lambda candidate: (-dag.get_node(candidate).priority, candidate))
        # POSTCONDITION empty_when_no_ready: returns an empty list when none are ready.
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        # POSTCONDITION state_transition: node is now RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        dag = self._sync_states()
        # POSTCONDITION state_transition: node is now SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # POSTCONDITION promote_dependents: unlock newly satisfiable dependents.
        for dependent in sorted(dag.get_dependents(node_id)):
            if self._states.get(dependent) is dag_engine_lite.NodeState.PENDING:
                dependencies = dag.get_dependencies(dependent)
                if all(
                    self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
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
        # POSTCONDITION state_transition: node is now FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # POSTCONDITION fail_fast: cancel every remaining non-terminal node.
            for other_id in dag.all_nodes():
                if other_id == node_id:
                    continue
                if self._states.get(other_id) not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
            return
        if failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # POSTCONDITION skip_downstream: skip all transitive dependents.
            for dependent in self._transitive_dependents(dag, node_id):
                if self._states.get(dependent) not in _TERMINAL_STATES:
                    self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
            return
        # POSTCONDITION continue_on_error: independent nodes stay eligible while
        # blocked dependents of the failed node are skipped.
        for dependent in self._transitive_dependents(dag, node_id):
            if self._states.get(dependent) not in _TERMINAL_STATES:
                self._states[dependent] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        dag = self._sync_states()
        nodes = dag.all_nodes()
        # POSTCONDITION empty_dag: an empty graph is finished.
        if not nodes:
            return True
        for node_id in nodes:
            state = self._states[node_id]
            # POSTCONDITION non_terminal_remaining: RUNNING or READY nodes remain eligible.
            if state in (
                dag_engine_lite.NodeState.READY,
                dag_engine_lite.NodeState.RUNNING,
            ):
                return False
        # POSTCONDITION all_terminal / blocked_by_failure: no eligible node remains.
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        dag = self._sync_states()
        # PRECONDITION node_must_exist: raise when the node is not scheduled.
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._sync_states()
        return {
            node_id: self._states[node_id]
            for node_id in dag.all_nodes()
            if node_id in self._states
        }


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    Coordinates execution using the DAG and WaveScheduler services and the
    _results mapping of node outcomes.
    """

    tier = system

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
        # POSTCONDITION validate_before_waves: reject inconsistent graphs up front.
        dag.validate()
        self._results = {}
        started = time.monotonic()
        halted = False
        # POSTCONDITION sequential_waves: execute wave after wave until finished.
        while not scheduler.is_finished() and not halted:
            wave = scheduler.next_wave()
            if not wave:  # pragma: no cover (assumption: a validated graph is not mutated while waves execute, so an unfinished scheduler always yields a non-empty wave)
                break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                action_started = time.monotonic()
                value: Optional[Any] = None
                error: Optional[Exception] = None
                retries_attempted = 0
                while True:
                    try:
                        value = definition.action()
                        error = None
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        error = exc
                        # POSTCONDITION retry_failures: retry up to definition.retries.
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        break
                duration_seconds = time.monotonic() - action_started
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=error,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    # POSTCONDITION apply_failure_policy: delegate policy handling.
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
        # Default outcome records for terminal nodes that were never dispatched.
        states = scheduler.get_all_states()
        for node_id in sorted(states):
            if node_id in self._results:
                continue
            state = states[node_id]
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        # POSTCONDITION consolidated_report: gather metrics and the critical path.
        critical_path, _ = dag.compute_critical_path(None)
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
            wall_clock_seconds=time.monotonic() - started,
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
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:13:05Z
# LAST_CHANGED: 2026-11-08T06:12:28Z
# CHANGE: Annotated the wave-loop empty-wave stall guard with '# pragma: no cover (assumption: a validated graph is not mutated while waves execute, so an unfinished scheduler always yields a non-empty wave)' rather than deleting it, resolving the unexercisable defensive guard feedback.
# COVERAGE_AUDIT: 2026-11-08T06:13:05Z
# QA_AUDIT: 2026-11-08T06:12:50Z
# --- END AUTOFAB METADATA ---
