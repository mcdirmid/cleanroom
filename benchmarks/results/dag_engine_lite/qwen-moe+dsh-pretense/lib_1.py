# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_185319_qwen-moe_dag_engine_lite_pretense
# Timestamp: 2026-10-26T18:53:19.632377+00:00
# Benchmark Task: dag_engine_lite
# Model: qwen-moe (Tier 1)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 629,477
#   Cached Inbound Tokens:   10,108,804
#   Outbound Tokens:         120,691
#   Total Tokens:            10,858,972
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     2545.93s
#   Step Latencies (s):      [543.1, 694.0, 140.5, 60.2, 30.1, 200.8, 191.2, 201.6, 110.6, 60.2, 30.1, 110.4, 50.3, 80.2, 341.0, 40.1, 60.2, 50.1, 70.2, 100.3, 50.1, 30.1, 30.1]
#   Role Execution Rounds:   lib: 6, pretense: 4, pretense_coverage: 5, pretense_qa: 8 (Total: 23)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       57
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
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

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass(frozen=True)
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T19:18:05Z
# LAST_CHANGED: 2026-10-26T19:18:05Z
# CHANGE: Added __str__ methods to DAGError, CycleError, NodeNotFoundError, and NodeExecutionError to fix empty str() representation caused by frozen dataclass fields not populating Exception.args.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier, get_singleton
from . import dag_engine_lite
from .dag_engine_lite import (
    DAGError,
    CycleError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    DAGRunReport,
)

