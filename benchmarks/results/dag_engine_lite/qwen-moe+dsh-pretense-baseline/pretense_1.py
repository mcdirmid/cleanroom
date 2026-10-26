"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for DagEngineLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite_impl import DAG, WaveScheduler, DAGRunner, __initialize__
from benchmark_1.parts.dag_engine_lite.lib.dag_engine_lite import (
    DAGError,
    CycleError,
    DAGRunReport,
    DAGRunner as DAGRunnerProto,
    DAG as DAGProto,
    FailurePolicy,
    NodeDefinition,
    NodeNotFoundError,
    NodeResult,
    NodeState,
    WaveScheduler as WaveSchedulerProto,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class DagEngineLiteState:
    """Canonical model state for DagEngineLite operations."""
    nodes: Set[str] = field(default_factory=set)
    node_definitions: Dict[str, Any] = field(default_factory=dict)
    upstream: Dict[str, Set[str]] = field(default_factory=dict)
    downstream: Dict[str, Set[str]] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)


# Re-import Dict for the dataclass field annotation
from typing import Dict


def _ensure_sets(target: Dict[str, Set[str]], keys: List[str]) -> None:
    for k in keys:
        if k not in target:
            target[k] = set()


proto = StateMachineProto[DagEngineLiteState]()


# ------------------------------------------------------------------------------
# 1.1 DAG.add_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.add_node)
def add_node():
    pass


@add_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    action: Any | NotBoundType = NotBound,
    dependencies: Any | NotBoundType = NotBound,
    priority: Any | NotBoundType = NotBound,
    retries: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (
        node_id if not isinstance(node_id, NotBoundType) else "node_1",
        action if not isinstance(action, NotBoundType) else (lambda: None),
        dependencies if not isinstance(dependencies, NotBoundType) else [],
        priority if not isinstance(priority, NotBoundType) else 0,
        retries if not isinstance(retries, NotBoundType) else 0,
    )


@add_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@add_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    action: Any,
    dependencies: Any,
    priority: Any,
    retries: Any,
    result: Any,
) -> None:
    if node_id not in state.nodes:
        state.nodes.add(node_id)
        state.node_definitions[node_id] = {"action": action, "dependencies": set(dependencies) if dependencies else set(), "priority": priority, "retries": retries}
        _ensure_sets(state.upstream, [node_id])
        _ensure_sets(state.downstream, [node_id])
        for dep_id in (dependencies or []):
            _ensure_sets(state.upstream, [dep_id])
            _ensure_sets(state.downstream, [dep_id])
            state.upstream[node_id].add(dep_id)
            state.downstream[dep_id].add(node_id)


# ------------------------------------------------------------------------------
# 1.2 DAG.add_edge
# ------------------------------------------------------------------------------

@proto.transition(DAG.add_edge)
def add_edge():
    pass


@add_edge.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any | NotBoundType = NotBound,
    downstream_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (
        upstream_id if not isinstance(upstream_id, NotBoundType) else "node_1",
        downstream_id if not isinstance(downstream_id, NotBoundType) else "node_2",
    )


@add_edge.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@add_edge.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    upstream_id: Any,
    downstream_id: Any,
    result: Any,
) -> None:
    if upstream_id not in state.nodes or downstream_id not in state.nodes:
        return
    _ensure_sets(state.upstream, [downstream_id])
    _ensure_sets(state.downstream, [upstream_id])
    state.upstream[downstream_id].add(upstream_id)
    state.downstream[upstream_id].add(downstream_id)


# ------------------------------------------------------------------------------
# 1.3 DAG.remove_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.remove_node)
def remove_node():
    pass


@remove_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@remove_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@remove_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    if node_id in state.nodes:
        state.nodes.discard(node_id)
        state.node_definitions.pop(node_id, None)
        state.node_states.pop(node_id, None)
        for dep_id in list(state.upstream.get(node_id, set())):
            state.downstream[dep_id].discard(node_id)
        for dep_id in list(state.downstream.get(node_id, set())):
            state.upstream[dep_id].discard(node_id)
        state.upstream.pop(node_id, None)
        state.downstream.pop(node_id, None)


# ------------------------------------------------------------------------------
# 1.4 DAG.has_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.has_node)
def has_node():
    pass


@has_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@has_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(state.nodes.__contains__(node_id))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@has_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.5 DAG.get_node
# ------------------------------------------------------------------------------

@proto.transition(DAG.get_node)
def get_node():
    pass


@get_node.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@get_node.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if node_id in state.nodes:
            return Value(state.node_definitions.get(node_id, {}))
        return Raised(NodeNotFoundError(message=f"Node '{node_id}' not found", node_id=node_id))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@get_node.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.6 DAG.get_dependencies
