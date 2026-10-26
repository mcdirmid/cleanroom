# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite.

This module models ``lib/dag_engine_lite_impl.py`` against the contracts declared
in ``low/dag_engine_lite_impl.pyi`` and ``low/dag_engine_lite.pyi``.

Sections:
1. Model state and transition specifications for the ``DAG``, ``WaveScheduler``,
   and ``DAGRunner`` services.
2. State machine prototype and synthesized in-memory fakes.
3. Deterministic fake unit tests.
4. Concrete implementation tests covering every operational branch.
5. Hypothesis stateful property fuzzing of the real implementation.
"""

from __future__ import annotations

import heapq
import unittest
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.context import get_current_draw
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

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
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


_TERMINAL_STATES = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
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


proto = StateMachineProto[DagEngineLiteState]()


# ------------------------------------------------------------------------------
# Model helper functions
# ------------------------------------------------------------------------------


def _make_action(node_id: str) -> Callable[[], str]:
    """Builds a deterministic, side-effect-free node action for fuzzing."""

    def action() -> str:
        return node_id

    return action


def _make_failing_action() -> Callable[[], str]:
    """Builds a deterministic node action that always raises."""

    def action() -> str:
        raise RuntimeError("synthetic node failure")

    return action


def _resolve_node_argument(
    state: DagEngineLiteState,
    node_id: Any,
    *,
    allow_missing: bool,
) -> Any:
    """Resolves a node argument from an explicit value or a generated candidate."""
    if not isinstance(node_id, NotBoundType):
        return node_id
    existing = sorted(state.nodes)
    if allow_missing:
        draw = get_current_draw()
        if draw is not None:
            choices: List[Any] = list(existing)
            choices.append(_missing_id(state))
            return draw(st.sampled_from(choices))
        return existing[0] if existing else _missing_id(state)
    if not existing:
        return _missing_id(state)
    draw = get_current_draw()
    if draw is not None:
        return draw(st.sampled_from(existing))
    return existing[0]


def _missing_id(state: DagEngineLiteState) -> str:
    """Returns an identifier guaranteed to be absent from the model graph."""
    candidate = "__missing__"
    index = 0
    while candidate in state.nodes:
        index += 1
        candidate = f"__missing_{index}__"
    return candidate


def _ensure_synced(state: DagEngineLiteState) -> None:
    """Discovers model nodes, pruning stale entries and seeding missing state."""
    registered = set(state.nodes)
    for stale_id in [node_id for node_id in state.states if node_id not in registered]:
        del state.states[stale_id]
    for node_id in state.nodes:
        if node_id not in state.states:
            if state.upstream[node_id]:
                state.states[node_id] = NodeState.PENDING
            else:
                state.states[node_id] = NodeState.READY


def _first_missing_dependency(state: DagEngineLiteState) -> Optional[str]:
    """Returns the first absent dependency referenced by a node definition."""
    for node_id in sorted(state.nodes):
        for dependency in sorted(state.nodes[node_id].dependencies):
            if dependency not in state.nodes:
                return dependency
    return None


def _find_cycle(state: DagEngineLiteState) -> Optional[Tuple[str, ...]]:
    """Depth-first search returning a directed cycle when one exists."""
    visited: Set[str] = set()
    path: List[str] = []
    path_set: Set[str] = set()

    def visit(node_id: str) -> Optional[Tuple[str, ...]]:
        if node_id in path_set:
            index = path.index(node_id)
            return tuple(path[index:] + [node_id])
        if node_id in visited:
            return None
        visited.add(node_id)
        path.append(node_id)
        path_set.add(node_id)
        for dependent_id in sorted(state.downstream.get(node_id, set())):
            cycle = visit(dependent_id)
            if cycle is not None:
                return cycle
        path.pop()
        path_set.discard(node_id)
        return None

    for node_id in sorted(state.nodes):
        if node_id not in visited:
            cycle = visit(node_id)
            if cycle is not None:
                return cycle
    return None


def _validate(state: DagEngineLiteState) -> None:
    """Validates dependency completeness and acyclicity on the model graph."""
    missing = _first_missing_dependency(state)
    if missing is not None:
        raise NodeNotFoundError(
            f"Missing dependency '{missing}'", missing
        )
    cycle = _find_cycle(state)
    if cycle is not None:
        raise CycleError(f"Cycle detected: {' -> '.join(cycle)}", cycle)


def _topological_sort(state: DagEngineLiteState) -> List[str]:
    """Deterministic Kahn topological sort over the model graph."""
    in_degree = {node_id: len(state.upstream[node_id]) for node_id in state.nodes}
    ready: List[Tuple[int, str]] = [
        (-state.nodes[node_id].priority, node_id)
        for node_id in state.nodes
        if in_degree[node_id] == 0
    ]
    heapq.heapify(ready)
    order: List[str] = []
    while ready:
        _, node_id = heapq.heappop(ready)
        order.append(node_id)
        for dependent_id in state.downstream[node_id]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                heapq.heappush(
                    ready, (-state.nodes[dependent_id].priority, dependent_id)
                )
    if len(order) != len(state.nodes):
        cycle = _find_cycle(state)
        sequence = cycle if cycle is not None else tuple(sorted(state.nodes))
        raise CycleError(f"Cycle detected: {' -> '.join(sequence)}", sequence)
    return order


def _critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    """Longest weighted path over the model graph."""
    order = _topological_sort(state)
    if not order:
        return ([], 0.0)
    earliest: Dict[str, float] = {}
    for node_id in order:
        duration = (
            estimated_durations.get(node_id, 1.0)
            if estimated_durations is not None
            else 1.0
        )
        upstream_weight = max(
            (earliest[dependency] for dependency in state.upstream[node_id]),
            default=0.0,
        )
        earliest[node_id] = upstream_weight + duration
    terminal_id = max(order, key=lambda candidate: earliest[candidate])
    path: List[str] = []
    current: Optional[str] = terminal_id
    while current is not None:
        path.append(current)
        upstream_ids = state.upstream[current]
        if upstream_ids:
            current = max(
                sorted(upstream_ids),
                key=lambda candidate: earliest[candidate],
            )
        else:
            current = None
    path.reverse()
    return (path, earliest[terminal_id])


def _next_wave(state: DagEngineLiteState) -> List[str]:
    """Resolves the next READY wave ordered by priority then identifier."""
    _ensure_synced(state)
    candidates = [
        node_id
        for node_id, node_state in state.states.items()
        if node_state is NodeState.READY
        and all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.upstream[node_id]
        )
    ]
    candidates.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
    return candidates


def _mark_succeeded(state: DagEngineLiteState, node_id: str) -> None:
    """Sets a node SUCCEEDED and promotes newly unblocked dependents."""
    _ensure_synced(state)
    state.states[node_id] = NodeState.SUCCEEDED
    for dependent_id in state.downstream.get(node_id, set()):
        if state.states.get(dependent_id) is NodeState.PENDING and all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.upstream[dependent_id]
        ):
            state.states[dependent_id] = NodeState.READY


def _mark_failed(
    state: DagEngineLiteState,
    node_id: str,
    failure_policy: FailurePolicy,
) -> None:
    """Sets a node FAILED and applies the requested failure policy."""
    _ensure_synced(state)
    state.states[node_id] = NodeState.FAILED
    if failure_policy is FailurePolicy.FAIL_FAST:
        for tracked_id, tracked_state in state.states.items():
            if tracked_state not in _TERMINAL_STATES:
                state.states[tracked_id] = NodeState.CANCELLED
    elif failure_policy is FailurePolicy.SKIP_DOWNSTREAM:
        pending = list(state.downstream.get(node_id, set()))
        visited: Set[str] = set()
        while pending:
            dependent_id = pending.pop()
            if dependent_id in visited:
                continue
            visited.add(dependent_id)
            if state.states.get(dependent_id) not in _TERMINAL_STATES:
                state.states[dependent_id] = NodeState.SKIPPED
            pending.extend(state.downstream.get(dependent_id, set()))


def _is_finished(state: DagEngineLiteState) -> bool:
    """Returns whether every model node reached a terminal state."""
    _ensure_synced(state)
    return all(
        state.states.get(node_id) in _TERMINAL_STATES for node_id in state.nodes
    )


def _copy_state(state: DagEngineLiteState) -> DagEngineLiteState:
    """Produces an isolated model state suitable for speculative simulation."""
    return DagEngineLiteState(
        nodes=dict(state.nodes),
        upstream={node_id: set(values) for node_id, values in state.upstream.items()},
        downstream={
            node_id: set(values) for node_id, values in state.downstream.items()
        },
        states=dict(state.states),
        results=dict(state.results),
    )


def _simulate_run(
    state: DagEngineLiteState, failure_policy: FailurePolicy
) -> DAGRunReport:
    """Simulates sequential runner execution over a disposable model state."""
    _validate(state)
    state.results = {}
    failed_in_run = False
    while not _is_finished(state):
        wave = _next_wave(state)
        if not wave:
            break
        for node_id in wave:
            definition = state.nodes[node_id]
            state.states[node_id] = NodeState.RUNNING
            value: Any = None
            error: Optional[Exception] = None
            attempts = 0
            while True:
                try:
                    value = definition.action()
                    error = None
                    break
                except Exception as exc:  # noqa: BLE001 - mirrored by the runner
                    error = exc
                    if attempts < definition.retries:
                        attempts += 1
                        continue
                    break
            if error is None:
                state.results[node_id] = NodeResult(
                    node_id=node_id,
                    state=NodeState.SUCCEEDED,
                    value=value,
                    duration_seconds=0.0,
                    retries_attempted=attempts,
                )
                _mark_succeeded(state, node_id)
            else:
                state.results[node_id] = NodeResult(
                    node_id=node_id,
                    state=NodeState.FAILED,
                    error=error,
                    duration_seconds=0.0,
                    retries_attempted=attempts,
                )
                _mark_failed(state, node_id, failure_policy)
                failed_in_run = True
                if failure_policy is FailurePolicy.FAIL_FAST:
                    break
        if failed_in_run and failure_policy is FailurePolicy.FAIL_FAST:
            break

    states = dict(state.states)
    for node_id, node_state in states.items():
        if node_state in (NodeState.SKIPPED, NodeState.CANCELLED) and node_id not in state.results:
            state.results[node_id] = NodeResult(node_id=node_id, state=node_state)

    critical_path, _weight = _critical_path(state)
    succeeded_nodes = tuple(
        sorted(
            {nid for nid, res in state.results.items() if res.state is NodeState.SUCCEEDED}
            | {nid for nid, st in states.items() if st is NodeState.SUCCEEDED}
        )
    )
    failed_nodes = tuple(
        sorted(
            {nid for nid, res in state.results.items() if res.state is NodeState.FAILED}
            | {nid for nid, st in states.items() if st is NodeState.FAILED}
        )
    )
    skipped_nodes = tuple(
        sorted(nid for nid, st in states.items() if st is NodeState.SKIPPED)
    )
    cancelled_nodes = tuple(
        sorted(nid for nid, st in states.items() if st is NodeState.CANCELLED)
    )
    return DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=succeeded_nodes,
        failed_nodes=failed_nodes,
        skipped_nodes=skipped_nodes,
        cancelled_nodes=cancelled_nodes,
        wall_clock_seconds=0.0,
        critical_path=tuple(critical_path),
        results=dict(state.results),
    )


def _apply_report(state: DagEngineLiteState, report: DAGRunReport) -> None:
    """Applies an observed run report back onto the canonical model state."""
    _ensure_synced(state)
    state.results = dict(report.results)
    for node_id in report.succeeded_nodes:
        state.states[node_id] = NodeState.SUCCEEDED
    for node_id in report.failed_nodes:
        state.states[node_id] = NodeState.FAILED
    for node_id in report.skipped_nodes:
        state.states[node_id] = NodeState.SKIPPED
    for node_id in report.cancelled_nodes:
        state.states[node_id] = NodeState.CANCELLED


def _same_definition(actual: Any, expected: Any) -> bool:
    """Structural equality for node definitions, ignoring action identity."""
    return (
        actual.node_id == expected.node_id
        and actual.dependencies == expected.dependencies
        and actual.priority == expected.priority
        and actual.retries == expected.retries
        and actual.action is expected.action
    )


def _same_critical_path(actual: Any, expected: Any) -> bool:
    """Compares critical path shape while tolerating floating point drift."""
    if not isinstance(actual, tuple) or len(actual) != 2:
        return False
    path, weight = actual
    expected_path, expected_weight = expected
    return list(path) == list(expected_path) and abs(float(weight) - float(expected_weight)) < 1e-9


def _same_report(actual: Any, expected: Any) -> bool:
    """Compares reports while ignoring nondeterministic timing fields."""
    if not isinstance(actual, DAGRunReport) or not isinstance(expected, DAGRunReport):
        return False
    if (
        actual.total_nodes != expected.total_nodes
        or tuple(actual.succeeded_nodes) != tuple(expected.succeeded_nodes)
        or tuple(actual.failed_nodes) != tuple(expected.failed_nodes)
        or tuple(actual.skipped_nodes) != tuple(expected.skipped_nodes)
        or tuple(actual.cancelled_nodes) != tuple(expected.cancelled_nodes)
        or tuple(actual.critical_path) != tuple(expected.critical_path)
    ):
        return False
    if set(actual.results.keys()) != set(expected.results.keys()):
        return False
    for node_id, actual_result in actual.results.items():
        expected_result = expected.results[node_id]
        if actual_result.state is not expected_result.state:
            return False
        if actual_result.retries_attempted != expected_result.retries_attempted:
            return False
        if actual_result.state is NodeState.SUCCEEDED:
            if actual_result.value != expected_result.value:
                return False
        if actual_result.state is NodeState.FAILED:
            if not (
                isinstance(actual_result.error, Exception)
                and isinstance(expected_result.error, Exception)
                and type(actual_result.error) is type(expected_result.error)
            ):
                return False
    return True


def _error_equals(actual: Exception, expected: Exception) -> bool:
    """Compares contracted exception identities and distinguishing payloads."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, NodeNotFoundError) and isinstance(
        expected, NodeNotFoundError
    ):
        return actual.node_id == expected.node_id
    if isinstance(actual, CycleError) and isinstance(expected, CycleError):
        return tuple(actual.cycle) == tuple(expected.cycle)
    return True


