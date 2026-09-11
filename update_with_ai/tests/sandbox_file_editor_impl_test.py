"""Unit tests for sandbox_file_editor_impl aligned with grounding specifications."""

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
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lib.node_config import NodeConfig
from lib.sandbox_file_editor import (
    EditManager,
    LineUpdateTool,
    TextReplacementTool,
)
from lib.sandbox_file_editor_impl import (
    EditManager as EditManagerImpl,
    LineUpdateTool as LineUpdateToolImpl,
    TextReplacementTool as TextReplacementToolImpl,
    __initialize__,
)
from lib.sandbox_guide_delivery import Guide
from lib.tool_provider import (
    ActualParameterBindings,
    IntegerParameterConverter,
    Parameter,
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


class MockIntegerConverter:
    tier = "agent_session"
    actual_type = int
    wire_type = None

    def convert(self, wire_value: Any) -> int:
        return int(wire_value)


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
        return text


class MockNodeConfig:
    tier = "agent_session"

    def __init__(self, templates: Set[Tuple[BoundFile, FileContent]]) -> None:
        self._templates = templates

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
        return self._templates

    @property
    def guide(self) -> Optional[Guide]:
        return None

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return set()


class SandboxFileEditorImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.target_path = os.path.join(self.test_dir, "file.txt")
        with open(self.target_path, "w", encoding="utf-8") as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        node = Node(address="//pkg:edit_test")
        self.rw_file = ReadWriteFile(
            short_name="file.txt",
            workspace_path=_make_workspace_path("file.txt"),
            owning_node=node,
        )
        self.ro_file = ReadOnlyFile(
            short_name="readonly.txt",
            workspace_path=_make_workspace_path("readonly.txt"),
            owning_node=node,
        )

        self.missing_bound = ReadWriteFile(
            short_name="missing.txt",
            workspace_path=_make_workspace_path("missing.txt"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.tool_mgr = MockToolManager()
        self.str_conv = MockStringConverter()
        self.int_conv = MockIntegerConverter()
        self.alias_mgr = MockAliasManager(self.test_dir)
        self.node_cfg = MockNodeConfig(
            templates={
                (self.rw_file, "Existing overwrite attempt"),
                (self.missing_bound, "Starter template content"),
            }
        )

        self.registry.register_instance(self.tool_mgr, keys=[ToolManager], tier="agent_session")
        self.registry.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(
            self.int_conv, keys=[IntegerParameterConverter], tier="agent_session"
        )
        self.registry.register_instance(self.alias_mgr, keys=[AliasManager], tier="agent_session")
        self.registry.register_instance(self.node_cfg, keys=[NodeConfig], tier="agent_session")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_edit_manager_initialization_and_template_materialization(self) -> None:
        """CUJ: EditManager installs tools and materializes missing templates without overwriting existing files."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            # Requirement: The edit manager unconditionally installs the text replacement tool and line update tool into the tool manager.
            # Requirement: [EditManager] The edit manager installs the text replacement tool and line update tool.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The text replacement tool is named `replace`.
            self.assertIn("replace", tool_names)
            # Requirement: The line update tool is named `update_lines`.
            self.assertIn("update_lines", tool_names)

            self.assertFalse(edit_mgr.has_modifications)

            # Requirement: Materializing templates retrieves configured templates from the node config, checks whether files exist using the filesystem at the host path formed from the alias manager workspace root and workspace path, and writes template content to missing target files while preserving existing files.
            # Requirement: [EditManager] Materializing templates populates missing read-write files with initial template content without overwriting existing files.
            edit_mgr.materialize_templates()

            # Missing file materialized
            missing_host = os.path.join(self.test_dir, "missing.txt")
            self.assertTrue(os.path.isfile(missing_host))
            with open(missing_host, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Starter template content")

            # Existing file NOT overwritten
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertNotIn("Existing overwrite attempt", f.read())

    def test_text_replacement_tool_exact_match_and_failures(self) -> None:
        """CUJ: TextReplacementTool replaces unique match and fails on duplicates or non-read-write files."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            replace_tool = scope.get_singleton(TextReplacementTool)
            edit_mgr = scope.get_singleton(EditManager)
            self.assertIsInstance(replace_tool.description, str)
            self.assertGreater(len(replace_tool.parameters), 0)

            # 1. Non-read-write file fails
            b_ro = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.ro_file),
                    (replace_tool.target_text_parameter, "Line 2"),
                    (replace_tool.replacement_text_parameter, "New Line 2"),
                }
            )
            # Requirement: [EditingTool] Executing an editing tool with a file alias that is not a read-write file fails, providing a response reminding the agent that only declared read-write files can be modified.
            resp_ro = replace_tool.execute_tool(b_ro)
            self.assertTrue(resp_ro.is_failed)
            self.assertEqual(resp_ro.reminder, "Only declared read-write files can be modified.")

            # 2. Text not found fails
            b_not_found = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "Not present"),
                    (replace_tool.replacement_text_parameter, "New"),
                }
            )
            # Requirement: Executing the text replacement tool fails if the target text is not found in the file content.
            self.assertTrue(replace_tool.execute_tool(b_not_found).is_failed)

            # 3. Successful replacement
            b_ok = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "Line 2"),
                    (replace_tool.replacement_text_parameter, "Updated Line 2"),
                }
            )
            # Requirement: Executing the text replacement tool reads file content using the filesystem.
            # Requirement: On successful text replacement tool execution, the unique occurrence of the target text is replaced with the replacement text, written using the filesystem, and file modifications are recorded.
            # Requirement: Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.
            # Requirement: [EditManager] Modifying a file records that workspace file modifications occurred during the session.
            # Requirement: On successful execution, an editing tool produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.
            resp = replace_tool.execute_tool(b_ok)
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.suppression_key, self.rw_file.short_name)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "read_file")
            bindings_dict = dict(resp.follow_up_tool_call.wire_parameter_bindings.bindings)
            self.assertEqual(bindings_dict.get("file"), self.rw_file.short_name)
            self.assertTrue(bindings_dict.get("line_numbers"))
            self.assertIsNotNone(resp.reminder)
            self.assertTrue(edit_mgr.has_modifications)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Line 1\nUpdated Line 2\nLine 3\n")

            # 4. Multiple matches fail
            with open(self.target_path, "w", encoding="utf-8") as f:
                f.write("duplicate\nduplicate\n")
            b_dup = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "duplicate"),
                    (replace_tool.replacement_text_parameter, "single"),
                }
            )
            # Requirement: Executing the text replacement tool fails if the target text matches multiple locations in the file.
            self.assertTrue(replace_tool.execute_tool(b_dup).is_failed)

            # 5. Target text exceeding 100k fails
            b_huge = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "x" * 100001),
                    (replace_tool.replacement_text_parameter, "New"),
                }
            )
            # Requirement: Executing the text replacement tool fails if the target text exceeds 100,000 characters, and reminds the agent that target text for replacement must not exceed 100,000 characters.
            resp_huge = replace_tool.execute_tool(b_huge)
            self.assertTrue(resp_huge.is_failed)
            self.assertEqual(resp_huge.reminder, "Target text for replacement must not exceed 100,000 characters.")

    def test_line_update_tool_bounds_and_insertion(self) -> None:
        """CUJ: LineUpdateTool updates line ranges and performs insertion when start > end."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            line_tool = scope.get_singleton(LineUpdateTool)
            edit_mgr = scope.get_singleton(EditManager)
            self.assertIsInstance(line_tool.description, str)
            self.assertGreater(len(line_tool.parameters), 0)

            # Non-read-write file fails
            b_ro = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.ro_file),
                    (line_tool.start_line_parameter, 1),
                    (line_tool.end_line_parameter, 1),
                    (line_tool.replacement_text_parameter, "New\n"),
                }
            )
            # Requirement: [EditingTool] Executing an editing tool with a file alias that is not a read-write file fails, providing a response reminding the agent that only declared read-write files can be modified.
            resp_line_ro = line_tool.execute_tool(b_ro)
            self.assertTrue(resp_line_ro.is_failed)
            self.assertEqual(resp_line_ro.reminder, "Only declared read-write files can be modified.")

            # 1. Replace lines 1 and 2
            b_replace = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.rw_file),
                    (line_tool.start_line_parameter, 1),
                    (line_tool.end_line_parameter, 2),
                    (line_tool.replacement_text_parameter, "Replaced 1 and 2\n"),
                }
            )
            # Requirement: Executing the line update tool reads file content using the filesystem.
            # Requirement: When the start line is less than or equal to the end line, successful execution replaces lines within the range, writes using the filesystem, and records file modifications.
            # Requirement: Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.
            # Requirement: On successful execution, an editing tool produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.
            resp1 = line_tool.execute_tool(b_replace)
            self.assertFalse(resp1.is_failed)
            self.assertEqual(resp1.suppression_key, self.rw_file.short_name)
            self.assertIsNotNone(resp1.follow_up_tool_call)
            assert resp1.follow_up_tool_call is not None
            self.assertEqual(resp1.follow_up_tool_call.tool_name, "read_file")
            bindings_dict = dict(resp1.follow_up_tool_call.wire_parameter_bindings.bindings)
            self.assertEqual(bindings_dict.get("file"), self.rw_file.short_name)
            self.assertTrue(bindings_dict.get("line_numbers"))
            self.assertIsNotNone(resp1.reminder)
            self.assertTrue(edit_mgr.has_modifications)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Replaced 1 and 2\nLine 3\n")

            # 2. Insertion: start_line > end_line inserts before start_line
            b_insert = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.rw_file),
                    (line_tool.start_line_parameter, 2),
                    (line_tool.end_line_parameter, 1),
                    (line_tool.replacement_text_parameter, "Inserted Line\n"),
                }
            )
            # Requirement: When the start line exceeds the end line, successful execution inserts the replacement lines before the start line, writes using the filesystem, and records file modifications.
            # Requirement: Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.
            resp2 = line_tool.execute_tool(b_insert)
            self.assertFalse(resp2.is_failed)
            self.assertEqual(resp2.suppression_key, self.rw_file.short_name)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Replaced 1 and 2\nInserted Line\nLine 3\n")

            # 3. Out-of-bounds start line fails
            b_oob_start = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.rw_file),
                    (line_tool.start_line_parameter, 100),
                    (line_tool.end_line_parameter, 100),
                    (line_tool.replacement_text_parameter, "Bad\n"),
                }
            )
            # Requirement: Executing the line update tool fails if the start line is less than one or exceeds the total line count plus one.
            self.assertTrue(line_tool.execute_tool(b_oob_start).is_failed)

            # 4. Out-of-bounds end line fails
            b_oob_end = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.rw_file),
                    (line_tool.start_line_parameter, 1),
                    (line_tool.end_line_parameter, 100),
                    (line_tool.replacement_text_parameter, "Bad\n"),
                }
            )
            # Requirement: When the start line is less than or equal to the end line, executing the line update tool fails if the end line exceeds the total line count.
            self.assertTrue(line_tool.execute_tool(b_oob_end).is_failed)

            # 5. Replacement text without trailing newline
            b_no_nl = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.rw_file),
                    (line_tool.start_line_parameter, 1),
                    (line_tool.end_line_parameter, 1),
                    (line_tool.replacement_text_parameter, "No newline"),
                }
            )
            self.assertFalse(line_tool.execute_tool(b_no_nl).is_failed)

    def test_diff_based_has_modifications(self) -> None:
        """CUJ: EditManager tracks real content differences and detects reverted modifications."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            replace_tool = scope.get_singleton(TextReplacementTool)
            edit_mgr = scope.get_singleton(EditManager)

            # Initially no modifications
            self.assertFalse(edit_mgr.has_modifications)

            # 1. Modify file -> has_modifications is True
            # Requirement: The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing.
            b_mod = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "Line 2"),
                    (replace_tool.replacement_text_parameter, "Modified Line 2"),
                }
            )
            resp1 = replace_tool.execute_tool(b_mod)
            self.assertFalse(resp1.is_failed)
            self.assertTrue(edit_mgr.has_modifications)

            # 2. Revert back to original content -> has_modifications is False
            b_revert = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "Modified Line 2"),
                    (replace_tool.replacement_text_parameter, "Line 2"),
                }
            )
            resp2 = replace_tool.execute_tool(b_revert)
            self.assertFalse(resp2.is_failed)
            # Requirement: [EditManager] The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.
            self.assertFalse(edit_mgr.has_modifications)

            # 3. No-op replacement with identical text -> has_modifications remains False
            b_noop = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "Line 2"),
                    (replace_tool.replacement_text_parameter, "Line 2"),
                }
            )
            resp3 = replace_tool.execute_tool(b_noop)
            self.assertFalse(resp3.is_failed)
            self.assertFalse(edit_mgr.has_modifications)

    def test_file_update_revision(self) -> None:
        """CUJ: EditManager file_update_revision increments when editing tools modify files."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(TextReplacementTool)
            line_tool = scope.get_singleton(LineUpdateTool)

            # Requirement: The edit manager tracks a file update revision that increments whenever workspace files are updated.
            # Requirement: [EditManager] The edit manager exposes a file update revision that tracks sequential updates made to workspace files.
            self.assertEqual(edit_mgr.file_update_revision, 0)

            # Perform text replacement
            b_replace = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_text_parameter, "Line 2"),
                    (replace_tool.replacement_text_parameter, "Modified Line 2"),
                }
            )
            resp1 = replace_tool.execute_tool(b_replace)
            self.assertFalse(resp1.is_failed)
            self.assertEqual(edit_mgr.file_update_revision, 1)

            # Perform line update
            b_line = ActualParameterBindings(
                bindings={
                    (line_tool.file_alias_parameter, self.rw_file),
                    (line_tool.start_line_parameter, 1),
                    (line_tool.end_line_parameter, 1),
                    (line_tool.replacement_text_parameter, "Updated Line 1\n"),
                }
            )
            resp2 = line_tool.execute_tool(b_line)
            self.assertFalse(resp2.is_failed)
            self.assertEqual(edit_mgr.file_update_revision, 2)

    def test_tool_parameter_converters(self) -> None:
        """CUJ: Parameter converters associated with tool parameters."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            replace_tool = scope.get_singleton(TextReplacementTool)
            line_tool = scope.get_singleton(LineUpdateTool)

            # Requirement: The text replacement tool file parameter uses the alias manager to convert a file alias.
            self.assertIs(replace_tool.file_alias_parameter.parameter_converter, self.alias_mgr)
            # Requirement: The text replacement tool target text parameter uses a string parameter converter to accept text.
            self.assertIs(replace_tool.target_text_parameter.parameter_converter, self.str_conv)
            # Requirement: The text replacement tool replacement text parameter uses a string parameter converter to accept text.
            self.assertIs(replace_tool.replacement_text_parameter.parameter_converter, self.str_conv)

            # Requirement: The line update tool file parameter uses the alias manager to convert a file alias.
            self.assertIs(line_tool.file_alias_parameter.parameter_converter, self.alias_mgr)
            # Requirement: The line update tool start line parameter uses an integer parameter converter to accept an integer.
            self.assertIs(line_tool.start_line_parameter.parameter_converter, self.int_conv)
            # Requirement: The line update tool end line parameter uses an integer parameter converter to accept an integer.
            self.assertIs(line_tool.end_line_parameter.parameter_converter, self.int_conv)
            # Requirement: The line update tool replacement text parameter uses a string parameter converter to accept text.
            self.assertIs(line_tool.replacement_text_parameter.parameter_converter, self.str_conv)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
# - [Tool] When a parameter is required, an argument must be supplied for tool execution.

