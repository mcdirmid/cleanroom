"""Consolidated Pretense specification, fake synthesis, unit tests, and fuzzing for SourceMetadataCoordinator.

Combines state machine model, deterministic unit tests, implementation parity tests, and Hypothesis fuzzing.
"""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict
from update_with_ai.parts.metadata.lib import src_metadata, src_metadata_impl
from update_with_ai.parts.metadata.lib.src_metadata import FileMetadata, SourceMetadataCoordinator


# ==============================================================================
# 1. State Machine Protocol & Model State
# ==============================================================================

@dataclass
class SourceMetadataState:
    """Canonical model state for SourceMetadataCoordinator."""
    files: PretenseDict[str, FileMetadata] = field(default_factory=PretenseDict)
    code_hashes: PretenseDict[str, str] = field(default_factory=PretenseDict)
    clock: str = "2026-10-24T12:00:00Z"


class SourceMetadataStateMachine(StateMachine[SourceMetadataState]):
    """Unified Pretense State Machine for SourceMetadataCoordinator."""

    def __init__(
        self,
        state: Optional[SourceMetadataState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SourceMetadataState(), singletons=singletons)

    @transition.seeding(name="seed_metadata")
    def seed_metadata(
        self,
        ctx: TransitionContext[Any, [Path | str, Optional[FileMetadata]], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    metadata=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda file_path="demo.py", metadata=None: None)
        def provide(res: None, file_path: Path | str = "demo.py", metadata: Optional[FileMetadata] = None) -> None:
            p = str(file_path)
            meta = metadata or FileMetadata(
                last_cleaned=self.state.clock,
                last_changed=self.state.clock,
                change_summary="seed",
                feedback=[],
                audits={},
                dirty=None,
                code_hash="seedhash1234",
            )
            self.state.files[p] = meta
        ctx.update(provide)

    @transition.seeding(name="seed_code_hash")
    def seed_code_hash(
        self,
        ctx: TransitionContext[Any, [Path | str, str], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    code_hash=Domain(strategy=lambda: 'hash12345678'),
                )
        ctx.returns(lambda file_path="demo.py", code_hash="hash12345678": None)
        ctx.update(lambda res, file_path="demo.py", code_hash="hash12345678": (
            self.state.code_hashes.__setitem__(str(file_path), str(code_hash))
        ))

    @transition.seeding(name="seed_clock")
    def seed_clock(
        self,
        ctx: TransitionContext[Any, [str], None],
    ) -> None:
        ctx.arguments(timestamp=Domain(strategy=lambda: '2026-10-24T12:00:00Z'))
        ctx.returns(lambda timestamp="2026-10-24T12:00:00Z": None)
        ctx.update(lambda res, timestamp="2026-10-24T12:00:00Z": setattr(self.state, "clock", str(timestamp)))

    @transition(SourceMetadataCoordinator.extract_metadata)
    def extract_metadata(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str], Optional[FileMetadata]],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: ('demo.py',) if not self.state.files else (next(iter(self.state.files.keys())),)))
        ctx.returns(lambda file_path="demo.py": self.state.files.get(str(file_path)))
        ctx.update(lambda res, file_path="demo.py": None)

    @transition(SourceMetadataCoordinator.extract_metadata_from_text)
    def extract_metadata_from_text(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [str, str], Optional[FileMetadata]],
    ) -> None:
        ctx.arguments(
                    content=Domain(strategy=lambda: ''),
                    filename_or_ext=Domain(strategy=lambda: 'test.py'),
                )
        def returns(content: str = "", filename_or_ext: str = "test.py") -> Optional[FileMetadata]:
            is_html = src_metadata._is_html_comment_format(filename_or_ext)
            lines = content.splitlines()
            bounds = src_metadata._extract_block_boundaries(lines, is_html)
            return None if bounds is None else src_metadata.parse_metadata_content(lines[bounds[0] : bounds[1] + 1])
        ctx.returns(returns)
        ctx.update(lambda res, content="", filename_or_ext="test.py": None)

    @transition(SourceMetadataCoordinator.extract_code_body)
    def extract_code_body(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [str, str], str],
    ) -> None:
        ctx.arguments(
                    content=Domain(strategy=lambda: ''),
                    filename_or_ext=Domain(strategy=lambda: 'test.py'),
                )
        def returns(content: str = "", filename_or_ext: str = "test.py") -> str:
            is_html = src_metadata._is_html_comment_format(filename_or_ext)
            lines = content.splitlines()
            bounds = src_metadata._extract_block_boundaries(lines, is_html)
            if bounds is None:
                return "\n".join(lines).strip()
            return "\n".join(lines[: bounds[0]] + lines[bounds[1] + 1 :]).strip()
        ctx.returns(returns)
        ctx.update(lambda res, content="", filename_or_ext="test.py": None)

    @transition(SourceMetadataCoordinator.compute_code_hash)
    def compute_code_hash(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [str, str], str],
    ) -> None:
        ctx.arguments(
                    content=Domain(strategy=lambda: ''),
                    filename_or_ext=Domain(strategy=lambda: 'test.py'),
                )
        def returns(content: str = "", filename_or_ext: str = "test.py") -> str:
            is_html = src_metadata._is_html_comment_format(filename_or_ext)
            lines = content.splitlines()
            bounds = src_metadata._extract_block_boundaries(lines, is_html)
            body = "\n".join(lines if bounds is None else lines[: bounds[0]] + lines[bounds[1] + 1 :]).strip()
            return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
        ctx.returns(returns)
        ctx.update(lambda res, content="", filename_or_ext="test.py": None)

    @transition(SourceMetadataCoordinator.compute_file_code_hash)
    def compute_file_code_hash(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str], Optional[str]],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: ('demo.py',) if not self.state.files else (next(iter(self.state.files.keys())),)))
        def returns(file_path: Path | str = "demo.py") -> Optional[str]:
            p = str(file_path)
            if p in self.state.code_hashes:
                return self.state.code_hashes[p]
            elif p in self.state.files:
                return self.state.files[p].code_hash or "fakehash1234"
            return None
        ctx.returns(returns)
        ctx.update(lambda res, file_path="demo.py": None)

    @transition(SourceMetadataCoordinator.is_code_modified)
    def is_code_modified(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str], bool],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: ('demo.py',) if not self.state.files else (next(iter(self.state.files.keys())),)))
        def returns(file_path: Path | str = "demo.py") -> bool:
            p = str(file_path)
            meta = self.state.files.get(p)
            if meta is None or not meta.code_hash:
                return True
            curr_hash = self.state.code_hashes.get(p, meta.code_hash)
            return curr_hash != meta.code_hash
        ctx.returns(returns)
        ctx.update(lambda res, file_path="demo.py": None)

    @transition(SourceMetadataCoordinator.is_metadata_altered)
    def is_metadata_altered(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [str, str, str], bool],
    ) -> None:
        ctx.arguments(
                    original_content=Domain(strategy=lambda: ''),
                    new_content=Domain(strategy=lambda: ''),
                    filename_or_ext=Domain(strategy=lambda: 'test.py'),
                )
        def returns(original_content: str = "", new_content: str = "", filename_or_ext: str = "test.py") -> bool:
            is_html = src_metadata._is_html_comment_format(filename_or_ext)
            orig_lines = original_content.splitlines()
            orig_bounds = src_metadata._extract_block_boundaries(orig_lines, is_html)
            new_lines = new_content.splitlines()
            new_bounds = src_metadata._extract_block_boundaries(new_lines, is_html)

            if orig_bounds is not None:
                if new_bounds is None:
                    return True
                orig_meta = orig_lines[orig_bounds[0] : orig_bounds[1] + 1]
                new_meta = new_lines[new_bounds[0] : new_bounds[1] + 1]
                return orig_meta != new_meta
            else:
                if new_bounds is not None:
                    return True
                return any(
                    line.strip() in ("# --- CLEANROOM METADATA ---", "# --- END CLEANROOM METADATA ---")
                    or (line.strip().startswith("<!--") and "CLEANROOM METADATA" in line.strip())
                    for line in new_lines
                )
        ctx.returns(returns)
        ctx.update(lambda res, original_content="", new_content="", filename_or_ext="test.py": None)

    @transition(SourceMetadataCoordinator.mark_dirty)
    def mark_dirty(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str, str], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    reason=Domain(strategy=lambda: 'manual dirty'),
                )
        ctx.returns(lambda file_path="demo.py", reason="manual dirty": None)
        def provide(res: None, file_path: Path | str = "demo.py", reason: str = "manual dirty") -> None:
            p = str(file_path)
            curr = self.state.files.get(p)
            if curr is None:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=None,
                    change_summary="",
                    feedback=[],
                    audits={},
                    dirty=reason,
                    code_hash=None,
                )
            else:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=curr.last_changed,
                    change_summary=curr.change_summary,
                    feedback=list(curr.feedback),
                    audits=dict(curr.audits),
                    dirty=reason,
                    code_hash=curr.code_hash,
                )
        ctx.update(provide)

    @transition(SourceMetadataCoordinator.mark_clean)
    def mark_clean(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str, str], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    default_change=Domain(strategy=lambda: 'new file'),
                )
        ctx.returns(lambda file_path="demo.py", default_change="new file": None)
        def provide(res: None, file_path: Path | str = "demo.py", default_change: str = "new file") -> None:
            p = str(file_path)
            curr = self.state.files.get(p)
            hash_val = self.state.code_hashes.get(p, curr.code_hash if curr else "clean1234567")
            if curr is None:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=self.state.clock,
                    change_summary=default_change,
                    feedback=[],
                    audits={},
                    dirty=None,
                    code_hash=hash_val,
                )
            else:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=curr.last_changed or self.state.clock,
                    change_summary=curr.change_summary or default_change,
                    feedback=[],
                    audits=dict(curr.audits),
                    dirty=None,
                    code_hash=hash_val,
                )
        ctx.update(provide)

    @transition(SourceMetadataCoordinator.record_change)
    def record_change(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str, str, Optional[str]], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    change_description=Domain(strategy=lambda: 'update'),
                    code_hash=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda file_path="demo.py", change_description="update", code_hash=None: None)
        def provide(res: None, file_path: Path | str = "demo.py", change_description: str = "update", code_hash: Optional[str] = None) -> None:
            p = str(file_path)
            h = code_hash or self.state.code_hashes.get(p, "changehash12")
            self.state.files[p] = FileMetadata(
                last_cleaned=self.state.clock,
                last_changed=self.state.clock,
                change_summary=change_description,
                feedback=[],
                audits={},
                dirty=None,
                code_hash=h,
            )
        ctx.update(provide)

    @transition(SourceMetadataCoordinator.append_feedback)
    def append_feedback(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str, str, str], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    explanation=Domain(strategy=lambda: 'feedback item'),
                    sender=Domain(strategy=lambda: 'user'),
                )
        ctx.returns(lambda file_path="demo.py", explanation="feedback item", sender="user": None)
        def provide(res: None, file_path: Path | str = "demo.py", explanation: str = "feedback item", sender: str = "user") -> None:
            p = str(file_path)
            curr = self.state.files.get(p)
            fb_item = f"[{self.state.clock} from {sender}]: {explanation}"
            if curr is None:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=None,
                    change_summary="",
                    feedback=[fb_item],
                    audits={},
                    dirty=None,
                    code_hash=None,
                )
            else:
                new_fb = list(curr.feedback)
                new_fb.append(fb_item)
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=curr.last_changed,
                    change_summary=curr.change_summary,
                    feedback=new_fb,
                    audits=dict(curr.audits),
                    dirty=curr.dirty,
                    code_hash=curr.code_hash,
                )
        ctx.update(provide)

    @transition(SourceMetadataCoordinator.stamp_audit)
    def stamp_audit(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str, str], None],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'demo.py'),
                    role_name=Domain(strategy=lambda: 'qa'),
                )
        ctx.returns(lambda file_path="demo.py", role_name="qa": None)
        def provide(res: None, file_path: Path | str = "demo.py", role_name: str = "qa") -> None:
            p = str(file_path)
            tag = src_metadata.get_audit_tag(role_name)
            curr = self.state.files.get(p)
            if curr is None:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=None,
                    change_summary="",
                    feedback=[],
                    audits={tag: self.state.clock},
                    dirty=None,
                    code_hash=None,
                )
            else:
                new_audits = dict(curr.audits)
                new_audits[tag] = self.state.clock
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=curr.last_changed,
                    change_summary=curr.change_summary,
                    feedback=list(curr.feedback),
                    audits=new_audits,
                    dirty=curr.dirty,
                    code_hash=curr.code_hash,
                )
        ctx.update(provide)

    @transition(SourceMetadataCoordinator.clear_audits)
    def clear_audits(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str], None],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: 'demo.py'))
        ctx.returns(lambda file_path="demo.py": None)
        def provide(res: None, file_path: Path | str = "demo.py") -> None:
            p = str(file_path)
            curr = self.state.files.get(p)
            if curr is not None:
                self.state.files[p] = FileMetadata(
                    last_cleaned=self.state.clock,
                    last_changed=curr.last_changed,
                    change_summary=curr.change_summary,
                    feedback=list(curr.feedback),
                    audits={},
                    dirty=curr.dirty,
                    code_hash=curr.code_hash,
                )
        ctx.update(provide)

    @transition(SourceMetadataCoordinator.delete_last_cleaned)
    def delete_last_cleaned(
        self,
        ctx: TransitionContext[SourceMetadataCoordinator, [Path | str], None],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: 'demo.py'))
        ctx.returns(lambda file_path="demo.py": None)
        def provide(res: None, file_path: Path | str = "demo.py") -> None:
            p = str(file_path)
            curr = self.state.files.get(p)
            if curr is not None:
                self.state.files[p] = FileMetadata(
                    last_cleaned=None,
                    last_changed=curr.last_changed,
                    change_summary=curr.change_summary,
                    feedback=list(curr.feedback),
                    audits=dict(curr.audits),
                    dirty=curr.dirty,
                    code_hash=curr.code_hash,
                )
        ctx.update(provide)


