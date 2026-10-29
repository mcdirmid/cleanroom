# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_231540_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-10-28T23:15:40.938416+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 346,483
#   Cached Inbound Tokens:   29,426,560
#   Outbound Tokens:         323,225
#   Total Tokens:            30,096,268
#   Financial Cost ($USD):   $0.3342
#   Wall Clock Duration:     1784.95s
#   Step Latencies (s):      [235.7, 551.4, 163.5, 340.3, 71.5, 81.8, 81.8, 51.1, 20.4, 204.2, 133.9, 154.3, 20.3, 40.9, 51.2, 20.3, 20.3]
#   Role Execution Rounds:   lib: 2, pretense: 6, pretense_coverage: 3, pretense_qa: 6 (Total: 17)
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
"""Library interface for the synchronous DAG execution and wave scheduling engine."""

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
@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __str__(self) -> str:
        """Returns the human-readable diagnostic message."""
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
# LAST_CLEANED: 2026-10-28T23:19:27Z
# LAST_CHANGED: 2026-10-28T23:19:27Z
# CHANGE: Implement DAG engine interface module: frozen data types (DAGError/CycleError/NodeNotFoundError/NodeExecutionError with __str__), NodeState/FailurePolicy enums, NodeDefinition/NodeResult/DAGRunReport records, and DAG/WaveScheduler/DAGRunner service protocols with SystemTier singleton inheritance and contract stubs.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Library implementation for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from support.lib.lifecycle import LifecycleRegistry, get_default_registry
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import get_singleton

