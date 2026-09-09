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
from lib.lifecycle import LifecycleRegistry, enter_phase
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


class MockAliasManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.workspace_root = DirectoryPath(path="/workspace")
        self.actual_type = FileAlias
        self.wire_type = String()

    def convert(self, wire_value: Any) -> Any:
        return wire_value

    def sanitize_text(self, text: str) -> str:
        return text


class MockNodeConfig:
    tier = "agent_session"

    def __init__(self, blame_targets: Optional[Set[BoundFile]] = None) -> None:
        self._blame_targets = blame_targets or set()

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
        return None

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return self._blame_targets


class MockGuideDelivery:
    tier = "agent_session"

    def __init__(self, has_steps: bool = False, next_step_content: Optional[str] = None) -> None:
        self.has_steps_remaining = has_steps
        self.next_step_content = next_step_content

    def advance_step(self, verification_passed: bool) -> Optional[Response]:
        if self.has_steps_remaining and self.next_step_content:
            return Response(is_failed=False, is_terminated=False, content=self.next_step_content)
        return None

    def parse_guide(self, content: FileContent) -> Guide:
        return Guide(summary="", sections=[])


class MockEditManager:
    tier = "agent_session"

    def __init__(self, has_modifications: bool = False) -> None:
        self.has_modifications = has_modifications

    def materialize_templates(self) -> None:
        pass


class MockVerificationCheck:
    def __init__(self, passes: bool = True, diagnostic: str = "") -> None:
        self.passes = passes
        self.diagnostic = diagnostic

    def verify(self) -> Tuple[bool, str]:
        return self.passes, self.diagnostic


class SandboxRunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        node = Node(address="//pkg:upstream")
        self.blame_target_file = ReadOnlyFile(
            short_name="dep.py",
            workspace_path=WorkspacePath(path="pkg/dep.py"),
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
            _ = scope.get_singleton(RunController)
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
            # Requirement: A call to the advance tool can be injected at agent session start when using step mode to deliver initial step content, executing without requiring a change summary.
            # Requirement: When progressive guide delivery is configured and steps remain in guide delivery, executing the advance tool advances the guide step and returns the next step content without terminating the run.
            resp = adv.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "Step 2 Instructions")

    def test_advance_tool_verification_check_failure(self) -> None:
        """CUJ: AdvanceTool evaluates verification checks and fails if any check fails."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            rc = scope.get_singleton(RunController)
            # Requirement: Installing a verification check appends it to the sequence of checks evaluated by the advance tool.
            # Requirement: [RunController] Installing a verification check adds it to the verification checks evaluated during session advancement.
            rc.install_verification_check(MockVerificationCheck(passes=False, diagnostic="Syntax Error"))

            adv = scope.get_singleton(AdvanceTool)
            b = ActualParameterBindings(bindings=set())
            # Requirement: When verification checks are installed, executing the advance tool evaluates each check in order and fails if any verification check does not pass.
            resp = adv.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)

    def test_advance_tool_modified_files_require_summary(self) -> None:
        """CUJ: AdvanceTool fails if workspace files modified and change summary is missing."""
        self.edit_mgr.has_modifications = True

        with enter_phase("agent_session", registry=self.registry) as scope:
            adv = scope.get_singleton(AdvanceToolImpl)

            # Missing change_summary -> fails
            b_missing = ActualParameterBindings(bindings=set())
            # Requirement: When no guide steps remain or guide delivery is not configured, executing the advance tool queries the edit manager and fails if workspace files were modified and the change summary is empty.
            resp_missing = adv.execute_tool(b_missing)
            self.assertTrue(resp_missing.is_failed)

            # Provided change_summary -> succeeds and terminates
            b_ok = ActualParameterBindings(bindings={(adv.change_summary, "Fixed issue")})
            # Requirement: On successful advance tool execution when no guide steps remain, the response indicates termination.
            resp_ok = adv.execute_tool(b_ok)
            self.assertFalse(resp_ok.is_failed)
            self.assertTrue(resp_ok.is_terminated)
            self.assertIn("Fixed issue", resp_ok.content)
            self.assertIsInstance(adv.description, str)
            self.assertGreater(len(adv.parameters), 0)

    def test_fail_tool(self) -> None:
        """CUJ: FailTool produces terminating failure response carrying explanation."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            fail_tool = scope.get_singleton(FailToolImpl)
            self.assertIsInstance(fail_tool.description, str)
            self.assertGreater(len(fail_tool.parameters), 0)
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

            # Invalid target fails
            unrecognized = ReadOnlyFile(
                short_name="unknown.py",
                workspace_path=WorkspacePath(path="unknown.py"),
                owning_node=Node(address="//pkg:unknown"),
            )
            b_invalid = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, unrecognized),
                    (blame_tool.explanation, "Broken"),
                }
            )
            resp_inv = blame_tool.execute_tool(b_invalid)
            self.assertTrue(resp_inv.is_failed)

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


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
# - Executing the blame tool fails if the target does not match any configured blame target, listing available blame targets.
# - When no workspace files were modified, no verification checks were installed, and no change summary was provided, executing the advance tool fails.
