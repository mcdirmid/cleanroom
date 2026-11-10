# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261102_233602_deepseek-flash_dag_engine_lite
# Timestamp: 2026-11-02T23:36:02.954774+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 167,722
#   Cached Inbound Tokens:   8,183,552
#   Outbound Tokens:         133,031
#   Total Tokens:            8,484,305
#   Financial Cost ($USD):   $0.1295
#   Wall Clock Duration:     666.57s
#   Step Latencies (s):      [156.7, 291.1, 21.1, 155.8, 63.4, 94.0, 20.9, 55.8, 41.5, 21.0, 20.6]
#   Role Execution Rounds:   coverage: 3, lib: 2, qa: 3, test: 3 (Total: 11)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       48
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
import enum

from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

# Requirements specified in dag_engine_lite.pyi

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
        # Exception messages are rendered verbatim by diagnostic assertions.
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
        # Registers the immutable node definition without eager dependency validation.
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
        # Requires both endpoints; missing identifiers raise NodeNotFoundError.
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
        # Removes the node and its incident edges; absent identifiers raise NodeNotFoundError.
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:38:43Z
# LAST_CHANGED: 2026-11-02T23:38:43Z
# CHANGE: Implement DAG engine interface: exception records with __str__, NodeState/FailurePolicy enums, frozen data types (NodeDefinition, NodeResult, DAGRunReport), and abstract DAG/WaveScheduler/DAGRunner protocol stubs matching low/dag_engine_lite.pyi
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi

_TERMINAL_STATES = (
    dag_engine_lite.NodeState.SUCCEEDED,
    dag_engine_lite.NodeState.FAILED,
    dag_engine_lite.NodeState.SKIPPED,
    dag_engine_lite.NodeState.CANCELLED,
)


class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        # MUST register the node definition into the graph.
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies) if dependencies is not None else frozenset(),
            priority=priority,
            retries=retries,
        )
        previous = self._nodes.get(node_id)
        if previous is not None:
            # Re-registration replaces the definition's outgoing dependency edges.
            for dependency in previous.dependencies:
                self._downstream.get(dependency, set()).discard(node_id)
            self._upstream[node_id] = set()
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # WHEN dependencies are provided, MUST add directed edges from each dependency to node_id.
        # Missing dependency checks are deferred to validate()/topological_sort().
        for dependency in definition.dependencies:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        for missing in (upstream_id, downstream_id):
            if missing not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    f"Node not found in graph: {missing}", missing
                )
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node not found in graph: {node_id}", node_id
            )
        # MUST remove the node and its incident edges.
        for upstream_id in self._upstream.get(node_id, set()):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self._downstream.get(node_id, set()):
            self._upstream.get(downstream_id, set()).discard(node_id)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)
        del self._nodes[node_id]
        # MUST purge the node identifier from wave scheduler state tracking;
        # the scheduler prunes identifiers absent from all_nodes() on its next sweep.

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node not found in graph: {node_id}", node_id
            )
        return definition

    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node not found in graph: {node_id}", node_id
            )
        return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node not found in graph: {node_id}", node_id
            )
        return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def _check_referenced_nodes(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._nodes[node_id].dependencies):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on missing node '{dependency}'",
                        dependency,
                    )

    def _find_cycle(self) -> Optional[List[str]]:
        colors: Dict[str, int] = {node_id: 0 for node_id in self._nodes}
        path: List[str] = []

        def visit(node_id: str) -> Optional[List[str]]:
            colors[node_id] = 1
            path.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                if colors[dependency] == 1:
                    # Active recursion path exposes the directed cycle sequence.
                    return path[path.index(dependency):]
                if colors[dependency] == 0:
                    cycle = visit(dependency)
                    if cycle is not None:
                        return cycle
            path.pop()
            colors[node_id] = 2
            return None

        for node_id in sorted(self._nodes):
            if colors[node_id] == 0:
                cycle = visit(node_id)
                if cycle is not None:
                    return cycle
        return None

    def validate(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        self._check_referenced_nodes()
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                "Dependency cycle detected: " + " -> ".join(cycle),
                tuple(cycle),
            )

    def topological_sort(self) -> List[str]:
        # Referenced nodes must exist before a deterministic ordering can be produced.
        self._check_referenced_nodes()
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }
        ready: List[str] = [node_id for node_id, degree in in_degree.items() if degree == 0]
        order: List[str] = []
        while ready:
            # Tie-break concurrently ready nodes: priority descending, then node_id ascending.
            ready.sort(key=lambda candidate: (-self._nodes[candidate].priority, candidate))
            current = ready.pop(0)
            order.append(current)
            for dependent in sorted(self._downstream.get(current, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
        # WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle() or []
            raise dag_engine_lite.CycleError(
                "Dependency cycle detected: " + " -> ".join(cycle),
                tuple(cycle),
            )
        return order

    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id)}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        if not self._nodes:
            return ([], 0.0)
        order = self.topological_sort()
        durations: Dict[str, float] = {}
        for node_id in self._nodes:
            if estimated_durations is not None and node_id in estimated_durations:
                durations[node_id] = estimated_durations[node_id]
            else:
                # MUST default to 1.0 per node when no duration weight is supplied.
                durations[node_id] = 1.0
        # Earliest completion time for each node via longest-path dynamic programming.
        earliest: Dict[str, float] = {}
        for node_id in order:
            best_predecessor = max(
                (earliest[dep] for dep in self._upstream.get(node_id, set())),
                default=0.0,
            )
            earliest[node_id] = best_predecessor + durations[node_id]
        # Terminal node with the maximum completion time anchors the critical path.
        terminal = min(order, key=lambda candidate: (-earliest[candidate], candidate))
        path: List[str] = [terminal]
        while True:
            upstream_ids = self._upstream.get(path[-1], set())
            if not upstream_ids:
                break
            predecessor = min(
                upstream_ids, key=lambda candidate: (-earliest[candidate], candidate)
            )
            path.append(predecessor)
        path.reverse()
        # MUST return the cumulative weight of that path.
        return (path, earliest[terminal])


