"""Pretense model, fake synthesis, and behavioral test suite for the DAG engine.

This module models the synchronous DAG execution and wave scheduling engine
defined by ``low/dag_engine_lite.pyi`` and concretely realized by
``lib/dag_engine_lite_impl.py`` (specified in ``low/dag_engine_lite_impl.pyi``).

The five canonical sections are:

1. Model state (:class:`DAGEngineState`) plus pure transition specifications for
   the ``DAG``, ``WaveScheduler``, and ``DAGRunner`` system-tier singletons.
2. The :data:`proto` state-machine protocol and fake synthesis helpers.
3. Deterministic unit tests exercising synthesized fakes.
4. Concrete implementation/parity tests exercising the real library classes
   inside an isolated lifecycle registry.
5. A Hypothesis stateful property test compiled from the same proto.

Contractual invariants modeled here:

* DAG ``add_node`` registers an immutable ``NodeDefinition`` and adds directed
  dependency edges from each declared dependency to the new node.
* ``add_edge`` and ``remove_node`` raise ``NodeNotFoundError`` for absent nodes.
* ``validate`` raises ``NodeNotFoundError`` for dangling dependencies and
  ``CycleError`` for directed cycles.
* ``topological_sort`` breaks ties by priority (descending) then node id
  (ascending) and raises ``CycleError`` when no complete ordering exists.
* ``find_roots``/``find_leaves`` expose in-degree-zero/out-degree-zero nodes.
* ``compute_critical_path`` returns the longest weighted dependency path and its
  cumulative weight (default weight ``1.0`` per node).
* ``WaveScheduler`` initializes roots to ``READY`` and other nodes to
  ``PENDING``, promotes newly unblocked dependents on success, and applies the
  ``FAIL_FAST``/``CONTINUE_ON_ERROR``/``SKIP_DOWNSTREAM`` policies on failure.
* ``DAGRunner.run`` executes ready waves sequentially, honors retries, applies
  the failure policy, and returns a consolidated ``DAGRunReport``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import unittest

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite as dag_spec
from benchmark_1.parts.dag_engine_lite.lib import dag_engine_lite_impl as dag_impl
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    __initialize__ as initialize_dag_engine,
)

# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================


TERMINAL_STATES = frozenset(
    {
        dag_spec.NodeState.SUCCEEDED,
        dag_spec.NodeState.FAILED,
        dag_spec.NodeState.SKIPPED,
        dag_spec.NodeState.CANCELLED,
    }
)


@dataclass
class DAGEngineState:
    """Canonical model state for the DAG, its scheduler, and its runner.

    Attributes:
        nodes: Registered node definitions keyed by node identifier.
        upstream: Direct prerequisites of each node.
        downstream: Direct dependents of each node.
        states: Scheduler execution state of each node.
        results: Recorded node execution outcomes.
    """

    nodes: Dict[str, dag_spec.NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, dag_spec.NodeState] = field(default_factory=dict)
    results: Dict[str, dag_spec.NodeResult[Any]] = field(default_factory=dict)


proto = StateMachineProto[DAGEngineState]()


def _noop() -> Any:
    """Default node action used when no callable is supplied."""
    return None


def _as_int(value: Any, default: int = 0) -> int:
    """Coerces a candidate value to an integer, falling back to ``default``."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def _as_node_id(value: Any, fallback: str) -> str:
    """Coerces a candidate node identifier to ``str``."""
    if isinstance(value, NotBoundType) or value is None:
        return fallback
    return str(value)


def _default_node_id(state: DAGEngineState) -> str:
    """Returns a deterministic node identifier from the current model state."""
    if state.nodes:
        return sorted(state.nodes)[0]
    return "missing"


def _fresh_node_id(state: DAGEngineState) -> str:
    """Returns a deterministic unused node identifier."""
    index = len(state.nodes)
    while f"node_{index}" in state.nodes:
        index += 1
    return f"node_{index}"


def _find_missing_dependency(state: DAGEngineState) -> Optional[str]:
    """Returns a dangling dependency identifier, or ``None`` when consistent."""
    for node_id in sorted(state.nodes):
        definition = state.nodes[node_id]
        for dependency in sorted(definition.dependencies):
            if dependency not in state.nodes:
                return dependency
        for dependency in sorted(state.upstream.get(node_id, set())):
            if dependency not in state.nodes:
                return dependency
    return None


def _find_cycle(state: DAGEngineState) -> Optional[Tuple[str, ...]]:
    """Returns the first directed cycle found, or ``None`` for an acyclic graph."""
    colors: Dict[str, int] = {node_id: 0 for node_id in state.nodes}
    stack: List[str] = []

    def visit(node_id: str) -> Optional[Tuple[str, ...]]:
        colors[node_id] = 1
        stack.append(node_id)
        for dependency in sorted(state.upstream.get(node_id, set())):
            if dependency not in colors:
                continue
            if colors[dependency] == 1:
                start = stack.index(dependency)
                return tuple(stack[start:] + [dependency])
            if colors[dependency] == 0:
                found = visit(dependency)
                if found is not None:
                    return found
        stack.pop()
        colors[node_id] = 2
        return None

    for node_id in sorted(state.nodes):
        if colors[node_id] == 0:
            found = visit(node_id)
            if found is not None:
                return found
    return None


def _topological_order(state: DAGEngineState) -> Optional[List[str]]:
    """Computes a priority-aware deterministic topological order.

    Returns ``None`` when the graph is not completely orderable (a cycle or a
    dangling prerequisite exists).
    """
    in_degree: Dict[str, int] = {
        node_id: len(state.upstream.get(node_id, set())) for node_id in state.nodes
    }
    ready: List[str] = [node_id for node_id in state.nodes if in_degree[node_id] == 0]
    order: List[str] = []

    while ready:
        ready.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
        node_id = ready.pop(0)
        order.append(node_id)
        for dependent in sorted(state.downstream.get(node_id, set())):
            if dependent not in in_degree:
                continue
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)

    if len(order) != len(state.nodes):
        return None
    return order


