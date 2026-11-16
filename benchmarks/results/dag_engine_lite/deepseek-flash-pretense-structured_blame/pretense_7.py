# === File: dag_engine_lite_pretense.py ===
"""Pretense interface and fake state machines for the synchronous DAG engine.

The module defines one stateless interface state machine, one stateful fake state
machine, a synthesized fake class, and a compiled Hypothesis fuzz test case for
each of the three contracted protocols of ``low/dag_engine_lite.pyi``: ``DAG``,
``WaveScheduler``, and ``DAGRunner``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    StateMachine,
    domain,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from dag_engine_lite_deepseek_flash_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGRunReport,
    DAGRunner,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)

# ==============================================================================
# Shared test doubles and finite domain helpers
# ==============================================================================

_TERMINAL_STATES = frozenset(
    {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
)


def _noop_action() -> None:
    """A zero-argument callable standing in for a node action."""


@dataclass
class GraphState:
    """Graph model shared by the stateful fakes of this module."""

    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    dependencies: Dict[str, Set[str]] = field(default_factory=dict)


@dataclass
class DAGState(GraphState):
    """Graph state owned exclusively by DAGFakeStateMachine."""


@dataclass
class WaveSchedulerState(GraphState):
    """Scheduling state owned exclusively by WaveSchedulerFakeStateMachine."""

    states: Dict[str, NodeState] = field(default_factory=dict)


@dataclass
class DAGRunnerState(GraphState):
    """Execution state owned exclusively by DAGRunnerFakeStateMachine."""

    failing: Set[str] = field(default_factory=set)


def _build_graph(
    model: GraphState,
    priorities: Mapping[str, int],
    dependencies: Mapping[str, Sequence[str]],
    retries: Optional[Mapping[str, int]] = None,
) -> None:
    """Deterministically (re)builds the modeled graph with the given shape."""
    model.nodes.clear()
    model.dependencies.clear()
    for node_id, priority in priorities.items():
        upstream = tuple(dependencies.get(node_id, ()))
        retry_count = (retries or {}).get(node_id, 0)
        model.nodes[node_id] = NodeDefinition[Any](
            node_id=node_id,
            action=_noop_action,
            dependencies=frozenset(upstream),
            priority=priority,
            retries=retry_count,
        )
        model.dependencies[node_id] = set(upstream)


def _dag_initial(state: DAGState) -> None:
    """Seeds the canonical DAG graph: a root, a chain, and a priority tie."""
    _build_graph(state, {"a": 0, "b": 2, "c": 1, "d": 1}, {"b": ("a",), "c": ("b",)})


def _scheduler_initial(state: WaveSchedulerState) -> None:
    """Seeds the canonical scheduler graph: a diamond with priority ordering."""
    _build_graph(state, {"a": 0, "b": 3, "c": 2, "d": 1}, {"b": ("a",), "c": ("a",), "d": ("b", "c")})
    state.states.clear()
    state.states.update(_initial_states(state))


def _runner_initial(state: DAGRunnerState) -> None:
    """Seeds the canonical runner graph: one root fails after retries, one succeeds."""
    _build_graph(state, {"a": 2, "b": 1, "c": 0, "d": 0}, {"c": ("a",), "d": ("b",)}, {"b": 2})
    state.failing.clear()
    state.failing.add("b")


def _initial_states(model: GraphState) -> Dict[str, NodeState]:
    """Derives the initial lifecycle states for the modeled graph."""
    return {
        node_id: NodeState.PENDING if model.dependencies.get(node_id) else NodeState.READY
        for node_id in model.nodes
    }


def _priority_order(model: GraphState, remaining: Mapping[str, Set[str]]) -> List[str]:
    """Orders the currently unblocked nodes by priority descending, then identifier ascending."""
    return sorted(
        (node_id for node_id, upstream in remaining.items() if not upstream),
        key=lambda node_id: (-model.nodes[node_id].priority, node_id),
    )


def _topological_order(model: GraphState) -> List[str]:
    """Computes a deterministic Kahn topological order of the modeled graph."""
    remaining: Dict[str, Set[str]] = {
        node_id: {
            upstream for upstream in upstream_ids if upstream in model.nodes
        }
        for node_id, upstream_ids in model.dependencies.items()
    }
    order: List[str] = []
    ready = _priority_order(model, remaining)
    while ready:
        node_id = ready[0]
        order.append(node_id)
        del remaining[node_id]
        for upstream in remaining.values():
            upstream.discard(node_id)
        ready = _priority_order(model, remaining)
    return order


def _ready_wave(model: GraphState, states: Mapping[str, NodeState]) -> List[str]:
    """Resolves the ordered ready wave whose dependencies have all succeeded."""
    return sorted(
        (
            node_id
            for node_id, state in states.items()
            if state == NodeState.READY
            and all(
                states.get(upstream) == NodeState.SUCCEEDED
                for upstream in model.dependencies.get(node_id, set())
            )
        ),
        key=lambda node_id: (-model.nodes[node_id].priority, node_id),
    )


def _dependents(model: GraphState, node_id: str) -> Set[str]:
    """Returns the direct downstream dependents of a node."""
    return {
        other for other, upstream in model.dependencies.items() if node_id in upstream
    }


def _transitive_dependents(model: GraphState, node_id: str) -> Set[str]:
    """Returns every transitive downstream dependent of a node."""
    found: Set[str] = set()
    pending = list(_dependents(model, node_id))
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(_dependents(model, current))
    return found


def _promote_dependents(
    model: GraphState, states: Dict[str, NodeState], node_id: str
) -> None:
    """Promotes newly unblocked dependents from PENDING to READY."""
    for dependent in _dependents(model, node_id):
        if states.get(dependent) == NodeState.PENDING and all(
            states.get(upstream) == NodeState.SUCCEEDED
            for upstream in model.dependencies.get(dependent, set())
        ):
            states[dependent] = NodeState.READY


def _cancel_unfinished(states: Dict[str, NodeState]) -> None:
    """Cancels every non-terminal node in the given state mapping."""
    for node_id, state in states.items():
        if state not in _TERMINAL_STATES:
            states[node_id] = NodeState.CANCELLED


def _skip_dependents(
    model: GraphState, states: Dict[str, NodeState], node_id: str
) -> None:
    """Skips every non-terminal transitive dependent of a failed node."""
    for dependent in _transitive_dependents(model, node_id):
        if states.get(dependent) not in _TERMINAL_STATES:
            states[dependent] = NodeState.SKIPPED


def _critical_path(
    model: GraphState, estimated_durations: Optional[Mapping[str, float]]
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the modeled graph."""
    order = _topological_order(model)
    durations = {
        node_id: float((estimated_durations or {}).get(node_id, 1.0)) for node_id in order
    }
    earliest: Dict[str, float] = {}
    predecessors: Dict[str, Optional[str]] = {}
    for node_id in order:
        best_value = 0.0
        best_predecessor: Optional[str] = None
        for upstream in sorted(model.dependencies.get(node_id, set())):
            if upstream in earliest and earliest[upstream] > best_value:
                best_value = earliest[upstream]
                best_predecessor = upstream
        earliest[node_id] = best_value + durations[node_id]
        predecessors[node_id] = best_predecessor
    if not order:
        return [], 0.0
    terminal = max(order, key=lambda node_id: (earliest[node_id], node_id))
    path: List[str] = []
    cursor: Optional[str] = terminal
    while cursor is not None:
        path.append(cursor)
        cursor = predecessors[cursor]
    path.reverse()
    return path, earliest[terminal]


