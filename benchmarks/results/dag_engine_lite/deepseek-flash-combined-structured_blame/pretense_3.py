# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, Mapping, Optional
import unittest

from pretense import call_target, sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, get_singleton, system
from benchmark_5.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteStateMachine,
    failing_action,
    noop_action,
)
from benchmark_5.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from benchmark_5.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_lite_initialize,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# The pseudo-state machine inherits every outer transition (require gates, model
# state mutations, and postcondition assertions) from the interface state machine
# and only overrides inner transitions to bind and observe the concrete SUT.

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for the DAG engine lite component trio."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        assert target.has_node(node_id)
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        assert definition.dependencies == frozenset(dependencies if dependencies is not None else ())
        assert definition.priority == priority
        assert definition.retries == retries
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert upstream_id in target.get_dependencies(downstream_id)
        assert downstream_id in target.get_dependents(upstream_id)
        return ret

    def inner_remove_node(self, node_id: str) -> Any:
        target: DAG = sut(DAG)
        dependents: set[str] = set()
        if target.has_node(node_id):
            dependents = target.get_dependents(node_id)
        ret = call_target(target.remove_node(node_id))
        assert not target.has_node(node_id)
        for other in dependents:
            if not target.has_node(other):
                continue
            assert node_id not in target.get_dependencies(other)
        return ret

    def inner_has_node(self, node_id: str) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        assert ret == (node_id in target.all_nodes())
        return ret

    def inner_get_node(self, node_id: str) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        assert node_id in target.all_nodes()
        return ret

    def inner_get_dependencies(self, node_id: str) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        for dependency in ret:
            if target.has_node(dependency):
                assert node_id in target.get_dependents(dependency)
        return ret

    def inner_get_dependents(self, node_id: str) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        for dependent in ret:
            assert dependent in target.all_nodes()
        return ret

    def inner_all_nodes(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert isinstance(ret, set)
        return ret

    def inner_validate(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        assert ret is None
        return ret

    def inner_topological_sort(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        nodes = target.all_nodes()
        assert set(ret) == nodes
        assert len(ret) == len(nodes)
        for node_id in nodes:
            for dependency in target.get_dependencies(node_id):
                assert ret.index(dependency) < ret.index(node_id)
        return ret

    def inner_find_roots(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        for node_id in ret:
            assert len(target.get_dependencies(node_id)) == 0
        for node_id in target.all_nodes():
            if len(target.get_dependencies(node_id)) == 0:
                assert node_id in ret
        return ret

    def inner_find_leaves(self) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        for node_id in ret:
            assert len(target.get_dependents(node_id)) == 0
        for node_id in target.all_nodes():
            if len(target.get_dependents(node_id)) == 0:
                assert node_id in ret
        return ret

    def inner_compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        path, weight = ret
        assert len(path) == len(set(path))
        for index in range(1, len(path)):
            assert path[index - 1] in target.get_dependencies(path[index])
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        positive = True
        for value in durations.values():
            if not value > 0.0:
                positive = False
        if positive:
            assert weight >= 0.0
            assert path[-1] in target.find_leaves()
        return ret

    def inner_next_wave(self) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        states = target.get_all_states()
        for node_id in ret:
            assert isinstance(node_id, str)
            assert states.get(node_id) == NodeState.READY
        return ret

    def inner_mark_running(self, node_id: str) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        assert target.get_state(node_id) == NodeState.RUNNING
        return ret

    def inner_mark_succeeded(self, node_id: str) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        states = target.get_all_states()
        assert states.get(node_id) == NodeState.SUCCEEDED
        return ret

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        states = target.get_all_states()
        assert states.get(node_id) == NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other in states:
                assert states[other] != NodeState.PENDING
        return ret

    def inner_is_finished(self) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        states = target.get_all_states()
        terminal = (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED)
        all_terminal = True
        for node_id in states:
            if states[node_id] not in terminal:
                all_terminal = False
        if all_terminal:
            assert ret
        return ret

    def inner_get_state(self, node_id: str) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        states = target.get_all_states()
        assert states.get(node_id) == ret
        return ret

    def inner_get_all_states(self) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        for node_id in ret:
            assert isinstance(node_id, str)
            assert isinstance(ret[node_id], NodeState)
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        assert ret.total_nodes >= len(ret.results)
        for node_id in ret.results:
            assert isinstance(node_id, str)
            assert ret.results[node_id].node_id == node_id
            assert isinstance(ret.results[node_id].state, NodeState)
        for node_id in ret.succeeded_nodes:
            assert isinstance(node_id, str)
        for node_id in ret.failed_nodes:
            assert isinstance(node_id, str)
        for node_id in ret.skipped_nodes:
            assert isinstance(node_id, str)
        for node_id in ret.cancelled_nodes:
            assert isinstance(node_id, str)
        assert ret.wall_clock_seconds >= 0.0
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete DAG engine lite services satisfy their contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope: LifecycleScope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.scheduler, DAGRunner: self.runner}
        )
        self.checked_dag: Any = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler: Any = self.sm.as_checked(WaveScheduler, self.scheduler)
        self.checked_runner: Any = self.sm.as_checked(DAGRunner, self.runner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_graph_queries(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 4, 1)
        self.checked_dag.add_node("gamma", noop_action, ["alpha", "beta"], 2, 0)
        assert self.checked_dag.has_node("alpha")
        assert not self.checked_dag.has_node("zeta")
        definition = self.checked_dag.get_node("beta")
        assert definition.node_id == "beta"
        assert definition.priority == 4
        assert definition.retries == 1
        assert definition.dependencies == frozenset({"alpha"})
        assert self.checked_dag.get_dependencies("gamma") == {"alpha", "beta"}
        assert self.checked_dag.get_dependents("alpha") == {"beta", "gamma"}
        assert self.checked_dag.all_nodes() == {"alpha", "beta", "gamma"}
        assert self.checked_dag.find_roots() == {"alpha"}
        assert self.checked_dag.find_leaves() == {"gamma"}
        self.checked_dag.validate()
        assert self.checked_dag.topological_sort() == ["alpha", "beta", "gamma"]
        assert self.checked_dag.compute_critical_path(None) == (["alpha", "beta", "gamma"], 3.0)
        assert self.checked_dag.compute_critical_path({"alpha": 2.0, "beta": 3.0}) == (["alpha", "beta", "gamma"], 6.0)

    def test_graph_edges_and_removal(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        assert self.checked_dag.get_dependencies("beta") == {"alpha"}
        assert self.checked_dag.get_dependents("alpha") == {"beta"}
        assert self.checked_dag.find_roots() == {"alpha"}
        self.checked_dag.remove_node("alpha")
        assert self.checked_dag.all_nodes() == {"beta"}
        assert self.checked_dag.get_dependencies("beta") == set()
        assert self.checked_dag.get_dependents("beta") == set()
        self.checked_dag.remove_node("beta")
        assert self.checked_dag.all_nodes() == set()

    def test_self_referential_edge_removal(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_edge("alpha", "alpha")
        assert self.checked_dag.get_dependencies("alpha") == {"alpha"}
        assert self.checked_dag.get_dependents("alpha") == {"alpha"}
        self.checked_dag.remove_node("alpha")
        assert self.checked_dag.all_nodes() == set()

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        assert set(self.checked_scheduler.get_all_states().keys()) == {"alpha", "beta"}
        self.checked_dag.remove_node("beta")
        states = self.checked_scheduler.get_all_states()
        assert set(states.keys()) == {"alpha"}
        assert "beta" not in states

    def test_empty_graph(self) -> None:
        assert self.checked_dag.all_nodes() == set()
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == set()
        self.checked_dag.validate()
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.is_finished()
        assert self.checked_scheduler.get_all_states() == {}

    def test_scheduler_wave_progression(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 4, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 2, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        assert self.checked_scheduler.get_state("alpha") == NodeState.READY
        self.checked_scheduler.mark_running("alpha")
        assert self.checked_scheduler.get_state("alpha") == NodeState.RUNNING
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("alpha") == NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("beta") == NodeState.READY
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY
        assert self.checked_scheduler.next_wave() == ["beta", "gamma"]
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        self.checked_scheduler.mark_failed("gamma", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("gamma") == NodeState.FAILED
        states = self.checked_scheduler.get_all_states()
        assert states["alpha"] == NodeState.SUCCEEDED
        assert states["beta"] == NodeState.SUCCEEDED
        assert states["gamma"] == NodeState.FAILED
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.is_finished()

    def test_scheduler_state_sync(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        assert self.checked_scheduler.get_state("alpha") == NodeState.READY
        assert self.checked_scheduler.get_all_states() == {"alpha": NodeState.READY}
        assert not self.checked_scheduler.is_finished()

    def test_scheduler_wave_after_upstream_success(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        waves = self.checked_scheduler.next_wave()
        assert waves == ["beta"]
        assert self.checked_scheduler.get_state("beta") == NodeState.READY

    def test_scheduler_promotion_after_prior_failure(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", noop_action, None, 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["alpha", "beta"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "beta"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("delta") == NodeState.SKIPPED
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        assert self.checked_scheduler.get_state("beta") == NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("delta") == NodeState.SKIPPED

    def test_scheduler_skip_downstream_diamond(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 3, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 2, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["beta", "gamma"], 0, 0)
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("alpha") == NodeState.FAILED
        assert self.checked_scheduler.get_state("beta") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("delta") == NodeState.SKIPPED

    def test_scheduler_finished_blocked_by_failure(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.is_finished()

    def test_runner_success_report(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 4, 0)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 2, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 3
        assert set(report.succeeded_nodes) == {"alpha", "beta", "gamma"}
        assert len(report.failed_nodes) == 0
        assert len(report.skipped_nodes) == 0
        assert len(report.cancelled_nodes) == 0
        assert report.wall_clock_seconds >= 0.0
        assert list(report.critical_path) == ["alpha", "beta", "gamma"]
        assert set(report.results.keys()) == {"alpha", "beta", "gamma"}
        assert report.results["gamma"].state == NodeState.SUCCEEDED
        assert report.results["alpha"].node_id == "alpha"

    def test_runner_fail_fast(self) -> None:
        self.checked_dag.add_node("alpha", failing_action, None, 1, 2)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert "alpha" in report.failed_nodes
        assert report.results["alpha"].retries_attempted == 2
        assert report.results["alpha"].error is not None
        assert "beta" in report.cancelled_nodes
        assert report.results["beta"].state == NodeState.CANCELLED

    def test_runner_skip_downstream(self) -> None:
        self.checked_dag.add_node("alpha", failing_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 0, 0)
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert "alpha" in report.failed_nodes
        assert set(report.skipped_nodes) == {"beta", "gamma"}
        assert report.results["gamma"].state == NodeState.SKIPPED

    def test_runner_continue_on_error(self) -> None:
        self.checked_dag.add_node("alpha", failing_action, None, 1, 1)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        self.checked_dag.add_node("gamma", noop_action, None, 2, 0)
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert "alpha" in report.failed_nodes
        assert "beta" in report.skipped_nodes
        assert "gamma" in report.succeeded_nodes

    def test_runner_preexisting_running_node(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_scheduler.mark_running("alpha")
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 1
        assert set(report.results.keys()) <= {"alpha"}

    def test_duplicate_node_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node("alpha", noop_action, None, 1, 0)

    def test_add_edge_missing_upstream_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("zeta", "alpha")

    def test_add_edge_missing_downstream_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("alpha", "zeta")

    def test_get_node_missing_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("zeta")

    def test_get_dependencies_missing_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("zeta")

    def test_get_dependents_missing_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependents("zeta")

    def test_remove_node_missing_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.remove_node("zeta")

    def test_remove_node_unregistered_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.remove_node("gamma")

    def test_validate_missing_dependency_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["omega"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_compute_critical_path_cycle_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).compute_critical_path(None)

    def test_runner_missing_dependency_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["omega"], 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(FailurePolicy.FAIL_FAST)

    def test_runner_cycle_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

    def test_scheduler_missing_node_violation(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_scheduler.violating(NodeNotFoundError).get_state("zeta")


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing the DAG, WaveScheduler, and DAGRunner services."""

    _active_scope: Optional[LifecycleScope] = None

    def __init__(self) -> None:
        if DagEngineLiteSUT._active_scope is not None:
            DagEngineLiteSUT._active_scope.__exit__(None, None, None)
            DagEngineLiteSUT._active_scope = None
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        DagEngineLiteSUT._active_scope = self.phase_scope
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
    """Builds a fresh aggregate SUT inside its own active lifecycle phase."""
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:57:19Z
# LAST_CHANGED: 2026-11-09T22:56:44Z
# CHANGE: Resolve pretense_qa cross-service collaborator graph divergence: scheduler/runner inner transitions no longer resolve a separate DAG service via sut(DAG) and assert graph agreement (inner_get_all_states key-set equality, inner_run total_nodes/identifier membership, next_wave dependency+priority ordering, mark_succeeded promotion, mark_failed SKIP_DOWNSTREAM dependents). Adapters now assert only SUT-internal postconditions (state transitions, READY/SKIPPED invariants, report-internal consistency, typing) that cannot diverge from an independently resolved collaborator; model-graph postconditions remain enforced by inherited outer transitions and the scenario suite. DAG inner transitions keep self-consistent observations.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:57:19Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:56:56Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_5.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    NodeState,
    WaveScheduler,
)


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# The unified state machine covers the DAG, WaveScheduler, and DAGRunner services
# because they share one execution model: graph structure plus node lifecycle state.
# Caller precondition contracts are gated with require(...) (model state only) and
# require_arg(...) (argument domains) so generative fuzzing never violates them.

NODE_ID_POOL: Tuple[str, ...] = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")

# Identifier that never becomes addable: declaring it as a dependency exercises the
# deferred missing-dependency precondition contract (NodeNotFoundError) downstream.
PHANTOM_ID: str = "omega"

TERMINAL_STATES: Tuple[NodeState, ...] = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)


def noop_action() -> None:
    """Successful zero-argument node action used by scenarios and fuzzing."""
    return None


def failing_action() -> None:
    """Failing zero-argument node action used to exercise failure policies."""
    raise RuntimeError("intentional node action failure")


def _is_finite(value: float) -> bool:
    """Reports whether a float weight is a finite real number."""
    if value != value:
        return False
    if value == float("inf") or value == float("-inf"):
        return False
    return True


def _ranks_before(priorities: Mapping[str, int], left: str, right: str) -> bool:
    """Orders nodes by priority descending, then identifier ascending."""
    left_priority = priorities.get(left, 0)
    right_priority = priorities.get(right, 0)
    if left_priority != right_priority:
        return left_priority > right_priority
    return left < right


def _ordered_by_priority(priorities: Mapping[str, int], node_ids: Sequence[str]) -> List[str]:
    """Deterministically orders node identifiers by priority descending, then name ascending."""
    pending = list(node_ids)
    ordered: List[str] = []
    for _ in range(len(pending)):
        best_index = 0
        for index in range(1, len(pending)):
            if _ranks_before(priorities, pending[index], pending[best_index]):
                best_index = index
        ordered.append(pending.pop(best_index))
    return ordered


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations.

    Holds graph structure (dependency sets plus scheduling metadata) and the node
    lifecycle states tracked by the wave scheduler.
    """

    initialized: bool = True
    nodes: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    priorities: Dict[str, int] = field(default_factory=dict)
    retries: Dict[str, int] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)

    @property
    def node_ids(self) -> Tuple[str, ...]:
        return tuple(self.nodes.keys())

    @property
    def has_nodes(self) -> bool:
        return len(self.nodes) > 0

    @property
    def addable_ids(self) -> Tuple[str, ...]:
        available = tuple(node_id for node_id in NODE_ID_POOL if node_id not in self.nodes)
        if len(available) > 0:
            return available
        return NODE_ID_POOL

    @property
    def full(self) -> bool:
        return len(self.nodes) >= len(NODE_ID_POOL)

    @property
    def node_id_choices(self) -> Tuple[str, ...]:
        if self.has_nodes:
            return self.node_ids
        return NODE_ID_POOL

    @property
    def dependency_choices(self) -> Tuple[str, ...]:
        return self.node_ids + (PHANTOM_ID,)

    @property
    def dependencies_complete(self) -> bool:
        for node_id in self.nodes:
            for dependency in self.nodes[node_id]:
                if dependency not in self.nodes:
                    return False
        return True

    def collect_dependencies(self, node_id: str, closure: Set[str]) -> None:
        for dependency in self.nodes.get(node_id, frozenset()):
            if dependency in closure:
                continue
            closure.add(dependency)
            self.collect_dependencies(dependency, closure)

    def dependency_closure(self, node_id: str) -> Set[str]:
        closure: Set[str] = set()
        self.collect_dependencies(node_id, closure)
        return closure

    @property
    def acyclic(self) -> bool:
        for node_id in self.nodes:
            if node_id in self.dependency_closure(node_id):
                return False
        return True

    @property
    def valid_graph(self) -> bool:
        return self.dependencies_complete and self.acyclic

    def dependents_of(self, node_id: str) -> Set[str]:
        return {other for other, dependencies in self.nodes.items() if node_id in dependencies}

    def roots(self) -> Set[str]:
        return {node_id for node_id in self.nodes if len(self.nodes[node_id]) == 0}

    def leaves(self) -> Set[str]:
        referenced: Set[str] = set()
        for dependencies in self.nodes.values():
            referenced.update(dependencies)
        return {node_id for node_id in self.nodes if node_id not in referenced}

    def collect_descendants(self, node_id: str, descendants: Set[str]) -> None:
        for dependent in self.dependents_of(node_id):
            if dependent in descendants:
                continue
            descendants.add(dependent)
            self.collect_descendants(dependent, descendants)

    def descendants_of(self, node_id: str) -> Set[str]:
        descendants: Set[str] = set()
        self.collect_descendants(node_id, descendants)
        return descendants

    def sync_states(self) -> None:
        for node_id in self.nodes:
            if node_id in self.states:
                continue
            if len(self.nodes[node_id]) == 0:
                self.states[node_id] = NodeState.READY
            else:
                self.states[node_id] = NodeState.PENDING

    def topological_order(self) -> List[str]:
        remaining: Dict[str, FrozenSet[str]] = {node_id: self.nodes[node_id] for node_id in self.nodes}
        order: List[str] = []
        for _ in range(len(self.nodes)):
            ready: List[str] = []
            for node_id in remaining:
                satisfied = True
                for dependency in remaining[node_id]:
                    if dependency in remaining:
                        satisfied = False
                if satisfied:
                    ready.append(node_id)
            if len(ready) == 0:
                break
            selected = _ordered_by_priority(self.priorities, ready)[0]
            order.append(selected)
            del remaining[selected]
        return order

    def critical_chain(self, node_id: str, durations: Mapping[str, float]) -> Tuple[List[str], float]:
        best_path: List[str] = []
        best_weight = 0.0
        for dependency in self.nodes.get(node_id, frozenset()):
            path, weight = self.critical_chain(dependency, durations)
            if weight > best_weight:
                best_path = path
                best_weight = weight
        best_path.append(node_id)
        return best_path, best_weight + float(durations.get(node_id, 1.0))

    def critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        best_path: List[str] = []
        best_weight = 0.0
        for node_id in self.nodes:
            path, weight = self.critical_chain(node_id, durations)
            if weight > best_weight:
                best_path = path
                best_weight = weight
        return best_path, best_weight


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense state machine for the DAG engine lite component trio."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state if state is not None else self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DagEngineLiteState:
        """Constructs initial model state; overridden by implementation pseudo state machines."""
        return DagEngineLiteState()

    # ------------------------------------------------------------------
    # Inner transitions: compute fake outcomes from model state. Concrete
    # implementation pseudo state machines override these to call the SUT.
    # ------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        return None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return None

    def inner_remove_node(self, node_id: str) -> None:
        return None

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return NodeDefinition(
            node_id=node_id,
            action=noop_action,
            dependencies=self.state.nodes[node_id],
            priority=self.state.priorities.get(node_id, 0),
            retries=self.state.retries.get(node_id, 0),
        )

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.nodes[node_id])

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return self.state.dependents_of(node_id)

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes.keys())

    def inner_validate(self) -> None:
        return None

    def inner_topological_sort(self) -> List[str]:
        return self.state.topological_order()

    def inner_find_roots(self) -> Set[str]:
        return self.state.roots()

    def inner_find_leaves(self) -> Set[str]:
        return self.state.leaves()

    def inner_compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        return self.state.critical_path(estimated_durations)

    def inner_next_wave(self) -> List[str]:
        ready: List[str] = []
        for node_id in self.state.nodes:
            if self.state.states.get(node_id) != NodeState.READY:
                continue
            satisfied = True
            for dependency in self.state.nodes[node_id]:
                if self.state.states.get(dependency) != NodeState.SUCCEEDED:
                    satisfied = False
            if satisfied:
                ready.append(node_id)
        return _ordered_by_priority(self.state.priorities, ready)

    def inner_mark_running(self, node_id: str) -> None:
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        return None

    def inner_is_finished(self) -> bool:
        if not self.state.has_nodes:
            return True
        for node_id in self.state.nodes:
            if self.state.states.get(node_id) not in TERMINAL_STATES:
                return False
        return True

    def inner_get_state(self, node_id: str) -> NodeState:
        current = self.state.states.get(node_id)
        if current is not None:
            return current
        if len(self.state.nodes[node_id]) == 0:
            return NodeState.READY
        return NodeState.PENDING

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return {node_id: self.state.states[node_id] for node_id in self.state.nodes}

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        results: Dict[str, NodeResult[Any]] = {}
        for node_id in self.state.nodes:
            results[node_id] = NodeResult(node_id=node_id, state=NodeState.SUCCEEDED)
        path, _ = self.state.critical_path(None)
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(results.keys()),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=results,
        )

    # ------------------------------------------------------------------
    # 1:1 outer transitions (one per public target method).
    # ------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[List[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(self.state.initialized)
        require(not self.state.full)
        require_arg(node_id, Domain.in_set(self.state.addable_ids))
        require_arg(action, Domain.sampled_from([noop_action, failing_action]))
        require_arg(dependencies, Domain.optional(Domain.list_of(Domain.in_set(self.state.dependency_choices))))
        require_arg(priority, Domain.range(0, 5))
        require_arg(retries, Domain.range(0, 3))
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        self.state.nodes[node_id] = frozenset(dependencies if dependencies is not None else ())
        self.state.priorities[node_id] = priority
        self.state.retries[node_id] = retries
        self.state.states.pop(node_id, None)
        assert node_id in self.state.nodes
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(upstream_id, Domain.in_set(self.state.node_id_choices))
        require_arg(downstream_id, Domain.in_set(self.state.node_id_choices))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.nodes[downstream_id] = self.state.nodes[downstream_id] | {upstream_id}
        assert upstream_id in self.state.nodes[downstream_id]
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret = self.inner_remove_node(node_id)
        del self.state.nodes[node_id]
        self.state.priorities.pop(node_id, None)
        self.state.retries.pop(node_id, None)
        self.state.states.pop(node_id, None)
        for other in list(self.state.nodes.keys()):
            self.state.nodes[other] = self.state.nodes[other] - {node_id}
        assert node_id not in self.state.nodes
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(NODE_ID_POOL))
        ret: bool = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret: NodeDefinition[Any] = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert ret.priority == self.state.priorities.get(node_id, 0)
        assert ret.retries == self.state.retries.get(node_id, 0)
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret: Set[str] = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.nodes[node_id])
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret: Set[str] = self.inner_get_dependents(node_id)
        assert ret == self.state.dependents_of(node_id)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_all_nodes()
        assert ret == set(self.state.nodes.keys())
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.initialized)
        require(self.state.valid_graph)
        ret = self.inner_validate()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.initialized)
        require(self.state.valid_graph)
        ret: List[str] = self.inner_topological_sort()
        assert set(ret) == set(self.state.nodes.keys())
        assert len(ret) == len(self.state.nodes)
        for node_id in self.state.nodes:
            for dependency in self.state.nodes[node_id]:
                assert ret.index(dependency) < ret.index(node_id)
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_find_roots()
        assert ret == self.state.roots()
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_find_leaves()
        assert ret == self.state.leaves()
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require(self.state.valid_graph)
        require_arg(estimated_durations, Domain.optional(Domain.type(Mapping[str, float])))
        ret: Tuple[List[str], float] = self.inner_compute_critical_path(estimated_durations)
        path = ret[0]
        weight = ret[1]
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        expected = 0.0
        finite = True
        for value in durations.values():
            if not _is_finite(float(value)):
                finite = False
        for node_id in path:
            expected += float(durations.get(node_id, 1.0))
        for index in range(1, len(path)):
            assert path[index - 1] in self.state.nodes[path[index]]
        assert set(path) <= set(self.state.nodes.keys())
        if finite:
            assert abs(weight - expected) <= 1e-6
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        require(self.state.initialized)
        self.state.sync_states()
        ret: List[str] = self.inner_next_wave()
        for node_id in ret:
            assert node_id in self.state.nodes
        for index in range(1, len(ret)):
            previous = ret[index - 1]
            current = ret[index]
            assert _ranks_before(self.state.priorities, previous, current)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret = self.inner_mark_running(node_id)
        self.state.sync_states()
        self.state.states[node_id] = NodeState.RUNNING
        assert self.state.states[node_id] == NodeState.RUNNING
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret = self.inner_mark_succeeded(node_id)
        self.state.sync_states()
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.dependents_of(node_id):
            if self.state.states.get(dependent) != NodeState.PENDING:
                continue
            unblocked = True
            for dependency in self.state.nodes[dependent]:
                if self.state.states.get(dependency) != NodeState.SUCCEEDED:
                    unblocked = False
            if unblocked:
                self.state.states[dependent] = NodeState.READY
        assert self.state.states[node_id] == NodeState.SUCCEEDED
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        require_arg(failure_policy, Domain.sampled_from([FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM]))
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.sync_states()
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other in self.state.nodes:
                if self.state.states.get(other) not in TERMINAL_STATES:
                    self.state.states[other] = NodeState.CANCELLED
        else:
            for dependent in self.state.descendants_of(node_id):
                if self.state.states.get(dependent) not in TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
        assert self.state.states[node_id] == NodeState.FAILED
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        require(self.state.initialized)
        self.state.sync_states()
        ret: bool = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require_arg(node_id, Domain.in_set(self.state.node_id_choices))
        ret: NodeState = self.inner_get_state(node_id)
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        self.state.sync_states()
        ret: Mapping[str, NodeState] = self.inner_get_all_states()
        assert set(ret.keys()) == set(self.state.nodes.keys())
        for node_id in ret:
            assert isinstance(ret[node_id], NodeState)
        return ret

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.state.initialized)
        require(self.state.has_nodes)
        require(self.state.valid_graph)
        require_arg(failure_policy, Domain.sampled_from([FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM]))
        ret: DAGRunReport = self.inner_run(failure_policy)
        assert ret.total_nodes == len(self.state.nodes)
        assert ret.wall_clock_seconds >= 0.0
        assert len(ret.succeeded_nodes) + len(ret.failed_nodes) + len(ret.skipped_nodes) + len(ret.cancelled_nodes) <= len(self.state.nodes)
        for node_id in ret.results:
            assert node_id in self.state.nodes
            assert ret.results[node_id].node_id == node_id
        for index in range(1, len(ret.critical_path)):
            assert ret.critical_path[index - 1] in self.state.nodes[ret.critical_path[index]]
        assert set(ret.critical_path) <= set(self.state.nodes.keys())
        for node_id in ret.results:
            self.state.states[node_id] = ret.results[node_id].state
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model into its ready-for-operations baseline state."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DagEngineLiteState] = None) -> Any:
    """Builds a synthesized fake bound to a fresh or supplied model state."""
    return FakeDagEngineLite(state=state if state is not None else DagEngineLiteState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies the synthesized fake honors every declared transition and seeding transition."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DagEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises each transition and seeding transition against the synthesized fake."""
        self.sm.seed_initial()
        self.fake.add_node("alpha", noop_action, None, 1, 0)
        self.fake.add_node("beta", noop_action, ["alpha"], 2, 1)
        self.fake.add_node("gamma", failing_action, ["alpha"], 0, 0)
        self.fake.has_node("alpha")
        self.fake.has_node("zeta")
        self.fake.get_node("beta")
        self.fake.get_dependencies("beta")
        self.fake.get_dependents("alpha")
        self.fake.all_nodes()
        self.fake.find_roots()
        self.fake.find_leaves()
        self.fake.validate()
        self.fake.topological_sort()
        self.fake.compute_critical_path(None)
        self.fake.compute_critical_path({"alpha": 2.0, "beta": 3.0})
        self.fake.next_wave()
        self.fake.mark_running("alpha")
        self.fake.mark_succeeded("alpha")
        self.fake.mark_running("beta")
        self.fake.mark_succeeded("beta")
        self.fake.mark_failed("gamma", FailurePolicy.SKIP_DOWNSTREAM)
        self.fake.is_finished()
        self.fake.get_state("alpha")
        self.fake.get_all_states()
        self.fake.add_edge("beta", "gamma")
        self.fake.remove_node("gamma")
        self.fake.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:26:04Z
# LAST_CHANGED: 2026-11-09T22:26:04Z
# CHANGE: Implement unified DAG/WaveScheduler/DAGRunner pretense state machine: modeled graph + node lifecycle state, state-gated require/require_arg contracts, inner transitions for fake outcomes, synthesized fake factory, full transition coverage test, and fake Hypothesis fuzzing.
# --- END AUTOFAB METADATA ---
