"""Tests for SandboxImpl — written from sandbox_impl.md and its dependency closure."""

import os
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch

from sandbox import SandboxConfig, VirtualName
from sandbox_impl import SandboxImpl
from tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolFailure,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    Continue,
)
from dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from dag_storage import NodeMessage


class InitTests(unittest.TestCase):
    """Tests for SandboxImpl.__init__ — from sandbox_impl.md §Data Types."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def test_init_accepts_minimal_config(self):
        config = self._make_config()
        sandbox = SandboxImpl(config)
        self.assertIsNotNone(sandbox)

    def test_init_accepts_diff_size_limit(self):
        config = self._make_config()
        sandbox = SandboxImpl(config, diff_size_limit=2000)
        self.assertIsNotNone(sandbox)

    def test_init_default_diff_size_limit_is_1000(self):
        config = self._make_config()
        sandbox = SandboxImpl(config)
        self.assertEqual(sandbox._diff_size_limit, 1000)

    def test_init_stores_diff_size_limit(self):
        config = self._make_config()
        sandbox = SandboxImpl(config, diff_size_limit=500)
        self.assertEqual(sandbox._diff_size_limit, 500)

    def test_no_state_persists_between_runs(self):
        """Invariant: No state persists between runs."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        # After init, write_occurred should be False
        self.assertFalse(sandbox.get_write_occurred())


class ToolDefinitionsTests(unittest.TestCase):
    """Tests for SandboxImpl.get_tool_definitions — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        """Helper to create a file on disk."""
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_get_tool_definitions_returns_list(self):
        config = self._make_config()
        sandbox = SandboxImpl(config)
        tools = sandbox.get_tool_definitions()
        self.assertIsInstance(tools, list)

    def test_tool_definitions_include_read_file(self):
        config = self._make_config(
            file_mappings={"test.txt": self._write_file("test.txt", "hello")},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("read_file", tool_names)

    def test_tool_definitions_include_edit_file(self):
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("edit_file", tool_names)

    def test_tool_definitions_include_replace_lines(self):
        path = self._write_file("test.txt", "hello\nworld\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("replace_lines", tool_names)

    def test_tool_definitions_include_search_files(self):
        config = self._make_config(
            file_mappings={"test.txt": self._write_file("test.txt", "hello")},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("search_files", tool_names)

    def test_tool_definitions_include_advance(self):
        config = self._make_config()
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("advance", tool_names)

    def test_tool_definitions_include_fail(self):
        config = self._make_config()
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("fail", tool_names)

    def test_blame_tool_included_when_blame_targets_non_empty(self):
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets={"test.txt": "node_1"},
        )
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("blame", tool_names)

    def test_blame_tool_excluded_when_blame_targets_empty(self):
        config = self._make_config()
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertNotIn("blame", tool_names)

    def test_advance_tool_always_emitted(self):
        """The advance tool is always emitted per sandbox_impl.md."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        tool_names = [t["name"] for t in sandbox.get_tool_definitions()]
        self.assertIn("advance", tool_names)



