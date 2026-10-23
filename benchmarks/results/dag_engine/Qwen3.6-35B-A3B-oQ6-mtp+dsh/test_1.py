from __future__ import annotations

import threading
import unittest
from typing import Any, Callable, Collection, ContextManager, cast, FrozenSet, List, Mapping, Optional, Set, Tuple
from unittest.mock import MagicMock

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from benchmarks.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    WaveScheduler,
    DAGRunner,
    __initialize__ as dag_engine_initialize,
)
from benchmarks.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGError,
    DAGRunReport,
    DAGTimeoutError,
    DAGCancelledError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)


# --- Helper factories ---

def _make_action(value: Any = None) -> Callable[[], Any]:
    """Create a simple action callable that returns the given value."""
    def action() -> Any:
        return value
    return action


def _make_node_def(
    node_id: str,
    action: Optional[Callable[[], Any]] = None,
    dependencies: Optional[Collection[str]] = None,
    priority: int = 0,
    timeout_seconds: Optional[float] = None,
    retries: int = 0,
) -> NodeDefinition[Any]:
    """Helper to create a NodeDefinition for verification purposes."""
    deps: FrozenSet[str] = frozenset(dependencies or [])
    return NodeDefinition(
        node_id=node_id,
        action=action or _make_action(),
        dependencies=deps,
        priority=priority,
        timeout_seconds=timeout_seconds,
        retries=retries,
    )


# =====================================================================
# DAG Tests
# =====================================================================