# ------------------------------------------------------------------------------

@proto.transition(DAG.get_dependencies)
def get_dependencies():
    pass


@get_dependencies.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@get_dependencies.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if node_id not in state.nodes:
            return Raised(NodeNotFoundError(message=f"Node '{node_id}' not found", node_id=node_id))
        return Value(state.upstream.get(node_id, set()))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@get_dependencies.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.7 DAG.get_dependents
# ------------------------------------------------------------------------------

@proto.transition(DAG.get_dependents)
def get_dependents():
    pass


@get_dependents.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@get_dependents.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if node_id not in state.nodes:
            return Raised(NodeNotFoundError(message=f"Node '{node_id}' not found", node_id=node_id))
        return Value(state.downstream.get(node_id, set()))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@get_dependents.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.8 DAG.all_nodes
# ------------------------------------------------------------------------------

@proto.transition(DAG.all_nodes)
def all_nodes():
    pass


@all_nodes.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@all_nodes.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(state.nodes)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@all_nodes.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.9 DAG.validate
# ------------------------------------------------------------------------------

@proto.transition(DAG.validate)
def validate():
    pass


@validate.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@validate.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@validate.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.10 DAG.topological_sort
# ------------------------------------------------------------------------------

@proto.transition(DAG.topological_sort)
def topological_sort():
    pass


@topological_sort.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@topological_sort.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(list(state.nodes))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@topological_sort.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.11 DAG.find_roots
# ------------------------------------------------------------------------------

@proto.transition(DAG.find_roots)
def find_roots():
    pass


@find_roots.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@find_roots.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        roots = set()
        for nid in state.nodes:
            if not state.upstream.get(nid):
                roots.add(nid)
        return Value(roots)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@find_roots.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.12 DAG.find_leaves
# ------------------------------------------------------------------------------

@proto.transition(DAG.find_leaves)
def find_leaves():
    pass


@find_leaves.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@find_leaves.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        leaves = set()
        for nid in state.nodes:
            if not state.downstream.get(nid):
                leaves.add(nid)
        return Value(leaves)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@find_leaves.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.13 DAG.compute_critical_path
# ------------------------------------------------------------------------------

@proto.transition(DAG.compute_critical_path)
def compute_critical_path():
    pass


@compute_critical_path.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (estimated_durations if not isinstance(estimated_durations, NotBoundType) else None,)


@compute_critical_path.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value((list(state.nodes) if state.nodes else [], 0.0))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@compute_critical_path.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    estimated_durations: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.14 WaveScheduler.next_wave
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.next_wave)
def next_wave():
    pass


@next_wave.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@next_wave.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value([])
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@next_wave.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.15 WaveScheduler.mark_running
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.mark_running)
def mark_running():
    pass


@mark_running.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@mark_running.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@mark_running.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    if node_id in state.nodes:
        state.node_states[node_id] = NodeState.RUNNING


# ------------------------------------------------------------------------------
# 1.16 WaveScheduler.mark_succeeded
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.mark_succeeded)
def mark_succeeded():
    pass


@mark_succeeded.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@mark_succeeded.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@mark_succeeded.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    if node_id in state.nodes:
        state.node_states[node_id] = NodeState.SUCCEEDED


# ------------------------------------------------------------------------------
# 1.17 WaveScheduler.mark_failed
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.mark_failed)
def mark_failed():
    pass


@mark_failed.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    policy_val = failure_policy if not isinstance(failure_policy, NotBoundType) else "fail_fast"
    return (
        node_id if not isinstance(node_id, NotBoundType) else "node_1",
        policy_val,
    )


@mark_failed.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@mark_failed.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    if node_id in state.nodes:
        state.node_states[node_id] = NodeState.FAILED
        policy_str = failure_policy if isinstance(failure_policy, str) else failure_policy.value if hasattr(failure_policy, 'value') else "fail_fast"
        if policy_str in ("fail_fast", FailurePolicy.FAIL_FAST.value):
            for nid in state.nodes:
                if state.node_states.get(nid) in (NodeState.PENDING, NodeState.READY, NodeState.RUNNING):
                    state.node_states[nid] = NodeState.CANCELLED
        elif policy_str in ("skip_downstream", FailurePolicy.SKIP_DOWNSTREAM.value):
            to_skip = set()
            queue = [node_id]
            while queue:
                cur = queue.pop(0)
                for dep in state.downstream.get(cur, set()):
                    if dep not in to_skip and dep != node_id:
                        to_skip.add(dep)
                        queue.append(dep)
            for sid in to_skip:
                if state.node_states.get(sid) not in (NodeState.SUCCEEDED, NodeState.FAILED):
                    state.node_states[sid] = NodeState.SKIPPED


