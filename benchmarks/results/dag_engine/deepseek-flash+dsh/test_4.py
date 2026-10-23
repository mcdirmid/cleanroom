"""Unit tests for the DAG execution and wave scheduling engine.

The suite verifies the concrete ``DAG``, ``WaveScheduler`` and ``DAGRunner``
singletons, together with their immutable data types, against the postconditions
and invariants contracted in ``low/dag_engine.pyi`` and ``low/dag_engine_impl.pyi``.
Every lifecycle-managed interaction executes inside an isolated system-tier
phase scope so singleton state never leaks between test methods.
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any, List, Optional

from benchmark_2.parts.dag_engine.lib import dag_engine
from benchmark_2.parts.dag_engine.lib import dag_engine_impl
from benchmark_2.parts.dag_engine.lib.dag_engine_impl import DAG, DAGRunner, WaveScheduler
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class _RecordingAction:
    """Action test double that records execution and returns a scripted value."""

    def __init__(self, name: str, record: List[str], value: Any = None) -> None:
        self.name = name
        self.record = record
        self.value = value

    def __call__(self) -> Any:
        self.record.append(self.name)
        return self.value


class _FlakyAction:
    """Action test double that raises for a fixed number of attempts."""

    def __init__(self, failures: int, value: Any = None) -> None:
        self.failures = failures
        self.value = value
        self.attempts = 0

    def __call__(self) -> Any:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise ValueError(f"attempt {self.attempts} failed")
        return self.value


class _CancellingAction:
    """Action test double that requests runner cancellation synchronously while executing."""

    def __init__(self) -> None:
        self.runner: Optional[DAGRunner] = None
        self.executions = 0

    def __call__(self) -> str:
        self.executions += 1
        runner = self.runner
        assert runner is not None
        runner.cancel()
        return "cancelled"


class _BlockingAction:
    """Action test double that stays in flight until the test releases it."""

    def __init__(self, wait_timeout: float = 3.0) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = False
        self.wait_timeout = wait_timeout

    def __call__(self) -> str:
        self.started.set()
        self.release.wait(timeout=self.wait_timeout)
        self.finished = True
        return "finished"


def _raise_value_error() -> Any:
    """Action test double that always fails with a ``ValueError``."""
    raise ValueError("action failed")


class DAGTest(unittest.TestCase):
    """Verifies dag_engine.DAG postconditions from low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        dag_engine_impl.__initialize__(self.registry)

    def test_add_node_registers_definition_and_dependency_edges(self) -> None:
        """POSTCONDITIONS: register the node definition and add dependency edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", lambda: None)
            dag.add_node(
                "downstream",
                lambda: "value",
                dependencies=["upstream"],
                priority=3,
                timeout_seconds=1.5,
                retries=2,
            )
            self.assertTrue(dag.has_node("downstream"))
            definition = dag.get_node("downstream")
            self.assertEqual(definition.node_id, "downstream")
            self.assertEqual(definition.dependencies, frozenset({"upstream"}))
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.timeout_seconds, 1.5)
            self.assertEqual(definition.retries, 2)
            self.assertEqual(definition.action(), "value")
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})
            self.assertEqual(dag.all_nodes(), {"upstream", "downstream"})

    def test_add_node_without_dependencies_registers_isolated_node(self) -> None:
        """POSTCONDITIONS: a node registered without dependencies is a root and leaf."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("solo", lambda: None)
            self.assertEqual(dag.get_dependencies("solo"), set())
            self.assertEqual(dag.get_dependents("solo"), set())
            self.assertEqual(dag.find_roots(), {"solo"})
            self.assertEqual(dag.find_leaves(), {"solo"})

    def test_add_edge_establishes_dependency(self) -> None:
        """POSTCONDITIONS: MUST establish a directed dependency edge from upstream to downstream."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", lambda: None)
            dag.add_node("down", lambda: None)
            dag.add_edge("up", "down")
            self.assertEqual(dag.get_dependencies("down"), {"up"})
            self.assertEqual(dag.get_dependents("up"), {"down"})
            self.assertEqual(dag.topological_sort(), ["up", "down"])
            self.assertIsNone(dag.validate())

    def test_add_edge_raises_node_not_found_for_unknown_nodes(self) -> None:
        """WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("known", lambda: None)
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.add_edge("missing", "known")
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.add_edge("known", "missing")
            self.assertEqual(dag.get_dependencies("known"), set())
            self.assertEqual(dag.get_dependents("known"), set())

    def test_remove_node_removes_incident_edges(self) -> None:
        """POSTCONDITIONS: MUST remove the node and all of its incident edges."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: None)
            dag.add_node("second", lambda: None, dependencies=["first"])
            dag.add_node("third", lambda: None, dependencies=["second"])
            dag.remove_node("second")
            self.assertFalse(dag.has_node("second"))
            self.assertEqual(dag.all_nodes(), {"first", "third"})
            self.assertEqual(dag.get_dependencies("third"), set())
            self.assertEqual(dag.get_dependents("first"), set())
            self.assertEqual(dag.find_leaves(), {"first", "third"})

    def test_remove_node_raises_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine.NodeNotFoundError) as context:
                dag.remove_node("ghost")
            self.assertEqual(context.exception.node_id, "ghost")

    def test_get_node_raises_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine.NodeNotFoundError) as context:
                dag.get_node("ghost")
            self.assertEqual(context.exception.node_id, "ghost")

    def test_dependency_queries_raise_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError for both queries."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.get_dependencies("ghost")
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.get_dependents("ghost")

    def test_has_node_reports_membership(self) -> None:
        """has_node reports False for unknown identifiers and True for registered nodes."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("present"))
            dag.add_node("present", lambda: None)
            self.assertTrue(dag.has_node("present"))
            self.assertFalse(dag.has_node("ghost"))

    def test_queries_return_defensive_copies(self) -> None:
        """GROUNDING: dependents, dependencies and node sets are returned as copies."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", lambda: None)
            dag.add_node("down", lambda: None, dependencies=["up"])
            dependencies = dag.get_dependencies("down")
            dependencies.add("injected")
            self.assertEqual(dag.get_dependencies("down"), {"up"})
            dependents = dag.get_dependents("up")
            dependents.add("injected")
            self.assertEqual(dag.get_dependents("up"), {"down"})
            nodes = dag.all_nodes()
            nodes.add("injected")
            self.assertEqual(dag.all_nodes(), {"up", "down"})

    def test_validate_accepts_acyclic_graph(self) -> None:
        """WHEN all referenced nodes exist and no cycle exists, MUST complete without error."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            self.assertIsNone(dag.validate())

    def test_validate_raises_for_missing_dependency(self) -> None:
        """WHEN a dependency node is missing, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("child", lambda: None, dependencies=["ghost"])
            with self.assertRaises(dag_engine.NodeNotFoundError):
                dag.validate()

    def test_validate_raises_cycle_error(self) -> None:
        """WHEN a cycle exists, MUST raise CycleError containing the cycle sequence."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine.CycleError) as context:
                dag.validate()
            cycle = context.exception.cycle
            self.assertIsInstance(cycle, tuple)
            self.assertEqual(set(cycle), {"a", "b"})

    def test_topological_sort_orders_prerequisites_first(self) -> None:
        """POSTCONDITIONS: every prerequisite MUST precede its dependents."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("middle", lambda: None, dependencies=["root"])
            dag.add_node("leaf", lambda: None, dependencies=["middle"])
            self.assertEqual(dag.topological_sort(), ["root", "middle", "leaf"])

    def test_topological_sort_breaks_ties_by_priority_then_name(self) -> None:
        """POSTCONDITIONS: MUST order concurrent ready nodes by priority desc, name asc."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("alpha", lambda: None, priority=1)
            dag.add_node("beta", lambda: None, priority=5)
            dag.add_node("gamma", lambda: None, priority=1)
            self.assertEqual(dag.topological_sort(), ["beta", "alpha", "gamma"])

    def test_topological_sort_raises_cycle_error(self) -> None:
        """WHEN a cycle exists, MUST raise CycleError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine.CycleError) as context:
                dag.topological_sort()
            self.assertEqual(set(context.exception.cycle), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        """find_roots returns in-degree zero nodes; find_leaves returns out-degree zero nodes."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_node("c", lambda: None, dependencies=["b"])
            dag.add_node("isolated", lambda: None)
            self.assertEqual(dag.find_roots(), {"a", "isolated"})
            self.assertEqual(dag.find_leaves(), {"c", "isolated"})

    def test_find_roots_and_leaves_of_empty_graph(self) -> None:
        """An empty graph has no roots, no leaves and an empty topological order."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.find_roots(), set())
            self.assertEqual(dag.find_leaves(), set())
            self.assertEqual(dag.topological_sort(), [])

    def test_compute_critical_path_default_weights(self) -> None:
        """POSTCONDITIONS: MUST return the longest path and its cumulative default weight."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None, dependencies=["a"])
            dag.add_node("c", lambda: None, dependencies=["b"])
            path, total = dag.compute_critical_path()
            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(total, 3.0)

    def test_compute_critical_path_uses_estimated_durations(self) -> None:
        """POSTCONDITIONS: node weights come from estimated_durations when provided."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("heavy", lambda: None)
            dag.add_node("light", lambda: None)
            dag.add_node("sink", lambda: None, dependencies=["heavy", "light"])
            path, total = dag.compute_critical_path(
                {"heavy": 5.0, "light": 2.0, "sink": 1.0}
            )
            self.assertEqual(path, ["heavy", "sink"])
            self.assertAlmostEqual(total, 6.0)

    def test_compute_critical_path_of_empty_graph(self) -> None:
        """POSTCONDITIONS: an empty DAG yields an empty path and zero cumulative weight."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            path, total = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertAlmostEqual(total, 0.0)
            weighted_path, weighted_total = dag.compute_critical_path({})
            self.assertEqual(weighted_path, [])
            self.assertAlmostEqual(weighted_total, 0.0)

    def test_add_node_supports_concurrent_mutation(self) -> None:
        """GROUNDING: graph mutations are synchronized for thread safety."""

        def add_batch(prefix: str) -> None:
            for index in range(10):
                dag.add_node(f"{prefix}_{index}", lambda: None)

        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            threads = [
                threading.Thread(target=add_batch, args=(f"worker{worker}",))
                for worker in range(4)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(dag.all_nodes()), 40)


