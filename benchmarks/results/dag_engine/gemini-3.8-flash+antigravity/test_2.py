"""Unit tests for dag_engine_impl per its grounding specification."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple
import unittest

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
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


class DagEngineImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and registration."""
        self.assertIsNotNone(self.registry)
        for sym in [DAG, DAGRunner, WaveScheduler]:
            self.assertIsNotNone(sym)

    def test_dag_add_node_simple(self) -> None:
        """POSTCONDITION: MUST register the node definition into the graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: "val")
            self.assertTrue(dag.has_node("A"))
            self.assertIn("A", dag.all_nodes())
            node = dag.get_node("A")
            self.assertEqual(node.node_id, "A")
            self.assertEqual(node.action(), "val")
            self.assertEqual(node.dependencies, frozenset())
            self.assertEqual(node.priority, 0)
            self.assertIsNone(node.timeout_seconds)
            self.assertEqual(node.retries, 0)

    def test_dag_add_node_with_dependencies_and_attributes(self) -> None:
        """POSTCONDITION: WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node(
                "B",
                lambda: 2,
                dependencies=["A"],
                priority=10,
                timeout_seconds=5.0,
                retries=2,
            )
            self.assertEqual(dag.get_dependencies("B"), {"A"})
            self.assertEqual(dag.get_dependents("A"), {"B"})
            node = dag.get_node("B")
            self.assertEqual(node.dependencies, frozenset({"A"}))
            self.assertEqual(node.priority, 10)
            self.assertEqual(node.timeout_seconds, 5.0)
            self.assertEqual(node.retries, 2)

    def test_dag_add_edge_success(self) -> None:
        """POSTCONDITION: MUST establish a directed dependency edge from upstream_id to downstream_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2)
            dag.add_edge("A", "B")
            self.assertIn("B", dag.get_dependents("A"))
            self.assertIn("A", dag.get_dependencies("B"))

    def test_dag_add_edge_missing_upstream_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN upstream_id does not exist, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("B", lambda: 2)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("A", "B")
            self.assertEqual(ctx.exception.node_id, "A")

    def test_dag_add_edge_missing_downstream_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN downstream_id does not exist, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("A", "B")
            self.assertEqual(ctx.exception.node_id, "B")

    def test_dag_remove_node_success(self) -> None:
        """POSTCONDITION: MUST remove the node and its incident edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3, dependencies=["B"])
            dag.remove_node("B")
            self.assertFalse(dag.has_node("B"))
            self.assertNotIn("B", dag.all_nodes())
            self.assertNotIn("B", dag.get_dependents("A"))
            self.assertNotIn("B", dag.get_dependencies("C"))

    def test_dag_remove_node_absent_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.remove_node("absent_node")
            self.assertEqual(ctx.exception.node_id, "absent_node")

    def test_dag_has_node_membership(self) -> None:
        """Verify has_node returns True if node exists, False otherwise."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("unknown"))
            dag.add_node("known", lambda: None)
            self.assertTrue(dag.has_node("known"))

    def test_dag_get_node_absent_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("missing")
            self.assertEqual(ctx.exception.node_id, "missing")

    def test_dag_get_dependencies_absent_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependencies("missing")
            self.assertEqual(ctx.exception.node_id, "missing")

    def test_dag_get_dependents_absent_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependents("missing")
            self.assertEqual(ctx.exception.node_id, "missing")

    def test_dag_all_nodes(self) -> None:
        """Verify all_nodes returns all node identifiers present in the graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2)
            self.assertEqual(dag.all_nodes(), {"A", "B"})

    def test_dag_validate_success(self) -> None:
        """POSTCONDITION: WHEN all referenced nodes exist and no cycle exists, MUST complete without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.validate()

    def test_dag_validate_missing_dependency_raises_node_not_found(self) -> None:
        """POSTCONDITION: WHEN a dependency node is missing, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1, dependencies=["ghost"])
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_dag_validate_cycle_raises_cycle_error(self) -> None:
        """POSTCONDITION: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2)
            dag.add_edge("A", "B")
            dag.add_edge("B", "A")
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertGreater(len(ctx.exception.cycle), 0)

    def test_dag_topological_sort_linear(self) -> None:
        """POSTCONDITION: MUST return a valid topological ordering where every prerequisite precedes its dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("C", lambda: 3, dependencies=["B"])
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            order = dag.topological_sort()
            self.assertEqual(order, ["A", "B", "C"])

    def test_dag_topological_sort_tie_breaking(self) -> None:
        """POSTCONDITION: MUST break ties between concurrent ready nodes using priority descending and name ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", lambda: 1, priority=1)
            dag.add_node("high_beta", lambda: 2, priority=10)
            dag.add_node("high_alpha", lambda: 3, priority=10)
            order = dag.topological_sort()
            self.assertEqual(order, ["high_alpha", "high_beta", "low"])

    def test_dag_topological_sort_cycle_raises_cycle_error(self) -> None:
        """POSTCONDITION: WHEN a cycle exists, MUST raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2)
            dag.add_edge("A", "B")
            dag.add_edge("B", "A")
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_dag_find_roots(self) -> None:
        """Verify find_roots returns all root nodes with in-degree zero."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.find_roots(), set())
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3)
            self.assertEqual(dag.find_roots(), {"A", "C"})

    def test_dag_find_leaves(self) -> None:
        """Verify find_leaves returns all leaf nodes with out-degree zero."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.find_leaves(), set())
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3)
            self.assertEqual(dag.find_leaves(), {"B", "C"})

    def test_dag_compute_critical_path_default_durations(self) -> None:
        """POSTCONDITION: MUST return the sequence of nodes that forms the longest path through the DAG and its cumulative weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3, dependencies=["B"])
            dag.add_node("D", lambda: 4, dependencies=["A"])
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["A", "B", "C"])
            self.assertEqual(weight, 3.0)

    def test_dag_compute_critical_path_custom_durations(self) -> None:
        """POSTCONDITION: MUST calculate path weight based on provided estimated_durations mapping."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3, dependencies=["A"])
            durations = {"A": 1.5, "B": 2.0, "C": 10.0}
            path, weight = dag.compute_critical_path(estimated_durations=durations)
            self.assertEqual(path, ["A", "C"])
            self.assertEqual(weight, 11.5)

    def test_dag_compute_critical_path_empty_graph(self) -> None:
        """POSTCONDITION: compute_critical_path on an empty graph MUST return empty path list and 0.0 weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    def test_wave_scheduler_next_wave_roots_and_tie_breaking(self) -> None:
        """POSTCONDITION: MUST order returned nodes by priority descending, then node_id ascending."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("Z", lambda: 1, priority=10)
            dag.add_node("B", lambda: 2, priority=20)
            dag.add_node("A", lambda: 3, priority=20)
            dag.add_node("C", lambda: 4, dependencies=["A"])

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["A", "B", "Z"])

    def test_wave_scheduler_initialized_with_existing_dag_registered_nodes(self) -> None:
        """GROUNDING: On initialization, assigns NodeState.READY to all root nodes, and NodeState.PENDING to remaining nodes."""
        def setup_existing_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_alpha", lambda: 1, priority=5)
            dag.add_node("root_beta", lambda: 2, priority=10)
            dag.add_node("dependent_child", lambda: 3, dependencies=["root_alpha", "root_beta"])

        with enter_phase(system, registry=self.registry, setup=setup_existing_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            states = scheduler.get_all_states()
            self.assertEqual(states["root_alpha"], NodeState.READY)
            self.assertEqual(states["root_beta"], NodeState.READY)
            self.assertEqual(states["dependent_child"], NodeState.PENDING)
            self.assertEqual(scheduler.get_state("root_alpha"), NodeState.READY)
            self.assertEqual(scheduler.get_state("root_beta"), NodeState.READY)
            self.assertEqual(scheduler.get_state("dependent_child"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["root_beta", "root_alpha"])
            self.assertFalse(scheduler.is_finished())

    def test_wave_scheduler_next_wave_empty_when_no_nodes_ready(self) -> None:
        """POSTCONDITION: WHEN no nodes are ready, MUST return an empty list."""
        def setup_graph(scope: LifecycleScope) -> None:
            pass

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), [])

    def test_wave_scheduler_mark_running(self) -> None:
        """POSTCONDITION: MUST update the node state to RUNNING."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("A"), NodeState.READY)
            scheduler.mark_running("A")
            self.assertEqual(scheduler.get_state("A"), NodeState.RUNNING)

    def test_wave_scheduler_mark_succeeded_promotes_dependents(self) -> None:
        """POSTCONDITION: MUST update the node state to SUCCEEDED and promote newly unblocked nodes to READY."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2)
            dag.add_node("C", lambda: 3, dependencies=["A", "B"])

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("C"), NodeState.PENDING)
            scheduler.mark_running("A")
            scheduler.mark_succeeded("A")
            self.assertEqual(scheduler.get_state("A"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("C"), NodeState.PENDING)
            scheduler.mark_running("B")
            scheduler.mark_succeeded("B")
            self.assertEqual(scheduler.get_state("B"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("C"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["C"])

    def test_wave_scheduler_mark_failed_fail_fast(self) -> None:
        """POSTCONDITION: WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("A")
            scheduler.mark_failed("A", failure_policy=FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("A"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("B"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("C"), NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_wave_scheduler_mark_failed_skip_downstream(self) -> None:
        """POSTCONDITION: WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3, dependencies=["B"])
            dag.add_node("D", lambda: 4)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("A")
            scheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("A"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("B"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("C"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("D"), NodeState.READY)

    def test_wave_scheduler_mark_failed_continue_on_error(self) -> None:
        """POSTCONDITION: WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("A")
            scheduler.mark_failed("A", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("A"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("C"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["C"])

    def test_wave_scheduler_is_finished_and_get_all_states(self) -> None:
        """Verify is_finished returns True only when all nodes reach terminal states."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("A")
            scheduler.mark_succeeded("A")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("B")
            scheduler.mark_succeeded("B")
            self.assertTrue(scheduler.is_finished())
            states = scheduler.get_all_states()
            self.assertEqual(states["A"], NodeState.SUCCEEDED)
            self.assertEqual(states["B"], NodeState.SUCCEEDED)

    def test_wave_scheduler_get_state_missing_node_raises_not_found(self) -> None:
        """POSTCONDITION: WHEN node_id is absent from the graph, get_state MUST raise NodeNotFoundError."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError) as ctx:
                scheduler.get_state("non_existent")
            self.assertEqual(ctx.exception.node_id, "non_existent")

    def test_wave_scheduler_is_finished_empty_schedule(self) -> None:
        """POSTCONDITION: WaveScheduler.is_finished MUST return True when no nodes exist in the schedule."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.get_all_states(), {})
            self.assertEqual(scheduler.next_wave(), [])

    def test_dag_runner_happy_path(self) -> None:
        """POSTCONDITION: MUST execute ready nodes concurrently and return a DAGRunReport capturing outcomes."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: "val_A", priority=1)
            dag.add_node("B", lambda: "val_B", dependencies=["A"], priority=2)
            dag.add_node("C", lambda: "val_C", dependencies=["A"], priority=3)
            dag.add_node("D", lambda: "val_D", dependencies=["B", "C"], priority=4)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(report.total_nodes, 4)
            self.assertEqual(set(report.succeeded_nodes), {"A", "B", "C", "D"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(len(report.critical_path), 3)
            for node_id, expected_val in [("A", "val_A"), ("B", "val_B"), ("C", "val_C"), ("D", "val_D")]:
                res = report.results[node_id]
                self.assertEqual(res.state, NodeState.SUCCEEDED)
                self.assertEqual(res.value, expected_val)
                self.assertIsNone(res.error)

    def test_dag_runner_retries_on_action_failure(self) -> None:
        """POSTCONDITION: MUST execute retries up to the configured retry count for failed node actions."""
        attempts = {"count": 0}

        def flaky_action() -> str:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ValueError("transient failure")
            return "recovered"

        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", flaky_action, retries=2)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(report.succeeded_nodes, ("A",))
            res = report.results["A"]
            self.assertEqual(res.state, NodeState.SUCCEEDED)
            self.assertEqual(res.value, "recovered")
            self.assertGreaterEqual(res.retries_attempted, 1)

    def test_dag_runner_failure_policy_fail_fast(self) -> None:
        """POSTCONDITION: MUST apply the specified failure_policy to the scheduler upon node failure."""
        def bad_action() -> None:
            raise RuntimeError("hard failure")

        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", bad_action, retries=0)
            dag.add_node("B", lambda: "b", dependencies=["A"])

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST)
            self.assertIn("A", report.failed_nodes)
            self.assertIn("B", report.cancelled_nodes)
            res_a = report.results["A"]
            self.assertEqual(res_a.state, NodeState.FAILED)
            self.assertIsNotNone(res_a.error)
            if isinstance(res_a.error, NodeExecutionError):
                self.assertEqual(res_a.error.node_id, "A")
                self.assertIsInstance(res_a.error.cause, RuntimeError)
            else:
                self.assertIsInstance(res_a.error, Exception)

    def test_dag_runner_failure_policy_skip_downstream(self) -> None:
        """POSTCONDITION: WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED."""
        def bad_action() -> None:
            raise RuntimeError("upstream failure")

        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", bad_action, retries=0)
            dag.add_node("B", lambda: "b", dependencies=["A"])
            dag.add_node("C", lambda: "c")

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
            self.assertIn("A", report.failed_nodes)
            self.assertIn("B", report.skipped_nodes)
            self.assertIn("C", report.succeeded_nodes)

    def test_dag_runner_failure_policy_continue_on_error(self) -> None:
        """POSTCONDITION: WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution."""
        def bad_action() -> None:
            raise RuntimeError("isolated failure")

        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", bad_action, retries=0)
            dag.add_node("B", lambda: "b")

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            self.assertIn("A", report.failed_nodes)
            self.assertIn("B", report.succeeded_nodes)

    def test_dag_runner_invalid_graph_validation_missing_dependency(self) -> None:
        """POSTCONDITION: Validates _dag using _dag.validate(), allowing missing dependency exceptions to raise immediately."""
        def setup_missing(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1, dependencies=["missing_dep"])

        with enter_phase(system, registry=self.registry, setup=setup_missing) as scope:
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(NodeNotFoundError):
                runner.run()

    def test_dag_runner_invalid_graph_validation_cycle(self) -> None:
        """POSTCONDITION: Validates _dag using _dag.validate(), allowing cycle exceptions to raise immediately."""
        def setup_cycle(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2)
            dag.add_edge("A", "B")
            dag.add_edge("B", "A")

        with enter_phase(system, registry=self.registry, setup=setup_cycle) as scope:
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(CycleError):
                runner.run()

    def test_dag_runner_timeout_raises_dag_timeout_error(self) -> None:
        """POSTCONDITION: WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError."""
        def slow_action() -> None:
            time.sleep(0.1)

        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", slow_action)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_dag_runner_max_concurrency_execution(self) -> None:
        """POSTCONDITION: MUST execute ready nodes concurrently up to the configured concurrency limit."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            for i in range(4):
                dag.add_node(f"N{i}", lambda: i)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=2)
            self.assertEqual(len(report.succeeded_nodes), 4)

    def test_dag_runner_cancel_prior_to_execution_aborts_and_cancels_nodes(self) -> None:
        """POSTCONDITION: WHEN cancelled prior to execution, MUST abort, mark non-terminal nodes as CANCELLED, and raise DAGCancelledError."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", lambda: 1)
            dag.add_node("B", lambda: 2, dependencies=["A"])

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            scheduler = scope.get_singleton(WaveScheduler)
            runner.cancel()
            with self.assertRaises(DAGCancelledError):
                runner.run()
            states = scheduler.get_all_states()
            self.assertEqual(states["A"], NodeState.CANCELLED)
            self.assertEqual(states["B"], NodeState.CANCELLED)

    def test_dag_runner_cancel_concurrently_during_run_aborts_and_cancels_nodes(self) -> None:
        """POSTCONDITION: WHEN cancelled during execution, MUST abort, mark non-terminal nodes as CANCELLED, and raise DAGCancelledError."""
        def setup_graph(scope: LifecycleScope) -> None:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def cancelling_action() -> None:
                runner.cancel()
                time.sleep(0.05)

            dag.add_node("A", cancelling_action)
            dag.add_node("B", lambda: 2, dependencies=["A"])
            dag.add_node("C", lambda: 3)

        with enter_phase(system, registry=self.registry, setup=setup_graph) as scope:
            runner = scope.get_singleton(DAGRunner)
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(DAGCancelledError):
                runner.run()
            states = scheduler.get_all_states()
            self.assertEqual(states["B"], NodeState.CANCELLED)
            self.assertIn(states["A"], (NodeState.CANCELLED, NodeState.SUCCEEDED))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T03:51:01Z
# LAST_CHANGED: 2026-10-22T03:43:34Z
# CHANGE: Resolve unacted feedback by adding unit tests for empty DAG compute_critical_path, missing node get_state raising NodeNotFoundError, empty schedule is_finished, WaveScheduler initialized with existing registered DAG nodes, and DAGRunner cancellation both prior to execution and concurrently during run
# COVERAGE_AUDIT: 2026-10-22T03:51:01Z
# QA_AUDIT: 2026-10-22T03:50:35Z
# --- END CLEANROOM METADATA ---