def _execute_run(model: DAGRunnerState, failure_policy: FailurePolicy) -> DAGRunReport:
    """Simulates a sequential wave execution of the modeled graph."""
    states = _initial_states(model)
    results: Dict[str, NodeResult[Any]] = {}
    wave = _ready_wave(model, states)
    while wave:
        for node_id in wave:
            if states.get(node_id) != NodeState.READY:
                continue
            definition = model.nodes[node_id]
            states[node_id] = NodeState.RUNNING
            if node_id not in model.failing:
                states[node_id] = NodeState.SUCCEEDED
                results[node_id] = NodeResult[Any](
                    node_id=node_id, state=NodeState.SUCCEEDED, value=None
                )
                _promote_dependents(model, states, node_id)
                continue
            states[node_id] = NodeState.FAILED
            results[node_id] = NodeResult[Any](
                node_id=node_id,
                state=NodeState.FAILED,
                error=NodeExecutionError(
                    message="node action failed",
                    node_id=node_id,
                    cause=RuntimeError(node_id),
                ),
                retries_attempted=definition.retries,
            )
            if failure_policy == FailurePolicy.FAIL_FAST:
                _cancel_unfinished(states)
            else:
                _skip_dependents(model, states, node_id)
        wave = _ready_wave(model, states)
    for node_id, state in states.items():
        if node_id not in results and state in _TERMINAL_STATES:
            results[node_id] = NodeResult[Any](node_id=node_id, state=state)
    critical_path, _ = _critical_path(model, None)
    return DAGRunReport(
        total_nodes=len(model.nodes),
        succeeded_nodes=tuple(
            sorted(node_id for node_id, state in states.items() if state == NodeState.SUCCEEDED)
        ),
        failed_nodes=tuple(
            sorted(node_id for node_id, state in states.items() if state == NodeState.FAILED)
        ),
        skipped_nodes=tuple(
            sorted(node_id for node_id, state in states.items() if state == NodeState.SKIPPED)
        ),
        cancelled_nodes=tuple(
            sorted(node_id for node_id, state in states.items() if state == NodeState.CANCELLED)
        ),
        wall_clock_seconds=0.0,
        critical_path=tuple(critical_path),
        results=results,
    )


def _node_ids(sm: DAGStateMachine) -> Sequence[str]:
    """Finite node identifier candidates for the DAG contract."""
    return ["f", "g", "h", "a", "b", "c", "d", "e"] + sorted(sm.inner_all_nodes() or set())


def _existing_node_ids(sm: DAGStateMachine) -> Sequence[str]:
    """Finite candidates for node identifiers that are currently registered."""
    return sorted(sm.inner_all_nodes() or set()) or ["a"]


def _fresh_node_ids(sm: DAGStateMachine) -> Sequence[str]:
    """Finite candidates for node identifiers that are currently unregistered."""
    registered = sm.inner_all_nodes() or set()
    candidates: List[str] = []
    index = 0
    while len(candidates) < 4:
        candidate = f"n{index}"
        if candidate not in registered:
            candidates.append(candidate)
        index += 1
    return candidates


def _dependency_options(sm: DAGStateMachine) -> Sequence[Optional[Collection[str]]]:
    """Finite dependency collection candidates drawn from the current graph."""
    nodes = sorted(sm.inner_all_nodes() or set())
    options: List[Optional[Collection[str]]] = [None, ()]
    options.extend((node_id,) for node_id in nodes)
    options.extend(
        (first, second) for first in nodes for second in nodes if first < second
    )
    options.append(tuple(nodes))
    return options


def _action_options(sm: DAGStateMachine) -> Sequence[Callable[[], Any]]:
    """Finite node action candidates for the DAG contract."""
    return [_noop_action]


def _duration_options(sm: DAGStateMachine) -> Sequence[Optional[Mapping[str, float]]]:
    """Finite estimated duration mapping candidates drawn from the current graph."""
    nodes = sorted(sm.inner_all_nodes() or set())
    options: List[Optional[Mapping[str, float]]] = [None, {}, {node_id: 1.0 for node_id in nodes}]
    options.append(
        {node_id: float(index + 1) for index, node_id in enumerate(nodes)}
    )
    return options