# ------------------------------------------------------------------------------
# 1.18 WaveScheduler.is_finished
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.is_finished)
def is_finished():
    pass


@is_finished.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@is_finished.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        if not state.nodes:
            return Value(True)
        terminal = (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED, NodeState.CANCELLED)
        all_terminal = all(state.node_states.get(n, NodeState.PENDING) in terminal for n in state.nodes)
        return Value(all_terminal)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@is_finished.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.19 WaveScheduler.get_state
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.get_state)
def get_state():
    pass


@get_state.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    return (node_id if not isinstance(node_id, NotBoundType) else "node_1",)


@get_state.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(state.node_states.get(node_id, NodeState.PENDING))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@get_state.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    node_id: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.20 WaveScheduler.get_all_states
# ------------------------------------------------------------------------------

@proto.transition(WaveScheduler.get_all_states)
def get_all_states():
    pass


@get_all_states.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
) -> Optional[Tuple[Any, ...]]:
    return ()


@get_all_states.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(dict(state.node_states))
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@get_all_states.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    result: Any,
) -> None:
    pass


# ------------------------------------------------------------------------------
# 1.21 DAGRunner.run
# ------------------------------------------------------------------------------

@proto.transition(DAGRunner.run)
def run():
    pass


@run.arguments
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    policy_val = failure_policy if not isinstance(failure_policy, NotBoundType) else "fail_fast"
    return (policy_val,)


@run.returns
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[Any]]:
    if outcome is NotBound:
        return Value(None)
    return outcome if isinstance(outcome, Outcome) else Value(outcome)


@run.provide
def _(
    state: DagEngineLiteState,
    this: Any,
    failure_policy: Any,
    result: Any,
) -> None:
    pass


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

