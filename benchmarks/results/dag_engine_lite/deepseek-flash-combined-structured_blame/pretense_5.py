# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from pretense import sut

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    enter_phase,
    get_singleton,
    system,
)

from dag_engine_lite.lib import dag_engine_lite_impl
from dag_engine_lite.lib.dag_engine_lite import (
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
from dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineStateMachine,
)

_ATTEMPTS: dict[str, int] = {}


def _action_ok() -> str:
    return "ok"


def _action_fail() -> str:
    raise RuntimeError("node action failed")


def _flaky_action() -> str:
    attempt = _ATTEMPTS.get("flaky", 0) + 1
    _ATTEMPTS["flaky"] = attempt
    if attempt < 2:
        raise RuntimeError("transient node action failure")
    return "recovered"


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class DAGEngineImplPseudoStateMachine(DAGEngineStateMachine):
    """Binds interface transitions to the concrete DAG, WaveScheduler, and DAGRunner SUTs."""

    # ------------------------------------------------------------------
    # DAG SUT bindings
    # ------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: DAG = sut(DAG)
        target.add_node(node_id, action, dependencies, priority, retries)
        assert sut(DAG).has_node(node_id)
        return None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        target.add_edge(upstream_id, downstream_id)
        assert upstream_id in sut(DAG).get_dependencies(downstream_id)
        assert downstream_id in sut(DAG).get_dependents(upstream_id)
        return None

    def inner_remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        target.remove_node(node_id)
        assert not sut(DAG).has_node(node_id)
        return None

    def inner_has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        return definition

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        target: DAG = sut(DAG)
        return target.all_nodes()

    def inner_validate(self) -> None:
        target: DAG = sut(DAG)
        target.validate()
        return None

    def inner_topological_sort(self) -> List[str]:
        target: DAG = sut(DAG)
        return target.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        target: DAG = sut(DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        target: DAG = sut(DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        target: DAG = sut(DAG)
        return target.compute_critical_path(estimated_durations)

    # ------------------------------------------------------------------
    # WaveScheduler SUT bindings
    # ------------------------------------------------------------------

    def inner_next_wave(self) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_running(node_id)
        assert sut(WaveScheduler).get_state(node_id) is NodeState.RUNNING
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_succeeded(node_id)
        assert sut(WaveScheduler).get_state(node_id) is NodeState.SUCCEEDED
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_failed(node_id, failure_policy)
        assert sut(WaveScheduler).get_state(node_id) is NodeState.FAILED
        return None

    def inner_is_finished(self) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_all_states()

    # ------------------------------------------------------------------
    # DAGRunner SUT binding
    # ------------------------------------------------------------------

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        report = target.run(failure_policy)
        states = sut(WaveScheduler).get_all_states()
        assert report.total_nodes == len(states)
        assert set(report.results.keys()) <= set(states.keys())
        for node_id, result in report.results.items():
            node_state = states.get(node_id)
            assert node_state is not None
            assert result.state is node_state
            assert result.duration_seconds >= 0.0
            if result.state is NodeState.SUCCEEDED:
                assert result.error is None
            if result.state is NodeState.FAILED:
                assert result.error is not None
        for node_id in report.succeeded_nodes:
            assert states.get(node_id) is NodeState.SUCCEEDED
        for node_id in report.failed_nodes:
            assert states.get(node_id) is NodeState.FAILED
        for node_id in report.skipped_nodes:
            assert states.get(node_id) is NodeState.SKIPPED
        for node_id in report.cancelled_nodes:
            assert states.get(node_id) is NodeState.CANCELLED
        critical_path, _ = sut(DAG).compute_critical_path(None)
        assert tuple(critical_path) == report.critical_path
        return report


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestDAGEngineImplReal(unittest.TestCase):
    """Verifies that the concrete DAG engine implementation satisfies its contracts."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        _ATTEMPTS.clear()
        self.registry = LifecycleRegistry()
        self.registry.register_module(dag_engine_lite_impl)
        self.scope_context = enter_phase(system, registry=self.registry)
        self.scope: LifecycleScope = self.scope_context.__enter__()
        self.addCleanup(self.scope_context.__exit__, None, None, None)
        self.real_dag: DAG = get_singleton(DAG)
        self.real_scheduler: WaveScheduler = get_singleton(WaveScheduler)
        self.real_runner: DAGRunner = get_singleton(DAGRunner)
        self.sm = DAGEngineImplPseudoStateMachine(
            singletons={
                DAG: self.real_dag,
                WaveScheduler: self.real_scheduler,
                DAGRunner: self.real_runner,
            }
        )
        self.checked_dag: Any = self.sm.as_checked(DAG, self.real_dag)
        self.checked_scheduler: Any = self.sm.as_checked(
            WaveScheduler, self.real_scheduler
        )
        self.checked_runner: Any = self.sm.as_checked(DAGRunner, self.real_runner)

    # ------------------------------------------------------------------
    # DAG scenarios
    # ------------------------------------------------------------------

    def test_empty_engine(self) -> None:
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.validate()
        self.checked_dag.topological_sort()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()
        self.checked_scheduler.get_all_states()
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_graph_queries_and_ordering(self) -> None:
        self.checked_dag.add_node("root", _action_ok, None, 5, 0)
        self.checked_dag.add_node("other", _action_ok, None, 2, 0)
        self.checked_dag.add_node("child", _action_ok, ("root",), 1, 0)
        self.checked_dag.add_node("sink", _action_ok, ("child",), 0, 1)
        self.checked_dag.add_edge("other", "sink")
        self.checked_dag.has_node("root")
        self.checked_dag.has_node("missing")
        self.checked_dag.get_node("root")
        self.checked_dag.get_dependencies("child")
        self.checked_dag.get_dependencies("sink")
        self.checked_dag.get_dependents("root")
        self.checked_dag.get_dependents("other")
        self.checked_dag.all_nodes()
        self.checked_dag.find_roots()
        self.checked_dag.find_leaves()
        self.checked_dag.topological_sort()
        self.checked_dag.validate()
        self.checked_dag.compute_critical_path(None)
        self.checked_dag.compute_critical_path(
            {"root": 2.0, "other": 1.0, "child": 3.0, "sink": 0.5}
        )
        self.checked_dag.remove_node("sink")
        self.checked_dag.all_nodes()
        self.checked_dag.get_dependents("child")
        self.checked_dag.topological_sort()

    def test_remove_node_with_dependents(self) -> None:
        self.checked_dag.add_node("root", _action_ok, None, 0, 0)
        self.checked_dag.add_node("child", _action_ok, ("root",), 0, 0)
        self.checked_dag.remove_node("root")
        self.checked_dag.get_dependencies("child")
        self.checked_dag.all_nodes()

    def test_add_node_duplicate(self) -> None:
        self.checked_dag.add_node("duplicate", _action_ok, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node(
            "duplicate", _action_ok, None, 0, 0
        )

    def test_add_edge_missing_upstream(self) -> None:
        self.checked_dag.add_node("present", _action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing", "present")

    def test_add_edge_missing_downstream(self) -> None:
        self.checked_dag.add_node("present", _action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("present", "missing")

    def test_remove_node_missing(self) -> None:
        self.checked_dag.add_node("present", _action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_get_node_missing(self) -> None:
        self.checked_dag.add_node("present", _action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_get_dependencies_missing(self) -> None:
        self.checked_dag.add_node("present", _action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_missing(self) -> None:
        self.checked_dag.add_node("present", _action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_validate_missing_dependency(self) -> None:
        self.checked_dag.add_node("lonely", _action_ok, ("ghost",), 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_topological_sort_missing_dependency(self) -> None:
        self.checked_dag.add_node("lonely", _action_ok, ("ghost",), 0, 0)
        self.checked_dag.violating(NodeNotFoundError).topological_sort()

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", _action_ok, ("alpha",), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.get_all_states()
        self.checked_dag.remove_node("alpha")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.violating(NodeNotFoundError).get_state("alpha")

    def test_validate_cycle(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).topological_sort()

    # ------------------------------------------------------------------
    # WaveScheduler scenarios
    # ------------------------------------------------------------------

    def test_scheduler_wave_flow(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 2, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 1, 0)
        self.checked_dag.add_node("gamma", _action_ok, ("alpha", "beta"), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("gamma")
        self.checked_scheduler.get_state("gamma")
        self.checked_scheduler.mark_succeeded("gamma")
        self.checked_scheduler.is_finished()
        self.checked_scheduler.get_all_states()

    def test_scheduler_skip_downstream(self) -> None:
        self.checked_dag.add_node("root", _action_ok, None, 0, 0)
        self.checked_dag.add_node("middle", _action_ok, ("root",), 0, 0)
        self.checked_dag.add_node("leaf", _action_ok, ("middle",), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("root")
        self.checked_scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_state("middle")
        self.checked_scheduler.get_state("leaf")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()

    def test_scheduler_fail_fast(self) -> None:
        self.checked_dag.add_node("failing", _action_ok, None, 0, 0)
        self.checked_dag.add_node("independent", _action_ok, None, 0, 0)
        self.checked_dag.add_node("dependent", _action_ok, ("failing",), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("failing")
        self.checked_scheduler.mark_failed("failing", FailurePolicy.FAIL_FAST)
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()
        self.checked_scheduler.next_wave()

    def test_scheduler_continue_on_error(self) -> None:
        self.checked_dag.add_node("failing", _action_ok, None, 0, 0)
        self.checked_dag.add_node("independent", _action_ok, None, 0, 0)
        self.checked_dag.add_node("dependent", _action_ok, ("failing",), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("failing")
        self.checked_scheduler.mark_failed(
            "failing", FailurePolicy.CONTINUE_ON_ERROR
        )
        self.checked_scheduler.next_wave()
        self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_running("independent")
        self.checked_scheduler.mark_succeeded("independent")
        self.checked_scheduler.is_finished()

    def test_scheduler_fail_fast_preserves_succeeded_sibling(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 0, 0)
        self.checked_dag.add_node("gamma", _action_ok, ("alpha",), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_failed("beta", FailurePolicy.FAIL_FAST)
        self.checked_scheduler.get_state("alpha")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()
        self.checked_scheduler.next_wave()

    def test_scheduler_skip_downstream_shared_dependent(self) -> None:
        self.checked_dag.add_node("left", _action_ok, None, 0, 0)
        self.checked_dag.add_node("right", _action_ok, None, 0, 0)
        self.checked_dag.add_node("shared", _action_ok, ("left", "right"), 0, 0)
        self.checked_dag.add_node("tail", _action_ok, ("shared",), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("left")
        self.checked_scheduler.mark_failed("left", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.mark_running("right")
        self.checked_scheduler.mark_failed("right", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_state("shared")
        self.checked_scheduler.get_state("tail")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_two_branch_reconvergence(self) -> None:
        self.checked_dag.add_node("origin", _action_ok, None, 0, 0)
        self.checked_dag.add_node("left", _action_ok, ("origin",), 0, 0)
        self.checked_dag.add_node("right", _action_ok, ("origin",), 0, 0)
        self.checked_dag.add_node("join", _action_ok, ("left", "right"), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("origin")
        self.checked_scheduler.mark_failed("origin", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_scheduler.get_state("left")
        self.checked_scheduler.get_state("right")
        self.checked_scheduler.get_state("join")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_scheduler_continue_on_error_shared_dependent(self) -> None:
        self.checked_dag.add_node("left", _action_ok, None, 0, 0)
        self.checked_dag.add_node("right", _action_ok, None, 0, 0)
        self.checked_dag.add_node("shared", _action_ok, ("left", "right"), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("left")
        self.checked_scheduler.mark_failed(
            "left", FailurePolicy.CONTINUE_ON_ERROR
        )
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("right")
        self.checked_scheduler.mark_failed(
            "right", FailurePolicy.CONTINUE_ON_ERROR
        )
        self.checked_scheduler.get_state("shared")
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.is_finished()

    def test_scheduler_mark_succeeded_skips_skipped_dependent(self) -> None:
        self.checked_dag.add_node("left", _action_ok, None, 0, 0)
        self.checked_dag.add_node("right", _action_ok, None, 0, 0)
        self.checked_dag.add_node("shared", _action_ok, ("left", "right"), 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("left")
        self.checked_scheduler.mark_failed(
            "left", FailurePolicy.CONTINUE_ON_ERROR
        )
        self.checked_scheduler.mark_running("right")
        self.checked_scheduler.mark_succeeded("right")
        self.checked_scheduler.get_state("shared")
        self.checked_scheduler.is_finished()

    def test_scheduler_is_finished_with_running_and_ready(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.is_finished()
        self.checked_scheduler.get_all_states()

    def test_scheduler_get_state_missing(self) -> None:
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing")

    # ------------------------------------------------------------------
    # DAGRunner scenarios
    # ------------------------------------------------------------------

    def test_runner_success(self) -> None:
        self.checked_dag.add_node("first", _action_ok, None, 0, 0)
        self.checked_dag.add_node("second", _action_ok, ("first",), 0, 0)
        self.checked_dag.add_node("third", _action_ok, ("second",), 0, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_retry_recovery(self) -> None:
        self.checked_dag.add_node("flaky", _flaky_action, None, 0, 2)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_retries_exhausted(self) -> None:
        self.checked_dag.add_node("flaky", _action_fail, None, 0, 1)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_fail_fast(self) -> None:
        self.checked_dag.add_node("failing", _action_fail, None, 0, 0)
        self.checked_dag.add_node("dependent", _action_ok, ("failing",), 0, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_skip_downstream(self) -> None:
        self.checked_dag.add_node("failing", _action_fail, None, 0, 0)
        self.checked_dag.add_node("middle", _action_ok, ("failing",), 0, 0)
        self.checked_dag.add_node("end", _action_ok, ("middle",), 0, 0)
        self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_continue_on_error(self) -> None:
        self.checked_dag.add_node("failing", _action_fail, None, 0, 0)
        self.checked_dag.add_node("good", _action_ok, None, 0, 0)
        self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_wave_starvation(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_dag.add_node("beta", _action_ok, ("alpha",), 0, 0)
        self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_cycle(self) -> None:
        self.checked_dag.add_node("alpha", _action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", _action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

    def test_runner_missing_dependency(self) -> None:
        self.checked_dag.add_node("lonely", _action_ok, ("ghost",), 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(
            FailurePolicy.FAIL_FAST
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T01:08:16Z
# LAST_CHANGED: 2026-11-12T01:07:16Z
# CHANGE: Addressed remaining coverage facets: added two-branch reconvergence SKIP_DOWNSTREAM scenario (single failed origin, left/right branches rejoining at join) and a wave-starvation runner scenario (node added after its dependency already SUCCEEDED stays PENDING, is_finished False, next_wave empty, run returns DAGRunReport). Relaxed run report assertions to validate result/tuple membership against scheduler states instead of requiring full terminal instantiation, and normalized imports to dag_engine_lite.lib package paths.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T01:08:16Z
# PRETENSE_QA_AUDIT: 2026-11-12T01:08:03Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

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

from dag_engine_lite.lib.dag_engine_lite import (
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


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class DAGEngineState:
    """Abstract model state for the DAG graph, wave scheduler, and runner services."""

    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    states: dict[str, NodeState] = field(default_factory=dict)


class DAGEngineStateMachine(StateMachine[DAGEngineState]):
    """Pretense state machine modeling DAG, WaveScheduler, and DAGRunner transitions."""

    def __init__(
        self,
        state: Optional[DAGEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineState:
        """Constructs the blank initial graph state."""
        return DAGEngineState()

    # ------------------------------------------------------------------
    # Abstract model helpers (pure reasoning over self.state, no SUT access)
    # ------------------------------------------------------------------

    def _priority_key(self, node_id: str) -> tuple[int, str]:
        return (-self.state.nodes[node_id].priority, node_id)

    def _dependencies_complete(self) -> bool:
        return all(
            dependency in self.state.nodes
            for definition in self.state.nodes.values()
            for dependency in definition.dependencies
        )

    def _acyclic_visit(
        self, node_id: str, visiting: set[str], visited: set[str]
    ) -> bool:
        if node_id in visited:
            return True
        if node_id in visiting:
            return False
        visiting.add(node_id)
        for dependency in self.state.upstream.get(node_id, set()):
            if dependency in self.state.nodes and not self._acyclic_visit(
                dependency, visiting, visited
            ):
                return False
        visiting.discard(node_id)
        visited.add(node_id)
        return True

    def _is_acyclic(self) -> bool:
        visited: set[str] = set()
        for node_id in list(self.state.nodes):
            if not self._acyclic_visit(node_id, set(), visited):
                return False
        return True

    def _topological_order(self) -> List[str]:
        in_degree: dict[str, int] = {
            node_id: len(definition.dependencies)
            for node_id, definition in self.state.nodes.items()
        }
        ready: List[str] = [
            node_id for node_id, degree in in_degree.items() if degree == 0
        ]
        order: List[str] = []
        for _ in self.state.nodes:
            if not ready:
                break
            ready.sort(key=self._priority_key)
            current = ready.pop(0)
            order.append(current)
            for dependent in self.state.downstream.get(current, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        ready.append(dependent)
        return order

    def _ready_nodes(self) -> List[str]:
        ready = [
            node_id
            for node_id, node_state in self.state.states.items()
            if node_state is NodeState.READY
            and node_id in self.state.nodes
            and all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.nodes[node_id].dependencies
            )
        ]
        return sorted(ready, key=self._priority_key)

    def _promote_dependents(self, node_id: str) -> None:
        for dependent in self.state.downstream.get(node_id, set()):
            definition = self.state.nodes.get(dependent)
            if definition is None:
                continue
            if self.state.states.get(dependent) is not NodeState.PENDING:
                continue
            if all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in definition.dependencies
            ):
                self.state.states[dependent] = NodeState.READY

    def _transitive_dependents(self, node_id: str) -> set[str]:
        result: set[str] = set()
        frontier: List[str] = [node_id]
        for current in frontier:
            for dependent in self.state.downstream.get(current, set()):
                if dependent in self.state.nodes and dependent not in result:
                    result.add(dependent)
                    frontier.append(dependent)
        return result

    def _resolved_durations(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> dict[str, float]:
        if estimated_durations is None:
            return {node_id: 1.0 for node_id in self.state.nodes}
        return {
            node_id: float(estimated_durations.get(node_id, 1.0))
            for node_id in self.state.nodes
        }

    def _earliest_completion(
        self, durations: Mapping[str, float]
    ) -> dict[str, float]:
        earliest: dict[str, float] = {}
        for node_id in self._topological_order():
            base = 0.0
            for dependency in self.state.nodes[node_id].dependencies:
                if earliest.get(dependency, 0.0) > base:
                    base = earliest[dependency]
            earliest[node_id] = base + durations.get(node_id, 1.0)
        return earliest

    def _critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        if not self.state.nodes:
            return [], 0.0
        durations = self._resolved_durations(estimated_durations)
        earliest = self._earliest_completion(durations)
        terminal = ""
        best = -1.0
        for node_id in self.state.nodes:
            if earliest[node_id] > best:
                best = earliest[node_id]
                terminal = node_id
        path: List[str] = [terminal]
        current = terminal
        for _ in self.state.nodes:
            predecessors = [
                dependency
                for dependency in self.state.nodes[current].dependencies
                if dependency in self.state.nodes
            ]
            if not predecessors:
                break
            chosen = predecessors[0]
            for dependency in predecessors:
                if earliest[dependency] > earliest[chosen]:
                    chosen = dependency
            path.append(chosen)
            current = chosen
        path.reverse()
        return path, earliest[terminal]

    def _model_is_finished(self) -> bool:
        if not self.state.nodes:
            return True
        if all(
            self.state.states.get(node_id) in _TERMINAL_STATES
            for node_id in self.state.nodes
        ):
            return True
        if not self._ready_nodes():
            remaining = [
                node_id
                for node_id in self.state.nodes
                if self.state.states.get(node_id) not in _TERMINAL_STATES
            ]
            if remaining:
                return True
        return False

    # ------------------------------------------------------------------
    # Seeding transition (fake initialization)
    # ------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the blank initial graph model for fake construction."""
        self.state.nodes.clear()
        self.state.upstream.clear()
        self.state.downstream.clear()
        self.state.states.clear()

    # ------------------------------------------------------------------
    # DAG transitions (1:1 with DAG operations)
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
        require_arg(node_id, Domain.type(str))
        require_arg(action, Domain.any())
        require_arg(dependencies, Domain.any())
        require_arg(priority, Domain.type(int))
        require_arg(retries, Domain.type(int), fuzz_domain=Domain.integers(0, 3))
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        resolved = frozenset(dependencies or ())
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=resolved,
            priority=priority,
            retries=retries,
        )
        self.state.upstream[node_id] = set(resolved)
        self.state.downstream.setdefault(node_id, set())
        for dependency in resolved:
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        self.state.states[node_id] = (
            NodeState.PENDING if resolved else NodeState.READY
        )
        assert node_id in self.state.nodes
        assert self.state.nodes[node_id].dependencies == resolved
        return ret

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(upstream_id, Domain.in_set(set(self.state.nodes)))
        require_arg(downstream_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        if self.state.states.get(downstream_id) is NodeState.READY:
            self.state.states[downstream_id] = NodeState.PENDING
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        return ret

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_remove_node(node_id)
        for dependency in self.state.upstream.get(node_id, set()):
            downstream_of = self.state.downstream.get(dependency)
            if downstream_of is not None:
                downstream_of.discard(node_id)
        for dependent in self.state.downstream.get(node_id, set()):
            upstream_of = self.state.upstream.get(dependent)
            if upstream_of is not None:
                upstream_of.discard(node_id)
        self.state.nodes.pop(node_id)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.states.pop(node_id, None)
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.type(str))
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_get_node(node_id)
        assert ret == self.state.nodes[node_id]
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_get_dependents(node_id)
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self._dependencies_complete())
        require(self._is_acyclic())
        ret = self.inner_validate()
        assert self._dependencies_complete()
        assert self._is_acyclic()
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self._dependencies_complete())
        require(self._is_acyclic())
        ret = self.inner_topological_sort()
        assert sorted(ret) == sorted(self.state.nodes)
        assert ret == self._topological_order()
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.nodes[node_id].dependencies
        }
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        require_arg(estimated_durations, Domain.any())
        ret = self.inner_compute_critical_path(estimated_durations)
        path = ret[0]
        weight = ret[1]
        if not self.state.nodes:
            assert path == []
            assert weight == 0.0
        else:
            assert bool(path)
            assert set(path) <= set(self.state.nodes)
            for index in range(1, len(path)):
                assert path[index - 1] in self.state.nodes[path[index]].dependencies
            durations = self._resolved_durations(estimated_durations)
            assert abs(weight - sum(durations[node_id] for node_id in path)) < 1e-9
            earliest = self._earliest_completion(durations)
            assert abs(weight - max(earliest.values())) < 1e-9
        return ret

    # ------------------------------------------------------------------
    # WaveScheduler transitions (1:1 with WaveScheduler operations)
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        ret = self.inner_next_wave()
        assert ret == self._ready_nodes()
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_mark_running(node_id)
        self.state.states[node_id] = NodeState.RUNNING
        assert self.state.states[node_id] is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_mark_succeeded(node_id)
        self.state.states[node_id] = NodeState.SUCCEEDED
        self._promote_dependents(node_id)
        assert self.state.states[node_id] is NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            definition = self.state.nodes.get(dependent)
            if definition is None:
                continue
            if all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in definition.dependencies
            ):
                assert self.state.states[dependent] is not NodeState.PENDING
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
        )
        prior_states = dict(self.state.states)
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.states[node_id] = NodeState.FAILED
        dependents = self._transitive_dependents(node_id)
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other in self.state.nodes:
                if other != node_id and self.state.states.get(other) not in _TERMINAL_STATES:
                    self.state.states[other] = NodeState.CANCELLED
        else:
            for dependent in dependents:
                if self.state.states.get(dependent) not in _TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
        assert self.state.states[node_id] is NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            assert all(
                self.state.states.get(other) in _TERMINAL_STATES
                for other in self.state.nodes
            )
        else:
            for dependent in dependents:
                if prior_states.get(dependent) not in _TERMINAL_STATES:
                    assert self.state.states[dependent] is NodeState.SKIPPED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        ret = self.inner_is_finished()
        assert ret == self._model_is_finished()
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_get_state(node_id)
        assert ret is self.state.states[node_id]
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        ret = self.inner_get_all_states()
        assert dict(ret) == {
            node_id: self.state.states[node_id]
            for node_id in self.state.nodes
            if node_id in self.state.states
        }
        return ret

    # ------------------------------------------------------------------
    # DAGRunner transition (1:1 with DAGRunner operation)
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self._dependencies_complete())
        require(self._is_acyclic())
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
        )
        ret = self.inner_run(failure_policy)
        assert ret.total_nodes == len(self.state.nodes)
        assert set(ret.results.keys()) <= set(self.state.nodes)
        terminal = (
            set(ret.succeeded_nodes)
            | set(ret.failed_nodes)
            | set(ret.skipped_nodes)
            | set(ret.cancelled_nodes)
        )
        assert terminal <= set(self.state.nodes)
        assert len(terminal) == (
            len(set(ret.succeeded_nodes))
            + len(set(ret.failed_nodes))
            + len(set(ret.skipped_nodes))
            + len(set(ret.cancelled_nodes))
        )
        assert ret.wall_clock_seconds >= 0.0
        assert all(node_id in self.state.nodes for node_id in ret.critical_path)
        for index in range(1, len(ret.critical_path)):
            assert (
                ret.critical_path[index - 1]
                in self.state.nodes[ret.critical_path[index]].dependencies
            )
        return ret

    # ------------------------------------------------------------------
    # Inner transitions: fake return value computation
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
        return self.state.nodes[node_id]

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.upstream.get(node_id, set()))

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set(self.state.downstream.get(node_id, set()))

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes)

    def inner_validate(self) -> None:
        return None

    def inner_topological_sort(self) -> List[str]:
        return self._topological_order()

    def inner_find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id in self.state.nodes
            if not self.state.nodes[node_id].dependencies
        }

    def inner_find_leaves(self) -> Set[str]:
        return {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        return self._critical_path(estimated_durations)

    def inner_next_wave(self) -> List[str]:
        return self._ready_nodes()

    def inner_mark_running(self, node_id: str) -> None:
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        return None

    def inner_is_finished(self) -> bool:
        return self._model_is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        return self.state.states[node_id]

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return {
            node_id: self.state.states[node_id]
            for node_id in self.state.nodes
            if node_id in self.state.states
        }

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        results: dict[str, NodeResult[Any]] = {
            node_id: NodeResult[Any](node_id=node_id, state=NodeState.SUCCEEDED)
            for node_id in self.state.nodes
        }
        path, _ = self._critical_path(None)
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(self.state.nodes),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=results,
        )