def _check_outcome(
    outcome: Any,
    expected_value: Any,
    expected_error: Optional[Exception],
    value_equals: Callable[[Any, Any], bool] = lambda actual, expected: actual == expected,
) -> Any:
    """Recognizes dispatched outcomes or synthesizes the contracted outcome."""
    if outcome is NotBound:
        if expected_error is not None:
            return Raised(expected_error)
        return Value(expected_value)
    if isinstance(outcome, Raised):
        if expected_error is not None and _error_equals(outcome.exc, expected_error):
            return outcome
        return None
    if isinstance(outcome, Value):
        if expected_error is None and value_equals(outcome.val, expected_value):
            return outcome
        return None
    return None


# ------------------------------------------------------------------------------
# 1.1 DAG.add_node
# ------------------------------------------------------------------------------


@proto.transition(DAG.add_node)
def add_node() -> None:
    pass


@add_node.arguments
def _add_node_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    action: Any | NotBoundType = NotBound,
    dependencies: Any | NotBoundType = NotBound,
    priority: Any | NotBoundType = NotBound,
    retries: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        index = 0
        while f"node_{index}" in state.nodes:
            index += 1
        resolved_id = f"node_{index}"
    else:
        resolved_id = str(node_id)
    draw = get_current_draw()
    if isinstance(action, NotBoundType):
        if draw is not None and draw(st.booleans()):
            resolved_action: Any = _make_failing_action()
        else:
            resolved_action = _make_action(resolved_id)
    else:
        resolved_action = action
    if isinstance(dependencies, NotBoundType):
        existing = sorted(state.nodes)
        if draw is not None and existing:
            if draw(st.booleans()):
                chosen = draw(
                    st.lists(
                        st.sampled_from(existing),
                        min_size=1,
                        max_size=min(3, len(existing)),
                        unique=True,
                    )
                )
                resolved_dependencies: Any = list(chosen)
            else:
                resolved_dependencies = None
        else:
            resolved_dependencies = None
    else:
        resolved_dependencies = dependencies
    if isinstance(priority, NotBoundType):
        resolved_priority = (
            draw(st.integers(min_value=-2, max_value=5)) if draw is not None else 0
        )
    else:
        resolved_priority = priority
    if isinstance(retries, NotBoundType):
        resolved_retries = (
            draw(st.integers(min_value=0, max_value=2)) if draw is not None else 0
        )
    else:
        resolved_retries = retries
    return (
        resolved_id,
        resolved_action,
        resolved_dependencies,
        resolved_priority,
        resolved_retries,
    )


