"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SubmissionCoordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.control.lib.submit import (
    SubmissionCoordinator,
    SubmissionOutcome,
)
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


@dataclass
class SubmissionState:
    """Canonical model state for target submission and validation."""
    clean_nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    dirty_nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    change_summaries: PretenseDict[DagNode, str] = field(default_factory=PretenseDict)
    verification_passed: bool = True


proto = StateMachineProto[SubmissionState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_submission_node(): pass

@seed_submission_node.arguments
def _(
    state: SubmissionState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    is_dirty: bool | NotBoundType = NotBound,
    verification_passed: bool | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, bool, bool]]:
    n = DagNode(UnitAddress("target"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    d = True if isinstance(is_dirty, NotBoundType) else bool(is_dirty)
    v = True if isinstance(verification_passed, NotBoundType) else bool(verification_passed)
    return (n, d, v)

@seed_submission_node.provide
def _(
    state: SubmissionState,
    this: Any,
    node: DagNode,
    is_dirty: bool,
    verification_passed: bool,
    result: None = None,
) -> None:
    if is_dirty:
        state.dirty_nodes.add(node)
        state.clean_nodes.discard(node)
    else:
        state.clean_nodes.add(node)
        state.dirty_nodes.discard(node)
    state.verification_passed = verification_passed


# ==============================================================================
# 2. SubmissionCoordinator Transitions
# ==============================================================================

@proto.transition(SubmissionCoordinator.submit_target)
def submit_target(): pass

@submit_target.arguments
def _(
    state: SubmissionState,
    this: Any,
    target_node: DagNode | NotBoundType = NotBound,
    change_summary: Optional[str] | NotBoundType = NotBound,
    has_modifications: bool | NotBoundType = NotBound,
    in_batch_dependencies: Optional[Sequence[DagNode]] | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, Optional[str], bool, Optional[Sequence[DagNode]]]]:
    tgt = DagNode(UnitAddress("node"), RoleAddress("lib")) if isinstance(target_node, NotBoundType) else target_node
    sumry = "Implement logic" if isinstance(change_summary, NotBoundType) else change_summary
    has_mods = True if isinstance(has_modifications, NotBoundType) else bool(has_modifications)
    in_deps = None if isinstance(in_batch_dependencies, NotBoundType) else in_batch_dependencies
    return (tgt, sumry, has_mods, in_deps)

@submit_target.returns
def _(
    state: SubmissionState,
    this: Any,
    target_node: DagNode,
    change_summary: Optional[str],
    has_modifications: bool,
    in_batch_dependencies: Optional[Sequence[DagNode]],
    outcome: object = NotBound,
) -> Optional[Outcome[SubmissionOutcome]]:
    # Gating 1: Verification failure
    if not state.verification_passed:
        expected = SubmissionOutcome(
            accepted=False,
            message="Verification checks failed for target node.",
        )
    # Gating 2: In-batch dependencies must be clean
    elif in_batch_dependencies and any(dep in state.dirty_nodes for dep in in_batch_dependencies):
        expected = SubmissionOutcome(
            accepted=False,
            message="Cannot submit target: one or more in-batch dependencies remain dirty.",
        )
    # Gating 3: Summary required when modifications exist
    elif has_modifications and not change_summary:
        expected = SubmissionOutcome(
            accepted=False,
            message="Submission rejected: change summary required when files are modified.",
        )
    else:
        expected = SubmissionOutcome(
            accepted=True,
            message=f"Target {target_node} submitted successfully.",
        )

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@submit_target.provide
def _(
    state: SubmissionState,
    this: Any,
    target_node: DagNode,
    change_summary: Optional[str],
    has_modifications: bool,
    in_batch_dependencies: Optional[Sequence[DagNode]],
    result: SubmissionOutcome,
) -> None:
    if result.accepted:
        state.dirty_nodes.discard(target_node)
        state.clean_nodes.add(target_node)
        if change_summary:
            state.change_summaries[target_node] = change_summary


@proto.transition(SubmissionCoordinator.submit_target_file)
def submit_target_file(): pass

@submit_target_file.arguments
def _(
    state: SubmissionState,
    this: Any,
    target: str | NotBoundType = NotBound,
    summary: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    workspace_root: Optional[str] | NotBoundType = NotBound,
    role_name: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]]:
    t = "lib/module.py" if isinstance(target, NotBoundType) else str(target)
    s = "Update logic" if isinstance(summary, NotBoundType) else summary
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    wr = None if isinstance(workspace_root, NotBoundType) else workspace_root
    rn = "lib" if isinstance(role_name, NotBoundType) else role_name
    return (t, s, rr, wr, rn)

