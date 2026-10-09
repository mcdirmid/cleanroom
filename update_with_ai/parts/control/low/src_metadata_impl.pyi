# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 5d74dff53adc
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for src_metadata_impl."""

from pathlib import Path
from typing import Dict, Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import src_metadata


@singleton_type("agent_session")
class SourceMetadataCoordinator(
    src_metadata.SourceMetadataCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of source metadata coordinator.

    GROUNDING:
    - Realizes in-band source file metadata parsing, deterministic code hashing, and in-place
      rewriting by identifying HTML and line hash comment delimiters, locating boundary indices,
      extracting code bodies, computing SHA-256 digests, and updating header blocks on disk.
    """

    @operation
    @override
    def extract_metadata_from_text(
        self,
        content: str,
        filename_or_ext: str,
    ) -> Optional[src_metadata.FileMetadata]:
        """Extracts in-band metadata record from content string.

        GROUNDING:
        - Grounded via regex boundary detection of HTML comment blocks for Markdown or line
          hash comment blocks for Python and Starlark, followed by key-value field extraction.
        """
        ...

    @operation
    @override
    def extract_metadata(
        self,
        file_path: Path | str,
    ) -> Optional[src_metadata.FileMetadata]:
        """Reads file on disk and extracts its in-band metadata block.

        GROUNDING:
        - Grounded via Path filesystem inspection, UTF-8 file reading, and delegation to
          extract_metadata_from_text.
        """
        ...

    @operation
    @override
    def extract_code_body(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str:
        """Extracts source code body strictly excluding metadata comment header.

        GROUNDING:
        - Grounded via block boundary detection, line concatenation of lines before start index
          and lines after end index, and whitespace trimming.
        """
        ...

    @operation
    @override
    def compute_code_hash(
        self,
        content: str,
        filename_or_ext: str,
    ) -> str:
        """Computes twelve-character SHA-256 hexadecimal hash of extracted code body.

        GROUNDING:
        - Grounded via extract_code_body and standard hashlib sha256 hex digest truncated to 12 chars.
        """
        ...

    @operation
    @override
    def compute_file_code_hash(
        self,
        file_path: Path | str,
    ) -> Optional[str]:
        """Computes code hash for file on disk excluding metadata comment header.

        GROUNDING:
        - Grounded via Path file existence check, UTF-8 read, and delegation to compute_code_hash.
        """
        ...

    @operation
    @override
    def is_code_modified(
        self,
        file_path: Path | str,
    ) -> bool:
        """Evaluates whether file on disk has code modifications compared to in-band code hash.

        GROUNDING:
        - Grounded via extract_metadata to read recorded code hash, compute_file_code_hash to get
          current disk hash, and equality comparison.
        """
        ...

    @operation
    @override
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

        GROUNDING:
        - Grounded via boundary slicing, header formatting, insertion point determination
          below shebang or frontmatter lines, and trailing newline preservation.
        """
        ...

    @operation
    @override
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

        GROUNDING:
        - Grounded via rewrite_metadata_in_text and Path write_text with parent directory creation.
        """
        ...

    @operation
    @override
    def delete_last_cleaned(
        self,
        file_path: Path | str,
    ) -> None:
        """Removes LAST_CLEANED timestamp from file in-band metadata block.

        GROUNDING:
        - Grounded via update_metadata with clear_last_cleaned set to True.
        """
        ...

    @operation
    @override
    def mark_dirty(
        self,
        file_path: Path | str,
        reason: str = "manual dirty",
    ) -> None:
        """Marks node dirty by adding DIRTY tag and advancing LAST_CLEANED to now.

        GROUNDING:
        - Grounded via update_metadata with dirty reason and current UTC timestamp.
        """
        ...

    @operation
    @override
    def mark_clean(
        self,
        file_path: Path | str,
        default_change: str = "new file",
    ) -> None:
        """Sets LAST_CLEANED to now, updates code hash, and clears feedback and dirty tags.

        GROUNDING:
        - Grounded via extract_metadata to resolve previous change state, compute_file_code_hash,
          and update_metadata with clear_feedback and clear_dirty set to True.
        """
        ...

    @operation
    @override
    def record_change(
        self,
        file_path: Path | str,
        change_description: str,
        code_hash: Optional[str] = None,
    ) -> None:
        """Marks node changed with updated timestamps, change description, and code hash.

        GROUNDING:
        - Grounded via compute_file_code_hash and update_metadata with current UTC timestamp for
          both last cleaned and last changed, clearing feedback, audits, and dirty tags.
        """
        ...

    @operation
    @override
    def append_feedback(
        self,
        file_path: Path | str,
        explanation: str,
        sender: str = "user",
    ) -> None:
        """Appends unacted feedback item to file metadata block and advances LAST_CLEANED.

        GROUNDING:
        - Grounded via feedback bracket formatting and update_metadata with append_feedback.
        """
        ...

    @operation
    @override
    def stamp_audit(
        self,
        file_path: Path | str,
        role_name: str,
    ) -> None:
        """Stamps role audit timestamp in file header and advances LAST_CLEANED.

        GROUNDING:
        - Grounded via update_metadata with stamp_audit set to role name.
        """
        ...

    @operation
    @override
    def clear_audits(
        self,
        file_path: Path | str,
    ) -> None:
        """Removes all audit tags from file in-band metadata block.

        GROUNDING:
        - Grounded via update_metadata with clear_audits set to True.
        """
        ...
