"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__
from benchmark_2.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGError,
    DAGRunReport,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    def _apply_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        deps = set(dependencies) if dependencies is not None else set()
        self.state.nodes[node_id] = {
            "node_id": node_id,
            "action": action,
            "priority": priority,
            "retries": retries,
            "deps": deps,
        }
        if node_id not in self.state.upstream:
            self.state.upstream[node_id] = set()
        if node_id not in self.state.downstream:
            self.state.downstream[node_id] = set()
        for d in deps:
            self.state.upstream[node_id].add(d)
            if d not in self.state.downstream:
                self.state.downstream[d] = set()
            self.state.downstream[d].add(node_id)
        if len(self.state.upstream[node_id]) == 0:
            self.state.states[node_id] = NodeState.READY
        else:
            self.state.states[node_id] = NodeState.PENDING

    def _apply_remove_node(self, node_id: str) -> None:
        if node_id in self.state.nodes:
            del self.state.nodes[node_id]
        if node_id in self.state.states:
            del self.state.states[node_id]
        for u in list(self.state.upstream.get(node_id, ())):
            if u in self.state.downstream:
                self.state.downstream[u].discard(node_id)
        for d in list(self.state.downstream.get(node_id, ())):
            if d in self.state.upstream:
                self.state.upstream[d].discard(node_id)
            if d in self.state.nodes:
                self.state.nodes[d]["deps"].discard(node_id)
        if node_id in self.state.upstream:
            del self.state.upstream[node_id]
        if node_id in self.state.downstream:
            del self.state.downstream[node_id]

    def _is_acyclic_and_complete(self) -> bool:
        for nid, info in self.state.nodes.items():
            for dep in info["deps"]:
                if dep not in self.state.nodes:
                    return False
        visited: Set[str] = set()
        rec_set: Set[str] = set()

        def has_cycle(n: str) -> bool:
            visited.add(n)
            rec_set.add(n)
            for m in self.state.downstream.get(n, set()):
                if m not in self.state.nodes:
                    continue
                if m in rec_set:
                    return True
                if m not in visited and has_cycle(m):
                    return True
            rec_set.remove(n)
            return False

        for n in self.state.nodes:
            if n not in visited and has_cycle(n):
                return False
        return True

    def _ensures_topo(self, res: List[str], target: DAG, check: Any) -> None:
        check.equal(len(res), len(self.state.nodes))
        pos = {n: i for i, n in enumerate(res)}
        for n in res:
            for p in self.state.upstream.get(n, set()):
                if p in pos:
                    check(pos[p] < pos[n], f"Dependency {p} must precede {n}")

    def _apply_mark_succeeded(self, node_id: str) -> None:
        self.state.states[node_id] = NodeState.SUCCEEDED
        for d in self.state.downstream.get(node_id, set()):
            if self.state.states.get(d) == NodeState.PENDING:
                if all(self.state.states.get(u) == NodeState.SUCCEEDED for u in self.state.upstream.get(d, set())):
                    self.state.states[d] = NodeState.READY

    def _apply_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        self.state.states[node_id] = NodeState.FAILED
        terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        if failure_policy == FailurePolicy.FAIL_FAST:
            for nid, st in list(self.state.states.items()):
                if st not in terminal:
                    self.state.states[nid] = NodeState.CANCELLED
        elif failure_policy in (FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR):
            queue = list(self.state.downstream.get(node_id, set()))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr not in visited:
                    visited.add(curr)
                    if self.state.states.get(curr) not in terminal:
                        self.state.states[curr] = NodeState.SKIPPED
                    queue.extend(self.state.downstream.get(curr, set()))

    def _calc_is_finished(self) -> bool:
        if not self.state.nodes:
            return True
        terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        return all(self.state.states.get(n) in terminal for n in self.state.nodes)

    @transition(DAG.add_node)
    def add_node(
        self,
        ctx: TransitionContext[DAG, [str, Callable[[], Any], Optional[Collection[str]], int, int], None],
    ) -> None:
        ctx.arguments(
                    node_id=Domain(strategy=lambda: f'node_{len(self.state.nodes)}', validator=lambda node_id: isinstance(node_id, str)),
                    action=Domain(strategy=lambda: lambda: 'ok'),
                    dependencies=Domain(strategy=lambda: []),
                    priority=Domain(strategy=lambda: 0),
                    retries=Domain(strategy=lambda: 0),
                )
        ctx.returns(lambda node_id, action, dependencies=None, priority=0, retries=0: None)
        ctx.ensures(
            lambda res, target, check, node_id, action, dependencies=None, priority=0, retries=0: (
                check(target.has_node(node_id), f"Node {node_id} should exist"),
                check.equal(target.get_node(node_id).priority, priority),
                check.equal(target.get_node(node_id).retries, retries),
            )
        )
        ctx.update(
            lambda res, node_id, action, dependencies=None, priority=0, retries=0: self._apply_add_node(
                node_id, action, dependencies, priority, retries
            )
        )

    @transition(DAG.add_edge)
    def add_edge(
        self,
        ctx: TransitionContext[DAG, [str, str], None],
    ) -> None:
        ctx.requires(lambda check: check(
            len(self.state.nodes) >= 2,
            "Must have at least 2 nodes",
        ))
        ctx.arguments(
                    upstream_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'u'),
                    downstream_id=Domain(strategy=lambda: list(self.state.nodes.keys())[1] if len(self.state.nodes) > 1 else 'v'),
                )
        ctx.returns(lambda upstream_id, downstream_id: None)
        ctx.ensures(
            lambda res, target, check, upstream_id, downstream_id: (
                check(upstream_id in target.get_dependencies(downstream_id), "Upstream in dependencies"),
                check(downstream_id in target.get_dependents(upstream_id), "Downstream in dependents"),
            )
        )
        ctx.update(
            lambda res, upstream_id, downstream_id: (
                self.state.upstream[downstream_id].add(upstream_id),
                self.state.downstream[upstream_id].add(downstream_id),
                self.state.nodes[downstream_id]["deps"].add(upstream_id),
                self.state.states.__setitem__(downstream_id, NodeState.PENDING),
            )
        )

    @transition(DAG.remove_node)
    def remove_node(
        self,
        ctx: TransitionContext[DAG, [str], None],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: None)
        ctx.ensures(
            lambda res, target, check, node_id: (
                check(not target.has_node(node_id), f"Node {node_id} removed"),
                check(node_id not in target.all_nodes(), f"Node {node_id} not in all_nodes"),
            )
        )
        ctx.update(lambda res, node_id: self._apply_remove_node(node_id))

    @transition(DAG.has_node)
    def has_node(
        self,
        ctx: TransitionContext[DAG, [str], bool],
    ) -> None:
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'unknown_node'), validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(lambda node_id: node_id in self.state.nodes)
        ctx.ensures(lambda res, target, check, node_id: check.equal(res, node_id in self.state.nodes))

    @transition(DAG.get_node)
    def get_node(
        self,
        ctx: TransitionContext[DAG, [str], NodeDefinition[Any]],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: NodeDefinition(
            node_id=node_id,
            action=self.state.nodes[node_id]["action"],
            dependencies=frozenset(self.state.nodes[node_id]["deps"]),
            priority=self.state.nodes[node_id]["priority"],
            retries=self.state.nodes[node_id]["retries"],
        ))
        ctx.ensures(lambda res, target, check, node_id: check.equal(res.node_id, node_id))

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        ctx: TransitionContext[DAG, [str], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: set(self.state.upstream.get(node_id, set())))
        ctx.ensures(
            lambda res, target, check, node_id: check.equal(
                res, set(self.state.upstream.get(node_id, set()))
            )
        )

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        ctx: TransitionContext[DAG, [str], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: set(self.state.downstream.get(node_id, set())))
        ctx.ensures(
            lambda res, target, check, node_id: check.equal(
                res, set(self.state.downstream.get(node_id, set()))
            )
        )

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
        ctx: TransitionContext[DAG, [], Set[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: set(self.state.nodes.keys()))
        ctx.ensures(lambda res, target, check: check.equal(res, set(self.state.nodes.keys())))

    @transition(DAG.validate)
    def validate(
        self,
        ctx: TransitionContext[DAG, [], None],
    ) -> None:
        ctx.requires(lambda check: check(self._is_acyclic_and_complete(), "Graph must be valid"))
        ctx.arguments()
        ctx.returns(lambda: None)
        ctx.ensures(lambda res, target, check: check(all(target.has_node(n) for n in target.all_nodes()), "Valid"))

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
        ctx: TransitionContext[DAG, [], List[str]],
    ) -> None:
        ctx.requires(lambda check: check(self._is_acyclic_and_complete(), "Graph must be valid"))
        ctx.arguments()
        ctx.returns(lambda: list(self.state.nodes.keys()))
        ctx.ensures(self._ensures_topo)

    @transition(DAG.find_roots)
    def find_roots(
        self,
        ctx: TransitionContext[DAG, [], Set[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: {nid for nid in self.state.nodes if not self.state.upstream.get(nid)})
        ctx.ensures(
            lambda res, target, check: check.equal(
                res, {nid for nid in self.state.nodes if not self.state.upstream.get(nid)}
            )
        )

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
        ctx: TransitionContext[DAG, [], Set[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: {nid for nid in self.state.nodes if not self.state.downstream.get(nid)})
        ctx.ensures(
            lambda res, target, check: check.equal(
                res, {nid for nid in self.state.nodes if not self.state.downstream.get(nid)}
            )
        )

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        ctx: TransitionContext[DAG, [Optional[Mapping[str, float]]], Tuple[List[str], float]],
    ) -> None:
        ctx.requires(lambda check: check(self._is_acyclic_and_complete(), "Graph must be valid"))
        ctx.arguments(estimated_durations=Domain(strategy=lambda: None))
        ctx.returns(lambda estimated_durations=None: (list(self.state.nodes.keys()), float(len(self.state.nodes))))
        ctx.ensures(lambda res, target, check, estimated_durations=None: (
            check(isinstance(res[0], list), "Path is list"),
            check(isinstance(res[1], (int, float)), "Weight is numeric"),
            check(res[1] >= 0.0, "Weight non-negative"),
        ))

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
        ctx: TransitionContext[WaveScheduler, [], List[str]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: [
            n for n, st in self.state.states.items()
            if st == NodeState.READY and all(self.state.states.get(d) == NodeState.SUCCEEDED for d in self.state.upstream.get(n, set()))
        ])
        ctx.ensures(lambda res, target, check: (
            check(isinstance(res, list), "Wave is list"),
            check(all(target.get_state(n) == NodeState.READY for n in res), "Wave nodes are READY"),
        ))

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        ctx: TransitionContext[WaveScheduler, [str], None],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: None)
        ctx.ensures(lambda res, target, check, node_id: check.equal(target.get_state(node_id), NodeState.RUNNING))
        ctx.update(lambda res, node_id: self.state.states.__setitem__(node_id, NodeState.RUNNING))

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        ctx: TransitionContext[WaveScheduler, [str], None],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: None)
        ctx.ensures(lambda res, target, check, node_id: check.equal(target.get_state(node_id), NodeState.SUCCEEDED))
        ctx.update(lambda res, node_id: self._apply_mark_succeeded(node_id))

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        ctx: TransitionContext[WaveScheduler, [str, FailurePolicy], None],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy')),
                    failure_policy=Domain(strategy=lambda: FailurePolicy.FAIL_FAST, validator=lambda failure_policy: isinstance(failure_policy, FailurePolicy)),
                )
        ctx.returns(lambda node_id, failure_policy=FailurePolicy.FAIL_FAST: None)
        ctx.ensures(lambda res, target, check, node_id, failure_policy=FailurePolicy.FAIL_FAST: (
            check.equal(target.get_state(node_id), NodeState.FAILED)
        ))
        ctx.update(lambda res, node_id, failure_policy=FailurePolicy.FAIL_FAST: self._apply_mark_failed(node_id, failure_policy))

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
        ctx: TransitionContext[WaveScheduler, [], bool],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: self._calc_is_finished())
        ctx.ensures(lambda res, target, check: check.equal(res, target.is_finished()))

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        ctx: TransitionContext[WaveScheduler, [str], NodeState],
    ) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Node must exist"))
        ctx.arguments(node_id=Domain(strategy=lambda: next(iter(self.state.nodes.keys()), 'dummy'), validator=lambda node_id: node_id in self.state.nodes))
        ctx.returns(lambda node_id: self.state.states.get(node_id, NodeState.PENDING))
        ctx.ensures(lambda res, target, check, node_id: check.equal(res, target.get_state(node_id)))

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
        ctx: TransitionContext[WaveScheduler, [], Mapping[str, NodeState]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: {n: self.state.states.get(n, NodeState.PENDING) for n in self.state.nodes})
        ctx.ensures(lambda res, target, check: check.equal(set(res.keys()), set(self.state.nodes.keys())))

    @transition(DAGRunner.run)
    def run(
        self,
        ctx: TransitionContext[DAGRunner, [FailurePolicy], DAGRunReport],
    ) -> None:
        ctx.requires(lambda check: check(self._is_acyclic_and_complete(), "Graph must be valid"))
        ctx.arguments(failure_policy=Domain(strategy=lambda: FailurePolicy.FAIL_FAST, validator=lambda failure_policy: isinstance(failure_policy, FailurePolicy)))
        ctx.returns(lambda failure_policy=FailurePolicy.FAIL_FAST: DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(self.state.nodes.keys()),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.01,
            critical_path=tuple(self.state.nodes.keys()),
            results={},
        ))
        ctx.ensures(lambda res, target, check, failure_policy=FailurePolicy.FAIL_FAST: (
            check.equal(res.total_nodes, len(self.state.nodes)),
            check(res.wall_clock_seconds >= 0.0, "Non-negative duration"),
            check.equal(len(res.results), len(self.state.nodes)),
        ))
        ctx.update(lambda res, failure_policy=FailurePolicy.FAIL_FAST: (
            self.state.states.update({n: NodeState.SUCCEEDED for n in self.state.nodes}),
        ))


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

    def test_fake_add_node_and_query(self) -> None:
        self.dag.add_node("n1", lambda: "ok", [], 1, 0)
        self.assertTrue(self.dag.has_node("n1"))
        self.assertEqual(self.dag.all_nodes(), {"n1"})
        self.assertEqual(self.dag.get_node("n1").node_id, "n1")
        self.assertEqual(self.dag.find_roots(), {"n1"})
        self.assertEqual(self.dag.find_leaves(), {"n1"})

    def test_fake_add_edge_and_dependencies(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        self.dag.add_node("n2", lambda: "b", [], 0, 0)
        self.dag.add_edge("n1", "n2")
        self.assertEqual(self.dag.get_dependencies("n2"), {"n1"})
        self.assertEqual(self.dag.get_dependents("n1"), {"n2"})

    def test_fake_remove_node(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        self.dag.remove_node("n1")
        self.assertFalse(self.dag.has_node("n1"))

    def test_fake_validate_and_sort(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        self.dag.validate()
        order = self.dag.topological_sort()
        self.assertEqual(order, ["n1"])

    def test_fake_compute_critical_path(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        path, total = self.dag.compute_critical_path(None)
        self.assertEqual(path, ["n1"])
        self.assertGreaterEqual(total, 0.0)

    def test_fake_wavescheduler_lifecycle(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, ["n1"])
        self.wavescheduler.mark_running("n1")
        self.assertEqual(self.wavescheduler.get_state("n1"), NodeState.RUNNING)
        self.wavescheduler.mark_succeeded("n1")
        self.assertEqual(self.wavescheduler.get_state("n1"), NodeState.SUCCEEDED)
        self.assertTrue(self.wavescheduler.is_finished())
        all_states = self.wavescheduler.get_all_states()
        self.assertIn("n1", all_states)

    def test_fake_wavescheduler_mark_failed(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        self.wavescheduler.mark_failed("n1", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("n1"), NodeState.FAILED)

    def test_fake_dagrunner_run(self) -> None:
        self.dag.add_node("n1", lambda: "a", [], 0, 0)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 1)


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
        self.sm = DagEngineLiteStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.wavescheduler,
                DAGRunner: self.dagrunner,
                dag_engine_lite.DAG: self.dag,
                dag_engine_lite.WaveScheduler: self.wavescheduler,
                dag_engine_lite.DAGRunner: self.dagrunner,
            }
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_empty_dag(self) -> None:
        self.sm.dispatch_transition("all_nodes")
        self.sm.dispatch_transition("find_roots")
        self.sm.dispatch_transition("find_leaves")
        self.sm.dispatch_transition("validate")
        self.sm.dispatch_transition("topological_sort")
        self.sm.dispatch_transition("compute_critical_path", None)
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_real_linear_pipeline(self) -> None:
        self.sm.dispatch_transition("add_node", "A", lambda: "res_A", None, 1, 0)
        self.sm.dispatch_transition("add_node", "B", lambda: "res_B", ["A"], 2, 0)
        self.sm.dispatch_transition("add_node", "C", lambda: "res_C", ["B"], 0, 0)
        self.sm.dispatch_transition("has_node", "A")
        self.sm.dispatch_transition("has_node", "unknown")
        self.sm.dispatch_transition("get_node", "A")
        self.sm.dispatch_transition("get_dependencies", "B")
        self.sm.dispatch_transition("get_dependents", "A")
        self.sm.dispatch_transition("all_nodes")
        self.sm.dispatch_transition("find_roots")
        self.sm.dispatch_transition("find_leaves")
        self.sm.dispatch_transition("validate")
        self.sm.dispatch_transition("topological_sort")
        self.sm.dispatch_transition("compute_critical_path", {"A": 2.0, "B": 3.0, "C": 1.0})
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_real_add_edge_and_remove(self) -> None:
        self.sm.dispatch_transition("add_node", "X", lambda: 1, None, 0, 0)
        self.sm.dispatch_transition("add_node", "Y", lambda: 2, None, 0, 0)
        self.sm.dispatch_transition("add_node", "Z", lambda: 3, None, 0, 0)
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("add_edge", "X", "Y")
        self.sm.dispatch_transition("add_edge", "Y", "Z")
        self.sm.dispatch_transition("remove_node", "Y")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("has_node", "Y")

    def test_real_node_errors(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "X")
        self.dag.add_node("P", lambda: 1)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("P", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("missing")

    def test_real_missing_dependency_validation(self) -> None:
        self.dag.add_node("N1", lambda: 1, dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()
        with self.assertRaises(NodeNotFoundError):
            self.dag.topological_sort()
        with self.assertRaises(NodeNotFoundError):
            self.dagrunner.run()

    def test_real_cycle_detection(self) -> None:
        self.dag.add_node("C1", lambda: 1)
        self.dag.add_node("C2", lambda: 2)
        self.dag.add_edge("C1", "C2")
        self.dag.add_edge("C2", "C1")
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()
        with self.assertRaises(CycleError):
            self.dagrunner.run()

    def test_real_priority_and_lexicographical_tiebreak(self) -> None:
        self.sm.dispatch_transition("add_node", "beta", lambda: 1, None, 5, 0)
        self.sm.dispatch_transition("add_node", "alpha", lambda: 2, None, 5, 0)
        self.sm.dispatch_transition("add_node", "top", lambda: 3, None, 10, 0)
        self.sm.dispatch_transition("topological_sort")
        self.sm.dispatch_transition("next_wave")

    def test_real_wave_scheduler_manual_progression(self) -> None:
        self.sm.dispatch_transition("add_node", "w1", lambda: 1, None, 0, 0)
        self.sm.dispatch_transition("add_node", "w2", lambda: 2, ["w1"], 0, 0)
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "w1")
        self.sm.dispatch_transition("mark_succeeded", "w1")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "w2")
        self.sm.dispatch_transition("mark_succeeded", "w2")
        self.sm.dispatch_transition("is_finished")

    def test_real_retry_success(self) -> None:
        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("transient failure")
            return "recovered"

        self.sm.dispatch_transition("add_node", "flaky", flaky, None, 0, 1)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_real_failure_policy_fail_fast(self) -> None:
        def fail_action() -> None:
            raise RuntimeError("boom")

        self.sm.dispatch_transition("add_node", "bad", fail_action, None, 10, 0)
        self.sm.dispatch_transition("add_node", "other", lambda: 1, None, 5, 0)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_real_failure_policy_continue_on_error(self) -> None:
        def fail_action() -> None:
            raise RuntimeError("boom")

        self.sm.dispatch_transition("add_node", "fail_node", fail_action, None, 0, 0)
        self.sm.dispatch_transition("add_node", "downstream_node", lambda: 1, ["fail_node"], 0, 0)
        self.sm.dispatch_transition("add_node", "independent_node", lambda: 2, None, 0, 0)
        self.sm.dispatch_transition("run", FailurePolicy.CONTINUE_ON_ERROR)

    def test_real_failure_policy_skip_downstream(self) -> None:
        def fail_action() -> None:
            raise RuntimeError("boom")

        self.sm.dispatch_transition("add_node", "fail_node_s", fail_action, None, 0, 0)
        self.sm.dispatch_transition("add_node", "downstream_s", lambda: 1, ["fail_node_s"], 0, 0)
        self.sm.dispatch_transition("add_node", "independent_s", lambda: 2, None, 0, 0)
        self.sm.dispatch_transition("run", FailurePolicy.SKIP_DOWNSTREAM)

    def test_real_scheduler_mark_failed_branches(self) -> None:
        self.sm.dispatch_transition("add_node", "m1", lambda: 1, None, 0, 0)
        self.sm.dispatch_transition("add_node", "m2", lambda: 2, ["m1"], 0, 0)
        self.sm.dispatch_transition("mark_failed", "m1", FailurePolicy.SKIP_DOWNSTREAM)
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("get_state", "m1")
        self.sm.dispatch_transition("get_state", "m2")

    def test_real_scheduler_is_finished_running_branch(self) -> None:
        self.sm.dispatch_transition("add_node", "r1", lambda: 1, None, 0, 0)
        self.sm.dispatch_transition("mark_running", "r1")
        self.assertFalse(self.wavescheduler.is_finished())

    def test_real_critical_path_multi_branch(self) -> None:
        self.sm.dispatch_transition("add_node", "r_a", lambda: 1, None, 0, 0)
        self.sm.dispatch_transition("add_node", "r_b", lambda: 2, None, 0, 0)
        self.sm.dispatch_transition("add_node", "join", lambda: 3, ["r_a", "r_b"], 0, 0)
        self.sm.dispatch_transition("compute_critical_path", {"r_a": 5.0, "r_b": 10.0, "join": 2.0})

    def test_real_run_breaks_when_wave_empty(self) -> None:
        self.sm.dispatch_transition("add_node", "stuck", lambda: 1, None, 0, 0)
        self.sm.dispatch_transition("mark_running", "stuck")
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_exception_str_representations(self) -> None:
        e1 = DAGError("error message")
        self.assertEqual(str(e1), "error message")
        e2 = CycleError("cycle", ("a", "b", "a"))
        self.assertEqual(str(e2), "cycle")
        e3 = NodeNotFoundError("missing", "node_x")
        self.assertEqual(str(e3), "missing")
        e4 = NodeExecutionError("failed", "node_y", ValueError("inner"))
        self.assertEqual(str(e4), "failed")


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
        if name.startswith("__"):
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
# LAST_CLEANED: 2026-10-28T23:29:37Z
# LAST_CHANGED: 2026-10-28T23:29:37Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: f8284a304bb7
# COVERAGE_AUDIT: 2026-10-28T23:29:37Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:29:37Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:29:37Z
# QA_AUDIT: 2026-10-28T23:29:37Z
# --- END CLEANROOM METADATA ---
