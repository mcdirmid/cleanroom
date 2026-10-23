"""Unit tests for dag_engine_impl per its grounding specification."""

from __future__ import annotations

import time
from typing import Any
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_2.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGRunReport,
    DAGTimeoutError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from benchmark_2.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class DagTest(unittest.TestCase):
    """Verifies behavioral contracts and invariants of the DAG component."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_default_parameters(self) -> None:
        """WHEN adding a node with default arguments, MUST register definition with defaults."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = lambda: "test"
            dag.add_node("task_1", action=action)

            self.assertTrue(dag.has_node("task_1"))
            self.assertIn("task_1", dag.all_nodes())
            node_def = dag.get_node("task_1")
            self.assertEqual(node_def.node_id, "task_1")
            self.assertEqual(node_def.dependencies, frozenset())
            self.assertEqual(node_def.priority, 0)
            self.assertIsNone(node_def.timeout_seconds)
            self.assertEqual(node_def.retries, 0)
            self.assertEqual(dag.get_dependencies("task_1"), set())
            self.assertEqual(dag.get_dependents("task_1"), set())

    def test_add_node_custom_parameters(self) -> None:
        """WHEN adding a node with custom priority, timeout, and retries, MUST store configured values."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node(
                "task_custom",
                action=lambda: None,
                priority=10,
                timeout_seconds=5.0,
                retries=3,
            )

            node_def = dag.get_node("task_custom")
            self.assertEqual(node_def.node_id, "task_custom")
            self.assertEqual(node_def.priority, 10)
            self.assertEqual(node_def.timeout_seconds, 5.0)
            self.assertEqual(node_def.retries, 3)

    def test_add_node_with_dependencies(self) -> None:
        """WHEN dependencies are provided to add_node, MUST establish dependency edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", action=lambda: 1)
            dag.add_node("downstream", action=lambda: 2, dependencies=["upstream"])

            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_add_edge_success(self) -> None:
        """WHEN both nodes exist, add_edge MUST establish directed dependency edge."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: None)
            dag.add_node("node_b", action=lambda: None)
            dag.add_edge("node_a", "node_b")

            self.assertEqual(dag.get_dependents("node_a"), {"node_b"})
            self.assertEqual(dag.get_dependencies("node_b"), {"node_a"})

    def test_add_edge_missing_upstream_raises(self) -> None:
        """WHEN upstream_id does not exist, add_edge MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_b", action=lambda: None)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("missing_upstream", "node_b")
            self.assertEqual(ctx.exception.node_id, "missing_upstream")

    def test_add_edge_missing_downstream_raises(self) -> None:
        """WHEN downstream_id does not exist, add_edge MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: None)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("node_a", "missing_downstream")
            self.assertEqual(ctx.exception.node_id, "missing_downstream")

    def test_remove_node_success(self) -> None:
        """WHEN an existing node is removed, MUST remove node and all incident edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None, dependencies=["b"])

            dag.remove_node("b")

            self.assertFalse(dag.has_node("b"))
            self.assertNotIn("b", dag.all_nodes())
            self.assertNotIn("b", dag.get_dependents("a"))
            self.assertNotIn("b", dag.get_dependencies("c"))

    def test_remove_node_missing_raises(self) -> None:
        """WHEN removing an absent node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.remove_node("missing_node")
            self.assertEqual(ctx.exception.node_id, "missing_node")

    def test_has_node(self) -> None:
        """has_node MUST return True if node exists, False otherwise."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("node_x"))
            dag.add_node("node_x", action=lambda: None)
            self.assertTrue(dag.has_node("node_x"))

    def test_get_node_missing_raises(self) -> None:
        """WHEN retrieving an absent node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("absent_node")
            self.assertEqual(ctx.exception.node_id, "absent_node")

    def test_get_dependencies_missing_raises(self) -> None:
        """WHEN querying dependencies for an absent node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependencies("absent_node")
            self.assertEqual(ctx.exception.node_id, "absent_node")

    def test_get_dependents_missing_raises(self) -> None:
        """WHEN querying dependents for an absent node, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependents("absent_node")
            self.assertEqual(ctx.exception.node_id, "absent_node")

    def test_all_nodes(self) -> None:
        """all_nodes MUST return the full set of registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())

            dag.add_node("x", action=lambda: None)
            dag.add_node("y", action=lambda: None)
            self.assertEqual(dag.all_nodes(), {"x", "y"})

    def test_validate_success(self) -> None:
        """WHEN all nodes exist and no cycles exist, validate MUST succeed without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None, dependencies=["b"])

            dag.validate()

    def test_validate_missing_dependency_raises(self) -> None:
        """WHEN a referenced dependency node does not exist, validate MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("b", action=lambda: None, dependencies=["missing_a"])

            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "missing_a")

    def test_validate_cycle_raises(self) -> None:
        """WHEN a directed cycle exists, validate MUST raise CycleError with cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None)
            dag.add_node("c", action=lambda: None)
            dag.add_edge("a", "b")
            dag.add_edge("b", "c")
            dag.add_edge("c", "a")

            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertTrue(len(ctx.exception.cycle) > 0)

    def test_topological_sort_linear(self) -> None:
        """topological_sort MUST return ordering where prerequisites precede dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None, dependencies=["b"])

            order = dag.topological_sort()
            self.assertEqual(order, ["a", "b", "c"])

    def test_topological_sort_tie_breaking(self) -> None:
        """topological_sort MUST break ties by priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_b", action=lambda: None, priority=10)
            dag.add_node("task_a", action=lambda: None, priority=20)
            dag.add_node("task_c", action=lambda: None, priority=10)
            dag.add_node("task_d", action=lambda: None, priority=5)

            order = dag.topological_sort()
            self.assertEqual(order, ["task_a", "task_b", "task_c", "task_d"])

    def test_topological_sort_cycle_raises(self) -> None:
        """WHEN graph contains a cycle, topological_sort MUST raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("x", action=lambda: None)
            dag.add_node("y", action=lambda: None)
            dag.add_edge("x", "y")
            dag.add_edge("y", "x")

            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_find_roots(self) -> None:
        """find_roots MUST return all nodes with in-degree zero."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_1", action=lambda: None)
            dag.add_node("root_2", action=lambda: None)
            dag.add_node("child", action=lambda: None, dependencies=["root_1", "root_2"])

            self.assertEqual(dag.find_roots(), {"root_1", "root_2"})

    def test_find_leaves(self) -> None:
        """find_leaves MUST return all nodes with out-degree zero."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", action=lambda: None)
            dag.add_node("leaf_1", action=lambda: None, dependencies=["root"])
            dag.add_node("leaf_2", action=lambda: None, dependencies=["root"])

            self.assertEqual(dag.find_leaves(), {"leaf_1", "leaf_2"})

    def test_compute_critical_path_empty_dag(self) -> None:
        """compute_critical_path on an empty DAG MUST return empty path and 0.0 weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    def test_compute_critical_path_unweighted(self) -> None:
        """compute_critical_path MUST default to 1.0 weight per node and return longest path."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            # Branch 1: a -> b -> d (weight 3.0)
            # Branch 2: a -> c -> e -> d (weight 4.0)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None, dependencies=["a"])
            dag.add_node("e", action=lambda: None, dependencies=["c"])
            dag.add_node("d", action=lambda: None, dependencies=["b", "e"])

            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["a", "c", "e", "d"])
            self.assertEqual(weight, 4.0)

    def test_compute_critical_path_weighted(self) -> None:
        """compute_critical_path MUST resolve node weights from estimated_durations."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            # Branch 1: a (2.0) -> b (10.0) -> d (3.0) = 15.0
            # Branch 2: a (2.0) -> c (1.0) -> d (3.0) = 6.0
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None, dependencies=["a"])
            dag.add_node("d", action=lambda: None, dependencies=["b", "c"])

            durations = {"a": 2.0, "b": 10.0, "c": 1.0, "d": 3.0}
            path, weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["a", "b", "d"])
            self.assertEqual(weight, 15.0)


class WaveSchedulerTest(unittest.TestCase):
    """Verifies wave scheduling, state transitions, dynamic registration, and failure policies."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_next_wave_roots_ordered(self) -> None:
        """next_wave MUST return all READY nodes ordered by priority descending, then name ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_b", action=lambda: None, priority=10)
            dag.add_node("task_a", action=lambda: None, priority=20)
            dag.add_node("task_c", action=lambda: None, priority=10)
            dag.add_node("task_d", action=lambda: None, priority=5)

            scheduler = scope.get_singleton(WaveScheduler)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["task_a", "task_b", "task_c", "task_d"])

    def test_next_wave_empty(self) -> None:
        """WHEN DAG contains no ready nodes, next_wave MUST return an empty list."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running(self) -> None:
        """mark_running MUST transition node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_1", action=lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("task_1")
            self.assertEqual(scheduler.get_state("task_1"), NodeState.RUNNING)

    def test_mark_succeeded_unlocks_dependents(self) -> None:
        """mark_succeeded MUST update state and promote unblocked dependents to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("a"), NodeState.READY)
            self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)

            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("b"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_mark_succeeded_multi_dependency(self) -> None:
        """A dependent node MUST NOT be promoted to READY until ALL upstream dependencies succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None)
            dag.add_node("c", action=lambda: None, dependencies=["a", "b"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("c"), NodeState.PENDING)

            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("c"), NodeState.PENDING)

            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("c"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_dynamic_node_registration_downstream_ready_when_upstream_succeeded(self) -> None:
        """WHEN dynamic node registration occurs in DAG where upstream dependencies are already SUCCEEDED, downstream node MUST become READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", action=lambda: "done")

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("upstream"), NodeState.READY)
            scheduler.mark_running("upstream")
            scheduler.mark_succeeded("upstream")
            self.assertEqual(scheduler.get_state("upstream"), NodeState.SUCCEEDED)

            # Dynamically register downstream node after upstream has already succeeded
            dag.add_node("downstream", action=lambda: "next", dependencies=["upstream"])

            # Downstream should be discovered and promoted to READY since its upstream is SUCCEEDED
            wave = scheduler.next_wave()
            self.assertIn("downstream", wave)
            self.assertEqual(scheduler.get_state("downstream"), NodeState.READY)

    def test_prune_scheduler_states_when_node_removed(self) -> None:
        """WHEN a registered node is removed from the DAG, scheduler states MUST be pruned."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("to_remove", action=lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("to_remove"), NodeState.READY)
            self.assertIn("to_remove", scheduler.get_all_states())

            # Remove node from DAG
            dag.remove_node("to_remove")

            # Scheduler synchronization should prune to_remove from states
            self.assertNotIn("to_remove", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("to_remove")
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_fail_fast(self) -> None:
        """WHEN failure_policy is FAIL_FAST, mark_failed MUST cancel all remaining pending nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", failure_policy=FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream(self) -> None:
        """WHEN failure_policy is SKIP_DOWNSTREAM, transitive dependents MUST transition to SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("c", action=lambda: None, dependencies=["b"])
            dag.add_node("d", action=lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.READY)

    def test_mark_failed_continue_on_error(self) -> None:
        """WHEN failure_policy is CONTINUE_ON_ERROR, independent nodes MUST remain eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])
            dag.add_node("d", action=lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("d"), NodeState.READY)

    def test_is_finished_empty_dag(self) -> None:
        """is_finished MUST return True when DAG contains no nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_progression(self) -> None:
        """is_finished MUST return False while nodes are non-terminal and True when all are terminal."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("a")
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_succeeded("a")
            self.assertTrue(scheduler.is_finished())

    def test_get_state_unregistered_node_raises_node_not_found(self) -> None:
        """WaveScheduler.get_state MUST raise NodeNotFoundError when queried with unregistered node identifier."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError) as ctx:
                scheduler.get_state("unregistered_node_id")
            self.assertEqual(ctx.exception.node_id, "unregistered_node_id")

    def test_get_all_states(self) -> None:
        """get_all_states MUST return the current NodeState of every registered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None, dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_succeeded("a")

            states = scheduler.get_all_states()
            self.assertEqual(states["a"], NodeState.SUCCEEDED)
            self.assertEqual(states["b"], NodeState.READY)