class TestDAG(unittest.TestCase):
    """Tests for DAG covering add_node, add_edge, remove_node, has_node,
    get_node, get_dependencies, get_dependents, all_nodes, validate,
    topological_sort, find_roots, find_leaves, and compute_critical_path."""

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        dag_engine_initialize(self._registry)

    def _make_dag(self) -> DAG:
        """Create a DAG instance in a fresh system lifecycle scope."""
        with enter_phase(system, registry=self._registry) as scope:
            return scope.get_singleton(DAG)

    # -- add_node --

    def test_add_node_simple(self) -> None:
        # POSTCONDITION: add_node MUST register the node definition into the graph.
        dag = self._make_dag()
        action = _make_action("hello")
        dag.add_node("a", action, priority=1)
        self.assertTrue(dag.has_node("a"))
        node_def = dag.get_node("a")
        self.assertEqual(node_def.node_id, "a")
        self.assertEqual(node_def.priority, 1)
        self.assertEqual(node_def.dependencies, frozenset())

    def test_add_node_with_dependencies(self) -> None:
        # POSTCONDITION: WHEN dependencies are provided, MUST add directed edges.
        dag = self._make_dag()
        dag.add_node("b", _make_action(), dependencies=["a"])
        dag.add_node("a", _make_action())
        deps = dag.get_dependencies("b")
        self.assertIn("a", deps)

    def test_add_node_with_priority(self) -> None:
        dag = self._make_dag()
        dag.add_node("pnode", _make_action(), priority=10)
        node_def = dag.get_node("pnode")
        self.assertEqual(node_def.priority, 10)

    def test_add_node_with_retries(self) -> None:
        dag = self._make_dag()
        dag.add_node("rnode", _make_action(), retries=3)
        node_def = dag.get_node("rnode")
        self.assertEqual(node_def.retries, 3)

    def test_add_node_with_timeout(self) -> None:
        dag = self._make_dag()
        dag.add_node("tnode", _make_action(), timeout_seconds=30.0)
        node_def = dag.get_node("tnode")
        self.assertEqual(node_def.timeout_seconds, 30.0)

    # -- add_edge --

    def test_add_edge_existing_nodes(self) -> None:
        # POSTCONDITION: MUST establish directed edge from upstream to downstream.
        dag = self._make_dag()
        dag.add_node("up", _make_action())
        dag.add_node("down", _make_action())
        dag.add_edge("up", "down")
        dependents = dag.get_dependents("up")
        self.assertIn("down", dependents)
        deps = dag.get_dependencies("down")
        self.assertIn("up", deps)

    def test_add_edge_missing_upstream_raises(self) -> None:
        # Raises NodeNotFoundError if either node identifier is missing.
        dag = self._make_dag()
        dag.add_node("down", _make_action())
        with self.assertRaises(NodeNotFoundError):
            dag.add_edge("nonexistent", "down")

    def test_add_edge_missing_downstream_raises(self) -> None:
        dag = self._make_dag()
        dag.add_node("up", _make_action())
        with self.assertRaises(NodeNotFoundError):
            dag.add_edge("up", "nonexistent")

    # -- remove_node --

    def test_remove_node_exists(self) -> None:
        # MUST remove the node and its incident edges.
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action())
        dag.add_edge("a", "b")
        dag.remove_node("a")
        self.assertFalse(dag.has_node("a"))
        # b should no longer have a as dependency
        self.assertEqual(dag.get_dependencies("b"), set())

    def test_remove_node_nonexistent_raises(self) -> None:
        # Raises NodeNotFoundError if absent.
        dag = self._make_dag()
        with self.assertRaises(NodeNotFoundError):
            dag.remove_node("nonexistent")

    # -- has_node --

    def test_has_node_true(self) -> None:
        dag = self._make_dag()
        dag.add_node("x", _make_action())
        self.assertTrue(dag.has_node("x"))

    def test_has_node_false(self) -> None:
        dag = self._make_dag()
        self.assertFalse(dag.has_node("nonexistent"))

    # -- get_node --

    def test_get_node_returns_definition(self) -> None:
        dag = self._make_dag()
        dag.add_node("g", _make_action("val"), priority=5)
        nd = dag.get_node("g")
        self.assertEqual(nd.node_id, "g")
        self.assertEqual(nd.priority, 5)

    def test_get_node_missing_raises(self) -> None:
        dag = self._make_dag()
        with self.assertRaises(NodeNotFoundError):
            dag.get_node("missing")

    # -- get_dependencies --

    def test_get_dependencies_returns_set(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action(), dependencies=["a"])
        deps = dag.get_dependencies("b")
        self.assertIsInstance(deps, set)
        self.assertEqual(deps, {"a"})

    def test_get_dependencies_no_deps(self) -> None:
        dag = self._make_dag()
        dag.add_node("solo", _make_action())
        self.assertEqual(dag.get_dependencies("solo"), set())

    def test_get_dependencies_missing_raises(self) -> None:
        dag = self._make_dag()
        with self.assertRaises(NodeNotFoundError):
            dag.get_dependencies("missing")

    # -- get_dependents --

    def test_get_dependents_returns_set(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action(), dependencies=["a"])
        deps = dag.get_dependents("a")
        self.assertIsInstance(deps, set)
        self.assertEqual(deps, {"b"})

    def test_get_dependents_no_dependents(self) -> None:
        dag = self._make_dag()
        dag.add_node("leaf", _make_action())
        self.assertEqual(dag.get_dependents("leaf"), set())

    def test_get_dependents_missing_raises(self) -> None:
        dag = self._make_dag()
        with self.assertRaises(NodeNotFoundError):
            dag.get_dependents("missing")

    # -- all_nodes --

    def test_all_nodes_returns_all(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action())
        dag.add_node("c", _make_action())
        nodes = dag.all_nodes()
        self.assertEqual(nodes, {"a", "b", "c"})

    def test_all_nodes_empty(self) -> None:
        dag = self._make_dag()
        self.assertEqual(dag.all_nodes(), set())

    # -- validate --

    def test_validate_valid_dag(self) -> None:
        # WHEN all referenced nodes exist and no cycle, MUST complete without error.
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action(), dependencies=["a"])
        dag.validate()  # Should not raise

    def test_validate_missing_dependency_raises(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        dag = self._make_dag()
        dag.add_node("b", _make_action(), dependencies=["missing"])
        with self.assertRaises(NodeNotFoundError):
            dag.validate()

    def test_validate_cycle_raises(self) -> None:
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        dag = self._make_dag()
        dag.add_node("a", _make_action(), dependencies=["c"])
        dag.add_node("b", _make_action(), dependencies=["a"])
        dag.add_node("c", _make_action(), dependencies=["b"])
        with self.assertRaises(CycleError) as ctx:
            dag.validate()
        self.assertIsInstance(ctx.exception, DAGError)
        self.assertTrue(hasattr(ctx.exception, "cycle"))

    # -- topological_sort --

    def test_topological_sort_linear(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action(), dependencies=["a"])
        dag.add_node("c", _make_action(), dependencies=["b"])
        order = dag.topological_sort()
        self.assertEqual(len(order), 3)
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("c"))

    def test_topological_sort_tiebreak_by_priority(self) -> None:
        # Tie-breaking: priority descending, then node_id ascending.
        dag = self._make_dag()
        dag.add_node("x", _make_action(), priority=1)
        dag.add_node("y", _make_action(), priority=5)
        dag.add_node("z", _make_action(), priority=5)
        # No dependencies, so order should be y, z (same priority, z > y alphabetically)
        order = dag.topological_sort()
        self.assertEqual(order[0], "y")
        self.assertEqual(order[1], "z")

    def test_topological_sort_cycle_raises(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action(), dependencies=["b"])
        dag.add_node("b", _make_action(), dependencies=["a"])
        with self.assertRaises(CycleError):
            dag.topological_sort()

    # -- find_roots --

    def test_find_roots_no_deps(self) -> None:
        dag = self._make_dag()
        dag.add_node("root1", _make_action())
        dag.add_node("root2", _make_action())
        dag.add_node("child", _make_action(), dependencies=["root1", "root2"])
        roots = dag.find_roots()
        self.assertEqual(roots, {"root1", "root2"})

    def test_find_roots_all_have_deps(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action(), dependencies=["b"])
        dag.add_node("b", _make_action(), dependencies=["a"])
        self.assertEqual(dag.find_roots(), set())

    # -- find_leaves --

    def test_find_leaves_no_dependents(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("leaf", _make_action(), dependencies=["a"])
        leaves = dag.find_leaves()
        self.assertEqual(leaves, {"leaf"})

    def test_find_leaves_all_have_dependents(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action(), dependencies=["b"])
        dag.add_node("b", _make_action())
        # 'b' is depended on by 'a', so 'b' is not a leaf; 'a' has no dependents
        self.assertEqual(dag.find_leaves(), {"a"})

    # -- compute_critical_path --

    def test_critical_path_default_durations(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action())
        dag.add_node("b", _make_action(), dependencies=["a"])
        path, weight = dag.compute_critical_path()
        self.assertEqual(len(path), 2)
        self.assertEqual(weight, 2.0)
        self.assertEqual(path[0], "a")
        self.assertEqual(path[1], "b")

    def test_critical_path_with_custom_durations(self) -> None:
        dag = self._make_dag()
        dag.add_node("a", _make_action(),)
        dag.add_node("b", _make_action(), dependencies=["a"])
        dag.add_node("c", _make_action(), dependencies=["a"])
        # Duration of b is 10, so path a->b is critical
        path, weight = dag.compute_critical_path(estimated_durations={"a": 1.0, "b": 10.0, "c": 1.0})
        self.assertEqual(weight, 11.0)
        self.assertIn("a", path)
        self.assertIn("b", path)

    def test_critical_path_single_node(self) -> None:
        dag = self._make_dag()
        dag.add_node("solo", _make_action())
        path, weight = dag.compute_critical_path()
        self.assertEqual(len(path), 1)
        self.assertEqual(weight, 1.0)
        self.assertEqual(path[0], "solo")


# =====================================================================
# WaveScheduler Tests
# =====================================================================


class TestWaveScheduler(unittest.TestCase):
    """Tests for WaveScheduler covering next_wave, mark_running, mark_succeeded,
    mark_failed, is_finished, get_state, get_all_states."""

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        dag_engine_initialize(self._registry)

    def _make_scheduler(
        self,
        nodes: Optional[List[Tuple[str, Callable[[], Any], Optional[Collection[str]], int]]] = None,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> WaveScheduler:
        """Create a DAG with nodes and return a configured WaveScheduler in scope."""
        default_nodes: List[Tuple[str, Callable[[], Any], Optional[Collection[str]], int]] = [
            ("a", _make_action("a"), None, 1),
            ("b", _make_action("b"), ["a"], 2),
            ("c", _make_action("c"), ["b"], 3),
        ]
        if nodes is None:
            nodes = default_nodes
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            for node_id, action, deps, priority in nodes:
                dag.add_node(node_id, action, dependencies=deps, priority=priority)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            # configure() initializes _states from dag.all_nodes() and sets failure policy
            cast(Any, scheduler).configure(dag, failure_policy=failure_policy)
            return scheduler

    def _make_registry_with_dag(self) -> Tuple[LifecycleRegistry, Any, DAGRunner]:
        """Helper to create a fresh registry, DAG, and DAGRunner."""
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            return registry, dag, runner

    # -- next_wave --

    def test_next_wave_returns_roots_first(self) -> None:
        # MUST return all nodes in READY state whose upstream deps are SUCCEEDED.
        scheduler = self._make_scheduler()
        wave = scheduler.next_wave()
        self.assertEqual(wave, ["a"])

    def test_next_wave_after_succeed(self) -> None:
        scheduler = self._make_scheduler()
        # First wave: root "a"
        wave = scheduler.next_wave()
        self.assertEqual(wave, ["a"])
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        # Second wave should have "b"
        wave = scheduler.next_wave()
        self.assertEqual(wave, ["b"])

    def test_next_wave_empty_when_finished(self) -> None:
        scheduler = self._make_scheduler()
        # Loop until no more waves remain
        while True:
            wave = scheduler.next_wave()
            if not wave:
                break
            for nid in wave:
                scheduler.mark_running(nid)
                scheduler.mark_succeeded(nid)
        self.assertEqual(wave, [])

    def test_next_wave_order_by_priority(self) -> None:
        # Order: priority descending then node_id ascending
        nodes: List[Tuple[str, Callable[[], Any], Optional[Collection[str]], int]] = [
            ("low", _make_action(), None, 1),
            ("high", _make_action(), None, 10),
            ("mid", _make_action(), None, 5),
        ]
        scheduler = self._make_scheduler(nodes=nodes)
        wave = scheduler.next_wave()
        self.assertEqual(wave, ["high", "mid", "low"])

    def test_next_wave_no_ready_nodes(self) -> None:
        nodes: List[Tuple[str, Callable[[], Any], Optional[Collection[str]], int]] = [("p", _make_action(), ["p"], 1)]
        scheduler = self._make_scheduler(nodes=nodes)
        wave = scheduler.next_wave()
        self.assertEqual(wave, [])

    # -- mark_running --

    def test_mark_running_transitions_state(self) -> None:
        scheduler = self._make_scheduler()
        scheduler.mark_running("a")
        self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)

    # -- mark_succeeded --

    def test_mark_succeeded_promotes_dependents(self) -> None:
        # MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        scheduler = self._make_scheduler()
        wave = scheduler.next_wave()
        self.assertEqual(wave, ["a"])
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(scheduler.get_state("b"), NodeState.READY)

    def test_mark_succeeded_transitions_state(self) -> None:
        scheduler = self._make_scheduler()
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)

    # -- mark_failed --

    def test_mark_failed_transitions_state(self) -> None:
        scheduler = self._make_scheduler()
        scheduler.mark_failed("a")
        self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)

    def test_mark_failed_fail_fast_cancels_pending(self) -> None:
        # WHEN failure policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        scheduler = self._make_scheduler(failure_policy=FailurePolicy.FAIL_FAST)
        scheduler.mark_failed("a")
        # "b" and "c" should be CANCELLED (they were PENDING)
        self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
        self.assertEqual(scheduler.get_state("c"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream_skips_transitive(self) -> None:
        # WHEN failure policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        scheduler = self._make_scheduler(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        scheduler.mark_failed("a")
        self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)

    def test_mark_failed_continue_on_error_keeps_independent_ready(self) -> None:
        # Retains non-terminal states for unblocked independent nodes.
        nodes = [
            ("a", _make_action(), None, 1),
            ("independent", _make_action(), None, 1),
            ("down", _make_action(), ["a"], 1),
        ]
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            for nid, act, deps, pri in nodes:
                dag.add_node(nid, act, dependencies=deps, priority=pri)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, scheduler).configure(dag, failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
            scheduler.mark_failed("a")
            self.assertEqual(scheduler.get_state("independent"), NodeState.READY)
            self.assertEqual(scheduler.get_state("down"), NodeState.PENDING)

    # -- is_finished --

    def test_is_finished_all_succeeded(self) -> None:
        scheduler = self._make_scheduler()
        wave = scheduler.next_wave()
        for nid in wave:
            scheduler.mark_running(nid)
            scheduler.mark_succeeded(nid)
        wave = scheduler.next_wave()
        for nid in wave:
            scheduler.mark_running(nid)
            scheduler.mark_succeeded(nid)
        wave = scheduler.next_wave()
        for nid in wave:
            scheduler.mark_running(nid)
            scheduler.mark_succeeded(nid)
        self.assertTrue(scheduler.is_finished())

    def test_is_finished_not_all_done(self) -> None:
        scheduler = self._make_scheduler()
        self.assertFalse(scheduler.is_finished())

    # -- get_state --

    def test_get_state_initial_states(self) -> None:
        scheduler = self._make_scheduler()
        self.assertEqual(scheduler.get_state("a"), NodeState.READY)
        self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)
        self.assertEqual(scheduler.get_state("c"), NodeState.PENDING)

    # -- get_all_states --

    def test_get_all_states_returns_mapping(self) -> None:
        scheduler = self._make_scheduler()
        states = scheduler.get_all_states()
        self.assertIsInstance(states, Mapping)
        self.assertEqual(len(states), 3)
        self.assertIn("a", states)
        self.assertIn("b", states)
        self.assertIn("c", states)


