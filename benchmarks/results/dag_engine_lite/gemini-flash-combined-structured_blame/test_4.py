from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple
import unittest

from support.lib.lifecycle import LifecycleTestCase
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
from dag_engine_lite.lib.dag_engine_lite_impl import DAG, DAGRunner, WaveScheduler


class DataTypesTest(unittest.TestCase):
    """Unit tests verifying data types, exception models, and enumeration values."""

    def test_dag_error_initialization(self) -> None:
        """Verify DAGError captures diagnostic message."""
        err = DAGError(message="graph failure")
        self.assertEqual(err.message, "graph failure")
        self.assertIsInstance(err, Exception)

    def test_cycle_error_fields(self) -> None:
        """Verify CycleError captures message and cycle sequence tuple."""
        err = CycleError(message="cycle detected", cycle=("A", "B", "A"))
        self.assertEqual(err.message, "cycle detected")
        self.assertEqual(err.cycle, ("A", "B", "A"))
        self.assertIsInstance(err, DAGError)

    def test_node_not_found_error_fields(self) -> None:
        """Verify NodeNotFoundError captures message and missing node identifier."""
        err = NodeNotFoundError(message="missing node", node_id="node_x")
        self.assertEqual(err.message, "missing node")
        self.assertEqual(err.node_id, "node_x")
        self.assertIsInstance(err, DAGError)

    def test_duplicate_node_error_fields(self) -> None:
        """Verify DuplicateNodeError captures message and duplicate node identifier."""
        err = DuplicateNodeError(message="duplicate node", node_id="node_a")
        self.assertEqual(err.message, "duplicate node")
        self.assertEqual(err.node_id, "node_a")
        self.assertIsInstance(err, DAGError)

    def test_node_execution_error_fields(self) -> None:
        """Verify NodeExecutionError captures message, failed node identifier, and underlying cause."""
        cause = ValueError("computation error")
        err = NodeExecutionError(message="execution failed", node_id="task_1", cause=cause)
        self.assertEqual(err.message, "execution failed")
        self.assertEqual(err.node_id, "task_1")
        self.assertIs(err.cause, cause)
        self.assertIsInstance(err, DAGError)

    def test_node_state_enum_values(self) -> None:
        """Verify NodeState enumeration defines all contracted execution lifecycle values."""
        self.assertEqual(NodeState.PENDING.value, "pending")
        self.assertEqual(NodeState.READY.value, "ready")
        self.assertEqual(NodeState.RUNNING.value, "running")
        self.assertEqual(NodeState.SUCCEEDED.value, "succeeded")
        self.assertEqual(NodeState.FAILED.value, "failed")
        self.assertEqual(NodeState.CANCELLED.value, "cancelled")
        self.assertEqual(NodeState.SKIPPED.value, "skipped")

    def test_failure_policy_enum_values(self) -> None:
        """Verify FailurePolicy enumeration defines all contracted execution strategies."""
        self.assertEqual(FailurePolicy.FAIL_FAST.value, "fail_fast")
        self.assertEqual(FailurePolicy.CONTINUE_ON_ERROR.value, "continue_on_error")
        self.assertEqual(FailurePolicy.SKIP_DOWNSTREAM.value, "skip_downstream")

    def test_node_definition_fields_and_defaults(self) -> None:
        """Verify NodeDefinition encapsulates task action, dependencies, priority, and retries."""
        action = lambda: 100
        deps = frozenset(["dep_a", "dep_b"])
        node_def = NodeDefinition(node_id="task_1", action=action, dependencies=deps, priority=5, retries=2)
        self.assertEqual(node_def.node_id, "task_1")
        self.assertIs(node_def.action, action)
        self.assertEqual(node_def.dependencies, deps)
        self.assertEqual(node_def.priority, 5)
        self.assertEqual(node_def.retries, 2)

        default_def = NodeDefinition(node_id="task_def", action=action, dependencies=frozenset())
        self.assertEqual(default_def.priority, 0)
        self.assertEqual(default_def.retries, 0)

    def test_node_result_fields_and_defaults(self) -> None:
        """Verify NodeResult captures execution outcome, return value, error, duration, and retries."""
        cause = RuntimeError("fail")
        result = NodeResult(
            node_id="task_1",
            state=NodeState.FAILED,
            value=None,
            error=cause,
            duration_seconds=0.15,
            retries_attempted=1,
        )
        self.assertEqual(result.node_id, "task_1")
        self.assertEqual(result.state, NodeState.FAILED)
        self.assertIsNone(result.value)
        self.assertIs(result.error, cause)
        self.assertEqual(result.duration_seconds, 0.15)
        self.assertEqual(result.retries_attempted, 1)

        default_result = NodeResult(node_id="task_2", state=NodeState.SUCCEEDED)
        self.assertIsNone(default_result.value)
        self.assertIsNone(default_result.error)
        self.assertEqual(default_result.duration_seconds, 0.0)
        self.assertEqual(default_result.retries_attempted, 0)

    def test_dag_run_report_fields(self) -> None:
        """Verify DAGRunReport aggregates node outcomes, execution duration, and critical path."""
        res_a = NodeResult(node_id="A", state=NodeState.SUCCEEDED, value="done")
        report = DAGRunReport(
            total_nodes=1,
            succeeded_nodes=("A",),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.5,
            critical_path=("A",),
            results={"A": res_a},
        )
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("A",))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.wall_clock_seconds, 0.5)
        self.assertEqual(report.critical_path, ("A",))
        self.assertEqual(report.results, {"A": res_a})


