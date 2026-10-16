# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:35:00Z
# CHANGE: Add unit tests for sandbox_submission_impl
# CODE_HASH: 0233309698f6
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import unittest
from typing import Any, Mapping, Optional, Sequence, Set
from support.lib.lifecycle import (
    LifecycleRegistry,
    enter_phase,
    system,
)
from update_with_ai.parts.agent.lib import (
    agent_file_alias,
    agent_node_config,
    agent_session,
)
from update_with_ai.parts.control.lib import control_coordinate
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.storage.lib import src_metadata
from update_with_ai.parts.sandbox.lib import (
    sandbox_file_editor,
    sandbox_guide_delivery,
    sandbox_run_control,
    sandbox_submission,
    sandbox_submission_impl,
    tool_provider,
)


def _make_node(unit: str = "unit_a", role: str = "dev") -> dag_storage.DagNode:
    return dag_storage.DagNode(
        unit_address=dag_storage.UnitAddress(unit),
        role_address=dag_storage.RoleAddress(role),
    )


def _make_file_alias(path: str) -> agent_file_alias.FileAlias:
    return agent_file_alias.FileAlias(agent_file_alias.RelativePath(path))


def _make_bound_file(
    path: str,
    owning_node: Optional[dag_storage.DagNode] = None,
) -> agent_file_alias.BoundFile:
    node = owning_node if owning_node is not None else _make_node(path.replace("/", "_").replace(".", "_"))
    return agent_file_alias.BoundFile(
        relative_path=agent_file_alias.RelativePath(path),
        workspace_path=agent_file_alias.file_paths.WorkspacePath(
            agent_file_alias.file_paths.PathString(f"/workspace/{path}")
        ),
        owning_node=node,
    )


def _bindings(d: Mapping[Any, Any]) -> Any:
    return d


class MockVerificationCheck:
    def __init__(self, passed: bool = True, diagnostic: str = "") -> None:
        self.passed = passed
        self.diagnostic = diagnostic

    def verify(self) -> tuple[bool, agent_node_config.VerificationDiagnostic]:
        return self.passed, agent_node_config.VerificationDiagnostic(self.diagnostic)


class MockToolManager:
    def __init__(self) -> None:
        self.tools: dict[str, tool_provider.Tool] = {}

    def install_tool(self, tool: tool_provider.Tool) -> None:
        self.tools[str(tool.name)] = tool


class MockEditManager:
    def __init__(self) -> None:
        self.hashes: dict[str, str] = {}
        self.has_modifications = False
        self.last_read_or_edited_file: Optional[agent_file_alias.FileAlias] = None

    def file_hash(self, file_alias: agent_file_alias.FileAlias) -> sandbox_file_editor.FileHash:
        return sandbox_file_editor.FileHash(self.hashes.get(str(file_alias.relative_path), "default_hash"))


class MockSourceMetadataCoordinator:
    def __init__(self) -> None:
        self.has_modifications = False
        self.modified_paths: Set[str] = set()

    def is_code_modified(self, target: Any) -> bool:
        path_str = str(target)
        return (
            path_str in self.modified_paths
            or any(p in path_str for p in self.modified_paths)
            or self.has_modifications
        )


class MockNodeConfig:
    def __init__(self) -> None:
        self.verification_checks: Sequence[agent_node_config.VerificationCheck] = []
        self.verification_success_message: Optional[agent_node_config.VerificationSuccessMessage] = None
        self.read_write_files: Sequence[agent_file_alias.FileAlias] = []
        self.read_only_files: Sequence[agent_file_alias.FileAlias] = []
        self.blame_targets_by_node: Mapping[dag_storage.DagNode, Sequence[agent_file_alias.BoundFile]] = {}
        self.is_step_mode = False
        self.guide: Any = None
        self.role_config: Any = None
        self.per_node_info_by_node: Mapping[dag_storage.DagNode, Any] = {}


