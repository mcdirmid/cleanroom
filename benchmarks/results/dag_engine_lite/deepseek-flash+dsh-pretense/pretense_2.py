# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
    FakeDagEngineLite,
    make_dag_engine_lite_fakes,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import FailurePolicy, NodeState
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

def _wave_precedes(state: DagEngineLiteState, first: str, second: str) -> bool:
    """Returns whether the first node is scheduled before the second node."""
    first_priority = state.nodes[first].priority
    second_priority = state.nodes[second].priority
    if first_priority != second_priority:
        return first_priority > second_priority
    return first < second


class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for the DAG engine, scheduler, and runner."""

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        assert node_id in self.state.nodes
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert downstream_id in self.state.downstream.get(upstream_id, set())
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        assert set(ret) == set(self.state.nodes)
        positions = {node_id: index for index, node_id in enumerate(ret)}
        assert all(
            positions[dependency] < positions[node_id]
            for node_id in ret
            for dependency in self.state.upstream.get(node_id, set())
        )
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        assert ret == {
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)
        }
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        path, weight = ret
        assert all(node_id in self.state.nodes for node_id in path)
        assert all(
            path[index] in self.state.upstream.get(path[index + 1], set())
            for index in range(len(path) - 1)
        )
        assert isinstance(weight, (int, float))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        assert set(ret) <= set(self.state.nodes)
        assert all(
            _wave_precedes(self.state, ret[index], ret[index + 1])
            for index in range(len(ret) - 1)
        )
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        assert self.state.states.get(node_id) is not None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        assert self.state.states.get(node_id) is not None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert self.state.states.get(node_id) is not None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        if not self.state.nodes:
            assert ret is True
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        assert set(ret) == set(self.state.nodes)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        nodes = set(self.state.nodes)
        assert ret.total_nodes == len(nodes)
        assert set(ret.succeeded_nodes) <= nodes
        assert set(ret.failed_nodes) <= nodes
        assert set(ret.skipped_nodes) <= nodes
        assert set(ret.cancelled_nodes) <= nodes
        assert set(ret.results) <= nodes
        assert set(ret.critical_path) <= nodes
        assert ret.wall_clock_seconds >= 0.0
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the DAG contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.wavescheduler,
                DAGRunner: self.dagrunner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_graph_queries_and_ordering(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 5, 1)
        dag.add_node("c", lambda: 3, ["b"], 1, 0)
        dag.has_node("a")
        dag.has_node("missing")
        dag.get_node("b")
        dag.get_dependencies("b")
        dag.get_dependents("a")
        dag.all_nodes()
        dag.find_roots()
        dag.find_leaves()
        dag.validate()
        dag.topological_sort()
        dag.compute_critical_path(None)
        dag.compute_critical_path({"a": 2.0, "b": 3.0, "c": 1.0})

    def test_add_edge_and_remove_node(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, None, 0, 0)
        dag.add_node("c", lambda: 3, None, 0, 0)
        dag.add_edge("a", "b")
        dag.add_edge("b", "c")
        dag.get_dependencies("c")
        dag.get_dependents("a")
        dag.topological_sort()
        dag.remove_node("b")
        dag.get_dependencies("c")
        dag.get_dependents("a")
        dag.all_nodes()
        dag.find_roots()
        dag.compute_critical_path(None)

    def test_remove_all_nodes(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.remove_node("a")
        dag.get_dependencies("b")
        dag.remove_node("b")
        dag.all_nodes()
        self.checked_wavescheduler.is_finished()

    def test_wave_scheduling_success_flow(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 3, 0)
        dag.add_node("c", lambda: 3, ["a"], 1, 0)
        scheduler.next_wave()
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        scheduler.next_wave()
        scheduler.get_state("b")
        scheduler.get_all_states()
        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")
        scheduler.mark_running("c")
        scheduler.mark_succeeded("c")
        scheduler.is_finished()

    def test_scheduler_fail_fast_policy(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.add_node("c", lambda: 3, ["b"], 0, 0)
        scheduler.next_wave()
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        scheduler.get_all_states()
        scheduler.is_finished()

    def test_scheduler_skip_downstream_policy(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.add_node("c", lambda: 3, ["b"], 0, 0)
        dag.add_node("d", lambda: 4, ["a"], 0, 0)
        scheduler.next_wave()
        scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        scheduler.get_all_states()
        scheduler.next_wave()
        scheduler.is_finished()

    def test_scheduler_continue_on_error_policy(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.add_node("x", lambda: 3, None, 0, 0)
        scheduler.next_wave()
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        scheduler.next_wave()
        scheduler.get_all_states()
        scheduler.is_finished()

    def test_runner_executes_graph(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 41, None, 2, 0)
        dag.add_node("b", lambda: 1, ["a"], 1, 1)
        self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_runner_retries_failed_action(self) -> None:
        attempts = {"count": 0}

        def flaky() -> int:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient failure")
            return 7

        self.checked_dag.add_node("a", flaky, None, 0, 2)
        self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_runner_skip_downstream_policy(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 1 / 0, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        self.checked_dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_continue_on_error_policy(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 1 / 0, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.add_node("c", lambda: 3, None, 0, 0)
        self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_empty_graph_operations(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.all_nodes()
        dag.find_roots()
        dag.find_leaves()
        dag.topological_sort()
        dag.validate()
        scheduler.next_wave()
        scheduler.get_all_states()
        scheduler.is_finished()

    def test_critical_path_empty_graph(self) -> None:
        self.checked_dag.compute_critical_path(None)

    def test_scheduler_states_after_node_removed(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        scheduler.next_wave()
        scheduler.get_state("a")
        scheduler.get_all_states()
        dag.remove_node("a")
        scheduler.get_all_states()
        scheduler.get_state("b")

    def test_scheduler_skip_downstream_converging_paths(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.add_node("c", lambda: 3, ["a"], 0, 0)
        dag.add_node("d", lambda: 4, ["b", "c"], 0, 0)
        scheduler.next_wave()
        scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        scheduler.get_all_states()
        scheduler.next_wave()
        scheduler.is_finished()

    def test_scheduler_continue_on_error_converging_paths(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        dag.add_node("c", lambda: 3, ["a"], 0, 0)
        dag.add_node("d", lambda: 4, ["b", "c"], 0, 0)
        dag.add_node("x", lambda: 5, None, 0, 0)
        scheduler.next_wave()
        scheduler.mark_running("a")
        scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        scheduler.get_all_states()
        scheduler.next_wave()
        scheduler.mark_running("x")
        scheduler.mark_succeeded("x")
        scheduler.is_finished()

    def test_scheduler_success_promotes_only_pending_dependents(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, None, 0, 0)
        dag.add_node("c", lambda: 3, ["a", "b"], 0, 0)
        dag.add_node("d", lambda: 4, ["b"], 0, 0)
        dag.add_node("e", lambda: 5, ["a"], 0, 0)
        scheduler.next_wave()
        scheduler.mark_running("b")
        scheduler.mark_succeeded("b")
        scheduler.mark_succeeded("c")
        scheduler.mark_running("a")
        scheduler.mark_succeeded("a")
        scheduler.get_state("c")
        scheduler.get_all_states()
        scheduler.next_wave()

    def test_scheduler_finished_when_blocked_by_failed_dependency(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        scheduler.get_all_states()
        scheduler.is_finished()

    def test_scheduler_running_node_blocks_ready_wave(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 2, ["a"], 0, 0)
        scheduler.next_wave()
        scheduler.mark_running("a")
        scheduler.is_finished()
        scheduler.get_all_states()

    def test_scheduler_finished_in_flight_with_non_blocking_ancestors(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("root", lambda: 1, None, 0, 0)
        dag.add_node("left", lambda: 2, ["root"], 0, 0)
        dag.add_node("right", lambda: 3, ["root"], 0, 0)
        dag.add_node("leaf", lambda: 4, ["left", "right"], 0, 0)
        dag.add_node("deep", lambda: 5, ["leaf"], 0, 0)
        scheduler.next_wave()
        scheduler.mark_running("root")
        scheduler.is_finished()
        scheduler.next_wave()
        scheduler.get_state("deep")
        scheduler.get_all_states()

    def test_scheduler_finished_transitively_blocked_by_failed_ancestor(self) -> None:
        dag = self.checked_dag
        scheduler = self.checked_wavescheduler
        dag.add_node("x", lambda: 1, None, 0, 0)
        scheduler.mark_failed("x", FailurePolicy.FAIL_FAST)
        dag.add_node("y1", lambda: 2, ["x"], 0, 0)
        dag.add_node("y2", lambda: 3, ["x"], 0, 0)
        dag.add_node("z", lambda: 4, ["y1", "y2"], 0, 0)
        dag.add_node("deep", lambda: 5, ["z"], 0, 0)
        scheduler.is_finished()
        scheduler.next_wave()
        scheduler.get_all_states()
        scheduler.get_state("deep")

    def test_runner_fail_fast_halts_after_failure(self) -> None:
        dag = self.checked_dag
        dag.add_node("a", lambda: 1, None, 0, 0)
        dag.add_node("b", lambda: 1 / 0, ["a"], 0, 0)
        dag.add_node("c", lambda: 3, ["b"], 0, 0)
        dag.add_node("d", lambda: 4, ["b"], 0, 0)
        self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for DagEngineLite state machine testing."""

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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T04:32:44Z
# LAST_CHANGED: 2026-11-03T04:32:15Z
# CHANGE: Add in-flight finished-detection scenarios closing the transitive-upstream coverage gap: (1) a RUNNING root with a deep chain and converging left/right dependents so is_finished evaluates non-succeeded, non-blocking ancestors transitively through converging paths; (2) a failed ancestor x added-after-failure with converging y1/y2 branches feeding z and deep, so transitively blocked unexecuted nodes are detected and no ready wave remains. Both drive is_finished/next_wave/get_state/get_all_states during an in-progress run.
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T04:32:44Z
# PRETENSE_QA_AUDIT: 2026-11-03T04:32:33Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    NodeState,
    WaveScheduler,
)


