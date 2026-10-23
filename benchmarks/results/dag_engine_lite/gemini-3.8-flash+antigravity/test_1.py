"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

from typing import List
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class DagTest(unittest.TestCase):
    """Verifies the DAG container, graph operations, validation, and topological sorting."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_default_attributes(self) -> None:
        """WHEN a node is added without optional attributes, MUST register node with default priority and retries."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", lambda: "val_a")
            self.assertTrue(dag.has_node("node_a"))
            node_def = dag.get_node("node_a")
            self.assertEqual(node_def.node_id, "node_a")
            self.assertEqual(node_def.priority, 0)
            self.assertEqual(node_def.retries, 0)
            self.assertEqual(node_def.dependencies, frozenset())

    def test_add_node_with_custom_attributes_and_dependencies(self) -> None:
        """WHEN a node is added with priority, retries, and dependencies, MUST register edges and definition."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream_1", lambda: 1)
            dag.add_node("upstream_2", lambda: 2)
            dag.add_node(
                "downstream",
                lambda: 3,
                dependencies=["upstream_1", "upstream_2"],
                priority=10,
                retries=3,
            )
            node_def = dag.get_node("downstream")
            self.assertEqual(node_def.priority, 10)
            self.assertEqual(node_def.retries, 3)
            self.assertEqual(node_def.dependencies, frozenset(["upstream_1", "upstream_2"]))
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream_1", "upstream_2"})
            self.assertIn("downstream", dag.get_dependents("upstream_1"))
            self.assertIn("downstream", dag.get_dependents("upstream_2"))

    def test_re_register_node_replaces_definition_and_dependencies(self) -> None:
        """WHEN an existing node is re-registered, MUST replace its definition and dependency edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("dep1", lambda: 1)
            dag.add_node("dep2", lambda: 2)
            dag.add_node("target", lambda: "old", dependencies=["dep1"], priority=1, retries=0)
            self.assertEqual(dag.get_node("target").priority, 1)
            self.assertEqual(dag.get_dependencies("target"), {"dep1"})
            self.assertIn("target", dag.get_dependents("dep1"))

            dag.add_node("target", lambda: "new", dependencies=["dep2"], priority=5, retries=2)
            new_def = dag.get_node("target")
            self.assertEqual(new_def.priority, 5)
            self.assertEqual(new_def.retries, 2)
            self.assertEqual(new_def.dependencies, frozenset(["dep2"]))
            self.assertEqual(dag.get_dependencies("target"), {"dep2"})
            self.assertNotIn("target", dag.get_dependents("dep1"))
            self.assertIn("target", dag.get_dependents("dep2"))

    def test_add_edge_happy_path(self) -> None:
        """WHEN adding an edge between existing nodes, MUST establish directed dependency."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("u", lambda: None)
            dag.add_node("v", lambda: None)
            dag.add_edge("u", "v")
            self.assertIn("u", dag.get_dependencies("v"))
            self.assertIn("v", dag.get_dependents("u"))

    def test_add_edge_missing_nodes_raises_not_found(self) -> None:
        """WHEN adding an edge referencing a missing node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("exists", lambda: None)
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("missing", "exists")
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("exists", "missing")

    def test_remove_node_and_incident_edges(self) -> None:
        """WHEN removing a node, MUST remove the node and update all incident dependency sets."""
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

    def test_remove_missing_node_raises_not_found(self) -> None:
        """WHEN removing a non-existent node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("non_existent")

    def test_get_node_missing_raises_not_found(self) -> None:
        """WHEN looking up an absent node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_node("absent")

    def test_get_dependencies_and_dependents_missing_node(self) -> None:
        """WHEN querying dependencies or dependents for a missing node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("missing")
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("missing")

    def test_all_nodes(self) -> None:
        """WHEN querying all_nodes, MUST return a set of all registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            dag.add_node("n1", lambda: 1)
            dag.add_node("n2", lambda: 2)
            self.assertEqual(dag.all_nodes(), {"n1", "n2"})

    def test_find_roots_and_leaves(self) -> None:
        """WHEN querying roots and leaves, MUST correctly identify in-degree and out-degree zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root1", lambda: None)
            dag.add_node("root2", lambda: None)
            dag.add_node("mid", lambda: None, dependencies=["root1", "root2"])
            dag.add_node("leaf1", lambda: None, dependencies=["mid"])
            dag.add_node("leaf2", lambda: None, dependencies=["mid"])
            self.assertEqual(dag.find_roots(), {"root1", "root2"})
            self.assertEqual(dag.find_leaves(), {"leaf1", "leaf2"})

    def test_validate_happy_path(self) -> None:
        """WHEN all dependencies exist and no cycle exists, MUST validate without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.validate()

    def test_validate_missing_dependency_raises_not_found(self) -> None:
        """WHEN a node definition references a dependency missing from the graph, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, dependencies=["ghost"])
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """WHEN a cycle exists, MUST raise CycleError containing the cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_topological_sort_and_tie_breaking(self) -> None:
        """WHEN sorting topologically, MUST respect dependencies and break ties by priority descending, name ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c", lambda: None, priority=5)
            dag.add_node("b", lambda: None, priority=10)
            dag.add_node("a", lambda: None, priority=10)
            dag.add_node("d", lambda: None, dependencies=["a", "b", "c"], priority=100)
            order = dag.topological_sort()
            self.assertEqual(order[:3], ["a", "b", "c"])
            self.assertEqual(order[3], "d")

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """WHEN topological sort encounters a cycle, MUST raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("x", lambda: None)
            dag.add_node("y", lambda: None, dependencies=["x"])
            dag.add_edge("y", "x")
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_compute_critical_path_default_and_custom_weights(self) -> None:
        """WHEN computing critical path, MUST return longest weighted path and total weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", lambda: None)
            dag.add_node("short_branch", lambda: None, dependencies=["start"])
            dag.add_node("long_branch_1", lambda: None, dependencies=["start"])
            dag.add_node("long_branch_2", lambda: None, dependencies=["long_branch_1"])
            dag.add_node("end", lambda: None, dependencies=["short_branch", "long_branch_2"])

            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["start", "long_branch_1", "long_branch_2", "end"])
            self.assertEqual(weight, 4.0)

            durations = {
                "start": 1.0,
                "short_branch": 10.0,
                "long_branch_1": 1.0,
                "long_branch_2": 1.0,
                "end": 1.0,
            }
            path2, weight2 = dag.compute_critical_path(estimated_durations=durations)
            self.assertEqual(path2, ["start", "short_branch", "end"])
            self.assertEqual(weight2, 12.0)

    def test_compute_critical_path_empty_dag(self) -> None:
        """WHEN the DAG is empty, computing critical path MUST return an empty path and zero duration."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, duration = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(duration, 0.0)


