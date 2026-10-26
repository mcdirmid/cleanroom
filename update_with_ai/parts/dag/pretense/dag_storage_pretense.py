"""Pretense State Machine and Fake Synthesis for DagStorage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Set, Tuple

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachine, StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib.dag_storage import (
    DagDependency,
    DagMessage,
    DagNode,
    DagStorage,
    RoleAddress,
    UnitAddress,
)


@dataclass
class DagStorageState:
    """Canonical model state for graph storage."""
    nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    dependencies: PretenseDict[DagNode, Set[DagDependency]] = field(default_factory=PretenseDict)
    dirty_nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    messages: PretenseDict[DagNode, Set[DagMessage]] = field(default_factory=PretenseDict)


proto = StateMachineProto[DagStorageState]()


# ==============================================================================
# 1. DagStorage Interface Transitions
# ==============================================================================

@proto.transition(DagStorage.get_dependencies)
def get_dependencies(): pass

@get_dependencies.arguments
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.nodes:
            return None
        return (list(state.nodes)[0],)
    return (node,)

@get_dependencies.returns
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[Set[DagDependency]]]:
    expected = set(state.dependencies.get(node, set()))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(DagStorage.get_messages)
def get_messages(): pass

@get_messages.arguments
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.nodes:
            return None
        return (list(state.nodes)[0],)
    return (node,)

@get_messages.returns
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[Set[DagMessage]]]:
    expected = set(state.messages.get(node, set()))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(DagStorage.is_dirty)
def is_dirty(): pass

@is_dirty.arguments
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.nodes:
            return None
        return (list(state.nodes)[0],)
    return (node,)

@is_dirty.returns
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    expected = node in state.dirty_nodes
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 2. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_node(): pass

@seed_node.arguments
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    is_dirty: bool | NotBoundType = NotBound,
    dependencies: Optional[Set[DagDependency]] | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, bool, Optional[Set[DagDependency]]]]:
    if isinstance(node, NotBoundType):
        resolved_node = DagNode(UnitAddress(f"//unit_{len(state.nodes)}"), RoleAddress("cleanroom:lib"))
    else:
        resolved_node = node
    resolved_dirty = False if isinstance(is_dirty, NotBoundType) else is_dirty
    resolved_deps = None if isinstance(dependencies, NotBoundType) else dependencies
    return (resolved_node, resolved_dirty, resolved_deps)

@seed_node.provide
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode,
    is_dirty: bool,
    dependencies: Optional[Set[DagDependency]],
    result: None = None,
) -> None:
    state.nodes.add(node)
    if is_dirty:
        state.dirty_nodes.add(node)
    else:
        state.dirty_nodes.discard(node)

    if dependencies is not None:
        state.dependencies[node] = set(dependencies)
        for dep in dependencies:
            state.nodes.add(dep.node)


@proto.seeding()
def seed_dirty_status(): pass

@seed_dirty_status.arguments
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    dirty: bool | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, bool]]:
    if isinstance(node, NotBoundType) or isinstance(dirty, NotBoundType):
        return None
    return (node, dirty)

@seed_dirty_status.provide
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode,
    dirty: bool,
    result: None = None,
) -> None:
    state.nodes.add(node)
    if dirty:
        state.dirty_nodes.add(node)
    else:
        state.dirty_nodes.discard(node)


@proto.seeding()
def seed_message(): pass

@seed_message.arguments
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    message: DagMessage | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, DagMessage]]:
    if isinstance(node, NotBoundType) or isinstance(message, NotBoundType):
        return None
    return (node, message)

@seed_message.provide
def _(
    state: DagStorageState,
    this: Any,
    node: DagNode,
    message: DagMessage,
    result: None = None,
) -> None:
    state.nodes.add(node)
    if node not in state.messages:
        state.messages[node] = set()
    state.messages[node].add(message)


def make_dag_storage_fake(
    initial_state: Optional[DagStorageState] = None,
) -> tuple[StateMachine[DagStorageState], DagStorage]:
    """Helper creating a configured DagStorage fake and its driving state machine."""
    sm = proto.make_state_machine(initial_state or DagStorageState())
    fake = sm.as_fake(dag_storage.DagStorage)
    return sm, fake
