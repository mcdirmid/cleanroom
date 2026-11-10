"""Unit tests for dag_engine_lite_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeNotFoundError,
    NodeState,
)
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)


class DagEngineLiteImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_registers_definition(self) -> None:
        """POSTCONDITION add_node.register_definition: the definition is registered."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 3, 2)
            definition = dag.get_node("a")
            self.assertEqual(definition.node_id, "a")
            self.assertIs(definition.action, action)
            self.assertEqual(definition.dependencies, frozenset())
            self.assertEqual(definition.priority, 3)
            self.assertEqual(definition.retries, 2)
            self.assertEqual(dag.all_nodes(), {"a"})

    def test_add_node_with_dependencies_creates_directed_edges(self) -> None:
        """POSTCONDITION add_node.directed_dependencies: dependency edges are added."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(dag.get_dependencies("b"), {"a"})
            self.assertEqual(dag.get_dependents("a"), {"b"})
            self.assertEqual(dag.get_dependencies("a"), set())
            self.assertEqual(dag.get_dependents("b"), set())

    def test_add_node_defers_missing_dependency_check(self) -> None:
        """POSTCONDITION add_node.defer_dependency_checks: missing dependencies surface at validate()."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("b", action, ["ghost"], 0, 0)
            self.assertTrue(dag.has_node("b"))
            with self.assertRaises(NodeNotFoundError) as error:
                dag.validate()
            self.assertEqual(error.exception.node_id, "ghost")

    def test_add_node_duplicate_raises_duplicate_node_error(self) -> None:
        """PRECONDITION add_node.duplicate_node: re-adding an identifier raises DuplicateNodeError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            with self.assertRaises(DuplicateNodeError) as error:
                dag.add_node("a", action, None, 0, 0)
            self.assertEqual(error.exception.node_id, "a")

    def test_add_edge_establishes_directed_dependency(self) -> None:
        """POSTCONDITION add_edge.directed_edge: downstream depends on upstream."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, None, 0, 0)
            dag.add_edge("a", "b")
            self.assertEqual(dag.get_dependencies("b"), {"a"})
            self.assertEqual(dag.get_dependents("a"), {"b"})

    def test_add_edge_missing_nodes_raise_node_not_found(self) -> None:
        """PRECONDITION add_edge.nodes_must_exist: unknown endpoints raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, None, 0, 0)
            with self.assertRaises(NodeNotFoundError) as upstream_error:
                dag.add_edge("ghost", "b")
            self.assertEqual(upstream_error.exception.node_id, "ghost")
            with self.assertRaises(NodeNotFoundError) as downstream_error:
                dag.add_edge("a", "ghost")
            self.assertEqual(downstream_error.exception.node_id, "ghost")

    def test_remove_node_purges_incident_edges(self) -> None:
        """POSTCONDITION remove_node.purge_incident_edges: node and incident edges are removed."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["b"], 0, 0)
            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertEqual(dag.all_nodes(), {"a", "c"})
            self.assertEqual(dag.get_dependencies("c"), set())
            self.assertEqual(dag.get_dependents("a"), set())

    def test_remove_node_missing_raises_node_not_found(self) -> None:
        """PRECONDITION remove_node.node_must_exist: unknown identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as error:
                dag.remove_node("ghost")
            self.assertEqual(error.exception.node_id, "ghost")

    def test_remove_node_purges_scheduler_state(self) -> None:
        """POSTCONDITION remove_node.purge_scheduler_state: scheduler tracking drops removed nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            self.assertEqual(set(scheduler.get_all_states()), {"a", "b"})
            dag.remove_node("b")
            self.assertEqual(set(scheduler.get_all_states()), {"a"})
            with self.assertRaises(NodeNotFoundError):
                scheduler.get_state("b")

    def test_has_node_reports_membership(self) -> None:
        """Operation has_node reports registered membership."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            self.assertFalse(dag.has_node("a"))
            dag.add_node("a", action, None, 0, 0)
            self.assertTrue(dag.has_node("a"))
            self.assertFalse(dag.has_node("b"))

    def test_get_node_missing_raises_node_not_found(self) -> None:
        """PRECONDITION get_node.node_must_exist: unknown identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as error:
                dag.get_node("ghost")
            self.assertEqual(error.exception.node_id, "ghost")

    def test_get_dependencies_missing_raises_node_not_found(self) -> None:
        """PRECONDITION get_dependencies.node_must_exist: unknown identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as error:
                dag.get_dependencies("ghost")
            self.assertEqual(error.exception.node_id, "ghost")

    def test_get_dependents_missing_raises_node_not_found(self) -> None:
        """PRECONDITION get_dependents.node_must_exist: unknown identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(NodeNotFoundError) as error:
                dag.get_dependents("ghost")
            self.assertEqual(error.exception.node_id, "ghost")

    def test_find_roots_and_leaves(self) -> None:
        """Operations find_roots and find_leaves partition the graph boundary."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["b"], 0, 0)
            dag.add_node("d", action, None, 0, 0)
            self.assertEqual(dag.find_roots(), {"a", "d"})
            self.assertEqual(dag.find_leaves(), {"c", "d"})
            self.assertEqual(dag.all_nodes(), {"a", "b", "c", "d"})

    def test_empty_graph_queries(self) -> None:
        """Empty graph queries return empty collections and validate without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())
            self.assertEqual(dag.find_roots(), set())
            self.assertEqual(dag.find_leaves(), set())
            self.assertEqual(dag.topological_sort(), [])
            dag.validate()

    def test_validate_accepts_valid_graph(self) -> None:
        """POSTCONDITION validate.complete_valid: an acyclic complete graph validates silently."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["a", "b"], 0, 0)
            dag.validate()
            self.assertEqual(dag.all_nodes(), {"a", "b", "c"})

    def test_validate_detects_cycle(self) -> None:
        """PRECONDITION validate.acyclic_graph: cycles raise CycleError with the cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, None, 0, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as error:
                dag.validate()
            self.assertEqual(set(error.exception.cycle), {"a", "b"})

    def test_topological_sort_dependency_order_and_tie_breaking(self) -> None:
        """POSTCONDITIONS topological_sort.dependency_order and tie_breaking: priorities then identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("r", action, None, 0, 0)
            dag.add_node("a", action, ["r"], 0, 0)
            dag.add_node("b", action, ["r"], 5, 0)
            dag.add_node("c", action, ["r"], 5, 0)
            order = dag.topological_sort()
            self.assertEqual(order, ["r", "b", "c", "a"])
            positions = {node: index for index, node in enumerate(order)}
            for node in order:
                for dependency in dag.get_dependencies(node):
                    self.assertLess(positions[dependency], positions[node])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """PRECONDITION topological_sort.acyclic_graph: cycles raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, None, 0, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as error:
                dag.topological_sort()
            self.assertEqual(set(error.exception.cycle), {"a", "b"})

    def test_compute_critical_path_weighted(self) -> None:
        """POSTCONDITIONS critical_path.longest_path and cumulative_weight: weighted longest path."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["a"], 0, 0)
            dag.add_node("d", action, ["b", "c"], 0, 0)
            path, total = dag.compute_critical_path(
                {"a": 1.0, "b": 5.0, "c": 2.0, "d": 1.5}
            )
            self.assertEqual(path, ["a", "b", "d"])
            self.assertEqual(total, 7.5)

    def test_compute_critical_path_default_durations(self) -> None:
        """POSTCONDITION critical_path.cumulative_weight: omitted durations default to one per node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["b"], 0, 0)
            path, total = dag.compute_critical_path(None)
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(total, 3.0)

    def test_next_wave_returns_ready_roots_in_priority_order(self) -> None:
        """POSTCONDITIONS next_wave.ready_nodes and priority_order: roots ordered by priority then identifier."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("b", action, None, 1, 0)
            dag.add_node("a", action, None, 5, 0)
            dag.add_node("c", action, None, 5, 0)
            self.assertEqual(scheduler.next_wave(), ["a", "c", "b"])
            self.assertEqual(scheduler.get_state("a"), NodeState.READY)
            self.assertEqual(scheduler.get_state("b"), NodeState.READY)

    def test_next_wave_empty_when_no_ready_nodes(self) -> None:
        """POSTCONDITION next_wave.empty_when_no_ready: no ready nodes yields an empty list."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """POSTCONDITION mark_running.state_transition: the node becomes RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents_after_all_upstreams_succeed(self) -> None:
        """POSTCONDITIONS mark_succeeded.state_transition and promote_dependents: unlock after all upstreams."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, None, 0, 0)
            dag.add_node("d", action, ["a", "b"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a", "b"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("d"), NodeState.PENDING)
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertEqual(scheduler.get_state("b"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("d"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["d"])

    def test_mark_failed_fail_fast_cancels_pending(self) -> None:
        """POSTCONDITIONS mark_failed.state_transition and fail_fast: pending nodes become CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["b"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("c"), NodeState.CANCELLED)

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """POSTCONDITION mark_failed.skip_downstream: transitive dependents become SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["b"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)

    def test_mark_failed_continue_on_error_skips_blocked_and_keeps_independent(self) -> None:
        """POSTCONDITION mark_failed.continue_on_error: blocked dependents skipped, independents still ready."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 10, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a", "c"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["c"])

    def test_is_finished_empty_dag(self) -> None:
        """POSTCONDITION is_finished.empty_dag: an empty DAG is finished."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_while_nodes_are_eligible(self) -> None:
        """POSTCONDITION is_finished.non_terminal_remaining: eligible nodes keep the run unfinished."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_after_all_nodes_terminal(self) -> None:
        """POSTCONDITION is_finished.all_terminal: terminal nodes finish the run."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.next_wave(), ["b"])
            scheduler.mark_running("b")
            scheduler.mark_succeeded("b")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_true_when_remaining_nodes_are_blocked(self) -> None:
        """POSTCONDITION is_finished.blocked_by_failure: blocked remainders finish the run."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_get_state_missing_raises_node_not_found(self) -> None:
        """PRECONDITION get_state.node_must_exist: unknown identifiers raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises(NodeNotFoundError) as error:
                scheduler.get_state("ghost")
            self.assertEqual(error.exception.node_id, "ghost")

    def test_get_all_states_lists_registered_nodes_only(self) -> None:
        """get_all_states reflects every registered node and filters removed nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(
                dict(scheduler.get_all_states()),
                {"a": NodeState.READY, "b": NodeState.PENDING},
            )
            dag.remove_node("b")
            self.assertEqual(set(scheduler.get_all_states()), {"a"})

    def test_run_executes_chain_and_reports_results(self) -> None:
        """POSTCONDITIONS run.sequential_waves and consolidated_report: chain executes in order."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            scheduler = scope.get_singleton(WaveScheduler)
            executed: list[str] = []

            def action_a() -> int:
                executed.append("a")
                return 1

            def action_b() -> int:
                executed.append("b")
                return 2

            def action_c() -> int:
                executed.append("c")
                return 3

            dag.add_node("a", action_a, None, 0, 0)
            dag.add_node("b", action_b, ["a"], 0, 0)
            dag.add_node("c", action_c, ["b"], 0, 0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(executed, ["a", "b", "c"])
            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(set(report.results), {"a", "b", "c"})
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["a"].value, 1)
            self.assertIsNone(report.results["b"].error)
            self.assertEqual(report.results["c"].value, 3)
            self.assertGreaterEqual(report.results["a"].duration_seconds, 0.0)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("a", "b", "c"))
            self.assertTrue(scheduler.is_finished())
            self.assertEqual(scheduler.get_state("c"), NodeState.SUCCEEDED)

    def test_run_retries_failed_action_then_succeeds(self) -> None:
        """POSTCONDITION run.retry_failures: retries are attempted before success."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            attempts: list[int] = []

            def flaky() -> str:
                attempts.append(len(attempts))
                if len(attempts) <= 2:
                    raise RuntimeError("transient")
                return "ok"

            dag.add_node("flaky", flaky, None, 0, 2)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(report.results["flaky"].state, NodeState.SUCCEEDED)
            self.assertEqual(report.results["flaky"].value, "ok")
            self.assertEqual(report.results["flaky"].retries_attempted, 2)
            self.assertIsNone(report.results["flaky"].error)
            self.assertEqual(set(report.succeeded_nodes), {"flaky"})

    def test_run_retries_exhausted_records_failure(self) -> None:
        """POSTCONDITION run.retry_failures: exhausted retries record a FAILED result."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            calls: list[int] = []

            def boom() -> int:
                calls.append(len(calls))
                raise ValueError("boom")

            dag.add_node("boom", boom, None, 0, 1)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            result = report.results["boom"]
            self.assertEqual(len(calls), 2)
            self.assertEqual(result.state, NodeState.FAILED)
            self.assertEqual(result.retries_attempted, 1)
            self.assertIsInstance(result.error, ValueError)
            self.assertEqual(set(report.failed_nodes), {"boom"})
            self.assertEqual(report.succeeded_nodes, ())

    def test_run_fail_fast_cancels_remaining_nodes(self) -> None:
        """POSTCONDITION run.apply_failure_policy: FAIL_FAST stops waves and cancels remaining nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            executed: list[str] = []

            def action_a() -> int:
                executed.append("a")
                raise RuntimeError("boom")

            def action_b() -> int:
                executed.append("b")
                return 2

            def action_c() -> int:
                executed.append("c")
                return 3

            dag.add_node("a", action_a, None, 0, 0)
            dag.add_node("b", action_b, ["a"], 0, 0)
            dag.add_node("c", action_c, ["b"], 0, 0)
            report = runner.run(FailurePolicy.FAIL_FAST)
            self.assertEqual(executed, ["a"])
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.cancelled_nodes), {"b", "c"})
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.results["a"].state, NodeState.FAILED)
            self.assertEqual(report.results["b"].state, NodeState.CANCELLED)
            self.assertEqual(report.results["c"].state, NodeState.CANCELLED)

    def test_run_skip_downstream_skips_transitive_dependents(self) -> None:
        """POSTCONDITION run.apply_failure_policy: SKIP_DOWNSTREAM skips transitive dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            executed: list[str] = []

            def action_a() -> int:
                executed.append("a")
                raise RuntimeError("boom")

            def action_b() -> int:
                executed.append("b")
                return 2

            def action_c() -> int:
                executed.append("c")
                return 3

            dag.add_node("a", action_a, None, 0, 0)
            dag.add_node("b", action_b, ["a"], 0, 0)
            dag.add_node("c", action_c, ["b"], 0, 0)
            report = runner.run(FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(executed, ["a"])
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.skipped_nodes), {"b", "c"})
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["b"].state, NodeState.SKIPPED)
            self.assertEqual(report.results["c"].state, NodeState.SKIPPED)

    def test_run_continue_on_error_executes_independent_nodes(self) -> None:
        """POSTCONDITION run.apply_failure_policy: CONTINUE_ON_ERROR still runs unblocked nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            executed: list[str] = []

            def action_a() -> int:
                executed.append("a")
                raise RuntimeError("boom")

            def action_b() -> int:
                executed.append("b")
                return 2

            def action_c() -> int:
                executed.append("c")
                return 7

            dag.add_node("a", action_a, None, 10, 0)
            dag.add_node("b", action_b, ["a"], 0, 0)
            dag.add_node("c", action_c, None, 0, 0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(executed, ["a", "c"])
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.succeeded_nodes), {"c"})
            self.assertEqual(set(report.skipped_nodes), {"b"})
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["c"].value, 7)
            self.assertEqual(report.results["b"].state, NodeState.SKIPPED)

    def test_run_missing_dependency_raises_node_not_found(self) -> None:
        """PRECONDITION run.dependencies_exist: missing dependencies raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def action() -> int:
                return 1

            dag.add_node("x", action, ["ghost"], 0, 0)
            with self.assertRaises(NodeNotFoundError) as error:
                runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(error.exception.node_id, "ghost")

    def test_run_cycle_raises_cycle_error(self) -> None:
        """PRECONDITION run.acyclic_graph: cyclic graphs raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, None, 0, 0)
            dag.add_edge("a", "b")
            dag.add_edge("b", "a")
            with self.assertRaises(CycleError) as error:
                runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(set(error.exception.cycle), {"a", "b"})

    def test_compute_critical_path_empty_graph(self) -> None:
        """POSTCONDITION critical_path.longest_path: an empty graph yields an empty path and zero weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, total = dag.compute_critical_path(None)
            self.assertEqual(path, [])
            self.assertEqual(total, 0.0)

    def test_is_finished_false_while_node_still_running(self) -> None:
        """POSTCONDITION is_finished.non_terminal_remaining: a RUNNING node keeps the run unfinished."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.RUNNING)
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_when_remainder_blocked_by_failed_dependency(self) -> None:
        """POSTCONDITION is_finished.blocked_by_failure: a blocked non-terminal remainder finishes the run."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.get_state("b"), NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_mark_succeeded_preserves_non_pending_dependent_state(self) -> None:
        """POSTCONDITION mark_succeeded.promote_dependents: non-PENDING dependents are left unchanged."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("c", action, ["a"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("c"), NodeState.READY)
            scheduler.mark_running("c")
            self.assertEqual(scheduler.get_state("c"), NodeState.RUNNING)
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("a"), NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("c"), NodeState.RUNNING)

    def test_next_wave_initializes_dynamically_registered_node(self) -> None:
        """POSTCONDITION next_wave.ready_nodes: nodes added after upstream success initialize READY and run."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            dag.add_node("b", action, ["a"], 0, 0)
            self.assertEqual(scheduler.get_state("b"), NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["b"])

    def test_mark_failed_skip_downstream_skips_multiply_reachable_diamond(self) -> None:
        """POSTCONDITION mark_failed.skip_downstream: multiply reachable transitive dependents are skipped."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)

            def action() -> int:
                return 1

            dag.add_node("a", action, None, 0, 0)
            dag.add_node("b", action, ["a"], 0, 0)
            dag.add_node("c", action, ["a"], 0, 0)
            dag.add_node("d", action, ["b", "c"], 0, 0)
            self.assertEqual(scheduler.next_wave(), ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), NodeState.SKIPPED)

    def test_run_halts_on_empty_wave_while_unfinished(self) -> None:
        """POSTCONDITION run.sequential_waves: an empty wave halts the loop with a consolidated report."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            scheduler = scope.get_singleton(WaveScheduler)
            executed: list[str] = []

            def action_a() -> int:
                executed.append("a")
                scheduler.mark_running("b")
                return 1

            def action_b() -> int:
                executed.append("b")
                return 2

            dag.add_node("a", action_a, None, 0, 0)
            dag.add_node("b", action_b, ["a"], 0, 0)
            report = runner.run(FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(executed, ["a"])
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"a"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("b"), NodeState.RUNNING)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:41:09Z
# LAST_CHANGED: 2026-11-09T22:26:12Z
# CHANGE: Add coverage-focused tests for all six reported branches: empty-graph critical path returns ([], 0.0); is_finished RUNNING-node and blocked-remainder judgements; mark_succeeded guard preserving non-PENDING dependents; dynamic node registration initializing READY when upstream already succeeded; diamond SKIP_DOWNSTREAM transitive dependents; and DAGRunner empty-wave halt with a consolidated report.
# COVERAGE_AUDIT: 2026-11-09T22:41:09Z
# QA_AUDIT: 2026-11-09T22:40:47Z
# --- END AUTOFAB METADATA ---
