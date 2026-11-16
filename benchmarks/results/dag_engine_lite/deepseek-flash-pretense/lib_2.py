# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261115_155756_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-15T15:57:56.822305+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 381,902
#   Cached Inbound Tokens:   52,202,877
#   Outbound Tokens:         446,499
#   Total Tokens:            53,031,278
#   Financial Cost ($USD):   $0.4818
#   Wall Clock Duration:     3377.15s
#   Step Latencies (s):      [271.2, 1527.2, 286.7, 81.9, 143.5, 380.0, 133.2, 20.3, 205.0, 43.1, 143.6, 135.4, 92.3, 40.9, 10.1, 61.4, 30.6, 20.4, 20.3]
#   Role Execution Rounds:   lib: 2, pretense_coverage: 3, pretense_impl: 5, pretense_intf: 3, pretense_qa: 6 (Total: 19)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       6
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface specification for the synchronous DAG execution and wave scheduling engine."""

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
    """Base exception for all DAG engine errors."""

    message: str

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the graph."""

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the graph."""

    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Raised when a node identifier is already registered in the graph."""

    node_id: str


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution."""

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
    """Immutable definition of a task node in the directed acyclic graph."""

    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@data_type
@dataclass(frozen=True)
class NodeResult(Generic[T]):
    """Outcome record of a node execution."""

    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@data_type
@dataclass(frozen=True)
class DAGRunReport:
    """Consolidated summary report of an entire DAG execution run."""

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
        estimated_durations: Optional[Mapping[str, float]],
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
        failure_policy: FailurePolicy,
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
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T16:02:21Z
# LAST_CHANGED: 2026-11-15T16:02:21Z
# CHANGE: Author interface module: DAGEngine error hierarchy (DAGError, CycleError, NodeNotFoundError, DuplicateNodeError, NodeExecutionError), NodeState/FailurePolicy enums, NodeDefinition/NodeResult/DAGRunReport data types, and DAG/WaveScheduler/DAGRunner service protocols with operation stubs.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete realization of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite

_TERMINAL_STATES = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

_FAILURE_STATES = frozenset(
    {
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)


@singleton
class DAG(dag_engine_lite.DAG):
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
        # Duplicate identifiers would silently overwrite an existing definition.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )
        dependency_set: frozenset[str] = (
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
        # Dependency existence is validated later, so edges are recorded unconditionally.
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{upstream_id}' is not registered in the DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{downstream_id}' is not registered in the DAG",
                node_id=downstream_id,
            )
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        # Incident edges are purged from both neighbor directions before deletion.
        for upstream_id in set(self._upstream.get(node_id, set())):
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in set(self._downstream.get(node_id, set())):
            self._upstream.get(downstream_id, set()).discard(node_id)
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
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return definition

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Every referenced dependency must be a registered node before ordering.
        for node_id, definition in self._nodes.items():
            for dependency in definition.dependencies:
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=(
                            f"Node '{node_id}' depends on unregistered node '{dependency}'"
                        ),
                        node_id=dependency,
                    )
        self.topological_sort()

    @operation
    @override
    def topological_sort(self) -> List[str]:
        node_ids = set(self._nodes.keys())
        # Only dependencies inside the registered node set contribute to in-degree.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()) & node_ids)
            for node_id in node_ids
        }
        heap: List[Tuple[int, str]] = []
        for node_id in node_ids:
            if in_degree[node_id] == 0:
                heapq.heappush(heap, (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while heap:
            _, node_id = heapq.heappop(heap)
            order.append(node_id)
            for dependent in self._downstream.get(node_id, set()):
                # Downstream targets of a registered node are always registered.
                if dependent not in in_degree:
                    with unreachable:
                        continue
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(
                        heap, (-self._nodes[dependent].priority, dependent)
                    )
        if len(order) != len(node_ids):
            remaining = node_ids - set(order)
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=self._find_cycle(remaining),
            )
        return order

    def _find_cycle(self, remaining: Set[str]) -> Tuple[str, ...]:
        # Depth-first back-edge search isolates one cyclic sequence for diagnostics.
        visited_state: Dict[str, int] = {node_id: 0 for node_id in remaining}
        cycle_path: List[str] = []

        def search(current: str, stack: List[str]) -> bool:
            visited_state[current] = 1
            stack.append(current)
            for dependent in self._downstream.get(current, set()):
                # Cyclic nodes only reference other cyclic nodes downstream.
                if dependent not in remaining:
                    with unreachable:
                        continue
                if visited_state[dependent] == 1:
                    index = stack.index(dependent)
                    cycle_path.extend(stack[index:] + [dependent])
                    return True
                if visited_state[dependent] == 0 and search(dependent, stack):
                    return True
            stack.pop()
            visited_state[current] = 2
            return False

        for node_id in sorted(remaining):
            if visited_state[node_id] == 0 and search(node_id, []):
                break
        return tuple(cycle_path) if cycle_path else tuple(sorted(remaining))

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id, set())
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not self._downstream.get(node_id, set())
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return [], 0.0
        # Forward accumulation of earliest completion times along the topological order.
        earliest_finish: Dict[str, float] = {}
        best_parent: Dict[str, Optional[str]] = {}
        for node_id in order:
            duration = (
                estimated_durations.get(node_id, 1.0)
                if estimated_durations is not None
                else 1.0
            )
            predecessors = self._upstream.get(node_id, set())
            if not predecessors:
                earliest_finish[node_id] = duration
                best_parent[node_id] = None
                continue
            best_predecessor = max(
                predecessors,
                key=lambda predecessor: (
                    earliest_finish.get(predecessor, 0.0),
                    predecessor,
                ),
            )
            earliest_finish[node_id] = (
                earliest_finish.get(best_predecessor, 0.0) + duration
            )
            best_parent[node_id] = best_predecessor
        terminal = max(order, key=lambda node_id: (earliest_finish[node_id], node_id))
        total_weight = earliest_finish[terminal]
        # Backtrack from the latest finishing terminal through recorded predecessors.
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = best_parent.get(current)
        path.reverse()
        return path, total_weight


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = "system"

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        # Discover nodes registered after the previous scheduling sweep.
        registered = self._dag.all_nodes()
        for node_id in list(self._states):
            if node_id not in registered:
                del self._states[node_id]
        for node_id in registered:
            if node_id in self._states:
                continue
            if self._dag.get_dependencies(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
            else:
                self._states[node_id] = dag_engine_lite.NodeState.READY

    def _blocked_by_failure(self, node_id: str) -> bool:
        # A node is unreachable when any transitive ancestor has failed or been skipped.
        stack: List[str] = list(self._dag.get_dependencies(node_id))
        visited: Set[str] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if self._states.get(current) in _FAILURE_STATES:
                return True
            if current in self._states:
                stack.extend(self._dag.get_dependencies(current))
        return False

    @operation
    @override
    def next_wave(self) -> List[str]:
        self._sync_states()
        ready: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                ready.append(node_id)
        # Highest priority first, then lexicographically smallest identifier.
        ready.sort(key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id))
        return ready

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Dependents whose entire prerequisite set succeeded become runnable.
        for dependent in self._dag.get_dependents(node_id):
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
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Every remaining non-terminal node is cancelled so the run halts.
            for other_id in list(self._states.keys()):
                if self._states[other_id] not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # Downstream dependents can never run once an ancestor has failed.
        pending: List[str] = list(self._dag.get_dependents(node_id))
        visited: Set[str] = {node_id}
        while pending:
            dependent = pending.pop()
            if dependent in visited:
                continue
            visited.add(dependent)
            if self._states.get(dependent) not in _TERMINAL_STATES:
                self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
            pending.extend(self._dag.get_dependents(dependent))

    @operation
    @override
    def is_finished(self) -> bool:
        self._sync_states()
        if not self._states:
            return True
        for node_id, state in self._states.items():
            if state in _TERMINAL_STATES:
                continue
            if self._blocked_by_failure(node_id):
                continue
            return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self._dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the scheduled DAG",
                node_id=node_id,
            )
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        registered = self._dag.all_nodes()
        return {
            node_id: state
            for node_id, state in self._states.items()
            if node_id in registered
        }


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
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
        self._dag.validate()
        self._results = {}
        start = time.monotonic()
        halted = False
        while not halted and not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_start = time.monotonic()
                retries_attempted = 0
                value: Any = None
                error: Optional[Exception] = None
                while True:
                    try:
                        value = definition.action()
                    except Exception as exc:
                        # Failed attempts are retried until the configured budget runs out.
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        error = exc
                        break
                    else:
                        break
                duration = time.monotonic() - node_start
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
        wall_clock_seconds = time.monotonic() - start
        # Unexecuted terminal nodes still receive result records for the report.
        for node_id, state in self._scheduler.get_all_states().items():
            if node_id in self._results:
                continue
            if state in _TERMINAL_STATES:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        succeeded_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is dag_engine_lite.NodeState.CANCELLED
            )
        )
        critical_path, _ = self._dag.compute_critical_path(None)
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T16:54:03Z
# LAST_CHANGED: 2026-11-15T16:45:30Z
# CHANGE: Quarantine coverage-flagged unreachable guards per guide: import unreachable and wrap the topological_sort in-degree membership guard and the cycle-search remaining-set membership guard in 'with unreachable:' to preserve them as tripwires while acknowledging the adjacency-invariant closure.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T16:54:03Z
# PRETENSE_QA_AUDIT: 2026-11-15T16:53:38Z
# --- END AUTOFAB METADATA ---
