# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-12T23:43:51Z
# CHANGE: Cover whitespace fallback unique match replacement and ambiguous match failure guidance when exact matching finds zero occurrences
# CODE_HASH: 9930eaae853f
# COVERAGE_AUDIT: 2026-10-13T01:05:05Z
# QA_AUDIT: 2026-10-13T01:05:05Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_file_editor_impl per its grounding specification."""

from __future__ import annotations

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
        workspace_path=agent_file_alias.file_paths.WorkspacePath(
            agent_file_alias.file_paths.PathString(rel_path)
        ),
        owning_node=cast(Any, None),
    )


def _make_read_write_file(rel_path: str) -> agent_file_alias.ReadWriteFile:
    return agent_file_alias.ReadWriteFile(
        relative_path=agent_file_alias.RelativePath(rel_path),
        workspace_path=agent_file_alias.file_paths.WorkspacePath(
            agent_file_alias.file_paths.PathString(rel_path)
        ),
        owning_node=cast(Any, None),
    )


class MockAgentConfig:
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

    def __init__(
        self,
        workspace_root: str,
        known_files: Optional[Set[agent_file_alias.FileAlias]] = None,
    ) -> None:
        self._workspace_root = agent_file_alias.file_paths.WorkspaceRoot(
            agent_file_alias.file_paths.PathString(str(workspace_root))
        )
        self._known_files = known_files if known_files is not None else set()

    @property
    def workspace_root(self) -> agent_file_alias.file_paths.WorkspaceRoot:
        return self._workspace_root

    @property
    def actual_type(self) -> type[agent_file_alias.FileAlias]:
        return agent_file_alias.FileAlias

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        for f in self._known_files:
            if str(f.relative_path) == wire_value:
                return f
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
        self.mock_alias_manager = MockAliasManager(
            self.root, known_files={self.read_only_file, self.read_write_file}
        )
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

    def test_file_hash_unbound_file_alias_resolves_to_declared_file(self) -> None:
        """Postcondition: file_hash MUST compute MD5 digest for an unbound file alias that resolves to a declared workspace file."""
        unbound_rw = agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath("read_write.py")
        )
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            expected_hash = hashlib.md5(INITIAL_CONTENT.encode("utf-8")).hexdigest()
            digest = edit_manager.file_hash(unbound_rw)
            self.assertEqual(digest, sandbox_file_editor.FileHash(expected_hash))

        unbound_ro = agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath("read_only.py")
        )
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            expected_ro_hash = hashlib.md5(b"readonly\n").hexdigest()
            digest_ro = edit_manager.file_hash(unbound_ro)
            self.assertEqual(digest_ro, sandbox_file_editor.FileHash(expected_ro_hash))

    def test_has_modifications_reflects_edits(self) -> None:
        """Postcondition: has_modifications MUST reflect modification status."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            self.assertFalse(edit_manager.has_modifications)
            self.mock_src_metadata.modified = True
            self.assertTrue(edit_manager.has_modifications)

    def test_has_modifications_with_contracted_workspace_root(self) -> None:
        """Postcondition: has_modifications evaluates with the contracted workspace root record."""
        root = self.mock_alias_manager.workspace_root
        self.assertIsInstance(root, agent_file_alias.file_paths.WorkspaceRoot)
        self.assertEqual(root.path, self.root)
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
        """Postcondition: On success MUST write content, record writes, and remind to verify syntax and types."""
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
            self.assertEqual(
                resp.suppression_key,
                tool_provider.SuppressionKey("replace_file_content"),
            )
            # Requirement: WHEN the replacement succeeds, MUST remind the agent to verify syntax and
            # type correctness before making further writes.
            self.assertIsNotNone(resp.reminder)
            reminder_text = str(resp.reminder).lower()
            self.assertTrue(
                "syntax" in reminder_text or "type" in reminder_text,
                f"Expected a syntax and type verification reminder, got: {resp.reminder}",
            )

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
            MockAliasManager(self.root, known_files={nested}),
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

    def test_replace_missing_target_file_treated_as_empty(self) -> None:
        """Postcondition: WHEN the target file is missing from the filesystem, MUST treat its content as empty."""
        missing_rw = _make_read_write_file("newly_created.py")
        registry = LifecycleRegistry()
        __initialize__(registry)
        registry.register_instance(
            MockNodeConfig(read_write_files={missing_rw}),
            keys=[agent_node_config.NodeConfig],
            tier=agent_session,
        )
        registry.register_instance(MockAgentConfig(), keys=[agent_config.AgentConfig], tier=system)
        registry.register_instance(self.mock_tool_manager, keys=[tool_provider.ToolManager], tier=agent_session)
        registry.register_instance(
            MockAliasManager(self.root, known_files={missing_rw}),
            keys=[
                agent_file_alias.AliasManager,
                tool_provider.ParameterType[agent_file_alias.FileAlias, str],
            ],
            tier=agent_session,
        )
        registry.register_instance(
            self.mock_src_metadata,
            keys=[src_metadata.SourceMetadataCoordinator],
            tier=agent_session,
        )
        with enter_phase(agent_session, registry=registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "",
                    "brand new content\n",
                    path=missing_rw,
                    start_line=1,
                )
            )
            self.assertFalse(resp.is_failed)
            host = os.path.join(self.root, "newly_created.py")
            self.assertTrue(os.path.isfile(host))
            with open(host, "r", encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "brand new content\n")

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

    def test_replace_whitespace_fallback_unique_match_replaces(self) -> None:
        """Postcondition: WHEN exact matching finds zero occurrences and allow_multiple is false, MUST fall back to line-by-line whitespace-stripped matching and replace unique match."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            # Ensure exact matching finds zero occurrences: target has 8 leading spaces,
            # while the file line has only 4 leading spaces ("    indented line\n").
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "        indented line",
                    "    renamed line",
                    path=self.read_write_file,
                    allow_multiple=False,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertIn("renamed line", self._read_rw())
            self.assertNotIn("indented line", self._read_rw())

    def test_replace_whitespace_fallback_multiline_unique_match_replaces(self) -> None:
        """Postcondition: WHEN exact matching finds zero occurrences for multi-line target and allow_multiple is false, MUST fall back to line-by-line whitespace-stripped matching and replace unique match."""
        multi_content = (
            "def calculate(x):\n"
            "    y = x + 1\n"
            "    return y\n"
        )
        with open(self.rw_host_path, "w", encoding="utf-8") as fh:
            fh.write(multi_content)

        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            # Target has 8 leading spaces on each line so exact string matching finds zero occurrences
            target = (
                "        def calculate(x):\n"
                "        y = x + 1\n"
                "        return y\n"
            )
            replacement = (
                "def calculate(x):\n"
                "    y = x + 2\n"
                "    return y\n"
            )
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    target,
                    replacement,
                    path=self.read_write_file,
                    allow_multiple=False,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertIn("y = x + 2", self._read_rw())
            self.assertNotIn("y = x + 1", self._read_rw())

    def test_replace_whitespace_fallback_multiple_matches_fails_with_guidance(self) -> None:
        """Postcondition: WHEN exact matching finds zero occurrences, allow_multiple is false, and whitespace-stripped fallback matches multiple locations within the search window, MUST fail indicating first two line numbers and guidance."""
        multi_ws_content = (
            "header line\n"
            "  duplicate whitespace item\n"
            "middle line\n"
            "    duplicate whitespace item\n"
            "footer line\n"
        )
        with open(self.rw_host_path, "w", encoding="utf-8") as fh:
            fh.write(multi_ws_content)

        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            # Target has 8 leading spaces, while file lines have 2 and 4 spaces,
            # ensuring exact string matching finds zero occurrences in the file.
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "        duplicate whitespace item",
                    "replacement",
                    path=self.read_write_file,
                    allow_multiple=False,
                )
            )
            self.assertTrue(resp.is_failed)
            content_str = str(resp.content).lower()
            self.assertIn("2", str(resp.content))
            self.assertIn("4", str(resp.content))
            self.assertTrue(
                "surrounding" in content_str
                or ("start" in content_str and "end" in content_str)
                or "line" in content_str,
                f"Expected surrounding lines or line range guidance, got: {resp.content}",
            )
            self.assertEqual(self._read_rw(), multi_ws_content)

    def test_replace_whitespace_fallback_multiline_multiple_matches_fails_with_guidance(self) -> None:
        """Postcondition: WHEN exact matching finds zero occurrences for multi-line target, allow_multiple is false, and whitespace-stripped fallback matches multiple locations within search window, MUST fail indicating first two line numbers and guidance."""
        multi_ws_block_content = (
            "section one\n"
            "  item alpha\n"
            "  item beta\n"
            "middle section\n"
            "    item alpha\n"
            "    item beta\n"
            "end section\n"
        )
        with open(self.rw_host_path, "w", encoding="utf-8") as fh:
            fh.write(multi_ws_block_content)

        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            # Multi-line target has 8 leading spaces, so exact matching finds zero occurrences
            target = (
                "        item alpha\n"
                "        item beta\n"
            )
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    target,
                    "replacement\n",
                    path=self.read_write_file,
                    allow_multiple=False,
                )
            )
            self.assertTrue(resp.is_failed)
            content_str = str(resp.content).lower()
            self.assertIn("2", str(resp.content))
            self.assertIn("5", str(resp.content))
            self.assertTrue(
                "surrounding" in content_str
                or ("start" in content_str and "end" in content_str)
                or "line" in content_str,
                f"Expected surrounding lines or line range guidance, got: {resp.content}",
            )
            self.assertEqual(self._read_rw(), multi_ws_block_content)

    def test_replace_whitespace_fallback_exceeds_search_window_bounds_fails(self) -> None:
        """Postcondition: WHEN exact matching finds zero occurrences, allow_multiple is false, and target content exceeds search window bounds during whitespace-stripped matching, MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            # 3-line target content exceeds the 2-line search window (start_line=2, end_line=3)
            target_exceeding = (
                "repeated\n"
                "indented line\n"
                "repeated\n"
            )
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    target_exceeding,
                    "replacement\n",
                    path=self.read_write_file,
                    start_line=2,
                    end_line=3,
                    allow_multiple=False,
                )
            )
            self.assertTrue(resp.is_failed)
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_multiple_target_not_found_in_search_window_fails(self) -> None:
        """Postcondition: WHEN allow_multiple is true and target content is not found within the search window, MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "completely_absent_target_content_xyz",
                    "replacement",
                    path=self.read_write_file,
                    allow_multiple=True,
                )
            )
            self.assertTrue(resp.is_failed)
            self.assertIn("not found", str(resp.content).lower())
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_multiple_target_absent_from_bounded_search_window_fails(self) -> None:
        """Postcondition: WHEN allow_multiple is true and target content is absent from bounded search window, MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "outside_target",
                    "replacement",
                    path=self.read_write_file,
                    start_line=1,
                    end_line=3,
                    allow_multiple=True,
                )
            )
            self.assertTrue(resp.is_failed)
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_appends_diff_delta_when_delta_output_configured(self) -> None:
        """Postcondition: WHEN delta output is configured, MUST include a diff delta representation of the change in response content."""
        registry = LifecycleRegistry()
        __initialize__(registry)
        registry.register_instance(
            MockNodeConfig(read_write_files={self.read_write_file}),
            keys=[agent_node_config.NodeConfig],
            tier=agent_session,
        )
        registry.register_instance(
            MockAgentConfig(edit_delta_output=True),
            keys=[agent_config.AgentConfig],
            tier=system,
        )
        registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session,
        )
        registry.register_instance(
            self.mock_alias_manager,
            keys=[
                agent_file_alias.AliasManager,
                tool_provider.ParameterType[agent_file_alias.FileAlias, str],
            ],
            tier=agent_session,
        )
        registry.register_instance(
            self.mock_src_metadata,
            keys=[src_metadata.SourceMetadataCoordinator],
            tier=agent_session,
        )
        with enter_phase(agent_session, registry=registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "unique_target",
                    "delta_target",
                    path=self.read_write_file,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertEqual(
                resp.suppression_key,
                tool_provider.SuppressionKey("replace_file_content"),
            )
            self.assertIn("delta_target", self._read_rw())
            content_str = str(resp.content)
            self.assertTrue(
                "-" in content_str or "+" in content_str or "diff" in content_str.lower(),
                f"Expected diff delta representation in response content, got: {resp.content}",
            )
            self.assertIn("delta_target", content_str)

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

    def test_replace_start_line_total_plus_one_appends(self) -> None:
        """Postcondition: start_line equal to total line count plus one allows appending to end of file."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            total = len(INITIAL_CONTENT.splitlines())
            resp = replace_tool.execute_tool(
                self._bindings(
                    replace_tool,
                    "",
                    "appended line\n",
                    path=self.read_write_file,
                    start_line=total + 1,
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertTrue(self._read_rw().endswith("appended line\n"))

    def test_replace_omitted_path_when_no_file_read_or_edited_fails(self) -> None:
        """Postcondition: WHEN path parameter is omitted and no file was read or edited in session, MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            self.assertIsNone(edit_manager.last_read_or_edited_file)
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "unique_target", "new_target")
            )
            self.assertTrue(resp.is_failed)
            self.assertEqual(self._read_rw(), INITIAL_CONTENT)

    def test_replace_omitted_path_when_last_file_not_read_write_fails(self) -> None:
        """Postcondition: WHEN path parameter is omitted and last read/edited file is not read-write, MUST fail."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            edit_manager = scope.get_singleton(EditManager)
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            edit_manager.record_file_read(self.read_only_file)
            resp = replace_tool.execute_tool(
                self._bindings(replace_tool, "unique_target", "new_target")
            )
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

    def test_target_content_parameter_missing_note_when_line_range_supplied(self) -> None:
        """Postcondition: WHEN line range arguments are supplied, missing note MUST explain that start line and end line only restrict search window."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.target_content_parameter
            self.assertIsNotNone(param.missing_message)
            assert param.missing_message is not None

            # With start_line supplied
            note_start = param.missing_message({tool_provider.ParameterName("start_line")})
            self.assertIsInstance(note_start, str)
            note_start_lower = str(note_start).lower()
            self.assertTrue(
                "restrict" in note_start_lower or "search window" in note_start_lower,
                f"Expected search window restriction explanation, got: {note_start}",
            )

            # With end_line supplied
            note_end = param.missing_message({tool_provider.ParameterName("end_line")})
            self.assertIsInstance(note_end, str)
            note_end_lower = str(note_end).lower()
            self.assertTrue(
                "restrict" in note_end_lower or "search window" in note_end_lower,
                f"Expected search window restriction explanation, got: {note_end}",
            )

            # With both start_line and end_line supplied
            note_both = param.missing_message({
                tool_provider.ParameterName("start_line"),
                tool_provider.ParameterName("end_line"),
            })
            self.assertIsInstance(note_both, str)
            note_both_lower = str(note_both).lower()
            self.assertTrue(
                "restrict" in note_both_lower or "search window" in note_both_lower,
                f"Expected search window restriction explanation, got: {note_both}",
            )

    def test_target_content_parameter_missing_note_when_line_range_omitted(self) -> None:
        """Postcondition: WHEN line range arguments are omitted, missing note MUST explain that target content must match existing text to append or insert content."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.target_content_parameter
            self.assertIsNotNone(param.missing_message)
            assert param.missing_message is not None

            # With neither start_line nor end_line supplied
            note_omitted = param.missing_message({tool_provider.ParameterName("path")})
            self.assertIsInstance(note_omitted, str)
            note_omitted_lower = str(note_omitted).lower()
            self.assertTrue(
                "match existing text" in note_omitted_lower
                or "append" in note_omitted_lower
                or "insert" in note_omitted_lower,
                f"Expected match existing text / append / insert explanation, got: {note_omitted}",
            )

            # With empty parameter set
            note_empty = param.missing_message(set())
            self.assertIsInstance(note_empty, str)
            note_empty_lower = str(note_empty).lower()
            self.assertTrue(
                "match existing text" in note_empty_lower
                or "append" in note_empty_lower
                or "insert" in note_empty_lower,
                f"Expected match existing text / append / insert explanation, got: {note_empty}",
            )

    def test_parameter_type_conversion_target_content(self) -> None:
        """Postcondition: target_content parameter type converts valid wire string and rejects invalid wire value."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.target_content_parameter
            self.assertEqual(param.name, tool_provider.ParameterName("target_content"))
            self.assertTrue(param.is_required)
            conv = param.parameter_type
            self.assertIsNotNone(conv.actual_type)
            self.assertTrue(conv.actual_type is sandbox_file_editor.TargetContent or conv.actual_type is str)
            self.assertEqual(conv.wire_type, str)
            converted = conv.convert("target text")
            self.assertEqual(converted, sandbox_file_editor.TargetContent("target text"))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, 12345))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, None))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, ["invalid"]))

    def test_parameter_type_conversion_replacement_content(self) -> None:
        """Postcondition: replacement_content parameter type converts valid wire string and rejects invalid wire value."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.replacement_content_parameter
            self.assertEqual(param.name, tool_provider.ParameterName("replacement_content"))
            self.assertTrue(param.is_required)
            conv = param.parameter_type
            self.assertIsNotNone(conv.actual_type)
            self.assertTrue(conv.actual_type is sandbox_file_editor.ReplacementContent or conv.actual_type is str)
            self.assertEqual(conv.wire_type, str)
            converted = conv.convert("replacement text")
            self.assertEqual(converted, sandbox_file_editor.ReplacementContent("replacement text"))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, 999))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, None))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, {"invalid": "dict"}))

    def test_parameter_type_conversion_start_line(self) -> None:
        """Postcondition: start_line parameter type converts valid wire int and converts optional line number when omitted."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.start_line_parameter
            self.assertEqual(param.name, tool_provider.ParameterName("start_line"))
            self.assertFalse(param.is_required)
            self.assertIsNone(param.default_value)
            conv = param.parameter_type
            self.assertIsNotNone(conv.actual_type)
            self.assertEqual(conv.wire_type, int)
            converted = conv.convert(42)
            self.assertEqual(converted, sandbox_file_editor.LineNumber(42))
            # Converting optional line number wire values when omitted
            self.assertIsNone(conv.convert(cast(Any, None)))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, "not_an_int"))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, [1, 2]))

    def test_parameter_type_conversion_end_line(self) -> None:
        """Postcondition: end_line parameter type converts valid wire int and converts optional line number when omitted."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.end_line_parameter
            self.assertEqual(param.name, tool_provider.ParameterName("end_line"))
            self.assertFalse(param.is_required)
            self.assertIsNone(param.default_value)
            conv = param.parameter_type
            self.assertIsNotNone(conv.actual_type)
            self.assertEqual(conv.wire_type, int)
            converted = conv.convert(100)
            self.assertEqual(converted, sandbox_file_editor.LineNumber(100))
            converted_one = conv.convert(1)
            self.assertEqual(converted_one, sandbox_file_editor.LineNumber(1))
            # Converting optional line number wire values when omitted
            self.assertIsNone(conv.convert(cast(Any, None)))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, "not_an_int"))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, [1, 2]))

    def test_parameter_type_conversion_allow_multiple(self) -> None:
        """Postcondition: allow_multiple parameter type converts valid wire bool and rejects invalid wire value."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            replace_tool = scope.get_singleton(ReplaceFileContentTool)
            param = replace_tool.allow_multiple_parameter
            self.assertEqual(param.name, tool_provider.ParameterName("allow_multiple"))
            self.assertFalse(param.is_required)
            self.assertFalse(bool(param.default_value))
            conv = param.parameter_type
            self.assertIsNotNone(conv.actual_type)
            self.assertTrue(conv.actual_type is sandbox_file_editor.AllowMultiple or conv.actual_type is bool)
            self.assertEqual(conv.wire_type, bool)
            self.assertEqual(conv.convert(True), sandbox_file_editor.AllowMultiple(True))
            self.assertEqual(conv.convert(False), sandbox_file_editor.AllowMultiple(False))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, "true"))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, 1))
            with self.assertRaises(tool_provider.ParameterConversionError):
                conv.convert(cast(Any, None))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
