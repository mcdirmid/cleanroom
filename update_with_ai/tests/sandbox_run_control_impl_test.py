"""Unit tests for sandbox_run_control_impl aligned with grounding specifications."""

import unittest
from typing import Any, Optional, Set, Tuple

from lib.dag_storage import Node
from lib.file_alias import (
    AliasManager,
    BoundFile,
    DirectoryPath,
    FileAlias,
    FileContent,
    ReadOnlyFile,
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
    RunController,
    VerificationCheck,
)
from lib.sandbox_run_control_impl import (
    AdvanceTool as AdvanceToolImpl,
    BlameTool as BlameToolImpl,
    FailTool as FailToolImpl,
    RunController as RunControllerImpl,
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
        verification_checks: Optional[list] = None,
    ) -> None:
        self._blame_targets = blame_targets or set()
        self._verification_checks = verification_checks or []
        self._guide: Optional[Guide] = None

    @property
    def read_only_files(self) -> Set[BoundFile]:
        return set()

    @property
    def read_write_files(self) -> Set[BoundFile]:
        return set()

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
    def verification_checks(self) -> list:
        return self._verification_checks


class MockGuideDelivery:
    tier = "agent_session"

    def __init__(self, has_steps: bool = False, next_step_content: Optional[str] = None) -> None:
        self.has_steps_remaining = has_steps
        self.next_step_content = next_step_content
        self.advance_step_called = False
        self.last_verification_passed: Optional[bool] = None
        self.last_failure_diagnostics: Optional[str] = None

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[Response]:
        self.advance_step_called = True
        self.last_verification_passed = verification_passed
        self.last_failure_diagnostics = failure_diagnostics
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


