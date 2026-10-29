"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import Raised
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    FailurePolicy,
    NodeDefinition,
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

_TERMINAL_STATES = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


def _noop() -> None:
    """Zero-argument action used by synthesized fakes and stateful fuzzing."""
    return None


_GENERATED_NODE_IDS = itertools.count()


def _fresh_node_id() -> str:
    """Returns a process-unique node identifier for generated fuzz arguments."""
    return f"n{next(_GENERATED_NODE_IDS)}"


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""

    initialized: bool = True
    definitions: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    dependencies: Dict[str, Set[str]] = field(default_factory=dict)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)


def _sort_key(state: DagEngineLiteState, node_id: str) -> Tuple[int, str]:
    """Ordering key: priority descending, then node_id ascending."""
    return (-state.definitions[node_id].priority, node_id)


def _state_cycle(state: DagEngineLiteState) -> Tuple[str, ...]:
    """Returns a directed cycle from the model graph, or an empty tuple."""
    visiting: Dict[str, int] = {}
    path: List[str] = []

    def visit(node_id: str) -> Optional[Tuple[str, ...]]:
        visiting[node_id] = 1
        path.append(node_id)
        for dependency in state.dependencies.get(node_id, set()):
            mark = visiting.get(dependency)
            if mark == 1:
                return tuple(path[path.index(dependency):])
            if mark is None:
                found = visit(dependency)
                if found is not None:
                    return found
        path.pop()
        visiting[node_id] = 2
        return None

    for node_id in state.definitions:
        if node_id not in visiting:
            cycle = visit(node_id)
            if cycle is not None:
                return cycle
    return ()


def _state_topological_order(state: DagEngineLiteState) -> Optional[List[str]]:
    """Returns a model topological order, or None when the model contains a cycle."""
    in_degree = {node_id: len(state.dependencies[node_id]) for node_id in state.definitions}
    ready = sorted(
        (node_id for node_id, degree in in_degree.items() if degree == 0),
        key=lambda node_id: _sort_key(state, node_id),
    )
    order: List[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for dependent in state.dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
                ready.sort(key=lambda node_id: _sort_key(state, node_id))
    if len(order) != len(state.definitions):
        return None
    return order


def _state_critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Optional[Tuple[List[str], float]]:
    """Returns the model longest weighted path, or None when the model has a cycle."""
    order = _state_topological_order(state)
    if order is None:
        return None
    durations = estimated_durations if estimated_durations is not None else {}
    earliest: Dict[str, float] = {}
    for node_id in order:
        upstream_times = [earliest[dep] for dep in state.dependencies[node_id]]
        best = max(upstream_times) if upstream_times else 0.0
        earliest[node_id] = best + durations.get(node_id, 1.0)
    if not order:
        return ([], 0.0)
    terminal = max(order, key=lambda node_id: (earliest[node_id], node_id))
    path: List[str] = [terminal]
    current = terminal
    while state.dependencies[current]:
        current = max(
            state.dependencies[current],
            key=lambda node_id: (earliest[node_id], node_id),
        )
        path.append(current)
    path.reverse()
    return (path, earliest[terminal])


def _state_transitive_dependents(state: DagEngineLiteState, node_id: str) -> Set[str]:
    """Returns all transitive dependents of a model node."""
    seen: Set[str] = set()
    pending: List[str] = list(state.dependents.get(node_id, set()))
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(state.dependents.get(current, set()))
    return seen


def _state_validate(state: DagEngineLiteState) -> None:
    """Raises the contracted model validation error when the model is invalid."""
    for node_id, definition in state.definitions.items():
        for dependency in definition.dependencies:
            if dependency not in state.definitions:
                raise NodeNotFoundError(
                    f"Node '{node_id}' depends on missing node '{dependency}'",
                    node_id=dependency,
                )
    cycle = _state_cycle(state)
    if cycle:
        raise CycleError(f"Dependency cycle detected: {' -> '.join(cycle)}", cycle=cycle)


def _state_next_wave(state: DagEngineLiteState) -> List[str]:
    """Model resolved next wave."""
    wave = [
        node_id
        for node_id, node_state in state.states.items()
        if node_state is NodeState.READY
        and all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.dependencies[node_id]
        )
    ]
    wave.sort(key=lambda node_id: _sort_key(state, node_id))
    return wave


def _state_is_finished(state: DagEngineLiteState) -> bool:
    """Model terminal-state predicate."""
    if not state.definitions:
        return True
    return all(node_state in _TERMINAL_STATES for node_state in state.states.values())


