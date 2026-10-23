"""Unit tests for the synchronous DAG execution and wave scheduling engine.

Every test asserts an explicit postcondition contracted by
``low/dag_engine_lite.pyi`` or ``low/dag_engine_lite_impl.pyi``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, cast
import unittest

from support.lib.lifecycle import LifecycleRegistry, begin_phase, system
from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def _returning(value: Any) -> Callable[[], Any]:
    """Builds a zero-argument node action returning ``value``."""

    def action() -> Any:
        return value

    return action


class _EngineTestCase(unittest.TestCase):
    """Shared fixture that resolves the engine singletons in an isolated phase."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.scope = begin_phase(system, registry=self.registry)
        self.addCleanup(self.scope.close)
        self.dag = self.scope.get_singleton(DAG)

    def _scheduler(self) -> WaveScheduler:
        return self.scope.get_singleton(WaveScheduler)

    def _runner(self) -> DAGRunner:
        return self.scope.get_singleton(DAGRunner)


class DataTypeTest(unittest.TestCase):
    """Tests for the passive data types and exceptions."""

    def test_error_hierarchy_exposes_message(self) -> None:
        cause = RuntimeError("root cause")
        errors = [
            dag_engine_lite.DAGError("base error"),
            dag_engine_lite.CycleError("cycle error", cycle=("a", "b", "a")),
            dag_engine_lite.NodeNotFoundError("missing error", node_id="a"),
            dag_engine_lite.NodeExecutionError(
                "execution error", node_id="a", cause=cause
            ),
        ]

        for error in errors:
            self.assertIsInstance(error, dag_engine_lite.DAGError)
            self.assertEqual(str(error), error.message)

        cycle_error = errors[1]
        self.assertIsInstance(cycle_error, dag_engine_lite.CycleError)
        self.assertEqual(cycle_error.cycle, ("a", "b", "a"))

        not_found_error = errors[2]
        self.assertIsInstance(not_found_error, dag_engine_lite.NodeNotFoundError)
        self.assertEqual(not_found_error.node_id, "a")

        execution_error = errors[3]
        self.assertIsInstance(execution_error, dag_engine_lite.NodeExecutionError)
        self.assertEqual(execution_error.node_id, "a")
        self.assertIs(execution_error.cause, cause)

    def test_enum_values(self) -> None:
        self.assertEqual(
            [state.value for state in dag_engine_lite.NodeState],
            [
                "pending",
                "ready",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                "skipped",
            ],
        )
        self.assertEqual(
            [policy.value for policy in dag_engine_lite.FailurePolicy],
            ["fail_fast", "continue_on_error", "skip_downstream"],
        )

    def test_node_definition_and_result_defaults(self) -> None:
        definition: dag_engine_lite.NodeDefinition[int] = (
            dag_engine_lite.NodeDefinition(
                node_id="node",
                action=lambda: 7,
                dependencies=frozenset({"upstream"}),
            )
        )
        self.assertEqual(definition.node_id, "node")
        self.assertEqual(definition.dependencies, frozenset({"upstream"}))
        self.assertEqual(definition.priority, 0)
        self.assertEqual(definition.retries, 0)
        self.assertEqual(definition.action(), 7)

        result: dag_engine_lite.NodeResult[int] = dag_engine_lite.NodeResult(
            node_id="node",
            state=dag_engine_lite.NodeState.SUCCEEDED,
        )
        self.assertIsNone(result.value)
        self.assertIsNone(result.error)
        self.assertEqual(result.duration_seconds, 0.0)
        self.assertEqual(result.retries_attempted, 0)

    def test_initialize_uses_default_registry(self) -> None:
        __initialize__(None)


