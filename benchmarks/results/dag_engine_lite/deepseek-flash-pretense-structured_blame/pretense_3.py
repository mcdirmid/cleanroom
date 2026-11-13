# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from pretense import Env, StateMachine, sut, sut_state
from support.lib.lifecycle import LifecycleTestCase, get_singleton

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
from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineState,
    DAGEngineStateMachine,
    action_alternative,
    action_fail,
    action_succeed,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DAGEngineImplPseudoStateMachine(DAGEngineStateMachine):
    """Implementation pseudo-state machine binding the concrete DAG engine services."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Adds a node to the concrete DAG service."""
        graph: DAG = sut(DAG)
        graph.add_node(node_id, action, dependencies, priority, retries)
        assert graph.has_node(node_id)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a dependency edge to the concrete DAG service."""
        graph: DAG = sut(DAG)
        graph.add_edge(upstream_id, downstream_id)
        assert downstream_id in graph.get_dependents(upstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        """Removes a node from the concrete DAG service."""
        graph: DAG = sut(DAG)
        graph.remove_node(node_id)
        assert not graph.has_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        """Queries node membership on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Queries the node definition on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        """Queries direct upstream dependencies on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        """Queries direct downstream dependents on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        """Queries every registered node identifier on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.all_nodes()

    def inner_validate(self) -> None:
        """Validates graph consistency on the concrete DAG service."""
        graph: DAG = sut(DAG)
        graph.validate()

    def inner_topological_sort(self) -> List[str]:
        """Computes the topological order on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        """Computes root nodes on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        """Computes leaf nodes on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the critical path on the concrete DAG service."""
        graph: DAG = sut(DAG)
        return graph.compute_critical_path(estimated_durations)

    def inner_next_wave(self) -> List[str]:
        """Resolves the next ready wave on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        return scheduler.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        """Marks a node running on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        scheduler.mark_running(node_id)
        assert scheduler.get_state(node_id) is NodeState.RUNNING

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Marks a node succeeded on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        scheduler.mark_succeeded(node_id)
        assert scheduler.get_state(node_id) is NodeState.SUCCEEDED

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Marks a node failed on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        scheduler.mark_failed(node_id, failure_policy)
        assert scheduler.get_state(node_id) is NodeState.FAILED

    def inner_is_finished(self) -> bool:
        """Queries completion on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        return scheduler.is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        """Queries one node state on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        return scheduler.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        """Queries every node state on the concrete wave scheduler service."""
        scheduler: WaveScheduler = sut(WaveScheduler)
        return scheduler.get_all_states()

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Executes the graph on the concrete sequential runner service."""
        runner: DAGRunner = sut(DAGRunner)
        return runner.run(failure_policy)


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDAGEngineImplReal(LifecycleTestCase):
    """Verifies that the concrete DAG engine implementation satisfies every contract."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DAGEngineImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.scheduler, DAGRunner: self.runner}
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.runner)

    def test_graph_queries(self) -> None:
        """Exercises node registration, navigation, validation, sorting, and path analysis."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_alternative, ("alpha",), 1, 0)
        self.checked_dag.add_node("gamma", action_succeed, ("beta",), 0, 0)
        _ = self.checked_dag.has_node("alpha")
        _ = self.checked_dag.has_node("missing")
        _ = self.checked_dag.get_node("beta")
        _ = self.checked_dag.get_node("alpha")
        _ = self.checked_dag.get_dependencies("beta")
        _ = self.checked_dag.get_dependents("alpha")
        _ = self.checked_dag.get_dependents("gamma")
        _ = self.checked_dag.all_nodes()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        self.checked_dag.validate()
        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.compute_critical_path(None)
        _ = self.checked_dag.compute_critical_path({"alpha": 2.0, "beta": 0.5})

    def test_edge_and_removal(self) -> None:
        """Exercises explicit edge insertion, dependency navigation, and node removal."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, (), 0, 0)
        self.checked_dag.add_node("gamma", action_succeed, None, 2, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "gamma")
        _ = self.checked_dag.get_dependencies("gamma")
        _ = self.checked_dag.get_dependents("alpha")
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.topological_sort()
        self.checked_dag.remove_node("gamma")
        _ = self.checked_dag.all_nodes()
        _ = self.checked_dag.find_leaves()
        self.checked_dag.remove_node("beta")
        _ = self.checked_dag.all_nodes()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.get_dependents("alpha")
        self.checked_dag.add_node("gamma", action_succeed, None, 0, 0)
        _ = self.checked_dag.all_nodes()

    def test_remove_node_with_dependents(self) -> None:
        """Removes a node that still has downstream dependents, purging incident edges."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.checked_dag.add_node("gamma", action_succeed, ("beta",), 0, 0)
        _ = self.checked_dag.get_dependents("beta")
        self.checked_dag.remove_node("beta")
        _ = self.checked_dag.all_nodes()
        _ = self.checked_dag.get_dependencies("gamma")
        _ = self.checked_dag.get_dependents("alpha")
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.topological_sort()

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Removes a node already tracked by the wave scheduler."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("beta")
        _ = self.checked_scheduler.get_all_states()
        self.checked_dag.remove_node("beta")
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.next_wave()
        _ = self.checked_scheduler.is_finished()

    def test_empty_graph_queries(self) -> None:
        """Exercises every query transition on an empty DAG."""
        _ = self.checked_dag.all_nodes()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.compute_critical_path(None)
        self.checked_dag.validate()
        _ = self.checked_scheduler.next_wave()
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()
        _ = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_add_edge_missing_node_violation(self) -> None:
        """Verifies the existing node precondition of add_edge."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("alpha", "missing")

    def test_remove_node_missing_node_violation(self) -> None:
        """Verifies the existing node precondition of remove_node."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_get_dependencies_missing_node_violation(self) -> None:
        """Verifies the existing node precondition of get_dependencies."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_missing_node_violation(self) -> None:
        """Verifies the existing node precondition of get_dependents."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_duplicate_node_violation(self) -> None:
        """Verifies the duplicate node precondition of add_node."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node("alpha", action_succeed, None, 0, 0)

    def test_missing_node_violation(self) -> None:
        """Verifies the existing node precondition of get_node."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_missing_dependency_violation(self) -> None:
        """Verifies the dependency completeness precondition of validate."""
        self.checked_dag.add_node("alpha", action_succeed, ("ghost",), 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_cycle_validation_violation(self) -> None:
        """Verifies the acyclicity precondition of validate."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).validate()

    def test_cycle_sorting_violation(self) -> None:
        """Verifies the acyclicity precondition of topological_sort."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_cycle_with_dead_end_branch_violation(self) -> None:
        """Verifies cycle reconstruction when a dependent tail branch hangs off the cycle."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 0, 0)
        self.checked_dag.add_node("gamma", action_succeed, None, 0, 0)
        self.checked_dag.add_node("aaa", action_succeed, None, 0, 0)
        self.checked_dag.add_node("aab", action_succeed, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "gamma")
        self.checked_dag.add_edge("gamma", "alpha")
        self.checked_dag.add_edge("gamma", "aaa")
        self.checked_dag.add_edge("aaa", "aab")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_scheduler_late_registered_dependent(self) -> None:
        """Registers a dependent after its prerequisite has already succeeded."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_blocked_after_late_registration(self) -> None:
        """Keeps a late registered dependent pending when its prerequisite failed."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        _ = self.checked_scheduler.next_wave()
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_promote_settled_dependent(self) -> None:
        """Promotes dependents on success while a dependent is already terminal."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 1, 0)
        self.checked_dag.add_node("gamma", action_succeed, ("alpha", "beta"), 0, 0)
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_failed("beta", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_scheduler.get_all_states()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_reconvergent_skip(self) -> None:
        """Skips reconvergent dependents while an already terminal dependent stays put."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 1, 0)
        self.checked_dag.add_node("delta", action_succeed, ("alpha", "beta"), 0, 0)
        self.checked_dag.add_node("epsilon", action_succeed, ("alpha", "delta"), 0, 0)
        self.checked_scheduler.mark_running("delta")
        self.checked_scheduler.mark_succeeded("delta")
        _ = self.checked_scheduler.get_all_states()
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_success_flow(self) -> None:
        """Exercises wave resolution, running, success promotion, and completion detection."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 1, 0)
        self.checked_dag.add_node("gamma", action_succeed, ("alpha",), 0, 0)
        _ = self.checked_scheduler.next_wave()
        _ = self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("gamma")
        self.checked_scheduler.mark_succeeded("gamma")
        _ = self.checked_scheduler.get_state("gamma")
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()
        _ = self.checked_scheduler.next_wave()

    def test_scheduler_fail_fast(self) -> None:
        """Exercises the fail fast policy cancelling all remaining nodes."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 0, 0)
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream(self) -> None:
        """Exercises the skip downstream policy skipping transitive dependents."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.checked_dag.add_node("gamma", action_succeed, ("beta",), 0, 0)
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_continue_on_error(self) -> None:
        """Exercises the continue on error policy keeping independent nodes eligible."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.checked_dag.add_node("gamma", action_succeed, None, 1, 0)
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("gamma")
        self.checked_scheduler.mark_succeeded("gamma")
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_missing_state_violation(self) -> None:
        """Verifies the registered node precondition of get_state."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing")

    def test_runner_happy_path(self) -> None:
        """Executes a fully successful dependency chain through the runner."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_alternative, ("alpha",), 1, 0)
        self.checked_dag.add_node("gamma", action_succeed, ("beta",), 0, 0)
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        _ = report.results
        _ = report.critical_path
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_runner_retries(self) -> None:
        """Executes a failing node with a configured retry through the runner."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 1)
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        _ = report.failed_nodes
        _ = report.results
        _ = self.checked_scheduler.is_finished()

    def test_runner_fail_fast(self) -> None:
        """Executes a failing graph under the fail fast policy."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, None, 1, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        _ = report.failed_nodes
        _ = report.cancelled_nodes
        _ = report.succeeded_nodes
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_runner_skip_downstream(self) -> None:
        """Executes a failing graph under the skip downstream policy."""
        self.checked_dag.add_node("alpha", action_fail, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        _ = report.skipped_nodes
        _ = report.failed_nodes
        _ = report.results
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_runner_repeat_run(self) -> None:
        """Executes the same graph twice so the completed scheduler loops immediately."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 1)
        _ = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        _ = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_runner_starved_running_node(self) -> None:
        """Runs a graph while a node is stranded running so the ready wave is empty."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("alpha")
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        _ = report.results
        _ = report.failed_nodes
        _ = report.skipped_nodes
        _ = report.succeeded_nodes
        _ = self.checked_scheduler.get_all_states()
        _ = self.checked_scheduler.is_finished()

    def test_runner_missing_dependency_violation(self) -> None:
        """Verifies the dependency completeness precondition of run."""
        self.checked_dag.add_node("alpha", action_succeed, ("ghost",), 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_runner_cycle_violation(self) -> None:
        """Verifies the acyclicity precondition of run."""
        self.checked_dag.add_node("alpha", action_succeed, None, 0, 0)
        self.checked_dag.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:39:42Z
# LAST_CHANGED: 2026-11-13T00:34:24Z
# CHANGE: Resolves all [from:pretense_coverage] facets with targeted TestDAGEngineImplReal scenarios: remove_node with live downstream dependents (incident edge purge) plus scheduler-state purge for a tracked removed node; cycle reconstruction with a dead-end dependent tail branch; late-registered dependent promotion and blocked-late-registration starvation; mark_succeeded while a dependent is already terminal (skipped); reconvergent SKIP_DOWNSTREAM traversal with an already-terminal shared dependent; and runner termination/materialization for a stranded RUNNING node with an empty ready wave.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:39:42Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:39:18Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

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
# 0. Sample Callables and Node State Sets (Shared by Fake and Real Scenarios)
# ==============================================================================

TERMINAL_STATES: Tuple[NodeState, ...] = (
    NodeState.SUCCEEDED,
    NodeState.FAILED,
    NodeState.SKIPPED,
    NodeState.CANCELLED,
)

FAILURE_POLICIES: Tuple[FailurePolicy, ...] = (
    FailurePolicy.FAIL_FAST,
    FailurePolicy.CONTINUE_ON_ERROR,
    FailurePolicy.SKIP_DOWNSTREAM,
)


def action_succeed() -> Any:
    """Node action that completes successfully with a deterministic value."""
    return "completed"


def action_alternative() -> Any:
    """Second successful node action used to differentiate node payloads."""
    return "alternate"


def action_fail() -> Any:
    """Node action that always raises so failure policies can be exercised."""
    raise RuntimeError("synthetic node action failure")


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DAGEngineState:
    """Canonical model state for the DAG, wave scheduler, and sequential runner services."""
    nodes: List[str] = field(default_factory=list)
    actions: Dict[str, Callable[[], Any]] = field(default_factory=dict)
    priorities: Dict[str, int] = field(default_factory=dict)
    retries: Dict[str, int] = field(default_factory=dict)
    declared: Dict[str, Set[str]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    critical_path: List[str] = field(default_factory=list)
    wall_clock: float = 0.0
    cyclic: bool = False
    dangling: bool = False
    seed_count: int = 0


class DAGEngineStateMachine(StateMachine[DAGEngineState]):
    """Unified Pretense State Machine for the DAG engine services."""

    def __init__(
        self,
        state: Optional[DAGEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineState:
        """Constructs the blank initial model state of an empty engine."""
        return DAGEngineState()

    # ------------------------------------------------------------------
    # Model query helpers (not transitions: they inspect model state only).
    # ------------------------------------------------------------------

    def reachable_from(self, start: str) -> Set[str]:
        """Collects every node transitively reachable from the given node identifier."""
        seen: Set[str] = set()
        frontier: List[str] = [start]
        for node_id in frontier:
            for next_id in self.state.downstream.get(node_id, set()):
                if next_id not in seen:
                    seen.add(next_id)
                    frontier.append(next_id)
        return seen

    def transitive_dependents(self, node_id: str) -> List[str]:
        """Returns the registered transitive dependents of the given node."""
        reachable = self.reachable_from(node_id)
        return [candidate for candidate in self.state.nodes if candidate in reachable]

    def graph_cyclic(self) -> bool:
        """Determines whether the modeled dependency graph contains a directed cycle."""
        return any(node_id in self.reachable_from(node_id) for node_id in self.state.nodes)

    def graph_dangling(self) -> bool:
        """Determines whether any registered node declares an unregistered dependency."""
        return any(
            dependency not in self.state.nodes
            for node_id in self.state.nodes
            for dependency in self.state.upstream.get(node_id, set())
        )

    def dependencies_satisfied(self, dependencies: Collection[str]) -> bool:
        """Determines whether every given dependency has already succeeded in the model."""
        return all(
            self.state.states.get(dependency) is NodeState.SUCCEEDED
            for dependency in dependencies
        )

    def sorted_order(self) -> List[str]:
        """Computes the deterministic model topological order of the registered nodes."""
        remaining: Set[str] = set(self.state.nodes)
        order: List[str] = []
        for _ in self.state.nodes:
            ready = [
                node_id
                for node_id in remaining
                if not self.state.upstream.get(node_id, set()) & remaining
            ]
            if not ready:
                return order
            ranked = sorted((-self.state.priorities.get(node_id, 0), node_id) for node_id in ready)
            chosen = ranked[0][1]
            order.append(chosen)
            remaining.discard(chosen)
        return order

    def critical_path_best(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted model dependency path through the graph."""
        order = self.sorted_order()
        if not order:
            return [], 0.0
        earliest: Dict[str, float] = {}
        parent: Dict[str, Optional[str]] = {}
        for node_id in order:
            duration = 1.0 if estimated_durations is None else estimated_durations.get(node_id, 1.0)
            upstream_ids = self.state.upstream.get(node_id, set())
            if not upstream_ids:
                earliest[node_id] = duration
                parent[node_id] = None
            else:
                best = max((earliest.get(pred, 0.0), pred) for pred in upstream_ids)
                earliest[node_id] = best[0] + duration
                parent[node_id] = best[1]
        terminal = max((earliest[node_id], node_id) for node_id in order)
        path: List[str] = []
        cursor: Optional[str] = terminal[1]
        for _ in order:
            if cursor is None:
                break
            path.append(cursor)
            cursor = parent.get(cursor)
        path.reverse()
        return path, terminal[0]

    def expected_wave(self) -> List[str]:
        """Computes the model's next ready wave in priority descending, identifier ascending order."""
        ready = [
            node_id
            for node_id in self.state.nodes
            if self.state.states.get(node_id) is NodeState.READY
            and all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(node_id, set())
            )
        ]
        ranked = sorted((-self.state.priorities.get(node_id, 0), node_id) for node_id in ready)
        return [chosen for _, chosen in ranked]

    def engine_finished(self) -> bool:
        """Determines whether the modeled engine can no longer make progress."""
        if not self.state.nodes:
            return True
        if all(self.state.states.get(node_id) in TERMINAL_STATES for node_id in self.state.nodes):
            return True
        if any(self.state.states.get(node_id) is NodeState.READY for node_id in self.state.nodes):
            return False
        if any(self.state.states.get(node_id) is NodeState.RUNNING for node_id in self.state.nodes):
            return False
        return True

    # ------------------------------------------------------------------
    # Seeding transition.
    # ------------------------------------------------------------------

    @transition.seeding
    def seed_node(self) -> None:
        """Seeds a single ready root node so transitions can be reached from blank state."""
        node_id = f"seed_{self.state.seed_count}"
        self.state.seed_count += 1
        self.state.nodes.append(node_id)
        self.state.actions[node_id] = action_succeed
        self.state.priorities[node_id] = 0
        self.state.retries[node_id] = 0
        self.state.declared[node_id] = set()
        self.state.upstream[node_id] = set()
        self.state.downstream[node_id] = set()
        self.state.states[node_id] = NodeState.READY
        self.state.cyclic = self.graph_cyclic()
        self.state.dangling = self.graph_dangling()

    # ------------------------------------------------------------------
    # DAG transitions.
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
        """Adds a task node, deferring missing dependency checks to validation and sorting."""
        require_arg(node_id, Domain.text(min_size=1), preferred=["alpha", "beta", "gamma"])
        require_arg(node_id, Domain.not_in(self.state.nodes), error=DuplicateNodeError)
        require_arg(action, Domain.type(Callable), preferred=[action_succeed])
        require_arg(
            dependencies,
            Domain.optional(Domain.type(Collection)),
            preferred=[None],
            fuzz_domain=Domain.optional(Domain.list_of(Domain.text(min_size=1))),
        )
        require_arg(priority, Domain.type(int), preferred=[0], fuzz_domain=Domain.sampled_from([0, 1, 2]))
        require_arg(retries, Domain.type(int), preferred=[0], fuzz_domain=Domain.sampled_from([0, 1]))
        self.inner_add_node(node_id, action, dependencies, priority, retries)
        declared: Set[str] = set() if dependencies is None else set(dependencies)
        self.state.nodes.append(node_id)
        self.state.actions[node_id] = action
        self.state.priorities[node_id] = priority
        self.state.retries[node_id] = retries
        self.state.declared[node_id] = declared
        self.state.upstream[node_id] = set(declared)
        self.state.downstream.setdefault(node_id, set())
        for dependency in declared:
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        self.state.states[node_id] = (
            NodeState.READY if self.dependencies_satisfied(declared) else NodeState.PENDING
        )
        self.state.cyclic = self.graph_cyclic()
        self.state.dangling = self.graph_dangling()
        assert node_id in self.state.nodes
        assert self.state.upstream[node_id] == declared
        assert self.dependencies_satisfied(declared) == (
            self.state.states[node_id] is NodeState.READY
        )

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge between two registered nodes."""
        require(bool(self.state.nodes))
        require_arg(upstream_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        require_arg(downstream_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        self.state.cyclic = self.graph_cyclic()
        self.state.dangling = self.graph_dangling()
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        """Removes a registered node together with all of its incident dependency edges."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        self.inner_remove_node(node_id)
        upstream_ids = set(self.state.upstream.get(node_id, set()))
        downstream_ids = set(self.state.downstream.get(node_id, set()))
        for dependency in upstream_ids:
            self.state.downstream.setdefault(dependency, set()).discard(node_id)
        for dependent in downstream_ids:
            self.state.upstream.setdefault(dependent, set()).discard(node_id)
        self.state.nodes.remove(node_id)
        self.state.actions.pop(node_id, None)
        self.state.priorities.pop(node_id, None)
        self.state.retries.pop(node_id, None)
        self.state.declared.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.states.pop(node_id, None)
        self.state.results.pop(node_id, None)
        self.state.cyclic = self.graph_cyclic()
        self.state.dangling = self.graph_dangling()
        assert node_id not in self.state.nodes
        assert node_id not in self.state.states

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the modeled graph."""
        require_arg(node_id, Domain.text(min_size=1), preferred=["alpha", "beta"])
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the registered immutable definition of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert ret.dependencies == frozenset(self.state.declared.get(node_id, set()))
        assert ret.priority == self.state.priorities.get(node_id, 0)
        assert ret.retries == self.state.retries.get(node_id, 0)
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns the direct upstream dependencies of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        ret = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns the direct downstream dependents of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        ret = self.inner_get_dependents(node_id)
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        """Returns every node identifier registered in the graph."""
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        """Validates dependency completeness and acyclicity of the graph."""
        require(not self.state.cyclic, error=CycleError)
        require(not self.state.dangling, error=NodeNotFoundError)
        self.inner_validate()
        assert not self.state.cyclic
        assert not self.state.dangling

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all registered nodes."""
        require(not self.state.cyclic, error=CycleError)
        ret = self.inner_topological_sort()
        assert set(ret) == set(self.state.nodes)
        assert all(
            ret.index(dependency) < ret.index(node_id)
            for node_id in self.state.nodes
            for dependency in self.state.upstream.get(node_id, set())
            if dependency in ret
        )
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        """Returns every node identifier that declares no dependency."""
        ret = self.inner_find_roots()
        assert ret == set(
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id, set())
        )
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        """Returns every node identifier that no other node depends on."""
        ret = self.inner_find_leaves()
        assert ret == set(
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id, set())
        )
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        require(not self.state.cyclic, error=CycleError)
        require_arg(
            estimated_durations,
            Domain.optional(Domain.mapping(Domain.text(min_size=1), Domain.type(float))),
            preferred=[None],
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        path, weight = ret
        assert all(node_id in self.state.nodes for node_id in path)
        assert isinstance(weight, (int, float))
        self.state.critical_path = list(path)
        return path, weight

    # ------------------------------------------------------------------
    # Wave scheduler transitions.
    # ------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies have succeeded."""
        ret = self.inner_next_wave()
        assert set(ret) <= set(self.state.nodes)
        assert ret == self.expected_wave()
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.inner_mark_running(node_id)
        self.state.states[node_id] = NodeState.RUNNING
        assert self.state.states[node_id] is NodeState.RUNNING

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to SUCCEEDED and promotes newly unblocked dependents."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        self.inner_mark_succeeded(node_id)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            if self.state.states.get(dependent) is NodeState.PENDING:
                if all(
                    self.state.states.get(dependency) is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(dependent, set())
                ):
                    self.state.states[dependent] = NodeState.READY
        assert self.state.states[node_id] is NodeState.SUCCEEDED

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Transitions a node to FAILED and applies the requested failure policy."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes))
        require_arg(
            failure_policy,
            Domain.sampled_from(FAILURE_POLICIES),
            preferred=[FailurePolicy.SKIP_DOWNSTREAM],
        )
        self.inner_mark_failed(node_id, failure_policy)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id in self.state.nodes:
                if self.state.states.get(other_id) not in TERMINAL_STATES:
                    self.state.states[other_id] = NodeState.CANCELLED
        else:
            for dependent in self.transitive_dependents(node_id):
                if self.state.states.get(dependent) not in TERMINAL_STATES:
                    self.state.states[dependent] = NodeState.SKIPPED
        assert self.state.states[node_id] is NodeState.FAILED
        if failure_policy is FailurePolicy.SKIP_DOWNSTREAM:
            assert all(
                self.state.states.get(dependent) in TERMINAL_STATES
                for dependent in self.transitive_dependents(node_id)
            )

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        """Determines whether every node has reached a terminal state."""
        ret = self.inner_is_finished()
        assert ret == self.engine_finished()
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a registered node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes), error=NodeNotFoundError)
        ret = self.inner_get_state(node_id)
        assert isinstance(ret, NodeState)
        self.state.states[node_id] = ret
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
        ret = self.inner_get_all_states()
        assert set(ret) == set(self.state.nodes)
        assert all(isinstance(state_value, NodeState) for state_value in ret.values())
        self.state.states = dict(ret)
        return ret

    # ------------------------------------------------------------------
    # Sequential runner transition.
    # ------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Executes the entire registered graph sequentially to completion under a failure policy."""
        require(not self.state.cyclic, error=CycleError)
        require(not self.state.dangling, error=NodeNotFoundError)
        require_arg(
            failure_policy,
            Domain.sampled_from(FAILURE_POLICIES),
            preferred=[FailurePolicy.CONTINUE_ON_ERROR],
        )
        ret = self.inner_run(failure_policy)
        self.state.results = dict(ret.results)
        self.state.critical_path = list(ret.critical_path)
        self.state.wall_clock = ret.wall_clock_seconds
        for node_id in self.state.nodes:
            if node_id in ret.results:
                self.state.states[node_id] = ret.results[node_id].state
        assert ret.total_nodes == len(self.state.nodes)
        assert isinstance(ret.succeeded_nodes, tuple)
        assert isinstance(ret.critical_path, tuple)
        assert set(ret.succeeded_nodes) <= set(self.state.nodes)
        assert set(ret.failed_nodes) <= set(self.state.nodes)
        assert set(ret.skipped_nodes) <= set(self.state.nodes)
        assert set(ret.cancelled_nodes) <= set(self.state.nodes)
        assert ret.wall_clock_seconds >= 0.0
        return ret

    # ------------------------------------------------------------------
    # Inner transitions: fake return computation from model state only.
    # ------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Computes the fake return value of add_node."""
        return None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Computes the fake return value of add_edge."""
        return None

    def inner_remove_node(self, node_id: str) -> None:
        """Computes the fake return value of remove_node."""
        return None

    def inner_has_node(self, node_id: str) -> bool:
        """Computes the fake return value of has_node."""
        return node_id in self.state.nodes

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Computes the fake return value of get_node."""
        return NodeDefinition(
            node_id=node_id,
            action=self.state.actions.get(node_id, action_succeed),
            dependencies=frozenset(self.state.declared.get(node_id, set())),
            priority=self.state.priorities.get(node_id, 0),
            retries=self.state.retries.get(node_id, 0),
        )

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        """Computes the fake return value of get_dependencies."""
        return set(self.state.upstream.get(node_id, set()))

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        """Computes the fake return value of get_dependents."""
        return set(self.state.downstream.get(node_id, set()))

    def inner_all_nodes(self) -> Set[str]:
        """Computes the fake return value of all_nodes."""
        return set(self.state.nodes)

    def inner_validate(self) -> None:
        """Computes the fake return value of validate."""
        return None

    def inner_topological_sort(self) -> List[str]:
        """Computes the fake return value of topological_sort."""
        return self.sorted_order()

    def inner_find_roots(self) -> Set[str]:
        """Computes the fake return value of find_roots."""
        return set(
            node_id for node_id in self.state.nodes if not self.state.upstream.get(node_id, set())
        )

    def inner_find_leaves(self) -> Set[str]:
        """Computes the fake return value of find_leaves."""
        return set(
            node_id for node_id in self.state.nodes if not self.state.downstream.get(node_id, set())
        )

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the fake return value of compute_critical_path."""
        return self.critical_path_best(estimated_durations)

    def inner_next_wave(self) -> List[str]:
        """Computes the fake return value of next_wave."""
        return self.expected_wave()

    def inner_mark_running(self, node_id: str) -> None:
        """Computes the fake return value of mark_running."""
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Computes the fake return value of mark_succeeded."""
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Computes the fake return value of mark_failed."""
        return None

    def inner_is_finished(self) -> bool:
        """Computes the fake return value of is_finished."""
        return self.engine_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        """Computes the fake return value of get_state."""
        return self.state.states.get(node_id, NodeState.PENDING)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        """Computes the fake return value of get_all_states."""
        return {
            node_id: self.state.states.get(node_id, NodeState.PENDING)
            for node_id in self.state.nodes
        }

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Computes the fake return value of run."""
        path, _ = self.critical_path_best(None)
        results: Dict[str, NodeResult[Any]] = {
            node_id: NodeResult(node_id=node_id, state=NodeState.SUCCEEDED, value=None)
            for node_id in self.state.nodes
        }
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

