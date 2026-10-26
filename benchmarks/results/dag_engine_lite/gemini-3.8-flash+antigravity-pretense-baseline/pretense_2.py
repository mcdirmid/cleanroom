"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
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
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    initialized: bool = True


proto = StateMachineProto[DagEngineLiteState]()


# ------------------------------------------------------------------------------
# 1.1 DAG.add_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.add_node)
def add_node(): pass

@add_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    action: Any | NotBoundType = NotBound,
    dependencies: Any | NotBoundType = NotBound,
    priority: Any | NotBoundType = NotBound,
    retries: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_id = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    resolved_action = action if not isinstance(action, NotBoundType) and action is not None else (lambda: 42)
    resolved_deps = tuple(dependencies) if not isinstance(dependencies, NotBoundType) and dependencies is not None else ()
    resolved_prio = int(priority) if not isinstance(priority, NotBoundType) else 0
    resolved_retries = int(retries) if not isinstance(retries, NotBoundType) else 0
    return (resolved_id, resolved_action, resolved_deps, resolved_prio, resolved_retries)

@add_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@add_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    result: Any,
) -> None:
    deps = frozenset(dependencies) if dependencies is not None else frozenset()
    action_fn = action if callable(action) else (lambda: None)
    ndef = NodeDefinition(
        node_id=str(node_id),
        action=action_fn,
        dependencies=deps,
        priority=priority or 0,
        retries=retries or 0,
    )
    nid = str(node_id)
    state.nodes[nid] = ndef
    if nid not in state.upstream:
        state.upstream[nid] = set()
    if nid not in state.downstream:
        state.downstream[nid] = set()
    for dep in deps:
        state.upstream[nid].add(dep)
        if dep not in state.downstream:
            state.downstream[dep] = set()
        state.downstream[dep].add(nid)
    if not state.upstream[nid]:
        state.states[nid] = NodeState.READY
    else:
        state.states[nid] = NodeState.PENDING


# ------------------------------------------------------------------------------
# 1.2 DAG.add_edge
# ------------------------------------------------------------------------------

@proto.transition(DAG.add_edge)
def add_edge(): pass

@add_edge.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    u = str(upstream_id) if not isinstance(upstream_id, NotBoundType) else "u_node"
    d = str(downstream_id) if not isinstance(downstream_id, NotBoundType) else "d_node"
    return (u, d)

@add_edge.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    u, d = str(upstream_id), str(downstream_id)
    if u not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {u}", node_id=u))
    if d not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {d}", node_id=d))
    return Value(None)

@add_edge.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any,
) -> None:
    u, d = str(upstream_id), str(downstream_id)
    if u in state.nodes and d in state.nodes:
        state.upstream[d].add(u)
        state.downstream[u].add(d)
        curr = state.nodes[d]
        state.nodes[d] = NodeDefinition(
            node_id=curr.node_id,
            action=curr.action,
            dependencies=curr.dependencies | {u},
            priority=curr.priority,
            retries=curr.retries,
        )
        if state.states.get(d) == NodeState.READY:
            state.states[d] = NodeState.PENDING


# ------------------------------------------------------------------------------
# 1.3 DAG.remove_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.remove_node)
def remove_node(): pass

@remove_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@remove_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {nid}", node_id=nid))
    return Value(None)

@remove_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    nid = str(node_id)
    if nid in state.nodes:
        for dep in list(state.upstream.get(nid, set())):
            if dep in state.downstream:
                state.downstream[dep].discard(nid)
        for child in list(state.downstream.get(nid, set())):
            if child in state.upstream:
                state.upstream[child].discard(nid)
            if child in state.nodes:
                c_node = state.nodes[child]
                state.nodes[child] = NodeDefinition(
                    node_id=c_node.node_id,
                    action=c_node.action,
                    dependencies=frozenset(d for d in c_node.dependencies if d != nid),
                    priority=c_node.priority,
                    retries=c_node.retries,
                )
        state.nodes.pop(nid, None)
        state.upstream.pop(nid, None)
        state.downstream.pop(nid, None)
        state.states.pop(nid, None)


# ------------------------------------------------------------------------------
# 1.4 DAG.has_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.has_node)
def has_node(): pass

