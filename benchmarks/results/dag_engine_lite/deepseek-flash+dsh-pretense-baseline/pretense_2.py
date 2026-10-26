"""Pretense state machine, fakes, unit tests, and property fuzzing for the
synchronous DAG execution and wave scheduling engine.

Models graph construction, deterministic topological ordering, critical path
analysis, wave scheduling, failure policy propagation, and sequential execution
per ``low/dag_engine_lite.pyi`` and ``low/dag_engine_lite_impl.pyi``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import time
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple
import unittest

import hypothesis.strategies as st
from pretense.compiler import compile_hypothesis_test_case
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


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

_TERMINAL_STATES: FrozenSet[NodeState] = frozenset(
    {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
)


@dataclass
class _ModelNode:
    """Reference-model record for a registered graph node."""

    node_id: str
    action: Callable[[], Any]
    dependencies: FrozenSet[str]
    priority: int
    retries: int


@dataclass
class DagEngineLiteState:
    """Canonical model state for the DAG, scheduler, and runner."""

    nodes: Dict[str, _ModelNode] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    next_id: int = 0
    tick: int = 0


proto = StateMachineProto[DagEngineLiteState]()


# ------------------------------------------------------------------------------
# 1.0 Reference model helpers
# ------------------------------------------------------------------------------

def _node_not_found(node_id: str) -> NodeNotFoundError:
    return NodeNotFoundError(
        message=f"Node not found in DAG: {node_id}", node_id=node_id
    )


def _cycle_error(cycle: Tuple[str, ...]) -> CycleError:
    return CycleError(
        message=f"Dependency cycle detected: {cycle}", cycle=cycle
    )


def _definition(node: _ModelNode) -> NodeDefinition[Any]:
    return NodeDefinition(
        node_id=node.node_id,
        action=node.action,
        dependencies=node.dependencies,
        priority=node.priority,
        retries=node.retries,
    )


def _model_cycle(state: DagEngineLiteState) -> Optional[Tuple[str, ...]]:
    color: Dict[str, int] = {}
    path: List[str] = []

    def visit(node_id: str) -> Optional[Tuple[str, ...]]:
        color[node_id] = 1
        path.append(node_id)
        for dependency in sorted(state.upstream.get(node_id, set())):
            marker = color.get(dependency, 0)
            if marker == 1:
                index = path.index(dependency)
                return tuple(path[index:]) + (dependency,)
            if marker == 0:
                found = visit(dependency)
                if found is not None:
                    return found
        path.pop()
        color[node_id] = 2
        return None

    for node_id in sorted(state.nodes):
        if color.get(node_id, 0) == 0:
            found = visit(node_id)
            if found is not None:
                return found
    return None


def _model_validate(state: DagEngineLiteState) -> None:
    for node_id, node in state.nodes.items():
        candidates = set(node.dependencies)
        candidates.update(state.upstream.get(node_id, set()))
        for dependency in candidates:
            if dependency not in state.nodes:
                raise _node_not_found(dependency)
    cycle = _model_cycle(state)
    if cycle is not None:
        raise _cycle_error(cycle)


def _model_topological_sort(state: DagEngineLiteState) -> List[str]:
    in_degree: Dict[str, int] = {
        node_id: len(state.upstream.get(node_id, set()))
        for node_id in state.nodes
    }
    ready: List[Tuple[int, str]] = []
    for node_id, degree in in_degree.items():
        if degree == 0:
            heapq.heappush(ready, (-state.nodes[node_id].priority, node_id))
    order: List[str] = []
    while ready:
        _, node_id = heapq.heappop(ready)
        order.append(node_id)
        for dependent in sorted(state.downstream.get(node_id, set())):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(
                    ready, (-state.nodes[dependent].priority, dependent)
                )
    if len(order) != len(state.nodes):
        cycle = _model_cycle(state)
        raise _cycle_error(cycle if cycle is not None else ())
    return order


def _model_critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    order = _model_topological_sort(state)
    if not order:
        return [], 0.0
    durations: Dict[str, float] = {}
    for node_id in order:
        if estimated_durations is not None:
            durations[node_id] = float(estimated_durations.get(node_id, 1.0))
        else:
            durations[node_id] = 1.0
    earliest: Dict[str, float] = {}
    predecessor: Dict[str, Optional[str]] = {}
    for node_id in order:
        best_time = 0.0
        best_dependency: Optional[str] = None
        for dependency in sorted(state.upstream.get(node_id, set())):
            dependency_time = earliest[dependency]
            if (
                best_dependency is None
                or dependency_time > best_time
                or (
                    dependency_time == best_time
                    and dependency < best_dependency
                )
            ):
                best_time = dependency_time
                best_dependency = dependency
        earliest[node_id] = best_time + durations[node_id]
        predecessor[node_id] = best_dependency
    leaves = [
        node_id
        for node_id in order
        if not state.downstream.get(node_id, set())
    ]
    terminal = min(leaves, key=lambda item: (-earliest[item], item))
    path: List[str] = []
    current: Optional[str] = terminal
    while current is not None:
        path.append(current)
        current = predecessor[current]
    path.reverse()
    return path, earliest[terminal]


def _model_sync(state: DagEngineLiteState) -> None:
    nodes = set(state.nodes)
    for known in list(state.states):
        if known not in nodes:
            del state.states[known]
    for node_id in nodes:
        if node_id not in state.states:
            if state.upstream.get(node_id, set()):
                state.states[node_id] = NodeState.PENDING
            else:
                state.states[node_id] = NodeState.READY


def _model_promote(state: DagEngineLiteState) -> None:
    for node_id in list(state.states):
        if state.states[node_id] is not NodeState.PENDING:
            continue
        dependencies = state.upstream.get(node_id, set())
        if all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in dependencies
        ):
            state.states[node_id] = NodeState.READY


def _model_dependents(state: DagEngineLiteState, node_id: str) -> Set[str]:
    if node_id not in state.nodes:
        raise _node_not_found(node_id)
    return set(state.downstream.get(node_id, set()))


def _model_transitive_dependents(
    state: DagEngineLiteState, node_id: str
) -> Set[str]:
    seen: Set[str] = set()
    pending: List[str] = list(_model_dependents(state, node_id))
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(_model_dependents(state, current))
    return seen


def _model_next_wave(state: DagEngineLiteState) -> List[str]:
    _model_sync(state)
    _model_promote(state)
    candidates: List[str] = []
    for node_id, node_state in state.states.items():
        if node_state is not NodeState.READY:
            continue
        dependencies = state.upstream.get(node_id, set())
        if all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in dependencies
        ):
            candidates.append(node_id)
    candidates.sort(key=lambda item: (-state.nodes[item].priority, item))
    return candidates


def _model_mark_running(state: DagEngineLiteState, node_id: str) -> None:
    state.states[node_id] = NodeState.RUNNING


def _model_mark_succeeded(state: DagEngineLiteState, node_id: str) -> None:
    _model_sync(state)
    state.states[node_id] = NodeState.SUCCEEDED
    for dependent in _model_dependents(state, node_id):
        if state.states.get(dependent) is not NodeState.PENDING:
            continue
        dependencies = state.upstream.get(dependent, set())
        if all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in dependencies
        ):
            state.states[dependent] = NodeState.READY


def _model_mark_failed(
    state: DagEngineLiteState, node_id: str, failure_policy: FailurePolicy
) -> None:
    _model_sync(state)
    state.states[node_id] = NodeState.FAILED
    if failure_policy is FailurePolicy.FAIL_FAST:
        for other, node_state in state.states.items():
            if node_state not in _TERMINAL_STATES:
                state.states[other] = NodeState.CANCELLED
        return
    for dependent in _model_transitive_dependents(state, node_id):
        node_state = state.states.get(dependent)
        if node_state is not None and node_state not in _TERMINAL_STATES:
            state.states[dependent] = NodeState.SKIPPED


def _model_is_finished(state: DagEngineLiteState) -> bool:
    _model_sync(state)
    if not state.states:
        return True
    if all(node_state in _TERMINAL_STATES for node_state in state.states.values()):
        return True
    _model_promote(state)
    return not any(
        node_state in (NodeState.READY, NodeState.RUNNING)
        for node_state in state.states.values()
    )


def _model_get_all_states(state: DagEngineLiteState) -> Dict[str, NodeState]:
    _model_sync(state)
    return {node_id: state.states[node_id] for node_id in state.nodes}


def _model_run(
    state: DagEngineLiteState, failure_policy: FailurePolicy
) -> DAGRunReport:
    _model_validate(state)
    start = time.perf_counter()
    state.results = {}
    halted = False
    while not _model_is_finished(state):
        wave = _model_next_wave(state)
        if not wave:
            break
        for node_id in wave:
            node = state.nodes[node_id]
            _model_mark_running(state, node_id)
            retries_attempted = 0
            value: Any = None
            error: Optional[Exception] = None
            while True:
                try:
                    value = node.action()
                    error = None
                    break
                except Exception as exc:  # cleanroom: allow-broad-exception
                    error = exc
                    if retries_attempted >= node.retries:
                        break
                    retries_attempted += 1
            if error is None:
                state.results[node_id] = NodeResult(
                    node_id=node_id,
                    state=NodeState.SUCCEEDED,
                    value=value,
                    retries_attempted=retries_attempted,
                )
                _model_mark_succeeded(state, node_id)
            else:
                state.results[node_id] = NodeResult(
                    node_id=node_id,
                    state=NodeState.FAILED,
                    error=error,
                    retries_attempted=retries_attempted,
                )
                _model_mark_failed(state, node_id, failure_policy)
                if failure_policy is FailurePolicy.FAIL_FAST:
                    halted = True
                    break
        if halted:
            break
    for node_id, node_state in _model_get_all_states(state).items():
        if node_id in state.results:
            continue
        if node_state in (NodeState.SKIPPED, NodeState.CANCELLED):
            state.results[node_id] = NodeResult(
                node_id=node_id, state=node_state
            )
    critical_path, _ = _model_critical_path(state)
    return DAGRunReport(
        total_nodes=len(state.nodes),
        succeeded_nodes=tuple(
            sorted(
                node_id
                for node_id, result in state.results.items()
                if result.state is NodeState.SUCCEEDED
            )
        ),
        failed_nodes=tuple(
            sorted(
                node_id
                for node_id, result in state.results.items()
                if result.state is NodeState.FAILED
            )
        ),
        skipped_nodes=tuple(
            sorted(
                node_id
                for node_id, result in state.results.items()
                if result.state is NodeState.SKIPPED
            )
        ),
        cancelled_nodes=tuple(
            sorted(
                node_id
                for node_id, result in state.results.items()
                if result.state is NodeState.CANCELLED
            )
        ),
        wall_clock_seconds=time.perf_counter() - start,
        critical_path=tuple(critical_path),
        results=dict(state.results),
    )


def _make_action(node_id: str) -> Callable[[], Any]:
    """Builds a deterministic node action; some identifiers always fail."""
    suffix = node_id[1:] if node_id.startswith("n") else ""
    index = int(suffix) if suffix.isdigit() else 0

    def action() -> Any:
        if index % 4 == 3:
            raise RuntimeError(f"action failure for {node_id}")
        return node_id

    return action


def _pick_node(state: DagEngineLiteState) -> str:
    """Chooses an existing node identifier, occasionally a missing one."""
    state.tick += 1
    existing = sorted(state.nodes)
    if existing and state.tick % 4 != 0:
        return existing[state.tick % len(existing)]
    return "missing_node"


def _accept_void(outcome: object) -> Optional[Outcome[Any]]:
    """Recognizes a contracted void outcome, accepting domain errors."""
    if outcome is NotBound:
        return Value(None)
    if isinstance(outcome, Raised):
        return outcome if isinstance(outcome.exc, DAGError) else None
    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    return None


# ------------------------------------------------------------------------------
# 1.1 DAG.add_node
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.DAG.add_node)
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
    sequence = state.next_id
    if isinstance(node_id, NotBoundType):
        node_id = f"n{sequence}"
        state.next_id += 1
    if isinstance(action, NotBoundType):
        action = _make_action(str(node_id))
    if isinstance(dependencies, NotBoundType):
        existing = sorted(state.nodes)
        dependencies = existing[: sequence % 3]
    if isinstance(priority, NotBoundType):
        priority = sequence % 3
    if isinstance(retries, NotBoundType):
        retries = sequence % 2
    return (node_id, action, dependencies, priority, retries)

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
    return _accept_void(outcome)

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
    identifier = str(node_id)
    dependency_set: FrozenSet[str] = frozenset(dependencies)
    previous = state.upstream.get(identifier)
    if previous is not None:
        for dependency in previous:
            downstream = state.downstream.get(dependency)
            if downstream is not None:
                downstream.discard(identifier)
    state.upstream[identifier] = set()
    state.downstream.setdefault(identifier, set())
    for dependency in dependency_set:
        state.upstream[identifier].add(dependency)
        state.downstream.setdefault(dependency, set()).add(identifier)
    state.nodes[identifier] = _ModelNode(
        node_id=identifier,
        action=action,
        dependencies=dependency_set,
        priority=int(priority),
        retries=int(retries),
    )


# ------------------------------------------------------------------------------
# 1.2 DAG.add_edge
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.DAG.add_edge)
def add_edge(): pass

@add_edge.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(upstream_id, NotBoundType):
        upstream_id = _pick_node(state)
    if isinstance(downstream_id, NotBoundType):
        downstream_id = _pick_node(state)
    return (upstream_id, downstream_id)

@add_edge.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    upstream = str(upstream_id)
    downstream = str(downstream_id)
    missing = None
    if upstream not in state.nodes:
        missing = upstream
    elif downstream not in state.nodes:
        missing = downstream
    if outcome is NotBound:
        if missing is not None:
            return Raised(_node_not_found(missing))
        return Value(None)
    if isinstance(outcome, Raised):
        if (
            missing is not None
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == missing
        ):
            return outcome
        return None
    if missing is None and isinstance(outcome, Value) and outcome.val is None:
        return outcome
    return None

@add_edge.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any,
) -> None:
    upstream = str(upstream_id)
    downstream = str(downstream_id)
    state.upstream.setdefault(downstream, set()).add(upstream)
    state.downstream.setdefault(upstream, set()).add(downstream)


# ------------------------------------------------------------------------------
# 1.3 DAG.remove_node
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.DAG.remove_node)
def remove_node(): pass

@remove_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@remove_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    identifier = str(node_id)
    if outcome is NotBound:
        if identifier not in state.nodes:
            return Raised(_node_not_found(identifier))
        return Value(None)
    if isinstance(outcome, Raised):
        if (
            identifier not in state.nodes
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == identifier
        ):
            return outcome
        return None
    if isinstance(outcome, Value) and outcome.val is None:
        if identifier in state.nodes:
            return outcome
        return None
    return None

@remove_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    identifier = str(node_id)
    for dependency in state.upstream.get(identifier, set()):
        downstream = state.downstream.get(dependency)
        if downstream is not None:
            downstream.discard(identifier)
    for dependent in state.downstream.get(identifier, set()):
        upstream = state.upstream.get(dependent)
        if upstream is not None:
            upstream.discard(identifier)
    state.nodes.pop(identifier, None)
    state.upstream.pop(identifier, None)
    state.downstream.pop(identifier, None)
    state.states.pop(identifier, None)


# ------------------------------------------------------------------------------
# 1.4 DAG.has_node
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.DAG.has_node)
def has_node(): pass

@has_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@has_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    expected = str(node_id) in state.nodes
    if outcome is NotBound:
        return Value(expected)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.get_node)
def get_node(): pass

@get_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@get_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    identifier = str(node_id)
    if outcome is NotBound:
        if identifier not in state.nodes:
            return Raised(_node_not_found(identifier))
        return Value(_definition(state.nodes[identifier]))
    if isinstance(outcome, Raised):
        if (
            identifier not in state.nodes
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == identifier
        ):
            return outcome
        return None
    if (
        identifier in state.nodes
        and isinstance(outcome, Value)
        and isinstance(outcome.val, NodeDefinition)
    ):
        expected = _definition(state.nodes[identifier])
        if (
            outcome.val.node_id == expected.node_id
            and outcome.val.dependencies == expected.dependencies
            and outcome.val.priority == expected.priority
            and outcome.val.retries == expected.retries
        ):
            return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.get_dependencies)
def get_dependencies(): pass

@get_dependencies.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@get_dependencies.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    identifier = str(node_id)
    if outcome is NotBound:
        if identifier not in state.nodes:
            return Raised(_node_not_found(identifier))
        return Value(set(state.upstream.get(identifier, set())))
    if isinstance(outcome, Raised):
        if (
            identifier not in state.nodes
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == identifier
        ):
            return outcome
        return None
    if (
        identifier in state.nodes
        and isinstance(outcome, Value)
        and set(outcome.val) == set(state.upstream.get(identifier, set()))
    ):
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.get_dependents)
def get_dependents(): pass

@get_dependents.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@get_dependents.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    identifier = str(node_id)
    if outcome is NotBound:
        if identifier not in state.nodes:
            return Raised(_node_not_found(identifier))
        return Value(set(state.downstream.get(identifier, set())))
    if isinstance(outcome, Raised):
        if (
            identifier not in state.nodes
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == identifier
        ):
            return outcome
        return None
    if (
        identifier in state.nodes
        and isinstance(outcome, Value)
        and set(outcome.val) == set(state.downstream.get(identifier, set()))
    ):
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.all_nodes)
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
    expected = set(state.nodes)
    if outcome is NotBound:
        return Value(expected)
    if isinstance(outcome, Value) and set(outcome.val) == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.validate)
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
    missing: Optional[str] = None
    for identifier, node in state.nodes.items():
        candidates = set(node.dependencies)
        candidates.update(state.upstream.get(identifier, set()))
        for dependency in candidates:
            if dependency not in state.nodes:
                missing = dependency
                break
        if missing is not None:
            break
    cycle = _model_cycle(state)
    if outcome is NotBound:
        if missing is not None:
            return Raised(_node_not_found(missing))
        if cycle is not None:
            return Raised(_cycle_error(cycle))
        return Value(None)
    if isinstance(outcome, Raised):
        if (
            missing is not None
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == missing
        ):
            return outcome
        if (
            missing is None
            and cycle is not None
            and isinstance(outcome.exc, CycleError)
            and outcome.exc.cycle == cycle
        ):
            return outcome
        return None
    if (
        missing is None
        and cycle is None
        and isinstance(outcome, Value)
        and outcome.val is None
    ):
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.topological_sort)
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
    if outcome is NotBound:
        try:
            return Value(_model_topological_sort(state))
        except CycleError as exc:
            return Raised(exc)
    try:
        expected = _model_topological_sort(state)
    except CycleError as exc:
        if isinstance(outcome, Raised) and isinstance(outcome.exc, CycleError):
            if outcome.exc.cycle == exc.cycle:
                return outcome
        return None
    if isinstance(outcome, Value) and list(outcome.val) == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.find_roots)
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
    expected = {
        identifier
        for identifier in state.nodes
        if not state.upstream.get(identifier, set())
    }
    if outcome is NotBound:
        return Value(expected)
    if isinstance(outcome, Value) and set(outcome.val) == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.find_leaves)
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
    expected = {
        identifier
        for identifier in state.nodes
        if not state.downstream.get(identifier, set())
    }
    if outcome is NotBound:
        return Value(expected)
    if isinstance(outcome, Value) and set(outcome.val) == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAG.compute_critical_path)
def compute_critical_path(): pass

@compute_critical_path.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(estimated_durations, NotBoundType):
        state.tick += 1
        if state.tick % 2 == 0:
            estimated_durations = {
                identifier: float((index % 4) + 1)
                for index, identifier in enumerate(sorted(state.nodes))
            }
        else:
            estimated_durations = None
    return (estimated_durations,)

@compute_critical_path.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        try:
            return Value(_model_critical_path(state, estimated_durations))
        except CycleError as exc:
            return Raised(exc)
    try:
        expected = _model_critical_path(state, estimated_durations)
    except CycleError as exc:
        if isinstance(outcome, Raised) and isinstance(outcome.exc, CycleError):
            if outcome.exc.cycle == exc.cycle:
                return outcome
        return None
    if (
        isinstance(outcome, Value)
        and isinstance(outcome.val, tuple)
        and len(outcome.val) == 2
        and list(outcome.val[0]) == expected[0]
        and float(outcome.val[1]) == expected[1]
    ):
        return outcome
    return None

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

@proto.transition(dag_engine_lite.WaveScheduler.next_wave)
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
    expected = _model_next_wave(state)
    if outcome is NotBound:
        return Value(expected)
    if isinstance(outcome, Value) and list(outcome.val) == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.WaveScheduler.mark_running)
def mark_running(): pass

@mark_running.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@mark_running.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    return _accept_void(outcome)

@mark_running.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    _model_mark_running(state, str(node_id))


# ------------------------------------------------------------------------------
# 1.16 WaveScheduler.mark_succeeded
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.WaveScheduler.mark_succeeded)
def mark_succeeded(): pass

@mark_succeeded.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@mark_succeeded.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if str(node_id) not in state.nodes:
            return Raised(_node_not_found(str(node_id)))
        return Value(None)
    if isinstance(outcome, Raised):
        if (
            str(node_id) not in state.nodes
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == str(node_id)
        ):
            return outcome
        return None
    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    return None

@mark_succeeded.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    _model_mark_succeeded(state, str(node_id))


# ------------------------------------------------------------------------------
# 1.17 WaveScheduler.mark_failed
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.WaveScheduler.mark_failed)
def mark_failed(): pass

@mark_failed.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    if isinstance(failure_policy, NotBoundType):
        state.tick += 1
        policies = list(FailurePolicy)
        failure_policy = policies[state.tick % len(policies)]
    return (node_id, failure_policy)

@mark_failed.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    identifier = str(node_id)
    policy = failure_policy
    missing = identifier not in state.nodes
    if isinstance(policy, FailurePolicy):
        missing = missing and policy is not FailurePolicy.FAIL_FAST
    if outcome is NotBound:
        if missing:
            return Raised(_node_not_found(identifier))
        return Value(None)
    if isinstance(outcome, Raised):
        if (
            missing
            and isinstance(outcome.exc, NodeNotFoundError)
            and outcome.exc.node_id == identifier
        ):
            return outcome
        return None
    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    return None

@mark_failed.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    _model_mark_failed(state, str(node_id), failure_policy)


# ------------------------------------------------------------------------------
# 1.18 WaveScheduler.is_finished
# ------------------------------------------------------------------------------

@proto.transition(dag_engine_lite.WaveScheduler.is_finished)
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
    expected = _model_is_finished(state)
    if outcome is NotBound:
        return Value(expected)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.WaveScheduler.get_state)
def get_state(): pass

@get_state.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(node_id, NotBoundType):
        node_id = _pick_node(state)
    return (node_id,)

@get_state.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    identifier = str(node_id)
    states = _model_get_all_states(state)
    if outcome is NotBound:
        if identifier not in states:
            return Raised(KeyError(identifier))
        return Value(states[identifier])
    if isinstance(outcome, Raised):
        if isinstance(outcome.exc, KeyError) and identifier not in states:
            return outcome
        return None
    if isinstance(outcome, Value) and identifier in states:
        if outcome.val == states[identifier]:
            return outcome
    return None

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

@proto.transition(dag_engine_lite.WaveScheduler.get_all_states)
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
    expected = _model_get_all_states(state)
    if outcome is NotBound:
        return Value(dict(expected))
    if isinstance(outcome, Value) and dict(outcome.val) == expected:
        return outcome
    return None

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

@proto.transition(dag_engine_lite.DAGRunner.run)
def run(): pass

@run.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    if isinstance(failure_policy, NotBoundType):
        state.tick += 1
        policies = list(FailurePolicy)
        failure_policy = policies[state.tick % len(policies)]
    return (failure_policy,)

@run.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        try:
            return Value(_model_run(state, failure_policy))
        except DAGError as exc:
            return Raised(exc)
    if isinstance(outcome, Raised):
        return outcome if isinstance(outcome.exc, DAGError) else None
    if isinstance(outcome, Value) and isinstance(outcome.val, DAGRunReport):
        report = outcome.val
        if report.total_nodes != len(state.nodes):
            return None
        try:
            expected_path, _ = _model_critical_path(state)
        except DAGError:
            return None
        if tuple(report.critical_path) != tuple(expected_path):
            return None
        return outcome
    return None

@run.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    if not isinstance(result, DAGRunReport):
        return
    for node_id, node_result in result.results.items():
        state.states[node_id] = node_result.state
    state.results = dict(result.results)


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_dag_engine_lite_fakes(
    state: DagEngineLiteState,
) -> Tuple[dag_engine_lite.DAG, dag_engine_lite.WaveScheduler, dag_engine_lite.DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = proto.make_state_machine(state)
    return (
        sm.as_fake(dag_engine_lite.DAG),
        sm.as_fake(dag_engine_lite.WaveScheduler),
        sm.as_fake(dag_engine_lite.DAGRunner),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestDagEngineLiteUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to the state machine specification."""

    def setUp(self) -> None:
        self.state = DagEngineLiteState()
        self.dag, self.scheduler, self.runner = make_dag_engine_lite_fakes(
            self.state
        )

    def test_fake_initial_state(self) -> None:
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.all_nodes(), set())
        self.assertTrue(self.scheduler.is_finished())

    def test_fake_add_and_inspect(self) -> None:
        self.dag.add_node("a", lambda: 1, priority=2)
        self.dag.add_node("b", lambda: 2, dependencies=["a"], priority=5)
        self.assertTrue(self.dag.has_node("a"))
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})
        definition = self.dag.get_node("b")
        self.assertEqual(definition.dependencies, frozenset({"a"}))
        self.assertEqual(definition.priority, 5)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_fake_add_edge_and_remove(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependencies("b"), set())

    def test_fake_missing_nodes_raise(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("ghost", "also_ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("ghost")
        with self.assertRaises(KeyError):
            self.scheduler.get_state("ghost")

    def test_fake_validate_and_topological_sort(self) -> None:
        self.dag.add_node("a", lambda: 1, priority=1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.validate()
        self.assertEqual(self.dag.topological_sort(), ["a", "b"])
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})
        self.dag.add_node("ghosted", lambda: 3, dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_fake_validate_cycle(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_fake_critical_path(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 2.0)
        weighted_path, weighted = self.dag.compute_critical_path(
            {"a": 2.5, "b": 4.0}
        )
        self.assertEqual(weighted_path, ["a", "b"])
        self.assertEqual(weighted, 6.5)

    def test_fake_wave_lifecycle(self) -> None:
        self.dag.add_node("low", lambda: 1, priority=5)
        self.dag.add_node("high", lambda: 2, priority=10)
        self.dag.add_node("child", lambda: 3, dependencies=["low"])
        self.assertEqual(self.scheduler.next_wave(), ["high", "low"])
        self.scheduler.mark_running("low")
        self.assertEqual(self.scheduler.get_state("low"), NodeState.RUNNING)
        self.scheduler.mark_succeeded("low")
        self.assertEqual(self.scheduler.get_state("low"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.get_state("child"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["high", "child"])
        self.assertEqual(
            self.scheduler.get_all_states(),
            {
                "low": NodeState.SUCCEEDED,
                "high": NodeState.READY,
                "child": NodeState.READY,
            },
        )
        self.assertFalse(self.scheduler.is_finished())

    def test_fake_mark_failed_policies(self) -> None:
        self.dag.add_node("parent", lambda: 1)
        self.dag.add_node("child", lambda: 2, dependencies=["parent"])
        self.dag.add_node("independent", lambda: 3)
        self.scheduler.mark_failed("parent", FailurePolicy.FAIL_FAST)
        self.assertEqual(
            set(self.scheduler.get_all_states().values()),
            {NodeState.FAILED, NodeState.CANCELLED},
        )
        self.assertTrue(self.scheduler.is_finished())

        self.state = DagEngineLiteState()
        self.dag, self.scheduler, self.runner = make_dag_engine_lite_fakes(
            self.state
        )
        self.dag.add_node("parent", lambda: 1)
        self.dag.add_node("child", lambda: 2, dependencies=["parent"])
        self.scheduler.mark_failed("parent", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("child"), NodeState.SKIPPED)

    def test_fake_run(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(report.critical_path, ("a", "b"))
        self.assertEqual(
            self.scheduler.get_all_states(),
            {"a": NodeState.SUCCEEDED, "b": NodeState.SUCCEEDED},
        )


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(dag_engine_lite.DAG)
        self.scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self.runner = get_singleton(dag_engine_lite.DAGRunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_error_records(self) -> None:
        cause = ValueError("boom")
        base = DAGError("base failure")
        cycle = CycleError("cycle failure", ("a", "b", "a"))
        missing = NodeNotFoundError("missing failure", "a")
        execution = NodeExecutionError("execution failure", "a", cause)
        self.assertEqual(str(base), "base failure")
        self.assertEqual(str(cycle), "cycle failure")
        self.assertEqual(str(missing), "missing failure")
        self.assertEqual(str(execution), "execution failure")
        self.assertEqual(cycle.cycle, ("a", "b", "a"))
        self.assertEqual(missing.node_id, "a")
        self.assertIs(execution.cause, cause)

    def test_add_node_and_inspection(self) -> None:
        self.dag.add_node("a", lambda: 1, priority=1, retries=1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"], priority=5)
        self.dag.add_node("c", lambda: 3)

        self.assertTrue(self.dag.has_node("a"))
        self.assertFalse(self.dag.has_node("ghost"))
        self.assertEqual(self.dag.all_nodes(), {"a", "b", "c"})
        definition = self.dag.get_node("b")
        self.assertEqual(definition.node_id, "b")
        self.assertEqual(definition.dependencies, frozenset({"a"}))
        self.assertEqual(definition.priority, 5)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("ghost")

        # Re-registration replaces upstream edges but keeps downstream dependents.
        self.dag.add_node("a", lambda: 10, dependencies=["b"])
        self.assertEqual(self.dag.get_dependencies("a"), {"b"})
        self.assertEqual(self.dag.get_dependents("b"), {"a"})
        self.dag.add_node("a", lambda: 11)
        self.assertEqual(self.dag.get_dependencies("a"), set())
        self.assertEqual(self.dag.get_dependents("b"), set())

    def test_add_edge_and_errors(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

        with self.assertRaises(NodeNotFoundError) as missing_upstream:
            self.dag.add_edge("ghost", "b")
        self.assertEqual(missing_upstream.exception.node_id, "ghost")
        with self.assertRaises(NodeNotFoundError) as missing_downstream:
            self.dag.add_edge("a", "ghost")
        self.assertEqual(missing_downstream.exception.node_id, "ghost")

    def test_remove_node_purges_edges_and_scheduler_state(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.add_node("c", lambda: 3, dependencies=["b"])
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")

        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertNotIn("b", self.scheduler.get_all_states())

        with self.assertRaises(NodeNotFoundError) as missing:
            self.dag.remove_node("b")
        self.assertEqual(missing.exception.node_id, "b")

    def test_validate_success_missing_and_cycle(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.validate()

        self.dag.add_node("consumer", lambda: 3, dependencies=["provider"])
        with self.assertRaises(NodeNotFoundError) as missing:
            self.dag.validate()
        self.assertEqual(missing.exception.node_id, "provider")
        self.dag.add_node("provider", lambda: 4)
        self.dag.validate()

        self.dag.add_edge("b", "a")
        with self.assertRaises(CycleError) as cycle:
            self.dag.validate()
        self.assertEqual(cycle.exception.cycle, ("a", "b", "a"))

    def test_topological_sort_priority_ties_and_cycles(self) -> None:
        self.dag.add_node("beta", lambda: 1, priority=5)
        self.dag.add_node("alpha", lambda: 2, priority=5)
        self.dag.add_node("top", lambda: 3, priority=10)
        self.dag.add_node("leaf", lambda: 4, dependencies=["beta"])
        self.assertEqual(
            self.dag.topological_sort(), ["top", "alpha", "beta", "leaf"]
        )

        self.dag.add_edge("leaf", "top")
        self.dag.add_edge("top", "leaf")
        with self.assertRaises(CycleError) as cycle:
            self.dag.topological_sort()
        self.assertTrue(cycle.exception.cycle)

        self.dag.remove_node("leaf")
        self.dag.remove_node("top")
        self.dag.add_node("dangling", lambda: 5, dependencies=["ghost"])
        with self.assertRaises(CycleError) as dangling:
            self.dag.topological_sort()
        self.assertEqual(dangling.exception.cycle, ())

    def test_find_roots_and_leaves(self) -> None:
        self.dag.add_node("root_a", lambda: 1)
        self.dag.add_node("root_b", lambda: 2)
        self.dag.add_node("middle", lambda: 3, dependencies=["root_a"])
        self.dag.add_node("leaf", lambda: 4, dependencies=["middle"])
        self.assertEqual(self.dag.find_roots(), {"root_a", "root_b"})
        self.assertEqual(self.dag.find_leaves(), {"root_b", "leaf"})

    def test_compute_critical_path(self) -> None:
        self.assertEqual(self.dag.compute_critical_path(), ([], 0.0))

        self.dag.add_node("start", lambda: 1)
        self.dag.add_node("short", lambda: 2, dependencies=["start"])
        self.dag.add_node("long_a", lambda: 3, dependencies=["start"])
        self.dag.add_node("long_b", lambda: 4, dependencies=["start"])
        self.dag.add_node(
            "end", lambda: 5, dependencies=["short", "long_a", "long_b"]
        )

        path, total = self.dag.compute_critical_path(
            {"start": 2.5, "short": 1.0, "long_a": 4.0, "long_b": 4.0, "end": 1.5}
        )
        self.assertEqual(path, ["start", "long_a", "end"])
        self.assertEqual(total, 8.0)

        default_path, default_total = self.dag.compute_critical_path()
        self.assertEqual(default_path, ["start", "long_a", "end"])
        self.assertEqual(default_total, 3.0)

    def test_scheduler_waves_states_and_completion(self) -> None:
        self.dag.add_node("low", lambda: 1, priority=5)
        self.dag.add_node("high", lambda: 2, priority=10)
        self.dag.add_node("child", lambda: 3, dependencies=["low"])
        self.assertEqual(self.scheduler.next_wave(), ["high", "low"])
        self.scheduler.mark_running("low")
        self.assertEqual(self.scheduler.get_state("low"), NodeState.RUNNING)
        self.scheduler.mark_succeeded("low")
        self.assertEqual(self.scheduler.get_state("low"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.get_state("child"), NodeState.READY)
        # Repeated success sees an already-promoted dependent and leaves it READY.
        self.scheduler.mark_succeeded("low")
        self.assertEqual(self.scheduler.get_state("child"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["high", "child"])
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(
            self.scheduler.get_all_states(),
            {
                "low": NodeState.SUCCEEDED,
                "high": NodeState.READY,
                "child": NodeState.READY,
            },
        )
        self.scheduler.mark_succeeded("high")
        self.scheduler.mark_succeeded("child")
        self.assertTrue(self.scheduler.is_finished())

        # A node registered after its prerequisite succeeded is promoted to READY.
        self.dag.add_node("late", lambda: 4, dependencies=["high"])
        self.assertEqual(self.scheduler.next_wave(), ["late"])

        with self.assertRaises(KeyError):
            self.scheduler.get_state("ghost")

    def test_scheduler_empty_graph(self) -> None:
        self.assertEqual(self.dag.all_nodes(), set())
        self.assertEqual(self.scheduler.next_wave(), [])
        self.assertEqual(self.scheduler.get_all_states(), {})
        self.assertTrue(self.scheduler.is_finished())

    def test_failure_policy_fail_fast(self) -> None:
        self.dag.add_node("parent", lambda: 1)
        self.dag.add_node("child", lambda: 2, dependencies=["parent"])
        self.dag.add_node("independent", lambda: 3)
        self.assertEqual(self.scheduler.next_wave(), ["independent", "parent"])
        self.scheduler.mark_failed("parent", FailurePolicy.FAIL_FAST)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["parent"], NodeState.FAILED)
        self.assertEqual(states["child"], NodeState.CANCELLED)
        self.assertEqual(states["independent"], NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_failure_policy_skip_downstream_diamond(self) -> None:
        self.dag.add_node("parent", lambda: 1)
        self.dag.add_node("left", lambda: 2, dependencies=["parent"])
        self.dag.add_node("right", lambda: 3, dependencies=["parent"])
        self.dag.add_node("join", lambda: 4, dependencies=["left", "right"])
        self.dag.add_node("independent", lambda: 5)
        self.scheduler.mark_failed("parent", FailurePolicy.SKIP_DOWNSTREAM)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["parent"], NodeState.FAILED)
        self.assertEqual(states["left"], NodeState.SKIPPED)
        self.assertEqual(states["right"], NodeState.SKIPPED)
        self.assertEqual(states["join"], NodeState.SKIPPED)
        self.assertEqual(states["independent"], NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())

    def test_failure_policy_continue_on_error_and_terminal_bypass(self) -> None:
        self.dag.add_node("parent", lambda: 1)
        self.dag.add_node("child", lambda: 2, dependencies=["parent"])
        self.dag.add_node("independent", lambda: 3)
        self.scheduler.mark_succeeded("child")
        self.scheduler.mark_failed("parent", FailurePolicy.CONTINUE_ON_ERROR)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["parent"], NodeState.FAILED)
        self.assertEqual(states["child"], NodeState.SUCCEEDED)
        self.assertEqual(states["independent"], NodeState.READY)

    def test_failure_policy_missing_transitive_dependent(self) -> None:
        self.dag.add_node("parent", lambda: 1)
        with self.assertRaises(NodeNotFoundError):
            self.scheduler.mark_failed("ghost", FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_success_report(self) -> None:
        self.dag.add_node("a", lambda: 1)
        self.dag.add_node("b", lambda: 2, dependencies=["a"])
        self.dag.add_node("c", lambda: 3, dependencies=["b"])
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.critical_path, ("a", "b", "c"))
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(
            {result.state for result in report.results.values()},
            {NodeState.SUCCEEDED},
        )

    def test_runner_empty_graph(self) -> None:
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.critical_path, ())
        self.assertEqual(report.results, {})

    def test_runner_retry_success(self) -> None:
        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("transient")
            return "ok"

        self.dag.add_node("flaky", flaky, retries=2)
        report = self.runner.run()
        self.assertEqual(report.succeeded_nodes, ("flaky",))
        self.assertEqual(report.results["flaky"].retries_attempted, 2)
        self.assertEqual(report.results["flaky"].value, "ok")

    def test_runner_fail_fast(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("a_failing", boom, retries=2)
        self.dag.add_node("z_child", lambda: 1, dependencies=["a_failing"])
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("a_failing",))
        self.assertEqual(report.cancelled_nodes, ("z_child",))
        self.assertEqual(report.succeeded_nodes, ())
        self.assertIsInstance(report.results["a_failing"].error, RuntimeError)
        self.assertEqual(report.results["a_failing"].retries_attempted, 2)
        self.assertEqual(
            self.scheduler.get_state("z_child"), NodeState.CANCELLED
        )

    def test_runner_fail_fast_halts_wave(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("a_failing", boom)
        self.dag.add_node("b_after", lambda: 1)
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("a_failing",))
        self.assertEqual(report.cancelled_nodes, ("b_after",))
        self.assertEqual(report.succeeded_nodes, ())

    def test_runner_continue_on_error(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("a_failing", boom)
        self.dag.add_node("b_child", lambda: 1, dependencies=["a_failing"])
        self.dag.add_node("c_independent", lambda: 2)
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("a_failing",))
        self.assertEqual(report.skipped_nodes, ("b_child",))
        self.assertEqual(report.succeeded_nodes, ("c_independent",))
        self.assertEqual(report.cancelled_nodes, ())

    def test_runner_skip_downstream(self) -> None:
        def boom() -> None:
            raise RuntimeError("boom")

        self.dag.add_node("z_failing", boom)
        self.dag.add_node("a_child", lambda: 1, dependencies=["z_failing"])
        report = self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("z_failing",))
        self.assertEqual(report.skipped_nodes, ("a_child",))

    def test_runner_validate_failure(self) -> None:
        self.dag.add_node("consumer", lambda: 1, dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.runner.run()

    def test_dag_only_registry_purges_without_scheduler(self) -> None:
        registry = LifecycleRegistry()
        registry.register_singleton(
            DAG, keys=[DAG, dag_engine_lite.DAG], tier=system
        )
        phase_scope = enter_phase(system, registry=registry)
        with phase_scope:
            dag = get_singleton(dag_engine_lite.DAG)
            dag.add_node("solo", lambda: 1)
            dag.remove_node("solo")
            self.assertEqual(dag.all_nodes(), set())


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
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self.dag, self.scheduler, self.runner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def close(self) -> None:
        if getattr(self, "phase_scope", None) is not None:
            self.phase_scope.__exit__(None, None, None)


def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)