class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _synchronize(self) -> dag_engine_lite.DAG:
        # Resolve the active DAG service on demand rather than caching a stale instance.
        dag = get_singleton(dag_engine_lite.DAG)
        self._dag = dag
        node_ids = dag.all_nodes()
        for node_id in node_ids:
            if node_id not in self._states:
                dependencies = dag.get_dependencies(node_id)
                # Roots start READY; dependent nodes start PENDING.
                if dependencies:
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
        for node_id in list(self._states.keys()):
            if node_id not in node_ids:
                # Purge tracking state for nodes no longer registered in the DAG.
                del self._states[node_id]
        # Promote pending nodes whose upstream dependencies have all succeeded.
        for node_id in node_ids:
            if self._states[node_id] is not dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                self._states[node_id] = dag_engine_lite.NodeState.READY
        return dag

    def next_wave(self) -> List[str]:
        dag = self._synchronize()
        ready: List[str] = []
        # MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                ready.append(node_id)
        # MUST order returned nodes by priority descending, then node_id ascending.
        ready.sort(key=lambda candidate: (-dag.get_node(candidate).priority, candidate))
        return ready

    def mark_running(self, node_id: str) -> None:
        self._synchronize()
        # MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        dag = self._synchronize()
        # MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST promote newly unblocked downstream dependents to READY.
        for dependent in dag.get_dependents(node_id):
            if self._states.get(dependent) is not dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = dag.get_dependencies(dependent)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    def _transitive_dependents(
        self, dag: dag_engine_lite.DAG, node_id: str
    ) -> List[str]:
        discovered: List[str] = []
        frontier = list(dag.get_dependents(node_id))
        while frontier:
            current = frontier.pop(0)
            if current in discovered:
                continue
            discovered.append(current)
            frontier.extend(dag.get_dependents(current))
        return discovered

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        dag = self._synchronize()
        # MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # MUST transition all remaining non-terminal nodes to CANCELLED.
            for other, state in self._states.items():
                if other != node_id and state not in _TERMINAL_STATES:
                    self._states[other] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # MUST transition all transitive dependents to SKIPPED.
            for dependent in self._transitive_dependents(dag, node_id):
                if self._states.get(dependent) not in _TERMINAL_STATES:
                    self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
        else:
            # CONTINUE_ON_ERROR: skip blocked transitive dependents of failed nodes while
            # leaving unblocked independent nodes eligible for execution.
            changed = True
            while changed:
                changed = False
                for other in list(self._states.keys()):
                    if self._states[other] in _TERMINAL_STATES:
                        continue
                    dependencies = dag.get_dependencies(other)
                    if any(
                        self._states.get(dep)
                        in (
                            dag_engine_lite.NodeState.FAILED,
                            dag_engine_lite.NodeState.SKIPPED,
                        )
                        for dep in dependencies
                    ):
                        self._states[other] = dag_engine_lite.NodeState.SKIPPED
                        changed = True

    def is_finished(self) -> bool:
        dag = self._synchronize()
        node_ids = dag.all_nodes()
        # WHEN the DAG contains no nodes, MUST return True.
        if not node_ids:
            return True
        # WHEN all nodes have reached terminal states, MUST return True.
        if all(self._states.get(node_id) in _TERMINAL_STATES for node_id in node_ids):
            return True
        # WHEN no ready nodes remain and unexecuted nodes are blocked, MUST return True.
        ready_exists = False
        running_exists = False
        for node_id in node_ids:
            state = self._states.get(node_id)
            if state is dag_engine_lite.NodeState.RUNNING:
                running_exists = True
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                ready_exists = True
        # WHEN any node remains non-terminal and eligible to execute, MUST return False.
        return not ready_exists and not running_exists

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        self._synchronize()
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._synchronize()
        return {
            node_id: self._states[node_id]
            for node_id in dag.all_nodes()
            if node_id in self._states
        }


