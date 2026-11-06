"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, Callable, Optional

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)


class FlakyAction:
    """Action that fails a configured number of times before succeeding."""

    def __init__(self, failures: int, value: str = "recovered") -> None:
        self.failures = failures
        self.value = value
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("transient failure")
        return self.value


def _boom() -> int:
    raise RuntimeError("boom")


class DagEngineLiteImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.scope = enter_phase(system, registry=self.registry)
        self.scope.__enter__()
        self.dag = self.scope.get_singleton(DAG)
        self.scheduler = self.scope.get_singleton(WaveScheduler)
        self.runner = self.scope.get_singleton(DAGRunner)

    def tearDown(self) -> None:
        self.scope.__exit__(None, None, None)

    def _add(
        self,
        node_id: str,
        action: Optional[Callable[[], Any]] = None,
        dependencies: Optional[list[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        """Registers a node with a default echo action when none is supplied."""
        resolved_action: Callable[[], Any] = action if action is not None else (lambda: node_id)
        self.dag.add_node(node_id, resolved_action, dependencies, priority, retries)

    def test_add_node_registers_definition_and_edges(self) -> None:
        """Verify add_node registers definitions and dependency edges."""
        self._add("a")
        self._add("b", lambda: 2, ["a"], 3, 1)
        self.assertTrue(self.dag.has_node("a"))
        self.assertFalse(self.dag.has_node("missing"))
        definition = self.dag.get_node("b")
        self.assertEqual(definition.node_id, "b")
        self.assertEqual(definition.dependencies, frozenset({"a"}))
        self.assertEqual(definition.priority, 3)
        self.assertEqual(definition.retries, 1)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})

    def test_add_node_duplicate_raises(self) -> None:
        """Verify add_node rejects an already registered identifier."""
        self._add("a")
        with self.assertRaises(DuplicateNodeError):
            self._add("a")

    def test_add_edge_connects_and_remove_purges_incident_edges(self) -> None:
        """Verify add_edge and remove_node maintain incident adjacency sets."""
        self._add("a")
        self._add("b")
        self._add("c")
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "c")
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.get_dependencies("c"), {"b"})
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertEqual(self.dag.all_nodes(), {"a", "c"})

    def test_add_edge_missing_endpoint_raises(self) -> None:
        """Verify add_edge reports missing endpoints."""
        self._add("a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "downstream")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("upstream", "a")

    def test_missing_node_lookups_raise(self) -> None:
        """Verify lookups of unregistered identifiers report missing nodes."""
        self._add("a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")

    def test_validate_reports_missing_dependency(self) -> None:
        """Verify validate reports dependencies that are not registered."""
        self._add("a", dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_validate_reports_cycle(self) -> None:
        """Verify validate reports a directed dependency cycle."""
        self._add("a", dependencies=["b"])
        self._add("b", dependencies=["a"])
        with self.assertRaises(CycleError) as caught:
            self.dag.validate()
        self.assertTrue(caught.exception.cycle)

    def test_topological_sort_orders_by_priority_then_identifier(self) -> None:
        """Verify deterministic priority/lexicographical topological ordering."""
        self._add("a", priority=0)
        self._add("b", priority=5)
        self._add("c", dependencies=["a"], priority=0)
        self._add("d", dependencies=["b"], priority=0)
        self.assertEqual(self.dag.topological_sort(), ["b", "a", "c", "d"])

    def test_topological_sort_reports_cycle(self) -> None:
        """Verify topological_sort reports a directed dependency cycle."""
        self._add("a", dependencies=["b"])
        self._add("b", dependencies=["a"])
        with self.assertRaises(CycleError) as caught:
            self.dag.topological_sort()
        self.assertTrue(caught.exception.cycle)

    def test_compute_critical_path_uses_weighted_durations(self) -> None:
        """Verify the longest weighted dependency path is selected."""
        self._add("a")
        self._add("c", dependencies=["a"])
        self._add("b", dependencies=["a"])
        path, weight = self.dag.compute_critical_path({"a": 5.0})
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 6.0)

    def test_compute_critical_path_defaults_and_empty_graph(self) -> None:
        """Verify default unit durations and the empty graph closure."""
        self.assertEqual(self.dag.compute_critical_path(None), ([], 0.0))
        self._add("a")
        self._add("b", dependencies=["a"])
        path, weight = self.dag.compute_critical_path(None)
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 2.0)

    def test_scheduler_wave_flow(self) -> None:
        """Verify root promotion, dependent unlocking, and terminal states."""
        self._add("a")
        self._add("b", dependencies=["a"])
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.assertIs(self.scheduler.get_state("a"), NodeState.READY)
        self.assertIs(self.scheduler.get_state("b"), NodeState.PENDING)
        self.scheduler.mark_running("a")
        self.assertIs(self.scheduler.get_state("a"), NodeState.RUNNING)
        self.scheduler.mark_succeeded("a")
        self.assertIs(self.scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertIs(self.scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["b"])
        self.scheduler.mark_succeeded("b")
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(
            dict(self.scheduler.get_all_states()),
            {"a": NodeState.SUCCEEDED, "b": NodeState.SUCCEEDED},
        )

    def test_scheduler_orders_ready_wave_by_priority(self) -> None:
        """Verify ready waves are ordered by priority descending then identifier ascending."""
        self._add("low", priority=0)
        self._add("high", priority=9)
        self._add("mid", priority=0)
        self.assertEqual(self.scheduler.next_wave(), ["high", "low", "mid"])

    def test_scheduler_skip_downstream_marks_transitive_dependents(self) -> None:
        """Verify SKIP_DOWNSTREAM marks transitive dependents skipped."""
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["b"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIs(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertIs(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertIs(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_continue_on_error_keeps_independent_nodes(self) -> None:
        """Verify CONTINUE_ON_ERROR skips blocked dependents but keeps independent nodes eligible."""
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("d")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIs(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertIs(self.scheduler.get_state("d"), NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), ["d"])

    def test_scheduler_fail_fast_cancels_remaining_work(self) -> None:
        """Verify FAIL_FAST cancels remaining unexecuted nodes."""
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"])
        self._add("done")
        self.scheduler.mark_running("done")
        self.scheduler.mark_succeeded("done")
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertIs(self.scheduler.get_state("b"), NodeState.CANCELLED)
        self.assertIs(self.scheduler.get_state("c"), NodeState.CANCELLED)
        self.assertIs(self.scheduler.get_state("done"), NodeState.SUCCEEDED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_continue_on_error_diamond_traversal(self) -> None:
        """Verify transitive dependent traversal terminates on converging branches."""
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"])
        self._add("d", dependencies=["b", "c"])
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIs(self.scheduler.get_state("d"), NodeState.SKIPPED)

    def test_scheduler_lookup_and_removal(self) -> None:
        """Verify state lookup rejects unknown nodes and removal purges tracking."""
        self._add("a")
        self._add("b", dependencies=["a"])
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("missing")
        self.dag.remove_node("a")
        states = self.scheduler.get_all_states()
        self.assertNotIn("a", states)
        self.assertIn("b", states)
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("a")

    def test_scheduler_empty_graph_is_finished(self) -> None:
        """Verify an empty DAG is immediately finished."""
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), [])
        self.assertEqual(dict(self.scheduler.get_all_states()), {})

    def test_runner_executes_graph_successfully(self) -> None:
        """Verify sequential execution records outcomes and the critical path."""
        self._add("a", lambda: "A")
        self._add("b", lambda: "B", ["a"])
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("a", "b"))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.results["a"].value, "A")
        self.assertEqual(report.results["b"].value, "B")
        self.assertEqual(report.critical_path, ("a", "b"))
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_runner_retries_transient_failures(self) -> None:
        """Verify configured retry attempts are executed before success."""
        flaky = FlakyAction(1)
        self._add("a", flaky, None, 0, 1)
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.succeeded_nodes, ("a",))
        self.assertEqual(report.results["a"].retries_attempted, 1)
        self.assertEqual(report.results["a"].value, "recovered")

    def test_runner_fail_fast_cancels_downstream(self) -> None:
        """Verify FAIL_FAST halts and cancels dependent work."""
        self._add("a", _boom)
        self._add("b", lambda: "B", ["a"])
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.cancelled_nodes, ("b",))
        self.assertIsNotNone(report.results["a"].error)
        self.assertIs(report.results["b"].state, NodeState.CANCELLED)

    def test_runner_skip_downstream_skips_dependents(self) -> None:
        """Verify SKIP_DOWNSTREAM skips transitive dependents of a failure."""
        self._add("a", _boom)
        self._add("b", lambda: "B", ["a"])
        report = self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.skipped_nodes, ("b",))
        self.assertIs(report.results["b"].state, NodeState.SKIPPED)

    def test_runner_continue_on_error_executes_independent_nodes(self) -> None:
        """Verify CONTINUE_ON_ERROR keeps independent nodes running."""
        self._add("a", _boom)
        self._add("b", lambda: "B", ["a"])
        self._add("d", lambda: "D")
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.skipped_nodes, ("b",))
        self.assertEqual(report.succeeded_nodes, ("d",))
        self.assertEqual(report.results["d"].value, "D")

    def test_runner_validates_before_execution(self) -> None:
        """Verify run enforces acyclicity and dependency completeness."""
        self._add("a", dependencies=["b"])
        self._add("b", dependencies=["a"])
        with self.assertRaises(CycleError):
            self.runner.run(FailurePolicy.FAIL_FAST)
        self.dag.remove_node("b")
        self.dag.remove_node("a")
        self._add("a", dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.runner.run(FailurePolicy.FAIL_FAST)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T21:08:20Z
# LAST_CHANGED: 2026-11-05T21:08:20Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 964b658e1d67
# COVERAGE_AUDIT: 2026-11-05T21:08:20Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T21:08:20Z
# PRETENSE_QA_AUDIT: 2026-11-05T21:08:20Z
# QA_AUDIT: 2026-11-05T21:08:20Z
# --- END AUTOFAB METADATA ---
