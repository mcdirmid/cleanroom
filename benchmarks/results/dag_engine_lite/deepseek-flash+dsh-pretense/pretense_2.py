"""Pretense specification, synthetic fakes, and tests for the lite DAG engine.

Target implementation:
    benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl

Interface contracts:
    benchmark_1.parts.dag_engine_lite.low.dag_engine_lite.pyi
    benchmark_1.parts.dag_engine_lite.low.dag_engine_lite_impl.pyi

The module is organized into the five canonical pretense sections:

1. ``DAGEngineState`` models the graph adjacency, per-node definitions, wave
   scheduler lifecycle states, and runner result records described by the
   ``INVARIANTS``/``POSTCONDITIONS`` of the low-level specifications.
2. ``proto = StateMachineProto[DAGEngineState]()`` maps every public operation
   of ``DAG``, ``WaveScheduler``, and ``DAGRunner`` to argument, return, and
   state-mutation transitions, and ``make_dag_engine_fakes`` synthesizes the
   three protocol fakes over one shared model state.
3. ``TestDAGEngineUnit`` exercises the synthesized fakes.
4. ``TestDAGEngineImplReal`` exercises the concrete singleton implementation
   inside isolated lifecycle registries, covering successful and erroring
   branches of every operation.
5. ``TestDAGEngineFuzz`` runs bounded Hypothesis property tests over generated
   acyclic graphs, including critical-path, ordering, and failure-policy
   invariants and full ``DAGRunReport`` partitioning.
"""

from __future__ import annotations

import time
import unittest
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, FrozenSet, List, Mapping, Optional, Set, Tuple

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)

# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_TERMINAL_STATES = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

