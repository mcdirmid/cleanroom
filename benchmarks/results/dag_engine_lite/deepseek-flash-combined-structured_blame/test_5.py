from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleTestCase

from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGTarget,
    DAGRunner as DAGRunnerTarget,
    WaveScheduler as WaveSchedulerTarget,
)


class DAGTest(LifecycleTestCase):
    """Unit tests for the DAG node registration, traversal, and ordering behavior."""

    target = DAGTarget

    def test_add_node_registers_definition(self) -> None:
        """Verify adding a node records its action, priority, and retry metadata."""
        self.sut.add_node("a", lambda: "value", None, 3, 2)
        self.assertTrue(self.sut.has_node("a"))
        definition = self.sut.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.priority, 3)
        self.assertEqual(definition.retries, 2)
        self.assertEqual(definition.action(), "value")
        self.assertEqual(self.sut.get_dependencies("a"), set())
        self.assertEqual(self.sut.get_dependents("a"), set())

    def test_add_node_records_directed_dependencies(self) -> None:
        """Verify dependency identifiers registered with a node become directed edges."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(self.sut.get_node("b").dependencies, frozenset({"a"}))
        self.assertEqual(self.sut.get_dependencies("b"), {"a"})
        self.assertEqual(self.sut.get_dependents("a"), {"b"})
        self.assertEqual(self.sut.get_dependents("b"), set())

    def test_add_node_collapses_duplicate_dependencies(self) -> None:
        """Verify repeated dependency identifiers collapse into a single immutable edge set."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a", "a"], 0, 0)
        self.assertEqual(self.sut.get_node("b").dependencies, frozenset({"a"}))
        self.assertEqual(self.sut.get_dependencies("b"), {"a"})

    def test_add_node_duplicate_raises_error(self) -> None:
        """Verify registering an already registered node identifier reports a duplicate node error."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        with self.assertRaises(DuplicateNodeError) as context:
            self.sut.add_node("a", lambda: None, None, 0, 0)
        self.assertEqual(context.exception.node_id, "a")
        self.assertEqual(self.sut.all_nodes(), {"a"})

    def test_add_node_defers_missing_dependency_validation(self) -> None:
        """Verify a missing dependency is accepted on insertion and reported later by validation."""
        self.sut.add_node("b", lambda: None, ["ghost"], 0, 0)
        self.assertFalse(self.sut.has_node("ghost"))
        self.assertEqual(self.sut.get_dependencies("b"), {"ghost"})
        with self.assertRaises(NodeNotFoundError):
            self.sut.validate()

    def test_add_edge_establishes_directed_edge(self) -> None:
        """Verify an explicit edge wires the downstream node to its upstream prerequisite."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, None, 0, 0)
        self.sut.add_edge("a", "b")
        self.assertEqual(self.sut.get_dependents("a"), {"b"})
        self.assertEqual(self.sut.get_dependencies("b"), {"a"})

    def test_add_edge_missing_upstream_raises_error(self) -> None:
        """Verify an edge referencing an unknown upstream node reports a missing node error."""
        self.sut.add_node("downstream", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.add_edge("ghost", "downstream")

    def test_add_edge_missing_downstream_raises_error(self) -> None:
        """Verify an edge referencing an unknown downstream node reports a missing node error."""
        self.sut.add_node("upstream", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.add_edge("upstream", "ghost")

    def test_remove_node_purges_incident_edges(self) -> None:
        """Verify removing a node detaches it from all upstream and downstream neighbors."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["b"], 0, 0)
        self.sut.remove_node("b")
        self.assertFalse(self.sut.has_node("b"))
        self.assertEqual(self.sut.all_nodes(), {"a", "c"})
        self.assertEqual(self.sut.get_dependencies("c"), set())
        self.assertEqual(self.sut.get_dependents("a"), set())
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_node("b")

    def test_remove_node_missing_raises_error(self) -> None:
        """Verify removing an unregistered node reports a missing node error."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.remove_node("ghost")

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Verify removing a node clears scheduler state so a re-added node starts fresh."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        scheduler = self.get_singleton(WaveSchedulerTarget)
        self.assertEqual(scheduler.next_wave(), ["a"])
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")
        self.assertTrue(scheduler.is_finished())
        self.sut.remove_node("b")
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)
        self.assertFalse(scheduler.is_finished())

    def test_remove_node_clears_state_from_all_states(self) -> None:
        """Verify a removed node disappears from the scheduler state mapping."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["b"], 0, 0)
        scheduler = self.get_singleton(WaveSchedulerTarget)
        self.assertEqual(scheduler.next_wave(), ["a"])
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")
        self.assertEqual(scheduler.get_state("b"), NodeState.SUCCEEDED)
        self.sut.remove_node("b")
        self.assertNotIn("b", scheduler.get_all_states())
        self.assertEqual(set(scheduler.get_all_states()), {"a", "c"})
        with self.assertRaises(NodeNotFoundError):
            scheduler.get_state("b")

    def test_has_node_reports_membership(self) -> None:
        """Verify membership queries reflect node insertion and removal."""
        self.assertFalse(self.sut.has_node("a"))
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.assertTrue(self.sut.has_node("a"))
        self.sut.remove_node("a")
        self.assertFalse(self.sut.has_node("a"))

    def test_all_nodes_returns_independent_copy(self) -> None:
        """Verify the node identifier snapshot is detached from internal graph state."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        nodes = self.sut.all_nodes()
        nodes.add("ghost")
        self.assertFalse(self.sut.has_node("ghost"))
        self.assertEqual(self.sut.all_nodes(), {"a"})

    def test_accessors_return_independent_copies(self) -> None:
        """Verify dependency and dependent accessors return detached sets."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        dependencies = self.sut.get_dependencies("b")
        dependencies.add("ghost")
        self.assertEqual(self.sut.get_dependencies("b"), {"a"})
        dependents = self.sut.get_dependents("a")
        dependents.add("ghost")
        self.assertEqual(self.sut.get_dependents("a"), {"b"})
        self.assertFalse(self.sut.has_node("ghost"))

    def test_get_node_missing_raises_error(self) -> None:
        """Verify looking up an unregistered node definition reports a missing node error."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_node("ghost")

    def test_get_dependencies_missing_raises_error(self) -> None:
        """Verify querying dependencies of an unregistered node reports a missing node error."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_dependencies("ghost")

    def test_get_dependents_missing_raises_error(self) -> None:
        """Verify querying dependents of an unregistered node reports a missing node error."""
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_dependents("ghost")

    def test_validate_accepts_complete_acyclic_graph(self) -> None:
        """Verify a complete acyclic graph validates without raising."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["b"], 0, 0)
        self.sut.validate()
        self.assertEqual(self.sut.all_nodes(), {"a", "b", "c"})

    def test_validate_missing_dependency_raises_error(self) -> None:
        """Verify validation reports a missing node error for an unknown dependency."""
        self.sut.add_node("a", lambda: None, ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.validate()

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """Verify validation reports a cycle error containing the participating nodes."""
        self.sut.add_node("a", lambda: None, ["b"], 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        with self.assertRaises(CycleError) as context:
            self.sut.validate()
        self.assertEqual(set(context.exception.cycle), {"a", "b"})

    def test_topological_sort_respects_dependency_order(self) -> None:
        """Verify prerequisites are ordered before their dependents."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["b"], 0, 0)
        self.assertEqual(self.sut.topological_sort(), ["a", "b", "c"])

    def test_topological_sort_orders_ready_nodes_by_priority(self) -> None:
        """Verify concurrently ready nodes are ordered by higher priority first."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, None, 5, 0)
        self.sut.add_node("c", lambda: None, ["a"], 1, 0)
        self.sut.add_node("d", lambda: None, ["c"], 10, 0)
        self.sut.add_node("e", lambda: None, ["b"], 2, 0)
        self.assertEqual(self.sut.topological_sort(), ["b", "e", "a", "c", "d"])

    def test_topological_sort_breaks_priority_ties_by_node_id(self) -> None:
        """Verify nodes sharing a priority are ordered by ascending identifier."""
        self.sut.add_node("z", lambda: None, None, 2, 0)
        self.sut.add_node("y", lambda: None, None, 2, 0)
        self.sut.add_node("x", lambda: None, None, 1, 0)
        self.assertEqual(self.sut.topological_sort(), ["y", "z", "x"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """Verify ordering a cyclic graph reports a cycle error."""
        self.sut.add_node("a", lambda: None, ["b"], 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        with self.assertRaises(CycleError):
            self.sut.topological_sort()

    def test_find_roots_returns_nodes_without_dependencies(self) -> None:
        """Verify root discovery collects every node with an empty upstream set."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, None, 0, 0)
        self.sut.add_node("c", lambda: None, ["a"], 0, 0)
        self.sut.add_node("d", lambda: None, ["c"], 0, 0)
        self.assertEqual(self.sut.find_roots(), {"a", "b"})

    def test_find_leaves_returns_nodes_without_dependents(self) -> None:
        """Verify leaf discovery collects every node with an empty downstream set."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["b"], 0, 0)
        self.sut.add_node("d", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.find_leaves(), {"c", "d"})

    def test_compute_critical_path_uses_default_weights(self) -> None:
        """Verify omitted durations default to a unit weight per node along the longest path."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        self.sut.add_node("c", lambda: None, ["b"], 0, 0)
        path, weight = self.sut.compute_critical_path(None)
        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 3.0)

    def test_compute_critical_path_selects_longest_weighted_path(self) -> None:
        """Verify the critical path follows the heaviest branch into a shared dependent."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, None, 0, 0)
        self.sut.add_node("c", lambda: None, ["a", "b"], 0, 0)
        path, weight = self.sut.compute_critical_path({"a": 1.0, "b": 5.0, "c": 2.0})
        self.assertEqual(path, ["b", "c"])
        self.assertEqual(weight, 7.0)

    def test_compute_critical_path_defaults_unspecified_durations(self) -> None:
        """Verify nodes omitted from the duration mapping fall back to a unit weight."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        self.sut.add_node("b", lambda: None, ["a"], 0, 0)
        path, weight = self.sut.compute_critical_path({"a": 3.0})
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 4.0)

    def test_compute_critical_path_for_single_node(self) -> None:
        """Verify a lone node forms its own critical path with a unit weight."""
        self.sut.add_node("a", lambda: None, None, 0, 0)
        path, weight = self.sut.compute_critical_path(None)
        self.assertEqual(path, ["a"])
        self.assertEqual(weight, 1.0)

    def test_compute_critical_path_for_empty_graph(self) -> None:
        """Verify an empty graph yields an empty critical path with zero total weight."""
        path, weight = self.sut.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)
        empty_path, empty_weight = self.sut.compute_critical_path({})
        self.assertEqual(empty_path, [])
        self.assertEqual(empty_weight, 0.0)


class WaveSchedulerTest(LifecycleTestCase):
    """Unit tests for wave readiness, state transitions, and failure policies."""

    target = WaveSchedulerTarget

    def test_next_wave_returns_ready_roots_in_priority_order(self) -> None:
        """Verify the initial wave contains only ready roots, highest priority first."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("alpha", lambda: None, None, 5, 0)
        dag.add_node("beta", lambda: None, None, 5, 0)
        dag.add_node("gamma", lambda: None, None, 9, 0)
        dag.add_node("delta", lambda: None, None, 1, 0)
        dag.add_node("epsilon", lambda: None, ["gamma"], 100, 0)
        self.assertEqual(self.sut.next_wave(), ["gamma", "alpha", "beta", "delta"])

    def test_next_wave_returns_empty_list_when_nothing_ready(self) -> None:
        """Verify no wave is produced while the only root is already running."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.assertEqual(self.sut.next_wave(), [])

    def test_next_wave_returns_empty_list_for_empty_graph(self) -> None:
        """Verify an empty graph yields an empty wave."""
        self.assertEqual(self.sut.next_wave(), [])

    def test_mark_running_updates_state(self) -> None:
        """Verify marking a node running records the running state."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.assertEqual(self.sut.get_state("a"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_unblocked_dependent(self) -> None:
        """Verify succeeding a node promotes its dependent to ready and into the next wave."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("b"), NodeState.READY)
        self.assertEqual(self.sut.next_wave(), ["b"])

    def test_mark_succeeded_waits_for_all_dependencies(self) -> None:
        """Verify a dependent is promoted only after every prerequisite has succeeded."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, None, 0, 0)
        dag.add_node("c", lambda: None, ["a", "b"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a", "b"])
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("c"), NodeState.PENDING)
        self.assertEqual(self.sut.next_wave(), ["b"])
        self.sut.mark_running("b")
        self.sut.mark_succeeded("b")
        self.assertEqual(self.sut.get_state("c"), NodeState.READY)
        self.assertEqual(self.sut.next_wave(), ["c"])

    def test_mark_succeeded_preserves_non_pending_dependent(self) -> None:
        """Verify promotion leaves already ready or running dependents in their states."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("b"), NodeState.READY)
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("b"), NodeState.READY)
        self.sut.mark_running("b")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("b"), NodeState.RUNNING)
        self.sut.mark_succeeded("b")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("b"), NodeState.SUCCEEDED)

    def test_mark_failed_fail_fast_cancels_non_terminal_nodes(self) -> None:
        """Verify a fail fast failure cancels every remaining non-terminal node."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("done", lambda: None, None, 9, 0)
        dag.add_node("failing", lambda: None, None, 5, 0)
        dag.add_node("dependent", lambda: None, ["failing"], 1, 0)
        self.assertEqual(self.sut.next_wave(), ["done", "failing"])
        self.sut.mark_running("done")
        self.sut.mark_succeeded("done")
        self.sut.mark_running("failing")
        self.sut.mark_failed("failing", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.sut.get_state("done"), NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("failing"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("dependent"), NodeState.CANCELLED)
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """Verify the skip downstream policy marks all transitive dependents as skipped."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        dag.add_node("c", lambda: None, ["b"], 0, 0)
        dag.add_node("d", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a", "d"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("d"), NodeState.READY)
        self.assertFalse(self.sut.is_finished())
        self.assertEqual(self.sut.next_wave(), ["d"])

    def test_mark_failed_skip_downstream_handles_diamond_reconvergence(self) -> None:
        """Verify a diamond reconvergence skips each transitive dependent exactly once."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        dag.add_node("c", lambda: None, ["a"], 0, 0)
        dag.add_node("d", lambda: None, ["b", "c"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("d"), NodeState.SKIPPED)
        states = self.sut.get_all_states()
        self.assertEqual(set(states), {"a", "b", "c", "d"})
        self.assertEqual(len(states), 4)
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_skip_downstream_preserves_terminal_dependent(self) -> None:
        """Verify an already skipped dependent stays unchanged when another upstream fails."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        dag.add_node("c", lambda: None, ["a"], 0, 0)
        dag.add_node("d", lambda: None, ["b", "c"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("b"), NodeState.READY)
        self.assertEqual(self.sut.get_state("c"), NodeState.READY)
        self.sut.mark_running("b")
        self.sut.mark_failed("b", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("d"), NodeState.SKIPPED)
        self.sut.mark_running("c")
        self.sut.mark_failed("c", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("b"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("c"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("d"), NodeState.SKIPPED)

    def test_mark_failed_continue_on_error_keeps_independent_nodes_runnable(self) -> None:
        """Verify the continue on error policy skips blocked dependents but keeps independent work."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        dag.add_node("d", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a", "d"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sut.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("d"), NodeState.READY)
        self.assertFalse(self.sut.is_finished())
        self.assertEqual(self.sut.next_wave(), ["d"])
        self.sut.mark_running("d")
        self.sut.mark_succeeded("d")
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_continue_on_error_skips_shared_dependent_once(self) -> None:
        """Verify a dependent shared by two failed nodes is skipped exactly once."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("b", lambda: None, None, 0, 0)
        dag.add_node("c", lambda: None, None, 0, 0)
        dag.add_node("d", lambda: None, ["b", "c"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["b", "c"])
        self.sut.mark_running("b")
        self.sut.mark_failed("b", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sut.get_state("d"), NodeState.SKIPPED)
        self.sut.mark_running("c")
        self.sut.mark_failed("c", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sut.get_state("b"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("c"), NodeState.FAILED)
        self.assertEqual(self.sut.get_state("d"), NodeState.SKIPPED)
        self.assertTrue(self.sut.is_finished())

    def test_get_state_initializes_root_and_non_root_states(self) -> None:
        """Verify state queries lazily initialize roots as ready and dependents as pending."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(self.sut.get_state("a"), NodeState.READY)
        self.assertEqual(self.sut.get_state("b"), NodeState.PENDING)

    def test_get_state_unknown_node_raises_error(self) -> None:
        """Verify querying the state of an unregistered node reports a missing node error."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.get_state("ghost")

    def test_get_all_states_reports_every_registered_node(self) -> None:
        """Verify the full state mapping covers every registered node with initial states."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        states = self.sut.get_all_states()
        self.assertEqual(set(states), {"a", "b"})
        self.assertEqual(states["a"], NodeState.READY)
        self.assertEqual(states["b"], NodeState.PENDING)

    def test_is_finished_false_until_every_node_terminal(self) -> None:
        """Verify completion is reported only after every node reaches a terminal state."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertFalse(self.sut.is_finished())
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_succeeded("a")
        self.assertFalse(self.sut.is_finished())
        self.assertEqual(self.sut.next_wave(), ["b"])
        self.sut.mark_running("b")
        self.sut.mark_succeeded("b")
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_false_while_node_running(self) -> None:
        """Verify a node still executing keeps the scheduler unfinished."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.assertFalse(self.sut.is_finished())

    def test_is_finished_true_for_empty_graph(self) -> None:
        """Verify an empty graph is already finished."""
        self.assertTrue(self.sut.is_finished())
        self.assertEqual(set(self.sut.get_all_states()), set())

    def test_is_finished_true_after_downstream_skipped(self) -> None:
        """Verify a failure whose dependents are skipped finishes the scheduler."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, None, 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertTrue(self.sut.is_finished())


class DAGRunnerTest(LifecycleTestCase):
    """Unit tests for sequential execution, retries, and consolidated run reports."""

    target = DAGRunnerTarget

    def test_run_executes_nodes_in_dependency_order_and_reports_success(self) -> None:
        """Verify a dependency chain executes in order and yields a fully successful report."""
        dag = self.get_singleton(DAGTarget)
        calls: list[str] = []

        def first() -> str:
            calls.append("first")
            return "first-value"

        def second() -> str:
            calls.append("second")
            return "second-value"

        dag.add_node("first", first, None, 0, 0)
        dag.add_node("second", second, ["first"], 0, 0)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"first", "second"})
        self.assertEqual(set(report.results), {"first", "second"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(tuple(report.critical_path), ("first", "second"))
        self.assertEqual(report.results["first"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["first"].value, "first-value")
        self.assertEqual(report.results["second"].value, "second-value")
        self.assertEqual(report.results["first"].retries_attempted, 0)
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertGreaterEqual(report.results["first"].duration_seconds, 0.0)

    def test_run_retries_flaky_action_until_success(self) -> None:
        """Verify a flaky action is retried up to the configured retry count and then recorded."""
        dag = self.get_singleton(DAGTarget)
        attempts: list[int] = []

        def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient")
            return "recovered"

        dag.add_node("flaky", flaky, None, 0, 2)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(set(report.succeeded_nodes), {"flaky"})
        self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["flaky"].value, "recovered")
        self.assertEqual(report.results["flaky"].retries_attempted, 2)

    def test_run_records_failure_after_retries_exhausted(self) -> None:
        """Verify an action that always fails is retried fully and recorded as failed."""
        dag = self.get_singleton(DAGTarget)
        calls: list[int] = []

        def broken() -> None:
            calls.append(1)
            raise RuntimeError("boom")

        dag.add_node("broken", broken, None, 0, 2)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(len(calls), 3)
        self.assertEqual(set(report.failed_nodes), {"broken"})
        self.assertEqual(report.results["broken"].state, NodeState.FAILED)
        self.assertEqual(report.results["broken"].retries_attempted, 2)
        self.assertIsNotNone(report.results["broken"].error)

    def test_run_fail_fast_cancels_unexecuted_dependents(self) -> None:
        """Verify a fail fast failure cancels dependents without executing them."""
        dag = self.get_singleton(DAGTarget)
        calls: list[str] = []

        def failing() -> None:
            calls.append("root")
            raise RuntimeError("boom")

        def child() -> None:
            calls.append("child")

        dag.add_node("root", failing, None, 0, 0)
        dag.add_node("child", child, ["root"], 0, 0)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(calls, ["root"])
        self.assertEqual(set(report.failed_nodes), {"root"})
        self.assertEqual(set(report.cancelled_nodes), {"child"})
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.results["child"].state, NodeState.CANCELLED)
        self.assertIsNone(report.results["child"].value)

    def test_run_fail_fast_halts_remaining_wave_nodes(self) -> None:
        """Verify a fail fast failure prevents the rest of the current wave from executing."""
        dag = self.get_singleton(DAGTarget)
        calls: list[str] = []

        def failing() -> None:
            calls.append("first")
            raise RuntimeError("boom")

        def second() -> None:
            calls.append("second")

        dag.add_node("first", failing, None, 5, 0)
        dag.add_node("second", second, None, 1, 0)
        report = self.sut.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(calls, ["first"])
        self.assertEqual(set(report.failed_nodes), {"first"})
        self.assertIn("second", report.cancelled_nodes)

    def test_run_skip_downstream_marks_transitive_dependents_skipped(self) -> None:
        """Verify the skip downstream policy skips all transitive dependents of a failed node."""
        dag = self.get_singleton(DAGTarget)
        calls: list[str] = []

        def failing() -> None:
            calls.append("a")
            raise RuntimeError("boom")

        def dependent() -> None:
            calls.append("dependent")

        dag.add_node("a", failing, None, 0, 0)
        dag.add_node("b", dependent, ["a"], 0, 0)
        dag.add_node("c", dependent, ["b"], 0, 0)
        report = self.sut.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(calls, ["a"])
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(set(report.skipped_nodes), {"b", "c"})
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.results["b"].state, NodeState.SKIPPED)
        self.assertEqual(report.results["c"].state, NodeState.SKIPPED)
        self.assertIsNone(report.results["b"].value)

    def test_run_continue_on_error_executes_independent_nodes(self) -> None:
        """Verify the continue on error policy still executes independent nodes."""
        dag = self.get_singleton(DAGTarget)
        calls: list[str] = []

        def failing() -> None:
            calls.append("a")
            raise RuntimeError("boom")

        def blocked() -> None:
            calls.append("b")

        def independent() -> str:
            calls.append("d")
            return "done"

        dag.add_node("a", failing, None, 0, 0)
        dag.add_node("b", blocked, ["a"], 0, 0)
        dag.add_node("d", independent, None, 0, 0)
        report = self.sut.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(set(calls), {"a", "d"})
        self.assertNotIn("b", calls)
        self.assertEqual(set(report.succeeded_nodes), {"d"})
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(set(report.skipped_nodes), {"b"})
        self.assertEqual(report.results["b"].state, NodeState.SKIPPED)

    def test_run_stops_on_stalled_wave_with_unfinished_node(self) -> None:
        """Verify execution halts on an empty wave while an unfinished node remains pending."""
        dag = self.get_singleton(DAGTarget)
        scheduler = self.get_singleton(WaveSchedulerTarget)
        calls: list[str] = []

        def first() -> None:
            calls.append("first")

        def second() -> None:
            calls.append("second")

        dag.add_node("first", first, None, 0, 0)
        scheduler.mark_succeeded("first")
        dag.add_node("second", second, ["first"], 0, 0)
        report = self.sut.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(calls, [])
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertNotIn("second", report.succeeded_nodes)

    def test_run_cycle_raises_cycle_error(self) -> None:
        """Verify executing a cyclic graph reports a cycle error before running any node."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, ["b"], 0, 0)
        dag.add_node("b", lambda: None, ["a"], 0, 0)
        with self.assertRaises(CycleError):
            self.sut.run(FailurePolicy.FAIL_FAST)

    def test_run_missing_dependency_raises_error(self) -> None:
        """Verify executing a graph with an unknown dependency reports a missing node error."""
        dag = self.get_singleton(DAGTarget)
        dag.add_node("a", lambda: None, ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.sut.run(FailurePolicy.FAIL_FAST)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T01:02:34Z
# LAST_CHANGED: 2026-11-12T00:58:25Z
# CHANGE: Add branch-coverage tests for the seven reported gaps: empty-graph critical path returns an empty path with zero weight; repeated dependent promotion preserves already ready, running, and succeeded states; skip-downstream diamond reconvergence skips each transitive dependent once while an already skipped dependent stays unchanged; continue-on-error with two failed upstreams skips the shared dependent exactly once; node removal clears its scheduler state without re-registration; and the runner halts execution on an empty wave while a pending node with succeeded upstream remains.
# COVERAGE_AUDIT: 2026-11-12T01:02:34Z
# QA_AUDIT: 2026-11-12T01:02:18Z
# --- END AUTOFAB METADATA ---
