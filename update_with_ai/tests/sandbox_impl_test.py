"""Unit tests for sandbox_impl aligned with grounding specifications."""

import unittest
from typing import Any, List, Optional, Set, Tuple

from lib.dag_storage import Node
from lib.file_alias import BoundFile, FileContent, ReadOnlyFile, UnboundFile, WorkspacePath
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from lib.model_config import ModelConfig
from lib.node_config import NodeConfig
from lib.sandbox import Sandbox, StartupToolExecution
from lib.sandbox_file_editor import EditManager
from lib.sandbox_file_reader import ReadManager, ReadTool
from lib.sandbox_guide_delivery import Guide
from lib.sandbox_impl import Sandbox as SandboxImpl, __initialize__
from lib.sandbox_run_control import AdvanceTool
from lib.tool_provider import (
    ActualParameterBindings,
    Parameter,
    ParameterConverter,
    Response,
    String,
    Tool,
    WireParameterBindings,
    WireType,
)


class MockModelConfig:
    tier = "system"

    def __init__(self, is_step_mode: bool = False, is_startup_reads: bool = False) -> None:
        self.is_step_mode = is_step_mode
        self.is_startup_reads = is_startup_reads
        self.model_name = "test-model"
        self.base_url = None
        self.api_key = None
        self.timeout = 30
        self.conversation_limit = 10
        self.temperature = 0.0
        self.max_tokens = None


class MockNodeConfig:
    tier = "agent_session"

    def __init__(
        self,
        read_only_files: Set[BoundFile],
        is_step_mode: Optional[bool] = None,
        allows_step_mode: bool = True,
    ) -> None:
        self.read_only_files = read_only_files
        self._is_step_mode = is_step_mode
        self.allows_step_mode = allows_step_mode

    @property
    def is_step_mode(self) -> bool:
        if self._is_step_mode is not None:
            return self._is_step_mode
        try:
            m_cfg = get_singleton(ModelConfig)
            return m_cfg.is_step_mode and self.allows_step_mode
        except Exception:
            return False

    @is_step_mode.setter
    def is_step_mode(self, val: bool) -> None:
        self._is_step_mode = val

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
        return set()


class MockEditManager:
    tier = "agent_session"

    def __init__(self) -> None:
        self.has_modifications = False
        self.templates_materialized = False

    def materialize_templates(self) -> None:
        self.templates_materialized = True


class MockAdvanceTool:
    tier = "agent_session"

    def __init__(self) -> None:
        self.executed = False

    @property
    def name(self) -> str:
        return "advance"

    @property
    def description(self) -> str:
        return "Advance tool"

    @property
    def parameters(self) -> Set[Parameter]:
        return set()

    def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
        self.executed = True
        return Response(is_failed=False, is_terminated=False, content="Guide step 1")


class DummyConverter:
    @property
    def actual_type(self) -> type:
        return object

    @property
    def wire_type(self) -> WireType:
        return String()

    def convert(self, wire_value: Any) -> Any:
        return wire_value


class MockReadTool:
    tier = "agent_session"

    def __init__(self) -> None:
        self.executed_files: List[BoundFile] = []
        self.file_alias_parameter = Parameter(
            name="file",
            description="file",
            parameter_converter=DummyConverter(),
            is_required=True,
        )
        self.line_numbers_parameter = Parameter(
            name="line_numbers",
            description="line numbers",
            parameter_converter=DummyConverter(),
            is_required=False,
        )

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read tool"

    @property
    def parameters(self) -> Set[Parameter]:
        return {self.file_alias_parameter, self.line_numbers_parameter}

    def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target = bindings_map.get("file")
        if isinstance(target, BoundFile):
            self.executed_files.append(target)
        return Response(is_failed=False, is_terminated=False, content=f"Content of {target}")


