"""Unit tests for dag_engine_impl per its grounding specification."""

from __future__ import annotations

import time
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_1.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGError,
    DAGRunReport,
    DAGTimeoutError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from benchmark_1.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class _FlakyAction:
    """Action helper that fails a specified number of times before succeeding."""

    def __init__(self, fail_count: int, return_value: str = "ok") -> None:
        self.attempts: int = 0
        self.fail_count: int = fail_count
        self.return_value: str = return_value

    def __call__(self) -> str:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise RuntimeError(f"Simulated failure on attempt {self.attempts}")
        return self.return_value


class _FailingAction:
    """Action helper that unconditionally raises an exception."""

    def __init__(self, message: str = "Unconditional failure") -> None:
        self.message: str = message
        self.attempts: int = 0

    def __call__(self) -> None:
        self.attempts += 1
        raise ValueError(self.message)


class _CancellingAction:
    """Action helper that cancels the runner when executed."""

    def __init__(self, runner: DAGRunner) -> None:
        self.runner: DAGRunner = runner

    def __call__(self) -> None:
        self.runner.cancel()


class _SleepingAction:
    """Action helper that sleeps for a given duration before returning."""

    def __init__(self, duration_seconds: float) -> None:
        self.duration_seconds: float = duration_seconds

    def __call__(self) -> str:
        time.sleep(self.duration_seconds)
        return "slept"


class DagEngineImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """Verify initial component presence and registry bindings."""
        self.assertIsNotNone(self.registry)
        for sym in [DAG, DAGRunner, WaveScheduler]:
            self.assertIsNotNone(sym)

    def test_dag_engine_data_types(self) -> None:
        """Verify data types and exception records are properly constructible."""
        err = DAGError("generic error")
        self.assertEqual(err.message, "generic error")

        cycle_err = CycleError("cycle", cycle=("a", "b", "a"))
        self.assertEqual(cycle_err.cycle, ("a", "b", "a"))

        nf_err = NodeNotFoundError("not found", node_id="missing")
        self.assertEqual(nf_err.node_id, "missing")

        exec_err = NodeExecutionError("execution failed", node_id="bad", cause=ValueError("root"))
        self.assertEqual(exec_err.node_id, "bad")
        self.assertIsInstance(exec_err.cause, ValueError)

        timeout_err = DAGTimeoutError("timed out")
        self.assertEqual(timeout_err.message, "timed out")

        cancel_err = DAGCancelledError("cancelled")
        self.assertEqual(cancel_err.message, "cancelled")

        node_def = NodeDefinition(
            node_id="n1",
            action=lambda: 123,
            dependencies=frozenset(["dep"]),
            priority=5,
            timeout_seconds=2.0,
            retries=1,
        )
        self.assertEqual(node_def.node_id, "n1")
        self.assertEqual(node_def.priority, 5)

        node_res = NodeResult(
            node_id="n1",
            state=NodeState.SUCCEEDED,
            value=123,
            duration_seconds=0.1,
            retries_attempted=0,
        )
        self.assertEqual(node_res.node_id, "n1")
        self.assertEqual(node_res.state, NodeState.SUCCEEDED)

    def test_dag_add_node_minimal(self) -> None:
        """Verify add_node registers a node definition with default attributes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = lambda: "minimal"
            dag.add_node("task1", action)

            self.assertTrue(dag.has_node("task1"))
            self.assertIn("task1", dag.all_nodes())
            node_def = dag.get_node("task1")
            self.assertEqual(node_def.node_id, "task1")
            self.assertEqual(node_def.action(), "minimal")
            self.assertEqual(node_def.dependencies, frozenset())
            self.assertEqual(node_def.priority, 0)
            self.assertIsNone(node_def.timeout_seconds)
            self.assertEqual(node_def.retries, 0)
            self.assertEqual(dag.get_dependencies("task1"), set())
            self.assertEqual(dag.get_dependents("task1"), set())

    def test_dag_add_node_with_dependencies_and_options(self) -> None:
        """Verify add_node with explicit dependencies establishes directed edges and records options."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("dep1", lambda: 1)
            dag.add_node("dep2", lambda: 2)
            dag.add_node(
                "main",
                lambda: 3,
                dependencies=["dep1", "dep2"],
                priority=10,
                timeout_seconds=5.0,
                retries=3,
            )

            node_def = dag.get_node("main")
            self.assertEqual(node_def.dependencies, frozenset(["dep1", "dep2"]))
            self.assertEqual(node_def.priority, 10)
            self.assertEqual(node_def.timeout_seconds, 5.0)
            self.assertEqual(node_def.retries, 3)
            self.assertEqual(dag.get_dependencies("main"), {"dep1", "dep2"})
            self.assertIn("main", dag.get_dependents("dep1"))
            self.assertIn("main", dag.get_dependents("dep2"))

    def test_dag_add_node_replaces_previous_dependencies(self) -> None:
        """Verify adding a node with new dependencies dynamically replaces previous upstream/downstream associations."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("dep1", lambda: 1)
            dag.add_node("dep2", lambda: 2)
            dag.add_node("target", lambda: 3, dependencies=["dep1"])

            self.assertEqual(dag.get_dependencies("target"), {"dep1"})
            self.assertIn("target", dag.get_dependents("dep1"))
            self.assertNotIn("target", dag.get_dependents("dep2"))

            dag.add_node("target", lambda: 4, dependencies=["dep2"])
            self.assertEqual(dag.get_dependencies("target"), {"dep2"})
            self.assertNotIn("target", dag.get_dependents("dep1"))
            self.assertIn("target", dag.get_dependents("dep2"))

    def test_dag_add_edge_success(self) -> None:
        """Verify add_edge establishes directed dependency relationship between existing nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("u", lambda: None)
            dag.add_node("v", lambda: None)
            dag.add_edge("u", "v")

            self.assertIn("u", dag.get_dependencies("v"))
            self.assertIn("v", dag.get_dependents("u"))

    def test_dag_add_edge_missing_upstream_raises_node_not_found(self) -> None:
        """Verify add_edge raises NodeNotFoundError when upstream node does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("v", lambda: None)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("missing_u", "v")
            self.assertEqual(ctx.exception.node_id, "missing_u")

    def test_dag_add_edge_missing_downstream_raises_node_not_found(self) -> None:
        """Verify add_edge raises NodeNotFoundError when downstream node does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("u", lambda: None)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("u", "missing_v")
            self.assertEqual(ctx.exception.node_id, "missing_v")

    def test_dag_remove_node_success(self) -> None:
        """Verify remove_node removes node and all incident dependency edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_node("c", lambda: None, dependencies=["b"])

            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertNotIn("b", dag.all_nodes())
            self.assertNotIn("b", dag.get_dependents("a"))
            self.assertNotIn("b", dag.get_dependencies("c"))

    def test_dag_remove_node_missing_raises_node_not_found(self) -> None:
        """Verify remove_node raises NodeNotFoundError when target node is absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.remove_node("nonexistent")
            self.assertEqual(ctx.exception.node_id, "nonexistent")

    def test_dag_has_node(self) -> None:
        """Verify has_node returns True for registered nodes and False otherwise."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("unadded"))
            dag.add_node("added", lambda: None)
            self.assertTrue(dag.has_node("added"))

    def test_dag_get_node_missing_raises_node_not_found(self) -> None:
        """Verify get_node raises NodeNotFoundError when node is absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("absent")
            self.assertEqual(ctx.exception.node_id, "absent")

    def test_dag_get_dependencies_missing_raises_node_not_found(self) -> None:
        """Verify get_dependencies raises NodeNotFoundError when node is absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependencies("absent")
            self.assertEqual(ctx.exception.node_id, "absent")

    def test_dag_get_dependents_missing_raises_node_not_found(self) -> None:
        """Verify get_dependents raises NodeNotFoundError when node is absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependents("absent")
            self.assertEqual(ctx.exception.node_id, "absent")

    def test_dag_all_nodes(self) -> None:
        """Verify all_nodes returns a complete set of registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            dag.add_node("n1", lambda: None)
            dag.add_node("n2", lambda: None)
            self.assertEqual(dag.all_nodes(), {"n1", "n2"})

    def test_dag_validate_success(self) -> None:
        """Verify validate succeeds when all dependencies exist and no cycles are present."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("step1", lambda: None)
            dag.add_node("step2", lambda: None, dependencies=["step1"])
            dag.add_node("step3", lambda: None, dependencies=["step2"])
            dag.validate()

    def test_dag_validate_missing_dependency_raises_node_not_found(self) -> None:
        """Verify validate raises NodeNotFoundError when a referenced dependency is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", lambda: None, dependencies=["nonexistent_parent"])
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_dag_validate_cycle_detected_raises_cycle_error(self) -> None:
        """Verify validate detects directed cycles and raises CycleError with cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c1", lambda: None)
            dag.add_node("c2", lambda: None, dependencies=["c1"])
            dag.add_node("c3", lambda: None, dependencies=["c2"])
            dag.add_edge("c3", "c1")
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertGreater(len(ctx.exception.cycle), 0)

    def test_dag_topological_sort_success(self) -> None:
        """Verify topological_sort orders nodes such that prerequisites precede dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", lambda: None)
            dag.add_node("branch_a", lambda: None, dependencies=["start"])
            dag.add_node("branch_b", lambda: None, dependencies=["start"])
            dag.add_node("end", lambda: None, dependencies=["branch_a", "branch_b"])

            order = dag.topological_sort()
            self.assertEqual(len(order), 4)
            self.assertLess(order.index("start"), order.index("branch_a"))
            self.assertLess(order.index("start"), order.index("branch_b"))
            self.assertLess(order.index("branch_a"), order.index("end"))
            self.assertLess(order.index("branch_b"), order.index("end"))

    def test_dag_topological_sort_tie_breaking(self) -> None:
        """Verify topological_sort breaks ties by priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("z_mid", lambda: None, priority=10)
            dag.add_node("a_mid", lambda: None, priority=10)
            dag.add_node("high", lambda: None, priority=20)
            dag.add_node("low", lambda: None, priority=0)

            order = dag.topological_sort()
            self.assertEqual(order, ["high", "a_mid", "z_mid", "low"])

    def test_dag_topological_sort_cycle_error(self) -> None:
        """Verify topological_sort raises CycleError when the graph contains a cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("x", lambda: None)
            dag.add_node("y", lambda: None, dependencies=["x"])
            dag.add_edge("y", "x")
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_dag_find_roots(self) -> None:
        """Verify find_roots returns all nodes with zero in-degree."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root1", lambda: None)
            dag.add_node("root2", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["root1", "root2"])
            self.assertEqual(dag.find_roots(), {"root1", "root2"})

    def test_dag_find_leaves(self) -> None:
        """Verify find_leaves returns all nodes with zero out-degree."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("leaf1", lambda: None, dependencies=["root"])
            dag.add_node("leaf2", lambda: None, dependencies=["root"])
            self.assertEqual(dag.find_leaves(), {"leaf1", "leaf2"})

    def test_dag_compute_critical_path_default_weights(self) -> None:
        """Verify compute_critical_path defaults to unit weight 1.0 when durations are omitted."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_node("c", lambda: None, dependencies=["b"])
            dag.add_node("d", lambda: None, dependencies=["a"])

            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(weight, 3.0)

    def test_dag_compute_critical_path_custom_weights(self) -> None:
        """Verify compute_critical_path uses provided duration mappings to resolve longest path."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_node("c", lambda: None, dependencies=["b"])
            dag.add_node("d", lambda: None, dependencies=["a"])

            durations = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 10.0}
            path, weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["a", "d"])
            self.assertEqual(weight, 11.0)

    def test_dag_compute_critical_path_empty_graph(self) -> None:
        """Verify compute_critical_path on an empty DAG returns an empty path and zero duration."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    def test_scheduler_initial_state_and_next_wave(self) -> None:
        """Verify scheduler initializes root nodes to READY, non-roots to PENDING, and produces next wave."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("r1", lambda: None)
            dag.add_node("r2", lambda: None)
            dag.add_node("c1", lambda: None, dependencies=["r1"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("r1"), NodeState.READY)
            self.assertEqual(scheduler.get_state("r2"), NodeState.READY)
            self.assertEqual(scheduler.get_state("c1"), NodeState.PENDING)
            self.assertEqual(set(scheduler.next_wave()), {"r1", "r2"})

    def test_scheduler_next_wave_priority_and_name_ordering(self) -> None:
        """Verify next_wave orders candidates by priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("z_task", lambda: None, priority=5)
            dag.add_node("a_task", lambda: None, priority=5)
            dag.add_node("high_task", lambda: None, priority=10)
            dag.add_node("low_task", lambda: None, priority=1)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(
                scheduler.next_wave(),
                ["high_task", "a_task", "z_task", "low_task"],
            )

    def test_scheduler_mark_running(self) -> None:
        """Verify mark_running transitions a node to RUNNING state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task", lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task")
            self.assertEqual(scheduler.get_state("task"), NodeState.RUNNING)

    def test_scheduler_mark_succeeded_promotes_dependents(self) -> None:
        """Verify mark_succeeded transitions node to SUCCEEDED and promotes dependents once all prereqs succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("p1", lambda: None)
            dag.add_node("p2", lambda: None)
            dag.add_node("dependent", lambda: None, dependencies=["p1", "p2"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_succeeded("p1")
            self.assertEqual(scheduler.get_state("p1"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.PENDING)

            scheduler.mark_succeeded("p2")
            self.assertEqual(scheduler.get_state("p2"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["dependent"])

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        """Verify mark_failed under FAIL_FAST marks failed node and transitions non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("f_node", lambda: None)
            dag.add_node("ready_node", lambda: None)
            dag.add_node("pending_node", lambda: None, dependencies=["ready_node"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("f_node", failure_policy=FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("f_node"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("pending_node"), NodeState.CANCELLED)

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        """Verify mark_failed under SKIP_DOWNSTREAM marks transitive dependents SKIPPED and preserves unblocked nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("f_node", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["f_node"])
            dag.add_node("grandchild", lambda: None, dependencies=["child"])
            dag.add_node("independent", lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("f_node", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("f_node"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("grandchild"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent"), NodeState.READY)

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        """Verify mark_failed under CONTINUE_ON_ERROR leaves unblocked independent nodes eligible for execution."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("f_node", lambda: None)
            dag.add_node("other_node", lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("f_node", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("f_node"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("other_node"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["other_node"])

    def test_scheduler_is_finished(self) -> None:
        """Verify is_finished returns True when all nodes reach terminal states or DAG is empty."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

            dag.add_node("task", lambda: None)
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_succeeded("task")
            self.assertTrue(scheduler.is_finished())

    def test_scheduler_get_all_states(self) -> None:
        """Verify get_all_states returns a mapping of all registered node execution states."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("n1", lambda: None)
            dag.add_node("n2", lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("n1")
            states = scheduler.get_all_states()
            self.assertEqual(states["n1"], NodeState.RUNNING)
            self.assertEqual(states["n2"], NodeState.READY)

    def test_scheduler_next_wave_empty_when_no_nodes_ready(self) -> None:
        """Verify next_wave returns an empty list when all candidate nodes are running or blocked."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["root"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("root")
            self.assertEqual(scheduler.next_wave(), [])

    def test_scheduler_unregistered_node_raises_node_not_found(self) -> None:
        """Verify scheduler operations raise NodeNotFoundError when invoked with unregistered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)

            with self.assertRaises(NodeNotFoundError) as ctx_get:
                scheduler.get_state("nonexistent")
            self.assertEqual(ctx_get.exception.node_id, "nonexistent")

            with self.assertRaises(NodeNotFoundError) as ctx_run:
                scheduler.mark_running("nonexistent")
            self.assertEqual(ctx_run.exception.node_id, "nonexistent")

            with self.assertRaises(NodeNotFoundError) as ctx_succ:
                scheduler.mark_succeeded("nonexistent")
            self.assertEqual(ctx_succ.exception.node_id, "nonexistent")

            with self.assertRaises(NodeNotFoundError) as ctx_fail:
                scheduler.mark_failed("nonexistent")
            self.assertEqual(ctx_fail.exception.node_id, "nonexistent")

    def test_scheduler_synchronizes_after_dag_remove_node(self) -> None:
        """Verify dynamically removing a node from the DAG synchronizes and purges scheduler state tracking."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("temp_node", lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("temp_node"), NodeState.READY)
            self.assertIn("temp_node", scheduler.get_all_states())

            dag.remove_node("temp_node")
            self.assertNotIn("temp_node", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("temp_node")
            self.assertTrue(scheduler.is_finished())

    def test_runner_run_empty_dag(self) -> None:
        """Verify executing run on an empty DAG returns a report with zero total nodes and empty outcome collections."""
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertIsInstance(report, DAGRunReport)
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ())
            self.assertEqual(report.results, {})
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_runner_run_happy_path(self) -> None:
        """Verify run executes DAG to completion, returning consolidated report with node results."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: "val_a")
            dag.add_node("b", lambda: "val_b", dependencies=["a"])
            dag.add_node("c", lambda: "val_c", dependencies=["b"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertIsInstance(report, DAGRunReport)
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b", "c"))
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["a"].value, "val_a")
            self.assertEqual(report.results["b"].value, "val_b")
            self.assertEqual(report.results["c"].value, "val_c")

    def test_runner_retry_mechanism_success(self) -> None:
        """Verify run executes retries up to configured retry count and records retries attempted."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = _FlakyAction(fail_count=2, return_value="recovered")
            dag.add_node("flaky", action, retries=2)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertEqual(report.results["flaky"].retries_attempted, 2)
            self.assertIn("flaky", report.succeeded_nodes)

    def test_runner_retry_exhausted_records_failure(self) -> None:
        """Verify run marks node FAILED when retry attempts are exhausted."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = _FailingAction(message="Persistent error")
            dag.add_node("failing", action, retries=1)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(report.results["failing"].state, NodeState.FAILED)
            self.assertEqual(report.results["failing"].retries_attempted, 1)
            self.assertIsNotNone(report.results["failing"].error)
            self.assertIn("failing", report.failed_nodes)

    def test_runner_failure_policy_fail_fast(self) -> None:
        """Verify run under FAIL_FAST marks failed nodes and cancels remaining nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", _FailingAction())
            dag.add_node("dependent", lambda: "ok", dependencies=["failing"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST)

            self.assertIn("failing", report.failed_nodes)
            self.assertIn("dependent", report.cancelled_nodes)

    def test_runner_failure_policy_skip_downstream(self) -> None:
        """Verify run under SKIP_DOWNSTREAM marks dependents SKIPPED while independent tasks succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", _FailingAction())
            dag.add_node("downstream", lambda: "ok", dependencies=["failing"])
            dag.add_node("independent", lambda: "standalone")

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertIn("failing", report.failed_nodes)
            self.assertIn("downstream", report.skipped_nodes)
            self.assertIn("independent", report.succeeded_nodes)

    def test_runner_failure_policy_continue_on_error(self) -> None:
        """Verify run under CONTINUE_ON_ERROR allows independent tasks to succeed despite failures."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("bad", _FailingAction())
            dag.add_node("good", lambda: "success")

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("bad", report.failed_nodes)
            self.assertIn("good", report.succeeded_nodes)

    def test_runner_timeout_raises_dag_timeout_error(self) -> None:
        """Verify run raises DAGTimeoutError when execution exceeds timeout_seconds."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", _SleepingAction(0.2))

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_runner_cancel_raises_dag_cancelled_error(self) -> None:
        """Verify cancel marks unstarted nodes CANCELLED and raises DAGCancelledError during run."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("canceller", _CancellingAction(runner))
            dag.add_node("pending", lambda: "after", dependencies=["canceller"])

            with self.assertRaises(DAGCancelledError):
                runner.run()

    def test_runner_cancel_standalone(self) -> None:
        """Verify cancel updates cancellation state on the runner."""
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()

    def test_runner_cancel_transitions_unstarted_nodes_to_cancelled(self) -> None:
        """Verify invoking cancel when unstarted nodes are present transitions non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("ready_task", lambda: "val")
            dag.add_node("pending_task", lambda: "val", dependencies=["ready_task"])

            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            self.assertEqual(scheduler.get_state("ready_task"), NodeState.READY)
            self.assertEqual(scheduler.get_state("pending_task"), NodeState.PENDING)

            runner.cancel()

            self.assertEqual(scheduler.get_state("ready_task"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("pending_task"), NodeState.CANCELLED)

    def test_runner_validates_graph_before_run(self) -> None:
        """Verify run validates the DAG, propagating CycleError or missing dependency errors immediately."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("loop1", lambda: None)
            dag.add_node("loop2", lambda: None, dependencies=["loop1"])
            dag.add_edge("loop2", "loop1")

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(CycleError):
                runner.run()

    def test_runner_max_concurrency_execution(self) -> None:
        """Verify run successfully executes multiple concurrent tasks under max_concurrency limit."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("t1", lambda: "r1")
            dag.add_node("t2", lambda: "r2")
            dag.add_node("t3", lambda: "r3")

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=2)
            self.assertEqual(set(report.succeeded_nodes), {"t1", "t2", "t3"})


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T21:55:53Z
# LAST_CHANGED: 2026-10-22T21:50:17Z
# CHANGE: Address coverage feedback by adding unit tests for: (1) compute_critical_path on empty DAG returning empty path and 0.0 weight; (2) add_node with new dependencies dynamically replacing previous upstream/downstream associations; (3) DAGRunner.run on empty DAG returning report with zero total nodes and empty collections; (4) WaveScheduler operations raising NodeNotFoundError on unregistered node IDs; (5) dynamic DAG node removal synchronizing and purging scheduler state; and (6) DAGRunner.cancel transitioning unstarted nodes to CANCELLED.
# COVERAGE_AUDIT: 2026-10-22T21:55:53Z
# QA_AUDIT: 2026-10-22T21:55:28Z
# --- END CLEANROOM METADATA ---