class DAGTest(LifecycleTestCase):
    """Unit tests for the DAG singleton implementation."""

    target = DAG

    def test_add_node_success(self) -> None:
        """Verify adding a node registers definition into the graph."""
        def dummy_action() -> int:
            return 42

        self.sut.add_node("A", dummy_action, None, 10, 1)
        self.assertTrue(self.sut.has_node("A"))
        node_def = self.sut.get_node("A")
        self.assertEqual(node_def.node_id, "A")
        self.assertEqual(node_def.priority, 10)
        self.assertEqual(node_def.retries, 1)
        self.assertEqual(node_def.dependencies, frozenset())
        self.assertEqual(node_def.action(), 42)
        self.assertEqual(self.sut.all_nodes(), {"A"})

    def test_add_node_with_dependencies_creates_directed_edges(self) -> None:
        """Verify adding node with dependencies creates directed edges."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.assertEqual(self.sut.get_dependencies("B"), {"A"})
        self.assertEqual(self.sut.get_dependents("A"), {"B"})

    def test_add_node_defers_missing_dependency_checks(self) -> None:
        """Verify adding a node defers missing dependency existence checks."""
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.assertTrue(self.sut.has_node("B"))
        self.assertEqual(self.sut.get_dependencies("B"), {"A"})

    def test_add_node_duplicate_raises_duplicate_node_error(self) -> None:
        """Verify adding a duplicate node identifier raises DuplicateNodeError."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        with self.assertRaises(DuplicateNodeError) as ctx:
            self.sut.add_node("A", lambda: None, None, 0, 0)
        self.assertEqual(ctx.exception.node_id, "A")

    def test_add_edge_success(self) -> None:
        """Verify adding directed edge establishes dependency between nodes."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, None, 0, 0)
        self.sut.add_edge("A", "B")
        self.assertEqual(self.sut.get_dependencies("B"), {"A"})
        self.assertEqual(self.sut.get_dependents("A"), {"B"})

    def test_add_edge_missing_upstream_raises_node_not_found_error(self) -> None:
        """Verify adding edge with missing upstream node raises NodeNotFoundError."""
        self.sut.add_node("B", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.add_edge("A", "B")
        self.assertEqual(ctx.exception.node_id, "A")

    def test_add_edge_missing_downstream_raises_node_not_found_error(self) -> None:
        """Verify adding edge with missing downstream node raises NodeNotFoundError."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.add_edge("A", "B")
        self.assertEqual(ctx.exception.node_id, "B")

    def test_remove_node_success_and_purges_incident_edges(self) -> None:
        """Verify removing node purges the node and all incident edges."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, None, 0, 0)
        self.sut.add_node("C", lambda: None, None, 0, 0)
        self.sut.add_edge("A", "B")
        self.sut.add_edge("B", "C")
        self.sut.remove_node("B")
        self.assertFalse(self.sut.has_node("B"))
        self.assertEqual(self.sut.all_nodes(), {"A", "C"})
        self.assertEqual(self.sut.get_dependents("A"), set())
        self.assertEqual(self.sut.get_dependencies("C"), set())

    def test_remove_node_missing_raises_node_not_found_error(self) -> None:
        """Verify removing missing node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.remove_node("missing")
        self.assertEqual(ctx.exception.node_id, "missing")

    def test_has_node_returns_true_for_existing_false_for_missing(self) -> None:
        """Verify has_node returns true for registered nodes and false for unregistered."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.assertTrue(self.sut.has_node("A"))
        self.assertFalse(self.sut.has_node("B"))

    def test_get_node_success(self) -> None:
        """Verify get_node retrieves registered node definition."""
        self.sut.add_node("A", lambda: "ok", None, 3, 2)
        node_def = self.sut.get_node("A")
        self.assertEqual(node_def.node_id, "A")
        self.assertEqual(node_def.priority, 3)
        self.assertEqual(node_def.retries, 2)
        self.assertEqual(node_def.action(), "ok")

    def test_get_node_missing_raises_node_not_found_error(self) -> None:
        """Verify get_node raises NodeNotFoundError for unregistered node."""
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.get_node("missing")
        self.assertEqual(ctx.exception.node_id, "missing")

    def test_get_dependencies_success(self) -> None:
        """Verify get_dependencies returns direct upstream prerequisites."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        deps = self.sut.get_dependencies("B")
        self.assertEqual(deps, {"A"})
        deps.add("C")
        self.assertEqual(self.sut.get_dependencies("B"), {"A"})

    def test_get_dependencies_missing_raises_node_not_found_error(self) -> None:
        """Verify get_dependencies raises NodeNotFoundError for unregistered node."""
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.get_dependencies("missing")
        self.assertEqual(ctx.exception.node_id, "missing")

    def test_get_dependents_success(self) -> None:
        """Verify get_dependents returns direct downstream dependents."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        dependents = self.sut.get_dependents("A")
        self.assertEqual(dependents, {"B"})
        dependents.add("C")
        self.assertEqual(self.sut.get_dependents("A"), {"B"})

    def test_get_dependents_missing_raises_node_not_found_error(self) -> None:
        """Verify get_dependents raises NodeNotFoundError for unregistered node."""
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.get_dependents("missing")
        self.assertEqual(ctx.exception.node_id, "missing")

    def test_all_nodes_returns_all_registered_node_ids(self) -> None:
        """Verify all_nodes returns all registered node identifiers."""
        self.assertEqual(self.sut.all_nodes(), set())
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, None, 0, 0)
        all_ids = self.sut.all_nodes()
        self.assertEqual(all_ids, {"A", "B"})
        all_ids.add("C")
        self.assertEqual(self.sut.all_nodes(), {"A", "B"})

    def test_validate_valid_dag_completes_without_error(self) -> None:
        """Verify validate completes without error on valid acyclic graph."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.add_node("C", lambda: None, ["B"], 0, 0)
        self.sut.validate()

    def test_validate_missing_dependency_raises_node_not_found_error(self) -> None:
        """Verify validate raises NodeNotFoundError when referenced dependency is missing."""
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.validate()
        self.assertEqual(ctx.exception.node_id, "A")

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """Verify validate raises CycleError when directed cycle exists."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, None, 0, 0)
        self.sut.add_node("dead_end", lambda: None, ["A"], 0, 0)
        self.sut.add_edge("A", "B")
        self.sut.add_edge("B", "A")
        with self.assertRaises(CycleError) as ctx:
            self.sut.validate()
        self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_validate_cycle_search_backtracking_traversal(self) -> None:
        """Verify graph validation detects directed cycles with dead-end backtracking."""
        self.sut.add_node("root", lambda: None, None, 10, 0)
        self.sut.add_node("loop_a", lambda: None, ["root"], 0, 0)
        self.sut.add_node("loop_b", lambda: None, None, 0, 0)
        self.sut.add_edge("loop_a", "loop_b")
        self.sut.add_edge("loop_b", "loop_a")
        self.sut.add_node("dead_1", lambda: None, ["loop_a"], 0, 0)
        self.sut.add_node("dead_2", lambda: None, ["dead_1"], 0, 0)
        with self.assertRaises(CycleError) as ctx:
            self.sut.validate()
        self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_topological_sort_valid_dag(self) -> None:
        """Verify topological sort returns valid dependency ordering."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.add_node("C", lambda: None, ["B"], 0, 0)
        order = self.sut.topological_sort()
        self.assertEqual(order, ["A", "B", "C"])

    def test_topological_sort_tie_breaking_by_priority_and_name(self) -> None:
        """Verify topological sort breaks ties using priority descending and name ascending."""
        self.sut.add_node("A", lambda: None, None, 10, 0)
        self.sut.add_node("B", lambda: None, None, 20, 0)
        self.sut.add_node("C", lambda: None, None, 20, 0)
        self.sut.add_node("D", lambda: None, None, 5, 0)
        order = self.sut.topological_sort()
        self.assertEqual(order, ["B", "C", "A", "D"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """Verify topological sort raises CycleError when directed cycle exists."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, None, 0, 0)
        self.sut.add_node("dead_end", lambda: None, ["A"], 0, 0)
        self.sut.add_edge("A", "B")
        self.sut.add_edge("B", "A")
        with self.assertRaises(CycleError) as ctx:
            self.sut.topological_sort()
        self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_topological_sort_cycle_search_backtracking_traversal(self) -> None:
        """Verify cycle detection backtracks through dead-end paths to locate directed cycle."""
        self.sut.add_node("root", lambda: None, None, 10, 0)
        self.sut.add_node("loop_a", lambda: None, ["root"], 0, 0)
        self.sut.add_node("loop_b", lambda: None, None, 0, 0)
        self.sut.add_node("loop_c", lambda: None, None, 0, 0)
        self.sut.add_edge("loop_a", "loop_b")
        self.sut.add_edge("loop_b", "loop_c")
        self.sut.add_edge("loop_c", "loop_a")
        self.sut.add_node("0_dead_pre_1", lambda: None, ["loop_a"], 0, 0)
        self.sut.add_node("0_dead_pre_2", lambda: None, ["0_dead_pre_1"], 0, 0)
        self.sut.add_node("z_dead_post_1", lambda: None, ["loop_b"], 0, 0)
        self.sut.add_node("z_dead_post_2", lambda: None, ["z_dead_post_1"], 0, 0)
        self.sut.add_edge("loop_c", "0_dead_pre_1")
        with self.assertRaises(CycleError) as ctx:
            self.sut.topological_sort()
        self.assertTrue(len(ctx.exception.cycle) > 0)
        cycle_set = set(ctx.exception.cycle)
        self.assertTrue("loop_a" in cycle_set and "loop_b" in cycle_set and "loop_c" in cycle_set)

    def test_find_roots_returns_nodes_with_in_degree_zero(self) -> None:
        """Verify find_roots returns all nodes with zero in-degree."""
        self.assertEqual(self.sut.find_roots(), set())
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.add_node("C", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.find_roots(), {"A", "C"})

    def test_find_leaves_returns_nodes_with_out_degree_zero(self) -> None:
        """Verify find_leaves returns all nodes with zero out-degree."""
        self.assertEqual(self.sut.find_leaves(), set())
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.add_node("C", lambda: None, ["A"], 0, 0)
        self.assertEqual(self.sut.find_leaves(), {"B", "C"})

    def test_compute_critical_path_with_default_durations(self) -> None:
        """Verify critical path calculation with default unit duration weights."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.add_node("C", lambda: None, ["B"], 0, 0)
        path, duration = self.sut.compute_critical_path(None)
        self.assertEqual(path, ["A", "B", "C"])
        self.assertEqual(duration, 3.0)

    def test_compute_critical_path_with_custom_durations(self) -> None:
        """Verify critical path calculation with custom node duration weights."""
        self.sut.add_node("A", lambda: None, None, 0, 0)
        self.sut.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.add_node("C", lambda: None, ["A"], 0, 0)
        self.sut.add_node("D", lambda: None, ["B", "C"], 0, 0)
        durations = {"A": 1.0, "B": 5.0, "C": 2.0, "D": 1.0}
        path, duration = self.sut.compute_critical_path(durations)
        self.assertEqual(path, ["A", "B", "D"])
        self.assertEqual(duration, 7.0)

    def test_compute_critical_path_empty_dag(self) -> None:
        """Verify critical path on empty graph returns empty path and zero duration."""
        path, duration = self.sut.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(duration, 0.0)


class WaveSchedulerTest(LifecycleTestCase):
    """Unit tests for the WaveScheduler singleton implementation."""

    target = WaveScheduler

    def test_next_wave_initial_returns_ready_roots_ordered_by_priority(self) -> None:
        """Verify next_wave returns ready root nodes ordered by priority."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 5, 0)
        dag.add_node("B", lambda: None, None, 15, 0)
        dag.add_node("C", lambda: None, None, 15, 0)
        dag.add_node("D", lambda: None, ["A"], 20, 0)
        wave = self.sut.next_wave()
        self.assertEqual(wave, ["B", "C", "A"])

    def test_next_wave_empty_when_no_ready_nodes(self) -> None:
        """Verify next_wave returns empty list when no nodes are ready."""
        wave = self.sut.next_wave()
        self.assertEqual(wave, [])

    def test_mark_running_transitions_state_to_running(self) -> None:
        """Verify marking node running updates state to running."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.assertEqual(self.sut.get_state("A"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents_to_ready(self) -> None:
        """Verify marking node succeeded promotes unblocked dependents to ready."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.next_wave()
        self.assertEqual(self.sut.get_state("B"), NodeState.PENDING)
        self.sut.mark_running("A")
        self.sut.mark_succeeded("A")
        self.assertEqual(self.sut.get_state("A"), NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("B"), NodeState.READY)
        wave = self.sut.next_wave()
        self.assertEqual(wave, ["B"])

    def test_mark_succeeded_does_not_promote_dependent_with_pending_prerequisites(self) -> None:
        """Verify marking node succeeded does not promote dependent with unfinished dependencies."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, None, 0, 0)
        dag.add_node("C", lambda: None, ["A", "B"], 0, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.sut.mark_succeeded("A")
        self.assertEqual(self.sut.get_state("C"), NodeState.PENDING)
        self.sut.mark_running("B")
        self.sut.mark_succeeded("B")
        self.assertEqual(self.sut.get_state("C"), NodeState.READY)

    def test_mark_failed_fail_fast_cancels_remaining_pending_nodes(self) -> None:
        """Verify mark_failed with fail_fast cancels remaining pending nodes."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 10, 0)
        dag.add_node("B", lambda: None, None, 5, 0)
        dag.add_node("C", lambda: None, ["A"], 0, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.sut.mark_failed("A", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.sut.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("B"), NodeState.CANCELLED)
        self.assertEqual(self.sut.get_state("C"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """Verify mark_failed with skip_downstream marks transitive dependents as skipped."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 10, 0)
        dag.add_node("B", lambda: None, ["A"], 0, 0)
        dag.add_node("C", lambda: None, ["B"], 0, 0)
        dag.add_node("D", lambda: None, None, 5, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.sut.mark_failed("A", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("D"), NodeState.READY)

    def test_mark_failed_continue_on_error_leaves_independent_nodes_eligible(self) -> None:
        """Verify mark_failed with continue_on_error keeps independent nodes eligible."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 10, 0)
        dag.add_node("B", lambda: None, ["A"], 0, 0)
        dag.add_node("C", lambda: None, None, 5, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.sut.mark_failed("A", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sut.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("C"), NodeState.READY)

    def test_is_finished_empty_dag_returns_true(self) -> None:
        """Verify is_finished returns true for empty graph."""
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_all_terminal_returns_true(self) -> None:
        """Verify is_finished returns true when all nodes reach terminal states."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        self.assertFalse(self.sut.is_finished())
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_succeeded("A")
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_non_terminal_remaining_returns_false(self) -> None:
        """Verify is_finished returns false when non-terminal eligible nodes remain."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, None, 0, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.sut.mark_succeeded("A")
        self.assertFalse(self.sut.is_finished())

    def test_is_finished_blocked_by_failure_returns_true(self) -> None:
        """Verify is_finished returns true when unexecuted nodes are blocked by failed dependencies."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, ["A"], 0, 0)
        self.sut.next_wave()
        self.sut.mark_running("A")
        self.sut.mark_failed("A", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertTrue(self.sut.is_finished())

    def test_get_state_success(self) -> None:
        """Verify get_state returns current node lifecycle state."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.get_state("A"), NodeState.READY)

    def test_get_state_missing_node_raises_node_not_found_error(self) -> None:
        """Verify get_state raises NodeNotFoundError for unregistered node."""
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.get_state("missing")
        self.assertEqual(ctx.exception.node_id, "missing")

    def test_get_all_states_reflects_all_nodes(self) -> None:
        """Verify get_all_states returns execution state of all registered nodes."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, ["A"], 0, 0)
        states = self.sut.get_all_states()
        self.assertEqual(states["A"], NodeState.READY)
        self.assertEqual(states["B"], NodeState.PENDING)

    def test_remove_node_purges_node_from_scheduler(self) -> None:
        """Verify removing a node from the graph purges it from scheduler state."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, None, 0, 0)
        self.sut.next_wave()
        dag.remove_node("B")
        states = self.sut.get_all_states()
        self.assertIn("A", states)
        self.assertNotIn("B", states)
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_state("B")


class DAGRunnerTest(LifecycleTestCase):
    """Unit tests for the DAGRunner singleton implementation."""

    target = DAGRunner

    def test_run_validates_graph_and_raises_node_not_found_on_missing_dependency(self) -> None:
        """Verify run validates graph and raises NodeNotFoundError on missing dependency."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, ["B"], 0, 0)
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(ctx.exception.node_id, "B")

    def test_run_validates_graph_and_raises_cycle_error_on_cycle(self) -> None:
        """Verify run validates graph and raises CycleError on directed cycle."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: None, None, 0, 0)
        dag.add_node("B", lambda: None, None, 0, 0)
        dag.add_node("dead_end", lambda: None, ["A"], 0, 0)
        dag.add_edge("A", "B")
        dag.add_edge("B", "A")
        with self.assertRaises(CycleError) as ctx:
            self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_run_successful_dag_returns_consolidated_report(self) -> None:
        """Verify run executes complete graph successfully and returns consolidated report."""
        dag = self.get_singleton(DAG)
        order_log: List[str] = []

        def task_a() -> str:
            order_log.append("A")
            return "value_A"

        def task_b() -> str:
            order_log.append("B")
            return "value_B"

        dag.add_node("A", task_a, None, 10, 0)
        dag.add_node("B", task_b, ["A"], 5, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"A", "B"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(report.critical_path, ("A", "B"))
        self.assertEqual(order_log, ["A", "B"])

        res_a = report.results["A"]
        self.assertEqual(res_a.node_id, "A")
        self.assertEqual(res_a.state, NodeState.SUCCEEDED)
        self.assertEqual(res_a.value, "value_A")
        self.assertIsNone(res_a.error)
        self.assertEqual(res_a.retries_attempted, 0)

        res_b = report.results["B"]
        self.assertEqual(res_b.node_id, "B")
        self.assertEqual(res_b.state, NodeState.SUCCEEDED)
        self.assertEqual(res_b.value, "value_B")
        self.assertIsNone(res_b.error)
        self.assertEqual(res_b.retries_attempted, 0)

    def test_run_sequential_waves_and_records_action_values(self) -> None:
        """Verify run executes ready waves sequentially and records node return values."""
        dag = self.get_singleton(DAG)
        dag.add_node("A", lambda: 10, None, 5, 0)
        dag.add_node("B", lambda: 20, None, 15, 0)
        dag.add_node("C", lambda: 30, ["A", "B"], 0, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.results["A"].value, 10)
        self.assertEqual(report.results["B"].value, 20)
        self.assertEqual(report.results["C"].value, 30)

    def test_run_retry_action_success_after_failure(self) -> None:
        """Verify run retries failed node actions up to retry limit and succeeds on recovery."""
        dag = self.get_singleton(DAG)
        attempts: Dict[str, int] = {"count": 0}

        def flaky_action() -> str:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("temporary network blip")
            return "recovered"

        dag.add_node("flake", flaky_action, None, 0, 2)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertIn("flake", report.succeeded_nodes)
        res = report.results["flake"]
        self.assertEqual(res.state, NodeState.SUCCEEDED)
        self.assertEqual(res.value, "recovered")
        self.assertEqual(res.retries_attempted, 1)

    def test_run_retry_action_exhausted_records_failed_result(self) -> None:
        """Verify run records failed state when action exceeds retries."""
        dag = self.get_singleton(DAG)

        def failing_action() -> None:
            raise ValueError("unrecoverable failure")

        dag.add_node("faulty", failing_action, None, 0, 1)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertIn("faulty", report.failed_nodes)
        res = report.results["faulty"]
        self.assertEqual(res.state, NodeState.FAILED)
        self.assertIsInstance(res.error, ValueError)
        self.assertEqual(res.retries_attempted, 1)

    def test_run_failure_policy_fail_fast_halts_and_cancels_remaining(self) -> None:
        """Verify run with fail_fast halts wave loop and cancels remaining nodes."""
        dag = self.get_singleton(DAG)

        def failing_action() -> None:
            raise RuntimeError("stop everything")

        dag.add_node("A", failing_action, None, 10, 0)
        dag.add_node("B", lambda: "ok", None, 5, 0)
        dag.add_node("C", lambda: "ok", ["A"], 0, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertIn("A", report.failed_nodes)
        self.assertIn("B", report.cancelled_nodes)
        self.assertIn("C", report.cancelled_nodes)

    def test_run_failure_policy_skip_downstream_skips_dependents_and_runs_independent(self) -> None:
        """Verify run with skip_downstream skips dependents while running independent branches."""
        dag = self.get_singleton(DAG)

        def failing_action() -> None:
            raise RuntimeError("branch failed")

        dag.add_node("A", failing_action, None, 10, 0)
        dag.add_node("B", lambda: "blocked", ["A"], 0, 0)
        dag.add_node("C", lambda: "independent_c", None, 5, 0)
        dag.add_node("D", lambda: "independent_d", ["C"], 0, 0)

        report = self.sut.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIn("A", report.failed_nodes)
        self.assertIn("B", report.skipped_nodes)
        self.assertIn("C", report.succeeded_nodes)
        self.assertIn("D", report.succeeded_nodes)

    def test_run_failure_policy_continue_on_error_completes_independent_branches(self) -> None:
        """Verify run with continue_on_error runs all unblocked independent branches."""
        dag = self.get_singleton(DAG)

        def failing_action() -> None:
            raise RuntimeError("error in task")

        dag.add_node("A", failing_action, None, 10, 0)
        dag.add_node("B", lambda: "dep_b", ["A"], 0, 0)
        dag.add_node("C", lambda: "independent_c", None, 5, 0)

        report = self.sut.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIn("A", report.failed_nodes)
        self.assertIn("B", report.skipped_nodes)
        self.assertIn("C", report.succeeded_nodes)

    def test_run_empty_dag_returns_empty_report(self) -> None:
        """Verify run on empty graph returns empty execution report."""
        report = self.sut.run(FailurePolicy.FAIL_FAST)
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
# LAST_CLEANED: 2026-11-12T05:11:07Z
# LAST_CHANGED: 2026-11-12T05:05:16Z
# CHANGE: Cover cycle search path backtracking traversal in topological sort and graph validation when dead-end branches accompany directed cycles
# COVERAGE_AUDIT: 2026-11-12T05:11:07Z
# QA_AUDIT: 2026-11-12T05:10:44Z
# --- END AUTOFAB METADATA ---