@has_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@has_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(str(node_id) in state.nodes)

@has_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.5 DAG.get_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.get_node)
def get_node(): pass

@get_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@get_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {nid}", node_id=nid))
    return Value(state.nodes[nid])

@get_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.6 DAG.get_dependencies
# ------------------------------------------------------------------------------

@proto.transition(DAG.get_dependencies)
def get_dependencies(): pass

@get_dependencies.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@get_dependencies.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {nid}", node_id=nid))
    return Value(set(state.upstream.get(nid, set())))

@get_dependencies.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.7 DAG.get_dependents
# ------------------------------------------------------------------------------

@proto.transition(DAG.get_dependents)
def get_dependents(): pass

@get_dependents.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@get_dependents.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {nid}", node_id=nid))
    return Value(set(state.downstream.get(nid, set())))

@get_dependents.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.8 DAG.all_nodes
# ------------------------------------------------------------------------------

@proto.transition(DAG.all_nodes)
def all_nodes(): pass

@all_nodes.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@all_nodes.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(set(state.nodes.keys()))

@all_nodes.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.9 DAG.validate
# ------------------------------------------------------------------------------

@proto.transition(DAG.validate)
def validate(): pass

@validate.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@validate.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    for nid, ndef in state.nodes.items():
        for dep in ndef.dependencies:
            if dep not in state.nodes:
                return Raised(NodeNotFoundError(message=f"Missing dep {dep}", node_id=dep))
    visited: Dict[str, int] = {}
    path: List[str] = []
    cycle_detected: Optional[Tuple[str, ...]] = None

    def check_cycle(curr: str) -> None:
        nonlocal cycle_detected
        visited[curr] = 1
        path.append(curr)
        for ch in sorted(state.downstream.get(curr, set())):
            if ch not in state.nodes:
                continue
            st_val = visited.get(ch, 0)
            if st_val == 1:
                idx = path.index(ch)
                cycle_detected = tuple(path[idx:] + [ch])
                return
            elif st_val == 0:
                check_cycle(ch)
                if cycle_detected is not None:
                    return
        path.pop()
        visited[curr] = 2

    for nid in sorted(state.nodes.keys()):
        if visited.get(nid, 0) == 0:
            check_cycle(nid)
            if cycle_detected is not None:
                return Raised(CycleError(message=f"Cycle: {cycle_detected}", cycle=cycle_detected))
    return Value(None)

@validate.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.10 DAG.topological_sort
# ------------------------------------------------------------------------------

@proto.transition(DAG.topological_sort)
def topological_sort(): pass

@topological_sort.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@topological_sort.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    for nid, ndef in state.nodes.items():
        for dep in ndef.dependencies:
            if dep not in state.nodes:
                return Raised(NodeNotFoundError(message=f"Missing dep {dep}", node_id=dep))
    in_degree = {nid: len([p for p in state.upstream.get(nid, set()) if p in state.nodes]) for nid in state.nodes}
    ready = [nid for nid, deg in in_degree.items() if deg == 0]
    ready.sort(key=lambda n: (-state.nodes[n].priority, n))
    ordered = []
    while ready:
        curr = ready.pop(0)
        ordered.append(curr)
        for ch in sorted(state.downstream.get(curr, set())):
            if ch in in_degree:
                in_degree[ch] -= 1
                if in_degree[ch] == 0:
                    ready.append(ch)
        ready.sort(key=lambda n: (-state.nodes[n].priority, n))
    if len(ordered) != len(state.nodes):
        return Raised(CycleError(message="Cycle detected", cycle=("cycle",)))
    return Value(ordered)

@topological_sort.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.11 DAG.find_roots
# ------------------------------------------------------------------------------

@proto.transition(DAG.find_roots)
def find_roots(): pass

@find_roots.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@find_roots.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    roots = {nid for nid in state.nodes if not any(p in state.nodes for p in state.upstream.get(nid, set()))}
    return Value(roots)

@find_roots.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.12 DAG.find_leaves
# ------------------------------------------------------------------------------

@proto.transition(DAG.find_leaves)
def find_leaves(): pass

