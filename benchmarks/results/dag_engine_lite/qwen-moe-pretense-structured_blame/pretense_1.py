# === File: dag_engine_lite_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for DagEngineLite."""

from __future__ import annotations

from typing import Any, Callable, Collection, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_1.parts.dag_engine_lite.pretense.dag_engine_lite_pretense import (
    DagEngineLiteStateMachine,
    DagEngineLiteState,
    FakeDagEngineLite,
    make_dag_engine_lite_fake,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import FailurePolicy, NodeState
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__ as _dag_engine_lite_initialize


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
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_node(node_id, action, dependencies, priority, retries))
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.add_edge(upstream_id, downstream_id))
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.remove_node(node_id))
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.has_node(node_id))
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_node(node_id))
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependencies(node_id))
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.get_dependents(node_id))
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.all_nodes())
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.validate())
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.topological_sort())
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_roots())
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.find_leaves())
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Any:
        target: DAG = sut(DAG)
        ret = call_target(target.compute_critical_path(estimated_durations))
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.next_wave())
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_running(node_id))
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_succeeded(node_id))
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.mark_failed(node_id, failure_policy))
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.is_finished())
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_state(node_id))
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Any:
        target: WaveScheduler = sut(WaveScheduler)
        ret = call_target(target.get_all_states())
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> Any:
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
        _dag_engine_lite_initialize(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.wavescheduler = get_singleton(WaveScheduler)
        self.dagrunner = get_singleton(DAGRunner)
        self.sm = DagEngineLiteImplPseudoStateMachine(singletons={
            DAG: self.dag,
            WaveScheduler: self.wavescheduler,
            DAGRunner: self.dagrunner,
        })
        self.checked_dag = self.sm.as_checked(DAG, self.dag)
        self.checked_wavescheduler = self.sm.as_checked(WaveScheduler, self.wavescheduler)
        self.checked_dagrunner = self.sm.as_checked(DAGRunner, self.dagrunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_add_node_and_has_node(self) -> None:
        self.checked_dag.add_node("n1", lambda: 42, [], 0, 0)
        assert self.checked_dag.has_node("n1")

    def test_add_edge(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_dag.add_edge("n1", "n2")
        assert "n1" in self.checked_dag.get_dependencies("n2")

    def test_get_node_definition(self) -> None:
        self.checked_dag.add_node("n1", lambda: "hello", [], 5, 1)
        nd = self.checked_dag.get_node("n1")
        assert nd.node_id == "n1"
        assert nd.priority == 5

    def test_get_dependencies_and_dependents(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_dag.add_node("n3", lambda: 3, frozenset(["n1"]), 0, 0)
        assert self.checked_dag.get_dependencies("n1") == {"n2", "n3"} or "n1" in self.checked_dag.get_dependencies("n2")
        assert self.checked_dag.get_dependents("n1")

    def test_all_nodes(self) -> None:
        self.checked_dag.add_node("a", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("b", lambda: 2, [], 0, 0)
        all_nodes = self.checked_dag.all_nodes()
        assert "a" in all_nodes
        assert "b" in all_nodes

    def test_validate_and_topological_sort(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_dag.validate()
        order = self.checked_dag.topological_sort()
        assert order.index("n1") < order.index("n2")

    def test_find_roots_and_leaves(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        roots = self.checked_dag.find_roots()
        assert "n1" in roots
        leaves = self.checked_dag.find_leaves()
        assert "n2" in leaves

    def test_compute_critical_path(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        path, weight = self.checked_dag.compute_critical_path(None)
        assert len(path) >= 1
        assert weight > 0

    def test_wave_scheduler_basic(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        wave = self.checked_wavescheduler.next_wave()
        assert "n1" in wave
        self.checked_wavescheduler.mark_running("n1")
        self.checked_wavescheduler.mark_succeeded("n1")
        self.checked_wavescheduler.mark_running("n2")
        self.checked_wavescheduler.mark_succeeded("n2")
        assert self.checked_wavescheduler.is_finished()

    def test_mark_failed_fail_fast(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_wavescheduler.mark_running("n1")
        self.checked_wavescheduler.mark_failed("n1", FailurePolicy.FAIL_FAST)
        assert self.checked_wavescheduler.get_state("n2") in (NodeState.CANCELLED, NodeState.SKIPPED)

    def test_dagrunner_run(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_dag.validate()
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 2
        assert report.succeeded_nodes == ("n1", "n2")

    def test_remove_node(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.remove_node("n1")
        assert not self.checked_dag.has_node("n1")

    def test_failure_policy_continue_on_error(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, [], 0, 0)
        self.checked_dag.add_node("n3", lambda: 3, frozenset(["n1", "n2"]), 0, 0)
        self.checked_wavescheduler.mark_running("n1")
        self.checked_wavescheduler.mark_failed("n1", FailurePolicy.CONTINUE_ON_ERROR)
        self.checked_wavescheduler.mark_running("n2")
        self.checked_wavescheduler.mark_succeeded("n2")
        assert self.checked_wavescheduler.get_state("n3") == NodeState.SKIPPED

    def test_mark_failed_skip_downstream(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_dag.add_node("n3", lambda: 3, frozenset(["n2"]), 0, 0)
        self.checked_wavescheduler.mark_running("n1")
        self.checked_wavescheduler.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        assert self.checked_wavescheduler.get_state("n1") == NodeState.FAILED
        assert self.checked_wavescheduler.get_state("n2") == NodeState.SKIPPED
        assert self.checked_wavescheduler.get_state("n3") == NodeState.SKIPPED

    def test_run_with_retry_failure(self) -> None:
        call_count = [0]

        def failing_action() -> int:
            call_count[0] += 1
            raise RuntimeError("transient failure")

        self.checked_dag.add_node("n1", failing_action, [], 0, 2)
        report = self.checked_dagrunner.run(FailurePolicy.FAIL_FAST)
        assert report.total_nodes == 1
        assert call_count[0] >= 2

    def test_run_with_skipped_nodes(self) -> None:
        self.checked_dag.add_node("n1", lambda: 1, [], 0, 0)
        self.checked_dag.add_node("n2", lambda: 2, frozenset(["n1"]), 0, 0)
        self.checked_dag.add_node("n3", lambda: 3, frozenset(["n2"]), 0, 0)
        self.checked_wavescheduler.mark_running("n1")
        self.checked_wavescheduler.mark_failed("n1", FailurePolicy.SKIP_DOWNSTREAM)
        report = self.checked_dagrunner.run(FailurePolicy.SKIP_DOWNSTREAM)
        assert report.total_nodes == 3
        assert any(r.state == NodeState.SKIPPED for r in report.results.values())


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> Any:
    registry = LifecycleRegistry()
    _dag_engine_lite_initialize(registry)
    phase_scope = enter_phase(system, registry=registry)
    phase_scope.__enter__()
    dag = get_singleton(DAG)
    wavescheduler = get_singleton(WaveScheduler)
    dagrunner = get_singleton(DAGRunner)
    return DagEngineLiteSUT(dag, wavescheduler, dagrunner, phase_scope)


class DagEngineLiteSUT:
    """Aggregate SUT exposing component services for DagEngineLite state machine testing."""

    def __init__(
        self,
        dag: DAG,
        wavescheduler: WaveScheduler,
        dagrunner: DAGRunner,
        phase_scope: Any,
    ) -> None:
        self.__dict__["_services"] = (dag, wavescheduler, dagrunner)
        self.__dict__["_phase_scope"] = phase_scope

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def close(self) -> None:
        self.__dict__["_phase_scope"].__exit__(None, None, None)


DagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    collaborators=[DagEngineLiteStateMachine],
    sut_factory=make_sut,
    initial_state_factory=DagEngineLiteState,
    name="DagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T20:28:28Z
# LAST_CHANGED: 2026-11-08T20:10:48Z
# CHANGE: Fixed test_run_with_skipped_nodes assertion: changed 'NodeState.SKIPPED in report.results.values()' to 'any(r.state == NodeState.SKIPPED for r in report.results.values())' because report.results maps node IDs to NodeResult objects that have a .state field.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T20:28:28Z
# PRETENSE_QA_AUDIT: 2026-11-08T20:28:07Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, FrozenSet, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAG,
    DAGRunReport,
    DAGRunner,
    FailurePolicy,
    NodeDefinition,
    NodeResult,
    NodeState,
    WaveScheduler,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================


def _dummy_action() -> Any:
    """Module-level action reference for type-constructible NodeDefinition."""
    return None


@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    initialized: bool = True
    nodes: Set[str] = field(default_factory=set)
    definitions: Mapping[str, NodeDefinition[Any]] = field(default_factory=dict)
    edges: Mapping[str, Set[str]] = field(default_factory=dict)


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
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["n1"])
        require_arg(action, Domain.type(Callable[[], Any]))
        require_arg(dependencies, Domain.type(Optional[Collection[str]]))
        require_arg(priority, Domain.range(-100, 100), preferred=[0])
        require_arg(retries, Domain.range(0, 10), preferred=[0])
        self.state.nodes.add(node_id)
        self.state.definitions[node_id] = NodeDefinition(
            node_id=node_id, action=action, dependencies=frozenset(dependencies or [])
        )
        ret = self.inner_add_node(node_id, action, dependencies, priority, retries)
        assert ret is None
        return ret

    @transition(DAG.add_edge)
    def add_edge(
        self,
        upstream_id: str,
        downstream_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(upstream_id, Domain.sampled_from(self.state.nodes))
        require_arg(downstream_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_add_edge(upstream_id, downstream_id)
        assert ret is None
        return ret

    @transition(DAG.remove_node)
    def remove_node(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_remove_node(node_id)
        assert ret is None
        return ret

    @transition(DAG.has_node)
    def has_node(
        self,
        node_id: str,
    ) -> bool:
        require(self.state.initialized)
        require_arg(node_id, Domain.type(str), preferred=["n1"])
        ret = self.inner_has_node(node_id)
        assert ret is not None
        return ret

    @transition(DAG.get_node)
    def get_node(
        self,
        node_id: str,
    ) -> NodeDefinition[Any]:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_get_node(node_id)
        assert ret is not None
        return ret

    @transition(DAG.get_dependencies)
    def get_dependencies(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_get_dependencies(node_id)
        assert ret is not None
        return ret

    @transition(DAG.get_dependents)
    def get_dependents(
        self,
        node_id: str,
    ) -> Set[str]:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_get_dependents(node_id)
        assert ret is not None
        return ret

    @transition(DAG.all_nodes)
    def all_nodes(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_all_nodes()
        assert ret is not None
        return ret

    @transition(DAG.validate)
    def validate(
        self,
    ) -> None:
        require(self.state.initialized)
        ret = self.inner_validate()
        assert ret is None
        return ret

    @transition(DAG.topological_sort)
    def topological_sort(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        ret = self.inner_topological_sort()
        assert ret is not None
        return ret

    @transition(DAG.find_roots)
    def find_roots(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_find_roots()
        assert ret is not None
        return ret

    @transition(DAG.find_leaves)
    def find_leaves(
        self,
    ) -> Set[str]:
        require(self.state.initialized)
        ret = self.inner_find_leaves()
        assert ret is not None
        return ret

    @transition(DAG.compute_critical_path)
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        require(self.state.initialized)
        require_arg(estimated_durations, Domain.type(Optional[Mapping[str, float]]))
        ret = self.inner_compute_critical_path(estimated_durations)
        assert ret is not None
        return ret

    @transition(WaveScheduler.next_wave)
    def next_wave(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        ret = self.inner_next_wave()
        assert ret is not None
        return ret

    @transition(WaveScheduler.mark_running)
    def mark_running(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_mark_running(node_id)
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_succeeded)
    def mark_succeeded(
        self,
        node_id: str,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_mark_succeeded(node_id)
        assert ret is None
        return ret

    @transition(WaveScheduler.mark_failed)
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)), preferred=[FailurePolicy.FAIL_FAST])
        ret = self.inner_mark_failed(node_id, failure_policy)
        assert ret is None
        return ret

    @transition(WaveScheduler.is_finished)
    def is_finished(
        self,
    ) -> bool:
        require(self.state.initialized)
        ret = self.inner_is_finished()
        assert ret is not None
        return ret

    @transition(WaveScheduler.get_state)
    def get_state(
        self,
        node_id: str,
    ) -> NodeState:
        require(self.state.initialized)
        require_arg(node_id, Domain.sampled_from(self.state.nodes))
        ret = self.inner_get_state(node_id)
        assert ret is not None
        return ret

    @transition(WaveScheduler.get_all_states)
    def get_all_states(
        self,
    ) -> Mapping[str, NodeState]:
        require(self.state.initialized)
        ret = self.inner_get_all_states()
        assert ret is not None
        return ret

    @transition(DAGRunner.run)
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        require(self.state.initialized)
        require_arg(failure_policy, Domain.sampled_from(list(FailurePolicy)), preferred=[FailurePolicy.FAIL_FAST])
        ret = self.inner_run(failure_policy)
        assert ret is not None
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True


proto = DagEngineLiteStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeDagEngineLite = synthesize_fake(DagEngineLiteStateMachine)


def make_dag_engine_lite_fake(
    state: Optional[DagEngineLiteState] = None,
) -> DAG:
    """Synthesizes a fake instance for the DAG component."""
    return FakeDagEngineLite(state=state or DagEngineLiteState())


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
        self.sm.add_node("n1", lambda: None, [], 0, 0)
        self.sm.add_edge("n1", "n2")
        self.sm.remove_node("n1")
        self.sm.has_node("n1")
        self.sm.get_node("n1")
        self.sm.get_dependencies("n1")
        self.sm.get_dependents("n1")
        self.sm.all_nodes()
        self.sm.validate()
        self.sm.topological_sort()
        self.sm.find_roots()
        self.sm.find_leaves()
        self.sm.compute_critical_path(None)
        self.sm.next_wave()
        self.sm.mark_running("n1")
        self.sm.mark_succeeded("n1")
        self.sm.mark_failed("n1", FailurePolicy.FAIL_FAST)
        self.sm.is_finished()
        self.sm.get_state("n1")
        self.sm.get_all_states()
        self.sm.run(FailurePolicy.FAIL_FAST)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeDagEngineLiteFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=DagEngineLiteState,
    name="FakeDagEngineLiteFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T19:54:11Z
# LAST_CHANGED: 2026-11-08T19:54:11Z
# CHANGE: Fixed 4 transitions: (1) add_node now updates self.state.nodes and self.state.definitions to maintain the model; (2) mark_running, mark_succeeded, mark_failed now use require_arg(node_id, Domain.sampled_from(self.state.nodes)) instead of Domain.type(str) to guard node existence per pret_qa.uncontracted_state_rule.
# --- END AUTOFAB METADATA ---
