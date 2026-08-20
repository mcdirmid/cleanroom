"""
Tests for the SandboxImpl implementation.

Rewritten to match the current implementation and the low-level spec
(specs/sandbox_impl-low.md, specs/sandbox-low.md, specs/tool_provider-low.md,
specs/dag_clean_logic-low.md).

The current API returns a single ToolCallOutcome per tool call: a ToolResult
or a Signal (ToolFailure, TerminateAgentWithSuccess, TerminateAgentWithFailure).
"""

import json
import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from update_with_ai.lib.sandbox import SandboxConfig
from update_with_ai.lib.sandbox_impl import SandboxImpl
from update_with_ai.lib.tool_provider import (
    ToolResult,
    ToolFailure,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
)
from update_with_ai.lib.dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult


class TestSandboxImpl(unittest.TestCase):
    """Main coverage: tools, policy enforcement, stubbing semantics, state."""

    def setUp(self) -> None:
        """Set up a temp workspace with text, python, multi-chunk and empty files."""
        self.temp_dir = tempfile.mkdtemp()

        # Plain text file (81 bytes).
        self.test_file_path = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\n")
            f.write("Line 2: This is a test\n")
            f.write("Line 3: Another line\n")
            f.write("Line 4: Final line\n")

        # Single-chunk python file.
        self.python_file_path = os.path.join(self.temp_dir, "test.py")
        with open(self.python_file_path, "w", encoding="utf-8") as f:
            f.write("class TestClass:\n")
            f.write("    def method_one(self):\n")
            f.write("        return 'one'\n")
            f.write("    def method_two(self):\n")
            f.write("        return 'two'\n")

        # Multi-chunk python file (top-level imports, class, function).
        self.multi_file_path = os.path.join(self.temp_dir, "multi.py")
        with open(self.multi_file_path, "w", encoding="utf-8") as f:
            f.write("import os\n")
            f.write("import sys\n\n")
            f.write("class A:\n")
            f.write("    def __init__(self):\n")
            f.write("        pass\n\n")
            f.write("def func():\n")
            f.write("    return 1\n")

        # Empty python file.
        self.empty_py_path = os.path.join(self.temp_dir, "empty.py")
        with open(self.empty_py_path, "w", encoding="utf-8") as f:
            pass

        # Plain text file WITHOUT a trailing newline (for trailing-newline
        # preservation tests).
        self.plain_file_path = os.path.join(self.temp_dir, "plain.txt")
        with open(self.plain_file_path, "w", encoding="utf-8") as f:
            f.write("a\nb\nc")

        # Creation target: mapped but does not exist until write_file creates
        # it (write_file is creation-only).
        self.new_file_path = os.path.join(self.temp_dir, "new.txt")

        self.file_mappings = {
            "test.txt": self.test_file_path,
            "test.py": self.python_file_path,
            "multi.py": self.multi_file_path,
            "empty.py": self.empty_py_path,
            "plain.txt": self.plain_file_path,
            "new.txt": self.new_file_path,
        }
        self.readable_paths = ["test.txt", "test.py", "multi.py", "empty.py", "plain.txt", "new.txt"]
        self.writable_paths = ["test.txt", "test.py", "multi.py", "empty.py", "plain.txt", "new.txt"]
        self.blame_targets = ["agent", "system"]

        # read_size_limit is comfortably above all the fixture files (81-111
        # bytes) so whole-file reads succeed; tests that exercise the limit
        # build their own SandboxConfig with a small read_size_limit.
        self.config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=1000,
            search_result_limit=5,
            verification_callback=None,
        )
        self.sandbox = SandboxImpl(self.config)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # Outcome narrowing helpers
    # ------------------------------------------------------------------

    def as_tool_result(self, outcome: Any) -> ToolResult:
        assert isinstance(outcome, ToolResult), f"Expected ToolResult, got {outcome!r}"
        return outcome

    def as_tool_failure(self, outcome: Any) -> ToolFailure:
        assert isinstance(outcome, ToolFailure), f"Expected ToolFailure, got {outcome!r}"
        return outcome

    def as_success(self, outcome: Any) -> TerminateAgentWithSuccess:
        assert isinstance(outcome, TerminateAgentWithSuccess), (
            f"Expected TerminateAgentWithSuccess, got {outcome!r}"
        )
        return outcome

    def as_terminate_failure(self, outcome: Any) -> TerminateAgentWithFailure[Any]:
        assert isinstance(outcome, TerminateAgentWithFailure), (
            f"Expected TerminateAgentWithFailure, got {outcome!r}"
        )
        return outcome

    # ------------------------------------------------------------------
    # get_tool_definitions
    # ------------------------------------------------------------------

    def test_get_tool_definitions_always_includes_core_tools(self) -> None:
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        for expected in ("read_file", "write_file", "edit_file", "replace_lines",
                         "search_files", "verify", "succeed", "fail"):
            self.assertIn(expected, names)

    def test_get_tool_definitions_follow_json_schema_shape(self) -> None:
        for definition in self.sandbox.get_tool_definitions():
            self.assertEqual(definition["type"], "function")
            self.assertIn("name", definition["function"])
            self.assertIn("description", definition["function"])
            self.assertIn("parameters", definition["function"])

    def test_replace_lines_definition_advises_reading_with_line_numbers(self) -> None:
        definitions = {d["function"]["name"]: d["function"] for d in self.sandbox.get_tool_definitions()}
        self.assertIn(
            "currently visible in context",
            definitions["replace_lines"]["description"],
        )
        self.assertIn("reads go stale after every edit", definitions["replace_lines"]["description"])
        self.assertIn("1-indexed", definitions["replace_lines"]["description"])
        self.assertIn("start_line", definitions["replace_lines"]["parameters"]["properties"])
        self.assertIn("end_line", definitions["replace_lines"]["parameters"]["properties"])

    def test_read_file_definition_line_numbers_off_by_default(self) -> None:
        definitions = {d["function"]["name"]: d["function"] for d in self.sandbox.get_tool_definitions()}
        read_def = definitions["read_file"]
        props = read_def["parameters"]["properties"]
        self.assertFalse(props["include_line_numbers"]["default"])
        self.assertIn("replace_lines", read_def["parameters"]["properties"]
                      ["include_line_numbers"]["description"])

    def test_read_file_line_numbers_require_writable(self) -> None:
        # Line numbers serve replace_lines edits, so a line-numbered read of a
        # read-only file is an argument error.
        config = SandboxConfig(
            file_mappings={"secret.txt": self.test_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt", "secret.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=1000,
            search_result_limit=5,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        failure = self.as_tool_failure(
            sandbox.read_file("secret.txt", include_line_numbers=True)
        )
        self.assertIn("writable", failure.value)
        # A writable file may be read with line numbers.
        result = self.as_tool_result(
            sandbox.read_file("test.txt", start_line=1, end_line=1, include_line_numbers=True)
        )
        self.assertIn("1 \u2502", result.content)

    def test_get_tool_definitions_chunk_tools_when_python_accessible(self) -> None:
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("read_chunks", names)
        self.assertIn("replace_chunks", names)

    def test_get_tool_definitions_no_chunk_tools_without_readable_python(self) -> None:
        # test.py is mapped but not readable -> no Python files are accessible.
        config = SandboxConfig(
            file_mappings={"test.py": self.python_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertNotIn("read_chunks", names)
        self.assertNotIn("replace_chunks", names)

    def test_get_tool_definitions_no_chunk_tools_without_python_mappings(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertNotIn("read_chunks", names)
        self.assertNotIn("replace_chunks", names)

    def test_get_tool_definitions_verify_always_present(self) -> None:
        # verify is always offered, with or without a verification callback.
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("verify", names)

        def callback() -> Tuple[bool, str]:
            return (True, "ok")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertIn("verify", names)

    def test_get_tool_definitions_blame_conditional(self) -> None:
        # Non-empty blame targets -> blame offered.
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("blame", names)
        blame_def = next(d for d in self.sandbox.get_tool_definitions()
                         if d["function"]["name"] == "blame")
        properties = blame_def["function"]["parameters"]["properties"]
        self.assertIn("blames", properties)
        self.assertIn("target", properties["blames"]["items"]["properties"])
        self.assertIn("feedback", properties["blames"]["items"]["properties"])

        # Empty blame targets -> blame not offered.
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(config).get_tool_definitions()]
        self.assertNotIn("blame", names)

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    def test_read_file_success(self) -> None:
        result = self.as_tool_result(self.sandbox.read_file("test.txt"))
        self.assertEqual(result.content_id, "test.txt")
        self.assertFalse(result.stub_previous)
        self.assertEqual(result.type, "tool_result")
        # Plain lines by default: line numbers are opt-in.
        self.assertIn("Line 1: Hello World", result.content)
        self.assertIn("Line 4: Final line", result.content)
        self.assertNotIn("\u2502", result.content)

    def test_read_file_line_numbered_format(self) -> None:
        result = self.as_tool_result(
            self.sandbox.read_file("test.txt", start_line=1, end_line=2, include_line_numbers=True)
        )
        self.assertEqual(
            result.content,
            "1 \u2502 Line 1: Hello World\n2 \u2502 Line 2: This is a test",
        )
        self.assertIn("2 lines remain", result.note)
        self.assertIn("start_line=3", result.note)

    def test_read_file_no_line_numbers_by_default(self) -> None:
        # include_line_numbers defaults to false; a plain read carries no
        # "N |" prefixes.
        result = self.as_tool_result(
            self.sandbox.read_file("test.txt", start_line=1, end_line=2)
        )
        self.assertEqual(result.content, "Line 1: Hello World\nLine 2: This is a test")

    def test_read_file_range(self) -> None:
        result = self.as_tool_result(
            self.sandbox.read_file("test.txt", start_line=2, end_line=3, include_line_numbers=True)
        )
        self.assertEqual(
            result.content,
            "2 \u2502 Line 2: This is a test\n3 \u2502 Line 3: Another line",
        )

    def test_read_file_omitted_end_line_reads_whole_remaining_file(self) -> None:
        # An omitted end_line means the whole remaining file, allowed when it
        # fits within the read size limit.
        result = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=3))
        self.assertIn("Line 3: Another line", result.content)
        self.assertIn("Line 4: Final line", result.content)
        self.assertIn("0 lines remain", result.note)

    def test_read_file_whole_file_exceeds_read_size_limit_fails(self) -> None:
        # A read whose content would exceed the read size limit fails and the
        # agent must narrow the line range.
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=30,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_file("test.txt"))
        self.assertIn("start_line/end_line", failure.value)
        # A smaller range fits within the limit.
        result = self.as_tool_result(
            SandboxImpl(config).read_file("test.txt", start_line=1, end_line=1)
        )
        self.assertIn("Line 1: Hello World", result.content)

    def test_read_file_policy_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("unknown.txt"))
        # LLS: policy violations signal a tool failure naming the virtual path.
        self.assertIn("unknown.txt", failure.value)

    def test_read_file_policy_not_readable(self) -> None:
        # Map a path that is not readable.
        config = SandboxConfig(
            file_mappings={"secret.txt": self.test_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_file("secret.txt"))
        self.assertIn("secret.txt", failure.value)

    def test_read_file_invalid_start_line(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt", start_line=0))

    def test_read_file_end_line_below_start_line(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt", start_line=3, end_line=2))

    def test_read_file_start_line_beyond_eof(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt", start_line=6))

    def test_read_file_empty_read_at_eof_not_stubbed(self) -> None:
        # A 4-line file; start_line 5 (past the last line) returns empty
        # content and is not stubbed.
        result = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=5))
        self.assertEqual(result.content, "")
        self.assertFalse(result.stub_previous)
        self.assertIn("0 lines remain", result.note)

    def test_read_file_region_overlap_stubs(self) -> None:
        first = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=1, end_line=2))
        self.assertFalse(first.stub_previous)
        self.assertEqual(first.content, "Line 1: Hello World\nLine 2: This is a test")

        # Overlapping line range -> the read STILL returns content; the
        # previous instances of the file's content are stubbed (stub_previous).
        second = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=2, end_line=3))
        self.assertTrue(second.stub_previous)
        self.assertEqual(second.content, "Line 2: This is a test\nLine 3: Another line")

    def test_read_file_non_overlapping_regions_not_stubbed(self) -> None:
        self.as_tool_result(self.sandbox.read_file("test.txt", start_line=1, end_line=1))
        second = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=3, end_line=3))
        self.assertFalse(second.stub_previous)
        self.assertNotIn("Content removed", second.content)

    def test_read_file_every_read_records_its_region(self) -> None:
        # Every read returns content and records its region; an overlapping
        # later read stubs the previous instances (never itself).
        self.as_tool_result(self.sandbox.read_file("test.txt", start_line=1, end_line=2))
        second = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=2, end_line=3))
        self.assertTrue(second.stub_previous)  # overlaps (1,2) -> stub previous
        self.assertEqual(second.content, "Line 2: This is a test\nLine 3: Another line")
        third = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=3, end_line=4))
        # (2,3) was recorded too, so (3,4) overlaps it.
        self.assertTrue(third.stub_previous)
        self.assertEqual(third.content, "Line 3: Another line\nLine 4: Final line")

    # ------------------------------------------------------------------
    # write_file
    # ------------------------------------------------------------------

    def test_write_file_success(self) -> None:
        # write_file is creation-only: it succeeds on a file that does not
        # exist yet.
        result = self.as_tool_result(self.sandbox.write_file("new.txt", "New content"))
        self.assertTrue(result.stub_previous)
        self.assertEqual(result.content_id, "new.txt")
        # Minimal structured result: no file-content echo.
        self.assertEqual(
            json.loads(result.content),
            {"success": True, "message": "File written successfully"},
        )
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.new_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "New content")

    def test_write_file_rejects_existing_file(self) -> None:
        # Modifying an existing file must go through edit_file/replace_lines;
        # write_file is only for creating new files.
        failure = self.as_tool_failure(self.sandbox.write_file("test.txt", "content"))
        self.assertIn("already exists", failure.value)
        self.assertIn("edit_file", failure.value)
        self.assertIn("replace_lines", failure.value)
        self.assertFalse(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Hello World", f.read())

    def test_write_file_empty_content_rejected(self) -> None:
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            original = f.read()
        failure = self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.assertFalse(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), original)

    def test_write_file_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.write_file("unknown.txt", "content"))
        self.assertIn("unknown.txt", failure.value)

    def test_write_file_not_writable(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.py": self.python_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt", "test.py"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).write_file("test.py", "content"))
        self.assertIn("test.py", failure.value)

    def test_write_file_clears_read_region_state(self) -> None:
        self.as_tool_result(self.sandbox.read_file("test.txt", start_line=1, end_line=1))
        self.as_tool_result(self.sandbox.edit_file("test.txt", "Hello World", "brand new"))
        # Stubbing state was cleared -> same region is not stubbed.
        after = self.as_tool_result(self.sandbox.read_file("test.txt", start_line=1, end_line=1))
        self.assertFalse(after.stub_previous)

    def test_write_file_clears_search_dedup_state(self) -> None:
        self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        self.as_tool_result(self.sandbox.edit_file("test.txt", "Hello World", "no matches here"))
        after = self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        self.assertFalse(after.stub_previous)

    def test_write_file_clears_chunk_state(self) -> None:
        self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.as_tool_result(self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "x = 1"}]))
        after = self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.assertFalse(after.stub_previous)

    def test_write_file_creates_missing_directories(self) -> None:
        nested = os.path.join(self.temp_dir, "nested", "sub", "file.txt")
        config = SandboxConfig(
            file_mappings={"nested.txt": nested},
            readable_paths=["nested.txt"],
            writable_paths=["nested.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        result = self.as_tool_result(sandbox.write_file("nested.txt", "Nested content"))
        self.assertTrue(result.stub_previous)
        self.assertTrue(os.path.exists(nested))
        with open(nested, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Nested content")

    # ------------------------------------------------------------------
    # edit_file
    # ------------------------------------------------------------------

    def test_edit_file_replaces_single_occurrence(self) -> None:
        result = self.as_tool_result(
            self.sandbox.edit_file("test.txt", "This is a test", "This is edited")
        )
        self.assertTrue(result.stub_previous)
        self.assertEqual(result.content_id, "test.txt")
        payload = json.loads(result.content)
        self.assertEqual(payload["matches_found"], 1)
        self.assertEqual(payload["message"], "Replaced 1 occurrence")
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: This is edited", f.read())

    def test_edit_file_identical_old_and_new_fails(self) -> None:
        # A no-op edit (old_str == new_str) is an invalid argument: it changes
        # nothing and must not report false progress.
        failure = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "This is a test", "This is a test")
        )
        self.assertIn("identical", failure.value)
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_edit_file_noop_loop_keeps_failing(self) -> None:
        # The run-16 loop: the agent repeatedly re-issues the same no-op edit
        # and re-reads. Each attempt must keep failing (never a false
        # "Replaced 1 occurrence"), so the loop cannot feed on false progress.
        for _ in range(3):
            failure = self.as_tool_failure(
                self.sandbox.edit_file("test.txt", "This is a test", "This is a test")
            )
            self.assertIn("identical", failure.value)
            self.as_tool_result(self.sandbox.read_file("test.txt"))

    def test_edit_file_not_found_fails(self) -> None:
        failure = self.as_tool_failure(self.sandbox.edit_file("test.txt", "zzz", "x"))
        self.assertIn("not found", failure.value)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Hello World", f.read())
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_edit_file_multiple_matches_fail_without_expect_multiple(self) -> None:
        self.as_tool_result(self.sandbox.write_file("new.txt", "x\ny\nx\n"))
        failure = self.as_tool_failure(self.sandbox.edit_file("new.txt", "x", "z"))
        self.assertIn("2 times", failure.value)
        with open(self.new_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "x\ny\nx\n")

    def test_edit_file_expect_multiple_replaces_all(self) -> None:
        self.as_tool_result(self.sandbox.write_file("new.txt", "x\ny\nx\n"))
        result = self.as_tool_result(
            self.sandbox.edit_file("new.txt", "x", "z", expect_multiple=True)
        )
        self.assertEqual(json.loads(result.content)["matches_found"], 2)
        with open(self.new_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "z\ny\nz\n")

    def test_edit_file_empty_old_str_fails(self) -> None:
        failure = self.as_tool_failure(self.sandbox.edit_file("test.txt", "", "x"))
        self.assertIn("non-empty", failure.value)

    def test_edit_file_policy_violation(self) -> None:
        failure = self.as_tool_failure(self.sandbox.edit_file("unknown.txt", "a", "b"))
        self.assertIn("not found in mappings", failure.value)

    # ------------------------------------------------------------------
    # replace_lines
    # ------------------------------------------------------------------

    def test_replace_lines_replaces_range(self) -> None:
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(
            self.sandbox.replace_lines("test.txt", 2, 3, "New middle")
        )
        self.assertTrue(result.stub_previous)
        self.assertEqual(result.content_id, "test.txt")
        payload = json.loads(result.content)
        self.assertEqual(payload["lines_replaced"], 2)
        self.assertEqual(payload["message"], "Replaced lines 2-3")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Line 1: Hello World\nNew middle\nLine 4: Final line\n")

    def test_replace_lines_deletes_range(self) -> None:
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(self.sandbox.replace_lines("test.txt", 2, 3, ""))
        self.assertEqual(json.loads(result.content)["lines_deleted"], 2)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Line 1: Hello World\nLine 4: Final line\n")

    def test_replace_lines_inserts_before_line(self) -> None:
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(self.sandbox.replace_lines("test.txt", 2, 1, "Inserted"))
        payload = json.loads(result.content)
        self.assertEqual(payload["inserted_before"], 2)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(
                f.read(),
                "Line 1: Hello World\nInserted\nLine 2: This is a test\n"
                "Line 3: Another line\nLine 4: Final line\n",
            )

    def test_replace_lines_prepends(self) -> None:
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(self.sandbox.replace_lines("test.txt", 1, 0, "Top"))
        self.assertEqual(json.loads(result.content)["inserted_before"], 1)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(
                f.read(),
                "Top\nLine 1: Hello World\nLine 2: This is a test\n"
                "Line 3: Another line\nLine 4: Final line\n",
            )

    def test_replace_lines_appends(self) -> None:
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(self.sandbox.replace_lines("test.txt", 5, 4, "Bottom"))
        self.assertEqual(json.loads(result.content)["inserted_before"], 5)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(
                f.read(),
                "Line 1: Hello World\nLine 2: This is a test\nLine 3: Another line\n"
                "Line 4: Final line\nBottom\n",
            )

    def test_replace_lines_no_trailing_newline_preserved(self) -> None:
        # plain.txt has no trailing newline ("a\nb\nc"); a replace keeps it.
        self.as_tool_result(
            self.sandbox.read_file("plain.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(self.sandbox.replace_lines("plain.txt", 2, 2, "X"))
        self.assertEqual(json.loads(result.content)["lines_replaced"], 1)
        with open(self.plain_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "a\nX\nc")

    def test_replace_lines_delete_all_lines_empties_file(self) -> None:
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(self.sandbox.replace_lines("test.txt", 1, 4, ""))
        self.assertEqual(json.loads(result.content)["lines_deleted"], 4)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "")

    def test_replace_lines_requires_visible_range(self) -> None:
        # replace_lines may edit only line ranges currently visible in context
        # (read with line numbers since the last write).
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 1, 1, "x")
        )
        self.assertIn("not currently visible in context", failure.value)
        self.assertIn("include_line_numbers=true", failure.value)

        # Reading lines 1-2 makes exactly that range editable.
        self.as_tool_result(
            self.sandbox.read_file("test.txt", start_line=1, end_line=2,
                                   include_line_numbers=True)
        )
        result = self.as_tool_result(
            self.sandbox.replace_lines("test.txt", 1, 2, "new first line")
        )
        self.assertEqual(json.loads(result.content)["lines_replaced"], 2)

    def test_replace_lines_plain_read_does_not_count(self) -> None:
        # Only line-numbered reads make a range visible to replace_lines.
        self.as_tool_result(self.sandbox.read_file("test.txt"))
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 1, 1, "x")
        )
        self.assertIn("not currently visible in context", failure.value)

    def test_read_file_plain_after_numbered_fails(self) -> None:
        # Sticky line-number mode: once a file is read with line numbers, a
        # plain read of it is a hard tool failure — never a stub.
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt"))
        self.assertIn("include_line_numbers=true", failure.value)

    def test_read_file_plain_after_numbered_fails_ever(self) -> None:
        # The plain-read ban persists across writes (it is not cleared by a
        # write, unlike visibility).
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "changed"))
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt"))
        self.assertIn("include_line_numbers=true", failure.value)
        # A numbered read still works after the write.
        result = self.as_tool_result(
            self.sandbox.read_file("test.txt", start_line=1, end_line=1,
                                   include_line_numbers=True)
        )
        self.assertEqual(result.type, "tool_result")

    def test_numbered_read_not_stubbed_by_plain_read(self) -> None:
        # A plain read of a range must not block the numbered view of the same
        # range: numbered reads are stubbed only by numbered reads, so the
        # line-numbered content (and thus replace_lines visibility) stays
        # obtainable after a plain read.
        self.as_tool_result(self.sandbox.read_file("test.txt"))
        result = self.as_tool_result(
            self.sandbox.read_file("test.txt", start_line=1, end_line=2,
                                   include_line_numbers=True)
        )
        self.assertFalse(result.stub_previous)
        self.assertIn("1 \u2502 Line 1: Hello World", result.content)
        # The numbered read made the range visible for line edits.
        edited = self.as_tool_result(
            self.sandbox.replace_lines("test.txt", 1, 2, "replaced")
        )
        self.assertEqual(json.loads(edited.content)["lines_replaced"], 2)

    def test_replace_lines_visibility_cleared_by_write(self) -> None:
        # Any write clears what is visible; replace_lines then fails until a
        # fresh numbered read.
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "Changed"))
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 2, 2, "x")
        )
        self.assertIn("not currently visible in context", failure.value)
        # A fresh numbered read unblocks replace_lines.
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        result = self.as_tool_result(
            self.sandbox.replace_lines("test.txt", 2, 2, "New line")
        )
        self.assertEqual(json.loads(result.content)["lines_replaced"], 1)

    def test_replace_lines_validation_fails(self) -> None:
        # start_line out of range (file has 4 lines; max start is 5).
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        failure = self.as_tool_failure(self.sandbox.replace_lines("test.txt", 6, 5, "x"))
        self.assertIn("start_line", failure.value)
        # end_line out of range.
        failure = self.as_tool_failure(self.sandbox.replace_lines("test.txt", 1, 5, "x"))
        self.assertIn("end_line", failure.value)
        # end_line negative.
        failure = self.as_tool_failure(self.sandbox.replace_lines("test.txt", 1, -1, "x"))
        self.assertIn("end_line", failure.value)
        # Non-integer line numbers.
        failure = self.as_tool_failure(self.sandbox.replace_lines("test.txt", "a", 1, "x"))
        self.assertIn("integers", failure.value)
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Hello World", f.read())

    # ------------------------------------------------------------------
    # search_files
    # ------------------------------------------------------------------

    def test_search_files_success(self) -> None:
        result = self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        self.assertEqual(result.content_id, "test.txt")
        self.assertFalse(result.stub_previous)
        self.assertIn("Hello", result.content)
        self.assertIn("1:", result.content)

    def test_search_files_dedup_by_path_and_pattern(self) -> None:
        first = self.as_tool_result(self.sandbox.search_files("test.txt", "test"))
        self.assertFalse(first.stub_previous)
        second = self.as_tool_result(self.sandbox.search_files("test.txt", "test"))
        # The search still returns results; the previous instances are stubbed.
        self.assertTrue(second.stub_previous)
        self.assertNotIn("Content removed", second.content)
        self.assertIn("matches total", second.note)

    def test_search_files_different_pattern_not_stubbed(self) -> None:
        self.as_tool_result(self.sandbox.search_files("test.txt", "Hello"))
        second = self.as_tool_result(self.sandbox.search_files("test.txt", "World"))
        self.assertFalse(second.stub_previous)

    def test_search_files_different_path_not_stubbed(self) -> None:
        self.as_tool_result(self.sandbox.search_files("test.txt", "test"))
        second = self.as_tool_result(self.sandbox.search_files("test.py", "Test"))
        self.assertFalse(second.stub_previous)

    def test_search_files_invalid_pattern(self) -> None:
        failure = self.as_tool_failure(self.sandbox.search_files("test.txt", "[invalid"))

    def test_search_files_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.search_files("unknown.txt", "x"))
        self.assertIn("unknown.txt", failure.value)

    def test_search_files_not_readable(self) -> None:
        config = SandboxConfig(
            file_mappings={"secret.txt": self.test_file_path, "test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).search_files("secret.txt", "x"))
        self.assertIn("secret.txt", failure.value)

    def test_search_files_recursive_in_directory(self) -> None:
        src_dir = os.path.join(self.temp_dir, "src")
        os.makedirs(os.path.join(src_dir, "sub"))
        with open(os.path.join(src_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("needle here\n")
        with open(os.path.join(src_dir, "sub", "b.txt"), "w", encoding="utf-8") as f:
            f.write("another needle\n")
        config = SandboxConfig(
            file_mappings={"src": src_dir},
            readable_paths=["src"],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.as_tool_result(SandboxImpl(config).search_files("src", "needle"))
        self.assertIn("a.py:1:", result.content)
        self.assertIn("sub/b.txt:1:", result.content)

    def test_search_files_omitted_limit_fails_when_matches_exceed_limit(self) -> None:
        # An omitted limit returns all matches; when that exceeds the search
        # result limit the tool fails and the agent must page with offset/limit.
        many_path = os.path.join(self.temp_dir, "many.txt")
        with open(many_path, "w", encoding="utf-8") as f:
            for i in range(20):
                f.write(f"Match {i}\n")
        config = SandboxConfig(
            file_mappings={"many.txt": many_path},
            readable_paths=["many.txt"],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).search_files("many.txt", "Match"))
        self.assertIn("specify offset/limit", failure.value)

    def test_search_files_pagination_with_limit_and_offset(self) -> None:
        many_path = os.path.join(self.temp_dir, "many.txt")
        with open(many_path, "w", encoding="utf-8") as f:
            for i in range(20):
                f.write(f"Match {i}\n")
        config = SandboxConfig(
            file_mappings={"many.txt": many_path},
            readable_paths=["many.txt"],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        first = self.as_tool_result(sandbox.search_files("many.txt", "Match", limit=5))
        lines = [line for line in first.content.split("\n") if line.strip()]
        self.assertEqual(len(lines), 5)
        self.assertIn("20 matches total", first.note)
        self.assertIn("15 more after this page", first.note)
        self.assertIn("offset=5", first.note)

        # Paging with a new offset is a distinct search, not stubbed.
        second = self.as_tool_result(
            sandbox.search_files("many.txt", "Match", offset=5, limit=5)
        )
        self.assertFalse(second.stub_previous)
        self.assertIn("10 more after this page", second.note)

    def test_search_files_explicit_limit_above_max_fails(self) -> None:
        many_path = os.path.join(self.temp_dir, "many.txt")
        with open(many_path, "w", encoding="utf-8") as f:
            for i in range(20):
                f.write(f"Match {i}\n")
        config = SandboxConfig(
            file_mappings={"many.txt": many_path},
            readable_paths=["many.txt"],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(
            SandboxImpl(config).search_files("many.txt", "Match", limit=10)
        )
        self.assertIn("search result limit", failure.value)

    # ------------------------------------------------------------------
    # read_chunks
    # ------------------------------------------------------------------

    def test_read_chunks_none_returns_all_chunks(self) -> None:
        result = self.as_tool_result(self.sandbox.read_chunks("test.py"))
        self.assertEqual(result.content_id, "test.py")
        self.assertFalse(result.stub_previous)
        self.assertIn("class TestClass", result.content)
        self.assertIn("def method_one", result.content)
        # The result reminds the agent how many chunks remain.
        self.assertIn("chunks remain", result.note)

    def test_read_chunks_specific_indices(self) -> None:
        result = self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.assertIn("class TestClass", result.content)

    def test_read_chunks_omitted_indices_fails_when_all_exceed_max(self) -> None:
        # Omitted chunk_indices means all chunks; when their total content
        # exceeds the read size limit the tool fails and the agent must
        # paginate with explicit chunk_indices.
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_chunks("multi.py"))
        self.assertIn("specify chunk_indices", failure.value)

    def test_read_chunks_explicit_indices_fail_when_exceed_max(self) -> None:
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(
            SandboxImpl(config).read_chunks("multi.py", chunk_indices=[0, 1, 2, 3])
        )
        self.assertIn("specify fewer chunk indices", failure.value)

    def test_read_chunks_include_adjacent(self) -> None:
        # Request chunk 1 with adjacent context: returned = requested + adjacent.
        result = self.as_tool_result(
            self.sandbox.read_chunks("multi.py", chunk_indices=[1], include_adjacent=True)
        )
        # Chunks 0, 1 and 2 are all returned (the content is the LLS contract;
        # the "--- Chunk N ---" header format is unspecified).
        self.assertIn("import os", result.content)
        self.assertIn("class A:", result.content)

    def test_read_chunks_non_python_file_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_chunks("test.txt"))
        self.assertIn("test.txt", failure.value)

    def test_read_chunks_negative_index_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_chunks("test.py", chunk_indices=[-1]))

    def test_read_chunks_out_of_range_index_rejected(self) -> None:
        # Per the sandbox LLS, requested chunk indices must be valid
        # non-negative indices; an out-of-range index is a parameter error
        # (it is not silently dropped).
        failure = self.as_tool_failure(self.sandbox.read_chunks("test.py", chunk_indices=[999]))

    def test_read_chunks_not_accessible(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_chunks("test.txt"))

    def test_read_chunks_not_readable(self) -> None:
        # a.py readable (python accessible), b.py mapped but not readable.
        a_path = os.path.join(self.temp_dir, "a.py")
        b_path = os.path.join(self.temp_dir, "b.py")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write("y = 2\n")
        config = SandboxConfig(
            file_mappings={"a.py": a_path, "b.py": b_path},
            readable_paths=["a.py"],
            writable_paths=["a.py"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_chunks("b.py"))
        self.assertIn("b.py", failure.value)

    def test_read_chunks_overlapping_indices_stub(self) -> None:
        first = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[0]))
        self.assertFalse(first.stub_previous)
        second = self.as_tool_result(
            self.sandbox.read_chunks("multi.py", chunk_indices=[0, 1])
        )
        # The read still returns content; the previous instances are stubbed.
        self.assertTrue(second.stub_previous)
        self.assertIn("--- Chunk 0 ---", second.content)

    def test_read_chunks_disjoint_indices_not_stubbed(self) -> None:
        first = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[0]))
        self.assertFalse(first.stub_previous)
        second = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[3]))
        self.assertFalse(second.stub_previous)

    def test_read_chunks_adjacent_context_counts_for_stubbing(self) -> None:
        # include_adjacent makes chunks 0,1,2 the returned set; a later read of
        # chunk 2 overlaps that set -> stubbed.
        self.as_tool_result(
            self.sandbox.read_chunks("multi.py", chunk_indices=[1], include_adjacent=True)
        )
        later = self.as_tool_result(self.sandbox.read_chunks("multi.py", chunk_indices=[2]))
        self.assertTrue(later.stub_previous)

        # Without adjacent context, chunk 1 alone does not pre-cover chunk 2.
        # Use a fresh sandbox so state from the adjacent read above does not
        # leak into this assertion.
        fresh = SandboxImpl(self.config)
        self.as_tool_result(fresh.read_chunks("multi.py", chunk_indices=[1]))
        later2 = self.as_tool_result(fresh.read_chunks("multi.py", chunk_indices=[2]))
        self.assertFalse(later2.stub_previous)

    def test_read_chunks_empty_file(self) -> None:
        result = self.as_tool_result(self.sandbox.read_chunks("empty.py"))
        self.assertEqual(result.content, "")
        self.assertFalse(result.stub_previous)

    # ------------------------------------------------------------------
    # replace_chunks
    # ------------------------------------------------------------------

    def test_replace_chunks_success(self) -> None:
        result = self.as_tool_result(
            self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "class NewClass:"}])
        )
        self.assertTrue(result.stub_previous)
        self.assertEqual(result.content_id, "test.py")
        self.assertEqual(json.loads(result.content)["chunks_replaced"], 1)
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            self.assertIn("class NewClass:", f.read())

    def test_replace_chunks_atomic_all_or_nothing(self) -> None:
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            original = f.read()
        replacements = [
            {"index": 0, "new_content": "class NewClass:"},
            {"index": 99, "new_content": "out of range"},
        ]
        failure = self.as_tool_failure(self.sandbox.replace_chunks("test.py", replacements))
        # Nothing was applied and no write occurred.
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), original)
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_replace_chunks_empty_replacements_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.replace_chunks("test.py", []))

    def test_replace_chunks_missing_key_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": 0}])
        )

    def test_replace_chunks_non_integer_index_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": "0", "new_content": "x"}])
        )

    def test_replace_chunks_negative_index_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": -1, "new_content": "x"}])
        )

    def test_replace_chunks_non_python_file_rejected(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.replace_chunks("test.txt", [{"index": 0, "new_content": "x"}])
        )
        self.assertIn("test.txt", failure.value)

    def test_replace_chunks_not_writable(self) -> None:
        config = SandboxConfig(
            file_mappings={"a.py": self.python_file_path, "test.txt": self.test_file_path},
            readable_paths=["a.py", "test.txt"],
            writable_paths=["test.txt"],
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(
            SandboxImpl(config).replace_chunks("a.py", [{"index": 0, "new_content": "x"}])
        )
        self.assertIn("a.py", failure.value)

    def test_replace_chunks_clears_stubbing_state(self) -> None:
        self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.as_tool_result(
            self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "class NewClass:"}])
        )
        after = self.as_tool_result(self.sandbox.read_chunks("test.py", chunk_indices=[0]))
        self.assertFalse(after.stub_previous)

    # ------------------------------------------------------------------
    # verify
    # ------------------------------------------------------------------

    def test_verify_no_callback_reports_no_changes(self) -> None:
        result = self.as_tool_result(self.sandbox.verify())
        self.assertEqual(result.content_id, "verify")
        self.assertTrue(result.stub_previous)
        self.assertIn("No files were changed", result.content)
        self.assertIn("No verification tool is configured", result.content)
        self.assertIn("succeed() may now be called", result.content)

    def test_verify_no_callback_reports_diff_after_write(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "New content"))
        result = self.as_tool_result(self.sandbox.verify())
        self.assertEqual(result.content_id, "verify")
        self.assertIn("### diff for test.txt", result.content)
        self.assertIn("-Line 2: This is a test", result.content)
        self.assertIn("+Line 2: New content", result.content)
        self.assertIn("No verification tool is configured", result.content)
        self.assertIn("succeed() may now be called", result.content)

    def test_verify_success(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (True, "Verification passed")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        result = self.as_tool_result(SandboxImpl(config).verify())
        # The diff is reported either way; the callback output is appended,
        # followed by the succeed() guidance.
        self.assertIn("No files were changed in this run.", result.content)
        self.assertIn("Verification passed", result.content)
        self.assertIn("succeed() may now be called", result.content)
        self.assertEqual(result.content_id, "verify")
        self.assertTrue(result.stub_previous)

    def test_verify_with_callback_includes_diff_after_write(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (True, "Verification passed")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        sandbox = SandboxImpl(config)
        self.as_tool_result(sandbox.edit_file("test.txt", "This is a test", "New content"))
        result = self.as_tool_result(sandbox.verify())
        self.assertIn("### diff for test.txt", result.content)
        self.assertIn("-Line 2: This is a test", result.content)
        self.assertIn("+Line 2: New content", result.content)
        self.assertIn("Verification passed", result.content)
        self.assertIn("succeed() may now be called", result.content)

    def test_verify_failure_records_failed_state(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (False, "lint errors found")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        result = self.as_tool_result(SandboxImpl(config).verify())
        self.assertIn("lint errors found", result.content)
        self.assertIn("Verification failed", result.content)
        self.assertIn("changing files", result.content)
        self.assertIn("verify() again", result.content)
        self.assertIn("blame() or fail()", result.content)

    def test_verify_diff_truncated_when_large(self) -> None:
        # A diff exceeding the diff size limit is truncated with a footer
        # reporting the truncated size and full change counts.
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=1000,
            search_result_limit=5,
            diff_size_limit=50,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        self.as_tool_result(sandbox.write_file("new.txt", "A" * 200 + "\n" + "B" * 200 + "\n"))
        result = self.as_tool_result(sandbox.verify())
        self.assertIn("... diff truncated", result.content)
        self.assertIn("50 of", result.content)
        self.assertIn("file(s), +", result.content)
        self.assertIn("Raise diff_size_limit", result.content)

    def test_verify_diff_size_limit_default(self) -> None:
        # diff_size_limit defaults to 1000 chars when not configured.
        sandbox = SandboxImpl(self.config)  # no diff_size_limit set
        big = ("line %d\n" * 300) % tuple(range(300))  # ~2100 chars, > 1000
        self.as_tool_result(sandbox.write_file("new.txt", big))
        result = self.as_tool_result(sandbox.verify())
        self.assertIn("... diff truncated", result.content)
        self.assertIn("1000 of", result.content)

    def test_verify_callback_exception(self) -> None:
        def callback() -> Tuple[bool, str]:
            raise ValueError("boom")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )
        failure = self.as_tool_failure(SandboxImpl(config).verify())
        # LLS (implementation spec): verification-callback exceptions signal a
        # tool failure; the exact wording is unspecified.

    # ------------------------------------------------------------------
    # succeed / fail
    # ------------------------------------------------------------------

    def _changes(self, *summaries: str) -> List[Dict[str, str]]:
        return [{"file": "test.txt", "summary": s} for s in summaries]

    def test_succeed_no_change_when_no_write(self) -> None:
        success = self.as_success(self.sandbox.succeed())
        self.assertEqual(success.type, "terminate_success")
        self.assertIsInstance(success.value, NoChangeResult)
        assert isinstance(success.value, NoChangeResult)
        self.assertEqual(success.value.type, "no_change")

    def test_succeed_change_result_when_write_occurred(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "updated"))
        self.as_tool_result(self.sandbox.verify())
        success = self.as_success(
            self.sandbox.succeed(self._changes("Rewrote the file content"))
        )
        self.assertIsInstance(success.value, ChangeResult)
        assert isinstance(success.value, ChangeResult)
        self.assertEqual(success.value.type, "change")
        # The per-file change summary is carried and broadcast to reverse deps.
        self.assertEqual(success.value.messages, ["test.txt: Rewrote the file content"])

    def test_succeed_bare_after_write_lists_changed_files(self) -> None:
        # sandbox LLS: when the run changed files, succeed() without changes
        # fails, listing the changed files and asking for the {file, summary}
        # shape.
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "updated"))
        self.as_tool_result(self.sandbox.verify())
        failure = self.as_tool_failure(self.sandbox.succeed())
        self.assertIn("test.txt", failure.value)
        self.assertIn("changes", failure.value)

    def test_succeed_bare_with_no_changes_is_no_change(self) -> None:
        # No files changed: succeed() without changes is a no-change result.
        success = self.as_success(self.sandbox.succeed())
        self.assertIsInstance(success.value, NoChangeResult)

    def test_succeed_bare_after_replace_chunks_lists_changed_file(self) -> None:
        # replace_chunks also records its file as changed.
        self.as_tool_result(self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "x"}]))
        self.as_tool_result(self.sandbox.verify())
        failure = self.as_tool_failure(self.sandbox.succeed())
        self.assertIn("test.py", failure.value)
        self.assertIn("changes", failure.value)

    def test_succeed_unknown_file_in_changes_fails(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "updated"))
        self.as_tool_result(self.sandbox.verify())
        failure = self.as_tool_failure(
            self.sandbox.succeed([{"file": "other.txt", "summary": "changed"}])
        )
        self.assertIn("other.txt", failure.value)
        self.assertIn("test.txt", failure.value)

    def test_succeed_overlong_summary_fails(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "updated"))
        self.as_tool_result(self.sandbox.verify())
        long_summary = "x" * (SandboxImpl.MAX_CHANGE_SUMMARY_LENGTH + 1)
        failure = self.as_tool_failure(self.sandbox.succeed(self._changes(long_summary)))
        self.assertIn("test.txt", failure.value)
        self.assertIn("chars", failure.value)

    def test_succeed_missing_changed_file_fails(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "updated"))
        self.as_tool_result(self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "updated"}]))
        self.as_tool_result(self.sandbox.verify())
        failure = self.as_tool_failure(self.sandbox.succeed(self._changes("Rewrote the file")))
        self.assertIn("test.py", failure.value)
        self.assertIn("covered", failure.value)

    def test_succeed_fabricated_change_rejected(self) -> None:
        # A claimed change must appear in the diff: rewriting a file with
        # byte-identical content is not a change, and reporting it as changed
        # is a fabricated summary.
        self.as_tool_result(
            self.sandbox.read_file("test.txt", include_line_numbers=True)
        )
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            original = f.read()
        lines = original.splitlines()
        self.as_tool_result(
            self.sandbox.replace_lines("test.txt", 1, len(lines), "\n".join(lines))
        )
        self.as_tool_result(self.sandbox.verify())
        failure = self.as_tool_failure(
            self.sandbox.succeed(self._changes("Rewrote the file"))
        )
        self.assertIn("does not appear in the diff", failure.value)
        self.assertIn("unchanged", failure.value)
        # After a real change, the same summary is accepted.
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "changed"))
        self.as_tool_result(self.sandbox.verify())
        success = self.as_success(self.sandbox.succeed(self._changes("Rewrote the file")))
        self.assertIsInstance(success.value, ChangeResult)

    def test_succeed_after_failed_write_is_no_change(self) -> None:
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        success = self.as_success(self.sandbox.succeed())
        self.assertIsInstance(success.value, NoChangeResult)

    def test_fail(self) -> None:
        failure = self.as_terminate_failure(self.sandbox.fail())
        self.assertEqual(failure.type, "terminate_failure")
        # LLS: the failure termination carries a str value describing the
        # failure; the exact wording is unspecified.
        self.assertIsInstance(failure.value, str)

    # ------------------------------------------------------------------
    # succeed verification gate
    # ------------------------------------------------------------------

    def _verified_config(self, outcome: Tuple[bool, str]) -> SandboxConfig:
        def callback() -> Tuple[bool, str]:
            return outcome

        return SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=callback,
        )

    def test_succeed_blocked_when_verify_not_called(self) -> None:
        # sandbox LLS: with a verification callback configured, succeed is
        # gated on verify() having been called and passed.
        sandbox = SandboxImpl(self._verified_config((True, "ok")))
        failure = self.as_tool_failure(sandbox.succeed(self._changes("ok")))
        self.assertIn("has not been called", failure.value)
        self.assertIn("verify()", failure.value)

    def test_succeed_blocked_when_files_changed_and_verify_not_called(self) -> None:
        # No callback configured: succeed is gated on verify() having been
        # called when the run changed files.
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "New content"))
        failure = self.as_tool_failure(self.sandbox.succeed(self._changes("ok")))
        self.assertIn("has not been called", failure.value)
        self.assertIn("verify()", failure.value)

    def test_succeed_allowed_after_no_callback_verify(self) -> None:
        # No callback configured: verify() must be called after a write, then
        # succeed() proceeds to the change-summary gate.
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "New content"))
        self.as_tool_result(self.sandbox.verify())
        success = self.as_success(self.sandbox.succeed(self._changes("ok")))
        self.assertIsInstance(success.value, ChangeResult)

    def test_succeed_blocked_when_last_verify_failed(self) -> None:
        sandbox = SandboxImpl(self._verified_config((False, "lint errors")))
        self.as_tool_result(sandbox.verify())
        failure = self.as_tool_failure(sandbox.succeed(self._changes("ok")))
        self.assertIn("failed", failure.value)
        self.assertIn("verify()", failure.value)

    def test_succeed_allowed_after_verify_passes(self) -> None:
        sandbox = SandboxImpl(self._verified_config((True, "ok")))
        self.as_tool_result(sandbox.verify())
        success = self.as_success(sandbox.succeed(self._changes("ok")))
        self.assertIsInstance(success.value, NoChangeResult)

    def test_fail_allowed_even_when_verify_gate_blocked(self) -> None:
        # Termination failure tools are never gated by verification.
        sandbox = SandboxImpl(self._verified_config((False, "lint errors")))
        failure = self.as_terminate_failure(sandbox.fail())
        self.assertEqual(failure.type, "terminate_failure")

    # ------------------------------------------------------------------
    # blame
    # ------------------------------------------------------------------

    def test_blame_no_targets_configured(self) -> None:
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=[],
            read_size_limit=20,
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).blame([("agent", "fix")]))

    def test_blame_empty_list(self) -> None:
        failure = self.as_tool_failure(self.sandbox.blame([]))

    def test_blame_invalid_target(self) -> None:
        failure = self.as_tool_failure(self.sandbox.blame([("bogus", "fix it")]))
        # LLS: the failure identifies the invalid pair (the target name).
        self.assertIn("bogus", failure.value)

    def test_blame_mixed_valid_and_invalid_targets(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.blame([("agent", "good"), ("bogus", "bad")])
        )
        self.assertIn("bogus", failure.value)

    def test_blame_valid_pairs(self) -> None:
        blames: List[Tuple[str, str]] = [
            ("agent", "Fix the agent output"),
            ("system", "Fix the system output"),
        ]
        success = self.as_success(self.sandbox.blame(blames))
        self.assertIsInstance(success.value, FeedbackResult)
        assert isinstance(success.value, FeedbackResult)
        self.assertEqual(success.value.type, "feedback")
        self.assertEqual(success.value.messages, blames)

    # ------------------------------------------------------------------
    # get_write_occurred
    # ------------------------------------------------------------------

    def test_get_write_occurred_initial_false(self) -> None:
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_get_write_occurred_true_after_write(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "content"))
        self.assertTrue(self.sandbox.get_write_occurred())

    def test_get_write_occurred_true_after_replace_chunks(self) -> None:
        self.as_tool_result(
            self.sandbox.replace_chunks("test.py", [{"index": 0, "new_content": "class NewClass:"}])
        )
        self.assertTrue(self.sandbox.get_write_occurred())

    def test_get_write_occurred_monotonic(self) -> None:
        self.as_tool_result(self.sandbox.edit_file("test.txt", "This is a test", "content"))
        # A later failed write does not clear the flag.
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.assertTrue(self.sandbox.get_write_occurred())

    def test_get_write_occurred_false_after_failed_write(self) -> None:
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.assertFalse(self.sandbox.get_write_occurred())

    # ------------------------------------------------------------------
    # State / invariants
    # ------------------------------------------------------------------

    def test_no_state_persists_between_runs(self) -> None:
        # A fresh instance has no stubbing state even with identical config.
        self.as_tool_result(self.sandbox.read_file("test.txt", start_line=1, end_line=1))
        fresh = SandboxImpl(self.config)
        result = self.as_tool_result(fresh.read_file("test.txt", start_line=1, end_line=1))
        self.assertFalse(result.stub_previous)
        self.assertFalse(fresh.get_write_occurred())

    def test_errors_leave_filesystem_unchanged(self) -> None:
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            test_txt = f.read()
        with open(self.python_file_path, "r", encoding="utf-8") as f:
            test_py = f.read()
        snapshots = {"test.txt": test_txt, "test.py": test_py}
        self.as_tool_failure(self.sandbox.write_file("test.txt", ""))
        self.as_tool_failure(self.sandbox.write_file("unknown.txt", "x"))
        self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": 99, "new_content": "x"}])
        )
        self.as_tool_failure(
            self.sandbox.replace_chunks("test.py", [{"index": 0}])
        )
        self.as_tool_failure(self.sandbox.read_file("test.txt", start_line=0))
        for name, expected in snapshots.items():
            path = self.file_mappings[name]
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), expected, f"{name} was modified by a failed call")


