"""
Tests for the FileViewImpl implementation.

Written from the LLS (specs/low/file_view_impl.md, specs/low/file_view.md,
specs/low/tool_provider.md): the file machinery's virtual-name addressing,
readable/writable policy enforcement, plain vs line-numbered views, the file
tools (read_file, replace, update_lines, search_files), template
initialization, session-start reads, injected re-reads, supersession flags,
the write-occurred flag, the search result limit, and error messages naming
virtual names.

The API returns a ToolCallOutcome per tool call: a sequence of one or more
results (ToolResult or PresentedToolResult values) or a Signal (ToolFailure).
A successful file write returns a two-result sequence: the write confirmation
(a ToolResult with supersedes set; its content a minimal status, never a
file-content echo) and the injected read (a PresentedToolResult pairing
read_file(file_path, include_line_numbers=True) with the file's numbered
content, supersedes set).

Stubbing follows tool_provider semantics: `supersedes` is set on the results
of operations on writable files (reads, writes, edits); it is unset on reads
of files that are not writable and on search results. The consuming agent
loop stubs the superseded result; file_view itself maintains no stubbing
state.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Optional, Tuple

from lib.file_view import FileViewConfig
from lib.file_view_impl import FileViewImpl
from lib.tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolResult,
    ToolFailure,
)


class TestFileViewImpl(unittest.TestCase):
    """Main coverage: tool definitions, policy enforcement, views, writes,
    injected reads, searches, supersession flags, and the write-occurred
    flag."""

    def setUp(self) -> None:
        """Set up a temp workspace with two writable files, a read-only
        file, and a mapped-but-missing writable target."""
        self.temp_dir = tempfile.mkdtemp()

        # Plain text file (4 lines).
        self.test_file_path = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\n")
            f.write("Line 2: This is a test\n")
            f.write("Line 3: Another line\n")
            f.write("Line 4: Final line\n")

        # Second writable file (2 lines).
        self.second_path = os.path.join(self.temp_dir, "second.txt")
        with open(self.second_path, "w", encoding="utf-8") as f:
            f.write("Second line one\n")
            f.write("Second line two\n")

        # Read-only file (2 lines).
        self.ro_path = os.path.join(self.temp_dir, "ro.txt")
        with open(self.ro_path, "w", encoding="utf-8") as f:
            f.write("Read only line 1\n")
            f.write("Read only line 2\n")

        # Mapped and writable but does not exist on disk.
        self.new_file_path = os.path.join(self.temp_dir, "new.txt")

        self.file_mappings = {
            "test.txt": self.test_file_path,
            "second.txt": self.second_path,
            "ro.txt": self.ro_path,
            "new.txt": self.new_file_path,
        }
        self.readable_paths = ["test.txt", "second.txt", "ro.txt", "new.txt"]
        self.writable_paths = ["test.txt", "second.txt", "new.txt"]

    def _file_view(
        self,
        file_mappings: Optional[dict] = None,
        readable_paths: Optional[list] = None,
        writable_paths: Optional[list] = None,
        templates: Optional[dict] = None,
        search_result_limit: int = 5,
        session_start_reads_enabled: bool = True,
    ) -> FileViewImpl:
        """Construct a FileViewImpl with the fixture defaults or overrides."""
        return FileViewImpl(FileViewConfig(
            file_mappings=file_mappings if file_mappings is not None else self.file_mappings,
            readable_paths=readable_paths if readable_paths is not None else self.readable_paths,
            writable_paths=writable_paths if writable_paths is not None else self.writable_paths,
            templates=templates if templates is not None else {},
            search_result_limit=search_result_limit,
            session_start_reads_enabled=session_start_reads_enabled,
        ))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # Outcome narrowing helpers
    # ------------------------------------------------------------------

    def as_tool_result(self, outcome: Any) -> ToolResult:
        """Unwrap a result sequence: its first result (for a write outcome,
        the write confirmation)."""
        if isinstance(outcome, list):
            assert len(outcome) >= 1, f"Expected a result sequence, got {outcome!r}"
            outcome = outcome[0]
        assert isinstance(outcome, ToolResult), f"Expected ToolResult, got {outcome!r}"
        return outcome

    def as_write_outcome(self, outcome: Any) -> Tuple[ToolResult, PresentedToolResult]:
        """A file write's outcome per the injected read rules: the write
        confirmation and the injected read, in that order."""
        assert isinstance(outcome, list) and len(outcome) == 2, (
            f"Expected a two-result sequence, got {outcome!r}"
        )
        confirmation = outcome[0]
        injected = outcome[1]
        assert isinstance(confirmation, ToolResult), (
            f"Expected ToolResult, got {confirmation!r}"
        )
        assert isinstance(injected, PresentedToolResult), (
            f"Expected PresentedToolResult, got {injected!r}"
        )
        return confirmation, injected

    def as_tool_failure(self, outcome: Any) -> ToolFailure:
        assert isinstance(outcome, ToolFailure), f"Expected ToolFailure, got {outcome!r}"
        return outcome
    def assert_supersedes(self, outcome: Any, supersedes: bool) -> ToolResult:
        """Assert the outcome is a ToolResult with the given supersedes flag."""
        result = self.as_tool_result(outcome)
        assert result.supersedes is supersedes, (
            f"Expected supersedes={supersedes}, got {result!r}"
        )
        return result

    def _numbered_read(self, view: FileViewImpl, file_path: str = "test.txt") -> None:
        self.assert_supersedes(
            view.read_file(file_path, include_line_numbers=True), True
        )

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------

    def test_get_tool_definitions_returns_exactly_the_file_tools(self) -> None:
        # The file machinery provides exactly the four file tools (LLS
        # get_tool_definitions): read_file, replace, update_lines, and
        # search_files — nothing else.
        names = [d["function"]["name"] for d in self._file_view().get_tool_definitions()]
        self.assertEqual(sorted(names), ["read_file", "replace", "search_files", "update_lines"])

    def test_update_lines_definition_marks_all_parameters_required(self) -> None:
        # LLS (specs/low/file_view.md update_lines): the tool definition's
        # schema marks file_path, start_line, end_line, and new_str as
        # required, so the model cannot omit them.
        update_def = next(
            d for d in self._file_view().get_tool_definitions()
            if d["function"]["name"] == "update_lines"
        )
        schema = update_def["function"]["parameters"]
        self.assertEqual(
            sorted(schema["required"]),
            ["end_line", "file_path", "new_str", "start_line"],
        )
        for param in ("file_path", "start_line", "end_line", "new_str"):
            self.assertIn(param, schema["properties"])

    # ------------------------------------------------------------------
    # read_file: readable/writable policies, views, supersession
    # ------------------------------------------------------------------

    def test_read_file_readonly_plain_never_supersedes(self) -> None:
        # A read of a file that is not writable renders plain, returns the
        # file's entire content, and never supersedes an earlier result.
        view = self._file_view(
            file_mappings={"ro.txt": self.ro_path},
            readable_paths=["ro.txt"],
            writable_paths=[],
        )
        result = self.assert_supersedes(view.read_file("ro.txt"), False)
        self.assertEqual(
            result.content,
            "Read only line 1\nRead only line 2",
        )
        self.assertNotIn("\u2502", result.content)
        self.assertIn("2 lines", result.note)
        self.assertIn("plain", result.note)

    def test_read_file_writable_existing_requires_line_numbers(self) -> None:
        # A writable file that already exists on disk is only readable in
        # the line-numbered view: a plain read fails advising
        # include_line_numbers=True (line numbers are metadata, never file
        # content); the numbered read supersedes the file's earlier result.
        view = self._file_view()
        failure = self.as_tool_failure(view.read_file("test.txt"))
        self.assertIn("include_line_numbers=True", failure.value)
        self.assertIn("writable", failure.value)

        result = self.assert_supersedes(
            view.read_file("test.txt", include_line_numbers=True), True
        )
        self.assertIn("1 \u2502 Line 1: Hello World", result.content)
        self.assertIn("4 \u2502 Line 4: Final line", result.content)
        self.assertIn("(line-numbered)", result.note)

    def test_read_file_include_line_numbers_requires_writable(self) -> None:
        # include_line_numbers serves update_lines edits, which require a
        # writable file; a numbered read of a read-only file is rejected.
        view = self._file_view(
            file_mappings={"ro.txt": self.ro_path},
            readable_paths=["ro.txt"],
            writable_paths=[],
        )
        failure = self.as_tool_failure(
            view.read_file("ro.txt", include_line_numbers=True)
        )
        self.assertIn("writable", failure.value)

    def test_read_file_policy_not_in_mappings(self) -> None:
        failure = self.as_tool_failure(self._file_view().read_file("nope.txt"))
        self.assertIn("nope.txt", failure.value)
    def test_read_file_policy_not_readable(self) -> None:
        view = self._file_view(
            file_mappings={"a.txt": self.test_file_path},
            readable_paths=[],
            writable_paths=["a.txt"],
        )
        failure = self.as_tool_failure(view.read_file("a.txt"))
        self.assertIn("not readable", failure.value)

    def test_read_file_missing_writable_file_reports_missing(self) -> None:
        # new.txt is writable but does not exist: the read reports the
        # missing file (not the line-number requirement).
        failure = self.as_tool_failure(self._file_view().read_file("new.txt"))
        self.assertIn("does not exist", failure.value)

    # ------------------------------------------------------------------
    # get_session_start_reads
    # ------------------------------------------------------------------

    def test_session_start_reads_reads_only_readable_not_writable(self) -> None:
        # When session-start reads are enabled (the default), returns a
        # session-start read for every file that is readable but not writable
        # and exists as a regular file on disk; each is a PresentedToolResult
        # pairing read_file with the plain read result (never superseding).
        # Here only ro.txt qualifies (test.txt/second.txt are writable;
        # new.txt does not exist).
        reads = self._file_view().get_session_start_reads()
        self.assertEqual(len(reads), 1)
        read = reads[0]
        self.assertIsInstance(read, PresentedToolResult)
        self.assertEqual(read.name, "read_file")
        self.assertEqual(read.arguments, {"file_path": "ro.txt"})
        self.assertIn("Read only line 1", read.result.content)
        self.assertNotIn("\u2502", read.result.content)  # plain: no line numbers
        self.assertFalse(read.result.supersedes)
        self.assertIn("plain", read.result.note)

    def test_session_start_reads_sorted_by_virtual_name(self) -> None:
        # Session-start reads are provided sorted by virtual name, not the
        # config's path order.
        ro2 = os.path.join(self.temp_dir, "ro2.txt")
        with open(ro2, "w", encoding="utf-8") as f:
            f.write("second\n")
        view = self._file_view(
            file_mappings={"a.txt": self.test_file_path, "b.txt": ro2},
            readable_paths=["b.txt", "a.txt"],
            writable_paths=[],
        )
        reads = view.get_session_start_reads()
        self.assertEqual([r.arguments["file_path"] for r in reads], ["a.txt", "b.txt"])

    def test_session_start_reads_skips_missing_files(self) -> None:
        # Files that do not exist are not provided (only files that exist as
        # regular files on disk); new.txt is mapped but missing.
        view = self._file_view()
        reads = view.get_session_start_reads()
        self.assertEqual([r.arguments["file_path"] for r in reads], ["ro.txt"])

    def test_session_start_reads_disabled_returns_empty(self) -> None:
        view = self._file_view(session_start_reads_enabled=False)
        self.assertEqual(view.get_session_start_reads(), [])

    def test_session_start_reads_change_no_state(self) -> None:
        # Requesting the session-start reads changes no file_view state: the
        # write-occurred flag stays unset.
        view = self._file_view()
        view.get_session_start_reads()
        self.assertFalse(view.get_write_occurred())
        self.assertEqual(view.get_changed_files(), [])

    # ------------------------------------------------------------------
    # Writes: the write confirmation and the injected read
    # ------------------------------------------------------------------

    def test_write_outcome_confirmation_then_injected_read(self) -> None:
        # A successful edit is a file write: its outcome is a sequence of two
        # results — the write confirmation (a ToolResult with supersedes set,
        # its content a minimal status) and the injected read (a
        # PresentedToolResult pairing read_file(file_path,
        # include_line_numbers=True) with the file's numbered content,
        # supersedes set), in that order.
        view = self._file_view()
        confirmation, injected = self.as_write_outcome(
            view.replace("test.txt", "This is a test", "New content")
        )
        self.assertEqual(confirmation.content, "Replaced 1 occurrence in test.txt")
        self.assertEqual(confirmation.note, "")
        self.assertTrue(confirmation.supersedes)
        self.assertEqual(injected.name, "read_file")
        self.assertEqual(
            injected.arguments,
            {"file_path": "test.txt", "include_line_numbers": True},
        )
        self.assertIn("2 \u2502 Line 2: New content", injected.result.content)
        self.assertTrue(injected.result.supersedes)
        # The change is on disk; the confirmation never echoes file content.
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: New content", f.read())

    def test_write_confirmation_never_echoes_file_content(self) -> None:
        # The write confirmation's content is a minimal structured status,
        # never a file-content echo (the file's current content appears via
        # the injected read).
        view = self._file_view()
        confirmation, injected = self.as_write_outcome(
            view.replace("test.txt", "This is a test", "New content")
        )
        self.assertNotIn("Line 1", confirmation.content)
        self.assertNotIn("Hello World", confirmation.content)
        self.assertIn("Line 2: New content", injected.result.content)

    def test_injected_read_reenables_line_numbered_view(self) -> None:
        # A write resets the view to plain, but the injected read that follows
        # re-enables the line-numbered view, so a line-range edit may follow
        # a write without a further read (LLS Auto re-read + Views).
        view = self._file_view()
        self._numbered_read(view)
        self.as_write_outcome(
            view.replace("test.txt", "This is a test", "New content")
        )
        result = self.assert_supersedes(
            view.update_lines("test.txt", 2, 2, "Line 2: replaced"), True
        )
        self.assertEqual(result.content, "Replaced lines 2-2 in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: replaced", f.read())

    def test_write_that_fails_provides_no_injected_read(self) -> None:
        # A write that fails provides no injected read: replace on a file
        # that does not exist is a ToolFailure, not a result sequence.
        view = self._file_view()
        failure = self.as_tool_failure(
            view.replace("new.txt", "x", "y")
        )
        self.assertIn("does not exist", failure.value)
        self.assertFalse(view.get_write_occurred())

    # ------------------------------------------------------------------
    # replace
    # ------------------------------------------------------------------

    def test_replace_replaces_single_occurrence(self) -> None:
        view = self._file_view()
        result = self.assert_supersedes(
            view.replace("test.txt", "This is a test", "New content"), True
        )
        self.assertEqual(result.content, "Replaced 1 occurrence in test.txt")
        self.assertTrue(view.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: New content", f.read())

    def test_replace_expect_multiple_replaces_all(self) -> None:
        view = self._file_view()
        result = self.assert_supersedes(
            view.replace("test.txt", "Line", "Row", expect_multiple=True), True
        )
        self.assertEqual(result.content, "Replaced 4 occurrences in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertNotIn("Line", f.read())

    def test_replace_identical_old_and_new_fails(self) -> None:
        # old_str identical to new_str would change nothing: rejected as an
        # invalid argument.
        failure = self.as_tool_failure(
            self._file_view().replace("test.txt", "x", "x")
        )
        self.assertIn("identical", failure.value)

    def test_replace_empty_old_str_fails(self) -> None:
        failure = self.as_tool_failure(
            self._file_view().replace("test.txt", "", "x")
        )
        self.assertIn("non-empty", failure.value)

    def test_replace_overlong_strings_fail_recommending_update_lines(self) -> None:
        # replace is for short search/replace pairs only: an old_str or
        # new_str over 200 characters fails, advising update_lines (which
        # requires the line-numbered view). No write occurs.
        view = self._file_view()
        overlong_old = self.as_tool_failure(
            view.replace("test.txt", "x" * 201, "y")
        )
        self.assertIn("200 characters", overlong_old.value)
        self.assertIn("update_lines", overlong_old.value)
        self.assertFalse(view.get_write_occurred())

        overlong_new = self.as_tool_failure(
            view.replace("test.txt", "Line 1", "y" * 201)
        )
        self.assertIn("200 characters", overlong_new.value)
        self.assertIn("update_lines", overlong_new.value)

    def test_replace_old_str_not_found_fails(self) -> None:
        failure = self.as_tool_failure(
            self._file_view().replace("test.txt", "no such text", "x")
        )
        self.assertIn("not found", failure.value)

    def test_replace_multiple_matches_fail_without_expect_multiple(self) -> None:
        failure = self.as_tool_failure(
            self._file_view().replace("test.txt", "Line", "Row")
        )
        self.assertIn("matches", failure.value)

    def test_replace_does_not_modify_missing_file(self) -> None:
        # replace modifies existing files only: a mapped-but-missing
        # writable file is not created.
        view = self._file_view()
        failure = self.as_tool_failure(
            view.replace("new.txt", "x", "y")
        )
        self.assertIn("does not exist", failure.value)
        self.assertFalse(os.path.exists(self.new_file_path))
        self.assertFalse(view.get_write_occurred())

    def test_replace_policy_not_writable_fails(self) -> None:
        view = self._file_view(
            file_mappings={"a.txt": self.test_file_path},
            readable_paths=["a.txt"],
            writable_paths=[],
        )
        failure = self.as_tool_failure(view.replace("a.txt", "x", "y"))
        self.assertIn("not writable", failure.value)

    # ------------------------------------------------------------------
    # update_lines
    # ------------------------------------------------------------------

    def test_update_lines_requires_line_numbered_view(self) -> None:
        # No numbered read: the file's current view is plain and the edit is
        # refused, advising a numbered read. The failure supersedes nothing
        # and removes nothing (no write occurs).
        view = self._file_view()
        failure = self.as_tool_failure(
            view.update_lines("test.txt", 1, 1, "x")
        )
        self.assertIn("include_line_numbers=True", failure.value)
        self.assertFalse(view.get_write_occurred())

    def test_update_lines_replaces_range(self) -> None:
        view = self._file_view()
        self._numbered_read(view)
        result = self.assert_supersedes(
            view.update_lines("test.txt", 2, 2, "Line 2: replaced"), True
        )
        self.assertEqual(result.content, "Replaced lines 2-2 in test.txt")
        self.assertTrue(view.get_write_occurred())
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("Line 2: replaced", f.read())

    def test_update_lines_deletes_range(self) -> None:
        view = self._file_view()
        self._numbered_read(view)
        result = self.assert_supersedes(
            view.update_lines("test.txt", 2, 3, ""), True
        )
        self.assertEqual(result.content, "Deleted lines 2-3 in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        self.assertNotIn("Line 2:", file_content)
        self.assertNotIn("Line 3:", file_content)
        self.assertIn("Line 4: Final line", file_content)

    def test_update_lines_inserts_before_line(self) -> None:
        # start_line > end_line inserts new_str before start_line (no lines
        # removed).
        view = self._file_view()
        self._numbered_read(view)
        result = self.assert_supersedes(
            view.update_lines("test.txt", 2, 1, "inserted"), True
        )
        self.assertEqual(result.content, "Inserted content before line 2 in test.txt")
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertIn("inserted", f.read())

    def test_update_lines_out_of_bounds_fails_with_line_count(self) -> None:
        view = self._file_view()
        self._numbered_read(view)
        failure = self.as_tool_failure(
            view.update_lines("test.txt", 99, 100, "x")
        )
        self.assertIn("between", failure.value)
        self.assertIn("4 lines", failure.value)

    def test_update_lines_non_integer_lines_fail(self) -> None:
        view = self._file_view()
        failure = self.as_tool_failure(
            view.update_lines("test.txt", "1", "1", "x")
        )
        self.assertIn("integers", failure.value)

    def test_update_lines_empty_file_insert(self) -> None:
        empty_path = os.path.join(self.temp_dir, "empty.txt")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")
        view = self._file_view(
            file_mappings={"empty.txt": empty_path},
            readable_paths=["empty.txt"],
            writable_paths=["empty.txt"],
        )
        self._numbered_read(view, "empty.txt")
        # Insertion with start_line=1, end_line=0
        confirm = self.assert_supersedes(
            view.update_lines("empty.txt", 1, 0, "inserted line"), True
        )
        self.assertIn("Inserted content", confirm.content)
        with open(empty_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "inserted line")

        # Insertion with start_line=1, end_line=1 on empty file
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")
        self._numbered_read(view, "empty.txt")
        confirm2 = self.assert_supersedes(
            view.update_lines("empty.txt", 1, 1, "inserted line 2"), True
        )
        self.assertIn("Inserted content", confirm2.content)
        with open(empty_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "inserted line 2")

    # ------------------------------------------------------------------
    # search_files
    # ------------------------------------------------------------------

    def test_search_files_root_and_prefix_paths(self) -> None:
        sub = os.path.join(self.temp_dir, "sub")
        os.makedirs(sub, exist_ok=True)
        a_path = os.path.join(sub, "a.txt")
        b_path = os.path.join(sub, "b.txt")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("target needle in a\n")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write("target needle in b\n")
        view = self._file_view(
            file_mappings={"sub/a.txt": a_path, "sub/b.txt": b_path},
            readable_paths=["sub/a.txt", "sub/b.txt"],
            writable_paths=[],
        )
        # Search using "." searches all readable files
        res_dot = self.assert_supersedes(view.search_files(".", "needle"), False)
        self.assertIn("a.txt:1:", res_dot.content)
        self.assertIn("b.txt:1:", res_dot.content)
        self.assertIn("2 matches total", res_dot.note)

        # Search with omitted path defaults to "."
        res_default = self.assert_supersedes(view.search_files(pattern="needle"), False)
        self.assertIn("a.txt:1:", res_default.content)
        self.assertIn("b.txt:1:", res_default.content)

        # Search using "/" searches all readable files
        res_slash = self.assert_supersedes(view.search_files("/", "needle"), False)
        self.assertIn("a.txt:1:", res_slash.content)
        self.assertIn("b.txt:1:", res_slash.content)

        # Search using directory prefix "sub"
        res_prefix = self.assert_supersedes(view.search_files("sub", "needle"), False)
        self.assertIn("a.txt:1:", res_prefix.content)
        self.assertIn("b.txt:1:", res_prefix.content)

    def test_search_files_renders_only_non_writable_matches(self) -> None:
        # Rendered matches are matches found in files that are not writable;
        # matches in writable files are counted in the note without content.
        sub = os.path.join(self.temp_dir, "sub")
        os.makedirs(sub, exist_ok=True)
        a_path = os.path.join(sub, "a.txt")
        b_path = os.path.join(sub, "b.txt")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("needle in a\n")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write("needle in b\n")
        view = self._file_view(
            file_mappings={"dir": sub, "a.txt": a_path, "b.txt": b_path},
            readable_paths=["dir"],
            writable_paths=["b.txt"],
        )
        result = self.assert_supersedes(view.search_files("dir", "needle"), False)
        # The writable file's match is never rendered; only a.txt's is.
        self.assertIn("a.txt:1:", result.content)
        self.assertNotIn("b.txt:", result.content)
        self.assertIn("1 matches total", result.note)
        self.assertIn("1 match(es) in writable files not shown", result.note)

    def test_search_files_never_supersedes(self) -> None:
        # Search results never supersede an earlier result (matches in
        # writable files are never rendered, so they never become stale).
        view = self._file_view(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
        )
        result = self.assert_supersedes(view.search_files("test.txt", "Line"), False)
        self.assertIn("test.txt:1:", result.content)
        self.assertIn("4 matches total", result.note)

    def test_search_files_omitted_limit_fails_when_exceeds_limit(self) -> None:
        # An omitted limit means all rendered matches; allowed only within the
        # search result limit, otherwise the tool fails advising pagination.
        view = self._file_view(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
            search_result_limit=2,
        )
        failure = self.as_tool_failure(view.search_files("test.txt", "Line"))
        self.assertIn("search result limit", failure.value)

    def test_search_files_explicit_limit_above_max_fails(self) -> None:
        view = self._file_view(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
            search_result_limit=2,
        )
        failure = self.as_tool_failure(
            view.search_files("test.txt", "Line", limit=10)
        )
        self.assertIn("search result limit", failure.value)

    def test_search_files_pagination_with_limit_and_offset(self) -> None:
        # Pagination pages over rendered matches only: limit returns up to
        # `limit` matches from offset; the note reports how many remain and
        # the offset to continue from.
        view = self._file_view(
            file_mappings={"test.txt": self.test_file_path},
            readable_paths=["test.txt"],
            writable_paths=[],
            search_result_limit=2,
        )
        first = self.assert_supersedes(
            view.search_files("test.txt", "Line", limit=2), False
        )
        self.assertIn("test.txt:1:", first.content)
        self.assertIn("test.txt:2:", first.content)
        self.assertIn("2 more after this page", first.note)
        second = self.assert_supersedes(
            view.search_files("test.txt", "Line", offset=2, limit=2), False
        )
        self.assertIn("test.txt:3:", second.content)
        self.assertIn("0 more after this page", second.note)

    def test_search_files_invalid_pattern_fails(self) -> None:
        failure = self.as_tool_failure(
            self._file_view().search_files("ro.txt", "[")
        )
        self.assertIn("Invalid regex", failure.value)

    def test_search_files_policy_failures(self) -> None:
        view = self._file_view()
        not_mapped = self.as_tool_failure(view.search_files("nope.txt", "x"))
        self.assertIn("nope.txt", not_mapped.value)
        not_readable = self.as_tool_failure(
            self._file_view(
                file_mappings={"a.txt": self.test_file_path},
                readable_paths=[],
                writable_paths=["a.txt"],
            ).search_files("a.txt", "x")
        )
        self.assertIn("not readable", not_readable.value)

    # ------------------------------------------------------------------
    # State: write-occurred, changed files, snapshots, run freshness
    # ------------------------------------------------------------------

    def test_write_occurred_false_until_first_write_then_monotonic(self) -> None:
        view = self._file_view()
        self.assertFalse(view.get_write_occurred())
        self.assert_supersedes(
            view.replace("test.txt", "This is a test", "New content"), True
        )
        self.assertTrue(view.get_write_occurred())
        self.assertTrue(view.get_write_occurred())

    def test_template_init_does_not_set_write_occurred(self) -> None:
        # Template initialization is not a file write: the write-occurred
        # flag stays unset after a template materializes a file.
        templated = os.path.join(self.temp_dir, "templated.txt")
        view = self._file_view(
            file_mappings={"templated.txt": templated},
            readable_paths=["templated.txt"],
            writable_paths=["templated.txt"],
            templates={"templated.txt": "# templated\n"},
        )
        self.assertTrue(os.path.exists(templated))
        self.assertFalse(view.get_write_occurred())
        self.assertEqual(view.get_changed_files(), [])

    def test_changed_files_in_write_order_deduped_with_snapshots(self) -> None:
        # The changed set lists each written file once, in write order; the
        # run-start snapshot is the file's content before the run's first
        # write; current content reflects the latest write.
        view = self._file_view()
        original = "Line 1: Hello World\nLine 2: This is a test\nLine 3: Another line\nLine 4: Final line\n"
        self.assertEqual(view.get_changed_files(), [])
        self.assertIsNone(view.get_run_start_snapshot("test.txt"))
        self.assert_supersedes(
            view.replace("test.txt", "This is a test", "New content"), True
        )
        self.assert_supersedes(
            view.replace("second.txt", "Second line one", "Second: first"), True
        )
        self.assert_supersedes(
            view.replace("test.txt", "New content", "Newer content"), True
        )
        self.assertEqual(view.get_changed_files(), ["test.txt", "second.txt"])
        self.assertEqual(
            view.get_run_start_snapshot("test.txt"),
            original,
        )
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            self.assertEqual(view.get_current_content("test.txt"), f.read())

    def test_no_state_persists_across_runs(self) -> None:
        # A fresh FileViewImpl for the same configuration starts clean: no
        # write-occurred flag, no changed files, and no line-numbered view
        # mode (a line edit is refused until a numbered read).
        view1 = self._file_view()
        self.assert_supersedes(
            view1.replace("test.txt", "This is a test", "New content"), True
        )
        view2 = self._file_view()
        self.assertFalse(view2.get_write_occurred())
        self.assertEqual(view2.get_changed_files(), [])
        failure = self.as_tool_failure(view2.update_lines("test.txt", 1, 1, "x"))
        self.assertIn("include_line_numbers=True", failure.value)


class TestTemplateInitialization(unittest.TestCase):
    """Template initialization (specs/low/file_view_impl.md, Templates): a
    writable file with a configured template that does not exist on disk is
    created with the template's content at run start, before any tool call;
    an existing writable file is never modified; initialization is not a file
    write — it never sets the write-occurred flag and never records the file
    as changed (the template content is the run-start baseline)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

        self.templated_path = os.path.join(self.temp_dir, "artifact.md")
        self.existing_path = os.path.join(self.temp_dir, "existing.md")
        with open(self.existing_path, "w", encoding="utf-8") as f:
            f.write("existing content\n")

        self.file_mappings = {
            "artifact.md": self.templated_path,
            "existing.md": self.existing_path,
        }
        self.readable_paths = ["artifact.md", "existing.md"]
        self.writable_paths = ["artifact.md", "existing.md"]
        self.template_content = "# artifact\nTODO: fill me in\n"

    def _file_view(self, templates) -> FileViewImpl:
        return FileViewImpl(FileViewConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            templates=templates,
            search_result_limit=5,
            session_start_reads_enabled=True,
        ))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def test_template_initializes_missing_file_with_exact_content(self) -> None:
        """A writable file with a template that does not exist on disk exists
        at run start with exactly the template's content."""
        self.assertFalse(os.path.exists(self.templated_path))
        self._file_view({"artifact.md": self.template_content})
        self.assertTrue(os.path.exists(self.templated_path))
        with open(self.templated_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), self.template_content)

    def test_template_never_modifies_existing_file(self) -> None:
        """A writable file that exists at configuration is never modified by
        its template."""
        self._file_view({"existing.md": "template would overwrite"})
        with open(self.existing_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "existing content\n")

    def test_template_initialization_is_not_a_run_write(self) -> None:
        """Initialization is part of the file_view's configuration, not a
        write of the run: the write-occurred flag stays unset and the file is
        not recorded as changed."""
        view = self._file_view({"artifact.md": self.template_content})
        self.assertFalse(view.get_write_occurred())
        self.assertEqual(view.get_changed_files(), [])

    def test_template_content_is_the_run_start_baseline(self) -> None:
        """A file initialized from its template exists at run start, so its
        snapshot (captured on the run's first write) is the template's
        content."""
        view = self._file_view({"artifact.md": self.template_content})
        read = view.read_file("artifact.md", include_line_numbers=True)
        assert isinstance(read, list) and read
        self.assertTrue(read[0].supersedes)
        view.update_lines("artifact.md", 2, 2, "Filled in.")
        self.assertEqual(
            view.get_run_start_snapshot("artifact.md"),
            self.template_content,
        )
        with open(self.templated_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "# artifact\nFilled in.\n")

    def test_materialized_file_is_a_writable_file(self) -> None:
        """The materialized file is a writable file: a plain read of the
        existing file is rejected (line numbers are metadata), and the
        numbered read works."""
        view = self._file_view({"artifact.md": self.template_content})
        plain = view.read_file("artifact.md", include_line_numbers=False)
        self.assertIsInstance(plain, ToolFailure)
        result = view.read_file("artifact.md", include_line_numbers=True)
        assert isinstance(result, list) and result
        self.assertTrue(result[0].supersedes)
        self.assertIn("1 \u2502 # artifact", result[0].content)


