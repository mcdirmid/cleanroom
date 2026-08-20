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
    ContentId,
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
ReadSizeLimit = int
SearchResultLimit = int
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
    read_size_limit: ReadSizeLimit
    search_result_limit: SearchResultLimit
    diff_size_limit: Optional[int] = None
    verification_callback: VerificationCallback = None

WriteOccurred = bool


class Sandbox(Protocol):
    """
    Interface for the LLS Sandbox.

    A component that provides secure file system operations and tool definitions
    for agent interactions, with stubbing semantics for content management.

    Each tool operation produces a ToolCallOutcome: a ToolResult on success, or
    a Signal (Continue, a TerminateAgentWith* signal, or ToolFailure).
    """

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return the list of tool definitions available in the current sandbox configuration.

        Tools are conditionally included based on configuration:
        - Always: read_file, write_file, search_files, succeed, fail
        - Conditional: read_chunks, replace_chunks (if Python accessible)
        - Conditional: verify (if verification callback non-null)
        - Conditional: blame (if blame targets non-empty)

        Returns:
            List of tool definitions following JSON schema format.

        Always succeeds.
        """
        ...

    def read_file(self, file_path: VirtualName, start_line: int = 1,
                  end_line: Optional[int] = None,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        """
        Read lines from a file using the virtual name provided by the agent.

        Args:
            file_path: Virtual path to the file
            start_line: 1-indexed first line to read (default: 1)
            end_line: 1-indexed last line to read (default: end of file)
            include_line_numbers: Prefix each line with its line number
                (default: false; allowed only for writable files)

        Returns:
            ToolResult with the (optionally line-numbered) content on success,
            or ToolFailure on policy or parameter violations.

        Stubbing semantics:
            stub_previous is True if the read line range overlaps any previous
            non-stubbed read line range for the same file.

        Note:
            The result's note reports how many lines were read, the file's
            line count, how many remain, and the next start_line.
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

        Stubbing semantics:
            stub_previous is always True (unconditional stubbing).
            Sets write_occurred flag.

        Note:
            Returns a minimal structured result (success/message); no file
            content is echoed.
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
            old_str: Exact text to find (must be non-empty)
            new_str: Replacement text
            expect_multiple: If True, replace all occurrences of old_str

        Returns:
            ToolResult on success, or ToolFailure on policy or argument
            violations (including when the file does not exist).

        Stubbing semantics:
            A file write: stub_previous is always True (unconditional stubbing).
            Sets write_occurred flag.

        Note:
            Returns a minimal structured result (success/matches_found/message);
            no file content is echoed.
        """
        ...

    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                      new_content: str) -> ToolCallOutcome:
        """
        Replace, delete, or insert lines by 1-indexed line range.

        Replaces lines start_line..end_line (inclusive) with new_content;
        start_line > end_line inserts new_content before start_line; empty
        new_content deletes the range.

        Args:
            file_path: Virtual path to the file
            start_line: 1-indexed start line (inclusive), 1..len(file)+1
            end_line: 1-indexed end line (inclusive), 0..len(file)
            new_content: Replacement content

        Returns:
            ToolResult on success, or ToolFailure on policy or argument
            violations (including when the file does not exist or the range is
            not visible in context).

        Stubbing semantics:
            A file write: stub_previous is always True (unconditional stubbing).
            Sets write_occurred flag.

        Note:
            Returns a minimal structured result (success/lines_replaced or
            lines_deleted or inserted_before/message); no file content is
            echoed.
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
            limit: Maximum matches to return (must not exceed the search result
                limit); if omitted, returns all matches, which fails when more
                than the search result limit exist.

        Returns:
            ToolResult with search results in content on success, or ToolFailure
            on policy, parameter, or pattern violations.

        Stubbing semantics:
            stub_previous is True if the same path, pattern, offset, and limit
            were previously searched.

        Note:
            The result's note reports how many matches remain and the offset
            to continue from.
        """
        ...

    def read_chunks(self, file_path: VirtualName,
                    chunk_indices: Optional[List[int]] = None,
                    include_adjacent: bool = False) -> ToolCallOutcome:
        """
        Read semantic chunks from a Python file.

        Args:
            file_path: Virtual path to the Python file
            chunk_indices: List of chunk indices to read (default: all)
            include_adjacent: Include neighboring chunks for context

        Returns:
            ToolResult with chunk content in content on success, or ToolFailure
            on policy or parameter violations.

        Stubbing semantics:
            stub_previous is True if requested chunk indices overlap with
            previous non-stubbed chunk reads for the same file.

        Preconditions:
            Python files must be accessible.
            file_path must be a Python file.
        """
        ...

    def replace_chunks(self, file_path: VirtualName, replacements: List[Dict],
                       encoding: Optional[str] = None) -> ToolCallOutcome:
        """
        Replace multiple chunks in a Python file atomically.

        Args:
            file_path: Virtual path to the Python file
            replacements: List of dicts with 'index' and 'new_content' keys
            encoding: Optional file encoding

        Returns:
            ToolResult on success, or ToolFailure on policy or argument violations.

        Stubbing semantics:
            stub_previous is always True (unconditional stubbing).
            All replacements apply atomically.
            Sets write_occurred flag.

        Note:
            Returns a minimal structured result (success/chunks_replaced/message);
            no file content is echoed.

        Preconditions:
            Python files must be accessible.
            file_path must be a Python file.
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

        Stubbing semantics:
            stub_previous is always True (unconditional stubbing).

        Note:
            The outcome records whether the callback succeeded (exit 0);
            succeed() is gated on this state when a callback is configured.
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
            the run modified the workspace). content_id is None (never stubbed).

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
            No stubbing occurs (termination tools do not produce ToolResult).
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
            content_id is None (never stubbed).

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