class DAGRunnerTest(unittest.TestCase):
    """Verifies end-to-end DAG execution, retries, failure policies, timeouts, and cancellation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_success_chain(self) -> None:
        """run MUST execute nodes, record results, and return consolidated DAGRunReport."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: 10)
            dag.add_node("b", action=lambda: 20, dependencies=["a"])
            dag.add_node("c", action=lambda: 30, dependencies=["b"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b", "c"))
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["a"].value, 10)
            self.assertEqual(report.results["b"].value, 20)
            self.assertEqual(report.results["c"].value, 30)

    def test_run_concurrent_diamond(self) -> None:
        """run MUST execute ready nodes concurrently up to max_concurrency limit."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "start")
            dag.add_node("b", action=lambda: "left", dependencies=["a"])
            dag.add_node("c", action=lambda: "right", dependencies=["a"])
            dag.add_node("d", action=lambda: "end", dependencies=["b", "c"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=2)

            self.assertEqual(report.total_nodes, 4)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c", "d"})
            self.assertEqual(report.results["d"].value, "end")

    def test_run_validates_dag_cycle_raises(self) -> None:
        """run MUST validate DAG and raise CycleError if a directed cycle exists."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None)
            dag.add_node("b", action=lambda: None)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(CycleError):
                runner.run()

    def test_run_validates_dag_missing_dependency_raises(self) -> None:
        """run MUST validate DAG and raise NodeNotFoundError if dependency is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: None, dependencies=["missing_prereq"])

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(NodeNotFoundError):
                runner.run()

    def test_run_with_retries_recovers(self) -> None:
        """run MUST execute retries up to definition.retries upon failure and recover."""
        with enter_phase(system, registry=self.registry) as scope:
            attempts = 0

            def flaky_action() -> str:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise RuntimeError("temporary failure")
                return "recovered"

            dag = scope.get_singleton(DAG)
            dag.add_node("retry_task", action=flaky_action, retries=2)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertIn("retry_task", report.succeeded_nodes)
            node_result = report.results["retry_task"]
            self.assertEqual(node_result.state, NodeState.SUCCEEDED)
            self.assertEqual(node_result.value, "recovered")
            self.assertEqual(node_result.retries_attempted, 2)

    def test_retry_attempts_upon_node_action_exceptions(self) -> None:
        """DAG execution MUST execute retry attempts upon node action exceptions up to definition.retries."""
        with enter_phase(system, registry=self.registry) as scope:
            attempts = 0

            def failing_action() -> None:
                nonlocal attempts
                attempts += 1
                raise RuntimeError(f"exception attempt {attempts}")

            dag = scope.get_singleton(DAG)
            dag.add_node("failing_retry_task", action=failing_action, retries=3)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("failing_retry_task", report.failed_nodes)
            result = report.results["failing_retry_task"]
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertEqual(result.retries_attempted, 3)
            self.assertEqual(attempts, 4)  # 1 initial attempt + 3 retries
            self.assertIsNotNone(result.error)

    def test_node_definition_timeout_triggers_action_timeout(self) -> None:
        """WHEN individual NodeDefinition timeout_seconds is exceeded, node action timeout MUST be triggered and recorded as failure."""
        with enter_phase(system, registry=self.registry) as scope:
            def slow_node_action() -> None:
                time.sleep(0.05)

            dag = scope.get_singleton(DAG)
            dag.add_node(
                "timed_out_node",
                action=slow_node_action,
                timeout_seconds=0.01,
                retries=0,
            )

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("timed_out_node", report.failed_nodes)
            result = report.results["timed_out_node"]
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertIsNotNone(result.error)

    def test_run_failure_policy_fail_fast(self) -> None:
        """WHEN node fails under FAIL_FAST, run MUST record failure and cancel non-terminal nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            def failing_action() -> None:
                raise ValueError("terminal failure")

            dag = scope.get_singleton(DAG)
            dag.add_node("fail_node", action=failing_action, retries=0)
            dag.add_node("dependent", action=lambda: 1, dependencies=["fail_node"])
            dag.add_node("independent", action=lambda: 2)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST)

            self.assertIn("fail_node", report.failed_nodes)
            self.assertEqual(report.results["fail_node"].state, NodeState.FAILED)
            self.assertIsNotNone(report.results["fail_node"].error)

    def test_run_failure_policy_skip_downstream(self) -> None:
        """WHEN node fails under SKIP_DOWNSTREAM, transitive dependents MUST be skipped while independent nodes succeed."""
        with enter_phase(system, registry=self.registry) as scope:
            def failing_action() -> None:
                raise RuntimeError("branch failed")

            dag = scope.get_singleton(DAG)
            dag.add_node("fail_a", action=failing_action)
            dag.add_node("child_b", action=lambda: None, dependencies=["fail_a"])
            dag.add_node("child_c", action=lambda: None, dependencies=["child_b"])
            dag.add_node("ok_d", action=lambda: "success")

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertIn("fail_a", report.failed_nodes)
            self.assertIn("child_b", report.skipped_nodes)
            self.assertIn("child_c", report.skipped_nodes)
            self.assertIn("ok_d", report.succeeded_nodes)

    def test_run_failure_policy_continue_on_error(self) -> None:
        """WHEN node fails under CONTINUE_ON_ERROR, independent branches MUST continue execution."""
        with enter_phase(system, registry=self.registry) as scope:
            def failing_action() -> None:
                raise RuntimeError("isolated failure")

            dag = scope.get_singleton(DAG)
            dag.add_node("fail_branch", action=failing_action)
            dag.add_node("independent_branch", action=lambda: "ok")

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIn("fail_branch", report.failed_nodes)
            self.assertIn("independent_branch", report.succeeded_nodes)

    def test_dag_timeout_handling_when_execution_exceeds_timeout_seconds(self) -> None:
        """WHEN overall execution duration exceeds timeout_seconds, runner MUST handle timeout by raising DAGTimeoutError."""
        with enter_phase(system, registry=self.registry) as scope:
            def prolonged_action() -> None:
                time.sleep(0.05)

            dag = scope.get_singleton(DAG)
            dag.add_node("prolonged_task", action=prolonged_action)

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_cancel_marks_unstarted_nodes_cancelled(self) -> None:
        """DAGRunner.cancel invocation MUST mark unstarted nodes CANCELLED in scheduler."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            scheduler = scope.get_singleton(WaveScheduler)

            def cancelling_action() -> None:
                runner.cancel()

            dag.add_node("canceller_task", action=cancelling_action)
            dag.add_node("pending_task_1", action=lambda: 1, dependencies=["canceller_task"])
            dag.add_node("pending_task_2", action=lambda: 2)

            with self.assertRaises(DAGCancelledError):
                runner.run()

            # Verify unstarted nodes are marked CANCELLED
            self.assertEqual(scheduler.get_state("pending_task_1"), NodeState.CANCELLED)
            # Direct cancel() invocation also cancels unstarted nodes
            runner.cancel()
            self.assertEqual(scheduler.get_state("pending_task_2"), NodeState.CANCELLED)

    def test_direct_cancel_prior_to_execution_marks_ready_and_pending_nodes_cancelled(self) -> None:
        """Direct invocation of DAGRunner.cancel on a graph containing initial READY and PENDING nodes prior to execution MUST transition unstarted nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("ready_root", action=lambda: "root")
            dag.add_node("pending_child", action=lambda: "child", dependencies=["ready_root"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("ready_root"), NodeState.READY)
            self.assertEqual(scheduler.get_state("pending_child"), NodeState.PENDING)

            runner = scope.get_singleton(DAGRunner)
            # Direct invocation prior to execution
            runner.cancel()

            self.assertEqual(scheduler.get_state("ready_root"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("pending_child"), NodeState.CANCELLED)
            states = scheduler.get_all_states()
            self.assertEqual(states["ready_root"], NodeState.CANCELLED)
            self.assertEqual(states["pending_child"], NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_run_failure_policy_continue_on_error_with_dependents_and_independent_branches(self) -> None:
        """DAG execution under FailurePolicy.CONTINUE_ON_ERROR where a failing node has direct and transitive downstream dependents alongside independent runnable branches MUST assert final node states."""
        with enter_phase(system, registry=self.registry) as scope:
            def failing_action() -> None:
                raise RuntimeError("failing root action")

            dag = scope.get_singleton(DAG)
            # Failing node with direct and transitive downstream dependents
            dag.add_node("fail_root", action=failing_action)
            dag.add_node("child_direct", action=lambda: "child", dependencies=["fail_root"])
            dag.add_node("grandchild_transitive", action=lambda: "grandchild", dependencies=["child_direct"])

            # Independent runnable branches
            dag.add_node("indep_root", action=lambda: "indep_root_val")
            dag.add_node("indep_child", action=lambda: "indep_child_val", dependencies=["indep_root"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(report.total_nodes, 5)

            # Assert final node states
            self.assertIn("fail_root", report.failed_nodes)
            self.assertEqual(report.results["fail_root"].state, NodeState.FAILED)

            self.assertIn("indep_root", report.succeeded_nodes)
            self.assertIn("indep_child", report.succeeded_nodes)
            self.assertEqual(report.results["indep_root"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["indep_child"].state, NodeState.SUCCEEDED)

            # Direct and transitive dependents cannot succeed or execute
            self.assertNotIn("child_direct", report.succeeded_nodes)
            self.assertNotIn("grandchild_transitive", report.succeeded_nodes)
            self.assertNotIn("child_direct", report.failed_nodes)
            self.assertNotIn("grandchild_transitive", report.failed_nodes)

            # Verify downstream dependents reached terminal skipped state
            self.assertIn("child_direct", report.skipped_nodes)
            self.assertIn("grandchild_transitive", report.skipped_nodes)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("child_direct"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("grandchild_transitive"), NodeState.SKIPPED)

    def test_run_serial_execution_max_concurrency_one(self) -> None:
        """DAG execution configured with max_concurrency of 1 MUST execute all nodes serially, complete execution, and accurately report outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_a", action=lambda: "a_val")
            dag.add_node("task_b", action=lambda: "b_val")
            dag.add_node("task_c", action=lambda: "c_val", dependencies=["task_a", "task_b"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=1)

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"task_a", "task_b", "task_c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["task_a"].value, "a_val")
            self.assertEqual(report.results["task_b"].value, "b_val")
            self.assertEqual(report.results["task_c"].value, "c_val")
            self.assertEqual(report.results["task_a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["task_b"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["task_c"].state, NodeState.SUCCEEDED)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertTrue(len(report.critical_path) > 0)

    def test_run_serial_max_concurrency_one_failure_after_retries(self) -> None:
        """DAG execution configured with max_concurrency of 1 where a node action fails after retries MUST capture errors and apply failure policy under single-worker concurrency."""
        with enter_phase(system, registry=self.registry) as scope:
            attempts = 0

            def failing_action() -> None:
                nonlocal attempts
                attempts += 1
                raise RuntimeError(f"serial failure attempt {attempts}")

            dag = scope.get_singleton(DAG)
            dag.add_node("fail_serial", action=failing_action, retries=2)
            dag.add_node("child_serial", action=lambda: "child", dependencies=["fail_serial"])
            dag.add_node("indep_serial", action=lambda: "indep")

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=1, failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(report.total_nodes, 3)
            self.assertIn("fail_serial", report.failed_nodes)
            node_result = report.results["fail_serial"]
            self.assertEqual(node_result.state, NodeState.FAILED)
            self.assertEqual(node_result.retries_attempted, 2)
            self.assertIsNotNone(node_result.error)
            self.assertEqual(attempts, 3)

            # Failure policy SKIP_DOWNSTREAM applied under single-worker concurrency
            self.assertIn("child_serial", report.skipped_nodes)
            self.assertIn("indep_serial", report.succeeded_nodes)
            self.assertEqual(report.results["indep_serial"].state, NodeState.SUCCEEDED)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("fail_serial"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child_serial"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("indep_serial"), NodeState.SUCCEEDED)

    def test_run_serial_max_concurrency_one_failure_after_retries_fail_fast(self) -> None:
        """DAG execution configured with max_concurrency of 1 where a node action fails after retries MUST apply FAIL_FAST policy under single-worker concurrency."""
        with enter_phase(system, registry=self.registry) as scope:
            attempts = 0

            def failing_action() -> None:
                nonlocal attempts
                attempts += 1
                raise ValueError(f"fail fast error {attempts}")

            dag = scope.get_singleton(DAG)
            dag.add_node("fail_fast_serial", action=failing_action, retries=1)
            dag.add_node("dependent_serial", action=lambda: "dep", dependencies=["fail_fast_serial"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=1, failure_policy=FailurePolicy.FAIL_FAST)

            self.assertIn("fail_fast_serial", report.failed_nodes)
            node_result = report.results["fail_fast_serial"]
            self.assertEqual(node_result.state, NodeState.FAILED)
            self.assertEqual(node_result.retries_attempted, 1)
            self.assertIsNotNone(node_result.error)
            self.assertEqual(attempts, 2)

            self.assertIn("dependent_serial", report.cancelled_nodes)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("dependent_serial"), NodeState.CANCELLED)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T04:29:01Z
# LAST_CHANGED: 2026-10-23T04:25:34Z
# CHANGE: Add unit test cases asserting DAG execution configured with max_concurrency of 1 for serial execution completion and outcome reporting, and where node action fails after retries to verify error capture and failure policy application under single-worker concurrency
# COVERAGE_AUDIT: 2026-10-23T04:29:01Z
# QA_AUDIT: 2026-10-23T04:28:27Z
# --- END CLEANROOM METADATA ---
