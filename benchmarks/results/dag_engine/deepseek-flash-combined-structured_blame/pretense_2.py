# === File: dag_engine_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngine."""

from __future__ import annotations

import time
import unittest
from typing import Any, Callable, Collection, Mapping, Optional

from pretense import call_target, sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_5.parts.dag_engine.pretense.dag_engine_pretense import DagEngineStateMachine
from benchmark_5.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGTimeoutError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from benchmark_5.parts.dag_engine.lib.dag_engine_impl import DAG, DAGRunner, WaveScheduler
from benchmark_5.parts.dag_engine.lib.dag_engine_impl import __initialize__ as _dag_engine_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Pseudo-state machines inherit every outer transition (preconditions, model state
# mutations, and postconditions) from the interface state machine and only override the
# inner observation hooks to bind the concrete target service.


def _action_ok() -> Any:
    """Successful node action returning a stable marker value."""
    return "ok"


def _action_fail() -> Any:
    """Node action that always raises to exercise failure handling."""
    raise RuntimeError("boom")


def _action_slow() -> Any:
    """Node action that exceeds a tight overall execution timeout."""
    time.sleep(0.2)
    return "slow"


class DagEngineImplPseudoStateMachine(DagEngineStateMachine):
    """Implementation pseudo-state machine for DagEngine."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, timeout_seconds, retries))
        return ret

    def inner_add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        return ret

    def inner_remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        return ret

    def inner_has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        return ret

    def inner_get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        return ret

    def inner_get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        return ret

    def inner_get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        return ret

    def inner_all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        return ret

    def inner_validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        return ret

    def inner_topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        return ret

    def inner_find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        return ret

    def inner_find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        return ret

    def inner_next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        return ret

    def inner_mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        return ret

    def inner_mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        return ret

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        return ret

    def inner_is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        return ret

    def inner_get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        return ret

    def inner_get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        return ret

    def inner_run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(timeout_seconds, failure_policy, max_concurrency))
        return ret

    def inner_cancel(
        self,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.cancel())
        return ret

    def inner_is_cancelled(
        self,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.is_cancelled())
        return ret


proto = DagEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the modeled contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DagEngineImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.scheduler, DAGRunner: self.runner}
        )
        self.checked_dag: Any = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler: Any = self.sm.as_checked(WaveScheduler, self.scheduler)
        self.checked_runner: Any = self.sm.as_checked(DAGRunner, self.runner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_empty_graph_queries(self) -> None:
        assert self.checked_dag.all_nodes() == set()
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == set()
        assert self.checked_dag.topological_sort() == []
        assert self.checked_dag.compute_critical_path(None) == ([], 0.0)
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.get_all_states() == {}
        assert self.checked_scheduler.is_finished()
        self.checked_dag.validate()
        report = self.checked_runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)
        assert report.total_nodes == 0
        assert len(report.succeeded_nodes) == 0
        assert len(report.critical_path) == 0

    def test_graph_mutations_and_queries(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 2, None, 0)
        self.checked_dag.add_node("b", _action_ok, ["a"], 1, None, 1)
        self.checked_dag.add_node("c", _action_ok, ["b"], 0, None, 0)
        assert self.checked_dag.has_node("a")
        assert not self.checked_dag.has_node("missing")
        definition = self.checked_dag.get_node("b")
        assert definition.node_id == "b"
        assert definition.priority == 1
        assert definition.retries == 1
        assert set(definition.dependencies) == {"a"}
        assert definition.action is _action_ok
        assert self.checked_dag.get_dependencies("b") == {"a"}
        assert self.checked_dag.get_dependents("a") == {"b"}
        assert self.checked_dag.all_nodes() == {"a", "b", "c"}
        assert self.checked_dag.find_roots() == {"a"}
        assert self.checked_dag.find_leaves() == {"c"}
        self.checked_dag.validate()
        assert self.checked_dag.topological_sort() == ["a", "b", "c"]
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == ["a", "b", "c"]
        assert weight == 3.0
        weighted_path, weighted = self.checked_dag.compute_critical_path({"a": 4.0, "b": 1.0, "c": 2.0})
        assert weighted_path == ["a", "b", "c"]
        assert weighted == 7.0

    def test_graph_edges_and_removal(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("b", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("c", _action_ok, None, 0, None, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "c")
        assert self.checked_dag.get_dependencies("b") == {"a"}
        assert self.checked_dag.get_dependents("a") == {"b"}
        self.checked_dag.remove_node("b")
        assert not self.checked_dag.has_node("b")
        assert self.checked_dag.all_nodes() == {"a", "c"}
        assert self.checked_dag.get_dependencies("c") == set()
        assert self.checked_dag.get_dependents("a") == set()
        self.checked_dag.validate()

    def test_scheduler_wave_execution(self) -> None:
        self.checked_dag.add_node("root", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("left", _action_ok, ["root"], 1, None, 0)
        self.checked_dag.add_node("right", _action_ok, ["root"], 2, None, 0)
        assert not self.checked_scheduler.is_finished()
        assert self.checked_scheduler.next_wave() == ["root"]
        self.checked_scheduler.mark_running("root")
        assert self.checked_scheduler.get_state("root") == NodeState.RUNNING
        self.checked_scheduler.mark_succeeded("root")
        assert self.checked_scheduler.next_wave() == ["right", "left"]
        states = self.checked_scheduler.get_all_states()
        assert set(states) == {"root", "left", "right"}
        assert states["root"] == NodeState.SUCCEEDED
        assert states["left"] == NodeState.READY
        self.checked_scheduler.mark_running("left")
        self.checked_scheduler.mark_failed("left", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("left") == NodeState.FAILED
        assert not self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_running("right")
        self.checked_scheduler.mark_succeeded("right")
        assert self.checked_scheduler.is_finished()
        assert self.checked_scheduler.next_wave() == []

    def test_add_edge_keeps_ready_downstream_ready(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 0, None, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "beta"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_dag.add_edge("alpha", "beta")
        assert self.checked_scheduler.get_state("beta") == NodeState.READY
        assert self.checked_scheduler.next_wave() == ["beta"]

    def test_runner_success_report(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("b", _action_ok, ["a"], 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"a", "b"}
        assert len(report.failed_nodes) == 0
        assert len(report.skipped_nodes) == 0
        assert len(report.cancelled_nodes) == 0
        assert len(report.critical_path) == 2
        assert report.wall_clock_seconds >= 0.0
        assert report.results["a"].value == "ok"
        assert report.results["a"].state == NodeState.SUCCEEDED
        assert self.checked_scheduler.is_finished()

    def test_runner_continue_on_error_policy(self) -> None:
        self.checked_dag.add_node("bad", _action_fail, None, 0, None, 0)
        self.checked_dag.add_node("good", _action_ok, None, 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
        assert set(report.succeeded_nodes) == {"good"}
        assert set(report.failed_nodes) == {"bad"}
        assert report.results["bad"].error is not None
        assert self.checked_scheduler.get_state("bad") == NodeState.FAILED
        assert self.checked_scheduler.get_state("good") == NodeState.SUCCEEDED

    def test_runner_retries_failures(self) -> None:
        self.checked_dag.add_node("bad", _action_fail, None, 0, None, 2)
        report = self.checked_runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)
        assert set(report.failed_nodes) == {"bad"}
        assert report.results["bad"].retries_attempted >= 1
        assert self.checked_scheduler.is_finished()

    def test_runner_fail_fast_policy(self) -> None:
        self.checked_dag.add_node("bad", _action_fail, None, 0, None, 0)
        self.checked_dag.add_node("child", _action_ok, ["bad"], 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.FAIL_FAST, 1)
        assert set(report.failed_nodes) == {"bad"}
        assert set(report.cancelled_nodes) == {"child"}
        assert self.checked_scheduler.get_state("child") == NodeState.CANCELLED
        assert self.checked_scheduler.is_finished()

    def test_runner_skip_downstream_policy(self) -> None:
        self.checked_dag.add_node("bad", _action_fail, None, 0, None, 0)
        self.checked_dag.add_node("child", _action_ok, ["bad"], 0, None, 0)
        self.checked_dag.add_node("grandchild", _action_ok, ["child"], 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.SKIP_DOWNSTREAM, 1)
        assert set(report.failed_nodes) == {"bad"}
        assert set(report.skipped_nodes) == {"child", "grandchild"}
        assert self.checked_scheduler.get_state("grandchild") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished()

    def test_runner_timeout(self) -> None:
        self.checked_dag.add_node("slow", _action_slow, None, 0, None, 0)
        self.checked_dag.add_node("tail", _action_ok, ["slow"], 0, None, 0)
        self.checked_runner.violating(DAGTimeoutError).run(0.001, FailurePolicy.CONTINUE_ON_ERROR, 1)

    def test_runner_cancelled(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_runner.cancel()
        assert self.checked_runner.is_cancelled()
        assert self.checked_scheduler.get_state("a") == NodeState.CANCELLED
        self.checked_dag.add_node("b", _action_ok, None, 0, None, 0)
        self.checked_runner.violating(DAGCancelledError).run(None, FailurePolicy.FAIL_FAST, 1)

    def test_get_node_missing(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_remove_node_missing(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_add_edge_missing(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("a", "missing")

    def test_get_dependencies_missing(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_missing(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_validate_missing_dependency(self) -> None:
        self.checked_dag.add_node("a", _action_ok, ["ghost"], 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("b", _action_ok, None, 0, None, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("b", _action_ok, None, 0, None, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_add_edge_missing_upstream(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing", "a")

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("b", _action_ok, ["a"], 0, None, 0)
        assert self.checked_scheduler.next_wave() == ["a"]
        assert set(self.checked_scheduler.get_all_states()) == {"a", "b"}
        self.checked_dag.remove_node("b")
        assert self.checked_dag.all_nodes() == {"a"}
        states = self.checked_scheduler.get_all_states()
        assert "b" not in states
        assert states["a"] == NodeState.READY
        assert self.checked_scheduler.next_wave() == ["a"]

    def test_mark_succeeded_skips_non_pending_dependents(self) -> None:
        self.checked_dag.add_node("root", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("child", _action_ok, ["root"], 0, None, 0)
        self.checked_dag.add_node("grandchild", _action_ok, ["child"], 0, None, 0)
        self.checked_scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("child") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("grandchild") == NodeState.SKIPPED
        self.checked_scheduler.mark_succeeded("root")
        assert self.checked_scheduler.get_state("root") == NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("child") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("grandchild") == NodeState.SKIPPED

    def test_mark_failed_diamond_skip_downstream(self) -> None:
        self.checked_dag.add_node("a", _action_ok, None, 0, None, 0)
        self.checked_dag.add_node("b", _action_ok, ["a"], 0, None, 0)
        self.checked_dag.add_node("c", _action_ok, ["a"], 0, None, 0)
        self.checked_dag.add_node("d", _action_ok, ["b", "c"], 0, None, 0)
        assert self.checked_scheduler.next_wave() == ["a"]
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("b") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("c") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("d") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished()

    def test_runner_continue_on_error_strands_dependent(self) -> None:
        self.checked_dag.add_node("bad", _action_fail, None, 0, None, 0)
        self.checked_dag.add_node("child", _action_ok, ["bad"], 0, None, 0)
        report = self.checked_runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 1)
        assert set(report.failed_nodes) == {"bad"}
        assert "child" in report.skipped_nodes
        assert set(report.succeeded_nodes) == set()
        assert report.total_nodes == 2
        assert self.checked_scheduler.get_state("child") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished()

    def _cancel_during_execution(self) -> Any:
        """Node action that signals cancellation while the wave is executing."""
        self.checked_runner.cancel()
        return "cancelled"

    def test_runner_cancel_from_node_action(self) -> None:
        self.checked_dag.add_node("worker", self._cancel_during_execution, None, 0, None, 0)
        self.checked_runner.violating(DAGCancelledError).run(None, FailurePolicy.FAIL_FAST, 1)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineSUT:
    """Aggregate SUT exposing component services for DagEngine state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_initialize(self.registry)
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

def make_sut() -> DagEngineSUT:
    return DagEngineSUT()


DagEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DagEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:52:28Z
# LAST_CHANGED: 2026-11-09T23:50:51Z
# CHANGE: Add real scenario test_add_edge_keeps_ready_downstream_ready: an edge added from an already SUCCEEDED upstream must leave the READY downstream node READY (reported by get_state and returned by next_wave), pinning the corrected post-edge scheduler behavior against the concrete implementation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T23:52:28Z
# PRETENSE_QA_AUDIT: 2026-11-09T23:52:06Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_5.parts.dag_engine.lib.dag_engine import (
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
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Each public target method is modeled by exactly one @transition(TargetClass.method)
# transition. Interface transitions delegate to an inner observation hook that computes
# the fake return value from model state; implementation pseudo-state machines override
# those inner hooks to invoke the concrete target.
# require() guards model-state preconditions only; require_arg() declares argument domains.


_TERMINAL_STATES = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


def _model_topological_order(state: DagEngineState) -> List[str]:
    """Computes the deterministic topological order predicted by model state."""
    in_degree: Dict[str, int] = {}
    downstream: Dict[str, Set[str]] = {}
    for node in state.nodes:
        in_degree[node] = 0
        downstream[node] = set()
    for node in state.nodes:
        for dependency in state.upstream.get(node, set()):
            if dependency not in in_degree:
                continue
            in_degree[node] = in_degree[node] + 1
            downstream[dependency].add(node)
    ready: List[Tuple[int, str]] = []
    for node in state.nodes:
        if in_degree[node] == 0:
            ready.append((-state.nodes[node], node))
    ready.sort()
    order: List[str] = []
    while ready:
        _, node = ready.pop(0)
        order.append(node)
        for dependent in sorted(downstream[node]):
            in_degree[dependent] = in_degree[dependent] - 1
            if in_degree[dependent] == 0:
                ready.append((-state.nodes[dependent], dependent))
                ready.sort()
    return order


def _noop_action() -> Any:
    """Trivial node action used by fake scenarios."""
    return None


@dataclass
class DagEngineState:
    """Canonical model state for DagEngine operations."""

    initialized: bool = True
    nodes: Dict[str, int] = field(default_factory=dict)
    definitions: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    order: Dict[str, int] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    acyclic: bool = True
    cancelled: bool = False


class DagEngineStateMachine(StateMachine[DagEngineState]):
    """Unified Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DagEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DagEngineState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return DagEngineState()

    def sync_scheduler_states(self) -> None:
        """Models lazy scheduler discovery: newly registered nodes start READY when they are
        roots and PENDING otherwise, while already known node states are left untouched."""
        for node in self.state.nodes:
            if node in self.state.states:
                continue
            if self.state.upstream.get(node, set()):
                self.state.states[node] = NodeState.PENDING
            else:
                self.state.states[node] = NodeState.READY

    # ------------------------------------------------------------------
    # Inner observation hooks (fake returns computed from model state)
    # ------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> Any:
        return make_return_value(None)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> Any:
        return make_return_value(None)

    def inner_remove_node(self, node_id: str) -> Any:
        return make_return_value(None)

    def inner_has_node(self, node_id: str) -> Any:
        return make_return_value(node_id in self.state.nodes)

    def inner_get_node(self, node_id: str) -> Any:
        return make_return_value(self.state.definitions[node_id])

    def inner_get_dependencies(self, node_id: str) -> Any:
        return make_return_value(set(self.state.upstream[node_id]))

    def inner_get_dependents(self, node_id: str) -> Any:
        return make_return_value(set(self.state.downstream[node_id]))

    def inner_all_nodes(self) -> Any:
        return make_return_value(set(self.state.nodes))

    def inner_validate(self) -> Any:
        return make_return_value(None)

    def inner_topological_sort(self) -> Any:
        return make_return_value(_model_topological_order(self.state))

    def inner_find_roots(self) -> Any:
        roots = set()
        for node in self.state.nodes:
            if not self.state.upstream.get(node, set()):
                roots.add(node)
        return make_return_value(roots)

    def inner_find_leaves(self) -> Any:
        leaves = set()
        for node in self.state.nodes:
            if not self.state.downstream.get(node, set()):
                leaves.add(node)
        return make_return_value(leaves)

    def inner_compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Any:
        order = _model_topological_order(self.state)
        weights: Dict[str, float] = {}
        parent: Dict[str, Optional[str]] = {}
        for node in order:
            weight = 1.0
            if estimated_durations is not None:
                weight = float(estimated_durations.get(node, 1.0))
            best: Optional[str] = None
            best_weight = 0.0
            for dependency in self.state.upstream.get(node, set()):
                if dependency in weights and weights[dependency] > best_weight:
                    best = dependency
                    best_weight = weights[dependency]
            weights[node] = best_weight + weight
            parent[node] = best
        last: Optional[str] = None
        last_weight = 0.0
        for node in order:
            if weights[node] > last_weight:
                last = node
                last_weight = weights[node]
        path: List[str] = []
        while last is not None:
            path.insert(0, last)
            last = parent[last]
        return make_return_value((path, last_weight))

    def inner_next_wave(self) -> Any:
        candidates: List[str] = []
        for node in self.state.nodes:
            if self.state.states.get(node) != NodeState.READY:
                continue
            blocked = False
            for dependency in self.state.upstream.get(node, set()):
                if self.state.states.get(dependency) != NodeState.SUCCEEDED:
                    blocked = True
            if not blocked:
                candidates.append(node)
        ordered = sorted((-self.state.nodes[node], node) for node in candidates)
        return make_return_value([node for _, node in ordered])

    def inner_mark_running(self, node_id: str) -> Any:
        return make_return_value(None)

    def inner_mark_succeeded(self, node_id: str) -> Any:
        return make_return_value(None)

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> Any:
        return make_return_value(None)

    def inner_is_finished(self) -> Any:
        return make_return_value(
            all(self.state.states.get(node) in _TERMINAL_STATES for node in self.state.nodes)
        )

    def inner_get_state(self, node_id: str) -> Any:
        return make_return_value(self.state.states.get(node_id, NodeState.PENDING))

    def inner_get_all_states(self) -> Any:
        return make_return_value(
            {node: self.state.states.get(node, NodeState.PENDING) for node in self.state.nodes}
        )

    def inner_run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> Any:
        nodes = sorted(self.state.nodes)
        results: Dict[str, NodeResult[Any]] = {
            node: NodeResult(node_id=node, state=NodeState.SUCCEEDED) for node in nodes
        }
        report = DAGRunReport(
            total_nodes=len(nodes),
            succeeded_nodes=tuple(nodes),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(_model_topological_order(self.state)),
            results=results,
        )
        return make_return_value(report)

    def inner_cancel(self) -> Any:
        return make_return_value(None)

    def inner_is_cancelled(self) -> Any:
        return make_return_value(self.state.cancelled)

    # ------------------------------------------------------------------
    # DAG transitions
    # ------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["alpha", "beta"])
        require_arg(action, Domain.any())
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])))
        require_arg(priority, Domain.type(int), preferred=[0, 1, 2])
        require_arg(timeout_seconds, Domain.optional(Domain.type(float)))
        require_arg(retries, Domain.type(int), preferred=[0, 1])
        ret = self.inner_add_node(node_id, action, dependencies, priority, timeout_seconds, retries)
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies or ()),
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        self.state.nodes[node_id] = priority
        self.state.definitions[node_id] = definition
        self.state.order[node_id] = max(self.state.order.values(), default=-1) + 1
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in definition.dependencies:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        assert self.state.nodes[node_id] == priority
        assert self.state.definitions[node_id].node_id == node_id
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(self.state.initialized)
        require_arg(upstream_id, Domain.in_set(self.state.nodes))
        require_arg(downstream_id, Domain.in_set(self.state.nodes))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream[upstream_id].add(downstream_id)
        if self.state.order.get(upstream_id, 0) >= self.state.order.get(downstream_id, 0):
            self.state.acyclic = False
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_remove_node(node_id)
        for dependent in sorted(self.state.downstream.get(node_id, set())):
            self.state.upstream[dependent].discard(node_id)
        for dependency in sorted(self.state.upstream.get(node_id, set())):
            self.state.downstream[dependency].discard(node_id)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.nodes.pop(node_id, None)
        self.state.definitions.pop(node_id, None)
        self.state.states.pop(node_id, None)
        self.state.order.pop(node_id, None)
        assert node_id not in self.state.nodes
        assert node_id not in self.state.states
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["alpha", "beta"])
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_get_node(node_id)
        assert ret == self.state.definitions[node_id]
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_get_dependencies(node_id)
        assert ret == self.state.upstream[node_id]
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = self.inner_get_dependents(node_id)
        assert ret == self.state.downstream[node_id]
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.initialized)
        require(self.state.acyclic)
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        ret = self.inner_validate()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.initialized)
        require(self.state.acyclic)
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        ret = self.inner_topological_sort()
        position = {node: index for index, node in enumerate(ret)}
        assert sorted(ret) == sorted(self.state.nodes)
        assert all(
            position[dependency] < position[node]
            for node in ret
            for dependency in self.state.upstream.get(node, set())
        )
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_find_roots()
        assert ret == {node for node in self.state.nodes if not self.state.upstream.get(node, set())}
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_find_leaves()
        assert ret == {node for node in self.state.nodes if not self.state.downstream.get(node, set())}
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require(self.state.acyclic)
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        require_arg(estimated_durations, Domain.optional(Domain.type(Mapping[str, float])))
        ret = self.inner_compute_critical_path(estimated_durations)
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        assert set(ret[0]) <= set(self.state.nodes)
        return ret

    # ------------------------------------------------------------------
    # WaveScheduler transitions
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        require(self.state.initialized)
        self.sync_scheduler_states()
        ret = self.inner_next_wave()
        assert set(ret) <= set(self.state.nodes)
        priorities = [self.state.nodes[node] for node in ret]
        assert priorities == sorted(priorities, reverse=True)
        assert len(ret) == len(set(ret))
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.sync_scheduler_states()
        ret = self.inner_mark_running(node_id)
        self.state.states[node_id] = NodeState.RUNNING
        assert self.state.states[node_id] == NodeState.RUNNING
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.sync_scheduler_states()
        ret = self.inner_mark_succeeded(node_id)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in sorted(self.state.downstream.get(node_id, set())):
            if dependent not in self.state.nodes:
                continue
            if self.state.states.get(dependent) != NodeState.PENDING:
                continue
            blocked = False
            for dependency in self.state.upstream.get(dependent, set()):
                if self.state.states.get(dependency) != NodeState.SUCCEEDED:
                    blocked = True
            if not blocked:
                self.state.states[dependent] = NodeState.READY
        assert self.state.states[node_id] == NodeState.SUCCEEDED
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        self.sync_scheduler_states()
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other in sorted(self.state.nodes):
                if self.state.states.get(other) not in _TERMINAL_STATES:
                    self.state.states[other] = NodeState.CANCELLED
        if failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            visited: Set[str] = set()
            pending = sorted(self.state.downstream.get(node_id, set()))
            for dependent in pending:
                if dependent in visited:
                    continue
                visited.add(dependent)
                if dependent not in self.state.nodes:
                    continue
                if self.state.states.get(dependent) not in _TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
                pending.extend(sorted(self.state.downstream.get(dependent, set())))
        assert self.state.states[node_id] == NodeState.FAILED
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        require(self.state.initialized)
        self.sync_scheduler_states()
        ret = self.inner_is_finished()
        assert ret == all(
            self.state.states.get(node) in _TERMINAL_STATES for node in self.state.nodes
        )
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.sync_scheduler_states()
        ret = self.inner_get_state(node_id)
        assert ret == self.state.states.get(node_id, NodeState.PENDING)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        self.sync_scheduler_states()
        ret = self.inner_get_all_states()
        assert set(self.state.nodes) <= set(ret)
        assert all(ret[node] in NodeState for node in ret)
        return ret

    # ------------------------------------------------------------------
    # DAGRunner transitions
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require(not self.state.cancelled)
        require(self.state.acyclic)
        require(
            all(
                dependency in self.state.nodes
                for dependencies in self.state.upstream.values()
                for dependency in dependencies
            )
        )
        require_arg(timeout_seconds, Domain.sampled_from([None]), preferred=[None])
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)))
        require_arg(max_concurrency, Domain.range(1, 8), preferred=[1, 2])
        self.sync_scheduler_states()
        ret = self.inner_run(timeout_seconds, failure_policy, max_concurrency)
        for node_id in ret.succeeded_nodes:
            self.state.states[node_id] = NodeState.SUCCEEDED
        for node_id in ret.failed_nodes:
            self.state.states[node_id] = NodeState.FAILED
        for node_id in ret.skipped_nodes:
            self.state.states[node_id] = NodeState.SKIPPED
        for node_id in ret.cancelled_nodes:
            self.state.states[node_id] = NodeState.CANCELLED
        for _ in range(len(self.state.nodes) + 1):
            changed = False
            for node in sorted(self.state.nodes):
                if self.state.states.get(node) in _TERMINAL_STATES:
                    continue
                blocked = False
                for dependency in self.state.upstream.get(node, set()):
                    if self.state.states.get(dependency) not in (None, NodeState.SUCCEEDED):
                        blocked = True
                if blocked:
                    self.state.states[node] = NodeState.SKIPPED
                    changed = True
            if not changed:
                break
        assert ret.total_nodes == len(self.state.nodes)
        assert set(ret.succeeded_nodes) <= set(self.state.nodes)
        assert set(ret.skipped_nodes) <= set(self.state.nodes)
        assert all(self.state.states.get(node) in _TERMINAL_STATES for node in self.state.nodes)
        return ret

    @transition(DAGRunner.cancel)
    def cancel(self) -> None:
        require(self.state.initialized)
        self.sync_scheduler_states()
        ret = self.inner_cancel()
        self.state.cancelled = True
        for node in sorted(self.state.nodes):
            if self.state.states.get(node) in (NodeState.READY, NodeState.PENDING):
                self.state.states[node] = NodeState.CANCELLED
        assert self.state.cancelled
        assert ret is None
        return ret

    @transition(DAGRunner.is_cancelled)
    def is_cancelled(self) -> bool:
        require(self.state.initialized)
        ret = self.inner_is_cancelled()
        assert ret == self.state.cancelled
        return ret

    # ------------------------------------------------------------------
    # Seeding transitions
    # ------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model as a fully initialized engine."""
        self.state.initialized = True


proto = DagEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngine = synthesize_fake(DagEngineStateMachine)

def make_dag_engine_fakes(
    state: Optional[DagEngineState] = None,
) -> Tuple[FailurePolicy, NodeDefinition, NodeResult, DAGRunReport, DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDagEngine(state=state or DagEngineState())
    return (
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
        fake,
    )


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_dag_engine_fakes()
        self.sm = DagEngineStateMachine()
        self.dag = self.fakes[4]
        self.scheduler = self.fakes[5]
        self.runner = self.fakes[6]

    def test_transitions_coverage(self) -> None:
        """Exercises every transition and seeding transition through the synthesized fake."""
        self.sm.seed_initial()
        self.dag.add_node("alpha", _noop_action, None, 2, None, 0)
        self.dag.add_node("beta", _noop_action, ["alpha"], 1, None, 1)
        self.dag.add_node("gamma", _noop_action, ["beta"], 0, None, 0)
        self.dag.add_edge("alpha", "beta")
        assert self.dag.has_node("alpha")
        assert not self.dag.has_node("missing")
        definition = self.dag.get_node("beta")
        assert definition.node_id == "beta"
        assert definition.priority == 1
        assert set(definition.dependencies) == {"alpha"}
        assert self.dag.get_dependencies("beta") == {"alpha"}
        assert self.dag.get_dependents("alpha") == {"beta"}
        assert self.dag.all_nodes() == {"alpha", "beta", "gamma"}
        assert self.dag.find_roots() == {"alpha"}
        assert self.dag.find_leaves() == {"gamma"}
        self.dag.validate()
        order = self.dag.topological_sort()
        assert order == ["alpha", "beta", "gamma"]
        path, _ = self.dag.compute_critical_path(None)
        assert path == ["alpha", "beta", "gamma"]
        assert self.scheduler.next_wave() == ["alpha"]
        self.scheduler.mark_running("alpha")
        assert self.scheduler.get_state("alpha") == NodeState.RUNNING
        self.scheduler.mark_succeeded("alpha")
        assert self.scheduler.next_wave() == ["beta"]
        assert set(self.scheduler.get_all_states()) == {"alpha", "beta", "gamma"}
        assert not self.scheduler.is_finished()
        self.scheduler.mark_running("beta")
        self.scheduler.mark_failed("beta", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.scheduler.get_state("beta") == NodeState.FAILED
        assert self.scheduler.get_state("gamma") == NodeState.SKIPPED
        assert self.scheduler.is_finished()
        report = self.runner.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
        assert report.total_nodes == 3
        assert not self.runner.is_cancelled()
        self.runner.cancel()
        assert self.runner.is_cancelled()
        self.dag.remove_node("gamma")
        self.dag.remove_node("beta")
        self.dag.remove_node("alpha")
        assert self.dag.all_nodes() == set()

    def test_add_edge_keeps_ready_downstream_ready(self) -> None:
        """An edge whose upstream is already SUCCEEDED must not demote a READY downstream."""
        self.dag.add_node("alpha", _noop_action, None, 0, None, 0)
        self.dag.add_node("beta", _noop_action, None, 0, None, 0)
        assert self.scheduler.next_wave() == ["alpha", "beta"]
        self.scheduler.mark_running("alpha")
        self.scheduler.mark_succeeded("alpha")
        self.dag.add_edge("alpha", "beta")
        assert self.scheduler.get_state("beta") == NodeState.READY
        assert self.scheduler.next_wave() == ["beta"]


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDagEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T23:50:44Z
# LAST_CHANGED: 2026-11-09T23:50:44Z
# CHANGE: Resolve pretense_qa post-edge ready node demotion: scheduler node states are now assigned by modeled lazy discovery (sync_scheduler_states: roots READY, non-roots PENDING at first scheduler interaction) instead of eagerly in add_node, and add_edge no longer demotes a READY downstream, so an edge from an already SUCCEEDED upstream keeps the downstream READY and eligible for next_wave. Added fake scenario test_add_edge_keeps_ready_downstream_ready.
# --- END AUTOFAB METADATA ---
