# === File: dag_engine_impl_pretense.py ===
from __future__ import annotations

import time
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

from dag_engine_gemini_argon_1.parts.dag_engine.lib import dag_engine_impl
from dag_engine_gemini_argon_1.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAG,
    DAGCancelledError,
    DAGRunReport,
    DAGRunner,
    DAGTimeoutError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
    WaveScheduler,
)
from dag_engine_gemini_argon_1.parts.dag_engine.lib.dag_engine_impl import (
    DAG as DAGImpl,
    DAGRunner as DAGRunnerImpl,
    WaveScheduler as WaveSchedulerImpl,
)
from dag_engine_gemini_argon_1.parts.dag_engine.pretense.dag_engine_pretense import (
    DAGEngineStateMachine,
    default_node_action,
)


_ACTIVE_DAGS: List[DAG] = []
_ACTIVE_RUNNERS: List[DAGRunner] = []


def failing_node_action() -> int:
    """Callable that raises an exception to exercise retry and failure policy paths."""
    return 1 // 0


def slow_node_action() -> int:
    """Callable that sleeps briefly to exercise timeout handling."""
    time.sleep(0.03)
    return 1


def cancel_during_run_action() -> int:
    """Callable that signals runner cancellation during active wave execution."""
    if _ACTIVE_RUNNERS:
        _ACTIVE_RUNNERS[-1].cancel()
    if _ACTIVE_DAGS:
        _ACTIVE_DAGS[-1].add_node(
            "n_dynamic", default_node_action, None, 0, None, 0
        )
    return 1


class DAGEngineImplPseudoStateMachine(DAGEngineStateMachine):
    """Implementation pseudo-state machine binding concrete DAG, WaveScheduler, and DAGRunner."""

    # ------------------------------------------------------------------
    # DAG inner transitions
    # ------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        target: DAG = sut(DAG)
        _ACTIVE_DAGS.append(target)
        return target.add_node(
            node_id, action, dependencies, priority, timeout_seconds, retries
        )

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        return target.add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        return target.remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        return target.get_node(node_id)

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
        return target.validate()

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
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: DAG = sut(DAG)
        return target.compute_critical_path(estimated_durations)

    # ------------------------------------------------------------------
    # WaveScheduler inner transitions
    # ------------------------------------------------------------------

    def inner_next_wave(self) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_succeeded(node_id)

    def inner_mark_failed(
        self, node_id: str, failure_policy: FailurePolicy
    ) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_failed(node_id, failure_policy)

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
    # DAGRunner inner transitions
    # ------------------------------------------------------------------

    def inner_run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        _ACTIVE_RUNNERS.append(target)
        return target.run(timeout_seconds, failure_policy, max_concurrency)

    def inner_cancel(self) -> None:
        target: DAGRunner = sut(DAGRunner)
        return target.cancel()


