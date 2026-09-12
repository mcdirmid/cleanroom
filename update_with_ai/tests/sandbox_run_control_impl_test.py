"""Unit tests for sandbox_run_control_impl aligned with grounding specifications."""

import unittest
from typing import Any, List, Optional, Sequence, Set, Tuple

from lib.dag_storage import Node
from lib.file_alias import (
    AliasManager,
    BoundFile,
    DirectoryPath,
    FileAlias,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.node_config import NodeConfig
from lib.sandbox_file_editor import EditManager
from lib.sandbox_guide_delivery import Guide, GuideDelivery
from lib.sandbox_run_control import (
    AdvanceTool,
    BlameTool,
    FailTool,
    FinishTool,
    RunController,
    RunTestsTool,
    VerificationCheck,
)
from lib.sandbox_run_control_impl import (
    AdvanceTool as AdvanceToolImpl,
    BlameTool as BlameToolImpl,
    FailTool as FailToolImpl,
    FinishTool as FinishToolImpl,
    RunController as RunControllerImpl,
    RunTestsTool as RunTestsToolImpl,
    __initialize__,
)
from lib.tool_provider import (
    ActualParameterBindings,
    Response,
    String,
    StringParameterConverter,
    Tool,
    ToolManager,
    WireParameterBindings,
)


class MockToolManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.installed_tools: Set[Tool] = set()

    def install_tool(self, tool: Tool) -> None:
        self.installed_tools.add(tool)

    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> Response:
        return Response(is_failed=False, is_terminated=False, content="")


class MockStringConverter:
    tier = "agent_session"
    actual_type = str
    wire_type = String()

    def convert(self, wire_value: Any) -> str:
        return str(wire_value)


def _make_directory_path(path: str) -> DirectoryPath:
    obj = object.__new__(DirectoryPath)
    object.__setattr__(obj, "path", path)
    return obj


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class MockAliasManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.workspace_root = _make_directory_path("/workspace")
        self.actual_type = FileAlias
        self.wire_type = String()

    def convert(self, wire_value: Any) -> Any:
        return wire_value

    def sanitize_text(self, text: str) -> str:
        return text.replace("/workspace/pkg/", "")


class MockNodeConfig:
    tier = "agent_session"

    def __init__(
        self,
        blame_targets: Optional[Set[BoundFile]] = None,
        verification_checks: Optional[Sequence[VerificationCheck]] = None,
        guide: Optional[Guide] = None,
        is_step_mode: bool = True,
        feedback: Optional[Sequence[str]] = None,
        read_write_files: Optional[Set[BoundFile]] = None,
    ) -> None:
        self._blame_targets = blame_targets or set()
        self._verification_checks: Sequence[VerificationCheck] = verification_checks or []
        self._guide = guide
        self.is_step_mode = is_step_mode
        self._feedback: Sequence[str] = feedback or ()
        self._read_write_files: Set[BoundFile] = read_write_files or set()

    @property
    def read_only_files(self) -> Set[BoundFile]:
        return set()

    @property
    def read_write_files(self) -> Set[BoundFile]:
        return set(self._read_write_files)

    @property
    def guide_file(self) -> Optional[UnboundFile]:
        return None

    @property
    def templates(self) -> Set[Tuple[BoundFile, FileContent]]:
        return set()

    @property
    def guide(self) -> Optional[Guide]:
        return self._guide

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return self._blame_targets

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        return self._verification_checks

    @property
    def feedback(self) -> Sequence[str]:
        return self._feedback


class MockGuideDelivery:
    tier = "agent_session"

    def __init__(
        self,
        has_steps: bool = False,
        next_step_content: Optional[str] = None,
        guide: Optional[Guide] = None,
    ) -> None:
        self.has_steps_remaining = has_steps
        self.next_step_content = next_step_content
        self.advance_step_called = False
        self.last_verification_passed: Optional[bool] = None
        self.last_failure_diagnostics: Optional[str] = None
        self._guide: Optional[Guide] = guide
        self.initial_delivered = False

    @property
    def guide(self) -> Optional[Guide]:
        return self._guide

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[Response]:
        # Requirement: [GuideDelivery] When advancing a step with passed verification, if no steps have been delivered yet, the guide delivery emits a response containing the guide summary alone without delivering a step section.
        self.advance_step_called = True
        self.last_verification_passed = verification_passed
        self.last_failure_diagnostics = failure_diagnostics
        if not self.initial_delivered:
            self.initial_delivered = True
            summary = self._guide.summary if self._guide else "Guide Summary"
            return Response(is_failed=False, is_terminated=False, content=summary)
        if self.has_steps_remaining:
            if not verification_passed:
                return Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Step failed with: {failure_diagnostics}",
                )
            if self.next_step_content:
                return Response(is_failed=False, is_terminated=False, content=self.next_step_content)
        return None

    def parse_guide(self, content: FileContent) -> Guide:
        return Guide(summary="", sections=[])


