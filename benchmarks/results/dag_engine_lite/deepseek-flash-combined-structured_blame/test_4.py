"""Unit tests for the synchronous DAG execution and wave scheduling engine.

Specifications: low/dag_engine_lite.pyi and low/dag_engine_lite_impl.pyi.
"""

from __future__ import annotations

import unittest
from typing import Any, Callable, Collection, Mapping, Optional

from support.lib.lifecycle import LifecycleTestCase, fake

from dag_engine_lite.lib import dag_engine_lite
from dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGService,
    DAGRunner as DAGRunnerService,
    WaveScheduler as WaveSchedulerService,
)


def no_op_action() -> None:
    """Neutral zero-argument node action used by graph-only fixtures."""
    return None


class GraphDouble(dag_engine_lite.DAG):
    """In-memory DAG double supplying graph topology to scheduler and runner targets.

    Only the observed collaborator behavior is reproduced: node definitions with
    priorities, upstream/downstream adjacency, and scripted validation and critical
    path answers. Test fixtures seed nodes directly through seed_node().
    """

    tier = "system"

    def __init__(self) -> None:
        self.definitions: dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self.upstream: dict[str, set[str]] = {}
        self.downstream: dict[str, set[str]] = {}
        self.validate_error: Optional[Exception] = None
        self.topological_order: list[str] = []
        self.critical_path: list[str] = []
        self.critical_path_weight: float = 0.0

    def seed_node(
        self,
        node_id: str,
        priority: int = 0,
        dependencies: Collection[str] = (),
        action: Callable[[], Any] = no_op_action,
        retries: int = 0,
    ) -> None:
        """Registers a node definition together with its dependency wiring."""
        frozen_dependencies = frozenset(dependencies)
        self.definitions[node_id] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_dependencies,
            priority=priority,
            retries=retries,
        )
        self.upstream.setdefault(node_id, set()).update(frozen_dependencies)
        self.downstream.setdefault(node_id, set())
        for dependency in frozen_dependencies:
            self.upstream.setdefault(dependency, set())
            self.downstream.setdefault(dependency, set()).add(node_id)

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        self.seed_node(
            node_id,
            priority=priority,
            dependencies=dependencies or (),
            action=action,
            retries=retries,
        )

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        self.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.downstream.setdefault(upstream_id, set()).add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        self.definitions.pop(node_id, None)
        self.upstream.pop(node_id, None)
        self.downstream.pop(node_id, None)
        for dependencies in self.upstream.values():
            dependencies.discard(node_id)
        for dependents in self.downstream.values():
            dependents.discard(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.definitions

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        return self.definitions[node_id]

    def get_dependencies(self, node_id: str) -> set[str]:
        return set(self.upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> set[str]:
        return set(self.downstream.get(node_id, set()))

    def all_nodes(self) -> set[str]:
        return set(self.definitions)

    def validate(self) -> None:
        if self.validate_error is not None:
            raise self.validate_error

    def topological_sort(self) -> list[str]:
        return list(self.topological_order)

    def find_roots(self) -> set[str]:
        return {node for node in self.definitions if not self.upstream.get(node)}

    def find_leaves(self) -> set[str]:
        return {node for node in self.definitions if not self.downstream.get(node)}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> tuple[list[str], float]:
        return (list(self.critical_path), self.critical_path_weight)


class WaveSchedulerDouble(dag_engine_lite.WaveScheduler):
    """Scripted wave scheduler double driving the DAG runner wave loop."""

    tier = "system"

    def __init__(self) -> None:
        self.waves: list[list[str]] = []
        self.states: dict[str, dag_engine_lite.NodeState] = {}
        self.started: list[str] = []
        self.completed: list[str] = []
        self.failures: list[tuple[str, dag_engine_lite.FailurePolicy]] = []

    def next_wave(self) -> list[str]:
        if not self.waves:
            return []
        return list(self.waves.pop(0))

    def mark_running(self, node_id: str) -> None:
        self.states[node_id] = dag_engine_lite.NodeState.RUNNING
        self.started.append(node_id)

    def mark_succeeded(self, node_id: str) -> None:
        self.states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        self.completed.append(node_id)

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        self.states[node_id] = dag_engine_lite.NodeState.FAILED
        self.failures.append((node_id, failure_policy))

    def is_finished(self) -> bool:
        return not self.waves

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        return self.states.get(node_id, dag_engine_lite.NodeState.PENDING)

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        return dict(self.states)


class DAGServiceTest(LifecycleTestCase):
    """Tests for the concrete graph service that stores nodes and edges."""

    target = DAGService

    def test_add_node_registers_definition_and_dependencies(self) -> None:
        """Adding a node stores its definition and records each dependency edge."""
        self.sut.add_node("a", no_op_action, None, 5, 2)
        self.sut.add_node("b", no_op_action, ["a"], 1, 0)
        self.assertTrue(self.sut.has_node("a"))
        self.assertTrue(self.sut.has_node("b"))
        self.assertEqual(self.sut.all_nodes(), {"a", "b"})
        definition = self.sut.get_node("b")
        self.assertEqual(definition.node_id, "b")
        self.assertEqual(set(definition.dependencies), {"a"})
        self.assertEqual(definition.priority, 1)
        self.assertEqual(definition.retries, 0)
        self.assertEqual(self.sut.get_dependencies("b"), {"a"})
        self.assertEqual(self.sut.get_dependents("a"), {"b"})

    def test_add_node_duplicate_identifier_raises(self) -> None:
        """An already registered identifier is rejected with DuplicateNodeError."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        with self.assertRaises(dag_engine_lite.DuplicateNodeError) as context:
            self.sut.add_node("a", no_op_action, None, 0, 0)
        self.assertEqual(context.exception.node_id, "a")
        self.assertEqual(self.sut.all_nodes(), {"a"})

    def test_add_node_defers_missing_dependency_validation(self) -> None:
        """Unknown dependencies are accepted at insertion time and reported by validate()."""
        self.sut.add_node("orphan", no_op_action, ["ghost"], 0, 0)
        self.assertTrue(self.sut.has_node("orphan"))
        self.assertEqual(self.sut.get_dependencies("orphan"), {"ghost"})
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as context:
            self.sut.validate()
        self.assertEqual(context.exception.node_id, "ghost")

    def test_add_edge_connects_nodes(self) -> None:
        """An explicit edge makes the downstream node depend on the upstream node."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, None, 0, 0)
        self.sut.add_edge("a", "b")
        self.assertEqual(self.sut.get_dependencies("b"), {"a"})
        self.assertEqual(self.sut.get_dependents("a"), {"b"})
        self.assertIsNone(self.sut.validate())

    def test_add_edge_unknown_node_raises(self) -> None:
        """Edges that reference unknown endpoints are rejected with NodeNotFoundError."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as downstream_context:
            self.sut.add_edge("a", "ghost")
        self.assertEqual(downstream_context.exception.node_id, "ghost")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as upstream_context:
            self.sut.add_edge("ghost", "a")
        self.assertEqual(upstream_context.exception.node_id, "ghost")

    def test_remove_node_purges_incident_edges(self) -> None:
        """Removing a node deletes it and purges all of its incident edges."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        self.sut.add_node("c", no_op_action, ["b"], 0, 0)
        self.sut.remove_node("b")
        self.assertFalse(self.sut.has_node("b"))
        self.assertEqual(self.sut.all_nodes(), {"a", "c"})
        self.assertEqual(self.sut.get_dependents("a"), set())
        self.assertEqual(self.sut.get_dependencies("c"), set())

    def test_remove_node_unknown_raises(self) -> None:
        """Removing an unknown node is rejected with NodeNotFoundError."""
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as context:
            self.sut.remove_node("ghost")
        self.assertEqual(context.exception.node_id, "ghost")

    def test_get_node_returns_registered_definition(self) -> None:
        """A registered definition is returned verbatim for its identifier."""
        self.sut.add_node("a", no_op_action, None, 3, 1)
        definition = self.sut.get_node("a")
        self.assertEqual(definition.node_id, "a")
        self.assertEqual(definition.priority, 3)
        self.assertEqual(definition.retries, 1)
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as context:
            self.sut.get_node("ghost")
        self.assertEqual(context.exception.node_id, "ghost")

    def test_neighbor_lookup_unknown_node_raises(self) -> None:
        """Neighbor lookups for unknown nodes are rejected with NodeNotFoundError."""
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as dependencies_context:
            self.sut.get_dependencies("ghost")
        self.assertEqual(dependencies_context.exception.node_id, "ghost")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as dependents_context:
            self.sut.get_dependents("ghost")
        self.assertEqual(dependents_context.exception.node_id, "ghost")

    def test_all_nodes_returns_copy_of_registered_nodes(self) -> None:
        """The reported identifier set is a copy, so mutating it leaves the graph intact."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        nodes = self.sut.all_nodes()
        self.assertEqual(nodes, {"a"})
        nodes.add("mutated")
        self.assertFalse(self.sut.has_node("mutated"))
        self.assertEqual(self.sut.all_nodes(), {"a"})

    def test_validate_accepts_valid_graph(self) -> None:
        """A complete acyclic graph validates without raising."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        self.sut.add_node("c", no_op_action, ["b"], 0, 0)
        self.assertIsNone(self.sut.validate())

    def test_validate_cycle_raises_cycle_error(self) -> None:
        """A directed cycle is rejected with CycleError carrying the cycle identifiers."""
        self.sut.add_node("a", no_op_action, ["b"], 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        with self.assertRaises(dag_engine_lite.CycleError) as context:
            self.sut.validate()
        self.assertEqual(set(context.exception.cycle), {"a", "b"})

    def test_topological_sort_orders_dependencies_first(self) -> None:
        """Every prerequisite precedes its dependents in the reported order."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        self.sut.add_node("c", no_op_action, ["b"], 0, 0)
        self.assertEqual(self.sut.topological_sort(), ["a", "b", "c"])

    def test_topological_sort_tie_breaks_by_priority_then_identifier(self) -> None:
        """Concurrent nodes are ordered by priority descending, then identifier ascending."""
        self.sut.add_node("gamma", no_op_action, None, 1, 0)
        self.sut.add_node("beta", no_op_action, None, 7, 0)
        self.sut.add_node("alpha", no_op_action, None, 7, 0)
        self.assertEqual(self.sut.topological_sort(), ["alpha", "beta", "gamma"])

    def test_topological_sort_cycle_raises_cycle_error(self) -> None:
        """A cyclic graph is rejected with CycleError while ordering the nodes."""
        self.sut.add_node("a", no_op_action, ["b"], 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        with self.assertRaises(dag_engine_lite.CycleError) as context:
            self.sut.topological_sort()
        self.assertEqual(set(context.exception.cycle), {"a", "b"})

    def test_find_roots_and_leaves(self) -> None:
        """Roots have no dependencies while leaves have no dependents."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        self.sut.add_node("c", no_op_action, ["b"], 0, 0)
        self.sut.add_node("d", no_op_action, None, 0, 0)
        self.assertEqual(self.sut.find_roots(), {"a", "d"})
        self.assertEqual(self.sut.find_leaves(), {"c", "d"})

    def test_compute_critical_path_longest_weighted_path(self) -> None:
        """The longest weighted path and its cumulative weight are reported."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        self.sut.add_node("c", no_op_action, ["a"], 0, 0)
        self.sut.add_node("d", no_op_action, ["b", "c"], 0, 0)
        path, weight = self.sut.compute_critical_path(
            {"a": 2.0, "b": 3.0, "c": 5.0, "d": 1.0}
        )
        self.assertEqual(path, ["a", "c", "d"])
        self.assertAlmostEqual(weight, 8.0)

    def test_compute_critical_path_defaults_missing_durations(self) -> None:
        """Nodes absent from the duration map contribute a unit weight each."""
        self.sut.add_node("a", no_op_action, None, 0, 0)
        self.sut.add_node("b", no_op_action, ["a"], 0, 0)
        path, weight = self.sut.compute_critical_path({"a": 4.0})
        self.assertEqual(path, ["a", "b"])
        self.assertAlmostEqual(weight, 5.0)

    def test_compute_critical_path_empty_graph_yields_empty_path(self) -> None:
        """A graph without nodes yields an empty path and a zero cumulative weight."""
        path, weight = self.sut.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)


class WaveSchedulerServiceTest(LifecycleTestCase):
    """Tests for the sequential wave scheduler service."""

    target = WaveSchedulerService

    @fake(dag_engine_lite.DAG)
    class FakeDAG(GraphDouble):
        """In-memory DAG double supplying graph topology to the scheduler."""

    def scheduler_dag(self) -> GraphDouble:
        return self.fakes[dag_engine_lite.DAG]

    def test_next_wave_returns_ready_roots_in_priority_order(self) -> None:
        """Only root nodes are ready, ordered by priority descending then identifier ascending."""
        dag = self.scheduler_dag()
        dag.seed_node("gamma", priority=1)
        dag.seed_node("beta", priority=7)
        dag.seed_node("alpha", priority=7)
        dag.seed_node("delta", priority=9, dependencies=("beta",))
        self.assertEqual(self.sut.next_wave(), ["alpha", "beta", "gamma"])

    def test_next_wave_returns_empty_list_for_empty_graph(self) -> None:
        """An empty graph yields an empty wave."""
        self.assertEqual(self.sut.next_wave(), [])

    def test_mark_running_transitions_state(self) -> None:
        """A dispatched node reports the RUNNING state."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.assertEqual(self.sut.get_state("a"), dag_engine_lite.NodeState.RUNNING)

    def test_mark_succeeded_promotes_newly_unblocked_dependents(self) -> None:
        """Succeeding a node promotes dependents whose dependencies have all succeeded."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b", dependencies=("a",))
        dag.seed_node("c", dependencies=("a", "b"))
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("a"), dag_engine_lite.NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("b"), dag_engine_lite.NodeState.READY)
        self.assertEqual(self.sut.get_state("c"), dag_engine_lite.NodeState.PENDING)
        self.assertEqual(self.sut.next_wave(), ["b"])
        self.sut.mark_running("b")
        self.sut.mark_succeeded("b")
        self.assertEqual(self.sut.get_state("c"), dag_engine_lite.NodeState.READY)
        self.assertEqual(self.sut.next_wave(), ["c"])

    def test_mark_succeeded_leaves_skipped_dependent_skipped(self) -> None:
        """A dependent already skipped by an upstream failure is not promoted to ready."""
        dag = self.scheduler_dag()
        dag.seed_node("start")
        dag.seed_node("failing")
        dag.seed_node("merge", dependencies=("start", "failing"))
        dag.seed_node("tail", dependencies=("merge",))
        self.assertEqual(self.sut.next_wave(), ["failing", "start"])
        self.sut.mark_running("failing")
        self.sut.mark_failed("failing", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("merge"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("tail"), dag_engine_lite.NodeState.SKIPPED)
        self.sut.mark_running("start")
        self.sut.mark_succeeded("start")
        self.assertEqual(self.sut.get_state("start"), dag_engine_lite.NodeState.SUCCEEDED)
        self.assertEqual(self.sut.get_state("merge"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("tail"), dag_engine_lite.NodeState.SKIPPED)
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_skip_downstream_skips_transitive_dependents(self) -> None:
        """Failing with skip-downstream transitions every transitive dependent to SKIPPED."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b", dependencies=("a",))
        dag.seed_node("c", dependencies=("b",))
        dag.seed_node("independent")
        self.assertEqual(self.sut.next_wave(), ["a", "independent"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("a"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(self.sut.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("c"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("independent"), dag_engine_lite.NodeState.READY)

    def test_mark_failed_skip_downstream_skips_reconvergent_diamond(self) -> None:
        """Skip-downstream skips both diamond branches and their reconvergent join."""
        dag = self.scheduler_dag()
        dag.seed_node("top")
        dag.seed_node("left", dependencies=("top",))
        dag.seed_node("right", dependencies=("top",))
        dag.seed_node("join", dependencies=("left", "right"))
        self.assertEqual(self.sut.next_wave(), ["top"])
        self.sut.mark_running("top")
        self.sut.mark_failed("top", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("top"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(self.sut.get_state("left"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("right"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("join"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.next_wave(), [])
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_skip_downstream_skips_reconvergent_shortcut(self) -> None:
        """A dependent reachable directly and by a longer path is skipped exactly once."""
        dag = self.scheduler_dag()
        dag.seed_node("top")
        dag.seed_node("middle", dependencies=("top",))
        dag.seed_node("join", dependencies=("top", "middle"))
        self.assertEqual(self.sut.next_wave(), ["top"])
        self.sut.mark_running("top")
        self.sut.mark_failed("top", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.sut.get_state("top"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(self.sut.get_state("middle"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("join"), dag_engine_lite.NodeState.SKIPPED)
        states = self.sut.get_all_states()
        self.assertEqual(
            set(states.keys()), {"top", "middle", "join"}
        )
        self.assertEqual(self.sut.next_wave(), [])
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_fail_fast_cancels_pending_nodes(self) -> None:
        """Failing with fail-fast cancels the remaining pending nodes."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b", dependencies=("a",))
        dag.seed_node("c", dependencies=("b",))
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(self.sut.get_state("a"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(self.sut.get_state("b"), dag_engine_lite.NodeState.CANCELLED)
        self.assertEqual(self.sut.get_state("c"), dag_engine_lite.NodeState.CANCELLED)
        self.assertTrue(self.sut.is_finished())

    def test_mark_failed_continue_on_error_keeps_independent_nodes_eligible(self) -> None:
        """Failing with continue-on-error skips blocked dependents but keeps independents ready."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b", dependencies=("a",))
        dag.seed_node("independent")
        self.assertEqual(self.sut.next_wave(), ["a", "independent"])
        self.sut.mark_running("a")
        self.sut.mark_failed("a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(self.sut.get_state("a"), dag_engine_lite.NodeState.FAILED)
        self.assertEqual(self.sut.get_state("b"), dag_engine_lite.NodeState.SKIPPED)
        self.assertEqual(self.sut.get_state("independent"), dag_engine_lite.NodeState.READY)
        self.assertEqual(self.sut.next_wave(), ["independent"])

    def test_is_finished_true_when_all_nodes_terminal(self) -> None:
        """The scheduler reports finished once every node is terminal."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b")
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.sut.mark_running("b")
        self.sut.mark_succeeded("b")
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_true_for_empty_dag(self) -> None:
        """An empty graph is already finished."""
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_false_when_ready_nodes_remain(self) -> None:
        """Runnable nodes keep the scheduler unfinished."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b")
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.next_wave(), ["b"])
        self.assertFalse(self.sut.is_finished())

    def test_is_finished_false_while_dependency_pending(self) -> None:
        """A dependent whose dependency has not succeeded keeps the scheduler unfinished."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b", dependencies=("a",))
        self.assertEqual(self.sut.next_wave(), ["a"])
        self.assertEqual(self.sut.get_state("b"), dag_engine_lite.NodeState.PENDING)
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        self.assertEqual(self.sut.get_state("b"), dag_engine_lite.NodeState.READY)
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_running("b")
        self.sut.mark_succeeded("b")
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_false_when_dependent_registered_after_upstream_succeeded(self) -> None:
        """A dependent added after its upstream succeeded is pending yet unfinished."""
        dag = self.scheduler_dag()
        dag.seed_node("upstream")
        self.assertEqual(self.sut.next_wave(), ["upstream"])
        self.sut.mark_running("upstream")
        self.sut.mark_succeeded("upstream")
        self.assertTrue(self.sut.is_finished())
        dag.seed_node("late_dependent", dependencies=("upstream",))
        self.assertEqual(
            self.sut.get_state("late_dependent"),
            dag_engine_lite.NodeState.PENDING,
        )
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_running("late_dependent")
        self.sut.mark_succeeded("late_dependent")
        self.assertTrue(self.sut.is_finished())

    def test_is_finished_with_pending_dependent_visited_before_ready_root(self) -> None:
        """Blocked dependents inspected ahead of a runnable root keep the scheduler unfinished."""
        dag = self.scheduler_dag()
        dag.seed_node("alpha_pending_dependent", dependencies=("delta_gated_parent",))
        dag.seed_node("beta_pending_dependent", dependencies=("delta_gated_parent",))
        dag.seed_node("gamma_pending_dependent", dependencies=("delta_gated_parent",))
        dag.seed_node("delta_gated_parent", dependencies=("zeta_ready_root",))
        dag.seed_node("zeta_ready_root")
        self.assertEqual(self.sut.next_wave(), ["zeta_ready_root"])
        self.assertEqual(
            self.sut.get_state("alpha_pending_dependent"),
            dag_engine_lite.NodeState.PENDING,
        )
        self.assertEqual(
            self.sut.get_state("beta_pending_dependent"),
            dag_engine_lite.NodeState.PENDING,
        )
        self.assertEqual(
            self.sut.get_state("gamma_pending_dependent"),
            dag_engine_lite.NodeState.PENDING,
        )
        self.assertEqual(
            self.sut.get_state("delta_gated_parent"),
            dag_engine_lite.NodeState.PENDING,
        )
        self.assertEqual(
            self.sut.get_state("zeta_ready_root"),
            dag_engine_lite.NodeState.READY,
        )
        self.assertFalse(self.sut.is_finished())
        self.sut.mark_running("zeta_ready_root")
        self.sut.mark_succeeded("zeta_ready_root")
        self.assertEqual(
            self.sut.get_state("delta_gated_parent"),
            dag_engine_lite.NodeState.READY,
        )
        self.assertFalse(self.sut.is_finished())

    def test_is_finished_true_when_remaining_nodes_blocked_by_failure(self) -> None:
        """Nodes blocked by a failure end the scheduler run."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b", dependencies=("a",))
        self.sut.mark_running("a")
        self.sut.mark_failed("a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertTrue(self.sut.is_finished())

    def test_get_state_unknown_node_raises_node_not_found(self) -> None:
        """Querying an unknown node is rejected with NodeNotFoundError."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as context:
            self.sut.get_state("ghost")
        self.assertEqual(context.exception.node_id, "ghost")

    def test_get_all_states_reports_registered_nodes(self) -> None:
        """Reported states cover exactly the nodes currently registered in the graph."""
        dag = self.scheduler_dag()
        dag.seed_node("a")
        dag.seed_node("b")
        self.assertEqual(self.sut.next_wave(), ["a", "b"])
        states = self.sut.get_all_states()
        self.assertEqual(set(states.keys()), {"a", "b"})
        self.assertEqual(states["a"], dag_engine_lite.NodeState.READY)
        self.sut.mark_running("a")
        self.sut.mark_succeeded("a")
        dag.remove_node("b")
        filtered_states = self.sut.get_all_states()
        self.assertEqual(set(filtered_states.keys()), {"a"})
        self.assertEqual(filtered_states["a"], dag_engine_lite.NodeState.SUCCEEDED)


class DAGRunnerServiceTest(LifecycleTestCase):
    """Tests for the sequential DAG execution runner service."""

    target = DAGRunnerService

    @fake(dag_engine_lite.DAG)
    class FakeDAG(GraphDouble):
        """In-memory DAG double supplying definitions and actions to the runner."""

    @fake(dag_engine_lite.WaveScheduler)
    class FakeWaveScheduler(WaveSchedulerDouble):
        """Scripted wave scheduler double supplying the runner wave sequence."""

    def runner_dag(self) -> GraphDouble:
        return self.fakes[dag_engine_lite.DAG]

    def runner_scheduler(self) -> WaveSchedulerDouble:
        return self.fakes[dag_engine_lite.WaveScheduler]

    def test_run_executes_waves_sequentially_and_builds_report(self) -> None:
        """All waves run in order and the consolidated report records every outcome."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        calls: list[str] = []

        def record_a() -> None:
            calls.append("a")

        def record_b() -> None:
            calls.append("b")

        dag.seed_node("a", priority=2, action=record_a)
        dag.seed_node("b", priority=1, dependencies=("a",), action=record_b)
        dag.critical_path = ["a", "b"]
        dag.critical_path_weight = 2.0
        scheduler.waves = [["a"], ["b"]]
        report = self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(calls, ["a", "b"])
        self.assertEqual(scheduler.started, ["a", "b"])
        self.assertEqual(scheduler.completed, ["a", "b"])
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(set(report.succeeded_nodes), {"a", "b"})
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(tuple(report.critical_path), ("a", "b"))
        self.assertGreaterEqual(report.wall_clock_seconds, 0.0)
        self.assertEqual(report.results["a"].state, dag_engine_lite.NodeState.SUCCEEDED)
        self.assertEqual(report.results["b"].state, dag_engine_lite.NodeState.SUCCEEDED)

    def test_run_halts_on_empty_wave_before_finish(self) -> None:
        """An empty wave halts the sequential loop and a consolidated report is returned."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        executed: list[str] = []

        def record_a() -> None:
            executed.append("a")

        dag.seed_node("a", action=record_a)
        dag.critical_path = ["a"]
        dag.critical_path_weight = 1.0
        scheduler.waves = [[]]
        report = self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(executed, [])
        self.assertEqual(scheduler.started, [])
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(report.succeeded_nodes, ())
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(tuple(report.critical_path), ("a",))
        self.assertEqual(dict(report.results), {})

    def test_run_records_defaults_for_unexecuted_terminal_nodes(self) -> None:
        """Skipped and cancelled nodes recorded only in scheduler states get default results."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()

        def record_a() -> None:
            return None

        dag.seed_node("a", action=record_a)
        dag.seed_node("b", dependencies=("a",))
        dag.seed_node("c", dependencies=("a",))
        dag.critical_path = ["a"]
        dag.critical_path_weight = 1.0
        scheduler.waves = [["a"]]
        scheduler.states["b"] = dag_engine_lite.NodeState.SKIPPED
        scheduler.states["c"] = dag_engine_lite.NodeState.CANCELLED
        report = self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.total_nodes, 3)
        self.assertEqual(report.succeeded_nodes, ("a",))
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ("b",))
        self.assertEqual(report.cancelled_nodes, ("c",))
        skipped_record = report.results["b"]
        self.assertEqual(skipped_record.node_id, "b")
        self.assertEqual(skipped_record.state, dag_engine_lite.NodeState.SKIPPED)
        self.assertIsNone(skipped_record.value)
        self.assertIsNone(skipped_record.error)
        self.assertEqual(skipped_record.duration_seconds, 0.0)
        self.assertEqual(skipped_record.retries_attempted, 0)
        cancelled_record = report.results["c"]
        self.assertEqual(cancelled_record.node_id, "c")
        self.assertEqual(cancelled_record.state, dag_engine_lite.NodeState.CANCELLED)
        self.assertIsNone(cancelled_record.value)
        self.assertIsNone(cancelled_record.error)
        self.assertEqual(cancelled_record.duration_seconds, 0.0)
        self.assertEqual(cancelled_record.retries_attempted, 0)

    def test_run_retries_failed_action_until_success(self) -> None:
        """Configured retries are attempted before a success outcome is recorded."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        attempts: list[int] = []

        def flaky_action() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient failure")
            return "completed"

        dag.seed_node("retry", action=flaky_action, retries=2)
        scheduler.waves = [["retry"]]
        report = self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(len(attempts), 3)
        record = report.results["retry"]
        self.assertEqual(record.state, dag_engine_lite.NodeState.SUCCEEDED)
        self.assertEqual(record.value, "completed")
        self.assertEqual(record.retries_attempted, 2)
        self.assertEqual(report.succeeded_nodes, ("retry",))

    def test_run_marks_node_failed_after_retries_exhausted(self) -> None:
        """Exhausted retries record a failure and apply the requested failure policy."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        attempts: list[int] = []

        def failing_action() -> None:
            attempts.append(1)
            raise RuntimeError("boom")

        dag.seed_node("bad", action=failing_action, retries=1)
        scheduler.waves = [["bad"]]
        report = self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(report.results["bad"].state, dag_engine_lite.NodeState.FAILED)
        self.assertEqual(report.failed_nodes, ("bad",))
        self.assertEqual(
            scheduler.failures,
            [("bad", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)],
        )

    def test_run_fail_fast_halts_remaining_waves(self) -> None:
        """A fail-fast failure stops dispatching of later waves."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        executed: list[str] = []

        def record_a() -> None:
            executed.append("a")

        def failing_b() -> None:
            executed.append("b")
            raise RuntimeError("boom")

        def record_c() -> None:
            executed.append("c")

        dag.seed_node("a", action=record_a)
        dag.seed_node("b", action=failing_b)
        dag.seed_node("c", action=record_c)
        scheduler.waves = [["a"], ["b"], ["c"]]
        report = self.sut.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.assertEqual(executed, ["a", "b"])
        self.assertEqual(
            scheduler.failures,
            [("b", dag_engine_lite.FailurePolicy.FAIL_FAST)],
        )
        self.assertEqual(report.results["b"].state, dag_engine_lite.NodeState.FAILED)

    def test_run_propagates_cycle_error_from_validation(self) -> None:
        """A validation cycle aborts the run before any wave is dispatched."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        executed: list[str] = []

        def record_a() -> None:
            executed.append("a")

        dag.seed_node("a", action=record_a)
        dag.validate_error = dag_engine_lite.CycleError(
            message="cycle detected", cycle=("a", "b")
        )
        scheduler.waves = [["a"]]
        with self.assertRaises(dag_engine_lite.CycleError):
            self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(executed, [])
        self.assertEqual(scheduler.started, [])

    def test_run_propagates_node_not_found_error_from_validation(self) -> None:
        """A missing dependency aborts the run before any wave is dispatched."""
        dag = self.runner_dag()
        scheduler = self.runner_scheduler()
        executed: list[str] = []

        def record_a() -> None:
            executed.append("a")

        dag.seed_node("a", action=record_a)
        dag.validate_error = dag_engine_lite.NodeNotFoundError(
            message="missing dependency", node_id="ghost"
        )
        scheduler.waves = [["a"]]
        with self.assertRaises(dag_engine_lite.NodeNotFoundError) as context:
            self.sut.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(context.exception.node_id, "ghost")
        self.assertEqual(executed, [])
        self.assertEqual(scheduler.started, [])


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T00:37:05Z
# LAST_CHANGED: 2026-11-12T00:36:16Z
# CHANGE: Add is_finished branch-coverage test for a dependent node registered after its upstream already succeeded: the scheduler synchronizes the late node as PENDING while all its dependencies are SUCCEEDED, so it remains non-terminal and eligible, asserting is_finished() is False, then transitions it to SUCCEEDED and asserts is_finished() is True.
# COVERAGE_AUDIT: 2026-11-12T00:37:05Z
# QA_AUDIT: 2026-11-12T00:36:42Z
# --- END AUTOFAB METADATA ---