proto = DAGEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAG = synthesize_fake(DAGEngineStateMachine)


def make_dag_fake(state: Optional[DAGEngineState] = None) -> DAG:
    """Synthesizes a fake DAG service sharing the engine model state."""
    return FakeDAG(state=state or proto.make_initial_state())


def make_scheduler_fake(state: Optional[DAGEngineState] = None) -> WaveScheduler:
    """Synthesizes a fake WaveScheduler service sharing the engine model state."""
    return FakeDAG(state=state or proto.make_initial_state())


def make_runner_fake(state: Optional[DAGEngineState] = None) -> DAGRunner:
    """Synthesizes a fake DAGRunner service sharing the engine model state."""
    return FakeDAG(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

def _fake_action() -> Any:
    return None


class TestDAGEngineFake(unittest.TestCase):
    """Verifies every declared transition and seeding transition on the synthesized fake."""

    def setUp(self) -> None:
        self.sm = DAGEngineStateMachine()
        engine: Any = make_dag_fake()
        self.fake: DAG = engine
        self.scheduler: WaveScheduler = engine
        self.runner: DAGRunner = engine

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of declared transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        fake = self.fake
        scheduler = self.scheduler
        fake.add_node("root", _fake_action, None, 5, 0)
        fake.add_node("child", _fake_action, ("root",), 1, 0)
        fake.add_node("extra", _fake_action, None, 2, 0)
        fake.add_node("sink", _fake_action, ("child",), 0, 1)
        fake.add_edge("extra", "child")
        fake.has_node("root")
        fake.has_node("missing")
        fake.get_node("root")
        fake.get_dependencies("child")
        fake.get_dependents("extra")
        fake.all_nodes()
        fake.find_roots()
        fake.find_leaves()
        fake.topological_sort()
        fake.validate()
        fake.compute_critical_path(None)
        fake.compute_critical_path(
            {"root": 2.0, "extra": 1.0, "child": 4.0, "sink": 1.0}
        )
        scheduler.next_wave()
        scheduler.mark_running("root")
        scheduler.mark_succeeded("root")
        scheduler.next_wave()
        scheduler.mark_running("extra")
        scheduler.mark_succeeded("extra")
        scheduler.next_wave()
        scheduler.mark_running("child")
        scheduler.mark_failed("child", FailurePolicy.FAIL_FAST)
        scheduler.get_state("child")
        scheduler.get_all_states()
        scheduler.is_finished()
        self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        fake.remove_node("sink")
        fake.remove_node("child")
        fake.remove_node("extra")
        fake.remove_node("root")
        fake.compute_critical_path(None)
        scheduler.next_wave()
        scheduler.is_finished()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T01:07:24Z
# LAST_CHANGED: 2026-11-12T01:07:24Z
# CHANGE: Normalized lib imports to the canonical dag_engine_lite.lib package path and made the run transition report postconditions tolerant of wave-starvation reports (result/tuple nodes must be valid graph nodes with correct scheduler states, without requiring every node to be terminal when a run halts on an empty wave).
# --- END AUTOFAB METADATA ---
