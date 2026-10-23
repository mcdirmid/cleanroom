"""Contract tests for the synchronous DAG execution and wave scheduling engine.

Derived from ``low/dag_engine_lite.pyi`` and ``low/dag_engine_lite_impl.pyi``.
The implementation classes (DAG, WaveScheduler, DAGRunner) are system-tier
singletons, so every test initializes an isolated registry and exercises the
singletons inside a single system phase scope.
"""

from __future__ import annotations

import unittest
from typing import Dict, List, cast

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

import benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl as impl_module
from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
)


def _noop() -> None:
    """Zero-argument no-op node action used while constructing graphs."""


class DAGTest(unittest.TestCase):
    """Verifies DAG registration, edge management, and graph algorithms."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        impl_module.__initialize__(registry=self.registry)

    def test_add_node_registers_definition(self) -> None:
        # POSTCONDITIONS: add_node MUST register the node definition into the graph.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, priority=3, retries=2)
            self.assertTrue(dag.has_node("a"))
            definition = dag.get_node("a")
            self.assertEqual(definition.node_id, "a")
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.retries, 2)
            self.assertEqual(dag.all_nodes(), {"a"})

    def test_add_node_with_dependencies_registers_edges(self) -> None:
        # POSTCONDITIONS: when dependencies are provided, edges MUST be added.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dag.add_node("downstream", _noop, dependencies=["upstream"])
            self.assertEqual(
                dag.get_node("downstream").dependencies, frozenset({"upstream"})
            )
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_add_node_freezes_dependency_collection(self) -> None:
        # GROUNDING: NodeDefinition is immutable with a frozen dependency set.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dependencies = ["upstream"]
            dag.add_node("downstream", _noop, dependencies=dependencies)
            dependencies.append("ghost")
            self.assertEqual(
                dag.get_node("downstream").dependencies, frozenset({"upstream"})
            )
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})

    def test_add_edge_links_existing_nodes(self) -> None:
        # POSTCONDITIONS: MUST establish a directed dependency edge.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dag.add_node("downstream", _noop)
            dag.add_edge("upstream", "downstream")
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_add_edge_unknown_upstream_raises(self) -> None:
        # POSTCONDITIONS: WHEN a node identifier is missing, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("downstream", _noop)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("ghost", "downstream")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_add_edge_unknown_downstream_raises(self) -> None:
        # POSTCONDITIONS: WHEN a node identifier is missing, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("upstream", "ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_remove_node_detaches_incident_edges(self) -> None:
        # POSTCONDITIONS: MUST remove the node and its incident edges.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])
            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.get_dependencies("c"), set())
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.all_nodes(), {"a", "c"})

    def test_remove_node_unknown_raises(self) -> None:
        # POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.remove_node("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_has_node_reflects_registration(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            self.assertTrue(dag.has_node("a"))
            self.assertFalse(dag.has_node("missing"))

    def test_get_node_unknown_raises(self) -> None:
        # POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_node("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_get_dependencies_unknown_raises(self) -> None:
        # POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_dependencies("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_get_dependents_unknown_raises(self) -> None:
        # POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_dependents("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_all_nodes_returns_copy(self) -> None:
        # GROUNDING: all_nodes returns a copy of set(_nodes.keys()).
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            nodes = dag.all_nodes()
            nodes.add("ghost")
            self.assertEqual(dag.all_nodes(), {"a"})

    def test_get_dependencies_returns_copy(self) -> None:
        # GROUNDING: get_dependencies returns a copy of the upstream set.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dag.add_node("downstream", _noop, dependencies=["upstream"])
            dependencies = dag.get_dependencies("downstream")
            dependencies.add("ghost")
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})

    def test_validate_accepts_consistent_acyclic_graph(self) -> None:
        # POSTCONDITIONS: WHEN all referenced nodes exist and no cycle exists,
        # MUST complete without error.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            dag.add_node("d", _noop, dependencies=["b", "c"])
            self.assertIsNone(dag.validate())

    def test_validate_missing_dependency_raises(self) -> None:
        # POSTCONDITIONS: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, dependencies=["ghost"])
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.validate()
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_validate_cycle_raises_cycle_error(self) -> None:
        # POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError with its sequence.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.validate()
            self.assertIsInstance(ctx.exception.cycle, tuple)
            self.assertEqual(set(ctx.exception.cycle), {"a", "b"})

    def test_topological_sort_breaks_ties_by_priority_then_name(self) -> None:
        # POSTCONDITIONS: ties use priority descending then node_id ascending.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, priority=0)
            dag.add_node("b", _noop, priority=5)
            dag.add_node("c", _noop, priority=5)
            dag.add_node("d", _noop, dependencies=["a"], priority=0)
            self.assertEqual(dag.topological_sort(), ["b", "c", "a", "d"])

    def test_topological_sort_places_prerequisites_first(self) -> None:
        # POSTCONDITIONS: every prerequisite precedes its dependents.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])
            self.assertEqual(dag.topological_sort(), ["a", "b", "c"])

    def test_topological_sort_cycle_raises(self) -> None:
        # POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.topological_sort()
            self.assertEqual(set(ctx.exception.cycle), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        # A diamond graph plus an isolated node: the isolated node is both a root
        # and a leaf.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            dag.add_node("d", _noop, dependencies=["b", "c"])
            dag.add_node("e", _noop)
            self.assertEqual(dag.find_roots(), {"a", "e"})
            self.assertEqual(dag.find_leaves(), {"d", "e"})

    def test_compute_critical_path_selects_longest_weighted_path(self) -> None:
        # POSTCONDITIONS: MUST return the longest path and its cumulative weight.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            dag.add_node("d", _noop, dependencies=["b", "c"])
            path, total = dag.compute_critical_path(
                {"a": 1.0, "b": 5.0, "c": 2.0, "d": 1.0}
            )
            self.assertEqual(path, ["a", "b", "d"])
            self.assertEqual(total, 7.0)

    def test_compute_critical_path_defaults_missing_durations_to_one(self) -> None:
        # POSTCONDITIONS: omitted duration weights default to 1.0.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])
            path, total = dag.compute_critical_path({"b": 5.0})
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(total, 7.0)

    def test_compute_critical_path_single_node(self) -> None:
        # POSTCONDITIONS: a lone node forms the critical path of weight 1.0.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("solo", _noop)
            path, total = dag.compute_critical_path()
            self.assertEqual(path, ["solo"])
            self.assertEqual(total, 1.0)

    def test_validate_cycle_with_acyclic_prerequisite_reports_cycle(self) -> None:
        # POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError containing
        # the cycle sequence even when the cycle is reachable through acyclic
        # prerequisite nodes.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop)
            dag.add_node("a", _noop, dependencies=["root"])
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.validate()
            cycle = ctx.exception.cycle
            self.assertIsInstance(cycle, tuple)
            self.assertEqual(set(cycle), {"a", "b"})
            self.assertNotIn("root", cycle)

    def test_compute_critical_path_empty_graph(self) -> None:
        # POSTCONDITIONS: an empty graph has an empty longest path of weight 0.0.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, total = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(total, 0.0)

    def test_compute_critical_path_resolves_tied_branches(self) -> None:
        # POSTCONDITIONS: several upstream branches may tie on earliest
        # completion time; the returned sequence MUST still be a longest path
        # and the returned weight MUST be its cumulative weight.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            dag.add_node("d", _noop, dependencies=["b", "c"])
            weights = {"a": 1.0, "b": 2.0, "c": 2.0, "d": 1.0}
            path, total = dag.compute_critical_path(weights)
            self.assertIn(path, [["a", "b", "d"], ["a", "c", "d"]])
            self.assertEqual(total, 4.0)
            self.assertEqual(sum(weights[node_id] for node_id in path), 4.0)


class WaveSchedulerTest(unittest.TestCase):
    """Verifies wave selection, node state transitions, and failure policies."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        impl_module.__initialize__(registry=self.registry)

    def test_next_wave_returns_ready_roots_ordered_by_priority(self) -> None:
        # POSTCONDITIONS: ready nodes ordered by priority descending then node_id
        # ascending; non-root nodes with unmet dependencies are excluded.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("alpha", _noop, priority=0)
            dag.add_node("beta", _noop, priority=5)
            dag.add_node("gamma", _noop, priority=5)
            dag.add_node("delta", _noop, dependencies=["alpha"], priority=100)
            self.assertEqual(scheduler.next_wave(), ["beta", "gamma", "alpha"])

    def test_next_wave_returns_empty_for_empty_graph(self) -> None:
        # POSTCONDITIONS: WHEN no nodes are ready, MUST return an empty list.
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), [])

    def test_next_wave_unlocks_dependents_after_success(self) -> None:
        # POSTCONDITIONS: mark_succeeded MUST promote newly unblocked dependents.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_mark_succeeded_waits_for_all_dependencies(self) -> None:
        # POSTCONDITIONS: a dependent only becomes READY once every upstream
        # dependency has SUCCEEDED.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop)
            dag.add_node("c", _noop, dependencies=["a", "b"])
            self.assertEqual(scheduler.next_wave(), ["a", "b"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.PENDING
            )
            self.assertEqual(scheduler.next_wave(), ["b"])
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_mark_running_transitions_node(self) -> None:
        # POSTCONDITIONS: MUST update the node state to RUNNING.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            scheduler.next_wave()
            scheduler.mark_running("a")
            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.RUNNING
            )

    def test_mark_failed_defaults_to_fail_fast(self) -> None:
        # POSTCONDITIONS: default FAIL_FAST transitions remaining PENDING nodes
        # to CANCELLED and leaves the graph finished.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            scheduler.next_wave()
            scheduler.mark_failed("a")
            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.CANCELLED
            )
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.CANCELLED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        # POSTCONDITIONS: SKIP_DOWNSTREAM MUST skip all transitive dependents
        # while leaving independent nodes untouched.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])
            dag.add_node("d", _noop)
            scheduler.next_wave()
            scheduler.mark_failed(
                "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("d"), dag_engine_lite.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())

    def test_mark_failed_skip_downstream_marks_diamond_dependents(self) -> None:
        # POSTCONDITIONS: every transitive dependent MUST be SKIPPED, including
        # a node reachable through more than one dependency chain.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            dag.add_node("d", _noop, dependencies=["b", "c"])
            scheduler.next_wave()
            scheduler.mark_failed(
                "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("d"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_succeeded_does_not_revive_skipped_dependent(self) -> None:
        # POSTCONDITIONS: only a PENDING dependent is promoted to READY when all
        # upstream dependencies succeed; a dependent already SKIPPED by
        # SKIP_DOWNSTREAM MUST stay SKIPPED.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop)
            dag.add_node("c", _noop, dependencies=["a", "b"])
            self.assertEqual(scheduler.next_wave(), ["a", "b"])
            scheduler.mark_failed(
                "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.READY
            )
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_continue_on_error_keeps_independent_nodes(self) -> None:
        # POSTCONDITIONS: CONTINUE_ON_ERROR MUST leave unblocked independent
        # nodes eligible for execution.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop)
            scheduler.next_wave()
            scheduler.mark_failed(
                "a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
            )
            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.PENDING
            )
            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), ["c"])
            scheduler.mark_running("c")
            scheduler.mark_succeeded("c")
            self.assertEqual(scheduler.next_wave(), [])
            self.assertFalse(scheduler.is_finished())

    def test_get_state_initializes_registered_nodes(self) -> None:
        # GROUNDING: get_state synchronizes newly registered nodes, initializing
        # roots to READY and non-roots to PENDING.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.PENDING
            )

    def test_get_all_states_returns_copy(self) -> None:
        # GROUNDING: get_all_states returns a shallow copy of the state mapping.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            states = scheduler.get_all_states()
            self.assertEqual(states["a"], dag_engine_lite.NodeState.READY)
            self.assertEqual(states["b"], dag_engine_lite.NodeState.PENDING)
            mutable = cast(Dict[str, dag_engine_lite.NodeState], states)
            mutable.clear()
            self.assertEqual(len(scheduler.get_all_states()), 2)

    def test_is_finished_true_for_empty_graph(self) -> None:
        # POSTCONDITIONS: WHEN the DAG contains no nodes, MUST return True.
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_until_all_nodes_terminal(self) -> None:
        # POSTCONDITIONS: MUST return False while any node is non-terminal and
        # True once every node is SUCCEEDED.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())


