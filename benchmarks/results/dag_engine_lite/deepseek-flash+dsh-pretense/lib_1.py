# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261103_003801_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-03T00:38:01.151936+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 230,565
#   Cached Inbound Tokens:   18,956,928
#   Outbound Tokens:         223,065
#   Total Tokens:            19,410,558
#   Financial Cost ($USD):   $0.2253
#   Wall Clock Duration:     1287.25s
#   Step Latencies (s):      [199.4, 673.4, 22.8, 218.3, 176.3, 31.2, 72.6, 21.0, 20.7, 72.4, 21.0, 20.6]
#   Role Execution Rounds:   lib: 2, pretense: 3, pretense_coverage: 3, pretense_qa: 4 (Total: 12)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Low-level specification for the synchronous DAG execution and wave scheduling engine."""

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
        - MUST defer missing dependency existence checks to validate() and topological_sort() without eagerly raising NodeNotFoundError.
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
        - MUST purge the node identifier from wave scheduler state tracking.
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

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and lexicographical node_id ascending.
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
        """Transitions a node to the RUNNING state.

        POSTCONDITIONS:
        - MUST update the node state to RUNNING.
        """
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
        - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution and transition blocked dependents of failed nodes to SKIPPED.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        POSTCONDITIONS:
        - WHEN all nodes in the DAG have reached terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED), MUST return True.
        - WHEN no ready nodes remain and unexecuted nodes are blocked by failed dependencies, MUST return True.
        - WHEN any node in the DAG remains non-terminal and eligible to execute, MUST return False.
        - WHEN the DAG contains no nodes, MUST return True.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node."""
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
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        POSTCONDITIONS:
        - MUST validate graph invariants before commencing wave execution.
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T00:41:21Z
# LAST_CHANGED: 2026-11-03T00:41:21Z
# CHANGE: Author the dag_engine_lite interface module: frozen data records (NodeDefinition, NodeResult, DAGRunReport), non-frozen exception dataclasses (DAGError, CycleError, NodeNotFoundError, NodeExecutionError) with message-preserving __str__, NodeState/FailurePolicy enums, and @singleton_type('system') Protocol services (DAG, WaveScheduler, DAGRunner) with @operation stubs matching low/dag_engine_lite.pyi.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple
import heapq
import time

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi


# Terminal node states: no further execution or state promotion may occur.
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
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """

    tier = system

    def __init__(self) -> None:
        # Concrete backing storage for node definitions and directed adjacency sets.
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
        """Adds a task node to the graph.

        GROUNDING:
        - Constructs immutable dag_engine_lite.NodeDefinition with frozen dependency set without eagerly checking dependency existence.
        - Inserts definition into _nodes, registering empty neighbor sets in _upstream and _downstream if absent.
        - Adds directed edges from each dependency to node_id, deferring existence validation.
        """
        frozen_dependencies: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        # MUST register the node definition into the graph.
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_dependencies,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # WHEN dependencies are provided, add edges from each dependency to node_id,
        # deferring existence validation to validate()/topological_sort().
        for dependency in frozen_dependencies:
            self._downstream.setdefault(dependency, set()).add(node_id)
            self._upstream[node_id].add(dependency)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        GROUNDING:
        - Verifies presence of upstream_id and downstream_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if either identifier is missing.
        - Updates _upstream and _downstream sets.
        """
        # WHEN upstream_id or downstream_id does not exist, raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Upstream node '{upstream_id}' does not exist in the graph.",
                upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Downstream node '{downstream_id}' does not exist in the graph.",
                downstream_id,
            )
        # MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        GROUNDING:
        - Verifies presence of node_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if absent.
        - Removes node_id from all incident upstream and downstream neighbor sets.
        - Deletes node_id from _nodes, _upstream, and _downstream.
        """
        # WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id,
            )
        # MUST remove the node and its incident edges.
        for upstream_id in self._upstream.get(node_id, set()):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self._downstream.get(node_id, set()):
            self._upstream.get(downstream_id, set()).discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)
        # Wave scheduler state tracking is purged dynamically: the scheduler
        # synchronizes its _states mapping against all_nodes() on every query.

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        GROUNDING:
        - Checks membership of node_id in _nodes.
        """
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        GROUNDING:
        - Looks up node_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if node_id is not present.
        """
        # WHEN node_id is absent, raise NodeNotFoundError.
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id,
            )
        # MUST return the NodeDefinition matching node_id.
        return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        GROUNDING:
        - Verifies node_id in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Returns a copy of _upstream[node_id].
        """
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id,
            )
        # MUST return all direct upstream dependencies as a defensive copy.
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        GROUNDING:
        - Verifies node_id in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Returns a copy of _downstream[node_id].
        """
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id,
            )
        # MUST return all direct downstream dependents as a defensive copy.
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        GROUNDING:
        - Returns a copy of set(_nodes.keys()).
        """
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        GROUNDING:
        - Verifies that every dependency in every node definition exists in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Executes depth-first search cycle detection with active recursion path tracking.
        - Raises dag_engine_lite.CycleError containing the cycle sequence upon detecting any directed cycle.
        """
        # WHEN a dependency node is missing, raise NodeNotFoundError.
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._upstream.get(node_id, set())):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on unknown node '{dependency}'.",
                        dependency,
                    )
        # WHEN a cycle exists, raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle:
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}.",
                tuple(cycle),
            )
        # WHEN all referenced nodes exist and no cycle exists, complete without error.

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        GROUNDING:
        - Computes in-degree counts from _upstream mapping.
        - Initializes ready list with nodes having in-degree zero, sorted by priority descending then node_id ascending.
        - Iteratively extracts candidate with highest priority, appends to order, and decrements downstream in-degrees.
        - Inserts newly zero in-degree nodes maintaining priority descending then node_id ascending order.
        - Raises dag_engine_lite.CycleError containing the cycle sequence if ordered count does not equal len(_nodes).
        - Returns computed topological order list.
        """
        # In-degree counts derive from the upstream adjacency mapping.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }
        # Ready heap ordered by priority descending, then node_id ascending.
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
            for downstream_id in sorted(self._downstream.get(node_id, set())):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    heapq.heappush(
                        ready,
                        (-self._nodes[downstream_id].priority, downstream_id),
                    )
        if len(order) != len(self._nodes):
            # Missing dependency references surface as NodeNotFoundError (deferred check).
            for node_id in sorted(self._nodes):
                for dependency in sorted(self._upstream.get(node_id, set())):
                    if dependency not in self._nodes:
                        raise dag_engine_lite.NodeNotFoundError(
                            f"Node '{node_id}' depends on unknown node '{dependency}'.",
                            dependency,
                        )
            # Otherwise the unorderable remainder must contain a directed cycle.
            cycle = self._find_cycle()
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}.",
                tuple(cycle),
            )
        # MUST return a valid topological ordering with deterministic tie-breaking.
        return order

    def _find_cycle(self) -> List[str]:
        """Depth-first search returning one directed cycle sequence, if any."""
        visited: Set[str] = set()
        active_path: List[str] = []
        active: Set[str] = set()

        def visit(node_id: str) -> Optional[List[str]]:
            visited.add(node_id)
            active.add(node_id)
            active_path.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                # Callers report missing dependencies before invoking cycle detection,
                # so cycle search traverses only registered nodes.
                if dependency in active:
                    start = active_path.index(dependency)
                    return active_path[start:] + [dependency]
                if dependency not in visited:
                    found = visit(dependency)
                    if found is not None:
                        return found
            active_path.pop()
            active.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                found = visit(node_id)
                if found is not None:
                    return found
        return []

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero.

        GROUNDING:
        - Iterates over _nodes, collecting node identifiers whose _upstream set is empty.
        - Returns set of root node identifiers.
        """
        return {
            node_id for node_id in self._nodes if not self._upstream.get(node_id)
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero.

        GROUNDING:
        - Iterates over _nodes, collecting node identifiers whose _downstream set is empty.
        - Returns set of leaf node identifiers.
        """
        return {
            node_id for node_id in self._nodes if not self._downstream.get(node_id)
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        GROUNDING:
        - Computes topological order using topological_sort().
        - Resolves duration weights mapping defaulting to 1.0 for unspecified nodes.
        - Computes earliest completion times using dynamic programming.
        - Identifies terminal node with maximum completion time.
        - Backtracks through upstream dependencies selecting predecessor yielding maximum earliest time.
        - Returns reversed path list and total path duration weight.
        """
        order = self.topological_sort()
        if not order:
            return [], 0.0
        # Default duration weight is 1.0 for every node lacking an explicit estimate.
        durations: Dict[str, float] = {node_id: 1.0 for node_id in self._nodes}
        if estimated_durations is not None:
            for node_id, duration in estimated_durations.items():
                if node_id in durations:
                    durations[node_id] = float(duration)
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for node_id in order:
            upstream = sorted(self._upstream.get(node_id, set()))
            best_predecessor: Optional[str] = None
            if upstream:
                # Deterministic tie-break: highest earliest completion, then node_id.
                best_predecessor = sorted(
                    upstream, key=lambda upstream_id: (-earliest[upstream_id], upstream_id)
                )[0]
            earliest[node_id] = (
                earliest[best_predecessor] if best_predecessor is not None else 0.0
            ) + durations[node_id]
            predecessor[node_id] = best_predecessor
        # Terminal node with maximum completion time (deterministic tie-break).
        terminal = sorted(order, key=lambda node_id: (-earliest[node_id], node_id))[0]
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        return path, earliest[terminal]


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
        # Phase-local scheduling state; the peer DAG service is resolved on demand.
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        """Resolves the active DAG service on demand."""
        return get_singleton(dag_engine_lite.DAG)

    def _dependencies_succeeded(self, dag: dag_engine_lite.DAG, node_id: str) -> bool:
        """Checks whether every upstream dependency of a node has SUCCEEDED."""
        for dependency in dag.get_dependencies(node_id):
            if self._states.get(dependency) is not dag_engine_lite.NodeState.SUCCEEDED:
                return False
        return True

    def _synchronize(self) -> dag_engine_lite.DAG:
        """Synchronizes _states with nodes currently registered in the DAG."""
        dag = self._resolve_dag()
        nodes = dag.all_nodes()
        # Purge state tracking for nodes removed from the graph.
        for stale_id in [node_id for node_id in self._states if node_id not in nodes]:
            del self._states[stale_id]
        # Initialize newly discovered nodes: roots READY, non-roots PENDING.
        for node_id in nodes:
            if node_id not in self._states:
                if dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
        return dag

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        GROUNDING:
        - Ensures _states contains all nodes from _dag.
        - Gathers all nodes currently in dag_engine_lite.NodeState.READY whose upstream dependencies are all dag_engine_lite.NodeState.SUCCEEDED.
        - Sorts candidate nodes by definition priority descending, then node_id ascending.
        - Returns ordered list of ready node identifiers.
        """
        dag = self._synchronize()
        candidates = [
            node_id
            for node_id in dag.all_nodes()
            if self._states.get(node_id) is dag_engine_lite.NodeState.READY
            and self._dependencies_succeeded(dag, node_id)
        ]
        # MUST order returned nodes by priority descending, then node_id ascending.
        candidates.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.RUNNING.
        """
        self._synchronize()
        # MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.SUCCEEDED.
        - Inspects downstream dependents of node_id.
        - Promotes any dependent currently PENDING to READY if all its upstream dependencies are SUCCEEDED.
        """
        dag = self._synchronize()
        # MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST promote newly unblocked dependents to READY.
        for dependent_id in dag.get_dependents(node_id):
            if self._states.get(dependent_id) is dag_engine_lite.NodeState.PENDING:
                if self._dependencies_succeeded(dag, dependent_id):
                    self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.FAILED.
        - Transitions all non-terminal nodes to CANCELLED if failure_policy is FAIL_FAST.
        - Traverses transitive downstream dependents and marks non-terminal dependents as SKIPPED if failure_policy is SKIP_DOWNSTREAM.
        - Retains non-terminal states for unblocked independent nodes if failure_policy is CONTINUE_ON_ERROR, transitioning blocked dependents of failed nodes to SKIPPED.
        """
        dag = self._synchronize()
        # MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # WHEN FAIL_FAST, cancel every remaining non-terminal node.
            for other_id in list(self._states):
                if self._states[other_id] not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # Collect transitive downstream dependents (all are permanently blocked).
        blocked: Set[str] = set(dag.get_dependents(node_id))
        pending: List[str] = list(blocked)
        while pending:
            dependent_id = pending.pop()
            # Each transitive dependent is enqueued at most once via the blocked set.
            for downstream_id in dag.get_dependents(dependent_id):
                if downstream_id not in blocked:
                    blocked.add(downstream_id)
                    pending.append(downstream_id)
        for dependent_id in blocked:
            if self._states.get(dependent_id) not in _TERMINAL_STATES:
                # WHEN SKIP_DOWNSTREAM or CONTINUE_ON_ERROR, blocked dependents are SKIPPED.
                self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
        if failure_policy is dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            # Leave unblocked independent nodes eligible for execution.
            for other_id in dag.all_nodes():
                if self._states.get(other_id) is dag_engine_lite.NodeState.PENDING:
                    if self._dependencies_succeeded(dag, other_id):
                        self._states[other_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        GROUNDING:
        - Synchronizes _states with all nodes currently registered in _dag.all_nodes().
        - Checks whether every node in the DAG is present in _states and in a terminal state.
        - Returns True if all registered DAG nodes have reached terminal states or if no ready nodes remain and unexecuted nodes are blocked by failed dependencies, or if DAG is empty; False otherwise.
        """
        dag = self._synchronize()
        nodes = dag.all_nodes()
        # WHEN the DAG contains no nodes, return True.
        if not nodes:
            return True
        # WHEN all nodes reached terminal states, return True.
        if all(self._states.get(node_id) in _TERMINAL_STATES for node_id in nodes):
            return True
        # WHEN no ready nodes remain, unexecuted nodes are blocked by failed dependencies.
        if not any(
            self._states.get(node_id) is dag_engine_lite.NodeState.READY
            for node_id in nodes
        ):
            return True
        # Otherwise a node remains non-terminal and eligible to execute.
        return False

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node.

        GROUNDING:
        - Ensures _states contains node_id by synchronizing with _dag.all_nodes() if absent.
        - Returns _states[node_id].
        """
        self._synchronize()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph.

        GROUNDING:
        - Ensures _states contains all nodes from _dag.all_nodes().
        - Returns a shallow copy of _states mapping filtered to only include nodes currently present in _dag.all_nodes().
        """
        dag = self._synchronize()
        return {node_id: self._states[node_id] for node_id in dag.all_nodes()}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier = system

    def __init__(self) -> None:
        # Consolidated execution outcomes accumulated across the current run.
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        GROUNDING:
        - Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately.
        - Initializes start wall-clock time and empty _results mapping.
        - Loops while _scheduler.is_finished() returns False and retrieves the next wave from _scheduler.next_wave().
        - Halts wave loop when next wave is empty.
        - Dispatches each ready wave node sequentially, marking it RUNNING in _scheduler.
        - Executes node action with retry attempts up to definition.retries upon exception.
        - Records dag_engine_lite.NodeResult(SUCCEEDED) and marks SUCCEEDED in _scheduler on success.
        - Records dag_engine_lite.NodeResult(FAILED) and marks FAILED in _scheduler with failure_policy on failure after retries.
        - Halts further wave execution when failure_policy is FAIL_FAST and a node has failed.
        - Populates _results with default unexecuted dag_engine_lite.NodeResult records for terminal skipped or cancelled nodes from _scheduler states.
        - Computes critical path using _dag.compute_critical_path().
        - Gathers succeeded, failed, skipped, and cancelled node tuples from _results and _scheduler states.
        - Returns consolidated dag_engine_lite.DAGRunReport.
        """
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        # MUST validate graph invariants before commencing wave execution.
        dag.validate()
        start_time = time.monotonic()
        self._results = {}
        halted = False
        # MUST execute ready waves sequentially until the scheduler is finished.
        while not halted and not scheduler.is_finished():
            wave = scheduler.next_wave()
            # Halts the wave loop when no further nodes are ready.
            if not wave:
                break  # pragma: no cover (assumption: an unfinished scheduler always yields a non-empty ready wave)
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                attempt_start = time.monotonic()
                retries_attempted = 0
                value: Any = None
                error: Optional[Exception] = None
                succeeded = False
                for attempt in range(definition.retries + 1):
                    try:
                        value = definition.action()
                        succeeded = True
                        break
                    # cleanroom: allow-broad-exception - failure is reified into NodeResult.error
                    except Exception as exc:
                        error = exc
                        retries_attempted = attempt
                duration_seconds = time.monotonic() - attempt_start
                if succeeded:
                    # Success: record SUCCEEDED outcome and unlock dependents.
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    # Failure: record FAILED outcome and apply the failure policy.
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        # Halt further wave execution on the first failure.
                        halted = True
                        break
        wall_clock_seconds = time.monotonic() - start_time
        # Populate default result records for nodes never dispatched.
        states = scheduler.get_all_states()
        for node_id in dag.all_nodes():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=states.get(node_id, dag_engine_lite.NodeState.PENDING),
                )
        # MUST capture the critical path of the executed graph.
        critical_path, _ = dag.compute_critical_path()
        # Gather outcome tuples from the consolidated results mapping.
        succeeded_nodes: List[str] = []
        failed_nodes: List[str] = []
        skipped_nodes: List[str] = []
        cancelled_nodes: List[str] = []
        for node_id, result in self._results.items():
            if result.state is dag_engine_lite.NodeState.SUCCEEDED:
                succeeded_nodes.append(node_id)
            elif result.state is dag_engine_lite.NodeState.FAILED:
                failed_nodes.append(node_id)
            elif result.state is dag_engine_lite.NodeState.SKIPPED:
                skipped_nodes.append(node_id)
            elif result.state is dag_engine_lite.NodeState.CANCELLED:
                cancelled_nodes.append(node_id)
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=tuple(succeeded_nodes),
            failed_nodes=tuple(failed_nodes),
            skipped_nodes=tuple(skipped_nodes),
            cancelled_nodes=tuple(cancelled_nodes),
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
# LAST_CLEANED: 2026-11-03T00:59:15Z
# LAST_CHANGED: 2026-11-03T00:58:51Z
# CHANGE: Resolve coverage feedback on unreachable defensive branches: drop the missing-dependency skip in the private cycle-detection helper (both contracted entry points already raise NodeNotFoundError before cycle detection), restructure the transitive blocked-dependent traversal to seed the blocked set up front and discover each dependent exactly once, removing the duplicate-visit skip, and annotate the empty-wave halt with '# pragma: no cover (assumption: an unfinished scheduler always yields a non-empty ready wave)' since completion reporting guarantees ready nodes remain. No functional behavior change; verified static checks plus runtime smoke tests for cycles, missing dependencies, diamond skip-downstream/continue policies, and retries.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T00:59:15Z
# PRETENSE_QA_AUDIT: 2026-11-03T00:59:04Z
# --- END AUTOFAB METADATA ---
