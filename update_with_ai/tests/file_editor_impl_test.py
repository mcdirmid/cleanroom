"""Tests for file_editor_impl derived from LLS."""

import os
import shutil
import tempfile
import unittest
from lib.tool_provider import ToolResult, ToolFailure
from lib.file_editor import FileEditorConfig
from lib.file_editor_impl import FileEditorFactoryImpl


class FileEditorImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.target_host_file = os.path.join(self.test_dir, "file.txt")
        with open(self.target_host_file, "w") as f:
            f.write("Line 1\nLine 2\nLine 3\n")
        self.virtual_file = "file.txt"
        self.factory = FileEditorFactoryImpl()

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tool_metadata(self) -> None:
        """Tests that replace and update_lines specify required tool metadata."""
        editor = self.factory.create_file_editor(FileEditorConfig(file_mappings={}, templates={}, read_write_files=[]))
        replace_meta = editor.get_replacement_tool().get_metadata()
        self.assertEqual(replace_meta.name, "replace")
        self.assertTrue("file_name" in replace_meta.parameters_schema or "file_name" in replace_meta.parameters_schema.get("properties", {}))

        line_meta = editor.get_line_update_tool().get_metadata()
        self.assertEqual(line_meta.name, "update_lines")
        self.assertTrue("file_name" in line_meta.parameters_schema or "file_name" in line_meta.parameters_schema.get("properties", {}))
        self.assertTrue("start_line" in line_meta.parameters_schema or "start_line" in line_meta.parameters_schema.get("properties", {}))
        self.assertTrue("end_line" in line_meta.parameters_schema or "end_line" in line_meta.parameters_schema.get("properties", {}))

    def test_replacement_tool_exact_match_and_failures(self) -> None:
        """Tests replacement tool boundary sides:
        1. Unique target content -> replaced successfully.
        2. Non-matching target content -> ToolFailure.
        3. Ambiguous multiple match content -> ToolFailure.
        4. Target text exceeding 100,000 characters -> ToolFailure.
        """
        cfg = FileEditorConfig(
            read_write_files=[self.virtual_file],
            file_mappings={self.virtual_file: self.target_host_file},
            templates={},
        )
        editor = self.factory.create_file_editor(cfg)
        replace_tool = editor.get_replacement_tool()

        # Success
        res = replace_tool.execute({
            "file_name": self.virtual_file,
            "target_content": "Line 2",
            "replacement_content": "Updated Line 2",
        })
        self.assertIsInstance(res, ToolResult)
        with open(self.target_host_file) as f:
            self.assertEqual(f.read(), "Line 1\nUpdated Line 2\nLine 3\n")

        # Non-matching failure
        res_fail = replace_tool.execute({
            "file_name": self.virtual_file,
            "target_content": "Non existent string",
            "replacement_content": "New",
        })
        self.assertIsInstance(res_fail, ToolFailure)

        # Exceeding size limit failure
        huge_text = "x" * 100001
        res_huge = replace_tool.execute({
            "file_name": self.virtual_file,
            "target_content": huge_text,
            "replacement_content": "New",
        })
        self.assertIsInstance(res_huge, ToolFailure)

    def test_line_update_tool_bounds(self) -> None:
        """Tests line update tool bounds:
        1. Valid 1-indexed range -> replaced successfully.
        2. Out-of-bounds start/end -> ToolFailure.
        """
        cfg = FileEditorConfig(
            read_write_files=[self.virtual_file],
            file_mappings={self.virtual_file: self.target_host_file},
            templates={},
        )
        editor = self.factory.create_file_editor(cfg)
        line_tool = editor.get_line_update_tool()

        res = line_tool.execute({
            "file_name": self.virtual_file,
            "start_line": 1,
            "end_line": 2,
            "replacement_text": "Replaced lines 1 and 2\n",
        })
        self.assertIsInstance(res, ToolResult)
        with open(self.target_host_file) as f:
            self.assertEqual(f.read(), "Replaced lines 1 and 2\nLine 3\n")

        # Out-of-bounds
        res_oob = line_tool.execute({
            "file_name": self.virtual_file,
            "start_line": 100,
            "end_line": 200,
            "replacement_text": "Invalid",
        })
        self.assertIsInstance(res_oob, ToolFailure)

    def test_line_update_insertion_and_deletion(self) -> None:
        """Tests line update invariants:
        1. start_line > end_line performs insertion at start_line without deleting lines.
        2. empty replacement_text deletes the specified line range.
        """
        cfg = FileEditorConfig(
            read_write_files=[self.virtual_file],
            file_mappings={self.virtual_file: self.target_host_file},
            templates={},
        )
        editor = self.factory.create_file_editor(cfg)
        line_tool = editor.get_line_update_tool()

        # Insertion: start_line=2, end_line=1 -> insert before line 2
        res_insert = line_tool.execute({
            "file_name": self.virtual_file,
            "start_line": 2,
            "end_line": 1,
            "replacement_text": "Inserted Line\n",
        })
        self.assertFalse(isinstance(res_insert, ToolFailure), getattr(res_insert, "feedback", ""))
        self.assertIsInstance(res_insert, ToolResult)
        with open(self.target_host_file) as f:
            self.assertEqual(f.read(), "Line 1\nInserted Line\nLine 2\nLine 3\n")

        # Deletion: delete line 2 ("Inserted Line\n")
        res_del = line_tool.execute({
            "file_name": self.virtual_file,
            "start_line": 2,
            "end_line": 2,
            "replacement_text": "",
        })
        self.assertIsInstance(res_del, ToolResult)
        with open(self.target_host_file) as f:
            self.assertEqual(f.read(), "Line 1\nLine 2\nLine 3\n")

    def test_materialize_templates_does_not_overwrite_existing(self) -> None:
        """Tests template materialization:
        1. Missing file -> writes starter template.
        2. Existing file -> preserves existing content without overwrite.
        """
        missing_host_file = os.path.join(self.test_dir, "missing.txt")
        cfg = FileEditorConfig(
            read_write_files=[self.virtual_file, "missing.txt"],
            file_mappings={
                self.virtual_file: self.target_host_file,
                "missing.txt": missing_host_file,
            },
            templates={
                self.virtual_file: "Template overwrite attempt",
                "missing.txt": "Starter template content",
            },
        )
        editor = self.factory.create_file_editor(cfg)
        editor.materialize_templates()

        self.assertTrue(os.path.isfile(missing_host_file))
        with open(missing_host_file) as f:
            self.assertEqual(f.read(), "Starter template content")

        with open(self.target_host_file) as f:
            self.assertNotIn("Template overwrite attempt", f.read())

    def test_replacement_tool_not_read_write_or_missing(self) -> None:
        """Tests that replace tool returns ToolFailure for undeclared or missing files."""
        cfg = FileEditorConfig(
            read_write_files=[self.virtual_file],
            file_mappings={self.virtual_file: self.target_host_file},
            templates={},
        )
        editor = self.factory.create_file_editor(cfg)
        tool = editor.get_replacement_tool()

        # Not in read_write_files
        res_not_rw = tool.execute({
            "file_name": "other.txt",
            "target_content": "Line",
            "replacement_content": "New",
        })
        self.assertIsInstance(res_not_rw, ToolFailure)
        self.assertTrue(bool(res_not_rw.feedback))

        # In read_write_files but missing on disk
        missing_host = os.path.join(self.test_dir, "missing_on_disk.txt")
        cfg2 = FileEditorConfig(
            read_write_files=["missing_on_disk.txt"],
            file_mappings={"missing_on_disk.txt": missing_host},
            templates={},
        )
        tool2 = self.factory.create_file_editor(cfg2).get_replacement_tool()
        res_missing = tool2.execute({
            "file_name": "missing_on_disk.txt",
            "target_content": "Line",
            "replacement_content": "New",
        })
        self.assertIsInstance(res_missing, ToolFailure)
        self.assertTrue(bool(res_missing.feedback))

    def test_replacement_tool_multiple_occurrences_fails(self) -> None:
        """Tests that replace tool fails when target_content matches multiple locations."""
        multi_file = os.path.join(self.test_dir, "multi.txt")
        with open(multi_file, "w") as f:
            f.write("duplicate\nfoo\nduplicate\n")

        cfg = FileEditorConfig(
            read_write_files=["multi.txt"],
            file_mappings={"multi.txt": multi_file},
            templates={},
        )
        editor = self.factory.create_file_editor(cfg)
        res = editor.get_replacement_tool().execute({
            "file_name": "multi.txt",
            "target_content": "duplicate",
            "replacement_content": "single",
        })
        self.assertIsInstance(res, ToolFailure)
        self.assertTrue(bool(res.feedback))

    def test_line_update_not_read_write_or_missing(self) -> None:
        """Tests that update_lines tool returns ToolFailure for undeclared or missing files."""
        cfg = FileEditorConfig(
            read_write_files=[self.virtual_file],
            file_mappings={self.virtual_file: self.target_host_file},
            templates={},
        )
        editor = self.factory.create_file_editor(cfg)
        tool = editor.get_line_update_tool()

        res_not_rw = tool.execute({
            "file_name": "other.txt",
            "start_line": 1,
            "end_line": 1,
            "replacement_text": "New",
        })
        self.assertIsInstance(res_not_rw, ToolFailure)

        missing_host = os.path.join(self.test_dir, "missing_on_disk.txt")
        cfg2 = FileEditorConfig(
            read_write_files=["missing_on_disk.txt"],
            file_mappings={"missing_on_disk.txt": missing_host},
            templates={},
        )
        tool2 = self.factory.create_file_editor(cfg2).get_line_update_tool()
        res_missing = tool2.execute({
            "file_name": "missing_on_disk.txt",
            "start_line": 1,
            "end_line": 1,
            "replacement_text": "New",
        })
        self.assertIsInstance(res_missing, ToolFailure)


if __name__ == "__main__":
    unittest.main()
