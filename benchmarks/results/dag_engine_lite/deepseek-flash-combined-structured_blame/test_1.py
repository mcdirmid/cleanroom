"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, Callable, List

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


def recording_action(label: str, calls: List[str], value: Any = None) -> Callable[[], Any]:
    """Factory wrapping a label into a node action that records its invocation."""

    def action() -> Any:
        calls.append(label)
        return value

    return action


def failing_action(label: str, calls: List[str], error: Exception) -> Callable[[], Any]:
    """Factory wrapping a label into a node action that records then raises error."""

    def action() -> Any:
        calls.append(label)
        raise error

    return action


class FlakyAction:
    """Scripted node action failing a fixed number of attempts before succeeding."""

    def __init__(self, failures: int, value: Any) -> None:
        self.failures = failures
        self.value = value
        self.calls = 0

    def __call__(self) -> Any:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("transient node failure")
        return self.value


class DagGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition(self) -> None:
        """Happy path: add_node registers the immutable NodeDefinition with its edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            action = recording_action("a", calls)
            dag.add_node("a", action, None, 3, 1)
            self.assertTrue(dag.has_node("a"))
            self.assertEqual(dag.all_nodes(), {"a"})
            definition = dag.get_node("a")
            self.assertEqual(definition.node_id, "a")
            self.assertIs(definition.action, action)
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.retries, 1)
            self.assertEqual(dag.get_dependencies("a"), set())
            self.assertEqual(dag.get_dependents("a"), set())

    def test_add_node_with_dependencies_adds_directed_edges(self) -> None:
        """POSTCONDITION: provided dependencies become directed edges from upstream to node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("root", recording_action("root", calls), None, 0, 0)
            dag.add_node("child", recording_action("child", calls), ["root"], 0, 0)
            self.assertEqual(dag.get_dependencies("child"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"child"})
            self.assertEqual(dag.get_node("child").dependencies, frozenset({"root"}))

    def test_add_node_defers_missing_dependency_checks(self) -> None:
        """POSTCONDITION: add_node defers missing dependency checks without eager NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("child", recording_action("child", calls), ["ghost"], 0, 0)
            self.assertFalse(dag.has_node("ghost"))
            self.assertEqual(dag.get_dependencies("child"), {"ghost"})
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.validate()
            self.assertIn(ctx.exception.node_id, {"ghost", "child"})

    def test_add_node_duplicate_raises_duplicate_node_error(self) -> None:
        """PRECONDITION: add_node with an already registered node_id raises DuplicateNodeError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            action = recording_action("dup", calls)
            dag.add_node("dup", action, None, 0, 0)
            with self.assertRaises(DuplicateNodeError) as ctx:
                dag.add_node("dup", action, None, 0, 0)
            self.assertEqual(ctx.exception.node_id, "dup")
            self.assertEqual(dag.all_nodes(), {"dup"})

    def test_add_edge_establishes_dependency(self) -> None:
        """POSTCONDITION: add_edge establishes a directed edge from upstream to downstream."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("up", recording_action("up", calls), None, 0, 0)
            dag.add_node("down", recording_action("down", calls), None, 0, 0)
            dag.add_edge("up", "down")
            self.assertEqual(dag.get_dependencies("down"), {"up"})
            self.assertEqual(dag.get_dependents("up"), {"down"})
            dag.validate()

    def test_add_edge_missing_nodes_raise_node_not_found(self) -> None:
        """PRECONDITION: add_edge with an unregistered endpoint raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("only", recording_action("only", calls), None, 0, 0)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("only", "missing_downstream")
            self.assertEqual(ctx.exception.node_id, "missing_downstream")
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.add_edge("missing_upstream", "only")
            self.assertEqual(ctx.exception.node_id, "missing_upstream")
            self.assertEqual(dag.get_dependents("only"), set())
            self.assertEqual(dag.get_dependencies("only"), set())

    def test_remove_node_purges_node_and_incident_edges(self) -> None:
        """POSTCONDITION: remove_node purges the node and all incident dependency edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependencies("c"), set())
            self.assertEqual(dag.get_dependents("a"), set())

    def test_remove_node_missing_raises_node_not_found(self) -> None:
        """PRECONDITION: remove_node with an unregistered node_id raises NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.remove_node("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")
            self.assertEqual(dag.all_nodes(), set())

    def test_lookup_of_missing_node_raises_node_not_found(self) -> None:
        """PRECONDITION: get_node/get_dependencies/get_dependents raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependencies("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_dependents("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_validate_complete_valid_graph(self) -> None:
        """POSTCONDITION: validate completes without error for a complete acyclic graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["a", "b"], 0, 0)
            self.assertIsNone(dag.validate())

    def test_validate_detects_cycle(self) -> None:
        """PRECONDITION: validate raises CycleError carrying the cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), ["b"], 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertEqual(set(ctx.exception.cycle), {"a", "b"})

    def test_topological_sort_dependency_order(self) -> None:
        """POSTCONDITION: every prerequisite precedes its dependents in topological order."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            order = dag.topological_sort()
            self.assertEqual(set(order), {"a", "b", "c"})
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("b"), order.index("c"))

    def test_topological_sort_tie_breaking(self) -> None:
        """POSTCONDITION: ties break by priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("low", recording_action("low", calls), None, 0, 0)
            dag.add_node("high", recording_action("high", calls), None, 10, 0)
            dag.add_node("mid_b", recording_action("mid_b", calls), None, 5, 0)
            dag.add_node("mid_a", recording_action("mid_a", calls), None, 5, 0)
            self.assertEqual(dag.topological_sort(), ["high", "mid_a", "mid_b", "low"])

    def test_topological_sort_cycle_raises(self) -> None:
        """PRECONDITION: topological_sort raises CycleError for a cyclic graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), ["b"], 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """Happy path: roots have no upstream, leaves have no downstream."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            dag.add_node("d", recording_action("d", calls), None, 0, 0)
            self.assertEqual(dag.find_roots(), {"a", "d"})
            self.assertEqual(dag.find_leaves(), {"c", "d"})

    def test_compute_critical_path_weighted(self) -> None:
        """POSTCONDITION: longest weighted path and its cumulative weight are returned."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            path, weight = dag.compute_critical_path({"a": 1.0, "b": 5.0, "c": 2.0})
            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(weight, 8.0)

    def test_compute_critical_path_defaults_to_unit_weights(self) -> None:
        """POSTCONDITION: omitted durations default to a response weight of 1.0 per node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(weight, 3.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """Boundary: a zero-node graph yields an empty path with zero cumulative weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertAlmostEqual(weight, 0.0)


class WaveSchedulerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_next_wave_orders_ready_roots_by_priority(self) -> None:
        """POSTCONDITION: next_wave returns READY roots ordered by priority descending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("low", recording_action("low", calls), None, 0, 0)
            dag.add_node("high", recording_action("high", calls), None, 5, 0)
            dag.add_node("dependent", recording_action("dependent", calls), ["high"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["high", "low"])
            self.assertEqual(scheduler.get_state("high"), NodeState.READY)
            self.assertEqual(scheduler.get_state("low"), NodeState.READY)
            self.assertEqual(scheduler.get_state("dependent"), NodeState.PENDING)

    def test_next_wave_empty_when_no_ready_nodes(self) -> None:
        """POSTCONDITION: next_wave returns an empty list when no node is READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """POSTCONDITION: mark_running updates the node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_unblocked_dependents(self) -> None:
        """POSTCONDITION: mark_succeeded updates state and promotes newly unblocked dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), None, 0, 0)
            dag.add_node("c", recording_action("c", calls), ["a", "b"], 0, 0)
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("c"), NodeState.PENDING)
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("b"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("c"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """POSTCONDITION: FAIL_FAST cancels every remaining non-terminal node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("c"), NodeState.CANCELLED)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """POSTCONDITION: SKIP_DOWNSTREAM skips transitive dependents of the failed node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            dag.add_node("d", recording_action("d", calls), None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a", "d"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["d"])
            self.assertFalse(scheduler.is_finished())

    def test_mark_failed_skip_downstream_marks_converging_dependent(self) -> None:
        """SKIP_DOWNSTREAM skips a converging dependent reached through two downstream paths."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["a"], 0, 0)
            dag.add_node("d", recording_action("d", calls), ["b", "c"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_continue_on_error_keeps_independent_nodes_eligible(self) -> None:
        """POSTCONDITION: CONTINUE_ON_ERROR skips blocked dependents but keeps independents eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("blocked", recording_action("blocked", calls), ["a"], 0, 0)
            dag.add_node("independent", recording_action("independent", calls), None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a", "independent"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("blocked"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["independent"])

    def test_is_finished_empty_dag(self) -> None:
        """POSTCONDITION: an empty DAG reports finished and exposes no states."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(dict(scheduler.get_all_states()), {})

    def test_is_finished_false_while_executable_nodes_remain(self) -> None:
        """POSTCONDITION: is_finished is False while an eligible node remains non-terminal."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_while_node_is_running(self) -> None:
        """is_finished reports unfinished while a node is in flight in the RUNNING state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_when_blocked_by_failure(self) -> None:
        """POSTCONDITION: is_finished is True when remaining nodes are blocked by failure."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_true_for_blocked_non_terminal_node(self) -> None:
        """is_finished reports finished when a non-terminal node is blocked by a failed dependency."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            # A node registered after the failure can never become eligible to execute.
            dag.add_node("late", recording_action("late", calls), ["a"], 0, 0)
            self.assertEqual(scheduler.get_state("late"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_get_state_of_missing_node_raises_node_not_found(self) -> None:
        """PRECONDITION: get_state raises NodeNotFoundError for an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError) as ctx:
                scheduler.get_state("ghost")
            self.assertEqual(ctx.exception.node_id, "ghost")

    def test_get_all_states_reflects_registered_nodes_only(self) -> None:
        """POSTCONDITION: get_all_states maps every currently registered node to its state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            states = scheduler.get_all_states()
            self.assertEqual(set(states), {"a", "b"})
            self.assertEqual(states["a"], NodeState.READY)
            self.assertEqual(states["b"], NodeState.PENDING)
            dag.remove_node("b")
            self.assertEqual(set(scheduler.get_all_states()), {"a"})


class DAGRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_executes_sequential_waves_and_reports_success(self) -> None:
        """POSTCONDITION: run executes ready waves sequentially and returns a consolidated report."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: List[str] = []
            dag.add_node("prepare", recording_action("prepare", calls, "prepared"), None, 0, 0)
            dag.add_node("publish", recording_action("publish", calls, "published"), ["prepare"], 0, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(calls, ["prepare", "publish"])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"prepare", "publish"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(set(report.results), {"prepare", "publish"})
            self.assertEqual(report.results["prepare"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["prepare"].value, "prepared")
            self.assertEqual(report.results["publish"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["publish"].value, "published")
            self.assertEqual(tuple(report.critical_path), ("prepare", "publish"))
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertGreaterEqual(report.results["prepare"].duration_seconds, 0.0)

    def test_run_retries_failed_actions(self) -> None:
        """POSTCONDITION: run retries a failed action up to the configured retry count."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            flaky = FlakyAction(failures=1, value="recovered")
            dag.add_node("flaky", flaky, None, 0, 1)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            result = report.results["flaky"]
            self.assertEqual(flaky.calls, 2)
            self.assertEqual(result.state, NodeState.SUCCEEDED)
            self.assertEqual(result.value, "recovered")
            self.assertEqual(result.retries_attempted, 1)
            self.assertEqual(set(report.succeeded_nodes), {"flaky"})

    def test_run_reports_failure_after_exhausting_retries(self) -> None:
        """POSTCONDITION: a node whose retries are exhausted is recorded as FAILED with its cause."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: List[str] = []
            error = RuntimeError("permanent failure")
            dag.add_node("doomed", failing_action("doomed", calls, error), None, 0, 2)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            result = report.results["doomed"]
            self.assertEqual(calls, ["doomed", "doomed", "doomed"])
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertIsNotNone(result.error)
            self.assertIn("permanent failure", str(result.error))
            self.assertEqual(result.retries_attempted, 2)
            self.assertEqual(set(report.failed_nodes), {"doomed"})

    def test_run_fail_fast_halts_and_cancels_remaining_nodes(self) -> None:
        """POSTCONDITION: FAIL_FAST halts execution and cancels pending downstream nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: List[str] = []
            error = RuntimeError("boom")
            dag.add_node("a", failing_action("a", calls, error), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            dag.add_node("d", recording_action("d", calls), ["a"], 0, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(calls, ["a"])
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.cancelled_nodes), {"b", "c", "d"})
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.results["a"].state, NodeState.FAILED)
            self.assertEqual(report.results["b"].state, NodeState.CANCELLED)
            self.assertEqual(report.results["c"].state, NodeState.CANCELLED)
            self.assertEqual(report.results["d"].state, NodeState.CANCELLED)

    def test_run_skip_downstream_skips_dependents_and_runs_independents(self) -> None:
        """POSTCONDITION: SKIP_DOWNSTREAM skips transitive dependents while independents execute."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: List[str] = []
            error = RuntimeError("boom")
            dag.add_node("a", failing_action("a", calls, error), None, 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            dag.add_node("c", recording_action("c", calls), ["b"], 0, 0)
            dag.add_node("independent", recording_action("independent", calls), None, 0, 0)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.skipped_nodes), {"b", "c"})
            self.assertEqual(set(report.succeeded_nodes), {"independent"})
            self.assertIn("independent", calls)
            self.assertNotIn("b", calls)
            self.assertNotIn("c", calls)
            self.assertEqual(report.results["b"].state, NodeState.SKIPPED)
            self.assertEqual(report.results["c"].state, NodeState.SKIPPED)

    def test_run_validates_missing_dependencies_before_waves(self) -> None:
        """PRECONDITION: run raises NodeNotFoundError before executing any node action."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: List[str] = []
            dag.add_node("child", recording_action("child", calls), ["ghost"], 0, 0)
            with self.assertRaises(NodeNotFoundError):
                runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(calls, [])

    def test_run_raises_cycle_error_for_cyclic_graph(self) -> None:
        """PRECONDITION: run raises CycleError for a cyclic graph without executing actions."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: List[str] = []
            dag.add_node("a", recording_action("a", calls), ["b"], 0, 0)
            dag.add_node("b", recording_action("b", calls), ["a"], 0, 0)
            with self.assertRaises(CycleError) as ctx:
                runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(set(ctx.exception.cycle), {"a", "b"})
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:32:34Z
# LAST_CHANGED: 2026-11-08T06:08:32Z
# CHANGE: Add coverage for converging SKIP_DOWNSTREAM dependents (a->b,a->c,b->d,c->d), RUNNING-state is_finished false, non-terminal node blocked by failed dependency, and empty-DAG critical path (empty sequence, zero weight).
# COVERAGE_AUDIT: 2026-11-08T06:32:34Z
# QA_AUDIT: 2026-11-08T06:32:16Z
# --- END AUTOFAB METADATA ---
