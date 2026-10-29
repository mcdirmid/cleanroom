"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for EditManager and file_editor_impl."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
import tempfile
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, Union, cast
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.session import session as agent_session
from update_with_ai.parts.agent.lib import (
    agent_config,
    file_alias,
    node_config,
)
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.sandbox.lib import (
    file_editor,
    file_reader,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.file_editor import (
    EditManager,
    FileHash,
    FileUpdateRevision,
)
from update_with_ai.parts.sandbox.lib.file_editor_impl import (
    EditManager as RealEditManager,
    ReplaceFileContentTool,
    __initialize__,
)


INITIAL_CONTENT = (
    "line one\n"
    "repeated\n"
    "    indented line\n"
    "repeated\n"
    "unique_target\n"
    "outside_target\n"
)


# ==============================================================================
# 1. State Machine Protocol Definition
# ==============================================================================

@dataclass
class EditManagerState:
    """Canonical model state for EditManager."""
    has_modifications: bool = False
    revision: int = 0
    last_file: Optional[file_alias.FileAlias] = None
    writable_files: PretenseSet[file_alias.ReadWriteFile] = field(default_factory=PretenseSet)
    file_hashes: PretenseDict[str, str] = field(default_factory=PretenseDict)


class EditManagerStateMachine(StateMachine[EditManagerState]):
    """Pretense StateMachine for EditManager."""

    def __init__(self, state: Optional[EditManagerState] = None):
        super().__init__(state=state or EditManagerState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_writable_file(
        self,
        ctx: TransitionContext[None, [str], None],
    ) -> None:
        ctx.arguments(relative_path=Domain(strategy=lambda: 'lib/module.py'))
        def _consequent(res: None, relative_path: str = "lib/module.py") -> None:
            node = DagNode(UnitAddress("target"), RoleAddress("lib"))
            rel = file_alias.RelativePath(relative_path)
            ws = file_paths.WorkspacePath(file_paths.PathString(f"ws/{relative_path}"))
            self.state.writable_files.add(file_alias.ReadWriteFile(rel, ws, node))
        ctx.update(_consequent)

    # ==============================================================================
    # 2. Interface Transitions
    # ==============================================================================

    @transition(name="has_modifications")
    def has_modifications(
        self,
        ctx: TransitionContext[EditManager, [], bool],
    ) -> None:
        ctx.returns(lambda: self.state.has_modifications)

    @transition(name="file_update_revision")
    def file_update_revision(
        self,
        ctx: TransitionContext[EditManager, [], FileUpdateRevision],
    ) -> None:
        ctx.returns(lambda: FileUpdateRevision(self.state.revision))

    @transition(name="last_read_or_edited_file")
    def last_read_or_edited_file(
        self,
        ctx: TransitionContext[EditManager, [], Optional[file_alias.FileAlias]],
    ) -> None:
        ctx.returns(lambda: self.state.last_file)

    @transition(EditManager.can_write)
    def can_write(
        self,
        ctx: TransitionContext[EditManager, [file_alias.RelativePath], tool_provider.ToolResponse],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: file_alias.RelativePath('lib/module.py')))
        def _returns(file_path: Optional[file_alias.RelativePath] = None) -> tool_provider.ToolResponse:
            p = file_path or file_alias.RelativePath("lib/module.py")
            writable_paths = {str(f.relative_path) for f in self.state.writable_files}
            path_str = str(p)
            if path_str in writable_paths:
                return tool_provider.ToolResponse(
                    is_failed=False,
                    is_terminated=True,
                    content=tool_provider.ToolResponseContent(f"Write permitted for '{path_str}'."),
                )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=True,
                content=tool_provider.ToolResponseContent(f"Error: Permission denied for writing '{path_str}'."),
            )
        ctx.returns(_returns)

    @transition(EditManager.record_file_edit)
    def record_file_edit(
        self,
        ctx: TransitionContext[EditManager, [file_alias.FileAlias], None],
    ) -> None:
        ctx.arguments(file=Domain(strategy=lambda: file_alias.UnboundFile(file_alias.RelativePath('lib/module.py'))))
        def _consequent(res: None, file: Optional[file_alias.FileAlias] = None) -> None:
            f = file or file_alias.UnboundFile(file_alias.RelativePath("lib/module.py"))
            self.state.has_modifications = True
            self.state.revision += 1
            self.state.last_file = f
        ctx.update(_consequent)


proto = EditManagerStateMachine()


