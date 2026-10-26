"""Pretense state machine, synthesized fakes, and verification suite for dag_engine_lite_impl.

Specifications:
- benchmark_3/parts/dag_engine_lite/low/dag_engine_lite.pyi
- benchmark_3/parts/dag_engine_lite/low/dag_engine_lite_impl.pyi
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

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
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DAGEngineLiteImplState:
    """Canonical model state tracking DAG definitions, scheduler progress, and execution results."""
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)


def _pure_find_cycle(state: DAGEngineLiteImplState) -> Tuple[str, ...]:
    """Finds a directed cycle within the registered nodes if one exists."""
    visited: Dict[str, int] = {}
    parent: Dict[str, str] = {}
    cycle_nodes: List[str] = []

    def dfs(u: str) -> bool:
        visited[u] = 1
        for v in sorted(state.downstream.get(u, set())):
            if v not in state.nodes:
                continue
            if visited.get(v, 0) == 1:
                cycle: List[str] = [v]
                curr = u
                while curr != v and curr in parent:
                    cycle.append(curr)
                    curr = parent[curr]
                cycle.append(v)
                cycle.reverse()
                cycle_nodes.extend(cycle)
                return True
            if visited.get(v, 0) == 0:
                parent[v] = u
                if dfs(v):
                    return True
        visited[u] = 2
        return False

    for node in sorted(state.nodes.keys()):
        if visited.get(node, 0) == 0:
            if dfs(node):
                return tuple(cycle_nodes)
    return ()


def _pure_validate(state: DAGEngineLiteImplState) -> None:
    """Validates completeness and acyclicity of the current DAG state."""
    for nid, ndef in state.nodes.items():
        for dep in ndef.dependencies:
            if dep not in state.nodes:
                raise NodeNotFoundError(message=f"Missing dependency: {dep}", node_id=dep)
        for dep in state.upstream.get(nid, set()):
            if dep not in state.nodes:
                raise NodeNotFoundError(message=f"Missing dependency: {dep}", node_id=dep)
    cycle = _pure_find_cycle(state)
    if cycle:
        raise CycleError(message="Directed cycle detected", cycle=cycle)


def _pure_topological_sort(state: DAGEngineLiteImplState) -> List[str]:
    """Computes deterministic topological ordering with priority and lexical tie-breaking."""
    in_degrees: Dict[str, int] = {nid: 0 for nid in state.nodes}
    for nid, deps in state.upstream.items():
        if nid in in_degrees:
            in_degrees[nid] = len([d for d in deps if d in state.nodes])

    ready = [nid for nid, deg in in_degrees.items() if deg == 0]
    ready.sort(key=lambda n: (-state.nodes[n].priority, n))
    result: List[str] = []

    while ready:
        curr = ready.pop(0)
        result.append(curr)
        for down in sorted(state.downstream.get(curr, set())):
            if down in in_degrees:
                in_degrees[down] -= 1
                if in_degrees[down] == 0:
                    ready.append(down)
                    ready.sort(key=lambda n: (-state.nodes[n].priority, n))

    if len(result) != len(state.nodes):
        cycle = _pure_find_cycle(state)
        raise CycleError(message="Cycle detected in DAG", cycle=tuple(cycle))
    return result


def _pure_compute_critical_path(
    state: DAGEngineLiteImplState,
    estimated_durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the graph."""
    if not state.nodes:
        return ([], 0.0)
    order = _pure_topological_sort(state)
    durations = {
        nid: (float(estimated_durations[nid]) if estimated_durations and nid in estimated_durations else 1.0)
        for nid in state.nodes
    }
    earliest: Dict[str, float] = {}
    best_pred: Dict[str, Optional[str]] = {}
    for nid in order:
        ups = [u for u in state.upstream.get(nid, set()) if u in state.nodes]
        if not ups:
            earliest[nid] = durations[nid]
            best_pred[nid] = None
        else:
            best_u = max(ups, key=lambda u: earliest[u])
            earliest[nid] = earliest[best_u] + durations[nid]
            best_pred[nid] = best_u

    max_node = max(order, key=lambda n: earliest[n])
    max_weight = earliest[max_node]
    path: List[str] = []
    curr: Optional[str] = max_node
    while curr is not None:
        path.append(curr)
        curr = best_pred.get(curr)
    path.reverse()
    return (path, max_weight)


def _pure_sync_scheduler(state: DAGEngineLiteImplState) -> None:
    """Synchronizes registered nodes into scheduler tracking state."""
    for nid in state.nodes:
        if nid not in state.node_states:
            ups = [u for u in state.upstream.get(nid, set()) if u in state.nodes]
            state.node_states[nid] = NodeState.READY if len(ups) == 0 else NodeState.PENDING


def _pure_next_wave(state: DAGEngineLiteImplState) -> List[str]:
    """Resolves ready nodes whose upstream dependencies have all succeeded."""
    _pure_sync_scheduler(state)
    ready_candidates: List[str] = []
    for nid, nstate in state.node_states.items():
        if nid not in state.nodes:
            continue
        if nstate == NodeState.READY:
            ups = [u for u in state.upstream.get(nid, set()) if u in state.nodes]
            if all(state.node_states.get(u) == NodeState.SUCCEEDED for u in ups):
                ready_candidates.append(nid)
    ready_candidates.sort(key=lambda n: (-state.nodes[n].priority, n))
    return ready_candidates


