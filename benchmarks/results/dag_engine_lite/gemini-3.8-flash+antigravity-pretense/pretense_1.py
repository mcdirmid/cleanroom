"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
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
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
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
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    initialized: bool = True


def _detect_cycle(state: DagEngineLiteState) -> Optional[Tuple[str, ...]]:
    """Detects cycles in the state graph using DFS recursion stack."""
    visited: Set[str] = set()
    rec_stack: List[str] = []

    def dfs(node: str) -> Optional[List[str]]:
        visited.add(node)
        rec_stack.append(node)
        for neighbor in sorted(state.downstream.get(node, set())):
            if neighbor not in state.nodes:
                continue
            if neighbor not in visited:
                c = dfs(neighbor)
                if c is not None:
                    return c
            elif neighbor in rec_stack:
                idx = rec_stack.index(neighbor)
                return rec_stack[idx:] + [neighbor]
        rec_stack.pop()
        return None

    for node in sorted(state.nodes.keys()):
        if node not in visited:
            c = dfs(node)
            if c is not None:
                return tuple(c)
    return None


def _compute_topological_sort(state: DagEngineLiteState) -> List[str]:
    """Computes deterministic topological ordering by priority descending, then id ascending."""
    in_degree: Dict[str, int] = {
        node: len([u for u in state.upstream.get(node, set()) if u in state.nodes])
        for node in state.nodes
    }
    ready = [node for node, deg in in_degree.items() if deg == 0]
    ready.sort(key=lambda n: (-state.nodes[n].priority, n))
    result: List[str] = []

    while ready:
        curr = ready.pop(0)
        result.append(curr)
        for down in sorted(state.downstream.get(curr, set())):
            if down in in_degree:
                in_degree[down] -= 1
                if in_degree[down] == 0:
                    ready.append(down)
                    ready.sort(key=lambda n: (-state.nodes[n].priority, n))
    return result


def _compute_critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    """Computes the critical path sequence and cumulative duration."""
    if not state.nodes:
        return ([], 0.0)
    topo = _compute_topological_sort(state)
    durations: Dict[str, float] = {}
    for n in state.nodes:
        if estimated_durations and n in estimated_durations:
            durations[n] = float(estimated_durations[n])
        else:
            durations[n] = 1.0

    earliest: Dict[str, float] = {}
    predecessor: Dict[str, Optional[str]] = {}

    for node in topo:
        up = [u for u in state.upstream.get(node, set()) if u in state.nodes]
        if not up:
            earliest[node] = durations[node]
            predecessor[node] = None
        else:
            best_p = max(up, key=lambda p: earliest.get(p, 0.0))
            earliest[node] = earliest[best_p] + durations[node]
            predecessor[node] = best_p

    if not earliest:
        return ([], 0.0)

    best_terminal = max(earliest.keys(), key=lambda n: (earliest[n], n))
    total_dur = earliest[best_terminal]

    path: List[str] = []
    curr: Optional[str] = best_terminal
    while curr is not None:
        path.append(curr)
        curr = predecessor[curr]
    path.reverse()
    return (path, total_dur)


