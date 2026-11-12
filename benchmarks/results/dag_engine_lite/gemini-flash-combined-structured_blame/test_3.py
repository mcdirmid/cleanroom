from __future__ import annotations

from typing import Any, List, Set, Tuple
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


class DataTypesTest(unittest.TestCase):
    """Verifies instantiation and attribute integrity of domain data types and exceptions."""

    def test_dag_error_hierarchy(self) -> None:
        """Verifies base and derived DAG exception contracts."""
        base_err = DAGError("base error")
        self.assertEqual(base_err.message, "base error")
        self.assertIsInstance(base_err, Exception)

        cycle_err = CycleError("cycle detected", ("a", "b", "a"))
        self.assertEqual(cycle_err.message, "cycle detected")
        self.assertEqual(cycle_err.cycle, ("a", "b", "a"))
        self.assertIsInstance(cycle_err, DAGError)

        not_found_err = NodeNotFoundError("node missing", "node_x")
        self.assertEqual(not_found_err.message, "node missing")
        self.assertEqual(not_found_err.node_id, "node_x")
        self.assertIsInstance(not_found_err, DAGError)

        dup_err = DuplicateNodeError("duplicate node", "node_y")
        self.assertEqual(dup_err.message, "duplicate node")
        self.assertEqual(dup_err.node_id, "node_y")
        self.assertIsInstance(dup_err, DAGError)

        cause_ex = RuntimeError("underlying failure")
        exec_err = NodeExecutionError("execution failed", "node_z", cause_ex)
        self.assertEqual(exec_err.message, "execution failed")
        self.assertEqual(exec_err.node_id, "node_z")
        self.assertEqual(exec_err.cause, cause_ex)
        self.assertIsInstance(exec_err, DAGError)

    def test_enums_and_data_classes(self) -> None:
        """Verifies enum members and immutable record data classes."""
        self.assertEqual(NodeState.PENDING.value, "pending")
        self.assertEqual(NodeState.READY.value, "ready")
        self.assertEqual(NodeState.RUNNING.value, "running")
        self.assertEqual(NodeState.SUCCEEDED.value, "succeeded")
        self.assertEqual(NodeState.FAILED.value, "failed")
        self.assertEqual(NodeState.CANCELLED.value, "cancelled")
        self.assertEqual(NodeState.SKIPPED.value, "skipped")

        self.assertEqual(FailurePolicy.FAIL_FAST.value, "fail_fast")
        self.assertEqual(FailurePolicy.CONTINUE_ON_ERROR.value, "continue_on_error")
        self.assertEqual(FailurePolicy.SKIP_DOWNSTREAM.value, "skip_downstream")

        action_fn = lambda: 42
        node_def: NodeDefinition[int] = NodeDefinition(
            node_id="task_1",
            action=action_fn,
            dependencies=frozenset({"dep_1"}),
            priority=5,
            retries=2,
        )
        self.assertEqual(node_def.node_id, "task_1")
        self.assertEqual(node_def.action(), 42)
        self.assertEqual(node_def.dependencies, frozenset({"dep_1"}))
        self.assertEqual(node_def.priority, 5)
        self.assertEqual(node_def.retries, 2)

        result: NodeResult[int] = NodeResult(
            node_id="task_1",
            state=NodeState.SUCCEEDED,
            value=42,
            error=None,
            duration_seconds=0.15,
            retries_attempted=1,
        )
        self.assertEqual(result.node_id, "task_1")
        self.assertEqual(result.state, NodeState.SUCCEEDED)
        self.assertEqual(result.value, 42)
        self.assertIsNone(result.error)
        self.assertEqual(result.duration_seconds, 0.15)
        self.assertEqual(result.retries_attempted, 1)

        report = DAGRunReport(
            total_nodes=1,
            succeeded_nodes=("task_1",),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.2,
            critical_path=("task_1",),
            results={"task_1": result},
        )
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("task_1",))
        self.assertEqual(report.critical_path, ("task_1",))