class MockEditManager:
    tier = "agent_session"

    def __init__(self, has_modifications: bool = False, file_update_revision: int = 0) -> None:
        self.has_modifications = has_modifications
        self.file_update_revision = file_update_revision

    def materialize_templates(self) -> None:
        pass


class MockVerificationCheck(VerificationCheck):
    def __init__(self, passes: bool = True, diagnostic: str = "") -> None:
        self.passes = passes
        self.diagnostic = diagnostic
        self.called = False
        self.call_count = 0

    def verify(self) -> Tuple[bool, str]:
        self.called = True
        self.call_count += 1
        return self.passes, self.diagnostic


class SandboxRunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        node = Node(address="//pkg:upstream")
        self.blame_target_file = ReadOnlyFile(
            short_name="dep.py",
            workspace_path=_make_workspace_path("pkg/dep.py"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.tool_mgr = MockToolManager()
        self.str_conv = MockStringConverter()
        self.alias_mgr = MockAliasManager()
        self.node_cfg = MockNodeConfig(
            blame_targets={self.blame_target_file},
            is_step_mode=True,
            guide=Guide(summary="Guide Summary", sections=[]),
        )
        self.guide_del = MockGuideDelivery(guide=Guide(summary="Guide Summary", sections=[]))
        self.edit_mgr = MockEditManager()

        self.registry.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")
        self.registry.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")
        self.registry.register_instance(self.guide_del, keys=[GuideDelivery], tier="agent_session")
        self.registry.register_instance(self.edit_mgr, keys=[EditManager], tier="agent_session")

    def test_run_controller_initialization_with_blame_and_step_mode(self) -> None:
        """CUJ: RunController installs advance, finish, fail, and blame tools when step mode and blame targets exist."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: Verification checks exposed by the run controller include the session verification checks from node config.
            # Requirement: [RunController] The run controller exposes verification checks that validate session criteria.
            self.assertEqual(ctrl.verification_checks, [])
            # Requirement: The run controller unconditionally installs the finish tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            # Requirement: [RunController] The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
            # Requirement: [RunController] The run controller installs a finish tool that concludes the session upon passing verification and enforces change documentation.
            # Requirement: [RunController] The run controller installs a fail tool that terminates the run in failure.
            # Requirement: [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: [RunController] The run controller installs a blame tool when blame targets are configured, attributing task failure to an upstream dependency node.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertIn("advance", tool_names)
            # Requirement: The finish tool is named `finish`, accepting a text change summary parameter, and shares a constant suppression key `finish`.
            self.assertIn("finish", tool_names)
            # Requirement: The fail tool is named `fail`.
            self.assertIn("fail", tool_names)
            # Requirement: The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`.
            self.assertIn("run_tests", tool_names)
            # Requirement: The blame tool is named `blame`.
            self.assertIn("blame", tool_names)

    def test_run_controller_initialization_without_blame_and_step_mode(self) -> None:
        """CUJ: RunController omits advance and blame tools when step mode is inactive and blame targets are empty."""
        reg = LifecycleRegistry()
        __initialize__(reg)
        tool_mgr = MockToolManager()
        cfg = MockNodeConfig(blame_targets=set(), is_step_mode=False, guide=None)
        reg.register_instance(tool_mgr, keys=[ToolManager], tier="agent_session")
        reg.register_instance(self.str_conv, keys=[StringParameterConverter], tier="agent_session")
        reg.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        reg.register_instance(cfg, keys=[NodeConfig], tier="agent_session")
        reg.register_instance(self.guide_del, keys=[GuideDelivery], tier="agent_session")
        reg.register_instance(self.edit_mgr, keys=[EditManager], tier="agent_session")

        with enter_phase("agent_session", registry=reg) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: The run controller unconditionally installs the finish tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            tool_names = {t.name for t in tool_mgr.installed_tools}
            self.assertIn("finish", tool_names)
            self.assertIn("fail", tool_names)
            self.assertIn("run_tests", tool_names)
            self.assertNotIn("advance", tool_names)
            self.assertNotIn("blame", tool_names)

    def test_run_controller_evaluate_verification_caching(self) -> None:
        """CUJ: RunController caches verification results and reuses them when file revision unchanged."""
        check = MockVerificationCheck(passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:5")
        self.node_cfg._verification_checks = [check]
        self.edit_mgr.file_update_revision = 1

        with enter_phase("agent_session", registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunControllerImpl)
            # First evaluation executes checks and caches result
            # Requirement: Evaluation of verification checks is cached alongside the edit manager file update revision.
            # Requirement: [RunController] The run controller caches verification evaluation results alongside the edit manager file update revision, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.
            # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation.
            passed1, diag1 = ctrl.evaluate_verification()
            self.assertFalse(passed1)
            self.assertEqual(check.call_count, 1)
            self.assertIn("dep.py:5", diag1)

            # Re-evaluation with same file revision reuses cached result without re-executing checks
            # Requirement: When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
            passed2, diag2 = ctrl.evaluate_verification()
            self.assertFalse(passed2)
            self.assertEqual(check.call_count, 1)
            self.assertEqual(diag1, diag2)

            # File update revision changes -> re-executes verification checks
            self.edit_mgr.file_update_revision = 2
            check.passes = True
            passed3, diag3 = ctrl.evaluate_verification()
            self.assertTrue(passed3)
            self.assertEqual(check.call_count, 2)

    def test_advance_tool_first_call_delivers_initial_summary_without_updating_verification(self) -> None:
        """CUJ: On first execution, AdvanceTool delivers initial guide summary without updating verification results."""
        self.guide_del.has_steps_remaining = True
        self.guide_del._guide = Guide(summary="Initial Guide Summary", sections=[])
        vcheck = MockVerificationCheck(passes=False, diagnostic="Failing check")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertEqual(adv.name, "advance")
            self.assertEqual(len(adv.parameters), 0)
            self.assertIsInstance(adv.description, str)

            b = ActualParameterBindings(bindings=set())
            # Requirement: On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
            resp = adv.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Initial Guide Summary", resp.content)
            self.assertEqual(vcheck.call_count, 0)
            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_subsequent_call_failing_verification_specifies_run_tests_followup(self) -> None:
        """CUJ: On subsequent execution, AdvanceTool fails when verification fails, specifying run_tests follow-up."""
        self.guide_del.has_steps_remaining = True
        self.guide_del._guide = Guide(summary="Initial Summary", sections=[])
        vcheck = MockVerificationCheck(passes=False, diagnostic="Failure in /workspace/pkg/dep.py:10")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())

            # First execution delivers initial summary without updating verification
            # Requirement: On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
            resp1 = adv.execute_tool(b)
            self.assertFalse(resp1.is_failed)
            self.assertEqual(vcheck.call_count, 0)

            # Subsequent execution updates verification results and fails
            # Requirement: On subsequent executions, executing the advance tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool.
            resp2 = adv.execute_tool(b)
            self.assertTrue(resp2.is_failed)
            self.assertFalse(resp2.is_terminated)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNotNone(resp2.reminder)
            self.assertIsNotNone(resp2.follow_up_tool_call)
            assert resp2.follow_up_tool_call is not None
            self.assertEqual(resp2.follow_up_tool_call.tool_name, "run_tests")
            self.assertEqual(len(resp2.follow_up_tool_call.wire_parameter_bindings.bindings), 0)
            self.assertEqual(resp2.suppression_key, "advance")

    def test_advance_tool_subsequent_call_passing_verification_advances_guide_step(self) -> None:
        """CUJ: On subsequent execution with passing verification, AdvanceTool advances guide step when steps remain."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 2 Instructions"
        self.guide_del._guide = Guide(summary="Summary", sections=[])
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())

            # First execution delivers initial summary
            # Requirement: On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
            adv.execute_tool(b)

            # Subsequent execution with passing verification
            # Requirement: On subsequent executions, executing the advance tool updates verification results if outdated.
            # Requirement: Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
            resp = adv.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Step 2 Instructions", resp.content)
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_no_steps_remaining_files_modified_requires_finish(self) -> None:
        """CUJ: AdvanceTool fails with reminder to call finish tool when no steps remain and files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())

            # First execution delivers initial summary
            adv.execute_tool(b)

            # Subsequent execution when no steps remain and workspace files modified
            # Requirement: Tool execution fails with a reminder to call the finish tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_no_steps_remaining_no_files_modified_specifies_finish_followup(self) -> None:
        """CUJ: AdvanceTool specifies finish follow-up tool call when no steps remain and no files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())

            # First execution delivers initial summary
            adv.execute_tool(b)

            # Subsequent execution when no steps remain and no workspace files modified
            # Requirement: Tool execution produces a response specifying a follow-up execution of the finish tool without a change summary when verification is passing, no steps remain, and no workspace files were modified.
            resp = adv.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "finish")
            self.assertEqual(len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0)
            self.assertEqual(resp.suppression_key, "advance")

    def test_finish_tool_parameters_and_converters(self) -> None:
        """CUJ: FinishTool declares change_summary parameter with string converter."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            # Requirement: The finish tool is named `finish`, accepting a text change summary parameter, and shares a constant suppression key `finish`.
            self.assertEqual(finish.name, "finish")
            self.assertIsInstance(finish.description, str)
            self.assertEqual(finish.parameters, {finish.change_summary})
            # Requirement: The finish tool change summary parameter uses a string parameter converter to accept text.
            self.assertIs(finish.change_summary.parameter_converter, self.str_conv)

    def test_finish_tool_fails_when_steps_remain_specifies_advance_followup(self) -> None:
        """CUJ: FinishTool fails when guide steps remain and specifies advance as follow-up."""
        self.guide_del.has_steps_remaining = True
        vcheck = MockVerificationCheck(passes=False)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the finish tool updates verification results if outdated.
            # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call.
            # Requirement: [FinishTool] Executing the finish tool while guide steps remain fails with a reminder to execute the advance tool, specifying the advance tool as a follow-up tool call.
            resp = finish.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "advance")
            self.assertEqual(len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0)
            # Requirement: The finish tool is named `finish`, accepting a text change summary parameter, and shares a constant suppression key `finish`.
            self.assertEqual(resp.suppression_key, "finish")

    def test_finish_tool_fails_when_verification_failing_specifies_run_tests_followup(self) -> None:
        """CUJ: FinishTool fails when verification fails and specifies run_tests follow-up."""
        self.guide_del.has_steps_remaining = False
        self.node_cfg._feedback = ["Previous feedback"]
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:20")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the finish tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool.
            resp = finish.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "run_tests")
            self.assertEqual(len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0)
            self.assertEqual(resp.suppression_key, "finish")

    def test_finish_tool_fails_when_feedback_present_and_no_files_modified(self) -> None:
        """CUJ: FinishTool fails when feedback is present and no workspace files were modified."""
        self.guide_del.has_steps_remaining = False
        self.node_cfg._feedback = ["Must address edge cases"]
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
            resp = finish.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "finish")

    def test_finish_tool_fails_when_files_modified_and_summary_omitted(self) -> None:
        """CUJ: FinishTool fails when workspace files modified but change summary omitted."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
            resp = finish.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "finish")

    def test_finish_tool_fails_when_no_files_modified_and_summary_provided(self) -> None:
        """CUJ: FinishTool fails when no workspace files modified but change summary provided."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings={(finish.change_summary, "Unneeded change summary")})
            # Requirement: Tool execution fails if no workspace files were modified and the change summary is provided, reminding the agent that a change summary can only be provided when workspace files were modified.
            resp = finish.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "finish")

    def test_finish_tool_succeeds_and_terminates_session(self) -> None:
        """CUJ: FinishTool succeeds and terminates session when criteria met and verification passes."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings={(finish.change_summary, "Added new feature")})
            # Requirement: Tool execution produces a terminating response indicating that the session completed successfully when verification is passing and all completion criteria are met.
            resp = finish.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Added new feature", resp.content)
            self.assertEqual(resp.suppression_key, "finish")

    def test_fail_tool(self) -> None:
        """CUJ: FailTool produces terminating failure response carrying explanation."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            fail_tool = scope.get_singleton(FailToolImpl)
            self.assertIsInstance(fail_tool.description, str)
            self.assertGreater(len(fail_tool.parameters), 0)
            # Requirement: The fail tool is named `fail`.
            self.assertEqual(fail_tool.name, "fail")
            # Requirement: The fail tool explanation parameter uses a string parameter converter to accept text.
            self.assertIs(fail_tool.explanation.parameter_converter, self.str_conv)

            b = ActualParameterBindings(bindings={(fail_tool.explanation, "Cannot solve bug")})
            # Requirement: Executing the fail tool produces a terminating response carrying the explanation.
            resp = fail_tool.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Cannot solve bug", resp.content)

    def test_blame_tool(self) -> None:
        """CUJ: BlameTool validates target and produces terminating feedback attribution."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            blame_tool = scope.get_singleton(BlameToolImpl)
            self.assertIsInstance(blame_tool.description, str)
            self.assertGreater(len(blame_tool.parameters), 0)
            # Requirement: The blame tool is named `blame`.
            self.assertEqual(blame_tool.name, "blame")
            # Requirement: The blame tool blame target parameter uses the alias manager to convert a file alias.
            self.assertIs(blame_tool.blame_target.parameter_converter, self.alias_mgr)
            # Requirement: The blame tool explanation parameter uses a string parameter converter to accept text.
            self.assertIs(blame_tool.explanation.parameter_converter, self.str_conv)

            # Invalid target fails
            unrecognized = ReadOnlyFile(
                short_name="unknown.py",
                workspace_path=_make_workspace_path("unknown.py"),
                owning_node=Node(address="//pkg:unknown"),
            )
            b_invalid = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, unrecognized),
                    (blame_tool.explanation, "Broken"),
                }
            )
            # Requirement: Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
            resp_inv = blame_tool.execute_tool(b_invalid)
            self.assertTrue(resp_inv.is_failed)
            self.assertIsNotNone(resp_inv.reminder)

            # Valid target terminates with Blamed attribution
            b_valid = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, self.blame_target_file),
                    (blame_tool.explanation, "Broken type signature"),
                }
            )
            # Requirement: On successful blame tool execution, the response indicates termination attributing feedback to the blame target owning node.
            # Requirement: [BlameTool] Executing the blame tool fails if the target is not one of the blame targets, and terminates the run with diagnostic feedback attributed to the owning node on success.
            resp_val = blame_tool.execute_tool(b_valid)
            self.assertFalse(resp_val.is_failed)
            self.assertTrue(resp_val.is_terminated)
            self.assertIn("dep.py: Broken type signature", resp_val.content)

    def test_finish_fails_when_feedback_present_and_no_modifications(self) -> None:
        """CUJ: FinishTool fails when feedback is present and no workspace files were modified, and advance tool is not installed."""
        rw_file = ReadWriteFile(
            short_name="target.py",
            workspace_path=_make_workspace_path("target.py"),
            owning_node=Node(address="//pkg:target"),
        )
        custom_node_cfg = MockNodeConfig(
            guide=None,
            is_step_mode=False,
            feedback=["Requirement X not met"],
            read_write_files={rw_file},
        )
        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")
        reg.register_instance(self.str_conv, keys=[StringParameterConverter], tier="agent_session")
        reg.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        reg.register_instance(self.edit_mgr, keys=[EditManager], tier="agent_session")
        reg.register_instance(self.guide_del, keys=[GuideDelivery], tier="agent_session")
        reg.register_instance(custom_node_cfg, keys=[NodeConfig], tier="agent_session")

        with enter_phase("agent_session", registry=reg) as scope:
            rc = scope.get_singleton(RunControllerImpl)
            rc.initialize()
            finish = scope.get_singleton(FinishToolImpl)
            b = ActualParameterBindings(bindings=set())

            # Requirement: The run controller unconditionally installs the finish tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            # AdvanceTool is NOT installed because is_step_mode is False
            self.assertNotIn("advance", {t.name for t in self.tool_mgr.installed_tools})

            # Finish fails because feedback is present and no modifications made
            # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
            finish_resp = finish.execute_tool(b)
            self.assertTrue(finish_resp.is_failed)
            self.assertIn("Workspace files must be modified to address feedback or the fail tool must be used.", finish_resp.reminder or "")

            # When modifications are made, finish with change summary succeeds
            # Requirement: Tool execution produces a terminating response indicating that the session completed successfully when verification is passing and all completion criteria are met.
            self.edit_mgr.has_modifications = True
            finish_with_summary = ActualParameterBindings(
                bindings={(finish.change_summary, "Addressed feedback")}
            )
            finish_ok = finish.execute_tool(finish_with_summary)
            self.assertFalse(finish_ok.is_failed)
            self.assertTrue(finish_ok.is_terminated)

    def test_run_tests_tool_failing_verification_presents_diagnostics_and_instructions(self) -> None:
        """CUJ: RunTestsTool fails when verification fails, presenting sanitized diagnostics and failure instructions."""
        self.guide_del._guide = Guide(
            summary="Summary",
            sections=[],
            verification_failure="Inspect diagnostics and fix workspace files.",
        )
        vcheck = MockVerificationCheck(passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:12")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            # Requirement: The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`.
            self.assertEqual(run_tests.name, "run_tests")
            self.assertEqual(run_tests.parameters, set())
            self.assertIsInstance(run_tests.description, str)

            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the run tests tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
            resp = run_tests.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("dep.py:12", resp.content)
            self.assertNotIn("/workspace/pkg/", resp.content)
            self.assertIn("## Verification failure\nInspect diagnostics and fix workspace files.", resp.content)
            # Requirement: The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`.
            self.assertEqual(resp.suppression_key, "run_tests")

    def test_run_tests_tool_passing_verification_presents_results(self) -> None:
        """CUJ: RunTestsTool produces a passing response when verification passes."""
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the run tests tool updates verification results if outdated.
            # Requirement: Tool execution produces a response presenting passing verification results when verification passes.
            resp = run_tests.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Verification passed", resp.content)
            # Requirement: The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`.
            self.assertEqual(resp.suppression_key, "run_tests")

    def test_run_tests_tool_updates_verification_results_if_outdated(self) -> None:
        """CUJ: RunTestsTool caches verification results and re-evaluates when workspace files updated."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Error 1")
        self.node_cfg._verification_checks = [vcheck]
        self.edit_mgr.file_update_revision = 1

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            b = ActualParameterBindings(bindings=set())

            # First execution runs checks
            # Requirement: Executing the run tests tool updates verification results if outdated.
            resp1 = run_tests.execute_tool(b)
            self.assertTrue(resp1.is_failed)
            self.assertEqual(vcheck.call_count, 1)

            # Second execution without file updates reuses cache
            resp2 = run_tests.execute_tool(b)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(vcheck.call_count, 1)

            # Third execution after file update re-evaluates
            self.edit_mgr.file_update_revision = 2
            vcheck.passes = True
            resp3 = run_tests.execute_tool(b)
            self.assertFalse(resp3.is_failed)
            self.assertEqual(vcheck.call_count, 2)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
# - [Tool] When a parameter is required, an argument must be supplied for tool execution.