def _simulate_run(
    state: DagEngineLiteState,
    failure_policy: FailurePolicy,
) -> Tuple[DAGRunReport, Dict[str, NodeState], Dict[str, NodeResult[Any]]]:
    """Simulates wave execution of the DAG, applying retries and failure policies."""
    if not state.nodes:
        report = DAGRunReport(
            total_nodes=0,
            succeeded_nodes=(),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=(),
            results={},
        )
        return report, {}, {}

    for node_id, defn in state.nodes.items():
        for dep in defn.dependencies:
            if dep not in state.nodes:
                raise NodeNotFoundError(message=f"Dependency {dep} not found", node_id=dep)
    cycle = _detect_cycle(state)
    if cycle:
        raise CycleError(message=f"Cycle detected: {cycle}", cycle=cycle)

    crit_path, _ = _compute_critical_path(state, None)
    sim_states: Dict[str, NodeState] = {}
    for n in state.nodes:
        if n in state.states:
            sim_states[n] = state.states[n]
        else:
            up = [u for u in state.upstream.get(n, set()) if u in state.nodes]
            sim_states[n] = NodeState.READY if not up else NodeState.PENDING

    sim_results: Dict[str, NodeResult[Any]] = dict(state.results)

    while True:
        ready: List[str] = []
        for nid in state.nodes:
            if sim_states.get(nid) == NodeState.READY:
                up = [u for u in state.upstream.get(nid, set()) if u in state.nodes]
                if all(sim_states.get(u) == NodeState.SUCCEEDED for u in up):
                    ready.append(nid)
        if not ready:
            break
        ready.sort(key=lambda n: (-state.nodes[n].priority, n))

        failed_any = False
        for nid in ready:
            sim_states[nid] = NodeState.RUNNING
            defn = state.nodes[nid]
            retries_allowed = defn.retries
            action = defn.action
            success = False
            last_err: Optional[Exception] = None
            retries_attempted = 0
            val = None

            for attempt in range(retries_allowed + 1):
                try:
                    val = action() if action else None
                    success = True
                    break
                except Exception as e:
                    last_err = e
                    if attempt < retries_allowed:
                        retries_attempted += 1

            if success:
                sim_states[nid] = NodeState.SUCCEEDED
                sim_results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.SUCCEEDED,
                    value=val,
                    duration_seconds=0.01,
                    retries_attempted=retries_attempted,
                )
                for down in state.downstream.get(nid, set()):
                    if down in sim_states and sim_states[down] == NodeState.PENDING:
                        up = [u for u in state.upstream.get(down, set()) if u in state.nodes]
                        if all(sim_states.get(u) == NodeState.SUCCEEDED for u in up):
                            sim_states[down] = NodeState.READY
            else:
                sim_states[nid] = NodeState.FAILED
                sim_results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.FAILED,
                    error=last_err,
                    duration_seconds=0.01,
                    retries_attempted=retries_attempted,
                )
                if failure_policy == FailurePolicy.FAIL_FAST:
                    for other in state.nodes:
                        if sim_states.get(other) not in (
                            NodeState.SUCCEEDED,
                            NodeState.FAILED,
                            NodeState.SKIPPED,
                            NodeState.CANCELLED,
                        ):
                            sim_states[other] = NodeState.CANCELLED
                            if other not in sim_results:
                                sim_results[other] = NodeResult(
                                    node_id=other,
                                    state=NodeState.CANCELLED,
                                    duration_seconds=0.0,
                                )
                    failed_any = True
                    break
                elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
                    visited: Set[str] = set()
                    queue = list(state.downstream.get(nid, set()))
                    while queue:
                        curr = queue.pop(0)
                        if curr in state.nodes and curr not in visited:
                            visited.add(curr)
                            if sim_states.get(curr) not in (
                                NodeState.SUCCEEDED,
                                NodeState.FAILED,
                                NodeState.SKIPPED,
                                NodeState.CANCELLED,
                            ):
                                sim_states[curr] = NodeState.SKIPPED
                                if curr not in sim_results:
                                    sim_results[curr] = NodeResult(
                                        node_id=curr,
                                        state=NodeState.SKIPPED,
                                        duration_seconds=0.0,
                                    )
                            queue.extend(state.downstream.get(curr, set()))
                elif failure_policy == FailurePolicy.CONTINUE_ON_ERROR:
                    pass

        if failed_any and failure_policy == FailurePolicy.FAIL_FAST:
            break

    for n in state.nodes:
        if sim_states.get(n) in (NodeState.CANCELLED, NodeState.SKIPPED):
            if n not in sim_results:
                sim_results[n] = NodeResult(
                    node_id=n,
                    state=sim_states[n],
                    duration_seconds=0.0,
                )

    topo = _compute_topological_sort(state)
    succeeded_nodes = tuple(n for n in topo if sim_states.get(n) == NodeState.SUCCEEDED)
    failed_nodes = tuple(n for n in topo if sim_states.get(n) == NodeState.FAILED)
    skipped_nodes = tuple(n for n in topo if sim_states.get(n) == NodeState.SKIPPED)
    cancelled_nodes = tuple(n for n in topo if sim_states.get(n) == NodeState.CANCELLED)

    report = DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded_nodes,
        failed_nodes=failed_nodes,
        skipped_nodes=skipped_nodes,
        cancelled_nodes=cancelled_nodes,
        wall_clock_seconds=0.01,
        critical_path=tuple(crit_path),
        results=sim_results,
    )
    return report, sim_states, sim_results


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
    return (
        node_id if not isinstance(node_id, NotBoundType) else f"node_{len(state.nodes)}",
        action if not isinstance(action, NotBoundType) else (lambda: None),
        dependencies if not isinstance(dependencies, NotBoundType) else [],
        priority if not isinstance(priority, NotBoundType) else 0,
        retries if not isinstance(retries, NotBoundType) else 0,
    )

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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
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
    deps = frozenset(dependencies if dependencies is not None else ())
    defn = NodeDefinition(
        node_id=str(node_id),
        action=action,
        dependencies=deps,
        priority=int(priority),
        retries=int(retries),
    )
    state.nodes[str(node_id)] = defn
    if str(node_id) not in state.upstream:
        state.upstream[str(node_id)] = set()
    if str(node_id) not in state.downstream:
        state.downstream[str(node_id)] = set()
    for d in deps:
        if d not in state.downstream:
            state.downstream[d] = set()
        state.downstream[d].add(str(node_id))
        state.upstream[str(node_id)].add(d)
    if not deps:
        state.states[str(node_id)] = NodeState.READY
    else:
        state.states[str(node_id)] = NodeState.PENDING


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
    nodes = list(state.nodes.keys())
    u = upstream_id if not isinstance(upstream_id, NotBoundType) else (nodes[0] if nodes else "upstream")
    d = downstream_id if not isinstance(downstream_id, NotBoundType) else (nodes[-1] if len(nodes) > 1 else "downstream")
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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if str(upstream_id) not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {upstream_id} not found", node_id=str(upstream_id)))
    if str(downstream_id) not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {downstream_id} not found", node_id=str(downstream_id)))
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
        cur = state.nodes[d]
        state.nodes[d] = NodeDefinition(
            node_id=cur.node_id,
            action=cur.action,
            dependencies=cur.dependencies | {u},
            priority=cur.priority,
            retries=cur.retries,
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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_0")
    return (nid,)

@remove_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if str(node_id) not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=str(node_id)))
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
        del state.nodes[nid]
        for up in state.upstream.get(nid, set()):
            state.downstream.get(up, set()).discard(nid)
        for down in state.downstream.get(nid, set()):
            state.upstream.get(down, set()).discard(nid)
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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "unknown")
    return (nid,)

