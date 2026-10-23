from __future__ import annotations

import time
import unittest
from typing import Dict, List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from benchmark_2.parts.dag_engine.lib import dag_engine
from benchmark_2.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class DAGTest(unittest.TestCase):
    """Verifies the singleton DAG contracts declared in low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition_with_defaults(self) -> None:
        """POSTCONDITION: add_node registers the node definition into the graph."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("alpha", lambda: "value")
            self.assertTrue(dag.has_node("alpha"))
            definition = dag.get_node("alpha")
            self.assertEqual(definition.node_id, "alpha")
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 0)
            self.assertIsNone(definition.timeout_seconds)
            self.assertEqual(definition.retries, 0)
            self.assertEqual(definition.action(), "value")

    def test_add_node_with_options_registers_edges(self) -> None:
        """POSTCONDITION: provided dependencies become directed dependency edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", lambda: 1)
            dag.add_node(
                "downstream",
                lambda: 2,
                dependencies=["upstream"],
                priority=7,
                timeout_seconds=2.5,
                retries=3,
            )
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})
            definition = dag.get_node("downstream")
            self.assertEqual(definition.dependencies, frozenset({"upstream"}))
            self.assertEqual(definition.priority, 7)
            self.assertEqual(definition.timeout_seconds, 2.5)
            self.assertEqual(definition.retries, 3)

    def test_add_edge_connects_registered_nodes(self) -> None:
        """POSTCONDITION: add_edge establishes a directed dependency edge."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2)
            dag.add_edge("first", "second")
            self.assertEqual(dag.get_dependencies("second"), {"first"})
            self.assertEqual(dag.get_dependents("first"), {"second"})

    def test_add_edge_with_missing_upstream_raises(self) -> None:
        """POSTCONDITION: missing upstream identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("second", lambda: 2)
            with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
                dag.add_edge("missing", "second")
            self.assertEqual(raised.exception.node_id, "missing")

    def test_add_edge_with_missing_downstream_raises(self) -> None:
        """POSTCONDITION: missing downstream identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
                dag.add_edge("first", "missing")
            self.assertEqual(raised.exception.node_id, "missing")

    def test_remove_node_removes_incident_edges(self) -> None:
        """POSTCONDITION: remove_node deletes the node and its incident edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("middle", lambda: 2)
            dag.add_node("last", lambda: 3)
            dag.add_edge("first", "middle")
            dag.add_edge("middle", "last")
            dag.remove_node("middle")
            self.assertFalse(dag.has_node("middle"))
            self.assertEqual(dag.all_nodes(), {"first", "last"})
            self.assertEqual(dag.get_dependents("first"), set())
            self.assertEqual(dag.get_dependencies("last"), set())

    def test_remove_missing_node_raises(self) -> None:
        """POSTCONDITION: removing an absent node raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
                dag.remove_node("ghost")
            self.assertEqual(raised.exception.node_id, "ghost")

    def test_unknown_node_lookups_raise(self) -> None:
        """POSTCONDITION: unknown identifiers raise NodeNotFoundError on lookup."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine.NodeNotFoundError) as node_raised:
                dag.get_node("ghost")
            self.assertEqual(node_raised.exception.node_id, "ghost")
            with self.assertRaises(dag_engine.NodeNotFoundError) as deps_raised:
                dag.get_dependencies("ghost")
            self.assertEqual(deps_raised.exception.node_id, "ghost")
            with self.assertRaises(dag_engine.NodeNotFoundError) as dependents_raised:
                dag.get_dependents("ghost")
            self.assertEqual(dependents_raised.exception.node_id, "ghost")

    def test_validate_accepts_consistent_acyclic_graph(self) -> None:
        """POSTCONDITION: valid complete acyclic graphs validate without error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2, dependencies=["first"])
            dag.add_node("third", lambda: 3, dependencies=["second"])
            dag.validate()

    def test_validate_reports_unregistered_dependency(self) -> None:
        """POSTCONDITION: missing referenced dependencies raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", lambda: 1, dependencies=["never_registered"])
            with self.assertRaises(dag_engine.NodeNotFoundError) as raised:
                dag.validate()
            self.assertEqual(raised.exception.node_id, "never_registered")

    def test_validate_detects_cycle(self) -> None:
        """POSTCONDITION: cycles raise CycleError carrying the cycle sequence."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2)
            dag.add_edge("first", "second")
            dag.add_edge("second", "first")
            with self.assertRaises(dag_engine.CycleError) as raised:
                dag.validate()
            self.assertEqual(set(raised.exception.cycle), {"first", "second"})

    def test_validate_cycle_sequence_includes_intermediate_nodes(self) -> None:
        """POSTCONDITION: the reported cycle includes every participating node."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("middle", lambda: 2)
            dag.add_node("last", lambda: 3)
            dag.add_edge("first", "middle")
            dag.add_edge("middle", "last")
            dag.add_edge("last", "first")
            with self.assertRaises(dag_engine.CycleError) as raised:
                dag.validate()
            self.assertEqual(
                set(raised.exception.cycle), {"first", "middle", "last"}
            )
            self.assertGreaterEqual(len(raised.exception.cycle), 3)

    def test_topological_sort_orders_by_priority_descending(self) -> None:
        """POSTCONDITION: independent ready nodes break ties by priority descending."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", lambda: 1, priority=0)
            dag.add_node("high", lambda: 2, priority=10)
            self.assertEqual(dag.topological_sort(), ["high", "low"])

    def test_topological_sort_breaks_ties_alphabetically(self) -> None:
        """POSTCONDITION: equal priorities break ties by node identifier ascending."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("beta", lambda: 1)
            dag.add_node("alpha", lambda: 2)
            self.assertEqual(dag.topological_sort(), ["alpha", "beta"])

    def test_topological_sort_prefers_dependencies_over_priority(self) -> None:
        """POSTCONDITION: every prerequisite precedes its dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("prerequisite", lambda: 1, priority=0)
            dag.add_node(
                "dependent",
                lambda: 2,
                dependencies=["prerequisite"],
                priority=100,
            )
            self.assertEqual(dag.topological_sort(), ["prerequisite", "dependent"])

    def test_topological_sort_cycle_raises(self) -> None:
        """POSTCONDITION: a cyclic graph raises CycleError from topological_sort."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2)
            dag.add_edge("first", "second")
            dag.add_edge("second", "first")
            with self.assertRaises(dag_engine.CycleError):
                dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """POSTCONDITION: root and leaf queries reflect in/out degrees."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: 1)
            dag.add_node("left", lambda: 2, dependencies=["root"])
            dag.add_node("right", lambda: 3, dependencies=["root"])
            dag.add_node("leaf", lambda: 4, dependencies=["left", "right"])
            self.assertEqual(dag.find_roots(), {"root"})
            self.assertEqual(dag.find_leaves(), {"leaf"})

    def test_compute_critical_path_with_default_weights(self) -> None:
        """POSTCONDITION: omitted durations default to one unit per node."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2, dependencies=["first"])
            dag.add_node("third", lambda: 3, dependencies=["second"])
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["first", "second", "third"])
            self.assertEqual(weight, 3.0)

    def test_compute_critical_path_uses_estimated_durations(self) -> None:
        """POSTCONDITION: supplied durations select the longest weighted path."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", lambda: 1)
            dag.add_node("slow", lambda: 2, dependencies=["start"])
            dag.add_node("fast", lambda: 3, dependencies=["start"])
            dag.add_node("finish", lambda: 4, dependencies=["slow", "fast"])
            durations = {"start": 1.0, "slow": 5.0, "fast": 1.0, "finish": 1.0}
            path, weight = dag.compute_critical_path(durations)
            self.assertEqual(path, ["start", "slow", "finish"])
            self.assertEqual(weight, 7.0)

    def test_compute_critical_path_on_empty_graph(self) -> None:
        """POSTCONDITION: an empty graph yields an empty path and zero weight."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)


class WaveSchedulerTest(unittest.TestCase):
    """Verifies the singleton WaveScheduler contracts declared in low/dag_engine_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_states_mark_roots_ready_and_others_pending(self) -> None:
        """GROUNDING: root nodes initialize READY and non-root nodes PENDING."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: 1, priority=1)
            dag.add_node("independent", lambda: 2, priority=9)
            dag.add_node("blocked", lambda: 3, dependencies=["root"], priority=50)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.READY)
            self.assertEqual(
                scheduler.get_state("independent"), dag_engine.NodeState.READY
            )
            self.assertEqual(
                scheduler.get_state("blocked"), dag_engine.NodeState.PENDING
            )
            self.assertEqual(scheduler.next_wave(), ["independent", "root"])

    def test_next_wave_is_empty_while_root_is_running(self) -> None:
        """POSTCONDITION: no dependent becomes ready until its upstream succeeds."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2, dependencies=["first"])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["first"])
            scheduler.mark_running("first")
            self.assertEqual(
                scheduler.get_state("first"), dag_engine.NodeState.RUNNING
            )
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_succeeded_unlocks_dependents_in_priority_order(self) -> None:
        """POSTCONDITION: succeeded nodes promote newly unblocked dependents to READY."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: 1)
            dag.add_node("low", lambda: 2, dependencies=["root"], priority=1)
            dag.add_node("high", lambda: 3, dependencies=["root"], priority=5)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("root")
            scheduler.mark_succeeded("root")
            self.assertEqual(
                scheduler.get_state("root"), dag_engine.NodeState.SUCCEEDED
            )
            self.assertEqual(scheduler.get_state("low"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("high"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["high", "low"])

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """POSTCONDITION: FAIL_FAST transitions remaining non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2, dependencies=["first"])
            dag.add_node("third", lambda: 3, dependencies=["second"])
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("first")
            self.assertEqual(
                scheduler.get_state("first"), dag_engine.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("second"), dag_engine.NodeState.CANCELLED
            )
            self.assertEqual(
                scheduler.get_state("third"), dag_engine.NodeState.CANCELLED
            )
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """POSTCONDITION: SKIP_DOWNSTREAM marks transitive dependents as SKIPPED."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2, dependencies=["first"])
            dag.add_node("third", lambda: 3, dependencies=["second"])
            dag.add_node("independent", lambda: 4)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("first", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(
                scheduler.get_state("first"), dag_engine.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("second"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("third"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("independent"), dag_engine.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), ["independent"])

    def test_mark_failed_skip_downstream_skips_multi_route_dependents(self) -> None:
        """POSTCONDITION: dependents reachable through several routes are skipped."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("left", lambda: 2, dependencies=["first"])
            dag.add_node("right", lambda: 3, dependencies=["first"])
            dag.add_node("merge", lambda: 4, dependencies=["left", "right"])
            dag.add_node("tail", lambda: 5, dependencies=["merge"])
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("first", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(
                scheduler.get_state("left"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("right"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("merge"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(
                scheduler.get_state("tail"), dag_engine.NodeState.SKIPPED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_continue_on_error_preserves_independent_nodes(self) -> None:
        """POSTCONDITION: CONTINUE_ON_ERROR leaves unblocked independent nodes eligible."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("dependent", lambda: 2, dependencies=["first"])
            dag.add_node("independent", lambda: 3)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_failed("first", dag_engine.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(
                scheduler.get_state("first"), dag_engine.NodeState.FAILED
            )
            self.assertEqual(
                scheduler.get_state("dependent"), dag_engine.NodeState.PENDING
            )
            self.assertEqual(
                scheduler.get_state("independent"), dag_engine.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), ["independent"])

    def test_is_finished_tracks_terminal_states(self) -> None:
        """POSTCONDITION: is_finished is True only when every node is terminal."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("second", lambda: 2, dependencies=["first"])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("first")
            scheduler.mark_succeeded("first")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("second")
            scheduler.mark_succeeded("second")
            self.assertTrue(scheduler.is_finished())

    def test_get_all_states_reports_every_node(self) -> None:
        """POSTCONDITION: get_all_states exposes a mapping of every node state."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: 1)
            dag.add_node("dependent", lambda: 2, dependencies=["root"])
            scheduler = scope.get_singleton(WaveScheduler)
            states = scheduler.get_all_states()
            self.assertEqual(set(states.keys()), {"root", "dependent"})
            self.assertEqual(states["root"], dag_engine.NodeState.READY)
            self.assertEqual(states["dependent"], dag_engine.NodeState.PENDING)

    def test_get_all_states_reflects_current_graph_members(self) -> None:
        """POSTCONDITION: previously reported states disappear when nodes are removed."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("kept", lambda: 1)
            dag.add_node("removed", lambda: 2)
            scheduler = scope.get_singleton(WaveScheduler)
            initial_states = scheduler.get_all_states()
            self.assertEqual(set(initial_states.keys()), {"kept", "removed"})
            self.assertEqual(initial_states["kept"], dag_engine.NodeState.READY)
            self.assertEqual(initial_states["removed"], dag_engine.NodeState.READY)
            scheduler.mark_running("kept")
            scheduler.mark_succeeded("kept")
            dag.remove_node("removed")
            remaining_states = scheduler.get_all_states()
            self.assertEqual(set(remaining_states.keys()), {"kept"})
            self.assertEqual(
                remaining_states["kept"], dag_engine.NodeState.SUCCEEDED
            )


class DAGRunnerTest(unittest.TestCase):
    """Verifies the singleton DAGRunner contracts declared in low/dag_engine_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_executes_chain_and_reports_success(self) -> None:
        """POSTCONDITION: run returns a DAGRunReport capturing every node outcome."""
        executed: List[str] = []

        def action_first() -> int:
            executed.append("first")
            return 1

        def action_second() -> int:
            executed.append("second")
            return 2

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", action_first)
            dag.add_node("second", action_second, dependencies=["first"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(executed, ["first", "second"])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"first", "second"})
            self.assertEqual(set(report.failed_nodes), set())
            self.assertEqual(set(report.skipped_nodes), set())
            self.assertEqual(set(report.cancelled_nodes), set())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("first", "second"))
            self.assertEqual(set(report.results.keys()), {"first", "second"})
            self.assertEqual(
                report.results["first"].state, dag_engine.NodeState.SUCCEEDED
            )
            self.assertEqual(report.results["first"].value, 1)
            self.assertEqual(report.results["second"].value, 2)
            self.assertEqual(report.results["first"].retries_attempted, 0)

    def test_run_executes_independent_nodes_concurrently(self) -> None:
        """POSTCONDITION: independent ready nodes execute within the concurrency limit."""
        executed: List[str] = []

        def action_one() -> str:
            executed.append("one")
            return "one"

        def action_two() -> str:
            executed.append("two")
            return "two"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("one", action_one)
            dag.add_node("two", action_two)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=2)
            self.assertEqual(set(executed), {"one", "two"})
            self.assertEqual(set(report.succeeded_nodes), {"one", "two"})
            self.assertEqual(set(report.results.keys()), {"one", "two"})

    def test_run_retries_failed_action(self) -> None:
        """POSTCONDITION: retries execute up to the configured retry count."""
        attempts: Dict[str, int] = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("transient failure")
            return "recovered"

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", flaky, retries=1)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(attempts["count"], 2)
            self.assertEqual(
                report.results["flaky"].state, dag_engine.NodeState.SUCCEEDED
            )
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertEqual(report.results["flaky"].retries_attempted, 1)
            self.assertEqual(set(report.succeeded_nodes), {"flaky"})

    def test_run_fail_fast_reports_failure_and_cancels_pending(self) -> None:
        """POSTCONDITION: FAIL_FAST records the failure and cancels pending nodes."""

        def failing() -> int:
            raise RuntimeError("boom")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", failing)
            dag.add_node("dependent", lambda: 2, dependencies=["failing"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=dag_engine.FailurePolicy.FAIL_FAST)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.succeeded_nodes), set())
            self.assertEqual(set(report.cancelled_nodes), {"dependent"})
            self.assertEqual(
                report.results["failing"].state, dag_engine.NodeState.FAILED
            )
            self.assertIsNotNone(report.results["failing"].error)

    def test_run_skip_downstream_marks_dependents_skipped(self) -> None:
        """POSTCONDITION: SKIP_DOWNSTREAM reports transitive dependents as skipped."""

        def failing() -> int:
            raise RuntimeError("boom")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", failing)
            dag.add_node("dependent", lambda: 2, dependencies=["failing"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.skipped_nodes), {"dependent"})
            self.assertEqual(set(report.cancelled_nodes), set())

    def test_run_continue_on_error_keeps_independent_nodes_running(self) -> None:
        """POSTCONDITION: CONTINUE_ON_ERROR still executes unblocked independent nodes."""

        def failing() -> int:
            raise RuntimeError("boom")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", failing)
            dag.add_node("independent", lambda: "ok")
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.CONTINUE_ON_ERROR,
                max_concurrency=2,
            )
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.succeeded_nodes), {"independent"})

    def test_run_continue_on_error_skips_unrunnable_dependents(self) -> None:
        """POSTCONDITION: unreachable nodes are skipped so the run still terminates."""

        def failing() -> int:
            raise RuntimeError("boom")

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", failing)
            dag.add_node("dependent", lambda: 2, dependencies=["failing"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.CONTINUE_ON_ERROR
            )
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.skipped_nodes), {"dependent"})

    def test_run_raises_timeout_when_execution_exceeds_budget(self) -> None:
        """POSTCONDITION: exceeding timeout_seconds raises DAGTimeoutError."""

        def slow() -> int:
            time.sleep(0.1)
            return 1

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", slow)
            dag.add_node("dependent", lambda: 2, dependencies=["slow"])
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_run_raises_timeout_when_budget_already_exhausted(self) -> None:
        """POSTCONDITION: an already exhausted budget raises DAGTimeoutError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.0)

    def test_run_after_cancel_raises_cancelled_error(self) -> None:
        """POSTCONDITION: run after cancel raises DAGCancelledError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: 1)
            dag.add_node("dependent", lambda: 2, dependencies=["first"])
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()
            self.assertEqual(
                scheduler.get_state("dependent"), dag_engine.NodeState.CANCELLED
            )
            self.assertTrue(scheduler.is_finished())
            with self.assertRaises(dag_engine.DAGCancelledError):
                runner.run()

    def test_run_cancelled_during_execution_raises_and_cancels_remaining(self) -> None:
        """POSTCONDITION: mid-run cancellation raises and cancels non-terminal nodes."""
        holders: List[DAGRunner] = []

        def cancel_execution() -> None:
            holders[0].cancel()

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", cancel_execution)
            dag.add_node("dependent", lambda: 2, dependencies=["first"])
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)
            holders.append(runner)
            with self.assertRaises(dag_engine.DAGCancelledError):
                runner.run()
            self.assertEqual(
                scheduler.get_state("dependent"), dag_engine.NodeState.CANCELLED
            )


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T17:57:13Z
# LAST_CHANGED: 2026-10-22T17:56:36Z
# CHANGE: Address feedback: reconcile scheduler state reporting after node removal by first reporting states for all nodes, transitioning a remaining node to SUCCEEDED, removing a previously reported node, and asserting the new state mapping contains exactly the surviving graph member with its updated state.
# COVERAGE_AUDIT: 2026-10-22T17:57:13Z
# QA_AUDIT: 2026-10-22T17:56:49Z
# --- END CLEANROOM METADATA ---
