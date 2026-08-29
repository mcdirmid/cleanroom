"""
Tests for the FileReaderImpl implementation.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Optional, Tuple

from lib.file_reader import FileReaderConfig
from lib.file_reader_impl import FileReaderImpl
from lib.tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolResult,
    ToolFailure,
)


class TestFileReaderImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

        self.test_file_path = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\n")
            f.write("Line 2: This is a test\n")
            f.write("Line 3: Another line\n")
            f.write("Line 4: Final line\n")

        self.second_path = os.path.join(self.temp_dir, "second.txt")
        with open(self.second_path, "w", encoding="utf-8") as f:
            f.write("Second line one\n")
            f.write("Second line two\n")

        self.ro_path = os.path.join(self.temp_dir, "ro.txt")
        with open(self.ro_path, "w", encoding="utf-8") as f:
            f.write("Read only line 1\n")
            f.write("Read only line 2\n")

        self.new_file_path = os.path.join(self.temp_dir, "new.txt")

        self.file_mappings = {
            "test.txt": self.test_file_path,
            "second.txt": self.second_path,
            "ro.txt": self.ro_path,
            "new.txt": self.new_file_path,
        }
        self.readable_paths = ["test.txt", "second.txt", "ro.txt", "new.txt"]

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _file_reader(
        self,
        file_mappings: Optional[dict] = None,
        readable_paths: Optional[list] = None,
        search_result_limit: int = 5,
        session_start_reads_enabled: bool = True,
    ) -> FileReaderImpl:
        return FileReaderImpl(FileReaderConfig(
            file_mappings=file_mappings if file_mappings is not None else self.file_mappings,
            readable_paths=readable_paths if readable_paths is not None else self.readable_paths,
            search_result_limit=search_result_limit,
            session_start_reads_enabled=session_start_reads_enabled,
        ))

    def test_get_tool_definitions(self) -> None:
        reader = self._file_reader()
        defs = reader.get_tool_definitions()
        names = [d["function"]["name"] for d in defs]
        self.assertEqual(sorted(names), ["read_file", "search_files"])

    def test_read_file_plain(self) -> None:
        reader = self._file_reader()
        outcome = reader.read_file("ro.txt", include_line_numbers=False)
        self.assertIsInstance(outcome, list)
        self.assertEqual(len(outcome), 1)
        res = outcome[0]
        self.assertIsInstance(res, ToolResult)
        self.assertIn("Read only line 1", res.content)
        self.assertFalse(res.supersedes)

    def test_read_file_line_numbers(self) -> None:
        reader = self._file_reader()
        outcome = reader.read_file("test.txt", include_line_numbers=True)
        self.assertIsInstance(outcome, list)
        self.assertEqual(len(outcome), 1)
        res = outcome[0]
        self.assertIsInstance(res, ToolResult)
        self.assertIn("1 | Line 1: Hello World", res.content)
        self.assertFalse(res.supersedes)

    def test_read_file_unmapped(self) -> None:
        reader = self._file_reader()
        outcome = reader.read_file("missing.txt")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("does not exist", outcome.value)

    def test_read_file_not_readable(self) -> None:
        reader = self._file_reader(readable_paths=["ro.txt"])
        outcome = reader.read_file("test.txt")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("not readable", outcome.value)

    def test_read_file_missing_on_disk(self) -> None:
        reader = self._file_reader()
        outcome = reader.read_file("new.txt")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("does not exist yet", outcome.value)

    def test_session_start_reads_enabled(self) -> None:
        reader = self._file_reader(readable_paths=["ro.txt", "second.txt"])
        reads = reader.get_session_start_reads()
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[0].arguments["file_path"], "ro.txt")
        self.assertEqual(reads[1].arguments["file_path"], "second.txt")
        self.assertFalse(reads[0].result.supersedes)

    def test_session_start_reads_disabled(self) -> None:
        reader = self._file_reader(session_start_reads_enabled=False)
        self.assertEqual(reader.get_session_start_reads(), [])

    def test_session_start_reads_skips_missing(self) -> None:
        reader = self._file_reader(readable_paths=["new.txt"])
        self.assertEqual(reader.get_session_start_reads(), [])

    def test_search_files_basic(self) -> None:
        reader = self._file_reader()
        outcome = reader.search_files(path=".", pattern="Hello")
        self.assertIsInstance(outcome, list)
        res = outcome[0]
        self.assertIsInstance(res, ToolResult)
        self.assertIn("test.txt: Line 1: Hello World", res.content)
        self.assertFalse(res.supersedes)

    def test_search_files_specific_path(self) -> None:
        reader = self._file_reader()
        outcome = reader.search_files(path="ro.txt", pattern="Read only")
        self.assertIsInstance(outcome, list)
        res = outcome[0]
        self.assertIsInstance(res, ToolResult)
        self.assertIn("ro.txt: Read only line 1", res.content)

    def test_search_files_invalid_pattern(self) -> None:
        reader = self._file_reader()
        outcome = reader.search_files(path=".", pattern="[unclosed")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("Invalid regex", outcome.value)

    def test_search_files_pagination(self) -> None:
        reader = self._file_reader(search_result_limit=5)
        outcome = reader.search_files(path=".", pattern="Line", offset=0, limit=2)
        self.assertIsInstance(outcome, list)
        res = outcome[0]
        self.assertIsInstance(res, ToolResult)
        self.assertIn("2 remaining", res.note)

    def test_sanitize_paths(self) -> None:
        reader = self._file_reader()
        raw = f"Error at {self.test_file_path}: syntax error"
        sanitized = reader.sanitize_paths(raw)
        self.assertEqual(sanitized, "Error at test.txt: syntax error")


if __name__ == "__main__":
    unittest.main()
