"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

from typing import Any, Callable, List
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def _returning(value: Any) -> Callable[[], Any]:
    """Builds a zero-argument action returning a fixed value."""
    def action() -> Any:
        return value
    return action


def _recording(events: List[str], label: str) -> Callable[[], str]:
    """Builds a zero-argument action that records its execution label."""
    def action() -> str:
        events.append(label)
        return label
    return action


def _failing(message: str) -> Callable[[], Any]:
    """Builds a zero-argument action that always raises a runtime error."""
    def action() -> Any:
        raise RuntimeError(message)
    return action


def _flaky(attempts: List[int], failures: int, value: Any) -> Callable[[], Any]:
    """Builds a zero-argument action failing a fixed number of leading attempts."""
    def action() -> Any:
        attempts.append(1)
        if len(attempts) <= failures:
            raise RuntimeError("transient failure")
        return value
    return action


class DagEngineLiteImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)


    # --- DAG graph structure -------------------------------------------------

    def test_add_node_registers_definition_and_edges(self) -> None:
        """POSTCONDITIONS: nodes are registered and dependency edges are directed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _returning("value"))
            dag.add_node("child", _returning("value"), dependencies=["root"], priority=5, retries=2)
            self.assertEqual(dag.all_nodes(), {"root", "child"})
            self.assertTrue(dag.has_node("child"))
            self.assertFalse(dag.has_node("ghost"))
            definition = dag.get_node("child")
            self.assertEqual(definition.node_id, "child")
            self.assertEqual(definition.dependencies, frozenset({"root"}))
            self.assertEqual(definition.priority, 5)
            self.assertEqual(definition.retries, 2)
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"child"})
            # INVARIANTS: neighbor lookups expose defensive copies of internal state.
            dependencies = dag.get_dependencies("child")
            dependencies.add("intruder")
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            nodes = dag.all_nodes()
            nodes.add("intruder")
            self.assertEqual(dag.all_nodes(), {"root", "child"})


    def test_add_node_defers_missing_dependency_validation(self) -> None:
        """POSTCONDITIONS: dependency existence checks are deferred to validate()."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("child", _returning(1), dependencies=["absent"])
            self.assertEqual(dag.get_dependencies("child"), {"absent"})
            with self.assertRaises(NodeNotFoundError) as context:
                dag.validate()
            self.assertEqual(context.exception.node_id, "absent")
            self.assertEqual(str(context.exception), context.exception.message)


    def test_add_edge_links_nodes_and_rejects_unknown(self) -> None:
        """POSTCONDITIONS: edges link existing nodes and raise NodeNotFoundError otherwise."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _returning(1))
            dag.add_node("child", _returning(2))
            dag.add_edge("root", "child")
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"child"})
            with self.assertRaises(NodeNotFoundError) as unknown_upstream:
                dag.add_edge("ghost", "root")
            self.assertEqual(unknown_upstream.exception.node_id, "ghost")
            with self.assertRaises(NodeNotFoundError) as unknown_downstream:
                dag.add_edge("root", "ghost")
            self.assertEqual(unknown_downstream.exception.node_id, "ghost")


    def test_remove_node_purges_incident_edges(self) -> None:
        """POSTCONDITIONS: removal detaches incident edges and raises for absent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _returning(1))
            dag.add_node("mid", _returning(2), dependencies=["root"])
            dag.add_node("leaf", _returning(3), dependencies=["mid"])
            dag.remove_node("mid")
            self.assertFalse(dag.has_node("mid"))
            self.assertEqual(dag.all_nodes(), {"root", "leaf"})
            self.assertEqual(dag.get_dependents("root"), set())
            self.assertEqual(dag.get_dependencies("leaf"), set())
            with self.assertRaises(NodeNotFoundError) as context:
                dag.remove_node("ghost")
            self.assertEqual(context.exception.node_id, "ghost")


    def test_lookups_raise_for_unknown_node(self) -> None:
        """POSTCONDITIONS: absent node lookups raise NodeNotFoundError with the identifier."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as missing_node:
                dag.get_node("ghost")
            self.assertEqual(missing_node.exception.node_id, "ghost")
            with self.assertRaises(NodeNotFoundError) as missing_dependencies:
                dag.get_dependencies("ghost")
            self.assertEqual(missing_dependencies.exception.node_id, "ghost")
            with self.assertRaises(NodeNotFoundError) as missing_dependents:
                dag.get_dependents("ghost")
            self.assertEqual(missing_dependents.exception.node_id, "ghost")


    def test_validate_accepts_acyclic_graph(self) -> None:
        """POSTCONDITIONS: a complete acyclic graph validates without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2), dependencies=["a"])
            dag.add_node("c", _returning(3), dependencies=["a"])
            dag.add_node("d", _returning(4), dependencies=["b", "c"])
            self.assertIsNone(dag.validate())


    def test_validate_detects_cycle(self) -> None:
        """POSTCONDITIONS: WHEN a cycle exists, validate() raises CycleError with the sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2))
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as context:
                dag.validate()
            self.assertEqual(set(context.exception.cycle), {"a", "b"})


    def test_find_roots_and_leaves(self) -> None:
        """POSTCONDITIONS: roots have no dependencies and leaves have no dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _returning(1))
            dag.add_node("mid", _returning(2), dependencies=["root"])
            dag.add_node("leaf", _returning(3), dependencies=["mid"])
            dag.add_node("isolated", _returning(4))
            self.assertEqual(dag.find_roots(), {"root", "isolated"})
            self.assertEqual(dag.find_leaves(), {"leaf", "isolated"})


    def test_topological_sort_orders_by_priority_then_identifier(self) -> None:
        """POSTCONDITIONS: ties break by priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c", _returning(1), priority=3)
            dag.add_node("a", _returning(2), priority=1)
            dag.add_node("b", _returning(3), priority=1)
            dag.add_node("d", _returning(4), dependencies=["a"])
            self.assertEqual(dag.topological_sort(), ["c", "a", "b", "d"])


    def test_topological_sort_detects_cycle(self) -> None:
        """POSTCONDITIONS: WHEN a cycle exists, topological_sort() raises CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2))
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as context:
                dag.topological_sort()
            self.assertEqual(set(context.exception.cycle), {"a", "b"})


    def test_compute_critical_path_weighted(self) -> None:
        """POSTCONDITIONS: the longest weighted path and its cumulative weight are returned."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _returning(1))
            dag.add_node("mid", _returning(2), dependencies=["root"])
            dag.add_node("leaf", _returning(3), dependencies=["mid"])
            dag.add_node("side", _returning(4), dependencies=["root"])
            path, weight = dag.compute_critical_path(
                {"root": 2.0, "mid": 3.0, "leaf": 1.0, "side": 0.5}
            )
            self.assertEqual(path, ["root", "mid", "leaf"])
            self.assertAlmostEqual(weight, 6.0)


    def test_compute_critical_path_defaults_to_unit_durations(self) -> None:
        """POSTCONDITIONS: unspecified duration weights default to 1.0 per node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2), dependencies=["a"])
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["a", "b"])
            self.assertAlmostEqual(weight, 2.0)


    def test_compute_critical_path_empty_graph(self) -> None:
        """POSTCONDITIONS: an empty graph yields an empty path with zero weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.compute_critical_path(), ([], 0.0))


    def test_compute_critical_path_single_node(self) -> None:
        """POSTCONDITIONS: a lone node forms a path weighted by its own duration."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("only", _returning(1))
            path, weight = dag.compute_critical_path({"only": 2.5})
            self.assertEqual(path, ["only"])
            self.assertAlmostEqual(weight, 2.5)


    # --- Wave scheduler ------------------------------------------------------

    def test_scheduler_initial_states_and_next_wave(self) -> None:
        """POSTCONDITIONS: roots start READY, non-roots PENDING, waves order by priority."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("low", _returning(1), priority=1)
            dag.add_node("high", _returning(2), priority=5)
            dag.add_node("child", _returning(3), dependencies=["high"])
            states = scheduler.get_all_states()
            self.assertEqual(states["high"], NodeState.READY)
            self.assertEqual(states["low"], NodeState.READY)
            self.assertEqual(states["child"], NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["high", "low"])
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)
            # Newly registered nodes are discovered on demand.
            dag.add_node("late", _returning(4))
            self.assertEqual(scheduler.get_state("late"), NodeState.READY)


    def test_mark_succeeded_unlocks_transitive_dependents(self) -> None:
        """POSTCONDITIONS: succeeded nodes promote unblocked dependents to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _returning("a"))
            dag.add_node("b", _returning("b"), dependencies=["a"])
            dag.add_node("c", _returning("c"), dependencies=["a"])
            dag.add_node("d", _returning("d"), dependencies=["b", "c"])
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.next_wave(), ["b", "c"])
            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("d"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["c"])
            scheduler.mark_succeeded("c")
            self.assertEqual(scheduler.get_state("d"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["d"])
            # Dependents that already left PENDING remain untouched.
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("b"), NodeState.SUCCEEDED)


    def test_mark_failed_skip_downstream(self) -> None:
        """POSTCONDITIONS: SKIP_DOWNSTREAM marks all transitive dependents SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2), dependencies=["a"])
            dag.add_node("c", _returning(3), dependencies=["a"])
            dag.add_node("d", _returning(4), dependencies=["b", "c"])
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
            # Dependents already in a terminal state are left unchanged.
            scheduler.mark_failed("b", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("b"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)


    def test_mark_failed_continue_on_error_keeps_independent_nodes(self) -> None:
        """POSTCONDITIONS: CONTINUE_ON_ERROR leaves independent nodes eligible and skips blocked ones."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("bad", _returning(1))
            dag.add_node("dependent", _returning(2), dependencies=["bad"])
            dag.add_node("independent", _returning(3))
            scheduler.mark_failed("bad", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("bad"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent"), NodeState.READY)
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), ["independent"])


    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """POSTCONDITIONS: FAIL_FAST transitions all remaining non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("bad", _returning(1))
            dag.add_node("dependent", _returning(2), dependencies=["bad"])
            dag.add_node("independent", _returning(3))
            scheduler.get_all_states()
            scheduler.mark_failed("bad")
            self.assertEqual(scheduler.get_state("bad"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("independent"), NodeState.CANCELLED)
            # Re-applying the policy leaves terminal nodes untouched.
            scheduler.mark_failed("bad", FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("independent"), NodeState.CANCELLED)


    def test_scheduler_is_finished_reports_terminal_states(self) -> None:
        """POSTCONDITIONS: finished is True for empty DAGs and fully terminal DAGs."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            dag.add_node("a", _returning(1))
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("a")
            self.assertTrue(scheduler.is_finished())


    def test_scheduler_state_tracking_follows_node_removal(self) -> None:
        """POSTCONDITIONS: scheduling state purges identifiers removed from the graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2), dependencies=["a"])
            self.assertEqual(scheduler.get_all_states(), {"a": NodeState.READY, "b": NodeState.PENDING})
            dag.remove_node("b")
            self.assertEqual(scheduler.get_all_states(), {"a": NodeState.READY})


    # --- DAG runner ----------------------------------------------------------

    def test_runner_executes_dag_and_reports_outcomes(self) -> None:
        """POSTCONDITIONS: ready waves execute sequentially and the report records every outcome."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            events: List[str] = []
            dag.add_node("a", _recording(events, "a"))
            dag.add_node("b", _recording(events, "b"), dependencies=["a"])
            dag.add_node("c", _recording(events, "c"), dependencies=["b"])
            report = runner.run()
            self.assertEqual(events, ["a", "b", "c"])
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(report.succeeded_nodes, ("a", "b", "c"))
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b", "c"))
            self.assertEqual(set(report.results.keys()), {"a", "b", "c"})
            self.assertEqual(report.results["a"].value, "a")
            self.assertGreaterEqual(report.results["a"].duration_seconds, 0.0)


    def test_runner_retries_failed_action_then_succeeds(self) -> None:
        """POSTCONDITIONS: retries execute up to the configured count before success."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            attempts: List[int] = []
            dag.add_node("flaky", _flaky(attempts, 1, "recovered"), retries=1)
            report = runner.run()
            result = report.results["flaky"]
            self.assertEqual(result.state, NodeState.SUCCEEDED)
            self.assertEqual(result.value, "recovered")
            self.assertEqual(result.retries_attempted, 1)
            self.assertEqual(report.succeeded_nodes, ("flaky",))


    def test_runner_records_failure_after_exhausting_retries(self) -> None:
        """POSTCONDITIONS: exhausted retries record a FAILED result carrying the caught exception."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad", _failing("boom"), retries=2)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            result = report.results["bad"]
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertIsInstance(result.error, RuntimeError)
            self.assertEqual(result.retries_attempted, 2)
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.succeeded_nodes, ())


    def test_runner_fail_fast_cancels_unexecuted_nodes(self) -> None:
        """POSTCONDITIONS: FAIL_FAST halts the run and cancels remaining nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            events: List[str] = []
            dag.add_node("bad", _failing("boom"), priority=10)
            dag.add_node("downstream", _recording(events, "downstream"), dependencies=["bad"])
            dag.add_node("other", _recording(events, "other"), priority=5)
            report = runner.run()
            self.assertEqual(events, [])
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.cancelled_nodes, ("downstream", "other"))
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertIsInstance(report.results["bad"].error, RuntimeError)
            self.assertEqual(report.results["other"].state, NodeState.CANCELLED)
            self.assertEqual(report.results["downstream"].state, NodeState.CANCELLED)


    def test_runner_continue_on_error_skips_blocked_dependents(self) -> None:
        """POSTCONDITIONS: CONTINUE_ON_ERROR skips blocked dependents and runs independent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            events: List[str] = []
            dag.add_node("bad", _failing("boom"), priority=10)
            dag.add_node("dependent", _recording(events, "dependent"), dependencies=["bad"])
            dag.add_node("good", _recording(events, "good"), priority=5)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(events, ["good"])
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.skipped_nodes, ("dependent",))
            self.assertEqual(report.succeeded_nodes, ("good",))
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["dependent"].state, NodeState.SKIPPED)


    def test_runner_skip_downstream_policy(self) -> None:
        """POSTCONDITIONS: SKIP_DOWNSTREAM skips the failed node's transitive dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            events: List[str] = []
            dag.add_node("bad", _failing("boom"), priority=10)
            dag.add_node("dependent", _recording(events, "dependent"), dependencies=["bad"])
            dag.add_node("good", _recording(events, "good"), priority=5)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(events, ["good"])
            self.assertEqual(report.skipped_nodes, ("dependent",))
            self.assertEqual(report.succeeded_nodes, ("good",))
            self.assertEqual(report.failed_nodes, ("bad",))


    def test_runner_validates_cycle_before_execution(self) -> None:
        """POSTCONDITIONS: cyclic graphs raise CycleError before any wave executes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", _returning(1))
            dag.add_node("b", _returning(2))
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError):
                runner.run()


    def test_runner_validates_missing_dependencies_before_execution(self) -> None:
        """POSTCONDITIONS: missing dependency nodes raise NodeNotFoundError before execution."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("child", _returning(1), dependencies=["absent"])
            with self.assertRaises(NodeNotFoundError) as context:
                runner.run()
            self.assertEqual(context.exception.node_id, "absent")


    def test_runner_empty_graph_reports_no_nodes(self) -> None:
        """POSTCONDITIONS: an empty DAG run reports zero nodes and no outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(report.results, {})
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:40:45Z
# LAST_CHANGED: 2026-11-02T23:40:45Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: e062e4936e8a
# COVERAGE_AUDIT: 2026-11-02T23:40:45Z
# QA_AUDIT: 2026-11-02T23:40:45Z
# --- END AUTOFAB METADATA ---