def _state_run_report(state: DagEngineLiteState) -> DAGRunReport:
    """Synthesizes a model run report from the current model states."""
    results = {
        node_id: NodeResult(node_id=node_id, state=state.states[node_id])
        for node_id in state.definitions
    }

    def _ids(target_state: NodeState) -> Tuple[str, ...]:
        return tuple(
            sorted(
                node_id
                for node_id, result in results.items()
                if result.state is target_state
            )
        )

    path = _state_critical_path(state, None)
    critical_path = path[0] if path is not None else []
    return DAGRunReport(
        total_nodes=len(state.definitions),
        succeeded_nodes=_ids(NodeState.SUCCEEDED),
        failed_nodes=_ids(NodeState.FAILED),
        skipped_nodes=_ids(NodeState.SKIPPED),
        cancelled_nodes=_ids(NodeState.CANCELLED),
        wall_clock_seconds=0.0,
        critical_path=tuple(critical_path),
        results=results,
    )


def _generate_edge_args(state: DagEngineLiteState) -> Tuple[str, str]:
    node_ids = sorted(state.definitions)
    if len(node_ids) >= 2:
        return (node_ids[0], node_ids[-1])
    if node_ids:
        return (node_ids[0], "missing_node")
    return ("missing_node", "missing_node")


def _generate_policy(state: DagEngineLiteState) -> FailurePolicy:
    return (
        FailurePolicy.FAIL_FAST,
        FailurePolicy.CONTINUE_ON_ERROR,
        FailurePolicy.SKIP_DOWNSTREAM,
    )[len(state.definitions) % 3]


def _pick_node_id(state: DagEngineLiteState) -> str:
    return sorted(state.definitions)[0] if state.definitions else "missing_node"


def _fake_add_edge(
    state: DagEngineLiteState, upstream_id: str, downstream_id: str
) -> Any:
    if upstream_id not in state.definitions:
        return Raised(
            NodeNotFoundError(
                f"Node '{upstream_id}' not found in graph", node_id=upstream_id
            )
        )
    if downstream_id not in state.definitions:
        return Raised(
            NodeNotFoundError(
                f"Node '{downstream_id}' not found in graph", node_id=downstream_id
            )
        )
    return None


def _fake_remove_node(state: DagEngineLiteState, node_id: str) -> Any:
    if node_id not in state.definitions:
        return Raised(
            NodeNotFoundError(f"Node '{node_id}' not found in graph", node_id=node_id)
        )
    return None


def _fake_get_node(state: DagEngineLiteState, node_id: str) -> Any:
    if node_id not in state.definitions:
        return Raised(
            NodeNotFoundError(f"Node '{node_id}' not found in graph", node_id=node_id)
        )
    return state.definitions[node_id]


def _fake_get_dependencies(state: DagEngineLiteState, node_id: str) -> Any:
    if node_id not in state.definitions:
        return Raised(
            NodeNotFoundError(f"Node '{node_id}' not found in graph", node_id=node_id)
        )
    return set(state.dependencies[node_id])


def _fake_get_dependents(state: DagEngineLiteState, node_id: str) -> Any:
    if node_id not in state.definitions:
        return Raised(
            NodeNotFoundError(f"Node '{node_id}' not found in graph", node_id=node_id)
        )
    return set(state.dependents[node_id])


def _fake_validate(state: DagEngineLiteState) -> Any:
    try:
        _state_validate(state)
    except (NodeNotFoundError, CycleError) as error:
        return Raised(error)
    return None


def _fake_topological_sort(state: DagEngineLiteState) -> Any:
    order = _state_topological_order(state)
    if order is None:
        cycle = _state_cycle(state)
        return Raised(
            CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}", cycle=cycle
            )
        )
    return order


def _fake_critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Any:
    path = _state_critical_path(state, estimated_durations)
    if path is None:
        cycle = _state_cycle(state)
        return Raised(
            CycleError(
                f"Dependency cycle detected: {' -> '.join(cycle)}", cycle=cycle
            )
        )
    return path


def _fake_run(
    state: DagEngineLiteState, failure_policy: FailurePolicy
) -> Any:
    try:
        _state_validate(state)
    except (NodeNotFoundError, CycleError) as error:
        return Raised(error)
    return _state_run_report(state)


def _update_add_node(
    state: DagEngineLiteState,
    node_id: str,
    action: Callable[[], Any],
    dependencies: Optional[Sequence[str]],
    priority: int,
    retries: int,
) -> None:
    frozen = frozenset(dependencies) if dependencies is not None else frozenset()
    state.definitions[node_id] = NodeDefinition(
        node_id=node_id,
        action=action,
        dependencies=frozen,
        priority=priority,
        retries=retries,
    )
    state.dependencies.setdefault(node_id, set())
    state.dependents.setdefault(node_id, set())
    for dependency in frozen:
        state.dependencies[node_id].add(dependency)
        state.dependents.setdefault(dependency, set()).add(node_id)
    if node_id not in state.states:
        state.states[node_id] = NodeState.READY if not frozen else NodeState.PENDING