proto = SourceMetadataStateMachine()


# ==============================================================================
# 5. Fake Factory Helper
# ==============================================================================

def make_metadata_fake(state: Optional[SourceMetadataState] = None) -> SourceMetadataCoordinator:
    """Instantiate a synthesized SourceMetadataCoordinator fake with Pretense."""
    st = state or SourceMetadataState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(SourceMetadataCoordinator)


# ==============================================================================
# 6. Unit Tests for Fake Synthesis
# ==============================================================================

class TestSrcMetadataCoordinatorFakeSynthesis(unittest.TestCase):
    """Verifies that SourceMetadataCoordinator fake synthesized by Pretense behaves accurately."""

    def setUp(self) -> None:
        self.state = SourceMetadataState(clock="2026-10-24T15:00:00Z")
        self.sm = proto.make_state_machine(self.state)
        self.fake: SourceMetadataCoordinator = self.sm.as_fake(SourceMetadataCoordinator)

    def test_seed_and_extract_metadata(self) -> None:
        file_path = "parts/core/lib/demo.py"
        meta = FileMetadata(
            last_cleaned="2026-10-24T14:00:00Z",
            last_changed="2026-10-24T14:00:00Z",
            change_summary="Initial commit",
            feedback=[],
            audits={"QA_AUDIT": "2026-10-24T14:10:00Z"},
            dirty=None,
            code_hash="abcd1234ef56",
        )
        self.sm.seed_metadata(file_path, meta)

        extracted = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(extracted)
        assert extracted is not None
        self.assertEqual(extracted.last_cleaned, "2026-10-24T14:00:00Z")
        self.assertEqual(extracted.change_summary, "Initial commit")
        self.assertEqual(extracted.code_hash, "abcd1234ef56")
        self.assertEqual(extracted.audits.get("QA_AUDIT"), "2026-10-24T14:10:00Z")

        # Unknown file returns None
        self.assertIsNone(self.fake.extract_metadata("nonexistent.py"))

    def test_code_hash_and_modification_detection(self) -> None:
        file_path = "parts/core/lib/worker.py"
        meta = FileMetadata(
            last_cleaned="2026-10-24T14:00:00Z",
            last_changed="2026-10-24T14:00:00Z",
            change_summary="Seed worker",
            feedback=[],
            audits={},
            dirty=None,
            code_hash="orig12345678",
        )
        self.sm.seed_metadata(file_path, meta)
        self.sm.seed_code_hash(file_path, "orig12345678")

        # Matching hash -> not modified
        self.assertFalse(self.fake.is_code_modified(file_path))

        # Modifying on-disk hash -> modified
        self.sm.seed_code_hash(file_path, "different123")
        self.assertTrue(self.fake.is_code_modified(file_path))

        # Unrecorded file -> modified
        self.assertTrue(self.fake.is_code_modified("unrecorded.py"))

    def test_mark_dirty_and_clean_lifecycle(self) -> None:
        file_path = "parts/agent/lib/config.py"
        self.fake.mark_dirty(file_path, reason="specification updated")

        meta = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.dirty, "specification updated")
        self.assertEqual(meta.last_cleaned, "2026-10-24T15:00:00Z")

        # Now mark clean
        self.fake.mark_clean(file_path, default_change="resolved dirty")
        meta_clean = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta_clean)
        assert meta_clean is not None
        self.assertIsNone(meta_clean.dirty)
        self.assertEqual(meta_clean.feedback, [])

    def test_record_change_and_audits(self) -> None:
        file_path = "parts/agent/lib/runner.py"
        self.fake.record_change(file_path, change_description="Add retry loop", code_hash="newhash12345")

        meta = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.change_summary, "Add retry loop")
        self.assertEqual(meta.code_hash, "newhash12345")
        self.assertEqual(meta.last_changed, "2026-10-24T15:00:00Z")

        # Stamp audit
        self.fake.stamp_audit(file_path, role_name="qa")
        meta_audited = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta_audited)
        assert meta_audited is not None
        self.assertEqual(meta_audited.audits.get("QA_AUDIT"), "2026-10-24T15:00:00Z")

        # Clear audits
        self.fake.clear_audits(file_path)
        meta_cleared = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta_cleared)
        assert meta_cleared is not None
        self.assertEqual(meta_cleared.audits, {})

    def test_append_feedback_and_delete_last_cleaned(self) -> None:
        file_path = "parts/agent/lib/runner.py"
        self.fake.append_feedback(file_path, explanation="Missing unit test for error branch", sender="verifier")

        meta = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(len(meta.feedback), 1)
        self.assertIn("Missing unit test for error branch", meta.feedback[0])
        self.assertIn("from verifier", meta.feedback[0])

        self.fake.delete_last_cleaned(file_path)
        meta_deleted = self.fake.extract_metadata(file_path)
        self.assertIsNotNone(meta_deleted)
        assert meta_deleted is not None
        self.assertIsNone(meta_deleted.last_cleaned)


