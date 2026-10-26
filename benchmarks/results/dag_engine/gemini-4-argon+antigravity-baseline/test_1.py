"""Comprehensive unit tests for dag_engine_impl."""

from __future__ import annotations

import threading
import time
import unittest
from typing import List
from unittest.mock import patch

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_1.parts.dag_engine.lib import dag_engine
from benchmark_1.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class DAGEngineImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_singleton_registration_and_resolution(self) -> None:
        """Verifies DAG, WaveScheduler, and DAGRunner singletons register and initialize in system tier."""
        default_reg = LifecycleRegistry()
        with patch(
            "benchmark_1.parts.dag_engine.lib.dag_engine_impl.get_default_registry",
            return_value=default_reg,
        ):
            __initialize__()
            with enter_phase(system, registry=default_reg) as scope:
                dag = scope.get_singleton(dag_engine.DAG)
                scheduler = scope.get_singleton(dag_engine.WaveScheduler)
                runner = scope.get_singleton(dag_engine.DAGRunner)
                self.assertIsInstance(dag, DAG)
                self.assertIsInstance(scheduler, WaveScheduler)
                self.assertIsInstance(runner, DAGRunner)

    def test_scenario_1_linear_graph_and_topological_sort(self) -> None:
        """Scenario 1: Linear graph construction and topological sort."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            dag.add_node("task_a", lambda: "a", priority=10)
            self.assertTrue(dag.has_node("task_a"))
            self.assertEqual(dag.get_dependencies("task_a"), set())

            dag.add_node("task_b", lambda: "b", dependencies=["task_a"], priority=5)
            self.assertTrue(dag.has_node("task_b"))
            self.assertEqual(dag.get_dependencies("task_b"), {"task_a"})
            self.assertEqual(dag.get_dependents("task_a"), {"task_b"})

            order = dag.topological_sort()
            self.assertEqual(order, ["task_a", "task_b"])

    def test_scenario_2_cycle_detection_during_validation(self) -> None:
        """Scenario 2: Cycle detection during graph validation."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            dag.add_node("step_1", lambda: 1)
            dag.add_node("step_2", lambda: 2, dependencies=["step_1"])
            dag.add_edge("step_2", "step_1")

            with self.assertRaises(dag_engine.CycleError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.cycle, ("step_1", "step_2", "step_1"))

            with self.assertRaises(dag_engine.CycleError) as ctx2:
                dag.topological_sort()
            self.assertEqual(ctx2.exception.cycle, ("step_1", "step_2", "step_1"))

    def test_scenario_3_referencing_missing_dependency_raises_error(self) -> None:
        """Scenario 3: Referencing missing dependency raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            dag.add_node("node_x", lambda: "x")

            with self.assertRaises(dag_engine.NodeNotFoundError) as ctx:
                dag.add_edge("node_missing", "node_x")
            self.assertEqual(ctx.exception.node_id, "node_missing")

            with self.assertRaises(dag_engine.NodeNotFoundError) as ctx2:
                dag.add_edge("node_x", "downstream_missing")
            self.assertEqual(ctx2.exception.node_id, "downstream_missing")

    def test_scenario_4_wave_scheduler_priority_tie_breaking(self) -> None:
        """Scenario 4: Wave scheduler resolves ready nodes with priority tie-breaking."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)

            dag.add_node("task_low", lambda: 1, priority=1)
            dag.add_node("task_high", lambda: 2, priority=10)
            dag.add_node("task_mid", lambda: 3, priority=5)
            dag.add_node("task_mid_b", lambda: 4, priority=5)

            wave = scheduler.next_wave()
            self.assertEqual(
                wave, ["task_high", "task_mid", "task_mid_b", "task_low"]
            )

            scheduler.mark_running("task_high")
            self.assertEqual(
                scheduler.get_state("task_high"), dag_engine.NodeState.RUNNING
            )

    def test_scenario_5_failure_policy_skip_downstream(self) -> None:
        """Scenario 5: Failure policy propagates skip downstream to dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)

            dag.add_node("parent_node", lambda: 1)
            dag.add_node("child_node", lambda: 2, dependencies=["parent_node"])
            dag.add_node("grandchild_node", lambda: 3, dependencies=["child_node"])
            dag.add_node("other_branch", lambda: 4)
            # Diamond dependency into grandchild_node
            dag.add_node("child_node_2", lambda: 5, dependencies=["parent_node"])
            dag.add_edge("child_node_2", "grandchild_node")

            scheduler.mark_failed(
                "parent_node",
                failure_policy=dag_engine.FailurePolicy.SKIP_DOWNSTREAM,
            )
            self.assertEqual(
                scheduler.get_state("parent_node"), dag_engine.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("child_node"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("child_node_2"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("grandchild_node"),
                dag_engine.NodeState.SKIPPED,
            )
            self.assertEqual(
                scheduler.get_state("other_branch"), dag_engine.NodeState.READY
            )
            # Mark a child succeeded before failing another parent with SKIP_DOWNSTREAM
            dag.add_node("parent_2", lambda: 6)
            dag.add_node("already_done", lambda: 7, dependencies=["parent_2"])
            scheduler.mark_succeeded("already_done")
            scheduler.mark_failed(
                "parent_2",
                failure_policy=dag_engine.FailurePolicy.SKIP_DOWNSTREAM,
            )
            self.assertEqual(
                scheduler.get_state("already_done"),
                dag_engine.NodeState.SUCCEEDED,
            )

    def test_scenario_6_critical_path_calculation(self) -> None:
        """Scenario 6: Critical path calculation with weighted node durations."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            dag.add_node("node_start", lambda: 1)
            dag.add_node("node_branch", lambda: 2, dependencies=["node_start"])
            dag.add_node("short_branch", lambda: 4, dependencies=["node_start"])
            dag.add_node(
                "node_end",
                lambda: 3,
                dependencies=["node_branch", "short_branch"],
            )

            durations = {
                "node_start": 2.5,
                "node_branch": 4.0,
                "node_end": 1.5,
                "short_branch": 1.0,
            }
            path, weight = dag.compute_critical_path(estimated_durations=durations)
            self.assertEqual(path, ["node_start", "node_branch", "node_end"])
            self.assertAlmostEqual(weight, 8.0)

            # Default weights (1.0 per node)
            default_path, default_weight = dag.compute_critical_path()
            self.assertEqual(default_path, ["node_start", "node_branch", "node_end"])
            self.assertAlmostEqual(default_weight, 3.0)

    def test_empty_dag_critical_path_roots_leaves_and_scheduler(self) -> None:
        """Verifies empty DAG behavior for critical path, roots, leaves, and scheduler completion."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)

            self.assertEqual(dag.all_nodes(), set())
            self.assertEqual(dag.find_roots(), set())
            self.assertEqual(dag.find_leaves(), set())
            self.assertEqual(dag.topological_sort(), [])
            self.assertEqual(dag.compute_critical_path(), ([], 0.0))
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(scheduler.get_all_states(), {})

    def test_node_operations_and_removal(self) -> None:
        """Tests node retrieval, removal, and missing node errors."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)

            dag.add_node("n1", lambda: 1)
            dag.add_node("n2", lambda: 2)
            # Sync scheduler when both n1 and n2 are roots (so n2 is READY)
            self.assertEqual(scheduler.get_state("n1"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("n2"), dag_engine.NodeState.READY)

            # Now add edge n1 -> n2 while n2 is in READY state: next_wave filters out n2 until n1 succeeds
            dag.add_edge("n1", "n2")
            # Adding duplicate edge is idempotent
            dag.add_edge("n1", "n2")
            self.assertEqual(scheduler.next_wave(), ["n1"])
            # Calling mark_succeeded on n1 when n2 is already in READY state
            scheduler.mark_succeeded("n1")
            self.assertEqual(scheduler.next_wave(), ["n2"])

            node_def = dag.get_node("n2")
            self.assertEqual(node_def.node_id, "n2")
            self.assertEqual(node_def.dependencies, frozenset({"n1"}))

            self.assertEqual(dag.find_roots(), {"n1"})
            self.assertEqual(dag.find_leaves(), {"n2"})

            # Remove n1
            dag.remove_node("n1")
            self.assertFalse(dag.has_node("n1"))
            self.assertEqual(dag.get_dependencies("n2"), set())
            self.assertEqual(scheduler.get_state("n2"), dag_engine.NodeState.READY)
            self.assertNotIn("n1", scheduler.get_all_states())

            # Errors on missing node operations
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.remove_node("missing")
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.get_node("missing")
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.get_dependencies("missing")
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.get_dependents("missing")

    def test_validate_missing_dependency(self) -> None:
        """Tests validate raising NodeNotFoundError when a node's dependency was never registered."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            dag.add_node("child", lambda: 1, dependencies=["unregistered_parent"])
            with self.assertRaises(dag_engine.NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "unregistered_parent")

            # Also test removing unregistered parent after child is removed
            dag.remove_node("child")
            dag.validate()

    def test_dfs_cycle_with_multiple_components_and_branches(self) -> None:
        """Tests cycle detection across disconnected components and diamond subgraphs."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            # Acyclic diamond first in alphabetical order
            dag.add_node("a1", lambda: 1)
            dag.add_node("a2", lambda: 2, dependencies=["a1"])
            dag.add_node("a3", lambda: 3, dependencies=["a1"])
            dag.add_node("a4", lambda: 4, dependencies=["a2", "a3"])

            # Second component with cycle
            dag.add_node("c1", lambda: 5)
            dag.add_node("c2", lambda: 6, dependencies=["c1"])
            dag.add_node("c3", lambda: 7, dependencies=["c2"])
            dag.add_edge("c3", "c1")

            with self.assertRaises(dag_engine.CycleError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.cycle, ("c1", "c2", "c3", "c1"))

    def test_scheduler_mark_succeeded_and_policies(self) -> None:
        """Tests WaveScheduler state transitions for mark_succeeded and failure policies."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)

            dag.add_node("p1", lambda: 1)
            dag.add_node("p2", lambda: 2)
            dag.add_node("join", lambda: 3, dependencies=["p1", "p2"])

            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("p1")
            scheduler.mark_succeeded("p1")
            # join still waiting on p2
            self.assertEqual(
                scheduler.get_state("join"), dag_engine.NodeState.PENDING
            )
            scheduler.mark_running("p2")
            scheduler.mark_succeeded("p2")
            # Now join is promoted to READY
            self.assertEqual(
                scheduler.get_state("join"), dag_engine.NodeState.READY
            )

            # Fail join with FAIL_FAST
            dag.add_node("unstarted", lambda: 4)
            self.assertEqual(
                scheduler.get_state("unstarted"), dag_engine.NodeState.READY
            )
            scheduler.mark_failed(
                "join", failure_policy=dag_engine.FailurePolicy.FAIL_FAST
            )
            self.assertEqual(
                scheduler.get_state("join"), dag_engine.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("unstarted"), dag_engine.NodeState.CANCELLED
            )
            self.assertTrue(scheduler.is_finished())

    def test_runner_concurrent_execution_and_retries(self) -> None:
        """Scenario 7: Concurrent runner execution across thread pool with retries."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            runner = scope.get_singleton(dag_engine.DAGRunner)

            attempts = {"flaky": 0}

            def flaky_task() -> str:
                attempts["flaky"] += 1
                if attempts["flaky"] < 3:
                    raise RuntimeError("transient error")
                return "recovered"

            dag.add_node("worker_1", lambda: "w1", priority=5)
            dag.add_node("worker_2", flaky_task, priority=10, retries=2)
            dag.add_node(
                "final",
                lambda: "done",
                dependencies=["worker_1", "worker_2"],
            )

            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.FAIL_FAST,
                max_concurrency=2,
            )
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(
                report.succeeded_nodes, ("final", "worker_1", "worker_2")
            )
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["worker_2"].value, "recovered")
            self.assertEqual(report.results["worker_2"].retries_attempted, 2)
            self.assertTrue(len(report.critical_path) >= 2)

    def test_runner_failure_policies(self) -> None:
        """Tests DAGRunner under FAIL_FAST, SKIP_DOWNSTREAM, and CONTINUE_ON_ERROR."""
        # 1. SKIP_DOWNSTREAM
        reg1 = LifecycleRegistry()
        __initialize__(reg1)
        with enter_phase(system, registry=reg1) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            runner = scope.get_singleton(dag_engine.DAGRunner)

            def fail_action() -> None:
                raise ValueError("boom")

            dag.add_node("bad", fail_action, priority=10, retries=1)
            dag.add_node("dependent", lambda: "dep", dependencies=["bad"])
            dag.add_node("independent", lambda: "ind", priority=1)

            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.SKIP_DOWNSTREAM,
                max_concurrency=1,
            )
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.skipped_nodes, ("dependent",))
            self.assertEqual(report.succeeded_nodes, ("independent",))
            self.assertEqual(report.results["bad"].retries_attempted, 1)
            self.assertIsInstance(report.results["bad"].error, ValueError)

        # 2. CONTINUE_ON_ERROR
        reg2 = LifecycleRegistry()
        __initialize__(reg2)
        with enter_phase(system, registry=reg2) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            runner = scope.get_singleton(dag_engine.DAGRunner)

            def fail_action_2() -> None:
                raise ValueError("boom2")

            dag.add_node("bad", fail_action_2, priority=10)
            dag.add_node("dependent", lambda: "dep", dependencies=["bad"])
            dag.add_node("independent", lambda: "ind", priority=1)

            report2 = runner.run(
                failure_policy=dag_engine.FailurePolicy.CONTINUE_ON_ERROR,
                max_concurrency=1,
            )
            self.assertEqual(report2.failed_nodes, ("bad",))
            self.assertEqual(report2.succeeded_nodes, ("independent",))
            self.assertEqual(report2.skipped_nodes, ("dependent",))

    def test_runner_timeout_and_cancellation(self) -> None:
        """Tests DAGRunner raising DAGTimeoutError and DAGCancelledError."""
        # 1. Timeout during execution
        reg1 = LifecycleRegistry()
        __initialize__(reg1)
        with enter_phase(system, registry=reg1) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            runner = scope.get_singleton(dag_engine.DAGRunner)

            dag.add_node("slow_1", lambda: time.sleep(0.05))
            dag.add_node("slow_2", lambda: time.sleep(0.05), dependencies=["slow_1"])

            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

        # 2. Timeout before wave starts (negative timeout)
        reg1b = LifecycleRegistry()
        __initialize__(reg1b)
        with enter_phase(system, registry=reg1b) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            runner = scope.get_singleton(dag_engine.DAGRunner)
            dag.add_node("fast", lambda: 1)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=-1.0)

        # 3. Cancel before run starts
        reg2 = LifecycleRegistry()
        __initialize__(reg2)
        with enter_phase(system, registry=reg2) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)
            runner = scope.get_singleton(dag_engine.DAGRunner)

            dag.add_node("n1", lambda: 1)
            runner.cancel()
            self.assertEqual(
                scheduler.get_state("n1"), dag_engine.NodeState.CANCELLED
            )

        # 4. Cancel during active wave execution
        reg3 = LifecycleRegistry()
        __initialize__(reg3)
        with enter_phase(system, registry=reg3) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            scheduler = scope.get_singleton(dag_engine.WaveScheduler)
            runner = scope.get_singleton(dag_engine.DAGRunner)

            def cancel_self() -> None:
                runner.cancel()

            dag.add_node("canceller", cancel_self)
            dag.add_node("after_cancel", lambda: 2, dependencies=["canceller"])

            with self.assertRaises(dag_engine.DAGCancelledError):
                runner.run()
            self.assertEqual(
                scheduler.get_state("after_cancel"),
                dag_engine.NodeState.CANCELLED,
            )

        # 5. Cancel checked at loop top when scheduler not finished
        reg4 = LifecycleRegistry()
        __initialize__(reg4)
        with enter_phase(system, registry=reg4) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            runner = scope.get_singleton(dag_engine.DAGRunner)
            assert isinstance(runner, DAGRunner)
            dag.add_node("n1", lambda: 1)
            runner._cancelled.set()
            with self.assertRaises(dag_engine.DAGCancelledError):
                runner.run()

    def test_direct_instantiation_lazy_singleton_resolution(self) -> None:
        """Tests WaveScheduler and DAGRunner resolving singletons lazily when constructed directly."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(dag_engine.DAG)
            dag.add_node("only", lambda: 42)
            # Construct without calling initialize() to exercise lazy _get_dag() and _get_scheduler()
            direct_sched = WaveScheduler()
            self.assertEqual(direct_sched.next_wave(), ["only"])
            direct_runner = DAGRunner()
            report = direct_runner.run()
            self.assertEqual(report.succeeded_nodes, ("only",))


if __name__ == "__main__":
    unittest.main()