def _update_add_edge(
    state: DagEngineLiteState, upstream_id: str, downstream_id: str
) -> None:
    if upstream_id in state.definitions and downstream_id in state.definitions:
        state.dependents[upstream_id].add(downstream_id)
        state.dependencies[downstream_id].add(upstream_id)


def _update_remove_node(state: DagEngineLiteState, node_id: str) -> None:
    if node_id not in state.definitions:
        return
    for dependency in state.dependencies[node_id]:
        state.dependents[dependency].discard(node_id)
    for dependent in state.dependents[node_id]:
        state.dependencies[dependent].discard(node_id)
    del state.definitions[node_id]
    del state.dependencies[node_id]
    del state.dependents[node_id]
    state.states.pop(node_id, None)


def _update_mark_succeeded(state: DagEngineLiteState, node_id: str) -> None:
    if node_id not in state.definitions:
        return
    state.states[node_id] = NodeState.SUCCEEDED
    for dependent in state.dependents[node_id]:
        if state.states.get(dependent) is not NodeState.PENDING:
            continue
        if all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.dependencies[dependent]
        ):
            state.states[dependent] = NodeState.READY


def _update_mark_failed(
    state: DagEngineLiteState, node_id: str, failure_policy: FailurePolicy
) -> None:
    if node_id not in state.definitions:
        return
    state.states[node_id] = NodeState.FAILED
    if failure_policy is FailurePolicy.FAIL_FAST:
        for other_id, node_state in state.states.items():
            if node_state not in _TERMINAL_STATES:
                state.states[other_id] = NodeState.CANCELLED
    else:
        for dependent in _state_transitive_dependents(state, node_id):
            if state.states.get(dependent) not in _TERMINAL_STATES:
                state.states[dependent] = NodeState.SKIPPED


def _update_run(state: DagEngineLiteState, report: DAGRunReport) -> None:
    state.results = dict(report.results)
    for node_id, result in report.results.items():
        state.states[node_id] = result.state


def _ensure_add_node(
    target: DAG,
    check: Any,
    node_id: str,
    dependencies: Optional[Sequence[str]],
) -> None:
    expected = set(dependencies) if dependencies is not None else set()
    check(target.has_node(node_id), "add_node must register the node definition")
    check.equal(target.get_dependencies(node_id), expected)


def _ensure_add_edge(
    target: DAG, check: Any, upstream_id: str, downstream_id: str
) -> None:
    check(
        upstream_id in target.get_dependencies(downstream_id),
        "add_edge must record the upstream dependency",
    )
    check(
        downstream_id in target.get_dependents(upstream_id),
        "add_edge must record the downstream dependent",
    )


def _ensure_remove_node(target: DAG, check: Any, node_id: str) -> None:
    check(not target.has_node(node_id), "remove_node must delete the node")
    for other_id in target.all_nodes():
        check(
            node_id not in target.get_dependencies(other_id),
            "remove_node must purge incident upstream edges",
        )
        check(
            node_id not in target.get_dependents(other_id),
            "remove_node must purge incident downstream edges",
        )


def _ensure_get_node(
    target: DAG, check: Any, node_id: str, res: NodeDefinition[Any]
) -> None:
    check(res.node_id == node_id, "get_node must return the matching definition")
    check(node_id in target.all_nodes(), "get_node must return a registered node")


def _ensure_get_dependencies(
    target: DAG, check: Any, node_id: str, res: Set[str]
) -> None:
    for dependency in res:
        if target.has_node(dependency):
            check(
                node_id in target.get_dependents(dependency),
                "get_dependencies must mirror the downstream adjacency",
            )


def _ensure_get_dependents(
    target: DAG, check: Any, node_id: str, res: Set[str]
) -> None:
    for dependent in res:
        if target.has_node(dependent):
            check(
                node_id in target.get_dependencies(dependent),
                "get_dependents must mirror the upstream adjacency",
            )


def _ensure_topological_order(target: DAG, check: Any, res: List[str]) -> None:
    nodes = target.all_nodes()
    check.equal(set(res), nodes)
    check.equal(len(res), len(set(res)))
    position = {node_id: index for index, node_id in enumerate(res)}
    for node_id in res:
        for dependency in target.get_dependencies(node_id):
            check(
                position[dependency] < position[node_id],
                "topological_sort must place prerequisites before dependents",
            )