class TestVirtualNameAddressing(unittest.TestCase):
    """Virtual-name addressing (specs/low/file_view.md, Virtual name):
    error messages name the virtual path, never the resolved filesystem
    path, and list the readable/writable paths."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

        self.real_path = os.path.join(self.temp_dir, "real_name.txt")
        with open(self.real_path, "w", encoding="utf-8") as f:
            f.write("Line 1\n")
            f.write("needle\n")

        # A mapped-but-missing file whose real path differs from its virtual
        # name: error messages must show the virtual name, never the real
        # on-disk path.
        self.missing_path = os.path.join(self.temp_dir, "missing_real.txt")

        self.file_mappings = {
            "alias.txt": self.real_path,
            "missing.txt": self.missing_path,
            "adir": self.temp_dir,
        }
        self.readable_paths = ["alias.txt", "missing.txt", "adir"]
        self.writable_paths = ["alias.txt"]

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def _file_view(self) -> FileViewImpl:
        return FileViewImpl(FileViewConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            templates={},
            search_result_limit=5,
            session_start_reads_enabled=True,
        ))

    def test_policy_failure_names_virtual_name_and_lists_readable(self) -> None:
        # A read of an unmapped file fails naming the virtual name and
        # listing the readable files.
        failure = self._file_view().read_file("nope.txt")
        assert isinstance(failure, ToolFailure)
        self.assertIn("nope.txt", failure.value)
        self.assertIn("alias.txt", failure.value)

    def test_read_missing_file_names_virtual_name_not_real_path(self) -> None:
        # A read of a mapped-but-missing file reports the missing file by
        # its virtual name; the resolved on-disk path never appears.
        failure = self._file_view().read_file("missing.txt")
        assert isinstance(failure, ToolFailure)
        self.assertIn("missing.txt", failure.value)
        self.assertNotIn(self.missing_path, failure.value)

    def test_search_missing_path_virtualizes_the_real_path(self) -> None:
        # search_files embeds the resolved path in its missing-path error;
        # the message is virtualized back to the virtual name before it
        # reaches the agent.
        failure = self._file_view().search_files("missing.txt", "x")
        assert isinstance(failure, ToolFailure)
        self.assertIn("missing.txt", failure.value)
        self.assertNotIn(self.missing_path, failure.value)

    def test_read_directory_names_virtual_name_not_real_path(self) -> None:
        # A read of a mapped directory (not a regular file) fails naming the
        # virtual name; the resolved directory path never appears.
        failure = self._file_view().read_file("adir")
        assert isinstance(failure, ToolFailure)
        self.assertIn("adir", failure.value)
        self.assertNotIn(self.temp_dir, failure.value)

    def test_sanitize_paths_replaces_full_and_relative_paths(self) -> None:
        fv = self._file_view()
        text = f"Error in {self.real_path} and pkg/subpkg/real_name.txt and //testing/lib:real_name"
        sanitized = fv.sanitize_paths(text)
        self.assertIn("alias.txt", sanitized)
        self.assertNotIn(self.real_path, sanitized)
        self.assertNotIn("pkg/subpkg/real_name.txt", sanitized)
        self.assertNotIn("//testing/lib:real_name", sanitized)


if __name__ == "__main__":
    unittest.main()