@add_node.returns
def _add_node_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    outcome: object = NotBound,
) -> Any:
    dependency_set = frozenset(dependencies or ())
    missing = next(
        (dependency for dependency in sorted(dependency_set) if dependency not in state.nodes),
        None,
    )
    expected_error = (
        NodeNotFoundError(f"Missing dependency '{missing}'", missing)
        if missing is not None
        else None
    )
    return _check_outcome(outcome, None, expected_error)


@add_node.provide
def _add_node_provide(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    result: Any,
) -> None:
    dependency_set = frozenset(dependencies or ())
    state.nodes[node_id] = NodeDefinition(
        node_id=node_id,
        action=action,
        dependencies=dependency_set,
        priority=priority,
        retries=retries,
    )
    state.upstream.setdefault(node_id, set())
    state.downstream.setdefault(node_id, set())
    for dependency in dependency_set:
        state.upstream[node_id].add(dependency)
        state.downstream.setdefault(dependency, set()).add(node_id)


# ------------------------------------------------------------------------------
# 1.2 DAG.add_edge
# ------------------------------------------------------------------------------


@proto.transition(DAG.add_edge)
def add_edge() -> None:
    pass


@add_edge.require
def _add_edge_requirement(state: DagEngineLiteState, this: Any) -> bool:
    return len(state.nodes) >= 2


