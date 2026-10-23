"""Unit tests for dag_engine_impl per its grounding specification."""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmark_2.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAG as DAGInterface,
    DAGCancelledError,
    DAGError,
    DAGRunReport,
    DAGTimeoutError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler as WaveSchedulerInterface,
)
from benchmark_2.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class _MockDAG(DAGInterface):
    """Lightweight mock implementation of the DAG collaborator protocol."""

    def __init__(self) -> None:
        self.nodes: Dict[str, NodeDefinition[Any]] = {}
        self.upstream: Dict[str, Set[str]] = {}
        self.downstream: Dict[str, Set[str]] = {}
        self.validate_error: Optional[Exception] = None
        self.critical_path_result: Tuple[List[str], float] = ([], 0.0)
        self.validate_called: int = 0

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        timeout_seconds: Optional[float] = None,
        retries: int = 0,
    ) -> None:
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        self.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        if node_id not in self.upstream:
            self.upstream[node_id] = set()
        if node_id not in self.downstream:
            self.downstream[node_id] = set()
        for dep in deps:
            self.upstream[node_id].add(dep)
            if dep not in self.downstream:
                self.downstream[dep] = set()
            self.downstream[dep].add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self.nodes:
            raise NodeNotFoundError(message=f"Node {upstream_id} not found", node_id=upstream_id)
        if downstream_id not in self.nodes:
            raise NodeNotFoundError(message=f"Node {downstream_id} not found", node_id=downstream_id)
        self.upstream[downstream_id].add(upstream_id)
        self.downstream[upstream_id].add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        if node_id not in self.nodes:
            raise NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id)
        del self.nodes[node_id]
        self.upstream.pop(node_id, None)
        self.downstream.pop(node_id, None)
        for deps in self.upstream.values():
            deps.discard(node_id)
        for deps in self.downstream.values():
            deps.discard(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        if node_id not in self.nodes:
            raise NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id)
        return self.nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self.nodes:
            raise NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id)
        return set(self.upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self.nodes:
            raise NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id)
        return set(self.downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        return set(self.nodes.keys())

    def validate(self) -> None:
        self.validate_called += 1
        if self.validate_error is not None:
            raise self.validate_error

    def topological_sort(self) -> List[str]:
        return sorted(self.nodes.keys())

    def find_roots(self) -> Set[str]:
        return {nid for nid in self.nodes if not self.upstream.get(nid)}

    def find_leaves(self) -> Set[str]:
        return {nid for nid in self.nodes if not self.downstream.get(nid)}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        return self.critical_path_result


class _MockWaveScheduler(WaveSchedulerInterface):
    """Lightweight mock implementation of the WaveScheduler collaborator protocol."""

    def __init__(self, dag: _MockDAG) -> None:
        self.dag = dag
        self.states: Dict[str, NodeState] = {}
        self.mark_running_calls: List[str] = []
        self.mark_succeeded_calls: List[str] = []
        self.mark_failed_calls: List[Tuple[str, FailurePolicy]] = []

    def _sync(self) -> None:
        all_ids = self.dag.all_nodes()
        for nid in list(self.states.keys()):
            if nid not in all_ids:
                del self.states[nid]
        roots = self.dag.find_roots()
        for nid in all_ids:
            if nid not in self.states:
                self.states[nid] = NodeState.READY if nid in roots else NodeState.PENDING
            elif self.states[nid] == NodeState.READY and nid not in roots:
                if not all(self.states.get(dep) == NodeState.SUCCEEDED for dep in self.dag.get_dependencies(nid)):
                    self.states[nid] = NodeState.PENDING
            elif self.states[nid] == NodeState.PENDING and nid in roots:
                self.states[nid] = NodeState.READY

    def next_wave(self) -> List[str]:
        self._sync()
        ready = [
            nid
            for nid, st in self.states.items()
            if st == NodeState.READY
            and all(self.states.get(dep) == NodeState.SUCCEEDED for dep in self.dag.get_dependencies(nid))
        ]
        ready.sort(key=lambda nid: (-self.dag.get_node(nid).priority, nid))
        return ready

    def mark_running(self, node_id: str) -> None:
        self._sync()
        self.mark_running_calls.append(node_id)
        self.states[node_id] = NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._sync()
        self.mark_succeeded_calls.append(node_id)
        self.states[node_id] = NodeState.SUCCEEDED
        for dep in self.dag.get_dependents(node_id):
            if self.states.get(dep) == NodeState.PENDING:
                if all(self.states.get(u) == NodeState.SUCCEEDED for u in self.dag.get_dependencies(dep)):
                    self.states[dep] = NodeState.READY

    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> None:
        self._sync()
        self.mark_failed_calls.append((node_id, failure_policy))
        self.states[node_id] = NodeState.FAILED
        terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        if failure_policy == FailurePolicy.FAIL_FAST:
            for nid, st in list(self.states.items()):
                if st not in terminal:
                    self.states[nid] = NodeState.CANCELLED
        elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            queue = list(self.dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                if self.states.get(curr) not in terminal:
                    self.states[curr] = NodeState.SKIPPED
                queue.extend(self.dag.get_dependents(curr))

    def is_finished(self) -> bool:
        self._sync()
        terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        for nid in self.dag.all_nodes():
            st = self.states.get(nid)
            if st not in terminal:
                if st == NodeState.READY and all(
                    self.states.get(dep) == NodeState.SUCCEEDED for dep in self.dag.get_dependencies(nid)
                ):
                    return False
                if st == NodeState.RUNNING:
                    return False
                # Check if any upstream can still succeed
                if any(self.states.get(dep) not in terminal for dep in self.dag.get_dependencies(nid)):
                    return False
        return True

    def get_state(self, node_id: str) -> NodeState:
        self._sync()
        if node_id not in self.states:
            raise NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id)
        return self.states[node_id]

    def get_all_states(self) -> Mapping[str, NodeState]:
        self._sync()
        return dict(self.states)


class DAGTest(unittest.TestCase):
    """Unit tests for the concrete DAG singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_has_get_node_and_all_nodes(self) -> None:
        """Verifies add_node, has_node, get_node, and all_nodes happy-path contracts."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("a"))
            self.assertEqual(dag.all_nodes(), set())

            action_a = lambda: 42
            dag.add_node("a", action_a)
            dag.add_node("b", lambda: "hello", dependencies=["a"], priority=5, timeout_seconds=1.5, retries=2)

            self.assertTrue(dag.has_node("a"))
            self.assertTrue(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "b"})

            node_b = dag.get_node("b")
            self.assertEqual(node_b.node_id, "b")
            self.assertEqual(node_b.dependencies, frozenset({"a"}))
            self.assertEqual(node_b.priority, 5)
            self.assertEqual(node_b.timeout_seconds, 1.5)
            self.assertEqual(node_b.retries, 2)
            self.assertEqual(node_b.action(), "hello")

            self.assertEqual(dag.get_dependencies("b"), {"a"})
            self.assertEqual(dag.get_dependents("a"), {"b"})

    def test_get_node_not_found_raises(self) -> None:
        """Verifies get_node, get_dependencies, and get_dependents raise NodeNotFoundError when absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as ctx:
                dag.get_node("missing")
            self.assertEqual(ctx.exception.node_id, "missing")

            with self.assertRaises(NodeNotFoundError):
                dag.get_dependencies("missing")

            with self.assertRaises(NodeNotFoundError):
                dag.get_dependents("missing")

    def test_add_edge_and_missing_node_errors(self) -> None:
        """Verifies add_edge establishes directed edges and raises NodeNotFoundError for missing endpoints."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("u", lambda: 1)
            dag.add_node("v", lambda: 2)

            dag.add_edge("u", "v")
            self.assertEqual(dag.get_dependencies("v"), {"u"})
            self.assertEqual(dag.get_dependents("u"), {"v"})

            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("nonexistent", "v")

            with self.assertRaises(NodeNotFoundError):
                dag.add_edge("u", "nonexistent")

    def test_remove_node_and_missing_error(self) -> None:
        """Verifies remove_node deletes the node and incident edges, or raises NodeNotFoundError when absent."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: 1)
            dag.add_node("b", lambda: 2, dependencies=["a"])
            dag.add_node("c", lambda: 3, dependencies=["b"])

            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependents("a"), set())
            self.assertEqual(dag.get_dependencies("c"), set())

            with self.assertRaises(NodeNotFoundError):
                dag.remove_node("b")

    def test_find_roots_and_leaves(self) -> None:
        """Verifies find_roots and find_leaves identify zero in-degree and zero out-degree nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("r1", lambda: 1)
            dag.add_node("r2", lambda: 2)
            dag.add_node("mid", lambda: 3, dependencies=["r1", "r2"])
            dag.add_node("l1", lambda: 4, dependencies=["mid"])
            dag.add_node("l2", lambda: 5, dependencies=["mid"])

            self.assertEqual(dag.find_roots(), {"r1", "r2"})
            self.assertEqual(dag.find_leaves(), {"l1", "l2"})

    def test_validate_success_missing_dependency_and_cycle(self) -> None:
        """Verifies validate passes on valid DAG, raises NodeNotFoundError on missing dependency, and CycleError on cycle."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", lambda: 1)
            dag.add_node("b", lambda: 2, dependencies=["a"])
            dag.validate()

            dag.add_node("c", lambda: 3, dependencies=["missing_dep"])
            with self.assertRaises(NodeNotFoundError):
                dag.validate()

            dag.remove_node("c")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as ctx:
                dag.validate()
            self.assertTrue(len(ctx.exception.cycle) >= 2)
            self.assertIn("a", ctx.exception.cycle)
            self.assertIn("b", ctx.exception.cycle)

    def test_topological_sort_ordering_and_cycle_error(self) -> None:
        """Verifies topological_sort orders by dependencies, breaks ties by priority desc then id asc, and raises CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("b_root", lambda: 1, priority=1)
            dag.add_node("a_root", lambda: 2, priority=1)
            dag.add_node("high_root", lambda: 3, priority=10)
            dag.add_node("child", lambda: 4, dependencies=["b_root", "a_root", "high_root"])

            order = dag.topological_sort()
            self.assertEqual(order, ["high_root", "a_root", "b_root", "child"])

            dag.add_edge("child", "high_root")
            with self.assertRaises(CycleError):
                dag.topological_sort()

    def test_compute_critical_path_empty_graph(self) -> None:
        """Verifies compute_critical_path on an empty graph returns empty path and 0.0 weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertAlmostEqual(weight, 0.0)

    def test_compute_critical_path_default_and_weighted(self) -> None:
        """Verifies compute_critical_path calculates longest path with default and custom duration weights."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", lambda: 1)
            dag.add_node("short_branch", lambda: 2, dependencies=["start"])
            dag.add_node("long_step1", lambda: 3, dependencies=["start"])
            dag.add_node("long_step2", lambda: 4, dependencies=["long_step1"])
            dag.add_node("end", lambda: 5, dependencies=["short_branch", "long_step2"])

            path_default, weight_default = dag.compute_critical_path()
            self.assertEqual(path_default, ["start", "long_step1", "long_step2", "end"])
            self.assertAlmostEqual(weight_default, 4.0)

            durations = {
                "start": 1.0,
                "short_branch": 10.0,
                "long_step1": 2.0,
                "long_step2": 2.0,
                "end": 1.0,
            }
            path_weighted, weight_weighted = dag.compute_critical_path(estimated_durations=durations)
            self.assertEqual(path_weighted, ["start", "short_branch", "end"])
            self.assertAlmostEqual(weight_weighted, 12.0)