# ==============================================================================
# 7. Parity Tests (Fake vs Real Implementation)
# ==============================================================================

class TestSrcMetadataCoordinatorParity(unittest.TestCase):
    """Verifies parity between Pretense fake and real SourceMetadataCoordinator implementation."""

    def setUp(self) -> None:
        self.state = SourceMetadataState()
        self.sm = proto.make_state_machine(self.state)
        self.fake: SourceMetadataCoordinator = self.sm.as_fake(SourceMetadataCoordinator)
        self.real: SourceMetadataCoordinator = src_metadata_impl.SourceMetadataCoordinator()

    def test_extract_code_body_parity(self) -> None:
        content = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# CHANGE: Add feature
# --- END CLEANROOM METADATA ---

def compute(x: int) -> int:
    return x * 2
"""
        fake_body = self.fake.extract_code_body(content, "compute.py")
        real_body = self.real.extract_code_body(content, "compute.py")
        self.assertEqual(fake_body, real_body)
        self.assertEqual(fake_body, "def compute(x: int) -> int:\n    return x * 2")

    def test_compute_code_hash_parity(self) -> None:
        content = """<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-02T14:40:00Z
CHANGE: Doc update
-->

# Overview
This is a test documentation file.
"""
        fake_hash = self.fake.compute_code_hash(content, "doc.md")
        real_hash = self.real.compute_code_hash(content, "doc.md")
        self.assertEqual(fake_hash, real_hash)
        self.assertEqual(len(fake_hash), 12)

    def test_is_metadata_altered_parity(self) -> None:
        orig = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# --- END CLEANROOM METADATA ---

code = True
"""
        modified_meta = orig.replace("14:55:48Z", "15:00:00Z")
        deleted_meta = "code = True\n"

        self.assertEqual(
            self.fake.is_metadata_altered(orig, modified_meta, "main.py"),
            self.real.is_metadata_altered(orig, modified_meta, "main.py"),
        )
        self.assertTrue(self.fake.is_metadata_altered(orig, modified_meta, "main.py"))

        self.assertEqual(
            self.fake.is_metadata_altered(orig, deleted_meta, "main.py"),
            self.real.is_metadata_altered(orig, deleted_meta, "main.py"),
        )
        self.assertTrue(self.fake.is_metadata_altered(orig, deleted_meta, "main.py"))


