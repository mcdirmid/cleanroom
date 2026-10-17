# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:40:00Z
# CHANGE: Realize SourceMetadataCoordinator implementation in src_metadata_impl
# CODE_HASH: 904e61032f5c
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)
from . import src_metadata


_is_html_comment_format = src_metadata._is_html_comment_format
_find_header_insertion_index = src_metadata._find_header_insertion_index
_extract_block_boundaries = src_metadata._extract_block_boundaries
parse_metadata_content = src_metadata.parse_metadata_content
format_metadata_block = src_metadata.format_metadata_block


class SourceMetadataCoordinator(
    src_metadata.SourceMetadataCoordinator, Singleton
):
    """Realizes source metadata parsing, hashing, and in-place header rewriting."""

    tier = system

    def extract_metadata_from_text(
        self, content: str, filename_or_ext: str
    ) -> Optional[src_metadata.FileMetadata]:
        # Contract: When content contains valid metadata block, MUST return populated FileMetadata; else None.
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)
        if bounds is None:
            return None
        start, end = bounds
        return parse_metadata_content(lines[start : end + 1])

    def extract_metadata(
        self, file_path: Path | str
    ) -> Optional[src_metadata.FileMetadata]:
        # Contract: When file exists and contains metadata block, MUST return populated FileMetadata; else None.
        p = Path(file_path)
        if not p.is_file():
            return None
        try:
            content = p.read_text(encoding="utf-8")
            return self.extract_metadata_from_text(content, p.name)
        except OSError:
            return None

    def extract_code_body(self, content: str, filename_or_ext: str) -> str:
        # Contract: MUST return content lines outside metadata comment header boundaries.
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)
        if bounds is None:
            body_lines = lines
        else:
            start, end = bounds
            body_lines = lines[:start] + lines[end + 1 :]
        return "\n".join(body_lines).strip()

    def compute_code_hash(self, content: str, filename_or_ext: str) -> str:
        # Contract: MUST return first twelve characters of SHA-256 digest of code body.
        body = self.extract_code_body(content, filename_or_ext)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]

    def compute_file_code_hash(self, file_path: Path | str) -> Optional[str]:
        # Contract: When file exists on disk, MUST return twelve-character code hash; else None.
        p = Path(file_path)
        if not p.is_file():
            return None
        try:
            content = p.read_text(encoding="utf-8")
            return self.compute_code_hash(content, p.name)
        except OSError:
            return None

    def is_code_modified(self, file_path: Path | str) -> bool:
        # Contract: When file does not exist or has no recorded code hash, MUST return True; when on-disk hash differs, MUST return True; when matches, MUST return False.
        p = Path(file_path)
        if not p.is_file():
            return True
        meta = self.extract_metadata(p)
        if meta is None or not meta.code_hash:
            return True
        current_hash = self.compute_file_code_hash(p)
        return current_hash != meta.code_hash

    def rewrite_metadata_in_text(
        self,
        content: str,
        filename_or_ext: str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        code_hash: Optional[str] = None,
        clear_code_hash: bool = False,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
    ) -> str:
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)

        existing_meta = (
            parse_metadata_content(lines[bounds[0] : bounds[1] + 1])
            if bounds is not None
            else src_metadata.FileMetadata(
                last_cleaned=None,
                last_changed=None,
                change_summary="",
                feedback=[],
                audits={},
            )
        )

        if clear_last_cleaned:
            new_last_cleaned: Optional[str] = None
        elif last_cleaned is not None:
            new_last_cleaned = last_cleaned
        else:
            new_last_cleaned = existing_meta.last_cleaned

        new_last_changed = (
            last_changed if last_changed is not None else existing_meta.last_changed
        )
        new_change = (
            change_summary
            if change_summary is not None
            else existing_meta.change_summary
        )

        if clear_code_hash:
            new_code_hash: Optional[str] = None
        elif code_hash is not None:
            new_code_hash = code_hash
        else:
            new_code_hash = existing_meta.code_hash

        if clear_feedback:
            new_feedback: List[str] = []
        else:
            new_feedback = list(existing_meta.feedback)

        if append_feedback:
            new_feedback.append(append_feedback)

        if clear_audits:
            new_audits: Dict[str, str] = {}
        elif audits is not None:
            new_audits = dict(audits)
        else:
            new_audits = dict(existing_meta.audits)

        if stamp_audit:
            role_upper = stamp_audit.upper().strip()
            tag = role_upper if role_upper.endswith("_AUDIT") else f"{role_upper}_AUDIT"
            new_audits[tag] = src_metadata.current_utc_timestamp()

        if clear_dirty:
            new_dirty: Optional[str] = None
        elif dirty is not None:
            new_dirty = dirty
        else:
            new_dirty = existing_meta.dirty

        new_meta = src_metadata.FileMetadata(
            last_cleaned=new_last_cleaned,
            last_changed=new_last_changed,
            change_summary=new_change,
            feedback=new_feedback,
            audits=new_audits,
            dirty=new_dirty,
            code_hash=new_code_hash,
        )

        new_block_lines = format_metadata_block(new_meta, is_html)

        if bounds is not None:
            start, end = bounds
            result_lines = lines[:start] + new_block_lines + lines[end + 1 :]
        else:
            insert_idx = _find_header_insertion_index(lines, is_html)
            if insert_idx == 0 and lines:
                new_block_lines.append("")
            result_lines = lines[:insert_idx] + new_block_lines + lines[insert_idx:]

        trailing_newline = content.endswith("\n") or not content
        res = "\n".join(result_lines)
        if trailing_newline and not res.endswith("\n"):
            res += "\n"
        return res

    def update_metadata(
        self,
        file_path: Path | str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        code_hash: Optional[str] = None,
        clear_code_hash: bool = False,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
    ) -> None:
        p = Path(file_path)
        if p.is_file():
            content = p.read_text(encoding="utf-8")
        else:
            content = ""
        updated = self.rewrite_metadata_in_text(
            content=content,
            filename_or_ext=p.name,
            last_cleaned=last_cleaned,
            clear_last_cleaned=clear_last_cleaned,
            last_changed=last_changed,
            change_summary=change_summary,
            code_hash=code_hash,
            clear_code_hash=clear_code_hash,
            clear_feedback=clear_feedback,
            append_feedback=append_feedback,
            audits=audits,
            clear_audits=clear_audits,
            stamp_audit=stamp_audit,
            dirty=dirty,
            clear_dirty=clear_dirty,
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(updated, encoding="utf-8")

    def delete_last_cleaned(self, file_path: Path | str) -> None:
        self.update_metadata(file_path, clear_last_cleaned=True)

    def mark_dirty(self, file_path: Path | str, reason: str = "manual dirty") -> None:
        now = src_metadata.current_utc_timestamp()
        self.update_metadata(file_path, dirty=reason, last_cleaned=now)

    def mark_clean(
        self, file_path: Path | str, default_change: str = "new file"
    ) -> None:
        p = Path(file_path)
        existing = self.extract_metadata(p)
        now = src_metadata.current_utc_timestamp()
        last_changed = (
            existing.last_changed if (existing and existing.last_changed) else now
        )
        change_summary = (
            existing.change_summary
            if (existing and existing.change_summary)
            else default_change
        )
        code_hash = self.compute_file_code_hash(p)
        self.update_metadata(
            p,
            last_cleaned=now,
            last_changed=last_changed,
            change_summary=change_summary,
            code_hash=code_hash,
            clear_feedback=True,
            clear_dirty=True,
        )

    def record_change(
        self,
        file_path: Path | str,
        change_description: str,
        code_hash: Optional[str] = None,
    ) -> None:
        now = src_metadata.current_utc_timestamp()
        p = Path(file_path)
        computed_hash = code_hash
        if computed_hash is None and p.is_file():
            computed_hash = self.compute_file_code_hash(p)
        self.update_metadata(
            file_path,
            last_cleaned=now,
            last_changed=now,
            change_summary=change_description,
            code_hash=computed_hash,
            clear_feedback=True,
            clear_audits=True,
            clear_dirty=True,
        )

    def append_feedback(
        self, file_path: Path | str, explanation: str, sender: str = "user"
    ) -> None:
        # Contract: MUST append formatted feedback entry and advance last cleaned timestamp to now.
        now = src_metadata.current_utc_timestamp()
        clean_entry = re.sub(r"^\[.*?\]:\s*", "", explanation.strip())
        self.update_metadata(file_path, append_feedback=clean_entry, last_cleaned=now)

    def stamp_audit(self, file_path: Path | str, role_name: str) -> None:
        # Contract: MUST record role audit timestamp as now and advance last cleaned timestamp to now.
        now = src_metadata.current_utc_timestamp()
        self.update_metadata(
            file_path,
            last_cleaned=now,
            stamp_audit=role_name,
        )

    def clear_audits(self, file_path: Path | str) -> None:
        # Contract: MUST rewrite file clearing all audit tags.
        self.update_metadata(file_path, clear_audits=True)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SourceMetadataCoordinator,
        keys=[
            src_metadata.SourceMetadataCoordinator,
            SourceMetadataCoordinator,
        ],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
