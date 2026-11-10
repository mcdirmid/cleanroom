# === File: dag_engine_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngine."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from pretense import (
    call_target,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGTimeoutError,
    DAG as DAGInterface,
    DAGRunner as DAGRunnerInterface,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
    WaveScheduler as WaveSchedulerInterface,
)
from benchmark_3.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_initialize,
)
from benchmark_3.parts.dag_engine.pretense.dag_engine_pretense import (
    DagEngineState,
    DagEngineStateMachine,
    failing_action,
    noop_action,
    value_action,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# The pseudo-state machine inherits the interface model (preconditions and model
# state mutations) and overrides the transitions that require observing the real
# system under test through call_target.

def _bind_service_instances(
    registry: LifecycleRegistry,
    dag: DAG,
    scheduler: WaveScheduler,
    runner: DAGRunner,
) -> None:
    """Registers the seeded service instances so every collaborator lookup agrees."""
    registry.register_instance(dag, keys=[DAG, DAGInterface], tier=system)
    registry.register_instance(scheduler, keys=[WaveScheduler, WaveSchedulerInterface], tier=system)
    registry.register_instance(runner, keys=[DAGRunner, DAGRunnerInterface], tier=system)

class DagEngineImplPseudoStateMachine(DagEngineStateMachine):
    """Implementation pseudo-state machine for the DAG engine services."""

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, timeout_seconds, retries))
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
        assert downstream_id in target.get_dependents(upstream_id)
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
        assert isinstance(ret, bool)
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
        assert all(dependency in target.all_nodes() for dependency in ret)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        assert all(dependent in target.all_nodes() for dependent in ret)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert all(target.has_node(node) for node in ret)
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
        assert len(ret) == len(target.all_nodes())
        positions = {node: index for index, node in enumerate(ret)}
        assert all(
            positions[dependency] < positions[node]
            for node in ret
            for dependency in target.get_dependencies(node)
        )
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        assert all(not target.get_dependencies(node) for node in ret)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        assert all(not target.get_dependents(node) for node in ret)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        assert all(node in target.all_nodes() for node in ret[0])
        assert isinstance(ret[1], float)
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        assert all(target.get_state(node) == NodeState.READY for node in ret)
        assert len(set(ret)) == len(ret)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        assert target.get_state(node_id) == NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        assert target.get_state(node_id) == NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert target.get_state(node_id) == NodeState.FAILED
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
        assert all(isinstance(state, NodeState) for state in ret.values())
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(timeout_seconds, failure_policy, max_concurrency))
        assert ret.total_nodes >= len(ret.results)
        terminal_nodes = (
            len(ret.succeeded_nodes)
            + len(ret.failed_nodes)
            + len(ret.skipped_nodes)
            + len(ret.cancelled_nodes)
        )
        assert terminal_nodes <= ret.total_nodes
        assert ret.wall_clock_seconds >= 0.0
        return ret

    @transition(DAGRunner.cancel)
    def cancel(
        self,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.cancel())
        assert target.is_cancelled()
        return ret

    @transition(DAGRunner.is_cancelled)
    def is_cancelled(
        self,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.is_cancelled())
        assert isinstance(ret, bool)
        return ret


