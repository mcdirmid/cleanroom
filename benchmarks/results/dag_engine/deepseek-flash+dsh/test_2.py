from __future__ import annotations

import time
import unittest
from typing import Any, Callable, List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from benchmark_1.parts.dag_engine.lib import dag_engine_impl
from benchmark_1.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGTimeoutError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from benchmark_1.parts.dag_engine.lib.dag_engine_impl import DAG, DAGRunner, WaveScheduler


def _action_returning(value: Any) -> Callable[[], Any]:
    """Builds a zero-argument node action that returns a fixed value."""

    def action() -> Any:
        return value

    return action


def _failing_action() -> Callable[[], Any]:
    """Builds a zero-argument node action that always raises."""

    def action() -> Any:
        raise RuntimeError("node action failed")

    return action


class DagEngineImplTest(unittest.TestCase):
    """Verifies DAG, WaveScheduler, and DAGRunner against contract postconditions."""

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        dag_engine_impl.__initialize__(self._registry)

    # --- DAG contract coverage ---

    def test_dag_add_node_registers_definition_and_dependency_edges(self) -> None:
        # add_node postconditions: node is registered and dependency edges are added.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            dag.add_node("a", _action_returning("A"))
            dag.add_node(
                "b",
                _action_returning("B"),
                dependencies=["a"],
                priority=3,
                timeout_seconds=2.5,
                retries=1,
            )

            self.assertTrue(dag.has_node("a"))
            self.assertTrue(dag.has_node("b"))
            self.assertFalse(dag.has_node("missing"))
            self.assertEqual(dag.all_nodes(), {"a", "b"})

            definition = dag.get_node("b")
            self.assertEqual(definition.node_id, "b")
            self.assertEqual(definition.dependencies, frozenset({"a"}))
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.timeout_seconds, 2.5)
            self.assertEqual(definition.retries, 1)

            self.assertEqual(dag.get_dependencies("b"), {"a"})
            self.assertEqual(dag.get_dependents("a"), {"b"})

    def test_dag_add_node_without_dependencies_uses_defaults(self) -> None:
        # add_node postcondition: omitted optional fields default to 0 / None.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            dag.add_node("root", _action_returning("root"))

            definition = dag.get_node("root")
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 0)
            self.assertIsNone(definition.timeout_seconds)
            self.assertEqual(definition.retries, 0)
            self.assertEqual(dag.find_roots(), {"root"})
            self.assertEqual(dag.find_leaves(), {"root"})

    def test_dag_add_edge_establishes_ordering_between_existing_nodes(self) -> None:
        # add_edge postcondition: a directed dependency edge is established.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            dag.add_node("upstream", _action_returning(1))
            dag.add_node("downstream", _action_returning(2))

            dag.add_edge("upstream", "downstream")

            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})
            self.assertEqual(dag.find_roots(), {"upstream"})
            self.assertEqual(dag.find_leaves(), {"downstream"})
            self.assertEqual(dag.topological_sort(), ["upstream", "downstream"])

    def test_dag_add_edge_with_missing_upstream_raises_node_not_found(self) -> None:
        # add_edge postcondition: WHEN either identifier is missing, raise NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("downstream", _action_returning(2))

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.add_edge("missing", "downstream")

            self.assertEqual(raised.exception.node_id, "missing")

    def test_dag_add_edge_with_missing_downstream_raises_node_not_found(self) -> None:
        # add_edge postcondition: missing downstream identifier raises NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _action_returning(1))

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.add_edge("upstream", "missing")

            self.assertEqual(raised.exception.node_id, "missing")

    def test_dag_remove_node_detaches_incident_edges(self) -> None:
        # remove_node postconditions: node and incident edges are removed.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["b"])

            dag.remove_node("b")

            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())

    def test_dag_remove_missing_node_raises_node_not_found(self) -> None:
        # remove_node postcondition: WHEN node_id is absent, raise NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.remove_node("missing")

            self.assertEqual(raised.exception.node_id, "missing")

    def test_dag_get_node_missing_raises_node_not_found(self) -> None:
        # get_node postcondition: WHEN node_id is absent, raise NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError) as raised:
                dag.get_node("missing")

            self.assertEqual(raised.exception.node_id, "missing")

    def test_dag_dependency_queries_on_missing_node_raise_node_not_found(self) -> None:
        # get_dependencies/get_dependents postconditions: absent node raises NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("missing")
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("missing")

    def test_dag_queries_return_independent_sets(self) -> None:
        # Query postconditions: returned collections are detached copies of graph state.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])

            dependencies = dag.get_dependencies("b")
            dependents = dag.get_dependents("a")
            nodes = dag.all_nodes()
            dependencies.add("intruder")
            dependents.add("intruder")
            nodes.add("intruder")

            self.assertEqual(dag.get_dependencies("b"), {"a"})
            self.assertEqual(dag.get_dependents("a"), {"b"})
            self.assertEqual(dag.all_nodes(), {"a", "b"})

    def test_dag_validate_accepts_acyclic_graph(self) -> None:
        # validate postcondition: WHEN all dependencies exist and no cycle exists, complete.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["b"])

            dag.validate()

    def test_dag_validate_missing_dependency_raises_node_not_found(self) -> None:
        # validate postcondition: WHEN a dependency node is missing, raise NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("b", _action_returning("b"), dependencies=["ghost"])

            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_dag_validate_cycle_raises_cycle_error_with_cycle(self) -> None:
        # validate postcondition: WHEN a cycle exists, raise CycleError containing the cycle.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"))
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            with self.assertRaises(CycleError) as raised:
                dag.validate()

            self.assertGreater(len(raised.exception.cycle), 0)
            self.assertLessEqual(set(raised.exception.cycle), {"a", "b"})

    def test_dag_topological_sort_orders_prerequisites_before_dependents(self) -> None:
        # topological_sort postcondition: prerequisites precede dependents.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["b"])

            self.assertEqual(dag.topological_sort(), ["a", "b", "c"])

    def test_dag_topological_sort_breaks_ties_by_node_id_ascending(self) -> None:
        # topological_sort postcondition: ties broken by node_id ascending.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("z", _action_returning("z"))
            dag.add_node("a", _action_returning("a"))
            dag.add_node("m", _action_returning("m"))

            self.assertEqual(dag.topological_sort(), ["a", "m", "z"])

    def test_dag_topological_sort_breaks_ties_by_priority_descending(self) -> None:
        # topological_sort postcondition: ties broken by priority descending.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", _action_returning("low"), priority=0)
            dag.add_node("high", _action_returning("high"), priority=5)
            dag.add_node("child", _action_returning("child"), dependencies=["low", "high"])

            self.assertEqual(dag.topological_sort(), ["high", "low", "child"])

    def test_dag_topological_sort_cycle_raises_cycle_error(self) -> None:
        # topological_sort postcondition: WHEN a cycle exists, raise CycleError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"))
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_dag_find_roots_and_leaves_partition_graph(self) -> None:
        # find_roots/find_leaves postconditions: in-degree zero vs out-degree zero.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _action_returning("root"))
            dag.add_node("middle", _action_returning("middle"), dependencies=["root"])
            dag.add_node("leaf", _action_returning("leaf"), dependencies=["middle"])
            dag.add_node("isolated", _action_returning("isolated"))

            self.assertEqual(dag.find_roots(), {"root", "isolated"})
            self.assertEqual(dag.find_leaves(), {"leaf", "isolated"})

    def test_dag_compute_critical_path_defaults_to_unit_weights(self) -> None:
        # compute_critical_path postcondition: omitted durations default to 1.0 per node.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["b"])

            path, weight = dag.compute_critical_path()

            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(weight, 3.0)

    def test_dag_compute_critical_path_returns_longest_weighted_path(self) -> None:
        # compute_critical_path postcondition: returns longest weighted dependency path.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["b"])
            dag.add_node("d", _action_returning("d"), dependencies=["a"])

            path, weight = dag.compute_critical_path(
                {"a": 2.0, "b": 3.0, "c": 1.0, "d": 10.0}
            )

            self.assertEqual(path, ["a", "d"])
            self.assertEqual(weight, 12.0)

    def test_dag_compute_critical_path_empty_graph_returns_zero_weight(self) -> None:
        # compute_critical_path postcondition: a graph with no nodes yields an empty
        # path sequence and a cumulative weight of zero.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            path, weight = dag.compute_critical_path()

            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    # --- WaveScheduler contract coverage ---

    def test_scheduler_initializes_roots_ready_and_dependents_pending(self) -> None:
        # Initialization postcondition: roots READY, remaining nodes PENDING.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)

            self.assertIs(scheduler.get_state("a"), NodeState.READY)
            self.assertIs(scheduler.get_state("b"), NodeState.PENDING)
            self.assertEqual(
                scheduler.get_all_states(),
                {"a": NodeState.READY, "b": NodeState.PENDING},
            )
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_next_wave_orders_ready_nodes_by_priority_then_id(self) -> None:
        # next_wave postcondition: priority descending, then node_id ascending.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", _action_returning("low"), priority=0)
            dag.add_node("high", _action_returning("high"), priority=5)
            dag.add_node("other", _action_returning("other"), priority=0)

            scheduler = scope.get_singleton(WaveScheduler)

            self.assertEqual(scheduler.next_wave(), ["high", "low", "other"])

    def test_scheduler_next_wave_empty_when_no_node_ready(self) -> None:
        # next_wave postcondition: WHEN no nodes are ready, return an empty list.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["a"])

            scheduler.mark_running("a")

            self.assertEqual(scheduler.next_wave(), [])

    def test_scheduler_mark_running_transitions_state(self) -> None:
        # mark_running postcondition: state becomes RUNNING.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")

            self.assertIs(scheduler.get_state("a"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_mark_succeeded_promotes_dependents_to_ready(self) -> None:
        # mark_succeeded postcondition: dependent whose dependencies succeeded becomes READY.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertIs(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertIs(scheduler.get_state("b"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_scheduler_mark_succeeded_waits_for_all_dependencies(self) -> None:
        # mark_succeeded postcondition: dependent stays PENDING until all prerequisites succeed.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"))
            dag.add_node("c", _action_returning("c"), dependencies=["a", "b"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertIs(scheduler.get_state("c"), NodeState.PENDING)
            self.assertNotIn("c", scheduler.next_wave())

            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")

            self.assertIs(scheduler.get_state("c"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_scheduler_classifies_nodes_added_after_scheduling_begins(self) -> None:
        # Scheduling invariant: nodes registered after scheduling began are classified
        # READY when every upstream prerequisite is already SUCCEEDED, so they remain
        # eligible for dispatch; dependents of those nodes stay PENDING.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            dag.add_node("late", _action_returning("late"), dependencies=["a"])
            dag.add_node("blocked", _action_returning("blocked"), dependencies=["late"])

            self.assertEqual(scheduler.next_wave(), ["late"])
            self.assertIs(scheduler.get_state("late"), NodeState.READY)
            self.assertNotIn("blocked", scheduler.next_wave())

    def test_scheduler_mark_succeeded_retains_advanced_dependents(self) -> None:
        # mark_succeeded postcondition: only dependents still PENDING transition to READY;
        # dependents already advanced retain their current state.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("advanced", _action_returning("advanced"), dependencies=["a"])
            dag.add_node("waiting", _action_returning("waiting"), dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)
            # Advance one dependent before its upstream completes.
            scheduler.mark_running("advanced")

            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")

            self.assertIs(scheduler.get_state("advanced"), NodeState.RUNNING)
            self.assertIs(scheduler.get_state("waiting"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["waiting"])

    def test_scheduler_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        # mark_failed postcondition: FAIL_FAST transitions remaining PENDING nodes to CANCELLED.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("independent", _action_returning("independent"))

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)

            self.assertIs(scheduler.get_state("a"), NodeState.FAILED)
            self.assertIs(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertIs(scheduler.get_state("independent"), NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_scheduler_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        # mark_failed postcondition: SKIP_DOWNSTREAM transitions transitive dependents to SKIPPED.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["b"])
            dag.add_node("independent", _action_returning("independent"))

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

            self.assertIs(scheduler.get_state("a"), NodeState.FAILED)
            self.assertIs(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertIs(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertIs(scheduler.get_state("independent"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["independent"])

    def test_scheduler_mark_failed_skip_downstream_visits_all_transitive_dependents(self) -> None:
        # mark_failed postcondition: every transitive dependent becomes SKIPPED exactly once,
        # including diamonds where a dependent is reachable through multiple paths.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])
            dag.add_node("c", _action_returning("c"), dependencies=["a"])
            dag.add_node("d", _action_returning("d"), dependencies=["b", "c"])
            dag.add_node("independent", _action_returning("independent"))

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)

            states = scheduler.get_all_states()
            self.assertIs(states["a"], NodeState.FAILED)
            self.assertIs(states["b"], NodeState.SKIPPED)
            self.assertIs(states["c"], NodeState.SKIPPED)
            self.assertIs(states["d"], NodeState.SKIPPED)
            self.assertIs(states["independent"], NodeState.READY)
            skipped = {node for node, state in states.items() if state is NodeState.SKIPPED}
            self.assertEqual(skipped, {"b", "c", "d"})
            self.assertEqual(scheduler.next_wave(), ["independent"])

    def test_scheduler_mark_failed_continue_on_error_keeps_independent_nodes_runnable(self) -> None:
        # mark_failed postcondition: CONTINUE_ON_ERROR retains unblocked independent nodes.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("dependent", _action_returning("dependent"), dependencies=["a"])
            dag.add_node("independent", _action_returning("independent"))

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)

            self.assertIs(scheduler.get_state("a"), NodeState.FAILED)
            self.assertIs(scheduler.get_state("dependent"), NodeState.PENDING)
            self.assertIs(scheduler.get_state("independent"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["independent"])
            self.assertFalse(scheduler.is_finished())

    def test_scheduler_is_finished_true_when_all_nodes_terminal(self) -> None:
        # is_finished postcondition: true only when every node is in a terminal state.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())

            states = scheduler.get_all_states()
            self.assertIs(states["a"], NodeState.SUCCEEDED)
            self.assertIs(states["b"], NodeState.SUCCEEDED)

    # --- DAGRunner contract coverage ---

    def test_runner_executes_all_nodes_and_reports_success(self) -> None:
        # run postconditions: dispatch ready nodes concurrently and return a full report.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            order: List[str] = []

            def action_a() -> str:
                order.append("a")
                return "A"

            def action_b() -> str:
                order.append("b")
                return "B"

            def action_c() -> str:
                order.append("c")
                return "C"

            dag.add_node("a", action_a)
            dag.add_node("b", action_b, dependencies=["a"])
            dag.add_node("c", action_c, dependencies=["b"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=2)

            self.assertEqual(order, ["a", "b", "c"])
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b", "c"))
            self.assertEqual(set(report.results), {"a", "b", "c"})
            self.assertIs(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["a"].value, "A")

    def test_runner_retries_failed_actions_before_succeeding(self) -> None:
        # run postcondition: retries are executed up to the configured retry count.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            attempts: List[int] = []

            def flaky() -> str:
                attempts.append(len(attempts))
                if len(attempts) < 3:
                    raise RuntimeError("transient failure")
                return "recovered"

            dag.add_node("flaky", flaky, retries=2)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(len(attempts), 3)
            result = report.results["flaky"]
            self.assertIs(result.state, NodeState.SUCCEEDED)
            self.assertEqual(result.value, "recovered")
            self.assertEqual(result.retries_attempted, 2)
            self.assertEqual(report.failed_nodes, ())

    def test_runner_records_failure_after_exhausting_retries(self) -> None:
        # run postcondition: failed actions after retries produce FAILED NodeResult entries.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("broken", _failing_action(), retries=1)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            result = report.results["broken"]
            self.assertIs(result.state, NodeState.FAILED)
            self.assertEqual(result.retries_attempted, 1)
            self.assertIsInstance(result.error, RuntimeError)
            self.assertEqual(set(report.failed_nodes), {"broken"})
            self.assertEqual(report.succeeded_nodes, ())

    def test_runner_fail_fast_policy_cancels_pending_dependents(self) -> None:
        # run postcondition: FAIL_FAST applies to the scheduler on node failure.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("broken", _failing_action())
            dag.add_node("dependent", _action_returning("dependent"), dependencies=["broken"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST)

            self.assertEqual(set(report.failed_nodes), {"broken"})
            self.assertEqual(set(report.cancelled_nodes), {"dependent"})
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.skipped_nodes, ())

    def test_runner_skip_downstream_policy_skips_transitive_dependents(self) -> None:
        # run postcondition: SKIP_DOWNSTREAM marks transitive dependents SKIPPED.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("broken", _failing_action())
            dag.add_node("dependent", _action_returning("dependent"), dependencies=["broken"])
            dag.add_node("independent", _action_returning("independent"))

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(set(report.failed_nodes), {"broken"})
            self.assertEqual(set(report.skipped_nodes), {"dependent"})
            self.assertEqual(set(report.succeeded_nodes), {"independent"})
            self.assertEqual(report.cancelled_nodes, ())

    def test_runner_continue_on_error_policy_runs_independent_nodes(self) -> None:
        # run postcondition: CONTINUE_ON_ERROR leaves unblocked independent nodes eligible.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("broken", _failing_action())
            dag.add_node("independent", _action_returning("independent"))

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(set(report.failed_nodes), {"broken"})
            self.assertEqual(set(report.succeeded_nodes), {"independent"})
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())

    def test_runner_continue_on_error_reports_blocked_dependents_as_skipped(self) -> None:
        # run postcondition: a CONTINUE_ON_ERROR run completes with dependents blocked by an
        # upstream failure reported among skipped nodes while independent nodes still succeed.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("broken", _failing_action())
            dag.add_node("dependent", _action_returning("dependent"), dependencies=["broken"])
            dag.add_node("independent", _action_returning("independent"))

            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(set(report.failed_nodes), {"broken"})
            self.assertEqual(set(report.skipped_nodes), {"dependent"})
            self.assertEqual(set(report.succeeded_nodes), {"independent"})
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.total_nodes, 3)

    def test_runner_raises_timeout_when_execution_exceeds_deadline(self) -> None:
        # run postcondition: WHEN execution exceeds timeout_seconds, raise DAGTimeoutError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)

            def slow() -> str:
                time.sleep(0.2)
                return "slow"

            dag.add_node("slow", slow)
            dag.add_node("after", _action_returning("after"), dependencies=["slow"])

            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_runner_cancel_marks_all_non_terminal_nodes_cancelled(self) -> None:
        # cancel postcondition: setting cancellation status marks all non-terminal nodes CANCELLED.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"), dependencies=["a"])

            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            runner.cancel()

            self.assertIs(scheduler.get_state("a"), NodeState.CANCELLED)
            self.assertIs(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])

    def test_runner_run_after_cancel_raises_cancelled(self) -> None:
        # run postcondition: a run begun after cancellation is aborted with DAGCancelledError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))

            runner = scope.get_singleton(DAGRunner)
            runner.cancel()

            with self.assertRaises(DAGCancelledError):
                runner.run()

    def test_runner_raises_cancelled_when_cancelled_during_execution(self) -> None:
        # run postcondition: WHEN cancelled during execution, raise DAGCancelledError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            runner_box: List[DAGRunner] = []

            def first_action() -> str:
                runner_box[0].cancel()
                return "first"

            dag.add_node("first", first_action)
            dag.add_node("second", _action_returning("second"), dependencies=["first"])

            runner = scope.get_singleton(DAGRunner)
            runner_box.append(runner)

            with self.assertRaises(DAGCancelledError):
                runner.run()

    def test_runner_validates_dag_before_execution(self) -> None:
        # run precondition: cycles in the DAG raise CycleError before execution.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _action_returning("a"))
            dag.add_node("b", _action_returning("b"))
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")

            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(CycleError):
                runner.run()

    def test_runner_validate_missing_dependency_raises_node_not_found(self) -> None:
        # run precondition: missing referenced dependencies raise NodeNotFoundError.
        with enter_phase(system, registry=self._registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("b", _action_returning("b"), dependencies=["ghost"])

            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(NodeNotFoundError):
                runner.run()


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T04:18:29Z
# LAST_CHANGED: 2026-10-22T04:17:51Z
# CHANGE: Add missing contract tests: empty-graph critical path returns ([], 0.0); scheduler classifies nodes registered after scheduling begins as READY when prerequisites already SUCCEEDED; mark_succeeded promotes only PENDING dependents while retaining advanced RUNNING dependents; SKIP_DOWNSTREAM covers all transitive dependents exactly once via a diamond; cancel marks all non-terminal nodes CANCELLED and a run after cancellation raises DAGCancelledError; CONTINUE_ON_ERROR runs complete with blocked dependents reported as skipped while independent nodes succeed.
# COVERAGE_AUDIT: 2026-10-22T04:18:29Z
# QA_AUDIT: 2026-10-22T04:18:07Z
# --- END CLEANROOM METADATA ---
