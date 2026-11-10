"""Unit tests for dag_engine_impl per its grounding specification."""

from __future__ import annotations

import threading
import time
import unittest

from dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGRunReport,
    DAGTimeoutError,
    FailurePolicy,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class DagEngineImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    # --- DAG: add_node ---

    def test_add_node_registers_definition(self) -> None:
        """Verifies that adding a node registers its immutable definition."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            action = lambda: 7
            dag.add_node("alpha", action, None, 5, None, 0)

            self.assertTrue(dag.has_node("alpha"))
            definition = dag.get_node("alpha")
            self.assertEqual(definition.node_id, "alpha")
            self.assertIs(definition.action, action)
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 5)
            self.assertIsNone(definition.timeout_seconds)
            self.assertEqual(definition.retries, 0)

    def test_add_node_with_dependencies_creates_edges(self) -> None:
        """Verifies that declared dependencies become directed edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None, None, 0, None, 0)
            dag.add_node("child", lambda: None, ["root"], 0, None, 0)

            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"child"})

    # --- DAG: add_edge ---

    def test_add_edge_establishes_directed_edge(self) -> None:
        """Verifies that add_edge records a directed dependency edge."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", lambda: None, None, 0, None, 0)
            dag.add_node("downstream", lambda: None, None, 0, None, 0)
            dag.add_edge("upstream", "downstream")

            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_add_edge_with_missing_nodes_raises(self) -> None:
        """Verifies that an endpoint absent from the graph is rejected."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("only", lambda: None, None, 0, None, 0)

            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("only", "missing")
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("missing", "only")

    # --- DAG: remove_node ---

    def test_remove_node_purges_incident_edges(self) -> None:
        """Verifies that removing a node also removes its incident edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: None, None, 0, None, 0)
            dag.add_node("second", lambda: None, None, 0, None, 0)
            dag.add_edge("first", "second")
            dag.remove_node("first")

            self.assertFalse(dag.has_node("first"))
            self.assertEqual(dag.all_nodes(), {"second"})
            self.assertEqual(dag.get_dependencies("second"), set())
            self.assertEqual(dag.get_dependents("second"), set())

    def test_remove_node_purges_upstream_dependencies(self) -> None:
        """Verifies that removing a node also detaches its upstream neighbors."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", lambda: None, None, 0, None, 0)
            dag.add_node("downstream", lambda: None, None, 0, None, 0)
            dag.add_edge("upstream", "downstream")
            dag.remove_node("downstream")

            self.assertFalse(dag.has_node("downstream"))
            self.assertEqual(dag.all_nodes(), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), set())

    def test_remove_node_missing_raises(self) -> None:
        """Verifies that removing an absent node is rejected."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("absent")

    # --- DAG: lookups ---

    def test_get_node_missing_raises(self) -> None:
        """Verifies that looking up an absent node raises an error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_node("absent")

    def test_get_dependencies_missing_raises(self) -> None:
        """Verifies that querying dependencies of an absent node raises an error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("absent")

    def test_get_dependents_missing_raises(self) -> None:
        """Verifies that querying dependents of an absent node raises an error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("absent")

    def test_has_node_and_all_nodes(self) -> None:
        """Verifies membership checks and enumeration of registered node identifiers."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, None, 0, None, 0)

            self.assertTrue(dag.has_node("a"))
            self.assertFalse(dag.has_node("c"))
            self.assertEqual(dag.all_nodes(), {"a", "b"})

    # --- DAG: validate ---

    def test_validate_accepts_consistent_graph(self) -> None:
        """Verifies that a consistent acyclic graph validates without error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.validate()

    def test_validate_missing_dependency_raises(self) -> None:
        """Verifies that a dangling dependency reference fails validation."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", lambda: None, ["ghost"], 0, None, 0)

            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_validate_cycle_raises_with_cycle_members(self) -> None:
        """Verifies that a cycle is reported together with its member sequence."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, None, 0, None, 0)
            dag.add_node("c", lambda: None, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "c")
            dag.add_edge("c", "a")

            with self.assertRaises(CycleError) as context:
                dag.validate()
            self.assertEqual(set(context.exception.cycle), {"a", "b", "c"})

    # --- DAG: topological_sort ---

    def test_topological_sort_orders_dependencies(self) -> None:
        """Verifies that every prerequisite precedes its dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c", lambda: None, ["b"], 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            order = dag.topological_sort()

            self.assertEqual(set(order), {"a", "b", "c"})
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("b"), order.index("c"))

    def test_topological_sort_tie_breaks_by_priority_then_name(self) -> None:
        """Verifies deterministic tie-breaking by priority then identifier."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", lambda: None, None, 1, None, 0)
            dag.add_node("high", lambda: None, None, 9, None, 0)
            dag.add_node("mid", lambda: None, None, 1, None, 0)

            self.assertEqual(dag.topological_sort(), ["high", "low", "mid"])

    def test_topological_sort_cycle_raises(self) -> None:
        """Verifies that topological ordering rejects a cyclic graph."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            with self.assertRaises(CycleError):
                dag.topological_sort()

    # --- DAG: roots, leaves, critical path ---

    def test_find_roots_and_leaves(self) -> None:
        """Verifies that degree-zero nodes are classified as roots or leaves."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: None, ["b"], 0, None, 0)
            dag.add_node("d", lambda: None, None, 0, None, 0)

            self.assertEqual(dag.find_roots(), {"a", "d"})
            self.assertEqual(dag.find_leaves(), {"c", "d"})

    def test_compute_critical_path_default_weights(self) -> None:
        """Verifies the longest path under default unit node weights."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: None, ["b"], 0, None, 0)

            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(weight, 3.0)

    def test_compute_critical_path_uses_estimated_durations(self) -> None:
        """Verifies that estimated durations select the heaviest branch."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: None, ["a"], 0, None, 0)

            path, weight = dag.compute_critical_path({"a": 1.0, "b": 2.0, "c": 5.0})
            self.assertEqual(path, ["a", "c"])
            self.assertEqual(weight, 6.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """Verifies the empty-graph critical path boundary values."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    # --- WaveScheduler ---

    def test_next_wave_returns_ready_nodes_in_priority_order(self) -> None:
        """Verifies that ready roots are returned ordered by priority."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: None, None, 1, None, 0)
            dag.add_node("second", lambda: None, ["first"], 0, None, 0)
            dag.add_node("urgent", lambda: None, None, 5, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.next_wave(), ["urgent", "first"])

    def test_next_wave_empty_when_no_node_ready(self) -> None:
        """Verifies that an empty wave is returned when nothing is ready."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("only", lambda: None, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("only")

            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """Verifies that marking running updates the node state."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("job", lambda: None, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("job")

            self.assertEqual(scheduler.get_state("job"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """Verifies that a success promotes newly unblocked dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", lambda: None, None, 0, None, 0)
            dag.add_node("downstream", lambda: None, ["upstream"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("upstream")
            scheduler.mark_succeeded("upstream")

            self.assertEqual(scheduler.get_state("upstream"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("downstream"), NodeState.READY)

    def test_mark_succeeded_does_not_promote_non_pending_dependent(self) -> None:
        """Verifies that a dependent already in a non-pending state is left alone."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", lambda: None, None, 0, None, 0)
            dag.add_node("downstream", lambda: None, ["upstream"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("downstream", FailurePolicy.CONTINUE_ON_ERROR)
            scheduler.mark_running("upstream")
            scheduler.mark_succeeded("upstream")

            self.assertEqual(scheduler.get_state("upstream"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("downstream"), NodeState.FAILED)

    def test_mark_failed_skip_downstream(self) -> None:
        """Verifies that transitive dependents are skipped after a failure."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: None, ["b"], 0, None, 0)
            dag.add_node("independent", lambda: None, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertIn(
                scheduler.get_state("independent"),
                (NodeState.PENDING, NodeState.READY),
            )

    def test_mark_failed_skip_downstream_diamond_shared_dependent(self) -> None:
        """Verifies that a shared transitive dependent is skipped exactly once."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: None, ["a"], 0, None, 0)
            dag.add_node("d", lambda: None, ["b", "c"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)

    def test_mark_failed_fail_fast_cancels_remaining(self) -> None:
        """Verifies that a fail-fast policy cancels remaining non-terminal nodes."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("independent", lambda: None, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("independent"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error_keeps_independent_nodes(self) -> None:
        """Verifies independent nodes stay eligible after a continue-on-error failure."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("independent", lambda: None, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertIn(
                scheduler.get_state("independent"),
                (NodeState.PENDING, NodeState.READY),
            )

    def test_is_finished_empty_graph(self) -> None:
        """Verifies that an empty graph is reported as finished."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_ignores_removed_graph_node(self) -> None:
        """Verifies a stale recorded state for a removed node does not block finishing."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            dag.remove_node("a")

            self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_with_non_terminal_node(self) -> None:
        """Verifies that a non-terminal node keeps the run unfinished."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_when_all_terminal(self) -> None:
        """Verifies that a graph whose nodes are all terminal is finished."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")

            self.assertTrue(scheduler.is_finished())

    def test_get_all_states_covers_every_node(self) -> None:
        """Verifies that a state is reported for every graph node."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            states = scheduler.get_all_states()
            self.assertEqual(set(states.keys()), {"a", "b"})
            self.assertIsInstance(states["a"], NodeState)
            self.assertIsInstance(states["b"], NodeState)

    # --- DAGRunner ---

    def test_is_cancelled_initially_false(self) -> None:
        """Verifies that cancellation is not signalled before cancel()."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            runner = scope.get_singleton(DAGRunner)
            self.assertFalse(runner.is_cancelled())

    def test_cancel_sets_cancelled_status(self) -> None:
        """Verifies that cancel() records the cancellation status."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()

            self.assertTrue(runner.is_cancelled())

    def test_run_success_reports_every_node(self) -> None:
        """Verifies the consolidated report for a successful run."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: 1, None, 0, None, 0)
            dag.add_node("b", lambda: 2, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.FAIL_FAST, 2)
            self.assertIsInstance(report, DAGRunReport)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertIsInstance(report.results["a"], NodeResult)
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["a"].value, 1)
            self.assertEqual(report.results["b"].value, 2)
            self.assertIsNone(report.results["a"].error)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_reports_critical_path(self) -> None:
        """Verifies that the run report carries the critical path."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.FAIL_FAST, 1)
            self.assertEqual(report.critical_path, ("a", "b"))

    def test_run_retries_failed_action(self) -> None:
        """Verifies that a flaky action eventually succeeds through retries."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            attempts = {"count": 0}

            def flaky() -> str:
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise RuntimeError("transient")
                return "ok"

            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", flaky, None, 0, None, 2)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.FAIL_FAST, 1)
            self.assertEqual(attempts["count"], 3)
            self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "ok")
            self.assertEqual(report.results["flaky"].retries_attempted, 2)

    def test_run_failure_fail_fast_cancels_dependents(self) -> None:
        """Verifies that fail-fast cancels the remaining nodes after a failure."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def boom() -> None:
                raise RuntimeError("boom")

            dag = scope.get_singleton(DAG)
            dag.add_node("a", boom, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.FAIL_FAST, 1)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.cancelled_nodes, ("b",))
            self.assertEqual(report.results["a"].state, NodeState.FAILED)
            self.assertIsInstance(report.results["a"].error, RuntimeError)

    def test_run_failure_skip_downstream_skips_dependents(self) -> None:
        """Verifies that skip-downstream policy skips transitive dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def boom() -> None:
                raise RuntimeError("boom")

            dag = scope.get_singleton(DAG)
            dag.add_node("a", boom, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: None, ["b"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.SKIP_DOWNSTREAM, 1)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(set(report.skipped_nodes), {"b", "c"})

    def test_run_failure_continue_on_error_runs_independent_nodes(self) -> None:
        """Verifies that continue-on-error lets independent nodes complete."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def boom() -> None:
                raise RuntimeError("boom")

            dag = scope.get_singleton(DAG)
            dag.add_node("a", boom, None, 0, None, 0)
            dag.add_node("b", lambda: "done", None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.succeeded_nodes, ("b",))

    def test_run_failure_continue_on_error_skips_stranded_dependent(self) -> None:
        """Verifies stranded dependents are skipped while independent nodes finish."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def boom() -> None:
                raise RuntimeError("boom")

            dag = scope.get_singleton(DAG)
            dag.add_node("a", boom, None, 0, None, 0)
            dag.add_node("b", lambda: None, ["a"], 0, None, 0)
            dag.add_node("c", lambda: "done", None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(2.0, FailurePolicy.CONTINUE_ON_ERROR, 2)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertIn("b", report.skipped_nodes)
            self.assertIn("c", report.succeeded_nodes)

    def test_run_cancelled_raises_cancelled_error(self) -> None:
        """Verifies that a signalled cancellation aborts the run with an error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()

            with self.assertRaises(DAGCancelledError):
                runner.run(None, FailurePolicy.FAIL_FAST, 1)

    def test_run_cancelled_during_in_flight_wave(self) -> None:
        """Verifies that cancellation signalled during an in-flight wave aborts the run."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            release = threading.Event()
            runner_holder: list[DAGRunner] = []

            def cancelling_action() -> None:
                runner_holder[0].cancel()
                release.set()

            def in_flight_action() -> None:
                release.wait(timeout=0.5)

            dag = scope.get_singleton(DAG)
            dag.add_node("canceller", cancelling_action, None, 0, None, 0)
            dag.add_node("worker", in_flight_action, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            runner_holder.append(runner)

            with self.assertRaises(DAGCancelledError):
                runner.run(None, FailurePolicy.FAIL_FAST, 2)
            self.assertTrue(runner.is_cancelled())

    def test_run_exceeding_timeout_raises(self) -> None:
        """Verifies that exceeding the overall timeout raises a timeout error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def slow() -> None:
                time.sleep(0.05)

            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(DAGTimeoutError):
                runner.run(0.0, FailurePolicy.FAIL_FAST, 1)

    def test_run_executes_ready_nodes_concurrently(self) -> None:
        """Verifies that independent ready nodes execute in the same wave."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            barrier = threading.Barrier(2)

            def rendezvous() -> None:
                barrier.wait(timeout=1.0)

            dag = scope.get_singleton(DAG)
            dag.add_node("left", rendezvous, None, 0, None, 0)
            dag.add_node("right", rendezvous, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.FAIL_FAST, 2)
            self.assertEqual(set(report.succeeded_nodes), {"left", "right"})
            self.assertEqual(report.failed_nodes, ())

    def test_run_rejects_cyclic_graph(self) -> None:
        """Verifies that a cyclic graph is rejected before execution."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None, None, 0, None, 0)
            dag.add_node("b", lambda: None, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(CycleError):
                runner.run(None, FailurePolicy.FAIL_FAST, 1)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:36:16Z
# LAST_CHANGED: 2026-11-09T23:16:48Z
# CHANGE: Remove the unmandated blocked-dependent state assertion flagged by QA: the continue-on-error scheduler test now asserts only the contracted outcomes (failed node FAILED and independent node remains eligible), matching observed PENDING behavior for the transitively blocked dependent instead of asserting SKIPPED.
# COVERAGE_AUDIT: 2026-11-09T23:36:16Z
# QA_AUDIT: 2026-11-09T23:36:01Z
# --- END AUTOFAB METADATA ---
