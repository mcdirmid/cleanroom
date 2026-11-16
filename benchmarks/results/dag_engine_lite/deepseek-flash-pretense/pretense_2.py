# === File: dag_engine_lite_pretense.py ===
"""Pretense specification for the synchronous DAG execution and wave scheduling engine.

The module separates the stateless behavioral contracts (``DAGStateMachine``,
``WaveSchedulerStateMachine``, ``DAGRunnerStateMachine``) from the stateful
in-memory fakes (``*FakeStateMachine``) so that independent implementations and
cross-tests share one pure specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple, cast
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

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGRunReport,
    DAGRunner,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
    WaveScheduler,
)

# ==============================================================================
# Shared helpers
# ==============================================================================

_TERMINAL_STATES = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


def _dependency_map(dependencies: Mapping[str, Collection[str]]) -> Mapping[str, Set[str]]:
    """Normalizes an upstream-dependency mapping into a set-valued mapping."""
    return {node_id: set(upstream) for node_id, upstream in dependencies.items()}


def _is_acyclic(dependencies: Mapping[str, Collection[str]]) -> bool:
    """Determines whether the upstream-dependency mapping contains no directed cycle."""
    remaining = {node_id: set(upstream) for node_id, upstream in dependencies.items()}
    progressed = True
    while progressed and remaining:
        progressed = False
        ready = [node_id for node_id, upstream in remaining.items() if not upstream]
        for node_id in ready:
            remaining.pop(node_id)
            progressed = True
        for upstream in remaining.values():
            upstream.difference_update(ready)
    return not remaining


# ==============================================================================
# 1. DAG interface: stateless behavioral contract
# ==============================================================================


class DAGStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the :class:`DAG` interface."""

    @domain()
    def unused_node_id(self, val: str) -> bool:
        return isinstance(val, str) and not self.inner_has_node(val)

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, self.unused_node_id, error=DuplicateNodeError)
        require_arg(action, object)
        require_arg(dependencies, Optional[Collection[str]])
        require_arg(priority, int)
        require_arg(retries, int)
        expected_upstream = set(dependencies or ())
        self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert self.inner_has_node(node_id)
        assert self.inner_get_dependencies(node_id) == expected_upstream

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require_arg(upstream_id, self.inner_all_nodes(), error=NodeNotFoundError)
        require_arg(downstream_id, self.inner_all_nodes(), error=NodeNotFoundError)
        self.inner_add_edge(upstream_id, downstream_id)
        assert downstream_id in self.inner_get_dependents(upstream_id)
        assert upstream_id in self.inner_get_dependencies(downstream_id)

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require_arg(node_id, self.inner_all_nodes(), error=NodeNotFoundError)
        self.inner_remove_node(node_id)
        assert not self.inner_has_node(node_id)
        for other in self.inner_all_nodes():
            assert node_id not in self.inner_get_dependencies(other)
            assert node_id not in self.inner_get_dependents(other)

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, str)
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.inner_all_nodes())
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require_arg(node_id, self.inner_all_nodes(), error=NodeNotFoundError)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert isinstance(ret.dependencies, frozenset)
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require_arg(node_id, self.inner_all_nodes(), error=NodeNotFoundError)
        ret = self.inner_get_dependencies(node_id)
        assert all(isinstance(upstream, str) for upstream in ret)
        for upstream in ret:
            if self.inner_has_node(upstream):
                assert node_id in self.inner_get_dependents(upstream)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require_arg(node_id, self.inner_all_nodes(), error=NodeNotFoundError)
        ret = self.inner_get_dependents(node_id)
        assert all(isinstance(dependent, str) for dependent in ret)
        for dependent in ret:
            if self.inner_has_node(dependent):
                assert node_id in self.inner_get_dependencies(dependent)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert all(isinstance(node_id, str) for node_id in ret)
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        require(
            all(
                self.inner_get_dependencies(node_id) <= self.inner_all_nodes()
                for node_id in self.inner_all_nodes()
            ),
            error=NodeNotFoundError,
        )
        require(
            _is_acyclic(
                {
                    node_id: self.inner_get_dependencies(node_id)
                    for node_id in self.inner_all_nodes()
                }
            ),
            error=CycleError,
        )
        self.inner_validate()

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(
            all(
                self.inner_get_dependencies(node_id) <= self.inner_all_nodes()
                for node_id in self.inner_all_nodes()
            ),
            error=CycleError,
        )
        require(
            _is_acyclic(
                {
                    node_id: self.inner_get_dependencies(node_id)
                    for node_id in self.inner_all_nodes()
                }
            ),
            error=CycleError,
        )
        nodes = self.inner_all_nodes()
        dependencies = _dependency_map(
            {node_id: self.inner_get_dependencies(node_id) for node_id in nodes}
        )
        ret = self.inner_topological_sort()
        assert len(ret) == len(nodes)
        assert set(ret) == set(nodes)
        positions = {node_id: index for index, node_id in enumerate(ret)}
        for node_id, upstream in dependencies.items():
            assert all(positions[dependency] < positions[node_id] for dependency in upstream)
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        nodes = self.inner_all_nodes()
        assert ret == {
            node_id for node_id in nodes if not self.inner_get_dependencies(node_id)
        }
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        nodes = self.inner_all_nodes()
        assert ret == {
            node_id for node_id in nodes if not self.inner_get_dependents(node_id)
        }
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require_arg(estimated_durations, Optional[Mapping[str, float]])
        require(
            all(
                self.inner_get_dependencies(node_id) <= self.inner_all_nodes()
                for node_id in self.inner_all_nodes()
            ),
            error=CycleError,
        )
        require(
            _is_acyclic(
                {
                    node_id: self.inner_get_dependencies(node_id)
                    for node_id in self.inner_all_nodes()
                }
            ),
            error=CycleError,
        )
        nodes = self.inner_all_nodes()
        dependencies = _dependency_map(
            {node_id: self.inner_get_dependencies(node_id) for node_id in nodes}
        )
        path, weight = self.inner_compute_critical_path(estimated_durations)
        durations = estimated_durations or {}
        assert set(path) <= set(nodes)
        assert len(path) == len(set(path))
        for index in range(1, len(path)):
            assert path[index - 1] in dependencies[path[index]]
        expected_weight = sum(float(durations.get(node_id, 1.0)) for node_id in path)
        assert abs(weight - expected_weight) < 1e-6
        return (path, weight)

    def inner_add_node(
        self,
        node_id: str,
        action: object,
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

    def inner_validate(self) -> None: ...

    def inner_topological_sort(self) -> List[str]: ...

    def inner_find_roots(self) -> Set[str]: ...

    def inner_find_leaves(self) -> Set[str]: ...

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]: ...


