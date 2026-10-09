# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T14:35:00Z
# CHANGE: new file
# CODE_HASH: 755c378950e7
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Protocol, Tuple


def _is_html_comment_format(path_or_ext: str) -> bool:
    ext = os.path.splitext(path_or_ext)[1].lower()
    return ext == ".md"


def _find_header_insertion_index(lines: List[str], is_html: bool) -> int:
    """Determines line index where metadata block should be inserted when missing."""
    if not lines:
        return 0

    if is_html:
        if lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    return i + 1
        return 0

    idx = 0
    if idx < len(lines) and lines[idx].startswith("#!"):
        idx += 1
    if idx < len(lines) and ("coding:" in lines[idx] or "coding=" in lines[idx]):
        idx += 1
    return idx


def _extract_block_boundaries(
    lines: List[str], is_html: bool
) -> Optional[Tuple[int, int]]:
    """Locates (start_line_idx, end_line_idx) inclusive for the metadata block."""
    if is_html:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("<!--") and "CLEANROOM METADATA" in stripped:
                for i in range(idx, len(lines)):
                    if "-->" in lines[i]:
                        return (idx, i)
                return None
        return None

    for idx, line in enumerate(lines):
        if line.strip() == "# --- CLEANROOM METADATA ---":
            for i in range(idx + 1, len(lines)):
                if lines[i].strip() == "# --- END CLEANROOM METADATA ---":
                    return (idx, i)
            return None
    return None


@dataclass(frozen=True)
class FileMetadata:
    """Encapsulates in-band source file metadata attributes."""

    last_cleaned: Optional[str]
    last_changed: Optional[str]
    change_summary: str
    feedback: List[str]
    audits: Dict[str, str] = field(default_factory=dict)
    dirty: Optional[str] = None
    code_hash: Optional[str] = None


class SourceMetadataCoordinator(Protocol):
    """Protocol for parsing, hashing, and mutating in-band source metadata."""

    def extract_metadata_from_text(
        self,
        content: str,
        filename_or_ext: str,
    ) -> Optional[FileMetadata]: ...

    def extract_metadata(
        self,
        file_path: Path | str,
    ) -> Optional[FileMetadata]: ...

    def extract_code_body(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str: ...

    def compute_code_hash(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str: ...

    def compute_file_code_hash(
        self,
        file_path: Path | str,
    ) -> Optional[str]: ...

    def is_code_modified(
        self,
        file_path: Path | str,
    ) -> bool: ...

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
    ) -> str: ...

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
    ) -> None: ...

    def delete_last_cleaned(
        self,
        file_path: Path | str,
    ) -> None: ...

    def mark_dirty(
        self,
        file_path: Path | str,
        reason: str = "manual dirty",
    ) -> None: ...

    def mark_clean(
        self,
        file_path: Path | str,
        default_change: str = "new file",
    ) -> None: ...

    def record_change(
        self,
        file_path: Path | str,
        change_description: str,
        code_hash: Optional[str] = None,
    ) -> None: ...

    def append_feedback(
        self,
        file_path: Path | str,
        explanation: str,
        sender: str = "user",
    ) -> None: ...

    def stamp_audit(
        self,
        file_path: Path | str,
        role_name: str,
    ) -> None: ...

    def clear_audits(
        self,
        file_path: Path | str,
    ) -> None: ...


def parse_metadata_content(block_lines: List[str]) -> FileMetadata:
    """Parses raw metadata block lines into FileMetadata."""
    last_cleaned: Optional[str] = None
    last_changed: Optional[str] = None
    change_summary = ""
    feedback: List[str] = []
    audits: Dict[str, str] = {}
    dirty: Optional[str] = None
    code_hash: Optional[str] = None

    in_feedback = False
    for line in block_lines:
        raw = line.strip()
        if raw.startswith("<!--"):
            raw = raw[4:].strip()
        if raw.endswith("-->"):
            raw = raw[:-3].strip()
        if raw.startswith("#"):
            raw = raw[1:].strip()

        if not raw or raw.startswith("---") or raw == "CLEANROOM METADATA":
            continue

        if raw.startswith("LAST_CLEANED:"):
            val = raw.split(":", 1)[1].strip()
            last_cleaned = val if val else None
            in_feedback = False
        elif raw.startswith("LAST_CHANGED:") or raw.startswith("LAST_UPDATED:"):
            val = raw.split(":", 1)[1].strip()
            last_changed = val if val else None
            in_feedback = False
        elif raw.startswith("CHANGE:"):
            change_summary = raw.split(":", 1)[1].strip()
            in_feedback = False
        elif raw.startswith("CODE_HASH:"):
            val = raw.split(":", 1)[1].strip()
            code_hash = val if val else None
            in_feedback = False
        elif raw.startswith("DIRTY:"):
            val = raw.split(":", 1)[1].strip()
            dirty = val if val else "True"
            in_feedback = False
        elif raw.startswith("FEEDBACK:"):
            in_feedback = True
        elif in_feedback and raw.startswith("-"):
            item = raw[1:].strip()
            if item:
                feedback.append(item)
        elif "_AUDIT:" in raw:
            key, val = raw.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key.endswith("_AUDIT") and val:
                audits[key] = val
            in_feedback = False
        else:
            in_feedback = False

    return FileMetadata(
        last_cleaned=last_cleaned,
        last_changed=last_changed,
        change_summary=change_summary,
        feedback=feedback,
        audits=audits,
        dirty=dirty,
        code_hash=code_hash,
    )


