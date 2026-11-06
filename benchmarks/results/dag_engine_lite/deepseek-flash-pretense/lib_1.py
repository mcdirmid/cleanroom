# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261105_195200_deepseek-flash_dag_engine_lite_pretense
# Timestamp: 2026-11-05T19:52:00.164327+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 376,407
#   Cached Inbound Tokens:   53,805,183
#   Outbound Tokens:         546,428
#   Total Tokens:            54,728,018
#   Financial Cost ($USD):   $0.5457
#   Wall Clock Duration:     3447.98s
#   Step Latencies (s):      [188.9, 707.6, 480.8, 319.2, 180.0, 390.2, 63.7, 52.7, 147.6, 52.6, 73.8, 62.8, 63.0, 62.9, 31.3, 74.6, 58.0, 10.7, 105.1, 54.3, 130.8, 10.3, 64.4, 66.2, 65.7, 10.4, 62.8, 75.3, 10.7, 41.7, 54.5, 10.8, 10.3]
#   Role Execution Rounds:   lib: 11, pretense: 8, pretense_coverage: 5, pretense_qa: 9 (Total: 33)
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
from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier
import enum

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')


@data_type
@dataclass
class DAGError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    node_id: str


@data_type
@dataclass
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


@singleton_type("system")
class DAG(Singleton[SystemTier], Protocol):
    @operation
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
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
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        ...


@singleton_type("system")
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
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
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


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    @operation
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T19:55:13Z
# LAST_CHANGED: 2026-11-05T19:55:13Z
# CHANGE: Implement interface module: convert exception classes to mutable dataclasses with __str__, add @data_type/@singleton_type/@operation decorators, preserve all contracts and signatures matching low/dag_engine_lite.pyi.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine_lite
import time

# Requirements specified in dag_engine_lite_impl.pyi