class ReadFileTests(unittest.TestCase):
    """Tests for SandboxImpl.read_file — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        """Helper to create a file on disk."""
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_read_file_returns_content(self):
        """read_file returns the file's entire content as a string in content."""
        path = self._write_file("test.txt", "hello world")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt")
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        assert isinstance(result, ToolResult)
        self.assertEqual(result.content, "hello world")

    def test_read_file_includes_note_with_line_count(self):
        """The result's note reports the file's line count."""
        path = self._write_file("test.txt", "line1\nline2\nline3\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt")
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertIn("3 lines", result.note)

    def test_read_file_non_writable_no_supersedes(self):
        """Read of non-writable file has supersedes=False."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt")
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertFalse(result.supersedes)

    def test_read_file_policy_violation_not_in_readable_paths(self):
        """Policy violation returns ToolFailure when file not in readable_paths."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=[],  # not readable
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt")
        self.assertIsInstance(outcome, ToolFailure)

    def test_read_file_policy_violation_not_in_file_mappings(self):
        """Policy violation returns ToolFailure when file not in file_mappings."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"other.txt": path},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt")
        self.assertIsInstance(outcome, ToolFailure)

    def test_read_file_with_line_numbers_returns_numbered_lines(self):
        """include_line_numbers=True prefixes lines with N │ line."""
        path = self._write_file("test.txt", "hello\nworld\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt", include_line_numbers=True)
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertIn("1 │ hello", result.content)
        self.assertIn("2 │ world", result.content)

    def test_read_file_writable_requires_line_numbers_when_exists(self):
        """Writable file already exists: plain read fails, advises include_line_numbers=True."""
        path = self._write_file("test.txt", "hello\nworld\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt")
        self.assertIsInstance(outcome, ToolFailure)

    def test_read_file_line_numbers_only_for_writable_paths(self):
        """include_line_numbers=True for non-writable file is a parameter error."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("test.txt", include_line_numbers=True)
        self.assertIsInstance(outcome, ToolFailure)

    def test_read_file_unbounded(self):
        """Reads are not paginated and are not bounded by a size limit."""
        content = "x" * 10000
        path = self._write_file("big.txt", content)
        config = self._make_config(
            file_mappings={"big.txt": path},
            readable_paths=["big.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("big.txt")
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertEqual(result.content, content)


class EditFileTests(unittest.TestCase):
    """Tests for SandboxImpl.edit_file — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        """Helper to create a file on disk."""
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_edit_file_replaces_text(self):
        """edit_file replaces old_str with new_str."""
        path = self._write_file("test.txt", "hello world")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "world", "universe")
        assert isinstance(outcome, list)
        # Should have write confirmation + injected read
        self.assertEqual(len(outcome), 2)
        # Verify content was actually changed
        with open(path) as f:
            self.assertEqual(f.read(), "hello universe")

    def test_edit_file_returns_two_results(self):
        """edit_file produces: write confirmation + injected read."""
        path = self._write_file("test.txt", "hello world")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "goodbye")
        assert isinstance(outcome, list)
        self.assertEqual(len(outcome), 2)
        # First is ToolResult (write confirmation)
        first = outcome[0]
        assert isinstance(first, ToolResult)
        self.assertTrue(first.supersedes)
        # Second is PresentedToolResult (injected read)
        second = outcome[1]
        assert isinstance(second, PresentedToolResult)
        self.assertEqual(second.name, "read_file")

    def test_edit_file_sets_write_occurred(self):
        """edit_file sets write_occurred flag to True."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        self.assertFalse(sandbox.get_write_occurred())
        sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertTrue(sandbox.get_write_occurred())

    def test_edit_file_policy_violation_not_in_writable_paths(self):
        """Policy violation returns ToolFailure when file not in writable_paths."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=[],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_policy_violation_not_in_file_mappings(self):
        """Policy violation returns ToolFailure when file not in file_mappings."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"other.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_old_str_absent(self):
        """Returns ToolFailure when old_str not found in file."""
        path = self._write_file("test.txt", "hello world")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "xyz", "abc")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_empty_old_str(self):
        """Returns ToolFailure when old_str is empty."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "", "abc")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_identical_strings(self):
        """Returns ToolFailure when old_str identical to new_str (no-op edit)."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "hello")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_old_str_over_100_chars(self):
        """Returns ToolFailure when old_str exceeds 100 characters."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        long_str = "x" * 101
        outcome = sandbox.edit_file("test.txt", long_str, "abc")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_new_str_over_100_chars(self):
        """Returns ToolFailure when new_str exceeds 100 characters."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        long_str = "y" * 101
        outcome = sandbox.edit_file("test.txt", "hello", long_str)
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_multiple_matches_no_expect_multiple(self):
        """Returns ToolFailure when more than one match and expect_multiple=False."""
        path = self._write_file("test.txt", "hello hello hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_multiple_matches_with_expect_multiple(self):
        """With expect_multiple=True, all occurrences are replaced."""
        path = self._write_file("test.txt", "hello hello hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "goodbye", expect_multiple=True)
        assert isinstance(outcome, list)
        with open(path) as f:
            self.assertEqual(f.read(), "goodbye goodbye goodbye")

    def test_edit_file_file_does_not_exist(self):
        """Returns ToolFailure when file does not exist on disk."""
        config = self._make_config(
            file_mappings={"test.txt": "/nonexistent/path.txt"},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertIsInstance(outcome, ToolFailure)

    def test_edit_file_injected_read_has_line_numbers(self):
        """Injected read after edit shows line-numbered content."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.edit_file("test.txt", "line1", "modified")
        assert isinstance(outcome, list)
        self.assertEqual(len(outcome), 2)
        injected = outcome[1]
        assert isinstance(injected, PresentedToolResult)
        read_result = injected.result
        self.assertIn("1 │ modified", read_result.content)
        self.assertIn("2 │ line2", read_result.content)


class ReplaceLinesTests(unittest.TestCase):
    """Tests for SandboxImpl.replace_lines — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        """Helper to create a file on disk."""
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_replace_lines_replaces_range(self):
        """replace_lines replaces lines start_line through end_line."""
        path = self._write_file("test.txt", "line1\nline2\nline3\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.read_file("test.txt", include_line_numbers=True)
        outcome = sandbox.replace_lines("test.txt", 2, 2, "modified")
        assert isinstance(outcome, list)
        with open(path) as f:
            content = f.read()
        self.assertIn("modified", content)

    def test_replace_lines_sets_write_occurred(self):
        """replace_lines sets write_occurred flag to True."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        self.assertFalse(sandbox.get_write_occurred())
        sandbox.read_file("test.txt", include_line_numbers=True)
        sandbox.replace_lines("test.txt", 1, 1, "modified")
        self.assertTrue(sandbox.get_write_occurred())

    def test_replace_lines_returns_two_results(self):
        """replace_lines produces: write confirmation + injected read."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.read_file("test.txt", include_line_numbers=True)
        outcome = sandbox.replace_lines("test.txt", 1, 1, "modified")
        assert isinstance(outcome, list)
        self.assertEqual(len(outcome), 2)
        first = outcome[0]
        assert isinstance(first, ToolResult)
        self.assertTrue(first.supersedes)
        second = outcome[1]
        assert isinstance(second, PresentedToolResult)

    def test_replace_lines_not_line_numbered_view(self):
        """Returns ToolFailure when file's view is not line-numbered."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.replace_lines("test.txt", 1, 1, "modified")
        self.assertIsInstance(outcome, ToolFailure)

    def test_replace_lines_policy_violation_not_in_writable_paths(self):
        """Policy violation returns ToolFailure when file not in writable_paths."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=[],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.replace_lines("test.txt", 1, 1, "modified")
        self.assertIsInstance(outcome, ToolFailure)

    def test_replace_lines_out_of_bounds(self):
        """Returns ToolFailure when start_line/end_line out of bounds."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.read_file("test.txt", include_line_numbers=True)
        outcome = sandbox.replace_lines("test.txt", 10, 10, "modified")
        self.assertIsInstance(outcome, ToolFailure)

    def test_replace_lines_insert_before_line(self):
        """replace_lines with start_line > end_line inserts before start_line."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.read_file("test.txt", include_line_numbers=True)
        outcome = sandbox.replace_lines("test.txt", 2, 1, "inserted\n")
        assert isinstance(outcome, list)
        with open(path) as f:
            content = f.read()
        self.assertIn("inserted", content)

    def test_replace_lines_delete_range(self):
        """replace_lines with empty new_str deletes the range."""
        path = self._write_file("test.txt", "line1\nline2\nline3\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.read_file("test.txt", include_line_numbers=True)
        outcome = sandbox.replace_lines("test.txt", 2, 2, "")
        assert isinstance(outcome, list)
        with open(path) as f:
            content = f.read()
        self.assertNotIn("line2", content)

    def test_replace_lines_file_does_not_exist(self):
        """Returns ToolFailure when file does not exist on disk."""
        config = self._make_config(
            file_mappings={"test.txt": "/nonexistent/path.txt"},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.replace_lines("test.txt", 1, 1, "modified")
        self.assertIsInstance(outcome, ToolFailure)

    def test_replace_lines_supersedes_nothing_on_failure(self):
        """A replace_lines failure supersedes nothing."""
        path = self._write_file("test.txt", "line1\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.replace_lines("test.txt", 10, 10, "modified")
        self.assertIsInstance(outcome, ToolFailure)


class SearchFilesTests(unittest.TestCase):
    """Tests for SandboxImpl.search_files — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        """Helper to create a file on disk."""
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_search_files_returns_matches(self):
        """search_files returns matches in content."""
        self._write_file("test.txt", "hello world")
        self._write_file("sub/nested.txt", "goodbye world")
        config = self._make_config(
            file_mappings={
                "test.txt": os.path.join(self.tmpdir, "test.txt"),
                "sub/nested.txt": os.path.join(self.tmpdir, "sub", "nested.txt"),
            },
            readable_paths=["test.txt", "sub/nested.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "world")
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertIsInstance(result, ToolResult)
        self.assertIn("world", result.content)

    def test_search_files_not_in_readable_paths(self):
        """Policy violation returns ToolFailure when path not in readable_paths."""
        self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            readable_paths=[],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "hello")
        self.assertIsInstance(outcome, ToolFailure)

    def test_search_files_invalid_pattern(self):
        """Returns ToolFailure for invalid regex pattern."""
        self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "[invalid")
        self.assertIsInstance(outcome, ToolFailure)

    def test_search_files_supersedes_false(self):
        """search_files results have supersedes=False."""
        self._write_file("test.txt", "hello world")
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "world")
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertFalse(result.supersedes)

    def test_search_files_respects_search_result_limit(self):
        """search_files respects the configured search result limit."""
        for i in range(10):
            self._write_file(f"test_{i}.txt", "match here")
        config = self._make_config(
            file_mappings={
                f"test_{i}.txt": os.path.join(self.tmpdir, f"test_{i}.txt")
                for i in range(10)
            },
            readable_paths=[f"test_{i}.txt" for i in range(10)],
            search_result_limit=5,
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "match")
        assert isinstance(outcome, list)

    def test_search_files_with_limit_parameter(self):
        """search_files respects the limit parameter."""
        for i in range(5):
            self._write_file(f"test_{i}.txt", "match here")
        config = self._make_config(
            file_mappings={
                f"test_{i}.txt": os.path.join(self.tmpdir, f"test_{i}.txt")
                for i in range(5)
            },
            readable_paths=[f"test_{i}.txt" for i in range(5)],
            search_result_limit=50,
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "match", limit=2)
        assert isinstance(outcome, list)

    def test_search_files_with_offset_parameter(self):
        """search_files supports offset-based pagination."""
        for i in range(5):
            self._write_file(f"test_{i}.txt", "match here")
        config = self._make_config(
            file_mappings={
                f"test_{i}.txt": os.path.join(self.tmpdir, f"test_{i}.txt")
                for i in range(5)
            },
            readable_paths=[f"test_{i}.txt" for i in range(5)],
            search_result_limit=50,
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "match", offset=2, limit=2)
        assert isinstance(outcome, list)

    def test_search_files_negative_offset(self):
        """Returns ToolFailure when offset is negative."""
        self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "hello", offset=-1)
        self.assertIsInstance(outcome, ToolFailure)

    def test_search_files_zero_limit(self):
        """Returns ToolFailure when limit is zero."""
        self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            readable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "hello", limit=0)
        self.assertIsInstance(outcome, ToolFailure)

    def test_search_files_limit_exceeds_search_result_limit(self):
        """Returns ToolFailure when limit exceeds search_result_limit."""
        self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            readable_paths=["test.txt"],
            search_result_limit=10,
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.search_files("", "hello", limit=20)
        self.assertIsInstance(outcome, ToolFailure)


class GetWriteOccurredTests(unittest.TestCase):
    """Tests for SandboxImpl.get_write_occurred — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_write_occurred_false_initially(self):
        """write_occurred is False when no writes have occurred."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        self.assertFalse(sandbox.get_write_occurred())

    def test_write_occurred_true_after_edit(self):
        """write_occurred becomes True after a successful edit."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertTrue(sandbox.get_write_occurred())

    def test_write_occurred_true_after_replace_lines(self):
        """write_occurred becomes True after a successful replace_lines."""
        path = self._write_file("test.txt", "line1\nline2\n")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.read_file("test.txt", include_line_numbers=True)
        sandbox.replace_lines("test.txt", 1, 1, "modified")
        self.assertTrue(sandbox.get_write_occurred())

    def test_write_occurred_monotonic(self):
        """write_occurred is monotonic: once True, never False."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "hello", "goodbye")
        self.assertTrue(sandbox.get_write_occurred())
        sandbox.edit_file("test.txt", "goodbye", "hello")
        self.assertTrue(sandbox.get_write_occurred())

    def test_write_occurred_false_after_failed_edit(self):
        """write_occurred stays False after a failed edit."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "xyz", "abc")  # won't match
        self.assertFalse(sandbox.get_write_occurred())


class GetSessionStartReadsTests(unittest.TestCase):
    """Tests for SandboxImpl.get_session_start_reads — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_session_start_reads_returns_list(self):
        """get_session_start_reads returns a list of PresentedToolResult."""
        path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={"readme.txt": path},
            readable_paths=["readme.txt"],
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        self.assertIsInstance(reads, list)

    def test_session_start_reads_disabled(self):
        """When session_start_reads_enabled is False, returns empty list."""
        path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={"readme.txt": path},
            readable_paths=["readme.txt"],
            session_start_reads_enabled=False,
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        self.assertEqual(reads, [])

    def test_session_start_reads_sorted_by_virtual_name(self):
        """Session-start reads are sorted by virtual name."""
        self._write_file("z_file.txt", "z")
        self._write_file("a_file.txt", "a")
        self._write_file("m_file.txt", "m")
        config = self._make_config(
            file_mappings={
                "z_file.txt": os.path.join(self.tmpdir, "z_file.txt"),
                "a_file.txt": os.path.join(self.tmpdir, "a_file.txt"),
                "m_file.txt": os.path.join(self.tmpdir, "m_file.txt"),
            },
            readable_paths=["z_file.txt", "a_file.txt", "m_file.txt"],
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        virtual_names = [r.name for r in reads]
        self.assertEqual(virtual_names, sorted(virtual_names))

    def test_session_start_reads_excludes_writable_paths(self):
        """Session-start reads only include files not in writable_paths."""
        path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={"readme.txt": path},
            readable_paths=["readme.txt"],
            writable_paths=["readme.txt"],
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        self.assertEqual(reads, [])

    def test_session_start_reads_each_is_presented_tool_result(self):
        """Each session-start read is a PresentedToolResult."""
        path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={"readme.txt": path},
            readable_paths=["readme.txt"],
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        for read in reads:
            self.assertIsInstance(read, PresentedToolResult)

    def test_session_start_reads_supersedes_unset(self):
        """Session-start read results have supersedes=False."""
        path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={"readme.txt": path},
            readable_paths=["readme.txt"],
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        for read in reads:
            self.assertFalse(read.result.supersedes)

    def test_get_session_start_reads_changes_no_state(self):
        """Requesting session-start reads changes no sandbox state."""
        path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={"readme.txt": path},
            readable_paths=["readme.txt"],
        )
        sandbox = SandboxImpl(config)
        reads1 = sandbox.get_session_start_reads()
        reads2 = sandbox.get_session_start_reads()
        self.assertEqual(len(reads1), len(reads2))

    def test_step_mode_excludes_guide_from_session_start_reads(self):
        """In step mode, the guide is not among session-start reads."""
        guide_path = self._write_file("guide.md", "# Guide: Test\n## Summary\n\nContent")
        readme_path = self._write_file("readme.txt", "hello")
        config = self._make_config(
            file_mappings={
                "guide.md": guide_path,
                "readme.txt": readme_path,
            },
            readable_paths=["guide.md", "readme.txt"],
            guide="guide.md",
        )
        sandbox = SandboxImpl(config)
        reads = sandbox.get_session_start_reads()
        virtual_names = [r.name for r in reads]
        self.assertNotIn("guide.md", virtual_names)



class FailTests(unittest.TestCase):
    """Tests for SandboxImpl.fail — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def test_fail_returns_terminate_agent_with_failure(self):
        """fail returns TerminateAgentWithFailure[str]."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.fail()
        assert isinstance(outcome, TerminateAgentWithFailure)
        self.assertEqual(outcome.value, "Task failed")

    def test_fail_value_is_task_failed(self):
        """fail's failure value is pinned to 'Task failed'."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.fail()
        assert isinstance(outcome, TerminateAgentWithFailure)
        self.assertEqual(outcome.value, "Task failed")

    def test_fail_type_discriminator(self):
        """fail has type discriminator 'terminate_failure'."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.fail()
        assert isinstance(outcome, TerminateAgentWithFailure)
        self.assertEqual(outcome.type, "terminate_failure")


class BlameTests(unittest.TestCase):
    """Tests for SandboxImpl.blame — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_blame_returns_terminate_agent_with_success(self):
        """blame with valid pairs returns TerminateAgentWithSuccess."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
            blame_targets={"test.txt": "node_1"},
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.blame([("test.txt", "Fix the code")])
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)

    def test_blame_carries_feedback_result(self):
        """blame carries FeedbackResult with correct messages."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
            blame_targets={"test.txt": "node_1"},
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.blame([("test.txt", "Fix the code")])
        assert isinstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome.value, FeedbackResult)

    def test_blame_feedback_message_kind(self):
        """blame FeedbackResult messages have kind 'feedback'."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
            blame_targets={"test.txt": "node_1"},
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.blame([("test.txt", "Fix the code")])
        assert isinstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome.value, FeedbackResult)
        messages = outcome.value.messages
        self.assertEqual(len(messages), 1)
        target, msg = messages[0]
        self.assertEqual(target, "node_1")
        self.assertEqual(msg.kind, "feedback")
        self.assertEqual(msg.text, "Fix the code")

    def test_blame_invalid_target_returns_tool_failure(self):
        """blame with invalid target returns ToolFailure."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
            blame_targets={"test.txt": "node_1"},
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.blame([("nonexistent.txt", "Fix the code")])
        self.assertIsInstance(outcome, ToolFailure)

    def test_blame_empty_list_returns_tool_failure(self):
        """blame with empty list returns ToolFailure."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
            blame_targets={"test.txt": "node_1"},
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.blame([])
        self.assertIsInstance(outcome, ToolFailure)

    def test_blame_multiple_targets(self):
        """blame with multiple targets returns multiple feedback messages."""
        path1 = self._write_file("test1.txt", "hello")
        path2 = self._write_file("test2.txt", "world")
        config = self._make_config(
            file_mappings={
                "test1.txt": path1,
                "test2.txt": path2,
            },
            writable_paths=["test1.txt", "test2.txt"],
            blame_targets={"test1.txt": "node_1", "test2.txt": "node_2"},
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.blame([
            ("test1.txt", "Fix test1"),
            ("test2.txt", "Fix test2"),
        ])
        assert isinstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome.value, FeedbackResult)
        self.assertEqual(len(outcome.value.messages), 2)



class AdvanceTests(unittest.TestCase):
    """Tests for SandboxImpl.advance — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)


    def _write_file(self, path, content=""):
        full_path = os.path.join(self.tmpdir, path)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_advance_no_change_no_callback_returns_terminate_success(self):
        """advance with no change and no callback returns TerminateAgentWithSuccess."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)

    def test_advance_no_change_carries_no_change_result(self):
        """advance with no change carries NoChangeResult."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        assert isinstance(outcome, TerminateAgentWithSuccess)
        result = outcome.value
        assert isinstance(result, NoChangeResult)
        config = self._make_config(
            verification_callback=lambda: (True, "All good"),
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)

    def test_advance_with_callback_failing_returns_tool_result(self):
        """advance with a failing verification returns ToolResult with feedback."""
        config = self._make_config(
            verification_callback=lambda: (False, "Tests failed"),
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertIsInstance(result, ToolResult)
        self.assertTrue(result.supersedes)
        self.assertEqual(result.note, "Verification failed.")

    def test_advance_no_callback_treated_as_passed(self):
        """When no callback is configured, verification is treated as passed."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)

    def test_advance_with_change_and_changes_returns_terminate_success(self):
        """advance with changed files and valid changes returns TerminateAgentWithSuccess."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "hello", "goodbye")
        changes = [{"file": "test.txt", "summary": "Changed hello to goodbye"}]
        outcome = sandbox.advance(changes)
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome, TerminateAgentWithSuccess)
        self.assertIsInstance(outcome.value, ChangeResult)

    def test_advance_run_changed_no_changes_return_tool_failure(self):
        """advance with run changed files but no changes returns ToolFailure."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "hello", "goodbye")
        outcome = sandbox.advance()
        self.assertIsInstance(outcome, ToolFailure)

    def test_advance_failing_verification_does_not_terminate(self):
        """advance on failing verification does not terminate; session continues."""
        call_count = [0]
        def failing_callback():
            call_count[0] += 1
            return (False, "Still failing")
        config = self._make_config(
            verification_callback=failing_callback,
        )
        sandbox = SandboxImpl(config)
        outcome1 = sandbox.advance()
        self.assertIsInstance(outcome1, list)
        outcome2 = sandbox.advance()
        self.assertIsInstance(outcome2, list)
        self.assertEqual(call_count[0], 2)

    def test_advance_change_summary_over_soft_bound_rejected(self):
        """A summary over the soft bound (200 chars) is rejected."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "hello", "goodbye")
        long_summary = "x" * 201
        outcome = sandbox.advance([{"file": "test.txt", "summary": long_summary}])
        self.assertIsInstance(outcome, ToolFailure)

    def test_advance_change_summary_over_hard_bound(self):
        """A summary over the hard bound (500 chars) is rejected with hard-bound guidance."""
        path = self._write_file("test.txt", "hello")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
        )
        sandbox = SandboxImpl(config)
        sandbox.edit_file("test.txt", "hello", "goodbye")
        very_long_summary = "x" * 501
        outcome = sandbox.advance([{"file": "test.txt", "summary": very_long_summary}])
        self.assertIsInstance(outcome, ToolFailure)

    def test_advance_entry_missing_file_field(self):
        """An entry with a missing file field returns ToolFailure."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance([{"summary": "no file field"}])
        self.assertIsInstance(outcome, ToolFailure)

    def test_advance_entry_missing_summary_field(self):
        """An entry with a missing summary field returns ToolFailure."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance([{"file": "test.txt"}])
        self.assertIsInstance(outcome, ToolFailure)

    def test_advance_entry_empty_summary(self):
        """An entry with an empty summary returns ToolFailure."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance([{"file": "test.txt", "summary": ""}])
        self.assertIsInstance(outcome, ToolFailure)

    def test_advance_entry_names_file_not_changed(self):
        """An entry naming a file the run did not change returns ToolFailure."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance([{"file": "test.txt", "summary": "changed"}])
        self.assertIsInstance(outcome, ToolFailure)


class TemplateInitializationTests(unittest.TestCase):
    """Tests for template initialization — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def test_template_creates_file_that_does_not_exist(self):
        """When a template file doesn't exist, it's created with template content."""
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            writable_paths=["test.txt"],
            templates={"test.txt": "template content"},
        )
        sandbox = SandboxImpl(config)
        path = os.path.join(self.tmpdir, "test.txt")
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            self.assertEqual(f.read(), "template content")

    def test_template_does_not_modify_existing_file(self):
        """An existing writable file is never modified by its template."""
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w") as f:
            f.write("existing content")
        config = self._make_config(
            file_mappings={"test.txt": path},
            writable_paths=["test.txt"],
            templates={"test.txt": "template content"},
        )
        sandbox = SandboxImpl(config)
        with open(path) as f:
            self.assertEqual(f.read(), "existing content")

    def test_template_initialization_does_not_set_write_occurred(self):
        """Template initialization is not a run write: does not set write_occurred."""
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            writable_paths=["test.txt"],
            templates={"test.txt": "template content"},
        )
        sandbox = SandboxImpl(config)
        self.assertFalse(sandbox.get_write_occurred())

    def test_template_initialization_does_not_record_as_changed(self):
        """Template initialization does not record the file as changed."""
        config = self._make_config(
            file_mappings={"test.txt": os.path.join(self.tmpdir, "test.txt")},
            writable_paths=["test.txt"],
            templates={"test.txt": "template content"},
        )
        sandbox = SandboxImpl(config)
        # advance with no changes should succeed (template init is not a change)
        outcome = sandbox.advance()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)


class StepModeTests(unittest.TestCase):
    """Tests for step mode — from sandbox_impl.md Behavioral Description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_config(self, **overrides):
        defaults = {
            "file_mappings": {},
            "readable_paths": [],
            "writable_paths": [],
            "blame_targets": {},
            "search_result_limit": 50,
        }
        defaults.update(overrides)
        return SandboxConfig(**defaults)

    def _write_file(self, path, content=""):
        full_path = os.path.join(self.tmpdir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return full_path

    def test_step_mode_guide_not_readable(self):
        """In step mode, reading the guide returns ToolFailure."""
        guide_path = self._write_file("guide.md", "# Guide: Test\n## Summary\n\nContent\n## Step 1\n\nDo this")
        config = self._make_config(
            file_mappings={"guide.md": guide_path},
            readable_paths=["guide.md"],
            guide="guide.md",
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.read_file("guide.md")
        self.assertIsInstance(outcome, ToolFailure)

    def test_step_mode_advance_delivers_guide_summary(self):
        """In step mode, advance delivers the guide summary."""
        guide_path = self._write_file("guide.md", "# Guide: Test\n## Summary\n\nGuide content\n## Step 1\n\nDo this")
        config = self._make_config(
            file_mappings={"guide.md": guide_path},
            readable_paths=["guide.md"],
            guide="guide.md",
        )
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        assert isinstance(outcome, list)
        result = outcome[0]
        if isinstance(result, PresentedToolResult):
            result = result.result
        self.assertIsInstance(result, ToolResult)
        self.assertIn("Guide content", result.content)

    def test_step_mode_delivers_step_sections_in_order(self):
        """Step sections are delivered in order after passing verification."""
        guide_path = self._write_file("guide.md", "# Guide: Test\n## Summary\n\nContent\n## Step 1\n\nFirst step\n## Step 2\n\nSecond step")
        config = self._make_config(
            file_mappings={"guide.md": guide_path},
            readable_paths=["guide.md"],
            guide="guide.md",
        )
        sandbox = SandboxImpl(config)
        # First advance: should deliver guide summary + step 1
        outcome1 = sandbox.advance()
        assert isinstance(outcome1, list)
        # Second advance: should deliver step 2
        outcome2 = sandbox.advance()
        assert isinstance(outcome2, list)

    def test_step_mode_no_guide_configured(self):
        """When no guide is configured, advance behaves normally."""
        config = self._make_config()
        sandbox = SandboxImpl(config)
        outcome = sandbox.advance()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)