class MockRoleConfig:
    def __init__(self) -> None:
        self.auditor_roles: Set[str] = set()

    def is_auditor(self, node: dag_storage.DagNode) -> bool:
        return str(node.role_address) in self.auditor_roles


class MockGuideDelivery:
    def __init__(self) -> None:
        self.has_steps_remaining = False

    def advance_step(
        self,
        verification_passed: bool,
        failure_diagnostics: agent_node_config.VerificationDiagnostic,
    ) -> tool_provider.ToolResponse:
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent("Advanced step"),
        )


class MockDagStorage:
    def __init__(self) -> None:
        self.clean_nodes: dict[dag_storage.DagNode, Optional[str]] = {}
        self.dirty_nodes: Set[dag_storage.DagNode] = set()
        self.messages: dict[dag_storage.DagNode, list[str]] = {}

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self.dirty_nodes

    def mark_node_clean(self, node: dag_storage.DagNode, summary: Optional[str] = None) -> None:
        self.clean_nodes[node] = summary
        self.dirty_nodes.discard(node)

    def get_messages(self, node: dag_storage.DagNode) -> Sequence[str]:
        return self.messages.get(node, [])


class MockSessionCoordinator:
    def __init__(self) -> None:
        self.open_targets: list[dag_storage.DagNode] = []
        self.node_by_alias: dict[str, dag_storage.DagNode] = {}
        self.alias_by_node: dict[dag_storage.DagNode, str] = {}
        self.submit_outcome: Optional[control_coordinate.ControlDispatchOutcome] = None
        self.blame_outcome: Optional[control_coordinate.ControlDispatchOutcome] = None
        self.fail_outcome: Optional[control_coordinate.ControlDispatchOutcome] = None
        self.dispatched_submit: Optional[tuple[Optional[str], Optional[str]]] = None
        self.dispatched_blame: Optional[tuple[Optional[str], Optional[str], str]] = None
        self.dispatched_fail: Optional[tuple[Optional[str], str]] = None

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        if state == control_coordinate.TargetState.OPEN and node not in self.open_targets:
            self.open_targets.append(node)
        self.node_by_alias[alias] = node
        self.alias_by_node[node] = alias

    def resolve_default_target(self, last_accessed_file: Optional[Any] = None) -> Optional[dag_storage.DagNode]:
        if not self.open_targets:
            return None
        return self.open_targets[0]

    def get_node_for_alias(self, alias: Optional[str]) -> Optional[dag_storage.DagNode]:
        return self.node_by_alias.get(alias or "")

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        return self.alias_by_node.get(node, "")

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        self.dispatched_submit = (target_alias, change_summary)
        if self.submit_outcome is not None:
            return self.submit_outcome
        target = self.get_node_for_alias(target_alias) if target_alias else self.resolve_default_target()
        summary_str = str(change_summary or "").strip()
        if has_modifications and not summary_str:
            return control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Error: Workspace files were modified, so change_summary must be provided.",
                remaining_open_targets=list(self.open_targets),
            )
        if not has_modifications and summary_str:
            return control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Error: Change summaries are not permitted when submitting without workspace file modifications.",
                remaining_open_targets=list(self.open_targets),
            )
        if target and target in self.open_targets:
            self.open_targets.remove(target)
        return control_coordinate.ControlDispatchOutcome(
            success=True, message="Submitted", remaining_open_targets=list(self.open_targets)
        )

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        self.dispatched_fail = (target_alias, explanation)
        if self.fail_outcome is not None:
            return self.fail_outcome
        target = self.get_node_for_alias(target_alias) if target_alias else self.resolve_default_target()
        if target and target in self.open_targets:
            self.open_targets.remove(target)
        return control_coordinate.ControlDispatchOutcome(
            success=True, message="Failed", remaining_open_targets=list(self.open_targets)
        )

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        self.dispatched_blame = (source_alias, blame_target_alias, explanation)
        if self.blame_outcome is not None:
            return self.blame_outcome
        target = self.get_node_for_alias(source_alias) if source_alias else self.resolve_default_target()
        if target and target in self.open_targets:
            self.open_targets.remove(target)
        return control_coordinate.ControlDispatchOutcome(
            success=True, message="Blamed", remaining_open_targets=list(self.open_targets)
        )


