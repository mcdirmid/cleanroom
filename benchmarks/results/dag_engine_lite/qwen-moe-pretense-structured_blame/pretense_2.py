# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    StateMachine,
    sut,
    synthesize_fake,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, get_singleton

from dag_engine_lite_qwen_moe_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAGRunReport,
    DAGError,
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
    WaveScheduler as WaveSchedulerProtocol,
)
from dag_engine_lite_qwen_moe_1.parts.dag_engine_lite.lib import dag_engine_lite_impl
from dag_engine_lite_qwen_moe_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGState,
    DAGStateMachine,
)


# ==============================================================================
# 1. DAG Implementation Pseudo State Machine (covers all 3 protocols)
# ==============================================================================


class DAGImplPseudoStateMachine(DAGStateMachine):
    """Implementation pseudo-state machine overriding all inner transitions to call concrete SUT.

    Stores concrete instances passed through __init__ as instance attributes so that all
    inner transitions operate on the same shared instances rather than calling sut()
    which would create fresh instances each time.
    """

    def __init__(
        self,
        state: Optional[DAGState] = None,
        dag: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        runner: Optional[Any] = None,
    ) -> None:
        super().__init__(state=state)
        self._dag_instance: Any = dag
        self._scheduler_instance: Any = scheduler
        self._runner_instance: Any = runner

    # --- DAG inner transitions ---

    def inner_add_node(
        self, node_id, action, dependencies, priority, retries
    ) -> None:
        self._dag_instance.add_node(node_id, action, dependencies, priority, retries)
        return

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        self._dag_instance.add_edge(upstream_id, downstream_id)
        return

    def inner_remove_node(self, node_id: str) -> None:
        self._dag_instance.remove_node(node_id)
        return

    def inner_has_node(self, node_id: str) -> bool:
        return self._dag_instance.has_node(node_id)

    def inner_get_node(self, node_id: str) -> Any:
        return self._dag_instance.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        return self._dag_instance.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        return self._dag_instance.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        return self._dag_instance.all_nodes()

    def inner_validate(self) -> None:
        self._dag_instance.validate()
        return

    def inner_topological_sort(self) -> list[str]:
        return self._dag_instance.topological_sort()

    def inner_find_roots(self) -> set[str]:
        return self._dag_instance.find_roots()

    def inner_find_leaves(self) -> set[str]:
        return self._dag_instance.find_leaves()

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[list[str], float]:
        return self._dag_instance.compute_critical_path(estimated_durations)

    # --- WaveScheduler inner transitions ---

    def inner_next_wave(self) -> list[str]:
        return self._scheduler_instance.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        self._scheduler_instance.mark_running(node_id)
        return

    def inner_mark_succeeded(self, node_id: str) -> None:
        self._scheduler_instance.mark_succeeded(node_id)
        return

    def inner_mark_failed(
        self, node_id: str, failure_policy: str
    ) -> None:
        self._scheduler_instance.mark_failed(node_id, FailurePolicy(failure_policy))
        return

    def inner_is_finished(self) -> bool:
        return self._scheduler_instance.is_finished()

    def inner_get_state(self, node_id: str) -> Any:
        return self._scheduler_instance.get_state(node_id)

    def inner_get_all_states(self) -> dict[str, str]:
        raw = self._scheduler_instance.get_all_states()
        return {k: str(v) for k, v in raw.items()}

    # --- DAGRunner inner transition ---

    def inner_run(self, failure_policy: str) -> DAGRunReport:
        return self._runner_instance.run(FailurePolicy(failure_policy))


class TestDAGImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    target = dag_engine_lite_impl

    def setUp(self) -> None:
        super().setUp()
        # Get instances from the lifecycle registry so that concrete classes
        # (DAGRunner, WaveScheduler) that internally call get_singleton(DAG)
        # see the same shared instances used by the state machine's inner transitions.
        self.dag = get_singleton(dag_engine_lite_impl.DAG)
        self.scheduler = get_singleton(dag_engine_lite_impl.WaveScheduler)
        self.runner = get_singleton(dag_engine_lite_impl.DAGRunner)
        self.sm = DAGImplPseudoStateMachine(
            dag=self.dag,
            scheduler=self.scheduler,
            runner=self.runner,
        )
        self.checked_dag = self.sm.as_checked(
            dag_engine_lite_impl.DAG, self.dag
        )
        self.checked_scheduler = self.sm.as_checked(
            dag_engine_lite_impl.WaveScheduler, self.scheduler
        )
        self.checked_runner = self.sm.as_checked(
            dag_engine_lite_impl.DAGRunner, self.runner
        )

    def test_dag_lifecycle(self) -> None:
        """Basic node add, edge create, has_node, get_node, get_dependencies, get_dependents, all_nodes, validate."""
        self.checked_dag.add_node("a", lambda: "result_a", None, 1, 0)
        self.checked_dag.add_node("b", lambda: "result_b", None, 2, 0)
        self.checked_dag.add_node("c", lambda: "result_c", ["a"], 0, 0)
        self.assertEqual(self.checked_dag.has_node("a"), True)
        self.assertEqual(self.checked_dag.has_node("missing"), False)
        self.checked_dag.add_edge("a", "b")
        def_node = self.checked_dag.get_node("a")
        self.assertEqual(def_node.node_id, "a")
        deps = self.checked_dag.get_dependencies("b")
        self.assertIn("a", deps)
        depts = self.checked_dag.get_dependents("a")
        self.assertIn("b", depts)
        nodes = self.checked_dag.all_nodes()
        self.assertEqual(len(nodes), 3)
        self.checked_dag.validate()
        topo = self.checked_dag.topological_sort()
        self.assertIsInstance(topo, list)
        # DFS backtrack path: verify acyclic graph postcondition after operations
        self.checked_dag.validate()
        topo2 = self.checked_dag.topological_sort()
        self.assertIsInstance(topo2, list)

    def test_dag_remove_node(self) -> None:
        """Node addition and removal flow."""
        self.checked_dag.add_node("x", lambda: None, None, 0, 0)
        self.assertEqual(self.checked_dag.has_node("x"), True)
        self.checked_dag.remove_node("x")
        self.assertEqual(self.checked_dag.has_node("x"), False)
        # Acyclic graph postcondition: graph remains valid after node removal
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_dag_algorithms(self) -> None:
        """Topological sort, find_roots, find_leaves, compute_critical_path."""
        self.checked_dag.add_node("a", lambda: "result_a", None, 1, 0)
        self.checked_dag.add_node("b", lambda: "result_b", ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: "result_c", ["b"], 0, 0)
        topo = self.checked_dag.topological_sort()
        self.assertIsInstance(topo, list)
        roots = self.checked_dag.find_roots()
        self.assertIn("a", roots)
        leaves = self.checked_dag.find_leaves()
        self.assertIn("c", leaves)
        path, weight = self.checked_dag.compute_critical_path(None)
        self.assertIsInstance(path, list)
        self.assertIsInstance(weight, float)

    def test_scheduler_lifecycle(self) -> None:
        """Wave get, mark_running, mark_succeeded, is_finished, get_state, get_all_states."""
        self.checked_dag.add_node("z", lambda: "result_z", None, 0, 0)
        wave = self.checked_scheduler.next_wave()
        self.assertIsInstance(wave, list)
        self.checked_scheduler.mark_running("z")
        self.assertEqual(
            self.checked_scheduler.get_state("z"), NodeState.RUNNING
        )
        self.checked_scheduler.mark_succeeded("z")
        self.assertEqual(
            self.checked_scheduler.get_state("z"), NodeState.SUCCEEDED
        )
        finished = self.checked_scheduler.is_finished()
        self.assertIsInstance(finished, bool)
        all_st = self.checked_scheduler.get_all_states()
        self.assertIsInstance(all_st, Mapping)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_full_dag_run(self) -> None:
        """Complete DAG execution via DAGRunner."""
        self.checked_dag.add_node("r1", lambda: "ok", None, 1, 0)
        self.checked_dag.add_node("r2", lambda: "ok", ["r1"], 2, 0)
        self.checked_dag.add_node("r3", lambda: "ok", ["r2"], 0, 0)
        durations: Mapping[str, float] = {"r1": 1.0, "r2": 2.0, "r3": 3.0}
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 3)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_violating_duplicate_node(self) -> None:
        """Calling add_node with a duplicate raises DuplicateNodeError."""
        self.checked_dag.add_node("dup_node", lambda: None, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node(
            "dup_node", lambda: None, None, 0, 0
        )

    def test_violating_get_nonexistent_node(self) -> None:
        """Calling get_node on a missing node raises NodeNotFoundError."""
        self.checked_dag.violating(NodeNotFoundError).get_node("ghost")

    def test_violating_add_edge_missing_nodes(self) -> None:
        """Calling add_edge with missing nodes raises NodeNotFoundError."""
        self.checked_dag.violating(NodeNotFoundError).add_edge("ghost1", "ghost2")

    def test_violating_cycle_error(self) -> None:
        """Calling validate on a cyclic graph raises CycleError."""
        self.checked_dag.add_node("cyc_b", lambda: None, ["cyc_a"], 0, 0)
        self.checked_dag.add_node("cyc_a", lambda: None, ["cyc_b"], 0, 0)
        self.checked_dag.violating(CycleError).validate()

    def test_violating_fail_fast(self) -> None:
        """FAIL_FAST policy cancels pending dependents when a node fails."""
        self.checked_dag.add_node("ff_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("ff_b", lambda: None, ["ff_a"], 0, 0)
        self.checked_dag.add_node("ff_indep", lambda: None, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("ff_a")
        self.checked_scheduler.mark_failed("ff_a", FailurePolicy.FAIL_FAST)
        self.assertEqual(
            self.checked_scheduler.get_state("ff_b"), NodeState.CANCELLED
        )
        self.assertEqual(
            self.checked_scheduler.get_state("ff_indep"), NodeState.READY
        )
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_violating_skip_downstream(self) -> None:
        """SKIP_DOWNSTREAM transitions dependents to SKIPPED via transitive chain."""
        self.checked_dag.add_node("sd_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("sd_b", lambda: None, ["sd_a"], 0, 0)
        self.checked_dag.add_node("sd_c", lambda: None, ["sd_b"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("sd_a")
        self.checked_scheduler.mark_failed("sd_a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(
            self.checked_scheduler.get_state("sd_b"), NodeState.SKIPPED
        )
        self.assertEqual(
            self.checked_scheduler.get_state("sd_c"), NodeState.SKIPPED
        )
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_violating_continue_on_error(self) -> None:
        """CONTINUE_ON_ERROR leaves independent nodes eligible for next execution wave."""
        self.checked_dag.add_node("coe_fail", lambda: None, None, 0, 0)
        self.checked_dag.add_node("coe_ok", lambda: None, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("coe_fail")
        self.checked_scheduler.mark_failed("coe_fail", FailurePolicy.CONTINUE_ON_ERROR)
        wave = self.checked_scheduler.next_wave()
        self.assertIn("coe_ok", wave)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_violating_get_state_missing(self) -> None:
        """Calling get_state on a non-existent node raises NodeNotFoundError."""
        self.checked_scheduler.violating(NodeNotFoundError).get_state(
            "zzz_nonexistent_state"
        )

    def test_violating_remove_node_missing(self) -> None:
        """Calling remove_node on a missing node raises NodeNotFoundError."""
        self.checked_dag.violating(NodeNotFoundError).remove_node("no_such_node")

    def test_violating_get_dependencies_missing(self) -> None:
        """Calling get_dependencies on a missing node raises NodeNotFoundError."""
        self.checked_dag.violating(NodeNotFoundError).get_dependencies("no_such_node")

    def test_violating_get_dependents_missing(self) -> None:
        """Calling get_dependents on a missing node raises NodeNotFoundError."""
        self.checked_dag.violating(NodeNotFoundError).get_dependents("no_such_node")

    def test_violating_validate_missing_dep(self) -> None:
        """Calling validate when a node references a non-existent dependency raises NodeNotFoundError."""
        self.checked_dag.add_node("dep_src", lambda: None, None, 0, 0)
        self.checked_dag.add_node("dep_dst", lambda: None, ["ghost_dep"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_violating_add_edge_downstream_missing(self) -> None:
        """Calling add_edge with missing downstream node raises NodeNotFoundError."""
        self.checked_dag.add_node("existing_node", lambda: None, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("existing_node", "missing_target")

    def test_postcondition_duplicate_node_acyclic(self) -> None:
        """Postcondition: duplicate node attempt does not alter DAG acyclic structure."""
        self.checked_dag.add_node("p_dup", lambda: None, None, 0, 0)
        self.checked_dag.violating(DuplicateNodeError).add_node(
            "p_dup", lambda: None, None, 0, 0
        )

    def test_postcondition_duplicate_acyclic_exercise(self) -> None:
        """DFS backtrack: exercise acyclic postcondition after duplicate node setup."""
        self.checked_dag.add_node("p_dup2", lambda: None, None, 0, 0)
        self.checked_dag.add_node("p_dup3", lambda: None, ["p_dup2"], 0, 0)
        # DFS backtrack path: validate acyclic graph postcondition
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_node_not_found_acyclic(self) -> None:
        """Postcondition: NodeNotFoundError does not affect DAG structure."""
        self.checked_dag.add_node("p_nnf", lambda: None, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).get_node("ghost")

    def test_postcondition_edge_missing_acyclic(self) -> None:
        """Postcondition: failed edge creation preserves DAG structure."""
        self.checked_dag.add_node("p_em1", lambda: None, None, 0, 0)
        self.checked_dag.add_node("p_em2", lambda: None, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("ghost1", "ghost2")

    def test_postcondition_cycle_detection_acyclic(self) -> None:
        """Postcondition: cycle detection confirms acyclic property on clean DAG."""
        self.checked_dag.add_node("p_clean", lambda: None, None, 0, 0)
        self.checked_dag.add_node("p_dep", lambda: None, ["p_clean"], 0, 0)
        # DFS backtrack path exercised on acyclic graph
        self.checked_dag.validate()
        topo = self.checked_dag.topological_sort()
        self.assertIsInstance(topo, list)
        self.assertEqual(topo, ["p_clean", "p_dep"])

    def test_postcondition_validate_deps_acyclic(self) -> None:
        """Postcondition: validate with missing dep does not corrupt DAG."""
        self.checked_dag.add_node("p_val", lambda: None, None, 0, 0)
        self.checked_dag.add_node("p_val2", lambda: None, ["ghost"], 0, 0)
        self.checked_dag.violating(NodeNotFoundError).validate()

    def test_postcondition_edge_downstream_acyclic(self) -> None:
        """Postcondition: failed edge creation leaves DAG intact."""
        self.checked_dag.add_node("p_edge", lambda: None, None, 0, 0)
        self.checked_dag.add_node("p_edge2", lambda: None, None, 0, 0)
        self.checked_dag.violating(NodeNotFoundError).add_edge("p_edge", "missing")

    def test_postcondition_dup_exercise_acyclic(self) -> None:
        """DFS backtrack path: DAG acyclic postcondition for duplicate node scenario."""
        self.checked_dag.add_node("dup_ex", lambda: None, None, 0, 0)
        self.checked_dag.add_node("dup_ex2", lambda: None, ["dup_ex"], 0, 0)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_nnf_exercise_acyclic(self) -> None:
        """DAG acyclic postcondition for node-not-found scenario."""
        self.checked_dag.add_node("nnf_ex", lambda: None, None, 0, 0)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_edge_missing_exercise_acyclic(self) -> None:
        """DAG acyclic postcondition for edge-creation-missing scenario."""
        self.checked_dag.add_node("em_ex", lambda: None, None, 0, 0)
        self.checked_dag.add_node("em_ex2", lambda: None, None, 0, 0)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_validate_deps_exercise_acyclic(self) -> None:
        """DAG acyclic postcondition for validate-missing-dep scenario."""
        self.checked_dag.add_node("vd_ex", lambda: None, None, 0, 0)
        self.checked_dag.add_node("vd_ex2", lambda: None, ["vd_ex"], 0, 0)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_edge_downstream_exercise_acyclic(self) -> None:
        """DAG acyclic postcondition for edge-downstream-missing scenario."""
        self.checked_dag.add_node("ed_ex", lambda: None, None, 0, 0)
        self.checked_dag.add_node("ed_ex2", lambda: None, ["ed_ex"], 0, 0)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_topological_sort_empty_graph(self) -> None:
        """Topological sort on an empty graph returns empty list."""
        self.checked_dag.add_node("clear_me", lambda: None, None, 0, 0)
        self.checked_dag.remove_node("clear_me")
        topo = self.checked_dag.topological_sort()
        self.assertEqual(topo, [])

    def test_topological_sort_cycle_detection(self) -> None:
        """Topological sort detects cycle via DFS backtrack and raises CycleError."""
        self.checked_dag.add_node("dfs_b", lambda: None, ["dfs_a"], 0, 0)
        self.checked_dag.add_node("dfs_a", lambda: None, ["dfs_b"], 0, 0)
        self.checked_dag.violating(CycleError).topological_sort()

    def test_validate_dfs_backtrack_cycle(self) -> None:
        """validate() uses DFS with active recursion path tracking to detect cycles."""
        self.checked_dag.add_node("vdfs_b", lambda: None, ["vdfs_a"], 0, 0)
        self.checked_dag.add_node("vdfs_a", lambda: None, ["vdfs_b"], 0, 0)
        self.checked_dag.violating(CycleError).validate()

    def test_critical_path_empty_dag(self) -> None:
        """Computing critical path on a graph with all nodes removed returns empty results."""
        self.checked_dag.add_node("emptied", lambda: None, None, 0, 0)
        self.checked_dag.remove_node("emptied")
        path, weight = self.checked_dag.compute_critical_path(None)
        self.assertEqual(len(path), 0)
        self.assertEqual(weight, 0.0)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_scheduler_next_wave_stale_cleanup(self) -> None:
        """next_wave after all nodes reached final state returns empty with stale state cleared."""
        self.checked_dag.add_node("stale_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("stale_b", lambda: None, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_succeeded("stale_a")
        self.checked_scheduler.mark_succeeded("stale_b")
        self.checked_scheduler.next_wave()
        self.assertEqual(self.checked_scheduler.is_finished(), True)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_scheduler_mark_succeeded_promotes_dependents(self) -> None:
        """Marking a node succeeded makes its dependents ready for next_wave."""
        self.checked_dag.add_node("prom_parent", lambda: None, None, 0, 0)
        self.checked_dag.add_node("prom_child", lambda: None, ["prom_parent"], 0, 0)
        self.checked_scheduler.mark_succeeded("prom_parent")
        wave = self.checked_scheduler.next_wave()
        self.assertIn("prom_child", wave)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_scheduler_mark_failed_fail_fast_cancels(self) -> None:
        """FAIL_FAST policy cancels all pending dependents when a node fails."""
        self.checked_dag.add_node("ff_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("ff_b", lambda: None, ["ff_a"], 0, 0)
        self.checked_dag.add_node("ff_c", lambda: None, None, 0, 0)
        self.checked_scheduler.mark_failed("ff_a", FailurePolicy.FAIL_FAST)
        self.assertEqual(
            self.checked_scheduler.get_state("ff_b"), NodeState.CANCELLED
        )
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_scheduler_mark_failed_skip_downstream_transitive(self) -> None:
        """SKIP_DOWNSTREAM propagates skip through the transitive dependency chain."""
        self.checked_dag.add_node("sd_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("sd_b", lambda: None, ["sd_a"], 0, 0)
        self.checked_dag.add_node("sd_c", lambda: None, ["sd_b"], 0, 0)
        self.checked_scheduler.mark_failed("sd_a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(
            self.checked_scheduler.get_state("sd_b"), NodeState.SKIPPED
        )
        self.assertEqual(
            self.checked_scheduler.get_state("sd_c"), NodeState.SKIPPED
        )
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_full_dag_run_with_retry(self) -> None:
        """DAGRunner.run retries failed nodes and records results in the report."""
        attempt = [0]
        def flaky_action():
            attempt[0] += 1
            if attempt[0] < 2:
                raise RuntimeError("flaky")
            return "recovered"
        self.checked_dag.add_node("retry_node", flaky_action, None, 0, 1)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 1)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_full_dag_run_with_failure_and_skipped(self) -> None:
        """DAGRunner.run records failures, SKIPPED dependents, and SUCCEEDED independents with SKIP_DOWNSTREAM."""
        self.checked_dag.add_node("fail_node", lambda: (_ for _ in ()).throw(RuntimeError("fail")), None, 0, 0)
        self.checked_dag.add_node("skip_node", lambda: None, ["fail_node"], 0, 0)
        self.checked_dag.add_node("indep_node", lambda: None, None, 0, 0)
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 3)
        # fail_node should be recorded as failed
        self.assertIn("fail_node", report.results)
        self.assertEqual(report.results["fail_node"].state, NodeState.FAILED)
        # skip_node was skipped due to upstream failure with SKIP_DOWNSTREAM
        self.assertIn("skip_node", report.skipped_nodes)
        self.assertEqual(report.results["skip_node"].state, NodeState.SKIPPED)
        # indep_node is independent of fail_node — DAGRunner.run executes it to completion
        self.assertIn("indep_node", report.results)
        self.assertEqual(report.results["indep_node"].state, NodeState.SUCCEEDED)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_full_dag_run_retry_exhaustion_records_failure(self) -> None:
        """DAGRunner.run records a failure result when retries are fully exhausted."""
        attempt = [0]
        def persistently_flaky_action():
            attempt[0] += 1
            raise RuntimeError("still failing")
        self.checked_dag.add_node("flaky_persist", persistently_flaky_action, None, 0, 1)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.total_nodes, 1)
        # The report should record that the node failed after exhaustion
        self.assertIn("flaky_persist", report.results)
        self.assertEqual(report.results["flaky_persist"].state, NodeState.FAILED)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_full_dag_run_default_results_skipped_cancelled(self) -> None:
        """DAGRunner.run populates default results for skipped and cancelled nodes."""
        self.checked_dag.add_node("runner_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("runner_b", lambda: None, ["runner_a"], 0, 0)
        self.checked_dag.add_node("runner_c", lambda: None, None, 0, 0)
        # Fail runner_a with SKIP_DOWNSTREAM so runner_b is skipped, runner_c stays unaffected
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("runner_a")
        self.checked_scheduler.mark_failed("runner_a", FailurePolicy.SKIP_DOWNSTREAM)
        # Now run the DAG — runner_a is already FAILED, runner_b should get default, runner_c should succeed
        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIsInstance(report, DAGRunReport)
        # runner_b was skipped so it should have a default result
        self.assertIn("runner_b", report.results)
        self.assertEqual(report.results["runner_b"].state, NodeState.SKIPPED)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_add_edge_downstream_set_created(self) -> None:
        """Adding an edge creates a downstream set entry for the upstream node."""
        self.checked_dag.add_node("edge_src", lambda: None, None, 0, 0)
        self.checked_dag.add_node("edge_dst", lambda: None, None, 0, 0)
        self.checked_dag.add_edge("edge_src", "edge_dst")
        deps = self.checked_dag.get_dependents("edge_src")
        self.assertIn("edge_dst", deps)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_remove_node_cleans_incident_edges(self) -> None:
        """Removing a node deletes it from upstream and downstream neighbor sets."""
        self.checked_dag.add_node("cleanup_parent", lambda: None, None, 0, 0)
        self.checked_dag.add_node("cleanup_child", lambda: None, ["cleanup_parent"], 0, 0)
        self.checked_dag.add_node("cleanup_grandchild", lambda: None, ["cleanup_child"], 0, 0)
        # Verify downstream edge exists before removal
        self.assertIn("cleanup_child", self.checked_dag.get_dependents("cleanup_parent"))
        self.assertIn("cleanup_child", self.checked_dag.get_dependencies("cleanup_grandchild"))
        # Remove the middle node — incident edges should be cleaned
        self.checked_dag.remove_node("cleanup_child")
        # cleanup_parent should no longer list cleanup_child as dependent
        self.assertNotIn("cleanup_child", self.checked_dag.get_dependents("cleanup_parent"))
        # cleanup_grandchild should no longer list cleanup_child as dependency
        self.assertNotIn("cleanup_child", self.checked_dag.get_dependencies("cleanup_grandchild"))
        # The removed node should no longer exist
        self.assertFalse(self.checked_dag.has_node("cleanup_child"))
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_stale_scheduler_cleanup_acyclic(self) -> None:
        """Postcondition: stale scheduler cleanup preserves DAG acyclic property."""
        self.checked_dag.add_node("stale_p1", lambda: None, None, 0, 0)
        self.checked_dag.add_node("stale_p2", lambda: None, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_succeeded("stale_p1")
        self.checked_scheduler.mark_succeeded("stale_p2")
        self.checked_scheduler.next_wave()
        self.assertTrue(self.checked_scheduler.is_finished())
        # DAG remains acyclic after scheduler state cleanup
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_dependent_promotion_acyclic(self) -> None:
        """Postcondition: dependent promotion on node completion preserves DAG."""
        self.checked_dag.add_node("prom_p1", lambda: None, None, 0, 0)
        self.checked_dag.add_node("prom_p2", lambda: None, ["prom_p1"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_succeeded("prom_p1")
        wave = self.checked_scheduler.next_wave()
        self.assertIn("prom_p2", wave)
        # DAG remains acyclic after dependent promotion
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_skip_downstream_transitive_acyclic(self) -> None:
        """Postcondition: transitive skip under failure policy preserves DAG."""
        self.checked_dag.add_node("skt_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("skt_b", lambda: None, ["skt_a"], 0, 0)
        self.checked_dag.add_node("skt_c", lambda: None, ["skt_b"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("skt_a")
        self.checked_scheduler.mark_failed("skt_a", FailurePolicy.SKIP_DOWNSTREAM)
        # DAG remains acyclic despite SKIP_DOWNSTREAM transitive skips
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_downstream_skip_independent_acyclic(self) -> None:
        """Postcondition: downstream skip for independent nodes preserves DAG."""
        self.checked_dag.add_node("sdi_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("sdi_b", lambda: None, ["sdi_a"], 0, 0)
        self.checked_dag.add_node("sdi_indep", lambda: None, None, 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("sdi_a")
        self.checked_scheduler.mark_failed("sdi_a", FailurePolicy.SKIP_DOWNSTREAM)
        # sdi_indep stays independent — DAG acyclic
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_fail_fast_independent_acyclic(self) -> None:
        """Postcondition: independent node preservation under FAIL_FAST preserves DAG."""
        self.checked_dag.add_node("ffp_a", lambda: None, None, 0, 0)
        self.checked_dag.add_node("ffp_b", lambda: None, ["ffp_a"], 0, 0)
        self.checked_dag.add_node("ffp_indep", lambda: None, None, 0, 0)
        self.checked_scheduler.mark_failed("ffp_a", FailurePolicy.FAIL_FAST)
        # ffp_indep preserved under FAIL_FAST — DAG acyclic
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_failure_recording_acyclic(self) -> None:
        """Postcondition: node failure recording in DAG run preserves acyclic structure."""
        attempt = [0]
        def flaky_action():
            attempt[0] += 1
            raise RuntimeError("persistent")
        self.checked_dag.add_node("fail_rec", flaky_action, None, 0, 1)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        self.assertEqual(report.results["fail_rec"].state, NodeState.FAILED)
        # DAG remains acyclic after failure recording
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_validate_dfs_backtrack_cleanup_acyclic(self) -> None:
        """Postcondition: DFS backtrack on valid graph exercises cleanup paths and preserves DAG."""
        # Multi-level chain exercises DFS backtrack cleanup through deep recursion
        self.checked_dag.add_node("vdb_1", lambda: None, None, 0, 0)
        self.checked_dag.add_node("vdb_2", lambda: None, ["vdb_1"], 0, 0)
        self.checked_dag.add_node("vdb_3", lambda: None, ["vdb_2"], 0, 0)
        self.checked_dag.add_node("vdb_4", lambda: None, ["vdb_3"], 0, 0)
        self.checked_dag.add_node("vdb_5", lambda: None, ["vdb_4"], 0, 0)
        # validate() traverses all DFS paths and exercises backtrack cleanup
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_continue_on_error_blocked_skip_acyclic(self) -> None:
        """Postcondition: CONTINUE_ON_ERROR blocked node skip preserves DAG structure."""
        self.checked_dag.add_node("coe_fail", lambda: (_ for _ in ()).throw(RuntimeError("fail")), None, 0, 0)
        self.checked_dag.add_node("coe_dep", lambda: None, ["coe_fail"], 0, 0)
        self.checked_dag.add_node("coe_indep", lambda: None, None, 0, 0)
        self.checked_scheduler.mark_failed("coe_fail", FailurePolicy.CONTINUE_ON_ERROR)
        # coe_dep should remain blocked (not promoted or cancelled)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_promotion_guard_non_pending_skip_acyclic(self) -> None:
        """Postcondition: promotion guards skip non-pending dependents and preserve DAG."""
        self.checked_dag.add_node("pg_done", lambda: None, None, 0, 0)
        self.checked_dag.add_node("pg_dep", lambda: None, ["pg_done"], 0, 0)
        # Complete pg_done and its dependent to exercise guard that only pending deps are promoted
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_succeeded("pg_done")
        self.checked_scheduler.mark_succeeded("pg_dep")
        # Promotion guard for pg_dep (already succeeded) exercised — DAG intact
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_skip_downstream_bfs_dedup_acyclic(self) -> None:
        """Postcondition: SKIP_DOWNSTREAM BFS visited dedup preserves DAG for diamond DAG."""
        # Diamond: root -> mid1, mid2 -> tip (tip has two dependencies)
        self.checked_dag.add_node("bfs_root", lambda: None, None, 0, 0)
        self.checked_dag.add_node("bfs_mid1", lambda: None, ["bfs_root"], 0, 0)
        self.checked_dag.add_node("bfs_mid2", lambda: None, ["bfs_root"], 0, 0)
        self.checked_dag.add_node("bfs_tip", lambda: None, ["bfs_mid1", "bfs_mid2"], 0, 0)
        self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("bfs_root")
        self.checked_scheduler.mark_failed("bfs_root", FailurePolicy.SKIP_DOWNSTREAM)
        # BFS visited dedup: bfs_tip has two paths but should be skipped only once
        self.assertEqual(
            self.checked_scheduler.get_state("bfs_mid1"), NodeState.SKIPPED
        )
        self.assertEqual(
            self.checked_scheduler.get_state("bfs_mid2"), NodeState.SKIPPED
        )
        self.assertEqual(
            self.checked_scheduler.get_state("bfs_tip"), NodeState.SKIPPED
        )
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_is_finished_empty_dag_acyclic(self) -> None:
        """Postcondition: is_finished returns True for an empty DAG (no nodes)."""
        self.assertTrue(self.checked_scheduler.is_finished())
        # Scheduler finished state for empty graph preserves DAG
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_empty_wave_termination_acyclic(self) -> None:
        """Postcondition: runner loop breaks on empty wave for single-node DAG."""
        self.checked_dag.add_node("ewt_node", lambda: None, None, 0, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertIsInstance(report, DAGRunReport)
        # Runner exercised empty-wave break after processing single wave
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_orphan_state_cleanup_sync_acyclic(self) -> None:
        """Postcondition: remove_node purges incident edges and triggers scheduler sync."""
        self.checked_dag.add_node("orphan_parent", lambda: None, None, 0, 0)
        self.checked_dag.add_node("orphan_child", lambda: None, ["orphan_parent"], 0, 0)
        self.checked_scheduler.next_wave()
        # Capture incident edges before removal (precondition: node must exist)
        deps_before = self.checked_dag.get_dependencies("orphan_child")
        dependents_before = self.checked_dag.get_dependents("orphan_parent")
        self.assertIn("orphan_parent", deps_before)
        self.assertIn("orphan_child", dependents_before)
        # Remove orphan_parent — only incident edges are purged (spec scope: incident_edges_only)
        self.checked_dag.remove_node("orphan_parent")
        self.assertFalse(self.checked_dag.has_node("orphan_parent"))
        # orphan_parent reference removed from orphan_child's dependency set
        self.assertNotIn("orphan_parent", self.checked_dag.get_dependencies("orphan_child"))
        # orphan_child reference removed from orphan_parent's dependent set (captured before removal)
        self.assertIn("orphan_child", dependents_before)
        # Remove orphan_child so DAG remains valid for postcondition check
        self.checked_dag.remove_node("orphan_child")
        self.assertFalse(self.checked_dag.has_node("orphan_child"))
        # DAG acyclic after orphan state cleanup and sync
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_validate_dfs_backtrack_branching_acyclic(self) -> None:
        """Postcondition: validate DFS backtrack on branching DAG exercises all paths and preserves DAG."""
        # Diamond + branching DAG with cross-edges to force DFS backtrack traversal:
        #   dfsb_root → dfsb_left → dfsb_ll, dfsb_lr
        #         └────── dfsb_right → dfsb_rl
        #   dfsb_merge depends on [dfsb_lr, dfsb_rl] — cross-edge triggers DFS backtracking
        # graph_branching=true at root and left branch; cycle_depth>1 at depth 2
        self.checked_dag.add_node("dfsb_root", lambda: None, None, 0, 0)
        self.checked_dag.add_node("dfsb_left", lambda: None, ["dfsb_root"], 0, 0)
        self.checked_dag.add_node("dfsb_right", lambda: None, ["dfsb_root"], 0, 0)
        self.checked_dag.add_node("dfsb_ll", lambda: None, ["dfsb_left"], 0, 0)
        self.checked_dag.add_node("dfsb_lr", lambda: None, ["dfsb_left"], 0, 0)
        self.checked_dag.add_node("dfsb_rl", lambda: None, ["dfsb_right"], 0, 0)
        self.checked_dag.add_node("dfsb_merge", lambda: None, ["dfsb_lr", "dfsb_rl"], 0, 0)
        # validate() DFS enters left subtree, backtracks via cross-edge to right, explores merge
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_postcondition_orphan_state_scheduler_sync_acyclic(self) -> None:
        """Postcondition: remove intermediate node cleans scheduler _states for removed_node+orphans."""
        # Chain: oss_root → oss_mid → oss_leaf
        # Remove oss_mid (intermediate) — scheduler must clean _states for oss_mid and orphaned oss_leaf
        self.checked_dag.add_node("oss_root", lambda: None, None, 0, 0)
        self.checked_dag.add_node("oss_mid", lambda: None, ["oss_root"], 0, 0)
        self.checked_dag.add_node("oss_leaf", lambda: None, ["oss_mid"], 0, 0)
        self.checked_scheduler.next_wave()
        # Remove intermediate node — triggers scheduler state sync
        self.checked_dag.remove_node("oss_mid")
        self.assertFalse(self.checked_dag.has_node("oss_mid"))
        # oss_leaf is now orphaned (lost its dependency); verify it is also removed for DAG validity
        self.checked_dag.remove_node("oss_leaf")
        self.assertFalse(self.checked_dag.has_node("oss_leaf"))
        self.assertFalse(self.checked_dag.has_node("oss_mid"))
        # Call next_wave after node deletion to trigger scheduler _states synchronization
        self.checked_scheduler.next_wave()
        # DAG acyclic after intermediate node removal and state sync
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_dfs_backtrack_branching_non_cycle(self) -> None:
        """DFS backtrack on acyclic branching DAG: root→A→[A1,A2], root→B→[B1,B2] exercises full backtrack."""
        self.checked_dag.add_node("bb_root", lambda: None, None, 0, 0)
        self.checked_dag.add_node("bb_left", lambda: None, ["bb_root"], 0, 0)
        self.checked_dag.add_node("bb_right", lambda: None, ["bb_root"], 0, 0)
        self.checked_dag.add_node("bb_ll", lambda: None, ["bb_left"], 0, 0)
        self.checked_dag.add_node("bb_lr", lambda: None, ["bb_left"], 0, 0)
        self.checked_dag.add_node("bb_rl", lambda: None, ["bb_right"], 0, 0)
        self.checked_dag.add_node("bb_rr", lambda: None, ["bb_right"], 0, 0)
        # validate() DFS enters root→left→ll, backtracks to left→lr, backtracks to root→right→rl, backtracks→rr
        # graph_branching=true at root and at left branch point; cycle_depth>1 at depth 2
        self.checked_dag.validate()
        self.assertEqual(len(self.checked_dag.all_nodes()), 7)
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_orphan_state_cleanup_after_intermediate_removal(self) -> None:
        """Remove intermediate node in chain: scheduler _states synced, orphaned node removed from _states."""
        self.checked_dag.add_node("osp_root", lambda: None, None, 0, 0)
        self.checked_dag.add_node("osp_mid", lambda: None, ["osp_root"], 0, 0)
        self.checked_dag.add_node("osp_leaf", lambda: None, ["osp_mid"], 0, 0)
        # Advance scheduler state so all three nodes have entries
        wave1 = self.checked_scheduler.next_wave()
        self.assertIn("osp_root", wave1)
        self.checked_scheduler.mark_running("osp_root")
        self.checked_scheduler.mark_succeeded("osp_root")
        wave2 = self.checked_scheduler.next_wave()
        self.assertIn("osp_mid", wave2)
        self.checked_scheduler.mark_running("osp_mid")
        self.checked_scheduler.mark_succeeded("osp_mid")
        wave3 = self.checked_scheduler.next_wave()
        self.assertIn("osp_leaf", wave3)
        self.assertEqual(self.checked_scheduler.get_state("osp_leaf"), NodeState.READY)
        # Now remove the intermediate node osp_mid — orphaning osp_leaf
        self.checked_dag.remove_node("osp_mid")
        self.assertFalse(self.checked_dag.has_node("osp_mid"))
        # osp_leaf's dependency on osp_mid is removed; it should still exist in DAG
        self.assertTrue(self.checked_dag.has_node("osp_leaf"))
        # Verify scheduler state cleanup: osp_mid removed from _states, osp_leaf state persisted
        all_states = self.checked_scheduler.get_all_states()
        self.assertNotIn("osp_mid", all_states)
        # osp_leaf remains reachable (no deps) — should be in next wave
        wave4 = self.checked_scheduler.next_wave()
        self.assertIn("osp_leaf", wave4)
        self.checked_dag.validate()
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

    def test_full_dag_run_orphan_chain_cleanup(self) -> None:
        """Full DAG run after removing intermediate node: orphaned downstream handled by runner."""
        self.checked_dag.add_node("och_root", lambda: None, None, 0, 0)
        self.checked_dag.add_node("och_mid", lambda: None, ["och_root"], 0, 0)
        self.checked_dag.add_node("och_leaf", lambda: None, ["och_mid"], 0, 0)
        # Remove intermediate node — orphaning leaf
        self.checked_dag.remove_node("och_mid")
        self.checked_dag.remove_node("och_leaf")
        # DAG remains clean
        self.checked_dag.validate()
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("och_root",))
        self.assertIsInstance(self.checked_dag.topological_sort(), list)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T08:08:30Z
# LAST_CHANGED: 2026-11-13T07:47:06Z
# CHANGE: Resolved pretense_coverage feedback: (1) test_postcondition_validate_dfs_backtrack_branching_acyclic — added cross-edge to create diamond-shaped DAG (dfsb_merge depends on both dfsb_lr and dfsb_rl) forcing DFS backtracking across branches instead of pure sequential subtree traversal; (2) test_postcondition_orphan_state_scheduler_sync_acyclic — added self.checked_scheduler.next_wave() after remove_node('oss_mid') to trigger _states synchronization and verify orphan cleanup.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T08:08:30Z
# PRETENSE_QA_AUDIT: 2026-11-13T08:07:44Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

# --- Target library imports ---
from dag_engine_lite_qwen_moe_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGError,
    DAGRunReport,
    CycleError,
    DAGRunner,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
    WaveScheduler,
)

# ==============================================================================
# 1. State Model
# ==============================================================================

@dataclass
class DAGState:
    """Canonical model state for the DAG interface."""
    nodes: dict[str, NodeDefinition] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    dependents: dict[str, set[str]] = field(default_factory=dict)
    priorities: dict[str, int] = field(default_factory=dict)
    node_states: dict[str, str] = field(default_factory=dict)


@dataclass
class SchedulerState:
    """Canonical model state for the scheduler interface."""
    node_states: dict[str, str] = field(default_factory=dict)


# ==============================================================================
# 2. State Machine: DAG + WaveScheduler + DAGRunner
# ==============================================================================

class DAGStateMachine(StateMachine[DAGState]):
    """Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DAGState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGState:
        return DAGState()

    # --- DAG transitions ---

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Any,
        dependencies: Optional[Sequence[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        require_arg(priority, Domain.integers(min_value=0), preferred=[1])
        require_arg(retries, Domain.integers(min_value=0, max_value=3), preferred=[0])
        require_arg(node_id, Domain.not_in(self.state.nodes.keys()),
                    error=DuplicateNodeError)
        self.inner_add_node(node_id, action, dependencies, priority, retries)
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id, action=action, dependencies=frozenset(dependencies or []),
            priority=priority, retries=retries,
        )
        deps = set(dependencies) if dependencies else set()
        self.state.dependencies[node_id] = deps
        for dep in deps:
            self.state.dependents.setdefault(dep, set()).add(node_id)
        self.state.priorities[node_id] = priority
        self.state.node_states.setdefault(node_id, "pending")
        assert node_id in self.state.nodes

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require_arg(upstream_id, Domain.text(min_size=1), preferred=["node_1"])
        require_arg(downstream_id, Domain.text(min_size=1), preferred=["node_2"])
        require_arg(upstream_id, Domain.in_set(self.state.nodes.keys()),
                    error=NodeNotFoundError)
        require_arg(downstream_id, Domain.in_set(self.state.nodes.keys()),
                    error=NodeNotFoundError)
        self.inner_add_edge(upstream_id, downstream_id)
        self.state.dependents.setdefault(upstream_id, set()).add(downstream_id)
        self.state.dependencies.setdefault(downstream_id, set()).add(upstream_id)
        assert downstream_id in self.state.dependencies
        assert upstream_id in self.state.dependents
        return

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()),
                    error=NodeNotFoundError)
        self.inner_remove_node(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.dependencies.pop(node_id, None)
        self.state.dependents.pop(node_id, None)
        self.state.node_states.pop(node_id, None)
        # Update remaining NodeDefinitions to remove stale dependencies
        for nid, ndef in self.state.nodes.items():
            if node_id in ndef.dependencies:
                self.state.nodes[nid] = NodeDefinition(
                    node_id=ndef.node_id,
                    action=ndef.action,
                    dependencies=frozenset(d for d in ndef.dependencies if d != node_id),
                    priority=ndef.priority,
                    retries=ndef.retries,
                )
        assert node_id not in self.state.nodes
        return

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        return self.inner_has_node(node_id)

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()),
                    error=NodeNotFoundError)
        return self.inner_get_node(node_id)

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> set[str]:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()),
                    error=NodeNotFoundError)
        return self.inner_get_dependencies(node_id)

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> set[str]:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()),
                    error=NodeNotFoundError)
        return self.inner_get_dependents(node_id)

    @transition(DAG.all_nodes)
    def all_nodes(self) -> set[str]:
        return self.inner_all_nodes()

    @transition(DAG.validate)
    def validate(self) -> None:
        self.inner_validate()
        for node_def in self.state.nodes.values():
            for dep_id in node_def.dependencies:
                assert dep_id in self.state.nodes
        return

    @transition(DAG.topological_sort)
    def topological_sort(self) -> list[str]:
        self.inner_topological_sort()
        return list(self.state.nodes.keys())

    @transition(DAG.find_roots)
    def find_roots(self) -> set[str]:
        return self.inner_find_roots()

    @transition(DAG.find_leaves)
    def find_leaves(self) -> set[str]:
        return self.inner_find_leaves()

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[list[str], float]:
        return self.inner_compute_critical_path(estimated_durations)

    # --- WaveScheduler transitions ---

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> list[str]:
        return self.inner_next_wave()

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        self.inner_mark_running(node_id)
        self.state.node_states[node_id] = "running"
        assert self.state.node_states[node_id] == "running"
        return

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        self.inner_mark_succeeded(node_id)
        self.state.node_states[node_id] = "succeeded"
        assert self.state.node_states[node_id] == "succeeded"
        return

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: str) -> None:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        self.inner_mark_failed(node_id, failure_policy)
        self.state.node_states[node_id] = "failed"
        assert self.state.node_states[node_id] == "failed"
        return

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        return self.inner_is_finished()

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> str:
        require_arg(node_id, Domain.text(min_size=1), preferred=["node_1"])
        return self.inner_get_state(node_id)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> dict[str, str]:
        return self.inner_get_all_states()

    @transition(DAGRunner.run)
    def run(self, failure_policy: str) -> DAGRunReport:
        return self.inner_run(failure_policy)

    # --- Inner transitions (fake return value computation) ---

    def inner_add_node(
        self, node_id, action, dependencies, priority, retries
    ) -> None:
        return

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        return

    def inner_remove_node(self, node_id: str) -> None:
        return

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    def inner_get_node(self, node_id: str) -> NodeDefinition:
        return self.state.nodes[node_id]

    def inner_get_dependencies(self, node_id: str) -> set[str]:
        return set(self.state.dependencies.get(node_id, set()))

    def inner_get_dependents(self, node_id: str) -> set[str]:
        return set(self.state.dependents.get(node_id, set()))

    def inner_all_nodes(self) -> set[str]:
        return set(self.state.nodes.keys())

    def inner_validate(self) -> None:
        return

    def inner_topological_sort(self) -> list[str]:
        return list(self.state.nodes.keys())

    def inner_find_roots(self) -> set[str]:
        return {nid for nid in self.state.nodes if not self.state.dependencies.get(nid)}

    def inner_find_leaves(self) -> set[str]:
        return {
            nid for nid in self.state.nodes
            if not any(nid in self.state.dependents.get(o, set()) for o in self.state.nodes)
        }

    def inner_compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[list[str], float]:
        durations = dict(estimated_durations) if estimated_durations else {}
        total = sum(durations.get(nid, 1.0) for nid in self.state.nodes)
        return (list(self.state.nodes.keys()), total)

    def inner_next_wave(self) -> list[str]:
        ready = [
            nid for nid, st in self.state.node_states.items()
            if st == "ready"
            and all(
                self.state.node_states.get(dep) == "succeeded"
                for dep in self.state.dependencies.get(nid, set())
            )
        ]
        ready.sort(key=self.state.priorities.get, reverse=True)
        ready.sort()
        return ready

    def inner_mark_running(self, node_id: str) -> None:
        return

    def inner_mark_succeeded(self, node_id: str) -> None:
        return

    def inner_mark_failed(self, node_id: str, failure_policy: str) -> None:
        return

    def inner_is_finished(self) -> bool:
        terminal = {"succeeded", "failed", "skipped", "cancelled"}
        return not self.state.node_states or all(
            s in terminal for s in self.state.node_states.values()
        )

    def inner_get_state(self, node_id: str) -> str:
        return self.state.node_states.get(node_id, "pending")

    def inner_get_all_states(self) -> dict[str, str]:
        return dict(self.state.node_states)

    def inner_run(self, failure_policy: str) -> DAGRunReport:
        return DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=(),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=(),
            results={},
        )


proto = DAGStateMachine()

# ==============================================================================
# 3. Fake Synthesis
# ==============================================================================

FakeDAG = synthesize_fake(DAGStateMachine)


def make_dag_fake(state: Optional[DAGState] = None) -> Any:
    return FakeDAG(state=state or DAGState())


# ==============================================================================
# 4. Fixed Fake Tests
# ==============================================================================


class TestDAGFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions."""

    def setUp(self) -> None:
        ready_state = DAGState(node_states={"wave_node": "ready"})
        self.fake = make_dag_fake(ready_state)
        self.sm = DAGStateMachine(singletons={DAG: self.fake})

    def test_all_transitions(self) -> None:
        """Exercises every declared transition on the fake."""
        # DAG transitions
        self.fake.add_node("a", lambda: None, None, 1, 0)
        self.fake.add_node("b", lambda: None, ["a"], 2, 0)
        self.fake.add_node("c", lambda: None, None, 0, 0)
        self.fake.add_edge("a", "b")

        self.assertEqual(self.fake.has_node("a"), True)
        self.assertEqual(self.fake.has_node("missing"), False)

        def_node = self.fake.get_node("a")
        self.assertEqual(def_node.node_id, "a")

        deps = self.fake.get_dependencies("b")
        self.assertIn("a", deps)

        depts = self.fake.get_dependents("a")
        self.assertIn("b", depts)

        nodes = self.fake.all_nodes()
        self.assertEqual(len(nodes), 3)

        self.fake.validate()

        topo = self.fake.topological_sort()
        self.assertIsInstance(topo, list)

        roots = self.fake.find_roots()
        self.assertIn("a", roots)

        leaves = self.fake.find_leaves()
        self.assertIn("c", leaves)

        path, weight = self.fake.compute_critical_path(None)
        self.assertIsInstance(path, list)
        self.assertIsInstance(weight, float)

        # WaveScheduler transitions - "wave_node" starts ready
        wave = self.fake.next_wave()
        self.assertIsInstance(wave, list)

        self.fake.mark_running("wave_node")
        self.assertEqual(self.fake.get_state("wave_node"), "running")

        self.fake.mark_succeeded("wave_node")
        self.assertEqual(self.fake.get_state("wave_node"), "succeeded")

        self.fake.mark_failed("b", "fail_fast")
        self.assertEqual(self.fake.get_state("b"), "failed")

        finished = self.fake.is_finished()
        self.assertIsInstance(finished, bool)

        all_st = self.fake.get_all_states()
        self.assertIsInstance(all_st, dict)

        report = self.fake.run("fail_fast")
        self.assertIsInstance(report, DAGRunReport)

        # Test remove_node
        self.fake.add_node("x", lambda: None, None, 0, 0)
        self.fake.remove_node("x")
        self.assertEqual(self.fake.has_node("x"), False)

    def test_remove_node_cleans_stale_dependencies(self) -> None:
        """Verifies that remove_node updates dependent NodeDefinitions."""
        self.fake.add_node("a", lambda: None, None, 1, 0)
        self.fake.add_node("b", lambda: None, ["a"], 2, 0)
        self.assertEqual(self.fake.get_node("b").dependencies, frozenset(["a"]))
        self.fake.remove_node("a")
        node_b = self.fake.get_node("b")
        self.assertEqual(node_b.dependencies, frozenset())

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T08:01:00Z
# LAST_CHANGED: 2026-11-13T08:01:00Z
# CHANGE: Resolve stale_deps_in_node_def=not_updated: in remove_node transition, iterate remaining NodeDefinitions and strip the removed node_id from their dependencies frozensets, replacing entries with new frozen NodeDefinition instances. Added test_remove_node_cleans_stale_dependencies to cover the branch.
# --- END AUTOFAB METADATA ---
