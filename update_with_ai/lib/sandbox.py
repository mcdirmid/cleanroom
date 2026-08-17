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
VerificationCallback = Optional[Callable[[], str]]

@dataclass
class SandboxConfig:
    """Client-supplied configuration for the sandbox: file mappings, readable and writable paths, blame targets, limits, and an optional verification callback."""
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    read_size_limit: ReadSizeLimit
    search_result_limit: SearchResultLimit
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

    def read_file(self, file_path: VirtualName, offset: Optional[int] = None,
                  limit: Optional[int] = None) -> ToolCallOutcome:
        """
        Read content from a file using the virtual name provided by the agent.

        Args:
            file_path: Virtual path to the file
            offset: Starting position (default: 0)
            limit: Maximum bytes to read (default: read_size_limit)

        Returns:
            ToolResult with content on success, or ToolFailure on policy or
            parameter violations.

        Stubbing semantics:
            stub_previous is True if the read region overlaps with any previous
            non-stubbed read region for the same file.
        """
        ...

    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome:
        """
        Write content to a file using the virtual name provided by the agent.

        Args:
            file_path: Virtual path to the file
            content: Content to write (overwrites existing file)

        Returns:
            ToolResult on success, or ToolFailure on policy or argument violations.

        Stubbing semantics:
            stub_previous is always True (unconditional stubbing).
            Sets write_occurred flag.
        """
        ...

    def search_files(self, path: VirtualName, pattern: str) -> ToolCallOutcome:
        """
        Search for a pattern in files using the virtual path provided by the agent.

        Args:
            path: Virtual path to search (recursive)
            pattern: Regex pattern to search for

        Returns:
            ToolResult with search results in content on success, or ToolFailure
            on policy or pattern violations.

        Stubbing semantics:
            stub_previous is True if the same path and pattern were previously searched.
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

        Preconditions:
            Python files must be accessible.
            file_path must be a Python file.
        """
        ...

    def verify(self) -> ToolCallOutcome:
        """
        Run the verification callback.

        Returns:
            ToolResult with verification result in content, or ToolFailure if
            the callback fails.

        Stubbing semantics:
            stub_previous is always True (unconditional stubbing).

        Preconditions:
            Verification callback must be non-null.
        """
        ...

    def succeed(self) -> ToolCallOutcome:
        """
        Signal successful termination.

        Returns:
            TerminateAgentWithSuccess carrying a TerminateSuccessResult
            (the implementation forms the result — no change, or change if
            the run modified the workspace). content_id is None (never stubbed).
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
