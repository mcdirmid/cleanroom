# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from dag_engine_lite_gemini_carbon_1.parts.dag_engine_lite.lib import dag_engine_lite_impl
from dag_engine_lite_gemini_carbon_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG as DAGInterface,
    DAGRunner as DAGRunnerInterface,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
    WaveScheduler as WaveSchedulerInterface,
)
from dag_engine_lite_gemini_carbon_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
)
from dag_engine_lite_gemini_carbon_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    ACTION_FAIL,
    ACTION_OK,
    DAGEngineLiteStateMachine,
    make_flaky_action,
)


class DAGEngineLiteImplPseudoStateMachine(DAGEngineLiteStateMachine):
    """Implementation pseudo-state machine driving concrete DAG, WaveScheduler, and DAGRunner."""

    # --------------------------------------------------------------------------
    # DAG Inner Transitions
    # --------------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: DAGInterface = sut(DAGInterface)
        return target.add_node(node_id, action, dependencies, priority, retries)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAGInterface = sut(DAGInterface)
        return target.add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        target: DAGInterface = sut(DAGInterface)
        return target.remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        target: DAGInterface = sut(DAGInterface)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAGInterface = sut(DAGInterface)
        return target.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: DAGInterface = sut(DAGInterface)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: DAGInterface = sut(DAGInterface)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        target: DAGInterface = sut(DAGInterface)
        return target.all_nodes()

    def inner_validate(self) -> None:
        target: DAGInterface = sut(DAGInterface)
        return target.validate()

    def inner_topological_sort(self) -> List[str]:
        target: DAGInterface = sut(DAGInterface)
        return target.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        target: DAGInterface = sut(DAGInterface)
        return target.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        target: DAGInterface = sut(DAGInterface)
        return target.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: DAGInterface = sut(DAGInterface)
        return target.compute_critical_path(estimated_durations)

    # --------------------------------------------------------------------------
    # WaveScheduler Inner Transitions
    # --------------------------------------------------------------------------

    def inner_next_wave(self) -> List[str]:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.mark_succeeded(node_id)

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveSchedulerInterface = sut(WaveSchedulerInterface)
        return target.get_all_states()

    # --------------------------------------------------------------------------
    # DAGRunner Inner Transitions
    # --------------------------------------------------------------------------

    def inner_run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        target: DAGRunnerInterface = sut(DAGRunnerInterface)
        return target.run(failure_policy)


proto = DAGEngineLiteImplPseudoStateMachine()


