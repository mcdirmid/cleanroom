"""Low-level interface specification for src_metadata."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Protocol
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier


@data_type
@dataclass(frozen=True)
class ChangeEntry:
    """Encapsulates a single timestamped structured change entry in CHANGES:.

    Args:
        timestamp: ISO 8601 UTC timestamp of submission.
        kind: Change kind ('new', 'contract', 'behavior', 'fix', 'refactor', or 'legacy').
        lines: 1-based changed line spans ('NEW', '42-68, 115-129', 'del@42', 'superseded', or '').
        scope: Optional comma-separated touched symbols/sections.
        delta: Concise before-to-after description of what changed locally.
        why: Optional local invariant or fix intent.
    """

    timestamp: str
    kind: str
    lines: str
    scope: Optional[str]
    delta: str
    why: Optional[str] = None


@data_type
@dataclass(frozen=True)
class FileMetadata:
    """Encapsulates in-band source file metadata attributes.

    Args:
        last_cleaned: ISO 8601 UTC timestamp of last clean operation.
        last_changed: ISO 8601 UTC timestamp of last content modification.
        change_summary: Single-line description of recent changes.
        feedback: Unacted diagnostic feedback items.
        audits: Role audit timestamps keyed by audit tag name.
        dirty: Optional explanation reason when node is marked dirty.
        changes: Chronological list of structured change entries.
    """

    last_cleaned: Optional[str]
    last_changed: Optional[str]
    change_summary: str
    feedback: List[str]
    audits: Dict[str, str] = field(default_factory=dict)
    dirty: Optional[str] = None
    changes: List[ChangeEntry] = field(default_factory=list)


@singleton_type("system")
class SourceMetadataCoordinator(Singleton[SystemTier], Protocol):
    """Coordinator that parses, hashes, and mutates in-band source metadata."""

    @operation
    def extract_metadata_from_text(
        self,
        content: str,
        filename_or_ext: str,
    ) -> Optional[FileMetadata]:
        """Extracts in-band metadata record from content string.

        POSTCONDITIONS:
        - When content contains valid metadata block, MUST return populated FileMetadata.
        - When content contains no metadata block, MUST return None.
        """
        ...

    @operation
    def extract_metadata(
        self,
        file_path: Path | str,
    ) -> Optional[FileMetadata]:
        """Reads file on disk and extracts its in-band metadata block.

        POSTCONDITIONS:
        - When file exists and contains metadata block, MUST return populated FileMetadata.
        - When file does not exist or read fails, MUST return None.
        """
        ...

    @operation
    def extract_code_body(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str:
        """Extracts source code body strictly excluding metadata comment header.

        POSTCONDITIONS:
        - MUST return content lines outside metadata comment header boundaries.
        """
        ...

    @operation
    def compute_code_hash(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str:
        """Computes twelve-character SHA-256 hexadecimal hash of extracted code body.

        POSTCONDITIONS:
        - MUST return first twelve characters of SHA-256 digest of code body.
        """
        ...

    @operation
    def compute_file_code_hash(
        self,
        file_path: Path | str,
    ) -> Optional[str]:
        """Computes code hash for file on disk excluding metadata comment header.

        POSTCONDITIONS:
        - When file exists on disk, MUST return twelve-character code hash.
        - When file does not exist, MUST return None.
        """
        ...

    @operation
    def is_code_modified(
        self,
        file_path: Path | str,
        workspace_root: Optional[Path | str] = None,
    ) -> bool:
        """Evaluates whether file on disk has code modifications compared to the role workspace pull manifest baseline.

        POSTCONDITIONS:
        - When file does not exist or has no recorded baseline code hash in `.autofab/pull_manifest.json`, MUST return True.
        - When on-disk code hash differs from recorded baseline code hash, MUST return True.
        - When on-disk code hash matches recorded baseline code hash, MUST return False.
        """
        ...

    @operation
    def is_metadata_altered(
        self,
        original_content: str,
        new_content: str,
        filename_or_ext: str,
    ) -> bool:
        """Evaluates whether new content alters, corrupts, deletes, or injects in-band metadata relative to original content.

        POSTCONDITIONS:
        - When original content contains metadata and new content deletes or alters the metadata block, MUST return True.
        - When original content contains metadata and new content preserves the identical metadata block, MUST return False.
        - When original content contains no metadata and new content introduces metadata delimiters or a metadata block, MUST return True.
        - When original content contains no metadata and new content contains no metadata delimiters or block, MUST return False.
        """
        ...

    @operation
    def rewrite_metadata_in_text(
        self,
        content: str,
        filename_or_ext: str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
        changes: Optional[List[ChangeEntry]] = None,
        clear_changes: bool = False,
        append_change: Optional[ChangeEntry] = None,
    ) -> str:
        """Updates or injects in-band metadata block within content string.

        POSTCONDITIONS:
        - MUST update specified fields while preserving existing unmodified fields.
        - When existing metadata block present, MUST update block, placing it at the bottom of the content string.
        - When existing metadata block absent, MUST append block at the bottom of the content string.
        - MUST preserve trailing newline status of original content.
        """
        ...

    @operation
    def update_metadata(
        self,
        file_path: Path | str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
        changes: Optional[List[ChangeEntry]] = None,
        clear_changes: bool = False,
        append_change: Optional[ChangeEntry] = None,
    ) -> None:
        """Rewrites file on disk in-place, updating metadata block while preserving code.

        POSTCONDITIONS:
        - MUST rewrite file on disk with updated metadata block.
        - MUST create parent directories when absent.
        """
        ...

    @operation
    def delete_last_cleaned(
        self,
        file_path: Path | str,
    ) -> None:
        """Removes LAST_CLEANED timestamp from file in-band metadata block.

        POSTCONDITIONS:
        - MUST rewrite file clearing last cleaned timestamp.
        """
        ...

    @operation
    def mark_dirty(
        self,
        file_path: Path | str,
        reason: str = "manual dirty",
    ) -> None:
        """Marks node dirty by adding DIRTY tag and advancing LAST_CLEANED to now.

        POSTCONDITIONS:
        - MUST rewrite file with dirty reason and current UTC timestamp.
        """
        ...

    @operation
    def mark_clean(
        self,
        file_path: Path | str,
        default_change: str = "new file",
    ) -> None:
        """Sets LAST_CLEANED to now, updates code hash, and clears feedback and dirty tags.

        POSTCONDITIONS:
        - MUST update last cleaned to now and ensure code hash matches disk content.
        - MUST clear unacted feedback and dirty tags.
        """
        ...

    @operation
    def record_change(
        self,
        file_path: Path | str,
        change_description: str,
        kind: str = "behavior",
        scope: Optional[str] = None,
        why: Optional[str] = None,
        prior_content: Optional[str] = None,
    ) -> None:
        """Marks node changed with updated timestamps, rebased prior spans, and bounded structured change entry.

        POSTCONDITIONS:
        - MUST update last cleaned and last changed timestamps to now.
        - MUST append structured ChangeEntry (rebasing prior entries when prior_content is provided and capping to MAX_CHANGE_ENTRIES).
        - MUST clear unacted feedback, audits, and dirty tags.
        """
        ...

    @operation
    def compute_changed_lines(
        self,
        old_content: Optional[str],
        new_content: str,
        filename_or_ext: str,
    ) -> str:
        """Computes 1-based changed line spans between old_content and new_content code bodies.

        POSTCONDITIONS:
        - When old_content is None, MUST return 'NEW'.
        - When code bodies are identical, MUST return ''.
        - Otherwise MUST return comma-separated 1-based line spans or 'del@<line>' anchors in new_content.
        """
        ...

    @operation
    def rebase_change_entries(
        self,
        entries: List[ChangeEntry],
        old_content: Optional[str],
        new_content: str,
        filename_or_ext: str,
    ) -> List[ChangeEntry]:
        """Rebases existing ChangeEntry line spans from old_content coordinates to new_content coordinates.

        POSTCONDITIONS:
        - MUST preserve 'NEW' and 'superseded' entries unchanged.
        - MUST shift untouched spans by sequence-matcher opcode offsets and collapse wholly overwritten/deleted spans.
        """
        ...

    @operation
    def filter_changes_since(
        self,
        entries: List[ChangeEntry],
        since_timestamp: Optional[str],
    ) -> List[ChangeEntry]:
        """Filters ChangeEntry items strictly newer than since_timestamp.

        POSTCONDITIONS:
        - When since_timestamp is None or empty, MUST return all entries.
        - Otherwise MUST return only entries with timestamp strictly greater than since_timestamp.
        """
        ...

    @operation
    def project_workspace_metadata(
        self,
        content: str,
        filename_or_ext: str,
        strip_changes: bool = False,
        since_timestamp: Optional[str] = None,
    ) -> str:
        """Projects in-band metadata for a role workspace by clearing lifecycle timestamps and filtering CHANGES:.

        POSTCONDITIONS:
        - MUST clear LAST_CLEANED, LAST_CHANGED, *_AUDIT, and DIRTY.
        - When strip_changes is True, MUST remove all CHANGES: entries.
        - When since_timestamp is provided and strip_changes is False, MUST retain only entries newer than since_timestamp.
        """
        ...

    @operation
    def append_feedback(
        self,
        file_path: Path | str,
        explanation: str,
        sender: str = "user",
    ) -> None:
        """Appends unacted feedback item with sender role attribution to file metadata block and advances LAST_CLEANED.

        POSTCONDITIONS:
        - MUST append formatted feedback entry (attributed with [from:<sender>] when sender is non-user) and advance last cleaned timestamp to now.
        """
        ...

    @operation
    def stamp_audit(
        self,
        file_path: Path | str,
        role_name: str,
    ) -> None:
        """Stamps role audit timestamp in file header and advances LAST_CLEANED.

        POSTCONDITIONS:
        - MUST record role audit timestamp as now and advance last cleaned timestamp to now.
        """
        ...

    @operation
    def clear_audits(
        self,
        file_path: Path | str,
    ) -> None:
        """Removes all audit tags from file in-band metadata block.

        POSTCONDITIONS:
        - MUST rewrite file clearing all audit tags.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for module-level procedural facade functions.

    POSTCONDITIONS:
    - MUST delegate module-level procedural queries and mutations to the active SourceMetadataCoordinator singleton.
    - MUST expose module-level functions for metadata extraction, code body isolation, code hashing, modification checks, metadata alteration checks, and lifecycle updates.
    - MUST derive canonical audit tag strings from role names.
    - MUST evaluate whether a role name denotes an auditor role.
    - MUST parse in-band metadata block content into FileMetadata records.
    - MUST format FileMetadata records into comment lines for supported languages.
    - MUST return the current UTC timestamp formatted as an ISO-8601 string.
    """
    ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-20T22:32:00Z
# CHANGE: Contract is_metadata_altered on SourceMetadataCoordinator and module facade
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
