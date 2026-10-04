"""Hermetic and declarative in-band source file metadata parsing and updating engine."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class FileMetadata:
    last_cleaned: Optional[str]
    last_changed: Optional[str]
    change_summary: str
    feedback: List[str]


def current_utc_timestamp() -> str:
    """Returns the current UTC timestamp truncated to seconds with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_html_comment_format(path_or_ext: str) -> bool:
    ext = os.path.splitext(path_or_ext)[1].lower()
    return ext == ".md"


def _find_header_insertion_index(lines: List[str], is_html: bool) -> int:
    """Determines line index where metadata block should be inserted when missing."""
    if not lines:
        return 0

    if is_html:
        # Check for YAML frontmatter
        if lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    return i + 1
        return 0

    # Line comment format: skip shebang and encoding
    idx = 0
    if idx < len(lines) and lines[idx].startswith("#!"):
        idx += 1
    if idx < len(lines) and ("coding:" in lines[idx] or "coding=" in lines[idx]):
        idx += 1
    return idx


def _extract_block_boundaries(lines: List[str], is_html: bool) -> Optional[Tuple[int, int]]:
    """Locates (start_line_idx, end_line_idx) inclusive for the metadata block at the file header."""
    if is_html:
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx < len(lines) and lines[idx].strip() == "---":
            idx += 1
            while idx < len(lines) and lines[idx].strip() != "---":
                idx += 1
            if idx < len(lines):
                idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx < len(lines):
            stripped = lines[idx].strip()
            if stripped.startswith("<!--") and "CLEANROOM METADATA" in stripped:
                start_idx = idx
                for i in range(start_idx, len(lines)):
                    if "-->" in lines[i]:
                        return (start_idx, i)
        return None

    # Line hash comments
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and lines[idx].startswith("#!"):
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and ("coding:" in lines[idx] or "coding=" in lines[idx]):
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and lines[idx].strip() == "# --- CLEANROOM METADATA ---":
        start_idx = idx
        for i in range(start_idx + 1, len(lines)):
            if lines[i].strip() == "# --- END CLEANROOM METADATA ---":
                return (start_idx, i)
    return None


def parse_metadata_content(block_lines: List[str]) -> FileMetadata:
    """Parses raw metadata block lines into FileMetadata."""
    last_cleaned: Optional[str] = None
    last_changed: Optional[str] = None
    change_summary = ""
    feedback: List[str] = []

    in_feedback = False
    for line in block_lines:
        raw = line.strip()
        # Strip comment syntax
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
        elif raw.startswith("LAST_CHANGED:"):
            val = raw.split(":", 1)[1].strip()
            last_changed = val if val else None
            in_feedback = False
        elif raw.startswith("CHANGE:"):
            change_summary = raw.split(":", 1)[1].strip()
            in_feedback = False
        elif raw.startswith("FEEDBACK:"):
            in_feedback = True
        elif in_feedback:
            if raw.startswith("-"):
                item = raw[1:].strip()
                if item:
                    feedback.append(item)
            elif raw.startswith("LAST_") or raw.startswith("CHANGE:"):
                in_feedback = False

    return FileMetadata(
        last_cleaned=last_cleaned,
        last_changed=last_changed,
        change_summary=change_summary,
        feedback=feedback,
    )


def extract_metadata_from_text(content: str, filename_or_ext: str) -> Optional[FileMetadata]:
    """Extracts in-band metadata from raw string content."""
    is_html = _is_html_comment_format(filename_or_ext)
    lines = content.splitlines()
    bounds = _extract_block_boundaries(lines, is_html)
    if bounds is None:
        return None
    start, end = bounds
    return parse_metadata_content(lines[start : end + 1])


def extract_metadata(file_path: Path | str) -> Optional[FileMetadata]:
    """Reads a source file and extracts its in-band metadata block."""
    p = Path(file_path)
    if not p.is_file():
        return None
    try:
        content = p.read_text(encoding="utf-8")
        return extract_metadata_from_text(content, p.name)
    except OSError:
        return None


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
        if meta.feedback:
            lines.append("# FEEDBACK:")
            for fb in meta.feedback:
                lines.append(f"# - {fb}")
        lines.append("# --- END CLEANROOM METADATA ---")
    return lines


