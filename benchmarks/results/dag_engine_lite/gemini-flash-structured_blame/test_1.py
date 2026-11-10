from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple
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


def sample_action() -> str:
    """Helper zero-argument callable returning a constant string."""
    return "result"


class DAGTest(unittest.TestCase):
    """Unit test suite for the concrete DAG singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_dag_error_hierarchy(self) -> None:
        """Verify exception class hierarchy rooted at DAGError."""
        self.assertTrue(issubclass(CycleError, DAGError))
        self.assertTrue(issubclass(NodeNotFoundError, DAGError))
        self.assertTrue(issubclass(DuplicateNodeError, DAGError))
        self.assertTrue(issubclass(NodeExecutionError, DAGError))

    def test_add_node_register_definition(self) -> None:
        """Verify adding a node registers definition into graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", sample_action, None, 10, 2)
            self.assertTrue(dag.has_node("task_a"))
            node_def = dag.get_node("task_a")
            self.assertIsInstance(node_def, NodeDefinition)
            self.assertEqual(node_def.node_id, "task_a")
            self.assertEqual(node_def.priority, 10)
            self.assertEqual(node_def.retries, 2)
            self.assertEqual(node_def.dependencies, frozenset())
            self.assertEqual(node_def.action(), "result")

    def test_add_node_directed_dependencies(self) -> None:
        """Verify adding a node with dependencies establishes directed edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("parent", sample_action, None, 0, 0)
            dag.add_node("child", sample_action, ["parent"], 0, 0)
            self.assertEqual(dag.get_dependencies("child"), {"parent"})
            self.assertEqual(dag.get_dependents("parent"), {"child"})

    def test_add_node_defer_dependency_checks(self) -> None:
        """Verify adding a node defers missing dependency existence checks."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", sample_action, ["unregistered_dep"], 0, 0)
            self.assertTrue(dag.has_node("orphan"))
            self.assertIn("unregistered_dep", dag.get_dependencies("orphan"))

    def test_add_node_duplicate_raises_error(self) -> None:
        """Verify adding a duplicate node raises DuplicateNodeError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node1", sample_action, None, 0, 0)
            with self.assertRaises(DuplicateNodeError) as ctx:
                dag.add_node("node1", sample_action, None, 5, 1)
            self.assertEqual(ctx.exception.node_id, "node1")

    def test_add_edge_directed_edge(self) -> None:
        """Verify add_edge establishes dependency edge from upstream to downstream."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_u", sample_action, None, 0, 0)
            dag.add_node("node_v", sample_action, None, 0, 0)
            dag.add_edge("node_u", "node_v")
            self.assertIn("node_u", dag.get_dependencies("node_v"))
            self.assertIn("node_v", dag.get_dependents("node_u"))

    def test_add_edge_missing_upstream_raises_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError when upstream node does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_v", sample_action, None, 0, 0)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("missing_u", "node_v")
            self.assertEqual(ctx.exception.node_id, "missing_u")

    def test_add_edge_missing_downstream_raises_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError when downstream node does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_u", sample_action, None, 0, 0)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("node_u", "missing_v")
            self.assertEqual(ctx.exception.node_id, "missing_v")

    def test_remove_node_purge_incident_edges(self) -> None:
        """Verify remove_node purges node definition and all incident edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("n1", sample_action, None, 0, 0)
            dag.add_node("n2", sample_action, ["n1"], 0, 0)
            dag.add_node("n3", sample_action, ["n2"], 0, 0)
            dag.remove_node("n2")
            self.assertFalse(dag.has_node("n2"))
            self.assertNotIn("n2", dag.all_nodes())
            self.assertEqual(dag.get_dependents("n1"), set())
            self.assertEqual(dag.get_dependencies("n3"), set())

    def test_remove_node_missing_raises_error(self) -> None:
        """Verify remove_node raises NodeNotFoundError for missing node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.remove_node("non_existent")
            self.assertEqual(ctx.exception.node_id, "non_existent")

    def test_has_node_membership(self) -> None:
        """Verify has_node returns correct presence boolean."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("present_node"))
            dag.add_node("present_node", sample_action, None, 0, 0)
            self.assertTrue(dag.has_node("present_node"))

    def test_get_node_missing_raises_error(self) -> None:
        """Verify get_node raises NodeNotFoundError for missing node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("absent")
            self.assertEqual(ctx.exception.node_id, "absent")

    def test_get_dependencies_missing_raises_error(self) -> None:
        """Verify get_dependencies raises NodeNotFoundError for missing node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependencies("unknown")
            self.assertEqual(ctx.exception.node_id, "unknown")

    def test_get_dependents_missing_raises_error(self) -> None:
        """Verify get_dependents raises NodeNotFoundError for missing node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependents("unknown")
            self.assertEqual(ctx.exception.node_id, "unknown")

    def test_all_nodes(self) -> None:
        """Verify all_nodes returns all registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            dag.add_node("x", sample_action, None, 0, 0)
            dag.add_node("y", sample_action, None, 0, 0)
            self.assertEqual(dag.all_nodes(), {"x", "y"})

    def test_validate_complete_valid(self) -> None:
        """Verify validate completes without error for valid acyclic graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("r", sample_action, None, 0, 0)
            dag.add_node("s", sample_action, ["r"], 0, 0)
            dag.validate()

    def test_validate_missing_dependency_raises_error(self) -> None:
        """Verify validate raises NodeNotFoundError when referenced dependency does not exist."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_with_missing", sample_action, ["missing_dep"], 0, 0)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "missing_dep")

    def test_validate_cycle_raises_error(self) -> None:
        """Verify validate raises CycleError on directed dependency cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c1", sample_action, ["c2"], 0, 0)
            dag.add_node("c2", sample_action, ["c1"], 0, 0)
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertIsInstance(ctx.exception.cycle, tuple)
            self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_topological_sort_dependency_order(self) -> None:
        """Verify topological_sort respects prerequisite execution order."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", sample_action, None, 0, 0)
            dag.add_node("second", sample_action, ["first"], 0, 0)
            dag.add_node("third", sample_action, ["second"], 0, 0)
            order = dag.topological_sort()
            self.assertEqual(order, ["first", "second", "third"])

    def test_topological_sort_tie_breaking(self) -> None:
        """Verify topological_sort breaks ties using priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("bravo", sample_action, None, 10, 0)
            dag.add_node("alpha", sample_action, None, 10, 0)
            dag.add_node("high_priority", sample_action, None, 20, 0)
            order = dag.topological_sort()
            self.assertEqual(order, ["high_priority", "alpha", "bravo"])

    def test_topological_sort_cycle_raises_error(self) -> None:
        """Verify topological_sort raises CycleError on cyclic graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("ca", sample_action, ["cb"], 0, 0)
            dag.add_node("cb", sample_action, ["ca"], 0, 0)
            with self.assertRaises(CycleError) as ctx:
                dag.topological_sort()
            self.assertIsInstance(ctx.exception.cycle, tuple)

    def test_find_roots(self) -> None:
        """Verify find_roots returns nodes with in-degree zero."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root1", sample_action, None, 0, 0)
            dag.add_node("root2", sample_action, None, 0, 0)
            dag.add_node("child", sample_action, ["root1", "root2"], 0, 0)
            self.assertEqual(dag.find_roots(), {"root1", "root2"})

    def test_find_leaves(self) -> None:
        """Verify find_leaves returns nodes with out-degree zero."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("parent", sample_action, None, 0, 0)
            dag.add_node("leaf1", sample_action, ["parent"], 0, 0)
            dag.add_node("leaf2", sample_action, ["parent"], 0, 0)
            self.assertEqual(dag.find_leaves(), {"leaf1", "leaf2"})

    def test_compute_critical_path_default_weights(self) -> None:
        """Verify critical path computation with default 1.0 duration weights."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", sample_action, None, 0, 0)
            dag.add_node("mid", sample_action, ["start"], 0, 0)
            dag.add_node("end", sample_action, ["mid"], 0, 0)
            dag.add_node("short", sample_action, None, 0, 0)
            dag.add_edge("short", "end")
            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, ["start", "mid", "end"])
            self.assertEqual(weight, 3.0)

    def test_compute_critical_path_custom_weights(self) -> None:
        """Verify critical path computation with custom duration weights."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", sample_action, None, 0, 0)
            dag.add_node("b", sample_action, None, 0, 0)
            dag.add_node("c", sample_action, None, 0, 0)
            dag.add_edge("a", "c")
            dag.add_edge("b", "c")
            durations = {"a": 2.0, "b": 10.0, "c": 3.0}
            path, weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["b", "c"])
            self.assertEqual(weight, 13.0)


class WaveSchedulerTest(unittest.TestCase):
    """Unit test suite for the concrete WaveScheduler singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_next_wave_ready_nodes_and_priority_order(self) -> None:
        """Verify next_wave returns ready nodes ordered by priority descending then node_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("task_low", sample_action, None, 1, 0)
            dag.add_node("task_high", sample_action, None, 10, 0)
            dag.add_node("task_mid", sample_action, None, 5, 0)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["task_high", "task_mid", "task_low"])

    def test_next_wave_empty_when_no_ready(self) -> None:
        """Verify next_wave returns empty list when no nodes are in ready state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("r1", sample_action, None, 0, 0)
            scheduler.mark_running("r1")
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_state_transition(self) -> None:
        """Verify mark_running transitions node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("node_x", sample_action, None, 0, 0)
            scheduler.mark_running("node_x")
            self.assertEqual(scheduler.get_state("node_x"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """Verify mark_succeeded promotes unlocked downstream nodes to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("parent1", sample_action, None, 0, 0)
            dag.add_node("parent2", sample_action, None, 0, 0)
            dag.add_node("child", sample_action, ["parent1", "parent2"], 0, 0)
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)
            scheduler.mark_running("parent1")
            scheduler.mark_succeeded("parent1")
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)
            scheduler.mark_running("parent2")
            scheduler.mark_succeeded("parent2")
            self.assertEqual(scheduler.get_state("child"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["child"])

    def test_mark_failed_fail_fast(self) -> None:
        """Verify mark_failed under FAIL_FAST policy cancels all remaining pending nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root_a", sample_action, None, 0, 0)
            dag.add_node("root_b", sample_action, None, 0, 0)
            dag.add_node("child_a", sample_action, ["root_a"], 0, 0)
            scheduler.mark_running("root_a")
            scheduler.mark_failed("root_a", FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("root_a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child_a"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("root_b"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream(self) -> None:
        """Verify mark_failed under SKIP_DOWNSTREAM policy skips transitive dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("f_root", sample_action, None, 0, 0)
            dag.add_node("f_mid", sample_action, ["f_root"], 0, 0)
            dag.add_node("f_leaf", sample_action, ["f_mid"], 0, 0)
            dag.add_node("indep", sample_action, None, 0, 0)
            scheduler.mark_running("f_root")
            scheduler.mark_failed("f_root", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("f_root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("f_mid"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("f_leaf"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("indep"), NodeState.READY)

    def test_mark_failed_skip_downstream_multipath(self) -> None:
        """Verify mark_failed under SKIP_DOWNSTREAM skips multi-path transitive dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", sample_action, None, 0, 0)
            dag.add_node("branch_a", sample_action, ["root"], 0, 0)
            dag.add_node("branch_b", sample_action, ["root"], 0, 0)
            dag.add_node("convergence", sample_action, ["branch_a", "branch_b"], 0, 0)
            dag.add_node("deep_child", sample_action, ["convergence"], 0, 0)
            dag.add_node("independent_root", sample_action, None, 0, 0)
            dag.add_node("independent_child", sample_action, ["independent_root"], 0, 0)
            scheduler.mark_running("root")
            scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("branch_a"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("branch_b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("convergence"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("deep_child"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent_root"), NodeState.READY)
            self.assertEqual(scheduler.get_state("independent_child"), NodeState.PENDING)

    def test_mark_failed_continue_on_error(self) -> None:
        """Verify mark_failed under CONTINUE_ON_ERROR policy leaves independent nodes eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("err_node", sample_action, None, 0, 0)
            dag.add_node("dep_node", sample_action, ["err_node"], 0, 0)
            dag.add_node("safe_node", sample_action, None, 0, 0)
            scheduler.mark_running("err_node")
            scheduler.mark_failed("err_node", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("err_node"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("dep_node"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("safe_node"), NodeState.READY)

    def test_is_finished_empty_dag(self) -> None:
        """Verify is_finished returns True for an empty graph."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_non_terminal_remaining(self) -> None:
        """Verify is_finished returns False when active non-terminal nodes remain."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("active", sample_action, None, 0, 0)
            dag.add_node("dependent", sample_action, ["active"], 0, 0)
            self.assertEqual(scheduler.get_state("active"), NodeState.READY)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.PENDING)
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_running_node_state(self) -> None:
        """Verify is_finished returns False when a node is in the RUNNING state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("running_task", sample_action, None, 0, 0)
            scheduler.mark_running("running_task")
            self.assertEqual(scheduler.get_state("running_task"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())
            dag.add_node("done_task", sample_action, None, 0, 0)
            scheduler.mark_running("done_task")
            scheduler.mark_succeeded("done_task")
            self.assertEqual(scheduler.get_state("done_task"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("running_task"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_all_terminal(self) -> None:
        """Verify is_finished returns True when all nodes have reached terminal states."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("term", sample_action, None, 0, 0)
            scheduler.mark_running("term")
            scheduler.mark_succeeded("term")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_blocked_by_failure(self) -> None:
        """Verify is_finished returns True when unexecuted nodes are blocked by failures."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("parent", sample_action, None, 0, 0)
            dag.add_node("child", sample_action, ["parent"], 0, 0)
            scheduler.mark_running("parent")
            scheduler.mark_failed("parent", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertTrue(scheduler.is_finished())

    def test_get_state_missing_node_raises_error(self) -> None:
        """Verify get_state raises NodeNotFoundError when node is not registered in DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError) as ctx:
                scheduler.get_state("non_existent_node")
            self.assertEqual(ctx.exception.node_id, "non_existent_node")

    def test_get_all_states(self) -> None:
        """Verify get_all_states reflects currently registered nodes and their states."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("m1", sample_action, None, 0, 0)
            dag.add_node("m2", sample_action, ["m1"], 0, 0)
            states = scheduler.get_all_states()
            self.assertEqual(states["m1"], NodeState.READY)
            self.assertEqual(states["m2"], NodeState.PENDING)

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Verify removing a node from DAG purges its state from wave scheduler tracking."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("to_remove", sample_action, None, 0, 0)
            self.assertIn("to_remove", scheduler.get_all_states())
            dag.remove_node("to_remove")
            self.assertNotIn("to_remove", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("to_remove")


class DAGRunnerTest(unittest.TestCase):
    """Unit test suite for the concrete DAGRunner singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_empty_graph(self) -> None:
        """Verify running an empty DAG returns report with zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertIsInstance(report, DAGRunReport)
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_sequential_waves_success(self) -> None:
        """Verify sequential wave execution produces consolidated DAGRunReport on success."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("task1", lambda: "val1", None, 10, 0)
            dag.add_node("task2", lambda: "val2", ["task1"], 5, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("task1", "task2"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertIn("task1", report.results)
            self.assertIn("task2", report.results)
            res1 = report.results["task1"]
            self.assertIsInstance(res1, NodeResult)
            self.assertEqual(res1.state, NodeState.SUCCEEDED)
            self.assertEqual(res1.value, "val1")
            self.assertIsNone(res1.error)
            self.assertEqual(res1.retries_attempted, 0)
            res2 = report.results["task2"]
            self.assertEqual(res2.state, NodeState.SUCCEEDED)
            self.assertEqual(res2.value, "val2")
            self.assertEqual(report.critical_path, ("task1", "task2"))

    def test_run_retry_failures_success(self) -> None:
        """Verify runner retries failed node action up to configured limit and succeeds."""
        attempt = 0

        def flaky_computation() -> str:
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise ValueError("temporary error")
            return "recovered_value"

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("flaky_node", flaky_computation, None, 0, 2)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(report.succeeded_nodes, ("flaky_node",))
            self.assertEqual(report.failed_nodes, ())
            res = report.results["flaky_node"]
            self.assertEqual(res.state, NodeState.SUCCEEDED)
            self.assertEqual(res.value, "recovered_value")
            self.assertEqual(res.retries_attempted, 1)

    def test_run_retry_exhausted_fail_fast(self) -> None:
        """Verify failure after retry exhaustion triggers FAIL_FAST cancelling pending nodes."""
        def permanent_failure() -> None:
            raise RuntimeError("permanent failure")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad_node", permanent_failure, None, 10, 1)
            dag.add_node("blocked_node", sample_action, ["bad_node"], 5, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(report.failed_nodes, ("bad_node",))
            self.assertIn("blocked_node", report.cancelled_nodes)
            res_bad = report.results["bad_node"]
            self.assertEqual(res_bad.state, NodeState.FAILED)
            self.assertIsNotNone(res_bad.error)
            self.assertEqual(res_bad.retries_attempted, 1)
            res_blocked = report.results["blocked_node"]
            self.assertEqual(res_blocked.state, NodeState.CANCELLED)

    def test_run_apply_failure_policy_skip_downstream(self) -> None:
        """Verify failure policy SKIP_DOWNSTREAM skips dependent nodes and continues independent."""
        def failing_task() -> None:
            raise RuntimeError("downstream must skip")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("fail_parent", failing_task, None, 10, 0)
            dag.add_node("skipped_child", sample_action, ["fail_parent"], 5, 0)
            dag.add_node("safe_branch", sample_action, None, 0, 0)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(report.failed_nodes, ("fail_parent",))
            self.assertIn("skipped_child", report.skipped_nodes)
            self.assertIn("safe_branch", report.succeeded_nodes)
            self.assertEqual(report.results["skipped_child"].state, NodeState.SKIPPED)
            self.assertEqual(report.results["safe_branch"].state, NodeState.SUCCEEDED)

    def test_run_apply_failure_policy_skip_downstream_multipath(self) -> None:
        """Verify runner skips multi-path transitive dependents under SKIP_DOWNSTREAM."""
        def failing_task() -> None:
            raise RuntimeError("multipath failure")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("mp_root", failing_task, None, 10, 0)
            dag.add_node("mp_left", sample_action, ["mp_root"], 5, 0)
            dag.add_node("mp_right", sample_action, ["mp_root"], 5, 0)
            dag.add_node("mp_converged", sample_action, ["mp_left", "mp_right"], 2, 0)
            dag.add_node("mp_final", sample_action, ["mp_converged"], 1, 0)
            dag.add_node("mp_other", sample_action, None, 0, 0)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(report.failed_nodes, ("mp_root",))
            self.assertIn("mp_left", report.skipped_nodes)
            self.assertIn("mp_right", report.skipped_nodes)
            self.assertIn("mp_converged", report.skipped_nodes)
            self.assertIn("mp_final", report.skipped_nodes)
            self.assertIn("mp_other", report.succeeded_nodes)
            self.assertEqual(report.results["mp_converged"].state, NodeState.SKIPPED)
            self.assertEqual(report.results["mp_final"].state, NodeState.SKIPPED)

    def test_run_apply_failure_policy_continue_on_error(self) -> None:
        """Verify failure policy CONTINUE_ON_ERROR skips blocked dependents while independent succeed."""
        def failing_task() -> None:
            raise RuntimeError("independent continues")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("err_source", failing_task, None, 10, 0)
            dag.add_node("blocked_task", sample_action, ["err_source"], 5, 0)
            dag.add_node("independent_task", sample_action, None, 1, 0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertIn("err_source", report.failed_nodes)
            self.assertIn("blocked_task", report.skipped_nodes)
            self.assertIn("independent_task", report.succeeded_nodes)

    def test_run_missing_dependency_raises_error(self) -> None:
        """Verify runner raises NodeNotFoundError when DAG contains missing dependency."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("invalid_node", sample_action, ["unregistered_dep"], 0, 0)
            with self.assertRaises(NodeNotFoundError) as ctx:
                runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(ctx.exception.node_id, "unregistered_dep")

    def test_run_cycle_raises_error(self) -> None:
        """Verify runner raises CycleError when DAG contains dependency cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("cycle_1", sample_action, ["cycle_2"], 0, 0)
            dag.add_node("cycle_2", sample_action, ["cycle_1"], 0, 0)
            with self.assertRaises(CycleError) as ctx:
                runner.run(FailurePolicy.FAIL_FAST)
            self.assertIsInstance(ctx.exception.cycle, tuple)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T20:16:33Z
# LAST_CHANGED: 2026-11-08T20:15:54Z
# CHANGE: Verify multi-path transitive dependent skipping under SKIP_DOWNSTREAM failure policy
# COVERAGE_AUDIT: 2026-11-08T20:16:33Z
# QA_AUDIT: 2026-11-08T20:16:17Z
# --- END AUTOFAB METADATA ---