def _scheduled_node_ids(sm: WaveSchedulerStateMachine) -> Sequence[str]:
    """Finite scheduled node identifier candidates for the scheduler contract."""
    return sorted(sm.inner_get_all_states() or {})


# ==============================================================================
# DAG: stateless interface state machine
# ==============================================================================


class DAGStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the DAG protocol."""

    @domain(
        valid=_node_ids,
        invalid=lambda sm: [0, 3.5, None, ""],
    )
    def node_identifier(self, node_id: str) -> bool:
        return isinstance(node_id, str) and node_id != ""

    @domain(
        valid=_existing_node_ids,
        invalid=lambda sm: _fresh_node_ids(sm),
    )
    def existing_node_id(self, node_id: str) -> bool:
        return isinstance(node_id, str) and node_id != "" and self.inner_has_node(node_id)

    @domain(
        valid=_fresh_node_ids,
        invalid=lambda sm: sorted(sm.inner_all_nodes() or set()) or ["a"],
    )
    def absent_node_id(self, node_id: str) -> bool:
        return isinstance(node_id, str) and node_id != "" and not self.inner_has_node(node_id)

    @domain(
        valid=_dependency_options,
        invalid=lambda sm: [1, "a", 3.5, {"a": 1}],
    )
    def dependency_collection(self, dependencies: Optional[Collection[str]]) -> bool:
        return dependencies is None or (
            isinstance(dependencies, Collection)
            and not isinstance(dependencies, (str, bytes))
            and all(isinstance(dependency, str) for dependency in dependencies)
        )

    @domain(
        valid=_action_options,
        invalid=lambda sm: [0, "action", None],
    )
    def node_action(self, action: Callable[[], Any]) -> bool:
        return callable(action)

    @domain(
        valid=_duration_options,
        invalid=lambda sm: [1, ["a"], {"a": "slow"}],
    )
    def duration_mapping(self, estimated_durations: Optional[Mapping[str, float]]) -> bool:
        return estimated_durations is None or (
            isinstance(estimated_durations, Mapping)
            and all(
                isinstance(key, str) and isinstance(value, (int, float))
                for key, value in estimated_durations.items()
            )
        )

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, self.absent_node_id, error=DuplicateNodeError)
        require_arg(action, self.node_action)
        require_arg(dependencies, self.dependency_collection)
        require_arg(priority, int)
        require_arg(retries, int)
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert ret is None
        assert self.inner_has_node(node_id)
        assert self.inner_get_dependencies(node_id) == set(dependencies or ())
        return ret

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require_arg(upstream_id, self.existing_node_id, error=NodeNotFoundError)
        require_arg(downstream_id, self.existing_node_id, error=NodeNotFoundError)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert ret is None
        assert upstream_id in self.inner_get_dependencies(downstream_id)
        return ret

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require_arg(node_id, self.existing_node_id, error=NodeNotFoundError)
        ret = self.inner_remove_node(node_id)
        assert ret is None
        assert not self.inner_has_node(node_id)
        assert all(
            node_id not in self.inner_get_dependencies(other)
            for other in self.inner_all_nodes()
        )
        return ret

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, self.node_identifier)
        ret = self.inner_has_node(node_id)
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require_arg(node_id, self.existing_node_id, error=NodeNotFoundError)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require_arg(node_id, self.existing_node_id, error=NodeNotFoundError)
        ret = self.inner_get_dependencies(node_id)
        assert isinstance(ret, set)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require_arg(node_id, self.existing_node_id, error=NodeNotFoundError)
        ret = self.inner_get_dependents(node_id)
        assert isinstance(ret, set)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert isinstance(ret, set)
        return ret

    @transition(DAG.all_dependencies_exist)
    def all_dependencies_exist(self) -> bool:
        ret = self.inner_all_dependencies_exist()
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.is_acyclic)
    def is_acyclic(self) -> bool:
        ret = self.inner_is_acyclic()
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.inner_all_dependencies_exist(), error=NodeNotFoundError)
        require(self.inner_is_acyclic(), error=CycleError)
        ret = self.inner_validate()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.inner_all_dependencies_exist(), error=NodeNotFoundError)
        require(self.inner_is_acyclic(), error=CycleError)
        ret = self.inner_topological_sort()
        assert isinstance(ret, list)
        assert len(ret) == len(self.inner_all_nodes())
        assert set(ret) <= self.inner_all_nodes()
        for index, node_id in enumerate(ret):
            assert self.inner_get_dependencies(node_id) <= set(ret[:index])
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        assert isinstance(ret, set)
        assert ret <= self.inner_all_nodes()
        assert all(not self.inner_get_dependencies(node_id) for node_id in ret)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        assert isinstance(ret, set)
        assert ret <= self.inner_all_nodes()
        assert all(not self.inner_get_dependents(node_id) for node_id in ret)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        require(self.inner_all_dependencies_exist(), error=NodeNotFoundError)
        require(self.inner_is_acyclic(), error=CycleError)
        require_arg(estimated_durations, self.duration_mapping)
        ret = self.inner_compute_critical_path(estimated_durations)
        path, weight = ret
        assert isinstance(path, list)
        assert set(path) <= self.inner_all_nodes()
        assert weight >= 0.0
        return ret

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None: ...

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None: ...

    def inner_remove_node(self, node_id: str) -> None: ...

    def inner_has_node(self, node_id: str) -> bool: ...

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]: ...

    def inner_get_dependencies(self, node_id: str) -> Set[str]: ...

    def inner_get_dependents(self, node_id: str) -> Set[str]: ...

    def inner_all_nodes(self) -> Set[str]: ...

    def inner_all_dependencies_exist(self) -> bool: ...

    def inner_is_acyclic(self) -> bool: ...

    def inner_validate(self) -> None: ...

    def inner_topological_sort(self) -> List[str]: ...

    def inner_find_roots(self) -> Set[str]: ...

    def inner_find_leaves(self) -> Set[str]: ...

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]: ...


# ==============================================================================
# DAG: stateful fake state machine and fuzzing
# ==============================================================================


class DAGFakeStateMachine(DAGStateMachine):
    """Stateful in-memory fake for the DAG protocol."""

    def __init__(
        self,
        state: Optional[DAGState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DAGState:
        state = DAGState()
        _dag_initial(state)
        return state

    @transition.seeding()
    def seed_initial(self) -> None:
        _dag_initial(self.state)

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        upstream = frozenset(dependencies or ())
        self.state.nodes[node_id] = NodeDefinition[Any](
            node_id=node_id,
            action=action,
            dependencies=upstream,
            priority=priority,
            retries=retries,
        )
        self.state.dependencies[node_id] = set(upstream)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        self.state.dependencies[downstream_id].add(upstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        del self.state.nodes[node_id]
        del self.state.dependencies[node_id]
        for upstream in self.state.dependencies.values():
            upstream.discard(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return self.state.nodes[node_id]

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.dependencies[node_id])

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return _dependents(self.state, node_id)

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes)

    def inner_all_dependencies_exist(self) -> bool:
        return all(
            dependency in self.state.nodes
            for upstream in self.state.dependencies.values()
            for dependency in upstream
        )

    def inner_is_acyclic(self) -> bool:
        return len(_topological_order(self.state)) == len(self.state.nodes)

    def inner_validate(self) -> None:
        return None

    def inner_topological_sort(self) -> List[str]:
        return _topological_order(self.state)

    def inner_find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id, upstream in self.state.dependencies.items()
            if not upstream
        }

    def inner_find_leaves(self) -> Set[str]:
        return {
            node_id for node_id in self.state.nodes if not _dependents(self.state, node_id)
        }

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        return _critical_path(self.state, estimated_durations)


FakeDAG = synthesize_fake(DAGFakeStateMachine)


def make_dag_fake(state: Optional[DAGState] = None) -> DAG:
    """Builds an in-memory DAG fake from the given (or a fresh) model state."""
    return FakeDAG(
        state=state if state is not None else DAGFakeStateMachine().make_initial_state()
    )


FakeDAGFuzzTest = compile_hypothesis_test_case(
    DAGFakeStateMachine,
    name="FakeDAGFuzzTest",
)


class TestDAGFake(unittest.TestCase):
    """Fixed fake tests covering valid-transition branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.fake = make_dag_fake(DAGState())

    def test_empty_graph(self) -> None:
        self.assertEqual(self.fake.all_nodes(), set())
        self.assertTrue(self.fake.all_dependencies_exist())
        self.assertTrue(self.fake.is_acyclic())
        self.assertFalse(self.fake.has_node("a"))
        self.assertEqual(self.fake.find_roots(), set())
        self.assertEqual(self.fake.find_leaves(), set())
        self.assertEqual(self.fake.topological_sort(), [])
        self.assertEqual(self.fake.compute_critical_path(None), ([], 0.0))
        self.fake.validate()

    def test_graph_lifecycle(self) -> None:
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, ("a",), 2, 1)
        self.fake.add_node("c", _noop_action, ("b",), 1, 0)
        self.assertEqual(self.fake.get_node("b").node_id, "b")
        self.assertEqual(self.fake.get_dependencies("b"), {"a"})
        self.assertEqual(self.fake.get_dependents("a"), {"b"})
        self.assertEqual(self.fake.topological_sort(), ["a", "b", "c"])
        path, weight = self.fake.compute_critical_path({"b": 2.5})
        self.assertEqual(path, ["a", "b", "c"])
        self.assertAlmostEqual(weight, 4.5)
        self.fake.add_edge("c", "a")
        self.assertFalse(self.fake.is_acyclic())
        self.fake.remove_node("c")
        self.assertTrue(self.fake.is_acyclic())
        self.fake.remove_node("a")
        self.assertTrue(self.fake.all_dependencies_exist())
        self.fake.add_node("d", _noop_action, ("missing",), 0, 0)
        self.assertFalse(self.fake.all_dependencies_exist())
        self.assertTrue(self.fake.is_acyclic())
        self.assertEqual(self.fake.find_roots(), {"b"})

    def test_priority_tie_breaking(self) -> None:
        self.fake.add_node("a", _noop_action, None, 0, 0)
        self.fake.add_node("b", _noop_action, None, 5, 0)
        self.fake.add_node("c", _noop_action, None, 5, 0)
        self.assertEqual(self.fake.topological_sort(), ["b", "c", "a"])
        self.assertEqual(self.fake.find_roots(), {"a", "b", "c"})
        self.assertEqual(self.fake.find_leaves(), {"a", "b", "c"})