def make_sut() -> Tuple[DAGInterface, WaveSchedulerInterface, DAGRunnerInterface]:
    _ = dag_engine_lite_impl
    registry = LifecycleRegistry()
    registry.register_singleton(DAG, keys=[DAG, DAGInterface], tier=system)
    registry.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, WaveSchedulerInterface],
        tier=system,
    )
    registry.register_singleton(
        DAGRunner,
        keys=[DAGRunner, DAGRunnerInterface],
        tier=system,
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return (
        get_singleton(DAGInterface),
        get_singleton(WaveSchedulerInterface),
        get_singleton(DAGRunnerInterface),
    )


class TestDAGEngineLiteImplReal(LifecycleTestCase):
    """Deterministic scenario and contract violation verification for dag_engine_lite_impl."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        dag = get_singleton(DAGInterface)
        scheduler = get_singleton(WaveSchedulerInterface)
        runner = get_singleton(DAGRunnerInterface)
        self.sm = DAGEngineLiteImplPseudoStateMachine(
            singletons={
                DAGInterface: dag,
                WaveSchedulerInterface: scheduler,
                DAGRunnerInterface: runner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAGInterface, dag)
        self.checked_scheduler = self.sm.as_checked(WaveSchedulerInterface, scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunnerInterface, runner)

    # --------------------------------------------------------------------------
    # Operational Scenarios (DAG, WaveScheduler, DAGRunner)
    # --------------------------------------------------------------------------

    def test_empty_dag_operations_and_run(self) -> None:
        self.checked_dag.all_nodes()
        self.checked_dag.has_node("missing_node")
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.validate()
        self.checked_dag.topological_sort()
        self.checked_dag.compute_critical_path(None)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()
        self.checked_scheduler.get_all_states()
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_dag_graph_queries_critical_path_and_mutation(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 1)
        self.checked_dag.add_node("n3", ACTION_OK, ["n1"], 8, 0)
        self.checked_dag.add_node("n4", ACTION_OK, None, 1, 0)
        self.checked_dag.add_edge("n2", "n4")
        self.checked_dag.add_edge("n3", "n4")

        self.checked_dag.has_node("n1")
        self.checked_dag.has_node("missing_node")
        self.checked_dag.get_node("n2")
        self.checked_dag.get_dependencies("n4")
        self.checked_dag.get_dependents("n1")
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.validate()
        self.checked_dag.topological_sort()
        self.checked_dag.compute_critical_path(None)
        self.checked_dag.compute_critical_path({"n1": 2.0, "n2": 5.0, "n3": 1.0, "n4": 3.0})

        self.checked_scheduler.get_state("n4")
        self.checked_dag.remove_node("n3")
        self.checked_dag.all_nodes()
        self.checked_scheduler.get_all_states()

    def test_wave_scheduler_manual_progression_and_unblocking(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n2"], 2, 0)

        self.checked_scheduler.is_finished()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_state("n1")
        self.checked_scheduler.get_state("n2")
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
        self.checked_scheduler.get_all_states()

    def test_wave_scheduler_mark_failed_skip_downstream(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n2"], 1, 0)
        self.checked_dag.add_node("n4", ACTION_OK, None, 2, 0)

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.get_state("n3")
        self.checked_scheduler.get_state("n4")
        self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_running("n4")
        self.checked_scheduler.mark_succeeded("n4")
        self.checked_scheduler.is_finished()

    def test_wave_scheduler_mark_failed_fail_fast(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, None, 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n1"], 1, 0)

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.FAIL_FAST)
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_wave_scheduler_mark_failed_continue_on_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, None, 2, 0)

        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_scheduler.is_finished()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n3")
        self.checked_scheduler.mark_succeeded("n3")
        self.checked_scheduler.is_finished()

    def test_runner_run_success_and_flaky_retry(self) -> None:
        self.checked_dag.add_node("n1", make_flaky_action(), None, 10, 2)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_run_fail_fast_with_retries_exhausted(self) -> None:
        self.checked_dag.add_node("n1", ACTION_FAIL, None, 10, 1)
        self.checked_dag.add_node("n2", ACTION_OK, None, 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n1"], 1, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_run_skip_downstream(self) -> None:
        self.checked_dag.add_node("n1", ACTION_FAIL, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, None, 2, 0)
        self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_run_continue_on_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_FAIL, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, None, 2, 0)
        self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_remove_blocking_node_promotes_dependent(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_scheduler.get_state("n2")
        self.checked_dag.remove_node("n1")
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.next_wave()

    def test_remove_node_with_unregistered_dependencies(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, ["unregistered_up1", "unregistered_up2"], 5, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 1, 0)
        self.checked_dag.get_dependencies("n1")
        self.checked_dag.remove_node("n1")
        self.checked_dag.has_node("n1")
        self.checked_dag.validate()
        self.checked_scheduler.get_state("n2")

    def test_add_edge_to_ready_node_demotes_to_pending(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, None, 5, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_state("n2")
        self.checked_dag.add_edge("n1", "n2")
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_succeeded("n1")
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.next_wave()

    def test_diamond_reconvergence_mark_failed_skip_downstream(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n1"], 4, 0)
        self.checked_dag.add_node("n4", ACTION_OK, ["n2", "n3"], 1, 0)
        self.checked_dag.add_node("n5", ACTION_OK, ["n4"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_diamond_reconvergence_mark_failed_continue_on_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n1"], 4, 0)
        self.checked_dag.add_node("n4", ACTION_OK, ["n2", "n3"], 1, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_is_finished_pending_chain_blocked_by_terminal_failure(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_failed("n1", FailurePolicy.CONTINUE_ON_ERROR)
        # Register downstream multi-hop chain after n1 is already in FAILED state
        # so n2, n3, n4 initialize as PENDING with upstream n1 in terminal FAILED state
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n2"], 3, 0)
        self.checked_dag.add_node("n4", ACTION_OK, ["n3"], 1, 0)
        self.checked_scheduler.get_state("n2")
        self.checked_scheduler.get_state("n4")
        self.checked_scheduler.is_finished()

    def test_is_finished_pending_chain_with_running_upstream(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n2"], 3, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.is_finished()

    def test_is_finished_cyclic_mutually_dependent_pending_nodes(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n2"], 3, 0)
        self.checked_dag.add_edge("n3", "n1")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()

    # --------------------------------------------------------------------------
    # Checked Precondition Violations (*Error)
    # --------------------------------------------------------------------------

    def test_add_node_duplicate_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node("n1", ACTION_OK, None, 0, 0)

    def test_add_edge_missing_upstream_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing_node", "n1")

    def test_add_edge_missing_downstream_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("n1", "missing_node")

    def test_remove_node_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing_node")

    def test_get_node_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_node("missing_node")

    def test_get_dependencies_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing_node")

    def test_get_dependents_not_found_error(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing_node")

    def test_validate_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, ["missing_dep"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 0, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 0, 0)
        self.checked_dag.add_node("n3", ACTION_OK, ["n2"], 0, 0)
        self.checked_dag.add_edge("n3", "n1")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle_error(self) -> None:
        self.checked_dag.add_node("n0", ACTION_OK, None, 10, 0)
        self.checked_dag.add_node("n1", ACTION_OK, ["n0"], 0, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 0, 0)
        self.checked_dag.add_edge("n2", "n1")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_compute_critical_path_cycle_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 0, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 0, 0)
        self.checked_dag.add_edge("n2", "n1")
        self.checked_dag.violating(CycleError).compute_critical_path(None)

    def test_scheduler_get_state_not_found_error(self) -> None:
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing_node")

    def test_runner_run_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, ["missing_dep"], 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(FailurePolicy.FAIL_FAST)

    def test_runner_run_cycle_error(self) -> None:
        self.checked_dag.add_node("n1", ACTION_OK, None, 0, 0)
        self.checked_dag.add_node("n2", ACTION_OK, ["n1"], 0, 0)
        self.checked_dag.add_edge("n2", "n1")
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)


TestDAGEngineLiteImplFuzz = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="TestDAGEngineLiteImplFuzz",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:29:37Z
# LAST_CHANGED: 2026-11-13T22:28:03Z
# CHANGE: Add deterministic scenario test in TestDAGEngineLiteImplReal for scheduler is_finished on mutually dependent cyclic pending nodes
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:29:37Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:29:07Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
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

from dag_engine_lite_gemini_carbon_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGError,
    DAGRunner,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)


# ==============================================================================
# Helper Functions (Graph Algorithms & Action Builders Outside Transitions)
# ==============================================================================


def make_success_action() -> Callable[[], str]:
    def _ok() -> str:
        return "ok"

    return _ok


def make_failing_action() -> Callable[[], str]:
    def _fail() -> str:
        raise RuntimeError("boom")

    return _fail


def make_flaky_action() -> Callable[[], str]:
    attempts: List[int] = [0]

    def _flaky() -> str:
        attempts[0] += 1
        if attempts[0] == 1:
            raise RuntimeError("transient")
        return "recovered"

    return _flaky


ACTION_OK: Callable[[], str] = make_success_action()
ACTION_FAIL: Callable[[], str] = make_failing_action()


def all_deps_present(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> bool:
    node_ids = set(nodes.keys())
    for nid, deps in upstream.items():
        if nid in node_ids:
            for dep in deps:
                if dep not in node_ids:
                    return False
    return True


def is_acyclic(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> bool:
    order = compute_kahn_order(nodes, upstream, downstream)
    return order is not None


def compute_kahn_order(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> Optional[List[str]]:
    import heapq

    node_set = set(nodes.keys())
    in_degree: Dict[str, int] = {
        nid: len(upstream.get(nid, set()) & node_set) for nid in node_set
    }
    heap: List[Tuple[int, str]] = []
    for nid in node_set:
        if in_degree[nid] == 0:
            heapq.heappush(heap, (-nodes[nid].priority, nid))

    order: List[str] = []
    for _ in range(len(node_set)):
        if not heap:
            break
        _, nid = heapq.heappop(heap)
        order.append(nid)
        for dep_id in downstream.get(nid, set()):
            if dep_id in in_degree:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    heapq.heappush(heap, (-nodes[dep_id].priority, dep_id))

    if len(order) != len(node_set):
        return None
    return order


def compute_critical_path_model(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    order = compute_kahn_order(nodes, upstream, downstream)
    assert order is not None
    if not order:
        return [], 0.0

    earliest_finish: Dict[str, float] = {}
    best_parent: Dict[str, Optional[str]] = {}

    for nid in order:
        dur = (
            float(estimated_durations[nid])
            if estimated_durations is not None and nid in estimated_durations
            else 1.0
        )
        preds = upstream.get(nid, set()) & set(nodes.keys())
        if not preds:
            earliest_finish[nid] = dur
            best_parent[nid] = None
        else:
            best_p: Optional[str] = None
            best_val: float = -1.0
            for p in sorted(preds):
                val = earliest_finish.get(p, 0.0)
                if best_p is None or (val, p) > (best_val, best_p):
                    best_val = val
                    best_p = p
            earliest_finish[nid] = best_val + dur
            best_parent[nid] = best_p

    max_leaf: str = order[0]
    max_val: float = earliest_finish[max_leaf]
    for nid in order[1:]:
        val = earliest_finish[nid]
        if (val, nid) > (max_val, max_leaf):
            max_val = val
            max_leaf = nid

    path: List[str] = []
    curr: Optional[str] = max_leaf
    for _ in range(len(order) + 1):
        if curr is None:
            break
        path.append(curr)
        curr = best_parent.get(curr)
    path.reverse()
    return path, max_val


def get_transitive_dependents(
    start_id: str,
    downstream: Mapping[str, Set[str]],
    valid_nodes: Set[str],
) -> Set[str]:
    visited: Set[str] = set()
    frontier: List[str] = list(downstream.get(start_id, set()) & valid_nodes)
    for _ in range(len(valid_nodes) + 1):
        if not frontier:
            break
        nxt_frontier: List[str] = []
        for nid in frontier:
            if nid not in visited and nid in valid_nodes:
                visited.add(nid)
                for child in downstream.get(nid, set()):
                    if child in valid_nodes and child not in visited:
                        nxt_frontier.append(child)
        frontier = nxt_frontier
    return visited


def sync_scheduler_states(state: DAGEngineLiteState) -> None:
    registered = set(state.nodes.keys())
    for nid in registered:
        if nid not in state.scheduler_states:
            deps = state.upstream.get(nid, set()) & registered
            if not deps and not state.upstream.get(nid, set()):
                state.scheduler_states[nid] = NodeState.READY
            else:
                state.scheduler_states[nid] = NodeState.PENDING
        elif state.scheduler_states[nid] == NodeState.READY:
            deps = state.upstream.get(nid, set())
            if any(
                dep not in registered or state.scheduler_states.get(dep) != NodeState.SUCCEEDED
                for dep in deps
            ):
                state.scheduler_states[nid] = NodeState.PENDING
        elif state.scheduler_states[nid] == NodeState.PENDING:
            deps = state.upstream.get(nid, set())
            if all(
                dep in registered and state.scheduler_states.get(dep) == NodeState.SUCCEEDED
                for dep in deps
            ):
                state.scheduler_states[nid] = NodeState.READY


def compute_ready_wave(state: DAGEngineLiteState) -> List[str]:
    sync_scheduler_states(state)
    registered = set(state.nodes.keys())
    ready: List[str] = []
    for nid in registered:
        if state.scheduler_states.get(nid) == NodeState.READY:
            deps = state.upstream.get(nid, set())
            if all(
                dep in registered and state.scheduler_states.get(dep) == NodeState.SUCCEEDED
                for dep in deps
            ):
                ready.append(nid)
    ready.sort(key=lambda n: (-state.nodes[n].priority, n))
    return ready


def apply_mark_succeeded(state: DAGEngineLiteState, node_id: str) -> None:
    sync_scheduler_states(state)
    state.scheduler_states[node_id] = NodeState.SUCCEEDED
    registered = set(state.nodes.keys())
    for dep_id in state.downstream.get(node_id, set()):
        if dep_id in registered and state.scheduler_states.get(dep_id) == NodeState.PENDING:
            up_deps = state.upstream.get(dep_id, set())
            if all(
                u in registered and state.scheduler_states.get(u) == NodeState.SUCCEEDED
                for u in up_deps
            ):
                state.scheduler_states[dep_id] = NodeState.READY


def apply_mark_failed(
    state: DAGEngineLiteState,
    node_id: str,
    failure_policy: FailurePolicy,
) -> None:
    sync_scheduler_states(state)
    terminal = {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
    state.scheduler_states[node_id] = NodeState.FAILED
    registered = set(state.nodes.keys())

    if failure_policy == FailurePolicy.FAIL_FAST:
        for nid in registered:
            if state.scheduler_states.get(nid) not in terminal:
                state.scheduler_states[nid] = NodeState.CANCELLED
    elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
        trans_deps = get_transitive_dependents(node_id, state.downstream, registered)
        for dep_id in trans_deps:
            if state.scheduler_states.get(dep_id) not in terminal:
                state.scheduler_states[dep_id] = NodeState.SKIPPED
    elif failure_policy == FailurePolicy.CONTINUE_ON_ERROR:
        trans_deps = get_transitive_dependents(node_id, state.downstream, registered)
        for dep_id in trans_deps:
            if state.scheduler_states.get(dep_id) not in terminal:
                state.scheduler_states[dep_id] = NodeState.SKIPPED


def compute_is_finished(state: DAGEngineLiteState) -> bool:
    sync_scheduler_states(state)
    if not state.nodes:
        return True
    terminal = {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
    if all(state.scheduler_states.get(nid) in terminal for nid in state.nodes):
        return True
    ready = compute_ready_wave(state)
    running = [
        nid
        for nid in state.nodes
        if state.scheduler_states.get(nid) == NodeState.RUNNING
    ]
    if not ready and not running:
        # Check if all remaining PENDING nodes are blocked by failed/skipped/cancelled upstream
        blocked_states = {NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        all_blocked = True
        for nid in state.nodes:
            st_val = state.scheduler_states.get(nid)
            if st_val not in terminal:
                # Check transitive upstream for any failed/skipped/cancelled
                has_failed_ancestor = False
                visited: Set[str] = set()
                frontier = list(state.upstream.get(nid, set()))
                for _ in range(len(state.nodes) + 1):
                    if not frontier:
                        break
                    nxt: List[str] = []
                    for u in frontier:
                        if u not in visited:
                            visited.add(u)
                            if state.scheduler_states.get(u) in blocked_states:
                                has_failed_ancestor = True
                            for p in state.upstream.get(u, set()):
                                if p not in visited:
                                    nxt.append(p)
                    frontier = nxt
                if not has_failed_ancestor:
                    all_blocked = False
        if all_blocked:
            return True
    return False


def simulate_fake_run(
    state: DAGEngineLiteState,
    failure_policy: FailurePolicy,
) -> DAGRunReport:
    # Make a working copy of scheduler states so inner_run does not mutate self.state
    sim_state = DAGEngineLiteState(
        nodes=dict(state.nodes),
        upstream={k: set(v) for k, v in state.upstream.items()},
        downstream={k: set(v) for k, v in state.downstream.items()},
        scheduler_states=dict(state.scheduler_states),
    )
    sync_scheduler_states(sim_state)
    results: Dict[str, NodeResult[Any]] = {}

    for _ in range(len(sim_state.nodes) + 2):
        if compute_is_finished(sim_state):
            break
        wave = compute_ready_wave(sim_state)
        halted = False
        for nid in wave:
            sim_state.scheduler_states[nid] = NodeState.RUNNING
            defn = sim_state.nodes[nid]
            succeeded = False
            val: Any = None
            err: Optional[Exception] = None
            attempts = 0
            for attempt in range(defn.retries + 1):
                try:
                    val = defn.action()
                    succeeded = True
                    attempts = attempt
                    break
                except Exception as exc:
                    err = exc
                    attempts = attempt
            if succeeded:
                results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.SUCCEEDED,
                    value=val,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=attempts,
                )
                apply_mark_succeeded(sim_state, nid)
            else:
                results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.FAILED,
                    value=None,
                    error=err,
                    duration_seconds=0.0,
                    retries_attempted=defn.retries,
                )
                apply_mark_failed(sim_state, nid, failure_policy)
                if failure_policy == FailurePolicy.FAIL_FAST:
                    halted = True
                    break
        if halted:
            break

    for nid in sim_state.nodes:
        st_val = sim_state.scheduler_states.get(nid, NodeState.PENDING)
        if nid not in results and st_val in (NodeState.SKIPPED, NodeState.CANCELLED):
            results[nid] = NodeResult(
                node_id=nid,
                state=st_val,
                value=None,
                error=None,
                duration_seconds=0.0,
                retries_attempted=0,
            )

    crit_path, _ = compute_critical_path_model(
        sim_state.nodes,
        sim_state.upstream,
        sim_state.downstream,
        None,
    )

    succeeded_nodes = tuple(
        nid for nid in sim_state.nodes if sim_state.scheduler_states.get(nid) == NodeState.SUCCEEDED
    )
    failed_nodes = tuple(
        nid for nid in sim_state.nodes if sim_state.scheduler_states.get(nid) == NodeState.FAILED
    )
    skipped_nodes = tuple(
        nid for nid in sim_state.nodes if sim_state.scheduler_states.get(nid) == NodeState.SKIPPED
    )
    cancelled_nodes = tuple(
        nid for nid in sim_state.nodes if sim_state.scheduler_states.get(nid) == NodeState.CANCELLED
    )

    return DAGRunReport(
        total_nodes=len(sim_state.nodes),
        succeeded_nodes=succeeded_nodes,
        failed_nodes=failed_nodes,
        skipped_nodes=skipped_nodes,
        cancelled_nodes=cancelled_nodes,
        wall_clock_seconds=0.0,
        critical_path=tuple(crit_path),
        results=results,
    )


def apply_run_to_model_state(
    state: DAGEngineLiteState,
    report: DAGRunReport,
) -> None:
    sync_scheduler_states(state)
    for nid, res in report.results.items():
        if nid in state.nodes:
            state.scheduler_states[nid] = res.state
    for nid in report.succeeded_nodes:
        if nid in state.nodes:
            state.scheduler_states[nid] = NodeState.SUCCEEDED
    for nid in report.failed_nodes:
        if nid in state.nodes:
            state.scheduler_states[nid] = NodeState.FAILED
    for nid in report.skipped_nodes:
        if nid in state.nodes:
            state.scheduler_states[nid] = NodeState.SKIPPED
    for nid in report.cancelled_nodes:
        if nid in state.nodes:
            state.scheduler_states[nid] = NodeState.CANCELLED


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class DAGEngineLiteState:
    """Canonical model state tracking DAG nodes, edges, and wave scheduler state."""

    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    scheduler_states: Dict[str, NodeState] = field(default_factory=dict)
    candidate_ids: List[str] = field(
        default_factory=lambda: ["n1", "n2", "n3", "n4", "n5"]
    )


class DAGEngineLiteStateMachine(StateMachine[DAGEngineLiteState]):
    """Unified Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DAGEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DAGEngineLiteState:
        """Constructs initial blank model state."""
        return DAGEngineLiteState()

    # --------------------------------------------------------------------------
    # Seeding Transitions
    # --------------------------------------------------------------------------

    @transition.seeding
    def seed_linear_dag(self) -> None:
        """Seeds a clean 2-node linear DAG if empty."""
        if not self.state.nodes:
            def_a = NodeDefinition(
                node_id="n1",
                action=ACTION_OK,
                dependencies=frozenset(),
                priority=10,
                retries=0,
            )
            def_b = NodeDefinition(
                node_id="n2",
                action=ACTION_OK,
                dependencies=frozenset({"n1"}),
                priority=5,
                retries=1,
            )
            self.state.nodes["n1"] = def_a
            self.state.nodes["n2"] = def_b
            self.state.upstream["n1"] = set()
            self.state.upstream["n2"] = {"n1"}
            self.state.downstream["n1"] = {"n2"}
            self.state.downstream["n2"] = set()
            sync_scheduler_states(self.state)

    # --------------------------------------------------------------------------
    # DAG Transitions
    # --------------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(
            node_id,
            Domain.not_in(self.state.nodes),
            error=DuplicateNodeError,
            fuzz_domain=Domain.sampled_from(
                [cid for cid in self.state.candidate_ids if cid not in self.state.nodes]
                or ["n_extra"]
            ),
            preferred=["n1", "n2", "n3"],
        )
        require(len(self.state.nodes) < len(self.state.candidate_ids))
        require_arg(
            action,
            Domain.type(object),
            fuzz_domain=Domain.sampled_from([ACTION_OK, ACTION_FAIL]),
            preferred=[ACTION_OK],
        )
        existing_ids = sorted(self.state.nodes.keys())
        require_arg(
            dependencies,
            Domain.optional(Domain.collection(Domain.text(min_size=1))),
            fuzz_domain=Domain.sampled_from(
                [None, []] + ([[existing_ids[0]]] if existing_ids else [])
            ),
            preferred=[None],
        )
        require_arg(
            priority,
            Domain.integers(min_value=-5, max_value=20),
            preferred=[0, 5, 10],
        )
        require_arg(
            retries,
            Domain.integers(min_value=0, max_value=2),
            preferred=[0, 1],
        )

        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)

        deps_set = frozenset(dependencies) if dependencies is not None else frozenset()
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps_set,
            priority=priority,
            retries=retries,
        )
        if node_id not in self.state.upstream:
            self.state.upstream[node_id] = set()
        if node_id not in self.state.downstream:
            self.state.downstream[node_id] = set()
        for dep in deps_set:
            self.state.upstream[node_id].add(dep)
            if dep not in self.state.downstream:
                self.state.downstream[dep] = set()
            self.state.downstream[dep].add(node_id)

        assert ret is None
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
        require(len(self.state.nodes) >= 2)
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

        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)

        assert ret is None
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_remove_node(node_id)

        del self.state.nodes[node_id]
        up_neighbors = self.state.upstream.pop(node_id, set())
        for u in up_neighbors:
            if u in self.state.downstream:
                self.state.downstream[u].discard(node_id)
        down_neighbors = self.state.downstream.pop(node_id, set())
        for d in down_neighbors:
            if d in self.state.upstream:
                self.state.upstream[d].discard(node_id)
        for other_id, up_set in list(self.state.upstream.items()):
            up_set.discard(node_id)
        for other_id, down_set in list(self.state.downstream.items()):
            down_set.discard(node_id)
        self.state.scheduler_states.pop(node_id, None)

        assert ret is None
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(
            node_id,
            Domain.text(min_size=1),
            fuzz_domain=Domain.sampled_from(self.state.candidate_ids + ["missing_node"]),
            preferred=["n1", "missing_node"],
        )

        ret = self.inner_has_node(node_id)

        expected = node_id in self.state.nodes
        assert ret == expected
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_get_node(node_id)

        expected = self.state.nodes[node_id]
        assert ret.node_id == expected.node_id
        assert ret.priority == expected.priority
        assert ret.retries == expected.retries
        assert ret.action is expected.action
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_get_dependencies(node_id)

        expected = set(self.state.upstream.get(node_id, set()))
        assert ret == expected
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_get_dependents(node_id)

        expected = set(self.state.downstream.get(node_id, set()) & set(self.state.nodes.keys()))
        assert ret == expected
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set(self.state.downstream.get(node_id, set()) & set(self.state.nodes.keys()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()

        assert ret == set(self.state.nodes.keys())
        return ret

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes.keys())

    @transition(DAG.validate)
    def validate(self) -> None:
        require(all_deps_present(self.state.nodes, self.state.upstream))
        require(
            is_acyclic(
                self.state.nodes,
                self.state.upstream,
                self.state.downstream,
            )
        )

        ret = self.inner_validate()

        assert ret is None
        return ret

    def inner_validate(self) -> None:
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(
            is_acyclic(
                self.state.nodes,
                self.state.upstream,
                self.state.downstream,
            )
        )

        ret = self.inner_topological_sort()

        expected = compute_kahn_order(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
        )
        assert expected is not None
        assert ret == expected
        return ret

    def inner_topological_sort(self) -> List[str]:
        order = compute_kahn_order(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
        )
        return order if order is not None else []

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

        registered = set(self.state.nodes.keys())
        expected = {
            nid
            for nid in self.state.nodes
            if not (self.state.downstream.get(nid, set()) & registered)
        }
        assert ret == expected
        return ret

    def inner_find_leaves(self) -> Set[str]:
        registered = set(self.state.nodes.keys())
        return {
            nid
            for nid in self.state.nodes
            if not (self.state.downstream.get(nid, set()) & registered)
        }

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(
            is_acyclic(
                self.state.nodes,
                self.state.upstream,
                self.state.downstream,
            )
        )
        require_arg(
            estimated_durations,
            Domain.optional(
                Domain.mapping(
                    Domain.text(min_size=1),
                    Domain.type(float),
                )
            ),
            fuzz_domain=Domain.sampled_from(
                [None, {"n1": 2.5, "n2": 3.0}, {"n1": 1.0, "n3": 4.0}]
            ),
            preferred=[None, {"n1": 2.5, "n2": 3.0}],
        )

        ret = self.inner_compute_critical_path(estimated_durations)

        expected_path, expected_weight = compute_critical_path_model(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )
        assert ret[0] == expected_path
        assert abs(ret[1] - expected_weight) < 1e-6
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        return compute_critical_path_model(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )

    # --------------------------------------------------------------------------
    # WaveScheduler Transitions
    # --------------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        ret = self.inner_next_wave()

        expected = compute_ready_wave(self.state)
        assert ret == expected
        return ret

    def inner_next_wave(self) -> List[str]:
        # Compute without mutating self.state
        sim = DAGEngineLiteState(
            nodes=dict(self.state.nodes),
            upstream={k: set(v) for k, v in self.state.upstream.items()},
            downstream={k: set(v) for k, v in self.state.downstream.items()},
            scheduler_states=dict(self.state.scheduler_states),
        )
        return compute_ready_wave(sim)

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_mark_running(node_id)

        sync_scheduler_states(self.state)
        self.state.scheduler_states[node_id] = NodeState.RUNNING
        assert ret is None
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_mark_succeeded(node_id)

        apply_mark_succeeded(self.state, node_id)
        assert ret is None
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
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

        apply_mark_failed(self.state, node_id, failure_policy)
        assert ret is None
        return ret

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        ret = self.inner_is_finished()

        expected = compute_is_finished(self.state)
        assert ret == expected
        return ret

    def inner_is_finished(self) -> bool:
        sim = DAGEngineLiteState(
            nodes=dict(self.state.nodes),
            upstream={k: set(v) for k, v in self.state.upstream.items()},
            downstream={k: set(v) for k, v in self.state.downstream.items()},
            scheduler_states=dict(self.state.scheduler_states),
        )
        return compute_is_finished(sim)

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(bool(self.state.nodes))
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )

        ret = self.inner_get_state(node_id)

        sync_scheduler_states(self.state)
        expected = self.state.scheduler_states[node_id]
        assert ret == expected
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        sim = DAGEngineLiteState(
            nodes=dict(self.state.nodes),
            upstream={k: set(v) for k, v in self.state.upstream.items()},
            downstream={k: set(v) for k, v in self.state.downstream.items()},
            scheduler_states=dict(self.state.scheduler_states),
        )
        sync_scheduler_states(sim)
        return sim.scheduler_states[node_id]

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        ret = self.inner_get_all_states()

        sync_scheduler_states(self.state)
        expected = {
            nid: self.state.scheduler_states[nid]
            for nid in self.state.nodes
        }
        assert dict(ret) == expected
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        sim = DAGEngineLiteState(
            nodes=dict(self.state.nodes),
            upstream={k: set(v) for k, v in self.state.upstream.items()},
            downstream={k: set(v) for k, v in self.state.downstream.items()},
            scheduler_states=dict(self.state.scheduler_states),
        )
        sync_scheduler_states(sim)
        return {nid: sim.scheduler_states[nid] for nid in sim.nodes}

    # --------------------------------------------------------------------------
    # DAGRunner Transitions
    # --------------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(all_deps_present(self.state.nodes, self.state.upstream))
        require(
            is_acyclic(
                self.state.nodes,
                self.state.upstream,
                self.state.downstream,
            )
        )
        # Ensure no node was artificially placed in RUNNING without completion before run()
        require(
            all(
                st_val != NodeState.RUNNING
                for st_val in self.state.scheduler_states.values()
            )
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

        ret = self.inner_run(failure_policy)
        expected_report = simulate_fake_run(self.state, failure_policy)

        apply_run_to_model_state(self.state, ret)

        expected_crit_path, _ = compute_critical_path_model(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            None,
        )
        assert ret.total_nodes == len(self.state.nodes)
        assert ret.wall_clock_seconds >= 0.0
        assert list(ret.critical_path) == expected_crit_path
        assert len(ret.succeeded_nodes) + len(ret.failed_nodes) + len(ret.skipped_nodes) + len(ret.cancelled_nodes) <= len(self.state.nodes)
        if all(
            defn.action in (ACTION_OK, ACTION_FAIL)
            for defn in self.state.nodes.values()
        ):
            assert set(ret.succeeded_nodes) == set(expected_report.succeeded_nodes)
            assert set(ret.failed_nodes) == set(expected_report.failed_nodes)
            assert set(ret.skipped_nodes) == set(expected_report.skipped_nodes)
            assert set(ret.cancelled_nodes) == set(expected_report.cancelled_nodes)
        return ret

    def inner_run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        return simulate_fake_run(self.state, failure_policy)


proto = DAGEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngineLite = synthesize_fake(DAGEngineLiteStateMachine)


def make_dag_engine_lite_fakes(
    state: Optional[DAGEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for DAG, WaveScheduler, and DAGRunner sharing model state."""
    fake_inst = FakeDAGEngineLite(
        state=state if state is not None else proto.make_initial_state()
    )
    return (fake_inst, fake_inst, fake_inst)


FakeDAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineLiteFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestDAGEngineLiteFake(unittest.TestCase):
    """Fixed fake tests covering edge branches not guaranteed during fuzzing."""

    def setUp(self) -> None:
        self.dag, self.scheduler, self.runner = make_dag_engine_lite_fakes()

    def test_empty_dag_and_failure_policies(self) -> None:
        self.assertEqual(self.dag.all_nodes(), set())
        self.assertEqual(self.dag.find_roots(), set())
        self.assertEqual(self.dag.find_leaves(), set())
        self.assertEqual(self.dag.compute_critical_path(None), ([], 0.0))
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), [])
        empty_report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(empty_report.total_nodes, 0)

        # Build diamond with failing and flaky nodes
        self.dag.add_node("n1", make_flaky_action(), None, 10, 1)
        self.dag.add_node("n2", ACTION_FAIL, ["n1"], 5, 0)
        self.dag.add_node("n3", ACTION_OK, ["n1"], 3, 0)
        self.dag.add_node("n4", ACTION_OK, ["n2"], 1, 0)
        self.dag.validate()
        order = self.dag.topological_sort()
        self.assertEqual(order[0], "n1")
        path, weight = self.dag.compute_critical_path({"n1": 2.0, "n2": 3.0, "n4": 4.0})
        self.assertEqual(path, ["n1", "n2", "n4"])
        self.assertAlmostEqual(weight, 9.0)

        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIn("n1", report.succeeded_nodes)
        self.assertIn("n3", report.succeeded_nodes)
        self.assertIn("n2", report.failed_nodes)
        self.assertIn("n4", report.skipped_nodes)

    def test_fail_fast_and_skip_downstream_and_remove(self) -> None:
        dag, sched, runner = make_dag_engine_lite_fakes()
        dag.add_node("n1", ACTION_FAIL, None, 10, 0)
        dag.add_node("n2", ACTION_OK, None, 1, 0)
        dag.add_node("n3", ACTION_OK, ["n1"], 1, 0)
        dag.add_edge("n1", "n3")
        self.assertTrue(dag.has_node("n1"))
        self.assertEqual(dag.get_node("n1").node_id, "n1")
        self.assertEqual(dag.get_dependencies("n3"), {"n1"})
        self.assertEqual(dag.get_dependents("n1"), {"n3"})

        rep = runner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("n1", rep.failed_nodes)
        self.assertIn("n2", rep.cancelled_nodes)

        dag2, sched2, _ = make_dag_engine_lite_fakes()
        dag2.add_node("n1", ACTION_OK, None, 5, 0)
        dag2.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        dag2.add_node("n3", ACTION_OK, ["n2"], 5, 0)
        self.assertFalse(sched2.is_finished())
        self.assertEqual(sched2.get_state("n1"), NodeState.READY)
        sched2.mark_running("n1")
        self.assertFalse(sched2.is_finished())
        sched2.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(sched2.get_all_states()["n3"], NodeState.SKIPPED)
        self.assertTrue(sched2.is_finished())
        dag2.remove_node("n3")
        self.assertFalse(dag2.has_node("n3"))

    def test_blocked_ancestor_detection_and_seeding(self) -> None:
        sm = DAGEngineLiteStateMachine()
        sm.seed_linear_dag()
        self.assertIn("n1", sm.state.nodes)
        # Test blocked_by_failure branch where PENDING node has FAILED upstream without mark_failed skipping it
        st_custom = DAGEngineLiteState()
        st_custom.nodes["n1"] = NodeDefinition("n1", ACTION_OK, frozenset(), 0, 0)
        st_custom.nodes["n2"] = NodeDefinition("n2", ACTION_OK, frozenset({"n1"}), 0, 0)
        st_custom.nodes["n3"] = NodeDefinition("n3", ACTION_OK, frozenset({"n2"}), 0, 0)
        st_custom.upstream = {"n1": set(), "n2": {"n1"}, "n3": {"n2"}}
        st_custom.downstream = {"n1": {"n2"}, "n2": {"n3"}, "n3": set()}
        st_custom.scheduler_states = {
            "n1": NodeState.FAILED,
            "n2": NodeState.PENDING,
            "n3": NodeState.PENDING,
        }
        self.assertTrue(compute_is_finished(st_custom))

        dag3, sched3, _ = make_dag_engine_lite_fakes()
        dag3.add_node("n1", ACTION_OK, None, 5, 0)
        dag3.add_node("n2", ACTION_OK, ["n1"], 5, 0)
        self.assertEqual(sched3.get_state("n2"), NodeState.PENDING)
        dag3.remove_node("n1")
        self.assertEqual(sched3.get_state("n2"), NodeState.READY)
        dag3.add_node("n1", ACTION_OK, None, 5, 0)
        dag3.add_edge("n1", "n2")
        self.assertEqual(sched3.get_state("n2"), NodeState.PENDING)

        st_missing_dep = DAGEngineLiteState()
        st_missing_dep.nodes["n2"] = NodeDefinition("n2", ACTION_OK, frozenset({"ghost"}), 0, 0)
        st_missing_dep.upstream = {"n2": {"ghost"}}
        st_missing_dep.downstream = {"ghost": {"n2"}, "n2": set()}
        self.assertFalse(compute_is_finished(st_missing_dep))

        # Test missing dependency & cycle helper branches
        st_bad = DAGEngineLiteState()
        st_bad.nodes["n1"] = NodeDefinition("n1", ACTION_OK, frozenset({"missing"}), 0, 0)
        st_bad.upstream = {"n1": {"missing"}}
        st_bad.downstream = {"missing": {"n1"}, "n1": set()}
        self.assertFalse(all_deps_present(st_bad.nodes, st_bad.upstream))

        st_cyc = DAGEngineLiteState()
        st_cyc.nodes["n1"] = NodeDefinition("n1", ACTION_OK, frozenset({"n2"}), 0, 0)
        st_cyc.nodes["n2"] = NodeDefinition("n2", ACTION_OK, frozenset({"n1"}), 0, 0)
        st_cyc.upstream = {"n1": {"n2"}, "n2": {"n1"}}
        st_cyc.downstream = {"n1": {"n2"}, "n2": {"n1"}}
        self.assertFalse(is_acyclic(st_cyc.nodes, st_cyc.upstream, st_cyc.downstream))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:02:28Z
# LAST_CHANGED: 2026-11-13T22:02:28Z
# CHANGE: Promote unblocked PENDING dependents to READY and demote newly blocked READY dependents in sync_scheduler_states upon DAG mutations
# --- END AUTOFAB METADATA ---
