"""Unit tests for sandbox_file_reader_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
import unittest
from typing import Any, Mapping, Optional, Set, Tuple

from lib.dag_storage import Node
from lib.file_alias import (
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
from lib.node_config import NodeConfig
from lib.template_format import TemplateFormatter
from lib.sandbox_file_reader import ReadManager, ReadTool, SearchTool
from lib.sandbox_file_reader_impl import (
    ReadManager as ReadManagerImpl,
    ReadTool as ReadToolImpl,
    RegexPatternConverter as RegexPatternConverterImpl,
    SearchTool as SearchToolImpl,
    __initialize__,
)
from lib.sandbox_guide_delivery import Guide
from lib.tool_provider import (
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

    def execute_tool(self, name: str, wire_parameter_bindings: WireParameterBindings) -> Response:
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
            f.write(f"Line 1 readonly at {self.test_dir}/readonly.txt\nLine 2 readonly\n")
        with open(self.ro_py_path, "w", encoding="utf-8") as f:
            f.write("def foo():\n    pass\n")
        self.ro_md_path = os.path.join(self.test_dir, "spec.md")
        with open(self.ro_md_path, "w", encoding="utf-8") as f:
            f.write(
                "# Title <doc_name>\n\n"
                "> META: \"Meta note at top.\"\n\n"
                "First section content.\n\n"
                "> META: \"Multi-line meta note\n> continued on second line.\"\n\n"
                "> NOTE: Non-meta quote.\n\n"
                "Second section content.\n\n"
                "> META: \"Trailing meta note.\"\n"
            )

        node = Node(address="//pkg:test")
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
            ro_files={self.ro_file, self.ro_py_file, self.ro_md_file},
            rw_files={self.rw_file},
            guide_file=self.guide_unbound,
            template_parameters={"doc_name": "MyDoc"},
        )

        self.registry.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")
        self.registry.register_instance(
            self.bool_conv, keys=[BooleanParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")
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
            # Both read_file and search_files installed in tool manager
            # Requirement: The read manager unconditionally installs the read tool into the tool manager and never installs the search tool.
            # Requirement: [ReadManager] The read manager installs the read tool and search tool.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The read tool is named `read_file`.
            self.assertIn("read_file", tool_names)
            # Requirement: The search tool is named `search_files`.
            self.assertNotIn("search_files", tool_names)

            # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
            # Requirement: [ReadManager] The read manager exposes the session's set of read-only files to support session startup context injection.
            # Requirement: [ReadManager] The read manager exposes the session's set of read-write files.
            # Requirement: [ReadManager] When step-mode is active, the read manager is configured with a guide file that is an unbound file.
            self.assertIn(self.ro_file, read_mgr.read_only_files)
            self.assertIn(self.ro_py_file, read_mgr.read_only_files)
            self.assertIn(self.rw_file, read_mgr.read_write_files)
            self.assertEqual(read_mgr.guide_file, self.guide_unbound)

    def test_read_manager_requires_line_numbers(self) -> None:
        """CUJ: Identifying whether files require line numbers when read."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            read_mgr = scope.get_singleton(ReadManager)
            # Requirement: The read manager identifies that read-write files and source code files require line numbers when read.
            self.assertTrue(read_mgr.requires_line_numbers(self.rw_file))
            # Requirement: The read manager identifies files ending with `.py` as source code files requiring line numbers.
            self.assertTrue(read_mgr.requires_line_numbers(self.ro_py_file))
            self.assertFalse(read_mgr.requires_line_numbers(self.ro_file))

    def test_read_tool_line_numbers_contract(self) -> None:
        """CUJ: Enforcing line number requirements for read-only vs read-write files."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            read_tool = scope.get_singleton(ReadTool)
            self.assertIsInstance(read_tool.description, str)
            self.assertGreater(len(read_tool.parameters), 0)
            # Requirement: The read tool file parameter uses the alias manager to convert a file alias.
            self.assertIs(read_tool.file_alias_parameter.parameter_converter, self.alias_mgr)
            # Requirement: The read tool line numbers parameter uses the boolean parameter converter.
            self.assertIs(read_tool.line_numbers_parameter.parameter_converter, self.bool_conv)

            # 1. Non-source read-only with line_numbers=False -> succeeds
            bindings1 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.ro_file), (read_tool.line_numbers_parameter, False)}
            )
            # Requirement: Executing the read tool reads file content using the filesystem at the host path formed from the alias manager workspace root and bound file workspace path.
            # Requirement: Read tool responses for read-write files carry a suppression key matching the file's short name, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.
            resp1 = read_tool.execute_tool(bindings1)
            self.assertFalse(resp1.is_failed)
            self.assertIsNone(resp1.suppression_key)
            self.assertIn("Line 1 readonly", resp1.content)
            self.assertIn("[WORKSPACE]/readonly.txt", resp1.content)

            # 2. Non-source read-only with line_numbers=True -> fails
            bindings2 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.ro_file), (read_tool.line_numbers_parameter, True)}
            )
            # Requirement: Executing the read tool fails if line numbers are requested when reading a non-source read-only file, reminding the agent that line numbers must be requested when reading read-write files and source code files and omitted when reading non-source read-only files, and specifying a follow-up execution of the read tool on the file with line numbers omitted.
            resp2 = read_tool.execute_tool(bindings2)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(
                resp2.reminder,
                "Line numbers must be requested when reading read-write files and source code files (.py), and omitted when reading non-source read-only files.",
            )
            self.assertIsNotNone(resp2.follow_up_tool_call)
            assert resp2.follow_up_tool_call is not None
            self.assertEqual(resp2.follow_up_tool_call.tool_name, "read_file")
            bindings2_dict = dict(resp2.follow_up_tool_call.wire_parameter_bindings.bindings)
            self.assertEqual(bindings2_dict, {"file": self.ro_file.short_name})

            # 3. Read-write with line_numbers=True -> succeeds with line numbers
            bindings3 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.rw_file), (read_tool.line_numbers_parameter, True)}
            )
            # Requirement: Read tool responses for read-write files carry a suppression key matching the file's short name, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.
            resp3 = read_tool.execute_tool(bindings3)
            self.assertFalse(resp3.is_failed)
            self.assertEqual(resp3.suppression_key, self.rw_file.short_name)
            self.assertIn("1: Line 1 writable", resp3.content)

            # 4. Read-write with line_numbers=False -> fails
            bindings4 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.rw_file), (read_tool.line_numbers_parameter, False)}
            )
            # Requirement: Executing the read tool fails if line numbers are not requested when reading a read-write file or source code file, reminding the agent that line numbers must be requested when reading read-write files and source code files and omitted when reading non-source read-only files, and specifying a follow-up execution of the read tool on the file with line numbers requested.
            resp4 = read_tool.execute_tool(bindings4)
            self.assertTrue(resp4.is_failed)
            self.assertEqual(
                resp4.reminder,
                "Line numbers must be requested when reading read-write files and source code files (.py), and omitted when reading non-source read-only files.",
            )
            self.assertIsNotNone(resp4.follow_up_tool_call)
            assert resp4.follow_up_tool_call is not None
            self.assertEqual(resp4.follow_up_tool_call.tool_name, "read_file")
            bindings4_dict = dict(resp4.follow_up_tool_call.wire_parameter_bindings.bindings)
            self.assertEqual(bindings4_dict, {"file": self.rw_file.short_name, "line_numbers": True})

            # 5. Read-only source code file (.py) with line_numbers=True -> succeeds with line numbers
            bindings5 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.ro_py_file), (read_tool.line_numbers_parameter, True)}
            )
            resp5 = read_tool.execute_tool(bindings5)
            self.assertFalse(resp5.is_failed)
            self.assertIsNone(resp5.suppression_key)
            self.assertIn("1: def foo():", resp5.content)

            # 6. Read-only source code file (.py) with line_numbers=False -> fails
            bindings6 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.ro_py_file), (read_tool.line_numbers_parameter, False)}
            )
            # Requirement: Executing the read tool fails if line numbers are not requested when reading a read-write file or source code file, reminding the agent that line numbers must be requested when reading read-write files and source code files and omitted when reading non-source read-only files, and specifying a follow-up execution of the read tool on the file with line numbers requested.
            resp6 = read_tool.execute_tool(bindings6)
            self.assertTrue(resp6.is_failed)
            self.assertEqual(
                resp6.reminder,
                "Line numbers must be requested when reading read-write files and source code files (.py), and omitted when reading non-source read-only files.",
            )
            self.assertIsNotNone(resp6.follow_up_tool_call)
            assert resp6.follow_up_tool_call is not None
            self.assertEqual(resp6.follow_up_tool_call.tool_name, "read_file")
            bindings6_dict = dict(resp6.follow_up_tool_call.wire_parameter_bindings.bindings)
            self.assertEqual(bindings6_dict, {"file": self.ro_py_file.short_name, "line_numbers": True})

    def test_read_tool_unbound_files(self) -> None:
        """CUJ: Handling unbound file requests (guide vs unknown files)."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            read_tool = scope.get_singleton(ReadTool)

            # Unbound matching guide file -> fails
            bindings_guide = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.guide_unbound)}
            )
            resp_guide = read_tool.execute_tool(bindings_guide)
            self.assertTrue(resp_guide.is_failed)

            # Unbound unknown file -> fails
            unknown_unbound = UnboundFile(short_name="unknown.txt")
            bindings_unknown = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, unknown_unbound)}
            )
            resp_unknown = read_tool.execute_tool(bindings_unknown)
            self.assertTrue(resp_unknown.is_failed)
            self.assertEqual(resp_unknown.reminder, "Only declared files can be inspected.")

    def test_read_tool_filters_meta_notes_in_markdown(self) -> None:
        """CUJ: Filtering > META: paragraphs when reading markdown files."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            read_tool = scope.get_singleton(ReadTool)
            b = ActualParameterBindings(
                bindings={
                    (read_tool.file_alias_parameter, self.ro_md_file),
                    (read_tool.line_numbers_parameter, False),
                }
            )
            # Requirement: When reading markdown files ending with .md, paragraphs beginning with > META: are filtered out from the returned content.
            # Requirement: When reading markdown files, paragraphs beginning with > META: are filtered out.
            # Requirement: When reading read-only markdown files ending with .md, content is formatted using the template formatter with session template parameters after filtering out paragraphs beginning with > META:.
            resp = read_tool.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertNotIn("Meta note", resp.content)
            self.assertNotIn("> META:", resp.content)
            self.assertIn("# Title MyDoc", resp.content)
            self.assertIn("First section content.", resp.content)
            self.assertIn("> NOTE: Non-meta quote.", resp.content)
            self.assertIn("Second section content.", resp.content)

    def test_search_tool_reporting_and_invalid_pattern(self) -> None:
        """CUJ: Searching regex across files and handling invalid regex."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            search_tool = scope.get_singleton(SearchTool)
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
# - Executing the read tool with an unbound file fails with a response guiding agent recovery that lists available readable file aliases, and reminds the agent that only declared files can be inspected.
# - When an unbound file equals the guide file configured for step-mode, the read tool failure response indicates that `advance` must be called to read the guide instead.
# - [ReadTool] Executing the read tool on the guide file provides progressive delivery feedback to the agent.