def _ensure_critical_path(
    target: DAG,
    check: Any,
    res: Tuple[List[str], float],
    estimated_durations: Optional[Mapping[str, float]],
) -> None:
    path, weight = res
    nodes = target.all_nodes()
    if not nodes:
        check.equal(path, [])
        check.equal(weight, 0.0)
        return
    check(len(path) > 0, "critical path must contain at least one node")
    check(
        all(node_id in nodes for node_id in path),
        "critical path nodes must be registered",
    )
    durations = estimated_durations if estimated_durations is not None else {}
    for index in range(1, len(path)):
        check(
            path[index - 1] in target.get_dependencies(path[index]),
            "critical path must follow dependency edges",
        )
    total = sum(durations.get(node_id, 1.0) for node_id in path)
    check.equal(weight, total)


def _ensure_next_wave(target: WaveScheduler, check: Any, res: List[str]) -> None:
    states = target.get_all_states()
    for node_id in res:
        check(node_id in states, "next_wave must return registered nodes")
        check(
            states[node_id] is NodeState.READY,
            "next_wave must return only READY nodes",
        )
    check.equal(len(res), len(set(res)))


def _ensure_mark_succeeded(target: WaveScheduler, check: Any, node_id: str) -> None:
    check(
        target.get_state(node_id) is NodeState.SUCCEEDED,
        "mark_succeeded must transition the node to SUCCEEDED",
    )


def _ensure_mark_failed(
    target: WaveScheduler,
    check: Any,
    node_id: str,
    failure_policy: FailurePolicy,
) -> None:
    states = target.get_all_states()
    check(
        states[node_id] is NodeState.FAILED,
        "mark_failed must transition the node to FAILED",
    )
    if failure_policy is FailurePolicy.FAIL_FAST:
        check(
            all(
                state in _TERMINAL_STATES
                for other_id, state in states.items()
                if other_id != node_id
            ),
            "FAIL_FAST must cancel all remaining non-terminal nodes",
        )


