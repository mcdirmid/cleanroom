# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for the DAG engine.

The module inherits the upstream interface state machine and overrides each
transition so that the concrete ``DAG``, ``WaveScheduler``, and ``DAGRunner``
services are exercised through ``call_target`` while postconditions are
observed on the live singleton instances. ``TestDagEngineLiteImplReal`` drives
operational scenarios through checked adapters, and ``DagEngineLiteFuzzTest``
compiles real-SUT property fuzzing over the same pseudo-state machine.
"""

from __future__ import annotations

import unittest
from typing import Any, Callable, Collection, Mapping, Optional, Tuple

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
from benchmark_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
    FakeDagEngineLite,
    make_dag_engine_lite_fakes,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    FailurePolicy,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


# ==============================================================================
# 0. Real SUT Observation Helpers
# ==============================================================================

def _sut_has_missing_dependency(target: DAG) -> bool:
    """Report whether any registered node references an absent dependency."""
    nodes = target.all_nodes()
    for node_id in nodes:
        definition = target.get_node(node_id)
        for dependency in definition.dependencies:
            if dependency not in nodes:
                return True
        for dependency in target.get_dependencies(node_id):
            if dependency not in nodes:
                return True
    return False


def _sut_has_cycle(target: DAG) -> bool:
    """Report whether the registered dependency graph cannot be fully ordered."""
    nodes = target.all_nodes()
    upstream = {node_id: target.get_dependencies(node_id) for node_id in nodes}
    in_degree = {node_id: len(upstream[node_id]) for node_id in nodes}
    ready = [node_id for node_id in nodes if in_degree[node_id] == 0]
    ordered = 0
    while ready:
        current = ready.pop()
        ordered += 1
        for dependent in target.get_dependents(current):
            if dependent in in_degree:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
    return ordered != len(nodes)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for the concrete DAG engine."""

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
        stored = target.get_node(node_id)
        assert stored.dependencies == frozenset(dependencies or ())
        assert stored.priority == priority
        assert stored.retries == retries
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        if not target.has_node(upstream_id) or not target.has_node(downstream_id):
            with raises(NodeNotFoundError):
                call_target(target.add_edge(upstream_id, downstream_id))
            return None
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
        if not target.has_node(node_id):
            with raises(NodeNotFoundError):
                call_target(target.remove_node(node_id))
            return None
        prerequisites = set(target.get_dependencies(node_id))
        dependents = set(target.get_dependents(node_id))
        ret = call_target(target.remove_node(node_id))
        assert not target.has_node(node_id)
        for prerequisite in prerequisites:
            if target.has_node(prerequisite):
                assert node_id not in target.get_dependents(prerequisite)
        for dependent in dependents:
            if target.has_node(dependent):
                assert node_id not in target.get_dependencies(dependent)
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        if not target.has_node(node_id):
            with raises(NodeNotFoundError):
                call_target(target.get_node(node_id))
            return None
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        if not target.has_node(node_id):
            with raises(NodeNotFoundError):
                call_target(target.get_dependencies(node_id))
            return None
        ret = call_target(target.get_dependencies(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        if not target.has_node(node_id):
            with raises(NodeNotFoundError):
                call_target(target.get_dependents(node_id))
            return None
        ret = call_target(target.get_dependents(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert isinstance(ret, set)
        return ret

    @transition(DAG.validate)
    def validate(self) -> Any:
        target: DAG = sut(DAG)
        if _sut_has_missing_dependency(target):
            with raises(NodeNotFoundError):
                call_target(target.validate())
            return None
        if _sut_has_cycle(target):
            with raises(CycleError):
                call_target(target.validate())
            return None
        ret = call_target(target.validate())
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> Any:
        target: DAG = sut(DAG)
        if _sut_has_missing_dependency(target):
            with raises(NodeNotFoundError):
                call_target(target.topological_sort())
            return None
        if _sut_has_cycle(target):
            with raises(CycleError):
                call_target(target.topological_sort())
            return None
        ret = call_target(target.topological_sort())
        assert isinstance(ret, list)
        assert set(ret) == target.all_nodes()
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        assert isinstance(ret, set)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        assert isinstance(ret, set)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        if _sut_has_missing_dependency(target):
            with raises(NodeNotFoundError):
                call_target(target.compute_critical_path(estimated_durations))
            return None
        if _sut_has_cycle(target):
            with raises(CycleError):
                call_target(target.compute_critical_path(estimated_durations))
            return None
        ret = call_target(target.compute_critical_path(estimated_durations))
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        assert isinstance(ret[0], list)
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        assert isinstance(ret, list)
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
    def is_finished(self) -> Any:
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
    def get_all_states(self) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        graph: DAG = sut(DAG)
        ret = call_target(target.get_all_states())
        assert isinstance(ret, Mapping)
        assert set(ret.keys()) == graph.all_nodes()
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        graph: DAG = sut(DAG)
        ret = call_target(target.run(failure_policy))
        assert isinstance(ret, DAGRunReport)
        assert isinstance(ret.results, Mapping)
        assert ret.total_nodes <= len(graph.all_nodes())
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete DAG engine satisfies the contracted behavior."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.wavescheduler,
                DAGRunner: self.dagrunner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # ------------------------------------------------------------------
    # DAG node and edge registration
    # ------------------------------------------------------------------

    def test_add_node_registers_definition(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.has_node("a")
        self.checked_dag.get_node("a")
        self.checked_dag.get_dependencies("a")
        self.checked_dag.get_dependents("a")
        self.checked_dag.all_nodes()

    def test_add_node_with_dependencies(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 1, 0)
        self.checked_dag.get_dependencies("b")
        self.checked_dag.get_dependents("a")

    def test_add_node_defers_missing_dependency_validation(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, ["ghost"], 0, 0)
        self.checked_dag.has_node("a")
        self.checked_dag.get_dependencies("a")

    def test_add_edge_connects_existing_nodes(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.get_dependencies("b")
        self.checked_dag.get_dependents("a")

    def test_add_edge_rejects_missing_upstream(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.add_edge("missing", "a")

    def test_add_edge_rejects_missing_downstream(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.add_edge("a", "missing")

    def test_remove_node_purges_prerequisite_references(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.remove_node("a")
        self.checked_dag.all_nodes()
        self.checked_dag.get_dependencies("b")

    def test_remove_node_purges_dependent_references(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.remove_node("b")
        self.checked_dag.all_nodes()
        self.checked_dag.get_dependents("a")

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_dag.remove_node("a")
        self.checked_wavescheduler.get_all_states()
        self.checked_wavescheduler.get_state("b")

    def test_remove_node_rejects_unknown_node(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.remove_node("missing")

    def test_get_node_rejects_unknown_node(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.get_node("missing")

    def test_get_dependencies_rejects_unknown_node(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.get_dependencies("missing")

    def test_get_dependents_rejects_unknown_node(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.get_dependents("missing")

    # ------------------------------------------------------------------
    # DAG validation, ordering, and analysis
    # ------------------------------------------------------------------

    def test_validate_accepts_acyclic_graph(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, ["b"], 0, 0)
        self.checked_dag.validate()

    def test_validate_rejects_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.validate()

    def test_validate_rejects_cycle(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.checked_dag.validate()

    def test_topological_sort_breaks_ties_by_priority_then_identifier(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 5, 0)
        self.checked_dag.add_node("c", lambda: 3, ["a"], 1, 0)
        self.checked_dag.add_node("d", lambda: 4, ["b"], 1, 0)
        self.checked_dag.topological_sort()

    def test_topological_sort_rejects_cycle(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.checked_dag.topological_sort()

    def test_topological_sort_rejects_deferred_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, ["b"], 0, 0)
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()

    def test_compute_critical_path_with_default_weights(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, ["a"], 0, 0)
        self.checked_dag.add_node("d", lambda: 4, ["b"], 0, 0)
        self.checked_dag.compute_critical_path(None)

    def test_compute_critical_path_with_estimated_durations(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, ["a"], 0, 0)
        self.checked_dag.compute_critical_path({"a": 2.0, "b": 1.0, "c": 5.0})

    def test_compute_critical_path_for_empty_graph(self) -> None:
        self.checked_dag.compute_critical_path(None)
        self.checked_dag.compute_critical_path({})

    # ------------------------------------------------------------------
    # Wave scheduling lifecycle
    # ------------------------------------------------------------------

    def test_scheduler_wave_progression(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, None, 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        self.checked_wavescheduler.get_state("a")
        self.checked_wavescheduler.get_all_states()
        self.checked_wavescheduler.is_finished()

    def test_scheduler_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.checked_wavescheduler.is_finished()

    def test_scheduler_mark_failed_skip_downstream_skips_dependents(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, ["b"], 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_wavescheduler.is_finished()

    def test_scheduler_mark_failed_continue_on_error_keeps_independent_nodes(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, None, 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_wavescheduler.next_wave()

    def test_scheduler_dependent_with_unfinished_prerequisite_stays_pending(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, ["a", "b"], 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        self.checked_wavescheduler.get_state("c")
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        self.checked_wavescheduler.next_wave()

    def test_scheduler_continue_on_error_promotes_late_registered_node(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("f", lambda: 2, None, 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        self.checked_dag.add_node("b", lambda: 3, ["a"], 0, 0)
        self.checked_wavescheduler.mark_running("f")
        self.checked_wavescheduler.mark_failed("f", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_wavescheduler.next_wave()

    def test_scheduler_is_finished_for_empty_graph(self) -> None:
        self.checked_wavescheduler.is_finished()

    def test_scheduler_is_finished_with_node_in_progress(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_wavescheduler.next_wave()
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.is_finished()

    def test_scheduler_is_finished_with_only_blocked_pending_nodes(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, ["ghost"], 0, 0)
        self.checked_wavescheduler.is_finished()

    def test_scheduler_get_state_initializes_pending_dependent(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_wavescheduler.get_state("b")
        self.checked_wavescheduler.get_all_states()

    # ------------------------------------------------------------------
    # Runner execution and failure policies
    # ------------------------------------------------------------------

    def test_runner_executes_graph_to_completion(self) -> None:
        calls: list[str] = []

        def record_a() -> None:
            calls.append("a")

        def record_b() -> None:
            calls.append("b")

        self.checked_dag.add_node("a", record_a, None, 0, 0)
        self.checked_dag.add_node("b", record_b, ["a"], 0, 0)
        self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_runner_retries_transient_failure(self) -> None:
        attempts: list[int] = []

        def flaky() -> None:
            attempts.append(1)
            if len(attempts) < 2:
                raise RuntimeError("transient failure")

        self.checked_dag.add_node("a", flaky, None, 0, 2)
        self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_fail_fast_policy(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.checked_dag.add_node("a", boom, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_runner_continue_on_error_policy(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.checked_dag.add_node("a", boom, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: 3, None, 0, 0)
        self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_skip_downstream_policy(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.checked_dag.add_node("a", boom, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_rejects_cycle(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_runner_rejects_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for the DAG engine fuzz test."""

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
# LAST_CLEANED: 2026-11-03T00:59:15Z
# LAST_CHANGED: 2026-11-03T00:57:15Z
# CHANGE: Fixed the deferred missing-dependency expectation: test_topological_sort_rejects_deferred_missing_dependency now asserts NodeNotFoundError (not CycleError) for a node referencing unknown dependency 'ghost', matching DAG.add_node's deferred-validation contract. The topological_sort and compute_critical_path overrides now branch on an SUT missing-dependency check before the cycle check, verifying NodeNotFoundError for unknown references and reserving CycleError for genuine directed cycles, so the exercised postconditions no longer contradict low/dag_engine_lite.pyi.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T00:59:15Z
# PRETENSE_QA_AUDIT: 2026-11-03T00:59:04Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for the DAG engine.

This module models the three collaborating interfaces declared in
``benchmark_1/parts/dag_engine_lite/low/dag_engine_lite.pyi``:

* ``DAG`` owns immutable node definitions plus upstream/downstream adjacency
  bookkeeping and deterministic topological ordering.
* ``WaveScheduler`` tracks per-node :class:`NodeState` lifecycle values and
  applies the contracted failure policies.
* ``DAGRunner`` executes ready waves sequentially and consolidates a
  :class:`DAGRunReport`.

Every public target method is modeled by exactly one 1:1 transition. Model
mutations and assertions are derived strictly from the contracted
POSTCONDITIONS in the specification. The synthesized fake exposes the full
public interface, and the compiled Hypothesis property test fuzzes the fake.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

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
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)


# ==============================================================================
# 0. Shared Model Helpers
# ==============================================================================

_TERMINAL_STATES = frozenset(
    {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
)


def _sync_scheduler_states(state: DagEngineLiteState) -> None:
    """Mirror the scheduler's lazy synchronization across registered DAG nodes."""
    for node_id in list(state.states.keys()):
        if node_id not in state.nodes:
            del state.states[node_id]
    for node_id in state.nodes:
        if node_id in state.states:
            continue
        dependencies = state.upstream.get(node_id, set())
        if all(state.states.get(dependency) is NodeState.SUCCEEDED for dependency in dependencies):
            state.states[node_id] = NodeState.READY
        else:
            state.states[node_id] = NodeState.PENDING


def _priority_key(state: DagEngineLiteState, node_id: str) -> Tuple[int, str]:
    """Ordering key: priority descending, then node identifier ascending."""
    return (-state.nodes[node_id].priority, node_id)


def _kahn_order(state: DagEngineLiteState) -> List[str]:
    """Kahn topological order with priority descending / identifier ascending ties."""
    in_degree = {node_id: len(state.upstream.get(node_id, set())) for node_id in state.nodes}
    heap: List[Tuple[int, str]] = [
        _priority_key(state, node_id) for node_id in state.nodes if in_degree[node_id] == 0
    ]
    heapq.heapify(heap)
    order: List[str] = []
    for _ in range(len(state.nodes)):
        if not heap:
            break
        _, current = heapq.heappop(heap)
        order.append(current)
        for dependent in sorted(state.downstream.get(current, set())):
            if dependent not in in_degree:
                continue
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(heap, _priority_key(state, dependent))
    return order


def _find_cycle(state: DagEngineLiteState) -> Tuple[str, ...]:
    """Find one directed dependency cycle, returning an empty tuple when acyclic."""
    colors: Dict[str, int] = {}

    def visit(node_id: str, path: List[str]) -> Optional[Tuple[str, ...]]:
        colors[node_id] = 1
        path.append(node_id)
        for dependency in sorted(state.upstream.get(node_id, set())):
            if dependency not in state.nodes:
                continue
            color = colors.get(dependency, 0)
            if color == 1:
                return tuple(path[path.index(dependency) :])
            if color == 0:
                cycle = visit(dependency, path)
                if cycle is not None:
                    return cycle
        path.pop()
        colors[node_id] = 2
        return None

    for node_id in sorted(state.nodes):
        if colors.get(node_id, 0) == 0:
            cycle = visit(node_id, [])
            if cycle is not None:
                return cycle
    return ()


def _missing_dependency(state: DagEngineLiteState) -> Optional[str]:
    """Return the first referenced dependency absent from the graph, if any."""
    for node_id in sorted(state.nodes):
        dependencies = set(state.nodes[node_id].dependencies) | state.upstream.get(node_id, set())
        for dependency in sorted(dependencies):
            if dependency not in state.nodes:
                return dependency
    return None


def _ready_wave(state: DagEngineLiteState) -> List[str]:
    """Resolve and order the ready nodes whose upstream dependencies succeeded."""
    _sync_scheduler_states(state)
    ready = [
        node_id
        for node_id in state.nodes
        if state.states.get(node_id) is NodeState.READY
        and all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.upstream.get(node_id, set())
        )
    ]
    ready.sort(key=lambda node_id: _priority_key(state, node_id))
    return ready


def _promote_dependents(state: DagEngineLiteState, node_id: str) -> None:
    """Promote newly unblocked downstream dependents from PENDING to READY."""
    for dependent in sorted(state.downstream.get(node_id, set())):
        if dependent not in state.nodes:
            continue
        if state.states.get(dependent) is not NodeState.PENDING:
            continue
        if all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.upstream.get(dependent, set())
        ):
            state.states[dependent] = NodeState.READY


def _transitive_dependents(state: DagEngineLiteState, node_id: str) -> Set[str]:
    """Collect every transitive downstream dependent of a node."""
    collected: Set[str] = set()
    frontier: List[str] = list(state.downstream.get(node_id, set()))
    while frontier:
        current = frontier.pop()
        if current in collected or current == node_id:
            continue
        collected.add(current)
        frontier.extend(state.downstream.get(current, set()))
    return collected


def _terminal_node(
    state: DagEngineLiteState,
    order: List[str],
    earliest: Mapping[str, float],
) -> Optional[str]:
    """Select the terminal node with the greatest completion time."""
    if not order:
        return None
    candidates = [node_id for node_id in order if not state.downstream.get(node_id)]
    if not candidates:
        candidates = list(order)
    return max(sorted(candidates), key=lambda node_id: earliest.get(node_id, 0.0))


def _critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Compute the longest weighted dependency path through the graph."""
    order = _kahn_order(state)
    durations: Mapping[str, float] = estimated_durations or {}
    earliest: Dict[str, float] = {}
    predecessor: Dict[str, Optional[str]] = {}
    for node_id in order:
        dependency_times: Dict[str, float] = {
            dependency: earliest[dependency]
            for dependency in sorted(state.upstream.get(node_id, set()))
            if dependency in earliest
        }
        best_predecessor: Optional[str] = None
        best_time = 0.0
        if dependency_times:
            best_predecessor = max(dependency_times, key=lambda dependency: dependency_times[dependency])
            best_time = dependency_times[best_predecessor]
        earliest[node_id] = best_time + float(durations.get(node_id, 1.0))
        predecessor[node_id] = best_predecessor
    terminal = _terminal_node(state, order, earliest)
    path: List[str] = []
    current = terminal
    for _ in range(len(order)):
        if current is None:
            break
        path.append(current)
        current = predecessor.get(current)
    path.reverse()
    total = earliest.get(terminal, 0.0) if terminal is not None else 0.0
    return path, total


def _model_run(state: DagEngineLiteState, failure_policy: FailurePolicy) -> DAGRunReport:
    """Optimistically simulate a run, promoting each modeled node to SUCCEEDED."""
    state.results.clear()
    for _ in range(len(state.nodes) + 1):
        wave = _ready_wave(state)
        if not wave:
            break
        for node_id in wave:
            state.states[node_id] = NodeState.SUCCEEDED
            state.results[node_id] = NodeResult(node_id=node_id, state=NodeState.SUCCEEDED)
            _promote_dependents(state, node_id)
    for node_id in state.nodes:
        if node_id in state.results:
            continue
        node_state = state.states.get(node_id)
        if node_state in {NodeState.SKIPPED, NodeState.CANCELLED}:
            state.results[node_id] = NodeResult(node_id=node_id, state=node_state)
    succeeded = tuple(
        node_id for node_id, result in state.results.items() if result.state is NodeState.SUCCEEDED
    )
    failed = tuple(
        node_id for node_id, result in state.results.items() if result.state is NodeState.FAILED
    )
    skipped = tuple(
        node_id for node_id, result in state.results.items() if result.state is NodeState.SKIPPED
    )
    cancelled = tuple(
        node_id for node_id, result in state.results.items() if result.state is NodeState.CANCELLED
    )
    critical_path, _ = _critical_path(state, None)
    return DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded,
        failed_nodes=failed,
        skipped_nodes=skipped,
        cancelled_nodes=cancelled,
        wall_clock_seconds=0.0,
        critical_path=tuple(critical_path),
        results=dict(state.results),
    )


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions (with raises(ExpectedException))
# live naturally inside the single transition body. require_arg defines the
# caller precondition contract, and only self.state is inspected by require(...).


@dataclass
class DagEngineLiteState:
    """Canonical model state for the DAG engine services."""

    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    initialized: bool = True


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for the DAG engine interfaces."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    # ------------------------------------------------------------------
    # DAG interface
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
        """Register a node definition and its deferred dependency edges."""
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])))
        require_arg(priority, Domain.type(int))
        require_arg(retries, Domain.type(int))
        dependency_set = frozenset(dependencies or ())
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        ret = make_return_value()
        assert ret is None
        assert node_id in self.state.nodes
        assert self.state.nodes[node_id].dependencies == dependency_set
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        """Add one directed dependency edge between two registered nodes."""
        require(self.state.initialized)
        require_arg(upstream_id, Domain.type(str), preferred=["a", "b", "c"])
        require_arg(downstream_id, Domain.type(str), preferred=["a", "b", "c"])
        if upstream_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(
                    f"upstream node {upstream_id!r} is not registered", upstream_id
                )
            raise NodeNotFoundError(f"upstream node {upstream_id!r} is not registered", upstream_id)
        if downstream_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(
                    f"downstream node {downstream_id!r} is not registered", downstream_id
                )
            raise NodeNotFoundError(
                f"downstream node {downstream_id!r} is not registered", downstream_id
            )
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        ret = make_return_value()
        assert ret is None
        assert upstream_id in self.state.upstream.get(downstream_id, set())
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        """Remove a node, its incident edges, and its scheduler bookkeeping."""
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
            raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        for dependency in set(self.state.upstream.get(node_id, set())):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in set(self.state.downstream.get(node_id, set())):
            self.state.upstream.get(dependent, set()).discard(node_id)
        del self.state.nodes[node_id]
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        ret = make_return_value()
        assert ret is None
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        """Report whether the identifier is registered in the graph."""
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        exists = node_id in self.state.nodes
        ret: bool = make_return_value(exists)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        """Return the registered immutable definition for the identifier."""
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
            raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        definition = self.state.nodes[node_id]
        ret: NodeDefinition[Any] = make_return_value(definition)
        assert ret.node_id == node_id
        assert ret.dependencies == definition.dependencies
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        """Return a copy of the direct upstream dependency identifiers."""
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
            raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        dependencies = set(self.state.upstream.get(node_id, set()))
        ret: Set[str] = make_return_value(dependencies)
        assert ret == self.state.upstream.get(node_id, set())
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        """Return a copy of the direct downstream dependent identifiers."""
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        if node_id not in self.state.nodes:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
            raise NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        dependents = set(self.state.downstream.get(node_id, set()))
        ret: Set[str] = make_return_value(dependents)
        assert ret == self.state.downstream.get(node_id, set())
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        """Return every currently registered node identifier."""
        require(self.state.initialized)
        identifiers = set(self.state.nodes)
        ret: Set[str] = make_return_value(identifiers)
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        """Validate dependency completeness and acyclicity."""
        require(self.state.initialized)
        missing = _missing_dependency(self.state)
        if missing is not None:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(
                    f"dependency node {missing!r} is not registered", missing
                )
            raise NodeNotFoundError(f"dependency node {missing!r} is not registered", missing)
        cycle = _find_cycle(self.state)
        if cycle:
            with raises(CycleError):
                make_return_value()
                raise CycleError("directed dependency cycle detected", cycle)
            raise CycleError("directed dependency cycle detected", cycle)
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        """Return the deterministic priority-aware topological ordering."""
        require(self.state.initialized)
        missing = _missing_dependency(self.state)
        if missing is not None:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(
                    f"dependency node {missing!r} is not registered", missing
                )
            raise NodeNotFoundError(f"dependency node {missing!r} is not registered", missing)
        order = _kahn_order(self.state)
        if len(order) != len(self.state.nodes):
            cycle = _find_cycle(self.state)
            if not cycle:
                cycle = tuple(sorted(set(self.state.nodes) - set(order)))
            with raises(CycleError):
                make_return_value()
                raise CycleError("directed dependency cycle detected", cycle)
            raise CycleError("directed dependency cycle detected", cycle)
        ret: List[str] = make_return_value(order)
        assert len(ret) == len(self.state.nodes)
        assert set(ret) == set(self.state.nodes)
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        """Return every node with no upstream dependencies."""
        require(self.state.initialized)
        roots = {
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)
        }
        ret: Set[str] = make_return_value(roots)
        assert ret == {
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)
        }
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        """Return every node with no downstream dependents."""
        require(self.state.initialized)
        leaves = {
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)
        }
        ret: Set[str] = make_return_value(leaves)
        assert ret == {
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)
        }
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Return the longest weighted dependency path and its total weight."""
        require(self.state.initialized)
        require_arg(estimated_durations, Domain.optional(Domain.type(Mapping[str, float])))
        missing = _missing_dependency(self.state)
        if missing is not None:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(
                    f"dependency node {missing!r} is not registered", missing
                )
            raise NodeNotFoundError(f"dependency node {missing!r} is not registered", missing)
        order = _kahn_order(self.state)
        if len(order) != len(self.state.nodes):
            cycle = _find_cycle(self.state)
            if not cycle:
                cycle = tuple(sorted(set(self.state.nodes) - set(order)))
            with raises(CycleError):
                make_return_value()
                raise CycleError("directed dependency cycle detected", cycle)
            raise CycleError("directed dependency cycle detected", cycle)
        path, weight = _critical_path(self.state, estimated_durations)
        ret: Tuple[List[str], float] = make_return_value((path, weight))
        assert ret[1] == weight
        return ret

    # ------------------------------------------------------------------
    # WaveScheduler interface
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        """Resolve the next ordered batch of ready node identifiers."""
        require(self.state.initialized)
        wave = _ready_wave(self.state)
        ret: List[str] = make_return_value(wave)
        assert ret == wave
        assert all(self.state.states.get(node_id) is NodeState.READY for node_id in ret)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        """Transition the node to the RUNNING lifecycle state."""
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        self.state.states[node_id] = NodeState.RUNNING
        ret = make_return_value()
        assert ret is None
        assert self.state.states.get(node_id) is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        """Transition the node to SUCCEEDED and unlock newly ready dependents."""
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        self.state.states[node_id] = NodeState.SUCCEEDED
        _promote_dependents(self.state, node_id)
        ret = make_return_value()
        assert ret is None
        assert self.state.states.get(node_id) is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        """Transition the node to FAILED and apply the contracted failure policy."""
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
        )
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other in self.state.nodes:
                if self.state.states.get(other) not in _TERMINAL_STATES:
                    self.state.states[other] = NodeState.CANCELLED
        else:
            for dependent in _transitive_dependents(self.state, node_id):
                if dependent not in self.state.nodes:
                    continue
                if self.state.states.get(dependent) not in _TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
        ret = make_return_value()
        assert ret is None
        assert self.state.states.get(node_id) is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        """Report whether every node reached a terminal state or is blocked."""
        require(self.state.initialized)
        _sync_scheduler_states(self.state)
        all_terminal = all(
            self.state.states.get(node_id) in _TERMINAL_STATES for node_id in self.state.nodes
        )
        executable = any(
            self.state.states.get(node_id) in {NodeState.READY, NodeState.RUNNING}
            for node_id in self.state.nodes
        )
        finished = all_terminal or not executable
        ret: bool = make_return_value(finished)
        assert ret or executable
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        """Return the current lifecycle state of the identifier."""
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        _sync_scheduler_states(self.state)
        node_state = self.state.states.get(node_id, NodeState.PENDING)
        ret: NodeState = make_return_value(node_state)
        assert ret is node_state
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Return the lifecycle state of every currently registered node."""
        require(self.state.initialized)
        _sync_scheduler_states(self.state)
        snapshot = {
            node_id: self.state.states.get(node_id, NodeState.PENDING)
            for node_id in self.state.nodes
        }
        ret: Mapping[str, NodeState] = make_return_value(snapshot)
        assert set(ret.keys()) == set(self.state.nodes)
        return ret

    # ------------------------------------------------------------------
    # DAGRunner interface
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Execute the graph wave by wave and consolidate the run report."""
        require(self.state.initialized)
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
        )
        missing = _missing_dependency(self.state)
        if missing is not None:
            with raises(NodeNotFoundError):
                make_return_value()
                raise NodeNotFoundError(
                    f"dependency node {missing!r} is not registered", missing
                )
            raise NodeNotFoundError(f"dependency node {missing!r} is not registered", missing)
        cycle = _find_cycle(self.state)
        if cycle:
            with raises(CycleError):
                make_return_value()
                raise CycleError("directed dependency cycle detected", cycle)
            raise CycleError("directed dependency cycle detected", cycle)
        report = _model_run(self.state, failure_policy)
        ret: DAGRunReport = make_return_value(report)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed the model state used to initialize synthesized fakes."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesize fake services backed by one shared model state machine."""
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
    return (fake, fake, fake)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T00:57:12Z
# LAST_CHANGED: 2026-11-03T00:57:12Z
# CHANGE: Corrected deferred missing-dependency semantics in the model: topological_sort and compute_critical_path now raise NodeNotFoundError when a node references an unregistered dependency (per DAG.add_node's deferred-validation postcondition), reserving CycleError strictly for genuine directed cycles. This aligns model behavior with the contract and the implementation's deferred checks.
# --- END AUTOFAB METADATA ---
