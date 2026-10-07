# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 7f78e07d2165
# --- END CLEANROOM METADATA ---


"""Low-level interface specification for src_metadata."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


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
        code_hash: Twelve-character SHA-256 digest of source code body.
    """

    last_cleaned: Optional[str]
    last_changed: Optional[str]
    change_summary: str
    feedback: List[str]
    audits: Dict[str, str] = field(default_factory=dict)
    dirty: Optional[str] = None
    code_hash: Optional[str] = None


@singleton_type("agent_session")
class SourceMetadataCoordinator(InTier[AgentSessionTier], Protocol):
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
    ) -> bool:
        """Evaluates whether file on disk has code modifications compared to in-band code hash.

        POSTCONDITIONS:
        - When file does not exist or has no recorded code hash, MUST return True.
        - When on-disk code hash differs from recorded code hash, MUST return True.
        - When on-disk code hash matches recorded code hash, MUST return False.
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
        """Updates or injects in-band metadata block within content string.

        POSTCONDITIONS:
        - MUST update specified fields while preserving existing unmodified fields.
        - When existing metadata block present, MUST replace block in-place.
        - When existing metadata block absent, MUST insert block below shebang or frontmatter.
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
        code_hash: Optional[str] = None,
    ) -> None:
        """Marks node changed with updated timestamps, change description, and code hash.

        POSTCONDITIONS:
        - MUST update last cleaned and last changed timestamps to now.
        - MUST record change description and stamp new code hash.
        - MUST clear unacted feedback, audits, and dirty tags.
        """
        ...

    @operation
    def append_feedback(
        self,
        file_path: Path | str,
        explanation: str,
        sender: str = "user",
    ) -> None:
        """Appends unacted feedback item to file metadata block and advances LAST_CLEANED.

        POSTCONDITIONS:
        - MUST append formatted feedback entry and advance last cleaned timestamp to now.
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
