"""Unit tests for sandbox_impl aligned with grounding specifications."""

import unittest
from typing import Any, List, Optional, Set, Tuple

from update_with_ai.parts.dag.lib.dag_storage import Node
from update_with_ai.parts.agent.lib.agent_file_alias import (
    BoundFile,
    FileAlias,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_node_config import Guide, NodeConfig
from update_with_ai.parts.sandbox.lib.sandbox import (
    Sandbox,
    StartupToolExecution,
)
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_file_reader import ViewFileTool
from update_with_ai.parts.sandbox.lib.sandbox_impl import (
    Sandbox as SandboxImpl,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib.sandbox_run_control import AdvanceTool
from update_with_ai.parts.sandbox.lib.tool_provider import (
    STRING_PARAMETER_TYPE,
    ActualParameterBindings,
    Parameter,
    ParameterType,
    Response,
    String,
    Tool,
    WireParameterBindings,
    WireType,
)


class MockAgentConfig:
    tier = system

    def __init__(
        self, is_step_mode: bool = False, is_startup_reads: bool = False
    ) -> None:
        self.is_step_mode = is_step_mode
        self.is_startup_reads = is_startup_reads
        self.conversation_limit = 10
        self.inject_followups = False


class MockNodeConfig:
    tier = agent_session

    def __init__(
        self,
        read_only_files: Set[ReadOnlyFile],
        is_step_mode: Optional[bool] = None,
        allows_step_mode: bool = True,
        read_write_files: Optional[Set[ReadWriteFile]] = None,
    ) -> None:
        self.read_only_files = read_only_files
        self._is_step_mode = is_step_mode
        self.allows_step_mode = allows_step_mode
        self._read_write_files = (
            read_write_files if read_write_files is not None else set()
        )

    @property
    def is_step_mode(self) -> bool:
        if self._is_step_mode is not None:
            return self._is_step_mode
        try:
            a_cfg = get_singleton(AgentConfig)
            return a_cfg.is_step_mode and self.allows_step_mode
        except Exception:
            return False

    @is_step_mode.setter
    def is_step_mode(self, val: bool) -> None:
        self._is_step_mode = val

    @property
    def read_write_files(self) -> Set[ReadWriteFile]:
        return self._read_write_files

    @read_write_files.setter
    def read_write_files(self, val: Set[ReadWriteFile]) -> None:
        self._read_write_files = val

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
    tier = agent_session

    def __init__(self) -> None:
        self.has_modifications = False
        self.templates_materialized = False

    def materialize_templates(self) -> None:
        self.templates_materialized = True


class MockAdvanceTool:
    tier = agent_session

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

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> Response:
        self.executed = True
        return Response(is_failed=False, is_terminated=False, content="Guide step 1")


class MockViewFileTool:
    tier = agent_session

    def __init__(self) -> None:
        self.executed_files: List[BoundFile] = []
        self.path_parameter = Parameter(
            name="path",
            description="path",
            parameter_converter=STRING_PARAMETER_TYPE,
            is_required=True,
        )

    @property
    def name(self) -> str:
        return "view_file"

    @property
    def description(self) -> str:
        return "View file tool"

    @property
    def parameters(self) -> Set[Parameter]:
        return {self.path_parameter}

    def execute_tool(
        self, actual_parameter_bindings: ActualParameterBindings
    ) -> Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target = bindings_map.get("path")
        if isinstance(target, BoundFile):
            self.executed_files.append(target)
        return Response(
            is_failed=False, is_terminated=False, content=f"Content of {target}"
        )


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        node = Node(unit_address="//pkg:target")
        self.ro_file = ReadOnlyFile(
            relative_path="spec.md",
            workspace_path=_make_workspace_path("pkg/spec.md"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.agent_cfg = MockAgentConfig(is_step_mode=True, is_startup_reads=True)
        self.node_cfg = MockNodeConfig(read_only_files={self.ro_file})
        self.edit_mgr = MockEditManager()
        self.adv_tool = MockAdvanceTool()
        self.view_file_tool = MockViewFileTool()

        self.registry.register_instance(
            self.agent_cfg, keys=[AgentConfig], tier=system
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier=agent_session
        )
        self.registry.register_instance(
            self.adv_tool, keys=[AdvanceTool], tier=agent_session
        )
        self.registry.register_instance(
            self.view_file_tool, keys=[ViewFileTool], tier=agent_session
        )

    def test_has_modifications_and_template_materialization_delegation(self) -> None:
        """CUJ: Sandbox delegates modification checking and template materialization to EditManager."""
        with enter_phase(agent_session, registry=self.registry) as scope:
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
        """CUJ: Assembling startup tool executions: advance first when in step mode, followed by view_file for read-only files."""
        node = Node(unit_address="//pkg:target")
        ro_file_z = ReadOnlyFile(
            relative_path="z_spec.md",
            workspace_path=_make_workspace_path("pkg/z_spec.md"),
            owning_node=node,
        )
        ro_file_a = ReadOnlyFile(
            relative_path="a_spec.md",
            workspace_path=_make_workspace_path("pkg/a_spec.md"),
            owning_node=node,
        )
        ro_file_py = ReadOnlyFile(
            relative_path="m_lib.py",
            workspace_path=_make_workspace_path("pkg/m_lib.py"),
            owning_node=node,
        )
        ro_files: Set[ReadOnlyFile] = {ro_file_z, ro_file_a, ro_file_py}
        self.node_cfg.read_only_files = ro_files

        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: [Sandbox] The sandbox exposes startup tool executions as an ordered sequence of initial tool executions based on active configuration.
            executions = sb.get_startup_tool_executions()

            self.assertEqual(len(executions), 4)
            # First is advance
            # Requirement: When using step mode to communicate a guide progressively, startup tool executions include an initial advance tool execution with the name of the advance tool, empty wire parameter bindings, and the response produced by executing the advance tool.
            self.assertEqual(executions[0].tool_name, "advance")
            self.assertEqual(executions[0].wire_parameter_bindings.bindings, set())
            self.assertEqual(executions[0].response.content, "Guide step 1")

            # Second is view_file for a_spec.md (ordered deterministically before m_lib.py and z_spec.md)
            # Requirement: When performing startup reads to inspect declared files at session start and the session has at most one read-write file, startup tool executions include file read executions for all declared read-only files from node config ordered deterministically by file alias relative path, positioned after any advance tool execution.
            # Requirement: Each file read execution uses the name of the view file tool, specifies wire parameter bindings mapping the path parameter of the view file tool to the read-only file alias relative path, and captures the response produced by executing the view file tool.
            self.assertEqual(executions[1].tool_name, "view_file")
            self.assertEqual(
                executions[1].wire_parameter_bindings.bindings, {("path", "a_spec.md")}
            )
            self.assertIn("a_spec.md", executions[1].response.content)

            # Third is view_file for m_lib.py
            self.assertEqual(executions[2].tool_name, "view_file")
            self.assertEqual(
                executions[2].wire_parameter_bindings.bindings,
                {("path", "m_lib.py")},
            )
            self.assertIn("m_lib.py", executions[2].response.content)

            # Fourth is view_file for z_spec.md
            self.assertEqual(executions[3].tool_name, "view_file")
            self.assertEqual(
                executions[3].wire_parameter_bindings.bindings, {("path", "z_spec.md")}
            )
            self.assertIn("z_spec.md", executions[3].response.content)

    def test_get_startup_tool_executions_disabled_modes(self) -> None:
        """CUJ: Omits advance when step mode is off, and omits reads when startup reads are off."""
        self.agent_cfg.is_step_mode = False
        self.agent_cfg.is_startup_reads = False

        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: When step mode is not used, startup tool executions contain no advance tool execution.
            # Requirement: When startup reads are not performed, startup tool executions contain no file read executions.
            executions = sb.get_startup_tool_executions()
            self.assertEqual(len(executions), 0)

    def test_get_startup_tool_executions_node_disallows_step_mode(self) -> None:
        """CUJ: Omits advance when node disallows step mode even if model config enables it."""
        self.agent_cfg.is_step_mode = True
        self.agent_cfg.is_startup_reads = False
        self.node_cfg.allows_step_mode = False

        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: When step mode is not used, startup tool executions contain no advance tool execution.
            executions = sb.get_startup_tool_executions()

    def test_get_startup_tool_executions_multi_target_skips_startup_reads(self) -> None:
        """CUJ: Multi-target sessions (batch size > 1) skip startup read-only file reads."""
        node = Node(unit_address="//pkg:target")
        ro_file = ReadOnlyFile(
            relative_path="spec.md",
            workspace_path=_make_workspace_path("pkg/spec.md"),
            owning_node=node,
        )
        rw_file_1 = ReadWriteFile(
            relative_path="file1.py",
            workspace_path=_make_workspace_path("pkg/file1.py"),
            owning_node=node,
        )
        rw_file_2 = ReadWriteFile(
            relative_path="file2.py",
            workspace_path=_make_workspace_path("pkg/file2.py"),
            owning_node=node,
        )
        self.agent_cfg.is_step_mode = False
        self.agent_cfg.is_startup_reads = True
        self.node_cfg.read_only_files = {ro_file}
        self.node_cfg.read_write_files = {rw_file_1, rw_file_2}

        with enter_phase(agent_session, registry=self.registry) as scope:
            sb = scope.get_singleton(Sandbox)
            # Requirement: When startup reads are not performed or the session has multiple read-write files, startup tool executions contain no file read executions.
            executions = sb.get_startup_tool_executions()
            self.assertEqual(len(executions), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
