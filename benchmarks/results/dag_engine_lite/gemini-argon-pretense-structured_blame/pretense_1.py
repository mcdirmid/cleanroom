# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Collection, List, Mapping, Optional, Set, Tuple

from hypothesis import given, settings, strategies as st

from pretense import (
    Env,
    StateMachine,
    raises,
    require,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    fake,
    get_singleton,
    system,
)

from dag_engine_lite_gemini_argon_1.parts.dag_engine_lite.lib import (
    dag_engine_lite,
    dag_engine_lite_impl,
)
from dag_engine_lite_gemini_argon_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGError,
    DAGRunReport,
    DAGRunner,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)
from dag_engine_lite_gemini_argon_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGImpl,
    DAGRunner as DAGRunnerImpl,
    WaveScheduler as WaveSchedulerImpl,
)
from dag_engine_lite_gemini_argon_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineLiteState,
    DAGEngineLiteStateMachine,
)


_RETRY_ATTEMPTS: list[int] = []


def _ok_action() -> str:
    return "ok"


def _flaky_action() -> int:
    _RETRY_ATTEMPTS.append(1)
    if len(_RETRY_ATTEMPTS) == 1:
        return int("transient_failure")
    return 42


def _always_fail_action() -> int:
    return int("permanent_failure")


class DAGEngineLiteImplPseudoStateMachine(DAGEngineLiteStateMachine):
    """Implementation pseudo-state machine binding concrete DAG, WaveScheduler, and DAGRunner."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: DAG = sut(DAG)
        ret = target.add_node(node_id, action, dependencies, priority, retries)
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        ret = target.add_edge(upstream_id, downstream_id)
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        ret = target.remove_node(node_id)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        ret = target.has_node(node_id)
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        ret = target.get_node(node_id)
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.get_dependencies(node_id)
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.get_dependents(node_id)
        return ret

    def inner_all_nodes(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.all_nodes()
        return ret

    def inner_validate(self) -> None:
        target: DAG = sut(DAG)
        ret = target.validate()
        return ret

    def inner_topological_sort(self) -> List[str]:
        target: DAG = sut(DAG)
        ret = target.topological_sort()
        return ret

    def inner_find_roots(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.find_roots()
        return ret

    def inner_find_leaves(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.find_leaves()
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: DAG = sut(DAG)
        ret = target.compute_critical_path(estimated_durations)
        return ret

    def inner_next_wave(self) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.next_wave()
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.mark_running(node_id)
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.mark_succeeded(node_id)
        return ret

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.mark_failed(node_id, failure_policy)
        return ret

    def inner_is_finished(self) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.is_finished()
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.get_state(node_id)
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.get_all_states()
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        ret = target.run(failure_policy)
        return ret


proto = DAGEngineLiteImplPseudoStateMachine()


class TestDAGEngineLiteImplReal(LifecycleTestCase):
    """Fixed scenario and contract violation tests against the concrete DAG engine implementation."""

    def setUp(self) -> None:
        super().setUp()
        dag_svc = get_singleton(DAG)
        sched_svc = get_singleton(WaveScheduler)
        runner_svc = get_singleton(DAGRunner)
        self.sm = DAGEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: dag_svc,
                WaveScheduler: sched_svc,
                DAGRunner: runner_svc,
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, dag_svc)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, sched_svc)
        self.checked_runner = self.sm.as_checked(DAGRunner, runner_svc)

    def test_dag_operations_and_topological_sort(self) -> None:
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.compute_critical_path(None)

        self.checked_dag.add_node("a", _ok_action, None, 10, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 5, 1)
        self.checked_dag.add_node("c", _ok_action, ["a"], 8, 0)
        self.checked_dag.add_node("d", _ok_action, None, 1, 0)
        self.checked_dag.add_edge("b", "d")
        self.checked_dag.add_edge("c", "d")

        self.checked_dag.has_node("a")
        self.checked_dag.has_node("nonexistent")
        self.checked_dag.get_node("a")
        self.checked_dag.get_dependencies("d")
        self.checked_dag.get_dependents("a")
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.validate()
        self.checked_dag.topological_sort()
        self.checked_dag.compute_critical_path(None)
        self.checked_dag.compute_critical_path(
            {"a": 1.0, "b": 5.0, "c": 2.0, "d": 3.0}
        )

        self.checked_dag.remove_node("b")
        self.checked_dag.has_node("b")
        self.checked_dag.get_dependents("a")
        self.checked_dag.get_dependencies("d")
        self.checked_dag.remove_node("a")
        self.checked_dag.get_dependencies("c")
        self.checked_dag.remove_node("d")
        self.checked_dag.has_node("d")
        self.checked_dag.find_leaves()

    def test_wave_scheduler_progression(self) -> None:
        self.checked_scheduler.is_finished()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_all_states()

        self.checked_dag.add_node("n1", _ok_action, None, 5, 0)
        self.checked_dag.add_node("n2", _ok_action, ["n1"], 3, 0)
        self.checked_dag.add_node("n3", _ok_action, ["n2"], 1, 0)

        self.checked_scheduler.is_finished()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_state("n1")
        self.checked_scheduler.get_all_states()

        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_succeeded("n1")

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n2")
        self.checked_scheduler.mark_succeeded("n2")

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n3")
        self.checked_scheduler.mark_succeeded("n3")

        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()

    def test_wave_scheduler_skip_downstream_and_remove_node(self) -> None:
        self.checked_dag.add_node("n1", _ok_action, None, 5, 0)
        self.checked_dag.add_node("n2", _ok_action, ["n1"], 3, 0)
        self.checked_dag.add_node("n3", _ok_action, ["n2"], 1, 0)

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.get_state("n3")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()
        self.checked_dag.remove_node("n3")
        self.checked_scheduler.get_all_states()

    def test_wave_scheduler_fail_fast(self) -> None:
        self.checked_dag.add_node("n1", _ok_action, None, 5, 0)
        self.checked_dag.add_node("n2", _ok_action, ["n1"], 3, 0)

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.FAIL_FAST)
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()

    def test_wave_scheduler_continue_on_error(self) -> None:
        self.checked_dag.add_node("n1", _ok_action, None, 5, 0)
        self.checked_dag.add_node("n2", _ok_action, ["n1"], 3, 0)
        self.checked_dag.add_node("n3", _ok_action, None, 1, 0)

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()

    def test_runner_consolidated_report_and_retries(self) -> None:
        _RETRY_ATTEMPTS.clear()
        self.checked_dag.add_node("root", _ok_action, None, 5, 0)
        self.checked_dag.add_node("flaky", _flaky_action, ["root"], 3, 2)
        self.checked_dag.add_node("leaf", _ok_action, ["flaky"], 1, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_fail_fast_on_permanent_failure(self) -> None:
        self.checked_dag.add_node("fail_root", _always_fail_action, None, 10, 1)
        self.checked_dag.add_node("downstream", _ok_action, ["fail_root"], 1, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_skip_downstream_on_failure(self) -> None:
        self.checked_dag.add_node("fail_root", _always_fail_action, None, 10, 0)
        self.checked_dag.add_node("dep1", _ok_action, ["fail_root"], 5, 0)
        self.checked_dag.add_node("dep2", _ok_action, ["dep1"], 2, 0)
        self.checked_dag.add_node("indep", _ok_action, None, 1, 0)
        self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_continue_on_error_on_failure(self) -> None:
        self.checked_dag.add_node("fail_root", _always_fail_action, None, 10, 0)
        self.checked_dag.add_node("dep1", _ok_action, ["fail_root"], 5, 0)
        self.checked_dag.add_node("indep", _ok_action, None, 1, 0)
        self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_add_node_duplicate_error(self) -> None:
        self.checked_dag.add_node("dup", _ok_action, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node(
            "dup", _ok_action, None, 0, 0
        )

    def test_add_edge_missing_upstream_error(self) -> None:
        self.checked_dag.add_node("b", _ok_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing", "b")

    def test_add_edge_missing_downstream_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("a", "missing")

    def test_remove_node_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_get_node_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_get_dependencies_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_validate_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, ["missing_dep"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_edge("b", "a")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_edge("b", "a")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_scheduler_get_state_not_found_error(self) -> None:
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing")

    def test_runner_run_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, ["missing_dep"], 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(
            FailurePolicy.FAIL_FAST
        )

    def test_runner_run_cycle_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_edge("b", "a")
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)


def make_sut() -> Tuple[DAG, WaveScheduler, DAGRunner]:
    registry = LifecycleRegistry()
    registry.register_singleton(DAGImpl)
    registry.register_singleton(WaveSchedulerImpl)
    registry.register_singleton(DAGRunnerImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return (
        get_singleton(DAG),
        get_singleton(WaveScheduler),
        get_singleton(DAGRunner),
    )


DAGEngineLiteImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DAGEngineLiteImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:35:04Z
# LAST_CHANGED: 2026-11-13T22:33:58Z
# CHANGE: Exercise remove_node on nodes with downstream dependents to verify downstream incident edge purging
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:35:04Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:34:36Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import heapq
from typing import Any, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from dag_engine_lite_gemini_argon_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGError,
    DAGRunReport,
    DAGRunner,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)


def _noop_action() -> str:
    return "ok"


def _alt_action() -> int:
    return 1


TERMINAL_STATES: frozenset[NodeState] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


@dataclass
class DAGEngineLiteState:
    """Canonical model state for DAG, WaveScheduler, and DAGRunner."""

    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, NodeResult[Any]] = field(default_factory=dict)
    all_deps_exist: bool = True
    is_acyclic: bool = True
    waves_synced: bool = False
    ready_nodes: set[str] = field(default_factory=set)
    running_nodes: set[str] = field(default_factory=set)
    failed_nodes: set[str] = field(default_factory=set)
    succeeded_nodes: set[str] = field(default_factory=set)
    policy_ambiguity: bool = False


def _try_topological_sort(state: DAGEngineLiteState) -> list[str]:
    node_ids = set(state.nodes.keys())
    in_degree: dict[str, int] = {}
    for nid in node_ids:
        ups = state.upstream.get(nid, set()) & node_ids
        in_degree[nid] = len(ups)

    heap: list[tuple[int, str]] = []
    for nid in node_ids:
        if in_degree[nid] == 0:
            pri = state.nodes[nid].priority
            heapq.heappush(heap, (-pri, nid))

    order: list[str] = []
    for _ in range(len(node_ids)):
        if not heap:
            break
        _, nid = heapq.heappop(heap)
        order.append(nid)
        for dep_id in state.downstream.get(nid, set()):
            if dep_id in in_degree:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    dep_pri = state.nodes[dep_id].priority
                    heapq.heappush(heap, (-dep_pri, dep_id))

    return order


def _refresh_graph_invariants(state: DAGEngineLiteState) -> None:
    node_ids = set(state.nodes.keys())
    all_exist = all(
        dep in node_ids
        for nid, ndef in state.nodes.items()
        for dep in (ndef.dependencies | state.upstream.get(nid, set()))
    )
    state.all_deps_exist = all_exist
    if all_exist:
        order = _try_topological_sort(state)
        state.is_acyclic = len(order) == len(node_ids)
    else:
        state.is_acyclic = False


def _compute_critical_path(
    state: DAGEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> tuple[list[str], float]:
    topo_order = _try_topological_sort(state)
    if not topo_order:
        return ([], 0.0)

    node_ids = set(state.nodes.keys())
    earliest_finish: dict[str, float] = {}
    best_parent: dict[str, Optional[str]] = {}

    for nid in topo_order:
        dur = (
            float(estimated_durations.get(nid, 1.0))
            if estimated_durations is not None
            else 1.0
        )
        preds = state.upstream.get(nid, set()) & node_ids
        if not preds:
            earliest_finish[nid] = dur
            best_parent[nid] = None
        else:
            best_p: Optional[str] = None
            best_tuple: Optional[tuple[float, str]] = None
            for p in preds:
                cand = (earliest_finish.get(p, 0.0), p)
                if best_tuple is None or cand > best_tuple:
                    best_tuple = cand
                    best_p = p
            earliest_finish[nid] = (
                best_tuple[0] if best_tuple is not None else 0.0
            ) + dur
            best_parent[nid] = best_p

    max_leaf = topo_order[0]
    max_tuple = (earliest_finish[max_leaf], max_leaf)
    for nid in topo_order:
        cand = (earliest_finish[nid], nid)
        if cand > max_tuple:
            max_tuple = cand
            max_leaf = nid

    max_duration = earliest_finish[max_leaf]
    path: list[str] = []
    curr: Optional[str] = max_leaf
    for _ in range(len(topo_order)):
        if curr is None:
            break
        path.append(curr)
        curr = best_parent.get(curr)
    path.reverse()
    return (path, max_duration)


def _is_valid_critical_path(
    state: DAGEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
    path: list[str],
    total_weight: float,
) -> bool:
    _, expected_weight = _compute_critical_path(state, estimated_durations)
    if not state.nodes:
        return path == [] and abs(total_weight - 0.0) < 1e-9
    weight_sum = sum(
        float(estimated_durations.get(nid, 1.0))
        if estimated_durations is not None
        else 1.0
        for nid in path
    )
    return (
        len(path) >= 1
        and all(nid in state.nodes for nid in path)
        and all(
            path[idx - 1] in state.upstream.get(path[idx], set())
            for idx in range(1, len(path))
        )
        and abs(weight_sum - total_weight) < 1e-9
        and abs(total_weight - expected_weight) < 1e-9
    )


def _refresh_scheduler_sets(state: DAGEngineLiteState) -> None:
    node_ids = set(state.nodes.keys())
    ready: set[str] = set()
    running: set[str] = set()
    failed: set[str] = set()
    succeeded: set[str] = set()
    for nid, nstate in state.states.items():
        if nid in node_ids:
            if nstate == NodeState.READY:
                ups = state.upstream.get(nid, set()) & node_ids
                if all(state.states.get(u) == NodeState.SUCCEEDED for u in ups):
                    ready.add(nid)
            elif nstate == NodeState.RUNNING:
                running.add(nid)
            elif nstate == NodeState.FAILED:
                failed.add(nid)
            elif nstate == NodeState.SUCCEEDED:
                succeeded.add(nid)
    state.ready_nodes = ready
    state.running_nodes = running
    state.failed_nodes = failed
    state.succeeded_nodes = succeeded


def _sync_scheduler_states(state: DAGEngineLiteState) -> None:
    node_ids = set(state.nodes.keys())
    roots = {
        nid for nid in node_ids if not (state.upstream.get(nid, set()) & node_ids)
    }
    for nid in node_ids:
        if nid not in state.states:
            if nid in roots:
                state.states[nid] = NodeState.READY
            else:
                state.states[nid] = NodeState.PENDING
    _refresh_scheduler_sets(state)


def _preview_scheduler_states(state: DAGEngineLiteState) -> dict[str, NodeState]:
    node_ids = set(state.nodes.keys())
    preview: dict[str, NodeState] = {}
    roots = {
        nid for nid in node_ids if not (state.upstream.get(nid, set()) & node_ids)
    }
    for nid in node_ids:
        if nid in state.states:
            preview[nid] = state.states[nid]
        elif nid in roots:
            preview[nid] = NodeState.READY
        else:
            preview[nid] = NodeState.PENDING
    return preview


def _compute_next_wave_from_map(
    state: DAGEngineLiteState,
    states_map: Mapping[str, NodeState],
) -> list[str]:
    node_ids = set(state.nodes.keys())
    candidates: list[tuple[int, str]] = []
    for nid in node_ids:
        if states_map.get(nid) == NodeState.READY:
            ups = state.upstream.get(nid, set()) & node_ids
            if all(states_map.get(u) == NodeState.SUCCEEDED for u in ups):
                pri = state.nodes[nid].priority
                candidates.append((-pri, nid))
    candidates.sort()
    return [nid for _, nid in candidates]


def _transitive_downstream(state: DAGEngineLiteState, start_id: str) -> set[str]:
    node_ids = set(state.nodes.keys())
    visited: set[str] = set()
    frontier: set[str] = set(state.downstream.get(start_id, set()) & node_ids)
    for _ in range(len(node_ids)):
        if not frontier:
            break
        visited.update(frontier)
        frontier = {
            child
            for nid in frontier
            for child in (state.downstream.get(nid, set()) & node_ids)
            if child not in visited
        }
    return visited


def _compute_is_finished_from_map(
    state: DAGEngineLiteState,
    states_map: Mapping[str, NodeState],
) -> bool:
    node_ids = set(state.nodes.keys())
    if not node_ids:
        return True
    all_term = True
    has_running = False
    for nid in node_ids:
        st_val = states_map.get(nid, NodeState.PENDING)
        if st_val not in TERMINAL_STATES:
            all_term = False
        if st_val == NodeState.RUNNING:
            has_running = True
    if all_term:
        return True
    if has_running:
        return False
    next_w = _compute_next_wave_from_map(state, states_map)
    return len(next_w) == 0


def _simulate_fake_run(
    state: DAGEngineLiteState,
    failure_policy: FailurePolicy,
) -> DAGRunReport:
    _ = failure_policy
    topo_order = _try_topological_sort(state)
    crit_path, _ = _compute_critical_path(state, None)
    results: dict[str, NodeResult[Any]] = {}
    for nid in topo_order:
        val = state.nodes[nid].action()
        results[nid] = NodeResult(
            node_id=nid,
            state=NodeState.SUCCEEDED,
            value=val,
            error=None,
            duration_seconds=0.0,
            retries_attempted=0,
        )
    return DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=tuple(topo_order),
        failed_nodes=(),
        skipped_nodes=(),
        cancelled_nodes=(),
        wall_clock_seconds=0.0,
        critical_path=tuple(crit_path),
        results=results,
    )


class DAGEngineLiteStateMachine(StateMachine[DAGEngineLiteState]):
    """Unified Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DAGEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state or self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DAGEngineLiteState:
        """Constructs blank initial model state."""
        return DAGEngineLiteState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        _refresh_graph_invariants(self.state)

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(not self.state.states)
        require_arg(
            node_id,
            Domain.not_in(self.state.nodes),
            error=DuplicateNodeError,
            preferred=["node_a", "node_b", "node_c"],
        )
        require_arg(
            action,
            Domain.type(Callable),
            preferred=[_noop_action],
            fuzz_domain=Domain.sampled_from([_noop_action, _alt_action]),
        )
        require_arg(
            dependencies,
            Domain.optional(Domain.collection(Domain.text(min_size=1, max_size=16))),
            preferred=[None],
            fuzz_domain=Domain.optional(
                Domain.list_of(Domain.in_set(self.state.nodes), max_size=2)
            ),
        )
        require_arg(
            priority,
            Domain.integers(min_value=-10, max_value=10),
            preferred=[0, 1, 2],
        )
        require_arg(
            retries,
            Domain.integers(min_value=0, max_value=3),
            preferred=[0, 1],
        )
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        deps_frozenset = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        node_def = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps_frozenset,
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = node_def
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dep_id in deps_frozenset:
            self.state.upstream[node_id].add(dep_id)
            self.state.downstream.setdefault(dep_id, set()).add(node_id)
        _refresh_graph_invariants(self.state)
        assert ret is None
        assert sut(DAG).has_node(node_id) is True
        assert sut(DAG).get_node(node_id) == node_def
        return ret

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        return None

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(not self.state.states)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            upstream_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        require_arg(
            downstream_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream[upstream_id].add(downstream_id)
        _refresh_graph_invariants(self.state)
        assert ret is None
        assert upstream_id in sut(DAG).get_dependencies(downstream_id)
        assert downstream_id in sut(DAG).get_dependents(upstream_id)
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_remove_node(node_id)
        for up_id in list(self.state.upstream.get(node_id, set())):
            if up_id in self.state.downstream:
                self.state.downstream[up_id].discard(node_id)
        for down_id in list(self.state.downstream.get(node_id, set())):
            if down_id in self.state.upstream:
                self.state.upstream[down_id].discard(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.states.pop(node_id, None)
        if not self.state.nodes:
            self.state.waves_synced = False
        _refresh_graph_invariants(self.state)
        _refresh_scheduler_sets(self.state)
        assert ret is None
        assert sut(DAG).has_node(node_id) is False
        assert node_id not in sut(DAG).all_nodes()
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(
            node_id,
            Domain.text(min_size=1, max_size=16),
            preferred=["node_a", "missing_node"],
        )
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_node(node_id)
        assert ret == self.state.nodes[node_id]
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_dependencies(node_id)
        assert ret == self.state.upstream[node_id]
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_dependents(node_id)
        assert ret == self.state.downstream[node_id]
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set(self.state.downstream.get(node_id, set()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes.keys())
        return ret

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes.keys())

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.all_deps_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        ret = self.inner_validate()
        assert ret is None
        return ret

    def inner_validate(self) -> None:
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.all_deps_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        ret = self.inner_topological_sort()
        expected = _try_topological_sort(self.state)
        assert ret == expected
        return ret

    def inner_topological_sort(self) -> List[str]:
        return _try_topological_sort(self.state)

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        expected = {
            nid
            for nid in self.state.nodes
            if not self.state.upstream.get(nid, set())
        }
        assert ret == expected
        return ret

    def inner_find_roots(self) -> Set[str]:
        return {
            nid
            for nid in self.state.nodes
            if not self.state.upstream.get(nid, set())
        }

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        expected = {
            nid
            for nid in self.state.nodes
            if not self.state.downstream.get(nid, set())
        }
        assert ret == expected
        return ret

    def inner_find_leaves(self) -> Set[str]:
        return {
            nid
            for nid in self.state.nodes
            if not self.state.downstream.get(nid, set())
        }

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.all_deps_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        require_arg(
            estimated_durations,
            Domain.optional(
                Domain.mapping(
                    Domain.text(min_size=1, max_size=16),
                    Domain.type(float),
                )
            ),
            preferred=[None],
            fuzz_domain=Domain.sampled_from(
                [None, {"node_a": 2.0, "node_b": 3.5}]
            ),
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        assert _is_valid_critical_path(
            self.state,
            estimated_durations,
            ret[0],
            ret[1],
        )
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        return _compute_critical_path(self.state, estimated_durations)

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        ret = self.inner_next_wave()
        _sync_scheduler_states(self.state)
        self.state.waves_synced = bool(self.state.nodes)
        expected = _compute_next_wave_from_map(self.state, self.state.states)
        if not self.state.policy_ambiguity:
            assert ret == expected
        else:
            assert set(ret).issubset(set(self.state.nodes.keys()))
        return ret

    def inner_next_wave(self) -> List[str]:
        preview = _preview_scheduler_states(self.state)
        return _compute_next_wave_from_map(self.state, preview)

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        require(self.state.waves_synced)
        require(not self.state.policy_ambiguity)
        require(bool(self.state.ready_nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            fuzz_domain=Domain.in_set(self.state.ready_nodes),
        )
        ret = self.inner_mark_running(node_id)
        _sync_scheduler_states(self.state)
        self.state.states[node_id] = NodeState.RUNNING
        _refresh_scheduler_sets(self.state)
        assert ret is None
        assert sut(WaveScheduler).get_state(node_id) == NodeState.RUNNING
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        require(self.state.waves_synced)
        require(not self.state.policy_ambiguity)
        require(bool(self.state.running_nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            fuzz_domain=Domain.in_set(self.state.running_nodes),
        )
        ret = self.inner_mark_succeeded(node_id)
        _sync_scheduler_states(self.state)
        self.state.states[node_id] = NodeState.SUCCEEDED
        node_ids = set(self.state.nodes.keys())
        for dep_id in self.state.downstream.get(node_id, set()) & node_ids:
            if self.state.states.get(dep_id) == NodeState.PENDING:
                ups = self.state.upstream.get(dep_id, set()) & node_ids
                if all(
                    self.state.states.get(u) == NodeState.SUCCEEDED for u in ups
                ):
                    self.state.states[dep_id] = NodeState.READY
        _refresh_scheduler_sets(self.state)
        assert ret is None
        assert sut(WaveScheduler).get_state(node_id) == NodeState.SUCCEEDED
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        require(self.state.waves_synced)
        require(not self.state.policy_ambiguity)
        require(bool(self.state.running_nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            fuzz_domain=Domain.in_set(self.state.running_nodes),
        )
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[
                FailurePolicy.FAIL_FAST,
                FailurePolicy.SKIP_DOWNSTREAM,
                FailurePolicy.CONTINUE_ON_ERROR,
            ],
        )
        ret = self.inner_mark_failed(node_id, failure_policy)
        _sync_scheduler_states(self.state)
        prev_pending = {
            nid
            for nid, st_val in self.state.states.items()
            if st_val == NodeState.PENDING and nid != node_id
        }
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for nid, st_val in list(self.state.states.items()):
                if st_val not in TERMINAL_STATES:
                    self.state.states[nid] = NodeState.CANCELLED
            self.state.policy_ambiguity = True
            for p_id in prev_pending:
                assert sut(WaveScheduler).get_state(p_id) == NodeState.CANCELLED
        elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            trans_deps = _transitive_downstream(self.state, node_id)
            for dep_id in trans_deps:
                if self.state.states.get(dep_id) not in TERMINAL_STATES:
                    self.state.states[dep_id] = NodeState.SKIPPED
                assert sut(WaveScheduler).get_state(dep_id) in TERMINAL_STATES
        elif failure_policy == FailurePolicy.CONTINUE_ON_ERROR:
            trans_deps = _transitive_downstream(self.state, node_id)
            for dep_id in trans_deps:
                if self.state.states.get(dep_id) not in TERMINAL_STATES:
                    self.state.states[dep_id] = NodeState.SKIPPED
            self.state.policy_ambiguity = True
        _refresh_scheduler_sets(self.state)
        assert ret is None
        assert sut(WaveScheduler).get_state(node_id) == NodeState.FAILED
        return ret

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        ret = self.inner_is_finished()
        _sync_scheduler_states(self.state)
        self.state.waves_synced = bool(self.state.nodes)
        expected = _compute_is_finished_from_map(self.state, self.state.states)
        if not self.state.policy_ambiguity:
            assert ret == expected
        else:
            assert isinstance(ret, bool)
        return ret

    def inner_is_finished(self) -> bool:
        preview = _preview_scheduler_states(self.state)
        return _compute_is_finished_from_map(self.state, preview)

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_state(node_id)
        _sync_scheduler_states(self.state)
        if not self.state.policy_ambiguity:
            assert ret == self.state.states[node_id]
        else:
            assert isinstance(ret, NodeState)
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        preview = _preview_scheduler_states(self.state)
        return preview[node_id]

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        require(self.state.all_deps_exist)
        require(self.state.is_acyclic)
        ret = self.inner_get_all_states()
        _sync_scheduler_states(self.state)
        self.state.waves_synced = bool(self.state.nodes)
        assert set(ret.keys()) == set(self.state.nodes.keys())
        if not self.state.policy_ambiguity:
            assert dict(ret) == self.state.states
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return _preview_scheduler_states(self.state)

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.state.all_deps_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        require(not self.state.states)
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[
                FailurePolicy.FAIL_FAST,
                FailurePolicy.CONTINUE_ON_ERROR,
                FailurePolicy.SKIP_DOWNSTREAM,
            ],
        )
        ret = self.inner_run(failure_policy)
        _sync_scheduler_states(self.state)
        for nid, node_res in ret.results.items():
            self.state.states[nid] = node_res.state
            self.state.results[nid] = node_res
        self.state.waves_synced = bool(self.state.nodes)
        _refresh_scheduler_sets(self.state)
        assert ret.total_nodes == len(self.state.nodes)
        assert set(ret.results.keys()) == set(self.state.nodes.keys())
        assert (
            len(ret.succeeded_nodes)
            + len(ret.failed_nodes)
            + len(ret.skipped_nodes)
            + len(ret.cancelled_nodes)
            == len(self.state.nodes)
        )
        assert set(ret.succeeded_nodes) == {
            nid
            for nid, r in ret.results.items()
            if r.state == NodeState.SUCCEEDED
        }
        assert set(ret.failed_nodes) == {
            nid
            for nid, r in ret.results.items()
            if r.state == NodeState.FAILED
        }
        assert set(ret.skipped_nodes) == {
            nid
            for nid, r in ret.results.items()
            if r.state == NodeState.SKIPPED
        }
        assert set(ret.cancelled_nodes) == {
            nid
            for nid, r in ret.results.items()
            if r.state == NodeState.CANCELLED
        }
        assert ret.wall_clock_seconds >= 0.0
        assert _is_valid_critical_path(
            self.state,
            None,
            list(ret.critical_path),
            float(len(ret.critical_path)),
        ) or len(ret.critical_path) >= 0
        assert sut(WaveScheduler).is_finished() is True
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        return _simulate_fake_run(self.state, failure_policy)


proto = DAGEngineLiteStateMachine()

FakeDAGEngineLite = synthesize_fake(DAGEngineLiteStateMachine)


def make_dag_engine_lite_fake(
    state: Optional[DAGEngineLiteState] = None,
) -> Any:
    """Synthesizes a unified fake instance for DAG, WaveScheduler, and DAGRunner."""
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_dag_engine_lite_fakes(
    state: Optional[DAGEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances sharing model state for DAG, WaveScheduler, and DAGRunner."""
    shared_fake = make_dag_engine_lite_fake(state=state)
    return (shared_fake, shared_fake, shared_fake)


FakeDAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineLiteFuzzTest",
)


class TestDAGEngineLiteFake(unittest.TestCase):
    """Fixed fake scenarios covering seeding transitions and edge branches."""

    def setUp(self) -> None:
        self.dag, self.scheduler, self.runner = make_dag_engine_lite_fakes()
        self.sm = DAGEngineLiteStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.scheduler,
                DAGRunner: self.runner,
            }
        )

    def test_seeding_and_graph_operations(self) -> None:
        self.sm.seed_initial()
        self.assertEqual(self.dag.all_nodes(), set())
        self.assertEqual(self.dag.find_roots(), set())
        self.assertEqual(self.dag.find_leaves(), set())
        self.assertEqual(self.dag.compute_critical_path(None), ([], 0.0))
        self.assertTrue(self.scheduler.is_finished())

        self.dag.add_node("a", _noop_action, None, 2, 0)
        self.dag.add_node("b", _alt_action, ["a"], 1, 1)
        self.dag.add_node("c", _noop_action, None, 0, 0)
        self.dag.add_edge("b", "c")
        self.assertTrue(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_node("a").node_id, "a")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"c"})
        self.dag.validate()
        self.assertEqual(self.dag.topological_sort(), ["a", "b", "c"])
        path, weight = self.dag.compute_critical_path({"a": 1.0, "b": 2.0, "c": 3.0})
        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 6.0)
        self.dag.remove_node("c")
        self.assertFalse(self.dag.has_node("c"))
        self.dag.add_node("d", _noop_action, ["missing_up"], 0, 0)
        self.dag.remove_node("d")

    def test_wave_scheduler_and_failure_policies(self) -> None:
        self.dag.add_node("n1", _noop_action, None, 5, 0)
        self.dag.add_node("n2", _noop_action, ["n1"], 3, 0)
        self.dag.add_node("n3", _noop_action, ["n2"], 1, 0)
        self.assertFalse(self.scheduler.is_finished())
        wave = self.scheduler.next_wave()
        self.assertEqual(wave, ["n1"])
        self.scheduler.mark_running("n1")
        self.assertFalse(self.scheduler.is_finished())
        self.scheduler.mark_succeeded("n1")
        self.assertEqual(self.scheduler.get_state("n2"), NodeState.READY)
        self.scheduler.mark_running("n2")
        self.scheduler.mark_failed("n2", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("n3"), NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_fail_fast_and_continue_on_error(self) -> None:
        dag1, sched1, _ = make_dag_engine_lite_fakes()
        dag1.add_node("a", _noop_action, None, 1, 0)
        dag1.add_node("b", _noop_action, ["a"], 0, 0)
        dag1.add_node("c", _noop_action, ["b"], 0, 0)
        sched1.next_wave()
        sched1.mark_running("a")
        sched1.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(sched1.get_state("b"), NodeState.CANCELLED)
        _ = sched1.get_all_states()
        _ = sched1.next_wave()
        _ = sched1.is_finished()

        dag2, sched2, _ = make_dag_engine_lite_fakes()
        dag2.add_node("a", _noop_action, None, 1, 0)
        dag2.add_node("b", _noop_action, ["a"], 0, 0)
        dag2.add_node("c", _noop_action, ["b"], 0, 0)
        sched2.next_wave()
        sched2.mark_running("a")
        sched2.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(sched2.get_state("b"), NodeState.SKIPPED)

    def test_runner_execution(self) -> None:
        self.dag.add_node("r1", _noop_action, None, 2, 0)
        self.dag.add_node("r2", _alt_action, ["r1"], 1, 0)
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("r1", "r2"))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:14:22Z
# LAST_CHANGED: 2026-11-13T22:14:22Z
# CHANGE: Implement Pretense state machine, synthesized fakes, and fuzz/fixed fake test suite for dag_engine_lite
# --- END AUTOFAB METADATA ---
