"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, Callable, List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_2.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def _noop() -> None:
    """Zero-argument action used for graph topology tests."""
    return None


def _recording_action(
    calls: List[str], name: str, value: Any = None
) -> Callable[[], Any]:
    """Builds an action that records its invocation and returns a scripted value."""

    def action() -> Any:
        calls.append(name)
        return value

    return action


def _failing_action(
    calls: List[str], name: str, error: Exception
) -> Callable[[], Any]:
    """Builds an action that records its invocation and raises the supplied error."""

    def action() -> Any:
        calls.append(name)
        raise error

    return action


def _flaky_action(calls: List[str], failures: int, value: Any) -> Callable[[], Any]:
    """Builds an action that raises for `failures` attempts and then succeeds."""
    attempts = 0

    def action() -> Any:
        nonlocal attempts
        attempts += 1
        calls.append("flaky")
        if attempts <= failures:
            raise RuntimeError("transient failure")
        return value

    return action


class DagEngineLiteImplTest(unittest.TestCase):
    """Verifies DAG, WaveScheduler, and DAGRunner against their low-level contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition(self) -> None:
        """DAG.add_node POSTCONDITIONS: registers the definition and its dependency edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dag.add_node(
                "downstream",
                _noop,
                dependencies=["upstream"],
                priority=7,
                retries=3,
            )

            self.assertTrue(dag.has_node("downstream"))
            self.assertSetEqual(dag.all_nodes(), {"upstream", "downstream"})

            definition = dag.get_node("downstream")
            self.assertEqual(definition.node_id, "downstream")
            self.assertIs(definition.action, _noop)
            self.assertIsInstance(definition.dependencies, frozenset)
            self.assertSetEqual(set(definition.dependencies), {"upstream"})
            self.assertEqual(definition.priority, 7)
            self.assertEqual(definition.retries, 3)

            self.assertSetEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertSetEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_add_node_defaults_optional_parameters(self) -> None:
        """DAG.add_node POSTCONDITIONS: omitted optional parameters bind to their defaults."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("solo", _noop)

            definition = dag.get_node("solo")
            self.assertEqual(definition.priority, 0)
            self.assertEqual(definition.retries, 0)
            self.assertSetEqual(set(definition.dependencies), set())
            self.assertSetEqual(dag.get_dependencies("solo"), set())
            self.assertSetEqual(dag.get_dependents("solo"), set())

    def test_add_node_defers_missing_dependency_validation(self) -> None:
        """DAG.add_node POSTCONDITIONS: missing dependencies are not raised eagerly."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, dependencies=["ghost"])

            self.assertTrue(dag.has_node("orphan"))
            self.assertSetEqual(dag.get_dependencies("orphan"), {"ghost"})

            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.validate()

    def test_add_node_replaces_existing_registration(self) -> None:
        """DAG.add_node POSTCONDITIONS: re-registering an identifier replaces the definition and its edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)

            def initial_action() -> None:
                return None

            def replacement_action() -> None:
                return None

            dag.add_node("target", initial_action)
            dag.add_node(
                "target",
                replacement_action,
                dependencies=["upstream"],
                priority=9,
                retries=2,
            )

            definition = dag.get_node("target")
            self.assertIs(definition.action, replacement_action)
            self.assertEqual(definition.priority, 9)
            self.assertEqual(definition.retries, 2)
            self.assertSetEqual(set(definition.dependencies), {"upstream"})
            self.assertSetEqual(dag.get_dependencies("target"), {"upstream"})
            self.assertSetEqual(dag.get_dependents("upstream"), {"target"})
            self.assertSetEqual(dag.all_nodes(), {"upstream", "target"})

    def test_add_node_reregistration_detaches_previous_dependency_edges(self) -> None:
        """DAG.add_node POSTCONDITIONS: re-registration detaches prior dependency edges and attaches new ones."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("previous_dep", _noop)
            dag.add_node("new_dep", _noop)
            dag.add_node("target", _noop, dependencies=["previous_dep"])

            self.assertSetEqual(dag.get_dependencies("target"), {"previous_dep"})
            self.assertSetEqual(dag.get_dependents("previous_dep"), {"target"})

            # Re-register target so its adjacency reflects only the new definition.
            dag.add_node("target", _noop, dependencies=["new_dep"], priority=3)

            self.assertSetEqual(dag.get_dependencies("target"), {"new_dep"})
            self.assertSetEqual(dag.get_dependents("new_dep"), {"target"})
            self.assertSetEqual(dag.get_dependents("previous_dep"), set())
            self.assertSetEqual(dag.find_roots(), {"previous_dep", "new_dep"})
            self.assertSetEqual(dag.find_leaves(), {"previous_dep", "target"})
            dag.validate()

            order = dag.topological_sort()
            self.assertLess(order.index("new_dep"), order.index("target"))
            self.assertSetEqual(set(order), {"previous_dep", "new_dep", "target"})

    def test_add_edge_connects_existing_nodes(self) -> None:
        """DAG.add_edge POSTCONDITIONS: establishes the directed dependency edge."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dag.add_node("downstream", _noop)

            dag.add_edge("upstream", "downstream")

            self.assertSetEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertSetEqual(dag.get_dependents("upstream"), {"downstream"})
            self.assertSetEqual(dag.find_roots(), {"upstream"})
            self.assertSetEqual(dag.find_leaves(), {"downstream"})

    def test_add_edge_missing_upstream_raises(self) -> None:
        """DAG.add_edge POSTCONDITIONS: WHEN upstream is missing, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("downstream", _noop)

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.add_edge("ghost", "downstream")
            self.assertEqual(captured.exception.node_id, "ghost")
            self.assertSetEqual(dag.get_dependencies("downstream"), set())

    def test_add_edge_missing_downstream_raises(self) -> None:
        """DAG.add_edge POSTCONDITIONS: WHEN downstream is missing, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.add_edge("upstream", "ghost")
            self.assertEqual(captured.exception.node_id, "ghost")
            self.assertSetEqual(dag.get_dependents("upstream"), set())

    def test_remove_node_purges_incident_edges(self) -> None:
        """DAG.remove_node POSTCONDITIONS: removes the node and all incident edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop)
            dag.add_node("middle", _noop, dependencies=["root"])
            dag.add_node("leaf", _noop, dependencies=["root"])
            dag.add_node("island", _noop)

            dag.remove_node("root")

            self.assertFalse(dag.has_node("root"))
            self.assertSetEqual(dag.all_nodes(), {"middle", "leaf", "island"})
            self.assertSetEqual(dag.get_dependencies("middle"), set())
            self.assertSetEqual(dag.get_dependencies("leaf"), set())
            self.assertSetEqual(dag.find_roots(), {"middle", "leaf", "island"})

    def test_remove_node_missing_raises(self) -> None:
        """DAG.remove_node POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.remove_node("ghost")
            self.assertEqual(captured.exception.node_id, "ghost")

    def test_get_node_missing_raises(self) -> None:
        """DAG.get_node POSTCONDITIONS: WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.get_node("ghost")
            self.assertEqual(captured.exception.node_id, "ghost")

    def test_dependency_queries_missing_raise(self) -> None:
        """DAG.get_dependencies/get_dependents POSTCONDITIONS: missing nodes raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.get_dependencies("ghost")
            self.assertEqual(captured.exception.node_id, "ghost")

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.get_dependents("ghost")
            self.assertEqual(captured.exception.node_id, "ghost")

    def test_has_node_reports_membership(self) -> None:
        """DAG.has_node POSTCONDITIONS: reports whether the node exists."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("present", _noop)

            self.assertTrue(dag.has_node("present"))
            self.assertFalse(dag.has_node("absent"))

    def test_graph_queries_return_independent_copies(self) -> None:
        """DAG.all_nodes/get_dependencies/get_dependents POSTCONDITIONS: return copies."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop)
            dag.add_node("downstream", _noop, dependencies=["upstream"])

            nodes = dag.all_nodes()
            nodes.add("ghost")
            self.assertSetEqual(dag.all_nodes(), {"upstream", "downstream"})

            dependencies = dag.get_dependencies("downstream")
            dependencies.add("ghost")
            self.assertSetEqual(dag.get_dependencies("downstream"), {"upstream"})

            dependents = dag.get_dependents("upstream")
            dependents.clear()
            self.assertSetEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_validate_accepts_consistent_graph(self) -> None:
        """DAG.validate POSTCONDITIONS: WHEN all referenced nodes exist and no cycle exists, MUST complete."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])

            dag.validate()

    def test_validate_missing_dependency_raises(self) -> None:
        """DAG.validate POSTCONDITIONS: WHEN a dependency node is missing, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, dependencies=["ghost"])

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                dag.validate()
            self.assertEqual(captured.exception.node_id, "ghost")

    def test_validate_detects_cycle(self) -> None:
        """DAG.validate POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError with the cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, dependencies=["c"])
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])

            with self.assertRaises(dag_engine_lite.CycleError) as captured:
                dag.validate()
            self.assertSetEqual(set(captured.exception.cycle), {"a", "b", "c"})

    def test_topological_sort_orders_prerequisites_first(self) -> None:
        """DAG.topological_sort POSTCONDITIONS: every prerequisite precedes its dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop)
            dag.add_node("left", _noop, dependencies=["root"])
            dag.add_node("right", _noop, dependencies=["root"])
            dag.add_node("sink", _noop, dependencies=["left", "right"])

            order = dag.topological_sort()

            self.assertEqual(len(order), 4)
            self.assertSetEqual(set(order), {"root", "left", "right", "sink"})
            position = {node: index for index, node in enumerate(order)}
            self.assertLess(position["root"], position["left"])
            self.assertLess(position["root"], position["right"])
            self.assertLess(position["left"], position["sink"])
            self.assertLess(position["right"], position["sink"])

    def test_topological_sort_breaks_ties_by_priority_then_identifier(self) -> None:
        """DAG.topological_sort POSTCONDITIONS: priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("beta", _noop, priority=0)
            dag.add_node("high", _noop, priority=5)
            dag.add_node("alpha", _noop, priority=5)
            dag.add_node("zeta", _noop, priority=0)

            order = dag.topological_sort()

            self.assertEqual(order, ["alpha", "high", "beta", "zeta"])

    def test_topological_sort_cycle_raises(self) -> None:
        """DAG.topological_sort POSTCONDITIONS: WHEN a cycle exists, MUST raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop, dependencies=["c"])
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])

            with self.assertRaises(dag_engine_lite.CycleError) as captured:
                dag.topological_sort()
            self.assertSetEqual(set(captured.exception.cycle), {"a", "b", "c"})

    def test_find_roots_and_leaves(self) -> None:
        """DAG.find_roots/find_leaves POSTCONDITIONS: report in-degree and out-degree zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])
            dag.add_node("island", _noop)

            self.assertSetEqual(dag.find_roots(), {"a", "island"})
            self.assertSetEqual(dag.find_leaves(), {"c", "island"})

    def test_compute_critical_path_default_weights(self) -> None:
        """DAG.compute_critical_path POSTCONDITIONS: longest path with 1.0 default node weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])

            path, total = dag.compute_critical_path()

            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(total, 3.0)

    def test_compute_critical_path_uses_estimated_durations(self) -> None:
        """DAG.compute_critical_path POSTCONDITIONS: weights select the longest weighted path."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["a"])
            dag.add_node("d", _noop, dependencies=["b", "c"])

            path, total = dag.compute_critical_path(
                {"a": 5.0, "b": 1.0, "c": 10.0, "d": 1.0}
            )

            self.assertEqual(path, ["a", "c", "d"])
            self.assertAlmostEqual(total, 16.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """DAG.compute_critical_path POSTCONDITIONS: an empty graph yields no path and zero weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            path, total = dag.compute_critical_path()

            self.assertEqual(path, [])
            self.assertAlmostEqual(total, 0.0)

    def test_next_wave_returns_ready_roots_sorted(self) -> None:
        """WaveScheduler.next_wave POSTCONDITIONS: READY roots ordered by priority then node_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("slow", _noop, priority=0)
            dag.add_node("fast", _noop, priority=5)
            dag.add_node("child", _noop, dependencies=["fast"])

            self.assertEqual(scheduler.next_wave(), ["fast", "slow"])
            self.assertEqual(
                scheduler.get_state("fast"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(
                scheduler.get_state("slow"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(
                scheduler.get_state("child"), dag_engine_lite.NodeState.PENDING
            )

    def test_next_wave_empty_when_no_node_ready(self) -> None:
        """WaveScheduler.next_wave POSTCONDITIONS: WHEN no nodes are ready, MUST return []."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("first", _noop)
            dag.add_node("second", _noop, dependencies=["first"])

            self.assertEqual(scheduler.next_wave(), ["first"])
            scheduler.mark_running("first")
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(
                scheduler.get_state("second"), dag_engine_lite.NodeState.PENDING
            )

    def test_mark_running_updates_state(self) -> None:
        """WaveScheduler.mark_running POSTCONDITIONS: MUST update the node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)

            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")

            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.RUNNING
            )

    def test_mark_succeeded_promotes_unblocked_dependents(self) -> None:
        """WaveScheduler.mark_succeeded POSTCONDITIONS: unblocks downstream dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])

            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.SUCCEEDED
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_mark_succeeded_waits_for_all_upstream_dependencies(self) -> None:
        """WaveScheduler.mark_succeeded POSTCONDITIONS: promote only when all upstream SUCCEEDED."""
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

            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")

            self.assertEqual(
                scheduler.get_state("c"), dag_engine_lite.NodeState.READY
            )
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_mark_succeeded_does_not_revive_terminal_dependents(self) -> None:
        """WaveScheduler.mark_succeeded POSTCONDITIONS: promotion applies only to newly unblocked nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("failed_upstream", _noop)
            dag.add_node("other_upstream", _noop)
            dag.add_node(
                "dependent",
                _noop,
                dependencies=["failed_upstream", "other_upstream"],
            )

            self.assertEqual(
                scheduler.next_wave(), ["failed_upstream", "other_upstream"]
            )
            scheduler.mark_failed(
                "failed_upstream", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(
                scheduler.get_state("dependent"), dag_engine_lite.NodeState.SKIPPED
            )

            scheduler.mark_running("other_upstream")
            scheduler.mark_succeeded("other_upstream")

            self.assertEqual(
                scheduler.get_state("dependent"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_defaults_to_fail_fast(self) -> None:
        """WaveScheduler.mark_failed POSTCONDITIONS: the default policy is FAIL_FAST."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop)

            self.assertEqual(scheduler.next_wave(), ["a", "b"])
            scheduler.mark_failed("a")

            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.CANCELLED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """WaveScheduler.mark_failed POSTCONDITIONS: FAIL_FAST cancels all non-terminal nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop)

            self.assertEqual(scheduler.next_wave(), ["a", "c"])
            scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST)

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

    def test_mark_failed_skip_downstream_marks_transitive_dependents_skipped(
        self,
    ) -> None:
        """WaveScheduler.mark_failed POSTCONDITIONS: SKIP_DOWNSTREAM skips transitive dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("c", _noop, dependencies=["b"])
            dag.add_node("island", _noop)

            self.assertEqual(scheduler.next_wave(), ["a", "island"])
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
                scheduler.get_state("island"), dag_engine_lite.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("island")
            scheduler.mark_succeeded("island")
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_handles_multi_path_dependents(self) -> None:
        """WaveScheduler.mark_failed POSTCONDITIONS: multi-path transitive dependents also become SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop)
            dag.add_node("left", _noop, dependencies=["root"])
            dag.add_node("right", _noop, dependencies=["root"])
            dag.add_node("join", _noop, dependencies=["left", "right"])

            self.assertEqual(scheduler.next_wave(), ["root"])
            scheduler.mark_failed(
                "root", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
            )

            self.assertEqual(
                scheduler.get_state("left"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("right"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("join"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_continue_on_error_skips_only_blocked_dependents(
        self,
    ) -> None:
        """WaveScheduler.mark_failed POSTCONDITIONS: CONTINUE_ON_ERROR keeps independent nodes eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])
            dag.add_node("island", _noop)

            self.assertEqual(scheduler.next_wave(), ["a", "island"])
            scheduler.mark_failed(
                "a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
            )

            self.assertEqual(
                scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("island"), dag_engine_lite.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("island")
            scheduler.mark_succeeded("island")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_tracks_terminal_progress(self) -> None:
        """WaveScheduler.is_finished POSTCONDITIONS: False until every node reaches a terminal state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])

            self.assertEqual(scheduler.next_wave(), ["a"])
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("b")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_true_for_empty_dag(self) -> None:
        """WaveScheduler.is_finished POSTCONDITIONS: WHEN the DAG contains no nodes, MUST return True."""
        with enter_phase(system, registry=self.registry) as scope:
            _dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(dict(scheduler.get_all_states()), {})
            self.assertTrue(scheduler.is_finished())

    def test_state_tracking_synchronizes_with_dynamic_graph(self) -> None:
        """WaveScheduler.get_all_states POSTCONDITIONS: reflect only currently registered nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", _noop)
            dag.add_node("b", _noop, dependencies=["a"])

            self.assertEqual(scheduler.next_wave(), ["a"])
            self.assertSetEqual(set(scheduler.get_all_states()), {"a", "b"})

            dag.add_node("c", _noop)
            self.assertSetEqual(set(scheduler.get_all_states()), {"a", "b", "c"})

            dag.remove_node("b")
            self.assertSetEqual(set(scheduler.get_all_states()), {"a", "c"})

    def test_state_sync_promotes_late_nodes_with_succeeded_upstreams(self) -> None:
        """WaveScheduler.next_wave POSTCONDITIONS: late-tracked nodes with satisfied dependencies become READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("upstream", _noop)

            self.assertEqual(scheduler.next_wave(), ["upstream"])
            scheduler.mark_running("upstream")
            scheduler.mark_succeeded("upstream")

            dag.add_node("late", _noop, dependencies=["upstream"])

            self.assertEqual(scheduler.next_wave(), ["late"])
            self.assertEqual(
                scheduler.get_state("late"), dag_engine_lite.NodeState.READY
            )

    def test_run_executes_sequential_waves_and_reports_success(self) -> None:
        """DAGRunner.run POSTCONDITIONS: executes waves sequentially and returns a consolidated report."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("first", _recording_action(calls, "first", "A"))
            dag.add_node(
                "second",
                _recording_action(calls, "second", "B"),
                dependencies=["first"],
            )

            report = runner.run()

            self.assertEqual(calls, ["first", "second"])
            self.assertEqual(report.total_nodes, 2)
            self.assertSetEqual(set(report.succeeded_nodes), {"first", "second"})
            self.assertEqual(tuple(report.failed_nodes), ())
            self.assertEqual(tuple(report.skipped_nodes), ())
            self.assertEqual(tuple(report.cancelled_nodes), ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(tuple(report.critical_path), ("first", "second"))
            self.assertSetEqual(set(report.results), {"first", "second"})
            self.assertEqual(
                report.results["first"].state,
                dag_engine_lite.NodeState.SUCCEEDED,
            )
            self.assertEqual(
                report.results["second"].state,
                dag_engine_lite.NodeState.SUCCEEDED,
            )
            self.assertEqual(report.results["first"].value, "A")
            self.assertEqual(report.results["second"].value, "B")

    def test_run_dispatches_wave_in_priority_order(self) -> None:
        """DAGRunner.run POSTCONDITIONS: ready waves execute in scheduler priority order."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("low", _recording_action(calls, "low"), priority=0)
            dag.add_node("high", _recording_action(calls, "high"), priority=5)

            runner.run()

            self.assertEqual(calls, ["high", "low"])

    def test_run_retries_failed_action_until_success(self) -> None:
        """DAGRunner.run POSTCONDITIONS: MUST execute retries up to the configured retry count."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node(
                "flaky", _flaky_action(calls, failures=2, value="recovered"), retries=3
            )

            report = runner.run()

            # The action fails twice and succeeds on its third invocation.
            self.assertEqual(len(calls), 3)
            self.assertEqual(
                report.results["flaky"].state,
                dag_engine_lite.NodeState.SUCCEEDED,
            )
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertSetEqual(set(report.succeeded_nodes), {"flaky"})
            self.assertSetEqual(set(report.failed_nodes), set())

    def test_run_reports_failure_after_retries_exhausted(self) -> None:
        """DAGRunner.run POSTCONDITIONS: failure is recorded once permitted retries are exhausted."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node(
                "bad", _failing_action(calls, "bad", ValueError("boom")), retries=2
            )

            report = runner.run()

            # The initial attempt is retried at least once before the failure sticks.
            self.assertGreaterEqual(len(calls), 2)
            self.assertEqual(
                report.results["bad"].state, dag_engine_lite.NodeState.FAILED
            )
            self.assertSetEqual(set(report.failed_nodes), {"bad"})
            self.assertSetEqual(set(report.succeeded_nodes), set())

    def test_run_fail_fast_reports_failed_and_cancelled_nodes(self) -> None:
        """DAGRunner.run POSTCONDITIONS: FAIL_FAST records the failure and cancels the rest."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad", _failing_action(calls, "bad", ValueError("boom")))
            dag.add_node(
                "child", _recording_action(calls, "child"), dependencies=["bad"]
            )

            report = runner.run()

            self.assertEqual(calls, ["bad"])
            self.assertEqual(
                report.results["bad"].state, dag_engine_lite.NodeState.FAILED
            )
            self.assertIsNotNone(report.results["bad"].error)
            self.assertIsInstance(report.results["bad"].error, Exception)
            self.assertIn("boom", str(report.results["bad"].error))
            self.assertEqual(
                report.results["child"].state, dag_engine_lite.NodeState.CANCELLED
            )
            self.assertSetEqual(set(report.failed_nodes), {"bad"})
            self.assertSetEqual(set(report.cancelled_nodes), {"child"})
            self.assertSetEqual(set(report.succeeded_nodes), set())
            self.assertSetEqual(set(report.skipped_nodes), set())
            self.assertEqual(
                scheduler.get_state("child"), dag_engine_lite.NodeState.CANCELLED
            )

    def test_run_skip_downstream_marks_transitive_dependents_skipped(self) -> None:
        """DAGRunner.run POSTCONDITIONS: SKIP_DOWNSTREAM skips transitive dependents after failure."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", _failing_action(calls, "a", ValueError("boom")))
            dag.add_node("b", _recording_action(calls, "b"), dependencies=["a"])
            dag.add_node("c", _recording_action(calls, "c"), dependencies=["b"])

            report = runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(calls, ["a"])
            self.assertSetEqual(set(report.failed_nodes), {"a"})
            self.assertSetEqual(set(report.skipped_nodes), {"b", "c"})
            self.assertSetEqual(set(report.cancelled_nodes), set())
            self.assertSetEqual(set(report.succeeded_nodes), set())
            self.assertEqual(
                report.results["b"].state, dag_engine_lite.NodeState.SKIPPED
            )
            self.assertEqual(
                report.results["c"].state, dag_engine_lite.NodeState.SKIPPED
            )

    def test_run_continue_on_error_executes_independent_nodes(self) -> None:
        """DAGRunner.run POSTCONDITIONS: CONTINUE_ON_ERROR keeps unblocked nodes executable."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad", _failing_action(calls, "bad", ValueError("boom")))
            dag.add_node(
                "child", _recording_action(calls, "child"), dependencies=["bad"]
            )
            dag.add_node(
                "independent", _recording_action(calls, "independent", "ok")
            )

            report = runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)

            self.assertSetEqual(set(calls), {"bad", "independent"})
            self.assertSetEqual(set(report.failed_nodes), {"bad"})
            self.assertSetEqual(set(report.skipped_nodes), {"child"})
            self.assertSetEqual(set(report.succeeded_nodes), {"independent"})
            self.assertEqual(report.results["independent"].value, "ok")

    def test_run_raises_cycle_error_before_executing_actions(self) -> None:
        """DAGRunner.run POSTCONDITIONS: validates graph invariants before wave execution."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", _recording_action(calls, "a"), dependencies=["b"])
            dag.add_node("b", _recording_action(calls, "b"), dependencies=["a"])

            with self.assertRaises(dag_engine_lite.CycleError):
                runner.run()
            self.assertEqual(calls, [])

    def test_run_raises_node_not_found_for_missing_dependency(self) -> None:
        """DAGRunner.run POSTCONDITIONS: missing dependencies raise NodeNotFoundError before execution."""
        calls: List[str] = []
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", _recording_action(calls, "a"))
            dag.add_node(
                "orphan", _recording_action(calls, "orphan"), dependencies=["ghost"]
            )

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as captured:
                runner.run()
            self.assertEqual(captured.exception.node_id, "ghost")
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:46:56Z
# LAST_CHANGED: 2026-11-02T23:46:34Z
# CHANGE: Added test_add_node_reregistration_detaches_previous_dependency_edges to address the adjacency-consistency feedback: a node is first registered with declared upstream dependency previous_dep (asserting its dependency/dependent queries), then re-registered for the same node_id with a different upstream new_dep. The test asserts the previously registered edge is detached (get_dependents(previous_dep) is empty, get_dependencies(target) exactly {new_dep}), the newly supplied edge is established (get_dependents(new_dep) is {target}), and the derived graph queries (find_roots, find_leaves, validate, topological_sort) reflect only the currently registered definition's adjacency. Module now has 48 tests; static checks pass.
# COVERAGE_AUDIT: 2026-11-02T23:46:56Z
# QA_AUDIT: 2026-11-02T23:46:44Z
# --- END AUTOFAB METADATA ---