class DAGDataTypeTest(unittest.TestCase):
    """Verifies the immutable data type contracts from low/dag_engine.pyi."""

    def test_node_definition_defaults(self) -> None:
        """NodeDefinition defaults: priority 0, no timeout and no retries."""
        definition = dag_engine.NodeDefinition[str](
            node_id="node",
            action=lambda: "value",
            dependencies=frozenset({"upstream"}),
        )
        self.assertEqual(definition.node_id, "node")
        self.assertEqual(definition.dependencies, frozenset({"upstream"}))
        self.assertEqual(definition.priority, 0)
        self.assertIsNone(definition.timeout_seconds)
        self.assertEqual(definition.retries, 0)

    def test_node_result_defaults(self) -> None:
        """NodeResult defaults: no error, zero duration and zero retries."""
        result = dag_engine.NodeResult[str](
            node_id="node",
            state=dag_engine.NodeState.SUCCEEDED,
            value="value",
        )
        self.assertIsNone(result.error)
        self.assertEqual(result.duration_seconds, 0.0)
        self.assertEqual(result.retries_attempted, 0)

    def test_node_not_found_error_carries_node_id(self) -> None:
        """NodeNotFoundError exposes the missing identifier and message."""
        error = dag_engine.NodeNotFoundError(message="missing", node_id="ghost")
        self.assertIsInstance(error, dag_engine.DAGError)
        self.assertEqual(error.message, "missing")
        self.assertEqual(error.node_id, "ghost")

    def test_cycle_error_carries_cycle(self) -> None:
        """CycleError exposes the cycle sequence and message."""
        error = dag_engine.CycleError(message="cycle", cycle=("a", "b"))
        self.assertIsInstance(error, dag_engine.DAGError)
        self.assertEqual(error.message, "cycle")
        self.assertEqual(error.cycle, ("a", "b"))


