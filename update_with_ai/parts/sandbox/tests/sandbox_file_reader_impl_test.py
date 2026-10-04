"""Unit tests for sandbox_file_reader_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any, cast, Mapping, Optional, Set, Tuple

from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib.agent_file_alias import (
    AliasManager,
    BoundFile,
    FileAlias,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    RegexPattern,
    RelativePath,
    UnboundFile,
)
from update_with_ai.parts.agent.lib.agent_node_config import NodeGuide, NodeConfig
from update_with_ai.parts.sandbox.lib.template_format import TemplateFormatter
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_file_reader import (
    ReadManager,
    ViewFileTool,
    SearchTool,
)
from update_with_ai.parts.sandbox.lib.sandbox_file_reader_impl import (
    ReadManager as ReadManagerImpl,
    ViewFileTool as ViewFileToolImpl,
    RegexPatternParameterType as RegexPatternParameterTypeImpl,
    SearchTool as SearchToolImpl,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib.tool_provider import (
    IdentityParameterType,
    ParameterConversionError,
    ParameterName,
    ParameterType,
    Tool,
    ToolManager,
    ToolParameter,
    ToolResponse,
    ToolResponseContent,
    WireType,
)


class ActualParameterBindings(dict[Any, Any]):
    def __init__(self, bindings: Any) -> None:
        if isinstance(bindings, set):
            super().__init__(dict(bindings))
        else:
            super().__init__(bindings)


class MockToolManager:
    tier = agent_session

    def __init__(self) -> None:
        self.installed_tools: Set[Tool] = set()

    def install_tool(self, tool: Tool) -> None:
        self.installed_tools.add(tool)

    def execute_tool(
        self, name: Any, wire_parameter_bindings: Mapping[ParameterName, WireType]
    ) -> ToolResponse:
        return ToolResponse(is_failed=False, is_terminated=False, content=ToolResponseContent(""))


class MockEditManager:
    tier = agent_session

    def __init__(self) -> None:
        self.last_read_or_edited_file: Optional[FileAlias] = None

    def record_file_read(self, file: FileAlias) -> None:
        self.last_read_or_edited_file = file

    def record_file_edit(self, file: ReadWriteFile) -> None:
        self.last_read_or_edited_file = file


class MockBooleanConverter:
    tier = agent_session
    actual_type = bool
    wire_type = None

    def convert(self, wire_value: Any) -> bool:
        return bool(wire_value)


class MockAgentConfig:
    tier = agent_session

    def __init__(self, is_mcp_mode: bool = False) -> None:
        self.is_mcp_mode = is_mcp_mode


@dataclass(frozen=True)
class _WorkspacePathDouble:
    path: str

    def __str__(self) -> str:
        return self.path

    def __fspath__(self) -> str:
        return self.path


def _make_workspace_path(path: str) -> Any:
    return _WorkspacePathDouble(path)


def _make_workspace_root(path: str) -> Any:
    return _WorkspacePathDouble(path)


class MockAliasManager:
    tier = agent_session

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = _make_workspace_root(workspace_root)
        self.actual_type = FileAlias
        self.wire_type = str
        self.files: dict[str, FileAlias] = {}

    def convert(self, wire_value: Any) -> Any:
        if isinstance(wire_value, FileAlias):
            return wire_value
        if str(wire_value) in self.files:
            return self.files[str(wire_value)]
        return UnboundFile(relative_path=RelativePath(str(wire_value)))

    def sanitize_text(self, text: str) -> str:
        return text.replace(self.workspace_root.path, "[WORKSPACE]")


class MockTemplateFormatter:
    tier = agent_session

    def format_template(self, content: str, parameters: Mapping[str, Any]) -> str:
        res = content
        for k, v in parameters.items():
            res = res.replace(f"<{k}>", str(v))
        return res


class MockNodeConfig:
    tier = agent_session

    def __init__(
        self,
        ro_files: Set[BoundFile],
        rw_files: Set[BoundFile],
        guide_file: Optional[UnboundFile] = None,
        template_parameters: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.read_only_files = ro_files
        self.read_write_files = rw_files
        self.guide_file = guide_file
        self._template_parameters = template_parameters or {}

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        return self._template_parameters

    @property
    def templates(self) -> Mapping[BoundFile, FileContent]:
        return {}

    @property
    def guide(self) -> Optional[NodeGuide]:
        return None

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return set()


class SandboxFileReaderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.rw_path = os.path.join(self.test_dir, "writable.txt")
        self.ro_path = os.path.join(self.test_dir, "readonly.txt")
        self.ro_py_path = os.path.join(self.test_dir, "readonly.py")
        with open(self.rw_path, "w", encoding="utf-8") as f:
            f.write("Line 1 writable\nLine 2 writable\n")
        with open(self.ro_path, "w", encoding="utf-8") as f:
            f.write(
                f"Line 1 readonly at {self.test_dir}/readonly.txt\nLine 2 readonly\n"
            )
        with open(self.ro_py_path, "w", encoding="utf-8") as f:
            f.write("def foo():\n    pass\n")
        self.ro_md_path = os.path.join(self.test_dir, "spec.md")
        with open(self.ro_md_path, "w", encoding="utf-8") as f:
            f.write(
                "# Title <doc_name>\n\n"
                '> META: "Meta note at top."\n\n'
                "First section content.\n\n"
                '> META: "Multi-line meta note\n> continued on second line."\n\n'
                "> NOTE: Non-meta quote.\n\n"
                "Second section content.\n\n"
                '> META: "Trailing meta note."\n'
            )

        self.ro_pyi_path = os.path.join(self.test_dir, "stub.pyi")
        with open(self.ro_pyi_path, "w", encoding="utf-8") as f:
            f.write("class Stub:\n    pass\n")

        node = DagNode(unit_address=UnitAddress("//pkg:test"), role_address=RoleAddress(""))
        self.ro_file = ReadOnlyFile(
            relative_path=RelativePath("readonly.txt"),
            workspace_path=_make_workspace_path("readonly.txt"),
            owning_node=node,
        )
        self.ro_py_file = ReadOnlyFile(
            relative_path=RelativePath("readonly.py"),
            workspace_path=_make_workspace_path("readonly.py"),
            owning_node=node,
        )
        self.ro_pyi_file = ReadOnlyFile(
            relative_path=RelativePath("stub.pyi"),
            workspace_path=_make_workspace_path("stub.pyi"),
            owning_node=node,
        )
        self.ro_md_file = ReadOnlyFile(
            relative_path=RelativePath("spec.md"),
            workspace_path=_make_workspace_path("spec.md"),
            owning_node=node,
        )
        self.rw_file = ReadWriteFile(
            relative_path=RelativePath("writable.txt"),
            workspace_path=_make_workspace_path("writable.txt"),
            owning_node=node,
        )
        self.guide_unbound = UnboundFile(relative_path=RelativePath("guide.md"))

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.tool_mgr = MockToolManager()
        self.bool_conv = MockBooleanConverter()
        self.alias_mgr = MockAliasManager(self.test_dir)
        self.alias_mgr.files = {
            self.ro_file.relative_path: self.ro_file,
            self.ro_py_file.relative_path: self.ro_py_file,
            self.ro_pyi_file.relative_path: self.ro_pyi_file,
            self.ro_md_file.relative_path: self.ro_md_file,
            self.rw_file.relative_path: self.rw_file,
            self.guide_unbound.relative_path: self.guide_unbound,
        }
        self.template_formatter = MockTemplateFormatter()
        self.edit_mgr = MockEditManager()
        self.agent_cfg = MockAgentConfig(is_mcp_mode=False)
        self.node_cfg = MockNodeConfig(
            ro_files={self.ro_file, self.ro_py_file, self.ro_pyi_file, self.ro_md_file},
            rw_files={self.rw_file},
            guide_file=self.guide_unbound,
            template_parameters={"doc_name": "MyDoc"},
        )

        self.registry.register_instance(
            self.tool_mgr, keys=[ToolManager], tier=agent_session
        )
        self.registry.register_instance(
            self.bool_conv, keys=[IdentityParameterType], tier=agent_session
        )
        self.registry.register_instance(
            self.alias_mgr, keys=[AliasManager], tier=agent_session
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.template_formatter, keys=[TemplateFormatter], tier=agent_session
        )
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier=agent_session
        )
        self.registry.register_instance(
            self.agent_cfg, keys=[AgentConfig], tier=agent_session
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_regex_pattern_converter(self) -> None:
        """CUJ: Converting wire string into RegexPattern."""
        conv = RegexPatternParameterTypeImpl()
        # Verify regex pattern parameter type converts a wire type string into a regex pattern
        pattern = conv.convert(r"foo\d+")
        self.assertEqual(pattern, r"foo\d+")

    def test_read_manager_initialization_and_properties(self) -> None:
        """CUJ: ReadManager installs tools and exposes declared files from NodeConfig."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            read_mgr = scope.get_singleton(ReadManagerImpl)
            # Requirement: WHEN agent config mcp mode is inactive, MUST install the view file tool for the agent session.
            # Requirement: MUST omit the search tool.
            # Requirement: [ReadManager] The read manager installs the view file tool and search tool.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Verify the view file tool is named view_file
            self.assertIn("view_file", tool_names)
            # Verify the search tool is omitted
            self.assertNotIn("search_files", tool_names)
            self.assertNotIn("can_read", tool_names)

            # When mcp mode is active, no inspection tools are installed
            self.agent_cfg.is_mcp_mode = True
            self.tool_mgr.installed_tools.clear()
            scope.get_singleton(ReadManagerImpl).initialize()
            tool_names_mcp = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: WHEN agent config mcp mode is active, MUST install no read tools.
            self.assertEqual(len(tool_names_mcp), 0)
            self.assertNotIn("view_file", tool_names_mcp)

            # Verify read manager exposes declared files from node config
            # Requirement: [ReadManager] The read manager exposes the session's set of read-only files.
            # Requirement: [ReadManager] The read manager exposes the session's set of read-write files.
            self.assertIn(self.ro_file, read_mgr.read_only_files)
            self.assertIn(self.ro_py_file, read_mgr.read_only_files)
            self.assertIn(self.rw_file, read_mgr.read_write_files)

    def test_view_file_tool_execution_and_formatting(self) -> None:
        """CUJ: Formatting with right-aligned line numbers and suppression keys."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)
            self.assertEqual(view_tool.name, "view_file")
            self.assertIsInstance(view_tool.description, str)
            self.assertEqual(view_tool.parameters, {view_tool.path_parameter.name: view_tool.path_parameter})
            # Verify the view file tool path parameter uses the alias manager to convert a file alias
            self.assertIs(view_tool.path_parameter.parameter_type, self.alias_mgr)

            # 1. Read-only file formatting and sanitization
            bindings1 = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.ro_file)}
            )
            # Requirement: WHEN reading an existing file, MUST format file content with one-indexed right-aligned line numbers followed by a colon and space.
            # Requirement: WHEN reading a read-only file, MUST omit suppression key and sanitize host paths.
            resp1 = view_tool.execute_tool(bindings1)
            self.assertFalse(resp1.is_failed)
            self.assertIsNone(resp1.suppression_key)
            self.assertIn(": Line 1 readonly", resp1.content)
            self.assertIn("[WORKSPACE]/readonly.txt", resp1.content)

            # 2. Read-write file formatting and suppression key
            bindings2 = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.rw_file)}
            )
            # Requirement: WHEN reading a read-write file, MUST set suppression key matching the file relative path.
            resp2 = view_tool.execute_tool(bindings2)
            self.assertFalse(resp2.is_failed)
            self.assertEqual(resp2.suppression_key, self.rw_file.relative_path)
            self.assertIn(": Line 1 writable", resp2.content)

            # 3. Read-only source code file (.py) formatting
            bindings3 = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.ro_py_file)}
            )
            resp3 = view_tool.execute_tool(bindings3)
            self.assertFalse(resp3.is_failed)
            self.assertIsNone(resp3.suppression_key)
            self.assertIn(": def foo():", resp3.content)

    def test_read_tool_unbound_files(self) -> None:
        """CUJ: Handling unbound file requests (guide vs unknown files)."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)

            # Unbound matching guide file -> fails
            bindings_guide = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.guide_unbound)}
            )
            resp_guide = view_tool.execute_tool(bindings_guide)
            self.assertTrue(resp_guide.is_failed)

            # Unbound unknown file -> fails
            unknown_unbound = UnboundFile(relative_path=RelativePath("unknown.txt"))
            bindings_unknown = ActualParameterBindings(
                bindings={(view_tool.path_parameter, unknown_unbound)}
            )
            resp_unknown = view_tool.execute_tool(bindings_unknown)
            self.assertTrue(resp_unknown.is_failed)
            self.assertTrue(resp_unknown.reminder)

            # Requirement: WHEN path matches a declared file workspace path, MUST produce a successful Response indicating access is permitted.
            # Transparent resolution: stub.py -> stub.pyi
            resp_py = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (view_tool.path_parameter, UnboundFile(relative_path=RelativePath("stub.py")))
                    }
                )
            )
            self.assertFalse(resp_py.is_failed)
            self.assertIn("class Stub:", resp_py.content)

            # Transparent resolution: module path update_with_ai.parts.pkg.stub.py -> stub.pyi
            resp_pkg = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (
                            view_tool.path_parameter,
                            UnboundFile(relative_path=RelativePath("update_with_ai.parts.pkg.stub.py")),
                        )
                    }
                )
            )
            self.assertFalse(resp_pkg.is_failed)
            self.assertIn("class Stub:", resp_pkg.content)

            # Transparent resolution: bare name stub -> stub.pyi
            resp_bare = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (view_tool.path_parameter, UnboundFile(relative_path=RelativePath("stub")))
                    }
                )
            )
            self.assertFalse(resp_bare.is_failed)
            self.assertIn("class Stub:", resp_bare.content)

            # Transparent resolution: module path with bare name pkg.stub -> stub.pyi
            resp_mod_bare = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (view_tool.path_parameter, UnboundFile(relative_path=RelativePath("pkg.stub")))
                    }
                )
            )
            self.assertFalse(resp_mod_bare.is_failed)
            self.assertIn("class Stub:", resp_mod_bare.content)

            # Requirement: WHEN path does not match any declared file workspace path, MUST produce a Response with failed set to True reminding the agent that only declared files can be read and listing readable file aliases.
            # Test files are rejected with dedicated guidance
            resp_test = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (
                            view_tool.path_parameter,
                            UnboundFile(relative_path=RelativePath("my_target_test.py")),
                        )
                    }
                )
            )
            self.assertTrue(resp_test.is_failed)
            self.assertTrue(resp_test.content)

    def test_read_tool_missing_file_handling(self) -> None:
        """CUJ: Handling missing read-write files (treated as empty) vs missing read-only files (fails)."""
        node = DagNode(unit_address=UnitAddress("//pkg:test"), role_address=RoleAddress(""))
        missing_rw_file = ReadWriteFile(
            relative_path=RelativePath("missing_rw.txt"),
            workspace_path=_make_workspace_path("missing_rw.txt"),
            owning_node=node,
        )
        missing_ro_file = ReadOnlyFile(
            relative_path=RelativePath("missing_ro.txt"),
            workspace_path=_make_workspace_path("missing_ro.txt"),
            owning_node=node,
        )

        with enter_phase(agent_session, registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)

            # Requirement: WHEN reading a read-write file that does not exist on disk, MUST treat file content as empty.
            rw_bindings = ActualParameterBindings(
                bindings={(view_tool.path_parameter, missing_rw_file)}
            )
            rw_resp = view_tool.execute_tool(rw_bindings)
            self.assertFalse(rw_resp.is_failed)
            self.assertEqual(rw_resp.content, "")
            self.assertEqual(rw_resp.suppression_key, missing_rw_file.relative_path)

            # Reading missing read-only file fails with guidance
            # Requirement: WHEN reading a missing read-only file, MUST produce a Response with failed set to True guiding agent recovery.
            ro_bindings = ActualParameterBindings(
                bindings={(view_tool.path_parameter, missing_ro_file)}
            )
            ro_resp = view_tool.execute_tool(ro_bindings)
            self.assertTrue(ro_resp.is_failed)
            self.assertTrue(ro_resp.reminder)

    def test_read_tool_filters_meta_notes_in_markdown(self) -> None:
        """CUJ: Filtering > META: paragraphs when reading markdown files."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)
            b = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.ro_md_file)}
            )
            # Requirement: WHEN reading a markdown file ending with .md, MUST filter out paragraphs beginning with '> META:'.
            # Requirement: WHEN reading a read-only markdown file ending with .md, MUST format content with session template parameters.
            resp = view_tool.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertNotIn("Meta note", resp.content)
            self.assertNotIn("> META:", resp.content)
            self.assertIn(": # Title MyDoc", resp.content)
            self.assertIn("First section content.", resp.content)
            self.assertIn("> NOTE: Non-meta quote.", resp.content)
            self.assertIn("Second section content.", resp.content)

    def test_search_tool_reporting_and_invalid_pattern(self) -> None:
        """CUJ: Searching regex across files and handling invalid regex."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            search_tool = scope.get_singleton(SearchTool)
            # Verify the search tool is named search_files
            self.assertEqual(search_tool.name, "search_files")
            self.assertIsInstance(search_tool.description, str)
            self.assertGreater(len(search_tool.parameters), 0)
            conv = search_tool.regex_pattern_parameter.parameter_type
            # Requirement: [SearchTool] The search tool accepts a regex pattern parameter.
            # Verify the search tool regex pattern parameter uses the regex pattern parameter type
            self.assertIsNotNone(conv.actual_type)
            self.assertIsNotNone(conv.wire_type)

            # Valid search matching both files
            bindings = ActualParameterBindings(
                bindings={(search_tool.regex_pattern_parameter, "Line")}
            )
            # Verify search tool searches pattern matches across read-only and read-write files
            # Requirement: [SearchTool] Executing the search tool searches pattern matches across the session's read-only and read-write files.
            resp = search_tool.execute_tool(bindings)
            self.assertFalse(resp.is_failed)
            # Read-only shows line content
            # Requirement: WHEN matches are found for read-only files, MUST return matched line contents and line numbers sanitized to mask host paths.
            self.assertIn("readonly.txt:1: Line 1 readonly", resp.content)
            # Read-write masks details to prevent unanchored edits
            # Requirement: WHEN matches are found for read-write files, MUST state that matches were found but cannot be displayed to prevent unanchored edits.
            self.assertIn(self.rw_file.relative_path, resp.content)
            self.assertTrue(
                "unanchored" in resp.content.lower() or "matches" in resp.content.lower()
            )

            # Invalid regex pattern fails
            bindings_invalid = ActualParameterBindings(
                bindings={(search_tool.regex_pattern_parameter, "[unclosed")}
            )
            # Requirement: WHEN regex pattern is invalid, MUST return a Response with failed set to True.
            resp_inv = search_tool.execute_tool(bindings_invalid)
            self.assertTrue(resp_inv.is_failed)

    def test_view_file_records_read_in_edit_manager(self) -> None:
        """CUJ: ViewFileTool records read file in EditManager upon successful execution."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)
            b = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.rw_file)}
            )
            # Requirement: WHEN reading a file succeeds, MUST record the read file to establish the session's last read or written file.
            resp = view_tool.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertEqual(self.edit_mgr.last_read_or_edited_file, self.rw_file)

    def test_can_read_operation(self) -> None:
        """CUJ: ReadManager validates workspace file inspection access and alias resolution via can_read."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            read_mgr = scope.get_singleton(ReadManager)
            # Requirement: [ReadManager] The read manager provides a can read operation validating inspection access for a file path.
            # Assert on ReadManager.guide_file property accessor
            self.assertEqual(cast(Any, read_mgr).guide_file, self.guide_unbound)

            # 1. Successful bound file validation records file read
            # Requirement: WHEN path matches a declared file workspace path, MUST produce a successful Response indicating access is permitted.
            resp_ro = read_mgr.can_read(self.ro_file.relative_path)
            self.assertFalse(resp_ro.is_failed)
            self.assertEqual(self.edit_mgr.last_read_or_edited_file, self.ro_file)

            # Test passing FileAlias directly
            resp_ro_direct = read_mgr.can_read(self.ro_file)
            self.assertFalse(resp_ro_direct.is_failed)

            # 2. Step-mode guide file rejection
            # Requirement: WHEN path does not match any declared file workspace path, MUST produce a Response with failed set to True reminding the agent that only declared files can be read and listing readable file aliases.
            resp_guide = read_mgr.can_read(self.guide_unbound.relative_path)
            self.assertTrue(resp_guide.is_failed)
            self.assertIn("advance", resp_guide.content)

            # 3. Transparent resolution from .py to .pyi
            # Requirement: WHEN path matches a declared file workspace path, MUST produce a successful Response indicating access is permitted.
            resp_py = read_mgr.can_read(RelativePath("stub.py"))
            self.assertFalse(resp_py.is_failed)
            self.assertEqual(self.edit_mgr.last_read_or_edited_file, self.ro_pyi_file)

            for cand in ["pkg.sub.stub.py", "pkg.stub", "pkg/stub.py"]:
                resp_cand = read_mgr.can_read(RelativePath(cand))
                self.assertFalse(resp_cand.is_failed)
                self.assertEqual(self.edit_mgr.last_read_or_edited_file, self.ro_pyi_file)

            # 4. Cleanroom blindness: _test.py rejection
            # Requirement: WHEN path does not match any declared file workspace path, MUST produce a Response with failed set to True reminding the agent that only declared files can be read and listing readable file aliases.
            resp_test = read_mgr.can_read(RelativePath("my_target_test.py"))
            self.assertTrue(resp_test.is_failed)
            self.assertTrue(resp_test.content)

            # 5. Undeclared file rejection
            # Requirement: WHEN path does not match any declared file workspace path, MUST produce a Response with failed set to True reminding the agent that only declared files can be read and listing readable file aliases.
            resp_unknown = read_mgr.can_read(RelativePath("unknown.txt"))
            self.assertTrue(resp_unknown.is_failed)
            self.assertIn(self.ro_file.relative_path, resp_unknown.content)
            self.assertTrue(resp_unknown.reminder)

    def test_regex_pattern_parameter_type_conversion(self) -> None:
        """CUJ: RegexPatternParameterType converts between string wire representations and regex patterns."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            converter = scope.get_singleton(RegexPatternParameterTypeImpl)
            # Verify regex pattern parameter type conversion
            self.assertEqual(converter.actual_type, RegexPattern)
            self.assertEqual(converter.wire_type, str)
            pattern = converter.convert("matched_.*")
            self.assertEqual(pattern, "matched_.*")

            # Requirement: WHEN wire_value is not a valid regular expression pattern, MUST raise tool_provider.ParameterConversionError with message formatted as "Invalid regex pattern '{wire_value}': {error}".
            with self.assertRaises(ParameterConversionError) as ctx:
                converter.convert("[unclosed")
            self.assertIn("Invalid regex pattern '[unclosed':", str(ctx.exception.message))

    def test_read_manager_initialization_tool_installation(self) -> None:
        """CUJ: Verify ReadManager installs ViewFileTool when mcp mode is inactive and no inspection tools when active."""
        reg_mcp = LifecycleRegistry()
        __initialize__(reg_mcp)
        reg_mcp.register_instance(MockAgentConfig(is_mcp_mode=True), keys=[AgentConfig], tier=system)
        tm_mcp = MockToolManager()
        reg_mcp.register_instance(tm_mcp, keys=[ToolManager], tier=agent_session)
        reg_mcp.register_instance(self.alias_mgr, keys=[AliasManager], tier=agent_session)
        reg_mcp.register_instance(self.node_cfg, keys=[NodeConfig], tier=agent_session)
        reg_mcp.register_instance(self.edit_mgr, keys=[EditManager], tier=agent_session)
        reg_mcp.register_instance(self.template_formatter, keys=[TemplateFormatter], tier=agent_session)
        reg_mcp.register_instance(self.bool_conv, keys=[IdentityParameterType], tier=agent_session)

        with enter_phase(agent_session, registry=reg_mcp) as scope:
            # Requirement: WHEN agent config mcp mode is active, MUST install no read tools.
            # Requirement: MUST omit the search tool.
            self.assertEqual(len(tm_mcp.installed_tools), 0)

        with enter_phase(agent_session, registry=self.registry) as scope:
            # Requirement: WHEN agent config mcp mode is inactive, MUST install the view file tool for the agent session.
            # Requirement: MUST omit the search tool.
            installed = self.tool_mgr.installed_tools
            self.assertEqual(len(installed), 1)
            installed_tool = next(iter(installed))
            self.assertIsInstance(installed_tool, ViewFileToolImpl)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
# - [Tool] When a parameter is required, an argument must be supplied for tool execution.