class TestEditManagerUnit(unittest.TestCase):
    """Unit tests for synthesized EditManager fake."""

    def setUp(self) -> None:
        self.state = EditManagerState()
        self.sm = EditManagerStateMachine(self.state)
        self.sm.seed_writable_file("lib/demo.py")
        self.fake: EditManager = self.sm.as_fake(EditManager)

    def test_default_edit_state(self) -> None:
        self.assertFalse(self.fake.has_modifications)
        self.assertEqual(int(self.fake.file_update_revision), 0)
        self.assertIsNone(self.fake.last_read_or_edited_file)

    def test_record_edit_advances_revision(self) -> None:
        f = file_alias.UnboundFile(file_alias.RelativePath("lib/demo.py"))
        self.fake.record_file_edit(cast(Any, f))
        self.assertTrue(self.fake.has_modifications)
        self.assertEqual(int(self.fake.file_update_revision), 1)
        self.assertEqual(self.fake.last_read_or_edited_file, f)

    def test_can_write_success_and_denied(self) -> None:
        ok = self.fake.can_write(file_alias.RelativePath("lib/demo.py"))
        self.assertFalse(ok.is_failed)
        denied = self.fake.can_write(file_alias.RelativePath("other.py"))
        self.assertTrue(denied.is_failed)


# ==============================================================================
# 2. Real Implementation Verification Tests
# ==============================================================================

def _make_read_only_file(rel_path: str) -> file_alias.ReadOnlyFile:
    return file_alias.ReadOnlyFile(
        relative_path=file_alias.RelativePath(rel_path),
        workspace_path=file_paths.WorkspacePath(
            file_paths.PathString(rel_path)
        ),
        owning_node=cast(Any, None),
    )


def _make_read_write_file(rel_path: str) -> file_alias.ReadWriteFile:
    return file_alias.ReadWriteFile(
        relative_path=file_alias.RelativePath(rel_path),
        workspace_path=file_paths.WorkspacePath(
            file_paths.PathString(rel_path)
        ),
        owning_node=cast(Any, None),
    )


class _MockAgentConfig:
    tier = system

    def __init__(self, edit_delta_output: bool = False) -> None:
        self._edit_delta_output = edit_delta_output

    @property
    def conversation_limit(self) -> agent_config.ConversationLimit:
        return agent_config.ConversationLimit(100)

    @property
    def inject_followups(self) -> bool:
        return False

    @property
    def is_step_mode(self) -> bool:
        return False

    @property
    def is_startup_reads(self) -> bool:
        return False

    @property
    def edit_delta_output(self) -> bool:
        return self._edit_delta_output

    @property
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        return agent_config.SupersedeArgKeepLimit(50)


class _MockNodeConfig:
    tier = agent_session

    def __init__(
        self,
        read_only_files: Optional[Set[file_alias.ReadOnlyFile]] = None,
        read_write_files: Optional[Set[file_alias.ReadWriteFile]] = None,
    ) -> None:
        self._read_only_files = read_only_files if read_only_files is not None else set()
        self._read_write_files = read_write_files if read_write_files is not None else set()

    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        return self._read_only_files

    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        return self._read_write_files

    @property
    def template_parameters(self) -> Mapping[node_config.TemplateParamKey, Any]:
        return {}


class _MockToolManager:
    tier = agent_session

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


class _MockAliasManager:
    tier = agent_session

    def __init__(
        self,
        workspace_root: str,
        known_files: Optional[Set[file_alias.FileAlias]] = None,
    ) -> None:
        self._workspace_root = file_paths.WorkspaceRoot(
            file_paths.PathString(str(workspace_root))
        )
        self._known_files = known_files if known_files is not None else set()

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
        for f in self._known_files:
            if str(f.relative_path) == path:
                return f
        return file_alias.UnboundFile(file_alias.RelativePath(path))

    convert = to_alias

    def sanitize_text(
        self, text: file_alias.UnsanitizedText
    ) -> file_alias.SanitizedText:
        return file_alias.SanitizedText(str(text))


class _MockAliasManagerType:
    tier = agent_session

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


class _MockSourceMetadataCoordinator:
    tier = agent_session

    def __init__(self) -> None:
        self.recorded_modifications: Set[str] = set()
        self.always_modified: bool = False

    def record_code_modified(self, path: Any) -> None:
        self.recorded_modifications.add(str(path))

    def is_code_modified(self, path: Any) -> bool:
        return self.always_modified or str(path) in self.recorded_modifications

    def is_metadata_altered(
        self, original_content: str, new_content: str, filename: str
    ) -> bool:
        return False


class _MockViewFileTool:
    tier = agent_session
    name = tool_provider.ToolName("view_file")

    def execute_tool(
        self,
        bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(""),
        )


