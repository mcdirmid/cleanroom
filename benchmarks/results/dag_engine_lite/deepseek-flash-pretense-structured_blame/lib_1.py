# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_055632_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-08T05:56:32.156663+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 359,283
#   Cached Inbound Tokens:   32,645,120
#   Outbound Tokens:         396,672
#   Total Tokens:            33,401,075
#   Financial Cost ($USD):   $0.3898
#   Wall Clock Duration:     2838.45s
#   Step Latencies (s):      [256.6, 836.4, 195.7, 132.8, 83.6, 224.0, 53.0, 61.0, 20.2, 278.9, 73.8, 287.7, 81.3, 93.8, 244.3, 53.0, 20.3, 124.1, 50.9, 20.2, 20.2]
#   Role Execution Rounds:   lib: 5, pretense: 5, pretense_coverage: 3, pretense_qa: 8 (Total: 21)
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
"""Library interface for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __init__(self, message: str) -> None:
        # Exception instances receive runtime attributes (__traceback__), so plain
        # classes with dataclass semantics are used instead of frozen dataclasses.
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


@data_type
class CycleError(DAGError):
    """Precondition contract violation error raised when a dependency cycle is detected within the DAG.

    Designates an untestable checked precondition violation when caller constructs or validates a cyclic graph.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]

    def __init__(self, message: str, cycle: Tuple[str, ...]) -> None:
        super().__init__(message)
        self.cycle = cycle


