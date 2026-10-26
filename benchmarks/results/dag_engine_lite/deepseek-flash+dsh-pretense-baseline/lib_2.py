# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_210736_deepseek-flash_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-26T21:07:36.447939+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 69,850
#   Cached Inbound Tokens:   6,759,552
#   Outbound Tokens:         102,857
#   Total Tokens:            6,932,259
#   Financial Cost ($USD):   $0.1332
#   Wall Clock Duration:     492.33s
#   Step Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       33
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Synchronous DAG execution and wave scheduling engine interface.

Defines immutable graph records, lifecycle state enumerations, failure
policies, and the singleton protocols for graph construction, deterministic
wave scheduling, and sequential execution. Concrete realizations live in
:mod:`dag_engine_lite_impl`.
"""

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
        - MUST defer missing dependency existence checks to validate() and topological_sort()
          without eagerly raising NodeNotFoundError.
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
        - MUST break ties between concurrent ready nodes using priority descending and
          lexicographical node_id ascending.
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
        - WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents
          to SKIPPED.
        - WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes
          to CANCELLED.
        - WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes
          eligible for execution and transition blocked dependents of failed nodes to SKIPPED.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.

        POSTCONDITIONS:
        - WHEN all nodes in the DAG have reached terminal states (SUCCEEDED, FAILED,
          SKIPPED, CANCELLED), MUST return True.
        - WHEN no ready nodes remain and unexecuted nodes are blocked by failed dependencies,
          MUST return True.
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
            Mapping of node identifier to current NodeState, reflecting only currently
            registered nodes.
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
            failure_policy: Failure policy applied upon node action failure.
                Defaults to FAIL_FAST.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        POSTCONDITIONS:
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations,
          and critical path.
        """
        ...


# === File: dag_engine_lite_impl.py ===
"""Concrete synchronous DAG execution and wave scheduling engine.

Realizes the adjacency graph, deterministic Kahn topological ordering, depth
first cycle detection, critical path analysis, wave state machine, and
sequential execution runner specified by :mod:`dag_engine_lite`.
"""

from __future__ import annotations

import heapq
import time
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleError,
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
    system,
)

from . import dag_engine_lite

# Terminal lifecycle states: no further execution may occur for these nodes.
_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

_NODE_NOT_FOUND_MESSAGE = "Node not found in DAG: {node_id}"
_CYCLE_MESSAGE = "Dependency cycle detected: {cycle}"