class DAG(dag_engine_lite.DAG):
    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    @operation
    @override
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
        # PRECONDITION: node_id must not already be registered (raises DuplicateNodeError).
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                f"Node '{node_id}' is already registered in the DAG.",
                node_id,
            )
        dependency_set: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        # POSTCONDITION: register the node definition and its adjacency bookkeeping.
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # POSTCONDITION: WHEN dependencies are provided, add a directed edge from each dependency.
        # Missing dependencies are deliberately deferred to validate()/topological_sort().
        for dependency in dependency_set:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # PRECONDITION: both endpoints must already exist (raises NodeNotFoundError).
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{upstream_id}' is not registered in the DAG.",
                upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{downstream_id}' is not registered in the DAG.",
                downstream_id,
            )
        # POSTCONDITION: establish a directed dependency edge upstream_id -> downstream_id.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # PRECONDITION: node_id must be registered (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG.",
                node_id,
            )
        # POSTCONDITION: remove every incident dependency edge from the adjacency bookkeeping.
        for dependency in list(self._upstream.get(node_id, set())):
            self._downstream.get(dependency, set()).discard(node_id)
        for dependent in list(self._downstream.get(node_id, set())):
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
        # PRECONDITION: node_id must be registered (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG.",
                node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # PRECONDITION: node_id must be registered (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG.",
                node_id,
            )
        # POSTCONDITION: return a defensive copy of all direct upstream dependencies.
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # PRECONDITION: node_id must be registered (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG.",
                node_id,
            )
        # POSTCONDITION: return a defensive copy of all direct downstream dependents.
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # PRECONDITION: every referenced dependency must exist (raises NodeNotFoundError).
        for node_id, dependencies in self._upstream.items():
            for dependency in dependencies:
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on unregistered node '{dependency}'.",
                        dependency,
                    )
        # PRECONDITION: the graph must contain no directed cycles (raises CycleError).
        # A full deterministic topological sweep performs the acyclicity verification.
        self.topological_sort()

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Deterministic Kahn sweep: in-degree derived from the _upstream adjacency mapping.
        in_degree: Dict[str, int] = {
            node_id: len(dependencies)
            for node_id, dependencies in self._upstream.items()
        }
        ready: List[str] = [
            node_id
            for node_id in self._nodes
            if in_degree.get(node_id, 0) == 0
        ]
        ready.sort(key=lambda node_id: (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, set())):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort(key=lambda candidate: (-self._nodes[candidate].priority, candidate))
        # POSTCONDITION: every node must appear exactly once; otherwise a cycle exists.
        if len(order) != len(self._nodes):
            cycle = self._detect_cycle()
            cycle_sequence: Tuple[str, ...]
            if cycle is not None:
                cycle_sequence = tuple(cycle)
            else:
                cycle_sequence = tuple(sorted(set(self._nodes) - set(order)))
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle_sequence)}.",
                cycle_sequence,
            )
        return order

    def _detect_cycle(self) -> Optional[List[str]]:
        """Depth-first search returning the node sequence forming a cycle, if any."""
        color: Dict[str, int] = {}
        path: List[str] = []

        def visit(node_id: str) -> Optional[List[str]]:
            color[node_id] = 1
            path.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                # Missing dependencies are reported by validate(), not as cycles.
                if dependency not in self._upstream:
                    continue
                if color.get(dependency, 0) == 1:
                    start = path.index(dependency)
                    return path[start:] + [dependency]
                if color.get(dependency, 0) == 0:
                    found = visit(dependency)
                    if found is not None:
                        return found
            path.pop()
            color[node_id] = 2
            return None

        for node_id in sorted(self._nodes):
            if color.get(node_id, 0) == 0:
                found = visit(node_id)
                if found is not None:
                    return found
        return None

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
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        order = self.topological_sort()
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        # Dynamic programming sweep: earliest completion time per node.
        # topological_sort() guarantees every referenced dependency is registered and
        # appears earlier in the order, so each dependency is already present in earliest.
        earliest: Dict[str, float] = {}
        for node_id in order:
            best_prerequisite = 0.0
            for dependency in self._upstream.get(node_id, set()):
                if earliest[dependency] > best_prerequisite:
                    best_prerequisite = earliest[dependency]
            earliest[node_id] = best_prerequisite + float(durations.get(node_id, 1.0))
        # POSTCONDITION: the longest path ends at a terminal (out-degree zero) node.
        leaves = [node_id for node_id in self._nodes if not self._downstream.get(node_id, set())]
        if not leaves:
            return ([], 0.0)
        terminal = min(leaves, key=lambda node_id: (-earliest[node_id], node_id))
        # Backtrack from the terminal node choosing the predecessor with the latest completion time.
        # Every dependency is present in earliest (see invariant above), so no membership guard is needed.
        reversed_path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            reversed_path.append(current)
            predecessor: Optional[str] = None
            predecessor_time = 0.0
            for dependency in sorted(self._upstream.get(current, set())):
                if predecessor is None or earliest[dependency] > predecessor_time:
                    predecessor = dependency
                    predecessor_time = earliest[dependency]
            current = predecessor
        reversed_path.reverse()
        return (reversed_path, earliest[terminal])


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _is_terminal(self, state: dag_engine_lite.NodeState) -> bool:
        return state in (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )

    def _sync_states(self) -> None:
        """Reconciles scheduler state with the nodes currently registered in the DAG."""
        registered = self._dag.all_nodes()
        for node_id in list(self._states):
            if node_id not in registered:
                del self._states[node_id]
        for node_id in registered:
            if node_id not in self._states:
                if self._dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        visited: Set[str] = set()
        pending: List[str] = list(self._dag.get_dependents(node_id))
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self._dag.get_dependents(current))
        return visited

    @operation
    @override
    def next_wave(self) -> List[str]:
        self._sync_states()
        # POSTCONDITION: return READY nodes whose upstream dependencies have all SUCCEEDED.
        candidates: List[str] = []
        for node_id, state in self._states.items():
            if state is not dag_engine_lite.NodeState.READY:
                continue
            dependencies = self._dag.get_dependencies(node_id)
            if all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                candidates.append(node_id)
        # POSTCONDITION: order by priority descending, then node_id ascending.
        candidates.sort(key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        # POSTCONDITION: record the terminal SUCCEEDED state.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # POSTCONDITION: promote newly unblocked PENDING dependents to READY.
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
    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy) -> None:
        self._sync_states()
        # POSTCONDITION: record the terminal FAILED state before applying the policy.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # POSTCONDITION: cancel every remaining non-terminal node.
            for other_id, other_state in self._states.items():
                if not self._is_terminal(other_state):
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # POSTCONDITION: skip every transitive dependent of the failed node.
            for dependent in self._transitive_dependents(node_id):
                if not self._is_terminal(self._states.get(dependent, dag_engine_lite.NodeState.PENDING)):
                    self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
        else:
            # CONTINUE_ON_ERROR: retain unblocked independent nodes, skip blocked dependents.
            changed = True
            while changed:
                changed = False
                for other_id in sorted(self._states):
                    other_state = self._states[other_id]
                    if self._is_terminal(other_state):
                        continue
                    if other_state is dag_engine_lite.NodeState.RUNNING:
                        continue
                    dependencies = self._dag.get_dependencies(other_id)
                    if any(
                        self._states.get(dependency)
                        in (dag_engine_lite.NodeState.FAILED, dag_engine_lite.NodeState.SKIPPED)
                        for dependency in dependencies
                    ):
                        self._states[other_id] = dag_engine_lite.NodeState.SKIPPED
                        changed = True

    @operation
    @override
    def is_finished(self) -> bool:
        self._sync_states()
        # POSTCONDITION: an empty DAG is trivially finished.
        if not self._states:
            return True
        # POSTCONDITION: all nodes terminal means the run is complete.
        if all(self._is_terminal(state) for state in self._states.values()):
            return True
        # POSTCONDITION: when no ready nodes remain and unexecuted nodes are blocked by
        # failed upstream dependencies, the run cannot progress and is therefore finished.
        if not self.next_wave():
            blocked = True
            for node_id, state in self._states.items():
                if self._is_terminal(state):
                    continue
                dependencies = self._dag.get_dependencies(node_id)
                if not any(
                    self._states.get(dependency)
                    in (dag_engine_lite.NodeState.FAILED, dag_engine_lite.NodeState.SKIPPED)
                    for dependency in dependencies
                ):
                    blocked = False
                    break
            if blocked:
                return True
        return False

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # PRECONDITION: node_id must be registered in the scheduled DAG (raises NodeNotFoundError).
        if not self._dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG.",
                node_id,
            )
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        registered = self._dag.all_nodes()
        # POSTCONDITION: reflect only currently registered nodes via a shallow copy.
        return {
            node_id: state
            for node_id, state in self._states.items()
            if node_id in registered
        }


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _execute(self, definition: dag_engine_lite.NodeDefinition[Any]) -> Tuple[dag_engine_lite.NodeState, Any, Optional[Exception], float, int]:
        """Executes a node action honoring the configured retry budget."""
        started = time.monotonic()
        retries_attempted = 0
        last_error: Optional[Exception] = None
        while retries_attempted <= definition.retries:
            try:
                value = definition.action()
                return (
                    dag_engine_lite.NodeState.SUCCEEDED,
                    value,
                    None,
                    time.monotonic() - started,
                    retries_attempted,
                )
            except Exception as error:  # cleanroom: allow-broad-exception (reified into NodeResult)
                last_error = error
                retries_attempted += 1
        return (
            dag_engine_lite.NodeState.FAILED,
            None,
            last_error,
            time.monotonic() - started,
            retries_attempted - 1,
        )

    @operation
    @override
    def run(self, failure_policy: dag_engine_lite.FailurePolicy) -> dag_engine_lite.DAGRunReport:
        # PRECONDITION: graph invariants are validated before wave execution begins.
        self._dag.validate()
        self._results = {}
        started = time.monotonic()
        fail_fast_tripped = False
        # POSTCONDITION: execute ready waves sequentially until the scheduler finishes.
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                state, value, error, duration, retries_used = self._execute(definition)
                if state is dag_engine_lite.NodeState.SUCCEEDED:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=retries_used,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=retries_used,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        fail_fast_tripped = True
                        break
            if fail_fast_tripped:
                break
        # POSTCONDITION: record default outcomes for skipped or cancelled nodes.
        final_states = self._scheduler.get_all_states()
        for node_id, state in final_states.items():
            if node_id in self._results:
                continue
            if state in (dag_engine_lite.NodeState.SKIPPED, dag_engine_lite.NodeState.CANCELLED):
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        wall_clock_seconds = time.monotonic() - started
        # POSTCONDITION: consolidate all outcomes and metrics into a DAGRunReport.
        critical_path = self._dag.compute_critical_path(None)
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
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path[0]),
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T20:49:23Z
# LAST_CHANGED: 2026-11-05T20:41:28Z
# CHANGE: Fix contract-closure dead code in compute_critical_path: pruned the unreachable 'if dependency not in earliest: continue' skip guard (previous line 254) and the redundant 'dependency in earliest' membership check in the DP sweep. topological_sort() guarantees every referenced dependency is registered and ordered before its dependents (missing dependencies and cycles both raise CycleError), so all dependencies are necessarily present in the earliest-completion table; documented that invariant in comments. No change to observable critical-path behavior.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T20:49:23Z
# PRETENSE_QA_AUDIT: 2026-11-05T20:49:10Z
# --- END AUTOFAB METADATA ---
