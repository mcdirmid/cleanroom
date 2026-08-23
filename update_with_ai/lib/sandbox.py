# lib/sandbox.py
"""
Interface definitions for the LLS Sandbox.
"""

from typing import Callable, Dict, List, Optional, Protocol, Tuple
from dataclasses import dataclass, field
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    Signal,
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    TerminateSuccessResult,
    ToolFailure,
    ToolCallOutcome,
)


# Type definitions
VirtualName = str
FilePath = str
FileMapping = Dict[VirtualName, FilePath]
ReadablePaths = List[VirtualName]
WritablePaths = List[VirtualName]
BlameTargets = List[str]
BlameTarget = str
Feedback = str
Blame = Tuple[BlameTarget, Feedback]
SearchResultLimit = int
DiffSizeLimit = int
# Template content keyed by the writable file's virtual name: the initial
# content the sandbox gives a writable file that does not exist on disk when
# the sandbox is configured (see sandbox-high.md / sandbox-low.md).
TemplateMapping = Dict[VirtualName, str]
# A verification callback runs a shell command and returns (success, output):
# success is True when the command exited 0. The sandbox uses the success flag
# to gate advance()'s termination (see sandbox-high.md / sandbox-low.md).
VerificationCallback = Optional[Callable[[], Tuple[bool, str]]]

@dataclass
class SandboxConfig:
    """Client-supplied configuration for the sandbox: file mappings, readable and writable paths, blame targets, limits, whether session-start reads are enabled, the guide and whether step mode is enabled, the templates (default: empty), and an optional verification callback."""
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    diff_size_limit: Optional[DiffSizeLimit] = None
    session_start_reads_enabled: bool = True
    guide: Optional[VirtualName] = None
    step_sections_enabled: bool = True
    templates: TemplateMapping = field(default_factory=dict)
    verification_callback: VerificationCallback = None

WriteOccurred = bool


class Sandbox(Protocol):
    """
    Interface for the LLS Sandbox.

    A component that provides secure file system operations and tool
    definitions for agent interactions. Tool results carry a supersedes flag
    per the Stubbing rules: reads of writable files, writes, edits, and
    verification supersede the earlier result for the same file or the
    verification command; reads of files that are not writable, searches, and
    termination results never supersede an earlier result. The consuming
    agent loop stubs the superseded result.

    Each tool operation produces a ToolCallOutcome: a sequence of one or
    more tool results (ToolResult or PresentedToolResult values) on success,
    or a Signal (Continue, a TerminateAgentWith* signal, or ToolFailure). A
    successful file write provides two results in order: the write
    confirmation and the injected read (the automatic re-read with the
    file's full numbered content, presented as a read the agent requested).
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return the list of tool definitions available in the current sandbox configuration.

        Tools are conditionally included based on configuration:
        - Always: read_file, write_file, edit_file, replace_lines,
          search_files, advance, fail
        - Conditional: blame (if blame targets non-empty)

        Returns:
            List of tool definitions following JSON schema format.

        Always succeeds.
        """
        ...

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        """
        Return the session-start reads: the plain reads of the read-only
        files, for rendering at the beginning of a run before the model's
        first turn.

        When session-start reads are enabled, returns a session-start read
        for every file that is readable but not writable and exists as a
        regular file on disk, sorted by virtual name; each is a
        PresentedToolResult pairing the read_file call with its plain read
        result (never superseding). When disabled, returns an empty list.
        Requesting the session-start reads changes no sandbox state.
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

    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome:
        """
        Create a new file with content, using the virtual name provided by the
        agent. Fails when the file already exists — modifying an existing file
        must go through edit_file or replace_lines.

        Args:
            file_path: Virtual path to the file
            content: Content to write (must be non-empty)

        Returns:
            A sequence of two results on success — the write confirmation (a
            ToolResult with supersedes set) and the injected read (a
            PresentedToolResult with the file's full numbered content) — or
            ToolFailure on policy or argument violations (including an
            existing file).

        Routing:
            supersedes is True (the write confirmation supersedes the earlier
            result for the file; the injected read supersedes the write
            confirmation and re-enables the line-numbered view). Sets
            write_occurred flag.

        Note:
            The write confirmation's content and note are a minimal structured
            status; no file content is echoed in it.
        """
        ...

    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str,
                  expect_multiple: bool = False) -> ToolCallOutcome:
        """
        Replace text in a file (content-based search and replace).

        Replaces exactly one occurrence of old_str with new_str; fails when
        old_str is absent or matches more than once unless expect_multiple=True,
        which replaces all occurrences.

        Args:
            file_path: Virtual path to the file
            old_str: Exact text to find (must be non-empty; at most 100
                characters — use replace_lines for larger changes)
            new_str: Replacement text (at most 100 characters)
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

    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
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

    def search_files(self, path: VirtualName, pattern: str,
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

    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome:
        """
        Signal the run's completion: verify the run and then signal
        successful termination, or provide feedback on a failing verification.

        Verifies the run automatically: computes the diff of each changed
        file vs. its content at run start (truncated when it exceeds the diff
        size limit) and runs the verification callback when one is
        configured; when no callback is configured, verification is treated
        as passed. On a failing verification, provides feedback (a ToolResult
        carrying the failure details and guidance, never the run's diff; not
        a tool failure) and the session continues. On a passing verification,
        signals successful termination.

        Args:
            changes: One entry per changed file — {"file": <virtual path>,
                "summary": one short sentence on what changed in the file, not
                how it was done}. Broadcast to reverse dependencies. Required
                when the run changed files; advance() without it fails with
                the list of changed files, the run's diff, and the required
                shape.

        Returns:
            On a failing verification: a ToolResult with the feedback (the
            session continues). On a passing verification:
            TerminateAgentWithSuccess carrying a TerminateSuccessResult (the
            implementation forms the result — no change, or change when the
            run changed files). Termination tools produce no ToolResult and
            never supersede an earlier result; a change message that is
            missing, malformed, or out of bounds signals a ToolFailure
            (never terminating).

        Routing:
            The failing-verification feedback sets supersedes: it supersedes
            the earlier non-stubbed verification result (an earlier advance
            feedback); advance's termination outcome never sets the flag.

        Note:
            The feedback's note reports only that verification failed, never
            the failure details, which live in the content.
        """
        ...

    def fail(self) -> ToolCallOutcome:
        """
        End the session in failure (agent failure).

        Returns:
            TerminateAgentWithFailure[T_tool]. A correctly-invoked fail is
            not a ToolFailure (ToolFailure signals a failed tool call).
            Termination tools produce no ToolResult and never supersede an earlier
            update.
        """
        ...

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        """
        Signal termination with blame: attribute the task's incompleteness to
        dependencies and provide feedback on how to correct their outputs.

        Args:
            blames: List of (target, feedback) pairs; each pair is one feedback
                    message to its target.

        Returns:
            TerminateAgentWithSuccess carrying a TerminateSuccessResult (the
            implementation forms a feedback result from the pairs) if all
            pairs are valid, or ToolFailure[T_tool] if any target is invalid.
            Termination tools produce no ToolResult and never supersede an earlier
            update.

        Preconditions:
            Blame targets must be configured and non-empty.
            Each pair's target must be in blame_targets.
        """
        ...

    def get_write_occurred(self) -> WriteOccurred:
        """
        Return whether the agent has modified the filesystem during the current run.

        Returns:
            True if any file write operation succeeded during the current run,
            False otherwise.
        """
        ...
