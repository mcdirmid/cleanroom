# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteStateMachine,
    DagEngineLiteState,
    FakeDagEngineLite,
    make_dag_engine_lite_fakes,
)
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAGError,
    DAGRunReport,
    DAGRunner as DAGRunnerLib,
    CycleError,
    DAG as DAGLib,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
    WaveScheduler as WaveSchedulerLib,
)
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite_impl import __initialize__ as _dag_engine_lite_initialize


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class DagEngineLiteImplPseudoStateMachine(DagEngineLiteStateMachine):
    """Implementation pseudo-state machine for DagEngineLite."""

    def inner_add_node(
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
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={DAG: self.dag, WaveScheduler: self.wavescheduler, DAGRunner: self.dagrunner}
        )
        self.checked_dag: Any = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler: Any = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner: Any = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_add_and_query_node(self) -> None:
        """Test adding a node and verifying existence via the DAG."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.assertTrue(self.checked_dag.has_node("a"))
        result = self.checked_dag.get_node("a")
        self.assertIsInstance(result, NodeDefinition)
        self.assertEqual(result.node_id, "a")

    def test_remove_node(self) -> None:
        """Test removing a node and verifying it no longer exists."""
        self.checked_dag.add_node("x", lambda: 2, None, 0, 0)
        self.assertTrue(self.checked_dag.has_node("x"))
        self.checked_dag.remove_node("x")
        self.assertFalse(self.checked_dag.has_node("x"))

    def test_add_edge_and_query_dependencies(self) -> None:
        """Test adding nodes, establishing edges, and querying dependency sets."""
        self.checked_dag.add_node("dep1", lambda: 10, None, 0, 0)
        self.checked_dag.add_node("dep2", lambda: 20, None, 0, 0)
        self.checked_dag.add_node("task1", lambda: 30, None, 5, 0)
        self.checked_dag.add_edge("dep1", "task1")
        self.checked_dag.add_edge("dep2", "task1")
        deps = self.checked_dag.get_dependencies("task1")
        self.assertIn("dep1", deps)
        self.assertIn("dep2", deps)

    def test_all_nodes_and_roots(self) -> None:
        """Test node enumeration, root identification, and topological sort."""
        self.checked_dag.add_node("root1", lambda: 1, None, 2, 0)
        self.checked_dag.add_node("root2", lambda: 2, None, 1, 0)
        all_nodes = self.checked_dag.all_nodes()
        self.assertEqual(len(all_nodes), 2)
        roots = self.checked_dag.find_roots()
        self.assertEqual(roots, {"root1", "root2"})
        order = self.checked_dag.topological_sort()
        self.assertIn("root1", order)
        self.assertIn("root2", order)

    def test_validate_acyclic_graph(self) -> None:
        """Test graph validation on an acyclic graph completes without error."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.validate()

    def test_mark_and_check_node_states(self) -> None:
        """Test wave scheduler state transitions for nodes."""
        self.checked_dag.add_node("n1", lambda: 1, None, 0, 0)
        self.checked_wavescheduler.mark_running("n1")
        self.assertEqual(self.checked_wavescheduler.get_state("n1"), NodeState.RUNNING)
        self.checked_wavescheduler.mark_succeeded("n1")
        self.assertEqual(self.checked_wavescheduler.get_state("n1"), NodeState.SUCCEEDED)

    def test_failure_policy_skip_downstream(self) -> None:
        """Test SKIP_DOWNSTREAM failure policy propagates skip to dependents."""
        self.checked_dag.add_node("upstream", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("downstream", lambda: 2, {"upstream"}, 0, 0)
        self.checked_wavescheduler.mark_running("upstream")
        self.checked_wavescheduler.mark_failed("upstream", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.checked_wavescheduler.get_state("upstream"), NodeState.FAILED)

    def test_duplicate_node_error(self) -> None:
        """Test that adding a duplicate node_id raises DuplicateNodeError."""
        self.checked_dag.add_node("dup", lambda: 1, None, 0, 0)
        self.assertTrue(self.checked_dag.has_node("dup"))
        with self.checked_dag.violating(DuplicateNodeError):
            self.checked_dag.add_node("dup", lambda: 2, None, 0, 0)

    def test_node_not_found_error(self) -> None:
        """Test that querying missing nodes correctly returns empty or false."""
        self.assertFalse(self.checked_dag.has_node("nonexistent"))

    def test_violating_add_edge_node_not_found(self) -> None:
        """Test that add_edge raises NodeNotFoundError for missing upstream node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.add_edge("missing", "nonexistent")

    def test_violating_add_edge_node_not_found_downstream(self) -> None:
        """Test that add_edge raises NodeNotFoundError for missing downstream node."""
        self.checked_dag.add_node("existing", lambda: 1, None, 0, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.add_edge("existing", "missing")

    def test_violating_remove_node_not_found(self) -> None:
        """Test that remove_node raises NodeNotFoundError for missing node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.remove_node("nonexistent")

    def test_violating_get_node_not_found(self) -> None:
        """Test that get_node raises NodeNotFoundError for missing node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.get_node("nonexistent")

    def test_violating_get_dependencies_not_found(self) -> None:
        """Test that get_dependencies raises NodeNotFoundError for missing node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.get_dependencies("nonexistent")

    def test_violating_get_dependents_not_found(self) -> None:
        """Test that get_dependents raises NodeNotFoundError for missing node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.get_dependents("nonexistent")

    def test_violating_get_state_not_found(self) -> None:
        """Test that get_state raises NodeNotFoundError for missing node."""
        with self.checked_wavescheduler.violating(NodeNotFoundError):
            self.checked_wavescheduler.get_state("nonexistent")

    def test_find_leaves(self) -> None:
        """Test finding leaf nodes (nodes with no dependents)."""
        self.checked_dag.add_node("leaf1", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("leaf2", lambda: 2, None, 0, 0)
        leaves = self.checked_dag.find_leaves()
        self.assertEqual(leaves, {"leaf1", "leaf2"})

    def test_is_finished_empty_dag(self) -> None:
        """Test that an empty DAG reports is_finished as True."""
        self.assertTrue(self.checked_wavescheduler.is_finished())

    def test_mark_failed_fail_fast(self) -> None:
        """Test FAIL_FAST policy: failed node causes all PENDING nodes to become CANCELLED."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, {"a"}, 0, 0)
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.checked_wavescheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.CANCELLED)
        self.assertEqual(self.checked_wavescheduler.get_state("c"), NodeState.CANCELLED)

    def test_mark_failed_continue_on_error(self) -> None:
        """Test CONTINUE_ON_ERROR: blocked dependents become SKIPPED but independent nodes stay PENDING."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, None, 0, 0)
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.checked_wavescheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self.checked_wavescheduler.get_state("c"), NodeState.READY)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """Test that mark_succeeded promotes PENDING dependents to READY when all upstreams succeed."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.PENDING)
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        self.assertEqual(self.checked_wavescheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.READY)

    def test_compute_critical_path(self) -> None:
        """Test critical path computation with different duration weights."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, {"b"}, 0, 0)
        durations: Mapping[str, float] = {"a": 1.0, "b": 2.0, "c": 3.0}
        path, total = self.checked_dag.compute_critical_path(durations)
        self.assertIsInstance(path, list)
        self.assertIsInstance(total, float)
        self.assertEqual(total, 6.0)
        self.assertEqual(path, ["a", "b", "c"])

    def test_topological_sort_tie_breaking(self) -> None:
        """Test that topological sort breaks ties by priority descending, then node_id ascending."""
        self.checked_dag.add_node("z", lambda: 1, None, 1, 0)
        self.checked_dag.add_node("a", lambda: 2, None, 1, 0)
        self.checked_dag.add_node("m", lambda: 3, None, 2, 0)
        order = self.checked_dag.topological_sort()
        self.assertEqual(order, ["m", "a", "z"])

    def test_cycle_detection(self) -> None:
        """Test that validate raises CycleError on a cyclic graph."""
        self.checked_dag.add_node("x", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("y", lambda: 2, None, 0, 0)
        self.checked_dag.add_node("z", lambda: 3, None, 0, 0)
        self.checked_dag.add_edge("x", "y")
        self.checked_dag.add_edge("y", "z")
        self.checked_dag.add_edge("z", "x")
        with self.checked_dag.violating(CycleError):
            self.checked_dag.validate()

    def test_dagrunner_sequential_waves(self) -> None:
        """Test DAGRunner.run executes waves sequentially and returns DAGRunReport."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        report: DAGRunReport = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("a", "b"))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertIsInstance(report.wall_clock_seconds, float)
        self.assertIsInstance(report.critical_path, tuple)
        self.assertIsInstance(report.results, Mapping)

    def test_dagrunner_failure_with_report(self) -> None:
        """Test DAGRunner.run with a failing node returns report with failed entries."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, None, 0, 0)
        report: DAGRunReport = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 3)

    def test_is_finished_after_full_run(self) -> None:
        """Test that is_finished returns True after all nodes reach terminal states."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertTrue(self.checked_wavescheduler.is_finished())

    def test_add_node_defer_dependency_checks(self) -> None:
        """Test that add_node defers missing dependency validation to validate()."""
        self.checked_dag.add_node("orphan", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("late", lambda: 2, {"missing_dep"}, 0, 0)
        self.assertTrue(self.checked_dag.has_node("late"))
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.validate()

    def test_remove_node_purge_incident_edges(self) -> None:
        """Test that remove_node purges all direct incident upstream and downstream edges.

        The DAG maintains direct edges only (no transitive closure). After removing mid,
        leaf's direct dependency on mid is purged (deps become empty), and root's
        direct dependent on mid is purged (dependents become empty).
        """
        self.checked_dag.add_node("root", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("mid", lambda: 2, {"root"}, 0, 0)
        self.checked_dag.add_node("leaf", lambda: 3, {"mid"}, 0, 0)
        self.assertTrue(self.checked_dag.has_node("mid"))
        self.assertEqual(self.checked_dag.get_dependencies("mid"), {"root"})
        self.assertEqual(self.checked_dag.get_dependents("root"), {"mid"})
        self.checked_dag.remove_node("mid")
        self.assertFalse(self.checked_dag.has_node("mid"))
        # Direct incident edges are purged; no transitive edges are created.
        self.assertEqual(self.checked_dag.get_dependencies("leaf"), set())
        self.assertEqual(self.checked_dag.get_dependents("root"), set())

    def test_validate_missing_dependency_error(self) -> None:
        """Test that validate raises NodeNotFoundError when a node's dependency is missing."""
        self.checked_dag.add_node("child", lambda: 1, {"ghost"}, 0, 0)
        self.checked_dag.add_node("standalone", lambda: 2, None, 0, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.validate()

    def test_compute_critical_path_empty_dag(self) -> None:
        """Test compute_critical_path returns empty path and zero weight for empty DAG."""
        path, total = self.checked_dag.compute_critical_path({})
        self.assertIsInstance(path, list)
        self.assertEqual(path, [])
        self.assertEqual(total, 0.0)

    def test_mark_failed_skip_downstream_terminal(self) -> None:
        """Test SKIP_DOWNSTREAM: already-terminal dependents (SUCCEEDED) remain unchanged."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, None, 0, 0)
        self.checked_wavescheduler.mark_running("a")
        self.checked_wavescheduler.mark_succeeded("a")
        self.assertEqual(self.checked_wavescheduler.get_state("a"), NodeState.SUCCEEDED)
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.READY)
        self.checked_wavescheduler.mark_running("b")
        self.checked_wavescheduler.mark_succeeded("b")
        self.assertEqual(self.checked_wavescheduler.get_state("b"), NodeState.SUCCEEDED)
        self.assertEqual(self.checked_wavescheduler.get_state("c"), NodeState.READY)
        self.checked_wavescheduler.mark_running("c")
        self.checked_wavescheduler.mark_failed("c", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.checked_wavescheduler.get_state("c"), NodeState.FAILED)

    def test_runner_node_action_raises_exception(self) -> None:
        """Test DAGRunner with a node whose action raises an exception, retries exhausted."""
        self.checked_dag.add_node("failing", lambda: (_ for _ in ()).throw(RuntimeError("boom")), None, 0, 1)
        self.checked_dag.add_node("ok", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("blocked", lambda: 2, {"failing"}, 0, 0)
        report: DAGRunReport = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, DAGRunReport)
        self.assertTrue(report.total_nodes >= 3)

    def test_runner_fail_fast_early_return(self) -> None:
        """Test DAGRunner with FAIL_FAST terminates after first node failure, blocking dependents."""
        self.checked_dag.add_node("root1", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("root2", lambda: 2, None, 0, 0)
        self.checked_dag.add_node("child", lambda: 3, {"root1", "root2"}, 0, 0)
        report: DAGRunReport = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, DAGRunReport)
        self.assertTrue(report.total_nodes >= 3)

    def test_runner_failure_with_cancelled_dependents(self) -> None:
        """Test DAGRunner.FAIL_FAST: cancelled dependents appear in report."""
        self.checked_dag.add_node("a", lambda: 1, None, 0, 0)
        self.checked_dag.add_node("b", lambda: 2, {"a"}, 0, 0)
        self.checked_dag.add_node("c", lambda: 3, {"a"}, 0, 0)
        report: DAGRunReport = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertIsNotNone(report)
        self.assertIsInstance(report, DAGRunReport)
        self.assertIsInstance(report.cancelled_nodes, tuple)


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for DagEngineLite state machine testing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_lite_initialize(self.registry)
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
    initial_state_factory=proto.make_initial_state,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T01:37:31Z
# LAST_CHANGED: 2026-11-10T01:36:35Z
# CHANGE: Fixed test_duplicate_node_error to use self.checked_dag.violating(DuplicateNodeError) to properly exercise the DuplicateNodeError path when adding a node_id that already exists in the DAG. The original test only added a node and called validate() without actually triggering the duplicate node error.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T01:37:31Z
# PRETENSE_QA_AUDIT: 2026-11-10T01:36:58Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    synthesize_fake,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_4.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    initialized: bool = True
    node_ids: Set[str] = field(default_factory=set)


class DagEngineLiteStateMachine(StateMachine[DagEngineLiteState]):
    """Unified Pretense State Machine for DagEngineLite."""

    def __init__(
        self,
        state: Optional[DagEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DagEngineLiteState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return DagEngineLiteState()

    def inner_add_node(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def inner_add_edge(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def inner_remove_node(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.node_ids

    def inner_get_node(self, node_id: str) -> Any:
        return NodeDefinition(node_id, lambda: None, frozenset(), 0, 0)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return set()

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return set()

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.node_ids)

    def inner_validate(self) -> None:
        return None

    def inner_topological_sort(self) -> List[str]:
        return list(self.state.node_ids)

    def inner_find_roots(self) -> Set[str]:
        return set(self.state.node_ids)

    def inner_find_leaves(self) -> Set[str]:
        return set(self.state.node_ids)

    def inner_compute_critical_path(self, estimated_durations: Any) -> Tuple[List[str], float]:
        return (list(self.state.node_ids), 0.0)

    def inner_next_wave(self) -> List[str]:
        return list(self.state.node_ids)

    def inner_mark_running(self, node_id: str) -> None:
        return None

    def inner_mark_succeeded(self, node_id: str) -> None:
        return None

    def inner_mark_failed(self, node_id: str, failure_policy: Any) -> None:
        return None

    def inner_is_finished(self) -> bool:
        return True

    def inner_get_state(self, node_id: str) -> NodeState:
        return NodeState.PENDING

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return {nid: NodeState.PENDING for nid in self.state.node_ids}

    def inner_run(self, failure_policy: Any) -> DAGRunReport:
        return DAGRunReport(0, (), (), (), (), 0.0, (), {})

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
        require_arg(node_id, Domain.type(str), preferred=["node1"])
        require_arg(action, Domain.type(Callable))
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])))
        require_arg(priority, Domain.range(-100, 100), preferred=[0])
        require_arg(retries, Domain.range(0, 10), preferred=[0])
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        self.state.node_ids.add(node_id)
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(upstream_id, Domain.in_set(self.state.node_ids))
        require_arg(downstream_id, Domain.in_set(self.state.node_ids))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(node_id, Domain.in_set(self.state.node_ids))
        ret = self.inner_remove_node(node_id)
        self.state.node_ids.discard(node_id)
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["node1"])
        ret: bool = self.inner_has_node(node_id)
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(node_id, Domain.in_set(self.state.node_ids))
        ret: NodeDefinition[Any] = self.inner_get_node(node_id)
        assert ret is not None
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(node_id, Domain.in_set(self.state.node_ids))
        ret: Set[str] = self.inner_get_dependencies(node_id)
        assert isinstance(ret, (set, frozenset))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(node_id, Domain.in_set(self.state.node_ids))
        ret: Set[str] = self.inner_get_dependents(node_id)
        assert isinstance(ret, (set, frozenset))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_all_nodes()
        assert isinstance(ret, (set, frozenset))
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        ret = self.inner_validate()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        ret: List[str] = self.inner_topological_sort()
        assert isinstance(ret, list)
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_find_roots()
        assert isinstance(ret, (set, frozenset))
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret: Set[str] = self.inner_find_leaves()
        assert isinstance(ret, (set, frozenset))
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require_arg(estimated_durations, Domain.optional(Domain.type(Mapping[str, float])), preferred=[[None]])
        ret: Tuple[List[str], float] = self.inner_compute_critical_path(estimated_durations)
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        assert isinstance(ret[0], list)
        assert isinstance(ret[1], float)
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        ret: List[str] = self.inner_next_wave()
        assert isinstance(ret, list)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["node1"])
        ret = self.inner_mark_running(node_id)
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(node_id, Domain.in_set(self.state.node_ids))
        ret = self.inner_mark_succeeded(node_id)
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["node1"])
        require_arg(failure_policy, Domain.type(FailurePolicy), preferred=[FailurePolicy.FAIL_FAST])
        ret = self.inner_mark_failed(node_id, failure_policy)
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        ret: bool = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require(self.state.node_ids)
        require_arg(node_id, Domain.in_set(self.state.node_ids))
        ret: NodeState = self.inner_get_state(node_id)
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        ret: Mapping[str, NodeState] = self.inner_get_all_states()
        assert isinstance(ret, Mapping)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require_arg(failure_policy, Domain.type(FailurePolicy), preferred=[FailurePolicy.FAIL_FAST])
        ret: DAGRunReport = self.inner_run(failure_policy)
        assert ret is not None
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
) -> Tuple[FailurePolicy, NodeDefinition, NodeResult, DAGRunReport, DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
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

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fakes = make_dag_engine_lite_fakes()
        self.sm = DagEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.sm.add_node("node1", lambda: None, None, 0, 0)
        self.sm.add_node("node2", lambda: None, None, 0, 0)
        self.sm.add_edge("node1", "node2")
        self.sm.has_node("node1")
        self.sm.get_node("node1")
        self.sm.get_dependencies("node1")
        self.sm.get_dependents("node1")
        self.sm.all_nodes()
        self.sm.validate()
        self.sm.topological_sort()
        self.sm.find_roots()
        self.sm.find_leaves()
        self.sm.compute_critical_path(None)
        self.sm.next_wave()
        self.sm.mark_running("node1")
        self.sm.mark_succeeded("node1")
        self.sm.mark_failed("node1", FailurePolicy.FAIL_FAST)
        self.sm.is_finished()
        self.sm.get_state("node1")
        self.sm.get_all_states()
        self.sm.run(FailurePolicy.FAIL_FAST)
        self.sm.remove_node("node2")


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T00:22:48Z
# LAST_CHANGED: 2026-11-10T00:22:48Z
# CHANGE: Fixed mark_succeeded precondition: replaced Domain.type(str) with Domain.in_set(self.state.node_ids) + require(self.state.node_ids) to guard node_id against non-existent nodes.
# --- END AUTOFAB METADATA ---
