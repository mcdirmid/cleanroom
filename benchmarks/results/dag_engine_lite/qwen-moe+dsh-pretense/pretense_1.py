"""Pretense module for DAG engine lite: models DAG, WaveScheduler, and DAGRunner state
transitions, synthesizes fakes, verifies concrete implementations with full coverage,
and executes bounded property fuzzing against low/dag_engine_lite.pyi contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, List, Mapping, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system

from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import (
    DAG,
    DAGRunner,
    WaveScheduler,
    __initialize__,
)
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    CycleError,
    DAGError,
    DAGRunReport,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
)

# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class TargetState:
    """Canonical model state tracking DAG nodes, edges, and scheduler lifecycle."""
    # DAG state
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    upstream: dict[str, Set[str]] = field(default_factory=lambda: {})
    downstream: dict[str, Set[str]] = field(default_factory=lambda: {})
    # Scheduler state
    scheduler_states: dict[str, str] = field(default_factory=dict)
    # Runner state
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Execution flags
    run_started: bool = False
    run_finished: bool = False


proto = StateMachineProto[TargetState]()


def _is_not_bound(v: Any) -> bool:
    return v is NotBound


def _val_or(v: Any) -> Any:
    if not _is_not_bound(v):
        return v
    return None


def _as_outcome(o: Any) -> Any:
    if o is NotBound:
        return Value(None)
    return o if isinstance(o, (Value, Raised)) else Value(o)


# --- DAG Transitions ---

@proto.transition(DAG.add_node)
def add_node():
    pass


@add_node.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
    action: Any = NotBound,
    dependencies: Any = NotBound,
    priority: Any = NotBound,
    retries: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    deps = set(dependencies) if not _is_not_bound(dependencies) and dependencies is not None else set()
    return (
        _val_or(node_id) or "node_0",
        _val_or(action) or (lambda: None),
        deps,
        _val_or(priority) if not _is_not_bound(priority) else 0,
        _val_or(retries) if not _is_not_bound(retries) else 0,
    )


@add_node.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    return _as_outcome(outcome)


@add_node.provide
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    result: Any,
) -> None:
    state.nodes[node_id] = {
        "node_id": node_id,
        "action": action,
        "dependencies": frozenset(dependencies),
        "priority": priority,
        "retries": retries,
    }
    if node_id not in state.upstream:
        state.upstream[node_id] = set()
    if node_id not in state.downstream:
        state.downstream[node_id] = set()
    for dep in dependencies:
        if dep not in state.upstream:
            state.upstream[dep] = set()
        if dep not in state.downstream:
            state.downstream[dep] = set()
        state.upstream[node_id].add(dep)
        state.downstream[dep].add(node_id)
    # Initialize scheduler state: READY for root nodes, PENDING for dependents
    if node_id not in state.scheduler_states:
        if not dependencies:
            state.scheduler_states[node_id] = NodeState.READY.value
        else:
            state.scheduler_states[node_id] = NodeState.PENDING.value


@proto.transition(DAG.add_edge)
def add_edge():
    pass


@add_edge.arguments
def _(
    state: TargetState,
    this: Any,
    upstream_id: Any = NotBound,
    downstream_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(upstream_id) or "node_a", _val_or(downstream_id) or "node_b")


@add_edge.returns
def _(
    state: TargetState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        if upstream_id not in state.nodes:
            return Raised(NodeNotFoundError(message=f"Node {upstream_id} not found", node_id=upstream_id))
        if downstream_id not in state.nodes:
            return Raised(NodeNotFoundError(message=f"Node {downstream_id} not found", node_id=downstream_id))
        return Value(None)
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@add_edge.provide
def _(
    state: TargetState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any,
) -> None:
    if upstream_id not in state.upstream:
        state.upstream[upstream_id] = set()
    if upstream_id not in state.downstream:
        state.downstream[upstream_id] = set()
    if downstream_id not in state.upstream:
        state.upstream[downstream_id] = set()
    if downstream_id not in state.downstream:
        state.downstream[downstream_id] = set()
    state.upstream[downstream_id].add(upstream_id)
    state.downstream[upstream_id].add(downstream_id)


@proto.transition(DAG.remove_node)
def remove_node():
    pass


@remove_node.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_x",)


@remove_node.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        if node_id in state.nodes:
            return Value(None)
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@remove_node.provide
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    if node_id in state.nodes:
        for dep in list(state.upstream.get(node_id, set())):
            state.downstream.get(dep, set()).discard(node_id)
        for child in list(state.downstream.get(node_id, set())):
            state.upstream.get(child, set()).discard(node_id)
        del state.nodes[node_id]
        state.upstream.pop(node_id, None)
        state.downstream.pop(node_id, None)


@proto.transition(DAG.has_node)
def has_node():
    pass


@has_node.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_check",)


@has_node.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        return Value(node_id in state.nodes)
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.get_node)
def get_node():
    pass


@get_node.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_get",)


@get_node.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        if node_id in state.nodes:
            info = state.nodes[node_id]
            return Value(NodeDefinition(
                node_id=info["node_id"],
                action=info["action"],
                dependencies=info["dependencies"],
                priority=info["priority"],
                retries=info["retries"],
            ))
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.get_dependencies)
def get_dependencies():
    pass


@get_dependencies.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_deps",)


@get_dependencies.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        if node_id in state.nodes:
            return Value(state.upstream.get(node_id, set()).copy())
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.get_dependents)
def get_dependents():
    pass


@get_dependents.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_dependents",)


@get_dependents.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        if node_id in state.nodes:
            return Value(state.downstream.get(node_id, set()).copy())
        return Raised(NodeNotFoundError(message=f"Node {node_id} not found", node_id=node_id))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.all_nodes)
def all_nodes():
    pass


@all_nodes.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@all_nodes.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        return Value(set(state.nodes.keys()))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.validate)
def validate():
    pass


@validate.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@validate.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    return _as_outcome(outcome)


@proto.transition(DAG.topological_sort)
def topological_sort():
    pass


@topological_sort.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@topological_sort.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        return Value(list(state.nodes.keys()))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.find_roots)
def find_roots():
    pass


@find_roots.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@find_roots.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        roots = {nid for nid in state.nodes if not state.upstream.get(nid, set())}
        return Value(roots)
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.find_leaves)
def find_leaves():
    pass


@find_leaves.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@find_leaves.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        leaves = {nid for nid in state.nodes if not state.downstream.get(nid, set())}
        return Value(leaves)
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(DAG.compute_critical_path)
def compute_critical_path():
    pass


@compute_critical_path.arguments
def _(
    state: TargetState,
    this: Any,
    estimated_durations: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(estimated_durations),)


@compute_critical_path.returns
def _(
    state: TargetState,
    this: Any,
    estimated_durations: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        return Value((list(state.nodes.keys()), 1.0))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


# --- WaveScheduler Transitions ---

@proto.transition(WaveScheduler.next_wave)
def next_wave():
    pass


@next_wave.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@next_wave.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    return _as_outcome(outcome)


@proto.transition(WaveScheduler.mark_running)
def mark_running():
    pass


@mark_running.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_run",)


@mark_running.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    return _as_outcome(outcome)


@mark_running.provide
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    state.scheduler_states[node_id] = NodeState.RUNNING.value


@proto.transition(WaveScheduler.mark_succeeded)
def mark_succeeded():
    pass


@mark_succeeded.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_succ",)


@mark_succeeded.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    return _as_outcome(outcome)


@mark_succeeded.provide
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    state.scheduler_states[node_id] = NodeState.SUCCEEDED.value
    for child in state.downstream.get(node_id, set()):
        if child in state.scheduler_states and state.scheduler_states[child] == NodeState.PENDING.value:
            deps = state.upstream.get(child, set())
            if all(state.scheduler_states.get(d) == NodeState.SUCCEEDED.value for d in deps):
                state.scheduler_states[child] = NodeState.READY.value


@proto.transition(WaveScheduler.mark_failed)
def mark_failed():
    pass


@mark_failed.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
    failure_policy: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    fp = failure_policy if not _is_not_bound(failure_policy) else FailurePolicy.FAIL_FAST
    return (_val_or(node_id) or "node_fail", fp)


@mark_failed.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    return _as_outcome(outcome)


@mark_failed.provide
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    state.scheduler_states[node_id] = NodeState.FAILED.value
    if failure_policy == FailurePolicy.FAIL_FAST:
        for nid_, st_val in list(state.scheduler_states.items()):
            if st_val not in (NodeState.SUCCEEDED.value, NodeState.FAILED.value):
                state.scheduler_states[nid_] = NodeState.CANCELLED.value
    elif failure_policy == FailurePolicy.SKIP_DOWNSTREAM:
        _mark_skip_downstream(state, node_id)


def _mark_skip_downstream(state: TargetState, node_id: str) -> None:
    """Traverse transitive downstream dependents and mark as SKIPPED."""
    queue = list(state.downstream.get(node_id, set()))
    while queue:
        current = queue.pop(0)
        if current not in state.scheduler_states:
            continue
        st_val = state.scheduler_states[current]
        if st_val not in (NodeState.SUCCEEDED.value, NodeState.FAILED.value, NodeState.SKIPPED.value):
            state.scheduler_states[current] = NodeState.SKIPPED.value
            queue.extend(state.downstream.get(current, set()))


@proto.transition(WaveScheduler.is_finished)
def is_finished():
    pass


@is_finished.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@is_finished.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        terminal = {NodeState.SUCCEEDED.value, NodeState.FAILED.value, NodeState.SKIPPED.value, NodeState.CANCELLED.value}
        all_terminal = all(
            state.scheduler_states.get(nid, NodeState.PENDING.value) in terminal
            for nid in state.nodes
        ) if state.nodes else True
        return Value(all_terminal)
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(WaveScheduler.get_state)
def get_state():
    pass


@get_state.arguments
def _(
    state: TargetState,
    this: Any,
    node_id: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (_val_or(node_id) or "node_st",)


@get_state.returns
def _(
    state: TargetState,
    this: Any,
    node_id: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        current = state.scheduler_states.get(node_id, NodeState.PENDING.value)
        return Value(current)
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


@proto.transition(WaveScheduler.get_all_states)
def get_all_states():
    pass


@get_all_states.arguments
def _(
    state: TargetState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@get_all_states.returns
def _(
    state: TargetState,
    this: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        return Value(dict(state.scheduler_states))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


# --- DAGRunner Transitions ---

@proto.transition(DAGRunner.run)
def run():
    pass


@run.arguments
def _(
    state: TargetState,
    this: Any,
    failure_policy: Any = NotBound,
) -> Optional[Tuple[Any, ...]]:
    fp = failure_policy if not _is_not_bound(failure_policy) else FailurePolicy.FAIL_FAST
    return (fp,)


@run.returns
def _(
    state: TargetState,
    this: Any,
    failure_policy: Any,
    outcome: Any = NotBound,
) -> Optional[Outcome[Any]]:
    if _is_not_bound(outcome):
        return Value(DAGRunReport(
            total_nodes=len(state.nodes),
            succeeded_nodes=tuple(k for k, v in state.results.items() if v.get("state") == NodeState.SUCCEEDED.value),
            failed_nodes=tuple(k for k, v in state.results.items() if v.get("state") == NodeState.FAILED.value),
            skipped_nodes=tuple(k for k, v in state.results.items() if v.get("state") == NodeState.SKIPPED.value),
            cancelled_nodes=tuple(k for k, v in state.results.items() if v.get("state") == NodeState.CANCELLED.value),
            wall_clock_seconds=0.01,
            critical_path=tuple(state.nodes.keys()),
            results={},
        ))
    return outcome if isinstance(outcome, (Value, Raised)) else Value(outcome)


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_target_fakes(state: TargetState) -> Tuple[DAG, WaveScheduler, DAGRunner]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = proto.make_state_machine(state)
    return (sm.as_fake(DAG), sm.as_fake(WaveScheduler), sm.as_fake(DAGRunner))


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestTargetUnit(unittest.TestCase):
    """Verifies that synthesized fake conforms to state machine specification."""

    def setUp(self) -> None:
        self.state = TargetState()
        self.dag, self.scheduler, self.runner = make_target_fakes(self.state)

    def test_add_node_creates_node(self) -> None:
        self.dag.add_node("a", lambda: None, priority=1)
        self.assertTrue(self.dag.has_node("a"))
        self.assertIn("a", self.state.nodes)

    def test_add_node_registers_dependencies(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        deps = self.dag.get_dependencies("b")
        self.assertEqual(deps, {"a"})
        self.assertIn("b", self.dag.get_dependents("a"))

    def test_has_node_returns_false_for_missing(self) -> None:
        self.assertFalse(self.dag.has_node("nonexistent"))

    def test_get_node_raises_on_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("nonexistent")

    def test_add_edge_raises_on_missing_node(self) -> None:
        self.dag.add_node("x", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("x", "missing")

    def test_remove_node_clears_edges(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependents("b"), set())

    def test_find_roots_and_leaves(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        roots = self.dag.find_roots()
        leaves = self.dag.find_leaves()
        self.assertIn("a", roots)
        self.assertIn("b", leaves)

    def test_all_nodes(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})

    def test_scheduler_initializes_state(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.RUNNING.value)

    def test_scheduler_mark_succeeded(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.SUCCEEDED.value)

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.scheduler.mark_succeeded("a")
        self.scheduler.mark_running("b")
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED.value)

    def test_mark_succeeded_unlocks_dependents(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.scheduler.mark_succeeded("a")
        states = self.scheduler.get_all_states()
        self.assertEqual(states.get("b"), NodeState.READY.value)

    def test_is_finished_true_when_all_terminal(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.scheduler.mark_succeeded("a")
        self.assertTrue(self.scheduler.is_finished())

    def test_is_finished_false_when_pending(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.assertFalse(self.scheduler.is_finished())

    def test_topological_sort_basic(self) -> None:
        self.dag.add_node("b", lambda: None, priority=1)
        self.dag.add_node("a", lambda: None, priority=2)
        order = self.dag.topological_sort()
        self.assertIn("a", order)
        self.assertIn("b", order)

    def test_compute_critical_path_basic(self) -> None:
        self.dag.add_node("a", lambda: None)
        path, total = self.dag.compute_critical_path()
        self.assertGreaterEqual(total, 0.0)


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestTargetImplReal(unittest.TestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.dag = get_singleton(DAG)
        self.scheduler = get_singleton(WaveScheduler)
        self.runner = get_singleton(DAGRunner)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_add_node(self) -> None:
        self.dag.add_node("a", lambda: "ok", priority=1, retries=1)
        self.assertTrue(self.dag.has_node("a"))
        nd = self.dag.get_node("a")
        self.assertEqual(nd.node_id, "a")
        self.assertEqual(nd.priority, 1)
        self.assertEqual(nd.retries, 1)

    def test_add_node_no_deps(self) -> None:
        self.dag.add_node("x", lambda: None)
        deps = self.dag.get_dependencies("x")
        self.assertEqual(deps, set())

    def test_add_edge(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.dag.add_edge("a", "b")
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_add_edge_missing_upstream(self) -> None:
        self.dag.add_node("b", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("missing", "b")

    def test_add_edge_missing_downstream(self) -> None:
        self.dag.add_node("a", lambda: None)
        with self.assertRaises(NodeNotFoundError):
            self.dag.add_edge("a", "missing")

    def test_remove_node(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertEqual(self.dag.get_dependencies("b"), set())

    def test_remove_node_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.remove_node("nonexistent")

    def test_find_roots(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        roots = self.dag.find_roots()
        self.assertEqual(roots, {"a"})

    def test_find_leaves(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        leaves = self.dag.find_leaves()
        self.assertEqual(leaves, {"b"})

    def test_all_nodes(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.assertEqual(self.dag.all_nodes(), {"a", "b"})

    def test_get_dependencies_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependencies("missing")

    def test_get_dependents_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_dependents("missing")

    def test_validate_empty(self) -> None:
        self.dag.validate()

    def test_validate_basic(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.dag.validate()

    def test_topological_sort_independent(self) -> None:
        self.dag.add_node("b", lambda: None, priority=1)
        self.dag.add_node("a", lambda: None, priority=2)
        order = self.dag.topological_sort()
        self.assertEqual(order[0], "a")
        self.assertEqual(order[1], "b")

    def test_topological_sort_with_deps(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        order = self.dag.topological_sort()
        self.assertEqual(order.index("a"), 0)
        self.assertEqual(order.index("b"), 1)

    def test_compute_critical_path_single(self) -> None:
        self.dag.add_node("a", lambda: None)
        path, total = self.dag.compute_critical_path()
        self.assertEqual(total, 1.0)
        self.assertEqual(list(path), ["a"])

    def test_compute_critical_path_with_durations(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        path, total = self.dag.compute_critical_path(estimated_durations={"a": 2.0, "b": 3.0})
        self.assertEqual(total, 5.0)
        self.assertEqual(list(path), ["a", "b"])

    def test_compute_critical_path_empty(self) -> None:
        path, total = self.dag.compute_critical_path()
        self.assertEqual(list(path), [])
        self.assertEqual(total, 0.0)

    def test_validate_graph_missing_dependency(self) -> None:
        self.dag.add_node("a", lambda: None, dependencies=["nonexistent"])
        with self.assertRaises(NodeNotFoundError):
            self.dag.validate()

    def test_validate_graph_cyclic(self) -> None:
        self.dag.add_node("a", lambda: None, dependencies=["b"])
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        with self.assertRaises(CycleError) as ctx:
            self.dag.validate()
        self.assertIn("a", str(ctx.exception))
        self.assertIn("b", str(ctx.exception))

    def test_topological_sort_cyclic(self) -> None:
        self.dag.add_node("a", lambda: None, dependencies=["b"])
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        with self.assertRaises(CycleError):
            self.dag.topological_sort()

    def test_get_node_missing_raises(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self.dag.get_node("nonexistent")

    def test_remove_node_downstream_cleanup(self) -> None:
        self.dag.add_node("x", lambda: None)
        self.dag.add_node("a", lambda: None, dependencies=["x"])
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.dag.remove_node("a")
        self.assertFalse(self.dag.has_node("a"))
        self.assertNotIn("a", self.dag.get_dependencies("b"))
        self.assertNotIn("b", self.dag.get_dependents("x"))
        self.assertTrue(self.dag.has_node("x"))
        self.assertTrue(self.dag.has_node("b"))

    def test_runner_empty_wave_terminates(self) -> None:
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(list(report.succeeded_nodes), [])
        self.assertEqual(list(report.failed_nodes), [])

    def test_runner_deadlock_guard(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        # Put nodes into non-terminal states so next_wave() returns empty
        # but is_finished() returns False (non-terminal nodes still exist)
        self.scheduler.mark_running("a")
        self.scheduler.mark_succeeded("a")
        self.scheduler.mark_running("b")
        # b is RUNNING (non-terminal), a is SUCCEEDED, nothing is READY
        # next_wave() == [] but is_finished() == False -> deadlock guard fires
        report = self.runner.run()
        self.assertTrue(report.total_nodes >= 2)

    # --- WaveScheduler tests ---

    def test_scheduler_next_wave_empty(self) -> None:
        wave = self.scheduler.next_wave()
        self.assertEqual(wave, [])

    def test_scheduler_next_wave_ready(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        wave = self.scheduler.next_wave()
        self.assertEqual(wave, ["a"])

    def test_scheduler_mark_running(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.scheduler.mark_running("a")
        self.assertEqual(self.scheduler.get_state("a"), NodeState.RUNNING)

    def test_scheduler_mark_succeeded_promotes_ready(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.scheduler.mark_succeeded("a")
        wave = self.scheduler.next_wave()
        self.assertIn("b", wave)

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None)
        self.scheduler.mark_failed("a", FailurePolicy.FAIL_FAST)
        self.assertEqual(self.scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.CANCELLED)

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        self.scheduler.mark_failed("a", FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self.scheduler.get_state("b"), NodeState.SKIPPED)

    def test_scheduler_is_finished_empty(self) -> None:
        self.assertTrue(self.scheduler.is_finished())

    def test_scheduler_is_finished_not_done(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.assertFalse(self.scheduler.is_finished())

    def test_get_all_states(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.scheduler.mark_running("a")
        states = self.scheduler.get_all_states()
        self.assertIn("a", states)

    # --- DAGRunner tests ---

    def test_runner_basic(self) -> None:
        self.dag.add_node("a", lambda: "result_a")
        self.dag.add_node("b", lambda: "result_b", dependencies=["a"])
        report = self.runner.run()
        self.assertEqual(report.total_nodes, 2)
        self.assertEqual(report.succeeded_nodes, ("a", "b"))

    def test_runner_with_retry_success(self) -> None:
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("fail")
            return "ok"

        self.dag.add_node("a", flaky, retries=2)
        report = self.runner.run()
        self.assertEqual(report.succeeded_nodes, ("a",))

    def test_runner_fail_fast(self) -> None:
        self.dag.add_node("a", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        report = self.runner.run(FailurePolicy.FAIL_FAST)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.cancelled_nodes, ("b",))

    def test_runner_continue_on_error(self) -> None:
        self.dag.add_node("a", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.dag.add_node("b", lambda: "ok")
        report = self.runner.run(FailurePolicy.CONTINUE_ON_ERROR)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.succeeded_nodes, ("b",))

    def test_runner_skip_downstream(self) -> None:
        self.dag.add_node("a", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        report = self.runner.run(FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(report.failed_nodes, ("a",))
        self.assertEqual(report.skipped_nodes, ("b",))

    def test_runner_with_custom_durations(self) -> None:
        self.dag.add_node("a", lambda: None)
        self.dag.add_node("b", lambda: None, dependencies=["a"])
        report = self.runner.run()
        self.assertIn("a", report.critical_path)
        self.assertIn("b", report.critical_path)


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

def make_sut() -> "TargetSUT":
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return TargetSUT(registry, scope)


class TargetSUT:
    """Multi-singleton aggregate SUT delegating method lookups across DAG, WaveScheduler, DAGRunner."""
    tier = system

    def __init__(self, registry: LifecycleRegistry, scope: Any) -> None:
        self.registry = registry
        self.phase_scope = scope
        self._dag = get_singleton(DAG)
        self._scheduler = get_singleton(WaveScheduler)
        self._runner = get_singleton(DAGRunner)
        self.__dict__["_services"] = (self._dag, self._scheduler, self._runner)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


TargetFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=TargetState,
    name="TargetFuzzTest",
)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T19:35:28Z
# LAST_CHANGED: 2026-10-26T19:34:32Z
# CHANGE: Added test_runner_deadlock_guard: verifies DAGRunner.run() handles the deadlock scenario where nodes exist in non-terminal states (e.g. RUNNING) but no nodes are READY for execution — next_wave() returns empty while is_finished() returns False, exercising the deadlock guard break path.
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T19:35:28Z
# PRETENSE_QA_AUDIT: 2026-10-26T19:35:02Z
# --- END CLEANROOM METADATA ---
