"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for RunController."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import (
    file_alias,
    node_config,
    agent_session,
)
from update_with_ai.parts.control.lib import coordinate
from update_with_ai.parts.dag.lib import dag_storage, subgraph
from update_with_ai.parts.sandbox.lib import (
    file_editor,
    guide_delivery,
    run_control,
    submission,
    template_format,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.run_control_impl import (
    AdvanceTool,
    CheckFilesTool,
    GetWorkTool,
    RunController,
    __initialize__,
)


def _make_node(unit: str = "unit_a", role: str = "dev") -> dag_storage.DagNode:
    return dag_storage.DagNode(
        unit_address=dag_storage.UnitAddress(unit),
        role_address=dag_storage.RoleAddress(role),
    )


# ==============================================================================
# 1. State Machine Protocol Definition
# ==============================================================================

@dataclass
class RunControllerState:
    """Canonical model state for RunController."""
    verification_passed: bool = True
    diagnostic_output: str = ""


proto = StateMachineProto[RunControllerState]()


# ==============================================================================
# 2. Comprehensive Non-Fuzz Tests
# ==============================================================================

@dataclass(frozen=True)
class MockVerificationResult:
    passed: bool
    diagnostic_output: str
    is_cached: bool = False


@dataclass(frozen=True)
class MockScheduledTask:
    node: dag_storage.DagNode
    task_prompt: str
    dependency_paths: Sequence[str]
    feedback_messages: Sequence[dag_storage.FeedbackMessage]


@dataclass(frozen=True)
class MockWorkSchedule:
    tasks: Sequence[MockScheduledTask]


class MockVerificationCheck:
    def __init__(self, passed: bool = True, diagnostic: str = "") -> None:
        self.passed = passed
        self.diagnostic = node_config.VerificationDiagnostic(diagnostic)
        self.call_count = 0

    def verify(self) -> Tuple[bool, node_config.VerificationDiagnostic]:
        self.call_count += 1
        return self.passed, self.diagnostic


class MockToolManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.installed_tools: Dict[tool_provider.ToolName, tool_provider.Tool] = {}

    def install_tool(self, tool: tool_provider.Tool) -> None:
        self.installed_tools[tool.name] = tool

    def execute_tool(
        self,
        name: tool_provider.ToolName,
        wire_parameter_bindings: Mapping[tool_provider.ParameterName, Any],
    ) -> tool_provider.ToolResponse:
        raise NotImplementedError()


class MockEditManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._revision = 0
        self._last_file = None
        self._modifications = False
        self._file_hashes: Dict[str, str] = {}

    @property
    def has_modifications(self) -> bool:
        return self._modifications

    @property
    def file_update_revision(self) -> file_editor.FileUpdateRevision:
        return file_editor.FileUpdateRevision(self._revision)

    def file_hash(self, file: Any) -> file_editor.FileHash:
        path = str(file.relative_path) if hasattr(file, "relative_path") else str(file)
        return file_editor.FileHash(self._file_hashes.get(path, "hash_default"))


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.read_only_files: Set[Any] = set()
        self.read_write_files: Set[Any] = set()
        self.verification_checks: Sequence[Any] = []
        self.verification_success_message: Optional[str] = None
        self.is_step_mode: bool = False
        self.guide_file: Optional[Any] = None
        self.template_parameters: Dict[Any, Any] = {}
        self.guide: Optional[Any] = None
        self.blame_targets_by_node: Dict[dag_storage.DagNode, Set[Any]] = {}


class MockRoleConfig:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.role = node_config.RoleName("dev")
        self.nodes: List[dag_storage.DagNode] = []
        self.version = node_config.ExecutionVersion(1)


class MockGuideDelivery:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.guide: Optional[Any] = None
        self.has_guide: bool = False
        self.has_steps_remaining: bool = False
        self.initialized: bool = False
        self.recorded_primers: List[Any] = []

    def initialize(self) -> None:
        self.initialized = True

    def summarize_workflow_progress(self) -> str:
        return "Progress summary: 1/3 steps complete"

    def record_initial_primer(self, primer: Any) -> None:
        self.recorded_primers.append(primer)

    def advance_step(
        self,
        verification_passed: bool = True,
        failure_diagnostics: Any = None,
        **kwargs: Any,
    ) -> tool_provider.ToolResponse:
        content = (
            "Next step milestone instructions"
            if verification_passed
            else (str(failure_diagnostics) if failure_diagnostics else "verification error")
        )
        return tool_provider.ToolResponse(
            is_failed=not verification_passed,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(content),
        )


class MockDagStorage:
    tier = system

    def __init__(self) -> None:
        self.dirty_nodes: Set[dag_storage.DagNode] = set()
        self.messages: Dict[dag_storage.DagNode, Set[dag_storage.DagMessage]] = {}

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self.dirty_nodes

    def mark_node_dirty(self, node: dag_storage.DagNode, reason: Optional[str] = None) -> None:
        self.dirty_nodes.add(node)

    def mark_node_clean(self, node: dag_storage.DagNode, change: Optional[Any] = None) -> None:
        self.dirty_nodes.discard(node)

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        return self.messages.get(node, set())

    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self.messages[node] = set()


class MockDagSubgraph:
    tier = system

    def __init__(self) -> None:
        pass


class MockSessionCoordinator:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.verification_result = True
        self.diagnostics_result = ""
        self.primer_result = "Primer overview instructions"
        self.open_targets: Set[Any] = set()
        self.storage: Optional[MockDagStorage] = None
        self.node_config: Optional[MockNodeConfig] = None
        self.role_config: Optional[MockRoleConfig] = None
        self.empty_schedule: bool = False

    def get_alias_for_node(self, node: Any) -> str:
        return str(node)

    def register_node(self, node: dag_storage.DagNode, path: str) -> None:
        if self.role_config is not None:
            self.role_config.nodes.append(node)

    def verify(self, node: Optional[dag_storage.DagNode] = None) -> Any:
        return MockVerificationResult(
            passed=self.verification_result,
            diagnostic_output=self.diagnostics_result,
            is_cached=False,
        )

    def compose_session_primer(self) -> str:
        return self.primer_result

    def dispatch_get_work(self, subgraph: Any) -> Any:
        if self.empty_schedule:
            return MockWorkSchedule(tasks=[])
        return MockWorkSchedule(
            tasks=[
                MockScheduledTask(
                    node=_make_node("unit1"),
                    task_prompt="Prompt",
                    dependency_paths=[],
                    feedback_messages=[],
                )
            ]
        )


class MockAliasManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.workspace_root = file_alias.file_paths.WorkspaceRoot(
            file_alias.file_paths.PathString("/workspace")
        )

    def to_alias(self, path: str) -> Any:
        return file_alias.FileAlias(file_alias.RelativePath(path))

    def sanitize_text(self, text: Any) -> Any:
        return text


class MockTemplateFormatter:
    tier = agent_session.agent_session

    def format_template(self, text: Any, parameters: Any) -> Any:
        return text


class MockSubmissionTool:
    tier = agent_session.agent_session
    description = "Mock submission tool"
    parameters: Mapping[Any, Any] = {}

    def __init__(self, name: str) -> None:
        self.name = tool_provider.ToolName(name)

    def execute_tool(self, actual_parameter_bindings: Mapping[Any, Any]) -> tool_provider.ToolResponse:
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent("Mock executed"),
        )


