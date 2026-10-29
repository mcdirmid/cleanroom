"""Pretense specifications and tests for loop_impl."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.loop.lib import cleaner, loop, node_cleaner, logger as loop_logger
from update_with_ai.parts.uv.lib import loop_impl, manifest_loader


# ==============================================================================
# 1. Pretense State Definitions
# ==============================================================================

@dataclass
class LoopState:
    dirty_nodes: Set[dag_storage.DagNode] = field(default_factory=set)
    feedback: Dict[dag_storage.DagNode, List[str]] = field(default_factory=dict)
    changes: Dict[dag_storage.DagNode, List[str]] = field(default_factory=dict)
    build_success: bool = True


class LoopStateMachine(StateMachine[LoopState]):
    """Pretense StateMachine for Loop."""

    def __init__(self, state: Optional[LoopState] = None):
        super().__init__(state=state or LoopState())

    # ==============================================================================
    # 2. Loop Transitions
    # ==============================================================================

    @transition(loop.Loop.clean_subgraph)
    def clean_subgraph(
        self,
        ctx: TransitionContext[loop.Loop, [dag_storage.DagNode], loop.BuildResult],
    ) -> None:
        ctx.arguments(target=Domain(strategy=lambda: dag_storage.DagNode(dag_storage.UnitAddress('//pkg/unit'), dag_storage.RoleAddress('lib'))))
        def _returns(target: Optional[dag_storage.DagNode] = None) -> loop.BuildResult:
            summary = "Cleaning pass succeeded" if self.state.build_success else "Cleaning pass failed"
            return loop.BuildResult(success=self.state.build_success, summary=loop.BuildSummary(summary))
        ctx.returns(_returns)

        def _consequent(res: loop.BuildResult, target: Optional[dag_storage.DagNode] = None) -> None:
            if self.state.build_success and target is not None:
                self.state.dirty_nodes.discard(target)
        ctx.update(_consequent)

    @transition(loop.Loop.mark_dirty)
    def mark_dirty(
        self,
        ctx: TransitionContext[loop.Loop, [dag_storage.DagNode, Optional[dag_storage.ChangeMessage]], None],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: dag_storage.DagNode(dag_storage.UnitAddress('//pkg/unit'), dag_storage.RoleAddress('lib'))),
                    message=Domain(strategy=lambda: None),
                )
        def _consequent(res: None, target: Optional[dag_storage.DagNode] = None, message: Optional[dag_storage.ChangeMessage] = None) -> None:
            if target is not None:
                self.state.dirty_nodes.add(target)
        ctx.update(_consequent)


proto = LoopStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_loop_fake(state: Optional[LoopState] = None) -> loop.Loop:
    """Instantiate a synthesized Loop fake."""
    sm = LoopStateMachine(state)
    return sm.as_fake(loop.Loop)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestLoopUnit(unittest.TestCase):
    """Unit tests for synthesized Loop fake."""

    def setUp(self) -> None:
        self.state = LoopState()
        self.fake = make_loop_fake(self.state)
        self.target = dag_storage.DagNode(dag_storage.UnitAddress("//parts/foo"), dag_storage.RoleAddress("lib"))

    def test_clean_and_mark_dirty(self) -> None:
        self.fake.mark_dirty(self.target, dag_storage.ChangeMessage(dag_storage.MessageContent("reason")))
        self.assertIn(self.target, self.state.dirty_nodes)
        result = self.fake.clean_subgraph(self.target)
        self.assertTrue(result.success)
        self.assertNotIn(self.target, self.state.dirty_nodes)


class DummyRunnerLogger(loop_logger.RunnerLogger):
    tier = system
    def __init__(self) -> None:
        self.events: list[loop_logger.RunnerLogEvent] = []
    def consume(self, event: loop_logger.RunnerLogEvent) -> None:
        self.events.append(event)


class DummyManifestLoader(manifest_loader.UvManifestLoader):
    tier = system
    def __init__(self) -> None:
        self.loaded: list[dag_storage.DagNode] = []
    def load_manifest(self, node: dag_storage.DagNode) -> None:
        self.loaded.append(node)
    def retrieve_manifest(self, node: dag_storage.DagNode) -> Optional[manifest_loader.TargetManifest]:
        return None


class DummyCleaner(cleaner.LoopCleaner):
    tier = system
    def __init__(self, succeed: bool = True) -> None:
        self.succeed = succeed
    def clean(self, target: dag_storage.DagNode, node_cleaner: node_cleaner.NodeCleaner) -> bool:
        return self.succeed


class DummyNodeCleaner(node_cleaner.NodeCleaner):
    tier = system
    def clean_node(self, target: dag_storage.DagNode) -> bool:
        return True


class DummyDagStorage(dag_storage.DagStorage):
    tier = system
    def __init__(self) -> None:
        self.dirty_nodes: Set[dag_storage.DagNode] = set()
        self.messages: dict[dag_storage.DagNode, list[dag_storage.DagMessage]] = {}
        self.dependencies_map: dict[dag_storage.DagNode, Set[dag_storage.DagDependency]] = {}
        self.materialized: list[dag_storage.DagNode] = []
        self.cleaned: list[dag_storage.DagNode] = []

    def get_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagDependency]:
        return self.dependencies_map.get(node, set())

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        return set(self.messages.get(node, []))

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self.dirty_nodes

    def add_message(self, message: dag_storage.DagMessage, to: dag_storage.DagNode) -> None:
        self.messages.setdefault(to, []).append(message)
        self.dirty_nodes.add(to)

    def add_feedback_message(self, node: dag_storage.DagNode, message: dag_storage.FeedbackMessage) -> None:
        self.messages.setdefault(node, []).append(message)
        self.dirty_nodes.add(node)

    def mark_node_dirty(self, node: dag_storage.DagNode, reason: Optional[str] = None) -> None:
        self.dirty_nodes.add(node)

    def mark_node_clean(self, node: dag_storage.DagNode, change_description: Optional[dag_storage.ChangeDescription] = None) -> None:
        self.dirty_nodes.discard(node)
        self.cleaned.append(node)

    def materialize_template(self, node: dag_storage.DagNode) -> None:
        self.materialized.append(node)


class TestLoopImplReal(unittest.TestCase):
    """Direct unit tests for loop_impl.py."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        loop_impl.__initialize__(self.registry)
        self.registry.register_singleton(DummyRunnerLogger, keys=[loop_logger.RunnerLogger], tier=system)
        self.registry.register_singleton(DummyManifestLoader, keys=[manifest_loader.UvManifestLoader], tier=system)
        self.registry.register_singleton(DummyCleaner, keys=[cleaner.LoopCleaner], tier=system)
        self.registry.register_singleton(DummyNodeCleaner, keys=[node_cleaner.NodeCleaner], tier=system)
        self.registry.register_singleton(DummyDagStorage, keys=[dag_storage.DagStorage], tier=system)

        self.phase_cm = enter_phase(system, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.loop = self.scope.get_singleton(loop.Loop)
        self.storage = self.scope.get_singleton(dag_storage.DagStorage)
        self.target = dag_storage.DagNode(dag_storage.UnitAddress("//pkg/unit"), dag_storage.RoleAddress("lib"))

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_clean_subgraph_success(self) -> None:
        result = self.loop.clean_subgraph(self.target)
        self.assertTrue(result.success)
        self.assertIn("Cleaning pass succeeded", result.summary)

    def test_mark_subgraph_clean(self) -> None:
        self.loop.mark_subgraph_clean(self.target)
        self.assertIn(self.target, getattr(self.storage, "materialized"))

    def test_mark_dirty(self) -> None:
        msg = dag_storage.ChangeMessage(dag_storage.MessageContent("reason"))
        self.loop.mark_dirty(self.target, msg)
        self.assertTrue(self.storage.is_dirty(self.target))

    def test_inject_feedback_and_record_change(self) -> None:
        fb = dag_storage.FeedbackMessage(dag_storage.MessageContent("feedback"))
        self.loop.inject_feedback(self.target, fb)
        ch = dag_storage.ChangeMessage(dag_storage.MessageContent("change"))
        self.loop.record_change(self.target, ch)
        self.assertTrue(self.storage.is_dirty(self.target))
