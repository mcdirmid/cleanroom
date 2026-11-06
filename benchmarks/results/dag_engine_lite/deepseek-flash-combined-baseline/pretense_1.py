# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from pretense import (
    call_target,
    raises,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteState,
    DagEngineLiteStateMachine,
)
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
)


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
    ) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
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
        self.sm = DagEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.wavescheduler,
                DAGRunner: self.dagrunner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_dag_add_inspect_and_analyze(self) -> None:
        """Verify registration, adjacency, traversal, ordering, and path analysis."""
        self.checked_dag.add_node("a", lambda: "A", None, 1, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.assertTrue(self.checked_dag.has_node("a"))
        self.assertFalse(self.checked_dag.has_node("missing"))
        self.assertEqual(self.checked_dag.get_node("b").node_id, "b")
        self.assertEqual(self.checked_dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.checked_dag.get_dependents("a"), {"b"})
        self.assertEqual(self.checked_dag.all_nodes(), {"a", "b"})
        self.assertEqual(self.checked_dag.find_roots(), {"a"})
        self.assertEqual(self.checked_dag.find_leaves(), {"b"})
        self.assertEqual(self.checked_dag.topological_sort(), ["a", "b"])
        path, weight = self.checked_dag.compute_critical_path(None)
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 2.0)
        weighted, weighted_total = self.checked_dag.compute_critical_path(
            {"a": 4.0, "b": 1.0}
        )
        self.assertEqual(weighted, ["a", "b"])
        self.assertEqual(weighted_total, 5.0)
        self.checked_dag.validate()

    def test_dag_add_edge_and_remove(self) -> None:
        """Verify explicit edge insertion and incident edge removal."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", None, 0, 0)
        self.checked_dag.add_node("c", lambda: "C", None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "c")
        self.assertEqual(self.checked_dag.get_dependents("a"), {"b"})
        self.checked_dag.remove_node("b")
        self.assertEqual(self.checked_dag.all_nodes(), {"a", "c"})
        self.assertEqual(self.checked_dag.get_dependents("a"), set())
        self.assertEqual(self.checked_dag.get_dependencies("c"), set())

    def test_scheduler_wave_flow(self) -> None:
        """Verify wave resolution, state transitions, and completion."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.assertEqual(self.checked_wavescheduler.next_wave(), ["a"])
        self.assertIs(self.checked_wavescheduler.get_state("a"), NodeState.READY)
        self.checked_wavescheduler.mark_running("a")
        self.assertIs(self.checked_wavescheduler.get_state("a"), NodeState.RUNNING)
        self.checked_wavescheduler.mark_succeeded("a")
        self.assertEqual(self.checked_wavescheduler.next_wave(), ["b"])
        self.checked_wavescheduler.mark_succeeded("b")
        self.assertTrue(self.checked_wavescheduler.is_finished())
        self.assertEqual(
            dict(self.checked_wavescheduler.get_all_states()),
            {"a": NodeState.SUCCEEDED, "b": NodeState.SUCCEEDED},
        )

    def test_scheduler_fail_fast(self) -> None:
        """Verify FAIL_FAST cancels the remaining unexecuted nodes."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertIs(self.checked_wavescheduler.get_state("b"), NodeState.CANCELLED)
        self.assertTrue(self.checked_wavescheduler.is_finished())

    def test_scheduler_skip_downstream(self) -> None:
        """Verify SKIP_DOWNSTREAM skips transitive dependents."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: "C", ["b"], 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIs(self.checked_wavescheduler.get_state("b"), NodeState.SKIPPED)
        self.assertIs(self.checked_wavescheduler.get_state("c"), NodeState.SKIPPED)

    def test_scheduler_continue_on_error(self) -> None:
        """Verify CONTINUE_ON_ERROR leaves independent nodes eligible."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.checked_dag.add_node("d", lambda: "D", None, 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIs(self.checked_wavescheduler.get_state("b"), NodeState.SKIPPED)
        self.assertFalse(self.checked_wavescheduler.is_finished())
        self.assertEqual(self.checked_wavescheduler.next_wave(), ["d"])

    def test_scheduler_empty_graph(self) -> None:
        """Verify an empty graph is finished and yields no waves."""
        self.assertTrue(self.checked_wavescheduler.is_finished())
        self.assertEqual(self.checked_wavescheduler.next_wave(), [])
        self.assertEqual(dict(self.checked_wavescheduler.get_all_states()), {})

    def test_scheduler_remove_purges_tracking(self) -> None:
        """Verify removal purges scheduler tracking state."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.assertEqual(self.checked_wavescheduler.next_wave(), ["a"])
        self.checked_dag.remove_node("a")
        states = self.checked_wavescheduler.get_all_states()
        self.assertNotIn("a", states)
        self.assertIn("b", states)

    def test_scheduler_diamond_skip(self) -> None:
        """Verify converging dependents are traversed once and skipped."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.checked_dag.add_node("c", lambda: "C", ["a"], 0, 0)
        self.checked_dag.add_node("d", lambda: "D", ["b", "c"], 0, 0)
        self.checked_wavescheduler.mark_failed("a", FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIs(self.checked_wavescheduler.get_state("d"), NodeState.SKIPPED)

    def test_critical_path_empty_graph(self) -> None:
        """Verify the empty graph critical path closure."""
        path, weight = self.checked_dag.compute_critical_path(None)
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_contracted_errors(self) -> None:
        """Verify checked preconditions surface contracted errors."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        with self.assertRaises(DuplicateNodeError):
            self.dag.add_node("a", lambda: "A", None, 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "a")
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")
        with self.assertRaises(NodeNotFoundError):
            self.wavescheduler.get_state("missing")

    def test_missing_dependency_validation(self) -> None:
        """Verify deferred dependency existence checks surface on validation."""
        self.checked_dag.add_node("a", lambda: "A", ["ghost"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()
        with self.assertRaises(NodeNotFoundError):
            self.dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_cycle_violations(self) -> None:
        """Verify cycle detection surfaces on validation, ordering, and execution."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        with self.assertRaises(CycleError):
            self.dag.validate()
        with self.assertRaises(CycleError):
            self.dag.topological_sort()
        with self.assertRaises(CycleError):
            self.dag.compute_critical_path(None)
        with self.assertRaises(CycleError):
            self.dagrunner.run(FailurePolicy.FAIL_FAST)

    def test_runner_success(self) -> None:
        """Verify successful sequential execution and reporting."""
        self.checked_dag.add_node("a", lambda: "A", None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("a", "b"))
        self.assertEqual(report.results["a"].value, "A")
        self.assertEqual(report.critical_path, ("a", "b"))

    def test_runner_retries(self) -> None:
        """Verify retry attempts before success."""
        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient")
            return "recovered"

        self.checked_dag.add_node("a", flaky, None, 0, 1)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.succeeded_nodes, ("a",))
        self.assertEqual(report.results["a"].retries_attempted, 1)

    def test_runner_fail_fast(self) -> None:
        """Verify FAIL_FAST halts and cancels dependent work."""
        self.checked_dag.add_node("a", _boom, None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.cancelled_nodes, ("b",))

    def test_runner_skip_downstream(self) -> None:
        """Verify SKIP_DOWNSTREAM skips dependents of a failure."""
        self.checked_dag.add_node("a", _boom, None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.skipped_nodes, ("b",))

    def test_runner_continue_on_error(self) -> None:
        """Verify CONTINUE_ON_ERROR executes independent nodes."""
        self.checked_dag.add_node("a", _boom, None, 0, 0)
        self.checked_dag.add_node("b", lambda: "B", ["a"], 0, 0)
        self.checked_dag.add_node("d", lambda: "D", None, 0, 0)
        report = self.checked_dagrunner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.skipped_nodes, ("b",))
        self.assertEqual(report.succeeded_nodes, ("d",))


def _boom() -> int:
    raise RuntimeError("boom")


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
        self.__dict__["_services"] = (self.dag, self.wavescheduler, self.dagrunner)

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
# LAST_CLEANED: 2026-11-05T21:08:20Z
# LAST_CHANGED: 2026-11-05T21:08:20Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: b3c8d448d293
# COVERAGE_AUDIT: 2026-11-05T21:08:20Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T21:08:20Z
# PRETENSE_QA_AUDIT: 2026-11-05T21:08:20Z
# QA_AUDIT: 2026-11-05T21:08:20Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

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
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAG,
    DAGError,
    DAGRunReport,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
    DAGRunner,
)


# ==============================================================================
# Graph model helpers
# ==============================================================================

_CANDIDATE_IDS: Tuple[str, ...] = (
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
)


def _cycle_nodes(
    nodes: Mapping[str, Any],
    downstream: Mapping[str, Set[str]],
) -> Tuple[str, ...]:
    """Returns the node identifiers forming a directed cycle, or an empty tuple."""
    colors: Dict[str, int] = {node_id: 0 for node_id in nodes}
    for start in sorted(nodes):
        if colors[start] != 0:
            continue
        colors[start] = 1
        path: List[str] = [start]
        stack: List[Tuple[str, Any]] = [(start, iter(sorted(downstream.get(start, set()))))]
        while stack:
            node_id, iterator = stack[-1]
            advanced = False
            for next_id in iterator:
                if colors.get(next_id) == 1:
                    index = path.index(next_id)
                    return tuple(path[index:] + [next_id])
                if colors.get(next_id) == 0:
                    colors[next_id] = 1
                    path.append(next_id)
                    stack.append((next_id, iter(sorted(downstream.get(next_id, set())))))
                    advanced = True
                    break
            if not advanced:
                stack.pop()
                colors[node_id] = 2
                path.pop()
    return ()


def _is_acyclic(nodes: Mapping[str, Any], downstream: Mapping[str, Set[str]]) -> bool:
    return not _cycle_nodes(nodes, downstream)


def _dependency_complete(
    nodes: Mapping[str, Any],
    upstream: Mapping[str, Set[str]],
) -> bool:
    for node_id in nodes:
        for dependency in upstream.get(node_id, set()):
            if dependency not in nodes:
                return False
    return True


def _transitive_dependents(
    downstream: Mapping[str, Set[str]],
    node_id: str,
) -> Set[str]:
    seen: Set[str] = set()
    pending: List[str] = list(downstream.get(node_id, set()))
    while pending:
        dependent = pending.pop()
        if dependent in seen:
            continue
        seen.add(dependent)
        pending.extend(downstream.get(dependent, set()))
    return seen


def _synchronize(
    states: Dict[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> None:
    for stale in list(states):
        if stale not in nodes:
            del states[stale]
    for node_id in nodes:
        if node_id not in states:
            if upstream.get(node_id):
                states[node_id] = NodeState.PENDING
            else:
                states[node_id] = NodeState.READY


def _is_terminal(state: Optional[NodeState]) -> bool:
    return state in (
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    )


def _ready_wave(
    states: Mapping[str, NodeState],
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
) -> List[str]:
    candidates = [
        node_id
        for node_id in nodes
        if states.get(node_id) is NodeState.READY
        and all(
            states.get(dependency) is NodeState.SUCCEEDED
            for dependency in upstream.get(node_id, set())
        )
    ]
    candidates.sort(key=lambda node_id: (-nodes[node_id].priority, node_id))
    return candidates


def _topological_order(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
) -> List[str]:
    in_degree = {node_id: len(upstream.get(node_id, set())) for node_id in nodes}
    ready = sorted(
        (node_id for node_id in nodes if in_degree[node_id] == 0),
        key=lambda node_id: (-nodes[node_id].priority, node_id),
    )
    order: List[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for downstream_id in sorted(downstream.get(node_id, set())):
            in_degree[downstream_id] -= 1
            if in_degree[downstream_id] == 0:
                ready.append(downstream_id)
                ready.sort(key=lambda item: (-nodes[item].priority, item))
    return order


def _critical_path(
    nodes: Mapping[str, NodeDefinition[Any]],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    estimated_durations: Optional[Mapping[str, float]],
) -> Tuple[List[str], float]:
    order = _topological_order(nodes, upstream, downstream)
    if not order:
        return ([], 0.0)
    durations = {node_id: 1.0 for node_id in nodes}
    if estimated_durations is not None:
        for node_id, duration in estimated_durations.items():
            if node_id in durations:
                durations[node_id] = duration
    earliest: Dict[str, float] = {}
    for node_id in order:
        start = max(
            (earliest.get(predecessor, 0.0) for predecessor in upstream.get(node_id, set())),
            default=0.0,
        )
        earliest[node_id] = start + durations[node_id]
    terminal = order[0]
    for node_id in order:
        if earliest[node_id] > earliest[terminal]:
            terminal = node_id
    path: List[str] = [terminal]
    current = terminal
    while True:
        best: Optional[str] = None
        for predecessor in sorted(upstream.get(current, set())):
            if best is None or earliest.get(predecessor, 0.0) > earliest.get(best, 0.0):
                best = predecessor
        if best is None:
            break
        path.append(best)
        current = best
    path.reverse()
    return (path, earliest[terminal])


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""

    available: Set[str] = field(default_factory=lambda: set(_CANDIDATE_IDS))
    nodes: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    states: Dict[str, NodeState] = field(default_factory=dict)
    results: Dict[str, NodeResult[Any]] = field(default_factory=dict)
    acyclic: bool = True
    dependencies_complete: bool = True


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
        require_arg(node_id, Domain.in_set(self.state.available), preferred=["a"])
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(dependencies, Domain.type(Optional[Collection[str]]))
        require_arg(priority, Domain.range(0, 5), preferred=[0])
        require_arg(retries, Domain.range(0, 3), preferred=[0])
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies) if dependencies is not None else frozenset(),
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = definition
        self.state.upstream.setdefault(node_id, set())
        self.state.downstream.setdefault(node_id, set())
        for dependency in definition.dependencies:
            self.state.upstream[node_id].add(dependency)
            self.state.downstream.setdefault(dependency, set()).add(node_id)
        self.state.available.discard(node_id)
        self.state.acyclic = _is_acyclic(self.state.nodes, self.state.downstream)
        self.state.dependencies_complete = _dependency_complete(
            self.state.nodes, self.state.upstream
        )
        ret = make_return_value(None)
        assert node_id in self.state.nodes
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require_arg(upstream_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        require_arg(downstream_id, Domain.in_set(self.state.nodes.keys()), preferred=["b"])
        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream[upstream_id].add(downstream_id)
        self.state.acyclic = _is_acyclic(self.state.nodes, self.state.downstream)
        ret = make_return_value(None)
        assert upstream_id in self.state.upstream[downstream_id]
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        for upstream_id in self.state.upstream.get(node_id, set()):
            self.state.downstream.get(upstream_id, set()).discard(node_id)
        for downstream_id in self.state.downstream.get(node_id, set()):
            self.state.upstream.get(downstream_id, set()).discard(node_id)
        del self.state.nodes[node_id]
        del self.state.upstream[node_id]
        del self.state.downstream[node_id]
        self.state.available.add(node_id)
        self.state.acyclic = _is_acyclic(self.state.nodes, self.state.downstream)
        self.state.dependencies_complete = _dependency_complete(
            self.state.nodes, self.state.upstream
        )
        ret = make_return_value(None)
        assert node_id not in self.state.nodes
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require_arg(node_id, Domain.type(str), preferred=["a"])
        expected = node_id in self.state.nodes
        ret = make_return_value(expected)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        definition = self.state.nodes[node_id]
        ret = make_return_value(definition)
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        dependencies = set(self.state.upstream.get(node_id, set()))
        ret = make_return_value(dependencies)
        assert ret == self.state.upstream.get(node_id, set())
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        dependents = set(self.state.downstream.get(node_id, set()))
        ret = make_return_value(dependents)
        assert ret == self.state.downstream.get(node_id, set())
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        registered = set(self.state.nodes)
        ret = make_return_value(registered)
        assert ret == set(self.state.nodes)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.dependencies_complete)
        require(self.state.acyclic)
        ret = make_return_value(None)
        assert self.state.acyclic
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.acyclic)
        order = _topological_order(
            self.state.nodes, self.state.upstream, self.state.downstream
        )
        ret = make_return_value(order)
        assert sorted(ret) == sorted(self.state.nodes)
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        roots = {
            node_id
            for node_id in self.state.nodes
            if not self.state.upstream.get(node_id)
        }
        ret = make_return_value(roots)
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.upstream.get(node_id)
        }
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        leaves = {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        ret = make_return_value(leaves)
        assert ret == {
            node_id
            for node_id in self.state.nodes
            if not self.state.downstream.get(node_id)
        }
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.acyclic)
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
        )
        path, weight = _critical_path(
            self.state.nodes,
            self.state.upstream,
            self.state.downstream,
            estimated_durations,
        )
        ret = make_return_value((path, weight))
        assert len(ret) == 2
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        wave = _ready_wave(
            self.state.states, self.state.nodes, self.state.upstream
        )
        ret = make_return_value(wave)
        assert set(ret) <= set(self.state.nodes)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        self.state.states[node_id] = NodeState.RUNNING
        ret = make_return_value(None)
        assert self.state.states[node_id] is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        self.state.states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.downstream.get(node_id, set()):
            if self.state.states.get(dependent) is NodeState.PENDING:
                if all(
                    self.state.states.get(dependency) is NodeState.SUCCEEDED
                    for dependency in self.state.upstream.get(dependent, set())
                ):
                    self.state.states[dependent] = NodeState.READY
        ret = make_return_value(None)
        assert self.state.states[node_id] is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)), preferred=[FailurePolicy.FAIL_FAST])
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        self.state.states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other in self.state.nodes:
                if other == node_id:
                    continue
                if not _is_terminal(self.state.states.get(other)):
                    self.state.states[other] = NodeState.CANCELLED
        else:
            for dependent in _transitive_dependents(self.state.downstream, node_id):
                if not _is_terminal(self.state.states.get(dependent)):
                    self.state.states[dependent] = NodeState.SKIPPED
        ret = make_return_value(None)
        assert self.state.states[node_id] is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        finished = all(
            _is_terminal(self.state.states.get(node_id))
            for node_id in self.state.nodes
        ) or not any(
            self.state.states.get(node_id) is NodeState.READY
            and all(
                self.state.states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.upstream.get(node_id, set())
            )
            for node_id in self.state.nodes
        )
        ret = make_return_value(finished)
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=["a"])
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        state = self.state.states[node_id]
        ret = make_return_value(state)
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        snapshot = {
            node_id: self.state.states[node_id] for node_id in self.state.nodes
        }
        ret = make_return_value(snapshot)
        assert set(ret) == set(self.state.nodes)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.acyclic)
        require(self.state.dependencies_complete)
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)), preferred=[FailurePolicy.FAIL_FAST])
        _synchronize(self.state.states, self.state.nodes, self.state.upstream)
        for node_id in self.state.nodes:
            self.state.states[node_id] = NodeState.SUCCEEDED
        succeeded = tuple(sorted(self.state.nodes))
        report = DAGRunReport(
            total_nodes=len(self.state.nodes),
            succeeded_nodes=succeeded,
            failed_nodes=(),
            skipped_nodes=(),
            cancelled_nodes=(),
            wall_clock_seconds=0.0,
            critical_path=tuple(
                _critical_path(
                    self.state.nodes,
                    self.state.upstream,
                    self.state.downstream,
                    None,
                )[0]
            ),
            results={},
        )
        ret = make_return_value(report)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.available = set(_CANDIDATE_IDS)


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(
    state: Optional[DagEngineLiteState] = None,
) -> Any:
    return FakeDagEngineLite(state=state or DagEngineLiteState())


def make_dag_engine_lite_fakes(
    state: Optional[DagEngineLiteState] = None,
) -> Tuple[Any, Any, Any]:
    fake = FakeDagEngineLite(state=state or DagEngineLiteState())
    return (fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestDagEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DagEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.add_node("a", lambda: "A", None, 0, 0)
        self.fake.add_node("b", lambda: "B", ["a"], 0, 0)
        self.fake.add_edge("a", "b")
        self.fake.has_node("a")
        self.fake.get_node("a")
        self.fake.get_dependencies("b")
        self.fake.get_dependents("a")
        self.fake.find_roots()
        self.fake.find_leaves()
        self.fake.all_nodes()
        self.fake.validate()
        self.fake.topological_sort()
        self.fake.compute_critical_path(None)
        self.fake.next_wave()
        self.fake.mark_running("a")
        self.fake.mark_succeeded("a")
        self.fake.get_state("b")
        self.fake.get_all_states()
        self.fake.is_finished()
        self.fake.run(FailurePolicy.FAIL_FAST)
        self.fake.mark_failed("b", FailurePolicy.SKIP_DOWNSTREAM)
        self.fake.remove_node("b")
        self.fake.remove_node("a")

    def test_cycle_detection_on_fake(self) -> None:
        """Exercises cycle-triggered contract violations on the fake."""
        self.fake.add_node("a", lambda: "A", None, 0, 0)
        self.fake.add_node("b", lambda: "B", None, 0, 0)
        self.fake.add_edge("a", "b")
        self.fake.add_edge("b", "a")
        with raises(CycleError):
            self.fake.validate()
        with raises(CycleError):
            self.fake.topological_sort()
        with raises(CycleError):
            self.fake.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-05T21:08:20Z
# LAST_CHANGED: 2026-11-05T21:08:20Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 40a5941d6388
# COVERAGE_AUDIT: 2026-11-05T21:08:20Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-05T21:08:20Z
# PRETENSE_QA_AUDIT: 2026-11-05T21:08:20Z
# QA_AUDIT: 2026-11-05T21:08:20Z
# --- END AUTOFAB METADATA ---
