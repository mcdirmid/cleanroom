# === File: dag_engine_lite_pretense.py ===
"""Pretense interface and fake state machines for the synchronous DAG execution engine.

This module separates the stateless behavioral contract (`DAGStateMachine`,
`WaveSchedulerStateMachine`, `DAGRunnerStateMachine`) from the stateful in-memory
fakes (`DAGFakeStateMachine`, `WaveSchedulerFakeStateMachine`,
`DAGRunnerFakeStateMachine`) so independent implementations and cross-tests share
one pure specification.
"""

from __future__ import annotations

import heapq
import unittest
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

from pretense import (
    StateMachine,
    domain,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib import dag_engine_lite as dag_lite

# ==============================================================================
# Shared helpers
# ==============================================================================

_NODE_ID_POOL: Tuple[str, ...] = ("a", "b", "c", "d", "e", "f", "g", "h")

_TERMINAL_STATES: FrozenSet[dag_lite.NodeState] = frozenset(
    {
        dag_lite.NodeState.SUCCEEDED,
        dag_lite.NodeState.FAILED,
        dag_lite.NodeState.SKIPPED,
        dag_lite.NodeState.CANCELLED,
    }
)


def _noop_action() -> Any:
    """Zero-argument action used by seeded fake graphs."""
    return None


def _is_terminal(state: dag_lite.NodeState) -> bool:
    """Reports whether a node state is terminal (no further execution possible)."""
    return state in _TERMINAL_STATES


def _downstream_map(nodes: Collection[str], upstream: Mapping[str, Set[str]]) -> Dict[str, Set[str]]:
    """Derives a downstream adjacency map from an upstream one, restricted to known nodes."""
    node_set = set(nodes)
    downstream: Dict[str, Set[str]] = {node_id: set() for node_id in node_set}
    for node_id in node_set:
        for dependency in set(upstream.get(node_id, set())) & node_set:
            downstream[dependency].add(node_id)
    return downstream


def _topological_order(
    nodes: Collection[str],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    priorities: Mapping[str, int],
) -> List[str]:
    """Computes a deterministic topological order (priority descending, then node id ascending)."""
    node_set = set(nodes)
    in_degree: Dict[str, int] = {
        node_id: len(set(upstream.get(node_id, set())) & node_set) for node_id in node_set
    }
    ready: List[Tuple[int, str]] = [
        (-priorities.get(node_id, 0), node_id) for node_id in node_set if in_degree[node_id] == 0
    ]
    heapq.heapify(ready)
    order: List[str] = []
    while ready:
        _, node_id = heapq.heappop(ready)
        order.append(node_id)
        for dependent in downstream.get(node_id, set()):
            if dependent in in_degree:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(ready, (-priorities.get(dependent, 0), dependent))
    return order


def _graph_is_acyclic(nodes: Collection[str], upstream: Mapping[str, Set[str]]) -> bool:
    """Reports whether the dependency graph induced by known nodes contains no directed cycle."""
    node_set = set(nodes)
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visited:
            return True
        if node_id in visiting:
            return False
        visiting.add(node_id)
        for dependency in set(upstream.get(node_id, set())) & node_set:
            if not visit(dependency):
                return False
        visiting.discard(node_id)
        visited.add(node_id)
        return True

    return all(visit(node_id) for node_id in node_set)


def _dependencies_complete(nodes: Collection[str], upstream: Mapping[str, Set[str]]) -> bool:
    """Reports whether every referenced dependency is itself a registered node."""
    node_set = set(nodes)
    return all(set(upstream.get(node_id, set())) <= node_set for node_id in node_set)


def _critical_path(
    nodes: Collection[str],
    upstream: Mapping[str, Set[str]],
    durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through an acyclic graph."""
    node_set = set(nodes)
    downstream = _downstream_map(node_set, upstream)
    order = _topological_order(node_set, upstream, downstream, {})
    weights = durations or {}
    earliest: Dict[str, float] = {}
    predecessors: Dict[str, Optional[str]] = {}
    for node_id in order:
        best_weight = 0.0
        best_predecessor: Optional[str] = None
        for dependency in upstream.get(node_id, set()):
            if dependency in earliest and earliest[dependency] > best_weight:
                best_weight = earliest[dependency]
                best_predecessor = dependency
        earliest[node_id] = best_weight + float(weights.get(node_id, 1.0))
        predecessors[node_id] = best_predecessor
    if not earliest:
        return [], 0.0
    terminal = max(order, key=lambda node_id: earliest[node_id])
    path: List[str] = []
    current: Optional[str] = terminal
    while current is not None:
        path.append(current)
        current = predecessors[current]
    path.reverse()
    return path, earliest[terminal]


# --- finite candidate producers bound to contract argument domains ---


def _registered_node_ids(machine: Any) -> List[str]:
    return sorted(machine.inner_all_nodes())


def _fresh_node_ids(machine: Any) -> List[str]:
    return [node_id for node_id in _NODE_ID_POOL if not machine.inner_has_node(node_id)]


def _scheduled_node_ids(machine: Any) -> List[str]:
    return sorted(machine.inner_get_all_states())


# ==============================================================================
# PART A: DAG INTERFACE
# ==============================================================================


class DAGStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the `DAG` interface."""

    @domain(valid=_registered_node_ids, invalid=lambda machine: ["zz_absent"])
    def known_node_id(self, node_id: str) -> bool:
        return isinstance(node_id, str) and self.inner_has_node(node_id)

    @domain(valid=_fresh_node_ids, invalid=_registered_node_ids)
    def fresh_node_id(self, node_id: str) -> bool:
        return isinstance(node_id, str) and not self.inner_has_node(node_id)

    @transition(dag_lite.DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, self.fresh_node_id)
        require_arg(action, object)
        require_arg(dependencies, Optional[Collection[str]])
        require_arg(priority, int)
        require_arg(retries, int)
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert ret is None
        assert self.inner_has_node(node_id)

    @transition(dag_lite.DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require_arg(upstream_id, self.known_node_id)
        require_arg(downstream_id, self.known_node_id)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert ret is None
        assert upstream_id in self.inner_get_dependencies(downstream_id)

    @transition(dag_lite.DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require_arg(node_id, self.known_node_id)
        ret = self.inner_remove_node(node_id)
        assert ret is None
        assert not self.inner_has_node(node_id)

    @transition(dag_lite.DAG.has_node)
    def has_node(self, node_id: str) -> Any:
        require_arg(node_id, str)
        ret = self.inner_has_node(node_id)
        assert isinstance(ret, bool)
        return ret

    @transition(dag_lite.DAG.get_node)
    def get_node(self, node_id: str) -> Any:
        require_arg(node_id, self.known_node_id)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    @transition(dag_lite.DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Any:
        require_arg(node_id, self.known_node_id)
        ret = self.inner_get_dependencies(node_id)
        assert isinstance(ret, set)
        return ret

    @transition(dag_lite.DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Any:
        require_arg(node_id, self.known_node_id)
        ret = self.inner_get_dependents(node_id)
        assert isinstance(ret, set)
        return ret

    @transition(dag_lite.DAG.all_nodes)
    def all_nodes(self) -> Any:
        ret = self.inner_all_nodes()
        assert isinstance(ret, set)
        return ret

    @transition(dag_lite.DAG.validate)
    def validate(self) -> None:
        require(self.inner_dependencies_complete())
        require(self.inner_graph_acyclic())
        ret = self.inner_validate()
        assert ret is None

    @transition(dag_lite.DAG.topological_sort)
    def topological_sort(self) -> Any:
        require(self.inner_dependencies_complete())
        require(self.inner_graph_acyclic())
        ret = self.inner_topological_sort()
        assert isinstance(ret, list)
        registered = self.inner_all_nodes()
        assert set(ret) == set(registered)
        for index, node_id in enumerate(ret):
            upstream = set(self.inner_get_dependencies(node_id)) & set(registered)
            for dependency in upstream:
                assert ret.index(dependency) < index
        return ret

    @transition(dag_lite.DAG.find_roots)
    def find_roots(self) -> Any:
        ret = self.inner_find_roots()
        assert isinstance(ret, set)
        assert ret <= self.inner_all_nodes()
        for node_id in ret:
            assert not set(self.inner_get_dependencies(node_id))
        return ret

    @transition(dag_lite.DAG.find_leaves)
    def find_leaves(self) -> Any:
        ret = self.inner_find_leaves()
        assert isinstance(ret, set)
        assert ret <= self.inner_all_nodes()
        for node_id in ret:
            assert not set(self.inner_get_dependents(node_id))
        return ret

    @transition(dag_lite.DAG.compute_critical_path)
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Any:
        require_arg(estimated_durations, Optional[Mapping[str, float]])
        require(self.inner_dependencies_complete())
        require(self.inner_graph_acyclic())
        ret = self.inner_compute_critical_path(estimated_durations)
        path, weight = ret
        assert isinstance(path, list)
        assert isinstance(weight, float)
        registered = self.inner_all_nodes()
        if registered:
            assert len(path) > 0
            assert len(set(path)) == len(path)
            for node_id in path:
                assert node_id in registered
            for upstream_id, downstream_id in zip(path, path[1:]):
                assert upstream_id in self.inner_get_dependencies(downstream_id)
        else:
            assert path == []
            assert weight == 0.0
        return ret

    # --- state queries consulted by contract preconditions ---

    def inner_has_node(self, node_id: str) -> bool: ...

    def inner_all_nodes(self) -> Set[str]: ...

    def inner_get_node(self, node_id: str) -> dag_lite.NodeDefinition[Any]: ...

    def inner_get_dependencies(self, node_id: str) -> Set[str]: ...

    def inner_get_dependents(self, node_id: str) -> Set[str]: ...

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

    def inner_validate(self) -> None: ...

    def inner_topological_sort(self) -> List[str]: ...

    def inner_find_roots(self) -> Set[str]: ...

    def inner_find_leaves(self) -> Set[str]: ...

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]: ...

    def inner_dependencies_complete(self) -> bool: ...

    def inner_graph_acyclic(self) -> bool: ...


@dataclass
class DAGState:
    """Model state owned exclusively by `DAGFakeStateMachine`."""

    definitions: Dict[str, dag_lite.NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)


class DAGFakeStateMachine(DAGStateMachine):
    """Stateful in-memory fake for the `DAG` interface."""

    def __init__(
        self,
        state: Optional[DAGState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGState:
        return DAGState()

    @transition.seeding()
    def seed_graph(self) -> None:
        self.state.definitions.clear()
        self.state.upstream.clear()
        self.state.downstream.clear()
        self.inner_add_node("a", _noop_action, None, 0, 0)
        self.inner_add_node("b", _noop_action, None, 1, 0)
        self.inner_add_node("c", _noop_action, ("a",), 0, 0)
        self.inner_add_edge("b", "c")

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        dependency_set = frozenset(dependencies or ())
        self.state.definitions[node_id] = dag_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self.state.upstream.setdefault(node_id, set()).update(dependency_set)
        self.state.downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            self.state.downstream.setdefault(dependency, set()).add(node_id)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        for dependency in list(self.state.upstream.get(node_id, set())):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in list(self.state.downstream.get(node_id, set())):
            self.state.upstream.get(dependent, set()).discard(node_id)
        self.state.definitions.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.definitions

    def inner_get_node(self, node_id: str) -> dag_lite.NodeDefinition[Any]:
        return self.state.definitions[node_id]

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.upstream.get(node_id, set()))

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set(self.state.downstream.get(node_id, set()))

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.definitions)

    def inner_validate(self) -> None:
        return None

    def inner_topological_sort(self) -> List[str]:
        priorities = {
            node_id: definition.priority for node_id, definition in self.state.definitions.items()
        }
        return _topological_order(
            self.state.definitions,
            self.state.upstream,
            self.state.downstream,
            priorities,
        )

    def inner_find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id in self.state.definitions
            if not set(self.state.upstream.get(node_id, set()))
        }

    def inner_find_leaves(self) -> Set[str]:
        return {
            node_id
            for node_id in self.state.definitions
            if not set(self.state.downstream.get(node_id, set()))
        }

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        return _critical_path(
            self.state.definitions,
            self.state.upstream,
            estimated_durations,
        )

    def inner_dependencies_complete(self) -> bool:
        return _dependencies_complete(self.state.definitions, self.state.upstream)

    def inner_graph_acyclic(self) -> bool:
        return _graph_is_acyclic(self.state.definitions, self.state.upstream)


FakeDAG: Any = synthesize_fake(DAGFakeStateMachine)


def make_dag_fake(state: Optional[DAGState] = None) -> dag_lite.DAG:
    """Builds a fresh in-memory `DAG` fake seeded with the initial model state."""
    return FakeDAG(state=state or DAGFakeStateMachine().make_initial_state())


FakeDAGFuzzTest = compile_hypothesis_test_case(
    DAGFakeStateMachine,
    name="FakeDAGFuzzTest",
)


# ==============================================================================
# PART A: WAVE SCHEDULER INTERFACE
# ==============================================================================


class WaveSchedulerStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the `WaveScheduler` interface."""

    @domain(valid=_scheduled_node_ids, invalid=lambda machine: ["zz_absent"])
    def scheduled_node_id(self, node_id: str) -> bool:
        return isinstance(node_id, str) and node_id in self.inner_get_all_states()

    @transition(dag_lite.WaveScheduler.next_wave)
    def next_wave(self) -> Any:
        before = self.inner_get_all_states()
        ret = self.inner_next_wave()
        assert isinstance(ret, list)
        for node_id in ret:
            assert before.get(node_id) == dag_lite.NodeState.READY
        return ret

    @transition(dag_lite.WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require_arg(node_id, self.scheduled_node_id)
        ret = self.inner_mark_running(node_id)
        assert ret is None
        assert self.inner_get_state(node_id) == dag_lite.NodeState.RUNNING

    @transition(dag_lite.WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require_arg(node_id, self.scheduled_node_id)
        before = self.inner_get_all_states()
        ret = self.inner_mark_succeeded(node_id)
        after = self.inner_get_all_states()
        assert ret is None
        assert after[node_id] == dag_lite.NodeState.SUCCEEDED
        for other_id, state in after.items():
            assert (
                state == before.get(other_id)
                or other_id == node_id
                or state == dag_lite.NodeState.READY
            )
            assert (
                state != dag_lite.NodeState.FAILED
                or before.get(other_id) == dag_lite.NodeState.FAILED
            )

    @transition(dag_lite.WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: dag_lite.FailurePolicy) -> None:
        require_arg(node_id, self.scheduled_node_id)
        require_arg(failure_policy, dag_lite.FailurePolicy)
        ret = self.inner_mark_failed(node_id, failure_policy)
        after = self.inner_get_all_states()
        assert ret is None
        assert after[node_id] == dag_lite.NodeState.FAILED
        if failure_policy == dag_lite.FailurePolicy.FAIL_FAST:
            for state in after.values():
                assert state != dag_lite.NodeState.PENDING

    @transition(dag_lite.WaveScheduler.is_finished)
    def is_finished(self) -> Any:
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    @transition(dag_lite.WaveScheduler.get_state)
    def get_state(self, node_id: str) -> Any:
        require_arg(node_id, self.scheduled_node_id)
        ret = self.inner_get_state(node_id)
        assert isinstance(ret, dag_lite.NodeState)
        assert ret == self.inner_get_all_states()[node_id]
        return ret

    @transition(dag_lite.WaveScheduler.get_all_states)
    def get_all_states(self) -> Any:
        ret = self.inner_get_all_states()
        for state in ret.values():
            assert isinstance(state, dag_lite.NodeState)
        return ret

    # --- state queries consulted by contract preconditions ---

    def inner_next_wave(self) -> List[str]: ...

    def inner_mark_running(self, node_id: str) -> None: ...

    def inner_mark_succeeded(self, node_id: str) -> None: ...

    def inner_mark_failed(self, node_id: str, failure_policy: dag_lite.FailurePolicy) -> None: ...

    def inner_is_finished(self) -> bool: ...

    def inner_get_state(self, node_id: str) -> dag_lite.NodeState: ...

    def inner_get_all_states(self) -> Mapping[str, dag_lite.NodeState]: ...


@dataclass
class WaveSchedulerState:
    """Model state owned exclusively by `WaveSchedulerFakeStateMachine`."""

    dependencies: Dict[str, Set[str]] = field(default_factory=dict)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)
    priorities: Dict[str, int] = field(default_factory=dict)
    states: Dict[str, dag_lite.NodeState] = field(default_factory=dict)


class WaveSchedulerFakeStateMachine(WaveSchedulerStateMachine):
    """Stateful in-memory fake for the `WaveScheduler` interface."""

    def __init__(
        self,
        state: Optional[WaveSchedulerState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> WaveSchedulerState:
        return WaveSchedulerState()

    @transition.seeding()
    def seed_waves(self) -> None:
        self.state.dependencies = {
            "a": set(),
            "b": set(),
            "c": {"a"},
            "d": {"b"},
            "e": {"c", "d"},
            "f": {"c", "e"},
        }
        self.state.dependents = {
            "a": {"c"},
            "b": {"d"},
            "c": {"e", "f"},
            "d": {"e"},
            "e": {"f"},
            "f": set(),
        }
        self.state.priorities = {"a": 0, "b": 1, "c": 0, "d": 0, "e": 0, "f": 0}
        self.state.states = {}
        self._sync()

    def _sync(self) -> None:
        for node_id in self.state.dependencies:
            if node_id not in self.state.states:
                if self.state.dependencies.get(node_id):
                    self.state.states[node_id] = dag_lite.NodeState.PENDING
                else:
                    self.state.states[node_id] = dag_lite.NodeState.READY

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        visited: Set[str] = set()
        pending: List[str] = list(self.state.dependents.get(node_id, set()))
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self.state.dependents.get(current, set()))
        return visited

    def inner_next_wave(self) -> List[str]:
        self._sync()
        ready = [
            node_id
            for node_id, state in self.state.states.items()
            if state == dag_lite.NodeState.READY
            and all(
                self.state.states.get(dependency) == dag_lite.NodeState.SUCCEEDED
                for dependency in self.state.dependencies.get(node_id, set())
            )
        ]
        ready.sort(key=lambda node_id: (-self.state.priorities.get(node_id, 0), node_id))
        return ready

    def inner_mark_running(self, node_id: str) -> None:
        self._sync()
        self.state.states[node_id] = dag_lite.NodeState.RUNNING

    def inner_mark_succeeded(self, node_id: str) -> None:
        self._sync()
        self.state.states[node_id] = dag_lite.NodeState.SUCCEEDED
        for dependent in self.state.dependents.get(node_id, set()):
            if self.state.states.get(dependent) == dag_lite.NodeState.PENDING:
                if all(
                    self.state.states.get(dependency) == dag_lite.NodeState.SUCCEEDED
                    for dependency in self.state.dependencies.get(dependent, set())
                ):
                    self.state.states[dependent] = dag_lite.NodeState.READY

    def inner_mark_failed(self, node_id: str, failure_policy: dag_lite.FailurePolicy) -> None:
        self._sync()
        self.state.states[node_id] = dag_lite.NodeState.FAILED
        dependents = self._transitive_dependents(node_id)
        if failure_policy == dag_lite.FailurePolicy.FAIL_FAST:
            for other_id, state in self.state.states.items():
                if other_id != node_id and not _is_terminal(state):
                    self.state.states[other_id] = dag_lite.NodeState.CANCELLED
        elif failure_policy == dag_lite.FailurePolicy.SKIP_DOWNSTREAM:
            for dependent in dependents:
                if not _is_terminal(self.state.states.get(dependent, dag_lite.NodeState.PENDING)):
                    self.state.states[dependent] = dag_lite.NodeState.SKIPPED
        else:
            for dependent in dependents:
                state = self.state.states.get(dependent, dag_lite.NodeState.PENDING)
                if not _is_terminal(state):
                    self.state.states[dependent] = dag_lite.NodeState.SKIPPED

    def inner_is_finished(self) -> bool:
        self._sync()
        if all(_is_terminal(state) for state in self.state.states.values()):
            return True
        return not self.inner_next_wave()

    def inner_get_state(self, node_id: str) -> dag_lite.NodeState:
        self._sync()
        return self.state.states[node_id]

    def inner_get_all_states(self) -> Mapping[str, dag_lite.NodeState]:
        self._sync()
        return {
            node_id: state
            for node_id, state in self.state.states.items()
            if node_id in self.state.dependencies
        }


FakeWaveScheduler: Any = synthesize_fake(WaveSchedulerFakeStateMachine)


def make_wave_scheduler_fake(
    state: Optional[WaveSchedulerState] = None,
) -> dag_lite.WaveScheduler:
    """Builds a fresh in-memory `WaveScheduler` fake seeded with the initial model state."""
    return FakeWaveScheduler(
        state=state or WaveSchedulerFakeStateMachine().make_initial_state()
    )


FakeWaveSchedulerFuzzTest = compile_hypothesis_test_case(
    WaveSchedulerFakeStateMachine,
    name="FakeWaveSchedulerFuzzTest",
)


# ==============================================================================
# PART A: DAG RUNNER INTERFACE
# ==============================================================================


class DAGRunnerStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the `DAGRunner` interface."""

    @transition(dag_lite.DAGRunner.run)
    def run(self, failure_policy: dag_lite.FailurePolicy) -> Any:
        require_arg(failure_policy, dag_lite.FailurePolicy)
        require(self.inner_dependencies_complete())
        require(self.inner_graph_acyclic())
        ret = self.inner_run(failure_policy)
        assert isinstance(ret, dag_lite.DAGRunReport)
        assert ret.wall_clock_seconds >= 0.0
        return ret

    # --- state queries consulted by contract preconditions ---

    def inner_run(self, failure_policy: dag_lite.FailurePolicy) -> dag_lite.DAGRunReport: ...

    def inner_dependencies_complete(self) -> bool: ...

    def inner_graph_acyclic(self) -> bool: ...


@dataclass
class DAGRunnerState:
    """Model state owned exclusively by `DAGRunnerFakeStateMachine`."""

    dependencies: Dict[str, Set[str]] = field(default_factory=dict)
    priorities: Dict[str, int] = field(default_factory=dict)


class DAGRunnerFakeStateMachine(DAGRunnerStateMachine):
    """Stateful in-memory fake for the `DAGRunner` interface."""

    def __init__(
        self,
        state: Optional[DAGRunnerState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGRunnerState:
        return DAGRunnerState()

    @transition.seeding()
    def seed_runner(self) -> None:
        self.state.dependencies = {
            "a": set(),
            "b": {"a"},
            "c": {"b"},
        }
        self.state.priorities = {"a": 0, "b": 0, "c": 0}

    def inner_run(self, failure_policy: dag_lite.FailurePolicy) -> dag_lite.DAGRunReport:
        nodes = set(self.state.dependencies)
        downstream = _downstream_map(nodes, self.state.dependencies)
        order = _topological_order(
            nodes, self.state.dependencies, downstream, self.state.priorities
        )
        results: Dict[str, dag_lite.NodeResult[Any]] = {
            node_id: dag_lite.NodeResult(
                node_id=node_id,
                state=dag_lite.NodeState.SUCCEEDED,
                value=None,
                error=None,
                duration_seconds=0.0,
                retries_attempted=0,
            )
            for node_id in order
        }
        path, weight = _critical_path(nodes, self.state.dependencies, None)
        return dag_lite.DAGRunReport(
            total_nodes=len(nodes),
            succeeded_nodes=tuple(order),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=weight,
            critical_path=tuple(path),
            results=results,
        )

    def inner_dependencies_complete(self) -> bool:
        return _dependencies_complete(self.state.dependencies, self.state.dependencies)

    def inner_graph_acyclic(self) -> bool:
        return _graph_is_acyclic(self.state.dependencies, self.state.dependencies)


FakeDAGRunner: Any = synthesize_fake(DAGRunnerFakeStateMachine)


def make_dag_runner_fake(state: Optional[DAGRunnerState] = None) -> dag_lite.DAGRunner:
    """Builds a fresh in-memory `DAGRunner` fake seeded with the initial model state."""
    return FakeDAGRunner(state=state or DAGRunnerFakeStateMachine().make_initial_state())


FakeDAGRunnerFuzzTest = compile_hypothesis_test_case(
    DAGRunnerFakeStateMachine,
    name="FakeDAGRunnerFuzzTest",
)


# ==============================================================================
# PART A: FIXED FAKE TESTS (factory seams not reached by fuzzing)
# ==============================================================================


class TestDAGFake(unittest.TestCase):
    """Fixed fake tests for the `make_dag_fake` factory seam."""

    def test_make_dag_fake(self) -> None:
        fake = make_dag_fake()
        assert fake.all_nodes() == set()
        fake.add_node("n1", _noop_action, None, 0, 0)
        assert fake.has_node("n1")
        assert fake.topological_sort() == ["n1"]
        assert _noop_action() is None


class TestWaveSchedulerFake(unittest.TestCase):
    """Fixed fake tests for the `make_wave_scheduler_fake` factory seam."""

    def test_make_wave_scheduler_fake(self) -> None:
        fake = make_wave_scheduler_fake()
        assert dict(fake.get_all_states()) == {}
        assert fake.is_finished()


class TestDAGRunnerFake(unittest.TestCase):
    """Fixed fake tests for the `make_dag_runner_fake` factory seam."""

    def test_make_dag_runner_fake(self) -> None:
        fake = make_dag_runner_fake()
        report = fake.run(dag_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 0
        assert dict(report.results) == {}

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T17:41:28Z
# LAST_CHANGED: 2026-11-15T17:41:28Z
# CHANGE: Removed uncontracted DAGRunner.run postconditions flagged by pretense_qa (slug dag_lite.runner.run.consolidated_report): dropped the report cardinality assertion (total_nodes == len(results)) and the results-key coverage assertion over succeeded/failed/skipped/cancelled node tuples. The low-level contract does not constrain DAGRunReport.results to cover every graph node (nodes already terminal before a run are omitted), so run now asserts only the contracted return type and non-negative elapsed wall-clock time.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation module for the synchronous DAG execution and wave scheduling engine.

The module binds the stateless interface contracts imported from ``pretense_intf`` to the
concrete DAG, WaveScheduler, and DAGRunner singletons defined in ``lib.dag_engine_lite_impl``.
Only concrete SUT resolution lives here: every inherited ``@transition`` contract, argument
domain, precondition guard, and postcondition stays in the interface module.
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

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib import dag_engine_lite as dag_lite
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGImpl,
    DAGRunner as DAGRunnerImpl,
    WaveScheduler as WaveSchedulerImpl,
)
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGRunnerStateMachine,
    DAGStateMachine,
    WaveSchedulerStateMachine,
)


def _noop_action() -> Any:
    """Zero-argument node action that succeeds without side effects."""
    return None


def _failing_action() -> Any:
    """Zero-argument node action that always raises, exercising failure policies."""
    raise RuntimeError("boom")


class DAGEngineLiteImplStateMachine(
    DAGStateMachine,
    WaveSchedulerStateMachine,
    DAGRunnerStateMachine,
):
    """Implementation binding for the DAG, WaveScheduler, and DAGRunner concrete singletons."""

    # --- DAG inner transitions ---

    def inner_has_node(self, node_id: str) -> bool:
        """Resolves whether ``node_id`` is registered in the concrete DAG."""
        target = sut(dag_lite.DAG)
        return target.has_node(node_id)

    def inner_all_nodes(self) -> Set[str]:
        """Resolves all node identifiers registered in the concrete DAG."""
        target = sut(dag_lite.DAG)
        return target.all_nodes()

    def inner_get_node(self, node_id: str) -> dag_lite.NodeDefinition[Any]:
        """Resolves the immutable definition of a registered node."""
        target = sut(dag_lite.DAG)
        return target.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        """Resolves the direct upstream dependencies of a node."""
        target = sut(dag_lite.DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        """Resolves the direct downstream dependents of a node."""
        target = sut(dag_lite.DAG)
        return target.get_dependents(node_id)

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Registers a node definition in the concrete DAG."""
        target = sut(dag_lite.DAG)
        target.add_node(node_id, action, dependencies, priority, retries)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Registers a directed dependency edge in the concrete DAG."""
        target = sut(dag_lite.DAG)
        target.add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        """Removes a node and its incident edges from the concrete DAG."""
        target = sut(dag_lite.DAG)
        target.remove_node(node_id)

    def inner_validate(self) -> None:
        """Validates consistency, completeness, and acyclicity of the concrete DAG."""
        target = sut(dag_lite.DAG)
        target.validate()

    def inner_topological_sort(self) -> List[str]:
        """Resolves the deterministic topological ordering of the concrete DAG."""
        target = sut(dag_lite.DAG)
        return target.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        """Resolves the root nodes of the concrete DAG."""
        target = sut(dag_lite.DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        """Resolves the leaf nodes of the concrete DAG."""
        target = sut(dag_lite.DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Resolves the longest weighted dependency path through the concrete DAG."""
        target = sut(dag_lite.DAG)
        return target.compute_critical_path(estimated_durations)

    def inner_dependencies_complete(self) -> bool:
        """Reports whether every referenced dependency is registered in the concrete DAG."""
        target = sut(dag_lite.DAG)
        registered = target.all_nodes()
        return all(target.get_dependencies(node_id) <= registered for node_id in registered)

    def inner_graph_acyclic(self) -> bool:
        """Reports whether the concrete DAG is free of directed dependency cycles."""
        target = sut(dag_lite.DAG)
        registered = target.all_nodes()
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def visit(node_id: str) -> bool:
            if node_id in visited:
                return True
            if node_id in visiting:
                return False
            visiting.add(node_id)
            for dependency in target.get_dependencies(node_id) & registered:
                if not visit(dependency):
                    return False
            visiting.discard(node_id)
            visited.add(node_id)
            return True

        return all(visit(node_id) for node_id in registered)

    # --- WaveScheduler inner transitions ---

    def inner_next_wave(self) -> List[str]:
        """Resolves the next batch of runnable nodes from the concrete scheduler."""
        target = sut(dag_lite.WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        """Marks a node RUNNING in the concrete scheduler."""
        target = sut(dag_lite.WaveScheduler)
        target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Marks a node SUCCEEDED in the concrete scheduler."""
        target = sut(dag_lite.WaveScheduler)
        target.mark_succeeded(node_id)

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: dag_lite.FailurePolicy,
    ) -> None:
        """Marks a node FAILED in the concrete scheduler and applies the failure policy."""
        target = sut(dag_lite.WaveScheduler)
        target.mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        """Resolves whether the concrete scheduler has reached a terminal state."""
        target = sut(dag_lite.WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> dag_lite.NodeState:
        """Resolves the current execution state of a scheduled node."""
        target = sut(dag_lite.WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, dag_lite.NodeState]:
        """Resolves the execution state of every scheduled node."""
        target = sut(dag_lite.WaveScheduler)
        return target.get_all_states()

    # --- DAGRunner inner transitions ---

    def inner_run(self, failure_policy: dag_lite.FailurePolicy) -> dag_lite.DAGRunReport:
        """Executes the concrete DAG through the concrete runner."""
        target = sut(dag_lite.DAGRunner)
        return target.run(failure_policy)


class TestDAGEngineLiteImplReal(LifecycleTestCase):
    """Real-SUT scenario conformance tests for the DAG engine implementation."""

    target = DAGImpl

    def setUp(self) -> None:
        super().setUp()
        self.sm = DAGEngineLiteImplStateMachine(
            singletons={
                dag_lite.DAG: self.sut,
                dag_lite.WaveScheduler: self.get_singleton(WaveSchedulerImpl),
                dag_lite.DAGRunner: self.get_singleton(DAGRunnerImpl),
            }
        )
        self.checked = self.sm.as_checked(dag_lite.DAG, self.sut)
        self.checked_scheduler = self.sm.as_checked(
            dag_lite.WaveScheduler, self.get_singleton(WaveSchedulerImpl)
        )
        self.checked_runner = self.sm.as_checked(
            dag_lite.DAGRunner, self.get_singleton(DAGRunnerImpl)
        )

    def test_real_dag_lifecycle(self) -> None:
        self.checked.add_node("a", _noop_action, None, 0, 0)
        self.checked.add_node("b", _noop_action, ("a",), 1, 0)
        self.checked.add_node("c", _noop_action, None, 0, 0)
        self.checked.add_node("d", _noop_action, None, 2, 0)
        self.checked.add_edge("c", "d")

        assert self.checked.has_node("a")
        assert not self.checked.has_node("zz_absent")
        assert self.checked.all_nodes() == {"a", "b", "c", "d"}

        assert self.checked.get_dependencies("b") == {"a"}
        assert self.checked.get_dependencies("d") == {"c"}
        assert self.checked.get_dependents("a") == {"b"}
        assert self.checked.get_dependents("c") == {"d"}

        definition = self.checked.get_node("b")
        assert definition.node_id == "b"
        assert definition.dependencies == frozenset({"a"})
        assert definition.priority == 1
        assert definition.retries == 0

        self.checked.validate()
        assert self.checked.find_roots() == {"a", "c"}
        assert self.checked.find_leaves() == {"b", "d"}
        assert self.checked.topological_sort() == ["a", "b", "c", "d"]

        path, weight = self.checked.compute_critical_path(
            {"a": 1.0, "b": 5.0, "c": 1.0, "d": 1.0}
        )
        assert path == ["a", "b"]
        assert weight == 6.0

        self.checked.remove_node("b")
        assert self.checked.all_nodes() == {"a", "c", "d"}
        assert not self.checked.has_node("b")
        assert self.checked.find_leaves() == {"a", "d"}
        assert self.checked.get_dependents("a") == set()

    def test_real_wave_scheduler(self) -> None:
        self.checked.add_node("a", _noop_action, None, 0, 0)
        self.checked.add_node("b", _noop_action, ("a",), 0, 0)
        self.checked.add_node("c", _noop_action, None, 0, 0)
        self.checked.add_node("d", _noop_action, ("c",), 0, 0)

        assert dict(self.checked_scheduler.get_all_states()) == {
            "a": dag_lite.NodeState.READY,
            "b": dag_lite.NodeState.PENDING,
            "c": dag_lite.NodeState.READY,
            "d": dag_lite.NodeState.PENDING,
        }
        assert self.checked_scheduler.next_wave() == ["a", "c"]

        self.checked_scheduler.mark_running("a")
        assert self.checked_scheduler.get_state("a") == dag_lite.NodeState.RUNNING
        self.checked_scheduler.mark_succeeded("a")
        assert self.checked_scheduler.get_state("a") == dag_lite.NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("b") == dag_lite.NodeState.READY
        assert self.checked_scheduler.is_finished() is False

        self.checked_scheduler.mark_running("b")
        self.checked_scheduler.mark_succeeded("b")
        self.checked_scheduler.mark_running("c")
        self.checked_scheduler.mark_succeeded("c")
        assert self.checked_scheduler.get_state("d") == dag_lite.NodeState.READY
        self.checked_scheduler.mark_running("d")
        self.checked_scheduler.mark_succeeded("d")
        assert self.checked_scheduler.is_finished() is True

    def test_real_runner_success(self) -> None:
        self.checked.add_node("a", _noop_action, None, 0, 0)
        self.checked.add_node("b", _noop_action, ("a",), 0, 0)
        self.checked.add_node("c", _noop_action, ("b",), 0, 0)

        report = self.checked_runner.run(dag_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert report.succeeded_nodes == ("a", "b", "c")
        assert report.failed_nodes == ()
        assert report.skipped_nodes == ()
        assert report.cancelled_nodes == ()
        assert report.critical_path == ("a", "b", "c")
        assert report.results["a"].state == dag_lite.NodeState.SUCCEEDED

    def test_real_runner_skip_downstream(self) -> None:
        self.checked.add_node("a", _failing_action, None, 0, 0)
        self.checked.add_node("b", _noop_action, ("a",), 0, 0)
        self.checked.add_node("c", _noop_action, None, 0, 0)

        report = self.checked_runner.run(dag_lite.FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 3
        assert report.failed_nodes == ("a",)
        assert report.skipped_nodes == ("b",)
        assert report.succeeded_nodes == ("c",)
        assert report.results["b"].state == dag_lite.NodeState.SKIPPED

    def test_real_scheduler_fail_fast(self) -> None:
        self.checked.add_node("a", _noop_action, None, 0, 0)
        self.checked.add_node("b", _noop_action, ("a",), 0, 0)
        self.checked.add_node("c", _noop_action, ("b",), 0, 0)

        assert dict(self.checked_scheduler.get_all_states()) == {
            "a": dag_lite.NodeState.READY,
            "b": dag_lite.NodeState.PENDING,
            "c": dag_lite.NodeState.PENDING,
        }

        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed("a", dag_lite.FailurePolicy.FAIL_FAST)
        after = dict(self.checked_scheduler.get_all_states())
        assert after["a"] == dag_lite.NodeState.FAILED
        assert after["b"] == dag_lite.NodeState.CANCELLED
        assert after["c"] == dag_lite.NodeState.CANCELLED
        assert self.checked_scheduler.is_finished() is True

    def test_real_runner_fail_fast(self) -> None:
        self.checked.add_node("a", _failing_action, None, 0, 0)
        self.checked.add_node("b", _noop_action, None, 0, 0)
        self.checked.add_node("c", _noop_action, ("b",), 0, 0)

        report = self.checked_runner.run(dag_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 3
        assert report.failed_nodes == ("a",)
        assert report.succeeded_nodes == ()
        assert set(report.cancelled_nodes) == {"b", "c"}
        assert report.results["a"].state == dag_lite.NodeState.FAILED
        assert report.results["b"].state == dag_lite.NodeState.CANCELLED
        assert report.results["c"].state == dag_lite.NodeState.CANCELLED

    def test_violating_add_node_duplicate(self) -> None:
        self.checked.add_node("dup", _noop_action, None, 0, 0)
        self.checked.violating(dag_lite.DuplicateNodeError).add_node(
            "dup", _noop_action, None, 0, 0
        )

    def test_violating_get_node_absent(self) -> None:
        self.checked.add_node("present", _noop_action, None, 0, 0)
        self.checked.violating(dag_lite.NodeNotFoundError).get_node("zz_absent")

    def test_violating_add_edge_absent(self) -> None:
        self.checked.add_node("present", _noop_action, None, 0, 0)
        self.checked.violating(dag_lite.NodeNotFoundError).add_edge("present", "zz_absent")

    def test_violating_remove_node_absent(self) -> None:
        self.checked.add_node("present", _noop_action, None, 0, 0)
        self.checked.violating(dag_lite.NodeNotFoundError).remove_node("zz_absent")

    def test_violating_get_dependencies_absent(self) -> None:
        self.checked.add_node("present", _noop_action, None, 0, 0)
        self.checked.violating(dag_lite.NodeNotFoundError).get_dependencies("zz_absent")

    def test_violating_get_dependents_absent(self) -> None:
        self.checked.add_node("present", _noop_action, None, 0, 0)
        self.checked.violating(dag_lite.NodeNotFoundError).get_dependents("zz_absent")

    def test_violating_validate_cycle(self) -> None:
        self.checked.add_node("x", _noop_action, ("y",), 0, 0)
        self.checked.add_node("y", _noop_action, ("x",), 0, 0)
        self.checked.violating(dag_lite.CycleError).validate()

    def test_violating_validate_cycle_with_downstream_tail(self) -> None:
        self.checked.add_node("x", _noop_action, ("y",), 0, 0)
        self.checked.add_node("y", _noop_action, ("x",), 0, 0)
        self.checked.add_node("z", _noop_action, ("x",), 0, 0)
        self.checked.violating(dag_lite.CycleError).validate()

    def test_violating_validate_cycle_with_dependent_tail_chain(self) -> None:
        self.checked.add_node("a", _noop_action, ("b",), 0, 0)
        self.checked.add_node("b", _noop_action, ("x",), 0, 0)
        self.checked.add_node("x", _noop_action, ("y",), 0, 0)
        self.checked.add_node("y", _noop_action, ("x",), 0, 0)
        self.checked.violating(dag_lite.CycleError).validate()

    def test_violating_validate_cycle_with_attached_tail_chain(self) -> None:
        self.checked.add_node("a", _noop_action, ("x",), 0, 0)
        self.checked.add_node("b", _noop_action, ("a",), 0, 0)
        self.checked.add_node("x", _noop_action, ("y",), 0, 0)
        self.checked.add_node("y", _noop_action, ("x",), 0, 0)
        self.checked.violating(dag_lite.CycleError).validate()

    def test_violating_validate_cycle_with_leaf_first_tail_chain(self) -> None:
        self.checked.add_node("b", _noop_action, ("a",), 0, 0)
        self.checked.add_node("a", _noop_action, ("x",), 0, 0)
        self.checked.add_node("x", _noop_action, ("y",), 0, 0)
        self.checked.add_node("y", _noop_action, ("x",), 0, 0)
        self.checked.violating(dag_lite.CycleError).validate()

    def test_violating_topological_sort_cycle(self) -> None:
        self.checked.add_node("x", _noop_action, ("y",), 0, 0)
        self.checked.add_node("y", _noop_action, ("x",), 0, 0)
        self.checked.violating(dag_lite.CycleError).topological_sort()

    def test_violating_validate_missing_dependency(self) -> None:
        self.checked.add_node("m", _noop_action, ("zz_absent",), 0, 0)
        self.checked.violating(dag_lite.NodeNotFoundError).validate()

    def test_violating_get_state_absent(self) -> None:
        self.checked_scheduler.violating(dag_lite.NodeNotFoundError).get_state("zz_absent")

    def test_violating_run_cycle(self) -> None:
        self.checked.add_node("p", _noop_action, ("q",), 0, 0)
        self.checked.add_node("q", _noop_action, ("p",), 0, 0)
        self.checked_runner.violating(dag_lite.CycleError).run(
            dag_lite.FailurePolicy.FAIL_FAST
        )


def make_sut() -> dict[type[Any], Any]:
    """Builds a lifecycle-bound DAG engine wired to the concrete implementation singletons."""
    registry = LifecycleRegistry()
    registry.register_singleton(DAGImpl)
    registry.register_singleton(WaveSchedulerImpl)
    registry.register_singleton(DAGRunnerImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        dag_lite.DAG: get_singleton(DAGImpl),
        dag_lite.WaveScheduler: get_singleton(WaveSchedulerImpl),
        dag_lite.DAGRunner: get_singleton(DAGRunnerImpl),
    }


DAGEngineLiteImplFuzzTest = compile_hypothesis_test_case(
    DAGEngineLiteImplStateMachine,
    sut_factory=make_sut,
    name="DAGEngineLiteImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T18:00:57Z
# LAST_CHANGED: 2026-11-15T18:00:08Z
# CHANGE: Added two validate cycle scenarios matching both pretense_coverage facets. Graph shape: chain root 'a' depends directly on cycle node 'x' (chain_root_depends_on_cycle_node), dependent leaf 'b' depends on attached node 'a' (dependent_relation depends_on_attached_node), and the two-node cycle 'x' <-> 'y' uses identifiers greater than the chain identifiers (chain_before_cycle, attached_id 'a' < dependent_id 'b'). test_violating_validate_cycle_with_attached_tail_chain registers a, b, x, y in identifier order; test_violating_validate_cycle_with_leaf_first_tail_chain registers the dependent leaf b before attached a so a dependency-first DFS starts at the leaf and exhausts the root-to-leaf tail chain before entering the cycle. Both call violating(CycleError).validate() terminally; prior scenarios unchanged and bin/check_files passes pretense lint and pyright.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T18:00:57Z
# PRETENSE_QA_AUDIT: 2026-11-15T18:00:29Z
# --- END AUTOFAB METADATA ---
