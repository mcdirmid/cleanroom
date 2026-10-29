"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite.

The model mirrors the synchronous DAG execution engine specified in ``low/dag_engine_lite.pyi``
and ``low/dag_engine_lite_impl.pyi``: a graph of task nodes with deferred dependency validation,
a wave scheduler tracking per-node execution states, and a sequential runner applying failure
policies. The state machine tracks an abstract adjacency model, synthesizes in-memory fakes for
the ``DAG``, ``WaveScheduler``, and ``DAGRunner`` singletons, and verifies the concrete
implementation through operational postconditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Mapping, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_5.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGError,
    DAGRunReport,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)
from benchmark_5.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


_TERMINAL: FrozenSet[NodeState] = frozenset(
    {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
)
_FAILURE_TERMINAL: FrozenSet[NodeState] = frozenset(
    {NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
)


def _benign_action() -> None:
    """A deterministic successfully-completing node action."""
    return None


def _failing_action() -> None:
    """A deterministic node action that always raises."""
    raise RuntimeError("node action failed")


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass(frozen=True)
class _NodeSpec:
    """Abstract model record of a registered node definition."""
    action: Any
    dependencies: FrozenSet[str]
    priority: int
    retries: int


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    initialized: bool = True
    nodes: dict[str, _NodeSpec] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    last_report: Any = None


def _copy_state(state: DagEngineLiteState) -> DagEngineLiteState:
    return DagEngineLiteState(
        initialized=state.initialized,
        nodes=dict(state.nodes),
        upstream={key: set(value) for key, value in state.upstream.items()},
        downstream={key: set(value) for key, value in state.downstream.items()},
        states=dict(state.states),
        results=dict(state.results),
        last_report=state.last_report,
    )


def _effective_states(state: DagEngineLiteState) -> dict[str, NodeState]:
    """Model scheduler view defaulting roots to READY and non-roots to PENDING."""
    resolved = dict(state.states)
    for node_id in state.nodes:
        if node_id not in resolved:
            if state.upstream.get(node_id):
                resolved[node_id] = NodeState.PENDING
            else:
                resolved[node_id] = NodeState.READY
    return {node_id: resolved[node_id] for node_id in state.nodes}


def _sync_states(state: DagEngineLiteState) -> None:
    resolved = _effective_states(state)
    state.states.clear()
    state.states.update(resolved)


def _sorted_ready(state: DagEngineLiteState) -> list[str]:
    resolved = _effective_states(state)
    candidates = [
        node_id
        for node_id in state.nodes
        if resolved[node_id] is NodeState.READY
        and all(
            resolved.get(upstream_id) is NodeState.SUCCEEDED
            for upstream_id in state.upstream.get(node_id, set())
        )
    ]
    return sorted(candidates, key=lambda node_id: (-state.nodes[node_id].priority, node_id))


def _is_finished(state: DagEngineLiteState) -> bool:
    if not state.nodes:
        return True
    resolved = _effective_states(state)
    if all(resolved[node_id] in _TERMINAL for node_id in state.nodes):
        return True
    for node_id in state.nodes:
        if resolved[node_id] in _TERMINAL:
            continue
        blocked = any(
            resolved.get(upstream_id) in _FAILURE_TERMINAL
            for upstream_id in state.upstream.get(node_id, set())
        )
        if not blocked:
            return False
    return True


def _topological_order(state: DagEngineLiteState) -> Optional[list[str]]:
    in_degree = {node_id: len(state.upstream.get(node_id, set())) for node_id in state.nodes}
    ready = [node_id for node_id in state.nodes if in_degree[node_id] == 0]
    order: list[str] = []
    while ready:
        ready.sort(key=lambda node_id: (-state.nodes[node_id].priority, node_id))
        node_id = ready.pop(0)
        order.append(node_id)
        for dependent in state.downstream.get(node_id, set()):
            if dependent in in_degree:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
    if len(order) != len(state.nodes):
        return None
    return order


def _find_cycle(state: DagEngineLiteState) -> Optional[Tuple[str, ...]]:
    visiting: dict[str, int] = {}
    stack: list[str] = []

    def visit(node_id: str) -> Optional[Tuple[str, ...]]:
        visiting[node_id] = 1
        stack.append(node_id)
        for dependency in sorted(state.upstream.get(node_id, set())):
            if dependency not in state.nodes:
                continue
            if visiting.get(dependency, 0) == 1:
                start = stack.index(dependency)
                return tuple(stack[start:])
            if visiting.get(dependency, 0) == 0:
                found = visit(dependency)
                if found is not None:
                    return found
        visiting[node_id] = 2
        stack.pop()
        return None

    for node_id in state.nodes:
        if visiting.get(node_id, 0) == 0:
            found = visit(node_id)
            if found is not None:
                return found
    return None


def _missing_dependency(state: DagEngineLiteState) -> Optional[str]:
    for node_id in sorted(state.nodes):
        for dependency in sorted(state.upstream.get(node_id, set())):
            if dependency not in state.nodes:
                return dependency
    return None


def _critical_path(
    state: DagEngineLiteState,
    durations: Optional[Mapping[str, float]] = None,
) -> Tuple[list[str], float]:
    order = _topological_order(state)
    if not order:
        return [], 0.0
    weights = {node_id: float(durations.get(node_id, 1.0)) if durations else 1.0 for node_id in order}
    earliest: dict[str, float] = {}
    for node_id in order:
        predecessors = [earliest[upstream_id] for upstream_id in state.upstream.get(node_id, set()) if upstream_id in earliest]
        earliest[node_id] = (max(predecessors) if predecessors else 0.0) + weights[node_id]
    terminal = max(order, key=lambda node_id: earliest[node_id])
    path = [terminal]
    while True:
        predecessors = [upstream_id for upstream_id in state.upstream.get(path[-1], set()) if upstream_id in earliest]
        if not predecessors:
            break
        path.append(max(predecessors, key=lambda node_id: earliest[node_id]))
    path.reverse()
    return path, earliest[terminal]


def _apply_add_node(
    state: DagEngineLiteState,
    node_id: str,
    action: Any,
    dependencies: Any,
    priority: int,
    retries: int,
) -> None:
    new_dependencies = set(dependencies or ())
    for old_dependency in set(state.upstream.get(node_id, set())):
        state.downstream.get(old_dependency, set()).discard(node_id)
    state.nodes[node_id] = _NodeSpec(
        action=action,
        dependencies=frozenset(new_dependencies),
        priority=priority,
        retries=retries,
    )
    state.upstream[node_id] = set(new_dependencies)
    state.downstream.setdefault(node_id, set())
    for dependency in new_dependencies:
        state.downstream.setdefault(dependency, set()).add(node_id)


def _apply_add_edge(state: DagEngineLiteState, upstream_id: str, downstream_id: str) -> None:
    if upstream_id not in state.nodes or downstream_id not in state.nodes:
        return
    state.upstream.setdefault(downstream_id, set()).add(upstream_id)
    state.downstream.setdefault(upstream_id, set()).add(downstream_id)


def _apply_remove_node(state: DagEngineLiteState, node_id: str) -> None:
    if node_id not in state.nodes:
        return
    for upstream_id in set(state.upstream.get(node_id, set())):
        state.downstream.get(upstream_id, set()).discard(node_id)
    for dependent in set(state.downstream.get(node_id, set())):
        if dependent in state.nodes:
            state.upstream.get(dependent, set()).discard(node_id)
    del state.nodes[node_id]
    state.upstream.pop(node_id, None)
    state.downstream.pop(node_id, None)
    state.states.pop(node_id, None)


def _apply_mark_running(state: DagEngineLiteState, node_id: str) -> None:
    _sync_states(state)
    if node_id in state.nodes:
        state.states[node_id] = NodeState.RUNNING


def _apply_mark_succeeded(state: DagEngineLiteState, node_id: str) -> None:
    _sync_states(state)
    state.states[node_id] = NodeState.SUCCEEDED
    for dependent in state.downstream.get(node_id, set()):
        if dependent not in state.nodes:
            continue
        if state.states.get(dependent) is not NodeState.PENDING:
            continue
        if all(
            state.states.get(upstream_id) is NodeState.SUCCEEDED
            for upstream_id in state.upstream.get(dependent, set())
        ):
            state.states[dependent] = NodeState.READY


def _apply_mark_failed(
    state: DagEngineLiteState,
    node_id: str,
    failure_policy: Optional[FailurePolicy],
) -> None:
    _sync_states(state)
    state.states[node_id] = NodeState.FAILED
    policy = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
    if policy is FailurePolicy.FAIL_FAST:
        for other_id in state.nodes:
            if state.states.get(other_id) not in _TERMINAL:
                state.states[other_id] = NodeState.CANCELLED
        return
    pending = list(state.downstream.get(node_id, set()))
    seen: set[str] = set()
    while pending:
        dependent = pending.pop()
        if dependent in seen:
            continue
        seen.add(dependent)
        if dependent not in state.nodes:
            continue
        if state.states.get(dependent) not in _TERMINAL:
            state.states[dependent] = NodeState.SKIPPED
        pending.extend(state.downstream.get(dependent, set()))
    for other_id in state.nodes:
        if state.states.get(other_id) is not NodeState.PENDING:
            continue
        if all(
            state.states.get(upstream_id) is NodeState.SUCCEEDED
            for upstream_id in state.upstream.get(other_id, set())
        ):
            state.states[other_id] = NodeState.READY


def _apply_run(state: DagEngineLiteState, report: Any) -> None:
    _sync_states(state)
    if not isinstance(report, DAGRunReport):
        return
    for node_id in state.nodes:
        result = report.results.get(node_id)
        if result is not None:
            state.states[node_id] = result.state
    state.results = dict(report.results)
    state.last_report = report


def _states_after_mark_running(state: DagEngineLiteState, node_id: str) -> dict[str, NodeState]:
    clone = _copy_state(state)
    _apply_mark_running(clone, node_id)
    return dict(clone.states)


def _states_after_mark_succeeded(state: DagEngineLiteState, node_id: str) -> dict[str, NodeState]:
    clone = _copy_state(state)
    _apply_mark_succeeded(clone, node_id)
    return dict(clone.states)


def _states_after_mark_failed(
    state: DagEngineLiteState,
    node_id: str,
    failure_policy: Optional[FailurePolicy],
) -> dict[str, NodeState]:
    clone = _copy_state(state)
    _apply_mark_failed(clone, node_id, failure_policy)
    return dict(clone.states)


def _is_error_outcome(outcome: Any) -> bool:
    return isinstance(outcome, BaseException) or type(outcome).__name__ == "Raised"


def _reaches(state: DagEngineLiteState, start_id: str, target_id: str) -> bool:
    frontier = [start_id]
    seen: set[str] = set()
    while frontier:
        current = frontier.pop()
        if current == target_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(sorted(state.downstream.get(current, set())))
    return False


def _model_run_report(
    state: DagEngineLiteState,
    failure_policy: Optional[FailurePolicy] = None,
) -> Any:
    clone = _copy_state(state)
    executed: list[str] = []
    while not _is_finished(clone):
        wave = _sorted_ready(clone)
        if not wave:
            break
        for node_id in wave:
            _apply_mark_succeeded(clone, node_id)
            executed.append(node_id)
    results: dict[str, Any] = {}
    for node_id in clone.nodes:
        results[node_id] = NodeResult[Any](
            node_id=node_id,
            state=clone.states.get(node_id, NodeState.SUCCEEDED),
        )
    path, _weight = _critical_path(clone, None)
    succeeded = tuple(node_id for node_id in executed if clone.states.get(node_id) is NodeState.SUCCEEDED)
    failed = tuple(node_id for node_id in clone.nodes if clone.states.get(node_id) is NodeState.FAILED)
    skipped = tuple(node_id for node_id in clone.nodes if clone.states.get(node_id) is NodeState.SKIPPED)
    cancelled = tuple(node_id for node_id in clone.nodes if clone.states.get(node_id) is NodeState.CANCELLED)
    return DAGRunReport(
        total_nodes=len(clone.nodes),
        succeeded_nodes=succeeded,
        failed_nodes=failed,
        skipped_nodes=skipped,
        cancelled_nodes=cancelled,
        wall_clock_seconds=0.0,
        critical_path=tuple(path),
        results=results,
    )


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)
        self._next_id = 0

    # ------------------------------------------------------------------
    # Generators and recognizers
    # ------------------------------------------------------------------

    def _first_node_id(self) -> str:
        return sorted(self.state.nodes)[0] if self.state.nodes else ""

    def _generate_add_node(self) -> tuple[Any, ...]:
        self._next_id += 1
        node_id = f"auto_node_{self._next_id}"
        dependencies = sorted(self.state.nodes)[:2]
        return (node_id, _benign_action, list(dependencies), self._next_id % 3, 0)

    def _recognize_add_node(
        self,
        node_id: Any = None,
        action: Any = None,
        dependencies: Any = None,
        priority: Any = 0,
        retries: Any = 0,
    ) -> bool:
        return isinstance(node_id, str) and callable(action)

    def _missing_node_id(self) -> str:
        self._next_id += 1
        candidate = f"missing_node_{self._next_id}"
        while candidate in self.state.nodes:
            self._next_id += 1
            candidate = f"missing_node_{self._next_id}"
        return candidate

    def _generate_add_edge(self) -> tuple[Any, ...]:
        node_ids = sorted(self.state.nodes)
        if len(node_ids) < 2:
            return (self._missing_node_id(), self._missing_node_id())
        for upstream_id in node_ids:
            for downstream_id in reversed(node_ids):
                if upstream_id != downstream_id and not _reaches(self.state, downstream_id, upstream_id):
                    return (upstream_id, downstream_id)
        return (node_ids[0], node_ids[-1])

    def _generate_add_edge_missing_upstream(self) -> tuple[Any, ...]:
        return (self._missing_node_id(), self._first_node_id() or self._missing_node_id())

    def _generate_add_edge_missing_downstream(self) -> tuple[Any, ...]:
        return (self._first_node_id(), self._missing_node_id())

    def _generate_existing_node(self) -> tuple[Any, ...]:
        return (self._first_node_id(),)

    def _generate_missing_node(self) -> tuple[Any, ...]:
        return (self._missing_node_id(),)

    def _generate_leaf_node(self) -> tuple[Any, ...]:
        leaves = sorted(
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)
        )
        if leaves:
            return (leaves[0],)
        return (self._first_node_id(),)

    def _generate_mark_failed(self) -> tuple[Any, ...]:
        policies = (FailurePolicy.FAIL_FAST, FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR)
        policy = policies[len(self.state.states) % len(policies)]
        return (self._first_node_id(), policy)

    def _generate_run(self) -> tuple[Any, ...]:
        policies = (FailurePolicy.FAIL_FAST, FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR)
        policy = policies[len(self.state.nodes) % len(policies)]
        return (policy,)

    def _generate_critical_path(self) -> tuple[Any, ...]:
        return (None,)

    def _recognize_any_node(self, node_id: Any = None) -> bool:
        return isinstance(node_id, str)

    def _recognize_existing_node(self, node_id: Any = None) -> bool:
        return isinstance(node_id, str) and node_id in self.state.nodes

    def _recognize_missing_node(self, node_id: Any = None) -> bool:
        return isinstance(node_id, str) and node_id not in self.state.nodes

    def _recognize_add_edge(self, upstream_id: Any = None, downstream_id: Any = None) -> bool:
        return isinstance(upstream_id, str) and isinstance(downstream_id, str) and upstream_id in self.state.nodes and downstream_id in self.state.nodes

    def _recognize_add_edge_missing_upstream(self, upstream_id: Any = None, downstream_id: Any = None) -> bool:
        return isinstance(upstream_id, str) and upstream_id not in self.state.nodes

    def _recognize_add_edge_missing_downstream(self, upstream_id: Any = None, downstream_id: Any = None) -> bool:
        return (
            isinstance(upstream_id, str)
            and upstream_id in self.state.nodes
            and isinstance(downstream_id, str)
            and downstream_id not in self.state.nodes
        )

    def _recognize_validate_ok(self) -> bool:
        return _missing_dependency(self.state) is None and _topological_order(self.state) is not None

    def _recognize_validate_missing(self) -> bool:
        return _missing_dependency(self.state) is not None

    def _recognize_validate_cycle(self) -> bool:
        return _missing_dependency(self.state) is None and _topological_order(self.state) is None

    def _recognize_topological_ok(self) -> bool:
        return _topological_order(self.state) is not None

    def _recognize_topological_cycle(self) -> bool:
        return _topological_order(self.state) is None

    def _recognize_mark_failed(self, node_id: Any = None, failure_policy: Any = None) -> bool:
        return (
            isinstance(node_id, str)
            and node_id in self.state.nodes
            and (failure_policy is None or isinstance(failure_policy, FailurePolicy))
        )

    def _recognize_run(self, failure_policy: Any = None) -> bool:
        return failure_policy is None or isinstance(failure_policy, FailurePolicy)

    def _recognize_run_ok(self, failure_policy: Any = None) -> bool:
        return (
            self._recognize_run(failure_policy)
            and len(self.state.nodes) > 0
            and _missing_dependency(self.state) is None
            and _topological_order(self.state) is not None
        )

    def _recognize_run_missing_dependency(self, failure_policy: Any = None) -> bool:
        return self._recognize_run(failure_policy) and _missing_dependency(self.state) is not None

    def _recognize_run_cycle(self, failure_policy: Any = None) -> bool:
        return (
            self._recognize_run(failure_policy)
            and _missing_dependency(self.state) is None
            and _topological_order(self.state) is None
        )

    def _recognize_critical_path(self, estimated_durations: Any = None) -> bool:
        return estimated_durations is None or isinstance(estimated_durations, dict)

    # ------------------------------------------------------------------
    # DAG transitions
    # ------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(self, ctx: TransitionContext[DAG, [Any, Any, Any, Any, Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_add_node()))
        ctx.returns(self._returns_add_node)
        ctx.ensures(self._ensure_add_node)
        ctx.update(self._update_add_node)

    def _returns_add_node(
        self,
        node_id: Any = None,
        action: Any = None,
        dependencies: Any = None,
        priority: Any = 0,
        retries: Any = 0,
    ) -> Any:
        return None

    def _ensure_add_node(
        self,
        res: Any,
        target: Any,
        check: Any,
        node_id: Any = None,
        action: Any = None,
        dependencies: Any = None,
        priority: Any = 0,
        retries: Any = 0,
    ) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check(target.has_node(node_id), "node registered in graph")
        definition = target.get_node(node_id)
        check.equal(definition.node_id, node_id)
        check.equal(set(definition.dependencies), set(dependencies or ()))
        check.equal(definition.priority, priority)
        check.equal(definition.retries, retries)
        check(definition.action is action, "action preserved verbatim")

    def _update_add_node(
        self,
        res: Any,
        node_id: Any = None,
        action: Any = None,
        dependencies: Any = None,
        priority: Any = 0,
        retries: Any = 0,
    ) -> None:
        if not isinstance(node_id, str) or not callable(action):
            return
        _apply_add_node(self.state, node_id, action, dependencies, int(priority or 0), int(retries or 0))

    @transition(DAG.add_edge)
    def add_edge(self, ctx: TransitionContext[DAG, [Any, Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_add_edge()))
        ctx.returns(self._returns_add_edge)
        ctx.ensures(self._ensure_add_edge)
        ctx.update(self._update_add_edge)

    @transition(DAG.add_edge)
    def add_edge_missing_upstream(self, ctx: TransitionContext[DAG, [Any, Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_add_edge_missing_upstream()))
        ctx.raises(DAGError, match=".*")

    @transition(DAG.add_edge)
    def add_edge_missing_downstream(self, ctx: TransitionContext[DAG, [Any, Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_add_edge_missing_downstream()))
        ctx.raises(DAGError, match=".*")

    def _returns_add_edge(self, upstream_id: Any = None, downstream_id: Any = None) -> Any:
        return None

    def _ensure_add_edge(
        self,
        res: Any,
        target: Any,
        check: Any,
        upstream_id: Any = None,
        downstream_id: Any = None,
    ) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check(downstream_id in target.get_dependents(upstream_id), "edge established")
        check(upstream_id in target.get_dependencies(downstream_id), "dependency registered")
        expected = set(self.state.upstream.get(downstream_id, set())) | {upstream_id}
        check.equal(target.get_dependencies(downstream_id), expected)

    def _update_add_edge(self, res: Any, upstream_id: Any = None, downstream_id: Any = None) -> None:
        if isinstance(upstream_id, str) and isinstance(downstream_id, str):
            _apply_add_edge(self.state, upstream_id, downstream_id)

    @transition(DAG.remove_node)
    def remove_node(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_leaf_node()))
        ctx.returns(self._returns_remove_node)
        ctx.ensures(self._ensure_remove_node)
        ctx.update(self._update_remove_node)

    @transition(DAG.remove_node)
    def remove_node_missing(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_missing_node()))
        ctx.raises(DAGError, match=".*")

    def _returns_remove_node(self, node_id: Any = None) -> Any:
        return None

    def _ensure_remove_node(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check(not target.has_node(node_id), "node removed from graph")
        for other_id in target.all_nodes():
            check(node_id not in target.get_dependencies(other_id), "incident upstream edge removed")
            check(node_id not in target.get_dependents(other_id), "incident downstream edge removed")

    def _update_remove_node(self, res: Any, node_id: Any = None) -> None:
        if isinstance(node_id, str):
            _apply_remove_node(self.state, node_id)

    @transition(DAG.has_node)
    def has_node(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_has_node)
        ctx.ensures(self._ensure_has_node)
        ctx.update(self._update_noop)

    def _returns_has_node(self, node_id: Any = None) -> Any:
        return node_id in self.state.nodes

    def _ensure_has_node(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, node_id in self.state.nodes)

    @transition(DAG.get_node)
    def get_node(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_get_node)
        ctx.ensures(self._ensure_get_node)
        ctx.update(self._update_noop)

    @transition(DAG.get_node)
    def get_node_missing(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_missing_node()))
        ctx.raises(DAGError, match=".*")

    def _returns_get_node(self, node_id: Any = None) -> Any:
        spec = self.state.nodes.get(node_id)
        if spec is None:
            return None
        return NodeDefinition[Any](
            node_id=node_id,
            action=spec.action,
            dependencies=spec.dependencies,
            priority=spec.priority,
            retries=spec.retries,
        )

    def _ensure_get_node(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        spec = self.state.nodes.get(node_id)
        if spec is None:
            return
        check.equal(res.node_id, node_id)
        check.equal(set(res.dependencies), set(spec.dependencies))
        check.equal(res.priority, spec.priority)
        check.equal(res.retries, spec.retries)
        check(res.action is spec.action, "action identity preserved")

    @transition(DAG.get_dependencies)
    def get_dependencies(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_get_dependencies)
        ctx.ensures(self._ensure_get_dependencies)
        ctx.update(self._update_noop)

    @transition(DAG.get_dependencies)
    def get_dependencies_missing(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_missing_node()))
        ctx.raises(DAGError, match=".*")

    def _returns_get_dependencies(self, node_id: Any = None) -> Any:
        return set(self.state.upstream.get(node_id, set()))

    def _ensure_get_dependencies(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(set(res), set(self.state.upstream.get(node_id, set())))

    @transition(DAG.get_dependents)
    def get_dependents(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_get_dependents)
        ctx.ensures(self._ensure_get_dependents)
        ctx.update(self._update_noop)

    @transition(DAG.get_dependents)
    def get_dependents_missing(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_missing_node()))
        ctx.raises(DAGError, match=".*")

    def _returns_get_dependents(self, node_id: Any = None) -> Any:
        return set(self.state.downstream.get(node_id, set()))

    def _ensure_get_dependents(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(set(res), set(self.state.downstream.get(node_id, set())))

    @transition(DAG.all_nodes)
    def all_nodes(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments()
        ctx.returns(self._returns_all_nodes)
        ctx.ensures(self._ensure_all_nodes)
        ctx.update(self._update_noop)

    def _returns_all_nodes(self) -> Any:
        return set(self.state.nodes)

    def _ensure_all_nodes(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        check.equal(set(res), set(self.state.nodes))

    @transition(DAG.validate)
    def validate(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized
                and _missing_dependency(self.state) is None
                and _topological_order(self.state) is not None,
                "graph is complete and acyclic",
            )
        )
        ctx.arguments()
        ctx.returns(self._returns_validate)
        ctx.ensures(self._ensure_validate)
        ctx.update(self._update_noop)

    @transition(DAG.validate)
    def validate_missing_dependency(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and _missing_dependency(self.state) is not None,
                "graph references a missing dependency",
            )
        )
        ctx.arguments()
        ctx.raises(DAGError, match=".*")

    @transition(DAG.validate)
    def validate_cycle(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized
                and _missing_dependency(self.state) is None
                and _topological_order(self.state) is None,
                "graph contains a dependency cycle",
            )
        )
        ctx.arguments()
        ctx.raises(DAGError, match=".*")

    def _returns_validate(self) -> Any:
        return None

    def _ensure_validate(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check(_missing_dependency(self.state) is None, "graph references only registered nodes")
        check(_topological_order(self.state) is not None, "graph is acyclic")

    @transition(DAG.topological_sort)
    def topological_sort(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and _topological_order(self.state) is not None,
                "graph is acyclic",
            )
        )
        ctx.arguments()
        ctx.returns(self._returns_topological_sort)
        ctx.ensures(self._ensure_topological_sort)
        ctx.update(self._update_noop)

    @transition(DAG.topological_sort)
    def topological_sort_cycle(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and _topological_order(self.state) is None,
                "graph contains a dependency cycle",
            )
        )
        ctx.arguments()
        ctx.raises(DAGError, match=".*")

    def _returns_topological_sort(self) -> Any:
        return _topological_order(self.state) or []

    def _ensure_topological_sort(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        expected = _topological_order(self.state)
        check(expected is not None, "model graph is acyclic")
        check.equal(list(res), expected)

    @transition(DAG.find_roots)
    def find_roots(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments()
        ctx.returns(self._returns_find_roots)
        ctx.ensures(self._ensure_find_roots)
        ctx.update(self._update_noop)

    def _returns_find_roots(self) -> Any:
        return {node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)}

    def _ensure_find_roots(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        expected = {node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)}
        check.equal(set(res), expected)

    @transition(DAG.find_leaves)
    def find_leaves(self, ctx: TransitionContext[DAG, [], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments()
        ctx.returns(self._returns_find_leaves)
        ctx.ensures(self._ensure_find_leaves)
        ctx.update(self._update_noop)

    def _returns_find_leaves(self) -> Any:
        return {node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)}

    def _ensure_find_leaves(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        expected = {node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id)}
        check.equal(set(res), expected)

    @transition(DAG.compute_critical_path)
    def compute_critical_path(self, ctx: TransitionContext[DAG, [Any], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_critical_path()))
        ctx.returns(self._returns_compute_critical_path)
        ctx.ensures(self._ensure_compute_critical_path)
        ctx.update(self._update_noop)

    def _returns_compute_critical_path(self, estimated_durations: Any = None) -> Any:
        return _critical_path(self.state, estimated_durations)

    def _ensure_compute_critical_path(
        self,
        res: Any,
        target: Any,
        check: Any,
        estimated_durations: Any = None,
    ) -> None:
        if _is_error_outcome(res):
            return
        check(isinstance(res, tuple) and len(res) == 2, "critical path outcome shape")
        path = list(res[0])
        weight = float(res[1])
        _expected_path, expected_weight = _critical_path(self.state, estimated_durations)
        check(abs(weight - expected_weight) < 1e-9, "critical path weight matches model")
        check(set(path) <= set(self.state.nodes), "critical path references registered nodes")
        for current_id, next_id in zip(path, path[1:]):
            check(next_id in self.state.downstream.get(current_id, set()), "critical path follows edges")
        if self.state.nodes:
            check(len(path) >= 1, "non-empty critical path for non-empty graph")
            if path:
                check(not self.state.upstream.get(path[0]), "critical path starts at a root")
                durations = estimated_durations or {}
                total = sum(float(durations.get(node_id, 1.0)) for node_id in path)
                check(abs(total - weight) < 1e-9, "critical path weight equals path duration sum")
        else:
            check.equal(path, [])
            check.equal(weight, 0.0)

    # ------------------------------------------------------------------
    # WaveScheduler transitions
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self, ctx: TransitionContext[WaveScheduler, [], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments()
        ctx.returns(self._returns_next_wave)
        ctx.ensures(self._ensure_next_wave)
        ctx.update(self._update_sync)

    def _returns_next_wave(self) -> Any:
        return _sorted_ready(self.state)

    def _ensure_next_wave(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        check.equal(list(res), _sorted_ready(self.state))
        check.equal(dict(target.get_all_states()), _effective_states(self.state))

    @transition(WaveScheduler.mark_running)
    def mark_running(self, ctx: TransitionContext[WaveScheduler, [Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and len(self.state.nodes) > 0, "graph has nodes"
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_mark_running)
        ctx.ensures(self._ensure_mark_running)
        ctx.update(self._update_mark_running)

    def _returns_mark_running(self, node_id: Any = None) -> Any:
        return None

    def _ensure_mark_running(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check.equal(dict(target.get_all_states()), _states_after_mark_running(self.state, node_id))

    def _update_mark_running(self, res: Any, node_id: Any = None) -> None:
        if isinstance(node_id, str):
            _apply_mark_running(self.state, node_id)

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, ctx: TransitionContext[WaveScheduler, [Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and len(self.state.nodes) > 0, "graph has nodes"
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_mark_succeeded)
        ctx.ensures(self._ensure_mark_succeeded)
        ctx.update(self._update_mark_succeeded)

    def _returns_mark_succeeded(self, node_id: Any = None) -> Any:
        return None

    def _ensure_mark_succeeded(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check.equal(dict(target.get_all_states()), _states_after_mark_succeeded(self.state, node_id))

    def _update_mark_succeeded(self, res: Any, node_id: Any = None) -> None:
        if isinstance(node_id, str):
            _apply_mark_succeeded(self.state, node_id)

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, ctx: TransitionContext[WaveScheduler, [Any, Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and len(self.state.nodes) > 0, "graph has nodes"
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_mark_failed()))
        ctx.returns(self._returns_mark_failed)
        ctx.ensures(self._ensure_mark_failed)
        ctx.update(self._update_mark_failed)

    def _returns_mark_failed(self, node_id: Any = None, failure_policy: Any = None) -> Any:
        return None

    def _ensure_mark_failed(
        self,
        res: Any,
        target: Any,
        check: Any,
        node_id: Any = None,
        failure_policy: Any = None,
    ) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, None)
        check.equal(
            dict(target.get_all_states()),
            _states_after_mark_failed(self.state, node_id, failure_policy),
        )

    def _update_mark_failed(self, res: Any, node_id: Any = None, failure_policy: Any = None) -> None:
        if isinstance(node_id, str):
            _apply_mark_failed(self.state, node_id, failure_policy)

    @transition(WaveScheduler.is_finished)
    def is_finished(self, ctx: TransitionContext[WaveScheduler, [], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments()
        ctx.returns(self._returns_is_finished)
        ctx.ensures(self._ensure_is_finished)
        ctx.update(self._update_sync)

    def _returns_is_finished(self) -> Any:
        return _is_finished(self.state)

    def _ensure_is_finished(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, _is_finished(self.state))
        check.equal(dict(target.get_all_states()), _effective_states(self.state))

    @transition(WaveScheduler.get_state)
    def get_state(self, ctx: TransitionContext[WaveScheduler, [Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and len(self.state.nodes) > 0, "graph has nodes"
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_existing_node()))
        ctx.returns(self._returns_get_state)
        ctx.ensures(self._ensure_get_state)
        ctx.update(self._update_sync)

    def _returns_get_state(self, node_id: Any = None) -> Any:
        return _effective_states(self.state).get(node_id)

    def _ensure_get_state(self, res: Any, target: Any, check: Any, node_id: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check.equal(res, _effective_states(self.state).get(node_id))

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self, ctx: TransitionContext[WaveScheduler, [], Any]) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "state initialized"))
        ctx.arguments()
        ctx.returns(self._returns_get_all_states)
        ctx.ensures(self._ensure_get_all_states)
        ctx.update(self._update_sync)

    def _returns_get_all_states(self) -> Any:
        return dict(_effective_states(self.state))

    def _ensure_get_all_states(self, res: Any, target: Any, check: Any) -> None:
        if _is_error_outcome(res):
            return
        check.equal(dict(res), _effective_states(self.state))

    # ------------------------------------------------------------------
    # DAGRunner transitions
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, ctx: TransitionContext[DAGRunner, [Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized
                and len(self.state.nodes) > 0
                and _missing_dependency(self.state) is None
                and _topological_order(self.state) is not None
                and all(
                    state is NodeState.READY or state is NodeState.PENDING
                    for state in _effective_states(self.state).values()
                ),
                "runner requires a fresh, valid, unstarted graph",
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_run()))
        ctx.returns(self._returns_run)
        ctx.ensures(self._ensure_run)
        ctx.update(self._update_run)

    @transition(DAGRunner.run)
    def run_missing_dependency(self, ctx: TransitionContext[DAGRunner, [Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized and _missing_dependency(self.state) is not None,
                "graph references a missing dependency",
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_run()))
        ctx.raises(DAGError, match=".*")

    @transition(DAGRunner.run)
    def run_cycle(self, ctx: TransitionContext[DAGRunner, [Any], Any]) -> None:
        ctx.requires(
            lambda check: check(
                self.state.initialized
                and _missing_dependency(self.state) is None
                and _topological_order(self.state) is None,
                "graph contains a dependency cycle",
            )
        )
        ctx.arguments(arg_0=Domain(strategy=lambda: self._generate_run()))
        ctx.raises(DAGError, match=".*")

    def _returns_run(self, failure_policy: Any = None) -> Any:
        return _model_run_report(self.state, failure_policy)

    def _ensure_run(self, res: Any, target: Any, check: Any, failure_policy: Any = None) -> None:
        if _is_error_outcome(res):
            return
        check(isinstance(res, DAGRunReport), "run yields a consolidated report")
        node_ids = set(res.results)
        check.equal(res.total_nodes, len(node_ids))
        check(res.wall_clock_seconds >= 0.0, "non-negative wall clock duration")
        for node_id, result in res.results.items():
            check.equal(result.node_id, node_id)
            check(result.state in _TERMINAL, "node reached a terminal state")
            check(result.duration_seconds >= 0.0, "non-negative node duration")
            check(result.retries_attempted >= 0, "non-negative retries")
        check.equal(
            set(res.succeeded_nodes),
            {node_id for node_id, result in res.results.items() if result.state is NodeState.SUCCEEDED},
        )
        check.equal(
            set(res.failed_nodes),
            {node_id for node_id, result in res.results.items() if result.state is NodeState.FAILED},
        )
        check.equal(
            set(res.skipped_nodes),
            {node_id for node_id, result in res.results.items() if result.state is NodeState.SKIPPED},
        )
        check.equal(
            set(res.cancelled_nodes),
            {node_id for node_id, result in res.results.items() if result.state is NodeState.CANCELLED},
        )
        policy = failure_policy if isinstance(failure_policy, FailurePolicy) else FailurePolicy.FAIL_FAST
        if res.failed_nodes and policy is FailurePolicy.FAIL_FAST:
            remaining = node_ids - set(res.succeeded_nodes) - set(res.failed_nodes) - set(res.skipped_nodes)
            check.equal(set(res.cancelled_nodes), remaining)
        path = list(res.critical_path)
        check(set(path) <= node_ids, "critical path references reported nodes")
        check(len(set(path)) == len(path), "critical path has no repeated nodes")

    def _update_run(self, res: Any, failure_policy: Any = None) -> None:
        _apply_run(self.state, res)

    # ------------------------------------------------------------------
    # Shared handlers
    # ------------------------------------------------------------------

    def _update_noop(self, res: Any) -> None:
        return None

    def _update_sync(self, res: Any) -> None:
        _sync_states(self.state)


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    machine = DagEngineLiteStateMachine(state or DagEngineLiteState())
    return (
        machine.as_fake(DAG),
        machine.as_fake(WaveScheduler),
        machine.as_fake(DAGRunner),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestDagEngineLiteUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to state machine specification."""

    def setUp(self) -> None:
        self.state = DagEngineLiteState()
        self.dag, self.scheduler, self.runner = make_dag_engine_lite_fakes(self.state)

    def _add(
        self,
        node_id: str,
        dependencies: Optional[list[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        self.dag.add_node(node_id, _benign_action, list(dependencies or []), priority, retries)

    def test_fake_add_node_registers_definition(self) -> None:
        self._add("a", priority=2, retries=1)
        self.assertTrue(self.dag.has_node("a"))
        definition = self.dag.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertEqual(definition.priority, 2)
        self.assertEqual(definition.retries, 1)
        self.assertEqual(definition.dependencies, frozenset())
        self.assertEqual(self.dag.all_nodes(), {"a"})
        self.assertEqual(self.dag.get_dependencies("a"), set())
        self.assertEqual(self.dag.get_dependents("a"), set())

    def test_fake_add_node_with_dependencies(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})

    def test_fake_add_edge_links_existing_nodes(self) -> None:
        self._add("a")
        self._add("b")
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_fake_add_edge_missing_node_raises(self) -> None:
        self._add("a")
        with self.assertRaises(DAGError):
            self.dag.add_edge("a", "ghost")

    def test_fake_remove_node_purges_edges(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.dag.remove_node("b")
        self.assertFalse(self.dag.has_node("b"))
        self.assertEqual(self.dag.all_nodes(), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), set())
        with self.assertRaises(DAGError):
            self.dag.remove_node("b")

    def test_fake_missing_node_queries_raise(self) -> None:
        self._add("a")
        with self.assertRaises(DAGError):
            self.dag.get_node("ghost")
        with self.assertRaises(DAGError):
            self.dag.get_dependencies("ghost")
        with self.assertRaises(DAGError):
            self.dag.get_dependents("ghost")

    def test_fake_validate_detects_missing_dependency(self) -> None:
        self._add("b", dependencies=["ghost"])
        with self.assertRaises(DAGError):
            self.dag.validate()

    def test_fake_validate_detects_cycle(self) -> None:
        self._add("a", dependencies=["b"])
        self._add("b", dependencies=["a"])
        with self.assertRaises(DAGError):
            self.dag.validate()
        with self.assertRaises(DAGError):
            self.dag.topological_sort()

    def test_fake_topological_sort_orders_by_priority(self) -> None:
        self._add("low", priority=0)
        self._add("high", priority=5)
        self.assertEqual(self.dag.topological_sort(), ["high", "low"])
        self.dag.validate()

    def test_fake_compute_critical_path(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        path, weight = self.dag.compute_critical_path({"a": 2.0, "b": 3.0})
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 5.0)
        default_path, default_weight = self.dag.compute_critical_path(None)
        self.assertEqual(default_path, ["a", "b"])
        self.assertEqual(default_weight, 2.0)

    def test_fake_scheduler_waves(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"], priority=3)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.RUNNING)
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.scheduler.next_wave(), ["c", "b"])
        self.assertEqual(self.scheduler.get_state("b"), NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())

    def test_fake_scheduler_fail_fast(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c")
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["a"], NodeState.FAILED)
        self.assertEqual(states["b"], NodeState.CANCELLED)
        self.assertEqual(states["c"], NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_fake_scheduler_skip_downstream(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["b"])
        self._add("d")
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["a"], NodeState.FAILED)
        self.assertEqual(states["b"], NodeState.SKIPPED)
        self.assertEqual(states["c"], NodeState.SKIPPED)
        self.assertEqual(states["d"], NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())

    def test_fake_scheduler_continue_on_error(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("d")
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["b"], NodeState.SKIPPED)
        self.assertEqual(states["d"], NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["d"])

    def test_fake_runner_success(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(report.critical_path, ("a", "b"))
        self.assertEqual(report.results["b"].state, NodeState.SUCCEEDED)
        self.assertEqual(self.state.states["a"], NodeState.SUCCEEDED)
        self.assertEqual(self.state.states["b"], NodeState.SUCCEEDED)

    def test_fake_runner_invalid_graph_raises(self) -> None:
        self._add("a", dependencies=["ghost"])
        with self.assertRaises(DAGError):
            self.runner.run()

    def test_fake_remove_node_with_dependents_detaches_edges(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"])
        self.dag.remove_node("a")
        self.assertEqual(self.dag.all_nodes(), {"b", "c"})
        self.assertEqual(self.dag.get_dependencies("b"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())
        self.assertEqual(self.dag.get_dependents("b"), set())
        self.assertEqual(self.dag.get_dependents("c"), set())
        self.assertEqual(self.dag.find_roots(), {"b", "c"})

    def test_fake_topological_sort_missing_dependency_raises(self) -> None:
        self._add("b", dependencies=["ghost"])
        with self.assertRaises(DAGError):
            self.dag.topological_sort()

    def test_fake_compute_critical_path_empty_graph(self) -> None:
        path, weight = self.dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_fake_mark_succeeded_keeps_terminal_dependent(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.scheduler.mark_succeeded("b")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SUCCEEDED)

    def test_fake_mark_failed_continue_promotes_unblocked_pending(self) -> None:
        self._add("a")
        self._add("failing")
        self.scheduler.mark_succeeded("a")
        self._add("dependent", dependencies=["a"])
        self.scheduler.mark_failed("failing", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.scheduler.get_state("dependent"), NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["dependent"])

    def test_fake_scheduler_state_after_remove_node(self) -> None:
        self._add("a")
        self._add("b")
        self.scheduler.get_all_states()
        self.dag.remove_node("a")
        self.assertEqual(set(self.scheduler.get_all_states()), {"b"})

    def test_fake_is_finished_pending_with_mixed_prerequisites(self) -> None:
        self._add("a")
        self._add("b")
        self._add("c", dependencies=["a", "b"])
        self.scheduler.next_wave()
        self.scheduler.mark_succeeded("a")
        self.scheduler.mark_running("b")
        self.assertFalse(self.scheduler.is_finished())

    def test_fake_is_finished_eligible_pending_dependent(self) -> None:
        self._add("prerequisite")
        self.scheduler.mark_succeeded("prerequisite")
        self._add("dependent", dependencies=["prerequisite"])
        self.assertFalse(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.get_state("dependent"), NodeState.PENDING)

    def test_fake_is_finished_blocked_dependents(self) -> None:
        self._add("root")
        self.scheduler.mark_failed("root", FailurePolicy.FAIL_FAST)
        self._add("left", dependencies=["root"])
        self._add("right", dependencies=["root"])
        self.assertTrue(self.scheduler.is_finished())
        self.assertEqual(self.scheduler.get_state("left"), NodeState.PENDING)
        self.assertEqual(self.scheduler.get_state("right"), NodeState.PENDING)


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
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.scheduler, DAGRunner: self.runner}
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _add(
        self,
        node_id: str,
        dependencies: Optional[list[str]] = None,
        priority: int = 0,
        retries: int = 0,
        action: Any = None,
    ) -> None:
        self.sm.dispatch_transition(
            "add_node",
            node_id,
            action or _benign_action,
            list(dependencies or []),
            priority,
            retries,
        )

    def test_add_node_registers_definition(self) -> None:
        self._add("a", priority=2, retries=1)
        self.sm.dispatch_transition("has_node", "a")
        self.sm.dispatch_transition("get_node", "a")
        self.sm.dispatch_transition("all_nodes")

    def test_add_node_with_dependencies(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.sm.dispatch_transition("has_node", "b")
        self.sm.dispatch_transition("get_dependencies", "b")
        self.sm.dispatch_transition("get_dependents", "a")

    def test_add_edge_links_nodes(self) -> None:
        self._add("a")
        self._add("b")
        self.sm.dispatch_transition("add_edge", "a", "b")
        self.sm.dispatch_transition("get_dependencies", "b")
        self.sm.dispatch_transition("get_dependents", "a")

    def test_add_edge_missing_node_raises(self) -> None:
        self._add("a")
        self._add("b")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "ghost")

    def test_add_edge_missing_upstream_raises(self) -> None:
        self._add("a")
        self._add("b")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("ghost", "b")

    def test_remove_node_purges_edges(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.sm.dispatch_transition("remove_node", "b")
        self.sm.dispatch_transition("all_nodes")
        self.sm.dispatch_transition("get_dependents", "a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("b")

    def test_has_node_negative(self) -> None:
        self._add("a")
        self.sm.dispatch_transition("has_node", "ghost")

    def test_missing_node_queries_raise(self) -> None:
        self._add("a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("ghost")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("ghost")

    def test_find_roots_and_leaves(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"])
        self.sm.dispatch_transition("find_roots")
        self.sm.dispatch_transition("find_leaves")
        self.sm.dispatch_transition("all_nodes")

    def test_validate_success(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.sm.dispatch_transition("validate")

    def test_validate_missing_dependency_raises(self) -> None:
        self._add("b", dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_validate_cycle_raises(self) -> None:
        self._add("a", dependencies=["b"])
        self._add("b", dependencies=["a"])
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_topological_sort_orders_by_priority(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"], priority=2)
        self._add("c", priority=1)
        self.sm.dispatch_transition("topological_sort")

    def test_compute_critical_path_default_weights(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["b"])
        self._add("d")
        self.sm.dispatch_transition("compute_critical_path")
        self.sm.dispatch_transition("compute_critical_path", {"a": 1.0, "b": 5.0, "c": 2.0, "d": 0.5})

    def test_scheduler_next_wave_orders_by_priority(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"], priority=5)
        self._add("c", dependencies=["a"], priority=1)
        self._add("d", priority=3)
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_mark_running(self) -> None:
        self._add("a")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "a")
        self.sm.dispatch_transition("get_state", "a")

    def test_scheduler_mark_succeeded_promotes_dependents(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"])
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "a")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self.sm.dispatch_transition("get_state", "a")
        self.sm.dispatch_transition("get_state", "b")
        self.sm.dispatch_transition("get_state", "c")
        self.sm.dispatch_transition("get_all_states")

    def test_scheduler_mark_succeeded_keeps_blocked_dependent_pending(self) -> None:
        self._add("a")
        self._add("b")
        self._add("c", dependencies=["a", "b"])
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self.sm.dispatch_transition("get_state", "c")
        self.sm.dispatch_transition("get_all_states")

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_failed", "a", FailurePolicy.FAIL_FAST)
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("is_finished")

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["b"])
        self._add("d")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_failed", "a", FailurePolicy.SKIP_DOWNSTREAM)
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("get_state", "d")

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("d")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_failed", "a", FailurePolicy.CONTINUE_ON_ERROR)
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_is_finished_empty_graph(self) -> None:
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_is_finished_after_completion(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("mark_succeeded", "b")
        self.sm.dispatch_transition("is_finished")

    def test_runner_success(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", priority=4)
        self.sm.dispatch_transition("run")

    def test_runner_fail_fast(self) -> None:
        self._add("a", action=_failing_action)
        self._add("b", dependencies=["a"])
        self._add("c")
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_skip_downstream(self) -> None:
        self._add("a", action=_failing_action)
        self._add("b", dependencies=["a"])
        self._add("c")
        self.sm.dispatch_transition("run", FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_continue_on_error(self) -> None:
        self._add("a", action=_failing_action)
        self._add("b", dependencies=["a"])
        self._add("c")
        self.sm.dispatch_transition("run", FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_retries(self) -> None:
        self._add("flaky", retries=2, action=_failing_action)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_invalid_graph_missing_dependency_raises(self) -> None:
        self._add("b", dependencies=["ghost"])
        with self.assertRaises(NodeNotFoundError):
            self.runner.run()

    def test_runner_cycle_raises(self) -> None:
        self._add("a", dependencies=["b"])
        self._add("b", dependencies=["a"])
        with self.assertRaises(CycleError):
            self.runner.run()

    def test_remove_node_with_dependents_detaches_edges(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self._add("c", dependencies=["a"])
        self.sm.dispatch_transition("remove_node", "a")
        self.sm.dispatch_transition("all_nodes")
        self.sm.dispatch_transition("get_dependencies", "b")
        self.sm.dispatch_transition("get_dependencies", "c")
        self.sm.dispatch_transition("find_roots")

    def test_topological_sort_missing_dependency_raises(self) -> None:
        self._add("b", dependencies=["ghost"])
        with self.assertRaises(DAGError):
            self.dag.topological_sort()

    def test_compute_critical_path_empty_graph(self) -> None:
        self.sm.dispatch_transition("compute_critical_path")

    def test_mark_succeeded_keeps_terminal_dependent(self) -> None:
        self._add("a")
        self._add("b", dependencies=["a"])
        self.sm.dispatch_transition("mark_succeeded", "b")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self.sm.dispatch_transition("get_state", "b")
        self.sm.dispatch_transition("get_all_states")

    def test_mark_failed_continue_promotes_unblocked_pending(self) -> None:
        self._add("a")
        self._add("failing")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self._add("dependent", dependencies=["a"])
        self.sm.dispatch_transition("mark_failed", "failing", FailurePolicy.CONTINUE_ON_ERROR)
        self.sm.dispatch_transition("get_state", "dependent")
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_state_after_remove_node(self) -> None:
        self._add("a")
        self._add("b")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("remove_node", "a")
        self.sm.dispatch_transition("get_all_states")

    def test_is_finished_pending_with_running_prerequisite(self) -> None:
        self._add("a")
        self._add("b")
        self._add("c", dependencies=["a", "b"])
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self.sm.dispatch_transition("mark_running", "b")
        self.sm.dispatch_transition("is_finished")

    def test_is_finished_eligible_pending_dependent(self) -> None:
        self._add("prerequisite")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_succeeded", "prerequisite")
        self._add("dependent", dependencies=["prerequisite"])
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("get_state", "dependent")

    def test_is_finished_blocked_dependents(self) -> None:
        self._add("root")
        self.sm.dispatch_transition("mark_failed", "root", FailurePolicy.FAIL_FAST)
        self._add("left", dependencies=["root"])
        self._add("right", dependencies=["root"])
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("get_all_states")


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


def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T23:45:14Z
# LAST_CHANGED: 2026-10-28T23:44:36Z
# CHANGE: Added deterministic coverage for the sole remaining completion-check deficit: an eligible-but-pending dependent whose sole prerequisite has already succeeded (with every prerequisite terminal-success and no running node). New fake unit test test_fake_is_finished_eligible_pending_dependent asserts is_finished() is False and the dependent remains PENDING; matching real test test_is_finished_eligible_pending_dependent drives the same scenario through dispatch_transition (add prereq, next_wave, mark_succeeded, add dependent, is_finished, get_state) so ensure handlers verify the not-finished verdict and the PENDING state against the implementation.
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:45:14Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:44:55Z
# --- END CLEANROOM METADATA ---