def _ensure_run_report(check: Any, res: DAGRunReport) -> None:
    check.equal(res.total_nodes, len(res.results))
    all_ids = set(res.results)
    for node_id, result in res.results.items():
        check.equal(result.node_id, node_id)
        check(result.duration_seconds >= 0.0, "execution durations must be non-negative")
    for group in (
        res.succeeded_nodes,
        res.failed_nodes,
        res.skipped_nodes,
        res.cancelled_nodes,
    ):
        check.equal(len(group), len(set(group)))
        check(
            all(node_id in all_ids for node_id in group),
            "report identifiers must reference recorded results",
        )
    for node_id in res.succeeded_nodes:
        check(
            res.results[node_id].state is NodeState.SUCCEEDED,
            "succeeded_nodes must match SUCCEEDED results",
        )
    for node_id in res.failed_nodes:
        check(
            res.results[node_id].state is NodeState.FAILED,
            "failed_nodes must match FAILED results",
        )
    for node_id in res.skipped_nodes:
        check(
            res.results[node_id].state is NodeState.SKIPPED,
            "skipped_nodes must match SKIPPED results",
        )
    for node_id in res.cancelled_nodes:
        check(
            res.results[node_id].state is NodeState.CANCELLED,
            "cancelled_nodes must match CANCELLED results",
        )
    check(
        all(node_id in all_ids for node_id in res.critical_path),
        "critical path must reference recorded results",
    )
    check(res.wall_clock_seconds >= 0.0, "wall clock duration must be non-negative")


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    # ------------------------------------------------------------------
    # DAG transitions
    # ------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        ctx: TransitionContext[DAG, [str, Any, Any, int, int], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: _fresh_node_id()),
                    action=Domain(strategy=lambda: _noop),
                    dependencies=Domain(strategy=lambda: ()),
                    priority=Domain(strategy=lambda: 0),
                    retries=Domain(strategy=lambda: 0),
                )
        ctx.returns(lambda node_id, action, dependencies=None, priority=0, retries=0: None)
        ctx.ensures(
            lambda res, target, check, node_id, action, dependencies=None, priority=0, retries=0: _ensure_add_node(
                target, check, node_id, dependencies
            )
        )
        ctx.update(
            lambda res, node_id, action, dependencies=None, priority=0, retries=0: _update_add_node(
                self.state, node_id, action, dependencies, priority, retries
            )
        )

    @transition(DAG.add_edge)
    def add_edge(
        self,
        ctx: TransitionContext[DAG, [str, str], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(upstream_id=Domain(strategy=lambda: _generate_edge_args(self.state)))
        ctx.returns(
            lambda upstream_id, downstream_id: _fake_add_edge(
                self.state, upstream_id, downstream_id
            )
        )
        ctx.ensures(
            lambda res, target, check, upstream_id, downstream_id: _ensure_add_edge(
                target, check, upstream_id, downstream_id
            )
        )
        ctx.update(
            lambda res, upstream_id, downstream_id: _update_add_edge(
                self.state, upstream_id, downstream_id
            )
        )

    @transition(DAG.remove_node)
    def remove_node(
        self,
        ctx: TransitionContext[DAG, [str], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: _fake_remove_node(self.state, node_id))
        ctx.ensures(
            lambda res, target, check, node_id: _ensure_remove_node(target, check, node_id)
        )
        ctx.update(lambda res, node_id: _update_remove_node(self.state, node_id))

    @transition(DAG.has_node)
    def has_node(
        self,
        ctx: TransitionContext[DAG, [str], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: node_id in self.state.definitions)
        ctx.ensures(
            lambda res, target, check, node_id: check.equal(
                res, node_id in target.all_nodes()
            )
        )
        ctx.update(lambda res, node_id: None)

    @transition(DAG.get_node)
    def get_node(
        self,
        ctx: TransitionContext[DAG, [str], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: _fake_get_node(self.state, node_id))
        ctx.ensures(
            lambda res, target, check, node_id: _ensure_get_node(target, check, node_id, res)
        )
        ctx.update(lambda res, node_id: None)

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        ctx: TransitionContext[DAG, [str], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: _fake_get_dependencies(self.state, node_id))
        ctx.ensures(
            lambda res, target, check, node_id: _ensure_get_dependencies(
                target, check, node_id, res
            )
        )
        ctx.update(lambda res, node_id: None)

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        ctx: TransitionContext[DAG, [str], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: _fake_get_dependents(self.state, node_id))
        ctx.ensures(
            lambda res, target, check, node_id: _ensure_get_dependents(
                target, check, node_id, res
            )
        )
        ctx.update(lambda res, node_id: None)

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
        ctx: TransitionContext[DAG, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: set(self.state.definitions))
        ctx.ensures(
            lambda res, target, check: check(
                all(target.has_node(node_id) for node_id in res),
                "all_nodes must report only registered nodes",
            )
        )
        ctx.update(lambda res: None)

    @transition(DAG.validate)
    def validate(
        self,
        ctx: TransitionContext[DAG, [], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: _fake_validate(self.state))
        ctx.ensures(
            lambda res, target, check: check.equal(
                len(target.topological_sort()), len(target.all_nodes())
            )
        )
        ctx.update(lambda res: None)

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
        ctx: TransitionContext[DAG, [], List[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: _fake_topological_sort(self.state))
        ctx.ensures(
            lambda res, target, check: _ensure_topological_order(target, check, res)
        )
        ctx.update(lambda res: None)

    @transition(DAG.find_roots)
    def find_roots(
        self,
        ctx: TransitionContext[DAG, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(
            lambda: {
                node_id
                for node_id in self.state.definitions
                if not self.state.dependencies[node_id]
            }
        )
        ctx.ensures(
            lambda res, target, check: check.equal(
                res,
                {
                    node_id
                    for node_id in target.all_nodes()
                    if not target.get_dependencies(node_id)
                },
            )
        )
        ctx.update(lambda res: None)

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
        ctx: TransitionContext[DAG, [], Set[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(
            lambda: {
                node_id
                for node_id in self.state.definitions
                if not self.state.dependents[node_id]
            }
        )
        ctx.ensures(
            lambda res, target, check: check.equal(
                res,
                {
                    node_id
                    for node_id in target.all_nodes()
                    if not target.get_dependents(node_id)
                },
            )
        )
        ctx.update(lambda res: None)

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        ctx: TransitionContext[DAG, [Any], Any],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(estimated_durations=Domain(strategy=lambda: None))
        ctx.returns(
            lambda estimated_durations=None: _fake_critical_path(
                self.state, estimated_durations
            )
        )
        ctx.ensures(
            lambda res, target, check, estimated_durations=None: _ensure_critical_path(
                target, check, res, estimated_durations
            )
        )
        ctx.update(lambda res, estimated_durations=None: None)

    # ------------------------------------------------------------------
    # WaveScheduler transitions
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
        ctx: TransitionContext[WaveScheduler, [], List[str]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: _state_next_wave(self.state))
        ctx.ensures(lambda res, target, check: _ensure_next_wave(target, check, res))
        ctx.update(lambda res: None)

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        ctx: TransitionContext[WaveScheduler, [str], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized and bool(self.state.definitions), "Engine must have registered nodes"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: None)
        ctx.ensures(
            lambda res, target, check, node_id: check(
                target.get_state(node_id) is NodeState.RUNNING,
                "mark_running must transition the node to RUNNING",
            )
        )
        ctx.update(
            lambda res, node_id: self.state.states.__setitem__(node_id, NodeState.RUNNING)
        )

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        ctx: TransitionContext[WaveScheduler, [str], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized and bool(self.state.definitions), "Engine must have registered nodes"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: None)
        ctx.ensures(
            lambda res, target, check, node_id: _ensure_mark_succeeded(
                target, check, node_id
            )
        )
        ctx.update(lambda res, node_id: _update_mark_succeeded(self.state, node_id))

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        ctx: TransitionContext[WaveScheduler, [str, FailurePolicy], None],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized and bool(self.state.definitions), "Engine must have registered nodes"))
        ctx.arguments(
                    node_id=Domain(strategy=lambda: _pick_node_id(self.state)),
                    failure_policy=Domain(strategy=lambda: _generate_policy(self.state)),
                )
        ctx.returns(lambda node_id, failure_policy=FailurePolicy.FAIL_FAST: None)
        ctx.ensures(
            lambda res, target, check, node_id, failure_policy=FailurePolicy.FAIL_FAST: _ensure_mark_failed(
                target, check, node_id, failure_policy
            )
        )
        ctx.update(
            lambda res, node_id, failure_policy=FailurePolicy.FAIL_FAST: _update_mark_failed(
                self.state, node_id, failure_policy
            )
        )

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
        ctx: TransitionContext[WaveScheduler, [], bool],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: _state_is_finished(self.state))
        ctx.ensures(
            lambda res, target, check: check.equal(
                res,
                all(
                    state in _TERMINAL_STATES
                    for state in target.get_all_states().values()
                ),
            )
        )
        ctx.update(lambda res: None)

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        ctx: TransitionContext[WaveScheduler, [str], NodeState],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized and bool(self.state.definitions), "Engine must have registered nodes"))
        ctx.arguments(node_id=Domain(strategy=lambda: _pick_node_id(self.state)))
        ctx.returns(lambda node_id: self.state.states.get(node_id, NodeState.PENDING))
        ctx.ensures(
            lambda res, target, check, node_id: check.equal(
                res, target.get_all_states().get(node_id)
            )
        )
        ctx.update(lambda res, node_id: None)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
        ctx: TransitionContext[WaveScheduler, [], Mapping[str, NodeState]],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments()
        ctx.returns(lambda: dict(self.state.states))
        ctx.ensures(
            lambda res, target, check: check(
                all(
                    target.get_state(node_id) is state
                    for node_id, state in res.items()
                ),
                "get_all_states must agree with individual node state queries",
            )
        )
        ctx.update(lambda res: None)

    # ------------------------------------------------------------------
    # DAGRunner transitions
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        ctx: TransitionContext[DAGRunner, [FailurePolicy], DAGRunReport],
    ) -> None:
        ctx.requires(lambda check: check(self.state.initialized, "Engine must be initialized"))
        ctx.arguments(failure_policy=Domain(strategy=lambda: _generate_policy(self.state)))
        ctx.returns(
            lambda failure_policy=FailurePolicy.FAIL_FAST: _fake_run(
                self.state, failure_policy
            )
        )
        ctx.ensures(
            lambda res, target, check, failure_policy=FailurePolicy.FAIL_FAST: _ensure_run_report(
                check, res
            )
        )
        ctx.update(
            lambda res, failure_policy=FailurePolicy.FAIL_FAST: _update_run(self.state, res)
        )


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
    """Verifies that synthesized fakes conform to the state machine specification."""

    def setUp(self) -> None:
        self.state = DagEngineLiteState()
        self.dag, self.wavescheduler, self.dagrunner = make_dag_engine_lite_fakes(
            self.state
        )

    def test_fake_add_node_registers_node(self) -> None:
        self.dag.add_node("a", _noop)
        self.assertTrue(self.dag.has_node("a"))
        self.assertFalse(self.dag.has_node("unknown"))

    def test_fake_add_node_records_dependencies(self) -> None:
        self.dag.add_node("a", _noop, (), 4, 0)
        self.dag.add_node("b", _noop, ("a",), 2, 1)
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"b"})
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})
        self.assertEqual(self.dag.get_node("a").node_id, "a")

    def test_fake_add_edge_missing_nodes_raise(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("unknown", "b")

    def test_fake_get_missing_node_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("unknown")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("unknown")

    def test_fake_remove_node(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, ("a",))
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependencies("b"), set())
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("a")

    def test_fake_validate_detects_missing_dependency(self) -> None:
        self.dag.add_node("b", _noop, ("ghost",))
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_fake_validate_detects_cycle(self) -> None:
        self.dag.add_node("a", _noop, ("b",))
        self.dag.add_node("b", _noop, ("a",))
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_fake_topological_sort_and_critical_path(self) -> None:
        self.dag.add_node("a", _noop, (), 0, 0)
        self.dag.add_node("b", _noop, ("a",), 0, 0)
        self.assertEqual(self.dag.topological_sort(), ["a", "b"])
        path, weight = self.dag.compute_critical_path(None)
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 2.0)

    def test_fake_empty_critical_path(self) -> None:
        path, weight = self.dag.compute_critical_path({})
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_fake_scheduler_lifecycle(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, ("a",))
        self.assertEqual(self.wavescheduler.next_wave(), ["a"])
        self.wavescheduler.mark_running("a")
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.RUNNING)
        self.wavescheduler.mark_succeeded("a")
        self.assertEqual(self.wavescheduler.next_wave(), ["b"])
        self.wavescheduler.mark_succeeded("b")
        self.assertTrue(self.wavescheduler.is_finished())
        self.assertEqual(
            self.wavescheduler.get_all_states(),
            {"a": NodeState.SUCCEEDED, "b": NodeState.SUCCEEDED},
        )

    def test_fake_scheduler_mark_failed_policies(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, ("a",))
        self.dag.add_node("c", _noop)
        self.wavescheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.wavescheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.wavescheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.wavescheduler.get_state("c"), NodeState.READY)
        self.wavescheduler.mark_failed("c", FailurePolicy.FAIL_FAST)
        self.assertTrue(self.wavescheduler.is_finished())

    def test_fake_runner_report(self) -> None:
        self.dag.add_node("a", _noop)
        self.dag.add_node("b", _noop, ("a",))
        report = self.dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.results.keys()), {"a", "b"})
        self.assertEqual(report.skipped_nodes, ())


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================


