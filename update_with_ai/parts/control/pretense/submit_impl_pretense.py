"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SubmissionCoordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
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


class SubmissionStateMachine(StateMachine[SubmissionState]):
    """Pretense StateMachine for SubmissionCoordinator."""

    def __init__(self, state: Optional[SubmissionState] = None):
        super().__init__(state=state or SubmissionState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_submission_node(
        self,
        ctx: TransitionContext[None, [DagNode, bool, bool], None],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress('target'), RoleAddress('lib'))),
                    is_dirty=Domain(strategy=lambda: True),
                    verification_passed=Domain(strategy=lambda: True),
                )
        def _consequent(
            res: None,
            node: DagNode = DagNode(UnitAddress("target"), RoleAddress("lib")),
            is_dirty: bool = True,
            verification_passed: bool = True,
        ) -> None:
            if is_dirty:
                self.state.dirty_nodes.add(node)
                self.state.clean_nodes.discard(node)
            else:
                self.state.clean_nodes.add(node)
                self.state.dirty_nodes.discard(node)
            self.state.verification_passed = verification_passed
        ctx.update(_consequent)

    # ==============================================================================
    # 2. SubmissionCoordinator Transitions
    # ==============================================================================

    @transition(SubmissionCoordinator.submit_target)
    def submit_target(
        self,
        ctx: TransitionContext[
            SubmissionCoordinator,
            [DagNode, Optional[str], bool, Optional[Sequence[DagNode]]],
            SubmissionOutcome,
        ],
    ) -> None:
        ctx.arguments(
                    target_node=Domain(strategy=lambda: DagNode(UnitAddress('node'), RoleAddress('lib'))),
                    change_summary=Domain(strategy=lambda: 'Implement logic'),
                    has_modifications=Domain(strategy=lambda: True),
                    in_batch_dependencies=Domain(strategy=lambda: None),
                )
        def _returns(
            target_node: DagNode = DagNode(UnitAddress("node"), RoleAddress("lib")),
            change_summary: Optional[str] = "Implement logic",
            has_modifications: bool = True,
            in_batch_dependencies: Optional[Sequence[DagNode]] = None,
        ) -> SubmissionOutcome:
            if not self.state.verification_passed:
                return SubmissionOutcome(
                    accepted=False,
                    message="Verification checks failed for target node.",
                )
            elif in_batch_dependencies and any(dep in self.state.dirty_nodes for dep in in_batch_dependencies):
                return SubmissionOutcome(
                    accepted=False,
                    message="Cannot submit target: one or more in-batch dependencies remain dirty.",
                )
            elif has_modifications and not change_summary:
                return SubmissionOutcome(
                    accepted=False,
                    message="Submission rejected: change summary required when files are modified.",
                )
            else:
                return SubmissionOutcome(
                    accepted=True,
                    message=f"Target {target_node} submitted successfully.",
                )
        ctx.returns(_returns)

        def _consequent(
            res: SubmissionOutcome,
            target_node: DagNode = DagNode(UnitAddress("node"), RoleAddress("lib")),
            change_summary: Optional[str] = "Implement logic",
            has_modifications: bool = True,
            in_batch_dependencies: Optional[Sequence[DagNode]] = None,
        ) -> None:
            if res.accepted:
                self.state.dirty_nodes.discard(target_node)
                self.state.clean_nodes.add(target_node)
                if change_summary:
                    self.state.change_summaries[target_node] = change_summary
        ctx.update(_consequent)

    @transition(SubmissionCoordinator.submit_target_file)
    def submit_target_file(
        self,
        ctx: TransitionContext[
            SubmissionCoordinator,
            [str, Optional[str], Optional[str], Optional[str], Optional[str]],
            SubmissionOutcome,
        ],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: 'lib/module.py'),
                    summary=Domain(strategy=lambda: 'Update logic'),
                    repo_root=Domain(strategy=lambda: None),
                    workspace_root=Domain(strategy=lambda: None),
                    role_name=Domain(strategy=lambda: 'lib'),
                )
        def _returns(
            target: str = "lib/module.py",
            summary: Optional[str] = "Update logic",
            repo_root: Optional[str] = None,
            workspace_root: Optional[str] = None,
            role_name: Optional[str] = "lib",
        ) -> SubmissionOutcome:
            if not self.state.verification_passed:
                return SubmissionOutcome(
                    accepted=False,
                    message="Verification checks failed for file.",
                )
            return SubmissionOutcome(
                accepted=True,
                message=f"File {target} submitted successfully.",
            )
        ctx.returns(_returns)

    @transition(SubmissionCoordinator.parse_unit_from_file_path)
    def parse_unit_from_file_path(
        self,
        ctx: TransitionContext[SubmissionCoordinator, [str, str], Tuple[str, str, str]],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'parts/core/lib/demo.py'),
                    repo_root=Domain(strategy=lambda: '/workspace'),
                )
        def _returns(file_path: str = "parts/core/lib/demo.py", repo_root: str = "/workspace") -> Tuple[str, str, str]:
            norm = file_path.replace("\\", "/").strip("/")
            parts = norm.split("/")
            part_dir, unit_name, role_name = "parts/core", "demo", "lib"
            for i, seg in enumerate(parts):
                if seg == "parts" and i + 3 < len(parts):
                    part_dir = f"parts/{parts[i+1]}"
                    role_name = parts[i+2]
                    unit_name = os.path.splitext(parts[i+3])[0]
                    break
            return (part_dir, unit_name, role_name)
        ctx.returns(_returns)


proto = SubmissionStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_submission_fake(state: Optional[SubmissionState] = None) -> SubmissionCoordinator:
    """Instantiate a synthesized SubmissionCoordinator fake."""
    sm = SubmissionStateMachine(state)
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
        self.sm = SubmissionStateMachine(self.state)
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
        sm = SubmissionStateMachine(state)
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