@has_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "missing")
    return (nid,)

@get_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if str(node_id) not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=str(node_id)))
    return Value(state.nodes[str(node_id)])

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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "missing")
    return (nid,)

@get_dependencies.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if str(node_id) not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=str(node_id)))
    return Value(set(state.upstream.get(str(node_id), set())))

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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "missing")
    return (nid,)

@get_dependents.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if str(node_id) not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=str(node_id)))
    return Value(set(state.downstream.get(str(node_id), set())))

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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    for node_id, defn in state.nodes.items():
        for dep in defn.dependencies:
            if dep not in state.nodes:
                return Raised(NodeNotFoundError(message=f"Dependency {dep} not found", node_id=dep))
    cycle = _detect_cycle(state)
    if cycle:
        return Raised(CycleError(message=f"Cycle detected: {cycle}", cycle=cycle))
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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    cycle = _detect_cycle(state)
    if cycle:
        return Raised(CycleError(message=f"Cycle detected: {cycle}", cycle=cycle))
    order = _compute_topological_sort(state)
    return Value(order)

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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    roots = {n for n in state.nodes if not [u for u in state.upstream.get(n, set()) if u in state.nodes]}
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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    leaves = {n for n in state.nodes if not [d for d in state.downstream.get(n, set()) if d in state.nodes]}
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
    return (estimated_durations if not isinstance(estimated_durations, NotBoundType) else None,)