from . import dag_engine_lite

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

    tier: str = "system"

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
        dependency_set = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        # POSTCONDITION: register the node definition into the graph.
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # POSTCONDITION: add directed dependency edges, deferring existence validation.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        # POSTCONDITION: WHEN either identifier is missing, raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{upstream_id}' does not exist in the DAG",
                upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{downstream_id}' does not exist in the DAG",
                downstream_id,
            )
        # POSTCONDITION: establish the directed edge from upstream to downstream.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        # POSTCONDITION: WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the DAG",
                node_id,
            )
        # POSTCONDITION: remove the node and all its incident edges.
        for upstream_id in self._upstream.get(node_id, set()):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self._downstream.get(node_id, set()):
            self._upstream.get(downstream_id, set()).discard(node_id)
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
        # POSTCONDITION: WHEN node_id is absent, raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the DAG",
                node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the DAG",
                node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the DAG",
                node_id,
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
        # POSTCONDITION: WHEN a dependency node is missing, raise NodeNotFoundError.
        known = set(self._nodes)
        for node_id, definition in self._nodes.items():
            referenced = set(definition.dependencies) | self._upstream.get(node_id, set())
            for dependency in sorted(referenced):
                if dependency not in known:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' references missing dependency '{dependency}'",
                        dependency,
                    )
        # POSTCONDITION: WHEN a cycle exists, raise CycleError containing the cycle.
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                "Cycle detected: " + " -> ".join(cycle),
                tuple(cycle),
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        # Missing dependencies are reported here as NodeNotFoundError.
        known = set(self._nodes)
        for node_id in self._nodes:
            for dependency in sorted(self._upstream.get(node_id, set())):
                if dependency not in known:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' references missing dependency '{dependency}'",
                        dependency,
                    )
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }
        ready = [node_id for node_id in self._nodes if in_degree[node_id] == 0]
        ready.sort(key=self._order_key)
        order: List[str] = []
        while ready:
            # Highest priority first, ties broken by ascending node identifier.
            node_id = ready.pop(0)
            order.append(node_id)
            # Every registered downstream identifier is itself a registered node, so it has
            # an entry in the in-degree map (add_edge validates both endpoints eagerly).
            for dependent in sorted(self._downstream.get(node_id, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
            ready.sort(key=self._order_key)
        # POSTCONDITION: WHEN a cycle exists, raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle() or []
            raise dag_engine_lite.CycleError(
                "Cycle detected: " + " -> ".join(cycle),
                tuple(cycle),
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
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
            return ([], 0.0)
        durations = estimated_durations or {}
        # Dynamic programming over the topological order: earliest completion time.
        # Every prerequisite of an ordered node precedes it and thus has an earliest entry.
        earliest: Dict[str, float] = {}
        for node_id in order:
            weight = float(durations.get(node_id, 1.0))
            predecessors = self._upstream.get(node_id, set())
            earliest[node_id] = (
                max((earliest[p] for p in predecessors), default=0.0) + weight
            )
        # Terminal node with the maximum completion time (ties broken alphabetically).
        terminal = min(order, key=lambda candidate: (-earliest[candidate], candidate))
        path: List[str] = []
        current = terminal
        while True:
            path.append(current)
            predecessors = list(self._upstream.get(current, set()))
            if not predecessors:
                break
            current = min(
                predecessors,
                key=lambda candidate: (-earliest[candidate], candidate),
            )
        path.reverse()
        return (path, earliest[terminal])

    def _find_cycle(self) -> Optional[List[str]]:
        """Returns one directed cycle as a node sequence, or None if acyclic."""
        white, gray, black = 0, 1, 2
        color: Dict[str, int] = {node_id: white for node_id in self._nodes}
        stack: List[str] = []

        def visit(node_id: str) -> Optional[List[str]]:
            color[node_id] = gray
            stack.append(node_id)
            # validate()/topological_sort() reject missing prerequisites before cycle
            # detection, so every traversed dependency has a color entry.
            for dependency in sorted(self._upstream.get(node_id, set())):
                if color[dependency] == gray:
                    return list(stack[stack.index(dependency):])
                if color[dependency] == white:
                    found = visit(dependency)
                    if found is not None:
                        return found
            stack.pop()
            color[node_id] = black
            return None

        for node_id in sorted(self._nodes):
            if color[node_id] == white:
                found = visit(node_id)
                if found is not None:
                    return found
        return None

    def _order_key(self, node_id: str) -> Tuple[int, str]:
        """Sort key realizing priority descending then node_id ascending."""
        return (-self._nodes[node_id].priority, node_id)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    """

    tier: str = "system"

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        nodes = self._sync_states()
        candidates: List[str] = []
        for node_id in nodes:
            if self._states.get(node_id) is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            # POSTCONDITION: only nodes whose upstream dependencies all SUCCEEDED.
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                candidates.append(node_id)
        # POSTCONDITION: priority descending, then node_id ascending.
        candidates.sort(key=self._order_key)
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
        # POSTCONDITION: promote newly unblocked dependents to READY.
        for dependent in sorted(self._dag.get_dependents(node_id)):
            if self._states.get(dependent) is not dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = self._dag.get_dependencies(dependent)
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
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # POSTCONDITION: transitive dependents become SKIPPED.
            for dependent in self._transitive_dependents(node_id):
                self._mark_skipped(dependent)
        elif failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # POSTCONDITION: all remaining non-terminal nodes become CANCELLED. The failed
            # node was just set to FAILED (terminal), so it is not re-cancelled here.
            for other_id, state in self._states.items():
                if state not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        else:
            # POSTCONDITION: blocked dependents are SKIPPED while independent nodes stay eligible.
            for dependent in self._transitive_dependents(node_id):
                self._mark_skipped(dependent)
            for other_id, state in self._states.items():
                if state is not dag_engine_lite.NodeState.PENDING:
                    continue
                dependencies = self._dag.get_dependencies(other_id)
                if all(
                    self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                    for dependency in dependencies
                ):
                    self._states[other_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        nodes = self._sync_states()
        # POSTCONDITION: WHEN the DAG contains no nodes, return True.
        if not nodes:
            return True
        memo: Dict[str, bool] = {}
        for node_id in nodes:
            if self._states.get(node_id) in _TERMINAL_STATES:
                continue
            if self._can_progress(node_id, memo):
                return False
        # All remaining nodes are terminal or blocked by failed/missing dependencies.
        return True

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
        nodes = self._sync_states()
        return {node_id: self._states[node_id] for node_id in nodes}

    def _sync_states(self) -> Set[str]:
        """Synchronizes state tracking with the currently registered DAG nodes."""
        nodes = self._dag.all_nodes()
        # Purge identifiers removed from the DAG (remove_node state tracking clean-up).
        for stale_id in [node_id for node_id in self._states if node_id not in nodes]:
            del self._states[stale_id]
        # Discover newly registered nodes: roots start READY, dependents PENDING.
        for node_id in nodes:
            if node_id in self._states:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            self._states[node_id] = (
                dag_engine_lite.NodeState.PENDING
                if dependencies
                else dag_engine_lite.NodeState.READY
            )
        return nodes

    def _transitive_dependents(self, node_id: str) -> List[str]:
        """Collects all transitive downstream dependents of a node."""
        visited: Set[str] = set()
        frontier: List[str] = [node_id]
        while frontier:
            current = frontier.pop()
            for dependent in sorted(self._dag.get_dependents(current)):
                if dependent not in visited:
                    visited.add(dependent)
                    frontier.append(dependent)
        return sorted(visited)

    def _mark_skipped(self, node_id: str) -> None:
        """Transitions a non-terminal node to the SKIPPED state."""
        if self._states.get(node_id) not in _TERMINAL_STATES:
            self._states[node_id] = dag_engine_lite.NodeState.SKIPPED

    def _can_progress(
        self,
        node_id: str,
        memo: Dict[str, bool],
    ) -> bool:
        """Determines whether a node can still reach a terminal success/failure state."""
        if node_id in memo:
            return memo[node_id]
        state = self._states.get(node_id)
        if state is dag_engine_lite.NodeState.SUCCEEDED:
            memo[node_id] = True
            return True
        if state is dag_engine_lite.NodeState.READY or state is dag_engine_lite.NodeState.RUNNING:
            memo[node_id] = True
            return True
        if state is not dag_engine_lite.NodeState.PENDING:
            memo[node_id] = False
            return False
        # The DAG contract forbids cycles and validate()/run() reject them before
        # completion analysis, so recursion over prerequisites always terminates.
        result = all(
            self._can_progress(dependency, memo)
            for dependency in self._dag.get_dependencies(node_id)
        )
        memo[node_id] = result
        return result

    def _order_key(self, node_id: str) -> Tuple[int, str]:
        """Sort key realizing priority descending then node_id ascending."""
        return (-self._dag.get_node(node_id).priority, node_id)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier: str = "system"

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
        """Executes the entire DAG sequentially to completion or failure."""
        # POSTCONDITION: validate graph invariants before commencing wave execution.
        self._dag.validate()
        self._results = {}
        started = time.perf_counter()
        fail_fast_triggered = False
        while not fail_fast_triggered and not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            # Defensive termination: run() never mutates the DAG itself, so a non-finished
            # acyclic graph always yields at least one runnable node.
            if not wave:  # pragma: no cover (assumption: is_finished() is False only while next_wave() returns a non-empty wave)
                break
            for node_id in wave:
                if fail_fast_triggered:
                    break
                # Defensive guard: next_wave() only emits READY nodes, and same-wave
                # failures only skip transitive dependents, never independent members.
                if self._scheduler.get_state(node_id) is not dag_engine_lite.NodeState.READY:  # pragma: no cover (assumption: wave members stay READY because they are mutually independent)
                    continue
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_started = time.perf_counter()
                attempts = 0
                value: Any = None
                error: Optional[Exception] = None
                succeeded = False
                while True:
                    try:
                        value = definition.action()
                    except Exception as exc:  # cleanroom: allow-broad-exception (reified into error result)
                        error = exc
                        # POSTCONDITION: retry up to the configured retry count.
                        if attempts < definition.retries:
                            attempts += 1
                            continue
                        break
                    else:
                        succeeded = True
                        break
                duration = time.perf_counter() - node_started
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    # POSTCONDITION: apply the configured failure policy to the scheduler.
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        fail_fast_triggered = True
        # Populate default records for nodes that never executed (skipped/cancelled).
        states = self._scheduler.get_all_states()
        for node_id, state in states.items():
            if node_id in self._results:
                continue
            self._results[node_id] = dag_engine_lite.NodeResult(
                node_id=node_id,
                state=state,
            )
        wall_clock = time.perf_counter() - started
        critical_path, _ = self._dag.compute_critical_path()
        succeeded = tuple(
            node_id
            for node_id, result in self._results.items()
            if result.state is dag_engine_lite.NodeState.SUCCEEDED
        )
        failed = tuple(
            node_id
            for node_id, result in self._results.items()
            if result.state is dag_engine_lite.NodeState.FAILED
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
        # POSTCONDITION: return a consolidated report of states, durations, and critical path.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=wall_clock,
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
# LAST_CLEANED: 2026-10-28T23:45:14Z
# LAST_CHANGED: 2026-10-28T23:42:48Z
# CHANGE: Resolve unreachable-branch feedback: removed the impossible downstream in-degree guard and missing-color cycle-walk guard (both endpoints are validated/registered before these walks), and dropped the cyclic-graph revisiting guard from completion analysis since the contract forbids cycles and validate()/run() reject them first; annotated the runner's defensive empty-wave break and non-ready wave-member guard with '# pragma: no cover (assumption: ...)' explaining the acyclic, unmutated-DAG invariant; also pruned the analogous redundant 'p in earliest' critical-path filters and the redundant 'other_id != node_id' FAIL_FAST condition. Behavior re-verified against contracts for topological ordering, cycles, missing dependencies, policies, retries, and empty graphs.
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:45:14Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:44:55Z
# --- END CLEANROOM METADATA ---