class WaveSchedulerTest(unittest.TestCase):
    """Verifies sequential wave resolution, state transitions, and failure policies."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_empty_graph_finished_and_no_waves(self) -> None:
        """WHEN the graph has no nodes, scheduler MUST report finished and return empty wave."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(scheduler.get_all_states(), {})

    def test_wave_ordering_by_priority_and_name(self) -> None:
        """WHEN roots are ready, next_wave MUST order by priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_z", lambda: None, priority=5)
            dag.add_node("node_b", lambda: None, priority=10)
            dag.add_node("node_a", lambda: None, priority=10)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), ["node_a", "node_b", "node_z"])

    def test_state_transitions_running_and_succeeded(self) -> None:
        """WHEN a node completes successfully, MUST transition to SUCCEEDED and unblock downstream nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("step1", lambda: None)
            dag.add_node("step2", lambda: None, dependencies=["step1"])
            scheduler = scope.get_singleton(WaveScheduler)

            wave1 = scheduler.next_wave()
            self.assertEqual(wave1, ["step1"])
            scheduler.mark_running("step1")
            self.assertEqual(scheduler.get_state("step1"), NodeState.RUNNING)
            self.assertEqual(scheduler.get_state("step2"), NodeState.PENDING)

            scheduler.mark_succeeded("step1")
            self.assertEqual(scheduler.get_state("step1"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("step2"), NodeState.READY)

            wave2 = scheduler.next_wave()
            self.assertEqual(wave2, ["step2"])
            scheduler.mark_running("step2")
            scheduler.mark_succeeded("step2")
            self.assertEqual(scheduler.get_state("step2"), NodeState.SUCCEEDED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_fail_fast_policy(self) -> None:
        """WHEN mark_failed is invoked with FAIL_FAST, MUST transition remaining pending nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_node", lambda: None)
            dag.add_node("dependent_node", lambda: None, dependencies=["fail_node"])
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("fail_node")
            scheduler.mark_failed("fail_node", failure_policy=FailurePolicy.FAIL_FAST)

            states = scheduler.get_all_states()
            self.assertEqual(states["fail_node"], NodeState.FAILED)
            self.assertEqual(states["dependent_node"], NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_policy(self) -> None:
        """WHEN mark_failed is invoked with SKIP_DOWNSTREAM, MUST transition transitive dependents to SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failed_root", lambda: None)
            dag.add_node("independent_root", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["failed_root"])
            dag.add_node("grandchild", lambda: None, dependencies=["child"])
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("failed_root")
            scheduler.mark_failed("failed_root", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("failed_root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("grandchild"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent_root"), NodeState.READY)
            self.assertFalse(scheduler.is_finished())

            self.assertEqual(scheduler.next_wave(), ["independent_root"])

    def test_mark_failed_continue_on_error_policy(self) -> None:
        """WHEN mark_failed is invoked with CONTINUE_ON_ERROR, independent nodes MUST remain eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_root", lambda: None)
            dag.add_node("good_root", lambda: None)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("fail_root")
            scheduler.mark_failed("fail_root", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("fail_root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("good_root"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["good_root"])

    def test_get_state_prior_to_wave_execution_initializes_state(self) -> None:
        """WHEN querying state for registered nodes prior to wave execution, scheduler MUST initialize root to READY and dependent to PENDING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["root"])
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.get_state("root"), NodeState.READY)
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)

    def test_get_state_unregistered_node_raises_not_found(self) -> None:
        """WHEN querying state for an unregistered node identifier, scheduler MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("unknown_node")

    def test_remove_node_synchronizes_scheduler_state(self) -> None:
        """WHEN a node is removed from the DAG, scheduler state MUST synchronize and omit the removed node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("removable", lambda: None)
            dag.add_node("keeper", lambda: None)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.get_state("removable"), NodeState.READY)
            self.assertIn("removable", scheduler.get_all_states())

            dag.remove_node("removable")

            self.assertNotIn("removable", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("removable")


class DAGRunnerTest(unittest.TestCase):
    """Verifies end-to-end execution of DAGs under DAGRunner and failure policies."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_successful_linear_pipeline(self) -> None:
        """WHEN all nodes succeed, MUST return DAGRunReport with all nodes succeeded and results populated."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 10)
            dag.add_node("second", lambda: 20, dependencies=["first"])
            runner = scope.get_singleton(DAGRunner)

            report = runner.run()
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("first", "second"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertIn("first", report.results)
            self.assertIn("second", report.results)
            self.assertEqual(report.results["first"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["first"].value, 10)
            self.assertEqual(report.results["second"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["second"].value, 20)
            self.assertEqual(report.critical_path, ("first", "second"))
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_validates_dag_and_propagates_cycle_error(self) -> None:
        """WHEN the DAG has a cycle, run MUST propagate CycleError upon validation."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_edge("b", "a")
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(CycleError):
                runner.run()

    def test_run_validates_dag_and_propagates_node_not_found_error(self) -> None:
        """WHEN the DAG references a missing dependency, run MUST propagate NodeNotFoundError upon validation."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node", lambda: None, dependencies=["missing_upstream"])
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(NodeNotFoundError):
                runner.run()

    def test_run_node_retries_and_recovers(self) -> None:
        """WHEN a node fails initially but succeeds within retries limit, MUST complete SUCCEEDED."""
        attempts = 0

        def flaky_action() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("Transient error")
            return "recovered"

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", flaky_action, retries=2)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run()
            self.assertEqual(report.succeeded_nodes, ("flaky",))
            self.assertEqual(report.failed_nodes, ())
            result = report.results["flaky"]
            self.assertEqual(result.state, NodeState.SUCCEEDED)
            self.assertEqual(result.value, "recovered")
            self.assertEqual(result.retries_attempted, 1)

    def test_run_fail_fast_policy(self) -> None:
        """WHEN a node fails under FAIL_FAST, MUST cancel pending nodes and stop execution."""
        def failing_action() -> None:
            raise RuntimeError("Permanent failure")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_fail", failing_action, retries=0)
            dag.add_node("dependent_node", lambda: "ok", dependencies=["root_fail"])
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST)
            self.assertEqual(report.failed_nodes, ("root_fail",))
            self.assertEqual(report.cancelled_nodes, ("dependent_node",))
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.results["root_fail"].state, NodeState.FAILED)
            self.assertIsInstance(report.results["root_fail"].error, RuntimeError)
            self.assertEqual(report.results["dependent_node"].state, NodeState.CANCELLED)

    def test_run_skip_downstream_policy(self) -> None:
        """WHEN a node fails under SKIP_DOWNSTREAM, MUST skip downstream nodes and complete independent nodes."""
        def failing_action() -> None:
            raise ValueError("Failure")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_branch_root", failing_action, retries=0)
            dag.add_node("fail_branch_child", lambda: None, dependencies=["fail_branch_root"])
            dag.add_node("good_branch", lambda: "success")
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
            self.assertIn("fail_branch_root", report.failed_nodes)
            self.assertIn("fail_branch_child", report.skipped_nodes)
            self.assertIn("good_branch", report.succeeded_nodes)
            self.assertEqual(report.results["fail_branch_child"].state, NodeState.SKIPPED)

    def test_run_continue_on_error_policy(self) -> None:
        """WHEN a node fails under CONTINUE_ON_ERROR, independent nodes MUST execute to completion."""
        def failing_action() -> None:
            raise RuntimeError("Error")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_node", failing_action, retries=0)
            dag.add_node("independent_node", lambda: "completed")
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            self.assertIn("fail_node", report.failed_nodes)
            self.assertIn("independent_node", report.succeeded_nodes)

    def test_run_node_retries_exhausted_records_failed_result(self) -> None:
        """WHEN an action exhausts all retries, runner MUST record a failed node result with retry count."""
        attempts = 0

        def always_failing_action() -> None:
            nonlocal attempts
            attempts += 1
            raise RuntimeError(f"Attempt {attempts} failed")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("exhausted_node", always_failing_action, retries=2)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(attempts, 3)
            self.assertEqual(report.failed_nodes, ("exhausted_node",))
            result = report.results["exhausted_node"]
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertIsInstance(result.error, RuntimeError)
            self.assertEqual(result.retries_attempted, 2)

    def test_run_continue_on_error_terminates_when_unready_tasks_remain_blocked(self) -> None:
        """WHEN running under CONTINUE_ON_ERROR with dependent tasks of a failed node, wave loop MUST terminate when blocked."""
        def failing_action() -> None:
            raise RuntimeError("Root failed")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failed_root", failing_action, retries=0)
            dag.add_node("blocked_child", lambda: "should not run", dependencies=["failed_root"])
            dag.add_node("independent", lambda: "completed")
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            self.assertIn("failed_root", report.failed_nodes)
            self.assertIn("independent", report.succeeded_nodes)
            self.assertNotIn("blocked_child", report.succeeded_nodes)
            self.assertNotIn("blocked_child", report.failed_nodes)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T17:44:32Z
# LAST_CHANGED: 2026-10-23T17:43:31Z
# CHANGE: Add missing unit test cases for node re-registration, empty DAG critical path, scheduler state initialization and unregistration error handling, node removal scheduler synchronization, continue-on-error blocked task termination, and retries exhaustion failure recording.
# COVERAGE_AUDIT: 2026-10-23T17:44:32Z
# QA_AUDIT: 2026-10-23T17:44:07Z
# --- END CLEANROOM METADATA ---