class MockVerificationCheck:
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
        self.node_cfg = MockNodeConfig(blame_targets={self.blame_target_file})
        self.guide_del = MockGuideDelivery()
        self.edit_mgr = MockEditManager()

        self.registry.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")
        self.registry.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")
        self.registry.register_instance(self.guide_del, keys=[GuideDelivery], tier="agent_session")
        self.registry.register_instance(self.edit_mgr, keys=[EditManager], tier="agent_session")

    def test_run_controller_initialization_with_blame(self) -> None:
        """CUJ: RunController installs advance, fail, and blame tools when blame targets exist."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: [RunController] The run controller exposes verification checks that validate session criteria during advancement.
            self.assertEqual(ctrl.verification_checks, [])
            # Requirement: The run controller installs the advance tool and fail tool unconditionally, and installs the blame tool only when blame targets are configured in the node config.
            # Requirement: [RunController] The run controller installs the advance tool and fail tool unconditionally, and installs the blame tool only when blame targets are configured.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The advance tool is named `advance`.
            self.assertIn("advance", tool_names)
            # Requirement: The fail tool is named `fail`.
            self.assertIn("fail", tool_names)
            # Requirement: The blame tool is named `blame`.
            self.assertIn("blame", tool_names)

    def test_advance_tool_guide_step_progression(self) -> None:
        """CUJ: AdvanceTool returns next guide step without terminating when guide steps remain."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 2 Instructions"

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())
            resp = adv.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "Step 2 Instructions")

    def test_advance_tool_guide_step_change_summary_rejected(self) -> None:
        """CUJ: AdvanceTool fails if change summary provided while guide steps remain."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 2 Instructions"

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings={(adv.change_summary, "Premature summary")})
            # Requirement: When guide step mode is on and steps remain in guide delivery, tool execution fails if a change summary is provided, and reminds the agent that a change summary can only be provided when completing the session after seeing all guide steps.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.reminder, "A change summary can only be provided when completing the session after seeing all guide steps.")
            self.assertFalse(self.guide_del.advance_step_called)

    def test_advance_tool_no_modifications_change_summary_rejected(self) -> None:
        """CUJ: AdvanceTool fails if change summary provided when no files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings={(adv.change_summary, "Unneeded summary")})
            # Requirement: When no file has changed, tool execution fails if a change summary is provided, and reminds the agent that a change summary can only be provided when workspace files were modified.
            # Requirement: Verification checks always execute as long as the change summary is set correctly.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.reminder, "A change summary can only be provided when workspace files were modified.")
            self.assertFalse(vcheck.called)

    def test_advance_tool_guide_step_verification_success(self) -> None:
        """CUJ: AdvanceTool executes verification checks and advances guide delivery when checks pass."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 2 Instructions"
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Verification checks execute as long as the change summary is set correctly, unless the previous advance call failed verification and no workspace files have been updated since.
            resp = adv.execute_tool(b)

            self.assertTrue(vcheck.called)
            self.assertTrue(self.guide_del.advance_step_called)
            self.assertIs(self.guide_del.last_verification_passed, True)
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.content, "Step 2 Instructions")

    def test_advance_tool_guide_step_verification_failure(self) -> None:
        """CUJ: AdvanceTool executes verification checks and delivers sanitized failure diagnostic to guide delivery when check fails."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 2 Instructions"
        vcheck = MockVerificationCheck(passes=False, diagnostic="Error in /workspace/pkg/dep.py:10")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Verification checks execute as long as the change summary is set correctly, unless the previous advance call failed verification and no workspace files have been updated since.
            # Requirement: When verification checks execute and any verification check fails, tool execution fails with diagnostic feedback sanitized through the alias manager, and the advance tool caches the failure output alongside the current file update revision from the edit manager.
            resp = adv.execute_tool(b)

            self.assertTrue(vcheck.called)
            self.assertTrue(self.guide_del.advance_step_called)
            self.assertIs(self.guide_del.last_verification_passed, False)
            self.assertEqual(self.guide_del.last_failure_diagnostics, "Error in dep.py:10")
            self.assertTrue(resp.is_failed)
            self.assertIn("Step failed with: Error in dep.py:10", resp.content)

    def test_advance_tool_no_modifications_without_summary_succeeds(self) -> None:
        """CUJ: AdvanceTool succeeds when no files modified and no summary provided."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())
            resp = adv.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)

    def test_advance_tool_verification_check_failure(self) -> None:
        """CUJ: AdvanceTool evaluates verification checks and fails if any check fails."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        self.node_cfg._verification_checks = [
            MockVerificationCheck(passes=False, diagnostic="Syntax Error in /workspace/pkg/dep.py:10")
        ]
        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings={(adv.change_summary, "Modified files")})
            # Requirement: Verification checks execute as long as the change summary is set correctly, unless the previous advance call failed verification and no workspace files have been updated since.
            # Requirement: When verification checks execute and any verification check fails, tool execution fails with diagnostic feedback sanitized through the alias manager, and the advance tool caches the failure output alongside the current file update revision from the edit manager.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Syntax Error in dep.py:10", resp.content)
            self.assertNotIn("/workspace/pkg/", resp.content)

    def test_advance_tool_repeated_verification_failure_cached_and_complains(self) -> None:
        """CUJ: AdvanceTool caches verification failure and complains on repeated calls without file updates."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        self.edit_mgr.file_update_revision = 1
        check = MockVerificationCheck(passes=False, diagnostic="Syntax Error in /workspace/pkg/dep.py:10")
        self.node_cfg._verification_checks = [check]
        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings={(adv.change_summary, "Modified files")})

            # First call executes verification and fails
            # Requirement: When verification checks execute and any verification check fails, tool execution fails with diagnostic feedback sanitized through the alias manager, and the advance tool caches the failure output alongside the current file update revision from the edit manager.
            resp1 = adv.execute_tool(b)
            self.assertTrue(resp1.is_failed)
            self.assertEqual(check.call_count, 1)
            self.assertIn("Syntax Error in dep.py:10", resp1.content)

            # Second call without file update -> does NOT re-run check (check.call_count remains 1)
            # Requirement: When the advance tool is called after a previous advance call that failed verification and no workspace files have been updated since that failure as indicated by the edit manager's file update revision, tool execution fails without re-executing verification checks, serving the cached output from the previous failed verification and reminding the agent that verification failed previously and workspace files must be updated before advancing again.
            resp2 = adv.execute_tool(b)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(check.call_count, 1)
            self.assertEqual(resp2.content, resp1.content)
            self.assertEqual(resp2.reminder, "Verification failed previously and workspace files must be updated before advancing again.")

            # Updating files increments file_update_revision
            self.edit_mgr.file_update_revision = 2
            # Re-running verification checks occurs on next call
            # Requirement: Verification checks execute as long as the change summary is set correctly, unless the previous advance call failed verification and no workspace files have been updated since.
            check.passes = True
            resp3 = adv.execute_tool(b)
            self.assertEqual(check.call_count, 2)
            self.assertFalse(resp3.is_failed)
            self.assertTrue(resp3.is_terminated)

    def test_advance_tool_modified_files_require_summary(self) -> None:
        """CUJ: AdvanceTool fails if workspace files modified and change summary is missing."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)

            # Missing change_summary -> fails
            b_missing = ActualParameterBindings(bindings=set())
            # Requirement: If workspace files were modified and either guide step mode is not on or no steps remain in guide delivery, tool execution fails if the change summary is not provided, and reminds the agent that a change summary must be provided when completing the session after modifying workspace files.
            resp_missing = adv.execute_tool(b_missing)
            self.assertTrue(resp_missing.is_failed)
            self.assertEqual(resp_missing.reminder, "A change summary must be provided when completing the session after modifying workspace files.")

            # Provided change_summary -> succeeds and terminates
            b_ok = ActualParameterBindings(bindings={(adv.change_summary, "Fixed issue")})
            resp_ok = adv.execute_tool(b_ok)
            self.assertFalse(resp_ok.is_failed)
            self.assertTrue(resp_ok.is_terminated)
            self.assertIn("Fixed issue", resp_ok.content)
            self.assertIsInstance(adv.description, str)
            self.assertGreater(len(adv.parameters), 0)
            # Requirement: The advance tool change summary parameter uses a string parameter converter to accept text.
            self.assertIs(adv.change_summary.parameter_converter, self.str_conv)

    def test_fail_tool(self) -> None:
        """CUJ: FailTool produces terminating failure response carrying explanation."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            fail_tool = scope.get_singleton(FailToolImpl)
            self.assertIsInstance(fail_tool.description, str)
            self.assertGreater(len(fail_tool.parameters), 0)
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
            self.assertEqual(resp_inv.reminder, "Only upstream files configured as blame targets can be blamed.")

            # Valid target terminates with Blamed attribution
            b_valid = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, self.blame_target_file),
                    (blame_tool.explanation, "Broken type signature"),
                }
            )
            # Requirement: On successful blame tool execution, the response indicates termination attributing feedback to the blame target owning node.
            resp_val = blame_tool.execute_tool(b_valid)
            self.assertFalse(resp_val.is_failed)
            self.assertTrue(resp_val.is_terminated)
            self.assertIn("Blamed dep.py: Broken type signature", resp_val.content)

    def test_advance_tool_guide_step_mode_failure_presents_guide_summary(self) -> None:
        """CUJ: AdvanceTool presents guide summary when execution fails in guide step mode."""
        self.node_cfg._guide = Guide(summary="# My Guide Summary", sections=[])
        self.guide_del.has_steps_remaining = True

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings={(adv.change_summary, "Premature summary")})
            # Requirement: When guide step mode is on, tool execution always presents the guide summary from node config whether execution fails or succeeds.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.content.startswith("# My Guide Summary\n\nError: change_summary is not allowed while guide steps remain."))

    def test_advance_tool_guide_step_mode_completion_presents_guide_summary(self) -> None:
        """CUJ: AdvanceTool presents guide summary upon session completion in guide step mode."""
        self.node_cfg._guide = Guide(summary="# My Guide Summary", sections=[])
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: When guide step mode is on, tool execution always presents the guide summary from node config whether execution fails or succeeds.
            resp = adv.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertTrue(resp.content.startswith("# My Guide Summary\n\nSession completed successfully"))

    def test_advance_tool_guide_step_mode_verification_failure_at_completion_presents_guide_summary(self) -> None:
        """CUJ: AdvanceTool presents guide summary when verification fails at completion in guide step mode."""
        self.node_cfg._guide = Guide(summary="# My Guide Summary", sections=[])
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        self.node_cfg._verification_checks = [
            MockVerificationCheck(passes=False, diagnostic="Syntax Error in dep.py:10")
        ]

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings={(adv.change_summary, "Modified files")})
            # Requirement: When guide step mode is on, tool execution always presents the guide summary from node config whether execution fails or succeeds.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.content.startswith("# My Guide Summary\n\nVerification failed: Syntax Error in dep.py:10"))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
# - [Tool] When a parameter is required, an argument must be supplied for tool execution.
# - A call to the advance tool can be injected when an agent session starts when using step mode to deliver initial step content, executing without requiring a change summary.