# ==============================================================================
# WaveScheduler: stateless interface state machine
# ==============================================================================


class WaveSchedulerStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the WaveScheduler protocol."""

    @domain(
        valid=_scheduled_node_ids,
        invalid=lambda sm: sorted(
            {"missing", "unknown"} - set(sm.inner_get_all_states() or {})
        )
        or ["missing"],
    )
    def scheduled_node_id(self, node_id: str) -> bool:
        return (
            isinstance(node_id, str)
            and node_id != ""
            and node_id in (self.inner_get_all_states() or {})
        )

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        before = self.inner_get_all_states()
        ret = self.inner_next_wave()
        assert isinstance(ret, list)
        assert len(ret) == len(set(ret))
        assert all(before.get(node_id) == NodeState.READY for node_id in ret)
        assert self.inner_get_all_states() == before
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require_arg(node_id, self.scheduled_node_id)
        ret = self.inner_mark_running(node_id)
        assert ret is None
        assert self.inner_get_state(node_id) == NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require_arg(node_id, self.scheduled_node_id)
        before = self.inner_get_all_states()
        ret = self.inner_mark_succeeded(node_id)
        assert ret is None
        after = self.inner_get_all_states()
        assert after.get(node_id) == NodeState.SUCCEEDED
        assert all(
            other == node_id
            or after.get(other) == before.get(other)
            or (
                before.get(other) == NodeState.PENDING
                and after.get(other) == NodeState.READY
            )
            for other in after
        )
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require_arg(node_id, self.scheduled_node_id)
        require_arg(failure_policy, FailurePolicy)
        ret = self.inner_mark_failed(node_id, failure_policy)
        assert ret is None
        after = self.inner_get_all_states()
        assert after.get(node_id) == NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            assert all(state in _TERMINAL_STATES for state in after.values())
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require_arg(node_id, self.scheduled_node_id, error=NodeNotFoundError)
        ret = self.inner_get_state(node_id)
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        ret = self.inner_get_all_states()
        assert all(isinstance(state, NodeState) for state in ret.values())
        return ret

    def inner_next_wave(self) -> List[str]: ...

    def inner_mark_running(self, node_id: str) -> None: ...

    def inner_mark_succeeded(self, node_id: str) -> None: ...

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None: ...

    def inner_is_finished(self) -> bool: ...

    def inner_get_state(self, node_id: str) -> NodeState: ...

    def inner_get_all_states(self) -> Mapping[str, NodeState]: ...


# ==============================================================================
# WaveScheduler: stateful fake state machine and fuzzing
# ==============================================================================


class WaveSchedulerFakeStateMachine(WaveSchedulerStateMachine):
    """Stateful in-memory fake for the WaveScheduler protocol."""

    def __init__(
        self,
        state: Optional[WaveSchedulerState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> WaveSchedulerState:
        state = WaveSchedulerState()
        _scheduler_initial(state)
        return state

    @transition.seeding()
    def seed_initial(self) -> None:
        _scheduler_initial(self.state)

    def _sync(self) -> None:
        for node_id, state in _initial_states(self.state).items():
            self.state.states.setdefault(node_id, state)

    def inner_next_wave(self) -> List[str]:
        self._sync()
        return _ready_wave(self.state, self.state.states)

    def inner_mark_running(self, node_id: str) -> None:
        self.state.states[node_id] = NodeState.RUNNING

    def inner_mark_succeeded(self, node_id: str) -> None:
        self.state.states[node_id] = NodeState.SUCCEEDED
        _promote_dependents(self.state, self.state.states, node_id)

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            _cancel_unfinished(self.state.states)
        else:
            _skip_dependents(self.state, self.state.states, node_id)

    def inner_is_finished(self) -> bool:
        self._sync()
        if all(state in _TERMINAL_STATES for state in self.state.states.values()):
            return True
        return len(self.inner_next_wave()) == 0

    def inner_get_state(self, node_id: str) -> NodeState:
        self._sync()
        return self.state.states[node_id]

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        self._sync()
        return dict(self.state.states)


FakeWaveScheduler = synthesize_fake(WaveSchedulerFakeStateMachine)


def make_wave_scheduler_fake(
    state: Optional[WaveSchedulerState] = None,
) -> WaveScheduler:
    """Builds an in-memory WaveScheduler fake from the given (or a fresh) model state."""
    return FakeWaveScheduler(
        state=(
            state
            if state is not None
            else WaveSchedulerFakeStateMachine().make_initial_state()
        )
    )


FakeWaveSchedulerFuzzTest = compile_hypothesis_test_case(
    WaveSchedulerFakeStateMachine,
    name="FakeWaveSchedulerFuzzTest",
)


class TestWaveSchedulerFake(unittest.TestCase):
    """Fixed fake tests covering valid-transition branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.fake = make_wave_scheduler_fake()

    def test_empty_scheduler(self) -> None:
        empty = make_wave_scheduler_fake(WaveSchedulerState())
        self.assertEqual(empty.next_wave(), [])
        self.assertTrue(empty.is_finished())
        self.assertEqual(dict(empty.get_all_states()), {})

    def test_wave_progression(self) -> None:
        self.assertEqual(self.fake.next_wave(), ["a"])
        self.assertFalse(self.fake.is_finished())
        self.fake.mark_running("a")
        self.assertEqual(self.fake.get_state("a"), NodeState.RUNNING)
        self.fake.mark_succeeded("a")
        self.assertEqual(self.fake.next_wave(), ["b", "c"])
        self.fake.mark_running("b")
        self.fake.mark_succeeded("b")
        self.assertEqual(self.fake.get_state("d"), NodeState.PENDING)
        self.fake.mark_running("c")
        self.fake.mark_succeeded("c")
        self.assertEqual(self.fake.get_state("d"), NodeState.READY)
        self.fake.mark_running("d")
        self.fake.mark_succeeded("d")
        self.assertTrue(self.fake.is_finished())

    def test_skip_downstream_policy(self) -> None:
        self.fake.mark_failed("b", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.fake.get_state("b"), NodeState.FAILED)
        self.assertEqual(self.fake.get_state("d"), NodeState.SKIPPED)
        self.assertEqual(self.fake.get_state("a"), NodeState.READY)
        self.assertFalse(self.fake.is_finished())

    def test_fail_fast_policy(self) -> None:
        self.fake.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.fake.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.fake.get_state("b"), NodeState.CANCELLED)
        self.assertEqual(self.fake.get_state("d"), NodeState.CANCELLED)
        self.assertTrue(self.fake.is_finished())

    def test_continue_on_error_policy(self) -> None:
        self.fake.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.fake.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.fake.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.fake.get_state("d"), NodeState.SKIPPED)
        self.assertTrue(self.fake.is_finished())


