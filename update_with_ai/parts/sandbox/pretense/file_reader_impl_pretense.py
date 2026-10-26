"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for ReadManager."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, Union, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import agent_session, file_alias, node_config
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from update_with_ai.parts.sandbox.lib import (
    file_editor,
    file_reader,
    template_format,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.file_reader import ReadManager
from update_with_ai.parts.sandbox.lib.tool_provider import ToolResponse, ToolResponseContent


@dataclass
class ReadManagerState:
    """Canonical model state for ReadManager."""
    read_only_files: PretenseSet[file_alias.ReadOnlyFile] = field(default_factory=PretenseSet)
    read_write_files: PretenseSet[file_alias.ReadWriteFile] = field(default_factory=PretenseSet)


proto = StateMachineProto[ReadManagerState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_readable_file(): pass

@seed_readable_file.arguments
def _(
    state: ReadManagerState,
    this: Any,
    relative_path: str | NotBoundType = NotBound,
    is_readonly: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, bool]]:
    p = "lib/module.py" if isinstance(relative_path, NotBoundType) else str(relative_path)
    ro = True if isinstance(is_readonly, NotBoundType) else bool(is_readonly)
    return (p, ro)

@seed_readable_file.provide
def _(
    state: ReadManagerState,
    this: Any,
    relative_path: str,
    is_readonly: bool,
    result: None = None,
) -> None:
    node = DagNode(UnitAddress("target"), RoleAddress("lib"))
    rel = file_alias.RelativePath(relative_path)
    ws = file_paths.WorkspacePath(file_paths.PathString(f"ws/{relative_path}"))
    if is_readonly:
        state.read_only_files.add(file_alias.ReadOnlyFile(rel, ws, node))
    else:
        state.read_write_files.add(file_alias.ReadWriteFile(rel, ws, node))


# ==============================================================================
# 2. ReadManager Transitions
# ==============================================================================

@proto.transition(name="read_only_files")
def read_only_files(): pass

@read_only_files.returns
def _(state: ReadManagerState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Set[file_alias.ReadOnlyFile]]]:
    expected = set(state.read_only_files)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="read_write_files")
def read_write_files(): pass

@read_write_files.returns
def _(state: ReadManagerState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Set[file_alias.ReadWriteFile]]]:
    expected = set(state.read_write_files)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(ReadManager.can_read)
def can_read(): pass

@can_read.arguments
def _(
    state: ReadManagerState,
    this: Any,
    path: Union[file_alias.RelativePath, file_alias.FileAlias] | str | NotBoundType = NotBound,
) -> Optional[Tuple[Union[file_alias.RelativePath, file_alias.FileAlias]]]:
    if isinstance(path, NotBoundType):
        p = file_alias.RelativePath("lib/module.py")
    elif isinstance(path, str):
        p = file_alias.RelativePath(path)
    else:
        p = path
    return (p,)

@can_read.returns
def _(
    state: ReadManagerState,
    this: Any,
    path: Union[file_alias.RelativePath, file_alias.FileAlias],
    outcome: object = NotBound,
) -> Optional[Outcome[ToolResponse]]:
    rel = str(path.relative_path if isinstance(path, file_alias.FileAlias) else path)
    ro_rels = {str(f.relative_path) for f in state.read_only_files}
    rw_rels = {str(f.relative_path) for f in state.read_write_files}

    if rel in ro_rels or rel in rw_rels:
        expected = ToolResponse(is_failed=False, is_terminated=False, content=ToolResponseContent(f"Access granted for {rel}"))
    else:
        expected = ToolResponse(is_failed=True, is_terminated=False, content=ToolResponseContent(f"Permission denied: {rel} is not a declared readable file."))

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_read_manager_fake(state: Optional[ReadManagerState] = None) -> ReadManager:
    """Instantiate a synthesized ReadManager fake."""
    st = state or ReadManagerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(ReadManager)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestReadManagerUnit(unittest.TestCase):
    """Unit tests for synthesized ReadManager fake."""

    def setUp(self) -> None:
        self.state = ReadManagerState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_readable_file("lib/demo.py", is_readonly=True)
        self.sm.seed_readable_file("tests/demo_test.py", is_readonly=False)
        self.fake: ReadManager = self.sm.as_fake(ReadManager)

    def test_read_properties(self) -> None:
        self.assertEqual(len(self.fake.read_only_files), 1)
        self.assertEqual(len(self.fake.read_write_files), 1)

    def test_can_read_success(self) -> None:
        resp = self.fake.can_read(file_alias.RelativePath("lib/demo.py"))
        self.assertIn("Access granted", resp.content)

    def test_can_read_denied(self) -> None:
        resp = self.fake.can_read(file_alias.RelativePath("secret.txt"))
        self.assertIn("Permission denied", resp.content)


