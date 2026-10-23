from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple


# Contract: __orphan__ - MUST derive canonical audit tag strings from role names.
def get_audit_tag(role_name: str) -> str:
    """Computes auditor tag dynamically: uppercase role name + _AUDIT."""
    clean = role_name.split(":")[-1].strip().upper()
    return clean if clean.endswith("_AUDIT") else f"{clean}_AUDIT"


def _load_role_definitions() -> Dict[str, Any]:
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
        cand = os.path.join(root, "cleanroom_roles.toml")
        if os.path.isfile(cand):
            try:
                with open(cand, "rb") as f:
                    roles = tomllib.load(f).get("roles", {})
                    if roles:
                        return roles
            except Exception:
                pass
        c_cand = os.path.join(root, "cleanroom.toml")
        if os.path.isfile(c_cand):
            try:
                with open(c_cand, "rb") as f:
                    c_data = tomllib.load(f)
                meth = c_data.get("methodology")
                if meth and isinstance(meth, str):
                    pkg = meth.lstrip("/").split(":")[0]
                    r_cand = os.path.join(root, pkg, "cleanroom_roles.toml")
                    if os.path.isfile(r_cand):
                        with open(r_cand, "rb") as f:
                            roles = tomllib.load(f).get("roles", {})
                            if roles:
                                return roles
            except Exception:
                pass
        try:
            for entry in os.listdir(root):
                sub = os.path.join(root, entry)
                if os.path.isdir(sub) and not entry.startswith((".", "bazel-", "venv")):
                    sub_cand = os.path.join(sub, "cleanroom_roles.toml")
                    if os.path.isfile(sub_cand):
                        with open(sub_cand, "rb") as f:
                            roles = tomllib.load(f).get("roles", {})
                            if roles:
                                return roles
        except Exception:
            pass
    return {}


# Contract: __orphan__ - MUST evaluate whether a role name denotes an auditor role.
def is_auditor_role(role_name: str) -> bool:
    """Checks whether a role is an auditor dynamically without hardcoded role names."""
    clean = role_name.split(":")[-1].strip().lower()
    try:
        from support.lib.lifecycle import Singleton, SystemTier, get_singleton
        from update_with_ai.parts.workspace.lib import role_registry
        reg = get_singleton(role_registry.WorkspaceRegistry)
        r_def = reg.resolve_role_definition(clean)
        return not r_def.writable_file_patterns or bool(r_def.audit_tag)
    except Exception:
        pass
    try:
        from support.lib.lifecycle import Singleton, SystemTier, get_singleton
        from update_with_ai.parts.agent.lib import node_config
        cfg: Any = get_singleton(node_config.NodeConfig)
        role_defs = cfg.role_definitions if hasattr(cfg, "role_definitions") else {}
        if clean in role_defs:
            r_def: Any = role_defs[clean]
            if isinstance(r_def, dict):
                audit_tag = r_def.get("audit_tag")
                src_pat = str(r_def.get("src_pattern", "") or "")
                is_aud = bool(r_def.get("is_auditor", False))
            else:
                audit_tag = r_def.audit_tag if hasattr(r_def, "audit_tag") else None
                src_pat = str(r_def.src_pattern or "") if hasattr(r_def, "src_pattern") else ""
                is_aud = bool(r_def.is_auditor) if hasattr(r_def, "is_auditor") else False
            return bool(is_aud or audit_tag or not src_pat)
    except Exception:
        pass
    role_defs = _load_role_definitions()
    if clean in role_defs:
        r_def = role_defs[clean]
        return bool(r_def.get("audit_tag") or not r_def.get("src_pattern"))
    return clean in ("auditor", "audit") or clean.endswith(("_audit", "_auditor"))


# Contract: FileMetadata encapsulates in-band source file metadata attributes.
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