_TERMINAL_STATES: frozenset[NodeState] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)

_FAILURE_STATES: frozenset[NodeState] = frozenset(
    {
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live naturally inside the single
# transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (validated on real calls).
# Use Domain.type(T) or open domains; use preferred=[...] to cluster fuzz inputs.


@dataclass
class DagEngineLiteState:
    """Canonical model state for the DAG graph and wave scheduler operations."""

    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    dependencies_resolved: bool = True
    acyclic: bool = True
    initialized: bool = True


def _dependencies_resolved(state: DagEngineLiteState) -> bool:
    """Returns whether every referenced dependency is a registered node."""
    return all(
        dependency in state.nodes
        for node_id in state.nodes
        for dependency in state.upstream.get(node_id, set())
    )


def _graph_is_acyclic(state: DagEngineLiteState) -> bool:
    """Returns whether the registered node graph contains no directed cycle."""
    indegree: Dict[str, int] = {
        node_id: sum(
            1
            for dependency in state.upstream.get(node_id, set())
            if dependency in state.nodes
        )
        for node_id in state.nodes
    }
    ready: List[str] = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for dependent in state.downstream.get(current, set()):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
    return visited == len(state.nodes)


def _refresh_graph_flags(state: DagEngineLiteState) -> None:
    """Recomputes cached graph validity flags after a structural mutation."""
    state.dependencies_resolved = _dependencies_resolved(state)
    state.acyclic = _graph_is_acyclic(state)


def _wave_sort_key(state: DagEngineLiteState, node_id: str) -> Tuple[int, str]:
    """Orders candidate nodes by priority descending, then node_id ascending."""
    return (-state.nodes[node_id].priority, node_id)


def _sync_scheduler_state(state: DagEngineLiteState) -> None:
    """Discovers registered nodes, initializing roots READY and others PENDING."""
    for node_id in state.nodes:
        if node_id not in state.states:
            state.states[node_id] = (
                NodeState.READY
                if not state.upstream.get(node_id)
                else NodeState.PENDING
            )
    for node_id in list(state.states):
        if node_id not in state.nodes:
            del state.states[node_id]


def _ready_wave(state: DagEngineLiteState) -> List[str]:
    """Returns READY nodes whose upstream dependencies all SUCCEEDED, ordered."""
    candidates = [
        node_id
        for node_id in state.nodes
        if state.states.get(node_id) is NodeState.READY
        and all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.upstream.get(node_id, set())
        )
    ]
    return sorted(candidates, key=lambda node_id: _wave_sort_key(state, node_id))


def _promote_dependents(state: DagEngineLiteState, node_id: str) -> None:
    """Promotes PENDING dependents to READY once all upstream nodes succeeded."""
    for dependent in state.downstream.get(node_id, set()):
        if dependent not in state.nodes:
            continue
        if state.states.get(dependent) is not NodeState.PENDING:
            continue
        if all(
            state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in state.upstream.get(dependent, set())
        ):
            state.states[dependent] = NodeState.READY


def _transitive_dependents(state: DagEngineLiteState, node_id: str) -> Set[str]:
    """Collects every transitive downstream dependent of a node identifier."""
    found: Set[str] = set()
    frontier: List[str] = list(state.downstream.get(node_id, set()))
    while frontier:
        current = frontier.pop()
        if current in found:
            continue
        found.add(current)
        frontier.extend(state.downstream.get(current, set()))
    return found


def _apply_failure_policy(
    state: DagEngineLiteState,
    node_id: str,
    failure_policy: FailurePolicy,
) -> None:
    """Marks a node FAILED and applies the contracted failure policy."""
    state.states[node_id] = NodeState.FAILED
    if failure_policy is FailurePolicy.FAIL_FAST:
        for other in list(state.states):
            if state.states[other] not in _TERMINAL_STATES:
                state.states[other] = NodeState.CANCELLED
        return
    for dependent in _transitive_dependents(state, node_id):
        if dependent not in state.nodes:
            continue
        if state.states.get(dependent) not in _TERMINAL_STATES:
            state.states[dependent] = NodeState.SKIPPED


def _topological_order(state: DagEngineLiteState) -> List[str]:
    """Computes the deterministic priority-ordered topological ordering."""
    indegree: Dict[str, int] = {
        node_id: len(state.upstream.get(node_id, set())) for node_id in state.nodes
    }
    ready: List[str] = [
        node_id for node_id, degree in indegree.items() if degree == 0
    ]
    ready.sort(key=lambda node_id: _wave_sort_key(state, node_id))
    order: List[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for dependent in sorted(state.downstream.get(current, set())):
            if dependent in indegree:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        ready.sort(key=lambda node_id: _wave_sort_key(state, node_id))
    return order


def _critical_path(
    state: DagEngineLiteState,
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path through the graph."""
    order = _topological_order(state)
    if not order:
        return [], 0.0
    durations = estimated_durations or {}
    earliest: Dict[str, float] = {}
    for node_id in order:
        predecessors = [
            earliest[dependency]
            for dependency in state.upstream.get(node_id, set())
            if dependency in earliest
        ]
        base = max(predecessors) if predecessors else 0.0
        earliest[node_id] = base + float(durations.get(node_id, 1.0))
    terminal = max(order, key=lambda node_id: earliest[node_id])
    path: List[str] = [terminal]
    while state.upstream.get(path[-1]):
        predecessors = [
            dependency
            for dependency in state.upstream.get(path[-1], set())
            if dependency in earliest
        ]
        if not predecessors:
            break
        path.append(max(predecessors, key=lambda node_id: earliest[node_id]))
    path.reverse()
    return path, earliest[terminal]


def _scheduler_is_finished(state: DagEngineLiteState) -> bool:
    """Determines whether no further progress is possible over registered nodes."""
    if not state.nodes:
        return True
    if all(state.states.get(node_id) in _TERMINAL_STATES for node_id in state.nodes):
        return True
    if _ready_wave(state):
        return False
    return any(
        state.states.get(node_id) not in _TERMINAL_STATES
        and any(
            state.states.get(dependency) in _FAILURE_STATES
            for dependency in state.upstream.get(node_id, set())
        )
        for node_id in state.nodes
    )


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense state machine for the DAG engine, scheduler, and runner."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

    # ------------------------------------------------------------------
    # DAG graph structure
    # ------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.not_in(self.state.nodes), preferred=["a", "b", "c"])
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])))
        require_arg(priority, Domain.type(int))
        require_arg(retries, Domain.type(int))
        dependency_set = frozenset(dependencies or ())
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        _refresh_graph_flags(self.state)
        ret = make_return_value()
        assert node_id in self.state.nodes
        assert set(self.state.upstream[node_id]) == set(dependency_set)
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(upstream_id, Domain.in_set(self.state.nodes))
        require_arg(downstream_id, Domain.in_set(self.state.nodes))
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        _refresh_graph_flags(self.state)
        ret = make_return_value()
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        for dependency in list(self.state.upstream.get(node_id, set())):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in list(self.state.downstream.get(node_id, set())):
            self.state.upstream.get(dependent, set()).discard(node_id)
        del self.state.nodes[node_id]
        del self.state.upstream[node_id]
        self.state.downstream.pop(node_id, None)
        self.state.states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        _refresh_graph_flags(self.state)
        ret = make_return_value()
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["a", "b", "c"])
        ret: bool = make_return_value(node_id in self.state.nodes)
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret: NodeDefinition[Any] = make_return_value(self.state.nodes[node_id])
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret: Set[str] = make_return_value(set(self.state.upstream.get(node_id, set())))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret: Set[str] = make_return_value(set(self.state.downstream.get(node_id, set())))
        assert ret <= set(self.state.nodes)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = make_return_value(set(self.state.nodes))
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        require(self.state.dependencies_resolved)
        require(self.state.acyclic)
        ret = make_return_value()
        assert self.state.dependencies_resolved
        assert self.state.acyclic
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        require(self.state.dependencies_resolved)
        require(self.state.acyclic)
        order = _topological_order(self.state)
        ret: List[str] = make_return_value(order)
        assert set(ret) == set(self.state.nodes)
        positions = {node_id: index for index, node_id in enumerate(ret)}
        assert all(
            positions[dependency] < positions[node_id]
            for node_id in ret
            for dependency in self.state.upstream.get(node_id, set())
        )
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = make_return_value(
            {node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id)}
        )
        assert ret <= set(self.state.nodes)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = make_return_value(
            {
                node_id
                for node_id in self.state.nodes
                if not self.state.downstream.get(node_id)
            }
        )
        assert ret <= set(self.state.nodes)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require(self.state.dependencies_resolved)
        require(self.state.acyclic)
        require_arg(
            estimated_durations,
            Domain.optional(Domain.type(Mapping[str, float])),
        )
        path, weight = _critical_path(self.state, estimated_durations)
        ret: Tuple[List[str], float] = make_return_value((path, weight))
        assert all(node_id in self.state.nodes for node_id in ret[0])
        assert isinstance(ret[1], float)
        return ret

    # ------------------------------------------------------------------
    # Wave scheduler
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        _sync_scheduler_state(self.state)
        wave = _ready_wave(self.state)
        ret: List[str] = make_return_value(wave)
        assert all(node_id in self.state.nodes for node_id in ret)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.state.states[node_id] = NodeState.RUNNING
        ret = make_return_value()
        assert self.state.states[node_id] is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.state.states[node_id] = NodeState.SUCCEEDED
        _promote_dependents(self.state, node_id)
        ret = make_return_value()
        assert self.state.states[node_id] is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        _apply_failure_policy(self.state, node_id, failure_policy)
        ret = make_return_value()
        assert self.state.states.get(node_id) is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        _sync_scheduler_state(self.state)
        finished = _scheduler_is_finished(self.state)
        ret: bool = make_return_value(finished)
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        _sync_scheduler_state(self.state)
        ret: NodeState = make_return_value(self.state.states[node_id])
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        _sync_scheduler_state(self.state)
        snapshot = {
            node_id: self.state.states[node_id] for node_id in self.state.nodes
        }
        ret: Mapping[str, NodeState] = make_return_value(snapshot)
        assert set(ret) == set(self.state.nodes)
        return ret

    # ------------------------------------------------------------------
    # Sequential runner
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require(self.state.dependencies_resolved)
        require(self.state.acyclic)
        require(len(self.state.nodes) > 0)
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        _sync_scheduler_state(self.state)
        wave = _ready_wave(self.state)
        for _ in range(len(self.state.nodes) + 1):
            if not wave:
                break
            for node_id in wave:
                self.state.states[node_id] = NodeState.SUCCEEDED
                self.state.results[node_id] = NodeResult(
                    node_id=node_id,
                    state=NodeState.SUCCEEDED,
                )
                _promote_dependents(self.state, node_id)
            wave = _ready_wave(self.state)
        succeeded = tuple(
            sorted(
                node_id
                for node_id in self.state.nodes
                if self.state.states.get(node_id) is NodeState.SUCCEEDED
            )
        )
        failed = tuple(
            sorted(
                node_id
                for node_id in self.state.nodes
                if self.state.states.get(node_id) is NodeState.FAILED
            )
        )
        skipped = tuple(
            sorted(
                node_id
                for node_id in self.state.nodes
                if self.state.states.get(node_id) is NodeState.SKIPPED
            )
        )
        cancelled = tuple(
            sorted(
                node_id
                for node_id in self.state.nodes
                if self.state.states.get(node_id) is NodeState.CANCELLED
            )
        )
        path, _weight = _critical_path(self.state, None)
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=dict(self.state.results),
        )
        ret: DAGRunReport = make_return_value(report)
        assert ret.total_nodes == len(self.state.nodes)
        assert set(ret.succeeded_nodes) <= set(self.state.nodes)
        assert set(ret.failed_nodes) <= set(self.state.nodes)
        assert set(ret.skipped_nodes) <= set(self.state.nodes)
        assert set(ret.cancelled_nodes) <= set(self.state.nodes)
        assert set(ret.critical_path) <= set(self.state.nodes)
        assert set(ret.results) <= set(self.state.nodes)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds state machine state for fake initialization."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake services backed by one shared model state machine."""
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
    return (
        cast(DAG, fake),
        cast(WaveScheduler, fake),
        cast(DAGRunner, fake),
    )


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T04:29:58Z
# LAST_CHANGED: 2026-11-03T04:29:58Z
# CHANGE: Remove non-contract non-empty graph precondition from compute_critical_path so the empty-DAG postcondition (empty path, zero weight) is modelable and reachable during real SUT fuzzing; fake still returns ([], 0.0) and asserts path membership/weight type.
# --- END AUTOFAB METADATA ---
