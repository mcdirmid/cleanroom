# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, Mapping, Optional

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, LifecycleTestCase, enter_phase, get_singleton, system

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib import dag_engine_lite_impl as dag_engine_lite_impl
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
    DAGRunnerStateMachine,
    DAGStateMachine,
    WaveSchedulerStateMachine,
    noop_action,
    topological_order,
)


def failing_action() -> None:
    """Zero-argument action whose execution raises an unhandled runtime error."""
    int("not-a-number")

# ==============================================================================
# 1. DAG Implementation Pseudo State Machine
# ==============================================================================


class DAGImplPseudoStateMachine(DAGStateMachine):
    """Implementation pseudo state machine driving the concrete DAG singleton."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Registers the node through the SUT and verifies the postconditions."""
        target: DAG = sut(DAG)
        target.add_node(node_id, action, dependencies, priority, retries)
        assert target.has_node(node_id)
        assert target.get_dependencies(node_id) == set(dependencies or ())
        assert target.get_node(node_id).priority == priority
        assert target.get_node(node_id).retries == retries
        return None

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds the dependency edge through the SUT and verifies both directions."""
        target: DAG = sut(DAG)
        target.add_edge(upstream_id, downstream_id)
        assert upstream_id in target.get_dependencies(downstream_id)
        assert downstream_id in target.get_dependents(upstream_id)
        return None

    def inner_remove_node(self, node_id: str) -> None:
        """Removes the node, verifies incident edge purge, and purges scheduler tracking."""
        target: DAG = sut(DAG)
        scheduler: WaveScheduler = sut(WaveScheduler)
        scheduler.get_all_states()
        target.remove_node(node_id)
        assert not target.has_node(node_id)
        assert node_id not in scheduler.get_all_states()
        return None

    def inner_has_node(self, node_id: str) -> bool:
        """Delegates node existence inspection to the SUT."""
        target: DAG = sut(DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Delegates node definition retrieval to the SUT."""
        target: DAG = sut(DAG)
        definition = target.get_node(node_id)
        assert definition.node_id == node_id
        return definition

    def inner_get_dependencies(self, node_id: str) -> set[str]:
        """Delegates upstream dependency inspection to the SUT."""
        target: DAG = sut(DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> set[str]:
        """Delegates downstream dependent inspection to the SUT."""
        target: DAG = sut(DAG)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> set[str]:
        """Delegates full node enumeration to the SUT."""
        target: DAG = sut(DAG)
        return target.all_nodes()

    def inner_validate(self) -> None:
        """Delegates consistency validation to the SUT."""
        target: DAG = sut(DAG)
        target.validate()
        return None

    def inner_topological_sort(self) -> list[str]:
        """Delegates ordering to the SUT and checks deterministic tie-breaking."""
        target: DAG = sut(DAG)
        order = target.topological_sort()
        expected = topological_order(
            self.state.nodes,
            self.state.priorities,
            self.state.upstream,
            self.state.downstream,
        )
        assert order == expected
        return order

    def inner_find_roots(self) -> set[str]:
        """Delegates root discovery to the SUT."""
        target: DAG = sut(DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> set[str]:
        """Delegates leaf discovery to the SUT."""
        target: DAG = sut(DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        """Delegates critical path dynamic programming to the SUT."""
        target: DAG = sut(DAG)
        path, weight = target.compute_critical_path(estimated_durations)
        return (list(path), weight)


# ==============================================================================
# 2. WaveScheduler Implementation Pseudo State Machine
# ==============================================================================


class WaveSchedulerImplPseudoStateMachine(WaveSchedulerStateMachine):
    """Implementation pseudo state machine driving the concrete WaveScheduler singleton."""

    def inner_next_wave(self) -> list[str]:
        """Delegates ready wave resolution to the SUT."""
        target: WaveScheduler = sut(WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        """Transitions the node to RUNNING through the SUT."""
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_running(node_id)
        assert target.get_state(node_id) == NodeState.RUNNING
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Transitions the node to SUCCEEDED through the SUT."""
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_succeeded(node_id)
        assert target.get_state(node_id) == NodeState.SUCCEEDED
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Transitions the node to FAILED through the SUT under the failure policy."""
        target: WaveScheduler = sut(WaveScheduler)
        target.mark_failed(node_id, failure_policy)
        assert target.get_state(node_id) == NodeState.FAILED
        return None

    def inner_is_finished(self) -> bool:
        """Delegates completion inspection to the SUT."""
        target: WaveScheduler = sut(WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        """Delegates node state inspection to the SUT."""
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        """Delegates full state enumeration to the SUT."""
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_all_states()


# ==============================================================================
# 3. DAGRunner Implementation Pseudo State Machine
# ==============================================================================


class DAGRunnerImplPseudoStateMachine(DAGRunnerStateMachine):
    """Implementation pseudo state machine driving the concrete DAGRunner singleton."""

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Executes the graph through the SUT and verifies report consistency."""
        target: DAGRunner = sut(DAGRunner)
        dag: DAG = sut(DAG)
        report = target.run(failure_policy)
        nodes = dag.all_nodes()
        assert report.total_nodes == len(nodes)
        assert set(report.results.keys()) <= nodes
        categories = (
            set(report.succeeded_nodes)
            | set(report.failed_nodes)
            | set(report.skipped_nodes)
            | set(report.cancelled_nodes)
        )
        assert categories <= nodes
        assert categories <= set(report.results.keys())
        if categories == nodes:
            assert (
                len(report.succeeded_nodes)
                + len(report.failed_nodes)
                + len(report.skipped_nodes)
                + len(report.cancelled_nodes)
                == len(nodes)
            )
        for node_id in report.succeeded_nodes:
            assert report.results[node_id].state == NodeState.SUCCEEDED
        for node_id in report.failed_nodes:
            assert report.results[node_id].state == NodeState.FAILED
        for node_id in report.skipped_nodes:
            assert report.results[node_id].state == NodeState.SKIPPED
        for node_id in report.cancelled_nodes:
            assert report.results[node_id].state == NodeState.CANCELLED
        assert report.wall_clock_seconds >= 0.0
        assert set(report.critical_path) <= nodes
        for index in range(1, len(report.critical_path)):
            assert report.critical_path[index - 1] in dag.get_dependencies(report.critical_path[index])
        return report


# ==============================================================================
# 4. SUT Factory and Hypothesis Fuzzing on the Real Implementation
# ==============================================================================


def make_sut() -> dict[type[Any], Any]:
    """Builds an isolated lifecycle scope registering all three concrete services."""
    registry = LifecycleRegistry()
    registry.register_singleton(DAGImpl, keys=[DAG])
    registry.register_singleton(WaveSchedulerImpl, keys=[WaveScheduler])
    registry.register_singleton(DAGRunnerImpl, keys=[DAGRunner])
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return {
        DAG: get_singleton(DAG),
        WaveScheduler: get_singleton(WaveScheduler),
        DAGRunner: get_singleton(DAGRunner),
    }


dag_impl_proto = DAGImplPseudoStateMachine()
scheduler_impl_proto = WaveSchedulerImplPseudoStateMachine()
runner_impl_proto = DAGRunnerImplPseudoStateMachine()


DAGFuzzTest = compile_hypothesis_test_case(
    proto=dag_impl_proto,
    sut_factory=make_sut,
    initial_state_factory=dag_impl_proto.make_initial_state,
    name="DAGFuzzTest",
)

WaveSchedulerFuzzTest = compile_hypothesis_test_case(
    proto=scheduler_impl_proto,
    sut_factory=make_sut,
    initial_state_factory=scheduler_impl_proto.make_initial_state,
    name="WaveSchedulerFuzzTest",
)

DAGRunnerFuzzTest = compile_hypothesis_test_case(
    proto=runner_impl_proto,
    sut_factory=make_sut,
    initial_state_factory=runner_impl_proto.make_initial_state,
    name="DAGRunnerFuzzTest",
)


# ==============================================================================
# 5. Fixed Real-Implementation Scenario Tests
# ==============================================================================


class TestDAGImplReal(LifecycleTestCase):
    """Fixed scenarios covering DAG contract violations and postconditions."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        self.dag_sut = get_singleton(DAG)
        self.scheduler_sut = get_singleton(WaveScheduler)
        self.runner_sut = get_singleton(DAGRunner)
        self.dag_proto = DAGImplPseudoStateMachine(
            singletons={
                DAG: self.dag_sut,
                WaveScheduler: self.scheduler_sut,
                DAGRunner: self.runner_sut,
            }
        )
        self.dag = self.dag_proto.as_checked(DAG, self.dag_sut)

    def test_duplicate_node_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(DuplicateNodeError).add_node("a", noop_action, None, 0, 0)

    def test_add_edge_missing_endpoint_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(NodeNotFoundError).add_edge("a", "missing")

    def test_add_edge_missing_upstream_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(NodeNotFoundError).add_edge("missing", "a")

    def test_remove_missing_node_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(NodeNotFoundError).remove_node("missing")

    def test_remove_connected_node_purges_edges(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, None, 0, 0)
        self.dag.add_node("c", noop_action, None, 0, 0)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("c", "b")
        self.dag.remove_node("a")
        self.dag.get_dependencies("b")
        self.dag.get_dependents("c")
        self.dag.all_nodes()

    def test_remove_prerequisite_node_purges_reverse_edges(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.dag.remove_node("b")
        self.dag.get_dependents("a")
        self.dag.get_dependencies("c")
        self.dag.all_nodes()

    def test_get_missing_node_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(NodeNotFoundError).get_node("missing")

    def test_get_missing_dependencies_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(NodeNotFoundError).get_dependencies("missing")

    def test_get_missing_dependents_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.violating(NodeNotFoundError).get_dependents("missing")

    def test_validate_dangling_dependency_rejected(self) -> None:
        self.dag.add_node("a", noop_action, ("b",), 0, 0)
        self.dag.violating(NodeNotFoundError).validate()

    def test_validate_cycle_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, None, 0, 0)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        self.dag.violating(CycleError).validate()

    def test_topological_sort_cycle_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, None, 0, 0)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        self.dag.violating(CycleError).topological_sort()

    def test_topological_sort_priority_ties(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("a",), 0, 0)
        self.dag.add_node("d", noop_action, None, 0, 0)
        self.dag.add_edge("d", "c")
        self.dag.validate()
        self.dag.topological_sort()
        self.dag.find_roots()
        self.dag.find_leaves()

    def test_critical_path_weighted(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.dag.add_node("d", noop_action, None, 0, 0)
        self.dag.compute_critical_path({"a": 2.0})


class TestWaveSchedulerImplReal(LifecycleTestCase):
    """Fixed scenarios covering scheduler waves, promotions, and failure policies."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        self.dag_sut = get_singleton(DAG)
        self.scheduler_sut = get_singleton(WaveScheduler)
        self.runner_sut = get_singleton(DAGRunner)
        singletons: dict[type[Any], Any] = {
            DAG: self.dag_sut,
            WaveScheduler: self.scheduler_sut,
            DAGRunner: self.runner_sut,
        }
        self.dag_proto = DAGImplPseudoStateMachine(singletons=singletons)
        self.dag = self.dag_proto.as_checked(DAG, self.dag_sut)
        self.scheduler_proto = WaveSchedulerImplPseudoStateMachine(singletons=singletons)
        self.scheduler_proto.seed_wave_graph()
        self.scheduler = self.scheduler_proto.as_checked(WaveScheduler, self.scheduler_sut)
        self.diamond_proto = WaveSchedulerImplPseudoStateMachine(singletons=singletons)
        self.diamond_proto.seed_diamond_graph()
        self.diamond_scheduler = self.diamond_proto.as_checked(WaveScheduler, self.scheduler_sut)
        self.chain_proto = WaveSchedulerImplPseudoStateMachine(singletons=singletons)
        self.chain_proto.seed_chain_graph()
        self.chain_scheduler = self.chain_proto.as_checked(WaveScheduler, self.scheduler_sut)
        self.blocked_proto = WaveSchedulerImplPseudoStateMachine(singletons=singletons)
        self.blocked_proto.seed_blocked_pending_graph()
        self.blocked_scheduler = self.blocked_proto.as_checked(WaveScheduler, self.scheduler_sut)

    def build_wave_graph(self) -> None:
        self.dag.add_node("a", noop_action, None, 1, 0)
        self.dag.add_node("b", noop_action, None, 5, 0)
        self.dag.add_node("c", noop_action, ("a",), 0, 0)

    def build_diamond_graph(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 1, 0)
        self.dag.add_node("c", noop_action, ("a",), 2, 0)
        self.dag.add_node("d", noop_action, ("b",), 3, 0)
        self.dag.add_edge("c", "d")

    def build_chain_graph(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 1, 0)

    def test_next_wave_ready_nodes(self) -> None:
        self.build_wave_graph()
        self.scheduler.next_wave()

    def test_mark_running_state_transition(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_running("a")
        self.scheduler.get_state("a")

    def test_mark_succeeded_promotes_dependents(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.scheduler.get_state("c")

    def test_mark_succeeded_skips_non_pending_dependent(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.scheduler.mark_succeeded("a")
        self.scheduler.get_state("c")

    def test_missing_state_lookup_rejected(self) -> None:
        self.build_wave_graph()
        self.scheduler.get_state("a")
        self.scheduler.violating(NodeNotFoundError).get_state("missing")

    def test_fail_fast_cancels_non_terminal(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.scheduler.get_state("b")
        self.scheduler.get_state("c")

    def test_skip_downstream_skips_dependents(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.scheduler.get_state("c")
        self.scheduler.get_state("b")

    def test_continue_on_error_keeps_independent(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.scheduler.get_state("c")
        self.scheduler.get_state("b")

    def test_is_finished_non_terminal_remaining(self) -> None:
        self.build_wave_graph()
        self.scheduler.is_finished()

    def test_is_finished_with_running_node(self) -> None:
        self.build_chain_graph()
        self.chain_scheduler.mark_running("a")
        self.chain_scheduler.is_finished()

    def test_is_finished_mixed_states(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.scheduler.is_finished()

    def test_is_finished_blocked_by_failure(self) -> None:
        self.build_wave_graph()
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.scheduler.mark_running("b")
        self.scheduler.mark_succeeded("b")
        self.scheduler.is_finished()

    def test_skip_downstream_diamond_dedup(self) -> None:
        self.build_diamond_graph()
        self.diamond_scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.diamond_scheduler.get_state("d")
        self.diamond_scheduler.is_finished()

    def test_continue_on_error_skips_blocked_dependent(self) -> None:
        self.build_diamond_graph()
        self.diamond_scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.diamond_scheduler.get_state("b")
        self.diamond_scheduler.get_state("d")
        self.diamond_scheduler.is_finished()

    def test_is_finished_shared_prerequisite_ready_dependent(self) -> None:
        self.build_diamond_graph()
        self.diamond_scheduler.mark_running("a")
        self.diamond_scheduler.mark_succeeded("a")
        self.diamond_scheduler.mark_running("b")
        self.diamond_scheduler.mark_succeeded("b")
        self.diamond_scheduler.mark_running("c")
        self.diamond_scheduler.mark_succeeded("c")
        self.diamond_scheduler.is_finished()

    def test_get_all_states(self) -> None:
        self.build_wave_graph()
        self.scheduler.get_all_states()


class TestDAGRunnerImplReal(LifecycleTestCase):
    """Fixed scenarios covering sequential execution, retries, and failure policies."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        self.dag_sut = get_singleton(DAG)
        self.scheduler_sut = get_singleton(WaveScheduler)
        self.runner_sut = get_singleton(DAGRunner)
        singletons: dict[type[Any], Any] = {
            DAG: self.dag_sut,
            WaveScheduler: self.scheduler_sut,
            DAGRunner: self.runner_sut,
        }
        self.dag_proto = DAGImplPseudoStateMachine(singletons=singletons)
        self.dag = self.dag_proto.as_checked(DAG, self.dag_sut)
        self.success_proto = DAGRunnerImplPseudoStateMachine(singletons=singletons)
        self.success_proto.seed_run_graph()
        self.success_runner = self.success_proto.as_checked(DAGRunner, self.runner_sut)
        self.failure_proto = DAGRunnerImplPseudoStateMachine(singletons=singletons)
        self.failure_proto.seed_failure_run()
        self.failure_runner = self.failure_proto.as_checked(DAGRunner, self.runner_sut)
        self.starvation_proto = DAGRunnerImplPseudoStateMachine(singletons=singletons)
        self.starvation_proto.seed_starvation_run()
        self.starvation_runner = self.starvation_proto.as_checked(DAGRunner, self.runner_sut)
        self.chain_scheduler_proto = WaveSchedulerImplPseudoStateMachine(singletons=singletons)
        self.chain_scheduler_proto.seed_chain_graph()
        self.chain_scheduler = self.chain_scheduler_proto.as_checked(WaveScheduler, self.scheduler_sut)
        self.single_failure_proto = DAGRunnerImplPseudoStateMachine(singletons=singletons)
        self.single_failure_proto.seed_single_failure_run()
        self.single_failure_runner = self.single_failure_proto.as_checked(DAGRunner, self.runner_sut)
        self.blocked_scheduler_proto = WaveSchedulerImplPseudoStateMachine(singletons=singletons)
        self.blocked_scheduler_proto.seed_blocked_pending_graph()
        self.blocked_scheduler = self.blocked_scheduler_proto.as_checked(WaveScheduler, self.scheduler_sut)

    def test_successful_sequential_waves(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.success_runner.run(FailurePolicy.FAIL_FAST)

    def test_fail_fast_policy(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", failing_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.failure_runner.run(FailurePolicy.FAIL_FAST)

    def test_skip_downstream_policy(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", failing_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.failure_runner.run(FailurePolicy.SKIP_DOWNSTREAM)

    def test_continue_on_error_policy(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", failing_action, ("a",), 0, 0)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.failure_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_retry_attempts(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", failing_action, ("a",), 0, 1)
        self.dag.add_node("c", noop_action, ("b",), 0, 0)
        self.failure_runner.run(FailurePolicy.CONTINUE_ON_ERROR)

    def test_run_dangling_dependency_rejected(self) -> None:
        self.dag.add_node("a", noop_action, ("b",), 0, 0)
        self.success_runner.violating(NodeNotFoundError).run(FailurePolicy.FAIL_FAST)

    def test_run_cycle_rejected(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, None, 0, 0)
        self.dag.add_edge("a", "b")
        self.dag.add_edge("b", "a")
        self.success_runner.violating(CycleError).run(FailurePolicy.FAIL_FAST)

    def test_wave_starvation_break(self) -> None:
        self.dag.add_node("a", noop_action, None, 0, 0)
        self.dag.add_node("b", noop_action, ("a",), 1, 0)
        self.chain_scheduler.mark_running("a")
        self.starvation_runner.run(FailurePolicy.FAIL_FAST)

    def test_is_finished_after_post_failure_registration(self) -> None:
        self.dag.add_node("a", failing_action, None, 0, 0)
        self.single_failure_runner.run(FailurePolicy.FAIL_FAST)
        self.dag.add_node("b", noop_action, ("a",), 1, 0)
        self.blocked_scheduler.is_finished()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T01:34:07Z
# LAST_CHANGED: 2026-11-15T01:33:26Z
# CHANGE: Resolve the remaining blocked-completion coverage facets: add a diamond scenario that marks both shared prerequisites SUCCEEDED to promote the dependent to READY and inspects is_finished (shared-prerequisite revisit, finished=false), and a post-failure dependency registration scenario that runs a single failing root, registers a new dependent on the FAILED node, and verifies is_finished reports finished=true with the dependent left PENDING; back it with the new blocked-pending scheduler seed and single-failure runner seed.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T01:34:07Z
# PRETENSE_QA_AUDIT: 2026-11-15T01:33:41Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Mapping, Optional
import unittest

from pretense import StateMachine, require, require_arg, synthesize_fake, transition
from pretense.compiler import compile_hypothesis_test_case

from dag_engine_lite_deepseek_flash_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)

# ==============================================================================
# Deterministic helpers (pure model computations shared with impl pretense)
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
    """Zero-argument callable used as the seeded node action domain."""
    return None


def topological_order(
    node_ids: Collection[str],
    priorities: Mapping[str, int],
    upstream: Mapping[str, set[str]],
    downstream: Mapping[str, set[str]],
) -> list[str]:
    """Kahn's algorithm ordering nodes by priority descending then identifier ascending."""
    node_id_set = set(node_ids)
    indegree = {
        node_id: len([dependency for dependency in upstream.get(node_id, set()) if dependency in node_id_set])
        for node_id in node_id_set
    }
    ready = sorted((-int(priorities.get(node_id, 0)), node_id) for node_id in node_id_set if indegree[node_id] == 0)
    order: list[str] = []
    for _ in range(len(node_id_set) + 1):
        if not ready:
            break
        _priority, node_id = ready.pop(0)
        order.append(node_id)
        for dependent in sorted(downstream.get(node_id, set())):
            indegree[dependent] = indegree[dependent] - 1
            if indegree[dependent] == 0:
                ready.append((-int(priorities.get(dependent, 0)), dependent))
                ready.sort()
    return order


def transitive_dependents(node_id: str, downstream: Mapping[str, set[str]]) -> set[str]:
    """Collects every transitive downstream dependent of a node."""
    found: set[str] = set()
    frontier = [node_id]
    for _ in range(len(downstream) + 1):
        next_frontier: list[str] = []
        for current in frontier:
            for dependent in downstream.get(current, set()):
                if dependent not in found and dependent != node_id:
                    found.add(dependent)
                    next_frontier.append(dependent)
        frontier = next_frontier
    return found


def earliest_finish(
    node_ids: Collection[str],
    priorities: Mapping[str, int],
    upstream: Mapping[str, set[str]],
    downstream: Mapping[str, set[str]],
    durations: Mapping[str, float],
) -> dict[str, float]:
    """Dynamic-programming earliest completion time per node over a topological order."""
    order = topological_order(node_ids, priorities, upstream, downstream)
    earliest: dict[str, float] = {}
    for node_id in order:
        base = 0.0
        for dependency in upstream.get(node_id, set()):
            if dependency in earliest and earliest[dependency] > base:
                base = earliest[dependency]
        earliest[node_id] = base + float(durations.get(node_id, 1.0))
    return earliest


# ==============================================================================
# 1. DAG State Machine (interface transitions and seeded sample model)
# ==============================================================================


@dataclass
class DAGState:
    """Canonical model state of the directed acyclic graph adjacency structure."""

    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    priorities: dict[str, int] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    acyclic: bool = True


class DAGStateMachine(StateMachine[DAGState]):
    """Unified Pretense state machine for the DAG interface."""

    def __init__(
        self,
        state: Optional[DAGState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGState:
        """Constructs blank initial model state."""
        return DAGState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds an empty but consistent adjacency model."""
        self.state.acyclic = True

    @domain()
    def fresh_node_id(self, node_id: str) -> bool:
        """Caller contract recognizer rejecting already registered node identifiers."""
        return node_id not in self.state.nodes

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Registers a node definition, deferring dependency existence validation."""
        require_arg(node_id, self.fresh_node_id)
        require_arg(action, callable)
        require_arg(
            dependencies,
            self._dom_add_node_dependencies,
        )
        require_arg(priority, int)
        require_arg(retries, int)
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        frozen_dependencies = frozenset(dependencies or ())
        definition: NodeDefinition[Any] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_dependencies,
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.priorities[node_id] = priority
        self.state.upstream[node_id] = set(frozen_dependencies)
        self.state.downstream.setdefault(node_id, set())
        for dependency in frozen_dependencies:
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        self.state.acyclic = len(
            topological_order(self.state.nodes, self.state.priorities, self.state.upstream, self.state.downstream)
        ) == len(self.state.nodes)
        assert self.state.upstream[node_id] == set(frozen_dependencies)
        assert node_id in self.state.nodes
        return ret

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Fake computation for add_node."""
        return None

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge between two registered nodes."""
        require(bool(self.state.nodes))
        require_arg(upstream_id, self.state.nodes)
        require_arg(downstream_id, self.state.nodes)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        self.state.acyclic = len(
            topological_order(self.state.nodes, self.state.priorities, self.state.upstream, self.state.downstream)
        ) == len(self.state.nodes)
        assert upstream_id in self.state.upstream[downstream_id]
        assert downstream_id in self.state.downstream[upstream_id]
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Fake computation for add_edge."""
        return None

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        """Removes a node together with all incident dependency edges."""
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_remove_node(node_id)
        for dependency in list(self.state.upstream[node_id]):
            self.state.downstream.get(dependency, set()).discard(node_id)
        for dependent in list(self.state.downstream[node_id]):
            self.state.upstream.get(dependent, set()).discard(node_id)
        del self.state.nodes[node_id]
        del self.state.priorities[node_id]
        del self.state.upstream[node_id]
        del self.state.downstream[node_id]
        self.state.acyclic = len(
            topological_order(self.state.nodes, self.state.priorities, self.state.upstream, self.state.downstream)
        ) == len(self.state.nodes)
        assert node_id not in self.state.nodes
        assert node_id not in self.state.upstream
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        """Fake computation for remove_node."""
        return None

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        """Reports whether a node identifier is registered."""
        require_arg(node_id, str)
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        """Fake computation for has_node."""
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Returns the immutable definition registered for a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        assert ret.priority == self.state.nodes[node_id].priority
        assert ret.retries == self.state.nodes[node_id].retries
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Fake computation for get_node."""
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> set[str]:
        """Returns the direct upstream dependencies of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_dependencies(node_id)
        assert ret == set(self.state.upstream[node_id])
        return ret

    def inner_get_dependencies(self, node_id: str) -> set[str]:
        """Fake computation for get_dependencies."""
        return set(self.state.upstream[node_id])

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> set[str]:
        """Returns the direct downstream dependents of a node."""
        require(bool(self.state.nodes))
        require_arg(node_id, self.state.nodes)
        ret = self.inner_get_dependents(node_id)
        assert ret == set(self.state.downstream[node_id])
        return ret

    def inner_get_dependents(self, node_id: str) -> set[str]:
        """Fake computation for get_dependents."""
        return set(self.state.downstream[node_id])

    @transition(DAG.all_nodes)
    def all_nodes(self) -> set[str]:
        """Returns every registered node identifier."""
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes)
        return ret

    def inner_all_nodes(self) -> set[str]:
        """Fake computation for all_nodes."""
        return set(self.state.nodes)

    @transition(DAG.validate)
    def validate(self) -> None:
        """Validates dependency completeness and acyclicity."""
        require(
            all(
                dependency in self.state.nodes
                for node_id in self.state.nodes
                for dependency in self.state.upstream[node_id]
            ),
        )
        require(self.state.acyclic)
        ret = self.inner_validate()
        assert self.state.acyclic
        return ret

    def inner_validate(self) -> None:
        """Fake computation for validate."""
        return None

    @transition(DAG.topological_sort)
    def topological_sort(self) -> list[str]:
        """Computes a deterministic topological ordering of all registered nodes."""
        require(
            all(
                dependency in self.state.nodes
                for node_id in self.state.nodes
                for dependency in self.state.upstream[node_id]
            )
        )
        require(self.state.acyclic)
        ret = self.inner_topological_sort()
        assert len(ret) == len(self.state.nodes)
        assert set(ret) == set(self.state.nodes)
        for index in range(len(ret)):
            assert all(dependency in ret[:index] for dependency in self.state.upstream[ret[index]])
        return ret

    def inner_topological_sort(self) -> list[str]:
        """Fake computation for topological_sort."""
        return topological_order(
            self.state.nodes,
            self.state.priorities,
            self.state.upstream,
            self.state.downstream,
        )

    @transition(DAG.find_roots)
    def find_roots(self) -> set[str]:
        """Returns every node with no upstream dependencies."""
        ret = self.inner_find_roots()
        assert ret == {node_id for node_id, dependencies in self.state.upstream.items() if not dependencies}
        return ret

    def inner_find_roots(self) -> set[str]:
        """Fake computation for find_roots."""
        return {node_id for node_id, dependencies in self.state.upstream.items() if not dependencies}

    @transition(DAG.find_leaves)
    def find_leaves(self) -> set[str]:
        """Returns every node with no downstream dependents."""
        ret = self.inner_find_leaves()
        assert ret == {node_id for node_id, dependents in self.state.downstream.items() if not dependents}
        return ret

    def inner_find_leaves(self) -> set[str]:
        """Fake computation for find_leaves."""
        return {node_id for node_id, dependents in self.state.downstream.items() if not dependents}

    @transition(DAG.compute_critical_path)
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> tuple[list[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        require(bool(self.state.nodes))
        require(
            all(
                dependency in self.state.nodes
                for node_id in self.state.nodes
                for dependency in self.state.upstream[node_id]
            )
        )
        require_arg(
            estimated_durations,
            self._dom_compute_critical_path_estimated_durations,
        )
        ret_path, ret_weight = self.inner_compute_critical_path(estimated_durations)
        durations = dict(estimated_durations or {})
        earliest = earliest_finish(
            self.state.nodes,
            self.state.priorities,
            self.state.upstream,
            self.state.downstream,
            durations,
        )
        assert len(ret_path) > 0
        assert ret_weight == max(earliest.values())
        assert ret_weight == sum(float(durations.get(node_id, 1.0)) for node_id in ret_path)
        for index in range(1, len(ret_path)):
            assert ret_path[index - 1] in self.state.upstream[ret_path[index]]
        assert not self.state.upstream[ret_path[0]]
        assert earliest[ret_path[-1]] == ret_weight
        return (ret_path, ret_weight)

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        """Fake computation for compute_critical_path."""
        durations = dict(estimated_durations or {})
        earliest = earliest_finish(
            self.state.nodes,
            self.state.priorities,
            self.state.upstream,
            self.state.downstream,
            durations,
        )
        weight = max(earliest.values())
        current = sorted((-earliest[node_id], node_id) for node_id in earliest)[0][1]
        path = [current]
        for _ in range(len(earliest)):
            candidates = [dependency for dependency in self.state.upstream.get(current, set()) if dependency in earliest]
            if not candidates:
                break
            current = sorted((-earliest[dependency], dependency) for dependency in candidates)[0][1]
            path.append(current)
        path.reverse()
        return (path, weight)

    @domain(valid=lambda self: list((None, (), ("a",), ("b",), ("a", "b"))))
    def _dom_add_node_dependencies(self, val: Any) -> bool:
        return val in (None, (), ("a",), ("b",), ("a", "b"))

    @domain(valid=lambda self: list((None, {}, {"a": 2.0})))
    def _dom_compute_critical_path_estimated_durations(self, val: Any) -> bool:
        return val in (None, {}, {"a": 2.0})


dag_proto = DAGStateMachine()
FakeDAG = synthesize_fake(DAGStateMachine)


def make_dag_fake(state: Optional[DAGState] = None) -> DAG:
    """Synthesizes a fake DAG instance sharing the model state."""
    return FakeDAG(state=state or dag_proto.make_initial_state())


FakeDAGFuzzTest = compile_hypothesis_test_case(
    proto=dag_proto,
    initial_state_factory=dag_proto.make_initial_state,
    name="FakeDAGFuzzTest",
)


class TestDAGFake(unittest.TestCase):
    """Fixed fake tests exercising every DAG transition and seeding transition."""

    def setUp(self) -> None:
        self.fake = make_dag_fake()
        self.sm = DAGStateMachine(singletons={DAG: self.fake})

    def test_graph_registration_and_queries(self) -> None:
        self.assertIsNone(noop_action())
        self.sm.seed_initial()
        self.sm.add_node("a", noop_action, None, 0, 0)
        self.sm.add_node("b", noop_action, ("a",), 2, 1)
        self.sm.add_node("c", noop_action, None, 1, 0)
        self.sm.add_edge("c", "b")
        self.sm.has_node("a")
        self.sm.get_node("b")
        self.sm.get_dependencies("b")
        self.sm.get_dependents("c")
        self.sm.all_nodes()
        self.sm.find_roots()
        self.sm.find_leaves()
        self.sm.remove_node("c")
        self.sm.remove_node("b")
        self.assertFalse(self.sm.has_node("b"))
        self.assertEqual(self.sm.all_nodes(), {"a"})

    def test_validation_and_ordering(self) -> None:
        self.sm.seed_initial()
        self.sm.add_node("a", noop_action, None, 0, 0)
        self.sm.add_node("b", noop_action, ("a",), 2, 0)
        self.sm.add_node("c", noop_action, None, 1, 0)
        self.sm.add_edge("c", "b")
        self.sm.validate()
        self.assertEqual(self.sm.topological_sort(), ["c", "a", "b"])
        self.assertEqual(self.sm.find_roots(), {"a", "c"})
        self.assertEqual(self.sm.find_leaves(), {"b"})

    def test_critical_path(self) -> None:
        self.sm.seed_initial()
        self.sm.add_node("a", noop_action, None, 0, 0)
        self.sm.add_node("b", noop_action, ("a",), 2, 0)
        self.sm.add_node("c", noop_action, None, 1, 0)
        self.sm.add_edge("c", "b")
        path, weight = self.sm.compute_critical_path(None)
        self.assertEqual(weight, 2.0)
        self.assertIn("b", path)


# ==============================================================================
# 2. WaveScheduler State Machine
# ==============================================================================


@dataclass
class WaveSchedulerState:
    """Canonical model state of the sequential wave scheduler."""

    nodes: set[str] = field(default_factory=set)
    priorities: dict[str, int] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    states: dict[str, NodeState] = field(default_factory=dict)


class WaveSchedulerStateMachine(StateMachine[WaveSchedulerState]):
    """Unified Pretense state machine for the WaveScheduler interface."""

    def __init__(
        self,
        state: Optional[WaveSchedulerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> WaveSchedulerState:
        """Constructs blank initial model state."""
        return WaveSchedulerState()

    @transition.seeding
    def seed_wave_graph(self) -> None:
        """Seeds a small diamond-shaped scheduling model."""
        self.state.nodes = {"a", "b", "c"}
        self.state.priorities = {"a": 1, "b": 5, "c": 0}
        self.state.upstream = {"a": set(), "b": set(), "c": {"a"}}
        self.state.downstream = {"a": {"c"}, "b": set(), "c": set()}
        self.state.states = {
            "a": NodeState.READY,
            "b": NodeState.READY,
            "c": NodeState.PENDING,
        }

    @transition.seeding
    def seed_diamond_graph(self) -> None:
        """Seeds a diamond scheduling model with a shared downstream dependent."""
        self.state.nodes = {"a", "b", "c", "d"}
        self.state.priorities = {"a": 0, "b": 1, "c": 2, "d": 3}
        self.state.upstream = {"a": set(), "b": {"a"}, "c": {"a"}, "d": {"b", "c"}}
        self.state.downstream = {"a": {"b", "c"}, "b": {"d"}, "c": {"d"}, "d": set()}
        self.state.states = {
            "a": NodeState.READY,
            "b": NodeState.PENDING,
            "c": NodeState.PENDING,
            "d": NodeState.PENDING,
        }

    @transition.seeding
    def seed_chain_graph(self) -> None:
        """Seeds a two node prerequisite chain scheduling model."""
        self.state.nodes = {"a", "b"}
        self.state.priorities = {"a": 0, "b": 1}
        self.state.upstream = {"a": set(), "b": {"a"}}
        self.state.downstream = {"a": {"b"}, "b": set()}
        self.state.states = {"a": NodeState.READY, "b": NodeState.PENDING}

    @transition.seeding
    def seed_blocked_pending_graph(self) -> None:
        """Seeds a schedule whose pending dependent is blocked by a failed prerequisite."""
        self.state.nodes = {"a", "b"}
        self.state.priorities = {"a": 0, "b": 1}
        self.state.upstream = {"a": set(), "b": {"a"}}
        self.state.downstream = {"a": {"b"}, "b": set()}
        self.state.states = {"a": NodeState.FAILED, "b": NodeState.PENDING}

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> list[str]:
        """Returns ready nodes ordered by priority descending then identifier ascending."""
        ret = self.inner_next_wave()
        ready = [
            node_id
            for node_id in self.state.states
            if self.state.states[node_id] == NodeState.READY
            and all(self.state.states.get(dependency) == NodeState.SUCCEEDED for dependency in self.state.upstream[node_id])
        ]
        expected = [
            node_id for _priority, node_id in sorted((-self.state.priorities[node_id], node_id) for node_id in ready)
        ]
        assert ret == expected
        return ret

    def inner_next_wave(self) -> list[str]:
        """Fake computation for next_wave."""
        ready = [
            node_id
            for node_id in self.state.states
            if self.state.states[node_id] == NodeState.READY
            and all(self.state.states.get(dependency) == NodeState.SUCCEEDED for dependency in self.state.upstream[node_id])
        ]
        return [node_id for _priority, node_id in sorted((-self.state.priorities[node_id], node_id) for node_id in ready)]

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        require(bool(self.state.states))
        require_arg(node_id, self.state.states)
        ret = self.inner_mark_running(node_id)
        self.state.states[node_id] = NodeState.RUNNING
        assert self.state.states[node_id] == NodeState.RUNNING
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        """Fake computation for mark_running."""
        return None

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to SUCCEEDED and promotes newly unblocked dependents."""
        require(bool(self.state.states))
        require_arg(node_id, self.state.states)
        ret = self.inner_mark_succeeded(node_id)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream[node_id]:
            if self.state.states.get(dependent) == NodeState.PENDING and all(
                self.state.states.get(dependency) == NodeState.SUCCEEDED
                for dependency in self.state.upstream[dependent]
            ):
                self.state.states[dependent] = NodeState.READY
        assert self.state.states[node_id] == NodeState.SUCCEEDED
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        """Fake computation for mark_succeeded."""
        return None

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Transitions a node to FAILED and applies the selected failure policy."""
        require(bool(self.state.states))
        require_arg(node_id, self.state.states)
        require_arg(
            failure_policy,
            self._dom_mark_failed_failure_policy,
        )
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other in self.state.states:
                if self.state.states[other] not in TERMINAL_STATES:
                    self.state.states[other] = NodeState.CANCELLED
        else:
            for blocked in transitive_dependents(node_id, self.state.downstream):
                if self.state.states.get(blocked) not in TERMINAL_STATES:
                    self.state.states[blocked] = NodeState.SKIPPED
        assert self.state.states[node_id] == NodeState.FAILED
        return ret

    def inner_mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Fake computation for mark_failed."""
        return None

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        """Reports whether every node reached a terminal state or is blocked by failure."""
        ret = self.inner_is_finished()
        expected = not any(
            self.state.states[node_id] not in TERMINAL_STATES
            and all(self.state.states.get(dependency) == NodeState.SUCCEEDED for dependency in self.state.upstream[node_id])
            for node_id in self.state.states
        )
        assert ret == expected
        return ret

    def inner_is_finished(self) -> bool:
        """Fake computation for is_finished."""
        return not any(
            self.state.states[node_id] not in TERMINAL_STATES
            and all(self.state.states.get(dependency) == NodeState.SUCCEEDED for dependency in self.state.upstream[node_id])
            for node_id in self.state.states
        )

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        """Returns the current execution state of a registered node."""
        require(bool(self.state.states))
        require_arg(node_id, self.state.states)
        ret = self.inner_get_state(node_id)
        assert ret == self.state.states[node_id]
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        """Fake computation for get_state."""
        return self.state.states[node_id]

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every scheduled node."""
        ret = self.inner_get_all_states()
        assert dict(ret) == dict(self.state.states)
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        """Fake computation for get_all_states."""
        return dict(self.state.states)

    @domain(valid=lambda self: list((FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM)))
    def _dom_mark_failed_failure_policy(self, val: Any) -> bool:
        return val in (FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM)


scheduler_proto = WaveSchedulerStateMachine()
FakeWaveScheduler = synthesize_fake(WaveSchedulerStateMachine)


def make_wave_scheduler_fake(state: Optional[WaveSchedulerState] = None) -> WaveScheduler:
    """Synthesizes a fake WaveScheduler instance sharing the model state."""
    return FakeWaveScheduler(state=state or scheduler_proto.make_initial_state())


FakeWaveSchedulerFuzzTest = compile_hypothesis_test_case(
    proto=scheduler_proto,
    initial_state_factory=scheduler_proto.make_initial_state,
    name="FakeWaveSchedulerFuzzTest",
)


class TestWaveSchedulerFake(unittest.TestCase):
    """Fixed fake tests exercising every WaveScheduler transition and seeding transition."""

    def setUp(self) -> None:
        self.fake = make_wave_scheduler_fake()
        self.sm = WaveSchedulerStateMachine(singletons={WaveScheduler: self.fake})

    def test_wave_progression(self) -> None:
        self.sm.seed_wave_graph()
        self.assertEqual(self.sm.next_wave(), ["b", "a"])
        self.sm.mark_running("a")
        self.sm.mark_succeeded("a")
        self.assertEqual(self.sm.get_state("c"), NodeState.READY)
        self.sm.mark_running("b")
        self.sm.mark_succeeded("b")
        self.sm.mark_running("c")
        self.sm.mark_succeeded("c")
        self.assertTrue(self.sm.is_finished())
        self.assertEqual(len(self.sm.get_all_states()), 3)

    def test_fail_fast_policy(self) -> None:
        self.sm.seed_wave_graph()
        self.sm.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.sm.get_state("b"), NodeState.CANCELLED)
        self.assertTrue(self.sm.is_finished())

    def test_skip_downstream_policy(self) -> None:
        self.sm.seed_wave_graph()
        self.sm.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sm.get_state("c"), NodeState.SKIPPED)
        self.assertFalse(self.sm.is_finished())
        self.sm.mark_running("b")
        self.sm.mark_succeeded("b")
        self.assertTrue(self.sm.is_finished())

    def test_continue_on_error_policy(self) -> None:
        self.sm.seed_wave_graph()
        self.sm.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sm.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.sm.get_state("b"), NodeState.READY)

    def test_diamond_skip_downstream_dedup(self) -> None:
        self.sm.seed_diamond_graph()
        self.assertEqual(len(self.sm.get_all_states()), 4)
        self.sm.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sm.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.sm.get_state("c"), NodeState.SKIPPED)
        self.assertEqual(self.sm.get_state("d"), NodeState.SKIPPED)
        self.assertTrue(self.sm.is_finished())

    def test_diamond_continue_skips_blocked_dependent(self) -> None:
        self.sm.seed_diamond_graph()
        self.sm.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sm.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.sm.get_state("d"), NodeState.SKIPPED)
        self.assertTrue(self.sm.is_finished())

    def test_chain_seed_and_running_state(self) -> None:
        self.sm.seed_chain_graph()
        self.assertEqual(self.sm.next_wave(), ["a"])
        self.sm.mark_running("a")
        self.assertFalse(self.sm.is_finished())
        self.sm.mark_succeeded("a")
        self.assertEqual(self.sm.get_state("b"), NodeState.READY)

    def test_blocked_pending_after_failure(self) -> None:
        self.sm.seed_blocked_pending_graph()
        self.assertEqual(self.sm.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.sm.get_state("b"), NodeState.PENDING)
        self.assertTrue(self.sm.is_finished())


# ==============================================================================
# 3. DAGRunner State Machine
# ==============================================================================


@dataclass
class DAGRunnerState:
    """Canonical model state of the sequential DAG execution runner."""

    nodes: set[str] = field(default_factory=set)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    planned: dict[str, NodeState] = field(default_factory=dict)
    critical_path: tuple[str, ...] = field(default_factory=tuple)
    ran: bool = False


class DAGRunnerStateMachine(StateMachine[DAGRunnerState]):
    """Unified Pretense state machine for the DAGRunner interface."""

    def __init__(
        self,
        state: Optional[DAGRunnerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGRunnerState:
        """Constructs blank initial model state."""
        return DAGRunnerState()

    @transition.seeding
    def seed_run_graph(self) -> None:
        """Seeds a fully succeeding chain execution plan."""
        self.state.nodes = {"a", "b", "c"}
        self.state.dependencies = {"a": set(), "b": {"a"}, "c": {"b"}}
        self.state.planned = {
            "a": NodeState.SUCCEEDED,
            "b": NodeState.SUCCEEDED,
            "c": NodeState.SUCCEEDED,
        }
        self.state.critical_path = ("a", "b", "c")
        self.state.ran = False

    @transition.seeding
    def seed_failure_run(self) -> None:
        """Seeds a chain execution plan whose middle node fails."""
        self.state.nodes = {"a", "b", "c"}
        self.state.dependencies = {"a": set(), "b": {"a"}, "c": {"b"}}
        self.state.planned = {
            "a": NodeState.SUCCEEDED,
            "b": NodeState.FAILED,
            "c": NodeState.PENDING,
        }
        self.state.critical_path = ("a", "b", "c")
        self.state.ran = False

    @transition.seeding
    def seed_starvation_run(self) -> None:
        """Seeds an execution plan whose in-flight node starves the wave loop."""
        self.state.nodes = {"a", "b"}
        self.state.dependencies = {"a": set(), "b": {"a"}}
        self.state.planned = {
            "a": NodeState.RUNNING,
            "b": NodeState.PENDING,
        }
        self.state.critical_path = ("a", "b")
        self.state.ran = False

    @transition.seeding
    def seed_single_failure_run(self) -> None:
        """Seeds an execution plan with a single failing root node."""
        self.state.nodes = {"a"}
        self.state.dependencies = {"a": set()}
        self.state.planned = {"a": NodeState.FAILED}
        self.state.critical_path = ("a",)
        self.state.ran = False

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Executes the abstract graph and verifies consolidated report invariants."""
        require_arg(
            failure_policy,
            self._dom_run_failure_policy,
        )
        ret = self.inner_run(failure_policy)
        categories = (
            set(ret.succeeded_nodes)
            | set(ret.failed_nodes)
            | set(ret.skipped_nodes)
            | set(ret.cancelled_nodes)
        )
        assert ret.total_nodes == len(self.state.nodes)
        assert ret.wall_clock_seconds >= 0.0
        if not self.state.nodes:
            assert categories == set()
            assert set(ret.results.keys()) == set()
            assert len(ret.critical_path) == 0
        else:
            assert categories <= self.state.nodes
            assert set(ret.results.keys()) <= self.state.nodes
            assert categories <= set(ret.results.keys())
            for node_id in ret.succeeded_nodes:
                assert ret.results[node_id].state == NodeState.SUCCEEDED
            for node_id in ret.failed_nodes:
                assert ret.results[node_id].state == NodeState.FAILED
            for node_id in ret.skipped_nodes:
                assert ret.results[node_id].state == NodeState.SKIPPED
            for node_id in ret.cancelled_nodes:
                assert ret.results[node_id].state == NodeState.CANCELLED
            if categories == self.state.nodes:
                assert (
                    len(ret.succeeded_nodes)
                    + len(ret.failed_nodes)
                    + len(ret.skipped_nodes)
                    + len(ret.cancelled_nodes)
                    == len(self.state.nodes)
                )
                assert tuple(ret.critical_path) == self.state.critical_path
            for index in range(1, len(ret.critical_path)):
                assert ret.critical_path[index - 1] in self.state.dependencies.get(ret.critical_path[index], set())
        self.state.ran = True
        assert self.state.ran
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Fake computation for run."""
        downstream = {node_id: set() for node_id in self.state.nodes}
        for node_id in self.state.nodes:
            for dependency in self.state.dependencies.get(node_id, set()):
                downstream.setdefault(dependency, set()).add(node_id)
        final_states = dict(self.state.planned)
        for node_id in sorted(self.state.planned):
            if self.state.planned[node_id] != NodeState.FAILED:
                continue
            if failure_policy == FailurePolicy.FAIL_FAST:
                for other in sorted(self.state.nodes):
                    if other != node_id and final_states.get(other) not in TERMINAL_STATES:
                        final_states[other] = NodeState.CANCELLED
            else:
                for blocked in sorted(transitive_dependents(node_id, downstream)):
                    if final_states.get(blocked) not in TERMINAL_STATES:
                        final_states[blocked] = NodeState.SKIPPED
        succeeded: list[str] = []
        failed: list[str] = []
        skipped: list[str] = []
        cancelled: list[str] = []
        results: dict[str, NodeResult[Any]] = {}
        for node_id in sorted(self.state.nodes):
            outcome = final_states.get(node_id, NodeState.PENDING)
            results[node_id] = NodeResult(node_id=node_id, state=outcome)
            if outcome == NodeState.SUCCEEDED:
                succeeded.append(node_id)
            elif outcome == NodeState.FAILED:
                failed.append(node_id)
            elif outcome == NodeState.SKIPPED:
                skipped.append(node_id)
            elif outcome == NodeState.CANCELLED:
                cancelled.append(node_id)
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=tuple(succeeded),
            failed_nodes=tuple(failed),
            skipped_nodes=tuple(skipped),
            cancelled_nodes=tuple(cancelled),
            wall_clock_seconds=0.0,
            critical_path=tuple(self.state.critical_path),
            results=results,
        )

    @domain(valid=lambda self: list((FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM)))
    def _dom_run_failure_policy(self, val: Any) -> bool:
        return val in (FailurePolicy.FAIL_FAST, FailurePolicy.CONTINUE_ON_ERROR, FailurePolicy.SKIP_DOWNSTREAM)


runner_proto = DAGRunnerStateMachine()
FakeDAGRunner = synthesize_fake(DAGRunnerStateMachine)


def make_dag_runner_fake(state: Optional[DAGRunnerState] = None) -> DAGRunner:
    """Synthesizes a fake DAGRunner instance sharing the model state."""
    return FakeDAGRunner(state=state or runner_proto.make_initial_state())


FakeDAGRunnerFuzzTest = compile_hypothesis_test_case(
    proto=runner_proto,
    initial_state_factory=runner_proto.make_initial_state,
    name="FakeDAGRunnerFuzzTest",
)


class TestDAGRunnerFake(unittest.TestCase):
    """Fixed fake tests exercising the DAGRunner transition and both seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_runner_fake()
        self.sm = DAGRunnerStateMachine(singletons={DAGRunner: self.fake})

    def test_successful_run(self) -> None:
        self.sm.seed_run_graph()
        report = self.sm.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(tuple(report.succeeded_nodes), ("a", "b", "c"))

    def test_fail_fast_run(self) -> None:
        self.sm.seed_failure_run()
        report = self.sm.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(tuple(report.failed_nodes), ("b",))
        self.assertEqual(tuple(report.cancelled_nodes), ("c",))

    def test_skip_downstream_run(self) -> None:
        self.sm.seed_failure_run()
        report = self.sm.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(tuple(report.skipped_nodes), ("c",))

    def test_continue_on_error_run(self) -> None:
        self.sm.seed_failure_run()
        report = self.sm.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(tuple(report.skipped_nodes), ("c",))

    def test_starvation_run(self) -> None:
        self.sm.seed_starvation_run()
        report = self.sm.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(tuple(report.succeeded_nodes), ())

    def test_single_failure_run(self) -> None:
        self.sm.seed_single_failure_run()
        report = self.sm.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(tuple(report.failed_nodes), ("a",))

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T01:33:19Z
# LAST_CHANGED: 2026-11-15T01:33:19Z
# CHANGE: Add seeding models needed for blocked-completion coverage: WaveScheduler.seed_blocked_pending_graph (failed prerequisite with an unexecuted PENDING dependent) and DAGRunner.seed_single_failure_run (single failing root plan), plus fixed fake scenarios asserting the blocked pending schedule reports finished and the single-node failure run reports the failed node.
# --- END AUTOFAB METADATA ---
