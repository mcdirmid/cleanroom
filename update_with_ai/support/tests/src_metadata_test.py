"""Unit tests for in-band source metadata parsing and formatting."""

import unittest
from pathlib import Path
import tempfile
from update_with_ai.parts.control.lib.src_metadata import (
    FileMetadata,
    append_feedback,
    clear_audits,
    compute_code_hash,
    compute_file_code_hash,
    delete_last_cleaned,
    extract_code_body,
    extract_metadata,
    extract_metadata_from_text,
    format_metadata_block,
    is_code_modified,
    mark_clean,
    mark_dirty,
    record_change,
    rewrite_metadata_in_text,
    stamp_audit,
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
            append_feedback(
                file_path, "[2026-10-02T14:52:10Z from //other:test]: Contract error"
            )
            meta2 = extract_metadata(file_path)
            self.assertIsNotNone(meta2)
            assert meta2 is not None
            self.assertEqual(len(meta2.feedback), 2)
            self.assertEqual(
                meta2.feedback[1],
                "[2026-10-02T14:52:10Z from //other:test]: Contract error",
            )

    def test_extract_audit_tags(self) -> None:
        text = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-02T14:50:12Z
# CHANGE: Added AgentConfig protocol.
# QA_AUDIT: 2026-10-02T15:00:00Z
# COVERAGE_AUDIT: 2026-10-02T15:05:00Z
# FEEDBACK:
# - [2026-10-02T15:10:00Z from //test]: Fix me
# --- END CLEANROOM METADATA ---

x = 1
"""
        meta = extract_metadata_from_text(text, "agent_config.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.audits.get("QA_AUDIT"), "2026-10-02T15:00:00Z")
        self.assertEqual(meta.audits.get("COVERAGE_AUDIT"), "2026-10-02T15:05:00Z")
        self.assertEqual(len(meta.feedback), 1)

    def test_format_metadata_block_with_audits(self) -> None:
        meta = FileMetadata(
            last_cleaned="2026-10-02T15:00:00Z",
            last_changed="2026-10-02T14:50:00Z",
            change_summary="Feature implementation.",
            feedback=[],
            audits={
                "QA_AUDIT": "2026-10-02T15:00:00Z",
                "COVERAGE_AUDIT": "2026-10-02T15:02:00Z",
            },
        )
        lines = format_metadata_block(meta, is_html=False)
        formatted = "\n".join(lines)
        self.assertIn("# QA_AUDIT: 2026-10-02T15:00:00Z", formatted)
        self.assertIn("# COVERAGE_AUDIT: 2026-10-02T15:02:00Z", formatted)

    def test_stamp_audit_helper_preserves_last_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "mod.py"
            file_path.write_text(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                "# CHANGE: Feature.\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 42\n",
                encoding="utf-8",
            )
            stamp_audit(file_path, "qa")
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            # Non-bump invariant: last_changed must NOT be modified
            self.assertEqual(meta.last_changed, "2026-10-02T14:00:00Z")
            # last_cleaned and QA_AUDIT must be stamped
            self.assertIsNotNone(meta.last_cleaned)
            self.assertIn("QA_AUDIT", meta.audits)
            self.assertEqual(meta.audits["QA_AUDIT"], meta.last_cleaned)

            # Stamp another role: coverage
            stamp_audit(file_path, "coverage")
            meta2 = extract_metadata(file_path)
            self.assertIsNotNone(meta2)
            assert meta2 is not None
            self.assertEqual(meta2.last_changed, "2026-10-02T14:00:00Z")
            self.assertIn("QA_AUDIT", meta2.audits)
            self.assertIn("COVERAGE_AUDIT", meta2.audits)

    def test_record_change_clears_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "mod2.py"
            file_path.write_text(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                "# CHANGE: Feature.\n"
                "# QA_AUDIT: 2026-10-02T14:10:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 42\n",
                encoding="utf-8",
            )
            record_change(file_path, "New change")
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.change_summary, "New change")
            # Author edit invalidation: audits must be cleared
            self.assertEqual(meta.audits, {})

    def test_clear_audits_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "mod3.py"
            file_path.write_text(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                "# CHANGE: Feature.\n"
                "# QA_AUDIT: 2026-10-02T14:10:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 42\n",
                encoding="utf-8",
            )
            clear_audits(file_path)
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.audits, {})

    def test_parse_and_format_dirty_tag(self) -> None:
        text = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-04T16:00:00Z
# LAST_CHANGED: 2026-10-04T15:00:00Z
# CHANGE: Added feature
# DIRTY: Explicit nudge from user
# --- END CLEANROOM METADATA ---

x = 1
"""
        meta = extract_metadata_from_text(text, "foo.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.dirty, "Explicit nudge from user")
        self.assertEqual(meta.last_cleaned, "2026-10-04T16:00:00Z")

        # HTML formatting
        lines_html = format_metadata_block(meta, is_html=True)
        self.assertIn("DIRTY: Explicit nudge from user", "\n".join(lines_html))

        # Hash comment formatting
        lines_hash = format_metadata_block(meta, is_html=False)
        self.assertIn("# DIRTY: Explicit nudge from user", "\n".join(lines_hash))

    def test_mark_dirty_and_clear_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "mod_dirty.py"
            file_path.write_text(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-04T15:00:00Z\n"
                "# LAST_CHANGED: 2026-10-04T15:00:00Z\n"
                "# CHANGE: Initial clean.\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 42\n",
                encoding="utf-8",
            )
            # Mark dirty
            mark_dirty(file_path, "Manual check needed")
            meta = extract_metadata(file_path)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.dirty, "Manual check needed")
            self.assertIsNotNone(meta.last_cleaned)
            # LAST_CHANGED preserved
            self.assertEqual(meta.last_changed, "2026-10-04T15:00:00Z")

            # Mark clean clears DIRTY tag and updates LAST_CLEANED
            mark_clean(file_path)
            meta_clean = extract_metadata(file_path)
            self.assertIsNotNone(meta_clean)
            assert meta_clean is not None
            self.assertIsNone(meta_clean.dirty)
            self.assertIsNotNone(meta_clean.last_cleaned)

            # Record change also clears DIRTY tag
            mark_dirty(file_path, "Dirtied again")
            record_change(file_path, "Fixed it")
            meta_changed = extract_metadata(file_path)
            self.assertIsNotNone(meta_changed)
            assert meta_changed is not None
            self.assertIsNone(meta_changed.dirty)
            self.assertEqual(meta_changed.change_summary, "Fixed it")

    def test_code_hash_mechanics(self) -> None:
        """Verifies code hash computation excluding header, formatting, parsing, and modification checks."""
        py_content = (
            "# --- CLEANROOM METADATA ---\n"
            "# LAST_CLEANED: 2026-10-04T15:00:00Z\n"
            "# LAST_CHANGED: 2026-10-04T15:00:00Z\n"
            "# CHANGE: Initial.\n"
            "# --- END CLEANROOM METADATA ---\n"
            "\n"
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )
        body = extract_code_body(py_content, "math_utils.py")
        self.assertEqual(body, "def add(a: int, b: int) -> int:\n    return a + b")

        hash1 = compute_code_hash(py_content, "math_utils.py")
        self.assertEqual(len(hash1), 12)

        # Modifying metadata does NOT change the code hash
        py_content_different_meta = (
            "# --- CLEANROOM METADATA ---\n"
            "# LAST_CLEANED: 2026-10-04T16:00:00Z\n"
            "# LAST_CHANGED: 2026-10-04T16:00:00Z\n"
            "# CHANGE: Updated summary.\n"
            "# --- END CLEANROOM METADATA ---\n"
            "\n"
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )
        hash2 = compute_code_hash(py_content_different_meta, "math_utils.py")
        self.assertEqual(hash1, hash2)

        # Modifying code body DOES change the code hash
        py_content_diff_code = py_content.replace("a + b", "a + b + 1")
        hash3 = compute_code_hash(py_content_diff_code, "math_utils.py")
        self.assertNotEqual(hash1, hash3)

        # Markdown format
        md_content = (
            "<!-- CLEANROOM METADATA\n"
            "LAST_CLEANED: 2026-10-04T15:00:00Z\n"
            "LAST_CHANGED: 2026-10-04T15:00:00Z\n"
            "CHANGE: Spec.\n"
            "CODE_HASH: abcd1234efgh\n"
            "-->\n"
            "\n"
            "# Heading\n"
            "Body paragraph.\n"
        )
        md_meta = extract_metadata_from_text(md_content, "spec.md")
        self.assertIsNotNone(md_meta)
        assert md_meta is not None
        self.assertEqual(md_meta.code_hash, "abcd1234efgh")

        # File modification check with disk operations
        with tempfile.TemporaryDirectory() as tmp_dir:
            fpath = Path(tmp_dir) / "test_mod.py"
            fpath.write_text(py_content, encoding="utf-8")

            # Initially no CODE_HASH in file -> is_code_modified returns True
            self.assertTrue(is_code_modified(fpath))

            # Mark clean stamps CODE_HASH
            mark_clean(fpath)
            meta = extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.code_hash, hash1)
            self.assertFalse(is_code_modified(fpath))

            # Modify code body -> is_code_modified returns True
            fpath.write_text(
                fpath.read_text(encoding="utf-8") + "\n# Extra line\n", encoding="utf-8"
            )
            self.assertTrue(is_code_modified(fpath))

            # Record change updates CODE_HASH to match modified body
            record_change(fpath, "Added extra line")
            meta_after = extract_metadata(fpath)
            self.assertIsNotNone(meta_after)
            assert meta_after is not None
            self.assertFalse(is_code_modified(fpath))
            self.assertNotEqual(meta_after.code_hash, hash1)

    def test_preamble_and_docstring_hash_exclusion(self) -> None:
        """Verifies that files with docstrings or comments before the metadata block properly exclude metadata."""
        py_with_docstring = '''"""This is a module docstring."""

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-01T10:00:00Z
# CODE_HASH: 1234567890ab
# --- END CLEANROOM METADATA ---

def hello():
    return "world"
'''
        hash1 = compute_code_hash(py_with_docstring, "hello.py")

        # Mutating metadata inside the block must not alter the hash
        py_mutated_meta = '''"""This is a module docstring."""

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2099-01-01T00:00:00Z
# LAST_CHANGED: 2099-01-01T00:00:00Z
# CHANGE: some change
# CODE_HASH: 999999999999
# --- END CLEANROOM METADATA ---

def hello():
    return "world"
'''
        hash2 = compute_code_hash(py_mutated_meta, "hello.py")
        self.assertEqual(hash1, hash2)

        # But changing code outside metadata block changes the hash
        py_mutated_code = py_with_docstring.replace('"world"', '"universe"')
        hash3 = compute_code_hash(py_mutated_code, "hello.py")
        self.assertNotEqual(hash1, hash3)


if __name__ == "__main__":
    unittest.main()