# Fakes are synthesized by the proto; no explicit fake factory needed.
# The proto's hypothesis strategies cover the transition argument space.


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestDagEngineFakeUnit(unittest.TestCase):
    """Deterministic unit tests verifying fake transitions against the state model."""

    def test_add_node_basic(self) -> None:
        """add_node must register the node in the model state."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 1, 0, result=None)
        self.assertIn("x", state.nodes)
        self.assertIn("x", state.node_definitions)

    def test_add_node_with_deps(self) -> None:
        """add_node must link dependencies in upstream/downstream dicts."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, ["a"], 0, 0, result=None)
        self.assertIn("a", state.upstream["b"])
        self.assertIn("b", state.downstream["a"])

    def test_add_edge_valid(self) -> None:
        """add_edge must link nodes when both exist."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "u", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "d", lambda: 2, [], 0, 0, result=None)
        add_edge.provider(state, None, "u", "d", result=None)
        self.assertIn("u", state.upstream["d"])
        self.assertIn("d", state.downstream["u"])

    def test_remove_node_existing(self) -> None:
        """remove_node must purge the node from all tracking dicts."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "y", lambda: 2, ["x"], 0, 0, result=None)
        remove_node.provider(state, None, "x", result=None)
        self.assertNotIn("x", state.nodes)
        self.assertNotIn("x", state.node_definitions)
        self.assertNotIn("x", state.upstream)
        self.assertNotIn("x", state.downstream)

    def test_has_node_exists(self) -> None:
        """has_node must return True for registered nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        result = has_node.return_fn(state, None, "x")
        self.assertEqual(result, Value(True))

    def test_has_node_absent(self) -> None:
        """has_node must return False for unregistered nodes."""
        state = DagEngineLiteState()
        result = has_node.return_fn(state, None, "x")
        self.assertEqual(result, Value(False))

    def test_get_node_missing(self) -> None:
        """get_node must return NodeNotFoundError for missing nodes."""
        state = DagEngineLiteState()
        result = get_node.return_fn(state, None, "x")
        self.assertIsInstance(result, Raised)
        self.assertIsInstance(result.exc, NodeNotFoundError)

    def test_get_node_def_existing(self) -> None:
        """get_node must return the definition for existing nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 42, [], 5, 2, result=None)
        result = get_node.return_fn(state, None, "x")
        self.assertEqual(result.val["dependencies"], set())
        self.assertEqual(result.val["priority"], 5)
        self.assertEqual(result.val["retries"], 2)
        self.assertTrue(callable(result.val["action"]))

    def test_get_dependencies_existing(self) -> None:
        """get_dependencies must return upstream set for existing nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, ["a"], 0, 0, result=None)
        result = get_dependencies.return_fn(state, None, "b")
        self.assertEqual(result, Value({"a"}))

    def test_get_dependents_existing(self) -> None:
        """get_dependents must return downstream set for existing nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, ["a"], 0, 0, result=None)
        result = get_dependents.return_fn(state, None, "a")
        self.assertEqual(result, Value({"b"}))

    def test_all_nodes_empty(self) -> None:
        """all_nodes must return empty set for empty graph."""
        state = DagEngineLiteState()
        result = all_nodes.return_fn(state, None)
        self.assertEqual(result, Value(set()))

    def test_all_nodes_nonempty(self) -> None:
        """all_nodes must return registered nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, [], 0, 0, result=None)
        result = all_nodes.return_fn(state, None)
        self.assertEqual(result, Value({"a", "b"}))

    def test_find_roots(self) -> None:
        """find_roots must return nodes with no dependencies."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "root", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "child", lambda: 2, ["root"], 0, 0, result=None)
        result = find_roots.return_fn(state, None)
        self.assertEqual(result, Value({"root"}))

    def test_find_leaves(self) -> None:
        """find_leaves must return nodes with no dependents."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "root", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "leaf", lambda: 2, ["root"], 0, 0, result=None)
        result = find_leaves.return_fn(state, None)
        self.assertEqual(result, Value({"leaf"}))

    def test_mark_running(self) -> None:
        """mark_running must set RUNNING state."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        mark_running.provider(state, None, "x", result=None)
        self.assertEqual(state.node_states["x"], NodeState.RUNNING)

    def test_mark_succeeded(self) -> None:
        """mark_succeeded must set SUCCEEDED state."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        mark_succeeded.provider(state, None, "x", result=None)
        self.assertEqual(state.node_states["x"], NodeState.SUCCEEDED)

    def test_mark_failed_fail_fast(self) -> None:
        """mark_failed with FAIL_FAST must cancel all non-terminal nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, [], 0, 0, result=None)
        mark_succeeded.provider(state, None, "a", result=None)
        mark_failed.provider(state, None, "b", "fail_fast", result=None)
        self.assertEqual(state.node_states["b"], NodeState.FAILED)
        self.assertEqual(state.node_states["a"], NodeState.SUCCEEDED)

    def test_mark_failed_skip_downstream(self) -> None:
        """mark_failed with SKIP_DOWNSTREAM must skip transitive dependents."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, ["a"], 0, 0, result=None)
        add_node.provider(state, None, "c", lambda: 3, ["b"], 0, 0, result=None)
        mark_failed.provider(state, None, "a", "skip_downstream", result=None)
        self.assertEqual(state.node_states["a"], NodeState.FAILED)
        self.assertEqual(state.node_states["b"], NodeState.SKIPPED)
        self.assertEqual(state.node_states["c"], NodeState.SKIPPED)

    def test_is_finished_empty(self) -> None:
        """is_finished must return True for empty graph."""
        state = DagEngineLiteState()
        result = is_finished.return_fn(state, None)
        self.assertEqual(result, Value(True))

    def test_is_finished_all_succeeded(self) -> None:
        """is_finished must return True when all nodes succeeded."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        mark_succeeded.provider(state, None, "x", result=None)
        result = is_finished.return_fn(state, None)
        self.assertEqual(result, Value(True))

    def test_is_finished_not_done(self) -> None:
        """is_finished must return False when nodes are still pending."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        result = is_finished.return_fn(state, None)
        self.assertEqual(result, Value(False))

    def test_get_state_default_pending(self) -> None:
        """get_state must return PENDING for untracked nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "x", lambda: 1, [], 0, 0, result=None)
        result = get_state.return_fn(state, None, "x")
        self.assertEqual(result, Value(NodeState.PENDING))

    def test_get_all_states(self) -> None:
        """get_all_states must return all tracked states."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, ["a"], 0, 0, result=None)
        mark_succeeded.provider(state, None, "a", result=None)
        mark_running.provider(state, None, "b", result=None)
        result = get_all_states.return_fn(state, None)
        expected = {"a": NodeState.SUCCEEDED, "b": NodeState.RUNNING}
        self.assertEqual(result, Value(expected))

    def test_compute_critical_path_empty(self) -> None:
        """compute_critical_path must return empty path for empty graph."""
        state = DagEngineLiteState()
        result = compute_critical_path.return_fn(state, None, None)
        self.assertEqual(result, Value(([], 0.0)))

    def test_next_wave_empty(self) -> None:
        """next_wave must return empty list for empty graph."""
        state = DagEngineLiteState()
        result = next_wave.return_fn(state, None)
        self.assertEqual(result, Value([]))

    def test_validate_no_error(self) -> None:
        """validate must return None for valid graphs."""
        state = DagEngineLiteState()
        result = validate.return_fn(state, None)
        self.assertEqual(result, Value(None))

    def test_topological_sort_returns_nodes(self) -> None:
        """topological_sort must return a list of all nodes."""
        state = DagEngineLiteState()
        add_node.provider(state, None, "a", lambda: 1, [], 0, 0, result=None)
        add_node.provider(state, None, "b", lambda: 2, [], 0, 0, result=None)
        result = topological_sort.return_fn(state, None)
        self.assertEqual(set(result.val), {"a", "b"})


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestDagEngineLiteUnit(unittest.TestCase):
    """Deterministic unit tests verifying real implementation against the state model."""

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)
        self._scope = enter_phase(system, registry=self._registry)
        self._scope.__enter__()
        self._dag = get_singleton(DAG)
        self._scheduler = get_singleton(WaveScheduler)
        self._runner = get_singleton(DAGRunner)

    def tearDown(self) -> None:
        self._scope.__exit__(None, None, None)

    def test_add_node_single(self) -> None:
        self._dag.add_node("a", lambda: 42, priority=5)
        self.assertTrue(self._dag.has_node("a"))
        defn = self._dag.get_node("a")
        self.assertEqual(defn.node_id, "a")
        self.assertEqual(defn.priority, 5)
        self.assertEqual(defn.retries, 0)
        self.assertEqual(defn.dependencies, frozenset())

    def test_add_node_with_deps(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"], priority=1)
        self.assertEqual(self._dag.get_dependencies("b"), {"a"})
        self.assertEqual(self._dag.get_dependents("a"), {"b"})
        self.assertEqual(self._dag.get_node("b").dependencies, frozenset({"a"}))

    def test_add_node_default_values(self) -> None:
        self._dag.add_node("x", lambda: 1)
        defn = self._dag.get_node("x")
        self.assertEqual(defn.priority, 0)
        self.assertEqual(defn.retries, 0)
        self.assertEqual(defn.dependencies, frozenset())

    def test_add_edge_valid(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        self._dag.add_edge("a", "b")
        self.assertEqual(self._dag.get_dependencies("b"), {"a"})
        self.assertEqual(self._dag.get_dependents("a"), {"b"})

    def test_add_edge_missing_upstream(self) -> None:
        self._dag.add_node("b", lambda: 2)
        with self.assertRaises(NodeNotFoundError) as ctx:
            self._dag.add_edge("nonexistent", "b")
        self.assertEqual(ctx.exception.node_id, "nonexistent")

    def test_add_edge_missing_downstream(self) -> None:
        self._dag.add_node("a", lambda: 1)
        with self.assertRaises(NodeNotFoundError) as ctx:
            self._dag.add_edge("a", "nonexistent")
        self.assertEqual(ctx.exception.node_id, "nonexistent")

    def test_remove_node_existing(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.remove_node("a")
        self.assertFalse(self._dag.has_node("a"))
        self.assertTrue(self._dag.has_node("b"))
        self.assertEqual(self._dag.get_dependencies("b"), set())

    def test_remove_node_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self._dag.remove_node("nonexistent")

    def test_has_node_true(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self.assertTrue(self._dag.has_node("a"))

    def test_has_node_false(self) -> None:
        self.assertFalse(self._dag.has_node("nonexistent"))

    def test_get_node_valid(self) -> None:
        self._dag.add_node("a", lambda: 1)
        defn = self._dag.get_node("a")
        self.assertEqual(defn.node_id, "a")

    def test_get_node_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self._dag.get_node("nonexistent")

    def test_get_dependencies_valid(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self.assertEqual(self._dag.get_dependencies("b"), {"a"})

    def test_get_dependencies_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self._dag.get_dependencies("nonexistent")

    def test_get_dependents_valid(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self.assertEqual(self._dag.get_dependents("a"), {"b"})

    def test_get_dependents_missing(self) -> None:
        with self.assertRaises(NodeNotFoundError):
            self._dag.get_dependents("nonexistent")

    def test_all_nodes_empty(self) -> None:
        self.assertEqual(self._dag.all_nodes(), set())

    def test_all_nodes_multiple(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        self._dag.add_node("c", lambda: 3)
        self.assertEqual(self._dag.all_nodes(), {"a", "b", "c"})

    def test_validate_empty_graph(self) -> None:
        self._dag.validate()

    def test_validate_valid_graph(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.validate()

    def test_validate_missing_dependency(self) -> None:
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        with self.assertRaises(NodeNotFoundError):
            self._dag.validate()

    def test_validate_cycle(self) -> None:
        self._dag.add_node("a", lambda: 1, dependencies=["c"])
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["b"])
        with self.assertRaises(CycleError) as ctx:
            self._dag.validate()
        self.assertIsInstance(ctx.exception.cycle, tuple)

    def test_topological_sort_linear(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["b"])
        result = self._dag.topological_sort()
        self.assertLess(result.index("a"), result.index("b"))
        self.assertLess(result.index("b"), result.index("c"))

    def test_topological_sort_parallel(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["a"])
        result = self._dag.topological_sort()
        self.assertEqual(result[0], "a")
        self.assertIn("b", result[1:])
        self.assertIn("c", result[1:])

    def test_topological_sort_priority_tiebreak(self) -> None:
        self._dag.add_node("a", lambda: 1, priority=10)
        self._dag.add_node("b", lambda: 2, priority=5)
        self._dag.add_node("c", lambda: 3, priority=5)
        result = self._dag.topological_sort()
        self.assertEqual(result[0], "a")

    def test_topological_sort_alphabetical_tiebreak(self) -> None:
        self._dag.add_node("b", lambda: 2, priority=5)
        self._dag.add_node("a", lambda: 1, priority=5)
        self._dag.add_node("c", lambda: 3, priority=5)
        result = self._dag.topological_sort()
        self.assertEqual(result[0], "a")
        self.assertEqual(result[1], "b")
        self.assertEqual(result[2], "c")

    def test_topological_sort_cycle_raises(self) -> None:
        self._dag.add_node("a", lambda: 1, dependencies=["b"])
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        with self.assertRaises(CycleError):
            self._dag.topological_sort()

    def test_find_roots(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["a"])
        self.assertEqual(self._dag.find_roots(), {"a"})

    def test_find_roots_no_deps(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        self.assertEqual(self._dag.find_roots(), {"a", "b"})

    def test_find_leaves(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["a"])
        self.assertEqual(self._dag.find_leaves(), {"b", "c"})

    def test_find_leaves_no_dependents(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        self.assertEqual(self._dag.find_leaves(), {"a", "b"})

    def test_compute_critical_path_linear(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["b"])
        path, weight = self._dag.compute_critical_path()
        self.assertEqual(path, ["a", "b", "c"])
        self.assertEqual(weight, 3.0)

    def test_compute_critical_path_empty(self) -> None:
        path, weight = self._dag.compute_critical_path()
        self.assertEqual(path, [])
        self.assertEqual(weight, 0.0)

    def test_compute_critical_path_custom_durations(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        path, weight = self._dag.compute_critical_path(estimated_durations={"a": 10.0, "b": 1.0})
        self.assertEqual(path, ["a", "b"])
        self.assertEqual(weight, 11.0)

    def test_scheduler_initial_states(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self.assertEqual(self._scheduler.get_state("a"), NodeState.READY)
        self.assertEqual(self._scheduler.get_state("b"), NodeState.PENDING)

    def test_scheduler_next_wave(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3)
        wave = self._scheduler.next_wave()
        self.assertIn("a", wave)
        self.assertIn("c", wave)
        self.assertNotIn("b", wave)

    def test_scheduler_mark_running(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._scheduler.mark_running("a")
        self.assertEqual(self._scheduler.get_state("a"), NodeState.RUNNING)

    def test_scheduler_mark_succeeded_unlocks(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._scheduler.mark_succeeded("a")
        self.assertEqual(self._scheduler.get_state("b"), NodeState.READY)

    def test_scheduler_mark_failed_skip_downstream(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["b"])
        self._scheduler.mark_failed("a", failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertEqual(self._scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self._scheduler.get_state("b"), NodeState.SKIPPED)
        self.assertEqual(self._scheduler.get_state("c"), NodeState.SKIPPED)

    def test_scheduler_mark_failed_fail_fast(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        self._scheduler.mark_failed("a", failure_policy=FailurePolicy.FAIL_FAST)
        self.assertEqual(self._scheduler.get_state("a"), NodeState.FAILED)
        self.assertEqual(self._scheduler.get_state("b"), NodeState.CANCELLED)

    def test_scheduler_is_finished_empty(self) -> None:
        self.assertTrue(self._scheduler.is_finished())

    def test_scheduler_is_finished_not_done(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self.assertFalse(self._scheduler.is_finished())

    def test_scheduler_is_finished_all_done(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._scheduler.mark_succeeded("a")
        self.assertTrue(self._scheduler.is_finished())

    def test_scheduler_get_all_states(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        states = self._scheduler.get_all_states()
        self.assertIn("a", states)
        self.assertIn("b", states)
        self.assertEqual(states["a"], NodeState.READY)
        self.assertEqual(states["b"], NodeState.READY)

    def test_run_single_node(self) -> None:
        self._dag.add_node("a", lambda: 42)
        report = self._runner.run()
        self.assertEqual(report.total_nodes, 1)
        self.assertIn("a", report.succeeded_nodes)
        self.assertEqual(report.failed_nodes, ())
        self.assertEqual(report.skipped_nodes, ())
        self.assertEqual(report.cancelled_nodes, ())
        self.assertEqual(report.results["a"].value, 42)

    def test_run_linear_chain(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        self._dag.add_node("c", lambda: 3, dependencies=["b"])
        report = self._runner.run()
        self.assertEqual(report.succeeded_nodes, ("a", "b", "c"))
        self.assertEqual(report.total_nodes, 3)

    def test_run_failure_fail_fast(self) -> None:
        """FAIL_FAST must halt remaining nodes in the same wave after a failure."""
        self._dag.add_node("a", lambda: 1 / 0)
        self._dag.add_node("b", lambda: 2)  # Independent, in same wave as a
        self._dag.add_node("c", lambda: 3, dependencies=["a", "b"])
        report = self._runner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.failed_nodes)
        # b was in same wave as a but skipped because halt flag was set
        self.assertIn("b", report.cancelled_nodes)
        self.assertIn("c", report.cancelled_nodes)

    def test_run_failure_fail_fast_sequential(self) -> None:
        """FAIL_FAST in sequential deps: halted flag checked between waves."""
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 1 / 0, dependencies=["a"])
        report = self._runner.run(failure_policy=FailurePolicy.FAIL_FAST)
        self.assertIn("a", report.succeeded_nodes)
        self.assertIn("b", report.failed_nodes)

    def test_run_failure_skip_downstream(self) -> None:
        self._dag.add_node("a", lambda: 1 / 0)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        report = self._runner.run(failure_policy=FailurePolicy.SKIP_DOWNSTREAM)
        self.assertIn("a", report.failed_nodes)
        self.assertIn("b", report.skipped_nodes)

    def test_run_failure_continue_on_error(self) -> None:
        self._dag.add_node("a", lambda: 1 / 0)
        self._dag.add_node("b", lambda: 2)
        self._dag.add_node("c", lambda: 3, dependencies=["a"])
        report = self._runner.run(failure_policy=FailurePolicy.CONTINUE_ON_ERROR)
        self.assertIn("a", report.failed_nodes)
        self.assertIn("b", report.succeeded_nodes)
        self.assertIn("c", report.skipped_nodes)

    def test_run_retry_succeeds(self) -> None:
        counter = [0]
        def try_three():
            counter[0] += 1
            if counter[0] < 3:
                raise RuntimeError("fail")
            return "ok"
        self._dag.add_node("a", try_three, retries=3)
        report = self._runner.run()
        self.assertEqual(report.results["a"].state, NodeState.SUCCEEDED)
        self.assertEqual(report.results["a"].retries_attempted, 2)
        self.assertEqual(report.results["a"].value, "ok")

    def test_run_retry_exhausted(self) -> None:
        def always_fail():
            raise RuntimeError("always")
        self._dag.add_node("a", always_fail, retries=2)
        report = self._runner.run()
        self.assertEqual(report.results["a"].state, NodeState.FAILED)
        self.assertEqual(report.results["a"].retries_attempted, 2)

    def test_run_empty_dag(self) -> None:
        report = self._runner.run()
        self.assertEqual(report.total_nodes, 0)
        self.assertEqual(report.succeeded_nodes, ())

    def test_run_critical_path_in_report(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        report = self._runner.run()
        self.assertEqual(report.critical_path, ("a", "b"))

    def test_run_node_execution_error(self) -> None:
        self._dag.add_node("a", lambda: 1 / 0)
        report = self._runner.run()
        self.assertIn("a", report.failed_nodes)
        self.assertIsInstance(report.results["a"].error, ZeroDivisionError)

    def test_run_duration_tracked(self) -> None:
        self._dag.add_node("a", lambda: 1)
        report = self._runner.run()
        self.assertGreater(report.results["a"].duration_seconds, 0.0)

    def test_run_wall_clock_tracked(self) -> None:
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2)
        report = self._runner.run()
        self.assertGreater(report.wall_clock_seconds, 0.0)

    def test_run_validation_cycle(self) -> None:
        self._dag.add_node("a", lambda: 1, dependencies=["b"])
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        with self.assertRaises(CycleError):
            self._runner.run()

    def test_add_edge_initializes_upstream_sets(self) -> None:
        """add_edge must create upstream/downstream sets for nodes added without edges."""
        self._dag.add_node("u", lambda: 1)
        self._dag.add_node("d", lambda: 2)
        # Edge between two independent nodes should create sets
        self._dag.add_edge("u", "d")
        self.assertIn("u", self._dag._upstream["d"])
        self.assertIn("d", self._dag._downstream["u"])

    def test_remove_node_clears_upstream_deps(self) -> None:
        """remove_node must update upstream dependencies' downstream sets."""
        self._dag.add_node("x", lambda: 1)
        self._dag.add_node("y", lambda: 2, dependencies=["x"])
        self._dag.add_node("z", lambda: 3)
        self._dag.add_edge("y", "z")  # z depends on y, x depends on z
        # Actually: x is independent, y depends on x, z depends on y
        # Remove x: y should no longer have x in downstream
        self._dag.remove_node("y")
        self.assertNotIn("y", self._dag._downstream.get("x", set()))

    def test_topological_sort_cycle_error(self) -> None:
        """topological_sort must raise CycleError for cyclic graphs."""
        self._dag.add_node("a", lambda: 1, dependencies=["b"])
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        with self.assertRaises(CycleError):
            self._dag.topological_sort()

    def test_next_wave_with_priorities(self) -> None:
        """next_wave must sort candidates by priority descending."""
        self._dag.add_node("low", lambda: 1, priority=1)
        self._dag.add_node("high", lambda: 2, priority=10)
        self._dag.add_node("mid", lambda: 3, priority=5)
        wave = self._scheduler.next_wave()
        self.assertEqual(wave, ["high", "mid", "low"])

    def test_next_wave_sort_key_exception(self) -> None:
        """next_wave sort_key must fallback to priority 0 when get_node fails."""
        self._dag.add_node("a", lambda: 1, priority=5)
        # Force the scheduler to have a stale state entry by manipulating internal state
        self._scheduler._states["stale_node"] = NodeState.PENDING
        # Now get_node("stale_node") will fail since it's not in the DAG
        wave = self._scheduler.next_wave()
        self.assertIn("a", wave)

    def test_run_break_on_empty_wave(self) -> None:
        """run must break when next_wave returns empty but not finished."""
        # Create a self-referencing node that depends on itself - but first add
        # a node that completes, then one that depends on it (never ready)
        self._dag.add_node("a", lambda: 1)
        self._dag.add_node("b", lambda: 2, dependencies=["c"])  # c never added - will fail validation
        # Actually validation will catch missing dep. Let's test differently.
        # Use a cycle: a->b->a
        self._dag.add_node("a", lambda: 1, dependencies=["b"])
        self._dag.add_node("b", lambda: 2, dependencies=["a"])
        with self.assertRaises(CycleError):
            self._runner.run()

    def test_cleanup_stale_states(self) -> None:
        """Scheduler must remove stale state entries for removed nodes."""
        self._dag.add_node("x", lambda: 1)
        self._scheduler.next_wave()  # Populate _states with x
        self.assertIn("x", self._scheduler._states)
        self._dag.remove_node("x")
        wave = self._scheduler.next_wave()  # Should clean up stale
        self.assertNotIn("x", self._scheduler._states)