class TestDAGEngineImplReal(LifecycleTestCase):
    """Fixed real scenario tests verifying concrete DAG, WaveScheduler, and DAGRunner."""

    def setUp(self) -> None:
        super().setUp()
        dag = get_singleton(DAG)
        sched = get_singleton(WaveScheduler)
        runner = get_singleton(DAGRunner)
        sm = DAGEngineImplPseudoStateMachine(
            singletons={
                DAG: dag,
                WaveScheduler: sched,
                DAGRunner: runner,
            }
        )
        self.checked_dag = sm.as_checked(DAG)
        self.checked_sched = sm.as_checked(WaveScheduler)
        self.checked_runner = sm.as_checked(DAGRunner)

    def test_dag_crud_and_queries(self) -> None:
        """Exercises node registration, edge creation, removal, and graph queries."""
        self.checked_dag.add_node("n1", default_node_action, None, 2, None, 0)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 1, 5.0, 1)
        self.checked_dag.add_node("n3", default_node_action, None, 0, None, 0)
        self.checked_dag.add_node("n4", default_node_action, ["n3"], 0, None, 0)
        self.checked_dag.add_edge("n2", "n3")
        self.checked_dag.add_edge("n4", "n1")
        self.checked_dag.remove_node("n4")
        _ = self.checked_dag.get_dependencies("n1")
        _ = self.checked_dag.get_dependents("n3")
        _ = self.checked_dag.has_node("n1")
        _ = self.checked_dag.has_node("missing")
        _ = self.checked_dag.get_node("n2")
        _ = self.checked_dag.get_dependencies("n2")
        _ = self.checked_dag.get_dependents("n1")
        _ = self.checked_dag.all_nodes()
        self.checked_dag.validate()
        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.compute_critical_path(None)
        _ = self.checked_dag.compute_critical_path(
            {"n1": 2.0, "n2": 3.0, "n3": 4.0}
        )

    def test_dag_empty_queries(self) -> None:
        """Exercises critical path and scheduler queries on an empty DAG."""
        _ = self.checked_dag.all_nodes()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.compute_critical_path(None)
        _ = self.checked_sched.is_finished()
        _ = self.checked_sched.next_wave()

    def test_dag_add_edge_missing_upstream(self) -> None:
        """Verifies NodeNotFoundError when upstream_id does not exist in add_edge."""
        self.checked_dag.add_node("n1", default_node_action, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing", "n1")

    def test_dag_add_edge_missing_downstream(self) -> None:
        """Verifies NodeNotFoundError when downstream_id does not exist in add_edge."""
        self.checked_dag.add_node("n1", default_node_action, None, 0, None, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("n1", "missing")

    def test_dag_remove_node_missing(self) -> None:
        """Verifies NodeNotFoundError when removing a non-existent node."""
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_dag_get_node_missing(self) -> None:
        """Verifies NodeNotFoundError when retrieving a non-existent node."""
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_dag_get_dependencies_missing(self) -> None:
        """Verifies NodeNotFoundError when querying dependencies of a missing node."""
        self.checked_dag.violating(NodeNotFoundError).get_dependencies(
            "missing"
        )

    def test_dag_get_dependents_missing(self) -> None:
        """Verifies NodeNotFoundError when querying dependents of a missing node."""
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_dag_validate_missing_dependency(self) -> None:
        """Verifies NodeNotFoundError when validate encounters an unregistered dependency."""
        self.checked_dag.add_node(
            "n1", default_node_action, ["missing"], 0, None, 0
        )
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_dag_validate_cycle(self) -> None:
        """Verifies CycleError when validate detects a cycle in the graph."""
        self.checked_dag.add_node("n1", default_node_action, None, 0, None, 0)
        self.checked_dag.add_node("n2", default_node_action, None, 0, None, 0)
        self.checked_dag.add_edge("n1", "n2")
        self.checked_dag.add_edge("n2", "n1")
        self.checked_dag.violating(CycleError).validate()

    def test_dag_topological_sort_cycle(self) -> None:
        """Verifies CycleError when topological_sort detects a cycle in the graph."""
        self.checked_dag.add_node("n1", default_node_action, None, 0, None, 0)
        self.checked_dag.add_node("n2", default_node_action, None, 0, None, 0)
        self.checked_dag.add_edge("n1", "n2")
        self.checked_dag.add_edge("n2", "n1")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_scheduler_waves_and_promotion(self) -> None:
        """Exercises WaveScheduler wave resolution, running/succeeded transitions, and promotion."""
        self.checked_dag.add_node("n1", default_node_action, None, 2, None, 0)
        self.checked_dag.add_node("n2", default_node_action, None, 1, None, 0)
        self.checked_dag.add_node(
            "n3", default_node_action, ["n1", "n2"], 0, None, 0
        )
        _ = self.checked_sched.is_finished()
        _ = self.checked_sched.next_wave()
        self.checked_sched.mark_running("n1")
        self.checked_sched.mark_running("n2")
        _ = self.checked_sched.next_wave()
        self.checked_sched.mark_succeeded("n1")
        _ = self.checked_sched.get_state("n3")
        self.checked_sched.mark_succeeded("n2")
        _ = self.checked_sched.get_state("n3")
        _ = self.checked_sched.next_wave()
        self.checked_sched.mark_running("n3")
        self.checked_sched.mark_succeeded("n3")
        _ = self.checked_sched.get_all_states()
        _ = self.checked_sched.is_finished()

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        """Exercises WaveScheduler.mark_failed with SKIP_DOWNSTREAM policy."""
        self.checked_dag.add_node("n1", default_node_action, None, 1, None, 0)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 0, None, 0)
        self.checked_dag.add_node("n3", default_node_action, ["n2"], 0, None, 0)
        self.checked_dag.add_node("n4", default_node_action, None, 0, None, 0)
        _ = self.checked_sched.next_wave()
        self.checked_sched.mark_running("n1")
        self.checked_sched.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_sched.get_state("n1")
        _ = self.checked_sched.get_state("n2")
        _ = self.checked_sched.get_state("n3")
        _ = self.checked_sched.get_state("n4")

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        """Exercises WaveScheduler.mark_failed with FAIL_FAST policy."""
        self.checked_dag.add_node("n1", default_node_action, None, 1, None, 0)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 0, None, 0)
        self.checked_dag.add_node("n3", default_node_action, None, 0, None, 0)
        _ = self.checked_sched.next_wave()
        self.checked_sched.mark_running("n1")
        self.checked_sched.mark_failed("n1", FailurePolicy.FAIL_FAST)
        _ = self.checked_sched.get_state("n2")
        _ = self.checked_sched.get_state("n3")
        _ = self.checked_sched.is_finished()

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        """Exercises WaveScheduler.mark_failed with CONTINUE_ON_ERROR policy."""
        self.checked_dag.add_node("n1", default_node_action, None, 2, None, 0)
        self.checked_dag.add_node("n2", default_node_action, None, 1, None, 0)
        _ = self.checked_sched.next_wave()
        self.checked_sched.mark_running("n1")
        self.checked_sched.mark_failed("n1", FailurePolicy.CONTINUE_ON_ERROR)
        _ = self.checked_sched.get_state("n2")
        _ = self.checked_sched.next_wave()

    def test_runner_run_success_and_cancel(self) -> None:
        """Exercises DAGRunner.run to completion and subsequent cancel()."""
        self.checked_dag.add_node("n1", default_node_action, None, 2, None, 0)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 1, 5.0, 0)
        self.checked_dag.add_node("n3", default_node_action, ["n2"], 0, None, 0)
        _ = self.checked_runner.run(5.0, FailurePolicy.FAIL_FAST, 2)
        self.checked_runner.cancel()

    def test_runner_retries_and_skip_downstream(self) -> None:
        """Exercises DAGRunner.run retry attempts and SKIP_DOWNSTREAM policy on failure."""
        self.checked_dag.add_node("n1", failing_node_action, None, 2, None, 1)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 1, None, 0)
        self.checked_dag.add_node("n3", default_node_action, None, 0, None, 0)
        _ = self.checked_runner.run(5.0, FailurePolicy.SKIP_DOWNSTREAM, 1)

    def test_runner_fail_fast(self) -> None:
        """Exercises DAGRunner.run with FAIL_FAST policy upon node failure."""
        self.checked_dag.add_node("n1", failing_node_action, None, 2, None, 0)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 1, None, 0)
        _ = self.checked_runner.run(5.0, FailurePolicy.FAIL_FAST, 1)

    def test_runner_continue_on_error(self) -> None:
        """Exercises DAGRunner.run with CONTINUE_ON_ERROR policy upon node failure."""
        self.checked_dag.add_node("n1", failing_node_action, None, 2, None, 0)
        self.checked_dag.add_node("n2", default_node_action, None, 1, None, 0)
        _ = self.checked_runner.run(5.0, FailurePolicy.CONTINUE_ON_ERROR, 1)

    def test_runner_timeout_error(self) -> None:
        """Verifies DAGTimeoutError when execution exceeds timeout_seconds."""
        self.checked_dag.add_node("n1", slow_node_action, None, 1, 0.001, 0)
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 0, None, 0)
        self.checked_runner.violating(DAGTimeoutError).run(
            0.001, FailurePolicy.FAIL_FAST, 1
        )

    def test_runner_cancelled_error(self) -> None:
        """Verifies DAGCancelledError when cancel() is signaled during execution."""
        self.checked_dag.add_node(
            "n1", cancel_during_run_action, None, 1, None, 0
        )
        self.checked_dag.add_node("n2", default_node_action, ["n1"], 0, None, 0)
        self.checked_runner.violating(DAGCancelledError).run(
            5.0, FailurePolicy.FAIL_FAST, 1
        )