# ==============================================================================
# DAGRunner: stateless interface state machine
# ==============================================================================


class DAGRunnerStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the DAGRunner protocol."""

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.inner_all_dependencies_exist(), error=NodeNotFoundError)
        require(self.inner_is_acyclic(), error=CycleError)
        require_arg(failure_policy, FailurePolicy)
        ret = self.inner_run(failure_policy)
        assert ret.total_nodes >= 0
        assert (
            len(ret.succeeded_nodes)
            + len(ret.failed_nodes)
            + len(ret.skipped_nodes)
            + len(ret.cancelled_nodes)
            <= ret.total_nodes
        )
        assert ret.wall_clock_seconds >= 0.0
        assert isinstance(ret.critical_path, tuple)
        assert all(
            result.state in _TERMINAL_STATES for result in ret.results.values()
        )
        return ret

    def inner_all_dependencies_exist(self) -> bool: ...

    def inner_is_acyclic(self) -> bool: ...

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport: ...


# ==============================================================================
# DAGRunner: stateful fake state machine and fuzzing
# ==============================================================================


class DAGRunnerFakeStateMachine(DAGRunnerStateMachine):
    """Stateful in-memory fake for the DAGRunner protocol."""

    def __init__(
        self,
        state: Optional[DAGRunnerState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DAGRunnerState:
        state = DAGRunnerState()
        _runner_initial(state)
        return state

    @transition.seeding()
    def seed_initial(self) -> None:
        _runner_initial(self.state)

    def inner_all_dependencies_exist(self) -> bool:
        return all(
            dependency in self.state.nodes
            for upstream in self.state.dependencies.values()
            for dependency in upstream
        )

    def inner_is_acyclic(self) -> bool:
        return len(_topological_order(self.state)) == len(self.state.nodes)

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        return _execute_run(self.state, failure_policy)


FakeDAGRunner = synthesize_fake(DAGRunnerFakeStateMachine)


def make_dag_runner_fake(state: Optional[DAGRunnerState] = None) -> DAGRunner:
    """Builds an in-memory DAGRunner fake from the given (or a fresh) model state."""
    return FakeDAGRunner(
        state=state if state is not None else DAGRunnerFakeStateMachine().make_initial_state()
    )


FakeDAGRunnerFuzzTest = compile_hypothesis_test_case(
    DAGRunnerFakeStateMachine,
    name="FakeDAGRunnerFuzzTest",
)


class TestDAGRunnerFake(unittest.TestCase):
    """Fixed fake tests covering valid-transition branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.fake = make_dag_runner_fake()

    def test_empty_run(self) -> None:
        empty = make_dag_runner_fake(DAGRunnerState())
        report = empty.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.critical_path, ())
        self.assertEqual(dict(report.results), {})

    def test_fail_fast_run(self) -> None:
        report = self.fake.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 4)
        self.assertEqual(report.succeeded_nodes, ("a",))
        self.assertEqual(report.failed_nodes, ("b",))
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ("c", "d"))
        self.assertEqual(report.results["b"].retries_attempted, 2)
        self.assertEqual(report.critical_path, ("b", "d"))

    def test_skip_downstream_run(self) -> None:
        report = self.fake.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.succeeded_nodes, ("a", "c"))
        self.assertEqual(report.failed_nodes, ("b",))
        self.assertEqual(report.skipped_nodes, ("d",))
        self.assertEqual(report.cancelled_nodes, ())

    def test_continue_on_error_run(self) -> None:
        report = self.fake.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.succeeded_nodes, ("a", "c"))
        self.assertEqual(report.failed_nodes, ("b",))
        self.assertEqual(report.skipped_nodes, ("d",))
        self.assertEqual(report.cancelled_nodes, ())

    def test_fail_fast_cancels_remaining_wave(self) -> None:
        state = DAGRunnerState()
        _build_graph(state, {"x": 5, "y": 1}, {})
        state.failing.add("x")
        report = make_dag_runner_fake(state).run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("x",))
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ("y",))
        self.assertEqual(report.succeeded_nodes, ())

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T18:58:45Z
# LAST_CHANGED: 2026-11-15T18:58:45Z
# CHANGE: Make precondition-domain invalid candidates semantically appropriate instead of type-invalid: absent_node_id (duplicate-node gate, DuplicateNodeError) now reports currently registered node ids as invalid candidates, existing_node_id (missing-node gate, NodeNotFoundError) reports guaranteed-unregistered ids, and the scheduler scheduled_node_id domain reports unregistered scheduled ids. Type-invalid candidates remain only on the plain node_identifier type domain.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl_pretense.py ===
"""Implementation pretense module for the synchronous DAG execution engine.

This module binds the concrete ``dag_engine_lite_impl`` singletons (``DAG``,
``WaveScheduler``, and ``DAGRunner``) to the stateless interface state machines
declared in ``pretense_intf/dag_engine_lite_pretense.py``.  The implementation
state machine supplies only the concrete ``inner_*`` bindings (resolving each
singleton through :func:`pretense.sut`) plus the real-SUT fuzz test and fixed
conformance scenarios.
"""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from dag_engine_lite_deepseek_flash_2.parts.dag_engine_lite.lib import dag_engine_lite
from dag_engine_lite_deepseek_flash_2.parts.dag_engine_lite.lib import dag_engine_lite_impl
from dag_engine_lite_deepseek_flash_2.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGRunnerStateMachine,
    DAGStateMachine,
    WaveSchedulerStateMachine,
)


