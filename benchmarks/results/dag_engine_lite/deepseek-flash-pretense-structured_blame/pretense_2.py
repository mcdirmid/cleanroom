# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, Mapping, Optional, Set, Tuple
import unittest

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase

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
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGImpl,
    DAGRunner as DAGRunnerImpl,
    WaveScheduler as WaveSchedulerImpl,
)
from dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineStateMachine,
    constant_action,
    noop_action,
)


def raising_action() -> None:
    """Callable action that always raises to exercise retry and failure policies."""
    raise RuntimeError("node action failed")


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DAGEngineImplPseudoStateMachine(DAGEngineStateMachine):
    """Implementation pseudo-state machine binding the DAG engine transitions to the SUT."""

    # --------------------------------------------------------------------------
    # DAG: node registration and graph structure
    # --------------------------------------------------------------------------

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
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        assert definition.dependencies == frozenset(dependencies or ())
        assert definition.priority == priority
        assert definition.retries == retries
        return None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        target.add_edge(upstream_id, downstream_id)
        assert upstream_id in target.get_dependencies(downstream_id)
        assert downstream_id in target.get_dependents(upstream_id)
        return None

    def inner_remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        target.remove_node(node_id)
        assert not target.has_node(node_id)
        for other_id in target.all_nodes():
            assert node_id not in target.get_dependencies(other_id)
            assert node_id not in target.get_dependents(other_id)
        return None

    def inner_has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        ret = target.has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        ret = target.get_node(node_id)
        assert ret.node_id == node_id
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.get_dependencies(node_id)
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.get_dependents(node_id)
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    def inner_all_nodes(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    def inner_validate(self) -> None:
        target: DAG = sut(DAG)
        target.validate()
        return None

    def inner_topological_sort(self) -> list[str]:
        target: DAG = sut(DAG)
        ret = target.topological_sort()
        assert sorted(ret) == sorted(self.state.nodes)
        positions = {node_id: index for index, node_id in enumerate(ret)}
        assert all(
            positions[dependency] < positions[node_id]
            for node_id in ret
            for dependency in self.state.upstream.get(node_id, set())
        )
        return ret

    def inner_find_roots(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.find_roots()
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.upstream.get(node_id)
        }
        return ret

    def inner_find_leaves(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = target.find_leaves()
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[list[str], float]:
        target: DAG = sut(DAG)
        ret = target.compute_critical_path(estimated_durations)
        assert all(node_id in self.state.nodes for node_id in ret[0])
        assert ret[1] >= 0.0
        return ret

    # --------------------------------------------------------------------------
    # WaveScheduler: wave resolution and execution-state bookkeeping
    # --------------------------------------------------------------------------

    def inner_next_wave(self) -> list[str]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.next_wave()
        assert set(ret) <= set(self.state.nodes)
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_running(node_id)
        assert target.get_state(node_id) == NodeState.RUNNING
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_succeeded(node_id)
        assert target.get_state(node_id) == NodeState.SUCCEEDED
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_failed(node_id, failure_policy)
        assert target.get_state(node_id) == NodeState.FAILED
        return None

    def inner_is_finished(self) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.is_finished()
        assert isinstance(ret, bool)
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.get_state(node_id)
        assert isinstance(ret, NodeState)
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = target.get_all_states()
        assert set(ret) <= set(self.state.nodes)
        return ret

    # --------------------------------------------------------------------------
    # DAGRunner: consolidated execution
    # --------------------------------------------------------------------------

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        report = target.run(failure_policy)
        assert report.total_nodes == len(self.state.nodes)
        assert set(report.results) <= set(self.state.nodes)
        return report


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDAGEngineImplReal(LifecycleTestCase):
    """Verifies that the concrete DAG engine implementation satisfies its contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.assertIsInstance(self.get_singleton(DAG), DAGImpl)
        self.assertIsInstance(self.get_singleton(WaveScheduler), WaveSchedulerImpl)
        self.assertIsInstance(self.get_singleton(DAGRunner), DAGRunnerImpl)
        self.sm = DAGEngineImplPseudoStateMachine(
            singletons={
                DAG: self.get_singleton(DAG),
                WaveScheduler: self.get_singleton(WaveScheduler),
                DAGRunner: self.get_singleton(DAGRunner),
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, self.get_singleton(DAG))
        self.checked_scheduler = self.sm.as_checked(
            WaveScheduler, self.get_singleton(WaveScheduler)
        )
        self.checked_runner = self.sm.as_checked(
            DAGRunner, self.get_singleton(DAGRunner)
        )

    def test_graph_structure_operations(self) -> None:
        """Registers nodes, queries structure, validates, orders, and removes nodes."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", constant_action, ["alpha"], 2, 1)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 1, 0)
        self.checked_dag.add_node("delta", noop_action, [], -1, 2)
        assert self.checked_dag.has_node("alpha") is True
        assert self.checked_dag.has_node("missing") is False
        definition = self.checked_dag.get_node("beta")
        assert definition.node_id == "beta"
        assert self.checked_dag.get_dependencies("beta") == {"alpha"}
        assert self.checked_dag.get_dependents("alpha") == {"beta"}
        assert self.checked_dag.all_nodes() == {"alpha", "beta", "gamma", "delta"}
        self.checked_dag.add_edge("alpha", "delta")
        self.checked_dag.validate()
        order = self.checked_dag.topological_sort()
        assert order[0] == "alpha"
        assert order[-1] == "delta"
        assert self.checked_dag.find_roots() == {"alpha"}
        assert self.checked_dag.find_leaves() == {"gamma", "delta"}
        path, weight = self.checked_dag.compute_critical_path(
            {"alpha": 1.0, "beta": 2.0, "gamma": 3.0, "delta": 4.0}
        )
        assert weight == 6.0
        assert path == ["alpha", "beta", "gamma"]
        default_path, default_weight = self.checked_dag.compute_critical_path(None)
        assert default_weight == 3.0
        assert default_path == ["alpha", "beta", "gamma"]
        self.checked_dag.remove_node("delta")
        assert self.checked_dag.all_nodes() == {"alpha", "beta", "gamma"}

    def test_remove_node_purges_incident_edges(self) -> None:
        """Removes a node that carries dependents and purges every incident edge."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 2, 0)
        self.checked_dag.add_edge("beta", "gamma")
        assert self.checked_dag.get_dependents("alpha") == {"beta", "gamma"}
        self.checked_dag.remove_node("alpha")
        assert self.checked_dag.all_nodes() == {"beta", "gamma"}
        assert self.checked_dag.get_dependencies("beta") == set()
        assert self.checked_dag.get_dependencies("gamma") == {"beta"}
        assert self.checked_dag.find_roots() == {"beta"}

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Purges a removed node from scheduler state discovered by wave resolution."""
        self.checked_dag.add_node("alpha", noop_action, None, 1, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_dag.remove_node("beta")
        assert self.checked_dag.all_nodes() == {"alpha"}
        states = self.checked_scheduler.get_all_states()
        assert set(states) == {"alpha"}
        assert self.checked_scheduler.get_state("alpha") == NodeState.READY

    def test_scheduler_wave_progression(self) -> None:
        """Drives a linear graph through every sequential wave to completion."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", constant_action, ["alpha"], 2, 1)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 1, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        assert self.checked_scheduler.get_state("alpha") == NodeState.RUNNING
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("alpha") == NodeState.SUCCEEDED
        assert self.checked_scheduler.next_wave() == ["beta"]
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        assert self.checked_scheduler.next_wave() == ["gamma"]
        self.checked_scheduler.mark_running("gamma")
        self.checked_scheduler.mark_succeeded("gamma")
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.is_finished() is True
        states = self.checked_scheduler.get_all_states()
        assert set(states) == {"alpha", "beta", "gamma"}
        assert states["gamma"] == NodeState.SUCCEEDED

    def test_scheduler_skip_downstream_policy(self) -> None:
        """Marks a failed node and skips all of its transitive dependents."""
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("beta") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_continue_on_error_policy(self) -> None:
        """Keeps independent ready nodes executable when a sibling node fails."""
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("gamma", noop_action, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "gamma"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("beta") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY
        assert self.checked_scheduler.is_finished() is False
        self.checked_scheduler.mark_running("gamma")
        self.checked_scheduler.mark_succeeded("gamma")
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_fail_fast_policy(self) -> None:
        """Cancels every remaining non-terminal node when a node fails fast."""
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("gamma", noop_action, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "gamma"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        assert self.checked_scheduler.get_state("beta") == NodeState.CANCELLED
        assert self.checked_scheduler.get_state("gamma") == NodeState.CANCELLED
        assert self.checked_scheduler.is_finished() is True

    def test_next_wave_late_dependent_registration(self) -> None:
        """Resolves a dependent registered after its prerequisite already succeeded."""
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        wave = self.checked_scheduler.next_wave()
        assert set(wave) <= {"beta"}
        assert "alpha" not in wave

    def test_mark_succeeded_repeated_with_ready_dependent(self) -> None:
        """Repeats a success transition whose dependent is already promoted to ready."""
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("beta") == NodeState.READY
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("alpha") == NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("beta") == NodeState.READY

    def test_scheduler_skip_downstream_diamond(self) -> None:
        """Skips a reconverged diamond join when one upstream branch fails downstream."""
        self.checked_dag.add_node("alpha", noop_action, None, 3, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 2, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["beta", "gamma"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("beta") == NodeState.READY
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_failed("beta", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("delta") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY

    def test_scheduler_continue_on_error_diamond(self) -> None:
        """Keeps an unblocked diamond branch eligible when a converged path fails."""
        self.checked_dag.add_node("alpha", noop_action, None, 3, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 2, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["beta", "gamma"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_failed("beta", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("delta") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY
        assert self.checked_scheduler.is_finished() is False

    def test_add_node_defers_missing_dependency(self) -> None:
        """Registers an unresolved dependency and inspects it through the scheduler."""
        self.checked_dag.add_node("alpha", noop_action, ["missing"], 0, 0)
        assert self.checked_dag.has_node("alpha") is True
        states = self.checked_scheduler.get_all_states()
        assert set(states) == {"alpha"}
        assert states["alpha"] == NodeState.PENDING
        assert self.checked_scheduler.next_wave() == []

    def test_mark_succeeded_partial_prerequisite_success(self) -> None:
        """Holds a two-prerequisite dependent pending until its second prerequisite succeeds."""
        self.checked_dag.add_node("alpha", noop_action, None, 2, 0)
        self.checked_dag.add_node("beta", noop_action, None, 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["alpha", "beta"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha", "beta"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("alpha") == NodeState.SUCCEEDED
        assert self.checked_scheduler.get_state("delta") == NodeState.PENDING
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_succeeded("beta")
        assert self.checked_scheduler.get_state("delta") == NodeState.READY

    def test_scheduler_skip_downstream_apex_failure(self) -> None:
        """Skips every converging branch when the diamond apex node fails."""
        self.checked_dag.add_node("alpha", noop_action, None, 3, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 2, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["beta", "gamma"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("beta") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("gamma") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("delta") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_continue_on_error_unblocked_join(self) -> None:
        """Leaves a join independent of the failed branch pending but never skipped."""
        self.checked_dag.add_node("alpha", noop_action, None, 3, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 2, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("delta", noop_action, ["alpha", "gamma"], 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        self.checked_scheduler.mark_succeeded("alpha")
        assert self.checked_scheduler.get_state("beta") == NodeState.READY
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY
        assert self.checked_scheduler.get_state("delta") == NodeState.PENDING
        self.checked_scheduler.mark_running("beta")
        self.checked_scheduler.mark_failed("beta", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("delta") == NodeState.PENDING
        assert self.checked_scheduler.get_state("gamma") == NodeState.READY
        assert self.checked_scheduler.is_finished() is False

    def test_is_finished_unresolved_deferred_dependency(self) -> None:
        """Exercises completion inspection while a node awaits an unregistered dependency."""
        self.checked_dag.add_node("alpha", noop_action, ["missing"], 0, 0)
        assert self.checked_scheduler.next_wave() == []
        self.checked_scheduler.is_finished()
        states = self.checked_scheduler.get_all_states()
        assert set(states) == {"alpha"}
        assert states["alpha"] == NodeState.PENDING

    def test_runner_successful_execution(self) -> None:
        """Executes every ready wave and reports all nodes as succeeded."""
        self.checked_dag.add_node("alpha", noop_action, None, 3, 0)
        self.checked_dag.add_node("beta", constant_action, ["alpha"], 1, 0)
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"alpha", "beta"}
        assert set(report.results) == {"alpha", "beta"}
        assert report.critical_path == ("alpha", "beta")

    def test_runner_retries_failed_action(self) -> None:
        """Retries a failing action and applies the skip downstream policy."""
        self.checked_dag.add_node("alpha", raising_action, None, 2, 2)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 0, 0)
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 2
        assert "alpha" in report.failed_nodes
        assert "beta" in report.skipped_nodes

    def test_runner_fail_fast_execution(self) -> None:
        """Halts wave execution and cancels remaining work under fail fast."""
        self.checked_dag.add_node("alpha", raising_action, None, 3, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, 0)
        self.checked_dag.add_node("gamma", noop_action, None, 0, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 3
        assert "alpha" in report.failed_nodes

    def test_runner_empty_dag(self) -> None:
        """Executes an empty graph and reports a vacuous completed run."""
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 0
        assert self.checked_scheduler.is_finished() is True

    def test_runner_empty_wave_stall_boundary(self) -> None:
        """Stops wave execution when a preoccupied running node leaves no ready wave."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        assert self.checked_scheduler.next_wave() == ["alpha"]
        self.checked_scheduler.mark_running("alpha")
        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 1

    # --------------------------------------------------------------------------
    # Contract violation scenarios (checked caller precondition violations)
    # --------------------------------------------------------------------------

    def test_add_node_duplicate_node_error(self) -> None:
        """Rejects registration of an already registered node identifier."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node(
            "alpha", noop_action, None, 0, 0
        )

    def test_add_edge_missing_upstream_node_error(self) -> None:
        """Rejects a dependency edge whose upstream node does not exist."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("missing", "alpha")

    def test_add_edge_missing_downstream_node_error(self) -> None:
        """Rejects a dependency edge whose downstream node does not exist."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("alpha", "missing")

    def test_remove_node_missing_node_error(self) -> None:
        """Rejects removal of a node identifier that is not registered."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).remove_node("missing")

    def test_get_node_missing_node_error(self) -> None:
        """Rejects definition lookup for an unregistered node identifier."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("missing")

    def test_get_dependencies_missing_node_error(self) -> None:
        """Rejects upstream dependency lookup for an unregistered node identifier."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_missing_node_error(self) -> None:
        """Rejects downstream dependent lookup for an unregistered node identifier."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_validate_missing_dependency_error(self) -> None:
        """Rejects validation when a registered node references a missing dependency."""
        self.checked_dag.add_node("alpha", noop_action, ["missing"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle_error(self) -> None:
        """Rejects validation when the graph contains a directed cycle."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", noop_action, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).validate()

    def test_topological_sort_cycle_error(self) -> None:
        """Rejects topological ordering when the graph contains a directed cycle."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", noop_action, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_dag.violating(CycleError).topological_sort()

    def test_run_missing_dependency_error(self) -> None:
        """Rejects execution when a registered node references a missing dependency."""
        self.checked_dag.add_node("alpha", noop_action, ["missing"], 0, 0)
        self.checked_runner.violating(NodeNotFoundError).run(
            FailurePolicy.CONTINUE_ON_ERROR
        )

    def test_run_cycle_error(self) -> None:
        """Rejects execution when the graph contains a directed cycle."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_dag.add_node("beta", noop_action, None, 0, 0)
        self.checked_dag.add_edge("alpha", "beta")
        self.checked_dag.add_edge("beta", "alpha")
        self.checked_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

    def test_get_state_missing_node_error(self) -> None:
        """Rejects scheduler state lookup for an unregistered node identifier."""
        self.checked_dag.add_node("alpha", noop_action, None, 0, 0)
        self.checked_scheduler.violating(NodeNotFoundError).get_state("missing")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:57:20Z
