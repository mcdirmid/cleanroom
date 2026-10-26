"""Pretense state machines, fake synthesis, unit tests, and fuzzing for RoleConfig and NodeConfig."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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


role_proto = StateMachineProto[RoleConfigState]()


@role_proto.seeding()
def seed_role_config(): pass

@seed_role_config.arguments
def _(
    state: RoleConfigState,
    this: Any,
    role: str | NotBoundType = NotBound,
    nodes: Optional[Sequence[DagNode]] | NotBoundType = NotBound,
    version: int | NotBoundType = NotBound,
) -> Optional[Tuple[str, Sequence[DagNode], int]]:
    r = "lib" if isinstance(role, NotBoundType) else str(role)
    ns = () if isinstance(nodes, NotBoundType) or nodes is None else tuple(nodes)
    v = 1 if isinstance(version, NotBoundType) else int(version)
    return (r, ns, v)

@seed_role_config.provide
def _(
    state: RoleConfigState,
    this: Any,
    role: str,
    nodes: Sequence[DagNode],
    version: int,
    result: None = None,
) -> None:
    state.role = role
    state.nodes = list(nodes)
    state.version = version


@role_proto.transition(name="role")
def role(): pass

@role.returns
def _(state: RoleConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[RoleName]]:
    expected = RoleName(state.role)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@role_proto.transition(name="nodes")
def nodes(): pass

@nodes.returns
def _(state: RoleConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Sequence[DagNode]]]:
    expected = tuple(state.nodes)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@role_proto.transition(name="version")
def version(): pass

@version.returns
def _(state: RoleConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[ExecutionVersion]]:
    expected = ExecutionVersion(state.version)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@role_proto.transition(RoleConfig.set_role)
def set_role(): pass

@set_role.arguments
def _(
    state: RoleConfigState,
    this: Any,
    role: RoleName | str | NotBoundType = NotBound,
) -> Optional[Tuple[RoleName]]:
    r = RoleName("test") if isinstance(role, NotBoundType) else RoleName(str(role))
    return (r,)

@set_role.provide
def _(
    state: RoleConfigState,
    this: Any,
    role: RoleName,
    result: None = None,
) -> None:
    state.role = str(role)


@role_proto.transition(RoleConfig.set_nodes)
def set_nodes(): pass

@set_nodes.arguments
def _(
    state: RoleConfigState,
    this: Any,
    nodes: Sequence[DagNode] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[DagNode]]]:
    ns = () if isinstance(nodes, NotBoundType) else tuple(nodes)
    return (ns,)

@set_nodes.provide
def _(
    state: RoleConfigState,
    this: Any,
    nodes: Sequence[DagNode],
    result: None = None,
) -> None:
    state.nodes = list(nodes)
    state.version += 1


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


node_proto = StateMachineProto[NodeConfigState]()


# Seeding transition for NodeConfig
@node_proto.seeding()
def seed_node_config(): pass

@seed_node_config.arguments
def _(
    state: NodeConfigState,
    this: Any,
    read_only_files: Optional[Set[file_alias.ReadOnlyFile]] | NotBoundType = NotBound,
    read_write_files: Optional[Set[file_alias.ReadWriteFile]] | NotBoundType = NotBound,
    allows_step_mode: bool | NotBoundType = NotBound,
    is_step_mode: bool | NotBoundType = NotBound,
    guide_file: Optional[file_alias.UnboundFile] | NotBoundType = NotBound,
    verification_success_message: Optional[str] | NotBoundType = NotBound,
    feedback: Optional[Sequence[str]] | NotBoundType = NotBound,
) -> Optional[Tuple[Set[file_alias.ReadOnlyFile], Set[file_alias.ReadWriteFile], bool, bool, Optional[file_alias.UnboundFile], Optional[VerificationSuccessMessage], Sequence[NodeFeedback]]]:
    ro = set() if isinstance(read_only_files, NotBoundType) or read_only_files is None else set(read_only_files)
    rw = set() if isinstance(read_write_files, NotBoundType) or read_write_files is None else set(read_write_files)
    allows = False if isinstance(allows_step_mode, NotBoundType) else bool(allows_step_mode)
    step = False if isinstance(is_step_mode, NotBoundType) else bool(is_step_mode)
    gf = None if isinstance(guide_file, NotBoundType) else guide_file
    vsm = None if isinstance(verification_success_message, NotBoundType) or verification_success_message is None else VerificationSuccessMessage(str(verification_success_message))
    fb = () if isinstance(feedback, NotBoundType) or feedback is None else tuple(NodeFeedback(f) for f in feedback)
    return (ro, rw, allows, step, gf, vsm, fb)

@seed_node_config.provide
def _(
    state: NodeConfigState,
    this: Any,
    read_only_files: Set[file_alias.ReadOnlyFile],
    read_write_files: Set[file_alias.ReadWriteFile],
    allows_step_mode: bool,
    is_step_mode: bool,
    guide_file: Optional[file_alias.UnboundFile],
    verification_success_message: Optional[VerificationSuccessMessage],
    feedback: Sequence[NodeFeedback],
    result: None = None,
) -> None:
    state.read_only_files = PretenseSet(read_only_files)
    state.read_write_files = PretenseSet(read_write_files)
    state.allows_step_mode = allows_step_mode
    state.is_step_mode = is_step_mode
    state.guide_file = guide_file
    state.verification_success_message = verification_success_message
    state.feedback = list(feedback)


# NodeConfig property transitions
@node_proto.transition(name="read_only_files")
def read_only_files(): pass

@read_only_files.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Set[file_alias.ReadOnlyFile]]]:
    expected = set(state.read_only_files)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="read_write_files")
def read_write_files(): pass

@read_write_files.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Set[file_alias.ReadWriteFile]]]:
    expected = set(state.read_write_files)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="allows_step_mode")
def allows_step_mode(): pass

@allows_step_mode.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.allows_step_mode
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="is_step_mode")
def is_step_mode(): pass

@is_step_mode.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    expected = state.is_step_mode
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="guide_file")
def guide_file(): pass

@guide_file.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[file_alias.UnboundFile]]]:
    expected = state.guide_file
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="templates")
def templates(): pass

@templates.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Mapping[file_alias.BoundFile, file_alias.FileContent]]]:
    expected = dict(state.templates)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="template_parameters")
def template_parameters(): pass

@template_parameters.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Mapping[TemplateParamKey, Any]]]:
    expected = dict(state.template_parameters)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="guide")
def guide(): pass

@guide.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[NodeGuide]]]:
    expected = state.guide
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="blame_targets_by_node")
def blame_targets_by_node(): pass

@blame_targets_by_node.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Mapping[DagNode, Set[file_alias.BoundFile]]]]:
    expected = {k: set(v) for k, v in state.blame_targets_by_node.items()}
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="verification_checks")
def verification_checks(): pass

@verification_checks.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Sequence[VerificationCheck]]]:
    expected = tuple(state.verification_checks)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="verification_checks_by_node")
def verification_checks_by_node(): pass

@verification_checks_by_node.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Mapping[DagNode, Sequence[VerificationCheck]]]]:
    expected = {k: tuple(v) for k, v in state.verification_checks_by_node.items()}
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="src_file_alias_by_node")
def src_file_alias_by_node(): pass

@src_file_alias_by_node.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Mapping[DagNode, file_alias.RelativePath]]]:
    expected = dict(state.src_file_alias_by_node)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="verification_success_message")
def verification_success_message(): pass

@verification_success_message.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Optional[VerificationSuccessMessage]]]:
    expected = state.verification_success_message
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="feedback")
def feedback(): pass

@feedback.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Sequence[NodeFeedback]]]:
    expected = tuple(state.feedback)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@node_proto.transition(name="per_node_info_by_node")
def per_node_info_by_node(): pass

@per_node_info_by_node.returns
def _(state: NodeConfigState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Mapping[DagNode, PerNodeInfo]]]:
    expected = dict(state.per_node_info_by_node)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factories
# ==============================================================================

def make_role_config_fake(state: Optional[RoleConfigState] = None) -> RoleConfig:
    """Instantiate a synthesized RoleConfig fake."""
    st = state or RoleConfigState()
    sm = role_proto.make_state_machine(st)
    return sm.as_fake(RoleConfig)


def make_node_config_fake(state: Optional[NodeConfigState] = None) -> NodeConfig:
    """Instantiate a synthesized NodeConfig fake."""
    st = state or NodeConfigState()
    sm = node_proto.make_state_machine(st)
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
        sm = node_proto.make_state_machine(state)
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
