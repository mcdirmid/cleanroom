from __future__ import annotations

import threading
import time
import unittest
from typing import Any, List, Optional, Sequence, Tuple

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from benchmarks.parts.dag_engine.lib import dag_engine
from benchmarks.parts.dag_engine.lib.dag_engine_impl import DAG, DAGRunner, WaveScheduler, __initialize__


def _noop_action() -> None:
    """Zero-argument node action used when the action body is irrelevant."""
    return None


def _make_registry() -> LifecycleRegistry:
    """Creates an isolated lifecycle registry initialized with the target module."""
    registry = LifecycleRegistry()
    __initialize__(registry)
    return registry


def _populate(dag: DAG, specifications: Sequence[Tuple[str, Sequence[str], int]]) -> None:
    """Registers nodes described by (node_id, dependencies, priority) tuples."""
    for node_id, dependencies, priority in specifications:
        dag.add_node(node_id, _noop_action, dependencies=dependencies, priority=priority)


class DAGTest(unittest.TestCase):
    """Verifies the dag_engine.DAG postconditions declared in low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = _make_registry()

    def test_add_node_registers_definition(self) -> None:
        # POSTCONDITIONS: MUST register the node definition into the graph.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("alpha", _noop_action)
            self.assertTrue(dag.has_node("alpha"))
            self.assertEqual(dag.all_nodes(), {"alpha"})
            definition = dag.get_node("alpha")
            self.assertEqual(definition.node_id, "alpha")
            self.assertIs(definition.action, _noop_action)
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 0)
            self.assertIsNone(definition.timeout_seconds)
            self.assertEqual(definition.retries, 0)
            self.assertEqual(dag.get_dependencies("alpha"), set())
            self.assertEqual(dag.get_dependents("alpha"), set())

    def test_add_node_with_dependencies_registers_edges(self) -> None:
        # POSTCONDITIONS: WHEN dependencies are provided, MUST add directed
        # dependency edges from each dependency to node_id.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop_action)
            dag.add_node(
                "child",
                _noop_action,
                dependencies=["root"],
                priority=3,
                timeout_seconds=2.5,
                retries=1,
            )
            definition = dag.get_node("child")
            self.assertEqual(definition.dependencies, frozenset({"root"}))
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.timeout_seconds, 2.5)
            self.assertEqual(definition.retries, 1)
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"child"})

    def test_add_edge_establishes_dependency(self) -> None:
        # POSTCONDITIONS: MUST establish a directed dependency edge from
        # upstream_id to downstream_id.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop_action)
            dag.add_node("downstream", _noop_action)
            dag.add_edge("upstream", "downstream")
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})
            self.assertIsNone(dag.validate())

    def test_add_edge_missing_nodes_raise_node_not_found(self) -> None:
        # POSTCONDITIONS: WHEN upstream_id or downstream_id does not exist,
        # MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("known", _noop_action)
            with self.assertRaises(dag_engine.NodeNotFoundError) as context:
                dag.add_edge("known", "ghost")
            self.assertEqual(context.exception.node_id, "ghost")
            self.assertTrue(context.exception.message)
            with self.assertRaises(dag_engine.NodeNotFoundError) as upstream_context:
                dag.add_edge("ghost", "known")
            self.assertEqual(upstream_context.exception.node_id, "ghost")

    def test_remove_node_removes_incident_edges(self) -> None:
        # POSTCONDITIONS: MUST remove the node and its incident edges.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", ["a"], 0)])
            dag.remove_node("a")
            self.assertFalse(dag.has_node("a"))
            self.assertEqual(dag.all_nodes(), {"b", "c"})
            self.assertEqual(dag.get_dependencies("b"), set())
            self.assertEqual(dag.get_dependencies("c"), set())
            self.assertEqual(dag.get_dependents("b"), set())
            self.assertEqual(dag.find_roots(), {"b", "c"})

    def test_remove_node_missing_raises_node_not_found(self) -> None:
        # POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine.NodeNotFoundError) as context:
                dag.remove_node("absent")
            self.assertEqual(context.exception.node_id, "absent")

    def test_missing_node_queries_raise_node_not_found(self) -> None:
        # POSTCONDITIONS: WHEN node_id is absent, get_node, get_dependencies,
        # and get_dependents MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("absent"))
            self.assertEqual(dag.all_nodes(), set())
            with self.assertRaises(dag_engine.NodeNotFoundError) as node_context:
                dag.get_node("absent")
            self.assertEqual(node_context.exception.node_id, "absent")
            with self.assertRaises(dag_engine.NodeNotFoundError) as dependency_context:
                dag.get_dependencies("absent")
            self.assertEqual(dependency_context.exception.node_id, "absent")
            with self.assertRaises(dag_engine.NodeNotFoundError) as dependent_context:
                dag.get_dependents("absent")
            self.assertEqual(dependent_context.exception.node_id, "absent")

    def test_returned_collections_are_copies(self) -> None:
        # POSTCONDITIONS: get_dependencies, get_dependents, and all_nodes MUST
        # return copies so that caller mutations do not corrupt the graph.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0)])
            dependencies = dag.get_dependencies("b")
            dependencies.add("injected")
            self.assertEqual(dag.get_dependencies("b"), {"a"})
            dependents = dag.get_dependents("a")
            dependents.add("injected")
            self.assertEqual(dag.get_dependents("a"), {"b"})
            nodes = dag.all_nodes()
            nodes.add("injected")
            self.assertEqual(dag.all_nodes(), {"a", "b"})
            self.assertFalse(dag.has_node("injected"))

    def test_validate_accepts_consistent_acyclic_graph(self) -> None:
        # POSTCONDITIONS: WHEN all referenced nodes exist and no cycle exists,
        # MUST complete without error.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", ["b"], 0)])
            self.assertIsNone(dag.validate())

    def test_validate_missing_dependency_raises_node_not_found(self) -> None:
        # POSTCONDITIONS: WHEN a dependency node is missing, MUST raise
        # NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("child", _noop_action, dependencies=["ghost"])
            with self.assertRaises(dag_engine.NodeNotFoundError) as context:
                dag.validate()
            self.assertEqual(context.exception.node_id, "ghost")
            self.assertTrue(context.exception.message)

    def test_validate_detects_cycle(self) -> None:
        # POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError containing
        # the cycle sequence.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", [], 0)])
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine.CycleError) as context:
                dag.validate()
            self.assertEqual(set(context.exception.cycle), {"a", "b"})
            self.assertTrue(context.exception.message)

    def test_topological_sort_places_prerequisites_first(self) -> None:
        # POSTCONDITIONS: MUST return a valid topological ordering where every
        # prerequisite precedes its dependents.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", ["a"], 0), ("d", ["b", "c"], 0)])
            order = dag.topological_sort()
            self.assertEqual(sorted(order), ["a", "b", "c", "d"])
            self.assertEqual(len(order), 4)
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("a"), order.index("c"))
            self.assertLess(order.index("b"), order.index("d"))
            self.assertLess(order.index("c"), order.index("d"))

    def test_topological_sort_breaks_ties_by_priority_then_name(self) -> None:
        # POSTCONDITIONS: MUST break ties between concurrent ready nodes using
        # priority descending and name ascending.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(
                dag,
                [
                    ("zulu", [], 5),
                    ("mike", [], 5),
                    ("bravo", [], 0),
                    ("alpha", [], 0),
                ],
            )
            self.assertEqual(dag.topological_sort(), ["mike", "zulu", "alpha", "bravo"])

    def test_topological_sort_raises_on_cycle(self) -> None:
        # POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", [], 0)])
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine.CycleError) as context:
                dag.topological_sort()
            self.assertEqual(set(context.exception.cycle), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        # Returns root nodes with in-degree zero and leaf nodes with
        # out-degree zero.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", ["b"], 0), ("d", [], 0)])
            self.assertEqual(dag.find_roots(), {"a", "d"})
            self.assertEqual(dag.find_leaves(), {"c", "d"})

    def test_compute_critical_path_default_weights(self) -> None:
        # POSTCONDITIONS: MUST return the sequence of nodes forming the longest
        # path and its cumulative weight; weights default to 1.0 per node.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", ["b"], 0)])
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(weight, 3.0)
            empty_path, empty_weight = dag.compute_critical_path({})
            self.assertEqual(empty_path, ["a", "b", "c"])
            self.assertEqual(empty_weight, 3.0)

    def test_compute_critical_path_honors_weighted_branch(self) -> None:
        # POSTCONDITIONS: MUST return the longest weighted dependency path where
        # omitted durations default to 1.0.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(
                dag,
                [
                    ("a", [], 0),
                    ("b", ["a"], 0),
                    ("c", ["a"], 0),
                    ("d", ["b", "c"], 0),
                ],
            )
            path, weight = dag.compute_critical_path({"b": 5.0})
            self.assertEqual(path, ["a", "b", "d"])
            self.assertEqual(weight, 7.0)

    def test_remove_node_with_upstream_dependencies_detaches_all_edges(self) -> None:
        # POSTCONDITIONS: MUST remove the node and every incident edge, including
        # the edges to its own upstream dependencies. Detaching b's edges leaves
        # both a and c with in-degree zero (roots) and out-degree zero (leaves).
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", ["b"], 0)])
            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())
            self.assertEqual(dag.find_roots(), {"a", "c"})
            self.assertEqual(dag.find_leaves(), {"a", "c"})
            self.assertIsNone(dag.validate())

    def test_compute_critical_path_empty_graph_returns_empty_path(self) -> None:
        # POSTCONDITIONS: the longest path over a graph with no nodes is the
        # empty sequence with zero cumulative weight.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    def test_compute_critical_path_equal_weight_chains_are_deterministic(self) -> None:
        # POSTCONDITIONS: rival equal-weight dependency chains select the same
        # maximum-weight path deterministically across repeated calls.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", ["a"], 0), ("c", [], 0), ("d", ["c"], 0)])
            first_path, first_weight = dag.compute_critical_path()
            second_path, second_weight = dag.compute_critical_path()
            self.assertEqual(first_path, second_path)
            self.assertEqual(first_weight, second_weight)
            self.assertEqual(first_weight, 2.0)
            self.assertIn(first_path, (["a", "b"], ["c", "d"]))

    def test_compute_critical_path_equal_weight_prerequisites_pick_shared_maximum(self) -> None:
        # POSTCONDITIONS: prerequisites with equal cumulative weight share the
        # maximum path weight, and the selected path is deterministic.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(
                dag, [("alpha", [], 0), ("mike", [], 0), ("sink", ["alpha", "mike"], 0)]
            )
            first_path, first_weight = dag.compute_critical_path()
            second_path, second_weight = dag.compute_critical_path()
            self.assertEqual(first_path, second_path)
            self.assertEqual(first_weight, 2.0)
            self.assertEqual(second_weight, 2.0)
            self.assertIn(first_path, (["alpha", "sink"], ["mike", "sink"]))

    def test_compute_critical_path_picks_heavier_prerequisite_not_first_by_id(self) -> None:
        # POSTCONDITIONS: cumulative weight is maximized even when the heavier
        # prerequisite sorts after the lighter one by node identifier.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            _populate(
                dag, [("alpha", [], 0), ("zulu", [], 0), ("sink", ["alpha", "zulu"], 0)]
            )
            path, weight = dag.compute_critical_path({"zulu": 5.0})
            self.assertEqual(path, ["zulu", "sink"])
            self.assertEqual(weight, 6.0)


class WaveSchedulerTest(unittest.TestCase):
    """Verifies the dag_engine.WaveScheduler postconditions declared in low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = _make_registry()

    def _scheduler_with(
        self, scope: LifecycleScope, specifications: Sequence[Tuple[str, Sequence[str], int]]
    ) -> WaveScheduler:
        dag = scope.get_singleton(DAG)
        _populate(dag, specifications)
        return scope.get_singleton(WaveScheduler)

    def test_initial_states_assign_ready_to_roots(self) -> None:
        # GROUNDING: on initialization, root nodes become READY and remaining
        # nodes become PENDING.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [("root", [], 0), ("child", ["root"], 0), ("grand", ["child"], 0)],
            )
            self.assertEqual(
                dict(scheduler.get_all_states()),
                {
                    "root": dag_engine.NodeState.READY,
                    "child": dag_engine.NodeState.PENDING,
                    "grand": dag_engine.NodeState.PENDING,
                },
            )
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.READY)

    def test_next_wave_orders_by_priority_then_id(self) -> None:
        # POSTCONDITIONS: MUST order returned nodes by priority descending, then
        # node_id ascending.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [("root", [], 0), ("high", [], 10), ("low", [], -5), ("child", ["root"], 0)],
            )
            self.assertEqual(scheduler.next_wave(), ["high", "root", "low"])

    def test_next_wave_returns_empty_when_no_node_ready(self) -> None:
        # POSTCONDITIONS: WHEN no nodes are ready, MUST return an empty list.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(scope, [("root", [], 0), ("high", [], 0)])
            scheduler.mark_running("root")
            scheduler.mark_running("high")
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(
                scheduler.get_state("high"), dag_engine.NodeState.RUNNING
            )

    def test_mark_running_transitions_state(self) -> None:
        # POSTCONDITIONS: MUST update the node state to RUNNING.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(scope, [("root", [], 0)])
            self.assertIsNone(scheduler.mark_running("root"))
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.RUNNING)
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_succeeded_promotes_unblocked_dependents(self) -> None:
        # POSTCONDITIONS: MUST update the node state to SUCCEEDED and evaluate
        # downstream dependents, promoting newly unblocked nodes to READY.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [
                    ("a", [], 0),
                    ("b", ["a"], 1),
                    ("c", ["a"], 2),
                    ("d", ["b", "c"], 0),
                ],
            )
            self.assertIsNone(scheduler.mark_succeeded("a"))
            self.assertEqual(scheduler.get_state("a"), dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("b"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("c"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("d"), dag_engine.NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["c", "b"])
            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("d"), dag_engine.NodeState.PENDING)
            scheduler.mark_succeeded("c")
            self.assertEqual(scheduler.get_state("d"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["d"])

    def test_is_finished_until_all_nodes_terminal(self) -> None:
        # POSTCONDITIONS: is_finished reports whether every node reached a
        # terminal state.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(scope, [("a", [], 0), ("b", ["a"], 0)])
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())

    def test_get_all_states_returns_snapshot_copy(self) -> None:
        # GROUNDING: get_all_states returns a shallow copy of the states mapping.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(scope, [("root", [], 0), ("child", ["root"], 0)])
            before = scheduler.get_all_states()
            self.assertEqual(set(before.keys()), {"root", "child"})
            scheduler.mark_running("root")
            after = scheduler.get_all_states()
            self.assertEqual(before["root"], dag_engine.NodeState.READY)
            self.assertEqual(after["root"], dag_engine.NodeState.RUNNING)

    def test_mark_failed_transitions_state(self) -> None:
        # POSTCONDITIONS: MUST update the node state to FAILED.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(scope, [("only", [], 0)])
            self.assertIsNone(scheduler.mark_failed("only"))
            self.assertEqual(scheduler.get_state("only"), dag_engine.NodeState.FAILED)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(
                dict(scheduler.get_all_states()),
                {"only": dag_engine.NodeState.FAILED},
            )

    def test_mark_succeeded_leaves_non_pending_dependents_unchanged(self) -> None:
        # POSTCONDITIONS: only dependents currently in PENDING are promoted to
        # READY once all of their upstream dependencies have succeeded.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope, [("a", [], 0), ("b", [], 0), ("target", ["a", "b"], 0)]
            )
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("target"), dag_engine.NodeState.PENDING)
            scheduler.mark_running("target")
            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("target"), dag_engine.NodeState.RUNNING)
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        # POSTCONDITIONS: WHEN failure policy is SKIP_DOWNSTREAM, MUST transition
        # all transitive dependents to SKIPPED.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [("a", [], 0), ("b", ["a"], 0), ("c", ["b"], 0), ("independent", [], 0)],
            )
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            scheduler.mark_failed("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent"), dag_engine.NodeState.READY)

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        # POSTCONDITIONS: WHEN failure policy is FAIL_FAST, MUST transition all
        # remaining non-terminal nodes to CANCELLED.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [("a", [], 0), ("b", ["a"], 0), ("c", ["b"], 0), ("independent", [], 0)],
            )
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.FAIL_FAST)
            scheduler.mark_failed("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine.NodeState.FAILED)
            for node_id in ("b", "c", "independent"):
                self.assertEqual(
                    scheduler.get_state(node_id), dag_engine.NodeState.CANCELLED
                )
            self.assertTrue(scheduler.is_finished())

    def test_get_all_states_tracks_nodes_added_and_removed_after_initialization(self) -> None:
        # POSTCONDITIONS: get_all_states reports the execution state of every
        # node currently present in the graph.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop_action)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("late", _noop_action, dependencies=["root"])
            states = scheduler.get_all_states()
            self.assertEqual(set(states.keys()), {"root", "late"})
            self.assertIn(
                states["late"],
                (dag_engine.NodeState.PENDING, dag_engine.NodeState.READY),
            )
            dag.remove_node("late")
            self.assertEqual(set(scheduler.get_all_states().keys()), {"root"})

    def test_get_all_states_reports_late_dependency_free_node_ready(self) -> None:
        # POSTCONDITIONS: a dependency-free node registered after scheduler
        # initialization is reported READY by get_all_states.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop_action)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("late_root", _noop_action)
            states = scheduler.get_all_states()
            self.assertIn("late_root", states)
            self.assertEqual(states["late_root"], dag_engine.NodeState.READY)
            self.assertIn("late_root", scheduler.next_wave())

    def test_mark_failed_skip_downstream_covers_multiple_paths(self) -> None:
        # POSTCONDITIONS: WHEN failure policy is SKIP_DOWNSTREAM, transitive
        # dependents reachable over several dependency paths are all SKIPPED.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [
                    ("a", [], 0),
                    ("b", ["a"], 0),
                    ("c", ["a"], 0),
                    ("sink", ["b", "c"], 0),
                ],
            )
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            scheduler.mark_failed("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine.NodeState.FAILED)
            for node_id in ("b", "c", "sink"):
                self.assertEqual(
                    scheduler.get_state(node_id), dag_engine.NodeState.SKIPPED
                )

    def test_mark_failed_skip_downstream_preserves_terminal_dependents(self) -> None:
        # POSTCONDITIONS: WHEN failure policy is SKIP_DOWNSTREAM, dependents that
        # already occupy a terminal state MUST keep that state.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = self._scheduler_with(
                scope,
                [("a", [], 0), ("terminal", ["a"], 0), ("tail", ["terminal"], 0)],
            )
            scheduler.mark_succeeded("terminal")
            self.assertEqual(scheduler.get_state("tail"), dag_engine.NodeState.READY)
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            scheduler.mark_failed("a")
            self.assertEqual(
                scheduler.get_state("terminal"), dag_engine.NodeState.SUCCEEDED
            )
            self.assertEqual(scheduler.get_state("tail"), dag_engine.NodeState.SKIPPED)


