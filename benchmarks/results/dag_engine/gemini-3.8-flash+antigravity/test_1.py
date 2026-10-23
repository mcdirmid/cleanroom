from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple
import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from benchmarks.parts.dag_engine.lib import dag_engine
from benchmarks.parts.dag_engine.lib.dag_engine_impl import DAG, DAGRunner, WaveScheduler, __initialize__


class DAGTest(unittest.TestCase):
    """Unit tests for the concrete DAG class implementing dag_engine.DAG."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_add_node_default_attributes(self) -> None:
        """WHEN node is registered without optional parameters, MUST use contracted defaults."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task1", action=lambda: 42)

            self.assertTrue(dag.has_node("task1"))
            self.assertIn("task1", dag.all_nodes())
            node_def = dag.get_node("task1")
            self.assertEqual(node_def.node_id, "task1")
            self.assertEqual(node_def.priority, 0)
            self.assertIsNone(node_def.timeout_seconds)
            self.assertEqual(node_def.retries, 0)
            self.assertEqual(node_def.dependencies, frozenset())
            self.assertEqual(node_def.action(), 42)

    def test_add_node_custom_attributes(self) -> None:
        """WHEN node is registered with optional parameters, MUST store exact configured attributes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("prereq", action=lambda: 1)
            dag.add_node(
                "custom_task",
                action=lambda: 100,
                dependencies=["prereq"],
                priority=10,
                timeout_seconds=5.0,
                retries=3,
            )

            node_def = dag.get_node("custom_task")
            self.assertEqual(node_def.node_id, "custom_task")
            self.assertEqual(node_def.priority, 10)
            self.assertEqual(node_def.timeout_seconds, 5.0)
            self.assertEqual(node_def.retries, 3)
            self.assertEqual(node_def.dependencies, frozenset(["prereq"]))

    def test_add_node_with_dependencies_creates_directed_edges(self) -> None:
        """WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2)
            dag.add_node("C", action=lambda: 3, dependencies=["A", "B"])

            self.assertEqual(dag.get_dependencies("C"), {"A", "B"})
            self.assertIn("C", dag.get_dependents("A"))
            self.assertIn("C", dag.get_dependents("B"))

    def test_add_edge_success(self) -> None:
        """MUST establish a directed dependency edge from upstream_id to downstream_id."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("source", action=lambda: 1)
            dag.add_node("target", action=lambda: 2)
            dag.add_edge("source", "target")

            self.assertIn("target", dag.get_dependents("source"))
            self.assertIn("source", dag.get_dependencies("target"))

    def test_add_edge_missing_upstream_raises_node_not_found(self) -> None:
        """WHEN upstream_id does not exist, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("target", action=lambda: 1)

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.add_edge("nonexistent", "target")
            self.assertEqual(cm.exception.node_id, "nonexistent")

    def test_add_edge_missing_downstream_raises_node_not_found(self) -> None:
        """WHEN downstream_id does not exist, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("source", action=lambda: 1)

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.add_edge("source", "nonexistent")
            self.assertEqual(cm.exception.node_id, "nonexistent")

    def test_remove_node_success(self) -> None:
        """MUST remove the node and its incident edges."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["B"])

            dag.remove_node("B")

            self.assertFalse(dag.has_node("B"))
            self.assertNotIn("B", dag.all_nodes())
            self.assertNotIn("B", dag.get_dependents("A"))
            self.assertNotIn("B", dag.get_dependencies("C"))

    def test_remove_node_missing_raises_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.remove_node("missing_node")
            self.assertEqual(cm.exception.node_id, "missing_node")

    def test_has_node_membership(self) -> None:
        """MUST return True if node exists, False otherwise."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("present", action=lambda: 1)

            self.assertTrue(dag.has_node("present"))
            self.assertFalse(dag.has_node("absent"))

    def test_get_node_missing_raises_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.get_node("unknown")
            self.assertEqual(cm.exception.node_id, "unknown")

    def test_get_dependencies_missing_raises_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.get_dependencies("unknown")
            self.assertEqual(cm.exception.node_id, "unknown")

    def test_get_dependents_missing_raises_node_not_found(self) -> None:
        """WHEN node_id is absent, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.get_dependents("unknown")
            self.assertEqual(cm.exception.node_id, "unknown")

    def test_all_nodes_empty_and_populated(self) -> None:
        """MUST return set of all registered node identifiers."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.all_nodes(), set())

            dag.add_node("n1", action=lambda: 1)
            dag.add_node("n2", action=lambda: 2)
            self.assertEqual(dag.all_nodes(), {"n1", "n2"})

    def test_find_roots_and_leaves_empty(self) -> None:
        """Empty graph has empty roots and empty leaves."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertEqual(dag.find_roots(), set())
            self.assertEqual(dag.find_leaves(), set())

    def test_find_roots_and_leaves_chain(self) -> None:
        """In chain A -> B -> C, root is A and leaf is C."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["B"])

            self.assertEqual(dag.find_roots(), {"A"})
            self.assertEqual(dag.find_leaves(), {"C"})

    def test_find_roots_and_leaves_diamond(self) -> None:
        """In diamond A -> B, A -> C, B -> D, C -> D, root is A and leaf is D."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["A"])
            dag.add_node("D", action=lambda: 4, dependencies=["B", "C"])

            self.assertEqual(dag.find_roots(), {"A"})
            self.assertEqual(dag.find_leaves(), {"D"})

    def test_validate_valid_dag_passes(self) -> None:
        """WHEN all referenced nodes exist and no cycle exists, MUST complete without error."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.validate()

    def test_validate_missing_dependency_raises_node_not_found(self) -> None:
        """WHEN a dependency node is missing, MUST raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1, dependencies=["ghost"])

            with self.assertRaises(dag_engine.NodeNotFoundError) as cm:
                dag.validate()
            self.assertEqual(cm.exception.node_id, "ghost")

    def test_validate_direct_cycle_raises_cycle_error(self) -> None:
        """WHEN a direct cycle exists (A -> B -> A), MUST raise CycleError containing the cycle sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2)
            dag.add_edge("A", "B")
            dag.add_edge("B", "A")

            with self.assertRaises(dag_engine.CycleError) as cm:
                dag.validate()
            self.assertGreater(len(cm.exception.cycle), 0)

    def test_validate_indirect_cycle_raises_cycle_error(self) -> None:
        """WHEN an indirect cycle exists (A -> B -> C -> A), MUST raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["B"])
            dag.add_edge("C", "A")

            with self.assertRaises(dag_engine.CycleError) as cm:
                dag.validate()
            self.assertGreater(len(cm.exception.cycle), 0)

    def test_topological_sort_linear_chain(self) -> None:
        """MUST return a valid topological ordering where every prerequisite precedes its dependents."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("step1", action=lambda: 1)
            dag.add_node("step2", action=lambda: 2, dependencies=["step1"])
            dag.add_node("step3", action=lambda: 3, dependencies=["step2"])

            order = dag.topological_sort()
            self.assertEqual(order, ["step1", "step2", "step3"])

    def test_topological_sort_tie_breaking_by_priority(self) -> None:
        """MUST break ties between concurrent ready nodes using priority descending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", action=lambda: 1, priority=5)
            dag.add_node("high", action=lambda: 2, priority=20)
            dag.add_node("medium", action=lambda: 3, priority=10)

            order = dag.topological_sort()
            self.assertEqual(order, ["high", "medium", "low"])

    def test_topological_sort_tie_breaking_by_name(self) -> None:
        """MUST break ties between concurrent ready nodes using name ascending when priority is equal."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("charlie", action=lambda: 1, priority=0)
            dag.add_node("alpha", action=lambda: 2, priority=0)
            dag.add_node("bravo", action=lambda: 3, priority=0)

            order = dag.topological_sort()
            self.assertEqual(order, ["alpha", "bravo", "charlie"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """WHEN a cycle exists, MUST raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("X", action=lambda: 1)
            dag.add_node("Y", action=lambda: 2)
            dag.add_edge("X", "Y")
            dag.add_edge("Y", "X")

            with self.assertRaises(dag_engine.CycleError):
                dag.topological_sort()

    def test_compute_critical_path_default_durations(self) -> None:
        """MUST return longest path through DAG and cumulative weight defaulting to 1.0 per node."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C1", action=lambda: 3, dependencies=["A"])
            dag.add_node("C2", action=lambda: 4, dependencies=["C1"])
            dag.add_node("D", action=lambda: 5, dependencies=["B", "C2"])

            path, weight = dag.compute_critical_path()
            self.assertEqual(path, ["A", "C1", "C2", "D"])
            self.assertEqual(weight, 4.0)

    def test_compute_critical_path_custom_durations(self) -> None:
        """MUST calculate path weight according to supplied estimated durations."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("A", action=lambda: 1)
            dag.add_node("B", action=lambda: 2, dependencies=["A"])
            dag.add_node("C", action=lambda: 3, dependencies=["A"])
            dag.add_node("D", action=lambda: 4, dependencies=["B", "C"])

            durations: Mapping[str, float] = {
                "A": 2.0,
                "B": 10.0,
                "C": 1.0,
                "D": 3.0,
            }
            path, weight = dag.compute_critical_path(estimated_durations=durations)
            self.assertEqual(path, ["A", "B", "D"])
            self.assertEqual(weight, 15.0)

    def test_compute_critical_path_single_node(self) -> None:
        """Single node path has weight equal to its single duration."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("solo", action=lambda: 1)

            path, weight = dag.compute_critical_path(estimated_durations={"solo": 5.5})
            self.assertEqual(path, ["solo"])
            self.assertEqual(weight, 5.5)

    def test_compute_critical_path_empty_dag(self) -> None:
        """WHEN DAG is empty, compute_critical_path MUST return an empty list and 0.0 weight."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            path, weight = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(weight, 0.0)

    def test_compute_critical_path_equal_weight_tie_breaking_by_priority(self) -> None:
        """WHEN multiple upstream predecessors have equal path weights, tie-breaking MUST prioritize higher priority."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", action=lambda: 1)
            dag.add_node("pred_a", action=lambda: 2, dependencies=["root"], priority=20)
            dag.add_node("pred_b", action=lambda: 3, dependencies=["root"], priority=10)
            dag.add_node("leaf", action=lambda: 4, dependencies=["pred_a", "pred_b"])

            path, weight = dag.compute_critical_path()
            self.assertEqual(weight, 3.0)
            self.assertEqual(path, ["root", "pred_a", "leaf"])

    def test_compute_critical_path_equal_weight_and_priority_tie_breaking_by_name(self) -> None:
        """WHEN upstream predecessors have equal path weight and equal priority, MUST break ties by node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", action=lambda: 1)
            dag.add_node("alpha", action=lambda: 2, dependencies=["root"], priority=0)
            dag.add_node("beta", action=lambda: 3, dependencies=["root"], priority=0)
            dag.add_node("leaf", action=lambda: 4, dependencies=["alpha", "beta"], priority=0)

            path, weight = dag.compute_critical_path()
            self.assertEqual(weight, 3.0)
            self.assertEqual(path, ["root", "alpha", "leaf"])