@add_edge.arguments
def _add_edge_arguments(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    existing = sorted(state.nodes)
    draw = get_current_draw()
    if (
        isinstance(upstream_id, NotBoundType)
        and isinstance(downstream_id, NotBoundType)
        and draw is not None
        and len(existing) >= 2
    ):
        pair = draw(
            st.lists(
                st.sampled_from(existing),
                min_size=2,
                max_size=2,
                unique=True,
            )
        )
        return (pair[0], pair[1])
    if isinstance(upstream_id, NotBoundType):
        resolved_upstream = existing[0] if existing else _missing_id(state)
    else:
        resolved_upstream = upstream_id
    if isinstance(downstream_id, NotBoundType):
        alternatives = [node for node in existing if node != resolved_upstream]
        resolved_downstream = alternatives[0] if alternatives else _missing_id(state)
    else:
        resolved_downstream = downstream_id
    return (resolved_upstream, resolved_downstream)


@add_edge.returns
def _add_edge_returns(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: object = NotBound,
) -> Any:
    if upstream_id not in state.nodes:
        expected_error: Optional[Exception] = NodeNotFoundError(
            f"Missing upstream '{upstream_id}'", upstream_id
        )
    elif downstream_id not in state.nodes:
        expected_error = NodeNotFoundError(
            f"Missing downstream '{downstream_id}'", downstream_id
        )
    else:
        expected_error = None
    return _check_outcome(outcome, None, expected_error)


@add_edge.provide
def _add_edge_provide(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any,
) -> None:
    state.upstream.setdefault(downstream_id, set()).add(upstream_id)
    state.downstream.setdefault(upstream_id, set()).add(downstream_id)


# ------------------------------------------------------------------------------
# 1.3 DAG.remove_node
# ------------------------------------------------------------------------------


@proto.transition(DAG.remove_node)
def remove_node() -> None:
    pass


@remove_node.arguments
def _remove_node_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@remove_node.returns
def _remove_node_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    expected_error = (
        NodeNotFoundError(f"Missing node '{node_id}'", node_id)
        if node_id not in state.nodes
        else None
    )
    return _check_outcome(outcome, None, expected_error)


@remove_node.provide
def _remove_node_provide(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    for upstream_id in state.upstream.get(node_id, set()):
        state.downstream.get(upstream_id, set()).discard(node_id)
    for downstream_id in state.downstream.get(node_id, set()):
        state.upstream.get(downstream_id, set()).discard(node_id)
    state.nodes.pop(node_id, None)
    state.upstream.pop(node_id, None)
    state.downstream.pop(node_id, None)


# ------------------------------------------------------------------------------
# 1.4 DAG.has_node
# ------------------------------------------------------------------------------


@proto.transition(DAG.has_node)
def has_node() -> None:
    pass


@has_node.arguments
def _has_node_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@has_node.returns
def _has_node_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    return _check_outcome(outcome, node_id in state.nodes, None)


# ------------------------------------------------------------------------------
# 1.5 DAG.get_node
# ------------------------------------------------------------------------------


@proto.transition(DAG.get_node)
def get_node() -> None:
    pass


@get_node.arguments
def _get_node_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@get_node.returns
def _get_node_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    if node_id not in state.nodes:
        return _check_outcome(
            outcome,
            None,
            NodeNotFoundError(f"Missing node '{node_id}'", node_id),
        )
    return _check_outcome(
        outcome,
        state.nodes[node_id],
        None,
        value_equals=_same_definition,
    )


# ------------------------------------------------------------------------------
# 1.6 DAG.get_dependencies
# ------------------------------------------------------------------------------


@proto.transition(DAG.get_dependencies)
def get_dependencies() -> None:
    pass


@get_dependencies.arguments
def _get_dependencies_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@get_dependencies.returns
def _get_dependencies_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    if node_id not in state.nodes:
        return _check_outcome(
            outcome,
            None,
            NodeNotFoundError(f"Missing node '{node_id}'", node_id),
        )
    return _check_outcome(outcome, set(state.upstream[node_id]), None)


# ------------------------------------------------------------------------------
# 1.7 DAG.get_dependents
# ------------------------------------------------------------------------------


@proto.transition(DAG.get_dependents)
def get_dependents() -> None:
    pass


@get_dependents.arguments
def _get_dependents_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@get_dependents.returns
def _get_dependents_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    if node_id not in state.nodes:
        return _check_outcome(
            outcome,
            None,
            NodeNotFoundError(f"Missing node '{node_id}'", node_id),
        )
    return _check_outcome(outcome, set(state.downstream[node_id]), None)


# ------------------------------------------------------------------------------
# 1.8 DAG.all_nodes
# ------------------------------------------------------------------------------


@proto.transition(DAG.all_nodes)
def all_nodes() -> None:
    pass


@all_nodes.arguments
def _all_nodes_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@all_nodes.returns
def _all_nodes_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    return _check_outcome(outcome, set(state.nodes), None)


# ------------------------------------------------------------------------------
# 1.9 DAG.validate
# ------------------------------------------------------------------------------


@proto.transition(DAG.validate)
def validate() -> None:
    pass


@validate.arguments
def _validate_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@validate.returns
def _validate_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    try:
        _validate(state)
    except (CycleError, NodeNotFoundError) as exc:
        return _check_outcome(outcome, None, exc)
    return _check_outcome(outcome, None, None)


# ------------------------------------------------------------------------------
# 1.10 DAG.topological_sort
# ------------------------------------------------------------------------------


@proto.transition(DAG.topological_sort)
def topological_sort() -> None:
    pass


@topological_sort.arguments
def _topological_sort_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@topological_sort.returns
def _topological_sort_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    try:
        order = _topological_sort(state)
    except CycleError as exc:
        return _check_outcome(outcome, None, exc)
    return _check_outcome(outcome, order, None)


# ------------------------------------------------------------------------------
# 1.11 DAG.find_roots
# ------------------------------------------------------------------------------


@proto.transition(DAG.find_roots)
def find_roots() -> None:
    pass


@find_roots.arguments
def _find_roots_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@find_roots.returns
def _find_roots_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    roots = {node_id for node_id in state.nodes if not state.upstream[node_id]}
    return _check_outcome(outcome, roots, None)


# ------------------------------------------------------------------------------
# 1.12 DAG.find_leaves
# ------------------------------------------------------------------------------


@proto.transition(DAG.find_leaves)
def find_leaves() -> None:
    pass


@find_leaves.arguments
def _find_leaves_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@find_leaves.returns
def _find_leaves_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    leaves = {node_id for node_id in state.nodes if not state.downstream[node_id]}
    return _check_outcome(outcome, leaves, None)


# ------------------------------------------------------------------------------
# 1.13 DAG.compute_critical_path
# ------------------------------------------------------------------------------


@proto.transition(DAG.compute_critical_path)
def compute_critical_path() -> None:
    pass


@compute_critical_path.arguments
def _compute_critical_path_arguments(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(estimated_durations, NotBoundType):
        draw = get_current_draw()
        if draw is not None and state.nodes:
            use_weights = draw(st.booleans())
            if use_weights:
                resolved: Any = {
                    node_id: draw(
                        st.floats(
                            min_value=0.0,
                            max_value=10.0,
                            allow_nan=False,
                            allow_infinity=False,
                        )
                    )
                    for node_id in sorted(state.nodes)
                }
            else:
                resolved = None
        else:
            resolved = None
    else:
        resolved = estimated_durations
    return (resolved,)


@compute_critical_path.returns
def _compute_critical_path_returns(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    outcome: object = NotBound,
) -> Any:
    try:
        path = _critical_path(state, estimated_durations)
    except CycleError as exc:
        return _check_outcome(outcome, None, exc)
    return _check_outcome(
        outcome,
        path,
        None,
        value_equals=_same_critical_path,
    )


# ------------------------------------------------------------------------------
# 1.14 WaveScheduler.next_wave
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.next_wave)
def next_wave() -> None:
    pass


@next_wave.arguments
def _next_wave_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@next_wave.returns
def _next_wave_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    return _check_outcome(outcome, _next_wave(state), None)


# ------------------------------------------------------------------------------
# 1.15 WaveScheduler.mark_running
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.mark_running)
def mark_running() -> None:
    pass


@mark_running.arguments
def _mark_running_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@mark_running.returns
def _mark_running_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    return _check_outcome(outcome, None, None)


@mark_running.provide
def _mark_running_provide(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    state.states[node_id] = NodeState.RUNNING


# ------------------------------------------------------------------------------
# 1.16 WaveScheduler.mark_succeeded
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.mark_succeeded)
def mark_succeeded() -> None:
    pass


@mark_succeeded.require
def _mark_succeeded_requirement(state: DagEngineLiteState, this: Any) -> bool:
    return len(state.nodes) >= 1


@mark_succeeded.arguments
def _mark_succeeded_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=False)
    return (resolved,)