class TestSrcMetadataCoordinatorReal(unittest.TestCase):
    """Direct verification of the real SourceMetadataCoordinator implementation covering all branches."""

    def setUp(self) -> None:
        self.coordinator: SourceMetadataCoordinator = src_metadata_impl.SourceMetadataCoordinator()

    def test_extract_python_and_markdown_metadata(self) -> None:
        py_text = """# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-02T14:55:48Z
# LAST_CHANGED: 2026-10-06T12:00:00Z
# CHANGE: Add feature
# QA_AUDIT: 2026-10-06T13:00:00Z
# --- END CLEANROOM METADATA ---

code = 1
"""
        meta = self.coordinator.extract_metadata_from_text(py_text, "main.py")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.change_summary, "Add feature")
        self.assertIn("QA_AUDIT", meta.audits)

        md_text = """<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-02T14:40:00Z
CHANGE: Doc
-->

# Hello
"""
        meta_md = self.coordinator.extract_metadata_from_text(md_text, "doc.md")
        self.assertIsNotNone(meta_md)
        assert meta_md is not None
        self.assertEqual(meta_md.change_summary, "Doc")

        # Invalid bounds returns None
        self.assertIsNone(self.coordinator.extract_metadata_from_text("plain text", "doc.md"))

    def test_rewrite_python_and_markdown(self) -> None:
        original = "#!/usr/bin/env python3\n\ndef main(): pass\n"
        updated = self.coordinator.rewrite_metadata_in_text(
            original, "main.py", change_summary="New code", last_cleaned="2026-10-06T10:00:00Z"
        )
        self.assertIn("# --- CLEANROOM METADATA ---", updated)
        self.assertIn("# CHANGE: New code", updated)

        md_orig = "---\ntitle: T\n---\n# Doc\n"
        md_updated = self.coordinator.rewrite_metadata_in_text(
            md_orig, "doc.md", change_summary="Frontmatter update"
        )
        self.assertIn("<!-- CLEANROOM METADATA", md_updated)

        # Clear code hash and explicit audits
        cleared = self.coordinator.rewrite_metadata_in_text(
            updated, "main.py", clear_code_hash=True, audits={"LIB_AUDIT": "2026-10-06T12:00:00Z"}
        )
        self.assertIn("LIB_AUDIT", cleared)

        # Top-of-file metadata with leading blank lines in body
        top_meta = "# --- CLEANROOM METADATA ---\n# CHANGE: init\n# --- END CLEANROOM METADATA ---\n\n\ndef foo(): pass\n"
        migrated = self.coordinator.rewrite_metadata_in_text(top_meta, "top.py")
        self.assertIn("def foo(): pass", migrated)

        # Only metadata, empty body
        only_meta = "# --- CLEANROOM METADATA ---\n# CHANGE: only\n# --- END CLEANROOM METADATA ---\n"
        rewritten_empty = self.coordinator.rewrite_metadata_in_text(only_meta, "empty.py", change_summary="new_only")
        self.assertIn("CHANGE: new_only", rewritten_empty)

    def test_altered_metadata_branches(self) -> None:
        # Orig has no metadata, new has no metadata
        self.assertFalse(self.coordinator.is_metadata_altered("a = 1\n", "a = 2\n", "a.py"))
        # Orig has no metadata, new has metadata injected
        self.assertTrue(self.coordinator.is_metadata_altered("a = 1\n", "# --- CLEANROOM METADATA ---\n# CHANGE: inj\n# --- END CLEANROOM METADATA ---\na = 1\n", "a.py"))
        # Orig has no metadata, new has partial metadata line
        self.assertTrue(self.coordinator.is_metadata_altered("a = 1\n", "# --- CLEANROOM METADATA ---\n", "a.py"))

    def test_file_operations_in_temp_dir(self) -> None:
        src_metadata_impl.__initialize__()
        with tempfile.TemporaryDirectory() as td:
            fpath = Path(td) / "test.py"
            fpath.write_text("print('test')\n", encoding="utf-8")

            # Non-existent file returns None/True
            missing = Path(td) / "truly_missing.py"
            self.assertIsNone(self.coordinator.extract_metadata(missing))
            self.assertIsNone(self.coordinator.compute_file_code_hash(missing))
            self.assertTrue(self.coordinator.is_code_modified(missing))

            # Update metadata on non-existent file creates it
            self.coordinator.update_metadata(missing, change_summary="created")
            self.assertTrue(missing.is_file())

            # File without code hash
            no_hash = Path(td) / "no_hash.py"
            no_hash.write_text("# --- CLEANROOM METADATA ---\n# CHANGE: none\n# --- END CLEANROOM METADATA ---\ncode = 1\n", encoding="utf-8")
            self.assertTrue(self.coordinator.is_code_modified(no_hash))

            # Mark clean & code modified
            self.coordinator.mark_clean(fpath, "init")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.change_summary, "init")
            self.assertFalse(self.coordinator.is_code_modified(fpath))

            # Feedback
            self.coordinator.append_feedback(fpath, "Critique", sender="reviewer")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(len(meta.feedback), 1)

            # Audit
            self.coordinator.stamp_audit(fpath, "qa")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIn("QA_AUDIT", meta.audits)

            # Mark dirty
            self.coordinator.mark_dirty(fpath, "rework")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.dirty, "rework")

            # Clear audits
            self.coordinator.clear_audits(fpath)
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.audits, {})

            # Delete last cleaned
            self.coordinator.delete_last_cleaned(fpath)
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertIsNone(meta.last_cleaned)

            # Record change
            self.coordinator.record_change(fpath, "updated code")
            meta = self.coordinator.extract_metadata(fpath)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta.change_summary, "updated code")