proto = DAGEngineImplPseudoStateMachine()


def make_sut() -> DAG:
    """Initializes lifecycle scope with concrete DAG, WaveScheduler, and DAGRunner singletons."""
    _ = dag_engine_impl
    registry = LifecycleRegistry()
    registry.register_singleton(DAGImpl)
    registry.register_singleton(WaveSchedulerImpl)
    registry.register_singleton(DAGRunnerImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(DAG)


DAGEngineImplFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="DAGEngineImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:46:29Z
# LAST_CHANGED: 2026-11-13T23:45:26Z
# CHANGE: Exercise both upstream and downstream incident edge purging in remove_node during test_dag_crud_and_queries
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T23:46:29Z
# PRETENSE_QA_AUDIT: 2026-11-13T23:46:01Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, FrozenSet, List, Mapping, Optional, Set, Tuple
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    test_only,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from dag_engine_gemini_argon_1.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAG,
    DAGCancelledError,
    DAGError,
    DAGRunReport,
    DAGRunner,
    DAGTimeoutError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)


def default_node_action() -> int:
    """Default deterministic callable for DAG nodes during fuzzing."""
    return 1


TERMINAL_STATES: FrozenSet[NodeState] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


def compute_topological_order(
    nodes: dict[str, NodeDefinition[Any]],
    upstream: dict[str, set[str]],
    downstream: dict[str, set[str]],
) -> Optional[List[str]]:
    """Computes deterministic topological sort or returns None if a cycle exists."""
    in_degree: dict[str, int] = {
        nid: len(upstream.get(nid, set()) & set(nodes.keys())) for nid in nodes
    }
    ready: set[str] = {nid for nid, deg in in_degree.items() if deg == 0}
    order: List[str] = []
    for _ in range(len(nodes)):
        if not ready:
            return None
        best_pair = min((-nodes[cand].priority, cand) for cand in ready)
        best = best_pair[1]
        ready.remove(best)
        order.append(best)
        for dep in downstream.get(best, set()):
            if dep in in_degree:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    ready.add(dep)
    return order