def _noop_action() -> None:
    """Zero-argument node action used by the fixed conformance scenarios."""


def _failing_action() -> None:
    """Zero-argument node action that always raises, for retry/failure scenarios."""
    raise RuntimeError("node action failed")


# ==============================================================================
# Implementation state machine: concrete SUT bindings
# ==============================================================================


class DAGEngineLiteImplStateMachine(
    DAGStateMachine,
    WaveSchedulerStateMachine,
    DAGRunnerStateMachine,
):
    """Implementation binding for the DAG, WaveScheduler, and DAGRunner singletons.

    The stateless interface state machines own every ``@transition``, ``require``,
    ``require_arg``, and ``@domain`` contract.  This class overrides only the
    ``inner_*`` methods that must dispatch to the registered concrete singletons;
    it never mutates ``self.state``, never calls ``super()``, and never re-declares
    a transition.
    """

    # --- DAG contract --------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        sut(dag_engine_lite.DAG).add_node(
            node_id, action, dependencies, priority, retries
        )

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        sut(dag_engine_lite.DAG).add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        sut(dag_engine_lite.DAG).remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        return sut(dag_engine_lite.DAG).has_node(node_id)

    def inner_get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        return sut(dag_engine_lite.DAG).get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return sut(dag_engine_lite.DAG).get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return sut(dag_engine_lite.DAG).get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        return sut(dag_engine_lite.DAG).all_nodes()

    def inner_all_dependencies_exist(self) -> bool:
        return sut(dag_engine_lite.DAG).all_dependencies_exist()

    def inner_is_acyclic(self) -> bool:
        return sut(dag_engine_lite.DAG).is_acyclic()

    def inner_validate(self) -> None:
        sut(dag_engine_lite.DAG).validate()

    def inner_topological_sort(self) -> List[str]:
        return sut(dag_engine_lite.DAG).topological_sort()

    def inner_find_roots(self) -> Set[str]:
        return sut(dag_engine_lite.DAG).find_roots()

    def inner_find_leaves(self) -> Set[str]:
        return sut(dag_engine_lite.DAG).find_leaves()

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        return sut(dag_engine_lite.DAG).compute_critical_path(estimated_durations)

    # --- WaveScheduler contract ---------------------------------------------

    def inner_next_wave(self) -> List[str]:
        return sut(dag_engine_lite.WaveScheduler).next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        sut(dag_engine_lite.WaveScheduler).mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        sut(dag_engine_lite.WaveScheduler).mark_succeeded(node_id)

    def inner_mark_failed(
        self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy
    ) -> None:
        sut(dag_engine_lite.WaveScheduler).mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        return sut(dag_engine_lite.WaveScheduler).is_finished()

    def inner_get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        return sut(dag_engine_lite.WaveScheduler).get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        return sut(dag_engine_lite.WaveScheduler).get_all_states()

    # --- DAGRunner contract --------------------------------------------------

    def inner_run(
        self, failure_policy: dag_engine_lite.FailurePolicy
    ) -> dag_engine_lite.DAGRunReport:
        return sut(dag_engine_lite.DAGRunner).run(failure_policy)


