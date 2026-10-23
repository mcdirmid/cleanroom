from __future__ import annotations

import unittest
from typing import Any, List, Set, Tuple

from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    get_default_registry,
    system,
)
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from benchmark_3.parts.dag_engine_lite.lib import dag_engine_lite


class TestDataTypesAndExceptions(unittest.TestCase):
    """Tests for exceptions, enums, and data types in dag_engine_lite."""

    def test_dag_error_hierarchy_and_str(self):
        err = dag_engine_lite.DAGError("base error")
        self.assertEqual(str(err), "base error")
        self.assertEqual(err.message, "base error")

        cycle_err = dag_engine_lite.CycleError("cycle found", cycle=("A", "B", "A"))
        self.assertEqual(str(cycle_err), "cycle found")
        self.assertEqual(cycle_err.cycle, ("A", "B", "A"))
        self.assertIsInstance(cycle_err, dag_engine_lite.DAGError)

        not_found_err = dag_engine_lite.NodeNotFoundError("node missing", node_id="X")
        self.assertEqual(str(not_found_err), "node missing")
        self.assertEqual(not_found_err.node_id, "X")
        self.assertIsInstance(not_found_err, dag_engine_lite.DAGError)

        cause = RuntimeError("root cause")
        exec_err = dag_engine_lite.NodeExecutionError("exec failed", node_id="Y", cause=cause)
        self.assertEqual(str(exec_err), "exec failed")
        self.assertEqual(exec_err.node_id, "Y")
        self.assertEqual(exec_err.cause, cause)
        self.assertIsInstance(exec_err, dag_engine_lite.DAGError)

    def test_enums(self):
        self.assertEqual(dag_engine_lite.NodeState.PENDING.value, "pending")
        self.assertEqual(dag_engine_lite.NodeState.READY.value, "ready")
        self.assertEqual(dag_engine_lite.NodeState.RUNNING.value, "running")
        self.assertEqual(dag_engine_lite.NodeState.SUCCEEDED.value, "succeeded")
        self.assertEqual(dag_engine_lite.NodeState.FAILED.value, "failed")
        self.assertEqual(dag_engine_lite.NodeState.CANCELLED.value, "cancelled")
        self.assertEqual(dag_engine_lite.NodeState.SKIPPED.value, "skipped")

        self.assertEqual(dag_engine_lite.FailurePolicy.FAIL_FAST.value, "fail_fast")
        self.assertEqual(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR.value, "continue_on_error")
        self.assertEqual(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM.value, "skip_downstream")

    def test_node_definition_and_results(self):
        defn = dag_engine_lite.NodeDefinition(
            node_id="N1",
            action=lambda: 10,
            dependencies=frozenset(["N0"]),
            priority=5,
            retries=2,
        )
        self.assertEqual(defn.node_id, "N1")
        self.assertEqual(defn.priority, 5)
        self.assertEqual(defn.retries, 2)
        self.assertEqual(defn.dependencies, frozenset(["N0"]))
        self.assertEqual(defn.action(), 10)

        res = dag_engine_lite.NodeResult(
            node_id="N1",
            state=dag_engine_lite.NodeState.SUCCEEDED,
            value=10,
            duration_seconds=0.1,
            retries_attempted=1,
        )
        self.assertEqual(res.node_id, "N1")
        self.assertEqual(res.state, dag_engine_lite.NodeState.SUCCEEDED)
        self.assertEqual(res.value, 10)
        self.assertIsNone(res.error)
        self.assertEqual(res.duration_seconds, 0.1)
        self.assertEqual(res.retries_attempted, 1)


