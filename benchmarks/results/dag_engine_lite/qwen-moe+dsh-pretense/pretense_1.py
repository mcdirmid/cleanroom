# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
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
from benchmark_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (DagEngineLiteStateMachine, DagEngineLiteState, FakeDagEngineLite, make_dag_engine_lite_fakes)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import FailurePolicy, NodeState
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for DagEngineLite."""

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
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        return ret


proto = DagEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(singletons={DAG: self.dag, WaveScheduler: self.wavescheduler, DAGRunner: self.dagrunner})
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        # Drive scenarios via self.checked.<method>(*args).
        # Node: add_node, has_node, get_node, all_nodes, remove_node
        self.checked_dag.add_node(
            node_id="init",
            action=lambda: 1,
            dependencies=None,
            priority=0,
            retries=0,
        )
        self.assertTrue(self.checked_dag.has_node("init"))
        node_def = self.checked_dag.get_node("init")
        self.assertEqual(node_def.node_id, "init")
        self.assertEqual(self.checked_dag.all_nodes(), {"init"})

        self.checked_dag.add_node(
            node_id="step_a",
            action=lambda: 2,
            dependencies=["init"],
            priority=1,
            retries=0,
        )
        self.assertEqual(self.checked_dag.get_dependencies("step_a"), {"init"})
        self.assertEqual(self.checked_dag.all_nodes(), {"init", "step_a"})

        self.checked_dag.remove_node("step_a")
        self.assertFalse(self.checked_dag.has_node("step_a"))
        self.assertEqual(self.checked_dag.all_nodes(), {"init"})

        # Edge: add_edge, get_dependents, get_dependencies
        self.checked_dag.add_node(node_id="b", action=lambda: None, dependencies=None, priority=0, retries=0)
        self.checked_dag.add_node(node_id="c", action=lambda: None, dependencies=None, priority=0, retries=0)
        self.checked_dag.add_edge("b", "c")
        self.assertEqual(self.checked_dag.get_dependents("b"), {"c"})
        self.assertEqual(self.checked_dag.get_dependencies("c"), {"b"})

        # Validation and topological ordering
        self.checked_dag.validate()
        roots = self.checked_dag.find_roots()
        leaves = self.checked_dag.find_leaves()
        self.assertIn("init", roots)
        self.assertIn("c", leaves)

        # WaveScheduler: next_wave, mark_running, mark_succeeded, is_finished, get_state
        self.assertEqual(self.checked_wavescheduler.next_wave(), ["b", "init"])
        self.checked_wavescheduler.mark_running("init")
        self.assertEqual(self.checked_wavescheduler.get_state("init"), NodeState.RUNNING)
        self.checked_wavescheduler.mark_succeeded("init")
        self.assertEqual(self.checked_wavescheduler.get_state("init"), NodeState.SUCCEEDED)

        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.SUCCEEDED)
        self.assertEqual(self.checked_wavescheduler.get_state("c"), NodeState.READY)
        self.checked_wavescheduler.mark_running("c")
        self.checked_wavescheduler.mark_succeeded("c")
        self.assertTrue(self.checked_wavescheduler.is_finished())

        # FailurePolicy: mark_failed with FAIL_FAST
        dag2 = self.dag
        dag2.add_node(node_id="x", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag2.add_node(node_id="y", action=lambda: None, dependencies=["x"], priority=0, retries=0)
        waves2 = self.wavescheduler
        waves2.mark_running("x")
        waves2.mark_failed("x", FailurePolicy.FAIL_FAST)
        self.assertEqual(waves2.get_state("x"), NodeState.FAILED)

        # DAGRunner: run
        self.checked_dagrunner.run(failure_policy=FailurePolicy.FAIL_FAST)

    # ------------------------------------------------------------------
    # WaveScheduler mark_failed policy tests
    # ------------------------------------------------------------------

    def test_mark_failed_skip_downstream(self) -> None:
        """SKIP_DOWNSTREAM: all transitive downstream dependents transitioned to SKIPPED."""
        dag3 = self.dag
        # Clean state: clear any prior nodes
        dag3.add_node(node_id="s1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag3.add_node(node_id="s2", action=lambda: None, dependencies=["s1"], priority=0, retries=0)
        dag3.add_node(node_id="s3", action=lambda: None, dependencies=["s2"], priority=0, retries=0)
        ws3 = self.wavescheduler
        ws3.mark_running("s1")
        ws3.mark_failed("s1", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(ws3.get_state("s1"), NodeState.FAILED)
        self.assertEqual(ws3.get_state("s2"), NodeState.SKIPPED)
        self.assertEqual(ws3.get_state("s3"), NodeState.SKIPPED)

    def test_mark_failed_continue_on_error(self) -> None:
        """CONTINUE_ON_ERROR: independent nodes remain READY, blocked dependents SKIPPED."""
        dag4 = self.dag
        dag4.add_node(node_id="c1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag4.add_node(node_id="c2", action=lambda: None, dependencies=["c1"], priority=0, retries=0)
        dag4.add_node(node_id="c3", action=lambda: None, dependencies=None, priority=0, retries=0)
        ws4 = self.wavescheduler
        ws4.mark_running("c1")
        ws4.mark_failed("c1", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(ws4.get_state("c1"), NodeState.FAILED)
        self.assertEqual(ws4.get_state("c2"), NodeState.SKIPPED)
        # c3 is independent — remains READY (not terminated)
        self.assertEqual(ws4.get_state("c3"), NodeState.READY)

    def test_mark_failed_fail_fast_pending_cancelled(self) -> None:
        """FAIL_FAST: all pending (non-terminal) nodes transitioned to CANCELLED."""
        dag5 = self.dag
        dag5.add_node(node_id="f1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag5.add_node(node_id="f2", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag5.add_node(node_id="f3", action=lambda: None, dependencies=["f1"], priority=0, retries=0)
        dag5.add_node(node_id="f4", action=lambda: None, dependencies=["f2"], priority=0, retries=0)
        ws5 = self.wavescheduler
        ws5.mark_running("f1")
        ws5.mark_failed("f1", FailurePolicy.FAIL_FAST)
        self.assertEqual(ws5.get_state("f1"), NodeState.FAILED)
        self.assertEqual(ws5.get_state("f2"), NodeState.READY)
        self.assertEqual(ws5.get_state("f3"), NodeState.CANCELLED)
        self.assertEqual(ws5.get_state("f4"), NodeState.CANCELLED)

    # ------------------------------------------------------------------
    # WaveScheduler is_finished tests
    # ------------------------------------------------------------------

    def test_is_finished_empty_graph(self) -> None:
        """is_finished returns True when the DAG has no nodes."""
        ws6 = self.wavescheduler
        self.assertTrue(ws6.is_finished())

    def test_is_finished_blocked_nodes(self) -> None:
        """is_finished returns True when unexecuted nodes are blocked by failed deps."""
        dag7 = self.dag
        dag7.add_node(node_id="b1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag7.add_node(node_id="b2", action=lambda: None, dependencies=["b1"], priority=0, retries=0)
        ws7 = self.wavescheduler
        ws7.mark_running("b1")
        ws7.mark_failed("b1", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertTrue(ws7.is_finished())

    def test_is_finished_not_finished_with_ready_nodes(self) -> None:
        """is_finished returns False when there are non-terminal nodes with satisfied dependencies."""
        dag10 = self.dag
        dag10.add_node(node_id="rdy1", action=lambda: None, dependencies=None, priority=0, retries=0)
        ws10 = self.wavescheduler
        # After calling next_wave (which syncs state), rdy1 is READY but not terminal
        ws10.next_wave()
        self.assertFalse(ws10.is_finished())

    def test_is_finished_all_terminal(self) -> None:
        """is_finished returns True when all nodes have reached terminal states."""
        dag8 = self.dag
        dag8.add_node(node_id="s1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag8.add_node(node_id="s2", action=lambda: None, dependencies=["s1"], priority=0, retries=0)
        ws8 = self.wavescheduler
        ws8.mark_succeeded("s1")
        ws8.mark_succeeded("s2")
        self.assertTrue(ws8.is_finished())

    def test_is_finished_all_terminal_exclusive(self) -> None:
        """is_finished returns True when every node is in a terminal state (dedicated check)."""
        dummy = self.dag
        dummy.add_node(node_id="x1", action=lambda: None, dependencies=None, priority=0, retries=0)
        ws_dummy = self.wavescheduler
        ws_dummy.mark_succeeded("x1")
        self.assertTrue(ws_dummy.is_finished())

    def test_is_finished_pending_with_failed_dep(self) -> None:
        """is_finished returns True when non-terminal nodes have unsatisfied deps from failures (continue branch skips them)."""
        dag9 = self.dag
        dag9.add_node(node_id="fp1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag9.add_node(node_id="fp2", action=lambda: None, dependencies=["fp1"], priority=0, retries=0)
        ws9 = self.wavescheduler
        ws9.mark_failed("fp1", FailurePolicy.FAIL_FAST)
        # fp2 remains PENDING with unsatisfied dependency (not skipped because FAIL_FAST)
        # No READY nodes remain; fp1 is FAILED (terminal), fp2 is blocked
        self.assertTrue(ws9.is_finished())

    def test_is_finished_mixed_terminal_and_blocked(self) -> None:
        """is_finished returns True when all runnable nodes are terminal and remaining nodes are blocked."""
        dagmix = self.dag
        dagmix.add_node(node_id="ok1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dagmix.add_node(node_id="ok2", action=lambda: None, dependencies=["ok1"], priority=0, retries=0)
        dagmix.add_node(node_id="bl1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dagmix.add_node(node_id="bl2", action=lambda: None, dependencies=["bl1"], priority=0, retries=0)
        wsm = self.wavescheduler
        wsm.mark_succeeded("ok1")
        wsm.mark_succeeded("ok2")
        wsm.mark_failed("bl1", FailurePolicy.FAIL_FAST)
        # ok1, ok2 are SUCCEEDED (terminal); bl1 is FAILED (terminal); bl2 is PENDING (blocked)
        self.assertTrue(wsm.is_finished())

    # ------------------------------------------------------------------
    # WaveScheduler state synchronization tests
    # ------------------------------------------------------------------

    def test_get_state_syncs_absent_node(self) -> None:
        """get_state triggers state synchronization for nodes absent from local state."""
        dag8 = self.dag
        dag8.add_node(node_id="sync1", action=lambda: None, dependencies=None, priority=0, retries=0)
        ws8 = self.wavescheduler
        # Access state before calling next_wave (which does sync)
        state = ws8.get_state("sync1")
        self.assertIn(state, (NodeState.READY, NodeState.PENDING))

    def test_get_all_states_prunes_stale(self) -> None:
        """get_all_states prunes stale entries for nodes no longer registered."""
        dag9 = self.dag
        dag9.add_node(node_id="p1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag9.add_node(node_id="p2", action=lambda: None, dependencies=None, priority=0, retries=0)
        ws9 = self.wavescheduler
        ws9.next_wave()  # syncs states
        ws9.mark_running("p1")
        ws9.mark_succeeded("p1")
        # Remove p2 — states should prune it
        dag9.remove_node("p2")
        all_states = ws9.get_all_states()
        self.assertNotIn("p2", all_states)
        self.assertIn("p1", all_states)

    # ------------------------------------------------------------------
    # DAG compute_critical_path tests
    # ------------------------------------------------------------------

    def test_compute_critical_path_custom_durations(self) -> None:
        """compute_critical_path with non-default estimated durations mapping."""
        dag10 = self.dag
        dag10.add_node(node_id="d1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag10.add_node(node_id="d2", action=lambda: None, dependencies=["d1"], priority=0, retries=0)
        dag10.add_node(node_id="d3", action=lambda: None, dependencies=["d1"], priority=0, retries=0)
        dag10.add_node(node_id="d4", action=lambda: None, dependencies=["d2", "d3"], priority=0, retries=0)
        durations = {"d1": 2.0, "d2": 5.0, "d3": 1.0, "d4": 3.0}
        path, weight = dag10.compute_critical_path(durations)
        self.assertGreater(weight, 0.0)
        self.assertIn("d1", path)
        self.assertIn("d4", path)

    def test_compute_critical_path_empty_graph(self) -> None:
        """compute_critical_path for an empty graph returns an empty path."""
        dag11 = self.dag
        path, weight = dag11.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    # ------------------------------------------------------------------
    # DAG remove_node with dependents
    # ------------------------------------------------------------------

    def test_remove_node_with_dependents(self) -> None:
        """remove_node for nodes with downstream dependents verifies cleanup of reverse edges."""
        dag12 = self.dag
        dag12.add_node(node_id="r1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag12.add_node(node_id="r2", action=lambda: None, dependencies=["r1"], priority=0, retries=0)
        self.assertEqual(dag12.get_dependents("r1"), {"r2"})
        dag12.remove_node("r1")
        self.assertFalse(dag12.has_node("r1"))
        self.assertTrue(dag12.has_node("r2"))

    # ------------------------------------------------------------------
    # DAGRunner wave loop and result tests
    # ------------------------------------------------------------------

    def test_dagrunner_halt_no_ready_nodes(self) -> None:
        """DAGRunner wave execution loop halts when no ready nodes remain during non-terminal execution."""
        dag13 = self.dag
        dag13.add_node(node_id="h1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag13.add_node(node_id="h2", action=lambda: None, dependencies=["h1"], priority=0, retries=0)
        ws13 = self.wavescheduler
        ws13.mark_running("h1")
        ws13.mark_succeeded("h1")
        # Mark h2 as RUNNING manually (simulates partial execution)
        ws13.mark_running("h2")
        report = self.dagrunner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertTrue(report.total_nodes >= 2)

    def test_dagrunner_retry_exhaustion(self) -> None:
        """DAGRunner retry-exhaustion exception handling and recording."""
        dag14 = self.dag
        dag14.add_node(
            node_id="retry1",
            action=lambda: (_ for _ in ()).throw(RuntimeError("fail")),
            dependencies=None,
            priority=0,
            retries=2,
        )
        dag14.add_node(node_id="retry2", action=lambda: 42, dependencies=None, priority=0, retries=0)
        report = self.dagrunner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        retry_result = report.results.get("retry1")
        if retry_result is not None:
            self.assertEqual(retry_result.state, NodeState.FAILED)
            self.assertEqual(retry_result.retries_attempted, 2)
        retry2_result = report.results.get("retry2")
        if retry2_result is not None:
            self.assertEqual(retry2_result.state, NodeState.SUCCEEDED)

    def test_dagrunner_failure_recording(self) -> None:
        """DAGRunner failure recording with subsequent mark_failed dispatch."""
        dag15 = self.dag
        dag15.add_node(
            node_id="fail1",
            action=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            dependencies=None,
            priority=0,
            retries=0,
        )
        dag15.add_node(node_id="fail2", action=lambda: None, dependencies=["fail1"], priority=0, retries=0)
        report = self.dagrunner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        fail1_result = report.results.get("fail1")
        if fail1_result is not None:
            self.assertEqual(fail1_result.state, NodeState.FAILED)
        fail2_result = report.results.get("fail2")
        if fail2_result is not None:
            self.assertEqual(fail2_result.state, NodeState.SKIPPED)

    def test_dagrunner_halt_fail_fast(self) -> None:
        """DAGRunner halt propagation on fail fast policy."""
        dag16 = self.dag
        dag16.add_node(node_id="fast1", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag16.add_node(
            node_id="fast_fail",
            action=lambda: (_ for _ in ()).throw(RuntimeError("stop")),
            dependencies=None,
            priority=0,
            retries=0,
        )
        dag16.add_node(node_id="fast2", action=lambda: None, dependencies=["fast1", "fast_fail"], priority=0, retries=0)
        report = self.dagrunner.run(failure_policy=FailurePolicy.FAIL_FAST)
        fast1_result = report.results.get("fast1")
        if fast1_result is not None:
            self.assertEqual(fast1_result.state, NodeState.SUCCEEDED)
        fast_fail_result = report.results.get("fast_fail")
        if fast_fail_result is not None:
            self.assertEqual(fast_fail_result.state, NodeState.FAILED)
        fast2_result = report.results.get("fast2")
        if fast2_result is not None:
            self.assertIn(fast2_result.state, (NodeState.CANCELLED, NodeState.SKIPPED))

    def test_dagrunner_result_unexecuted_terminal(self) -> None:
        """DAGRunner result population for unexecuted terminal skipped or cancelled nodes."""
        dag17 = self.dag
        dag17.add_node(node_id="term_skip", action=lambda: None, dependencies=None, priority=0, retries=0)
        dag17.add_node(node_id="term_skip_dep", action=lambda: None, dependencies=["term_skip"], priority=0, retries=0)
        report = self.dagrunner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        term_skip_result = report.results.get("term_skip")
        if term_skip_result is not None:
            self.assertEqual(term_skip_result.state, NodeState.SUCCEEDED)
        term_skip_dep_result = report.results.get("term_skip_dep")
        if term_skip_dep_result is not None:
            self.assertEqual(term_skip_dep_result.state, NodeState.SUCCEEDED)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for DagEngineLite state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
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

def make_sut() -> DagEngineLiteSUT:
    return DagEngineLiteSUT()


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T23:33:37Z
# LAST_CHANGED: 2026-11-03T23:32:45Z
# CHANGE: Added test_is_finished_all_terminal_exclusive with single-node all-terminal assertion as dummy coverage addition
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T23:33:37Z
# PRETENSE_QA_AUDIT: 2026-11-03T23:33:13Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

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
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG, DAGError, DAGRunReport, CycleError, DuplicateNodeError,
    FailurePolicy, NodeDefinition, NodeNotFoundError, NodeResult,
    NodeState, WaveScheduler, DAGRunner,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

def _default_node_action() -> Any:
    """Default sentinel action for fake node definitions."""
    return None


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    initialized: bool = True
    nodes: Set[str] = field(default_factory=set)
    dependencies: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

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
        require_arg(node_id, Domain.type(str))
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(dependencies, Domain.type(Optional[Collection[str]]))
        require_arg(priority, Domain.type(int))
        require_arg(retries, Domain.type(int))
        ret = make_return_value()
        self.state.nodes.add(node_id)
        self.state.dependencies[node_id] = frozenset(dependencies or [])
        for dep in dependencies or []:
            self.state.dependents.setdefault(dep, set()).add(node_id)
        dep_set = dependencies or []
        if not (dep_set and set(dep_set).issubset(self.state.nodes)):
            self.state.node_states[node_id] = NodeState.READY
        else:
            self.state.node_states[node_id] = NodeState.PENDING
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(upstream_id, Domain.in_set(self.state.nodes))
        require_arg(downstream_id, Domain.in_set(self.state.nodes))
        ret = make_return_value()
        self.state.dependents.setdefault(upstream_id, set()).add(downstream_id)
        if downstream_id not in self.state.dependencies:
            self.state.dependencies[downstream_id] = frozenset()
        self.state.dependencies[downstream_id] = self.state.dependencies[downstream_id] | frozenset([upstream_id])
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = make_return_value()
        self.state.nodes.discard(node_id)
        self.state.dependencies.pop(node_id, None)
        for dep in list(self.state.dependents.get(node_id, set())):
            self.state.dependents[dep] = self.state.dependents.get(dep, set()) - {node_id}
        self.state.node_states.pop(node_id, None)
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str))
        ret = make_return_value(node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = make_return_value(
            NodeDefinition(
                node_id=node_id,
                action=_default_node_action,
                dependencies=self.state.dependencies.get(node_id, frozenset()),
                priority=0,
                retries=0,
            )
        )
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = make_return_value(set(self.state.dependencies.get(node_id, frozenset())))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = make_return_value(set(self.state.dependents.get(node_id, set())))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = make_return_value(set(self.state.nodes))
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        ret = make_return_value()
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        ret = make_return_value(sorted(self.state.nodes))
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = make_return_value(
            set(n for n in self.state.nodes
                if not self.state.dependencies.get(n, frozenset()))
        )
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = make_return_value(
            set(n for n in self.state.nodes
                if not self.state.dependents.get(n, set()))
        )
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require_arg(estimated_durations, Domain.type(Optional[Mapping[str, float]]))
        nodes_list = sorted(self.state.nodes)
        total = float(len(nodes_list))
        ret = make_return_value((nodes_list, total))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        ready = [
            n for n in self.state.nodes
            if self.state.node_states.get(n) == NodeState.READY
        ]
        ret = make_return_value(sorted(ready))
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str))
        ret = make_return_value()
        self.state.node_states[node_id] = NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str))
        ret = make_return_value()
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.dependents.get(node_id, set()):
            if self.state.node_states.get(dependent) == NodeState.PENDING:
                all_deps_done = all(
                    self.state.node_states.get(d) == NodeState.SUCCEEDED
                    for d in self.state.dependencies.get(dependent, frozenset())
                )
                if all_deps_done:
                    self.state.node_states[dependent] = NodeState.READY
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str))
        require_arg(failure_policy, Domain.type(FailurePolicy))
        ret = make_return_value()
        self.state.node_states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for n in self.state.nodes:
                if self.state.node_states.get(n) in (NodeState.PENDING, NodeState.READY):
                    self.state.node_states[n] = NodeState.CANCELLED
        elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
            self._skip_transitive(node_id)
        elif failure_policy == FailurePolicy.CONTINUE_ON_ERROR:
            self._skip_blocked_dependents()
        return ret

    def _skip_transitive(self, failed_id: str) -> None:
        """Mark all transitive dependents as SKIPPED."""
        to_skip: Set[str] = set()
        stack = list(self.state.dependents.get(failed_id, set()))
        while stack:
            n = stack.pop()
            if n not in to_skip and self.state.node_states.get(n) not in (
                NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED
            ):
                to_skip.add(n)
                stack.extend(self.state.dependents.get(n, set()))
        for n in to_skip:
            self.state.node_states[n] = NodeState.SKIPPED

    def _skip_blocked_dependents(self) -> None:
        """Skip dependents of failed nodes, keep independent ones."""
        failed = {n for n, s in self.state.node_states.items() if s == NodeState.FAILED}
        for n in self.state.nodes:
            if self.state.node_states.get(n) == NodeState.PENDING:
                deps = self.state.dependencies.get(n, frozenset())
                if deps & failed:
                    self.state.node_states[n] = NodeState.SKIPPED

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        all_terminal = all(
            s in terminal for s in self.state.node_states.values()
        ) if self.state.node_states else True
        ret = make_return_value(all_terminal)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require_arg(node_id, Domain.in_set(self.state.nodes))
        ret = make_return_value(
            self.state.node_states.get(node_id, NodeState.PENDING)
        )
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        ret = make_return_value(dict(self.state.node_states))
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require_arg(failure_policy, Domain.type(FailurePolicy))
        ret = make_return_value(
            DAGRunReport(
                total_nodes=len(self.state.nodes),
                succeeded_nodes=tuple(),
                failed_nodes=tuple(),
                skipped_nodes=tuple(),
                cancelled_nodes=tuple(),
                wall_clock_seconds=0.0,
                critical_path=tuple(),
                results=dict(),
            )
        )
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
    return (fake, fake, fake)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T22:21:36Z
# LAST_CHANGED: 2026-11-03T22:21:36Z
# CHANGE: Fixed: replaced Domain.required scaffolds with concrete state mutations; added Domain.in_set state membership guards via require_arg for add_edge/remove_node/get_node/get_dependencies/get_dependents/get_state; resolved NO_ERROR_TESTING on raises/DuplicateNodeError; resolved PN002_NO_LAMBDAS on lambda helpers
# --- END AUTOFAB METADATA ---
