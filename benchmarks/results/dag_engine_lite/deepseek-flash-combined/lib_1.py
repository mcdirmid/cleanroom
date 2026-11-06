# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_205515_deepseek-flash_dag_engine_lite_combined
# Timestamp: 2026-11-05T20:55:15.226181+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 674,312
#   Cached Inbound Tokens:   70,502,527
#   Outbound Tokens:         697,200
#   Total Tokens:            71,874,039
#   Financial Cost ($USD):   $0.7310
#   Wall Clock Duration:     3428.50s
#   Step Latencies (s):      [195.2, 347.4, 10.7, 242.5, 685.1, 92.6, 10.7, 97.9, 97.9, 11.0, 44.2, 67.0, 65.5, 65.2, 10.6, 10.6, 585.7, 148.3, 148.6, 86.3, 10.4, 201.3, 162.1, 11.2, 233.0, 130.2, 119.2, 84.7, 43.9, 68.4, 64.8, 52.8, 42.7, 13.2, 10.7, 48.5, 33.3, 63.9, 42.2, 14.4, 21.9, 89.9, 34.0, 10.3, 84.9, 67.9, 11.4, 75.2, 44.8, 10.7, 10.3]
#   Role Execution Rounds:   coverage: 7, lib: 7, pretense: 10, pretense_coverage: 5, pretense_qa: 13, qa: 6, test: 3 (Total: 51)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       59
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.lifecycle import Singleton, SystemTier, system
import enum

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')

@dataclass
class DAGError(Exception):
    # Base exception for all DAG engine errors; message carries diagnostics.
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class CycleError(DAGError):
    # Raised when a dependency cycle is detected within the DAG; cycle holds the sequence.
    cycle: Tuple[str, ...]


@dataclass
class NodeNotFoundError(DAGError):
    # Raised when a referenced node identifier is absent from the DAG.
    node_id: str


@dataclass
class DuplicateNodeError(DAGError):
    # Raised when adding a node identifier that is already registered.
    node_id: str


@dataclass
class NodeExecutionError(DAGError):
    # Raised when an unhandled exception occurs during node action execution.
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


@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    # TODO_NodeDefinition_body
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    # TODO_NodeResult_body
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@dataclass(frozen=True)
class DAGRunReport:
    # TODO_DAGRunReport_body
    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


class DAG(Singleton[SystemTier], Protocol):
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
        # TODO_add_node_body
        ...

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # TODO_add_edge_body
        ...

    def remove_node(self, node_id: str) -> None:
        # TODO_remove_node_body
        ...

    def has_node(self, node_id: str) -> bool:
        # TODO_has_node_body
        ...

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        # TODO_get_node_body
        ...

    def get_dependencies(self, node_id: str) -> Set[str]:
        # TODO_get_dependencies_body
        ...

    def get_dependents(self, node_id: str) -> Set[str]:
        # TODO_get_dependents_body
        ...

    def all_nodes(self) -> Set[str]:
        # TODO_all_nodes_body
        ...

    def validate(self) -> None:
        # TODO_validate_body
        ...

    def topological_sort(self) -> List[str]:
        # TODO_topological_sort_body
        ...

    def find_roots(self) -> Set[str]:
        # TODO_find_roots_body
        ...

    def find_leaves(self) -> Set[str]:
        # TODO_find_leaves_body
        ...

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        # TODO_compute_critical_path_body
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    def next_wave(self) -> List[str]:
        # TODO_next_wave_body
        ...

    def mark_running(self, node_id: str) -> None:
        # TODO_mark_running_body
        ...

    def mark_succeeded(self, node_id: str) -> None:
        # TODO_mark_succeeded_body
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        # TODO_mark_failed_body
        ...

    def is_finished(self) -> bool:
        # TODO_is_finished_body
        ...

    def get_state(self, node_id: str) -> NodeState:
        # TODO_get_state_body
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        # TODO_get_all_states_body
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        # TODO_run_body
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T20:58:40Z
# LAST_CHANGED: 2026-11-05T20:58:40Z
# CHANGE: Implement DAG engine interface module: non-frozen dataclass exception hierarchy (DAGError/CycleError/NodeNotFoundError/DuplicateNodeError/NodeExecutionError) with __str__ delegating to message, transition enums, and singleton Protocol definitions matching low/dag_engine_lite.pyi.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi

