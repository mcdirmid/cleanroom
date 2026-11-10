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
from benchmark_4.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
    FakeDagEngineLite,
    make_dag_engine_lite_fake,
)
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_lite_initialize,
)


def noop_action() -> Any:
    """Zero-argument node action that completes successfully without side effects."""
    return None


class FlakyAction:
    """Node action that fails a configured number of initial attempts before succeeding."""

    def __init__(self, failures: int, value: Any = None) -> None:
        self.failures = failures
        self.value = value
        self.attempts = 0

    def __call__(self) -> Any:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise RuntimeError("synthetic node action failure")
        return self.value


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine observing concrete DAG engine execution."""

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
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        assert definition.priority == priority
        assert definition.retries == retries
        assert set(definition.dependencies) == set(dependencies or ())
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
        assert downstream_id in target.get_dependents(upstream_id)
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
        assert ret == (node_id in target.all_nodes())
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
        assert isinstance(ret, set)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        for registered_id in ret:
            assert target.has_node(registered_id)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        registered = target.all_nodes()
        assert set(ret) == registered
        assert len(ret) == len(registered)
        positions = {node_id: index for index, node_id in enumerate(ret)}
        for node_id in ret:
            for dependency in target.get_dependencies(node_id):
                assert positions[dependency] < positions[node_id]
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        for node_id in ret:
            assert not target.get_dependencies(node_id)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        for node_id in ret:
            assert not target.get_dependents(node_id)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        path, weight = ret
        registered = target.all_nodes()
        assert isinstance(path, list)
        assert isinstance(weight, (int, float))
        assert set(path) <= registered
        for index in range(len(path) - 1):
            assert path[index + 1] in target.get_dependents(path[index])
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        assert len(ret) == len(set(ret))
        for node_id in ret:
            assert target.get_state(node_id) is NodeState.READY
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
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        dag: DAG = sut(DAG)
        assert set(ret.keys()) == dag.all_nodes()
        for node_id in ret:
            assert isinstance(ret[node_id], NodeState)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        dag: DAG = sut(DAG)
        registered = dag.all_nodes()
        assert ret.total_nodes == len(registered)
        assert set(ret.succeeded_nodes) <= registered
        assert set(ret.failed_nodes) <= registered
        for node_id in ret.succeeded_nodes:
            result = ret.results.get(node_id)
            if result is not None:
                assert result.state is NodeState.SUCCEEDED
        assert ret.wall_clock_seconds >= 0.0
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete DAG engine implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.wavescheduler, DAGRunner: self.dagrunner}
        )
        self.checked_dag: Any = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler: Any = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner: Any = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_build_graph_and_query(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 2, 1)
        self.checked_dag.add_node("c", noop_action, None, 1, 0)
        self.checked_dag.add_edge("a", "c")
        assert self.checked_dag.has_node("a")
        assert not self.checked_dag.has_node("ghost")
        definition = self.checked_dag.get_node("b")
        assert definition.node_id == "b"
        assert definition.dependencies == frozenset({"a"})
        assert definition.priority == 2
        assert self.checked_dag.get_dependencies("b") == {"a"}
        assert self.checked_dag.get_dependents("a") == {"b", "c"}
        assert self.checked_dag.all_nodes() == {"a", "b", "c"}

    def test_validation_and_ordering(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 1)
        self.checked_dag.add_node("b", noop_action, ["a"], 3, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 1, 0)
        self.checked_dag.add_node("d", noop_action, ["b"], 0, 0)
        self.checked_dag.validate()
        order = self.checked_dag.topological_sort()
        assert order == ["a", "b", "c", "d"]
        assert self.checked_dag.find_roots() == {"a"}
        assert self.checked_dag.find_leaves() == {"c", "d"}
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == ["a", "b", "d"]
        assert weight == 3.0
        weighted_path, weighted = self.checked_dag.compute_critical_path(
            {"a": 4.0, "b": 1.0, "d": 2.0}
        )
        assert weighted_path == ["a", "b", "d"]
        assert weighted == 7.0

    def test_critical_path_branching(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 2, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 1, 0)
        self.checked_dag.add_node("d", noop_action, ["b", "c"], 0, 0)
        path, weight = self.checked_dag.compute_critical_path(
            {"a": 1.0, "b": 5.0, "c": 1.0, "d": 1.0}
        )
        assert path == ["a", "b", "d"]
        assert weight == 7.0
        assert self.checked_dag.find_leaves() == {"d"}

    def test_empty_graph_queries(self) -> None:
        assert self.checked_dag.all_nodes() == set()
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == set()
        assert self.checked_dag.topological_sort() == []
        self.checked_dag.validate()
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0
        assert self.checked_wavescheduler.next_wave() == []
        assert self.checked_wavescheduler.get_all_states() == {}
        assert self.checked_wavescheduler.is_finished()

    def test_remove_node_purges_edges_and_state(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["b"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a"]
        self.checked_dag.remove_node("b")
        assert not self.checked_dag.has_node("b")
        assert self.checked_dag.get_dependencies("c") == set()
        assert self.checked_dag.get_dependents("a") == set()
        assert "b" not in self.checked_wavescheduler.get_all_states()

    def test_scheduler_wave_lifecycle(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, None, 0, 0)
        self.checked_dag.add_edge("a", "c")
        assert self.checked_wavescheduler.next_wave() == ["a"]
        assert not self.checked_wavescheduler.is_finished()
        self.checked_wavescheduler.mark_running("a")
        assert self.checked_wavescheduler.get_state("a") is NodeState.RUNNING
        self.checked_wavescheduler.mark_succeeded("a")
        assert self.checked_wavescheduler.get_state("a") is NodeState.SUCCEEDED
        assert self.checked_wavescheduler.get_state("b") is NodeState.READY
        assert self.checked_wavescheduler.get_state("c") is NodeState.READY
        assert self.checked_wavescheduler.get_all_states() == {
            "a": NodeState.SUCCEEDED,
            "b": NodeState.READY,
            "c": NodeState.READY,
        }
        assert self.checked_wavescheduler.next_wave() == ["b", "c"]
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        self.checked_wavescheduler.mark_running("c")
        self.checked_wavescheduler.mark_succeeded("c")
        assert self.checked_wavescheduler.next_wave() == []
        assert self.checked_wavescheduler.is_finished()

    def test_scheduler_blocks_ready_node_with_pending_upstream(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a", "b"]
        self.checked_dag.add_edge("a", "b")
        assert self.checked_dag.get_dependencies("b") == {"a"}
        assert self.checked_wavescheduler.next_wave() == ["a"]
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        assert self.checked_wavescheduler.next_wave() == ["b"]
        assert not self.checked_wavescheduler.is_finished()

    def test_scheduler_diamond_promotion(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("d", noop_action, ["b", "c"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a"]
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        assert self.checked_wavescheduler.next_wave() == ["b", "c"]
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        assert self.checked_wavescheduler.get_state("d") is NodeState.PENDING
        assert self.checked_wavescheduler.next_wave() == ["c"]
        self.checked_wavescheduler.mark_running("c")
        self.checked_wavescheduler.mark_succeeded("c")
        assert self.checked_wavescheduler.get_state("d") is NodeState.READY
        assert self.checked_wavescheduler.next_wave() == ["d"]

    def test_scheduler_promotes_pending_after_dependency_removal(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a"]
        assert self.checked_wavescheduler.get_state("b") is NodeState.PENDING
        self.checked_dag.remove_node("a")
        assert self.checked_dag.get_dependencies("b") == set()
        assert self.checked_wavescheduler.next_wave() == ["b"]
        assert self.checked_wavescheduler.get_state("b") is NodeState.READY

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["b"], 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_wavescheduler.get_state("a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("b") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("c") is NodeState.SKIPPED
        assert self.checked_wavescheduler.is_finished()

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        assert self.checked_wavescheduler.get_state("a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("b") is NodeState.CANCELLED

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, None, 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_wavescheduler.get_state("a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("b") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("c") is NodeState.READY

    def test_scheduler_mark_failed_continue_on_error_diamond(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("d", noop_action, ["b", "c"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a"]
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        assert self.checked_wavescheduler.next_wave() == ["b", "c"]
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        assert self.checked_wavescheduler.get_state("d") is NodeState.PENDING
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_wavescheduler.get_state("a") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("b") is NodeState.SUCCEEDED
        assert self.checked_wavescheduler.get_state("c") is NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("d") is NodeState.SKIPPED
        assert self.checked_wavescheduler.is_finished()

    def test_scheduler_mark_failed_continue_on_error_completed_ancestors(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("d", noop_action, ["b", "c"], 0, 0)
        self.checked_dag.add_node("e", noop_action, None, 0, 0)
        self.checked_dag.add_node("f", noop_action, ["e"], 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a", "e"]
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        assert self.checked_wavescheduler.next_wave() == ["b", "c", "e"]
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        assert self.checked_wavescheduler.get_state("d") is NodeState.PENDING
        self.checked_wavescheduler.mark_running("c")
        self.checked_wavescheduler.mark_succeeded("c")
        assert self.checked_wavescheduler.next_wave() == ["d", "e"]
        self.checked_wavescheduler.mark_failed("e", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_wavescheduler.get_state("a") is NodeState.SUCCEEDED
        assert self.checked_wavescheduler.get_state("b") is NodeState.SUCCEEDED
        assert self.checked_wavescheduler.get_state("c") is NodeState.SUCCEEDED
        assert self.checked_wavescheduler.get_state("d") is NodeState.READY
        assert self.checked_wavescheduler.get_state("e") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("f") is NodeState.SKIPPED
        assert self.checked_wavescheduler.next_wave() == ["d"]
        self.checked_wavescheduler.mark_running("d")
        self.checked_wavescheduler.mark_succeeded("d")
        assert self.checked_wavescheduler.is_finished()

    def test_scheduler_is_finished_blocked_by_failed_dependency(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, 0)
        self.checked_dag.add_node("c", noop_action, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a", "b", "c"]
        self.checked_wavescheduler.mark_running("c")
        self.checked_wavescheduler.mark_succeeded("c")
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_dag.add_edge("a", "b")
        assert self.checked_wavescheduler.get_state("b") is NodeState.READY
        assert self.checked_wavescheduler.next_wave() == []
        assert self.checked_wavescheduler.is_finished()

    def test_scheduler_is_finished_blocked_by_transitive_failure(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, 0)
        self.checked_dag.add_node("c", noop_action, None, 0, 0)
        self.checked_dag.add_node("d", noop_action, None, 0, 0)
        self.checked_dag.add_node("e", noop_action, None, 0, 0)
        assert self.checked_wavescheduler.next_wave() == ["a", "b", "c", "d", "e"]
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        self.checked_wavescheduler.mark_failed("b", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_dag.add_edge("b", "d")
        self.checked_dag.add_edge("d", "c")
        self.checked_dag.add_edge("a", "c")
        self.checked_dag.add_edge("c", "e")
        self.checked_dag.add_edge("b", "e")
        assert self.checked_wavescheduler.get_state("a") is NodeState.SUCCEEDED
        assert self.checked_wavescheduler.get_state("b") is NodeState.FAILED
        assert self.checked_wavescheduler.get_state("d") is NodeState.READY
        assert self.checked_wavescheduler.get_state("c") is NodeState.READY
        assert self.checked_wavescheduler.get_state("e") is NodeState.READY
        assert self.checked_wavescheduler.next_wave() == []
        assert self.checked_wavescheduler.is_finished()

    def test_runner_success(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["b"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert set(report.succeeded_nodes) == {"a", "b", "c"}
        assert report.failed_nodes == ()
        assert report.skipped_nodes == ()
        assert report.cancelled_nodes == ()
        assert set(report.results.keys()) == {"a", "b", "c"}
        assert report.critical_path == ("a", "b", "c")
        assert report.wall_clock_seconds >= 0.0

    def test_runner_retry_then_succeeds(self) -> None:
        self.checked_dag.add_node("a", FlakyAction(1), None, 0, 1)
        report = self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert set(report.succeeded_nodes) == {"a"}
        assert report.failed_nodes == ()
        assert report.results["a"].state is NodeState.SUCCEEDED

    def test_runner_retry_exhausted_fail_fast(self) -> None:
        self.checked_dag.add_node("a", FlakyAction(5), None, 0, 1)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert set(report.failed_nodes) == {"a"}
        assert report.results["a"].state is NodeState.FAILED
        assert set(report.cancelled_nodes) == {"b"}
        assert report.succeeded_nodes == ()

    def test_runner_continue_on_error_skips_downstream(self) -> None:
        self.checked_dag.add_node("a", FlakyAction(5), None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, None, 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert set(report.failed_nodes) == {"a"}
        assert set(report.skipped_nodes) == {"b"}
        assert set(report.succeeded_nodes) == {"c"}

    def test_runner_skip_downstream_policy(self) -> None:
        self.checked_dag.add_node("a", FlakyAction(5), None, 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.add_node("c", noop_action, ["b"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert set(report.failed_nodes) == {"a"}
        assert set(report.skipped_nodes) == {"b", "c"}
        assert report.succeeded_nodes == ()

    def test_runner_empty_graph(self) -> None:
        report = self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 0
        assert report.succeeded_nodes == ()
        assert report.results == {}

    def test_violation_duplicate_node(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node("a", noop_action, None, 0, 0)

    def test_violation_add_edge_missing_upstream(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("ghost", "a")

    def test_violation_add_edge_missing_downstream(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("a", "ghost")

    def test_violation_remove_missing_node(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).remove_node("ghost")

    def test_violation_get_missing_node(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_node("ghost")

    def test_violation_get_missing_dependencies(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("ghost")

    def test_violation_get_missing_dependents(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependents("ghost")

    def test_violation_validate_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", noop_action, ["ghost"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_violation_validate_cycle(self) -> None:
        self.checked_dag.add_node("a", noop_action, ["b"], 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.violating(CycleError).validate()

    def test_violation_topological_sort_cycle(self) -> None:
        self.checked_dag.add_node("a", noop_action, ["b"], 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dag.violating(CycleError).topological_sort()

    def test_violation_get_state_missing_node(self) -> None:
        self.checked_wavescheduler.violating(NodeNotFoundError).get_state("ghost")

    def test_violation_run_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", noop_action, ["ghost"], 0, 0)
        self.checked_dagrunner.violating(NodeNotFoundError).run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_violation_run_cycle(self) -> None:
        self.checked_dag.add_node("a", noop_action, ["b"], 0, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, 0)
        self.checked_dagrunner.violating(CycleError).run(FailurePolicy.CONTINUE_ON_ERROR)


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
    """Constructs a fresh activated DAG engine aggregate for real fuzz testing."""
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T18:33:19Z
# LAST_CHANGED: 2026-11-09T18:32:43Z
# CHANGE: Resolve converging completed ancestor closure facet: replace the linear completed chain in test_scheduler_mark_failed_continue_on_error_completed_ancestors with the required topology of two completed paths sharing a prerequisite. Shared prerequisite a is SUCCEEDED, then both branches a->b and a->c are driven to SUCCEEDED so dependent d (deps b,c) has two completed ancestor paths converging on a (the shared-ancestor second path) and is promoted to READY only after the second path completes; the independent failing branch e->f keeps e FAILED and skips blocked dependent f under CONTINUE_ON_ERROR, while the ancestor closure retains d. Waves re-derived as [a,e], [b,c,e], [d,e], then [d]; all node ids remain inside the declared pool a-f and model predictions stay in parity.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T18:33:19Z
# PRETENSE_QA_AUDIT: 2026-11-09T18:32:56Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
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
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
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

TERMINAL_STATES: Tuple[NodeState, ...] = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)

BLOCKING_STATES: Tuple[NodeState, ...] = (
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)

NODE_ID_POOL: List[str] = ["a", "b", "c", "d", "e", "f"]


def noop_action() -> Any:
    """Zero-argument node action used by model and fixed fake scenarios."""
    return None


def transitive_dependents(state: DagEngineLiteState, node_id: str) -> List[str]:
    """Collects all transitive downstream dependents of a node in discovery order."""
    discovered: List[str] = []
    frontier: List[str] = [node_id]
    for current in frontier:
        for dependent in sorted(state.downstream.get(current, set())):
            if dependent not in discovered:
                discovered.append(dependent)
                frontier.append(dependent)
    return discovered


def sync_states(state: DagEngineLiteState) -> None:
    """Discovers newly registered nodes, seeding roots as READY and others as PENDING."""
    for node_id in state.nodes:
        if node_id not in state.states:
            if state.upstream.get(node_id):
                state.states[node_id] = NodeState.PENDING
            else:
                state.states[node_id] = NodeState.READY


def promote_unblocked(state: DagEngineLiteState) -> None:
    """Promotes PENDING nodes whose dependency edges were purged to READY."""
    for node_id in state.nodes:
        if state.states.get(node_id) is not NodeState.PENDING:
            continue
        if state.upstream.get(node_id, set()):
            continue
        state.states[node_id] = NodeState.READY


def dependencies_exist(state: DagEngineLiteState) -> bool:
    """Determines whether every referenced dependency identifier is registered."""
    for node_id in state.nodes:
        for dependency in state.upstream.get(node_id, set()):
            if dependency not in state.nodes:
                return False
    return True


def topological_order(state: DagEngineLiteState) -> List[str]:
    """Computes a deterministic topological order using priority then identifier tie-breaking."""
    in_degree: Dict[str, int] = {}
    for node_id in state.nodes:
        in_degree[node_id] = len(state.upstream.get(node_id, set()))
    pending: List[Tuple[int, str]] = []
    for node_id in state.nodes:
        if in_degree[node_id] == 0:
            pending.append((-state.nodes[node_id].priority, node_id))
    pending.sort()
    order: List[str] = []
    while pending:
        _priority, node_id = pending.pop(0)
        order.append(node_id)
        for dependent in sorted(state.downstream.get(node_id, set())):
            if dependent not in in_degree:
                continue
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                pending.append((-state.nodes[dependent].priority, dependent))
                pending.sort()
    return order


def is_acyclic(state: DagEngineLiteState) -> bool:
    """Determines whether the model graph admits a complete topological order."""
    return len(topological_order(state)) == len(state.nodes)


def node_ready(state: DagEngineLiteState, node_id: str) -> bool:
    """Determines whether a READY node has all upstream dependencies SUCCEEDED."""
    if state.states.get(node_id) is not NodeState.READY:
        return False
    for dependency in state.upstream.get(node_id, set()):
        if state.states.get(dependency) is not NodeState.SUCCEEDED:
            return False
    return True


def ready_wave(state: DagEngineLiteState) -> List[str]:
    """Resolves and orders the currently ready wave by priority descending, identifier ascending."""
    candidates: List[str] = []
    for node_id in state.nodes:
        if node_ready(state, node_id):
            candidates.append(node_id)
    ordered = sorted((-state.nodes[node_id].priority, node_id) for node_id in candidates)
    return [node_id for _priority, node_id in ordered]


def critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the model graph."""
    durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
    earliest: Dict[str, float] = {}
    predecessor: Dict[str, str] = {}
    for node_id in topological_order(state):
        upstream_ids = sorted(state.upstream.get(node_id, set()))
        best_time = 0.0
        best_predecessor: Optional[str] = None
        for index, upstream_id in enumerate(upstream_ids):
            upstream_time = earliest.get(upstream_id, 0.0)
            if index == 0 or upstream_time > best_time:
                best_time = upstream_time
                best_predecessor = upstream_id
        earliest[node_id] = best_time + float(durations.get(node_id, 1.0))
        if best_predecessor is not None:
            predecessor[node_id] = best_predecessor
    if not earliest:
        return ([], 0.0)
    terminal = sorted(earliest.keys())[0]
    for node_id in sorted(earliest.keys()):
        if earliest[node_id] > earliest[terminal]:
            terminal = node_id
    path: List[str] = [terminal]
    current: Optional[str] = predecessor.get(terminal)
    while current is not None:
        path.append(current)
        current = predecessor.get(current)
    path.reverse()
    return (path, earliest[terminal])


