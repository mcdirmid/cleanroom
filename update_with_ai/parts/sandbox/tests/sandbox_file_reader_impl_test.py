"""Unit tests for sandbox_file_reader_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
import unittest
from typing import Any, Mapping, Optional, Set, Tuple

from update_with_ai.parts.dag.lib.dag_storage import Node
from update_with_ai.parts.agent.lib.agent_file_alias import (
    AliasManager,
    BoundFile,
    DirectoryPath,
    FileAlias,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    RegexPattern,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib.agent_node_config import Guide, NodeConfig
from update_with_ai.parts.sandbox.lib.template_format import TemplateFormatter
from update_with_ai.parts.sandbox.lib.sandbox_file_reader import (
    ReadManager,
    ViewFileTool,
    SearchTool,
)
from update_with_ai.parts.sandbox.lib.sandbox_file_reader_impl import (
    ReadManager as ReadManagerImpl,
    ViewFileTool as ViewFileToolImpl,
    RegexPatternConverter as RegexPatternConverterImpl,
    SearchTool as SearchToolImpl,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ActualParameterBindings,
    BooleanParameterConverter,
    Parameter,
    ParameterConverter,
    Response,
    String,
    Tool,
    ToolManager,
    WireParameterBindings,
    WireType,
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


class MockBooleanConverter:
    tier = "agent_session"
    actual_type = bool
    wire_type = None

    def convert(self, wire_value: Any) -> bool:
        return bool(wire_value)


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

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = _make_directory_path(workspace_root)
        self.actual_type = FileAlias
        self.wire_type = String()

    def convert(self, wire_value: Any) -> Any:
        return wire_value

    def sanitize_text(self, text: str) -> str:
        return text.replace(self.workspace_root.path, "[WORKSPACE]")


class MockTemplateFormatter:
    tier = "agent_session"

    def format_template(self, content: str, parameters: Mapping[str, Any]) -> str:
        res = content
        for k, v in parameters.items():
            res = res.replace(f"<{k}>", str(v))
        return res


class MockNodeConfig:
    tier = "agent_session"

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
    def templates(self) -> Set[Tuple[BoundFile, FileContent]]:
        return set()

    @property
    def guide(self) -> Optional[Guide]:
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

        node = Node(unit_address="//pkg:test")
        self.ro_file = ReadOnlyFile(
            short_name="readonly.txt",
            workspace_path=_make_workspace_path("readonly.txt"),
            owning_node=node,
        )
        self.ro_py_file = ReadOnlyFile(
            short_name="readonly.py",
            workspace_path=_make_workspace_path("readonly.py"),
            owning_node=node,
        )
        self.ro_pyi_file = ReadOnlyFile(
            short_name="stub.pyi",
            workspace_path=_make_workspace_path("stub.pyi"),
            owning_node=node,
        )
        self.ro_md_file = ReadOnlyFile(
            short_name="spec.md",
            workspace_path=_make_workspace_path("spec.md"),
            owning_node=node,
        )
        self.rw_file = ReadWriteFile(
            short_name="writable.txt",
            workspace_path=_make_workspace_path("writable.txt"),
            owning_node=node,
        )
        self.guide_unbound = UnboundFile(short_name="guide.md")

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.tool_mgr = MockToolManager()
        self.bool_conv = MockBooleanConverter()
        self.alias_mgr = MockAliasManager(self.test_dir)
        self.template_formatter = MockTemplateFormatter()
        self.node_cfg = MockNodeConfig(
            ro_files={self.ro_file, self.ro_py_file, self.ro_pyi_file, self.ro_md_file},
            rw_files={self.rw_file},
            guide_file=self.guide_unbound,
            template_parameters={"doc_name": "MyDoc"},
        )

        self.registry.register_instance(
            self.tool_mgr, keys=[ToolManager], tier="agent_session"
        )
        self.registry.register_instance(
            self.bool_conv, keys=[BooleanParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(
            self.alias_mgr, keys=[AliasManager], tier="agent_session"
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier="agent_session"
        )
        self.registry.register_instance(
            self.template_formatter, keys=[TemplateFormatter], tier="agent_session"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_regex_pattern_converter(self) -> None:
        """CUJ: Converting wire string into RegexPattern."""
        conv = RegexPatternConverterImpl()
        # Requirement: The regex pattern converter converts a wire type string into a regex pattern.
        pattern = conv.convert(r"foo\d+")
        self.assertEqual(pattern, r"foo\d+")

    def test_read_manager_initialization_and_properties(self) -> None:
        """CUJ: ReadManager installs tools and exposes declared files from NodeConfig."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            read_mgr = scope.get_singleton(ReadManager)
            # Requirement: The read manager unconditionally installs the view file tool into the tool manager and never installs the search tool.
            # Requirement: [ReadManager] The read manager installs the view file tool and search tool.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The view file tool is named `view_file`.
            self.assertIn("view_file", tool_names)
            # Requirement: The search tool is named `search_files`.
            self.assertNotIn("search_files", tool_names)

            # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
            # Requirement: [ReadManager] The read manager exposes the session's set of read-only files.
            # Requirement: [ReadManager] The read manager exposes the session's set of read-write files.
            # Requirement: [ReadManager] When step-mode is active, the read manager is configured with a guide file that is an unbound file.
            self.assertIn(self.ro_file, read_mgr.read_only_files)
            self.assertIn(self.ro_py_file, read_mgr.read_only_files)
            self.assertIn(self.rw_file, read_mgr.read_write_files)
            self.assertEqual(read_mgr.guide_file, self.guide_unbound)

    def test_view_file_tool_execution_and_formatting(self) -> None:
        """CUJ: Formatting with right-aligned line numbers and suppression keys."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)
            self.assertEqual(view_tool.name, "view_file")
            self.assertIsInstance(view_tool.description, str)
            self.assertEqual(view_tool.parameters, {view_tool.path_parameter})
            # Requirement: The view file tool path parameter uses the alias manager to convert a file alias.
            self.assertIs(view_tool.path_parameter.parameter_converter, self.alias_mgr)

            # 1. Read-only file formatting and sanitization
            bindings1 = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.ro_file)}
            )
            # Requirement: Executing the view file tool reads file content using the filesystem at the host path formed from the alias manager workspace root and bound file workspace path, returning content formatted with one-indexed right-aligned line numbers followed by a colon and space.
            # Requirement: View file tool responses for read-write files carry a suppression key matching the file's short name, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.
            resp1 = view_tool.execute_tool(bindings1)
            self.assertFalse(resp1.is_failed)
            self.assertIsNone(resp1.suppression_key)
            self.assertIn("  1: Line 1 readonly", resp1.content)
            self.assertIn("[WORKSPACE]/readonly.txt", resp1.content)

            # 2. Read-write file formatting and suppression key
            bindings2 = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.rw_file)}
            )
            resp2 = view_tool.execute_tool(bindings2)
            self.assertFalse(resp2.is_failed)
            self.assertEqual(resp2.suppression_key, self.rw_file.short_name)
            self.assertIn("  1: Line 1 writable", resp2.content)

            # 3. Read-only source code file (.py) formatting
            bindings3 = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.ro_py_file)}
            )
            resp3 = view_tool.execute_tool(bindings3)
            self.assertFalse(resp3.is_failed)
            self.assertIsNone(resp3.suppression_key)
            self.assertIn("  1: def foo():", resp3.content)

    def test_read_tool_unbound_files(self) -> None:
        """CUJ: Handling unbound file requests (guide vs unknown files)."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)

            # Unbound matching guide file -> fails
            bindings_guide = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.guide_unbound)}
            )
            resp_guide = view_tool.execute_tool(bindings_guide)
            self.assertTrue(resp_guide.is_failed)

            # Unbound unknown file -> fails
            unknown_unbound = UnboundFile(short_name="unknown.txt")
            bindings_unknown = ActualParameterBindings(
                bindings={(view_tool.path_parameter, unknown_unbound)}
            )
            resp_unknown = view_tool.execute_tool(bindings_unknown)
            self.assertTrue(resp_unknown.is_failed)
            self.assertEqual(
                resp_unknown.reminder, "Only declared files can be inspected."
            )

            # Transparent resolution: stub.py -> stub.pyi
            resp_py = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (view_tool.path_parameter, UnboundFile(short_name="stub.py"))
                    }
                )
            )
            self.assertFalse(resp_py.is_failed)
            self.assertIn("class Stub:", resp_py.content)

            # Transparent resolution: module path testing.parts.pkg.stub.py -> stub.pyi
            resp_pkg = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (
                            view_tool.path_parameter,
                            UnboundFile(short_name="testing.parts.pkg.stub.py"),
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
                        (view_tool.path_parameter, UnboundFile(short_name="stub"))
                    }
                )
            )
            self.assertFalse(resp_bare.is_failed)
            self.assertIn("class Stub:", resp_bare.content)

            # Test files are rejected with dedicated guidance
            resp_test = view_tool.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (
                            view_tool.path_parameter,
                            UnboundFile(short_name="my_target_test.py"),
                        )
                    }
                )
            )
            self.assertTrue(resp_test.is_failed)
            self.assertIn("Test files are not inspectable by design", resp_test.content)

    def test_read_tool_missing_file_handling(self) -> None:
        """CUJ: Handling missing read-write files (treated as empty) vs missing read-only files (fails)."""
        node = Node(unit_address="//pkg:test")
        missing_rw_file = ReadWriteFile(
            short_name="missing_rw.txt",
            workspace_path=_make_workspace_path("missing_rw.txt"),
            owning_node=node,
        )
        missing_ro_file = ReadOnlyFile(
            short_name="missing_ro.txt",
            workspace_path=_make_workspace_path("missing_ro.txt"),
            owning_node=node,
        )

        with enter_phase("agent_session", registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)

            # Requirement: When the target file does not exist on disk, view file tool execution treats a read-write file as having empty content, and fails with a response guiding agent recovery when inspecting a missing read-only file.
            rw_bindings = ActualParameterBindings(
                bindings={(view_tool.path_parameter, missing_rw_file)}
            )
            rw_resp = view_tool.execute_tool(rw_bindings)
            self.assertFalse(rw_resp.is_failed)
            self.assertEqual(rw_resp.content, "")
            self.assertEqual(rw_resp.suppression_key, missing_rw_file.short_name)

            # Reading missing read-only file fails with guidance
            ro_bindings = ActualParameterBindings(
                bindings={(view_tool.path_parameter, missing_ro_file)}
            )
            ro_resp = view_tool.execute_tool(ro_bindings)
            self.assertTrue(ro_resp.is_failed)
            self.assertIn("missing_ro.txt' does not exist on disk", ro_resp.content)
            self.assertEqual(ro_resp.reminder, "Only declared files can be inspected.")

    def test_read_tool_filters_meta_notes_in_markdown(self) -> None:
        """CUJ: Filtering > META: paragraphs when reading markdown files."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            view_tool = scope.get_singleton(ViewFileTool)
            b = ActualParameterBindings(
                bindings={(view_tool.path_parameter, self.ro_md_file)}
            )
            # Requirement: When reading markdown files ending with .md, paragraphs beginning with > META: are filtered out from the returned content.
            # Requirement: When reading read-only markdown files ending with .md, content is formatted using the template formatter with session template parameters after filtering out paragraphs beginning with > META:.
            resp = view_tool.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertNotIn("Meta note", resp.content)
            self.assertNotIn("> META:", resp.content)
            self.assertIn("  1: # Title MyDoc", resp.content)
            self.assertIn("First section content.", resp.content)
            self.assertIn("> NOTE: Non-meta quote.", resp.content)
            self.assertIn("Second section content.", resp.content)

    def test_search_tool_reporting_and_invalid_pattern(self) -> None:
        """CUJ: Searching regex across files and handling invalid regex."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            search_tool = scope.get_singleton(SearchTool)
            # Requirement: The search tool is named `search_files`.
            self.assertEqual(search_tool.name, "search_files")
            self.assertIsInstance(search_tool.description, str)
            self.assertGreater(len(search_tool.parameters), 0)
            conv = search_tool.regex_pattern_parameter.parameter_converter
            # Requirement: [SearchTool] The search tool accepts a regex pattern parameter.
            # Requirement: The search tool regex pattern parameter uses the regex pattern converter.
            self.assertIsNotNone(conv.actual_type)
            self.assertIsNotNone(conv.wire_type)

            # Valid search matching both files
            bindings = ActualParameterBindings(
                bindings={(search_tool.regex_pattern_parameter, "Line")}
            )
            # Requirement: The search tool searches for regex pattern matches across read-only files and read-write files using the filesystem.
            # Requirement: [SearchTool] Executing the search tool searches pattern matches across the session's read-only and read-write files.
            resp = search_tool.execute_tool(bindings)
            self.assertFalse(resp.is_failed)
            # Read-only shows line content
            # Requirement: On successful search tool execution, matches in read-only files provide matched line contents and line numbers sanitized by the alias manager to mask host paths.
            self.assertIn("readonly.txt:1: Line 1 readonly", resp.content)
            # Read-write masks details to prevent unanchored edits
            # Requirement: On successful search tool execution, matches in read-write files state that matches were found but cannot be displayed to prevent unanchored edits.
            self.assertIn("writable.txt: matches found", resp.content)

            # Invalid regex pattern fails
            bindings_invalid = ActualParameterBindings(
                bindings={(search_tool.regex_pattern_parameter, "[unclosed")}
            )
            # Requirement: Executing the search tool fails when provided with an invalid regex pattern.
            resp_inv = search_tool.execute_tool(bindings_invalid)
            self.assertTrue(resp_inv.is_failed)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
# - [Tool] When a parameter is required, an argument must be supplied for tool execution.
# - Executing the view file tool with an unbound file fails with a response guiding agent recovery that lists available readable file aliases, and reminds the agent that only declared files can be inspected.
# - When an unbound file equals the guide file configured for step-mode, the view file tool failure response indicates that `advance` must be called to read the guide instead.
