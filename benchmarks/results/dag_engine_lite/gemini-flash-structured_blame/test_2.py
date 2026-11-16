from __future__ import annotations

import unittest
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleTestCase, fake, system
from dag_engine_lite.lib import dag_engine_lite_impl
from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG as DAGProtocol,
    DAGError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler as WaveSchedulerProtocol,
)


class DataTypeTest(unittest.TestCase):
    """Unit tests for standalone domain data types and exceptions."""

    def test_node_state_values(self) -> None:
        """Verify NodeState enum members and wire values."""
        self.assertEqual(NodeState.PENDING.value, "pending")
        self.assertEqual(NodeState.READY.value, "ready")
        self.assertEqual(NodeState.RUNNING.value, "running")
        self.assertEqual(NodeState.SUCCEEDED.value, "succeeded")
        self.assertEqual(NodeState.FAILED.value, "failed")
        self.assertEqual(NodeState.CANCELLED.value, "cancelled")
        self.assertEqual(NodeState.SKIPPED.value, "skipped")

    def test_failure_policy_values(self) -> None:
        """Verify FailurePolicy enum members and wire values."""
        self.assertEqual(FailurePolicy.FAIL_FAST.value, "fail_fast")
        self.assertEqual(FailurePolicy.CONTINUE_ON_ERROR.value, "continue_on_error")
        self.assertEqual(FailurePolicy.SKIP_DOWNSTREAM.value, "skip_downstream")

    def test_node_definition_initialization(self) -> None:
        """Verify NodeDefinition fields, generic binding, and default arguments."""
        action_fn = lambda: 42
        node = NodeDefinition(
            node_id="task_1",
            action=action_fn,
            dependencies=frozenset(["upstream_a", "upstream_b"]),
            priority=5,
            retries=2,
        )
        self.assertEqual(node.node_id, "task_1")
        self.assertEqual(node.action(), 42)
        self.assertEqual(node.dependencies, frozenset(["upstream_a", "upstream_b"]))
        self.assertEqual(node.priority, 5)
        self.assertEqual(node.retries, 2)

        default_node = NodeDefinition(
            node_id="task_default",
            action=action_fn,
            dependencies=frozenset(),
        )
        self.assertEqual(default_node.priority, 0)
        self.assertEqual(default_node.retries, 0)

    def test_node_result_initialization(self) -> None:
        """Verify NodeResult fields and defaults."""
        cause = RuntimeError("failed task")
        res = NodeResult(
            node_id="node_x",
            state=NodeState.FAILED,
            value=None,
            error=cause,
            duration_seconds=0.15,
            retries_attempted=3,
        )
        self.assertEqual(res.node_id, "node_x")
        self.assertEqual(res.state, NodeState.FAILED)
        self.assertIsNone(res.value)
        self.assertIs(res.error, cause)
        self.assertEqual(res.duration_seconds, 0.15)
        self.assertEqual(res.retries_attempted, 3)

        success_res = NodeResult(
            node_id="node_y",
            state=NodeState.SUCCEEDED,
            value="success_val",
        )
        self.assertIsNone(success_res.error)
        self.assertEqual(success_res.duration_seconds, 0.0)
        self.assertEqual(success_res.retries_attempted, 0)
        self.assertEqual(success_res.value, "success_val")

    def test_dag_run_report_initialization(self) -> None:
        """Verify DAGRunReport fields and aggregation data structure."""
        outcome = NodeResult(node_id="n1", state=NodeState.SUCCEEDED, value=1)
        report = DAGRunReport(
            total_nodes=4,
            succeeded_nodes=("n1",),
            failed_nodes=("n2",),
            skipped_nodes=("n3",),
            cancelled_nodes=("n4",),
            wall_clock_seconds=0.45,
            critical_path=("n1", "n2"),
            results={"n1": outcome},
        )
        self.assertEqual(report.total_nodes, 4)
        self.assertEqual(report.succeeded_nodes, ("n1",))
        self.assertEqual(report.failed_nodes, ("n2",))
        self.assertEqual(report.skipped_nodes, ("n3",))
        self.assertEqual(report.cancelled_nodes, ("n4",))
        self.assertEqual(report.wall_clock_seconds, 0.45)
        self.assertEqual(report.critical_path, ("n1", "n2"))
        self.assertEqual(report.results["n1"], outcome)

    def test_exception_types_and_fields(self) -> None:
        """Verify DAG error hierarchies and diagnostic payload fields."""
        self.assertTrue(issubclass(CycleError, DAGError))
        self.assertTrue(issubclass(NodeNotFoundError, DAGError))
        self.assertTrue(issubclass(DuplicateNodeError, DAGError))
        self.assertTrue(issubclass(NodeExecutionError, DAGError))

        cycle_err = CycleError(message="Cycle found", cycle=("a", "b", "a"))
        self.assertEqual(cycle_err.message, "Cycle found")
        self.assertEqual(cycle_err.cycle, ("a", "b", "a"))

        not_found_err = NodeNotFoundError(message="Node missing", node_id="missing_node")
        self.assertEqual(not_found_err.message, "Node missing")
        self.assertEqual(not_found_err.node_id, "missing_node")

        dup_err = DuplicateNodeError(message="Duplicate node", node_id="dup_node")
        self.assertEqual(dup_err.message, "Duplicate node")
        self.assertEqual(dup_err.node_id, "dup_node")

        underlying = ValueError("bad action")
        exec_err = NodeExecutionError(message="Execution failed", node_id="exec_node", cause=underlying)
        self.assertEqual(exec_err.message, "Execution failed")
        self.assertEqual(exec_err.node_id, "exec_node")
        self.assertIs(exec_err.cause, underlying)