def _pure_mark_succeeded(state: DAGEngineLiteImplState, node_id: str) -> None:
    """Marks node succeeded and promotes eligible dependents to ready."""
    state.node_states[node_id] = NodeState.SUCCEEDED
    for down in state.downstream.get(node_id, set()):
        if down in state.nodes and state.node_states.get(down) == NodeState.PENDING:
            ups = [u for u in state.upstream.get(down, set()) if u in state.nodes]
            if all(state.node_states.get(u) == NodeState.SUCCEEDED for u in ups):
                state.node_states[down] = NodeState.READY


def _pure_mark_failed(
    state: DAGEngineLiteImplState,
    node_id: str,
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
) -> None:
    """Marks node failed and propagates failure policy across scheduler state."""
    state.node_states[node_id] = NodeState.FAILED
    terminal_states = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
    if failure_policy == FailurePolicy.FAIL_FAST:
        for nid in list(state.node_states.keys()):
            if nid in state.nodes and state.node_states[nid] not in terminal_states:
                state.node_states[nid] = NodeState.CANCELLED
    elif failure_policy in (FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR):
        queue = list(state.downstream.get(node_id, set()))
        visited = set(queue)
        while queue:
            curr = queue.pop(0)
            if curr in state.nodes and state.node_states.get(curr) not in terminal_states:
                state.node_states[curr] = NodeState.SKIPPED
            for nxt in state.downstream.get(curr, set()):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)


def _pure_is_finished(state: DAGEngineLiteImplState) -> bool:
    """Determines whether scheduler has completed all reachable nodes."""
    _pure_sync_scheduler(state)
    if not state.nodes:
        return True
    if any(state.node_states.get(nid) == NodeState.RUNNING for nid in state.nodes):
        return False
    terminal_states = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
    if all(state.node_states.get(nid) in terminal_states for nid in state.nodes):
        return True
    ready = _pure_next_wave(state)
    if ready:
        return False
    unexecuted = [nid for nid in state.nodes if state.node_states.get(nid) not in terminal_states]
    if not unexecuted:
        return True
    blocked: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for nid in unexecuted:
            if nid not in blocked:
                ups = [u for u in state.upstream.get(nid, set()) if u in state.nodes]
                if any(
                    state.node_states.get(u) in {NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
                    or u in blocked
                    for u in ups
                ):
                    blocked.add(nid)
                    changed = True
    return len(blocked) == len(unexecuted)


def _pure_run(
    state: DAGEngineLiteImplState,
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
) -> DAGRunReport:
    """Simulates complete sequential execution of the DAG."""
    _pure_validate(state)
    _pure_sync_scheduler(state)
    while not _pure_is_finished(state):
        wave = _pure_next_wave(state)
        if not wave:
            break
        for nid in wave:
            state.node_states[nid] = NodeState.RUNNING
            ndef = state.nodes[nid]
            success = False
            last_err: Optional[Exception] = None
            ret_val: Any = None
            attempts = 0
            for attempt in range(ndef.retries + 1):
                attempts = attempt
                try:
                    ret_val = ndef.action()
                    success = True
                    break
                except Exception as exc:
                    last_err = exc
            if success:
                _pure_mark_succeeded(state, nid)
                state.results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.SUCCEEDED,
                    value=ret_val,
                    duration_seconds=0.01,
                    retries_attempted=attempts,
                )
            else:
                _pure_mark_failed(state, nid, failure_policy=failure_policy)
                state.results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.FAILED,
                    error=last_err,
                    duration_seconds=0.01,
                    retries_attempted=attempts,
                )
                if failure_policy == FailurePolicy.FAIL_FAST:
                    break

    for nid, nstate in state.node_states.items():
        if nid in state.nodes and nid not in state.results:
            state.results[nid] = NodeResult(node_id=nid, state=nstate)

    path, _ = _pure_compute_critical_path(state)
    succeeded = tuple(nid for nid, res in state.results.items() if res.state == NodeState.SUCCEEDED)
    failed = tuple(nid for nid, res in state.results.items() if res.state == NodeState.FAILED)
    skipped = tuple(nid for nid, res in state.results.items() if res.state == NodeState.SKIPPED)
    cancelled = tuple(nid for nid, res in state.results.items() if res.state == NodeState.CANCELLED)

    return DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded,
        failed_nodes=failed,
        skipped_nodes=skipped,
        cancelled_nodes=cancelled,
        wall_clock_seconds=0.01,
        critical_path=tuple(path),
        results=dict(state.results),
    )


proto = StateMachineProto[DAGEngineLiteImplState]()


# ------------------------------------------------------------------------------
# DAG Transitions
# ------------------------------------------------------------------------------

@proto.transition(DAG.add_node)
def add_node(): pass

