"""Unit tests for in-band source metadata parsing and formatting."""

import unittest
from pathlib import Path
import tempfile
from support.lib.src_metadata import (
    FileMetadata,
    append_feedback,
    delete_last_cleaned,
    extract_metadata,
    extract_metadata_from_text,
    mark_clean,
    record_change,
    rewrite_metadata_in_text,
    update_metadata,
)


class SrcMetadataTest(unittest.TestCase):

    def test_extract_python_metadata(self) -> None:
        text = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-02T14:50:12Z
# CHANGE: Added AgentConfig protocol.
# FEEDBACK:
# - [2026-10-02T14:52:10Z from //parts/agent:agent_config_test]: Contract violation
# --- END CLEANROOM METADATA ---

from typing import Protocol
"""
        meta = extract_metadata_from_text(text, "agent_config.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.last_cleaned, "2026-10-02T14:55:48Z")
        self.assertEqual(meta.last_changed, "2026-10-02T14:50:12Z")
        self.assertEqual(meta.change_summary, "Added AgentConfig protocol.")
        self.assertEqual(len(meta.feedback), 1)
        self.assertIn("Contract violation", meta.feedback[0])

    def test_extract_markdown_metadata(self) -> None:
        text = """<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-02T14:40:00Z
LAST_CHANGED: 2026-10-02T14:35:10Z
CHANGE: Define fallback hierarchy.
-->