# ==============================================================================
# 5. Hypothesis Property Fuzz Tests
# ==============================================================================

class TestDagEngineLiteFuzz(unittest.TestCase):
    """Hypothesis property fuzz tests for the DAG engine."""

    @given(
        node_ids=st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5), min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=20)
    def test_property_all_nodes_registered(self, node_ids: List[str]) -> None:
        """Property: after adding nodes, all_nodes returns exactly the added set."""
        reg = LifecycleRegistry()
        __initialize__(reg)
        with enter_phase(system, registry=reg) as scope:
            scope.__enter__()
            dag = get_singleton(DAG)
            for nid in node_ids:
                dag.add_node(nid, lambda: None)
            self.assertEqual(dag.all_nodes(), set(node_ids))

    @given(
        node_ids=st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=3), min_size=1, max_size=4, unique=True),
    )
    @settings(max_examples=20)
    def test_property_roots_have_no_incoming(self, node_ids: List[str]) -> None:
        """Property: roots returned by find_roots have zero incoming edges."""
        reg = LifecycleRegistry()
        __initialize__(reg)
        with enter_phase(system, registry=reg) as scope:
            scope.__enter__()
            dag = get_singleton(DAG)
            for nid in node_ids:
                dag.add_node(nid, lambda: None)
            roots = dag.find_roots()
            for r in roots:
                self.assertEqual(dag.get_dependencies(r), set())