@compute_critical_path.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    cycle = _detect_cycle(state)
    if cycle:
        return Raised(CycleError(message=f"Cycle detected: {cycle}", cycle=cycle))
    path, dur = _compute_critical_path(state, estimated_durations)
    return Value((path, dur))

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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    ready: List[str] = []
    for nid in state.nodes:
        st = state.states.get(nid, NodeState.READY if not state.upstream.get(nid) else NodeState.PENDING)
        if st == NodeState.READY:
            up = state.upstream.get(nid, set())
            if all(state.states.get(u) == NodeState.SUCCEEDED for u in up if u in state.nodes):
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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_0")
    return (nid,)

@mark_running.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_0")
    return (nid,)

@mark_succeeded.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
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
    for down in state.downstream.get(nid, set()):
        if state.states.get(down, NodeState.PENDING) == NodeState.PENDING:
            up = state.upstream.get(down, set())
            if all(state.states.get(u) == NodeState.SUCCEEDED for u in up if u in state.nodes):
                state.states[down] = NodeState.READY


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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_0")
    pol = failure_policy if not isinstance(failure_policy, NotBoundType) else FailurePolicy.FAIL_FAST
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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
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
    pol = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    if pol == FailurePolicy.FAIL_FAST:
        for node in state.nodes:
            if state.states.get(node) not in (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED):
                state.states[node] = NodeState.CANCELLED
    elif pol == FailurePolicy.SKIP_DOWNSTREAM:
        visited: Set[str] = set()
        queue = list(state.downstream.get(nid, set()))
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                if state.states.get(curr) not in (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED):
                    state.states[curr] = NodeState.SKIPPED
                queue.extend(state.downstream.get(curr, set()))
    elif pol == FailurePolicy.CONTINUE_ON_ERROR:
        pass


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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if not state.nodes:
        return Value(True)
    terminals = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
    fin = all(state.states.get(n) in terminals for n in state.nodes)
    return Value(fin)

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
    nodes = list(state.nodes.keys())
    nid = node_id if not isinstance(node_id, NotBoundType) else (nodes[0] if nodes else "node_0")
    return (nid,)

@get_state.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    nid = str(node_id)
    if nid not in state.nodes:
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=nid))
    if nid not in state.states:
        default_st = NodeState.READY if not state.upstream.get(nid) else NodeState.PENDING
        return Value(default_st)
    return Value(state.states[nid])

@get_state.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    nid = str(node_id)
    if nid not in state.states:
        state.states[nid] = NodeState.READY if not state.upstream.get(nid) else NodeState.PENDING


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
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    res = {
        n: state.states.get(n, NodeState.READY if not state.upstream.get(n) else NodeState.PENDING)
        for n in state.nodes
    }
    return Value(res)

@get_all_states.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    to_remove = [k for k in state.states if k not in state.nodes]
    for k in to_remove:
        state.states.pop(k, None)
    for n in state.nodes:
        if n not in state.states:
            state.states[n] = NodeState.READY if not state.upstream.get(n) else NodeState.PENDING


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
    pol = failure_policy if not isinstance(failure_policy, NotBoundType) else FailurePolicy.FAIL_FAST
    return (pol,)

@run.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    pol = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    try:
        report, _, _ = _simulate_run(state, pol)
        return Value(report)
    except NodeNotFoundError as e:
        return Raised(e)
    except CycleError as e:
        return Raised(e)