class TestSandboxImplErrors(unittest.TestCase):
    """Error-message quality and filesystem edge cases."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.real_foo = os.path.join(self.temp_dir, "foo.txt")
        self.real_bar = os.path.join(self.temp_dir, "bar.txt")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def _config(self, file_mappings, readable_paths, writable_paths,
                blame_targets: Optional[List[str]] = None,
                read_size_limit: int = 100,
                search_result_limit: int = 10,
                verification_callback=None) -> SandboxConfig:
        return SandboxConfig(
            file_mappings=file_mappings,
            readable_paths=readable_paths,
            writable_paths=writable_paths,
            blame_targets=blame_targets or [],
            read_size_limit=read_size_limit,
            search_result_limit=search_result_limit,
            verification_callback=verification_callback,
        )

    def as_tool_failure(self, outcome: Any) -> ToolFailure:
        assert isinstance(outcome, ToolFailure), f"Expected ToolFailure, got {outcome!r}"
        return outcome

    def test_read_nonexistent_file_virtualizes_real_path(self) -> None:
        missing = os.path.join(self.temp_dir, "missing", "foo.txt")
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": missing},
            readable_paths=["foo.txt"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.read_file("foo.txt"))
        # LLS: messages name the virtual path, never the resolved filesystem path.
        self.assertIn("foo.txt", failure.value)
        self.assertNotIn(missing, failure.value)

    def test_error_messages_virtualize_partial_real_paths(self) -> None:
        # A real path that prefixes another is replaced longest-first.
        real_a = os.path.join(self.temp_dir, "foo.txt")
        real_b = os.path.join(self.temp_dir, "foo.txt.bak")
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": real_a, "foo.txt.bak": real_b},
            readable_paths=["foo.txt", "foo.txt.bak"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.read_file("foo.txt"))
        # LLS: messages name the virtual path, never the resolved filesystem path.
        self.assertIn("foo.txt", failure.value)
        self.assertNotIn(self.temp_dir, failure.value)

    def test_read_denial_lists_readable_files(self) -> None:
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": self.real_foo, "bar.txt": self.real_bar},
            readable_paths=["foo.txt"],
            writable_paths=["foo.txt"],
        ))
        failure = self.as_tool_failure(sandbox.read_file("bar.txt"))
        # LLS (implementation spec): denial messages name the virtual path and
        # list the readable paths.
        self.assertIn("bar.txt", failure.value)
        self.assertIn("foo.txt", failure.value)
        failure2 = self.as_tool_failure(sandbox.read_file("baz.txt"))
        self.assertIn("foo.txt", failure2.value)

    def test_write_denial_lists_writable_files(self) -> None:
        sandbox = SandboxImpl(self._config(
            file_mappings={"foo.txt": self.real_foo, "bar.txt": self.real_bar},
            readable_paths=["foo.txt", "bar.txt"],
            writable_paths=["foo.txt"],
        ))
        failure = self.as_tool_failure(sandbox.write_file("bar.txt", "content"))
        # LLS (implementation spec): denial messages name the virtual path and
        # list the writable paths.
        self.assertIn("bar.txt", failure.value)
        self.assertIn("foo.txt", failure.value)
        failure2 = self.as_tool_failure(sandbox.write_file("baz.txt", "content"))
        self.assertIn("foo.txt", failure2.value)

    def test_search_nonexistent_path(self) -> None:
        missing = os.path.join(self.temp_dir, "nonexistent")
        sandbox = SandboxImpl(self._config(
            file_mappings={"d": missing},
            readable_paths=["d"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.search_files("d", "pattern"))
        # LLS: messages name the virtual path, never the resolved filesystem path.
        self.assertIn("d", failure.value)
        self.assertNotIn(self.temp_dir, failure.value)

    def test_read_empty_file(self) -> None:
        empty = os.path.join(self.temp_dir, "empty.txt")
        open(empty, "w", encoding="utf-8").close()
        sandbox = SandboxImpl(self._config(
            file_mappings={"empty.txt": empty},
            readable_paths=["empty.txt"],
            writable_paths=["empty.txt"],
        ))
        result = sandbox.read_file("empty.txt")
        assert isinstance(result, ToolResult)
        self.assertEqual(result.content, "")
        self.assertFalse(result.stub_previous)

    def test_read_path_that_is_a_directory(self) -> None:
        sandbox = SandboxImpl(self._config(
            file_mappings={"d": self.temp_dir},
            readable_paths=["d"],
            writable_paths=[],
        ))
        failure = self.as_tool_failure(sandbox.read_file("d"))
        # LLS: messages name the virtual path; the exact wording is unspecified.
        self.assertIn("d", failure.value)

    def test_write_special_characters_round_trip(self) -> None:
        content = "Special chars: \n\t\ufffd\U0001F600"
        target = os.path.join(self.temp_dir, "special.txt")
        sandbox = SandboxImpl(self._config(
            file_mappings={"special.txt": target},
            readable_paths=["special.txt"],
            writable_paths=["special.txt"],
        ))
        result = sandbox.write_file("special.txt", content)
        assert isinstance(result, ToolResult)
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)


if __name__ == "__main__":
    unittest.main()
