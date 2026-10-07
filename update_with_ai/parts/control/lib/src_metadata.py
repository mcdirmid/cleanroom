# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T14:35:00Z
# CHANGE: new file
# CODE_HASH: a877ab67678e
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol


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


def _get_coordinator() -> SourceMetadataCoordinator:
    try:
        from support.lib.lifecycle import get_singleton
        return get_singleton(SourceMetadataCoordinator)
    except Exception:
        from . import src_metadata_impl
        return src_metadata_impl.SourceMetadataCoordinator()


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


def parse_metadata_content(block_lines: List[str]) -> FileMetadata:
    from . import src_metadata_impl
    return src_metadata_impl.parse_metadata_content(block_lines)


def format_metadata_block(meta: FileMetadata, is_html: bool) -> List[str]:
    from . import src_metadata_impl
    return src_metadata_impl.format_metadata_block(meta, is_html)