class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the low-level contracts."""

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
            }
        )

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _add(
        self,
        node_id: str,
        dependencies: Sequence[str] = (),
        priority: int = 0,
        retries: int = 0,
        action: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.sm.dispatch_transition(
            "add_node", node_id, action or _noop, list(dependencies), priority, retries
        )

    def test_add_node_and_graph_queries(self) -> None:
        self._add("a")
        self._add("b", ("a",), 3)
        self.sm.dispatch_transition("has_node", "b")
        self.sm.dispatch_transition("get_node", "a")
        self.sm.dispatch_transition("get_dependencies", "b")
        self.sm.dispatch_transition("get_dependents", "a")
        self.sm.dispatch_transition("all_nodes")
        self.sm.dispatch_transition("find_roots")
        self.sm.dispatch_transition("find_leaves")
        self.sm.dispatch_transition("validate")
        self.sm.dispatch_transition("topological_sort")

    def test_add_node_without_dependencies(self) -> None:
        self.sm.dispatch_transition("add_node", "solo", _noop, None, 0, 0)
        self.sm.dispatch_transition("get_dependencies", "solo")
        self.sm.dispatch_transition("find_roots")
        self.sm.dispatch_transition("find_leaves")

    def test_add_edge_success(self) -> None:
        self._add("a")
        self._add("b")
        self.sm.dispatch_transition("add_edge", "a", "b")
        self.sm.dispatch_transition("get_dependencies", "b")
        self.sm.dispatch_transition("get_dependents", "a")

    def test_add_edge_missing_upstream(self) -> None:
        self._add("b")
        self.sm.dispatch_transition("add_edge", "missing", "b")

    def test_add_edge_missing_downstream(self) -> None:
        self._add("a")
        self.sm.dispatch_transition("add_edge", "a", "missing")

    def test_remove_node_purges_incident_edges(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self._add("c", ("b",))
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("remove_node", "b")
        self.sm.dispatch_transition("get_dependencies", "c")
        self.sm.dispatch_transition("get_dependents", "a")
        self.sm.dispatch_transition("get_all_states")

    def test_remove_missing_node(self) -> None:
        self.sm.dispatch_transition("remove_node", "missing")

    def test_get_missing_node_queries(self) -> None:
        self.sm.dispatch_transition("get_node", "missing")
        self.sm.dispatch_transition("get_dependencies", "missing")
        self.sm.dispatch_transition("get_dependents", "missing")

    def test_validate_missing_dependency(self) -> None:
        self._add("b", ("ghost",))
        self.sm.dispatch_transition("validate")

    def test_validate_cycle(self) -> None:
        self._add("a", ("b",))
        self._add("b", ("a",))
        self.sm.dispatch_transition("validate")
        self.sm.dispatch_transition("topological_sort")

    def test_validate_acyclic_reversed_insertion(self) -> None:
        self._add("a", ("b",))
        self._add("b")
        self.sm.dispatch_transition("validate")
        self.sm.dispatch_transition("topological_sort")

    def test_topological_priority_tiebreak(self) -> None:
        self._add("low", (), 1)
        self._add("high", (), 5)
        self._add("same", (), 5)
        self._add("leaf", ("high", "same", "low"), 9)
        self.sm.dispatch_transition("topological_sort")

    def test_critical_path_weighted_and_default(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self._add("c", ("a",))
        self._add("d", ("b", "c"))
        self.sm.dispatch_transition(
            "compute_critical_path", {"a": 1.0, "b": 5.0, "c": 1.0, "d": 1.0}
        )
        self.sm.dispatch_transition("compute_critical_path", None)
        self.sm.dispatch_transition("compute_critical_path", {})

    def test_critical_path_empty_graph(self) -> None:
        self.sm.dispatch_transition("compute_critical_path", None)

    def test_critical_path_single_node(self) -> None:
        self._add("solo")
        self.sm.dispatch_transition("compute_critical_path", None)

    def test_scheduler_next_wave_order(self) -> None:
        self._add("first", (), 1)
        self._add("second", (), 9)
        self._add("third", (), 9)
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "third")
        self.sm.dispatch_transition("get_state", "third")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_succeeded", "third")
        self.sm.dispatch_transition("mark_running", "second")
        self.sm.dispatch_transition("mark_succeeded", "second")
        self.sm.dispatch_transition("mark_running", "first")
        self.sm.dispatch_transition("mark_succeeded", "first")
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("is_finished")

    def test_scheduler_filters_unmet_dependencies(self) -> None:
        self._add("a")
        self._add("b")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("add_edge", "a", "b")
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_new_node_with_succeeded_dependency(self) -> None:
        self._add("a")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("mark_running", "a")
        self.sm.dispatch_transition("mark_succeeded", "a")
        self._add("b", ("a",))
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_remove_purges_state_tracking(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("remove_node", "a")
        self.sm.dispatch_transition("get_all_states")

    def test_scheduler_mark_succeeded_promotes_dependents(self) -> None:
        self._add("a")
        self._add("b")
        self._add("c", ("a", "b"))
        self.sm.dispatch_transition("mark_succeeded", "a")
        self.sm.dispatch_transition("get_state", "c")
        self.sm.dispatch_transition("mark_succeeded", "b")
        self.sm.dispatch_transition("get_state", "c")
        self.sm.dispatch_transition("mark_succeeded", "b")
        self.sm.dispatch_transition("mark_succeeded", "c")

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self._add("c")
        self.sm.dispatch_transition("mark_running", "c")
        self.sm.dispatch_transition("mark_failed", "a", FailurePolicy.FAIL_FAST)
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("is_finished")

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self._add("c", ("a",))
        self._add("d", ("b", "c"))
        self._add("independent")
        self.sm.dispatch_transition("mark_failed", "a", FailurePolicy.SKIP_DOWNSTREAM)
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("is_finished")

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self._add("independent")
        self.sm.dispatch_transition("mark_failed", "a", FailurePolicy.CONTINUE_ON_ERROR)
        self.sm.dispatch_transition("get_all_states")
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("next_wave")

    def test_scheduler_empty_graph_finished(self) -> None:
        self.sm.dispatch_transition("is_finished")
        self.sm.dispatch_transition("next_wave")
        self.sm.dispatch_transition("get_all_states")

    def test_runner_empty_graph(self) -> None:
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_success(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_retry_recovery(self) -> None:
        attempts = [0]

        def flaky() -> str:
            attempts[0] += 1
            if attempts[0] < 2:
                raise ValueError("transient")
            return "recovered"

        self._add("flaky", (), 0, 2, flaky)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_retry_exhausted_fail_fast(self) -> None:
        def always_fails() -> None:
            raise RuntimeError("boom")

        self._add("first", (), 9, 1, always_fails)
        self._add("second", (), 1)
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_continue_on_error(self) -> None:
        def always_fails() -> None:
            raise RuntimeError("boom")

        self._add("first", (), 9, 0, always_fails)
        self._add("dependent", ("first",), 1)
        self._add("independent", (), 1)
        self.sm.dispatch_transition("run", FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_skip_downstream(self) -> None:
        def always_fails() -> None:
            raise RuntimeError("boom")

        self._add("first", (), 9, 0, always_fails)
        self._add("deep", ("first",), 1)
        self._add("independent", (), 1)
        self.sm.dispatch_transition("run", FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_validate_missing_dependency(self) -> None:
        self._add("b", ("ghost",))
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_validate_cycle(self) -> None:
        self._add("a", ("b",))
        self._add("b", ("a",))
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)

    def test_runner_no_ready_wave(self) -> None:
        self._add("a")
        self._add("b", ("a",))
        self.sm.dispatch_transition("mark_running", "a")
        self.sm.dispatch_transition("run", FailurePolicy.FAIL_FAST)


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
# LAST_CLEANED: 2026-10-28T23:30:42Z
# LAST_CHANGED: 2026-10-28T23:30:42Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 7f32bfb1cb73
# COVERAGE_AUDIT: 2026-10-28T23:30:42Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-28T23:30:42Z
# PRETENSE_QA_AUDIT: 2026-10-28T23:30:42Z
# QA_AUDIT: 2026-10-28T23:30:42Z
# --- END CLEANROOM METADATA ---
