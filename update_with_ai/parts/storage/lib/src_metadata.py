# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:40:00Z
# CHANGE: Separate interface and forwarding from realization
# CODE_HASH: 1dadd82533ae
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple


def get_audit_tag(role_name: str) -> str:
    """Computes auditor tag dynamically: uppercase role name + _AUDIT."""
    clean = role_name.split(":")[-1].strip().upper()
    return clean if clean.endswith("_AUDIT") else f"{clean}_AUDIT"


def _load_role_definitions_from_roles_toml() -> Dict[str, Any]:
    bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
    search_roots = [bwd]
    cur = bwd
    while cur and cur != os.path.dirname(cur):
        search_roots.append(cur)
        cur = os.path.dirname(cur)
    cur = os.path.abspath(os.path.dirname(__file__))
    while cur and cur != os.path.dirname(cur):
        search_roots.append(cur)
        cur = os.path.dirname(cur)
    import tomllib
    for root in search_roots:
        for fname in (
            "cleanroom_roles.toml",
            "cleanroom_python_roles.toml",
            os.path.join("update_python_with_ai", "cleanroom_roles.toml"),
        ):
            cand = os.path.join(root, fname)
            if os.path.isfile(cand):
                try:
                    with open(cand, "rb") as f:
                        data = tomllib.load(f)
                        roles = data.get("roles", {})
                        if roles:
                            return roles
                except Exception:
                    pass
    return {}


def is_auditor_role(role_name: str) -> bool:
    """Checks whether a role is an auditor dynamically without hardcoded role names."""
    clean = role_name.split(":")[-1].strip().lower()
    try:
        from support.lib.lifecycle import get_singleton
        from update_with_ai.parts.agent.lib import agent_node_config
        cfg = get_singleton(agent_node_config.NodeConfig)
        role_defs = getattr(cfg, "role_definitions", {})
        if clean in role_defs:
            r_def = role_defs[clean]
            return bool(
                getattr(r_def, "is_auditor", False)
                or getattr(r_def, "audit_tag", None)
                or not getattr(r_def, "src_pattern", "")
            )
    except Exception:
        pass
    role_defs = _load_role_definitions_from_roles_toml()
    if clean in role_defs:
        r_def = role_defs[clean]
        return bool(r_def.get("audit_tag") or not r_def.get("src_pattern"))
    if clean in ("auditor", "audit") or clean.endswith(("_audit", "_auditor")):
        return True
    return False


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


_coordinator_override: Optional[SourceMetadataCoordinator] = None


def set_source_metadata_coordinator(
    coord: Optional[SourceMetadataCoordinator],
) -> None:
    """Sets or clears override coordinator instance."""
    global _coordinator_override
    _coordinator_override = coord


def _get_coordinator() -> SourceMetadataCoordinator:
    if _coordinator_override is not None:
        return _coordinator_override
    try:
        from support.lib.lifecycle import get_singleton
        return get_singleton(SourceMetadataCoordinator)
    except Exception:
        from support.lib.lifecycle import get_default_registry
        desc = get_default_registry().find_descriptor(SourceMetadataCoordinator)
        if desc is None:
            from . import storage_asm
            storage_asm.__initialize__()
            desc = get_default_registry().find_descriptor(SourceMetadataCoordinator)
        if desc is not None:
            if desc.instance is not None:
                return desc.instance
            if desc.impl is not None:
                return desc.impl()
        raise


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