def format_metadata_block(meta: FileMetadata, is_html: bool) -> List[str]:
    """Formats a FileMetadata record into comment block lines."""
    ch = meta.change_summary or ""

    lines: List[str] = []
    if is_html:
        lines.append("<!-- CLEANROOM METADATA")
        if meta.last_cleaned:
            lines.append(f"LAST_CLEANED: {meta.last_cleaned}")
        if meta.last_changed:
            lines.append(f"LAST_CHANGED: {meta.last_changed}")
        if ch:
            lines.append(f"CHANGE: {ch}")
        if meta.code_hash:
            lines.append(f"CODE_HASH: {meta.code_hash}")
        if meta.dirty:
            lines.append(f"DIRTY: {meta.dirty}")
        if meta.audits:
            for k in sorted(meta.audits.keys()):
                lines.append(f"{k}: {meta.audits[k]}")
        if meta.feedback:
            lines.append("FEEDBACK:")
            for fb in meta.feedback:
                lines.append(f"- {fb}")
        lines.append("-->")
    else:
        lines.append("# --- CLEANROOM METADATA ---")
        if meta.last_cleaned:
            lines.append(f"# LAST_CLEANED: {meta.last_cleaned}")
        if meta.last_changed:
            lines.append(f"# LAST_CHANGED: {meta.last_changed}")
        if ch:
            lines.append(f"# CHANGE: {ch}")
        if meta.code_hash:
            lines.append(f"# CODE_HASH: {meta.code_hash}")
        if meta.dirty:
            lines.append(f"# DIRTY: {meta.dirty}")
        if meta.audits:
            for k in sorted(meta.audits.keys()):
                lines.append(f"# {k}: {meta.audits[k]}")
        if meta.feedback:
            lines.append("# FEEDBACK:")
            for fb in meta.feedback:
                lines.append(f"# - {fb}")
        lines.append("# --- END CLEANROOM METADATA ---")
    return lines