@mark_succeeded.returns
def _mark_succeeded_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    if node_id not in state.nodes:
        return _check_outcome(
            outcome,
            None,
            NodeNotFoundError(f"Missing node '{node_id}'", node_id),
        )
    return _check_outcome(outcome, None, None)


@mark_succeeded.provide
def _mark_succeeded_provide(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    _mark_succeeded(state, node_id)


# ------------------------------------------------------------------------------
# 1.17 WaveScheduler.mark_failed
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.mark_failed)
def mark_failed() -> None:
    pass


@mark_failed.require
def _mark_failed_requirement(state: DagEngineLiteState, this: Any) -> bool:
    return len(state.nodes) >= 1


@mark_failed.arguments
def _mark_failed_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=False)
    if isinstance(failure_policy, NotBoundType):
        draw = get_current_draw()
        resolved_policy = (
            draw(st.sampled_from(list(FailurePolicy)))
            if draw is not None
            else FailurePolicy.FAIL_FAST
        )
    else:
        resolved_policy = failure_policy
    return (resolved, resolved_policy)


@mark_failed.returns
def _mark_failed_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Any:
    if node_id not in state.nodes:
        return _check_outcome(
            outcome,
            None,
            NodeNotFoundError(f"Missing node '{node_id}'", node_id),
        )
    return _check_outcome(outcome, None, None)


@mark_failed.provide
def _mark_failed_provide(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    _mark_failed(state, node_id, failure_policy)


# ------------------------------------------------------------------------------
# 1.18 WaveScheduler.is_finished
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.is_finished)
def is_finished() -> None:
    pass


@is_finished.arguments
def _is_finished_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@is_finished.returns
def _is_finished_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    return _check_outcome(outcome, _is_finished(state), None)


# ------------------------------------------------------------------------------
# 1.19 WaveScheduler.get_state
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.get_state)
def get_state() -> None:
    pass