@add_node.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    action: Any | NotBoundType = NotBound,
    dependencies: Any | NotBoundType = NotBound,
    priority: Any | NotBoundType = NotBound,
    retries: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_node_id = node_id if not isinstance(node_id, NotBoundType) else f"node_{len(state.nodes) + 1}"
    resolved_action = action if not isinstance(action, NotBoundType) else (lambda: None)
    resolved_deps = dependencies if not isinstance(dependencies, NotBoundType) else None
    resolved_priority = priority if not isinstance(priority, NotBoundType) else 0
    resolved_retries = retries if not isinstance(retries, NotBoundType) else 0
    return (resolved_node_id, resolved_action, resolved_deps, resolved_priority, resolved_retries)

@add_node.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any = None,
    priority: Any = 0,
    retries: Any = 0,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@add_node.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any = None,
    priority: Any = 0,
    retries: Any = 0,
    result: Any = None,
) -> None:
    deps_set = frozenset(dependencies) if dependencies is not None else frozenset()
    node_def = NodeDefinition(
        node_id=str(node_id),
        action=action,
        dependencies=deps_set,
        priority=int(priority) if isinstance(priority, int) else 0,
        retries=int(retries) if isinstance(retries, int) else 0,
    )
    nid = str(node_id)
    state.nodes[nid] = node_def
    if nid not in state.upstream:
        state.upstream[nid] = set()
    if nid not in state.downstream:
        state.downstream[nid] = set()
    for dep in deps_set:
        state.upstream[nid].add(dep)
        if dep not in state.downstream:
            state.downstream[dep] = set()
        state.downstream[dep].add(nid)
    if nid not in state.node_states:
        state.node_states[nid] = NodeState.READY if len(deps_set) == 0 else NodeState.PENDING


@proto.transition(DAG.add_edge)
def add_edge(): pass

@add_edge.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    u = upstream_id if not isinstance(upstream_id, NotBoundType) else (nodes[0] if len(nodes) > 0 else "node_u")
    d = downstream_id if not isinstance(downstream_id, NotBoundType) else (nodes[1] if len(nodes) > 1 else "node_d")
    return (u, d)

@add_edge.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    u_id = str(upstream_id)
    d_id = str(downstream_id)
    if u_id not in state.nodes or d_id not in state.nodes:
        missing = u_id if u_id not in state.nodes else d_id
        return Raised(NodeNotFoundError(message=f"Node not found: {missing}", node_id=missing))
    return Value(None)

@add_edge.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any = None,
) -> None:
    u_id = str(upstream_id)
    d_id = str(downstream_id)
    if u_id in state.nodes and d_id in state.nodes:
        state.upstream.setdefault(d_id, set()).add(u_id)
        state.downstream.setdefault(u_id, set()).add(d_id)
        if state.node_states.get(d_id) == NodeState.READY and state.node_states.get(u_id) != NodeState.SUCCEEDED:
            state.node_states[d_id] = NodeState.PENDING


@proto.transition(DAG.remove_node)
def remove_node(): pass

@remove_node.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@remove_node.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node not found: {nid}", node_id=nid))
    return Value(None)

@remove_node.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    nid = str(node_id)
    state.nodes.pop(nid, None)
    state.node_states.pop(nid, None)
    state.results.pop(nid, None)
    ups = state.upstream.pop(nid, set())
    for u in ups:
        if u in state.downstream:
            state.downstream[u].discard(nid)
    downs = state.downstream.pop(nid, set())
    for d in downs:
        if d in state.upstream:
            state.upstream[d].discard(nid)


@proto.transition(DAG.has_node)
def has_node(): pass

@has_node.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@has_node.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(str(node_id) in state.nodes)

@has_node.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.get_node)
def get_node(): pass

@get_node.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@get_node.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node not found: {nid}", node_id=nid))
    return Value(state.nodes[nid])

@get_node.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.get_dependencies)
def get_dependencies(): pass

@get_dependencies.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@get_dependencies.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node not found: {nid}", node_id=nid))
    return Value(set(state.upstream.get(nid, set())))

@get_dependencies.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.get_dependents)
def get_dependents(): pass

@get_dependents.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@get_dependents.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node not found: {nid}", node_id=nid))
    return Value(set(state.downstream.get(nid, set())))

@get_dependents.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.all_nodes)
def all_nodes(): pass

@all_nodes.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@all_nodes.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(set(state.nodes.keys()))

@all_nodes.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.validate)
def validate(): pass

@validate.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@validate.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    try:
        _pure_validate(state)
        return Value(None)
    except (NodeNotFoundError, CycleError) as exc:
        return Raised(exc)

@validate.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.topological_sort)
def topological_sort(): pass

@topological_sort.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@topological_sort.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    try:
        order = _pure_topological_sort(state)
        return Value(order)
    except CycleError as exc:
        return Raised(exc)

@topological_sort.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.find_roots)
def find_roots(): pass

@find_roots.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@find_roots.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    roots = {nid for nid in state.nodes if len(state.upstream.get(nid, set())) == 0}
    return Value(roots)

@find_roots.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.find_leaves)
def find_leaves(): pass