class TestDAG(unittest.TestCase):
    """Tests for the DAG singleton covering add_node, edges, traversal, sort, and paths."""

    def setUp(self):
        self.registry = LifecycleRegistry()

    def _setup_dag(self):
        __initialize__(self.registry)

    def test_initialize_with_default_registry(self):
        # Coverage for registry is None branch in __initialize__
        __initialize__(None)

    def test_dag_add_node_and_has_node(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("X"))
            dag.add_node("X", action=lambda: 42)
            self.assertTrue(dag.has_node("X"))
            self.assertEqual(dag.all_nodes(), {"X"})

    def test_dag_add_node_with_dependencies(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            # Re-adding B with same dep to cover existing sets
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            self.assertEqual(dag.get_dependencies("B"), {"A"})
            self.assertEqual(dag.get_dependents("A"), {"B"})

    def test_dag_get_node_definition(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node(
                "A",
                action=lambda: "hello",
                dependencies=["X"],
                priority=5,
                retries=2,
            )
            node_def = dag.get_node("A")
            self.assertEqual(node_def.node_id, "A")
            self.assertEqual(node_def.priority, 5)
            self.assertEqual(node_def.retries, 2)
            self.assertEqual(node_def.dependencies, frozenset(["X"]))

    def test_dag_get_node_missing_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_node("MISSING")
            self.assertEqual(ctx.exception.node_id, "MISSING")

    def test_dag_add_edge_valid(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2)
            dag.add_edge("A", "B")
            self.assertEqual(dag.get_dependencies("B"), {"A"})
            self.assertEqual(dag.get_dependents("A"), {"B"})
            self.assertIn("A", dag.get_node("B").dependencies)

    def test_dag_add_edge_missing_upstream_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("B", action=lambda: 1)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("NOPE", "B")
            self.assertEqual(ctx.exception.node_id, "NOPE")

    def test_dag_add_edge_missing_downstream_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("A", "NOPE")
            self.assertEqual(ctx.exception.node_id, "NOPE")

    def test_dag_remove_node(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["B"])
            dag.remove_node("B")
            self.assertFalse(dag.has_node("B"))
            self.assertTrue(dag.has_node("A"))
            self.assertTrue(dag.has_node("C"))
            self.assertEqual(dag.get_dependents("A"), set())
            self.assertEqual(dag.get_dependencies("C"), set())

    def test_dag_remove_node_missing_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.remove_node("NOPE")
            self.assertEqual(ctx.exception.node_id, "NOPE")

    def test_dag_get_dependencies_missing_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_dependencies("NOPE")
            self.assertEqual(ctx.exception.node_id, "NOPE")

    def test_dag_get_dependents_missing_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_dependents("NOPE")
            self.assertEqual(ctx.exception.node_id, "NOPE")

    def test_dag_find_roots_and_leaves(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3)
            self.assertEqual(dag.find_roots(), {"A", "C"})
            self.assertEqual(dag.find_leaves(), {"B", "C"})

    def test_dag_validate_no_cycle(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.validate()

    def test_dag_validate_missing_dependency_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1, dependencies=["MISSING"])
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "MISSING")

    def test_dag_validate_cycle_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2)
            dag.add_edge("A", "B")
            dag.add_edge("B", "A")
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.validate()
            self.assertIn("A", ctx.exception.cycle)
            self.assertIn("B", ctx.exception.cycle)

    def test_dag_topological_sort_priority_and_tie_breaking(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("Z", action=lambda: 1, priority=10)
            dag.add_node("A", action=lambda: 2, priority=10)
            dag.add_node("M", action=lambda: 3, priority=5)
            dag.add_node("D", action=lambda: 4, dependencies=["Z", "A"], priority=20)
            order = dag.topological_sort()
            # Between A and Z (both priority 10), tie breaks by name ascending: A precedes Z
            self.assertEqual(order[:2], ["A", "Z"])
            self.assertEqual(order[2:], ["D", "M"])

    def test_dag_topological_sort_cycle_raises(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1, dependencies=["B"])
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.topological_sort()
            self.assertIsInstance(ctx.exception.cycle, tuple)

    def test_dag_compute_critical_path_empty(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            path, duration = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(duration, 0.0)

    def test_dag_compute_critical_path_custom_durations(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup_dag()
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["A"])
            dag.add_node("D", action=lambda: 4, dependencies=["B", "C"])
            # Path A->B->D duration = 1 + 10 + 2 = 13
            # Path A->C->D duration = 1 + 3 + 2 = 6
            path, duration = dag.compute_critical_path(
                estimated_durations={"A": 1.0, "B": 10.0, "C": 3.0, "D": 2.0}
            )
            self.assertEqual(path, ["A", "B", "D"])
            self.assertEqual(duration, 13.0)


class TestWaveScheduler(unittest.TestCase):
    """Tests for WaveScheduler covering state transitions, wave ordering, and failure policies."""

    def setUp(self):
        self.registry = LifecycleRegistry()

    def _setup(self):
        __initialize__(self.registry)

    def test_wave_scheduler_sync_and_next_wave(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1, priority=1)
            dag.add_node("B", action=lambda: 2, priority=5)
            dag.add_node("C", action=lambda: 3, dependencies=["A"], priority=10)
            wave = scheduler.next_wave()
            # B has higher priority than A
            self.assertEqual(wave, ["B", "A"])

    def test_wave_scheduler_mark_running_and_succeeded(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            scheduler.mark_running("A")
            self.assertEqual(scheduler.get_state("A"), dag_engine_lite.NodeState.RUNNING)
            scheduler.mark_succeeded("A")
            self.assertEqual(scheduler.get_state("A"), dag_engine_lite.NodeState.SUCCEEDED)
            # Dependent B promoted to READY
            self.assertEqual(scheduler.get_state("B"), dag_engine_lite.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["B"])

    def test_wave_scheduler_multiple_dependencies_unlock(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2)
            dag.add_node("C", action=lambda: 3, dependencies=["A", "B"])
            scheduler.mark_succeeded("A")
            # C still pending because B has not succeeded
            self.assertEqual(scheduler.get_state("C"), dag_engine_lite.NodeState.PENDING)
            scheduler.mark_succeeded("B")
            # C now promoted to READY
            self.assertEqual(scheduler.get_state("C"), dag_engine_lite.NodeState.READY)

    def test_wave_scheduler_node_removal_sync(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1)
            scheduler.next_wave()
            self.assertIn("A", scheduler.get_all_states())
            dag.remove_node("A")
            self.assertNotIn("A", scheduler.get_all_states())
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                scheduler.get_state("A")

    def test_wave_scheduler_is_finished_transitions(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            # Empty DAG returns True
            self.assertTrue(scheduler.is_finished())
            dag.add_node("A", action=lambda: 1)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("A")
            self.assertTrue(scheduler.is_finished())

    def test_wave_scheduler_fail_fast(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3)
            scheduler.mark_failed("A", dag_engine_lite.FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("A"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("B"), dag_engine_lite.NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("C"), dag_engine_lite.NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_wave_scheduler_skip_downstream(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["B"])
            dag.add_node("D", action=lambda: 4)
            # Transitive chain A -> B -> C
            scheduler.mark_failed("A", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("A"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("B"), dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("C"), dag_engine_lite.NodeState.SKIPPED)
            # Independent D stays READY
            self.assertEqual(scheduler.get_state("D"), dag_engine_lite.NodeState.READY)
            self.assertFalse(scheduler.is_finished())

    def test_wave_scheduler_continue_on_error(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2)
            scheduler.mark_failed("A", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("A"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("B"), dag_engine_lite.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["B"])


class TestDAGRunner(unittest.TestCase):
    """Tests for DAGRunner covering sequential execution, retries, and policies."""

    def setUp(self):
        self.registry = LifecycleRegistry()

    def _setup(self):
        __initialize__(self.registry)

    def test_runner_empty_dag(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ())

    def test_runner_validates_before_running(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("A", action=lambda: 1, dependencies=["MISSING"])
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                runner.run()

    def test_runner_success_chain(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls = []
            dag.add_node("A", action=lambda: calls.append("A") or "res_a")
            dag.add_node("B", action=lambda: calls.append("B") or "res_b", dependencies=["A"])
            report = runner.run()
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("A", "B"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(calls, ["A", "B"])
            self.assertEqual(report.results["A"].value, "res_a")
            self.assertEqual(report.results["B"].value, "res_b")
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("A", "B"))

    def test_runner_fail_fast_halts(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def failing():
                raise ValueError("explicit failure")

            dag.add_node("A", action=failing)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3)
            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST)
            self.assertIn("A", report.failed_nodes)
            self.assertIn("B", report.cancelled_nodes)
            self.assertIn("C", report.cancelled_nodes)
            self.assertIsInstance(report.results["A"].error, ValueError)

    def test_runner_continue_on_error(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def failing():
                raise RuntimeError("fail A")

            dag.add_node("A", action=failing)
            dag.add_node("B", action=lambda: "success B")
            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.failed_nodes, ("A",))
            self.assertEqual(report.succeeded_nodes, ("B",))
            self.assertEqual(report.results["B"].value, "success B")

    def test_runner_skip_downstream(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def failing():
                raise RuntimeError("fail A")

            dag.add_node("A", action=failing)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: "success C")
            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(report.failed_nodes, ("A",))
            self.assertEqual(report.skipped_nodes, ("B",))
            self.assertEqual(report.succeeded_nodes, ("C",))

    def test_runner_retry_recovers(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            attempts = [0]

            def flaky():
                attempts[0] += 1
                if attempts[0] < 3:
                    raise KeyError("transient key error")
                return "recovered"

            dag.add_node("A", action=flaky, retries=2)
            report = runner.run()
            self.assertEqual(report.succeeded_nodes, ("A",))
            self.assertEqual(attempts[0], 3)
            self.assertEqual(report.results["A"].retries_attempted, 2)
            self.assertEqual(report.results["A"].value, "recovered")

    def test_runner_retry_exhausted(self):
        with enter_phase(system, registry=self.registry) as scope:
            self._setup()
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            attempts = [0]

            def always_fail():
                attempts[0] += 1
                raise TypeError("persistent type error")

            dag.add_node("A", action=always_fail, retries=1)
            report = runner.run()
            self.assertEqual(report.failed_nodes, ("A",))
            self.assertEqual(attempts[0], 2)
            self.assertEqual(report.results["A"].retries_attempted, 1)
            self.assertIsInstance(report.results["A"].error, TypeError)


if __name__ == "__main__":
    unittest.main()
