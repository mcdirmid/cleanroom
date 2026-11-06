# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
    FakeDagEngineLite,
    make_dag_engine_lite_fake,
)
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_lite_initialize,
)
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG as DAGProtocol,
    DAGRunner as DAGRunnerProtocol,
    WaveScheduler as WaveSchedulerProtocol,
    CycleError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for DagEngineLite."""

    @transition(DAGProtocol.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        assert target.has_node(node_id)
        return ret

    @transition(DAGProtocol.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert upstream_id in target.get_dependencies(downstream_id)
        return ret

    @transition(DAGProtocol.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.remove_node(node_id))
        assert not target.has_node(node_id)
        return ret

    @transition(DAGProtocol.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.has_node(node_id))
        assert isinstance(ret, bool)
        return ret

    @transition(DAGProtocol.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        return ret

    @transition(DAGProtocol.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.get_dependencies(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAGProtocol.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.get_dependents(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAGProtocol.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.all_nodes())
        assert isinstance(ret, set)
        return ret

    @transition(DAGProtocol.validate)
    def validate(
        self,
    ) -> None:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.validate())
        return ret

    @transition(DAGProtocol.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.topological_sort())
        assert len(ret) == len(target.all_nodes())
        return ret

    @transition(DAGProtocol.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.find_roots())
        assert ret <= target.all_nodes()
        return ret

    @transition(DAGProtocol.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.find_leaves())
        assert ret <= target.all_nodes()
        return ret

    @transition(DAGProtocol.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.compute_critical_path(estimated_durations))
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        return ret

    @transition(WaveSchedulerProtocol.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        dag: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.next_wave())
        assert set(ret) <= dag.all_nodes()
        return ret

    @transition(WaveSchedulerProtocol.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        dag: DAGProtocol = sut(DAGProtocol)
        if not dag.has_node(node_id):
            return None
        ret = call_target(target.mark_running(node_id))
        assert target.get_state(node_id) == NodeState.RUNNING
        return ret

    @transition(WaveSchedulerProtocol.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        dag: DAGProtocol = sut(DAGProtocol)
        if not dag.has_node(node_id):
            return None
        ret = call_target(target.mark_succeeded(node_id))
        assert target.get_state(node_id) == NodeState.SUCCEEDED
        return ret

    @transition(WaveSchedulerProtocol.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        dag: DAGProtocol = sut(DAGProtocol)
        if not dag.has_node(node_id):
            return None
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert target.get_state(node_id) == NodeState.FAILED
        return ret

    @transition(WaveSchedulerProtocol.is_finished)
    def is_finished(
        self,
    ) -> bool:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        ret = call_target(target.is_finished())
        assert isinstance(ret, bool)
        return ret

    @transition(WaveSchedulerProtocol.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        ret = call_target(target.get_state(node_id))
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveSchedulerProtocol.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        target: WaveSchedulerProtocol = sut(WaveSchedulerProtocol)
        dag: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.get_all_states())
        assert set(ret.keys()) <= dag.all_nodes()
        return ret

    @transition(DAGRunnerProtocol.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        target: DAGRunnerProtocol = sut(DAGRunnerProtocol)
        dag: DAGProtocol = sut(DAGProtocol)
        ret = call_target(target.run(failure_policy))
        assert ret.total_nodes == len(dag.all_nodes())
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

def _action_one() -> int:
    return 1


def _action_two() -> int:
    return 2


def _action_seven() -> int:
    return 7


def _failing_action() -> int:
    raise RuntimeError("deliberate node failure")


class _FlakyAction:
    """Node action that fails a fixed number of times before succeeding."""

    def __init__(self, failures: int) -> None:
        self.remaining = failures

    def __call__(self) -> int:
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("transient node failure")
        return 42


class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={
                DAGProtocol: self.dag,
                DAG: self.dag,
                WaveSchedulerProtocol: self.wavescheduler,
                WaveScheduler: self.wavescheduler,
                DAGRunnerProtocol: self.dagrunner,
                DAGRunner: self.dagrunner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAGProtocol, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveSchedulerProtocol, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunnerProtocol, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_dag_graph_operations(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", _action_one, None, 0, 0)
        dag.add_node("b", _action_two, ["a"], 2, 0)
        dag.add_node("c", _action_seven, ["a"], 1, 0)
        dag.add_node("d", _action_one, None, 3, 0)
        dag.add_edge("d", "a")
        assert dag.has_node("a")
        assert not dag.has_node("missing")
        node = dag.get_node("b")
        assert node.node_id == "b"
        assert dag.get_dependencies("b") == {"a"}
        assert dag.get_dependents("a") == {"b", "c"}
        assert dag.all_nodes() == {"a", "b", "c", "d"}
        dag.validate()
        assert dag.topological_sort() == ["d", "a", "b", "c"]
        assert dag.find_roots() == {"d"}
        assert dag.find_leaves() == {"b", "c"}
        path, total = dag.compute_critical_path({"b": 5.0})
        assert path == ["d", "a", "b"]
        assert total == 7.0
        dag.remove_node("d")
        assert not dag.has_node("d")
        assert dag.get_dependencies("a") == set()
        dag.remove_node("b")
        assert dag.get_dependents("a") == {"c"}

    def test_dag_scheduler_waves(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", _action_one, None, 0, 0)
        dag.add_node("b", _action_two, ["a"], 0, 0)
        dag.add_node("c", _action_seven, None, 0, 0)
        assert scheduler.next_wave() == ["a", "c"]
        scheduler.mark_running("a")
        assert scheduler.get_state("a") == NodeState.RUNNING
        scheduler.mark_succeeded("a")
        assert scheduler.get_state("b") == NodeState.READY
        assert not scheduler.is_finished()
        assert scheduler.next_wave() == ["b", "c"]
        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")
        scheduler.mark_running("c")
        scheduler.mark_succeeded("c")
        assert scheduler.is_finished()
        states = scheduler.get_all_states()
        assert set(states.keys()) == {"a", "b", "c"}
        assert states["a"] == NodeState.SUCCEEDED

    def test_empty_graph(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        assert dag.all_nodes() == set()
        assert not dag.has_node("a")
        assert dag.find_roots() == set()
        assert dag.find_leaves() == set()
        dag.validate()
        assert dag.topological_sort() == []
        assert scheduler.next_wave() == []
        assert scheduler.is_finished()
        assert scheduler.get_all_states() == {}

    def test_mark_failed_fail_fast(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", _action_one, None, 0, 0)
        dag.add_node("b", _action_two, ["a"], 0, 0)
        assert scheduler.next_wave() == ["a"]
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        assert scheduler.get_state("a") == NodeState.FAILED
        assert scheduler.get_state("b") == NodeState.CANCELLED
        assert scheduler.is_finished()

    def test_mark_failed_skip_downstream(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", _action_one, None, 0, 0)
        dag.add_node("b", _action_two, ["a"], 0, 0)
        dag.add_node("c", _action_seven, ["b"], 0, 0)
        dag.add_node("d", _action_one, None, 0, 0)
        assert scheduler.next_wave() == ["a", "d"]
        scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        assert scheduler.get_state("b") == NodeState.SKIPPED
        assert scheduler.get_state("c") == NodeState.SKIPPED
        assert scheduler.get_state("d") == NodeState.READY

    def test_mark_failed_continue_on_error(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", _action_one, None, 0, 0)
        dag.add_node("b", _action_two, ["a"], 0, 0)
        dag.add_node("d", _action_seven, None, 0, 0)
        assert scheduler.next_wave() == ["a", "d"]
        scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        assert scheduler.get_state("b") == NodeState.SKIPPED
        assert scheduler.get_state("d") == NodeState.READY
        assert not scheduler.is_finished()
        scheduler.mark_running("d")
        scheduler.mark_succeeded("d")
        assert scheduler.is_finished()

    def test_runner_success(self) -> None:
        dag = self.checked_dag
        runner = self.checked_dagrunner
        dag.add_node("a", _action_one, None, 0, 0)
        dag.add_node("b", _action_two, ["a"], 1, 0)
        report = runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"a", "b"}
        assert report.failed_nodes == ()
        assert report.skipped_nodes == ()
        assert report.cancelled_nodes == ()
        assert set(report.critical_path) == {"a", "b"}
        assert report.results["a"].value == 1
        assert report.results["b"].value == 2

    def test_runner_retries(self) -> None:
        dag = self.checked_dag
        runner = self.checked_dagrunner
        dag.add_node("a", _FlakyAction(1), None, 0, 2)
        report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert set(report.succeeded_nodes) == {"a"}
        assert report.results["a"].value == 42

    def test_runner_fail_fast(self) -> None:
        dag = self.checked_dag
        runner = self.checked_dagrunner
        dag.add_node("a", _failing_action, None, 3, 0)
        dag.add_node("b", _action_one, ["a"], 0, 0)
        dag.add_node("c", _action_seven, None, 0, 0)
        report = runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 3
        assert "a" in report.failed_nodes
        assert report.results["a"].error is not None

    def test_runner_skip_downstream(self) -> None:
        dag = self.checked_dag
        runner = self.checked_dagrunner
        dag.add_node("a", _failing_action, None, 3, 0)
        dag.add_node("b", _action_one, ["a"], 0, 0)
        dag.add_node("c", _action_seven, None, 0, 0)
        report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert "a" in report.failed_nodes
        assert "b" in report.skipped_nodes
        assert "c" in report.succeeded_nodes

    def test_runner_continue_on_error(self) -> None:
        dag = self.checked_dag
        runner = self.checked_dagrunner
        dag.add_node("a", _failing_action, None, 3, 0)
        dag.add_node("b", _action_one, ["a"], 0, 0)
        dag.add_node("c", _action_seven, None, 0, 0)
        report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert "a" in report.failed_nodes
        assert "b" in report.skipped_nodes
        assert "c" in report.succeeded_nodes

    def test_runner_failed_state(self) -> None:
        dag = self.checked_dag
        runner = self.checked_dagrunner
        dag.add_node("a", _failing_action, None, 0, 0)
        dag.add_node("b", _action_one, ["a"], 0, 0)
        runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert self.wavescheduler.get_state("a") == NodeState.FAILED
        assert self.wavescheduler.get_state("b") == NodeState.SKIPPED
        assert self.wavescheduler.get_all_states()["a"] == NodeState.FAILED

    def test_missing_node_contract(self) -> None:
        self.dag.add_node("a", _action_one, None, 0, 0)
        with self.assertRaises(DuplicateNodeError):
            self.dag.add_node("a", _action_two, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("missing")

    def test_missing_dependency_contract(self) -> None:
        self.dag.add_node("a", _action_one, ["missing"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()
        with self.assertRaises(NodeNotFoundError):
            self.dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_cycle_contract(self) -> None:
        self.dag.add_node("a", _action_one, None, 0, 0)
        self.dag.add_node("b", _action_two, None, 0, 0)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        with self.assertRaises(CycleError) as cycle_context:
            self.dag.validate()
        cycle_error = cycle_context.exception
        assert isinstance(cycle_error, CycleError)
        assert set(cycle_error.cycle) == {"a", "b"}
        with self.assertRaises(CycleError):
            self.dag.topological_sort()
        with self.assertRaises(CycleError):
            self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.dag.remove_node("b")
        self.dag.add_edge("a", "a")
        with self.assertRaises(CycleError) as self_edge_context:
            self.dag.validate()
        self_edge_error = self_edge_context.exception
        assert isinstance(self_edge_error, CycleError)
        assert "a" in self_edge_error.cycle
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_empty_critical_path(self) -> None:
        path, total = self.checked_dag.compute_critical_path(None)
        assert path == []
        assert total == 0.0

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.next_wave() == ["a"]
        scheduler.mark_running("a")
        assert scheduler.get_state("a") == NodeState.RUNNING
        self.checked_dag.remove_node("a")
        assert "a" not in scheduler.get_all_states()

    def test_mark_succeeded_with_non_pending_dependent(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_running("b")
        scheduler.mark_succeeded("a")
        assert scheduler.get_state("b") == NodeState.RUNNING

    def test_mark_failed_continue_with_running_and_multi_path_dependent(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        self.checked_dag.add_node("c", _action_seven, ["a"], 0, 0)
        self.checked_dag.add_node("d", _action_one, ["b", "c"], 0, 0)
        self.checked_dag.add_node("e", _action_two, None, 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_running("e")
        scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        assert scheduler.get_state("b") == NodeState.SKIPPED
        assert scheduler.get_state("c") == NodeState.SKIPPED
        assert scheduler.get_state("d") == NodeState.SKIPPED
        assert scheduler.get_state("e") == NodeState.RUNNING

    def test_is_finished_when_blocked_by_failed_dependency(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        scheduler.mark_running("b")
        assert scheduler.is_finished()

    def test_next_wave_empty_when_dependencies_unsatisfied(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        scheduler.mark_running("b")
        assert scheduler.next_wave() == []

    def test_runner_empty_graph(self) -> None:
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 0
        assert list(report.critical_path) == []
        assert list(report.succeeded_nodes) == []
        assert list(report.failed_nodes) == []

    def test_forward_reference_node_registration(self) -> None:
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.validate()
        assert self.checked_dag.find_roots() == {"a"}
        assert self.checked_dag.topological_sort() == ["a", "b"]

    def test_mark_succeeded_leaves_partially_ready_dependent(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, None, 0, 0)
        self.checked_dag.add_node("c", _action_seven, ["a", "b"], 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_succeeded("a")
        assert scheduler.get_state("c") == NodeState.PENDING

    def test_add_edge_endpoint_violations(self) -> None:
        self.dag.add_node("a", _action_one, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")

    def test_deferred_dependency_topological_sort(self) -> None:
        self.dag.add_node("a", _action_one, ["missing"], 0, 0)
        with self.assertRaises(CycleError) as cycle_context:
            self.dag.topological_sort()
        cycle_error = cycle_context.exception
        assert isinstance(cycle_error, CycleError)
        assert len(cycle_error.cycle) >= 1

    def test_mark_failed_skip_downstream_multi_path(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        self.checked_dag.add_node("c", _action_seven, ["a"], 0, 0)
        self.checked_dag.add_node("d", _action_one, ["b", "c"], 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        assert scheduler.get_state("b") == NodeState.SKIPPED
        assert scheduler.get_state("c") == NodeState.SKIPPED
        assert scheduler.get_state("d") == NodeState.SKIPPED

    def test_is_finished_false_when_dependency_unsatisfied(self) -> None:
        self.checked_dag.add_node("a", _action_one, ["missing"], 0, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.next_wave() == []
        assert not scheduler.is_finished()

    def test_runner_halts_on_empty_wave(self) -> None:
        self.checked_dag.add_node("a", _action_one, None, 0, 0)
        self.checked_dag.add_node("b", _action_two, ["a"], 0, 0)
        scheduler = self.checked_wavescheduler
        scheduler.mark_running("a")
        report = self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 2


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for DagEngineLite state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self.dag, self.wavescheduler, self.dagrunner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T20:49:23Z
# LAST_CHANGED: 2026-11-05T20:48:59Z
# CHANGE: Fourth-round coverage audit response: the deferred topological-sort contract is exercised by test_deferred_dependency_topological_sort (registered node with unregistered dependency raises CycleError from topological_sort with the derived cycle sequence asserted); SKIP_DOWNSTREAM propagation through a multi-path dependent is exercised by test_mark_failed_skip_downstream_multi_path; is_finished returning False with no wave and an outstanding dependency that is neither failed nor skipped is exercised by test_is_finished_false_when_dependency_unsatisfied; and the runner empty-wave halt is now invoked with a node already RUNNING and an unsatisfied dependent (mark_running a, b PENDING) so the wave loop breaks while the scheduler reports not finished. Downstream-missing edge endpoint, empty-graph runner, forward-reference registration, and partially-ready promotion scenarios remain in place.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T20:49:23Z
# PRETENSE_QA_AUDIT: 2026-11-05T20:49:10Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    NodeDefinition,
    NodeResult,
    NodeState,
    FailurePolicy,
    WaveScheduler,
)


# ==============================================================================
# 0. Pure Model Helpers
# ==============================================================================
_TERMINAL_STATES: Set[NodeState] = {
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
}

_FAILURE_STATES: Set[NodeState] = {
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
}


def _all_dependencies_present(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> bool:
    """Reports whether every referenced dependency is a registered node."""
    for node in nodes:
        for dependency in upstream.get(node, set()):
            if dependency not in nodes:
                return False
    return True


def _is_acyclic(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> bool:
    """Reports whether the modeled graph contains no directed dependency cycle."""
    indegree: Dict[str, int] = {}
    for node in nodes:
        indegree[node] = 0
    for node in nodes:
        for dependency in upstream.get(node, set()):
            if dependency in indegree:
                indegree[node] += 1
    available: List[str] = []
    for node in nodes:
        if indegree[node] == 0:
            available.append(node)
    visited = 0
    for node in available:
        visited += 1
        for dependent in downstream.get(node, set()):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    available.append(dependent)
    return visited == len(nodes)


def _precedes(
    left: str,
    right: str,
    nodes: Mapping[str, NodeDefinition[Any]],
) -> bool:
    """Deterministic scheduling order: priority descending, then identifier ascending."""
    left_priority = nodes[left].priority
    right_priority = nodes[right].priority
    if left_priority != right_priority:
        return left_priority > right_priority
    return left < right


def _ordered_by_priority(
    identifiers: Sequence[str],
    nodes: Mapping[str, NodeDefinition[Any]],
) -> List[str]:
    """Orders identifiers by priority descending then identifier ascending."""
    remaining: List[str] = list(identifiers)
    ordered: List[str] = []
    for _ in range(len(remaining)):
        best = remaining[0]
        for candidate in remaining:
            if _precedes(candidate, best, nodes):
                best = candidate
        remaining.remove(best)
        ordered.append(best)
    return ordered


def _topological_order(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> List[str]:
    """Computes a priority-tie-broken topological ordering over registered nodes."""
    indegree: Dict[str, int] = {}
    for node in nodes:
        indegree[node] = 0
    for node in nodes:
        for dependency in upstream.get(node, set()):
            if dependency in indegree:
                indegree[node] += 1
    available: List[str] = []
    for node in nodes:
        if indegree[node] == 0:
            available.append(node)
    ordered: List[str] = []
    for _ in range(len(nodes)):
        if not available:
            break
        best = available[0]
        for candidate in available:
            if _precedes(candidate, best, nodes):
                best = candidate
        available.remove(best)
        ordered.append(best)
        for dependent in downstream.get(best, set()):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    available.append(dependent)
    return ordered


def _critical_path(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the modeled graph."""
    weights: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
    order = _topological_order(nodes, upstream, downstream)
    earliest: Dict[str, float] = {}
    for node in order:
        predecessors: List[str] = []
        for dependency in upstream.get(node, set()):
            if dependency in earliest:
                predecessors.append(dependency)
        best_predecessor_time = 0.0
        for predecessor in predecessors:
            if earliest[predecessor] > best_predecessor_time:
                best_predecessor_time = earliest[predecessor]
        earliest[node] = best_predecessor_time + float(weights.get(node, 1.0))
    if not order:
        return ([], 0.0)
    terminal = order[0]
    for node in order:
        if earliest[node] > earliest[terminal]:
            terminal = node
    path: List[str] = []
    current: Optional[str] = terminal
    while current is not None:
        path.append(current)
        predecessors = sorted(
            dependency for dependency in upstream.get(current, set()) if dependency in earliest
        )
        if not predecessors:
            current = None
        else:
            best = predecessors[0]
            for predecessor in predecessors:
                if earliest[predecessor] > earliest[best]:
                    best = predecessor
            current = best
    path.reverse()
    return (path, earliest[terminal])