class WaveSchedulerTest(unittest.TestCase):
    """Verifies dag_engine.WaveScheduler postconditions from low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        dag_engine_impl.__initialize__(self.registry)

    def test_next_wave_returns_ready_roots_ordered_by_priority(self) -> None:
        """POSTCONDITIONS: order ready nodes by priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("alpha", lambda: None, priority=1)
            dag.add_node("beta", lambda: None, priority=5)
            dag.add_node("gamma", lambda: None, priority=1)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["beta", "alpha", "gamma"])

    def test_next_wave_empty_when_no_nodes_are_ready(self) -> None:
        """WHEN no nodes are ready, MUST return an empty list."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("solo", lambda: None, dependencies=[])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["solo"])
            scheduler.mark_running("solo")
            self.assertEqual(scheduler.next_wave(), [])

    def test_next_wave_excludes_nodes_with_unsatisfied_dependencies(self) -> None:
        """POSTCONDITIONS: only READY nodes whose upstream dependencies succeeded."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["root"])
            scheduler = scope.get_singleton(WaveScheduler)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["root"])
            self.assertNotIn("child", wave)
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("child"), dag_engine.NodeState.PENDING)

    def test_mark_running_transitions_state(self) -> None:
        """POSTCONDITIONS: MUST update the node state to RUNNING."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("solo", lambda: None)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("solo")
            self.assertEqual(scheduler.get_state("solo"), dag_engine.NodeState.RUNNING)

    def test_mark_succeeded_promotes_downstream_dependents(self) -> None:
        """POSTCONDITIONS: MUST promote newly unblocked dependents to READY."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_a", lambda: None)
            dag.add_node("beta", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["root_a"])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["beta", "root_a"])
            scheduler.mark_running("root_a")
            scheduler.mark_succeeded("root_a")
            self.assertEqual(
                scheduler.get_state("root_a"), dag_engine.NodeState.SUCCEEDED
            )
            self.assertEqual(scheduler.get_state("child"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["beta", "child"])

    def test_mark_succeeded_requires_all_dependencies(self) -> None:
        """A dependent stays PENDING until every upstream dependency succeeded."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: None)
            dag.add_node("second", lambda: None)
            dag.add_node("joined", lambda: None, dependencies=["first", "second"])
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("first")
            scheduler.mark_succeeded("first")
            self.assertEqual(
                scheduler.get_state("joined"), dag_engine.NodeState.PENDING
            )
            scheduler.mark_running("second")
            scheduler.mark_succeeded("second")
            self.assertEqual(
                scheduler.get_state("joined"), dag_engine.NodeState.READY
            )

    def test_mark_failed_default_policy_cancels_remaining_nodes(self) -> None:
        """WHEN failure_policy is FAIL_FAST, MUST transition remaining PENDING nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("middle", lambda: None, dependencies=["root"])
            dag.add_node("last", lambda: None, dependencies=["middle"])
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("root")
            scheduler.mark_failed("root")
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.FAILED)
            self.assertEqual(
                scheduler.get_state("middle"), dag_engine.NodeState.CANCELLED
            )
            self.assertEqual(
                scheduler.get_state("last"), dag_engine.NodeState.CANCELLED
            )
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_marks_transitive_dependents(self) -> None:
        """WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("middle", lambda: None, dependencies=["root"])
            dag.add_node("last", lambda: None, dependencies=["middle"])
            dag.add_node("independent", lambda: None)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("root")
            scheduler.mark_failed("root", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.FAILED)
            self.assertEqual(
                scheduler.get_state("middle"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(scheduler.get_state("last"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(
                scheduler.get_state("independent"), dag_engine.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())

    def test_mark_failed_continue_on_error_keeps_independent_nodes_eligible(self) -> None:
        """WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("middle", lambda: None, dependencies=["root"])
            dag.add_node("independent", lambda: None)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("root")
            scheduler.mark_failed("root", dag_engine.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.FAILED)
            self.assertEqual(
                scheduler.get_state("middle"), dag_engine.NodeState.PENDING
            )
            self.assertEqual(
                scheduler.get_state("independent"), dag_engine.NodeState.READY
            )
            self.assertEqual(scheduler.next_wave(), ["independent"])
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_for_empty_graph(self) -> None:
        """WHEN the DAG contains no nodes, MUST return True."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(dict(scheduler.get_all_states()), {})

    def test_is_finished_tracks_terminal_states(self) -> None:
        """WHEN any node is not terminal MUST return False; when all are terminal MUST return True."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", lambda: None)
            dag.add_node("second", lambda: None, dependencies=["first"])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("first")
            scheduler.mark_succeeded("first")
            self.assertFalse(scheduler.is_finished())
            scheduler.mark_running("second")
            scheduler.mark_succeeded("second")
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(
                dict(scheduler.get_all_states()),
                {
                    "first": dag_engine.NodeState.SUCCEEDED,
                    "second": dag_engine.NodeState.SUCCEEDED,
                },
            )

    def test_get_all_states_reports_every_registered_node(self) -> None:
        """POSTCONDITIONS: get_all_states maps every node identifier to its state."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("child", lambda: None, dependencies=["root"])
            scheduler = scope.get_singleton(WaveScheduler)
            states = scheduler.get_all_states()
            self.assertEqual(set(states.keys()), {"root", "child"})
            self.assertEqual(states["root"], dag_engine.NodeState.READY)
            self.assertEqual(states["child"], dag_engine.NodeState.PENDING)

    def test_state_reporting_after_node_removal(self) -> None:
        """A removed identifier MUST disappear from reported states and MUST NOT be scheduled.

        POSTCONDITIONS: get_all_states reports every node currently registered in the
        DAG, so removing a node prunes its entry and the remaining nodes stay schedulable.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("keep", lambda: None)
            dag.add_node("remove_me", lambda: None)
            dag.add_node("dependent", lambda: None, dependencies=["keep"])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(
                set(scheduler.get_all_states().keys()),
                {"keep", "remove_me", "dependent"},
            )
            dag.remove_node("remove_me")
            scheduler.is_finished()
            states = scheduler.get_all_states()
            self.assertNotIn("remove_me", states)
            self.assertEqual(set(states.keys()), {"keep", "dependent"})
            self.assertEqual(scheduler.next_wave(), ["keep"])
            scheduler.mark_running("keep")
            scheduler.mark_succeeded("keep")
            self.assertEqual(scheduler.next_wave(), ["dependent"])

    def test_mark_failed_skip_downstream_covers_diamond_dependents(self) -> None:
        """WHEN failure_policy is SKIP_DOWNSTREAM, a dependent reachable by more than one route MUST be SKIPPED.

        The ``tail`` node depends on both ``left`` and ``right``, so it is reached
        through two distinct transitive dependency routes from the failed root.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", lambda: None)
            dag.add_node("left", lambda: None, dependencies=["root"])
            dag.add_node("right", lambda: None, dependencies=["root"])
            dag.add_node("tail", lambda: None, dependencies=["left", "right"])
            dag.add_node("independent", lambda: None)
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("root")
            scheduler.mark_failed("root", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("root"), dag_engine.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("left"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(
                scheduler.get_state("right"), dag_engine.NodeState.SKIPPED
            )
            self.assertEqual(scheduler.get_state("tail"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(
                scheduler.get_state("independent"), dag_engine.NodeState.READY
            )
            self.assertFalse(scheduler.is_finished())


class DAGRunnerTest(unittest.TestCase):
    """Verifies dag_engine.DAGRunner postconditions from low/dag_engine.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        dag_engine_impl.__initialize__(self.registry)

    def test_run_executes_chain_and_returns_report(self) -> None:
        """POSTCONDITIONS: execute ready nodes and return a DAGRunReport of the run."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            order: List[str] = []
            dag.add_node("first", _RecordingAction("first", order, 1))
            dag.add_node(
                "second",
                _RecordingAction("second", order, 2),
                dependencies=["first"],
            )
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(order, ["first", "second"])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"first", "second"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ("first", "second"))
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(set(report.results.keys()), {"first", "second"})
            first_result = report.results["first"]
            self.assertEqual(first_result.node_id, "first")
            self.assertEqual(first_result.state, dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(first_result.value, 1)
            self.assertIsNone(first_result.error)
            self.assertGreaterEqual(first_result.duration_seconds, 0.0)
            self.assertEqual(first_result.retries_attempted, 0)

    def test_run_retries_failed_action_before_succeeding(self) -> None:
        """POSTCONDITIONS: MUST execute retries up to the configured retry count."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            action = _FlakyAction(failures=2, value="ok")
            dag.add_node("flaky", action, retries=2)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(action.attempts, 3)
            result = report.results["flaky"]
            self.assertEqual(result.state, dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(result.value, "ok")
            self.assertEqual(result.retries_attempted, 2)
            self.assertEqual(set(report.succeeded_nodes), {"flaky"})
            self.assertEqual(report.failed_nodes, ())

    def test_run_records_exhausted_retries_as_failed(self) -> None:
        """An action failing after all retries MUST be recorded as a failed NodeResult."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            action = _FlakyAction(failures=5, value="never")
            dag.add_node("flaky", action, retries=1)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(action.attempts, 2)
            result = report.results["flaky"]
            self.assertEqual(result.state, dag_engine.NodeState.FAILED)
            self.assertIsNotNone(result.error)
            self.assertIsInstance(result.error, Exception)
            self.assertEqual(result.retries_attempted, 1)
            self.assertEqual(set(report.failed_nodes), {"flaky"})
            self.assertEqual(report.succeeded_nodes, ())

    def test_run_fail_fast_cancels_downstream_nodes(self) -> None:
        """WHEN fail_fast policy applies, remaining nodes MUST transition to CANCELLED."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", _raise_value_error)
            dag.add_node("downstream", lambda: None, dependencies=["failing"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=dag_engine.FailurePolicy.FAIL_FAST)
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.cancelled_nodes), {"downstream"})
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.skipped_nodes, ())

    def test_run_skip_downstream_marks_transitive_skipped_nodes(self) -> None:
        """WHEN skip_downstream policy applies, transitive dependents MUST be SKIPPED.

        ``tail`` depends on both ``left`` and ``right``, so it is a dependent reached
        by more than one dependency route from the failed node and must be skipped.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", _raise_value_error)
            dag.add_node("left", lambda: None, dependencies=["failing"])
            dag.add_node("right", lambda: None, dependencies=["failing"])
            dag.add_node("tail", lambda: None, dependencies=["left", "right"])
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.SKIP_DOWNSTREAM
            )
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.skipped_nodes), {"left", "right", "tail"})
            self.assertEqual(report.cancelled_nodes, ())

    def test_run_continue_on_error_executes_independent_nodes(self) -> None:
        """WHEN continue_on_error policy applies, unblocked independent nodes keep running."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", _raise_value_error)
            dag.add_node("healthy", lambda: 3)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.CONTINUE_ON_ERROR
            )
            self.assertEqual(set(report.succeeded_nodes), {"healthy"})
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(report.results["healthy"].value, 3)
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())

    def test_run_continue_on_error_reports_permanently_blocked_dependents_as_skipped(self) -> None:
        """WHEN a dependent can never become ready under continue_on_error, it MUST be reported SKIPPED.

        The failed node leaves ``blocked`` PENDING forever, so the runner must record
        it among the skipped nodes instead of scheduling it or looping indefinitely.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("failing", _raise_value_error)
            dag.add_node("blocked", lambda: None, dependencies=["failing"])
            dag.add_node("healthy", lambda: 3)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(
                failure_policy=dag_engine.FailurePolicy.CONTINUE_ON_ERROR
            )
            self.assertEqual(set(report.failed_nodes), {"failing"})
            self.assertEqual(set(report.skipped_nodes), {"blocked"})
            self.assertEqual(set(report.succeeded_nodes), {"healthy"})
            self.assertEqual(report.cancelled_nodes, ())

    def test_run_raises_cycle_error(self) -> None:
        """Cycle or missing dependency exceptions from validation MUST propagate immediately."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: None)
            dag.add_node("b", lambda: None)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.CycleError):
                runner.run()

    def test_run_raises_node_not_found_for_missing_dependency(self) -> None:
        """WHEN a dependency node is missing, run MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", lambda: None, dependencies=["ghost"])
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.NodeNotFoundError):
                runner.run()

    def test_run_raises_timeout_error(self) -> None:
        """WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", lambda: time.sleep(0.2))
            dag.add_node("followup", lambda: None, dependencies=["slow"])
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.05)

    def test_run_raises_timeout_error_for_already_elapsed_deadline(self) -> None:
        """WHEN the execution deadline has already elapsed, MUST raise DAGTimeoutError.

        The timeout budget is far smaller than the first wave's duration, so the
        deadline is exhausted while the graph still has nodes left to schedule.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("heavy", lambda: time.sleep(0.1))
            dag.add_node("after_heavy", lambda: None, dependencies=["heavy"])
            dag.add_node("after_after", lambda: None, dependencies=["after_heavy"])
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.001)

    def test_run_raises_timeout_error_without_dispatching_an_exhausted_budget(self) -> None:
        """WHEN the timeout budget is already exhausted before scheduling, MUST raise DAGTimeoutError.

        No wave may be dispatched for an exhausted budget, so no node action executes.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            executed: List[str] = []
            dag.add_node("first", _RecordingAction("first", executed))
            dag.add_node("second", _RecordingAction("second", executed))
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.0)
            self.assertEqual(executed, [])

    def test_run_node_timeout_is_reported_as_terminal_failure(self) -> None:
        """A node action exceeding its per-node timeout_seconds MUST end in a terminal failure state.

        NodeDefinition.timeout_seconds configures a per-node execution timeout, so the
        exceeding node is recorded with a terminal failure outcome instead of success.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("slow", lambda: time.sleep(0.2), timeout_seconds=0.01)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()
            self.assertEqual(set(report.failed_nodes), {"slow"})
            self.assertEqual(report.succeeded_nodes, ())
            result = report.results["slow"]
            self.assertEqual(result.state, dag_engine.NodeState.FAILED)
            self.assertIsNotNone(result.error)
            self.assertIsInstance(result.error, Exception)

    def test_run_cancellation_while_node_action_running_cancels_running_node(self) -> None:
        """WHEN cancelled while a node action is still executing, running nodes MUST be CANCELLED.

        The cancel request is issued synchronously from inside the executing action, so
        the action is deterministically still running when cancellation is observed.
        POSTCONDITIONS: the running node and all unstarted dependents MUST transition to
        CANCELLED and the runner MUST raise DAGCancelledError without dispatching a wave.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            action = _CancellingAction()
            executed: List[str] = []
            dag.add_node("running_node", action)
            dag.add_node(
                "follower",
                _RecordingAction("follower", executed),
                dependencies=["running_node"],
            )
            dag.add_node(
                "sibling",
                _RecordingAction("sibling", executed),
                dependencies=["running_node"],
            )
            runner = scope.get_singleton(DAGRunner)
            action.runner = runner
            with self.assertRaises(dag_engine.DAGCancelledError):
                runner.run(timeout_seconds=5.0)
            self.assertEqual(action.executions, 1)
            self.assertEqual(executed, [])
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(
                scheduler.get_state("running_node"), dag_engine.NodeState.CANCELLED
            )
            self.assertEqual(
                scheduler.get_state("follower"), dag_engine.NodeState.CANCELLED
            )
            self.assertEqual(
                scheduler.get_state("sibling"), dag_engine.NodeState.CANCELLED
            )

    def test_run_cancellation_observed_while_action_still_in_flight(self) -> None:
        """WHEN cancellation is observed while a dispatched action is in flight, MUST raise DAGCancelledError.

        The gated action stays in flight from before cancellation is requested until
        after the runner has aborted, so the runner deterministically observes the
        cancellation while the action is still in flight rather than after its result
        has been recorded. POSTCONDITIONS: DAGCancelledError is raised, the running node
        is CANCELLED and unstarted dependents are CANCELLED without ever executing.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            action = _BlockingAction()
            executed: List[str] = []
            dag.add_node("running_node", action)
            dag.add_node(
                "dependent",
                _RecordingAction("dependent", executed),
                dependencies=["running_node"],
            )
            runner = scope.get_singleton(DAGRunner)
            cancelled: List[bool] = []

            def request_cancellation() -> None:
                if action.started.wait(timeout=5.0):
                    runner.cancel()
                    cancelled.append(True)

            canceller = threading.Thread(target=request_cancellation)
            canceller.start()
            try:
                with self.assertRaises(dag_engine.DAGCancelledError):
                    runner.run(timeout_seconds=20.0)
            finally:
                action.release.set()
                canceller.join(timeout=5.0)
            self.assertFalse(canceller.is_alive())
            self.assertEqual(cancelled, [True])
            self.assertIn("running_node", dag.all_nodes())
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(
                scheduler.get_state("running_node"), dag_engine.NodeState.CANCELLED
            )
            self.assertEqual(
                scheduler.get_state("dependent"), dag_engine.NodeState.CANCELLED
            )
            self.assertEqual(executed, [])

    def test_cancel_marks_every_non_terminal_node_cancelled(self) -> None:
        """POSTCONDITIONS: cancel MUST set cancellation status and cancel non-terminal nodes.

        Cancellation is requested directly while every node is still READY or PENDING,
        so the runner must mark them CANCELLED without executing any node action.
        """
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            executed: List[str] = []
            dag.add_node("first", _RecordingAction("first", executed))
            dag.add_node(
                "second",
                _RecordingAction("second", executed, 2),
                dependencies=["first"],
            )
            runner = scope.get_singleton(DAGRunner)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("first"), dag_engine.NodeState.READY)
            self.assertEqual(
                scheduler.get_state("second"), dag_engine.NodeState.PENDING
            )
            runner.cancel()
            for node_id in dag.all_nodes():
                self.assertEqual(
                    scheduler.get_state(node_id), dag_engine.NodeState.CANCELLED
                )
            self.assertEqual(executed, [])
            try:
                runner.run(timeout_seconds=5.0)
            except dag_engine.DAGCancelledError:
                pass
            self.assertEqual(executed, [])

    def test_run_executes_all_nodes_with_single_worker(self) -> None:
        """POSTCONDITIONS: MUST execute ready nodes concurrently up to max_concurrency."""
        with enter_phase(system, registry=self.registry, defer_startup=True) as scope:
            dag = scope.get_singleton(DAG)
            executed: List[str] = []
            for name in ("alpha", "beta", "gamma"):
                dag.add_node(name, _RecordingAction(name, executed))
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=1)
            self.assertEqual(sorted(executed), ["alpha", "beta", "gamma"])
            self.assertEqual(len(executed), 3)
            self.assertEqual(
                set(report.succeeded_nodes), {"alpha", "beta", "gamma"}
            )


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-22T22:07:29Z
# LAST_CHANGED: 2026-10-22T22:06:53Z
# CHANGE: Add deterministic in-flight cancellation test: a gated action stays blocked from before cancellation is requested until after the runner aborts, so cancellation is observed while the dispatched action is still in flight; assert DAGCancelledError, CANCELLED running node, CANCELLED dependents that never execute, using Event handshakes with bounded gate timeout to avoid timing races and hangs
# COVERAGE_AUDIT: 2026-10-22T22:07:29Z
# QA_AUDIT: 2026-10-22T22:07:05Z
# --- END CLEANROOM METADATA ---
