# === File: dag_engine_lite_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    StateMachine,
    raises,
    require,
    sut,
    sut_state,
    synthesize_fake,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

import benchmarks.runs.dag_engine_lite_gemini_flash_1.parts.dag_engine_lite.lib.dag_engine_lite as dag_engine_lite
import benchmarks.runs.dag_engine_lite_gemini_flash_1.parts.dag_engine_lite.lib.dag_engine_lite_impl as dag_engine_lite_impl
from benchmarks.runs.dag_engine_lite_gemini_flash_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DAGEngineLiteStateMachine,
    proto,
)


def _dummy_action() -> int:
    return 42


def _failing_action() -> int:
    raise RuntimeError("Intentional node failure")


_retry_counter = 0


def _retry_succeeds_action() -> int:
    global _retry_counter
    _retry_counter += 1
    if _retry_counter < 2:
        raise RuntimeError("Transient failure on attempt 1")
    return 100


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class DAGEngineLiteImplPseudoStateMachine(DAGEngineLiteStateMachine):
    """Implementation pseudo-state machine overriding inner transitions to drive concrete SUT."""

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.add_node(node_id, action, dependencies, priority, retries)

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.add_edge(upstream_id, downstream_id)

    def inner_remove_node(self, node_id: str) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.remove_node(node_id)

    def inner_has_node(self, node_id: str) -> bool:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.has_node(node_id)

    def inner_get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.get_node(node_id)

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.get_dependencies(node_id)

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.get_dependents(node_id)

    def inner_all_nodes(self) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.all_nodes()

    def inner_validate(self) -> None:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.validate()

    def inner_topological_sort(self) -> List[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.topological_sort()

    def inner_find_roots(self) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.find_roots()

    def inner_find_leaves(self) -> Set[str]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.find_leaves()

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        target: dag_engine_lite.DAG = sut(dag_engine_lite.DAG)
        return target.compute_critical_path(estimated_durations)

    def inner_next_wave(self) -> List[str]:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.next_wave()

    def inner_mark_running(self, node_id: str) -> None:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.mark_running(node_id)

    def inner_mark_succeeded(self, node_id: str) -> None:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.mark_succeeded(node_id)

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.mark_failed(node_id, failure_policy)

    def inner_is_finished(self) -> bool:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.is_finished()

    def inner_get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.get_state(node_id)

    def inner_get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        target: dag_engine_lite.WaveScheduler = sut(dag_engine_lite.WaveScheduler)
        return target.get_all_states()

    def inner_run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        target: dag_engine_lite.DAGRunner = sut(dag_engine_lite.DAGRunner)
        return target.run(failure_policy)


impl_proto = DAGEngineLiteImplPseudoStateMachine()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestDAGEngineLiteImplReal(unittest.TestCase):
    """Verifies that concrete library realization satisfies specification contracts."""

    def setUp(self) -> None:
        global _retry_counter
        _retry_counter = 0
        self.registry = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real_dag = get_singleton(dag_engine_lite.DAG)
        self.real_scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self.real_runner = get_singleton(dag_engine_lite.DAGRunner)
        self.sm = DAGEngineLiteImplPseudoStateMachine(
            singletons={
                dag_engine_lite.DAG: self.real_dag,
                dag_engine_lite.WaveScheduler: self.real_scheduler,
                dag_engine_lite.DAGRunner: self.real_runner,
            }
        )
        self.checked_dag: Any = self.sm.as_checked(dag_engine_lite.DAG, self.real_dag)
        self.checked_scheduler: Any = self.sm.as_checked(dag_engine_lite.WaveScheduler, self.real_scheduler)
        self.checked_runner: Any = self.sm.as_checked(dag_engine_lite.DAGRunner, self.real_runner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    # --- DAG Happy Path & Queries ---

    def test_dag_lifecycle_basic(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, ["a"], 1, 0)
        self.checked_dag.add_edge("b", "c")
        _ = self.checked_dag.has_node("a")
        _ = self.checked_dag.has_node("missing")
        _ = self.checked_dag.get_node("a")
        _ = self.checked_dag.get_dependencies("b")
        _ = self.checked_dag.get_dependents("a")
        _ = self.checked_dag.all_nodes()
        self.checked_dag.validate()
        _ = self.checked_dag.topological_sort()
        _ = self.checked_dag.find_roots()
        _ = self.checked_dag.find_leaves()
        _ = self.checked_dag.compute_critical_path(None)
        _ = self.checked_dag.compute_critical_path({"a": 2.0, "b": 3.0, "c": 1.0})
        self.checked_dag.remove_node("c")

    def test_remove_node_purge_incident_edges(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, ["b"], 1, 0)
        assert "b" in self.checked_dag.get_dependents("a")
        assert "b" in self.checked_dag.get_dependencies("c")
        _ = self.checked_scheduler.get_all_states()
        self.checked_dag.remove_node("b")
        assert self.checked_dag.has_node("b") is False
        assert "b" not in self.checked_dag.get_dependents("a")
        assert "b" not in self.checked_dag.get_dependencies("c")
        assert "b" not in self.checked_scheduler.get_all_states()

    def test_critical_path_longest_path(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("d", _dummy_action, ["b", "c"], 1, 0)
        durations = {"a": 1.0, "b": 10.0, "c": 2.0, "d": 1.0}
        path, weight = self.checked_dag.compute_critical_path(durations)
        assert path == ["a", "b", "d"]
        assert weight == 12.0

    def test_critical_path_empty_graph(self) -> None:
        path, weight = self.checked_dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0

    # --- Contract Violation Tests for DAG ---

    def test_add_node_duplicate_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 0, 0)
        self.checked_dag.violating(dag_engine_lite.DuplicateNodeError).add_node("a", _dummy_action, None, 0, 0)

    def test_add_edge_missing_upstream_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 0, 0)
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).add_edge("missing", "a")

    def test_add_edge_missing_downstream_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 0, 0)
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).add_edge("a", "missing")

    def test_remove_node_missing_error(self) -> None:
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).remove_node("missing")

    def test_get_node_missing_error(self) -> None:
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).get_node("missing")

    def test_get_dependencies_missing_error(self) -> None:
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).get_dependencies("missing")

    def test_get_dependents_missing_error(self) -> None:
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).get_dependents("missing")

    def test_validate_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, ["missing_dep"], 0, 0)
        self.checked_dag.violating(dag_engine_lite.NodeNotFoundError).validate()

    def test_validate_cycle_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 0, 0)
        self.checked_dag.add_node("b", _dummy_action, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        self.checked_dag.violating(dag_engine_lite.CycleError).validate()

    def test_topological_sort_cycle_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 0, 0)
        self.checked_dag.add_node("b", _dummy_action, None, 0, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        self.checked_dag.violating(dag_engine_lite.CycleError).topological_sort()

    # --- WaveScheduler Tests ---

    def test_scheduler_is_finished_empty_dag(self) -> None:
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_is_finished_non_terminal_remaining(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        assert self.checked_scheduler.is_finished() is False
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        assert self.checked_scheduler.is_finished() is False

    def test_scheduler_is_finished_blocked_by_failure(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.is_finished() is True

    def test_wave_scheduler_lifecycle(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        _ = self.checked_scheduler.is_finished()
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        _ = self.checked_scheduler.get_state("a")
        _ = self.checked_scheduler.get_all_states()
        self.checked_scheduler.mark_succeeded("a")
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("b")
        self.checked_scheduler.mark_succeeded("b")
        _ = self.checked_scheduler.is_finished()

    def test_scheduler_get_state_query(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.READY
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.PENDING

    def test_scheduler_get_state_missing_error(self) -> None:
        self.checked_scheduler.violating(dag_engine_lite.NodeNotFoundError).get_state("missing")

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, None, 5, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.CANCELLED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, ["b"], 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_scheduler.get_state("a") == dag_engine_lite.NodeState.FAILED
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.get_state("c") == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.is_finished() is True

    def test_scheduler_mark_failed_continue_on_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, None, 1, 0)
        _ = self.checked_scheduler.next_wave()
        self.checked_scheduler.mark_running("a")
        self.checked_scheduler.mark_failed("a", dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert self.checked_scheduler.is_finished() is False
        assert self.checked_scheduler.get_state("b") == dag_engine_lite.NodeState.SKIPPED
        assert self.checked_scheduler.get_state("c") == dag_engine_lite.NodeState.READY
        self.checked_scheduler.mark_running("c")
        self.checked_scheduler.mark_succeeded("c")
        assert self.checked_scheduler.is_finished() is True

    # --- DAGRunner Tests ---

    def test_runner_success(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2

    def test_runner_missing_dependency_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, ["missing"], 10, 0)
        self.checked_runner.violating(dag_engine_lite.NodeNotFoundError).run(dag_engine_lite.FailurePolicy.FAIL_FAST)

    def test_runner_cycle_error(self) -> None:
        self.checked_dag.add_node("a", _dummy_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, None, 5, 0)
        self.checked_dag.add_edge("a", "b")
        self.checked_dag.add_edge("b", "a")
        self.checked_runner.violating(dag_engine_lite.CycleError).run(dag_engine_lite.FailurePolicy.FAIL_FAST)

    def test_runner_fail_fast_policy(self) -> None:
        self.checked_dag.add_node("a", _failing_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, None, 5, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert len(report.failed_nodes) == 1

    def test_runner_skip_downstream_policy(self) -> None:
        self.checked_dag.add_node("a", _failing_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, ["b"], 1, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM)
        assert len(report.failed_nodes) == 1
        assert "b" in report.skipped_nodes
        assert "c" in report.skipped_nodes

    def test_runner_continue_on_error_policy(self) -> None:
        self.checked_dag.add_node("a", _failing_action, None, 10, 0)
        self.checked_dag.add_node("b", _dummy_action, ["a"], 5, 0)
        self.checked_dag.add_node("c", _dummy_action, None, 1, 0)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR)
        assert len(report.succeeded_nodes) == 1

    def test_runner_retry_success(self) -> None:
        self.checked_dag.add_node("a", _retry_succeeds_action, None, 10, 2)
        report = self.checked_runner.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        assert len(report.succeeded_nodes) == 1


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

class DAGEngineLiteSUT:
    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        dag_engine_lite_impl.__initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(dag_engine_lite.DAG)
        self.scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self.runner = get_singleton(dag_engine_lite.DAGRunner)
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
    proto=impl_proto,
    sut_factory=make_sut,
    initial_state_factory=impl_proto.make_initial_state,
    name="DAGEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T02:42:25Z
# LAST_CHANGED: 2026-11-11T02:37:10Z
# CHANGE: Add test_scheduler_is_finished_blocked_by_failure and assert is_finished status across failure policy scenarios to cover blocked dependency completion
# PRETENSE_COVERAGE_AUDIT: 2026-11-11T02:42:25Z
# PRETENSE_QA_AUDIT: 2026-11-11T02:41:37Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

import benchmarks.runs.dag_engine_lite_gemini_flash_1.parts.dag_engine_lite.lib.dag_engine_lite as dag_engine_lite


def _dummy_action() -> int:
    return 42


def _detect_cycle_dfs(
    node: str,
    dependencies: dict[str, set[str]],
    visited: dict[str, int],
    path: list[str],
) -> Optional[Tuple[str, ...]]:
    visited[node] = 1
    path.append(node)
    for upstream in sorted(dependencies.get(node, set())):
        if visited.get(upstream, 0) == 1:
            idx = path.index(upstream)
            return tuple(path[idx:])
        if visited.get(upstream, 0) == 0:
            cycle = _detect_cycle_dfs(upstream, dependencies, visited, path)
            if cycle is not None:
                return cycle
    visited[node] = 2
    path.pop()
    return None


def _find_cycle(
    nodes: dict[str, dag_engine_lite.NodeDefinition[Any]],
    dependencies: dict[str, set[str]],
) -> Optional[Tuple[str, ...]]:
    visited: dict[str, int] = {}
    path: list[str] = []
    for node_id in sorted(nodes.keys()):
        if visited.get(node_id, 0) == 0:
            cycle = _detect_cycle_dfs(node_id, dependencies, visited, path)
            if cycle is not None:
                return cycle
    return None


def _best_candidate(
    candidates: list[str],
    nodes: dict[str, dag_engine_lite.NodeDefinition[Any]],
) -> str:
    best_id = candidates[0]
    best_priority = nodes[best_id].priority
    for cid in candidates[1:]:
        cp = nodes[cid].priority
        if cp > best_priority or (cp == best_priority and cid < best_id):
            best_id = cid
            best_priority = cp
    return best_id


def _topo_sort(
    nodes: dict[str, dag_engine_lite.NodeDefinition[Any]],
    dependencies: dict[str, set[str]],
) -> List[str]:
    in_degree: dict[str, int] = {
        nid: len([u for u in dependencies.get(nid, set()) if u in nodes])
        for nid in nodes
    }
    result: list[str] = []
    available = set(nodes.keys())
    for _ in range(len(nodes)):
        candidates = [nid for nid in available if in_degree[nid] == 0]
        if not candidates:
            cycle = _find_cycle(nodes, dependencies)
            c = cycle if cycle is not None else tuple(sorted(available))
            raise dag_engine_lite.CycleError(
                cycle=c,
                message=f"Cycle detected among nodes: {c}",
            )
        best = _best_candidate(candidates, nodes)
        result.append(best)
        available.remove(best)
        for dep in nodes:
            if best in dependencies.get(dep, set()):
                in_degree[dep] -= 1
    return result


def _critical_path(
    order: list[str],
    durations: Mapping[str, float],
    dependencies: dict[str, set[str]],
) -> Tuple[List[str], float]:
    if not order:
        return ([], 0.0)
    earliest: dict[str, float] = {}
    predecessor: dict[str, Optional[str]] = {}
    for nid in order:
        d = durations.get(nid, 1.0)
        upstreams = dependencies.get(nid, set())
        max_prev = 0.0
        best_p: Optional[str] = None
        for p in upstreams:
            if p in earliest and earliest[p] > max_prev:
                max_prev = earliest[p]
                best_p = p
        earliest[nid] = max_prev + d
        predecessor[nid] = best_p

    end_node = order[0]
    max_time = earliest[end_node]
    for nid in order[1:]:
        if earliest[nid] > max_time:
            max_time = earliest[nid]
            end_node = nid

    path: list[str] = []
    curr: Optional[str] = end_node
    for _ in range(len(order) + 1):
        if curr is None:
            break
        path.append(curr)
        curr = predecessor.get(curr)
    path.reverse()
    return (path, max_time)


def _sync_scheduler_states(state: DAGEngineLiteState) -> None:
    roots = {
        nid for nid in state.node_ids
        if not [u for u in state.dependencies.get(nid, set()) if u in state.node_ids]
    }
    for nid in state.node_ids:
        if nid not in state.node_states:
            if nid in roots:
                state.node_states[nid] = dag_engine_lite.NodeState.READY
            else:
                state.node_states[nid] = dag_engine_lite.NodeState.PENDING


def _get_transitive_dependents(node_id: str, state: DAGEngineLiteState) -> set[str]:
    result: set[str] = set()
    queue = list(state.dependents.get(node_id, set()))
    for _ in range(len(state.node_ids) + 1):
        if not queue:
            break
        curr = queue.pop(0)
        if curr not in result and curr in state.node_ids:
            result.add(curr)
            queue.extend(state.dependents.get(curr, set()))
    return result


_NODE_POOL: tuple[str, ...] = tuple(f"node_{i}" for i in range(1, 51)) + (
    "n1", "n2", "n3", "n4", "n5",
    "a", "b", "c", "d", "e",
)


def _dependencies_exist(state: DAGEngineLiteState) -> bool:
    for defn in state.nodes.values():
        for dep in defn.dependencies:
            if dep not in state.node_ids:
                return False
    for nid, deps in state.dependencies.items():
        if nid in state.node_ids:
            for dep in deps:
                if dep not in state.node_ids:
                    return False
    return True


def _is_acyclic(state: DAGEngineLiteState) -> bool:
    return _find_cycle(state.nodes, state.dependencies) is None


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class DAGEngineLiteState:
    """Canonical model state tracking nodes, edges, and lifecycle execution states."""
    nodes: dict[str, dag_engine_lite.NodeDefinition[Any]] = field(default_factory=dict)
    node_ids: set[str] = field(default_factory=set)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    dependents: dict[str, set[str]] = field(default_factory=dict)
    node_states: dict[str, dag_engine_lite.NodeState] = field(default_factory=dict)

    @property
    def available_node_ids(self) -> set[str]:
        return set(_NODE_POOL) - self.node_ids

    @property
    def dependencies_exist(self) -> bool:
        return _dependencies_exist(self)

    @property
    def is_acyclic(self) -> bool:
        return _is_acyclic(self)


class DAGEngineLiteStateMachine(StateMachine[DAGEngineLiteState]):
    """Unified Pretense State Machine for DAG Engine Lite."""

    def __init__(
        self,
        state: Optional[DAGEngineLiteState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> DAGEngineLiteState:
        return DAGEngineLiteState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.nodes.clear()
        self.state.node_ids.clear()
        self.state.dependencies.clear()
        self.state.dependents.clear()
        self.state.node_states.clear()

    # --- DAG Transitions ---

    @transition(dag_engine_lite.DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        require(bool(self.state.available_node_ids))
        require_arg(node_id, Domain.in_set(self.state.available_node_ids), error=dag_engine_lite.DuplicateNodeError)
        require_arg(action, Domain.any())
        require_arg(dependencies, Domain.optional(Domain.type(Collection[str])))
        require_arg(priority, Domain.range(-100, 100), preferred=[0, 1, 10])
        require_arg(retries, Domain.range(0, 5), preferred=[0, 1, 2])
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        frozen_deps = frozenset(dependencies) if dependencies is not None else frozenset()
        self.state.nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_deps,
            priority=priority,
            retries=retries,
        )
        self.state.node_ids.add(node_id)
        if node_id not in self.state.dependencies:
            self.state.dependencies[node_id] = set()
        if node_id not in self.state.dependents:
            self.state.dependents[node_id] = set()
        if dependencies is not None:
            for dep in dependencies:
                self.state.dependencies[node_id].add(dep)
                if dep not in self.state.dependents:
                    self.state.dependents[dep] = set()
                self.state.dependents[dep].add(node_id)
        assert node_id in self.state.node_ids
        return ret

    def inner_add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        if node_id in self.state.node_ids:
            raise dag_engine_lite.DuplicateNodeError(
                node_id=node_id,
                message=f"Node {node_id} already exists in DAG",
            )
        return None

    @transition(dag_engine_lite.DAG.add_edge)
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        require(bool(self.state.node_ids))
        require_arg(upstream_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        require_arg(downstream_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_add_edge(upstream_id, downstream_id)
        if downstream_id not in self.state.dependencies:
            self.state.dependencies[downstream_id] = set()
        self.state.dependencies[downstream_id].add(upstream_id)
        if upstream_id not in self.state.dependents:
            self.state.dependents[upstream_id] = set()
        self.state.dependents[upstream_id].add(downstream_id)
        assert upstream_id in self.state.dependencies[downstream_id]
        return ret

    def inner_add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=upstream_id,
                message=f"Upstream node {upstream_id} not found",
            )
        if downstream_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=downstream_id,
                message=f"Downstream node {downstream_id} not found",
            )
        return None

    @transition(dag_engine_lite.DAG.remove_node)
    def remove_node(self, node_id: str) -> None:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_remove_node(node_id)
        self.state.nodes.pop(node_id, None)
        self.state.node_ids.discard(node_id)
        self.state.node_states.pop(node_id, None)
        deps = self.state.dependencies.pop(node_id, set())
        for d in deps:
            if d in self.state.dependents:
                self.state.dependents[d].discard(node_id)
        dependents = self.state.dependents.pop(node_id, set())
        for dep in dependents:
            if dep in self.state.dependencies:
                self.state.dependencies[dep].discard(node_id)
        assert node_id not in self.state.node_ids
        return ret

    def inner_remove_node(self, node_id: str) -> None:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found",
            )
        return None

    @transition(dag_engine_lite.DAG.has_node)
    def has_node(self, node_id: str) -> bool:
        require_arg(node_id, Domain.type(str))
        ret = self.inner_has_node(node_id)
        assert ret == (node_id in self.state.node_ids)
        return ret

    def inner_has_node(self, node_id: str) -> bool:
        return node_id in self.state.node_ids

    @transition(dag_engine_lite.DAG.get_node)
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_get_node(node_id)
        assert ret.node_id == node_id
        return ret

    def inner_get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found",
            )
        return self.state.nodes[node_id]

    @transition(dag_engine_lite.DAG.get_dependencies)
    def get_dependencies(self, node_id: str) -> Set[str]:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_get_dependencies(node_id)
        assert ret == self.state.dependencies.get(node_id, set())
        return ret

    def inner_get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found",
            )
        return set(self.state.dependencies.get(node_id, set()))

    @transition(dag_engine_lite.DAG.get_dependents)
    def get_dependents(self, node_id: str) -> Set[str]:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_get_dependents(node_id)
        assert ret == self.state.dependents.get(node_id, set())
        return ret

    def inner_get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found",
            )
        return set(self.state.dependents.get(node_id, set()))

    @transition(dag_engine_lite.DAG.all_nodes)
    def all_nodes(self) -> Set[str]:
        ret = self.inner_all_nodes()
        assert ret == set(self.state.node_ids)
        return ret

    def inner_all_nodes(self) -> Set[str]:
        return set(self.state.node_ids)

    @transition(dag_engine_lite.DAG.validate)
    def validate(self) -> None:
        require(self.state.dependencies_exist)
        require(self.state.is_acyclic)
        ret = self.inner_validate()
        assert ret is None
        return ret

    def inner_validate(self) -> None:
        for nid, defn in self.state.nodes.items():
            for dep in defn.dependencies:
                if dep not in self.state.node_ids:
                    raise dag_engine_lite.NodeNotFoundError(
                        node_id=dep,
                        message=f"Referenced dependency {dep} not registered in graph",
                    )
        cycle = _find_cycle(self.state.nodes, self.state.dependencies)
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                cycle=cycle,
                message=f"Directed cycle detected: {cycle}",
            )
        return None

    @transition(dag_engine_lite.DAG.topological_sort)
    def topological_sort(self) -> List[str]:
        require(self.state.dependencies_exist)
        require(self.state.is_acyclic)
        ret = self.inner_topological_sort()
        assert len(ret) == len(self.state.node_ids)
        return ret

    def inner_topological_sort(self) -> List[str]:
        return _topo_sort(self.state.nodes, self.state.dependencies)

    @transition(dag_engine_lite.DAG.find_roots)
    def find_roots(self) -> Set[str]:
        ret = self.inner_find_roots()
        assert isinstance(ret, set)
        return ret

    def inner_find_roots(self) -> Set[str]:
        return {
            nid for nid in self.state.node_ids
            if not [u for u in self.state.dependencies.get(nid, set()) if u in self.state.node_ids]
        }

    @transition(dag_engine_lite.DAG.find_leaves)
    def find_leaves(self) -> Set[str]:
        ret = self.inner_find_leaves()
        assert isinstance(ret, set)
        return ret

    def inner_find_leaves(self) -> Set[str]:
        return {
            nid for nid in self.state.node_ids
            if not [d for d in self.state.dependents.get(nid, set()) if d in self.state.node_ids]
        }

    @transition(dag_engine_lite.DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.dependencies_exist)
        require(self.state.is_acyclic)
        require_arg(estimated_durations, Domain.optional(Domain.type(Mapping[str, float])))
        ret = self.inner_compute_critical_path(estimated_durations)
        assert ret[1] >= 0.0
        return ret

    def inner_compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        if not self.state.node_ids:
            return ([], 0.0)
        durations = estimated_durations if estimated_durations is not None else {}
        order = _topo_sort(self.state.nodes, self.state.dependencies)
        return _critical_path(order, durations, self.state.dependencies)

    # --- WaveScheduler Transitions ---

    @transition(dag_engine_lite.WaveScheduler.next_wave)
    def next_wave(self) -> List[str]:
        ret = self.inner_next_wave()
        assert isinstance(ret, list)
        return ret

    def inner_next_wave(self) -> List[str]:
        _sync_scheduler_states(self.state)
        ready_candidates: list[str] = []
        for nid in sorted(self.state.node_ids):
            if self.state.node_states.get(nid) == dag_engine_lite.NodeState.READY:
                upstreams = self.state.dependencies.get(nid, set())
                if all(self.state.node_states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstreams):
                    ready_candidates.append(nid)
        sorted_candidates: list[str] = []
        rem = list(ready_candidates)
        for _ in range(len(ready_candidates)):
            best = _best_candidate(rem, self.state.nodes)
            sorted_candidates.append(best)
            rem.remove(best)
        return sorted_candidates

    @transition(dag_engine_lite.WaveScheduler.mark_running)
    def mark_running(self, node_id: str) -> None:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_mark_running(node_id)
        self.state.node_states[node_id] = dag_engine_lite.NodeState.RUNNING
        assert self.state.node_states[node_id] == dag_engine_lite.NodeState.RUNNING
        return ret

    def inner_mark_running(self, node_id: str) -> None:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found in scheduler",
            )
        return None

    @transition(dag_engine_lite.WaveScheduler.mark_succeeded)
    def mark_succeeded(self, node_id: str) -> None:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_mark_succeeded(node_id)
        self.state.node_states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dep in self.state.dependents.get(node_id, set()):
            if dep in self.state.node_ids:
                upstreams = self.state.dependencies.get(dep, set())
                if all(self.state.node_states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstreams):
                    if self.state.node_states.get(dep) == dag_engine_lite.NodeState.PENDING:
                        self.state.node_states[dep] = dag_engine_lite.NodeState.READY
        assert self.state.node_states[node_id] == dag_engine_lite.NodeState.SUCCEEDED
        return ret

    def inner_mark_succeeded(self, node_id: str) -> None:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found in scheduler",
            )
        return None

    @transition(dag_engine_lite.WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        require_arg(failure_policy, Domain.sampled_from(list(dag_engine_lite.FailurePolicy)))
        ret = self.inner_mark_failed(node_id, failure_policy)
        self.state.node_states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid in self.state.node_ids:
                if self.state.node_states.get(nid) in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                ):
                    self.state.node_states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            downstream_nodes = _get_transitive_dependents(node_id, self.state)
            for d in downstream_nodes:
                if self.state.node_states.get(d) not in (
                    dag_engine_lite.NodeState.SUCCEEDED,
                    dag_engine_lite.NodeState.FAILED,
                ):
                    self.state.node_states[d] = dag_engine_lite.NodeState.SKIPPED
        elif failure_policy == dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            downstream_nodes = _get_transitive_dependents(node_id, self.state)
            for d in downstream_nodes:
                if self.state.node_states.get(d) not in (
                    dag_engine_lite.NodeState.SUCCEEDED,
                    dag_engine_lite.NodeState.FAILED,
                ):
                    self.state.node_states[d] = dag_engine_lite.NodeState.SKIPPED
        assert self.state.node_states[node_id] == dag_engine_lite.NodeState.FAILED
        return ret

    def inner_mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not found in scheduler",
            )
        return None

    @transition(dag_engine_lite.WaveScheduler.is_finished)
    def is_finished(self) -> bool:
        ret = self.inner_is_finished()
        assert isinstance(ret, bool)
        return ret

    def inner_is_finished(self) -> bool:
        if not self.state.node_ids:
            return True
        _sync_scheduler_states(self.state)
        terminal_states = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        all_terminal = all(self.state.node_states.get(nid) in terminal_states for nid in self.state.node_ids)
        if all_terminal:
            return True
        ready = [
            nid for nid in self.state.node_ids
            if self.state.node_states.get(nid) == dag_engine_lite.NodeState.READY
        ]
        if not ready:
            has_unblocked = False
            for nid in self.state.node_ids:
                if self.state.node_states.get(nid) == dag_engine_lite.NodeState.PENDING:
                    upstreams = self.state.dependencies.get(nid, set())
                    if not any(self.state.node_states.get(u) == dag_engine_lite.NodeState.FAILED for u in upstreams):
                        has_unblocked = True
            if not has_unblocked:
                return True
        return False

    @transition(dag_engine_lite.WaveScheduler.get_state)
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        require(bool(self.state.node_ids))
        require_arg(node_id, Domain.in_set(self.state.node_ids), error=dag_engine_lite.NodeNotFoundError)
        ret = self.inner_get_state(node_id)
        assert isinstance(ret, dag_engine_lite.NodeState)
        return ret

    def inner_get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self.state.node_ids:
            raise dag_engine_lite.NodeNotFoundError(
                node_id=node_id,
                message=f"Node {node_id} not registered in DAG",
            )
        _sync_scheduler_states(self.state)
        return self.state.node_states.get(node_id, dag_engine_lite.NodeState.PENDING)

    @transition(dag_engine_lite.WaveScheduler.get_all_states)
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        ret = self.inner_get_all_states()
        assert isinstance(ret, Mapping)
        return ret

    def inner_get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        _sync_scheduler_states(self.state)
        return {
            nid: self.state.node_states.get(nid, dag_engine_lite.NodeState.PENDING)
            for nid in self.state.node_ids
        }

    # --- DAGRunner Transitions ---

    @transition(dag_engine_lite.DAGRunner.run)
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        require(self.state.dependencies_exist)
        require(self.state.is_acyclic)
        require_arg(failure_policy, Domain.sampled_from(list(dag_engine_lite.FailurePolicy)))
        ret = self.inner_run(failure_policy)
        assert isinstance(ret, dag_engine_lite.DAGRunReport)
        return ret

    def inner_run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        self.inner_validate()
        _sync_scheduler_states(self.state)
        order = _topo_sort(self.state.nodes, self.state.dependencies)
        path, _ = _critical_path(order, {}, self.state.dependencies)
        results: dict[str, dag_engine_lite.NodeResult[Any]] = {}
        succeeded: list[str] = []
        failed: list[str] = []
        skipped: list[str] = []
        cancelled: list[str] = []

        for nid in order:
            upstreams = self.state.dependencies.get(nid, set())
            if any(u in failed or u in skipped for u in upstreams):
                self.state.node_states[nid] = dag_engine_lite.NodeState.SKIPPED
                skipped.append(nid)
                results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=dag_engine_lite.NodeState.SKIPPED,
                )
                continue
            defn = self.state.nodes[nid]
            try:
                val = defn.action()
                self.state.node_states[nid] = dag_engine_lite.NodeState.SUCCEEDED
                succeeded.append(nid)
                results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=dag_engine_lite.NodeState.SUCCEEDED,
                    value=val,
                )
            except Exception as exc:
                self.state.node_states[nid] = dag_engine_lite.NodeState.FAILED
                failed.append(nid)
                results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=dag_engine_lite.NodeState.FAILED,
                    error=exc,
                )
                if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                    for rem in order:
                        if rem not in results:
                            self.state.node_states[rem] = dag_engine_lite.NodeState.CANCELLED
                            cancelled.append(rem)
                            results[rem] = dag_engine_lite.NodeResult(
                                node_id=rem,
                                state=dag_engine_lite.NodeState.CANCELLED,
                            )
                    break

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self.state.node_ids),
            succeeded_nodes=tuple(succeeded),
            failed_nodes=tuple(failed),
            skipped_nodes=tuple(skipped),
            cancelled_nodes=tuple(cancelled),
            wall_clock_seconds=0.01,
            critical_path=tuple(path),
            results=results,
        )


