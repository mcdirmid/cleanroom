"""Pretense state machines, fake synthesis, unit tests, and fuzzing for RoleConfig and NodeConfig."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.agent.lib import file_alias, node_config
from update_with_ai.parts.agent.lib.node_config import (
    ExecutionVersion,
    GuideSummary,
    NodeConfig,
    NodeFeedback,
    NodeGuide,
    PerNodeInfo,
    RoleConfig,
    RoleName,
    StepContent,
    StepIndex,
    StepSection,
    StepTitle,
    TemplateParamKey,
    VerificationCheck,
    VerificationDiagnostic,
    VerificationSuccessMessage,
)
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


# ==============================================================================
# 1. RoleConfig State Machine
# ==============================================================================

@dataclass
class RoleConfigState:
    """Canonical model state for RoleConfig."""
    role: str = "lib"
    nodes: List[DagNode] = field(default_factory=list)
    version: int = 1


class RoleConfigStateMachine(StateMachine[RoleConfigState]):
    """Pretense StateMachine for RoleConfig."""

    def __init__(self, state: Optional[RoleConfigState] = None):
        super().__init__(state=state or RoleConfigState())

    @transition.seeding()
    def seed_role_config(
        self,
        ctx: TransitionContext[None, [str, Optional[Sequence[DagNode]], int], None],
    ) -> None:
        ctx.arguments(
                    role=Domain(strategy=lambda: 'lib'),
                    nodes=Domain(strategy=lambda: ()),
                    version=Domain(strategy=lambda: 1),
                )
        def _consequent(res: None, role: str = "lib", nodes: Optional[Sequence[DagNode]] = None, version: int = 1) -> None:
            self.state.role = role
            self.state.nodes = list(nodes or ())
            self.state.version = version
        ctx.update(_consequent)

    @transition(name="role")
    def role(
        self,
        ctx: TransitionContext[RoleConfig, [], RoleName],
    ) -> None:
        ctx.returns(lambda: RoleName(self.state.role))

    @transition(name="nodes")
    def nodes(
        self,
        ctx: TransitionContext[RoleConfig, [], Sequence[DagNode]],
    ) -> None:
        ctx.returns(lambda: tuple(self.state.nodes))

    @transition(name="version")
    def version(
        self,
        ctx: TransitionContext[RoleConfig, [], ExecutionVersion],
    ) -> None:
        ctx.returns(lambda: ExecutionVersion(self.state.version))

    @transition(RoleConfig.set_role)
    def set_role(
        self,
        ctx: TransitionContext[RoleConfig, [RoleName | str], None],
    ) -> None:
        ctx.arguments(role=Domain(strategy=lambda: RoleName('test')))
        ctx.update(lambda res, role=RoleName("test"): setattr(self.state, "role", str(role)))

    @transition(RoleConfig.set_nodes)
    def set_nodes(
        self,
        ctx: TransitionContext[RoleConfig, [Sequence[DagNode]], None],
    ) -> None:
        ctx.arguments(nodes=Domain(strategy=lambda: ()))
        def _consequent(res: None, nodes: Sequence[DagNode] = ()) -> None:
            self.state.nodes = list(nodes)
            self.state.version += 1
        ctx.update(_consequent)


role_proto = RoleConfigStateMachine()


# ==============================================================================
# 2. NodeConfig State Machine
# ==============================================================================

@dataclass
class NodeConfigState:
    """Canonical model state for NodeConfig."""
    read_only_files: PretenseSet[file_alias.ReadOnlyFile] = field(default_factory=PretenseSet)
    read_write_files: PretenseSet[file_alias.ReadWriteFile] = field(default_factory=PretenseSet)
    allows_step_mode: bool = False
    is_step_mode: bool = False
    guide_file: Optional[file_alias.UnboundFile] = None
    templates: PretenseDict[file_alias.BoundFile, file_alias.FileContent] = field(default_factory=PretenseDict)
    template_parameters: PretenseDict[TemplateParamKey, Any] = field(default_factory=PretenseDict)
    guide: Optional[NodeGuide] = None
    blame_targets_by_node: PretenseDict[DagNode, PretenseSet[file_alias.BoundFile]] = field(default_factory=PretenseDict)
    verification_checks: List[VerificationCheck] = field(default_factory=list)
    verification_checks_by_node: PretenseDict[DagNode, List[VerificationCheck]] = field(default_factory=PretenseDict)
    src_file_alias_by_node: PretenseDict[DagNode, file_alias.RelativePath] = field(default_factory=PretenseDict)
    verification_success_message: Optional[VerificationSuccessMessage] = None
    feedback: List[NodeFeedback] = field(default_factory=list)
    per_node_info_by_node: PretenseDict[DagNode, PerNodeInfo] = field(default_factory=PretenseDict)


class NodeConfigStateMachine(StateMachine[NodeConfigState]):
    """Pretense StateMachine for NodeConfig."""

    def __init__(self, state: Optional[NodeConfigState] = None):
        super().__init__(state=state or NodeConfigState())

    @transition.seeding()
    def seed_node_config(
        self,
        ctx: TransitionContext[
            None,
            [
                Optional[Set[file_alias.ReadOnlyFile]],
                Optional[Set[file_alias.ReadWriteFile]],
                bool,
                bool,
                Optional[file_alias.UnboundFile],
                Optional[str],
                Optional[Sequence[str]],
            ],
            None,
        ],
    ) -> None:
        ctx.arguments(
                    read_only_files=Domain(strategy=lambda: set()),
                    read_write_files=Domain(strategy=lambda: set()),
                    allows_step_mode=Domain(strategy=lambda: False),
                    is_step_mode=Domain(strategy=lambda: False),
                    guide_file=Domain(strategy=lambda: None),
                    verification_success_message=Domain(strategy=lambda: None),
                    feedback=Domain(strategy=lambda: ()),
                )
        def _consequent(
            res: None,
            read_only_files: Optional[Set[file_alias.ReadOnlyFile]] = None,
            read_write_files: Optional[Set[file_alias.ReadWriteFile]] = None,
            allows_step_mode: bool = False,
            is_step_mode: bool = False,
            guide_file: Optional[file_alias.UnboundFile] = None,
            verification_success_message: Optional[str] = None,
            feedback: Optional[Sequence[str]] = None,
        ) -> None:
            self.state.read_only_files = PretenseSet(read_only_files or ())
            self.state.read_write_files = PretenseSet(read_write_files or ())
            self.state.allows_step_mode = bool(allows_step_mode)
            self.state.is_step_mode = bool(is_step_mode)
            self.state.guide_file = guide_file
            self.state.verification_success_message = VerificationSuccessMessage(str(verification_success_message)) if verification_success_message else None
            self.state.feedback = [NodeFeedback(f) for f in (feedback or ())]
        ctx.update(_consequent)

    @transition(name="read_only_files")
    def read_only_files(self, ctx: TransitionContext[NodeConfig, [], Set[file_alias.ReadOnlyFile]]) -> None:
        ctx.returns(lambda: set(self.state.read_only_files))

    @transition(name="read_write_files")
    def read_write_files(self, ctx: TransitionContext[NodeConfig, [], Set[file_alias.ReadWriteFile]]) -> None:
        ctx.returns(lambda: set(self.state.read_write_files))

    @transition(name="allows_step_mode")
    def allows_step_mode(self, ctx: TransitionContext[NodeConfig, [], bool]) -> None:
        ctx.returns(lambda: self.state.allows_step_mode)

    @transition(name="is_step_mode")
    def is_step_mode(self, ctx: TransitionContext[NodeConfig, [], bool]) -> None:
        ctx.returns(lambda: self.state.is_step_mode)

    @transition(name="guide_file")
    def guide_file(self, ctx: TransitionContext[NodeConfig, [], Optional[file_alias.UnboundFile]]) -> None:
        ctx.returns(lambda: self.state.guide_file)

    @transition(name="templates")
    def templates(self, ctx: TransitionContext[NodeConfig, [], Mapping[file_alias.BoundFile, file_alias.FileContent]]) -> None:
        ctx.returns(lambda: dict(self.state.templates))

    @transition(name="template_parameters")
    def template_parameters(self, ctx: TransitionContext[NodeConfig, [], Mapping[TemplateParamKey, Any]]) -> None:
        ctx.returns(lambda: dict(self.state.template_parameters))

    @transition(name="guide")
    def guide(self, ctx: TransitionContext[NodeConfig, [], Optional[NodeGuide]]) -> None:
        ctx.returns(lambda: self.state.guide)

    @transition(name="blame_targets_by_node")
    def blame_targets_by_node(self, ctx: TransitionContext[NodeConfig, [], Mapping[DagNode, Set[file_alias.BoundFile]]]) -> None:
        ctx.returns(lambda: {k: set(v) for k, v in self.state.blame_targets_by_node.items()})

    @transition(name="verification_checks")
    def verification_checks(self, ctx: TransitionContext[NodeConfig, [], Sequence[VerificationCheck]]) -> None:
        ctx.returns(lambda: tuple(self.state.verification_checks))

    @transition(name="verification_checks_by_node")
    def verification_checks_by_node(self, ctx: TransitionContext[NodeConfig, [], Mapping[DagNode, Sequence[VerificationCheck]]]) -> None:
        ctx.returns(lambda: {k: tuple(v) for k, v in self.state.verification_checks_by_node.items()})

    @transition(name="src_file_alias_by_node")
    def src_file_alias_by_node(self, ctx: TransitionContext[NodeConfig, [], Mapping[DagNode, file_alias.RelativePath]]) -> None:
        ctx.returns(lambda: dict(self.state.src_file_alias_by_node))

    @transition(name="verification_success_message")
    def verification_success_message(self, ctx: TransitionContext[NodeConfig, [], Optional[VerificationSuccessMessage]]) -> None:
        ctx.returns(lambda: self.state.verification_success_message)

    @transition(name="feedback")
    def feedback(self, ctx: TransitionContext[NodeConfig, [], Sequence[NodeFeedback]]) -> None:
        ctx.returns(lambda: tuple(self.state.feedback))

    @transition(name="per_node_info_by_node")
    def per_node_info_by_node(self, ctx: TransitionContext[NodeConfig, [], Mapping[DagNode, PerNodeInfo]]) -> None:
        ctx.returns(lambda: dict(self.state.per_node_info_by_node))


node_proto = NodeConfigStateMachine()


# ==============================================================================
# 3. Helper Factories
# ==============================================================================

def make_role_config_fake(state: Optional[RoleConfigState] = None) -> RoleConfig:
    """Instantiate a synthesized RoleConfig fake."""
    sm = RoleConfigStateMachine(state)
    return sm.as_fake(RoleConfig)


def make_node_config_fake(state: Optional[NodeConfigState] = None) -> NodeConfig:
    """Instantiate a synthesized NodeConfig fake."""
    sm = NodeConfigStateMachine(state)
    return sm.as_fake(NodeConfig)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestRoleConfigUnit(unittest.TestCase):
    """Unit tests for synthesized RoleConfig fake."""

    def test_default_role_config(self) -> None:
        fake = make_role_config_fake()
        self.assertEqual(fake.role, "lib")
        self.assertEqual(fake.nodes, ())
        self.assertEqual(fake.version, 1)

    def test_set_role_and_nodes_increments_version(self) -> None:
        fake = make_role_config_fake()
        fake.set_role(RoleName("test"))
        self.assertEqual(fake.role, "test")
        self.assertEqual(fake.version, 1)

        node = DagNode(UnitAddress("core"), RoleAddress("lib"))
        fake.set_nodes([node])
        self.assertEqual(fake.nodes, (node,))
        self.assertEqual(fake.version, 2)


class TestNodeConfigUnit(unittest.TestCase):
    """Unit tests for synthesized NodeConfig fake."""

    def test_default_node_config(self) -> None:
        fake = make_node_config_fake()
        self.assertEqual(fake.read_only_files, set())
        self.assertEqual(fake.read_write_files, set())
        self.assertFalse(fake.allows_step_mode)
        self.assertFalse(fake.is_step_mode)
        self.assertIsNone(fake.guide_file)
        self.assertEqual(fake.feedback, ())
        self.assertIsNone(fake.verification_success_message)

    def test_seeded_node_config(self) -> None:
        state = NodeConfigState()
        sm = NodeConfigStateMachine(state)
        node = DagNode(UnitAddress("mod"), RoleAddress("lib"))
        rw_file = file_alias.ReadWriteFile(
            relative_path=file_alias.RelativePath("mod.py"),
            workspace_path=file_paths.WorkspacePath(file_paths.PathString("src/mod.py")),
            owning_node=node,
        )
        sm.seed_node_config(
            read_write_files={rw_file},
            allows_step_mode=True,
            is_step_mode=True,
            verification_success_message="All checks passed.",
            feedback=["Please fix formatting."],
        )
        fake = sm.as_fake(NodeConfig)
        self.assertIn(rw_file, fake.read_write_files)
        self.assertTrue(fake.allows_step_mode)
        self.assertTrue(fake.is_step_mode)
        self.assertEqual(fake.verification_success_message, "All checks passed.")
        self.assertEqual(fake.feedback, ("Please fix formatting.",))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestRoleConfigFuzz(unittest.TestCase):
    """Fuzz testing for RoleConfig transitions and version increment invariant."""

    @settings(max_examples=30)
    @given(
        roles=st.lists(st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"), min_size=1, max_size=5),
        node_counts=st.lists(st.integers(min_value=0, max_value=4), min_size=1, max_size=5),
    )
    def test_version_increments_on_set_nodes(self, roles: list[str], node_counts: list[int]) -> None:
        fake = make_role_config_fake()
        current_version = fake.version

        for role_name in roles:
            fake.set_role(RoleName(role_name))
            self.assertEqual(fake.role, role_name)
            self.assertEqual(fake.version, current_version)

        for count in node_counts:
            nodes_list = [
                DagNode(UnitAddress(f"unit_{i}"), RoleAddress("lib"))
                for i in range(count)
            ]
            fake.set_nodes(nodes_list)
            current_version += 1
            self.assertEqual(fake.version, current_version)
            self.assertEqual(len(fake.nodes), count)