class DAGTest(LifecycleTestCase):
    """Unit tests for DAG singleton implementation."""

    target = dag_engine_lite_impl.DAG

    def test_add_node_registers_definition(self) -> None:
        """Verify adding a node registers its definition and updates membership."""
        action = lambda: "output_a"
        self.sut.add_node("node_a", action, None, 10, 1)

        self.assertTrue(self.sut.has_node("node_a"))
        self.assertEqual(self.sut.all_nodes(), {"node_a"})

        node_def = self.sut.get_node("node_a")
        self.assertEqual(node_def.node_id, "node_a")
        self.assertEqual(node_def.priority, 10)
        self.assertEqual(node_def.retries, 1)
        self.assertEqual(node_def.dependencies, frozenset())
        self.assertEqual(node_def.action(), "output_a")

    def test_add_node_with_dependencies(self) -> None:
        """Verify adding a node with dependencies establishes direct upstream connections."""
        self.sut.add_node("dep_1", lambda: None, None, 0, 0)
        self.sut.add_node("dep_2", lambda: None, None, 0, 0)
        self.sut.add_node("target_node", lambda: None, ["dep_1", "dep_2"], 0, 0)

        self.assertEqual(self.sut.get_dependencies("target_node"), {"dep_1", "dep_2"})
        self.assertIn("target_node", self.sut.get_dependents("dep_1"))
        self.assertIn("target_node", self.sut.get_dependents("dep_2"))

    def test_add_node_defers_missing_dependency_checks(self) -> None:
        """Verify adding a node referencing unregistered dependencies does not eagerly raise NodeNotFoundError."""
        self.sut.add_node("node_forward", lambda: None, ["unregistered_dep_1", "unregistered_dep_2"], 0, 0)
        self.assertTrue(self.sut.has_node("node_forward"))
        self.assertEqual(self.sut.get_dependencies("node_forward"), {"unregistered_dep_1", "unregistered_dep_2"})

    def test_add_node_duplicate_raises_duplicate_node_error(self) -> None:
        """Verify adding a node with an already registered identifier raises DuplicateNodeError."""
        self.sut.add_node("node_unique", lambda: None, None, 0, 0)
        with self.assertRaises(DuplicateNodeError):
            self.sut.add_node("node_unique", lambda: None, None, 5, 1)

    def test_add_edge_connects_nodes(self) -> None:
        """Verify add_edge establishes a directed dependency between existing nodes."""
        self.sut.add_node("upstream", lambda: None, None, 0, 0)
        self.sut.add_node("downstream", lambda: None, None, 0, 0)
        self.sut.add_edge("upstream", "downstream")

        self.assertIn("upstream", self.sut.get_dependencies("downstream"))
        self.assertIn("downstream", self.sut.get_dependents("upstream"))

    def test_add_edge_missing_upstream_raises_node_not_found_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError when upstream identifier does not exist."""
        self.sut.add_node("downstream", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.add_edge("missing_upstream", "downstream")

    def test_add_edge_missing_downstream_raises_node_not_found_error(self) -> None:
        """Verify add_edge raises NodeNotFoundError when downstream identifier does not exist."""
        self.sut.add_node("upstream", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.add_edge("upstream", "missing_downstream")

    def test_remove_node_purges_node_and_incident_edges(self) -> None:
        """Verify removing a node purges definition and all incident dependency edges."""
        self.sut.add_node("node_a", lambda: None, None, 0, 0)
        self.sut.add_node("node_b", lambda: None, ["node_a"], 0, 0)
        self.sut.add_node("node_c", lambda: None, ["node_b"], 0, 0)

        self.sut.remove_node("node_b")

        self.assertFalse(self.sut.has_node("node_b"))
        self.assertNotIn("node_b", self.sut.all_nodes())
        self.assertEqual(self.sut.get_dependents("node_a"), set())
        self.assertEqual(self.sut.get_dependencies("node_c"), set())

    def test_remove_node_missing_raises_node_not_found_error(self) -> None:
        """Verify remove_node raises NodeNotFoundError when node identifier does not exist."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.remove_node("nonexistent_node")

    def test_has_node_reports_existence(self) -> None:
        """Verify has_node accurately reports registration status."""
        self.assertFalse(self.sut.has_node("node_alpha"))
        self.sut.add_node("node_alpha", lambda: None, None, 0, 0)
        self.assertTrue(self.sut.has_node("node_alpha"))

    def test_get_node_missing_raises_node_not_found_error(self) -> None:
        """Verify get_node raises NodeNotFoundError for an unregistered node identifier."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_node("unregistered_node")

    def test_get_dependencies_missing_raises_node_not_found_error(self) -> None:
        """Verify get_dependencies raises NodeNotFoundError for an unregistered node identifier."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_dependencies("unregistered_node")

    def test_get_dependents_missing_raises_node_not_found_error(self) -> None:
        """Verify get_dependents raises NodeNotFoundError for an unregistered node identifier."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_dependents("unregistered_node")

    def test_all_nodes_returns_all_registered_identifiers(self) -> None:
        """Verify all_nodes returns a complete set of registered node identifiers."""
        self.assertEqual(self.sut.all_nodes(), set())
        self.sut.add_node("n1", lambda: None, None, 0, 0)
        self.sut.add_node("n2", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.all_nodes(), {"n1", "n2"})

    def test_all_dependencies_exist_observability(self) -> None:
        """Verify all_dependencies_exist returns True when dependencies are satisfied and False otherwise."""
        self.assertTrue(self.sut.all_dependencies_exist())
        self.sut.add_node("child", lambda: None, ["parent"], 0, 0)
        self.assertFalse(self.sut.all_dependencies_exist())
        self.sut.add_node("parent", lambda: None, None, 0, 0)
        self.assertTrue(self.sut.all_dependencies_exist())

    def test_is_acyclic_observability(self) -> None:
        """Verify is_acyclic correctly distinguishes acyclic graphs from cycles."""
        self.assertTrue(self.sut.is_acyclic())
        self.sut.add_node("step_1", lambda: None, None, 0, 0)
        self.sut.add_node("step_2", lambda: None, ["step_1"], 0, 0)
        self.sut.add_node("step_3", lambda: None, ["step_2"], 0, 0)
        self.assertTrue(self.sut.is_acyclic())

        self.sut.add_edge("step_3", "step_1")
        self.assertFalse(self.sut.is_acyclic())

    def test_validate_succeeds_on_valid_dag(self) -> None:
        """Verify validate completes without error on a complete acyclic DAG."""
        self.sut.add_node("v1", lambda: None, None, 0, 0)
        self.sut.add_node("v2", lambda: None, ["v1"], 0, 0)
        self.sut.validate()

    def test_validate_missing_dependency_raises_node_not_found_error(self) -> None:
        """Verify validate raises NodeNotFoundError when a referenced dependency is missing."""
        self.sut.add_node("dangling_child", lambda: None, ["missing_parent"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.validate()

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """Verify validate raises CycleError when a directed cycle is present."""
        self.sut.add_node("c1", lambda: None, None, 0, 0)
        self.sut.add_node("c2", lambda: None, ["c1"], 0, 0)
        self.sut.add_edge("c2", "c1")
        with self.assertRaises(CycleError):
            self.sut.validate()

    def test_validate_cycle_with_dead_end_branch_backtracking(self) -> None:
        """Verify validate detects cycles in graphs with dead-end sink branches requiring DFS backtracking."""
        self.sut.add_node("m_cycle_head", lambda: None, None, 0, 0)
        self.sut.add_node("a_prior_sink", lambda: None, ["m_cycle_head"], 0, 0)
        self.sut.add_node("a_sub_sink", lambda: None, ["a_prior_sink"], 0, 0)
        self.sut.add_node("n_dead_end_sink", lambda: None, ["m_cycle_head"], 0, 0)
        self.sut.add_node("n_sub_sink", lambda: None, ["n_dead_end_sink"], 0, 0)
        self.sut.add_node("z_cycle_partner", lambda: None, ["m_cycle_head"], 0, 0)
        self.sut.add_edge("z_cycle_partner", "m_cycle_head")
        with self.assertRaises(CycleError):
            self.sut.validate()

    def test_topological_sort_returns_valid_order(self) -> None:
        """Verify topological_sort produces an ordering where prerequisites precede dependents."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["a"], 0, 0)
        self.sut.add_node("d", lambda: None, ["b", "c"], 0, 0)

        order = self.sut.topological_sort()
        self.assertEqual(len(order), 4)
        self.assertEqual(order[0], "a")
        self.assertEqual(order[3], "d")
        self.assertIn("b", order[1:3])
        self.assertIn("c", order[1:3])

    def test_topological_sort_resolves_ties_by_priority_and_id(self) -> None:
        """Verify topological_sort resolves concurrent ties by priority descending then node_id ascending."""
        self.sut.add_node("task_low", lambda: None, None, priority=1, retries=0)
        self.sut.add_node("task_high", lambda: None, None, priority=10, retries=0)
        self.sut.add_node("task_mid_b", lambda: None, None, priority=5, retries=0)
        self.sut.add_node("task_mid_a", lambda: None, None, priority=5, retries=0)

        order = self.sut.topological_sort()
        self.assertEqual(order, ["task_high", "task_mid_a", "task_mid_b", "task_low"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """Verify topological_sort raises CycleError when graph contains a dependency cycle."""
        self.sut.add_node("cycle_1", lambda: None, None, 0, 0)
        self.sut.add_node("cycle_2", lambda: None, ["cycle_1"], 0, 0)
        self.sut.add_edge("cycle_2", "cycle_1")
        with self.assertRaises(CycleError):
            self.sut.topological_sort()

    def test_topological_sort_cycle_with_dead_end_branch_backtracking(self) -> None:
        """Verify topological_sort detects cycles and backtracks over dead-end branches during cycle reconstruction."""
        self.sut.add_node("m_cycle_head", lambda: None, None, 0, 0)
        self.sut.add_node("a_prior_sink", lambda: None, ["m_cycle_head"], 0, 0)
        self.sut.add_node("a_sub_sink", lambda: None, ["a_prior_sink"], 0, 0)
        self.sut.add_node("n_dead_end_sink", lambda: None, ["m_cycle_head"], 0, 0)
        self.sut.add_node("n_sub_sink", lambda: None, ["n_dead_end_sink"], 0, 0)
        self.sut.add_node("z_cycle_partner", lambda: None, ["m_cycle_head"], 0, 0)
        self.sut.add_edge("z_cycle_partner", "m_cycle_head")
        with self.assertRaises(CycleError):
            self.sut.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """Verify find_roots returns nodes without dependencies and find_leaves returns nodes without dependents."""
        self.assertEqual(self.sut.find_roots(), set())
        self.assertEqual(self.sut.find_leaves(), set())

        self.sut.add_node("root_1", lambda: None, None, 0, 0)
        self.sut.add_node("root_2", lambda: None, None, 0, 0)
        self.sut.add_node("middle", lambda: None, ["root_1", "root_2"], 0, 0)
        self.sut.add_node("leaf_1", lambda: None, ["middle"], 0, 0)
        self.sut.add_node("leaf_2", lambda: None, ["middle"], 0, 0)

        self.assertEqual(self.sut.find_roots(), {"root_1", "root_2"})
        self.assertEqual(self.sut.find_leaves(), {"leaf_1", "leaf_2"})

    def test_topological_sort_empty_graph(self) -> None:
        """Verify topological_sort on an empty graph returns an empty list."""
        self.assertEqual(self.sut.topological_sort(), [])

    def test_compute_critical_path_with_default_durations(self) -> None:
        """Verify compute_critical_path calculates longest path and cumulative weight with default 1.0 weights."""
        self.sut.add_node("start", lambda: None, None, 0, 0)
        self.sut.add_node("mid_long_1", lambda: None, ["start"], 0, 0)
        self.sut.add_node("mid_long_2", lambda: None, ["mid_long_1"], 0, 0)
        self.sut.add_node("end", lambda: None, ["mid_long_2"], 0, 0)
        self.sut.add_node("mid_short", lambda: None, ["start"], 0, 0)
        self.sut.add_edge("mid_short", "end")

        path, duration = self.sut.compute_critical_path(None)
        self.assertEqual(path, ["start", "mid_long_1", "mid_long_2", "end"])
        self.assertEqual(duration, 4.0)

    def test_compute_critical_path_with_custom_durations(self) -> None:
        """Verify compute_critical_path calculates longest path using custom duration weights."""
        self.sut.add_node("n_a", lambda: None, None, 0, 0)
        self.sut.add_node("n_b", lambda: None, ["n_a"], 0, 0)
        self.sut.add_node("n_c", lambda: None, ["n_a"], 0, 0)
        self.sut.add_node("n_d", lambda: None, ["n_c"], 0, 0)

        durations: Dict[str, float] = {
            "n_a": 1.0,
            "n_b": 10.0,
            "n_c": 2.0,
            "n_d": 3.0,
        }
        path, duration = self.sut.compute_critical_path(durations)
        self.assertEqual(path, ["n_a", "n_b"])
        self.assertEqual(duration, 11.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """Verify compute_critical_path on an empty graph returns an empty path and zero duration."""
        path, duration = self.sut.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(duration, 0.0)


class WaveSchedulerTest(LifecycleTestCase):
    """Unit tests for WaveScheduler singleton implementation."""

    target = dag_engine_lite_impl.WaveScheduler

    def test_empty_dag_is_finished_and_next_wave_empty(self) -> None:
        """Verify empty graph scheduler is immediately finished and yields an empty wave."""
        self.assertTrue(self.sut.is_finished())
        self.assertEqual(self.sut.next_wave(), [])
        self.assertEqual(self.sut.get_all_states(), {})

    def test_initial_wave_yields_roots(self) -> None:
        """Verify next_wave initially yields root nodes in READY state and non-roots in PENDING."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("root_a", lambda: None, None, 0, 0)
        dag.add_node("child_b", lambda: None, ["root_a"], 0, 0)

        self.assertFalse(self.sut.is_finished())
        self.assertEqual(self.sut.get_state("root_a"), NodeState.READY)
        self.assertEqual(self.sut.get_state("child_b"), NodeState.PENDING)

        wave = self.sut.next_wave()
        self.assertEqual(wave, ["root_a"])

    def test_next_wave_orders_by_priority_descending(self) -> None:
        """Verify next_wave orders ready nodes by priority descending then node_id ascending."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("alpha", lambda: None, None, priority=5, retries=0)
        dag.add_node("beta", lambda: None, None, priority=20, retries=0)
        dag.add_node("gamma", lambda: None, None, priority=5, retries=0)

        wave = self.sut.next_wave()
        self.assertEqual(wave, ["beta", "alpha", "gamma"])

    def test_mark_running_transitions_state(self) -> None:
        """Verify mark_running transitions node state to RUNNING."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("task_run", lambda: None, None, 0, 0)

        self.sut.mark_running("task_run")
        self.assertEqual(self.sut.get_state("task_run"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents_to_ready(self) -> None:
        """Verify mark_succeeded transitions node to SUCCEEDED and promotes dependents to READY."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("step_a", lambda: None, None, 0, 0)
        dag.add_node("step_b", lambda: None, ["step_a"], 0, 0)

        self.assertEqual(self.sut.get_state("step_b"), NodeState.PENDING)

        self.sut.mark_succeeded("step_a")
        self.assertEqual(self.sut.get_state("step_a"), NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("step_b"), NodeState.READY)

        wave = self.sut.next_wave()
        self.assertEqual(wave, ["step_b"])

        self.sut.mark_succeeded("step_b")
        self.assertTrue(self.sut.is_finished())

    def test_mark_succeeded_unblocks_only_when_all_dependencies_succeed(self) -> None:
        """Verify multi-dependency nodes only become READY when all prerequisites succeed."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("parent_1", lambda: None, None, 0, 0)
        dag.add_node("parent_2", lambda: None, None, 0, 0)
        dag.add_node("joined_child", lambda: None, ["parent_1", "parent_2"], 0, 0)

        self.sut.mark_succeeded("parent_1")
        self.assertEqual(self.sut.get_state("joined_child"), NodeState.PENDING)

        self.sut.mark_succeeded("parent_2")
        self.assertEqual(self.sut.get_state("joined_child"), NodeState.READY)

    def test_mark_failed_skip_downstream_policy(self) -> None:
        """Verify SKIP_DOWNSTREAM marks node FAILED and transitive dependents SKIPPED while independent nodes remain."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("root_fail", lambda: None, None, 0, 0)
        dag.add_node("child_trans_1", lambda: None, ["root_fail"], 0, 0)
        dag.add_node("child_trans_2", lambda: None, ["child_trans_1"], 0, 0)
        dag.add_node("independent_node", lambda: None, None, 0, 0)

        self.sut.mark_failed("root_fail", FailurePolicy.SKIP_DOWNSTREAM)

        self.assertEqual(self.sut.get_state("root_fail"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("child_trans_1"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("child_trans_2"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("independent_node"), NodeState.READY)
        self.assertFalse(self.sut.is_finished())

    def test_mark_failed_fail_fast_policy(self) -> None:
        """Verify FAIL_FAST marks node FAILED and cancels all remaining non-terminal nodes."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("fast_fail_node", lambda: None, None, 0, 0)
        dag.add_node("pending_dep", lambda: None, ["fast_fail_node"], 0, 0)
        dag.add_node("independent_pending", lambda: None, None, 0, 0)

        self.sut.mark_failed("fast_fail_node", FailurePolicy.FAIL_FAST)

        self.assertEqual(self.sut.get_state("fast_fail_node"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("pending_dep"), NodeState.CANCELLED)
        self.assertEqual(self.sut.get_state("independent_pending"), NodeState.CANCELLED)
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_continue_on_error_policy(self) -> None:
        """Verify CONTINUE_ON_ERROR marks node FAILED and blocked dependents SKIPPED while independent nodes execute."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("fail_branch", lambda: None, None, 0, 0)
        dag.add_node("blocked_child", lambda: None, ["fail_branch"], 0, 0)
        dag.add_node("good_branch", lambda: None, None, 0, 0)
        dag.add_node("good_child", lambda: None, ["good_branch"], 0, 0)

        self.sut.mark_failed("fail_branch", FailurePolicy.CONTINUE_ON_ERROR)

        self.assertEqual(self.sut.get_state("fail_branch"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("blocked_child"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("good_branch"), NodeState.READY)
        self.assertFalse(self.sut.is_finished())

    def test_is_finished_when_blocked_by_failure(self) -> None:
        """Verify is_finished returns True when no ready nodes remain and unexecuted nodes are blocked by failed dependencies."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("root_only", lambda: None, None, 0, 0)
        dag.add_node("blocked_leaf", lambda: None, ["root_only"], 0, 0)

        self.sut.mark_failed("root_only", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_returns_false_when_executing_node_is_running(self) -> None:
        """Verify is_finished returns False when an executing node remains non-terminal in the RUNNING state."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("active_job", lambda: None, None, 0, 0)
        self.sut.mark_running("active_job")
        self.assertEqual(self.sut.get_state("active_job"), NodeState.RUNNING)
        self.assertFalse(self.sut.is_finished())

    def test_is_finished_returns_true_when_unschedulable_circular_dependencies_block_nodes(self) -> None:
        """Verify is_finished returns True when unexecuted nodes remain non-terminal but no ready nodes can be scheduled due to unschedulable circular dependencies."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("blocked_cycle_a", lambda: None, ["blocked_cycle_b"], 0, 0)
        dag.add_node("blocked_cycle_b", lambda: None, ["blocked_cycle_a"], 0, 0)

        self.assertEqual(self.sut.get_state("blocked_cycle_a"), NodeState.PENDING)
        self.assertEqual(self.sut.get_state("blocked_cycle_b"), NodeState.PENDING)
        self.assertEqual(self.sut.next_wave(), [])
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_returns_true_when_partial_graph_blocked_by_circular_dependency(self) -> None:
        """Verify is_finished returns True when some nodes succeed but remaining unexecuted nodes are blocked by circular dependencies."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("root_step", lambda: None, None, 0, 0)
        dag.add_node("loop_1", lambda: None, ["root_step", "loop_2"], 0, 0)
        dag.add_node("loop_2", lambda: None, ["loop_1"], 0, 0)

        self.assertEqual(self.sut.next_wave(), ["root_step"])
        self.sut.mark_succeeded("root_step")

        self.assertEqual(self.sut.get_state("loop_1"), NodeState.PENDING)
        self.assertEqual(self.sut.get_state("loop_2"), NodeState.PENDING)
        self.assertEqual(self.sut.next_wave(), [])
        self.assertTrue(self.sut.is_finished())

    def test_get_state_missing_node_raises_node_not_found_error(self) -> None:
        """Verify get_state raises NodeNotFoundError when node identifier does not exist in graph."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_state("unregistered_task")

    def test_get_all_states_filters_to_registered_nodes(self) -> None:
        """Verify get_all_states returns a snapshot mapping of all registered node states."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("node_one", lambda: None, None, 0, 0)
        dag.add_node("node_two", lambda: None, ["node_one"], 0, 0)

        states = self.sut.get_all_states()
        self.assertEqual(set(states.keys()), {"node_one", "node_two"})
        self.assertEqual(states["node_one"], NodeState.READY)
        self.assertEqual(states["node_two"], NodeState.PENDING)

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Verify removing a node from the DAG purges it from scheduler state tracking."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("temporary_node", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.get_state("temporary_node"), NodeState.READY)

        dag.remove_node("temporary_node")
        self.assertNotIn("temporary_node", self.sut.get_all_states())
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_state("temporary_node")


class DAGRunnerTest(LifecycleTestCase):
    """Unit tests for DAGRunner singleton implementation."""

    target = dag_engine_lite_impl.DAGRunner

    def test_run_single_node_success(self) -> None:
        """Verify runner executes a single-node DAG and produces a successful run report."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("single_task", lambda: 100, None, 0, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("single_task",))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(report.critical_path, ("single_task",))

        res = report.results["single_task"]
        self.assertEqual(res.node_id, "single_task")
        self.assertEqual(res.state, NodeState.SUCCEEDED)
        self.assertEqual(res.value, 100)
        self.assertIsNone(res.error)
        self.assertEqual(res.retries_attempted, 0)

    def test_run_linear_pipeline_success(self) -> None:
        """Verify runner executes a multi-stage sequential pipeline in dependency order."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        execution_order: List[str] = []

        def make_action(name: str, val: int) -> Callable[[], int]:
            def action() -> int:
                execution_order.append(name)
                return val
            return action

        dag.add_node("stage_1", make_action("stage_1", 10), None, 0, 0)
        dag.add_node("stage_2", make_action("stage_2", 20), ["stage_1"], 0, 0)
        dag.add_node("stage_3", make_action("stage_3", 30), ["stage_2"], 0, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(execution_order, ["stage_1", "stage_2", "stage_3"])
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.succeeded_nodes, ("stage_1", "stage_2", "stage_3"))
        self.assertEqual(report.results["stage_1"].value, 10)
        self.assertEqual(report.results["stage_2"].value, 20)
        self.assertEqual(report.results["stage_3"].value, 30)
        self.assertEqual(report.critical_path, ("stage_1", "stage_2", "stage_3"))

    def test_run_retries_failing_action_until_success(self) -> None:
        """Verify runner retries an action up to configured retries when initial attempts fail."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        attempts = 0

        def flaky_action() -> str:
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise ValueError("temporary error")
            return "recovered"

        dag.add_node("flaky_node", flaky_action, None, priority=0, retries=3)

        report = self.sut.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(report.succeeded_nodes, ("flaky_node",))
        self.assertEqual(report.failed_nodes, ())
        res = report.results["flaky_node"]
        self.assertEqual(res.state, NodeState.SUCCEEDED)
        self.assertEqual(res.value, "recovered")
        self.assertEqual(res.retries_attempted, 2)

    def test_run_action_exhausts_retries_and_fails(self) -> None:
        """Verify runner records failure after all configured retry attempts are exhausted."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        attempts = 0

        def always_failing_action() -> None:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("persistent failure")

        dag.add_node("doomed_node", always_failing_action, None, priority=0, retries=2)

        report = self.sut.run(FailurePolicy.FAIL_FAST)

        self.assertIn("doomed_node", report.failed_nodes)
        self.assertEqual(attempts, 3)
        res = report.results["doomed_node"]
        self.assertEqual(res.state, NodeState.FAILED)
        self.assertEqual(res.retries_attempted, 2)
        self.assertIsInstance(res.error, RuntimeError)

    def test_run_failure_policy_fail_fast(self) -> None:
        """Verify runner halts execution and reports cancelled nodes under FAIL_FAST policy."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)

        def failing_action() -> None:
            raise RuntimeError("hard failure")

        dag.add_node("bad_node", failing_action, None, 0, 0)
        dag.add_node("child_node", lambda: None, ["bad_node"], 0, 0)
        dag.add_node("independent_node", lambda: None, None, 0, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)

        self.assertIn("bad_node", report.failed_nodes)
        self.assertIn("child_node", report.cancelled_nodes)
        self.assertEqual(report.results["bad_node"].state, NodeState.FAILED)
        self.assertIsNotNone(report.results["bad_node"].error)

    def test_run_failure_policy_skip_downstream(self) -> None:
        """Verify runner skips dependent nodes and continues independent branches under SKIP_DOWNSTREAM policy."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)

        def failing_action() -> None:
            raise RuntimeError("branch failure")

        dag.add_node("fail_root", failing_action, None, priority=10, retries=0)
        dag.add_node("dependent_child", lambda: None, ["fail_root"], priority=0, retries=0)
        dag.add_node("parallel_root", lambda: "parallel_ok", None, priority=5, retries=0)

        report = self.sut.run(FailurePolicy.SKIP_DOWNSTREAM)

        self.assertIn("fail_root", report.failed_nodes)
        self.assertIn("dependent_child", report.skipped_nodes)
        self.assertIn("parallel_root", report.succeeded_nodes)
        self.assertEqual(report.results["parallel_root"].value, "parallel_ok")
        self.assertEqual(report.results["dependent_child"].state, NodeState.SKIPPED)

    def test_run_failure_policy_continue_on_error(self) -> None:
        """Verify runner executes all possible unblocked nodes under CONTINUE_ON_ERROR policy."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)

        def failing_action() -> None:
            raise RuntimeError("node error")

        dag.add_node("faulty", failing_action, None, 0, 0)
        dag.add_node("blocked", lambda: None, ["faulty"], 0, 0)
        dag.add_node("healthy_1", lambda: "h1", None, 0, 0)
        dag.add_node("healthy_2", lambda: "h2", ["healthy_1"], 0, 0)

        report = self.sut.run(FailurePolicy.CONTINUE_ON_ERROR)

        self.assertIn("faulty", report.failed_nodes)
        self.assertIn("blocked", report.skipped_nodes)
        self.assertIn("healthy_1", report.succeeded_nodes)
        self.assertIn("healthy_2", report.succeeded_nodes)

    def test_run_missing_dependency_raises_node_not_found_error(self) -> None:
        """Verify runner validates graph and raises NodeNotFoundError when dependencies are missing."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("broken_node", lambda: None, ["absent_dep"], 0, 0)

        with self.assertRaises(NodeNotFoundError):
            self.sut.run(FailurePolicy.FAIL_FAST)

    def test_run_cycle_raises_cycle_error(self) -> None:
        """Verify runner validates graph and raises CycleError when a cycle is present."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("c_node_1", lambda: None, None, 0, 0)
        dag.add_node("c_node_2", lambda: None, ["c_node_1"], 0, 0)
        dag.add_edge("c_node_2", "c_node_1")

        with self.assertRaises(CycleError):
            self.sut.run(FailurePolicy.FAIL_FAST)


class DAGRunnerCollaboratorTest(LifecycleTestCase):
    """Unit tests for DAGRunner verifying collaborator interaction sequencing with @fake WaveScheduler."""

    target = dag_engine_lite_impl.DAGRunner

    @fake(WaveSchedulerProtocol)
    class FakeWaveScheduler:
        tier = system

        def __init__(self) -> None:
            self.wave_calls: int = 0
            self.running_nodes: List[str] = []
            self.succeeded_nodes: List[str] = []
            self.failed_nodes: List[Tuple[str, FailurePolicy]] = []
            self._finished: bool = False

        def next_wave(self) -> List[str]:
            self.wave_calls += 1
            if self.wave_calls == 1:
                return ["mocked_node"]
            return []

        def mark_running(self, node_id: str) -> None:
            self.running_nodes.append(node_id)

        def mark_succeeded(self, node_id: str) -> None:
            self.succeeded_nodes.append(node_id)
            self._finished = True

        def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
            self.failed_nodes.append((node_id, failure_policy))
            self._finished = True

        def is_finished(self) -> bool:
            return self._finished

        def get_state(self, node_id: str) -> NodeState:
            if node_id in self.succeeded_nodes:
                return NodeState.SUCCEEDED
            if any(n == node_id for n, _ in self.failed_nodes):
                return NodeState.FAILED
            return NodeState.READY

        def get_all_states(self) -> Dict[str, NodeState]:
            states: Dict[str, NodeState] = {}
            for n in self.succeeded_nodes:
                states[n] = NodeState.SUCCEEDED
            return states

    fake_wave_scheduler: FakeWaveScheduler

    def test_runner_collaborator_interaction(self) -> None:
        """Verify runner invokes WaveScheduler protocol operations during wave scheduling."""
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        dag.add_node("mocked_node", lambda: "mock_output", None, 0, 0)

        report = self.sut.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(self.fake_wave_scheduler.running_nodes, ["mocked_node"])
        self.assertEqual(self.fake_wave_scheduler.succeeded_nodes, ["mocked_node"])
        self.assertEqual(report.succeeded_nodes, ("mocked_node",))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T02:09:04Z
# LAST_CHANGED: 2026-11-16T02:08:20Z
# CHANGES:
# - [2026-11-16T01:54:42Z] [kind:new] [Lines: 4-289, 302-330, 343-527, 562-822] [Scope: DAG,WaveScheduler,DAGRunner,NodeDefinition,NodeResult,DAGRunReport] Delta: Author comprehensive unit tests verifying DAG, WaveScheduler, and DAGRunner behavioral contracts, invariants, and failure policies | Why: Satisfy low-level specification requirements across DAG execution engine singletons and data types
# - [2026-11-16T02:04:05Z] [kind:fix] [Lines: 290-291, 299-301, 331-335, 528-561] [Scope: DAG,WaveScheduler] Delta: Add cycle backtracking tests with dead-end sinks in validate and topological_sort, and WaveScheduler.is_finished tests for RUNNING state and circular blocked dependencies | Why: Address coverage feedback for cycle backtracking and WaveScheduler is_finished branch conditions
# - [2026-11-16T02:08:20Z] [kind:fix] [Lines: 292-298, 336-342] [Scope: DAG] Delta: Update cycle backtracking tests so dead-end sink branch identifiers sort lexicographically before cyclic dependent identifiers in validate and topological_sort | Why: Ensure DFS traversal exhausts dead-end paths and exercises search backtracking before detecting cycle
# COVERAGE_AUDIT: 2026-11-16T02:09:04Z
# QA_AUDIT: 2026-11-16T02:08:41Z
# --- END AUTOFAB METADATA ---