@find_leaves.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@find_leaves.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    leaves = {nid for nid in state.nodes if len(state.downstream.get(nid, set())) == 0}
    return Value(leaves)

@find_leaves.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(DAG.compute_critical_path)
def compute_critical_path(): pass

@compute_critical_path.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    dur = estimated_durations if not isinstance(estimated_durations, NotBoundType) else None
    return (dur,)

@compute_critical_path.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    estimated_durations: Any = None,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    try:
        path, weight = _pure_compute_critical_path(state, estimated_durations)
        return Value((path, weight))
    except CycleError as exc:
        return Raised(exc)

@compute_critical_path.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    estimated_durations: Any = None,
    result: Any = None,
) -> None:
    pass


# ------------------------------------------------------------------------------
# WaveScheduler Transitions
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.next_wave)
def next_wave(): pass

@next_wave.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@next_wave.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(_pure_next_wave(state))

@next_wave.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    _pure_sync_scheduler(state)


@proto.transition(WaveScheduler.mark_running)
def mark_running(): pass

@mark_running.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_1")
    return (nid,)

@mark_running.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@mark_running.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    state.node_states[str(node_id)] = NodeState.RUNNING


@proto.transition(WaveScheduler.mark_succeeded)
def mark_succeeded(): pass

@mark_succeeded.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_1")
    return (nid,)

@mark_succeeded.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@mark_succeeded.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    _pure_mark_succeeded(state, str(node_id))


@proto.transition(WaveScheduler.mark_failed)
def mark_failed(): pass

@mark_failed.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_1")
    fp = failure_policy if not isinstance(failure_policy, NotBoundType) else FailurePolicy.FAIL_FAST
    return (nid, fp)

@mark_failed.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    failure_policy: Any = FailurePolicy.FAIL_FAST,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(None)

@mark_failed.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    failure_policy: Any = FailurePolicy.FAIL_FAST,
    result: Any = None,
) -> None:
    fp = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    _pure_mark_failed(state, str(node_id), failure_policy=fp)


@proto.transition(WaveScheduler.is_finished)
def is_finished(): pass

@is_finished.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@is_finished.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    return Value(_pure_is_finished(state))

@is_finished.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    _pure_sync_scheduler(state)


@proto.transition(WaveScheduler.get_state)
def get_state(): pass

@get_state.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@get_state.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node not found: {nid}", node_id=nid))
    if nid not in state.node_states:
        _pure_sync_scheduler(state)
    return Value(state.node_states[nid])

@get_state.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    node_id: Any,
    result: Any = None,
) -> None:
    pass


@proto.transition(WaveScheduler.get_all_states)
def get_all_states(): pass

@get_all_states.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()

@get_all_states.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    _pure_sync_scheduler(state)
    return Value({nid: state.node_states[nid] for nid in state.nodes if nid in state.node_states})

@get_all_states.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    result: Any = None,
) -> None:
    _pure_sync_scheduler(state)


# ------------------------------------------------------------------------------
# DAGRunner Transitions
# ------------------------------------------------------------------------------

@proto.transition(DAGRunner.run)
def run(): pass

@run.arguments
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    fp = failure_policy if not isinstance(failure_policy, NotBoundType) else FailurePolicy.FAIL_FAST
    return (fp,)

@run.returns
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    failure_policy: Any = FailurePolicy.FAIL_FAST,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        if isinstance(outcome, DAGRunReport):
            return Value(outcome)
        return outcome if isinstance(outcome, Outcome) else Value(outcome)
    try:
        report = _pure_run(state, failure_policy=failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST)
        return Value(report)
    except DAGError as exc:
        return Raised(exc)