_BLOCKING_STATES = frozenset(
    {
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

_FAILURE_POLICIES = (
    dag_engine_lite.FailurePolicy.FAIL_FAST,
    dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
    dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
)


@dataclass(frozen=True)
class _ModelNode:
    """Model-side immutable node definition mirroring ``NodeDefinition``."""

    node_id: str
    action: Callable[[], Any]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@dataclass
class DAGEngineState:
    """Model state for the DAG graph, wave scheduler, and sequential runner."""

    nodes: dict[str, _ModelNode] = field(default_factory=dict)
    upstream: dict[str, Set[str]] = field(default_factory=dict)
    downstream: dict[str, Set[str]] = field(default_factory=dict)
    states: dict[str, dag_engine_lite.NodeState] = field(default_factory=dict)
    results: dict[str, dag_engine_lite.NodeResult[Any]] = field(default_factory=dict)
    scheduler_synced: bool = False


def _ensure_adjacency(state: DAGEngineState, node_id: str) -> None:
    state.upstream.setdefault(node_id, set())
    state.downstream.setdefault(node_id, set())


def _model_add_edge(state: DAGEngineState, upstream_id: str, downstream_id: str) -> None:
    _ensure_adjacency(state, upstream_id)
    _ensure_adjacency(state, downstream_id)
    state.upstream[downstream_id].add(upstream_id)
    state.downstream[upstream_id].add(downstream_id)


def _model_add_node(
    state: DAGEngineState,
    node_id: str,
    action: Callable[[], Any],
    dependencies: Optional[Collection[str]],
    priority: int,
    retries: int,
) -> None:
    deps = frozenset(dependencies) if dependencies is not None else frozenset()
    state.nodes[node_id] = _ModelNode(
        node_id=node_id,
        action=action,
        dependencies=deps,
        priority=priority,
        retries=retries,
    )
    _ensure_adjacency(state, node_id)
    for dependency in deps:
        _model_add_edge(state, dependency, node_id)
    state.states.setdefault(
        node_id,
        dag_engine_lite.NodeState.READY
        if not state.upstream.get(node_id)
        else dag_engine_lite.NodeState.PENDING,
    )


def _model_remove_node(state: DAGEngineState, node_id: str) -> None:
    if node_id not in state.nodes:
        return
    for dependency in list(state.upstream.get(node_id, ())):
        state.downstream.get(dependency, set()).discard(node_id)
    for dependent in list(state.downstream.get(node_id, ())):
        state.upstream.get(dependent, set()).discard(node_id)
    state.upstream.pop(node_id, None)
    state.downstream.pop(node_id, None)
    state.nodes.pop(node_id, None)
    state.states.pop(node_id, None)
    state.results.pop(node_id, None)


def _model_missing_dependency(state: DAGEngineState) -> bool:
    for node_id in state.nodes:
        for dependency in state.upstream.get(node_id, ()):
            if dependency not in state.nodes:
                return True
    return False


def _first_missing_dependency(state: DAGEngineState) -> str:
    for node_id in sorted(state.nodes):
        for dependency in sorted(state.upstream.get(node_id, ())):
            if dependency not in state.nodes:
                return dependency
    return ""


def _node_not_found(node_id: str) -> dag_engine_lite.NodeNotFoundError:
    return dag_engine_lite.NodeNotFoundError(
        message=f"Node {node_id!r} is not present in the DAG.",
        node_id=node_id,
    )


def _cycle_error(cycle: Optional[Tuple[str, ...]]) -> dag_engine_lite.CycleError:
    sequence = tuple(cycle) if cycle is not None else ()
    rendered = " -> ".join(sequence) if sequence else "unknown"
    return dag_engine_lite.CycleError(
        message=f"Dependency cycle detected: {rendered}",
        cycle=sequence,
    )


def _model_cycle(state: DAGEngineState) -> Optional[Tuple[str, ...]]:
    visited: Set[str] = set()
    path: List[str] = []
    on_path: dict[str, int] = {}

    def visit(node_id: str) -> Optional[Tuple[str, ...]]:
        if node_id in on_path:
            return tuple(path[on_path[node_id]:] + [node_id])
        if node_id in visited:
            return None
        visited.add(node_id)
        on_path[node_id] = len(path)
        path.append(node_id)
        for dependent in sorted(state.downstream.get(node_id, ())):
            detected = visit(dependent)
            if detected is not None:
                return detected
        path.pop()
        del on_path[node_id]
        return None

    for node_id in sorted(state.nodes):
        detected = visit(node_id)
        if detected is not None:
            return detected
    return None


def _model_topological_order(state: DAGEngineState) -> List[str]:
    indegree: dict[str, int] = {
        node_id: len(state.upstream.get(node_id, ())) for node_id in state.nodes
    }
    ready: List[str] = [
        node_id for node_id, degree in indegree.items() if degree == 0
    ]
    ready.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    order: List[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for dependent in sorted(state.downstream.get(node_id, ())):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        ready.sort(key=lambda candidate: (-state.nodes[candidate].priority, candidate))
    return order


def _model_critical_path(
    state: DAGEngineState,
    estimated_durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    if not state.nodes:
        return ([], 0.0)
    order = _model_topological_order(state)
    durations = {
        node_id: float(
            estimated_durations[node_id]
            if estimated_durations is not None and node_id in estimated_durations
            else 1.0
        )
        for node_id in order
    }
    earliest: dict[str, float] = {}
    for node_id in order:
        predecessors = [
            dependency
            for dependency in state.upstream.get(node_id, ())
            if dependency in earliest
        ]
        baseline = max((earliest[p] for p in predecessors), default=0.0)
        earliest[node_id] = baseline + durations[node_id]
    if not earliest:
        return ([], 0.0)
    terminal = max(order, key=lambda node_id: (earliest[node_id], node_id))
    path: List[str] = [terminal]
    while True:
        predecessors = [
            dependency
            for dependency in state.upstream.get(path[-1], ())
            if dependency in earliest
        ]
        if not predecessors:
            break
        best = max(predecessors, key=lambda p: (earliest[p], p))
        path.append(best)
    path.reverse()
    return (path, earliest[terminal])


def _sync_scheduler_state(state: DAGEngineState) -> None:
    registered = set(state.nodes)
    for node_id in list(state.states):
        if node_id not in registered:
            state.states.pop(node_id, None)
    for node_id in registered:
        if node_id not in state.states:
            state.states[node_id] = (
                dag_engine_lite.NodeState.READY
                if not state.upstream.get(node_id)
                else dag_engine_lite.NodeState.PENDING
            )
    state.scheduler_synced = True


def _model_next_wave(state: DAGEngineState) -> List[str]:
    _sync_scheduler_state(state)
    candidates: List[str] = []
    for node_id, node_state in state.states.items():
        if node_state is not dag_engine_lite.NodeState.READY:
            continue
        if all(
            state.states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
            for dependency in state.upstream.get(node_id, ())
        ):
            candidates.append(node_id)
    candidates.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    return candidates


def _model_mark_running(state: DAGEngineState, node_id: str) -> None:
    state.states[node_id] = dag_engine_lite.NodeState.RUNNING


def _model_mark_succeeded(state: DAGEngineState, node_id: str) -> None:
    state.states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
    for dependent in state.downstream.get(node_id, ()):
        if state.states.get(dependent) is dag_engine_lite.NodeState.PENDING:
            if all(
                state.states.get(dependency)
                is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in state.upstream.get(dependent, ())
            ):
                state.states[dependent] = dag_engine_lite.NodeState.READY


def _transitive_dependents(state: DAGEngineState, node_id: str) -> Set[str]:
    discovered: Set[str] = set()
    frontier = list(state.downstream.get(node_id, ()))
    while frontier:
        current = frontier.pop()
        if current in discovered:
            continue
        discovered.add(current)
        frontier.extend(state.downstream.get(current, ()))
    return discovered


def _model_mark_failed(
    state: DAGEngineState,
    node_id: str,
    failure_policy: dag_engine_lite.FailurePolicy,
) -> None:
    state.states[node_id] = dag_engine_lite.NodeState.FAILED
    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
        for candidate, candidate_state in list(state.states.items()):
            if candidate_state not in _TERMINAL_STATES:
                state.states[candidate] = dag_engine_lite.NodeState.CANCELLED
        return
    for dependent in _transitive_dependents(state, node_id):
        dependent_state = state.states.get(dependent)
        if dependent_state is not None and dependent_state in _TERMINAL_STATES:
            continue
        state.states[dependent] = dag_engine_lite.NodeState.SKIPPED


def _model_is_finished(state: DAGEngineState) -> bool:
    _sync_scheduler_state(state)
    if not state.nodes:
        return True
    if all(node_state in _TERMINAL_STATES for node_state in state.states.values()):
        return True
    for node_id, node_state in state.states.items():
        if node_state in _TERMINAL_STATES:
            continue
        if node_state in (
            dag_engine_lite.NodeState.READY,
            dag_engine_lite.NodeState.RUNNING,
        ):
            return False
        if node_state is dag_engine_lite.NodeState.PENDING:
            blocked = any(
                state.states.get(dependency) in _BLOCKING_STATES
                for dependency in state.upstream.get(node_id, ())
            )
            if not blocked:
                return False
    return True


def _model_node_definition(model_node: _ModelNode) -> dag_engine_lite.NodeDefinition[Any]:
    return dag_engine_lite.NodeDefinition(
        node_id=model_node.node_id,
        action=model_node.action,
        dependencies=model_node.dependencies,
        priority=model_node.priority,
        retries=model_node.retries,
    )


def _model_report(state: DAGEngineState) -> dag_engine_lite.DAGRunReport:
    _sync_scheduler_state(state)
    succeeded = tuple(
        sorted(
            node_id
            for node_id, node_state in state.states.items()
            if node_state is dag_engine_lite.NodeState.SUCCEEDED
        )
    )
    failed = tuple(
        sorted(
            node_id
            for node_id, node_state in state.states.items()
            if node_state is dag_engine_lite.NodeState.FAILED
        )
    )
    skipped = tuple(
        sorted(
            node_id
            for node_id, node_state in state.states.items()
            if node_state is dag_engine_lite.NodeState.SKIPPED
        )
    )
    cancelled = tuple(
        sorted(
            node_id
            for node_id, node_state in state.states.items()
            if node_state is dag_engine_lite.NodeState.CANCELLED
        )
    )
    results = dict(state.results)
    for node_id in state.nodes:
        node_state = state.states.get(node_id)
        if node_id in results or node_state is None:
            continue
        if node_state in _TERMINAL_STATES:
            results[node_id] = dag_engine_lite.NodeResult(
                node_id=node_id, state=node_state
            )
    path, _ = _model_critical_path(state, None)
    return dag_engine_lite.DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded,
        failed_nodes=failed,
        skipped_nodes=skipped,
        cancelled_nodes=cancelled,
        wall_clock_seconds=0.0,
        critical_path=tuple(path),
        results=results,
    )


def _fresh_node_id(state: DAGEngineState) -> str:
    index = len(state.nodes)
    while f"n{index}" in state.nodes:
        index += 1
    return f"n{index}"


def _pick_node_id(state: DAGEngineState, index: int = 0) -> str:
    identifiers = sorted(state.nodes)
    if not identifiers:
        return "missing-node"
    return identifiers[index % len(identifiers)]


def _pick_node_pair(state: DAGEngineState) -> Tuple[str, str]:
    identifiers = sorted(state.nodes)
    if len(identifiers) >= 2:
        return (identifiers[0], identifiers[1])
    if identifiers:
        return (identifiers[0], "missing-node")
    return ("missing-node", "missing-node")


proto = StateMachineProto[DAGEngineState]()


# --- DAG.add_node -------------------------------------------------------------


@proto.transition(DAG.add_node)
def _dag_add_node() -> None: ...


@_dag_add_node.arguments
def _dag_add_node_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    action: Any | NotBoundType = NotBound,
    dependencies: Any | NotBoundType = NotBound,
    priority: Any | NotBoundType = NotBound,
    retries: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_node_id = (
        node_id if not isinstance(node_id, NotBoundType) else _fresh_node_id(state)
    )
    resolved_action = (
        action if not isinstance(action, NotBoundType) else (lambda: None)
    )
    resolved_dependencies = (
        dependencies if not isinstance(dependencies, NotBoundType) else None
    )
    resolved_priority = priority if not isinstance(priority, NotBoundType) else 0
    resolved_retries = retries if not isinstance(retries, NotBoundType) else 0
    return (
        resolved_node_id,
        resolved_action,
        resolved_dependencies,
        resolved_priority,
        resolved_retries,
    )


@_dag_add_node.returns
def _dag_add_node_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any = None,
    priority: Any = 0,
    retries: Any = 0,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_add_node.provide
def _dag_add_node_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    result: Any,
) -> None:
    _model_add_node(state, node_id, action, dependencies, priority, retries)


# --- DAG.add_edge -------------------------------------------------------------


@proto.transition(DAG.add_edge)
def _dag_add_edge() -> None: ...


@_dag_add_edge.arguments
def _dag_add_edge_arguments(
    state: DAGEngineState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    default_upstream, default_downstream = _pick_node_pair(state)
    resolved_upstream = (
        upstream_id
        if not isinstance(upstream_id, NotBoundType)
        else default_upstream
    )
    resolved_downstream = (
        downstream_id
        if not isinstance(downstream_id, NotBoundType)
        else default_downstream
    )
    return (resolved_upstream, resolved_downstream)


@_dag_add_edge.returns
def _dag_add_edge_returns(
    state: DAGEngineState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if upstream_id not in state.nodes or downstream_id not in state.nodes:
            missing = upstream_id if upstream_id not in state.nodes else downstream_id
            return Raised(_node_not_found(missing))
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_add_edge.provide
def _dag_add_edge_provide(
    state: DAGEngineState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any,
) -> None:
    if upstream_id in state.nodes and downstream_id in state.nodes:
        _model_add_edge(state, upstream_id, downstream_id)


# --- DAG.remove_node ----------------------------------------------------------


@proto.transition(DAG.remove_node)
def _dag_remove_node() -> None: ...


@_dag_remove_node.arguments
def _dag_remove_node_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_dag_remove_node.returns
def _dag_remove_node_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if node_id not in state.nodes:
            return Raised(_node_not_found(node_id))
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_remove_node.provide
def _dag_remove_node_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    _model_remove_node(state, node_id)


# --- DAG.has_node -------------------------------------------------------------


@proto.transition(DAG.has_node)
def _dag_has_node() -> None: ...


@_dag_has_node.arguments
def _dag_has_node_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_dag_has_node.returns
def _dag_has_node_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(node_id in state.nodes)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_has_node.provide
def _dag_has_node_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    return None


# --- DAG.get_node -------------------------------------------------------------


@proto.transition(DAG.get_node)
def _dag_get_node() -> None: ...


@_dag_get_node.arguments
def _dag_get_node_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_dag_get_node.returns
def _dag_get_node_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        model_node = state.nodes.get(node_id)
        if model_node is None:
            return Raised(_node_not_found(node_id))
        return Value(_model_node_definition(model_node))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_get_node.provide
def _dag_get_node_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    return None


# --- DAG.get_dependencies -----------------------------------------------------


@proto.transition(DAG.get_dependencies)
def _dag_get_dependencies() -> None: ...


@_dag_get_dependencies.arguments
def _dag_get_dependencies_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_dag_get_dependencies.returns
def _dag_get_dependencies_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if node_id not in state.nodes:
            return Raised(_node_not_found(node_id))
        return Value(set(state.upstream.get(node_id, ())))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_get_dependencies.provide
def _dag_get_dependencies_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    return None


# --- DAG.get_dependents -------------------------------------------------------


@proto.transition(DAG.get_dependents)
def _dag_get_dependents() -> None: ...


@_dag_get_dependents.arguments
def _dag_get_dependents_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_dag_get_dependents.returns
def _dag_get_dependents_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if node_id not in state.nodes:
            return Raised(_node_not_found(node_id))
        return Value(set(state.downstream.get(node_id, ())))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_get_dependents.provide
def _dag_get_dependents_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    return None


# --- DAG.all_nodes ------------------------------------------------------------


@proto.transition(DAG.all_nodes)
def _dag_all_nodes() -> None: ...


@_dag_all_nodes.arguments
def _dag_all_nodes_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_dag_all_nodes.returns
def _dag_all_nodes_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(set(state.nodes))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_all_nodes.provide
def _dag_all_nodes_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- DAG.validate -------------------------------------------------------------


@proto.transition(DAG.validate)
def _dag_validate() -> None: ...


@_dag_validate.arguments
def _dag_validate_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_dag_validate.returns
def _dag_validate_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if _model_missing_dependency(state):
            return Raised(_node_not_found(_first_missing_dependency(state)))
        cycle = _model_cycle(state)
        if cycle is not None:
            return Raised(_cycle_error(cycle))
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_validate.provide
def _dag_validate_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- DAG.topological_sort -----------------------------------------------------


@proto.transition(DAG.topological_sort)
def _dag_topological_sort() -> None: ...


@_dag_topological_sort.arguments
def _dag_topological_sort_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_dag_topological_sort.returns
def _dag_topological_sort_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if _model_missing_dependency(state):
            return Raised(_node_not_found(_first_missing_dependency(state)))
        cycle = _model_cycle(state)
        if cycle is not None:
            return Raised(_cycle_error(cycle))
        return Value(_model_topological_order(state))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_topological_sort.provide
def _dag_topological_sort_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- DAG.find_roots -----------------------------------------------------------


@proto.transition(DAG.find_roots)
def _dag_find_roots() -> None: ...


@_dag_find_roots.arguments
def _dag_find_roots_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_dag_find_roots.returns
def _dag_find_roots_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(
            {
                node_id
                for node_id in state.nodes
                if not state.upstream.get(node_id)
            }
        )
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_find_roots.provide
def _dag_find_roots_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- DAG.find_leaves ----------------------------------------------------------


@proto.transition(DAG.find_leaves)
def _dag_find_leaves() -> None: ...


@_dag_find_leaves.arguments
def _dag_find_leaves_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_dag_find_leaves.returns
def _dag_find_leaves_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(
            {
                node_id
                for node_id in state.nodes
                if not state.downstream.get(node_id)
            }
        )
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_find_leaves.provide
def _dag_find_leaves_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- DAG.compute_critical_path ------------------------------------------------


@proto.transition(DAG.compute_critical_path)
def _dag_compute_critical_path() -> None: ...


@_dag_compute_critical_path.arguments
def _dag_compute_critical_path_arguments(
    state: DAGEngineState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = (
        estimated_durations
        if not isinstance(estimated_durations, NotBoundType)
        else None
    )
    return (resolved,)


@_dag_compute_critical_path.returns
def _dag_compute_critical_path_returns(
    state: DAGEngineState,
    this: Any,
    estimated_durations: Any = None,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(_model_critical_path(state, estimated_durations))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_dag_compute_critical_path.provide
def _dag_compute_critical_path_provide(
    state: DAGEngineState,
    this: Any,
    estimated_durations: Any,
    result: Any,
) -> None:
    return None


# --- WaveScheduler.next_wave --------------------------------------------------


@proto.transition(WaveScheduler.next_wave)
def _scheduler_next_wave() -> None: ...


@_scheduler_next_wave.arguments
def _scheduler_next_wave_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_scheduler_next_wave.returns
def _scheduler_next_wave_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(_model_next_wave(state))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_next_wave.provide
def _scheduler_next_wave_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- WaveScheduler.mark_running -----------------------------------------------


@proto.transition(WaveScheduler.mark_running)
def _scheduler_mark_running() -> None: ...


@_scheduler_mark_running.arguments
def _scheduler_mark_running_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_scheduler_mark_running.returns
def _scheduler_mark_running_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_mark_running.provide
def _scheduler_mark_running_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    _model_mark_running(state, node_id)


# --- WaveScheduler.mark_succeeded ---------------------------------------------


@proto.transition(WaveScheduler.mark_succeeded)
def _scheduler_mark_succeeded() -> None: ...


@_scheduler_mark_succeeded.arguments
def _scheduler_mark_succeeded_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_scheduler_mark_succeeded.returns
def _scheduler_mark_succeeded_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_mark_succeeded.provide
def _scheduler_mark_succeeded_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    _model_mark_succeeded(state, node_id)


# --- WaveScheduler.mark_failed ------------------------------------------------


@proto.transition(WaveScheduler.mark_failed)
def _scheduler_mark_failed() -> None: ...


@_scheduler_mark_failed.arguments
def _scheduler_mark_failed_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_node = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    resolved_policy = (
        failure_policy
        if not isinstance(failure_policy, NotBoundType)
        else dag_engine_lite.FailurePolicy.FAIL_FAST
    )
    return (resolved_node, resolved_policy)


@_scheduler_mark_failed.returns
def _scheduler_mark_failed_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    failure_policy: Any = dag_engine_lite.FailurePolicy.FAIL_FAST,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_mark_failed.provide
def _scheduler_mark_failed_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    _model_mark_failed(state, node_id, failure_policy)


# --- WaveScheduler.is_finished ------------------------------------------------


@proto.transition(WaveScheduler.is_finished)
def _scheduler_is_finished() -> None: ...


@_scheduler_is_finished.arguments
def _scheduler_is_finished_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_scheduler_is_finished.returns
def _scheduler_is_finished_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(_model_is_finished(state))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_is_finished.provide
def _scheduler_is_finished_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- WaveScheduler.get_state --------------------------------------------------


@proto.transition(WaveScheduler.get_state)
def _scheduler_get_state() -> None: ...


@_scheduler_get_state.arguments
def _scheduler_get_state_arguments(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = node_id if not isinstance(node_id, NotBoundType) else _pick_node_id(state)
    return (resolved,)


@_scheduler_get_state.returns
def _scheduler_get_state_returns(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        _sync_scheduler_state(state)
        node_state = state.states.get(node_id)
        if node_state is None:
            return Raised(KeyError(node_id))
        return Value(node_state)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_get_state.provide
def _scheduler_get_state_provide(
    state: DAGEngineState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    return None


# --- WaveScheduler.get_all_states ---------------------------------------------


@proto.transition(WaveScheduler.get_all_states)
def _scheduler_get_all_states() -> None: ...


@_scheduler_get_all_states.arguments
def _scheduler_get_all_states_arguments(
    state: DAGEngineState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@_scheduler_get_all_states.returns
def _scheduler_get_all_states_returns(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        _sync_scheduler_state(state)
        return Value(
            {
                node_id: state.states[node_id]
                for node_id in state.nodes
                if node_id in state.states
            }
        )
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_scheduler_get_all_states.provide
def _scheduler_get_all_states_provide(
    state: DAGEngineState,
    this: Any,
    result: Any,
) -> None:
    return None


# --- DAGRunner.run ------------------------------------------------------------


@proto.transition(DAGRunner.run)
def _runner_run() -> None: ...


@_runner_run.arguments
def _runner_run_arguments(
    state: DAGEngineState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = (
        failure_policy
        if not isinstance(failure_policy, NotBoundType)
        else dag_engine_lite.FailurePolicy.FAIL_FAST
    )
    return (resolved,)


@_runner_run.returns
def _runner_run_returns(
    state: DAGEngineState,
    this: Any,
    failure_policy: Any = dag_engine_lite.FailurePolicy.FAIL_FAST,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(_model_report(state))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@_runner_run.provide
def _runner_run_provide(
    state: DAGEngineState,
    this: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    _sync_scheduler_state(state)
    for node_id in state.nodes:
        node_state = state.states.get(node_id)
        if node_state is None or node_state not in _TERMINAL_STATES:
            continue
        state.results.setdefault(
            node_id,
            dag_engine_lite.NodeResult(node_id=node_id, state=node_state),
        )


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================


def make_dag_engine_fakes(
    state: DAGEngineState,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes the three DAG engine fakes over one shared model state."""
    state_machine = proto.make_state_machine(state)
    return (
        state_machine.as_fake(DAG),
        state_machine.as_fake(WaveScheduler),
        state_machine.as_fake(DAGRunner),
    )


def make_dag_engine_fake(state: DAGEngineState) -> DAG:
    """Synthesizes a standalone DAG fake over the supplied model state."""
    return proto.make_state_machine(state).as_fake(DAG)


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================


class TestDAGEngineUnit(unittest.TestCase):
    """Verifies that the synthesized fakes conform to the state machine."""

    def setUp(self) -> None:
        self.state = DAGEngineState()
        self.dag, self.scheduler, self.runner = make_dag_engine_fakes(self.state)

    def test_add_node_registers_definition(self) -> None:
        action: Callable[[], Any] = lambda: "value"
        self.assertIsNone(self.dag.add_node("a", action, None, 2, 1))
        self.assertTrue(self.dag.has_node("a"))
        self.assertFalse(self.dag.has_node("missing-node"))
        definition = self.dag.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertIs(definition.action, action)
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.priority, 2)
        self.assertEqual(definition.retries, 1)
        self.assertEqual(self.dag.all_nodes(), {"a"})

    def test_add_node_with_dependencies_updates_adjacency(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, {"a"}, 0, 0)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.get_dependencies("a"), set())
        self.assertEqual(self.dag.get_dependents("b"), set())
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})

    def test_add_edge_and_remove_node(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.assertIsNone(self.dag.add_edge("a", "b"))
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertIsNone(self.dag.remove_node("b"))
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.all_nodes(), {"a"})

    def test_missing_nodes_raise_contracted_errors(self) -> None:
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_node("missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependencies("missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependents("missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.add_edge("missing-node", "also-missing")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.remove_node("missing-node")

    def test_scheduler_initial_states_and_waves(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, {"a"})
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.READY)
        self.assertEqual(states["b"], dag_engine_lite.NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.assertFalse(self.scheduler.is_finished())

    def test_scheduler_promotes_dependents_after_success(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, {"a"})
        self.scheduler.mark_running("a")
        self.assertEqual(
            self.scheduler.get_state("a"), dag_engine_lite.NodeState.RUNNING
        )
        self.scheduler.mark_succeeded("a")
        self.assertEqual(
            self.scheduler.get_state("a"), dag_engine_lite.NodeState.SUCCEEDED
        )
        self.assertEqual(
            self.scheduler.get_state("b"), dag_engine_lite.NodeState.READY
        )
        self.scheduler.mark_succeeded("b")
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_failure_policies(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, {"a"})
        self.dag.add_node("c", lambda: None, {"b"})
        self.scheduler.get_all_states()
        self.scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST)
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
        self.assertEqual(states["b"], dag_engine_lite.NodeState.CANCELLED)
        self.assertEqual(states["c"], dag_engine_lite.NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_reconvergent_failure_policies(self) -> None:
        for policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            with self.subTest(policy=policy.name):
                state = DAGEngineState()
                dag, scheduler, _ = make_dag_engine_fakes(state)
                dag.add_node("a", lambda: None)
                dag.add_node("b", lambda: None, {"a"})
                dag.add_node("c", lambda: None, {"a"})
                dag.add_node("join", lambda: None, {"b", "c"})
                dag.add_node("tail", lambda: None, {"join"})
                dag.add_node("independent", lambda: None)
                scheduler.get_all_states()
                scheduler.mark_failed("a", policy)
                states = dict(scheduler.get_all_states())
                self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
                for dependent in ("b", "c", "join", "tail"):
                    self.assertEqual(
                        states[dependent], dag_engine_lite.NodeState.SKIPPED
                    )
                self.assertEqual(
                    states["independent"], dag_engine_lite.NodeState.READY
                )

    def test_topological_sort_defers_missing_dependency(self) -> None:
        self.dag.add_node("b", lambda: None, {"a"})
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.topological_sort()
        self.dag.add_node("a", lambda: None)
        self.assertEqual(self.dag.topological_sort(), ["a", "b"])

    def test_remove_node_with_deferred_dependency(self) -> None:
        self.dag.add_node("b", lambda: None, {"a"})
        self.dag.remove_node("b")
        self.dag.add_node("a", lambda: None)
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.find_leaves(), {"a"})

    def test_topological_order_and_critical_path(self) -> None:
        self.dag.add_node("a", lambda: None, None, 0, 0)
        self.dag.add_node("b", lambda: None, {"a"}, 1, 0)
        self.dag.add_node("c", lambda: None, {"a"}, 2, 0)
        self.assertEqual(self.dag.topological_sort(), ["a", "c", "b"])
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(weight, 2.0)
        self.assertEqual(len(path), 2)
        self.assertIn("a", path)

    def test_validate_detects_missing_dependency(self) -> None:
        self.dag.add_node("b", lambda: None, {"a"})
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.validate()
        self.dag.add_node("a", lambda: None)
        self.assertIsNone(self.dag.validate())

    def test_validate_detects_cycle(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, {"a"})
        self.dag.add_edge("b", "a")
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.validate()
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.topological_sort()

    def test_runner_reports_terminal_states(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, {"a"})
        self.scheduler.mark_succeeded("a")
        self.scheduler.mark_succeeded("b")
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(set(report.failed_nodes), set())
        self.assertEqual(set(report.skipped_nodes), set())
        self.assertEqual(set(report.cancelled_nodes), set())
        self.assertEqual(set(report.results), {"a", "b"})
        self.assertEqual(len(report.critical_path), 2)


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================


class TestDAGEngineImplReal(unittest.TestCase):
    """Verifies the concrete DAG engine singletons inside an isolated registry."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.executed: List[str] = []

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _ok_action(self, node_id: str, value: Any = None) -> Callable[[], Any]:
        def action() -> Any:
            self.executed.append(node_id)
            return value if value is not None else node_id

        return action

    def _fail_action(self, node_id: str) -> Callable[[], Any]:
        def action() -> Any:
            self.executed.append(node_id)
            raise RuntimeError(f"node {node_id} failed intentionally")

        return action

    # --- DAG ---------------------------------------------------------------

    def test_add_node_defaults_and_queries(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node(
            "b", self._ok_action("b"), dependencies={"a"}, priority=3, retries=2
        )
        self.assertTrue(self.dag.has_node("a"))
        self.assertTrue(self.dag.has_node("b"))
        self.assertFalse(self.dag.has_node("missing-node"))
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})
        node_a = self.dag.get_node("a")
        self.assertEqual(node_a.node_id, "a")
        self.assertEqual(node_a.dependencies, frozenset())
        self.assertEqual(node_a.priority, 0)
        self.assertEqual(node_a.retries, 0)
        node_b = self.dag.get_node("b")
        self.assertEqual(node_b.dependencies, frozenset({"a"}))
        self.assertEqual(node_b.priority, 3)
        self.assertEqual(node_b.retries, 2)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.get_dependencies("a"), set())
        self.assertEqual(self.dag.get_dependents("b"), set())
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})

    def test_add_node_defers_missing_dependency_validation(self) -> None:
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.assertTrue(self.dag.has_node("b"))
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.validate()
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.topological_sort()
        self.dag.add_node("a", self._ok_action("a"))
        self.assertIsNone(self.dag.validate())
        self.assertEqual(self.dag.topological_sort(), ["a", "b"])

    def test_remove_node_with_unregistered_deferred_dependency(self) -> None:
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), set())
        self.dag.add_node("a", self._ok_action("a"))
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"a"})
        self.assertIsNone(self.dag.validate())

    def test_add_edge_and_missing_node_errors(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"))
        self.dag.add_node("c", self._ok_action("c"))
        self.assertIsNone(self.dag.add_edge("a", "c"))
        self.assertEqual(self.dag.get_dependencies("c"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"c"})
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.add_edge("a", "missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.add_edge("missing-node", "a")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_node("missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependencies("missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.get_dependents("missing-node")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.dag.remove_node("missing-node")

    def test_remove_node_purges_incident_edges(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"b"})
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a", "c"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())

    def test_validate_accepts_acyclic_graph(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a", "b"})
        self.assertIsNone(self.dag.validate())
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"c"})

    def test_validate_detects_cycle_with_sequence(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"b"})
        self.dag.add_edge("c", "a")
        with self.assertRaises(dag_engine_lite.CycleError) as context:
            self.dag.validate()
        self.assertTrue(context.exception.cycle)
        self.assertTrue(set(context.exception.cycle) <= {"a", "b", "c"})

    def test_topological_sort_orders_by_priority_then_identifier(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"}, priority=1)
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"}, priority=2)
        self.dag.add_node("d", self._ok_action("d"), dependencies={"b", "c"})
        order = self.dag.topological_sort()
        self.assertEqual(order, ["a", "c", "b", "d"])
        positions = {node_id: index for index, node_id in enumerate(order)}
        for node_id in self.dag.all_nodes():
            for dependency in self.dag.get_dependencies(node_id):
                self.assertLess(positions[dependency], positions[node_id])

    def test_topological_sort_raises_on_cycle(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_edge("b", "a")
        with self.assertRaises(dag_engine_lite.CycleError):
            self.dag.topological_sort()

    def test_compute_critical_path_default_weights(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"b"})
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 3.0)

    def test_compute_critical_path_weighted_branch(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"})
        self.dag.add_node("d", self._ok_action("d"), dependencies={"b"})
        self.dag.add_node("e", self._ok_action("e"), dependencies={"c"})
        path, weight = self.dag.compute_critical_path(
            {"a": 2.0, "b": 5.0, "c": 1.0, "d": 1.0, "e": 9.0}
        )
        self.assertEqual(path, ["a", "c", "e"])
        self.assertEqual(weight, 12.0)

    # --- WaveScheduler -----------------------------------------------------

    def test_scheduler_next_wave_priority_and_initial_states(self) -> None:
        self.dag.add_node("a", self._ok_action("a"), priority=0)
        self.dag.add_node("b", self._ok_action("b"), priority=5)
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"})
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.READY)
        self.assertEqual(states["b"], dag_engine_lite.NodeState.READY)
        self.assertEqual(states["c"], dag_engine_lite.NodeState.PENDING)
        self.assertEqual(self.scheduler.next_wave(), ["b", "a"])
        self.assertEqual(
            self.scheduler.get_state("a"), dag_engine_lite.NodeState.READY
        )

    def test_scheduler_wave_transitions_unlock_dependents(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.assertEqual(
            self.scheduler.get_state("a"), dag_engine_lite.NodeState.RUNNING
        )
        self.assertEqual(self.scheduler.next_wave(), [])
        self.scheduler.mark_succeeded("a")
        self.assertEqual(
            self.scheduler.get_state("b"), dag_engine_lite.NodeState.READY
        )
        self.assertEqual(self.scheduler.next_wave(), ["b"])
        self.scheduler.mark_running("b")
        self.scheduler.mark_succeeded("b")
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(
            dict(self.scheduler.get_all_states()),
            {
                "a": dag_engine_lite.NodeState.SUCCEEDED,
                "b": dag_engine_lite.NodeState.SUCCEEDED,
            },
        )

    def test_scheduler_fail_fast_cancels_pending_nodes(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"))
        self.scheduler.get_all_states()
        self.scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST)
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
        self.assertEqual(states["b"], dag_engine_lite.NodeState.CANCELLED)
        self.assertEqual(states["c"], dag_engine_lite.NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_skip_downstream_marks_transitive_dependents(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"b"})
        self.dag.add_node("d", self._ok_action("d"))
        self.scheduler.get_all_states()
        self.scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
        self.assertEqual(states["b"], dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(states["c"], dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(states["d"], dag_engine_lite.NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())
        self.scheduler.mark_succeeded("d")
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_continue_on_error_keeps_independent_nodes(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"b"})
        self.dag.add_node("d", self._ok_action("d"))
        self.scheduler.get_all_states()
        self.scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
        self.assertEqual(states["b"], dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(states["c"], dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(states["d"], dag_engine_lite.NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), ["d"])

    def test_scheduler_skip_downstream_reconvergent_dependents(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"})
        self.dag.add_node("join", self._ok_action("join"), dependencies={"b", "c"})
        self.dag.add_node("tail", self._ok_action("tail"), dependencies={"join"})
        self.dag.add_node("independent", self._ok_action("independent"))
        self.scheduler.get_all_states()
        self.scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
        for dependent in ("b", "c", "join", "tail"):
            self.assertEqual(
                states[dependent], dag_engine_lite.NodeState.SKIPPED
            )
        self.assertEqual(
            states["independent"], dag_engine_lite.NodeState.READY
        )
        self.assertEqual(self.scheduler.next_wave(), ["independent"])

    def test_scheduler_continue_on_error_reconvergent_dependents(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"})
        self.dag.add_node("join", self._ok_action("join"), dependencies={"b", "c"})
        self.dag.add_node("tail", self._ok_action("tail"), dependencies={"join"})
        self.dag.add_node("independent", self._ok_action("independent"))
        self.scheduler.get_all_states()
        self.scheduler.mark_failed(
            "a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["a"], dag_engine_lite.NodeState.FAILED)
        for dependent in ("b", "c", "join", "tail"):
            self.assertEqual(
                states[dependent], dag_engine_lite.NodeState.SKIPPED
            )
        self.assertEqual(
            states["independent"], dag_engine_lite.NodeState.READY
        )
        self.assertEqual(self.scheduler.next_wave(), ["independent"])

    def test_scheduler_purges_states_for_removed_nodes(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"))
        states = dict(self.scheduler.get_all_states())
        self.assertEqual(states["b"], dag_engine_lite.NodeState.READY)
        self.dag.remove_node("b")
        states = dict(self.scheduler.get_all_states())
        self.assertNotIn("b", states)
        self.assertEqual(states["a"], dag_engine_lite.NodeState.READY)

    def test_scheduler_empty_graph_is_finished(self) -> None:
        self.assertEqual(self.scheduler.next_wave(), [])
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(dict(self.scheduler.get_all_states()), {})

    # --- DAGRunner ---------------------------------------------------------

    def test_runner_empty_graph_returns_empty_report(self) -> None:
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(tuple(report.succeeded_nodes), ())
        self.assertEqual(tuple(report.failed_nodes), ())
        self.assertEqual(tuple(report.skipped_nodes), ())
        self.assertEqual(tuple(report.cancelled_nodes), ())
        self.assertEqual(dict(report.results), {})
        self.assertEqual(tuple(report.critical_path), ())
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_runner_executes_chain_successfully(self) -> None:
        self.dag.add_node("a", self._ok_action("a", "value-a"))
        self.dag.add_node("b", self._ok_action("b", "value-b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c", "value-c"), dependencies={"b"})
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
        self.assertEqual(set(report.failed_nodes), set())
        self.assertEqual(set(report.skipped_nodes), set())
        self.assertEqual(set(report.cancelled_nodes), set())
        self.assertEqual(self.executed, ["a", "b", "c"])
        self.assertEqual(report.results["a"].value, "value-a")
        self.assertEqual(report.results["b"].value, "value-b")
        self.assertEqual(report.results["c"].value, "value-c")
        self.assertEqual(
            report.results["a"].state, dag_engine_lite.NodeState.SUCCEEDED
        )
        self.assertEqual(tuple(report.critical_path), ("a", "b", "c"))
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_runner_executes_diamond_in_dependency_order(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"}, priority=1)
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"}, priority=2)
        self.dag.add_node("d", self._ok_action("d"), dependencies={"b", "c"})
        report = self.runner.run()
        self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c", "d"})
        positions = {
            node_id: index for index, node_id in enumerate(self.executed)
        }
        self.assertLess(positions["a"], positions["b"])
        self.assertLess(positions["a"], positions["c"])
        self.assertLess(positions["b"], positions["d"])
        self.assertLess(positions["c"], positions["d"])

    def test_runner_fail_fast_cancels_remaining_nodes(self) -> None:
        self.dag.add_node("a", self._fail_action("a"), priority=10)
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"))
        report = self.runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertIn("b", set(report.cancelled_nodes))
        self.assertTrue(
            {"b", "c"}
            <= set(report.cancelled_nodes) | set(report.succeeded_nodes)
        )
        self.assertEqual(set(report.results), {"a", "b", "c"})
        self.assertIsNotNone(report.results["a"].error)
        self.assertEqual(
            report.results["a"].state, dag_engine_lite.NodeState.FAILED
        )

    def test_runner_fail_fast_cancelled_results_recorded(self) -> None:
        self.dag.add_node("a", self._fail_action("a"), priority=10)
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        report = self.runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(
            report.results["b"].state, dag_engine_lite.NodeState.CANCELLED
        )

    def test_runner_skip_downstream_continues_independent_nodes(self) -> None:
        self.dag.add_node("a", self._fail_action("a"), priority=10)
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"))
        report = self.runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(set(report.skipped_nodes), {"b"})
        self.assertEqual(set(report.succeeded_nodes), {"c"})
        self.assertEqual(set(report.results), {"a", "b", "c"})

    def test_runner_continue_on_error_skips_blocked_dependents(self) -> None:
        self.dag.add_node("a", self._fail_action("a"), priority=10)
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"))
        report = self.runner.run(
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(set(report.skipped_nodes), {"b"})
        self.assertEqual(set(report.succeeded_nodes), {"c"})

    def test_runner_skip_downstream_reconvergent_dependents(self) -> None:
        self.dag.add_node("a", self._fail_action("a"), priority=10)
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"})
        self.dag.add_node("join", self._ok_action("join"), dependencies={"b", "c"})
        self.dag.add_node("tail", self._ok_action("tail"), dependencies={"join"})
        self.dag.add_node("independent", self._ok_action("independent"))
        report = self.runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(
            set(report.skipped_nodes), {"b", "c", "join", "tail"}
        )
        self.assertEqual(set(report.succeeded_nodes), {"independent"})
        self.assertEqual(
            set(report.results),
            {"a", "b", "c", "join", "tail", "independent"},
        )

    def test_runner_continue_on_error_reconvergent_dependents(self) -> None:
        self.dag.add_node("a", self._fail_action("a"), priority=10)
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_node("c", self._ok_action("c"), dependencies={"a"})
        self.dag.add_node("join", self._ok_action("join"), dependencies={"b", "c"})
        self.dag.add_node("tail", self._ok_action("tail"), dependencies={"join"})
        self.dag.add_node("independent", self._ok_action("independent"))
        report = self.runner.run(
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR
        )
        self.assertEqual(set(report.failed_nodes), {"a"})
        self.assertEqual(
            set(report.skipped_nodes), {"b", "c", "join", "tail"}
        )
        self.assertEqual(set(report.succeeded_nodes), {"independent"})
        self.assertEqual(
            set(report.results),
            {"a", "b", "c", "join", "tail", "independent"},
        )

    def test_runner_retries_until_success(self) -> None:
        attempts: List[int] = []

        def flaky() -> str:
            attempts.append(len(attempts) + 1)
            if len(attempts) < 3:
                raise RuntimeError("transient failure")
            return "recovered"

        self.dag.add_node("a", flaky, retries=3)
        report = self.runner.run()
        self.assertEqual(set(report.succeeded_nodes), {"a"})
        result = report.results["a"]
        self.assertEqual(result.state, dag_engine_lite.NodeState.SUCCEEDED)
        self.assertEqual(result.value, "recovered")
        self.assertGreaterEqual(result.retries_attempted, 1)
        self.assertGreaterEqual(len(attempts), 3)

    def test_runner_retries_exhausted_records_failure(self) -> None:
        def always_fails() -> Any:
            raise RuntimeError("permanent failure")

        self.dag.add_node("a", always_fails, retries=1)
        report = self.runner.run()
        self.assertEqual(set(report.failed_nodes), {"a"})
        result = report.results["a"]
        self.assertEqual(result.state, dag_engine_lite.NodeState.FAILED)
        self.assertIsNotNone(result.error)
        self.assertIsInstance(result.error, Exception)
        self.assertGreaterEqual(result.retries_attempted, 1)

    def test_runner_validates_cycle_before_execution(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        self.dag.add_edge("b", "a")
        with self.assertRaises(dag_engine_lite.CycleError):
            self.runner.run()
        self.assertEqual(self.executed, [])

    def test_runner_validates_missing_dependency_before_execution(self) -> None:
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        with self.assertRaises(dag_engine_lite.NodeNotFoundError):
            self.runner.run()
        self.assertEqual(self.executed, [])

    def test_runner_records_sub_second_durations(self) -> None:
        def slow_action() -> str:
            time.sleep(0.01)
            return "done"

        self.dag.add_node("a", slow_action)
        report = self.runner.run()
        self.assertEqual(set(report.succeeded_nodes), {"a"})
        result = report.results["a"]
        self.assertGreaterEqual(result.duration_seconds, 0.0)
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_runner_report_critical_path_matches_graph(self) -> None:
        self.dag.add_node("a", self._ok_action("a"))
        self.dag.add_node("b", self._ok_action("b"), dependencies={"a"})
        report = self.runner.run()
        expected_path, _ = self.dag.compute_critical_path()
        self.assertEqual(tuple(report.critical_path), tuple(expected_path))


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================


class DAGEngineSUT:
    """Aggregate SUT delegating attribute lookup across the three services."""

    tier = system

    dag: DAG
    scheduler: WaveScheduler
    runner: DAGRunner
    registry: LifecycleRegistry
    phase_scope: Any
    _services: Tuple[Any, ...]

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

    def close(self) -> None:
        self.phase_scope.__exit__(None, None, None)


def make_sut() -> DAGEngineSUT:
    """Supplies a cleanly initialized real DAG engine aggregate SUT."""
    return DAGEngineSUT()


def _compiled_fuzz_case() -> Any:
    """Builds the canonical compiled stateful case for downstream harnesses."""
    return compile_hypothesis_test_case(
        proto=proto,
        sut_factory=make_sut,
        initial_state_factory=DAGEngineState,
        name="DAGEngineCompiledFuzz",
    )


class TestDAGEngineFuzz(unittest.TestCase):
    """Bounded property fuzzing over generated acyclic graph topologies."""

    @settings(max_examples=20, deadline=None)
    @given(
        priorities=st.lists(
            st.integers(min_value=-2, max_value=2), min_size=1, max_size=6
        ),
        dependency_flags=st.lists(
            st.booleans(), min_size=6, max_size=6
        ),
        failure_policy=st.sampled_from(_FAILURE_POLICIES),
        fail_slot=st.integers(min_value=-1, max_value=5),
    )
    def test_runner_invariants_over_generated_dags(
        self,
        priorities: List[int],
        dependency_flags: List[bool],
        failure_policy: dag_engine_lite.FailurePolicy,
        fail_slot: int,
    ) -> None:
        registry = LifecycleRegistry()
        __initialize__(registry)
        scope = enter_phase(system, registry=registry)
        scope.__enter__()
        try:
            dag = get_singleton(DAG)
            scheduler = get_singleton(WaveScheduler)
            runner = get_singleton(DAGRunner)
            node_ids = [f"f{index}" for index in range(len(priorities))]
            node_id_set = set(node_ids)
            dependencies: dict[str, Tuple[str, ...]] = {}
            for index, node_id in enumerate(node_ids):
                earlier = node_ids[:index]
                dependencies[node_id] = tuple(
                    candidate
                    for candidate, flag in zip(earlier, dependency_flags)
                    if flag
                )

            executed: List[str] = []
            fail_id = (
                node_ids[fail_slot] if 0 <= fail_slot < len(node_ids) else None
            )

            def build_action(target: str, failing: bool) -> Callable[[], Any]:
                def action() -> Any:
                    executed.append(target)
                    if failing:
                        raise RuntimeError(f"node {target} failed intentionally")
                    return target

                return action

            for index, node_id in enumerate(node_ids):
                dag.add_node(
                    node_id,
                    build_action(node_id, node_id == fail_id),
                    dependencies=dependencies[node_id],
                    priority=priorities[index],
                )

            dag.validate()
            self.assertEqual(dag.all_nodes(), node_id_set)
            children: dict[str, Set[str]] = {node_id: set() for node_id in node_ids}
            for node_id in node_ids:
                for dependency in dependencies[node_id]:
                    children[dependency].add(node_id)
            self.assertEqual(
                dag.find_roots(),
                {node_id for node_id in node_ids if not dependencies[node_id]},
            )
            self.assertEqual(
                dag.find_leaves(),
                {node_id for node_id in node_ids if not children[node_id]},
            )
            for node_id in node_ids:
                self.assertEqual(
                    dag.get_dependencies(node_id), set(dependencies[node_id])
                )
                self.assertEqual(dag.get_dependents(node_id), children[node_id])

            order = dag.topological_sort()
            self.assertEqual(len(order), len(node_ids))
            self.assertEqual(set(order), node_id_set)
            positions = {
                node_id: index for index, node_id in enumerate(order)
            }
            for node_id in node_ids:
                for dependency in dependencies[node_id]:
                    self.assertLess(positions[dependency], positions[node_id])

            path, weight = dag.compute_critical_path()
            self.assertEqual(weight, float(len(path)))
            self.assertTrue(set(path) <= node_id_set)
            for upstream, downstream in zip(path, path[1:]):
                self.assertIn(upstream, set(dependencies[downstream]))

            report = runner.run(failure_policy)
            succeeded = set(report.succeeded_nodes)
            failed = set(report.failed_nodes)
            skipped = set(report.skipped_nodes)
            cancelled = set(report.cancelled_nodes)
            self.assertEqual(report.total_nodes, len(node_ids))
            self.assertEqual(
                succeeded | failed | skipped | cancelled, node_id_set
            )
            for left in (succeeded, failed, skipped, cancelled):
                for right in (succeeded, failed, skipped, cancelled):
                    if left is not right:
                        self.assertEqual(left & right, set())
            self.assertEqual(set(report.results), node_id_set)
            for node_id, result in report.results.items():
                self.assertEqual(result.node_id, node_id)
                self.assertIn(result.state, _TERMINAL_STATES)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            expected_path, _ = dag.compute_critical_path()
            self.assertEqual(tuple(report.critical_path), tuple(expected_path))
            if fail_id is not None:
                self.assertNotEqual(
                    report.results[fail_id].state,
                    dag_engine_lite.NodeState.SUCCEEDED,
                )
                if fail_id in executed:
                    self.assertEqual(
                        report.results[fail_id].state,
                        dag_engine_lite.NodeState.FAILED,
                    )
                    self.assertIsNotNone(report.results[fail_id].error)
            self.assertTrue(dict(scheduler.get_all_states()))
        finally:
            scope.__exit__(None, None, None)

    @settings(max_examples=15, deadline=None)
    @given(
        count=st.integers(min_value=1, max_value=5),
        removals=st.lists(
            st.integers(min_value=0, max_value=4), min_size=1, max_size=5
        ),
    )
    def test_scheduler_purges_removed_nodes(
        self, count: int, removals: List[int]
    ) -> None:
        registry = LifecycleRegistry()
        __initialize__(registry)
        scope = enter_phase(system, registry=registry)
        scope.__enter__()
        try:
            dag = get_singleton(DAG)
            scheduler = get_singleton(WaveScheduler)
            node_ids = [f"p{index}" for index in range(count)]
            for index, node_id in enumerate(node_ids):
                dependencies = {node_ids[index - 1]} if index else set()
                dag.add_node(node_id, lambda: None, dependencies=dependencies)
            for raw in removals:
                candidate = node_ids[raw % count]
                if dag.has_node(candidate):
                    dag.remove_node(candidate)
                states = dict(scheduler.get_all_states())
                self.assertEqual(set(states), dag.all_nodes())
                self.assertTrue(
                    all(
                        state in _TERMINAL_STATES
                        or state
                        in (
                            dag_engine_lite.NodeState.READY,
                            dag_engine_lite.NodeState.PENDING,
                        )
                        for state in states.values()
                    )
                )
        finally:
            scope.__exit__(None, None, None)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T21:26:40Z
# LAST_CHANGED: 2026-10-26T21:24:33Z
# CHANGE: Resolve feedback by adding the three missing contract assertions: (1) topological_sort now raises NodeNotFoundError for deferred missing dependencies (model transition updated to distinguish missing-dependency from cycle, with fake and real tests validating the NodeNotFoundError then successful ordering after the prerequisite is registered); (2) new fake and real tests remove a node declaring an unregistered prerequisite and then register that prerequisite, asserting its dependents/leaves are purged of the incident edge; (3) new reconvergent-topology tests for both SKIP_DOWNSTREAM and CONTINUE_ON_ERROR at scheduler and runner level, where a join node is reachable through multiple upstream paths (a->b/c->join->tail) and must transitively SKIP while an independent root stays READY and executes.
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T21:26:40Z
# PRETENSE_QA_AUDIT: 2026-10-26T21:26:17Z
# --- END CLEANROOM METADATA ---