proto = DagEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineImplReal(unittest.TestCase):
    """Verifies that the concrete DAG engine implementations satisfy their contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        _bind_service_instances(self.registry, self.dag, self.wavescheduler, self.dagrunner)
        self.sm = DagEngineImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.wavescheduler, DAGRunner: self.dagrunner}
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_graph_construction(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", value_action, ["a"], 1, None, 0)
        self.checked_dag.add_node("c", noop_action, ["b"], 0, None, 0)
        self.assertTrue(self.checked_dag.has_node("a"))
        self.assertFalse(self.checked_dag.has_node("missing"))
        self.assertEqual(self.checked_dag.get_node("b").node_id, "b")
        self.assertEqual(self.checked_dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.checked_dag.get_dependents("b"), {"c"})
        self.assertEqual(self.checked_dag.all_nodes(), {"a", "b", "c"})
        self.assertEqual(self.checked_dag.find_roots(), {"a"})
        self.assertEqual(self.checked_dag.find_leaves(), {"c"})
        self.checked_dag.validate()
        self.assertEqual(self.checked_dag.topological_sort(), ["a", "b", "c"])

    def test_edges_and_removal(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, None, 0)
        self.checked_dag.add_edge("a", "b")
        self.assertEqual(self.checked_dag.get_dependents("a"), {"b"})
        self.assertEqual(self.checked_dag.get_dependencies("b"), {"a"})
        self.checked_dag.remove_node("b")
        self.assertFalse(self.checked_dag.has_node("b"))
        self.assertEqual(self.checked_dag.get_dependents("a"), set())
        self.assertEqual(self.checked_dag.find_leaves(), {"a"})

    def test_critical_path(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.checked_dag.add_node("c", noop_action, ["b"], 0, None, 0)
        self.assertEqual(self.checked_dag.compute_critical_path(None), (["a", "b", "c"], 3.0))
        self.assertEqual(
            self.checked_dag.compute_critical_path({"a": 1.0, "b": 5.0, "c": 1.0}),
            (["a", "b", "c"], 7.0),
        )

    def test_wave_scheduling(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 5, None, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.checked_scheduler.mark_running("a")
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.RUNNING)
        self.checked_scheduler.mark_succeeded("a")
        self.assertEqual(self.checked_scheduler.next_wave(), ["b"])
        self.assertFalse(self.checked_scheduler.is_finished())
        self.assertEqual(
            dict(self.checked_scheduler.get_all_states()),
            {"a": NodeState.SUCCEEDED, "b": NodeState.READY},
        )
        self.checked_scheduler.mark_succeeded("b")
        self.assertTrue(self.checked_scheduler.is_finished())

    def test_failure_policy_skip_downstream(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.SKIPPED)

    def test_failure_policy_fail_fast(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, None, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.CANCELLED)

    def test_failure_policy_continue_on_error(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, None, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.READY)

    def test_runner_execution(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", value_action, ["a"], 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(tuple(report.critical_path), ("a", "b"))
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertTrue(self.checked_scheduler.is_finished())
        self.assertFalse(self.checked_runner.is_cancelled())

    def test_runner_failure_report(self) -> None:
        self.checked_dag.add_node("a", failing_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.FAIL_FAST, 1)
        self.assertEqual(report.total_nodes, 2)
        self.assertIn("a", report.failed_nodes)

    def test_runner_cancel(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_scheduler.next_wave()
        self.checked_runner.cancel()
        self.assertTrue(self.checked_runner.is_cancelled())
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.CANCELLED)

    # ---- Degenerate graph scenarios -------------------------------------------

    def test_empty_graph_scenarios(self) -> None:
        self.assertTrue(self.checked_scheduler.is_finished())
        self.assertEqual(self.checked_dag.all_nodes(), set())
        self.assertEqual(self.checked_dag.find_roots(), set())
        self.assertEqual(self.checked_dag.find_leaves(), set())
        self.assertEqual(self.checked_dag.topological_sort(), [])
        self.checked_dag.validate()
        self.assertEqual(dict(self.checked_scheduler.get_all_states()), {})
        self.assertEqual(self.checked_scheduler.next_wave(), [])
        self.assertEqual(self.dag.compute_critical_path(None), ([], 0.0))
        self.assertEqual(self.dag.compute_critical_path({}), ([], 0.0))

    def test_removal_with_dependents(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 0, None, 0)
        self.checked_dag.remove_node("a")
        self.assertEqual(self.checked_dag.all_nodes(), {"b", "c"})
        self.assertEqual(self.checked_dag.find_roots(), {"b", "c"})
        self.assertEqual(self.checked_dag.find_leaves(), {"b", "c"})
        self.assertEqual(self.checked_dag.get_dependencies("b"), set())
        self.assertEqual(self.checked_dag.get_dependencies("c"), set())
        self.assertEqual(self.checked_scheduler.next_wave(), ["b", "c"])
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.checked_scheduler.get_state("c"), NodeState.READY)

    def test_removal_observation_sequence(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 0, None, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.assertEqual(
            dict(self.checked_scheduler.get_all_states()),
            {"a": NodeState.READY, "b": NodeState.PENDING, "c": NodeState.PENDING},
        )
        self.checked_dag.remove_node("a")
        self.assertEqual(self.checked_scheduler.next_wave(), ["b", "c"])
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.checked_scheduler.get_state("c"), NodeState.READY)
        self.assertNotIn("a", dict(self.checked_scheduler.get_all_states()))

    def test_removed_node_state_and_incarnation_purge(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_scheduler.mark_succeeded("a")
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.checked_dag.remove_node("a")
        self.assertEqual(self.checked_scheduler.next_wave(), [])
        self.assertEqual(dict(self.checked_scheduler.get_all_states()), {})
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.assertEqual(self.checked_scheduler.get_state("a"), NodeState.READY)

    def test_late_edge_readiness_demotion(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, None, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["a", "b"])
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.READY)
        self.checked_dag.add_edge("a", "b")
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.PENDING)
        self.checked_scheduler.mark_succeeded("a")
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.checked_scheduler.next_wave(), ["b"])

    def test_runner_blocked_dependent_termination(self) -> None:
        self.dag.add_node("a", failing_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, ["a"], 0, None, 0)
        report = self.dagrunner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)
        self.assertEqual(report.total_nodes, 2)
        self.assertIn("a", report.failed_nodes)
        self.assertEqual(list(self.wavescheduler.next_wave()), [])
        self.assertNotEqual(self.wavescheduler.get_state("b"), NodeState.SUCCEEDED)
        self.assertFalse(self.wavescheduler.is_finished())

    def test_late_prerequisite_readiness(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, None, 0, None, 0)
        self.checked_dag.add_edge("a", "b")
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.checked_scheduler.mark_succeeded("a")
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.checked_scheduler.next_wave(), ["b"])
        self.checked_scheduler.mark_succeeded("b")
        self.assertTrue(self.checked_scheduler.is_finished())

    def test_already_nonpending_dependent(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.checked_scheduler.mark_succeeded("b")
        self.checked_scheduler.mark_succeeded("a")
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.SUCCEEDED)
        self.assertTrue(self.checked_scheduler.is_finished())

    def test_blocked_wave_termination(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.checked_scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.checked_scheduler.next_wave(), [])
        self.assertFalse(self.checked_scheduler.is_finished())

    def test_transitive_skip_diamond(self) -> None:
        self.checked_dag.add_node("a", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.checked_dag.add_node("c", noop_action, ["a"], 0, None, 0)
        self.checked_dag.add_node("d", noop_action, ["b", "c"], 0, None, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["a"])
        self.checked_scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.checked_scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.checked_scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.checked_scheduler.get_state("d"), NodeState.SKIPPED)
        self.assertTrue(self.checked_scheduler.is_finished())

    def test_runner_retry_failures(self) -> None:
        self.checked_dag.add_node("a", failing_action, None, 0, None, 2)
        report = self.checked_runner.run(None, FailurePolicy.FAIL_FAST, 1)
        self.assertEqual(report.total_nodes, 1)
        self.assertIn("a", report.failed_nodes)
        self.assertEqual(report.results["a"].retries_attempted, 2)

    # ---- Contract violation and recovery scenarios ----------------------------

    def test_missing_node_contract_errors(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "other")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")
        self.assertEqual(self.dag.all_nodes(), {"a"})
        self.dag.add_node("b", noop_action, None, 0, None, 0)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_missing_dependency_validation_error(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_node("b", noop_action, ["missing"], 0, None, 0)
            self.dag.validate()

    def test_cycle_contract_errors(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, None, 0, None, 0)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()
        self.dag.remove_node("b")
        self.dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.dag.validate()
        self.assertEqual(self.dag.topological_sort(), ["a", "b"])

    def test_runner_timeout_error(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        with self.assertRaises(DAGTimeoutError):
            self.dagrunner.run(1e-06, FailurePolicy.CONTINUE_ON_ERROR, 1)

    def test_runner_cancellation_error(self) -> None:
        self.dag.add_node("a", self._cancel_then_add_node, None, 0, None, 0)
        with self.assertRaises(DAGCancelledError):
            self.dagrunner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)
        self.assertTrue(self.dagrunner.is_cancelled())

    def _cancel_then_add_node(self) -> None:
        """Cancels the runner and then registers a fresh unstarted node."""
        self.dagrunner.cancel()
        self.dag.add_node("late", noop_action, None, 0, None, 0)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineSUT:
    """Aggregate SUT exposing component services for DAG engine state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        _bind_service_instances(self.registry, self.dag, self.wavescheduler, self.dagrunner)
        self.__dict__["_services"] = (self.dag, self.wavescheduler, self.dagrunner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def close(self) -> None:
        self.phase_scope.__exit__(None, None, None)


def make_sut() -> DagEngineSUT:
    return DagEngineSUT()


DagEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineState,
    name="DagEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:36:04Z
# LAST_CHANGED: 2026-11-08T17:35:29Z
# CHANGE: Keep the out-of-band runner scenario fully raw so model and SUT never desynchronize: test_runner_blocked_dependent_termination now seeds the graph through the raw DAG, executes the raw DAGRunner.run under CONTINUE_ON_ERROR, and makes all post-run observations (next_wave, get_state, is_finished) against the raw WaveScheduler instead of the model-backed checked proxy. Audited every other scenario using raw SUT calls to confirm they either perform no SUT mutation or make no subsequent checked model-backed assertions.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:36:04Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:35:42Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast
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
from benchmark_3.parts.dag_engine.lib.dag_engine import (
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
# transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).
# require gates caller dispatch on model state only (PN009).

_TERMINAL_STATES: FrozenSet[NodeState] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)

_FAILURE_POLICIES: List[FailurePolicy] = [
    FailurePolicy.FAIL_FAST,
    FailurePolicy.CONTINUE_ON_ERROR,
    FailurePolicy.SKIP_DOWNSTREAM,
]


def noop_action() -> None:
    """Zero-argument action that succeeds without a value."""
    return None


def value_action() -> int:
    """Zero-argument action that succeeds with a constant value."""
    return 1


def failing_action() -> None:
    """Zero-argument action that raises so failure handling can be exercised."""
    raise RuntimeError("simulated node action failure")


def _topological_order(state: DagEngineState) -> List[str]:
    """Computes a deterministic topological order using the documented tie-break."""
    in_degree: Dict[str, int] = {
        node: len([dependency for dependency in state.upstream.get(node, set()) if dependency in state.nodes])
        for node in state.nodes
    }
    ready: List[str] = [node for node in state.nodes if in_degree[node] == 0]
    ready = [
        ranked_node
        for _priority, ranked_node in sorted((-state.nodes[node].priority, node) for node in ready)
    ]
    order: List[str] = []
    for _ in range(len(state.nodes) + 1):
        if not ready:
            break
        node = ready.pop(0)
        order.append(node)
        for dependent in state.downstream.get(node, set()):
            if dependent not in in_degree:
                continue
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
        ready = [
            ranked_node
            for _priority, ranked_node in sorted((-state.nodes[item].priority, item) for item in ready)
        ]
    return order


def _critical_path(
    state: DagEngineState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the model graph."""
    order = _topological_order(state)
    completion: Dict[str, float] = {}
    predecessor: Dict[str, Optional[str]] = {}
    for node in order:
        weight = 1.0
        if estimated_durations is not None:
            weight = estimated_durations.get(node, 1.0)
        best_value = 0.0
        best_node: Optional[str] = None
        for dependency in state.upstream.get(node, set()):
            if dependency not in completion:
                continue
            if completion[dependency] > best_value:
                best_value = completion[dependency]
                best_node = dependency
        completion[node] = best_value + weight
        predecessor[node] = best_node
    tail: Optional[str] = None
    tail_value = 0.0
    for node in order:
        if tail is None or completion[node] > tail_value:
            tail = node
            tail_value = completion[node]
    path: List[str] = []
    current = tail
    for _ in range(len(order) + 1):
        if current is None:
            break
        path.append(current)
        current = predecessor.get(current)
    path.reverse()
    return path, tail_value


def _transitive_dependents(state: DagEngineState, node_id: str) -> Set[str]:
    """Collects every node transitively dependent on a node."""
    dependents: Set[str] = set()
    frontier: Set[str] = {node_id}
    for _ in range(len(state.nodes) + 1):
        if not frontier:
            break
        next_frontier: Set[str] = set()
        for node in frontier:
            for dependent in state.downstream.get(node, set()):
                if dependent in dependents:
                    continue
                dependents.add(dependent)
                next_frontier.add(dependent)
        frontier = next_frontier
    return dependents


@dataclass
class DagEngineState:
    """Canonical model state for the DAG execution and wave scheduling engine."""
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    cancelled: bool = False


def _reconcile_readiness(state: DagEngineState, node_id: str) -> None:
    """Classifies a non-terminal node as READY only when every prerequisite is satisfied."""
    if state.node_states.get(node_id) not in {NodeState.PENDING, NodeState.READY}:
        return
    if all(
        state.node_states.get(dependency) == NodeState.SUCCEEDED
        for dependency in state.upstream.get(node_id, set())
    ):
        state.node_states[node_id] = NodeState.READY
    else:
        state.node_states[node_id] = NodeState.PENDING


class DagEngineStateMachine(StateMachine[DagEngineState]):
    """Unified Pretense State Machine for the DAG engine services."""

    def __init__(
        self,
        state: Optional[DagEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineState(), singletons=singletons)

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        require_arg(node_id, Domain.type(str))
        require_arg(action, Domain.sampled_from([noop_action, value_action, failing_action]))
        require_arg(
            dependencies,
            cast(
                "Domain[Optional[Collection[str]]]",
                Domain.optional(Domain.list_of(Domain.in_set(set(self.state.nodes.keys())))),
            ),
        )
        require_arg(priority, Domain.type(int))
        require_arg(timeout_seconds, Domain.sampled_from([None, 30.0, 300.0]))
        require_arg(retries, Domain.range(0, 3))
        registered_dependencies: FrozenSet[str] = frozenset(dependencies or ())
        definition: NodeDefinition[Any] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=registered_dependencies,
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in registered_dependencies:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        if node_id not in self.state.node_states:
            self.state.node_states[node_id] = NodeState.PENDING
        _reconcile_readiness(self.state, node_id)
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require_arg(upstream_id, Domain.in_set(set(self.state.nodes.keys())))
        require_arg(downstream_id, Domain.in_set(set(self.state.nodes.keys())))
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        _reconcile_readiness(self.state, downstream_id)
        assert downstream_id in self.state.downstream[upstream_id]
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        dependents = set(self.state.downstream.get(node_id, set()))
        for dependency in self.state.upstream.get(node_id, set()):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in dependents:
            self.state.upstream.get(dependent, set()).discard(node_id)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.nodes.pop(node_id, None)
        self.state.node_states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        for dependent in dependents:
            _reconcile_readiness(self.state, dependent)
        assert node_id not in self.state.nodes
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require_arg(node_id, Domain.type(str))
        present = node_id in self.state.nodes
        ret: bool = make_return_value(present)
        assert ret == present
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        definition = self.state.nodes[node_id]
        ret: NodeDefinition[Any] = make_return_value(definition)
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        dependencies = set(self.state.upstream.get(node_id, set()))
        ret: Set[str] = make_return_value(dependencies)
        assert ret == dependencies
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        dependents = set(self.state.downstream.get(node_id, set()))
        ret: Set[str] = make_return_value(dependents)
        assert ret == dependents
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        known = set(self.state.nodes.keys())
        ret: Set[str] = make_return_value(known)
        assert ret == known
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        order = _topological_order(self.state)
        require(len(order) == len(self.state.nodes))
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        order = _topological_order(self.state)
        require(len(order) == len(self.state.nodes))
        ret: List[str] = make_return_value(order)
        assert ret == order
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        roots = {node for node in self.state.nodes if not self.state.upstream.get(node, set())}
        ret: Set[str] = make_return_value(roots)
        assert ret == roots
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        leaves = {node for node in self.state.nodes if not self.state.downstream.get(node, set())}
        ret: Set[str] = make_return_value(leaves)
        assert ret == leaves
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(len(self.state.nodes) > 0)
        order = _topological_order(self.state)
        require(len(order) == len(self.state.nodes))
        require_arg(
            estimated_durations,
            cast(
                "Domain[Optional[Mapping[str, float]]]",
                Domain.optional(Domain.mapping_of(Domain.type(str), Domain.type(float))),
            ),
        )
        path, weight = _critical_path(self.state, estimated_durations)
        ret: Tuple[List[str], float] = make_return_value((path, weight))
        assert ret[1] == weight
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        wave = [
            node
            for node in self.state.nodes
            if self.state.node_states.get(node) == NodeState.READY
            and all(
                self.state.node_states.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(node, set())
            )
        ]
        wave = [
            ranked_node
            for _priority, ranked_node in sorted((-self.state.nodes[node].priority, node) for node in wave)
        ]
        ret: List[str] = make_return_value(wave)
        assert ret == wave
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        self.state.node_states[node_id] = NodeState.RUNNING
        ret = make_return_value()
        assert self.state.node_states.get(node_id) == NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            if self.state.node_states.get(dependent) != NodeState.PENDING:
                continue
            if all(
                self.state.node_states.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(dependent, set())
            ):
                self.state.node_states[dependent] = NodeState.READY
        ret = make_return_value()
        assert self.state.node_states.get(node_id) == NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        require_arg(failure_policy, Domain.sampled_from(_FAILURE_POLICIES))
        self.state.node_states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.SKIP_DOWNSTREAM:
            for dependent in _transitive_dependents(self.state, node_id):
                if self.state.node_states.get(dependent) not in _TERMINAL_STATES:
                    self.state.node_states[dependent] = NodeState.SKIPPED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for node in self.state.nodes:
                if self.state.node_states.get(node) not in _TERMINAL_STATES:
                    self.state.node_states[node] = NodeState.CANCELLED
        ret = make_return_value()
        assert self.state.node_states.get(node_id) == NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        finished = all(
            self.state.node_states.get(node) in _TERMINAL_STATES for node in self.state.nodes
        )
        ret: bool = make_return_value(finished)
        assert ret == finished
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require_arg(node_id, Domain.in_set(set(self.state.nodes.keys())))
        current = self.state.node_states.get(node_id, NodeState.PENDING)
        ret: NodeState = make_return_value(current)
        assert ret == current
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        current: Mapping[str, NodeState] = {
            node: self.state.node_states.get(node, NodeState.PENDING) for node in self.state.nodes
        }
        ret: Mapping[str, NodeState] = make_return_value(current)
        assert ret == current
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        require(not self.state.cancelled)
        require(len(self.state.nodes) > 0)
        require(
            all(
                self.state.node_states.get(node) in {NodeState.PENDING, NodeState.READY}
                for node in self.state.nodes
            )
        )
        require(
            all(
                self.state.upstream.get(node, set())
                for node in self.state.nodes
                if self.state.node_states.get(node) == NodeState.PENDING
            )
        )
        order = _topological_order(self.state)
        require(len(order) == len(self.state.nodes))
        allowed_policies = [
            policy
            for policy in _FAILURE_POLICIES
            if policy is not FailurePolicy.CONTINUE_ON_ERROR
            or all(
                definition.action is not failing_action
                for definition in self.state.nodes.values()
            )
        ]
        require_arg(timeout_seconds, Domain.sampled_from([None, 30.0, 300.0]))
        require_arg(failure_policy, Domain.sampled_from(allowed_policies))
        require_arg(max_concurrency, Domain.range(1, 8))
        succeeded: List[str] = []
        for node in order:
            definition = self.state.nodes[node]
            self.state.node_states[node] = NodeState.SUCCEEDED
            self.state.results[node] = NodeResult(
                node_id=node,
                state=NodeState.SUCCEEDED,
                value=None,
                error=None,
                duration_seconds=0.0,
                retries_attempted=definition.retries,
            )
            succeeded.append(node)
        path, _weight = _critical_path(self.state, None)
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(succeeded),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=dict(self.state.results),
        )
        ret: DAGRunReport = make_return_value(report)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    @transition(DAGRunner.cancel)
    def cancel(
        self,
    ) -> None:
        self.state.cancelled = True
        for node in self.state.nodes:
            if self.state.node_states.get(node) not in _TERMINAL_STATES:
                self.state.node_states[node] = NodeState.CANCELLED
        ret = make_return_value()
        assert self.state.cancelled
        return ret

    @transition(DAGRunner.is_cancelled)
    def is_cancelled(
        self,
    ) -> bool:
        cancelled = self.state.cancelled
        ret: bool = make_return_value(cancelled)
        assert ret == cancelled
        return ret


proto = DagEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngine = synthesize_fake(DagEngineStateMachine)


def make_dag_engine_fakes(
    state: Optional[DagEngineState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes a fake exposing every DAG engine service over one model state."""
    fake = FakeDagEngine(state=state or DagEngineState())
    return (cast(DAG, fake), cast(WaveScheduler, fake), cast(DAGRunner, fake))


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        self.dag, self.scheduler, self.runner = make_dag_engine_fakes()

    def test_graph_construction(self) -> None:
        self.dag.add_node("root", noop_action, None, 0, None, 0)
        self.dag.add_node("leaf", value_action, ["root"], 5, None, 1)
        self.assertTrue(self.dag.has_node("root"))
        self.assertFalse(self.dag.has_node("missing"))
        self.assertEqual(self.dag.get_node("leaf").node_id, "leaf")
        self.assertEqual(self.dag.get_dependencies("leaf"), {"root"})
        self.assertEqual(self.dag.get_dependents("root"), {"leaf"})
        self.assertEqual(self.dag.all_nodes(), {"root", "leaf"})
        self.assertEqual(self.dag.find_roots(), {"root"})
        self.assertEqual(self.dag.find_leaves(), {"leaf"})
        self.dag.validate()
        self.assertEqual(self.dag.topological_sort(), ["root", "leaf"])

    def test_edges_and_removal(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, None, 0, None, 0)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.scheduler.get_state("b"), NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("b"), NodeState.READY)
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.find_leaves(), {"a"})

    def test_critical_path(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.dag.add_node("c", noop_action, ["b"], 0, None, 0)
        self.assertEqual(self.dag.compute_critical_path(None), (["a", "b", "c"], 3.0))
        self.assertEqual(
            self.dag.compute_critical_path({"a": 1.0, "b": 5.0, "c": 1.0}),
            (["a", "b", "c"], 7.0),
        )

    def test_scheduler_waves(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.next_wave(), [])
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.next_wave(), ["b"])
        self.assertEqual(self.scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(
            self.scheduler.get_all_states(),
            {"a": NodeState.SUCCEEDED, "b": NodeState.READY},
        )
        self.assertFalse(self.scheduler.is_finished())
        self.scheduler.mark_succeeded("b")
        self.assertTrue(self.scheduler.is_finished())

    def test_readiness_derivation(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.scheduler.mark_succeeded("a")
        self.dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["b"])
        self.dag.add_node("c", noop_action, ["b"], 0, None, 0)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.PENDING)
        self.dag.remove_node("b")
        self.assertEqual(self.scheduler.get_state("c"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["c"])

    def test_failure_policy_skip_downstream(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, ["a"], 0, None, 0)
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)

    def test_failure_policy_fail_fast(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, None, 0, None, 0)
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.CANCELLED)

    def test_failure_policy_continue_on_error(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", noop_action, None, 0, None, 0)
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.READY)

    def test_runner_lifecycle(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, None, 0)
        self.dag.add_node("b", value_action, ["a"], 0, None, 0)
        report = self.runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.results.keys()), {"a", "b"})
        self.assertFalse(self.runner.is_cancelled())
        self.assertTrue(self.scheduler.is_finished())
        self.runner.cancel()
        self.assertTrue(self.runner.is_cancelled())
        self.assertEqual(self.scheduler.get_state("a"), NodeState.SUCCEEDED)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineState,
    name="FakeDagEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:20:14Z
# LAST_CHANGED: 2026-11-08T17:20:14Z
# CHANGE: Reconcile modeled node readiness in both directions: a shared _reconcile_readiness helper classifies any non-terminal node as READY exactly when all of its upstream dependencies are SUCCEEDED (so add_node classifies nodes registered with already-satisfied prerequisites as READY, and add_edge handles both demotion and promotion). remove_node now records direct dependents before purging incident edges and reclassifies each of them afterwards, so dependents left with no remaining prerequisites become READY and are reported by next_wave/get_state/get_all_states. Added a fake readiness-derivation scenario covering registration with a satisfied prerequisite and promotion after prerequisite removal.
# --- END AUTOFAB METADATA ---