class DAGTest(unittest.TestCase):
    """Unit tests for the DAG singleton service."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_happy_path(self) -> None:
        """Verifies adding a node registers its definition and updates node membership."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = lambda: "result_a"
            dag.add_node("node_a", action, None, 10, 2)

            self.assertTrue(dag.has_node("node_a"))
            self.assertEqual(dag.all_nodes(), {"node_a"})

            definition = dag.get_node("node_a")
            self.assertEqual(definition.node_id, "node_a")
            self.assertEqual(definition.priority, 10)
            self.assertEqual(definition.retries, 2)
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.action(), "result_a")

    def test_add_node_duplicate_raises_error(self) -> None:
        """Verifies duplicate node identifier raises DuplicateNodeError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", lambda: None, None, 0, 0)
            with self.assertRaises(DuplicateNodeError):
                dag.add_node("node_a", lambda: None, None, 1, 0)

    def test_add_node_directed_dependencies(self) -> None:
        """Verifies node added with dependencies establishes directed edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream_node", lambda: None, None, 0, 0)
            dag.add_node("downstream_node", lambda: None, ["upstream_node"], 0, 0)

            self.assertEqual(dag.get_dependencies("downstream_node"), {"upstream_node"})
            self.assertEqual(dag.get_dependents("upstream_node"), {"downstream_node"})

    def test_add_node_defer_dependency_checks(self) -> None:
        """Verifies missing dependencies are deferred without eager NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_child", lambda: None, ["unregistered_parent"], 0, 0)
            self.assertTrue(dag.has_node("task_child"))
            self.assertEqual(dag.get_dependencies("task_child"), {"unregistered_parent"})

    def test_add_edge_directed_edge(self) -> None:
        """Verifies adding a directed edge between existing nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_u", lambda: None, None, 0, 0)
            dag.add_node("node_v", lambda: None, None, 0, 0)
            dag.add_edge("node_u", "node_v")

            self.assertIn("node_v", dag.get_dependents("node_u"))
            self.assertIn("node_u", dag.get_dependencies("node_v"))

    def test_add_edge_missing_nodes_raise_error(self) -> None:
        """Verifies adding an edge with nonexistent nodes raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_valid", lambda: None, None, 0, 0)

            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("node_missing", "node_valid")

            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("node_valid", "node_missing")

    def test_remove_node_purge_incident_edges(self) -> None:
        """Verifies node removal purges all incident edges and node definition."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, 0)
            dag.add_node("b", lambda: None, ["a"], 0, 0)
            dag.add_node("c", lambda: None, ["b"], 0, 0)

            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertNotIn("b", dag.all_nodes())
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())

    def test_remove_node_missing_raises_error(self) -> None:
        """Verifies removing a nonexistent node raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("nonexistent_node")

    def test_remove_node_purge_scheduler_state(self) -> None:
        """Verifies node removal purges scheduler tracking state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("temp_node", lambda: None, None, 0, 0)
            self.assertEqual(scheduler.get_state("temp_node"), NodeState.READY)

            dag.remove_node("temp_node")
            self.assertNotIn("temp_node", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("temp_node")

    def test_has_node(self) -> None:
        """Verifies has_node returns correct presence boolean."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("node_x"))
            dag.add_node("node_x", lambda: None, None, 0, 0)
            self.assertTrue(dag.has_node("node_x"))

    def test_get_node_missing_raises_error(self) -> None:
        """Verifies retrieving definition of missing node raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_node("unregistered_node")

    def test_get_dependencies_missing_raises_error(self) -> None:
        """Verifies retrieving dependencies of missing node raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("missing_node")

    def test_get_dependents_missing_raises_error(self) -> None:
        """Verifies retrieving dependents of missing node raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("missing_node")

    def test_all_nodes(self) -> None:
        """Verifies all_nodes returns all registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            dag.add_node("n1", lambda: None, None, 0, 0)
            dag.add_node("n2", lambda: None, None, 0, 0)
            self.assertEqual(dag.all_nodes(), {"n1", "n2"})

    def test_validate_complete_valid(self) -> None:
        """Verifies validate completes without error for a valid DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None, None, 0, 0)
            dag.add_node("left", lambda: None, ["root"], 0, 0)
            dag.add_node("right", lambda: None, ["root"], 0, 0)
            dag.add_node("sink", lambda: None, ["left", "right"], 0, 0)
            dag.validate()

    def test_validate_missing_dependency_raises_error(self) -> None:
        """Verifies validate raises NodeNotFoundError when referenced dependency is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("child", lambda: None, ["ghost_parent"], 0, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_validate_cycle_raises_error(self) -> None:
        """Verifies validate raises CycleError when a directed cycle is present."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("cycle_1", lambda: None, ["cycle_2"], 0, 0)
            dag.add_node("cycle_2", lambda: None, ["cycle_1"], 0, 0)
            with self.assertRaises(CycleError):
                dag.validate()

    def test_topological_sort_dependency_order(self) -> None:
        """Verifies topological sort respects prerequisite ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, 0)
            dag.add_node("b", lambda: None, ["a"], 0, 0)
            dag.add_node("c", lambda: None, ["b"], 0, 0)
            dag.add_node("d", lambda: None, ["a"], 0, 0)

            order: List[str] = dag.topological_sort()
            self.assertEqual(len(order), 4)
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("b"), order.index("c"))
            self.assertLess(order.index("a"), order.index("d"))

    def test_topological_sort_tie_breaking(self) -> None:
        """Verifies topological sort breaks ties by priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("beta", lambda: None, None, 0, 0)
            dag.add_node("alpha", lambda: None, None, 0, 0)
            dag.add_node("priority_high", lambda: None, None, 10, 0)
            dag.add_node("priority_low", lambda: None, None, 1, 0)

            order = dag.topological_sort()
            self.assertEqual(order[0], "priority_high")
            self.assertEqual(order[1], "priority_low")
            self.assertEqual(order[2], "alpha")
            self.assertEqual(order[3], "beta")

    def test_topological_sort_cycle_raises_error(self) -> None:
        """Verifies topological sort raises CycleError when graph contains a cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("n1", lambda: None, ["n3"], 0, 0)
            dag.add_node("n2", lambda: None, ["n1"], 0, 0)
            dag.add_node("n3", lambda: None, ["n2"], 0, 0)
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_find_roots(self) -> None:
        """Verifies find_roots returns all in-degree zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_1", lambda: None, None, 0, 0)
            dag.add_node("root_2", lambda: None, None, 0, 0)
            dag.add_node("child", lambda: None, ["root_1", "root_2"], 0, 0)

            roots: Set[str] = dag.find_roots()
            self.assertEqual(roots, {"root_1", "root_2"})

    def test_find_leaves(self) -> None:
        """Verifies find_leaves returns all out-degree zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None, None, 0, 0)
            dag.add_node("leaf_1", lambda: None, ["root"], 0, 0)
            dag.add_node("leaf_2", lambda: None, ["root"], 0, 0)

            leaves: Set[str] = dag.find_leaves()
            self.assertEqual(leaves, {"leaf_1", "leaf_2"})

    def test_compute_critical_path_default_durations(self) -> None:
        """Verifies critical path calculation with default 1.0 node durations."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, 0)
            dag.add_node("b", lambda: None, ["a"], 0, 0)
            dag.add_node("c", lambda: None, ["b"], 0, 0)
            dag.add_node("short_branch", lambda: None, ["a"], 0, 0)

            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(weight, 3.0)

    def test_compute_critical_path_custom_durations(self) -> None:
        """Verifies critical path calculation with custom node durations."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", lambda: None, None, 0, 0)
            dag.add_node("fast_mid", lambda: None, ["start"], 0, 0)
            dag.add_node("slow_mid", lambda: None, ["start"], 0, 0)
            dag.add_node("end", lambda: None, ["fast_mid", "slow_mid"], 0, 0)

            durations = {
                "start": 1.5,
                "fast_mid": 2.0,
                "slow_mid": 10.0,
                "end": 0.5,
            }
            path, weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["start", "slow_mid", "end"])
            self.assertEqual(weight, 12.0)

    def test_compute_critical_path_empty_dag(self) -> None:
        """Verifies critical path calculation for an empty DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)



