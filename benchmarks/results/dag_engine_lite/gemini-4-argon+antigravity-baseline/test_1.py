"""Comprehensive unit tests for dag_engine_lite_impl."""

from __future__ import annotations

import unittest
from typing import List
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite, dag_engine_lite_impl


class DagEngineLiteImplTest(unittest.TestCase):
    """Unit tests covering DAG, WaveScheduler, and DAGRunner implementations."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(self.registry)

    def test_scenario_1_linear_graph_and_topological_sort(self) -> None:
        """Scenario 1 — Linear graph construction and topological sort."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            self.assertEqual(dag.all_nodes(), set())

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
        """Scenario 2 — Cycle detection during graph validation."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            dag.add_node("step_1", lambda: 1)
            dag.add_node("step_2", lambda: 2, dependencies=["step_1"])

            # Add edge from step_2 to step_1 so step_1 depends on step_2
            dag.add_edge("step_2", "step_1")
            self.assertIn("step_2", dag.get_dependencies("step_1"))
            self.assertIn("step_1", dag.get_dependencies("step_2"))

            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.cycle, ("step_1", "step_2", "step_1"))

            with self.assertRaises(dag_engine_lite.CycleError) as ctx2:
                dag.topological_sort()
            self.assertEqual(ctx2.exception.cycle, ("step_1", "step_2", "step_1"))

    def test_scenario_3_referencing_missing_dependency_raises_error(self) -> None:
        """Scenario 3 — Referencing missing dependency raises error."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            dag.add_node("node_x", lambda: "x")

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("node_missing", "node_x")
            self.assertEqual(ctx.exception.node_id, "node_missing")

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx2:
                dag.add_edge("node_x", "downstream_missing")
            self.assertEqual(ctx2.exception.node_id, "downstream_missing")

    def test_scenario_4_wave_scheduler_priority_tie_breaking(self) -> None:
        """Scenario 4 — Wave scheduler resolves ready nodes with priority tie-breaking."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            scheduler = get_singleton(dag_engine_lite.WaveScheduler)

            dag.add_node("task_low", lambda: 1, priority=5)
            dag.add_node("task_high", lambda: 2, priority=10)
            dag.add_node("task_mid", lambda: 3, priority=5)

            wave = scheduler.next_wave()
            self.assertEqual(wave, ["task_high", "task_low", "task_mid"])

            scheduler.mark_running("task_high")
            self.assertEqual(
                scheduler.get_state("task_high"), dag_engine_lite.NodeState.RUNNING
            )

    def test_scenario_5_failure_policy_skip_downstream(self) -> None:
        """Scenario 5 — Failure policy propagates skip downstream to dependents."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            scheduler = get_singleton(dag_engine_lite.WaveScheduler)

            dag.add_node("parent_node", lambda: 1)
            dag.add_node("child_node", lambda: 2, dependencies=["parent_node"])
            dag.add_node("grandchild_node", lambda: 3, dependencies=["child_node"])
            dag.add_node("independent_node", lambda: 4)

            scheduler.mark_failed(
                "parent_node",
                failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            )
            self.assertEqual(
                scheduler.get_state("parent_node"), dag_engine_lite.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("child_node"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("grandchild_node"),
                dag_engine_lite.NodeState.SKIPPED,
            )
            self.assertEqual(
                scheduler.get_state("independent_node"),
                dag_engine_lite.NodeState.READY,
            )

    def test_scenario_6_critical_path_calculation(self) -> None:
        """Scenario 6 — Critical path calculation with weighted node durations."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            dag.add_node("node_start", lambda: 1)
            dag.add_node("node_branch", lambda: 2, dependencies=["node_start"])
            dag.add_node("node_end", lambda: 3, dependencies=["node_branch"])

            durations = {
                "node_start": 2.5,
                "node_branch": 4.0,
                "node_end": 1.5,
            }
            path, weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["node_start", "node_branch", "node_end"])
            self.assertAlmostEqual(weight, 8.0)

    def test_scenario_7_sequential_runner_execution(self) -> None:
        """Scenario 7 — Sequential runner execution and run report compilation."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            runner = get_singleton(dag_engine_lite.DAGRunner)

            dag.add_node("worker_1", lambda: "res1")
            dag.add_node("worker_2", lambda: "res2", dependencies=["worker_1"])

            report = runner.run(
                failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
            )
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("worker_1", "worker_2"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ("worker_1", "worker_2"))
            self.assertEqual(report.results["worker_1"].value, "res1")
            self.assertEqual(report.results["worker_2"].value, "res2")

    def test_dag_node_and_edge_operations_and_errors(self) -> None:
        """Tests node retrieval, removal, roots, leaves, and missing node errors."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            dag.add_node("n1", lambda: 1, priority=2, retries=3)
            dag.add_node("n2", lambda: 2)
            dag.add_node("n3", lambda: 3, dependencies=["n2"])
            dag.add_edge("n1", "n2")
            # Adding existing edge again is idempotent
            dag.add_edge("n1", "n2")

            n1_def = dag.get_node("n1")
            self.assertEqual(n1_def.node_id, "n1")
            self.assertEqual(n1_def.priority, 2)
            self.assertEqual(n1_def.retries, 3)

            self.assertEqual(dag.find_roots(), {"n1"})
            self.assertEqual(dag.find_leaves(), {"n3"})

            # Remove n2 and verify incident edges are cleaned up
            dag.remove_node("n2")
            self.assertFalse(dag.has_node("n2"))
            self.assertEqual(dag.get_dependents("n1"), set())
            self.assertEqual(dag.get_dependencies("n3"), set())
            self.assertEqual(dag.get_node("n3").dependencies, frozenset())

            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.remove_node("n2")
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.get_node("n2")
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.get_dependencies("n2")
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.get_dependents("n2")

    def test_dag_dangling_dependency_and_out_of_order_addition(self) -> None:
        """Tests adding a node with unregistered dependency, validating, then registering it."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            dag.add_node("child", lambda: 1, dependencies=["missing_parent"])

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "missing_parent")

            # Now register missing_parent; edge should already be in _downstream
            dag.add_node("missing_parent", lambda: 0)
            dag.validate()
            self.assertEqual(dag.get_dependents("missing_parent"), {"child"})
            self.assertEqual(dag.topological_sort(), ["missing_parent", "child"])

    def test_dag_complex_cycle_and_diamond_graph(self) -> None:
        """Tests diamond graph (no cycle) vs deeper cycle detection."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            # Diamond: a -> b, a -> c, b -> d, c -> d
            dag.add_node("a", lambda: 1)
            dag.add_node("b", lambda: 2, dependencies=["a"], priority=1)
            dag.add_node("c", lambda: 3, dependencies=["a"], priority=2)
            dag.add_node("d", lambda: 4, dependencies=["b", "c"])
            # Also add dangling edge in downstream to ensure DFS skips non-existent nodes
            dag.add_node("e", lambda: 5, dependencies=["non_existent"])
            dag.remove_node("e")

            dag.validate()
            self.assertEqual(dag.topological_sort(), ["a", "c", "b", "d"])
            path, weight = dag.compute_critical_path()
            self.assertEqual(weight, 3.0)
            self.assertEqual(path, ["a", "c", "d"])

            # Empty DAG critical path
            empty_dag = dag_engine_lite_impl.DAG()
            self.assertEqual(empty_dag.compute_critical_path(), ([], 0.0))

            # Introduce cycle d -> b (so b depends on d: a -> b -> d -> b)
            dag.add_edge("d", "b")
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.cycle, ("b", "d", "b"))

    def test_wave_scheduler_states_and_dynamic_sync(self) -> None:
        """Tests WaveScheduler state transitions, dynamic node additions/removals, and policies."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            scheduler = get_singleton(dag_engine_lite.WaveScheduler)

            # Empty graph is finished
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])

            dag.add_node("r1", lambda: 1)
            dag.add_node("d1", lambda: 2, dependencies=["r1"])
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(
                scheduler.get_state("r1"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(
                scheduler.get_state("d1"), dag_engine_lite.NodeState.PENDING
            )

            # Mark r1 running -> next_wave is empty
            scheduler.mark_running("r1")
            self.assertEqual(scheduler.next_wave(), [])
            scheduler.mark_succeeded("r1")
            self.assertEqual(
                scheduler.get_state("d1"), dag_engine_lite.NodeState.READY
            )

            # Dynamically add d2 depending on r1 (which is already SUCCEEDED)
            dag.add_node("d2", lambda: 3, dependencies=["r1"])
            self.assertEqual(
                scheduler.get_state("d2"), dag_engine_lite.NodeState.READY
            )

            # Remove d2 from DAG and verify scheduler syncs it out
            dag.remove_node("d2")
            all_states = scheduler.get_all_states()
            self.assertNotIn("d2", all_states)

            # Test diamond dependency in scheduler where one parent is still pending
            dag.add_node("r2", lambda: 4)
            dag.add_node("join", lambda: 5, dependencies=["d1", "r2"])
            scheduler.mark_succeeded("d1")
            # join still waiting on r2
            self.assertEqual(
                scheduler.get_state("join"), dag_engine_lite.NodeState.PENDING
            )
            scheduler.mark_succeeded("r2")
            self.assertEqual(
                scheduler.get_state("join"), dag_engine_lite.NodeState.READY
            )
            scheduler.mark_succeeded("join")
            self.assertTrue(scheduler.is_finished())

    def test_wave_scheduler_skip_downstream_diamond_and_fail_fast(self) -> None:
        """Tests skip downstream with diamond convergence and fail fast cancellation."""
        with enter_phase(system, registry=self.registry):
            dag = get_singleton(dag_engine_lite.DAG)
            scheduler = get_singleton(dag_engine_lite.WaveScheduler)

            dag.add_node("a", lambda: 1)
            dag.add_node("b", lambda: 2, dependencies=["a"])
            dag.add_node("c", lambda: 3, dependencies=["a"])
            dag.add_node("d", lambda: 4, dependencies=["b", "c"])
            dag.add_node("done", lambda: 5)

            scheduler.mark_succeeded("done")
            # Mark 'a' failed with SKIP_DOWNSTREAM; 'd' is reached via both 'b' and 'c'
            scheduler.mark_failed(
                "a", failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(
                scheduler.get_state("d"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("done"), dag_engine_lite.NodeState.SUCCEEDED
            )

            # Test FAIL_FAST
            dag.add_node("p1", lambda: 6)
            dag.add_node("p2", lambda: 7, dependencies=["p1"])
            scheduler.mark_failed(
                "p1", failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST
            )
            self.assertEqual(
                scheduler.get_state("p2"), dag_engine_lite.NodeState.CANCELLED
            )

    def test_dag_runner_retries_and_failure_policies(self) -> None:
        """Tests DAGRunner retry logic, FAIL_FAST, SKIP_DOWNSTREAM, and CONTINUE_ON_ERROR."""
        # 1. Test retry succeeds on 2nd retry
        reg1 = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(reg1)
        with enter_phase(system, registry=reg1):
            dag = get_singleton(dag_engine_lite.DAG)
            runner = get_singleton(dag_engine_lite.DAGRunner)

            attempts_list: List[int] = []

            def flaky_action() -> str:
                attempts_list.append(1)
                if len(attempts_list) < 3:
                    raise ValueError("transient error")
                return "recovered"

            dag.add_node("flaky", flaky_action, retries=2)
            report = runner.run()
            self.assertEqual(report.succeeded_nodes, ("flaky",))
            self.assertEqual(report.results["flaky"].retries_attempted, 2)
            self.assertEqual(report.results["flaky"].value, "recovered")

        # 2. Test FAIL_FAST halts wave execution and cancels remaining nodes
        reg2 = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(reg2)
        with enter_phase(system, registry=reg2):
            dag = get_singleton(dag_engine_lite.DAG)
            runner = get_singleton(dag_engine_lite.DAGRunner)

            def failing_action() -> None:
                raise RuntimeError("boom")

            dag.add_node("fail_root", failing_action, priority=10, retries=1)
            dag.add_node("other_root", lambda: "ok", priority=1)
            dag.add_node("child", lambda: "child", dependencies=["fail_root"])

            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST)
            self.assertEqual(report.failed_nodes, ("fail_root",))
            self.assertEqual(report.cancelled_nodes, ("child", "other_root"))
            self.assertEqual(report.results["fail_root"].retries_attempted, 1)
            err = report.results["fail_root"].error
            self.assertIsInstance(err, dag_engine_lite.NodeExecutionError)
            assert isinstance(err, dag_engine_lite.NodeExecutionError)
            self.assertEqual(err.node_id, "fail_root")
            self.assertIsInstance(err.cause, RuntimeError)
            self.assertEqual(
                report.results["child"].state, dag_engine_lite.NodeState.CANCELLED
            )

        # 3. Test SKIP_DOWNSTREAM skips dependents in same and later waves while running independent nodes
        reg3 = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(reg3)
        with enter_phase(system, registry=reg3):
            dag = get_singleton(dag_engine_lite.DAG)
            runner = get_singleton(dag_engine_lite.DAGRunner)

            def raise_node_exec_error() -> None:
                raise dag_engine_lite.NodeExecutionError(
                    message="direct error",
                    node_id="bad",
                    cause=ValueError("inner"),
                )

            dag.add_node("bad", raise_node_exec_error, priority=10)
            dag.add_node("bad_dep", lambda: 1, dependencies=["bad"])
            dag.add_node("good", lambda: "good_val", priority=5)

            report = runner.run(
                failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(report.succeeded_nodes, ("good",))
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.skipped_nodes, ("bad_dep",))
            self.assertEqual(
                report.results["bad_dep"].state, dag_engine_lite.NodeState.SKIPPED
            )

        # 4. Test CONTINUE_ON_ERROR where downstream node stays PENDING and wave loop halts cleanly
        reg4 = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(reg4)
        with enter_phase(system, registry=reg4):
            dag = get_singleton(dag_engine_lite.DAG)
            runner = get_singleton(dag_engine_lite.DAGRunner)

            def fail_act() -> None:
                raise ValueError("err")

            dag.add_node("root_fail", fail_act, priority=10)
            dag.add_node("dependent_blocked", lambda: 1, dependencies=["root_fail"])
            dag.add_node("root_ok", lambda: "ok", priority=5)

            report = runner.run(
                failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
            )
            self.assertEqual(report.succeeded_nodes, ("root_ok",))
            self.assertEqual(report.failed_nodes, ("root_fail",))
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())

    def test_direct_collaborator_injection_and_edge_cases(self) -> None:
        """Tests direct collaborator fallback properties and mid-wave state transitions."""
        dag = dag_engine_lite_impl.DAG()
        scheduler = dag_engine_lite_impl.WaveScheduler()
        scheduler._dag_instance = dag
        runner = dag_engine_lite_impl.DAGRunner()
        runner._dag_instance = dag
        runner._scheduler_instance = scheduler

        # Test mid-wave state change where a node in the wave is no longer READY when reached
        def cancel_sibling() -> str:
            scheduler.mark_failed(
                "sibling", failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
            )
            return "first_done"

        dag.add_node("first", cancel_sibling, priority=10)
        dag.add_node("sibling", lambda: "sib", priority=1)

        report = runner.run(
            failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )
        self.assertEqual(report.succeeded_nodes, ("first",))
        self.assertEqual(report.failed_nodes, ("sibling",))

        # Test _find_cycle when a neighbor is missing from _nodes or already visited
        dag2 = dag_engine_lite_impl.DAG()
        dag2.add_node("x", lambda: 1, dependencies=["ghost"])
        dag2.add_node("y", lambda: 2)
        dag2.add_node("z", lambda: 3, dependencies=["y"])
        # _find_cycle skips 'ghost' because 'ghost' is not in _nodes
        self.assertIsNone(dag2._find_cycle())


if __name__ == "__main__":
    unittest.main()
