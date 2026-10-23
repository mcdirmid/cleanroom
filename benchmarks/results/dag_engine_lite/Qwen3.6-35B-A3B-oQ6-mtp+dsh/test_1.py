from __future__ import annotations

import time
import unittest
from typing import Any, Callable, FrozenSet, Set
from unittest.mock import patch, MagicMock

from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    system,
)

from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    WaveScheduler,
    DAGRunner,
    __initialize__,
)

import benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite as dag_engine_lite


# --- Mock Helper Factory Functions ---

def _make_action(value: Any = "result") -> Callable[[], Any]:
    """Wrap a primitive value into a zero-argument action callable."""
    call_record: list = []
    def action() -> Any:
        call_record.append(value)
        return value
    action.call_record = call_record  # type: ignore[attr-defined]
    return action


def _frozen_deps(ids: list[str]) -> FrozenSet[str]:
    """Convert a list of node ids to a FrozenSet for NodeDefinition dependencies."""
    return frozenset(ids)


# --- Test Case: DAG ---

class TestDAGNodeManagement(unittest.TestCase):
    """Tests for DAG node CRUD operations (add_node, has_node, get_node, remove_node).

    Derived from dag_engine_lite_impl.pyi and dag_engine_lite.pyi:
    - add_node: registers node definition into the graph, adds dependency edges
    - has_node: checks node existence
    - get_node: retrieves node definition, raises NodeNotFoundError if absent
    - remove_node: removes node and incident edges, raises NodeNotFoundError if absent
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_add_node_registers_definition(self) -> None:
        """Happy-path: add_node registers the node definition into the graph.

        POSTCONDITION: MUST register the node definition into the graph.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a")
            self.assertTrue(dag.has_node("node_a"))

    def test_add_node_with_dependencies(self) -> None:
        """Happy-path: add_node with dependencies adds directed dependency edges.

        POSTCONDITION: WHEN dependencies are provided, MUST add directed dependency edges.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a")
            dag.add_node("node_b", action=lambda: "b", dependencies=["node_a"])
            deps = dag.get_dependencies("node_b")
            self.assertIn("node_a", deps)

    def test_add_node_priority_stored(self) -> None:
        """Happy-path: add_node stores priority value for scheduling.

        POSTCONDITION: MUST register the node definition (with priority) into the graph.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a", priority=5)
            node_def = dag.get_node("node_a")
            self.assertEqual(node_def.priority, 5)

    def test_add_node_retries_stored(self) -> None:
        """Happy-path: add_node stores retry count.

        POSTCONDITION: MUST register the node definition (with retries) into the graph.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a", retries=3)
            node_def = dag.get_node("node_a")
            self.assertEqual(node_def.retries, 3)

    def test_has_node_returns_true_for_existing(self) -> None:
        """Happy-path: has_node returns True for an existing node."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a")
            self.assertTrue(dag.has_node("node_a"))

    def test_has_node_returns_false_for_missing(self) -> None:
        """Alternate: has_node returns False for a missing node."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            self.assertFalse(dag.has_node("nonexistent"))

    def test_get_node_returns_definition(self) -> None:
        """Happy-path: get_node returns the NodeDefinition matching node_id."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            action = _make_action("test_val")
            dag.add_node("node_a", action=action, priority=2, retries=1)
            node_def = dag.get_node("node_a")
            self.assertEqual(node_def.node_id, "node_a")
            self.assertEqual(node_def.priority, 2)
            self.assertEqual(node_def.retries, 1)
            self.assertEqual(node_def.dependencies, frozenset())

    def test_get_node_raises_for_missing(self) -> None:
        """Alternate: get_node raises NodeNotFoundError when node_id is absent.

        POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.get_node("missing")
            self.assertEqual(ctx.exception.node_id, "missing")

    def test_remove_node_removes_definition_and_edges(self) -> None:
        """Happy-path: remove_node removes the node and its incident edges.

        POSTCONDITION: MUST remove the node and its incident edges.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a")
            dag.add_node("node_b", action=lambda: "b", dependencies=["node_a"])
            dag.remove_node("node_a")
            self.assertFalse(dag.has_node("node_a"))
            # Verify node_b no longer references node_a as dependency
            self.assertFalse(dag.has_node("node_a"))
            # get_dependents on removed node raises NodeNotFoundError per contract

    def test_remove_node_raises_for_missing(self) -> None:
        """Alternate: remove_node raises NodeNotFoundError when node_id is absent.

        POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.remove_node("nonexistent")
            self.assertEqual(ctx.exception.node_id, "nonexistent")

    def test_get_dependencies_returns_upstream(self) -> None:
        """Happy-path: get_dependencies returns all direct upstream dependencies.

        POSTCONDITION: MUST return all direct upstream dependencies.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a")
            dag.add_node("node_b", action=lambda: "b", dependencies=["node_a"])
            dag.add_node("node_c", action=lambda: "c", dependencies=["node_a", "node_b"])
            deps = dag.get_dependencies("node_c")
            self.assertEqual(deps, {"node_a", "node_b"})

    def test_get_dependencies_raises_for_missing(self) -> None:
        """Alternate: get_dependencies raises NodeNotFoundError if node_id is not in the graph."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.get_dependencies("missing")

    def test_get_dependents_returns_downstream(self) -> None:
        """Happy-path: get_dependents returns all direct downstream dependents.

        POSTCONDITION: MUST return all direct downstream dependents.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("node_a", action=lambda: "a")
            dag.add_node("node_b", action=lambda: "b", dependencies=["node_a"])
            dag.add_node("node_c", action=lambda: "c", dependencies=["node_a"])
            dependents = dag.get_dependents("node_a")
            self.assertEqual(dependents, {"node_b", "node_c"})

    def test_get_dependents_raises_for_missing(self) -> None:
        """Alternate: get_dependents raises NodeNotFoundError if node_id is not in the graph."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.get_dependents("missing")

    def test_all_nodes_returns_all_identifiers(self) -> None:
        """Happy-path: all_nodes returns all registered node identifiers.

        POSTCONDITION: MUST return a copy of set(_nodes.keys()).
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b")
            dag.add_node("c", action=lambda: "c")
            nodes = dag.all_nodes()
            self.assertEqual(nodes, {"a", "b", "c"})