# Contract: SourceMetadataCoordinator protocol for parsing, hashing, and mutating in-band source metadata.
class SourceMetadataCoordinator(Singleton[SystemTier], Protocol):
    """Protocol for parsing, hashing, and mutating in-band source metadata."""

    # Contract: Extracts in-band metadata record from content string.
    def extract_metadata_from_text(
        self,
        content: str,
        filename_or_ext: str,
    ) -> Optional[FileMetadata]: ...

    # Contract: Reads file on disk and extracts its in-band metadata block.
    def extract_metadata(
        self,
        file_path: Path | str,
    ) -> Optional[FileMetadata]: ...

    # Contract: Extracts source code body strictly excluding metadata comment header.
    def extract_code_body(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str: ...

    # Contract: Computes twelve-character SHA-256 hexadecimal hash of extracted code body.
    def compute_code_hash(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str: ...

    # Contract: Computes code hash for file on disk excluding metadata comment header.
    def compute_file_code_hash(
        self,
        file_path: Path | str,
    ) -> Optional[str]: ...

    # Contract: Evaluates whether file on disk has code modifications compared to in-band code hash.
    def is_code_modified(
        self,
        file_path: Path | str,
    ) -> bool: ...

    # Contract: Evaluates whether new content alters, corrupts, deletes, or injects in-band metadata.
    def is_metadata_altered(
        self,
        original_content: str,
        new_content: str,
        filename_or_ext: str,
    ) -> bool: ...

    # Contract: Updates or injects in-band metadata block within content string.
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

    # Contract: Rewrites file on disk in-place, updating metadata block while preserving code.
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

    # Contract: Removes LAST_CLEANED timestamp from file in-band metadata block.
    def delete_last_cleaned(
        self,
        file_path: Path | str,
    ) -> None: ...

    # Contract: Marks node dirty by adding DIRTY tag and advancing LAST_CLEANED to now.
    def mark_dirty(
        self,
        file_path: Path | str,
        reason: str = "manual dirty",
    ) -> None: ...

    # Contract: Sets LAST_CLEANED to now, updates code hash, and clears feedback and dirty tags.
    def mark_clean(
        self,
        file_path: Path | str,
        default_change: str = "new file",
    ) -> None: ...

    # Contract: Marks node changed with updated timestamps, change description, and code hash.
    def record_change(
        self,
        file_path: Path | str,
        change_description: str,
        code_hash: Optional[str] = None,
    ) -> None: ...

    # Contract: Appends unacted feedback item to file metadata block and advances LAST_CLEANED.
    def append_feedback(
        self,
        file_path: Path | str,
        explanation: str,
        sender: str = "user",
    ) -> None: ...

    # Contract: Stamps role audit timestamp in file header and advances LAST_CLEANED.
    def stamp_audit(
        self,
        file_path: Path | str,
        role_name: str,
    ) -> None: ...

    # Contract: Removes all audit tags from file in-band metadata block.
    def clear_audits(
        self,
        file_path: Path | str,
    ) -> None: ...


# Contract: __orphan__ - module-level helper evaluating Markdown format convention.
def _is_html_comment_format(path_or_ext: str) -> bool:
    ext = os.path.splitext(path_or_ext)[1].lower()
    return ext == ".md"


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def _find_header_insertion_index(lines: List[str], is_html: bool) -> int:
    """Determines line index where metadata block should be inserted when missing."""
    return len(lines)


# Contract: __orphan__ - module-level helper extracting block boundary range.
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


# Contract: __orphan__ - MUST parse in-band metadata block content into FileMetadata records.
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


# Contract: __orphan__ - MUST format FileMetadata records into comment lines for supported languages.
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


def _get_coordinator() -> SourceMetadataCoordinator:
    try:
        from support.lib.lifecycle import Singleton, SystemTier, get_singleton
        return get_singleton(SourceMetadataCoordinator)
    except Exception:
        from support.lib.lifecycle import Singleton, SystemTier, get_default_registry
        desc = get_default_registry().find_descriptor(SourceMetadataCoordinator)
        if desc is None:
            from . import metadata_asm
            metadata_asm.__initialize__()
            desc = get_default_registry().find_descriptor(SourceMetadataCoordinator)
        if desc is not None:
            if desc.instance is not None:
                return desc.instance
            if desc.impl is not None:
                return desc.impl()
        raise


# Contract: __orphan__ - MUST return the current UTC timestamp formatted as an ISO-8601 string.
def current_utc_timestamp() -> str:
    """Returns current UTC timestamp truncated to seconds with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def extract_metadata_from_text(
    content: str, filename_or_ext: str
) -> Optional[FileMetadata]:
    return _get_coordinator().extract_metadata_from_text(content, filename_or_ext)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def extract_metadata(file_path: Path | str) -> Optional[FileMetadata]:
    return _get_coordinator().extract_metadata(file_path)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def extract_code_body(content: str, filename_or_ext: str) -> str:
    return _get_coordinator().extract_code_body(content, filename_or_ext)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def compute_code_hash(content: str, filename_or_ext: str) -> str:
    return _get_coordinator().compute_code_hash(content, filename_or_ext)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def compute_file_code_hash(file_path: Path | str) -> Optional[str]:
    return _get_coordinator().compute_file_code_hash(file_path)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def is_code_modified(file_path: Path | str) -> bool:
    return _get_coordinator().is_code_modified(file_path)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def is_metadata_altered(
    original_content: str,
    new_content: str,
    filename_or_ext: str,
) -> bool:
    return _get_coordinator().is_metadata_altered(
        original_content=original_content,
        new_content=new_content,
        filename_or_ext=filename_or_ext,
    )


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
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


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
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


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def delete_last_cleaned(file_path: Path | str) -> None:
    _get_coordinator().delete_last_cleaned(file_path)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def mark_dirty(file_path: Path | str, reason: str = "manual dirty") -> None:
    _get_coordinator().mark_dirty(file_path, reason=reason)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def mark_clean(file_path: Path | str, default_change: str = "new file") -> None:
    _get_coordinator().mark_clean(file_path, default_change=default_change)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def record_change(
    file_path: Path | str,
    change_description: str,
    code_hash: Optional[str] = None,
) -> None:
    _get_coordinator().record_change(
        file_path, change_description, code_hash=code_hash
    )


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def append_feedback(
    file_path: Path | str, explanation: str, sender: str = "user"
) -> None:
    _get_coordinator().append_feedback(file_path, explanation, sender=sender)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def stamp_audit(file_path: Path | str, role_name: str) -> None:
    _get_coordinator().stamp_audit(file_path, role_name)


# Contract: __orphan__ - module-level procedural facade delegating to SourceMetadataCoordinator.
def clear_audits(file_path: Path | str) -> None:
    _get_coordinator().clear_audits(file_path)

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-20T22:32:00Z
# CHANGE: Expose is_metadata_altered on SourceMetadataCoordinator and module facade
# --- END CLEANROOM METADATA ---
