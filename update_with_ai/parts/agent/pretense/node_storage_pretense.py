"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AgentStorage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.agent.lib.node_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.dag.lib.dag_storage import (
    DagDependency,
    DagMessage,
    DagNode,
    RoleAddress,
    UnitAddress,
)


@dataclass
class AgentStorageState:
    """Canonical model state for AgentStorage."""
    nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    dependencies: PretenseDict[DagNode, Set[DagDependency]] = field(default_factory=PretenseDict)
    dirty_nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    messages: PretenseDict[DagNode, Set[DagMessage]] = field(default_factory=PretenseDict)
    node_definitions: PretenseDict[DagNode, NodeDefinition] = field(default_factory=PretenseDict)
    task_prompts: PretenseDict[DagNode, TaskPrompt] = field(default_factory=PretenseDict)


proto = StateMachineProto[AgentStorageState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_node(): pass

@seed_node.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    is_dirty: bool | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, bool]]:
    n = DagNode(UnitAddress("target"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    dirty = False if isinstance(is_dirty, NotBoundType) else bool(is_dirty)
    return (n, dirty)

@seed_node.provide
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode,
    is_dirty: bool,
    result: None = None,
) -> None:
    state.nodes.add(node)
    if is_dirty:
        state.dirty_nodes.add(node)
    else:
        state.dirty_nodes.discard(node)


@proto.seeding()
def seed_node_definition(): pass

@seed_node_definition.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    task_prompt: str | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, TaskPrompt]]:
    n = DagNode(UnitAddress("target"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    prompt = TaskPrompt("Clean the target node" if isinstance(task_prompt, NotBoundType) else str(task_prompt))
    return (n, prompt)

@seed_node_definition.provide
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode,
    task_prompt: TaskPrompt,
    result: None = None,
) -> None:
    state.nodes.add(node)
    state.task_prompts[node] = task_prompt
    state.node_definitions[node] = NodeDefinition(task_prompt=task_prompt)


# ==============================================================================
# 2. AgentStorage Transitions
# ==============================================================================

@proto.transition(AgentStorage.get_dependencies)
def get_dependencies(): pass

@get_dependencies.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.nodes:
            return None
        return (next(iter(state.nodes)),)
    return (node,)

@get_dependencies.returns
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[Sequence[DagDependency]]]:
    expected = tuple(state.dependencies.get(node, set()))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AgentStorage.get_messages)
def get_messages(): pass

@get_messages.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.nodes:
            return None
        return (next(iter(state.nodes)),)
    return (node,)

@get_messages.returns
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[Sequence[DagMessage]]]:
    expected = tuple(state.messages.get(node, set()))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AgentStorage.is_dirty)
def is_dirty(): pass

@is_dirty.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.nodes:
            return None
        return (next(iter(state.nodes)),)
    return (node,)

@is_dirty.returns
def _(
    state: AgentStorageState,
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


@proto.transition(AgentStorage.get_node_definition)
def get_node_definition(): pass

@get_node_definition.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.node_definitions:
            return None
        return (next(iter(state.node_definitions.keys())),)
    return (node,)

@get_node_definition.returns
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[NodeDefinition]]:
    expected = state.node_definitions.get(node, NodeDefinition(task_prompt=TaskPrompt("default prompt")))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AgentStorage.get_task_prompt)
def get_task_prompt(): pass

@get_task_prompt.arguments
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.task_prompts:
            return None
        return (next(iter(state.task_prompts.keys())),)
    return (node,)

@get_task_prompt.returns
def _(
    state: AgentStorageState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[TaskPrompt]]:
    expected = state.task_prompts.get(node, TaskPrompt("default prompt"))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_agent_storage_fake(state: Optional[AgentStorageState] = None) -> AgentStorage:
    """Instantiate a synthesized AgentStorage fake with Pretense."""
    st = state or AgentStorageState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(AgentStorage)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestAgentStorageUnit(unittest.TestCase):
    """Unit tests for synthesized AgentStorage fake."""

    def setUp(self) -> None:
        self.state = AgentStorageState()
        self.sm = proto.make_state_machine(self.state)
        self.node = DagNode(UnitAddress("target"), RoleAddress("lib"))
        self.sm.seed_node(self.node, is_dirty=True)
        self.sm.seed_node_definition(self.node, task_prompt="Implement feature X")
        self.fake: AgentStorage = self.sm.as_fake(AgentStorage)

    def test_is_dirty(self) -> None:
        self.assertTrue(self.fake.is_dirty(self.node))
        clean_node = DagNode(UnitAddress("clean_unit"), RoleAddress("lib"))
        self.assertFalse(self.fake.is_dirty(clean_node))

    def test_get_task_prompt(self) -> None:
        self.assertEqual(self.fake.get_task_prompt(self.node), "Implement feature X")

    def test_get_node_definition(self) -> None:
        defn = self.fake.get_node_definition(self.node)
        self.assertEqual(defn.task_prompt, "Implement feature X")


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestAgentStorageFuzz(unittest.TestCase):
    """Property fuzz tests for AgentStorage state and transitions."""

    @settings(max_examples=30)
    @given(
        prompts=st.lists(st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _"), min_size=1, max_size=6),
        dirty_flags=st.lists(st.booleans(), min_size=1, max_size=6),
    )
    def test_storage_invariants_under_fuzz(self, prompts: list[str], dirty_flags: list[bool]) -> None:
        state = AgentStorageState()
        sm = proto.make_state_machine(state)

        for i, (prompt, dirty) in enumerate(zip(prompts, dirty_flags)):
            node = DagNode(UnitAddress(f"unit_{i}"), RoleAddress("lib"))
            sm.seed_node(node, is_dirty=dirty)
            sm.seed_node_definition(node, task_prompt=prompt)

        fake = sm.as_fake(AgentStorage)

        for i, (prompt, dirty) in enumerate(zip(prompts, dirty_flags)):
            node = DagNode(UnitAddress(f"unit_{i}"), RoleAddress("lib"))
            self.assertEqual(fake.is_dirty(node), dirty)
            self.assertEqual(fake.get_task_prompt(node), prompt)
            self.assertEqual(fake.get_node_definition(node).task_prompt, prompt)
