# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
    DAGRunner,
)
from benchmark_2.parts.dag_engine_lite.lib.dag_engine_lite_impl import __initialize__
from benchmark_2.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineLiteState,
    DAGEngineLiteStateMachine,
)


def _dummy_action() -> None:
    pass


def _failing_action() -> None:
    raise RuntimeError("Action failure simulation")


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class DAGEngineLiteImplPseudoStateMachine(DAGEngineLiteStateMachine):
    """Implementation pseudo-state machine for DAGEngineLite delegating to concrete SUT singletons."""

    # --------------------------------------------------------------------------
    # DAG Inner Transition Overrides
    # --------------------------------------------------------------------------

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: DAG = sut(DAG)
        return target.add_node(node_id, action, dependencies, priority, retries)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: DAG = sut(DAG)
        return target.add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        target: DAG = sut(DAG)
        return target.remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        target: DAG = sut(DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        target: DAG = sut(DAG)
        return target.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: DAG = sut(DAG)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        target: DAG = sut(DAG)
        return target.all_nodes()

    def inner_validate(self) -> None:
        target: DAG = sut(DAG)
        return target.validate()

    def inner_topological_sort(self) -> List[str]:
        target: DAG = sut(DAG)
        return target.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        target: DAG = sut(DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        target: DAG = sut(DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: DAG = sut(DAG)
        return target.compute_critical_path(estimated_durations)

    # --------------------------------------------------------------------------
    # WaveScheduler Inner Transition Overrides
    # --------------------------------------------------------------------------

    def inner_next_wave(self) -> List[str]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_succeeded(node_id)

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        target: WaveScheduler = sut(WaveScheduler)
        return target.mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        target: WaveScheduler = sut(WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> NodeState:
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        target: WaveScheduler = sut(WaveScheduler)
        return target.get_all_states()

    # --------------------------------------------------------------------------
    # DAGRunner Inner Transition Overrides
    # --------------------------------------------------------------------------

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        target: DAGRunner = sut(DAGRunner)
        return target.run(failure_policy)


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestDAGEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies all contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()

        self.real = get_singleton(DAG)
        scheduler = get_singleton(WaveScheduler)
        runner = get_singleton(DAGRunner)

        self.sm = DAGEngineLiteImplPseudoStateMachine(
            singletons={
                DAG: self.real,
                WaveScheduler: scheduler,
                DAGRunner: runner,
            }
        )
        self.checked_dag: Any = self.sm.as_checked(DAG, self.real)
        self.checked: Any = self.checked_dag
        self.checked_scheduler: Any = self.sm.as_checked(WaveScheduler, scheduler)
        self.checked_runner: Any = self.sm.as_checked(DAGRunner, runner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_dag_lifecycle_and_queries(self) -> None:
        """Tests basic node and edge additions, inspection queries, and roots/leaves."""
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, None, 1, 0)

        self.checked_dag.add_edge("b", "c")

        assert self.checked_dag.has_node("a")
        assert not self.checked_dag.has_node("nonexistent")

        node_a = self.checked_dag.get_node("a")
        assert node_a.node_id == "a"
        assert node_a.priority == 10

        deps_b = self.checked_dag.get_dependencies("b")
        assert "a" in deps_b

        depents_a = self.checked_dag.get_dependents("a")
        assert "b" in depents_a

        all_nodes = self.checked_dag.all_nodes()
        assert len(all_nodes) == 3

        roots = self.checked_dag.find_roots()
        assert "a" in roots

        leaves = self.checked_dag.find_leaves()
        assert "c" in leaves

        self.checked_dag.validate()

        order = self.checked_dag.topological_sort()
        assert order == ["a", "b", "c"]

        path, weight = self.checked_dag.compute_critical_path(None)
        assert len(path) == 3
        assert weight == 3.0

        path2, weight2 = self.checked_dag.compute_critical_path({"a": 2.0, "b": 3.0, "c": 4.0})
        assert weight2 == 9.0

        self.checked_dag.remove_node("c")
        assert not self.checked_dag.has_node("c")

    def test_compute_critical_path_empty_graph(self) -> None:
        """Tests critical path computation on an empty graph."""
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0

    def test_remove_node_with_dependents(self) -> None:
        """Tests removing a node that has downstream dependents to purge incident edges."""
        self.checked_dag.add_node("u", _dummy_action, None, 1, 0)
        self.checked_dag.add_node("v", _dummy_action, ["u"], 1, 0)
        deps = self.checked_dag.get_dependencies("v")
        assert "u" in deps
        self.checked_dag.remove_node("u")
        assert not self.checked_dag.has_node("u")
        assert self.checked_dag.has_node("v")
        deps_after = self.checked_dag.get_dependencies("v")
        assert "u" not in deps_after

    def test_remove_node_purges_scheduler_state(self) -> None:
        """Tests that removing a node purges its state from wave scheduler tracking."""
        self.checked_dag.add_node("c", _dummy_action, None, 1, 0)
        states = self.checked_scheduler.get_all_states()
        assert "c" in states
        self.checked_dag.remove_node("c")
        states_after = self.checked_scheduler.get_all_states()
        assert "c" not in states_after

    def test_wave_scheduler_execution_flow(self) -> None:
        """Tests wave scheduler state transitions and dependency unlocking."""
        self.checked_dag.add_node("n1", _dummy_action, None, 5, 0)
        self.checked_dag.add_node("n2", _dummy_action, ["n1"], 1, 0)

        wave1 = self.checked_scheduler.next_wave()
        assert wave1 == ["n1"]

        self.checked_scheduler.mark_running("n1")
        assert self.checked_scheduler.get_state("n1") == NodeState.RUNNING

        self.checked_scheduler.mark_succeeded("n1")
        assert self.checked_scheduler.get_state("n1") == NodeState.SUCCEEDED

        wave2 = self.checked_scheduler.next_wave()
        assert wave2 == ["n2"]

        self.checked_scheduler.mark_running("n2")
        self.checked_scheduler.mark_succeeded("n2")

        states = self.checked_scheduler.get_all_states()
        assert states["n1"] == NodeState.SUCCEEDED
        assert states["n2"] == NodeState.SUCCEEDED

        assert self.checked_scheduler.is_finished()

    def test_scheduler_failure_policies(self) -> None:
        """Tests scheduler behavior under fail-fast, skip-downstream, and continue-on-error."""
        self.checked_dag.add_node("root", _dummy_action, None, 1, 0)
        self.checked_dag.add_node("child", _dummy_action, ["root"], 1, 0)

        wave = self.checked_scheduler.next_wave()
        assert "root" in wave

        self.checked_scheduler.mark_running("root")
        self.checked_scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)

        assert self.checked_scheduler.get_state("root") == NodeState.FAILED
        assert self.checked_scheduler.get_state("child") == NodeState.SKIPPED
        assert self.checked_scheduler.is_finished()

    def test_scheduler_skip_downstream_transitive(self) -> None:
        """Tests transitive dependent cascading skip under SKIP_DOWNSTREAM policy with depth 2."""
        self.checked_dag.add_node("root", _dummy_action, None, 3, 0)
        self.checked_dag.add_node("child", _dummy_action, ["root"], 2, 0)
        self.checked_dag.add_node("grandchild", _dummy_action, ["child"], 1, 0)
        self.checked_scheduler.mark_running("root")
        self.checked_scheduler.mark_failed("root", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("root") == NodeState.FAILED
        assert self.checked_scheduler.get_state("child") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("grandchild") == NodeState.SKIPPED

    def test_scheduler_fail_fast_policy(self) -> None:
        """Tests fail fast cancelling remaining pending nodes."""
        self.checked_dag.add_node("n_fail", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("n_other", _dummy_action, None, 5, 0)

        self.checked_scheduler.mark_running("n_fail")
        self.checked_scheduler.mark_failed("n_fail", FailurePolicy.FAIL_FAST)

        assert self.checked_scheduler.get_state("n_fail") == NodeState.FAILED
        assert self.checked_scheduler.get_state("n_other") == NodeState.CANCELLED

    def test_scheduler_continue_on_error_policy(self) -> None:
        """Tests continue on error allowing independent branches to execute."""
        self.checked_dag.add_node("failing", _dummy_action, None, 1, 0)
        self.checked_dag.add_node("child_of_failing", _dummy_action, ["failing"], 1, 0)
        self.checked_dag.add_node("independent", _dummy_action, None, 1, 0)

        self.checked_scheduler.mark_running("failing")
        self.checked_scheduler.mark_failed("failing", FailurePolicy.CONTINUE_ON_ERROR)

        assert self.checked_scheduler.get_state("failing") == NodeState.FAILED
        assert self.checked_scheduler.get_state("child_of_failing") == NodeState.SKIPPED
        assert self.checked_scheduler.get_state("independent") == NodeState.READY

    def test_dag_runner_successful_run(self) -> None:
        """Tests running a valid DAG with the DAGRunner."""
        self.checked_dag.add_node("task1", _dummy_action, None, 2, 0)
        self.checked_dag.add_node("task2", _dummy_action, ["task1"], 1, 0)

        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert len(report.succeeded_nodes) == 2
        assert len(report.failed_nodes) == 0
        assert report.results["task1"].state == NodeState.SUCCEEDED

    def test_dag_runner_failure_handling(self) -> None:
        """Tests DAGRunner execution with a node that fails actions."""
        self.checked_dag.add_node("bad_node", _failing_action, None, 2, 1)
        self.checked_dag.add_node("downstream_bad", _dummy_action, ["bad_node"], 1, 0)

        report = self.checked_runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 2
        assert "bad_node" in report.failed_nodes
        assert "downstream_bad" in report.skipped_nodes

    def test_dag_runner_fail_fast_execution_wave_termination(self) -> None:
        """Tests DAGRunner early termination and cancellation under FAIL_FAST when a node fails."""
        self.checked_dag.add_node("fail_first", _failing_action, None, 10, 0)
        self.checked_dag.add_node("never_run", _dummy_action, None, 5, 0)
        report = self.checked_runner.run(FailurePolicy.FAIL_FAST)
        assert "fail_first" in report.failed_nodes
        assert "never_run" in report.cancelled_nodes
        assert report.results["fail_first"].state == NodeState.FAILED
        assert report.results["never_run"].state == NodeState.CANCELLED

    def test_contract_violation_duplicate_node(self) -> None:
        """Tests DuplicateNodeError contract violation on add_node."""
        self.checked_dag.add_node("dup", _dummy_action, None, 0, 0)
        with self.checked_dag.violating(DuplicateNodeError):
            self.checked_dag.add_node("dup", _dummy_action, None, 0, 0)

    def test_contract_violation_node_not_found_on_edge(self) -> None:
        """Tests NodeNotFoundError when adding edge between missing nodes."""
        self.checked_dag.add_node("existing", _dummy_action, None, 0, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.add_edge("existing", "missing")

    def test_contract_violation_node_not_found_on_edge_missing_upstream(self) -> None:
        """Tests NodeNotFoundError when adding edge where upstream node is missing."""
        self.checked_dag.add_node("existing", _dummy_action, None, 0, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.add_edge("missing", "existing")

    def test_contract_violation_node_not_found_on_get(self) -> None:
        """Tests NodeNotFoundError when retrieving nonexistent node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.get_node("ghost")

    def test_contract_violation_node_not_found_on_remove(self) -> None:
        """Tests NodeNotFoundError when removing nonexistent node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.remove_node("ghost")

    def test_contract_violation_node_not_found_on_dependencies(self) -> None:
        """Tests NodeNotFoundError when querying dependencies of nonexistent node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.get_dependencies("ghost")

    def test_contract_violation_node_not_found_on_dependents(self) -> None:
        """Tests NodeNotFoundError when querying dependents of nonexistent node."""
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.get_dependents("ghost")

    def test_contract_violation_node_not_found_on_scheduler_state(self) -> None:
        """Tests NodeNotFoundError when getting state of nonexistent node."""
        with self.checked_scheduler.violating(NodeNotFoundError):
            self.checked_scheduler.get_state("ghost")

    def test_contract_violation_validate_missing_dependency(self) -> None:
        """Tests NodeNotFoundError during validation when dependency does not exist."""
        self.checked_dag.add_node("n_with_missing_dep", _dummy_action, ["missing_upstream"], 0, 0)
        with self.checked_dag.violating(NodeNotFoundError):
            self.checked_dag.validate()

    def test_contract_violation_validate_cycle(self) -> None:
        """Tests CycleError during validation when a cycle exists."""
        self.checked_dag.add_node("c1", _dummy_action, None, 0, 0)
        self.checked_dag.add_node("c2", _dummy_action, None, 0, 0)
        self.checked_dag.add_edge("c1", "c2")
        self.checked_dag.add_edge("c2", "c1")
        with self.checked_dag.violating(CycleError):
            self.checked_dag.validate()

    def test_contract_violation_topological_sort_cycle(self) -> None:
        """Tests CycleError during topological sort when a cycle exists."""
        self.checked_dag.add_node("t1", _dummy_action, None, 0, 0)
        self.checked_dag.add_node("t2", _dummy_action, None, 0, 0)
        self.checked_dag.add_edge("t1", "t2")
        self.checked_dag.add_edge("t2", "t1")
        with self.checked_dag.violating(CycleError):
            self.checked_dag.topological_sort()

    def test_contract_violation_runner_cycle(self) -> None:
        """Tests CycleError during DAGRunner run when a cycle exists."""
        self.checked_dag.add_node("r1", _dummy_action, None, 0, 0)
        self.checked_dag.add_node("r2", _dummy_action, None, 0, 0)
        self.checked_dag.add_edge("r1", "r2")
        self.checked_dag.add_edge("r2", "r1")
        with self.checked_runner.violating(CycleError):
            self.checked_runner.run(FailurePolicy.FAIL_FAST)

    def test_contract_violation_runner_missing_dependency(self) -> None:
        """Tests NodeNotFoundError during DAGRunner run when dependency is missing."""
        self.checked_dag.add_node("r_missing", _dummy_action, ["unregistered"], 0, 0)
        with self.checked_runner.violating(NodeNotFoundError):
            self.checked_runner.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================


class DAGEngineLiteSUT:
    """Multi-singleton aggregate SUT delegating method dispatch across component services."""

    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag: DAG = get_singleton(DAG)
        self.scheduler: WaveScheduler = get_singleton(WaveScheduler)
        self.runner: DAGRunner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self.dag, self.scheduler, self.runner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> DAGEngineLiteSUT:
    return DAGEngineLiteSUT()


DAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=DAGEngineLiteImplPseudoStateMachine(),
    sut_factory=make_sut,
    initial_state_factory=DAGEngineLiteState,
    name="DAGEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:59:57Z
# LAST_CHANGED: 2026-11-09T22:58:54Z
# CHANGE: Add real scenario tests resolving coverage feedback: fail fast wave termination, missing upstream edge rejection, transitive skip downstream at depth 2, empty graph critical path, and node removal purging incident edges and scheduler state
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:59:57Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:59:31Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, List, Mapping, Optional, Sequence, Set, Tuple
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
    DAG,
    DAGRunReport,
    CycleError,
    DuplicateNodeError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler,
    DAGRunner,
)


def _default_action() -> None:
    pass


def _node_sort_key(node_defn: NodeDefinition[Any]) -> tuple[int, str]:
    return (-node_defn.priority, node_defn.node_id)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class DAGEngineLiteState:
    """Canonical model state tracking nodes, dependency edges, execution states, and outcomes."""

    initialized: bool = True
    nodes: dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    upstream: dict[str, set[str]] = field(default_factory=dict)
    downstream: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)
    node_results: dict[str, NodeResult[Any]] = field(default_factory=dict)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def find_cycle(self) -> Optional[list[str]]:
        visited: set[str] = set()
        rec_stack: list[str] = []
        rec_set: set[str] = set()

        def dfs(u: str) -> Optional[list[str]]:
            visited.add(u)
            rec_stack.append(u)
            rec_set.add(u)
            for v in sorted(self.downstream.get(u, set())):
                if v in self.nodes:
                    if v in rec_set:
                        idx = rec_stack.index(v)
                        return rec_stack[idx:] + [v]
                    if v not in visited:
                        res = dfs(v)
                        if res:
                            return res
            rec_stack.pop()
            rec_set.remove(u)
            return None

        for n in sorted(self.nodes.keys()):
            if n not in visited:
                res = dfs(n)
                if res:
                    return res
        return None

    def all_dependencies_exist(self) -> bool:
        for nid, defn in self.nodes.items():
            for dep in defn.dependencies:
                if dep not in self.nodes:
                    return False
        for nid, ups in self.upstream.items():
            for up in ups:
                if up not in self.nodes:
                    return False
        return True

    def compute_topological_sort(self) -> list[str]:
        in_degree: dict[str, int] = {}
        for nid in self.nodes:
            ups = self.upstream.get(nid, set()) & set(self.nodes.keys())
            in_degree[nid] = len(ups)

        candidates = [self.nodes[nid] for nid, deg in in_degree.items() if deg == 0]
        candidates.sort(key=_node_sort_key)
        ready_queue = [c.node_id for c in candidates]

        order: list[str] = []
        for _ in range(len(self.nodes)):
            if not ready_queue:
                break
            curr = ready_queue.pop(0)
            order.append(curr)
            newly_ready: list[NodeDefinition[Any]] = []
            for down in sorted(self.downstream.get(curr, set())):
                if down in self.nodes:
                    in_degree[down] -= 1
                    if in_degree[down] == 0:
                        newly_ready.append(self.nodes[down])
            if newly_ready:
                newly_ready.sort(key=_node_sort_key)
                for item in newly_ready:
                    ready_queue.append(item.node_id)
                ready_defns = [self.nodes[nid] for nid in ready_queue]
                ready_defns.sort(key=_node_sort_key)
                ready_queue = [c.node_id for c in ready_defns]

        return order

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> tuple[list[str], float]:
        if not self.nodes:
            return ([], 0.0)

        topo = self.compute_topological_sort()
        durations: dict[str, float] = {}
        for nid in self.nodes:
            if estimated_durations and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        earliest: dict[str, float] = {}
        predecessor: dict[str, Optional[str]] = {}

        for u in topo:
            ups = sorted(self.upstream.get(u, set()) & set(self.nodes.keys()))
            max_prev = 0.0
            best_p: Optional[str] = None
            for p in ups:
                p_time = earliest.get(p, 0.0)
                if p_time > max_prev:
                    max_prev = p_time
                    best_p = p
            earliest[u] = max_prev + durations[u]
            predecessor[u] = best_p

        max_node: Optional[str] = None
        max_duration = -1.0
        for n in topo:
            time = earliest.get(n, 0.0)
            if time > max_duration:
                max_duration = time
                max_node = n

        if max_node is None:
            return ([], 0.0)

        path: list[str] = []
        curr: Optional[str] = max_node
        for _ in range(len(self.nodes)):
            if curr is None:
                break
            path.append(curr)
            curr = predecessor.get(curr)

        path.reverse()
        return (path, max_duration)

    def sync_scheduler_states(self) -> None:
        for nid in self.nodes:
            if nid not in self.node_states:
                ups = self.upstream.get(nid, set()) & set(self.nodes.keys())
                if not ups:
                    self.node_states[nid] = NodeState.READY
                else:
                    self.node_states[nid] = NodeState.PENDING

    def compute_next_wave(self) -> list[str]:
        self.sync_scheduler_states()
        ready_candidates: list[NodeDefinition[Any]] = []
        for nid, st in self.node_states.items():
            if nid in self.nodes and st == NodeState.READY:
                ups = self.upstream.get(nid, set()) & set(self.nodes.keys())
                if all(self.node_states.get(p) == NodeState.SUCCEEDED for p in ups):
                    ready_candidates.append(self.nodes[nid])

        ready_candidates.sort(key=_node_sort_key)
        return [c.node_id for c in ready_candidates]

    def promote_dependents(self, node_id: str) -> None:
        downs = self.downstream.get(node_id, set()) & set(self.nodes.keys())
        for down in downs:
            if self.node_states.get(down) == NodeState.PENDING:
                ups = self.upstream.get(down, set()) & set(self.nodes.keys())
                if all(self.node_states.get(p) == NodeState.SUCCEEDED for p in ups):
                    self.node_states[down] = NodeState.READY

    def apply_failure_policy(self, failed_node: str, policy: FailurePolicy) -> None:
        self.node_states[failed_node] = NodeState.FAILED
        if policy == FailurePolicy.FAIL_FAST:
            for nid in self.nodes:
                if self.node_states.get(nid) in (NodeState.PENDING, NodeState.READY):
                    self.node_states[nid] = NodeState.CANCELLED
        elif policy == FailurePolicy.SKIP_DOWNSTREAM:
            dependents: set[str] = set()
            curr = set(self.downstream.get(failed_node, set()) & set(self.nodes.keys()))
            for _ in range(len(self.nodes)):
                if not curr:
                    break
                dependents.update(curr)
                next_curr: set[str] = set()
                for d in curr:
                    next_curr.update(self.downstream.get(d, set()) & set(self.nodes.keys()))
                curr = next_curr - dependents
            for d in dependents:
                if self.node_states.get(d) not in (NodeState.SUCCEEDED, NodeState.FAILED):
                    self.node_states[d] = NodeState.SKIPPED
        elif policy == FailurePolicy.CONTINUE_ON_ERROR:
            dependents: set[str] = set()
            curr = set(self.downstream.get(failed_node, set()) & set(self.nodes.keys()))
            for _ in range(len(self.nodes)):
                if not curr:
                    break
                dependents.update(curr)
                next_curr: set[str] = set()
                for d in curr:
                    next_curr.update(self.downstream.get(d, set()) & set(self.nodes.keys()))
                curr = next_curr - dependents
            for d in dependents:
                if self.node_states.get(d) not in (NodeState.SUCCEEDED, NodeState.FAILED):
                    self.node_states[d] = NodeState.SKIPPED

    def compute_is_finished(self) -> bool:
        self.sync_scheduler_states()
        if not self.nodes:
            return True
        terminal_states = {
            NodeState.SUCCEEDED,
            NodeState.FAILED,
            NodeState.SKIPPED,
            NodeState.CANCELLED,
        }
        if all(self.node_states.get(nid) in terminal_states for nid in self.nodes):
            return True
        ready = self.compute_next_wave()
        if not ready:
            has_running = any(self.node_states.get(nid) == NodeState.RUNNING for nid in self.nodes)
            if not has_running:
                return True
        return False

    def get_node_state(self, node_id: str) -> NodeState:
        self.sync_scheduler_states()
        return self.node_states[node_id]

    def get_all_node_states(self) -> dict[str, NodeState]:
        self.sync_scheduler_states()
        return {nid: self.node_states[nid] for nid in self.nodes}

    def execute_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        self.sync_scheduler_states()
        for _ in range(len(self.nodes) + 1):
            wave = self.compute_next_wave()
            if not wave:
                break
            failed_in_wave = False
            for nid in wave:
                self.node_states[nid] = NodeState.RUNNING
                defn = self.nodes[nid]
                try:
                    val = defn.action()
                    self.node_states[nid] = NodeState.SUCCEEDED
                    self.promote_dependents(nid)
                    self.node_results[nid] = NodeResult(
                        node_id=nid,
                        state=NodeState.SUCCEEDED,
                        value=val,
                        duration_seconds=0.01,
                        retries_attempted=0,
                    )
                except Exception as exc:
                    self.apply_failure_policy(nid, failure_policy)
                    self.node_results[nid] = NodeResult(
                        node_id=nid,
                        state=NodeState.FAILED,
                        error=exc,
                        duration_seconds=0.01,
                        retries_attempted=defn.retries,
                    )
                    failed_in_wave = True
                    if failure_policy == FailurePolicy.FAIL_FAST:
                        break
            if failed_in_wave and failure_policy == FailurePolicy.FAIL_FAST:
                break

        for nid in self.nodes:
            if nid not in self.node_results:
                st = self.node_states.get(nid, NodeState.SKIPPED)
                self.node_results[nid] = NodeResult(
                    node_id=nid,
                    state=st,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        crit_path, _ = self.compute_critical_path(None)
        succeeded = tuple(n for n in self.nodes if self.node_states.get(n) == NodeState.SUCCEEDED)
        failed = tuple(n for n in self.nodes if self.node_states.get(n) == NodeState.FAILED)
        skipped = tuple(n for n in self.nodes if self.node_states.get(n) == NodeState.SKIPPED)
        cancelled = tuple(n for n in self.nodes if self.node_states.get(n) == NodeState.CANCELLED)

        return DAGRunReport(
            total_nodes=len(self.nodes),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=0.05,
            critical_path=tuple(crit_path),
            results=dict(self.node_results),
        )


class DAGEngineLiteStateMachine(StateMachine[DAGEngineLiteState]):
    """Unified Pretense State Machine for DAG, WaveScheduler, and DAGRunner."""

    def __init__(
        self,
        state: Optional[DAGEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineLiteState:
        return DAGEngineLiteState()

    # --------------------------------------------------------------------------
    # DAG Transitions
    # --------------------------------------------------------------------------

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require_arg(node_id, Domain.not_in(self.state.nodes.keys()), preferred=["n1", "n2", "n3", "n4"])
        require_arg(action, Domain.any(), preferred=[_default_action])
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])), preferred=[None, []])
        require_arg(priority, Domain.type(int), preferred=[0, 1, 5])
        require_arg(retries, Domain.type(int), preferred=[0, 1, 2])
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        self.state.nodes[node_id] = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies) if dependencies else frozenset(),
            priority=priority,
            retries=retries,
        )
        if node_id not in self.state.upstream:
            self.state.upstream[node_id] = set()
        if node_id not in self.state.downstream:
            self.state.downstream[node_id] = set()
        if dependencies:
            for dep in dependencies:
                self.state.upstream[node_id].add(dep)
                self.state.downstream.setdefault(dep, set()).add(node_id)
        assert self.state.has_node(node_id)

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        if node_id in self.state.nodes:
            raise DuplicateNodeError(f"Duplicate node: {node_id}", node_id)

    @transition(DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(len(self.state.nodes) >= 2)
        require_arg(upstream_id, Domain.in_set(self.state.nodes.keys()))
        require_arg(downstream_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        self.state.upstream.setdefault(downstream_id, set()).add(upstream_id)
        self.state.downstream.setdefault(upstream_id, set()).add(downstream_id)
        assert upstream_id in self.state.upstream[downstream_id]

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {upstream_id}", upstream_id)
        if downstream_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {downstream_id}", downstream_id)

    @transition(DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_remove_node(node_id)
        del self.state.nodes[node_id]
        for ups in self.state.upstream.values():
            ups.discard(node_id)
        for downs in self.state.downstream.values():
            downs.discard(node_id)
        self.state.upstream.pop(node_id, None)
        self.state.downstream.pop(node_id, None)
        self.state.node_states.pop(node_id, None)
        self.state.node_results.pop(node_id, None)
        assert not self.state.has_node(node_id)

    def inner_remove_node(self, node_id: str) -> None:
        if node_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {node_id}", node_id)

    @transition(DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.type(str), preferred=["n1", "n2", "nonexistent"])
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.nodes)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.nodes

    @transition(DAG.get_node)
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    def inner_get_node(self, node_id: str) -> NodeDefinition[Any]:
        if node_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {node_id}", node_id)
        return self.state.nodes[node_id]

    @transition(DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_get_dependencies(node_id)
        assert ret == self.state.upstream.get(node_id, set())
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {node_id}", node_id)
        return set(self.state.upstream.get(node_id, set()))

    @transition(DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_get_dependents(node_id)
        assert ret == self.state.downstream.get(node_id, set())
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {node_id}", node_id)
        return set(self.state.downstream.get(node_id, set()))

    @transition(DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.nodes.keys())
        return ret

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.nodes.keys())

    @transition(DAG.validate)
    def validate(self) -> None:
        require(self.state.all_dependencies_exist())
        require(self.state.find_cycle() is None)
        ret = self.inner_validate()
        assert ret is None

    def inner_validate(self) -> None:
        for nid, defn in self.state.nodes.items():
            for dep in defn.dependencies:
                if dep not in self.state.nodes:
                    raise NodeNotFoundError(f"Dependency not found: {dep}", dep)
        for nid, ups in self.state.upstream.items():
            for up in ups:
                if up not in self.state.nodes:
                    raise NodeNotFoundError(f"Dependency not found: {up}", up)
        cycle = self.state.find_cycle()
        if cycle:
            raise CycleError(f"Cycle detected: {cycle}", tuple(cycle))

    @transition(DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.all_dependencies_exist())
        require(self.state.find_cycle() is None)
        ret = self.inner_topological_sort()
        assert len(ret) == len(self.state.nodes)
        return ret

    def inner_topological_sort(self) -> List[str]:
        cycle = self.state.find_cycle()
        if cycle:
            raise CycleError(f"Cycle detected: {cycle}", tuple(cycle))
        return self.state.compute_topological_sort()

    @transition(DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        expected = {nid for nid in self.state.nodes if not self.state.upstream.get(nid)}
        assert ret == expected
        return ret

    def inner_find_roots(self) -> Set[str]:
        return {nid for nid in self.state.nodes if not self.state.upstream.get(nid)}

    @transition(DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        expected = {nid for nid in self.state.nodes if not self.state.downstream.get(nid)}
        assert ret == expected
        return ret

    def inner_find_leaves(self) -> Set[str]:
        return {nid for nid in self.state.nodes if not self.state.downstream.get(nid)}

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.all_dependencies_exist())
        require(self.state.find_cycle() is None)
        require_arg(
            estimated_durations,
            Domain.optional(Domain.type(Mapping[str, float])),
            preferred=[None, {"n1": 2.0}],
        )
        ret = self.inner_compute_critical_path(estimated_durations)
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        assert ret[1] >= 0.0
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        return self.state.compute_critical_path(estimated_durations)

    # --------------------------------------------------------------------------
    # WaveScheduler Transitions
    # --------------------------------------------------------------------------

    @transition(WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        ret = self.inner_next_wave()
        assert isinstance(ret, list)
        return ret

    def inner_next_wave(self) -> List[str]:
        return self.state.compute_next_wave()

    @transition(WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_mark_running(node_id)
        self.state.node_states[node_id] = NodeState.RUNNING
        assert self.state.node_states[node_id] == NodeState.RUNNING

    def inner_mark_running(self, node_id: str) -> None:
        self.state.node_states[node_id] = NodeState.RUNNING

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_mark_succeeded(node_id)
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        self.state.promote_dependents(node_id)
        assert self.state.node_states[node_id] == NodeState.SUCCEEDED

    def inner_mark_succeeded(self, node_id: str) -> None:
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        self.state.promote_dependents(node_id)

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        require_arg(
            failure_policy,
            Domain.sampled_from(list(FailurePolicy)),
            preferred=[
                FailurePolicy.FAIL_FAST,
                FailurePolicy.CONTINUE_ON_ERROR,
                FailurePolicy.SKIP_DOWNSTREAM,
            ],
        )
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.apply_failure_policy(node_id, failure_policy)
        assert self.state.node_states[node_id] == NodeState.FAILED

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        self.state.apply_failure_policy(node_id, failure_policy)

    @transition(WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    def inner_is_finished(self) -> bool:
        return self.state.compute_is_finished()

    @transition(WaveScheduler.get_state)
    def get_state(self, node_id: str) -> NodeState:
        require(len(self.state.nodes) > 0)
        require_arg(node_id, Domain.in_set(self.state.nodes.keys()))
        ret = self.inner_get_state(node_id)
        assert ret in NodeState
        return ret

    def inner_get_state(self, node_id: str) -> NodeState:
        if node_id not in self.state.nodes:
            raise NodeNotFoundError(f"Node not found: {node_id}", node_id)
        return self.state.get_node_state(node_id)

    @transition(WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, NodeState]:
        ret = self.inner_get_all_states()
        assert isinstance(ret, dict)
        return ret

    def inner_get_all_states(self) -> Mapping[str, NodeState]:
        return self.state.get_all_node_states()

    # --------------------------------------------------------------------------
    # DAGRunner Transitions
    # --------------------------------------------------------------------------

    @transition(DAGRunner.run)
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        require(self.state.all_dependencies_exist())
        require(self.state.find_cycle() is None)
        require_arg(
            failure_policy,
            Domain.sampled_from(list(FailurePolicy)),
            preferred=[
                FailurePolicy.FAIL_FAST,
                FailurePolicy.CONTINUE_ON_ERROR,
                FailurePolicy.SKIP_DOWNSTREAM,
            ],
        )
        ret = self.inner_run(failure_policy)
        assert isinstance(ret, DAGRunReport)
        assert ret.total_nodes == len(self.state.nodes)
        return ret

    def inner_run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        for nid, defn in self.state.nodes.items():
            for dep in defn.dependencies:
                if dep not in self.state.nodes:
                    raise NodeNotFoundError(f"Dependency not found: {dep}", dep)
        cycle = self.state.find_cycle()
        if cycle:
            raise CycleError(f"Cycle detected: {cycle}", tuple(cycle))
        return self.state.execute_run(failure_policy)

    # --------------------------------------------------------------------------
    # Seeding Transitions
    # --------------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = DAGEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngineLite = synthesize_fake(DAGEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DAGEngineLiteState] = None) -> Any:
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_dag_fake(state: Optional[DAGEngineLiteState] = None) -> DAG:
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_wave_scheduler_fake(state: Optional[DAGEngineLiteState] = None) -> WaveScheduler:
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_dag_runner_fake(state: Optional[DAGEngineLiteState] = None) -> DAGRunner:
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_dag_engine_lite_fakes(
    state: Optional[DAGEngineLiteState] = None,
) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    fake = FakeDAGEngineLite(state=state or proto.make_initial_state())
    return (fake, fake, fake)


FakeDAGEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeDAGEngineLiteFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestDAGEngineLiteFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_dag_engine_lite_fake()
        self.sm = DAGEngineLiteStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()

        self.fake.add_node("n1", _default_action, None, 1, 0)
        self.fake.add_node("n2", _default_action, ["n1"], 2, 1)
        self.fake.add_node("n3", _default_action, None, 0, 0)

        self.fake.add_edge("n1", "n3")

        res_has = self.fake.has_node("n1")
        assert res_has is True

        node_n1 = self.fake.get_node("n1")
        assert node_n1.node_id == "n1"

        deps = self.fake.get_dependencies("n2")
        assert "n1" in deps

        depents = self.fake.get_dependents("n1")
        assert "n2" in depents

        all_n = self.fake.all_nodes()
        assert len(all_n) == 3

        self.fake.validate()

        order = self.fake.topological_sort()
        assert len(order) == 3

        roots = self.fake.find_roots()
        assert "n1" in roots

        leaves = self.fake.find_leaves()
        assert "n2" in leaves

        path, weight = self.fake.compute_critical_path({"n1": 1.5, "n2": 2.5, "n3": 0.5})
        assert weight > 0.0

        wave1 = self.fake.next_wave()
        assert "n1" in wave1

        self.fake.mark_running("n1")
        self.fake.mark_succeeded("n1")
        self.fake.mark_failed("n3", FailurePolicy.CONTINUE_ON_ERROR)

        fin = self.fake.is_finished()
        assert isinstance(fin, bool)

        st = self.fake.get_state("n1")
        assert st == NodeState.SUCCEEDED

        all_st = self.fake.get_all_states()
        assert "n1" in all_st

        report = self.fake.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 3

        self.fake.remove_node("n3")
        assert not self.fake.has_node("n3")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:43:32Z
# LAST_CHANGED: 2026-11-09T22:43:32Z
# CHANGE: Gate add_node node_id parameter using Domain.not_in(self.state.nodes.keys()) to prevent duplicate node identifier contract violations during generative fuzz testing, and add acyclic and dependency existence preconditions on validate, topological_sort, compute_critical_path, and run
# --- END AUTOFAB METADATA ---
