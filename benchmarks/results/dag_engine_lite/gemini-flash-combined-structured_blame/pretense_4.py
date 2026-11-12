# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase, get_singleton
from dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    WaveScheduler,
    DAGRunner,
    DAGError,
    CycleError,
    NodeNotFoundError,
    DuplicateNodeError,
    NodeExecutionError,
    NodeState,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    DAGRunReport,
)
from dag_engine_lite.lib import dag_engine_lite_impl
from dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineLiteState,
    DAGEngineLiteStateMachine,
)


class DAGEngineLiteImplPseudoStateMachine(DAGEngineLiteStateMachine):
    """Implementation pseudo-state machine for DAG engine coordinating concrete SUT execution."""

    def make_initial_state(self) -> DAGEngineLiteState:
        return DAGEngineLiteState(
            available_node_ids=["A", "B", "C", "D", "E", "F", "G"],
            active_node_ids=[],
        )

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: DAG = sut(DAG)
        return target.add_node(node_id, action, dependencies, priority, retries)

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

    def inner_next_wave(self) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_succeeded(node_id)

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
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

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        return target.run(failure_policy)


class TestDAGEngineLiteImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        self.real_dag: DAG = get_singleton(DAG)
        self.real_scheduler: WaveScheduler = get_singleton(WaveScheduler)
        self.real_runner: DAGRunner = get_singleton(DAGRunner)
        self.sm = DAGEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: self.real_dag,
                WaveScheduler: self.real_scheduler,
                DAGRunner: self.real_runner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, self.real_dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.real_scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.real_runner)
        self.checked = self.checked_dag

    def test_empty_dag_operations(self) -> None:
        _ = self.checked_dag.all_nodes()
        self.checked_dag.validate()
        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.compute_critical_path(None)
        _ = self.checked_scheduler.next_wave()
        _ = self.checked_scheduler.get_all_states()
        assert self.checked_scheduler.is_finished() is True
        _ = self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_dag_lifecycle_and_queries(self) -> None:
        def action_a() -> int:
            return 10

        def action_b() -> int:
            return 20

        self.checked_dag.add_node("A", action_a, None, 5, 1)
        self.checked_dag.add_node("B", action_b, ["A"], 10, 0)
        self.checked_dag.add_edge("A", "B")
        _ = self.checked_dag.has_node("A")
        _ = self.checked_dag.has_node("missing")
        _ = self.checked_dag.get_node("A")
        _ = self.checked_dag.get_dependencies("B")
        _ = self.checked_dag.get_dependents("A")
        _ = self.checked_dag.all_nodes()
        self.checked_dag.validate()
        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.compute_critical_path(None)
        _ = self.checked_dag.compute_critical_path({"A": 1.5, "B": 2.5})
        self.checked_dag.remove_node("A")
        self.checked_dag.remove_node("B")

    def test_remove_node_purges_incident_edges(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, None, 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.add_node("C", action, ["B"], 0, 0)

        # 1. Purge incident upstream and downstream: remove B which has upstream A and downstream C
        self.checked_dag.remove_node("B")
        _ = self.checked_dag.get_dependents("A")
        _ = self.checked_dag.get_dependencies("C")

        # 2. Purge incident downstream: add edge A -> C, then remove A (which has downstream C)
        self.checked_dag.add_edge("A", "C")
        self.checked_dag.remove_node("A")
        _ = self.checked_dag.get_dependencies("C")

        # 3. Purge incident upstream: add D -> C, then remove C (which has upstream D)
        self.checked_dag.add_node("D", action, None, 0, 0)
        self.checked_dag.add_edge("D", "C")
        self.checked_dag.remove_node("C")
        _ = self.checked_dag.get_dependents("D")
        self.checked_dag.remove_node("D")

    def test_scheduler_wave_flow(self) -> None:
        def action_a() -> int:
            return 1

        def action_b() -> int:
            return 2

        self.checked_dag.add_node("A", action_a, None, 5, 0)
        self.checked_dag.add_node("B", action_b, ["A"], 1, 0)
        _ = self.checked_scheduler.is_finished()
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("A")
        _ = self.checked_scheduler.get_state("A")
        _ = self.checked_scheduler.get_all_states()
        self.checked_scheduler.mark_succeeded("A")
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("B")
        self.checked_scheduler.mark_succeeded("B")
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_fail_fast(self) -> None:
        def action_a() -> int:
            return 1

        def action_b() -> int:
            return 2

        self.checked_dag.add_node("A", action_a, None, 5, 0)
        self.checked_dag.add_node("B", action_b, None, 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("A")
        self.checked_scheduler.mark_failed("A", FailurePolicy.FAIL_FAST)
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, None, 10, 0)
        self.checked_dag.add_node("B", action, ["A"], 5, 0)
        self.checked_dag.add_node("C", action, ["B"], 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("A")
        self.checked_scheduler.mark_failed("A", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_scheduler.get_state("A")
        _ = self.checked_scheduler.get_state("B")
        _ = self.checked_scheduler.get_state("C")
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_transitive_cascade(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, None, 10, 0)
        self.checked_dag.add_node("B", action, ["A"], 5, 0)
        self.checked_dag.add_node("C", action, ["B"], 2, 0)
        self.checked_dag.add_node("D", action, ["C"], 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("A")
        self.checked_scheduler.mark_failed("A", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_scheduler.get_state("A")
        _ = self.checked_scheduler.get_state("B")
        _ = self.checked_scheduler.get_state("C")
        _ = self.checked_scheduler.get_state("D")
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_continue_on_error(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, None, 10, 0)
        self.checked_dag.add_node("B", action, ["A"], 5, 0)
        self.checked_dag.add_node("C", action, ["B"], 2, 0)
        self.checked_dag.add_node("D", action, None, 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("A")
        self.checked_scheduler.mark_failed("A", FailurePolicy.CONTINUE_ON_ERROR)
        _ = self.checked_scheduler.get_state("B")
        _ = self.checked_scheduler.get_state("C")
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("D")
        self.checked_scheduler.mark_succeeded("D")
        _ = self.checked_scheduler.is_finished()

    def test_runner_run_success(self) -> None:
        def action_a() -> int:
            return 10

        def action_b() -> int:
            return 20

        self.checked_dag.add_node("A", action_a, None, 5, 0)
        self.checked_dag.add_node("B", action_b, ["A"], 1, 0)
        _ = self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_run_with_retry(self) -> None:
        def fail_action() -> int:
            raise RuntimeError("Action failure")

        self.checked_dag.add_node("A", fail_action, None, 0, 2)
        _ = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_run_skip_downstream(self) -> None:
        def fail_action() -> int:
            raise ValueError("Upstream boom")

        def downstream_action() -> int:
            return 42

        self.checked_dag.add_node("A", fail_action, None, 10, 0)
        self.checked_dag.add_node("B", downstream_action, ["A"], 5, 0)
        self.checked_dag.add_node("C", downstream_action, ["B"], 1, 0)
        _ = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_runner_run_fail_fast_cancels_remaining(self) -> None:
        def fail_action() -> int:
            raise RuntimeError("Node A failed")

        def remaining_action() -> int:
            return 42

        self.checked_dag.add_node("A", fail_action, None, 10, 0)
        self.checked_dag.add_node("B", remaining_action, None, 5, 0)
        _ = self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_run_fail_fast_dependent(self) -> None:
        def fail_action() -> int:
            raise RuntimeError("Node A failed")

        def dep_action() -> int:
            return 42

        self.checked_dag.add_node("A", fail_action, None, 10, 0)
        self.checked_dag.add_node("B", dep_action, ["A"], 5, 0)
        _ = self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_runner_run_continue_on_error(self) -> None:
        def fail_action() -> int:
            raise RuntimeError("Node A failed")

        def dep_action() -> int:
            return 100

        def indep_action() -> int:
            return 200

        self.checked_dag.add_node("A", fail_action, None, 10, 0)
        self.checked_dag.add_node("B", dep_action, ["A"], 5, 0)
        self.checked_dag.add_node("C", dep_action, ["B"], 2, 0)
        self.checked_dag.add_node("D", indep_action, None, 1, 0)
        _ = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_error_add_node_duplicate(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node("A", action, None, 0, 0)

    def test_error_add_edge_missing_upstream(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("B", action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing", "B")

    def test_error_add_edge_missing_downstream(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("A", "missing")

    def test_error_remove_node_missing(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_error_get_node_missing(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_error_get_dependencies_missing(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_error_get_dependents_missing(self) -> None:
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_error_validate_missing_dependency(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["missing"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_error_validate_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["B"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.violating(CycleError).validate()

    def test_error_topological_sort_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["B"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.violating(CycleError).topological_sort()

    def test_error_topological_sort_branching_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["C"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.add_node("C", action, ["A"], 0, 0)
        self.checked_dag.add_node("D", action, ["B"], 0, 0)
        self.checked_dag.violating(CycleError).topological_sort()

    def test_error_validate_branching_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["C"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.add_node("C", action, ["A"], 0, 0)
        self.checked_dag.add_node("D", action, ["B"], 0, 0)
        self.checked_dag.violating(CycleError).validate()

    def test_error_compute_critical_path_branching_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["C"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.add_node("C", action, ["A"], 0, 0)
        self.checked_dag.add_node("D", action, ["B"], 0, 0)
        self.checked_dag.violating(CycleError).compute_critical_path(None)

    def test_error_runner_branching_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["C"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.add_node("C", action, ["A"], 0, 0)
        self.checked_dag.add_node("D", action, ["B"], 0, 0)
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

    def test_error_topological_sort_missing_dependency(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["missing"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).topological_sort()

    def test_error_compute_critical_path_missing_dependency(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["missing"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).compute_critical_path(None)

    def test_error_compute_critical_path_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["B"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_dag.violating(CycleError).compute_critical_path(None)

    def test_error_scheduler_get_state_missing(self) -> None:
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing")

    def test_error_runner_missing_dependency(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["missing"], 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(FailurePolicy.FAIL_FAST)

    def test_error_runner_cycle(self) -> None:
        def action() -> int:
            return 1

        self.checked_dag.add_node("A", action, ["B"], 0, 0)
        self.checked_dag.add_node("B", action, ["A"], 0, 0)
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T05:22:37Z
# LAST_CHANGED: 2026-11-12T05:21:20Z
# CHANGE: Fix branching cycle scenarios to use 4 nodes within available_node_ids domain and specialize make_initial_state on pseudo-state machine
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T05:22:37Z
# PRETENSE_QA_AUDIT: 2026-11-12T05:22:03Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple
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
from pretense.compiler import compile_hypothesis_test_case
from dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    WaveScheduler,
    DAGRunner,
    DAGError,
    CycleError,
    NodeNotFoundError,
    DuplicateNodeError,
    NodeExecutionError,
    NodeState,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    DAGRunReport,
)


@dataclass
class DAGEngineLiteState:
    """Canonical model state tracking DAG structure, scheduler lifecycle, and execution status."""
    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    available_node_ids: list[str] = field(default_factory=list)
    active_node_ids: list[str] = field(default_factory=list)
    is_valid: bool = True
    is_acyclic: bool = True


class DAGEngineLiteStateMachine(StateMachine[DAGEngineLiteState]):
    """Unified Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DAGEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineLiteState:
        """Constructs default blank model state."""
        return DAGEngineLiteState(
            available_node_ids=["A", "B", "C", "D"],
            active_node_ids=[],
        )

    # --------------------------------------------------------------------------
    # DAG Transitions (1:1 with DAG interface methods)
    # --------------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(bool(self.state.available_node_ids))
        require_arg(node_id, Domain.in_set(self.state.available_node_ids), preferred=["A", "B"])
        require_arg(action, Domain.any())
        require_arg(dependencies, Domain.any())
        require_arg(priority, Domain.integers(-10, 10), preferred=[0, 1, 5])
        require_arg(retries, Domain.integers(0, 5), preferred=[0, 1])
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        if node_id in self.state.available_node_ids:
            self.state.available_node_ids.remove(node_id)
        if node_id not in self.state.active_node_ids:
            self.state.active_node_ids.append(node_id)
        dep_set = frozenset(dependencies) if dependencies is not None else frozenset()
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dep_set,
            priority=priority,
            retries=retries,
        )
        if node_id not in self.state.upstream:
            self.state.upstream[node_id] = set()
        if node_id not in self.state.downstream:
            self.state.downstream[node_id] = set()
        for dep in dep_set:
            self.state.upstream[node_id].add(dep)
            if dep not in self.state.downstream:
                self.state.downstream[dep] = set()
            self.state.downstream[dep].add(node_id)
        self.state.node_states[node_id] = NodeState.PENDING
        assert ret is None

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
        require(len(self.state.active_node_ids) >= 2)
        require_arg(upstream_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        require_arg(downstream_id, Domain.in_set(self.state.active_node_ids), preferred=["B"])
        ret = self.inner_add_edge(upstream_id, downstream_id)
        if upstream_id in self.state.nodes and downstream_id in self.state.nodes:
            self.state.upstream[downstream_id].add(upstream_id)
            self.state.downstream[upstream_id].add(downstream_id)
        assert ret is None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_remove_node(node_id)
        if node_id in self.state.active_node_ids:
            self.state.active_node_ids.remove(node_id)
        if node_id not in self.state.available_node_ids:
            self.state.available_node_ids.append(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.node_states.pop(node_id, None)
        ups = self.state.upstream.pop(node_id, set())
        for up in ups:
            if up in self.state.downstream:
                self.state.downstream[up].discard(node_id)
        downs = self.state.downstream.pop(node_id, set())
        for down in downs:
            if down in self.state.upstream:
                self.state.upstream[down].discard(node_id)
        assert ret is None

    def inner_remove_node(self, node_id: str) -> None:
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.type(str), preferred=["A", "missing"])
        ret = self.inner_has_node(node_id)
        expected = node_id in self.state.nodes
        assert ret == expected
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_get_dependencies(node_id)
        assert isinstance(ret, set)
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_get_dependents(node_id)
        assert isinstance(ret, set)
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
        require(self.state.is_valid)
        ret = self.inner_validate()
        assert ret is None

    def inner_validate(self) -> None:
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.is_valid)
        ret = self.inner_topological_sort()
        assert len(ret) == len(self.state.nodes)
        return ret

    def inner_topological_sort(self) -> List[str]:
        return sorted(self.state.nodes.keys())

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        assert isinstance(ret, set)
        return ret

    def inner_find_roots(self) -> Set[str]:
        roots: set[str] = set()
        for nid in self.state.nodes:
            if not self.state.upstream.get(nid):
                roots.add(nid)
        return roots

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        assert isinstance(ret, set)
        return ret

    def inner_find_leaves(self) -> Set[str]:
        leaves: set[str] = set()
        for nid in self.state.nodes:
            if not self.state.downstream.get(nid):
                leaves.add(nid)
        return leaves

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.is_valid)
        require_arg(estimated_durations, Domain.any())
        ret = self.inner_compute_critical_path(estimated_durations)
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        nids = sorted(self.state.nodes.keys())
        weight = float(len(nids))
        return (nids, weight)

    # --------------------------------------------------------------------------
    # WaveScheduler Transitions (1:1 with WaveScheduler interface methods)
    # --------------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        ret = self.inner_next_wave()
        assert isinstance(ret, list)
        return ret

    def inner_next_wave(self) -> List[str]:
        ready: list[str] = []
        for nid in sorted(self.state.nodes.keys()):
            st_val = self.state.node_states.get(nid, NodeState.PENDING)
            if st_val == NodeState.READY:
                ready.append(nid)
        return ready

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_mark_running(node_id)
        self.state.node_states[node_id] = NodeState.RUNNING
        assert ret is None

    def inner_mark_running(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_mark_succeeded(node_id)
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        assert ret is None

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)), preferred=[FailurePolicy.FAIL_FAST])
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.node_states[node_id] = NodeState.FAILED
        assert ret is None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    def inner_is_finished(self) -> bool:
        if not self.state.nodes:
            return True
        for nid in self.state.nodes:
            st_val = self.state.node_states.get(nid, NodeState.PENDING)
            if st_val not in (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED):
                return False
        return True

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(bool(self.state.active_node_ids))
        require_arg(node_id, Domain.in_set(self.state.active_node_ids), preferred=["A"])
        ret = self.inner_get_state(node_id)
        assert isinstance(ret, NodeState)
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        return self.state.node_states.get(node_id, NodeState.PENDING)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        ret = self.inner_get_all_states()
        assert isinstance(ret, dict)
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return dict(self.state.node_states)

    # --------------------------------------------------------------------------
    # DAGRunner Transitions (1:1 with DAGRunner interface methods)
    # --------------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.state.is_valid)
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)), preferred=[FailurePolicy.FAIL_FAST])
        ret = self.inner_run(failure_policy)
        assert isinstance(ret, DAGRunReport)
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        nids = tuple(sorted(self.state.nodes.keys()))
        results: dict[str, NodeResult[Any]] = {}
        for nid in nids:
            results[nid] = NodeResult(
                node_id=nid,
                state=NodeState.SUCCEEDED,
                value=None,
                error=None,
                duration_seconds=0.01,
                retries_attempted=0,
            )
        return DAGRunReport(
            total_nodes=len(nids),
            succeeded_nodes=nids,
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.05,
            critical_path=nids,
            results=results,
        )

    # --------------------------------------------------------------------------
    # Seeding Transitions
    # --------------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.available_node_ids = ["A", "B", "C", "D"]
        self.state.active_node_ids = []
        self.state.nodes.clear()
        self.state.upstream.clear()
        self.state.downstream.clear()
        self.state.node_states.clear()
        self.state.is_valid = True
        self.state.is_acyclic = True


proto = DAGEngineLiteStateMachine()


FakeDAGEngineLite = synthesize_fake(DAGEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DAGEngineLiteState] = None) -> Any:
    """Synthesizes fake instance implementing DAG, WaveScheduler, and DAGRunner."""
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_dag_engine_lite_fakes(
    state: Optional[DAGEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake_inst = FakeDAGEngineLite(state=state or proto.make_initial_state())
    return (fake_inst, fake_inst, fake_inst)


FakeDAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineLiteFuzzTest",
)


class TestDAGEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DAGEngineLiteStateMachine(
            singletons={
                DAG: self.fake,
                WaveScheduler: self.fake,
                DAGRunner: self.fake,
            }
        )

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()

        def dummy_action() -> int:
            return 42

        self.fake.add_node("A", dummy_action, None, 0, 0)
        self.fake.add_node("B", dummy_action, ["A"], 1, 0)
        self.fake.add_edge("A", "B")
        _ = self.fake.has_node("A")
        _ = self.fake.get_node("A")
        _ = self.fake.get_dependencies("B")
        _ = self.fake.get_dependents("A")
        _ = self.fake.all_nodes()
        self.fake.validate()
        _ = self.fake.topological_sort()
        _ = self.fake.find_roots()
        _ = self.fake.find_leaves()
        _ = self.fake.compute_critical_path(None)
        _ = self.fake.next_wave()
        self.fake.mark_running("A")
        self.fake.mark_succeeded("A")
        self.fake.mark_failed("B", FailurePolicy.FAIL_FAST)
        _ = self.fake.is_finished()
        _ = self.fake.get_state("A")
        _ = self.fake.get_all_states()
        _ = self.fake.run(FailurePolicy.FAIL_FAST)
        self.fake.remove_node("B")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:53:40Z
# LAST_CHANGED: 2026-11-12T04:53:40Z
# CHANGE: Initial implementation of DAG engine pretense state machine, fake, and tests
# --- END AUTOFAB METADATA ---
