# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, Mapping, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib import dag_engine_lite_impl
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
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineStateMachine,
    FakeDAGEngine,
    action_fail,
    action_ok,
    action_text,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DAGEngineImplPseudoStateMachine(DAGEngineStateMachine):
    """Implementation pseudo-state machine binding the concrete DAG engine SUT."""

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

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        target.add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        target.remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        return target.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> set[str]:
        target: DAG = sut(DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> set[str]:
        target: DAG = sut(DAG)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> set[str]:
        target: DAG = sut(DAG)
        return target.all_nodes()

    def inner_validate(self) -> None:
        target: DAG = sut(DAG)
        target.validate()

    def inner_topological_sort(self) -> list[str]:
        target: DAG = sut(DAG)
        return target.topological_sort()

    def inner_find_roots(self) -> set[str]:
        target: DAG = sut(DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> set[str]:
        target: DAG = sut(DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        target: DAG = sut(DAG)
        return target.compute_critical_path(estimated_durations)

    def inner_next_wave(self) -> list[str]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_succeeded(node_id)

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_all_states()

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        return target.run(failure_policy)


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDAGEngineImplReal(LifecycleTestCase):
    """Verifies that the concrete DAG engine implementation satisfies contracts."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DAGEngineImplPseudoStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.scheduler,
                DAGRunner: self.runner,
            },
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.runner)

    def test_graph_lifecycle(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 1, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.validate()
        self.assertTrue(self.checked_dag.has_node("alpha"))
        self.assertEqual(self.checked_dag.get_dependencies("beta"), {"alpha"})
        self.assertEqual(self.checked_dag.get_dependents("alpha"), {"beta"})
        self.assertEqual(self.checked_dag.find_roots(), {"alpha"})
        self.assertEqual(self.checked_dag.find_leaves(), {"beta"})
        self.assertEqual(self.checked_dag.topological_sort(), ["alpha", "beta"])
        self.checked_dag.remove_node("beta")
        self.assertFalse(self.checked_dag.has_node("beta"))

    def test_add_node_with_dependencies(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_dag.add_node("gamma", action_ok, frozenset({"alpha"}), 0, 0)
        self.checked_dag.validate()
        self.assertEqual(self.checked_dag.get_dependencies("gamma"), {"alpha"})
        self.assertEqual(self.checked_dag.get_node("gamma").dependencies, frozenset({"alpha"}))
        self.assertEqual(self.checked_dag.find_roots(), {"alpha", "beta"})
        self.assertEqual(self.checked_dag.topological_sort(), ["alpha", "beta", "gamma"])

    def test_add_node_duplicate_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node("alpha", action_ok, None, 0, 0)

    def test_add_edge_missing_endpoint_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("alpha", "missing")

    def test_remove_node_missing_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_remove_node_purges_incident_edges(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_dag.add_node("gamma", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "gamma")
        self.checked_dag.remove_node("beta")
        self.assertEqual(self.checked_dag.all_nodes(), {"alpha", "gamma"})
        self.assertEqual(self.checked_dag.get_dependents("alpha"), set())
        self.assertEqual(self.checked_dag.get_dependencies("gamma"), set())

    def test_remove_node_purges_scheduler_state(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_scheduler.get_all_states()
        self.checked_dag.remove_node("beta")
        states = self.checked_scheduler.get_all_states()
        self.assertEqual(set(states.keys()), {"alpha"})

    def test_get_node_missing_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_get_dependencies_missing_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_missing_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_validate_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_dag.add_node("gamma", action_ok, frozenset({"alpha"}), 0, 0)
        self.checked_dag.remove_node("alpha")
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_scheduler_lifecycle(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 1, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.assertEqual(self.checked_scheduler.next_wave(), ["alpha"])
        self.checked_scheduler.mark_running("alpha")
        self.assertEqual(self.checked_scheduler.get_state("alpha"), NodeState.RUNNING)
        self.checked_scheduler.mark_succeeded("alpha")
        self.assertEqual(self.checked_scheduler.next_wave(), ["beta"])

    def test_mark_succeeded_promotes_ready_dependent(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_scheduler.get_all_states()
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_scheduler.mark_succeeded("alpha")
        states = self.checked_scheduler.get_all_states()
        self.assertEqual(states["alpha"], NodeState.SUCCEEDED)
        self.assertEqual(states["beta"], NodeState.READY)

    def test_next_wave_promotes_pending_dependent(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["alpha", "beta"])
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_dag.add_node("gamma", action_ok, frozenset({"alpha"}), 0, 0)
        self.assertEqual(self.checked_scheduler.next_wave(), ["beta", "gamma"])
        self.assertEqual(self.checked_scheduler.get_state("gamma"), NodeState.READY)

    def test_mark_failed_fail_fast(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_dag.add_node("delta", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        states = self.checked_scheduler.get_all_states()
        self.assertEqual(states["alpha"], NodeState.FAILED)
        self.assertEqual(states["beta"], NodeState.CANCELLED)
        self.assertEqual(states["delta"], NodeState.CANCELLED)
        self.assertTrue(self.checked_scheduler.is_finished())

    def test_mark_failed_skip_downstream_diamond(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_dag.add_node("gamma", action_ok, None, 0, 0)
        self.checked_dag.add_node("delta", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("alpha", "gamma")
        self.checked_dag.add_edge("beta", "delta")
        self.checked_dag.add_edge("gamma", "delta")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        states = self.checked_scheduler.get_all_states()
        self.assertEqual(states["beta"], NodeState.SKIPPED)
        self.assertEqual(states["gamma"], NodeState.SKIPPED)
        self.assertEqual(states["delta"], NodeState.SKIPPED)

    def test_mark_failed_continue_on_error(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_dag.add_node("gamma", action_ok, None, 0, 0)
        self.checked_dag.add_node("delta", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "gamma")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        states = self.checked_scheduler.get_all_states()
        self.assertEqual(states["beta"], NodeState.SKIPPED)
        self.assertEqual(states["gamma"], NodeState.SKIPPED)
        self.assertEqual(states["delta"], NodeState.READY)
        self.assertFalse(self.checked_scheduler.is_finished())

    def test_is_finished_blocked_by_failure(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_scheduler.get_all_states()
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        self.checked_dag.add_edge("alpha", "beta")
        self.assertTrue(self.checked_scheduler.is_finished())

    def test_get_state_missing_error(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing")

    def test_runner_lifecycle(self) -> None:
        self.checked_dag.add_node("alpha", action_ok, None, 0, 0)
        self.checked_dag.add_node("beta", action_text, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("alpha", "beta"))

    def test_runner_retry_failures(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 0, 2)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("alpha",))
        self.assertEqual(report.skipped_nodes, ("beta",))
        self.assertEqual(report.results["alpha"].state, NodeState.FAILED)
        self.assertEqual(report.results["beta"].state, NodeState.SKIPPED)

    def test_runner_fail_fast_policy(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 5, 0)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_dag.add_node("delta", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("alpha",))
        self.assertEqual(report.cancelled_nodes, ("beta", "delta"))
        self.assertEqual(report.results["beta"].state, NodeState.CANCELLED)
        self.assertEqual(report.results["delta"].state, NodeState.CANCELLED)

    def test_runner_consolidated_report(self) -> None:
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_ok, None, 0, 0)
        self.checked_dag.add_node("gamma", action_ok, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "gamma")
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ("alpha",))
        self.assertEqual(report.skipped_nodes, ("beta", "gamma"))
        self.assertEqual(report.results["beta"].state, NodeState.SKIPPED)
        self.assertEqual(report.results["gamma"].state, NodeState.SKIPPED)
        self.assertEqual(report.critical_path, ("alpha", "beta", "gamma"))


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> DAG:
    """Constructs a fresh DAG engine service scope for one fuzz test run."""
    registry = LifecycleRegistry()
    registry.register_singleton(DAGImpl, keys=[DAGImpl, DAG], tier=system)
    registry.register_singleton(WaveSchedulerImpl, keys=[WaveSchedulerImpl, WaveScheduler], tier=system)
    registry.register_singleton(DAGRunnerImpl, keys=[DAGRunnerImpl, DAGRunner], tier=system)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(DAG)


proto = DAGEngineImplPseudoStateMachine()

DAGEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DAGEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T18:43:37Z
# LAST_CHANGED: 2026-11-14T18:32:35Z
# CHANGE: Resolve [from:pretense_coverage] facets by adding fixed real-SUT scenario tests: duplicate-node/add-edge/remove-node/get_node/get_dependencies/get_dependents/validate/topological_sort/get_state contract violations via terminal checked.violating(...), non-empty dependency registration, incident-edge and scheduler-state purge, already-ready dependent promotion, next_wave pending promotion, FAIL_FAST/SKIP_DOWNSTREAM/CONTINUE_ON_ERROR policies (including diamond reconvergence and blocked is_finished), and runner retry/fail-fast/consolidated-report outcome records.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T18:43:37Z
# PRETENSE_QA_AUDIT: 2026-11-14T18:43:11Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import unittest
from typing import Any, Callable, Collection, Mapping, Optional

from pretense import (
    Env,
    StateMachine,
    domain,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
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
    NodeResult,
    NodeState,
    WaveScheduler,
)

# ==============================================================================
# 0. Test Action Doubles & Terminal Predicates
# ==============================================================================

def action_ok() -> int:
    """Deterministic successful node action returning an integer value."""
    return 1


def action_text() -> str:
    """Deterministic successful node action returning a string value."""
    return "done"


def action_fail() -> int:
    """Deterministic failing node action used to exercise failure policies."""
    raise RuntimeError("node action failed")


def _execute_action(action: Callable[[], Any]) -> tuple[bool, Any]:
    """Executes a pooled action and reports whether it succeeded."""
    try:
        return True, action()
    except RuntimeError:
        return False, None


TERMINAL_STATES = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)

BLOCKING_STATES = (
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)


def _make_action_pool() -> list[Callable[[], Any]]:
    """Builds the pool of deterministic actions available to graph fuzzing."""
    return [action_ok, action_text, action_fail]


def _make_available_ids() -> list[str]:
    """Builds the pool of identifier candidates eligible for add_node."""
    return ["alpha", "beta", "gamma", "delta", "epsilon", "n0", "n1", "n2", "n3", "n4"]


def _make_dependency_options() -> list[Optional[Collection[str]]]:
    """Builds the initial domain of dependency collections."""
    return [None]


def _make_duration_options() -> list[Optional[Mapping[str, float]]]:
    """Builds the initial domain of estimated-duration mappings."""
    return [None]


def _make_failure_policies() -> list[FailurePolicy]:
    """Builds the domain of supported failure policies."""
    return [
        FailurePolicy.FAIL_FAST,
        FailurePolicy.CONTINUE_ON_ERROR,
        FailurePolicy.SKIP_DOWNSTREAM,
    ]


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DAGEngineState:
    """Model state for the DAG graph, wave scheduler, and sequential runner."""

    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    scheduler_states: dict[str, NodeState] = field(default_factory=dict)
    running_nodes: set[str] = field(default_factory=set)
    results: dict[str, NodeResult[Any]] = field(default_factory=dict)
    acyclic: bool = True
    dependencies_complete: bool = True
    scheduler_active: bool = False
    ready_ids: set[str] = field(default_factory=set)
    active_ids: set[str] = field(default_factory=set)
    available_ids: list[str] = field(default_factory=_make_available_ids)
    action_pool: list[Callable[[], Any]] = field(default_factory=_make_action_pool)
    dependency_options: list[Optional[Collection[str]]] = field(default_factory=_make_dependency_options)
    duration_options: list[Optional[Mapping[str, float]]] = field(default_factory=_make_duration_options)
    failure_policies: list[FailurePolicy] = field(default_factory=_make_failure_policies)


class DAGEngineStateMachine(StateMachine[DAGEngineState]):
    """Pretense state machine modeling DAG, scheduler, and runner contracts."""

    def __init__(
        self,
        state: Optional[DAGEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineState:
        """Constructs the blank initial model state for fuzzing."""
        return DAGEngineState()

    # ------------------------------------------------------------------
    # Model queries (used by both the fake and implementation adapters)
    # ------------------------------------------------------------------

    def _priority(self, node_id: str) -> int:
        return self.state.nodes[node_id].priority

    def _order_nodes(self, node_ids: list[str]) -> list[str]:
        decorated = [(-self._priority(node_id), node_id) for node_id in node_ids]
        decorated.sort()
        return [node_id for _, node_id in decorated]

    def _reachable(self, start: str, goal: str) -> bool:
        if start == goal:
            return True
        seen: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            seen.add(current)
            for next_id in self.state.downstream.get(current, set()):
                if next_id == goal:
                    return True
                if next_id not in seen:
                    stack.append(next_id)
        return False

    def _descendants(self, node_id: str) -> set[str]:
        descendants: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            for next_id in self.state.downstream.get(current, set()):
                if next_id in self.state.nodes and next_id not in descendants:
                    descendants.add(next_id)
                    stack.append(next_id)
        return descendants

    def _recompute_validity(self) -> None:
        for definition in self.state.nodes.values():
            for dependency in definition.dependencies:
                if dependency not in self.state.nodes:
                    self.state.dependencies_complete = False
                    return
        self.state.dependencies_complete = True

    def _topological_order(self) -> list[str]:
        node_set = set(self.state.nodes)
        in_degree: dict[str, int] = {}
        for node_id in node_set:
            in_degree[node_id] = len(self.state.upstream.get(node_id, set()) & node_set)
        heap: list[tuple[int, str]] = []
        for node_id in node_set:
            if in_degree[node_id] == 0:
                heapq.heappush(heap, (-self._priority(node_id), node_id))
        order: list[str] = []
        while heap:
            _, node_id = heapq.heappop(heap)
            order.append(node_id)
            for dependent_id in sorted(self.state.downstream.get(node_id, set()) & node_set):
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    heapq.heappush(heap, (-self._priority(dependent_id), dependent_id))
        return order

    def _critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        order = self._topological_order()
        if not order:
            return [], 0.0
        earliest: dict[str, float] = {}
        parent: dict[str, Optional[str]] = {}
        for node_id in order:
            if estimated_durations is not None:
                duration = estimated_durations.get(node_id, 1.0)
            else:
                duration = 1.0
            predecessors = sorted(self.state.upstream.get(node_id, set()) & set(self.state.nodes))
            if not predecessors:
                earliest[node_id] = duration
                parent[node_id] = None
                continue
            best = predecessors[0]
            for candidate in predecessors:
                if (earliest.get(candidate, 0.0), candidate) > (earliest.get(best, 0.0), best):
                    best = candidate
            earliest[node_id] = earliest.get(best, 0.0) + duration
            parent[node_id] = best
        max_leaf = order[0]
        for candidate in order:
            if (earliest[candidate], candidate) > (earliest[max_leaf], max_leaf):
                max_leaf = candidate
        path: list[str] = []
        current: Optional[str] = max_leaf
        while current is not None:
            path.append(current)
            current = parent.get(current)
        path.reverse()
        return path, earliest[max_leaf]

    def _sync_scheduler_states(self) -> None:
        node_set = set(self.state.nodes)
        for node_id in list(self.state.scheduler_states):
            if node_id not in node_set:
                del self.state.scheduler_states[node_id]
        for node_id in node_set:
            if node_id not in self.state.scheduler_states:
                if self.state.upstream.get(node_id, set()):
                    self.state.scheduler_states[node_id] = NodeState.PENDING
                else:
                    self.state.scheduler_states[node_id] = NodeState.READY
        self._refresh_scheduler_sets()

    def _refresh_scheduler_sets(self) -> None:
        self.state.ready_ids = set(self._compute_wave())
        active_ids: set[str] = set()
        for node_id in self.state.nodes:
            if self.state.scheduler_states.get(node_id) not in TERMINAL_STATES:
                active_ids.add(node_id)
        self.state.active_ids = active_ids

    def _promote_dependents(self, node_id: str, states: dict[str, NodeState]) -> None:
        node_set = set(self.state.nodes)
        for dependent_id in self.state.downstream.get(node_id, set()) & node_set:
            if states.get(dependent_id) == NodeState.PENDING:
                dependencies = self.state.upstream.get(dependent_id, set())
                if all(states.get(dependency) == NodeState.SUCCEEDED for dependency in dependencies):
                    states[dependent_id] = NodeState.READY

    def _promote_satisfied(self, states: dict[str, NodeState]) -> None:
        for node_id in self.state.nodes:
            if states.get(node_id) == NodeState.PENDING:
                dependencies = self.state.upstream.get(node_id, set())
                if all(states.get(dependency) == NodeState.SUCCEEDED for dependency in dependencies):
                    states[node_id] = NodeState.READY

    def _compute_wave(self, states: Optional[dict[str, NodeState]] = None) -> list[str]:
        current = self.state.scheduler_states if states is None else states
        node_set = set(self.state.nodes)
        ready: list[str] = []
        for node_id in node_set:
            if current.get(node_id) != NodeState.READY:
                continue
            dependencies = self.state.upstream.get(node_id, set())
            if all(current.get(dependency) == NodeState.SUCCEEDED for dependency in dependencies):
                ready.append(node_id)
        return self._order_nodes(ready)

    def _apply_failure_policy(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
        states: dict[str, NodeState],
    ) -> None:
        node_set = set(self.state.nodes)
        if failure_policy == FailurePolicy.FAIL_FAST:
            for candidate in node_set:
                if states.get(candidate) not in TERMINAL_STATES:
                    states[candidate] = NodeState.CANCELLED
            return
        for descendant_id in self._descendants(node_id):
            if states.get(descendant_id) not in TERMINAL_STATES:
                states[descendant_id] = NodeState.SKIPPED

    def _compute_finished(self, states: Optional[dict[str, NodeState]] = None) -> bool:
        current = self.state.scheduler_states if states is None else states
        node_set = set(self.state.nodes)
        if not node_set:
            return True
        if all(current.get(node_id) in TERMINAL_STATES for node_id in node_set):
            return True
        if self._compute_wave(current):
            return False
        for node_id in node_set:
            if current.get(node_id) in TERMINAL_STATES:
                continue
            dependencies = self.state.upstream.get(node_id, set())
            if not any(current.get(dependency) in BLOCKING_STATES for dependency in dependencies):
                return False
        return True

    def _has_terminal_states(self) -> bool:
        return any(
            state in TERMINAL_STATES for state in self.state.scheduler_states.values()
        )

    def _predict_run(
        self,
        failure_policy: FailurePolicy,
    ) -> tuple[DAGRunReport, dict[str, NodeState]]:
        node_set = set(self.state.nodes)
        local: dict[str, NodeState] = {}
        for node_id in node_set:
            existing = self.state.scheduler_states.get(node_id)
            if existing is not None:
                local[node_id] = existing
            else:
                dependencies = self.state.upstream.get(node_id, set()) & node_set
                local[node_id] = NodeState.PENDING if dependencies else NodeState.READY
        results: dict[str, NodeResult[Any]] = {}
        for _ in range(len(node_set) + 1):
            wave = self._compute_wave(local)
            if not wave:
                break
            halted = False
            for node_id in wave:
                local[node_id] = NodeState.RUNNING
                definition = self.state.nodes[node_id]
                succeeded, value = _execute_action(definition.action)
                if succeeded:
                    results[node_id] = NodeResult(
                        node_id=node_id,
                        state=NodeState.SUCCEEDED,
                        value=value,
                    )
                    local[node_id] = NodeState.SUCCEEDED
                    self._promote_dependents(node_id, local)
                else:
                    results[node_id] = NodeResult(
                        node_id=node_id,
                        state=NodeState.FAILED,
                        error=RuntimeError("node action failed"),
                        retries_attempted=definition.retries,
                    )
                    local[node_id] = NodeState.FAILED
                    self._apply_failure_policy(node_id, failure_policy, local)
                    if failure_policy == FailurePolicy.FAIL_FAST:
                        halted = True
                        break
            if halted:
                break
        for node_id in node_set:
            if node_id not in results:
                results[node_id] = NodeResult(node_id=node_id, state=local[node_id])
        succeeded = tuple(sorted(
            node_id for node_id in node_set if results[node_id].state == NodeState.SUCCEEDED
        ))
        failed = tuple(sorted(
            node_id for node_id in node_set if results[node_id].state == NodeState.FAILED
        ))
        skipped = tuple(sorted(
            node_id for node_id in node_set if results[node_id].state == NodeState.SKIPPED
        ))
        cancelled = tuple(sorted(
            node_id for node_id in node_set if results[node_id].state == NodeState.CANCELLED
        ))
        path, _ = self._critical_path(None)
        report = DAGRunReport(
            total_nodes=len(node_set),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=results,
        )
        return report, local

    def _refresh_domains(self, node_id: str) -> None:
        self.state.dependency_options.append(None)
        peers = [peer for peer in self.state.nodes if peer != node_id]
        if peers:
            self.state.dependency_options.append(frozenset([peers[0]]))
        self.state.duration_options.append(None)
        self.state.duration_options.append({node_id: 2.0})

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
        retries: int,
    ) -> None:
        require_arg(node_id, self.state.available_ids, error=DuplicateNodeError)
        require_arg(action, self.state.action_pool)
        require_arg(dependencies, self.state.dependency_options)
        require_arg(priority, int)
        require_arg(retries, int)
        self.inner_add_node(node_id, action, dependencies, priority, retries)
        dependency_set = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dependency_set,
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream[node_id] = set(dependency_set)
        self.state.downstream.setdefault(node_id, set())
        for dependency in dependency_set:
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        if node_id in self.state.available_ids:
            self.state.available_ids.remove(node_id)
        self._recompute_validity()
        self._refresh_domains(node_id)
        self._refresh_scheduler_sets()
        assert sut(DAG).has_node(node_id)
        assert sut(DAG).all_nodes() == set(self.state.nodes)

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        return None

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(upstream_id, self.state.nodes)
        require_arg(downstream_id, self.state.nodes)
        creates_cycle = self._reachable(downstream_id, upstream_id)
        self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        if creates_cycle:
            self.state.acyclic = False
        self._refresh_scheduler_sets()
        assert upstream_id in sut(DAG).get_dependencies(downstream_id)
        assert downstream_id in sut(DAG).get_dependents(upstream_id)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        self.inner_remove_node(node_id)
        upstream_ids = set(self.state.upstream.get(node_id, set()))
        downstream_ids = set(self.state.downstream.get(node_id, set()))
        for upstream_id in upstream_ids:
            self.state.downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in downstream_ids:
            self.state.upstream.get(downstream_id, set()).discard(node_id)
        del self.state.nodes[node_id]
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.running_nodes.discard(node_id)
        self.state.results.pop(node_id, None)
        if node_id not in self.state.available_ids:
            self.state.available_ids.append(node_id)
        self._recompute_validity()
        self._sync_scheduler_states()
        assert not sut(DAG).has_node(node_id)
        assert sut(DAG).all_nodes() == set(self.state.nodes)

    def inner_remove_node(self, node_id: str) -> None:
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, str)
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert ret.dependencies == self.state.nodes[node_id].dependencies
        assert ret.priority == self.state.nodes[node_id].priority
        assert ret.retries == self.state.nodes[node_id].retries
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    def inner_get_dependencies(self, node_id: str) -> set[str]:
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_dependents(node_id)
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    def inner_get_dependents(self, node_id: str) -> set[str]:
        return set(self.state.downstream.get(node_id, set()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    def inner_all_nodes(self) -> set[str]:
        return set(self.state.nodes)

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.dependencies_complete)
        require(self.state.acyclic)
        self.inner_validate()

    def inner_validate(self) -> None:
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> list[str]:
        require(self.state.acyclic)
        expected = self._topological_order()
        ret = self.inner_topological_sort()
        assert ret == expected
        return ret

    def inner_topological_sort(self) -> list[str]:
        return self._topological_order()

    @transition(DAG.find_roots)
    def find_roots(self) -> set[str]:
        expected = self._model_roots()
        ret = self.inner_find_roots()
        assert ret == expected
        return ret

    def inner_find_roots(self) -> set[str]:
        return self._model_roots()

    def _model_roots(self) -> set[str]:
        roots: set[str] = set()
        for node_id in self.state.nodes:
            if not self.state.upstream.get(node_id, set()):
                roots.add(node_id)
        return roots

    @transition(DAG.find_leaves)
    def find_leaves(self) -> set[str]:
        expected = self._model_leaves()
        ret = self.inner_find_leaves()
        assert ret == expected
        return ret

    def inner_find_leaves(self) -> set[str]:
        return self._model_leaves()

    def _model_leaves(self) -> set[str]:
        leaves: set[str] = set()
        for node_id in self.state.nodes:
            if not self.state.downstream.get(node_id, set()):
                leaves.add(node_id)
        return leaves

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        require_arg(estimated_durations, self.state.duration_options)
        expected_path, expected_weight = self._critical_path(estimated_durations)
        ret = self.inner_compute_critical_path(estimated_durations)
        assert ret[0] == expected_path
        assert abs(ret[1] - expected_weight) < 1e-9
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        return self._critical_path(estimated_durations)

    # ------------------------------------------------------------------
    # Wave scheduler transitions
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> list[str]:
        self._sync_scheduler_states()
        self._promote_satisfied(self.state.scheduler_states)
        self._refresh_scheduler_sets()
        self.state.scheduler_active = True
        expected = self._compute_wave()
        ret = self.inner_next_wave()
        assert ret == expected
        return ret

    def inner_next_wave(self) -> list[str]:
        return self._compute_wave()

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        self._sync_scheduler_states()
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.ready_ids)
        self.inner_mark_running(node_id)
        self.state.scheduler_states[node_id] = NodeState.RUNNING
        self.state.running_nodes.add(node_id)
        self.state.scheduler_active = True
        self._refresh_scheduler_sets()
        assert sut(WaveScheduler).get_state(node_id) == NodeState.RUNNING

    def inner_mark_running(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        self._sync_scheduler_states()
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.active_ids)
        self.inner_mark_succeeded(node_id)
        self.state.scheduler_states[node_id] = NodeState.SUCCEEDED
        self.state.running_nodes.discard(node_id)
        self.state.scheduler_active = True
        self._promote_dependents(node_id, self.state.scheduler_states)
        self._refresh_scheduler_sets()
        expected = {
            current_id: self.state.scheduler_states[current_id]
            for current_id in self.state.nodes
            if current_id in self.state.scheduler_states
        }
        assert dict(sut(WaveScheduler).get_all_states()) == expected

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        self._sync_scheduler_states()
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.active_ids)
        require_arg(failure_policy, self.state.failure_policies)
        self.inner_mark_failed(node_id, failure_policy)
        self.state.scheduler_states[node_id] = NodeState.FAILED
        self.state.running_nodes.discard(node_id)
        self.state.scheduler_active = True
        self._apply_failure_policy(node_id, failure_policy, self.state.scheduler_states)
        self._refresh_scheduler_sets()
        expected = {
            current_id: self.state.scheduler_states[current_id]
            for current_id in self.state.nodes
            if current_id in self.state.scheduler_states
        }
        assert dict(sut(WaveScheduler).get_all_states()) == expected

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        self._sync_scheduler_states()
        expected = self._compute_finished()
        ret = self.inner_is_finished()
        assert ret == expected
        return ret

    def inner_is_finished(self) -> bool:
        return self._compute_finished()

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        self._sync_scheduler_states()
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_state(node_id)
        assert ret == self.state.scheduler_states[node_id]
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        return self.state.scheduler_states[node_id]

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        self._sync_scheduler_states()
        ret = self.inner_get_all_states()
        expected = {
            node_id: self.state.scheduler_states[node_id]
            for node_id in self.state.nodes
            if node_id in self.state.scheduler_states
        }
        assert dict(ret) == expected
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return {
            node_id: self.state.scheduler_states[node_id]
            for node_id in self.state.nodes
            if node_id in self.state.scheduler_states
        }

    # ------------------------------------------------------------------
    # Sequential runner transition
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.state.dependencies_complete)
        require(self.state.acyclic)
        require_arg(failure_policy, self.state.failure_policies)
        require(not self.state.running_nodes)
        require(not self._has_terminal_states())
        predicted, final_states = self._predict_run(failure_policy)
        ret = self.inner_run(failure_policy)
        self.state.scheduler_states = dict(final_states)
        self.state.results = dict(ret.results)
        self.state.running_nodes = set()
        self.state.scheduler_active = True
        self._refresh_scheduler_sets()
        node_set = set(self.state.nodes)
        assert ret.total_nodes == len(node_set)
        assert set(ret.results.keys()) == node_set
        assert tuple(sorted(ret.succeeded_nodes)) == predicted.succeeded_nodes
        assert tuple(sorted(ret.failed_nodes)) == predicted.failed_nodes
        assert tuple(sorted(ret.skipped_nodes)) == predicted.skipped_nodes
        assert tuple(sorted(ret.cancelled_nodes)) == predicted.cancelled_nodes
        for node_id in node_set:
            assert ret.results[node_id].state == predicted.results[node_id].state
            assert ret.results[node_id].state in TERMINAL_STATES
        assert ret.wall_clock_seconds >= 0.0
        assert tuple(ret.critical_path) == predicted.critical_path
        assert set(ret.critical_path) <= node_set
        assert sut(WaveScheduler).is_finished()
        expected_states = {
            node_id: ret.results[node_id].state for node_id in node_set
        }
        assert dict(sut(WaveScheduler).get_all_states()) == expected_states
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        report, _ = self._predict_run(failure_policy)
        return report


proto = DAGEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngine = synthesize_fake(DAGEngineStateMachine)


def make_dag_engine_fakes(
    state: Optional[DAGEngineState] = None,
) -> tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fakes sharing one model state for all engine services."""
    fake = FakeDAGEngine(state=state or proto.make_initial_state())
    return (fake, fake, fake)


FakeDAGEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestDAGEngineFake(unittest.TestCase):
    """Fixed fake scenarios covering edge branches not reached by fuzzing."""

    def setUp(self) -> None:
        self.dag, self.scheduler, self.runner = make_dag_engine_fakes()

    def test_graph_structure_queries(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_text, None, 2, 0)
        self.dag.add_node("gamma", action_ok, None, 1, 0)
        self.dag.add_edge("alpha", "beta")
        self.dag.add_edge("alpha", "gamma")
        self.dag.add_edge("beta", "gamma")
        self.dag.validate()
        self.assertEqual(self.dag.all_nodes(), {"alpha", "beta", "gamma"})
        self.assertTrue(self.dag.has_node("beta"))
        self.assertFalse(self.dag.has_node("missing"))
        self.assertEqual(self.dag.get_node("beta").priority, 2)
        self.assertEqual(self.dag.get_node("alpha").dependencies, frozenset())
        self.assertEqual(self.dag.get_dependencies("gamma"), {"alpha", "beta"})
        self.assertEqual(self.dag.get_dependents("alpha"), {"beta", "gamma"})
        self.assertEqual(self.dag.find_roots(), {"alpha"})
        self.assertEqual(self.dag.find_leaves(), {"gamma"})
        self.assertEqual(self.dag.topological_sort(), ["alpha", "beta", "gamma"])

    def test_critical_path_weighting(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_text, None, 0, 0)
        self.dag.add_node("gamma", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "gamma")
        self.dag.add_edge("beta", "gamma")
        path, weight = self.dag.compute_critical_path(None)
        self.assertEqual(weight, 2.0)
        self.assertEqual(path, ["beta", "gamma"])
        weighted_path, weighted = self.dag.compute_critical_path({"beta": 2.0})
        self.assertEqual(weighted, 3.0)
        self.assertEqual(weighted_path, ["beta", "gamma"])

    def test_scheduler_promotion(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_text, None, 0, 0)
        self.dag.add_node("gamma", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        self.dag.add_edge("beta", "gamma")
        self.assertEqual(self.scheduler.get_all_states()["alpha"], NodeState.READY)
        self.assertEqual(self.scheduler.next_wave(), ["alpha"])
        self.scheduler.mark_running("alpha")
        self.assertEqual(self.scheduler.get_state("alpha"), NodeState.RUNNING)
        self.assertFalse(self.scheduler.is_finished())
        self.scheduler.mark_succeeded("alpha")
        self.assertEqual(self.scheduler.next_wave(), ["beta"])
        self.scheduler.mark_running("beta")
        self.scheduler.mark_succeeded("beta")
        self.assertEqual(self.scheduler.next_wave(), ["gamma"])
        self.scheduler.mark_running("gamma")
        self.scheduler.mark_succeeded("gamma")
        self.assertTrue(self.scheduler.is_finished())

    def test_late_dependent_promotion(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_text, None, 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["alpha", "beta"])
        self.scheduler.mark_succeeded("alpha")
        self.dag.add_node("gamma", action_ok, frozenset({"alpha"}), 0, 0)
        self.assertEqual(self.scheduler.next_wave(), ["beta", "gamma"])
        self.assertEqual(self.scheduler.get_state("gamma"), NodeState.READY)

    def test_scheduler_skip_downstream(self) -> None:
        self.dag.add_node("alpha", action_fail, None, 0, 0)
        self.dag.add_node("beta", action_ok, None, 0, 0)
        self.dag.add_node("gamma", action_ok, None, 0, 0)
        self.dag.add_node("delta", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        self.dag.add_edge("beta", "gamma")
        self.scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["alpha"], NodeState.FAILED)
        self.assertEqual(states["beta"], NodeState.SKIPPED)
        self.assertEqual(states["gamma"], NodeState.SKIPPED)
        self.assertEqual(states["delta"], NodeState.READY)
        self.assertFalse(self.scheduler.is_finished())

    def test_scheduler_fail_fast(self) -> None:
        self.dag.add_node("alpha", action_fail, None, 0, 0)
        self.dag.add_node("beta", action_ok, None, 0, 0)
        self.dag.add_node("delta", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        self.scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        states = self.scheduler.get_all_states()
        self.assertEqual(states["alpha"], NodeState.FAILED)
        self.assertEqual(states["beta"], NodeState.CANCELLED)
        self.assertEqual(states["delta"], NodeState.CANCELLED)
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_blocked_termination(self) -> None:
        self.dag.add_node("alpha", action_fail, None, 0, 0)
        self.dag.add_node("beta", action_ok, None, 0, 0)
        self.scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        self.dag.add_edge("alpha", "beta")
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_terminal_with_running(self) -> None:
        self.dag.add_node("alpha", action_fail, None, 0, 0)
        self.dag.add_node("beta", action_ok, None, 0, 0)
        self.scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        self.scheduler.mark_running("beta")
        self.assertFalse(self.scheduler.is_finished())

    def test_runner_skip_downstream(self) -> None:
        self.dag.add_node("alpha", action_text, None, 0, 0)
        self.dag.add_node("beta", action_fail, None, 0, 1)
        self.dag.add_node("gamma", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        self.dag.add_edge("beta", "gamma")
        self.scheduler.get_all_states()
        report = self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.succeeded_nodes, ("alpha",))
        self.assertEqual(report.failed_nodes, ("beta",))
        self.assertEqual(report.skipped_nodes, ("gamma",))
        self.assertTrue(self.scheduler.is_finished())

    def test_runner_fail_fast(self) -> None:
        self.dag.add_node("alpha", action_fail, None, 5, 0)
        self.dag.add_node("beta", action_ok, None, 0, 0)
        self.dag.add_node("delta", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("alpha",))
        self.assertEqual(report.cancelled_nodes, ("beta", "delta"))
        self.assertEqual(report.succeeded_nodes, ())

    def test_runner_continue_on_error(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_fail, None, 0, 1)
        self.dag.add_node("gamma", action_ok, None, 0, 0)
        self.dag.add_node("delta", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        self.dag.add_edge("beta", "gamma")
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.succeeded_nodes, ("alpha", "delta"))
        self.assertEqual(report.failed_nodes, ("beta",))
        self.assertEqual(report.skipped_nodes, ("gamma",))

    def test_runner_empty_graph(self) -> None:
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.critical_path, ())
        self.assertTrue(self.scheduler.is_finished())

    def test_remove_and_cycle(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_text, None, 0, 0)
        self.dag.add_node("gamma", action_ok, None, 0, 0)
        self.dag.add_edge("alpha", "beta")
        self.dag.add_edge("beta", "gamma")
        self.dag.add_edge("gamma", "alpha")
        self.scheduler.get_all_states()
        self.dag.remove_node("gamma")
        self.assertEqual(self.dag.all_nodes(), {"alpha", "beta"})
        self.scheduler.get_all_states()
        self.dag.remove_node("beta")
        self.dag.remove_node("alpha")
        self.assertEqual(self.dag.all_nodes(), set())

    def test_invalid_dependencies(self) -> None:
        self.dag.add_node("alpha", action_ok, None, 0, 0)
        self.dag.add_node("beta", action_text, None, 0, 0)
        self.dag.add_node("gamma", action_ok, frozenset({"alpha"}), 0, 0)
        self.dag.remove_node("alpha")
        self.assertTrue(self.dag.has_node("gamma"))
        self.assertFalse(self.dag.has_node("alpha"))

    def test_self_loop_failure(self) -> None:
        self.dag.add_node("alpha", action_fail, None, 0, 0)
        self.dag.add_edge("alpha", "alpha")
        self.scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("alpha"), NodeState.FAILED)


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

# Defined in dag_engine_lite_impl_pretense.py


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

# Defined in dag_engine_lite_impl_pretense.py


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

# Defined in dag_engine_lite_impl_pretense.py

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T18:32:26Z
# LAST_CHANGED: 2026-11-14T18:32:26Z
# CHANGE: Resolve pretense_coverage facets: remove the non-contractual add_node scheduler_active gate so nodes may be registered after scheduling begins, add pending-dependent promotion during next_wave synchronization (ready_nodes postcondition), and cover the new late-registration/promotion path with a fixed fake scenario while retaining 100% coverage.
# --- END AUTOFAB METADATA ---