def _make_read_only_file(rel_path: str, host_path: Optional[str] = None) -> file_alias.ReadOnlyFile:
    path = host_path if host_path is not None else rel_path
    return file_alias.ReadOnlyFile(
        relative_path=file_alias.RelativePath(rel_path),
        workspace_path=file_paths.WorkspacePath(file_paths.PathString(path)),
        owning_node=cast(Any, None),
    )


def _make_read_write_file(rel_path: str, host_path: Optional[str] = None) -> file_alias.ReadWriteFile:
    path = host_path if host_path is not None else rel_path
    return file_alias.ReadWriteFile(
        relative_path=file_alias.RelativePath(rel_path),
        workspace_path=file_paths.WorkspacePath(file_paths.PathString(path)),
        owning_node=cast(Any, None),
    )


class _MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(
        self,
        read_only_files: Optional[Set[file_alias.ReadOnlyFile]] = None,
        read_write_files: Optional[Set[file_alias.ReadWriteFile]] = None,
        template_parameters: Optional[Mapping[node_config.TemplateParamKey, Any]] = None,
    ) -> None:
        self._read_only_files = read_only_files if read_only_files is not None else set()
        self._read_write_files = read_write_files if read_write_files is not None else set()
        self._template_parameters = template_parameters if template_parameters is not None else {}

    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        return self._read_only_files

    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        return self._read_write_files

    @property
    def template_parameters(self) -> Mapping[node_config.TemplateParamKey, Any]:
        return self._template_parameters


class _MockToolManager:
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


class _MockEditManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.reads: List[file_alias.FileAlias] = []
        self._last_file: Optional[file_alias.FileAlias] = None

    @property
    def last_read_or_edited_file(self) -> Optional[file_alias.FileAlias]:
        return self._last_file

    def record_file_read(self, file: file_alias.FileAlias) -> None:
        self.reads.append(file)
        self._last_file = file


class _MockTemplateFormatter:
    tier = agent_session.agent_session

    def format_template(
        self,
        text: template_format.TemplateText,
        parameters: Mapping[template_format.TemplateKey, Any],
    ) -> template_format.FormattedText:
        res = str(text)
        for k, v in parameters.items():
            res = res.replace(f"<{k}>", str(v))
        return template_format.FormattedText(res)


class _MockAliasManager:
    tier = agent_session.agent_session

    def __init__(self, workspace_root: str = "/tmp/workspace") -> None:
        self._workspace_root = file_paths.WorkspaceRoot(
            file_paths.PathString(str(workspace_root))
        )

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        return self._workspace_root

    @property
    def actual_type(self) -> type[file_alias.FileAlias]:
        return file_alias.FileAlias

    @property
    def wire_type(self) -> type[str]:
        return str

    def to_alias(self, path: str) -> file_alias.FileAlias:
        return file_alias.FileAlias(file_alias.RelativePath(path))

    convert = to_alias

    def sanitize_text(
        self, text: file_alias.UnsanitizedText
    ) -> file_alias.SanitizedText:
        s = str(text)
        root = str(self._workspace_root.path)
        if root in s:
            s = s.replace(root, "<sanitized_root>")
        return file_alias.SanitizedText(s)


class _MockAliasManagerType:
    tier = agent_session.agent_session

    def __init__(self, alias_mgr: _MockAliasManager) -> None:
        self._alias_mgr = alias_mgr

    @property
    def actual_type(self) -> type[file_alias.FileAlias]:
        return file_alias.FileAlias

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> file_alias.FileAlias:
        return self._alias_mgr.to_alias(wire_value)


class _MockFilePathManager:
    tier = system

    def create_host_path(self, path: Any) -> file_paths.HostPath:
        p = str(path.path) if isinstance(path, file_paths.HostPath) else str(path)
        return file_paths.HostPath(file_paths.PathString(p))

    def create_absolute_path(self, path: Any) -> file_paths.AbsolutePath:
        p = str(path.path) if isinstance(path, file_paths.HostPath) else str(path)
        return file_paths.AbsolutePath(file_paths.PathString(p))

    def create_workspace_path(self, path: Any) -> file_paths.WorkspacePath:
        p = str(path.path) if isinstance(path, file_paths.HostPath) else str(path)
        return file_paths.WorkspacePath(file_paths.PathString(p))

    def resolve_path(
        self, root: Any, relative: Any
    ) -> file_paths.AbsolutePath:
        root_str = str(root.path) if isinstance(root, file_paths.HostPath) else str(root)
        rel_str = str(relative.path) if isinstance(relative, file_paths.HostPath) else str(relative)
        return file_paths.AbsolutePath(file_paths.PathString(os.path.join(root_str, rel_str)))