class WaveSchedulerTest(unittest.TestCase):
    """Unit tests for the concrete WaveScheduler singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_dag = _MockDAG()
        self.registry.register_instance(self.mock_dag, keys=[DAGInterface, DAG], tier=system)

    def test_empty_dag_is_finished(self) -> None:
        """Verifies WaveScheduler reports is_finished True and empty next_wave when DAG has no nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.next_wave(), [])
            self.assertEqual(scheduler.get_all_states(), {})

    def test_get_state_unregistered_node_raises(self) -> None:
        """Verifies get_state raises KeyError or NodeNotFoundError for an unregistered node identifier."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises((KeyError, NodeNotFoundError)):
                scheduler.get_state("unregistered_node")

    def test_dynamic_state_synchronization_on_add_node_and_add_edge(self) -> None:
        """Verifies WaveScheduler state synchronization when nodes or edges are added dynamically."""
        self.mock_dag.add_node("n1", lambda: 1)
        self.mock_dag.add_node("n2", lambda: 2)

        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), ["n1", "n2"])
            self.assertEqual(scheduler.get_state("n1"), NodeState.READY)
            self.assertEqual(scheduler.get_state("n2"), NodeState.READY)

            # Add an edge between existing nodes after initial synchronization
            self.mock_dag.add_edge("n1", "n2")
            self.assertEqual(scheduler.next_wave(), ["n1"])

            # Add a new root node and a new dependent node dynamically
            self.mock_dag.add_node("n3", lambda: 3)
            self.mock_dag.add_node("n4", lambda: 4, dependencies=["n3"])
            self.assertFalse(scheduler.is_finished())
            self.assertEqual(scheduler.get_state("n3"), NodeState.READY)
            self.assertEqual(scheduler.get_state("n4"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["n1", "n3"])

            # Complete all registered nodes and verify is_finished
            scheduler.mark_running("n1")
            scheduler.mark_succeeded("n1")
            self.assertEqual(scheduler.get_state("n2"), NodeState.READY)
            scheduler.mark_running("n2")
            scheduler.mark_succeeded("n2")
            scheduler.mark_running("n3")
            scheduler.mark_succeeded("n3")
            self.assertEqual(scheduler.get_state("n4"), NodeState.READY)
            scheduler.mark_running("n4")
            scheduler.mark_succeeded("n4")
            self.assertTrue(scheduler.is_finished())

    def test_wave_progression_and_priority_ordering(self) -> None:
        """Verifies next_wave, mark_running, mark_succeeded, get_state, and get_all_states across waves."""
        self.mock_dag.add_node("r_low", lambda: 1, priority=1)
        self.mock_dag.add_node("r_high_b", lambda: 2, priority=5)
        self.mock_dag.add_node("r_high_a", lambda: 3, priority=5)
        self.mock_dag.add_node("dep", lambda: 4, dependencies=["r_low", "r_high_a"])

        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())

            wave1 = scheduler.next_wave()
            self.assertEqual(wave1, ["r_high_a", "r_high_b", "r_low"])
            self.assertEqual(scheduler.get_state("dep"), NodeState.PENDING)

            for nid in wave1:
                scheduler.mark_running(nid)
                self.assertEqual(scheduler.get_state(nid), NodeState.RUNNING)

            self.assertEqual(scheduler.next_wave(), [])

            scheduler.mark_succeeded("r_high_a")
            self.assertEqual(scheduler.get_state("r_high_a"), NodeState.SUCCEEDED)
            # dep still waiting on r_low
            self.assertEqual(scheduler.get_state("dep"), NodeState.PENDING)

            scheduler.mark_succeeded("r_low")
            scheduler.mark_succeeded("r_high_b")
            self.assertEqual(scheduler.get_state("dep"), NodeState.READY)

            wave2 = scheduler.next_wave()
            self.assertEqual(wave2, ["dep"])

            scheduler.mark_running("dep")
            scheduler.mark_succeeded("dep")
            self.assertTrue(scheduler.is_finished())
            all_states = scheduler.get_all_states()
            self.assertEqual(
                all_states,
                {
                    "r_low": NodeState.SUCCEEDED,
                    "r_high_b": NodeState.SUCCEEDED,
                    "r_high_a": NodeState.SUCCEEDED,
                    "dep": NodeState.SUCCEEDED,
                },
            )

    def test_mark_failed_fail_fast_policy(self) -> None:
        """Verifies mark_failed with FAIL_FAST transitions remaining non-terminal nodes to CANCELLED."""
        self.mock_dag.add_node("a", lambda: 1)
        self.mock_dag.add_node("b", lambda: 2)
        self.mock_dag.add_node("c", lambda: 3, dependencies=["a"])

        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["a", "b"])

            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=FailurePolicy.FAIL_FAST)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("c"), NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_skip_downstream_policy(self) -> None:
        """Verifies mark_failed with SKIP_DOWNSTREAM marks transitive dependents SKIPPED while leaving independent nodes eligible."""
        self.mock_dag.add_node("a", lambda: 1)
        self.mock_dag.add_node("b", lambda: 2, dependencies=["a"])
        self.mock_dag.add_node("c", lambda: 3, dependencies=["b"])
        self.mock_dag.add_node("indep", lambda: 4)

        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.next_wave()
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("indep"), NodeState.READY)
            self.assertFalse(scheduler.is_finished())

            self.assertEqual(scheduler.next_wave(), ["indep"])
            scheduler.mark_running("indep")
            scheduler.mark_succeeded("indep")
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_continue_on_error_policy(self) -> None:
        """Verifies mark_failed with CONTINUE_ON_ERROR leaves independent ready nodes eligible."""
        self.mock_dag.add_node("a", lambda: 1)
        self.mock_dag.add_node("indep", lambda: 2)

        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.next_wave()
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)

            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("indep"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["indep"])


class DAGRunnerTest(unittest.TestCase):
    """Unit tests for the concrete DAGRunner singleton implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_dag = _MockDAG()
        self.mock_scheduler = _MockWaveScheduler(self.mock_dag)
        self.registry.register_instance(self.mock_dag, keys=[DAGInterface, DAG], tier=system)
        self.registry.register_instance(
            self.mock_scheduler, keys=[WaveSchedulerInterface, WaveScheduler], tier=system
        )

    def test_run_happy_path_and_retries(self) -> None:
        """Verifies DAGRunner executes waves, retries transient failures up to retry count, and builds DAGRunReport."""
        attempts = {"flaky": 0}

        def flaky_action() -> str:
            attempts["flaky"] += 1
            if attempts["flaky"] < 2:
                raise RuntimeError("transient error")
            return "recovered"

        self.mock_dag.add_node("root", lambda: 10)
        self.mock_dag.add_node("flaky", flaky_action, dependencies=["root"], retries=2)
        self.mock_dag.critical_path_result = (["root", "flaky"], 2.0)

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(max_concurrency=2)

            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"root", "flaky"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ("root", "flaky"))
            self.assertEqual(report.results["root"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["root"].value, 10)
            self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "recovered")
            self.assertEqual(report.results["flaky"].retries_attempted, 1)

    def test_run_failure_with_skip_downstream_policy(self) -> None:
        """Verifies DAGRunner records failed node after exhausting retries and applies SKIP_DOWNSTREAM policy."""
        def failing_action() -> None:
            raise ValueError("permanent failure")

        self.mock_dag.add_node("bad", failing_action, retries=1)
        self.mock_dag.add_node("downstream", lambda: 1, dependencies=["bad"])
        self.mock_dag.add_node("good", lambda: "ok")
        self.mock_dag.critical_path_result = (["bad", "downstream"], 2.0)

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM, max_concurrency=2)

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(report.succeeded_nodes, ("good",))
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertEqual(report.skipped_nodes, ("downstream",))
            self.assertEqual(report.results["bad"].state, NodeState.FAILED)
            self.assertIsInstance(report.results["bad"].error, ValueError)
            self.assertEqual(report.results["bad"].retries_attempted, 1)

    def test_run_failure_with_fail_fast_policy(self) -> None:
        """Verifies DAGRunner under FAIL_FAST marks failed node FAILED and remaining pending downstream nodes CANCELLED."""
        def failing_action() -> None:
            raise RuntimeError("boom")

        self.mock_dag.add_node("bad", failing_action, priority=10)
        self.mock_dag.add_node("downstream", lambda: 1, dependencies=["bad"])
        self.mock_dag.critical_path_result = (["bad", "downstream"], 2.0)

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST, max_concurrency=1)

            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertIn("downstream", report.cancelled_nodes)
            self.assertEqual(report.results["bad"].state, NodeState.FAILED)

    def test_run_failure_with_continue_on_error_blocked_downstream(self) -> None:
        """Verifies DAGRunner under CONTINUE_ON_ERROR executes independent nodes and terminates cleanly when downstream nodes remain blocked by failed upstream dependencies."""
        def failing_action() -> None:
            raise RuntimeError("upstream failed")

        self.mock_dag.add_node("bad", failing_action)
        self.mock_dag.add_node("blocked_child", lambda: 1, dependencies=["bad"])
        self.mock_dag.add_node("indep", lambda: "success")
        self.mock_dag.critical_path_result = (["bad", "blocked_child"], 2.0)

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR, max_concurrency=2)

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(report.succeeded_nodes, ("indep",))
            self.assertEqual(report.failed_nodes, ("bad",))
            self.assertNotIn("blocked_child", report.succeeded_nodes)
            self.assertEqual(report.results["bad"].state, NodeState.FAILED)
            self.assertEqual(report.results["indep"].state, NodeState.SUCCEEDED)

    def test_run_node_action_exceeds_per_node_timeout(self) -> None:
        """Verifies DAGRunner fails a node when its action exceeds NodeDefinition.timeout_seconds."""
        def slow_node_action() -> int:
            time.sleep(0.05)
            return 42

        self.mock_dag.add_node("slow_node", slow_node_action, timeout_seconds=0.01, retries=0)
        self.mock_dag.critical_path_result = (["slow_node"], 1.0)

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            report = runner.run(failure_policy=FailurePolicy.FAIL_FAST, max_concurrency=1)

            self.assertEqual(report.failed_nodes, ("slow_node",))
            self.assertEqual(report.results["slow_node"].state, NodeState.FAILED)
            self.assertIsNotNone(report.results["slow_node"].error)

    def test_run_propagates_validation_errors(self) -> None:
        """Verifies DAGRunner validates the DAG before running and propagates CycleError."""
        self.mock_dag.validate_error = CycleError(message="cycle", cycle=("a", "b", "a"))

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(CycleError):
                runner.run()

    def test_run_timeout_raises_dag_timeout_error(self) -> None:
        """Verifies DAGRunner raises DAGTimeoutError when overall execution exceeds timeout_seconds."""
        def slow_step() -> int:
            time.sleep(0.03)
            return 1

        self.mock_dag.add_node("step1", slow_step)
        self.mock_dag.add_node("step2", slow_step, dependencies=["step1"])

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(DAGTimeoutError):
                runner.run(timeout_seconds=0.01, max_concurrency=1)

    def test_cancel_prior_to_execution_raises_cancelled_error(self) -> None:
        """Verifies invoking cancel() prior to run() marks non-terminal nodes CANCELLED and raises DAGCancelledError."""
        self.mock_dag.add_node("n1", lambda: 1)
        self.mock_dag.add_node("n2", lambda: 2, dependencies=["n1"])

        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            runner.cancel()
            with self.assertRaises(DAGCancelledError):
                runner.run(max_concurrency=2)

    def test_cancel_across_concurrent_execution_raises_cancelled_error(self) -> None:
        """Verifies invoking cancel() across concurrent wave execution marks non-terminal nodes CANCELLED and raises DAGCancelledError."""
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(DAGRunner)
            started_event = threading.Event()

            def concurrent_cancelling_action() -> int:
                started_event.set()
                runner.cancel()
                return 1

            def peer_action() -> int:
                started_event.wait(timeout=0.5)
                return 2

            self.mock_dag.add_node("c1", concurrent_cancelling_action)
            self.mock_dag.add_node("c2", peer_action)
            self.mock_dag.add_node("c3", lambda: 3, dependencies=["c1", "c2"])

            with self.assertRaises(DAGCancelledError):
                runner.run(max_concurrency=2)



if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T04:59:37Z
# LAST_CHANGED: 2026-10-23T04:51:44Z
# CHANGE: Remove uncontracted assertion that WaveScheduler.get_all_states deletes removed nodes from _states after initialization
# COVERAGE_AUDIT: 2026-10-23T04:59:37Z
# QA_AUDIT: 2026-10-23T04:58:32Z
# --- END CLEANROOM METADATA ---
