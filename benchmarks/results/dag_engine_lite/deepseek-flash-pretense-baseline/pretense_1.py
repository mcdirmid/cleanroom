# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_4.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__
from benchmark_4.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
    FakeDagEngineLite,
    make_dag_engine_lite_fakes,
    model_cycle,
    model_first_missing,
)
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import CycleError, FailurePolicy, NodeState


_TERMINAL_STATES = frozenset({
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
})


def _ok_action() -> str:
    return "ok"


def _failing_action() -> str:
    raise RuntimeError("boom")


def _make_flaky_action(failures: int) -> Callable[[], str]:
    calls = {"count": 0}

    def action() -> str:
        calls["count"] += 1
        if calls["count"] <= failures:
            raise RuntimeError("transient failure")
        return "recovered"

    return action


def _transitive_dependents(dag: DAG, node_id: str) -> Set[str]:
    visited: Set[str] = set()
    pending: List[str] = [node_id]
    for current in pending:
        for dependent in sorted(dag.get_dependents(current)):
            if dependent not in visited and dependent != node_id:
                visited.add(dependent)
                pending.append(dependent)
    return visited


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
        expected_dependencies = set(dependencies) if dependencies is not None else set()
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        assert target.has_node(node_id)
        assert expected_dependencies <= target.get_dependencies(node_id)
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        upstream_exists = target.has_node(upstream_id)
        downstream_exists = target.has_node(downstream_id)
        ret: Any = None
        if upstream_exists and downstream_exists:
            ret = call_target(target.add_edge(upstream_id, downstream_id))
            assert upstream_id in target.get_dependencies(downstream_id)
            assert downstream_id in target.get_dependents(upstream_id)
        else:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.add_edge(upstream_id, downstream_id))
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if target.has_node(node_id):
            ret = call_target(target.remove_node(node_id))
            assert not target.has_node(node_id)
        else:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.remove_node(node_id))
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        assert ret == (node_id in target.all_nodes())
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if target.has_node(node_id):
            ret = call_target(target.get_node(node_id))
            assert ret.node_id == node_id
        else:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.get_node(node_id))
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if target.has_node(node_id):
            ret = call_target(target.get_dependencies(node_id))
            assert all(node_id in target.get_dependents(dependency) for dependency in ret if target.has_node(dependency))
        else:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.get_dependencies(node_id))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if target.has_node(node_id):
            ret = call_target(target.get_dependents(node_id))
            assert all(node_id in target.get_dependencies(dependent) for dependent in ret)
        else:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.get_dependents(node_id))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert all(target.has_node(node_id) for node_id in ret)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if model_first_missing(self.state) is not None:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.validate())
        elif model_cycle(self.state):
            with raises(dag_engine_lite.CycleError):
                ret = call_target(target.validate())
        else:
            ret = call_target(target.validate())
            assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if model_first_missing(self.state) is not None:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.topological_sort())
        elif model_cycle(self.state):
            with raises(dag_engine_lite.CycleError):
                ret = call_target(target.topological_sort())
        else:
            ret = call_target(target.topological_sort())
            positions = {node_id: index for index, node_id in enumerate(ret)}
            assert set(ret) == target.all_nodes()
            assert all(
                positions[dependency] < positions[node_id]
                for node_id in ret
                for dependency in target.get_dependencies(node_id)
            )
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        assert all(not target.get_dependencies(node_id) for node_id in ret)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        assert all(not target.get_dependents(node_id) for node_id in ret)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret: Any = None
        if model_first_missing(self.state) is not None:
            with raises(dag_engine_lite.NodeNotFoundError):
                ret = call_target(target.compute_critical_path(estimated_durations))
        elif model_cycle(self.state):
            with raises(dag_engine_lite.CycleError):
                ret = call_target(target.compute_critical_path(estimated_durations))
        else:
            ret = call_target(target.compute_critical_path(estimated_durations))
            path, weight = ret
            assert set(path) <= target.all_nodes()
            assert all(path[index + 1] in target.get_dependents(path[index]) for index in range(len(path) - 1))
            assert weight >= 0.0
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        dag: DAG = sut(DAG)
        ret = call_target(target.next_wave())
        states = target.get_all_states()
        assert all(states.get(node_id) is NodeState.READY for node_id in ret)
        assert all(
            all(states.get(dependency) is NodeState.SUCCEEDED for dependency in dag.get_dependencies(node_id))
            for node_id in ret
        )
        ordering = [(-dag.get_node(node_id).priority, node_id) for node_id in ret]
        assert ordering == sorted(ordering)
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
        dag: DAG = sut(DAG)
        pre_states = target.get_all_states()
        ret = call_target(target.mark_succeeded(node_id))
        assert target.get_state(node_id) is NodeState.SUCCEEDED
        for dependent in dag.get_dependents(node_id):
            if dependent != node_id and pre_states.get(dependent) is NodeState.PENDING:
                promoted = all(
                    dag.has_node(dependency) and target.get_state(dependency) is NodeState.SUCCEEDED
                    for dependency in dag.get_dependencies(dependent)
                )
                assert (target.get_state(dependent) is NodeState.READY) == promoted
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        dag: DAG = sut(DAG)
        pre_states = target.get_all_states()
        dependents = _transitive_dependents(dag, node_id)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert target.get_state(node_id) is NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            assert all(state in _TERMINAL_STATES for state in target.get_all_states().values())
        else:
            assert all(
                target.get_state(dependent) is NodeState.SKIPPED
                for dependent in dependents
                if pre_states.get(dependent) not in _TERMINAL_STATES
            )
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        dag: DAG = sut(DAG)
        ret = call_target(target.is_finished())
        states = target.get_all_states()
        ready = [
            node_id
            for node_id, state in states.items()
            if state is NodeState.READY
            and all(states.get(dependency) is NodeState.SUCCEEDED for dependency in dag.get_dependencies(node_id))
        ]
        assert isinstance(ret, bool)
        if ret:
            assert not states or all(state in _TERMINAL_STATES for state in states.values()) or not ready
        else:
            assert ready
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        assert ret is target.get_all_states()[node_id]
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        dag: DAG = sut(DAG)
        ret = call_target(target.get_all_states())
        assert set(ret) == dag.all_nodes()
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        dag: DAG = sut(DAG)
        scheduler: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.run(failure_policy))
        node_ids = dag.all_nodes()
        states = scheduler.get_all_states()
        reported = (
            set(ret.succeeded_nodes)
            | set(ret.failed_nodes)
            | set(ret.skipped_nodes)
            | set(ret.cancelled_nodes)
        )
        non_terminal = {node_id for node_id, state in states.items() if state not in _TERMINAL_STATES}
        assert ret.total_nodes == len(node_ids)
        assert set(ret.results) <= node_ids
        assert reported | non_terminal == node_ids
        assert all(states[node_id] is NodeState.SUCCEEDED for node_id in ret.succeeded_nodes)
        assert all(states[node_id] is NodeState.FAILED for node_id in ret.failed_nodes)
        assert all(states[node_id] is NodeState.SKIPPED for node_id in ret.skipped_nodes)
        assert all(states[node_id] is NodeState.CANCELLED for node_id in ret.cancelled_nodes)
        assert all(ret.results[node_id].node_id == node_id for node_id in ret.results)
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(singletons={
            DAG: self.dag,
            WaveScheduler: self.wavescheduler,
            DAGRunner: self.dagrunner,
        })
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_node_registration_and_queries(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 4, 0)
        self.checked_dag.add_node("c", _ok_action, ["a", "b"], 2, 1)
        self.checked_dag.add_edge("b", "c")
        self.checked_dag.has_node("a")
        self.checked_dag.has_node("absent")
        self.checked_dag.get_node("c")
        self.checked_dag.get_dependencies("c")
        self.checked_dag.get_dependents("b")
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_scheduler.get_state("a")
        self.checked_scheduler.get_all_states()

    def test_node_error_branches(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.add_edge("absent", "a")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.add_edge("a", "absent")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.remove_node("absent")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.get_node("absent")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.get_dependencies("absent")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.get_dependents("absent")

    def test_remove_node_purges_incident_edges(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, None, 0, 0)
        self.checked_dag.add_node("c", _ok_action, ["b"], 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_scheduler.next_wave()
        self.checked_dag.remove_node("b")
        self.checked_scheduler.get_all_states()
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()

    def test_validate_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["ghost"], 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.validate()
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.topological_sort()
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.checked_dag.compute_critical_path(None)

    def test_validate_cycle(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        with self.assertRaises(dag_engine_lite.CycleError):
            self.checked_dag.validate()
        with self.assertRaises(dag_engine_lite.CycleError):
            self.checked_dag.topological_sort()
        with self.assertRaises(dag_engine_lite.CycleError):
            self.checked_dag.compute_critical_path(None)

    def test_topological_order_tie_breaking(self) -> None:
        self.checked_dag.add_node("z", _ok_action, None, 1, 0)
        self.checked_dag.add_node("y", _ok_action, None, 2, 0)
        self.checked_dag.add_node("x", _ok_action, None, 2, 0)
        self.checked_dag.add_node("w", _ok_action, ["x", "y"], 5, 0)
        self.checked_dag.add_node("v", _ok_action, ["z"], 0, 0)
        self.checked_dag.validate()
        self.checked_dag.topological_sort()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()

    def test_compute_critical_path(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("d", _ok_action, ["b", "c"], 0, 0)
        self.checked_dag.compute_critical_path(None)
        self.checked_dag.compute_critical_path({"a": 3.0, "b": 1.0, "c": 2.0, "d": 2.0})
        self.checked_dag.topological_sort()

    def test_empty_graph(self) -> None:
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.validate()
        self.checked_dag.topological_sort()
        self.checked_dag.compute_critical_path(None)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()
        self.checked_scheduler.get_all_states()
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_next_wave_and_success_transitions(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, None, 0, 0)
        self.checked_dag.add_node("d", _ok_action, ["a", "c"], 3, 0)
        self.checked_dag.add_edge("a", "c")
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_succeeded("a")
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_succeeded("c")
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_state("b")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_mark_failed_fail_fast(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_mark_failed_skip_downstream(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 2, 0)
        self.checked_dag.add_node("c", _ok_action, ["a"], 1, 0)
        self.checked_dag.add_node("d", _ok_action, ["b", "c"], 0, 0)
        self.checked_scheduler.mark_succeeded("a")
        self.checked_scheduler.mark_succeeded("b")
        self.checked_scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_all_states()

    def test_mark_failed_continue_on_error(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_state("b")
        self.checked_scheduler.get_state("c")

    def test_run_success(self) -> None:
        self.checked_dag.add_node("a", _ok_action, None, 0, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, ["b"], 0, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_run_fail_fast_halts_wave(self) -> None:
        self.checked_dag.add_node("a", _failing_action, None, 5, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, None, 1, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_run_continue_on_error(self) -> None:
        self.checked_dag.add_node("a", _failing_action, None, 5, 0)
        self.checked_dag.add_node("b", _ok_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", _ok_action, None, 1, 0)
        self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_run_retry_success(self) -> None:
        self.checked_dag.add_node("a", _make_flaky_action(2), None, 0, 3)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_run_retry_exhausted(self) -> None:
        self.checked_dag.add_node("a", _make_flaky_action(5), None, 0, 1)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for DagEngineLite state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
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
# LAST_CLEANED: 2026-11-02T23:53:58Z
# LAST_CHANGED: 2026-11-02T23:53:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 0c6758e7dbf4
# PRETENSE_COVERAGE_AUDIT: 2026-11-02T23:53:58Z
# PRETENSE_QA_AUDIT: 2026-11-02T23:53:58Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

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
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    CycleError,
    WaveScheduler,
    DAGRunner,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_TERMINAL_STATES = frozenset({
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
})


def _null_action() -> None:
    """Neutral fuzzing action for node definitions."""
    return None


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""

    initialized: bool = True
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)


def model_first_missing(state: DagEngineLiteState) -> Optional[str]:
    """Returns the first referenced dependency absent from the model graph."""
    for node_id in sorted(state.upstream):
        for dependency in sorted(state.upstream[node_id]):
            if dependency not in state.nodes:
                return dependency
    return None


def _model_cycle_visit(
    state: DagEngineLiteState,
    node_id: str,
    visiting: Set[str],
    visited: Set[str],
    path: List[str],
) -> Tuple[str, ...]:
    """Depth-first visit used by model_cycle to detect a directed dependency cycle."""
    visiting.add(node_id)
    path.append(node_id)
    for dependency in sorted(state.upstream.get(node_id, set())):
        if dependency in visiting:
            return tuple(path[path.index(dependency):] + [dependency])
        if dependency not in visited:
            found = _model_cycle_visit(state, dependency, visiting, visited, path)
            if found:
                return found
    path.pop()
    visiting.discard(node_id)
    visited.add(node_id)
    return ()


def model_cycle(state: DagEngineLiteState) -> Tuple[str, ...]:
    """Returns a directed cycle sequence in the model graph, or an empty tuple."""
    visiting: Set[str] = set()
    visited: Set[str] = set()
    path: List[str] = []
    for node_id in sorted(state.nodes):
        if node_id not in visited:
            found = _model_cycle_visit(state, node_id, visiting, visited, path)
            if found:
                return found
    return ()


def model_sync(state: DagEngineLiteState) -> None:
    """Discovers registered model nodes and purges removed scheduler state."""
    for node_id in sorted(state.nodes):
        if node_id not in state.states:
            if state.upstream[node_id]:
                state.states[node_id] = NodeState.PENDING
            else:
                state.states[node_id] = NodeState.READY
    for node_id in list(state.states):
        if node_id not in state.nodes:
            del state.states[node_id]


def model_ready_candidates(state: DagEngineLiteState) -> List[str]:
    """Returns READY model nodes whose upstream dependencies are all SUCCEEDED."""
    candidates = [
        node_id
        for node_id, status in state.states.items()
        if status is NodeState.READY
        and all(state.states.get(dependency) is NodeState.SUCCEEDED for dependency in state.upstream[node_id])
    ]
    candidates.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    return candidates


def model_transitive_dependents(state: DagEngineLiteState, node_id: str) -> Set[str]:
    """Returns all transitive downstream dependents of a model node."""
    visited: Set[str] = set()
    pending: List[str] = [node_id]
    for current in pending:
        for dependent in sorted(state.downstream.get(current, set())):
            if dependent not in visited:
                visited.add(dependent)
                pending.append(dependent)
    return visited


def model_topological_order(state: DagEngineLiteState) -> List[str]:
    """Computes a deterministic topological ordering of the model graph."""
    in_degree: Dict[str, int] = {node_id: len(state.upstream[node_id]) for node_id in state.nodes}
    ready: List[str] = [node_id for node_id, degree in in_degree.items() if degree == 0]
    ready.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    order: List[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for dependent in state.downstream.get(node_id, set()):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
        ready.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    return order


def model_critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the model graph."""
    durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
    order = model_topological_order(state)
    if not order:
        return [], 0.0
    earliest: Dict[str, float] = {}
    for node_id in order:
        prerequisite_finishes = [earliest[dependency] for dependency in state.upstream[node_id]]
        earliest[node_id] = (max(prerequisite_finishes) if prerequisite_finishes else 0.0) + durations.get(node_id, 1.0)
    leaves = [node_id for node_id in state.nodes if not state.downstream[node_id]]
    terminal = min(leaves, key=lambda node_id: (-earliest[node_id], node_id))
    path: List[str] = [terminal]
    current = terminal
    while state.upstream[current]:
        current = min(state.upstream[current], key=lambda node_id: (-earliest[node_id], node_id))
        path.append(current)
    path.reverse()
    return path, earliest[terminal]


def model_completed_report(state: DagEngineLiteState) -> DAGRunReport:
    """Builds the report a fully successful model execution produces."""
    node_ids = model_topological_order(state)
    results: Dict[str, NodeResult[Any]] = {
        node_id: NodeResult(node_id=node_id, state=NodeState.SUCCEEDED) for node_id in node_ids
    }
    critical_path, _ = model_critical_path(state, None)
    return DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=tuple(node_ids),
        failed_nodes=(),
        skipped_nodes=(),
        cancelled_nodes=(),
        wall_clock_seconds=0.0,
        critical_path=tuple(critical_path),
        results=results,
    )


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    # -------------------------------------------------------------------------
    # DAG transitions
    # -------------------------------------------------------------------------

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
        require_arg(node_id, Domain.type(str))
        require_arg(action, Domain.any())
        require_arg(
            dependencies,
            cast("Domain[Optional[Collection[str]]]", Domain.optional(Domain.list_of(Domain.type(str), max_size=3))),
        )
        require_arg(priority, Domain.type(int))
        require_arg(retries, Domain.sampled_from([0, 1, 2, 3]))
        frozen_dependencies = frozenset(dependencies) if dependencies is not None else frozenset()
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_dependencies,
            priority=priority,
            retries=retries,
        )
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in frozen_dependencies:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        ret = make_return_value()
        assert ret is None

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(upstream_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        require_arg(downstream_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        if upstream_id not in self.state.nodes or downstream_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
        else:
            self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
            self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
            ret = make_return_value()
            assert ret is None

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
        else:
            for dependency in self.state.upstream.get(node_id, set()):
                self.state.downstream.get(dependency, set()).discard(node_id)
            for dependent in self.state.downstream.get(node_id, set()):
                self.state.upstream.get(dependent, set()).discard(node_id)
            del self.state.nodes[node_id]
            del self.state.upstream[node_id]
            del self.state.downstream[node_id]
            ret = make_return_value()
            assert ret is None

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        ret: bool = make_return_value(node_id in self.state.nodes)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
            return None
        ret: NodeDefinition[Any] = make_return_value(self.state.nodes[node_id])
        assert ret == self.state.nodes[node_id]
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
            return None
        ret: Set[str] = make_return_value(set(self.state.upstream[node_id]))
        assert ret == self.state.upstream[node_id]
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=sorted(self.state.nodes)[:3])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
            return None
        ret: Set[str] = make_return_value(set(self.state.downstream[node_id]))
        assert ret == self.state.downstream[node_id]
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = make_return_value(set(self.state.nodes))
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        missing = model_first_missing(self.state)
        if missing is not None:
            with raises(NodeNotFoundError):
                make_return_value()
        elif model_cycle(self.state):
            with raises(CycleError):
                make_return_value()
        else:
            ret = make_return_value()
            assert ret is None

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        require(self.state.initialized)
        if model_first_missing(self.state) is not None:
            with raises(NodeNotFoundError):
                make_return_value()
            return None
        if model_cycle(self.state):
            with raises(CycleError):
                make_return_value()
            return None
        expected = model_topological_order(self.state)
        ret: List[str] = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        roots = {node_id for node_id in self.state.nodes if not self.state.upstream[node_id]}
        ret: Set[str] = make_return_value(roots)
        assert ret == roots
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        leaves = {node_id for node_id in self.state.nodes if not self.state.downstream[node_id]}
        ret: Set[str] = make_return_value(leaves)
        assert ret == leaves
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        require(self.state.initialized)
        require_arg(
            estimated_durations,
            cast(
                "Domain[Optional[Mapping[str, float]]]",
                Domain.optional(Domain.mapping_of(Domain.type(str), Domain.sampled_from([1.0, 2.0, 3.0]))),
            ),
        )
        if model_first_missing(self.state) is not None:
            with raises(NodeNotFoundError):
                make_return_value()
            return None
        if model_cycle(self.state):
            with raises(CycleError):
                make_return_value()
            return None
        expected_path, expected_weight = model_critical_path(self.state, estimated_durations)
        ret: Tuple[List[str], float] = make_return_value((expected_path, expected_weight))
        assert ret[0] == expected_path
        assert abs(ret[1] - expected_weight) < 1e-9
        return ret

    # -------------------------------------------------------------------------
    # WaveScheduler transitions
    # -------------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        model_sync(self.state)
        expected = model_ready_candidates(self.state)
        ret: List[str] = make_return_value(expected)
        assert all(node_id in self.state.nodes for node_id in ret)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=sorted(self.state.nodes)[:3])
        model_sync(self.state)
        self.state.states[node_id] = NodeState.RUNNING
        ret = make_return_value()
        assert ret is None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=sorted(self.state.nodes)[:3])
        model_sync(self.state)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in sorted(self.state.downstream.get(node_id, set())):
            if self.state.states.get(dependent) is NodeState.PENDING and all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream[dependent]
            ):
                self.state.states[dependent] = NodeState.READY
        ret = make_return_value()
        assert ret is None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=sorted(self.state.nodes)[:3])
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        model_sync(self.state)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id in list(self.state.states):
                if self.state.states[other_id] not in _TERMINAL_STATES:
                    self.state.states[other_id] = NodeState.CANCELLED
        else:
            for dependent in model_transitive_dependents(self.state, node_id):
                if self.state.states.get(dependent) not in _TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
        ret = make_return_value()
        assert ret is None

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        model_sync(self.state)
        if not self.state.states:
            ret = make_return_value(True)
            assert ret is True
            return ret
        if all(status in _TERMINAL_STATES for status in self.state.states.values()):
            ret = make_return_value(True)
            assert ret is True
            return ret
        ret = make_return_value(not model_ready_candidates(self.state))
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=sorted(self.state.nodes)[:3])
        model_sync(self.state)
        ret: NodeState = make_return_value(self.state.states[node_id])
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        model_sync(self.state)
        ret: Mapping[str, NodeState] = make_return_value(dict(self.state.states))
        assert set(ret) <= set(self.state.nodes)
        return ret

    # -------------------------------------------------------------------------
    # DAGRunner transitions
    # -------------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        require(self.state.initialized)
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        require(model_first_missing(self.state) is None)
        require(not model_cycle(self.state))
        model_sync(self.state)
        for node_id in model_topological_order(self.state):
            self.state.states[node_id] = NodeState.SUCCEEDED
        expected = model_completed_report(self.state)
        ret: DAGRunReport = make_return_value(expected)
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


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
    return (
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:53:58Z
# LAST_CHANGED: 2026-11-02T23:53:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: bfa9b6b27926
# PRETENSE_COVERAGE_AUDIT: 2026-11-02T23:53:58Z
# PRETENSE_QA_AUDIT: 2026-11-02T23:53:58Z
# --- END AUTOFAB METADATA ---
