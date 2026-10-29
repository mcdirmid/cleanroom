# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_021843_qwen-moe_dag_engine_lite_pretense
# Timestamp: 2026-10-29T02:18:43.824339+00:00
# Benchmark Task: dag_engine_lite
# Model: qwen-moe (Tier 1)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 3,164,942
#   Cached Inbound Tokens:   39,997,754
#   Outbound Tokens:         680,270
#   Total Tokens:            43,842,966
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     11845.74s
#   Step Latencies (s):      [409.7, 523.2, 1031.5, 113.1, 265.6, 184.0, 143.0, 61.3, 61.3, 132.8, 30.6, 102.0, 296.7, 82.0, 51.2, 122.9, 92.3, 20.3, 71.4, 102.1, 30.7, 40.9, 296.2, 81.5, 214.4, 102.0, 81.8, 40.8, 71.4, 30.7, 41.0, 163.3, 30.6, 91.9, 367.9, 173.7, 92.0, 30.8, 41.0, 255.3, 398.2, 51.2, 102.4, 133.1, 40.8, 296.1, 20.4, 51.1, 357.5, 30.7, 71.6, 582.3, 30.8, 50.9, 2655.7, 61.5, 91.8, 275.8, 30.6, 112.5, 408.6, 61.2, 153.5, 296.6, 20.4, 174.0, 185.4, 205.8, 30.8, 30.6]
#   Role Execution Rounds:   lib: 3, pretense: 26, pretense_coverage: 15, pretense_qa: 26 (Total: 70)
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
from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
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

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str

    def __str__(self) -> str:
        return self.message


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

    def __str__(self) -> str:
        return self.message


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
        - MUST defer missing dependency existence checks to validate() and topological_sort() without eagerly raising NodeNotFoundError.
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
        - MUST break ties between concurrent ready nodes using priority descending and lexicographical node_id ascending.
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
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        Args:
            failure_policy: Failure policy applied upon node action failure. Defaults to FAIL_FAST.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        Raises:
            NodeNotFoundError: When graph validation detects referenced dependencies not present in the graph.
            CycleError: When graph validation detects directed cycles in the graph.

        POSTCONDITIONS:
        - MUST validate graph invariants before commencing wave execution.
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:27:08Z
# LAST_CHANGED: 2026-10-29T02:27:08Z
# CHANGE: Implemented interface module: data types (DAGError, CycleError, NodeNotFoundError, NodeExecutionError, NodeDefinition, NodeResult, DAGRunReport), enums (NodeState, FailurePolicy), and protocol stubs (DAG, WaveScheduler, DAGRunner) with full POSTCONDITIONS and docstrings per low/dag_engine_lite.pyi specification.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations

from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
import heapq
from . import dag_engine_lite
from .dag_engine_lite import (
    DAGError,
    DAGRunReport,
    CycleError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream.
    """

    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeDefinition[Any]] = {}
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
        dep_set = frozenset(dependencies) if dependencies else frozenset()
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dep_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        # Register empty neighbor sets if absent
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()
        # Add directed edges from each dependency to node_id
        if dependencies:
            for dep_id in dependencies:
                if dep_id not in self._upstream:
                    self._upstream[dep_id] = set()
                if dep_id not in self._downstream:
                    self._downstream[dep_id] = set()
                self._upstream[node_id].add(dep_id)
                self._downstream[dep_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # POSTCONDITION: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node '{upstream_id}' not found in DAG", node_id=upstream_id
            )
        if downstream_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node '{downstream_id}' not found in DAG", node_id=downstream_id
            )
        # POSTCONDITION: MUST establish a directed dependency edge.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG", node_id=node_id
            )
        # Remove all incident edges
        for dep_id in list(self._upstream.get(node_id, set())):
            self._downstream[dep_id].discard(node_id)
        for dependent_id in list(self._downstream.get(node_id, set())):
            self._upstream[dependent_id].discard(node_id)
        # Delete node from all maps
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG", node_id=node_id
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG", node_id=node_id
            )
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG", node_id=node_id
            )
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
            for dep_id in definition.dependencies:
                if dep_id not in self._nodes:
                    raise NodeNotFoundError(
                        message=f"Missing dependency '{dep_id}' for node '{node_id}'",
                        node_id=dep_id,
                    )
        # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError.
        cycle = self._detect_cycle()
        if cycle is not None:
            raise CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=tuple(cycle),
            )

    def _detect_cycle(self) -> Optional[List[str]]:
        """Depth-first search cycle detection with active recursion path tracking."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {node_id: WHITE for node_id in self._nodes}
        parent: Dict[str, Optional[str]] = {node_id: None for node_id in self._nodes}

        def dfs(node_id: str) -> Optional[List[str]]:
            color[node_id] = GRAY
            for dependent_id in self._downstream.get(node_id, set()):
                if color[dependent_id] == GRAY:
                    # Found cycle: backtrack to reconstruct cycle path
                    cycle = [dependent_id, node_id]
                    current = node_id
                    while current != dependent_id:
                        current = parent.get(current)
                        if current is None or current == dependent_id:
                            break
                        cycle.append(current)
                    cycle.reverse()
                    return cycle
                if color[dependent_id] == WHITE:
                    parent[dependent_id] = node_id
                    result = dfs(dependent_id)
                    if result is not None:
                        return result
            color[node_id] = BLACK
            return None

        for node_id in self._nodes:
            if color[node_id] == WHITE:
                result = dfs(node_id)
                if result is not None:
                    return result
        return None

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError.
        validate_cycle = self._detect_cycle()
        if validate_cycle is not None:
            raise CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(validate_cycle)}",
                cycle=tuple(validate_cycle),
            )

        # Compute in-degree counts from _upstream mapping
        in_degree: Dict[str, int] = {node_id: 0 for node_id in self._nodes}
        for node_id in self._nodes:
            in_degree[node_id] = len(
                [d for d in self._upstream.get(node_id, set()) if d in self._nodes]
            )

        # Initialize ready list with zero in-degree nodes, sorted by priority desc then node_id asc
        heap: List[Tuple[int, str]] = []
        for node_id in self._nodes:
            if in_degree[node_id] == 0:
                heapq.heappush(heap, (-self._nodes[node_id].priority, node_id))

        order: List[str] = []
        while heap:
            neg_pri, node_id = heapq.heappop(heap)
            order.append(node_id)
            # Decrement downstream in-degrees
            for dependent_id in self._downstream.get(node_id, set()):
                if dependent_id in self._nodes:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        heapq.heappush(
                            heap,
                            (-self._nodes[dependent_id].priority, dependent_id),
                        )

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id)
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not self._downstream.get(node_id)
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # POSTCONDITION: MUST return the longest path through the DAG.
        # POSTCONDITION: MUST return the cumulative weight of that path.
        if not self._nodes:
            return ([], 0.0)

        durations = estimated_durations or {}
        topo_order = self.topological_sort()

        # earliest completion time using dynamic programming
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for node_id in topo_order:
            duration = durations.get(node_id, 1.0)
            upstream_deps = [
                d
                for d in self._upstream.get(node_id, set())
                if d in earliest
            ]
            if upstream_deps:
                best_pred = max(upstream_deps, key=lambda d: earliest[d])
                earliest[node_id] = earliest[best_pred] + duration
                predecessor[node_id] = best_pred
            else:
                earliest[node_id] = duration
                predecessor[node_id] = None

        # Identify terminal node with maximum completion time
        terminal = max(earliest, key=lambda n: earliest[n])
        total_weight = earliest[terminal]

        # Backtrack through predecessors
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()

        return (path, total_weight)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: DAG = get_singleton(DAG)
        self._states: Dict[str, NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronize _states with all nodes from _dag, initializing new nodes."""
        all_node_ids = self._dag.all_nodes()
        for node_id in all_node_ids:
            if node_id not in self._states:
                deps = self._dag.get_dependencies(node_id)
                # Initialize root nodes to READY, non-root nodes to PENDING
                if not deps:
                    self._states[node_id] = NodeState.READY
                else:
                    self._states[node_id] = NodeState.PENDING
        # Remove states for nodes no longer in the DAG
        for stale_id in list(self._states.keys()):
            if stale_id not in all_node_ids:
                del self._states[stale_id]

    @operation
    @override
    def next_wave(self) -> List[str]:
        # POSTCONDITION: MUST return all READY nodes whose upstream deps are SUCCEEDED.
        # POSTCONDITION: MUST order by priority descending, then node_id ascending.
        self._sync_states()
        candidates = []
        for node_id, state in self._states.items():
            if state != NodeState.READY:
                continue
            # Check all upstream deps are SUCCEEDED
            deps = self._dag.get_dependencies(node_id)
            if all(self._states.get(d) == NodeState.SUCCEEDED for d in deps):
                candidates.append(node_id)
        # Sort by priority descending, then node_id ascending
        candidates.sort(
            key=lambda nid: (-self._dag.get_node(nid).priority, nid)
        )
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # POSTCONDITION: MUST update the node state to RUNNING.
        self._states[node_id] = NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        # POSTCONDITION: MUST update the node state to SUCCEEDED.
        self._states[node_id] = NodeState.SUCCEEDED
        # MUST evaluate downstream dependents and promote newly unblocked nodes to READY
        dependents = self._dag.get_dependents(node_id)
        for dep_id in dependents:
            if self._states.get(dep_id) == NodeState.PENDING:
                all_deps_succeeded = all(
                    self._states.get(d) == NodeState.SUCCEEDED
                    for d in self._dag.get_dependencies(dep_id)
                )
                if all_deps_succeeded:
                    self._states[dep_id] = NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> None:
        # POSTCONDITION: MUST update the node state to FAILED.
        self._states[node_id] = NodeState.FAILED

        if failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            # MUST transition all transitive dependents to SKIPPED.
            self._mark_transitive_skipped(node_id)
        elif failure_policy == FailurePolicy.CONTINUE_ON_ERROR:
            # MUST leave unblocked independent nodes eligible for execution.
            # MUST transition blocked dependents of failed nodes to SKIPPED.
            self._mark_continue_on_error_skipped()
        elif failure_policy == FailurePolicy.FAIL_FAST:
            # MUST transition all remaining non-terminal nodes to CANCELLED.
            for nid, state in self._states.items():
                if state not in (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED):
                    self._states[nid] = NodeState.CANCELLED

    def _mark_transitive_skipped(self, failed_node_id: str) -> None:
        """Mark all transitive dependents of a failed node as SKIPPED."""
        to_visit = [failed_node_id]
        visited = set()
        while to_visit:
            current = to_visit.pop()
            visited.add(current)
            dependents = self._dag.get_dependents(current)
            for dep_id in dependents:
                if self._states.get(dep_id) not in (
                    NodeState.SUCCEEDED,
                    NodeState.FAILED,
                    NodeState.SKIPPED,
                    NodeState.CANCELLED,
                ):
                    self._states[dep_id] = NodeState.SKIPPED
                    to_visit.append(dep_id)

    def _mark_continue_on_error_skipped(self) -> None:
        """For CONTINUE_ON_ERROR: mark blocked dependents as SKIPPED, leave independent nodes."""
        failed_nodes = {
            nid
            for nid, state in self._states.items()
            if state == NodeState.FAILED
        }
        # Find all nodes reachable from failed nodes
        reachable_from_failed: Set[str] = set()
        to_visit = list(failed_nodes)
        visited = set()
        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue
            visited.add(current)
            dependents = self._dag.get_dependents(current)
            for dep_id in dependents:
                reachable_from_failed.add(dep_id)
                to_visit.append(dep_id)
        # Mark non-terminal reachable nodes as SKIPPED
        for nid in reachable_from_failed:
            if self._states.get(nid) not in (
                NodeState.SUCCEEDED,
                NodeState.FAILED,
                NodeState.SKIPPED,
                NodeState.CANCELLED,
            ):
                self._states[nid] = NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        # WHEN the DAG contains no nodes, MUST return True.
        # MUST synchronize states first.
        self._sync_states()
        if not self._states:
            return True
        terminal_states = {
            NodeState.SUCCEEDED,
            NodeState.FAILED,
            NodeState.SKIPPED,
            NodeState.CANCELLED,
        }
        return all(state in terminal_states for state in self._states.values())

    @operation
    @override
    def get_state(self, node_id: str) -> NodeState:
        # Ensures _states contains node_id by synchronizing if absent.
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, NodeState]:
        # Ensures _states contains all nodes from _dag.all_nodes().
        self._sync_states()
        all_node_ids = self._dag.all_nodes()
        return dict(
            (nid, state)
            for nid, state in self._states.items()
            if nid in all_node_ids
        )


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG via get_singleton(dag_engine_lite.DAG) and WaveScheduler via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: DAG = get_singleton(DAG)
        self._scheduler: WaveScheduler = get_singleton(WaveScheduler)
        self._results: Dict[str, NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        # MUST validate graph invariants before commencing wave execution.
        self._dag.validate()

        import time

        start_time = time.time()
        self._results = {}

        # Execute waves sequentially
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break

            for node_id in wave:
                definition = self._dag.get_node(node_id)
                # Mark running
                self._scheduler.mark_running(node_id)

                retries_attempted = 0
                max_retries = definition.retries
                last_exception: Optional[Exception] = None
                result: Optional[NodeResult[Any]] = None

                # Execute with retries
                while True:
                    try:
                        node_start = time.time()
                        value = definition.action()
                        node_end = time.time()
                        duration = node_end - node_start

                        result = NodeResult(
                            node_id=node_id,
                            state=NodeState.SUCCEEDED,
                            value=value,
                            error=None,
                            duration_seconds=duration,
                            retries_attempted=retries_attempted,
                        )
                        self._scheduler.mark_succeeded(node_id)
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_exception = exc
                        retries_attempted += 1
                        if retries_attempted > max_retries:
                            break
                        # Retry: reset to READY for re-execution
                        # The scheduler will re-include it in next next_wave call

                if result is None:
                    # All retries exhausted
                    node_end = time.time()
                    duration = node_end - start_time
                    result = NodeResult(
                        node_id=node_id,
                        state=NodeState.FAILED,
                        value=None,
                        error=last_exception,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_failed(
                        node_id, failure_policy=failure_policy
                    )

                self._results[node_id] = result

                # POSTCONDITION: Halts further wave execution on FAIL_FAST failure.
                if failure_policy == FailurePolicy.FAIL_FAST and result.state == NodeState.FAILED:
                    break

        end_time = time.time()
        wall_clock = end_time - start_time

        # Populate unexecuted terminal nodes
        all_states = self._scheduler.get_all_states()
        all_node_ids = self._dag.all_nodes()
        for nid in all_node_ids:
            if nid not in self._results:
                state = all_states.get(nid, NodeState.PENDING)
                self._results[nid] = NodeResult(
                    node_id=nid,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        # Compute critical path
        critical_path_list, critical_path_weight = self._dag.compute_critical_path()

        # Gather node tuples
        succeeded = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == NodeState.SUCCEEDED
        )
        failed = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == NodeState.FAILED
        )
        skipped = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == NodeState.SKIPPED
        )
        cancelled = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == NodeState.CANCELLED
        )

        report = DAGRunReport(
            total_nodes=len(all_node_ids),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(critical_path_list),
            results=self._results,
        )

        return report


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
# LAST_CLEANED: 2026-10-29T05:36:00Z
# LAST_CHANGED: 2026-10-29T05:35:16Z
# CHANGE: Removed 5 unreachable defensive checks: (1) stale _downstream membership guard in _detect_cycle DFS, (2) redundant CycleError fallback in topological_sort (already guarded by _detect_cycle), (3) empty-earliest return guard in compute_critical_path (already handled by empty-graph check + DP loop), (4) visited-cycle guard in _mark_transitive_skipped (acyclic graph guarantee), (5) empty-failed-nodes guard in _mark_continue_on_error_skipped (mark_failed always sets node to FAILED first).
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T05:36:00Z
# PRETENSE_QA_AUDIT: 2026-10-29T05:35:34Z
# --- END CLEANROOM METADATA ---