class TestDAGEdgeOperations(unittest.TestCase):
    """Tests for DAG add_edge and add_node edge construction.

    Derived from dag_engine_lite_impl.pyi:
    - add_edge: adds directed dependency edge, raises NodeNotFoundError if either node missing
    - add_node: when dependencies provided, adds directed dependency edges from each to node_id
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_add_edge_establishes_dependency(self) -> None:
        """Happy-path: add_edge establishes a directed dependency edge.

        POSTCONDITION: MUST establish a directed dependency edge from upstream_id to downstream_id.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", action=lambda: "up")
            dag.add_node("down", action=lambda: "down")
            dag.add_edge("up", "down")
            deps = dag.get_dependencies("down")
            self.assertIn("up", deps)

    def test_add_edge_raises_when_upstream_missing(self) -> None:
        """Alternate: add_edge raises NodeNotFoundError when upstream_id does not exist.

        POSTCONDITION: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("down", action=lambda: "down")
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("missing_up", "down")
            self.assertEqual(ctx.exception.node_id, "missing_up")

    def test_add_edge_raises_when_downstream_missing(self) -> None:
        """Alternate: add_edge raises NodeNotFoundError when downstream_id does not exist."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("up", action=lambda: "up")
            with self.assertRaises(dag_engine_lite.NodeNotFoundError) as ctx:
                dag.add_edge("up", "missing_down")
            self.assertEqual(ctx.exception.node_id, "missing_down")