@run.provide
def _(
    state: DAGEngineLiteImplState,
    this: Any,
    failure_policy: Any = FailurePolicy.FAIL_FAST,
    result: Any = None,
) -> None:
    pass


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_dag_engine_fakes(state: DAGEngineLiteImplState) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = proto.make_state_machine(state)
    return (sm.as_fake(DAG), sm.as_fake(WaveScheduler), sm.as_fake(DAGRunner))


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestDAGEngineLiteImplUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to state machine specification."""

    def setUp(self) -> None:
        self.state = DAGEngineLiteImplState()
        self.dag, self.scheduler, self.runner = make_dag_engine_fakes(self.state)

    def test_dag_add_and_get_node(self) -> None:
        action = lambda: "val1"
        self.dag.add_node("n1", action, priority=10, retries=2)
        self.assertTrue(self.dag.has_node("n1"))
        self.assertEqual(self.dag.all_nodes(), {"n1"})
        node_def = self.dag.get_node("n1")
        self.assertEqual(node_def.node_id, "n1")
        self.assertEqual(node_def.priority, 10)
        self.assertEqual(node_def.retries, 2)
        self.assertEqual(self.dag.get_dependencies("n1"), set())
        self.assertEqual(self.dag.get_dependents("n1"), set())

    def test_dag_add_edge_and_dependencies(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_dag_add_edge_missing_node_raises(self) -> None:
        self.dag.add_node("a", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "a")

    def test_dag_remove_node(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.dag.add_edge("a", "b")
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertTrue(self.dag.has_node("b"))
        self.assertEqual(self.dag.get_dependencies("b"), set())
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("a")

    def test_dag_remove_node_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("nonexistent")

    def test_dag_validate_missing_dependency_raises(self) -> None:
        self.dag.add_node("child", lambda: None, dependencies=["parent_missing"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_dag_validate_cycle_raises(self) -> None:
        self.dag.add_node("n1", lambda: None)
        self.dag.add_node("n2", lambda: None)
        self.dag.add_edge("n1", "n2")
        self.dag.add_edge("n2", "n1")
        with self.assertRaises(CycleError):
            self.dag.validate()

    def test_dag_topological_sort_priority_tie_breaking(self) -> None:
        self.dag.add_node("root_low", lambda: None, priority=1)
        self.dag.add_node("root_high", lambda: None, priority=5)
        self.dag.add_node("root_mid", lambda: None, priority=3)
        order = self.dag.topological_sort()
        self.assertEqual(order, ["root_high", "root_mid", "root_low"])

    def test_dag_topological_sort_cycle_raises(self) -> None:
        self.dag.add_node("c1", lambda: None)
        self.dag.add_node("c2", lambda: None)
        self.dag.add_edge("c1", "c2")
        self.dag.add_edge("c2", "c1")
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_dag_find_roots_and_leaves(self) -> None:
        self.dag.add_node("r1", lambda: None)
        self.dag.add_node("r2", lambda: None)
        self.dag.add_node("leaf", lambda: None)
        self.dag.add_edge("r1", "leaf")
        self.dag.add_edge("r2", "leaf")
        self.assertEqual(self.dag.find_roots(), {"r1", "r2"})
        self.assertEqual(self.dag.find_leaves(), {"leaf"})

    def test_dag_compute_critical_path(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.dag.add_edge("a", "b")
        path, weight = self.dag.compute_critical_path({"a": 2.5, "b": 1.5})
        self.assertEqual(path, ["a", "b"])
        self.assertAlmostEqual(weight, 4.0)

    def test_scheduler_lifecycle_and_promotion(self) -> None:
        self.dag.add_node("root", lambda: None)
        self.dag.add_node("child", lambda: None, dependencies=["root"])
        wave1 = self.scheduler.next_wave()
        self.assertEqual(wave1, ["root"])
        self.assertEqual(self.scheduler.get_state("root"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("child"), NodeState.PENDING)

        self.scheduler.mark_running("root")
        self.assertEqual(self.scheduler.get_state("root"), NodeState.RUNNING)

        self.scheduler.mark_succeeded("root")
        self.assertEqual(self.scheduler.get_state("root"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.get_state("child"), NodeState.READY)

        wave2 = self.scheduler.next_wave()
        self.assertEqual(wave2, ["child"])
        self.scheduler.mark_succeeded("child")
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self.dag.add_node("failed_node", lambda: None)
        self.dag.add_node("other_node", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("failed_node", failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("failed_node"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("other_node"), NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("p", lambda: None)
        self.dag.add_node("c", lambda: None, dependencies=["p"])
        self.dag.add_node("indep", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("p", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("p"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("indep"), NodeState.READY)

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        self.dag.add_node("p", lambda: None)
        self.dag.add_node("c", lambda: None, dependencies=["p"])
        self.dag.add_node("indep", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("p", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("p"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("indep"), NodeState.READY)

    def test_scheduler_is_finished_empty(self) -> None:
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_get_all_states(self) -> None:
        self.dag.add_node("n1", lambda: None)
        self.dag.add_node("n2", lambda: None)
        states = self.scheduler.get_all_states()
        self.assertEqual(set(states.keys()), {"n1", "n2"})
        self.assertEqual(states["n1"], NodeState.READY)
        self.assertEqual(states["n2"], NodeState.READY)

    def test_runner_run_success(self) -> None:
        recorded: List[str] = []
        self.dag.add_node("step1", lambda: recorded.append("step1"))
        self.dag.add_node("step2", lambda: recorded.append("step2"), dependencies=["step1"])
        report = self.runner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"step1", "step2"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())

    def test_dag_get_dependencies_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")

    def test_dag_get_dependents_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_dag_compute_critical_path_empty(self) -> None:
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_scheduler_get_state_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("nonexistent")

    def test_scheduler_is_finished_running_nodes(self) -> None:
        self.dag.add_node("r1", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_running("r1")
        self.assertFalse(self.scheduler.is_finished())

    def test_scheduler_mark_failed_transitive_multi_hop_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["B"])
        self.dag.add_node("D", lambda: None, dependencies=["C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

    def test_scheduler_mark_failed_transitive_multi_hop_continue_on_error(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["B"])
        self.dag.add_node("D", lambda: None, dependencies=["C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

    def test_scheduler_mark_failed_diamond_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["A"])
        self.dag.add_node("D", lambda: None, dependencies=["B", "C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

        # Branch failure in diamond
        self.dag.add_node("A2", lambda: None)
        self.dag.add_node("B2", lambda: None, dependencies=["A2"])
        self.dag.add_node("C2", lambda: None, dependencies=["A2"])
        self.dag.add_node("D2", lambda: None, dependencies=["B2", "C2"])
        self.scheduler.next_wave()
        self.scheduler.mark_succeeded("A2")
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)
        self.scheduler.mark_failed("B2", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("D2"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)

    def test_scheduler_mark_failed_diamond_continue_on_error(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["A"])
        self.dag.add_node("D", lambda: None, dependencies=["B", "C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

        # Branch failure in diamond under CONTINUE_ON_ERROR
        self.dag.add_node("A2", lambda: None)
        self.dag.add_node("B2", lambda: None, dependencies=["A2"])
        self.dag.add_node("C2", lambda: None, dependencies=["A2"])
        self.dag.add_node("D2", lambda: None, dependencies=["B2", "C2"])
        self.scheduler.next_wave()
        self.scheduler.mark_succeeded("A2")
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)
        self.scheduler.mark_failed("B2", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("D2"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)

    def test_scheduler_is_finished_unexecuted_non_terminal_blocked(self) -> None:
        self.dag.add_node("p", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("p", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.dag.add_node("c_blocked", lambda: None, dependencies=["p"])
        self.dag.add_node("c_blocked2", lambda: None, dependencies=["c_blocked"])
        self.assertEqual(self.scheduler.get_state("c_blocked"), NodeState.PENDING)
        self.assertEqual(self.scheduler.get_state("c_blocked2"), NodeState.PENDING)
        self.assertTrue(self.scheduler.is_finished())
        # Adding an unblocked node should make is_finished False
        self.dag.add_node("indep_ready", lambda: None)
        self.assertFalse(self.scheduler.is_finished())

    def test_runner_run_with_retries_and_failure(self) -> None:
        attempts: List[int] = [0]
        def failing_action() -> None:
            attempts[0] += 1
            raise RuntimeError("Intentional failure")

        self.dag.add_node("fail_step", failing_action, retries=2)
        self.dag.add_node("cancelled_step", lambda: None, dependencies=["fail_step"])
        report = self.runner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.failed_nodes), {"fail_step"})
        self.assertEqual(set(report.cancelled_nodes), {"cancelled_step"})
        self.assertIn("fail_step", report.results)
        self.assertEqual(report.results["fail_step"].retries_attempted, 2)
        self.assertEqual(report.results["fail_step"].state, NodeState.FAILED)
        self.assertEqual(report.results["cancelled_step"].state, NodeState.CANCELLED)

    def test_runner_run_failing_skip_downstream(self) -> None:
        self.dag.add_node("fail_step", lambda: (_ for _ in ()).throw(RuntimeError("fail")), retries=1)
        self.dag.add_node("dep_step", lambda: None, dependencies=["fail_step"])
        self.dag.add_node("indep", lambda: "ok")
        report = self.runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(set(report.succeeded_nodes), {"indep"})
        self.assertEqual(set(report.failed_nodes), {"fail_step"})
        self.assertEqual(set(report.skipped_nodes), {"dep_step"})
        self.assertEqual(report.results["fail_step"].retries_attempted, 1)

    def test_runner_run_failing_continue_on_error(self) -> None:
        self.dag.add_node("fail_step", lambda: (_ for _ in ()).throw(RuntimeError("fail")), retries=0)
        self.dag.add_node("dep_step", lambda: None, dependencies=["fail_step"])
        self.dag.add_node("indep", lambda: "ok")
        report = self.runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(set(report.succeeded_nodes), {"indep"})
        self.assertEqual(set(report.failed_nodes), {"fail_step"})
        self.assertEqual(set(report.skipped_nodes), {"dep_step"})


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestDAGEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_dag_add_and_retrieve_nodes(self) -> None:
        self.dag.add_node("node_a", lambda: 42, priority=5, retries=1)
        self.assertTrue(self.dag.has_node("node_a"))
        self.assertFalse(self.dag.has_node("nonexistent"))
        node_def = self.dag.get_node("node_a")
        self.assertEqual(node_def.node_id, "node_a")
        self.assertEqual(node_def.priority, 5)
        self.assertEqual(node_def.retries, 1)
        self.assertEqual(self.dag.all_nodes(), {"node_a"})

    def test_real_dag_edges_and_dependencies(self) -> None:
        self.dag.add_node("upstream", lambda: None)
        self.dag.add_node("downstream", lambda: None)
        self.dag.add_edge("upstream", "downstream")
        self.assertEqual(self.dag.get_dependencies("downstream"), {"upstream"})
        self.assertEqual(self.dag.get_dependents("upstream"), {"downstream"})

    def test_real_dag_edge_missing_raises(self) -> None:
        self.dag.add_node("existing", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("existing", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "existing")

    def test_real_dag_remove_node(self) -> None:
        self.dag.add_node("r_a", lambda: None)
        self.dag.add_node("r_b", lambda: None)
        self.dag.add_edge("r_a", "r_b")
        self.dag.remove_node("r_a")
        self.assertFalse(self.dag.has_node("r_a"))
        self.assertEqual(self.dag.get_dependencies("r_b"), set())
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("r_a")

    def test_real_dag_remove_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")

    def test_real_dag_validate_and_cycles(self) -> None:
        self.dag.add_node("valid_root", lambda: None)
        self.dag.validate()

        self.dag.add_node("missing_dep_node", lambda: None, dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

        self.dag.remove_node("missing_dep_node")
        self.dag.add_node("c_1", lambda: None)
        self.dag.add_node("c_2", lambda: None)
        self.dag.add_edge("c_1", "c_2")
        self.dag.add_edge("c_2", "c_1")
        with self.assertRaises(CycleError):
            self.dag.validate()

    def test_real_dag_topological_sort(self) -> None:
        self.dag.add_node("low", lambda: None, priority=0)
        self.dag.add_node("high", lambda: None, priority=10)
        order = self.dag.topological_sort()
        self.assertEqual(order, ["high", "low"])

    def test_real_dag_roots_leaves_and_critical_path(self) -> None:
        self.dag.add_node("start", lambda: None)
        self.dag.add_node("end", lambda: None)
        self.dag.add_edge("start", "end")
        self.assertEqual(self.dag.find_roots(), {"start"})
        self.assertEqual(self.dag.find_leaves(), {"end"})
        path, weight = self.dag.compute_critical_path({"start": 0.05, "end": 0.05})
        self.assertEqual(path, ["start", "end"])
        self.assertAlmostEqual(weight, 0.10)

    def test_real_scheduler_waves_and_transitions(self) -> None:
        self.dag.add_node("w1", lambda: None)
        self.dag.add_node("w2", lambda: None, dependencies=["w1"])
        wave = self.scheduler.next_wave()
        self.assertEqual(wave, ["w1"])
        self.scheduler.mark_running("w1")
        self.assertEqual(self.scheduler.get_state("w1"), NodeState.RUNNING)
        self.scheduler.mark_succeeded("w1")
        self.assertEqual(self.scheduler.get_state("w1"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.get_state("w2"), NodeState.READY)
        wave2 = self.scheduler.next_wave()
        self.assertEqual(wave2, ["w2"])
        self.scheduler.mark_succeeded("w2")
        self.assertTrue(self.scheduler.is_finished())

    def test_real_scheduler_failure_policies(self) -> None:
        self.dag.add_node("failed_ff", lambda: None)
        self.dag.add_node("pending_ff", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("failed_ff", failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("failed_ff"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("pending_ff"), NodeState.CANCELLED)

    def test_real_scheduler_finished_and_states(self) -> None:
        self.assertTrue(self.scheduler.is_finished())
        self.dag.add_node("single", lambda: None)
        self.assertFalse(self.scheduler.is_finished())
        states = self.scheduler.get_all_states()
        self.assertIn("single", states)
        self.assertEqual(states["single"], NodeState.READY)

    def test_real_runner_run_success_and_failure(self) -> None:
        self.dag.add_node("task1", lambda: "ok1")
        self.dag.add_node("task2", lambda: "ok2", dependencies=["task1"])
        report = self.runner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"task1", "task2"})
        self.assertEqual(report.failed_nodes, ())

    def test_real_dag_get_dependencies_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")

    def test_real_dag_get_dependents_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_real_dag_topological_sort_cycle_raises(self) -> None:
        self.dag.add_node("c_a", lambda: None)
        self.dag.add_node("c_b", lambda: None)
        self.dag.add_edge("c_a", "c_b")
        self.dag.add_edge("c_b", "c_a")
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_real_dag_compute_critical_path_empty(self) -> None:
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_real_scheduler_get_state_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("nonexistent")

    def test_real_scheduler_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("p", lambda: None)
        self.dag.add_node("c", lambda: None, dependencies=["p"])
        self.dag.add_node("indep", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("p", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("p"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("indep"), NodeState.READY)

    def test_real_scheduler_mark_failed_continue_on_error(self) -> None:
        self.dag.add_node("p", lambda: None)
        self.dag.add_node("c", lambda: None, dependencies=["p"])
        self.dag.add_node("indep", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("p", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("p"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("indep"), NodeState.READY)

    def test_real_scheduler_is_finished_running_nodes(self) -> None:
        self.dag.add_node("r_running", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_running("r_running")
        self.assertFalse(self.scheduler.is_finished())

    def test_real_scheduler_mark_failed_transitive_multi_hop_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["B"])
        self.dag.add_node("D", lambda: None, dependencies=["C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

    def test_real_scheduler_mark_failed_transitive_multi_hop_continue_on_error(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["B"])
        self.dag.add_node("D", lambda: None, dependencies=["C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

    def test_real_scheduler_mark_failed_diamond_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["A"])
        self.dag.add_node("D", lambda: None, dependencies=["B", "C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

        # Branch failure in diamond
        self.dag.add_node("A2", lambda: None)
        self.dag.add_node("B2", lambda: None, dependencies=["A2"])
        self.dag.add_node("C2", lambda: None, dependencies=["A2"])
        self.dag.add_node("D2", lambda: None, dependencies=["B2", "C2"])
        self.scheduler.next_wave()
        self.scheduler.mark_succeeded("A2")
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)
        self.scheduler.mark_failed("B2", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("D2"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)

    def test_real_scheduler_mark_failed_diamond_continue_on_error(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["A"])
        self.dag.add_node("D", lambda: None, dependencies=["B", "C"])
        self.dag.add_node("X", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("A", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("D"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("X"), NodeState.READY)

        # Branch failure in diamond under CONTINUE_ON_ERROR
        self.dag.add_node("A2", lambda: None)
        self.dag.add_node("B2", lambda: None, dependencies=["A2"])
        self.dag.add_node("C2", lambda: None, dependencies=["A2"])
        self.dag.add_node("D2", lambda: None, dependencies=["B2", "C2"])
        self.scheduler.next_wave()
        self.scheduler.mark_succeeded("A2")
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.READY)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)
        self.scheduler.mark_failed("B2", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("B2"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("D2"), NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("C2"), NodeState.READY)

    def test_real_scheduler_is_finished_unexecuted_non_terminal_blocked(self) -> None:
        self.dag.add_node("p", lambda: None)
        self.scheduler.next_wave()
        self.scheduler.mark_failed("p", failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.dag.add_node("c_blocked", lambda: None, dependencies=["p"])
        self.dag.add_node("c_blocked2", lambda: None, dependencies=["c_blocked"])
        self.assertEqual(self.scheduler.get_state("c_blocked"), NodeState.PENDING)
        self.assertEqual(self.scheduler.get_state("c_blocked2"), NodeState.PENDING)
        self.assertTrue(self.scheduler.is_finished())
        # Adding an unblocked node should make is_finished False
        self.dag.add_node("indep_ready", lambda: None)
        self.assertFalse(self.scheduler.is_finished())

    def test_real_runner_run_failing_with_retries_fail_fast(self) -> None:
        attempts: List[int] = [0]
        def failing_action() -> None:
            attempts[0] += 1
            raise RuntimeError("Intentional error")

        self.dag.add_node("fail_step", failing_action, retries=2)
        self.dag.add_node("cancelled_step", lambda: None, dependencies=["fail_step"])
        report = self.runner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.failed_nodes), {"fail_step"})
        self.assertEqual(set(report.cancelled_nodes), {"cancelled_step"})
        self.assertEqual(report.results["fail_step"].retries_attempted, 2)
        self.assertEqual(report.results["fail_step"].state, NodeState.FAILED)

    def test_real_runner_run_failing_with_skip_downstream(self) -> None:
        self.dag.add_node("fail_step", lambda: (_ for _ in ()).throw(RuntimeError("fail")), retries=1)
        self.dag.add_node("dep_step", lambda: None, dependencies=["fail_step"])
        self.dag.add_node("indep", lambda: "ok")
        report = self.runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(set(report.succeeded_nodes), {"indep"})
        self.assertEqual(set(report.failed_nodes), {"fail_step"})
        self.assertEqual(set(report.skipped_nodes), {"dep_step"})
        self.assertEqual(report.results["fail_step"].retries_attempted, 1)

    def test_real_runner_run_failing_with_continue_on_error(self) -> None:
        self.dag.add_node("fail_step", lambda: (_ for _ in ()).throw(RuntimeError("fail")), retries=0)
        self.dag.add_node("dep_step", lambda: None, dependencies=["fail_step"])
        self.dag.add_node("indep", lambda: "ok")
        report = self.runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(set(report.succeeded_nodes), {"indep"})
        self.assertEqual(set(report.failed_nodes), {"fail_step"})
        self.assertEqual(set(report.skipped_nodes), {"dep_step"})

    def test_real_fake_parity(self) -> None:
        state = DAGEngineLiteImplState()
        fake_dag, fake_sched, fake_runner = make_dag_engine_fakes(state)
        self.dag.add_node("node_p", lambda: None, priority=2)
        fake_dag.add_node("node_p", lambda: None, priority=2)
        self.assertEqual(self.dag.has_node("node_p"), fake_dag.has_node("node_p"))
        self.assertEqual(self.dag.all_nodes(), fake_dag.all_nodes())
        real_def = self.dag.get_node("node_p")
        fake_def = fake_dag.get_node("node_p")
        self.assertEqual(real_def.node_id, fake_def.node_id)
        self.assertEqual(real_def.priority, fake_def.priority)


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class DAGEngineLiteImplSUT:
    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self.dag, self.scheduler, self.runner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> DAGEngineLiteImplSUT:
    return DAGEngineLiteImplSUT()


DAGEngineLiteImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DAGEngineLiteImplState,
    name="DAGEngineLiteImplFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T21:26:31Z
# LAST_CHANGED: 2026-10-26T21:25:42Z
# CHANGE: Add comprehensive unit and real implementation test coverage for WaveScheduler.mark_failed transitive propagation across multi-hop and diamond graphs under SKIP_DOWNSTREAM and CONTINUE_ON_ERROR, and verify WaveScheduler.is_finished completion when unexecuted nodes remain non-terminal while blocked by failed dependencies
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T21:26:31Z
# PRETENSE_QA_AUDIT: 2026-10-26T21:26:05Z
# --- END CLEANROOM METADATA ---