class _DefaultSourceMetadataCoordinator:
    """Default in-process implementation of SourceMetadataCoordinator."""

    def extract_metadata_from_text(
        self, content: str, filename_or_ext: str
    ) -> Optional[FileMetadata]:
        is_html = _is_html_comment_format(filename_or_ext)
        lines = content.splitlines()
        bounds = _extract_block_boundaries(lines, is_html)
        if bounds is None:
            return None
        start, end = bounds
        return parse_metadata_content(lines[start : end + 1])

    def extract_metadata(
        self, file_path: Path | str
    ) -> Optional[FileMetadata]:
        p = Path(file_path)
        if not p.is_file():
            return None
        try:
            content = p.read_text(encoding="utf-8")
            return self.extract_metadata_from_text(content, p.name)
        except OSError as e:
            sys.stderr.write(
                f"Warning: Failed reading metadata from '{file_path}': {e}\n"
            )
            return None

    def extract_code_body(self, content: str, filename_or_ext: str) -> str:
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
        body = self.extract_code_body(content, filename_or_ext)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]

    def compute_file_code_hash(self, file_path: Path | str) -> Optional[str]:
        p = Path(file_path)
        if not p.is_file():
            return None
        try:
            content = p.read_text(encoding="utf-8")
            return self.compute_code_hash(content, p.name)
        except OSError as e:
            sys.stderr.write(
                f"Warning: Failed reading '{file_path}' for code hash: {e}\n"
            )
            return None

    def is_code_modified(self, file_path: Path | str) -> bool:
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
            else FileMetadata(
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
            new_audits[tag] = current_utc_timestamp()

        if clear_dirty:
            new_dirty: Optional[str] = None
        elif dirty is not None:
            new_dirty = dirty
        else:
            new_dirty = existing_meta.dirty

        new_meta = FileMetadata(
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
        now = current_utc_timestamp()
        self.update_metadata(file_path, dirty=reason, last_cleaned=now)

    def mark_clean(
        self, file_path: Path | str, default_change: str = "new file"
    ) -> None:
        p = Path(file_path)
        existing = self.extract_metadata(p)
        now = current_utc_timestamp()
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
        now = current_utc_timestamp()
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
        now = current_utc_timestamp()
        if explanation.startswith("[") and "]:" in explanation:
            entry = explanation
        else:
            entry = f"[{now} from {sender}]: {explanation}"
        self.update_metadata(file_path, append_feedback=entry, last_cleaned=now)

    def stamp_audit(self, file_path: Path | str, role_name: str) -> None:
        now = current_utc_timestamp()
        self.update_metadata(
            file_path,
            last_cleaned=now,
            stamp_audit=role_name,
        )

    def clear_audits(self, file_path: Path | str) -> None:
        self.update_metadata(file_path, clear_audits=True)


_coordinator_instance: Optional[SourceMetadataCoordinator] = None
_default_coordinator: Optional[SourceMetadataCoordinator] = None


def set_source_metadata_coordinator(
    coord: Optional[SourceMetadataCoordinator],
) -> None:
    """Sets or clears override coordinator instance."""
    global _coordinator_instance
    _coordinator_instance = coord


def _get_coordinator() -> SourceMetadataCoordinator:
    global _coordinator_instance, _default_coordinator
    if _coordinator_instance is not None:
        return _coordinator_instance
    try:
        from support.lib.lifecycle import get_singleton
        return get_singleton(SourceMetadataCoordinator)
    except Exception:
        if _default_coordinator is None:
            _default_coordinator = _DefaultSourceMetadataCoordinator()
        return _default_coordinator


def current_utc_timestamp() -> str:
    """Returns current UTC timestamp truncated to seconds with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_metadata_from_text(
    content: str, filename_or_ext: str
) -> Optional[FileMetadata]:
    return _get_coordinator().extract_metadata_from_text(content, filename_or_ext)


def extract_metadata(file_path: Path | str) -> Optional[FileMetadata]:
    return _get_coordinator().extract_metadata(file_path)


def extract_code_body(content: str, filename_or_ext: str) -> str:
    return _get_coordinator().extract_code_body(content, filename_or_ext)


def compute_code_hash(content: str, filename_or_ext: str) -> str:
    return _get_coordinator().compute_code_hash(content, filename_or_ext)


def compute_file_code_hash(file_path: Path | str) -> Optional[str]:
    return _get_coordinator().compute_file_code_hash(file_path)


def is_code_modified(file_path: Path | str) -> bool:
    return _get_coordinator().is_code_modified(file_path)


def rewrite_metadata_in_text(
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
    return _get_coordinator().rewrite_metadata_in_text(
        content=content,
        filename_or_ext=filename_or_ext,
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


def update_metadata(
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
    _get_coordinator().update_metadata(
        file_path=file_path,
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


def delete_last_cleaned(file_path: Path | str) -> None:
    _get_coordinator().delete_last_cleaned(file_path)


def mark_dirty(file_path: Path | str, reason: str = "manual dirty") -> None:
    _get_coordinator().mark_dirty(file_path, reason=reason)


def mark_clean(file_path: Path | str, default_change: str = "new file") -> None:
    _get_coordinator().mark_clean(file_path, default_change=default_change)


def record_change(
    file_path: Path | str,
    change_description: str,
    code_hash: Optional[str] = None,
) -> None:
    _get_coordinator().record_change(
        file_path, change_description, code_hash=code_hash
    )


def append_feedback(
    file_path: Path | str, explanation: str, sender: str = "user"
) -> None:
    _get_coordinator().append_feedback(file_path, explanation, sender=sender)


def stamp_audit(file_path: Path | str, role_name: str) -> None:
    _get_coordinator().stamp_audit(file_path, role_name)


def clear_audits(file_path: Path | str) -> None:
    _get_coordinator().clear_audits(file_path)