# ==============================================================================
# 8. Hypothesis Fuzz Testing
# ==============================================================================

class TestSrcMetadataCoordinatorFuzz(unittest.TestCase):
    """Property fuzz testing using Hypothesis on SourceMetadataCoordinator state transitions."""

    @settings(max_examples=50)
    @given(
        actions=st.lists(
            st.tuples(
                st.sampled_from(["dirty", "clean", "change", "feedback", "audit", "clear_audit"]),
                st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
                st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _"),
            ),
            min_size=1,
            max_size=20,
        )
    )
    def test_metadata_invariants_under_fuzz(self, actions: list[tuple[str, str, str]]) -> None:
        state = SourceMetadataState(clock="2026-10-24T18:00:00Z")
        sm = proto.make_state_machine(state)
        fake: SourceMetadataCoordinator = sm.as_fake(SourceMetadataCoordinator)

        for kind, file_suffix, payload in actions:
            file_path = f"file_{file_suffix}.py"
            if kind == "dirty":
                fake.mark_dirty(file_path, reason=payload)
                meta = fake.extract_metadata(file_path)
                assert meta is not None
                self.assertEqual(meta.dirty, payload)
            elif kind == "clean":
                fake.mark_clean(file_path, default_change=payload)
                meta = fake.extract_metadata(file_path)
                assert meta is not None
                self.assertIsNone(meta.dirty)
                self.assertEqual(meta.feedback, [])
            elif kind == "change":
                fake.record_change(file_path, change_description=payload)
                meta = fake.extract_metadata(file_path)
                assert meta is not None
                self.assertEqual(meta.change_summary, payload)
                self.assertIsNone(meta.dirty)
                self.assertEqual(meta.feedback, [])
            elif kind == "feedback":
                fake.append_feedback(file_path, explanation=payload)
                meta = fake.extract_metadata(file_path)
                assert meta is not None
                self.assertTrue(any(payload in fb for fb in meta.feedback))
            elif kind == "audit":
                role = "qa" if not payload.strip() else payload.split()[0].lower()
                fake.stamp_audit(file_path, role_name=role)
                meta = fake.extract_metadata(file_path)
                assert meta is not None
                tag = src_metadata.get_audit_tag(role)
                self.assertIn(tag, meta.audits)
            elif kind == "clear_audit":
                fake.clear_audits(file_path)
                meta = fake.extract_metadata(file_path)
                if meta is not None:
                    self.assertEqual(meta.audits, {})