class WaveSchedulerTest(unittest.TestCase):
    """Unit tests for WaveScheduler resolving execution waves and tracking node lifecycle states."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_states_roots_ready_others_pending(self) -> None:
        """On initialization, MUST assign READY to all root nodes and PENDING to remaining nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root1", action=lambda: 1)
            dag.add_node("root2", action=lambda: 2)
            dag.add_node("child", action=lambda: 3, dependencies=["root1", "root2"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("root1"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("root2"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("child"), dag_engine.NodeState.PENDING)
            self.assertFalse(scheduler.is_finished())

    def test_next_wave_empty_graph(self) -> None:
        """WHEN no nodes are ready, MUST return an empty list."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.next_wave(), [])
            self.assertTrue(scheduler.is_finished())

    def test_next_wave_ordering_priority_descending_then_name_ascending(self) -> None:
        """MUST order returned nodes by priority descending, then node_id ascending."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("task_c", action=lambda: 1, priority=10)
            dag.add_node("task_b", action=lambda: 2, priority=20)
            dag.add_node("task_a", action=lambda: 3, priority=20)
            dag.add_node("task_d", action=lambda: 4, priority=5)

            scheduler = scope.get_singleton(WaveScheduler)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["task_a", "task_b", "task_c", "task_d"])

    def test_mark_running_transitions_state(self) -> None:
        """MUST update the node state to RUNNING."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("job", action=lambda: 1)

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("job")
            self.assertEqual(scheduler.get_state("job"), dag_engine.NodeState.RUNNING)
            self.assertEqual(scheduler.next_wave(), [])

    def test_mark_succeeded_unlocks_downstream_dependents(self) -> None:
        """MUST update the node state to SUCCEEDED and promote newly unblocked nodes to READY."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("first", action=lambda: 1)
            dag.add_node("second", action=lambda: 2, dependencies=["first"])

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertEqual(scheduler.get_state("second"), dag_engine.NodeState.PENDING)

            scheduler.mark_running("first")
            scheduler.mark_succeeded("first")

            self.assertEqual(scheduler.get_state("first"), dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(scheduler.get_state("second"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["second"])

    def test_mark_succeeded_multi_dependency_requires_all_succeeded(self) -> None:
        """Dependent node remains PENDING until ALL upstream dependencies have SUCCEEDED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("dep1", action=lambda: 1)
            dag.add_node("dep2", action=lambda: 2)
            dag.add_node("joined", action=lambda: 3, dependencies=["dep1", "dep2"])

            scheduler = scope.get_singleton(WaveScheduler)
            scheduler.mark_running("dep1")
            scheduler.mark_succeeded("dep1")

            self.assertEqual(scheduler.get_state("joined"), dag_engine.NodeState.PENDING)
            self.assertEqual(scheduler.next_wave(), ["dep2"])

            scheduler.mark_running("dep2")
            scheduler.mark_succeeded("dep2")

            self.assertEqual(scheduler.get_state("joined"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["joined"])

    def test_mark_failed_skip_downstream(self) -> None:
        """WHEN failure policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_root", action=lambda: 1)
            dag.add_node("child1", action=lambda: 2, dependencies=["fail_root"])
            dag.add_node("child2", action=lambda: 3, dependencies=["child1"])
            dag.add_node("independent_root", action=lambda: 4)

            scheduler = scope.get_singleton(WaveScheduler)
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.SKIP_DOWNSTREAM)

            scheduler.mark_running("fail_root")
            scheduler.mark_failed("fail_root")

            self.assertEqual(scheduler.get_state("fail_root"), dag_engine.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("child1"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("child2"), dag_engine.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("independent_root"), dag_engine.NodeState.READY)

    def test_mark_failed_fail_fast(self) -> None:
        """WHEN failure policy is FAIL_FAST, MUST transition all remaining non-terminal nodes to CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_root", action=lambda: 1)
            dag.add_node("other_root", action=lambda: 2)
            dag.add_node("other_child", action=lambda: 3, dependencies=["other_root"])

            scheduler = scope.get_singleton(WaveScheduler)
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.FAIL_FAST)

            scheduler.mark_running("fail_root")
            scheduler.mark_failed("fail_root")

            self.assertEqual(scheduler.get_state("fail_root"), dag_engine.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("other_root"), dag_engine.NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("other_child"), dag_engine.NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_mark_failed_continue_on_error(self) -> None:
        """WHEN failure policy is CONTINUE_ON_ERROR, retains non-terminal states for unblocked independent nodes."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("fail_root", action=lambda: 1)
            dag.add_node("independent_root", action=lambda: 2)

            scheduler = scope.get_singleton(WaveScheduler)
            setattr(scheduler, "_failure_policy", dag_engine.FailurePolicy.CONTINUE_ON_ERROR)

            scheduler.mark_running("fail_root")
            scheduler.mark_failed("fail_root")

            self.assertEqual(scheduler.get_state("fail_root"), dag_engine.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("independent_root"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.next_wave(), ["independent_root"])

    def test_is_finished_true_when_all_nodes_terminal(self) -> None:
        """MUST return True if all nodes are in terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED)."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("job1", action=lambda: 1)
            dag.add_node("job2", action=lambda: 2)

            scheduler = scope.get_singleton(WaveScheduler)
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("job1")
            scheduler.mark_succeeded("job1")
            self.assertFalse(scheduler.is_finished())

            scheduler.mark_running("job2")
            scheduler.mark_succeeded("job2")
            self.assertTrue(scheduler.is_finished())

    def test_get_all_states_returns_complete_mapping(self) -> None:
        """MUST return execution state mapping of every node in the graph."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("n1", action=lambda: 1)
            dag.add_node("n2", action=lambda: 2, dependencies=["n1"])

            scheduler = scope.get_singleton(WaveScheduler)
            states = scheduler.get_all_states()
            self.assertEqual(
                states,
                {
                    "n1": dag_engine.NodeState.READY,
                    "n2": dag_engine.NodeState.PENDING,
                },
            )

    def test_get_state_unmanaged_node_raises_error(self) -> None:
        """WHEN querying execution state of an unmanaged node identifier, MUST raise error."""
        with enter_phase(system, registry=self.registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            with self.assertRaises((dag_engine.NodeNotFoundError, KeyError)):
                scheduler.get_state("nonexistent_node")


class DAGRunnerTest(unittest.TestCase):
    """Unit tests for DAGRunner coordinating concurrent graph execution, retries, and cancellation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_run_empty_dag(self) -> None:
        """WHEN executing an empty DAG, run MUST return an empty DAGRunReport."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(report.total_nodes, 0)
            self.assertEqual(report.succeeded_nodes, ())
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertEqual(report.critical_path, ())
            self.assertEqual(len(report.results), 0)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_linear_pipeline_success(self) -> None:
        """MUST execute entire DAG to completion and return consolidated DAGRunReport."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("step1", action=lambda: "apple")
            dag.add_node("step2", action=lambda: "banana", dependencies=["step1"])
            dag.add_node("step3", action=lambda: "cherry", dependencies=["step2"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(report.total_nodes, 3)
            self.assertEqual(set(report.succeeded_nodes), {"step1", "step2", "step3"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertGreater(report.wall_clock_seconds, 0.0)
            self.assertEqual(report.critical_path, ("step1", "step2", "step3"))

            result1 = report.results["step1"]
            self.assertEqual(result1.node_id, "step1")
            self.assertEqual(result1.state, dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(result1.value, "apple")
            self.assertIsNone(result1.error)

            result2 = report.results["step2"]
            self.assertEqual(result2.value, "banana")

            result3 = report.results["step3"]
            self.assertEqual(result3.value, "cherry")

    def test_run_concurrent_diamond_graph(self) -> None:
        """MUST execute concurrent branches and join outcomes properly."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("start", action=lambda: 10)
            dag.add_node("branch_left", action=lambda: 20, dependencies=["start"])
            dag.add_node("branch_right", action=lambda: 30, dependencies=["start"])
            dag.add_node("finish", action=lambda: 40, dependencies=["branch_left", "branch_right"])

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertEqual(report.total_nodes, 4)
            self.assertEqual(set(report.succeeded_nodes), {"start", "branch_left", "branch_right", "finish"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())

    def test_run_retries_transient_failure_then_succeeds(self) -> None:
        """MUST execute retries up to configured retry count for failed node actions."""
        attempts = 0

        def flaky_action() -> str:
            nonlocal attempts
            attempts += 1
            if attempts <= 1:
                raise ValueError("temporary glitch")
            return "recovered"

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("flaky", action=flaky_action, retries=2)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertIn("flaky", report.succeeded_nodes)
            flaky_result = report.results["flaky"]
            self.assertEqual(flaky_result.state, dag_engine.NodeState.SUCCEEDED)
            self.assertEqual(flaky_result.value, "recovered")
            self.assertEqual(flaky_result.retries_attempted, 1)

    def test_run_retries_exhausted_records_failed(self) -> None:
        """WHEN retries are exhausted, MUST record FAILED outcome and store caught exception."""
        def persistent_fail() -> None:
            raise RuntimeError("permanent breakdown")

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("bad_node", action=persistent_fail, retries=1)

            runner = scope.get_singleton(DAGRunner)
            report = runner.run()

            self.assertIn("bad_node", report.failed_nodes)

            bad_result = report.results["bad_node"]
            self.assertEqual(bad_result.state, dag_engine.NodeState.FAILED)
            self.assertIsInstance(bad_result.error, RuntimeError)
            self.assertEqual(bad_result.retries_attempted, 1)

    def test_run_timeout_raises_dag_timeout_error(self) -> None:
        """WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError."""
        def slow_action() -> None:
            time.sleep(0.5)

        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("sluggish", action=slow_action)

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.01)

    def test_run_non_positive_timeout_raises_dag_timeout_error(self) -> None:
        """WHEN timeout_seconds is zero or negative, MUST raise DAGTimeoutError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("dummy", action=lambda: 1)
            runner = scope.get_singleton(DAGRunner)

            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=0.0)

            with self.assertRaises(dag_engine.DAGTimeoutError):
                runner.run(timeout_seconds=-1.0)

    def test_run_cancellation_raises_dag_cancelled_error(self) -> None:
        """WHEN cancelled during execution, MUST mark running and pending nodes as CANCELLED and raise DAGCancelledError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            def aborting_action() -> None:
                runner.cancel()

            dag.add_node("canceller", action=aborting_action)
            dag.add_node("blocked", action=lambda: 1, dependencies=["canceller"])

            with self.assertRaises(dag_engine.DAGCancelledError):
                runner.run()

            self.assertEqual(scheduler.get_state("blocked"), dag_engine.NodeState.CANCELLED)

    def test_cancel_marks_unstarted_nodes_cancelled(self) -> None:
        """WHEN DAGRunner.cancel is invoked, MUST mark unstarted ready and pending nodes as CANCELLED."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("ready_node", action=lambda: 1)
            dag.add_node("pending_node", action=lambda: 2, dependencies=["ready_node"])

            scheduler = scope.get_singleton(WaveScheduler)
            runner = scope.get_singleton(DAGRunner)

            self.assertEqual(scheduler.get_state("ready_node"), dag_engine.NodeState.READY)
            self.assertEqual(scheduler.get_state("pending_node"), dag_engine.NodeState.PENDING)

            runner.cancel()

            self.assertEqual(scheduler.get_state("ready_node"), dag_engine.NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("pending_node"), dag_engine.NodeState.CANCELLED)
            self.assertTrue(scheduler.is_finished())

    def test_run_validates_dag_cycle_raises_cycle_error(self) -> None:
        """WHEN a cycle exists, run MUST immediately raise CycleError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("loop1", action=lambda: 1)
            dag.add_node("loop2", action=lambda: 2)
            dag.add_edge("loop1", "loop2")
            dag.add_edge("loop2", "loop1")

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.CycleError):
                runner.run()

    def test_run_validates_dag_missing_dependency_raises_node_not_found(self) -> None:
        """WHEN a dependency node is missing, run MUST immediately raise NodeNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("orphan", action=lambda: 1, dependencies=["missing_prereq"])

            runner = scope.get_singleton(DAGRunner)
            with self.assertRaises(dag_engine.NodeNotFoundError):
                runner.run()


class DAGDataStructuresAndErrorsTest(unittest.TestCase):
    """Unit tests verifying exception types, dataclasses, and enum constants."""

    def test_exception_inheritance(self) -> None:
        """All domain errors MUST inherit from DAGError and Exception."""
        self.assertTrue(issubclass(dag_engine.CycleError, dag_engine.DAGError))
        self.assertTrue(issubclass(dag_engine.NodeNotFoundError, dag_engine.DAGError))
        self.assertTrue(issubclass(dag_engine.NodeExecutionError, dag_engine.DAGError))
        self.assertTrue(issubclass(dag_engine.DAGTimeoutError, dag_engine.DAGError))
        self.assertTrue(issubclass(dag_engine.DAGCancelledError, dag_engine.DAGError))
        self.assertTrue(issubclass(dag_engine.DAGError, Exception))

    def test_node_state_enum_values(self) -> None:
        """NodeState enum MUST define contracted lifecycle states."""
        self.assertEqual(dag_engine.NodeState.PENDING.value, "pending")
        self.assertEqual(dag_engine.NodeState.READY.value, "ready")
        self.assertEqual(dag_engine.NodeState.RUNNING.value, "running")
        self.assertEqual(dag_engine.NodeState.SUCCEEDED.value, "succeeded")
        self.assertEqual(dag_engine.NodeState.FAILED.value, "failed")
        self.assertEqual(dag_engine.NodeState.CANCELLED.value, "cancelled")
        self.assertEqual(dag_engine.NodeState.SKIPPED.value, "skipped")

    def test_failure_policy_enum_values(self) -> None:
        """FailurePolicy enum MUST define contracted failure strategies."""
        self.assertEqual(dag_engine.FailurePolicy.FAIL_FAST.value, "fail_fast")
        self.assertEqual(dag_engine.FailurePolicy.CONTINUE_ON_ERROR.value, "continue_on_error")
        self.assertEqual(dag_engine.FailurePolicy.SKIP_DOWNSTREAM.value, "skip_downstream")

    def test_node_definition_data_type(self) -> None:
        """NodeDefinition MUST be an immutable dataclass storing node execution parameters."""
        action_fn = lambda: "test"
        node_def = dag_engine.NodeDefinition(
            node_id="n1",
            action=action_fn,
            dependencies=frozenset(["dep1"]),
            priority=5,
            timeout_seconds=10.0,
            retries=2,
        )
        self.assertEqual(node_def.node_id, "n1")
        self.assertEqual(node_def.action(), "test")
        self.assertEqual(node_def.dependencies, frozenset(["dep1"]))
        self.assertEqual(node_def.priority, 5)
        self.assertEqual(node_def.timeout_seconds, 10.0)
        self.assertEqual(node_def.retries, 2)

    def test_node_result_data_type(self) -> None:
        """NodeResult MUST be an immutable outcome record of a node execution."""
        result = dag_engine.NodeResult(
            node_id="n1",
            state=dag_engine.NodeState.SUCCEEDED,
            value="output_val",
            error=None,
            duration_seconds=1.25,
            retries_attempted=0,
        )
        self.assertEqual(result.node_id, "n1")
        self.assertEqual(result.state, dag_engine.NodeState.SUCCEEDED)
        self.assertEqual(result.value, "output_val")
        self.assertIsNone(result.error)
        self.assertEqual(result.duration_seconds, 1.25)
        self.assertEqual(result.retries_attempted, 0)

    def test_dag_run_report_data_type(self) -> None:
        """DAGRunReport MUST be an immutable consolidated summary report."""
        report = dag_engine.DAGRunReport(
            total_nodes=1,
            succeeded_nodes=("n1",),
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=2.5,
            critical_path=("n1",),
            results={
                "n1": dag_engine.NodeResult(
                    node_id="n1",
                    state=dag_engine.NodeState.SUCCEEDED,
                    value="ok",
                ),
            },
        )
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ("n1",))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.wall_clock_seconds, 2.5)
        self.assertEqual(report.critical_path, ("n1",))
        self.assertIn("n1", report.results)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-21T01:25:46Z
# LAST_CHANGED: 2026-10-21T01:08:07Z
# CHANGE: Add test coverage for compute_critical_path empty DAG and predecessor tie-breaking, WaveScheduler.get_state unmanaged node errors, DAGRunner empty DAG execution, non-positive timeouts, and cancel state transitions
# COVERAGE_AUDIT: 2026-10-21T01:25:46Z
# QA_AUDIT: 2026-10-21T01:25:16Z
# --- END CLEANROOM METADATA ---
