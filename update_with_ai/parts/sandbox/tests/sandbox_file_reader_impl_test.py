# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-09T04:19:04Z
# CHANGE: Fix MockFilePathManager.resolve_path and path creation to handle string workspace_root paths
# CODE_HASH: 268c736feb48
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_file_reader_impl per its grounding specification."""

from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any, Dict, List, Mapping, Optional, Set, cast

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import (
    agent_file_alias,
    agent_node_config,
    agent_session,
)
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.sandbox.lib import (
    sandbox_file_editor,
    sandbox_file_reader,
    template_format,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.sandbox_file_reader_impl import (
    ReadManager,
    ViewFileTool,
    RegexPatternParameterType,
    SearchTool,
    __initialize__,
)


def _make_read_only_file(rel_path: str, host_path: Optional[str] = None) -> agent_file_alias.ReadOnlyFile:
    path = host_path if host_path is not None else rel_path
    obj = agent_file_alias.ReadOnlyFile(
        relative_path=agent_file_alias.RelativePath(rel_path),
        workspace_path=cast(Any, path),
        owning_node=cast(Any, None),
    )
    object.__setattr__(obj, "resolve_path", lambda: path)
    return obj


def _make_read_write_file(rel_path: str, host_path: Optional[str] = None) -> agent_file_alias.ReadWriteFile:
    path = host_path if host_path is not None else rel_path
    obj = agent_file_alias.ReadWriteFile(
        relative_path=agent_file_alias.RelativePath(rel_path),
        workspace_path=cast(Any, path),
        owning_node=cast(Any, None),
    )
    object.__setattr__(obj, "resolve_path", lambda: path)
    return obj


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(
        self,
        read_only_files: Optional[Set[agent_file_alias.ReadOnlyFile]] = None,
        read_write_files: Optional[Set[agent_file_alias.ReadWriteFile]] = None,
        template_parameters: Optional[Mapping[agent_node_config.TemplateParamKey, Any]] = None,
    ) -> None:
        self._read_only_files = read_only_files if read_only_files is not None else set()
        self._read_write_files = read_write_files if read_write_files is not None else set()
        self._template_parameters = template_parameters if template_parameters is not None else {}

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        return self._read_only_files

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        return self._read_write_files

    @property
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        return self._template_parameters


class MockToolManager:
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


class MockEditManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.reads: List[agent_file_alias.FileAlias] = []
        self._last_file: Optional[agent_file_alias.FileAlias] = None

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        return self._last_file

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        self.reads.append(file)
        self._last_file = file


class MockTemplateFormatter:
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


class MockAliasManager:
    tier = agent_session.agent_session

    def __init__(self, workspace_root: str = "/tmp/workspace") -> None:
        self._workspace_root = workspace_root

    @property
    def workspace_root(self) -> Any:
        return self._workspace_root

    @property
    def actual_type(self) -> type[agent_file_alias.FileAlias]:
        return agent_file_alias.FileAlias

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        return agent_file_alias.FileAlias(agent_file_alias.RelativePath(wire_value))

    def sanitize_text(
        self, text: agent_file_alias.UnsanitizedText
    ) -> agent_file_alias.SanitizedText:
        s = str(text)
        if self._workspace_root in s:
            s = s.replace(self._workspace_root, "<sanitized_root>")
        return agent_file_alias.SanitizedText(s)


class MockFilePathManager:
    tier = system

    def create_host_path(self, path: Any) -> file_paths.HostPath:
        p = str(path.path) if hasattr(path, "path") else str(path)
        return file_paths.HostPath(file_paths.PathString(p))

    def create_absolute_path(self, path: Any) -> file_paths.AbsolutePath:
        p = str(path.path) if hasattr(path, "path") else str(path)
        return file_paths.AbsolutePath(file_paths.PathString(p))

    def create_workspace_path(self, path: Any) -> file_paths.WorkspacePath:
        p = str(path.path) if hasattr(path, "path") else str(path)
        return file_paths.WorkspacePath(file_paths.PathString(p))

    def resolve_path(
        self, root: Any, relative: Any
    ) -> file_paths.AbsolutePath:
        root_str = str(root.path) if hasattr(root, "path") else str(root)
        rel_str = str(relative.path) if hasattr(relative, "path") else str(relative)
        return file_paths.AbsolutePath(file_paths.PathString(os.path.join(root_str, rel_str)))


class MockRoleConfig:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.role = agent_node_config.RoleName("developer")
        self.nodes: List[Any] = []
        self.version = agent_node_config.ExecutionVersion(1)

    def set_role(self, role: Any) -> None:
        self.role = role

    def set_nodes(self, nodes: Any) -> None:
        self.nodes = list(nodes)


class SandboxFileReaderImplTest(unittest.TestCase):
    def setUp(self) -> None:
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
        self.mock_node_config = MockNodeConfig(
            read_only_files={self.declared_read_only, self.declared_ro_md, self.missing_read_only},
            read_write_files={self.declared_read_write, self.missing_read_write},
            template_parameters={agent_node_config.TemplateParamKey("user"): "Developer"},
        )
        self.registry.register_instance(
            self.mock_node_config,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )
        self.mock_tool_manager = MockToolManager()
        self.registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session.agent_session,
        )
        self.mock_edit_manager = MockEditManager()
        self.registry.register_instance(
            self.mock_edit_manager,
            keys=[sandbox_file_editor.EditManager],
            tier=agent_session.agent_session,
        )
        self.mock_template_formatter = MockTemplateFormatter()
        self.registry.register_instance(
            self.mock_template_formatter,
            keys=[template_format.TemplateFormatter],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager = MockAliasManager(self.root)
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[
                agent_file_alias.AliasManager,
                tool_provider.ParameterType[agent_file_alias.FileAlias, str],
            ],
            tier=agent_session.agent_session,
        )
        self.mock_file_path_manager = MockFilePathManager()
        self.registry.register_instance(
            self.mock_file_path_manager,
            keys=[file_paths.FilePathManager],
            tier=system,
        )
        self.mock_role_config = MockRoleConfig()
        self.registry.register_instance(
            self.mock_role_config,
            keys=[agent_node_config.RoleConfig],
            tier=agent_session.agent_session,
        )

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and singleton resolution."""
        self.assertIsNotNone(self.registry)
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            for cls in [ReadManager, ViewFileTool, RegexPatternParameterType, SearchTool]:
                instance = scope.get_singleton(cls)
                self.assertIsNotNone(instance)
            self.assertIn(
                tool_provider.ToolName("view_file"),
                self.mock_tool_manager.installed_tools,
            )
            self.assertNotIn(
                tool_provider.ToolName("search_files"),
                self.mock_tool_manager.installed_tools,
            )

    def test_read_manager_access_control(self) -> None:
        """Postcondition: Check access permissions for declared and undeclared files."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ReadManager)
            # Declared file access
            resp_decl = manager.can_read(agent_file_alias.RelativePath("sample.py"))
            self.assertFalse(resp_decl.is_failed)
            self.assertEqual(resp_decl.content, "Access permitted for 'sample.py'.")

            # Undeclared file access
            resp_undecl = manager.can_read(agent_file_alias.RelativePath("undeclared.py"))
            self.assertTrue(resp_undecl.is_failed)
            self.assertTrue(str(resp_undecl.content).startswith("Error: Unknown file 'undeclared.py'. Available files: "))
            self.assertEqual(resp_undecl.reminder, "Only declared files can be inspected.")

    def test_read_manager_file_properties(self) -> None:
        """Postcondition: Exposes session read-only and read-write files resolved from NodeConfig."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(ReadManager)
            self.assertEqual(manager.read_only_files, {self.declared_read_only, self.declared_ro_md, self.missing_read_only})
            self.assertEqual(manager.read_write_files, {self.declared_read_write, self.missing_read_write})

    def test_regex_pattern_conversion(self) -> None:
        """Postcondition: Convert valid regex pattern and raise ParameterConversionError on invalid."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            param_type = scope.get_singleton(RegexPatternParameterType)
            self.assertEqual(param_type.wire_type, str)
            self.assertEqual(param_type.actual_type, agent_file_alias.RegexPattern)
            valid = param_type.convert("^test.*[0-9]+$")
            self.assertEqual(valid, agent_file_alias.RegexPattern("^test.*[0-9]+$"))

            with self.assertRaises(tool_provider.ParameterConversionError) as ctx:
                param_type.convert("[invalid(regex")
            self.assertTrue(str(ctx.exception.message).startswith("Invalid regex pattern '[invalid(regex': "))

    def test_view_file_tool_metadata(self) -> None:
        """Postcondition: Verify view_file tool parameters and metadata."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ViewFileTool)
            self.assertEqual(tool.name, tool_provider.ToolName("view_file"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool.path_parameter.name, tool.parameters)

    def test_view_file_read_only_formatting_and_sanitization(self) -> None:
        """Postcondition: Line-number formatting, path sanitization, suppression key omission, and read recording."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ViewFileTool)
            resp = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.declared_read_only),
            })
            self.assertFalse(resp.is_failed)
            # Verify 1-indexed right-aligned line numbers followed by a colon and space
            content_str = str(resp.content)
            self.assertIn("1: def hello():", content_str)
            # Verify text sanitization of host paths
            self.assertNotIn(self.root, content_str)
            self.assertIn("<sanitized_root>", content_str)
            # Verify suppression key is omitted for read-only files
            self.assertIsNone(resp.suppression_key)
            # Verify read was recorded
            self.assertEqual(self.mock_edit_manager.last_read_or_edited_file, self.declared_read_only)

    def test_view_file_read_write_suppression_and_missing_handling(self) -> None:
        """Postcondition: Suppression key delivery for read-write file, and empty content for missing read-write file."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ViewFileTool)
            # Existing read-write file: suppression key matching relative path
            resp = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.declared_read_write),
            })
            self.assertFalse(resp.is_failed)
            self.assertEqual(
                resp.suppression_key,
                tool_provider.SuppressionKey(str(self.declared_read_write.relative_path)),
            )
            self.assertEqual(self.mock_edit_manager.last_read_or_edited_file, self.declared_read_write)

            # Missing read-write file: treated as empty
            resp_missing = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.missing_read_write),
            })
            self.assertFalse(resp_missing.is_failed)
            self.assertEqual(str(resp_missing.content).strip(), "")

    def test_view_file_markdown_template_and_meta_filtering(self) -> None:
        """Postcondition: Filter > META: lines and substitute template parameters for markdown files."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ViewFileTool)
            resp = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.declared_ro_md),
            })
            self.assertFalse(resp.is_failed)
            content_str = str(resp.content)
            # Filter out paragraphs beginning with '> META:'
            self.assertNotIn("> META:", content_str)
            self.assertNotIn("internal note", content_str)
            # Format content with session template parameters
            self.assertIn("Hello Developer!", content_str)
            self.assertNotIn("<user>", content_str)

    def test_view_file_missing_and_undeclared_errors(self) -> None:
        """Postcondition: Missing read-only file and undeclared unbound file produce failures with guidance."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(ViewFileTool)

            # Missing read-only file on disk
            resp_missing = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(self.missing_read_only),
            })
            self.assertTrue(resp_missing.is_failed)
            self.assertEqual(
                str(resp_missing.content),
                f"Error: File '{self.missing_read_only.relative_path}' does not exist on disk.",
            )
            self.assertEqual(resp_missing.reminder, tool_provider.ToolReminder("Only declared files can be inspected."))

            # Undeclared unbound file
            unbound = agent_file_alias.UnboundFile(agent_file_alias.RelativePath("unbound.py"))
            resp_unbound = tool.execute_tool({
                tool.path_parameter: tool_provider.SomeParameterActualType(unbound),
            })
            self.assertTrue(resp_unbound.is_failed)
            self.assertTrue(
                str(resp_unbound.content).startswith(f"Error: Unknown file '{unbound.relative_path}'. Available files: ")
            )
            self.assertEqual(resp_unbound.reminder, tool_provider.ToolReminder("Only declared files can be inspected."))

    def test_search_tool_metadata(self) -> None:
        """Postcondition: Verify search tool parameters and metadata."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SearchTool)
            self.assertEqual(tool.name, tool_provider.ToolName("search_files"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool.regex_pattern_parameter.name, tool.parameters)

    def test_search_tool_execution(self) -> None:
        """Postcondition: Match read-only lines sanitized, redact read-write details, fallback on no-match, and fail on invalid regex."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SearchTool)

            # Pattern matching read-only and read-write files
            resp_match = tool.execute_tool({
                tool.regex_pattern_parameter: tool_provider.SomeParameterActualType(
                    agent_file_alias.RegexPattern("def|class")
                ),
            })
            self.assertFalse(resp_match.is_failed)
            content_str = str(resp_match.content)
            # Read-only match returns line contents and numbers, sanitized
            self.assertIn("def hello():", content_str)
            self.assertNotIn(self.root, content_str)
            # Read-write match details hidden
            expected_rw_msg = f"{self.declared_read_write.relative_path}: matches found (details hidden to prevent unanchored edits)"
            self.assertIn(expected_rw_msg, content_str)

            # No-match fallback response
            resp_nomatch = tool.execute_tool({
                tool.regex_pattern_parameter: tool_provider.SomeParameterActualType(
                    agent_file_alias.RegexPattern("nonexistent_pattern_12345")
                ),
            })
            self.assertFalse(resp_nomatch.is_failed)
            self.assertIn("no match", str(resp_nomatch.content).lower())

            # Invalid regex pattern failure
            resp_invalid = tool.execute_tool({
                tool.regex_pattern_parameter: tool_provider.SomeParameterActualType(
                    agent_file_alias.RegexPattern("[invalid(")
                ),
            })
            self.assertTrue(resp_invalid.is_failed)
            self.assertTrue(str(resp_invalid.content).startswith("Error: Invalid regex pattern "))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
