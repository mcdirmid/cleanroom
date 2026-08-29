"""
Interface LLS: file_view
Provides the file machinery: file mappings, readable/writable policies, the
file tools (read, edit, line-range edit, search), session-start reads,
templates, and the write-occurred flag.
"""

from typing import Dict, List, Optional, Protocol
from dataclasses import dataclass
from .tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolDefinition,
)


# Type definitions
VirtualName = str
FilePath = str
FileMapping = Dict[VirtualName, FilePath]
ReadablePaths = List[VirtualName]
WritablePaths = List[VirtualName]
# Template content keyed by the writable file's virtual name: the initial
# content file_view gives a writable file that does not exist on disk when
# file_view is configured (see specs/low/file_view.md).
TemplateMapping = Dict[VirtualName, str]
SearchResultLimit = int
WriteOccurred = bool


@dataclass
class FileViewConfig:
    """Client-supplied configuration for the file machinery: file mappings
    (each file's virtual name to its full path), the readable and writable
    virtual names, the templates (a mapping from writable virtual names to
    their template content), the search result limit (the maximum rendered
    matches a single search may return), and whether session-start reads are
    enabled."""
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    templates: TemplateMapping
    search_result_limit: SearchResultLimit
    session_start_reads_enabled: bool


class FileView(Protocol):
    """
    Interface for the LLS FileView.

    Provides secure file system operations and the file tools' definitions.
    Stubbing follows tool_provider semantics: when a result's supersedes flag
    is set, the earlier non-stubbed result for the same file is replaced by a
    placeholder, keeping the conversation focused on current state; a result
    with the flag unset supersedes nothing, and at most one earlier result is
    superseded per result.

    Each tool operation produces a ToolCallOutcome: a sequence of one or
    more tool results (ToolResult or PresentedToolResult values) on success,
    or a Signal (a ToolFailure). After a successful file write, the file's
    current content appears in the conversation.
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return the file tools' definitions: read_file, replace,
        update_lines, and search_files, each following the JSON schema
        format expected by the model.

        Always succeeds.
        """
        ...

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        """
        Return the session-start reads: the plain reads of the read-only
        files, for rendering at the beginning of a run before the model's
        first turn.

        When session-start reads are enabled, returns a session-start read
        for every file that is readable but not writable, sorted by virtual
        name; each is a PresentedToolResult pairing the read_file call with
        its plain read result (supersedes unset). When disabled, returns an
        empty list. Requesting the session-start reads changes no file_view
        state.
        """
        ...

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        """
        Read a file's entire content using the virtual name provided by the
        agent.

        Args:
            file_path: Virtual path to the file
            include_line_numbers: Prefix each line with its line number
                (default: false). REQUIRED when reading a writable file that
                already exists on disk: a plain read of such a file fails
                advising the line-numbered view (line numbers are metadata,
                not file content). Allowed only for writable files.

        Returns:
            A one-result sequence: a ToolResult with the (optionally
            line-numbered) content on success, or ToolFailure on policy or
            parameter violations.

        Routing:
            supersedes is True when the file is writable (the read supersedes
            the earlier result for that file); False when the file is not
            writable — reads of readable files are never stubbed.

        Note:
            The result's note reports the file's line count and view.
            Reads are not paginated and are not bounded by a size limit.
        """
        ...

    def replace(self, file_path: VirtualName, old_str: str, new_str: str,
                expect_multiple: bool = False) -> ToolCallOutcome:
        """
        Replace text in a file (content-based search and replace).

        Replaces exactly one occurrence of old_str with new_str; fails when
        old_str is absent or matches more than once unless expect_multiple=True,
        which replaces all occurrences.

        Args:
            file_path: Virtual path to the file
            old_str: Exact text to find (must be non-empty; at most 200
                characters — use update_lines for larger changes)
            new_str: Replacement text (at most 200 characters)
            expect_multiple: If True, replace all occurrences of old_str

        Returns:
            A sequence of two results on success — the write confirmation (a
            ToolResult with supersedes set) and the injected read (a
            PresentedToolResult with the file's full numbered content) — or
            ToolFailure on policy or argument violations (including when the
            file does not exist or either string exceeds the length limit).

        Routing:
            A file write: supersedes is True (the write confirmation
            supersedes the earlier result for the file; the injected read
            supersedes the write confirmation and re-enables the line-numbered
            view). Sets write_occurred flag.

        Note:
            The write confirmation's content and note are a minimal structured
            status; no file content is echoed in it.
        """
        ...

    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                     new_str: str) -> ToolCallOutcome:
        """
        Replace, delete, or insert lines by 1-indexed line range.

        Replaces lines start_line..end_line (inclusive) with new_str;
        start_line > end_line inserts new_str before start_line; empty
        new_str deletes the range.

        Args:
            file_path: Virtual path to the file
            start_line: 1-indexed start line (inclusive), 1..len(file)+1
            end_line: 1-indexed end line (inclusive), 0..len(file)
            new_str: Replacement content

        Returns:
            A sequence of two results on success — the write confirmation (a
            ToolResult with supersedes set) and the injected read (a
            PresentedToolResult with the file's full numbered content) — or
            ToolFailure on policy or argument violations (including when the
            file does not exist or the file's current view is not
            line-numbered).

        Routing:
            A file write: supersedes is True (the write confirmation
            supersedes the earlier result for the file; the injected read
            supersedes the write confirmation and re-enables the line-numbered
            view). Sets write_occurred flag.

        Note:
            The write confirmation's content and note are a minimal structured
            status; no file content is echoed in it.
        """
        ...

    def search_files(self, path: VirtualName = ".", pattern: str = "",
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        """
        Search for a pattern in files using the virtual path provided by the agent.

        Args:
            path: Virtual path to search (recursive)
            pattern: Regex pattern to search for
            offset: Match offset to start from (default: 0)
            limit: Maximum rendered matches to return (must not exceed the
                search result limit); if omitted, returns all rendered
                matches, which fails when more than the search result limit
                exist.

        Returns:
            ToolResult with search results in content on success, or
            ToolFailure on policy, parameter, or pattern violations.

        Routing:
            supersedes is always False (search results never supersede an
            earlier result). Rendered matches are matches found in files that
            are not writable; matches found in writable files are reported as
            counts in the note without content, so search results in the
            conversation never become stale.

        Note:
            The result's note reports the total rendered matches, how many
            remain, the offset to continue from, and the count of suppressed
            matches in writable files.
        """
        ...

    def get_write_occurred(self) -> WriteOccurred:
        """
        Return whether the agent has modified the filesystem during the
        current run.

        Returns:
            True if any file write operation succeeded during the current run,
            False otherwise.
        """
        ...

    # Internal accessors for the termination machinery (run_control reads
    # the changed set, the run-start snapshots, and the current content
    # through the configured file_view; see specs/low/run_control_impl.md).

    def get_changed_files(self) -> List[VirtualName]:
        """The files written by the run, in write order (deduped)."""
        ...

    def get_run_start_snapshot(self, file_path: VirtualName) -> Optional[str]:
        """The file's content at run start (before the run's first write of
        the file); None when no baseline was captured."""
        ...

    def get_current_content(self, file_path: VirtualName) -> Optional[str]:
        """The file's current content on disk; None when unreadable."""
        ...

    def sanitize_paths(self, text: str) -> str:
        """Translate referenced disk paths, workspace paths, and package prefixes in text into virtual names."""
        ...
