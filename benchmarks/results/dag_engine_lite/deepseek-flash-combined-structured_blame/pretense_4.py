# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

import unittest
from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib import (
    dag_engine_lite,
    dag_engine_lite_impl,
)
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineState,
    DAGEngineStateMachine,
)


def _succeed() -> int:
    """Node action that always completes successfully."""
    return 42


def _explode() -> int:
    """Node action that always raises so failure policies can be exercised."""
    raise RuntimeError("node action failed")


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DAGEngineImplPseudoStateMachine(DAGEngineStateMachine):
    """Implementation pseudo-state machine binding the concrete DAG engine services."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        target.add_node(node_id, action, dependencies, priority, retries)
        assert target.has_node(node_id)
        return None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        target.add_edge(upstream_id, downstream_id)
        assert upstream_id in target.get_dependencies(downstream_id)
        return None

    def inner_remove_node(self, node_id: str) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        target.remove_node(node_id)
        assert not target.has_node(node_id)
        return None

    def inner_has_node(self, node_id: str) -> bool:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.all_nodes()

    def inner_validate(self) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        target.validate()
        return None

    def inner_topological_sort(self) -> List[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.compute_critical_path(estimated_durations)

    def inner_next_wave(self) -> List[str]:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        target.mark_running(node_id)
        assert target.get_state(node_id) == dag_engine_lite.NodeState.RUNNING
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        target.mark_succeeded(node_id)
        assert target.get_state(node_id) == dag_engine_lite.NodeState.SUCCEEDED
        return None

    def inner_mark_failed(
        self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy
    ) -> None:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        target.mark_failed(node_id, failure_policy)
        assert target.get_state(node_id) == dag_engine_lite.NodeState.FAILED
        return None

    def inner_is_finished(self) -> bool:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.get_all_states()

    def inner_run(
        self, failure_policy: dag_engine_lite.FailurePolicy
    ) -> dag_engine_lite.DAGRunReport:
        target: dag_engine_lite.DAGRunner = sut(dag_engine_lite.DAGRunner)
        return target.run(failure_policy)


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDAGEngineImplReal(LifecycleTestCase, unittest.TestCase):
    """Verifies that the concrete DAG engine implementation satisfies its contracts."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        dag = self.get_singleton(dag_engine_lite.DAG)
        scheduler = self.get_singleton(dag_engine_lite.WaveScheduler)
        runner = self.get_singleton(dag_engine_lite.DAGRunner)
        self.sm = DAGEngineImplPseudoStateMachine(
            singletons={
                dag_engine_lite.DAG: dag,
                dag_engine_lite.WaveScheduler: scheduler,
                dag_engine_lite.DAGRunner: runner,
            }
        )
        self.checked = self.sm.as_checked(dag_engine_lite.DAG, dag)
        self.checked_scheduler = self.sm.as_checked(dag_engine_lite.WaveScheduler, scheduler)
        self.checked_runner = self.sm.as_checked(dag_engine_lite.DAGRunner, runner)

    # --------------------------------------------------------------------------
    # Graph scenarios
    # --------------------------------------------------------------------------

    def test_graph_construction_and_queries(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 1, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 1)
        self.checked.add_node("gamma", _succeed, (), 2, 0)
        assert self.checked.has_node("alpha")
        assert not self.checked.has_node("delta")
        assert self.checked.get_node("beta").node_id == "beta"
        assert self.checked.get_dependencies("beta") == {"alpha"}
        assert self.checked.get_dependents("alpha") == {"beta"}
        assert self.checked.all_nodes() == {"alpha", "beta", "gamma"}
        assert self.checked.find_roots() == {"alpha", "gamma"}
        assert self.checked.find_leaves() == {"beta", "gamma"}
        self.checked.validate()
        assert self.checked.topological_sort() == ["gamma", "alpha", "beta"]

    def test_graph_edges_and_removal(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked.add_node("gamma", _succeed, None, 0, 0)
        self.checked.add_edge("gamma", "beta")
        assert self.checked.get_dependencies("beta") == {"alpha", "gamma"}
        assert self.checked.get_dependents("gamma") == {"beta"}
        self.checked.remove_node("gamma")
        assert not self.checked.has_node("gamma")
        assert self.checked.get_dependencies("beta") == {"alpha"}
        assert self.checked.all_nodes() == {"alpha", "beta"}

    def test_remove_node_purges_incident_edges(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked.add_node("gamma", _succeed, ["beta"], 0, 0)
        assert self.checked.get_dependencies("beta") == {"alpha"}
        assert self.checked.get_dependents("beta") == {"gamma"}
        self.checked.remove_node("beta")
        assert not self.checked.has_node("beta")
        assert self.checked.get_dependencies("gamma") == set()
        assert self.checked.get_dependents("alpha") == set()
        assert self.checked.all_nodes() == {"alpha", "gamma"}
        self.checked.validate()

    def test_critical_path(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, ["a"], 0, 0)
        self.checked.add_node("c", _succeed, ["b"], 0, 0)
        path, weight = self.checked.compute_critical_path(None)
        assert path == ["a", "b", "c"]
        assert weight == 3.0
        weighted_path, weighted = self.checked.compute_critical_path(
            {"a": 2.0, "b": 1.0, "c": 5.0}
        )
        assert weighted_path == ["a", "b", "c"]
        assert weighted == 8.0

    def test_empty_graph(self) -> None:
        assert self.checked.all_nodes() == set()
        assert self.checked.find_roots() == set()
        assert self.checked.find_leaves() == set()
        assert self.checked.topological_sort() == []
        assert self.checked.compute_critical_path(None) == ([], 0.0)
        self.checked.validate()
        assert self.checked_scheduler.get_all_states() == {}
        assert self.checked_scheduler.is_finished()

    # --------------------------------------------------------------------------
    # Graph contract violations
    # --------------------------------------------------------------------------

    def test_duplicate_node_error(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.violating(dag_engine_lite.DuplicateNodeError).add_node(
            "alpha", _succeed, None, 0, 0
        )

    def test_add_edge_missing_node_error(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.violating(dag_engine_lite.NodeNotFoundError).add_edge("alpha", "ghost")

    def test_add_edge_missing_upstream_error(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.violating(dag_engine_lite.NodeNotFoundError).add_edge("ghost", "alpha")

    def test_remove_node_missing_error(self) -> None:
        self.checked.violating(dag_engine_lite.NodeNotFoundError).remove_node("ghost")

    def test_get_node_missing_error(self) -> None:
        self.checked.violating(dag_engine_lite.NodeNotFoundError).get_node("ghost")

    def test_get_dependencies_missing_error(self) -> None:
        self.checked.violating(dag_engine_lite.NodeNotFoundError).get_dependencies("ghost")

    def test_get_dependents_missing_error(self) -> None:
        self.checked.violating(dag_engine_lite.NodeNotFoundError).get_dependents("ghost")

    def test_validate_missing_dependency_error(self) -> None:
        self.checked.add_node("alpha", _succeed, ["ghost"], 0, 0)
        self.checked.violating(dag_engine_lite.NodeNotFoundError).validate()

    def test_validate_cycle_error(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, None, 0, 0)
        self.checked.add_edge("a", "b")
        self.checked.add_edge("b", "a")
        self.checked.violating(dag_engine_lite.CycleError).validate()

    def test_topological_sort_cycle_error(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, None, 0, 0)
        self.checked.add_edge("a", "b")
        self.checked.add_edge("b", "a")
        self.checked.violating(dag_engine_lite.CycleError).topological_sort()

    # --------------------------------------------------------------------------
    # Scheduler scenarios
    # --------------------------------------------------------------------------

    def test_scheduler_waves(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        assert not self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_running("alpha")
        assert self.checked_scheduler.get_state("alpha") == dag_engine_lite.NodeState.RUNNING
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.next_wave() == ["beta"]
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        assert (
            self.checked_scheduler.get_all_states()["beta"]
            == dag_engine_lite.NodeState.SUCCEEDED
        )
        assert self.checked_scheduler.is_finished()

    def test_scheduler_fail_fast(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed("alpha", dag_engine_lite.FailurePolicy.FAIL_FAST)
        states = self.checked_scheduler.get_all_states()
        assert states["alpha"] == dag_engine_lite.NodeState.FAILED
        assert states["beta"] == dag_engine_lite.NodeState.CANCELLED
        assert self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked.add_node("gamma", _succeed, ["beta"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed(
            "alpha", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.checked_scheduler.get_all_states()
        assert states["beta"] == dag_engine_lite.NodeState.SKIPPED
        assert states["gamma"] == dag_engine_lite.NodeState.SKIPPED

    def test_scheduler_continue_on_error(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked.add_node("gamma", _succeed, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed(
            "alpha", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )
        states = self.checked_scheduler.get_all_states()
        assert states["beta"] == dag_engine_lite.NodeState.SKIPPED
        assert states["gamma"] == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.next_wave() == ["gamma"]

    def test_scheduler_get_state_missing_error(self) -> None:
        self.checked_scheduler.violating(dag_engine_lite.NodeNotFoundError).get_state("ghost")

    def test_scheduler_dynamic_registration_after_success(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked.add_node("delta", _succeed, None, 0, 0)
        assert self.checked_scheduler.get_state("delta") == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.next_wave() == ["delta"]

    def test_scheduler_dependency_bearing_registration_after_upstream_success(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked.add_node("delta", _succeed, ["alpha"], 0, 0)
        assert self.checked_scheduler.get_state("delta") == dag_engine_lite.NodeState.PENDING
        assert self.checked_scheduler.next_wave() == []
        assert not self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("delta") == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.next_wave() == ["delta"]

    def test_scheduler_mark_succeeded_dependent_already_ready(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "beta"]
        self.checked.add_edge("alpha", "beta")
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("beta") == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.next_wave() == ["beta"]

    def test_scheduler_skip_downstream_diamond(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, ["a"], 0, 0)
        self.checked.add_node("c", _succeed, ["a"], 0, 0)
        self.checked.add_node("d", _succeed, ["b", "c"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["a"]
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.checked_scheduler.get_all_states()
        assert states["b"] == dag_engine_lite.NodeState.SKIPPED
        assert states["c"] == dag_engine_lite.NodeState.SKIPPED
        assert states["d"] == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_fanout_with_cross_dependency(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, ["a"], 0, 0)
        self.checked.add_node("c", _succeed, ["a"], 0, 0)
        self.checked.add_edge("b", "c")
        assert self.checked.get_dependents("a") == {"b", "c"}
        assert self.checked.get_dependents("b") == {"c"}
        assert self.checked.get_dependencies("c") == {"a", "b"}
        assert self.checked_scheduler.next_wave() == ["a"]
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.checked_scheduler.get_all_states()
        assert states["a"] == dag_engine_lite.NodeState.FAILED
        assert states["b"] == dag_engine_lite.NodeState.SKIPPED
        assert states["c"] == dag_engine_lite.NodeState.SKIPPED
        assert (
            sum(
                1
                for state in states.values()
                if state == dag_engine_lite.NodeState.SKIPPED
            )
            == 2
        )
        assert self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_triangle_below_dependent(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, ["a"], 0, 0)
        self.checked.add_node("c", _succeed, ["b"], 0, 0)
        self.checked.add_node("d", _succeed, ["b", "c"], 0, 0)
        assert self.checked.get_dependents("a") == {"b"}
        assert self.checked.get_dependents("b") == {"c", "d"}
        assert self.checked.get_dependents("c") == {"d"}
        assert self.checked_scheduler.next_wave() == ["a"]
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.checked_scheduler.get_all_states()
        assert states["a"] == dag_engine_lite.NodeState.FAILED
        assert states["b"] == dag_engine_lite.NodeState.SKIPPED
        assert states["c"] == dag_engine_lite.NodeState.SKIPPED
        assert states["d"] == dag_engine_lite.NodeState.SKIPPED
        assert (
            sum(
                1
                for state in states.values()
                if state == dag_engine_lite.NodeState.SKIPPED
            )
            == 3
        )
        assert self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_fanout_cross_edge_below_dependent(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, ["a"], 0, 0)
        self.checked.add_node("c", _succeed, ["a"], 0, 0)
        self.checked.add_node("d", _succeed, ["b"], 0, 0)
        self.checked.add_edge("d", "c")
        assert self.checked.get_dependents("a") == {"b", "c"}
        assert self.checked.get_dependents("b") == {"d"}
        assert self.checked.get_dependents("d") == {"c"}
        assert self.checked.get_dependencies("c") == {"a", "d"}
        assert self.checked_scheduler.next_wave() == ["a"]
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.checked_scheduler.get_all_states()
        assert states["a"] == dag_engine_lite.NodeState.FAILED
        assert states["b"] == dag_engine_lite.NodeState.SKIPPED
        assert states["c"] == dag_engine_lite.NodeState.SKIPPED
        assert states["d"] == dag_engine_lite.NodeState.SKIPPED
        assert (
            sum(
                1
                for state in states.values()
                if state == dag_engine_lite.NodeState.SKIPPED
            )
            == 3
        )
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_fanout_cross_edge_below_dependent_reentry(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, ["a"], 0, 0)
        self.checked.add_node("c", _succeed, ["a"], 0, 0)
        self.checked.add_node("d", _succeed, ["c"], 0, 0)
        self.checked.add_edge("d", "b")
        assert self.checked.get_dependents("a") == {"b", "c"}
        assert self.checked.get_dependents("c") == {"d"}
        assert self.checked.get_dependents("d") == {"b"}
        assert self.checked.get_dependencies("b") == {"a", "d"}
        assert self.checked_scheduler.next_wave() == ["a"]
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.checked_scheduler.get_all_states()
        assert states["a"] == dag_engine_lite.NodeState.FAILED
        assert states["b"] == dag_engine_lite.NodeState.SKIPPED
        assert states["c"] == dag_engine_lite.NodeState.SKIPPED
        assert states["d"] == dag_engine_lite.NodeState.SKIPPED
        assert (
            sum(
                1
                for state in states.values()
                if state == dag_engine_lite.NodeState.SKIPPED
            )
            == 3
        )
        assert self.checked_scheduler.is_finished()

    def test_scheduler_is_finished_blocked_by_failure(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.checked.add_node("gamma", _succeed, ["alpha"], 0, 0)
        assert self.checked_scheduler.get_state("gamma") == dag_engine_lite.NodeState.PENDING
        assert self.checked_scheduler.is_finished()

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked.remove_node("beta")
        states = self.checked_scheduler.get_all_states()
        assert "beta" not in states
        assert states["alpha"] == dag_engine_lite.NodeState.READY
        self.checked_scheduler.violating(dag_engine_lite.NodeNotFoundError).get_state("beta")

    # --------------------------------------------------------------------------
    # Runner scenarios
    # --------------------------------------------------------------------------

    def test_runner_success(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"alpha", "beta"}
        assert report.failed_nodes == ()
        assert set(report.critical_path) == {"alpha", "beta"}

    def test_runner_fail_fast(self) -> None:
        self.checked.add_node("alpha", _explode, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert "alpha" in report.failed_nodes
        assert report.total_nodes == 2

    def test_runner_skip_downstream(self) -> None:
        self.checked.add_node("alpha", _explode, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked.add_node("gamma", _succeed, ["beta"], 0, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        assert "alpha" in report.failed_nodes
        assert "beta" in report.skipped_nodes

    def test_runner_continue_on_error(self) -> None:
        self.checked.add_node("alpha", _explode, None, 0, 0)
        self.checked.add_node("beta", _succeed, ["alpha"], 0, 0)
        self.checked.add_node("gamma", _succeed, None, 0, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert "alpha" in report.failed_nodes
        assert "gamma" in report.succeeded_nodes

    def test_runner_retries(self) -> None:
        self.checked.add_node("alpha", _explode, None, 0, 2)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert "alpha" in report.failed_nodes

    def test_runner_missing_dependency_error(self) -> None:
        self.checked.add_node("alpha", _succeed, ["ghost"], 0, 0)
        self.checked_runner.violating(dag_engine_lite.NodeNotFoundError).run(
            dag_engine_lite.FailurePolicy.FAIL_FAST
        )

    def test_runner_cycle_error(self) -> None:
        self.checked.add_node("a", _succeed, None, 0, 0)
        self.checked.add_node("b", _succeed, None, 0, 0)
        self.checked.add_edge("a", "b")
        self.checked.add_edge("b", "a")
        self.checked_runner.violating(dag_engine_lite.CycleError).run(
            dag_engine_lite.FailurePolicy.FAIL_FAST
        )

    def test_runner_wave_starvation_after_reattachment(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "beta"]
        self.checked.add_edge("alpha", "beta")
        self.checked_scheduler.mark_running("alpha")
        assert self.checked_scheduler.next_wave() == []
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert report.succeeded_nodes == ()
        assert report.failed_nodes == ()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T00:43:34Z
# LAST_CHANGED: 2026-11-12T00:43:10Z
# CHANGE: Added two TestDAGEngineImplReal scenarios resolving the pretense_coverage facet 'duplicate reenqueued reconvergent dependent' for dag_lite.scheduler.mark_failed.skip_downstream with witness graph_shape=fanout_cross_edge_below_dependent policy=SKIP_DOWNSTREAM. (1) test_scheduler_skip_downstream_fanout_cross_edge_below_dependent: failed root 'a' fans out to dependents 'b' and 'c'; a dependent chain b->d continues below dependent 'b', and a cross edge d->c placed BELOW dependent 'b' re-enters sibling dependent 'c', so 'c' is transitively reached from failed 'a' both directly (a->c) and via a->b->d->c after it has already been skipped, exercising the duplicate/re-enqueued reconvergent dependent path. Verifies adjacency (dependents(a)={b,c}, dependents(b)={d}, dependents(d)={c}, dependencies(c)={a,d}), then under SKIP_DOWNSTREAM asserts a FAILED and b, c, d SKIPPED with a total SKIPPED count of exactly 3 (no duplicate skip accounting) and an empty follow-up wave. (2) test_scheduler_skip_downstream_fanout_cross_edge_below_dependent_reentry: mirrored orientation a->{b,c}, c->d, cross edge d->b re-enters dependent 'b' below dependent 'c', asserting the same deduplicated SKIPPED outcome. Both scenarios assert is_finished() True.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T00:43:34Z
# PRETENSE_QA_AUDIT: 2026-11-12T00:43:21Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple

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

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib.dag_engine_lite import (
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
# 1. Model Helpers (pure functions over abstract model state)
# ==============================================================================

TERMINAL_STATES: Tuple[NodeState, ...] = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)


def _noop() -> None:
    """Default zero-argument node action used when seeding model state."""
    return None


def _dependents_map(upstream: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """Inverts an upstream dependency map into a downstream dependent map."""
    dependents: Dict[str, Set[str]] = {}
    for node_id in upstream:
        dependents.setdefault(node_id, set())
    for node_id, dependencies in upstream.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, set()).add(node_id)
    return dependents


def _has_cycle(upstream: Dict[str, Set[str]]) -> bool:
    """Detects a directed cycle with Kahn elimination over the upstream map."""
    dependents = _dependents_map(upstream)
    indegree = {node_id: len(dependencies) for node_id, dependencies in upstream.items()}
    ready = [node_id for node_id, count in indegree.items() if count == 0]
    eliminated = 0
    for _step in range(len(indegree)):
        if not ready:
            break
        current = ready.pop()
        eliminated += 1
        for dependent in dependents.get(current, set()):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    return eliminated != len(indegree)


def _transitive_dependents(downstream: Dict[str, Set[str]], node_id: str) -> Set[str]:
    """Collects all transitively reachable downstream dependents of a node."""
    found: Set[str] = set()
    frontier: List[str] = [node_id]
    for _step in range(len(downstream) + 1):
        if not frontier:
            break
        current = frontier.pop()
        for dependent in downstream.get(current, set()):
            if dependent not in found:
                found.add(dependent)
                frontier.append(dependent)
    return found


def _sync_statuses(
    nodes: Dict[str, NodeDefinition[Any]],
    upstream: Dict[str, Set[str]],
    statuses: Dict[str, NodeState],
) -> None:
    """Discovers registered nodes and initializes roots READY and others PENDING."""
    for node_id in nodes:
        if node_id not in statuses:
            if upstream.get(node_id):
                statuses[node_id] = NodeState.PENDING
            else:
                statuses[node_id] = NodeState.READY


def _priority_order(
    nodes: Dict[str, NodeDefinition[Any]], candidates: Collection[str]
) -> List[str]:
    """Orders identifiers by priority descending, then node_id ascending."""
    ranked = sorted((-nodes[node_id].priority, node_id) for node_id in candidates)
    return [node_id for _priority, node_id in ranked]


def _ready_wave(
    nodes: Dict[str, NodeDefinition[Any]],
    upstream: Dict[str, Set[str]],
    statuses: Dict[str, NodeState],
) -> List[str]:
    """Resolves the next executable wave of READY nodes with SUCCEEDED upstreams."""
    candidates: List[str] = []
    for node_id in nodes:
        if statuses.get(node_id) == NodeState.READY:
            if all(
                statuses.get(dependency) == NodeState.SUCCEEDED
                for dependency in upstream.get(node_id, set())
            ):
                candidates.append(node_id)
    return _priority_order(nodes, candidates)


def _topological_order(
    nodes: Dict[str, NodeDefinition[Any]], upstream: Dict[str, Set[str]]
) -> List[str]:
    """Computes the deterministic topological order with priority tie-breaking."""
    indegree = {
        node_id: len(upstream.get(node_id, set())) for node_id in nodes
    }
    ready = _priority_order(nodes, [node_id for node_id in nodes if indegree[node_id] == 0])
    order: List[str] = []
    for _step in range(len(nodes)):
        if not ready:
            break
        current = ready.pop(0)
        order.append(current)
        unlocked: List[str] = []
        for dependent in nodes:
            if current in upstream.get(dependent, set()):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    unlocked.append(dependent)
        ready = _priority_order(nodes, ready + unlocked)
    return order


def _critical_path(
    nodes: Dict[str, NodeDefinition[Any]],
    upstream: Dict[str, Set[str]],
    durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the model graph."""
    order = _topological_order(nodes, upstream)
    if not order:
        return ([], 0.0)
    earliest: Dict[str, float] = {}
    predecessor: Dict[str, str] = {}
    for node_id in order:
        weight = 1.0 if durations is None else float(durations.get(node_id, 1.0))
        best = 0.0
        best_predecessor: Optional[str] = None
        for dependency in sorted(upstream.get(node_id, set())):
            candidate = earliest.get(dependency, 0.0)
            if candidate > best:
                best = candidate
                best_predecessor = dependency
        earliest[node_id] = best + weight
        if best_predecessor is not None:
            predecessor[node_id] = best_predecessor
    terminal = order[0]
    for node_id in order:
        if earliest[node_id] > earliest[terminal]:
            terminal = node_id
    path: List[str] = []
    current: Optional[str] = terminal
    for _step in range(len(order) + 1):
        if current is None:
            break
        path.append(current)
        current = predecessor.get(current)
    path.reverse()
    return (path, earliest[terminal])


def _is_finished(
    nodes: Dict[str, NodeDefinition[Any]], statuses: Dict[str, NodeState]
) -> bool:
    """Reports whether no READY work remains, matching scheduler termination."""
    if not nodes:
        return True
    for node_id in nodes:
        if statuses.get(node_id) == NodeState.READY:
            return False
    return True


# ==============================================================================
# 2. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DAGEngineState:
    """Abstract model state of the DAG graph, wave scheduler, and run outcomes."""
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    statuses: Dict[str, NodeState] = field(default_factory=dict)
    outcomes: Dict[str, NodeResult[Any]] = field(default_factory=dict)


class DAGEngineStateMachine(StateMachine[DAGEngineState]):
    """Unified Pretense State Machine for the DAG engine services."""

    def __init__(
        self,
        state: Optional[DAGEngineState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineState:
        """Constructs the blank model state used by fuzzing and fake synthesis."""
        return DAGEngineState()

    # --------------------------------------------------------------------------
    # Graph transitions (DAG)
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
        require_arg(node_id, Domain.type(str), preferred=["alpha"])
        require_arg(action, Domain.any(), preferred=[_noop])
        require_arg(
            dependencies,
            Domain.type(Optional[Collection[str]]),
            preferred=[None],
        )
        require_arg(priority, Domain.integers(-3, 3), preferred=[0])
        require_arg(retries, Domain.integers(0, 2), preferred=[0])
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        dependency_set = frozenset(dependencies or ())
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self.state.upstream[node_id] = set(dependency_set)
        self.state.downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        assert node_id in self.state.nodes
        assert self.state.upstream[node_id] == set(dependency_set)
        return ret

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Computes the fake return value for add_node."""
        return None

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(upstream_id, Domain.in_set(self.state.nodes))
        require_arg(downstream_id, Domain.in_set(self.state.nodes))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Computes the fake return value for add_edge."""
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_remove_node(node_id)
        removed_upstream = self.state.upstream.pop(node_id, set())
        for dependency in removed_upstream:
            self.state.downstream.get(dependency, set()).discard(node_id)
        removed_downstream = self.state.downstream.pop(node_id, set())
        for dependent in removed_downstream:
            self.state.upstream.get(dependent, set()).discard(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.statuses.pop(node_id, None)
        self.state.outcomes.pop(node_id, None)
        assert node_id not in self.state.nodes
        assert node_id not in self.state.upstream
        assert node_id not in self.state.downstream
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        """Computes the fake return value for remove_node."""
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.type(str))
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        """Computes the fake return value for has_node."""
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_get_node(node_id)
        assert ret == self.state.nodes[node_id]
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Computes the fake return value for get_node."""
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        """Computes the fake return value for get_dependencies."""
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_get_dependents(node_id)
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        """Computes the fake return value for get_dependents."""
        return set(self.state.downstream.get(node_id, set()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    def inner_all_nodes(self) -> Set[str]:
        """Computes the fake return value for all_nodes."""
        return set(self.state.nodes)

    @transition(DAG.validate)
    def validate(self) -> None:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        require(not _has_cycle(self.state.upstream))
        ret = self.inner_validate()
        assert all(
            dependency in self.state.nodes
            for dependencies in self.state.upstream.values()
            for dependency in dependencies
        )
        return ret

    def inner_validate(self) -> None:
        """Computes the fake return value for validate."""
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(not _has_cycle(self.state.upstream))
        ret = self.inner_topological_sort()
        assert len(ret) == len(self.state.nodes)
        assert set(ret) == set(self.state.nodes)
        assert all(
            self.state.upstream.get(ret[position], set()).issubset(set(ret[:position]))
            for position in range(len(ret))
        )
        return ret

    def inner_topological_sort(self) -> List[str]:
        """Computes the fake return value for topological_sort."""
        return _topological_order(self.state.nodes, self.state.upstream)

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        assert ret == {
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)
        }
        return ret

    def inner_find_roots(self) -> Set[str]:
        """Computes the fake return value for find_roots."""
        return {
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)
        }

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        assert ret == {
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)
        }
        return ret

    def inner_find_leaves(self) -> Set[str]:
        """Computes the fake return value for find_leaves."""
        return {
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)
        }

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        require(not _has_cycle(self.state.upstream))
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
            preferred=[None],
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        path, weight = ret
        assert weight >= 0.0
        assert all(node_id in self.state.nodes for node_id in path)
        assert all(
            path[position + 1] in self.state.downstream.get(path[position], set())
            for position in range(len(path) - 1)
        )
        return ret

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        """Computes the fake return value for compute_critical_path."""
        return _critical_path(self.state.nodes, self.state.upstream, estimated_durations)

    # --------------------------------------------------------------------------
    # Scheduler transitions (WaveScheduler)
    # --------------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        _sync_statuses(self.state.nodes, self.state.upstream, self.state.statuses)
        ret = self.inner_next_wave()
        assert ret == _ready_wave(self.state.nodes, self.state.upstream, self.state.statuses)
        return ret

    def inner_next_wave(self) -> List[str]:
        """Computes the fake return value for next_wave."""
        return _ready_wave(self.state.nodes, self.state.upstream, self.state.statuses)

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_mark_running(node_id)
        self.state.statuses[node_id] = NodeState.RUNNING
        assert self.state.statuses[node_id] == NodeState.RUNNING
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        """Computes the fake return value for mark_running."""
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_mark_succeeded(node_id)
        self.state.statuses[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            if self.state.statuses.get(dependent) == NodeState.PENDING:
                if all(
                    self.state.statuses.get(dependency) == NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(dependent, set())
                ):
                    self.state.statuses[dependent] = NodeState.READY
        assert self.state.statuses[node_id] == NodeState.SUCCEEDED
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Computes the fake return value for mark_succeeded."""
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[FailurePolicy.FAIL_FAST],
        )
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.statuses[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other in self.state.nodes:
                if self.state.statuses.get(other) not in TERMINAL_STATES:
                    self.state.statuses[other] = NodeState.CANCELLED
        else:
            for dependent in _transitive_dependents(self.state.downstream, node_id):
                if self.state.statuses.get(dependent) not in TERMINAL_STATES:
                    self.state.statuses[dependent] = NodeState.SKIPPED
        assert self.state.statuses[node_id] == NodeState.FAILED
        return ret

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Computes the fake return value for mark_failed."""
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        _sync_statuses(self.state.nodes, self.state.upstream, self.state.statuses)
        ret = self.inner_is_finished()
        if not self.state.nodes:
            assert ret
        if all(
            self.state.statuses.get(node_id) in TERMINAL_STATES
            for node_id in self.state.nodes
        ):
            assert ret
        return ret

    def inner_is_finished(self) -> bool:
        """Computes the fake return value for is_finished."""
        return _is_finished(self.state.nodes, self.state.statuses)

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        _sync_statuses(self.state.nodes, self.state.upstream, self.state.statuses)
        ret = self.inner_get_state(node_id)
        assert ret == self.state.statuses[node_id]
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        """Computes the fake return value for get_state."""
        return self.state.statuses[node_id]

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        _sync_statuses(self.state.nodes, self.state.upstream, self.state.statuses)
        ret = self.inner_get_all_states()
        assert set(ret) == set(self.state.nodes)
        assert all(
            ret[node_id] == self.state.statuses[node_id] for node_id in self.state.nodes
        )
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        """Computes the fake return value for get_all_states."""
        return {
            node_id: self.state.statuses[node_id] for node_id in self.state.nodes
        }

    # --------------------------------------------------------------------------
    # Runner transition (DAGRunner)
    # --------------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        require(not _has_cycle(self.state.upstream))
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[FailurePolicy.FAIL_FAST],
        )
        ret = self.inner_run(failure_policy)
        assert ret.total_nodes == len(self.state.nodes)
        assert ret.wall_clock_seconds >= 0.0
        assert all(node_id in self.state.nodes for node_id in ret.succeeded_nodes)
        assert all(node_id in self.state.nodes for node_id in ret.failed_nodes)
        assert all(node_id in self.state.nodes for node_id in ret.skipped_nodes)
        assert all(node_id in self.state.nodes for node_id in ret.cancelled_nodes)
        for node_id in self.state.nodes:
            if node_id in ret.results:
                self.state.statuses[node_id] = ret.results[node_id].state
                self.state.outcomes[node_id] = ret.results[node_id]
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Computes the fake return value for run."""
        results: Dict[str, NodeResult[Any]] = {
            node_id: NodeResult(node_id=node_id, state=NodeState.SUCCEEDED)
            for node_id in self.state.nodes
        }
        path, _weight = _critical_path(self.state.nodes, self.state.upstream, None)
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(sorted(self.state.nodes)),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=results,
        )

    # --------------------------------------------------------------------------
    # Seeding transitions
    # --------------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a minimal two node chain so fuzzing can reach stateful rules."""
        self.state.nodes["seed_a"] = NodeDefinition(
            node_id="seed_a",
            action=_noop,
            dependencies=frozenset(),
            priority=0,
            retries=0,
        )
        self.state.nodes["seed_b"] = NodeDefinition(
            node_id="seed_b",
            action=_noop,
            dependencies=frozenset({"seed_a"}),
            priority=0,
            retries=0,
        )
        self.state.upstream["seed_a"] = set()
        self.state.upstream["seed_b"] = {"seed_a"}
        self.state.downstream["seed_a"] = {"seed_b"}
        self.state.downstream["seed_b"] = set()
        self.state.statuses.clear()
        self.state.outcomes.clear()


proto = DAGEngineStateMachine()


# ==============================================================================
# 3. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngine = synthesize_fake(DAGEngineStateMachine)


def make_dag_engine_fake(state: Optional[DAGEngineState] = None) -> Any:
    """Synthesizes a fake instance for the DAG engine services."""
    return FakeDAGEngine(state=state or proto.make_initial_state())


# Fake Fuzzing (Exercises synthesized fake against state machine contracts):
FakeDAGEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineFuzzTest",
)


# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestDAGEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_fake()
        self.sm = DAGEngineStateMachine()

    def test_seed_initial(self) -> None:
        self.sm.seed_initial()
        assert len(self.sm.state.nodes) == 2

    def test_graph_queries(self) -> None:
        self.fake.add_node("alpha", _noop, None, 1, 0)
        assert self.fake.has_node("alpha")
        assert self.fake.get_node("alpha").node_id == "alpha"
        assert self.fake.get_dependencies("alpha") == set()
        assert self.fake.get_dependents("alpha") == set()
        assert self.fake.all_nodes() == {"alpha"}
        assert self.fake.find_roots() == {"alpha"}
        assert self.fake.find_leaves() == {"alpha"}
        self.fake.validate()
        assert self.fake.topological_sort() == ["alpha"]

    def test_graph_edges(self) -> None:
        self.fake.add_node("alpha", _noop, None, 1, 0)
        self.fake.add_node("beta", _noop, None, 0, 0)
        self.fake.add_edge("alpha", "beta")
        assert self.fake.get_dependencies("beta") == {"alpha"}
        assert self.fake.get_dependents("alpha") == {"beta"}
        assert self.fake.topological_sort() == ["alpha", "beta"]
        self.fake.remove_node("beta")
        assert self.fake.all_nodes() == {"alpha"}
        assert self.fake.get_dependents("alpha") == set()

    def test_critical_path(self) -> None:
        self.fake.add_node("alpha", _noop, None, 0, 0)
        self.fake.add_node("beta", _noop, ["alpha"], 0, 0)
        path, weight = self.fake.compute_critical_path(None)
        assert path == ["alpha", "beta"]
        assert weight == 2.0

    def test_scheduler_success(self) -> None:
        self.fake.add_node("alpha", _noop, None, 0, 0)
        self.fake.add_node("beta", _noop, ["alpha"], 0, 0)
        assert self.fake.next_wave() == ["alpha"]
        self.fake.mark_running("alpha")
        assert self.fake.get_state("alpha") == NodeState.RUNNING
        self.fake.mark_succeeded("alpha")
        assert self.fake.next_wave() == ["beta"]
        self.fake.mark_running("beta")
        self.fake.mark_succeeded("beta")
        assert self.fake.get_all_states()["beta"] == NodeState.SUCCEEDED
        assert self.fake.is_finished()

    def test_scheduler_fail_fast(self) -> None:
        self.fake.add_node("alpha", _noop, None, 0, 0)
        self.fake.add_node("beta", _noop, ["alpha"], 0, 0)
        self.fake.next_wave()
        self.fake.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        assert self.fake.get_all_states()["beta"] == NodeState.CANCELLED

    def test_scheduler_skip_downstream(self) -> None:
        self.fake.add_node("alpha", _noop, None, 0, 0)
        self.fake.add_node("beta", _noop, ["alpha"], 0, 0)
        self.fake.next_wave()
        self.fake.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.fake.get_all_states()["beta"] == NodeState.SKIPPED

    def test_scheduler_continue_on_error(self) -> None:
        self.fake.add_node("alpha", _noop, None, 0, 0)
        self.fake.add_node("beta", _noop, ["alpha"], 0, 0)
        self.fake.next_wave()
        self.fake.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.fake.get_all_states()["beta"] == NodeState.SKIPPED

    def test_runner(self) -> None:
        self.fake.add_node("alpha", _noop, None, 0, 0)
        self.fake.add_node("beta", _noop, ["alpha"], 0, 0)
        report = self.fake.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert set(report.results) == {"alpha", "beta"}

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T00:17:30Z
# LAST_CHANGED: 2026-11-12T00:17:30Z
# CHANGE: Implemented the interface pretense state machine for the DAG engine: DAGEngineState model over graph/upstream/downstream/statuses/outcomes, one 1:1 transition per DAG, WaveScheduler, and DAGRunner operation with require/require_arg preconditions and contract assertions, synthesize_fake plus fake factory, TestDAGEngineFake covering every transition and seeding transition, and a compiled FakeDAGEngineFuzzTest.
# --- END AUTOFAB METADATA ---