class DAG(dag_engine_lite.DAG):
    tier = system

    def __init__(self) -> None:
        # Private adjacency storage backing the graph structure.
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
        # Duplicate identifier is a checked precondition violation.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                f"Node '{node_id}' is already registered in the graph",
                node_id,
            )
        # Immutable definition stores the frozen dependency set without eager existence checks.
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
        # Directed dependency edges from each dependency to node_id are recorded eagerly,
        # while missing dependency existence is deferred to validate()/topological_sort().
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Both endpoints are checked preconditions.
        for endpoint in (upstream_id, downstream_id):
            if endpoint not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    f"Node '{endpoint}' is not registered in the graph",
                    endpoint,
                )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        # Existence is a checked precondition.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the graph",
                node_id,
            )
        # Purge incident edges from every neighbor set.
        for upstream_id in self._upstream[node_id]:
            self._downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self._downstream[node_id]:
            self._upstream.get(downstream_id, set()).discard(node_id)
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # Existence is a checked precondition.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the graph",
                node_id,
            )
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        # Existence is a checked precondition.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the graph",
                node_id,
            )
        return set(self._upstream[node_id])

    def get_dependents(self, node_id: str) -> Set[str]:
        # Existence is a checked precondition.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the graph",
                node_id,
            )
        return set(self._downstream[node_id])

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def validate(self) -> None:
        # Every referenced dependency edge must target a registered node.
        for node_id, upstream_ids in self._upstream.items():
            for upstream_id in upstream_ids:
                if upstream_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' references unknown dependency '{upstream_id}'",
                        upstream_id,
                    )
        # Depth-first cycle detection with an explicit active recursion path.
        visited: Set[str] = set()
        active: List[str] = []

        def visit(current_id: str) -> None:
            if current_id in active:
                start = active.index(current_id)
                cycle = tuple(active[start:] + [current_id])
                raise dag_engine_lite.CycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}",
                    cycle,
                )
            if current_id in visited:
                return
            active.append(current_id)
            for dependency in sorted(self._upstream.get(current_id, set())):
                if dependency in self._nodes:
                    visit(dependency)
            active.pop()
            visited.add(current_id)

        for node_id in sorted(self._nodes):
            visit(node_id)

    def topological_sort(self) -> List[str]:
        # In-degree counts derive from the upstream adjacency mapping.
        in_degree: Dict[str, int] = {}
        for node_id in self._nodes:
            in_degree[node_id] = len(
                [dep for dep in self._upstream.get(node_id, set()) if dep in self._nodes]
            )
        # Ready queue maintains priority descending, then node_id ascending.
        ready: List[str] = sorted(
            [node_id for node_id, degree in in_degree.items() if degree == 0],
            key=lambda node_id: (-self._nodes[node_id].priority, node_id),
        )
        ordered: List[str] = []
        while ready:
            # Highest priority candidate is extracted first.
            current_id = ready.pop(0)
            ordered.append(current_id)
            for dependent_id in sorted(self._downstream.get(current_id, set())):
                # Every recorded dependent of a registered node is itself registered,
                # so the in-degree map always covers this identifier.
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    ready.append(dependent_id)
            ready.sort(key=lambda node_id: (-self._nodes[node_id].priority, node_id))
        if len(ordered) != len(self._nodes):
            # Locate a concrete cycle among the unresolved nodes for diagnostics.
            remaining = set(self._nodes) - set(ordered)
            active: List[str] = []
            cycle: Tuple[str, ...] = ()

            def visit(current_id: str) -> None:
                nonlocal cycle
                if cycle:
                    return
                if current_id in active:
                    start = active.index(current_id)
                    cycle = tuple(active[start:] + [current_id])
                    return
                active.append(current_id)
                for dependency in sorted(self._upstream.get(current_id, set())):
                    if dependency in remaining:
                        visit(dependency)
                active.pop()

            for node_id in sorted(remaining):
                visit(node_id)
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}",
                cycle,
            )
        return ordered

    def find_roots(self) -> Set[str]:
        # Roots have an empty upstream dependency set.
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id, set())
        }

    def find_leaves(self) -> Set[str]:
        # Leaves have an empty downstream dependent set.
        return {
            node_id
            for node_id in self._nodes
            if not self._downstream.get(node_id, set())
        }

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        ordered = self.topological_sort()
        if not ordered:
            return ([], 0.0)
        # Duration weights default to 1.0 for unspecified nodes.
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        earliest: Dict[str, float] = {}
        for node_id in ordered:
            predecessors = [
                dep
                for dep in self._upstream.get(node_id, set())
                if dep in earliest
            ]
            base = max((earliest[dep] for dep in predecessors), default=0.0)
            earliest[node_id] = base + float(durations.get(node_id, 1.0))
        # Terminal nodes are those without dependents; a non-empty DAG always has one.
        terminals = [node_id for node_id in ordered if not self._downstream.get(node_id, set())]
        terminal_id = sorted(terminals, key=lambda node_id: (-earliest[node_id], node_id))[0]
        # Backtrack through the predecessor yielding the maximum earliest completion.
        path: List[str] = []
        current_id = terminal_id
        while True:
            path.append(current_id)
            predecessors = [
                dep
                for dep in self._upstream.get(current_id, set())
                if dep in earliest
            ]
            if not predecessors:
                break
            current_id = sorted(
                predecessors,
                key=lambda dep: (-earliest[dep], dep),
            )[0]
        path.reverse()
        return (path, earliest[terminal_id])


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        # Collaborator DAG and node state tracking.
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}
        self._tracked: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}

    def _sync_states(self) -> None:
        # Synchronize dynamic node state with currently registered DAG nodes.
        registered = self._dag.all_nodes()
        for node_id in sorted(registered):
            definition = self._dag.get_node(node_id)
            # A definition object change indicates a freshly registered node
            # (including removal followed by re-registration), which resets state.
            if node_id not in self._states or self._tracked.get(node_id) is not definition:
                dependencies = self._dag.get_dependencies(node_id)
                self._states[node_id] = (
                    dag_engine_lite.NodeState.READY
                    if not dependencies
                    else dag_engine_lite.NodeState.PENDING
                )
            self._tracked[node_id] = definition
        # Purge state entries for nodes no longer registered in the graph.
        for node_id in list(self._states):
            if node_id not in registered:
                del self._states[node_id]
        for node_id in list(self._tracked):
            if node_id not in registered:
                del self._tracked[node_id]
        # Promote pending nodes whose upstream dependencies are all satisfied.
        for node_id in sorted(registered):
            if self._states[node_id] is not dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                self._states[node_id] = dag_engine_lite.NodeState.READY

    def next_wave(self) -> List[str]:
        self._sync_states()
        # Ready nodes must have all upstream dependencies SUCCEEDED.
        candidates: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                candidates.append(node_id)
        # Order by priority descending, then node_id ascending.
        return sorted(
            candidates,
            key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id),
        )

    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Promote newly unblocked dependents to READY.
        for dependent_id in sorted(self._dag.get_dependents(node_id)):
            if self._states.get(dependent_id) is not dag_engine_lite.NodeState.PENDING:
                continue
            dependencies = self._dag.get_dependencies(dependent_id)
            if all(
                self._states.get(dep) is dag_engine_lite.NodeState.SUCCEEDED
                for dep in dependencies
            ):
                self._states[dependent_id] = dag_engine_lite.NodeState.READY

    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal_states = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Cancel every remaining non-terminal node.
            for other_id in self._states:
                if self._states[other_id] not in terminal_states:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
            return
        # SKIP_DOWNSTREAM and CONTINUE_ON_ERROR both skip blocked transitive dependents.
        transitive: Set[str] = set()
        frontier: List[str] = list(self._dag.get_dependents(node_id))
        while frontier:
            current_id = frontier.pop()
            if current_id in transitive:
                continue
            transitive.add(current_id)
            frontier.extend(self._dag.get_dependents(current_id))
        for dependent_id in sorted(transitive):
            if self._states.get(dependent_id) not in terminal_states:
                self._states[dependent_id] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        self._sync_states()
        if not self._states:
            # Empty DAG is trivially finished.
            return True
        terminal_states = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        if all(state in terminal_states for state in self._states.values()):
            return True
        # Any runnable node (READY/RUNNING) keeps the run unfinished. Synchronization
        # promotes every pending node whose prerequisites are all succeeded, so any
        # remaining pending node is blocked by a failed dependency.
        for state in self._states.values():
            if state in (dag_engine_lite.NodeState.READY, dag_engine_lite.NodeState.RUNNING):
                return False
        # No ready nodes remain and unexecuted nodes are blocked by failed dependencies.
        return True

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # Registration in the scheduled DAG is a checked precondition.
        if node_id not in self._dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the scheduled graph",
                node_id,
            )
        self._sync_states()
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        registered = self._dag.all_nodes()
        return {
            node_id: state
            for node_id, state in self._states.items()
            if node_id in registered
        }


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        # Collaborators and outcome storage.
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def run(self, failure_policy: dag_engine_lite.FailurePolicy) -> dag_engine_lite.DAGRunReport:
        # Validate graph invariants before commencing wave execution.
        self._dag.validate()
        start_time = time.monotonic()
        self._results = {}
        failed = False
        # Execute ready waves sequentially until the scheduler reports completion.
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_start = time.monotonic()
                retries_attempted = 0
                node_value: Any = None
                node_error: Optional[Exception] = None
                while True:
                    try:
                        node_value = definition.action()
                    except Exception as caught:  # reified into NodeResult records
                        # cleanroom: allow-broad-exception (caught failures reified into NodeResult.error)
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        node_error = caught
                        break
                    break
                duration = time.monotonic() - node_start
                if node_error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=node_value,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=node_error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    failed = True
                # Fail-fast halts further wave execution after the first failure.
                if failed and failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                    break
            if failed and failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                break
        # Populate default result records for unexecuted terminal nodes.
        for node_id, state in sorted(self._scheduler.get_all_states().items()):
            if node_id in self._results:
                continue
            if state in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        critical_path, _weight = self._dag.compute_critical_path(None)
        # Gather outcome partitions from the union of this invocation's recorded
        # results and the final scheduler states, so nodes that were already
        # terminal when run() was entered (e.g. prior FAILED outcomes) are included.
        final_states: Dict[str, dag_engine_lite.NodeState] = {
            node_id: state
            for node_id, state in self._scheduler.get_all_states().items()
        }
        for node_id, result in self._results.items():
            final_states[node_id] = result.state
        succeeded_nodes = tuple(
            sorted(
                node_id
                for node_id, state in final_states.items()
                if state is dag_engine_lite.NodeState.SUCCEEDED
            )
        )
        failed_nodes = tuple(
            sorted(
                node_id
                for node_id, state in final_states.items()
                if state is dag_engine_lite.NodeState.FAILED
            )
        )
        skipped_nodes = tuple(
            sorted(
                node_id
                for node_id, state in final_states.items()
                if state is dag_engine_lite.NodeState.SKIPPED
            )
        )
        cancelled_nodes = tuple(
            sorted(
                node_id
                for node_id, state in final_states.items()
                if state is dag_engine_lite.NodeState.CANCELLED
            )
        )
        # Consolidated run report capturing outcomes, metrics, and critical path.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=time.monotonic() - start_time,
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
# LAST_CLEANED: 2026-11-05T21:52:18Z
# LAST_CHANGED: 2026-11-05T21:45:12Z
# CHANGE: Fix DAGRunner.run outcome partitioning to match low/dag_engine_lite_impl.pyi grounding: succeeded_nodes, failed_nodes, skipped_nodes, and cancelled_nodes are now gathered from the union of this invocation's recorded _results and the final _scheduler states, so a node already terminal when run() is entered (notably a prior FAILED outcome) is reported in its partition instead of being dropped. Default result records remain restricted to unexecuted SKIPPED/CANCELLED nodes and the empty-wave halt semantics are unchanged.
# COVERAGE_AUDIT: 2026-11-05T21:45:58Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T21:52:18Z
# PRETENSE_QA_AUDIT: 2026-11-05T21:52:05Z
# QA_AUDIT: 2026-11-05T21:45:37Z
# --- END AUTOFAB METADATA ---
