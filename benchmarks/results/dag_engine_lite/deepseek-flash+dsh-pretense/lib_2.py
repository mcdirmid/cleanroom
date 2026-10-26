# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_210709_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-10-26T21:07:09.984444+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 276,811
#   Cached Inbound Tokens:   12,962,816
#   Outbound Tokens:         272,367
#   Total Tokens:            13,511,994
#   Financial Cost ($USD):   $0.2438
#   Wall Clock Duration:     1180.94s
#   Step Latencies (s):      [30.6, 40.5, 90.8, 60.3, 150.6, 20.1, 30.2, 41.4, 262.0, 463.7, 20.1, 120.4, 80.6, 171.1, 20.1, 20.1]
#   Role Execution Rounds:   high: 1, lib: 2, low: 3, planning: 1, pretense: 2, pretense_coverage: 2, pretense_qa: 2, scenario: 1, spec_qa: 2 (Total: 16)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       49
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

from support.lib.framework import data_type, operation, singleton_type, variant
from support.lib.lifecycle import Singleton, SystemTier

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')


@data_type
@dataclass(frozen=True)
class DAGError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@variant
@dataclass(frozen=True)
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@variant
@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    node_id: str


@variant
@dataclass(frozen=True)
class NodeExecutionError(DAGError):
    node_id: str
    cause: Exception


class NodeState(enum.Enum):
    PENDING = 'pending'
    READY = 'ready'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    SKIPPED = 'skipped'


class FailurePolicy(enum.Enum):
    FAIL_FAST = 'fail_fast'
    CONTINUE_ON_ERROR = 'continue_on_error'
    SKIP_DOWNSTREAM = 'skip_downstream'


@data_type
@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@data_type
@dataclass(frozen=True)
class NodeResult(Generic[T]):
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@data_type
@dataclass(frozen=True)
class DAGRunReport:
    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


@singleton_type('system')
class DAG(Singleton[SystemTier], Protocol):
    @operation
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        ...

    @operation
    def validate(self) -> None:
        ...

    @operation
    def topological_sort(self) -> List[str]:
        ...

    @operation
    def find_roots(self) -> Set[str]:
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        ...

    @operation
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        ...


@singleton_type('system')
class WaveScheduler(Singleton[SystemTier], Protocol):
    @operation
    def next_wave(self) -> List[str]:
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        ...

    @operation
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
        ...

    @operation
    def is_finished(self) -> bool:
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        ...


@singleton_type('system')
class DAGRunner(Singleton[SystemTier], Protocol):
    @operation
    def run(self, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> DAGRunReport:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T21:17:21Z
# LAST_CHANGED: 2026-10-26T21:17:21Z
# CHANGE: Implement the DAG interface module: framework-decorated data types (DAGError with __str__ returning message, CycleError/NodeNotFoundError/NodeExecutionError variants), NodeState/FailurePolicy enums, frozen record types (NodeDefinition, NodeResult, DAGRunReport), and abstract Singleton[SystemTier] Protocol singletons (DAG, WaveScheduler, DAGRunner) with ellipsis operation stubs matching low/dag_engine_lite.pyi. Exception __str__ ensures str(exc) returns the diagnostic message for runtime assertions.
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    SystemTier,
    get_default_registry,
    get_singleton,
)

from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi

_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)


