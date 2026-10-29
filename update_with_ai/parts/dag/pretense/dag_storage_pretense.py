"""Pretense State Machine and Fake Synthesis for DagStorage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Set, Tuple

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib.dag_storage import (
    ChangeMessage,
    DagDependency,
    DagMessage,
    DagNode,
    DagStorage,
    MessageContent,
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


class DagStorageStateMachine(StateMachine[DagStorageState]):
    """State machine for graph storage."""

    def __init__(
        self,
        state: Optional[DagStorageState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagStorageState(), singletons=singletons)

    @transition(DagStorage.get_dependencies)
    def get_dependencies(self, ctx: TransitionContext[DagStorage, [DagNode], Set[DagDependency]]) -> None:
        ctx.arguments(node=Domain(strategy=lambda: (list(self.state.nodes)[0],) if self.state.nodes else None))
        ctx.returns(lambda node: set(self.state.dependencies.get(node, set())))
        ctx.update(lambda res, node: None)

    @transition(DagStorage.get_messages)
    def get_messages(self, ctx: TransitionContext[DagStorage, [DagNode], Set[DagMessage]]) -> None:
        ctx.arguments(node=Domain(strategy=lambda: (list(self.state.nodes)[0],) if self.state.nodes else None))
        ctx.returns(lambda node: set(self.state.messages.get(node, set())))
        ctx.update(lambda res, node: None)

    @transition(DagStorage.is_dirty)
    def is_dirty(self, ctx: TransitionContext[DagStorage, [DagNode], bool]) -> None:
        ctx.arguments(node=Domain(strategy=lambda: (list(self.state.nodes)[0],) if self.state.nodes else None))
        ctx.returns(lambda node: node in self.state.dirty_nodes)
        ctx.update(lambda res, node: None)

    @transition.seeding(name="seed_node")
    def seed_node(
        self,
        ctx: TransitionContext[Any, [DagNode, bool, Optional[Set[DagDependency]]], None],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress(f'//unit_{len(self.state.nodes)}'), RoleAddress('cleanroom:lib'))),
                    is_dirty=Domain(strategy=lambda: False),
                    dependencies=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda node=None, is_dirty=False, dependencies=None: None)
        def _seed(node: Any, dirty: bool, deps: Any) -> None:
            resolved_node = node or DagNode(UnitAddress(f"//unit_{len(self.state.nodes)}"), RoleAddress("cleanroom:lib"))
            self.state.nodes.add(resolved_node)
            if dirty:
                self.state.dirty_nodes.add(resolved_node)
            else:
                self.state.dirty_nodes.discard(resolved_node)
            if deps is not None:
                self.state.dependencies[resolved_node] = set(deps)
                for dep in deps:
                    self.state.nodes.add(dep.node)
        ctx.update(lambda res, node=None, is_dirty=False, dependencies=None: _seed(node, is_dirty, dependencies))

    @transition.seeding(name="seed_dirty_status")
    def seed_dirty_status(self, ctx: TransitionContext[Any, [DagNode, bool], None]) -> None:
        ctx.arguments(
            node=Domain(strategy=lambda: list(self.state.nodes)[0] if self.state.nodes else DagNode(UnitAddress("//default"), RoleAddress("cleanroom:lib"))),
            dirty=Domain.boolean(),
        )
        ctx.returns(lambda node, dirty: None)
        def _seed_dirty(node: DagNode, dirty: bool) -> None:
            self.state.nodes.add(node)
            if dirty:
                self.state.dirty_nodes.add(node)
            else:
                self.state.dirty_nodes.discard(node)
        ctx.update(lambda res, node, dirty: _seed_dirty(node, dirty))

    @transition.seeding(name="seed_message")
    def seed_message(self, ctx: TransitionContext[Any, [DagNode, DagMessage], None]) -> None:
        ctx.arguments(
            node=Domain(strategy=lambda: list(self.state.nodes)[0] if self.state.nodes else DagNode(UnitAddress("//default"), RoleAddress("cleanroom:lib"))),
            message=Domain(strategy=lambda: ChangeMessage(MessageContent("test message"))),
        )
        ctx.returns(lambda node, message: None)
        def _seed_msg(node: DagNode, message: DagMessage) -> None:
            self.state.nodes.add(node)
            if node not in self.state.messages:
                self.state.messages[node] = set()
            self.state.messages[node].add(message)
        ctx.update(lambda res, node, message: _seed_msg(node, message))


proto = DagStorageStateMachine()


def make_dag_storage_fake(
    initial_state: Optional[DagStorageState] = None,
) -> tuple[StateMachine[DagStorageState], DagStorage]:
    """Helper creating a configured DagStorage fake and its driving state machine."""
    sm = DagStorageStateMachine(state=initial_state or DagStorageState())
    fake = sm.as_fake(dag_storage.DagStorage)
    return sm, fake
