"""Unit tests for dag_engine_impl per its grounding specification."""

from __future__ import annotations

import threading
import time
import unittest

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
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


def _noop() -> None:
    """Zero-argument node action used when a node has no observable computation."""
    return None


def _returns(value: str) -> str:
    """Zero-argument node action factory returning a fixed string value."""
    return value


class DagEngineImplTest(unittest.TestCase):
    """Contract tests for DAG, WaveScheduler, and DAGRunner singletons."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition_and_dependencies(self) -> None:
        """POSTCONDITIONS: add_node.register_definition and add_node.directed_dependencies."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 2, 5.0, 1)
            dag.add_node("child", _noop, {"root"}, 0, None, 0)

            self.assertTrue(dag.has_node("root"))
            self.assertTrue(dag.has_node("child"))
            definition = dag.get_node("child")
            self.assertEqual(definition.node_id, "child")
            self.assertEqual(set(definition.dependencies), {"root"})
            self.assertEqual(definition.priority, 0)
            self.assertIsNone(definition.timeout_seconds)
            self.assertEqual(definition.retries, 0)
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependencies("root"), set())
            self.assertEqual(dag.get_dependents("root"), {"child"})
            self.assertEqual(dag.get_dependents("child"), set())
            self.assertEqual(dag.all_nodes(), {"root", "child"})

    def test_add_edge_establishes_directed_edge(self) -> None:
        """POSTCONDITION: add_edge.directed_edge."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop, None, 0, None, 0)
            dag.add_node("downstream", _noop, None, 0, None, 0)

            dag.add_edge("upstream", "downstream")

            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})
            self.assertEqual(dag.find_roots(), {"upstream"})
            self.assertEqual(dag.find_leaves(), {"downstream"})

    def test_add_edge_unknown_upstream_raises(self) -> None:
        """PRECONDITION: add_edge.nodes_must_exist for a missing upstream."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("downstream", _noop, None, 0, None, 0)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.add_edge("ghost", "downstream")

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_add_edge_unknown_downstream_raises(self) -> None:
        """PRECONDITION: add_edge.nodes_must_exist for a missing downstream."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop, None, 0, None, 0)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.add_edge("upstream", "ghost")

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_remove_node_purges_incident_edges(self) -> None:
        """POSTCONDITION: remove_node.purge_incident_edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            dag.add_node("c", _noop, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "c")

            dag.remove_node("b")

            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())

    def test_remove_node_unknown_raises(self) -> None:
        """PRECONDITION: remove_node.node_must_exist."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.remove_node("ghost")

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_has_node_reports_absence(self) -> None:
        """Happy-path successor of has_node for an unregistered identifier."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("known", _noop, None, 0, None, 0)

            self.assertTrue(dag.has_node("known"))
            self.assertFalse(dag.has_node("unknown"))

    def test_get_node_unknown_raises(self) -> None:
        """PRECONDITION: get_node.node_must_exist."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.get_node("ghost")

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_get_dependencies_unknown_raises(self) -> None:
        """PRECONDITION: get_dependencies.node_must_exist."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.get_dependencies("ghost")

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_get_dependents_unknown_raises(self) -> None:
        """PRECONDITION: get_dependents.node_must_exist."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.get_dependents("ghost")

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_validate_accepts_acyclic_graph(self) -> None:
        """POSTCONDITION: validate.complete_valid."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)

            self.assertIsNone(dag.validate())

    def test_validate_reports_missing_dependency(self) -> None:
        """PRECONDITION: validate.dependencies_exist."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, {"ghost"}, 0, None, 0)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.validate()

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_validate_reports_cycle(self) -> None:
        """PRECONDITION: validate.acyclic_graph."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            with self.assertRaises(CycleError) as raised:
                dag.validate()

            self.assertEqual(set(raised.exception.cycle), {"a", "b"})

    def test_topological_sort_orders_dependencies_first(self) -> None:
        """POSTCONDITION: topological_sort.dependency_order."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("c", _noop, {"b"}, 0, None, 0)

            order = dag.topological_sort()

            self.assertEqual(sorted(order), ["a", "b", "c"])
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("b"), order.index("c"))

    def test_topological_sort_tie_breaks_by_priority_then_name(self) -> None:
        """POSTCONDITION: topological_sort.tie_breaking (priority descending, name ascending)."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", _noop, None, 0, None, 0)
            dag.add_node("high", _noop, None, 5, None, 0)
            dag.add_node("high_two", _noop, None, 5, None, 0)

            self.assertEqual(dag.topological_sort(), ["high", "high_two", "low"])

    def test_topological_sort_reports_cycle(self) -> None:
        """PRECONDITION: topological_sort.acyclic_graph."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            with self.assertRaises(CycleError) as raised:
                dag.topological_sort()

            self.assertEqual(set(raised.exception.cycle), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        """Happy-path verification of root (in-degree zero) and leaf (out-degree zero) discovery."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("c", _noop, {"a"}, 0, None, 0)

            self.assertEqual(dag.find_roots(), {"a"})
            self.assertEqual(dag.find_leaves(), {"b", "c"})

    def test_compute_critical_path_uses_estimated_durations(self) -> None:
        """POSTCONDITIONS: critical_path.longest_path and critical_path.cumulative_weight."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("c", _noop, {"b"}, 0, None, 0)

            path, weight = dag.compute_critical_path({"a": 1.0, "b": 3.0, "c": 2.0})

            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(weight, 6.0)

    def test_compute_critical_path_defaults_to_unit_weights(self) -> None:
        """POSTCONDITION: critical_path.cumulative_weight defaults each node weight to 1.0."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)

            path, weight = dag.compute_critical_path(None)

            self.assertEqual(path, ["a", "b"])
            self.assertAlmostEqual(weight, 2.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """POSTCONDITION: critical_path.longest_path yields no path for an empty graph."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            path, weight = dag.compute_critical_path(None)

            self.assertEqual(path, [])
            self.assertAlmostEqual(weight, 0.0)

    def test_next_wave_returns_ready_roots_in_priority_order(self) -> None:
        """POSTCONDITIONS: next_wave.ready_nodes and next_wave.priority_order."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_low", _noop, None, 0, None, 0)
            dag.add_node("root_high", _noop, None, 5, None, 0)
            dag.add_node("child", _noop, {"root_low"}, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.next_wave(), ["root_high", "root_low"])
            self.assertEqual(scheduler.get_state("root_low"), NodeState.READY)
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)
            self.assertEqual(
                dict(scheduler.get_all_states()),
                {
                    "root_low": NodeState.READY,
                    "root_high": NodeState.READY,
                    "child": NodeState.PENDING,
                },
            )

    def test_next_wave_empty_when_no_ready_nodes(self) -> None:
        """POSTCONDITION: next_wave.empty_when_no_ready."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.next_wave(), ["root"])
            scheduler.mark_running("root")

            self.assertEqual(scheduler.next_wave(), [])

    def test_next_wave_ignores_removed_nodes(self) -> None:
        """Scheduling state tracks nodes currently registered in the backing DAG."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.next_wave(), ["a", "b"])

            dag.remove_node("b")
            wave = scheduler.next_wave()

            self.assertEqual(wave, ["a"])
            self.assertNotIn("b", scheduler.get_all_states())

    def test_mark_running_updates_state(self) -> None:
        """POSTCONDITION: mark_running.state_transition."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("root")

            self.assertEqual(scheduler.get_state("root"), NodeState.RUNNING)
            self.assertEqual(scheduler.get_all_states()["root"], NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """POSTCONDITIONS: mark_succeeded.state_transition and mark_succeeded.promote_dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("b"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_mark_succeeded_requires_all_upstreams_succeeded(self) -> None:
        """POSTCONDITION: mark_succeeded.promote_dependents waits for every upstream to succeed."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            dag.add_node("c", _noop, {"a", "b"}, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("c"), NodeState.PENDING)

            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("c"), NodeState.READY)

    def test_mark_succeeded_does_not_promote_skipped_dependents(self) -> None:
        """POSTCONDITION: mark_succeeded.promote_dependents leaves non-PENDING dependents untouched."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("blocker", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a", "blocker"}, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("blocker")
            scheduler.mark_failed("blocker", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)

            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)

    def test_mark_failed_skip_downstream(self) -> None:
        """POSTCONDITION: mark_failed.skip_downstream transitively skips all dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("c", _noop, {"b"}, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)

    def test_mark_failed_skip_downstream_handles_diamond_dependents(self) -> None:
        """POSTCONDITION: mark_failed.skip_downstream terminates on diamond-shaped dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("c", _noop, {"a"}, 0, None, 0)
            dag.add_node("d", _noop, {"b", "c"}, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_fail_fast_cancels_remaining(self) -> None:
        """POSTCONDITION: mark_failed.fail_fast cancels all remaining non-terminal nodes."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("independent", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("independent"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error_keeps_independent_nodes(self) -> None:
        """POSTCONDITION: mark_failed.continue_on_error leaves unblocked nodes eligible."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, {"a"}, 0, None, 0)
            dag.add_node("independent", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)
            self.assertEqual(scheduler.get_state("independent"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["independent"])

    def test_is_finished_true_for_empty_dag(self) -> None:
        """POSTCONDITION: is_finished.empty_dag."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertFalse(dag.all_nodes())
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_tracks_terminal_states(self) -> None:
        """POSTCONDITIONS: is_finished.non_terminal_remaining and is_finished.all_terminal."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")

            self.assertTrue(scheduler.is_finished())

    def test_run_returns_consolidated_report(self) -> None:
        """POSTCONDITION: run.consolidated_report captures states, values, and critical path."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: _returns("a-value"), None, 0, None, 0)
            dag.add_node("b", lambda: _returns("b-value"), {"a"}, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)

            self.assertEqual(report.total_nodes, 2)
            self.assertCountEqual(report.succeeded_nodes, ["a", "b"])
            self.assertCountEqual(report.failed_nodes, [])
            self.assertEqual(set(report.results), {"a", "b"})
            self.assertEqual(report.results["a"].value, "a-value")
            self.assertEqual(report.results["b"].value, "b-value")
            self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(set(report.critical_path), {"a", "b"})

    def test_run_executes_ready_nodes_concurrently(self) -> None:
        """POSTCONDITION: run.concurrent_execution dispatches independent ready nodes together."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            barrier = threading.Barrier(2, timeout=2.0)

            def wait_for_peer() -> str:
                barrier.wait()
                return "ok"

            dag.add_node("left", wait_for_peer, None, 0, None, 0)
            dag.add_node("right", wait_for_peer, None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)

            self.assertCountEqual(report.succeeded_nodes, ["left", "right"])
            self.assertCountEqual(report.failed_nodes, [])

    def test_run_retries_failed_action(self) -> None:
        """POSTCONDITION: run.retry_failures retries a failing action until it succeeds."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            attempts: list[int] = []

            def flaky() -> str:
                attempts.append(len(attempts))
                if len(attempts) <= 2:
                    raise ValueError("transient failure")
                return "recovered"

            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", flaky, None, 0, None, 3)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)

            self.assertCountEqual(report.failed_nodes, [])
            self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertEqual(len(attempts), 3)
            self.assertGreaterEqual(report.results["flaky"].retries_attempted, 1)

    def test_run_records_failed_node_under_continue_on_error(self) -> None:
        """POSTCONDITION: run.apply_failure_policy records failure and keeps independent nodes running."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def failing() -> str:
                raise RuntimeError("boom")

            dag = scope.get_singleton(DAG)
            dag.add_node("bad", failing, None, 0, None, 0)
            dag.add_node("good", lambda: _returns("ok"), None, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)

            self.assertCountEqual(report.failed_nodes, ["bad"])
            self.assertCountEqual(report.succeeded_nodes, ["good"])
            self.assertEqual(report.results["bad"].state, NodeState.FAILED)
            self.assertIsNotNone(report.results["bad"].error)

    def test_run_propagates_cycle_error_from_validation(self) -> None:
        """Graph validation failures surface from run instead of executing nodes."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, None, 0, None, 0)
            dag.add_node("b", _noop, None, 0, None, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(CycleError):
                runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)

    def test_run_propagates_missing_dependency_from_validation(self) -> None:
        """Graph validation failures surface from run when a dependency is missing."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, {"ghost"}, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(NodeNotFoundError) as raised:
                runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)

            self.assertEqual(raised.exception.node_id, "ghost")

    def test_run_reports_cancelled_nodes_under_fail_fast(self) -> None:
        """POSTCONDITION: run.apply_failure_policy surfaces cancelled dependents in the report."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def failing() -> str:
                raise RuntimeError("boom")

            dag = scope.get_singleton(DAG)
            dag.add_node("bad", failing, None, 0, None, 0)
            dag.add_node("child_a", _noop, {"bad"}, 0, None, 0)
            dag.add_node("child_b", _noop, {"bad"}, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.FAIL_FAST, 2)

            self.assertEqual(report.total_nodes, 3)
            self.assertCountEqual(report.failed_nodes, ["bad"])
            self.assertCountEqual(report.cancelled_nodes, ["child_a", "child_b"])
            self.assertCountEqual(report.succeeded_nodes, [])
            self.assertCountEqual(report.skipped_nodes, [])

    def test_run_raises_timeout_error(self) -> None:
        """PRECONDITION: run.timeout_limit raises DAGTimeoutError once execution exceeds the limit."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def slow() -> str:
                time.sleep(0.05)
                return "slow"

            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow, None, 0, None, 0)
            dag.add_node("after_slow", lambda: _returns("fast"), {"slow"}, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(DAGTimeoutError):
                runner.run(0.01, FailurePolicy.CONTINUE_ON_ERROR, 1)

    def test_run_records_node_timeout_as_failed_outcome(self) -> None:
        """Boundary: a node exceeding its own timeout_seconds is reported as a failed outcome."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def slow() -> str:
                time.sleep(0.05)
                return "late"

            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow, None, 0, 0.01, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)

            self.assertEqual(report.total_nodes, 1)
            self.assertNotIn("slow", report.succeeded_nodes)
            self.assertIn(report.results["slow"].state, (NodeState.FAILED, NodeState.CANCELLED))
            self.assertIsNotNone(report.results["slow"].error)

    def test_run_records_timeout_when_slow_node_action_raises(self) -> None:
        """Boundary: a node action raising after its timeout is reported as a timeout outcome."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            def slow_failure() -> str:
                time.sleep(0.05)
                raise RuntimeError("late failure")

            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow_failure, None, 0, 0.01, 0)
            runner = scope.get_singleton(DAGRunner)

            report = runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)

            self.assertEqual(report.total_nodes, 1)
            self.assertNotIn("slow", report.succeeded_nodes)
            self.assertIn(report.results["slow"].state, (NodeState.FAILED, NodeState.CANCELLED))
            self.assertIsNotNone(report.results["slow"].error)

    def test_cancel_sets_cancellation_status(self) -> None:
        """POSTCONDITIONS: is_cancelled.active_status, is_cancelled.cancelled_status, cancel.abort_execution."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("pending", _noop, None, 0, None, 0)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            self.assertFalse(runner.is_cancelled())

            runner.cancel()

            self.assertTrue(runner.is_cancelled())
            self.assertEqual(scheduler.get_state("pending"), NodeState.CANCELLED)

    def test_run_raises_cancelled_error_when_cancelled_in_flight(self) -> None:
        """PRECONDITION: run.abort_on_cancel raises when cancel is signalled mid-flight."""
        runner_holder: list[DAGRunner] = []

        def cancel_in_flight() -> str:
            runner_holder[0].cancel()
            return "cancelled"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("canceller", cancel_in_flight, None, 0, None, 0)
            dag.add_node("downstream", _noop, {"canceller"}, 0, None, 0)
            runner = scope.get_singleton(DAGRunner)
            runner_holder.append(runner)

            with self.assertRaises(DAGCancelledError):
                runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T16:58:54Z
# LAST_CHANGED: 2026-11-08T16:58:23Z
# CHANGE: Addressed the two remaining audit findings: (1) the removed-node scenario now first observes both nodes in a ready wave (next_wave returns a and b) and only then removes b, asserting the subsequent wave reports only the still-registered node and drops b from scheduling state; (2) added a slow node action that raises after exceeding its own timeout_seconds, verifying the reported outcome is non-succeeded (failed or cancelled) with an error attached, covering the timeout-preceding-action-error boundary. Cleared the resolved in-file feedback entries.
# COVERAGE_AUDIT: 2026-11-08T16:58:54Z
# QA_AUDIT: 2026-11-08T16:58:41Z
# --- END AUTOFAB METADATA ---
