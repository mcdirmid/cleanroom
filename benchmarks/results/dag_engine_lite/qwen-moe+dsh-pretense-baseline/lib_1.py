# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_220102_qwen-moe_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-26T22:01:02.416090+00:00
# Benchmark Task: dag_engine_lite
# Model: qwen-moe (Tier 1)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 315,640
#   Cached Inbound Tokens:   6,331,641
#   Outbound Tokens:         72,039
#   Total Tokens:            6,719,320
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     1151.54s
#   Step Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       92
#   Unit Tests Failed:       0
#   Line Coverage:           98.0%
#   Branch Coverage:         98.0%
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


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier, get_singleton, LifecycleRegistry
from . import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """

    tier = SystemTier("system")

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
        deps = frozenset(dependencies) if dependencies else frozenset()
        defn = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = defn
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()
        for dep_id in deps:
            if dep_id not in self._upstream:
                self._upstream[dep_id] = set()
            if dep_id not in self._downstream:
                self._downstream[dep_id] = set()
            self._upstream[node_id].add(dep_id)
            self._downstream[dep_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found",
                node_id=downstream_id,
            )
        if downstream_id not in self._upstream:
            self._upstream[downstream_id] = set()
        if upstream_id not in self._downstream:
            self._downstream[upstream_id] = set()
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        # Also update the node definition's dependencies
        node_def = self._nodes[downstream_id]
        new_deps = frozenset(self._upstream[downstream_id])
        if new_deps != node_def.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=downstream_id,
                action=node_def.action,
                dependencies=new_deps,
                priority=node_def.priority,
                retries=node_def.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found",
                node_id=node_id,
            )
        # Remove from all upstream sets
        for dep_id in list(self._upstream.get(node_id, set())):
            if dep_id in self._downstream:
                self._downstream[dep_id].discard(node_id)
        # Remove from all downstream sets
        for dependent_id in list(self._downstream.get(node_id, set())):
            if dependent_id in self._upstream:
                self._upstream[dependent_id].discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

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
                message=f"Node '{node_id}' not found",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found",
                node_id=node_id,
            )
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
        # Check all dependencies exist
        for node_id, defn in self._nodes.items():
            for dep_id in defn.dependencies:
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Node '{node_id}' depends on missing node '{dep_id}'",
                        node_id=dep_id,
                    )
        # Cycle detection via DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self._nodes}
        parent_map: Dict[str, Optional[str]] = {n: None for n in self._nodes}

        def _dfs(node: str, path: List[str]) -> None:
            color[node] = GRAY
            path.append(node)
            for dep in self._downstream.get(node, set()):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    # Found a cycle - extract it
                    cycle_start = path.index(dep)
                    cycle = tuple(path[cycle_start:])
                    raise dag_engine_lite.CycleError(
                        message=f"Cycle detected: {' -> '.join(cycle)}",
                        cycle=cycle,
                    )
                if color[dep] == WHITE:
                    _dfs(dep, path)
            path.pop()
            color[node] = BLACK

        for node in sorted(self._nodes.keys()):
            if color[node] == WHITE:
                _dfs(node, [])

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        self.validate()  # Also checks for cycles

        # Compute in-degrees
        in_degree: Dict[str, int] = {n: 0 for n in self._nodes}
        for node_id in self._nodes:
            for dep in self._upstream.get(node_id, set()):
                if dep in in_degree:
                    in_degree[node_id] = in_degree.get(node_id, 0) + 1  # type: ignore[assignment]
        # Recalculate properly
        in_degree = {n: 0 for n in self._nodes}
        for node_id in self._nodes:
            for dep in self._upstream.get(node_id, set()):
                if dep in self._nodes:
                    in_degree[node_id] += 1

        # Use a list of candidates sorted by priority desc, node_id asc
        ready: List[str] = []
        for node_id in self._nodes:
            if in_degree[node_id] == 0:
                ready.append(node_id)

        def sort_key(nid: str) -> Tuple[int, str]:
            return (-self._nodes[nid].priority, nid)

        ready.sort(key=sort_key)

        result: List[str] = []
        while ready:
            # Pick the first (highest priority, then alphabetically first)
            node = ready.pop(0)
            result.append(node)
            # Process dependents
            new_ready: List[str] = []
            for dependent in self._downstream.get(node, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        new_ready.append(dependent)
            if new_ready:
                ready.extend(new_ready)
                ready.sort(key=sort_key)

        if len(result) != len(self._nodes):
            # Should not happen after validate(), but just in case
            remaining = set(self._nodes.keys()) - set(result)
            cycle = tuple(sorted(remaining))
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected in DAG",
                cycle=cycle,
            )

        return result

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {nid for nid in self._nodes if not self._upstream.get(nid)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {nid for nid in self._nodes if not self._downstream.get(nid)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        topo_order = self.topological_sort()
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            durations[nid] = estimated_durations.get(nid, 1.0) if estimated_durations else 1.0

        # Earliest completion time
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for nid in topo_order:
            upstream = self._upstream.get(nid, set()) & set(self._nodes.keys())
            if upstream:
                best_pred = max(upstream, key=lambda p: earliest.get(p, 0.0))
                earliest[nid] = earliest.get(best_pred, 0.0) + durations[nid]
                predecessor[nid] = best_pred
            else:
                earliest[nid] = durations[nid]
                predecessor[nid] = None

        if not earliest:
            return ([], 0.0)

        # Find the terminal node with max completion time
        terminal = max(earliest, key=lambda n: earliest[n])
        total = earliest[terminal]

        # Backtrack
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor.get(current)
        path.reverse()

        return (path, total)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = SystemTier("system")

    def __init__(self) -> None:
        self._dag: Any = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronizes _states with all nodes currently registered in _dag."""
        current_nodes = self._dag.all_nodes()
        # Remove stale entries for removed nodes
        stale = set(self._states.keys()) - current_nodes
        for sid in stale:
            del self._states[sid]
        # Add new nodes
        for nid in current_nodes:
            if nid not in self._states:
                deps = self._dag.get_dependencies(nid)
                # Check if all deps are in the graph
                all_deps_exist = all(d in current_nodes for d in deps)
                if all_deps_exist and not deps:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        candidates = []
        for nid, state in self._states.items():
            if state != dag_engine_lite.NodeState.READY:
                continue
            deps = self._dag.get_dependencies(nid)
            all_succeeded = all(
                self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                for d in deps
            )
            if all_succeeded:
                candidates.append(nid)
        # Sort by priority descending, then node_id ascending
        def sort_key(nid: str) -> Tuple[int, str]:
            try:
                p = self._dag.get_node(nid).priority
            except Exception:
                p = 0
            return (-p, nid)
        candidates.sort(key=sort_key)
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Check downstream dependents
        for dependent in self._dag.get_dependents(node_id):
            if dependent in self._states and self._states[dependent] == dag_engine_lite.NodeState.PENDING:
                deps = self._dag.get_dependencies(dependent)
                all_succeeded = all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                )
                if all_succeeded:
                    self._states[dependent] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Cancel all remaining non-terminal nodes
            for nid in list(self._states.keys()):
                if self._states[nid] in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED

        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # Skip all transitive dependents
            to_skip = self._transitive_dependents(node_id)
            for sid in to_skip:
                if self._states.get(sid) not in (
                    dag_engine_lite.NodeState.SUCCEEDED,
                    dag_engine_lite.NodeState.FAILED,
                ):
                    self._states[sid] = dag_engine_lite.NodeState.SKIPPED

        elif failure_policy == dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            # Find blocked dependents of failed nodes and skip them
            # Keep independent nodes eligible
            failed_nodes = {nid for nid, st in self._states.items() if st == dag_engine_lite.NodeState.FAILED}
            for nid in list(self._states.keys()):
                if self._states[nid] in (dag_engine_lite.NodeState.SUCCEEDED, dag_engine_lite.NodeState.FAILED, dag_engine_lite.NodeState.SKIPPED):
                    continue
                deps = self._dag.get_dependencies(nid)
                any_failed = any(d in failed_nodes for d in deps)
                if any_failed:
                    self._states[nid] = dag_engine_lite.NodeState.SKIPPED

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        """Returns all transitive downstream dependents of a node."""
        visited: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            for dep in self._dag.get_dependents(current):
                if dep not in visited:
                    visited.add(dep)
                    queue.append(dep)
        return visited

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        terminal_states = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        if not self._states:
            return True
        return all(s in terminal_states for s in self._states.values())

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        current_nodes = self._dag.all_nodes()
        return {nid: st for nid, st in self._states.items() if nid in current_nodes}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = SystemTier("system")

    def __init__(self) -> None:
        self._dag: Any = get_singleton(dag_engine_lite.DAG)
        self._scheduler: Any = get_singleton(dag_engine_lite.WaveScheduler)

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        # Validate first
        self._dag.validate()

        start_time = time.monotonic()
        results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}
        halted = False

        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                # No more waves but not finished - break
                break

            for node_id in wave:
                if halted:
                    break

                self._scheduler.mark_running(node_id)
                node_def = self._dag.get_node(node_id)
                retries_attempted = 0
                max_retries = node_def.retries
                success = False
                caught_error: Optional[Exception] = None

                while retries_attempted <= max_retries:
                    try:
                        result_value = node_def.action()
                        elapsed = time.monotonic() - start_time
                        results[node_id] = dag_engine_lite.NodeResult(
                            node_id=node_id,
                            state=dag_engine_lite.NodeState.SUCCEEDED,
                            value=result_value,
                            duration_seconds=elapsed,
                            retries_attempted=retries_attempted,
                        )
                        self._scheduler.mark_succeeded(node_id)
                        success = True
                        break
                    except Exception as exc:
                        caught_error = exc
                        retries_attempted += 1
                        if retries_attempted <= max_retries:
                            continue
                        # All retries exhausted
                        elapsed = time.monotonic() - start_time
                        results[node_id] = dag_engine_lite.NodeResult(
                            node_id=node_id,
                            state=dag_engine_lite.NodeState.FAILED,
                            error=exc,
                            duration_seconds=elapsed,
                            retries_attempted=retries_attempted - 1,
                        )
                        self._scheduler.mark_failed(node_id, failure_policy=failure_policy)
                        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                            halted = True
                        break

                if not success:
                    # Already recorded result above
                    pass

        # Record default results for any unexecuted terminal nodes
        all_states = self._scheduler.get_all_states()
        for nid in all_states:
            if nid not in results:
                st = all_states[nid]
                results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=st,
                    duration_seconds=time.monotonic() - start_time,
                )

        elapsed = time.monotonic() - start_time

        # Compute critical path
        critical_path_list, critical_path_weight = self._dag.compute_critical_path()

        succeeded = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.SUCCEEDED)
        failed = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.FAILED)
        skipped = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.SKIPPED)
        cancelled = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.CANCELLED)

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(results),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path_list),
            results=results,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: LifecycleRegistry | None = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    from support.lib.lifecycle import get_default_registry, system
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