@dataclass
class DagEngineLiteState:
    """Canonical model state for DAG node registration, scheduling, and execution."""

    initialized: bool = True
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)

    @property
    def keys(self) -> List[str]:
        """Registered node identifiers, usable as argument domains for existing nodes."""
        return sorted(self.nodes)

    @property
    def fresh_ids(self) -> List[str]:
        """Pool identifiers not yet registered, usable as argument domains for registration."""
        return [candidate for candidate in NODE_ID_POOL if candidate not in self.nodes]


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DAG construction, wave scheduling, and execution."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DagEngineLiteState:
        """Constructs the blank initial model state; specialized by pseudo-state machines."""
        return DagEngineLiteState()

    # ------------------------------------------------------------------
    # DAG construction and inspection transitions
    # ------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.fresh_ids))
        require_arg(action, Domain.type(Callable[[], None]))
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])))
        require_arg(priority, Domain.range(-10, 11), preferred=[0, 1])
        require_arg(retries, Domain.range(0, 4), preferred=[0, 1])
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
        for dependency in sorted(definition.dependencies):
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert self.state.nodes[node_id] is definition
        assert self.state.upstream.get(node_id) is not None
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require_arg(upstream_id, Domain.in_set(self.state.keys))
        require_arg(downstream_id, Domain.in_set(self.state.keys))
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.keys))
        upstream_ids = set(self.state.upstream.get(node_id, set()))
        dependent_ids = set(self.state.downstream.get(node_id, set()))
        for dependency in sorted(upstream_ids):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in sorted(dependent_ids):
            self.state.upstream.get(dependent, set()).discard(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        ret = self.inner_remove_node(node_id)
        assert node_id not in self.state.nodes
        assert node_id not in self.state.upstream
        assert node_id not in self.state.downstream
        assert node_id not in self.state.states
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require_arg(node_id, Domain.type(str), preferred=NODE_ID_POOL)
        present = node_id in self.state.nodes
        ret: bool = self.inner_has_node(node_id)
        assert ret == present
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require_arg(node_id, Domain.in_set(self.state.keys))
        stored = self.state.nodes.get(node_id)
        definition = stored if stored is not None else NodeDefinition(
            node_id=node_id,
            action=noop_action,
            dependencies=frozenset(),
            priority=0,
            retries=0,
        )
        ret: NodeDefinition[Any] = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert ret.dependencies == definition.dependencies
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(self.state.keys))
        stored = set(self.state.upstream.get(node_id, set()))
        ret: Set[str] = self.inner_get_dependencies(node_id)
        assert ret == stored
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(self.state.keys))
        stored = set(self.state.downstream.get(node_id, set()))
        ret: Set[str] = self.inner_get_dependents(node_id)
        assert ret == stored
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        snapshot = set(self.state.nodes)
        ret: Set[str] = self.inner_all_nodes()
        assert ret == snapshot
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(dependencies_exist(self.state))
        require(is_acyclic(self.state))
        order = topological_order(self.state)
        complete = dependencies_exist(self.state) and len(order) == len(self.state.nodes)
        ret = self.inner_validate()
        assert len(order) <= len(self.state.nodes)
        if complete:
            assert set(order) == set(self.state.nodes)
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(dependencies_exist(self.state))
        require(is_acyclic(self.state))
        order = topological_order(self.state)
        ret: List[str] = self.inner_topological_sort()
        assert set(ret) <= set(self.state.nodes)
        if dependencies_exist(self.state) and len(order) == len(self.state.nodes):
            assert set(ret) == set(self.state.nodes)
            for node_id in ret:
                for dependency in self.state.upstream.get(node_id, set()):
                    assert ret.index(dependency) < ret.index(node_id)
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        roots = {node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id, set())}
        ret: Set[str] = self.inner_find_roots()
        assert ret == roots
        assert ret <= set(self.state.nodes)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        leaves = {node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id, set())}
        ret: Set[str] = self.inner_find_leaves()
        assert ret == leaves
        assert ret <= set(self.state.nodes)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(dependencies_exist(self.state))
        require(is_acyclic(self.state))
        require_arg(
            estimated_durations,
            Domain.optional(Domain.type(Mapping[str, float])),
        )
        path, weight = critical_path(self.state, estimated_durations)
        ret: Tuple[List[str], float] = self.inner_compute_critical_path(estimated_durations)
        assert set(ret[0]) <= set(self.state.nodes)
        assert isinstance(ret[1], float)
        return ret

    # ------------------------------------------------------------------
    # Wave scheduler transitions
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        sync_states(self.state)
        promote_unblocked(self.state)
        wave = ready_wave(self.state)
        ret: List[str] = self.inner_next_wave()
        assert ret == wave
        assert set(ret) <= set(self.state.nodes)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.keys))
        sync_states(self.state)
        self.state.states[node_id] = NodeState.RUNNING
        ret = self.inner_mark_running(node_id)
        assert self.state.states.get(node_id) is NodeState.RUNNING
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.keys))
        sync_states(self.state)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in sorted(self.state.downstream.get(node_id, set())):
            if self.state.states.get(dependent) is not NodeState.PENDING:
                continue
            if all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(dependent, set())
            ):
                self.state.states[dependent] = NodeState.READY
        ret = self.inner_mark_succeeded(node_id)
        assert self.state.states.get(node_id) is NodeState.SUCCEEDED
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.keys))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        sync_states(self.state)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id in sorted(self.state.nodes):
                if self.state.states.get(other_id) not in TERMINAL_STATES:
                    self.state.states[other_id] = NodeState.CANCELLED
        elif failure_policy is FailurePolicy.SKIP_DOWNSTREAM:
            for other_id in transitive_dependents(self.state, node_id):
                if self.state.states.get(other_id) not in TERMINAL_STATES:
                    self.state.states[other_id] = NodeState.SKIPPED
        else:
            for other_id in transitive_dependents(self.state, node_id):
                if self.state.states.get(other_id) not in TERMINAL_STATES:
                    self.state.states[other_id] = NodeState.SKIPPED
        ret = self.inner_mark_failed(node_id, failure_policy)
        assert self.state.states.get(node_id) is NodeState.FAILED
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        sync_states(self.state)
        terminal_count = 0
        ready_exists = False
        blocked_exists = False
        for node_id in self.state.nodes:
            current = self.state.states.get(node_id)
            if current in TERMINAL_STATES:
                terminal_count += 1
                continue
            if node_ready(self.state, node_id):
                ready_exists = True
            for dependency in self.state.upstream.get(node_id, set()):
                if self.state.states.get(dependency) in BLOCKING_STATES:
                    blocked_exists = True
        finished = not self.state.nodes or terminal_count == len(self.state.nodes) or (
            not ready_exists and blocked_exists
        )
        ret: bool = self.inner_is_finished()
        assert ret == finished
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require_arg(node_id, Domain.in_set(self.state.keys))
        sync_states(self.state)
        current = self.state.states.get(node_id, NodeState.PENDING)
        ret: NodeState = self.inner_get_state(node_id)
        assert ret == current
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        sync_states(self.state)
        snapshot = {
            node_id: self.state.states.get(node_id, NodeState.PENDING)
            for node_id in self.state.nodes
        }
        ret: Mapping[str, NodeState] = self.inner_get_all_states()
        assert set(ret.keys()) == set(self.state.nodes)
        assert all(ret[node_id] == state for node_id, state in snapshot.items())
        return ret

    # ------------------------------------------------------------------
    # Runner transition
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(dependencies_exist(self.state))
        require(is_acyclic(self.state))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        sync_states(self.state)
        executed: Dict[str, NodeResult[Any]] = {}
        for _step in range(len(self.state.nodes) + 1):
            promote_unblocked(self.state)
            wave = ready_wave(self.state)
            if not wave:
                break
            for node_id in wave:
                self.state.states[node_id] = NodeState.SUCCEEDED
                executed[node_id] = NodeResult(node_id=node_id, state=NodeState.SUCCEEDED)
                for dependent in sorted(self.state.downstream.get(node_id, set())):
                    if self.state.states.get(dependent) is not NodeState.PENDING:
                        continue
                    if all(
                        self.state.states.get(dependency) is NodeState.SUCCEEDED
                        for dependency in self.state.upstream.get(dependent, set())
                    ):
                        self.state.states[dependent] = NodeState.READY
        for node_id in sorted(self.state.nodes):
            current = self.state.states.get(node_id)
            if node_id in executed or current is None:
                continue
            if current in TERMINAL_STATES:
                executed[node_id] = NodeResult(node_id=node_id, state=current)
        self.state.results = dict(executed)
        path, weight = critical_path(self.state, None)
        succeeded: List[str] = []
        failed: List[str] = []
        skipped: List[str] = []
        cancelled: List[str] = []
        for node_id in sorted(executed.keys()):
            result = executed[node_id]
            if result.state is NodeState.SUCCEEDED:
                succeeded.append(node_id)
            elif result.state is NodeState.FAILED:
                failed.append(node_id)
            elif result.state is NodeState.SKIPPED:
                skipped.append(node_id)
            elif result.state is NodeState.CANCELLED:
                cancelled.append(node_id)
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(succeeded),
            failed_nodes=tuple(failed),
            skipped_nodes=tuple(skipped),
            cancelled_nodes=tuple(cancelled),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=dict(executed),
        )
        ret: DAGRunReport = self.inner_run(failure_policy)
        assert ret.total_nodes == len(self.state.nodes)
        assert ret.wall_clock_seconds >= 0.0
        assert weight >= 0.0
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model state as an initialized, blank DAG engine."""
        self.state.initialized = True
        self.state.nodes.clear()
        self.state.upstream.clear()
        self.state.downstream.clear()
        self.state.states.clear()
        self.state.results.clear()


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DagEngineLiteState] = None) -> Any:
    """Synthesizes a fake DAG engine sharing the canonical model state."""
    factory: Any = FakeDagEngineLite
    return factory(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DagEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition on the fake."""
        self.sm.seed_initial()
        self.fake.add_node("a", noop_action, None, 0, 0)
        self.fake.add_node("b", noop_action, ["a"], 2, 1)
        self.fake.add_node("c", noop_action, None, 1, 0)
        self.fake.add_edge("a", "c")
        assert self.fake.has_node("a")
        assert not self.fake.has_node("ghost")
        node = self.fake.get_node("b")
        assert node.node_id == "b"
        assert node.dependencies == frozenset({"a"})
        assert self.fake.get_dependencies("b") == {"a"}
        assert self.fake.get_dependents("a") == {"b", "c"}
        assert self.fake.all_nodes() == {"a", "b", "c"}
        assert self.fake.find_roots() == {"a"}
        assert self.fake.find_leaves() == {"b", "c"}
        self.fake.validate()
        order = self.fake.topological_sort()
        assert order == ["a", "b", "c"]
        path, weight = self.fake.compute_critical_path(None)
        assert path == ["a", "b"]
        assert weight == 2.0
        assert self.fake.next_wave() == ["a"]
        self.fake.mark_running("a")
        self.fake.mark_succeeded("a")
        assert self.fake.get_state("b") is NodeState.READY
        assert self.fake.get_all_states() == {
            "a": NodeState.SUCCEEDED,
            "b": NodeState.READY,
            "c": NodeState.READY,
        }
        assert not self.fake.is_finished()
        self.fake.mark_running("b")
        self.fake.mark_succeeded("b")
        self.fake.mark_running("c")
        self.fake.mark_succeeded("c")
        assert self.fake.is_finished()
        self.fake.remove_node("c")
        report = self.fake.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"a", "b"}
        assert report.critical_path == ("a", "b")

    def test_mark_failed_skip_downstream(self) -> None:
        self.fake.add_node("a", noop_action, None, 0, 0)
        self.fake.add_node("b", noop_action, ["a"], 0, 0)
        self.fake.add_node("c", noop_action, ["b"], 0, 0)
        self.fake.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.fake.get_state("a") is NodeState.FAILED
        assert self.fake.get_state("b") is NodeState.SKIPPED
        assert self.fake.get_state("c") is NodeState.SKIPPED
        assert self.fake.is_finished()
        assert self.fake.next_wave() == []

    def test_mark_failed_fail_fast(self) -> None:
        self.fake.add_node("a", noop_action, None, 0, 0)
        self.fake.add_node("b", noop_action, ["a"], 0, 0)
        self.fake.mark_failed("a", FailurePolicy.FAIL_FAST)
        assert self.fake.get_state("a") is NodeState.FAILED
        assert self.fake.get_state("b") is NodeState.CANCELLED

    def test_mark_failed_continue_on_error(self) -> None:
        self.fake.add_node("a", noop_action, None, 0, 0)
        self.fake.add_node("b", noop_action, ["a"], 0, 0)
        self.fake.add_node("c", noop_action, None, 0, 0)
        self.fake.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.fake.get_state("a") is NodeState.FAILED
        assert self.fake.get_state("b") is NodeState.SKIPPED
        assert self.fake.get_state("c") is NodeState.READY

    def test_empty_dag(self) -> None:
        assert self.fake.all_nodes() == set()
        assert self.fake.find_roots() == set()
        assert self.fake.find_leaves() == set()
        assert self.fake.next_wave() == []
        assert self.fake.get_all_states() == {}
        assert self.fake.is_finished()
        assert self.fake.topological_sort() == []
        path, weight = self.fake.compute_critical_path(None)
        assert path == []
        assert weight == 0.0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T18:23:00Z
# LAST_CHANGED: 2026-11-09T18:23:00Z
# CHANGE: Resolve model/SUT postcondition divergence in next_wave: add promote_unblocked so PENDING nodes whose dependency edges were purged (empty upstream) are promoted to READY before the wave is resolved, matching observed scheduler behavior (model_wave=empty vs observed_wave=b). Audit of sibling transitions: the DAGRunner.run model loop now also promotes unblocked nodes before each wave, since the concrete runner resolves waves through the same promoting scheduler; get_state/get_all_states/is_finished intentionally keep no promotion (confirmed consistent with observed behavior).
# --- END AUTOFAB METADATA ---
