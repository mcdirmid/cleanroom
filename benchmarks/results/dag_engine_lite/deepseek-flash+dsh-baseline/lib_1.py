# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261102_233551_deepseek-flash_dag_engine_lite_baseline
# Timestamp: 2026-11-02T23:35:51.903204+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 46,100
#   Cached Inbound Tokens:   1,750,016
#   Outbound Tokens:         52,252
#   Total Tokens:            1,848,368
#   Financial Cost ($USD):   $0.0435
#   Wall Clock Duration:     293.74s
#   Step Latencies (s):      [286.2]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       30
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Low-level interface specification for the synchronous DAG execution and wave scheduling engine."""

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
        """Adds a task node to the graph."""
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        ...

    @operation
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node."""
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
        ...


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:40:45Z
# LAST_CHANGED: 2026-11-02T23:40:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4a6b58035c39
# COVERAGE_AUDIT: 2026-11-02T23:40:45Z
# QA_AUDIT: 2026-11-02T23:40:45Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete realization of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system

from . import dag_engine_lite

# States from which a node never becomes eligible to execute again.
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
        # MUST register the node definition into the graph, deferring dependency validation.
        dependency_set: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
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
        self._upstream[node_id] = set(dependency_set)
        # WHEN dependencies are provided, MUST add directed dependency edges to node_id.
        for upstream_id in dependency_set:
            self._downstream.setdefault(upstream_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN either endpoint is absent, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{upstream_id}' does not exist in the graph.",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{downstream_id}' does not exist in the graph.",
                node_id=downstream_id,
            )
        # MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id=node_id,
            )
        # MUST remove the node and its incident edges from every neighbor set.
        for upstream_id in self._upstream[node_id]:
            self._downstream[upstream_id].discard(node_id)
        for downstream_id in self._downstream[node_id]:
            self._upstream[downstream_id].discard(node_id)
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id=node_id,
            )
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in the graph.",
                node_id=node_id,
            )
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for definition in self._nodes.values():
            for dependency in definition.dependencies:
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{definition.node_id}' depends on missing node '{dependency}'.",
                        node_id=dependency,
                    )
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                "Dependency cycle detected in the graph.",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Deterministic Kahn sweep: priority descending, then node_id ascending.
        in_degree: Dict[str, int] = {node_id: len(self._upstream[node_id]) for node_id in self._nodes}
        ready: List[Tuple[int, str]] = [
            (-self._nodes[node_id].priority, node_id)
            for node_id in self._nodes
            if in_degree[node_id] == 0
        ]
        heapq.heapify(ready)
        order: List[str] = []
        while ready:
            _, node_id = heapq.heappop(ready)
            order.append(node_id)
            for downstream_id in sorted(self._downstream[node_id]):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    heapq.heappush(ready, (-self._nodes[downstream_id].priority, downstream_id))
        # WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            remaining = tuple(sorted(set(self._nodes.keys()) - set(order)))
            raise dag_engine_lite.CycleError(
                "Dependency cycle detected in the graph.",
                cycle=self._find_cycle() or remaining,
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream[node_id]}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream[node_id]}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return ([], 0.0)
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        earliest: Dict[str, float] = {}
        # Dynamically compute earliest completion times in topological order.
        for node_id in order:
            upstream_completion = [earliest[upstream_id] for upstream_id in self._upstream[node_id]]
            earliest[node_id] = max(upstream_completion, default=0.0) + durations.get(node_id, 1.0)
        # Backtrack from the terminal node with the greatest completion time.
        terminal_id = max(sorted(order), key=lambda candidate: earliest[candidate])
        path: List[str] = []
        current_id = terminal_id
        while True:
            path.append(current_id)
            upstream_ids = sorted(self._upstream[current_id])
            if not upstream_ids:
                break
            current_id = max(upstream_ids, key=lambda candidate: earliest[candidate])
        path.reverse()
        return (path, earliest[terminal_id])

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        visiting: Set[str] = set()
        visited: Set[str] = set()
        path: List[str] = []

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            if node_id in visiting:
                return tuple(path[path.index(node_id):] + [node_id])
            if node_id in visited:
                return None
            visiting.add(node_id)
            path.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                cycle = visit(dependency)
                if cycle is not None:
                    return cycle
            path.pop()
            visiting.discard(node_id)
            visited.add(node_id)
            return None

        for node_id in sorted(self._nodes):
            cycle = visit(node_id)
            if cycle is not None:
                return cycle
        return None


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @operation
    @override
    def next_wave(self) -> List[str]:
        self._sync_states()
        # MUST return READY nodes whose upstream dependencies are all SUCCEEDED.
        ready: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in self._dag.get_dependencies(node_id)
            ):
                ready.append(node_id)
        # MUST order by priority descending, then node_id ascending.
        ready.sort(key=lambda candidate: (-self._dag.get_node(candidate).priority, candidate))
        return ready

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST promote newly unblocked PENDING dependents to READY.
        for dependent_id in self._dag.get_dependents(node_id):
            if self._states.get(dependent_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in self._dag.get_dependencies(dependent_id)
            ):
                self._states[dependent_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if (
            failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            or failure_policy is dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        ):
            # Blocked transitive dependents of the failed node become SKIPPED.
            for dependent_id in self._blocked_dependents(node_id):
                if self._states.get(dependent_id) not in _TERMINAL_STATES:
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
            return
        # FAIL_FAST cancels every remaining non-terminal node.
        for other_id, state in list(self._states.items()):
            if state not in _TERMINAL_STATES:
                self._states[other_id] = dag_engine_lite.NodeState.CANCELLED

    @operation
    @override
    def is_finished(self) -> bool:
        self._sync_states()
        registered = self._dag.all_nodes()
        # WHEN the DAG contains no nodes, MUST return True.
        if not registered:
            return True
        # WHEN all nodes reached terminal states, MUST return True.
        if all(self._states[node_id] in _TERMINAL_STATES for node_id in registered):
            return True
        # WHEN no ready nodes remain, unexecuted nodes are blocked, so MUST return True.
        return not self.next_wave()

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self._states:
            self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        return {
            node_id: self._states[node_id]
            for node_id in sorted(self._dag.all_nodes())
        }

    def _sync_states(self) -> None:
        registered = self._dag.all_nodes()
        # Purge scheduling state for nodes removed from the graph.
        for node_id in list(self._states.keys()):
            if node_id not in registered:
                del self._states[node_id]
        # Discover registered nodes: roots are READY, non-roots start PENDING.
        for node_id in registered:
            if node_id not in self._states:
                if self._dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY

    def _blocked_dependents(self, node_id: str) -> Set[str]:
        blocked: Set[str] = set()
        pending: List[str] = list(self._dag.get_dependents(node_id))
        while pending:
            dependent_id = pending.pop()
            if dependent_id in blocked:
                continue
            blocked.add(dependent_id)
            pending.extend(self._dag.get_dependents(dependent_id))
        return blocked


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        # MUST validate graph invariants before commencing wave execution.
        self._dag.validate()
        started_at = time.monotonic()
        self._results = {}
        halted = False
        # MUST execute ready waves sequentially until no eligible nodes remain.
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            for node_id in wave:
                result = self._execute_node(node_id, failure_policy)
                # Halts further wave execution on FAIL_FAST failure.
                if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST and result.state is dag_engine_lite.NodeState.FAILED:
                    halted = True
                    break
            # Stop scheduling new waves once a FAIL_FAST failure has halted the run.
            if halted:
                break
        # Record default outcomes for nodes that never executed (skipped or cancelled).
        for node_id, state in self._scheduler.get_all_states().items():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(node_id=node_id, state=state)
        critical_path, _total_weight = self._dag.compute_critical_path()
        succeeded_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.SUCCEEDED)
        )
        failed_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.FAILED)
        )
        skipped_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.SKIPPED)
        )
        cancelled_nodes = tuple(
            sorted(node_id for node_id, result in self._results.items() if result.state is dag_engine_lite.NodeState.CANCELLED)
        )
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=time.monotonic() - started_at,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

    def _execute_node(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.NodeResult[Any]:
        definition = self._dag.get_node(node_id)
        self._scheduler.mark_running(node_id)
        started_at = time.monotonic()
        attempts = 0
        value: Any = None
        error: Optional[Exception] = None
        while True:
            try:
                value = definition.action()
            except Exception as exc:  # cleanroom: allow-broad-exception
                # Capture the caught exception instance for the result record.
                error = exc
                # MUST execute retries up to the configured retry count.
                if attempts >= definition.retries:
                    break
                attempts += 1
            else:
                # Successful execution clears any error captured by earlier attempts.
                error = None
                break
        duration_seconds = time.monotonic() - started_at
        if error is None:
            result: dag_engine_lite.NodeResult[Any] = dag_engine_lite.NodeResult(
                node_id=node_id,
                state=dag_engine_lite.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=duration_seconds,
                retries_attempted=attempts,
            )
            self._scheduler.mark_succeeded(node_id)
        else:
            result = dag_engine_lite.NodeResult(
                node_id=node_id,
                state=dag_engine_lite.NodeState.FAILED,
                error=error,
                duration_seconds=duration_seconds,
                retries_attempted=attempts,
            )
            # MUST apply the configured failure policy upon node failure.
            self._scheduler.mark_failed(node_id, failure_policy)
        self._results[node_id] = result
        return result


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
# LAST_CLEANED: 2026-11-02T23:40:45Z
# LAST_CHANGED: 2026-11-02T23:40:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 96e9b3429f14
# COVERAGE_AUDIT: 2026-11-02T23:40:45Z
# QA_AUDIT: 2026-11-02T23:40:45Z
# --- END AUTOFAB METADATA ---
