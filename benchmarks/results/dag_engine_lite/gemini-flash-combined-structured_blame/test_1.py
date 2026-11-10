from __future__ import annotations

from typing import Any, Mapping, Optional
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from dag_engine_lite.lib.dag_engine_lite import (
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
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def default_action() -> str:
    """Action callback returning a fixed success string."""
    return "ok"


def failing_action() -> None:
    """Action callback that unconditionally raises a RuntimeError."""
    raise RuntimeError("Simulated failure")


class FlakyAction:
    """Action callback that fails a configured number of times before succeeding."""

    def __init__(self, failures_before_success: int, return_value: str = "ok") -> None:
        self.attempts: int = 0
        self.failures_before_success: int = failures_before_success
        self.return_value: str = return_value

    def __call__(self) -> str:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            raise RuntimeError(f"Simulated failure attempt {self.attempts}")
        return self.return_value


class DAGTest(unittest.TestCase):
    """Unit tests for the DAG singleton implementation verifying contracts and invariants."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_happy_path(self) -> None:
        """Verify adding a valid task node registers its immutable definition and state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=10, retries=2)

            self.assertTrue(dag.has_node("task_a"))
            self.assertEqual(dag.all_nodes(), {"task_a"})
            definition = dag.get_node("task_a")
            self.assertEqual(definition.node_id, "task_a")
            self.assertEqual(definition.priority, 10)
            self.assertEqual(definition.retries, 2)
            self.assertEqual(definition.dependencies, frozenset())

    def test_add_node_duplicate_raises_error(self) -> None:
        """Verify adding an already registered node raises DuplicateNodeError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)

            with self.assertRaises(DuplicateNodeError) as ctx:
                dag.add_node("task_a", default_action, None, priority=5, retries=1)
            self.assertEqual(ctx.exception.node_id, "task_a")

    def test_add_node_defers_missing_dependency_checks(self) -> None:
        """Verify add_node allows non-existent dependencies without eagerly raising NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            self.assertTrue(dag.has_node("task_b"))

    def test_add_node_with_dependencies_establishes_edges(self) -> None:
        """Verify add_node with dependencies establishes upstream and downstream relationships."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)

            self.assertEqual(dag.get_dependencies("task_b"), {"task_a"})
            self.assertEqual(dag.get_dependents("task_a"), {"task_b"})

    def test_add_edge_happy_path(self) -> None:
        """Verify add_edge creates a directed dependency edge between registered nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, None, priority=0, retries=0)
            dag.add_edge("task_a", "task_b")

            self.assertEqual(dag.get_dependencies("task_b"), {"task_a"})
            self.assertEqual(dag.get_dependents("task_a"), {"task_b"})

    def test_add_edge_missing_upstream_raises_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError if the upstream node does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_b", default_action, None, priority=0, retries=0)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("missing_upstream", "task_b")
            self.assertEqual(ctx.exception.node_id, "missing_upstream")

    def test_add_edge_missing_downstream_raises_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError if the downstream node does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("task_a", "missing_downstream")
            self.assertEqual(ctx.exception.node_id, "missing_downstream")

    def test_remove_node_happy_path(self) -> None:
        """Verify remove_node purges the node and all its incident dependency edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_node("task_c", default_action, ["task_b"], priority=0, retries=0)

            dag.remove_node("task_b")
            self.assertFalse(dag.has_node("task_b"))
            self.assertEqual(dag.all_nodes(), {"task_a", "task_c"})
            self.assertEqual(dag.get_dependents("task_a"), set())
            self.assertEqual(dag.get_dependencies("task_c"), set())

    def test_remove_node_missing_raises_error(self) -> None:
        """Verify remove_node raises NodeNotFoundError when referencing an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.remove_node("missing_node")
            self.assertEqual(ctx.exception.node_id, "missing_node")

    def test_has_node_nonexistent_returns_false(self) -> None:
        """Verify has_node returns False for unregistered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("unknown_node"))

    def test_get_node_missing_raises_error(self) -> None:
        """Verify get_node raises NodeNotFoundError when node is not registered."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("missing_node")
            self.assertEqual(ctx.exception.node_id, "missing_node")

    def test_get_dependencies_missing_raises_error(self) -> None:
        """Verify get_dependencies raises NodeNotFoundError when node is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependencies("missing_node")
            self.assertEqual(ctx.exception.node_id, "missing_node")

    def test_get_dependents_missing_raises_error(self) -> None:
        """Verify get_dependents raises NodeNotFoundError when node is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependents("missing_node")
            self.assertEqual(ctx.exception.node_id, "missing_node")

    def test_all_nodes_empty_and_populated(self) -> None:
        """Verify all_nodes returns an empty set on fresh graph and all nodes when populated."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())

            dag.add_node("n1", default_action, None, priority=0, retries=0)
            dag.add_node("n2", default_action, None, priority=0, retries=0)
            self.assertEqual(dag.all_nodes(), {"n1", "n2"})

    def test_validate_valid_graph_completes(self) -> None:
        """Verify validate succeeds without error on a complete, acyclic graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.validate()

    def test_validate_missing_dependency_raises_error(self) -> None:
        """Verify validate raises NodeNotFoundError if a referenced dependency is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_b", default_action, ["missing_task"], priority=0, retries=0)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "missing_task")

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """Verify validate raises CycleError when a dependency cycle exists."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_edge("task_b", "task_a")

            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_topological_sort_dependency_order(self) -> None:
        """Verify topological_sort orders prerequisite nodes before dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_node("task_c", default_action, ["task_b"], priority=0, retries=0)

            order = dag.topological_sort()
            self.assertEqual(order, ["task_a", "task_b", "task_c"])

    def test_topological_sort_tie_breaking(self) -> None:
        """Verify topological_sort resolves ties using priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_low", default_action, None, priority=1, retries=0)
            dag.add_node("task_z_high", default_action, None, priority=10, retries=0)
            dag.add_node("task_a_high", default_action, None, priority=10, retries=0)

            order = dag.topological_sort()
            self.assertEqual(order, ["task_a_high", "task_z_high", "task_low"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """Verify topological_sort raises CycleError when the graph contains a cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_edge("task_b", "task_a")

            with self.assertRaises(CycleError) as ctx:
                dag.topological_sort()
            self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_find_roots_and_leaves(self) -> None:
        """Verify find_roots finds in-degree zero nodes and find_leaves finds out-degree zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_1", default_action, None, priority=0, retries=0)
            dag.add_node("root_2", default_action, None, priority=0, retries=0)
            dag.add_node("mid", default_action, ["root_1", "root_2"], priority=0, retries=0)
            dag.add_node("leaf", default_action, ["mid"], priority=0, retries=0)

            self.assertEqual(dag.find_roots(), {"root_1", "root_2"})
            self.assertEqual(dag.find_leaves(), {"leaf"})

    def test_compute_critical_path_default_durations(self) -> None:
        """Verify critical path computation defaults unspecified durations to 1.0."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_node("task_c", default_action, ["task_b"], priority=0, retries=0)

            path, total_weight = dag.compute_critical_path(None)
            self.assertEqual(path, ["task_a", "task_b", "task_c"])
            self.assertAlmostEqual(total_weight, 3.0)

    def test_compute_critical_path_custom_durations(self) -> None:
        """Verify critical path computation selects the longest weighted path."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", default_action, None, priority=0, retries=0)
            dag.add_node("heavy", default_action, ["start"], priority=0, retries=0)
            dag.add_node("light", default_action, ["start"], priority=0, retries=0)
            dag.add_node("end", default_action, ["heavy", "light"], priority=0, retries=0)

            durations: Mapping[str, float] = {
                "start": 2.0,
                "heavy": 10.0,
                "light": 1.0,
                "end": 3.0,
            }
            path, total_weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["start", "heavy", "end"])
            self.assertAlmostEqual(total_weight, 15.0)