@data_type
class NodeNotFoundError(DAGError):
    """Precondition contract violation error raised when a referenced node identifier does not exist in the DAG.

    Designates an untestable checked precondition violation when caller references an unregistered node.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str

    def __init__(self, message: str, node_id: str) -> None:
        super().__init__(message)
        self.node_id = node_id


@data_type
class DuplicateNodeError(DAGError):
    """Precondition contract violation error raised when attempting to add a node identifier that already exists in the DAG.

    Designates an untestable checked precondition violation when caller attempts to add a duplicate node.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
    """

    node_id: str

    def __init__(self, message: str, node_id: str) -> None:
        super().__init__(message)
        self.node_id = node_id


@data_type
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the failed node.
        cause: Underlying caught exception.
    """

    node_id: str
    cause: Exception

    def __init__(self, message: str, node_id: str, cause: Exception) -> None:
        super().__init__(message)
        self.node_id = node_id
        self.cause = cause


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
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Adds a task node to the graph.

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
            retries: Number of permitted retry attempts upon exception.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.
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
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.
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
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.
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
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        Args:
            estimated_durations: Optional mapping of node identifiers to duration weights.
                Defaults to 1.0 per node if omitted.

        Returns:
            Tuple of (critical path node identifiers, total path weight).
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
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.
        """
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        Args:
            node_id: Identifier of the failed node.
            failure_policy: Failure policy applied upon failure.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.
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
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        Args:
            failure_policy: Failure policy applied upon node action failure.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:00:53Z
# LAST_CHANGED: 2026-11-08T06:00:53Z
# CHANGE: Implemented interface module: concrete exception hierarchy (DAGError/CycleError/NodeNotFoundError/DuplicateNodeError/NodeExecutionError) with message-based __str__ (exceptions cannot be frozen dataclasses), NodeState/FailurePolicy enums, frozen data types (NodeDefinition, NodeResult, DAGRunReport), and system-tier Protocol singletons DAG/WaveScheduler/DAGRunner with framework decorators and stub-only signature parity with low specs.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Library implementation for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Terminal execution states shared by scheduler and runner bookkeeping.
_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

# Per-graph registration epochs for node identifiers. Registering an identifier again after it was
# removed yields a fresh epoch, which retires stale per-identifier scheduler bookkeeping.
_REGISTRATION_EPOCHS: Dict[int, Dict[str, int]] = {}


def _bump_registration_epoch(graph: dag_engine_lite.DAG, node_id: str) -> None:
    """Records a fresh registration epoch for a node identifier on the given graph."""
    epochs = _REGISTRATION_EPOCHS.setdefault(id(graph), {})
    epochs[node_id] = epochs.get(node_id, 0) + 1


def _registration_epoch(graph: dag_engine_lite.DAG, node_id: str) -> int:
    """Reports the current registration epoch for a node identifier on the given graph."""
    return _REGISTRATION_EPOCHS.get(id(graph), {}).get(node_id, 0)


class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def _refresh_definition_dependencies(self, node_id: str, dependencies: FrozenSet[str]) -> None:
        """Re-registers an immutable node definition with an updated frozen dependency set."""
        definition = self._nodes[node_id]
        self._nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=definition.node_id,
            action=definition.action,
            dependencies=dependencies,
            priority=definition.priority,
            retries=definition.retries,
        )

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
        # Checked precondition: duplicate identifiers are rejected.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(f"Node '{node_id}' is already registered", node_id)
        requested = frozenset(dependencies) if dependencies is not None else frozenset()
        # Register the immutable definition without eagerly resolving dependency existence.
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=requested,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # A fresh registration epoch retires scheduler tracking left over from a prior registration.
        _bump_registration_epoch(self, node_id)
        # Include directed edges for every requested dependency, deferring missing node checks.
        for upstream_id in sorted(requested):
            self._upstream[node_id].add(upstream_id)
            self._downstream.setdefault(upstream_id, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Checked precondition: both endpoints must already exist.
        for candidate in (upstream_id, downstream_id):
            if candidate not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(f"Node '{candidate}' is not registered", candidate)
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)
        # Keep the registered definition's frozen dependency set consistent with the adjacency view.
        definition = self._nodes[downstream_id]
        if upstream_id not in definition.dependencies:
            self._refresh_definition_dependencies(downstream_id, definition.dependencies | {upstream_id})

    def remove_node(self, node_id: str) -> None:
        # Checked precondition: the node must already exist.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(f"Node '{node_id}' is not registered", node_id)
        # Incident edges are purged from both adjacency directions before the node is deleted.
        for upstream_id in sorted(self._upstream.get(node_id, set())):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in sorted(self._downstream.get(node_id, set())):
            self._upstream.get(downstream_id, set()).discard(node_id)
            # Drop the incident edge from the dependent's immutable definition view as well.
            dependent_definition = self._nodes[downstream_id]
            if node_id in dependent_definition.dependencies:
                self._refresh_definition_dependencies(downstream_id, dependent_definition.dependencies - {node_id})
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(f"Node '{node_id}' is not registered", node_id)
        return definition

    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(f"Node '{node_id}' is not registered", node_id)
        # Defensive copy so callers cannot mutate the internal adjacency state.
        return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(f"Node '{node_id}' is not registered", node_id)
        return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def _detect_cycle(self) -> Optional[Tuple[str, ...]]:
        """Finds a directed cycle sequence using depth-first search with recursion path tracking."""
        visiting: Set[str] = set()
        visited: Set[str] = set()
        stack: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            visiting.add(node_id)
            stack.append(node_id)
            for upstream_id in sorted(self._upstream.get(node_id, set())):
                if upstream_id not in self._nodes:
                    continue
                if upstream_id in visiting:
                    start = stack.index(upstream_id)
                    return tuple(stack[start:] + [upstream_id])
                if upstream_id not in visited:
                    cycle = visit(upstream_id)
                    if cycle is not None:
                        return cycle
            stack.pop()
            visiting.discard(node_id)
            visited.add(node_id)
            return None

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                cycle = visit(node_id)
                if cycle is not None:
                    return cycle
        return None

    def validate(self) -> None:
        # Checked precondition: every referenced dependency must be a registered node.
        for node_id in sorted(self._nodes):
            for upstream_id in sorted(self._upstream.get(node_id, set())):
                if upstream_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on unregistered node '{upstream_id}'",
                        upstream_id,
                    )
        # Checked precondition: the graph must be acyclic.
        cycle = self._detect_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(f"Dependency cycle detected: {' -> '.join(cycle)}", cycle)

    def topological_sort(self) -> List[str]:
        in_degree: Dict[str, int] = {}
        for node_id in self._nodes:
            in_degree[node_id] = sum(
                1 for upstream_id in self._upstream.get(node_id, set()) if upstream_id in self._nodes
            )
        ready = [node_id for node_id in self._nodes if in_degree[node_id] == 0]
        ready.sort(key=lambda candidate: (-self._nodes[candidate].priority, candidate))
        order: List[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for downstream_id in sorted(self._downstream.get(current, set())):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    ready.append(downstream_id)
                    # Explicit stable key: priority descending, then identifier ascending.
                    ready.sort(key=lambda candidate: (-self._nodes[candidate].priority, candidate))
        if len(order) != len(self._nodes):
            cycle = self._detect_cycle()
            if cycle is None:  # unreachable (assumption: nodes left by in-degree drainage always lie on a directed cycle)
                cycle = tuple(sorted(node_id for node_id in self._nodes if node_id not in set(order)))
            raise dag_engine_lite.CycleError(f"Dependency cycle detected: {' -> '.join(cycle)}", cycle)
        return order

    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id)}

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return ([], 0.0)
        durations = estimated_durations if estimated_durations is not None else {}
        # Dynamic programming sweep over the topological order for earliest completion times.
        earliest: Dict[str, float] = {}
        for node_id in order:
            weight = durations.get(node_id, 1.0)
            upstream_finish = [
                earliest[upstream_id]
                for upstream_id in self._upstream.get(node_id, set())
                if upstream_id in earliest
            ]
            earliest[node_id] = max(upstream_finish, default=0.0) + weight
        # The terminal node with the maximum completion time ends the longest path.
        terminal = min(order, key=lambda candidate: (-earliest[candidate], candidate))
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            predecessors = [
                upstream_id
                for upstream_id in self._upstream.get(current, set())
                if upstream_id in earliest
            ]
            current = min(predecessors, key=lambda candidate: (-earliest[candidate], candidate)) if predecessors else None
        path.reverse()
        return (path, earliest[terminal])


class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}
        self._epochs: Dict[str, int] = {}

    def _graph(self) -> dag_engine_lite.DAG:
        """Resolves the active DAG collaborator on demand."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _synchronize(self) -> Set[str]:
        """Aligns tracked states with the currently registered DAG nodes and promotes unblocked nodes."""
        graph = self._graph()
        nodes = graph.all_nodes()
        # Drop state for nodes no longer registered in the graph (purging stale scheduler tracking).
        for node_id in list(self._states):
            if node_id not in nodes:
                del self._states[node_id]
        for node_id in list(self._epochs):
            if node_id not in nodes:
                del self._epochs[node_id]
        # Discover newly (or newly re-registered) nodes: retire stale tracking, then derive readiness.
        for node_id in sorted(nodes):
            epoch = _registration_epoch(graph, node_id)
            if node_id not in self._states or self._epochs.get(node_id) != epoch:
                upstream = graph.get_dependencies(node_id)
                if upstream:
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
                self._epochs[node_id] = epoch
        # Re-derive readiness of every non-terminal node from the live dependency graph, so that
        # newly added edges both promote unblocked nodes and demote nodes with unsatisfied upstreams.
        for node_id in sorted(nodes):
            state = self._states.get(node_id)
            if state is not dag_engine_lite.NodeState.PENDING and state is not dag_engine_lite.NodeState.READY:
                continue
            upstream = graph.get_dependencies(node_id)
            if all(self._states.get(upstream_id) is dag_engine_lite.NodeState.SUCCEEDED for upstream_id in upstream):
                self._states[node_id] = dag_engine_lite.NodeState.READY
            else:
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
        return nodes

    def next_wave(self) -> List[str]:
        graph = self._graph()
        nodes = self._synchronize()
        ready_wave: List[str] = []
        for node_id in nodes:
            if self._states.get(node_id) is not dag_engine_lite.NodeState.READY:
                continue
            upstream = graph.get_dependencies(node_id)
            if all(self._states.get(upstream_id) is dag_engine_lite.NodeState.SUCCEEDED for upstream_id in upstream):
                ready_wave.append(node_id)
        # Priority descending, then identifier ascending for deterministic wave ordering.
        ready_wave.sort(key=lambda candidate: (-graph.get_node(candidate).priority, candidate))
        return ready_wave

    def mark_running(self, node_id: str) -> None:
        # Synchronize first so the node's registration epoch is recorded and the RUNNING transition
        # is not mistaken for stale tracking left over from a prior registration.
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        graph = self._graph()
        # Synchronize tracked state before mutating so dependent promotion is complete.
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Promote newly unblocked dependents to READY.
        for downstream_id in sorted(graph.get_dependents(node_id)):
            if self._states.get(downstream_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            upstream = graph.get_dependencies(downstream_id)
            if all(self._states.get(upstream_id) is dag_engine_lite.NodeState.SUCCEEDED for upstream_id in upstream):
                self._states[downstream_id] = dag_engine_lite.NodeState.READY

    def _skip_downstream(self, node_id: str) -> None:
        """Marks every transitive dependent that has not reached a terminal state as SKIPPED."""
        graph = self._graph()
        pending = sorted(graph.get_dependents(node_id))
        visited: Set[str] = set()
        while pending:
            current = pending.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if self._states.get(current) not in _TERMINAL_STATES:
                self._states[current] = dag_engine_lite.NodeState.SKIPPED
            for dependent_id in sorted(graph.get_dependents(current)):
                if dependent_id not in visited:
                    pending.append(dependent_id)

    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy) -> None:
        # Synchronize tracked state so policy transitions cover every registered node.
        self._synchronize()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Cancel every remaining node that has not reached a terminal state.
            for other_id in sorted(self._states):
                if other_id == node_id:
                    continue
                if self._states[other_id] not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # Skip all transitive dependents that can no longer become ready because of the failure.
        self._skip_downstream(node_id)

    def is_finished(self) -> bool:
        nodes = self._synchronize()
        if not nodes:
            return True
        remaining = [node_id for node_id in sorted(nodes) if self._states.get(node_id) not in _TERMINAL_STATES]
        if not remaining:
            return True
        # Any ready or running node means work is still eligible to execute.
        for node_id in remaining:
            state = self._states.get(node_id)
            if state is dag_engine_lite.NodeState.READY or state is dag_engine_lite.NodeState.RUNNING:
                return False
        # Remaining pending nodes are blocked by failed or skipped dependencies.
        return True

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        graph = self._graph()
        if not graph.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(f"Node '{node_id}' is not registered", node_id)
        self._synchronize()
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        nodes = self._synchronize()
        # Only currently registered nodes are reported.
        return {node_id: self._states[node_id] for node_id in sorted(nodes)}