@run.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    pol = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    try:
        _, new_states, new_results = _simulate_run(state, pol)
        state.states.update(new_states)
        state.results.update(new_results)
    except Exception:
        pass


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
        self.assertEqual(len(self.dag.all_nodes()), 0)
        self.assertTrue(self.wavescheduler.is_finished())

    def test_fake_add_node(self) -> None:
        self.dag.add_node("task1", lambda: 10, priority=5, retries=2)
        self.assertTrue(self.dag.has_node("task1"))
        node = self.dag.get_node("task1")
        self.assertEqual(node.node_id, "task1")
        self.assertEqual(node.priority, 5)
        self.assertEqual(node.retries, 2)
        self.assertEqual(self.dag.get_dependencies("task1"), set())

    def test_fake_add_edge(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None)
        self.dag.add_edge("A", "B")
        self.assertIn("A", self.dag.get_dependencies("B"))
        self.assertIn("B", self.dag.get_dependents("A"))

    def test_fake_add_edge_missing(self) -> None:
        self.dag.add_node("A", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing_upstream", "A")

    def test_fake_add_edge_missing_downstream(self) -> None:
        self.dag.add_node("A", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("A", "missing_downstream")

    def test_fake_remove_node(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.remove_node("A")
        self.assertFalse(self.dag.has_node("A"))
        self.assertTrue(self.dag.has_node("B"))
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("A")

    def test_fake_remove_node_removes_edges(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["B"])
        self.assertEqual(self.dag.get_dependents("A"), {"B"})
        self.assertEqual(self.dag.get_dependencies("C"), {"B"})
        self.dag.remove_node("B")
        self.assertFalse(self.dag.has_node("B"))
        self.assertEqual(self.dag.get_dependents("A"), set())
        self.assertEqual(self.dag.get_dependencies("C"), set())
        self.assertEqual(self.dag.all_nodes(), {"A", "C"})

    def test_fake_has_node(self) -> None:
        self.assertFalse(self.dag.has_node("non_existent"))
        self.dag.add_node("A", lambda: 1)
        self.assertTrue(self.dag.has_node("A"))

    def test_fake_get_node(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("absent")
        self.dag.add_node("A", lambda: 100)
        self.assertEqual(self.dag.get_node("A").node_id, "A")

    def test_fake_get_dependencies(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("absent")
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.assertEqual(self.dag.get_dependencies("B"), {"A"})

    def test_fake_get_dependents(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("absent")
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.assertEqual(self.dag.get_dependents("A"), {"B"})

    def test_fake_all_nodes(self) -> None:
        self.assertEqual(self.dag.all_nodes(), set())
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None)
        self.assertEqual(self.dag.all_nodes(), {"A", "B"})

    def test_fake_validate(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.validate()

    def test_fake_validate_cycle(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None)
        self.dag.add_edge("A", "B")
        self.dag.add_edge("B", "A")
        with self.assertRaises(CycleError):
            self.dag.validate()

    def test_fake_validate_missing_dep(self) -> None:
        self.dag.add_node("A", lambda: None, dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_fake_topological_sort(self) -> None:
        self.dag.add_node("C", lambda: None, priority=1)
        self.dag.add_node("A", lambda: None, priority=10)
        self.dag.add_node("B", lambda: None, dependencies=["A"], priority=5)
        order = self.dag.topological_sort()
        self.assertEqual(order, ["A", "B", "C"])

    def test_fake_find_roots(self) -> None:
        self.dag.add_node("root1", lambda: None)
        self.dag.add_node("root2", lambda: None)
        self.dag.add_node("child", lambda: None, dependencies=["root1", "root2"])
        self.assertEqual(self.dag.find_roots(), {"root1", "root2"})

    def test_fake_find_leaves(self) -> None:
        self.dag.add_node("root", lambda: None)
        self.dag.add_node("leaf1", lambda: None, dependencies=["root"])
        self.dag.add_node("leaf2", lambda: None, dependencies=["root"])
        self.assertEqual(self.dag.find_leaves(), {"leaf1", "leaf2"})

    def test_fake_compute_critical_path(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None, dependencies=["B"])
        path, dur = self.dag.compute_critical_path({"A": 2.0, "B": 3.0, "C": 1.0})
        self.assertEqual(path, ["A", "B", "C"])
        self.assertEqual(dur, 6.0)

    def test_fake_empty_dag_critical_path_and_is_finished(self) -> None:
        path, dur = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(dur, 0.0)
        self.assertTrue(self.wavescheduler.is_finished())
        self.assertEqual(self.wavescheduler.next_wave(), [])

    def test_fake_next_wave(self) -> None:
        self.dag.add_node("A", lambda: None, priority=2)
        self.dag.add_node("B", lambda: None, priority=5)
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, ["B", "A"])

    def test_fake_mark_running(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.wavescheduler.mark_running("A")
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.RUNNING)

    def test_fake_mark_succeeded(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.PENDING)
        self.wavescheduler.mark_succeeded("A")
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.SUCCEEDED)
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.READY)

    def test_fake_mark_failed(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None)
        self.wavescheduler.mark_failed("A", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.CANCELLED)

    def test_fake_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None, dependencies=["A"])
        self.dag.add_node("C", lambda: None)
        self.wavescheduler.mark_failed("A", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("B"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("C"), NodeState.READY)

    def test_fake_is_finished(self) -> None:
        self.assertTrue(self.wavescheduler.is_finished())
        self.dag.add_node("A", lambda: None)
        self.assertFalse(self.wavescheduler.is_finished())
        self.wavescheduler.mark_succeeded("A")
        self.assertTrue(self.wavescheduler.is_finished())

    def test_fake_get_state(self) -> None:
        self.dag.add_node("root", lambda: None)
        self.assertEqual(self.wavescheduler.get_state("root"), NodeState.READY)

    def test_fake_scheduler_get_state_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("unregistered_node")


    def test_fake_get_all_states(self) -> None:
        self.dag.add_node("A", lambda: None)
        states = self.wavescheduler.get_all_states()
        self.assertIn("A", states)

    def test_fake_remove_node_synchronizes_scheduler_states(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None)
        states_before = self.wavescheduler.get_all_states()
        self.assertIn("A", states_before)
        self.assertIn("B", states_before)
        self.dag.remove_node("A")
        states_after = self.wavescheduler.get_all_states()
        self.assertNotIn("A", states_after)
        self.assertIn("B", states_after)
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("A")

    def test_fake_run(self) -> None:
        self.dag.add_node("A", lambda: 1)
        report = self.dagrunner.run()
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("A",))
        self.assertEqual(self.wavescheduler.get_state("A"), NodeState.SUCCEEDED)
        self.assertTrue(self.wavescheduler.is_finished())

    def test_fake_run_with_retries(self) -> None:
        attempts = 0
        def flaky() -> str:
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise ValueError(f"Transient fault on attempt {attempts}")
            return "recovered"

        self.dag.add_node("flaky", flaky, retries=2)
        report = self.dagrunner.run()
        self.assertIn("flaky", report.succeeded_nodes)
        self.assertEqual(report.results["flaky"].retries_attempted, 2)
        self.assertEqual(report.results["flaky"].value, "recovered")
        self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)

    def test_fake_run_failure_fail_fast(self) -> None:
        def bad_action() -> None:
            raise RuntimeError("Fatal execution error")

        self.dag.add_node("bad", bad_action, retries=1)
        self.dag.add_node("child", lambda: 2, dependencies=["bad"])
        self.dag.add_node("independent", lambda: 3)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("bad", report.failed_nodes)
        self.assertEqual(report.results["bad"].retries_attempted, 1)
        self.assertEqual(report.results["bad"].state, NodeState.FAILED)
        self.assertIn("child", report.cancelled_nodes)
        self.assertIn("independent", report.cancelled_nodes)
        self.assertEqual(report.results["child"].state, NodeState.CANCELLED)
        self.assertEqual(report.results["independent"].state, NodeState.CANCELLED)

    def test_fake_run_failure_skip_downstream(self) -> None:
        def bad_action() -> None:
            raise RuntimeError("Fatal node action")

        self.dag.add_node("bad", bad_action, retries=0)
        self.dag.add_node("downstream", lambda: 2, dependencies=["bad"])
        self.dag.add_node("independent", lambda: 3)
        report = self.dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIn("bad", report.failed_nodes)
        self.assertIn("downstream", report.skipped_nodes)
        self.assertIn("independent", report.succeeded_nodes)
        self.assertEqual(report.results["downstream"].state, NodeState.SKIPPED)
        self.assertEqual(report.results["independent"].state, NodeState.SUCCEEDED)


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

    def test_real_dag_add_and_query(self) -> None:
        self.dag.add_node("x", lambda: 1, priority=10, retries=1)
        self.assertTrue(self.dag.has_node("x"))
        defn = self.dag.get_node("x")
        self.assertEqual(defn.node_id, "x")
        self.assertEqual(defn.priority, 10)
        self.assertEqual(defn.retries, 1)
        self.assertEqual(self.dag.all_nodes(), {"x"})

    def test_real_dag_edges_and_dependencies(self) -> None:
        self.dag.add_node("p", lambda: 1)
        self.dag.add_node("q", lambda: 2)
        self.dag.add_edge("p", "q")
        self.assertIn("p", self.dag.get_dependencies("q"))
        self.assertIn("q", self.dag.get_dependents("p"))

    def test_real_dag_node_not_found(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("unknown", "other")
        self.dag.add_node("existing", lambda: 1)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("existing", "missing_downstream")

    def test_real_dag_remove_node_removes_edges(self) -> None:
        self.dag.add_node("A", lambda: 1)
        self.dag.add_node("B", lambda: 2, dependencies=["A"])
        self.dag.add_node("C", lambda: 3, dependencies=["B"])
        self.dag.remove_node("B")
        self.assertFalse(self.dag.has_node("B"))
        self.assertEqual(self.dag.get_dependents("A"), set())
        self.assertEqual(self.dag.get_dependencies("C"), set())

    def test_real_dag_roots_leaves_and_topo(self) -> None:
        self.dag.add_node("r1", lambda: 1)
        self.dag.add_node("r2", lambda: 2)
        self.dag.add_node("c", lambda: 3, dependencies=["r1", "r2"])
        self.assertEqual(self.dag.find_roots(), {"r1", "r2"})
        self.assertEqual(self.dag.find_leaves(), {"c"})
        topo = self.dag.topological_sort()
        self.assertTrue(topo.index("r1") < topo.index("c"))
        self.assertTrue(topo.index("r2") < topo.index("c"))

    def test_real_dag_cycle_detection(self) -> None:
        self.dag.add_node("n1", lambda: 1)
        self.dag.add_node("n2", lambda: 2)
        self.dag.add_edge("n1", "n2")
        self.dag.add_edge("n2", "n1")
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_real_dag_validate_missing_dependency(self) -> None:
        self.dag.add_node("n1", lambda: 1, dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_real_dag_critical_path(self) -> None:
        self.dag.add_node("n1", lambda: 1)
        self.dag.add_node("n2", lambda: 2, dependencies=["n1"])
        path, weight = self.dag.compute_critical_path({"n1": 1.5, "n2": 2.5})
        self.assertEqual(path, ["n1", "n2"])
        self.assertEqual(weight, 4.0)

    def test_real_empty_dag_critical_path_and_is_finished(self) -> None:
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)
        self.assertTrue(self.wavescheduler.is_finished())
        self.assertEqual(self.wavescheduler.next_wave(), [])

    def test_real_scheduler_lifecycle(self) -> None:
        self.dag.add_node("t1", lambda: 1)
        self.dag.add_node("t2", lambda: 2, dependencies=["t1"])
        wave = self.wavescheduler.next_wave()
        self.assertEqual(wave, ["t1"])
        self.wavescheduler.mark_running("t1")
        self.assertEqual(self.wavescheduler.get_state("t1"), NodeState.RUNNING)
        self.wavescheduler.mark_succeeded("t1")
        self.assertEqual(self.wavescheduler.get_state("t1"), NodeState.SUCCEEDED)
        self.assertEqual(self.wavescheduler.get_state("t2"), NodeState.READY)
        wave2 = self.wavescheduler.next_wave()
        self.assertEqual(wave2, ["t2"])
        self.wavescheduler.mark_succeeded("t2")
        self.assertTrue(self.wavescheduler.is_finished())

    def test_real_scheduler_get_state_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("unregistered_node")

    def test_real_remove_node_synchronizes_scheduler_states(self) -> None:
        self.dag.add_node("A", lambda: None)
        self.dag.add_node("B", lambda: None)
        states_before = self.wavescheduler.get_all_states()
        self.assertIn("A", states_before)
        self.assertIn("B", states_before)
        self.dag.remove_node("A")
        states_after = self.wavescheduler.get_all_states()
        self.assertNotIn("A", states_after)
        self.assertIn("B", states_after)
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("A")


    def test_real_scheduler_failure_fail_fast(self) -> None:
        self.dag.add_node("t1", lambda: 1)
        self.dag.add_node("t2", lambda: 2)
        self.wavescheduler.mark_failed("t1", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.wavescheduler.get_state("t1"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("t2"), NodeState.CANCELLED)

    def test_real_scheduler_failure_skip_downstream(self) -> None:
        self.dag.add_node("t1", lambda: 1)
        self.dag.add_node("t2", lambda: 2, dependencies=["t1"])
        self.dag.add_node("independent", lambda: 3)
        self.wavescheduler.mark_failed("t1", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("t1"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("t2"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("independent"), NodeState.READY)

    def test_real_runner_execution(self) -> None:
        self.dag.add_node("work", lambda: "ok")
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 1)
        self.assertIn("work", report.succeeded_nodes)

    def test_real_runner_execution_with_retries(self) -> None:
        attempts = 0
        def flaky_action() -> str:
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise ValueError("Transient error")
            return "recovered"

        self.dag.add_node("flaky", flaky_action, retries=2)
        report = self.dagrunner.run()
        self.assertIn("flaky", report.succeeded_nodes)
        self.assertEqual(report.results["flaky"].retries_attempted, 2)
        self.assertEqual(report.results["flaky"].value, "recovered")

    def test_real_runner_execution_failure_fail_fast(self) -> None:
        def bad_action() -> None:
            raise RuntimeError("Fatal action")

        self.dag.add_node("bad", bad_action, retries=1)
        self.dag.add_node("child", lambda: 2, dependencies=["bad"])
        self.dag.add_node("indep", lambda: 3)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIn("bad", report.failed_nodes)
        self.assertIn("child", report.cancelled_nodes)
        self.assertIn("indep", report.cancelled_nodes)

    def test_real_runner_execution_failure_skip_downstream(self) -> None:
        def bad_action() -> None:
            raise RuntimeError("Fatal action")

        self.dag.add_node("bad", bad_action, retries=0)
        self.dag.add_node("child", lambda: 2, dependencies=["bad"])
        self.dag.add_node("indep", lambda: 3)
        report = self.dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIn("bad", report.failed_nodes)
        self.assertIn("child", report.skipped_nodes)
        self.assertIn("indep", report.succeeded_nodes)


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
# LAST_CLEANED: 2026-10-26T17:41:43Z
# LAST_CHANGED: 2026-10-26T17:40:32Z
# CHANGE: Ensure WaveScheduler get_all_states synchronizes strictly with active nodes and add unit and real test coverage verifying scheduler state tracking reflects node removal after DAG remove_node
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T17:41:43Z
# PRETENSE_QA_AUDIT: 2026-10-26T17:41:08Z
# --- END CLEANROOM METADATA ---
