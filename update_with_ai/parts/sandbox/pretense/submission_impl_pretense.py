"""Pretense test suite for sandbox submission_impl.

Tests SubmitTool, FailTool, BlameTool, and parameter types under sandbox.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, cast

from hypothesis import given, settings
from hypothesis import strategies as st

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib import file_alias, node_config
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.control.lib import coordinate
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.sandbox.lib import (
    guide_delivery,
    run_control,
    submission,
    submission_impl,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.submission_impl import (
    BlameTool,
    FailTool,
    SubmitTool,
    _BlameExplanationParamType,
    _ChangeSummaryParamType,
    _FailureExplanationParamType,
    _match_blame_target,
)


def _make_node(unit: str, role: str = "dev") -> dag_storage.DagNode:
    return dag_storage.DagNode(
        unit_address=dag_storage.UnitAddress(unit),
        role_address=dag_storage.RoleAddress(role),
    )


class MockNodeConfig:
    tier = agent_session

    def __init__(self) -> None:
        self.is_step_mode: bool = False
        self.read_write_files: Set[file_alias.BoundFile] = set()


class MockGuideDelivery:
    tier = agent_session

    def __init__(self) -> None:
        self.has_steps_remaining: bool = False


class MockRunController:
    tier = agent_session

    def __init__(self) -> None:
        self.is_passed: bool = True
        self.diagnostic_output: str = ""
        self.blame_targets_by_node: Dict[dag_storage.DagNode, Set[file_alias.BoundFile]] = {}
        self.update_verification_called = False

    def update_verification(self) -> None:
        self.update_verification_called = True


class MockSourceMetadataCoordinator:
    tier = agent_session

    def __init__(self) -> None:
        self.has_modifications: Optional[bool] = None
        self.modified_paths: Set[str] = set()

    def is_code_modified(self, path: str) -> bool:
        return path in self.modified_paths


class MockAliasManager:
    tier = agent_session

    def __init__(self, ws_root: str = "/ws") -> None:
        self.workspace_root = file_alias.file_paths.WorkspaceRoot(
            file_alias.file_paths.PathString(ws_root)
        )

    def to_alias(self, path: str) -> Any:
        return file_alias.FileAlias(file_alias.RelativePath(path))


@dataclass
class MockSubmissionOutcome:
    success: bool
    message: str


class MockSessionCoordinator:
    tier = agent_session

    def __init__(self) -> None:
        self.open_targets: Set[dag_storage.DagNode] = set()
        self.default_target: Optional[dag_storage.DagNode] = None
        self.aliases_by_node: Dict[dag_storage.DagNode, str] = {}
        self.nodes_by_alias: Dict[str, dag_storage.DagNode] = {}
        self.submit_outcome = MockSubmissionOutcome(success=True, message="Task completed successfully.")
        self.fail_outcome = MockSubmissionOutcome(success=True, message="Task failed as expected.")
        self.blame_outcome = MockSubmissionOutcome(success=True, message="Defect attributed upstream.")
        self.last_submit_args: Dict[str, Any] = {}
        self.last_fail_args: Dict[str, Any] = {}
        self.last_blame_args: Dict[str, Any] = {}
        self.registered_nodes: List[Any] = []

    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        return self.default_target

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        return self.aliases_by_node.get(node, str(node.unit_address))

    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        return self.nodes_by_alias.get(alias)

    def register_node(self, node: dag_storage.DagNode, alias: str, state: Any) -> None:
        self.registered_nodes.append((node, alias, state))

    def dispatch_submit(
        self,
        target_alias: Optional[str],
        change_summary: Optional[str],
        has_modifications: bool,
    ) -> MockSubmissionOutcome:
        self.last_submit_args = {
            "target_alias": target_alias,
            "change_summary": change_summary,
            "has_modifications": has_modifications,
        }
        return self.submit_outcome

    def dispatch_fail(
        self,
        target_alias: Optional[str],
        explanation: str,
    ) -> MockSubmissionOutcome:
        self.last_fail_args = {
            "target_alias": target_alias,
            "explanation": explanation,
        }
        return self.fail_outcome

    def dispatch_blame(
        self,
        source_alias: str,
        blame_target_alias: str,
        explanation: str,
    ) -> MockSubmissionOutcome:
        self.last_blame_args = {
            "source_alias": source_alias,
            "blame_target_alias": blame_target_alias,
            "explanation": explanation,
        }
        return self.blame_outcome


class TestSubmissionReal(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        submission_impl.__initialize__(self.registry)

        self.mock_node_config = MockNodeConfig()
        self.mock_guide_delivery = MockGuideDelivery()
        self.mock_run_controller = MockRunController()
        self.mock_metadata = MockSourceMetadataCoordinator()
        self.mock_alias_mgr = MockAliasManager()
        self.mock_coordinator = MockSessionCoordinator()

        self.registry.register_instance(self.mock_node_config, keys=[node_config.NodeConfig], tier=agent_session)
        self.registry.register_instance(self.mock_guide_delivery, keys=[guide_delivery.GuideDelivery], tier=agent_session)
        self.registry.register_instance(self.mock_run_controller, keys=[run_control.RunController], tier=agent_session)
        self.registry.register_instance(self.mock_metadata, keys=[src_metadata.SourceMetadataCoordinator], tier=agent_session)
        self.registry.register_instance(self.mock_alias_mgr, keys=[file_alias.AliasManager], tier=agent_session)
        self.registry.register_instance(self.mock_coordinator, keys=[coordinate.SessionCoordinator], tier=agent_session)

        # Register AliasManagerType singleton
        class MockAliasManagerType(tool_provider.ParameterType[file_alias.FileAlias, str]):
            @property
            def actual_type(self) -> type[file_alias.FileAlias]:
                return file_alias.FileAlias

            @property
            def wire_type(self) -> type[str]:
                return str

            def convert(self, wire_value: str) -> file_alias.FileAlias:
                return file_alias.FileAlias(file_alias.RelativePath(wire_value))

        self.registry.register_instance(MockAliasManagerType(), keys=[tool_provider.AliasManagerType], tier=agent_session)

    def test_parameter_types(self) -> None:
        # 1. _ChangeSummaryParamType
        cs_type = _ChangeSummaryParamType()
        self.assertEqual(cs_type.actual_type, submission.ChangeSummary)
        self.assertEqual(cs_type.wire_type, str)
        self.assertIsNone(cs_type.convert(None))  # type: ignore
        self.assertIsNone(cs_type.convert(""))
        self.assertIsNone(cs_type.convert("   "))
        self.assertEqual(cs_type.convert("Updated logic"), submission.ChangeSummary("Updated logic"))
        with self.assertRaises(tool_provider.ParameterConversionError):
            cs_type.convert(123)  # type: ignore

        # 2. _FailureExplanationParamType
        fe_type = _FailureExplanationParamType()
        self.assertEqual(fe_type.actual_type, submission.FailureExplanation)
        self.assertEqual(fe_type.wire_type, str)
        self.assertEqual(fe_type.convert("syntax error"), submission.FailureExplanation("syntax error"))
        with self.assertRaises(tool_provider.ParameterConversionError):
            fe_type.convert(456)  # type: ignore

        # 3. _BlameExplanationParamType
        be_type = _BlameExplanationParamType()
        self.assertEqual(be_type.actual_type, submission.BlameExplanation)
        self.assertEqual(be_type.wire_type, str)
        self.assertEqual(be_type.convert("upstream bug"), submission.BlameExplanation("upstream bug"))
        with self.assertRaises(tool_provider.ParameterConversionError):
            be_type.convert(789)  # type: ignore

    def test_submit_tool_properties(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            self.assertEqual(str(tool.name), "submit")
            self.assertTrue(len(str(tool.description)) > 0)
            self.assertEqual(str(tool.target_parameter.name), "target")
            self.assertEqual(str(tool.change_summary_parameter.name), "change_summary")
            self.assertIn(tool.target_parameter.name, tool.parameters)
            self.assertIn(tool.change_summary_parameter.name, tool.parameters)

    def test_submit_tool_step_mode_blocks_submission(self) -> None:
        self.mock_node_config.is_step_mode = True
        self.mock_guide_delivery.has_steps_remaining = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("guide step mode is active", str(resp.content).lower())
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, tool_provider.ToolName("advance"))

    def test_submit_tool_failing_verification_blocks_submission(self) -> None:
        self.mock_run_controller.is_passed = False
        self.mock_run_controller.diagnostic_output = "Line 10: SyntaxError"
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("verification is failing", str(resp.content).lower())
            self.assertIn("Line 10: SyntaxError", str(resp.content))
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, tool_provider.ToolName("check_files"))

    def test_submit_tool_success_terminating_vs_non_terminating(self) -> None:
        node1 = _make_node("unit1")
        node2 = _make_node("unit2")

        # 1. Other open targets remain -> non-terminating
        self.mock_coordinator.open_targets = {node2}
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            resp = tool.execute_tool(cast(Any, {
                tool.target_parameter: file_alias.FileAlias(file_alias.RelativePath("unit1.py")),
                tool.change_summary_parameter: submission.ChangeSummary("Done"),
            }))
            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(self.mock_coordinator.last_submit_args["target_alias"], "unit1.py")
            self.assertEqual(self.mock_coordinator.last_submit_args["change_summary"], "Done")

        # 2. No open targets remain -> terminating
        self.mock_coordinator.open_targets = set()
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)

    def test_submit_tool_modification_detection_and_matching(self) -> None:
        node = _make_node("unit1")
        alias = file_alias.FileAlias(file_alias.RelativePath("src/foo.py"))
        ws_root = file_paths.WorkspaceRoot(file_paths.PathString("/ws"))
        ws_path = file_paths.WorkspacePath(file_paths.PathString("src/foo.py"))
        bound = file_alias.BoundFile(file_alias.RelativePath("src/foo.py"), ws_path, owning_node=node)
        self.mock_node_config.read_write_files = {bound}

        # Case 1: Target provided matches rw_file, detected via is_code_modified
        self.mock_metadata.modified_paths.add("/ws/src/foo.py")
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool(cast(Any, {tool.target_parameter: alias}))
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 2: Target provided matches rw_file, detected via has_modifications attribute
        self.mock_metadata.modified_paths.clear()
        self.mock_metadata.has_modifications = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool(cast(Any, {tool.target_parameter: alias}))
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 3: Target not explicitly provided, resolves via default target
        self.mock_metadata.has_modifications = False
        self.mock_metadata.modified_paths.add("/ws/src/foo.py")
        self.mock_coordinator.default_target = node
        self.mock_coordinator.aliases_by_node[node] = "src/foo.py"
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool({})
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 4: Target not matched, checks non-matched candidate
        unmatched_alias = file_alias.FileAlias(file_alias.RelativePath("unmatched.py"))
        self.mock_metadata.modified_paths.add("/ws/unmatched.py")
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool(cast(Any, {tool.target_parameter: unmatched_alias}))
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 5: No target to check at all, falls back to scanning read_write_files
        self.mock_coordinator.default_target = None
        self.mock_metadata.modified_paths.clear()
        self.mock_metadata.modified_paths.add("/ws/src/foo.py")
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool({})
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 6: Unmatched candidate with has_modifications=True
        self.mock_metadata.modified_paths.clear()
        self.mock_metadata.has_modifications = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool(cast(Any, {tool.target_parameter: unmatched_alias}))
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 7: No target and empty read_write_files with has_modifications=True
        self.mock_node_config.read_write_files = set()
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool({})
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

        # Case 8: No target with read_write_files loop hitting has_modifications=True
        self.mock_node_config.read_write_files = {bound}
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            tool.execute_tool({})
            self.assertTrue(self.mock_coordinator.last_submit_args["has_modifications"])

    def test_submit_tool_failure_reminders(self) -> None:
        test_cases = [
            ("Session feedback is present: please fix", "modify workspace files to address feedback"),
            ("Change summary is prohibited for audit nodes", "prohibited for audit nodes"),
            ("Submitting without modifications not permitted with summary", "not permitted when submitting without"),
            ("Please provide change_summary for your changes", "provide a change_summary"),
            ("Unknown error occurred", None),
        ]
        for msg, expected_reminder in test_cases:
            self.mock_coordinator.submit_outcome = MockSubmissionOutcome(success=False, message=msg)
            with enter_phase(agent_session, registry=self.registry) as scope:
                tool = scope.get_singleton(SubmitTool)
                resp = tool.execute_tool({})
                self.assertTrue(resp.is_failed)
                if expected_reminder:
                    self.assertIsNotNone(resp.reminder)
                    self.assertIn(expected_reminder.lower(), str(resp.reminder).lower())
                else:
                    self.assertIsNone(resp.reminder)

    def test_fail_tool_properties_and_execution(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(FailTool)
            self.assertEqual(str(tool.name), "fail")
            self.assertTrue(len(str(tool.description)) > 0)
            self.assertEqual(str(tool.target_parameter.name), "target")
            self.assertEqual(str(tool.explanation_parameter.name), "explanation")
            self.assertIn(tool.target_parameter.name, tool.parameters)
            self.assertIn(tool.explanation_parameter.name, tool.parameters)

            resp = tool.execute_tool(cast(Any, {
                tool.target_parameter: file_alias.FileAlias(file_alias.RelativePath("unit1.py")),
                tool.explanation_parameter: submission.FailureExplanation("Cannot satisfy constraints"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertEqual(self.mock_coordinator.last_fail_args["target_alias"], "unit1.py")
            self.assertEqual(self.mock_coordinator.last_fail_args["explanation"], "Cannot satisfy constraints")

    def test_match_blame_target_helper(self) -> None:
        node = _make_node("unit1")
        ws_root = file_paths.WorkspaceRoot(file_paths.PathString("/ws"))
        bt1 = file_alias.BoundFile(
            file_alias.RelativePath("parts/core/lib/foo.py"),
            file_paths.WorkspacePath(file_paths.PathString("parts/core/lib/foo.py")),
            owning_node=node,
        )
        targets = [bt1]

        # 1. Exact match
        self.assertEqual(_match_blame_target("parts/core/lib/foo.py", targets), bt1)
        self.assertEqual(_match_blame_target("/parts/core/lib/foo.py", targets), bt1)

        # 2. Suffix match
        self.assertEqual(_match_blame_target("core/lib/foo.py", targets), bt1)

        # 3. Basename match (different directories, same filename)
        self.assertEqual(_match_blame_target("unrelated/dir/foo.py", targets), bt1)

        # 4. No match
        self.assertIsNone(_match_blame_target("bar.py", targets))

    def test_blame_tool_properties_and_validation(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            self.assertEqual(str(tool.name), "blame")
            self.assertTrue(len(str(tool.description)) > 0)
            self.assertEqual(str(tool.target_parameter.name), "target")
            self.assertEqual(str(tool.blame_target_parameter.name), "blame_target")
            self.assertEqual(str(tool.explanation_parameter.name), "explanation")
            self.assertIn(tool.target_parameter.name, tool.parameters)
            self.assertIn(tool.blame_target_parameter.name, tool.parameters)
            self.assertIn(tool.explanation_parameter.name, tool.parameters)

            # Multiline explanation fails
            resp = tool.execute_tool(cast(Any, {
                tool.explanation_parameter: submission.BlameExplanation("Line 1\nLine 2"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertIn("single paragraph", str(resp.content).lower())

    def test_blame_tool_active_node_and_target_resolution(self) -> None:
        node1 = _make_node("unit1")
        dep_node = _make_node("dep_unit")
        ws_root = file_paths.WorkspaceRoot(file_paths.PathString("/ws"))
        bt_dep = file_alias.BoundFile(
            file_alias.RelativePath("dep/api.py"),
            file_paths.WorkspacePath(file_paths.PathString("dep/api.py")),
            owning_node=dep_node,
        )
        self.mock_run_controller.blame_targets_by_node = {node1: {bt_dep}}
        self.mock_coordinator.open_targets = {node1}

        # 1. Successful blame execution with explicit blame_target (using basename to trigger canon normalization)
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.blame_target_parameter: file_alias.FileAlias(file_alias.RelativePath("api.py")),
                tool.explanation_parameter: submission.BlameExplanation("Defect in dep"),
            }))
            self.assertFalse(resp.is_failed)
            self.assertEqual(self.mock_coordinator.last_blame_args["blame_target_alias"], "dep/api.py")
            self.assertEqual(self.mock_coordinator.last_blame_args["explanation"], "Defect in dep")

        # 1b. Active node resolved via get_node_for_alias when blame_target is omitted
        self.mock_coordinator.open_targets = {node1, _make_node("other")}
        self.mock_coordinator.nodes_by_alias["unit1.py"] = node1
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.target_parameter: file_alias.FileAlias(file_alias.RelativePath("unit1.py")),
                tool.explanation_parameter: submission.BlameExplanation("Resolved via get_node_for_alias"),
            }))
            self.assertFalse(resp.is_failed, msg=str(resp.content))

        # 2. Successful blame with omitted blame_target (infers single configured blame target)
        self.mock_coordinator.open_targets = {node1}
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.explanation_parameter: submission.BlameExplanation("Defect inferred"),
            }))
            self.assertFalse(resp.is_failed)
            self.assertEqual(self.mock_coordinator.last_blame_args["blame_target_alias"], "dep/api.py")

        # 3. Blame target passed as target_parameter matching blame targets
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.target_parameter: file_alias.FileAlias(file_alias.RelativePath("dep/api.py")),
                tool.explanation_parameter: submission.BlameExplanation("Passed as target"),
            }))
            self.assertFalse(resp.is_failed)
            self.assertEqual(self.mock_coordinator.last_blame_args["blame_target_alias"], "dep/api.py")

        # 4. No active node found error
        self.mock_coordinator.open_targets = set()
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.explanation_parameter: submission.BlameExplanation("No active node"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertIn("no active node found", str(resp.content).lower())

        # 5. Active node has no configured blame targets
        self.mock_coordinator.open_targets = {node1}
        self.mock_run_controller.blame_targets_by_node = {node1: set()}
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.explanation_parameter: submission.BlameExplanation("No blame targets"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertIn("has no configured blame targets", str(resp.content).lower())

        # 6. Multiple blame targets and omitted blame_target
        bt2 = file_alias.BoundFile(
            file_alias.RelativePath("dep/other.py"),
            file_paths.WorkspacePath(file_paths.PathString("dep/other.py")),
            owning_node=dep_node,
        )
        self.mock_run_controller.blame_targets_by_node = {node1: {bt_dep, bt2}}
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.explanation_parameter: submission.BlameExplanation("Multiple targets"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertIn("multiple blame targets exist", str(resp.content).lower())

        # 7. Invalid blame target specified
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.blame_target_parameter: file_alias.FileAlias(file_alias.RelativePath("nonexistent.py")),
                tool.explanation_parameter: submission.BlameExplanation("Invalid"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertIn("not valid for active node", str(resp.content).lower())

        # 8. Blame dispatch failure
        self.mock_coordinator.blame_outcome = MockSubmissionOutcome(success=False, message="Blame rejected")
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            resp = tool.execute_tool(cast(Any, {
                tool.blame_target_parameter: file_alias.FileAlias(file_alias.RelativePath("dep/api.py")),
                tool.explanation_parameter: submission.BlameExplanation("Rejected blame"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertIn("Blame rejected", str(resp.content))


class TestSubmissionFuzz(unittest.TestCase):
    @settings(max_examples=25)
    @given(summary=st.text())
    def test_change_summary_conversion_fuzz(self, summary: str) -> None:
        param_type = _ChangeSummaryParamType()
        res = param_type.convert(summary)
        if not summary.strip():
            self.assertIsNone(res)
        else:
            self.assertIsNotNone(res)
            self.assertEqual(res, submission.ChangeSummary(summary.strip()))
