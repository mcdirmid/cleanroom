"""Unit tests for sandbox_run_control_impl aligned with grounding specifications."""

import unittest
from typing import Any, List, Mapping, Optional, Sequence, Set, Tuple

from update_with_ai.parts.dag.lib.dag_storage import Dependency, Node
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib.agent_file_alias import (
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
from update_with_ai.parts.agent.lib.agent_node_config import (
    Guide,
    NodeConfig,
    VerificationCheck,
)
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_guide_delivery import GuideDelivery
from update_with_ai.parts.sandbox.lib.sandbox_run_control import (
    AdvanceTool,
    BlameTool,
    FailTool,
    RunController,
    RunTestsTool,
    SubmitTool,
)
from update_with_ai.parts.sandbox.lib.sandbox_run_control_impl import (
    AdvanceTool as AdvanceToolImpl,
    BlameTool as BlameToolImpl,
    FailTool as FailToolImpl,
    RunController as RunControllerImpl,
    RunTestsTool as RunTestsToolImpl,
    SubmitTool as SubmitToolImpl,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib import template_format
from update_with_ai.parts.sandbox.lib.tool_provider import (
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

    def execute_tool(
        self, name: str, wire_parameter_bindings: WireParameterBindings
    ) -> Response:
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
        blame_targets_by_node: Optional[Mapping[Node, Set[BoundFile]]] = None,
        verification_checks: Optional[Sequence[VerificationCheck]] = None,
        verification_checks_by_node: Optional[
            Mapping[Node, Sequence[VerificationCheck]]
        ] = None,
        guide: Optional[Guide] = None,
        is_step_mode: bool = True,
        feedback: Optional[Sequence[str]] = None,
        read_write_files: Optional[Set[BoundFile]] = None,
        verification_success_message: Optional[str] = None,
        src_file_alias_by_node: Optional[Mapping[Node, str]] = None,
    ) -> None:
        self._blame_targets = blame_targets or set()
        self.blame_targets_by_node: Mapping[Node, Set[BoundFile]] = (
            blame_targets_by_node or {}
        )
        self._verification_checks: Sequence[VerificationCheck] = (
            verification_checks or []
        )
        self.verification_checks_by_node: Mapping[Node, Sequence[VerificationCheck]] = (
            verification_checks_by_node or {}
        )
        self._guide = guide
        self.is_step_mode = is_step_mode
        self._feedback: Sequence[str] = feedback or ()
        self._read_write_files: Set[BoundFile] = read_write_files or set()
        self._verification_success_message = verification_success_message
        self.src_file_alias_by_node: Mapping[Node, str] = src_file_alias_by_node or {}

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
    def verification_success_message(self) -> Optional[str]:
        return self._verification_success_message

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
                return Response(
                    is_failed=False, is_terminated=False, content=self.next_step_content
                )
        return None

    def parse_guide(self, content: FileContent) -> Guide:
        return Guide(summary="", sections=[])


class MockEditManager:
    tier = "agent_session"

    def __init__(
        self, has_modifications: bool = False, file_update_revision: int = 0
    ) -> None:
        self.has_modifications = has_modifications
        self.file_update_revision = file_update_revision
        self._locked_files: Set[Any] = set()

    @property
    def locked_files(self) -> Set[Any]:
        return set(self._locked_files)

    def lock_file(self, file: Any) -> None:
        self._locked_files.add(file)

    def unlock_file(self, file: Any) -> None:
        self._locked_files.discard(file)

    def materialize_templates(self) -> None:
        pass


class TargetFileObj:
    def __init__(self, short_name: str) -> None:
        self.short_name = short_name


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


class MockDagStorage:
    tier = "system"

    def __init__(self) -> None:
        self.dependencies: dict[Node, Set[Dependency]] = {}

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return self.dependencies.get(node, set())


class MockTemplateFormatter:
    tier = "agent_session"

    def format_template(self, text: str, parameters: Any) -> str:
        nodes = parameters.get("nodes", [])
        if "<!-- for: node in nodes -->" in text:
            lines = ["Remaining open files:"]
            for n in nodes:
                lines.append(f"- `{n['src_alias']}`")
            return "\n".join(lines)
        return text


class SandboxRunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        node = Node(unit_address="//pkg:upstream", role_address="lib")
        self.blame_target_file = ReadOnlyFile(
            short_name="dep.py",
            workspace_path=_make_workspace_path("pkg/dep.py"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage, keys=[dag_storage.DagStorage], tier="system"
        )

        self.tool_mgr = MockToolManager()
        self.str_conv = MockStringConverter()
        self.alias_mgr = MockAliasManager()
        self.tmpl_formatter = MockTemplateFormatter()
        self.node_cfg = MockNodeConfig(
            blame_targets={self.blame_target_file},
            is_step_mode=True,
            guide=Guide(summary="Guide Summary", sections=[]),
        )
        self.guide_del = MockGuideDelivery(
            guide=Guide(summary="Guide Summary", sections=[])
        )
        self.edit_mgr = MockEditManager()

        self.registry.register_instance(
            self.tool_mgr, keys=[ToolManager], tier="agent_session"
        )
        self.registry.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(
            self.alias_mgr, keys=[AliasManager], tier="agent_session"
        )
        self.registry.register_instance(
            self.tmpl_formatter,
            keys=[template_format.TemplateFormatter],
            tier="agent_session",
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier="agent_session"
        )
        self.registry.register_instance(
            self.guide_del, keys=[GuideDelivery], tier="agent_session"
        )
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier="agent_session"
        )

    def test_run_controller_initialization_with_blame_and_step_mode(self) -> None:
        """CUJ: RunController installs advance, submit, fail, and blame tools when step mode and blame targets exist."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: Verification checks exposed by the run controller include the session verification checks from node config.
            # Requirement: [RunController] The run controller exposes verification checks that validate session criteria.
            self.assertEqual(ctrl.verification_checks, [])
            # Requirement: The run controller unconditionally installs the submit tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            # Requirement: [RunController] The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
            # Requirement: [RunController] The run controller installs a submit tool that concludes target processing upon passing verification and enforces change documentation.
            # Requirement: [RunController] The run controller installs a fail tool that terminates the run in failure.
            # Requirement: [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: [RunController] The run controller installs a blame tool when blame targets are configured, attributing task failure to an upstream dependency node.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertIn("advance", tool_names)
            # Requirement: The submit tool is named `submit`, accepting an optional target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
            self.assertIn("submit", tool_names)
            # Requirement: The fail tool is named `fail`.
            self.assertIn("fail", tool_names)
            # Requirement: The run tests tool is named `run_tests`, accepting an optional target parameter, and shares a constant suppression key `run_tests`.
            self.assertIn("run_tests", tool_names)
            # Requirement: The blame tool is named `blame`.
            self.assertIn("blame", tool_names)

    def test_run_controller_initialization_without_blame_and_step_mode(self) -> None:
        """CUJ: RunController omits advance and blame tools when step mode is inactive and blame targets are empty."""
        reg = LifecycleRegistry()
        __initialize__(reg)
        tool_mgr = MockToolManager()
        cfg = MockNodeConfig(blame_targets=set(), is_step_mode=False, guide=None)
        reg.register_instance(
            self.storage, keys=[dag_storage.DagStorage], tier="system"
        )
        reg.register_instance(tool_mgr, keys=[ToolManager], tier="agent_session")
        reg.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier="agent_session"
        )
        reg.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        reg.register_instance(
            self.tmpl_formatter,
            keys=[template_format.TemplateFormatter],
            tier="agent_session",
        )
        reg.register_instance(cfg, keys=[NodeConfig], tier="agent_session")
        reg.register_instance(
            self.guide_del, keys=[GuideDelivery], tier="agent_session"
        )
        reg.register_instance(self.edit_mgr, keys=[EditManager], tier="agent_session")

        with enter_phase("agent_session", registry=reg) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: The run controller unconditionally installs the submit tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            tool_names = {t.name for t in tool_mgr.installed_tools}
            self.assertIn("submit", tool_names)
            self.assertIn("fail", tool_names)
            self.assertIn("run_tests", tool_names)
            self.assertNotIn("advance", tool_names)
            self.assertNotIn("blame", tool_names)

    def test_run_controller_evaluate_verification_caching(self) -> None:
        """CUJ: RunController caches verification results and reuses them when file revision unchanged."""
        check = MockVerificationCheck(
            passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:5"
        )
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

            # Modifying workspace files updates revision and triggers re-execution
            self.edit_mgr.file_update_revision = 2
            check.passes = True
            passed3, _ = ctrl.evaluate_verification()
            self.assertTrue(passed3)
            self.assertEqual(check.call_count, 2)

    def test_advance_tool_initial_delivery_omits_verification_update(self) -> None:
        """CUJ: AdvanceTool delivers initial guide summary on first execution without evaluating verification checks."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Failing initial check")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertEqual(advance.name, "advance")
            self.assertEqual(advance.parameters, set())
            self.assertIsInstance(advance.description, str)

            # Requirement: On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
            resp = advance.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "Guide Summary")
            self.assertEqual(vcheck.call_count, 0)
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_subsequent_execution_fails_when_verification_failing(
        self,
    ) -> None:
        """CUJ: Subsequent advance call evaluates verification and fails when verification fails."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Syntax error")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: On subsequent executions, executing the advance tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool with reasoning text indicating that verification results must be inspected before advancing.
            resp = advance.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNotNone(resp.reminder)
            assert resp.reminder is not None
            self.assertIn("run tests tool should be called first", resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "run_tests")
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "Verification results must be inspected before advancing.",
            )

    def test_advance_tool_steps_remaining_delivers_next_step(self) -> None:
        """CUJ: AdvanceTool advances guide step and delivers next step section when verification passes."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 1: Write initial test case"
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
            resp = advance.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "Step 1: Write initial test case")
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_no_steps_remaining_files_modified_requires_submit(
        self,
    ) -> None:
        """CUJ: AdvanceTool fails with reminder to call submit tool when no steps remain and files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: Tool execution fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
            resp = advance.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            assert resp.reminder is not None
            self.assertIn("submit", resp.reminder)
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_no_steps_remaining_no_files_modified_specifies_submit_followup(
        self,
    ) -> None:
        """CUJ: AdvanceTool specifies submit follow-up tool call when no steps remain and no files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: Tool execution produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.
            resp = advance.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "submit")
            self.assertEqual(
                len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0
            )
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "All guide steps are complete.",
            )
            self.assertEqual(resp.suppression_key, "advance")

    def test_submit_tool_parameters_and_converters(self) -> None:
        """CUJ: SubmitTool declares target and change_summary parameters with converters."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            # Requirement: The submit tool is named `submit`, accepting an optional target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
            self.assertEqual(submit.name, "submit")
            self.assertIsInstance(submit.description, str)
            self.assertEqual(submit.parameters, {submit.target, submit.change_summary})
            # Requirement: The submit tool change summary parameter uses a string parameter converter to accept text.
            self.assertIs(submit.change_summary.parameter_converter, self.str_conv)
            self.assertIs(submit.target.parameter_converter, self.alias_mgr)

    def test_submit_tool_fails_when_steps_remain_specifies_advance_followup(
        self,
    ) -> None:
        """CUJ: SubmitTool fails when guide steps remain and specifies advance as follow-up."""
        self.guide_del.has_steps_remaining = True
        vcheck = MockVerificationCheck(passes=False)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the submit tool updates verification results if outdated.
            # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "advance")
            self.assertEqual(
                len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0
            )
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "Remaining guide steps must be completed before finishing.",
            )
            # Requirement: The submit tool is named `submit`, accepting an optional target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_fails_when_verification_failing_specifies_run_tests_followup(
        self,
    ) -> None:
        """CUJ: SubmitTool fails when verification fails and specifies run_tests follow-up."""
        self.guide_del.has_steps_remaining = False
        self.node_cfg._feedback = ["Previous feedback"]
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(
            passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:20"
        )
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the submit tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool with reasoning text indicating that verification results must be inspected before submitting.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "run_tests")
            self.assertEqual(
                len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0
            )
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "Verification results must be inspected before submitting.",
            )
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_fails_when_feedback_present_and_no_files_modified(
        self,
    ) -> None:
        """CUJ: SubmitTool fails when feedback is present and no workspace files were modified."""
        self.guide_del.has_steps_remaining = False
        self.node_cfg._feedback = ["Must address edge cases"]
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_fails_when_files_modified_and_summary_omitted(self) -> None:
        """CUJ: SubmitTool fails when workspace files modified but change summary omitted."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_succeeds_when_no_files_modified_and_summary_provided(
        self,
    ) -> None:
        """CUJ: SubmitTool succeeds and terminates when no workspace files modified but change summary provided."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(
                bindings={(submit.change_summary, "Unneeded change summary")}
            )
            # Requirement: Tool execution marks the target as submitted, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp = submit.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Unneeded change summary", resp.content)
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_succeeds_and_terminates_session(self) -> None:
        """CUJ: SubmitTool succeeds and terminates session when criteria met and verification passes."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(
                bindings={(submit.change_summary, "Added new feature")}
            )
            # Requirement: Tool execution marks the target as submitted, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp = submit.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Added new feature", resp.content)
            self.assertEqual(resp.suppression_key, "submit")

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

            b = ActualParameterBindings(
                bindings={(fail_tool.explanation, "Cannot solve bug")}
            )
            # Requirement: Executing the fail tool marks the target as failed and in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
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
                owning_node=Node(unit_address="//pkg:unknown", role_address="lib"),
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
            # Requirement: On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp_val = blame_tool.execute_tool(b_valid)
            self.assertFalse(resp_val.is_failed)
            self.assertTrue(resp_val.is_terminated)
            self.assertIn("dep.py: Broken type signature", resp_val.content)

            # Backward compatibility: raw_target provided instead of blame_target
            b_legacy = ActualParameterBindings(
                bindings={
                    (blame_tool.target, self.blame_target_file),
                    (blame_tool.explanation, "Legacy blame call"),
                }
            )
            # Requirement: On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp_leg = blame_tool.execute_tool(b_legacy)
            self.assertFalse(resp_leg.is_failed)
            self.assertTrue(resp_leg.is_terminated)
            self.assertIn("dep.py: Legacy blame call", resp_leg.content)

    def test_multi_node_submit_and_in_session_dependencies(self) -> None:
        """CUJ: Multi-node session enforces in-session dependency order, validates targets, and marks completion."""
        node1 = Node(unit_address="//pkg:unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:unit2", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {node1: "unit1.py", node2: "unit2.py"}
        self.storage.dependencies[node2] = {Dependency(node=node1)}

        vcheck1 = MockVerificationCheck(passes=True)
        vcheck2 = MockVerificationCheck(passes=True)
        self.node_cfg.verification_checks_by_node = {node1: [vcheck1], node2: [vcheck2]}
        self.guide_del.has_steps_remaining = False

        with enter_phase("agent_session", registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # Address lookup by unit address fallback
            self.assertEqual(rc.get_node_for_alias("//pkg:unit1"), node1)

            # 1. Submitting without target in multi-target session fails
            b_no_target = ActualParameterBindings(bindings=set())
            # Requirement: In multi-target sessions, tool execution fails when the target parameter is omitted or does not match an open session target, reminding the agent to specify an open target.
            resp1 = submit.execute_tool(b_no_target)
            self.assertTrue(resp1.is_failed)
            self.assertIn("Target parameter must be specified", resp1.content)

            # 2. Submitting unknown target fails
            b_unknown = ActualParameterBindings(
                bindings={(submit.target, "unknown.py")}
            )
            # Requirement: In multi-target sessions, tool execution fails when the target parameter is omitted or does not match an open session target, reminding the agent to specify an open target.
            resp2 = submit.execute_tool(b_unknown)
            self.assertTrue(resp2.is_failed)
            self.assertIn("is not an open target", resp2.content)

            # 3. Submitting node2 before node1 fails due to in-session dependency
            b_dep_first = ActualParameterBindings(
                bindings={(submit.target, "unit2.py")}
            )
            # Requirement: Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.
            resp3 = submit.execute_tool(b_dep_first)
            self.assertTrue(resp3.is_failed)
            self.assertIn("must be submitted before `unit2.py`", resp3.content)

            # 4. Submitting node1 succeeds: marks node1 SUBMITTED, leaves session open with remaining open files
            b_node1 = ActualParameterBindings(
                bindings={
                    (submit.target, TargetFileObj("unit1.py")),
                    (submit.change_summary, "Cleaned unit 1"),
                }
            )
            # Requirement: Tool execution marks the target as submitted, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp4 = submit.execute_tool(b_node1)
            self.assertFalse(resp4.is_failed)
            self.assertFalse(resp4.is_terminated)
            self.assertEqual(rc.get_node_state(node1), "SUBMITTED")
            self.assertIn("Target `unit1.py` submitted successfully.", resp4.content)
            self.assertIn("- `unit2.py`", resp4.content)

            # 5. Submitting node2 succeeds and terminates session without summary
            b_node2 = ActualParameterBindings(
                bindings={(submit.target, TargetFileObj("unit2.py"))}
            )
            # Requirement: Tool execution marks the target as submitted, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp5 = submit.execute_tool(b_node2)
            self.assertFalse(resp5.is_failed)
            self.assertTrue(resp5.is_terminated)
            self.assertEqual(rc.get_node_state(node2), "SUBMITTED")
            self.assertIn("Session completed successfully.", resp5.content)
            self.assertEqual(rc.format_open_targets_reminder(), "")

    def test_multi_node_fail_blocks_dependents_and_terminates(self) -> None:
        """CUJ: Multi-node fail marks target FAILED, dependents BLOCKED, and terminates when no open nodes remain."""
        node1 = Node(unit_address="//pkg:f_unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:f_unit2", role_address="lib")
        node3 = Node(unit_address="//pkg:f_unit3", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "f_unit1.py",
            node2: "f_unit2.py",
            node3: "f_unit3.py",
        }
        self.storage.dependencies[node2] = {Dependency(node=node1)}

        with enter_phase("agent_session", registry=self.registry) as scope:
            fail_tool = scope.get_singleton(FailToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # Fail node1: blocks node2, node3 remains open -> non-terminating
            b_fail = ActualParameterBindings(
                bindings={
                    (fail_tool.target, TargetFileObj("f_unit1.py")),
                    (fail_tool.explanation, "Broken base"),
                }
            )
            # Requirement: Executing the fail tool marks the target as failed and in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp1 = fail_tool.execute_tool(b_fail)
            self.assertFalse(resp1.is_failed)
            self.assertFalse(resp1.is_terminated)
            self.assertEqual(rc.get_node_state(node1), "FAILED")
            self.assertEqual(rc.get_node_state(node2), "BLOCKED")
            self.assertIn("Remaining open files:\n- `f_unit3.py`", resp1.content)

            # Fail node3: no open nodes remain -> terminates with failure
            b_fail3 = ActualParameterBindings(
                bindings={
                    (fail_tool.target, "f_unit3.py"),
                    (fail_tool.explanation, "Failed unit 3"),
                }
            )
            # Requirement: Executing the fail tool marks the target as failed and in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp2 = fail_tool.execute_tool(b_fail3)
            self.assertTrue(resp2.is_failed)
            self.assertTrue(resp2.is_terminated)
            self.assertIn("Failed: Failed unit 3", resp2.content)

    def test_multi_node_blame_blocks_dependents_and_terminates(self) -> None:
        """CUJ: Multi-node blame marks target BLAME, dependents BLOCKED, and terminates when no open nodes remain."""
        node1 = Node(unit_address="//pkg:b_unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:b_unit2", role_address="lib")
        node3 = Node(unit_address="//pkg:b_unit3", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "b_unit1.py",
            node2: "b_unit2.py",
            node3: "b_unit3.py",
        }
        self.storage.dependencies[node2] = {Dependency(node=node1)}
        b_rw1 = ReadWriteFile(
            short_name="b_unit1.py",
            workspace_path=_make_workspace_path("pkg/b_unit1.py"),
            owning_node=node1,
        )
        b_rw3 = ReadWriteFile(
            short_name="b_unit3.py",
            workspace_path=_make_workspace_path("pkg/b_unit3.py"),
            owning_node=node3,
        )
        self.node_cfg._read_write_files = {b_rw1, b_rw3}
        bt = ReadOnlyFile(
            short_name="upstream_spec.md",
            workspace_path=_make_workspace_path("pkg/upstream_spec.md"),
            owning_node=Node(unit_address="//pkg:upstream_unit", role_address="spec"),
        )
        self.node_cfg.blame_targets_by_node = {node1: {bt}, node3: {bt}}

        with enter_phase("agent_session", registry=self.registry) as scope:
            blame_tool = scope.get_singleton(BlameToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # Blame node1 with invalid target fails
            b_bad = ActualParameterBindings(
                bindings={
                    (blame_tool.target, "b_unit1.py"),
                    (blame_tool.blame_target, "wrong.py"),
                    (blame_tool.explanation, "Bad"),
                }
            )
            # Requirement: Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
            resp_bad = blame_tool.execute_tool(b_bad)
            self.assertTrue(resp_bad.is_failed)

            # Blame node1 with valid target: marks node1 BLAME, blocks node2. node3 remains open -> non-terminating!
            b_ok = ActualParameterBindings(
                bindings={
                    (blame_tool.target, TargetFileObj("b_unit1.py")),
                    (blame_tool.blame_target, "upstream_spec.md"),
                    (blame_tool.explanation, "Spec defect"),
                }
            )
            # Requirement: On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp_ok = blame_tool.execute_tool(b_ok)
            self.assertFalse(resp_ok.is_failed)
            self.assertFalse(resp_ok.is_terminated)
            self.assertEqual(rc.get_node_state(node1), "BLAME")
            self.assertEqual(rc.get_node_state(node2), "BLOCKED")
            self.assertEqual(rc.get_node_state(node3), "OPEN")
            self.assertIn(b_rw1, self.edit_mgr.locked_files)
            self.assertNotIn(b_rw3, self.edit_mgr.locked_files)
            self.assertNotIn(bt, self.edit_mgr.locked_files)
            self.assertIn(
                "Target `b_unit1.py` blamed `upstream_spec.md`: Spec defect",
                resp_ok.content,
            )
            self.assertIn("- `b_unit3.py`", resp_ok.content)

            # Blame node3: no open nodes remain -> terminates!
            b_ok3 = ActualParameterBindings(
                bindings={
                    (blame_tool.target, "b_unit3.py"),
                    (blame_tool.blame_target, "upstream_spec.md"),
                    (blame_tool.explanation, "Spec defect 3"),
                }
            )
            # Requirement: On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
            resp_ok3 = blame_tool.execute_tool(b_ok3)
            self.assertFalse(resp_ok3.is_failed)
            self.assertTrue(resp_ok3.is_terminated)
            self.assertEqual(rc.get_node_state(node3), "BLAME")
            self.assertIn(b_rw3, self.edit_mgr.locked_files)
            self.assertNotIn(bt, self.edit_mgr.locked_files)
            self.assertIn("Blamed upstream_spec.md: Spec defect 3", resp_ok3.content)

    def test_run_tests_with_target_parameter(self) -> None:
        """CUJ: RunTestsTool evaluates specific verification checks when target is specified."""
        node1 = Node(unit_address="//pkg:rt_unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:rt_unit2", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "rt_unit1.py",
            node2: "rt_unit2.py",
        }
        vcheck1 = MockVerificationCheck(passes=True, diagnostic="Check 1 passed")
        vcheck2 = MockVerificationCheck(passes=False, diagnostic="Check 2 failed")
        self.node_cfg.verification_checks_by_node = {
            node1: [vcheck1],
            node2: [vcheck2],
        }

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)

            # Test target rt_unit1.py passes
            # Requirement: When a target is specified, executing the run tests tool evaluates verification checks for that target.
            b1 = ActualParameterBindings(
                bindings={(run_tests.target, TargetFileObj("rt_unit1.py"))}
            )
            resp1 = run_tests.execute_tool(b1)
            self.assertFalse(resp1.is_failed)
            self.assertEqual(vcheck1.call_count, 1)
            self.assertEqual(vcheck2.call_count, 0)

            # Cached verification check evaluation for node without file revision updates
            resp1_cached = run_tests.execute_tool(b1)
            self.assertFalse(resp1_cached.is_failed)
            self.assertEqual(vcheck1.call_count, 1)

            # Test target rt_unit2.py fails
            b2 = ActualParameterBindings(bindings={(run_tests.target, "rt_unit2.py")})
            resp2 = run_tests.execute_tool(b2)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(vcheck2.call_count, 1)

    def test_run_tests_tool_failing_verification_presents_diagnostics_and_instructions(
        self,
    ) -> None:
        """CUJ: RunTestsTool fails when verification fails, presenting sanitized diagnostics and failure instructions."""
        self.guide_del._guide = Guide(
            summary="Summary",
            sections=[],
            verification_failure="Inspect diagnostics and fix workspace files.",
        )
        vcheck = MockVerificationCheck(
            passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:12"
        )
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            # Requirement: The run tests tool is named `run_tests`, accepting an optional target parameter, and shares a constant suppression key `run_tests`.
            self.assertEqual(run_tests.name, "run_tests")
            self.assertEqual(run_tests.parameters, {run_tests.target})
            self.assertIsInstance(run_tests.description, str)

            b = ActualParameterBindings(bindings=set())
            # Requirement: [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
            resp = run_tests.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("dep.py:12", resp.content)
            self.assertNotIn("/workspace/pkg/", resp.content)
            self.assertIn(
                "## Verification failure\nInspect diagnostics and fix workspace files.",
                resp.content,
            )
            # Requirement: The run tests tool is named `run_tests`, accepting an optional target parameter, and shares a constant suppression key `run_tests`.
            self.assertEqual(resp.suppression_key, "run_tests")

    def test_run_tests_tool_passing_verification_presents_results(self) -> None:
        """CUJ: RunTestsTool produces a passing response when verification passes."""
        vcheck = MockVerificationCheck(
            passes=True, diagnostic="All tests pass in /workspace/pkg/test.py"
        )
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            b = ActualParameterBindings(bindings=set())
            # Requirement: [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
            resp = run_tests.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Verification passed", resp.content)
            self.assertIn("All tests pass in test.py", resp.content)
            # Requirement: The run tests tool is named `run_tests`, accepting an optional target parameter, and shares a constant suppression key `run_tests`.
            self.assertEqual(resp.suppression_key, "run_tests")

            # Custom verification_success_message
            # Requirement: Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
            self.node_cfg._verification_success_message = "Test test.py passed."
            self.edit_mgr.file_update_revision = 99
            resp2 = run_tests.execute_tool(b)
            self.assertIn("Test test.py passed.", resp2.content)

    def test_run_tests_tool_updates_verification_results_if_outdated(self) -> None:
        """CUJ: RunTestsTool caches verification results and re-evaluates when workspace files updated."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Error 1")
        self.node_cfg._verification_checks = [vcheck]
        self.edit_mgr.file_update_revision = 1

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            b = ActualParameterBindings(bindings=set())

            # First execution runs checks
            # Requirement: [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            resp1 = run_tests.execute_tool(b)
            self.assertTrue(resp1.is_failed)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNone(resp1.reminder)
            self.assertIsNone(resp1.follow_up_tool_call)

            # Second execution without file updates reuses cache
            # Requirement: Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous run tests tool execution.
            resp2 = run_tests.execute_tool(b)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNotNone(resp2.reminder)
            assert resp2.reminder is not None
            self.assertIn(
                "Verification failed, no new information will be revealed",
                resp2.reminder,
            )

            # Third execution after file update re-evaluates
            self.edit_mgr.file_update_revision = 2
            vcheck.passes = True
            resp3 = run_tests.execute_tool(b)
            self.assertFalse(resp3.is_failed)
            self.assertEqual(vcheck.call_count, 2)
            self.assertIsNone(resp3.reminder)
            self.assertIsNone(resp3.follow_up_tool_call)

    def test_run_tests_tool_repeated_with_read_write_file_specifies_view_file_followup(
        self,
    ) -> None:
        """CUJ: Repeated run_tests execution specifies follow-up read of the source file with view_file and reasoning."""
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]
        rw_file = ReadWriteFile(
            short_name="src.py",
            workspace_path=_make_workspace_path("/workspace/src.py"),
            owning_node=Node(unit_address="//pkg:target", role_address="lib"),
        )
        self.node_cfg._read_write_files = {rw_file}
        self.edit_mgr.file_update_revision = 1

        with enter_phase("agent_session", registry=self.registry) as scope:
            run_tests = scope.get_singleton(RunTestsTool)
            b = ActualParameterBindings(bindings=set())

            resp1 = run_tests.execute_tool(b)
            self.assertFalse(resp1.is_failed)
            self.assertIsNone(resp1.reminder)
            self.assertIsNone(resp1.follow_up_tool_call)

            # Requirement: Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous run tests tool execution.
            # Requirement: Specifies a follow-up execution of the view file tool on the session source file and reasoning text noting that verification passed without permission to run more tests and to advance or submit the session if correct, or noting that verification failed without permission to run more tests until files are updated, when workspace files have not been updated since the previous run tests tool execution.
            # When is_step_mode is False (default for coverage / non-step nodes), reasoning directs to submit
            self.node_cfg.is_step_mode = False
            resp2 = run_tests.execute_tool(b)
            self.assertFalse(resp2.is_failed)
            self.assertIsNotNone(resp2.reminder)
            assert resp2.reminder is not None
            self.assertIn(
                "Verification passes, no new information will be revealed by this tool call until src.py is updated.",
                resp2.reminder,
            )
            self.assertIsNotNone(resp2.follow_up_tool_call)
            assert resp2.follow_up_tool_call is not None
            self.assertEqual(resp2.follow_up_tool_call.tool_name, "view_file")
            self.assertEqual(
                resp2.follow_up_tool_call.wire_parameter_bindings.bindings,
                {("path", "src.py")},
            )
            self.assertEqual(
                resp2.follow_up_tool_call.reasoning_text,
                "Oh, verification passes and I'm not allowed to run anymore tests. Let me read src.py again and see if I can figure out a different course of action. If it is already correct, I need to submit the agent session rather than run more tests.",
            )

            # In step mode, reasoning directs the agent to advance rather than submit
            self.node_cfg.is_step_mode = True
            resp_step = run_tests.execute_tool(b)
            assert resp_step.follow_up_tool_call is not None
            self.assertEqual(
                resp_step.follow_up_tool_call.reasoning_text,
                "Oh, verification passes and I'm not allowed to run anymore tests. Let me read src.py again and see if I can figure out a different course of action. If it is already correct, I need to advance the agent session rather than run more tests.",
            )

            # When verification fails, reasoning indicates no more tests until files are updated
            vcheck.passes = False
            self.edit_mgr.file_update_revision = 2
            _ = run_tests.execute_tool(b)
            resp_fail = run_tests.execute_tool(b)
            assert resp_fail.follow_up_tool_call is not None
            self.assertEqual(
                resp_fail.follow_up_tool_call.reasoning_text,
                "Oh, verification failed and I'm not allowed to run anymore tests until I update the files. Let me read src.py again and see if I can figure out a different course of action.",
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