class DAGTest(_EngineTestCase):
    """Tests for graph construction, inspection, validation, and analysis."""

    def test_add_node_with_defaults(self) -> None:
        action = _returning("value")
        self.dag.add_node("solo", action)

        self.assertTrue(self.dag.has_node("solo"))
        self.assertFalse(self.dag.has_node("absent"))
        definition = self.dag.get_node("solo")
        self.assertEqual(definition.node_id, "solo")
        self.assertIs(definition.action, action)
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.priority, 0)
        self.assertEqual(definition.retries, 0)
        self.assertEqual(self.dag.get_dependencies("solo"), set())
        self.assertEqual(self.dag.get_dependents("solo"), set())
        self.assertEqual(self.dag.all_nodes(), {"solo"})

    def test_add_node_with_dependencies_and_options(self) -> None:
        self.dag.add_node("upstream", _returning(1))
        self.dag.add_node(
            "downstream",
            _returning(2),
            dependencies=["upstream"],
            priority=4,
            retries=3,
        )

        definition = self.dag.get_node("downstream")
        self.assertEqual(definition.dependencies, frozenset({"upstream"}))
        self.assertEqual(definition.priority, 4)
        self.assertEqual(definition.retries, 3)
        self.assertEqual(self.dag.get_dependencies("downstream"), {"upstream"})
        self.assertEqual(self.dag.get_dependents("upstream"), {"downstream"})

    def test_add_node_reuses_existing_neighbor_sets(self) -> None:
        self.dag.add_node("upstream", _returning(1))
        self.dag.add_node("downstream", _returning(2), dependencies=["upstream"])
        self.dag.add_node("upstream", _returning(3))

        self.assertTrue(self.dag.has_node("upstream"))
        self.assertEqual(self.dag.get_dependents("upstream"), {"downstream"})

    def test_add_node_with_missing_dependency_is_rejected_by_validate(self) -> None:
        self.dag.add_node("downstream", _returning(1), dependencies=["missing"])

        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.validate()
        self.assertEqual(raised.exception.node_id, "missing")

    def test_add_edge_updates_adjacency_and_definition(self) -> None:
        self.dag.add_node("upstream", _returning(1))
        self.dag.add_node("downstream", _returning(2))

        self.dag.add_edge("upstream", "downstream")

        self.assertEqual(self.dag.get_dependencies("downstream"), {"upstream"})
        self.assertEqual(self.dag.get_dependents("upstream"), {"downstream"})
        self.assertEqual(
            self.dag.get_node("downstream").dependencies, frozenset({"upstream"})
        )

    def test_add_edge_missing_upstream_raises(self) -> None:
        self.dag.add_node("downstream", _returning(1))

        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.add_edge("missing", "downstream")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_add_edge_missing_downstream_raises(self) -> None:
        self.dag.add_node("upstream", _returning(1))

        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.add_edge("upstream", "missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_remove_node_clears_incident_edges(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])

        self.dag.remove_node("b")

        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a", "c"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertEqual(self.dag.get_node("c").dependencies, frozenset())

    def test_remove_node_missing_raises(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.remove_node("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_get_node_missing_raises(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.get_node("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_get_dependencies_missing_raises(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.get_dependencies("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_get_dependents_missing_raises(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self.dag.get_dependents("missing")
        self.assertEqual(raised.exception.node_id, "missing")

    def test_query_results_are_copies(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])

        dependencies = self.dag.get_dependencies("b")
        dependents = self.dag.get_dependents("a")
        nodes = self.dag.all_nodes()
        dependencies.clear()
        dependents.clear()
        nodes.clear()

        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        self.dag.add_node("root_a", _returning(1))
        self.dag.add_node("root_b", _returning(2))
        self.dag.add_node("middle", _returning(3), dependencies=["root_a", "root_b"])
        self.dag.add_node("leaf", _returning(4), dependencies=["middle"])

        self.assertEqual(self.dag.find_roots(), {"root_a", "root_b"})
        self.assertEqual(self.dag.find_leaves(), {"leaf"})

    def test_find_roots_and_leaves_empty_graph(self) -> None:
        self.assertEqual(self.dag.find_roots(), set())
        self.assertEqual(self.dag.find_leaves(), set())

    def test_validate_accepts_acyclic_graph(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])

        self.assertIsNone(self.dag.validate())

    def test_validate_accepts_shared_dependent(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_node("c", _returning(3), dependencies=["a", "b"])

        self.assertIsNone(self.dag.validate())

    def test_validate_detects_cycle_with_sequence(self) -> None:
        self.dag.add_node("step_1", _returning(1))
        self.dag.add_node("step_2", _returning(2), dependencies=["step_1"])
        self.dag.add_edge("step_2", "step_1")

        with self.assertRaises(dag_engine_lite.CycleError) as raised:
            self.dag.validate()
        self.assertEqual(raised.exception.cycle, ("step_1", "step_2", "step_1"))

    def test_topological_sort_linear_graph(self) -> None:
        self.dag.add_node("task_a", _returning(1))
        self.dag.add_node("task_b", _returning(2), dependencies=["task_a"])

        self.assertEqual(self.dag.topological_sort(), ["task_a", "task_b"])

    def test_topological_sort_orders_ready_by_priority_then_name(self) -> None:
        self.dag.add_node("low", _returning(1), priority=5)
        self.dag.add_node("high", _returning(2), priority=10)
        self.dag.add_node("mid", _returning(3), priority=5)

        self.assertEqual(self.dag.topological_sort(), ["high", "low", "mid"])

    def test_topological_sort_reorders_newly_ready_nodes(self) -> None:
        self.dag.add_node("z", _returning(1), priority=10)
        self.dag.add_node("a", _returning(2), priority=10)
        self.dag.add_node("m", _returning(3), priority=5)
        self.dag.add_node("d", _returning(4), dependencies=["z", "a"], priority=20)

        self.assertEqual(self.dag.topological_sort(), ["a", "z", "d", "m"])

    def test_topological_sort_waits_for_all_dependencies(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_node("c", _returning(3), dependencies=["a", "b"])

        self.assertEqual(self.dag.topological_sort(), ["a", "b", "c"])

    def test_topological_sort_empty_graph(self) -> None:
        self.assertEqual(self.dag.topological_sort(), [])

    def test_topological_sort_cycle_raises(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")

        with self.assertRaises(dag_engine_lite.CycleError) as raised:
            self.dag.topological_sort()
        self.assertEqual(set(raised.exception.cycle), {"a", "b"})

    def test_compute_critical_path_empty_graph(self) -> None:
        self.assertEqual(self.dag.compute_critical_path(), ([], 0.0))

    def test_compute_critical_path_single_node(self) -> None:
        self.dag.add_node("only", _returning(1))

        self.assertEqual(self.dag.compute_critical_path(), (["only"], 1.0))

    def test_compute_critical_path_default_weights(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["b"])

        path, weight = self.dag.compute_critical_path()

        self.assertEqual(path, ["a", "b", "c"])
        self.assertAlmostEqual(weight, 3.0)

    def test_compute_critical_path_weighted_scenario(self) -> None:
        self.dag.add_node("node_start", _returning(1))
        self.dag.add_node("node_branch", _returning(2), dependencies=["node_start"])
        self.dag.add_node("node_end", _returning(3), dependencies=["node_branch"])

        path, weight = self.dag.compute_critical_path(
            {"node_start": 2.5, "node_branch": 4.0, "node_end": 1.5}
        )

        self.assertEqual(path, ["node_start", "node_branch", "node_end"])
        self.assertAlmostEqual(weight, 8.0)

    def test_compute_critical_path_selects_heaviest_branch(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        self.dag.add_node("c", _returning(3), dependencies=["a"])

        path, weight = self.dag.compute_critical_path(
            {"a": 1.0, "b": 4.0, "c": 1.0}
        )

        self.assertEqual(path, ["a", "b"])
        self.assertAlmostEqual(weight, 5.0)

    def test_compute_critical_path_chooses_heaviest_predecessor(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_node("c", _returning(3), dependencies=["a", "b"])

        path, weight = self.dag.compute_critical_path(
            {"a": 1.0, "b": 3.0, "c": 2.0}
        )

        self.assertEqual(path, ["b", "c"])
        self.assertAlmostEqual(weight, 5.0)


class WaveSchedulerTest(_EngineTestCase):
    """Tests for state synchronization, wave ordering, and failure policies."""

    def test_initial_states(self) -> None:
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["root"])
        scheduler = self._scheduler()

        states = scheduler.get_all_states()

        self.assertEqual(states["root"], dag_engine_lite.NodeState.READY)
        self.assertEqual(states["child"], dag_engine_lite.NodeState.PENDING)

    def test_next_wave_orders_by_priority_then_identifier(self) -> None:
        self.dag.add_node("task_low", _returning(1), priority=5)
        self.dag.add_node("task_high", _returning(2), priority=10)
        self.dag.add_node("task_mid", _returning(3), priority=5)
        scheduler = self._scheduler()

        self.assertEqual(
            scheduler.next_wave(), ["task_high", "task_low", "task_mid"]
        )

    def test_next_wave_returns_empty_when_nothing_ready(self) -> None:
        self.dag.add_node("only", _returning(1))
        scheduler = self._scheduler()
        scheduler.mark_running("only")

        self.assertEqual(scheduler.next_wave(), [])

    def test_next_wave_empty_graph(self) -> None:
        self.assertEqual(self._scheduler().next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        self.dag.add_node("only", _returning(1))
        scheduler = self._scheduler()

        scheduler.mark_running("only")

        self.assertEqual(
            scheduler.get_state("only"), dag_engine_lite.NodeState.RUNNING
        )

    def test_mark_succeeded_promotes_unblocked_dependents(self) -> None:
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["root"])
        scheduler = self._scheduler()

        scheduler.mark_succeeded("root")

        self.assertEqual(
            scheduler.get_state("root"), dag_engine_lite.NodeState.SUCCEEDED
        )
        self.assertEqual(
            scheduler.get_state("child"), dag_engine_lite.NodeState.READY
        )
        self.assertEqual(scheduler.next_wave(), ["child"])

    def test_mark_succeeded_waits_for_all_dependencies(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2))
        self.dag.add_node("joined", _returning(3), dependencies=["a", "b"])
        scheduler = self._scheduler()

        scheduler.mark_succeeded("a")
        self.assertEqual(
            scheduler.get_state("joined"), dag_engine_lite.NodeState.PENDING
        )

        scheduler.mark_succeeded("b")
        self.assertEqual(
            scheduler.get_state("joined"), dag_engine_lite.NodeState.READY
        )

        scheduler.mark_succeeded("a")
        self.assertEqual(
            scheduler.get_state("joined"), dag_engine_lite.NodeState.READY
        )

    def test_state_sync_discovers_new_and_removed_nodes(self) -> None:
        scheduler = self._scheduler()
        self.dag.add_node("transient", _returning(1))
        self.assertIn("transient", scheduler.get_all_states())

        self.dag.remove_node("transient")

        self.assertNotIn("transient", scheduler.get_all_states())
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            scheduler.get_state("transient")
        self.assertEqual(raised.exception.node_id, "transient")

    def test_mark_failed_fail_fast_cancels_non_terminal_nodes(self) -> None:
        self.dag.add_node("bad", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["bad"])
        self.dag.add_node("good", _returning(3))
        self.dag.add_node("good_child", _returning(4), dependencies=["good"])
        scheduler = self._scheduler()
        scheduler.mark_succeeded("good")

        scheduler.mark_failed("bad")

        self.assertEqual(
            scheduler.get_state("bad"), dag_engine_lite.NodeState.FAILED
        )
        self.assertEqual(
            scheduler.get_state("good"), dag_engine_lite.NodeState.SUCCEEDED
        )
        self.assertEqual(
            scheduler.get_state("child"), dag_engine_lite.NodeState.CANCELLED
        )
        self.assertEqual(
            scheduler.get_state("good_child"),
            dag_engine_lite.NodeState.CANCELLED,
        )
        self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_marks_transitive_dependents(self) -> None:
        self.dag.add_node("grandparent", _returning(1))
        self.dag.add_node("parent", _returning(2), dependencies=["grandparent"])
        self.dag.add_node("child", _returning(3), dependencies=["parent"])
        self.dag.add_node("independent", _returning(4))
        scheduler = self._scheduler()

        scheduler.mark_failed(
            "grandparent", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )

        self.assertEqual(
            scheduler.get_state("grandparent"), dag_engine_lite.NodeState.FAILED
        )
        self.assertEqual(
            scheduler.get_state("parent"), dag_engine_lite.NodeState.SKIPPED
        )
        self.assertEqual(
            scheduler.get_state("child"), dag_engine_lite.NodeState.SKIPPED
        )
        self.assertEqual(
            scheduler.get_state("independent"), dag_engine_lite.NodeState.READY
        )
        self.assertFalse(scheduler.is_finished())

        scheduler.mark_succeeded("independent")
        self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_handles_diamond_once(self) -> None:
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("left", _returning(2), dependencies=["root"])
        self.dag.add_node("right", _returning(3), dependencies=["root"])
        self.dag.add_node("join", _returning(4), dependencies=["left", "right"])
        scheduler = self._scheduler()

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

    def test_mark_failed_skip_downstream_preserves_terminal_dependent(self) -> None:
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("child", _returning(2), dependencies=["root"])
        scheduler = self._scheduler()
        scheduler.mark_succeeded("child")

        scheduler.mark_failed(
            "root", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )

        self.assertEqual(
            scheduler.get_state("child"), dag_engine_lite.NodeState.SUCCEEDED
        )

    def test_mark_failed_continue_on_error_leaves_independent_ready(self) -> None:
        self.dag.add_node("bad", _returning(1))
        self.dag.add_node("other", _returning(2))
        scheduler = self._scheduler()

        scheduler.mark_failed(
            "bad", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )

        self.assertEqual(
            scheduler.get_state("bad"), dag_engine_lite.NodeState.FAILED
        )
        self.assertEqual(
            scheduler.get_state("other"), dag_engine_lite.NodeState.READY
        )
        self.assertEqual(scheduler.next_wave(), ["other"])
        self.assertFalse(scheduler.is_finished())

    def test_is_finished_empty_graph(self) -> None:
        self.assertTrue(self._scheduler().is_finished())

    def test_is_finished_requires_all_nodes_terminal(self) -> None:
        self.dag.add_node("a", _returning(1))
        self.dag.add_node("b", _returning(2), dependencies=["a"])
        scheduler = self._scheduler()

        self.assertFalse(scheduler.is_finished())
        scheduler.mark_succeeded("a")
        self.assertFalse(scheduler.is_finished())
        scheduler.mark_succeeded("b")
        self.assertTrue(scheduler.is_finished())

    def test_get_all_states_returns_a_copy(self) -> None:
        self.dag.add_node("only", _returning(1))
        scheduler = self._scheduler()

        states = cast(Dict[str, dag_engine_lite.NodeState], scheduler.get_all_states())
        states["only"] = dag_engine_lite.NodeState.FAILED

        self.assertEqual(
            scheduler.get_all_states()["only"], dag_engine_lite.NodeState.READY
        )


class DAGRunnerTest(_EngineTestCase):
    """Tests for sequential execution, retries, and run report compilation."""

    def test_run_empty_dag(self) -> None:
        report = self._runner().run()

        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.critical_path, ())
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(report.results, {})

    def test_run_validates_graph_before_execution(self) -> None:
        self.dag.add_node("broken", _returning(1), dependencies=["missing"])

        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as raised:
            self._runner().run()
        self.assertEqual(raised.exception.node_id, "missing")

    def test_run_rejects_cyclic_graph_before_execution(self) -> None:
        executed: List[str] = []

        def action() -> None:
            executed.append("ran")

        self.dag.add_node("a", action)
        self.dag.add_node("b", action)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")

        with self.assertRaises(dag_engine_lite.CycleError):
            self._runner().run()
        self.assertEqual(executed, [])

    def test_run_executes_dependency_chain(self) -> None:
        executed: List[str] = []

        def first() -> str:
            executed.append("a")
            return "value_a"

        def second() -> str:
            executed.append("b")
            return "value_b"

        self.dag.add_node("a", first)
        self.dag.add_node("b", second, dependencies=["a"])

        report = self._runner().run()

        self.assertEqual(executed, ["a", "b"])
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("a", "b"))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.critical_path, ("a", "b"))
        self.assertEqual(
            report.results["a"].state, dag_engine_lite.NodeState.SUCCEEDED
        )
        self.assertEqual(report.results["a"].value, "value_a")
        self.assertEqual(report.results["b"].value, "value_b")
        self.assertGreaterEqual(report.results["a"].duration_seconds, 0.0)

    def test_run_executes_diamond_graph(self) -> None:
        self.dag.add_node("root", _returning(1))
        self.dag.add_node("left", _returning(2), dependencies=["root"])
        self.dag.add_node("right", _returning(3), dependencies=["root"])
        self.dag.add_node("join", _returning(4), dependencies=["left", "right"])

        report = self._runner().run()

        self.assertEqual(report.total_nodes, 4)
        self.assertEqual(set(report.succeeded_nodes), {"root", "left", "right", "join"})
        self.assertEqual(report.critical_path[0], "root")
        self.assertEqual(report.critical_path[-1], "join")
        self.assertEqual(len(report.critical_path), 3)

    def test_run_retries_until_action_succeeds(self) -> None:
        attempts: List[int] = []

        def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient")
            return "recovered"

        self.dag.add_node("flaky", flaky, retries=2)

        report = self._runner().run()

        self.assertEqual(len(attempts), 3)
        self.assertEqual(report.succeeded_nodes, ("flaky",))
        self.assertEqual(report.results["flaky"].value, "recovered")
        self.assertEqual(report.results["flaky"].retries_attempted, 2)

    def test_run_records_exhausted_failure_and_cancels_under_fail_fast(self) -> None:
        attempts: List[int] = []

        def always_failing() -> None:
            attempts.append(1)
            raise TypeError("persistent")

        self.dag.add_node("bad", always_failing, retries=1)
        self.dag.add_node("child", _returning(2), dependencies=["bad"])
        self.dag.add_node("independent", _returning(3))

        report = self._runner().run()

        self.assertEqual(len(attempts), 2)
        self.assertEqual(report.failed_nodes, ("bad",))
        self.assertEqual(set(report.cancelled_nodes), {"child", "independent"})
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.results["bad"].retries_attempted, 1)
        self.assertIsInstance(report.results["bad"].error, TypeError)
        self.assertEqual(
            report.results["child"].state, dag_engine_lite.NodeState.CANCELLED
        )

    def test_run_fail_fast_halts_remaining_wave(self) -> None:
        executed: List[str] = []

        def failing() -> None:
            executed.append("bad")
            raise ValueError("boom")

        def independent() -> None:
            executed.append("independent")

        self.dag.add_node("bad", failing)
        self.dag.add_node("independent", independent)
        self.dag.add_node("child", _returning(1), dependencies=["bad"])

        report = self._runner().run(
            failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST
        )

        self.assertEqual(executed, ["bad"])
        self.assertEqual(report.failed_nodes, ("bad",))
        self.assertEqual(set(report.cancelled_nodes), {"independent", "child"})

    def test_run_defaults_to_fail_fast(self) -> None:
        def failing() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("bad", failing)
        self.dag.add_node("child", _returning(1), dependencies=["bad"])

        report = self._runner().run()

        self.assertEqual(report.failed_nodes, ("bad",))
        self.assertEqual(report.cancelled_nodes, ("child",))

    def test_run_continue_on_error_breaks_on_empty_wave(self) -> None:
        def failing() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("bad", failing)
        self.dag.add_node("blocked", _returning(1), dependencies=["bad"])
        self.dag.add_node("independent", _returning(2))

        report = self._runner().run(
            failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )

        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.failed_nodes, ("bad",))
        self.assertEqual(report.succeeded_nodes, ("independent",))
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertNotIn("blocked", report.results)

    def test_run_skip_downstream_marks_transitive_dependents(self) -> None:
        def failing() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("bad", failing)
        self.dag.add_node("child", _returning(1), dependencies=["bad"])
        self.dag.add_node("grandchild", _returning(2), dependencies=["child"])
        self.dag.add_node("independent", _returning(3))

        report = self._runner().run(
            failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )

        self.assertEqual(report.failed_nodes, ("bad",))
        self.assertEqual(set(report.skipped_nodes), {"child", "grandchild"})
        self.assertEqual(report.succeeded_nodes, ("independent",))
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(
            report.results["child"].state, dag_engine_lite.NodeState.SKIPPED
        )
        self.assertEqual(
            report.results["grandchild"].state, dag_engine_lite.NodeState.SKIPPED
        )


if __name__ == "__main__":
    unittest.main()