def compute_longest_path(
    nodes: dict[str, NodeDefinition[Any]],
    upstream: dict[str, set[str]],
    downstream: dict[str, set[str]],
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    """Computes critical path and total weight across a valid acyclic graph."""
    order = compute_topological_order(nodes, upstream, downstream)
    if not order:
        return ([], 0.0)
    dist: dict[str, float] = {}
    prev: dict[str, Optional[str]] = {}
    for nid in order:
        w = (
            float(estimated_durations.get(nid, 1.0))
            if estimated_durations is not None
            else 1.0
        )
        best_pred: Optional[str] = None
        best_pred_dist: float = 0.0
        for u in sorted(upstream.get(nid, set())):
            if u in dist:
                if best_pred is None or dist[u] > best_pred_dist:
                    best_pred = u
                    best_pred_dist = dist[u]
        dist[nid] = best_pred_dist + w
        prev[nid] = best_pred
    end_node = order[0]
    for nid in order:
        if dist[nid] > dist[end_node]:
            end_node = nid
    path: List[str] = []
    curr: Optional[str] = end_node
    for _ in range(len(order)):
        if curr is None:
            break
        path.append(curr)
        curr = prev.get(curr)
    path.reverse()
    return (path, dist[end_node])


def compute_transitive_downstream(
    node_id: str,
    nodes: dict[str, NodeDefinition[Any]],
    downstream: dict[str, set[str]],
) -> set[str]:
    """Computes all transitive downstream dependents of node_id."""
    visited: set[str] = set(downstream.get(node_id, set()))
    for _ in range(len(nodes) + 1):
        added: set[str] = set()
        for nid in visited:
            for dep in downstream.get(nid, set()):
                if dep not in visited:
                    added.add(dep)
        if not added:
            break
        visited.update(added)
    return visited


def refresh_state_flags(state: DAGEngineState) -> None:
    """Refreshes cached graph validity and runnable flags on state."""
    state.all_dependencies_exist = all(
        dep in state.nodes
        for nid in state.nodes
        for dep in state.upstream.get(nid, set())
    )
    state.is_acyclic = (
        compute_topological_order(state.nodes, state.upstream, state.downstream)
        is not None
    )
    state.can_run_cleanly = all(
        state.node_states.get(nid)
        in (None, NodeState.READY, NodeState.PENDING, NodeState.SUCCEEDED)
        for nid in state.nodes
    )


def sync_scheduler_states(state: DAGEngineState) -> None:
    """Synchronizes scheduler node states with current DAG nodes."""
    for nid in state.nodes:
        if nid not in state.node_states:
            if not state.upstream.get(nid):
                state.node_states[nid] = NodeState.READY
            else:
                state.node_states[nid] = NodeState.PENDING
    refresh_state_flags(state)


@dataclass
class DAGEngineState:
    """Canonical model state for DAG, WaveScheduler, and DAGRunner."""

    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, NodeResult[Any]] = field(default_factory=dict)
    cancelled: bool = False
    all_dependencies_exist: bool = True
    is_acyclic: bool = True
    can_run_cleanly: bool = True
    can_add_more_nodes: bool = True