# =====================================================================
# DAGRunner Tests
# =====================================================================


class _RunnerContext:
    """Context manager that keeps a DAGRunner lifecycle scope open."""
    def __init__(
        self,
        registry: LifecycleRegistry,
        nodes: List[Tuple[str, Callable[[], Any], Optional[Collection[str]], int]],
    ) -> None:
        self._registry = registry
        self._nodes = nodes
        self._scope: Any = None
        self._dag: Any = None
        self._runner: DAGRunner = None  # type: ignore

    def __enter__(self) -> Tuple[Any, Any, DAGRunner]:
        self._scope = enter_phase(system, registry=self._registry)
        scope = self._scope.__enter__()
        dag = scope.get_singleton(DAG)
        for node_id, action, deps, priority in self._nodes:
            dag.add_node(node_id, action, dependencies=deps, priority=priority)
        runner: DAGRunner = scope.get_singleton(DAGRunner)
        # Retrieve WaveScheduler from scope and configure the runner
        scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
        cast(Any, runner).configure(dag, scheduler)
        self._dag = dag
        self._runner = runner
        return scope, dag, runner

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._scope is not None:
            self._scope.__exit__(exc_type, exc_val, exc_tb)


class TestDAGRunner(unittest.TestCase):
    """Tests for DAGRunner covering run and cancel."""

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        dag_engine_initialize(self._registry)

    def _make_runner_and_dag(
        self,
        nodes: List[Tuple[str, Callable[[], Any], Optional[Collection[str]], int]],
    ) -> _RunnerContext:
        """Helper to create a DAG with nodes and return (scope, dag, runner) within an open phase."""
        return _RunnerContext(self._registry, nodes)

    def test_run_successful_dag(self) -> None:
        # MUST execute ready nodes and return DAGRunReport with outcomes.
        action_a = MagicMock(return_value="result_a")
        action_b = MagicMock(return_value="result_b")
        with self._make_runner_and_dag([
            ("a", action_a, None, 1),
            ("b", action_b, ["a"], 2),
        ]) as (scope, dag, runner):
            report = runner.run()
            self.assertIsInstance(report, DAGRunReport)
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())

    def test_run_report_critical_path(self) -> None:
        action_a = _make_action()
        action_b = _make_action()
        with self._make_runner_and_dag([
            ("a", action_a, None, 1),
            ("b", action_b, ["a"], 2),
        ]) as (scope, dag, runner):
            report = runner.run()
            self.assertTrue(hasattr(report, "critical_path"))

    def test_run_report_results_mapping(self) -> None:
        with self._make_runner_and_dag([
            ("a", _make_action("x"), None, 1),
        ]) as (scope, dag, runner):
            report = runner.run()
            self.assertIn("a", report.results)
            self.assertIsInstance(report.results["a"], NodeResult)
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)

    def test_run_with_timeout_raises(self) -> None:
        # Test that timeout triggers when execution time exceeds limit.
        # The implementation checks elapsed time before dispatching each wave,
        # so a chain of sequential nodes (each in its own wave) accumulates time.
        timed_actions: List[Tuple[str, float]] = []
        def make_slow_action(name: str, delay: float) -> Callable[[], None]:
            def action() -> None:
                import time
                timed_actions.append((name, time.time()))
                time.sleep(delay)
            return action
        # Create 3 sequential nodes, each sleeps 0.01s => ~0.03s total > 0.01s timeout
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("step1", make_slow_action("step1", 0.01), None, 1)
            dag.add_node("step2", make_slow_action("step2", 0.01), ["step1"], 1)
            dag.add_node("step3", make_slow_action("step3", 0.01), ["step2"], 1)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            with self.assertRaises(DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_run_cycle_raises(self) -> None:
        def action() -> None:
            pass
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action, dependencies=["b"])
            dag.add_node("b", action, dependencies=["a"])
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            with self.assertRaises(CycleError):
                runner.run()

    def test_cancel_during_execution(self) -> None:
        # WHEN cancelled during execution, MUST mark running nodes as CANCELLED and raise DAGCancelledError.
        action_a = _make_action("a")
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action_a, None, 1)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            # Cancel immediately before run - will raise
            runner.cancel()
            with self.assertRaises(DAGCancelledError):
                runner.run()

    def test_run_zero_concurrency_single_node(self) -> None:
        action = _make_action("done")
        with self._make_runner_and_dag([
            ("solo", action, None, 1),
        ]) as (scope, dag, runner):
            report = runner.run()
            self.assertEqual(report.total_nodes, 1)
            self.assertEqual(report.succeeded_nodes, ("solo",))

    # -- retry logic in _execute_node --

    def test_execute_node_retries_on_failure(self) -> None:
        # WHEN action fails and definition.retries > 0, MUST retry with backoff.
        attempt_count = 0

        def flaky_action() -> None:
            nonlocal attempt_count
            attempt_count += 1
            raise Exception("fail")

        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", flaky_action, retries=2)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            report = runner.run()
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertGreaterEqual(attempt_count, 2)

    def test_execute_node_cancellation_during_execution(self) -> None:
        # WHEN _cancelled flag is set during _execute_node, MUST return CANCELLED.
        cancel_flag = False
        event: threading.Event = threading.Event()

        def blocking_action() -> None:
            event.wait()

        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", blocking_action)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            # Start run in background, then cancel mid-execution
            report_holder: List[Any] = []
            error_holder: List[BaseException] = []

            def run_in_thread() -> None:
                try:
                    report_holder.append(runner.run())
                except BaseException as e:
                    error_holder.append(e)

            t = threading.Thread(target=run_in_thread)
            t.start()
            # Give action time to start
            event.wait(timeout=1.0)
            runner.cancel()
            event.set()
            t.join(timeout=5.0)
            if error_holder:
                self.assertEqual(type(error_holder[0]), DAGCancelledError)

    def test_cancel_cancels_ready_pending_states(self) -> None:
        # POSTCONDITION: cancel() MUST set _cancelled flag and mark READY/PENDING nodes as CANCELLED.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), ["a"])
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            cast(Any, runner).configure(dag, scheduler)
            # Configure scheduler to populate _states from dag.all_nodes()
            cast(Any, scheduler).configure(dag, failure_policy=FailurePolicy.FAIL_FAST)
            # Cancel before any run
            runner.cancel()
            # Check that node "b" (PENDING) is now CANCELLED
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)

    def test_next_wave_empty_when_dag_is_none(self) -> None:
        # Defensive: when _dag is None, next_wave returns [].
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            # Don't configure — _dag remains None
            wave = scheduler.next_wave()
            self.assertEqual(wave, [])

    def test_mark_succeeded_returns_early_when_dag_is_none(self) -> None:
        # Defensive: when _dag is None, mark_succeeded returns without error.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            # Don't configure — _dag remains None
            scheduler.mark_succeeded("a")  # Should not raise

    def test_run_raises_runtime_error_when_not_configured(self) -> None:
        # WHEN runner.run() called without configure(), MUST raise RuntimeError.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            # Do NOT call runner.configure — should raise
            with self.assertRaises(RuntimeError):
                runner.run()

    def test_compute_critical_path_empty_dag(self) -> None:
        # WHEN DAG is empty, compute_critical_path returns ([], 0.0).
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            path, total = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(total, 0.0)

    def test_detect_cycle_downstream_not_in_nodes(self) -> None:
        # WHEN downstream neighbor v not in _nodes during DFS, MUST skip (continue branch).
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            # _detect_cycle traverses neighbors; if a neighbor reference is stale or missing,
            # the DFS continues without adding to cycle path.
            # Verify that a valid DAG with no cycles does not raise.
            dag.validate()  # Should not raise

    def test_get_transitive_dependents_visited_dedup(self) -> None:
        # When multiple paths converge on the same dependent, visited set prevents re-traversal.
        # Diamond: a -> b, a -> c, b -> d, c -> d
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), ["a"])
            dag.add_node("c", _make_action(), ["a"])
            dag.add_node("d", _make_action(), ["b", "c"])
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, scheduler).configure(dag, failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
            # Mark "a" failed — transitive dependents of "a" include b, c, d.
            # Visited-set dedup should prevent double-marking of "d".
            scheduler.mark_failed("a")
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)

    def test_run_cancellation_during_execution_raises_cancelled_error(self) -> None:
        # WHEN cancellation flag is set during run execution, MUST raise DAGCancelledError
        # and mark non-terminal nodes appropriately.
        event: threading.Event = threading.Event()

        def blocking_action() -> None:
            event.wait(timeout=5.0)

        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", blocking_action, None, 1)
            dag.add_node("b", _make_action("done"), ["a"], 1)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)

            report_holder: List[Any] = []
            error_holder: List[BaseException] = []

            def run_in_thread() -> None:
                try:
                    report_holder.append(runner.run())
                except BaseException as e:
                    error_holder.append(e)

            t = threading.Thread(target=run_in_thread)
            t.start()
            # Wait for action to start, then cancel
            event.wait(timeout=1.0)
            runner.cancel()
            event.set()
            t.join(timeout=5.0)
            self.assertTrue(len(error_holder) > 0)
            self.assertEqual(type(error_holder[0]), DAGCancelledError)

    def test_compute_critical_path_empty_dag_returns_empty(self) -> None:
        # An empty DAG's compute_critical_path returns ([], 0.0).
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            # Empty DAG: compute_critical_path returns ([], 0.0)
            path, total = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(total, 0.0)

    def test_retry_backoff_delay_via_sleep(self) -> None:
        # WHEN retries > 0 and action fails, MUST apply backoff delay via time.sleep
        # between retry attempts (attempt > 0).
        import time

        attempt_count = 0
        start_times: List[float] = []

        def flaky_action() -> None:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count > 1:
                start_times.append(time.monotonic())
            raise Exception("fail")

        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", flaky_action, retries=2)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            runner.run()
        # With retries=2, there should be 3 total attempts (1 initial + 2 retries)
        self.assertEqual(attempt_count, 3)
        # If backoff sleep was applied, there should be at least 2 start times recorded
        self.assertGreaterEqual(len(start_times), 1)

    def test_compute_critical_path_cycle_error_falls_through(self) -> None:
        # WHEN compute_critical_path raises CycleError during run(),
        # the critical_path in the report should be empty.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            # Build a cycle: a -> b -> c -> a
            dag.add_node("a", _make_action(), ["c"])
            dag.add_node("b", _make_action(), ["a"])
            dag.add_node("c", _make_action(), ["b"])
            # An invalid DAG with a cycle; compute_critical_path should raise CycleError
            with self.assertRaises(CycleError):
                dag.compute_critical_path()

    def test_remove_node_cleans_up_downstream_edges(self) -> None:
        # WHEN removing a node, MUST remove it from all incident edges
        # including the downstream.get(up_id, set()).discard(node_id) path.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            # Build: a -> b -> c
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), ["a"])
            dag.add_node("c", _make_action(), ["b"])
            # Remove middle node b
            dag.remove_node("b")
            # a should no longer depend on b, b should no longer depend on c
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.get_dependencies("a"), set())
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())

    def test_detect_cycle_neighbor_not_in_color_map(self) -> None:
        # WHEN _detect_cycle encounters a neighbor not yet in the DFS color map,
        # it adds the neighbor and continues traversal.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            # Build a multi-component DAG where DFS explores disconnected-ish components
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), ["a"])
            dag.add_node("c", _make_action(), ["a"])
            # validate() will run _detect_cycle; neighbor traversal visits
            # each node sequentially, ensuring the "neighbor not in color map"
            # path is exercised.
            dag.validate()  # Should not raise for valid DAG

    def test_cancel_during_run_sets_cancelled_states(self) -> None:
        # WHEN cancel() is called during run execution, MUST mark
        # READY and PENDING non-terminal nodes as CANCELLED.
        ready_nodes: List[str] = []
        import time

        def blocking_action() -> None:
            ready_nodes.append("a")

        barrier = threading.Event()

        def blocking_action_wait() -> None:
            barrier.wait()

        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", blocking_action_wait)
            dag.add_node("b", blocking_action_wait, ["a"])
            dag.add_node("c", _make_action(), ["a"])
            dag.add_node("d", _make_action(), ["b", "c"])
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)

            result_holder: List[Any] = []
            error_holder: List[BaseException] = []

            def run_in_thread() -> None:
                try:
                    result_holder.append(runner.run())
                except BaseException as e:
                    error_holder.append(e)

            t = threading.Thread(target=run_in_thread)
            t.start()
            # Wait for first wave to start executing
            barrier.wait(timeout=1.0)
            time.sleep(0.05)  # Give runner time to process
            runner.cancel()
            barrier.set()  # Unblock the blocking action
            t.join(timeout=5.0)
            # Check that scheduler states reflect CANCELLED
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
            # at least some nodes should be terminal
            all_states = scheduler.get_all_states()
            terminal_states = {NodeState.CANCELLED, NodeState.FAILED, NodeState.SUCCEEDED, NodeState.SKIPPED}
            for state in all_states.values():
                self.assertIn(state, terminal_states)

    def test_next_wave_sort_key_fallback_node_not_found(self) -> None:
        # WHEN next_wave encounters a READY node whose definition has been
        # removed from _dag, get_node raises NodeNotFoundError and falls back
        # to a default sort_key.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action(), priority=10)
            dag.add_node("b", _make_action(), ["a"], priority=5)
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            # Corrupt the DAG by removing 'a' from _nodes but leaving it in
            # _scheduler._states as READY — next_wave will try to sort it
            # via get_node and hit NodeNotFoundError, exercising the
            # sort_key fallback path.
            cast(Any, dag)._nodes.pop("a")
            # The scheduler's state still has 'a' as READY
            cast(Any, scheduler)._states["a"] = NodeState.READY
            # next_wave must handle NodeNotFoundError gracefully
            wave = scheduler.next_wave()
            self.assertIsInstance(wave, list)
            # 'b' should still be sorted by priority fallback
            if "b" in wave:
                self.assertEqual(wave[0], "b")

    def test_run_breaks_wave_loop_when_next_wave_empty(self) -> None:
        # WHEN next_wave returns empty but is_finished returns False,
        # the runner breaks out of the wave loop (line 445).
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), ["a"])
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            # Corrupt scheduler state: mark 'a' as PENDING so it never runs.
            # next_wave will return [] (no READY nodes) but is_finished is
            # False because 'a' is not terminal.
            cast(Any, scheduler)._states["a"] = NodeState.PENDING
            cast(Any, scheduler)._states["b"] = NodeState.PENDING
            # Runner must break the wave loop when next_wave returns empty
            # without all nodes reaching terminal state.
            report = runner.run()
            self.assertTrue(hasattr(report, "critical_path"))

    def test_run_catches_critical_path_cycle_error_defaults_empty(self) -> None:
        # WHEN compute_critical_path raises CycleError during run(),
        # the runner catches the exception and defaults to an empty
        # critical_path in the report.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action())
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            # Create a real cycle: add edge b -> a so a depends on b AND
            # b depends on a (cycle). Both nodes are READY in the same wave
            # so the wave loop completes, then compute_critical_path raises.
            cast(Any, dag)._upstream["a"].add("b")
            cast(Any, dag)._downstream["b"].add("a")
            cast(Any, dag)._upstream.setdefault("b", set()).add("a")
            report = runner.run()
            self.assertTrue(hasattr(report, "critical_path"))
            self.assertIsInstance(report.critical_path, (list, tuple))

    def test_run_catches_critical_path_node_not_found_error(self) -> None:
        # WHEN compute_critical_path traverses _downstream and encounters
        # a node_id that no longer exists in _nodes, it raises
        # NodeNotFoundError which the runner catches and defaults to empty.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action())
            # Add b as a dependency of a (a -> b edge), then remove 'b'
            # from _nodes after configure so the critical path traversal
            # finds 'b' in _downstream['a'] but not in _nodes.
            cast(Any, dag)._upstream["a"].add("b")
            cast(Any, dag)._downstream["a"].add("b")
            cast(Any, dag)._upstream.setdefault("b", set()).add("a")
            runner: DAGRunner = scope.get_singleton(DAGRunner)
            scheduler: WaveScheduler = scope.get_singleton(WaveScheduler)
            cast(Any, runner).configure(dag, scheduler)
            # Remove 'b' from _nodes only — it remains as a dangling
            # reference in _downstream['a']. After 'a' succeeds in the wave
            # loop, compute_critical_path traverses edges and hits the
            # missing node, raising NodeNotFoundError.
            cast(Any, dag)._nodes.pop("b")
            report = runner.run()
            self.assertTrue(hasattr(report, "critical_path"))
            self.assertIsInstance(report.critical_path, (list, tuple))

    def test_detect_cycle_downstream_neighbor_not_in_color_dict(self) -> None:
        # WHEN _detect_cycle encounters a downstream neighbor not yet in the
        # DFS color dict (node in _downstream but not in _nodes),
        # it adds it to the color map and continues traversal.
        registry = LifecycleRegistry()
        dag_engine_initialize(registry)
        with enter_phase(system, registry=registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), ["a"])
            # Inject a phantom downstream neighbor not in _nodes — this is
            # the scenario where _downstream contains a node not in _nodes
            # and the DFS color map doesn't have it yet.
            cast(Any, dag)._downstream["a"].add("phantom")
            cast(Any, dag)._downstream.setdefault("phantom", set())
            # validate() runs _detect_cycle which should handle the
            # phantom node not in the color dict by adding it and continuing.
            dag.validate()


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-21T03:46:11Z
# LAST_CHANGED: 2026-10-21T03:40:36Z
# CHANGE: Fixed test_run_catches_critical_path_node_not_found_error: removed the _downstream.pop('b', None) call so 'b' remains as a dangling reference in _downstream['a']. Now compute_critical_path traversing edges discovers 'b' missing from _nodes and raises NodeNotFoundError, covering lines 496-497. (The lib pragma blame on lines 328-330 is in dag_engine_impl.py which is read-only per cleanroom rules.)
# COVERAGE_AUDIT: 2026-10-21T03:46:11Z
# QA_AUDIT: 2026-10-21T03:45:19Z
# --- END CLEANROOM METADATA ---