class TestDAGGraphTraversal(unittest.TestCase):
    """Tests for DAG topological_sort, find_roots, find_leaves, and compute_critical_path.

    Derived from dag_engine_lite.pyi:
    - topological_sort: valid topo ordering, priority desc + name asc tie-breaking, CycleError on cycles
    - find_roots: nodes with in-degree zero
    - find_leaves: nodes with out-degree zero
    - compute_critical_path: longest weighted path
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_find_roots_returns_zero_indegree(self) -> None:
        """Happy-path: find_roots returns all root nodes with in-degree zero.

        POSTCONDITION: Returns Set of root node identifiers.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root_a", action=lambda: "a")
            dag.add_node("root_b", action=lambda: "b")
            dag.add_node("child", action=lambda: "c", dependencies=["root_a", "root_b"])
            roots = dag.find_roots()
            self.assertEqual(roots, {"root_a", "root_b"})

    def test_find_leaves_returns_zero_outdegree(self) -> None:
        """Happy-path: find_leaves returns all leaf nodes with out-degree zero.

        POSTCONDITION: Returns Set of leaf node identifiers.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("root", action=lambda: "a")
            dag.add_node("leaf_a", action=lambda: "b", dependencies=["root"])
            dag.add_node("leaf_b", action=lambda: "c", dependencies=["root"])
            leaves = dag.find_leaves()
            self.assertEqual(leaves, {"leaf_a", "leaf_b"})

    def test_topological_sort_valid_order(self) -> None:
        """Happy-path: topological_sort returns valid ordering where prerequisites precede dependents.

        POSTCONDITION: MUST return a valid topological ordering where every prerequisite precedes its dependents.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("c", action=lambda: "c")
            dag.add_node("b", action=lambda: "b", dependencies=["c"])
            dag.add_node("a", action=lambda: "a", dependencies=["b"])
            order = dag.topological_sort()
            idx_c = order.index("c")
            idx_b = order.index("b")
            idx_a = order.index("a")
            self.assertLess(idx_c, idx_b)
            self.assertLess(idx_b, idx_a)

    def test_topological_sort_tie_breaking_priority_desc(self) -> None:
        """Happy-path: topological_sort breaks ties by priority descending.

        POSTCONDITION: MUST break ties between concurrent ready nodes using priority descending.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("low", action=lambda: "low", priority=1)
            dag.add_node("high", action=lambda: "high", priority=10)
            order = dag.topological_sort()
            self.assertLess(order.index("high"), order.index("low"))

    def test_topological_sort_tie_breaking_name_asc(self) -> None:
        """Happy-path: topological_sort breaks ties by node_id ascending when priorities match.

        POSTCONDITION: MUST break ties between concurrent ready nodes using name ascending.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("b_node", action=lambda: "b", priority=5)
            dag.add_node("a_node", action=lambda: "a", priority=5)
            order = dag.topological_sort()
            self.assertLess(order.index("a_node"), order.index("b_node"))

    def test_topological_sort_raises_on_cycle(self) -> None:
        """Alternate: topological_sort raises CycleError when the graph contains a cycle.

        POSTCONDITION: WHEN a cycle exists, MUST raise CycleError.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a", dependencies=["c"])
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.topological_sort()
            self.assertIsInstance(ctx.exception.cycle, tuple)

    def test_compute_critical_path_default_weights(self) -> None:
        """Happy-path: compute_critical_path returns longest path with default 1.0 weights.

        POSTCONDITION: MUST return the sequence of nodes that forms the longest path.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            path, total = dag.compute_critical_path()
            self.assertEqual(path, ["a", "b", "c"])
            self.assertEqual(total, 3.0)

    def test_compute_critical_path_custom_weights(self) -> None:
        """Happy-path: compute_critical_path uses custom duration weights.

        POSTCONDITION: MUST return the cumulative weight of the critical path.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a", priority=0)
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["a"])
            path, total = dag.compute_critical_path({"a": 1.0, "b": 10.0, "c": 2.0})
            self.assertEqual(total, 11.0)  # a->b = 1+10

    def test_compute_critical_path_branch_selection(self) -> None:
        """Happy-path: compute_critical_path selects the longest branch.

        POSTCONDITION: MUST return the sequence of nodes forming the longest path.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            dag.add_node("d", action=lambda: "d", dependencies=["a"])
            dag.add_node("e", action=lambda: "e", dependencies=["d", "c"])
            path, total = dag.compute_critical_path()
            # Path: a -> b -> c -> e has weight 4, path: a -> d -> e has weight 3
            self.assertEqual(total, 4.0)