@get_state.arguments
def _get_state_arguments(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    resolved = _resolve_node_argument(state, node_id, allow_missing=True)
    return (resolved,)


@get_state.returns
def _get_state_returns(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Any:
    _ensure_synced(state)
    if node_id not in state.states:
        return _check_outcome(outcome, None, KeyError(node_id))
    return _check_outcome(outcome, state.states[node_id], None)


# ------------------------------------------------------------------------------
# 1.20 WaveScheduler.get_all_states
# ------------------------------------------------------------------------------


@proto.transition(WaveScheduler.get_all_states)
def get_all_states() -> None:
    pass


@get_all_states.arguments
def _get_all_states_arguments(
    state: DagEngineLiteState, this: Any
) -> Optional[Tuple[Any, ...]]:
    return ()


@get_all_states.returns
def _get_all_states_returns(
    state: DagEngineLiteState, this: Any, outcome: object = NotBound
) -> Any:
    _ensure_synced(state)
    return _check_outcome(outcome, dict(state.states), None)


# ------------------------------------------------------------------------------
# 1.21 DAGRunner.run
# ------------------------------------------------------------------------------


@proto.transition(DAGRunner.run)
def run() -> None:
    pass


@run.arguments
def _run_arguments(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(failure_policy, NotBoundType):
        draw = get_current_draw()
        resolved = (
            draw(st.sampled_from(list(FailurePolicy)))
            if draw is not None
            else FailurePolicy.FAIL_FAST
        )
    else:
        resolved = failure_policy
    return (resolved,)


@run.returns
def _run_returns(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Any:
    try:
        expected = _simulate_run(_copy_state(state), failure_policy)
    except (CycleError, NodeNotFoundError) as exc:
        return _check_outcome(outcome, None, exc)
    return _check_outcome(
        outcome,
        expected,
        None,
        value_equals=_same_report,
    )


@run.provide
def _run_provide(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    if isinstance(result, DAGRunReport):
        _apply_report(state, result)


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
        self.dag, self.wavescheduler, self.dagrunner = make_dag_engine_lite_fakes(
            self.state
        )

    def test_fake_initial_state(self) -> None:
        self.assertTrue(self.state.nodes == {})
        self.assertEqual(self.dag.all_nodes(), set())

    def test_fake_add_node_and_inspection(self) -> None:
        self.dag.add_node("task_a", lambda: 1, priority=10)
        self.dag.add_node("task_b", lambda: 2, ["task_a"], priority=5)
        self.assertEqual(self.dag.all_nodes(), {"task_a", "task_b"})
        self.assertTrue(self.dag.has_node("task_a"))
        self.assertFalse(self.dag.has_node("ghost"))
        self.assertEqual(self.dag.get_dependencies("task_b"), {"task_a"})
        self.assertEqual(self.dag.get_dependents("task_a"), {"task_b"})
        definition = self.dag.get_node("task_a")
        self.assertEqual(definition.node_id, "task_a")
        self.assertEqual(definition.priority, 10)
        self.assertEqual(self.dag.find_roots(), {"task_a"})
        self.assertEqual(self.dag.find_leaves(), {"task_b"})
        self.dag.validate()
        self.assertEqual(self.dag.topological_sort(), ["task_a", "task_b"])

    def test_fake_add_edge_and_remove_node(self) -> None:
        self.dag.add_node("task_a", lambda: 1)
        self.dag.add_node("task_b", lambda: 2)
        self.dag.add_edge("task_a", "task_b")
        self.assertEqual(self.dag.get_dependencies("task_b"), {"task_a"})
        self.dag.remove_node("task_b")
        self.assertFalse(self.dag.has_node("task_b"))
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("task_b")

    def test_fake_errors(self) -> None:
        self.dag.add_node("task_a", lambda: 1)
        self.dag.add_node("task_b", lambda: 2)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "task_a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("task_a", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_fake_critical_path(self) -> None:
        self.dag.add_node("start", lambda: 1, priority=2)
        self.dag.add_node("branch", lambda: 2, ["start"], priority=1)
        self.dag.add_node("end", lambda: 3, ["branch"])
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["start", "branch", "end"])
        self.assertAlmostEqual(weight, 3.0)
        weighted_path, weighted = self.dag.compute_critical_path(
            {"start": 2.5, "branch": 4.0, "end": 1.5}
        )
        self.assertEqual(weighted_path, ["start", "branch", "end"])
        self.assertAlmostEqual(weighted, 8.0)

    def test_fake_scheduler_transitions(self) -> None:
        self.dag.add_node("high", lambda: 1, priority=10)
        self.dag.add_node("low", lambda: 2, priority=5)
        self.dag.add_node("child", lambda: 3, ["high"], priority=1)
        self.assertEqual(self.wavescheduler.next_wave(), ["high", "low"])
        self.wavescheduler.mark_running("high")
        self.assertIs(self.wavescheduler.get_state("high"), NodeState.RUNNING)
        self.wavescheduler.mark_succeeded("high")
        self.assertIn("child", self.wavescheduler.get_all_states())
        self.assertIs(self.wavescheduler.get_state("child"), NodeState.READY)
        self.assertFalse(self.wavescheduler.is_finished())
        self.wavescheduler.mark_failed("low", FailurePolicy.FAIL_FAST)
        self.assertTrue(self.wavescheduler.is_finished())
        self.assertIs(self.wavescheduler.get_state("child"), NodeState.CANCELLED)

    def test_fake_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("parent", lambda: 1)
        self.dag.add_node("child", lambda: 2, ["parent"])
        self.dag.add_node("grandchild", lambda: 3, ["child"])
        self.wavescheduler.mark_failed("parent", FailurePolicy.SKIP_DOWNSTREAM)
        states = self.wavescheduler.get_all_states()
        self.assertIs(states["parent"], NodeState.FAILED)
        self.assertIs(states["child"], NodeState.SKIPPED)
        self.assertIs(states["grandchild"], NodeState.SKIPPED)

    def test_fake_runner_run(self) -> None:
        self.dag.add_node("task_a", lambda: "a")
        self.dag.add_node("task_b", lambda: "b", ["task_a"])
        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("task_a", "task_b"))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.critical_path, ("task_a", "task_b"))
        self.assertEqual(
            report.results["task_a"].value,
            "a",
        )


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

    def test_real_services_resolve(self) -> None:
        self.assertIsNotNone(self.dag)
        self.assertIsNotNone(self.wavescheduler)
        self.assertIsNotNone(self.dagrunner)
        self.assertIs(self.dag, get_singleton(dag_engine_lite.DAG))
        self.assertIs(
            self.wavescheduler, get_singleton(dag_engine_lite.WaveScheduler)
        )
        self.assertIs(self.dagrunner, get_singleton(dag_engine_lite.DAGRunner))

    def test_real_graph_construction_and_order(self) -> None:
        self.dag.add_node("task_a", lambda: 1, priority=10)
        self.dag.add_node("task_b", lambda: 2, ["task_a"], priority=5)
        self.dag.add_node("task_c", lambda: 3, priority=5)
        self.dag.add_node("task_d", lambda: 4, ["task_a", "task_b"], priority=0)
        self.assertEqual(
            self.dag.all_nodes(), {"task_a", "task_b", "task_c", "task_d"}
        )
        self.assertEqual(self.dag.find_roots(), {"task_a", "task_c"})
        self.assertEqual(self.dag.find_leaves(), {"task_c", "task_d"})
        self.assertEqual(
            self.dag.topological_sort(), ["task_a", "task_b", "task_c", "task_d"]
        )
        self.dag.validate()
        definition = self.dag.get_node("task_d")
        self.assertEqual(definition.dependencies, frozenset({"task_a", "task_b"}))
        self.assertEqual(definition.priority, 0)
        self.assertEqual(definition.retries, 0)
        self.assertEqual(self.dag.get_dependencies("task_d"), {"task_a", "task_b"})
        self.assertEqual(self.dag.get_dependents("task_a"), {"task_b", "task_d"})

    def test_real_empty_graph(self) -> None:
        self.assertEqual(self.dag.all_nodes(), set())
        self.assertEqual(self.dag.find_roots(), set())
        self.assertEqual(self.dag.find_leaves(), set())
        self.assertEqual(self.dag.topological_sort(), [])
        self.assertEqual(self.dag.compute_critical_path(), ([], 0.0))
        self.dag.validate()

    def test_real_add_edge_and_missing_errors(self) -> None:
        self.dag.add_node("up", lambda: 1)
        self.dag.add_node("down", lambda: 2)
        self.dag.add_edge("up", "down")
        self.assertEqual(self.dag.get_dependencies("down"), {"up"})
        with self.assertRaises(NodeNotFoundError) as upstream_error:
            self.dag.add_edge("ghost", "down")
        self.assertEqual(upstream_error.exception.node_id, "ghost")
        with self.assertRaises(NodeNotFoundError) as downstream_error:
            self.dag.add_edge("up", "ghost")
        self.assertEqual(downstream_error.exception.node_id, "ghost")

    def test_real_add_node_missing_dependency(self) -> None:
        with self.assertRaises(NodeNotFoundError) as missing:
            self.dag.add_node("orphan", lambda: 1, ["ghost"])
        self.assertEqual(missing.exception.node_id, "ghost")
        self.assertFalse(self.dag.has_node("orphan"))

    def test_real_remove_node_and_dangling_validation(self) -> None:
        self.dag.add_node("task_a", lambda: 1)
        self.dag.add_node("task_b", lambda: 2, ["task_a"])
        self.dag.add_node("task_c", lambda: 3, ["task_b"])
        self.dag.remove_node("task_b")
        self.assertFalse(self.dag.has_node("task_b"))
        self.assertEqual(self.dag.get_dependents("task_a"), set())
        self.assertEqual(self.dag.get_dependencies("task_c"), set())
        with self.assertRaises(NodeNotFoundError) as missing:
            self.dag.validate()
        self.assertEqual(missing.exception.node_id, "task_b")
        with self.assertRaises(NodeNotFoundError) as absent:
            self.dag.remove_node("ghost")
        self.assertEqual(absent.exception.node_id, "ghost")

    def test_real_unknown_node_lookups(self) -> None:
        for lookup in (
            lambda: self.dag.get_node("ghost"),
            lambda: self.dag.get_dependencies("ghost"),
            lambda: self.dag.get_dependents("ghost"),
        ):
            with self.assertRaises(NodeNotFoundError) as absent:
                lookup()
            self.assertEqual(absent.exception.node_id, "ghost")

    def test_real_cycle_detection(self) -> None:
        self.dag.add_node("step_1", lambda: 1)
        self.dag.add_node("step_2", lambda: 2, ["step_1"])
        self.dag.add_edge("step_2", "step_1")
        with self.assertRaises(CycleError) as cycle_error:
            self.dag.validate()
        self.assertEqual(set(cycle_error.exception.cycle), {"step_1", "step_2"})
        self.assertEqual(
            cycle_error.exception.cycle[0], cycle_error.exception.cycle[-1]
        )
        with self.assertRaises(CycleError):
            self.dag.topological_sort()
        with self.assertRaises(CycleError):
            self.dag.compute_critical_path()

    def test_real_critical_path_weighted(self) -> None:
        self.dag.add_node("node_start", lambda: 1, priority=2)
        self.dag.add_node("node_branch", lambda: 2, ["node_start"], priority=1)
        self.dag.add_node("node_end", lambda: 3, ["node_branch"])
        path, weight = self.dag.compute_critical_path(
            {"node_start": 2.5, "node_branch": 4.0, "node_end": 1.5}
        )
        self.assertEqual(path, ["node_start", "node_branch", "node_end"])
        self.assertAlmostEqual(weight, 8.0)

    def test_real_critical_path_defaults_and_ties(self) -> None:
        self.dag.add_node("task_a", lambda: 1, priority=10)
        self.dag.add_node("task_b", lambda: 2, ["task_a"], priority=5)
        self.dag.add_node("task_c", lambda: 3, priority=5)
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["task_a", "task_b"])
        self.assertAlmostEqual(weight, 2.0)
        partial_path, partial_weight = self.dag.compute_critical_path(
            {"task_a": 5.0}
        )
        self.assertEqual(partial_path, ["task_a", "task_b"])
        self.assertAlmostEqual(partial_weight, 6.0)

    def test_real_scheduler_dynamic_sync_and_waves(self) -> None:
        self.dag.add_node("task_low", lambda: 1, priority=5)
        self.dag.add_node("task_high", lambda: 2, priority=10)
        self.dag.add_node("task_mid", lambda: 3, priority=5)
        states = self.wavescheduler.get_all_states()
        self.assertIs(states["task_high"], NodeState.READY)
        self.assertEqual(
            self.wavescheduler.next_wave(),
            ["task_high", "task_low", "task_mid"],
        )
        self.wavescheduler.mark_running("task_high")
        self.assertIs(self.wavescheduler.get_state("task_high"), NodeState.RUNNING)
        self.assertEqual(
            self.wavescheduler.next_wave(), ["task_low", "task_mid"]
        )
        self.dag.add_node("task_late", lambda: 4, ["task_mid"], priority=20)
        self.assertIn("task_late", self.wavescheduler.get_all_states())
        self.assertIs(self.wavescheduler.get_state("task_late"), NodeState.PENDING)

    def test_real_scheduler_success_promotion(self) -> None:
        self.dag.add_node("left", lambda: 1)
        self.dag.add_node("right", lambda: 2)
        self.dag.add_node("join", lambda: 3, ["left", "right"])
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_succeeded("left")
        self.assertIs(self.wavescheduler.get_state("join"), NodeState.PENDING)
        self.wavescheduler.mark_succeeded("right")
        self.assertIs(self.wavescheduler.get_state("join"), NodeState.READY)
        self.assertEqual(self.wavescheduler.next_wave(), ["join"])

    def test_real_scheduler_fail_fast(self) -> None:
        self.dag.add_node("root_a", lambda: 1)
        self.dag.add_node("root_b", lambda: 2)
        self.dag.add_node("child", lambda: 3, ["root_a"])
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_failed("root_a", FailurePolicy.FAIL_FAST)
        states = self.wavescheduler.get_all_states()
        self.assertIs(states["root_a"], NodeState.FAILED)
        self.assertIs(states["root_b"], NodeState.CANCELLED)
        self.assertIs(states["child"], NodeState.CANCELLED)
        self.assertTrue(self.wavescheduler.is_finished())

    def test_real_scheduler_continue_on_error(self) -> None:
        self.dag.add_node("root_a", lambda: 1)
        self.dag.add_node("root_b", lambda: 2)
        self.dag.add_node("child", lambda: 3, ["root_a"])
        self.wavescheduler.next_wave()
        self.wavescheduler.mark_failed("root_a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIs(self.wavescheduler.get_state("root_b"), NodeState.READY)
        self.assertIs(self.wavescheduler.get_state("child"), NodeState.PENDING)
        self.assertFalse(self.wavescheduler.is_finished())

    def test_real_scheduler_remove_prunes_state(self) -> None:
        self.dag.add_node("temporary", lambda: 1)
        self.wavescheduler.get_all_states()
        self.dag.remove_node("temporary")
        self.assertEqual(self.wavescheduler.get_all_states(), {})
        self.assertTrue(self.wavescheduler.is_finished())
        with self.assertRaises(KeyError):
            self.wavescheduler.get_state("temporary")

    def test_real_runner_success_and_retries(self) -> None:
        attempts: Dict[str, int] = {"flaky": 0}

        def flaky() -> str:
            attempts["flaky"] += 1
            if attempts["flaky"] < 3:
                raise RuntimeError("transient")
            return "recovered"

        self.dag.add_node("root", lambda: "root-value", retries=1)
        self.dag.add_node("flaky", flaky, ["root"], retries=2)
        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("flaky", "root"))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.results["root"].value, "root-value")
        self.assertEqual(report.results["root"].retries_attempted, 0)
        self.assertEqual(report.results["flaky"].value, "recovered")
        self.assertEqual(report.results["flaky"].retries_attempted, 2)
        self.assertGreaterEqual(report.results["flaky"].duration_seconds, 0.0)
        self.assertEqual(report.critical_path, ("root", "flaky"))

    def test_real_runner_fail_fast(self) -> None:
        self.dag.add_node("root", lambda: 1)
        self.dag.add_node("child", lambda: 2, ["root"])

        def boom() -> int:
            raise ValueError("boom")

        self.dag.add_node("exploder", boom, ["child"], retries=1)
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.failed_nodes, ("exploder",))
        self.assertEqual(report.succeeded_nodes, ("child", "root"))
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.results["exploder"].retries_attempted, 1)
        self.assertIsInstance(report.results["exploder"].error, ValueError)
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_real_runner_skip_downstream(self) -> None:
        def boom() -> int:
            raise RuntimeError("boom")

        self.dag.add_node("parent", boom, priority=5)
        self.dag.add_node("child", lambda: 2, ["parent"])
        self.dag.add_node("second_child", lambda: 3, ["parent"])
        self.dag.add_node(
            "grandchild", lambda: 4, ["child", "second_child"]
        )
        self.dag.add_node("independent", lambda: 5, priority=-1)
        report = self.dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("parent",))
        self.assertEqual(
            report.skipped_nodes, ("child", "grandchild", "second_child")
        )
        self.assertEqual(report.succeeded_nodes, ("independent",))
        self.assertIn("grandchild", report.results)
        self.assertIs(report.results["grandchild"].state, NodeState.SKIPPED)

    def test_real_runner_continue_on_error_stalls_blocked_nodes(self) -> None:
        def boom() -> int:
            raise RuntimeError("boom")

        self.dag.add_node("parent", boom, priority=10)
        self.dag.add_node("blocked", lambda: 2, ["parent"])
        self.dag.add_node("independent", lambda: 3, priority=5)
        report = self.dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("parent",))
        self.assertEqual(report.succeeded_nodes, ("independent",))
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertNotIn("blocked", report.results)

    def test_real_runner_empty_graph(self) -> None:
        report = self.dagrunner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.critical_path, ())
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_real_runner_prevalidates_cycles(self) -> None:
        self.dag.add_node("step_1", lambda: 1)
        self.dag.add_node("step_2", lambda: 2, ["step_1"])
        self.dag.add_edge("step_2", "step_1")
        with self.assertRaises(CycleError):
            self.dagrunner.run()

    def test_real_parity_with_fake(self) -> None:
        real_dag = self.dag
        real_scheduler = self.wavescheduler
        real_runner = self.dagrunner
        fake_state = DagEngineLiteState()
        fake_dag, fake_scheduler, fake_runner = make_dag_engine_lite_fakes(fake_state)

        def build(dag: Any) -> None:
            dag.add_node("start", lambda: "start", priority=3)
            dag.add_node("left", lambda: "left", ["start"], priority=2)
            dag.add_node("right", lambda: "right", ["start"], priority=1)
            dag.add_node("join", lambda: "join", ["left", "right"], priority=0)

        build(real_dag)
        build(fake_dag)
        self.assertEqual(real_dag.all_nodes(), fake_dag.all_nodes())
        self.assertEqual(real_dag.topological_sort(), fake_dag.topological_sort())
        self.assertEqual(real_dag.find_roots(), fake_dag.find_roots())
        self.assertEqual(
            real_dag.compute_critical_path(), fake_dag.compute_critical_path()
        )
        self.assertEqual(real_scheduler.next_wave(), fake_scheduler.next_wave())
        real_report = real_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        fake_report = fake_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(real_report.succeeded_nodes, fake_report.succeeded_nodes)
        self.assertEqual(real_report.failed_nodes, fake_report.failed_nodes)
        self.assertEqual(real_report.critical_path, fake_report.critical_path)
        self.assertEqual(
            set(real_report.results.keys()), set(fake_report.results.keys())
        )


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
        self.__dict__["_services"] = (
            self.dag,
            self.wavescheduler,
            self.dagrunner,
        )

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def teardown(self) -> None:
        scope = self.__dict__.get("phase_scope")
        if scope is not None:
            scope.__exit__(None, None, None)


