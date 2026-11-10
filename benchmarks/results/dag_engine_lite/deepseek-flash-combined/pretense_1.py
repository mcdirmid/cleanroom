# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple
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
from benchmark_3.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
    FakeDagEngineLite,
    make_dag_engine_lite_fakes,
)
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_lite_initialize,
)
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)


# ==============================================================================
# Scenario action fixtures
# ==============================================================================

_attempt_counter: dict[str, int] = {}


def _failing_action() -> int:
    raise RuntimeError("synthetic node failure")


def _flaky_action() -> int:
    _attempt_counter["count"] = _attempt_counter.get("count", 0) + 1
    if _attempt_counter["count"] < 3:
        raise RuntimeError("transient node failure")
    return 7


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for DagEngineLite."""

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        assert target.has_node(node_id)
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert upstream_id in target.get_dependencies(downstream_id)
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        assert not target.has_node(node_id)
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        assert set(ret) == target.all_nodes()
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        assert target.get_state(node_id) is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        assert target.get_state(node_id) is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert target.get_state(node_id) is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

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
        self.sm = DagEngineLiteImplPseudoStateMachine(singletons={DAG: self.dag, WaveScheduler: self.wavescheduler, DAGRunner: self.dagrunner})
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_dag_conformance(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 1, 0)
        self.checked_dag.add_node("node_c", lambda: 3, ["node_a"], 0, 0)
        self.checked_dag.add_node("node_d", lambda: 4, None, 0, 0)
        assert self.checked_dag.has_node("node_a")
        assert not self.checked_dag.has_node("node_missing")
        definition = self.checked_dag.get_node("node_b")
        assert definition.node_id == "node_b"
        assert set(self.checked_dag.get_dependencies("node_b")) == {"node_a"}
        assert set(self.checked_dag.get_dependents("node_a")) == {"node_b", "node_c"}
        assert set(self.checked_dag.all_nodes()) == {"node_a", "node_b", "node_c", "node_d"}
        self.checked_dag.validate()
        order = self.checked_dag.topological_sort()
        assert order == ["node_a", "node_b", "node_c", "node_d"]
        assert set(self.checked_dag.find_roots()) == {"node_a", "node_d"}
        assert set(self.checked_dag.find_leaves()) == {"node_b", "node_c", "node_d"}
        path, total = self.checked_dag.compute_critical_path({"node_a": 1.0, "node_b": 2.0, "node_c": 1.0, "node_d": 0.5})
        assert path == ["node_a", "node_b"]
        assert total == 3.0
        self.checked_dag.add_edge("node_c", "node_d")
        assert set(self.checked_dag.get_dependencies("node_d")) == {"node_c"}
        self.checked_dag.remove_node("node_c")
        assert not self.checked_dag.has_node("node_c")
        assert set(self.checked_dag.all_nodes()) == {"node_a", "node_b", "node_d"}
        self.checked_dag.validate()

    def test_real_scheduler_conformance(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 2, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 1, 0)
        self.checked_dag.add_node("node_c", lambda: 3, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a", "node_c"]
        self.checked_wavescheduler.mark_running("node_a")
        assert self.checked_wavescheduler.get_state("node_a") is NodeState.RUNNING
        self.checked_wavescheduler.mark_succeeded("node_a")
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.READY
        states = self.checked_wavescheduler.get_all_states()
        assert set(states.keys()) == {"node_a", "node_b", "node_c"}
        assert not self.checked_wavescheduler.is_finished()
        assert self.checked_wavescheduler.next_wave() == ["node_b", "node_c"]

    def test_real_scheduler_skip_downstream(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.checked_dag.add_node("node_c", lambda: 3, ["node_b"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a"]
        self.checked_wavescheduler.mark_failed("node_a", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_wavescheduler.get_state("node_a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("node_c") is NodeState.SKIPPED
        assert self.checked_wavescheduler.is_finished()

    def test_real_scheduler_fail_fast(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.checked_dag.add_node("node_c", lambda: 3, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a", "node_c"]
        self.checked_wavescheduler.mark_failed("node_a", FailurePolicy.FAIL_FAST)
        assert self.checked_wavescheduler.get_state("node_a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.CANCELLED
        assert self.checked_wavescheduler.get_state("node_c") is NodeState.CANCELLED
        assert self.checked_wavescheduler.is_finished()

    def test_real_scheduler_continue_on_error(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.checked_dag.add_node("node_c", lambda: 3, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a", "node_c"]
        self.checked_wavescheduler.mark_failed("node_a", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_wavescheduler.get_state("node_a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("node_c") is NodeState.READY
        assert not self.checked_wavescheduler.is_finished()

    def test_real_runner_success(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"node_a", "node_b"}
        assert report.failed_nodes == ()
        assert report.skipped_nodes == ()
        assert report.cancelled_nodes == ()
        assert set(report.results.keys()) == {"node_a", "node_b"}
        assert len(report.critical_path) >= 1

    def test_real_runner_retries(self) -> None:
        _attempt_counter.clear()
        self.checked_dag.add_node("node_a", _flaky_action, None, 0, 2)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert set(report.succeeded_nodes) == {"node_a"}
        assert report.failed_nodes == ()
        assert _attempt_counter["count"] == 3

    def test_real_runner_retries_exhausted(self) -> None:
        _attempt_counter.clear()
        self.checked_dag.add_node("node_a", _failing_action, None, 0, 2)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert set(report.failed_nodes) == {"node_a"}
        assert report.succeeded_nodes == ()

    def test_real_runner_skip_downstream(self) -> None:
        self.checked_dag.add_node("node_a", _failing_action, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.checked_dag.add_node("node_c", lambda: 3, None, 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 3
        assert set(report.failed_nodes) == {"node_a"}
        assert set(report.skipped_nodes) == {"node_b"}
        assert set(report.succeeded_nodes) == {"node_c"}

    def test_real_runner_fail_fast(self) -> None:
        self.checked_dag.add_node("node_a", _failing_action, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, None, 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert set(report.failed_nodes) == {"node_a"}
        assert "node_b" in report.cancelled_nodes

    def test_real_remove_node_updates_scheduler(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a"]
        assert set(self.checked_wavescheduler.get_all_states().keys()) == {
            "node_a",
            "node_b",
        }
        self.checked_dag.remove_node("node_b")
        assert set(self.checked_wavescheduler.get_all_states().keys()) == {"node_a"}
        assert self.checked_wavescheduler.next_wave() == ["node_a"]

    def test_real_late_synchronized_node_becomes_ready(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.checked_wavescheduler.mark_running("node_a")
        self.checked_wavescheduler.mark_succeeded("node_a")
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.READY
        assert self.checked_wavescheduler.next_wave() == ["node_b"]

    def test_real_synchronized_node_completion(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a"]
        self.checked_wavescheduler.mark_succeeded("node_a")
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.READY
        assert self.checked_wavescheduler.next_wave() == ["node_b"]
        self.checked_dag.add_node("node_c", lambda: 3, ["node_a"], 0, 0)
        self.checked_dag.remove_node("node_c")
        self.checked_dag.add_node("node_c", lambda: 4, ["node_a"], 0, 0)
        assert self.checked_wavescheduler.get_state("node_c") is NodeState.READY
        assert self.checked_wavescheduler.next_wave() == ["node_b", "node_c"]

    def test_real_mark_succeeded_preserves_dependents(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a"]
        self.checked_wavescheduler.mark_succeeded("node_a")
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.READY
        self.checked_wavescheduler.mark_succeeded("node_a")
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.READY
        self.checked_wavescheduler.mark_running("node_b")
        self.checked_wavescheduler.mark_succeeded("node_b")
        self.checked_wavescheduler.mark_succeeded("node_a")
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.SUCCEEDED

    def test_real_skip_downstream_diamond(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.checked_dag.add_node("node_c", lambda: 3, ["node_a"], 0, 0)
        self.checked_dag.add_node(
            "node_d", lambda: 4, ["node_b", "node_c"], 0, 0
        )
        assert self.checked_wavescheduler.next_wave() == ["node_a"]
        self.checked_wavescheduler.mark_failed(
            "node_a", FailurePolicy.SKIP_DOWNSTREAM
        )
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("node_c") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("node_d") is NodeState.SKIPPED
        assert self.checked_wavescheduler.is_finished()

    def test_real_empty_dag_is_finished(self) -> None:
        assert self.checked_wavescheduler.is_finished()
        assert self.checked_wavescheduler.next_wave() == []

    def test_real_finished_when_blocked_by_failed_dependency(self) -> None:
        self.checked_dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["node_a"]
        self.checked_wavescheduler.mark_failed(
            "node_a", FailurePolicy.CONTINUE_ON_ERROR
        )
        assert self.checked_wavescheduler.get_state("node_b") is NodeState.SKIPPED
        self.checked_dag.add_node("node_c", lambda: 3, ["node_a"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == []
        assert self.checked_wavescheduler.is_finished()

    def test_real_run_empty_dag(self) -> None:
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 0
        assert list(report.critical_path) == []
        assert len(report.succeeded_nodes) == 0
        assert len(report.failed_nodes) == 0

    def test_real_run_halts_without_ready_nodes(self) -> None:
        self.dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        assert self.wavescheduler.next_wave() == ["node_a"]
        self.wavescheduler.mark_running("node_a")
        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 2
        assert len(report.succeeded_nodes) == 0
        assert len(report.failed_nodes) == 0
        assert not self.wavescheduler.is_finished()

    def test_real_run_with_prior_terminal_state(self) -> None:
        self.dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.dag.add_node("node_b", lambda: 2, ["node_a"], 0, 0)
        self.dag.add_node("node_c", lambda: 3, None, 0, 0)
        assert self.wavescheduler.next_wave() == ["node_a", "node_c"]
        self.wavescheduler.mark_failed("node_a", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.wavescheduler.get_state("node_b") is NodeState.SKIPPED
        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert "node_a" in report.failed_nodes
        assert "node_b" in report.skipped_nodes
        assert self.wavescheduler.get_state("node_c") is NodeState.SUCCEEDED
        assert self.wavescheduler.is_finished()

    def test_real_checked_preconditions(self) -> None:
        self.dag.add_node("node_a", lambda: 1, None, 0, 0)
        with self.assertRaises(DuplicateNodeError):
            self.dag.add_node("node_a", lambda: 2, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("node_a", "node_missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("node_missing", "node_a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("node_missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("node_missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("node_missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("node_missing")
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("node_missing")

    def test_real_validate_missing_dependency(self) -> None:
        self.dag.add_node("node_a", lambda: 1, ["node_missing"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_real_cycle_detection(self) -> None:
        self.dag.add_node("node_a", lambda: 1, None, 0, 0)
        self.dag.add_node("node_b", lambda: 2, None, 0, 0)
        self.dag.add_edge("node_b", "node_a")
        self.dag.add_edge("node_a", "node_b")
        with self.assertRaises(CycleError) as cycle_context:
            self.dag.validate()
        assert "node_a" in cycle_context.exception.cycle
        assert "node_b" in cycle_context.exception.cycle
        with self.assertRaises(CycleError):
            self.dag.topological_sort()


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
        self.__dict__["_services"] = (self.dag, self.wavescheduler, self.dagrunner,)

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
# LAST_CLEANED: 2026-11-05T21:52:18Z
# LAST_CHANGED: 2026-11-05T21:51:55Z
# CHANGE: Extend test_real_synchronized_node_completion to exercise both registration orderings that drive synchronization-time promotion: node_b is registered after node_a already SUCCEEDED and is promoted to READY plus scheduled by the next next_wave query, and node_c is registered, removed before ever acquiring scheduler state, then re-registered after node_a succeeded so the next synchronization again promotes it to READY. The scenario asserts both nodes appear in the next wave, covering the synchronization-time promotion statement without relying on any further success transition.
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T21:52:18Z
# PRETENSE_QA_AUDIT: 2026-11-05T21:52:05Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    NodeState,
    WaveScheduler,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live naturally inside the single
# transition body. require(...) gates model-state preconditions; require_arg(...)
# defines the caller precondition contract (checked at runtime on real calls).


_NODE_ID_UNIVERSE: Tuple[str, ...] = (
    "node_a",
    "node_b",
    "node_c",
    "node_d",
    "node_e",
    "node_f",
)


def _default_candidate_ids() -> Set[str]:
    return set(_NODE_ID_UNIVERSE)


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""

    initialized: bool = True
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    scheduler_states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    candidate_ids: Set[str] = field(default_factory=_default_candidate_ids)
    has_cycle: bool = False
    all_dependencies_known: bool = True


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
        require(self.state.candidate_ids)
        require_arg(node_id, Domain.in_set(self.state.candidate_ids))
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(
            dependencies,
            Domain.type(Optional[Collection[str]]),
            preferred=[None, ["node_a"]],
        )
        require_arg(priority, Domain.type(int), preferred=[0, 1])
        require_arg(retries, Domain.type(int), preferred=[0])
        dependency_set = frozenset(dependencies or ())
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.candidate_ids.discard(node_id)
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        missing_dependency = False
        for known_id in self.state.nodes:
            for dependency in self.state.upstream.get(known_id, set()):
                if dependency not in self.state.nodes:
                    missing_dependency = True
        self.state.all_dependencies_known = not missing_dependency
        degree_map = {
            known_id: len(self.state.upstream.get(known_id, set()))
            for known_id in self.state.nodes
        }
        degree_pool = [
            known_id for known_id, degree in degree_map.items() if degree == 0
        ]
        visited = 0
        for _ in range(len(self.state.nodes)):
            if not degree_pool:
                break
            current_id = degree_pool.pop(0)
            visited += 1
            for dependent in self.state.downstream.get(current_id, set()):
                if dependent in degree_map:
                    degree_map[dependent] -= 1
                    if degree_map[dependent] == 0:
                        degree_pool.append(dependent)
        self.state.has_cycle = (
            self.state.all_dependencies_known
            and visited != len(self.state.nodes)
        )
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert ret is None
        assert self.state.nodes[node_id] is definition
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(upstream_id, Domain.in_set(self.state.nodes.keys()))
        require_arg(downstream_id, Domain.in_set(self.state.nodes.keys()))
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        degree_map = {
            known_id: len(self.state.upstream.get(known_id, set()))
            for known_id in self.state.nodes
        }
        degree_pool = [
            known_id for known_id, degree in degree_map.items() if degree == 0
        ]
        visited = 0
        for _ in range(len(self.state.nodes)):
            if not degree_pool:
                break
            current_id = degree_pool.pop(0)
            visited += 1
            for dependent in self.state.downstream.get(current_id, set()):
                if dependent in degree_map:
                    degree_map[dependent] -= 1
                    if degree_map[dependent] == 0:
                        degree_pool.append(dependent)
        self.state.has_cycle = (
            self.state.all_dependencies_known
            and visited != len(self.state.nodes)
        )
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert ret is None
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        for dependency in set(self.state.upstream.get(node_id, set())):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in set(self.state.downstream.get(node_id, set())):
            self.state.upstream.get(dependent, set()).discard(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.scheduler_states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        self.state.candidate_ids.add(node_id)
        missing_dependency = False
        for known_id in self.state.nodes:
            for dependency in self.state.upstream.get(known_id, set()):
                if dependency not in self.state.nodes:
                    missing_dependency = True
        self.state.all_dependencies_known = not missing_dependency
        degree_map = {
            known_id: len(self.state.upstream.get(known_id, set()))
            for known_id in self.state.nodes
        }
        degree_pool = [
            known_id for known_id, degree in degree_map.items() if degree == 0
        ]
        visited = 0
        for _ in range(len(self.state.nodes)):
            if not degree_pool:
                break
            current_id = degree_pool.pop(0)
            visited += 1
            for dependent in self.state.downstream.get(current_id, set()):
                if dependent in degree_map:
                    degree_map[dependent] -= 1
                    if degree_map[dependent] == 0:
                        degree_pool.append(dependent)
        self.state.has_cycle = (
            self.state.all_dependencies_known
            and visited != len(self.state.nodes)
        )
        ret = self.inner_remove_node(node_id)
        assert ret is None
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["node_a", "node_missing"])
        exists = node_id in self.state.nodes
        ret: bool = self.inner_has_node(node_id)
        assert ret == exists
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        definition = self.state.nodes[node_id]
        ret: NodeDefinition[Any] = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        dependencies = set(self.state.upstream.get(node_id, set()))
        ret: Set[str] = self.inner_get_dependencies(node_id)
        assert ret == dependencies
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        dependents = set(self.state.downstream.get(node_id, set()))
        ret: Set[str] = self.inner_get_dependents(node_id)
        assert ret == dependents
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        node_ids = set(self.state.nodes.keys())
        ret: Set[str] = self.inner_all_nodes()
        assert ret == node_ids
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        require(self.state.all_dependencies_known)
        require(not self.state.has_cycle)
        ret = self.inner_validate()
        assert ret is None
        assert self.state.all_dependencies_known
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        require(self.state.all_dependencies_known)
        require(not self.state.has_cycle)
        in_degree = {
            node_id: len(self.state.upstream.get(node_id, set()))
            for node_id in self.state.nodes
        }
        ready_pool = [node_id for node_id, degree in in_degree.items() if degree == 0]
        ordered: List[str] = []
        for _ in range(len(self.state.nodes)):
            if not ready_pool:
                break
            ranked = [(-self.state.nodes[item].priority, item) for item in ready_pool]
            ranked.sort()
            current = ranked[0][1]
            ready_pool = [item for _, item in ranked[1:]]
            ordered.append(current)
            for dependent in self.state.downstream.get(current, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        ready_pool.append(dependent)
        ret: List[str] = self.inner_topological_sort()
        assert ret == ordered
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        roots = {
            node_id
            for node_id in self.state.nodes
            if not self.state.upstream.get(node_id)
        }
        ret: Set[str] = self.inner_find_roots()
        assert ret == roots
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        leaves = {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        ret: Set[str] = self.inner_find_leaves()
        assert ret == leaves
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require(self.state.all_dependencies_known)
        require(not self.state.has_cycle)
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
            preferred=[None, {"node_a": 2.0}],
        )
        durations: Mapping[str, float] = estimated_durations or {}
        in_degree = {
            node_id: len(self.state.upstream.get(node_id, set()))
            for node_id in self.state.nodes
        }
        ready_pool = [node_id for node_id, degree in in_degree.items() if degree == 0]
        ordered: List[str] = []
        for _ in range(len(self.state.nodes)):
            if not ready_pool:
                break
            ranked = [(-self.state.nodes[item].priority, item) for item in ready_pool]
            ranked.sort()
            current = ranked[0][1]
            ready_pool = [item for _, item in ranked[1:]]
            ordered.append(current)
            for dependent in self.state.downstream.get(current, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        ready_pool.append(dependent)
        earliest: Dict[str, float] = {}
        for node_id in ordered:
            best = 0.0
            for dependency in self.state.upstream.get(node_id, set()):
                if earliest.get(dependency, 0.0) > best:
                    best = earliest[dependency]
            earliest[node_id] = best + float(durations.get(node_id, 1.0))
        end_node = ""
        end_weight = -1.0
        for node_id in ordered:
            if earliest[node_id] >= end_weight:
                end_weight = earliest[node_id]
                end_node = node_id
        path: List[str] = []
        current = end_node
        for _ in range(len(self.state.nodes)):
            if not current:
                break
            path.append(current)
            best_predecessor = ""
            best_weight = -1.0
            for dependency in self.state.upstream.get(current, set()):
                if dependency in earliest and earliest[dependency] >= best_weight:
                    best_weight = earliest[dependency]
                    best_predecessor = dependency
            current = best_predecessor
        path.reverse()
        total = earliest[end_node] if end_node else 0.0
        ret: Tuple[List[str], float] = self.inner_compute_critical_path(estimated_durations)
        assert len(ret[0]) == len(path)
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(node_id, set())
                ):
                    self.state.scheduler_states[node_id] = NodeState.READY
                else:
                    self.state.scheduler_states[node_id] = NodeState.PENDING
        ready: List[str] = []
        for node_id, node_state in self.state.scheduler_states.items():
            if node_id not in self.state.nodes:
                continue
            if node_state is not NodeState.READY:
                continue
            if all(
                self.state.scheduler_states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(node_id, set())
            ):
                ready.append(node_id)
        ranked_ready = [(-self.state.nodes[item].priority, item) for item in ready]
        ranked_ready.sort()
        ready = [item for _, item in ranked_ready]
        ret: List[str] = self.inner_next_wave()
        assert ret == ready
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        for known_id in self.state.nodes:
            if known_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(known_id, set())
                ):
                    self.state.scheduler_states[known_id] = NodeState.READY
                else:
                    self.state.scheduler_states[known_id] = NodeState.PENDING
        self.state.scheduler_states[node_id] = NodeState.RUNNING
        ret = self.inner_mark_running(node_id)
        assert ret is None
        assert self.state.scheduler_states[node_id] is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        for known_id in self.state.nodes:
            if known_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(known_id, set())
                ):
                    self.state.scheduler_states[known_id] = NodeState.READY
                else:
                    self.state.scheduler_states[known_id] = NodeState.PENDING
        self.state.scheduler_states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            if dependent not in self.state.nodes:
                continue
            if self.state.scheduler_states.get(dependent) is not NodeState.PENDING:
                continue
            if all(
                self.state.scheduler_states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(dependent, set())
            ):
                self.state.scheduler_states[dependent] = NodeState.READY
        ret = self.inner_mark_succeeded(node_id)
        assert ret is None
        assert self.state.scheduler_states[node_id] is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[FailurePolicy.SKIP_DOWNSTREAM],
        )
        for known_id in self.state.nodes:
            if known_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(known_id, set())
                ):
                    self.state.scheduler_states[known_id] = NodeState.READY
                else:
                    self.state.scheduler_states[known_id] = NodeState.PENDING
        self.state.scheduler_states[node_id] = NodeState.FAILED
        terminal_states = (
            NodeState.SUCCEEDED,
            NodeState.FAILED,
            NodeState.SKIPPED,
            NodeState.CANCELLED,
        )
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id in self.state.nodes:
                if self.state.scheduler_states.get(other_id) not in terminal_states:
                    self.state.scheduler_states[other_id] = NodeState.CANCELLED
        else:
            blocked = {node_id}
            for _ in range(len(self.state.nodes)):
                expanded = set(blocked)
                for blocked_id in blocked:
                    expanded.update(self.state.downstream.get(blocked_id, set()))
                blocked = expanded
            for dependent in blocked:
                if dependent == node_id:
                    continue
                if dependent not in self.state.nodes:
                    continue
                if self.state.scheduler_states.get(dependent) in terminal_states:
                    continue
                self.state.scheduler_states[dependent] = NodeState.SKIPPED
        ret = self.inner_mark_failed(node_id, failure_policy)
        assert ret is None
        assert self.state.scheduler_states[node_id] is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(node_id, set())
                ):
                    self.state.scheduler_states[node_id] = NodeState.READY
                else:
                    self.state.scheduler_states[node_id] = NodeState.PENDING
        terminal_states = (
            NodeState.SUCCEEDED,
            NodeState.FAILED,
            NodeState.SKIPPED,
            NodeState.CANCELLED,
        )
        finished = True
        for node_id in self.state.nodes:
            node_state = self.state.scheduler_states.get(node_id, NodeState.PENDING)
            if node_state in terminal_states:
                continue
            if node_state is NodeState.READY or node_state is NodeState.RUNNING:
                finished = False
                break
            if all(
                self.state.scheduler_states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(node_id, set())
            ):
                finished = False
                break
        ret: bool = self.inner_is_finished()
        assert ret == finished
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require(self.state.nodes)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        for known_id in self.state.nodes:
            if known_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(known_id, set())
                ):
                    self.state.scheduler_states[known_id] = NodeState.READY
                else:
                    self.state.scheduler_states[known_id] = NodeState.PENDING
        ret: NodeState = self.inner_get_state(node_id)
        assert ret is self.state.scheduler_states[node_id]
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        for known_id in self.state.nodes:
            if known_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(known_id, set())
                ):
                    self.state.scheduler_states[known_id] = NodeState.READY
                else:
                    self.state.scheduler_states[known_id] = NodeState.PENDING
        states = {
            node_id: self.state.scheduler_states[node_id]
            for node_id in self.state.nodes
        }
        ret: Mapping[str, NodeState] = self.inner_get_all_states()
        assert ret == states
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require(self.state.all_dependencies_known)
        require(not self.state.has_cycle)
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[FailurePolicy.CONTINUE_ON_ERROR],
        )
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                if all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(node_id, set())
                ):
                    self.state.scheduler_states[node_id] = NodeState.READY
                else:
                    self.state.scheduler_states[node_id] = NodeState.PENDING
        results: Dict[str, NodeResult[Any]] = {}
        for _ in range(len(self.state.nodes) + 1):
            wave = [
                node_id
                for node_id in self.state.nodes
                if self.state.scheduler_states.get(node_id) is NodeState.READY
                and all(
                    self.state.scheduler_states.get(dependency)
                    is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(node_id, set())
                )
            ]
            if not wave:
                break
            ranked = [(-self.state.nodes[item].priority, item) for item in wave]
            ranked.sort()
            wave = [item for _, item in ranked]
            for node_id in wave:
                self.state.scheduler_states[node_id] = NodeState.RUNNING
                self.state.scheduler_states[node_id] = NodeState.SUCCEEDED
                results[node_id] = NodeResult(
                    node_id=node_id,
                    state=NodeState.SUCCEEDED,
                    value=None,
                    duration_seconds=0.0,
                )
                for dependent in self.state.downstream.get(node_id, set()):
                    if dependent not in self.state.nodes:
                        continue
                    if (
                        self.state.scheduler_states.get(dependent)
                        is not NodeState.PENDING
                    ):
                        continue
                    if all(
                        self.state.scheduler_states.get(dependency)
                        is NodeState.SUCCEEDED
                        for dependency in self.state.upstream.get(dependent, set())
                    ):
                        self.state.scheduler_states[dependent] = NodeState.READY
        for node_id in self.state.nodes:
            if node_id in results:
                continue
            node_state = self.state.scheduler_states.get(node_id)
            if node_state is NodeState.SKIPPED or node_state is NodeState.CANCELLED:
                results[node_id] = NodeResult(node_id=node_id, state=node_state)
        self.state.results = dict(results)
        succeeded_nodes = tuple(
            node_id
            for node_id in self.state.nodes
            if self.state.scheduler_states.get(node_id) is NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            node_id
            for node_id in self.state.nodes
            if self.state.scheduler_states.get(node_id) is NodeState.FAILED
        )
        skipped_nodes = tuple(
            node_id
            for node_id in self.state.nodes
            if self.state.scheduler_states.get(node_id) is NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            node_id
            for node_id in self.state.nodes
            if self.state.scheduler_states.get(node_id) is NodeState.CANCELLED
        )
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=0.0,
            critical_path=(),
            results=results,
        )
        ret: DAGRunReport = self.inner_run(failure_policy)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True
        self.state.candidate_ids = set(_NODE_ID_UNIVERSE)


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[FailurePolicy, NodeDefinition, NodeResult, DAGRunReport, DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_dag_engine_lite_fakes()
        self.sm = DagEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.add_node("node_a", lambda: 1, None, 0, 0)
        self.sm.add_node("node_b", lambda: 2, ["node_a"], 1, 0)
        self.sm.add_node("node_c", lambda: 3, None, 0, 0)
        self.sm.add_edge("node_b", "node_c")
        assert self.sm.has_node("node_a")
        assert not self.sm.has_node("node_missing")
        definition = self.sm.get_node("node_a")
        assert definition.node_id == "node_a"
        assert self.sm.get_dependencies("node_b") == {"node_a"}
        assert self.sm.get_dependents("node_a") == {"node_b"}
        assert self.sm.all_nodes() == {"node_a", "node_b", "node_c"}
        self.sm.validate()
        order = self.sm.topological_sort()
        assert order == ["node_a", "node_b", "node_c"]
        assert self.sm.find_roots() == {"node_a"}
        assert self.sm.find_leaves() == {"node_c"}
        path, total = self.sm.compute_critical_path({"node_a": 2.0})
        assert path == ["node_a", "node_b", "node_c"]
        assert total == 4.0
        report = self.sm.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert set(report.succeeded_nodes) == {"node_a", "node_b", "node_c"}
        assert report.failed_nodes == ()
        assert self.sm.get_state("node_c") is NodeState.SUCCEEDED
        states = self.sm.get_all_states()
        assert states["node_b"] is NodeState.SUCCEEDED
        assert self.sm.is_finished()
        self.sm.remove_node("node_c")
        assert not self.sm.has_node("node_c")

        scheduler = DagEngineLiteStateMachine()
        scheduler.seed_initial()
        scheduler.add_node("node_a", lambda: 1, None, 2, 0)
        scheduler.add_node("node_b", lambda: 2, ["node_a"], 1, 0)
        scheduler.add_node("node_c", lambda: 3, None, 0, 0)
        assert scheduler.next_wave() == ["node_a", "node_c"]
        scheduler.mark_running("node_a")
        assert scheduler.get_state("node_a") is NodeState.RUNNING
        scheduler.mark_succeeded("node_a")
        assert scheduler.get_state("node_b") is NodeState.READY
        assert not scheduler.is_finished()
        scheduler.mark_failed("node_b", FailurePolicy.SKIP_DOWNSTREAM)
        assert scheduler.get_state("node_b") is NodeState.FAILED
        assert not scheduler.is_finished()
        scheduler.mark_failed("node_c", FailurePolicy.CONTINUE_ON_ERROR)
        assert scheduler.get_state("node_c") is NodeState.FAILED
        assert scheduler.is_finished()
        scheduler_states = scheduler.get_all_states()
        assert scheduler_states["node_a"] is NodeState.SUCCEEDED


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T21:49:52Z
# LAST_CHANGED: 2026-11-05T21:49:52Z
# CHANGE: Model synchronization-time completion in every scheduler state sync: when a node has no recorded scheduler state, it now becomes READY if all of its registered dependencies are already SUCCEEDED (roots vacuously qualify) and PENDING otherwise. This covers nodes registered or re-registered after their prerequisites have completed becoming eligible on the next synchronization (next_wave/get_state/get_all_states/is_finished/mark_*/run) without requiring a further success transition, and keeps the modeled state aligned with the implementation's scheduler synchronization.
# --- END AUTOFAB METADATA ---
