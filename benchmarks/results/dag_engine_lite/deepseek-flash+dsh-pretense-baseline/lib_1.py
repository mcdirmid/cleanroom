# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_231537_deepseek-flash_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-28T23:15:37.906311+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 74,805
#   Cached Inbound Tokens:   6,524,288
#   Outbound Tokens:         133,821
#   Total Tokens:            6,732,914
#   Financial Cost ($USD):   $0.1111
#   Wall Clock Duration:     904.48s
#   Step Latencies (s):      [697.9, 192.4]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
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
"""Synchronous DAG execution and wave scheduling engine interface specification."""

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
# LAST_CLEANED: 2026-10-28T23:30:42Z
# LAST_CHANGED: 2026-10-28T23:30:42Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b47e787a3c63
# COVERAGE_AUDIT: 2026-10-28T23:30:42Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:30:42Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:30:42Z
# QA_AUDIT: 2026-10-28T23:30:42Z
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

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


class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node
      identifiers to definitions and sets.
    """

    tier = system

    def __init__(self) -> None:
        # INVARIANT: all three mappings are keyed by registered node identifiers.
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
        # WHEN dependencies are provided, freeze them into the definition and add edges.
        frozen = frozenset(dependencies) if dependencies is not None else frozenset()
        self._nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen,
            priority=priority,
            retries=retries,
        )
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # Missing dependency existence checks are deferred to validate()/topological_sort().
        for dependency in frozen:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{upstream_id}' not found in graph", node_id=upstream_id
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{downstream_id}' not found in graph", node_id=downstream_id
            )
        # MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._downstream[upstream_id].add(downstream_id)
        self._upstream[downstream_id].add(upstream_id)

    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph", node_id=node_id
            )
        # MUST remove the node and its incident edges.
        for dependency in self._upstream[node_id]:
            self._downstream[dependency].discard(node_id)
        for dependent in self._downstream[node_id]:
            self._upstream[dependent].discard(node_id)
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph", node_id=node_id
            )
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph", node_id=node_id
            )
        # MUST return all direct upstream dependencies (defensive copy).
        return set(self._upstream[node_id])

    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph", node_id=node_id
            )
        # MUST return all direct downstream dependents (defensive copy).
        return set(self._downstream[node_id])

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def validate(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for node_id, definition in self._nodes.items():
            for dependency in definition.dependencies:
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on missing node '{dependency}'",
                        node_id=dependency,
                    )
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle:
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}", cycle=cycle
            )

    def topological_sort(self) -> List[str]:
        # In-degree counts derive exclusively from the upstream adjacency mapping.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream[node_id]) for node_id in self._nodes
        }
        ready = sorted(
            (node_id for node_id, degree in in_degree.items() if degree == 0),
            key=self._priority_key,
        )
        order: List[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for dependent in self._downstream[current]:
                in_degree[dependent] -= 1
                # Newly unblocked nodes keep priority-descending, node_id-ascending order.
                if in_degree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort(key=self._priority_key)
        # WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}", cycle=cycle
            )
        return order

    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream[node_id]}

    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream[node_id]}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # MUST compute a valid topological order before dynamic programming.
        order = self.topological_sort()
        durations = estimated_durations if estimated_durations is not None else {}
        earliest: Dict[str, float] = {}
        # earliest[node] = max(earliest[upstream]) + duration[node]
        for node_id in order:
            upstream_times = [earliest[dependency] for dependency in self._upstream[node_id]]
            best = max(upstream_times) if upstream_times else 0.0
            earliest[node_id] = best + durations.get(node_id, 1.0)
        # An empty graph has no path and therefore a zero total weight.
        if not order:
            return ([], 0.0)
        # Identify the terminal node with the maximum completion time.
        terminal = max(order, key=lambda node_id: (earliest[node_id], node_id))
        path: List[str] = [terminal]
        # Backtrack through the predecessor that yields the maximum earliest time.
        current = terminal
        while self._upstream[current]:
            current = max(
                self._upstream[current],
                key=lambda node_id: (earliest[node_id], node_id),
            )
            path.append(current)
        path.reverse()
        return (path, earliest[terminal])

    def _priority_key(self, node_id: str) -> Tuple[int, str]:
        return (-self._nodes[node_id].priority, node_id)

    def _find_cycle(self) -> Tuple[str, ...]:
        """Returns the identifiers forming a directed cycle, or an empty tuple."""
        visiting: Dict[str, int] = {}
        path: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            visiting[node_id] = 1
            path.append(node_id)
            for dependency in self._upstream[node_id]:
                mark = visiting.get(dependency)
                if mark == 1:
                    return tuple(path[path.index(dependency):])
                if mark is None:
                    found = visit(dependency)
                    if found is not None:
                        return found
            path.pop()
            visiting[node_id] = 2
            return None

        for node_id in self._nodes:
            if node_id not in visiting:
                cycle = visit(node_id)
                if cycle is not None:
                    return cycle
        return ()


class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of the sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def next_wave(self) -> List[str]:
        dag = self._resolve_dag()
        self._sync_states(dag)
        wave: List[str] = []
        for node_id, state in self._states.items():
            # MUST return all nodes currently in READY whose upstream dependencies are SUCCEEDED.
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                wave.append(node_id)
        # MUST order returned nodes by priority descending, then node_id ascending.
        wave.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        return wave

    def mark_running(self, node_id: str) -> None:
        self._sync_states(self._resolve_dag())
        # MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        dag = self._resolve_dag()
        self._sync_states(dag)
        # MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST promote newly unblocked downstream dependents to READY.
        for dependent in dag.get_dependents(node_id):
            if self._states.get(dependent) is not dag_engine_lite.NodeState.PENDING:
                continue
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dag.get_dependencies(dependent)
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        dag = self._resolve_dag()
        self._sync_states(dag)
        # MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # WHEN FAIL_FAST, MUST transition all remaining non-terminal nodes to CANCELLED.
            for other_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        else:
            # WHEN SKIP_DOWNSTREAM or CONTINUE_ON_ERROR, blocked dependents become SKIPPED.
            for dependent in self._transitive_dependents(dag, node_id):
                if self._states.get(dependent) not in _TERMINAL_STATES:
                    self._states[dependent] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        dag = self._resolve_dag()
        self._sync_states(dag)
        # WHEN the DAG contains no nodes, MUST return True.
        if not dag.all_nodes():
            return True
        # WHEN any node remains non-terminal and eligible to execute, MUST return False.
        for state in self._states.values():
            if state not in _TERMINAL_STATES:
                return False
        return True

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        self._sync_states(self._resolve_dag())
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._resolve_dag()
        self._sync_states(dag)
        return {node_id: self._states[node_id] for node_id in dag.all_nodes()}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _sync_states(self, dag: dag_engine_lite.DAG) -> None:
        registered = dag.all_nodes()
        # Initialize newly discovered nodes: unblocked nodes start READY, others PENDING.
        for node_id in registered:
            if node_id not in self._states:
                if all(
                    self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                    for dependency in dag.get_dependencies(node_id)
                ):
                    self._states[node_id] = dag_engine_lite.NodeState.READY
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
        # MUST purge removed node identifiers from wave scheduler state tracking.
        for node_id in list(self._states.keys()):
            if node_id not in registered:
                del self._states[node_id]

    def _transitive_dependents(
        self, dag: dag_engine_lite.DAG, node_id: str
    ) -> Set[str]:
        seen: Set[str] = set()
        pending: List[str] = list(dag.get_dependents(node_id))
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(dag.get_dependents(current))
        return seen


class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of the sequential DAG execution runner.

    GROUNDING:
    - Resolves the active DAG and WaveScheduler services via get_singleton.
    - Coordinates execution using _results.
    """

    tier = system

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        # MUST validate graph invariants before commencing wave execution.
        dag.validate()
        started = time.perf_counter()
        self._results = {}
        halted = False
        # MUST execute ready waves sequentially.
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            # Halt wave execution when no node is ready to make forward progress.
            if not wave:
                break
            for node_id in wave:
                # WHEN FAIL_FAST halts the run, cancelled wave peers are not executed.
                if halted:
                    break
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                result = self._execute_node(definition)
                self._results[node_id] = result
                # MUST apply the specified failure_policy to the scheduler upon failure.
                if result.state is dag_engine_lite.NodeState.FAILED:
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
        elapsed = time.perf_counter() - started
        # Populate default records for terminal nodes that never executed this run.
        for node_id, state in scheduler.get_all_states().items():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id, state=state
                )
        critical_path, _ = dag.compute_critical_path()
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
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

    def _execute_node(
        self, definition: dag_engine_lite.NodeDefinition[Any]
    ) -> dag_engine_lite.NodeResult[Any]:
        started = time.perf_counter()
        attempts = 0
        while True:
            try:
                value = definition.action()
                # MUST record successful NodeResult and execution duration.
                return dag_engine_lite.NodeResult(
                    node_id=definition.node_id,
                    state=dag_engine_lite.NodeState.SUCCEEDED,
                    value=value,
                    duration_seconds=time.perf_counter() - started,
                    retries_attempted=attempts,
                )
            except Exception as exc:  # cleanroom: allow-broad-exception
                # MUST execute retries up to the configured retry count.
                if attempts < definition.retries:
                    attempts += 1
                    continue
                # MUST record the caught exception in the failed NodeResult.
                return dag_engine_lite.NodeResult(
                    node_id=definition.node_id,
                    state=dag_engine_lite.NodeState.FAILED,
                    error=exc,
                    duration_seconds=time.perf_counter() - started,
                    retries_attempted=attempts,
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
# LAST_CLEANED: 2026-10-28T23:30:42Z
# LAST_CHANGED: 2026-10-28T23:30:42Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 886d069f33a7
# COVERAGE_AUDIT: 2026-10-28T23:30:42Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:30:42Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:30:42Z
# QA_AUDIT: 2026-10-28T23:30:42Z
# --- END CLEANROOM METADATA ---
