# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T14:35:00Z
# CHANGE: new file
# CODE_HASH: 2bdf38c8bd30
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

from pathlib import Path
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.control.lib import src_metadata, src_metadata_impl


class SrcMetadataImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.coordinator = src_metadata_impl.SourceMetadataCoordinator()
        self.registry.register_instance(
            self.coordinator,
            keys=[
                src_metadata.SourceMetadataCoordinator,
                src_metadata_impl.SourceMetadataCoordinator,
            ],
        )

    def test_extract_python_metadata(self) -> None:
        text = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-02T14:50:12Z
# CHANGE: Added AgentConfig protocol.
# CODE_HASH: abc123def456
# DIRTY: test dirty
# QA_AUDIT: 2026-10-02T14:55:00Z
# FEEDBACK:
# - [2026-10-02T14:52:10Z from //parts/agent:agent_config_test]: Contract violation
# --- END CLEANROOM METADATA ---

from typing import Protocol
"""
        meta = self.coordinator.extract_metadata_from_text(text, "agent_config.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.last_cleaned, "2026-10-02T14:55:48Z")
        self.assertEqual(meta.last_changed, "2026-10-02T14:50:12Z")
        self.assertEqual(meta.change_summary, "Added AgentConfig protocol.")
        self.assertEqual(meta.code_hash, "abc123def456")
        self.assertEqual(meta.dirty, "test dirty")
        self.assertEqual(meta.audits.get("QA_AUDIT"), "2026-10-02T14:55:00Z")
        self.assertEqual(len(meta.feedback), 1)
        self.assertIn("Contract violation", meta.feedback[0])

    def test_extract_markdown_metadata(self) -> None:
        text = """<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-02T14:40:00Z
LAST_CHANGED: 2026-10-02T14:35:10Z
CHANGE: Define fallback hierarchy.
CODE_HASH: ffe112233445
-->

# agent_config specification
"""
        meta = self.coordinator.extract_metadata_from_text(text, "agent_config.md")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.last_cleaned, "2026-10-02T14:40:00Z")
        self.assertEqual(meta.last_changed, "2026-10-02T14:35:10Z")
        self.assertEqual(meta.change_summary, "Define fallback hierarchy.")
        self.assertEqual(meta.code_hash, "ffe112233445")
        self.assertEqual(meta.feedback, [])

    def test_extract_code_body_and_compute_hash(self) -> None:
        text = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# CHANGE: test
# --- END CLEANROOM METADATA ---

def hello():
    return "world"
"""
        body = self.coordinator.extract_code_body(text, "hello.py")
        self.assertEqual(body, 'def hello():\n    return "world"')
        h1 = self.coordinator.compute_code_hash(text, "hello.py")
        self.assertEqual(len(h1), 12)

        # Modifying metadata header should NOT change code hash
        text2 = text.replace("2026-10-02T14:55:48Z", "2026-10-06T12:00:00Z")
        h2 = self.coordinator.compute_code_hash(text2, "hello.py")
        self.assertEqual(h1, h2)

    def test_rewrite_python_metadata_insert_shebang(self) -> None:
        original = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def main(): pass
"""
        updated = self.coordinator.rewrite_metadata_in_text(
            original,
            "main.py",
            last_cleaned="2026-10-06T10:00:00Z",
            last_changed="2026-10-06T10:00:00Z",
            change_summary="Initial commit",
        )
        lines = updated.splitlines()
        self.assertEqual(lines[0], "#!/usr/bin/env python3")
        self.assertEqual(lines[1], "# -*- coding: utf-8 -*-")
        self.assertEqual(lines[2], "# --- CLEANROOM METADATA ---")
        self.assertIn("def main(): pass", updated)

    def test_rewrite_markdown_frontmatter(self) -> None:
        original = """---
title: Spec
author: Cleanroom
---

# Title
"""
        updated = self.coordinator.rewrite_metadata_in_text(
            original,
            "spec.md",
            last_cleaned="2026-10-06T10:00:00Z",
            change_summary="Frontmatter test",
        )
        lines = updated.splitlines()
        self.assertEqual(lines[0], "---")
        self.assertEqual(lines[3], "---")
        self.assertEqual(lines[4], "<!-- CLEANROOM METADATA")
        self.assertIn("# Title", updated)

    def test_file_operations_in_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fpath = Path(td) / "sub" / "test_file.py"
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text("print('test')\n", encoding="utf-8")

            # mark clean
            self.coordinator.mark_clean(fpath, "init")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIsNotNone(meta.last_cleaned)
            self.assertEqual(meta.change_summary, "init")
            self.assertFalse(self.coordinator.is_code_modified(fpath))

            # append feedback
            self.coordinator.append_feedback(fpath, "Critique text", sender="reviewer")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(len(meta.feedback), 1)
            self.assertIn("from reviewer]: Critique text", meta.feedback[0])

            # stamp audit
            self.coordinator.stamp_audit(fpath, "qa")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIn("QA_AUDIT", meta.audits)

            # mark dirty
            self.coordinator.mark_dirty(fpath, "need rework")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.dirty, "need rework")

            # clear audits
            self.coordinator.clear_audits(fpath)
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.audits, {})

            # delete last cleaned
            self.coordinator.delete_last_cleaned(fpath)
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIsNone(meta.last_cleaned)

            # record change
            self.coordinator.record_change(fpath, "revised code")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.change_summary, "revised code")
            self.assertIsNone(meta.dirty)
            self.assertEqual(meta.feedback, [])

    def test_module_level_helpers(self) -> None:
        text = """<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-06T12:00:00Z
CHANGE: helper test
-->

# Header
"""
        meta = src_metadata.extract_metadata_from_text(text, "file.md")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.change_summary, "helper test")
        self.assertEqual(src_metadata.extract_code_body(text, "file.md"), "# Header")
        self.assertEqual(len(src_metadata.compute_code_hash(text, "file.md")), 12)


if __name__ == "__main__":
    unittest.main()
