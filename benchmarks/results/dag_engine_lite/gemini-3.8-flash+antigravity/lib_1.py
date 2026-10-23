# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_172848_gemini-3_8-flash_dag_engine_lite
# Timestamp: 2026-10-23T17:28:48.462672+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-3.8-flash (Tier 2)
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,634,917
#   Cached Inbound Tokens:   6,685,200
#   Outbound Tokens:         150,966
#   Total Tokens:            8,471,083
#   Financial Cost ($USD):   $0.3910
#   Wall Clock Duration:     949.06s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   coverage: 3, lib: 3, qa: 3, test: 3 (Total: 12)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       36
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
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

@dataclass(frozen=True)
class DAGError(Exception):
    message: str


@dataclass(frozen=True)
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    node_id: str


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


@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


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


class DAG(Singleton[SystemTier], Protocol):
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        ...

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        ...

    def remove_node(self, node_id: str) -> None:
        ...

    def has_node(self, node_id: str) -> bool:
        ...

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        ...

    def get_dependencies(self, node_id: str) -> Set[str]:
        ...

    def get_dependents(self, node_id: str) -> Set[str]:
        ...

    def all_nodes(self) -> Set[str]:
        ...

    def validate(self) -> None:
        ...

    def topological_sort(self) -> List[str]:
        ...

    def find_roots(self) -> Set[str]:
        ...

    def find_leaves(self) -> Set[str]:
        ...

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    def next_wave(self) -> List[str]:
        ...

    def mark_running(self, node_id: str) -> None:
        ...

    def mark_succeeded(self, node_id: str) -> None:
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
        ...

    def is_finished(self) -> bool:
        ...

    def get_state(self, node_id: str) -> NodeState:
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    def run(self, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> DAGRunReport:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T17:29:54Z
# LAST_CHANGED: 2026-10-23T17:29:54Z
# CHANGE: Initial implementation of DAG engine interface protocols and data types
# --- END CLEANROOM METADATA ---


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
        # Construct immutable NodeDefinition with frozen dependency set
        dep_set: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dep_set,
            priority=priority,
            retries=retries,
        )
        if node_id in self._upstream:
            for old_dep in list(self._upstream[node_id]):
                if old_dep in self._downstream:
                    self._downstream[old_dep].discard(node_id)
            self._upstream[node_id].clear()
        else:
            self._upstream[node_id] = set()

        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        self._nodes[node_id] = node_def

        # Add directed dependency edges from each dependency to node_id
        for dep in dep_set:
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)
            self._upstream[node_id].add(dep)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Upstream node '{upstream_id}' not found in DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Downstream node '{downstream_id}' not found in DAG",
                node_id=downstream_id,
            )

        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

        old_def = self._nodes[downstream_id]
        if upstream_id not in old_def.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=old_def.node_id,
                action=old_def.action,
                dependencies=frozenset(old_def.dependencies | {upstream_id}),
                priority=old_def.priority,
                retries=old_def.retries,
            )

    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        for up in list(self._upstream.get(node_id, set())):
            if up in self._downstream:
                self._downstream[up].discard(node_id)

        for down in list(self._downstream.get(node_id, set())):
            if down in self._upstream:
                self._upstream[down].discard(node_id)
            if down in self._nodes:
                d_def = self._nodes[down]
                if node_id in d_def.dependencies:
                    self._nodes[down] = dag_engine_lite.NodeDefinition(
                        node_id=d_def.node_id,
                        action=d_def.action,
                        dependencies=frozenset(d_def.dependencies - {node_id}),
                        priority=d_def.priority,
                        retries=d_def.retries,
                    )

        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        state: Dict[str, int] = {}
        path: List[str] = []

        def dfs(u: str) -> Optional[Tuple[str, ...]]:
            state[u] = 1
            path.append(u)
            for v in sorted(self._downstream.get(u, set())):
                if state.get(v, 0) == 1:
                    idx = path.index(v)
                    return tuple(path[idx:] + [v])
                if state.get(v, 0) == 0:
                    res = dfs(v)
                    if res is not None:
                        return res
            path.pop()
            state[u] = 2
            return None

        for node in sorted(self._nodes.keys()):
            if state.get(node, 0) == 0:
                c = dfs(node)
                if c is not None:
                    return c
        return None

    def validate(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError
        for node_id, node_def in sorted(self._nodes.items()):
            for dep in sorted(node_def.dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Dependency '{dep}' referenced by node '{node_id}' does not exist in graph",
                        node_id=dep,
                    )
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    def topological_sort(self) -> List[str]:
        in_degrees: Dict[str, int] = {}
        for node in self._nodes:
            in_degrees[node] = len([up for up in self._upstream.get(node, set()) if up in self._nodes])

        ready: List[str] = [n for n, deg in in_degrees.items() if deg == 0]
        # Break ties between concurrent ready nodes using priority descending and name ascending
        ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        result: List[str] = []
        while ready:
            curr = ready.pop(0)
            result.append(curr)
            for downstream in sorted(self._downstream.get(curr, set())):
                if downstream in in_degrees:
                    in_degrees[downstream] -= 1
                    if in_degrees[downstream] == 0:
                        ready.append(downstream)
                        ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        # WHEN a cycle exists, MUST raise CycleError
        if len(result) != len(self._nodes):
            cycle = self._find_cycle() or ()
            raise dag_engine_lite.CycleError(
                f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=cycle,
            )

        return result

    def find_roots(self) -> Set[str]:
        return {n for n in self._nodes if not any(up in self._nodes for up in self._upstream.get(n, set()))}

    def find_leaves(self) -> Set[str]:
        return {n for n in self._nodes if not any(down in self._nodes for down in self._downstream.get(n, set()))}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        if not self._nodes:
            return ([], 0.0)

        order = self.topological_sort()
        durations = estimated_durations or {}

        earliest: Dict[str, float] = {}
        best_pred: Dict[str, Optional[str]] = {}

        for node in order:
            dur = float(durations.get(node, 1.0))
            upstream_nodes = [up for up in self._upstream.get(node, set()) if up in self._nodes]
            if not upstream_nodes:
                earliest[node] = dur
                best_pred[node] = None
            else:
                sorted_up = sorted(
                    upstream_nodes,
                    key=lambda p: (-earliest[p], -self._nodes[p].priority, p),
                )
                max_p = sorted_up[0]
                earliest[node] = earliest[max_p] + dur
                best_pred[node] = max_p

        leaves = self.find_leaves()
        sorted_leaves = sorted(
            leaves,
            key=lambda n: (-earliest[n], -self._nodes[n].priority, n),
        )
        terminal_node = sorted_leaves[0]

        path: List[str] = []
        curr: Optional[str] = terminal_node
        while curr is not None:
            path.append(curr)
            curr = best_pred.get(curr)

        path.reverse()
        total_weight = earliest[terminal_node]
        return (path, total_weight)


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        all_nodes = self._dag.all_nodes()
        roots = self._dag.find_roots()
        for node_id in all_nodes:
            if node_id not in self._states:
                if node_id in roots:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
        for node_id in list(self._states.keys()):
            if node_id not in all_nodes:
                del self._states[node_id]

    def next_wave(self) -> List[str]:
        self._sync_states()
        ready_candidates: List[str] = []
        for node_id, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                upstream = self._dag.get_dependencies(node_id)
                if all(self._states.get(up) == dag_engine_lite.NodeState.SUCCEEDED for up in upstream):
                    ready_candidates.append(node_id)
        ready_candidates.sort(key=lambda n: (-self._dag.get_node(n).priority, n))
        return ready_candidates

    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dep_id in self._dag.get_dependents(node_id):
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING:
                upstream = self._dag.get_dependencies(dep_id)
                if all(self._states.get(up) == dag_engine_lite.NodeState.SUCCEEDED for up in upstream):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for n, s in list(self._states.items()):
                if n != node_id and s not in terminal_states:
                    self._states[n] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            queue = list(self._dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr not in visited:
                    visited.add(curr)
                    if self._states.get(curr) not in terminal_states:
                        self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                    for nxt in self._dag.get_dependents(curr):
                        if nxt not in visited:
                            queue.append(nxt)
        elif failure_policy == dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            pass

    def is_finished(self) -> bool:
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        if not all_nodes:
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        return all(self._states.get(n) in terminal_states for n in all_nodes)

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self._states:
            self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in scheduler",
                node_id=node_id,
            )
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        return dict(self._states)


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler

        # Validate DAG consistency, completeness, and acyclicity
        dag.validate()

        start_time = time.perf_counter()
        self._results = {}

        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                break
            wave_failed = False
            for node_id in wave:
                scheduler.mark_running(node_id)
                node_def = dag.get_node(node_id)

                node_start = time.perf_counter()
                success = False
                result_val: Any = None
                last_error: Optional[Exception] = None
                retries_attempted = 0

                # Initial execution attempt
                try:
                    result_val = node_def.action()
                    success = True
                except Exception as exc:  # cleanroom: allow-broad-exception
                    last_error = exc
                    for attempt in range(1, node_def.retries + 1):
                        retries_attempted = attempt
                        try:
                            result_val = node_def.action()
                            success = True
                            last_error = None
                            break
                        except Exception as retry_exc:  # cleanroom: allow-broad-exception
                            last_error = retry_exc

                node_duration = time.perf_counter() - node_start

                if success:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=result_val,
                        error=None,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_error,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy=failure_policy)
                    wave_failed = True
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

            if wave_failed and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        # Populate unexecuted terminal results
        all_states = scheduler.get_all_states()
        for node_id, state in all_states.items():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        critical_path_list, _ = dag.compute_critical_path()
        critical_path = tuple(critical_path_list)

        succeeded_nodes = tuple(
            n for n, r in self._results.items() if r.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            n for n, r in self._results.items() if r.state == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            n for n, r in self._results.items() if r.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            n for n, r in self._results.items() if r.state == dag_engine_lite.NodeState.CANCELLED
        )

        wall_clock_seconds = time.perf_counter() - start_time

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=critical_path,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T17:44:32Z
# LAST_CHANGED: 2026-10-23T17:43:21Z
# CHANGE: Eliminate unreachable defensive branches in cycle detection and critical path computation
# COVERAGE_AUDIT: 2026-10-23T17:44:32Z
# QA_AUDIT: 2026-10-23T17:44:07Z
# --- END CLEANROOM METADATA ---
