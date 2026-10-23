# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_195828_gemini-4-argon_dag_engine_lite_baseline
# Timestamp: 2026-10-23T19:58:28.643070+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-4-argon (Tier 4)
# Methodology: baseline
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 133,142
#   Cached Inbound Tokens:   1,826,763
#   Outbound Tokens:         19,591
#   Total Tokens:            1,979,496
#   Financial Cost ($USD):   $1.3756
#   Wall Clock Duration:     280.72s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       14
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Synchronous DAG execution and wave scheduling engine."""

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
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)
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
    """Concrete realization of the Directed Acyclic Graph."""

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
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        for dep_id in deps:
            self._upstream[node_id].add(dep_id)
            if dep_id not in self._downstream:
                self._downstream[dep_id] = set()
            self._downstream[dep_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found in DAG.",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found in DAG.",
                node_id=downstream_id,
            )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        old_def = self._nodes[downstream_id]
        if upstream_id not in old_def.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=old_def.node_id,
                action=old_def.action,
                dependencies=old_def.dependencies | {upstream_id},
                priority=old_def.priority,
                retries=old_def.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        for up_id in list(self._upstream.get(node_id, ())):
            if up_id in self._downstream:
                self._downstream[up_id].discard(node_id)
        for down_id in list(self._downstream.get(node_id, ())):
            if down_id in self._upstream:
                self._upstream[down_id].discard(node_id)
            if down_id in self._nodes:
                down_def = self._nodes[down_id]
                if node_id in down_def.dependencies:
                    self._nodes[down_id] = dag_engine_lite.NodeDefinition(
                        node_id=down_def.node_id,
                        action=down_def.action,
                        dependencies=down_def.dependencies - {node_id},
                        priority=down_def.priority,
                        retries=down_def.retries,
                    )
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
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Executes DFS cycle detection and returns the cycle tuple if found."""
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        stack: List[str] = []

        def dfs(node_id: str) -> Optional[Tuple[str, ...]]:
            visited.add(node_id)
            in_stack.add(node_id)
            stack.append(node_id)

            for neighbor in sorted(self._downstream.get(node_id, ())):
                if neighbor not in self._nodes:
                    continue
                if neighbor in in_stack:
                    idx = stack.index(neighbor)
                    return tuple(stack[idx:] + [neighbor])
                if neighbor not in visited:
                    res = dfs(neighbor)
                    if res is not None:
                        return res

            stack.pop()
            in_stack.remove(node_id)
            return None

        for node_id in sorted(self._nodes.keys()):
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle is not None:
                    return cycle
        return None

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        for node_id in sorted(self._nodes.keys()):
            node_def = self._nodes[node_id]
            all_deps = set(node_def.dependencies) | self._upstream.get(node_id, set())
            for dep_id in sorted(all_deps):
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep_id}' of node '{node_id}' does not exist in DAG.",
                        node_id=dep_id,
                    )

        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()))
            for node_id in self._nodes
        }

        def sort_key(nid: str) -> Tuple[int, str]:
            return (-self._nodes[nid].priority, nid)

        ready: List[str] = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0],
            key=sort_key,
        )
        order: List[str] = []

        while ready:
            current = ready.pop(0)
            order.append(current)
            for down_id in sorted(self._downstream.get(current, ())):
                if down_id in in_degree:
                    in_degree[down_id] -= 1
                    if in_degree[down_id] == 0:
                        ready.append(down_id)
                        ready.sort(key=sort_key)

        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            if cycle is None:  # pragma: no cover
                remaining = sorted(set(self._nodes.keys()) - set(order))
                cycle = tuple(remaining + [remaining[0]]) if remaining else ()
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected during topological sort: {' -> '.join(cycle)}",
                cycle=cycle,
            )

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if len(self._upstream.get(node_id, set())) == 0
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if len(self._downstream.get(node_id, set())) == 0
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

        durations: Dict[str, float] = {
            node_id: (
                float(estimated_durations[node_id])
                if estimated_durations is not None and node_id in estimated_durations
                else 1.0
            )
            for node_id in self._nodes
        }

        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for node_id in order:
            ups = [
                u for u in self._upstream.get(node_id, set()) if u in earliest
            ]
            if not ups:
                earliest[node_id] = durations[node_id]
                predecessor[node_id] = None
            else:
                best_pred = max(
                    ups,
                    key=lambda u: (earliest[u], self._nodes[u].priority, u),
                )
                earliest[node_id] = earliest[best_pred] + durations[node_id]
                predecessor[node_id] = best_pred

        terminal_node = max(
            order,
            key=lambda nid: (earliest[nid], self._nodes[nid].priority, nid),
        )
        max_weight = earliest[terminal_node]

        path: List[str] = []
        curr: Optional[str] = terminal_node
        while curr is not None:
            path.append(curr)
            curr = predecessor.get(curr)
        path.reverse()

        return (path, max_weight)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._dag_instance: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        if self._dag_instance is not None:
            return self._dag_instance
        return get_singleton(dag_engine_lite.DAG)

    def _sync_states(self) -> dag_engine_lite.DAG:
        dag = self._dag
        current_nodes = dag.all_nodes()
        for removed in list(self._states.keys()):
            if removed not in current_nodes:
                del self._states[removed]
        roots = dag.find_roots()
        for node_id in current_nodes:
            if node_id not in self._states:
                if node_id in roots:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
                else:
                    deps = dag.get_dependencies(node_id)
                    if deps and all(
                        self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                        for d in deps
                    ):
                        self._states[node_id] = dag_engine_lite.NodeState.READY
                    else:
                        self._states[node_id] = dag_engine_lite.NodeState.PENDING
        return dag

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        dag = self._sync_states()
        candidates: List[str] = []
        for node_id, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(node_id)
                if all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                ):
                    candidates.append(node_id)

        candidates.sort(
            key=lambda nid: (-dag.get_node(nid).priority, nid)
        )
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
        dag = self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dep_id in dag.get_dependents(node_id):
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING:
                upstreams = dag.get_dependencies(dep_id)
                if all(
                    self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED
                    for u in upstreams
                ):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        dag = self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid, st in list(self._states.items()):
                if st not in _TERMINAL_STATES:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            queue = list(dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                if self._states.get(curr) not in _TERMINAL_STATES:
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                for nxt in dag.get_dependents(curr):
                    if nxt not in visited:
                        queue.append(nxt)
        elif failure_policy == dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            pass

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        dag = self._sync_states()
        all_nodes = dag.all_nodes()
        if not all_nodes:
            return True
        return all(
            node_id in self._states and self._states[node_id] in _TERMINAL_STATES
            for node_id in all_nodes
        )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        if node_id not in self._states:
            self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        self._dag_instance: Optional[dag_engine_lite.DAG] = None
        self._scheduler_instance: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        if self._dag_instance is not None:
            return self._dag_instance
        return get_singleton(dag_engine_lite.DAG)

    @property
    def _scheduler(self) -> dag_engine_lite.WaveScheduler:
        if self._scheduler_instance is not None:
            return self._scheduler_instance
        return get_singleton(dag_engine_lite.WaveScheduler)

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = self._dag
        scheduler = self._scheduler
        dag.validate()

        start_wall_clock = time.perf_counter()
        self._results = {}

        halted = False
        while not scheduler.is_finished() and not halted:
            wave = scheduler.next_wave()
            if not wave:
                break

            for node_id in wave:
                if scheduler.get_state(node_id) != dag_engine_lite.NodeState.READY:
                    continue
                node_def = dag.get_node(node_id)
                scheduler.mark_running(node_id)

                node_start = time.perf_counter()
                attempts = 0
                max_retries = max(0, node_def.retries)
                succeeded = False
                return_val: Any = None
                last_exc: Optional[Exception] = None

                while True:
                    try:
                        return_val = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:
                        last_exc = exc
                        if attempts < max_retries:
                            attempts += 1
                        else:
                            break

                duration = time.perf_counter() - node_start
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=return_val,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    assert last_exc is not None
                    exec_error = (
                        last_exc
                        if isinstance(last_exc, dag_engine_lite.NodeExecutionError)
                        else dag_engine_lite.NodeExecutionError(
                            message=f"Execution of node '{node_id}' failed: {last_exc}",
                            node_id=node_id,
                            cause=last_exc,
                        )
                    )
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=exec_error,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_failed(node_id, failure_policy=failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break

        all_states = scheduler.get_all_states()
        for node_id, state in all_states.items():
            if node_id not in self._results and state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        wall_clock_seconds = time.perf_counter() - start_wall_clock
        crit_path_list, _ = dag.compute_critical_path()

        succeeded_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                nid
                for nid, st in all_states.items()
                if st == dag_engine_lite.NodeState.CANCELLED
            )
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(crit_path_list),
            results=dict(self._results),
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[dag_engine_lite.DAG, DAG],
        tier=system,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[dag_engine_lite.WaveScheduler, WaveScheduler],
        tier=system,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[dag_engine_lite.DAGRunner, DAGRunner],
        tier=system,
    )


_initialize_ = __initialize__
