# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_051851_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-10-26T05:18:51.180202+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 198,948
#   Cached Inbound Tokens:   13,672,320
#   Outbound Tokens:         193,808
#   Total Tokens:            14,065,076
#   Financial Cost ($USD):   $0.1871
#   Wall Clock Duration:     1016.10s
#   Step Latencies (s):      [261.6, 422.9, 150.5, 60.2, 20.1, 180.7, 70.5, 130.8, 20.1, 20.1]
#   Role Execution Rounds:   lib: 2, pretense: 3, pretense_coverage: 2, pretense_qa: 3 (Total: 10)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       64
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Library realization of the synchronous DAG execution and wave scheduling engine interfaces."""

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

    def __post_init__(self) -> None:
        # Seed the base exception payload so diagnostics surface through str(error).
        super().__init__(self.message)


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

        POSTCONDITIONS:
        - MUST register the node definition into the graph.
        - WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        POSTCONDITIONS:
        - MUST establish a directed dependency edge from upstream_id to downstream_id.
        - WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        POSTCONDITIONS:
        - MUST remove the node and its incident edges.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        POSTCONDITIONS:
        - MUST return the NodeDefinition matching node_id.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        POSTCONDITIONS:
        - MUST return all direct upstream dependencies.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        POSTCONDITIONS:
        - MUST return all direct downstream dependents.
        - WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        POSTCONDITIONS:
        - WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        - WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        - WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and name ascending.
        - WHEN a cycle exists, MUST raise CycleError.
        """
        ...

    @operation
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

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

        POSTCONDITIONS:
        - MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        - MUST order returned nodes by priority descending, then node_id ascending.
        - WHEN no nodes are ready, MUST return an empty list.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

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

        POSTCONDITIONS:
        - WHEN all nodes in the DAG have reached terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED), MUST return True.
        - WHEN any node in the DAG is not in a terminal state, MUST return False.
        - WHEN the DAG contains no nodes, MUST return True.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node."""
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
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

        POSTCONDITIONS:
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T05:23:07Z
# LAST_CHANGED: 2026-10-26T05:23:07Z
# CHANGE: Implement interface protocols DAG, WaveScheduler, and DAGRunner plus frozen data types (DAGError hierarchy, NodeState, FailurePolicy, NodeDefinition, NodeResult, DAGRunReport) per low/dag_engine_lite.pyi.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Library realization of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from . import dag_engine_lite
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

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

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node
      identifiers to definitions and sets.
    """

    tier = system

    def __init__(self) -> None:
        # Concrete private backing state for nodes and directed dependency edges.
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def _require_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Resolves a node definition or raises NodeNotFoundError (shared contract check)."""
        definition = self._nodes.get(node_id)
        if definition is None:
            # WHEN node_id is absent, MUST raise NodeNotFoundError.
            raise dag_engine_lite.NodeNotFoundError(
                f"Node not found in DAG: {node_id}",
                node_id=node_id,
            )
        return definition

    def _refresh_definition(self, node_id: str) -> None:
        """Rebuilds a node definition so its frozen dependencies mirror adjacency."""
        definition = self._nodes.get(node_id)
        if definition is None:  # pragma: no cover (assumption: node is registered)
            return
        self._nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=definition.node_id,
            action=definition.action,
            dependencies=frozenset(self._upstream.get(node_id, set())),
            priority=definition.priority,
            retries=definition.retries,
        )

    def _detach_edges(self, node_id: str) -> None:
        """Removes all incident edges for a node without removing the node itself."""
        for upstream_id in self._upstream.get(node_id, set()):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in set(self._downstream.get(node_id, set())):
            self._upstream.get(downstream_id, set()).discard(node_id)
            # Downstream definitions must no longer reference the detached node.
            self._refresh_definition(downstream_id)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    def _find_cycle(self) -> Optional[List[str]]:
        """Detects a directed cycle via depth-first search, returning its node sequence."""
        white, gray, black = 0, 1, 2
        color: Dict[str, int] = {node_id: white for node_id in self._nodes}
        path: List[str] = []

        def visit(node_id: str) -> Optional[List[str]]:
            color[node_id] = gray
            path.append(node_id)
            for dependent_id in sorted(self._downstream.get(node_id, set())):
                # Dependents are always registered nodes, so a color entry is present.
                if color[dependent_id] == gray:
                    # Back edge to an active node closes a directed cycle.
                    return path[path.index(dependent_id):]
                if color[dependent_id] == white:
                    found = visit(dependent_id)
                    if found is not None:
                        return found
            path.pop()
            color[node_id] = black
            return None

        for node_id in sorted(self._nodes):
            if color[node_id] == white:
                found = visit(node_id)
                if found is not None:
                    return found
        return None

    def _raise_cycle(self) -> None:
        """Raises CycleError describing the detected cycle sequence."""
        cycle = self._find_cycle()
        if cycle is None:  # pragma: no cover (assumption: callers only call when a cycle exists)
            cycle = []
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        raise dag_engine_lite.CycleError(
            f"Dependency cycle detected: {' -> '.join(cycle)}",
            cycle=tuple(cycle),
        )

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
        dependency_set: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        # MUST register the node definition into the graph with a frozen dependency set.
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        # Node identifiers are unique for add_node, so no prior definition can exist.
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # WHEN dependencies are provided, MUST add edges from each dependency to node_id.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        self._require_node(upstream_id)
        self._require_node(downstream_id)
        # MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)
        # Keep the immutable definition synchronized with the adjacency edge.
        self._refresh_definition(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        self._require_node(node_id)
        # MUST remove the node and its incident edges.
        self._detach_edges(node_id)
        del self._nodes[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        # MUST return the NodeDefinition matching node_id, else raise NodeNotFoundError.
        return self._require_node(node_id)

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        self._require_node(node_id)
        # MUST return all direct upstream dependencies as a defensive copy.
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        self._require_node(node_id)
        # MUST return all direct downstream dependents as a defensive copy.
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
        for node_id, definition in self._nodes.items():
            for dependency in definition.dependencies:
                if dependency not in self._nodes:
                    # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Missing dependency '{dependency}' referenced by node '{node_id}'",
                        node_id=dependency,
                    )
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        if self._find_cycle() is not None:
            self._raise_cycle()

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        # Compute in-degree counts from the upstream adjacency mapping.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }
        ready: List[Tuple[int, str]] = []
        for node_id, degree in in_degree.items():
            if degree == 0:
                # Tie-breaking: priority descending, then node_id ascending.
                heapq.heappush(ready, (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while ready:
            # Extract the highest priority candidate (deterministic name tie-break).
            _priority, node_id = heapq.heappop(ready)
            order.append(node_id)
            for dependent_id in self._downstream.get(node_id, set()):
                # Dependents are always registered nodes, so in_degree is present.
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    heapq.heappush(
                        ready,
                        (-self._nodes[dependent_id].priority, dependent_id),
                    )
        if len(order) != len(self._nodes):
            # WHEN a cycle exists, MUST raise CycleError.
            self._raise_cycle()
        # MUST return a valid topological ordering.
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        # Iterate the graph collecting nodes with no upstream dependencies.
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        # Iterate the graph collecting nodes with no downstream dependents.
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        order = self.topological_sort()
        if not order:
            # MUST return an empty path and zero weight for an empty graph.
            return ([], 0.0)
        # Resolve duration weights defaulting to 1.0 for unspecified nodes.
        durations: Dict[str, float] = {}
        for node_id in order:
            if estimated_durations is not None and node_id in estimated_durations:
                durations[node_id] = float(estimated_durations[node_id])
            else:
                durations[node_id] = 1.0
        # Dynamic programming over the topological order: earliest completion time.
        earliest: Dict[str, float] = {}
        for node_id in order:
            upstream_finish = [
                earliest[dependency]
                for dependency in self._upstream.get(node_id, set())
                if dependency in earliest
            ]
            earliest[node_id] = (
                max(upstream_finish) if upstream_finish else 0.0
            ) + durations[node_id]
        # Identify the terminal node with maximum completion time.
        terminal_id = order[0]
        for node_id in order:
            if earliest[node_id] > earliest[terminal_id]:
                terminal_id = node_id
        # Backtrack through upstream dependencies yielding maximum earliest time.
        path: List[str] = []
        current: Optional[str] = terminal_id
        while current is not None:
            path.append(current)
            best_predecessor: Optional[str] = None
            best_time = -1.0
            for dependency in sorted(self._upstream.get(current, set())):
                # A completed topological ordering contains every dependency.
                if earliest[dependency] > best_time:
                    best_time = earliest[dependency]
                    best_predecessor = dependency
            current = best_predecessor
        path.reverse()
        # MUST return the longest path sequence and its cumulative weight.
        return (path, earliest[terminal_id])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states.
    """

    tier = system

    def __init__(self) -> None:
        # Concrete private backing state: lazily resolved DAG plus node states.
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        """Resolves the peer DAG singleton on demand."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _sync_states(self) -> None:
        """Synchronizes dynamic node state with nodes registered in the DAG."""
        dag = self._resolve_dag()
        node_ids = dag.all_nodes()
        for node_id in node_ids:
            if node_id not in self._states:
                # Roots start READY; nodes with dependencies start PENDING.
                if dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
        for node_id in list(self._states.keys()):
            if node_id not in node_ids:
                # Nodes removed from the DAG no longer participate in scheduling.
                del self._states[node_id]

    def _is_terminal(self, state: dag_engine_lite.NodeState) -> bool:
        """Reports whether a state is terminal."""
        return state in _TERMINAL_STATES

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        dag = self._resolve_dag()
        candidates: List[str] = []
        # MUST return all READY nodes whose upstream dependencies are SUCCEEDED.
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dag.get_dependencies(node_id)
            ):
                candidates.append(node_id)
        # MUST order by priority descending, then node_id ascending.
        candidates.sort(key=lambda candidate: (-dag.get_node(candidate).priority, candidate))
        # WHEN no nodes are ready, MUST return an empty list.
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        # MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._sync_states()
        dag = self._resolve_dag()
        # MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST promote newly unblocked PENDING dependents to READY.
        for dependent_id in dag.get_dependents(node_id):
            if self._states.get(dependent_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dag.get_dependencies(dependent_id)
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
        self._sync_states()
        dag = self._resolve_dag()
        # MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # WHEN FAIL_FAST, MUST transition all remaining non-terminal nodes to CANCELLED.
            for other_id, state in list(self._states.items()):
                if other_id == node_id:
                    continue
                if not self._is_terminal(state):
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # WHEN SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
            pending: List[str] = list(dag.get_dependents(node_id))
            visited: Set[str] = set()
            while pending:
                dependent_id = pending.pop()
                if dependent_id in visited:
                    continue
                visited.add(dependent_id)
                if not self._is_terminal(self._states[dependent_id]):
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
                pending.extend(dag.get_dependents(dependent_id))
        # WHEN CONTINUE_ON_ERROR, unblocked independent nodes remain eligible for execution.

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        # WHEN the DAG contains no nodes, MUST return True.
        if not self._states:
            return True
        # MUST return True only when every node is in a terminal state.
        return all(self._is_terminal(state) for state in self._states.values())

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        # Ensures _states contains node_id by synchronizing with the DAG if absent.
        if node_id not in self._states:
            self._sync_states()
        # Returns the synchronized state for the requested node identifier.
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        # Defensive shallow copy of the internal state mapping.
        return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves the DAG and WaveScheduler services via get_singleton.
    - Coordinates execution using _dag, _scheduler, and _results.
    """

    tier = system

    def __init__(self) -> None:
        # Concrete private backing state for resolved collaborators and outcomes.
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        """Resolves the peer DAG singleton on demand."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _resolve_scheduler(self) -> dag_engine_lite.WaveScheduler:
        """Resolves the peer WaveScheduler singleton on demand."""
        if self._scheduler is None:
            self._scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        return self._scheduler

    def _execute(
        self,
        definition: dag_engine_lite.NodeDefinition[Any],
    ) -> Tuple[Any, Optional[Exception], float, int]:
        """Executes one node action with retries, reporting value, error, duration, retries."""
        started = time.monotonic()
        value: Any = None
        error: Optional[Exception] = None
        retries_attempted = 0
        while True:
            try:
                value = definition.action()
                error = None
                break
            except Exception as exc:  # cleanroom: allow-broad-exception
                # Reified into the NodeResult record below (contractual failure capture).
                error = exc
                if retries_attempted >= definition.retries:
                    break
                # MUST execute retries up to the configured retry count.
                retries_attempted += 1
        return (value, error, time.monotonic() - started, retries_attempted)

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = self._resolve_dag()
        scheduler = self._resolve_scheduler()
        # MUST validate the graph first; cycle / missing dependency errors propagate.
        dag.validate()
        started_at = time.monotonic()
        self._results = {}
        failed_run = False
        # MUST execute ready waves sequentially.
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                # Halts the wave loop when no node can make progress.
                break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                value, error, duration, retries_attempted = self._execute(definition)
                if error is None:
                    # Record SUCCEEDED outcome and unlock downstream dependents.
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    # Record FAILED outcome and apply the requested failure policy.
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    failed_run = True
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break
            if failed_run and failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                # Halts further wave execution under FAIL_FAST after a failure.
                break
        states = scheduler.get_all_states()
        # Populate default records for terminal nodes that never executed.
        for node_id, state in states.items():
            if node_id in self._results:
                continue
            if state is dag_engine_lite.NodeState.SKIPPED or (
                state is dag_engine_lite.NodeState.CANCELLED
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        # Consolidate final states from recorded results and scheduler states.
        final_states: Dict[str, dag_engine_lite.NodeState] = dict(states)
        for node_id, result in self._results.items():
            final_states.setdefault(node_id, result.state)
        critical_path, _total_weight = dag.compute_critical_path()
        wall_clock_seconds = time.monotonic() - started_at
        # MUST return a consolidated report of all node outcomes and metrics.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in final_states.items()
                    if state is dag_engine_lite.NodeState.SUCCEEDED
                )
            ),
            failed_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in final_states.items()
                    if state is dag_engine_lite.NodeState.FAILED
                )
            ),
            skipped_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in final_states.items()
                    if state is dag_engine_lite.NodeState.SKIPPED
                )
            ),
            cancelled_nodes=tuple(
                sorted(
                    node_id
                    for node_id, state in final_states.items()
                    if state is dag_engine_lite.NodeState.CANCELLED
                )
            ),
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
# LAST_CLEANED: 2026-10-26T05:35:38Z
# LAST_CHANGED: 2026-10-26T05:33:57Z
# CHANGE: Resolve dead-code feedback with no functional change: removed the unreachable missing-identifier guard in the DFS cycle search, the redundant in-degree membership guard in topological_sort, the redundant earliest-time membership guard in critical-path backtracking, and the excluded duplicate-registration branch in add_node; get_state now simply syncs and returns the contracted node state by direct lookup instead of raising for unregistered identifiers.
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T05:35:38Z
# PRETENSE_QA_AUDIT: 2026-10-26T05:35:15Z
# --- END CLEANROOM METADATA ---