FakeDAGEngine = synthesize_fake(DAGEngineStateMachine)


def make_dag_fake(state: Optional[DAGEngineState] = None) -> DAG:
    """Synthesizes a fake DAG service sharing the given model state."""
    return FakeDAGEngine(state=state if state is not None else DAGEngineState())


def make_scheduler_fake(state: Optional[DAGEngineState] = None) -> WaveScheduler:
    """Synthesizes a fake wave scheduler service sharing the given model state."""
    return FakeDAGEngine(state=state if state is not None else DAGEngineState())


def make_runner_fake(state: Optional[DAGEngineState] = None) -> DAGRunner:
    """Synthesizes a fake sequential runner service sharing the given model state."""
    return FakeDAGEngine(state=state if state is not None else DAGEngineState())


# Fake Fuzzing (Exercises the synthesized fake against state machine contracts):
FakeDAGEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestDAGEngineFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.sm = DAGEngineStateMachine()
        self.fake = make_dag_fake(self.sm.state)

    def test_seeding_and_graph_transitions(self) -> None:
        """Exercises the seeding transition and every graph query transition."""
        self.sm.seed_node()
        _ = self.fake.has_node("seed_0")
        self.sm.add_node("alpha", action_succeed, None, 0, 0)
        self.sm.add_node("beta", action_alternative, ("alpha",), 1, 0)
        self.sm.add_node("gamma", action_fail, ("beta",), 2, 1)
        _ = self.sm.has_node("alpha")
        _ = self.sm.get_node("beta")
        _ = self.sm.get_dependencies("beta")
        _ = self.sm.get_dependents("alpha")
        _ = self.sm.all_nodes()
        self.sm.add_edge("alpha", "gamma")
        self.sm.validate()
        _ = self.sm.topological_sort()
        _ = self.sm.find_roots()
        _ = self.sm.find_leaves()
        _ = self.sm.compute_critical_path(None)
        _ = self.sm.compute_critical_path({"alpha": 2.0, "beta": 0.5})
        self.sm.remove_node("gamma")
        _ = self.sm.all_nodes()
        _ = self.sm.find_leaves()

    def test_scheduler_transitions(self) -> None:
        """Exercises every wave scheduler transition through a successful run."""
        self.sm.add_node("alpha", action_succeed, None, 0, 0)
        self.sm.add_node("beta", action_succeed, None, 1, 0)
        self.sm.add_node("gamma", action_succeed, ("alpha",), 0, 0)
        _ = self.sm.next_wave()
        self.sm.mark_running("beta")
        self.sm.mark_succeeded("beta")
        self.sm.mark_running("alpha")
        self.sm.mark_succeeded("alpha")
        _ = self.sm.next_wave()
        self.sm.mark_running("gamma")
        self.sm.mark_succeeded("gamma")
        _ = self.sm.get_state("gamma")
        _ = self.sm.get_all_states()
        _ = self.sm.is_finished()

    def test_failure_policies(self) -> None:
        """Exercises every failure policy branch of the wave scheduler transition."""
        self.sm.add_node("alpha", action_fail, None, 0, 0)
        self.sm.add_node("beta", action_succeed, ("alpha",), 0, 0)
        self.sm.mark_running("alpha")
        self.sm.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        _ = self.sm.is_finished()
        self.sm.add_node("delta", action_succeed, None, 0, 0)
        self.sm.add_node("epsilon", action_succeed, None, 0, 0)
        self.sm.mark_running("delta")
        self.sm.mark_failed("delta", FailurePolicy.FAIL_FAST)
        _ = self.sm.is_finished()
        self.sm.add_node("zeta", action_succeed, None, 0, 0)
        self.sm.mark_running("zeta")
        self.sm.mark_failed("zeta", FailurePolicy.CONTINUE_ON_ERROR)
        _ = self.sm.get_all_states()
        _ = self.sm.is_finished()

    def test_runner_transition(self) -> None:
        """Exercises the sequential runner transition on the fake."""
        self.sm.add_node("alpha", action_succeed, None, 0, 0)
        self.sm.add_node("beta", action_succeed, ("alpha",), 1, 0)
        _ = self.sm.run(FailurePolicy.CONTINUE_ON_ERROR)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:38:37Z
# LAST_CHANGED: 2026-11-13T00:38:37Z
# CHANGE: Resolves [from:pretense_qa] dependency collection domain over-restriction: add_node now validates dependencies with Domain.optional(Domain.type(Collection)) (accepts any collection of node identifiers, e.g. ('alpha','delta'), lists, sets, or None) instead of the closed sampled_from(DEPENDENCY_CHOICES) set, with a bounded string-list fuzz_domain for generation; likewise relaxes the action gate to Domain.type(Callable), priority/retries to Domain.type(int) with small fuzz domains, and compute_critical_path durations to an optional mapping domain; the critical path weight assertion now checks numeric type instead of non-negativity so arbitrary duration weights remain valid.
# --- END AUTOFAB METADATA ---