class DAGEngineStateMachine(StateMachine[DAGEngineState]):
    """Unified Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DAGEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state or self.make_initial_state(), singletons=singletons
        )

    def make_initial_state(self) -> DAGEngineState:
        """Constructs blank initial model state."""
        return DAGEngineState()

    @transition.seeding
    def seed_node(self) -> None:
        """Initializes model validity flags without desynchronizing empty DAG state."""
        refresh_state_flags(self.state)

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
        require(not self.state.node_states, error=DAGError)
        require(self.state.can_add_more_nodes, error=DAGError)
        require_arg(
            node_id,
            Domain.not_in(self.state.nodes),
            error=DAGError,
            preferred=["n1", "n2", "n3"],
            fuzz_domain=Domain.sampled_from(["n1", "n2", "n3", "n4", "n5"]),
        )
        require_arg(
            action,
            Domain.type(object),
            preferred=[default_node_action],
            fuzz_domain=Domain.sampled_from([default_node_action]),
        )
        require_arg(
            dependencies,
            Domain.optional(
                Domain.collection(Domain.text(min_size=1, max_size=8))
            ),
            preferred=[None],
            fuzz_domain=Domain.sampled_from([None]),
        )
        require_arg(
            priority,
            Domain.integers(min_value=-10, max_value=10),
            preferred=[0, 1, 2],
        )
        require_arg(
            timeout_seconds,
            Domain.optional(Domain.type(float)),
            preferred=[None, 5.0],
            fuzz_domain=Domain.sampled_from([None, 5.0]),
        )
        require_arg(
            retries,
            Domain.integers(min_value=0, max_value=3),
            preferred=[0, 1],
        )
        ret = self.inner_add_node(
            node_id, action, dependencies, priority, timeout_seconds, retries
        )
        deps_frozen: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        defn = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps_frozen,
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        self.state.nodes[node_id] = defn
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dep in deps_frozen:
            self.state.upstream[node_id].add(dep)
            self.state.downstream.setdefault(dep, set()).add(node_id)
        self.state.can_add_more_nodes = len(self.state.nodes) < 5
        refresh_state_flags(self.state)
        assert ret is None
        return ret

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        return None

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(not self.state.node_states, error=DAGError)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            upstream_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        require_arg(
            downstream_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        refresh_state_flags(self.state)
        assert ret is None
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(not self.state.node_states, error=DAGError)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_remove_node(node_id)
        for uset in self.state.upstream.values():
            uset.discard(node_id)
        for dset in self.state.downstream.values():
            dset.discard(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.can_add_more_nodes = len(self.state.nodes) < 5
        refresh_state_flags(self.state)
        assert ret is None
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(
            node_id,
            Domain.text(min_size=1, max_size=8),
            preferred=["n1", "n2", "missing"],
        )
        ret = self.inner_has_node(node_id)
        expected = node_id in self.state.nodes
        assert ret == expected
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_node(node_id)
        expected = self.state.nodes[node_id]
        assert ret.node_id == expected.node_id
        assert ret.priority == expected.priority
        assert ret.retries == expected.retries
        assert ret.timeout_seconds == expected.timeout_seconds
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_dependencies(node_id)
        expected = set(self.state.upstream.get(node_id, set()))
        assert ret == expected
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        ret = self.inner_get_dependents(node_id)
        expected = set(self.state.downstream.get(node_id, set()))
        assert ret == expected
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set(self.state.downstream.get(node_id, set()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes.keys())
        return ret

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes.keys())

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.all_dependencies_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        ret = self.inner_validate()
        assert ret is None
        return ret

    def inner_validate(self) -> None:
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.all_dependencies_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        ret = self.inner_topological_sort()
        expected = compute_topological_order(
            self.state.nodes, self.state.upstream, self.state.downstream
        )
        assert ret == expected
        return ret

    def inner_topological_sort(self) -> List[str]:
        order = compute_topological_order(
            self.state.nodes, self.state.upstream, self.state.downstream
        )
        return order if order is not None else []

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        expected = {
            nid
            for nid in self.state.nodes
            if not self.state.upstream.get(nid, set())
        }
        assert ret == expected
        return ret

    def inner_find_roots(self) -> Set[str]:
        return {
            nid
            for nid in self.state.nodes
            if not self.state.upstream.get(nid, set())
        }

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        expected = {
            nid
            for nid in self.state.nodes
            if not self.state.downstream.get(nid, set())
        }
        assert ret == expected
        return ret

    def inner_find_leaves(self) -> Set[str]:
        return {
            nid
            for nid in self.state.nodes
            if not self.state.downstream.get(nid, set())
        }

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.all_dependencies_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        require_arg(
            estimated_durations,
            Domain.optional(
                Domain.mapping(
                    Domain.text(min_size=1, max_size=8),
                    Domain.type(float),
                )
            ),
            preferred=[None, {"n1": 2.0, "n2": 3.0}],
            fuzz_domain=Domain.sampled_from([None, {"n1": 2.0, "n2": 3.0}]),
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        _, expected_weight = compute_longest_path(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )
        path_nodes = ret[0]
        path_weight = sum(
            float(estimated_durations.get(nid, 1.0))
            if estimated_durations is not None
            else 1.0
            for nid in path_nodes
        )
        valid_edges = all(
            path_nodes[i] in self.state.upstream.get(path_nodes[i + 1], set())
            for i in range(len(path_nodes) - 1)
        )
        assert valid_edges
        assert abs(path_weight - expected_weight) < 1e-6
        assert abs(ret[1] - expected_weight) < 1e-6
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        return compute_longest_path(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )

    # ------------------------------------------------------------------
    # WaveScheduler transitions
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        require(self.state.all_dependencies_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        sync_scheduler_states(self.state)
        ret = self.inner_next_wave()
        ready_candidates: List[str] = []
        for nid in self.state.nodes:
            if self.state.node_states.get(nid) == NodeState.READY:
                deps = self.state.upstream.get(nid, set())
                if all(
                    self.state.node_states.get(u) == NodeState.SUCCEEDED
                    for u in deps
                ):
                    ready_candidates.append(nid)
        expected = [
            nid
            for _, nid in sorted(
                (-self.state.nodes[nid].priority, nid)
                for nid in ready_candidates
            )
        ]
        assert ret == expected
        return ret

    def inner_next_wave(self) -> List[str]:
        ready_candidates: List[str] = []
        for nid in self.state.nodes:
            if self.state.node_states.get(nid) == NodeState.READY:
                deps = self.state.upstream.get(nid, set())
                if all(
                    self.state.node_states.get(u) == NodeState.SUCCEEDED
                    for u in deps
                ):
                    ready_candidates.append(nid)
        return [
            nid
            for _, nid in sorted(
                (-self.state.nodes[nid].priority, nid)
                for nid in ready_candidates
            )
        ]

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.node_states), error=NodeNotFoundError)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        sync_scheduler_states(self.state)
        ret = self.inner_mark_running(node_id)
        self.state.node_states[node_id] = NodeState.RUNNING
        refresh_state_flags(self.state)
        assert ret is None
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.node_states), error=NodeNotFoundError)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        sync_scheduler_states(self.state)
        ret = self.inner_mark_succeeded(node_id)
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        for dep in self.state.downstream.get(node_id, set()):
            if self.state.node_states.get(dep) == NodeState.PENDING:
                if all(
                    self.state.node_states.get(u) == NodeState.SUCCEEDED
                    for u in self.state.upstream.get(dep, set())
                ):
                    self.state.node_states[dep] = NodeState.READY
        refresh_state_flags(self.state)
        assert ret is None
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(bool(self.state.node_states), error=NodeNotFoundError)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[
                FailurePolicy.FAIL_FAST,
                FailurePolicy.SKIP_DOWNSTREAM,
                FailurePolicy.CONTINUE_ON_ERROR,
            ],
        )
        sync_scheduler_states(self.state)
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.node_states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for nid in list(self.state.node_states.keys()):
                if self.state.node_states[nid] not in TERMINAL_STATES:
                    self.state.node_states[nid] = NodeState.CANCELLED
        elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            trans_deps = compute_transitive_downstream(
                node_id, self.state.nodes, self.state.downstream
            )
            for dep in trans_deps:
                if (
                    dep in self.state.node_states
                    and self.state.node_states[dep] not in TERMINAL_STATES
                ):
                    self.state.node_states[dep] = NodeState.SKIPPED
        refresh_state_flags(self.state)
        assert ret is None
        return ret

    def inner_mark_failed(
        self, node_id: str, failure_policy: FailurePolicy
    ) -> None:
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        require(self.state.all_dependencies_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        sync_scheduler_states(self.state)
        ret = self.inner_is_finished()
        expected = all(
            self.state.node_states.get(nid) in TERMINAL_STATES
            for nid in self.state.nodes
        )
        assert ret == expected
        return ret

    def inner_is_finished(self) -> bool:
        return all(
            self.state.node_states.get(nid) in TERMINAL_STATES
            for nid in self.state.nodes
        )

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(bool(self.state.node_states), error=NodeNotFoundError)
        require(bool(self.state.nodes), error=NodeNotFoundError)
        require_arg(
            node_id,
            Domain.in_set(self.state.nodes),
            error=NodeNotFoundError,
        )
        sync_scheduler_states(self.state)
        ret = self.inner_get_state(node_id)
        assert ret == self.state.node_states[node_id]
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        return self.state.node_states[node_id]

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        require(bool(self.state.node_states), error=DAGError)
        sync_scheduler_states(self.state)
        ret = self.inner_get_all_states()
        for nid in self.state.nodes:
            assert ret.get(nid) == self.state.node_states[nid]
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return dict(self.state.node_states)

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
        require(self.state.all_dependencies_exist, error=NodeNotFoundError)
        require(self.state.is_acyclic, error=CycleError)
        require(not self.state.cancelled, error=DAGCancelledError)
        require(self.state.can_run_cleanly, error=DAGError)
        require_arg(
            timeout_seconds,
            Domain.optional(Domain.type(float)),
            error=DAGTimeoutError,
            preferred=[None, 5.0],
            fuzz_domain=Domain.sampled_from([None, 5.0]),
        )
        require_arg(
            failure_policy,
            Domain.sampled_from(
                [
                    FailurePolicy.FAIL_FAST,
                    FailurePolicy.CONTINUE_ON_ERROR,
                    FailurePolicy.SKIP_DOWNSTREAM,
                ]
            ),
            preferred=[
                FailurePolicy.FAIL_FAST,
                FailurePolicy.CONTINUE_ON_ERROR,
                FailurePolicy.SKIP_DOWNSTREAM,
            ],
        )
        require_arg(
            max_concurrency,
            Domain.integers(min_value=1, max_value=4),
            preferred=[1, 2],
        )
        sync_scheduler_states(self.state)
        ret = self.inner_run(timeout_seconds, failure_policy, max_concurrency)
        self.state.node_states.update(
            {nid: NodeState.SUCCEEDED for nid in ret.succeeded_nodes}
        )
        self.state.node_states.update(
            {nid: NodeState.FAILED for nid in ret.failed_nodes}
        )
        self.state.node_states.update(
            {nid: NodeState.SKIPPED for nid in ret.skipped_nodes}
        )
        self.state.node_states.update(
            {nid: NodeState.CANCELLED for nid in ret.cancelled_nodes}
        )
        self.state.results.update(ret.results)
        refresh_state_flags(self.state)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    def inner_run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        results: dict[str, NodeResult[Any]] = {}
        temp_states = dict(self.state.node_states)
        order = (
            compute_topological_order(
                self.state.nodes, self.state.upstream, self.state.downstream
            )
            or []
        )
        for nid in order:
            if temp_states.get(nid) not in TERMINAL_STATES:
                val = self.state.nodes[nid].action()
                temp_states[nid] = NodeState.SUCCEEDED
                results[nid] = NodeResult(
                    node_id=nid,
                    state=NodeState.SUCCEEDED,
                    value=val,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )
        succeeded = tuple(
            nid
            for nid in order
            if temp_states.get(nid) == NodeState.SUCCEEDED
        )
        failed = tuple(
            nid for nid in order if temp_states.get(nid) == NodeState.FAILED
        )
        skipped = tuple(
            nid for nid in order if temp_states.get(nid) == NodeState.SKIPPED
        )
        cancelled = tuple(
            nid
            for nid in order
            if temp_states.get(nid) == NodeState.CANCELLED
        )
        cpath, _ = compute_longest_path(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            None,
        )
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=0.0,
            critical_path=tuple(cpath),
            results=results,
        )

    @transition(DAGRunner.cancel)
    def cancel(self) -> None:
        require(bool(self.state.node_states), error=DAGError)
        sync_scheduler_states(self.state)
        ret = self.inner_cancel()
        self.state.cancelled = True
        self.state.node_states.update(
            {
                nid: NodeState.CANCELLED
                for nid, st in self.state.node_states.items()
                if st not in TERMINAL_STATES
            }
        )
        refresh_state_flags(self.state)
        assert ret is None
        assert sut(DAGRunner).is_cancelled() is True
        return ret

    def inner_cancel(self) -> None:
        return None

    @test_only
    def is_cancelled(self) -> bool:
        return self.state.cancelled


proto = DAGEngineStateMachine()

FakeDAGEngine = synthesize_fake(DAGEngineStateMachine)


def make_dag_engine_fakes(
    state: Optional[DAGEngineState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances sharing DAGEngineState."""
    fake_instance = FakeDAGEngine(state=state or proto.make_initial_state())
    return (fake_instance, fake_instance, fake_instance)


FakeDAGEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineFuzzTest",
)


class TestDAGEngineFake(unittest.TestCase):
    """Fixed fake tests covering seeding transitions and edge branches."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        self.fake_dag, self.fake_sched, self.fake_runner = (
            make_dag_engine_fakes(state=state)
        )
        self.sm = DAGEngineStateMachine(
            state=state,
            singletons={
                DAG: self.fake_dag,
                WaveScheduler: self.fake_sched,
                DAGRunner: self.fake_runner,
            },
        )

    def test_seed_and_lifecycle(self) -> None:
        """Exercises seeding transition and all interface operations on fake."""
        self.sm.seed_node()
        self.fake_dag.add_node("n1", default_node_action, None, 1, None, 0)
        self.fake_dag.add_node("n2", default_node_action, ["n1"], 0, 1.0, 1)
        self.fake_dag.add_node("n3", default_node_action, None, 2, None, 0)
        self.fake_dag.add_node("n4", default_node_action, None, 0, None, 0)
        self.fake_dag.add_edge("n2", "n3")
        self.fake_dag.remove_node("n4")
        assert self.fake_dag.has_node("n1") is True
        _ = self.fake_dag.get_node("n1")
        _ = self.fake_dag.get_dependencies("n2")
        _ = self.fake_dag.get_dependents("n1")
        _ = self.fake_dag.all_nodes()
        self.fake_dag.validate()
        _ = self.fake_dag.topological_sort()
        _ = self.fake_dag.find_roots()
        _ = self.fake_dag.find_leaves()
        _ = self.fake_dag.compute_critical_path(
            {"n1": 2.0, "n2": 3.0, "n3": 1.0}
        )
        _ = self.fake_runner.run(5.0, FailurePolicy.CONTINUE_ON_ERROR, 1)

    def test_scheduler_failure_policies(self) -> None:
        """Exercises transitive downstream skipping and fail-fast on fake."""
        self.fake_dag.add_node("n0", default_node_action, None, 2, None, 0)
        self.fake_dag.add_node("n1", default_node_action, ["n0"], 1, None, 0)
        self.fake_dag.add_node("n2", default_node_action, ["n1"], 0, None, 0)
        self.fake_dag.add_node("n3", default_node_action, ["n2"], 0, None, 0)
        self.fake_dag.add_node("n4", default_node_action, None, 0, None, 0)
        _ = self.fake_sched.next_wave()
        self.fake_sched.mark_running("n0")
        self.fake_sched.mark_succeeded("n0")
        assert self.fake_sched.get_state("n1") == NodeState.READY
        self.fake_sched.mark_running("n1")
        self.fake_sched.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.fake_sched.get_state("n3") == NodeState.SKIPPED
        self.fake_sched.mark_failed("n1", FailurePolicy.FAIL_FAST)
        assert self.fake_sched.get_state("n4") == NodeState.CANCELLED
        _ = self.fake_sched.get_all_states()
        assert self.fake_sched.is_finished() is True
        self.fake_runner.cancel()
        assert self.fake_runner.is_cancelled() is True

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T23:40:38Z
# LAST_CHANGED: 2026-11-13T23:40:38Z
# CHANGE: Transition all non-terminal nodes (including RUNNING) to CANCELLED in cancel() transition
# --- END AUTOFAB METADATA ---