# ==============================================================================
# Real-SUT SUT factory and compiled fuzz test
# ==============================================================================


def make_sut() -> dict[type[Any], Any]:
    """Registers the concrete DAG engine singletons and enters the system phase.

    Each implementation class is registered under both its concrete key and its
    contracted protocol key so that collaborators resolved through
    ``get_singleton(<Protocol>)`` (e.g. the scheduler's DAG dependency) resolve to
    the same singleton instances as the ones bound to the state machine.
    """
    registry = LifecycleRegistry()
    registry.register_singleton(
        dag_engine_lite_impl.DAG,
        keys=[dag_engine_lite_impl.DAG, dag_engine_lite.DAG],
        tier=system,
    )
    registry.register_singleton(
        dag_engine_lite_impl.WaveScheduler,
        keys=[dag_engine_lite_impl.WaveScheduler, dag_engine_lite.WaveScheduler],
        tier=system,
    )
    registry.register_singleton(
        dag_engine_lite_impl.DAGRunner,
        keys=[dag_engine_lite_impl.DAGRunner, dag_engine_lite.DAGRunner],
        tier=system,
    )
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        dag_engine_lite.DAG: get_singleton(dag_engine_lite.DAG),
        dag_engine_lite.WaveScheduler: get_singleton(dag_engine_lite.WaveScheduler),
        dag_engine_lite.DAGRunner: get_singleton(dag_engine_lite.DAGRunner),
    }


DAGEngineLiteImplFuzzTest = compile_hypothesis_test_case(
    DAGEngineLiteImplStateMachine,
    sut_factory=make_sut,
    name="DAGEngineLiteImplFuzzTest",
)


# ==============================================================================
# Fixed real-SUT conformance scenarios
# ==============================================================================