def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)


# === File: dag_engine_lite_pretense.py ===
"""Pretense data-type tests for the dag_engine_lite interface component.

The interface module declares protocols and immutable value types. Protocols are
not instantiable in isolation, so this module verifies the value-type contracts
(immutability, defaults, enum membership, and error payloads) that concrete
implementations consume.
"""

from __future__ import annotations

from dataclasses import dataclass
import unittest
from typing import Any

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value

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
    """Canonical model state for the interface value types."""

    initialized: bool = True


proto = StateMachineProto[DagEngineLiteState]()


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================


class TestDagEngineLiteUnit(unittest.TestCase):
    """Verifies the immutable value types declared by the interface."""

    def setUp(self) -> None:
        self.state = DagEngineLiteState()

    def test_state_initialized(self) -> None:
        self.assertTrue(self.state.initialized)

    def test_node_definition_defaults_and_equality(self) -> None:
        action = lambda: 7  # noqa: E731 - identity is what matters here
        definition = NodeDefinition("task", action, frozenset({"upstream"}))
        self.assertEqual(definition.node_id, "task")
        self.assertIs(definition.action, action)
        self.assertEqual(definition.dependencies, frozenset({"upstream"}))
        self.assertEqual(definition.priority, 0)
        self.assertEqual(definition.retries, 0)
        self.assertEqual(
            definition,
            NodeDefinition("task", action, frozenset({"upstream"})),
        )
        with self.assertRaises(Exception):
            definition.priority = 5  # type: ignore[misc]

    def test_node_result_defaults(self) -> None:
        result: NodeResult[Any] = NodeResult("task", NodeState.SUCCEEDED, value=3)
        self.assertEqual(result.node_id, "task")
        self.assertIs(result.state, NodeState.SUCCEEDED)
        self.assertEqual(result.value, 3)
        self.assertIsNone(result.error)
        self.assertEqual(result.duration_seconds, 0.0)
        self.assertEqual(result.retries_attempted, 0)

    def test_dag_run_report_fields(self) -> None:
        result = NodeResult("task", NodeState.SUCCEEDED, value=1)
        report = DAGRunReport(
            total_nodes=1,
            succeeded_nodes=("task",),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.01,
            critical_path=("task",),
            results={"task": result},
        )
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("task",))
        self.assertEqual(report.critical_path, ("task",))
        self.assertEqual(report.results["task"].value, 1)

    def test_enums_and_errors(self) -> None:
        self.assertEqual(NodeState.PENDING.value, "pending")
        self.assertEqual(NodeState.READY.value, "ready")
        self.assertEqual(NodeState.RUNNING.value, "running")
        self.assertEqual(NodeState.SUCCEEDED.value, "succeeded")
        self.assertEqual(NodeState.FAILED.value, "failed")
        self.assertEqual(NodeState.CANCELLED.value, "cancelled")
        self.assertEqual(NodeState.SKIPPED.value, "skipped")
        self.assertEqual(FailurePolicy.FAIL_FAST.value, "fail_fast")
        self.assertEqual(FailurePolicy.CONTINUE_ON_ERROR.value, "continue_on_error")
        self.assertEqual(FailurePolicy.SKIP_DOWNSTREAM.value, "skip_downstream")

        base_error = DAGError("base")
        self.assertIsInstance(base_error, Exception)
        self.assertEqual(str(base_error), "base")

        cycle_error = CycleError("cycle", ("a", "b", "a"))
        self.assertIsInstance(cycle_error, DAGError)
        self.assertEqual(cycle_error.cycle, ("a", "b", "a"))

        not_found = NodeNotFoundError("missing", "a")
        self.assertIsInstance(not_found, DAGError)
        self.assertEqual(not_found.node_id, "a")

        execution_error = NodeExecutionError("failed", "a", ValueError("boom"))
        self.assertIsInstance(execution_error, DAGError)
        self.assertEqual(execution_error.node_id, "a")
        self.assertIsInstance(execution_error.cause, ValueError)
