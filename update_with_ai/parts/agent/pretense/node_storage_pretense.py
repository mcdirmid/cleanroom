"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AgentStorage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
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


class AgentStorageStateMachine(StateMachine[AgentStorageState]):
    """Pretense StateMachine for AgentStorage."""

    def __init__(self, state: Optional[AgentStorageState] = None):
        super().__init__(state=state or AgentStorageState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_node(
        self,
        ctx: TransitionContext[None, [DagNode, bool], None],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress('target'), RoleAddress('lib'))),
                    is_dirty=Domain(strategy=lambda: False),
                )
        def _consequent(res: None, node: DagNode = DagNode(UnitAddress("target"), RoleAddress("lib")), is_dirty: bool = False) -> None:
            self.state.nodes.add(node)
            if is_dirty:
                self.state.dirty_nodes.add(node)
            else:
                self.state.dirty_nodes.discard(node)
        ctx.update(_consequent)

    @transition.seeding()
    def seed_node_definition(
        self,
        ctx: TransitionContext[None, [DagNode, str], None],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress('target'), RoleAddress('lib'))),
                    task_prompt=Domain(strategy=lambda: 'Clean the target node'),
                )
        def _consequent(res: None, node: DagNode = DagNode(UnitAddress("target"), RoleAddress("lib")), task_prompt: str = "Clean the target node") -> None:
            self.state.nodes.add(node)
            prompt = TaskPrompt(str(task_prompt))
            self.state.task_prompts[node] = prompt
            self.state.node_definitions[node] = NodeDefinition(task_prompt=prompt)
        ctx.update(_consequent)

    # ==============================================================================
    # 2. AgentStorage Transitions
    # ==============================================================================

    @transition(AgentStorage.get_dependencies)
    def get_dependencies(
        self,
        ctx: TransitionContext[AgentStorage, [DagNode], Sequence[DagDependency]],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: next(iter(self.state.nodes))))
        ctx.returns(lambda node: tuple(self.state.dependencies.get(node, set())))

    @transition(AgentStorage.get_messages)
    def get_messages(
        self,
        ctx: TransitionContext[AgentStorage, [DagNode], Sequence[DagMessage]],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: next(iter(self.state.nodes))))
        ctx.returns(lambda node: tuple(self.state.messages.get(node, set())))

    @transition(AgentStorage.is_dirty)
    def is_dirty(
        self,
        ctx: TransitionContext[AgentStorage, [DagNode], bool],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: next(iter(self.state.nodes))))
        ctx.returns(lambda node: node in self.state.dirty_nodes)

    @transition(AgentStorage.get_node_definition)
    def get_node_definition(
        self,
        ctx: TransitionContext[AgentStorage, [DagNode], NodeDefinition],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: next(iter(self.state.node_definitions.keys()))))
        ctx.returns(lambda node: self.state.node_definitions.get(node, NodeDefinition(task_prompt=TaskPrompt("default prompt"))))

    @transition(AgentStorage.get_task_prompt)
    def get_task_prompt(
        self,
        ctx: TransitionContext[AgentStorage, [DagNode], TaskPrompt],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: next(iter(self.state.task_prompts.keys()))))
        ctx.returns(lambda node: self.state.task_prompts.get(node, TaskPrompt("default prompt")))


proto = AgentStorageStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_agent_storage_fake(state: Optional[AgentStorageState] = None) -> AgentStorage:
    """Instantiate a synthesized AgentStorage fake with Pretense."""
    sm = AgentStorageStateMachine(state)
    return sm.as_fake(AgentStorage)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestAgentStorageUnit(unittest.TestCase):
    """Unit tests for synthesized AgentStorage fake."""

    def setUp(self) -> None:
        self.state = AgentStorageState()
        self.sm = AgentStorageStateMachine(self.state)
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
        sm = AgentStorageStateMachine(state)

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