# ==============================================================================
# 2. DAG interface: stateful in-memory fake
# ==============================================================================


@dataclass
class DAGState:
    """Model state owned exclusively by :class:`DAGFakeStateMachine`."""

    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)


class DAGFakeStateMachine(DAGStateMachine):
    """Stateful in-memory fake for the :class:`DAG` interface."""

    def __init__(
        self,
        state: Optional[DAGState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DAGState:
        return DAGState()

    @transition.seeding
    def seed_diamond(self) -> None:
        self.inner_add_node("alpha", print, None, 0, 0)
        self.inner_add_node("beta", print, ("alpha",), 3, 1)
        self.inner_add_node("gamma", print, ("alpha",), 1, 0)
        self.inner_add_node("delta", print, ("beta", "gamma"), 2, 0)

    def inner_add_node(
        self,
        node_id: str,
        action: object,
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        state = cast(DAGState, self.state)
        upstream = frozenset(dependencies or ())
        state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=cast(Callable[[], Any], action),
            dependencies=upstream,
            priority=priority,
            retries=retries,
        )
        state.upstream.setdefault(node_id, set())
        state.downstream.setdefault(node_id, set())
        for dependency in upstream:
            state.upstream[node_id].add(dependency)
            state.downstream.setdefault(dependency, set()).add(node_id)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        state = cast(DAGState, self.state)
        state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        state.downstream.setdefault(upstream_id, set()).add(downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        state = cast(DAGState, self.state)
        upstream = state.upstream.pop(node_id, set())
        downstream = state.downstream.pop(node_id, set())
        for dependency in upstream:
            state.downstream.get(dependency, set()).discard(node_id)
        for dependent in downstream:
            state.upstream.get(dependent, set()).discard(node_id)
        state.nodes.pop(node_id, None)

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in cast(DAGState, self.state).nodes

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return cast(DAGState, self.state).nodes[node_id]

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(cast(DAGState, self.state).upstream.get(node_id, set()))

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set(cast(DAGState, self.state).downstream.get(node_id, set()))

    def inner_all_nodes(self) -> Set[str]:
        return set(cast(DAGState, self.state).nodes.keys())

    def inner_validate(self) -> None:
        return None

    def inner_topological_sort(self) -> List[str]:
        state = cast(DAGState, self.state)
        nodes = sorted(state.nodes.keys())
        priorities = {node_id: state.nodes[node_id].priority for node_id in nodes}
        in_degree = {
            node_id: sum(
                1
                for dependency in state.upstream.get(node_id, set())
                if dependency in state.nodes
            )
            for node_id in nodes
        }
        ready = sorted(
            (node_id for node_id in nodes if in_degree[node_id] == 0),
            key=lambda node_id: (-priorities[node_id], node_id),
        )
        order: List[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for dependent in state.downstream.get(current, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        ready.append(dependent)
            ready.sort(key=lambda node_id: (-priorities[node_id], node_id))
        return order

    def inner_find_roots(self) -> Set[str]:
        state = cast(DAGState, self.state)
        return {
            node_id for node_id in state.nodes if not state.upstream.get(node_id, set())
        }

    def inner_find_leaves(self) -> Set[str]:
        state = cast(DAGState, self.state)
        return {
            node_id for node_id in state.nodes if not state.downstream.get(node_id, set())
        }

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        state = cast(DAGState, self.state)
        durations = estimated_durations or {}
        order = self.inner_topological_sort()
        if not order:
            return ([], 0.0)
        earliest: dict[str, float] = {}
        predecessor: dict[str, Optional[str]] = {}
        for node_id in order:
            best_weight = 0.0
            best_predecessor: Optional[str] = None
            for dependency in sorted(state.upstream.get(node_id, set())):
                if dependency in earliest and earliest[dependency] > best_weight:
                    best_weight = earliest[dependency]
                    best_predecessor = dependency
            earliest[node_id] = best_weight + float(durations.get(node_id, 1.0))
            predecessor[node_id] = best_predecessor
        terminal = max(order, key=lambda node_id: earliest[node_id])
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        return (path, earliest[terminal])


FakeDAG = synthesize_fake(DAGFakeStateMachine)


def make_dag_fake(state: Optional[DAGState] = None) -> DAG:
    """Constructs a stateful fake realizing the :class:`DAG` interface."""
    return cast(
        DAG,
        FakeDAG(
            state=state if state is not None else DAGFakeStateMachine().make_initial_state()
        ),
    )


FakeDAGFuzzTest = compile_hypothesis_test_case(
    DAGFakeStateMachine,
    name="FakeDAGFuzzTest",
)


# ==============================================================================
# 3. WaveScheduler interface: stateless behavioral contract
# ==============================================================================


class WaveSchedulerStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the :class:`WaveScheduler` interface."""

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        snapshot = dict(self.inner_get_all_states())
        ret = self.inner_next_wave()
        assert len(ret) == len(set(ret))
        assert all(snapshot[node_id] is NodeState.READY for node_id in ret)
        assert ret or not any(state is NodeState.READY for state in snapshot.values())
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require_arg(node_id, str)
        self.inner_mark_running(node_id)
        assert self.inner_get_state(node_id) is NodeState.RUNNING

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require_arg(node_id, str)
        self.inner_mark_succeeded(node_id)
        assert self.inner_get_state(node_id) is NodeState.SUCCEEDED

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require_arg(node_id, str)
        require_arg(failure_policy, FailurePolicy)
        self.inner_mark_failed(node_id, failure_policy)
        states = dict(self.inner_get_all_states())
        assert states[node_id] is NodeState.FAILED
        cancelled = failure_policy is FailurePolicy.FAIL_FAST
        assert all(
            state is NodeState.CANCELLED
            for other_id, state in states.items()
            if other_id != node_id and state not in _TERMINAL_STATES
        ) or not cancelled

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        states = dict(self.inner_get_all_states())
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        finished = all(state in _TERMINAL_STATES for state in states.values())
        assert not finished or ret
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require_arg(node_id, self.inner_get_all_states(), error=NodeNotFoundError)
        states = dict(self.inner_get_all_states())
        ret = self.inner_get_state(node_id)
        assert ret is states[node_id]
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        ret = self.inner_get_all_states()
        assert all(isinstance(node_id, str) for node_id in ret)
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
# 4. WaveScheduler interface: stateful in-memory fake
# ==============================================================================


@dataclass
class WaveSchedulerState:
    """Model state owned exclusively by :class:`WaveSchedulerFakeStateMachine`."""

    priorities: dict[str, int] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    states: dict[str, NodeState] = field(default_factory=dict)


class WaveSchedulerFakeStateMachine(WaveSchedulerStateMachine):
    """Stateful in-memory fake for the :class:`WaveScheduler` interface."""

    def __init__(
        self,
        state: Optional[WaveSchedulerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> WaveSchedulerState:
        return WaveSchedulerState()

    @transition.seeding
    def seed_diamond(self) -> None:
        self._register("alpha", (), 0)
        self._register("beta", ("alpha",), 3)
        self._register("gamma", ("alpha",), 1)
        self._register("delta", ("beta", "gamma"), 2)

    def _register(
        self, node_id: str, dependencies: Collection[str], priority: int
    ) -> None:
        state = cast(WaveSchedulerState, self.state)
        if node_id in state.states:
            return
        upstream = set(dependencies)
        state.dependencies[node_id] = upstream
        state.priorities[node_id] = priority
        state.states[node_id] = NodeState.READY if not upstream else NodeState.PENDING

    def _ensure_registered(self, node_id: str) -> None:
        state = cast(WaveSchedulerState, self.state)
        if node_id in state.states:
            return
        state.dependencies[node_id] = set()
        state.priorities[node_id] = 0
        state.states[node_id] = NodeState.READY

    def _ready_nodes(self) -> List[str]:
        state = cast(WaveSchedulerState, self.state)
        ready = [
            node_id
            for node_id, node_state in state.states.items()
            if node_state is NodeState.READY
            and all(
                state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in state.dependencies.get(node_id, set())
            )
        ]
        ready.sort(key=lambda node_id: (-state.priorities.get(node_id, 0), node_id))
        return ready

    def _dependents(self, node_id: str) -> Set[str]:
        state = cast(WaveSchedulerState, self.state)
        return {
            dependent
            for dependent, dependencies in state.dependencies.items()
            if node_id in dependencies
        }

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        pending = [node_id]
        collected: Set[str] = set()
        while pending:
            current = pending.pop()
            for dependent in self._dependents(current):
                if dependent not in collected and dependent != node_id:
                    collected.add(dependent)
                    pending.append(dependent)
        return collected

    def inner_next_wave(self) -> List[str]:
        return self._ready_nodes()

    def inner_mark_running(self, node_id: str) -> None:
        state = cast(WaveSchedulerState, self.state)
        self._ensure_registered(node_id)
        state.states[node_id] = NodeState.RUNNING

    def inner_mark_succeeded(self, node_id: str) -> None:
        state = cast(WaveSchedulerState, self.state)
        self._ensure_registered(node_id)
        state.states[node_id] = NodeState.SUCCEEDED
        for dependent in self._dependents(node_id):
            promoted = state.states.get(dependent) is NodeState.PENDING and all(
                state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in state.dependencies.get(dependent, set())
            )
            if promoted:
                state.states[dependent] = NodeState.READY

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        state = cast(WaveSchedulerState, self.state)
        self._ensure_registered(node_id)
        state.states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id, other_state in state.states.items():
                if other_state not in _TERMINAL_STATES:
                    state.states[other_id] = NodeState.CANCELLED
            return
        for dependent in self._transitive_dependents(node_id):
            if state.states.get(dependent) not in _TERMINAL_STATES:
                state.states[dependent] = NodeState.SKIPPED

    def inner_is_finished(self) -> bool:
        state = cast(WaveSchedulerState, self.state)
        terminal = all(
            node_state in _TERMINAL_STATES for node_state in state.states.values()
        )
        running = any(
            node_state is NodeState.RUNNING for node_state in state.states.values()
        )
        ready = bool(self._ready_nodes())
        return terminal or (not running and not ready)

    def inner_get_state(self, node_id: str) -> NodeState:
        return cast(WaveSchedulerState, self.state).states[node_id]

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return dict(cast(WaveSchedulerState, self.state).states)


FakeWaveScheduler = synthesize_fake(WaveSchedulerFakeStateMachine)


def make_wave_scheduler_fake(
    state: Optional[WaveSchedulerState] = None,
) -> WaveScheduler:
    """Constructs a stateful fake realizing the :class:`WaveScheduler` interface."""
    return cast(
        WaveScheduler,
        FakeWaveScheduler(
            state=state
            if state is not None
            else WaveSchedulerFakeStateMachine().make_initial_state()
        ),
    )


FakeWaveSchedulerFuzzTest = compile_hypothesis_test_case(
    WaveSchedulerFakeStateMachine,
    name="FakeWaveSchedulerFuzzTest",
)


# ==============================================================================
# 5. DAGRunner interface: stateless behavioral contract
# ==============================================================================


class DAGRunnerStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the :class:`DAGRunner` interface."""

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require_arg(failure_policy, FailurePolicy)
        ret = self.inner_run(failure_policy)
        assert isinstance(ret, DAGRunReport)
        assert ret.total_nodes >= len(ret.results)
        assert ret.wall_clock_seconds >= 0.0
        assert all(isinstance(node_id, str) for node_id in ret.results)
        assert all(isinstance(node_id, str) for node_id in ret.critical_path)
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport: ...


# ==============================================================================
# 6. DAGRunner interface: stateful in-memory fake
# ==============================================================================


@dataclass
class DAGRunnerState:
    """Model state owned exclusively by :class:`DAGRunnerFakeStateMachine`."""

    completed_runs: int = 0


class DAGRunnerFakeStateMachine(DAGRunnerStateMachine):
    """Stateful in-memory fake for the :class:`DAGRunner` interface."""

    def __init__(
        self,
        state: Optional[DAGRunnerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> DAGRunnerState:
        return DAGRunnerState()

    @transition.seeding
    def seed_empty(self) -> None:
        state = cast(DAGRunnerState, self.state)
        state.completed_runs = 0

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        state = cast(DAGRunnerState, self.state)
        state.completed_runs += 1
        return DAGRunReport(
            total_nodes=0,
            succeeded_nodes=(),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=(),
            results={},
        )


FakeDAGRunner = synthesize_fake(DAGRunnerFakeStateMachine)


def make_dag_runner_fake(state: Optional[DAGRunnerState] = None) -> DAGRunner:
    """Constructs a stateful fake realizing the :class:`DAGRunner` interface."""
    return cast(
        DAGRunner,
        FakeDAGRunner(
            state=state
            if state is not None
            else DAGRunnerFakeStateMachine().make_initial_state()
        ),
    )


FakeDAGRunnerFuzzTest = compile_hypothesis_test_case(
    DAGRunnerFakeStateMachine,
    name="FakeDAGRunnerFuzzTest",
)


# ==============================================================================
# 7. Fixed fake tests for branches not exercised by fuzzing
# ==============================================================================


class TestDAGFake(unittest.TestCase):
    """Fixed fake tests covering valid transitions not reached by fuzzing."""

    def test_empty_graph(self) -> None:
        graph = make_dag_fake()
        self.assertEqual(graph.all_nodes(), set())
        self.assertFalse(graph.has_node("alpha"))
        self.assertEqual(graph.compute_critical_path(None), ([], 0.0))
        self.assertEqual(graph.find_roots(), set())
        self.assertEqual(graph.find_leaves(), set())
        graph.validate()
        self.assertEqual(graph.topological_sort(), [])

    def test_populated_graph(self) -> None:
        graph = make_dag_fake()
        graph.add_node("epsilon", print, None, 0, 0)
        graph.add_node("zeta", print, ("epsilon",), 1, 0)
        graph.add_edge("epsilon", "zeta")
        self.assertTrue(graph.has_node("epsilon"))
        self.assertEqual(graph.get_dependencies("zeta"), {"epsilon"})
        self.assertEqual(graph.get_dependents("epsilon"), {"zeta"})
        self.assertEqual(graph.get_node("zeta").node_id, "zeta")
        self.assertEqual(graph.find_roots(), {"epsilon"})
        self.assertEqual(graph.find_leaves(), {"zeta"})
        graph.validate()
        self.assertEqual(graph.topological_sort(), ["epsilon", "zeta"])
        path, weight = graph.compute_critical_path({"epsilon": 2.0, "zeta": 3.0})
        self.assertEqual(path, ["epsilon", "zeta"])
        self.assertAlmostEqual(weight, 5.0)
        graph.remove_node("epsilon")
        self.assertFalse(graph.has_node("epsilon"))
        self.assertEqual(graph.all_nodes(), {"zeta"})

    def test_duplicate_node_is_rejected(self) -> None:
        sm = DAGFakeStateMachine()
        self.assertTrue(sm.unused_node_id(""))
        sm.add_node("", print, None, 0, 0)
        self.assertFalse(sm.unused_node_id(""))
        self.assertTrue(sm.has_node(""))

    def test_priorities_and_durations(self) -> None:
        graph = make_dag_fake()
        graph.add_node("eta", print, None, 5, 1)
        graph.add_node("theta", print, ("eta",), 1, 2)
        self.assertEqual(graph.topological_sort(), ["eta", "theta"])
        path, weight = graph.compute_critical_path(None)
        self.assertEqual(path, ["eta", "theta"])
        self.assertAlmostEqual(weight, 2.0)


class TestWaveSchedulerFake(unittest.TestCase):
    """Fixed fake tests covering scheduler branches not reached by fuzzing."""

    def test_empty_scheduler(self) -> None:
        scheduler = make_wave_scheduler_fake()
        self.assertEqual(scheduler.next_wave(), [])
        self.assertTrue(scheduler.is_finished())
        self.assertEqual(dict(scheduler.get_all_states()), {})
        with self.assertRaises(Exception):
            scheduler.get_state("alpha")

    def test_seeded_scheduler(self) -> None:
        state = WaveSchedulerState(
            priorities={"alpha": 0, "beta": 1},
            dependencies={"alpha": set(), "beta": {"alpha"}},
            states={"alpha": NodeState.READY, "beta": NodeState.PENDING},
        )
        scheduler = make_wave_scheduler_fake(state)
        self.assertEqual(scheduler.next_wave(), ["alpha"])
        scheduler.mark_running("alpha")
        self.assertEqual(scheduler.get_state("alpha"), NodeState.RUNNING)
        scheduler.mark_succeeded("alpha")
        self.assertEqual(scheduler.get_state("beta"), NodeState.READY)
        self.assertFalse(scheduler.is_finished())
        scheduler.mark_failed("beta", FailurePolicy.FAIL_FAST)
        self.assertTrue(scheduler.is_finished())
        self.assertEqual(scheduler.get_state("alpha"), NodeState.SUCCEEDED)

    def test_skip_downstream_and_continue(self) -> None:
        state = WaveSchedulerState(
            priorities={"alpha": 0, "beta": 0, "gamma": 0},
            dependencies={"alpha": set(), "beta": {"alpha"}, "gamma": {"beta"}},
            states={
                "alpha": NodeState.READY,
                "beta": NodeState.PENDING,
                "gamma": NodeState.PENDING,
            },
        )
        scheduler = make_wave_scheduler_fake(state)
        scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(scheduler.get_state("beta"), NodeState.SKIPPED)
        self.assertEqual(scheduler.get_state("gamma"), NodeState.SKIPPED)
        self.assertTrue(scheduler.is_finished())

    def test_continue_on_error(self) -> None:
        state = WaveSchedulerState(
            priorities={"alpha": 0, "beta": 0},
            dependencies={"alpha": set(), "beta": {"alpha"}},
            states={"alpha": NodeState.READY, "beta": NodeState.PENDING},
        )
        scheduler = make_wave_scheduler_fake(state)
        scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(scheduler.get_state("beta"), NodeState.SKIPPED)
        self.assertTrue(scheduler.is_finished())


class TestDAGRunnerFake(unittest.TestCase):
    """Fixed fake tests covering runner branches not reached by fuzzing."""

    def test_run_policies(self) -> None:
        runner = make_dag_runner_fake()
        for policy in (
            FailurePolicy.FAIL_FAST,
            FailurePolicy.CONTINUE_ON_ERROR,
            FailurePolicy.SKIP_DOWNSTREAM,
        ):
            report = runner.run(policy)
            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(dict(report.results), {})

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T16:50:50Z
# LAST_CHANGED: 2026-11-15T16:50:50Z
# CHANGE: Fix consolidated-report cardinality overspecification in DAGRunnerStateMachine.run: drop the total_nodes == len(results) equality (a valid run may omit result records for starved/unexecuted nodes, e.g. total_nodes=2 with one result record) and relax the reported-node subset assertion, keeping only contract-true structural invariants: report type, total_nodes >= len(results) (results are a subset of graph nodes), non-negative wall-clock time, and string node identifiers in results and critical path.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation specification for the synchronous DAG execution and wave scheduling engine.

Binds the stateless behavioral contracts defined in ``dag_engine_lite_pretense``
to the concrete services realized in ``lib.dag_engine_lite_impl`` and supplies
real-SUT scenario tests plus compiled fuzz tests. The implementation state
machines are stateless: they only resolve the concrete SUT via ``sut(...)`` and
delegate each ``inner_*`` operation to it, inheriting every ``@transition``,
``require``, and ``require_arg`` contract verbatim from the interface.
"""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple, cast

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGRunReport,
    DAGRunner,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
    WaveScheduler,
)
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGImpl,
    DAGRunner as DAGRunnerImpl,
    WaveScheduler as WaveSchedulerImpl,
)
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.pretense_intf.dag_engine_lite_pretense import (
    DAGRunnerStateMachine,
    DAGStateMachine,
    WaveSchedulerStateMachine,
)

# Scenario node identifier domain offered to fuzzing and to the duplicate-node
# guard. It covers both the diamond identifiers (alpha..delta) and the extended
# candidate identifiers (epsilon..kappa) exercised across the engine scenarios.
_SCENARIO_NODE_IDS = frozenset(
    {
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "eta",
        "theta",
        "iota",
        "kappa",
    }
)


def _succeed() -> str:
    """A node action that always completes successfully."""
    return "ok"


def _fail() -> str:
    """A node action that always raises."""
    raise RuntimeError("boom")


def _flaky(attempts: List[int]) -> Callable[[], str]:
    """Builds a node action that fails twice before succeeding."""

    def action() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("flaky")
        return "ok"

    return action


def _resolve_service(
    registry: LifecycleRegistry,
    impl: type[Any],
    protocol: type[Any],
) -> Any:
    """Registers ``impl`` for ``protocol`` when absent and resolves the active singleton."""
    if registry.find_descriptor(protocol) is None:
        registry.register_singleton(impl, keys=[protocol], tier=system)
    return get_singleton(protocol)


# ==============================================================================
# Implementation state machines: stateless bindings to the concrete services
# ==============================================================================


class DAGImplStateMachine(DAGStateMachine):
    """Implementation binding for the concrete :class:`DAG` service."""

    def inner_available_node_ids(self) -> Set[str]:
        return set(_SCENARIO_NODE_IDS) - sut(DAG).all_nodes()

    def inner_add_node(
        self,
        node_id: str,
        action: object,
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        sut(DAG).add_node(
            node_id,
            cast(Callable[[], Any], action),
            dependencies,
            priority,
            retries,
        )

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        sut(DAG).add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        sut(DAG).remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        return sut(DAG).has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return sut(DAG).get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return sut(DAG).get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return sut(DAG).get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        return sut(DAG).all_nodes()

    def inner_validate(self) -> None:
        sut(DAG).validate()

    def inner_topological_sort(self) -> List[str]:
        return sut(DAG).topological_sort()

    def inner_find_roots(self) -> Set[str]:
        return sut(DAG).find_roots()

    def inner_find_leaves(self) -> Set[str]:
        return sut(DAG).find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        return sut(DAG).compute_critical_path(estimated_durations)


class WaveSchedulerImplStateMachine(WaveSchedulerStateMachine):
    """Implementation binding for the concrete :class:`WaveScheduler` service."""

    def inner_next_wave(self) -> List[str]:
        return sut(WaveScheduler).next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        sut(WaveScheduler).mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        sut(WaveScheduler).mark_succeeded(node_id)

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        sut(WaveScheduler).mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        return sut(WaveScheduler).is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        return sut(WaveScheduler).get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return sut(WaveScheduler).get_all_states()


class DAGRunnerImplStateMachine(DAGRunnerStateMachine):
    """Implementation binding for the concrete :class:`DAGRunner` service."""

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        return sut(DAGRunner).run(failure_policy)


# ==============================================================================
# Shared SUT factory for compiled fuzz tests
# ==============================================================================


def make_sut() -> dict[type[Any], Any]:
    """Registers every implementation singleton and returns the protocol bindings."""
    registry = LifecycleRegistry()
    registry.register_singleton(DAGImpl, keys=[DAG], tier=system)
    registry.register_singleton(WaveSchedulerImpl, keys=[WaveScheduler], tier=system)
    registry.register_singleton(DAGRunnerImpl, keys=[DAGRunner], tier=system)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        DAG: get_singleton(DAG),
        WaveScheduler: get_singleton(WaveScheduler),
        DAGRunner: get_singleton(DAGRunner),
    }


# ==============================================================================
# Real-SUT scenario tests
# ==============================================================================


class TestDAGImplReal(LifecycleTestCase):
    """Real-SUT scenario tests for the concrete :class:`DAG` service."""

    target = DAGImpl

    def setUp(self) -> None:
        super().setUp()
        self.dag = cast(DAG, _resolve_service(self.registry, DAGImpl, DAG))
        self.sm = DAGImplStateMachine(singletons={DAG: self.dag})
        self.checked = self.sm.as_checked(DAG, self.dag)

    def test_graph_mutation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("epsilon",), 2, 0)
        self.checked.add_node("eta", _succeed, ("epsilon",), 1, 0)
        self.assertTrue(self.checked.has_node("epsilon"))
        self.assertEqual(self.checked.get_dependencies("zeta"), {"epsilon"})
        self.assertEqual(self.checked.get_dependents("epsilon"), {"zeta", "eta"})
        self.assertEqual(self.checked.all_nodes(), {"epsilon", "zeta", "eta"})
        self.assertEqual(self.checked.get_node("zeta").node_id, "zeta")
        self.assertEqual(self.checked.find_roots(), {"epsilon"})
        self.assertEqual(self.checked.find_leaves(), {"zeta", "eta"})
        self.checked.add_edge("zeta", "eta")
        self.assertEqual(self.checked.get_dependencies("eta"), {"epsilon", "zeta"})
        self.assertEqual(self.checked.find_leaves(), {"eta"})
        self.checked.validate()
        self.checked.remove_node("eta")
        self.assertFalse(self.checked.has_node("eta"))
        self.assertEqual(self.checked.get_dependents("epsilon"), {"zeta"})
        self.assertEqual(self.checked.topological_sort(), ["epsilon", "zeta"])

    def test_topological_tie_breaking(self) -> None:
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_node("beta", _succeed, ("alpha",), 3, 0)
        self.checked.add_node("gamma", _succeed, ("alpha",), 1, 0)
        self.checked.add_node("delta", _succeed, ("beta", "gamma"), 2, 0)
        self.assertEqual(
            self.checked.topological_sort(), ["alpha", "beta", "gamma", "delta"]
        )

    def test_critical_path(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        self.checked.add_node("eta", _succeed, None, 0, 0)
        self.checked.add_node("theta", _succeed, ("eta",), 0, 0)
        path, weight = self.checked.compute_critical_path(
            {"epsilon": 2.0, "zeta": 3.0, "eta": 1.0, "theta": 1.0}
        )
        self.assertEqual(path, ["epsilon", "zeta"])
        self.assertAlmostEqual(weight, 5.0)

    def test_duplicate_node_violation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.violating(DuplicateNodeError).add_node(
            "epsilon", _succeed, None, 0, 0
        )

    def test_missing_node_violation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.violating(NodeNotFoundError).get_dependencies("theta")

    def test_cycle_violation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        self.checked.add_edge("zeta", "epsilon")
        self.checked.violating(CycleError).topological_sort()

    def test_cycle_with_downstream_dependent_violation(self) -> None:
        self.checked.add_node("zeta", _succeed, None, 0, 0)
        self.checked.add_node("eta", _succeed, ("zeta",), 0, 0)
        self.checked.add_node("alpha", _succeed, ("eta",), 0, 0)
        self.checked.add_edge("eta", "zeta")
        self.checked.violating(CycleError).topological_sort()

    def test_add_edge_missing_upstream_violation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        self.checked.violating(NodeNotFoundError).add_edge("theta", "zeta")

    def test_add_edge_missing_downstream_violation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        self.checked.violating(NodeNotFoundError).add_edge("epsilon", "theta")

    def test_validate_missing_dependency_violation(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("theta",), 0, 0)
        self.checked.violating(NodeNotFoundError).validate()

    def test_remove_node_with_dependents(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("eta", _succeed, ("epsilon",), 0, 0)
        self.checked.add_node("zeta", _succeed, ("eta",), 0, 0)
        self.assertEqual(self.checked.get_dependents("eta"), {"zeta"})
        self.checked.remove_node("eta")
        self.assertEqual(self.checked.all_nodes(), {"epsilon", "zeta"})
        self.assertEqual(self.checked.get_dependencies("zeta"), set())
        self.assertEqual(self.checked.find_roots(), {"epsilon", "zeta"})
        self.assertEqual(self.checked.topological_sort(), ["epsilon", "zeta"])

    def test_topological_acyclic_branch(self) -> None:
        self.checked.add_node("epsilon", _succeed, None, 0, 0)
        self.checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        self.checked.add_node("alpha", _succeed, None, 0, 0)
        self.checked.add_edge("zeta", "alpha")
        self.assertEqual(
            self.checked.topological_sort(), ["epsilon", "zeta", "alpha"]
        )


class TestWaveSchedulerImplReal(LifecycleTestCase):
    """Real-SUT scenario tests for the concrete :class:`WaveScheduler` service."""

    target = DAGImpl

    def setUp(self) -> None:
        super().setUp()
        self.dag = cast(DAG, _resolve_service(self.registry, DAGImpl, DAG))
        self.scheduler = cast(
            WaveScheduler,
            _resolve_service(self.registry, WaveSchedulerImpl, WaveScheduler),
        )
        self.dag_sm = DAGImplStateMachine(singletons={DAG: self.dag})
        self.dag_checked = self.dag_sm.as_checked(DAG, self.dag)
        self.sm = WaveSchedulerImplStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.scheduler}
        )
        self.checked = self.sm.as_checked(WaveScheduler, self.scheduler)

    def test_wave_progression(self) -> None:
        self.dag_checked.add_node("alpha", _succeed, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 3, 0)
        self.dag_checked.add_node("gamma", _succeed, ("alpha",), 1, 0)
        self.dag_checked.add_node("delta", _succeed, ("beta", "gamma"), 2, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.checked.mark_running("alpha")
        self.assertIs(self.checked.get_state("alpha"), NodeState.RUNNING)
        self.checked.mark_succeeded("alpha")
        self.assertEqual(self.checked.next_wave(), ["beta", "gamma"])
        self.checked.mark_running("beta")
        self.checked.mark_succeeded("beta")
        self.checked.mark_running("gamma")
        self.checked.mark_succeeded("gamma")
        self.assertEqual(self.checked.next_wave(), ["delta"])
        self.assertFalse(self.checked.is_finished())
        self.checked.mark_running("delta")
        self.checked.mark_succeeded("delta")
        self.assertTrue(self.checked.is_finished())

    def test_fail_fast(self) -> None:
        self.dag_checked.add_node("alpha", _fail, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.checked.mark_running("alpha")
        self.checked.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        self.assertIs(self.checked.get_state("beta"), NodeState.CANCELLED)
        self.assertTrue(self.checked.is_finished())

    def test_continue_on_error(self) -> None:
        self.dag_checked.add_node("alpha", _fail, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.dag_checked.add_node("gamma", _succeed, ("beta",), 0, 0)
        self.dag_checked.add_node("delta", _succeed, None, 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha", "delta"])
        self.checked.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        states = dict(self.checked.get_all_states())
        self.assertIs(states["beta"], NodeState.SKIPPED)
        self.assertIs(states["gamma"], NodeState.SKIPPED)
        self.assertFalse(self.checked.is_finished())
        self.assertEqual(self.checked.next_wave(), ["delta"])

    def test_skip_downstream(self) -> None:
        self.dag_checked.add_node("alpha", _fail, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.dag_checked.add_node("gamma", _succeed, ("beta",), 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.checked.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        states = dict(self.checked.get_all_states())
        self.assertIs(states["beta"], NodeState.SKIPPED)
        self.assertIs(states["gamma"], NodeState.SKIPPED)
        self.assertTrue(self.checked.is_finished())

    def test_unknown_node_violation(self) -> None:
        self.checked.violating(NodeNotFoundError).get_state("theta")

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.dag_checked.add_node("alpha", _succeed, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.dag_checked.remove_node("alpha")
        states = dict(self.checked.get_all_states())
        self.assertNotIn("alpha", states)
        self.assertIn("beta", states)

    def test_late_dependent_after_failure(self) -> None:
        self.dag_checked.add_node("alpha", _fail, None, 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.checked.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.assertEqual(self.checked.next_wave(), [])
        self.assertTrue(self.checked.is_finished())

    def test_promote_skips_non_pending_dependent(self) -> None:
        self.dag_checked.add_node("alpha", _succeed, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.dag_checked.add_node("gamma", _succeed, ("alpha",), 0, 0)
        self.dag_checked.add_node("delta", _succeed, ("beta", "gamma"), 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.checked.mark_succeeded("alpha")
        self.checked.mark_failed("beta", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked.mark_succeeded("gamma")
        states = dict(self.checked.get_all_states())
        self.assertIs(states["delta"], NodeState.SKIPPED)

    def test_skip_downstream_diamond(self) -> None:
        self.dag_checked.add_node("alpha", _fail, None, 0, 0)
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        self.dag_checked.add_node("gamma", _succeed, ("alpha",), 0, 0)
        self.dag_checked.add_node("delta", _succeed, ("beta", "gamma"), 0, 0)
        self.assertEqual(self.checked.next_wave(), ["alpha"])
        self.checked.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        states = dict(self.checked.get_all_states())
        self.assertIs(states["beta"], NodeState.SKIPPED)
        self.assertIs(states["gamma"], NodeState.SKIPPED)
        self.assertIs(states["delta"], NodeState.SKIPPED)
        self.assertTrue(self.checked.is_finished())


class TestDAGRunnerImplReal(LifecycleTestCase):
    """Real-SUT scenario tests for the concrete :class:`DAGRunner` service."""

    target = DAGImpl

    def setUp(self) -> None:
        super().setUp()
        self.dag = cast(DAG, _resolve_service(self.registry, DAGImpl, DAG))
        self.scheduler = cast(
            WaveScheduler,
            _resolve_service(self.registry, WaveSchedulerImpl, WaveScheduler),
        )
        self.runner = cast(
            DAGRunner, _resolve_service(self.registry, DAGRunnerImpl, DAGRunner)
        )
        self.dag_sm = DAGImplStateMachine(singletons={DAG: self.dag})
        self.dag_checked = self.dag_sm.as_checked(DAG, self.dag)
        self.sm = DAGRunnerImplStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.scheduler,
                DAGRunner: self.runner,
            }
        )
        self.checked = self.sm.as_checked(DAGRunner, self.runner)

    def test_run_success(self) -> None:
        self.dag_checked.add_node("epsilon", _succeed, None, 0, 0)
        self.dag_checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        report = self.checked.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"epsilon", "zeta"})
        self.assertEqual(tuple(report.critical_path), ("epsilon", "zeta"))
        self.assertIs(report.results["zeta"].state, NodeState.SUCCEEDED)

    def test_empty_run(self) -> None:
        report = self.checked.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(dict(report.results), {})

    def test_retry_attempts(self) -> None:
        attempts: List[int] = []
        self.dag_checked.add_node("epsilon", _flaky(attempts), None, 0, 3)
        report = self.checked.run(FailurePolicy.CONTINUE_ON_ERROR)
        result = report.results["epsilon"]
        self.assertIs(result.state, NodeState.SUCCEEDED)
        self.assertGreaterEqual(result.retries_attempted, 2)

    def test_fail_fast_run(self) -> None:
        self.dag_checked.add_node("epsilon", _fail, None, 0, 0)
        self.dag_checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        report = self.checked.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(set(report.failed_nodes), {"epsilon"})
        self.assertEqual(set(report.cancelled_nodes), {"zeta"})

    def test_skip_downstream_run(self) -> None:
        self.dag_checked.add_node("epsilon", _fail, None, 0, 0)
        self.dag_checked.add_node("eta", _succeed, None, 0, 0)
        self.dag_checked.add_node("zeta", _succeed, ("epsilon",), 0, 0)
        report = self.checked.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(set(report.failed_nodes), {"epsilon"})
        self.assertEqual(set(report.skipped_nodes), {"zeta"})
        self.assertEqual(set(report.succeeded_nodes), {"eta"})

    def test_sequential_waves_with_late_dependent(self) -> None:
        self.dag_checked.add_node("alpha", _succeed, None, 0, 0)
        first = self.checked.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(set(first.succeeded_nodes), {"alpha"})
        self.dag_checked.add_node("beta", _succeed, ("alpha",), 0, 0)
        second = self.checked.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(second.total_nodes, 2)


# ==============================================================================
# Compiled fuzz tests
# ==============================================================================


DAGImplFuzzTest = compile_hypothesis_test_case(
    DAGImplStateMachine,
    sut_factory=make_sut,
    name="DAGImplFuzzTest",
)

DAGRunnerImplFuzzTest = compile_hypothesis_test_case(
    DAGRunnerImplStateMachine,
    sut_factory=make_sut,
    name="DAGRunnerImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T16:54:03Z
# LAST_CHANGED: 2026-11-15T16:53:23Z
# CHANGE: Resolve pretense_coverage feedback: add test_cycle_with_downstream_dependent_violation exercising cycle diagnostics when a dependent lies outside the cycle. The scenario registers zeta, eta (dependent on zeta) and alpha (dependent on eta), then adds the back edge eta->zeta so the graph contains the zeta/eta cycle with alpha downstream but outside it, and asserts topological_sort raises contracted CycleError via violating(CycleError).
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T16:54:03Z
# PRETENSE_QA_AUDIT: 2026-11-15T16:53:38Z
# --- END AUTOFAB METADATA ---