def _missing_node(node_id: str) -> dag_engine_lite.NodeNotFoundError:
    """Builds the contracted node-not-found error for a missing identifier."""
    return dag_engine_lite.NodeNotFoundError(
        message=_NODE_NOT_FOUND_MESSAGE.format(node_id=node_id),
        node_id=node_id,
    )


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping
      node identifiers to definitions and sets.
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
        # Contract: register the immutable node definition in the registry.
        dependency_set: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition

        # Contract: repeated registration replaces the upstream edges described by
        # the new definition while preserving existing downstream dependents.
        previous_upstream = self._upstream.get(node_id)
        if previous_upstream is not None:
            for previous in previous_upstream:
                downstream = self._downstream.get(previous)
                if downstream is not None:
                    downstream.discard(node_id)
        self._upstream[node_id] = set()
        self._downstream.setdefault(node_id, set())

        # Contract: add directed dependency edges without eagerly validating
        # dependency existence; validation is deferred to validate().
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Contract: WHEN either endpoint is missing, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise _missing_node(upstream_id)
        if downstream_id not in self._nodes:
            raise _missing_node(downstream_id)

        # Contract: MUST establish a directed dependency edge upstream -> downstream.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # Contract: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise _missing_node(node_id)

        # Contract: remove every incident edge from both adjacency indexes.
        for dependency in self._upstream.get(node_id, set()):
            downstream = self._downstream.get(dependency)
            if downstream is not None:
                downstream.discard(node_id)
        for dependent in self._downstream.get(node_id, set()):
            upstream = self._upstream.get(dependent)
            if upstream is not None:
                upstream.discard(node_id)

        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        # Contract: purge the removed node from wave scheduler state tracking.
        self._purge_scheduler(node_id)

    def _purge_scheduler(self, node_id: str) -> None:
        """Removes a deleted node from the active wave scheduler state index."""
        try:
            scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        except LifecycleError:
            # A graph may be used in a registry with no scheduler registered.
            return
        forget = getattr(scheduler, "_forget_node", None)
        if callable(forget):
            forget(node_id)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        # Contract: membership is tested directly against the node registry.
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # Contract: WHEN node_id is absent, MUST raise NodeNotFoundError.
        definition = self._nodes.get(node_id)
        if definition is None:
            raise _missing_node(node_id)
        return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # Contract: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise _missing_node(node_id)
        # Contract: return a defensive copy of the upstream neighbor set.
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # Contract: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise _missing_node(node_id)
        # Contract: return a defensive copy of the downstream neighbor set.
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        # Contract: return a defensive copy of all registered node identifiers.
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Contract: every referenced dependency must exist in the node registry.
        for node_id in self._nodes:
            definition = self._nodes[node_id]
            candidates = set(definition.dependencies)
            candidates.update(self._upstream.get(node_id, set()))
            for dependency in candidates:
                if dependency not in self._nodes:
                    raise _missing_node(dependency)

        # Contract: detect directed cycles with an active recursion path.
        cycle = self._cycle_sequence()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=_CYCLE_MESSAGE.format(cycle=cycle),
                cycle=cycle,
            )

    def _cycle_sequence(self) -> Optional[Tuple[str, ...]]:
        """Returns a directed cycle sequence, or None when the graph is acyclic.

        Depth-first traversal follows upstream dependency edges with active path
        recursion tracking; a back-edge to a node already on the active path
        constitutes the reported cycle.
        """
        color: Dict[str, int] = {}
        path: List[str] = []

        def visit(node: str) -> Optional[Tuple[str, ...]]:
            color[node] = 1
            path.append(node)
            for dependency in sorted(self._upstream.get(node, set())):
                state = color.get(dependency, 0)
                if state == 1:
                    index = path.index(dependency)
                    return tuple(path[index:]) + (dependency,)
                if state == 0:
                    found = visit(dependency)
                    if found is not None:
                        return found
            path.pop()
            color[node] = 2
            return None

        for node in sorted(self._nodes):
            if color.get(node, 0) == 0:
                found = visit(node)
                if found is not None:
                    return found
        return None

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Contract: maintain in-degree counts from the upstream adjacency index.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }

        # Contract: process unblocked nodes in priority descending, node_id ascending order.
        ready: List[Tuple[int, str]] = []
        for node_id, degree in in_degree.items():
            if degree == 0:
                heapq.heappush(
                    ready, (-self._nodes[node_id].priority, node_id)
                )

        order: List[str] = []
        while ready:
            _, node_id = heapq.heappop(ready)
            order.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(
                        ready,
                        (-self._nodes[dependent].priority, dependent),
                    )

        # Contract: WHEN a cycle prevents ordering, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._cycle_sequence()
            if cycle is None:
                cycle = ()
            raise dag_engine_lite.CycleError(
                message=_CYCLE_MESSAGE.format(cycle=cycle),
                cycle=cycle,
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        # Contract: roots have an empty upstream dependency set.
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id, set())
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        # Contract: leaves have an empty downstream dependent set.
        return {
            node_id
            for node_id in self._nodes
            if not self._downstream.get(node_id, set())
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # Contract: critical path follows a valid topological ordering.
        order = self.topological_sort()
        if not order:
            return [], 0.0

        # Contract: unspecified node duration weights default to 1.0.
        durations: Dict[str, float] = {}
        for node_id in order:
            if estimated_durations is not None:
                durations[node_id] = float(estimated_durations.get(node_id, 1.0))
            else:
                durations[node_id] = 1.0

        # Contract: dynamic programming over earliest completion times.
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for node_id in order:
            best_time = 0.0
            best_dependency: Optional[str] = None
            for dependency in sorted(self._upstream.get(node_id, set())):
                dependency_time = earliest[dependency]
                if (
                    best_dependency is None
                    or dependency_time > best_time
                    or (
                        dependency_time == best_time
                        and dependency < best_dependency
                    )
                ):
                    best_time = dependency_time
                    best_dependency = dependency
            earliest[node_id] = best_time + durations[node_id]
            predecessor[node_id] = best_dependency

        # Contract: backtrack from the terminal leaf with maximal completion time.
        leaves = [
            node_id for node_id in order if not self._downstream.get(node_id, set())
        ]
        terminal = min(leaves, key=lambda node_id: (-earliest[node_id], node_id))
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        return path, earliest[terminal]


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of the sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronizes the state index with the currently registered DAG nodes."""
        nodes = self._dag.all_nodes()
        for known in list(self._states):
            if known not in nodes:
                del self._states[known]  # pragma: no cover (assumption: remove_node purges state)
        for node_id in nodes:
            if node_id not in self._states:
                if self._dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY

    def _promote_unblocked(self) -> None:
        """Promotes pending nodes whose prerequisites have all succeeded."""
        for node_id in list(self._states):
            if self._states[node_id] is not dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency)
                is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                self._states[node_id] = dag_engine_lite.NodeState.READY

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        """Collects all transitive downstream dependents of a node."""
        seen: Set[str] = set()
        pending: List[str] = list(self._dag.get_dependents(node_id))
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(self._dag.get_dependents(current))
        return seen

    @operation
    @override
    def next_wave(self) -> List[str]:
        self._sync_states()
        self._promote_unblocked()

        # Contract: include only READY nodes whose upstream dependencies succeeded.
        candidates: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency)
                is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                candidates.append(node_id)

        # Contract: order by priority descending, then node_id ascending.
        candidates.sort(
            key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id)
        )
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # Contract: update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        # Contract: update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED

        # Contract: promote newly unblocked dependents to READY.
        for dependent in self._dag.get_dependents(node_id):
            if (
                self._states.get(dependent)
                is not dag_engine_lite.NodeState.PENDING
            ):
                continue
            dependencies = self._dag.get_dependencies(dependent)
            if all(
                self._states.get(dependency)
                is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self._sync_states()
        # Contract: update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Contract: cancel every remaining non-terminal node.
            for other, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[other] = dag_engine_lite.NodeState.CANCELLED
            return

        # Contract: SKIP_DOWNSTREAM and CONTINUE_ON_ERROR both mark blocked
        # transitive dependents SKIPPED; independent nodes stay eligible.
        for dependent in self._transitive_dependents(node_id):
            state = self._states.get(dependent)
            if state is not None and state not in _TERMINAL_STATES:
                self._states[dependent] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        self._sync_states()
        # Contract: an empty graph is finished.
        if not self._states:
            return True
        # Contract: all terminal states means the run is finished.
        if all(state in _TERMINAL_STATES for state in self._states.values()):
            return True
        self._promote_unblocked()
        # Contract: with no ready or running node, remaining nodes are blocked
        # by failed dependencies and can never execute.
        return not any(
            state
            in (
                dag_engine_lite.NodeState.READY,
                dag_engine_lite.NodeState.RUNNING,
            )
            for state in self._states.values()
        )

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        # Contract: reflect only nodes currently registered in the DAG.
        return {
            node_id: self._states[node_id] for node_id in self._dag.all_nodes()
        }

    def _forget_node(self, node_id: str) -> None:
        """Purges a removed node from the scheduling state index."""
        self._states.pop(node_id, None)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of the sequential DAG execution runner.

    GROUNDING:
    - Resolves the active DAG and WaveScheduler services.
    - Coordinates execution using _dag, _scheduler, and _results.
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
        # Contract: validate graph invariants before commencing execution.
        self._dag.validate()

        start = time.perf_counter()
        self._results = {}
        halted = False

        # Contract: execute ready waves sequentially until completion.
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                # Contract: halt the wave loop when no executable wave remains.
                break  # pragma: no cover (assumption: is_finished gates empty waves)
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)

                node_start = time.perf_counter()
                retries_attempted = 0
                value: Any = None
                error: Optional[Exception] = None

                # Contract: retry a failing action up to the configured retry count.
                while True:
                    try:
                        value = definition.action()
                        error = None
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        error = exc
                        if retries_attempted >= definition.retries:
                            break
                        retries_attempted += 1

                duration = time.perf_counter() - node_start

                if error is None:
                    # Contract: record a SUCCEEDED result and unlock dependents.
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    # Contract: record a FAILED result and apply the failure policy.
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if (
                        failure_policy
                        is dag_engine_lite.FailurePolicy.FAIL_FAST
                    ):
                        halted = True
                        break
            if halted:
                break

        # Contract: record default results for terminal unexecuted nodes.
        for state_node, state in self._scheduler.get_all_states().items():
            if state_node in self._results:
                continue
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[state_node] = dag_engine_lite.NodeResult(
                    node_id=state_node,
                    state=state,
                )

        # Contract: compile terminal outcomes and critical path into the report.
        succeeded = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.FAILED
            )
        )
        skipped = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.CANCELLED
            )
        )
        critical_path, _ = self._dag.compute_critical_path()
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=time.perf_counter() - start,
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