class TestFileEditorReal(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.rw_host_path = os.path.join(self.root, "read_write.py")
        with open(self.rw_host_path, "w", encoding="utf-8") as fh:
            fh.write(INITIAL_CONTENT)
        with open(os.path.join(self.root, "read_only.py"), "w", encoding="utf-8") as fh:
            fh.write("readonly\n")

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.read_only_file = _make_read_only_file("read_only.py")
        self.read_write_file = _make_read_write_file("read_write.py")
        self.mock_node_config = _MockNodeConfig(
            read_only_files={self.read_only_file},
            read_write_files={self.read_write_file},
        )
        self.registry.register_instance(
            self.mock_node_config,
            keys=[node_config.NodeConfig],
            tier=agent_session,
        )
        self.registry.register_instance(
            _MockAgentConfig(),
            keys=[agent_config.AgentConfig],
            tier=system,
        )
        self.mock_tool_manager = _MockToolManager()
        self.registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session,
        )
        self.mock_alias_manager = _MockAliasManager(
            self.root, known_files={self.read_only_file, self.read_write_file}
        )
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[
                file_alias.AliasManager,
            ],
            tier=agent_session,
        )
        self.registry.register_instance(
            _MockAliasManagerType(self.mock_alias_manager),
            keys=[tool_provider.AliasManagerType],
            tier=agent_session,
        )
        self.mock_src_metadata = _MockSourceMetadataCoordinator()
        self.registry.register_instance(
            self.mock_src_metadata,
            keys=[src_metadata.SourceMetadataCoordinator],
            tier=agent_session,
        )
        self.registry.register_singleton(
            _MockViewFileTool,
            keys=[file_reader.ViewFileTool],
            tier=agent_session,
        )

    def _read_rw(self) -> str:
        with open(self.rw_host_path, "r", encoding="utf-8") as fh:
            return fh.read()

    def _bindings(
        self,
        tool: ReplaceFileContentTool,
        target: str,
        replacement: str,
        path: Optional[file_alias.FileAlias] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        allow_multiple: Optional[bool] = None,
    ) -> Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]:
        params = tool.parameters
        bindings: Dict[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType] = {
            params[tool_provider.ParameterName("target_content")]: tool_provider.SomeParameterActualType(
                file_editor.TargetContent(target)
            ),
            params[tool_provider.ParameterName("replacement_content")]: tool_provider.SomeParameterActualType(
                file_editor.ReplacementContent(replacement)
            ),
            params[tool_provider.ParameterName("start_line")]: tool_provider.SomeParameterActualType(
                None if start_line is None else file_editor.LineNumber(start_line)
            ),
            params[tool_provider.ParameterName("end_line")]: tool_provider.SomeParameterActualType(
                None if end_line is None else file_editor.LineNumber(end_line)
            ),
            params[tool_provider.ParameterName("allow_multiple")]: tool_provider.SomeParameterActualType(
                file_editor.AllowMultiple(bool(allow_multiple))
            ),
        }
        if path is not None:
            bindings[params[tool_provider.ParameterName("path")]] = tool_provider.SomeParameterActualType(path)
        return bindings

    def test_initialization(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            for cls in [RealEditManager, ReplaceFileContentTool]:
                instance = scope.get_singleton(cls)
                self.assertIsNotNone(instance)
            self.assertIn(
                tool_provider.ToolName("replace_file_content"),
                self.mock_tool_manager.installed_tools,
            )

    def test_replace_success_writes_and_reminds(self) -> None:
        self.mock_src_metadata.always_modified = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            mgr = scope.get_singleton(RealEditManager)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="unique_target",
                    replacement="replaced_target",
                    path=self.read_write_file,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertIn("replaced_target", self._read_rw())
            self.assertTrue(mgr.has_modifications)
            self.assertEqual(int(mgr.file_update_revision), 1)

    def test_can_write_access_control(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(RealEditManager)
            ok = mgr.can_write(self.read_write_file.relative_path)
            self.assertFalse(ok.is_failed)
            denied = mgr.can_write(file_alias.RelativePath("unknown.py"))
            self.assertTrue(denied.is_failed)

    def test_replace_target_not_found(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="nonexistent",
                    replacement="foo",
                    path=self.read_write_file,
                )
            )
            self.assertTrue(resp.is_failed)

    def test_replace_rejects_read_only_file(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="readonly",
                    replacement="foo",
                    path=self.read_only_file,
                )
            )
            self.assertTrue(resp.is_failed)

    def test_replace_multiple_rejected_when_not_allowed(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="repeated",
                    replacement="new",
                    path=self.read_write_file,
                    allow_multiple=False,
                )
            )
            self.assertTrue(resp.is_failed)

    def test_replace_multiple_when_allowed(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="repeated",
                    replacement="new",
                    path=self.read_write_file,
                    allow_multiple=True,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertEqual(self._read_rw().count("new"), 2)

    def test_replace_creates_missing_parent_dirs(self) -> None:
        new_file = _make_read_write_file("sub/dir/new.py")
        self.mock_alias_manager._known_files.add(new_file)
        self.mock_node_config.read_write_files.add(new_file)
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="",
                    replacement="content\n",
                    path=new_file,
                )
            )
            self.assertFalse(resp.is_failed)
            abs_new = os.path.join(self.root, "sub/dir/new.py")
            self.assertTrue(os.path.isfile(abs_new))

    def test_file_hash_computation(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            mgr = scope.get_singleton(RealEditManager)
            h = mgr.file_hash(self.read_write_file)
            expected = hashlib.md5(INITIAL_CONTENT.encode("utf-8")).hexdigest()
            self.assertEqual(str(h), expected)

    def test_parameter_converters(self) -> None:
        from update_with_ai.parts.sandbox.lib.file_editor_impl import (  # cleanroom: allow-private-import
            _TargetContentParamType,
            _ReplacementContentParamType,
            _LineNumberParamType,
            _AllowMultipleParamType,
        )
        tc = _TargetContentParamType()
        self.assertEqual(tc.convert("hello"), file_editor.TargetContent("hello"))
        rc = _ReplacementContentParamType()
        self.assertEqual(rc.convert("world"), file_editor.ReplacementContent("world"))
        ln = _LineNumberParamType()
        self.assertEqual(ln.convert(10), file_editor.LineNumber(10))
        am = _AllowMultipleParamType()
        self.assertEqual(am.convert(True), file_editor.AllowMultiple(True))

    def test_replace_bounded_line_range_and_whitespace_fallback(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            # Line range replacement
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="unique_target",
                    replacement="bounded_target",
                    path=self.read_write_file,
                    start_line=4,
                    end_line=6,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertIn("bounded_target", self._read_rw())

            # Whitespace fallback (target has different indent)
            resp_ws = tool.execute_tool(
                self._bindings(
                    tool,
                    target="indented line",
                    replacement="    clean indented line",
                    path=self.read_write_file,
                )
            )
            self.assertFalse(resp_ws.is_failed)
            self.assertIn("clean indented line", self._read_rw())

    def test_replace_edge_cases(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)

            # No-op replacement fails
            resp_noop = tool.execute_tool(
                self._bindings(
                    tool,
                    target="unique_target",
                    replacement="unique_target",
                    path=self.read_write_file,
                )
            )
            self.assertTrue(resp_noop.is_failed)

            # Invalid line bounds (start_line > end_line)
            resp_bounds = tool.execute_tool(
                self._bindings(
                    tool,
                    target="unique_target",
                    replacement="foo",
                    path=self.read_write_file,
                    start_line=5,
                    end_line=3,
                )
            )
            self.assertTrue(resp_bounds.is_failed)

            # Append at total_lines + 1
            total_lines = len(self._read_rw().splitlines())
            resp_append = tool.execute_tool(
                self._bindings(
                    tool,
                    target="",
                    replacement="appended_line\n",
                    path=self.read_write_file,
                    start_line=total_lines + 1,
                    end_line=None,
                )
            )
            self.assertFalse(resp_append.is_failed)
            self.assertTrue(self._read_rw().endswith("appended_line\n"))

            # Metadata altered error
            self.mock_src_metadata.is_metadata_altered = lambda original_content, new_content, filename: True
            resp_meta = tool.execute_tool(
                self._bindings(
                    tool,
                    target="appended_line",
                    replacement="tampered_metadata",
                    path=self.read_write_file,
                )
            )
            self.assertTrue(resp_meta.is_failed)
            self.assertIn("metadata", str(resp_meta.content).lower())

    def test_replace_omitted_path_binds_last_read_write_file(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ReplaceFileContentTool)
            mgr = scope.get_singleton(RealEditManager)
            mgr.record_file_read(self.read_write_file)
            resp = tool.execute_tool(
                self._bindings(
                    tool,
                    target="unique_target",
                    replacement="auto_bound",
                    path=None,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertIn("auto_bound", self._read_rw())


# ==============================================================================
# 3. Hypothesis Property Fuzz Testing
# ==============================================================================

class TestEditManagerFuzz(unittest.TestCase):
    """Property fuzz testing for EditManager invariants."""

    @settings(max_examples=30)
    @given(
        num_edits=st.integers(min_value=1, max_value=10),
    )
    def test_revision_strictly_monotonically_increases(self, num_edits: int) -> None:
        state = EditManagerState()
        sm = EditManagerStateMachine(state)
        fake = sm.as_fake(EditManager)

        for i in range(1, num_edits + 1):
            f = file_alias.UnboundFile(file_alias.RelativePath(f"file_{i}.py"))
            fake.record_file_edit(cast(Any, f))
            self.assertEqual(int(fake.file_update_revision), i)
            self.assertTrue(fake.has_modifications)
            self.assertEqual(fake.last_read_or_edited_file, f)
