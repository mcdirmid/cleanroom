"""Unit tests for dag_engine_impl against the low-level DAG engine contract."""

from __future__ import annotations

import time
import unittest
from typing import List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGTimeoutError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def _noop() -> None:
    """Zero-argument action used when only graph structure matters."""
    return None


class DAGTest(unittest.TestCase):
    """Verifies dag_engine.DAG contract behaviors on the concrete DAG implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition(self) -> None:
        """add_node registers the immutable definition with all scheduling metadata."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> str:
                return "value"

            dag.add_node("alpha", action, None, 3, 1.5, 2)
            self.assertTrue(dag.has_node("alpha"))
            self.assertEqual(dag.all_nodes(), {"alpha"})
            definition = dag.get_node("alpha")
            self.assertEqual(definition.node_id, "alpha")
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.timeout_seconds, 1.5)
            self.assertEqual(definition.retries, 2)
            self.assertIs(definition.action, action)

    def test_add_node_without_dependencies(self) -> None:
        """add_node with no dependencies leaves the node free of upstream and downstream edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 0, None, 0)
            self.assertEqual(dag.get_dependencies("root"), set())
            self.assertEqual(dag.get_dependents("root"), set())
            self.assertEqual(dag.find_roots(), {"root"})
            self.assertEqual(dag.find_leaves(), {"root"})

    def test_add_node_with_dependencies_adds_directed_edges(self) -> None:
        """add_node with dependencies adds directed edges from each dependency to the new node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 0, None, 0)
            dag.add_node("child", _noop, ["root"], 0, None, 0)
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"child"})
            self.assertEqual(dag.get_node("child").dependencies, frozenset({"root"}))

    def test_add_edge_establishes_directed_dependency(self) -> None:
        """add_edge connects the upstream prerequisite to the downstream dependent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", _noop, None, 0, None, 0)
            dag.add_node("down", _noop, None, 0, None, 0)
            dag.add_edge("up", "down")
            self.assertEqual(dag.get_dependencies("down"), {"up"})
            self.assertEqual(dag.get_dependents("up"), {"down"})

    def test_add_edge_missing_upstream_raises_node_not_found(self) -> None:
        """add_edge rejects an absent upstream identifier with NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("down", _noop, None, 0, None, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("ghost", "down")

    def test_add_edge_missing_downstream_raises_node_not_found(self) -> None:
        """add_edge rejects an absent downstream identifier with NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", _noop, None, 0, None, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("up", "ghost")

    def test_remove_node_purges_incident_edges(self) -> None:
        """remove_node deletes the node and purges every incident dependency edge."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["b"], 0, None, 0)
            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependencies("c"), set())
            self.assertEqual(dag.get_dependents("a"), set())

    def test_remove_node_missing_raises_node_not_found(self) -> None:
        """remove_node rejects an absent identifier with NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("ghost")

    def test_get_node_missing_raises_node_not_found(self) -> None:
        """get_node rejects an absent identifier with NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_node("ghost")

    def test_get_dependencies_missing_raises_node_not_found(self) -> None:
        """get_dependencies rejects an absent identifier with NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("ghost")

    def test_get_dependents_missing_raises_node_not_found(self) -> None:
        """get_dependents rejects an absent identifier with NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("ghost")

    def test_all_nodes_returns_snapshot_copy(self) -> None:
        """all_nodes returns an isolated snapshot that cannot mutate the graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            snapshot = dag.all_nodes()
            snapshot.add("intruder")
            self.assertFalse(dag.has_node("intruder"))
            self.assertEqual(dag.all_nodes(), {"a"})

    def test_validate_accepts_complete_acyclic_graph(self) -> None:
        """validate accepts a complete acyclic diamond graph without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["a"], 0, None, 0)
            dag.add_node("d", _noop, ["b", "c"], 0, None, 0)
            dag.validate()

    def test_validate_missing_dependency_raises_node_not_found(self) -> None:
        """validate reports a dangling dependency as NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, ["ghost"], 0, None, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """validate reports a dependency cycle along with the participating node sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as caught:
                dag.validate()
            cycle = caught.exception.cycle
            self.assertIsInstance(cycle, tuple)
            self.assertIn("a", cycle)
            self.assertIn("b", cycle)

    def test_topological_sort_respects_dependency_order(self) -> None:
        """topological_sort places every prerequisite before its dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["a"], 0, None, 0)
            dag.add_node("d", _noop, ["b", "c"], 0, None, 0)
            order = dag.topological_sort()
            self.assertEqual(len(order), 4)
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("a"), order.index("c"))
            self.assertLess(order.index("b"), order.index("d"))
            self.assertLess(order.index("c"), order.index("d"))

    def test_topological_sort_breaks_ties_by_priority_then_name(self) -> None:
        """topological_sort breaks concurrent ties by priority descending then name ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("zeta", _noop, None, 1, None, 0)
            dag.add_node("alpha", _noop, None, 5, None, 0)
            dag.add_node("mu", _noop, None, 1, None, 0)
            self.assertEqual(dag.topological_sort(), ["alpha", "mu", "zeta"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """topological_sort rejects a cyclic graph with CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """find_roots and find_leaves report the degree-zero boundary nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["a"], 0, None, 0)
            dag.add_node("d", _noop, ["b", "c"], 0, None, 0)
            self.assertEqual(dag.find_roots(), {"a"})
            self.assertEqual(dag.find_leaves(), {"d"})

    def test_compute_critical_path_longest_weighted_path(self) -> None:
        """compute_critical_path selects the heaviest weighted path and its cumulative weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["a"], 0, None, 0)
            dag.add_node("d", _noop, ["b", "c"], 0, None, 0)
            path, total = dag.compute_critical_path(
                {"a": 1.0, "b": 5.0, "c": 1.0, "d": 2.0}
            )
            self.assertEqual(path, ["a", "b", "d"])
            self.assertAlmostEqual(total, 8.0)

    def test_compute_critical_path_defaults_to_unit_weights(self) -> None:
        """compute_critical_path defaults omitted duration weights to one unit per node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["b"], 0, None, 0)
            path, total = dag.compute_critical_path(None)
            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(total, 3.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """compute_critical_path yields an empty path and zero weight for an empty graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, total = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertAlmostEqual(total, 0.0)


class WaveSchedulerTest(unittest.TestCase):
    """Verifies dag_engine.WaveScheduler contract behaviors on the concrete implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_next_wave_orders_ready_roots_by_priority(self) -> None:
        """next_wave returns ready roots ordered by priority descending then name ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", _noop, None, 0, None, 0)
            dag.add_node("high", _noop, None, 3, None, 0)
            dag.add_node("mid", _noop, None, 1, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["high", "mid", "low"])

    def test_next_wave_empty_when_no_ready_nodes(self) -> None:
        """next_wave returns an empty list once no node remains ready."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """mark_running moves the node into the RUNNING state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """mark_succeeded promotes newly unblocked dependents to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("b"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_mark_succeeded_keeps_terminal_dependent_terminal(self) -> None:
        """A dependent already SKIPPED stays terminal when another upstream succeeds."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["a"], 0, None, 0)
            dag.add_node("d", _noop, ["b", "c"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("b"), NodeState.READY)
            self.assertEqual(scheduler.get_state("c"), NodeState.READY)
            scheduler.mark_failed("b", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
            scheduler.mark_running("c")
            scheduler.mark_succeeded("c")
            self.assertEqual(scheduler.get_state("c"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
            self.assertEqual(scheduler.next_wave(), [])

    def test_remove_node_drops_stale_scheduler_state(self) -> None:
        """Removing a graph node removes its scheduler-reported state as well."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(
                set(scheduler.get_all_states().keys()), {"a", "b"}
            )
            dag.remove_node("b")
            self.assertFalse(scheduler.is_finished())
            states = scheduler.get_all_states()
            self.assertEqual(set(states.keys()), {"a"})
            self.assertEqual(states["a"], NodeState.READY)

    def test_mark_failed_skip_downstream(self) -> None:
        """mark_failed with SKIP_DOWNSTREAM skips transitive dependents only."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["b"], 0, None, 0)
            dag.add_node("d", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["d"])

    def test_mark_failed_skip_downstream_convergent_diamond(self) -> None:
        """SKIP_DOWNSTREAM skips every transitive dependent reachable on multiple paths."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, ["a"], 0, None, 0)
            dag.add_node("d", _noop, ["b", "c"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_failed_fail_fast(self) -> None:
        """mark_failed with FAIL_FAST cancels the remaining non-terminal nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error(self) -> None:
        """mark_failed with CONTINUE_ON_ERROR keeps independent nodes executable."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            dag.add_node("c", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_is_finished_reports_terminal_states(self) -> None:
        """is_finished tracks whether every node has reached a terminal state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_empty_dag(self) -> None:
        """is_finished reports an empty graph as finished."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_get_all_states_initial_states(self) -> None:
        """get_all_states exposes READY roots and PENDING dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(
                scheduler.get_all_states(),
                {"a": NodeState.READY, "b": NodeState.PENDING},
            )


class DAGRunnerTest(unittest.TestCase):
    """Verifies dag_engine.DAGRunner contract behaviors on the concrete implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_success_report(self) -> None:
        """run executes a dependency chain and consolidates outcomes into a report."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action_a() -> str:
                return "alpha"

            def action_b() -> str:
                return "beta"

            dag.add_node("a", action_a, None, 0, None, 0)
            dag.add_node("b", action_b, ["a"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(None, FailurePolicy.FAIL_FAST, 2)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("a", "b"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b"))
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["a"].value, "alpha")
            self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["b"].value, "beta")
            self.assertGreaterEqual(report.results["a"].duration_seconds, 0.0)
            self.assertEqual(report.results["a"].retries_attempted, 0)

    def test_run_retries_failed_action(self) -> None:
        """run retries a failing action up to the configured retry count."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            attempts: List[int] = []

            def failing() -> str:
                attempts.append(1)
                raise ValueError("boom")

            dag.add_node("a", failing, None, 0, None, 2)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(None, FailurePolicy.FAIL_FAST, 1)
            self.assertEqual(report.failed_nodes, ("a",))
            result = report.results["a"]
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertEqual(result.retries_attempted, 2)
            self.assertEqual(len(attempts), 3)
            self.assertIsInstance(result.error, ValueError)

    def test_run_skip_downstream_policy(self) -> None:
        """run applies SKIP_DOWNSTREAM and reports the skipped dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def failing() -> str:
                raise ValueError("boom")

            dag.add_node("a", failing, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(None, FailurePolicy.SKIP_DOWNSTREAM, 2)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.skipped_nodes, ("b",))
            self.assertEqual(report.succeeded_nodes, ())

    def test_run_continue_on_error_policy(self) -> None:
        """run applies CONTINUE_ON_ERROR and still executes independent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def failing() -> str:
                raise ValueError("boom")

            def succeeding() -> str:
                return "ok"

            dag.add_node("bad", failing, None, 0, None, 0)
            dag.add_node("good", succeeding, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.succeeded_nodes, ("good",))

    def test_run_continue_on_error_terminates_with_retained_dependent(self) -> None:
        """A run whose only remaining node is a retained PENDING dependent still terminates."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def failing() -> str:
                raise ValueError("boom")

            dag.add_node("a", failing, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["a"].state, NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)

    def test_run_timeout_raises(self) -> None:
        """run raises DAGTimeoutError once the overall timeout is exceeded."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def slow() -> str:
                time.sleep(0.05)
                return "slow"

            dag.add_node("slow", slow, None, 0, None, 0)
            dag.add_node("after", _noop, ["slow"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(DAGTimeoutError):
                runner.run(0.01, FailurePolicy.FAIL_FAST, 1)

    def test_run_cancellation_during_execution_raises(self) -> None:
        """Cancellation signaled while nodes run aborts with DAGCancelledError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def cancelling() -> str:
                runner.cancel()
                return "cancelled"

            def slow() -> str:
                time.sleep(0.05)
                return "slow"

            dag.add_node("canceller", cancelling, None, 0, None, 0)
            dag.add_node("worker", slow, None, 0, None, 0)
            dag.add_node("tail", _noop, ["worker"], 0, None, 0)
            with self.assertRaises(DAGCancelledError):
                runner.run(None, FailurePolicy.FAIL_FAST, 2)

    def test_is_cancelled_reports_cancel_status(self) -> None:
        """is_cancelled reflects whether cancellation has been signaled."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            self.assertFalse(runner.is_cancelled())
            runner.cancel()
            self.assertTrue(runner.is_cancelled())

    def test_cancel_marks_unstarted_nodes_cancelled(self) -> None:
        """cancel marks all unstarted nodes as CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, ["a"], 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()
            self.assertEqual(scheduler.get_state("a"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:00:39Z
# LAST_CHANGED: 2026-11-08T17:00:06Z
# CHANGE: Added coverage for six feedback facets: mid-execution cancellation raising DAGCancelledError, convergent-diamond SKIP_DOWNSTREAM, promotion retaining already-SKIPPED dependents, empty-graph critical path, scheduler state pruning after node removal, and CONTINUE_ON_ERROR termination with a retained PENDING dependent.
# COVERAGE_AUDIT: 2026-11-08T17:00:39Z
# QA_AUDIT: 2026-11-08T17:00:25Z
# --- END AUTOFAB METADATA ---