@singleton_type('system')
class DAG(dag_engine_lite.DAG):
    tier = SystemTier('system')

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    @override
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        # POSTCONDITION: register the node definition; WHEN dependencies are provided,
        # add edges from each dependency to node_id; defer existence checks to validate().
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
        for upstream_id in dependency_set:
            # Deferred validation: record the edge even when the upstream node is absent.
            self._upstream.setdefault(node_id, set()).add(upstream_id)
            self._downstream.setdefault(upstream_id, set()).add(node_id)

    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN either identifier does not exist, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Upstream node '{upstream_id}' not found in graph",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Downstream node '{downstream_id}' not found in graph",
                node_id=downstream_id,
            )
        # MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @override
    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # MUST remove the node and all incident dependency edges.
        for upstream_id in list(self._upstream.get(node_id, set())):
            downstream_neighbors = self._downstream.get(upstream_id)
            if downstream_neighbors is not None:
                downstream_neighbors.discard(node_id)
        for downstream_id in list(self._downstream.get(node_id, set())):
            upstream_neighbors = self._upstream.get(downstream_id)
            if upstream_neighbors is not None:
                upstream_neighbors.discard(node_id)
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]
        # Purge dangling deferred dependency keys recorded for missing upstream nodes.
        # (_upstream keys are always registered nodes; only _downstream defers an
        # edge whose upstream has not been added yet.)
        for orphan_id in [key for key in self._downstream if key not in self._nodes and not self._downstream[key]]:
            del self._downstream[orphan_id]

    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        definition = self._nodes.get(node_id)
        if definition is None:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        return definition

    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # MUST return all direct upstream dependencies as a defensive copy.
        return set(self._upstream[node_id])

    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # MUST return all direct downstream dependents as a defensive copy.
        return set(self._downstream[node_id])

    @override
    def all_nodes(self) -> Set[str]:
        # MUST return all registered node identifiers as a defensive copy.
        return set(self._nodes.keys())

    @override
    def validate(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for node_id in self._nodes:
            for upstream_id in self._upstream[node_id]:
                if upstream_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on missing node '{upstream_id}'",
                        node_id=upstream_id,
                    )
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}",
                cycle=tuple(cycle),
            )

    @override
    def topological_sort(self) -> List[str]:
        # Missing dependencies cannot participate in an ordering; surface them first.
        for node_id in self._nodes:
            for upstream_id in self._upstream[node_id]:
                if upstream_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on missing node '{upstream_id}'",
                        node_id=upstream_id,
                    )
        # MUST break ties between concurrent ready nodes using priority descending
        # and lexicographical node_id ascending.
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream[node_id]) for node_id in self._nodes
        }
        ready: List[str] = [node_id for node_id, degree in in_degree.items() if degree == 0]
        ready.sort(key=self._priority_key)
        order: List[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for downstream_id in sorted(self._downstream[node_id]):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    ready.append(downstream_id)
            ready.sort(key=self._priority_key)
        # WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            cycle_sequence: Tuple[str, ...] = tuple(cycle) if cycle is not None else ()
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle_sequence)}",
                cycle=cycle_sequence,
            )
        # MUST return a valid topological ordering where every prerequisite precedes
        # its dependents.
        return order

    @override
    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream[node_id]}

    @override
    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream[node_id]}

    @override
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return [], 0.0
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        # Resolve duration weights, defaulting to 1.0 for unspecified nodes.
        durations_by_node: Dict[str, float] = {
            node_id: float(durations.get(node_id, 1.0)) for node_id in order
        }
        # Dynamic programming: earliest completion time for each node.
        earliest: Dict[str, float] = {}
        for node_id in order:
            upstream_ids = self._upstream[node_id]
            predecessor_time = max(
                (earliest[upstream_id] for upstream_id in upstream_ids),
                default=0.0,
            )
            earliest[node_id] = predecessor_time + durations_by_node[node_id]
        # Identify the terminal (leaf) node with the maximum completion time
        # (lexicographical tie-break for determinism).
        terminal_ids = [node_id for node_id in order if not self._downstream[node_id]]
        terminal_id = min(
            terminal_ids,
            key=lambda node_id: (-earliest[node_id], node_id),
        )
        # Backtrack through the predecessor yielding the maximum earliest completion time.
        path: List[str] = [terminal_id]
        current_id = terminal_id
        while self._upstream[current_id]:
            predecessor_ids = list(self._upstream[current_id])
            predecessor = min(
                predecessor_ids,
                key=lambda candidate: (-earliest[candidate], candidate),
            )
            path.append(predecessor)
            current_id = predecessor
        path.reverse()
        # MUST return the longest path sequence and its cumulative weight.
        return path, earliest[terminal_id]

    def _priority_key(self, node_id: str) -> Tuple[int, str]:
        return (-self._nodes[node_id].priority, node_id)

    def _find_cycle(self) -> Optional[List[str]]:
        visited: Set[str] = set()
        active: List[str] = []
        active_set: Set[str] = set()

        def visit(node_id: str) -> Optional[List[str]]:
            if node_id in active_set:
                start = active.index(node_id)
                return active[start:] + [node_id]
            if node_id in visited:
                return None
            visited.add(node_id)
            active.append(node_id)
            active_set.add(node_id)
            for downstream_id in sorted(self._downstream.get(node_id, set())):
                cycle = visit(downstream_id)
                if cycle is not None:
                    return cycle
            active.pop()
            active_set.discard(node_id)
            return None

        for node_id in sorted(self._nodes):
            cycle = visit(node_id)
            if cycle is not None:
                return cycle
        return None