@find_leaves.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@find_leaves.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    leaves = {nid for nid in state.nodes if not any(c in state.nodes for c in state.downstream.get(nid, set()))}
    return Value(leaves)

@find_leaves.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.13 DAG.compute_critical_path
# ------------------------------------------------------------------------------

@proto.transition(DAG.compute_critical_path)
def compute_critical_path(): pass

@compute_critical_path.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    d = dict(estimated_durations) if not isinstance(estimated_durations, NotBoundType) and estimated_durations is not None else None
    return (d,)

@compute_critical_path.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    if not state.nodes:
        return Value(([], 0.0))
    # Simple critical path for fake
    nodes = sorted(state.nodes.keys())
    return Value((nodes, float(len(nodes))))

@compute_critical_path.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.14 WaveScheduler.next_wave
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.next_wave)
def next_wave(): pass

@next_wave.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@next_wave.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    ready: List[str] = []
    for nid, st_val in state.states.items():
        if st_val == NodeState.READY:
            deps = state.upstream.get(nid, set())
            if all(state.states.get(d) == NodeState.SUCCEEDED for d in deps):
                ready.append(nid)
    ready.sort(key=lambda n: (-state.nodes[n].priority if n in state.nodes else 0, n))
    return Value(ready)

@next_wave.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.15 WaveScheduler.mark_running
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.mark_running)
def mark_running(): pass

@mark_running.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@mark_running.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@mark_running.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    state.states[str(node_id)] = NodeState.RUNNING


# ------------------------------------------------------------------------------
# 1.16 WaveScheduler.mark_succeeded
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.mark_succeeded)
def mark_succeeded(): pass

@mark_succeeded.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@mark_succeeded.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@mark_succeeded.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    nid = str(node_id)
    state.states[nid] = NodeState.SUCCEEDED
    for child in state.downstream.get(nid, set()):
        if state.states.get(child) == NodeState.PENDING:
            upstreams = state.upstream.get(child, set())
            if all(state.states.get(u) == NodeState.SUCCEEDED for u in upstreams):
                state.states[child] = NodeState.READY


# ------------------------------------------------------------------------------
# 1.17 WaveScheduler.mark_failed
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.mark_failed)
def mark_failed(): pass

@mark_failed.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    pol = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    return (nid, pol)

@mark_failed.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@mark_failed.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    nid = str(node_id)
    state.states[nid] = NodeState.FAILED
    terminals = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
    if failure_policy == FailurePolicy.FAIL_FAST:
        for k in list(state.states.keys()):
            if k != nid and state.states[k] not in terminals:
                state.states[k] = NodeState.CANCELLED
    else:
        queue = list(state.downstream.get(nid, set()))
        seen = set()
        while queue:
            curr = queue.pop(0)
            if curr in seen:
                continue
            seen.add(curr)
            if state.states.get(curr) not in terminals:
                state.states[curr] = NodeState.SKIPPED
            for next_c in state.downstream.get(curr, set()):
                if next_c not in seen:
                    queue.append(next_c)


# ------------------------------------------------------------------------------
# 1.18 WaveScheduler.is_finished
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.is_finished)
def is_finished(): pass

@is_finished.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@is_finished.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    if not state.nodes:
        return Value(True)
    terminals = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
    if all(state.states.get(n) in terminals for n in state.nodes):
        return Value(True)
    if any(state.states.get(n) in (NodeState.RUNNING, NodeState.READY) for n in state.nodes):
        return Value(False)
    return Value(True)

@is_finished.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.19 WaveScheduler.get_state
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.get_state)
def get_state(): pass

@get_state.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nid = str(node_id) if not isinstance(node_id, NotBoundType) else "sample_node_id"
    return (nid,)

@get_state.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Missing {nid}", node_id=nid))
    return Value(state.states.get(nid, NodeState.PENDING))

@get_state.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.20 WaveScheduler.get_all_states
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.get_all_states)
def get_all_states(): pass

@get_all_states.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@get_all_states.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value({nid: state.states.get(nid, NodeState.PENDING) for nid in state.nodes})

@get_all_states.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.21 DAGRunner.run
# ------------------------------------------------------------------------------

