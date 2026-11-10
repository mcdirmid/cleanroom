"""Unit tests for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import unittest
from typing import Any, Optional

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
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


class _Action:
    """Scripted zero-argument action that records calls and scripted failures."""

    def __init__(
        self,
        value: Any = None,
        fail_times: int = 0,
        error: Optional[Exception] = None,
    ) -> None:
        self.value: Any = value
        self.fail_times: int = fail_times
        self.error: Optional[Exception] = error
        self.calls: int = 0

    def __call__(self) -> Any:
        self.calls += 1
        if self.calls <= self.fail_times:
            if self.error is not None:
                raise self.error
            raise RuntimeError("scripted action failure")
        return self.value


class DagEngineLiteImplTest(unittest.TestCase):
    """Exercises the DAG, WaveScheduler, and DAGRunner singletons within a system phase."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = self.phase_scope.get_singleton(DAG)
        self.scheduler = self.phase_scope.get_singleton(WaveScheduler)
        self.runner = self.phase_scope.get_singleton(DAGRunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # --- DAG node management ---

    def test_add_node_registers_definition(self) -> None:
        """POSTCONDITION register_definition: the node definition is registered."""
        action = _Action(7)
        self.dag.add_node("a", action, None, 3, 1)
        self.assertTrue(self.dag.has_node("a"))
        definition = self.dag.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertIs(definition.action, action)
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.priority, 3)
        self.assertEqual(definition.retries, 1)
        self.assertEqual(self.dag.all_nodes(), {"a"})

    def test_add_node_with_dependencies_creates_edges(self) -> None:
        """POSTCONDITION directed_dependencies: edges are added from each dependency."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), None, 0, 0)
        self.dag.add_node("c", _Action(), ["a", "b"], 0, 0)
        self.assertEqual(self.dag.get_dependencies("c"), {"a", "b"})
        self.assertEqual(self.dag.get_dependents("a"), {"c"})
        self.assertEqual(self.dag.get_dependents("b"), {"c"})
        self.assertEqual(self.dag.get_dependencies("a"), set())

    def test_add_node_defers_missing_dependency_checks(self) -> None:
        """POSTCONDITION defer_dependency_checks: missing dependencies surface at validate."""
        self.dag.add_node("a", _Action(), ["ghost"], 0, 0)
        self.assertTrue(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependencies("a"), {"ghost"})
        with self.assertRaises(NodeNotFoundError) as context:
            self.dag.validate()
        self.assertEqual(context.exception.node_id, "ghost")

    def test_add_node_duplicate_raises_duplicate_node_error(self) -> None:
        """PRECONDITION duplicate_node: a duplicate identifier raises DuplicateNodeError."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        with self.assertRaises(DuplicateNodeError) as context:
            self.dag.add_node("a", _Action(), None, 0, 0)
        self.assertEqual(context.exception.node_id, "a")

    def test_add_edge_establishes_directed_edge(self) -> None:
        """POSTCONDITION directed_edge: a directed dependency edge is established."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), None, 0, 0)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_add_edge_missing_node_raises_node_not_found_error(self) -> None:
        """PRECONDITION nodes_must_exist: either missing endpoint raises NodeNotFoundError."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "a")

    def test_remove_node_purges_incident_edges_and_scheduler_state(self) -> None:
        """POSTCONDITIONS purge_incident_edges and purge_scheduler_state."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.scheduler.next_wave()
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.all_nodes(), {"b"})
        self.assertEqual(self.dag.get_dependencies("b"), set())
        self.assertNotIn("a", self.scheduler.get_all_states())
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("a")

    def test_remove_non_root_node_purges_upstream_dependency_edge(self) -> None:
        """POSTCONDITION purge_incident_edges: removing a dependent purges its upstream edge."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["b"], 0, 0)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.scheduler.next_wave()
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a", "c"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertNotIn("b", self.scheduler.get_all_states())

    def test_remove_node_missing_raises_node_not_found_error(self) -> None:
        """PRECONDITION node_must_exist: removing an unknown node raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError) as context:
            self.dag.remove_node("missing")
        self.assertEqual(context.exception.node_id, "missing")

    def test_has_node_reports_presence(self) -> None:
        """has_node reports node registration without raising on unknown identifiers."""
        self.assertFalse(self.dag.has_node("a"))
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.assertTrue(self.dag.has_node("a"))

    def test_get_node_missing_raises_node_not_found_error(self) -> None:
        """PRECONDITION node_must_exist: get_node raises NodeNotFoundError when absent."""
        with self.assertRaises(NodeNotFoundError) as context:
            self.dag.get_node("missing")
        self.assertEqual(context.exception.node_id, "missing")

    def test_get_dependencies_and_dependents_return_defensive_copies(self) -> None:
        """POSTCONDITIONS return_upstream/return_downstream expose independent sets."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        dependencies = self.dag.get_dependencies("b")
        dependencies.add("ghost")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        dependents = self.dag.get_dependents("a")
        dependents.clear()
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_get_dependencies_missing_raises_node_not_found_error(self) -> None:
        """PRECONDITION node_must_exist: get_dependencies raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")

    def test_get_dependents_missing_raises_node_not_found_error(self) -> None:
        """PRECONDITION node_must_exist: get_dependents raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_all_nodes_returns_every_registered_identifier(self) -> None:
        """all_nodes returns the complete set of registered node identifiers."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), None, 0, 0)
        self.assertEqual(self.dag.all_nodes(), {"a", "b", "c"})

    # --- DAG validation and ordering ---

    def test_validate_accepts_consistent_acyclic_graph(self) -> None:
        """POSTCONDITION complete_valid: a complete acyclic graph validates without error."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["a", "b"], 0, 0)
        self.assertIsNone(self.dag.validate())

    def test_validate_detects_cycle(self) -> None:
        """PRECONDITION acyclic_graph: a directed cycle raises CycleError with its sequence."""
        self.dag.add_node("a", _Action(), ["b"], 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        with self.assertRaises(CycleError) as context:
            self.dag.validate()
        self.assertEqual(set(context.exception.cycle), {"a", "b"})

    def test_topological_sort_orders_prerequisites_first(self) -> None:
        """POSTCONDITION dependency_order: every prerequisite precedes its dependents."""
        self.dag.add_node("c", _Action(), ["b"], 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.assertEqual(self.dag.topological_sort(), ["a", "b", "c"])

    def test_topological_sort_breaks_ties_by_priority_then_identifier(self) -> None:
        """POSTCONDITION tie_breaking: priority descending then node_id ascending."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), None, 5, 0)
        self.dag.add_node("c", _Action(), None, 0, 0)
        self.assertEqual(self.dag.topological_sort(), ["b", "a", "c"])

    def test_topological_sort_raises_cycle_error(self) -> None:
        """PRECONDITION acyclic_graph: topological_sort raises CycleError on a cycle."""
        self.dag.add_node("a", _Action(), ["b"], 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """find_roots/find_leaves report in-degree zero and out-degree zero nodes."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["b"], 0, 0)
        self.dag.add_node("d", _Action(), None, 0, 0)
        self.assertEqual(self.dag.find_roots(), {"a", "d"})
        self.assertEqual(self.dag.find_leaves(), {"c", "d"})

    def test_compute_critical_path_uses_default_durations(self) -> None:
        """POSTCONDITIONS longest_path/cumulative_weight with default weight of 1.0."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["a"], 0, 0)
        self.dag.add_node("d", _Action(), ["b", "c"], 0, 0)
        path, weight = self.dag.compute_critical_path(None)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0], "a")
        self.assertEqual(path[-1], "d")
        self.assertEqual(weight, 3.0)

    def test_compute_critical_path_uses_estimated_durations(self) -> None:
        """POSTCONDITIONS longest_path/cumulative_weight with explicit duration weights."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["a"], 0, 0)
        self.dag.add_node("d", _Action(), ["b", "c"], 0, 0)
        path, weight = self.dag.compute_critical_path(
            {"a": 1.0, "b": 5.0, "c": 2.0, "d": 1.0}
        )
        self.assertEqual(path, ["a", "b", "d"])
        self.assertEqual(weight, 7.0)

    def test_compute_critical_path_empty_graph_returns_empty_path(self) -> None:
        """BOUNDARY longest_path: an empty graph yields an empty path and zero weight."""
        path, weight = self.dag.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    # --- Wave scheduling ---

    def test_next_wave_returns_ready_roots_ordered_by_priority(self) -> None:
        """POSTCONDITIONS ready_nodes/priority_order: ready roots ordered by priority."""
        self.dag.add_node("a", _Action(), None, 1, 0)
        self.dag.add_node("b", _Action(), None, 5, 0)
        self.dag.add_node("c", _Action(), ["a"], 9, 0)
        self.assertEqual(self.scheduler.next_wave(), ["b", "a"])

    def test_next_wave_empty_when_no_nodes_are_ready(self) -> None:
        """POSTCONDITION empty_when_no_ready: no ready node yields an empty list."""
        self.assertEqual(self.scheduler.next_wave(), [])
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """POSTCONDITION state_transition: mark_running sets the RUNNING state."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.scheduler.next_wave()
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_blocked_dependents(self) -> None:
        """POSTCONDITIONS state_transition/promote_dependents: dependents become READY."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["b"], 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["b"])

    def test_mark_succeeded_requires_all_upstream_dependencies(self) -> None:
        """POSTCONDITION promote_dependents: promotion waits for every upstream dependency."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["a"], 0, 0)
        self.dag.add_node("d", _Action(), ["b", "c"], 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("b"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("d"), NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["b", "c"])
        self.scheduler.mark_running("b")
        self.scheduler.mark_succeeded("b")
        self.assertEqual(self.scheduler.get_state("d"), NodeState.PENDING)
        self.scheduler.mark_running("c")
        self.scheduler.mark_succeeded("c")
        self.assertEqual(self.scheduler.get_state("d"), NodeState.READY)

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """POSTCONDITION fail_fast: remaining PENDING nodes become CANCELLED."""
        self.dag.add_node("a", _Action(), None, 10, 0)
        self.dag.add_node("b", _Action(), None, 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a", "b"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """POSTCONDITION skip_downstream: transitive dependents become SKIPPED."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["b"], 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_mark_failed_continue_on_error_keeps_independent_nodes_eligible(self) -> None:
        """POSTCONDITION continue_on_error: unblocked independent nodes stay eligible."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("d", _Action(), None, 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a", "d"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("d"), NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), ["d"])
        self.scheduler.mark_running("d")
        self.scheduler.mark_succeeded("d")
        self.assertTrue(self.scheduler.is_finished())

    def test_mark_failed_continue_on_error_traverses_shared_ancestor_paths(self) -> None:
        """POSTCONDITION continue_on_error: shared-ancestor dependents are all skipped."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["a"], 0, 0)
        self.dag.add_node("d", _Action(), ["b", "c"], 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("d"), NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_mark_failed_continue_on_error_leaves_independent_branch_ancestors_untouched(self) -> None:
        """POSTCONDITION continue_on_error: a failed branch leaves independent non-terminal branches intact."""
        self.dag.add_node("a", _Action(), None, 10, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("c", _Action(), ["b"], 0, 0)
        self.dag.add_node("x", _Action(), None, 0, 0)
        self.dag.add_node("x2", _Action(), ["x"], 0, 0)
        self.dag.add_node("y", _Action(), ["x2"], 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a", "x"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("x"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("x2"), NodeState.PENDING)
        self.assertEqual(self.scheduler.get_state("y"), NodeState.PENDING)
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), ["x"])
        self.scheduler.mark_running("x")
        self.scheduler.mark_succeeded("x")
        self.assertEqual(self.scheduler.get_state("x2"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("y"), NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["x2"])
        self.scheduler.mark_running("x2")
        self.scheduler.mark_succeeded("x2")
        self.assertEqual(self.scheduler.get_state("y"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["y"])
        self.scheduler.mark_running("y")
        self.scheduler.mark_succeeded("y")
        self.assertTrue(self.scheduler.is_finished())

    def test_mark_failed_continue_on_error_preserves_independent_diamond_convergence(self) -> None:
        """POSTCONDITION continue_on_error: an independent diamond branch still converges after a failure."""
        self.dag.add_node("a", _Action(), None, 10, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.dag.add_node("x", _Action(), None, 0, 0)
        self.dag.add_node("p", _Action(), ["x"], 0, 0)
        self.dag.add_node("q", _Action(), ["x"], 0, 0)
        self.dag.add_node("z", _Action(), ["p", "q"], 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a", "x"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("x"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("p"), NodeState.PENDING)
        self.assertEqual(self.scheduler.get_state("q"), NodeState.PENDING)
        self.assertEqual(self.scheduler.get_state("z"), NodeState.PENDING)
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), ["x"])
        self.scheduler.mark_running("x")
        self.scheduler.mark_succeeded("x")
        self.assertEqual(self.scheduler.get_state("p"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("q"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("z"), NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["p", "q"])
        self.scheduler.mark_running("p")
        self.scheduler.mark_succeeded("p")
        self.assertEqual(self.scheduler.get_state("z"), NodeState.PENDING)
        self.scheduler.mark_running("q")
        self.scheduler.mark_succeeded("q")
        self.assertEqual(self.scheduler.get_state("z"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["z"])
        self.scheduler.mark_running("z")
        self.scheduler.mark_succeeded("z")
        self.assertTrue(self.scheduler.is_finished())

    def test_is_finished_true_when_blocked_dependents_remain_without_ready_nodes(self) -> None:
        """POSTCONDITION blocked_by_failure: blocked dependents finish the run when nothing is ready."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.scheduler.next_wave()
        self.scheduler.mark_running("a")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), [])
        self.assertTrue(self.scheduler.is_finished())

    def test_is_finished_empty_dag_is_true(self) -> None:
        """POSTCONDITION empty_dag: an empty DAG is finished."""
        self.assertTrue(self.scheduler.is_finished())

    def test_is_finished_false_with_non_terminal_nodes(self) -> None:
        """POSTCONDITION non_terminal_remaining: eligible nodes keep the run unfinished."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        self.assertFalse(self.scheduler.is_finished())
        self.scheduler.next_wave()
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.assertFalse(self.scheduler.is_finished())

    def test_is_finished_true_when_all_nodes_terminal(self) -> None:
        """POSTCONDITION all_terminal: every terminal node finishes the run."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), None, 0, 0)
        self.scheduler.next_wave()
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.scheduler.mark_running("b")
        self.scheduler.mark_failed("b", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertTrue(self.scheduler.is_finished())

    def test_get_state_missing_raises_node_not_found_error(self) -> None:
        """PRECONDITION node_must_exist: get_state raises NodeNotFoundError when absent."""
        with self.assertRaises(NodeNotFoundError) as context:
            self.scheduler.get_state("missing")
        self.assertEqual(context.exception.node_id, "missing")

    def test_get_all_states_reports_initial_states(self) -> None:
        """get_all_states reflects every registered node with root/non-root defaults."""
        self.dag.add_node("a", _Action(), None, 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        states = self.scheduler.get_all_states()
        self.assertEqual(set(states.keys()), {"a", "b"})
        self.assertEqual(states["a"], NodeState.READY)
        self.assertEqual(states["b"], NodeState.PENDING)

    # --- DAG execution runner ---

    def test_run_executes_all_nodes_and_reports_success(self) -> None:
        """POSTCONDITIONS sequential_waves/consolidated_report: successful end-to-end run."""
        action_a = _Action(1)
        action_b = _Action(2)
        self.dag.add_node("a", action_a, None, 0, 0)
        self.dag.add_node("b", action_b, ["a"], 0, 0)
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(tuple(report.failed_nodes), ())
        self.assertEqual(tuple(report.skipped_nodes), ())
        self.assertEqual(tuple(report.cancelled_nodes), ())
        self.assertEqual(set(report.results.keys()), {"a", "b"})
        self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].value, 1)
        self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["b"].value, 2)
        self.assertEqual(action_a.calls, 1)
        self.assertEqual(action_b.calls, 1)
        self.assertGreaterEqual(report.results["a"].duration_seconds, 0.0)
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(tuple(report.critical_path), ("a", "b"))

    def test_run_retries_failed_action_before_succeeding(self) -> None:
        """POSTCONDITION retry_failures: retries execute up to the configured count."""
        action = _Action("ok", fail_times=2)
        self.dag.add_node("a", action, None, 0, 2)
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(action.calls, 3)
        self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].value, "ok")
        self.assertEqual(report.results["a"].retries_attempted, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a"})

    def test_run_records_failure_with_caught_error(self) -> None:
        """POSTCONDITION consolidated_report: failed actions record the caught exception."""
        boom = RuntimeError("boom")
        action = _Action(fail_times=1, error=boom)
        self.dag.add_node("a", action, None, 0, 0)
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(tuple(report.failed_nodes), ("a",))
        self.assertEqual(report.results["a"].state, NodeState.FAILED)
        self.assertIs(report.results["a"].error, boom)

    def test_run_fail_fast_halts_and_cancels_remaining_nodes(self) -> None:
        """POSTCONDITION apply_failure_policy: FAIL_FAST cancels unexecuted nodes."""
        bad = _Action(fail_times=1, error=RuntimeError("bad"))
        good = _Action(5)
        self.dag.add_node("a", bad, None, 10, 0)
        self.dag.add_node("b", good, None, 0, 0)
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(tuple(report.failed_nodes), ("a",))
        self.assertIn("b", report.cancelled_nodes)
        self.assertEqual(report.results["b"].state, NodeState.CANCELLED)
        self.assertEqual(good.calls, 0)

    def test_run_skip_downstream_skips_blocked_dependents(self) -> None:
        """POSTCONDITION apply_failure_policy: SKIP_DOWNSTREAM skips blocked dependents."""
        bad = _Action(fail_times=1, error=RuntimeError("bad"))
        self.dag.add_node("a", bad, None, 0, 0)
        self.dag.add_node("b", _Action(1), ["a"], 0, 0)
        report = self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(tuple(report.failed_nodes), ("a",))
        self.assertEqual(set(report.skipped_nodes), {"b"})
        self.assertEqual(report.results["b"].state, NodeState.SKIPPED)

    def test_run_continue_on_error_executes_independent_nodes(self) -> None:
        """POSTCONDITION apply_failure_policy: independent nodes still execute."""
        bad = _Action(fail_times=1, error=RuntimeError("bad"))
        good = _Action(9)
        self.dag.add_node("a", bad, None, 0, 0)
        self.dag.add_node("b", _Action(1), ["a"], 0, 0)
        self.dag.add_node("c", good, None, 0, 0)
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(tuple(report.failed_nodes), ("a",))
        self.assertIn("c", report.succeeded_nodes)
        self.assertEqual(report.results["c"].value, 9)
        self.assertEqual(good.calls, 1)
        self.assertEqual(set(report.skipped_nodes), {"b"})

    def test_run_validates_missing_dependency_before_execution(self) -> None:
        """POSTCONDITION validate_before_waves: missing dependencies surface before waves."""
        action = _Action()
        self.dag.add_node("a", action, ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(action.calls, 0)

    def test_run_validates_cycle_before_execution(self) -> None:
        """POSTCONDITION validate_before_waves: cycles surface before wave execution."""
        action = _Action()
        self.dag.add_node("a", action, ["b"], 0, 0)
        self.dag.add_node("b", _Action(), ["a"], 0, 0)
        with self.assertRaises(CycleError):
            self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(action.calls, 0)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T18:21:26Z
# LAST_CHANGED: 2026-11-09T18:20:49Z
# CHANGE: Resolved the continue_on_error 'independent branch shared ancestor convergence' coverage feedback: added test_mark_failed_continue_on_error_preserves_independent_diamond_convergence. The test marks a node FAILED on a branch (a -> b) while an independent diamond branch (x -> p, x -> q, and z depending on both p and q) converges from a shared ancestor. It asserts the failed branch is skipped (b SKIPPED) while the independent diamond branch stays untouched (x READY, p/q/z PENDING), then drives the diamond so z is promoted to READY only after both p and q succeed, and verifies is_finished transitions to True. Covers branch_shape=diamond with failed_node=outside_branch and shared ancestor convergence. Verified with bin/check_files.
# COVERAGE_AUDIT: 2026-11-09T18:21:26Z
# QA_AUDIT: 2026-11-09T18:21:13Z
# --- END AUTOFAB METADATA ---