class MockReadManager:
    tier = "agent_session"

    def requires_line_numbers(self, file: BoundFile) -> bool:
        return file.short_name.endswith(".py")


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        node = Node(address="//pkg:target")
        self.ro_file = ReadOnlyFile(
            short_name="spec.md",
            workspace_path=_make_workspace_path("pkg/spec.md"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.model_cfg = MockModelConfig(is_step_mode=True, is_startup_reads=True)
        self.node_cfg = MockNodeConfig(read_only_files={self.ro_file})
        self.edit_mgr = MockEditManager()
        self.adv_tool = MockAdvanceTool()
        self.read_tool = MockReadTool()
        self.read_mgr = MockReadManager()

        self.registry.register_instance(self.model_cfg, keys=[ModelConfig], tier="system")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")
        self.registry.register_instance(self.edit_mgr, keys=[EditManager], tier="agent_session")
        self.registry.register_instance(self.adv_tool, keys=[AdvanceTool], tier="agent_session")
        self.registry.register_instance(self.read_tool, keys=[ReadTool], tier="agent_session")
        self.registry.register_instance(self.read_mgr, keys=[ReadManager], tier="agent_session")

    def test_has_modifications_and_template_materialization_delegation(self) -> None:
        """CUJ: Sandbox delegates modification checking and template materialization to EditManager."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)

            # Requirement: Querying file modifications delegates to the edit manager.
            # Requirement: [Sandbox] The sandbox exposes whether workspace file modifications occurred during the session.
            self.assertFalse(sb.has_modifications)
            self.edit_mgr.has_modifications = True
            self.assertTrue(sb.has_modifications)

            # Requirement: Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.
            # Requirement: [Sandbox] Materializing startup templates populates missing read-write files without overwriting existing files.
            self.assertFalse(self.edit_mgr.templates_materialized)
            sb.materialize_startup_templates()
            self.assertTrue(self.edit_mgr.templates_materialized)

    def test_get_startup_tool_executions_step_mode_and_startup_reads(self) -> None:
        """CUJ: Assembling startup tool executions: advance first when in step mode, followed by read_file for read-only files."""
        node = Node(address="//pkg:target")
        ro_file_z = ReadOnlyFile(short_name="z_spec.md", workspace_path=_make_workspace_path("pkg/z_spec.md"), owning_node=node)
        ro_file_a = ReadOnlyFile(short_name="a_spec.md", workspace_path=_make_workspace_path("pkg/a_spec.md"), owning_node=node)
        ro_file_py = ReadOnlyFile(short_name="m_lib.py", workspace_path=_make_workspace_path("pkg/m_lib.py"), owning_node=node)
        ro_files: Set[BoundFile] = {ro_file_z, ro_file_a, ro_file_py}
        self.node_cfg.read_only_files = ro_files

        with enter_phase("agent_session", registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: [Sandbox] The sandbox exposes startup tool executions as an ordered sequence of initial tool executions based on active configuration, ordering startup reads deterministically by file alias short name.
            executions = sb.get_startup_tool_executions()

            self.assertEqual(len(executions), 4)
            # First is advance
            # Requirement: When using step mode to communicate a guide progressively, startup tool executions include an initial advance tool execution with the name of the advance tool, empty wire parameter bindings, and the response produced by executing the advance tool.
            self.assertEqual(executions[0].tool_name, "advance")
            self.assertEqual(executions[0].wire_parameter_bindings.bindings, set())
            self.assertEqual(executions[0].response.content, "Guide step 1")

            # Second is read_file for a_spec.md (ordered deterministically before m_lib.py and z_spec.md)
            # Requirement: When performing startup reads to inspect declared files at session start, startup tool executions include file read executions for all declared read-only files from node config ordered deterministically by file alias short name, positioned after any advance tool execution.
            # Requirement: Each file read execution uses the name of the read tool, specifies wire parameter bindings mapping the file alias parameter of the read tool to the read-only file alias short name while supplying line numbers as determined by the read manager for source code files, and captures the response produced by executing the read tool.
            self.assertEqual(executions[1].tool_name, "read_file")
            self.assertEqual(executions[1].wire_parameter_bindings.bindings, {("file", "a_spec.md")})
            self.assertIn("a_spec.md", executions[1].response.content)

            # Third is read_file for m_lib.py (supplies line_numbers=True for source code file)
            self.assertEqual(executions[2].tool_name, "read_file")
            self.assertEqual(executions[2].wire_parameter_bindings.bindings, {("file", "m_lib.py"), ("line_numbers", True)})
            self.assertIn("m_lib.py", executions[2].response.content)

            # Fourth is read_file for z_spec.md
            self.assertEqual(executions[3].tool_name, "read_file")
            self.assertEqual(executions[3].wire_parameter_bindings.bindings, {("file", "z_spec.md")})
            self.assertIn("z_spec.md", executions[3].response.content)

    def test_get_startup_tool_executions_disabled_modes(self) -> None:
        """CUJ: Omits advance when step mode is off, and omits reads when startup reads are off."""
        self.model_cfg.is_step_mode = False
        self.model_cfg.is_startup_reads = False

        with enter_phase("agent_session", registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: When step mode is not used, startup tool executions contain no advance tool execution.
            # Requirement: When startup reads are not performed, startup tool executions contain no file read executions.
            executions = sb.get_startup_tool_executions()
            self.assertEqual(len(executions), 0)

    def test_get_startup_tool_executions_node_disallows_step_mode(self) -> None:
        """CUJ: Omits advance when node disallows step mode even if model config enables it."""
        self.model_cfg.is_step_mode = True
        self.model_cfg.is_startup_reads = False
        self.node_cfg.allows_step_mode = False

        with enter_phase("agent_session", registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: When step mode is not used, startup tool executions contain no advance tool execution.
            executions = sb.get_startup_tool_executions()
            self.assertEqual(len(executions), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