@submit_target_file.returns
def _(
    state: SubmissionState,
    this: Any,
    target: str,
    summary: Optional[str],
    repo_root: Optional[str],
    workspace_root: Optional[str],
    role_name: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[SubmissionOutcome]]:
    if not state.verification_passed:
        expected = SubmissionOutcome(
            accepted=False,
            message="Verification checks failed for file.",
        )
    else:
        expected = SubmissionOutcome(
            accepted=True,
            message=f"File {target} submitted successfully.",
        )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SubmissionCoordinator.parse_unit_from_file_path)
def parse_unit_from_file_path(): pass

@parse_unit_from_file_path.arguments
def _(
    state: SubmissionState,
    this: Any,
    file_path: str | NotBoundType = NotBound,
    repo_root: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str]]:
    p = "parts/core/lib/demo.py" if isinstance(file_path, NotBoundType) else str(file_path)
    r = "/workspace" if isinstance(repo_root, NotBoundType) else str(repo_root)
    return (p, r)

@parse_unit_from_file_path.returns
def _(
    state: SubmissionState,
    this: Any,
    file_path: str,
    repo_root: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Tuple[str, str, str]]]:
    # Extract part, unit, role from standard layout parts/<part>/<role>/<unit>.<ext>
    norm = file_path.replace("\\", "/").strip("/")
    parts = norm.split("/")
    part_dir, unit_name, role_name = "parts/core", "demo", "lib"
    for i, seg in enumerate(parts):
        if seg == "parts" and i + 3 < len(parts):
            part_dir = f"parts/{parts[i+1]}"
            role_name = parts[i+2]
            unit_name = os.path.splitext(parts[i+3])[0]
            break
    expected = (part_dir, unit_name, role_name)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_submission_fake(state: Optional[SubmissionState] = None) -> SubmissionCoordinator:
    """Instantiate a synthesized SubmissionCoordinator fake."""
    st = state or SubmissionState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(SubmissionCoordinator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

import os
import stat
import tempfile
from update_with_ai.parts.control.lib import submit_impl, verification
from update_with_ai.parts.agent.lib import file_alias, node_config
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.dag.lib import dag_storage


class MockDagStorageSubmit:
    tier = agent_session

    def __init__(self) -> None:
        self.dirty_nodes: Set[DagNode] = set()
        self.clean_nodes: Set[DagNode] = set()
        self.change_descriptions: Dict[DagNode, Any] = {}

    def is_dirty(self, node: DagNode) -> bool:
        return node in self.dirty_nodes

    def mark_node_clean(self, node: DagNode, change_desc: Any = None) -> None:
        self.clean_nodes.add(node)
        self.change_descriptions[node] = change_desc


class MockVerificationEvaluatorSubmit:
    tier = agent_session

    def __init__(self) -> None:
        self.passed = True
        self.diagnostic = ""

    def evaluate_verification(self, target: Optional[DagNode] = None) -> verification.VerificationResult:
        return verification.VerificationResult(
            passed=self.passed,
            diagnostic_output=self.diagnostic,
            is_cached=False,
        )


class MockNodeConfigSubmit:
    tier = agent_session

    def __init__(self) -> None:
        self.feedback: Optional[List[str]] = None
        self.role_definitions: Dict[str, Any] = {
            "lib": {
                "role_name": "lib",
                "src_pattern": "{unit_dir}/lib/{unit_name}.py",
                "feedback_role_deps": [],
            },
            "test": {
                "role_name": "test",
                "src_pattern": "{unit_dir}/tests/{unit_name}_test.py",
                "feedback_role_deps": ["lib"],
            },
            "qa": {
                "role_name": "qa",
                "src_pattern": "",
                "audit_tag": "QA_AUDIT",
                "feedback_role_deps": ["lib"],
            },
        }


class MockAliasManagerSubmit:
    tier = agent_session

    def to_alias(self, path: str) -> Any:
        return file_alias.FileAlias(file_alias.RelativePath(path))


class TestSubmitImplReal(unittest.TestCase):
    """Direct unit tests for submit_impl.SubmissionCoordinator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        submit_impl.__initialize__(self.registry)

        self.mock_storage = MockDagStorageSubmit()
        self.mock_verifier = MockVerificationEvaluatorSubmit()
        self.mock_node_cfg = MockNodeConfigSubmit()
        self.mock_alias_mgr = MockAliasManagerSubmit()

        self.registry.register_instance(self.mock_storage, keys=[dag_storage.DagStorage], tier=agent_session)
        self.registry.register_instance(self.mock_verifier, keys=[verification.VerificationEvaluator], tier=agent_session)
        self.registry.register_instance(self.mock_node_cfg, keys=[node_config.NodeConfig], tier=agent_session)
        self.registry.register_instance(self.mock_alias_mgr, keys=[file_alias.AliasManager], tier=agent_session)

        self.target = DagNode(UnitAddress("pkg:calc"), RoleAddress("lib"))
        self.dep = DagNode(UnitAddress("pkg:calc"), RoleAddress("test"))

    def test_submit_target_gating(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(submit_impl.SubmissionCoordinator)

            # 1. Verification failure
            self.mock_verifier.passed = False
            self.mock_verifier.diagnostic = "Compilation error"
            res = coord.submit_target(self.target, change_summary="Fixed", has_modifications=True)
            self.assertFalse(res.accepted)
            self.assertIn("Verification is failing", res.message)

            # 2. In-batch dependency is dirty
            self.mock_verifier.passed = True
            self.mock_storage.dirty_nodes.add(self.dep)
            res = coord.submit_target(self.target, change_summary="Fixed", has_modifications=True, in_batch_dependencies=[self.dep])
            self.assertFalse(res.accepted)
            self.assertIn("must be submitted before dependent targets", res.message)

            # 3. Session feedback present but no modifications
            self.mock_storage.dirty_nodes.clear()
            self.mock_node_cfg.feedback = ["Please address this issue"]
            res = coord.submit_target(self.target, change_summary=None, has_modifications=False)
            self.assertFalse(res.accepted)
            self.assertIn("Session feedback is present but no workspace files were modified", res.message)

            # 4. Auditor node cannot have change summary
            self.mock_node_cfg.feedback = None
            auditor_node = DagNode(UnitAddress("pkg:calc"), RoleAddress("qa"))
            res = coord.submit_target(auditor_node, change_summary="Some changes", has_modifications=False)
            self.assertFalse(res.accepted)
            self.assertIn("Change summaries are not permitted for audit nodes", res.message)

            # 5. Producer modified but no summary
            res = coord.submit_target(self.target, change_summary=None, has_modifications=True)
            self.assertFalse(res.accepted)
            self.assertIn("Workspace files were modified but change_summary was not provided", res.message)

            # 6. Producer unmodified but summary provided
            res = coord.submit_target(self.target, change_summary="Some summary", has_modifications=False)
            self.assertFalse(res.accepted)
            self.assertIn("Change summaries are not permitted when submitting without", res.message)

            # 7. Producer modified with summary -> success
            res = coord.submit_target(self.target, change_summary="Added feature", has_modifications=True)
            self.assertTrue(res.accepted)
            self.assertIn(self.target, self.mock_storage.clean_nodes)

            # 8. Producer unmodified without summary -> success
            res = coord.submit_target(self.target, change_summary=None, has_modifications=False)
            self.assertTrue(res.accepted)

    def test_submit_target_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = os.path.join(tmp_dir, "repo")
            ws_root = os.path.join(tmp_dir, "ws")
            os.makedirs(os.path.join(repo_root, "pkg/lib"), exist_ok=True)
            os.makedirs(os.path.join(ws_root, "pkg/lib"), exist_ok=True)

            lib_file = os.path.join(repo_root, "pkg/lib/calc.py")
            with open(lib_file, "w", encoding="utf-8") as f:
                f.write("# --- CLEANROOM METADATA ---\n# --- END CLEANROOM METADATA ---\ndef calc(): pass\n")

            ws_lib_file = os.path.join(ws_root, "pkg/lib/calc.py")
            with open(ws_lib_file, "w", encoding="utf-8") as f:
                f.write("# --- CLEANROOM METADATA ---\n# --- END CLEANROOM METADATA ---\ndef calc(): pass\n")

            with enter_phase(agent_session, registry=self.registry) as scope:
                coord = scope.get_singleton(submit_impl.SubmissionCoordinator)

                # 1. Target not found
                res = coord.submit_target_file("pkg/lib/missing.py", repo_root=repo_root, workspace_root=ws_root, role_name="lib")
                self.assertFalse(res.accepted)
                self.assertIn("not found on disk", res.message)

                # 2. Producer submit outside directory scope
                res = coord.submit_target_file("pkg/tests/calc_test.py", repo_root=repo_root, workspace_root=ws_root, role_name="lib")
                self.assertFalse(res.accepted)

                # 3. Producer submit modified with summary -> [CHANGE]
                res = coord.submit_target_file("pkg/lib/calc.py", summary="Initial calc", repo_root=repo_root, workspace_root=ws_root, role_name="lib")
                self.assertTrue(res.accepted, msg=res.message)
                self.assertIn("[CHANGE]", res.message)

                # 4. Auditor submit audited implementation target
                res = coord.submit_target_file("pkg/lib/calc.py", repo_root=repo_root, workspace_root=ws_root, role_name="qa")
                self.assertTrue(res.accepted, msg=res.message)
                self.assertIn("[AUDIT]", res.message)
                self.assertIn("[AUDIT]", res.message)


class TestSubmissionCoordinatorUnit(unittest.TestCase):
    """Unit tests for synthesized SubmissionCoordinator fake."""

    def setUp(self) -> None:
        self.state = SubmissionState()
        self.sm = proto.make_state_machine(self.state)
        self.target = DagNode(UnitAddress("core"), RoleAddress("lib"))
        self.dep = DagNode(UnitAddress("core"), RoleAddress("low"))
        self.fake: SubmissionCoordinator = self.sm.as_fake(SubmissionCoordinator)

    def test_submit_target_success(self) -> None:
        outcome = self.fake.submit_target(self.target, change_summary="Add core module", has_modifications=True)
        self.assertTrue(outcome.accepted)
        self.assertIn(self.target, self.state.clean_nodes)
        self.assertEqual(self.state.change_summaries[self.target], "Add core module")

    def test_submit_target_rejects_uncleaned_in_batch_dependency(self) -> None:
        self.state.dirty_nodes.add(self.dep)
        outcome = self.fake.submit_target(
            self.target,
            change_summary="Update",
            has_modifications=True,
            in_batch_dependencies=[self.dep],
        )
        self.assertFalse(outcome.accepted)
        self.assertIn("in-batch dependencies remain dirty", outcome.message)

    def test_submit_target_rejects_missing_summary_on_modification(self) -> None:
        outcome = self.fake.submit_target(self.target, change_summary=None, has_modifications=True)
        self.assertFalse(outcome.accepted)
        self.assertIn("change summary required", outcome.message)

    def test_parse_unit_from_file_path(self) -> None:
        part, unit, role = self.fake.parse_unit_from_file_path("parts/agent/lib/session.py", "/workspace")
        self.assertEqual(part, "parts/agent")
        self.assertEqual(unit, "session")
        self.assertEqual(role, "lib")


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestSubmissionCoordinatorFuzz(unittest.TestCase):
    """Property fuzz testing for SubmissionCoordinator."""

    @settings(max_examples=30)
    @given(
        has_mods=st.booleans(),
        has_summary=st.booleans(),
        dep_is_dirty=st.booleans(),
    )
    def test_submission_gating_invariants(self, has_mods: bool, has_summary: bool, dep_is_dirty: bool) -> None:
        state = SubmissionState()
        sm = proto.make_state_machine(state)
        fake = sm.as_fake(SubmissionCoordinator)

        target = DagNode(UnitAddress("target"), RoleAddress("lib"))
        dep = DagNode(UnitAddress("dep"), RoleAddress("low"))

        if dep_is_dirty:
            state.dirty_nodes.add(dep)

        summary = "Fixed issue" if has_summary else None
        outcome = fake.submit_target(
            target,
            change_summary=summary,
            has_modifications=has_mods,
            in_batch_dependencies=[dep],
        )

        if dep_is_dirty:
            self.assertFalse(outcome.accepted)
        elif has_mods and not has_summary:
            self.assertFalse(outcome.accepted)
        else:
            self.assertTrue(outcome.accepted)