class DAGRunnerTest(unittest.TestCase):
    """Verifies the dag_engine.DAGRunner postconditions declared in low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = _make_registry()

    def _run_tolerating_cancellation(
        self, runner: DAGRunner
    ) -> Tuple[Optional[dag_engine.DAGRunReport], bool]:
        """Runs the DAG, accepting either a report or DAGCancelledError."""
        try:
            return runner.run(), False
        except dag_engine.DAGCancelledError:
            return None, True

    def test_run_executes_dependencies_in_order_and_reports_success(self) -> None:
        # POSTCONDITIONS: MUST execute ready nodes, return a DAGRunReport
        # capturing all node states, durations, and the critical path.
        executed: List[str] = []

        def make_action(node_id: str, value: int) -> Any:
            def action() -> int:
                executed.append(node_id)
                return value

            return action

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", make_action("a", 1))
            dag.add_node("b", make_action("b", 2), dependencies=["a"])
            dag.add_node("c", make_action("c", 3), dependencies=["b"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(executed, ["a", "b", "c"])
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
            self.assertEqual(list(report.failed_nodes), [])
            self.assertEqual(list(report.skipped_nodes), [])
            self.assertEqual(list(report.cancelled_nodes), [])
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(list(report.critical_path), ["a", "b", "c"])
            self.assertEqual(set(report.results.keys()), {"a", "b", "c"})
            for node_id in ("a", "b", "c"):
                self.assertEqual(report.results[node_id].state, dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(report.results["c"].value, 3)

    def test_run_reports_failed_node_without_raising(self) -> None:
        # POSTCONDITIONS: MUST record a FAILED NodeResult for a raising action.
        def failing_action() -> None:
            raise ValueError("kaboom")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("boom", failing_action)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(report.total_nodes, 1)
            self.assertEqual(list(report.failed_nodes), ["boom"])
            self.assertEqual(list(report.succeeded_nodes), [])
            self.assertIn("boom", report.results)
            result = report.results["boom"]
            self.assertEqual(result.state, dag_engine.NodeState.FAILED)
            self.assertIsInstance(result.error, Exception)

    def test_run_retries_failing_action_up_to_configured_count(self) -> None:
        # POSTCONDITIONS: MUST execute retries up to the configured retry count
        # for failed node actions.
        attempts = 0

        def failing_action() -> None:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("still failing")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", failing_action, retries=2)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(list(report.failed_nodes), ["flaky"])
            result = report.results["flaky"]
            self.assertEqual(result.state, dag_engine.NodeState.FAILED)
            self.assertGreaterEqual(attempts, 2)
            self.assertLessEqual(attempts, 3)
            self.assertGreaterEqual(result.retries_attempted, 1)
            self.assertLessEqual(result.retries_attempted, 2)

    def test_run_succeeds_after_retry(self) -> None:
        # POSTCONDITIONS: MUST execute retries for failed actions, allowing a
        # later successful attempt to record SUCCEEDED.
        attempts = 0

        def flaky_action() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("transient")
            return "recovered"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", flaky_action, retries=2)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(set(report.succeeded_nodes), {"flaky"})
            self.assertEqual(list(report.failed_nodes), [])
            result = report.results["flaky"]
            self.assertEqual(result.state, dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(result.value, "recovered")
            self.assertIsNone(result.error)

    def test_run_raises_timeout_when_execution_exceeds_deadline(self) -> None:
        # POSTCONDITIONS: WHEN execution exceeds timeout_seconds between waves,
        # MUST raise DAGTimeoutError before dispatching the blocked dependent.
        def slow_action() -> str:
            time.sleep(0.2)
            return "slow"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow_action)
            dag.add_node("after", _noop_action, dependencies=["slow"])
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.02)

    def test_run_validates_graph_before_executing_cycle(self) -> None:
        # POSTCONDITIONS: validation failures raise immediately from run().
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            _populate(dag, [("a", [], 0), ("b", [], 0)])
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.CycleError):
                runner.run()

    def test_run_validates_graph_before_executing_missing_dependency(self) -> None:
        # POSTCONDITIONS: WHEN a dependency node is missing, run() raises
        # NodeNotFoundError during validation.
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("child", _noop_action, dependencies=["ghost"])
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.NodeNotFoundError) as context:
                runner.run()
            self.assertEqual(context.exception.node_id, "ghost")

    def test_cancel_during_execution_aborts_downstream_nodes(self) -> None:
        # POSTCONDITIONS: cancel() MUST set cancellation status and abort
        # subsequent wave execution.
        started = threading.Event()
        release = threading.Event()
        executed: List[str] = []
        outcomes: List[Optional[BaseException]] = []
        reports: List[dag_engine.DAGRunReport] = []

        def slow_action() -> str:
            executed.append("slow")
            started.set()
            release.wait(timeout=5.0)
            return "slow"

        def downstream_action() -> None:
            executed.append("after")

        def run_in_thread() -> None:
            try:
                reports.append(runner.run())
                outcomes.append(None)
            except BaseException as error:  # noqa: BLE001 - forwarded to the test thread
                outcomes.append(error)

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow_action)
            dag.add_node("after", downstream_action, dependencies=["slow"])
            runner = scope.get_singleton(DAGRunner)
            worker = threading.Thread(target=run_in_thread, daemon=True)
            worker.start()
            self.assertTrue(started.wait(timeout=5.0))
            runner.cancel()
            release.set()
            worker.join(timeout=5.0)
            self.assertFalse(worker.is_alive())
            # Downstream wave execution must be aborted by cancellation.
            self.assertEqual(executed, ["slow"])
            cancelled = any(
                isinstance(outcome, dag_engine.DAGCancelledError) for outcome in outcomes
            )
            self.assertTrue(
                cancelled or len(reports) == 1,
                "Expected a DAGCancelledError or a completed DAGRunReport after cancellation",
            )
            if reports:
                self.assertEqual(reports[0].total_nodes, 2)

    def test_run_aborts_when_cancelled_before_execution(self) -> None:
        # POSTCONDITIONS: cancel() MUST abort subsequent wave execution; a run
        # started after cancellation either raises DAGCancelledError or reports
        # the cancelled nodes without executing any action.
        executed: List[str] = []

        def action() -> None:
            executed.append("ran")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action)
            dag.add_node("b", action)
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()
            report, cancelled = self._run_tolerating_cancellation(runner)
            self.assertEqual(executed, [])
            if report is None:
                self.assertTrue(cancelled)
            else:
                self.assertEqual(set(report.cancelled_nodes), {"a", "b"})

    def test_run_stops_between_waves_when_cancelled(self) -> None:
        # POSTCONDITIONS: WHEN cancelled between waves, MUST abort subsequent
        # wave execution so that the next wave's node never runs.
        executed: List[str] = []
        holders: List[DAGRunner] = []

        def cancelling_action() -> str:
            executed.append("a")
            holders[0].cancel()
            return "a"

        def downstream_action() -> None:
            executed.append("b")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", cancelling_action)
            dag.add_node("b", downstream_action, dependencies=["a"])
            runner = scope.get_singleton(DAGRunner)
            holders.append(runner)
            report, cancelled = self._run_tolerating_cancellation(runner)
            self.assertEqual(executed, ["a"])
            if report is None:
                self.assertTrue(cancelled)
            else:
                self.assertIn("b", report.cancelled_nodes)

    def test_run_handles_cancellation_signalled_as_final_wave_drains(self) -> None:
        # POSTCONDITIONS: cancellation signalled while the final wave is running
        # is still honored by raising DAGCancelledError or reporting the run.
        executed: List[str] = []
        holders: List[DAGRunner] = []

        def cancelling_action() -> str:
            executed.append("only")
            holders[0].cancel()
            return "only"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("only", cancelling_action)
            runner = scope.get_singleton(DAGRunner)
            holders.append(runner)
            report, cancelled = self._run_tolerating_cancellation(runner)
            self.assertEqual(executed, ["only"])
            if report is None:
                self.assertTrue(cancelled)
            else:
                self.assertEqual(report.total_nodes, 1)

    def test_run_raises_timeout_after_final_wave_completes(self) -> None:
        # POSTCONDITIONS: WHEN execution exceeds timeout_seconds, MUST raise
        # DAGTimeoutError even when the overrun happens in the final wave.
        def slow_action() -> str:
            time.sleep(0.2)
            return "slow"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow_action)
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.02)

    def test_run_terminates_under_continue_on_error_with_blocked_dependents(self) -> None:
        # POSTCONDITIONS: with CONTINUE_ON_ERROR in effect for the scheduler that
        # actually coordinates the run, a failed prerequisite leaves its dependent
        # unable to become ready; that dependent stays non-terminal while execution
        # still terminates and run returns a report recording the failure.
        executed: List[str] = []

        def failing_action() -> None:
            executed.append("root")
            raise RuntimeError("boom")

        def downstream_action() -> None:
            executed.append("child")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", failing_action)
            dag.add_node("child", downstream_action, dependencies=["root"])
            runner = scope.get_singleton(DAGRunner)
            # The runner builds the scheduler that coordinates its own run; select
            # the contracted CONTINUE_ON_ERROR policy on that exact instance.
            coordinating = getattr(runner, "_scheduler")
            setattr(
                coordinating,
                "_failure_policy",
                dag_engine.FailurePolicy.CONTINUE_ON_ERROR,
            )
            setattr(runner, "_failure_policy", dag_engine.FailurePolicy.CONTINUE_ON_ERROR)
            report = runner.run()
            self.assertIsInstance(report, dag_engine.DAGRunReport)
            self.assertEqual(report.total_nodes, 2)
            self.assertIn("root", report.failed_nodes)
            self.assertEqual(executed, ["root"])
            # The coordinating scheduler recording the root as FAILED proves this
            # instance took part in the run whose report was just returned.
            self.assertEqual(
                coordinating.get_state("root"), dag_engine.NodeState.FAILED
            )
            # CONTINUE_ON_ERROR retains the blocked dependent in a non-terminal
            # state instead of cancelling or skipping it.
            self.assertNotIn(
                coordinating.get_state("child"),
                (
                    dag_engine.NodeState.SUCCEEDED,
                    dag_engine.NodeState.FAILED,
                    dag_engine.NodeState.SKIPPED,
                    dag_engine.NodeState.CANCELLED,
                ),
                "CONTINUE_ON_ERROR must leave the blocked dependent non-terminal",
            )

    def test_run_honors_per_node_action_timeout(self) -> None:
        # POSTCONDITIONS: an action exceeding its declared node timeout yields a
        # recorded failure consistent with its retry count, while independent
        # nodes proceed and run still returns a report.
        slow_attempts: List[str] = []
        executed: List[str] = []

        def slow_action() -> str:
            slow_attempts.append("slow")
            time.sleep(0.12)
            return "slow"

        def quick_action() -> str:
            executed.append("quick")
            return "quick"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow_action, timeout_seconds=0.03, retries=1)
            # Independent, higher-priority node completes before the timed-out
            # node's failure is recorded, so it proceeds under any policy.
            dag.add_node("quick", quick_action, priority=10)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertIsInstance(report, dag_engine.DAGRunReport)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(list(report.failed_nodes), ["slow"])
            self.assertEqual(set(report.succeeded_nodes), {"quick"})
            self.assertEqual(executed, ["quick"])
            result = report.results["slow"]
            self.assertEqual(result.state, dag_engine.NodeState.FAILED)
            self.assertIsNotNone(result.error)
            self.assertGreaterEqual(len(slow_attempts), 2)
            self.assertGreaterEqual(result.retries_attempted, 1)
            self.assertLessEqual(result.retries_attempted, 2)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-21T00:26:26Z
# LAST_CHANGED: 2026-10-21T00:25:40Z
# CHANGE: Target the scheduler instance that actually coordinates the run: after constructing DAGRunner, select CONTINUE_ON_ERROR on getattr(runner, '_scheduler') (the run-coordinating scheduler, documented in low/dag_engine_impl.pyi) and mirror it on the runner; then assert the run terminates and returns the DAGRunReport with root failed, prove participation by observing that same scheduler reports root FAILED, and assert the blocked dependent remains non-terminal instead of being cancelled/skipped. The lifecycle-resolved scheduler is no longer inspected
# COVERAGE_AUDIT: 2026-10-21T00:26:26Z
# QA_AUDIT: 2026-10-21T00:26:03Z
# --- END CLEANROOM METADATA ---
