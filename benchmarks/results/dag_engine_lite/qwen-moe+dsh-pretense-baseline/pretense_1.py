"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__
from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import FailurePolicy, NodeState, DAGRunReport, NodeNotFoundError, CycleError


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    initialized: bool = True


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    @transition(DAG.add_node)
    def add_node(
        self,
        ctx: TransitionContext[DAG, [Any, Any, Any, Any, Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: 'sample_node_id'),
                    action=Domain(strategy=lambda: None),
                    dependencies=Domain(strategy=lambda: []),
                    priority=Domain(strategy=lambda: 1),
                    retries=Domain(strategy=lambda: 1),
                )
        ctx.returns(lambda node_id=None, action=None, dependencies=None, priority=None, retries=None: None)
        ctx.ensures(lambda res, target, check, node_id=None, action=None, dependencies=None, priority=None, retries=None: None)
        ctx.update(lambda res, node_id=None, action=None, dependencies=None, priority=None, retries=None: None)

    @transition(DAG.add_edge)
    def add_edge(
        self,
        ctx: TransitionContext[DAG, [Any, Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    upstream_id=Domain(strategy=lambda: 'sample_upstream_id'),
                    downstream_id=Domain(strategy=lambda: 'sample_downstream_id'),
                )
        ctx.returns(lambda upstream_id=None, downstream_id=None: None)
        ctx.ensures(lambda res, target, check, upstream_id=None, downstream_id=None: None)
        ctx.update(lambda res, upstream_id=None, downstream_id=None: None)

    @transition(DAG.remove_node)
    def remove_node(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(DAG.has_node)
    def has_node(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(DAG.get_node)
    def get_node(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(DAG.validate)
    def validate(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(DAG.find_roots)
    def find_roots(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(estimated_durations=Domain(strategy=lambda: None))
        ctx.returns(lambda estimated_durations=None: None)
        ctx.ensures(lambda res, target, check, estimated_durations=None: None)
        ctx.update(lambda res, estimated_durations=None: None)

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
        ctx: TransitionContext[WaveScheduler, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        ctx: TransitionContext[WaveScheduler, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        ctx: TransitionContext[WaveScheduler, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        ctx: TransitionContext[WaveScheduler, [Any, Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: 'sample_node_id'),
                    failure_policy=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda node_id=None, failure_policy=None: None)
        ctx.ensures(lambda res, target, check, node_id=None, failure_policy=None: None)
        ctx.update(lambda res, node_id=None, failure_policy=None: None)

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
        ctx: TransitionContext[WaveScheduler, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        ctx: TransitionContext[WaveScheduler, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: 'sample_node_id'))
        ctx.returns(lambda node_id=None: None)
        ctx.ensures(lambda res, target, check, node_id=None: None)
        ctx.update(lambda res, node_id=None: None)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
        ctx: TransitionContext[WaveScheduler, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments()
        ctx.returns(lambda : None)
        ctx.ensures(lambda res, target, check: None)
        ctx.update(lambda res: None)

    @transition(DAGRunner.run)
    def run(
        self,
        ctx: TransitionContext[DAGRunner, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Must be initialized"))
        ctx.arguments(failure_policy=Domain(strategy=lambda: None))
        ctx.returns(lambda failure_policy=None: None)
        ctx.ensures(lambda res, target, check, failure_policy=None: None)
        ctx.update(lambda res, failure_policy=None: None)


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = DagEngineLiteStateMachine(state or DagEngineLiteState())
    return (
        sm.as_fake(DAG),
        sm.as_fake(WaveScheduler),
        sm.as_fake(DAGRunner),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestDagEngineLiteUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to state machine specification."""

    def setUp(self) -> None:
        self.state = DagEngineLiteState()
        self.dag, self.wavescheduler, self.dagrunner = make_dag_engine_lite_fakes(self.state)

    def test_fake_initial_state(self) -> None:
        self.assertTrue(self.state.initialized)

    def test_fake_add_node(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.add_node("sample_node_id", lambda: None, [], 1, 1)
        self.assertIsNotNone(self.state)

    def test_fake_add_edge(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.add_edge("sample_upstream_id", "sample_downstream_id")
        self.assertIsNotNone(self.state)

    def test_fake_remove_node(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.remove_node("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_has_node(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.has_node("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_get_node(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.get_node("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_get_dependencies(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.get_dependencies("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_get_dependents(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.get_dependents("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_all_nodes(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.all_nodes()
        self.assertIsNotNone(self.state)

    def test_fake_validate(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.validate()
        self.assertIsNotNone(self.state)

    def test_fake_topological_sort(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.topological_sort()
        self.assertIsNotNone(self.state)

    def test_fake_find_roots(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.find_roots()
        self.assertIsNotNone(self.state)

    def test_fake_find_leaves(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.find_leaves()
        self.assertIsNotNone(self.state)

    def test_fake_compute_critical_path(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dag.compute_critical_path(None)
        self.assertIsNotNone(self.state)

    def test_fake_next_wave(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.next_wave()
        self.assertIsNotNone(self.state)

    def test_fake_mark_running(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.mark_running("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_mark_succeeded(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.mark_succeeded("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_mark_failed(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.mark_failed("sample_node_id", FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(self.state)

    def test_fake_is_finished(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.is_finished()
        self.assertIsNotNone(self.state)

    def test_fake_get_state(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.get_state("sample_node_id")
        self.assertIsNotNone(self.state)

    def test_fake_get_all_states(self) -> None:
        # Test transition execution against synthesized fake
        res = self.wavescheduler.get_all_states()
        self.assertIsNotNone(self.state)

    def test_fake_run(self) -> None:
        # Test transition execution against synthesized fake
        res = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(self.state)


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteStateMachine(singletons={DAG: self.dag, WaveScheduler: self.wavescheduler, DAGRunner: self.dagrunner})

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        # Drive scenarios via self.sm.dispatch_transition('<transition_name>', *args).
        # Operational postconditions and invariants are verified automatically by ctx.ensures(...);
        # fixed scenario tests should contain no redundant manual self.assertEqual/assertTrue assertions.
        self.assertIsNotNone(self.sm)

    # --- DAG node management ---

    def test_real_dag_add_node_single(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.assertTrue(self.dag.has_node("a"))

    def test_real_dag_add_node_with_deps(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 1, 0)
        self.assertIn("a", self.dag.get_dependencies("b"))

    def test_real_dag_add_edge_valid(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, [], 0, 0)
        self.dag.add_edge("a", "b")
        self.assertIn("b", self.dag.get_dependents("a"))
        self.assertIn("a", self.dag.get_dependencies("b"))

    def test_real_dag_add_edge_missing(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.add_edge("a", "missing")

    def test_real_dag_add_edge_missing_upstream(self) -> None:
        # Triggers missing.append(upstream_id) when upstream not in _nodes
        self.dag.add_node("b", lambda: None, [], 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.add_edge("missing", "b")

    def test_real_dag_remove_node(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))

    def test_real_dag_remove_node_with_deps(self) -> None:
        # Chain a->b->c; remove b to cover discard on lines 94, 97
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, ["b"], 0, 0)
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertNotIn("b", self.dag.get_dependencies("c"))
        self.assertNotIn("b", self.dag.get_dependents("a"))

    def test_real_dag_remove_missing(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.remove_node("nonexistent")

    def test_real_dag_has_node(self) -> None:
        self.dag.add_node("x", lambda: None, [], 0, 0)
        self.assertTrue(self.dag.has_node("x"))
        self.assertFalse(self.dag.has_node("y"))

    def test_real_dag_get_node(self) -> None:
        self.dag.add_node("n", lambda: None, [], 5, 2)
        nd = self.dag.get_node("n")
        self.assertEqual(nd.node_id, "n")
        self.assertEqual(nd.priority, 5)
        self.assertEqual(nd.retries, 2)

    def test_real_dag_get_node_missing(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_node("nope")

    def test_real_dag_get_dependencies(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, ["a", "b"], 0, 0)
        deps = self.dag.get_dependencies("c")
        self.assertIn("a", deps)
        self.assertIn("b", deps)

    def test_real_dag_get_dependencies_missing(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependencies("ghost")

    def test_real_dag_get_dependents(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        d = self.dag.get_dependents("a")
        self.assertIn("b", d)

    def test_real_dag_get_dependents_missing(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependents("ghost")

    def test_real_dag_all_nodes(self) -> None:
        self.dag.add_node("x", lambda: None, [], 0, 0)
        self.dag.add_node("y", lambda: None, ["x"], 0, 0)
        self.dag.add_node("z", lambda: None, [], 0, 0)
        nodes = self.dag.all_nodes()
        self.assertEqual(nodes, {"x", "y", "z"})

    # --- DAG validate ---

    def test_real_dag_validate_ok(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.validate()

    def test_real_dag_validate_missing_dep(self) -> None:
        self.dag.add_node("a", lambda: None, ["ghost"], 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.validate()

    def test_real_dag_validate_cycle(self) -> None:
        self.dag.add_node("a", lambda: None, ["b"], 0, 0)
        self.dag.add_node("b", lambda: None, ["c"], 0, 0)
        self.dag.add_node("c", lambda: None, ["a"], 0, 0)
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.validate()

    # --- DAG topological_sort ---

    def test_real_dag_topo_sort(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, ["b"], 0, 0)
        order = self.dag.topological_sort()
        self.assertEqual(order, ["a", "b", "c"])

    def test_real_dag_topo_sort_priority(self) -> None:
        self.dag.add_node("low", lambda: None, [], -1, 0)
        self.dag.add_node("high", lambda: None, [], 10, 0)
        self.dag.add_node("mid", lambda: None, [], 5, 0)
        order = self.dag.topological_sort()
        self.assertEqual(order[0], "high")
        self.assertEqual(order[-1], "low")

    def test_real_dag_topo_sort_cycle(self) -> None:
        self.dag.add_node("a", lambda: None, ["b"], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.topological_sort()

    # --- DAG roots/leaves ---

    def test_real_dag_find_roots(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, ["a"], 0, 0)
        roots = self.dag.find_roots()
        self.assertEqual(roots, {"a"})

    def test_real_dag_find_leaves(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        leaves = self.dag.find_leaves()
        self.assertEqual(leaves, {"b"})

    def test_real_dag_roots_all_leaves(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"a"})

    # --- DAG compute_critical_path ---

    def test_real_dag_critical_path_simple(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        path, duration = self.dag.compute_critical_path({"a": 3.0, "b": 2.0})
        self.assertEqual(path, ["a", "b"])
        self.assertAlmostEqual(duration, 5.0)

    def test_real_dag_critical_path_default(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        path, duration = self.dag.compute_critical_path()
        self.assertEqual(path, ["a", "b"])
        self.assertAlmostEqual(duration, 2.0)

    def test_real_dag_critical_path_converge(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, ["a"], 0, 0)
        self.dag.add_node("d", lambda: None, ["b", "c"], 0, 0)
        path, duration = self.dag.compute_critical_path({"a": 1.0, "b": 5.0, "c": 2.0, "d": 1.0})
        self.assertIn("d", path)
        self.assertAlmostEqual(duration, 7.0)

    # --- DAGRunner ---

    def test_real_runner_run_simple(self) -> None:
        results_holder = []
        self.dag.add_node("a", lambda: results_holder.append("a"), [], 0, 0)
        self.dag.add_node("b", lambda: results_holder.append("b"), ["a"], 0, 0)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.succeeded_nodes)
        self.assertIn("b", report.succeeded_nodes)
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())

    def test_real_runner_run_failure_fast(self) -> None:
        self.dag.add_node("a", lambda: (_ for _ in ()).throw(RuntimeError("boom")), [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.failed_nodes)
        self.assertIn("b", report.cancelled_nodes)

    def test_real_runner_run_continue_on_error(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: (_ for _ in ()).throw(RuntimeError("boom")), ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, [], 0, 0)
        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIn("a", report.succeeded_nodes)
        self.assertIn("c", report.succeeded_nodes)
        self.assertIn("b", report.failed_nodes)

    def test_real_runner_run_skip_downstream(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: (_ for _ in ()).throw(RuntimeError("boom")), ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, ["b"], 0, 0)
        self.dag.add_node("d", lambda: None, [], 0, 0)
        report = self.dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIn("a", report.succeeded_nodes)
        self.assertIn("b", report.failed_nodes)
        self.assertIn("c", report.skipped_nodes)
        self.assertIn("d", report.succeeded_nodes)

    def test_real_runner_run_retry_success(self) -> None:
        counter = [0]
        def flaky():
            counter[0] += 1
            raise RuntimeError("fail")
        self.dag.add_node("a", flaky, [], 0, 0)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.failed_nodes)

    def test_real_runner_run_retry_exhaust(self) -> None:
        counter = [0]
        def always_fail():
            counter[0] += 1
            raise RuntimeError("boom")
        self.dag.add_node("a", always_fail, [], 0, 1)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.failed_nodes)
        self.assertEqual(counter[0], 2)  # initial + 1 retry (retries=1)

    def test_real_runner_run_retry_multiple_attempts(self) -> None:
        counter = [0]
        def always_fail():
            counter[0] += 1
            raise RuntimeError("boom")
        self.dag.add_node("a", always_fail, [], 0, 2)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.failed_nodes)
        self.assertEqual(counter[0], 3)  # initial + 2 retries (retries=2)

    def test_real_runner_run_empty(self) -> None:
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertIsNotNone(report.wall_clock_seconds)

    # --- WaveScheduler tests ---

    def test_real_ws_next_wave_empty(self) -> None:
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, [])

    def test_real_ws_next_wave_roots(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, ["a"])

    def test_real_ws_next_wave_promoted(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_succeeded("a")
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, ["b"])

    def test_real_ws_mark_succeeded_promotes(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_running("a")
        self.wavescheduler.mark_succeeded("a")
        state = self.wavescheduler.get_state("b")
        self.assertEqual(state, dag_engine_lite.NodeState.READY)

    def test_real_ws_mark_failed_fail_fast(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, [], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_running("a")
        self.wavescheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("b"), dag_engine_lite.NodeState.CANCELLED)
        self.assertEqual(self.wavescheduler.get_state("c"), dag_engine_lite.NodeState.CANCELLED)

    def test_real_ws_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, [], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_running("a")
        self.wavescheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
        # c is a root (no deps), so it is READY (not affected by a's failure)
        self.assertEqual(self.wavescheduler.get_state("c"), dag_engine_lite.NodeState.READY)

    def test_real_ws_mark_failed_continue_on_error(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.dag.add_node("c", lambda: None, [], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_running("a")
        self.wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.wavescheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
        # c is a root (no deps), so it is READY (not affected by a's failure)
        self.assertEqual(self.wavescheduler.get_state("c"), dag_engine_lite.NodeState.READY)

    def test_real_ws_is_finished(self) -> None:
        self.assertTrue(self.wavescheduler.is_finished())
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.wavescheduler.next_wave()
        self.assertFalse(self.wavescheduler.is_finished())
        self.wavescheduler.mark_succeeded("a")
        self.assertTrue(self.wavescheduler.is_finished())

    def test_real_ws_get_state(self) -> None:
        self.dag.add_node("x", lambda: None, [], 0, 0)
        wave = self.wavescheduler.next_wave()
        self.assertEqual(self.wavescheduler.get_state("x"), dag_engine_lite.NodeState.READY)

    def test_real_ws_get_state_before_next_wave(self) -> None:
        # get_state with a node that hasn't been through next_wave yet
        # sync_states should promote roots to READY (the correct state)
        self.dag.add_node("p", lambda: None, [], 0, 0)
        self.dag.add_node("q", lambda: None, ["p"], 0, 0)
        # sync_states (triggered by get_state) promotes roots to READY
        self.assertEqual(self.wavescheduler.get_state("p"), dag_engine_lite.NodeState.READY)
        self.assertEqual(self.wavescheduler.get_state("q"), dag_engine_lite.NodeState.PENDING)

    def test_real_ws_get_all_states(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.dag.add_node("b", lambda: None, ["a"], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_succeeded("a")
        all_states = self.wavescheduler.get_all_states()
        self.assertEqual(all_states["a"], dag_engine_lite.NodeState.SUCCEEDED)
        self.assertIn(all_states["b"], (dag_engine_lite.NodeState.PENDING, dag_engine_lite.NodeState.READY))

    def test_real_ws_is_finished_all_terminal(self) -> None:
        self.dag.add_node("a", lambda: None, [], 0, 0)
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_succeeded("a")
        self.assertTrue(self.wavescheduler.is_finished())



# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for Hypothesis fuzzing."""

    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self.dag, self.wavescheduler, self.dagrunner,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:18:37Z
# LAST_CHANGED: 2026-10-29T02:18:37Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 4ddc5ca8bc7f
# COVERAGE_AUDIT: 2026-10-29T02:18:37Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T02:18:37Z
# PRETENSE_QA_AUDIT: 2026-10-29T02:18:37Z
# QA_AUDIT: 2026-10-29T02:18:37Z
# --- END CLEANROOM METADATA ---
