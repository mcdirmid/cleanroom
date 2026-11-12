# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_004444_deepseek-flash_dag_engine_lite_combined
# Timestamp: 2026-11-12T00:44:44.253567+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 605,719
#   Cached Inbound Tokens:   27,204,992
#   Outbound Tokens:         397,420
#   Total Tokens:            28,208,131
#   Financial Cost ($USD):   $0.4109
#   Wall Clock Duration:     1425.46s
#   Step Latencies (s):      [335.0, 371.1, 61.6, 71.9, 10.1, 605.5, 10.1, 132.2, 53.9, 20.4, 208.7, 162.4, 95.3, 51.4, 160.0, 61.6, 12.5, 23.0, 22.9, 125.7, 10.1, 211.8, 10.1, 20.3]
#   Role Execution Rounds:   coverage: 2, lib: 5, pretense: 3, pretense_coverage: 3, pretense_qa: 5, qa: 4, test: 2 (Total: 24)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       63
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface protocols and passive data types for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import enum
from dataclasses import dataclass
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
class DuplicateNodeError(DAGError):
    """Raised when attempting to add a node identifier that already exists.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
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

        Preconditions:
            The node identifier must not already be registered; duplicates raise
            DuplicateNodeError.

        Postconditions:
            The node definition is registered and directed dependency edges are
            created for every supplied dependency. Missing dependency existence
            is deferred to graph validation and topological ordering.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        Preconditions:
            Both node identifiers must exist in the graph; otherwise a
            NodeNotFoundError is raised.

        Postconditions:
            A directed dependency edge is established from the upstream node to
            the downstream node.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        Preconditions:
            The node identifier must exist in the graph; otherwise a
            NodeNotFoundError is raised.

        Postconditions:
            The node and its incident edges are removed, and the identifier is
            purged from scheduler state tracking.
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

        Preconditions:
            The node identifier must exist in the graph; otherwise a
            NodeNotFoundError is raised.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.

        Preconditions:
            The node identifier must exist in the graph; otherwise a
            NodeNotFoundError is raised.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.

        Preconditions:
            The node identifier must exist in the graph; otherwise a
            NodeNotFoundError is raised.
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

        Preconditions:
            All referenced dependencies must exist and the graph must be
            acyclic; otherwise NodeNotFoundError or CycleError is raised.

        Postconditions:
            Completes without error when the graph is complete and acyclic.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority
        (descending), then alphabetically by node identifier (ascending).

        Returns:
            List of node identifiers in topological order.

        Preconditions:
            The graph must be acyclic; otherwise a CycleError is raised.
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
            estimated_durations: Optional mapping of node identifiers to duration
                weights. Defaults to 1.0 per node if omitted.

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
            List of node identifiers ready for execution, ordered by priority
            descending and then node identifier ascending.
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
            True if all nodes in the DAG have reached terminal states or are
            blocked by failed dependencies, or if the DAG is empty.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Current NodeState.

        Preconditions:
            The node identifier must be registered in the scheduled DAG;
            otherwise a NodeNotFoundError is raised.
        """
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph.

        Returns:
            Mapping of node identifier to current NodeState, reflecting only
            currently registered nodes.
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

        Preconditions:
            All referenced dependencies must exist and the graph must be
            acyclic; otherwise NodeNotFoundError or CycleError is raised.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T00:50:49Z
# LAST_CHANGED: 2026-11-12T00:50:49Z
# CHANGE: Implement interface module: DAG exception hierarchy (non-frozen dataclass errors with __str__), NodeState/FailurePolicy enums, frozen NodeDefinition/NodeResult/DAGRunReport data types, and @singleton_type Protocol services DAG, WaveScheduler, and DAGRunner declaring the contracted operations.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG graph, wave scheduler, and sequential runner."""