def rewrite_metadata_in_text(
    content: str,
    filename_or_ext: str,
    last_cleaned: Optional[str] = None,
    clear_last_cleaned: bool = False,
    last_changed: Optional[str] = None,
    change_summary: Optional[str] = None,
    clear_feedback: bool = False,
    append_feedback: Optional[str] = None,
) -> str:
    """Updates or injects the in-band metadata block within a content string."""
    is_html = _is_html_comment_format(filename_or_ext)
    lines = content.splitlines()
    bounds = _extract_block_boundaries(lines, is_html)

    existing_meta = (
        parse_metadata_content(lines[bounds[0] : bounds[1] + 1])
        if bounds is not None
        else FileMetadata(last_cleaned=None, last_changed=None, change_summary="", feedback=[])
    )

    if clear_last_cleaned:
        new_last_cleaned: Optional[str] = None
    elif last_cleaned is not None:
        new_last_cleaned = last_cleaned
    else:
        new_last_cleaned = existing_meta.last_cleaned

    new_last_changed = last_changed if last_changed is not None else existing_meta.last_changed
    new_change = change_summary if change_summary is not None else existing_meta.change_summary

    if clear_feedback:
        new_feedback: List[str] = []
    else:
        new_feedback = list(existing_meta.feedback)

    if append_feedback:
        new_feedback.append(append_feedback)

    new_meta = FileMetadata(
        last_cleaned=new_last_cleaned,
        last_changed=new_last_changed,
        change_summary=new_change,
        feedback=new_feedback,
    )

    new_block_lines = format_metadata_block(new_meta, is_html)

    if bounds is not None:
        start, end = bounds
        result_lines = lines[:start] + new_block_lines + lines[end + 1 :]
    else:
        insert_idx = _find_header_insertion_index(lines, is_html)
        # Add a trailing blank line after the block if inserting at top
        if insert_idx == 0 and lines:
            new_block_lines.append("")
        result_lines = lines[:insert_idx] + new_block_lines + lines[insert_idx:]

    trailing_newline = content.endswith("\n") or not content
    res = "\n".join(result_lines)
    if trailing_newline and not res.endswith("\n"):
        res += "\n"
    return res


def update_metadata(
    file_path: Path | str,
    last_cleaned: Optional[str] = None,
    clear_last_cleaned: bool = False,
    last_changed: Optional[str] = None,
    change_summary: Optional[str] = None,
    clear_feedback: bool = False,
    append_feedback: Optional[str] = None,
) -> None:
    """Rewrites a file in-place, updating its metadata block while preserving code."""
    p = Path(file_path)
    if p.is_file():
        content = p.read_text(encoding="utf-8")
    else:
        content = ""
    updated = rewrite_metadata_in_text(
        content=content,
        filename_or_ext=p.name,
        last_cleaned=last_cleaned,
        clear_last_cleaned=clear_last_cleaned,
        last_changed=last_changed,
        change_summary=change_summary,
        clear_feedback=clear_feedback,
        append_feedback=append_feedback,
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(updated, encoding="utf-8")


def delete_last_cleaned(file_path: Path | str) -> None:
    """Removes the LAST_CLEANED timestamp from the file's in-band metadata block."""
    update_metadata(file_path, clear_last_cleaned=True)


def mark_clean(file_path: Path | str, default_change: str = "new file") -> None:
    """Sets LAST_CLEANED to now, initializes LAST_CHANGED/CHANGE if missing, and clears feedback."""
    p = Path(file_path)
    existing = extract_metadata(p)
    now = current_utc_timestamp()
    last_changed = existing.last_changed if (existing and existing.last_changed) else now
    change_summary = (
        existing.change_summary
        if (existing and existing.change_summary)
        else default_change
    )
    update_metadata(
        p,
        last_cleaned=now,
        last_changed=last_changed,
        change_summary=change_summary,
        clear_feedback=True,
    )


def record_change(file_path: Path | str, change_description: str) -> None:
    """Marks a node changed: updates LAST_CLEANED, LAST_CHANGED, and CHANGE, clearing feedback."""
    now = current_utc_timestamp()
    update_metadata(
        file_path,
        last_cleaned=now,
        last_changed=now,
        change_summary=change_description,
        clear_feedback=True,
    )


def append_feedback(file_path: Path | str, explanation: str, sender: str = "user") -> None:
    """Appends an unacted feedback item to the file's in-band metadata block."""
    if explanation.startswith("[") and "]:" in explanation:
        entry = explanation
    else:
        now = current_utc_timestamp()
        entry = f"[{now} from {sender}]: {explanation}"
    update_metadata(file_path, append_feedback=entry)