class WaveSchedulerTest(unittest.TestCase):
    """Unit tests for the WaveScheduler singleton verifying scheduling state transitions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_scheduler_empty_dag(self) -> None:
        """Verify scheduler on empty DAG reports finished immediately and empty next_wave."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(scheduler.get_all_states(), {})

    def test_scheduler_initial_ready_and_priority_order(self) -> None:
        """Verify roots are initialized to READY and next_wave orders by priority then node_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_low", default_action, None, priority=1, retries=0)
            dag.add_node("task_z_high", default_action, None, priority=10, retries=0)
            dag.add_node("task_a_high", default_action, None, priority=10, retries=0)
            dag.add_node("dependent", default_action, ["task_low"], priority=5, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.get_state("task_low"), NodeState.READY)
            self.assertEqual(scheduler.get_state("task_a_high"), NodeState.READY)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.PENDING)

            wave = scheduler.next_wave()
            self.assertEqual(wave, ["task_a_high", "task_z_high", "task_low"])

    def test_scheduler_mark_running_and_succeeded_promotes_dependents(self) -> None:
        """Verify transitioning a node to SUCCEEDED promotes satisfied downstream nodes to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("task_a"), NodeState.READY)
            self.assertEqual(scheduler.get_state("task_b"), NodeState.PENDING)

            scheduler.mark_running("task_a")
            self.assertEqual(scheduler.get_state("task_a"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_succeeded("task_a")
            self.assertEqual(scheduler.get_state("task_a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("task_b"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["task_b"])

            scheduler.mark_running("task_b")
            self.assertEqual(scheduler.get_state("task_b"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("task_b")
            self.assertTrue(scheduler.is_finished())

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        """Verify mark_failed under FAIL_FAST cancels all remaining non-terminal nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_node("task_c", default_action, None, priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task_a")
            scheduler.mark_failed("task_a", FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("task_a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("task_b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("task_c"), NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        """Verify mark_failed under SKIP_DOWNSTREAM marks transitive dependents as SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_node("task_c", default_action, ["task_b"], priority=0, retries=0)
            dag.add_node("task_d", default_action, None, priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task_a")
            scheduler.mark_failed("task_a", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("task_a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("task_b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("task_c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("task_d"), NodeState.READY)
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        """Verify mark_failed under CONTINUE_ON_ERROR leaves independent nodes eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_node("task_d", default_action, None, priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task_a")
            scheduler.mark_failed("task_a", FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("task_a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("task_b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("task_d"), NodeState.READY)
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_is_finished_when_blocked_by_failure(self) -> None:
        """Verify is_finished returns True when all remaining nodes are blocked by failed dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task_a")
            scheduler.mark_failed("task_a", FailurePolicy.CONTINUE_ON_ERROR)

            self.assertTrue(scheduler.is_finished())

    def test_scheduler_is_finished_non_terminal_running_node(self) -> None:
        """Verify is_finished returns False when any node is in RUNNING state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("task_a")
            self.assertEqual(scheduler.get_state("task_a"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_is_finished_single_running_node(self) -> None:
        """Verify is_finished returns False for a single-node graph when that node is RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_single", default_action, None, priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task_single")
            self.assertEqual(scheduler.get_state("task_single"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_get_state_missing_raises_error(self) -> None:
        """Verify get_state raises NodeNotFoundError when referencing an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError) as ctx:
                scheduler.get_state("missing_node")
            self.assertEqual(ctx.exception.node_id, "missing_node")

    def test_scheduler_purges_state_on_dag_remove_node(self) -> None:
        """Verify removing a node from DAG purges it from scheduler get_all_states."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, None, priority=0, retries=0)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertIn("task_b", scheduler.get_all_states())

            dag.remove_node("task_b")
            self.assertNotIn("task_b", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError) as ctx:
                scheduler.get_state("task_b")
            self.assertEqual(ctx.exception.node_id, "task_b")


class DAGRunnerTest(unittest.TestCase):
    """Unit tests for the DAGRunner singleton verifying complete execution workflows."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_runner_empty_dag(self) -> None:
        """Verify runner execution on an empty graph returns an empty report."""
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ())
            self.assertEqual(report.results, {})
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_runner_happy_path_sequential_execution(self) -> None:
        """Verify sequential wave execution and consolidated report generation for valid DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", lambda: "res_a", None, priority=0, retries=0)
            dag.add_node("task_b", lambda: "res_b", ["task_a"], priority=0, retries=0)
            dag.add_node("task_c", lambda: "res_c", ["task_b"], priority=0, retries=0)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"task_a", "task_b", "task_c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(len(report.critical_path), 3)

            res_a = report.results["task_a"]
            self.assertEqual(res_a.state, NodeState.SUCCEEDED)
            self.assertEqual(res_a.value, "res_a")
            self.assertGreaterEqual(res_a.duration_seconds, 0.0)

            res_b = report.results["task_b"]
            self.assertEqual(res_b.state, NodeState.SUCCEEDED)
            self.assertEqual(res_b.value, "res_b")

            res_c = report.results["task_c"]
            self.assertEqual(res_c.state, NodeState.SUCCEEDED)
            self.assertEqual(res_c.value, "res_c")

    def test_runner_retry_success(self) -> None:
        """Verify failed action retries up to configured retry limit and succeeds."""
        with enter_phase(system, registry=self.registry) as scope:
            flaky = FlakyAction(failures_before_success=1, return_value="recovered")
            dag = scope.get_singleton(DAG)
            dag.add_node("flaky_task", flaky, None, priority=0, retries=2)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertIn("flaky_task", report.succeeded_nodes)
            res = report.results["flaky_task"]
            self.assertEqual(res.state, NodeState.SUCCEEDED)
            self.assertEqual(res.value, "recovered")
            self.assertEqual(res.retries_attempted, 1)

    def test_runner_retry_exhausted_fail_fast(self) -> None:
        """Verify exhausted retries mark node FAILED and apply FAIL_FAST cancellation."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing_task", failing_action, None, priority=0, retries=1)
            dag.add_node("downstream_task", default_action, ["failing_task"], priority=0, retries=0)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertIn("failing_task", report.failed_nodes)
            self.assertIn("downstream_task", report.cancelled_nodes)

            res = report.results["failing_task"]
            self.assertEqual(res.state, NodeState.FAILED)
            self.assertEqual(res.retries_attempted, 1)
            self.assertIsNotNone(res.error)

    def test_runner_failure_skip_downstream(self) -> None:
        """Verify failure under SKIP_DOWNSTREAM skips downstream nodes and executes independent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing_task", failing_action, None, priority=0, retries=0)
            dag.add_node("downstream_1", default_action, ["failing_task"], priority=0, retries=0)
            dag.add_node("downstream_2", default_action, ["downstream_1"], priority=0, retries=0)
            dag.add_node("independent_task", default_action, None, priority=0, retries=0)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)

            self.assertIn("failing_task", report.failed_nodes)
            self.assertIn("downstream_1", report.skipped_nodes)
            self.assertIn("downstream_2", report.skipped_nodes)
            self.assertIn("independent_task", report.succeeded_nodes)
            self.assertEqual(report.results["downstream_1"].state, NodeState.SKIPPED)

    def test_runner_failure_continue_on_error(self) -> None:
        """Verify failure under CONTINUE_ON_ERROR skips blocked nodes while running independent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing_task", failing_action, None, priority=0, retries=0)
            dag.add_node("downstream_task", default_action, ["failing_task"], priority=0, retries=0)
            dag.add_node("independent_task", default_action, None, priority=0, retries=0)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("failing_task", report.failed_nodes)
            self.assertIn("downstream_task", report.skipped_nodes)
            self.assertIn("independent_task", report.succeeded_nodes)

    def test_runner_validates_cycles_before_execution(self) -> None:
        """Verify runner raises CycleError prior to wave execution if graph contains a cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, None, priority=0, retries=0)
            dag.add_node("task_b", default_action, ["task_a"], priority=0, retries=0)
            dag.add_edge("task_b", "task_a")

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(CycleError) as ctx:
                runner.run(FailurePolicy.FAIL_FAST)
            self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_runner_validates_missing_dependencies_before_execution(self) -> None:
        """Verify runner raises NodeNotFoundError prior to wave execution if dependency is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", default_action, ["missing_dep"], priority=0, retries=0)

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(NodeNotFoundError) as ctx:
                runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(ctx.exception.node_id, "missing_dep")


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T22:52:20Z
# LAST_CHANGED: 2026-11-08T21:49:11Z
# CHANGE: Add test cases covering is_finished returning False when nodes are in RUNNING state
# COVERAGE_AUDIT: 2026-11-08T22:52:20Z
# QA_AUDIT: 2026-11-08T22:51:52Z
# --- END AUTOFAB METADATA ---
