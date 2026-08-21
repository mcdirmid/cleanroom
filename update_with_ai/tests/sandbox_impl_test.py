"""
Tests for the SandboxImpl implementation.

Written from the LLS (specs/sandbox_impl-low.md, specs/sandbox-low.md,
specs/tool_provider-low.md, specs/dag_clean_logic-low.md): the sandbox's
Stubbing rules, operation postconditions, and expected failure signals.

The API returns a single ToolCallOutcome per tool call: a ToolResult or a
Signal (ToolFailure, TerminateAgentWithSuccess, TerminateAgentWithFailure).

Stubbing (sandbox-low.md, Stubbing): a ToolResult's `supersedes` flag is set
on the results of operations on writable files and on verification results;
it is not set on reads of files that are not writable, on searches, or on
termination tools' results. The consuming agent loop stubs the superseded
result; the sandbox itself maintains no stubbing state.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Tuple

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
        """Set up a temp workspace with a writable file, a read-only file,
        and a creation target."""
        self.temp_dir = tempfile.mkdtemp()

        # Plain text file (4 lines).
        self.test_file_path = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\n")
            f.write("Line 2: This is a test\n")
            f.write("Line 3: Another line\n")
            f.write("Line 4: Final line\n")

        # Creation target: mapped but does not exist until write_file creates
        # it (write_file is creation-only).
        self.new_file_path = os.path.join(self.temp_dir, "new.txt")

        self.file_mappings = {
            "test.txt": self.test_file_path,
            "ro.txt": self.test_file_path,
            "new.txt": self.new_file_path,
        }
        self.readable_paths = ["test.txt", "ro.txt", "new.txt"]
        self.writable_paths = ["test.txt", "new.txt"]
        self.blame_targets = ["agent", "system"]

        self.config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
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

    def assert_supersedes(self, outcome: Any, supersedes: bool) -> ToolResult:
        """Assert the outcome is a ToolResult with the given supersedes flag.

        supersedes=True: the result supersedes the earlier non-stubbed result
        for the same file or tool command (the agent loop stubs it).
        supersedes=False: the result never supersedes an earlier result
        (reads of files that are not writable, searches, termination tools).
        """
        result = self.as_tool_result(outcome)
        assert result.supersedes is supersedes, (
            f"Expected supersedes={supersedes}, got {result!r}"
        )
        return result

    # ------------------------------------------------------------------
    # get_tool_definitions
    # ------------------------------------------------------------------

    def test_get_tool_definitions_always_includes_core_tools(self) -> None:
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        for expected in ("read_file", "write_file", "edit_file", "replace_lines",
                         "search_files", "verify", "succeed", "fail"):
            self.assertIn(expected, names)

    def test_get_tool_definitions_follow_json_schema_shape(self) -> None:
        for d in self.sandbox.get_tool_definitions():
            self.assertEqual(d["type"], "function")
            fn = d["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertEqual(fn["parameters"]["type"], "object")

    def test_read_file_definition_line_numbers_off_by_default(self) -> None:
        read_def = next(
            d for d in self.sandbox.get_tool_definitions()
            if d["function"]["name"] == "read_file"
        )
        props = read_def["function"]["parameters"]["properties"]
        self.assertFalse(props["include_line_numbers"]["default"])
        # No pagination parameters: the whole file is read.
        self.assertNotIn("start_line", props)
        self.assertNotIn("end_line", props)

    def test_replace_lines_definition_marks_all_parameters_required(self) -> None:
        # LLS (sandbox-low.md replace_lines): the tool definition's schema
        # marks file_path, start_line, end_line, and new_str as required, so
        # the model cannot omit them (e.g., drop end_line).
        replace_def = next(
            d for d in self.sandbox.get_tool_definitions()
            if d["function"]["name"] == "replace_lines"
        )
        schema = replace_def["function"]["parameters"]
        self.assertEqual(
            sorted(schema["required"]),
            ["end_line", "file_path", "new_str", "start_line"],
        )
        for param in ("file_path", "start_line", "end_line", "new_str"):
            self.assertIn(param, schema["properties"])

    def test_get_tool_definitions_verify_always_present(self) -> None:
        names = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("verify", names)

    def test_get_tool_definitions_blame_conditional(self) -> None:
        with_targets = [d["function"]["name"] for d in self.sandbox.get_tool_definitions()]
        self.assertIn("blame", with_targets)

        no_targets = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        names = [d["function"]["name"] for d in SandboxImpl(no_targets).get_tool_definitions()]
        self.assertNotIn("blame", names)

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    def test_read_file_reads_entire_file(self) -> None:
        # A read returns the file's ENTIRE content (never paginated). A
        # non-writable file reads plain; its result never supersedes.
        config = SandboxConfig(
            file_mappings={"ro.txt": self.test_file_path},
            readable_paths=["ro.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.assert_supersedes(SandboxImpl(config).read_file("ro.txt"), False)
        self.assertEqual(
            result.content,
            "Line 1: Hello World\nLine 2: This is a test\n"
            "Line 3: Another line\nLine 4: Final line",
        )
        self.assertIn("4 lines", result.note)

    def test_read_file_writable_existing_requires_line_numbers(self) -> None:
        # The buy-in flow: a plain read of a writable file that already
        # exists is rejected with guidance; the agent re-reads with
        # include_line_numbers=True and the numbered read supersedes the
        # earlier result for the file.
        failure = self.as_tool_failure(self.sandbox.read_file("test.txt"))
        self.assertIn("include_line_numbers=True", failure.value)
        self.assertIn("writable", failure.value)

        result = self.assert_supersedes(
            self.sandbox.read_file("test.txt", include_line_numbers=True), True
        )
        self.assertIn("1 \u2502 Line 1: Hello World", result.content)
        self.assertIn("(line-numbered)", result.note)

    def test_read_file_writable_missing_still_reports_missing(self) -> None:
        # new.txt is writable but does not exist: the read reports the
        # missing file (not the line-number requirement).
        failure = self.as_tool_failure(self.sandbox.read_file("new.txt"))
        self.assertIn("does not exist", failure.value)

    def test_read_file_line_numbered_view(self) -> None:
        # test.txt is writable, so the numbered read supersedes the earlier
        # result for the file.
        result = self.assert_supersedes(
            self.sandbox.read_file("test.txt", include_line_numbers=True), True
        )
        self.assertIn("1 \u2502 Line 1: Hello World", result.content)
        self.assertIn("4 \u2502 Line 4: Final line", result.content)
        self.assertIn("(line-numbered)", result.note)

    def test_read_file_writable_read_supersedes(self) -> None:
        result = self.assert_supersedes(
            self.sandbox.read_file("test.txt", include_line_numbers=True), True
        )
        self.assertIn("1 \u2502 Line 1: Hello World", result.content)

    def test_read_file_readonly_file_never_supersedes(self) -> None:
        # A file that is readable but not writable reads plain and never
        # supersedes an earlier result (reads of readable files are not
        # stubbed).
        config = SandboxConfig(
            file_mappings={"ro.txt": self.test_file_path},
            readable_paths=["ro.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.assert_supersedes(SandboxImpl(config).read_file("ro.txt"), False)
        self.assertIn("Line 1: Hello World", result.content)
        self.assertNotIn("\u2502", result.content)

    def test_read_file_line_numbers_require_writable(self) -> None:
        config = SandboxConfig(
            file_mappings={"ro.txt": self.test_file_path},
            readable_paths=["ro.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(
            SandboxImpl(config).read_file("ro.txt", include_line_numbers=True)
        )
        self.assertIn("writable", failure.value)

    def test_read_file_policy_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.read_file("nope.txt"))
        self.assertIn("nope.txt", failure.value)

    def test_read_file_policy_not_readable(self) -> None:
        config = SandboxConfig(
            file_mappings={"a.txt": self.test_file_path},
            readable_paths=[],
            writable_paths=["a.txt"],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).read_file("a.txt"))
        self.assertIn("not readable", failure.value)

    # ------------------------------------------------------------------
    # write_file
    # ------------------------------------------------------------------

    def test_write_file_success_supersedes(self) -> None:
        # LLS (sandbox-low.md write_file): the result carries a minimal
        # structured status — never a file-content echo — and supersedes the
        # earlier result for the file (the agent loop stubs it).
        result = self.assert_supersedes(self.sandbox.write_file("new.txt", "hello\nworld"), True)
        self.assertEqual(result.content, "Created new.txt; 2 lines")
        self.assertEqual(result.note, "")
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.new_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello\nworld")

    def test_write_result_is_status_and_resets_view(self) -> None:
        # A write/edit result carries the operation's status (never a
        # file-content echo) and supersedes the file's earlier results; the
        # write resets the view to plain (a write invalidates the line
        # numbers), so a line-range edit requires a fresh numbered read.
        self.assert_supersedes(
            self.sandbox.read_file("test.txt", include_line_numbers=True), True
        )
        edited = self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assertEqual(edited.content, "Replaced 1 occurrence in test.txt")
        self.assertEqual(edited.note, "")
        # The change is on disk; the result never echoes file content.
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: New content", f.read())

        new_result = self.assert_supersedes(
            self.sandbox.write_file("new.txt", "one\ntwo"), True
        )
        self.assertEqual(new_result.content, "Created new.txt; 2 lines")

    def test_replace_lines_after_write_requires_fresh_numbered_read(self) -> None:
        # A write invalidates the line-numbered view: replace_lines after a
        # write fails with a reminder, and succeeds only after re-reading
        # numbered (the read->edit->re-read discipline).
        self._numbered_read()
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 2, 2, "Line 2: replaced")
        )
        self.assertIn("invalidated", failure.value)
        self.assertIn("include_line_numbers=True", failure.value)
        # LLS: the failure supersedes nothing and removes nothing; there are
        # no buffers to close.
        self.assertFalse(hasattr(failure, "close_buffer"))

        self._numbered_read()
        result = self.assert_supersedes(
            self.sandbox.replace_lines("test.txt", 2, 2, "Line 2: replaced"), True
        )
        self.assertEqual(result.content, "Replaced lines 2-2 in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: replaced", f.read())

    def test_replace_lines_plain_view_failure_advises_numbered_read(self) -> None:
        # LLS (sandbox-low.md Stubbing + replace_lines Failure Handling): a
        # replace_lines failure for a file whose view is not line-numbered
        # returns ToolFailure advising a numbered read; the failure
        # supersedes nothing and removes nothing (no buffers to close).
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 1, 1, "Line 1: replaced")
        )
        self.assertFalse(hasattr(failure, "close_buffer"))
        self.assertIn("include_line_numbers=True", failure.value)

        # A numbered read restores the view; replace_lines then succeeds (the
        # write resets the view to plain), so the next line edit fails again
        # with the same advice.
        self._numbered_read()
        self.assert_supersedes(
            self.sandbox.replace_lines("test.txt", 1, 1, "Line 1: replaced"), True
        )
        failure2 = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 2, 2, "Line 2: replaced")
        )
        self.assertFalse(hasattr(failure2, "close_buffer"))
        self.assertIn("include_line_numbers=True", failure2.value)

    def test_write_file_rejects_existing_file(self) -> None:
        failure = self.as_tool_failure(self.sandbox.write_file("test.txt", "x"))
        self.assertIn("already exists", failure.value)
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_write_file_empty_content_rejected(self) -> None:
        failure = self.as_tool_failure(self.sandbox.write_file("new.txt", ""))
        self.assertIn("non-empty", failure.value)

    def test_write_file_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.write_file("nope.txt", "x"))
        self.assertIn("nope.txt", failure.value)

    def test_write_file_not_writable(self) -> None:
        config = SandboxConfig(
            file_mappings={"a.txt": self.test_file_path},
            readable_paths=["a.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).write_file("a.txt", "x"))
        self.assertIn("not writable", failure.value)

    def test_write_file_creates_missing_directories(self) -> None:
        nested = os.path.join(self.temp_dir, "sub", "nested.txt")
        config = SandboxConfig(
            file_mappings={"nested.txt": nested},
            readable_paths=["nested.txt"],
            writable_paths=["nested.txt"],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        self.assert_supersedes(sandbox.write_file("nested.txt", "x"), True)
        self.assertTrue(os.path.exists(nested))

    # ------------------------------------------------------------------
    # edit_file
    # ------------------------------------------------------------------

    def test_edit_file_replaces_single_occurrence(self) -> None:
        # LLS (sandbox-low.md edit_file): the result is a minimal structured
        # status with supersedes set — never a file-content echo.
        result = self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assertEqual(result.content, "Replaced 1 occurrence in test.txt")
        self.assertEqual(result.note, "")
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: New content", f.read())

    def test_edit_file_identical_old_and_new_fails(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "x", "x")
        )
        self.assertIn("identical", failure.value)

    def test_edit_file_not_found_fails(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "no such text", "x")
        )
        self.assertIn("not found", failure.value)

    def test_edit_file_multiple_matches_fail_without_expect_multiple(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "Line", "Row")
        )
        self.assertIn("matches", failure.value)

    def test_edit_file_expect_multiple_replaces_all(self) -> None:
        result = self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "Line", "Row", expect_multiple=True), True
        )
        self.assertEqual(result.content, "Replaced 4 occurrences in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertNotIn("Line", f.read())

    def test_edit_file_empty_old_str_fails(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "", "x")
        )
        self.assertIn("non-empty", failure.value)

    def test_edit_file_overlong_strings_fail_recommending_replace_lines(self) -> None:
        # edit_file is for short search/replace pairs only: an old_str or
        # new_str over 100 characters fails, advising replace_lines (which
        # requires the line-numbered view). No write occurs.
        overlong_old = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "x" * 101, "y")
        )
        self.assertIn("100 characters", overlong_old.value)
        self.assertIn("replace_lines", overlong_old.value)
        self.assertFalse(self.sandbox.get_write_occurred())

        overlong_new = self.as_tool_failure(
            self.sandbox.edit_file("test.txt", "Line 1", "y" * 101)
        )
        self.assertIn("100 characters", overlong_new.value)
        self.assertIn("replace_lines", overlong_new.value)

    def test_edit_file_at_length_limit_succeeds(self) -> None:
        # A 100-character old_str is within the limit and edits normally.
        filler = "x" * 94  # 94 + len("TARGET") == 100
        with open(self.test_file_path, "a", encoding="utf-8") as f:
            f.write(filler + "TARGET\n")
        result = self.assert_supersedes(
            self.sandbox.edit_file("test.txt", filler + "TARGET", "replaced"), True
        )
        self.assertEqual(result.content, "Replaced 1 occurrence in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertNotIn("TARGET", f.read())

    def test_edit_file_policy_violation(self) -> None:
        config = SandboxConfig(
            file_mappings={"a.txt": self.test_file_path},
            readable_paths=["a.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).edit_file("a.txt", "x", "y"))
        self.assertIn("not writable", failure.value)

    # ------------------------------------------------------------------
    # replace_lines
    # ------------------------------------------------------------------

    def _numbered_read(self) -> None:
        self.assert_supersedes(
            self.sandbox.read_file("test.txt", include_line_numbers=True), True
        )

    def test_replace_lines_replaces_range(self) -> None:
        self._numbered_read()
        result = self.assert_supersedes(
            self.sandbox.replace_lines("test.txt", 2, 2, "Line 2: replaced"), True
        )
        # LLS: the result is a minimal status with supersedes set — never a
        # file-content echo; the write resets the view to plain.
        self.assertEqual(result.content, "Replaced lines 2-2 in test.txt")
        self.assertTrue(self.sandbox.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: replaced", f.read())

    def test_replace_lines_deletes_range(self) -> None:
        self._numbered_read()
        result = self.assert_supersedes(
            self.sandbox.replace_lines("test.txt", 2, 3, ""), True
        )
        self.assertEqual(result.content, "Deleted lines 2-3 in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        self.assertNotIn("Line 2:", file_content)
        self.assertNotIn("Line 3:", file_content)
        self.assertIn("Line 4: Final line", file_content)

    def test_replace_lines_inserts_before_line(self) -> None:
        self._numbered_read()
        result = self.assert_supersedes(
            self.sandbox.replace_lines("test.txt", 2, 1, "inserted"), True
        )
        self.assertEqual(result.content, "Inserted content before line 2 in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("inserted", f.read())

    def test_replace_lines_requires_line_numbered_view(self) -> None:
        # No numbered read: the view is plain and the edit is refused.
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 1, 1, "x")
        )
        self.assertIn("include_line_numbers=True", failure.value)
        self.assertFalse(self.sandbox.get_write_occurred())

    def test_replace_lines_validation_fails(self) -> None:
        self._numbered_read()
        failure = self.as_tool_failure(
            self.sandbox.replace_lines("test.txt", 99, 100, "x")
        )
        self.assertIn("between", failure.value)

    # ------------------------------------------------------------------
    # search_files
    # ------------------------------------------------------------------

    def test_search_files_success_readonly(self) -> None:
        # A read-only search target: matches are rendered; the result never
        # supersedes an earlier result.
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.assert_supersedes(SandboxImpl(config).search_files("test.txt", "Line"), False)
        self.assertIn("test.txt:1:", result.content)
        self.assertIn("4 matches total", result.note)

    def test_search_files_suppresses_writable_matches(self) -> None:
        a_path = os.path.join(self.temp_dir, "a.txt")
        b_path = os.path.join(self.temp_dir, "b.txt")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("needle in a\n")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write("needle in b\n")
        config = SandboxConfig(
            file_mappings={"dir": self.temp_dir, "a.txt": a_path, "b.txt": b_path},
            readable_paths=["dir"],
            writable_paths=["b.txt"],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.assert_supersedes(SandboxImpl(config).search_files("dir", "needle"), False)
        # The writable file's match is never rendered; only a.txt's is.
        self.assertIn("a.txt:1:", result.content)
        self.assertNotIn("b.txt:", result.content)
        self.assertIn("1 matches total", result.note)
        self.assertIn("1 match(es) in writable files not shown", result.note)

    def test_search_files_invalid_pattern(self) -> None:
        failure = self.as_tool_failure(self.sandbox.search_files("test.txt", "["))
        self.assertIn("Invalid regex", failure.value)

    def test_search_files_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self.sandbox.search_files("nope.txt", "x"))
        self.assertIn("nope.txt", failure.value)

    def test_search_files_not_readable(self) -> None:
        config = SandboxConfig(
            file_mappings={"a.txt": self.test_file_path},
            readable_paths=[],
            writable_paths=["a.txt"],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).search_files("a.txt", "x"))
        self.assertIn("not readable", failure.value)

    def test_search_files_recursive_in_directory(self) -> None:
        config = SandboxConfig(
            file_mappings={"dir": self.temp_dir},
            readable_paths=["dir"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        result = self.assert_supersedes(SandboxImpl(config).search_files("dir", "Line 1"), False)
        self.assertIn("test.txt:1:", result.content)

    def test_search_files_omitted_limit_fails_when_matches_exceed_limit(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=2,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).search_files("test.txt", "Line"))
        self.assertIn("search result limit", failure.value)

    def test_search_files_pagination_with_limit_and_offset(self) -> None:
        config = SandboxConfig(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
            blame_targets=[],
            search_result_limit=2,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        first = self.assert_supersedes(
            sandbox.search_files("test.txt", "Line", limit=2), False
        )
        self.assertIn("test.txt:1:", first.content)
        self.assertIn("test.txt:2:", first.content)
        self.assertIn("2 more after this page", first.note)
        second = self.assert_supersedes(
            sandbox.search_files("test.txt", "Line", offset=2, limit=2), False
        )
        self.assertIn("test.txt:3:", second.content)
        self.assertIn("0 more after this page", second.note)

    def test_search_files_explicit_limit_above_max_fails(self) -> None:
        failure = self.as_tool_failure(
            self.sandbox.search_files("test.txt", "Line", limit=10)
        )
        self.assertIn("search result limit", failure.value)

    # ------------------------------------------------------------------
    # verify
    # ------------------------------------------------------------------

    def test_verify_no_callback_reports_no_changes(self) -> None:
        result = self.assert_supersedes(self.sandbox.verify(), True)
        self.assertIn("No files were changed", result.content)
        self.assertIn("No verification tool is configured", result.content)
        self.assertIn("succeed() may now be called", result.content)
        # The note reports only the status (pinned in sandbox_impl-low.md),
        # never the failure details (which live in the content).
        self.assertEqual(result.note, "No verification tool configured.")

    def test_verify_no_callback_reports_diff_after_write(self) -> None:
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        result = self.assert_supersedes(self.sandbox.verify(), True)
        self.assertIn("### diff for test.txt", result.content)
        self.assertIn("-Line 2: This is a test", result.content)
        self.assertIn("+Line 2: New content", result.content)
        self.assertIn("succeed() may now be called", result.content)

    def test_verify_success(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (True, "Verification passed")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            verification_callback=callback,
        )
        result = self.assert_supersedes(SandboxImpl(config).verify(), True)
        self.assertIn("No files were changed in this run.", result.content)
        self.assertIn("Verification passed", result.content)
        self.assertIn("succeed() may now be called", result.content)
        self.assertEqual(result.note, "Verification passed.")

    def test_verify_failure_records_failed_state(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (False, "lint errors found")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            verification_callback=callback,
        )
        result = self.assert_supersedes(SandboxImpl(config).verify(), True)
        self.assertIn("lint errors found", result.content)
        self.assertIn("Verification failed", result.content)
        self.assertIn("verify() again", result.content)
        self.assertEqual(result.note, "Verification failed.")

    def test_verify_diff_truncated_when_large(self) -> None:
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            diff_size_limit=40,
            verification_callback=None,
        )
        sandbox = SandboxImpl(config)
        self.assert_supersedes(
            sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        result = self.assert_supersedes(sandbox.verify(), True)
        self.assertIn("diff truncated", result.content)
        self.assertIn("showing 40 of", result.content)

    def test_verify_callback_exception(self) -> None:
        def callback() -> Tuple[bool, str]:
            raise RuntimeError("callback blew up")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            verification_callback=callback,
        )
        failure = self.as_tool_failure(SandboxImpl(config).verify())
        self.assertIn("Verification error", failure.value)

    def test_verify_reexecution_reports_new_diff(self) -> None:
        # A second verify after a write reports the new diff; the result
        # supersedes the earlier verification result (per the Stubbing
        # rules, a verification sets the flag).
        first = self.assert_supersedes(self.sandbox.verify(), True)
        self.assertIn("No files were changed", first.content)
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        second = self.assert_supersedes(self.sandbox.verify(), True)
        self.assertIn("### diff for test.txt", second.content)

    # ------------------------------------------------------------------
    # succeed / fail / blame
    # ------------------------------------------------------------------

    def test_succeed_no_change_when_no_write(self) -> None:
        result = self.as_success(self.sandbox.succeed())
        self.assertEqual(result.value.type, "no_change")

    def test_succeed_change_result_when_write_occurred(self) -> None:
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        result = self.as_success(self.sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "Updated the test line"}]
        ))
        self.assertEqual(result.value.type, "change")
        self.assertEqual(result.value.messages, ["test.txt: Updated the test line"])

    def test_succeed_bare_after_write_lists_changed_files(self) -> None:
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        failure = self.as_tool_failure(self.sandbox.succeed())
        self.assertIn("test.txt", failure.value)

    def test_succeed_unknown_file_in_changes_fails(self) -> None:
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        failure = self.as_tool_failure(self.sandbox.succeed(
            changes=[{"file": "nope.txt", "summary": "changed"}]
        ))
        self.assertIn("nope.txt", failure.value)

    def test_succeed_overlong_summary_fails(self) -> None:
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        failure = self.as_tool_failure(self.sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "x" * 201}]
        ))
        # First soft-limit rejection: directs shortening to the soft bound
        # (200), naming the parts of the file that changed (substance pinned
        # in sandbox-low.md; exact phrasing not pinned).
        self.assertIn("short sentence", failure.value)
        self.assertIn("200", failure.value)
        self.assertIn("parts of the file that changed", failure.value)

    def test_succeed_soft_grace_accepts_within_hard_limit(self) -> None:
        # A summary over the soft bound (200) is rejected up to 4 times, then
        # accepted on the next succeed call when within the hard bound (500).
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        for _ in range(4):
            self.as_tool_failure(self.sandbox.succeed(
                changes=[{"file": "test.txt", "summary": "x" * 201}]
            ))
        outcome = self.sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "y" * 480}]
        )
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome, TerminateAgentWithSuccess)
        self.assertIsInstance(outcome.value, ChangeResult)
        self.assertEqual(outcome.value.messages, ["test.txt: " + "y" * 480])

    def test_succeed_hard_grace_turns_succeed_into_failure(self) -> None:
        # A summary over the hard bound (500) is rejected up to 4 times, then
        # succeed() turns into a hard failure (TerminateAgentWithFailure).
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        for _ in range(4):
            failure = self.as_tool_failure(self.sandbox.succeed(
                changes=[{"file": "test.txt", "summary": "x" * 600}]
            ))
            self.assertIn("500", failure.value)
        outcome = self.sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "x" * 600}]
        )
        self.assertIsInstance(outcome, TerminateAgentWithFailure)

    def test_succeed_missing_changed_file_fails(self) -> None:
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(self.sandbox.write_file("new.txt", "x"), True)
        self.assert_supersedes(self.sandbox.verify(), True)
        failure = self.as_tool_failure(self.sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "changed"}]
        ))
        self.assertIn("new.txt", failure.value)

    def test_succeed_fabricated_change_rejected(self) -> None:
        # A claimed change that does not appear in the diff (file rewritten
        # back to identical content) is rejected, and the run is directed to
        # report no change: succeed() with no changes resolves the deadlock
        # (writes net out to no change -> NoChangeResult).
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(
            self.sandbox.edit_file("test.txt", "New content", "This is a test"), True
        )
        self.assert_supersedes(self.sandbox.verify(), True)
        failure = self.as_tool_failure(self.sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "I changed it"}]
        ))
        self.assertIn("net-changed nothing", failure.value)
        self.assertIn("with no changes", failure.value)

        outcome = self.sandbox.succeed()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome, TerminateAgentWithSuccess)
        self.assertIsInstance(outcome.value, NoChangeResult)

    def test_fail(self) -> None:
        result = self.as_terminate_failure(self.sandbox.fail())
        self.assertEqual(result.value, "Task failed")

    def test_succeed_blocked_when_verify_not_called(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (True, "ok")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            verification_callback=callback,
        )
        sandbox = SandboxImpl(config)
        self.assert_supersedes(
            sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        failure = self.as_tool_failure(sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "changed"}]
        ))
        self.assertIn("verify() has not been called", failure.value)

    def test_succeed_blocked_when_last_verify_failed(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (False, "bad")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            verification_callback=callback,
        )
        sandbox = SandboxImpl(config)
        self.assert_supersedes(
            sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(sandbox.verify(), True)
        failure = self.as_tool_failure(sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "changed"}]
        ))
        self.assertIn("last verify() call failed", failure.value)

    def test_succeed_allowed_after_verify_passes(self) -> None:
        def callback() -> Tuple[bool, str]:
            return (True, "ok")

        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=self.blame_targets,
            search_result_limit=5,
            verification_callback=callback,
        )
        sandbox = SandboxImpl(config)
        self.assert_supersedes(
            sandbox.edit_file("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(sandbox.verify(), True)
        result = self.as_success(sandbox.succeed(
            changes=[{"file": "test.txt", "summary": "changed"}]
        ))
        self.assertEqual(result.value.type, "change")

    def test_fail_allowed_even_when_verify_gate_blocked(self) -> None:
        result = self.as_terminate_failure(self.sandbox.fail())
        self.assertEqual(result.value, "Task failed")

    def test_blame_no_targets_configured(self) -> None:
        config = SandboxConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            blame_targets=[],
            search_result_limit=5,
            verification_callback=None,
        )
        failure = self.as_tool_failure(SandboxImpl(config).blame([("x", "fix it")]))
        self.assertIn("not configured", failure.value)

    def test_blame_empty_list_fails(self) -> None:
        failure = self.as_tool_failure(self.sandbox.blame([]))
        self.assertIn("must not be empty", failure.value)

    def test_blame_invalid_target_fails(self) -> None:
        failure = self.as_tool_failure(self.sandbox.blame([("not_a_dep", "fix it")]))
        self.assertIn("not_a_dep", failure.value)

    def test_blame_success_forms_feedback_result(self) -> None:
        result = self.as_success(
            self.sandbox.blame([("agent", "fix the output"), ("system", "redo")])
        )
        self.assertIsInstance(result.value, FeedbackResult)
        self.assertEqual(
            result.value.messages,
            [("agent", "fix the output"), ("system", "redo")],
        )

    # ------------------------------------------------------------------
    # get_write_occurred
    # ------------------------------------------------------------------

    def test_write_occurred_false_until_first_write(self) -> None:
        self.assertFalse(self.sandbox.get_write_occurred())
        self.assert_supersedes(self.sandbox.write_file("new.txt", "x"), True)
        self.assertTrue(self.sandbox.get_write_occurred())
        self.assertTrue(self.sandbox.get_write_occurred())


if __name__ == "__main__":
    unittest.main()
