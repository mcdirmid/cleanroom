# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, Mapping, Optional
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
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    FailurePolicy,
    NodeState,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_lite_initialize,
)
from benchmark_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
)


def _noop_action() -> Any:
    """Successful node action used by real implementation scenarios."""
    return None


def _failing_action() -> Any:
    """Failing node action used to exercise failure policies."""
    raise RuntimeError("induced node failure")


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Overrides observe the real SUT through sut(TargetClass) and pivot on
# call_target(target.method(...)). Model state and preconditions are inherited
# from the interface state machine, so no require/require_arg guards are repeated
# here and no model state is mutated.

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for the DAG, scheduler, and runner."""

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
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        assert definition.dependencies == frozenset(dependencies or ())
        assert definition.priority == priority
        assert definition.retries == retries
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert upstream_id in target.get_dependencies(downstream_id)
        assert downstream_id in target.get_dependents(upstream_id)
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        assert target.has_node(node_id) is False
        assert node_id not in target.all_nodes()
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        assert ret == (node_id in target.all_nodes())
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        assert ret.node_id == node_id
        assert node_id in target.all_nodes()
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        assert isinstance(ret, set)
        assert node_id in target.all_nodes()
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        assert isinstance(ret, set)
        assert node_id in target.all_nodes()
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert all(target.has_node(node_id) for node_id in ret)
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
        assert len(ret) == len(target.all_nodes())
        assert set(ret) == target.all_nodes()
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        assert all(not target.get_dependencies(node_id) for node_id in ret)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        assert all(not target.get_dependents(node_id) for node_id in ret)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        path, weight = ret
        assert len(path) == len(set(path))
        assert set(path) <= target.all_nodes()
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        states = target.get_all_states()
        assert all(node_id in states for node_id in ret)
        assert all(states[node_id] is NodeState.READY for node_id in ret)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        assert target.get_state(node_id) is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        assert target.get_state(node_id) is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert target.get_state(node_id) is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        assert ret is True or ret is False
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
        assert all(isinstance(node_id, str) for node_id in ret)
        assert all(isinstance(state, NodeState) for state in ret.values())
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        assert ret.wall_clock_seconds >= 0.0
        assert len(ret.results) <= ret.total_nodes
        assert all(isinstance(result.state, NodeState) for result in ret.results.values())
        assert all(
            result.node_id == node_id for node_id, result in ret.results.items()
        )
        assert len(ret.critical_path) <= ret.total_nodes
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies contracted behavior."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.scheduler, DAGRunner: self.runner}
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.runner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_graph_construction_scenarios(self) -> None:
        """Drives registration, edge creation, lookups, and removal through checked calls."""
        self.checked_dag.add_node("alpha", _noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 1, 1)
        assert self.checked_dag.has_node("alpha") is True
        assert self.checked_dag.has_node("omega") is False
        assert self.checked_dag.get_node("beta").priority == 1
        assert self.checked_dag.get_node("beta").retries == 1
        assert self.checked_dag.get_dependencies("beta") == {"alpha"}
        assert self.checked_dag.get_dependents("alpha") == {"beta"}
        assert self.checked_dag.all_nodes() == {"alpha", "beta"}
        self.checked_dag.add_edge("alpha", "beta")
        assert self.checked_dag.get_dependents("alpha") == {"beta"}
        self.checked_dag.remove_node("beta")
        assert self.checked_dag.all_nodes() == {"alpha"}
        assert self.checked_dag.get_dependents("alpha") == set()

    def test_graph_analysis_scenarios(self) -> None:
        """Drives validation, ordering, roots/leaves, and critical path analysis."""
        self.checked_dag.add_node("alpha", _noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 1, 0)
        self.checked_dag.add_node("gamma", _noop_action, ("alpha",), 0, 0)
        self.checked_dag.add_node("delta", _noop_action, ("beta", "gamma"), 5, 0)
        self.checked_dag.validate()
        assert self.checked_dag.topological_sort() == ["alpha", "beta", "gamma", "delta"]
        assert self.checked_dag.find_roots() == {"alpha"}
        assert self.checked_dag.find_leaves() == {"delta"}
        path, weight = self.checked_dag.compute_critical_path(
            {"alpha": 1.0, "beta": 2.0, "gamma": 3.0, "delta": 4.0}
        )
        assert path == ["alpha", "gamma", "delta"]
        assert weight == 8.0
        default_path, default_weight = self.checked_dag.compute_critical_path(None)
        assert default_weight == 3.0
        assert default_path[0] == "alpha"
        assert default_path[-1] == "delta"
        assert all(
            default_path[index] in self.checked_dag.get_dependencies(default_path[index + 1])
            for index in range(len(default_path) - 1)
        )

    def test_empty_graph_scenarios(self) -> None:
        """Drives analysis, scheduling, and finished determination over an empty graph."""
        self.checked_dag.validate()
        assert self.checked_dag.all_nodes() == set()
        assert self.checked_dag.topological_sort() == []
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == set()
        empty_path, empty_weight = self.checked_dag.compute_critical_path(None)
        assert empty_path == []
        assert empty_weight == 0.0
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.get_all_states() == {}
        assert self.checked_scheduler.is_finished() is True

    def test_deferred_dependency_scenarios(self) -> None:
        """Registers a node whose dependency is absent without eager rejection."""
        self.checked_dag.add_node("alpha", _noop_action, ("phantom",), 0, 0)
        assert self.checked_dag.has_node("alpha") is True
        assert self.checked_dag.has_node("phantom") is False
        assert self.checked_dag.all_nodes() == {"alpha"}
        assert self.checked_dag.get_dependencies("alpha") == {"phantom"}
        assert self.checked_dag.get_dependents("alpha") == set()
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == {"alpha"}
        assert self.checked_scheduler.next_wave() == []

    def test_graph_removal_purges_state_scenarios(self) -> None:
        """Removes an interior node, purging incident edges and scheduler records."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        self.checked_dag.add_node("gamma", _noop_action, ("beta",), 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        assert set(self.checked_scheduler.get_all_states()) == {"alpha", "beta", "gamma"}
        self.checked_dag.remove_node("beta")
        assert self.checked_dag.has_node("beta") is False
        assert self.checked_dag.get_dependencies("gamma") == set()
        assert self.checked_dag.get_dependents("alpha") == set()
        assert set(self.checked_dag.all_nodes()) == {"alpha", "gamma"}
        states = self.checked_scheduler.get_all_states()
        assert "beta" not in states
        assert set(states) == {"alpha", "gamma"}
        assert self.checked_scheduler.get_state("alpha") is NodeState.READY

    def test_scheduler_wave_scenarios(self) -> None:
        """Drives wave resolution and node lifecycle transitions of the scheduler."""
        self.checked_dag.add_node("alpha", _noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        assert self.checked_scheduler.is_finished() is False
        self.checked_scheduler.mark_running("alpha")
        assert self.checked_scheduler.get_state("alpha") is NodeState.RUNNING
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("alpha") is NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("beta") is NodeState.READY
        assert self.checked_scheduler.next_wave() == ["beta"]
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        states = self.checked_scheduler.get_all_states()
        assert states["alpha"] is NodeState.SUCCEEDED
        assert states["beta"] is NodeState.SUCCEEDED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_skip_downstream_scenarios(self) -> None:
        """Drives the skip-downstream failure policy across a dependency chain."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("alpha") is NodeState.FAILED
        assert self.checked_scheduler.get_state("beta") is NodeState.SKIPPED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_fail_fast_scenarios(self) -> None:
        """Drives the fail-fast failure policy cancelling remaining pending nodes."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "beta"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        assert self.checked_scheduler.get_state("beta") is NodeState.CANCELLED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_is_finished_scenarios(self) -> None:
        """Drives finished determination while running and while blocked by failure."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        self.checked_scheduler.mark_running("alpha")
        assert self.checked_scheduler.get_state("alpha") is NodeState.RUNNING
        assert self.checked_scheduler.is_finished() is False
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("beta") is NodeState.SKIPPED
        self.checked_dag.add_node("gamma", _noop_action, ("alpha",), 0, 0)
        assert self.checked_scheduler.get_state("gamma") is NodeState.PENDING
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_continue_on_error_scenarios(self) -> None:
        """Retains independent unblocked work while dependents of a failure are skipped."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        self.checked_dag.add_node("epsilon", _noop_action, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "epsilon"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("alpha") is NodeState.FAILED
        assert self.checked_scheduler.get_state("beta") is NodeState.SKIPPED
        assert self.checked_scheduler.get_state("epsilon") is NodeState.READY
        assert self.checked_scheduler.is_finished() is False
        assert self.checked_scheduler.next_wave() == ["epsilon"]
        self.checked_scheduler.mark_running("epsilon")
        self.checked_scheduler.mark_succeeded("epsilon")
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_diamond_skip_scenarios(self) -> None:
        """Skips a diamond of transitive dependents once under the skip policy."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        self.checked_dag.add_node("gamma", _noop_action, ("alpha",), 0, 0)
        self.checked_dag.add_node("delta", _noop_action, ("beta", "gamma"), 0, 0)
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("alpha") is NodeState.FAILED
        assert self.checked_scheduler.get_state("beta") is NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") is NodeState.SKIPPED
        assert self.checked_scheduler.get_all_states()["delta"] is NodeState.SKIPPED
        assert self.checked_scheduler.is_finished() is True

    def test_runner_success_scenarios(self) -> None:
        """Drives a successful full graph run and inspects the consolidated report."""
        self.checked_dag.add_node("alpha", _noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        self.checked_dag.add_node("gamma", _noop_action, ("beta",), 0, 0)
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert set(report.succeeded_nodes) == {"alpha", "beta", "gamma"}
        assert report.failed_nodes == ()
        assert report.skipped_nodes == ()
        assert report.cancelled_nodes == ()
        assert report.critical_path == ("alpha", "beta", "gamma")
        assert report.wall_clock_seconds >= 0.0

    def test_runner_skip_downstream_scenarios(self) -> None:
        """Drives a failing node under the skip-downstream reporting policy."""
        self.checked_dag.add_node("alpha", _failing_action, None, 0, 0)
        self.checked_dag.add_node("beta", _noop_action, ("alpha",), 0, 0)
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 2
        assert report.failed_nodes == ("alpha",)
        assert report.skipped_nodes == ("beta",)
        assert report.succeeded_nodes == ()

    def test_runner_fail_fast_scenarios(self) -> None:
        """Drives a failing node under the fail-fast reporting policy."""
        self.checked_dag.add_node("alpha", _failing_action, None, 0, 1)
        self.checked_dag.add_node("beta", _noop_action, None, 0, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert report.failed_nodes == ("alpha",)
        assert report.succeeded_nodes == ()
        assert "beta" in report.cancelled_nodes


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing the DAG, scheduler, and runner services for fuzzing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:32:36Z
# LAST_CHANGED: 2026-11-08T06:29:08Z
# CHANGE: No code change (file is at the last verified checkpoint; all legitimately coverable facets were already implemented and accepted). Recording the adjudication of the remaining pret_cov demand in-band because it is not satisfiable from this target: the requested rejections (DuplicateNodeError; NodeNotFoundError for add_edge endpoints, remove_node, get_node/get_dependencies/get_dependents, scheduler.get_state, and the deferred validate/topological_sort surfaces; CycleError from validate/topological_sort) are declared by low/dag_engine_lite.pyi itself as 'untestable checked precondition violation[s]' (lines 30/44/58), and guides/pretense.md line 55 forbids transitions or scenario tests from violating preconditions or asserting *Error, so no reachable exercise exists. The suggested 'terminal contract-violation transition whose require/require_arg guard carries the contracted error' also cannot be authored here: implementation pseudo-state machines must not duplicate require guards (guide line 61) and may not import require_arg/Domain (PN_IMPL_NO_REQUIRE_ARG_IMPORT); such guards live only in the interface state machine benchmark_1/.../dag_engine_lite_pretense.py, which is not an assigned target in this dispatch. The auditor also excludes the only executable alternative (exception assertions), and the library API exposes no such transition mechanism (transition has no terminal attribute; probe code is rejected by PRE_LINT_NO_TOP_LEVEL_PROBE). Static verification: PASSED (0 lint/type errors). Remaining resolution requires either (a) an interface-state-machine scope handoff to model guard-carried contract violations, or (b) an adjudication that untestable checked preconditions are out of coverage scope.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T06:32:36Z
# PRETENSE_QA_AUDIT: 2026-11-08T06:32:18Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
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


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# Transitions model target methods 1:1 via @transition(TargetClass.method). Model
# state tracks the registered graph, the wave scheduler lifecycle, and the runner
# results. Checked preconditions (*Error) are gated with require(...) / require_arg(...)
# so generators never violate caller obligations; operational branches live inside the
# single transition body.

_TERMINAL_STATES: Tuple[NodeState, ...] = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)

_BLOCKING_STATES: Tuple[NodeState, ...] = (
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)

_NAMED_NODE_IDS: Tuple[str, ...] = (
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
    "lambda_",
    "mu",
    "nu",
    "xi",
    "omicron",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "chi",
    "psi",
    "omega",
)

_NODE_ID_POOL: Tuple[str, ...] = _NAMED_NODE_IDS + tuple(
    f"node{index}" for index in range(40)
)


def _noop_action() -> Any:
    """Neutral node action used by fixed fake scenarios."""
    return None


def _transitive_upstream(upstream: Mapping[str, Set[str]], seeds: Collection[str]) -> Set[str]:
    """Computes the transitive upstream closure of the seed node identifiers."""
    reached: Set[str] = set(seeds)
    frontier: List[str] = list(seeds)
    for node_id in frontier:
        for parent_id in upstream.get(node_id, set()):
            if parent_id not in reached:
                reached.add(parent_id)
                frontier.append(parent_id)
    return reached


def _topological_order(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> List[str]:
    """Computes the deterministic topological order; short orders indicate invalid graphs."""
    pending: Dict[str, Set[str]] = {node_id: set(upstream.get(node_id, set())) for node_id in nodes}
    order: List[str] = []
    for _ in range(len(nodes) + 1):
        ready = sorted(
            [node_id for node_id, dependencies in pending.items() if not dependencies],
            key=lambda node_id: (-nodes[node_id].priority, node_id),
        )
        if not ready:
            break
        current = ready[0]
        order.append(current)
        del pending[current]
        for dependencies in pending.values():
            dependencies.discard(current)
    return order


def _critical_path(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    durations: Mapping[str, float],
) -> Tuple[List[str], float]:
    """Computes the longest weighted dependency path and its cumulative weight."""
    earliest: Dict[str, float] = {}
    for _ in range(len(nodes) + 1):
        for node_id in nodes:
            dependencies = upstream.get(node_id, set())
            if all(parent_id in earliest for parent_id in dependencies):
                earliest[node_id] = max(
                    (earliest[parent_id] for parent_id in dependencies),
                    default=0.0,
                ) + durations.get(node_id, 1.0)
    if not earliest:
        return ([], 0.0)
    terminal = max(sorted(earliest), key=lambda node_id: earliest[node_id])
    path: List[str] = []
    current = terminal
    for _ in range(len(nodes) + 1):
        path.append(current)
        parents = [parent_id for parent_id in upstream.get(current, set()) if parent_id in earliest]
        if not parents:
            break
        current = min(parents, key=lambda parent_id: (-earliest[parent_id], parent_id))
    path.reverse()
    return (path, earliest[terminal])


@dataclass
class DagEngineLiteState:
    """Canonical model state for DAG, wave scheduler, and runner operations."""

    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    scheduler_states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    initialized: bool = True


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for the DAG, scheduler, and runner services."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineLiteState(), singletons=singletons)

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
        require_arg(
            node_id,
            Domain.in_set(
                [candidate for candidate in _NODE_ID_POOL if candidate not in self.state.nodes]
            ),
        )
        require_arg(action, Domain.any())
        require_arg(
            dependencies,
            Domain.type(Optional[Collection[str]]),
            preferred=[None, ("alpha",), ("beta",), ("alpha", "beta")],
        )
        require_arg(priority, Domain.range(0, 10), preferred=[0])
        require_arg(retries, Domain.range(0, 3), preferred=[0])
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies or ()),
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency_id in definition.dependencies:
            self.state.upstream[node_id].add(dependency_id)
            self.state.downstream.setdefault(dependency_id, set()).add(node_id)
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert self.state.nodes[node_id].node_id == node_id
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(upstream_id, Domain.in_set(list(self.state.nodes)))
        require_arg(
            downstream_id,
            Domain.in_set(
                [
                    candidate
                    for candidate in self.state.nodes
                    if candidate not in _transitive_upstream(self.state.upstream, {upstream_id})
                ]
            ),
        )
        self.state.downstream[upstream_id].add(downstream_id)
        self.state.upstream[downstream_id].add(upstream_id)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert downstream_id in self.state.downstream[upstream_id]
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        for parent_id in set(self.state.upstream.get(node_id, set())):
            self.state.downstream.setdefault(parent_id, set()).discard(node_id)
        for dependent_id in set(self.state.downstream.get(node_id, set())):
            self.state.upstream.setdefault(dependent_id, set()).discard(node_id)
        del self.state.nodes[node_id]
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.scheduler_states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        ret = self.inner_remove_node(node_id)
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["alpha"])
        present = node_id in self.state.nodes
        ret = self.inner_has_node(node_id)
        assert present is (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        definition = self.state.nodes[node_id]
        ret = self.inner_get_node(node_id)
        assert definition.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        dependencies = set(self.state.upstream.get(node_id, set()))
        ret = self.inner_get_dependencies(node_id)
        assert set(self.state.upstream.get(node_id, set())) == dependencies
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        dependents = set(self.state.downstream.get(node_id, set()))
        ret = self.inner_get_dependents(node_id)
        assert set(self.state.downstream.get(node_id, set())) == dependents
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        node_ids = set(self.state.nodes)
        ret = self.inner_all_nodes()
        assert node_ids == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        order = _topological_order(self.state.nodes, self.state.upstream)
        require(len(order) == len(self.state.nodes))
        ret = self.inner_validate()
        assert len(order) == len(self.state.nodes)
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        order = _topological_order(self.state.nodes, self.state.upstream)
        require(len(order) == len(self.state.nodes))
        ret = self.inner_topological_sort()
        assert len(order) == len(self.state.nodes)
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        roots = {
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id, set())
        }
        ret = self.inner_find_roots()
        assert all(not self.state.upstream.get(node_id, set()) for node_id in roots)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        leaves = {
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id, set())
        }
        ret = self.inner_find_leaves()
        assert all(not self.state.downstream.get(node_id, set()) for node_id in leaves)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        order = _topological_order(self.state.nodes, self.state.upstream)
        require(len(order) == len(self.state.nodes))
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
            preferred=[None],
        )
        path, weight = _critical_path(
            self.state.nodes,
            self.state.upstream,
            estimated_durations or {},
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        assert len(path) == len(set(path))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                root = not self.state.upstream.get(node_id, set())
                self.state.scheduler_states[node_id] = (
                    NodeState.READY if root else NodeState.PENDING
                )
        candidates: List[Tuple[int, str]] = []
        for candidate_id in self.state.nodes:
            if self.state.scheduler_states.get(candidate_id) is NodeState.READY and all(
                self.state.scheduler_states.get(parent_id) is NodeState.SUCCEEDED
                for parent_id in self.state.upstream.get(candidate_id, set())
            ):
                candidates.append((-self.state.nodes[candidate_id].priority, candidate_id))
        candidates.sort()
        wave = [candidate_id for _, candidate_id in candidates]
        ret = self.inner_next_wave()
        assert all(self.state.scheduler_states.get(node_id) is not None for node_id in self.state.nodes)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        self.state.scheduler_states[node_id] = NodeState.RUNNING
        ret = self.inner_mark_running(node_id)
        assert self.state.scheduler_states[node_id] is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        self.state.scheduler_states[node_id] = NodeState.SUCCEEDED
        for dependent_id in self.state.downstream.get(node_id, set()):
            if self.state.scheduler_states.get(dependent_id) is NodeState.PENDING and all(
                self.state.scheduler_states.get(parent_id) is NodeState.SUCCEEDED
                for parent_id in self.state.upstream.get(dependent_id, set())
            ):
                self.state.scheduler_states[dependent_id] = NodeState.READY
        ret = self.inner_mark_succeeded(node_id)
        assert self.state.scheduler_states[node_id] is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        require_arg(
            failure_policy,
            Domain.sampled_from(FailurePolicy),
            preferred=[FailurePolicy.CONTINUE_ON_ERROR],
        )
        self.state.scheduler_states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id in self.state.nodes:
                if self.state.scheduler_states.get(other_id) not in _TERMINAL_STATES:
                    self.state.scheduler_states[other_id] = NodeState.CANCELLED
        else:
            frontier = list(self.state.downstream.get(node_id, set()))
            visited: Set[str] = set()
            for dependent_id in frontier:
                if dependent_id in visited:
                    continue
                visited.add(dependent_id)
                frontier.extend(self.state.downstream.get(dependent_id, set()))
                if self.state.scheduler_states.get(dependent_id) not in _TERMINAL_STATES:
                    self.state.scheduler_states[dependent_id] = NodeState.SKIPPED
        ret = self.inner_mark_failed(node_id, failure_policy)
        assert self.state.scheduler_states[node_id] is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                root = not self.state.upstream.get(node_id, set())
                self.state.scheduler_states[node_id] = (
                    NodeState.READY if root else NodeState.PENDING
                )
        unfinished = [
            node_id
            for node_id in self.state.nodes
            if self.state.scheduler_states.get(node_id) not in _TERMINAL_STATES
        ]
        blocked = all(
            any(
                self.state.scheduler_states.get(parent_id) in _BLOCKING_STATES
                for parent_id in self.state.upstream.get(node_id, set())
            )
            for node_id in unfinished
        )
        finished = not unfinished or blocked
        ret = self.inner_is_finished()
        assert all(self.state.scheduler_states.get(node_id) is not None for node_id in self.state.nodes)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(list(self.state.nodes)))
        if node_id not in self.state.scheduler_states:
            root = not self.state.upstream.get(node_id, set())
            self.state.scheduler_states[node_id] = (
                NodeState.READY if root else NodeState.PENDING
            )
        state = self.state.scheduler_states[node_id]
        ret = self.inner_get_state(node_id)
        assert node_id in self.state.scheduler_states
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                root = not self.state.upstream.get(node_id, set())
                self.state.scheduler_states[node_id] = (
                    NodeState.READY if root else NodeState.PENDING
                )
        states = {node_id: self.state.scheduler_states[node_id] for node_id in self.state.nodes}
        ret = self.inner_get_all_states()
        assert set(states) == set(self.state.nodes)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        order = _topological_order(self.state.nodes, self.state.upstream)
        require(len(order) == len(self.state.nodes))
        require_arg(
            failure_policy,
            Domain.sampled_from(FailurePolicy),
            preferred=[FailurePolicy.CONTINUE_ON_ERROR],
        )
        for node_id in self.state.nodes:
            if node_id not in self.state.scheduler_states:
                root = not self.state.upstream.get(node_id, set())
                self.state.scheduler_states[node_id] = (
                    NodeState.READY if root else NodeState.PENDING
                )
        results: Dict[str, NodeResult[Any]] = {}
        for _ in range(len(self.state.nodes) + 1):
            wave = [
                node_id
                for node_id in order
                if self.state.scheduler_states.get(node_id) is NodeState.READY
                and all(
                    self.state.scheduler_states.get(parent_id) is NodeState.SUCCEEDED
                    for parent_id in self.state.upstream.get(node_id, set())
                )
            ]
            if not wave:
                break
            for node_id in wave:
                self.state.scheduler_states[node_id] = NodeState.RUNNING
                results[node_id] = NodeResult(node_id=node_id, state=NodeState.SUCCEEDED)
                self.state.scheduler_states[node_id] = NodeState.SUCCEEDED
                for dependent_id in self.state.downstream.get(node_id, set()):
                    if self.state.scheduler_states.get(
                        dependent_id
                    ) is NodeState.PENDING and all(
                        self.state.scheduler_states.get(parent_id) is NodeState.SUCCEEDED
                        for parent_id in self.state.upstream.get(dependent_id, set())
                    ):
                        self.state.scheduler_states[dependent_id] = NodeState.READY
        for node_id in self.state.nodes:
            if node_id not in results:
                results[node_id] = NodeResult(
                    node_id=node_id,
                    state=self.state.scheduler_states.get(node_id, NodeState.PENDING),
                )
        self.state.results = results
        critical_path, weight = _critical_path(self.state.nodes, self.state.upstream, {})
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(
                sorted(
                    node_id
                    for node_id, result in results.items()
                    if result.state is NodeState.SUCCEEDED
                )
            ),
            failed_nodes=tuple(
                sorted(
                    node_id
                    for node_id, result in results.items()
                    if result.state is NodeState.FAILED
                )
            ),
            skipped_nodes=tuple(
                sorted(
                    node_id
                    for node_id, result in results.items()
                    if result.state is NodeState.SKIPPED
                )
            ),
            cancelled_nodes=tuple(
                sorted(
                    node_id
                    for node_id, result in results.items()
                    if result.state is NodeState.CANCELLED
                )
            ),
            wall_clock_seconds=0.0,
            critical_path=tuple(critical_path),
            results=results,
        )
        ret = self.inner_run(failure_policy)
        assert report.total_nodes == len(self.state.nodes)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model state machine into its initialized baseline state."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(
    state: Optional[DagEngineLiteState] = None,
) -> DAG:
    """Creates a synthesized fake exposing the DAG, scheduler, and runner protocols."""
    return FakeDagEngineLite(state=state or DagEngineLiteState())


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Creates synthesized fake views bound to each DagEngineLite service protocol."""
    fake: Any = make_dag_engine_lite_fake(state)
    return (fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all modeled transitions."""

    def setUp(self) -> None:
        self.sm = DagEngineLiteStateMachine()
        self.dag, self.scheduler, self.runner = make_dag_engine_lite_fakes()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition on the fake."""
        self.sm.seed_initial()
        self.dag.add_node("alpha", _noop_action, None, 2, 0)
        self.dag.add_node("beta", _noop_action, ("alpha",), 1, 1)
        self.dag.add_node("gamma", _noop_action, ("beta",), 0, 0)
        assert self.dag.has_node("alpha") is True
        assert self.dag.has_node("missing") is False
        assert self.dag.get_node("beta").node_id == "beta"
        assert self.dag.get_dependencies("beta") == {"alpha"}
        self.dag.add_edge("alpha", "gamma")
        assert self.dag.get_dependents("alpha") == {"beta", "gamma"}
        assert self.dag.all_nodes() == {"alpha", "beta", "gamma"}
        self.dag.validate()
        assert self.dag.topological_sort() == ["alpha", "beta", "gamma"]
        assert self.dag.find_roots() == {"alpha"}
        assert self.dag.find_leaves() == {"gamma"}
        path, weight = self.dag.compute_critical_path({"alpha": 1.0, "beta": 2.0, "gamma": 3.0})
        assert path == ["alpha", "beta", "gamma"]
        assert weight == 6.0
        assert self.scheduler.next_wave() == ["alpha"]
        self.scheduler.mark_running("alpha")
        assert self.scheduler.get_state("alpha") is NodeState.RUNNING
        self.scheduler.mark_succeeded("alpha")
        self.scheduler.mark_failed("beta", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.scheduler.get_state("beta") is NodeState.FAILED
        assert self.scheduler.get_all_states()["gamma"] is NodeState.SKIPPED
        assert self.scheduler.is_finished() is True
        self.dag.remove_node("gamma")
        assert self.runner.run(FailurePolicy.CONTINUE_ON_ERROR).total_nodes == 2

    def test_empty_graph_scenarios(self) -> None:
        """Verifies blank model states expose empty graph, scheduler, and run results."""
        assert self.dag.all_nodes() == set()
        assert self.dag.find_roots() == set()
        assert self.dag.find_leaves() == set()
        self.dag.validate()
        assert self.dag.topological_sort() == []
        path, weight = self.dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0
        assert self.scheduler.next_wave() == []
        assert self.scheduler.is_finished() is True
        assert self.scheduler.get_all_states() == {}
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 0
        assert report.critical_path == ()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T06:07:27Z
# LAST_CHANGED: 2026-11-08T06:07:27Z
# CHANGE: Implemented the DagEngineLite interface pretense module: modeled DAG/WaveScheduler/DAGRunner graph, scheduler, and runner state in DagEngineLiteState with 21 1:1 transitions gated by require/require_arg domains (node id pool, in_set membership, sampled_from enums, range/preferred hints), model-side topological order and critical path helpers, synthesized FakeDagEngineLite with fake factories, fixed TestDagEngineLiteFake scenarios covering 100% of transitions plus seeding, and FakeDagEngineLiteFuzzTest hypothesis compilation.
# --- END AUTOFAB METADATA ---