def _critical_path(
    state: DAGEngineState, estimated_durations: Optional[Mapping[str, float]] = None
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the model graph."""
    order = _topological_order(state)
    if not order:
        return ([], 0.0)

    earliest: Dict[str, float] = {}
    predecessor: Dict[str, Optional[str]] = {}

    for node_id in order:
        best_time = 0.0
        best_predecessor: Optional[str] = None
        for dependency in sorted(state.upstream.get(node_id, set())):
            if dependency not in earliest:
                continue
            candidate = earliest[dependency]
            if candidate > best_time:
                best_time = candidate
                best_predecessor = dependency
        duration = 1.0
        if estimated_durations is not None:
            raw = estimated_durations.get(node_id, 1.0)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                duration = float(raw)
        earliest[node_id] = best_time + duration
        predecessor[node_id] = best_predecessor

    end_node: Optional[str] = None
    end_time = -1.0
    for node_id in order:
        if earliest[node_id] > end_time:
            end_time = earliest[node_id]
            end_node = node_id

    path: List[str] = []
    current = end_node
    while current is not None:
        path.append(current)
        current = predecessor[current]
    path.reverse()
    return (path, max(end_time, 0.0))


def _sync_states(state: DAGEngineState) -> None:
    """Registers newly discovered nodes as ``READY`` roots or ``PENDING`` nodes."""
    for node_id in state.nodes:
        if node_id not in state.states:
            if state.upstream.get(node_id):
                state.states[node_id] = dag_spec.NodeState.PENDING
            else:
                state.states[node_id] = dag_spec.NodeState.READY


def _promote_dependents(state: DAGEngineState, node_id: str) -> None:
    """Promotes blocked dependents whose prerequisites have all succeeded."""
    for dependent in sorted(state.downstream.get(node_id, set())):
        if dependent not in state.nodes:
            continue
        if state.states.get(dependent) is not dag_spec.NodeState.PENDING:
            continue
        prerequisites = state.upstream.get(dependent, set())
        if all(
            state.states.get(prerequisite) is dag_spec.NodeState.SUCCEEDED
            for prerequisite in prerequisites
        ):
            state.states[dependent] = dag_spec.NodeState.READY


def _ready_wave(state: DAGEngineState) -> List[str]:
    """Returns the next wave of ``READY`` nodes with all prerequisites met."""
    _sync_states(state)
    candidates: List[str] = []
    for node_id in state.nodes:
        if state.states.get(node_id) is not dag_spec.NodeState.READY:
            continue
        prerequisites = state.upstream.get(node_id, set())
        if all(
            state.states.get(prerequisite) is dag_spec.NodeState.SUCCEEDED
            for prerequisite in prerequisites
        ):
            candidates.append(node_id)
    candidates.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    return candidates


def _is_finished(state: DAGEngineState) -> bool:
    """Reports whether every model node has reached a terminal state."""
    _sync_states(state)
    return all(
        state.states.get(node_id) in TERMINAL_STATES for node_id in state.nodes
    )


def _apply_failure_policy(
    state: DAGEngineState, node_id: str, policy: dag_spec.FailurePolicy
) -> None:
    """Applies the contracted failure policy to the model scheduler state."""
    if policy is dag_spec.FailurePolicy.FAIL_FAST:
        for other_id in sorted(state.states):
            if state.states.get(other_id) not in TERMINAL_STATES:
                state.states[other_id] = dag_spec.NodeState.CANCELLED
        return

    if policy is dag_spec.FailurePolicy.SKIP_DOWNSTREAM:
        pending: List[str] = sorted(state.downstream.get(node_id, set()))
        visited: Set[str] = set()
        while pending:
            dependent = pending.pop(0)
            if dependent in visited or dependent not in state.nodes:
                continue
            visited.add(dependent)
            if (
                dependent in state.states
                and state.states.get(dependent) not in TERMINAL_STATES
            ):
                state.states[dependent] = dag_spec.NodeState.SKIPPED
            pending.extend(sorted(state.downstream.get(dependent, set())))


def _simulate_run(
    state: DAGEngineState, policy: dag_spec.FailurePolicy
) -> dag_spec.DAGRunReport:
    """Simulates a complete sequential run over the model graph."""
    missing = _find_missing_dependency(state)
    if missing is not None:
        raise dag_spec.NodeNotFoundError(
            f"dependency node {missing!r} is not registered", missing
        )
    cycle = _find_cycle(state)
    if cycle is not None:
        raise dag_spec.CycleError("dependency cycle detected", cycle)

    _sync_states(state)
    budget = len(state.nodes) * 4 + 4

    while budget > 0 and not _is_finished(state):
        budget -= 1
        wave = _ready_wave(state)
        if not wave:
            break
        failed_in_wave = False
        for node_id in wave:
            state.states[node_id] = dag_spec.NodeState.RUNNING
            definition = state.nodes[node_id]
            attempts = 0
            value: Any = None
            while True:
                try:
                    value = definition.action()
                except Exception as exc:  # noqa: BLE001 - mirrored engine behavior
                    if attempts < definition.retries:
                        attempts += 1
                        continue
                    state.states[node_id] = dag_spec.NodeState.FAILED
                    state.results[node_id] = dag_spec.NodeResult(
                        node_id,
                        dag_spec.NodeState.FAILED,
                        None,
                        exc,
                        0.0,
                        attempts,
                    )
                    _apply_failure_policy(state, node_id, policy)
                    failed_in_wave = True
                    break
                else:
                    state.states[node_id] = dag_spec.NodeState.SUCCEEDED
                    state.results[node_id] = dag_spec.NodeResult(
                        node_id,
                        dag_spec.NodeState.SUCCEEDED,
                        value,
                        None,
                        0.0,
                        attempts,
                    )
                    _promote_dependents(state, node_id)
                    break
            if failed_in_wave and policy is dag_spec.FailurePolicy.FAIL_FAST:
                break
        if failed_in_wave and policy is dag_spec.FailurePolicy.FAIL_FAST:
            break

    for node_id in sorted(state.nodes):
        node_state = state.states.get(node_id, dag_spec.NodeState.PENDING)
        if node_id not in state.results and node_state in TERMINAL_STATES:
            state.results[node_id] = dag_spec.NodeResult(node_id, node_state)

    succeeded = tuple(
        sorted(
            node_id
            for node_id, result in state.results.items()
            if result.state is dag_spec.NodeState.SUCCEEDED
        )
    )
    failed = tuple(
        sorted(
            node_id
            for node_id, result in state.results.items()
            if result.state is dag_spec.NodeState.FAILED
        )
    )
    skipped = tuple(
        sorted(
            node_id
            for node_id, result in state.results.items()
            if result.state is dag_spec.NodeState.SKIPPED
        )
    )
    cancelled = tuple(
        sorted(
            node_id
            for node_id, result in state.results.items()
            if result.state is dag_spec.NodeState.CANCELLED
        )
    )
    path, _weight = _critical_path(state, None)
    return dag_spec.DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded,
        failed_nodes=failed,
        skipped_nodes=skipped,
        cancelled_nodes=cancelled,
        wall_clock_seconds=0.0,
        critical_path=tuple(path),
        results=dict(state.results),
    )


# ------------------------------------------------------------------------------
# DAG transitions
# ------------------------------------------------------------------------------


@proto.transition(dag_impl.DAG.add_node)
def add_node() -> None:
    pass


@add_node.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    action: Any | NotBoundType = NotBound,
    dependencies: Any | NotBoundType = NotBound,
    priority: Any | NotBoundType = NotBound,
    retries: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_id = (
        _fresh_node_id(state)
        if isinstance(node_id, NotBoundType) or node_id is None
        else str(node_id)
    )
    resolved_action: Callable[[], Any] = action if callable(action) else _noop
    if isinstance(dependencies, NotBoundType) or dependencies is None:
        resolved_dependencies: Optional[Tuple[str, ...]] = None
    else:
        try:
            resolved_dependencies = tuple(str(item) for item in dependencies)
        except TypeError:
            resolved_dependencies = None
    resolved_priority = _as_int(priority, 0)
    resolved_retries = max(0, _as_int(retries, 0))
    return (
        resolved_id,
        resolved_action,
        resolved_dependencies,
        resolved_priority,
        resolved_retries,
    )


@add_node.returns
def _(
    state: DAGEngineState,
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
    state: DAGEngineState,
    this: Any,
    node_id: str,
    action: Callable[[], Any],
    dependencies: Optional[Collection[str]],
    priority: int,
    retries: int,
    result: Any,
) -> None:
    frozen_dependencies = frozenset(dependencies or ())
    state.nodes[node_id] = dag_spec.NodeDefinition(
        node_id=node_id,
        action=action,
        dependencies=frozen_dependencies,
        priority=priority,
        retries=retries,
    )
    state.upstream.setdefault(node_id, set())
    state.downstream.setdefault(node_id, set())
    for dependency in frozen_dependencies:
        state.upstream[node_id].add(dependency)
        state.downstream.setdefault(dependency, set()).add(node_id)


@proto.transition(dag_impl.DAG.add_edge)
def add_edge() -> None:
    pass


@add_edge.arguments
def _(
    state: DAGEngineState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_upstream = _as_node_id(upstream_id, _default_node_id(state))
    resolved_downstream = _as_node_id(downstream_id, _default_node_id(state))
    return (resolved_upstream, resolved_downstream)


@add_edge.returns
def _(
    state: DAGEngineState,
    this: Any,
    upstream_id: str,
    downstream_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    for candidate in (upstream_id, downstream_id):
        if candidate not in state.nodes:
            return Raised(
                dag_spec.NodeNotFoundError(
                    f"node {candidate!r} is not registered", candidate
                )
            )
    return Value(None)


@add_edge.provide
def _(
    state: DAGEngineState,
    this: Any,
    upstream_id: str,
    downstream_id: str,
    result: Any,
) -> None:
    state.upstream.setdefault(downstream_id, set()).add(upstream_id)
    state.downstream.setdefault(upstream_id, set()).add(downstream_id)


@proto.transition(dag_impl.DAG.remove_node)
def remove_node() -> None:
    pass


@remove_node.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@remove_node.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if node_id not in state.nodes:
        return Raised(
            dag_spec.NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        )
    return Value(None)


@remove_node.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    for dependency in sorted(state.upstream.get(node_id, set())):
        state.downstream.get(dependency, set()).discard(node_id)
    for dependent in sorted(state.downstream.get(node_id, set())):
        state.upstream.get(dependent, set()).discard(node_id)
    state.upstream.pop(node_id, None)
    state.downstream.pop(node_id, None)
    state.nodes.pop(node_id, None)
    state.states.pop(node_id, None)
    state.results.pop(node_id, None)


@proto.transition(dag_impl.DAG.has_node)
def has_node() -> None:
    pass


@has_node.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@has_node.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(node_id in state.nodes)


@has_node.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    return None


@proto.transition(dag_impl.DAG.get_node)
def get_node() -> None:
    pass


@get_node.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@get_node.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if node_id not in state.nodes:
        return Raised(
            dag_spec.NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        )
    return Value(state.nodes[node_id])


@get_node.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    return None


@proto.transition(dag_impl.DAG.get_dependencies)
def get_dependencies() -> None:
    pass


@get_dependencies.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@get_dependencies.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if node_id not in state.nodes:
        return Raised(
            dag_spec.NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        )
    return Value(set(state.upstream.get(node_id, set())))


@get_dependencies.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    return None


@proto.transition(dag_impl.DAG.get_dependents)
def get_dependents() -> None:
    pass


@get_dependents.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@get_dependents.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    if node_id not in state.nodes:
        return Raised(
            dag_spec.NodeNotFoundError(f"node {node_id!r} is not registered", node_id)
        )
    return Value(set(state.downstream.get(node_id, set())))


@get_dependents.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    return None


@proto.transition(dag_impl.DAG.all_nodes)
def all_nodes() -> None:
    pass


@all_nodes.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@all_nodes.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(set(state.nodes))


@all_nodes.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.DAG.validate)
def validate() -> None:
    pass


@validate.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@validate.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    missing = _find_missing_dependency(state)
    if missing is not None:
        return Raised(
            dag_spec.NodeNotFoundError(
                f"dependency node {missing!r} is not registered", missing
            )
        )
    cycle = _find_cycle(state)
    if cycle is not None:
        return Raised(dag_spec.CycleError("dependency cycle detected", cycle))
    return Value(None)


@validate.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.DAG.topological_sort)
def topological_sort() -> None:
    pass


@topological_sort.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@topological_sort.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    order = _topological_order(state)
    if order is None:
        cycle = _find_cycle(state)
        if cycle is None:
            missing = _find_missing_dependency(state)
            if missing is not None:
                cycle = (missing,)
            else:
                cycle = tuple(sorted(state.nodes))
        return Raised(dag_spec.CycleError("dependency cycle detected", cycle))
    return Value(order)


@topological_sort.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.DAG.find_roots)
def find_roots() -> None:
    pass


@find_roots.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@find_roots.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(
        {node_id for node_id in state.nodes if not state.upstream.get(node_id)}
    )


@find_roots.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.DAG.find_leaves)
def find_leaves() -> None:
    pass


@find_leaves.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@find_leaves.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(
        {node_id for node_id in state.nodes if not state.downstream.get(node_id)}
    )


@find_leaves.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.DAG.compute_critical_path)
def compute_critical_path() -> None:
    pass


@compute_critical_path.arguments
def _(
    state: DAGEngineState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(estimated_durations, NotBoundType) or estimated_durations is None:
        resolved: Optional[Dict[str, float]] = None
    elif isinstance(estimated_durations, Mapping):
        resolved = {
            str(key): float(value)
            for key, value in estimated_durations.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
    else:
        resolved = None
    return (resolved,)


@compute_critical_path.returns
def _(
    state: DAGEngineState,
    this: Any,
    estimated_durations: Optional[Mapping[str, float]],
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    missing = _find_missing_dependency(state)
    if missing is not None:
        return Raised(
            dag_spec.NodeNotFoundError(
                f"dependency node {missing!r} is not registered", missing
            )
        )
    cycle = _find_cycle(state)
    if cycle is not None:
        return Raised(dag_spec.CycleError("dependency cycle detected", cycle))
    path, weight = _critical_path(state, estimated_durations)
    return Value((path, weight))


@compute_critical_path.provide
def _(
    state: DAGEngineState,
    this: Any,
    estimated_durations: Optional[Mapping[str, float]],
    result: Any,
) -> None:
    return None


# ------------------------------------------------------------------------------
# WaveScheduler transitions
# ------------------------------------------------------------------------------


@proto.transition(dag_impl.WaveScheduler.next_wave)
def next_wave() -> None:
    pass


@next_wave.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@next_wave.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(_ready_wave(state))


@next_wave.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.WaveScheduler.mark_running)
def mark_running() -> None:
    pass


@mark_running.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@mark_running.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(None)


@mark_running.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    state.states[node_id] = dag_spec.NodeState.RUNNING


@proto.transition(dag_impl.WaveScheduler.mark_succeeded)
def mark_succeeded() -> None:
    pass


@mark_succeeded.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@mark_succeeded.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(None)


@mark_succeeded.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    state.states[node_id] = dag_spec.NodeState.SUCCEEDED
    _promote_dependents(state, node_id)


@proto.transition(dag_impl.WaveScheduler.mark_failed)
def mark_failed() -> None:
    pass


@mark_failed.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_id = _as_node_id(node_id, _default_node_id(state))
    resolved_policy = (
        failure_policy
        if isinstance(failure_policy, dag_spec.FailurePolicy)
        else dag_spec.FailurePolicy.FAIL_FAST
    )
    return (resolved_id, resolved_policy)


@mark_failed.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    failure_policy: dag_spec.FailurePolicy,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(None)


@mark_failed.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    failure_policy: dag_spec.FailurePolicy,
    result: Any,
) -> None:
    state.states[node_id] = dag_spec.NodeState.FAILED
    _apply_failure_policy(state, node_id, failure_policy)


@proto.transition(dag_impl.WaveScheduler.is_finished)
def is_finished() -> None:
    pass


@is_finished.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@is_finished.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    return Value(_is_finished(state))


@is_finished.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


@proto.transition(dag_impl.WaveScheduler.get_state)
def get_state() -> None:
    pass


@get_state.arguments
def _(
    state: DAGEngineState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_as_node_id(node_id, _default_node_id(state)),)


@get_state.returns
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    _sync_states(state)
    if node_id not in state.states:
        return Raised(KeyError(node_id))
    return Value(state.states[node_id])


@get_state.provide
def _(
    state: DAGEngineState,
    this: Any,
    node_id: str,
    result: Any,
) -> None:
    return None


@proto.transition(dag_impl.WaveScheduler.get_all_states)
def get_all_states() -> None:
    pass


@get_all_states.arguments
def _(state: DAGEngineState, this: Any) -> Optional[Tuple[Any, ...]]:
    return ()


@get_all_states.returns
def _(
    state: DAGEngineState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    _sync_states(state)
    return Value(dict(state.states))


@get_all_states.provide
def _(state: DAGEngineState, this: Any, result: Any) -> None:
    return None


# ------------------------------------------------------------------------------
# DAGRunner transitions
# ------------------------------------------------------------------------------


@proto.transition(dag_impl.DAGRunner.run)
def run() -> None:
    pass


@run.arguments
def _(
    state: DAGEngineState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved_policy = (
        failure_policy
        if isinstance(failure_policy, dag_spec.FailurePolicy)
        else dag_spec.FailurePolicy.FAIL_FAST
    )
    return (resolved_policy,)


@run.returns
def _(
    state: DAGEngineState,
    this: Any,
    failure_policy: dag_spec.FailurePolicy,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is not NotBound:
        return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)
    # A full run report carries wall-clock measurements that cannot be modelled
    # deterministically; the state mutations produced by ``provide`` capture the
    # contracted observable behavior instead.
    return None


@run.provide
def _(
    state: DAGEngineState,
    this: Any,
    failure_policy: dag_spec.FailurePolicy,
    result: Any,
) -> None:
    _simulate_run(state, failure_policy)


# ==============================================================================
# 2. State Machine Proto & Fake Synthesis
# ==============================================================================


def make_dag_engine_state() -> DAGEngineState:
    """Creates a fresh model state instance."""
    return DAGEngineState()


def make_dag_engine_fakes(
    state: DAGEngineState,
) -> Tuple[Any, Any, Any]:
    """Synthesizes fake DAG, WaveScheduler, and DAGRunner sharing one model."""
    return (
        proto.make_state_machine(state).as_fake(dag_impl.DAG),
        proto.make_state_machine(state).as_fake(dag_impl.WaveScheduler),
        proto.make_state_machine(state).as_fake(dag_impl.DAGRunner),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================


class TestDAGEngineUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to the state machine specification."""

    def setUp(self) -> None:
        self.state = make_dag_engine_state()
        self.dag, self.scheduler, self.runner = make_dag_engine_fakes(self.state)

    def test_fake_initial_state(self) -> None:
        self.assertEqual(self.dag.all_nodes(), set())
        self.assertEqual(self.dag.find_roots(), set())
        self.assertEqual(self.dag.find_leaves(), set())
        self.assertTrue(self.scheduler.is_finished())

    def test_add_node_registers_definition(self) -> None:
        self.dag.add_node("a", _noop, priority=3, retries=1)
        self.assertTrue(self.dag.has_node("a"))
        self.assertEqual(self.dag.all_nodes(), {"a"})
        definition = self.dag.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertEqual(definition.priority, 3)
        self.assertEqual(definition.retries, 1)
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(self.dag.get_dependencies("a"), set())
        self.assertEqual(self.dag.get_dependents("a"), set())

    def test_add_node_with_dependencies(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})

    def test_add_edge_missing_node_raises(self) -> None:
        self.dag.add_node("a", _noop)
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.add_edge("a", "b")
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.add_edge("b", "a")

    def test_add_edge_updates_adjacency(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_remove_node_missing_raises(self) -> None:
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.remove_node("missing")

    def test_remove_node_clears_incident_edges(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependencies("b"), set())
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.get_node("a")

    def test_remove_node_with_prerequisites_and_dependents_clears_all_edges(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.add_node("c", _noop, dependencies=["b"])
        self.dag.add_node("d", _noop, dependencies=["b"])
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a", "c", "d"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertEqual(self.dag.get_dependencies("d"), set())
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.get_dependents("b")

    def test_validate_missing_dependency_raises(self) -> None:
        self.dag.add_node("b", _noop, dependencies=["a"])
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.validate()

    def test_validate_cycle_raises(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        with self.assertRaises(dag_spec.CycleError):
            self.dag.validate()
        with self.assertRaises(dag_spec.CycleError):
            self.dag.topological_sort()

    def test_topological_sort_priority_and_name_tie_break(self) -> None:
        self.dag.add_node("a", _noop, priority=0)
        self.dag.add_node("b", _noop, dependencies=["a"], priority=1)
        self.dag.add_node("c", _noop, priority=2)
        self.dag.add_node("d", _noop, priority=0)
        self.assertEqual(self.dag.topological_sort(), ["c", "a", "b", "d"])

    def test_compute_critical_path_default_weights(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.add_node("c", _noop, dependencies=["b"])
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 3.0)

    def test_compute_critical_path_custom_weights(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        path, weight = self.dag.compute_critical_path({"a": 1.5, "b": 2.5})
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 4.0)

    def test_scheduler_next_wave_orders_by_priority(self) -> None:
        self.dag.add_node("a", _noop, priority=0)
        self.dag.add_node("b", _noop, priority=5)
        self.dag.add_node("c", _noop, dependencies=["a", "b"])
        self.assertEqual(self.scheduler.next_wave(), ["b", "a"])
        self.assertEqual(
            self.scheduler.get_state("c"), dag_spec.NodeState.PENDING
        )

    def test_scheduler_get_state_before_any_transition_initializes_states(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        # No preceding next_wave/mark_* call: get_state must synchronize.
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.READY)
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.PENDING)

    def test_scheduler_mark_succeeded_unlocks_dependents(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.RUNNING)
        self.scheduler.mark_succeeded("a")
        self.assertEqual(
            self.scheduler.get_state("a"), dag_spec.NodeState.SUCCEEDED
        )
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["b"])

    def test_scheduler_mark_succeeded_skips_already_terminal_dependents(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.add_node("c", _noop, dependencies=["a"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed("c", dag_spec.FailurePolicy.CONTINUE_ON_ERROR)
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.READY)
        self.assertEqual(self.scheduler.get_state("c"), dag_spec.NodeState.FAILED)

    def test_scheduler_fail_fast_cancels_remaining(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed("a", dag_spec.FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.FAILED)
        self.assertEqual(
            self.scheduler.get_state("b"), dag_spec.NodeState.CANCELLED
        )
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_skip_downstream_marks_transitive_dependents(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.add_node("c", _noop, dependencies=["b"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed(
            "a", dag_spec.FailurePolicy.SKIP_DOWNSTREAM
        )
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("c"), dag_spec.NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_skip_downstream_multiple_paths_skips_each_once(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.add_node("c", _noop, dependencies=["a"])
        self.dag.add_node("d", _noop, dependencies=["b", "c"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed(
            "a", dag_spec.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.scheduler.get_all_states()
        self.assertEqual(states["b"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(states["c"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(states["d"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(
            list(states.values()).count(dag_spec.NodeState.SKIPPED), 3
        )
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_continue_on_error_keeps_independent_nodes(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop)
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed(
            "a", dag_spec.FailurePolicy.CONTINUE_ON_ERROR
        )
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())

    def test_scheduler_get_all_states_tracks_nodes(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        states = self.scheduler.get_all_states()
        self.assertEqual(states["a"], dag_spec.NodeState.READY)
        self.assertEqual(states["b"], dag_spec.NodeState.PENDING)

    def test_remove_node_after_scheduler_sync_reports_only_registered_nodes(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.scheduler.get_all_states()  # synchronize before removal
        self.dag.remove_node("b")
        states = self.scheduler.get_all_states()
        self.assertEqual(set(states.keys()), self.dag.all_nodes())
        self.assertEqual(set(states.keys()), {"a"})
        self.assertNotIn("b", states)

    def test_runner_success_report(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.runner.run()
        self.assertEqual(self.state.results["a"].state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(self.state.results["a"].value, 1)
        self.assertEqual(self.state.results["b"].state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(self.state.results["b"].value, 2)
        self.assertEqual(self.state.states["a"], dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(self.state.states["b"], dag_spec.NodeState.SUCCEEDED)

    def test_runner_retries_failed_action(self) -> None:
        calls = {"count": 0}

        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("transient")
            return "recovered"

        self.dag.add_node("a", flaky, retries=2)
        self.runner.run()
        result = self.state.results["a"]
        self.assertEqual(result.state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(result.value, "recovered")
        self.assertEqual(calls["count"], 3)
        self.assertEqual(result.retries_attempted, 2)

    def test_runner_fail_fast_cancels_remaining(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.runner.run(dag_spec.FailurePolicy.FAIL_FAST)
        self.assertEqual(self.state.results["a"].state, dag_spec.NodeState.FAILED)
        self.assertEqual(self.state.states["b"], dag_spec.NodeState.CANCELLED)

    def test_runner_skip_downstream_skips_dependents(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.dag.add_node("c", _noop, dependencies=["b"])
        self.runner.run(dag_spec.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.state.results["a"].state, dag_spec.NodeState.FAILED)
        self.assertEqual(self.state.states["b"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(self.state.states["c"], dag_spec.NodeState.SKIPPED)

    def test_runner_continue_on_error_runs_independent_nodes(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", lambda: "ok")
        self.runner.run(dag_spec.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.state.results["a"].state, dag_spec.NodeState.FAILED)
        self.assertEqual(self.state.results["b"].state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(self.state.results["b"].value, "ok")

    def test_runner_continue_on_error_leaves_blocked_dependent_unexecuted(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", _noop, dependencies=["a"])
        self.runner.run(dag_spec.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.state.results["a"].state, dag_spec.NodeState.FAILED)
        self.assertEqual(self.state.states["b"], dag_spec.NodeState.PENDING)
        self.assertNotIn("b", self.state.results)


# ==============================================================================
# 4. Concrete Implementation Tests & Parity
# ==============================================================================


class TestDAGEngineImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        initialize_dag_engine(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(dag_spec.DAG)
        self.scheduler = get_singleton(dag_spec.WaveScheduler)
        self.runner = get_singleton(dag_spec.DAGRunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    @staticmethod
    def _noop() -> Any:
        return None

    # -- DAG structural operations -------------------------------------------------

    def test_real_add_and_query_nodes(self) -> None:
        self.dag.add_node("a", self._noop, priority=2, retries=1)
        self.assertTrue(self.dag.has_node("a"))
        self.assertFalse(self.dag.has_node("missing"))
        self.assertEqual(self.dag.all_nodes(), {"a"})
        definition = self.dag.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(definition.priority, 2)
        self.assertEqual(definition.retries, 1)
        self.assertEqual(self.dag.get_dependencies("a"), set())
        self.assertEqual(self.dag.get_dependents("a"), set())

    def test_real_add_node_with_dependencies(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"], priority=1)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.get_node("b").dependencies, frozenset({"a"}))
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})

    def test_real_add_edge(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_real_add_edge_missing_node_raises(self) -> None:
        self.dag.add_node("a", self._noop)
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.add_edge("a", "missing")
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.add_edge("missing", "a")

    def test_real_remove_node(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.all_nodes(), {"b"})
        self.assertEqual(self.dag.get_dependencies("b"), set())

    def test_real_remove_node_with_prerequisites_and_dependents(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["b"])
        self.dag.add_node("d", self._noop, dependencies=["b"])
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a", "c", "d"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertEqual(self.dag.get_dependencies("d"), set())
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.get_dependents("b")

    def test_real_remove_missing_node_raises(self) -> None:
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.remove_node("missing")

    def test_real_get_missing_node_raises(self) -> None:
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_real_validate_accepts_acyclic_graph(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.assertIsNone(self.dag.validate())

    def test_real_validate_missing_dependency_raises(self) -> None:
        self.dag.add_node("b", self._noop, dependencies=["a"])
        with self.assertRaises(dag_spec.NodeNotFoundError):
            self.dag.validate()

    def test_real_validate_cycle_raises(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        with self.assertRaises(dag_spec.CycleError):
            self.dag.validate()
        with self.assertRaises(dag_spec.CycleError):
            self.dag.topological_sort()

    def test_real_topological_sort_ordering(self) -> None:
        self.dag.add_node("a", self._noop, priority=0)
        self.dag.add_node("b", self._noop, dependencies=["a"], priority=1)
        self.dag.add_node("c", self._noop, priority=2)
        self.dag.add_node("d", self._noop, priority=0)
        self.assertEqual(self.dag.topological_sort(), ["c", "a", "b", "d"])
        for node_id in self.dag.all_nodes():
            position = self.dag.topological_sort().index(node_id)
            for dependency in self.dag.get_dependencies(node_id):
                self.assertLess(
                    self.dag.topological_sort().index(dependency), position
                )

    def test_real_find_roots_and_leaves(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop)
        self.dag.add_node("c", self._noop, dependencies=["a", "b"])
        self.assertEqual(self.dag.find_roots(), {"a", "b"})
        self.assertEqual(self.dag.find_leaves(), {"c"})

    def test_real_compute_critical_path_default_weights(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["b"])
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 3.0)

    def test_real_compute_critical_path_custom_weights(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["a"])
        path, weight = self.dag.compute_critical_path({"a": 1.0, "b": 2.0, "c": 5.0})
        self.assertEqual(path, ["a", "c"])
        self.assertEqual(weight, 6.0)

    # -- WaveScheduler operations --------------------------------------------------

    def test_real_scheduler_initial_wave(self) -> None:
        self.dag.add_node("a", self._noop, priority=0)
        self.dag.add_node("b", self._noop, priority=5)
        self.dag.add_node("c", self._noop, dependencies=["a", "b"])
        self.assertEqual(self.scheduler.next_wave(), ["b", "a"])
        self.assertEqual(self.scheduler.get_state("c"), dag_spec.NodeState.PENDING)

    def test_real_scheduler_get_state_before_any_transition(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        # No preceding scheduler transition: get_state must synchronize itself.
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.READY)
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.PENDING)

    def test_real_scheduler_mark_succeeded_unlocks(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.RUNNING)
        self.scheduler.mark_succeeded("a")
        self.assertEqual(
            self.scheduler.get_state("a"), dag_spec.NodeState.SUCCEEDED
        )
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["b"])

    def test_real_scheduler_mark_succeeded_only_promotes_pending(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["a"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed("c", dag_spec.FailurePolicy.CONTINUE_ON_ERROR)
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.READY)
        self.assertEqual(self.scheduler.get_state("c"), dag_spec.NodeState.FAILED)

    def test_real_scheduler_fail_fast(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed("a", dag_spec.FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.FAILED)
        self.assertEqual(
            self.scheduler.get_state("b"), dag_spec.NodeState.CANCELLED
        )
        self.assertTrue(self.scheduler.is_finished())

    def test_real_scheduler_skip_downstream(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["b"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed(
            "a", dag_spec.FailurePolicy.SKIP_DOWNSTREAM
        )
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.SKIPPED)
        self.assertEqual(self.scheduler.get_state("c"), dag_spec.NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_real_scheduler_skip_downstream_multiple_paths(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["a"])
        self.dag.add_node("d", self._noop, dependencies=["b", "c"])
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed(
            "a", dag_spec.FailurePolicy.SKIP_DOWNSTREAM
        )
        states = self.scheduler.get_all_states()
        self.assertEqual(states["b"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(states["c"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(states["d"], dag_spec.NodeState.SKIPPED)
        self.assertEqual(
            list(states.values()).count(dag_spec.NodeState.SKIPPED), 3
        )
        self.assertTrue(self.scheduler.is_finished())

    def test_real_scheduler_continue_on_error(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop)
        self.scheduler.next_wave()  # synchronize scheduler state
        self.scheduler.mark_failed(
            "a", dag_spec.FailurePolicy.CONTINUE_ON_ERROR
        )
        self.assertEqual(self.scheduler.get_state("a"), dag_spec.NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())

    def test_real_scheduler_empty_graph_finished(self) -> None:
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.next_wave(), [])
        self.assertEqual(self.scheduler.get_all_states(), {})

    def test_real_scheduler_get_all_states(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        states = self.scheduler.get_all_states()
        self.assertEqual(states["a"], dag_spec.NodeState.READY)
        self.assertEqual(states["b"], dag_spec.NodeState.PENDING)

    def test_real_remove_node_after_scheduler_sync_reports_only_registered(self) -> None:
        self.dag.add_node("a", self._noop)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.scheduler.get_all_states()  # synchronize before removal
        self.dag.remove_node("b")
        states = self.scheduler.get_all_states()
        self.assertEqual(set(states.keys()), self.dag.all_nodes())
        self.assertEqual(set(states.keys()), {"a"})
        self.assertNotIn("b", states)

    # -- DAGRunner operations ------------------------------------------------------

    def test_real_runner_success(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("a", "b"))
        self.assertEqual(report.failed_nodes, ())
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(report.results["a"].state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].value, 1)
        self.assertEqual(report.results["b"].state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(report.results["b"].value, 2)
        self.assertEqual(tuple(report.critical_path), ("a", "b"))

    def test_real_runner_retries_then_succeeds(self) -> None:
        calls = {"count": 0}

        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("transient")
            return "recovered"

        self.dag.add_node("a", flaky, retries=2)
        report = self.runner.run()
        self.assertEqual(report.results["a"].state, dag_spec.NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].value, "recovered")
        self.assertEqual(calls["count"], 3)

    def test_real_runner_fail_fast(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        report = self.runner.run(dag_spec.FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(
            report.results["a"].state, dag_spec.NodeState.FAILED
        )
        self.assertIsNotNone(report.results["a"].error)

    def test_real_runner_skip_downstream(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        self.dag.add_node("c", self._noop, dependencies=["b"])
        report = self.runner.run(dag_spec.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertIn("b", report.skipped_nodes)
        self.assertIn("c", report.skipped_nodes)
        self.assertEqual(
            report.results["b"].state, dag_spec.NodeState.SKIPPED
        )

    def test_real_runner_continue_on_error(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", lambda: "ok")
        report = self.runner.run(dag_spec.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.succeeded_nodes, ("b",))
        self.assertEqual(report.results["b"].value, "ok")

    def test_real_runner_continue_on_error_blocked_dependent_unexecuted(self) -> None:
        def boom() -> Any:
            raise RuntimeError("boom")

        self.dag.add_node("a", boom)
        self.dag.add_node("b", self._noop, dependencies=["a"])
        report = self.runner.run(dag_spec.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(self.scheduler.get_state("b"), dag_spec.NodeState.PENDING)
        self.assertNotIn("b", report.results)

    def test_real_runner_empty_graph(self) -> None:
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(tuple(report.critical_path), ())

    # -- Fake/real parity ----------------------------------------------------------

    def test_parity_graph_queries(self) -> None:
        model = make_dag_engine_state()
        fake, _scheduler, _runner = make_dag_engine_fakes(model)
        for target in (fake, self.dag):
            target.add_node("a", self._noop, priority=1)
            target.add_node("b", self._noop, dependencies=["a"], priority=2)
            target.add_node("c", self._noop, priority=0)

        self.assertEqual(fake.all_nodes(), self.dag.all_nodes())
        self.assertEqual(fake.find_roots(), self.dag.find_roots())
        self.assertEqual(fake.find_leaves(), self.dag.find_leaves())
        self.assertEqual(fake.topological_sort(), self.dag.topological_sort())
        self.assertEqual(fake.get_dependencies("b"), self.dag.get_dependencies("b"))
        self.assertEqual(fake.get_dependents("a"), self.dag.get_dependents("a"))

    def test_parity_scheduler_states(self) -> None:
        model = make_dag_engine_state()
        fake_dag, fake_scheduler, _runner = make_dag_engine_fakes(model)
        for target in (fake_dag, self.dag):
            target.add_node("a", self._noop)
            target.add_node("b", self._noop, dependencies=["a"])

        self.assertEqual(
            fake_scheduler.next_wave(), self.scheduler.next_wave()
        )
        fake_scheduler.mark_succeeded("a")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(
            fake_scheduler.get_state("b"), self.scheduler.get_state("b")
        )
        self.assertEqual(
            fake_scheduler.get_all_states(), self.scheduler.get_all_states()
        )


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================


class DAGEngineSUT:
    """Aggregate SUT exposing the DAG module's singleton services.

    The DAG, WaveScheduler, and DAGRunner singletons are created in one isolated
    lifecycle registry and resolved inside an active system phase scope. Method
    lookup is delegated to the owning singleton so the compiled property test can
    drive every modelled transition against the real implementation.
    """

    # Declared as a class attribute so lifecycle introspection of the caller
    # instance never routes a ``tier`` lookup through ``__getattr__``.
    tier = system

    def __init__(self) -> None:
        # Seed the delegated service slot before any singleton resolution.
        # ``get_singleton`` introspects the calling instance (including its
        # ``tier`` attribute), so ``__getattr__`` must already be able to see a
        # fully formed, empty service tuple at that point.
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        initialize_dag_engine(self.registry)
        self.scope = enter_phase(system, registry=self.registry)
        self.scope.__enter__()
        self.dag = get_singleton(dag_spec.DAG)
        self.scheduler = get_singleton(dag_spec.WaveScheduler)
        self.runner = get_singleton(dag_spec.DAGRunner)
        self.__dict__["_services"] = (self.dag, self.scheduler, self.runner)

    def __getattr__(self, name: str) -> Any:
        # Dunder lookups must never be delegated: doing so would confuse
        # construction, pickling, and introspection while partially initialized.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        # Read the service slots straight from ``__dict__`` so this method can
        # never re-enter itself through missing instance attributes.
        services = self.__dict__.get("_services", ())
        for service in services:
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(name)


def make_dag_engine_sut() -> DAGEngineSUT:
    """Creates a cleanly initialized real SUT for property-based testing."""
    return DAGEngineSUT()


DAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_dag_engine_sut,
    initial_state_factory=make_dag_engine_state,
    name="DAGEngineLiteFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T05:35:38Z
# LAST_CHANGED: 2026-10-26T05:34:52Z
# CHANGE: Add twelve contract-coverage tests (fake + real suites) for previously unasserted behaviors: removing a node with both prerequisites and dependents clears every incident edge; removing a node after scheduler synchronization reports only currently registered nodes; get_state initializes READY/PENDING before any other scheduler transition; mark_succeeded promotes only PENDING dependents while leaving terminal ones untouched; SKIP_DOWNSTREAM over a diamond graph marks every transitive dependent SKIPPED exactly once; and CONTINUE_ON_ERROR leaves a blocked dependent PENDING and unexecuted when wave execution halts.
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T05:35:38Z
# PRETENSE_QA_AUDIT: 2026-10-26T05:35:15Z
# --- END CLEANROOM METADATA ---