class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _graph(self) -> dag_engine_lite.DAG:
        """Resolves the active DAG collaborator on demand."""
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _wave_scheduler(self) -> dag_engine_lite.WaveScheduler:
        """Resolves the active wave scheduler collaborator on demand."""
        if self._scheduler is None:
            self._scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        return self._scheduler

    def run(self, failure_policy: dag_engine_lite.FailurePolicy) -> dag_engine_lite.DAGRunReport:
        graph = self._graph()
        scheduler = self._wave_scheduler()
        # Graph invariants are validated before any wave executes.
        graph.validate()
        self._results = {}
        start_time = time.monotonic()
        halted = False
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                # A prior failure in this wave may have cancelled the remaining nodes.
                if scheduler.get_state(node_id) is not dag_engine_lite.NodeState.READY:
                    continue
                definition = graph.get_node(node_id)
                scheduler.mark_running(node_id)
                node_start = time.monotonic()
                value: Any = None
                error: Optional[Exception] = None
                retries_attempted = 0
                succeeded = False
                while True:
                    try:
                        value = definition.action()
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        # Action failures are reified into NodeResult records and failure policies.
                        if retries_attempted >= definition.retries:
                            error = exc
                            break
                        retries_attempted += 1
                        continue
                    succeeded = True
                    break
                duration = time.monotonic() - node_start
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
            if halted:
                break
        # Record default outcomes for terminal nodes that never executed their action.
        states = scheduler.get_all_states()
        for node_id in sorted(states):
            if node_id not in self._results and states[node_id] in _TERMINAL_STATES:
                self._results[node_id] = dag_engine_lite.NodeResult(node_id=node_id, state=states[node_id])
        critical_path, _ = graph.compute_critical_path(None)
        wall_clock_seconds = time.monotonic() - start_time
        succeeded_nodes = tuple(sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.SUCCEEDED))
        failed_nodes = tuple(sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.FAILED))
        skipped_nodes = tuple(sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.SKIPPED))
        cancelled_nodes = tuple(sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.CANCELLED))
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(graph.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path),
            results=self._results,
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
# LAST_CLEANED: 2026-11-08T06:43:37Z
# LAST_CHANGED: 2026-11-08T06:28:42Z
# CHANGE: Resolved coverage feedback in DAG.topological_sort: pruned the unexercisable defensive guard for unregistered downstream dependents (downstream adjacency only ever holds registered node identifiers, so the in-degree decrement applies directly), and annotated the cycle-sequence fallback branch with '# unreachable (assumption: nodes left by in-degree drainage always lie on a directed cycle)' since a leftover node implies the depth-first cycle detection always returns a sequence.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T06:43:37Z
# PRETENSE_QA_AUDIT: 2026-11-08T06:43:15Z
# --- END AUTOFAB METADATA ---