@singleton_type('system')
class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = SystemTier('system')

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @override
    def next_wave(self) -> List[str]:
        dag = self._synchronize()
        self._promote_unblocked(dag)
        # MUST return all READY nodes whose upstream dependencies are all SUCCEEDED,
        # ordered by priority descending, then node_id ascending.
        candidates = [
            node_id
            for node_id in dag.all_nodes()
            if self._states.get(node_id) is dag_engine_lite.NodeState.READY
            and all(
                self._states.get(upstream_id) is dag_engine_lite.NodeState.SUCCEEDED
                for upstream_id in dag.get_dependencies(node_id)
            )
        ]
        candidates.sort(key=lambda node_id: (-dag.get_node(node_id).priority, node_id))
        # WHEN no nodes are ready, MUST return an empty list.
        return candidates

    @override
    def mark_running(self, node_id: str) -> None:
        self._synchronize()
        # MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @override
    def mark_succeeded(self, node_id: str) -> None:
        dag = self._synchronize()
        # MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        self._promote_unblocked(dag)

    @override
    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy=dag_engine_lite.FailurePolicy.FAIL_FAST) -> None:
        dag = self._synchronize()
        # MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # WHEN FAIL_FAST, MUST transition all remaining non-terminal nodes to CANCELLED.
            for other_id in dag.all_nodes():
                if self._states.get(other_id) not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # WHEN SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
            for dependent_id in self._transitive_dependents(dag, node_id):
                if self._states.get(dependent_id) not in _TERMINAL_STATES:
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED
        else:
            # WHEN CONTINUE_ON_ERROR, leave unblocked independent nodes eligible,
            # but transition all blocked dependents of the failed node to SKIPPED.
            for dependent_id in self._transitive_dependents(dag, node_id):
                if self._states.get(dependent_id) not in _TERMINAL_STATES:
                    self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED

    @override
    def is_finished(self) -> bool:
        dag = self._synchronize()
        registered = dag.all_nodes()
        # WHEN the DAG contains no nodes, MUST return True.
        if not registered:
            return True
        for node_id in registered:
            state = self._states.get(node_id)
            if state in _TERMINAL_STATES:
                continue
            # A non-terminal node remains eligible while every prerequisite succeeded.
            dependencies = dag.get_dependencies(node_id)
            if all(
                self._states.get(upstream_id) is dag_engine_lite.NodeState.SUCCEEDED
                for upstream_id in dependencies
            ):
                return False
        # WHEN all nodes are terminal, or no executable node remains because
        # uncompleted nodes are blocked by failed dependencies, MUST return True.
        return True

    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        self._synchronize()
        return self._states[node_id]

    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        dag = self._synchronize()
        registered = dag.all_nodes()
        # Return a shallow copy filtered to currently registered nodes.
        return {
            node_id: self._states[node_id]
            for node_id in registered
            if node_id in self._states
        }

    def _synchronize(self) -> dag_engine_lite.DAG:
        dag = get_singleton(dag_engine_lite.DAG)
        self._dag = dag
        registered = dag.all_nodes()
        # Purge scheduling state recorded for nodes removed from the graph.
        for stale_id in [node_id for node_id in self._states if node_id not in registered]:
            del self._states[stale_id]
        roots = dag.find_roots()
        # Initialize roots to READY and non-root nodes to PENDING.
        for node_id in registered:
            if node_id in self._states:
                continue
            if node_id in roots:
                self._states[node_id] = dag_engine_lite.NodeState.READY
            else:
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
        return dag

    def _promote_unblocked(self, dag: dag_engine_lite.DAG) -> None:
        for node_id in dag.all_nodes():
            if self._states.get(node_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            if all(
                self._states.get(upstream_id) is dag_engine_lite.NodeState.SUCCEEDED
                for upstream_id in dag.get_dependencies(node_id)
            ):
                self._states[node_id] = dag_engine_lite.NodeState.READY

    def _transitive_dependents(self, dag: dag_engine_lite.DAG, node_id: str) -> List[str]:
        collected: List[str] = []
        seen: Set[str] = set()
        frontier: List[str] = list(dag.get_dependents(node_id))
        while frontier:
            current = frontier.pop(0)
            if current in seen:
                continue
            seen.add(current)
            collected.append(current)
            frontier.extend(dag.get_dependents(current))
        return collected


@singleton_type('system')
class DAGRunner(dag_engine_lite.DAGRunner):
    tier = SystemTier('system')

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @override
    def run(self, failure_policy: dag_engine_lite.FailurePolicy=dag_engine_lite.FailurePolicy.FAIL_FAST) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler
        # MUST validate graph invariants before commencing wave execution.
        dag.validate()
        self._results = {}
        start_time = time.monotonic()
        halted = False
        # MUST execute ready waves sequentially.
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            # Halts the wave loop when no ready wave remains (grounding).
            if not wave:  # pragma: no cover (assumption: is_finished() is False only while a dependency-satisfied non-terminal node exists, which next_wave() promotes and returns)
                break
            for node_id in wave:
                definition = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                value: Any = None
                error: Optional[Exception] = None
                retries_attempted = 0
                node_start = time.monotonic()
                while True:
                    try:
                        value = definition.action()
                        error = None
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        error = exc
                        # MUST execute retries up to the configured retry count.
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        break
                duration_seconds = time.monotonic() - node_start
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        error=None,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=error,
                        duration_seconds=duration_seconds,
                        retries_attempted=retries_attempted,
                    )
                    # MUST apply the specified failure policy upon node failure.
                    scheduler.mark_failed(node_id, failure_policy)
                    # Halts further wave execution on FAIL_FAST after a failure.
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
            if halted:
                break
        wall_clock_seconds = time.monotonic() - start_time
        states = scheduler.get_all_states()
        # Populate default unexecuted records for terminal skipped or cancelled nodes.
        for node_id, state in states.items():
            if node_id in self._results:
                continue
            if state in (dag_engine_lite.NodeState.SKIPPED, dag_engine_lite.NodeState.CANCELLED):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        # Critical path is computed from the validated graph structure.
        critical_path, _ = dag.compute_critical_path()
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
        # MUST return a consolidated report capturing all node outcomes and metrics.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
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
# LAST_CLEANED: 2026-10-26T21:26:40Z
# LAST_CHANGED: 2026-10-26T21:26:00Z
# CHANGE: Resolve unreachable-branch feedback: eliminate the dead _upstream orphan purge in DAG.remove_node (keys are always registered nodes; only _downstream defers edges for not-yet-added upstreams, whose cleanup remains reachable) and remove the dead unregistered-node guard in _find_cycle; annotate the contractually mandated empty-wave halt in DAGRunner.run with '# pragma: no cover (assumption: is_finished() is False only while a dependency-satisfied non-terminal node exists, which next_wave() promotes and returns)' per the grounding's halts-wave-loop-when-next-wave-is-empty requirement. Runtime behavior unchanged (regression verified: wave dispatch, retries, all failure policies, cycle/missing-dep detection, scheduler purge).
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T21:26:40Z
# PRETENSE_QA_AUDIT: 2026-10-26T21:26:17Z
# --- END CLEANROOM METADATA ---