class _MockRoleConfig:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.role = node_config.RoleName("developer")
        self.nodes: List[Any] = []
        self.version = node_config.ExecutionVersion(1)

    def set_role(self, role: Any) -> None:
        self.role = role

    def set_nodes(self, nodes: Any) -> None:
        self.nodes = list(nodes)


class TestFileReaderReal(unittest.TestCase):
    """Direct verification of the real file_reader_impl implementation."""

    def setUp(self) -> None:
        import tempfile
        from update_with_ai.parts.agent.lib import agent_session, node_config
        from update_with_ai.parts.sandbox.lib import (
            file_editor,
            file_reader,
            template_format,
            tool_provider,
        )
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            ReadManager as RealReadManager,
            ViewFileTool,
            RegexPatternParameterType,
            SearchTool,
            __initialize__,
        )

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name

        self.ro_host_path = os.path.join(self.root, "sample.py")
        with open(self.ro_host_path, "w", encoding="utf-8") as fh:
            fh.write(f"def hello():\n    return '{self.root}'\n")

        self.ro_md_host_path = os.path.join(self.root, "guide.md")
        with open(self.ro_md_host_path, "w", encoding="utf-8") as fh:
            fh.write("# Title\n\n> META: internal note\n\nHello <user>!\n")

        self.rw_host_path = os.path.join(self.root, "target.py")
        with open(self.rw_host_path, "w", encoding="utf-8") as fh:
            fh.write("class Target:\n    pass\n")

        self.declared_read_only = _make_read_only_file("sample.py", self.ro_host_path)
        self.declared_ro_md = _make_read_only_file("guide.md", self.ro_md_host_path)
        self.missing_read_only = _make_read_only_file("missing.py", os.path.join(self.root, "missing.py"))
        self.declared_read_write = _make_read_write_file("target.py", self.rw_host_path)
        self.missing_read_write = _make_read_write_file("absent_target.py", os.path.join(self.root, "absent_target.py"))

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.mock_node_config = _MockNodeConfig(
            read_only_files={self.declared_read_only, self.declared_ro_md, self.missing_read_only},
            read_write_files={self.declared_read_write, self.missing_read_write},
            template_parameters={node_config.TemplateParamKey("user"): "Developer"},
        )
        self.registry.register_instance(
            self.mock_node_config,
            keys=[node_config.NodeConfig],
            tier=agent_session.agent_session,
        )
        self.mock_tool_manager = _MockToolManager()
        self.registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session.agent_session,
        )
        self.mock_edit_manager = _MockEditManager()
        self.registry.register_instance(
            self.mock_edit_manager,
            keys=[file_editor.EditManager],
            tier=agent_session.agent_session,
        )
        self.mock_template_formatter = _MockTemplateFormatter()
        self.registry.register_instance(
            self.mock_template_formatter,
            keys=[template_format.TemplateFormatter],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager = _MockAliasManager(self.root)
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[
                file_alias.AliasManager,
            ],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            _MockAliasManagerType(self.mock_alias_manager),
            keys=[tool_provider.AliasManagerType],
            tier=agent_session.agent_session,
        )
        self.mock_file_path_manager = _MockFilePathManager()
        self.registry.register_instance(
            self.mock_file_path_manager,
            keys=[file_paths.FilePathManager],
            tier=system,
        )
        self.mock_role_config = _MockRoleConfig()
        self.registry.register_instance(
            self.mock_role_config,
            keys=[node_config.RoleConfig],
            tier=agent_session.agent_session,
        )

    def test_initialization(self) -> None:
        from update_with_ai.parts.agent.lib import agent_session
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            ReadManager as RealReadManager,
            ViewFileTool,
            RegexPatternParameterType,
            SearchTool,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            for cls in [RealReadManager, ViewFileTool, RegexPatternParameterType, SearchTool]:
                instance = scope.get_singleton(cls)
                self.assertIsNotNone(instance)
            self.assertIn(
                tool_provider.ToolName("view_file"),
                self.mock_tool_manager.installed_tools,
            )

    def test_read_manager_access_control(self) -> None:
        from update_with_ai.parts.agent.lib import agent_session
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            ReadManager as RealReadManager,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(RealReadManager)
            resp_decl = manager.can_read(file_alias.RelativePath("sample.py"))
            self.assertFalse(resp_decl.is_failed)
            self.assertEqual(resp_decl.content, "Access permitted for 'sample.py'.")

            resp_undecl = manager.can_read(file_alias.RelativePath("undeclared.py"))
            self.assertTrue(resp_undecl.is_failed)

    def test_read_manager_file_properties(self) -> None:
        from update_with_ai.parts.agent.lib import agent_session
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            ReadManager as RealReadManager,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(RealReadManager)
            self.assertEqual(manager.read_only_files, {self.declared_read_only, self.declared_ro_md, self.missing_read_only})
            self.assertEqual(manager.read_write_files, {self.declared_read_write, self.missing_read_write})

    def test_regex_pattern_conversion(self) -> None:
        from update_with_ai.parts.agent.lib import agent_session
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            RegexPatternParameterType,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            param_type = scope.get_singleton(RegexPatternParameterType)
            valid = param_type.convert("^test.*[0-9]+$")
            self.assertEqual(valid, file_alias.RegexPattern("^test.*[0-9]+$"))

            with self.assertRaises(tool_provider.ParameterConversionError):
                param_type.convert("[invalid(regex")

    def test_view_file_tool(self) -> None:
        from update_with_ai.parts.agent.lib import agent_session
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            ViewFileTool,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ViewFileTool)
            resp = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.declared_read_only),
            })
            self.assertFalse(resp.is_failed)
            content_str = str(resp.content)
            self.assertIn("1: def hello():", content_str)
            self.assertIn("<sanitized_root>", content_str)
            self.assertIsNone(resp.suppression_key)

            # Read-write file
            resp_rw = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.declared_read_write),
            })
            self.assertFalse(resp_rw.is_failed)
            self.assertIsNotNone(resp_rw.suppression_key)

            # Missing read-write file: empty
            resp_m_rw = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.missing_read_write),
            })
            self.assertFalse(resp_m_rw.is_failed)
            self.assertEqual(str(resp_m_rw.content).strip(), "")

            # Markdown file with META: and template param
            resp_md = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.declared_ro_md),
            })
            self.assertFalse(resp_md.is_failed)
            self.assertNotIn("> META:", str(resp_md.content))
            self.assertIn("Hello Developer!", str(resp_md.content))

            # Missing read-only file error
            resp_missing = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.missing_read_only),
            })
            self.assertTrue(resp_missing.is_failed)

            # Undeclared file
            unbound = file_alias.UnboundFile(file_alias.RelativePath("unbound.py"))
            resp_unbound = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(unbound),
            })
            self.assertTrue(resp_unbound.is_failed)

    def test_search_tool_execution(self) -> None:
        from update_with_ai.parts.agent.lib import agent_session
        from update_with_ai.parts.sandbox.lib.file_reader_impl import (
            SearchTool,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SearchTool)
            resp_match = tool.execute_tool({
                tool.regex_pattern_parameter: tool_provider.SomeParameterActualType(
                    file_alias.RegexPattern("def|class")
                ),
            })
            self.assertFalse(resp_match.is_failed)
            self.assertIn("def hello():", str(resp_match.content))

            resp_nomatch = tool.execute_tool({
                tool.regex_pattern_parameter: tool_provider.SomeParameterActualType(
                    file_alias.RegexPattern("nonexistent_xyz")
                ),
            })
            self.assertFalse(resp_nomatch.is_failed)

            resp_invalid = tool.execute_tool({
                tool.regex_pattern_parameter: tool_provider.SomeParameterActualType(
                    file_alias.RegexPattern("[invalid(")
                ),
            })
            self.assertTrue(resp_invalid.is_failed)



# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestReadManagerFuzz(unittest.TestCase):
    """Property fuzz testing for ReadManager."""

    @settings(max_examples=30)
    @given(
        declared=st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def test_can_read_invariants(self, declared: list[str]) -> None:
        state = ReadManagerState()
        sm = proto.make_state_machine(state)
        for d in declared:
            sm.seed_readable_file(f"lib/{d}.py", is_readonly=True)

        fake = sm.as_fake(ReadManager)
        for d in declared:
            self.assertIn("Access granted", fake.can_read(file_alias.RelativePath(f"lib/{d}.py")).content)

        # Undeclared path is denied
        self.assertIn("Permission denied", fake.can_read(file_alias.RelativePath("undeclared.py")).content)
