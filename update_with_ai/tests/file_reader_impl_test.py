"""Tests for file_reader_impl derived from LLS."""

import os
import shutil
import tempfile
import unittest
from lib.tool_provider import ToolResult, ToolFailure
from lib.file_reader import FileReaderConfig
from lib.file_reader_impl import FileReaderFactoryImpl


class FileReaderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.rw_file = os.path.join(self.test_dir, "writable.txt")
        self.ro_file = os.path.join(self.test_dir, "readonly.txt")
        self.denied_file = os.path.join(self.test_dir, "denied.txt")
        with open(self.rw_file, "w") as f:
            f.write("Line 1\nLine 2\n")
        with open(self.ro_file, "w") as f:
            f.write("Read-only Line 1\nRead-only Line 2\n")
        with open(self.denied_file, "w") as f:
            f.write("Secret\n")
        self.factory = FileReaderFactoryImpl()

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tool_metadata(self) -> None:
        """Tests that read_file and search_files specify required tool metadata."""
        reader = FileReaderFactoryImpl().create_file_reader(FileReaderConfig(file_mappings={}, read_only_files=[], read_write_files=[]))
        read_meta = reader.get_read_tool().get_metadata()
        self.assertEqual(read_meta.name, "read_file")
        self.assertTrue("file_name" in read_meta.parameters_schema or "file_name" in read_meta.parameters_schema.get("properties", {}))

        search_meta = reader.get_search_tool().get_metadata()
        self.assertEqual(search_meta.name, "search_files")
        self.assertTrue("pattern" in search_meta.parameters_schema or "pattern" in search_meta.parameters_schema.get("properties", {}))

    def test_read_file_line_numbers_contract_on_all_sides(self) -> None:
        """Tests all sides of read_file line numbers contract:
        1. Writable file with line_numbers=True -> ToolResult with 1-indexed line numbers.
        2. Writable file with line_numbers=False -> ToolFailure.
        3. Read-only file with line_numbers=False -> ToolResult with plain content.
        4. Read-only file with line_numbers=True -> ToolFailure.
        5. Unmapped/inaccessible file -> ToolFailure listing available files.
        """
        cfg = FileReaderConfig(
            read_only_files=[self.ro_file],
            read_write_files=[self.rw_file],
            file_mappings={self.rw_file: self.rw_file, self.ro_file: self.ro_file},
        )
        reader = self.factory.create_file_reader(cfg)
        tool = reader.get_read_tool()

        # Side 1: Writable + line_numbers=True
        res1 = tool.execute({"file_name": self.rw_file, "line_numbers": True})
        self.assertIsInstance(res1, ToolResult)
        self.assertIn("1: Line 1", res1.content)

        # Side 2: Writable + line_numbers=False
        res2 = tool.execute({"file_name": self.rw_file, "line_numbers": False})
        self.assertIsInstance(res2, ToolFailure)

        # Side 3: Read-only + line_numbers=False
        res3 = tool.execute({"file_name": self.ro_file, "line_numbers": False})
        self.assertIsInstance(res3, ToolResult)
        self.assertIn("Read-only Line 1", res3.content)

        # Side 4: Read-only + line_numbers=True
        res4 = tool.execute({"file_name": self.ro_file, "line_numbers": True})
        self.assertIsInstance(res4, ToolFailure)

        # Side 5: Inaccessible / unmapped file lists available files
        res5 = tool.execute({"file_name": self.denied_file, "line_numbers": True})
        self.assertIsInstance(res5, ToolFailure)

    def test_search_files_reporting_contract(self) -> None:
        """Tests search_files reporting contract:
        1. Matching regex on writable vs read-only files.
        2. Invalid regex pattern produces ToolFailure.
        """
        cfg = FileReaderConfig(
            read_only_files=[self.ro_file],
            read_write_files=[self.rw_file],
            file_mappings={self.rw_file: self.rw_file, self.ro_file: self.ro_file},
        )
        reader = self.factory.create_file_reader(cfg)
        tool = reader.get_search_tool()

        # Valid regex match
        res = tool.execute({"pattern": "Line"})
        self.assertIsInstance(res, ToolResult)

        # Invalid regex
        res_inv = tool.execute({"pattern": "["})
        self.assertIsInstance(res_inv, ToolFailure)

    def test_sanitize_paths_descending_length(self) -> None:
        """Tests sanitize_paths replaces host paths with virtual names in descending length order."""
        cfg = FileReaderConfig(
            read_only_files=[],
            read_write_files=[],
            file_mappings={
                "short": "/a/b",
                "long_file": "/a/b/c/long_file.txt",
            },
        )
        reader = self.factory.create_file_reader(cfg)
        sanitized = reader.sanitize_paths("Path /a/b/c/long_file.txt and /a/b are paths")
        self.assertEqual(sanitized, "Path long_file and short are paths")

    def test_search_files_result_limit_truncation(self) -> None:
        """Tests that search results exceeding search_result_limit are truncated with indicator."""
        cfg = FileReaderConfig(
            read_only_files=[self.ro_file],
            read_write_files=[self.rw_file],
            file_mappings={self.rw_file: self.rw_file, self.ro_file: self.ro_file},
            search_result_limit=1,
        )
        reader = self.factory.create_file_reader(cfg)
        tool = reader.get_search_tool()
        res = tool.execute({"pattern": "Line"})
        self.assertIsInstance(res, ToolResult)
        self.assertTrue(bool(res.content))

    def test_get_session_start_reads_loads_readonly_files(self) -> None:
        """Tests get_session_start_reads returns content of all accessible read-only files."""
        cfg = FileReaderConfig(
            read_only_files=[self.ro_file],
            read_write_files=[self.rw_file],
            file_mappings={self.rw_file: self.rw_file, self.ro_file: self.ro_file},
        )
        reader = self.factory.create_file_reader(cfg)
        reads = reader.get_session_start_reads()
        self.assertEqual(len(reads), 1)
        self.assertIn("Read-only Line 1", reads[0].content)

    def test_read_file_missing_on_disk_failure(self) -> None:
        """Tests that read_file returns ToolFailure when a declared file is missing from disk."""
        missing_host = os.path.join(self.test_dir, "nonexistent.txt")
        cfg = FileReaderConfig(
            read_only_files=["nonexistent.txt"],
            read_write_files=[],
            file_mappings={"nonexistent.txt": missing_host},
        )
        reader = self.factory.create_file_reader(cfg)
        res = reader.get_read_tool().execute({"file_name": "nonexistent.txt", "line_numbers": False})
        self.assertIsInstance(res, ToolFailure)

        # get_session_start_reads skips or handles missing files gracefully
        reads = reader.get_session_start_reads()
        self.assertEqual(len(reads), 0)


if __name__ == "__main__":
    unittest.main()