# Aliases for auto-generated __initialize__ registry keys
_DAGProtocol = dag_engine_lite.DAG
_WaveSchedulerProtocol = dag_engine_lite.WaveScheduler
_DAGRunnerProtocol = dag_engine_lite.DAGRunner


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

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
        # Postcondition: MUST register the node definition into the graph.
        frozen_deps = frozenset(dependencies) if dependencies else frozenset()
        self._nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_deps,
            priority=priority,
            retries=retries,
        )
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # Postcondition: WHEN dependencies are provided, MUST add directed dependency edges.
        if dependencies:
            for dep in dependencies:
                self._upstream.setdefault(dep, set())
                self._downstream.setdefault(dep, set())
                self._upstream[node_id].add(dep)
                self._downstream[dep].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Postcondition: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes or downstream_id not in self._nodes:
            missing = []
            if upstream_id not in self._nodes:
                missing.append(upstream_id)
            if downstream_id not in self._nodes:
                missing.append(downstream_id)
            raise NodeNotFoundError(
                message=f"Node(s) not found: {', '.join(missing)}",
                node_id=missing[0],
            )
        # Postcondition: MUST establish a directed dependency edge.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # Postcondition: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # Postcondition: MUST remove the node and its incident edges.
        for dep in self._upstream.get(node_id, set()):
            self._downstream[dep].discard(node_id)
        for dependent in self._downstream.get(node_id, set()):
            self._upstream[dependent].discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        # Postcondition: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # Postcondition: MUST return the NodeDefinition matching node_id.
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # Postcondition: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # Postcondition: MUST return all direct upstream dependencies.
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # Postcondition: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # Postcondition: MUST return all direct downstream dependents.
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Postcondition: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for node_id, definition in self._nodes.items():
            for dep_id in definition.dependencies:
                if dep_id not in self._nodes:
                    raise NodeNotFoundError(
                        message=f"Node '{node_id}' references missing dependency '{dep_id}'",
                        node_id=dep_id,
                    )
        # Postcondition: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._detect_cycle()
        if cycle is not None:
            raise CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=tuple(cycle),
            )

    def _detect_cycle(self) -> Optional[List[str]]:
        """Depth-first search cycle detection tracking active recursion path."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self._nodes}
        path: List[str] = []

        def dfs(node_id: str) -> Optional[List[str]]:
            color[node_id] = GRAY
            path.append(node_id)
            for dep in self._upstream.get(node_id, set()):
                if color.get(dep, WHITE) == GRAY:
                    cycle_start = path.index(dep)
                    return path[cycle_start:] + [dep]
                if color.get(dep, WHITE) == WHITE:
                    result = dfs(dep)
                    if result is not None:
                        return result
            path.pop()
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
        # Postcondition: WHEN a cycle exists, MUST raise CycleError.
        self.validate()

        # Compute in-degree counts from _upstream mapping.
        in_degree: Dict[str, int] = {n: 0 for n in self._nodes}
        for node_id in self._nodes:
            in_degree[node_id] = len(self._upstream.get(node_id, set()))

        # Initialize ready list with in-degree zero nodes, sorted by priority desc, name asc.
        ready: List[str] = []
        for node_id in self._nodes:
            if in_degree[node_id] == 0:
                ready.append(node_id)
        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        order: List[str] = []
        while ready:
            # Extract candidate with highest priority (first in sorted list).
            candidate = ready.pop(0)
            order.append(candidate)
            # Decrement downstream in-degrees.
            for dependent in self._downstream.get(candidate, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    # Insert maintaining priority descending then node_id ascending.
                    ready.append(dependent)
                    ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        # Postcondition: Returns node identifiers whose _upstream set is empty.
        return {nid for nid in self._nodes if not self._upstream.get(nid)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        # Postcondition: Returns node identifiers whose _downstream set is empty.
        return {nid for nid in self._nodes if not self._downstream.get(nid)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # Postcondition: MUST return the sequence of nodes that forms the longest path.
        topo_order = self.topological_sort()
        durations = estimated_durations or {}

        # Earliest completion time using DP.
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for node_id in topo_order:
            duration = durations.get(node_id, 1.0)
            upstream_deps = self._upstream.get(node_id, set())
            if not upstream_deps:
                earliest[node_id] = duration
                predecessor[node_id] = None
            else:
                best_pred = None
                best_time = 0.0
                for p in upstream_deps:
                    if earliest.get(p, 0.0) > best_time:
                        best_time = earliest[p]
                        best_pred = p
                earliest[node_id] = best_time + duration
                predecessor[node_id] = best_pred

        # Identify terminal node with maximum completion time.
        if not earliest:
            return ([], 0.0)

        terminal = max(earliest, key=lambda n: earliest[n])
        total_weight = earliest[terminal]

        # Backtrack through predecessors to build path.
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()

        return (path, total_weight)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._dag: DAG = get_singleton(DAG)
        self._states: Dict[str, NodeState] = {}

    def _synchronize(self) -> None:
        """Ensure _states contains all nodes from _dag, initializing as needed."""
        for nid in self._dag.all_nodes():
            if nid not in self._states:
                deps = self._dag.get_dependencies(nid)
                if not deps:
                    self._states[nid] = NodeState.READY
                else:
                    self._states[nid] = NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        # GROUNDING: Ensures _states contains all nodes.
        self._synchronize()

        # Postcondition: MUST return all nodes in READY state whose upstream deps are SUCCEEDED.
        wave: List[str] = []
        for nid, state in self._states.items():
            if state != NodeState.READY:
                continue
            deps = self._dag.get_dependencies(nid)
            if all(self._states.get(d) == NodeState.SUCCEEDED for d in deps):
                wave.append(nid)

        # Postcondition: MUST order by priority descending, then node_id ascending.
        wave.sort(key=lambda nid: (-self._dag.get_node(nid).priority, nid))
        return wave

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # Postcondition: MUST update node state to RUNNING.
        self._synchronize()
        self._states[node_id] = NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        # Postcondition: MUST update node state to SUCCEEDED.
        self._synchronize()
        self._states[node_id] = NodeState.SUCCEEDED

        # Postcondition: MUST evaluate downstream dependents and promote unblocked to READY.
        dependents = self._dag.get_dependents(node_id)
        for dep_id in dependents:
            if self._states.get(dep_id) == NodeState.PENDING:
                deps = self._dag.get_dependencies(dep_id)
                if all(self._states.get(d) == NodeState.SUCCEEDED for d in deps):
                    self._states[dep_id] = NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> None:
        # Postcondition: MUST update node state to FAILED.
        self._synchronize()
        self._states[node_id] = NodeState.FAILED

        if failure_policy == FailurePolicy.FAIL_FAST:
            # Postcondition: MUST transition all remaining PENDING nodes to CANCELLED.
            for nid in list(self._states.keys()):
                if self._states[nid] in (NodeState.PENDING, NodeState.READY):
                    self._states[nid] = NodeState.CANCELLED
        elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            # Postcondition: MUST transition all transitive dependents to SKIPPED.
            self._skip_dependents(node_id)
        # CONTINUE_ON_ERROR: leave unblocked independent nodes eligible.

    def _skip_dependents(self, node_id: str) -> None:
        """Recursively mark transitive downstream dependents as SKIPPED."""
        dependents = self._dag.get_dependents(node_id)
        for dep_id in dependents:
            if self._states.get(dep_id) in (NodeState.PENDING, NodeState.READY):
                self._states[dep_id] = NodeState.SKIPPED
                self._skip_dependents(dep_id)

    @operation
    @override
    def is_finished(self) -> bool:
        # GROUNDING: Ensures _states contains all nodes.
        self._synchronize()
        # Postcondition: Returns True if all nodes are terminal or DAG is empty.
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
        # GROUNDING: Ensures _states contains node_id.
        self._synchronize()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, NodeState]:
        # GROUNDING: Ensures _states contains all nodes.
        self._synchronize()
        # Postcondition: Returns a shallow copy of _states mapping.
        return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

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
        # GROUNDING: Validates _dag before execution.
        self._dag.validate()

        # GROUNDING: Initializes start time and empty results.
        start_time = time.monotonic()
        self._results = {}

        # GROUNDING: Loops while scheduler is not finished.
        while not self._scheduler.is_finished():
            # GROUNDING: Retrieves next wave.
            wave = self._scheduler.next_wave()
            # Deadlock guard: when unresolvable dependency cycles block progress,
            # no node is READY despite non-terminal nodes remaining.
            if not wave:
                break

            # GROUNDING: Dispatches each ready wave node sequentially.
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                node_result = self._execute_node(node_id, definition, failure_policy)
                self._results[node_id] = node_result

                if node_result.state == NodeState.SUCCEEDED:
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._scheduler.mark_failed(node_id, failure_policy)
                    # GROUNDING: Halts further wave execution on FAIL_FAST failure.
                    if failure_policy == FailurePolicy.FAIL_FAST:
                        break

        # GROUNDING: Populates default results for terminal skipped/cancelled nodes.
        for nid, state in self._scheduler.get_all_states().items():
            if nid not in self._results:
                if state in (NodeState.SKIPPED, NodeState.CANCELLED):
                    self._results[nid] = NodeResult(
                        node_id=nid,
                        state=state,
                    )

        end_time = time.monotonic()

        # GROUNDING: Computes critical path.
        critical_path_nodes, critical_path_weight = self._dag.compute_critical_path()

        # GROUNDING: Gathers result tuples.
        succeeded = tuple(nid for nid, r in self._results.items() if r.state == NodeState.SUCCEEDED)
        failed = tuple(nid for nid, r in self._results.items() if r.state == NodeState.FAILED)
        skipped = tuple(nid for nid, r in self._results.items() if r.state == NodeState.SKIPPED)
        cancelled = tuple(nid for nid, r in self._results.items() if r.state == NodeState.CANCELLED)

        return DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=end_time - start_time,
            critical_path=tuple(critical_path_nodes),
            results=self._results,
        )

    def _execute_node(
        self,
        node_id: str,
        definition: NodeDefinition[Any],
        failure_policy: FailurePolicy,
    ) -> NodeResult[Any]:
        """Execute a single node with retry logic."""
        self._scheduler.mark_running(node_id)
        max_attempts = definition.retries + 1
        last_error: Optional[Exception] = None
        start = time.monotonic()

        for attempt in range(max_attempts):
            try:
                attempt_start = time.monotonic()
                value = definition.action()
                duration = time.monotonic() - attempt_start
                return NodeResult(
                    node_id=node_id,
                    state=NodeState.SUCCEEDED,
                    value=value,
                    duration_seconds=duration,
                    retries_attempted=attempt,
                )
            # cleanroom: allow-broad-exception
            except Exception as exc:
                last_error = exc
                continue

        duration = time.monotonic() - start
        return NodeResult(
            node_id=node_id,
            state=NodeState.FAILED,
            error=last_error,
            duration_seconds=duration,
            retries_attempted=max_attempts - 1,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, DAG, dag_engine_lite.DAG, _DAGProtocol],
        tier=DAG.tier,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, WaveScheduler, dag_engine_lite.WaveScheduler, _WaveSchedulerProtocol],
        tier=WaveScheduler.tier,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, DAGRunner, dag_engine_lite.DAGRunner, _DAGRunnerProtocol],
        tier=DAGRunner.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T19:35:28Z
# LAST_CHANGED: 2026-10-26T19:29:03Z
# CHANGE: Restored empty wave deadlock guard in DAGRunner.run() — hypothesis fuzz test confirmed that nodes with unresolvable dependencies can cause is_finished() to return False while next_wave() returns empty. The guard prevents infinite spin by breaking the loop when no progress is possible.
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T19:35:28Z
# PRETENSE_QA_AUDIT: 2026-10-26T19:35:02Z
# --- END CLEANROOM METADATA ---
