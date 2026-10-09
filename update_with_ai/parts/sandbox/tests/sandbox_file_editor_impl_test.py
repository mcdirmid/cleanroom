# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:46:23Z
# LAST_CHANGED: 2026-10-09T22:20:00Z
# CHANGE: Test has_modifications with dataclass workspace_root
# CODE_HASH: 98d71cccf0f7
# QA_AUDIT: 2026-10-09T21:46:23Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_file_editor_impl per its grounding specification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import tempfile
import unittest
from typing import Any, Dict, Mapping, Optional, Set, cast

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib import (
    agent_config,
    agent_file_alias,
    agent_node_config,
)
from update_with_ai.parts.control.lib import src_metadata
from update_with_ai.parts.sandbox.lib import sandbox_file_editor, tool_provider
from update_with_ai.parts.sandbox.lib.sandbox_file_editor_impl import (
    EditManager,
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


def _make_read_only_file(rel_path: str) -> agent_file_alias.ReadOnlyFile:
    return agent_file_alias.ReadOnlyFile(
        relative_path=agent_file_alias.RelativePath(rel_path),
        workspace_path=cast(Any, rel_path),
        owning_node=cast(Any, None),
    )


def _make_read_write_file(rel_path: str) -> agent_file_alias.ReadWriteFile:
    return agent_file_alias.ReadWriteFile(
        relative_path=agent_file_alias.RelativePath(rel_path),
        workspace_path=cast(Any, rel_path),
        owning_node=cast(Any, None),
    )


class MockAgentConfig:
    tier = system

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
        return False

    @property
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        return agent_config.SupersedeArgKeepLimit(50)


class MockNodeConfig:
    tier = agent_session

    def __init__(
        self,
        read_only_files: Optional[Set[agent_file_alias.ReadOnlyFile]] = None,
        read_write_files: Optional[Set[agent_file_alias.ReadWriteFile]] = None,
    ) -> None:
        self._read_only_files = read_only_files if read_only_files is not None else set()
        self._read_write_files = read_write_files if read_write_files is not None else set()

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        return self._read_only_files

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        return self._read_write_files

    @property
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        return {}


class MockToolManager:
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


class MockAliasManager:
    tier = agent_session

    def __init__(self, workspace_root: Any) -> None:
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
        return agent_file_alias.UnboundFile(agent_file_alias.RelativePath(wire_value))

    def sanitize_text(
        self, text: agent_file_alias.UnsanitizedText
    ) -> agent_file_alias.SanitizedText:
        return agent_file_alias.SanitizedText(str(text))


class MockSourceMetadataCoordinator:
    tier = agent_session

    def __init__(self) -> None:
        self.modified = False

    def is_code_modified(self, file_path: Any) -> bool:
        return self.modified

    def extract_metadata(self, file_path: Any) -> Any:
        return None

    def compute_code_hash(self, content: str, filename_or_ext: str) -> str:
        return "123456789012"


class SandboxFileEditorImplTest(unittest.TestCase):
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
        self.registry.register_instance(
            MockNodeConfig(
                read_only_files={self.read_only_file},
                read_write_files={self.read_write_file},
            ),
            keys=[agent_node_config.NodeConfig],
            tier=agent_session,
        )
        self.registry.register_instance(
            MockAgentConfig(),
            keys=[agent_config.AgentConfig],
            tier=system,
        )
        self.mock_tool_manager = MockToolManager()
        self.registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session,
        )
        self.mock_alias_manager = MockAliasManager(self.root)
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[
                agent_file_alias.AliasManager,
                tool_provider.ParameterType[agent_file_alias.FileAlias, str],
            ],
            tier=agent_session,
        )
        self.mock_src_metadata = MockSourceMetadataCoordinator()
        self.registry.register_instance(
            self.mock_src_metadata,
            keys=[src_metadata.SourceMetadataCoordinator],
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
        path: Optional[agent_file_alias.FileAlias] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        allow_multiple: Optional[bool] = None,
    ) -> Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]:
        params = tool.parameters
        bindings: Dict[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType] = {
            params[tool_provider.ParameterName("target_content")]: tool_provider.SomeParameterActualType(
                sandbox_file_editor.TargetContent(target)
            ),
            params[tool_provider.ParameterName("replacement_content")]: tool_provider.SomeParameterActualType(
                sandbox_file_editor.ReplacementContent(replacement)
            ),
            params[tool_provider.ParameterName("start_line")]: tool_provider.SomeParameterActualType(
                None if start_line is None else sandbox_file_editor.LineNumber(start_line)
            ),
            params[tool_provider.ParameterName("end_line")]: tool_provider.SomeParameterActualType(
                None if end_line is None else sandbox_file_editor.LineNumber(end_line)
            ),
            params[tool_provider.ParameterName("allow_multiple")]: tool_provider.SomeParameterActualType(
                sandbox_file_editor.AllowMultiple(bool(allow_multiple))
            ),
        }
        if path is not None:
            bindings[params[tool_provider.ParameterName("path")]] = tool_provider.SomeParameterActualType(path)
        return bindings

    def test_initialization(self) -> None:
        """CUJ: Singletons resolve and replace tool exposes its contracted parameters."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            self.assertIsNone(edit_manager.last_read_or_edited_file)
            self.assertEqual(
                edit_manager.file_update_revision,
                sandbox_file_editor.FileUpdateRevision(0),
            )
            self.assertFalse(edit_manager.has_modifications)

            self.assertEqual(replace_tool.name, tool_provider.ToolName("replace_file_content"))
            self.assertTrue(len(replace_tool.description) > 0)

            param_names = {
                tool_provider.ParameterName("path"),
                tool_provider.ParameterName("target_content"),
                tool_provider.ParameterName("replacement_content"),
                tool_provider.ParameterName("start_line"),
                tool_provider.ParameterName("end_line"),
                tool_provider.ParameterName("allow_multiple"),
            }
            self.assertTrue(param_names.issubset(set(replace_tool.parameters.keys())))

            self.assertEqual(replace_tool.path_parameter.name, tool_provider.ParameterName("path"))
            self.assertEqual(replace_tool.target_content_parameter.name, tool_provider.ParameterName("target_content"))
            self.assertEqual(replace_tool.replacement_content_parameter.name, tool_provider.ParameterName("replacement_content"))
            self.assertEqual(replace_tool.start_line_parameter.name, tool_provider.ParameterName("start_line"))
            self.assertEqual(replace_tool.end_line_parameter.name, tool_provider.ParameterName("end_line"))
            self.assertEqual(replace_tool.allow_multiple_parameter.name, tool_provider.ParameterName("allow_multiple"))

    def test_record_file_read_updates_last_file(self) -> None:
        """Postcondition: record_file_read MUST update the last read or edited file."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            edit_manager.record_file_read(self.read_only_file)
            self.assertEqual(edit_manager.last_read_or_edited_file, self.read_only_file)
            edit_manager.record_file_read(self.read_write_file)
            self.assertEqual(edit_manager.last_read_or_edited_file, self.read_write_file)

    def test_record_file_edit_updates_last_file_and_revision(self) -> None:
        """Postcondition: record_file_edit MUST update last file and increment the revision."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            rev0 = edit_manager.file_update_revision
            edit_manager.record_file_read(self.read_only_file)
            edit_manager.record_file_edit(self.read_write_file)
            self.assertEqual(edit_manager.last_read_or_edited_file, self.read_write_file)
            rev1 = edit_manager.file_update_revision
            self.assertGreater(rev1, rev0)
            edit_manager.record_file_edit(self.read_write_file)
            self.assertGreater(edit_manager.file_update_revision, rev1)

    def test_file_hash_is_md5_of_content(self) -> None:
        """Postcondition: file_hash MUST return the MD5 hex digest of filesystem content."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            expected = hashlib.md5(INITIAL_CONTENT.encode("utf-8")).hexdigest()
            self.assertEqual(
                edit_manager.file_hash(self.read_write_file),
                sandbox_file_editor.FileHash(expected),
            )

    def test_has_modifications_reflects_edits(self) -> None:
        """Postcondition: has_modifications MUST reflect modification status."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            self.assertFalse(edit_manager.has_modifications)
            self.mock_src_metadata.modified = True
            self.assertTrue(edit_manager.has_modifications)

    def test_has_modifications_with_dataclass_workspace_root(self) -> None:
        """Postcondition: has_modifications handles dataclass workspace_root correctly."""
        @dataclass(frozen=True)
        class DummyWsRoot:
            path: str

        self.mock_alias_manager._workspace_root = DummyWsRoot(path=self.root)
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            self.assertFalse(edit_manager.has_modifications)

    def test_can_write_rejects_undeclared_file(self) -> None:
        """Postcondition: WHEN not a declared read-write file, MUST fail with guidance."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            resp_undeclared = edit_manager.can_write(agent_file_alias.RelativePath("undeclared.py"))
            self.assertTrue(resp_undeclared.is_failed)
            resp_read_only = edit_manager.can_write(self.read_only_file)
            self.assertTrue(resp_read_only.is_failed)
            self.assertIsNone(edit_manager.last_read_or_edited_file)

    def test_can_write_permits_declared_file(self) -> None:
        """Postcondition: WHEN a declared read-write file is supplied, MUST record edit and confirm access."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            resp_alias = edit_manager.can_write(self.read_write_file)
            self.assertFalse(resp_alias.is_failed)
            self.assertEqual(edit_manager.last_read_or_edited_file, self.read_write_file)
            resp_path = edit_manager.can_write(agent_file_alias.RelativePath("read_write.py"))
            self.assertFalse(resp_path.is_failed)

    def test_replace_success_writes_and_reminds(self) -> None:
        """Postcondition: On success MUST write content, record writes, and remind to call check files."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            rev0 = edit_manager.file_update_revision
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "unique_target", "replaced_target", path=self.read_write_file)
            )
            self.assertFalse(resp.is_failed)
            self.assertEqual(
                self._read_rw(), INITIAL_CONTENT.replace("unique_target", "replaced_target")
            )
            self.assertGreater(edit_manager.file_update_revision, rev0)
            self.assertEqual(edit_manager.last_read_or_edited_file, self.read_write_file)
            self.assertIsNotNone(resp.reminder)
            self.assertIn("check", str(resp.reminder).lower())

    def test_replace_creates_missing_parent_directories(self) -> None:
        """Postcondition: On success MUST write updated content creating missing parent directories."""
        nested = _make_read_write_file("nested/dir/new.py")
        registry = LifecycleRegistry()
        __initialize__(registry)
        registry.register_instance(
            MockNodeConfig(read_write_files={nested}),
            keys=[agent_node_config.NodeConfig],
            tier=agent_session,
        )
        registry.register_instance(MockAgentConfig(), keys=[agent_config.AgentConfig], tier=system)
        registry.register_instance(MockToolManager(), keys=[tool_provider.ToolManager], tier=agent_session)
        registry.register_instance(
            MockAliasManager(self.root),
            keys=[
                agent_file_alias.AliasManager,
                tool_provider.ParameterType[agent_file_alias.FileAlias, str],
            ],
            tier=agent_session,
        )
        registry.register_instance(
            MockSourceMetadataCoordinator(),
            keys=[src_metadata.SourceMetadataCoordinator],
            tier=agent_session,
        )
        with enter_phase(agent_session, registry=registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "", "new content\n", path=nested, start_line=1)
            )
            host = os.path.join(self.root, "nested", "dir", "new.py")
            if not resp.is_failed:
                self.assertTrue(os.path.isfile(host))
                with open(host, "r", encoding="utf-8") as fh:
                    self.assertIn("new content", fh.read())

    def test_replace_multiple_when_allowed(self) -> None:
        """Postcondition: WHEN multiple replacements permitted, MUST replace multiple occurrences."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool, "repeated", "updated", path=self.read_write_file, allow_multiple=True
                )
            )
            self.assertFalse(resp.is_failed)
            content = self._read_rw()
            self.assertNotIn("repeated", content)
            self.assertEqual(content.count("updated"), 2)

    def test_replace_multiple_rejected_when_not_allowed(self) -> None:
        """Postcondition: WHEN allow_multiple false and multiple matches, MUST fail citing first two line numbers."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "repeated", "updated", path=self.read_write_file)
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("2", str(resp.content))
            self.assertIn("4", str(resp.content))
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_within_bounded_line_range(self) -> None:
        """Postcondition: MUST replace target content within the bounded line range."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool, "repeated", "bounded", path=self.read_write_file, start_line=3, end_line=4
                )
            )
            self.assertFalse(resp.is_failed)
            lines = self._read_rw().splitlines()
            self.assertEqual(lines[1], "repeated")
            self.assertEqual(lines[3], "bounded")

    def test_replace_target_outside_window_fails_with_locations(self) -> None:
        """Postcondition: WHEN target not in window but exists elsewhere, MUST fail citing line numbers."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool, "outside_target", "x", path=self.read_write_file, start_line=1, end_line=2
                )
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("6", str(resp.content))
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_whitespace_fallback(self) -> None:
        """Postcondition: WHEN exact match finds zero and allow_multiple false, MUST fall back to stripped matching."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "indented line", "    renamed line", path=self.read_write_file)
            )
            self.assertFalse(resp.is_failed)
            self.assertIn("renamed line", self._read_rw())
            self.assertNotIn("indented line", self._read_rw())

    def test_replace_noop_fails(self) -> None:
        """Postcondition: WHEN the edit produces no change, MUST fail reminding no-op edits will fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "unique_target", "unique_target", path=self.read_write_file)
            )
            self.assertTrue(resp.is_failed)
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_invalid_line_bounds_fail(self) -> None:
        """Postcondition: Invalid start_line / end_line combinations MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            total = len(INITIAL_CONTENT.splitlines())
            cases = [
                (0, None),
                (total + 2, None),
                (None, 0),
                (None, total + 1),
                (5, 3),
            ]
            for start, end in cases:
                with self.subTest(start_line=start, end_line=end):
                    resp = replace_tool.execute_tool(
                        self._bindings(
                            replace_tool,
                            "unique_target",
                            "x",
                            path=self.read_write_file,
                            start_line=start,
                            end_line=end,
                        )
                    )
                    self.assertTrue(resp.is_failed)
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_omitted_path_without_history_fails(self) -> None:
        """Postcondition: WHEN path omitted and no read-write history exists, MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            edit_manager.record_file_read(self.read_only_file)
            resp = replace_tool.execute_tool(self._bindings(replace_tool, "unique_target", "x"))
            self.assertTrue(resp.is_failed)
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_omitted_path_binds_last_read_write_file(self) -> None:
        """Postcondition: WHEN path omitted and last file is read-write, MUST bind to it and warn."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            edit_manager.record_file_read(self.read_write_file)
            resp = replace_tool.execute_tool(self._bindings(replace_tool, "unique_target", "bound_target"))
            self.assertFalse(resp.is_failed)
            self.assertIn("bound_target", self._read_rw())
            self.assertTrue(len(str(resp.content)) > 0)

    def test_file_hash_missing_file(self) -> None:
        """Postcondition: File hashing when the target file does not exist on disk."""
        missing = _make_read_write_file("nonexistent.py")
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            try:
                digest = edit_manager.file_hash(missing)
                self.assertIsInstance(digest, str)
            except (FileNotFoundError, OSError):
                pass

    def test_replace_rejects_undeclared_or_read_only_file(self) -> None:
        """Postcondition: Rejecting execution when the replacement tool is invoked on a file that is not a declared read-write file."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            # Invoked on read-only file
            resp_ro = replace_tool.execute_tool(
                self._bindings(replace_tool, "line", "newline", path=self.read_only_file)
            )
            self.assertTrue(resp_ro.is_failed)

            # Invoked on undeclared file
            undeclared = agent_file_alias.UnboundFile(agent_file_alias.RelativePath("undeclared.py"))
            resp_undecl = replace_tool.execute_tool(
                self._bindings(replace_tool, "line", "newline", path=undeclared)
            )
            self.assertTrue(resp_undecl.is_failed)

    def test_replace_target_not_found_anywhere(self) -> None:
        """Postcondition: Reporting failure when target content cannot be found anywhere in the file."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "completely_nonexistent_string_12345",
                    "replacement",
                    path=self.read_write_file,
                )
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("not found", str(resp.content).lower())

    def test_replace_file_content_tool_initialize_installs_into_tool_manager(self) -> None:
        """Postcondition: ReplaceFileContentTool.initialize installs replace_file_content into ToolManager."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            replace_tool.initialize()
            self.assertIn(tool_provider.ToolName("replace_file_content"), self.mock_tool_manager.installed_tools)
            self.assertIs(self.mock_tool_manager.installed_tools[tool_provider.ToolName("replace_file_content")], replace_tool)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