class MockAliasManager:
    def actual_type(self) -> type:
        return agent_file_alias.FileAlias

    def wire_type(self) -> type:
        return str

    def to_alias(self, path: str) -> agent_file_alias.FileAlias:
        return _make_file_alias(path)

    convert = to_alias


class MockAliasManagerType:
    tier = agent_session.agent_session

    @property
    def actual_type(self) -> type[agent_file_alias.FileAlias]:
        return agent_file_alias.FileAlias

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        return _make_file_alias(wire_value)


class MockRunController:
    tier = agent_session.agent_session

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        from support.lib.lifecycle import get_singleton
        try:
            cfg = get_singleton(agent_node_config.NodeConfig)
            return cfg.verification_checks
        except Exception:
            return []

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        from support.lib.lifecycle import get_singleton
        try:
            node_cfg = get_singleton(agent_node_config.NodeConfig)
            return {
                node: set(bound_files)
                for node, bound_files in getattr(node_cfg, "blame_targets_by_node", {}).items()
            }
        except Exception:
            return {}

    def initialize(self) -> None:
        self._passed = True
        self._diagnostic_output = ""

    def update_verification(self) -> None:
        all_passed = True
        diag_parts: list[str] = []
        for check in self.verification_checks:
            check_passed, check_diag = check.verify()
            if not check_passed:
                all_passed = False
                if check_diag:
                    diag_parts.append(str(check_diag))
        self._passed = all_passed
        self._diagnostic_output = "\n".join(diag_parts).strip()


class SandboxSubmissionImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.mock_run_controller = MockRunController()
        self.registry.register_instance(
            self.mock_run_controller,
            keys=[sandbox_run_control.RunController],
            tier=agent_session.agent_session,
        )
        sandbox_submission_impl.__initialize__(self.registry)

        self.mock_storage = MockDagStorage()
        self.registry.register_instance(
            self.mock_storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )
        self.mock_src_metadata = MockSourceMetadataCoordinator()
        self.registry.register_instance(
            self.mock_src_metadata,
            keys=[src_metadata.SourceMetadataCoordinator],
            tier=agent_session.agent_session,
        )
        self.mock_tool_manager = MockToolManager()
        self.registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session.agent_session,
        )
        self.mock_edit_manager = MockEditManager()
        self.registry.register_instance(
            self.mock_edit_manager,
            keys=[sandbox_file_editor.EditManager],
            tier=agent_session.agent_session,
        )
        self.mock_node_config = MockNodeConfig()
        self.registry.register_instance(
            self.mock_node_config,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )
        self.mock_role_config = MockRoleConfig()
        self.registry.register_instance(
            self.mock_role_config,
            keys=[agent_node_config.RoleConfig],
            tier=agent_session.agent_session,
        )
        self.mock_guide_delivery = MockGuideDelivery()
        self.registry.register_instance(
            self.mock_guide_delivery,
            keys=[sandbox_guide_delivery.GuideDelivery],
            tier=agent_session.agent_session,
        )
        self.mock_session_coordinator = MockSessionCoordinator()
        self.registry.register_instance(
            self.mock_session_coordinator,
            keys=[control_coordinate.SessionCoordinator],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager = MockAliasManager()
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[agent_file_alias.AliasManager],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager_type = MockAliasManagerType()
        self.registry.register_instance(
            self.mock_alias_manager_type,
            keys=[tool_provider.AliasManagerType],
            tier=agent_session.agent_session,
        )

    def test_singleton_registration(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(sandbox_submission.SubmitTool)
            fail = scope.get_singleton(sandbox_submission.FailTool)
            blame = scope.get_singleton(sandbox_submission.BlameTool)
            self.assertIsInstance(submit, sandbox_submission_impl.SubmitTool)
            self.assertIsInstance(fail, sandbox_submission_impl.FailTool)
            self.assertIsInstance(blame, sandbox_submission_impl.BlameTool)

    def test_submit_tool_metadata(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            self.assertEqual(tool.name, tool_provider.ToolName("submit"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool_provider.ParameterName("change_summary"), tool.parameters)
            self.assertIn(tool_provider.ParameterName("target"), tool.parameters)

    def test_submit_tool_fails_when_guide_steps_remain(self) -> None:
        self.mock_node_config.is_step_mode = True
        self.mock_guide_delivery.has_steps_remaining = True
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("Guide step mode is active and guide steps remain", str(resp.content))

    def test_submit_tool_fails_when_verification_failing(self) -> None:
        check = MockVerificationCheck(passed=False, diagnostic="Syntax error on line 5")
        self.mock_node_config.verification_checks = [check]
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("Verification is failing", str(resp.content))

    def test_submit_tool_fails_when_modified_without_summary(self) -> None:
        self.mock_edit_manager.has_modifications = True
        self.mock_src_metadata.has_modifications = True
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("Workspace files were modified", str(resp.content))

    def test_submit_tool_fails_when_unmodified_with_summary(self) -> None:
        self.mock_edit_manager.has_modifications = False
        self.mock_src_metadata.has_modifications = False
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            param = tool.change_summary_parameter
            resp = tool.execute_tool(_bindings({param: sandbox_submission.ChangeSummary("Did some work")}))
            self.assertTrue(resp.is_failed)
            self.assertIn("Change summaries are not permitted", str(resp.content))

    def test_submit_tool_fails_when_unaddressed_feedback(self) -> None:
        self.mock_session_coordinator.submit_outcome = control_coordinate.ControlDispatchOutcome(
            success=False,
            message="Error: Session feedback is present but no workspace files were modified. You must modify workspace files to address feedback before submitting, or call fail if the feedback cannot be resolved.",
            remaining_open_targets=[],
        )
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("Session feedback is present", str(resp.content))
            self.assertIsNotNone(resp.reminder)
            self.assertIn("modify workspace files to address feedback", str(resp.reminder))
            self.assertNotIn("change_summary", str(resp.reminder))

    def test_submit_tool_succeeds_with_modifications_and_summary(self) -> None:
        self.mock_edit_manager.has_modifications = True
        self.mock_src_metadata.has_modifications = True
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.SubmitTool)
            param = tool.change_summary_parameter
            resp = tool.execute_tool(
                _bindings(
                    {
                        tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                        param: sandbox_submission.ChangeSummary("Updated function foo"),
                    }
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.dispatched_submit,
                ("pkg/unit1.py", "Updated function foo"),
            )

    def test_fail_tool_metadata(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.FailTool)
            self.assertEqual(tool.name, tool_provider.ToolName("fail"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool_provider.ParameterName("explanation"), tool.parameters)

    def test_fail_tool_execution(self) -> None:
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.FailTool)
            param = tool.explanation_parameter
            resp = tool.execute_tool(
                _bindings(
                    {
                        tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                        param: sandbox_submission.FailureExplanation("Cannot complete task"),
                    }
                )
            )
            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.dispatched_fail,
                ("pkg/unit1.py", "Cannot complete task"),
            )

    def test_blame_tool_metadata(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.BlameTool)
            self.assertEqual(tool.name, tool_provider.ToolName("blame"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool_provider.ParameterName("explanation"), tool.parameters)
            self.assertIn(tool_provider.ParameterName("blame_target"), tool.parameters)

    def test_blame_tool_fails_multiline_explanation(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.BlameTool)
            param = tool.explanation_parameter
            resp = tool.execute_tool(_bindings({param: sandbox_submission.BlameExplanation("line 1\nline 2")}))
            self.assertTrue(resp.is_failed)
            self.assertIn("single paragraph without newline", str(resp.content))

    def test_blame_tool_succeeds_single_blame_target(self) -> None:
        source_node = _make_node("unit1", "dev")
        dep_node = _make_node("dep1", "lib")
        bound_target = _make_bound_file("dep1.py", owning_node=dep_node)
        self.mock_node_config.blame_targets_by_node = {source_node: [bound_target]}
        self.mock_session_coordinator.register_node(source_node, "unit1.py")

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.BlameTool)
            param = tool.explanation_parameter
            resp = tool.execute_tool(_bindings({param: sandbox_submission.BlameExplanation("Defect in dep1.py interface")}))
            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.dispatched_blame,
                ("unit1.py", "dep1.py", "Defect in dep1.py interface"),
            )

    def test_blame_tool_resolves_blame_target_from_target_parameter_when_multiple_targets(self) -> None:
        source_node = _make_node("unit1", "qa")
        dep_node1 = _make_node("dep1", "lib")
        dep_node2 = _make_node("dep2", "test")
        bound1 = _make_bound_file("dep1.py", owning_node=dep_node1)
        bound2 = _make_bound_file("dep2.py", owning_node=dep_node2)
        self.mock_node_config.blame_targets_by_node = {source_node: [bound1, bound2]}
        self.mock_session_coordinator.register_node(source_node, "unit1.py")

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.BlameTool)
            param = tool.explanation_parameter
            resp = tool.execute_tool(
                _bindings(
                    {
                        tool.target_parameter: _make_file_alias("dep1.py"),
                        param: sandbox_submission.BlameExplanation("Defect in dep1.py interface"),
                    }
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.dispatched_blame,
                ("unit1.py", "dep1.py", "Defect in dep1.py interface"),
            )

    def test_blame_tool_resolves_when_target_and_blame_target_both_passed(self) -> None:
        source_node = _make_node("unit1", "qa")
        dep_node1 = _make_node("dep1", "lib")
        dep_node2 = _make_node("dep2", "test")
        bound1 = _make_bound_file("dep1.py", owning_node=dep_node1)
        bound2 = _make_bound_file("dep2.py", owning_node=dep_node2)
        self.mock_node_config.blame_targets_by_node = {source_node: [bound1, bound2]}
        self.mock_session_coordinator.register_node(source_node, "unit1.py")

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.BlameTool)
            param = tool.explanation_parameter
            resp = tool.execute_tool(
                _bindings(
                    {
                        tool.target_parameter: _make_file_alias("dep1.py"),
                        tool.blame_target_parameter: _make_file_alias("dep1.py"),
                        param: sandbox_submission.BlameExplanation("Defect in dep1.py interface"),
                    }
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.dispatched_blame,
                ("unit1.py", "dep1.py", "Defect in dep1.py interface"),
            )

    def test_blame_tool_resolves_when_only_blame_target_passed(self) -> None:
        source_node = _make_node("unit1", "qa")
        dep_node1 = _make_node("dep1", "lib")
        dep_node2 = _make_node("dep2", "test")
        bound1 = _make_bound_file("dep1.py", owning_node=dep_node1)
        bound2 = _make_bound_file("dep2.py", owning_node=dep_node2)
        self.mock_node_config.blame_targets_by_node = {source_node: [bound1, bound2]}
        self.mock_session_coordinator.register_node(source_node, "unit1.py")

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(sandbox_submission.BlameTool)
            param = tool.explanation_parameter
            resp = tool.execute_tool(
                _bindings(
                    {
                        tool.blame_target_parameter: _make_file_alias("dep2.py"),
                        param: sandbox_submission.BlameExplanation("Defect in dep2.py interface"),
                    }
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.dispatched_blame,
                ("unit1.py", "dep2.py", "Defect in dep2.py interface"),
            )


if __name__ == "__main__":
    unittest.main()