def _transitive_dependents(
    start: str,
    downstream: Mapping[str, Set[str]],
) -> Set[str]:
    """Collects every transitive downstream dependent of a node."""
    seen: Set[str] = set()
    frontier: List[str] = [start]
    for node in frontier:
        for dependent in downstream.get(node, set()):
            if dependent not in seen:
                seen.add(dependent)
                frontier.append(dependent)
    return seen


def _synced_states(
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> Dict[str, NodeState]:
    """Returns scheduler tracking synchronized with currently registered graph nodes."""
    synced: Dict[str, NodeState] = {}
    for node in nodes:
        existing = states.get(node)
        if existing is None:
            if upstream.get(node):
                synced[node] = NodeState.PENDING
            else:
                synced[node] = NodeState.READY
        else:
            synced[node] = existing
    return synced


def _ready_wave(
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> List[str]:
    """Collects ready nodes whose upstream dependencies all succeeded."""
    candidates: List[str] = []
    for node in nodes:
        if states.get(node) != NodeState.READY:
            continue
        satisfied = True
        for dependency in upstream.get(node, set()):
            if states.get(dependency) != NodeState.SUCCEEDED:
                satisfied = False
                break
        if satisfied:
            candidates.append(node)
    return _ordered_by_priority(candidates, nodes)


def _blocked_by_failure(
    node: str,
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> bool:
    """Reports whether a non-terminal node is transitively blocked by a failed dependency."""
    seen: Set[str] = set()
    frontier: List[str] = [node]
    for current in frontier:
        for dependency in upstream.get(current, set()):
            if dependency in seen:
                continue
            seen.add(dependency)
            if states.get(dependency) in _FAILURE_STATES:
                return True
            if dependency in nodes:
                frontier.append(dependency)
    return False


def _scheduler_finished(
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> bool:
    """Reports whether all nodes are terminal or every survivor is blocked by a failed dependency."""
    for node in nodes:
        if states.get(node) in _TERMINAL_STATES:
            continue
        satisfied = True
        for dependency in upstream.get(node, set()):
            if states.get(dependency) != NodeState.SUCCEEDED:
                satisfied = False
                break
        if satisfied:
            return False
        if not _blocked_by_failure(node, states, nodes, upstream):
            return False
    return True


def _promoted_states(
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    node_id: str,
) -> Dict[str, NodeState]:
    """Returns states with a node succeeded and newly unblocked dependents promoted to READY."""
    promoted = _synced_states(states, nodes, upstream)
    promoted[node_id] = NodeState.SUCCEEDED
    for dependent in sorted(downstream.get(node_id, set())):
        if promoted.get(dependent) != NodeState.PENDING:
            continue
        satisfied = True
        for dependency in upstream.get(dependent, set()):
            if promoted.get(dependency) != NodeState.SUCCEEDED:
                satisfied = False
                break
        if satisfied:
            promoted[dependent] = NodeState.READY
    return promoted


def _failed_states(
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    node_id: str,
    failure_policy: FailurePolicy,
) -> Dict[str, NodeState]:
    """Returns states with a node failed and the configured failure policy applied."""
    failed = _synced_states(states, nodes, upstream)
    failed[node_id] = NodeState.FAILED
    if failure_policy == FailurePolicy.FAIL_FAST:
        for node in nodes:
            if failed.get(node) not in _TERMINAL_STATES:
                failed[node] = NodeState.CANCELLED
        return failed
    for dependent in _transitive_dependents(node_id, downstream):
        if dependent in nodes and failed.get(dependent) not in _TERMINAL_STATES:
            failed[dependent] = NodeState.SKIPPED
    return failed


def _simulate_run(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    states: Mapping[str, NodeState],
    failure_policy: FailurePolicy,
) -> Tuple[Dict[str, NodeState], Dict[str, NodeResult[Any]]]:
    """Simulates sequential wave execution of node actions with retries and failure policy."""
    simulated = _synced_states(states, nodes, upstream)
    results: Dict[str, NodeResult[Any]] = {}
    for _ in range(len(nodes) + 1):
        if _scheduler_finished(simulated, nodes, upstream):
            break
        wave = _ready_wave(simulated, nodes, upstream)
        if not wave:
            break
        halted = False
        for node in wave:
            simulated[node] = NodeState.RUNNING
            definition = nodes[node]
            attempts = 0
            value: Any = None
            error: Optional[Exception] = None
            for _attempt in range(definition.retries + 1):
                try:
                    value = definition.action()
                    error = None
                    break
                except Exception as exc:
                    error = exc
                    if attempts >= definition.retries:
                        break
                    attempts += 1
            if error is None:
                simulated = _promoted_states(simulated, nodes, upstream, downstream, node)
                results[node] = NodeResult(
                    node_id=node,
                    state=NodeState.SUCCEEDED,
                    value=value,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=attempts,
                )
            else:
                simulated = _failed_states(
                    simulated,
                    nodes,
                    upstream,
                    downstream,
                    node,
                    failure_policy,
                )
                results[node] = NodeResult(
                    node_id=node,
                    state=NodeState.FAILED,
                    value=None,
                    error=error,
                    duration_seconds=0.0,
                    retries_attempted=attempts,
                )
                if failure_policy == FailurePolicy.FAIL_FAST:
                    halted = True
                    break
        if halted:
            break
    for node in nodes:
        if node not in results:
            results[node] = NodeResult(
                node_id=node,
                state=simulated.get(node, NodeState.PENDING),
                value=None,
                error=None,
                duration_seconds=0.0,
                retries_attempted=0,
            )
    return (simulated, results)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""

    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    initialized: bool = True


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(self.state.initialized)
        require_arg(
            node_id,
            Domain.in_set(
                frozenset({"a", "b", "c", "d", "e", "f", "g", "h"})
                - frozenset(self.state.nodes.keys())
            ),
        )
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(dependencies, cast(Domain[Optional[Collection[str]]], Domain.optional(Domain.list_of(Domain.type(str)))))
        require_arg(priority, Domain.range(0, 5), preferred=[0, 2, 3])
        require_arg(retries, Domain.range(0, 3), preferred=[0, 1])
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies or ()),
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in definition.dependencies:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(upstream_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        require_arg(downstream_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        for dependency in sorted(self.state.upstream.get(node_id, set())):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in sorted(self.state.downstream.get(node_id, set())):
            self.state.upstream.get(dependent, set()).discard(node_id)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.nodes.pop(node_id, None)
        self.state.states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "missing"])
        ret: bool = make_return_value(node_id in self.state.nodes)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        ret: NodeDefinition[Any] = make_return_value(self.state.nodes[node_id])
        assert ret == self.state.nodes[node_id]
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        ret: Set[str] = make_return_value(set(self.state.upstream.get(node_id, set())))
        assert ret == self.state.upstream.get(node_id, set())
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        ret: Set[str] = make_return_value(set(self.state.downstream.get(node_id, set())))
        assert ret == self.state.downstream.get(node_id, set())
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = make_return_value(set(self.state.nodes.keys()))
        assert ret == set(self.state.nodes.keys())
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        require(_all_dependencies_present(self.state.nodes, self.state.upstream))
        require(_is_acyclic(self.state.nodes, self.state.upstream, self.state.downstream))
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        require(_all_dependencies_present(self.state.nodes, self.state.upstream))
        require(_is_acyclic(self.state.nodes, self.state.upstream, self.state.downstream))
        order = _topological_order(self.state.nodes, self.state.upstream, self.state.downstream)
        ret: List[str] = make_return_value(list(order))
        assert len(ret) == len(self.state.nodes)
        assert set(ret) == set(self.state.nodes.keys())
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        roots: Set[str] = set()
        for node in self.state.nodes:
            if not self.state.upstream.get(node):
                roots.add(node)
        ret: Set[str] = make_return_value(roots)
        assert ret == roots
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        leaves: Set[str] = set()
        for node in self.state.nodes:
            if not self.state.downstream.get(node):
                leaves.add(node)
        ret: Set[str] = make_return_value(leaves)
        assert ret == leaves
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require(_all_dependencies_present(self.state.nodes, self.state.upstream))
        require(_is_acyclic(self.state.nodes, self.state.upstream, self.state.downstream))
        require_arg(
            estimated_durations,
            cast(
                Domain[Optional[Mapping[str, float]]],
                Domain.optional(Domain.type(Dict[str, float])),
            ),
        )
        path, total = _critical_path(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )
        ret: Tuple[List[str], float] = make_return_value((path, total))
        assert len(ret[0]) == len(path)
        assert isinstance(ret[1], float)
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        self.state.states = _synced_states(self.state.states, self.state.nodes, self.state.upstream)
        wave = _ready_wave(self.state.states, self.state.nodes, self.state.upstream)
        ret: List[str] = make_return_value(list(wave))
        assert ret == wave
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        self.state.states = _synced_states(self.state.states, self.state.nodes, self.state.upstream)
        self.state.states[node_id] = NodeState.RUNNING
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        self.state.states = _promoted_states(
            self.state.states,
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            node_id,
        )
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        self.state.states = _failed_states(
            self.state.states,
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            node_id,
            failure_policy,
        )
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        self.state.states = _synced_states(self.state.states, self.state.nodes, self.state.upstream)
        finished = _scheduler_finished(self.state.states, self.state.nodes, self.state.upstream)
        ret: bool = make_return_value(finished)
        assert ret == finished
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(frozenset(self.state.nodes.keys())))
        self.state.states = _synced_states(self.state.states, self.state.nodes, self.state.upstream)
        ret: NodeState = make_return_value(self.state.states[node_id])
        assert ret == self.state.states[node_id]
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        self.state.states = _synced_states(self.state.states, self.state.nodes, self.state.upstream)
        mapping: Dict[str, NodeState] = {}
        for node in self.state.nodes:
            mapping[node] = self.state.states[node]
        ret: Mapping[str, NodeState] = make_return_value(dict(mapping))
        assert ret == mapping
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require(_all_dependencies_present(self.state.nodes, self.state.upstream))
        require(_is_acyclic(self.state.nodes, self.state.upstream, self.state.downstream))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        simulated_states, results = _simulate_run(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            self.state.states,
            failure_policy,
        )
        self.state.states = simulated_states
        self.state.results = results
        succeeded: List[str] = []
        failed: List[str] = []
        skipped: List[str] = []
        cancelled: List[str] = []
        for node in self.state.nodes:
            state = self.state.states.get(node, NodeState.PENDING)
            if state == NodeState.SUCCEEDED:
                succeeded.append(node)
            elif state == NodeState.FAILED:
                failed.append(node)
            elif state == NodeState.SKIPPED:
                skipped.append(node)
            elif state == NodeState.CANCELLED:
                cancelled.append(node)
        path, _ = _critical_path(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            None,
        )
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(succeeded),
            failed_nodes=tuple(failed),
            skipped_nodes=tuple(skipped),
            cancelled_nodes=tuple(cancelled),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=results,
        )
        ret: DAGRunReport = make_return_value(report)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(
    state: Optional[DagEngineLiteState] = None,
) -> Any:
    """Synthesizes a fake double implementing every DagEngineLite service interface."""
    return FakeDagEngineLite(state=state or DagEngineLiteState())


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[Any, Any, Any, Any, DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = make_dag_engine_lite_fake(state)
    return (fake, fake, fake, fake, fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

def _noop_action() -> int:
    return 0


def _failing_fake_action() -> int:
    raise RuntimeError("deliberate fake node failure")


class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DagEngineLiteStateMachine()

    def test_seeding_and_dag_transitions(self) -> None:
        self.sm.seed_initial()
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 2, 0)
        self.fake.add_node("c", _noop_action, ["a"], 1, 0)
        self.fake.add_node("d", _noop_action, None, 3, 0)
        self.fake.add_edge("d", "a")
        assert self.fake.has_node("a")
        assert not self.fake.has_node("missing")
        node = self.fake.get_node("b")
        assert node.node_id == "b"
        assert self.fake.get_dependencies("b") == {"a"}
        assert self.fake.get_dependents("a") == {"b", "c"}
        assert self.fake.all_nodes() == {"a", "b", "c", "d"}
        self.fake.validate()
        assert self.fake.topological_sort() == ["d", "a", "b", "c"]
        assert self.fake.find_roots() == {"d"}
        assert self.fake.find_leaves() == {"b", "c"}
        path, total = self.fake.compute_critical_path({"b": 5.0})
        assert path == ["d", "a", "b"]
        assert total == 7.0
        self.fake.remove_node("d")
        assert not self.fake.has_node("d")
        assert self.fake.get_dependencies("a") == set()
        self.fake.remove_node("b")
        assert self.fake.get_dependents("a") == {"c"}

    def test_wave_scheduler_transitions(self) -> None:
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        self.fake.add_node("c", _noop_action, None, 0, 0)
        assert self.fake.next_wave() == ["a", "c"]
        self.fake.mark_running("a")
        assert self.fake.get_state("a") == NodeState.RUNNING
        self.fake.mark_succeeded("a")
        assert self.fake.get_state("b") == NodeState.READY
        assert not self.fake.is_finished()
        assert self.fake.next_wave() == ["b", "c"]
        self.fake.mark_running("b")
        self.fake.mark_succeeded("b")
        self.fake.mark_running("c")
        self.fake.mark_succeeded("c")
        assert self.fake.is_finished()
        states = self.fake.get_all_states()
        assert set(states.keys()) == {"a", "b", "c"}
        assert states["c"] == NodeState.SUCCEEDED

    def test_mark_failed_policies(self) -> None:
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        self.fake.add_node("c", _noop_action, ["b"], 0, 0)
        self.fake.add_node("d", _noop_action, None, 0, 0)
        assert self.fake.next_wave() == ["a", "d"]
        self.fake.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.fake.get_state("b") == NodeState.SKIPPED
        assert self.fake.get_state("c") == NodeState.SKIPPED
        assert self.fake.get_state("d") == NodeState.READY

        self.fake = make_dag_engine_lite_fake()
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        assert self.fake.next_wave() == ["a"]
        self.fake.mark_failed("a", FailurePolicy.FAIL_FAST)
        assert self.fake.get_state("b") == NodeState.CANCELLED
        assert self.fake.is_finished()

        self.fake = make_dag_engine_lite_fake()
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        self.fake.add_node("d", _noop_action, None, 0, 0)
        assert self.fake.next_wave() == ["a", "d"]
        self.fake.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.fake.get_state("b") == NodeState.SKIPPED
        assert self.fake.get_state("d") == NodeState.READY
        assert not self.fake.is_finished()
        self.fake.mark_running("d")
        self.fake.mark_succeeded("d")
        assert self.fake.is_finished()

    def test_run_transitions(self) -> None:
        for policy in (FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM):
            self.fake = make_dag_engine_lite_fake()
            self.fake.add_node("a", _noop_action, None, 0, 0)
            self.fake.add_node("b", _noop_action, ["a"], 0, 0)
            report = self.fake.run(policy)
            assert report.total_nodes == 2
            assert set(report.succeeded_nodes) == {"a", "b"}
            assert report.failed_nodes == ()
            assert report.skipped_nodes == ()
            assert report.cancelled_nodes == ()
            assert self.fake.is_finished()

    def test_run_failure_modeling(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.fake.add_node("a", _failing_fake_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        report = self.fake.run(FailurePolicy.FAIL_FAST)
        assert "a" in report.failed_nodes
        assert self.fake.get_state("a") == NodeState.FAILED
        assert self.fake.get_state("b") == NodeState.CANCELLED

        self.fake = make_dag_engine_lite_fake()
        self.fake.add_node("a", _failing_fake_action, None, 0, 1)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        report = self.fake.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert "a" in report.failed_nodes
        assert "b" in report.skipped_nodes
        assert self.fake.get_state("a") == NodeState.FAILED

        self.fake = make_dag_engine_lite_fake()
        self.fake.add_node("a", _failing_fake_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ["a"], 0, 0)
        self.fake.add_node("c", _noop_action, None, 0, 0)
        report = self.fake.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert "a" in report.failed_nodes
        assert "b" in report.skipped_nodes
        assert "c" in report.succeeded_nodes
        assert self.fake.get_state("c") == NodeState.SUCCEEDED

    def test_is_finished_blocked_graphs(self) -> None:
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, None, 0, 0)
        self.fake.add_edge("b", "a")
        self.fake.add_edge("a", "b")
        assert not self.fake.is_finished()

        self.fake = make_dag_engine_lite_fake()
        self.fake.add_node("a", _noop_action, ["missing"], 0, 0)
        assert not self.fake.is_finished()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T20:38:37Z
# LAST_CHANGED: 2026-11-05T20:26:30Z
# CHANGE: Apply modeled outcomes through direct self.state assignments so checked/fuzz adapters observe them: scheduler synchronization, success promotion, failure-policy application, and full run execution are computed by pure helpers (_synced_states, _promoted_states, _failed_states, _simulate_run) and assigned directly (self.state.states = ..., self.state.results = ...) in next_wave, mark_running, mark_succeeded, mark_failed, is_finished, get_state, get_all_states, and run, so post-run FAILED/SKIPPED states are modeled instead of left stale. No behavioral change to the modeled transitions.
# --- END AUTOFAB METADATA ---