@proto.transition(DAGRunner.run)
def run(): pass

@run.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    pol = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    return (pol,)

@run.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    succeeded = tuple(n for n in state.nodes)
    report = DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded,
        failed_nodes=(),
        skipped_nodes=(),
        cancelled_nodes=(),
        wall_clock_seconds=0.01,
        critical_path=succeeded,
        results={n: NodeResult(node_id=n, state=NodeState.SUCCEEDED) for n in state.nodes},
    )
    return Value(report)

@run.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    for n in state.nodes:
        state.states[n] = NodeState.SUCCEEDED


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_dag_engine_lite_fakes(
    state: DagEngineLiteState,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = proto.make_state_machine(state)
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
        self.assertEqual(len(self.state.nodes), 0)

    def test_fake_add_node(self) -> None:
        self.dag.add_node("node1", lambda: 10, dependencies=None, priority=5, retries=1)
        self.assertIn("node1", self.state.nodes)
        self.assertEqual(self.state.nodes["node1"].priority, 5)

    def test_fake_add_edge(self) -> None:
        self.dag.add_node("u", lambda: 1)
        self.dag.add_node("d", lambda: 2)
        self.dag.add_edge("u", "d")
        self.assertIn("u", self.state.upstream["d"])
        self.assertIn("d", self.state.downstream["u"])

    def test_fake_add_edge_missing_raises(self) -> None:
        self.dag.add_node("u", lambda: 1)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("u", "missing")

    def test_fake_remove_node(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.remove_node("a")
        self.assertNotIn("a", self.state.nodes)
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("a")

    def test_fake_has_node(self) -> None:
        self.assertFalse(self.dag.has_node("x"))
        self.dag.add_node("x", lambda: 1)
        self.assertTrue(self.dag.has_node("x"))

    def test_fake_get_node(self) -> None:
        self.dag.add_node("x", lambda: 42, priority=2)
        node = self.dag.get_node("x")
        self.assertEqual(node.node_id, "x")
        self.assertEqual(node.priority, 2)
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("nonexistent")

    def test_fake_get_dependencies(self) -> None:
        self.dag.add_node("x", lambda: 1)
        self.dag.add_node("y", lambda: 2, dependencies=["x"])
        self.assertEqual(self.dag.get_dependencies("y"), {"x"})
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("nonexistent")

    def test_fake_get_dependents(self) -> None:
        self.dag.add_node("x", lambda: 1)
        self.dag.add_node("y", lambda: 2, dependencies=["x"])
        self.assertEqual(self.dag.get_dependents("x"), {"y"})
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("nonexistent")

    def test_fake_all_nodes(self) -> None:
        self.dag.add_node("n1", lambda: 1)
        self.dag.add_node("n2", lambda: 2)
        self.assertEqual(self.dag.all_nodes(), {"n1", "n2"})

    def test_fake_validate(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.validate()

        self.dag.add_node("c", lambda: 3, dependencies=["missing"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_fake_validate_cycle(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.dag.validate()

    def test_fake_topological_sort(self) -> None:
        self.dag.add_node("b", lambda: 2, priority=1)
        self.dag.add_node("a", lambda: 1, priority=10)
        topo = self.dag.topological_sort()
        self.assertEqual(topo, ["a", "b"])

    def test_fake_find_roots(self) -> None:
        self.dag.add_node("root", lambda: 1)
        self.dag.add_node("child", lambda: 2, dependencies=["root"])
        self.assertEqual(self.dag.find_roots(), {"root"})

    def test_fake_find_leaves(self) -> None:
        self.dag.add_node("root", lambda: 1)
        self.dag.add_node("child", lambda: 2, dependencies=["root"])
        self.assertEqual(self.dag.find_leaves(), {"child"})

    def test_fake_compute_critical_path(self) -> None:
        self.dag.add_node("n1", lambda: 1)
        path, dur = self.dag.compute_critical_path()
        self.assertEqual(path, ["n1"])
        self.assertEqual(dur, 1.0)

    def test_fake_next_wave(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, ["a"])

    def test_fake_mark_running(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.wavescheduler.mark_running("a")
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.RUNNING)

    def test_fake_mark_succeeded(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.wavescheduler.mark_succeeded("a")
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.wavescheduler.get_state("b"), NodeState.READY)

    def test_fake_mark_failed(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.wavescheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("b"), NodeState.CANCELLED)

    def test_fake_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.wavescheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("b"), NodeState.SKIPPED)

    def test_fake_is_finished(self) -> None:
        self.assertTrue(self.wavescheduler.is_finished())
        self.dag.add_node("a", lambda: 1)
        self.assertFalse(self.wavescheduler.is_finished())
        self.wavescheduler.mark_succeeded("a")
        self.assertTrue(self.wavescheduler.is_finished())

    def test_fake_get_state(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.READY)
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("missing")

    def test_fake_get_all_states(self) -> None:
        self.dag.add_node("a", lambda: 1)
        states = self.wavescheduler.get_all_states()
        self.assertEqual(states, {"a": NodeState.READY})

    def test_fake_run(self) -> None:
        self.dag.add_node("a", lambda: 1)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("a",))


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

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        self.assertIsNotNone(self.dag)
        self.assertIsNotNone(self.wavescheduler)
        self.assertIsNotNone(self.dagrunner)

    def test_real_dag_add_and_get_node(self) -> None:
        self.dag.add_node("nodeA", lambda: "valA", priority=10, retries=2)
        self.assertTrue(self.dag.has_node("nodeA"))
        ndef = self.dag.get_node("nodeA")
        self.assertEqual(ndef.node_id, "nodeA")
        self.assertEqual(ndef.priority, 10)
        self.assertEqual(ndef.retries, 2)
        self.assertEqual(ndef.dependencies, frozenset())
        self.assertEqual(ndef.action(), "valA")

    def test_real_dag_get_node_not_found(self) -> None:
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.dag.get_node("absent")
        self.assertEqual(ctx.exception.node_id, "absent")

    def test_real_dag_add_edge_and_dependencies(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2)
        self.dag.add_edge("A", "B")
        self.assertEqual(self.dag.get_dependencies("B"), {"A"})
        self.assertEqual(self.dag.get_dependents("A"), {"B"})
        # NodeDefinition dependencies updated
        self.assertIn("A", self.dag.get_node("B").dependencies)

    def test_real_dag_add_edge_missing_nodes(self) -> None:
        self.dag.add_node("A", lambda: 1)
        with self.assertRaises(NodeNotFoundError) as ctx1:
            self.dag.add_edge("missing_upstream", "A")
        self.assertEqual(ctx1.exception.node_id, "missing_upstream")

        with self.assertRaises(NodeNotFoundError) as ctx2:
            self.dag.add_edge("A", "missing_downstream")
        self.assertEqual(ctx2.exception.node_id, "missing_downstream")

    def test_real_dag_remove_node(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2, dependencies=["A"])
        self.dag.add_node("C", lambda: 3, dependencies=["B"])
        self.wavescheduler.next_wave()
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.PENDING)

        self.dag.remove_node("B")
        self.assertFalse(self.dag.has_node("B"))
        self.assertNotIn("B", self.dag.get_dependents("A"))
        self.assertNotIn("B", self.dag.get_dependencies("C"))
        self.assertNotIn("B", self.dag.all_nodes())

        # Removing missing raises NodeNotFoundError
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.dag.remove_node("B")
        self.assertEqual(ctx.exception.node_id, "B")

    def test_real_dag_get_dependencies_and_dependents_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_real_dag_validate_missing_dep(self) -> None:
        # Deferred check: add_node allows missing dependency initially
        self.dag.add_node("B", lambda: 2, dependencies=["A"])
        with self.assertRaises(NodeNotFoundError) as ctx:
            self.dag.validate()
        self.assertEqual(ctx.exception.node_id, "A")

    def test_real_dag_validate_and_topo_sort_cycle(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2)
        self.dag.add_edge("A", "B")
        self.dag.add_edge("B", "A")

        with self.assertRaises(CycleError) as ctx1:
            self.dag.validate()
        self.assertIn("A", ctx1.exception.cycle)

        with self.assertRaises(CycleError) as ctx2:
            self.dag.topological_sort()
        self.assertIn("A", ctx2.exception.cycle)

    def test_real_dag_topological_sort_missing_dep(self) -> None:
        self.dag.add_node("B", lambda: 2, dependencies=["missing"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.topological_sort()

    def test_real_dag_topological_sort_priority_tie_break(self) -> None:
        # Independent nodes sorted by priority descending, then node_id ascending
        self.dag.add_node("B", lambda: 1, priority=5)
        self.dag.add_node("A", lambda: 1, priority=5)
        self.dag.add_node("C", lambda: 1, priority=10)
        self.dag.add_node("D", lambda: 1, priority=1)
        topo = self.dag.topological_sort()
        self.assertEqual(topo, ["C", "A", "B", "D"])

    def test_real_dag_find_roots_and_leaves(self) -> None:
        self.dag.add_node("R1", lambda: 1)
        self.dag.add_node("R2", lambda: 1)
        self.dag.add_node("M", lambda: 1, dependencies=["R1", "R2"])
        self.dag.add_node("L1", lambda: 1, dependencies=["M"])
        self.dag.add_node("L2", lambda: 1, dependencies=["M"])

        self.assertEqual(self.dag.find_roots(), {"R1", "R2"})
        self.assertEqual(self.dag.find_leaves(), {"L1", "L2"})

    def test_real_dag_critical_path_empty(self) -> None:
        path, dur = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(dur, 0.0)

    def test_real_dag_critical_path_custom_durations(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 1, dependencies=["A"])
        self.dag.add_node("C", lambda: 1, dependencies=["A"])
        self.dag.add_node("D", lambda: 1, dependencies=["B", "C"])

        durations = {"A": 2.0, "B": 5.0, "C": 1.0, "D": 3.0}
        path, weight = self.dag.compute_critical_path(estimated_durations=durations)
        self.assertEqual(path, ["A", "B", "D"])
        self.assertEqual(weight, 10.0)

    def test_real_dag_critical_path_default_durations(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 1, dependencies=["A"])
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["A", "B"])
        self.assertEqual(weight, 2.0)

    def test_real_wave_scheduler_flow(self) -> None:
        self.dag.add_node("A", lambda: 1, priority=1)
        self.dag.add_node("B", lambda: 2, priority=2)
        self.dag.add_node("C", lambda: 3, dependencies=["A", "B"])

        # First wave should contain roots sorted by priority descending
        wave1 = self.wavescheduler.next_wave()
        self.assertEqual(wave1, ["B", "A"])

        self.wavescheduler.mark_running("B")
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.RUNNING)
        self.assertFalse(self.wavescheduler.is_finished())

        self.wavescheduler.mark_succeeded("B")
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.SUCCEEDED)
        # C is still pending because A is not completed
        self.assertEqual(self.wavescheduler.get_state("C"), NodeState.PENDING)

        self.wavescheduler.mark_running("A")
        self.wavescheduler.mark_succeeded("A")
        # Now C should be promoted to READY
        self.assertEqual(self.wavescheduler.get_state("C"), NodeState.READY)

        wave2 = self.wavescheduler.next_wave()
        self.assertEqual(wave2, ["C"])

        self.wavescheduler.mark_running("C")
        self.wavescheduler.mark_succeeded("C")
        self.assertTrue(self.wavescheduler.is_finished())

    def test_real_wave_scheduler_get_state_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("missing")

    def test_real_wave_scheduler_get_all_states(self) -> None:
        self.dag.add_node("A", lambda: 1)
        all_st = self.wavescheduler.get_all_states()
        self.assertEqual(all_st, {"A": NodeState.READY})

    def test_real_wave_scheduler_mark_failed_fail_fast(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2)
        self.dag.add_node("C", lambda: 3, dependencies=["A"])

        self.wavescheduler.next_wave()
        self.wavescheduler.mark_failed("A", failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.CANCELLED)
        self.assertEqual(self.wavescheduler.get_state("C"), NodeState.CANCELLED)
        self.assertTrue(self.wavescheduler.is_finished())

    def test_real_wave_scheduler_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2)
        self.dag.add_node("C", lambda: 3, dependencies=["A"])
        self.dag.add_node("D", lambda: 4, dependencies=["C"])

        self.wavescheduler.next_wave()
        self.wavescheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.READY)
        self.assertEqual(self.wavescheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("D"), NodeState.SKIPPED)

    def test_real_wave_scheduler_mark_failed_continue_on_error(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2)
        self.dag.add_node("C", lambda: 3, dependencies=["A"])

        self.wavescheduler.next_wave()
        self.wavescheduler.mark_failed("A", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.READY)
        self.assertEqual(self.wavescheduler.get_state("C"), NodeState.SKIPPED)

    def test_real_dag_runner_success(self) -> None:
        calls = []
        self.dag.add_node("A", lambda: calls.append("A") or "resA")
        self.dag.add_node("B", lambda: calls.append("B") or "resB", dependencies=["A"])

        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("A", "B"))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.critical_path, ("A", "B"))
        self.assertEqual(report.results["A"].value, "resA")
        self.assertEqual(report.results["B"].value, "resB")
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_real_dag_runner_retry_success(self) -> None:
        attempts = 0

        def flaky_action():
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise ValueError("Temporary failure")
            return "recovered"

        self.dag.add_node("flaky", flaky_action, retries=3)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.succeeded_nodes, ("flaky",))
        self.assertEqual(report.results["flaky"].retries_attempted, 2)
        self.assertEqual(report.results["flaky"].value, "recovered")

    def test_real_dag_runner_fail_fast(self) -> None:
        def boom():
            raise RuntimeError("Task failed")

        self.dag.add_node("A", boom, retries=1)
        self.dag.add_node("B", lambda: "ok")
        self.dag.add_node("C", lambda: "downstream", dependencies=["A"])

        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("A",))
        self.assertIn("B", report.cancelled_nodes)
        self.assertIn("C", report.cancelled_nodes)
        self.assertIsInstance(report.results["A"].error, RuntimeError)
        self.assertEqual(report.results["A"].retries_attempted, 1)

    def test_real_dag_runner_continue_on_error(self) -> None:
        def boom():
            raise RuntimeError("Task failed")

        self.dag.add_node("A", boom)
        self.dag.add_node("B", lambda: "independent_success")
        self.dag.add_node("C", lambda: "downstream", dependencies=["A"])

        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("A",))
        self.assertEqual(report.succeeded_nodes, ("B",))
        self.assertEqual(report.skipped_nodes, ("C",))

    def test_real_dag_runner_skip_downstream(self) -> None:
        def boom():
            raise RuntimeError("Task failed")

        self.dag.add_node("A", boom)
        self.dag.add_node("B", lambda: "ok")
        self.dag.add_node("C", lambda: "skip_me", dependencies=["A"])

        report = self.dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("A",))
        self.assertEqual(report.succeeded_nodes, ("B",))
        self.assertEqual(report.skipped_nodes, ("C",))

    def test_real_dag_runner_validation_failure(self) -> None:
        self.dag.add_node("A", lambda: 1, dependencies=["missing"])
        with self.assertRaises(NodeNotFoundError):
            self.dagrunner.run()

    def test_real_dag_runner_empty(self) -> None:
        report = self.dagrunner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.critical_path, ())

    def test_real_dag_remove_node_standalone_no_scheduler(self) -> None:
        dag = DAG()
        dag.add_node("X", lambda: 1)
        dag.remove_node("X")
        self.assertFalse(dag.has_node("X"))

    def test_real_wave_scheduler_sync_states_deleted_node(self) -> None:
        self.wavescheduler._states["orphaned"] = NodeState.READY
        self.wavescheduler.next_wave()
        self.assertNotIn("orphaned", self.wavescheduler._states)

    def test_real_wave_scheduler_mark_failed_diamond_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2, dependencies=["A"])
        self.dag.add_node("C", lambda: 3, dependencies=["A"])
        self.dag.add_node("D", lambda: 4, dependencies=["B", "C"])
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("D"), NodeState.SKIPPED)

    def test_real_wave_scheduler_is_finished_blocked_pending(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.wavescheduler._states["A"] = NodeState.PENDING
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