proto = DAGEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeDAGEngineLite = synthesize_fake(DAGEngineLiteStateMachine)


def make_dag_engine_lite_fake(state: Optional[DAGEngineLiteState] = None) -> Any:
    """Synthesizes fake instance implementing all DAG Engine Lite interfaces."""
    return FakeDAGEngineLite(state=state or proto.make_initial_state())


def make_dag_engine_lite_fakes(
    state: Optional[DAGEngineLiteState] = None,
) -> Tuple[dag_engine_lite.DAG, dag_engine_lite.WaveScheduler, dag_engine_lite.DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
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
        self.fake.add_node("n1", _dummy_action, None, 10, 0)
        self.fake.add_node("n2", _dummy_action, ["n1"], 5, 0)
        self.fake.add_edge("n1", "n2")
        _ = self.fake.has_node("n1")
        _ = self.fake.get_node("n1")
        _ = self.fake.get_dependencies("n2")
        _ = self.fake.get_dependents("n1")
        _ = self.fake.all_nodes()
        self.fake.validate()
        _ = self.fake.topological_sort()
        _ = self.fake.find_roots()
        _ = self.fake.find_leaves()
        _ = self.fake.compute_critical_path(None)
        _ = self.fake.next_wave()
        self.fake.mark_running("n1")
        self.fake.mark_succeeded("n1")
        self.fake.mark_failed("n2", dag_engine_lite.FailurePolicy.FAIL_FAST)
        _ = self.fake.is_finished()
        _ = self.fake.get_state("n1")
        _ = self.fake.get_all_states()
        _ = self.fake.run(dag_engine_lite.FailurePolicy.FAIL_FAST)
        self.fake.remove_node("n2")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T02:11:36Z
# LAST_CHANGED: 2026-11-11T02:11:36Z
# CHANGE: Constrain retries parameter in add_node with Domain.range(0, 5) and priority with Domain.range(-100, 100) to prevent unconstrained retry loop timeouts during fuzzing
# --- END AUTOFAB METADATA ---