class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _execute_node(
        self, definition: dag_engine_lite.NodeDefinition[Any]
    ) -> dag_engine_lite.NodeResult[Any]:
        attempts = 0
        started = time.perf_counter()
        while True:
            try:
                value = definition.action()
            except Exception as exc:  # cleanroom: allow-broad-exception
                # Retries are executed up to the configured retry count.
                attempts += 1
                if attempts > definition.retries:
                    elapsed = time.perf_counter() - started
                    return dag_engine_lite.NodeResult(
                        node_id=definition.node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=exc,
                        duration_seconds=elapsed,
                        retries_attempted=attempts - 1,
                    )
                continue
            elapsed = time.perf_counter() - started
            return dag_engine_lite.NodeResult(
                node_id=definition.node_id,
                state=dag_engine_lite.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=elapsed,
                retries_attempted=attempts,
            )

    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler
        self._results = {}
        # MUST validate graph invariants before commencing wave execution.
        dag.validate()
        started = time.perf_counter()
        halted = False
        # MUST execute ready waves sequentially.
        while not halted and not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:  # unreachable (assumption: is_finished matches next_wave readiness)
                break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                # MUST execute retries up to the configured retry count.
                result = self._execute_node(definition)
                self._results[node_id] = result
                if result.state is dag_engine_lite.NodeState.SUCCEEDED:
                    scheduler.mark_succeeded(node_id)
                else:
                    # MUST apply the specified failure_policy to the scheduler.
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
        elapsed = time.perf_counter() - started
        # Capture default terminal outcomes (skipped or cancelled) for unexecuted nodes.
        for node_id in dag.all_nodes():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=scheduler.get_state(node_id),
                )
        critical_path, _total_weight = dag.compute_critical_path()
        results = dict(self._results)
        succeeded = tuple(
            sorted(
                node_id
                for node_id, result in results.items()
                if result.state is dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed = tuple(
            sorted(
                node_id
                for node_id, result in results.items()
                if result.state is dag_engine_lite.NodeState.FAILED
            )
        )
        skipped = tuple(
            sorted(
                node_id
                for node_id, result in results.items()
                if result.state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled = tuple(
            sorted(
                node_id
                for node_id, result in results.items()
                if result.state is dag_engine_lite.NodeState.CANCELLED
            )
        )
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(results),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=results,
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
# LAST_CLEANED: 2026-11-02T23:46:56Z
# LAST_CHANGED: 2026-11-02T23:44:41Z
# CHANGE: Resolve unreachable-code feedback: remove the redundant upstream-membership guard in DFS cycle detection (all callers pre-validate referenced dependencies), delete the no-op pending-promotion pass in the CONTINUE_ON_ERROR branch (synchronization already applies the same predicate and the intervening pass only marks SKIPPED), and annotate the defensive empty-wave stall guard with '# unreachable (assumption: ...)'. Runtime re-verified across happy path, cycles, retries, all failure policies, removal purge, and empty DAG.
# COVERAGE_AUDIT: 2026-11-02T23:46:56Z
# QA_AUDIT: 2026-11-02T23:46:44Z
# --- END AUTOFAB METADATA ---