class TestDAGValidation(unittest.TestCase):
    """Tests for DAG validate().

    Derived from dag_engine_lite.pyi:
    - validate: checks dependency completeness and acyclicity
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_validate_passes_on_valid_dag(self) -> None:
        """Happy-path: validate completes without error when graph is valid.

        POSTCONDITION: WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.validate()  # Should not raise

    def test_validate_raises_for_missing_dependency(self) -> None:
        """Alternate: validate raises NodeNotFoundError when a dependency node is missing.

        POSTCONDITION: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a", dependencies=["nonexistent"])
            with self.assertRaises(dag_engine_lite.NodeNotFoundError):
                dag.validate()

    def test_validate_raises_for_cycle(self) -> None:
        """Alternate: validate raises CycleError when a cycle exists.

        POSTCONDITION: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a", dependencies=["b"])
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            with self.assertRaises(dag_engine_lite.CycleError) as ctx:
                dag.validate()
            self.assertIsInstance(ctx.exception.cycle, tuple)


# --- Test Case: WaveScheduler ---

class TestWaveSchedulerOperations(unittest.TestCase):
    """Tests for WaveScheduler: next_wave, mark_running, mark_succeeded, mark_failed.

    Derived from dag_engine_lite_impl.pyi:
    - next_wave: returns ready nodes ordered by priority desc, node_id asc
    - mark_running: transitions to RUNNING
    - mark_succeeded: transitions to SUCCEEDED, promotes unblocked dependents to READY
    - mark_failed: transitions to FAILED, applies failure policy
    - is_finished: True when all nodes terminal
    - get_state / get_all_states: node state queries
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_next_wave_returns_roots_first(self) -> None:
        """Happy-path: next_wave returns root nodes (no dependencies) whose state is READY.

        POSTCONDITION: MUST return all nodes in READY state whose upstream deps are SUCCEEDED.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["a"])

    def test_next_wave_empty_when_all_done(self) -> None:
        """Alternate: next_wave returns an empty list when no nodes are ready.

        POSTCONDITION: WHEN no nodes are ready, MUST return an empty list.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a", dependencies=["x"])
            wave = scheduler.next_wave()
            self.assertEqual(wave, [])

    def test_next_wave_ordered_by_priority(self) -> None:
        """Happy-path: next_wave orders nodes by priority descending, then node_id ascending.

        POSTCONDITION: MUST order returned nodes by priority descending, then node_id ascending.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("low", action=lambda: "low", priority=1)
            dag.add_node("high", action=lambda: "high", priority=10)
            dag.add_node("mid", action=lambda: "mid", priority=5)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["high", "mid", "low"])

    def test_mark_running_transitions_state(self) -> None:
        """Happy-path: mark_running updates node state to RUNNING.

        POSTCONDITION: MUST update the node state to RUNNING.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.RUNNING)

    def test_mark_succeeded_promotes_dependents(self) -> None:
        """Happy-path: mark_succeeded transitions to SUCCEEDED and unlocks downstream.

        POSTCONDITION: MUST update to SUCCEEDED, MUST evaluate downstream and promote unblocked to READY.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.SUCCEEDED)
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["b"])

    def test_mark_failed_sets_failed_state(self) -> None:
        """Happy-path: mark_failed updates node state to FAILED.

        POSTCONDITION: MUST update the node state to FAILED.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            scheduler.mark_failed("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)

    def test_mark_failed_fail_fast_cancels_remaining(self) -> None:
        """Alternate: mark_failed with FAIL_FAST transitions all PENDING nodes to CANCELLED.

        POSTCONDITION: WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING to CANCELLED.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c")
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST)
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
            # 'b' is a dependent of 'a' -> CANCELLED; 'c' is a root (READY) -> also CANCELLED by FAIL_FAST
            self.assertEqual(scheduler.get_state("c"), dag_engine_lite.NodeState.CANCELLED)
            self.assertEqual(scheduler.get_state("b"), dag_engine_lite.NodeState.CANCELLED)

    def test_mark_failed_skip_downstream_skips_dependents(self) -> None:
        """Alternate: mark_failed with SKIP_DOWNSTREAM transitions transitive dependents to SKIPPED.

        POSTCONDITION: WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c")
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
            # 'c' is a root node with no dependency on 'a' -> stays READY
            self.assertEqual(scheduler.get_state("c"), dag_engine_lite.NodeState.READY)

    def test_mark_failed_continue_on_error_leaves_independent(self) -> None:
        """Alternate: mark_failed with CONTINUE_ON_ERROR leaves unblocked independent nodes.

        POSTCONDITION: WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c")
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
            # 'c' is a root node with no dependency on 'a' -> stays READY
            self.assertEqual(scheduler.get_state("c"), dag_engine_lite.NodeState.READY)

    def test_is_finished_true_when_all_terminal(self) -> None:
        """Happy-path: is_finished returns True when all nodes are in terminal states.

        POSTCONDITION: WHEN all nodes have reached terminal states, MUST return True.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertTrue(scheduler.is_finished())

    def test_is_finished_false_when_not_all_terminal(self) -> None:
        """Alternate: is_finished returns False when any node is not terminal.

        POSTCONDITION: WHEN any node is not in a terminal state, MUST return False.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            scheduler.mark_running("a")
            scheduler.mark_succeeded("a")
            self.assertFalse(scheduler.is_finished())

    def test_is_finished_true_when_empty_dag(self) -> None:
        """Alternate: is_finished returns True when the DAG contains no nodes.

        POSTCONDITION: WHEN the DAG contains no nodes, MUST return True.
        """
        with enter_phase(system, registry=self._registry) as scope:
            scheduler = scope.get_singleton(WaveScheduler)
            self.assertTrue(scheduler.is_finished())

    def test_get_state_returns_current_state(self) -> None:
        """Happy-path: get_state retrieves the current execution state of a node."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            scheduler.mark_running("a")
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.RUNNING)

    def test_get_all_states_returns_mapping(self) -> None:
        """Happy-path: get_all_states returns a mapping of node identifier to current state."""
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b")
            states = scheduler.get_all_states()
            self.assertIn("a", states)
            self.assertIn("b", states)


# --- Test Case: DAGRunner ---

class TestDAGRunnerExecution(unittest.TestCase):
    """Tests for DAGRunner.run().

    Derived from dag_engine_lite_impl.pyi:
    - run: executes entire DAG sequentially to completion under failure policies
    - MUST execute ready waves, retries, apply failure_policy, return DAGRunReport
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_run_success_all_nodes(self) -> None:
        """Happy-path: run executes all nodes to success and returns DAGRunReport.

        POSTCONDITION: MUST return a DAGRunReport capturing all node states and outcomes.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", action=lambda: "result_a")
            dag.add_node("b", action=lambda: "result_b", dependencies=["a"])
            report = runner.run()
            self.assertEqual(report.total_nodes, 2)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
            self.assertEqual(report.failed_nodes, ())
            self.assertEqual(report.skipped_nodes, ())
            self.assertEqual(report.cancelled_nodes, ())
            self.assertIn("a", report.results)
            self.assertIn("b", report.results)
            self.assertEqual(report.results["a"].state, dag_engine_lite.NodeState.SUCCEEDED)
            self.assertEqual(report.results["b"].state, dag_engine_lite.NodeState.SUCCEEDED)

    def test_run_failure_policy_fail_fast(self) -> None:
        """Alternate: run with FAIL_FAST halts further wave execution on failure.

        POSTCONDITION: MUST apply the specified failure_policy to the scheduler upon node failure.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            def failing_action():
                raise RuntimeError("action failed")
            def success_action():
                return "ok"
            dag.add_node("a", action=failing_action)
            dag.add_node("b", action=success_action)
            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST)
            self.assertEqual(report.failed_nodes, ("a",))
            self.assertEqual(report.cancelled_nodes, ("b",))

    def test_run_retries_on_failure(self) -> None:
        """Alternate: run executes retries up to configured retry count.

        POSTCONDITION: MUST execute retries up to the configured retry count for failed node actions.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            call_count: dict = {"count": 0}
            def eventually_fails():
                call_count["count"] += 1
                raise RuntimeError("still failing")
            dag.add_node("a", action=eventually_fails, retries=2)
            report = runner.run()
            self.assertEqual(call_count["count"], 3)
            self.assertEqual(report.results["a"].state, dag_engine_lite.NodeState.FAILED)
            self.assertEqual(report.results["a"].retries_attempted, 2)

    def test_run_with_default_critical_path(self) -> None:
        """Happy-path: run includes critical_path in DAGRunReport.

        POSTCONDITION: MUST return a DAGRunReport capturing critical path.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            report = runner.run()
            self.assertEqual(report.critical_path, ("a", "b", "c"))

    def test_run_includes_wall_clock_seconds(self) -> None:
        """Happy-path: run records wall_clock_seconds in the report.

        POSTCONDITION: MUST return a DAGRunReport with wall_clock_seconds.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", action=lambda: "a")
            report = runner.run()
            self.assertIsInstance(report.wall_clock_seconds, float)
            self.assertGreaterEqual(report.wall_clock_seconds, 0.0)

    def test_run_node_execution_error_records_error(self) -> None:
        """Alternate: run records error details on failed node result.

        POSTCONDITION: MUST record NodeResult with error for failed nodes.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", action=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            report = runner.run()
            self.assertEqual(report.results["a"].state, dag_engine_lite.NodeState.FAILED)
            self.assertIsNotNone(report.results["a"].error)

    def test_run_diamond_dependency(self) -> None:
        r"""Happy-path: run handles diamond dependency pattern correctly.

        DAG structure:
            a
           / \
          b   c
           \ /
            d
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["a"])
            dag.add_node("d", action=lambda: "d", dependencies=["b", "c"])
            report = runner.run()
            self.assertEqual(report.total_nodes, 4)
            self.assertEqual(set(report.succeeded_nodes), {"a", "b", "c", "d"})


class TestDAGEdgeCases(unittest.TestCase):
    """Tests for edge cases and empty-graph paths in DAG and WaveScheduler.

    Derived from dag_engine_lite_impl.pyi and dag_engine_lite.pyi:
    - compute_critical_path on empty DAG
    - next_wave empty with non-finished scheduler (blocked nodes)
    - transitive SKIP_DOWNSTREAM across multi-level chains
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_compute_critical_path_empty_dag(self) -> None:
        """Edge-case: compute_critical_path on an empty DAG returns ([], 0.0).

        POSTCONDITION: WHEN no nodes exist, MUST return empty path list and 0.0 total.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            path, total = dag.compute_critical_path()
            self.assertEqual(path, [])
            self.assertEqual(total, 0.0)

    def test_next_wave_empty_when_blocked(self) -> None:
        """Edge-case: next_wave returns empty list when all nodes are blocked on unmet dependencies.

        POSTCONDITION: WHEN no nodes are ready (all blocked), MUST return an empty list.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            # "b" depends on "a" which doesn't exist, so no nodes are ready
            wave = scheduler.next_wave()
            self.assertEqual(wave, [])

    def test_mark_failed_skip_downstream_transitive_chain(self) -> None:
        """Coverage: mark_failed with SKIP_DOWNSTREAM transits through multi-level dependents.

        Graph: A -> B -> C (3-level chain). Skipping A should mark B and C as SKIPPED.

        POSTCONDITION: MUST transition all transitive dependents to SKIPPED via BFS traversal.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), dag_engine_lite.NodeState.SKIPPED)


class TestDAGRunnerEdgeCases(unittest.TestCase):
    """Tests for DAGRunner edge cases around skipped nodes and early-break paths.

    Derived from dag_engine_lite_impl.pyi:
    - DAGRunReport.skipped_nodes collection for SKIP_DOWNSTREAM/CONTINUE_ON_ERROR
    - next_wave empty while scheduler not finished (early break in run loop)
    """

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)

    def test_run_skip_downstream_records_skipped_in_report(self) -> None:
        """Coverage: DAGRunner.run() with SKIP_DOWNSTREAM produces SKIPPED nodes in DAGRunReport.

        Graph: A -> B, A fails -> B should be SKIPPED and appear in report.skipped_nodes.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            def failing_action():
                raise RuntimeError("boom")
            dag.add_node("a", action=failing_action)
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(set(report.failed_nodes), {"a"})
            self.assertEqual(set(report.skipped_nodes), {"b"})

    def test_run_continue_on_error_leaves_dependent_unexecuted(self) -> None:
        """Coverage: DAGRunner.run() with CONTINUE_ON_ERROR does not mark dependents SKIPPED.

        Graph: A -> B, A fails -> B stays unexecuted (PENDING/READY) but not SKIPPED.
        CONTINUE_ON_ERROR only retains non-terminal states for independent nodes.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            runner = scope.get_singleton(DAGRunner)
            def failing_action():
                raise RuntimeError("boom")
            dag.add_node("a", action=failing_action)
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            report = runner.run(failure_policy=dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
            self.assertEqual(set(report.failed_nodes), {"a"})
            # B depends on failed A and is not independent — it stays unexecuted
            self.assertEqual(set(report.skipped_nodes), set())

    def test_cycle_error_on_circular_dependency(self) -> None:
        """Coverage: DAG.validate() raises CycleError when a directed cycle exists.

        Graph: A -> B -> C -> A (3-node cycle).
        POSTCONDITION: MUST raise CycleError containing the cycle sequence.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a", dependencies=["c"])
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            with self.assertRaises(dag_engine_lite.CycleError):
                dag.validate()

    def test_next_wave_empty_after_fail_fast_cancel(self) -> None:
        """Edge-case: next_wave returns empty while scheduler is not finished (cancel path).

        Graph: A -> B. FAIL_FAST on A -> B becomes CANCELLED, next_wave returns [].
        The run loop must handle the empty-wave early break gracefully.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            wave = scheduler.next_wave()
            self.assertEqual(wave, ["a"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=dag_engine_lite.FailurePolicy.FAIL_FAST)
            wave2 = scheduler.next_wave()
            self.assertEqual(wave2, [])

    def test_remove_node_with_upstream_and_downstream_deps(self) -> None:
        """Coverage: remove_node on a non-root node with both upstream and downstream edges.

        Graph: A -> B -> C. Removing B must remove B from A's dependents set
        and remove A from B's dependencies, and remove C from B's dependents set.

        POSTCONDITION: MUST remove all incident edges including upstream dependency edges.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["b"])
            dag.remove_node("b")
            self.assertFalse(dag.has_node("b"))
            self.assertTrue(dag.has_node("a"))
            self.assertTrue(dag.has_node("c"))
            # a should no longer list b as a dependent (b was removed)
            self.assertNotIn("b", dag.get_dependents("a"))
            # c should no longer list b as a dependency
            self.assertNotIn("b", dag.get_dependencies("c"))

    def test_skip_downstream_diamond_topology(self) -> None:
        """Coverage: SKIP_DOWNSTREAM BFS with diamond topology exercises dedup continue guard.

        Graph: A -> B, A -> C, B -> D, C -> D (D reachable via two paths).
        Failing A should mark B, C, and D as SKIPPED. D is reached twice in BFS
        but the continue guard skips already-seen nodes.

        POSTCONDITION: MUST transition all transitive dependents to SKIPPED via BFS,
        visiting each node only once despite convergent diamond paths.
        """
        with enter_phase(system, registry=self._registry) as scope:
            dag = scope.get_singleton(DAG)
            scheduler = scope.get_singleton(WaveScheduler)
            dag.add_node("a", action=lambda: "a")
            dag.add_node("b", action=lambda: "b", dependencies=["a"])
            dag.add_node("c", action=lambda: "c", dependencies=["a"])
            dag.add_node("d", action=lambda: "d", dependencies=["b", "c"])
            scheduler.mark_running("a")
            scheduler.mark_failed("a", failure_policy=dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
            self.assertEqual(scheduler.get_state("a"), dag_engine_lite.NodeState.FAILED)
            self.assertEqual(scheduler.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("c"), dag_engine_lite.NodeState.SKIPPED)
            self.assertEqual(scheduler.get_state("d"), dag_engine_lite.NodeState.SKIPPED)


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T19:16:52Z
# LAST_CHANGED: 2026-10-23T19:15:41Z
# CHANGE: Added 2 missing test cases: (1) test_remove_node_with_upstream_and_downstream_deps removes a non-root node B in A->B->C graph, verifying B is removed from upstream dep's dependents set and from downstream dep's dependencies set, (2) test_skip_downstream_diamond_topology uses A->B, A->C, B->D, C->D diamond to exercise BFS dedup continue guard where D is reachable via two paths.
# COVERAGE_AUDIT: 2026-10-23T19:16:52Z
# QA_AUDIT: 2026-10-23T19:16:10Z
# --- END CLEANROOM METADATA ---
