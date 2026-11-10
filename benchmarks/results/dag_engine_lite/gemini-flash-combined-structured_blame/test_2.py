from __future__ import annotations

from typing import Any, Callable, List, Mapping, Optional, Set, Tuple
import unittest

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    enter_phase,
    system,
)
from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
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


class FlakyAction:
    """Action helper that fails a specified number of times before succeeding."""

    def __init__(self, fail_count: int, return_value: str = "ok") -> None:
        self.fail_count: int = fail_count
        self.return_value: str = return_value
        self.call_count: int = 0

    def __call__(self) -> str:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise RuntimeError(f"Simulated failure attempt {self.call_count}")
        return self.return_value


class ExecutionTracker:
    """Action helper tracking execution sequence across nodes."""

    def __init__(self) -> None:
        self.order: List[str] = []

    def make_action(self, node_id: str, return_value: str = "ok") -> Callable[[], str]:
        def action() -> str:
            self.order.append(node_id)
            return return_value

        return action


class DAGTest(unittest.TestCase):
    """Unit tests for the concrete DAG implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope: LifecycleScope = enter_phase(system, registry=self.registry)
        self.scope: LifecycleScope = self.phase_scope.__enter__()
        self.dag: DAG = self.scope.get_singleton(DAG)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_add_node_and_get_node(self) -> None:
        """Verify adding a node and retrieving its immutable definition."""
        def sample_action() -> int:
            return 42

        self.dag.add_node("task_a", sample_action, dependencies=None, priority=10, retries=2)
        self.assertTrue(self.dag.has_node("task_a"))
        self.assertIn("task_a", self.dag.all_nodes())

        definition: NodeDefinition[Any] = self.dag.get_node("task_a")
        self.assertEqual(definition.node_id, "task_a")
        self.assertEqual(definition.priority, 10)
        self.assertEqual(definition.retries, 2)
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.action(), 42)

    def test_add_node_with_dependencies(self) -> None:
        """Verify adding a node with dependencies establishes directed edges."""
        self.dag.add_node("dep_a", lambda: "a", dependencies=None, priority=0, retries=0)
        self.dag.add_node("task_b", lambda: "b", dependencies=["dep_a"], priority=5, retries=0)

        self.assertEqual(self.dag.get_dependencies("task_b"), {"dep_a"})
        self.assertEqual(self.dag.get_dependents("dep_a"), {"task_b"})

    def test_add_node_duplicate_raises_error(self) -> None:
        """Verify adding duplicate node raises DuplicateNodeError."""
        self.dag.add_node("node_dup", lambda: 1, dependencies=None, priority=0, retries=0)
        with self.assertRaises(DuplicateNodeError) as ctx:
            self.dag.add_node("node_dup", lambda: 2, dependencies=None, priority=0, retries=0)
        self.assertEqual(ctx.exception.node_id, "node_dup")

    def test_add_node_defers_dependency_checks(self) -> None:
        """Verify missing dependencies are deferred without eager error at addition time."""
        self.dag.add_node("node_pending", lambda: None, dependencies=["unregistered"], priority=0, retries=0)
        self.assertTrue(self.dag.has_node("node_pending"))
        self.assertIn("unregistered", self.dag.get_dependencies("node_pending"))

    def test_add_edge_success(self) -> None:
        """Verify adding directed edge between existing nodes."""
        self.dag.add_node("upstream", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("downstream", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_edge("upstream", "downstream")

        self.assertIn("upstream", self.dag.get_dependencies("downstream"))
        self.assertIn("downstream", self.dag.get_dependents("upstream"))

    def test_add_edge_missing_nodes_raise_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError when either node is missing."""
        self.dag.add_node("existing", lambda: None, dependencies=None, priority=0, retries=0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("existing", "nonexistent")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("nonexistent", "existing")

    def test_remove_node_success(self) -> None:
        """Verify removing a node purges incident dependency edges."""
        self.dag.add_node("src", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("mid", lambda: None, dependencies=["src"], priority=0, retries=0)
        self.dag.add_node("dst", lambda: None, dependencies=["mid"], priority=0, retries=0)

        self.dag.remove_node("mid")
        self.assertFalse(self.dag.has_node("mid"))
        self.assertNotIn("mid", self.dag.all_nodes())
        self.assertNotIn("mid", self.dag.get_dependents("src"))
        self.assertNotIn("mid", self.dag.get_dependencies("dst"))

    def test_remove_node_missing_raises_error(self) -> None:
        """Verify removing non-existent node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("unknown_node")

    def test_has_node_returns_false_for_unknown(self) -> None:
        """Verify has_node returns False for unregistered identifiers."""
        self.assertFalse(self.dag.has_node("unregistered_id"))

    def test_get_node_missing_raises_error(self) -> None:
        """Verify get_node on unregistered node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("absent_node")

    def test_get_dependencies_missing_raises_error(self) -> None:
        """Verify get_dependencies on unregistered node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("absent_node")

    def test_get_dependents_missing_raises_error(self) -> None:
        """Verify get_dependents on unregistered node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("absent_node")

    def test_validate_complete_valid(self) -> None:
        """Verify validate succeeds when dependencies exist and no cycle."""
        self.dag.add_node("root", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("leaf", lambda: None, dependencies=["root"], priority=0, retries=0)
        self.dag.validate()

    def test_validate_missing_dependency_raises_error(self) -> None:
        """Verify validate raises NodeNotFoundError for dangling dependency."""
        self.dag.add_node("orphan", lambda: None, dependencies=["missing_dep"], priority=0, retries=0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_validate_cycle_raises_error(self) -> None:
        """Verify validate raises CycleError upon detecting directed cycle."""
        self.dag.add_node("c1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("c2", lambda: None, dependencies=["c1"], priority=0, retries=0)
        self.dag.add_edge("c2", "c1")
        with self.assertRaises(CycleError) as ctx:
            self.dag.validate()
        self.assertTrue(len(ctx.exception.cycle) >= 2)

    def test_topological_sort_valid_order(self) -> None:
        """Verify topological sort returns valid dependency ordering."""
        self.dag.add_node("p1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("p2", lambda: None, dependencies=["p1"], priority=0, retries=0)
        self.dag.add_node("p3", lambda: None, dependencies=["p2"], priority=0, retries=0)

        order: List[str] = self.dag.topological_sort()
        self.assertEqual(order, ["p1", "p2", "p3"])

    def test_topological_sort_tie_breaking(self) -> None:
        """Verify topological sort breaks ties by priority descending, then node_id ascending."""
        self.dag.add_node("low", lambda: None, dependencies=None, priority=1, retries=0)
        self.dag.add_node("high_b", lambda: None, dependencies=None, priority=10, retries=0)
        self.dag.add_node("high_a", lambda: None, dependencies=None, priority=10, retries=0)

        order: List[str] = self.dag.topological_sort()
        self.assertEqual(order, ["high_a", "high_b", "low"])

    def test_topological_sort_cycle_raises_error(self) -> None:
        """Verify topological sort raises CycleError when directed cycle exists."""
        self.dag.add_node("loop_a", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("loop_b", lambda: None, dependencies=["loop_a"], priority=0, retries=0)
        self.dag.add_edge("loop_b", "loop_a")
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """Verify identification of root nodes and leaf nodes."""
        self.dag.add_node("r1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("r2", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("m", lambda: None, dependencies=["r1"], priority=0, retries=0)
        self.dag.add_node("l1", lambda: None, dependencies=["m"], priority=0, retries=0)
        self.dag.add_node("l2", lambda: None, dependencies=["r2"], priority=0, retries=0)

        self.assertEqual(self.dag.find_roots(), {"r1", "r2"})
        self.assertEqual(self.dag.find_leaves(), {"l1", "l2"})

    def test_compute_critical_path_default_weights(self) -> None:
        """Verify critical path computation with default unit durations."""
        self.dag.add_node("n1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("n2", lambda: None, dependencies=["n1"], priority=0, retries=0)
        self.dag.add_node("n3", lambda: None, dependencies=["n2"], priority=0, retries=0)
        self.dag.add_node("short", lambda: None, dependencies=["n1"], priority=0, retries=0)

        path, weight = self.dag.compute_critical_path(None)
        self.assertEqual(path, ["n1", "n2", "n3"])
        self.assertAlmostEqual(weight, 3.0)

    def test_compute_critical_path_custom_weights(self) -> None:
        """Verify critical path computation with customized duration mapping."""
        self.dag.add_node("start", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("heavy", lambda: None, dependencies=["start"], priority=0, retries=0)
        self.dag.add_node("light", lambda: None, dependencies=["start"], priority=0, retries=0)
        self.dag.add_node("end", lambda: None, dependencies=["heavy", "light"], priority=0, retries=0)

        durations: Mapping[str, float] = {
            "start": 2.0,
            "heavy": 10.0,
            "light": 1.0,
            "end": 3.0,
        }
        path, weight = self.dag.compute_critical_path(durations)
        self.assertEqual(path, ["start", "heavy", "end"])
        self.assertAlmostEqual(weight, 15.0)


class WaveSchedulerTest(unittest.TestCase):
    """Unit tests for the concrete WaveScheduler implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope: LifecycleScope = enter_phase(system, registry=self.registry)
        self.scope: LifecycleScope = self.phase_scope.__enter__()
        self.dag: DAG = self.scope.get_singleton(DAG)
        self.scheduler: WaveScheduler = self.scope.get_singleton(WaveScheduler)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_empty_dag_is_finished_and_next_wave_empty(self) -> None:
        """Verify empty DAG is immediately finished and yields empty wave."""
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), [])

    def test_next_wave_ready_nodes_and_priority_ordering(self) -> None:
        """Verify next_wave returns ready nodes ordered by priority then id."""
        self.dag.add_node("w_low", lambda: None, dependencies=None, priority=1, retries=0)
        self.dag.add_node("w_high_b", lambda: None, dependencies=None, priority=10, retries=0)
        self.dag.add_node("w_high_a", lambda: None, dependencies=None, priority=10, retries=0)

        wave: List[str] = self.scheduler.next_wave()
        self.assertEqual(wave, ["w_high_a", "w_high_b", "w_low"])

    def test_mark_running_state_transition(self) -> None:
        """Verify mark_running transitions node to RUNNING state."""
        self.dag.add_node("run_node", lambda: None, dependencies=None, priority=0, retries=0)
        self.scheduler.mark_running("run_node")
        self.assertEqual(self.scheduler.get_state("run_node"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """Verify mark_succeeded unblocks and promotes dependents to READY."""
        self.dag.add_node("parent", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("child", lambda: None, dependencies=["parent"], priority=0, retries=0)

        self.scheduler.mark_running("parent")
        self.scheduler.mark_succeeded("parent")

        self.assertEqual(self.scheduler.get_state("parent"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.get_state("child"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["child"])

    def test_mark_failed_skip_downstream(self) -> None:
        """Verify mark_failed with SKIP_DOWNSTREAM policy skips transitive dependents."""
        self.dag.add_node("fail_src", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("dep_1", lambda: None, dependencies=["fail_src"], priority=0, retries=0)
        self.dag.add_node("dep_2", lambda: None, dependencies=["dep_1"], priority=0, retries=0)
        self.dag.add_node("other", lambda: None, dependencies=None, priority=0, retries=0)

        self.scheduler.mark_running("fail_src")
        self.scheduler.mark_failed("fail_src", FailurePolicy.SKIP_DOWNSTREAM)

        self.assertEqual(self.scheduler.get_state("fail_src"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("dep_1"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("dep_2"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("other"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["other"])

    def test_mark_failed_fail_fast(self) -> None:
        """Verify mark_failed with FAIL_FAST policy cancels remaining non-terminal nodes."""
        self.dag.add_node("node_1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("node_2", lambda: None, dependencies=None, priority=0, retries=0)

        self.scheduler.mark_running("node_1")
        self.scheduler.mark_failed("node_1", FailurePolicy.FAIL_FAST)

        self.assertEqual(self.scheduler.get_state("node_1"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("node_2"), NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_mark_failed_continue_on_error(self) -> None:
        """Verify mark_failed with CONTINUE_ON_ERROR skips blocked but preserves independent nodes."""
        self.dag.add_node("f_node", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("f_child", lambda: None, dependencies=["f_node"], priority=0, retries=0)
        self.dag.add_node("indep", lambda: None, dependencies=None, priority=0, retries=0)

        self.scheduler.mark_running("f_node")
        self.scheduler.mark_failed("f_node", FailurePolicy.CONTINUE_ON_ERROR)

        self.assertEqual(self.scheduler.get_state("f_node"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("f_child"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("indep"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["indep"])

    def test_is_finished_transitions(self) -> None:
        """Verify is_finished handles non-terminal and terminal states correctly."""
        self.dag.add_node("t_root", lambda: None, dependencies=None, priority=0, retries=0)
        self.assertFalse(self.scheduler.is_finished())

        self.scheduler.mark_running("t_root")
        self.assertFalse(self.scheduler.is_finished())

        self.scheduler.mark_succeeded("t_root")
        self.assertTrue(self.scheduler.is_finished())

    def test_get_state_missing_node_raises_error(self) -> None:
        """Verify get_state on unregistered node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("unknown_node_state")

    def test_get_all_states(self) -> None:
        """Verify get_all_states captures current execution states of registered nodes."""
        self.dag.add_node("st1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("st2", lambda: None, dependencies=None, priority=0, retries=0)

        states: Mapping[str, NodeState] = self.scheduler.get_all_states()
        self.assertIn("st1", states)
        self.assertIn("st2", states)
        self.assertEqual(states["st1"], NodeState.READY)
        self.assertEqual(states["st2"], NodeState.READY)

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Verify removing node from DAG purges it from scheduler state."""
        self.dag.add_node("temp_node", lambda: None, dependencies=None, priority=0, retries=0)
        _ = self.scheduler.next_wave()
        self.assertIn("temp_node", self.scheduler.get_all_states())

        self.dag.remove_node("temp_node")
        self.assertNotIn("temp_node", self.scheduler.get_all_states())
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("temp_node")


class DAGRunnerTest(unittest.TestCase):
    """Unit tests for the concrete DAGRunner implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope: LifecycleScope = enter_phase(system, registry=self.registry)
        self.scope: LifecycleScope = self.phase_scope.__enter__()
        self.dag: DAG = self.scope.get_singleton(DAG)
        self.scheduler: WaveScheduler = self.scope.get_singleton(WaveScheduler)
        self.runner: DAGRunner = self.scope.get_singleton(DAGRunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_run_success_sequential_waves(self) -> None:
        """Verify sequential wave execution and consolidated report generation."""
        tracker = ExecutionTracker()
        self.dag.add_node("w1", tracker.make_action("w1", "val1"), dependencies=None, priority=10, retries=0)
        self.dag.add_node("w2", tracker.make_action("w2", "val2"), dependencies=["w1"], priority=5, retries=0)
        self.dag.add_node("w3", tracker.make_action("w3", "val3"), dependencies=["w1"], priority=0, retries=0)
        self.dag.add_node("w4", tracker.make_action("w4", "val4"), dependencies=["w2", "w3"], priority=0, retries=0)

        report: DAGRunReport = self.runner.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(report.total_nodes, 4)
        self.assertEqual(set(report.succeeded_nodes), {"w1", "w2", "w3", "w4"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertTrue(report.wall_clock_seconds >= 0.0)
        self.assertTrue(len(report.critical_path) > 0)

        res_w1: NodeResult[Any] = report.results["w1"]
        self.assertEqual(res_w1.state, NodeState.SUCCEEDED)
        self.assertEqual(res_w1.value, "val1")
        self.assertEqual(res_w1.retries_attempted, 0)
        self.assertEqual(tracker.order[0], "w1")
        self.assertEqual(tracker.order[-1], "w4")

    def test_run_validates_graph_missing_dependency(self) -> None:
        """Verify runner validates graph before execution, detecting missing dependencies."""
        self.dag.add_node("broken", lambda: None, dependencies=["ghost"], priority=0, retries=0)
        with self.assertRaises(NodeNotFoundError):
            self.runner.run(FailurePolicy.FAIL_FAST)

    def test_run_validates_graph_cycle(self) -> None:
        """Verify runner validates graph before execution, detecting directed cycles."""
        self.dag.add_node("cycle_1", lambda: None, dependencies=None, priority=0, retries=0)
        self.dag.add_node("cycle_2", lambda: None, dependencies=["cycle_1"], priority=0, retries=0)
        self.dag.add_edge("cycle_2", "cycle_1")
        with self.assertRaises(CycleError):
            self.runner.run(FailurePolicy.FAIL_FAST)

    def test_run_retry_failures_then_succeed(self) -> None:
        """Verify runner retries failed actions up to definition limit."""
        action = FlakyAction(fail_count=2, return_value="success_after_retries")
        self.dag.add_node("retry_node", action, dependencies=None, priority=0, retries=2)

        report: DAGRunReport = self.runner.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(report.succeeded_nodes, ("retry_node",))
        self.assertEqual(report.failed_nodes, ())
        result: NodeResult[Any] = report.results["retry_node"]
        self.assertEqual(result.state, NodeState.SUCCEEDED)
        self.assertEqual(result.value, "success_after_retries")
        self.assertEqual(result.retries_attempted, 2)
        self.assertEqual(action.call_count, 3)

    def test_run_retry_exhausted_fail_fast(self) -> None:
        """Verify runner records failure and cancels remaining nodes on retry exhaustion."""
        action = FlakyAction(fail_count=5)
        self.dag.add_node("exhaust_node", action, dependencies=None, priority=10, retries=1)
        self.dag.add_node("indep_node", lambda: "ok", dependencies=None, priority=5, retries=0)

        report: DAGRunReport = self.runner.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(report.failed_nodes, ("exhaust_node",))
        self.assertIn("indep_node", report.cancelled_nodes)
        result: NodeResult[Any] = report.results["exhaust_node"]
        self.assertEqual(result.state, NodeState.FAILED)
        self.assertEqual(result.retries_attempted, 1)
        self.assertIsNotNone(result.error)

    def test_run_skip_downstream_policy(self) -> None:
        """Verify runner applies SKIP_DOWNSTREAM policy skipping dependent tasks."""
        action = FlakyAction(fail_count=1)
        self.dag.add_node("failed_task", action, dependencies=None, priority=10, retries=0)
        self.dag.add_node("blocked_task", lambda: "skip", dependencies=["failed_task"], priority=5, retries=0)
        self.dag.add_node("clean_task", lambda: "ok", dependencies=None, priority=5, retries=0)

        report: DAGRunReport = self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)

        self.assertEqual(report.failed_nodes, ("failed_task",))
        self.assertIn("blocked_task", report.skipped_nodes)
        self.assertIn("clean_task", report.succeeded_nodes)
        self.assertEqual(report.results["blocked_task"].state, NodeState.SKIPPED)

    def test_run_continue_on_error_policy(self) -> None:
        """Verify runner applies CONTINUE_ON_ERROR policy continuing independent tasks."""
        action = FlakyAction(fail_count=1)
        self.dag.add_node("f_root", action, dependencies=None, priority=10, retries=0)
        self.dag.add_node("f_child", lambda: "skip", dependencies=["f_root"], priority=5, retries=0)
        self.dag.add_node("f_other", lambda: "clean", dependencies=None, priority=5, retries=0)

        report: DAGRunReport = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)

        self.assertEqual(report.failed_nodes, ("f_root",))
        self.assertIn("f_child", report.skipped_nodes)
        self.assertIn("f_other", report.succeeded_nodes)

    def test_run_empty_dag(self) -> None:
        """Verify runner executes cleanly on empty DAG."""
        report: DAGRunReport = self.runner.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.critical_path, ())
        self.assertEqual(len(report.results), 0)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:59:43Z
# LAST_CHANGED: 2026-11-09T22:31:34Z
# CHANGE: Implement comprehensive unit test suite for DAG, WaveScheduler, and DAGRunner covering graph operations, cycle detection, topological sorting, tie-breaking, failure policies, retries, and critical path computation.
# COVERAGE_AUDIT: 2026-11-09T22:59:43Z
# QA_AUDIT: 2026-11-09T22:59:24Z
# --- END AUTOFAB METADATA ---
