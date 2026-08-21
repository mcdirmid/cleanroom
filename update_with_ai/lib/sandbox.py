# lib/sandbox.py
"""
Interface definitions for the LLS Sandbox.
"""

from typing import Callable, Dict, List, Optional, Protocol, Tuple
from dataclasses import dataclass
from .tool_provider import (
    ToolDefinition,
    ToolResult,
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
# A verification callback runs a shell command and returns (success, output):
# success is True when the command exited 0. The sandbox uses the success flag
# to gate succeed() (see sandbox-high.md / sandbox-low.md).
VerificationCallback = Optional[Callable[[], Tuple[bool, str]]]

@dataclass
class SandboxConfig:
    """Client-supplied configuration for the sandbox: file mappings, readable and writable paths, blame targets, limits, and an optional verification callback."""
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    diff_size_limit: Optional[DiffSizeLimit] = None
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

    Each tool operation produces a ToolCallOutcome: a ToolResult on success,
    or a Signal (Continue, a TerminateAgentWith* signal, or ToolFailure).
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return the list of tool definitions available in the current sandbox configuration.

        Tools are conditionally included based on configuration:
        - Always: read_file, write_file, edit_file, replace_lines,
          search_files, verify, succeed, fail
        - Conditional: blame (if blame targets non-empty)

        Returns:
            List of tool definitions following JSON schema format.

        Always succeeds.
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
            ToolResult with the (optionally line-numbered) content on success,
            or ToolFailure on policy or parameter violations.

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
            ToolResult on success, or ToolFailure on policy or argument
            violations (including an existing file).

        Routing:
            supersedes is True (the write supersedes the earlier result for
            the file). Sets write_occurred flag.

        Note:
            The content and note are a minimal structured status; no file
            content is echoed in the conversation.
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
            ToolResult on success, or ToolFailure on policy or argument
            violations (including when the file does not exist or either
            string exceeds the length limit).

        Routing:
            A file write: supersedes is True (the edit supersedes the earlier
            result for the file). Sets write_occurred flag.

        Note:
            The content and note are a minimal structured status; no file
            content is echoed in the conversation.
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
            ToolResult on success, or ToolFailure on policy or argument
            violations (including when the file does not exist or the file's
            current view is not line-numbered).

        Routing:
            A file write: supersedes is True (the edit supersedes the earlier
            result for the file). Sets write_occurred flag.

        Note:
            The content and note are a minimal structured status; no file
            content is echoed in the conversation.
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

    def verify(self) -> ToolCallOutcome:
        """
        Report the run's file changes and run the verification callback when configured.

        Always reports the diff of each changed file vs. its content at run
        start, truncated when it exceeds the diff size limit. When a
        verification callback is configured, its output and exit code are
        additionally reported (the diff is reported either way).

        Returns:
            ToolResult on success, or ToolFailure on callback error.

        Routing:
            supersedes is True (the verification result supersedes the earlier
            non-stubbed verification result).

        Note:
            The note reports only whether verification succeeded or failed (or
            that no verification tool is configured), never the failure
            details, which live in the content. The outcome records whether
            the callback succeeded (exit 0); succeed() is gated on this state
            when a callback is configured.
        """
        ...

    def succeed(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome:
        """
        Signal successful termination, carrying the agent's change summary.

        Args:
            changes: One entry per changed file — {"file": <virtual path>,
                "summary": one short sentence on what changed in the file, not
                how it was done}. Broadcast to reverse dependencies. Required
                when the run changed files; succeed() without it fails with
                the list of changed files and the required shape.

        Returns:
            TerminateAgentWithSuccess carrying a TerminateSuccessResult
            (the implementation forms the result — no change, or change if
            the run modified the workspace). Termination tools produce no
            ToolResult and never supersede an earlier result.

        Preconditions:
            When a verification callback is configured, verify() must have
            been called and its last outcome must have succeeded; otherwise
            this signals a ToolFailure (never terminating) advising the agent
            to verify, fail, or blame. When the run changed files, every
            changed file must appear in `changes` with a non-empty, bounded
            summary; violations signal a ToolFailure (never terminating).
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
