"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Callable, Dict, List, cast

from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system


def _constant(value: int) -> Callable[[], int]:
    """Module-level factory wrapping a primitive into a zero-argument node action."""

    def action() -> int:
        return value

    return action


class DagEngineLiteImplTest(unittest.TestCase):
    """Verifies DAG, WaveScheduler, and DAGRunner contracts from low/dag_engine_lite_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope: LifecycleScope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_add_node_registers_definition(self) -> None:
        """DAG POSTCONDITION register_definition: the definition is registered with its inputs."""
        dag = self.phase_scope.get_singleton(DAG)
        action = _constant(7)

        dag.add_node("a", action, ["b"], 5, 2)

        self.assertTrue(dag.has_node("a"))
        definition = dag.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertIs(definition.action, action)
        self.assertEqual(definition.dependencies, frozenset({"b"}))
        self.assertEqual(definition.priority, 5)
        self.assertEqual(definition.retries, 2)

    def test_add_node_rejects_duplicate_identifier(self) -> None:
        """DAG PRECONDITION add_node.duplicate_node: re-registration raises DuplicateNodeError."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)

        with self.assertRaises(DuplicateNodeError):
            dag.add_node("a", _constant(2), None, 0, 0)

        self.assertEqual(dag.get_node("a").priority, 0)

    def test_add_node_defers_dependency_validation(self) -> None:
        """DAG POSTCONDITION defer_dependency_checks: missing dependencies surface in validate()."""
        dag = self.phase_scope.get_singleton(DAG)

        dag.add_node("a", _constant(1), ["ghost"], 0, 0)

        self.assertFalse(dag.has_node("ghost"))
        self.assertEqual(dag.get_dependencies("a"), {"ghost"})
        with self.assertRaises(NodeNotFoundError):
            dag.validate()

    def test_add_node_without_dependencies_has_empty_upstream(self) -> None:
        """DAG POSTCONDITION directed_dependencies: WHEN dependencies are omitted no edges are added."""
        dag = self.phase_scope.get_singleton(DAG)

        dag.add_node("root", _constant(1), None, 0, 0)

        self.assertEqual(dag.get_dependencies("root"), set())
        self.assertEqual(dag.get_dependents("root"), set())
        self.assertEqual(dag.all_nodes(), {"root"})

    def test_add_edge_establishes_directed_edge(self) -> None:
        """DAG POSTCONDITION add_edge.directed_edge: downstream depends on upstream."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("up", _constant(1), None, 0, 0)
        dag.add_node("down", _constant(2), None, 0, 0)

        dag.add_edge("up", "down")

        self.assertEqual(dag.get_dependencies("down"), {"up"})
        self.assertEqual(dag.get_dependents("up"), {"down"})
        self.assertNotIn("down", dag.get_dependencies("up"))
        dag.validate()

    def test_add_edge_rejects_unknown_node(self) -> None:
        """DAG PRECONDITION add_edge.nodes_must_exist: unknown endpoints raise NodeNotFoundError."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("up", _constant(1), None, 0, 0)

        with self.assertRaises(NodeNotFoundError):
            dag.add_edge("up", "missing")
        with self.assertRaises(NodeNotFoundError):
            dag.add_edge("missing", "up")

    def test_remove_node_purges_incident_edges(self) -> None:
        """DAG POSTCONDITION remove_node.purge_incident_edges: node and incident edges disappear."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)

        dag.remove_node("b")

        self.assertFalse(dag.has_node("b"))
        self.assertEqual(dag.all_nodes(), {"a", "c"})
        self.assertNotIn("b", dag.get_dependents("a"))
        self.assertNotIn("b", dag.get_dependencies("c"))
        dag.validate()

    def test_remove_node_rejects_unknown_node(self) -> None:
        """DAG PRECONDITION remove_node.node_must_exist: unknown node raises NodeNotFoundError."""
        dag = self.phase_scope.get_singleton(DAG)

        with self.assertRaises(NodeNotFoundError):
            dag.remove_node("missing")

    def test_get_node_rejects_unknown_node(self) -> None:
        """DAG PRECONDITION get_node.node_must_exist: unknown node raises NodeNotFoundError."""
        dag = self.phase_scope.get_singleton(DAG)

        with self.assertRaises(NodeNotFoundError):
            dag.get_node("missing")

    def test_get_dependencies_returns_copy(self) -> None:
        """DAG POSTCONDITION get_dependencies.return_upstream: returns a copy of direct upstream."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        dependencies = dag.get_dependencies("b")
        self.assertEqual(dependencies, {"a"})
        dependencies.add("ghost")
        self.assertEqual(dag.get_dependencies("b"), {"a"})

    def test_get_dependents_returns_copy(self) -> None:
        """DAG POSTCONDITION get_dependents.return_downstream: returns a copy of direct downstream."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        dependents = dag.get_dependents("a")
        self.assertEqual(dependents, {"b"})
        dependents.add("ghost")
        self.assertEqual(dag.get_dependents("a"), {"b"})

    def test_get_dependencies_rejects_unknown_node(self) -> None:
        """DAG PRECONDITION get_dependencies.node_must_exist: unknown node raises NodeNotFoundError."""
        dag = self.phase_scope.get_singleton(DAG)

        with self.assertRaises(NodeNotFoundError):
            dag.get_dependencies("missing")

    def test_get_dependents_rejects_unknown_node(self) -> None:
        """DAG PRECONDITION get_dependents.node_must_exist: unknown node raises NodeNotFoundError."""
        dag = self.phase_scope.get_singleton(DAG)

        with self.assertRaises(NodeNotFoundError):
            dag.get_dependents("missing")

    def test_all_nodes_returns_copy_of_registered_identifiers(self) -> None:
        """DAG POSTCONDITION all_nodes: returns a copy of every registered node identifier."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        nodes = dag.all_nodes()
        self.assertEqual(nodes, {"a", "b"})
        nodes.add("ghost")
        self.assertEqual(dag.all_nodes(), {"a", "b"})

    def test_validate_accepts_complete_acyclic_graph(self) -> None:
        """DAG POSTCONDITION validate.complete_valid: a consistent acyclic graph validates cleanly."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)

        dag.validate()

        self.assertEqual(dag.get_dependencies("c"), {"b"})

    def test_validate_rejects_cycle(self) -> None:
        """DAG PRECONDITION validate.acyclic_graph: a directed cycle raises CycleError with its sequence."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), ["b"], 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        with self.assertRaises(CycleError) as raised:
            dag.validate()

        error = cast(CycleError, raised.exception)
        self.assertEqual(set(error.cycle), {"a", "b"})

    def test_topological_sort_respects_dependencies(self) -> None:
        """DAG POSTCONDITION topological_sort.dependency_order: prerequisites precede dependents."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("down", _constant(1), ["up"], 0, 0)
        dag.add_node("up", _constant(2), None, 0, 0)

        self.assertEqual(dag.topological_sort(), ["up", "down"])

    def test_topological_sort_breaks_ties_by_priority_then_id(self) -> None:
        """DAG POSTCONDITION topological_sort.tie_breaking: priority descending, then node_id ascending."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("bbb", _constant(1), None, 5, 0)
        dag.add_node("aaa", _constant(2), None, 5, 0)
        dag.add_node("ccc", _constant(3), None, 9, 0)

        self.assertEqual(dag.topological_sort(), ["ccc", "aaa", "bbb"])

    def test_topological_sort_rejects_cycle(self) -> None:
        """DAG PRECONDITION topological_sort.acyclic_graph: a directed cycle raises CycleError."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), ["b"], 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        with self.assertRaises(CycleError) as raised:
            dag.topological_sort()

        error = cast(CycleError, raised.exception)
        self.assertEqual(set(error.cycle), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        """DAG POSTCONDITIONS find_roots/find_leaves: in-degree zero and out-degree zero nodes."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)
        dag.add_node("island", _constant(4), None, 0, 0)

        self.assertEqual(dag.find_roots(), {"a", "island"})
        self.assertEqual(dag.find_leaves(), {"c", "island"})

    def test_compute_critical_path_longest_weighted_path(self) -> None:
        """DAG POSTCONDITIONS critical_path.longest_path/cumulative_weight: longest weighted chain."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)
        dag.add_node("d", _constant(4), ["a"], 0, 0)

        path, weight = dag.compute_critical_path(
            {"a": 1.0, "b": 2.0, "c": 1.0, "d": 5.0}
        )

        self.assertEqual(path, ["a", "d"])
        self.assertEqual(weight, 6.0)

    def test_compute_critical_path_defaults_unit_durations(self) -> None:
        """DAG POSTCONDITION critical_path.cumulative_weight: omitted durations default to 1.0."""
        dag = self.phase_scope.get_singleton(DAG)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)

        path, weight = dag.compute_critical_path(None)

        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 3.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """DAG POSTCONDITION critical_path.cumulative_weight: an empty registered graph yields no path."""
        dag = self.phase_scope.get_singleton(DAG)

        path, weight = dag.compute_critical_path(None)

        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_next_wave_orders_ready_roots_by_priority(self) -> None:
        """WaveScheduler POSTCONDITIONS next_wave.ready_nodes/priority_order: ready roots ordered."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), None, 5, 0)

        self.assertEqual(scheduler.next_wave(), ["b", "a"])
        self.assertEqual(scheduler.get_state("a"), NodeState.READY)
        self.assertEqual(scheduler.get_state("b"), NodeState.READY)

    def test_next_wave_excludes_blocked_and_running_nodes(self) -> None:
        """WaveScheduler POSTCONDITION next_wave.ready_nodes: only READY nodes with SUCCEEDED upstream."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a"])
        self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)
        scheduler.mark_running("a")
        self.assertEqual(scheduler.next_wave(), [])

    def test_next_wave_empty_when_no_ready(self) -> None:
        """WaveScheduler POSTCONDITION next_wave.empty_when_no_ready: no ready nodes yields empty list."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a"])
        scheduler.mark_running("a")
        self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """WaveScheduler POSTCONDITION mark_running.state_transition: state becomes RUNNING."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)

        self.assertEqual(scheduler.get_state("a"), NodeState.READY)
        scheduler.mark_running("a")

        self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_unblocked_dependents(self) -> None:
        """WaveScheduler POSTCONDITION mark_succeeded.promote_dependents: unlocked dependents become READY."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a"])
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")

        self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(scheduler.next_wave(), ["b"])
        self.assertEqual(scheduler.get_state("c"), NodeState.PENDING)

        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")

        self.assertEqual(scheduler.get_state("c"), NodeState.READY)
        self.assertEqual(scheduler.next_wave(), ["c"])

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """WaveScheduler POSTCONDITION mark_failed.skip_downstream: transitive dependents become SKIPPED."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)
        dag.add_node("x", _constant(4), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a", "x"])
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

        self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("x"), NodeState.READY)

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """WaveScheduler POSTCONDITION mark_failed.fail_fast: remaining non-terminal nodes become CANCELLED."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("x", _constant(3), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a", "x"])
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)

        self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
        self.assertEqual(scheduler.get_state("x"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error_preserves_independent_nodes(self) -> None:
        """WaveScheduler POSTCONDITION mark_failed.continue_on_error: independent nodes stay eligible."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("x", _constant(3), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a", "x"])
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)

        self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("x"), NodeState.READY)
        self.assertEqual(scheduler.next_wave(), ["x"])

    def test_mark_failed_skip_downstream_reconvergent_dependent(self) -> None:
        """WaveScheduler: a diamond dependent is skipped while independent nodes stay eligible."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["a"], 0, 0)
        dag.add_node("d", _constant(4), ["b", "c"], 0, 0)
        dag.add_node("x", _constant(5), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a", "x"])
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

        self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("x"), NodeState.READY)
        self.assertEqual(scheduler.next_wave(), ["x"])
        self.assertEqual(
            scheduler.get_all_states(),
            {
                "a": NodeState.FAILED,
                "b": NodeState.SKIPPED,
                "c": NodeState.SKIPPED,
                "d": NodeState.SKIPPED,
                "x": NodeState.READY,
            },
        )

    def test_mark_failed_continue_on_error_reconvergent_dependent(self) -> None:
        """WaveScheduler: a diamond dependent is skipped under continue-on-error too."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["a"], 0, 0)
        dag.add_node("d", _constant(4), ["b", "c"], 0, 0)
        dag.add_node("x", _constant(5), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a", "x"])
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)

        self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("x"), NodeState.READY)
        self.assertEqual(scheduler.next_wave(), ["x"])

        scheduler.mark_running("x")
        scheduler.mark_succeeded("x")

        self.assertTrue(scheduler.is_finished())

    def test_is_finished_true_for_empty_dag(self) -> None:
        """WaveScheduler POSTCONDITION is_finished.empty_dag: an empty DAG is finished."""
        scheduler = self.phase_scope.get_singleton(WaveScheduler)

        self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_while_nodes_remain(self) -> None:
        """WaveScheduler POSTCONDITION is_finished.non_terminal_remaining: pending work is not finished."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a"])
        self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_when_all_nodes_terminal(self) -> None:
        """WaveScheduler POSTCONDITION is_finished.all_terminal: terminal nodes mark the DAG finished."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a"])
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        self.assertEqual(scheduler.next_wave(), ["b"])
        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")

        self.assertTrue(scheduler.is_finished())

    def test_is_finished_true_after_fail_fast_cancellation(self) -> None:
        """WaveScheduler POSTCONDITION is_finished.blocked_by_failure: cancelled dependents finish the run."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        self.assertEqual(scheduler.next_wave(), ["a"])
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)

        self.assertTrue(scheduler.is_finished())

    def test_get_state_rejects_unknown_node(self) -> None:
        """WaveScheduler PRECONDITION get_state.node_must_exist: unknown node raises NodeNotFoundError."""
        scheduler = self.phase_scope.get_singleton(WaveScheduler)

        with self.assertRaises(NodeNotFoundError):
            scheduler.get_state("missing")

    def test_get_all_states_reports_every_registered_node(self) -> None:
        """WaveScheduler POSTCONDITION get_all_states: mapping covers registered nodes and is a copy."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        states = scheduler.get_all_states()
        self.assertEqual(states, {"a": NodeState.READY, "b": NodeState.PENDING})

        mutable_states = cast(Dict[str, NodeState], scheduler.get_all_states())
        mutable_states["ghost"] = NodeState.PENDING
        self.assertNotIn("ghost", scheduler.get_all_states())

    def test_remove_node_purges_scheduler_state(self) -> None:
        """DAG POSTCONDITION remove_node.purge_scheduler_state: removed identifiers leave scheduler state."""
        dag = self.phase_scope.get_singleton(DAG)
        scheduler = self.phase_scope.get_singleton(WaveScheduler)
        dag.add_node("a", _constant(1), None, 0, 0)

        self.assertIn("a", scheduler.get_all_states())

        dag.remove_node("a")

        self.assertNotIn("a", scheduler.get_all_states())

    def test_run_executes_all_nodes_in_dependency_order(self) -> None:
        """DAGRunner POSTCONDITIONS sequential_waves/consolidated_report: nodes run in dependency order."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)
        executed: List[str] = []

        def action_a() -> str:
            executed.append("a")
            return "result-a"

        def action_b() -> str:
            executed.append("b")
            return "result-b"

        dag.add_node("a", action_a, None, 0, 0)
        dag.add_node("b", action_b, ["a"], 0, 0)

        report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)

        self.assertEqual(executed, ["a", "b"])
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.critical_path, ("a", "b"))
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(set(report.results.keys()), {"a", "b"})
        self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].value, "result-a")
        self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["b"].value, "result-b")

    def test_run_retries_failing_action(self) -> None:
        """DAGRunner POSTCONDITION run.retry_failures: a transient failure is retried up to the retry count."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)
        attempts: Dict[str, int] = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient failure")
            return "ok"

        dag.add_node("flaky", flaky, None, 0, 2)

        report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)

        result = report.results["flaky"]
        self.assertEqual(result.state, NodeState.SUCCEEDED)
        self.assertEqual(result.value, "ok")
        self.assertEqual(result.retries_attempted, 1)
        self.assertEqual(report.succeeded_nodes, ("flaky",))

    def test_run_records_failure_without_retries(self) -> None:
        """DAGRunner POSTCONDITION run.consolidated_report: an exhausted action records a FAILED result."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)

        def failing() -> str:
            raise ValueError("boom")

        dag.add_node("boom", failing, None, 0, 0)

        report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)

        result = report.results["boom"]
        self.assertEqual(result.state, NodeState.FAILED)
        self.assertIsInstance(result.error, ValueError)
        self.assertEqual(result.retries_attempted, 0)
        self.assertEqual(report.failed_nodes, ("boom",))

    def test_run_applies_fail_fast_policy(self) -> None:
        """DAGRunner POSTCONDITION run.apply_failure_policy: FAIL_FAST cancels the remaining nodes."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)

        def failing() -> str:
            raise RuntimeError("boom")

        dag.add_node("a", failing, None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        report = runner.run(FailurePolicy.FAIL_FAST)

        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(report.results["a"].state, NodeState.FAILED)
        self.assertEqual(set(report.cancelled_nodes), {"b"})
        self.assertEqual(report.results["b"].state, NodeState.CANCELLED)

    def test_run_applies_skip_downstream_policy(self) -> None:
        """DAGRunner POSTCONDITION run.apply_failure_policy: SKIP_DOWNSTREAM skips dependents only."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)

        def failing() -> str:
            raise RuntimeError("boom")

        dag.add_node("a", failing, None, 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)
        dag.add_node("c", _constant(3), ["b"], 0, 0)
        dag.add_node("x", _constant(4), None, 0, 0)

        report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)

        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(set(report.skipped_nodes), {"b", "c"})
        self.assertEqual(set(report.succeeded_nodes), {"x"})
        self.assertEqual(report.results["b"].state, NodeState.SKIPPED)
        self.assertEqual(report.results["c"].state, NodeState.SKIPPED)

    def test_run_rejects_missing_dependency(self) -> None:
        """DAGRunner PRECONDITION run.dependencies_exist: validate_before_waves raises NodeNotFoundError."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)
        dag.add_node("a", _constant(1), ["ghost"], 0, 0)

        with self.assertRaises(NodeNotFoundError):
            runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_run_rejects_cyclic_graph(self) -> None:
        """DAGRunner PRECONDITION run.acyclic_graph: validate_before_waves raises CycleError."""
        dag = self.phase_scope.get_singleton(DAG)
        runner = self.phase_scope.get_singleton(DAGRunner)
        dag.add_node("a", _constant(1), ["b"], 0, 0)
        dag.add_node("b", _constant(2), ["a"], 0, 0)

        with self.assertRaises(CycleError):
            runner.run(FailurePolicy.FAIL_FAST)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:13:05Z
# LAST_CHANGED: 2026-11-08T06:09:52Z
# CHANGE: Addressed feedback: removed the wave-loop halt test that mutated the graph mid-run into a cycle and asserted a consolidated DAGRunReport for a violated run.acyclic_graph precondition (CycleError is the only contracted outcome). Retained the empty-graph critical-path and reconvergent diamond dependent coverage; no unresolvable contracted scenario asserts report behavior for cyclic graphs.
# COVERAGE_AUDIT: 2026-11-08T06:13:05Z
# QA_AUDIT: 2026-11-08T06:12:50Z
# --- END AUTOFAB METADATA ---
