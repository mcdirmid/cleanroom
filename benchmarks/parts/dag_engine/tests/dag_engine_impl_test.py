"""Behavioral tests for the DAG execution and wave scheduling engine.

The suite is derived from ``low/dag_engine.pyi`` and
``low/dag_engine_impl.pyi``: every test asserts an explicit postcondition
contracted for ``DAG``, ``WaveScheduler``, or ``DAGRunner``.
"""

from __future__ import annotations

from contextlib import ExitStack
import time
from typing import Any, Callable, List, Optional
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmarks.parts.dag_engine.lib import dag_engine
from benchmarks.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def _returning(value: Any) -> Callable[[], Any]:
    """Builds a zero-argument node action that returns ``value``."""

    def action() -> Any:
        return value

    return action


class DAGEngineImplTest(unittest.TestCase):
    """Contract tests for the graph, scheduler, and runner implementations."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.dag = DAG()

    def _scheduler(self) -> WaveScheduler:
        return WaveScheduler(self.dag)

    def _runner(self) -> DAGRunner:
        return DAGRunner(self.dag, self._scheduler())

    # ---- DAG.add_node -------------------------------------------------

    def test_add_node_registers_definition_with_options(self) -> None:
        """POSTCONDITION: add_node registers the node and its dependency edges."""
        self.dag.add_node("base", _returning(1))
        self.dag.add_node(
            "task",
            _returning(2),
            dependencies=["base"],
            priority=3,
            timeout_seconds=1.5,
            retries=2,
        )

        self.assertTrue(self.dag.has_node("task"))
        definition = self.dag.get_node("task")
        self.assertEqual(definition.node_id, "task")
        self.assertEqual(definition.dependencies, frozenset({"base"}))
        self.assertEqual(definition.priority, 3)
        self.assertEqual(definition.timeout_seconds, 1.5)
        self.assertEqual(definition.retries, 2)
        self.assertEqual(self.dag.get_dependencies("task"), {"base"})
        self.assertEqual(self.dag.get_dependents("base"), {"task"})

    def test_add_node_uses_default_options(self) -> None:
        """POSTCONDITION: omitted optional arguments bind their documented defaults."""
        action = _returning("done")
        self.dag.add_node("solo", action)

        definition = self.dag.get_node("solo")
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.priority, 0)
        self.assertIsNone(definition.timeout_seconds)
        self.assertEqual(definition.retries, 0)
        self.assertIs(definition.action, action)

    # ---- DAG.add_edge -------------------------------------------------

    def test_add_edge_establishes_dependency(self) -> None:
        """POSTCONDITION: add_edge establishes a directed dependency edge."""
        self.dag.add_node("up", _returning(1))
        self.dag.add_node("down", _returning(2))
        self.dag.add_edge("up", "down")

        self.assertEqual(self.dag.get_dependencies("down"), {"up"})
        self.assertEqual(self.dag.get_dependents("up"), {"down"})

    def test_add_edge_unknown_upstream_raises(self) -> None:
        """POSTCONDITION: missing upstream identifier raises NodeNotFoundError."""
        self.dag.add_node("down", _returning(1))
        with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
            self.dag.add_edge("missing-up", "down")
        self.assertEqual(raised.exception.node_id, "missing-up")

    def test_add_edge_unknown_downstream_raises(self) -> None:
        """POSTCONDITION: missing downstream identifier raises NodeNotFoundError."""
        self.dag.add_node("up", _returning(1))
        with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
            self.dag.add_edge("up", "missing-down")
        self.assertEqual(raised.exception.node_id, "missing-down")

    # ---- DAG.remove_node ----------------------------------------------

    def test_remove_node_removes_incident_edges(self) -> None:
        """POSTCONDITION: remove_node deletes the node and all incident edges."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])

        self.dag.remove_node("b")

        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a", "c"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())

    def test_remove_unknown_node_raises(self) -> None:
        """POSTCONDITION: removing an absent node raises NodeNotFoundError."""
        with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
            self.dag.remove_node("ghost")
        self.assertEqual(raised.exception.node_id, "ghost")

    # ---- DAG queries --------------------------------------------------

    def test_has_node_reports_membership(self) -> None:
        """has_node reflects registration state for known and unknown identifiers."""
        self.dag.add_node("present", _returning(1))
        self.assertTrue(self.dag.has_node("present"))
        self.assertFalse(self.dag.has_node("absent"))

    def test_all_nodes_returns_registered_identifiers(self) -> None:
        """all_nodes returns the full set of registered node identifiers."""
        self.dag.add_node("x", _returning(1))
        self.dag.add_node("y", _returning(2))
        self.dag.add_node("z", _returning(3))
        self.assertEqual(self.dag.all_nodes(), {"x", "y", "z"})

    def test_get_node_unknown_raises(self) -> None:
        """POSTCONDITION: get_node on an absent identifier raises NodeNotFoundError."""
        with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
            self.dag.get_node("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_get_dependencies_unknown_raises(self) -> None:
        """POSTCONDITION: get_dependencies on an absent identifier raises NodeNotFoundError."""
        with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
            self.dag.get_dependencies("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_get_dependents_unknown_raises(self) -> None:
        """POSTCONDITION: get_dependents on an absent identifier raises NodeNotFoundError."""
        with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
            self.dag.get_dependents("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_find_roots_and_leaves(self) -> None:
        """POSTCONDITION: roots have no dependencies and leaves have no dependents."""
        self.dag.add_node("r1", _returning(1))
        self.dag.add_node("r2", _returning(2))
        self.dag.add_node("mid", _returning(3), dependencies=["r1", "r2"])
        self.dag.add_node("leaf", _returning(4), dependencies=["mid"])

        self.assertEqual(self.dag.find_roots(), {"r1", "r2"})
        self.assertEqual(self.dag.find_leaves(), {"leaf"})

    # ---- DAG.validate -------------------------------------------------

    def test_validate_accepts_valid_graph(self) -> None:
        """POSTCONDITION: a complete acyclic graph validates without error."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])
        self.assertIsNone(self.dag.validate())

    def test_validate_detects_cycle(self) -> None:
        """POSTCONDITION: an existing directed cycle raises CycleError with its sequence."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")

        with self.assertRaises(dag_engine.CycleError) as raised:
            self.dag.validate()
        self.assertEqual(set(raised.exception.cycle), {"a", "b"})

    # ---- DAG.topological_sort -----------------------------------------

    def test_topological_sort_respects_dependencies(self) -> None:
        """POSTCONDITION: every prerequisite precedes its dependents in the ordering."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])
        self.dag.add_node("d", _returning(4))

        order = self.dag.topological_sort()

        self.assertEqual(set(order), {"a", "b", "c", "d"})
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("c"))
        self.assertLess(order.index("d"), len(order))

    def test_topological_sort_orders_ready_by_priority(self) -> None:
        """POSTCONDITION: independent ready nodes break ties by priority descending."""
        self.dag.add_node("low", _returning(1), priority=0)
        self.dag.add_node("high", _returning(2), priority=10)
        self.assertEqual(self.dag.topological_sort(), ["high", "low"])

    def test_topological_sort_orders_ready_alphabetically(self) -> None:
        """POSTCONDITION: equal-priority ready nodes break ties by identifier ascending."""
        self.dag.add_node("b", _returning(1), priority=0)
        self.dag.add_node("a", _returning(2), priority=0)
        self.assertEqual(self.dag.topological_sort(), ["a", "b"])

    def test_topological_sort_cycle_raises(self) -> None:
        """POSTCONDITION: a cyclic graph raises CycleError from topological_sort."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")

        with self.assertRaises(dag_engine.CycleError):
            self.dag.topological_sort()

    # ---- DAG.compute_critical_path ------------------------------------

    def test_compute_critical_path_weighted(self) -> None:
        """POSTCONDITION: the weighted longest dependency path and weight are returned."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])

        path, weight = self.dag.compute_critical_path({"a": 1.0, "b": 5.0, "c": 2.0})

        self.assertEqual(set(path), {"a", "b", "c"})
        self.assertAlmostEqual(weight, 8.0)

    def test_compute_critical_path_default_weight(self) -> None:
        """POSTCONDITION: omitted durations default to one unit per node."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])

        path, weight = self.dag.compute_critical_path()

        self.assertEqual(set(path), {"a", "b", "c"})
        self.assertAlmostEqual(weight, 3.0)

    def test_compute_critical_path_longest_branch(self) -> None:
        """POSTCONDITION: the heaviest branch of a forked graph forms the path."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["a"])

        path, weight = self.dag.compute_critical_path(
            {"a": 1.0, "b": 4.0, "c": 1.0}
        )

        self.assertEqual(set(path), {"a", "b"})
        self.assertAlmostEqual(weight, 5.0)

    # ---- WaveScheduler ------------------------------------------------

    def test_scheduler_initial_states(self) -> None:
        """POSTCONDITION: roots initialize READY and dependent nodes initialize PENDING."""
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["root"])
        scheduler = self._scheduler()

        states = scheduler.get_all_states()
        self.assertEqual(states["root"], dag_engine.NodeState.READY)
        self.assertEqual(states["child"], dag_engine.NodeState.PENDING)

    def test_next_wave_orders_ready_roots(self) -> None:
        """POSTCONDITION: next_wave returns ready nodes by priority then identifier."""
        self.dag.add_node("r1", _returning(1), priority=0)
        self.dag.add_node("r2", _returning(2), priority=5)
        self.dag.add_node("r3", _returning(3), priority=5)
        self.dag.add_node("child", _returning(4), dependencies=["r1"])
        scheduler = self._scheduler()

        self.assertEqual(scheduler.next_wave(), ["r2", "r3", "r1"])

    def test_next_wave_returns_empty_when_none_ready(self) -> None:
        """POSTCONDITION: next_wave returns an empty list when nothing is ready."""
        self.dag.add_node("only", _returning(1))
        scheduler = self._scheduler()
        scheduler.mark_running("only")

        self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """POSTCONDITION: mark_running updates the node state to RUNNING."""
        self.dag.add_node("only", _returning(1))
        scheduler = self._scheduler()
        scheduler.mark_running("only")

        self.assertEqual(
            scheduler.get_state("only"), dag_engine.NodeState.RUNNING
        )

    def test_mark_succeeded_unlocks_dependents(self) -> None:
        """POSTCONDITION: mark_succeeded promotes fully unblocked dependents to READY."""
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["root"])
        scheduler = self._scheduler()

        scheduler.mark_succeeded("root")

        self.assertEqual(
            scheduler.get_state("root"), dag_engine.NodeState.SUCCEEDED
        )
        self.assertEqual(
            scheduler.get_state("child"), dag_engine.NodeState.READY
        )
        self.assertEqual(scheduler.next_wave(), ["child"])

    def test_mark_succeeded_waits_for_all_dependencies(self) -> None:
        """POSTCONDITION: a node stays PENDING until every dependency has SUCCEEDED."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_node("joined", _returning(3), dependencies=["a", "b"])
        scheduler = self._scheduler()

        scheduler.mark_succeeded("a")
        self.assertEqual(
            scheduler.get_state("joined"), dag_engine.NodeState.PENDING
        )

        scheduler.mark_succeeded("b")
        self.assertEqual(
            scheduler.get_state("joined"), dag_engine.NodeState.READY
        )

    def test_mark_failed_sets_failed_state(self) -> None:
        """POSTCONDITION: mark_failed updates the node state to FAILED."""
        self.dag.add_node("broken", _returning(1))
        scheduler = self._scheduler()
        scheduler.mark_failed("broken")

        self.assertEqual(
            scheduler.get_state("broken"), dag_engine.NodeState.FAILED
        )

    def test_mark_failed_skip_downstream_skips_dependents(self) -> None:
        """POSTCONDITION: mark_failed with SKIP_DOWNSTREAM transitions transitive dependents to SKIPPED."""
        self.dag.add_node("parent", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["parent"])
        scheduler = self._scheduler()
        scheduler.mark_failed(
            "parent", failure_policy=dag_engine.FailurePolicy.SKIP_DOWNSTREAM
        )

        self.assertEqual(
            scheduler.get_state("parent"), dag_engine.NodeState.FAILED
        )
        self.assertEqual(
            scheduler.get_state("child"), dag_engine.NodeState.SKIPPED
        )

    def test_mark_failed_continue_on_error_retains_independent(self) -> None:
        """POSTCONDITION: mark_failed with CONTINUE_ON_ERROR leaves independent ready nodes eligible."""
        self.dag.add_node("bad", _returning(1))
        self.dag.add_node("other", _returning(2))
        scheduler = self._scheduler()
        scheduler.mark_failed(
            "bad", failure_policy=dag_engine.FailurePolicy.CONTINUE_ON_ERROR
        )

        self.assertEqual(
            scheduler.get_state("bad"), dag_engine.NodeState.FAILED
        )
        self.assertEqual(
            scheduler.get_state("other"), dag_engine.NodeState.READY
        )

    def test_is_finished_when_all_terminal(self) -> None:
        """POSTCONDITION: is_finished is True only once every node is terminal."""
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        scheduler = self._scheduler()

        self.assertFalse(scheduler.is_finished())
        scheduler.mark_succeeded("a")
        self.assertFalse(scheduler.is_finished())
        scheduler.mark_succeeded("b")
        self.assertTrue(scheduler.is_finished())

    # ---- DAGRunner ----------------------------------------------------

    def test_run_executes_dependency_chain(self) -> None:
        """POSTCONDITION: run records the report for a successful chain."""
        executed: List[str] = []

        def first() -> int:
            executed.append("a")
            return 1

        def second() -> int:
            executed.append("b")
            return 2

        self.dag.add_node("a", first)
        self.dag.add_node("b", second, dependencies=["a"])
        runner = self._runner()

        report = runner.run()

        self.assertEqual(executed, ["a", "b"])
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(set(report.critical_path), {"a", "b"})
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(report.results["a"].state, dag_engine.NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].value, 1)
        self.assertGreaterEqual(report.results["b"].duration_seconds, 0.0)

    def test_run_retries_transient_failures(self) -> None:
        """POSTCONDITION: run retries a failing action up to the configured count."""
        attempts: List[int] = []

        def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient")
            return "ok"

        self.dag.add_node("flaky", flaky, retries=2)
        runner = self._runner()

        report = runner.run()

        self.assertEqual(len(attempts), 3)
        self.assertEqual(report.succeeded_nodes, ("flaky",))
        self.assertEqual(report.results["flaky"].value, "ok")
        self.assertEqual(report.results["flaky"].retries_attempted, 2)

    def test_run_records_failed_nodes(self) -> None:
        """POSTCONDITION: an exhausted failing action is recorded as FAILED."""
        failure = ValueError("boom")

        def failing() -> None:
            raise failure

        self.dag.add_node("bad", failing)
        runner = self._runner()

        report = runner.run()

        self.assertEqual(report.failed_nodes, ("bad",))
        result = report.results["bad"]
        self.assertEqual(result.state, dag_engine.NodeState.FAILED)
        self.assertIs(result.error, failure)

    def test_run_timeout_raises(self) -> None:
        """POSTCONDITION: exceeding the overall timeout raises DAGTimeoutError."""
        self.dag.add_node("slow", lambda: time.sleep(0.3))
        self.dag.add_node("after", _returning(2), dependencies=["slow"])
        runner = self._runner()

        with self.assertRaises(dag_engine.DAGTimeoutError):
            runner.run(timeout_seconds=0.05)

    def test_cancel_aborts_subsequent_execution(self) -> None:
        """POSTCONDITION: cancel sets cancellation status and aborts wave execution."""
        executed: List[str] = []

        def action() -> None:
            executed.append("ran")

        self.dag.add_node("ready", action)
        self.dag.add_node("pending", action, dependencies=["ready"])
        runner = self._runner()

        runner.cancel()
        report: Optional[dag_engine.DAGRunReport] = None
        cancelled = False
        try:
            report = runner.run()
        except dag_engine.DAGCancelledError:
            cancelled = True

        self.assertEqual(executed, [])
        if not cancelled:
            self.assertIsNotNone(report)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-21T20:59:21Z
# LAST_CHANGED: 2026-10-21T20:59:21Z
# CHANGE: Author dag_engine_impl test suite: DAG graph ops (add_node/add_edge/remove_node, unknown-node errors, validate cycles, deterministic topological sort with priority/name tie-breaks, roots/leaves, weighted and default critical paths), WaveScheduler lifecycle states and wave promotion/ordering, and DAGRunner success/retry/failure/timeout/cancel contracts; tests resolve tiered singletons via isolated LifecycleRegistry + enter_phase.
# --- END CLEANROOM METADATA ---
