"""Unit tests for dag_engine_lite_impl covering DAG, WaveScheduler, and DAGRunner contracts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Callable, Dict, List, Tuple

# Expose the benchmark part under its package scope so that companion library
# modules resolve as 'dag_engine_lite.lib.<module>' from any collection root.
_PART_SCOPE_DIR = Path(__file__).resolve().parents[2]
if str(_PART_SCOPE_DIR) not in sys.path:
    sys.path.insert(0, str(_PART_SCOPE_DIR))

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system

from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


def _noop() -> None:
    """Zero-argument placeholder action used to register inert graph nodes."""
    return None


class ScriptedAction:
    """Deterministic node action that fails a scripted count of times before succeeding."""

    def __init__(self, failures: int, value: str) -> None:
        self.failures = failures
        self.value = value
        self.attempts = 0

    def __call__(self) -> str:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise RuntimeError("scripted node failure")
        return self.value


class RecordingBook:
    """Shared execution log and attempt counters for recording node actions."""

    def __init__(self) -> None:
        self.executed: List[str] = []
        self.attempts: Dict[str, int] = {}

    def action(self, node_id: str) -> Callable[[], str]:
        def run() -> str:
            self.executed.append(node_id)
            self.attempts[node_id] = self.attempts.get(node_id, 0) + 1
            return "value-" + node_id
        return run


class DAGTest(unittest.TestCase):
    """Contract tests for DAG node registration, edges, and accessor operations."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition(self) -> None:
        """Happy path: add_node registers an immutable definition with all supplied fields."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = ScriptedAction(0, "result")
            dag.add_node("alpha", action, None, 7, 3)
            self.assertTrue(dag.has_node("alpha"))
            definition: NodeDefinition[object] = dag.get_node("alpha")
            self.assertEqual(definition.node_id, "alpha")
            self.assertEqual(definition.priority, 7)
            self.assertEqual(definition.retries, 3)
            self.assertEqual(definition.dependencies, frozenset())
            self.assertIs(definition.action, action)

    def test_add_node_with_dependencies_creates_edges(self) -> None:
        """POSTCONDITIONS: WHEN dependencies are provided, directed edges are registered."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("leaf", _noop, ["root"], 0, 0)
            self.assertEqual(dag.get_dependencies("leaf"), {"root"})
            self.assertEqual(dag.get_dependents("root"), {"leaf"})
            self.assertEqual(dag.get_node("leaf").dependencies, frozenset({"root"}))

    def test_add_node_duplicate_identifier_raises(self) -> None:
        """PRECONDITIONS: add_node raises DuplicateNodeError for an already registered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("dup", _noop, None, 0, 0)
            with self.assertRaises(DuplicateNodeError):
                dag.add_node("dup", _noop, None, 0, 0)

    def test_add_node_defers_missing_dependency_validation(self) -> None:
        """POSTCONDITIONS: missing dependencies are not checked eagerly by add_node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, ["ghost"], 0, 0)
            self.assertTrue(dag.has_node("orphan"))
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_add_edge_connects_registered_nodes(self) -> None:
        """POSTCONDITIONS: add_edge establishes an edge between two registered nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop, None, 0, 0)
            dag.add_node("downstream", _noop, None, 0, 0)
            dag.add_edge("upstream", "downstream")
            self.assertEqual(dag.get_dependencies("downstream"), {"upstream"})
            self.assertEqual(dag.get_dependents("upstream"), {"downstream"})

    def test_add_edge_unknown_upstream_raises(self) -> None:
        """PRECONDITIONS: add_edge raises NodeNotFoundError when upstream_id is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("known", _noop, None, 0, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("ghost", "known")

    def test_add_edge_unknown_downstream_raises(self) -> None:
        """PRECONDITIONS: add_edge raises NodeNotFoundError when downstream_id is missing."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("known", _noop, None, 0, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("known", "ghost")

    def test_remove_node_deletes_incident_edges(self) -> None:
        """POSTCONDITIONS: remove_node removes the node and purges its incident edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.remove_node("first")
            self.assertFalse(dag.has_node("first"))
            self.assertEqual(dag.all_nodes(), {"second"})
            self.assertEqual(dag.get_dependencies("second"), set())

    def test_remove_node_unknown_identifier_raises(self) -> None:
        """PRECONDITIONS: remove_node raises NodeNotFoundError for an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("ghost")

    def test_remove_node_purges_upstream_and_downstream_edges(self) -> None:
        """POSTCONDITIONS: remove_node purges all incident edges in both directions."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("upstream", _noop, None, 0, 0)
            dag.add_node("middle", _noop, ["upstream"], 0, 0)
            dag.add_node("downstream", _noop, ["middle"], 0, 0)
            self.assertEqual(dag.get_dependents("upstream"), {"middle"})
            self.assertEqual(dag.get_dependencies("downstream"), {"middle"})
            dag.remove_node("middle")
            self.assertFalse(dag.has_node("middle"))
            self.assertEqual(dag.all_nodes(), {"upstream", "downstream"})
            self.assertEqual(dag.get_dependents("upstream"), set())
            self.assertEqual(dag.get_dependencies("downstream"), set())

    def test_has_node_reports_membership(self) -> None:
        """Happy path: has_node reflects graph membership without raising for unknown ids."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("present", _noop, None, 0, 0)
            self.assertTrue(dag.has_node("present"))
            self.assertFalse(dag.has_node("absent"))

    def test_get_node_unknown_identifier_raises(self) -> None:
        """PRECONDITIONS: get_node raises NodeNotFoundError for an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_node("ghost")

    def test_get_dependencies_unknown_identifier_raises(self) -> None:
        """PRECONDITIONS: get_dependencies raises NodeNotFoundError for an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("ghost")

    def test_get_dependents_unknown_identifier_raises(self) -> None:
        """PRECONDITIONS: get_dependents raises NodeNotFoundError for an unregistered node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("ghost")

    def test_all_nodes_returns_registered_identifiers(self) -> None:
        """Happy path: all_nodes reports exactly the registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            dag.add_node("one", _noop, None, 0, 0)
            dag.add_node("two", _noop, ["one"], 0, 0)
            self.assertEqual(dag.all_nodes(), {"one", "two"})


class DAGTraversalTest(unittest.TestCase):
    """Contract tests for DAG validation, ordering, root/leaf discovery, and critical path."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_validate_accepts_acyclic_graph(self) -> None:
        """POSTCONDITIONS: WHEN all referenced nodes exist and no cycle exists, validate succeeds."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            self.assertIsNone(dag.validate())

    def test_validate_rejects_missing_dependency(self) -> None:
        """PRECONDITIONS: validate raises NodeNotFoundError when a dependency is unregistered."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", _noop, ["ghost"], 0, 0)
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

    def test_validate_rejects_directed_cycle(self) -> None:
        """PRECONDITIONS: validate raises CycleError when the graph contains a directed cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.add_node("third", _noop, ["second"], 0, 0)
            dag.add_edge("third", "first")
            with self.assertRaises(CycleError):
                dag.validate()

    def test_topological_sort_orders_prerequisites_first(self) -> None:
        """POSTCONDITIONS: every prerequisite precedes its dependents in the topological order."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.add_node("third", _noop, ["second"], 0, 0)
            order = dag.topological_sort()
            self.assertEqual(order, ["first", "second", "third"])
            self.assertLess(order.index("first"), order.index("second"))
            self.assertLess(order.index("second"), order.index("third"))

    def test_topological_sort_breaks_ties_by_priority_then_identifier(self) -> None:
        """POSTCONDITIONS: concurrent ready nodes order by priority descending then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", _noop, None, 0, 0)
            dag.add_node("mid", _noop, None, 5, 0)
            dag.add_node("high", _noop, None, 10, 0)
            dag.add_node("beta", _noop, None, 5, 0)
            self.assertEqual(dag.topological_sort(), ["high", "beta", "mid", "low"])

    def test_topological_sort_rejects_directed_cycle(self) -> None:
        """PRECONDITIONS: topological_sort raises CycleError when the graph is cyclic."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.add_edge("second", "first")
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_find_roots_and_leaves(self) -> None:
        """Happy path: find_roots collects zero in-degree nodes, find_leaves zero out-degree nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("middle", _noop, ["root"], 0, 0)
            dag.add_node("solo", _noop, None, 0, 0)
            self.assertEqual(dag.find_roots(), {"root", "solo"})
            self.assertEqual(dag.find_leaves(), {"middle", "solo"})

    def test_compute_critical_path_uses_duration_weights(self) -> None:
        """POSTCONDITIONS: compute_critical_path returns the longest weighted path and its weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.add_node("third", _noop, ["second"], 0, 0)
            path, weight = dag.compute_critical_path(
                {"first": 2.0, "second": 3.0, "third": 1.0}
            )
            self.assertEqual(path, ["first", "second", "third"])
            self.assertAlmostEqual(weight, 6.0)

    def test_compute_critical_path_selects_heaviest_branch(self) -> None:
        """POSTCONDITIONS: the critical path follows the branch with the greatest completion time."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", _noop, None, 0, 0)
            dag.add_node("heavy", _noop, ["start"], 0, 0)
            dag.add_node("light", _noop, ["start"], 0, 0)
            dag.add_node("finish", _noop, ["heavy"], 0, 0)
            path, weight = dag.compute_critical_path(
                {"start": 1.0, "heavy": 5.0, "light": 1.0, "finish": 1.0}
            )
            self.assertEqual(path, ["start", "heavy", "finish"])
            self.assertAlmostEqual(weight, 7.0)

    def test_compute_critical_path_defaults_duration_to_one(self) -> None:
        """POSTCONDITIONS: WHEN estimated_durations is omitted, each node defaults to weight 1.0."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.add_node("third", _noop, ["second"], 0, 0)
            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, ["first", "second", "third"])
            self.assertAlmostEqual(weight, 3.0)

    def test_compute_critical_path_empty_graph(self) -> None:
        """POSTCONDITIONS: an empty graph yields an empty path with zero cumulative weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            path, weight = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertAlmostEqual(weight, 0.0)


class WaveSchedulerTest(unittest.TestCase):
    """Contract tests for WaveScheduler state transitions, wave ordering, and failure policies."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _build_graph(self, scope: LifecycleScope) -> Tuple[DAG, WaveScheduler]:
        """Registers a root with one dependent plus an independent root inside the active scope."""
        dag = scope.get_singleton(DAG)
        scheduler = scope.get_singleton(WaveScheduler)
        dag.add_node("root", _noop, None, 0, 0)
        dag.add_node("child", _noop, ["root"], 0, 0)
        dag.add_node("other", _noop, None, 0, 0)
        scheduler.next_wave()
        return dag, scheduler

    def test_next_wave_orders_ready_roots_by_priority(self) -> None:
        """POSTCONDITIONS: next_wave returns READY roots ordered by priority descending, id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("low", _noop, None, 0, 0)
            dag.add_node("high", _noop, None, 9, 0)
            dag.add_node("mid", _noop, None, 9, 0)
            self.assertEqual(scheduler.next_wave(), ["high", "mid", "low"])

    def test_next_wave_returns_empty_when_nothing_ready(self) -> None:
        """POSTCONDITIONS: WHEN no nodes are ready, next_wave returns an empty list."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("child", _noop, ["root"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["root"])
            scheduler.mark_running("root")
            self.assertEqual(scheduler.next_wave(), [])

    def test_get_all_states_initializes_roots_ready_and_others_pending(self) -> None:
        """GROUNDING: get_all_states exposes every DAG node, roots READY and non-roots PENDING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("child", _noop, ["root"], 0, 0)
            states = scheduler.get_all_states()
            self.assertEqual(set(states.keys()), {"root", "child"})
            self.assertEqual(states["root"], NodeState.READY)
            self.assertEqual(states["child"], NodeState.PENDING)

    def test_mark_running_transitions_state(self) -> None:
        """POSTCONDITIONS: mark_running updates the node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            scheduler.mark_running("root")
            self.assertEqual(scheduler.get_state("root"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """POSTCONDITIONS: mark_succeeded sets SUCCEEDED and promotes unblocked dependents to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("child", _noop, ["root"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["root"])
            scheduler.mark_running("root")
            scheduler.mark_succeeded("root")
            self.assertEqual(scheduler.get_state("root"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("child"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["child"])

    def test_get_state_unknown_identifier_raises(self) -> None:
        """PRECONDITIONS: get_state raises NodeNotFoundError for a node absent from the DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("ghost")

    def test_is_finished_true_for_empty_dag(self) -> None:
        """POSTCONDITIONS: WHEN the DAG contains no nodes, is_finished returns True."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(dag.all_nodes(), set())
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_while_nodes_remain_eligible(self) -> None:
        """POSTCONDITIONS: WHEN a node remains non-terminal and eligible, is_finished returns False."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_when_all_nodes_terminal(self) -> None:
        """POSTCONDITIONS: WHEN every DAG node reached a terminal state, is_finished returns True."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("child", _noop, ["root"], 0, 0)
            scheduler.mark_succeeded("root")
            scheduler.mark_succeeded("child")
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_fail_fast_cancels_remaining_nodes(self) -> None:
        """POSTCONDITIONS: FAIL_FAST transitions all remaining non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            _dag, scheduler = self._build_graph(scope)
            scheduler.mark_failed("root", FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("other"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """POSTCONDITIONS: SKIP_DOWNSTREAM transitions transitive dependents to SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            _dag, scheduler = self._build_graph(scope)
            scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child"), NodeState.SKIPPED)
            self.assertNotEqual(scheduler.get_state("other"), NodeState.SKIPPED)
            self.assertNotEqual(scheduler.get_state("other"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error_skips_only_blocked_dependents(self) -> None:
        """POSTCONDITIONS: CONTINUE_ON_ERROR skips blocked dependents and keeps independents eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            _dag, scheduler = self._build_graph(scope)
            scheduler.mark_failed("root", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child"), NodeState.SKIPPED)
            self.assertNotEqual(scheduler.get_state("other"), NodeState.FAILED)
            self.assertNotEqual(scheduler.get_state("other"), NodeState.SKIPPED)
            self.assertNotEqual(scheduler.get_state("other"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream_reaches_transitive_dependents(self) -> None:
        """POSTCONDITIONS: SKIP_DOWNSTREAM propagates across the full transitive downstream closure."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("middle", _noop, ["root"], 0, 0)
            dag.add_node("last", _noop, ["middle"], 0, 0)
            scheduler.next_wave()
            scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("middle"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("last"), NodeState.SKIPPED)

    def test_mark_failed_skip_downstream_handles_converging_dependents(self) -> None:
        """POSTCONDITIONS: the transitive downstream closure is fully skipped when branches converge."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("left", _noop, ["root"], 0, 0)
            dag.add_node("right", _noop, ["root"], 0, 0)
            dag.add_node("shared", _noop, ["left", "right"], 0, 0)
            scheduler.next_wave()
            scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("left"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("right"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("shared"), NodeState.SKIPPED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_succeeded_leaves_dependents_past_pending_unchanged(self) -> None:
        """POSTCONDITIONS: only PENDING dependents are promoted; dependents past PENDING are unchanged."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("alpha", _noop, None, 0, 0)
            dag.add_node("beta", _noop, None, 0, 0)
            dag.add_node("child", _noop, ["alpha", "beta"], 0, 0)
            scheduler.next_wave()
            scheduler.mark_succeeded("alpha")
            self.assertEqual(scheduler.get_state("child"), NodeState.PENDING)
            scheduler.mark_succeeded("beta")
            self.assertEqual(scheduler.get_state("child"), NodeState.READY)
            scheduler.mark_succeeded("alpha")
            self.assertEqual(scheduler.get_state("child"), NodeState.READY)
            scheduler.mark_succeeded("child")
            self.assertEqual(scheduler.get_state("child"), NodeState.SUCCEEDED)
            scheduler.mark_succeeded("alpha")
            self.assertEqual(scheduler.get_state("child"), NodeState.SUCCEEDED)

    def test_remove_node_purges_tracked_node_from_scheduler(self) -> None:
        """POSTCONDITIONS: remove_node purges the node identifier from wave scheduler state tracking."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("child", _noop, ["root"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["root"])
            scheduler.mark_succeeded("root")
            scheduler.mark_succeeded("child")
            self.assertEqual(scheduler.get_state("child"), NodeState.SUCCEEDED)
            dag.remove_node("child")
            self.assertNotIn("child", scheduler.get_all_states())
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("child")

    def test_mark_failed_continue_on_error_handles_converging_dependents(self) -> None:
        """POSTCONDITIONS: CONTINUE_ON_ERROR skips every blocked dependent of a converging diamond."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            dag.add_node("left", _noop, ["root"], 0, 0)
            dag.add_node("right", _noop, ["root"], 0, 0)
            dag.add_node("shared", _noop, ["left", "right"], 0, 0)
            scheduler.next_wave()
            scheduler.mark_failed("root", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("root"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("left"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("right"), NodeState.SKIPPED)
            self.assertNotEqual(scheduler.get_state("shared"), NodeState.FAILED)

    def test_is_finished_true_when_remaining_nodes_blocked_by_failure(self) -> None:
        """POSTCONDITIONS: WHEN no nodes are ready and non-terminal nodes are blocked, is_finished is True."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("root", _noop, None, 0, 0)
            scheduler.next_wave()
            scheduler.mark_failed("root", FailurePolicy.CONTINUE_ON_ERROR)
            dag.add_node("later", _noop, ["root"], 0, 0)
            self.assertEqual(scheduler.get_state("later"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())


class DAGRunnerTest(unittest.TestCase):
    """Contract tests for sequential DAG execution, retries, failure policies, and reporting."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_executes_dependencies_and_reports_success(self) -> None:
        """Happy path: run executes a chain in dependency order and reports a consolidated summary."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            book = RecordingBook()
            dag.add_node("first", book.action("first"), None, 0, 0)
            dag.add_node("second", book.action("second"), ["first"], 0, 0)
            report: DAGRunReport = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(book.executed, ["first", "second"])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"first", "second"})
            self.assertEqual(list(report.failed_nodes), [])
            self.assertEqual(list(report.skipped_nodes), [])
            self.assertEqual(list(report.cancelled_nodes), [])
            self.assertEqual(list(report.critical_path), ["first", "second"])
            self.assertEqual(set(report.results.keys()), {"first", "second"})
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_records_successful_node_values(self) -> None:
        """POSTCONDITIONS: successful NodeResult records capture the action return value and SUCCEEDED state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("only", ScriptedAction(0, "computed"), None, 0, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            result: NodeResult[object] = report.results["only"]
            self.assertEqual(result.node_id, "only")
            self.assertEqual(result.state, NodeState.SUCCEEDED)
            self.assertEqual(result.value, "computed")
            self.assertIsNone(result.error)
            self.assertEqual(result.retries_attempted, 0)
            self.assertGreaterEqual(result.duration_seconds, 0.0)

    def test_run_retries_failed_action_before_succeeding(self) -> None:
        """POSTCONDITIONS: failed node actions are retried up to the configured retry count."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            action = ScriptedAction(1, "recovered")
            dag.add_node("flaky", action, None, 0, 2)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(action.attempts, 2)
            self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertEqual(report.results["flaky"].retries_attempted, 1)
            self.assertEqual(set(report.succeeded_nodes), {"flaky"})

    def test_run_exhausts_retries_before_failing(self) -> None:
        """POSTCONDITIONS: a node failing every attempt is retried exactly retries times then FAILED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            action = ScriptedAction(10, "never")
            dag.add_node("doomed", action, None, 0, 2)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(action.attempts, 3)
            self.assertEqual(report.results["doomed"].state, NodeState.FAILED)
            self.assertIsInstance(report.results["doomed"].error, RuntimeError)
            self.assertEqual(list(report.failed_nodes), ["doomed"])

    def test_run_fail_fast_cancels_unexecuted_nodes(self) -> None:
        """POSTCONDITIONS: FAIL_FAST halts execution and cancels nodes that were never executed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad", ScriptedAction(10, "x"), None, 0, 0)
            dag.add_node("other", ScriptedAction(0, "y"), None, 0, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(list(report.failed_nodes), ["bad"])
            self.assertIn("other", report.cancelled_nodes)
            self.assertEqual(report.results["other"].state, NodeState.CANCELLED)
            self.assertNotIn("other", report.succeeded_nodes)

    def test_run_skip_downstream_reports_skipped_dependents(self) -> None:
        """POSTCONDITIONS: SKIP_DOWNSTREAM reports transitive dependents of the failed node as skipped."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad", ScriptedAction(10, "x"), None, 0, 0)
            dag.add_node("child", ScriptedAction(0, "y"), ["bad"], 0, 0)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(list(report.failed_nodes), ["bad"])
            self.assertEqual(list(report.skipped_nodes), ["child"])
            self.assertEqual(report.results["child"].state, NodeState.SKIPPED)
            self.assertEqual(list(report.succeeded_nodes), [])

    def test_run_continue_on_error_executes_independent_nodes(self) -> None:
        """POSTCONDITIONS: CONTINUE_ON_ERROR keeps independent nodes eligible after a failure."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("bad", ScriptedAction(10, "x"), None, 0, 0)
            dag.add_node("good", ScriptedAction(0, "y"), None, 0, 0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(set(report.succeeded_nodes), {"good"})
            self.assertEqual(list(report.failed_nodes), ["bad"])
            self.assertEqual(report.results["good"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["good"].value, "y")

    def test_run_rejects_missing_dependency(self) -> None:
        """PRECONDITIONS: run validates the graph and raises NodeNotFoundError for missing dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("orphan", _noop, ["ghost"], 0, 0)
            with self.assertRaises(NodeNotFoundError):
                runner.run(FailurePolicy.FAIL_FAST)

    def test_run_rejects_directed_cycle(self) -> None:
        """PRECONDITIONS: run validates the graph and raises CycleError for a directed cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("first", _noop, None, 0, 0)
            dag.add_node("second", _noop, ["first"], 0, 0)
            dag.add_edge("second", "first")
            with self.assertRaises(CycleError):
                runner.run(FailurePolicy.FAIL_FAST)

    def test_run_empty_graph_reports_no_work(self) -> None:
        """POSTCONDITIONS: running an empty graph yields an empty report with no recorded outcomes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            self.assertEqual(dag.all_nodes(), set())
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(list(report.succeeded_nodes), [])
            self.assertEqual(list(report.failed_nodes), [])
            self.assertEqual(list(report.skipped_nodes), [])
            self.assertEqual(list(report.cancelled_nodes), [])
            self.assertEqual(list(report.critical_path), [])
            self.assertEqual(set(report.results.keys()), set())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_halts_when_next_wave_is_empty(self) -> None:
        """POSTCONDITIONS: the wave loop halts as soon as the scheduler resolves an empty wave."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)
            book = RecordingBook()
            dag.add_node("root", book.action("root"), None, 0, 0)
            dag.add_node("child", book.action("child"), ["root"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["root"])
            scheduler.mark_running("root")
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(book.executed, [])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(list(report.succeeded_nodes), [])
            self.assertEqual(list(report.failed_nodes), [])
            self.assertEqual(list(report.critical_path), ["root", "child"])


class DAGEngineCompositionTest(unittest.TestCase):
    """Contract tests for runner coordination across DAG and WaveScheduler singletons."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_executes_wide_wave_in_priority_order(self) -> None:
        """POSTCONDITIONS: ready waves execute in priority descending, node_id ascending order."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            book = RecordingBook()
            dag.add_node("low", book.action("low"), None, 0, 0)
            dag.add_node("high", book.action("high"), None, 10, 0)
            dag.add_node("mid", book.action("mid"), None, 5, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(book.executed, ["high", "mid", "low"])
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"low", "high", "mid"})

    def test_run_records_state_for_every_node(self) -> None:
        """POSTCONDITIONS: the run report records an outcome for every node registered in the DAG."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("first", ScriptedAction(0, "a"), None, 0, 0)
            dag.add_node("second", ScriptedAction(0, "b"), ["first"], 0, 0)
            dag.add_node("third", ScriptedAction(0, "c"), ["first"], 0, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(set(report.results.keys()), {"first", "second", "third"})
            for node_id in ("first", "second", "third"):
                self.assertEqual(report.results[node_id].state, NodeState.SUCCEEDED)

    def test_scheduler_finishes_after_successful_run(self) -> None:
        """POSTCONDITIONS: after a successful run every node reaches a terminal state."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("first", ScriptedAction(0, "a"), None, 0, 0)
            dag.add_node("second", ScriptedAction(0, "b"), ["first"], 0, 0)
            runner.run(FailurePolicy.FAIL_FAST)
            self.assertTrue(scheduler.is_finished())
            states = scheduler.get_all_states()
            self.assertEqual(states["first"], NodeState.SUCCEEDED)
            self.assertEqual(states["second"], NodeState.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T21:45:58Z
# LAST_CHANGED: 2026-11-05T21:14:43Z
# CHANGE: Re-submit full contract suite (58 tests) after the prior delivery appeared to be lost to an upstream sync conflict; all seven cited gaps are covered: remove_node with upstream prerequisites purges incident edges in both directions; compute_critical_path and run() on an empty graph yield the empty path, zero weight and a zero-node DAGRunReport; remove_node on a scheduler-tracked node leaves it untracked (absent from get_all_states, get_state raises NodeNotFoundError); mark_succeeded leaves dependents already past PENDING (READY then terminal) unchanged; mark_failed covers converging diamond dependents under both SKIP_DOWNSTREAM and CONTINUE_ON_ERROR; is_finished is True when no nodes are ready and non-terminal nodes are blocked by a failed dependency (node registered after its prerequisite failed); and run() halts when the scheduler resolves an empty next wave while the run is not finished.
# COVERAGE_AUDIT: 2026-11-05T21:45:58Z
# QA_AUDIT: 2026-11-05T21:45:37Z
# --- END AUTOFAB METADATA ---
