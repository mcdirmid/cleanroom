"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
import pretense.proto
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite import (
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
    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)


def _compute_topo_sort(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> Tuple[Optional[List[str]], Optional[Tuple[str, ...]]]:
    """Computes deterministic topological sort or detects dependency cycle."""
    if not nodes:
        return ([], None)
    in_deg: dict[str, int] = {
        nid: len([u for u in upstream.get(nid, set()) if u in nodes])
        for nid in nodes
    }
    ready: list[str] = sorted(
        [nid for nid, deg in in_deg.items() if deg == 0],
        key=lambda nid: (-nodes[nid].priority, nid),
    )
    order: list[str] = []
    for _ in range(len(nodes)):
        if not ready:
            break
        curr = ready.pop(0)
        order.append(curr)
        newly_ready: list[str] = []
        for d in sorted(downstream.get(curr, set())):
            if d in in_deg:
                in_deg[d] -= 1
                if in_deg[d] == 0:
                    newly_ready.append(d)
        ready.extend(newly_ready)
        ready.sort(key=lambda nid: (-nodes[nid].priority, nid))

    if len(order) < len(nodes):
        cycle_nodes = tuple(sorted([nid for nid, deg in in_deg.items() if deg > 0]))
        return (None, cycle_nodes)
    return (order, None)


def _compute_crit_path(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    """Computes the critical path and cumulative weight through the DAG."""
    if not nodes:
        return ([], 0.0)
    order, cycle = _compute_topo_sort(nodes, upstream, downstream)
    if order is None or not order:
        return ([], 0.0)
    dur = durations or {}
    earliest: dict[str, float] = {}
    pred: dict[str, Optional[str]] = {}
    for nid in order:
        best_p: Optional[str] = None
        max_prev = 0.0
        for p in sorted(upstream.get(nid, set())):
            if p in earliest and earliest[p] > max_prev:
                max_prev = earliest[p]
                best_p = p
        earliest[nid] = max_prev + float(dur.get(nid, 1.0))
        pred[nid] = best_p

    end_node = max(order, key=lambda nid: earliest.get(nid, 0.0))
    path: list[str] = []
    curr: Optional[str] = end_node
    for _ in range(len(order)):
        if curr is None:
            break
        path.append(curr)
        curr = pred.get(curr)
    path.reverse()
    return (path, earliest[end_node])


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
        ctx.requires(lambda check: check(True, "Can add node"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: f'node_{len(self.state.nodes)}', validator=lambda node_id: isinstance(node_id, str)),
                    action=Domain(strategy=lambda: lambda: 1),
                    dependencies=Domain(strategy=lambda: [list(self.state.nodes.keys())[-1]] if self.state.nodes else []),
                    priority=Domain(strategy=lambda: 0),
                    retries=Domain(strategy=lambda: 0),
                )
        ctx.returns(lambda node_id, action=lambda: None, dependencies=None, priority=0, retries=0: None)
        ctx.ensures(
            lambda res, target, check, node_id, action=lambda: None, dependencies=None, priority=0, retries=0: (
                check(target.has_node(node_id), f"Node {node_id} must exist in DAG"),
                check.equal(target.get_node(node_id).node_id, node_id),
                check.equal(target.get_node(node_id).priority, priority),
                check.equal(target.get_node(node_id).retries, retries),
                check(set(dependencies or ()).issubset(target.get_dependencies(node_id)), "Dependencies must be registered"),
            )
        )
        def _update(res: Any, node_id: str, action: Any = lambda: None, dependencies: Any = None, priority: int = 0, retries: int = 0) -> None:
            deps = frozenset(dependencies) if dependencies else frozenset()
            self.state.nodes[node_id] = NodeDefinition(node_id, action, deps, priority, retries)
            self.state.upstream.setdefault(node_id, set())
            self.state.downstream.setdefault(node_id, set())
            for d in deps:
                self.state.upstream[node_id].add(d)
                self.state.downstream.setdefault(d, set()).add(node_id)
            current_st = self.state.node_states.get(node_id)
            if current_st is None or current_st in (NodeState.READY, NodeState.PENDING):
                if deps and any(self.state.node_states.get(d) != NodeState.SUCCEEDED for d in deps):
                    self.state.node_states[node_id] = NodeState.PENDING
                else:
                    self.state.node_states[node_id] = NodeState.READY
        ctx.update(_update)

    @transition(DAG.add_edge)
    def add_edge(
        self,
        ctx: TransitionContext[DAG, [Any, Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can add edge"))
        ctx.arguments(
                    upstream_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda upstream_id: isinstance(upstream_id, str)),
                    downstream_id=Domain(strategy=lambda: list(self.state.nodes.keys())[-1] if self.state.nodes else 'node_0', validator=lambda downstream_id: isinstance(downstream_id, str)),
                )
        ctx.returns(
            lambda upstream_id, downstream_id: (
                Raised(NodeNotFoundError(f"Upstream node {upstream_id} not found", node_id=upstream_id))
                if upstream_id not in self.state.nodes
                else (
                    Raised(NodeNotFoundError(f"Downstream node {downstream_id} not found", node_id=downstream_id))
                    if downstream_id not in self.state.nodes
                    else None
                )
            )
        )
        ctx.ensures(
            lambda res, target, check, upstream_id, downstream_id: (
                check(upstream_id in target.get_dependencies(downstream_id), f"Upstream {upstream_id} must be in dependencies"),
                check(downstream_id in target.get_dependents(upstream_id), f"Downstream {downstream_id} must be in dependents"),
            )
        )
        def _update(res: Any, upstream_id: str, downstream_id: str) -> None:
            if upstream_id in self.state.nodes and downstream_id in self.state.nodes:
                self.state.upstream[downstream_id].add(upstream_id)
                self.state.downstream[upstream_id].add(downstream_id)
                curr_def = self.state.nodes[downstream_id]
                new_deps = curr_def.dependencies | {upstream_id}
                self.state.nodes[downstream_id] = NodeDefinition(
                    curr_def.node_id, curr_def.action, new_deps, curr_def.priority, curr_def.retries
                )
                if any(self.state.node_states.get(u) != NodeState.SUCCEEDED for u in self.state.upstream[downstream_id]):
                    if self.state.node_states.get(downstream_id) in (NodeState.READY, NodeState.PENDING):
                        self.state.node_states[downstream_id] = NodeState.PENDING
        ctx.update(_update)

    @transition(DAG.remove_node)
    def remove_node(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can remove node"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(
            lambda node_id: (
                Raised(NodeNotFoundError(f"Node {node_id} not found", node_id=node_id))
                if node_id not in self.state.nodes
                else None
            )
        )
        ctx.ensures(
            lambda res, target, check, node_id: (
                check(not target.has_node(node_id), f"Node {node_id} must not exist after removal"),
                check(node_id not in target.all_nodes(), f"Node {node_id} must not be in all_nodes"),
            )
        )
        def _update(res: Any, node_id: str) -> None:
            if node_id in self.state.nodes:
                del self.state.nodes[node_id]
                self.state.node_states.pop(node_id, None)
                ups = self.state.upstream.pop(node_id, set())
                downs = self.state.downstream.pop(node_id, set())
                for u in ups:
                    if u in self.state.downstream:
                        self.state.downstream[u].discard(node_id)
                for d in downs:
                    if d in self.state.upstream:
                        self.state.upstream[d].discard(node_id)
                        if d in self.state.nodes:
                            curr = self.state.nodes[d]
                            self.state.nodes[d] = NodeDefinition(
                                curr.node_id, curr.action, curr.dependencies - {node_id}, curr.priority, curr.retries
                            )
                            if self.state.node_states.get(d) == NodeState.PENDING:
                                if all(self.state.node_states.get(u) == NodeState.SUCCEEDED for u in self.state.upstream[d] if u in self.state.nodes):
                                    self.state.node_states[d] = NodeState.READY
        ctx.update(_update)

    @transition(DAG.has_node)
    def has_node(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can check has_node"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(lambda node_id: node_id in self.state.nodes)
        ctx.ensures(lambda res, target, check, node_id: check.equal(res, node_id in self.state.nodes))
        ctx.update(lambda res, node_id: None)

    @transition(DAG.get_node)
    def get_node(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can get_node"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(
            lambda node_id: (
                self.state.nodes[node_id]
                if node_id in self.state.nodes
                else Raised(NodeNotFoundError(f"Node {node_id} not found", node_id=node_id))
            )
        )
        ctx.ensures(
            lambda res, target, check, node_id: (
                check.equal(res.node_id, node_id),
                check.equal(res.priority, self.state.nodes[node_id].priority),
            )
        )
        ctx.update(lambda res, node_id: None)

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can get_dependencies"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(
            lambda node_id: (
                set(self.state.upstream[node_id])
                if node_id in self.state.nodes
                else Raised(NodeNotFoundError(f"Node {node_id} not found", node_id=node_id))
            )
        )
        ctx.ensures(lambda res, target, check, node_id: check.equal(res, self.state.upstream.get(node_id, set())))
        ctx.update(lambda res, node_id: None)

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can get_dependents"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(
            lambda node_id: (
                set(self.state.downstream[node_id])
                if node_id in self.state.nodes
                else Raised(NodeNotFoundError(f"Node {node_id} not found", node_id=node_id))
            )
        )
        ctx.ensures(lambda res, target, check, node_id: check.equal(res, self.state.downstream.get(node_id, set())))
        ctx.update(lambda res, node_id: None)

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can query all_nodes"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.nodes.keys()))
        ctx.ensures(lambda res, target, check: check.equal(res, set(self.state.nodes.keys())))
        ctx.update(lambda res: None)

    @transition(DAG.validate)
    def validate(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can validate"))
        ctx.arguments()
        def _returns() -> Optional[Raised]:
            for nid, ndef in self.state.nodes.items():
                for dep in ndef.dependencies:
                    if dep not in self.state.nodes:
                        return Raised(NodeNotFoundError(f"Dependency {dep} missing for node {nid}", node_id=dep))
            order, cycle = _compute_topo_sort(self.state.nodes, self.state.upstream, self.state.downstream)
            if cycle is not None:
                return Raised(CycleError(f"Dependency cycle detected: {cycle}", cycle=cycle))
            return None
        ctx.returns(_returns)
        ctx.ensures(
            lambda res, target, check: (
                check(all(all(dep in target.all_nodes() for dep in target.get_dependencies(n)) for n in target.all_nodes()), "All dependencies must exist in DAG")
            )
        )
        ctx.update(lambda res: None)

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can topological_sort"))
        ctx.arguments()
        def _returns() -> Any:
            for nid, ndef in self.state.nodes.items():
                for dep in ndef.dependencies:
                    if dep not in self.state.nodes:
                        return Raised(NodeNotFoundError(f"Dependency {dep} missing for node {nid}", node_id=dep))
            order, cycle = _compute_topo_sort(self.state.nodes, self.state.upstream, self.state.downstream)
            if cycle is not None:
                return Raised(CycleError(f"Dependency cycle detected: {cycle}", cycle=cycle))
            return order if order is not None else []
        ctx.returns(_returns)
        def _ensures(res: List[str], target: DAG, check: Any) -> None:
            all_n = target.all_nodes()
            check.equal(len(res), len(all_n))
            check.equal(set(res), all_n)
            idx_map = {nid: i for i, nid in enumerate(res)}
            for nid in res:
                for dep in target.get_dependencies(nid):
                    check(idx_map[dep] < idx_map[nid], f"Dependency {dep} must precede {nid}")
        ctx.ensures(_ensures)
        ctx.update(lambda res: None)

    @transition(DAG.find_roots)
    def find_roots(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can find_roots"))
        ctx.arguments()
        ctx.returns(lambda: {n for n, ups in self.state.upstream.items() if len(ups) == 0 and n in self.state.nodes})
        ctx.ensures(lambda res, target, check: check.equal(res, {n for n in target.all_nodes() if len(target.get_dependencies(n)) == 0}))
        ctx.update(lambda res: None)

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
        ctx: TransitionContext[DAG, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can find_leaves"))
        ctx.arguments()
        ctx.returns(lambda: {n for n, downs in self.state.downstream.items() if len(downs) == 0 and n in self.state.nodes})
        ctx.ensures(lambda res, target, check: check.equal(res, {n for n in target.all_nodes() if len(target.get_dependents(n)) == 0}))
        ctx.update(lambda res: None)

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can compute_critical_path"))
        ctx.arguments(estimated_durations=Domain(strategy=lambda: None))
        ctx.returns(lambda estimated_durations=None: _compute_crit_path(self.state.nodes, self.state.upstream, self.state.downstream, estimated_durations))
        def _ensures(res: Tuple[List[str], float], target: DAG, check: Any, estimated_durations: Any = None) -> None:
            path, total_weight = res
            dur = estimated_durations or {}
            expected_weight = sum(float(dur.get(n, 1.0)) for n in path)
            check.equal(total_weight, expected_weight)
            for i in range(len(path) - 1):
                check(path[i] in target.get_dependencies(path[i + 1]), f"Edge {path[i]} -> {path[i+1]} must exist")
        ctx.ensures(_ensures)
        ctx.update(lambda res, estimated_durations=None: None)

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
        ctx: TransitionContext[WaveScheduler, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can get next_wave"))
        ctx.arguments()
        def _returns() -> List[str]:
            ready = [
                n for n in self.state.nodes
                if self.state.node_states.get(n) == NodeState.READY and all(
                    self.state.node_states.get(u) == NodeState.SUCCEEDED
                    for u in self.state.upstream.get(n, set()) if u in self.state.nodes
                )
            ]
            return sorted(ready, key=lambda n: (-self.state.nodes[n].priority, n))
        ctx.returns(_returns)
        ctx.ensures(lambda res, target, check: check(all(target.get_state(n) == NodeState.READY for n in res), "All wave nodes must be READY"))
        ctx.update(lambda res: None)

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        ctx: TransitionContext[WaveScheduler, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(bool(self.state.nodes), "Target node must exist in graph"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0], validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(lambda node_id: None)
        ctx.ensures(lambda res, target, check, node_id: check.equal(target.get_state(node_id), NodeState.RUNNING))
        ctx.update(lambda res, node_id: self.state.node_states.__setitem__(node_id, NodeState.RUNNING))

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        ctx: TransitionContext[WaveScheduler, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(bool(self.state.nodes), "Target node must exist in graph"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0], validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(lambda node_id: None)
        ctx.ensures(lambda res, target, check, node_id: check.equal(target.get_state(node_id), NodeState.SUCCEEDED))
        def _update(res: Any, node_id: str) -> None:
            self.state.node_states[node_id] = NodeState.SUCCEEDED
            for d in self.state.downstream.get(node_id, set()):
                if d in self.state.nodes and self.state.node_states.get(d) == NodeState.PENDING:
                    if all(self.state.node_states.get(u) == NodeState.SUCCEEDED for u in self.state.upstream.get(d, set()) if u in self.state.nodes):
                        self.state.node_states[d] = NodeState.READY
        ctx.update(_update)

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        ctx: TransitionContext[WaveScheduler, [Any, Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(bool(self.state.nodes), "Target node must exist in graph"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0], validator=lambda node_id: isinstance(node_id, str)),
                    failure_policy=Domain(strategy=lambda: FailurePolicy.FAIL_FAST),
                )
        ctx.returns(lambda node_id, failure_policy=FailurePolicy.FAIL_FAST: None)
        ctx.ensures(lambda res, target, check, node_id, failure_policy=FailurePolicy.FAIL_FAST: check.equal(target.get_state(node_id), NodeState.FAILED))
        def _update(res: Any, node_id: str, failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST) -> None:
            self.state.node_states[node_id] = NodeState.FAILED
            terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
            if failure_policy == FailurePolicy.FAIL_FAST:
                for n in self.state.nodes:
                    if self.state.node_states.get(n) not in terminal:
                        self.state.node_states[n] = NodeState.CANCELLED
            elif failure_policy in (FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR):
                queue = list(self.state.downstream.get(node_id, set()))
                visited = set(queue)
                for curr in queue:
                    if self.state.node_states.get(curr) not in terminal:
                        self.state.node_states[curr] = NodeState.SKIPPED
                    for nxt in sorted(self.state.downstream.get(curr, set())):
                        if nxt not in visited:
                            visited.add(nxt)
                            queue.append(nxt)
        ctx.update(_update)

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
        ctx: TransitionContext[WaveScheduler, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can check is_finished"))
        ctx.arguments()
        def _returns() -> bool:
            if not self.state.nodes:
                return True
            if any(self.state.node_states.get(n) == NodeState.RUNNING for n in self.state.nodes):
                return False
            terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
            if all(self.state.node_states.get(n) in terminal for n in self.state.nodes):
                return True
            if any(self.state.node_states.get(n) == NodeState.READY for n in self.state.nodes):
                return False
            return True
        ctx.returns(_returns)
        def _ensures(res: bool, target: WaveScheduler, check: Any) -> None:
            states = target.get_all_states()
            if not states:
                check.equal(res, True)
            elif any(s == NodeState.RUNNING for s in states.values()):
                check.equal(res, False)
            else:
                terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
                if all(s in terminal for s in states.values()):
                    check.equal(res, True)
        ctx.ensures(_ensures)
        ctx.update(lambda res: None)

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        ctx: TransitionContext[WaveScheduler, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can get_state"))
        ctx.arguments(node_id=Domain(strategy=lambda: list(self.state.nodes.keys())[0] if self.state.nodes else 'node_0', validator=lambda node_id: isinstance(node_id, str)))
        ctx.returns(
            lambda node_id: (
                self.state.node_states[node_id]
                if node_id in self.state.nodes
                else Raised(NodeNotFoundError(f"Node {node_id} not in DAG", node_id=node_id))
            )
        )
        ctx.ensures(
            lambda res, target, check, node_id: (
                check(isinstance(res, NodeState), "Must return NodeState"),
                check.equal(res, self.state.node_states.get(node_id, res)),
            )
        )
        ctx.update(lambda res, node_id: None)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
        ctx: TransitionContext[WaveScheduler, [], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can get_all_states"))
        ctx.arguments()
        ctx.returns(lambda: {n: self.state.node_states.get(n, NodeState.PENDING) for n in self.state.nodes})
        ctx.ensures(lambda res, target, check: check.equal(set(res.keys()), set(self.state.nodes.keys())))
        ctx.update(lambda res: None)

    @transition(DAGRunner.run)
    def run(
        self,
        ctx: TransitionContext[DAGRunner, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(True, "Can run"))
        ctx.arguments(failure_policy=Domain(strategy=lambda: FailurePolicy.FAIL_FAST))
        def _returns(failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST) -> Any:
            for nid, ndef in self.state.nodes.items():
                for dep in ndef.dependencies:
                    if dep not in self.state.nodes:
                        return Raised(NodeNotFoundError(f"Dependency {dep} missing for node {nid}", node_id=dep))
            order, cycle = _compute_topo_sort(self.state.nodes, self.state.upstream, self.state.downstream)
            if cycle is not None:
                return Raised(CycleError(f"Dependency cycle detected: {cycle}", cycle=cycle))

            succeeded: list[str] = []
            failed: list[str] = []
            skipped: list[str] = []
            cancelled: list[str] = []
            results: dict[str, NodeResult[Any]] = {}
            for nid in self.state.nodes:
                current_st = self.state.node_states.get(nid, NodeState.READY)
                if current_st == NodeState.FAILED:
                    failed.append(nid)
                    results[nid] = NodeResult(nid, NodeState.FAILED, error=Exception("Action failure"))
                elif current_st == NodeState.SKIPPED:
                    skipped.append(nid)
                    results[nid] = NodeResult(nid, NodeState.SKIPPED)
                elif current_st == NodeState.CANCELLED:
                    cancelled.append(nid)
                    results[nid] = NodeResult(nid, NodeState.CANCELLED)
                else:
                    succeeded.append(nid)
                    results[nid] = NodeResult(nid, NodeState.SUCCEEDED, value=None)

            crit_path, _ = _compute_crit_path(self.state.nodes, self.state.upstream, self.state.downstream)
            return DAGRunReport(
                total_nodes=len(self.state.nodes),
                succeeded_nodes=tuple(succeeded),
                failed_nodes=tuple(failed),
                skipped_nodes=tuple(skipped),
                cancelled_nodes=tuple(cancelled),
                wall_clock_seconds=0.01,
                critical_path=tuple(crit_path),
                results=results,
            )
        ctx.returns(_returns)
        ctx.ensures(
            lambda res, target, check, failure_policy=FailurePolicy.FAIL_FAST: (
                check.equal(res.total_nodes, len(self.state.nodes)),
                check(set(res.succeeded_nodes).issubset(set(self.state.nodes.keys())), "Succeeded nodes must be subset of graph"),
                check(set(res.failed_nodes).issubset(set(self.state.nodes.keys())), "Failed nodes must be subset of graph"),
                check(res.wall_clock_seconds >= 0.0, "Wall clock time must be non-negative"),
                check.equal(len(res.results), len(self.state.nodes)),
            )
        )
        def _update_run(res: Any, failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST) -> None:
            report: Optional[DAGRunReport] = None
            if isinstance(res, DAGRunReport):
                report = res
            elif hasattr(res, "value") and isinstance(res.value, DAGRunReport):
                report = res.value
            if report is not None:
                for nid, result in report.results.items():
                    self.state.node_states[nid] = result.state
        ctx.update(_update_run)


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

    def test_fake_add_node_and_state(self) -> None:
        self.dag.add_node("n1", lambda: 42, priority=10, retries=2)
        self.assertIn("n1", self.state.nodes)
        self.assertEqual(self.state.nodes["n1"].priority, 10)
        self.assertEqual(self.state.nodes["n1"].retries, 2)
        self.assertEqual(self.state.node_states["n1"], NodeState.READY)

    def test_fake_add_node_with_dependencies(self) -> None:
        self.dag.add_node("n1", lambda: 1)
        self.dag.add_node("n2", lambda: 2, dependencies=["n1"])
        self.assertIn("n1", self.state.upstream["n2"])
        self.assertIn("n2", self.state.downstream["n1"])
        self.assertEqual(self.state.node_states["n2"], NodeState.PENDING)

    def test_fake_add_edge_success_and_error(self) -> None:
        self.dag.add_node("u", lambda: None)
        self.dag.add_node("v", lambda: None)
        self.dag.add_edge("u", "v")
        self.assertIn("u", self.dag.get_dependencies("v"))
        self.assertIn("v", self.dag.get_dependents("u"))
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing_upstream", "v")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("u", "missing_downstream")

    def test_fake_remove_node_success_and_error(self) -> None:
        self.dag.add_node("r1", lambda: None)
        self.dag.add_node("r2", lambda: None, dependencies=["r1"])
        self.dag.remove_node("r1")
        self.assertFalse(self.dag.has_node("r1"))
        self.assertNotIn("r1", self.dag.get_dependencies("r2"))
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")

    def test_fake_remove_node_with_dependents(self) -> None:
        self.dag.add_node("parent", lambda: None)
        self.dag.add_node("child", lambda: None, dependencies=["parent"])
        self.assertIn("parent", self.dag.get_dependencies("child"))
        self.dag.remove_node("parent")
        self.assertFalse(self.dag.has_node("parent"))
        self.assertEqual(self.dag.get_dependencies("child"), set())
        self.assertEqual(self.dag.get_node("child").dependencies, frozenset())
        self.assertEqual(self.wavescheduler.get_state("child"), NodeState.READY)

    def test_fake_get_node_and_queries(self) -> None:
        self.dag.add_node("root", lambda: None)
        self.dag.add_node("leaf", lambda: None, dependencies=["root"])
        node_def = self.dag.get_node("root")
        self.assertEqual(node_def.node_id, "root")
        self.assertEqual(self.dag.all_nodes(), {"root", "leaf"})
        self.assertEqual(self.dag.find_roots(), {"root"})
        self.assertEqual(self.dag.find_leaves(), {"leaf"})
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("nonexistent")

    def test_fake_validate_and_topological_sort(self) -> None:
        self.dag.add_node("a", lambda: None, priority=5)
        self.dag.add_node("b", lambda: None, dependencies=["a"], priority=10)
        self.dag.validate()
        order = self.dag.topological_sort()
        self.assertEqual(order, ["a", "b"])

    def test_fake_validate_errors(self) -> None:
        self.dag.add_node("bad", lambda: None, dependencies=["missing_dep"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()
        self.dag.remove_node("bad")
        self.dag.add_node("c1", lambda: None)
        self.dag.add_node("c2", lambda: None, dependencies=["c1"])
        self.dag.add_edge("c2", "c1")
        with self.assertRaises(CycleError):
            self.dag.validate()

    def test_fake_topological_sort_missing_dependency(self) -> None:
        self.dag.add_node("orphan", lambda: None, dependencies=["phantom_dep"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.topological_sort()

    def test_fake_compute_critical_path(self) -> None:
        self.dag.add_node("p1", lambda: None)
        self.dag.add_node("p2", lambda: None, dependencies=["p1"])
        path, weight = self.dag.compute_critical_path({"p1": 2.5, "p2": 3.5})
        self.assertEqual(path, ["p1", "p2"])
        self.assertEqual(weight, 6.0)

    def test_fake_compute_critical_path_empty_graph(self) -> None:
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_fake_scheduler_lifecycle(self) -> None:
        self.dag.add_node("s1", lambda: None)
        self.dag.add_node("s2", lambda: None, dependencies=["s1"])
        wave1 = self.wavescheduler.next_wave()
        self.assertEqual(wave1, ["s1"])
        self.wavescheduler.mark_running("s1")
        self.assertEqual(self.wavescheduler.get_state("s1"), NodeState.RUNNING)
        self.wavescheduler.mark_succeeded("s1")
        self.assertEqual(self.wavescheduler.get_state("s1"), NodeState.SUCCEEDED)
        wave2 = self.wavescheduler.next_wave()
        self.assertEqual(wave2, ["s2"])
        self.wavescheduler.mark_succeeded("s2")
        self.assertTrue(self.wavescheduler.is_finished())
        states = self.wavescheduler.get_all_states()
        self.assertEqual(states["s1"], NodeState.SUCCEEDED)
        self.assertEqual(states["s2"], NodeState.SUCCEEDED)

    def test_fake_scheduler_failure_policies(self) -> None:
        self.dag.add_node("f1", lambda: None)
        self.dag.add_node("f2", lambda: None, dependencies=["f1"])
        self.wavescheduler.mark_failed("f1", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("f1"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("f2"), NodeState.CANCELLED)
        self.assertTrue(self.wavescheduler.is_finished())

    def test_fake_scheduler_failure_transitive_skip_downstream(self) -> None:
        self.dag.add_node("t1", lambda: None)
        self.dag.add_node("t2", lambda: None, dependencies=["t1"])
        self.dag.add_node("t3", lambda: None, dependencies=["t2"])
        self.dag.add_node("t4", lambda: None, dependencies=["t3"])
        self.wavescheduler.mark_failed("t1", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("t1"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("t2"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("t3"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("t4"), NodeState.SKIPPED)

    def test_fake_scheduler_failure_transitive_continue_on_error(self) -> None:
        self.dag.add_node("c1", lambda: None)
        self.dag.add_node("c2", lambda: None, dependencies=["c1"])
        self.dag.add_node("c3", lambda: None, dependencies=["c2"])
        self.dag.add_node("c_indep", lambda: None)
        self.wavescheduler.mark_failed("c1", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.wavescheduler.get_state("c1"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("c2"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("c3"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("c_indep"), NodeState.READY)

    def test_fake_is_finished_empty_graph_and_running(self) -> None:
        self.assertTrue(self.wavescheduler.is_finished())
        self.dag.add_node("run_node", lambda: None)
        self.wavescheduler.mark_running("run_node")
        self.assertFalse(self.wavescheduler.is_finished())

    def test_fake_get_state_absent_node(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("absent_node")

    def test_fake_runner_run(self) -> None:
        self.dag.add_node("r1", lambda: None)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("r1",))
        self.assertEqual(len(report.results), 1)


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

    def test_real_graph_construction_and_queries(self) -> None:
        self.sm.dispatch_transition("add_node", "a", lambda: "val_a", [], 10, 0)
        self.sm.dispatch_transition("add_node", "b", lambda: "val_b", ["a"], 5, 0)
        self.sm.dispatch_transition("add_node", "c", lambda: "val_c", ["a"], 8, 0)
        self.sm.dispatch_transition("add_node", "d", lambda: "val_d", ["b", "c"], 1, 0)
        self.sm.dispatch_transition("has_node", "a")
        self.sm.dispatch_transition("has_node", "missing")
        self.sm.dispatch_transition("get_node", "a")
        self.sm.dispatch_transition("get_dependencies", "d")
        self.sm.dispatch_transition("get_dependents", "a")
        self.sm.dispatch_transition("all_nodes")
        self.sm.dispatch_transition("find_roots")
        self.sm.dispatch_transition("find_leaves")
        self.sm.dispatch_transition("validate")
        self.sm.dispatch_transition("topological_sort")
        self.sm.dispatch_transition("compute_critical_path", {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0})

    def test_real_add_edge_and_remove_node(self) -> None:
        self.sm.dispatch_transition("add_node", "x", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("add_node", "y", lambda: 2, [], 0, 0)
        self.sm.dispatch_transition("add_edge", "x", "y")
        self.sm.dispatch_transition("get_dependencies", "y")
        self.sm.dispatch_transition("get_dependents", "x")
        self.sm.dispatch_transition("remove_node", "y")
        self.sm.dispatch_transition("has_node", "y")

    def test_real_remove_node_with_dependents(self) -> None:
        self.sm.dispatch_transition("add_node", "p1", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("add_node", "c1", lambda: 2, ["p1"], 0, 0)
        self.sm.dispatch_transition("remove_node", "p1")
        self.sm.dispatch_transition("has_node", "p1")
        self.sm.dispatch_transition("get_dependencies", "c1")
        self.sm.dispatch_transition("get_node", "c1")
        self.sm.dispatch_transition("get_state", "c1")

    def test_real_node_not_found_errors(self) -> None:
        self.sm.dispatch_transition("add_node", "exist_node", lambda: 1, [], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing_node")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing_node")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing_node")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing_node")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing_upstream", "exist_node")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("exist_node", "missing_downstream")
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("missing_sched_node")

    def test_real_validation_and_cycle_errors(self) -> None:
        self.sm.dispatch_transition("add_node", "n_bad", lambda: 1, ["nonexistent_dep"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()
        with self.assertRaises(NodeNotFoundError):
            self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.sm.dispatch_transition("remove_node", "n_bad")
        self.sm.dispatch_transition("add_node", "c1", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("add_node", "c2", lambda: 2, ["c1"], 0, 0)
        self.sm.dispatch_transition("add_edge", "c2", "c1")
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()
        with self.assertRaises(CycleError):
            self.dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_real_topological_sort_missing_dependency(self) -> None:
        self.sm.dispatch_transition("add_node", "topo_bad", lambda: 1, ["missing_dep_for_topo"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.topological_sort()
        self.sm.dispatch_transition("remove_node", "topo_bad")

    def test_real_compute_critical_path_empty_graph(self) -> None:
        self.sm.dispatch_transition("compute_critical_path")

    def test_real_scheduler_waves_and_lifecycle(self) -> None:
        self.sm.dispatch_transition("add_node", "w1", lambda: 1, [], 10, 0)
        self.sm.dispatch_transition("add_node", "w2", lambda: 2, ["w1"], 5, 0)
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "w1")
        self.sm.dispatch_transition("get_state", "w1")
        self.sm.dispatch_transition("mark_succeeded", "w1")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "w2")
        self.sm.dispatch_transition("mark_succeeded", "w2")
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("is_finished")

    def test_real_scheduler_failure_fail_fast(self) -> None:
        self.sm.dispatch_transition("add_node", "ff1", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("add_node", "ff2", lambda: 2, ["ff1"], 0, 0)
        self.sm.dispatch_transition("mark_failed", "ff1", FailurePolicy.FAIL_FAST)
        self.sm.dispatch_transition("is_finished")

    def test_real_scheduler_failure_skip_downstream(self) -> None:
        self.sm.dispatch_transition("add_node", "sd1", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("add_node", "sd2", lambda: 2, ["sd1"], 0, 0)
        self.sm.dispatch_transition("add_node", "sd3", lambda: 3, ["sd2"], 0, 0)
        self.sm.dispatch_transition("add_node", "sd4", lambda: 4, ["sd3"], 0, 0)
        self.sm.dispatch_transition("mark_failed", "sd1", FailurePolicy.SKIP_DOWNSTREAM)
        self.sm.dispatch_transition("get_state", "sd2")
        self.sm.dispatch_transition("get_state", "sd3")
        self.sm.dispatch_transition("get_state", "sd4")
        self.sm.dispatch_transition("is_finished")

    def test_real_scheduler_failure_continue_on_error(self) -> None:
        self.sm.dispatch_transition("add_node", "ce1", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("add_node", "ce2", lambda: 2, ["ce1"], 0, 0)
        self.sm.dispatch_transition("add_node", "ce3", lambda: 3, ["ce2"], 0, 0)
        self.sm.dispatch_transition("add_node", "ce_indep", lambda: 4, [], 0, 0)
        self.sm.dispatch_transition("mark_failed", "ce1", FailurePolicy.CONTINUE_ON_ERROR)
        self.sm.dispatch_transition("get_state", "ce2")
        self.sm.dispatch_transition("get_state", "ce3")
        self.sm.dispatch_transition("get_state", "ce_indep")

    def test_real_is_finished_empty_and_running(self) -> None:
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("add_node", "rn_real", lambda: 1, [], 0, 0)
        self.sm.dispatch_transition("mark_running", "rn_real")
        self.sm.dispatch_transition("is_finished")

    def test_real_dag_runner_success(self) -> None:
        self.sm.dispatch_transition("add_node", "r1", lambda: "ok1", [], 0, 0)
        self.sm.dispatch_transition("add_node", "r2", lambda: "ok2", ["r1"], 0, 0)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)
        self.sm.dispatch_transition("get_state", "r1")
        self.sm.dispatch_transition("get_state", "r2")
        self.sm.dispatch_transition("is_finished")

    def test_real_dag_runner_failure_with_retries(self) -> None:
        attempts = [0]
        def flaky_action() -> None:
            attempts[0] += 1
            raise ValueError("Failure attempt")
        self.sm.dispatch_transition("add_node", "flaky", flaky_action, [], 0, 2)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_real_dag_runner_failure_policies(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")
        self.sm.dispatch_transition("add_node", "f_node", boom, [], 0, 0)
        self.sm.dispatch_transition("add_node", "f_dep", lambda: 10, ["f_node"], 0, 0)
        self.sm.dispatch_transition("add_node", "f_indep", lambda: 20, [], 0, 0)
        self.sm.dispatch_transition("run", FailurePolicy.CONTINUE_ON_ERROR)


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
        self.__dict__["_services"] = (self.dag, self.wavescheduler, self.dagrunner)

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
# LAST_CLEANED: 2026-10-29T00:07:19Z
# LAST_CHANGED: 2026-10-29T00:05:05Z
# CHANGE: Add comprehensive test coverage and state machine transitions for error branches and contract postconditions across DAG and WaveScheduler
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T00:07:19Z
# PRETENSE_QA_AUDIT: 2026-10-29T00:06:27Z
# --- END CLEANROOM METADATA ---
