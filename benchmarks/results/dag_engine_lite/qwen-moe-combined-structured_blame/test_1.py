"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from dag_engine_lite.lib.dag_engine_lite import (
    DAGError,
    CycleError,
    NodeNotFoundError,
    DuplicateNodeError,
    NodeExecutionError,
    NodeState,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    DAGRunReport,
)


class MockActionFactory:
    """Helper to create deterministic mock actions for node definitions."""

    def __init__(self) -> None:
        self._count = 0

    def make(self, return_value: int = 0) -> MagicMock:
        mock = MagicMock(return_value=return_value)
        self._count += 1
        return mock

    def make_failing(self, exception: Exception = Exception("action error")) -> MagicMock:
        mock = MagicMock(side_effect=exception)
        self._count += 1
        return mock


class DagEngineLiteImplTest(unittest.TestCase):
    """Tests for DAG, WaveScheduler, and DAGRunner singletons."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self._action_factory = MockActionFactory()

    def tearDown(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    # DAG tests                                                           #
    # ------------------------------------------------------------------ #

    def test_dag_add_node_and_has_node(self) -> None:
        """CUJ: add_node registers a node, has_node reports it."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            mock = self._action_factory.make(return_value=42)
            dag.add_node("task_a", mock, None, priority=5, retries=0)
            self.assertTrue(dag.has_node("task_a"))
            self.assertIn("task_a", dag.all_nodes())

    def test_dag_add_duplicate_node_raises(self) -> None:
        """PRECONDITION: add_node with duplicate node_id raises DuplicateNodeError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            mock = self._action_factory.make(return_value=1)
            dag.add_node("task_x", mock, None, priority=0, retries=0)
            with self.assertRaises(DuplicateNodeError):
                dag.add_node("task_x", self._action_factory.make(return_value=2), None, 0, 0)

    def test_dag_add_node_with_dependencies(self) -> None:
        """POSTCONDITION: add_node registers directed dependency edges."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", self._action_factory.make(return_value=1), None, priority=1, retries=0)
            dag.add_node("down", self._action_factory.make(return_value=2), {"up"}, priority=2, retries=0)
            self.assertEqual(dag.get_dependencies("down"), {"up"})
            self.assertIn("down", dag.get_dependents("up"))

    def test_dag_add_node_defers_missing_dep_check(self) -> None:
        """POSTCONDITION: add_node defers missing dependency checks to validate()."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", self._action_factory.make(return_value=0), {"nonexistent"}, priority=0, retries=0)
            self.assertTrue(dag.has_node("orphan"))

    def test_dag_get_node_returns_definition(self) -> None:
        """POSTCONDITION: get_node returns the NodeDefinition for node_id."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            action = self._action_factory.make(return_value=99)
            dag.add_node("task_gn", action, frozenset(), priority=10, retries=1)
            nd = dag.get_node("task_gn")
            self.assertEqual(nd.node_id, "task_gn")
            self.assertEqual(nd.priority, 10)
            self.assertEqual(nd.retries, 1)

    def test_dag_get_node_missing_raises(self) -> None:
        """PRECONDITION: get_node for absent node raises NodeNotFoundError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_node("ghost")

    def test_dag_add_edge_missing_node_raises(self) -> None:
        """PRECONDITION: add_edge with missing upstream_id raises NodeNotFoundError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("absent", "also_absent")

    def test_dag_remove_node(self) -> None:
        """POSTCONDITION: remove_node removes node and incident edges."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("to_remove", self._action_factory.make(return_value=0), None, priority=1, retries=0)
            self.assertTrue(dag.has_node("to_remove"))
            dag.remove_node("to_remove")
            self.assertFalse(dag.has_node("to_remove"))
            self.assertNotIn("to_remove", dag.all_nodes())

    def test_dag_remove_missing_node_raises(self) -> None:
        """PRECONDITION: remove_node for absent node raises NodeNotFoundError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("nonexistent")

    def test_dag_find_roots_and_leaves(self) -> None:
        """POSTCONDITION: find_roots returns in-degree zero nodes; find_leaves returns out-degree zero."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", self._action_factory.make(return_value=1), None, priority=1, retries=0)
            dag.add_node("mid", self._action_factory.make(return_value=2), {"root"}, priority=0, retries=0)
            dag.add_node("leaf", self._action_factory.make(return_value=3), {"mid"}, priority=0, retries=0)
            roots = dag.find_roots()
            leaves = dag.find_leaves()
            self.assertIn("root", roots)
            self.assertIn("leaf", leaves)
            self.assertNotIn("mid", roots)
            self.assertNotIn("mid", leaves)

    def test_dag_validate_accepts_valid_graph(self) -> None:
        """POSTCONDITION: validate completes without error on a valid acyclic graph."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.validate()  # should not raise

    def test_dag_validate_cycle_raises(self) -> None:
        """POSTCONDITION: validate raises CycleError on a cyclic graph."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c1", self._action_factory.make(return_value=1), {"c2"}, priority=0, retries=0)
            dag.add_node("c2", self._action_factory.make(return_value=2), {"c1"}, priority=0, retries=0)
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertIsNotNone(ctx.exception.cycle)

    def test_dag_topological_sort_order(self) -> None:
        """POSTCONDITION: topological_sort returns valid ordering with tie-breaking."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low_p", self._action_factory.make(return_value=1), None, priority=1, retries=0)
            dag.add_node("high_p", self._action_factory.make(return_value=2), None, priority=10, retries=0)
            dag.add_node("mid_p", self._action_factory.make(return_value=3), None, priority=5, retries=0)
            order = dag.topological_sort()
            self.assertEqual(order, ["high_p", "mid_p", "low_p"])

    def test_dag_topological_sort_respects_dependencies(self) -> None:
        """POSTCONDITION: topological_sort ensures prerequisites precede dependents."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=5, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=10, retries=0)
            order = dag.topological_sort()
            self.assertLess(order.index("a"), order.index("b"))
            self.assertLess(order.index("b"), order.index("c"))

    def test_dag_topological_sort_cycle_raises(self) -> None:
        """POSTCONDITION: topological_sort raises CycleError on a cyclic graph."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("x1", self._action_factory.make(return_value=1), {"x2"}, priority=0, retries=0)
            dag.add_node("x2", self._action_factory.make(return_value=2), {"x1"}, priority=0, retries=0)
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_dag_compute_critical_path(self) -> None:
        """POSTCONDITION: compute_critical_path returns the longest weighted path."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=0, retries=0)
            path, duration = dag.compute_critical_path(None)
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(duration, 3.0)

    def test_dag_compute_critical_path_with_custom_durations(self) -> None:
        """POSTCONDITION: critical path respects custom estimated_durations."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"a"}, priority=0, retries=0)
            path, duration = dag.compute_critical_path({"a": 1.0, "b": 10.0, "c": 2.0})
            self.assertEqual(path, ["a", "b"])
            self.assertAlmostEqual(duration, 11.0)

    def test_dag_add_edge_directed_edge(self) -> None:
        """POSTCONDITION: add_edge establishes directed edge from upstream to downstream."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("down", self._action_factory.make(return_value=2), None, priority=0, retries=0)
            dag.add_edge("up", "down")
            self.assertEqual(dag.get_dependencies("down"), {"up"})
            self.assertEqual(dag.get_dependents("up"), {"down"})

    def test_dag_remove_node_purges_incident_edges(self) -> None:
        """POSTCONDITION: remove_node purges upstream AND downstream incident edges."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=0, retries=0)
            # b has upstream a and downstream c; removing b must purge both
            dag.remove_node("b")
            self.assertNotIn("b", dag.all_nodes())
            self.assertNotIn("b", dag.get_dependents("a"))
            self.assertNotIn("b", dag.get_dependencies("c"))

    def test_dag_compute_critical_path_empty_dag(self) -> None:
        """POSTCONDITION: compute_critical_path handles empty DAG."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, duration = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertEqual(duration, 0.0)

    def test_dag_get_dependencies_missing_node_raises(self) -> None:
        """PRECONDITION: get_dependencies for absent node raises NodeNotFoundError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("missing")

    def test_dag_get_dependents_missing_node_raises(self) -> None:
        """PRECONDITION: get_dependents for absent node raises NodeNotFoundError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("missing")

    # ------------------------------------------------------------------ #
    # WaveScheduler tests                                                 #
    # ------------------------------------------------------------------ #

    def _build_simple_graph(self) -> None:
        """Helper: build a linear A->B->C graph with actions and registered nodes."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self._action_factory.make(return_value=1)
            self._action_factory.make(return_value=2)
            self._action_factory.make(return_value=3)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=0, retries=0)

    def test_wavescheduler_next_wave_initial_roots(self) -> None:
        """POSTCONDITION: next_wave returns root nodes (dependencies satisfied)."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("root1", self._action_factory.make(return_value=1), None, priority=1, retries=0)
            dag.add_node("root2", self._action_factory.make(return_value=2), None, priority=0, retries=0)
            wave = sched.next_wave()
            self.assertIn("root1", wave)
            self.assertIn("root2", wave)

    def test_wavescheduler_next_wave_priority_ordering(self) -> None:
        """POSTCONDITION: next_wave orders nodes by priority descending."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("low", self._action_factory.make(return_value=1), None, priority=1, retries=0)
            dag.add_node("high", self._action_factory.make(return_value=2), None, priority=10, retries=0)
            wave = sched.next_wave()
            self.assertEqual(wave, ["high", "low"])

    def test_wavescheduler_mark_succeeded_promotes_dependents(self) -> None:
        """POSTCONDITION: mark_succeeded promotes unblocked dependents to READY."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            wave1 = sched.next_wave()
            self.assertIn("a", wave1)
            self.assertEqual(sched.get_state("a"), NodeState.READY)
            sched.mark_running("a")
            sched.mark_succeeded("a")
            self.assertEqual(sched.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(sched.get_state("b"), NodeState.READY)

    def test_wavescheduler_mark_failed_fail_fast(self) -> None:
        """POSTCONDITION: FAIL_FAST transitions remaining PENDING nodes to CANCELLED."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), None, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"a", "b"}, priority=0, retries=0)
            sched.next_wave()
            sched.mark_running("a")
            sched.mark_failed("a", FailurePolicy.FAIL_FAST)
            self.assertEqual(sched.get_state("a"), NodeState.FAILED)
            self.assertEqual(sched.get_state("b"), NodeState.CANCELLED)
            self.assertEqual(sched.get_state("c"), NodeState.CANCELLED)

    def test_wavescheduler_mark_failed_skip_downstream(self) -> None:
        """POSTCONDITION: SKIP_DOWNSTREAM transitions transitive dependents to SKIPPED."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=0, retries=0)
            sched.next_wave()
            sched.mark_running("a")
            sched.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(sched.get_state("a"), NodeState.FAILED)
            self.assertEqual(sched.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(sched.get_state("c"), NodeState.SKIPPED)

    def test_wavescheduler_is_finished_all_succeeded(self) -> None:
        """POSTCONDITION: is_finished returns True when all nodes are terminal."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            sched.next_wave()
            sched.mark_running("a")
            sched.mark_succeeded("a")
            self.assertTrue(sched.is_finished())

    def test_wavescheduler_is_finished_empty_dag(self) -> None:
        """POSTCONDITION: is_finished returns True for empty DAG."""
        with enter_phase("system", registry=self.registry) as scope:
            sched = scope.get_singleton(WaveScheduler)
            self.assertTrue(sched.is_finished())

    def test_wavescheduler_get_state_missing_node_raises(self) -> None:
        """PRECONDITION: get_state for unregistered node raises NodeNotFoundError."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("x", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            with self.assertRaises(NodeNotFoundError):
                sched.get_state("nonexistent")

    def test_wavescheduler_get_state_initialized_from_dag(self) -> None:
        """POSTCONDITION: get_state synchronizes _states when called before next_wave."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            # Call get_state before next_wave to trigger state synchronization for root
            state = sched.get_state("a")
            self.assertEqual(state, NodeState.READY)
            # Also test non-root node synchronization
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            state = sched.get_state("b")
            self.assertEqual(state, NodeState.PENDING)

    def test_wavescheduler_get_all_states(self) -> None:
        """POSTCONDITION: get_all_states returns states for all registered nodes."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            sched.next_wave()
            states = sched.get_all_states()
            self.assertIn("a", states)
            self.assertIn("b", states)
            self.assertEqual(states["a"], NodeState.READY)

    def test_wavescheduler_next_wave_empty_when_no_ready(self) -> None:
        """POSTCONDITION: next_wave returns empty list when no nodes are ready."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            # Initial wave has "a" ready
            wave1 = sched.next_wave()
            self.assertIn("a", wave1)
            # After marking a running and succeeding, "b" should be ready
            sched.mark_running("a")
            sched.mark_succeeded("a")
            wave2 = sched.next_wave()
            self.assertIn("b", wave2)
            # Now no more ready nodes
            sched.mark_running("b")
            wave3 = sched.next_wave()
            self.assertEqual(wave3, [])

    def test_wavescheduler_next_wave_node_state_filtering(self) -> None:
        """POSTCONDITION: next_wave only returns nodes in READY state."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), None, priority=0, retries=0)
            wave = sched.next_wave()
            # Both are READY initially
            self.assertIn("a", wave)
            self.assertIn("b", wave)
            # Mark a running - it should not appear in next wave
            sched.mark_running("a")
            wave2 = sched.next_wave()
            self.assertNotIn("a", wave2)
            self.assertIn("b", wave2)

    def test_wavescheduler_mark_succeeded_promotes_non_pending(self) -> None:
        """POSTCONDITION: mark_succeeded promotes PENDING dependents to READY when all deps succeed."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            # a and b are roots (no deps) - both start READY; c depends on {a, b} - starts PENDING
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), None, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"a", "b"}, priority=0, retries=0)
            wave = sched.next_wave()
            self.assertIn("a", wave)
            self.assertIn("b", wave)
            # Mark both a and b succeeded so c (deps={a,b}) can transition PENDING -> READY
            sched.mark_running("a")
            sched.mark_succeeded("a")
            sched.mark_running("b")
            sched.mark_succeeded("b")
            # c should transition from PENDING to READY now that all deps succeeded
            self.assertEqual(sched.get_state("c"), NodeState.READY)
            wave2 = sched.next_wave()
            self.assertIn("c", wave2)

    def test_wavescheduler_mark_failed_continue_on_error_propagates(self) -> None:
        """POSTCONDITION: CONTINUE_ON_ERROR allows independent dependents to proceed."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make_failing(Exception("crash")), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), None, priority=0, retries=0)
            wave = sched.next_wave()
            self.assertIn("a", wave)
            self.assertIn("c", wave)
            sched.mark_running("a")
            sched.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(sched.get_state("b"), NodeState.SKIPPED)
            # c is independent - should still be executable
            self.assertEqual(sched.get_state("c"), NodeState.READY)

    def test_wavescheduler_mark_failed_skip_downstream_traverses_chain(self) -> None:
        """POSTCONDITION: SKIP_DOWNSTREAM traverses all transitive dependents."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make_failing(Exception("crash")), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=0, retries=0)
            dag.add_node("d", self._action_factory.make(return_value=4), {"c"}, priority=0, retries=0)
            wave = sched.next_wave()
            self.assertIn("a", wave)
            sched.mark_running("a")
            sched.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(sched.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(sched.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(sched.get_state("d"), NodeState.SKIPPED)

    def test_wavescheduler_get_state_synchronization(self) -> None:
        """POSTCONDITION: get_state returns correct state after transitions."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            sched = scope.get_singleton(WaveScheduler)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            # Before next_wave, state tracking begins
            wave = sched.next_wave()
            self.assertIn("a", wave)
            self.assertEqual(sched.get_state("a"), NodeState.READY)
            sched.mark_running("a")
            self.assertEqual(sched.get_state("a"), NodeState.RUNNING)
            sched.mark_succeeded("a")
            self.assertEqual(sched.get_state("a"), NodeState.SUCCEEDED)

    # ------------------------------------------------------------------ #
    # DAGRunner tests                                                     #
    # ------------------------------------------------------------------ #

    def test_dag_runner_run_all_succeeded(self) -> None:
        """POSTCONDITION: run executes all nodes and returns completed report."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.succeeded_nodes, ("a", "b"))
            self.assertEqual(report.failed_nodes, ())
            self.assertIn("a", report.results)
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)

    def test_dag_runner_run_empty_wave_halt(self) -> None:
        """POSTCONDITION: run halts when no waves remain to execute."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            # Empty DAG - run must halt immediately without error
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(len(report.succeeded_nodes), 0)
            self.assertEqual(len(report.results), 0)

    def test_dag_runner_run_retry_on_failure(self) -> None:
        """POSTCONDITION: run retries failed node actions up to configured retry count."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            failing = self._action_factory.make_failing(Exception("fail"))
            dag.add_node("retry_me", failing, None, priority=0, retries=2)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.results["retry_me"].state, NodeState.FAILED)
            self.assertEqual(report.results["retry_me"].retries_attempted, 3)

    def test_dag_runner_run_fail_fast_stops_execution(self) -> None:
        """POSTCONDITION: FAIL_FAST halts wave execution on node failure."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", self._action_factory.make_failing(Exception("crash")), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), None, priority=0, retries=0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.results["a"].state, NodeState.FAILED)
            self.assertEqual(report.results["b"].state, NodeState.CANCELLED)

    def test_dag_runner_run_with_skip_downstream(self) -> None:
        """POSTCONDITION: run applies SKIP_DOWNSTREAM on node failure."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", self._action_factory.make_failing(Exception("crash")), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.skipped_nodes, ("b",))

    def test_dag_runner_run_reports_critical_path(self) -> None:
        """POSTCONDITION: run includes critical path in report."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.critical_path, ("a", "b"))

    def test_dag_runner_run_cycle_raises(self) -> None:
        """PRECONDITION: run raises CycleError if graph contains a cycle."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("cyc_a", self._action_factory.make(return_value=1), {"cyc_b"}, priority=0, retries=0)
            dag.add_node("cyc_b", self._action_factory.make(return_value=2), {"cyc_a"}, priority=0, retries=0)
            with self.assertRaises(CycleError):
                runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_dag_runner_run_dependency_validation(self) -> None:
        """PRECONDITION: run raises NodeNotFoundError for missing dependencies."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("orphan", self._action_factory.make(return_value=1), {"missing_node"}, priority=0, retries=0)
            with self.assertRaises(NodeNotFoundError):
                runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_dag_runner_run_multiple_waves_sequential(self) -> None:
        """POSTCONDITION: run executes waves sequentially to completion."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", self._action_factory.make(return_value=1), None, priority=0, retries=0)
            dag.add_node("b", self._action_factory.make(return_value=2), {"a"}, priority=0, retries=0)
            dag.add_node("c", self._action_factory.make(return_value=3), {"b"}, priority=0, retries=0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(len(report.succeeded_nodes), 3)
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["c"].state, NodeState.SUCCEEDED)

    # ------------------------------------------------------------------ #
    # Data type tests                                                     #
    # ------------------------------------------------------------------ #

    def test_dag_error_hierarchy(self) -> None:
        """INVARIANT: All DAG errors inherit from DAGError."""
        self.assertTrue(issubclass(CycleError, DAGError))
        self.assertTrue(issubclass(NodeNotFoundError, DAGError))
        self.assertTrue(issubclass(DuplicateNodeError, DAGError))
        self.assertTrue(issubclass(NodeExecutionError, DAGError))

    def test_node_definition_has_correct_fields(self) -> None:
        """INVARIANT: NodeDefinition has all required fields with correct types."""
        action = self._action_factory.make(return_value=0)
        nd = NodeDefinition(
            node_id="test",
            action=action,
            dependencies=frozenset(),
            priority=1,
            retries=0,
        )
        self.assertEqual(nd.node_id, "test")
        self.assertEqual(nd.priority, 1)
        self.assertEqual(nd.retries, 0)
        self.assertIsInstance(nd.dependencies, frozenset)

    def test_node_result_defaults(self) -> None:
        """INVARIANT: NodeResult has correct default field values."""
        nr = NodeResult(node_id="x", state=NodeState.PENDING)
        self.assertIsNone(nr.value)
        self.assertIsNone(nr.error)
        self.assertEqual(nr.duration_seconds, 0.0)
        self.assertEqual(nr.retries_attempted, 0)

    def test_node_state_enum_values(self) -> None:
        """INVARIANT: NodeState has all expected enum members."""
        expected = {"PENDING", "READY", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"}
        actual = {s.name for s in NodeState}
        self.assertEqual(actual, expected)

    def test_failure_policy_enum_values(self) -> None:
        """INVARIANT: FailurePolicy has all expected enum members."""
        expected = {"FAIL_FAST", "CONTINUE_ON_ERROR", "SKIP_DOWNSTREAM"}
        actual = {p.name for p in FailurePolicy}
        self.assertEqual(actual, expected)

    def test_dag_run_report_structure(self) -> None:
        """INVARIANT: DAGRunReport has all required fields."""
        report = DAGRunReport(
            total_nodes=1,
            succeeded_nodes=("a",),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.1,
            critical_path=("a",),
            results={"a": NodeResult(node_id="a", state=NodeState.SUCCEEDED, value=42)},
        )
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.wall_clock_seconds, 0.1)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T01:39:52Z
# LAST_CHANGED: 2026-11-10T01:38:12Z
# CHANGE: Added test_wavescheduler_get_state_initialized_from_dag to cover missing get_state contract compliance: tests state synchronization when get_state is called on a root node before next_wave(), and on a non-root node (PENDING state) before next_wave(). Combined with existing error test for nonexistent node, this covers all get_state branches per grounding spec.
# COVERAGE_AUDIT: 2026-11-10T01:39:52Z
# QA_AUDIT: 2026-11-10T01:38:43Z
# --- END AUTOFAB METADATA ---
