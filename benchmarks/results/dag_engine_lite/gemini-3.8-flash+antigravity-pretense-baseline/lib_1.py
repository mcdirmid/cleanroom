# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_231531_gemini-3_8-flash_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-28T23:15:31.965056+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 416,084
#   Cached Inbound Tokens:   6,448,799
#   Outbound Tokens:         94,781
#   Total Tokens:            6,959,664
#   Financial Cost ($USD):   $0.2407
#   Wall Clock Duration:     850.65s
#   Step Latencies (s):      []
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
from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.lifecycle import Singleton, SystemTier, system
import enum

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')

@dataclass
class DAGError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@dataclass
class NodeNotFoundError(DAGError):
    node_id: str


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
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
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

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
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

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
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
    def run(self, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> DAGRunReport:
        # TODO_run_body
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T23:29:37Z
# LAST_CHANGED: 2026-10-28T23:29:37Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 70aea53ecad7
# COVERAGE_AUDIT: 2026-10-28T23:29:37Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:29:37Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:29:37Z
# QA_AUDIT: 2026-10-28T23:29:37Z
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
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = node_def
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        for dep in deps:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found in DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found in DAG",
                node_id=downstream_id,
            )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        old_def = self._nodes[downstream_id]
        self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
            node_id=old_def.node_id,
            action=old_def.action,
            dependencies=frozenset(self._upstream[downstream_id]),
            priority=old_def.priority,
            retries=old_def.retries,
        )

    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        for u in list(self._upstream.get(node_id, ())):
            if u in self._downstream:
                self._downstream[u].discard(node_id)
        for d in list(self._downstream.get(node_id, ())):
            if d in self._upstream:
                self._upstream[d].discard(node_id)
            if d in self._nodes:
                old = self._nodes[d]
                self._nodes[d] = dag_engine_lite.NodeDefinition(
                    node_id=old.node_id,
                    action=old.action,
                    dependencies=frozenset(self._upstream[d]),
                    priority=old.priority,
                    retries=old.retries,
                )
        del self._nodes[node_id]
        if node_id in self._upstream:
            del self._upstream[node_id]
        if node_id in self._downstream:
            del self._downstream[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        visited: Set[str] = set()
        rec_stack: List[str] = []
        rec_set: Set[str] = set()

        def dfs(node: str) -> Optional[Tuple[str, ...]]:
            visited.add(node)
            rec_stack.append(node)
            rec_set.add(node)

            for neighbor in sorted(self._downstream.get(node, set())):
                if neighbor in rec_set:
                    idx = rec_stack.index(neighbor)
                    return tuple(rec_stack[idx:] + [neighbor])
                if neighbor not in visited:
                    res = dfs(neighbor)
                    if res is not None:
                        return res

            rec_stack.pop()
            rec_set.remove(node)
            return None

        for node in sorted(self._nodes.keys()):
            if node not in visited:
                res = dfs(node)
                if res is not None:
                    return res
        return None

    def validate(self) -> None:
        for node_id in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[node_id].dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Referenced dependency '{dep}' not found in DAG",
                        node_id=dep,
                    )
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Directed cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    def topological_sort(self) -> List[str]:
        for node_id in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[node_id].dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Referenced dependency '{dep}' not found in DAG",
                        node_id=dep,
                    )

        in_degree: Dict[str, int] = {}
        for nid in self._nodes:
            in_degree[nid] = len(self._upstream.get(nid, set()))

        ready: List[str] = [nid for nid in self._nodes if in_degree[nid] == 0]
        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        order: List[str] = []
        while ready:
            curr = ready.pop(0)
            order.append(curr)
            for downstream in sorted(self._downstream.get(curr, set())):
                if downstream in in_degree:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        ready.append(downstream)
                        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        if len(order) != len(self._nodes):
            cycle = self._find_cycle() or ()
            raise dag_engine_lite.CycleError(
                message="Directed cycle detected during topological sort",
                cycle=cycle,
            )
        return order

    def find_roots(self) -> Set[str]:
        return {nid for nid in self._nodes if not self._upstream.get(nid)}

    def find_leaves(self) -> Set[str]:
        return {nid for nid in self._nodes if not self._downstream.get(nid)}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        if not self._nodes:
            return ([], 0.0)

        order = self.topological_sort()
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            if estimated_durations is not None and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        earliest: Dict[str, float] = {}
        best_pred: Dict[str, Optional[str]] = {}

        for nid in order:
            up = [p for p in self._upstream.get(nid, set()) if p in self._nodes]
            if not up:
                earliest[nid] = durations[nid]
                best_pred[nid] = None
            else:
                best_p: Optional[str] = None
                max_t = -1.0
                for p in sorted(up):
                    t = earliest[p]
                    if t > max_t:
                        max_t = t
                        best_p = p
                earliest[nid] = max_t + durations[nid]
                best_pred[nid] = best_p

        max_total = -1.0
        best_end: Optional[str] = None
        for nid in sorted(self._nodes.keys()):
            if earliest[nid] > max_total:
                max_total = earliest[nid]
                best_end = nid

        path: List[str] = []
        curr = best_end
        while curr is not None:
            path.append(curr)
            curr = best_pred.get(curr)
        path.reverse()
        return (path, max(max_total, 0.0))


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        current_nodes = self._dag.all_nodes()
        for nid in list(self._states.keys()):
            if nid not in current_nodes:
                del self._states[nid]
        roots = self._dag.find_roots()
        for nid in current_nodes:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    def next_wave(self) -> List[str]:
        self._sync_states()
        candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = self._dag.get_dependencies(nid)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    candidates.append(nid)

        candidates.sort(key=lambda nid: (-self._dag.get_node(nid).priority, nid))
        return candidates

    def mark_running(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dependent in self._dag.get_dependents(node_id):
            if self._states.get(dependent) == dag_engine_lite.NodeState.PENDING:
                deps = self._dag.get_dependencies(dependent)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    self._states[dependent] = dag_engine_lite.NodeState.READY

    def _get_transitive_dependents(self, node_id: str) -> Set[str]:
        result: Set[str] = set()
        queue = list(self._dag.get_dependents(node_id))
        while queue:
            curr = queue.pop(0)
            if curr not in result:
                result.add(curr)
                queue.extend(self._dag.get_dependents(curr))
        return result

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid, state in self._states.items():
                if state not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            dependents = self._get_transitive_dependents(node_id)
            for dep in dependents:
                if dep in self._states and self._states[dep] not in terminal_states:
                    self._states[dep] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        self._sync_states()
        nodes = self._dag.all_nodes()
        if not nodes:
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        if all(self._states.get(nid) in terminal_states for nid in nodes):
            return True
        if any(self._states.get(nid) == dag_engine_lite.NodeState.RUNNING for nid in nodes):
            return False
        if len(self.next_wave()) > 0:
            return False
        return True

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self._states:
            self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler state",
                node_id=node_id,
            )
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        current_nodes = self._dag.all_nodes()
        return {nid: state for nid, state in self._states.items() if nid in current_nodes}


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
        self._dag.validate()
        start_time = time.monotonic()
        self._results = {}

        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:
                break
            failed_in_wave = False
            for node_id in wave:
                self._scheduler.mark_running(node_id)
                node_def = self._dag.get_node(node_id)
                attempts = 0
                node_start = time.monotonic()
                val = None
                last_exc: Optional[Exception] = None
                succeeded = False
                while True:
                    try:
                        val = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_exc = exc
                        if attempts < node_def.retries:
                            attempts += 1
                        else:
                            break

                duration = time.monotonic() - node_start
                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=val,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_exc,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy=failure_policy)
                    failed_in_wave = True
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

            if failed_in_wave and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        # Populate unexecuted terminal results from scheduler states
        all_states = self._scheduler.get_all_states()
        for nid, st in all_states.items():
            if nid not in self._results:
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=st,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        critical_path, _ = self._dag.compute_critical_path()
        wall_clock_seconds = time.monotonic() - start_time

        succeeded_nodes = tuple(
            nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.CANCELLED
        )

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
# LAST_CLEANED: 2026-10-28T23:29:37Z
# LAST_CHANGED: 2026-10-28T23:29:37Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4ecd4e938a24
# COVERAGE_AUDIT: 2026-10-28T23:29:37Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:29:37Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:29:37Z
# QA_AUDIT: 2026-10-28T23:29:37Z
# --- END CLEANROOM METADATA ---
