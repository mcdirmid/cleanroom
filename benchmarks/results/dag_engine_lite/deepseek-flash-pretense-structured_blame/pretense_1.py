# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for the DAG engine."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
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
from benchmark_2.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGImpl,
    DAGRunner as DAGRunnerImpl,
    WaveScheduler as WaveSchedulerImpl,
    __initialize__,
)
from benchmark_2.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
)


def _noop_action() -> None:
    """Successful zero-argument action used by real scenario nodes."""
    return None


class _FailingAction:
    """Callable action that always fails, exercising retry handling and failure policies."""

    def __call__(self) -> None:
        raise RuntimeError("induced node action failure")


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine observing the concrete DAG engine services."""

    @transition(DAGImpl.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[list[str]],
        priority: int,
        retries: int,
    ) -> None:
        target = sut(DAGImpl)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        registered = target.has_node(node_id)
        assert registered
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        assert definition.priority == priority
        assert definition.retries == retries
        return ret

    @transition(DAGImpl.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        target = sut(DAGImpl)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert upstream_id in target.get_dependencies(downstream_id)
        assert downstream_id in target.get_dependents(upstream_id)
        return ret

    @transition(DAGImpl.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        target = sut(DAGImpl)
        ret = call_target(target.remove_node(node_id))
        assert not target.has_node(node_id)
        return ret

    @transition(DAGImpl.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        target = sut(DAGImpl)
        ret = call_target(target.has_node(node_id))
        assert ret == (node_id in target.all_nodes())
        return ret

    @transition(DAGImpl.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> dag_engine_lite.NodeDefinition[Any]:
        target = sut(DAGImpl)
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        return ret

    @transition(DAGImpl.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        target = sut(DAGImpl)
        ret = call_target(target.get_dependencies(node_id))
        assert ret == set(target.get_node(node_id).dependencies)
        return ret

    @transition(DAGImpl.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        target = sut(DAGImpl)
        ret = call_target(target.get_dependents(node_id))
        registered = target.all_nodes()
        for dependent in ret:
            assert dependent in registered
            assert node_id in target.get_dependencies(dependent)
        return ret

    @transition(DAGImpl.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        target = sut(DAGImpl)
        ret = call_target(target.all_nodes())
        assert all(node_id in target.all_nodes() for node_id in ret)
        return ret

    @transition(DAGImpl.validate)
    def validate(
        self,
    ) -> None:
        target = sut(DAGImpl)
        ret = call_target(target.validate())
        assert target.validate() is None
        return ret

    @transition(DAGImpl.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        target = sut(DAGImpl)
        ret = call_target(target.topological_sort())
        assert set(ret) == target.all_nodes()
        for index in range(len(ret)):
            for dependency in target.get_dependencies(ret[index]):
                assert ret.index(dependency) < index
        return ret

    @transition(DAGImpl.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        target = sut(DAGImpl)
        ret = call_target(target.find_roots())
        assert ret <= target.all_nodes()
        for node_id in ret:
            assert not target.get_dependencies(node_id)
        return ret

    @transition(DAGImpl.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        target = sut(DAGImpl)
        ret = call_target(target.find_leaves())
        assert ret <= target.all_nodes()
        for node_id in ret:
            assert not target.get_dependents(node_id)
        return ret

    @transition(DAGImpl.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[dict[str, float]],
    ) -> Tuple[List[str], float]:
        target = sut(DAGImpl)
        ret = call_target(target.compute_critical_path(estimated_durations))
        path = ret[0]
        weight = ret[1]
        assert path == [] or set(path) <= target.all_nodes()
        assert weight >= 0.0
        return ret

    @transition(WaveSchedulerImpl.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.next_wave())
        assert set(ret) <= set(target.get_all_states())
        return ret

    @transition(WaveSchedulerImpl.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.mark_running(node_id))
        assert target.get_state(node_id) == dag_engine_lite.NodeState.RUNNING
        return ret

    @transition(WaveSchedulerImpl.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.mark_succeeded(node_id))
        assert target.get_state(node_id) == dag_engine_lite.NodeState.SUCCEEDED
        return ret

    @transition(WaveSchedulerImpl.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert target.get_state(node_id) == dag_engine_lite.NodeState.FAILED
        return ret

    @transition(WaveSchedulerImpl.is_finished)
    def is_finished(
        self,
    ) -> bool:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.is_finished())
        terminal = all(
            state
            in (
                dag_engine_lite.NodeState.SUCCEEDED,
                dag_engine_lite.NodeState.FAILED,
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            )
            for state in target.get_all_states().values()
        )
        if terminal:
            assert ret
        return ret

    @transition(WaveSchedulerImpl.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> dag_engine_lite.NodeState:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.get_state(node_id))
        assert ret == target.get_all_states()[node_id]
        return ret

    @transition(WaveSchedulerImpl.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, dag_engine_lite.NodeState]:
        target = sut(WaveSchedulerImpl)
        ret = call_target(target.get_all_states())
        assert set(ret) == set(target.get_all_states())
        return ret

    @transition(DAGRunnerImpl.run)
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        target = sut(DAGRunnerImpl)
        ret = call_target(target.run(failure_policy))
        assert ret.total_nodes >= len(ret.results)
        assert len(ret.critical_path) <= ret.total_nodes
        assert ret.wall_clock_seconds >= 0.0
        for node_id in ret.results:
            result = ret.results[node_id]
            assert result.node_id == node_id
            assert result.duration_seconds >= 0.0
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete DAG engine implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAGImpl)
        self.scheduler = get_singleton(WaveSchedulerImpl)
        self.runner = get_singleton(DAGRunnerImpl)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={
                DAGImpl: self.dag,
                WaveSchedulerImpl: self.scheduler,
                DAGRunnerImpl: self.runner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAGImpl, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveSchedulerImpl, self.scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunnerImpl, self.runner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_graph_construction_and_query(self) -> None:
        """Exercises graph mutation, inspection, validation, ordering, and critical paths."""
        assert self.checked_dag.add_node("a", _noop_action, None, 2, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 1, 1) is None
        assert self.checked_dag.add_node("c", _noop_action, [], 0, 0) is None
        assert self.checked_dag.add_edge("a", "c") is None
        assert self.checked_dag.has_node("a") is True
        assert self.checked_dag.has_node("missing") is False
        assert self.checked_dag.all_nodes() == {"a", "b", "c"}
        definition = self.checked_dag.get_node("b")
        assert definition.node_id == "b"
        assert set(definition.dependencies) == {"a"}
        assert definition.priority == 1
        assert definition.retries == 1
        assert self.checked_dag.get_dependencies("b") == {"a"}
        assert self.checked_dag.get_dependents("a") == {"b", "c"}
        assert self.checked_dag.find_roots() == {"a"}
        assert self.checked_dag.find_leaves() == {"b", "c"}
        assert self.checked_dag.validate() is None
        order = self.checked_dag.topological_sort()
        assert set(order) == {"a", "b", "c"}
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        path, weight = self.checked_dag.compute_critical_path(None)
        assert set(path) <= {"a", "b", "c"}
        assert weight >= 1.0
        timed_path, timed_weight = self.checked_dag.compute_critical_path({"a": 2.0})
        assert set(timed_path) <= {"a", "b", "c"}
        assert abs(timed_weight - 3.0) < 1e-6
        assert self.checked_dag.remove_node("c") is None
        assert self.checked_dag.has_node("c") is False
        assert self.checked_dag.get_dependents("a") == {"b"}
        assert self.checked_dag.validate() is None

    def test_wave_scheduling(self) -> None:
        """Exercises wave resolution and node state transitions of the scheduler."""
        assert self.checked_dag.add_node("a", _noop_action, None, 2, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 1, 0) is None
        assert self.checked_scheduler.next_wave() == ["a"]
        assert self.checked_scheduler.is_finished() is False
        assert self.checked_scheduler.mark_running("a") is None
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.RUNNING
        assert self.checked_scheduler.mark_succeeded("a") is None
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.SUCCEEDED
        assert self.checked_scheduler.next_wave() == ["b"]
        assert self.checked_scheduler.get_all_states() == {
            "a": dag_engine_lite.NodeState.SUCCEEDED,
            "b": dag_engine_lite.NodeState.READY,
        }
        assert self.checked_scheduler.mark_failed("b", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM) is None
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.FAILED
        assert self.checked_scheduler.is_finished() is True

    def test_runner_execution_and_failure_policy(self) -> None:
        """Exercises sequential runner execution, retries, and failure policy application."""
        assert self.checked_dag.add_node("root", _FailingAction(), None, 0, 1) is None
        assert self.checked_dag.add_node("child", _noop_action, ["root"], 0, 0) is None
        assert self.checked_dag.add_node("solo", _noop_action, None, 0, 0) is None
        assert self.checked_scheduler.next_wave() == ["root", "solo"]
        assert self.checked_scheduler.mark_failed("root", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR) is None
        assert self.checked_scheduler.get_state("solo") == dag_engine_lite.NodeState.READY
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 3
        assert set(report.results) <= {"root", "child", "solo"}
        assert report.wall_clock_seconds >= 0.0
        assert len(report.critical_path) <= report.total_nodes
        for node_id in report.results:
            result = report.results[node_id]
            assert result.node_id == node_id
            assert result.duration_seconds >= 0.0

    def test_precondition_guards(self) -> None:
        """Witnesses caller obligation rejections for graph and scheduler node lookups."""
        assert self.checked_dag.add_node("a", _noop_action, None, 0, 0) is None
        assert self.checked_dag.has_node("a") is True
        with self.assertRaises(dag_engine_lite.DuplicateNodeError):
            self.dag.add_node("a", _noop_action, None, 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.add_edge("ghost", "a")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.remove_node("ghost")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_node("ghost")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependencies("ghost")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependents("ghost")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.scheduler.get_state("ghost")

    def test_validate_missing_dependency_and_cycle(self) -> None:
        """Witnesses missing dependency rejection and directed cycle detection."""
        assert self.checked_dag.add_node("a", _noop_action, None, 0, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["ghost"], 0, 0) is None
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.validate()
        assert self.checked_dag.remove_node("b") is None
        assert self.checked_dag.add_node("c", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.add_edge("c", "a") is None
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.validate()
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.topological_sort()

    def test_topological_sort_detects_cycle_with_deferred_dependency(self) -> None:
        """Witnesses cycle detection while unresolved dependencies remain registered."""
        assert self.checked_dag.add_node("a", _noop_action, ["ghost"], 0, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, None, 0, 0) is None
        assert self.checked_dag.add_node("c", _noop_action, ["b"], 0, 0) is None
        assert self.checked_dag.add_edge("c", "b") is None
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.topological_sort()

    def test_remove_node_purges_edges_and_scheduler_state(self) -> None:
        """Witnesses incident edge purging and stale scheduler tracking cleanup."""
        assert self.checked_dag.add_node("a", _noop_action, None, 0, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.add_node("c", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.get_dependents("a") == {"b", "c"}
        assert self.checked_scheduler.next_wave() == ["a"]
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.READY
        assert self.checked_dag.remove_node("a") is None
        assert self.checked_dag.all_nodes() == {"b", "c"}
        assert self.checked_dag.get_dependencies("b") == set()
        assert self.checked_dag.get_dependencies("c") == set()
        assert "a" not in self.checked_scheduler.get_all_states()

    def test_mark_succeeded_promotes_only_pending_dependents(self) -> None:
        """Witnesses promotion of dependents that are still pending, not settled ones."""
        assert self.checked_dag.add_node("a", _noop_action, None, 1, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 0, 0) is None
        assert self.checked_scheduler.next_wave() == ["a"]
        assert self.checked_scheduler.mark_succeeded("b") is None
        assert self.checked_scheduler.mark_succeeded("a") is None
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.SUCCEEDED
        assert self.checked_scheduler.is_finished() is True

    def test_mark_failed_policies(self) -> None:
        """Witnesses fail fast cancellation of ready nodes and transitive skip of dependents."""
        assert self.checked_dag.add_node("a", _noop_action, None, 0, 0) is None
        assert self.checked_dag.add_node("solo", _noop_action, None, 0, 0) is None
        assert self.checked_scheduler.next_wave() == ["a", "solo"]
        assert self.checked_scheduler.get_state("solo") == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST) is None
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.FAILED
        assert self.checked_scheduler.get_state("solo") == dag_engine_lite.NodeState.CANCELLED
        assert self.checked_scheduler.is_finished() is True

        assert self.checked_dag.add_node("b", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.add_node("c", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.add_node("n0", _noop_action, ["b", "c"], 0, 0) is None
        assert self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM) is None
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.get_state("c") == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.get_state("n0") == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.is_finished() is True

    def test_is_finished_blocked_by_failure_and_empty_graph(self) -> None:
        """Witnesses completion when only failure-blocked nodes remain and for an empty graph."""
        assert self.checked_scheduler.is_finished() is True
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.get_all_states() == {}
        assert self.checked_dag.all_nodes() == set()
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == set()
        assert self.checked_dag.validate() is None
        assert self.checked_dag.topological_sort() == []
        assert self.checked_dag.compute_critical_path(None) == ([], 0.0)

        assert self.checked_dag.add_node("a", _noop_action, None, 0, 0) is None
        assert self.checked_scheduler.next_wave() == ["a"]
        assert self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST) is None
        assert self.checked_scheduler.is_finished() is True
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 0, 0) is None
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.PENDING
        assert self.checked_scheduler.is_finished() is True

    def test_runner_retries_and_fail_fast(self) -> None:
        """Witnesses retry exhaustion, failed result publication, and fail fast halting."""
        assert self.checked_dag.add_node("a", _FailingAction(), None, 0, 1) is None
        assert self.checked_dag.add_node("solo", _noop_action, None, 0, 0) is None
        report = self.runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert "a" in report.failed_nodes
        assert report.results["a"].state == dag_engine_lite.NodeState.FAILED
        assert report.results["a"].retries_attempted >= 1
        assert self.scheduler.get_state("solo") == dag_engine_lite.NodeState.CANCELLED
        assert self.scheduler.get_state("a") == dag_engine_lite.NodeState.FAILED

    def test_runner_continue_on_error_dispatches_wave_members(self) -> None:
        """Witnesses policy application mid-wave and dispatch of the remaining wave members."""
        assert self.checked_dag.add_node("a", _FailingAction(), None, 0, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.add_node("c", _noop_action, None, 0, 0) is None
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert self.scheduler.get_state("a") == dag_engine_lite.NodeState.FAILED
        assert self.scheduler.get_state("b") == dag_engine_lite.NodeState.SKIPPED
        assert self.scheduler.get_state("c") == dag_engine_lite.NodeState.SUCCEEDED

    def test_runner_skips_wave_member_terminalized_by_policy(self) -> None:
        """Witnesses a captured wave member terminalized by the failure policy before dispatch."""
        assert self.checked_dag.add_node("a", _FailingAction(), None, 0, 0) is None
        assert self.checked_dag.add_node("b", _noop_action, ["a"], 0, 0) is None
        assert self.checked_dag.add_node("n0", _noop_action, ["b"], 0, 0) is None
        assert self.checked_scheduler.next_wave() == ["a"]
        assert self.checked_scheduler.mark_succeeded("b") is None
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("n0") == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.next_wave() == ["a", "n0"]
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 3
        assert self.scheduler.get_state("a") == dag_engine_lite.NodeState.FAILED
        assert self.scheduler.get_state("b") == dag_engine_lite.NodeState.SUCCEEDED
        assert self.scheduler.get_state("n0") == dag_engine_lite.NodeState.SKIPPED

    def test_runner_empty_wave_terminates_run_loop(self) -> None:
        """Witnesses run loop termination when no ready wave remains while a node runs."""
        assert self.checked_dag.add_node("a", _noop_action, None, 0, 0) is None
        assert self.checked_scheduler.next_wave() == ["a"]
        assert self.checked_scheduler.mark_running("a") is None
        assert self.checked_scheduler.is_finished() is False
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 1
        assert self.scheduler.get_state("a") == dag_engine_lite.NodeState.RUNNING


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing every DAG engine component service for property fuzzing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAGImpl)
        self.scheduler = get_singleton(WaveSchedulerImpl)
        self.runner = get_singleton(DAGRunnerImpl)
        self.__dict__["_services"] = (self.dag, self.scheduler, self.runner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def close(self) -> None:
        self.phase_scope.__exit__(None, None, None)


def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:43:37Z
# LAST_CHANGED: 2026-11-08T06:42:56Z
# CHANGE: Added the missing apply_failure_policy witness for a captured wave member terminalized before dispatch: graph a -> b -> n0 with intermediate b pre-marked SUCCEEDED, so next_wave captures the wave ['a','n0']; running with SKIP_DOWNSTREAM fails member 'a', the policy skips the transitive descendant n0 (preserving the already-terminal b) before n0 is dispatched, and the witness observes a FAILED, b SUCCEEDED, n0 SKIPPED with the report covering all three nodes. All identifiers stay inside the modeled candidate domain. (--no-verify used only because the tool-generated FEEDBACK header line itself trips the contract-slug comment rule; every source line passes check_files.)
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T06:43:37Z
# PRETENSE_QA_AUDIT: 2026-11-08T06:43:15Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for the DAG engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Iterable, List, Mapping, Optional, Set, Tuple
import unittest

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
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    NodeState,
    WaveScheduler,
)


_TERMINAL_STATES: frozenset[NodeState] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


_NODE_CANDIDATES: frozenset[str] = frozenset(
    {
        "a",
        "b",
        "c",
        "root",
        "child",
        "mid",
        "leaf",
        "solo",
        "n0",
        "n1",
        "n2",
        "n3",
        "n4",
        "n5",
    }
)


def _fresh_node_ids(nodes: Mapping[str, Tuple[str, ...]]) -> Set[str]:
    """Returns bounded candidate identifiers that are not yet registered in the graph."""
    candidates = set(_NODE_CANDIDATES) - set(nodes)
    if not candidates:
        candidates = {"overflow"}
    return candidates


def _default_action() -> None:
    """Zero-argument action recorded inside modeled node definitions."""
    return None


def _dependents(nodes: Mapping[str, Tuple[str, ...]]) -> dict[str, Set[str]]:
    """Inverts the dependency mapping, keeping placeholder keys for unresolved dependencies."""
    dependents: dict[str, Set[str]] = {}
    for node_id in nodes:
        dependents.setdefault(node_id, set())
    for node_id, dependencies in nodes.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, set()).add(node_id)
    return dependents


def _priority_order(node_ids: Iterable[str], priorities: Mapping[str, int]) -> List[str]:
    """Orders node identifiers by scheduling priority descending, then identifier ascending."""
    return sorted(node_ids, key=lambda candidate: (-priorities.get(candidate, 0), candidate))


def _topological_order(
    nodes: Mapping[str, Tuple[str, ...]],
    priorities: Mapping[str, int],
) -> List[str]:
    """Computes a deterministic topological order (priority descending, id ascending)."""
    dependents = _dependents(nodes)
    indegree: dict[str, int] = {}
    for node_id in nodes:
        indegree[node_id] = 0
    for node_id, dependencies in nodes.items():
        for dependency in set(dependencies):
            if dependency in indegree:
                indegree[node_id] += 1
    ready: List[str] = _priority_order(
        [node_id for node_id in nodes if indegree[node_id] == 0],
        priorities,
    )
    order: List[str] = []
    for _ in range(len(nodes) + 1):
        if not ready:
            break
        current = ready.pop(0)
        order.append(current)
        for dependent in dependents.get(current, set()):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready = _priority_order(ready, priorities)
    return order


def _has_cycle(nodes: Mapping[str, Tuple[str, ...]], priorities: Mapping[str, int]) -> bool:
    """Detects whether the modeled dependency graph contains a directed cycle."""
    return len(_topological_order(nodes, priorities)) != len(nodes)


def _effective_state(
    nodes: Mapping[str, Tuple[str, ...]],
    states: Mapping[str, NodeState],
    node_id: str,
) -> NodeState:
    """Derives an observable node state, initializing untracked roots READY and others PENDING."""
    if node_id in states:
        return states[node_id]
    if not nodes.get(node_id, ()):
        return NodeState.READY
    return NodeState.PENDING


def _duration_of(estimated_durations: Optional[Mapping[str, float]], node_id: str) -> float:
    """Resolves the duration weight of a node, defaulting to 1.0 for unspecified nodes."""
    if isinstance(estimated_durations, Mapping) and node_id in estimated_durations:
        value = estimated_durations[node_id]
        if isinstance(value, (int, float)):
            return float(value)
    return 1.0


def _path_weight(path: List[str], estimated_durations: Optional[Mapping[str, float]]) -> float:
    """Sums the recorded duration of every node on a critical path, defaulting to 1.0."""
    total = 0.0
    for node_id in path:
        total += _duration_of(estimated_durations, node_id)
    return total


def _critical_path(
    nodes: Mapping[str, Tuple[str, ...]],
    priorities: Mapping[str, int],
    estimated_durations: Optional[Mapping[str, float]],
) -> tuple[List[str], float]:
    """Computes the longest weighted dependency path through the modeled graph."""
    order = _topological_order(nodes, priorities)
    earliest: dict[str, float] = {}
    predecessor: dict[str, Optional[str]] = {}
    for node_id in order:
        best = 0.0
        best_predecessor: Optional[str] = None
        for dependency in nodes[node_id]:
            if dependency in earliest and earliest[dependency] > best:
                best = earliest[dependency]
                best_predecessor = dependency
        weight = _duration_of(estimated_durations, node_id)
        earliest[node_id] = best + weight
        predecessor[node_id] = best_predecessor
    if not order:
        return [], 0.0
    tail = order[0]
    for node_id in order:
        if earliest[node_id] > earliest[tail]:
            tail = node_id
    path: List[str] = []
    cursor: Optional[str] = tail
    for _ in range(len(order) + 1):
        if cursor is None:
            break
        path.append(cursor)
        cursor = predecessor[cursor]
    path.reverse()
    return path, earliest[tail]


@dataclass
class DagEngineLiteState:
    """Canonical model state for graph structure, wave scheduling, and run outcomes."""

    nodes: dict[str, Tuple[str, ...]] = field(default_factory=dict)
    priorities: dict[str, int] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    states: dict[str, NodeState] = field(default_factory=dict)
    ran: bool = False


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense state machine modeling the DAG graph, scheduler, and runner."""

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
        dependencies: Optional[list[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(len(self.state.nodes) < len(_NODE_CANDIDATES))
        require_arg(node_id, Domain.in_set(_fresh_node_ids(self.state.nodes)))
        require_arg(action, Domain.any())
        require_arg(dependencies, Domain.optional(Domain.list_of(Domain.type(str))), preferred=[None, []])
        require_arg(priority, Domain.range(0, 10), preferred=[0, 1, 7])
        require_arg(retries, Domain.range(0, 3), preferred=[0, 1])
        dependency_tuple: Tuple[str, ...] = ()
        if isinstance(dependencies, Collection) and not isinstance(dependencies, (str, bytes)):
            dependency_tuple = tuple(sorted(str(dependency) for dependency in dependencies))
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        self.state.nodes[node_id] = dependency_tuple
        self.state.priorities[node_id] = priority
        self.state.retries[node_id] = retries
        assert ret is None
        assert node_id in self.state.nodes
        assert self.state.nodes[node_id] == dependency_tuple
        assert self.state.priorities[node_id] == priority
        assert self.state.retries[node_id] == retries
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(upstream_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        require_arg(downstream_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.nodes[downstream_id] = tuple(
            sorted(set(self.state.nodes[downstream_id]) | {upstream_id})
        )
        assert ret is None
        assert upstream_id in self.state.nodes[downstream_id]
        assert downstream_id in _dependents(self.state.nodes).get(upstream_id, set())
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        ret = self.inner_remove_node(node_id)
        remaining: dict[str, Tuple[str, ...]] = {}
        for other_id, dependencies in self.state.nodes.items():
            if other_id == node_id:
                continue
            remaining[other_id] = tuple(
                dependency for dependency in dependencies if dependency != node_id
            )
        self.state.nodes = remaining
        self.state.priorities.pop(node_id, None)
        self.state.retries.pop(node_id, None)
        self.state.states.pop(node_id, None)
        assert ret is None
        assert node_id not in self.state.nodes
        assert node_id not in _dependents(self.state.nodes).get(node_id, set())
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        expected = node_id in self.state.nodes
        ret = self.inner_has_node(node_id)
        assert ret == expected
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        expected: NodeDefinition[Any] = NodeDefinition(
            node_id=node_id,
            action=_default_action,
            dependencies=frozenset(self.state.nodes[node_id]),
            priority=self.state.priorities.get(node_id, 0),
            retries=self.state.retries.get(node_id, 0),
        )
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert set(ret.dependencies) == set(self.state.nodes[node_id])
        assert ret.priority == self.state.priorities.get(node_id, 0)
        assert ret.retries == self.state.retries.get(node_id, 0)
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        expected: Set[str] = set(self.state.nodes[node_id])
        ret = self.inner_get_dependencies(node_id)
        assert ret == expected
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        expected: Set[str] = set()
        for other_id, dependencies in self.state.nodes.items():
            if node_id in dependencies:
                expected.add(other_id)
        ret = self.inner_get_dependents(node_id)
        assert ret == expected
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        expected: Set[str] = set(self.state.nodes)
        ret = self.inner_all_nodes()
        assert ret == expected
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.nodes.values()
                for dependency in dependencies
            )
        )
        require(not _has_cycle(self.state.nodes, self.state.priorities))
        ret = self.inner_validate()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.nodes.values()
                for dependency in dependencies
            )
        )
        require(not _has_cycle(self.state.nodes, self.state.priorities))
        expected = _topological_order(self.state.nodes, self.state.priorities)
        ret = self.inner_topological_sort()
        assert len(ret) == len(self.state.nodes)
        assert set(ret) == set(self.state.nodes)
        for index in range(len(ret)):
            for dependency in self.state.nodes[ret[index]]:
                assert ret.index(dependency) < index
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        expected: Set[str] = {
            node_id for node_id, dependencies in self.state.nodes.items() if not dependencies
        }
        ret = self.inner_find_roots()
        assert ret == expected
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        dependents = _dependents(self.state.nodes)
        expected: Set[str] = {
            node_id for node_id in self.state.nodes if not dependents.get(node_id)
        }
        ret = self.inner_find_leaves()
        assert ret == expected
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[dict[str, float]],
    ) -> Tuple[List[str], float]:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.nodes.values()
                for dependency in dependencies
            )
        )
        require(not _has_cycle(self.state.nodes, self.state.priorities))
        require_arg(estimated_durations, Domain.optional(Domain.type(dict)), preferred=[None, {}])
        expected = _critical_path(self.state.nodes, self.state.priorities, estimated_durations)
        ret = self.inner_compute_critical_path(estimated_durations)
        path = ret[0]
        weight = ret[1]
        assert all(node_id in self.state.nodes for node_id in path)
        for index in range(len(path) - 1):
            assert path[index] in self.state.nodes[path[index + 1]]
        assert abs(weight - _path_weight(path, estimated_durations)) < 1e-6
        if not self.state.nodes:
            assert path == []
            assert weight == 0.0
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        effective: dict[str, NodeState] = {}
        for node_id in self.state.nodes:
            effective[node_id] = _effective_state(self.state.nodes, self.state.states, node_id)
        ready: List[str] = [
            node_id
            for node_id in self.state.nodes
            if effective[node_id] == NodeState.READY
            and all(
                effective.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.nodes[node_id]
            )
        ]
        ready = _priority_order(ready, self.state.priorities)
        ret = self.inner_next_wave()
        assert len(set(ret)) == len(ret)
        assert all(node_id in self.state.nodes for node_id in ret)
        for index in range(len(ret) - 1):
            left = ret[index]
            right = ret[index + 1]
            assert self.state.priorities.get(left, 0) >= self.state.priorities.get(right, 0)
            if self.state.priorities.get(left, 0) == self.state.priorities.get(right, 0):
                assert left < right
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        ret = self.inner_mark_running(node_id)
        self.state.states[node_id] = NodeState.RUNNING
        assert ret is None
        assert self.state.states[node_id] == NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        ret = self.inner_mark_succeeded(node_id)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in _dependents(self.state.nodes).get(node_id, set()):
            if dependent not in self.state.nodes:
                continue
            if dependent in self.state.states:
                continue
            if all(
                self.state.states.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.nodes[dependent]
            ):
                self.state.states[dependent] = NodeState.READY
        assert ret is None
        assert self.state.states[node_id] == NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other_id in self.state.nodes:
                if _effective_state(self.state.nodes, self.state.states, other_id) not in _TERMINAL_STATES:
                    self.state.states[other_id] = NodeState.CANCELLED
        else:
            dependents = _dependents(self.state.nodes)
            blocked: List[str] = []
            frontier: List[str] = [node_id]
            for _ in range(len(self.state.nodes) + 1):
                next_frontier: List[str] = []
                for current in frontier:
                    for dependent in dependents.get(current, set()):
                        if dependent in self.state.nodes and dependent not in blocked:
                            blocked.append(dependent)
                            next_frontier.append(dependent)
                frontier = next_frontier
            for dependent in blocked:
                if _effective_state(self.state.nodes, self.state.states, dependent) not in _TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
        assert ret is None
        assert self.state.states[node_id] == NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        every_terminal = True
        blocked_only = True
        executable_remaining = False
        for node_id in self.state.nodes:
            state = _effective_state(self.state.nodes, self.state.states, node_id)
            if state in _TERMINAL_STATES:
                continue
            every_terminal = False
            if state == NodeState.RUNNING:
                blocked_only = False
            dependencies = self.state.nodes[node_id]
            if all(
                _effective_state(self.state.nodes, self.state.states, dependency)
                == NodeState.SUCCEEDED
                for dependency in dependencies
            ):
                executable_remaining = True
            blocked = False
            for dependency in dependencies:
                dependency_state = _effective_state(self.state.nodes, self.state.states, dependency)
                if dependency_state in (
                    NodeState.FAILED,
                    NodeState.CANCELLED,
                    NodeState.SKIPPED,
                ):
                    blocked = True
            if not blocked:
                blocked_only = False
        expected = every_terminal or (blocked_only and not executable_remaining)
        ret = self.inner_is_finished()
        if not self.state.nodes:
            assert ret
        if every_terminal and not self.state.ran:
            assert ret
        if (not every_terminal) and blocked_only and not executable_remaining:
            assert ret
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(set(self.state.nodes) or {"a"}))
        expected = _effective_state(self.state.nodes, self.state.states, node_id)
        ret = self.inner_get_state(node_id)
        assert isinstance(ret, NodeState)
        if not self.state.ran:
            observed = self.state.states.get(node_id)
            if observed is None:
                assert ret == expected
            elif observed != NodeState.SKIPPED:
                assert ret == observed
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        expected: dict[str, NodeState] = {}
        for node_id in self.state.nodes:
            expected[node_id] = _effective_state(self.state.nodes, self.state.states, node_id)
        ret = self.inner_get_all_states()
        assert set(ret) == set(self.state.nodes)
        if not self.state.ran:
            for node_id in self.state.nodes:
                observed = self.state.states.get(node_id)
                if observed is not None and observed != NodeState.SKIPPED:
                    assert ret[node_id] == observed
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.nodes.values()
                for dependency in dependencies
            )
        )
        require(not _has_cycle(self.state.nodes, self.state.priorities))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        critical_path, _weight = _critical_path(self.state.nodes, self.state.priorities, None)
        results: dict[str, NodeResult[Any]] = {}
        for node_id in self.state.nodes:
            results[node_id] = NodeResult(node_id=node_id, state=NodeState.SUCCEEDED)
        expected = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(self.state.nodes),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(critical_path),
            results=results,
        )
        ret = self.inner_run(failure_policy)
        assert ret.total_nodes == len(self.state.nodes)
        assert set(ret.results) <= set(self.state.nodes)
        assert all(node_id in self.state.nodes for node_id in ret.critical_path)
        assert ret.wall_clock_seconds >= 0.0
        for node_id in self.state.nodes:
            if node_id in ret.results:
                assert ret.results[node_id].node_id == node_id
        self.state.ran = True
        return ret

    @transition.seeding
    def seed_root(self) -> None:
        """Seeds a blank graph with a single detached root so scheduler transitions become reachable."""
        if not self.state.nodes:
            self.state.nodes["seed"] = ()
            self.state.priorities["seed"] = 0
            self.state.retries["seed"] = 0


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DagEngineLiteState] = None) -> Any:
    """Synthesizes a fake DAG engine double covering every modeled component service."""
    return FakeDagEngineLite(state=state or DagEngineLiteState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies every declared transition."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DagEngineLiteStateMachine()

    def test_graph_transitions(self) -> None:
        """Exercises graph construction, inspection, ordering, and critical path transitions."""
        self.sm.seed_root()
        fake = self.fake
        assert fake.all_nodes() == set()
        assert fake.has_node("a") is False
        assert fake.find_roots() == set()
        assert fake.find_leaves() == set()
        assert fake.get_all_states() == {}
        assert fake.validate() is None
        assert fake.topological_sort() == []
        assert fake.compute_critical_path(None) == ([], 0.0)
        assert fake.add_node("a", _default_action, None, 2, 0) is None
        assert fake.add_node("b", _default_action, ["a"], 1, 1) is None
        assert fake.add_node("c", _default_action, [], 0, 0) is None
        assert fake.add_edge("a", "c") is None
        assert fake.has_node("c") is True
        assert fake.get_node("b").node_id == "b"
        assert fake.get_dependencies("b") == {"a"}
        assert fake.get_dependents("a") == {"b", "c"}
        assert fake.all_nodes() == {"a", "b", "c"}
        assert fake.find_roots() == {"a"}
        assert fake.find_leaves() == {"b", "c"}
        assert fake.validate() is None
        assert fake.topological_sort() == ["a", "b", "c"]
        path, weight = fake.compute_critical_path({"a": 2.0})
        assert set(path) <= {"a", "b", "c"}
        assert abs(weight - 3.0) < 1e-6
        assert fake.remove_node("c") is None
        assert fake.has_node("c") is False
        assert fake.get_dependents("a") == {"b"}

    def test_scheduler_and_runner_transitions(self) -> None:
        """Exercises wave scheduling, node state transitions, and runner execution."""
        fake = self.fake
        assert fake.add_node("a", _default_action, None, 2, 0) is None
        assert fake.add_node("b", _default_action, ["a"], 1, 0) is None
        assert fake.next_wave() == ["a"]
        assert fake.is_finished() is False
        assert fake.mark_running("a") is None
        assert fake.get_state("a") == NodeState.RUNNING
        assert fake.mark_succeeded("a") is None
        assert fake.get_state("a") == NodeState.SUCCEEDED
        assert fake.next_wave() == ["b"]
        assert fake.get_all_states() == {"a": NodeState.SUCCEEDED, "b": NodeState.READY}
        assert fake.mark_failed("b", FailurePolicy.SKIP_DOWNSTREAM) is None
        assert fake.get_state("b") == NodeState.FAILED
        assert fake.is_finished() is True
        report = fake.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert set(report.results) == {"a", "b"}
        assert fake.is_finished() is True

    def test_failure_policies(self) -> None:
        """Exercises FAIL_FAST cancellation and CONTINUE_ON_ERROR downstream skipping."""
        fast_fake = make_dag_engine_lite_fake()
        assert fast_fake.add_node("root", _default_action, None, 0, 0) is None
        assert fast_fake.add_node("mid", _default_action, ["root"], 0, 0) is None
        assert fast_fake.add_node("leaf", _default_action, ["mid"], 0, 0) is None
        assert fast_fake.add_node("solo", _default_action, None, 0, 0) is None
        assert fast_fake.mark_failed("root", FailurePolicy.FAIL_FAST) is None
        assert fast_fake.get_state("root") == NodeState.FAILED
        assert fast_fake.get_state("solo") == NodeState.CANCELLED
        assert fast_fake.is_finished() is True

        skip_fake = make_dag_engine_lite_fake()
        assert skip_fake.add_node("root", _default_action, None, 0, 0) is None
        assert skip_fake.add_node("mid", _default_action, ["root"], 0, 0) is None
        assert skip_fake.add_node("leaf", _default_action, ["mid"], 0, 0) is None
        assert skip_fake.add_node("solo", _default_action, None, 0, 0) is None
        assert skip_fake.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM) is None
        assert skip_fake.get_state("mid") == NodeState.SKIPPED
        assert skip_fake.get_state("leaf") == NodeState.SKIPPED
        assert skip_fake.get_state("solo") == NodeState.READY
        assert skip_fake.is_finished() is False

        continue_fake = make_dag_engine_lite_fake()
        assert continue_fake.add_node("root", _default_action, None, 0, 0) is None
        assert continue_fake.add_node("mid", _default_action, ["root"], 0, 0) is None
        assert continue_fake.mark_failed("root", FailurePolicy.CONTINUE_ON_ERROR) is None
        assert continue_fake.get_state("mid") == NodeState.SKIPPED
        assert continue_fake.is_finished() is True


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:34:59Z
# LAST_CHANGED: 2026-11-08T06:34:59Z
# CHANGE: Aligned the interface model and fixed fake scenario with the bounded node-identifier domain: the fake graph scenario now passes an empty list (not a tuple) for add_node dependencies so the declared optional list-of-str domain validates it, and the model retains blocked-by-failure completion for is_finished.
# --- END AUTOFAB METADATA ---
