# === File: dag_engine_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngine."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_4.parts.dag_engine.lib.dag_engine import (
    CycleError,
    DAGCancelledError,
    DAGRunReport,
    DAGTimeoutError,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeState,
)
from benchmark_4.parts.dag_engine.lib.dag_engine_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__ as _dag_engine_initialize,
)
from benchmark_4.parts.dag_engine.pretense.dag_engine_pretense import (
    DagEngineState,
    DagEngineStateMachine,
    FakeDagEngine,
    failing_action,
    make_dag_engine_fake,
    make_dag_engine_fakes,
    noop_action,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================


class DagEngineImplPseudoStateMachine(DagEngineStateMachine):
    """Implementation pseudo-state machine verifying the concrete DAG engine services."""

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(
            target.add_node(node_id, action, dependencies, priority, timeout_seconds, retries)
        )
        assert sut(DAG).has_node(node_id) is True
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        assert upstream_id in sut(DAG).get_dependencies(downstream_id)
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        assert sut(DAG).has_node(node_id) is False
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        assert isinstance(ret, bool)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        assert isinstance(ret, NodeDefinition)
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        assert isinstance(ret, set)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        assert isinstance(ret, list)
        assert set(ret) == sut(DAG).all_nodes()
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        assert isinstance(ret, set)
        assert ret.issubset(sut(DAG).all_nodes())
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        assert isinstance(ret, set)
        assert ret.issubset(sut(DAG).all_nodes())
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        assert isinstance(ret[0], list)
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        assert isinstance(ret, list)
        assert all(sut(WaveScheduler).get_state(node_id) is NodeState.READY for node_id in ret)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        assert sut(WaveScheduler).get_state(node_id) is NodeState.RUNNING
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        assert sut(WaveScheduler).get_state(node_id) is NodeState.SUCCEEDED
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        assert sut(WaveScheduler).get_state(node_id) is NodeState.FAILED
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        assert isinstance(ret, dict)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.run(timeout_seconds, failure_policy, max_concurrency))
        assert isinstance(ret, DAGRunReport)
        assert ret.total_nodes >= 0
        return ret

    @transition(DAGRunner.cancel)
    def cancel(
        self,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.cancel())
        assert ret is None
        assert sut(DAGRunner).is_cancelled() is True
        return ret

    @transition(DAGRunner.is_cancelled)
    def is_cancelled(
        self,
    ) -> Any:
        target: DAGRunner = sut(DAGRunner)
        ret = call_target(target.is_cancelled())
        assert isinstance(ret, bool)
        return ret


proto = DagEngineImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================


class TestDagEngineImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the modeled contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        _dag_engine_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineImplPseudoStateMachine(
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

    def test_graph_conformance(self) -> None:
        dag = self.checked_dag
        dag.add_node("alpha", noop_action, None, 0, None, 0)
        dag.add_node("beta", noop_action, ["alpha"], 5, 1.0, 1)
        dag.add_node("gamma", noop_action, ["beta"], 1, None, 0)
        dag.add_edge("alpha", "gamma")
        assert dag.has_node("alpha") is True
        assert dag.get_node("alpha").node_id == "alpha"
        assert dag.get_dependencies("beta") == {"alpha"}
        assert dag.get_dependents("beta") == {"gamma"}
        assert dag.all_nodes() == {"alpha", "beta", "gamma"}
        dag.validate()
        assert dag.topological_sort() == ["alpha", "beta", "gamma"]
        assert dag.find_roots() == {"alpha"}
        assert dag.find_leaves() == {"gamma"}
        path, weight = dag.compute_critical_path(None)
        assert path == ["alpha", "beta", "gamma"]
        assert weight == 3.0

    def test_graph_weighted_critical_path(self) -> None:
        dag = self.checked_dag
        dag.add_node("alpha", noop_action, None, 0, None, 0)
        dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        dag.add_node("gamma", noop_action, ["alpha"], 2, None, 0)
        path, weight = dag.compute_critical_path({"alpha": 2.0, "beta": 3.0, "gamma": 1.5})
        assert path == ["alpha", "beta"]
        assert weight == 5.0

    def test_graph_empty_critical_path(self) -> None:
        dag = self.checked_dag
        dag.add_node("alpha", noop_action, None, 0, None, 0)
        dag.remove_node("alpha")
        assert dag.all_nodes() == set()
        path, weight = dag.compute_critical_path(None)
        assert path == []
        assert weight == 0.0

    def test_graph_remove_node_purges_incident_edges(self) -> None:
        dag = self.checked_dag
        dag.add_node("alpha", noop_action, None, 0, None, 0)
        dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        dag.add_node("gamma", noop_action, ["alpha"], 2, None, 0)
        assert dag.get_dependents("alpha") == {"beta", "gamma"}
        dag.remove_node("alpha")
        assert dag.has_node("alpha") is False
        assert dag.all_nodes() == {"beta", "gamma"}
        assert dag.get_dependencies("beta") == set()
        assert dag.get_dependencies("gamma") == set()
        assert dag.find_roots() == {"beta", "gamma"}

    def test_graph_remove_node_with_upstream_dependency(self) -> None:
        dag = self.checked_dag
        dag.add_node("alpha", noop_action, None, 0, None, 0)
        dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        assert dag.get_dependencies("beta") == {"alpha"}
        assert dag.get_dependents("alpha") == {"beta"}
        dag.remove_node("beta")
        assert dag.has_node("beta") is False
        assert dag.all_nodes() == {"alpha"}
        assert dag.get_dependents("alpha") == set()
        assert dag.find_leaves() == {"alpha"}

    def test_scheduler_conformance(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.is_finished() is False
        assert scheduler.next_wave() == ["alpha"]
        scheduler.mark_running("alpha")
        assert scheduler.get_state("alpha") is NodeState.RUNNING
        scheduler.mark_succeeded("alpha")
        assert scheduler.get_state("alpha") is NodeState.SUCCEEDED
        assert scheduler.get_state("beta") is NodeState.READY
        assert scheduler.next_wave() == ["beta"]
        scheduler.mark_failed("beta", FailurePolicy.CONTINUE_ON_ERROR)
        assert scheduler.get_state("beta") is NodeState.FAILED
        assert scheduler.is_finished() is True
        states = scheduler.get_all_states()
        assert states["alpha"] is NodeState.SUCCEEDED
        assert states["beta"] is NodeState.FAILED

    def test_scheduler_wave_priority_and_empty_wave(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 1, None, 0)
        self.checked_dag.add_node("beta", noop_action, None, 5, None, 0)
        self.checked_dag.add_node("gamma", noop_action, None, 3, None, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.is_finished() is False
        assert scheduler.next_wave() == ["beta", "gamma", "alpha"]
        scheduler.mark_running("beta")
        assert scheduler.next_wave() == ["gamma", "alpha"]
        scheduler.mark_succeeded("beta")
        scheduler.mark_running("gamma")
        scheduler.mark_succeeded("gamma")
        scheduler.mark_running("alpha")
        scheduler.mark_succeeded("alpha")
        assert scheduler.next_wave() == []
        assert scheduler.is_finished() is True

    def test_scheduler_promotes_only_pending_dependents(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 2, None, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.is_finished() is False
        scheduler.mark_running("gamma")
        assert scheduler.get_state("gamma") is NodeState.RUNNING
        scheduler.mark_succeeded("alpha")
        assert scheduler.get_state("alpha") is NodeState.SUCCEEDED
        assert scheduler.get_state("beta") is NodeState.READY
        assert scheduler.get_state("gamma") is NodeState.RUNNING
        assert scheduler.next_wave() == ["beta"]

    def test_scheduler_fail_fast_cancels_non_terminal_nodes(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 2, None, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.is_finished() is False
        scheduler.mark_failed("alpha", FailurePolicy.FAIL_FAST)
        assert scheduler.get_state("alpha") is NodeState.FAILED
        assert scheduler.get_state("beta") is NodeState.CANCELLED
        assert scheduler.get_state("gamma") is NodeState.CANCELLED
        assert scheduler.is_finished() is True

    def test_scheduler_skip_downstream_skips_transitive_dependents(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        self.checked_dag.add_node("gamma", noop_action, ["beta"], 2, None, 0)
        self.checked_dag.add_node("delta", noop_action, None, 3, None, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.is_finished() is False
        scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert scheduler.get_state("alpha") is NodeState.FAILED
        assert scheduler.get_state("beta") is NodeState.SKIPPED
        assert scheduler.get_state("gamma") is NodeState.SKIPPED
        assert scheduler.get_state("delta") is NodeState.READY
        assert scheduler.is_finished() is False

    def test_scheduler_skip_downstream_multi_path(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 2, None, 0)
        self.checked_dag.add_node("delta", noop_action, ["beta", "gamma"], 3, None, 0)
        scheduler = self.checked_wavescheduler
        assert scheduler.is_finished() is False
        scheduler.mark_failed("alpha", FailurePolicy.SKIP_DOWNSTREAM)
        assert scheduler.get_state("alpha") is NodeState.FAILED
        assert scheduler.get_state("beta") is NodeState.SKIPPED
        assert scheduler.get_state("gamma") is NodeState.SKIPPED
        assert scheduler.get_state("delta") is NodeState.SKIPPED
        assert scheduler.is_finished() is True

    def test_scheduler_empty_dag_is_finished(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        assert self.checked_wavescheduler.is_finished() is False
        self.checked_dag.remove_node("alpha")
        assert self.checked_wavescheduler.is_finished() is True

    def test_scheduler_cancel_aborts_non_terminal_nodes(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        assert self.checked_wavescheduler.is_finished() is False
        self.checked_dagrunner.cancel()
        assert self.checked_dagrunner.is_cancelled() is True
        states = self.wavescheduler.get_all_states()
        assert states["alpha"] is NodeState.CANCELLED
        assert states["beta"] is NodeState.CANCELLED

    def test_runner_conformance(self) -> None:
        self.checked_dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        runner = self.checked_dagrunner
        assert runner.is_cancelled() is False
        report = runner.run(None, FailurePolicy.FAIL_FAST, 2)
        assert report.total_nodes == 2
        assert set(report.succeeded_nodes) == {"alpha", "beta"}
        assert report.failed_nodes == ()
        assert set(report.results) == {"alpha", "beta"}
        assert self.checked_wavescheduler.is_finished() is True
        runner.cancel()
        assert runner.is_cancelled() is True

    def test_runner_retry_failures(self) -> None:
        self.checked_dag.add_node("alpha", failing_action, None, 0, None, 1)
        report = self.checked_dagrunner.run(None, FailurePolicy.FAIL_FAST, 1)
        assert report.results["alpha"].state is NodeState.FAILED
        assert report.results["alpha"].retries_attempted == 1
        assert set(report.failed_nodes) == {"alpha"}

    def test_runner_continue_on_error_policy(self) -> None:
        self.checked_dag.add_node("alpha", failing_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, None, 1, None, 0)
        self.checked_dag.add_node("gamma", noop_action, ["alpha"], 2, None, 0)
        report = self.checked_dagrunner.run(5.0, FailurePolicy.CONTINUE_ON_ERROR, 1)
        assert set(report.failed_nodes) == {"alpha"}
        assert "beta" in report.succeeded_nodes
        assert "gamma" not in report.succeeded_nodes

    def test_runner_skip_downstream_report(self) -> None:
        self.checked_dag.add_node("alpha", failing_action, None, 0, None, 0)
        self.checked_dag.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        report = self.checked_dagrunner.run(None, FailurePolicy.SKIP_DOWNSTREAM, 1)
        assert report.results["alpha"].state is NodeState.FAILED
        assert report.results["beta"].state is NodeState.SKIPPED
        assert "beta" in report.skipped_nodes

    def test_add_edge_absent_node_error(self) -> None:
        self.dag.add_node("alpha", noop_action, None, 0, None, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("ghost", "alpha")

    def test_validate_missing_dependency_error(self) -> None:
        self.dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.dag.add_node("beta", noop_action, ["ghost"], 0, None, 0)
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_validate_cycle_error(self) -> None:
        self.dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.dag.add_node("beta", noop_action, ["alpha"], 0, None, 0)
        self.dag.add_edge("beta", "alpha")
        with self.assertRaises(CycleError):
            self.dag.validate()

    def test_topological_sort_cycle_error(self) -> None:
        self.dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.dag.add_node("beta", noop_action, ["alpha"], 0, None, 0)
        self.dag.add_edge("beta", "alpha")
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_runner_timeout_error(self) -> None:
        self.dag.add_node("alpha", noop_action, None, 0, None, 0)
        with self.assertRaises(DAGTimeoutError):
            self.dagrunner.run(-1.0, FailurePolicy.FAIL_FAST, 1)

    def test_runner_cancelled_error(self) -> None:
        self.dag.add_node("alpha", noop_action, None, 0, None, 0)
        self.dagrunner.cancel()
        self.wavescheduler.mark_running("alpha")
        with self.assertRaises(DAGCancelledError):
            self.dagrunner.run(None, FailurePolicy.FAIL_FAST, 1)


# ==============================================================================
# 3. Real Hypothesis Fuzzing
# ==============================================================================


class DagEngineSUT:
    """Aggregate SUT exposing the DAG engine component services for fuzzing."""

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        _dag_engine_initialize(self.registry)
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


def make_sut() -> DagEngineSUT:
    return DagEngineSUT()


DagEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=DagEngineState,
    name="DagEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:12:58Z
# LAST_CHANGED: 2026-11-08T17:12:32Z
# CHANGE: Resolve remaining pret_cov starvation: add a scenario removing a node that has an upstream dependency (purges the node from its upstream neighbor's dependent set and leaves the upstream node as root/leaf), and a skip-downstream scenario over a diamond graph where the transitive dependent delta is reached through both the alpha-beta-delta and alpha-gamma-delta paths and must be skipped exactly once with all nodes terminal.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:12:58Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:12:46Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Set, Tuple
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

from benchmark_4.parts.dag_engine.lib.dag_engine import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    NodeState,
    WaveScheduler,
)

_TERMINAL_STATES = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.SKIPPED,
        NodeState.CANCELLED,
    }
)


def noop_action() -> Any:
    """Deterministic zero-argument action used by seeding, fake, and real scenarios."""
    return None


def failing_action() -> Any:
    """Deterministic zero-argument action used by node failure scenarios.

    Executing this action raises, allowing failure policies and retry accounting
    to be exercised deterministically.
    """
    raise RuntimeError("canonical failing action")


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================


@dataclass
class DagEngineState:
    """Canonical model state mirroring the DAG graph and wave scheduling state."""

    nodes: Set[str] = field(default_factory=set)
    definitions: Dict[str, NodeDefinition[Any]] = field(default_factory=dict)
    dependencies: Dict[str, Set[str]] = field(default_factory=dict)
    dependents: Dict[str, Set[str]] = field(default_factory=dict)
    priorities: Dict[str, int] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)
    cancelled: bool = False

    def _ordered(self, node_ids: Collection[str]) -> List[str]:
        """Orders node identifiers by priority descending, then identifier ascending."""
        return sorted(node_ids, key=lambda node_id: (-self.priorities.get(node_id, 0), node_id))

    def graph_complete(self) -> bool:
        """Whether every referenced dependency is itself registered in the graph."""
        return all(
            dependency in self.nodes
            for node_dependencies in self.dependencies.values()
            for dependency in node_dependencies
        )

    def topological_order(self) -> Optional[List[str]]:
        """Deterministic topological ordering, or None when the graph contains a cycle."""
        indegree: Dict[str, int] = {node_id: 0 for node_id in self.nodes}
        for node_id in self.nodes:
            indegree[node_id] = len(
                [dep for dep in self.dependencies.get(node_id, set()) if dep in self.nodes]
            )
        ready = self._ordered([node_id for node_id, degree in indegree.items() if degree == 0])
        ordered: List[str] = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for dependent in self._ordered(self.dependents.get(node_id, set())):
                if dependent not in indegree:
                    continue
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
            ready = self._ordered(ready)
        if len(ordered) != len(self.nodes):
            return None
        return ordered

    def graph_acyclic(self) -> bool:
        """Whether the graph admits a complete topological ordering."""
        return self.topological_order() is not None

    def find_root_ids(self) -> Set[str]:
        """Nodes with no upstream dependencies."""
        return {node_id for node_id in self.nodes if not self.dependencies.get(node_id)}

    def find_leaf_ids(self) -> Set[str]:
        """Nodes with no downstream dependents."""
        return {node_id for node_id in self.nodes if not self.dependents.get(node_id)}

    def critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Longest weighted dependency path and its cumulative weight."""
        order = self.topological_order()
        if not order:
            return ([], 0.0)
        weights: Dict[str, float] = {
            node_id: (
                float(estimated_durations.get(node_id, 1.0))
                if estimated_durations is not None
                else 1.0
            )
            for node_id in order
        }
        earliest: Dict[str, float] = {node_id: weights[node_id] for node_id in order}
        predecessor: Dict[str, Optional[str]] = {node_id: None for node_id in order}
        for node_id in order:
            for dependent in self._ordered(self.dependents.get(node_id, set())):
                if dependent not in earliest:
                    continue
                candidate = earliest[node_id] + weights[dependent]
                if candidate > earliest[dependent]:
                    earliest[dependent] = candidate
                    predecessor[dependent] = node_id
        best = order[0]
        for node_id in order:
            if earliest[node_id] > earliest[best]:
                best = node_id
        path: List[str] = []
        current: Optional[str] = best
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()
        return (path, earliest[best])

    def descendants(self, node_id: str) -> Set[str]:
        """All transitive downstream dependents of a node."""
        seen: Set[str] = set()
        frontier: List[str] = [node_id]
        while frontier:
            current = frontier.pop()
            for dependent in self.dependents.get(current, set()):
                if dependent not in seen:
                    seen.add(dependent)
                    frontier.append(dependent)
        return seen

    def ready_wave(self) -> List[str]:
        """Nodes in READY state whose upstream dependencies have all SUCCEEDED."""
        ready = [
            node_id
            for node_id in self.nodes
            if self.node_states.get(node_id) is NodeState.READY
            and all(
                self.node_states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.dependencies.get(node_id, set())
            )
        ]
        return self._ordered(ready)

    def all_terminal(self) -> bool:
        """Whether every registered node has reached a terminal lifecycle state."""
        return all(self.node_states.get(node_id) in _TERMINAL_STATES for node_id in self.nodes)

    def run_report(self) -> DAGRunReport:
        """Aggregated report mirroring the scheduler's observed node outcomes."""
        results: Dict[str, NodeResult[Any]] = {
            node_id: NodeResult(
                node_id=node_id,
                state=self.node_states.get(node_id, NodeState.PENDING),
            )
            for node_id in self._ordered(self.nodes)
        }
        succeeded = tuple(
            node_id
            for node_id in self._ordered(self.nodes)
            if self.node_states.get(node_id) is NodeState.SUCCEEDED
        )
        failed = tuple(
            node_id
            for node_id in self._ordered(self.nodes)
            if self.node_states.get(node_id) is NodeState.FAILED
        )
        skipped = tuple(
            node_id
            for node_id in self._ordered(self.nodes)
            if self.node_states.get(node_id) is NodeState.SKIPPED
        )
        cancelled = tuple(
            node_id
            for node_id in self._ordered(self.nodes)
            if self.node_states.get(node_id) is NodeState.CANCELLED
        )
        path, weight = self.critical_path(None)
        return DAGRunReport(
            total_nodes=len(self.nodes),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=weight,
            critical_path=tuple(path),
            results=results,
        )


class DagEngineStateMachine(StateMachine[DagEngineState]):
    """Unified Pretense state machine modeling the DAG engine services 1:1."""

    def __init__(
        self,
        state: Optional[DagEngineState] = None,
        singletons: Optional[Dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagEngineState(), singletons=singletons)

    @transition(DAG.add_node)
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        require_arg(node_id, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(action, Domain.any(), preferred=[noop_action])
        require_arg(
            dependencies,
            Domain.type(Optional[Collection[str]]),
            preferred=[None],
        )
        require_arg(priority, Domain.range(-10, 10), preferred=[0])
        require_arg(timeout_seconds, Domain.sampled_from([None, 1.0, 5.0, 30.0]), preferred=[None])
        require_arg(retries, Domain.range(0, 3), preferred=[0])
        resolved = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=resolved,
            priority=priority,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        self.state.nodes.add(node_id)
        self.state.definitions[node_id] = definition
        self.state.dependencies.setdefault(node_id, set()).update(resolved)
        self.state.priorities[node_id] = priority
        self.state.dependents.setdefault(node_id, set())
        for upstream_id in resolved:
            self.state.dependents.setdefault(upstream_id, set()).add(node_id)
        if node_id not in self.state.node_states:
            self.state.node_states[node_id] = (
                NodeState.PENDING if resolved else NodeState.READY
            )
        ret = make_return_value(None)
        assert ret is None
        assert self.state.definitions[node_id].node_id == node_id

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require_arg(upstream_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        require_arg(downstream_id, Domain.in_set(self.state.nodes), preferred=["beta"])
        self.state.dependencies.setdefault(downstream_id, set()).add(upstream_id)
        self.state.dependents.setdefault(upstream_id, set()).add(downstream_id)
        ret = make_return_value(None)
        assert ret is None
        assert upstream_id in self.state.dependencies[downstream_id]

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        for upstream_id in self.state.dependencies.get(node_id, set()):
            self.state.dependents.get(upstream_id, set()).discard(node_id)
        for downstream_id in self.state.dependents.get(node_id, set()):
            self.state.dependencies.get(downstream_id, set()).discard(node_id)
        self.state.nodes.discard(node_id)
        self.state.definitions.pop(node_id, None)
        self.state.dependencies.pop(node_id, None)
        self.state.dependents.pop(node_id, None)
        self.state.priorities.pop(node_id, None)
        self.state.node_states.pop(node_id, None)
        ret = make_return_value(None)
        assert ret is None
        assert node_id not in self.state.nodes

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require_arg(node_id, Domain.type(str), preferred=["alpha", "beta"])
        ret: bool = make_return_value(node_id in self.state.nodes)
        assert isinstance(ret, bool)
        assert ret == (node_id in self.state.nodes)
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        ret: NodeDefinition[Any] = make_return_value(self.state.definitions[node_id])
        assert isinstance(ret, NodeDefinition)
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        ret: Set[str] = make_return_value(set(self.state.dependencies.get(node_id, set())))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        ret: Set[str] = make_return_value(set(self.state.dependents.get(node_id, set())))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        ret: Set[str] = make_return_value(set(self.state.nodes))
        assert isinstance(ret, set)
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.graph_complete())
        require(self.state.graph_acyclic())
        ret = make_return_value(None)
        assert ret is None

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.graph_complete())
        require(self.state.graph_acyclic())
        ordered = self.state.topological_order()
        ret: List[str] = make_return_value(list(ordered) if ordered is not None else [])
        assert isinstance(ret, list)
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        ret: Set[str] = make_return_value(self.state.find_root_ids())
        assert isinstance(ret, set)
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        ret: Set[str] = make_return_value(self.state.find_leaf_ids())
        assert isinstance(ret, set)
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.graph_complete())
        require(self.state.graph_acyclic())
        require_arg(
            estimated_durations,
            Domain.type(Optional[Mapping[str, float]]),
            preferred=[None],
        )
        path, weight = self.state.critical_path(estimated_durations)
        ret: Tuple[List[str], float] = make_return_value((path, weight))
        assert isinstance(ret, tuple)
        assert len(ret) == 2
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        ret: List[str] = make_return_value(self.state.ready_wave())
        assert isinstance(ret, list)
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        self.state.node_states[node_id] = NodeState.RUNNING
        ret = make_return_value(None)
        assert ret is None
        assert self.state.node_states[node_id] is NodeState.RUNNING

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        self.state.node_states[node_id] = NodeState.SUCCEEDED
        for dependent in self.state.dependents.get(node_id, set()):
            if self.state.node_states.get(dependent) is NodeState.PENDING and all(
                self.state.node_states.get(dependency) is NodeState.SUCCEEDED
                for dependency in self.state.dependencies.get(dependent, set())
            ):
                self.state.node_states[dependent] = NodeState.READY
        ret = make_return_value(None)
        assert ret is None
        assert self.state.node_states[node_id] is NodeState.SUCCEEDED

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        require_arg(
            failure_policy,
            Domain.sampled_from(list(FailurePolicy)),
            preferred=[FailurePolicy.FAIL_FAST],
        )
        self.state.node_states[node_id] = NodeState.FAILED
        if failure_policy is FailurePolicy.FAIL_FAST:
            for other_id in self.state._ordered(self.state.nodes):
                if self.state.node_states.get(other_id) not in _TERMINAL_STATES:
                    self.state.node_states[other_id] = NodeState.CANCELLED
        elif failure_policy is FailurePolicy.SKIP_DOWNSTREAM:
            for dependent in self.state._ordered(self.state.descendants(node_id)):
                if self.state.node_states.get(dependent) not in _TERMINAL_STATES:
                    self.state.node_states[dependent] = NodeState.SKIPPED
        ret = make_return_value(None)
        assert ret is None
        assert self.state.node_states[node_id] is NodeState.FAILED

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        ret: bool = make_return_value(self.state.all_terminal())
        assert isinstance(ret, bool)
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require_arg(node_id, Domain.in_set(self.state.nodes), preferred=["alpha"])
        ret: NodeState = make_return_value(
            self.state.node_states.get(node_id, NodeState.PENDING)
        )
        assert isinstance(ret, NodeState)
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        ret: Mapping[str, NodeState] = make_return_value(dict(self.state.node_states))
        assert isinstance(ret, dict)
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        require(self.state.graph_complete())
        require(self.state.graph_acyclic())
        require(not self.state.cancelled)
        require_arg(timeout_seconds, Domain.sampled_from([None, 1.0, 5.0, 30.0]), preferred=[None])
        require_arg(
            failure_policy,
            Domain.sampled_from(list(FailurePolicy)),
            preferred=[FailurePolicy.CONTINUE_ON_ERROR],
        )
        require_arg(max_concurrency, Domain.range(1, 4), preferred=[1])
        ret: DAGRunReport = make_return_value(self.state.run_report())
        assert isinstance(ret, DAGRunReport)
        assert ret.total_nodes >= 0
        return ret

    @transition(DAGRunner.cancel)
    def cancel(
        self,
    ) -> None:
        self.state.cancelled = True
        ret = make_return_value(None)
        assert ret is None
        assert self.state.cancelled

    @transition(DAGRunner.is_cancelled)
    def is_cancelled(
        self,
    ) -> bool:
        ret: bool = make_return_value(self.state.cancelled)
        assert isinstance(ret, bool)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the blank model into an explicit, non-cancelled initial state."""
        self.state.cancelled = False


proto = DagEngineStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngine = synthesize_fake(DagEngineStateMachine)


def make_dag_engine_fake(state: Optional[DagEngineState] = None) -> Any:
    """Creates the synthesized fake implementing every DAG engine service."""
    return FakeDagEngine(state=state or DagEngineState())


def make_dag_engine_fakes(
    state: Optional[DagEngineState] = None,
) -> Tuple[Any, Any, Any]:
    """Creates fake DAG, WaveScheduler, and DAGRunner sharing one model state."""
    fake = make_dag_engine_fake(state)
    return (fake, fake, fake)


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================


class TestDagEngineFake(unittest.TestCase):
    """Exercises every transition and seeding transition on the synthesized fake."""

    def setUp(self) -> None:
        self.fake: Any = make_dag_engine_fake()

    def test_seeding_transition(self) -> None:
        sm = DagEngineStateMachine()
        sm.seed_initial()
        fake = self.fake
        fake.add_node("seed", noop_action, None, 0, None, 0)
        assert fake.all_nodes() == {"seed"}
        assert fake.is_cancelled() is False

    def test_graph_transitions(self) -> None:
        fake = self.fake
        fake.add_node("alpha", noop_action, None, 0, None, 0)
        fake.add_node("beta", noop_action, ["alpha"], 5, 1.0, 1)
        fake.add_edge("alpha", "beta")
        assert fake.has_node("alpha") is True
        assert fake.get_node("alpha").node_id == "alpha"
        assert fake.get_dependencies("beta") == {"alpha"}
        assert fake.get_dependents("alpha") == {"beta"}
        assert fake.all_nodes() == {"alpha", "beta"}
        assert fake.find_roots() == {"alpha"}
        assert fake.find_leaves() == {"beta"}
        fake.validate()
        assert fake.topological_sort() == ["alpha", "beta"]
        path, weight = fake.compute_critical_path({"alpha": 2.0, "beta": 3.0})
        assert path == ["alpha", "beta"]
        assert weight == 5.0
        fake.remove_node("beta")
        assert fake.has_node("beta") is False
        assert fake.all_nodes() == {"alpha"}

    def test_scheduler_transitions(self) -> None:
        fake = self.fake
        fake.add_node("alpha", noop_action, None, 0, None, 0)
        fake.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        assert fake.get_all_states() == {
            "alpha": NodeState.READY,
            "beta": NodeState.PENDING,
        }
        assert fake.next_wave() == ["alpha"]
        fake.mark_running("alpha")
        assert fake.get_state("alpha") is NodeState.RUNNING
        fake.mark_succeeded("alpha")
        assert fake.get_state("alpha") is NodeState.SUCCEEDED
        assert fake.get_state("beta") is NodeState.READY
        assert fake.is_finished() is False
        fake.mark_failed("beta", FailurePolicy.FAIL_FAST)
        assert fake.get_state("beta") is NodeState.FAILED
        assert fake.is_finished() is True

    def test_runner_transitions(self) -> None:
        fake = self.fake
        fake.add_node("alpha", noop_action, None, 0, None, 0)
        fake.add_node("beta", noop_action, ["alpha"], 1, None, 0)
        assert fake.is_cancelled() is False
        report = fake.run(None, FailurePolicy.CONTINUE_ON_ERROR, 2)
        assert report.total_nodes == 2
        assert set(report.results) == {"alpha", "beta"}
        fake.cancel()
        assert fake.is_cancelled() is True


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

FakeDagEngineFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineState,
    name="FakeDagEngineFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:09:37Z
# LAST_CHANGED: 2026-11-08T17:09:37Z
# CHANGE: Add the model's canonical failing_action fixture (deterministic zero-argument action that raises) alongside noop_action so implementation scenario suites can exercise node failure, retry, and failure-policy contracts without module-private action fixtures.
# --- END AUTOFAB METADATA ---