# LAST_CHANGED: 2026-11-12T16:56:52Z
# CHANGE: Resolve pretense_qa feedback: remove the uncontracted is_finished() completion expectation for a node awaiting an unregistered dependency (actual completion state is not contracted for deferred/unresolved dependencies), while still exercising the completion-inspection path and asserting the contracted post-state that the unresolved node remains PENDING and registered.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T16:57:20Z
# PRETENSE_QA_AUDIT: 2026-11-12T16:57:07Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Mapping, Optional, Sequence, Set, Tuple
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
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGError,
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
# Model helpers (pure computations over abstract model state)
# ==============================================================================

TERMINAL_STATES: frozenset[NodeState] = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


def noop_action() -> None:
    """Trivial callable action used for synthesized fake node definitions."""
    return None


def constant_action() -> int:
    """Constant-returning callable action used for synthesized fake node definitions."""
    return 1


def priority_order(
    node_ids: Collection[str],
    nodes: Mapping[str, NodeDefinition[Any]],
) -> list[str]:
    """Orders node identifiers by priority descending, then identifier ascending."""
    ranked = sorted((-nodes[node_id].priority, node_id) for node_id in node_ids)
    return [node_id for _, node_id in ranked]


def kahn_order(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> Optional[list[str]]:
    """Computes a deterministic priority-ordered topological order, or None on a cycle."""
    indegree = {node_id: len(upstream.get(node_id, set())) for node_id in nodes}
    order: list[str] = []
    for _ in range(len(nodes) + 1):
        candidates = {
            node_id
            for node_id in nodes
            if node_id not in order and indegree[node_id] == 0
        }
        if not candidates:
            break
        node_id = priority_order(candidates, nodes)[0]
        order.append(node_id)
        for dependent in downstream.get(node_id, set()):
            if dependent in indegree:
                indegree[dependent] -= 1
    if len(order) != len(nodes):
        return None
    return order


def is_acyclic(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> bool:
    """Determines whether the modeled dependency graph is acyclic."""
    return kahn_order(nodes, upstream, downstream) is not None


def critical_path_of(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    durations: Optional[Mapping[str, float]],
) -> Tuple[list[str], float]:
    """Computes the longest weighted dependency path and its cumulative weight."""
    order = kahn_order(nodes, upstream, downstream)
    if order is None:
        return ([], 0.0)
    if not order:
        return ([], 0.0)
    earliest: dict[str, float] = {}
    predecessor: dict[str, str] = {}
    for node_id in order:
        candidate_weight = 1.0 if durations is None else float(durations.get(node_id, 1.0))
        weight = candidate_weight if candidate_weight >= 0.0 else 1.0
        weight = weight if weight <= 1000000.0 else 1000000.0
        best = 0.0
        best_predecessor = ""
        for dependency in upstream.get(node_id, set()):
            candidate = earliest.get(dependency, 0.0)
            if candidate > best:
                best = candidate
                best_predecessor = dependency
        earliest[node_id] = best + weight
        if best_predecessor:
            predecessor[node_id] = best_predecessor
    terminal = order[0]
    for node_id in order:
        if earliest[node_id] > earliest[terminal]:
            terminal = node_id
    path = [terminal]
    for _ in range(len(order) + 1):
        previous = predecessor.get(path[-1])
        if previous is None:
            break
        path.append(previous)
    path.reverse()
    return (path, earliest[terminal])


def sync_states(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    node_states: dict[str, NodeState],
) -> None:
    """Discovers newly registered nodes, seeding roots as READY and others as PENDING."""
    for node_id in nodes:
        if node_id not in node_states:
            if upstream.get(node_id):
                node_states[node_id] = NodeState.PENDING
            else:
                node_states[node_id] = NodeState.READY


def reachable_dependents(
    node_id: str,
    downstream: Mapping[str, Set[str]],
) -> set[str]:
    """Collects the transitive downstream dependents of a node."""
    discovered = {node_id}
    frontier = [node_id]
    for _ in range(len(downstream) + 1):
        next_frontier: list[str] = []
        for current in frontier:
            for dependent in downstream.get(current, set()):
                if dependent not in discovered:
                    discovered.add(dependent)
                    next_frontier.append(dependent)
        if not next_frontier:
            break
        frontier = next_frontier
    return discovered - {node_id}


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DAGEngineState:
    """Model state tracking registered nodes, dependency edges, and execution states."""
    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    dependencies_valid: bool = True
    acyclic: bool = True


class DAGEngineStateMachine(StateMachine[DAGEngineState]):
    """Unified Pretense State Machine for the DAG engine component services."""

    def __init__(
        self,
        state: Optional[DAGEngineState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return DAGEngineState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.dependencies_valid = True
        self.state.acyclic = True

    # --------------------------------------------------------------------------
    # DAG: node registration and graph structure
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
        """Adds a task node to the modeled graph, deferring missing dependency checks."""
        require_arg(node_id, Domain.type(str), preferred=["alpha", "beta", "gamma"], error=DuplicateNodeError)
        require_arg(action, Domain.any())
        require_arg(dependencies, Domain.type(Optional[Collection[str]]))
        require_arg(priority, Domain.integers(-3, 3))
        require_arg(retries, Domain.integers(0, 2))
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies or ()),
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream.setdefault(node_id, set()).update(definition.dependencies)
        self.state.downstream.setdefault(node_id, set())
        for dependency in definition.dependencies:
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        self.state.dependencies_valid = all(
            dependency in self.state.nodes
            for dependency_ids in self.state.upstream.values()
            for dependency in dependency_ids
        )
        self.state.acyclic = is_acyclic(
            self.state.nodes, self.state.upstream, self.state.downstream
        )
        assert ret is None
        assert self.state.nodes[node_id].node_id == node_id
        assert self.state.nodes[node_id].dependencies == frozenset(dependencies or ())

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Computes fake return value for a node registration."""
        return None

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge between two registered nodes."""
        require(bool(self.state.nodes))
        require_arg(upstream_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        require_arg(downstream_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        self.state.acyclic = is_acyclic(
            self.state.nodes, self.state.upstream, self.state.downstream
        )
        assert ret is None
        assert upstream_id in self.state.upstream.get(downstream_id, set())
        assert downstream_id in self.state.downstream.get(upstream_id, set())

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Computes fake return value for a dependency edge insertion."""
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        """Removes a node and purges all of its incident edges."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        ret = self.inner_remove_node(node_id)
        for dependency in self.state.upstream.get(node_id, set()):
            self.state.downstream.setdefault(dependency, set()).discard(node_id)
        for dependent in self.state.downstream.get(node_id, set()):
            self.state.upstream.setdefault(dependent, set()).discard(node_id)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.nodes.pop(node_id, None)
        self.state.node_states.pop(node_id, None)
        self.state.dependencies_valid = all(
            dependency in self.state.nodes
            for dependency_ids in self.state.upstream.values()
            for dependency in dependency_ids
        )
        self.state.acyclic = is_acyclic(
            self.state.nodes, self.state.upstream, self.state.downstream
        )
        assert ret is None
        assert node_id not in self.state.nodes

    def inner_remove_node(self, node_id: str) -> None:
        """Computes fake return value for a node removal."""
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        """Reports whether a node identifier is registered in the modeled graph."""
        require_arg(node_id, Domain.type(str))
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        """Computes fake return value for node membership."""
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Returns the registered immutable node definition."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Computes fake return value for a node definition lookup."""
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns the direct upstream dependency identifiers of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        ret = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.upstream.get(node_id, set()))
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        """Computes fake return value for upstream dependency identifiers."""
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns the direct downstream dependent identifiers of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        ret = self.inner_get_dependents(node_id)
        assert ret == set(self.state.downstream.get(node_id, set()))
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        """Computes fake return value for downstream dependent identifiers."""
        return set(self.state.downstream.get(node_id, set()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        """Returns every registered node identifier."""
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    def inner_all_nodes(self) -> Set[str]:
        """Computes fake return value for all registered node identifiers."""
        return set(self.state.nodes)

    @transition(DAG.validate)
    def validate(self) -> None:
        """Validates that dependencies exist and that the graph is acyclic."""
        require(self.state.dependencies_valid, error=NodeNotFoundError)
        require(self.state.acyclic, error=CycleError)
        ret = self.inner_validate()
        assert ret is None

    def inner_validate(self) -> None:
        """Computes fake behavior for graph validation."""
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> list[str]:
        """Returns a priority-tie-broken topological ordering of all nodes."""
        require(self.state.dependencies_valid, error=CycleError)
        require(self.state.acyclic, error=CycleError)
        ret = self.inner_topological_sort()
        positions = {node_id: index for index, node_id in enumerate(ret)}
        assert set(ret) <= set(self.state.nodes)
        assert all(
            positions.get(dependency, -1) < positions[node_id]
            for node_id in ret
            for dependency in self.state.upstream.get(node_id, set())
        )
        return ret

    def inner_topological_sort(self) -> list[str]:
        """Computes fake return value for the topological ordering."""
        order = kahn_order(self.state.nodes, self.state.upstream, self.state.downstream)
        return [] if order is None else order

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        """Returns all nodes without any upstream dependencies."""
        ret = self.inner_find_roots()
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.upstream.get(node_id)
        }
        return ret

    def inner_find_roots(self) -> Set[str]:
        """Computes fake return value for root node identifiers."""
        return {
            node_id
            for node_id in self.state.nodes
            if not self.state.upstream.get(node_id)
        }

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        """Returns all nodes without any downstream dependents."""
        ret = self.inner_find_leaves()
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        return ret

    def inner_find_leaves(self) -> Set[str]:
        """Computes fake return value for leaf node identifiers."""
        return {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[list[str], float]:
        """Returns the longest weighted dependency path and its cumulative weight."""
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        assert all(node_id in self.state.nodes for node_id in ret[0])
        assert ret[1] >= 0.0
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[list[str], float]:
        """Computes fake return value for the weighted critical path."""
        return critical_path_of(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )

    # --------------------------------------------------------------------------
    # WaveScheduler: wave resolution and execution-state bookkeeping
    # --------------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> list[str]:
        """Returns the next batch of ready nodes ordered by priority."""
        sync_states(self.state.nodes, self.state.upstream, self.state.node_states)
        ret = self.inner_next_wave()
        assert set(ret) <= set(self.state.nodes)
        assert all(
            self.state.node_states.get(node_id) == NodeState.READY
            for node_id in ret
        )
        return ret

    def inner_next_wave(self) -> list[str]:
        """Computes fake return value for the next ready wave."""
        ready = {
            node_id
            for node_id in self.state.nodes
            if self.state.node_states.get(node_id) == NodeState.READY
            and all(
                self.state.node_states.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(node_id, set())
            )
        }
        return priority_order(ready, self.state.nodes)

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        """Transitions a modeled node into the RUNNING state."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_mark_running(node_id)
        self.state.node_states[node_id] = NodeState.RUNNING
        assert ret is None
        assert self.state.node_states.get(node_id) == NodeState.RUNNING

    def inner_mark_running(self, node_id: str) -> None:
        """Computes fake behavior for a RUNNING transition."""
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a modeled node into the SUCCEEDED state and promotes dependents."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)))
        ret = self.inner_mark_succeeded(node_id)
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            if self.state.node_states.get(dependent) == NodeState.PENDING and all(
                self.state.node_states.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(dependent, set())
            ):
                self.state.node_states[dependent] = NodeState.READY
        assert ret is None
        assert self.state.node_states.get(node_id) == NodeState.SUCCEEDED

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Computes fake behavior for a SUCCEEDED transition."""
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Transitions a modeled node into the FAILED state and applies the failure policy."""
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
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.node_states[node_id] = NodeState.FAILED
        blocked = reachable_dependents(node_id, self.state.downstream)
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other_id in self.state.nodes:
                if self.state.node_states.get(other_id) not in TERMINAL_STATES:
                    self.state.node_states[other_id] = NodeState.CANCELLED
        else:
            for dependent in blocked:
                if self.state.node_states.get(dependent) not in TERMINAL_STATES:
                    self.state.node_states[dependent] = NodeState.SKIPPED
        assert ret is None
        assert self.state.node_states.get(node_id) == NodeState.FAILED

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Computes fake behavior for a FAILED transition."""
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        """Reports whether every modeled node has reached a terminal state."""
        sync_states(self.state.nodes, self.state.upstream, self.state.node_states)
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    def inner_is_finished(self) -> bool:
        """Computes fake return value for completion detection."""
        return all(
            self.state.node_states.get(node_id) in TERMINAL_STATES
            for node_id in self.state.nodes
        )

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        """Returns the modeled execution state of a registered node."""
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(set(self.state.nodes)), error=NodeNotFoundError)
        sync_states(self.state.nodes, self.state.upstream, self.state.node_states)
        ret = self.inner_get_state(node_id)
        assert ret == self.state.node_states.get(node_id)
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        """Computes fake return value for a node execution state lookup."""
        return self.state.node_states.get(node_id, NodeState.PENDING)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the modeled execution state of every registered node."""
        sync_states(self.state.nodes, self.state.upstream, self.state.node_states)
        ret = self.inner_get_all_states()
        assert set(ret) <= set(self.state.nodes)
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        """Computes fake return value for all node execution states."""
        return {
            node_id: self.state.node_states.get(node_id, NodeState.PENDING)
            for node_id in self.state.nodes
        }

    # --------------------------------------------------------------------------
    # DAGRunner: consolidated execution
    # --------------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Executes the modeled graph to completion under the supplied failure policy."""
        require(self.state.dependencies_valid, error=NodeNotFoundError)
        require(self.state.acyclic, error=CycleError)
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
        sync_states(self.state.nodes, self.state.upstream, self.state.node_states)
        for node_id in self.state.nodes:
            if self.state.node_states.get(node_id) not in TERMINAL_STATES:
                self.state.node_states[node_id] = NodeState.SUCCEEDED
        ret = self.inner_run(failure_policy)
        assert isinstance(ret, DAGRunReport)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Computes fake return value for a consolidated execution report."""
        path, _weight = critical_path_of(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            None,
        )
        results: dict[str, NodeResult[Any]] = {}
        for node_id in self.state.nodes:
            results[node_id] = NodeResult(
                node_id=node_id,
                state=self.state.node_states.get(node_id, NodeState.SUCCEEDED),
            )
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(
                sorted(
                    node_id
                    for node_id in self.state.nodes
                    if self.state.node_states.get(node_id) == NodeState.SUCCEEDED
                )
            ),
            failed_nodes=tuple(
                sorted(
                    node_id
                    for node_id in self.state.nodes
                    if self.state.node_states.get(node_id) == NodeState.FAILED
                )
            ),
            skipped_nodes=tuple(
                sorted(
                    node_id
                    for node_id in self.state.nodes
                    if self.state.node_states.get(node_id) == NodeState.SKIPPED
                )
            ),
            cancelled_nodes=tuple(
                sorted(
                    node_id
                    for node_id in self.state.nodes
                    if self.state.node_states.get(node_id) == NodeState.CANCELLED
                )
            ),
            wall_clock_seconds=0.0,
            critical_path=tuple(path),
            results=results,
        )


proto = DAGEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngine = synthesize_fake(DAGEngineStateMachine)


def make_dag_engine_fakes(
    state: Optional[DAGEngineState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for the component services sharing model state."""
    instance = FakeDAGEngine(state=state or proto.make_initial_state())
    return (instance, instance, instance)


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
        self.dag, self.scheduler, self.runner = make_dag_engine_fakes()
        self.sm = DAGEngineStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.scheduler,
                DAGRunner: self.runner,
            }
        )

    def test_graph_transitions_coverage(self) -> None:
        """Exercises graph registration, structural queries, and graph validation."""
        self.sm.seed_initial()
        self.dag.add_node("alpha", noop_action, None, 0, 0)
        self.dag.add_node("beta", constant_action, ["alpha"], 2, 1)
        self.dag.add_node("gamma", noop_action, ["beta"], 1, 0)
        assert self.dag.has_node("alpha") is True
        assert self.dag.has_node("missing") is False
        assert self.dag.get_node("beta").node_id == "beta"
        assert self.dag.get_dependencies("beta") == {"alpha"}
        assert self.dag.get_dependents("alpha") == {"beta"}
        assert self.dag.all_nodes() == {"alpha", "beta", "gamma"}
        self.dag.add_edge("alpha", "gamma")
        self.dag.validate()
        order = self.dag.topological_sort()
        assert order[0] == "alpha"
        assert order[-1] == "gamma"
        assert self.dag.find_roots() == {"alpha"}
        assert self.dag.find_leaves() == {"gamma"}
        path, weight = self.dag.compute_critical_path(
            {"alpha": 1.0, "beta": 2.0, "gamma": 3.0}
        )
        assert weight == 6.0
        assert path == ["alpha", "beta", "gamma"]
        self.dag.remove_node("gamma")
        assert self.dag.all_nodes() == {"alpha", "beta"}

    def test_scheduler_and_runner_transitions_coverage(self) -> None:
        """Exercises wave scheduling, state transitions, and consolidated execution."""
        self.sm.seed_initial()
        self.dag.add_node("alpha", noop_action, None, 0, 0)
        self.dag.add_node("beta", constant_action, ["alpha"], 2, 1)
        self.dag.add_node("gamma", noop_action, ["beta"], 1, 0)
        assert self.scheduler.next_wave() == ["alpha"]
        self.scheduler.mark_running("alpha")
        assert self.scheduler.get_state("alpha") == NodeState.RUNNING
        self.scheduler.mark_succeeded("alpha")
        assert self.scheduler.get_state("alpha") == NodeState.SUCCEEDED
        assert self.scheduler.next_wave() == ["beta"]
        assert self.scheduler.get_all_states()["alpha"] == NodeState.SUCCEEDED
        assert self.scheduler.is_finished() is False
        self.scheduler.mark_failed("beta", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.scheduler.get_state("gamma") == NodeState.SKIPPED
        self.scheduler.mark_failed("gamma", FailurePolicy.CONTINUE_ON_ERROR)
        self.scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 3
        assert report.failed_nodes == ("alpha", "beta", "gamma")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:39:55Z
# LAST_CHANGED: 2026-11-12T16:39:55Z
# CHANGE: Implement interface Pretense state machine for the DAG engine: DAGEngineState model tracking nodes/edges/execution states, 22 one-to-one transitions covering DAG, WaveScheduler, and DAGRunner operations with gated preconditions and error documentation, synthesized multi-service fakes, fixed fake transition-coverage scenarios, and compiled fake property fuzzing.
# --- END AUTOFAB METADATA ---
