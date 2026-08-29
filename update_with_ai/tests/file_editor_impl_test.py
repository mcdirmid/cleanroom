"""
Tests for the FileEditorImpl implementation.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Optional, Tuple

from lib.file_reader import FileReader
from lib.file_editor import FileEditorConfig
from lib.file_editor_impl import FileEditorImpl
from lib.tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolResult,
    ToolFailure,
)



class _MockFileReader(FileReader):
    def __init__(self, file_mappings: dict[str, str], readable_paths: list[str]) -> None:
        self.file_mappings = file_mappings
        self.readable_paths = readable_paths
        self.calls: list[tuple[str, Any]] = []

    def get_readable_paths(self) -> list[str]:
        self.calls.append(("get_readable_paths", ()))
        return list(self.readable_paths)

    def is_readable(self, path: str) -> bool:
        self.calls.append(("is_readable", (path,)))
        return path in self.readable_paths

    def resolve_path(self, path: str) -> str:
        self.calls.append(("resolve_path", (path,)))
        if path not in self.readable_paths:
            raise ValueError(f"Path not readable: {path}")
        return self.file_mappings.get(path, path)

    def read_file(self, path: str, line_numbers: bool = True) -> PresentedToolResult:
        self.calls.append(("read_file", (path, line_numbers)))
        if path not in self.readable_paths:
            return [ToolFailure(f"Path not readable: {path}")]
        real_path = self.file_mappings.get(path, path)
        if not os.path.exists(real_path):
            return [ToolFailure(f"File not found: {path}")]
        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()
        return [ToolResult(content=content)]

    def get_file_size(self, path: str) -> int:
        self.calls.append(("get_file_size", (path,)))
        real_path = self.file_mappings.get(path, path)
        return os.path.getsize(real_path) if os.path.exists(real_path) else 0


class TestFileEditorImpl(unittest.TestCase):
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
        self.writable_paths = ["test.txt", "second.txt", "new.txt"]

        self.reader = _MockFileReader(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _file_editor(
        self,
        writable_paths: Optional[list] = None,
        templates: Optional[dict] = None,
    ) -> FileEditorImpl:
        return FileEditorImpl(
            FileEditorConfig(
                writable_paths=writable_paths if writable_paths is not None else self.writable_paths,
                templates=templates if templates is not None else {},
            ),
            file_reader=self.reader,
        )

    def test_get_tool_definitions(self) -> None:
        editor = self._file_editor()
        defs = editor.get_tool_definitions()
        names = [d["function"]["name"] for d in defs]
        self.assertEqual(sorted(names), ["replace", "update_lines"])

    def test_replace_single_occurrence(self) -> None:
        editor = self._file_editor()
        self.assertFalse(editor.get_write_occurred())

        outcome = editor.replace("test.txt", old_str="Hello World", new_str="Cleanroom")
        self.assertIsInstance(outcome, list)
        self.assertEqual(len(outcome), 2)
        confirm, injected = outcome
        self.assertIsInstance(confirm, ToolResult)
        self.assertTrue(confirm.supersedes)
        self.assertIsInstance(injected, PresentedToolResult)
        self.assertTrue(injected.result.supersedes)
        self.assertIn("Cleanroom", injected.result.content)

        self.assertTrue(editor.get_write_occurred())
        self.assertEqual(editor.get_changed_files(), ["test.txt"])
        self.assertIn("Hello World", str(editor.get_run_start_snapshot("test.txt")))

    def test_replace_read_only_fails(self) -> None:
        editor = self._file_editor(writable_paths=["test.txt"])
        outcome = editor.replace("ro.txt", old_str="Read only", new_str="Write")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("read-only", outcome.value)

    def test_replace_overlong_string(self) -> None:
        editor = self._file_editor()
        overlong = "x" * 201
        outcome = editor.replace("test.txt", old_str=overlong, new_str="bar")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("replace supports strings up to 200 chars", outcome.value)

    def test_replace_empty_old_str(self) -> None:
        editor = self._file_editor()
        outcome = editor.replace("test.txt", old_str="", new_str="bar")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("empty", outcome.value)

    def test_update_lines_requires_line_numbered_view_if_not_read(self) -> None:
        editor = self._file_editor()
        outcome = editor.update_lines("test.txt", start_line=1, end_line=1, new_str="Replaced\n")
        self.assertIsInstance(outcome, ToolFailure)
        self.assertIn("requires line-numbered view", outcome.value)

    def test_update_lines_after_injected_read(self) -> None:
        editor = self._file_editor()
        editor.replace("test.txt", old_str="Hello World", new_str="World")
        # Injected read enabled line numbers!
        outcome = editor.update_lines("test.txt", start_line=2, end_line=2, new_str="Line 2: Updated\n")
        self.assertIsInstance(outcome, list)
        self.assertEqual(len(outcome), 2)
        injected = outcome[1]
        self.assertIn("Line 2: Updated", injected.result.content)

    def test_update_lines_delete(self) -> None:
        editor = self._file_editor()
        editor.replace("test.txt", old_str="Hello World", new_str="World")
        outcome = editor.update_lines("test.txt", start_line=1, end_line=2, new_str="")
        self.assertIsInstance(outcome, list)
        injected = outcome[1]
        self.assertNotIn("Line 1", injected.result.content)

    def test_update_lines_insert(self) -> None:
        editor = self._file_editor()
        editor.replace("test.txt", old_str="Hello World", new_str="World")
        outcome = editor.update_lines("test.txt", start_line=2, end_line=1, new_str="Inserted line\n")
        self.assertIsInstance(outcome, list)
        injected = outcome[1]
        self.assertIn("Inserted line", injected.result.content)

    def test_template_initialization_on_missing_file(self) -> None:
        editor = self._file_editor(templates={"new.txt": "Initial template content\n"})
        self.assertTrue(os.path.exists(self.new_file_path))
        with open(self.new_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "Initial template content\n")
        self.assertFalse(editor.get_write_occurred())

    def test_template_preserves_existing_file(self) -> None:
        editor = self._file_editor(templates={"test.txt": "Overwritten content\n"})
        with open(self.test_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Line 1: Hello World", content)


if __name__ == "__main__":
    unittest.main()