# agent_config specification
"""
        meta = extract_metadata_from_text(text, "agent_config.md")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.last_cleaned, "2026-10-02T14:40:00Z")
        self.assertEqual(meta.last_changed, "2026-10-02T14:35:10Z")
        self.assertEqual(meta.change_summary, "Define fallback hierarchy.")
        self.assertEqual(meta.feedback, [])

    def test_rewrite_python_metadata_existing(self) -> None:
        original = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-02T14:50:12Z
# CHANGE: Old change.
# FEEDBACK:
# - [2026-10-02T14:52:10Z from test]: Fix bug
# --- END CLEANROOM METADATA ---

def foo(): pass
"""
        updated = rewrite_metadata_in_text(
            original,
            "foo.py",
            last_cleaned="2026-10-02T15:00:00Z",
            last_changed="2026-10-02T15:00:00Z",
            change_summary="New change.",
            clear_feedback=True,
        )
        meta = extract_metadata_from_text(updated, "foo.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.last_cleaned, "2026-10-02T15:00:00Z")
        self.assertEqual(meta.last_changed, "2026-10-02T15:00:00Z")
        self.assertEqual(meta.change_summary, "New change.")
        self.assertEqual(meta.feedback, [])
        self.assertIn("def foo(): pass", updated)

    def test_rewrite_python_metadata_insert_shebang(self) -> None:
        original = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def main(): pass
"""
        updated = rewrite_metadata_in_text(
            original,
            "script.py",
            last_cleaned="2026-10-02T15:00:00Z",
            last_changed="2026-10-02T15:00:00Z",
            change_summary="Created script.",
        )
        lines = updated.splitlines()
        self.assertEqual(lines[0], "#!/usr/bin/env python3")
        self.assertEqual(lines[1], "# -*- coding: utf-8 -*-")
        self.assertEqual(lines[2], "# --- CLEANROOM METADATA ---")
        self.assertIn("def main(): pass", updated)

    def test_rewrite_markdown_metadata_insert_frontmatter(self) -> None:
        original = """---
title: Doc
---

# Hello World
"""
        updated = rewrite_metadata_in_text(
            original,
            "doc.md",
            last_cleaned="2026-10-02T15:00:00Z",
            last_changed="2026-10-02T15:00:00Z",
            change_summary="Created doc.",
        )
        lines = updated.splitlines()
        self.assertEqual(lines[0], "---")
        self.assertEqual(lines[1], "title: Doc")
        self.assertEqual(lines[2], "---")
        self.assertEqual(lines[3], "<!-- CLEANROOM METADATA")
        self.assertIn("# Hello World", updated)

    def test_append_feedback(self) -> None:
        original = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-02T14:50:12Z
# CHANGE: Added feature.
# --- END CLEANROOM METADATA ---

code = 1
"""
        updated = rewrite_metadata_in_text(
            original,
            "test.py",
            append_feedback="[2026-10-02T15:10:00Z from //test:target]: Assertion failed",
        )
        meta = extract_metadata_from_text(updated, "test.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(len(meta.feedback), 1)
        self.assertEqual(
            meta.feedback[0],
            "[2026-10-02T15:10:00Z from //test:target]: Assertion failed",
        )

    def test_file_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.py"
            file_path.write_text("print('hello')\n", encoding="utf-8")

            update_metadata(
                file_path,
                last_cleaned="2026-10-02T16:00:00Z",
                last_changed="2026-10-02T16:00:00Z",
                change_summary="First write.",
            )

            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.last_cleaned, "2026-10-02T16:00:00Z")
            self.assertIn("print('hello')", file_path.read_text(encoding="utf-8"))

    def test_clear_last_cleaned(self) -> None:
        original = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-02T14:50:12Z
# CHANGE: Previous change.
# --- END CLEANROOM METADATA ---

x = 1
"""
        updated = rewrite_metadata_in_text(
            original,
            "x.py",
            clear_last_cleaned=True,
            change_summary="Nudged dirty.",
        )
        meta = extract_metadata_from_text(updated, "x.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertIsNone(meta.last_cleaned)
        self.assertEqual(meta.last_changed, "2026-10-02T14:50:12Z")
        self.assertEqual(meta.change_summary, "Nudged dirty.")
        self.assertNotIn("LAST_CLEANED:", updated)

    def test_delete_last_cleaned_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test.py"
            file_path.write_text(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:55:48Z\n"
                "# LAST_CHANGED: 2026-10-02T14:50:12Z\n"
                "# CHANGE: Initial.\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 1\n",
                encoding="utf-8",
            )
            delete_last_cleaned(file_path)
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIsNone(meta.last_cleaned)
            self.assertEqual(meta.last_changed, "2026-10-02T14:50:12Z")
            self.assertEqual(meta.change_summary, "Initial.")

    def test_mark_clean_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "fresh.py"
            file_path.write_text("x = 10\n", encoding="utf-8")
            mark_clean(file_path)
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIsNotNone(meta.last_cleaned)
            self.assertIsNotNone(meta.last_changed)
            self.assertEqual(meta.last_cleaned, meta.last_changed)
            self.assertEqual(meta.change_summary, "new file")
            self.assertEqual(meta.feedback, [])

    def test_record_change_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "changed.py"
            file_path.write_text(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                "# CHANGE: Old.\n"
                "# FEEDBACK:\n"
                "# - [2026-10-02T14:10:00Z from test]: Fix me\n"
                "# --- END CLEANROOM METADATA ---\n"
                "y = 20\n",
                encoding="utf-8",
            )
            record_change(file_path, "Refactored module.")
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.change_summary, "Refactored module.")
            self.assertEqual(meta.feedback, [])
            self.assertEqual(meta.last_cleaned, meta.last_changed)

    def test_append_feedback_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "fb.py"
            file_path.write_text("z = 30\n", encoding="utf-8")
            append_feedback(file_path, "First defect")
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(len(meta.feedback), 1)
            self.assertIn("from user]: First defect", meta.feedback[0])

            # Append pre-formatted feedback
            append_feedback(file_path, "[2026-10-02T14:52:10Z from //other:test]: Contract error")
            meta2 = extract_metadata(file_path)
            self.assertIsNotNone(meta2)
            assert meta2 is not None
            self.assertEqual(len(meta2.feedback), 2)
            self.assertEqual(meta2.feedback[1], "[2026-10-02T14:52:10Z from //other:test]: Contract error")


if __name__ == "__main__":
    unittest.main()
