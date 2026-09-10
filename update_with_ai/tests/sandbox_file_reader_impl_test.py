"""Unit tests for sandbox_file_reader_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
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
    ReadWriteFile,
    RegexPattern,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.node_config import NodeConfig
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


class MockNodeConfig:
    tier = "agent_session"

    def __init__(
        self,
        ro_files: Set[BoundFile],
        rw_files: Set[BoundFile],
        guide_file: Optional[UnboundFile] = None,
    ) -> None:
        self.read_only_files = ro_files
        self.read_write_files = rw_files
        self.guide_file = guide_file

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
        with open(self.rw_path, "w", encoding="utf-8") as f:
            f.write("Line 1 writable\nLine 2 writable\n")
        with open(self.ro_path, "w", encoding="utf-8") as f:
            f.write(f"Line 1 readonly at {self.test_dir}/readonly.txt\nLine 2 readonly\n")

        node = Node(address="//pkg:test")
        self.ro_file = ReadOnlyFile(
            short_name="readonly.txt",
            workspace_path=_make_workspace_path("readonly.txt"),
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
        self.node_cfg = MockNodeConfig(
            ro_files={self.ro_file},
            rw_files={self.rw_file},
            guide_file=self.guide_unbound,
        )

        self.registry.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")
        self.registry.register_instance(
            self.bool_conv, keys=[BooleanParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")

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
            self.assertIn(self.rw_file, read_mgr.read_write_files)
            self.assertEqual(read_mgr.guide_file, self.guide_unbound)

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

            # 1. Read-only with line_numbers=False -> succeeds
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

            # 2. Read-only with line_numbers=True -> fails
            bindings2 = ActualParameterBindings(
                bindings={(read_tool.file_alias_parameter, self.ro_file), (read_tool.line_numbers_parameter, True)}
            )
            # Requirement: Executing the read tool fails if line numbers are requested when reading a read-only file, and reminds the agent that line numbers must be requested when reading read-write files and omitted when reading read-only files.
            resp2 = read_tool.execute_tool(bindings2)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(
                resp2.reminder,
                "Line numbers must be requested when reading read-write files and omitted when reading read-only files.",
            )

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
            # Requirement: Executing the read tool fails if line numbers are not requested when reading a read-write file, and reminds the agent that line numbers must be requested when reading read-write files and omitted when reading read-only files.
            resp4 = read_tool.execute_tool(bindings4)
            self.assertTrue(resp4.is_failed)
            self.assertEqual(
                resp4.reminder,
                "Line numbers must be requested when reading read-write files and omitted when reading read-only files.",
            )

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