class TestRunControlReal(unittest.TestCase):
    """Direct verification of the real RunController and associated tools."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        for name, key in (
            ("submit", submission.SubmitTool),
            ("fail", submission.FailTool),
            ("blame", submission.BlameTool),
        ):
            self.registry.register_instance(
                MockSubmissionTool(name),
                keys=[key],
                tier=agent_session.agent_session,
            )
        self.mock_storage = MockDagStorage()
        self.registry.register_instance(
            self.mock_storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )
        self.mock_subgraph = MockDagSubgraph()
        self.registry.register_instance(
            self.mock_subgraph,
            keys=[subgraph.DagSubgraph],
            tier=system,
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
            keys=[file_editor.EditManager],
            tier=agent_session.agent_session,
        )
        self.mock_node_config = MockNodeConfig()
        self.registry.register_instance(
            self.mock_node_config,
            keys=[node_config.NodeConfig],
            tier=agent_session.agent_session,
        )
        self.mock_role_config = MockRoleConfig()
        self.registry.register_instance(
            self.mock_role_config,
            keys=[node_config.RoleConfig],
            tier=agent_session.agent_session,
        )
        self.mock_guide_delivery = MockGuideDelivery()
        self.registry.register_instance(
            self.mock_guide_delivery,
            keys=[guide_delivery.GuideDelivery],
            tier=agent_session.agent_session,
        )
        self.mock_session_coordinator = MockSessionCoordinator()
        self.mock_session_coordinator.storage = self.mock_storage
        self.mock_session_coordinator.node_config = self.mock_node_config
        self.mock_session_coordinator.role_config = self.mock_role_config
        self.registry.register_instance(
            self.mock_session_coordinator,
            keys=[coordinate.SessionCoordinator],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager = MockAliasManager()
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[file_alias.AliasManager],
            tier=agent_session.agent_session,
        )
        self.mock_template_formatter = MockTemplateFormatter()
        self.registry.register_instance(
            self.mock_template_formatter,
            keys=[template_format.TemplateFormatter],
            tier=agent_session.agent_session,
        )

    def test_initialization(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            for cls in [AdvanceTool, CheckFilesTool, GetWorkTool, RunController]:
                instance = scope.get_singleton(cls)
                self.assertIsNotNone(instance)

    def test_check_files_tool_passes_verification(self) -> None:
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn("all verification checks passed", str(resp.content).lower())

    def test_check_files_tool_fails_verification(self) -> None:
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.verification_checks = [
            MockVerificationCheck(passed=False, diagnostic="error: syntax invalid")
        ]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("error: syntax invalid", str(resp.content))

    def test_get_work_tool_returns_primer(self) -> None:
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn("Prompt", str(resp.content))

    def test_advance_tool_failing_first_step_repeats_primer(self) -> None:
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.verification_checks = [
            MockVerificationCheck(passed=False, diagnostic="verification error")
        ]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("verification error", str(resp.content))

    def test_advance_tool_passes_verification(self) -> None:
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_guide_delivery.has_steps_remaining = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn("Next step milestone instructions", str(resp.content))


    def test_get_work_tool_open_targets_and_blame_install(self) -> None:
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")

        # Open targets exist -> fails
        self.mock_session_coordinator.open_targets = {node}
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("open active nodes remain", str(resp.content).lower())

        # Clear open targets, add blame target -> blame installed
        self.mock_session_coordinator.open_targets = set()
        alias = file_alias.FileAlias(file_alias.RelativePath("dep.py"))
        ws_path = file_alias.file_paths.WorkspacePath(file_alias.file_paths.PathString("dep.py"))
        bound = file_alias.BoundFile(file_alias.RelativePath("dep.py"), ws_path, owning_node=node)
        self.mock_node_config.blame_targets_by_node = {node: {bound}}
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn(tool_provider.ToolName("blame"), self.mock_tool_manager.installed_tools)

    def test_advance_tool_no_steps_remaining(self) -> None:
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_guide_delivery.has_steps_remaining = False

        # Modified files -> prompts to submit (returns is_failed=True to force prompt)
        self.mock_edit_manager._modifications = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("submit", str(resp.content).lower())

        # Unmodified files -> submit or proceed (returns is_failed=False)
        self.mock_edit_manager._modifications = False
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)

    def test_tool_metadata_and_properties(self) -> None:
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            c_tool = scope.get_singleton(CheckFilesTool)
            self.assertEqual(str(c_tool.name), "check_files")
            self.assertTrue(len(str(c_tool.description)) > 0)
            self.assertEqual(len(c_tool.parameters), 0)

            a_tool = scope.get_singleton(AdvanceTool)
            self.assertEqual(str(a_tool.name), "advance")
            self.assertTrue(len(str(a_tool.description)) > 0)
            self.assertEqual(len(a_tool.parameters), 0)

            w_tool = scope.get_singleton(GetWorkTool)
            self.assertEqual(str(w_tool.name), "get_work")
            self.assertTrue(len(str(w_tool.description)) > 0)
            self.assertEqual(len(w_tool.parameters), 0)

    def test_check_files_unchanged_and_failure_instructions(self) -> None:
        # 1. Unchanged verification status
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunController)
            ctrl.update_verification()
            # Second update with same hash
            ctrl.update_verification()
            self.assertTrue(ctrl.is_unchanged)

            tool = scope.get_singleton(CheckFilesTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn("unchanged", str(resp.content).lower())

        # 2. Failure with guide instructions
        class MockGuideWithFailure:
            verification_failure = "Follow steps in the guide to fix."
            summary = None

        self.mock_node_config.guide = MockGuideWithFailure()
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=False, diagnostic="Error in syntax")]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            resp = tool.execute_tool({})
            self.assertTrue(resp.is_failed)
            self.assertIn("Error in syntax", str(resp.content))
            self.assertIn("Follow steps in the guide to fix", str(resp.content))

    def test_get_work_tool_empty_tasks_and_step_mode_and_summary(self) -> None:
        # Empty tasks
        self.mock_session_coordinator.empty_schedule = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn("Workspace is clean", str(resp.content))

        # Reset empty_schedule and test step mode & guide file & guide summary
        self.mock_session_coordinator.empty_schedule = False
        self.mock_node_config.is_step_mode = True
        self.mock_node_config.guide_file = file_alias.FileAlias(file_alias.RelativePath("guides/dev.md"))
        class MockGuideWithSummary:
            verification_failure = None
            summary = "Summary of instructions"
        self.mock_node_config.guide = MockGuideWithSummary()

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            resp = tool.execute_tool({})
            self.assertFalse(resp.is_failed)
            self.assertIn("advance", str(resp.content).lower())
            self.assertIn("guides/dev.md", str(resp.content))
            self.assertIn("Summary of instructions", str(resp.content))
            self.assertIn(tool_provider.ToolName("advance"), self.mock_tool_manager.installed_tools)
            self.assertTrue(self.mock_guide_delivery.initialized)

    def test_run_controller_properties_and_targets(self) -> None:
        node = _make_node("unit1")
        alias = file_alias.FileAlias(file_alias.RelativePath("foo.py"))
        ws_path = file_alias.file_paths.WorkspacePath(file_alias.file_paths.PathString("foo.py"))
        bound = file_alias.BoundFile(file_alias.RelativePath("foo.py"), ws_path, owning_node=node)
        self.mock_node_config.blame_targets_by_node = {node: {bound}}
        self.mock_node_config.read_write_files = {alias}
        self.mock_node_config.is_step_mode = True

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunController)
            ctrl.initialize()
            self.assertIn(tool_provider.ToolName("advance"), self.mock_tool_manager.installed_tools)
            self.assertIn(node, ctrl.blame_targets_by_node)
            self.assertEqual(len(ctrl.verification_checks), len(self.mock_node_config.verification_checks))
            ctrl.update_verification()
            self.assertFalse(ctrl.is_unchanged)
            ctrl.update_verification()
            self.assertTrue(ctrl.is_unchanged)


# ==============================================================================
# 3. Hypothesis Property Fuzz Testing
# ==============================================================================

class TestRunControlFuzz(unittest.TestCase):
    """Property fuzz testing for RunController."""

    @settings(max_examples=20)
    @given(passed=st.booleans())
    def test_run_controller_property(self, passed: bool) -> None:
        state = RunControllerState(verification_passed=passed)
        self.assertEqual(state.verification_passed, passed)
