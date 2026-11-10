# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    StateMachine,
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    WaveScheduler,
    DAGRunner,
    CycleError,
    DAGError,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    DAGRunReport,
)
from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG as DAGImpl,
    WaveScheduler as WaveSchedulerImpl,
    DAGRunner as DAGRunnerImpl,
    __initialize__,
)
from benchmark_3.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineLiteState,
    DAGEngineLiteStateMachine,
)


_retry_state = {"count": 0}


def _dummy_action() -> str:
    """Default dummy action for node execution."""
    return "ok"


def _dummy_action_alt() -> int:
    """Alternative dummy action for node execution."""
    return 42


def _always_fail_action() -> str:
    """Action that raises an exception during node execution."""
    raise ValueError("Action execution failed")


def _retry_action() -> str:
    """Action that fails twice then succeeds."""
    _retry_state["count"] += 1
    if _retry_state["count"] <= 2:
        raise RuntimeError("Transient failure")
    return "recovered"


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DAGEngineLiteImplPseudoStateMachine(DAGEngineLiteStateMachine):
    """Implementation pseudo-state machine for DAGEngineLite delegating to real SUT."""

    # --- DAG Interface Transition Overrides ---

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
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        return ret

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        return ret

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        return ret

    # --- WaveScheduler Interface Transition Overrides ---

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        return ret

    # --- DAGRunner Interface Transition Overrides ---

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(failure_policy))
        return ret


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDAGEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.sm = DAGEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: self.dag,
                WaveScheduler: self.scheduler,
                DAGRunner: self.runner,
            }
        )
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_scheduler = self.sm.as_checked(WaveScheduler, self.scheduler)
        self.checked_runner = self.sm.as_checked(DAGRunner, self.runner)
        self.checked = self.checked_dag

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_dag_lifecycle_conformance(self) -> None:
        """Drives operational DAG lifecycle scenarios through checked proxies."""
        self.checked_dag.add_node("n1", _dummy_action, None, 1, 0)
        self.checked_dag.add_node("n2", _dummy_action_alt, ["n1"], 2, 0)
        self.checked_dag.add_node("n3", _dummy_action, ["n1"], 0, 0)
        self.checked_dag.add_edge("n2", "n3")

        _ = self.checked_dag.has_node("n1")
        _ = self.checked_dag.get_node("n1")
        _ = self.checked_dag.get_dependencies("n2")
        _ = self.checked_dag.get_dependents("n1")
        _ = self.checked_dag.all_nodes()
        self.checked_dag.validate()

        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.compute_critical_path({"n1": 2.0, "n2": 3.0, "n3": 1.0})

        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("n1")
        self.checked_scheduler.mark_succeeded("n1")
        self.checked_scheduler.mark_failed("n2", FailurePolicy.FAIL_FAST)
        _ = self.checked_scheduler.is_finished()
        _ = self.checked_scheduler.get_state("n2")
        _ = self.checked_scheduler.get_all_states()

        _ = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        self.checked_dag.remove_node("n3")

    def test_wave_scheduler_execution_conformance(self) -> None:
        """Drives sequential wave execution scenarios through checked proxies."""
        self.checked_dag.add_node("a", _dummy_action, None, 5, 1)
        self.checked_dag.add_node("b", _dummy_action_alt, ["a"], 10, 0)
        self.checked_dag.validate()

        wave1 = self.checked_scheduler.next_wave()
        assert "a" in wave1
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_succeeded("a")

        wave2 = self.checked_scheduler.next_wave()
        assert "b" in wave2
        self.checked_scheduler.mark_running("b")
        self.checked_scheduler.mark_succeeded("b")

        assert self.checked_scheduler.is_finished()

    def test_empty_dag_conformance(self) -> None:
        """Verifies empty graph behaviors and terminal contract evaluations."""
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0
        assert self.checked_scheduler.is_finished()
        assert self.checked_scheduler.next_wave() == []
        assert self.checked_scheduler.get_all_states() == {}
        assert self.checked_dag.find_roots() == set()
        assert self.checked_dag.find_leaves() == set()
        assert self.checked_dag.topological_sort() == []
        self.checked_dag.validate()

    def test_runner_sequential_waves(self) -> None:
        """Drives sequential wave execution in DAGRunner.run across multiple waves."""
        self.checked_dag.add_node("w1_a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("w1_b", _dummy_action_alt, None, 5, 0)
        self.checked_dag.add_node("w2_a", _dummy_action, ["w1_a", "w1_b"], 1, 0)
        self.checked_dag.add_node("w3_a", _dummy_action_alt, ["w2_a"], 1, 0)
        self.checked_dag.validate()

        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 4
        assert set(report.succeeded_nodes) == {"w1_a", "w1_b", "w2_a", "w3_a"}
        assert report.failed_nodes == ()
        assert report.skipped_nodes == ()
        assert report.cancelled_nodes == ()
        assert self.checked_scheduler.is_finished()
        assert self.checked_scheduler.get_state("w3_a") == NodeState.SUCCEEDED

    def test_runner_retries_conformance(self) -> None:
        """Drives node retry attempts up to configured retries in DAGRunner.run."""
        _retry_state["count"] = 0
        self.dag.add_node("r1", _retry_action, None, 1, 2)
        self.dag.validate()

        report = self.runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 1
        assert "r1" in report.succeeded_nodes
        assert report.results["r1"].retries_attempted == 2
        assert report.results["r1"].state == NodeState.SUCCEEDED

    def test_runner_failure_skip_downstream(self) -> None:
        """Drives SKIP_DOWNSTREAM failure policy execution in DAGRunner.run."""
        self.checked_dag.add_node("fail_root", _always_fail_action, None, 5, 0)
        self.checked_dag.add_node("dep1", _dummy_action, ["fail_root"], 1, 0)
        self.checked_dag.add_node("dep2", _dummy_action, ["dep1"], 1, 0)
        self.checked_dag.add_node("indep", _dummy_action_alt, None, 10, 0)
        self.checked_dag.validate()

        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 4
        assert "fail_root" in report.failed_nodes
        assert "dep1" in report.skipped_nodes
        assert "dep2" in report.skipped_nodes
        assert "indep" in report.succeeded_nodes
        assert self.checked_scheduler.get_state("dep1") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("dep2") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished()

    def test_runner_failure_continue_on_error(self) -> None:
        """Drives CONTINUE_ON_ERROR failure policy execution in DAGRunner.run."""
        self.checked_dag.add_node("fail_a", _always_fail_action, None, 5, 0)
        self.checked_dag.add_node("child_a", _dummy_action, ["fail_a"], 1, 0)
        self.checked_dag.add_node("ok_b", _dummy_action, None, 2, 0)
        self.checked_dag.add_node("child_b", _dummy_action_alt, ["ok_b"], 1, 0)
        self.checked_dag.validate()

        report = self.checked_runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        assert report.total_nodes == 4
        assert "fail_a" in report.failed_nodes
        assert "child_a" in report.skipped_nodes
        assert "ok_b" in report.succeeded_nodes
        assert "child_b" in report.succeeded_nodes
        assert self.checked_scheduler.is_finished()

    def test_scheduler_mark_failed_policies(self) -> None:
        """Drives SKIP_DOWNSTREAM and CONTINUE_ON_ERROR on WaveScheduler directly."""
        self.checked_dag.add_node("f1", _dummy_action, None, 1, 0)
        self.checked_dag.add_node("c1", _dummy_action, ["f1"], 1, 0)
        self.checked_dag.add_node("f2", _dummy_action, None, 1, 0)
        self.checked_dag.add_node("c2", _dummy_action, ["f2"], 1, 0)
        self.checked_dag.validate()

        self.checked_scheduler.mark_failed("f1", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("f1") == NodeState.FAILED
        assert self.checked_scheduler.get_state("c1") == NodeState.SKIPPED

        self.checked_scheduler.mark_failed("f2", FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.get_state("f2") == NodeState.FAILED
        assert self.checked_scheduler.get_state("c2") == NodeState.SKIPPED

    def test_runner_failure_fail_fast(self) -> None:
        """Drives FAIL_FAST failure policy execution in DAGRunner.run upon node error."""
        self.checked_dag.add_node("fail_node", _always_fail_action, None, 5, 0)
        self.checked_dag.add_node("pending_node", _dummy_action, None, 1, 0)
        self.checked_dag.validate()

        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert "fail_node" in report.failed_nodes
        assert "pending_node" in report.cancelled_nodes
        assert self.checked_scheduler.get_state("pending_node") == NodeState.CANCELLED
        assert self.checked_scheduler.is_finished()

    def test_scheduler_is_finished_running_state(self) -> None:
        """Verifies is_finished returns False while a node is RUNNING."""
        self.checked_dag.add_node("run_node", _dummy_action, None, 0, 0)
        self.checked_dag.validate()
        wave = self.checked_scheduler.next_wave()
        assert "run_node" in wave
        self.checked_scheduler.mark_running("run_node")
        assert not self.checked_scheduler.is_finished()
        self.checked_scheduler.mark_succeeded("run_node")
        assert self.checked_scheduler.is_finished()

    def test_dag_remove_node_with_dependents(self) -> None:
        """Verifies incident edges and scheduler state are purged when removing a parent node."""
        self.checked_dag.add_node("parent", _dummy_action, None, 0, 0)
        self.checked_dag.add_node("child", _dummy_action, ["parent"], 0, 0)
        assert "child" in self.checked_dag.get_dependents("parent")
        assert "parent" in self.checked_dag.get_dependencies("child")

        self.checked_dag.remove_node("parent")
        assert not self.checked_dag.has_node("parent")
        assert "parent" not in self.checked_dag.get_dependencies("child")
        assert self.checked_dag.find_roots() == {"child"}

    def test_checked_precondition_errors(self) -> None:
        """Verifies contracted error exceptions on checked precondition violations."""
        self.dag.add_node("dup", _dummy_action, None, 0, 0)
        with self.assertRaises(DuplicateNodeError):
            self.dag.add_node("dup", _dummy_action, None, 0, 0)

        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("missing")

        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("dup", "missing")

        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing_upstream", "dup")

        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")

        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("missing")

        with self.assertRaises(NodeNotFoundError):
            self.scheduler.get_state("missing")

        self.dag.add_node("node_with_missing_dep", _dummy_action, ["unregistered_dep"], 0, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

        with self.assertRaises(NodeNotFoundError):
            self.dag.topological_sort()

        self.dag.remove_node("node_with_missing_dep")

        self.dag.add_node("cyc_a", _dummy_action, ["cyc_b"], 0, 0)
        self.dag.add_node("cyc_b", _dummy_action, ["cyc_a"], 0, 0)
        with self.assertRaises(CycleError):
            self.dag.validate()

        with self.assertRaises(CycleError):
            self.dag.topological_sort()


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

class DAGEngineLiteSUT:
    """Aggregate multi-singleton SUT delegating method lookups across component services."""
    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self.dag, self.scheduler, self.runner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> DAGEngineLiteSUT:
    """Factory creating aggregate SUT initialized within system lifecycle phase."""
    return DAGEngineLiteSUT()


proto_impl = DAGEngineLiteImplPseudoStateMachine()

DAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto_impl,
    sut_factory=make_sut,
    initial_state_factory=DAGEngineLiteState,
    name="DAGEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T22:52:23Z
# LAST_CHANGED: 2026-11-08T22:48:52Z
# CHANGE: Add scenario tests for fail_fast runner termination, is_finished with running node, remove_node with incident dependents, and missing dependency/upstream preconditions
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T22:52:23Z
# PRETENSE_QA_AUDIT: 2026-11-08T22:51:56Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

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
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_3.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    WaveScheduler,
    DAGRunner,
    CycleError,
    DAGError,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeExecutionError,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    DAGRunReport,
)

def _dummy_action() -> str:
    """Default dummy action for node execution."""
    return "ok"


def _dummy_action_alt() -> int:
    """Alternative dummy action for node execution."""
    return 42


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DAGEngineLiteState:
    """Canonical model state tracking abstract DAG nodes, edges, states, and results."""
    initialized: bool = True
    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    results: dict[str, NodeResult[Any]] = field(default_factory=dict)

    def is_acyclic(self) -> bool:
        """Determines whether the graph contains any directed cycle."""
        in_degree: dict[str, int] = {n: 0 for n in self.nodes}
        for u, deps in self.upstream.items():
            if u in self.nodes:
                in_degree[u] = sum(1 for d in deps if d in self.nodes)
        queue = [n for n, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            n = queue.pop(0)
            visited += 1
            for d in self.downstream.get(n, set()):
                if d in in_degree:
                    in_degree[d] -= 1
                    if in_degree[d] == 0:
                        queue.append(d)
        return visited == len(self.nodes)

    def is_valid(self) -> bool:
        """Checks graph consistency: all dependencies exist and graph is acyclic."""
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    return False
        return self.is_acyclic()

    def compute_topological_sort(self) -> list[str]:
        """Computes deterministic topological ordering with priority and name tie-breaking."""
        in_degree: dict[str, int] = {
            n: sum(1 for d in self.upstream.get(n, set()) if d in self.nodes)
            for n in self.nodes
        }
        ready = [n for n, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda n: (-self.nodes[n].priority, n))
        order: list[str] = []
        while ready:
            curr = ready.pop(0)
            order.append(curr)
            for d in self.downstream.get(curr, set()):
                if d in in_degree:
                    in_degree[d] -= 1
                    if in_degree[d] == 0:
                        ready.append(d)
            ready.sort(key=lambda n: (-self.nodes[n].priority, n))
        return order

    def compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> tuple[list[str], float]:
        """Computes longest weighted dependency path through the graph."""
        if not self.nodes:
            return ([], 0.0)
        topo = self.compute_topological_sort()
        durations: dict[str, float] = {
            n: float(estimated_durations[n]) if estimated_durations is not None and n in estimated_durations else 1.0
            for n in self.nodes
        }
        earliest: dict[str, float] = {}
        best_predecessor: dict[str, Optional[str]] = {}
        for n in topo:
            up = sorted(p for p in self.upstream.get(n, set()) if p in earliest)
            if not up:
                earliest[n] = durations[n]
                best_predecessor[n] = None
            else:
                best_p = max(up, key=lambda p: earliest[p])
                earliest[n] = earliest[best_p] + durations[n]
                best_predecessor[n] = best_p
        end_node = max(sorted(topo), key=lambda n: earliest[n])
        total_weight = earliest[end_node]
        path: list[str] = []
        curr: Optional[str] = end_node
        while curr is not None:
            path.append(curr)
            curr = best_predecessor[curr]
        path.reverse()
        return (path, total_weight)

    def compute_next_wave(self) -> list[str]:
        """Gathers ready nodes whose upstream dependencies are succeeded."""
        ready_nodes: list[str] = []
        for nid in self.nodes:
            state = self.node_states.get(nid, NodeState.PENDING)
            if state == NodeState.READY:
                up = self.upstream.get(nid, set())
                if all(self.node_states.get(u) == NodeState.SUCCEEDED for u in up):
                    ready_nodes.append(nid)
        ready_nodes.sort(key=lambda n: (-self.nodes[n].priority, n))
        return ready_nodes

    def compute_is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states or execution is halted."""
        if not self.nodes:
            return True
        terminal = {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED}
        if all(self.node_states.get(n) in terminal for n in self.nodes):
            return True
        next_w = self.compute_next_wave()
        if not next_w:
            if any(self.node_states.get(n) == NodeState.RUNNING for n in self.nodes):
                return False
            return True
        return False

    def sync_scheduler_states(self) -> None:
        """Synchronizes scheduler node_states with all registered DAG nodes."""
        for n in self.nodes:
            if n not in self.node_states:
                if not self.upstream.get(n):
                    self.node_states[n] = NodeState.READY
                else:
                    self.node_states[n] = NodeState.PENDING

    def can_run(self) -> bool:
        """Determines whether run can be initiated safely."""
        if not self.is_valid():
            return False
        if any(s == NodeState.RUNNING for s in self.node_states.values()):
            return False
        return True

    def simulate_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Simulates full execution run under failure policy."""
        self.sync_scheduler_states()

        succeeded: list[str] = []
        failed: list[str] = []
        while not self.compute_is_finished():
            wave = self.compute_next_wave()
            if not wave:
                break
            for nid in wave:
                self.node_states[nid] = NodeState.RUNNING
                node = self.nodes[nid]
                try:
                    val = node.action()
                    self.node_states[nid] = NodeState.SUCCEEDED
                    succeeded.append(nid)
                    self.results[nid] = NodeResult(
                        node_id=nid,
                        state=NodeState.SUCCEEDED,
                        value=val,
                        duration_seconds=0.01,
                    )
                    for d in self.downstream.get(nid, set()):
                        if self.node_states.get(d) == NodeState.PENDING:
                            up_deps = self.upstream.get(d, set())
                            if all(self.node_states.get(u) == NodeState.SUCCEEDED for u in up_deps):
                                self.node_states[d] = NodeState.READY
                except Exception as exc:
                    self.node_states[nid] = NodeState.FAILED
                    failed.append(nid)
                    self.results[nid] = NodeResult(
                        node_id=nid,
                        state=NodeState.FAILED,
                        error=exc,
                        duration_seconds=0.01,
                        retries_attempted=node.retries,
                    )
                    if failure_policy == FailurePolicy.FAIL_FAST:
                        for other in self.nodes:
                            if self.node_states.get(other) in (
                                NodeState.PENDING,
                                NodeState.READY,
                                NodeState.RUNNING,
                            ):
                                self.node_states[other] = NodeState.CANCELLED
                                self.results[other] = NodeResult(node_id=other, state=NodeState.CANCELLED)
                        break
                    elif failure_policy in (FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR):
                        queue = list(self.downstream.get(nid, set()))
                        while queue:
                            cur = queue.pop(0)
                            if self.node_states.get(cur) in (
                                NodeState.PENDING,
                                NodeState.READY,
                                NodeState.RUNNING,
                            ):
                                self.node_states[cur] = NodeState.SKIPPED
                                self.results[cur] = NodeResult(node_id=cur, state=NodeState.SKIPPED)
                                queue.extend(self.downstream.get(cur, set()))
            if failure_policy == FailurePolicy.FAIL_FAST and failed:
                break

        skipped = [n for n, s in self.node_states.items() if s == NodeState.SKIPPED]
        cancelled = [n for n, s in self.node_states.items() if s == NodeState.CANCELLED]
        crit_path, _ = self.compute_critical_path(None)
        return DAGRunReport(
            total_nodes=len(self.nodes),
            succeeded_nodes=tuple(succeeded),
            failed_nodes=tuple(failed),
            skipped_nodes=tuple(skipped),
            cancelled_nodes=tuple(cancelled),
            wall_clock_seconds=0.05,
            critical_path=tuple(crit_path),
            results=dict(self.results),
        )

    def apply_failure_policy(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Applies failure policy transitions for failed node."""
        self.node_states[node_id] = NodeState.FAILED
        if failure_policy == FailurePolicy.FAIL_FAST:
            for other in self.nodes:
                if self.node_states.get(other) in (
                    NodeState.PENDING,
                    NodeState.READY,
                    NodeState.RUNNING,
                ):
                    self.node_states[other] = NodeState.CANCELLED
        elif failure_policy in (FailurePolicy.SKIP_DOWNSTREAM, FailurePolicy.CONTINUE_ON_ERROR):
            queue = list(self.downstream.get(node_id, set()))
            while queue:
                cur = queue.pop(0)
                if self.node_states.get(cur) in (
                    NodeState.PENDING,
                    NodeState.READY,
                    NodeState.RUNNING,
                ):
                    self.node_states[cur] = NodeState.SKIPPED
                    queue.extend(self.downstream.get(cur, set()))


class DAGEngineLiteStateMachine(StateMachine[DAGEngineLiteState]):
    """Unified Pretense State Machine for DAGEngineLite."""

    def __init__(
        self,
        state: Optional[DAGEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DAGEngineLiteState(), singletons=singletons)

    # --- DAG Interface Transitions ---

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, Domain.not_in(self.state.nodes.keys(), base_type=str))
        require_arg(action, Domain.type(Callable[[], Any]), preferred=[_dummy_action, _dummy_action_alt])
        require_arg(dependencies, Domain.type(Optional[Collection[str]]), preferred=[None, []])
        require_arg(priority, Domain.type(int), preferred=[0, 1, 2, 10])
        require_arg(retries, Domain.range(0, 5), preferred=[0, 1, 2])

        deps: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self.state.nodes[node_id] = node_def
        if node_id not in self.state.upstream:
            self.state.upstream[node_id] = set()
        if node_id not in self.state.downstream:
            self.state.downstream[node_id] = set()
        for d in deps:
            self.state.upstream[node_id].add(d)
            if d not in self.state.downstream:
                self.state.downstream[d] = set()
            self.state.downstream[d].add(node_id)

        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(len(self.state.nodes) >= 2)
        require_arg(upstream_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        require_arg(downstream_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))

        self.state.upstream[downstream_id].add(upstream_id)
        self.state.downstream[upstream_id].add(downstream_id)
        old_def = self.state.nodes[downstream_id]
        new_deps = frozenset(old_def.dependencies | {upstream_id})
        self.state.nodes[downstream_id] = NodeDefinition(
            node_id=old_def.node_id,
            action=old_def.action,
            dependencies=new_deps,
            priority=old_def.priority,
            retries=old_def.retries,
        )

        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))

        for u in self.state.upstream.get(node_id, set()):
            if u in self.state.downstream:
                self.state.downstream[u].discard(node_id)
        for d in self.state.downstream.get(node_id, set()):
            if d in self.state.upstream:
                self.state.upstream[d].discard(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.node_states.pop(node_id, None)

        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.type(str), preferred=list(self.state.nodes.keys()) + ["missing"])
        fake_ret = node_id in self.state.nodes
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        fake_ret = self.state.nodes[node_id]
        ret = make_return_value(fake_ret)
        assert ret.node_id == node_id
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        fake_ret = set(self.state.upstream.get(node_id, set()))
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        fake_ret = set(self.state.downstream.get(node_id, set()))
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        fake_ret = set(self.state.nodes.keys())
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.is_valid())
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.is_acyclic())
        fake_ret = self.state.compute_topological_sort()
        ret = make_return_value(fake_ret)
        assert len(ret) == len(self.state.nodes)
        return ret

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        fake_ret = {nid for nid in self.state.nodes if not self.state.upstream.get(nid)}
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        fake_ret = {nid for nid in self.state.nodes if not self.state.downstream.get(nid)}
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self, estimated_durations: Optional[Mapping[str, float]]
    ) -> Tuple[List[str], float]:
        require(self.state.is_acyclic())
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
            preferred=[None],
        )
        fake_path, fake_dur = self.state.compute_critical_path(estimated_durations)
        ret = make_return_value((fake_path, fake_dur))
        assert ret == (fake_path, fake_dur)
        return ret

    # --- WaveScheduler Interface Transitions ---

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        self.state.sync_scheduler_states()
        fake_ret = self.state.compute_next_wave()
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        self.state.sync_scheduler_states()
        self.state.node_states[node_id] = NodeState.RUNNING
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        self.state.sync_scheduler_states()
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        for d in self.state.downstream.get(node_id, set()):
            if self.state.node_states.get(d) == NodeState.PENDING:
                up_deps = self.state.upstream.get(d, set())
                if all(self.state.node_states.get(u) == NodeState.SUCCEEDED for u in up_deps):
                    self.state.node_states[d] = NodeState.READY
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        require_arg(
            failure_policy,
            Domain.sampled_from([
                FailurePolicy.FAIL_FAST,
                FailurePolicy.CONTINUE_ON_ERROR,
                FailurePolicy.SKIP_DOWNSTREAM,
            ]),
            preferred=[FailurePolicy.FAIL_FAST],
        )
        self.state.sync_scheduler_states()
        self.state.apply_failure_policy(node_id, failure_policy)

        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        self.state.sync_scheduler_states()
        fake_ret = self.state.compute_is_finished()
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(bool(self.state.nodes))
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()), preferred=list(self.state.nodes.keys()))
        self.state.sync_scheduler_states()
        fake_ret = self.state.node_states[node_id]
        ret = make_return_value(fake_ret)
        assert ret == fake_ret
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        self.state.sync_scheduler_states()
        fake_ret = {nid: self.state.node_states[nid] for nid in self.state.nodes}
        ret = make_return_value(fake_ret)
        assert set(ret.keys()) == set(self.state.nodes.keys())
        return ret

    # --- DAGRunner Interface Transitions ---

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.state.can_run())
        require_arg(
            failure_policy,
            Domain.sampled_from([
                FailurePolicy.FAIL_FAST,
                FailurePolicy.CONTINUE_ON_ERROR,
                FailurePolicy.SKIP_DOWNSTREAM,
            ]),
            preferred=[FailurePolicy.FAIL_FAST],
        )
        fake_report = self.state.simulate_run(failure_policy)
        ret = make_return_value(fake_report)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    # --- Seeding Transition ---

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = DAGEngineLiteStateMachine()

# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngineLite = synthesize_fake(DAGEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DAGEngineLiteState] = None) -> DAG:
    """Synthesizes fake instance for DAGEngineLite."""
    return FakeDAGEngineLite(state=state or DAGEngineLiteState())


def make_dag_fake(state: Optional[DAGEngineLiteState] = None) -> DAG:
    """Synthesizes fake instance for DAG."""
    return FakeDAGEngineLite(state=state or DAGEngineLiteState())


def make_wave_scheduler_fake(state: Optional[DAGEngineLiteState] = None) -> WaveScheduler:
    """Synthesizes fake instance for WaveScheduler."""
    return FakeDAGEngineLite(state=state or DAGEngineLiteState())


def make_dag_runner_fake(state: Optional[DAGEngineLiteState] = None) -> DAGRunner:
    """Synthesizes fake instance for DAGRunner."""
    return FakeDAGEngineLite(state=state or DAGEngineLiteState())


def make_dag_engine_lite_fakes(
    state: Optional[DAGEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    fake = FakeDAGEngineLite(state=state or DAGEngineLiteState())
    return (fake, fake, fake)


FakeDAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DAGEngineLiteState,
    name="FakeDAGEngineLiteFuzzTest",
)

# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestDAGEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake_dag, self.fake_scheduler, self.fake_runner = make_dag_engine_lite_fakes()
        self.sm = DAGEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()

        # 1. add_node
        self.fake_dag.add_node("n1", _dummy_action, None, 1, 0)
        self.fake_dag.add_node("n2", _dummy_action_alt, ["n1"], 2, 0)
        self.fake_dag.add_node("n3", _dummy_action, ["n1"], 0, 0)

        # 2. add_edge
        self.fake_dag.add_edge("n2", "n3")

        # 3. has_node
        assert self.fake_dag.has_node("n1")
        assert not self.fake_dag.has_node("missing")

        # 4. get_node
        node_1 = self.fake_dag.get_node("n1")
        assert node_1.node_id == "n1"

        # 5. get_dependencies
        deps = self.fake_dag.get_dependencies("n2")
        assert "n1" in deps

        # 6. get_dependents
        down = self.fake_dag.get_dependents("n1")
        assert "n2" in down

        # 7. all_nodes
        nodes = self.fake_dag.all_nodes()
        assert len(nodes) == 3

        # 8. validate
        self.fake_dag.validate()

        # 9. topological_sort
        topo = self.fake_dag.topological_sort()
        assert topo[0] == "n1"

        # 10. find_roots
        roots = self.fake_dag.find_roots()
        assert "n1" in roots

        # 11. find_leaves
        leaves = self.fake_dag.find_leaves()
        assert "n3" in leaves

        # 12. compute_critical_path
        path, weight = self.fake_dag.compute_critical_path({"n1": 2.0, "n2": 3.0, "n3": 1.0})
        assert len(path) == 3
        assert weight == 6.0

        # 13. next_wave
        wave = self.fake_scheduler.next_wave()
        assert "n1" in wave

        # 14. mark_running
        self.fake_scheduler.mark_running("n1")
        assert self.fake_scheduler.get_state("n1") == NodeState.RUNNING

        # 15. mark_succeeded
        self.fake_scheduler.mark_succeeded("n1")
        assert self.fake_scheduler.get_state("n1") == NodeState.SUCCEEDED

        # 16. mark_failed
        self.fake_scheduler.mark_failed("n2", FailurePolicy.FAIL_FAST)
        assert self.fake_scheduler.get_state("n2") == NodeState.FAILED

        # 17. is_finished
        _ = self.fake_scheduler.is_finished()

        # 18. get_state
        assert self.fake_scheduler.get_state("n2") == NodeState.FAILED

        # 19. get_all_states
        all_st = self.fake_scheduler.get_all_states()
        assert "n1" in all_st

        # 20. run
        report = self.fake_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes >= 0

        # 21. remove_node
        self.fake_dag.remove_node("n3")
        assert not self.fake_dag.has_node("n3")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T22:28:12Z
# LAST_CHANGED: 2026-11-08T22:28:12Z
# CHANGE: Cancel RUNNING nodes alongside PENDING and READY nodes under FAIL_FAST in apply_failure_policy and simulate_run
# --- END AUTOFAB METADATA ---