class TestDAGEngineLiteImplReal(LifecycleTestCase):
    """Fixed scenarios covering contracted branches that fuzzing cannot reach."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        dag = self.get_singleton(dag_engine_lite_impl.DAG)
        scheduler = self.get_singleton(dag_engine_lite_impl.WaveScheduler)
        runner = self.get_singleton(dag_engine_lite_impl.DAGRunner)
        self.sm = DAGEngineLiteImplStateMachine(
            singletons={
                dag_engine_lite.DAG: dag,
                dag_engine_lite.WaveScheduler: scheduler,
                dag_engine_lite.DAGRunner: runner,
            }
        )
        self.dag = self.sm.as_checked(dag_engine_lite.DAG, dag)
        self.scheduler = self.sm.as_checked(dag_engine_lite.WaveScheduler, scheduler)
        self.runner = self.sm.as_checked(dag_engine_lite.DAGRunner, runner)

    def test_dag_graph_scenario(self) -> None:
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 2, 1)
        self.dag.add_node("c", _noop_action, ("b",), 1, 0)
        self.assertEqual(self.dag.all_nodes(), {"a", "b", "c"})
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})
        self.assertEqual(self.dag.find_roots(), {"a"})
        self.assertEqual(self.dag.find_leaves(), {"c"})
        self.assertEqual(self.dag.topological_sort(), ["a", "b", "c"])
        path, weight = self.dag.compute_critical_path({"b": 2.5})
        self.assertEqual(path, ["a", "b", "c"])
        self.assertAlmostEqual(weight, 4.5)
        self.dag.validate()
        self.dag.add_edge("c", "a")
        self.assertFalse(self.dag.is_acyclic())
        self.dag.remove_node("c")
        self.assertTrue(self.dag.is_acyclic())
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})

    def test_duplicate_node_violation(self) -> None:
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.violating(dag_engine_lite.DuplicateNodeError).add_node(
            "a", _noop_action, None, 0, 0
        )

    def test_missing_dependency_violation(self) -> None:
        self.dag.add_node("a", _noop_action, ("missing",), 0, 0)
        self.dag.violating(dag_engine_lite.NodeNotFoundError).validate()

    def test_cycle_violation(self) -> None:
        self.dag.add_node("a", _noop_action, ("b",), 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.dag.violating(dag_engine_lite.CycleError).topological_sort()

    def test_scheduler_wave_scenario(self) -> None:
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 2, 0)
        self.dag.add_node("c", _noop_action, ("a",), 1, 0)
        self.assertEqual(self.scheduler.next_wave(), ["a"])
        self.assertFalse(self.scheduler.is_finished())
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.next_wave(), ["b", "c"])
        self.scheduler.mark_running("b")
        self.scheduler.mark_succeeded("b")
        self.assertEqual(self.scheduler.get_state("c"), dag_engine_lite.NodeState.READY)
        self.scheduler.mark_running("c")
        self.scheduler.mark_succeeded("c")
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_skip_downstream_policy(self) -> None:
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_fail_fast_policy(self) -> None:
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(
            self.scheduler.get_state("b"), dag_engine_lite.NodeState.CANCELLED
        )
        self.assertTrue(self.scheduler.is_finished())

    def test_runner_report_scenario(self) -> None:
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        report = self.runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.critical_path, ("a", "b"))
        self.assertEqual(set(report.results), {"a", "b"})

    def test_validate_acyclic_dead_end_traversal(self) -> None:
        """Covers DFS dead-end completion while validating an acyclic graph."""
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.dag.add_node("c", _noop_action, ("a",), 0, 0)
        self.dag.add_node("d", _noop_action, ("b", "c"), 0, 0)
        self.dag.validate()
        self.assertTrue(self.dag.is_acyclic())
        self.assertEqual(self.dag.topological_sort(), ["a", "b", "c", "d"])

    def test_validate_isolated_node_dead_end(self) -> None:
        """Covers validation of a lone node whose DFS path completes at a dead end."""
        self.dag.add_node("solo", _noop_action, None, 0, 0)
        self.dag.validate()
        self.assertTrue(self.dag.is_acyclic())

    def test_validate_acyclic_component_before_cycle(self) -> None:
        """Covers cycle detection after exploring an acyclic dead-end component."""
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.dag.add_node("x", _noop_action, ("y",), 0, 0)
        self.dag.add_node("y", _noop_action, ("x",), 0, 0)
        self.dag.violating(dag_engine_lite.CycleError).validate()

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Covers the scheduler state purge postcondition on node removal."""
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.assertIn("a", self.scheduler.get_all_states())
        self.dag.remove_node("a")
        self.assertNotIn("a", self.scheduler.get_all_states())

    def test_scheduler_running_node_not_finished(self) -> None:
        """Covers the non-terminal RUNNING branch of is_finished()."""
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.scheduler.mark_running("a")
        self.assertFalse(self.scheduler.is_finished())

    def test_runner_exits_when_no_wave_remains(self) -> None:
        """Covers the runner wave-loop exit when an in-flight node leaves no wave."""
        self.dag.add_node("a", _noop_action, None, 0, 0)
        self.dag.add_node("b", _noop_action, ("a",), 0, 0)
        self.scheduler.mark_running("a")
        report = self.runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 2)

    def test_runner_retry_exhaustion_records_failure(self) -> None:
        """Covers retry exhaustion and failed-node outcome recording."""
        self.dag.add_node("x", _failing_action, None, 0, 1)
        report = self.runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("x",))
        result = report.results["x"]
        self.assertEqual(result.state, dag_engine_lite.NodeState.FAILED)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.retries_attempted, 1)

    def test_runner_fail_fast_cancels_same_wave(self) -> None:
        """Covers fail-fast cancellation of a sibling node within the same wave."""
        self.dag.add_node("x", _failing_action, None, 1, 0)
        self.dag.add_node("y", _noop_action, None, 0, 0)
        report = self.runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("x",))
        self.assertEqual(report.cancelled_nodes, ("y",))
        self.assertEqual(
            report.results["y"].state, dag_engine_lite.NodeState.CANCELLED
        )
        self.assertEqual(set(report.results), {"x", "y"})

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T19:08:29Z
# LAST_CHANGED: 2026-11-15T19:07:47Z
# CHANGE: Address pretense_coverage gaps by adding fixed real-SUT scenarios: (1) acyclic-component-before-cycle validate via violating(CycleError) and (2,3) branching/isolated-node validate runs that complete the DFS cycle search through dead ends; (4) remove_node after scheduler state sync to purge tracked scheduler state; (5) mark_running then is_finished()==False for a non-terminal RUNNING node; (6) mark_running before runner.run so the wave loop exits when next_wave() is empty; (7,8) failing action with retries=1 to exhaust retries and record the FAILED NodeResult with its error; (9,10) FAIL_FAST wave where one failing node cancels a same-wave sibling, asserting CANCELLED terminal outcomes in the consolidated report. Added a _failing_action helper. All static checks pass.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T19:08:29Z
# PRETENSE_QA_AUDIT: 2026-11-15T19:08:03Z
# --- END AUTOFAB METADATA ---