class WaveSchedulerTest(unittest.TestCase):
    """Unit tests for the WaveScheduler singleton service."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_next_wave_ready_nodes_and_priority_order(self) -> None:
        """Verifies next_wave returns ready nodes ordered by priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("root_low", lambda: None, None, 5, 0)
            dag.add_node("root_high", lambda: None, None, 20, 0)
            dag.add_node("root_mid_b", lambda: None, None, 10, 0)
            dag.add_node("root_mid_a", lambda: None, None, 10, 0)
            dag.add_node("dependent_task", lambda: None, ["root_high"], 100, 0)

            wave = scheduler.next_wave()
            self.assertEqual(wave, ["root_high", "root_mid_a", "root_mid_b", "root_low"])

    def test_next_wave_empty_when_no_ready(self) -> None:
        """Verifies next_wave returns an empty list when no nodes are ready."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running(self) -> None:
        """Verifies mark_running updates node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("task", lambda: None, None, 0, 0)
            self.assertEqual(scheduler.get_state("task"), NodeState.READY)

            scheduler.mark_running("task")
            self.assertEqual(scheduler.get_state("task"), NodeState.RUNNING)

    def test_mark_succeeded_and_promote_dependents(self) -> None:
        """Verifies mark_succeeded transitions node to SUCCEEDED and promotes dependents to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("p1", lambda: None, None, 0, 0)
            dag.add_node("p2", lambda: None, None, 0, 0)
            dag.add_node("child", lambda: None, ["p1", "p2"], 0, 0)

            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)

            scheduler.mark_succeeded("p1")
            self.assertEqual(scheduler.get_state("p1"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)

            scheduler.mark_succeeded("p2")
            self.assertEqual(scheduler.get_state("p2"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("child"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["child"])

    def test_mark_failed_skip_downstream(self) -> None:
        """Verifies mark_failed with SKIP_DOWNSTREAM marks transitive dependents as SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("failed_task", lambda: None, None, 0, 0)
            dag.add_node("child_1", lambda: None, ["failed_task"], 0, 0)
            dag.add_node("grandchild_1", lambda: None, ["child_1"], 0, 0)
            dag.add_node("independent_task", lambda: None, None, 0, 0)

            scheduler.mark_failed("failed_task", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("failed_task"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child_1"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("grandchild_1"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent_task"), NodeState.READY)

    def test_mark_failed_fail_fast(self) -> None:
        """Verifies mark_failed with FAIL_FAST cancels all non-terminal nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("root_a", lambda: None, None, 0, 0)
            dag.add_node("root_b", lambda: None, None, 0, 0)
            dag.add_node("dependent_c", lambda: None, ["root_a"], 0, 0)

            scheduler.mark_failed("root_a", FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("root_a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("root_b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("dependent_c"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error(self) -> None:
        """Verifies mark_failed with CONTINUE_ON_ERROR skips blocked dependents while retaining independent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("failing_root", lambda: None, None, 0, 0)
            dag.add_node("blocked_child", lambda: None, ["failing_root"], 0, 0)
            dag.add_node("independent_root", lambda: None, None, 0, 0)

            scheduler.mark_failed("failing_root", FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("failing_root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("blocked_child"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent_root"), NodeState.READY)

    def test_is_finished_empty_dag(self) -> None:
        """Verifies is_finished returns True for an empty DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_non_terminal_remaining(self) -> None:
        """Verifies is_finished returns False when non-terminal eligible nodes remain."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("task_1", lambda: None, None, 0, 0)
            dag.add_node("task_2", lambda: None, ["task_1"], 0, 0)

            # Ready and pending nodes are non-terminal
            self.assertEqual(scheduler.get_state("task_1"), NodeState.READY)
            self.assertEqual(scheduler.get_state("task_2"), NodeState.PENDING)
            self.assertFalse(scheduler.is_finished())

            # Running node is also non-terminal
            scheduler.mark_running("task_1")
            self.assertEqual(scheduler.get_state("task_1"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())


    def test_is_finished_all_terminal(self) -> None:
        """Verifies is_finished returns True when all nodes have reached terminal states."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("t1", lambda: None, None, 0, 0)
            dag.add_node("t2", lambda: None, None, 0, 0)

            scheduler.mark_succeeded("t1")
            scheduler.mark_failed("t2", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertTrue(scheduler.is_finished())

    def test_is_finished_blocked_by_failure(self) -> None:
        """Verifies is_finished returns True when unexecuted pending nodes are blocked by failed dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("succeeded_node", lambda: None, None, 0, 0)
            dag.add_node("failing_node", lambda: None, None, 0, 0)

            scheduler.mark_succeeded("succeeded_node")
            scheduler.mark_failed("failing_node", FailurePolicy.SKIP_DOWNSTREAM)

            # Add dependent nodes after failure so they are initialized to unexecuted PENDING state
            dag.add_node("blocked_child", lambda: None, ["failing_node"], 0, 0)
            dag.add_node("blocked_grandchild", lambda: None, ["blocked_child"], 0, 0)

            self.assertEqual(scheduler.get_state("blocked_child"), NodeState.PENDING)
            self.assertEqual(scheduler.get_state("blocked_grandchild"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_get_state_missing_node_raises_error(self) -> None:
        """Verifies get_state raises NodeNotFoundError for unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("nonexistent_task")

    def test_get_all_states(self) -> None:
        """Verifies get_all_states returns execution state of every registered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("root_task", lambda: None, None, 0, 0)
            dag.add_node("child_task", lambda: None, ["root_task"], 0, 0)

            states = scheduler.get_all_states()
            self.assertEqual(states["root_task"], NodeState.READY)
            self.assertEqual(states["child_task"], NodeState.PENDING)


class DAGRunnerTest(unittest.TestCase):
    """Unit tests for the DAGRunner singleton service."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_validate_before_waves_missing_dep(self) -> None:
        """Verifies run validates graph invariants and raises NodeNotFoundError for missing dependency."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("orphan", lambda: None, ["ghost_dep"], 0, 0)
            with self.assertRaises(NodeNotFoundError):
                runner.run(FailurePolicy.FAIL_FAST)

    def test_run_validate_before_waves_cycle(self) -> None:
        """Verifies run validates graph invariants and raises CycleError when a cycle is present."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("loop_a", lambda: None, ["loop_b"], 0, 0)
            dag.add_node("loop_b", lambda: None, ["loop_a"], 0, 0)
            with self.assertRaises(CycleError):
                runner.run(FailurePolicy.FAIL_FAST)

    def test_run_sequential_waves_happy_path(self) -> None:
        """Verifies sequential wave execution and consolidated report structure on success."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            execution_order: List[str] = []

            def action_a() -> str:
                execution_order.append("a")
                return "res_a"

            def action_b() -> str:
                execution_order.append("b")
                return "res_b"

            dag.add_node("a", action_a, None, 0, 0)
            dag.add_node("b", action_b, ["a"], 0, 0)

            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertEqual(execution_order, ["a", "b"])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("a", "b"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b"))

            res_a = report.results["a"]
            self.assertEqual(res_a.state, NodeState.SUCCEEDED)
            self.assertEqual(res_a.value, "res_a")
            self.assertIsNone(res_a.error)
            self.assertEqual(res_a.retries_attempted, 0)

            res_b = report.results["b"]
            self.assertEqual(res_b.state, NodeState.SUCCEEDED)
            self.assertEqual(res_b.value, "res_b")
            self.assertIsNone(res_b.error)
            self.assertEqual(res_b.retries_attempted, 0)

    def test_run_halts_when_wave_empty_with_running_node(self) -> None:
        """Verifies runner halts wave loop when next wave is empty despite running node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("task_running", lambda: "ok", None, 0, 0)
            scheduler.mark_running("task_running")

            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])

            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(report.total_nodes, 1)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())


    def test_run_retry_failures_eventual_success(self) -> None:
        """Verifies runner retries failed actions up to retries count before success."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            attempts = 0

            def flaky_action() -> str:
                nonlocal attempts
                attempts += 1
                if attempts <= 1:
                    raise RuntimeError("intermittent error")
                return "recovered"

            dag.add_node("flaky_node", flaky_action, None, 0, 1)

            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertIn("flaky_node", report.succeeded_nodes)
            res = report.results["flaky_node"]
            self.assertEqual(res.state, NodeState.SUCCEEDED)
            self.assertEqual(res.value, "recovered")
            self.assertEqual(res.retries_attempted, 1)

    def test_run_retry_failures_exhausted(self) -> None:
        """Verifies runner marks node FAILED after retry attempts are exhausted."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            attempts = 0

            def persistent_failure() -> None:
                nonlocal attempts
                attempts += 1
                raise ValueError("permanent error")

            dag.add_node("failing_node", persistent_failure, None, 0, 2)

            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("failing_node", report.failed_nodes)
            res = report.results["failing_node"]
            self.assertEqual(res.state, NodeState.FAILED)
            self.assertEqual(res.retries_attempted, 2)
            self.assertIsInstance(res.error, ValueError)

    def test_run_apply_failure_policy_fail_fast(self) -> None:
        """Verifies FAIL_FAST stops further wave execution and cancels unexecuted nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def failing_action() -> None:
                raise RuntimeError("critical crash")

            dag.add_node("faulty", failing_action, None, 10, 0)
            dag.add_node("pending_indep", lambda: "ok", None, 0, 0)
            dag.add_node("pending_dep", lambda: "ok", ["faulty"], 0, 0)

            report = runner.run(FailurePolicy.FAIL_FAST)

            self.assertIn("faulty", report.failed_nodes)
            self.assertIn("pending_indep", report.cancelled_nodes)
            self.assertIn("pending_dep", report.cancelled_nodes)
            self.assertEqual(report.succeeded_nodes, ())

    def test_run_apply_failure_policy_skip_downstream(self) -> None:
        """Verifies SKIP_DOWNSTREAM skips transitive dependents while independent nodes succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def bad_action() -> None:
                raise RuntimeError("node failed")

            dag.add_node("bad_node", bad_action, None, 10, 0)
            dag.add_node("dep_node", lambda: "ok", ["bad_node"], 0, 0)
            dag.add_node("good_node", lambda: "ok", None, 5, 0)

            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)

            self.assertIn("bad_node", report.failed_nodes)
            self.assertIn("dep_node", report.skipped_nodes)
            self.assertIn("good_node", report.succeeded_nodes)

    def test_run_apply_failure_policy_continue_on_error(self) -> None:
        """Verifies CONTINUE_ON_ERROR skips blocked dependents while independent nodes succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def faulty_action() -> None:
                raise RuntimeError("error")

            dag.add_node("fail_task", faulty_action, None, 10, 0)
            dag.add_node("blocked_task", lambda: "ok", ["fail_task"], 0, 0)
            dag.add_node("independent_task", lambda: "ok", None, 1, 0)

            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("fail_task", report.failed_nodes)
            self.assertIn("blocked_task", report.skipped_nodes)
            self.assertIn("independent_task", report.succeeded_nodes)

    def test_run_empty_dag(self) -> None:
        """Verifies runner completes cleanly on an empty DAG."""
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



if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T02:42:20Z
# LAST_CHANGED: 2026-11-11T02:41:21Z
# CHANGE: Verify is_finished returns True when unexecuted pending nodes are blocked by failed dependencies resolving coverage feedback
# COVERAGE_AUDIT: 2026-11-11T02:42:20Z
# QA_AUDIT: 2026-11-11T02:41:51Z
# --- END AUTOFAB METADATA ---