from __future__ import annotations

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

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete directed acyclic graph holding node definitions and directed dependency edges."""

    tier = "system"

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
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the graph",
                node_id=node_id,
            )
        # Freeze the declared dependency collection so the definition stays immutable.
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
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # Wire each declared dependency edge without eagerly checking existence.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{upstream_id}' is not registered in the graph",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{downstream_id}' is not registered in the graph",
                node_id=downstream_id,
            )
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        # Detach the node from every incident upstream and downstream edge.
        for dependency in self._upstream.get(node_id, set()):
            self._downstream.get(dependency, set()).discard(node_id)
        for dependent in self._downstream.get(node_id, set()):
            self._upstream.get(dependent, set()).discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes)

    @operation
    @override
    def validate(self) -> None:
        # Every referenced dependency must resolve to a registered node.
        for node_id in sorted(self._upstream):
            for dependency in sorted(self._upstream[node_id]):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' depends on unregistered node '{dependency}'"
                        ),
                        node_id=dependency,
                    )
        # A depth-first sweep over the dependency edges rejects directed cycles.
        cycle = self._detect_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Deferred dependency checks surface here when graph validation was skipped.
        for node_id in sorted(self._upstream):
            for dependency in sorted(self._upstream[node_id]):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' depends on unregistered node '{dependency}'"
                        ),
                        node_id=dependency,
                    )
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set())) for node_id in self._nodes
        }
        ready: List[str] = [
            node_id for node_id in self._nodes if in_degree[node_id] == 0
        ]
        order: List[str] = []
        while ready:
            # Highest priority first, then lexicographically smallest identifier.
            ready.sort(key=lambda candidate: (-self._nodes[candidate].priority, candidate))
            current = ready.pop(0)
            order.append(current)
            for dependent in sorted(self._downstream.get(current, set())):
                if dependent not in in_degree:
                    # Downstream edges are created only for registered nodes.
                    with unreachable:
                        continue
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
        if len(order) != len(self._nodes):
            # A residual in-degree means the graph still contains a cycle.
            cycle = self._detect_cycle()
            if cycle is not None:
                raise dag_engine_lite.CycleError(
                    message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle=cycle,
                )
            # The cycle traversal always discovers the cycle implied by the
            # residual in-degree, so this fallback is never reached.
            with unreachable:
                raise dag_engine_lite.CycleError(
                    message="Dependency cycle detected in the graph",
                    cycle=(),
                )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id for node_id in self._nodes if not self._upstream.get(node_id)
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id for node_id in self._nodes if not self._downstream.get(node_id)
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return ([], 0.0)
        durations: Mapping[str, float] = (
            estimated_durations if estimated_durations is not None else {}
        )
        # Earliest finishing time of every node given its upstream dependencies.
        earliest: Dict[str, float] = {}
        for node_id in order:
            duration = float(durations.get(node_id, 1.0))
            upstream = self._upstream.get(node_id, set())
            best_upstream = max(
                (earliest[dependency] for dependency in upstream),
                default=0.0,
            )
            earliest[node_id] = best_upstream + duration
        terminal = min(order, key=lambda candidate: (-earliest[candidate], candidate))
        path: List[str] = []
        current = terminal
        # Walk backwards through the upstream edge that produced the finish time.
        while True:
            path.append(current)
            upstream = self._upstream.get(current, set())
            if not upstream:
                break
            current = min(
                upstream, key=lambda dependency: (-earliest[dependency], dependency)
            )
        path.reverse()
        return (path, earliest[terminal])

    def _detect_cycle(self) -> Optional[Tuple[str, ...]]:
        """Returns the first directed cycle discovered, or None for an acyclic graph."""
        visited: Set[str] = set()
        active: Dict[str, int] = {}
        path: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            if node_id in active:
                return tuple(path[active[node_id] :] + [node_id])
            if node_id in visited:
                return None
            active[node_id] = len(path)
            path.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                cycle = visit(dependency)
                if cycle is not None:
                    return cycle
            path.pop()
            del active[node_id]
            visited.add(node_id)
            return None

        for node_id in sorted(self._nodes):
            cycle = visit(node_id)
            if cycle is not None:
                return cycle
        return None


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete sequential wave scheduler tracking the lifecycle state of every node."""

    tier = "system"

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}
        self._definitions: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        self._sync()
        ready: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            # A ready node may only execute once every upstream dependency succeeded.
            if self._upstream_satisfied(node_id):
                ready.append(node_id)
        ready.sort(
            key=lambda candidate: (-self._dag.get_node(candidate).priority, candidate)
        )
        return ready

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._sync()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._sync()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Promote every dependent that is now unblocked by the successful node.
        for dependent in sorted(self._dag.get_dependents(node_id)):
            if self._states.get(dependent) is not dag_engine_lite.NodeState.PENDING:
                continue
            if self._upstream_satisfied(dependent):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        self._sync()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Every remaining non-terminal node is cancelled immediately.
            for candidate in list(self._states):
                if candidate == node_id:
                    continue
                if self._states[candidate] in terminal:
                    continue
                self._states[candidate] = dag_engine_lite.NodeState.CANCELLED
            return
        if failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # Every transitive dependent becomes unreachable and is skipped.
            for dependent in sorted(self._transitive_dependents(node_id)):
                current = self._states.get(dependent)
                if current is None or current in terminal:
                    continue
                self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
            return
        # Continued execution skips only dependents blocked behind a failed upstream.
        blocked: Set[str] = set()
        for candidate, state in self._states.items():
            if state is not dag_engine_lite.NodeState.FAILED:
                continue
            blocked.update(self._transitive_dependents(candidate))
        for dependent in sorted(blocked):
            current = self._states.get(dependent)
            if current is None or current in terminal:
                continue
            self._states[dependent] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        self._sync()
        terminal = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        for node_id, state in self._states.items():
            if state in terminal:
                continue
            # A running node, or one whose upstream dependencies all succeeded,
            # remains eligible to execute so the run is not finished.
            if state is dag_engine_lite.NodeState.RUNNING:
                return False
            if self._upstream_satisfied(node_id):
                return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if not self._dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the graph",
                node_id=node_id,
            )
        self._sync()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync()
        # Expose state only for nodes that remain registered in the graph.
        return {
            node_id: self._states[node_id]
            for node_id in self._dag.all_nodes()
            if node_id in self._states
        }

    def _sync(self) -> None:
        """Aligns tracked state with the currently registered graph nodes."""
        registered = self._dag.all_nodes()
        for node_id in list(self._states):
            if node_id not in registered:
                del self._states[node_id]
                self._definitions.pop(node_id, None)
        for node_id in sorted(registered):
            definition = self._dag.get_node(node_id)
            # A node removed and later re-added starts scheduling from scratch.
            if node_id in self._states and self._definitions.get(node_id) is definition:
                continue
            self._definitions[node_id] = definition
            # Roots begin ready; every node with upstream dependencies begins
            # pending until its dependencies are explicitly marked succeeded.
            if self._dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine_lite.NodeState.READY

    def _upstream_satisfied(self, node_id: str) -> bool:
        """Checks whether every direct upstream dependency has succeeded."""
        for dependency in self._dag.get_dependencies(node_id):
            if self._states.get(dependency) is not dag_engine_lite.NodeState.SUCCEEDED:
                return False
        return True

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        """Collects every node reachable through downstream dependency edges."""
        collected: Set[str] = set()
        pending: List[str] = sorted(self._dag.get_dependents(node_id))
        while pending:
            current = pending.pop()
            if current in collected:
                continue
            collected.add(current)
            pending.extend(sorted(self._dag.get_dependents(current)))
        return collected


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete sequential runner executing DAG waves to completion under failure policies."""

    tier = "system"

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
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        # Reject incomplete or cyclic graphs before any node action executes.
        self._dag.validate()
        started_at = time.perf_counter()
        self._results = {}
        halted = False
        while not halted and not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                # Stop when the scheduler cannot surface another executable wave,
                # so the run terminates and still reports its consolidated results.
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                result = self._execute(definition)
                self._results[node_id] = result
                if result.state is dag_engine_lite.NodeState.SUCCEEDED:
                    self._scheduler.mark_succeeded(node_id)
                    continue
                self._scheduler.mark_failed(node_id, failure_policy)
                if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                    halted = True
                    break
        # Record unexecuted nodes that the scheduler resolved to a terminal skip
        # or cancel state.
        for node_id, state in self._scheduler.get_all_states().items():
            if node_id in self._results:
                continue
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id, state=state
                )
        critical_path, _critical_weight = self._dag.compute_critical_path(None)
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
        elapsed = time.perf_counter() - started_at
        results: Mapping[str, dag_engine_lite.NodeResult[Any]] = dict(self._results)
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=elapsed,
            critical_path=tuple(critical_path),
            results=results,
        )

    def _execute(
        self, definition: dag_engine_lite.NodeDefinition[Any]
    ) -> dag_engine_lite.NodeResult[Any]:
        """Invokes the node action, retrying failures up to the configured count."""
        retries_attempted = 0
        started_at = time.perf_counter()
        value: Any = None
        error: Optional[Exception] = None
        while True:
            try:
                value = definition.action()
            except Exception as caught:  # cleanroom: allow-broad-exception
                error = caught
                if retries_attempted >= definition.retries:
                    break
                retries_attempted += 1
                continue
            # A later successful attempt clears the failure captured by an earlier one.
            error = None
            break
        elapsed = time.perf_counter() - started_at
        if error is None:
            return dag_engine_lite.NodeResult(
                node_id=definition.node_id,
                state=dag_engine_lite.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=elapsed,
                retries_attempted=retries_attempted,
            )
        return dag_engine_lite.NodeResult(
            node_id=definition.node_id,
            state=dag_engine_lite.NodeState.FAILED,
            error=error,
            duration_seconds=elapsed,
            retries_attempted=retries_attempted,
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T01:08:16Z
# LAST_CHANGED: 2026-11-12T01:01:52Z
# CHANGE: Resolve QA blast [slug:dag_lite.runner.run.sequential_waves]: the empty-wave termination path in DAGRunner.run is reachable, so its 'with unreachable:' quarantine was removed and the plain break restored. A scheduler holding a pending node whose upstream already succeeded reports is_finished=False while next_wave returns no executable nodes; run() now stops the wave loop and returns the consolidated DAGRunReport instead of raising AssertionError (exp=DAGRunReport, obs=AssertionError). Sibling quarantines for the topological-sort registration guard and the residual-in-degree cycle fallback remain unreachable under graph invariants and are unchanged.
# COVERAGE_AUDIT: 2026-11-12T01:02:34Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T01:08:16Z
# PRETENSE_QA_AUDIT: 2026-11-12T01:08:03Z
# QA_AUDIT: 2026-11-12T01:02:18Z
# --- END AUTOFAB METADATA ---