class DAGRunnerTest(unittest.TestCase):
    """Verifies sequential execution, retries, reporting, and failure policies."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        impl_module.__initialize__(registry=self.registry)

    def test_run_success_reports_all_nodes(self) -> None:
        # POSTCONDITIONS: MUST execute ready waves sequentially and return a
        # consolidated report capturing every node outcome and the critical path.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            executed: List[str] = []

            def action_a() -> int:
                executed.append("a")
                return 1

            def action_b() -> int:
                executed.append("b")
                return 2

            def action_c() -> int:
                executed.append("c")
                return 3

            dag.add_node("a", action_a)
            dag.add_node("b", action_b, dependencies=["a"])
            dag.add_node("c", action_c, dependencies=["b"])
            report = runner.run()
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(executed, ["a", "b", "c"])
            self.assertEqual(
                report.results["a"].state, dag_engine_lite.NodeState.SUCCEEDED
            )
            self.assertEqual(
                report.results["b"].state, dag_engine_lite.NodeState.SUCCEEDED
            )
            self.assertEqual(
                report.results["c"].state, dag_engine_lite.NodeState.SUCCEEDED
            )
            self.assertEqual(report.results["a"].value, 1)
            self.assertEqual(report.results["b"].value, 2)
            self.assertEqual(report.results["c"].value, 3)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b", "c"))

    def test_run_retries_failed_action_until_success(self) -> None:
        # POSTCONDITIONS: MUST execute retries up to the configured retry count.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            attempts: List[int] = []

            def flaky() -> str:
                attempts.append(1)
                if len(attempts) < 3:
                    raise RuntimeError("transient")
                return "ok"

            dag.add_node("a", flaky, retries=2)
            report = runner.run()
            self.assertEqual(len(attempts), 3)
            result = report.results["a"]
            self.assertEqual(result.state, dag_engine_lite.NodeState.SUCCEEDED)
            self.assertEqual(result.value, "ok")
            self.assertEqual(result.retries_attempted, 2)
            self.assertEqual(set(report.succeeded_nodes), {"a"})

    def test_run_exhausted_retries_records_failure(self) -> None:
        # POSTCONDITIONS: a node whose retries are exhausted MUST be recorded as
        # FAILED with the originating exception.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            attempts: List[int] = []

            def always_fails() -> str:
                attempts.append(1)
                raise RuntimeError("permanent")

            dag.add_node("a", always_fails, retries=1)
            report = runner.run()
            self.assertEqual(len(attempts), 2)
            result = report.results["a"]
            self.assertEqual(result.state, dag_engine_lite.NodeState.FAILED)
            self.assertIsNotNone(result.error)
            self.assertEqual(result.retries_attempted, 1)
            self.assertEqual(set(report.failed_nodes), {"a"})

    def test_run_fail_fast_cancels_remaining_nodes(self) -> None:
        # POSTCONDITIONS: FAIL_FAST MUST cancel nodes still pending when a node
        # fails.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def fails() -> None:
                raise RuntimeError("boom")

            dag.add_node("a", fails)
            dag.add_node("b", _noop, dependencies=["a"])
            report = runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.cancelled_nodes), {"b"})
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(
                report.results["a"].state, dag_engine_lite.NodeState.FAILED
            )
            self.assertIsNotNone(report.results["a"].error)
            self.assertEqual(
                report.results["b"].state, dag_engine_lite.NodeState.CANCELLED
            )

    def test_run_skip_downstream_skips_dependents_only(self) -> None:
        # POSTCONDITIONS: SKIP_DOWNSTREAM MUST skip transitive dependents while
        # independent nodes still execute and succeed.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def fails() -> None:
                raise RuntimeError("boom")

            dag.add_node("a", fails, priority=100)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, priority=0)
            report = runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.skipped_nodes), {"b"})
            self.assertEqual(set(report.succeeded_nodes), {"c"})
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(
                report.results["b"].state, dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                report.results["c"].state, dag_engine_lite.NodeState.SUCCEEDED
            )

    def test_run_continue_on_error_leaves_dependent_pending(self) -> None:
        # POSTCONDITIONS: CONTINUE_ON_ERROR MUST leave unblocked independent
        # nodes eligible while a blocked dependent stays non-terminal.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def fails() -> None:
                raise RuntimeError("boom")

            dag.add_node("a", fails, priority=100)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, priority=0)
            report = runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.succeeded_nodes), {"c"})
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(
                report.results["a"].state, dag_engine_lite.NodeState.FAILED
            )

    def test_run_cycle_raises_before_execution(self) -> None:
        # POSTCONDITIONS: validation errors MUST raise immediately, before any
        # node action executes.
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            executed: List[str] = []

            def action() -> None:
                executed.append("run")

            dag.add_node("a", action)
            dag.add_node("b", action)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine_lite.CycleError):
                runner.run()
            self.assertEqual(executed, [])


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T17:53:59Z
# LAST_CHANGED: 2026-10-23T17:53:23Z
# CHANGE: Addresses all five feedback gaps: (1) validate CycleError now asserted for a cycle reachable through an acyclic prerequisite, checking the reported cycle contains only cyclic nodes; (2) critical path asserted for an empty graph (empty path, zero weight); (3) critical path asserted under tied upstream branch completion times, verifying the returned sequence is one of the longest paths and the weight equals its cumulative weight; (4) mark_succeeded asserted not to revive a dependent already SKIPPED by SKIP_DOWNSTREAM when a remaining prerequisite later succeeds; (5) SKIP_DOWNSTREAM asserted to mark a diamond dependent reachable through multiple upstream chains as SKIPPED.
# COVERAGE_AUDIT: 2026-10-23T17:53:59Z
# QA_AUDIT: 2026-10-23T17:53:43Z
# --- END CLEANROOM METADATA ---
