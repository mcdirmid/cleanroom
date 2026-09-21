"""Unit tests for sandbox_file_editor_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from typing import Any, Mapping, Optional, Sequence, Set, Tuple

from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_file_alias import (
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
from update_with_ai.parts.agent.lib.agent_node_config import Guide, NodeConfig
from update_with_ai.parts.sandbox.lib.template_format import TemplateFormatter
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import (
    EditManager,
    ReplaceFileContentTool,
)
from update_with_ai.parts.sandbox.lib.sandbox_file_editor_impl import (
    EditManager as EditManagerImpl,
    ReplaceFileContentTool as ReplaceFileContentToolImpl,
    __initialize__,
)
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ActualParameterBindings,
    BooleanParameterConverter,
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
    tier = agent_session

    def __init__(self) -> None:
        self.installed_tools: Set[Tool] = set()

    def install_tool(self, tool: Tool) -> None:
        self.installed_tools.add(tool)

    def execute_tool(
        self, name: str, wire_parameter_bindings: WireParameterBindings
    ) -> Response:
        return Response(is_failed=False, is_terminated=False, content="")


class MockStringConverter:
    tier = agent_session
    actual_type = str
    wire_type = String()

    def convert(self, wire_value: Any) -> str:
        return str(wire_value)


class MockIntegerConverter:
    tier = agent_session
    actual_type = int
    wire_type = None

    def convert(self, wire_value: Any) -> int:
        return int(wire_value)


class MockBooleanConverter:
    tier = agent_session
    actual_type = bool
    wire_type = None

    def convert(self, wire_value: Any) -> bool:
        if isinstance(wire_value, bool):
            return wire_value
        if isinstance(wire_value, str):
            return wire_value.lower() in ("true", "1", "yes")
        return bool(wire_value)


class MockAgentConfig:
    tier = agent_session

    def __init__(
        self,
        edit_delta_output: bool = True,
        is_mcp_mode: bool = False,
    ) -> None:
        self.edit_delta_output = edit_delta_output
        self.is_mcp_mode = is_mcp_mode


def _make_directory_path(path: str) -> DirectoryPath:
    obj = object.__new__(DirectoryPath)
    object.__setattr__(obj, "path", path)
    return obj


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class MockAliasManager:
    tier = agent_session

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = _make_directory_path(workspace_root)
        self.actual_type = FileAlias
        self.wire_type = String()
        self.files: dict[str, FileAlias] = {}

    def convert(self, wire_value: Any) -> Any:
        if isinstance(wire_value, FileAlias):
            return wire_value
        if str(wire_value) in self.files:
            return self.files[str(wire_value)]
        return UnboundFile(relative_path=str(wire_value))

    def sanitize_text(self, text: str) -> str:
        return text


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
        templates: Set[Tuple[BoundFile, FileContent]],
        template_parameters: Optional[Mapping[str, Any]] = None,
        verification_checks: Optional[Sequence[Any]] = None,
    ) -> None:
        self._templates = templates
        self._template_parameters = template_parameters or {}
        self._verification_checks = verification_checks or []

    @property
    def verification_checks(self) -> Sequence[Any]:
        return self._verification_checks

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        return self._template_parameters

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

        node = MagicMock()
        self.rw_file = ReadWriteFile(
            relative_path="file.txt",
            workspace_path=_make_workspace_path("file.txt"),
            owning_node=node,
        )
        self.ro_file = ReadOnlyFile(
            relative_path="readonly.txt",
            workspace_path=_make_workspace_path("readonly.txt"),
            owning_node=node,
        )

        self.missing_bound = ReadWriteFile(
            relative_path="missing.txt",
            workspace_path=_make_workspace_path("missing.txt"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.tool_mgr = MockToolManager()
        self.str_conv = MockStringConverter()
        self.int_conv = MockIntegerConverter()
        self.bool_conv = MockBooleanConverter()
        self.agent_cfg = MockAgentConfig()
        self.alias_mgr = MockAliasManager(self.test_dir)
        self.alias_mgr.files = {
            self.rw_file.relative_path: self.rw_file,
            self.ro_file.relative_path: self.ro_file,
            self.missing_bound.relative_path: self.missing_bound,
        }
        self.template_formatter = MockTemplateFormatter()
        self.node_cfg = MockNodeConfig(
            templates={
                (self.rw_file, "Existing overwrite attempt"),
                (self.missing_bound, "Starter template <param> content"),
            },
            template_parameters={"param": "materialized"},
        )

        self.registry.register_instance(
            self.tool_mgr, keys=[ToolManager], tier=agent_session
        )
        self.registry.register_instance(
            self.agent_cfg, keys=[AgentConfig], tier=agent_session
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

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_edit_manager_initialization_and_template_materialization(self) -> None:
        """CUJ: EditManager installs tools and materializes missing templates without overwriting existing files."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            # Requirement: The edit manager installs the replace file content tool into the tool manager when mcp mode is inactive, and installs no editing tools when mcp mode is active.
            # Requirement: [EditManager] The edit manager installs the replace file content tool.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The replace file content tool is named `replace_file_content`.
            self.assertIn("replace_file_content", tool_names)
            self.assertNotIn("can_write", tool_names)

            # When mcp mode is active, no editing tools are installed
            self.agent_cfg.is_mcp_mode = True
            self.tool_mgr.installed_tools.clear()
            scope.get_singleton(EditManagerImpl).initialize()
            tool_names_mcp = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The edit manager installs the replace file content tool into the tool manager when mcp mode is inactive, and installs no editing tools when mcp mode is active.
            self.assertEqual(len(tool_names_mcp), 0)
            self.assertNotIn("replace_file_content", tool_names_mcp)

            self.assertFalse(edit_mgr.has_modifications)

            # Requirement: Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes formatted template content for missing files while preserving existing files.
            # Requirement: [EditManager] Materializing templates populates missing read-write files with initial template content without overwriting existing files.
            edit_mgr.materialize_templates()

            # Missing file materialized
            missing_host = os.path.join(self.test_dir, "missing.txt")
            self.assertTrue(os.path.isfile(missing_host))
            with open(missing_host, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Starter template materialized content")

            # Existing file NOT overwritten
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertNotIn("Existing overwrite attempt", f.read())

    def test_replace_file_content_tool_whole_file_and_failures(self) -> None:
        """CUJ: ReplaceFileContentTool replaces unique match and fails on duplicates or non-read-write files."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            edit_mgr = scope.get_singleton(EditManager)
            self.assertIsInstance(replace_tool.description, str)
            self.assertGreater(len(replace_tool.parameters), 0)

            # 1. Non-read-write file fails
            b_ro = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.ro_file),
                    (replace_tool.target_content_parameter, "Line 2"),
                    (replace_tool.replacement_content_parameter, "New Line 2"),
                }
            )
            # Requirement: Before modifying a file, editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
            resp_ro = replace_tool.execute_tool(b_ro)
            self.assertTrue(resp_ro.is_failed)
            self.assertEqual(
                resp_ro.reminder, "Only declared read-write files can be modified."
            )

            # 2. Content not found fails
            b_not_found = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Not present"),
                    (replace_tool.replacement_content_parameter, "New"),
                }
            )
            # Requirement: Tool execution fails if the target content is not found within the designated line range or matches multiple locations within the designated line range, and on success replaces the single matching occurrence, when allow multiple is not set or false.
            # Requirement: Tool execution specifies a follow-up execution of the view file tool on the target file with reasoning text indicating that the target content was not found, when target content is not found anywhere in the file.
            resp_not_found = replace_tool.execute_tool(b_not_found)
            self.assertTrue(resp_not_found.is_failed)
            self.assertIn("target_content not found in file", resp_not_found.content)
            self.assertIsNotNone(resp_not_found.follow_up_tool_call)
            assert resp_not_found.follow_up_tool_call is not None
            self.assertEqual(resp_not_found.follow_up_tool_call.tool_name, "view_file")
            self.assertEqual(
                resp_not_found.follow_up_tool_call.wire_parameter_bindings.bindings,
                {("path", self.rw_file.relative_path)},
            )
            assert resp_not_found.follow_up_tool_call.reasoning_text is not None
            self.assertIn(
                "Target content not found",
                resp_not_found.follow_up_tool_call.reasoning_text,
            )

            # 3. Successful replacement
            b_ok = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 2"),
                    (replace_tool.replacement_content_parameter, "Updated Line 2"),
                }
            )
            # Requirement: Tool execution reads the file content from the filesystem, treating missing files as empty.
            # Requirement: Tool execution writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file modifications occurred on success.
            # Requirement: [EditManager] Modifying a file records that workspace file modifications occurred during the session.
            # Requirement: On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and reminds the agent to call the check file tool to verify syntax and type correctness before making further modifications.
            # Requirement: Editing tool responses share a constant suppression key replace_file_content.
            resp = replace_tool.execute_tool(b_ok)
            self.assertFalse(resp.is_failed)
            self.assertEqual(resp.suppression_key, "replace_file_content")
            self.assertIsNone(resp.follow_up_tool_call)
            self.assertIsNotNone(resp.reminder)
            self.assertIn("check_file", resp.reminder or "")
            self.assertTrue(edit_mgr.has_modifications)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Line 1\nUpdated Line 2\nLine 3\n")

            # 4. Multiple matches fail when allow_multiple is not set or false
            with open(self.target_path, "w", encoding="utf-8") as f:
                f.write("duplicate\nduplicate\n")
            b_dup = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "duplicate"),
                    (replace_tool.replacement_content_parameter, "single"),
                }
            )
            # Requirement: Tool execution fails if the target content is not found within the designated line range or matches multiple locations within the designated line range, and on success replaces the single matching occurrence, when allow multiple is not set or false.
            # Requirement: Tool execution provides failure feedback indicating the first two matching line numbers to assist in narrowing the replacement region and instructs the agent to include more surrounding lines in target_content or specify start_line and end_line, when target content matches multiple locations in the file and allow multiple is false.
            resp_dup = replace_tool.execute_tool(b_dup)
            self.assertTrue(resp_dup.is_failed)
            self.assertIn("matches 2 locations", resp_dup.content)
            self.assertIn("Include more surrounding lines", resp_dup.content)

            # 5. Multiple matches succeed when allow_multiple is true
            b_dup_allowed = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "duplicate"),
                    (replace_tool.replacement_content_parameter, "single"),
                    (replace_tool.allow_multiple_parameter, True),
                }
            )
            # Requirement: Tool execution fails if the target content is not found within the designated line range, and replaces all occurrences of the target content within the designated line range, when allow multiple is true.
            resp_dup_allowed = replace_tool.execute_tool(b_dup_allowed)
            self.assertFalse(resp_dup_allowed.is_failed)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "single\nsingle\n")

            # 6. Replacement producing no change to file content fails
            b_no_change = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "single"),
                    (replace_tool.replacement_content_parameter, "single"),
                    (replace_tool.allow_multiple_parameter, True),
                }
            )
            # Requirement: Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.
            resp_no_change = replace_tool.execute_tool(b_no_change)
            self.assertTrue(resp_no_change.is_failed)
            self.assertEqual(
                resp_no_change.reminder,
                "The edit had no effect, and such edits will fail.",
            )
            # Requirement: Editing tool responses share a constant suppression key replace_file_content.
            self.assertEqual(resp_no_change.suppression_key, "replace_file_content")
            self.assertIsNone(resp_no_change.follow_up_tool_call)

    def test_replace_file_content_tool_line_ranges(self) -> None:
        """CUJ: ReplaceFileContentTool validates start_line/end_line bounds and constrains replacements to ranges."""
        with open(self.target_path, "w", encoding="utf-8") as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)

            # 1. start_line < 1 fails
            b_zero_start = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "New"),
                    (replace_tool.start_line_parameter, 0),
                }
            )
            # Requirement: Tool execution fails if the start line is less than one or exceeds the total line count plus one, when a start line is provided.
            resp_zero_start = replace_tool.execute_tool(b_zero_start)
            self.assertTrue(resp_zero_start.is_failed)
            self.assertIn("start_line 0 out of bounds", resp_zero_start.content)

            # 2. start_line > total line count + 1 fails
            b_oob_start = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "New"),
                    (replace_tool.start_line_parameter, 5),
                }
            )
            # Requirement: Tool execution fails if the start line is less than one or exceeds the total line count plus one, when a start line is provided.
            resp_oob_start = replace_tool.execute_tool(b_oob_start)
            self.assertTrue(resp_oob_start.is_failed)
            self.assertIn("start_line 5 out of bounds", resp_oob_start.content)

            # 3. end_line < 1 fails
            b_zero_end = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "New"),
                    (replace_tool.end_line_parameter, 0),
                }
            )
            # Requirement: Tool execution fails if the end line is less than one or exceeds the total line count, when an end line is provided.
            resp_zero_end = replace_tool.execute_tool(b_zero_end)
            self.assertTrue(resp_zero_end.is_failed)
            self.assertIn("end_line 0 out of bounds", resp_zero_end.content)

            # 4. end_line > total line count fails
            b_oob_end = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "New"),
                    (replace_tool.end_line_parameter, 4),
                }
            )
            # Requirement: Tool execution fails if the end line is less than one or exceeds the total line count, when an end line is provided.
            resp_oob_end = replace_tool.execute_tool(b_oob_end)
            self.assertTrue(resp_oob_end.is_failed)
            self.assertIn("end_line 4 out of bounds", resp_oob_end.content)

            # 5. start_line > end_line fails
            b_start_gt_end = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line"),
                    (replace_tool.replacement_content_parameter, "New"),
                    (replace_tool.start_line_parameter, 3),
                    (replace_tool.end_line_parameter, 2),
                }
            )
            # Requirement: Tool execution fails if the start line exceeds the end line, when both start line and end line are provided.
            resp_start_gt_end = replace_tool.execute_tool(b_start_gt_end)
            self.assertTrue(resp_start_gt_end.is_failed)
            self.assertIn("cannot be greater than end_line", resp_start_gt_end.content)

            # 6. Scoped replacement within range ignores occurrences outside range
            with open(self.target_path, "w", encoding="utf-8") as f:
                f.write("target\ntarget\ntarget\n")
            b_scoped = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "target"),
                    (replace_tool.replacement_content_parameter, "replaced"),
                    (replace_tool.start_line_parameter, 2),
                    (replace_tool.end_line_parameter, 2),
                }
            )
            resp_scoped = replace_tool.execute_tool(b_scoped)
            self.assertFalse(resp_scoped.is_failed)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "target\nreplaced\ntarget\n")

            # 7. Scoped replacement fails when target_content is not found in designated range
            b_scoped_missing = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "missing"),
                    (replace_tool.replacement_content_parameter, "replaced"),
                    (replace_tool.start_line_parameter, 2),
                    (replace_tool.end_line_parameter, 2),
                }
            )
            resp_scoped_missing = replace_tool.execute_tool(b_scoped_missing)
            self.assertTrue(resp_scoped_missing.is_failed)
            self.assertIn(
                "target_content not found in specified line range",
                resp_scoped_missing.content,
            )

            # 7b. Scoped target found elsewhere in file reports its actual line number
            with open(self.target_path, "w", encoding="utf-8") as f:
                f.write("line 1\nline 2\ntarget line\nline 4\n")
            b_scoped_locator = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "target line"),
                    (replace_tool.replacement_content_parameter, "replaced"),
                    (replace_tool.start_line_parameter, 1),
                    (replace_tool.end_line_parameter, 2),
                }
            )
            # Requirement: Tool execution provides failure feedback indicating the line numbers where the target content was located, when target content is not found within the designated line range but exists elsewhere in the file.
            resp_scoped_locator = replace_tool.execute_tool(b_scoped_locator)
            self.assertTrue(resp_scoped_locator.is_failed)
            self.assertIn(
                "target_content exists at line 3", resp_scoped_locator.content
            )

            # 8. Scoped multiple matches within range fails when allow_multiple is false
            with open(self.target_path, "w", encoding="utf-8") as f:
                f.write("alpha alpha\nbeta\n")
            b_scoped_dup = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "alpha"),
                    (replace_tool.replacement_content_parameter, "gamma"),
                    (replace_tool.start_line_parameter, 1),
                    (replace_tool.end_line_parameter, 1),
                }
            )
            resp_scoped_dup = replace_tool.execute_tool(b_scoped_dup)
            self.assertTrue(resp_scoped_dup.is_failed)
            self.assertIn("matches 2 locations in line range", resp_scoped_dup.content)

            # 9. Scoped multiple matches within range succeeds when allow_multiple is true
            b_scoped_dup_allowed = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "alpha"),
                    (replace_tool.replacement_content_parameter, "gamma"),
                    (replace_tool.start_line_parameter, 1),
                    (replace_tool.end_line_parameter, 1),
                    (replace_tool.allow_multiple_parameter, True),
                }
            )
            resp_scoped_dup_allowed = replace_tool.execute_tool(b_scoped_dup_allowed)
            self.assertFalse(resp_scoped_dup_allowed.is_failed)
            with open(self.target_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "gamma gamma\nbeta\n")

    def test_replace_file_content_tool_diff_and_followup_configs(self) -> None:
        """CUJ: ReplaceFileContentTool produces unified diff and respects delta output configuration."""
        with open(self.target_path, "w", encoding="utf-8") as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)

            # 1. Delta output enabled produces diff delta in response content
            self.agent_cfg.edit_delta_output = True

            b_diff = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "Header"),
                }
            )
            # Requirement: When configured to produce delta output, successful editing tool execution includes a diff delta representation in the response content.
            # Requirement: Editing tool responses share a constant suppression key replace_file_content.
            resp_diff = replace_tool.execute_tool(b_diff)
            self.assertFalse(resp_diff.is_failed)
            self.assertIn("```diff", resp_diff.content)
            self.assertIn("-Line 1", resp_diff.content)
            self.assertIn("+Header", resp_diff.content)
            self.assertIsNone(resp_diff.follow_up_tool_call)
            self.assertIsNotNone(resp_diff.reminder)
            self.assertIn("check_file", resp_diff.reminder or "")
            self.assertEqual(resp_diff.suppression_key, "replace_file_content")

            # 2. Delta output disabled omits diff delta
            self.agent_cfg.edit_delta_output = False

            b_no_followup = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Header"),
                    (replace_tool.replacement_content_parameter, "Line 1"),
                }
            )
            resp_no_followup = replace_tool.execute_tool(b_no_followup)
            self.assertFalse(resp_no_followup.is_failed)
            self.assertNotIn("```diff", resp_no_followup.content)
            self.assertEqual(resp_no_followup.content, "Successfully replaced content.")
            self.assertIsNone(resp_no_followup.follow_up_tool_call)
            self.assertIsNotNone(resp_no_followup.reminder)
            self.assertIn("check_file", resp_no_followup.reminder or "")
            self.assertEqual(resp_no_followup.suppression_key, "replace_file_content")

            # Reset config
            self.agent_cfg.edit_delta_output = True

    def test_diff_based_has_modifications(self) -> None:
        """CUJ: EditManager tracks real content differences and detects reverted modifications."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            edit_mgr = scope.get_singleton(EditManager)

            # Initially no modifications
            self.assertFalse(edit_mgr.has_modifications)

            # 1. Modify file -> has_modifications is True
            # Requirement: The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing.
            b_mod = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 2"),
                    (replace_tool.replacement_content_parameter, "Modified Line 2"),
                }
            )
            resp1 = replace_tool.execute_tool(b_mod)
            self.assertFalse(resp1.is_failed)
            self.assertTrue(edit_mgr.has_modifications)

            # 2. Revert back to original content -> has_modifications is False
            b_revert = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Modified Line 2"),
                    (replace_tool.replacement_content_parameter, "Line 2"),
                }
            )
            resp2 = replace_tool.execute_tool(b_revert)
            self.assertFalse(resp2.is_failed)
            # Requirement: [EditManager] The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.
            self.assertFalse(edit_mgr.has_modifications)

            # 3. No-op replacement with identical text -> fails and has_modifications remains False
            b_noop = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 2"),
                    (replace_tool.replacement_content_parameter, "Line 2"),
                }
            )
            # Requirement: Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.
            resp3 = replace_tool.execute_tool(b_noop)
            self.assertTrue(resp3.is_failed)
            self.assertEqual(
                resp3.reminder, "The edit had no effect, and such edits will fail."
            )
            self.assertFalse(edit_mgr.has_modifications)

    def test_editing_tools_missing_file_handling(self) -> None:
        """CUJ: ReplaceFileContentTool treats missing read-write files as empty and creates parent directories on write."""
        nested_rel = "nested/dir/missing.txt"
        nested_host = os.path.join(self.test_dir, nested_rel)
        node = MagicMock()
        missing_rw_file = ReadWriteFile(
            relative_path="missing.txt",
            workspace_path=_make_workspace_path(nested_rel),
            owning_node=node,
        )

        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            edit_mgr = scope.get_singleton(EditManager)

            # 1. Replace tool on missing file treats content as empty -> target content not found fails cleanly
            # Requirement: Tool execution reads the file content from the filesystem, treating missing files as empty.
            b_rep = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, missing_rw_file),
                    (replace_tool.target_content_parameter, "some_text"),
                    (replace_tool.replacement_content_parameter, "new_text"),
                }
            )
            resp_rep = replace_tool.execute_tool(b_rep)
            self.assertTrue(resp_rep.is_failed)
            self.assertIn("target_content not found in file", resp_rep.content)

            # 2. Replace tool creating file treats missing file as empty and creates parent directories
            # Requirement: Tool execution writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file modifications occurred on success.
            b_create = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, missing_rw_file),
                    (replace_tool.target_content_parameter, ""),
                    (
                        replace_tool.replacement_content_parameter,
                        "First line\nSecond line\n",
                    ),
                }
            )
            resp_create = replace_tool.execute_tool(b_create)
            self.assertFalse(resp_create.is_failed)
            self.assertTrue(os.path.exists(nested_host))
            with open(nested_host, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "First line\nSecond line\n")
            self.assertTrue(edit_mgr.has_modifications)

    def test_file_update_revision(self) -> None:
        """CUJ: EditManager file_update_revision increments when editing tools modify files."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)

            # Requirement: The edit manager tracks a file update revision that increments whenever workspace files are updated.
            # Requirement: [EditManager] The edit manager exposes a file update revision that tracks sequential updates made to workspace files.
            self.assertEqual(edit_mgr.file_update_revision, 0)

            # Perform first replacement
            b1 = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 2"),
                    (replace_tool.replacement_content_parameter, "Modified Line 2"),
                }
            )
            resp1 = replace_tool.execute_tool(b1)
            self.assertFalse(resp1.is_failed)
            self.assertEqual(edit_mgr.file_update_revision, 1)

            # Perform second replacement
            b2 = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "Modified Line 1"),
                }
            )
            resp2 = replace_tool.execute_tool(b2)
            self.assertFalse(resp2.is_failed)
            self.assertEqual(edit_mgr.file_update_revision, 2)

    def test_edit_manager_initial_content_detection_and_filesystem_modifications(
        self,
    ) -> None:
        """CUJ: EditManager records initial contents from filesystem and detects creations, deletions, and errors."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            assert isinstance(edit_mgr, EditManagerImpl)

            # 1. File exists on disk, record_initial_content reads it
            existing_file = os.path.join(self.test_dir, "existing.txt")
            with open(existing_file, "w", encoding="utf-8") as f:
                f.write("initial data")
            # Requirement: The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing.
            # Requirement: [EditManager] The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.
            edit_mgr.record_initial_content(existing_file)
            self.assertFalse(edit_mgr.has_modifications)

            # 2. File deleted after initial content recorded -> has_modifications is True
            os.remove(existing_file)
            self.assertTrue(edit_mgr.has_modifications)

            # 3. Non-existent file recorded as initial content None -> has_modifications is False while absent
            new_file = os.path.join(self.test_dir, "new_file.txt")
            edit_mgr.record_initial_content(new_file)
            # Recreate existing_file so it doesn't trigger has_modifications
            with open(existing_file, "w", encoding="utf-8") as f:
                f.write("initial data")
            self.assertFalse(edit_mgr.has_modifications)

            # 4. Creating the new file on disk -> has_modifications is True
            with open(new_file, "w", encoding="utf-8") as f:
                f.write("created content")
            self.assertTrue(edit_mgr.has_modifications)
            os.remove(new_file)

            # 5. Record initial content when open raises OSError
            err_file = os.path.join(self.test_dir, "err_file.txt")
            with open(err_file, "w", encoding="utf-8") as f:
                f.write("err")
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                edit_mgr.record_initial_content(err_file)

            # 6. Read fails during has_modifications comparison -> has_modifications is True
            read_err_file = os.path.join(self.test_dir, "read_err.txt")
            with open(read_err_file, "w", encoding="utf-8") as f:
                f.write("initial read err")
            edit_mgr.record_initial_content(read_err_file, "initial read err")
            with patch("builtins.open", side_effect=OSError("Read error")):
                self.assertTrue(edit_mgr.has_modifications)

    def test_tool_parameter_converters(self) -> None:
        """CUJ: Parameter converters associated with tool parameters."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)

            # Requirement: The replace file content tool path parameter uses the alias manager to convert a file alias.
            self.assertIs(
                replace_tool.file_alias_parameter.parameter_converter, self.alias_mgr
            )
            self.assertFalse(replace_tool.file_alias_parameter.is_required)
            # Requirement: The replace file content tool target content parameter uses a string parameter converter to accept text.
            self.assertEqual(
                replace_tool.target_content_parameter.parameter_converter.actual_type,
                str,
            )
            # Requirement: The replace file content tool replacement content parameter uses a string parameter converter to accept text.
            self.assertEqual(
                replace_tool.replacement_content_parameter.parameter_converter.actual_type,
                str,
            )
            # Requirement: The replace file content tool start line parameter uses an integer parameter converter to accept an integer.
            self.assertEqual(
                replace_tool.start_line_parameter.parameter_converter.actual_type,
                int,
            )
            # Requirement: The replace file content tool end line parameter uses an integer parameter converter to accept an integer.
            self.assertEqual(
                replace_tool.end_line_parameter.parameter_converter.actual_type,
                int,
            )
            # Requirement: The replace file content tool allow multiple parameter uses a boolean parameter converter to accept a boolean.
            self.assertEqual(
                replace_tool.allow_multiple_parameter.parameter_converter.actual_type,
                bool,
            )
    def test_materialize_templates_runs_verification_checks(self) -> None:
        """CUJ: Running verification checks when templates are materialized."""
        mock_check = MagicMock()
        mock_check.verify.return_value = (True, "OK")
        mock_failing_check = MagicMock()
        mock_failing_check.verify.side_effect = RuntimeError("lint error")

        new_rw_file = ReadWriteFile(
            relative_path="templated.txt",
            workspace_path=_make_workspace_path("templated.txt"),
            owning_node=MagicMock(),
        )
        self.node_cfg._templates.add((new_rw_file, FileContent("Initial template")))
        self.node_cfg._verification_checks = [mock_check, mock_failing_check]

        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            edit_mgr.materialize_templates()
            mock_check.verify.assert_called_once()
            mock_failing_check.verify.assert_called_once()

            templated_host = os.path.join(self.test_dir, "templated.txt")
            self.assertTrue(os.path.isfile(templated_host))
            self.assertFalse(edit_mgr.has_modifications)

    def test_locked_files_management(self) -> None:
        """CUJ: Locking and unlocking read-write files in EditManager."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            # Requirement: The edit manager exposes read-write files locked against modification.
            # Requirement: [EditManager] The edit manager exposes read-write files locked against modification.
            self.assertEqual(edit_mgr.locked_files, set())

            # Requirement: The edit manager supports locking individual read-write files against modification.
            # Requirement: [EditManager] The edit manager supports locking individual read-write files against modification.
            edit_mgr.lock_file(self.rw_file)
            self.assertEqual(edit_mgr.locked_files, {self.rw_file})

            # Requirement: The edit manager supports unlocking individual read-write files.
            # Requirement: [EditManager] The edit manager supports unlocking individual read-write files.
            edit_mgr.unlock_file(self.rw_file)
            self.assertEqual(edit_mgr.locked_files, set())

    def test_replace_file_content_fails_on_locked_file(self) -> None:
        """CUJ: Replacing content fails when target file is locked against modification."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)

            edit_mgr.lock_file(self.rw_file)

            # Requirement: Before modifying a file, editing tool execution fails if the file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.
            bindings = ActualParameterBindings(
                bindings={
                    (replace_tool.file_alias_parameter, self.rw_file),
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "New Line 1"),
                }
            )
            resp = replace_tool.execute_tool(bindings)
            self.assertTrue(resp.is_failed)
            self.assertIn("has been locked against further modification", resp.content)
            self.assertIsNotNone(resp.reminder)
            self.assertIn(
                "Files that have been the target of a submit, fail, or blame cannot be modified.",
                resp.reminder or "",
            )

            # Unlock allows modification again
            edit_mgr.unlock_file(self.rw_file)
            resp_unlocked = replace_tool.execute_tool(bindings)
            self.assertFalse(resp_unlocked.is_failed)

    def test_edit_manager_tracks_last_read_or_edited_file(self) -> None:
        """CUJ: EditManager tracks last read or edited file alias across session."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            # Requirement: The edit manager tracks the last read or edited file alias across the session, recording file reads from the file reader and file edits from editing tools.
            self.assertIsNone(edit_mgr.last_read_or_edited_file)

            edit_mgr.record_file_read(self.ro_file)
            self.assertEqual(edit_mgr.last_read_or_edited_file, self.ro_file)

            edit_mgr.record_file_edit(self.rw_file)
            self.assertEqual(edit_mgr.last_read_or_edited_file, self.rw_file)

    def test_replace_file_content_optional_path(self) -> None:
        """CUJ: ReplaceFileContentTool implicitly binds omitted path to last read or edited file."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)

            # 1. Path omitted when no file read or edited yet -> fails
            b_no_file = ActualParameterBindings(
                bindings={
                    (replace_tool.target_content_parameter, "Line 1"),
                    (replace_tool.replacement_content_parameter, "Modified Line 1"),
                }
            )
            # Requirement: Tool execution implicitly binds the target file to the last file read or edited in the edit manager if that file is a read-write file, informs the agent with a warning in the response content that the path was implicitly bound while allowing the tool execution to proceed, or fails if no file has been read or edited or if the last read or edited file is not a read-write file, when the path parameter is omitted.
            resp_no_file = replace_tool.execute_tool(b_no_file)
            self.assertTrue(resp_no_file.is_failed)
            self.assertIn("no file has been read or edited yet", resp_no_file.content)

            # 2. Path omitted when last accessed file is read-only -> fails
            edit_mgr.record_file_read(self.ro_file)
            resp_ro = replace_tool.execute_tool(b_no_file)
            self.assertTrue(resp_ro.is_failed)
            self.assertIn("is not a read-write file", resp_ro.content)

            # 3. Path omitted when last accessed file is read-write -> succeeds with warning
            edit_mgr.record_file_read(self.rw_file)
            resp_rw = replace_tool.execute_tool(b_no_file)
            self.assertFalse(resp_rw.is_failed)
            self.assertIn(
                "Warning: 'path' was not specified; implicitly editing last accessed file",
                resp_rw.content,
            )
            self.assertEqual(edit_mgr.last_read_or_edited_file, self.rw_file)

    def test_can_write_operation(self) -> None:
        """CUJ: EditManager validates modification access for read-write files and prevents modification of locked files via can_write."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_mgr = scope.get_singleton(EditManager)
            # Requirement: [EditManager] The edit manager provides a can write operation validating modification access for a read-write file.

            # 1. Non-read-write file fails
            # Requirement: Tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
            resp_ro = edit_mgr.can_write(self.ro_file.relative_path)
            self.assertTrue(resp_ro.is_failed)
            self.assertIn("is not a declared read-write file", resp_ro.content)
            self.assertEqual(
                resp_ro.reminder, "Only declared read-write files can be modified."
            )

            # 2. Unlocked read-write file succeeds and records edit
            # Requirement: When an unlocked read-write file is supplied, tool execution records the file edit in the edit manager and produces a successful response indicating that modification is permitted.
            resp_rw = edit_mgr.can_write(self.rw_file.relative_path)
            self.assertFalse(resp_rw.is_failed)
            self.assertIn("Modification permitted", resp_rw.content)
            self.assertEqual(edit_mgr.last_read_or_edited_file, self.rw_file)

            # Test passing FileAlias directly
            resp_rw_direct = edit_mgr.can_write(self.rw_file)
            self.assertFalse(resp_rw_direct.is_failed)

            # 3. Locked file fails
            edit_mgr.lock_file(self.rw_file)
            # Requirement: Tool execution fails if the file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.
            resp_locked = edit_mgr.can_write(self.rw_file.relative_path)
            self.assertTrue(resp_locked.is_failed)
            self.assertIn("locked against further modification", resp_locked.content)
            self.assertEqual(
                resp_locked.reminder,
                "Files that have been the target of a submit, fail, or blame cannot be modified.",
            )

            # 4. Unlocking permits modification again
            edit_mgr.unlock_file(self.rw_file)
            resp_unlocked = edit_mgr.can_write(self.rw_file.relative_path)
            self.assertFalse(resp_unlocked.is_failed)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
# - [Tool] When a parameter is required, an argument must be supplied for tool execution.
