"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
import unittest

from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


def _make_action(return_value: Any = "ok") -> Callable[[], Any]:
    """Factory helper creating a standard zero-argument action callable."""
    def _action() -> Any:
        return return_value
    return _action


class MockDAG(dag_engine_lite.DAG):
    """Lightweight mock implementation of the DAG protocol for isolated testing."""

    def __init__(self) -> None:
        self.nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self.upstream: Dict[str, Set[str]] = {}
        self.downstream: Dict[str, Set[str]] = {}
        self.validate_error: Optional[Exception] = None
        self.validate_called: int = 0
        self.critical_path_result: Tuple[List[str], float] = ([], 0.0)

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        self.nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self.upstream.setdefault(node_id, set()).update(deps)
        self.downstream.setdefault(node_id, set())
        for dep in deps:
            self.downstream.setdefault(dep, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self.nodes:
            raise dag_engine_lite.NodeNotFoundError("Missing upstream", upstream_id)
        if downstream_id not in self.nodes:
            raise dag_engine_lite.NodeNotFoundError("Missing downstream", downstream_id)
        self.upstream[downstream_id].add(upstream_id)
        self.downstream[upstream_id].add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        if node_id not in self.nodes:
            raise dag_engine_lite.NodeNotFoundError("Missing node", node_id)
        del self.nodes[node_id]
        for up in self.upstream.pop(node_id, set()):
            if up in self.downstream:
                self.downstream[up].discard(node_id)
        for down in self.downstream.pop(node_id, set()):
            if down in self.upstream:
                self.upstream[down].discard(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        if node_id not in self.nodes:
            raise dag_engine_lite.NodeNotFoundError("Missing node", node_id)
        return self.nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self.nodes:
            raise dag_engine_lite.NodeNotFoundError("Missing node", node_id)
        return set(self.upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self.nodes:
            raise dag_engine_lite.NodeNotFoundError("Missing node", node_id)
        return set(self.downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        return set(self.nodes.keys())

    def validate(self) -> None:
        self.validate_called += 1
        if self.validate_error is not None:
            raise self.validate_error

    def topological_sort(self) -> List[str]:
        return list(self.nodes.keys())

    def find_roots(self) -> Set[str]:
        return {nid for nid, ups in self.upstream.items() if not ups}

    def find_leaves(self) -> Set[str]:
        return {nid for nid, downs in self.downstream.items() if not downs}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        return self.critical_path_result


class MockWaveScheduler(dag_engine_lite.WaveScheduler):
    """Lightweight mock implementation of WaveScheduler protocol for isolated runner tests."""

    def __init__(self, waves: List[List[str]], initial_states: Mapping[str, dag_engine_lite.NodeState]) -> None:
        self.waves: List[List[str]] = list(waves)
        self.states: Dict[str, dag_engine_lite.NodeState] = dict(initial_states)
        self.running_marked: List[str] = []
        self.succeeded_marked: List[str] = []
        self.failed_marked: List[Tuple[str, dag_engine_lite.FailurePolicy]] = []

    def next_wave(self) -> List[str]:
        if self.waves:
            return self.waves.pop(0)
        return []

    def mark_running(self, node_id: str) -> None:
        self.running_marked.append(node_id)
        self.states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self.succeeded_marked.append(node_id)
        self.states[node_id] = dag_engine_lite.NodeState.SUCCEEDED

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self.failed_marked.append((node_id, failure_policy))
        self.states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for k, v in list(self.states.items()):
                if v in (dag_engine_lite.NodeState.PENDING, dag_engine_lite.NodeState.READY):
                    self.states[k] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            for k, v in list(self.states.items()):
                if v == dag_engine_lite.NodeState.PENDING:
                    self.states[k] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        terminal = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        return all(s in terminal for s in self.states.values())

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        return self.states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        return dict(self.states)


class DAGTest(unittest.TestCase):
    """Unit tests for the concrete DAG singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_has_get_node_and_all_nodes(self) -> None:
        """Verifies add_node registers NodeDefinition and has_node, get_node, all_nodes reflect it."""
        action = _make_action(42)
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("n1"))
            self.assertEqual(dag.all_nodes(), set())

            dag.add_node("n1", action, dependencies=["n0"], priority=5, retries=2)
            self.assertTrue(dag.has_node("n1"))
            self.assertEqual(dag.all_nodes(), {"n1"})

            defn = dag.get_node("n1")
            self.assertEqual(defn.node_id, "n1")
            self.assertIs(defn.action, action)
            self.assertEqual(defn.dependencies, frozenset({"n0"}))
            self.assertEqual(defn.priority, 5)
            self.assertEqual(defn.retries, 2)
            self.assertEqual(dag.get_dependencies("n1"), {"n0"})

    def test_get_node_and_neighbors_not_found(self) -> None:
        """Verifies get_node, get_dependencies, and get_dependents raise NodeNotFoundError when absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx1:
                dag.get_node("missing")
            self.assertEqual(ctx1.exception.node_id, "missing")

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx2:
                dag.get_dependencies("missing")
            self.assertEqual(ctx2.exception.node_id, "missing")

            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx3:
                dag.get_dependents("missing")
            self.assertEqual(ctx3.exception.node_id, "missing")

    def test_add_edge_and_dependents(self) -> None:
        """Verifies add_edge establishes directed edge and updates dependencies and dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("u", _make_action())
            dag.add_node("d", _make_action())
            dag.add_edge("u", "d")

            self.assertEqual(dag.get_dependencies("d"), {"u"})
            self.assertEqual(dag.get_dependents("u"), {"d"})
            self.assertEqual(dag.get_dependencies("u"), set())
            self.assertEqual(dag.get_dependents("d"), set())

    def test_add_edge_missing_nodes_raises(self) -> None:
        """Verifies add_edge raises NodeNotFoundError when upstream_id or downstream_id is absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())

            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.add_edge("missing_up", "a")

            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.add_edge("a", "missing_down")

    def test_remove_node_and_incident_edges(self) -> None:
        """Verifies remove_node deletes node and cleans up incident upstream and downstream edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), dependencies=["a"])
            dag.add_node("c", _make_action(), dependencies=["b"])

            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())

            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.remove_node("b")

    def test_find_roots_and_leaves(self) -> None:
        """Verifies find_roots returns in-degree zero nodes and find_leaves returns out-degree zero nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.find_roots(), set())
            self.assertEqual(dag.find_leaves(), set())

            dag.add_node("r1", _make_action())
            dag.add_node("r2", _make_action())
            dag.add_node("mid", _make_action(), dependencies=["r1", "r2"])
            dag.add_node("l1", _make_action(), dependencies=["mid"])
            dag.add_node("l2", _make_action(), dependencies=["mid"])

            self.assertEqual(dag.find_roots(), {"r1", "r2"})
            self.assertEqual(dag.find_leaves(), {"l1", "l2"})

    def test_validate_success_and_errors(self) -> None:
        """Verifies validate succeeds on valid DAG, raises NodeNotFoundError on missing dep, and CycleError on cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), dependencies=["a"])
            dag.validate()

            # Missing dependency node
            dag.add_node("c", _make_action(), dependencies=["nonexistent"])
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx_nf:
                dag.validate()
            self.assertEqual(ctx_nf.exception.node_id, "nonexistent")

            # Remove invalid node and introduce a cycle a -> b -> a
            dag.remove_node("c")
            dag.add_edge("b", "a")
            with self.assertRaises(dag_engine_lite.CycleError) as ctx_cyc:
                dag.validate()
            self.assertTrue(len(ctx_cyc.exception.cycle) >= 2)
            self.assertIn("a", ctx_cyc.exception.cycle)
            self.assertIn("b", ctx_cyc.exception.cycle)

    def test_topological_sort_ordering_and_cycle_error(self) -> None:
        """Verifies topological_sort respects dependencies, priority descending, node_id ascending, and raises CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_b", _make_action(), priority=10)
            dag.add_node("root_a", _make_action(), priority=10)
            dag.add_node("root_high", _make_action(), priority=20)
            dag.add_node("child", _make_action(), dependencies=["root_a", "root_b"], priority=100)

            order = dag.topological_sort()
            self.assertEqual(order, ["root_high", "root_a", "root_b", "child"])

            # Introduce cycle child -> root_a
            dag.add_edge("child", "root_a")
            with self.assertRaises(dag_engine_lite.CycleError):
                dag.topological_sort()

    def test_compute_critical_path_default_and_custom_weights(self) -> None:
        """Verifies compute_critical_path returns longest weighted path and total weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.compute_critical_path(), ([], 0.0))

            dag.add_node("a", _make_action())
            dag.add_node("b", _make_action(), dependencies=["a"])
            dag.add_node("c", _make_action(), dependencies=["b"])
            dag.add_node("short", _make_action(), dependencies=["a"])

            # Default weight 1.0 per node -> path a -> b -> c has weight 3.0
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["a", "b", "c"])
            self.assertAlmostEqual(weight, 3.0)

            # Custom weights making a -> short heavier (1.0 + 10.0 = 11.0 vs 1.0 + 2.0 + 3.0 = 6.0)
            custom_path, custom_weight = dag.compute_critical_path(
                estimated_durations={"a": 1.0, "b": 2.0, "c": 3.0, "short": 10.0}
            )
            self.assertEqual(custom_path, ["a", "short"])
            self.assertAlmostEqual(custom_weight, 11.0)


class WaveSchedulerTest(unittest.TestCase):
    """Unit tests for the concrete WaveScheduler singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_empty_dag_scheduler(self) -> None:
        """Verifies WaveScheduler behavior when the DAG is empty."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(scheduler.get_all_states(), {})

    def test_wave_progression_and_priority_ordering(self) -> None:
        """Verifies WaveScheduler initializes states, orders waves by priority/id, and promotes downstream nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("r_low", _make_action(), priority=1)
            dag.add_node("r_high_b", _make_action(), priority=5)
            dag.add_node("r_high_a", _make_action(), priority=5)
            dag.add_node("dep", _make_action(), dependencies=["r_low", "r_high_a"])

            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.get_state("r_low"), dag_engine_lite.NodeState.READY)
            self.assertEqual(scheduler.get_state("dep"), dag_engine_lite.NodeState.PENDING)

            wave1 = scheduler.next_wave()
            self.assertEqual(wave1, ["r_high_a", "r_high_b", "r_low"])

            for nid in wave1:
                scheduler.mark_running(nid)
                self.assertEqual(scheduler.get_state(nid), dag_engine_lite.NodeState.RUNNING)

            # While running, no nodes are READY
            self.assertEqual(scheduler.next_wave(), [])

            scheduler.mark_succeeded("r_high_a")
            scheduler.mark_succeeded("r_high_b")
            # dep still waiting on r_low
            self.assertEqual(scheduler.get_state("dep"), dag_engine_lite.NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), [])

            scheduler.mark_succeeded("r_low")
            self.assertEqual(scheduler.get_state("dep"), dag_engine_lite.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["dep"])

            scheduler.mark_running("dep")
            scheduler.mark_succeeded("dep")
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(
                scheduler.get_all_states(),
                {
                    "r_low": dag_engine_lite.NodeState.SUCCEEDED,
                    "r_high_b": dag_engine_lite.NodeState.SUCCEEDED,
                    "r_high_a": dag_engine_lite.NodeState.SUCCEEDED,
                    "dep": dag_engine_lite.NodeState.SUCCEEDED,
                },
            )

    def test_mark_failed_fail_fast(self) -> None:
        """Verifies mark_failed with FAIL_FAST transitions remaining non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("n1", _make_action())
            dag.add_node("n2", _make_action())
            dag.add_node("n3", _make_action(), dependencies=["n2"])

            scheduler.next_wave()
            scheduler.mark_running("n1")
            scheduler.mark_failed("n1", dag_engine_lite.FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("n1"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("n2"), dag_engine_lite.NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("n3"), dag_engine_lite.NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream(self) -> None:
        """Verifies mark_failed with SKIP_DOWNSTREAM transitions transitive dependents to SKIPPED while keeping independent nodes eligible."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("bad", _make_action(), priority=10)
            dag.add_node("child", _make_action(), dependencies=["bad"])
            dag.add_node("grandchild", _make_action(), dependencies=["child"])
            dag.add_node("indep", _make_action(), priority=1)

            scheduler.next_wave()
            scheduler.mark_running("bad")
            scheduler.mark_failed("bad", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("bad"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child"), dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("grandchild"), dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("indep"), dag_engine_lite.NodeState.READY)
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), ["indep"])

    def test_get_state_before_prior_synchronization(self) -> None:
        """Verifies WaveScheduler.get_state synchronizes and returns state before any prior wave scheduling or synchronization."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            dag.add_node("root", _make_action())
            dag.add_node("child", _make_action(), dependencies=["root"])

            # Call get_state directly before is_finished(), next_wave(), or get_all_states()
            self.assertEqual(scheduler.get_state("root"), dag_engine_lite.NodeState.READY)
            self.assertEqual(scheduler.get_state("child"), dag_engine_lite.NodeState.PENDING)

            # Also verify dynamic node registration after initial state query
            dag.add_node("late_root", _make_action())
            self.assertEqual(scheduler.get_state("late_root"), dag_engine_lite.NodeState.READY)

    def test_mark_failed_continue_on_error_with_mock_dag(self) -> None:
        """Verifies mark_failed with CONTINUE_ON_ERROR leaves independent nodes READY using a MockDAG collaborator."""
        mock_dag = MockDAG()
        mock_dag.add_node("fail_node", _make_action(), priority=5)
        mock_dag.add_node("dep_node", _make_action(), dependencies=["fail_node"])
        mock_dag.add_node("ok_node", _make_action(), priority=1)
        self.registry.register_instance(mock_dag, keys=[dag_engine_lite.DAG], tier=system)

        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["fail_node", "ok_node"])

            scheduler.mark_running("fail_node")
            scheduler.mark_failed("fail_node", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("fail_node"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("ok_node"), dag_engine_lite.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["ok_node"])


class DAGRunnerTest(unittest.TestCase):
    """Unit tests for the concrete DAGRunner singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_happy_path_and_retries(self) -> None:
        """Verifies DAGRunner executes waves in order, retries transient failures, and produces a complete DAGRunReport."""
        execution_log: List[str] = []
        attempts = {"flaky": 0}

        def make_logged_action(nid: str, val: Any) -> Callable[[], Any]:
            def _act() -> Any:
                execution_log.append(nid)
                return val
            return _act

        def flaky_action() -> str:
            execution_log.append("flaky")
            attempts["flaky"] += 1
            if attempts["flaky"] < 3:
                raise RuntimeError("transient error")
            return "recovered"

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("start", make_logged_action("start", 10))
            dag.add_node("flaky", flaky_action, dependencies=["start"], retries=2)
            dag.add_node("end", make_logged_action("end", 20), dependencies=["flaky"])

            report = runner.run()

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"start", "flaky", "end"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("start", "flaky", "end"))

            self.assertEqual(execution_log, ["start", "flaky", "flaky", "flaky", "end"])
            self.assertEqual(report.results["start"].value, 10)
            self.assertEqual(report.results["start"].state, dag_engine_lite.NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertEqual(report.results["flaky"].retries_attempted, 2)
            self.assertIsNone(report.results["flaky"].error)
            self.assertEqual(report.results["end"].value, 20)

    def test_run_fail_fast_policy(self) -> None:
        """Verifies DAGRunner halts execution and marks remaining nodes CANCELLED under FAIL_FAST."""
        def failing_action() -> None:
            raise ValueError("boom")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("a", failing_action, priority=10, retries=1)
            dag.add_node("b", _make_action("b_val"), priority=1)
            dag.add_node("c", _make_action("c_val"), dependencies=["b"])

            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST)

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(set(report.cancelled_nodes), {"b", "c"})
            self.assertEqual(report.skipped_nodes, ())

            res_a = report.results["a"]
            self.assertEqual(res_a.state, dag_engine_lite.NodeState.FAILED)
            self.assertIsInstance(res_a.error, ValueError)
            self.assertEqual(res_a.retries_attempted, 1)

            self.assertEqual(report.results["b"].state, dag_engine_lite.NodeState.CANCELLED)
            self.assertEqual(report.results["c"].state, dag_engine_lite.NodeState.CANCELLED)

    def test_run_skip_downstream_policy(self) -> None:
        """Verifies DAGRunner skips dependent branch while completing independent branch under SKIP_DOWNSTREAM."""
        def failing_action() -> None:
            raise RuntimeError("branch failed")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("bad", failing_action, priority=10)
            dag.add_node("bad_dep", _make_action("never"), dependencies=["bad"])
            dag.add_node("good", _make_action("good_val"), priority=5)
            dag.add_node("good_dep", _make_action("good_dep_val"), dependencies=["good"])

            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(report.total_nodes, 4)
            self.assertEqual(set(report.succeeded_nodes), {"good", "good_dep"})
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.skipped_nodes, ("bad_dep",))
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["bad_dep"].state, dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(report.results["good_dep"].value, "good_dep_val")

    def test_run_continue_on_error_policy_halts_on_empty_wave_with_pending_dependent(self) -> None:
        """Verifies DAGRunner executes independent nodes and halts wave loop when next_wave is empty while is_finished is False due to blocked PENDING dependents under CONTINUE_ON_ERROR."""
        def failing_action() -> None:
            raise RuntimeError("fail")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            dag.add_node("bad", failing_action, priority=10)
            dag.add_node("blocked_dep", _make_action("never"), dependencies=["bad"])
            dag.add_node("good", _make_action("ok"), priority=5)

            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)

            # blocked_dep remains PENDING so scheduler.is_finished() is False, yet next_wave() is [] and runner.run() halts cleanly
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.get_state("blocked_dep"), dag_engine_lite.NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), [])

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(report.succeeded_nodes, ("good",))
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["good"].value, "ok")
            self.assertEqual(report.results["bad"].state, dag_engine_lite.NodeState.FAILED)

    def test_run_propagates_validation_errors_and_uses_collaborators(self) -> None:
        """Verifies DAGRunner invokes DAG.validate() and WaveScheduler collaborator methods."""
        mock_dag = MockDAG()
        mock_dag.add_node("n1", _make_action("v1"))
        mock_dag.critical_path_result = (["n1"], 1.0)
        mock_sched = MockWaveScheduler(
            waves=[["n1"]],
            initial_states={"n1": dag_engine_lite.NodeState.READY},
        )
        self.registry.register_instance(mock_dag, keys=[dag_engine_lite.DAG], tier=system)
        self.registry.register_instance(
            mock_sched, keys=[dag_engine_lite.WaveScheduler], tier=system
        )

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(mock_dag.validate_called, 1)
            self.assertEqual(mock_sched.running_marked, ["n1"])
            self.assertEqual(mock_sched.succeeded_marked, ["n1"])
            self.assertEqual(report.succeeded_nodes, ("n1",))
            self.assertEqual(report.critical_path, ("n1",))

            # Verify validation error propagation
            mock_dag.validate_error = dag_engine_lite.CycleError("cycle!", ("n1", "n1"))
            with self.assertRaises(dag_engine_lite.CycleError):
                runner.run()


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T20:13:43Z
# LAST_CHANGED: 2026-10-23T20:12:01Z
# CHANGE: Add unit tests for WaveScheduler.get_state prior to state synchronization and DAGRunner.run halting when next_wave is empty while is_finished is False
# COVERAGE_AUDIT: 2026-10-23T20:13:43Z
# QA_AUDIT: 2026-10-23T20:13:04Z
# --- END CLEANROOM METADATA ---
