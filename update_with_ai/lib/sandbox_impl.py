"""
Implementation of the LLS Sandbox interface.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .sandbox import (
    VirtualName, Blame, SandboxConfig, WriteOccurred, Sandbox
)
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    ToolCallOutcome,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
)
from .dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult


class SandboxImpl(Sandbox):
    """
    Implementation of the LLS Sandbox interface.

    Provides secure file system operations, policy enforcement, and per-run
    state (write-occurred flag, per-file view modes, pre-write snapshots).
    No stubbing state is maintained: the supersedes flag is set statically
    per operation type and the sandbox tracks nothing about prior results;
    the agent loop applies the stubbing.
    """

    def __init__(self, config: SandboxConfig):
        """
        Initialize the sandbox with configuration.

        Args:
            config: Configuration object containing file mappings, policies, etc.
        """
        self.config = config
        self.write_occurred: WriteOccurred = False

        # Per-run change-summary rejection counters (soft/hard length bounds):
        # a summary over the soft bound is rejected up to a grace count, then
        # accepted within the hard bound; a summary over the hard bound after
        # its grace turns succeed() into a hard failure. Reset on any accepted
        # summary; per-run state only (fresh sandbox per run).
        self._summary_soft_rejections: int = 0
        self._summary_hard_rejections: int = 0

        # Precompute real->virtual path map so error messages can present
        # virtual names to the agent instead of absolute on-disk paths.
        self._real_to_virtual: Dict[str, str] = {}
        for virtual, real in self.config.file_mappings.items():
            if real:
                self._real_to_virtual.setdefault(real, virtual)
        # Longest paths first so a path that prefixes another is replaced
        # correctly (e.g. /pkg/foo.txt before /pkg/foo.txt.bak).
        self._real_paths_sorted: List[str] = sorted(
            self._real_to_virtual.keys(), key=len, reverse=True
        )

        # Per-run view mode per writable file: False = plain view, True =
        # line-numbered view. Set by read_file; a write resets the view to
        # plain (the line numbers are invalidated).
        self._file_views: Dict[VirtualName, bool] = {}

        # Verify gate state: None = verify() not yet called; True/False = the
        # last verify() outcome. When a verification callback is configured,
        # succeed() requires this to be True (see sandbox-high.md).
        self._verify_passed: Optional[bool] = None

        # Files written by the run (virtual names, deduped, in write order).
        # succeed() reports these when called without a change message.
        self._changed_files: List[str] = []

        # Pre-write content snapshots: each file's content at run start (before
        # this run's first write of that file), used by verify()'s diff report
        # when no verification callback is configured.
        self._pre_write_snapshots: Dict[VirtualName, Optional[str]] = {}

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return tool definitions based on configuration."""
        definitions = []

        # Always available
        definitions.extend([
            self._create_tool_definition(
                "read_file",
                "Read a file's ENTIRE content (files are small; reads are never paginated). "
                "Reading a writable file makes its content the file's current content in the "
                "conversation (an earlier read of the same file is replaced by a stub). "
                "Line numbers are metadata, not file content: reading "
                "a writable file that already exists REQUIRES include_line_numbers=True (a "
                "plain read is rejected); line numbers also serve replace_lines edits.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "include_line_numbers": {"type": "boolean", "description": "Prefix each line with its line number; REQUIRED when reading a writable file that already exists; line numbers serve replace_lines edits and are allowed only for writable files (default: false)", "default": False}
                }
            ),
            self._create_tool_definition(
                "write_file",
                "Create a NEW file with the given content. Fails if the file already exists — use edit_file (content-based) or replace_lines (line-based) to modify existing files. Empty content is rejected. After a write the file's earlier content is no longer visible until you read the file again.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                }
            ),
            self._create_tool_definition(
                "edit_file",
                "Replace text in a file (content-based search and replace): replaces exactly one occurrence of old_str with new_str; fails when old_str is absent or matches more than once unless expect_multiple=True (then replaces all occurrences). old_str and new_str are limited to 100 characters each — use replace_lines for larger changes (requires the line-numbered view). After an edit the file's earlier content is no longer visible until you read the file again.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "old_str": {"type": "string", "description": "Exact text to find"},
                    "new_str": {"type": "string", "description": "Replacement text"},
                    "expect_multiple": {"type": "boolean", "description": "Allow multiple matches and replace all of them", "default": False}
                }
            ),
            self._create_tool_definition(
                "replace_lines",
                "Replace, delete, or insert lines by 1-indexed line range: replaces lines start_line..end_line with new_str; start_line > end_line inserts new_str before start_line; empty new_str deletes the range. Requires the line-numbered view: call read_file(file_path, include_line_numbers=true) first. Line numbers are 1-indexed and current only in the most recent read.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "start_line": {"type": "integer", "description": "1-indexed start line (inclusive); between 1 and len(file)+1"},
                    "end_line": {"type": "integer", "description": "1-indexed end line (inclusive); between 0 and len(file)"},
                    "new_str": {"type": "string", "description": "Replacement content; empty deletes the range"}
                },
                required=["file_path", "start_line", "end_line", "new_str"],
            ),
            self._create_tool_definition(
                "search_files",
                "Search for a pattern in files. Renders matches only for read-only files; matches in writable files are counted in the note but never shown (their content is not supported and would go stale).",
                {
                    "path": {"type": "string", "description": "Virtual path to search"},
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "offset": {"type": "integer", "description": "Match offset to start from (default: 0)", "default": 0},
                    "limit": {"type": "integer", "description": f"Maximum rendered matches to return (1..{self.config.search_result_limit}); if omitted, returns all rendered matches, which fails if more than {self.config.search_result_limit} exist. Each result includes a note reporting how many rendered matches remain and the offset to continue from."}
                }
            ),
            self._create_tool_definition(
                "succeed",
                "Signal successful termination",
                {
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string", "description": "A file changed by this run"},
                                "summary": {"type": "string", "description": "One short sentence naming the parts of the file that changed, so the next agent knows what to pay attention to when updating further artifacts; not the task performed, not how it was done; aim for at most %d characters (hard limit %d)" % (SandboxImpl.SOFT_CHANGE_SUMMARY_LENGTH, SandboxImpl.HARD_CHANGE_SUMMARY_LENGTH)}
                            },
                            "required": ["file", "summary"],
                            "additionalProperties": False
                        },
                        "description": "Required when the run changed files: one entry per changed file, each a short sentence naming the parts of that file that changed, so the next agent knows what to pay attention to when updating further artifacts"
                    }
                },
            ),
            self._create_tool_definition(
                "fail",
                "Signal failed termination",
                {}
            )
        ])

        # Always: verify — reports the diff of the run's changes; runs the
        # configured verification callback when one exists.
        definitions.append(
            self._create_tool_definition(
                "verify",
                "Report the diff of the run's file changes vs. their state at run start. When a verification callback is configured, run it and report whether the output passed. When the run changed files, succeed() requires verify() to have been called. Re-running verify replaces the earlier verification report in the conversation.",
                {}
            )
        )

        # Conditional: blame
        if self.config.blame_targets:
            definitions.append(
                self._create_tool_definition(
                    "blame",
                    "Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs",
                    {
                        "blames": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target": {"type": "string", "description": "Target to blame (a dependency)"},
                                    "feedback": {"type": "string", "description": "Feedback on how to correct the target's output"}
                                },
                                "required": ["target", "feedback"],
                                "additionalProperties": False
                            },
                            "description": "Blame pairs (target, feedback), each delivered as a feedback message to its target"
                        }
                    }
                )
            )

        return definitions

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        """Read a file's entire content, optionally in the line-numbered view."""
        # Check if path exists in mappings first
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can read: {self._readable_list()}"
            )

        # Then check readability
        if file_path not in self.config.readable_paths:
            return self._error_response(
                f"File path '{file_path}' is not readable. "
                f"Files you can read: {self._readable_list()}"
            )

        # Line numbers exist to serve replace_lines edits, which require a
        # writable file; a line-numbered read of a read-only file is an
        # argument error.
        if include_line_numbers and file_path not in self.config.writable_paths:
            return self._error_response(
                f"include_line_numbers is allowed only for writable files; "
                f"'{file_path}' is not writable"
            )

        # Resolve path
        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")
        if not os.path.isfile(real_path):
            return self._error_response(f"Path '{real_path}' is not a file")

        # A writable file that already exists on disk is only readable in the
        # line-numbered view: the agent must buy into line numbers (they are
        # metadata, not file content), which also guarantees the numbered
        # view that replace_lines requires. A plain read fails with guidance.
        if (
            file_path in self.config.writable_paths
            and not include_line_numbers
        ):
            return self._error_response(
                f"Reading the writable file '{file_path}' requires "
                f"include_line_numbers=True: line numbers are metadata, not "
                f"file content. Call read_file('{file_path}', "
                f"include_line_numbers=True) to see them."
            )

        # Read the entire file (reads are not paginated and are not bounded by
        # a size limit).
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")

        # A read sets the file's view for the run (plain or line-numbered);
        # the view persists across writes and gates replace_lines.
        self._file_views[file_path] = include_line_numbers

        content = self._render_lines(lines, include_line_numbers)
        n = len(lines)
        view = "line-numbered" if include_line_numbers else "plain"
        note = f"Read {n} lines ({view})"

        # Routing per the sandbox contract's Stubbing rules: a read of a
        # writable file supersedes the earlier result for that file (the
        # agent loop stubs it); a read of a file that is not writable never
        # supersedes an earlier result — reads of readable files are not
        # stubbed.
        if file_path in self.config.writable_paths:
            return ToolResult(
                content=content,
                supersedes=True,
                note=note,
            )
        return ToolResult(content=content, supersedes=False, note=note)

    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome:
        """Create a new file; its result supersedes the file's earlier results."""
        # Check if path exists in mappings first
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can write: {self._writable_list()}"
            )

        # Then check writability
        if file_path not in self.config.writable_paths:
            return self._error_response(
                f"File path '{file_path}' is not writable. "
                f"Files you can write: {self._writable_list()}"
            )

        if not content:
            return self._error_response("Content must be non-empty")

        # Resolve path
        real_path = self.config.file_mappings[file_path]

        # write_file creates new files only; modifying an existing file must go
        # through the editing tools, which preserve the surrounding content.
        if os.path.exists(real_path):
            return self._error_response(
                f"File '{file_path}' already exists; write_file is only for "
                f"creating new files. Use edit_file (content-based) or "
                f"replace_lines (line-based) to modify it."
            )

        # Ensure directory exists (skip for bare filenames with no directory)
        parent_dir = os.path.dirname(real_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Snapshot pre-write content (first write of the run only) for the
        # no-callback verify diff.
        self._snapshot(file_path, real_path)

        # Write file
        try:
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")

        # Update state
        self.write_occurred = True
        if file_path not in self._changed_files:
            self._changed_files.append(file_path)

        # The result is minimal: a structured success message, never a
        # file-content echo. supersedes is set so the agent loop stubs the
        # file's earlier results (the file's content is not visible until the
        # agent reads the file again).
        n = len(content.splitlines())
        return ToolResult(
            content=f"Created {file_path}; {n} lines",
            supersedes=True,
        )

    def _snapshot(self, file_path: VirtualName, real_path: str) -> None:
        """Capture a file's pre-write content on the run's first write of it."""
        if file_path in self._pre_write_snapshots:
            return
        try:
            with open(real_path, "r", encoding="utf-8") as f:
                self._pre_write_snapshots[file_path] = f.read()
        except FileNotFoundError:
            self._pre_write_snapshots[file_path] = ""
        except Exception:
            self._pre_write_snapshots[file_path] = None

    @staticmethod
    def _render_lines(lines: List[str], numbered: bool) -> str:
        """Render lines plain or in the line-numbered view ("N \u2502 line")."""
        if numbered:
            width = len(str(len(lines)))
            return "\n".join(
                f"{i:>{width}} \u2502 {line}" for i, line in enumerate(lines, start=1)
            )
        return "\n".join(lines)

    def _apply_write(self, file_path: VirtualName, real_path: str, new_content: str,
                     status: str) -> ToolCallOutcome:
        """Snapshot pre-write content, write the file, and update per-run state.

        Shared by the editing tools (edit_file, replace_lines): a successful
        edit is a file write — it sets the write-occurred flag and records the
        changed file. The ToolResult's content is the operation's status (a
        structured success message), never a file-content echo; supersedes is
        set so the agent loop stubs the file's earlier results (the file's
        current content is not visible until the agent reads the file again).
        A write invalidates the line-numbered view: the file's view resets to
        plain, so the agent must re-read with include_line_numbers=True
        before the next line-range edit (replace_lines) — line numbers are
        stale after the write.
        """
        self._snapshot(file_path, real_path)
        # The write changes the line structure: reset the view to plain so
        # replace_lines re-validates against a fresh numbered read.
        self._file_views[file_path] = False

        try:
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")

        self.write_occurred = True
        if file_path not in self._changed_files:
            self._changed_files.append(file_path)

        return ToolResult(
            content=status,
            supersedes=True,
        )

    @staticmethod
    def _split_lines(content: str) -> Tuple[List[str], bool]:
        """Split content into lines without terminators; report trailing newline."""
        if content == "":
            return [], False
        trailing = content.endswith('\n')
        lines = content.split('\n')
        if trailing and lines and lines[-1] == '':
            lines = lines[:-1]
        return lines, trailing

    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str,
                  expect_multiple: bool = False) -> ToolCallOutcome:
        """Replace text in a file (content-based search and replace)."""
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can write: {self._writable_list()}"
            )
        if file_path not in self.config.writable_paths:
            return self._error_response(
                f"File path '{file_path}' is not writable. "
                f"Files you can write: {self._writable_list()}"
            )
        if not old_str:
            return self._error_response("old_str must be non-empty")
        if old_str == new_str:
            return self._error_response(
                "old_str and new_str are identical; the edit would change "
                "nothing — fix the old_str or new_str and retry"
            )
        if len(old_str) > self.MAX_EDIT_LENGTH or len(new_str) > self.MAX_EDIT_LENGTH:
            return self._error_response(
                f"edit_file supports only short old_str and new_str (at most "
                f"{self.MAX_EDIT_LENGTH} characters each; got old_str="
                f"{len(old_str)}, new_str={len(new_str)}). Use replace_lines "
                f"for larger edits (requires the line-numbered view: "
                f"read_file(file_path, include_line_numbers=True))."
            )

        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(
                f"File '{file_path}' does not exist; use write_file to create it"
            )
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")

        count = content.count(old_str)
        if count == 0:
            return self._error_response(f"old_str not found in '{file_path}'")
        if count > 1 and not expect_multiple:
            return self._error_response(
                f"old_str matches {count} times in '{file_path}'; "
                "pass expect_multiple=True to replace all, or narrow old_str"
            )
        if expect_multiple:
            new_content = content.replace(old_str, new_str)
            message = f"Replaced {count} occurrences in {file_path}"
        else:
            new_content = content.replace(old_str, new_str, 1)
            message = f"Replaced 1 occurrence in {file_path}"
        return self._apply_write(file_path, real_path, new_content, message)

    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                      new_str: str) -> ToolCallOutcome:
        """Replace, delete, or insert lines by 1-indexed line range."""
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can write: {self._writable_list()}"
            )
        if file_path not in self.config.writable_paths:
            return self._error_response(
                f"File path '{file_path}' is not writable. "
                f"Files you can write: {self._writable_list()}"
            )
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            return self._error_response("start_line and end_line must be integers")

        # replace_lines operates on 1-indexed line numbers: the file's current
        # view must be line-numbered (the agent enabled line numbers by reading
        # with include_line_numbers=True). A write resets the view to plain —
        # the line numbers are invalidated until the next numbered read — so
        # a line edit after a write fails with the reminder below. The failure
        # supersedes nothing and removes nothing (per the sandbox contract).
        if not self._file_views.get(file_path, False):
            return ToolFailure(
                value=(
                    f"replace_lines requires the line-numbered view: call "
                    f"read_file('{file_path}', include_line_numbers=True) to "
                    f"re-enable it (a write invalidated the line numbers); the "
                    f"file's current view is plain"
                ),
            )

        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(
                f"File '{file_path}' does not exist; use write_file to create it"
            )
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")

        lines, trailing = self._split_lines(content)
        n = len(lines)
        if not (1 <= start_line <= n + 1):
            return self._error_response(
                f"start_line must be between 1 and {n + 1} (file has {n} lines)"
            )
        if not (0 <= end_line <= n):
            return self._error_response(
                f"end_line must be between 0 and {n} (file has {n} lines)"
            )

        insertion = [new_str] if new_str else []
        if start_line > end_line:
            new_lines = lines[:start_line - 1] + insertion + lines[start_line - 1:]
            message = f"Inserted content before line {start_line} in {file_path}"
        else:
            new_lines = lines[:start_line - 1] + insertion + lines[end_line:]
            removed = end_line - start_line + 1
            if new_str:
                message = f"Replaced lines {start_line}-{end_line} in {file_path}"
            else:
                message = f"Deleted lines {start_line}-{end_line} in {file_path}"

        if new_lines:
            content = '\n'.join(new_lines)
            if trailing:
                content += '\n'
        else:
            content = ""
        return self._apply_write(file_path, real_path, content, message)

    def search_files(self, path: VirtualName, pattern: str,
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        """Search for a pattern in files; render matches only for read-only files."""
        # Check if path exists in mappings first
        if path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{path}' not found in mappings. "
                f"Files you can read: {self._readable_list()}"
            )

        # Then check readability
        if path not in self.config.readable_paths:
            return self._error_response(
                f"Path '{path}' is not readable. "
                f"Files you can read: {self._readable_list()}"
            )

        # Validate parameters
        if offset is not None and offset < 0:
            return self._error_response("Offset must be non-negative")
        if limit is not None and limit <= 0:
            return self._error_response("Limit must be positive")
        if limit is not None and limit > self.config.search_result_limit:
            return self._error_response(
                f"Limit {limit} exceeds the search result limit "
                f"({self.config.search_result_limit}); specify a smaller limit"
            )

        try:
            re.compile(pattern)
        except re.error as e:
            return self._error_response(f"Invalid regex pattern: {str(e)}")

        # Resolve path
        real_path = self.config.file_mappings[path]
        if not os.path.exists(real_path):
            return self._error_response(f"Path '{real_path}' does not exist")

        if offset is None:
            offset = 0

        # Perform search; matches are (virtual_name, text) pairs so matches in
        # writable files can be suppressed (their content would go stale).
        try:
            matches = self._perform_search(real_path, pattern)
        except Exception as e:
            return self._error_response(f"Error searching: {str(e)}")

        rendered: List[str] = []
        suppressed = 0
        for virtual, text in matches:
            if virtual in self.config.writable_paths:
                suppressed += 1
            else:
                rendered.append(text)

        total = len(rendered)
        if limit is None:
            # Omitted limit means all rendered matches; allowed only within the
            # search result limit, otherwise the tool fails and the agent
            # must page through results with offset/limit.
            if total > self.config.search_result_limit:
                return self._error_response(
                    f"Search returned {total} rendered matches, exceeding the "
                    f"search result limit ({self.config.search_result_limit}); "
                    f"specify offset/limit to page through results"
                )
            page = rendered
        else:
            page = rendered[offset:offset + limit]
        content = "\n".join(page)

        page_end = offset + len(page)
        remaining = max(total - page_end, 0)
        note = (
            f"{total} matches total; {remaining} more after this page; "
            f"continue with offset={page_end}"
        )
        if suppressed:
            note += f"; {suppressed} match(es) in writable files not shown"

        # Search results never supersede an earlier result (matches in
        # writable files are never rendered, so they never become stale).
        return ToolResult(content=content, supersedes=False, note=note)

    def verify(self) -> ToolCallOutcome:
        """Report the run's changes (diff vs. run start); run the verification callback when configured."""
        diff = self._diff_report()
        if self.config.verification_callback is None:
            output = (
                diff
                + "\nNo verification tool is configured to validate the output; "
                "succeed() may now be called (verify has been called)."
            )
            self._verify_passed = True
            return ToolResult(
                content=output,
                supersedes=True,
                note="No verification tool configured.",
            )

        try:
            success, output = self.config.verification_callback()
        except Exception as e:
            return ToolFailure[str](f"Verification error: {str(e)}")

        self._verify_passed = success
        content = diff if not output else diff + "\n\n" + output
        if success:
            content += "\nVerification passed; succeed() may now be called."
            note = "Verification passed."
        else:
            content += (
                "\nVerification failed; fix the reported issues by changing "
                "files (edit_file/replace_lines/write_file) and then call "
                "verify() again, or call blame() or fail() to end the run."
            )
            note = "Verification failed."
        # The verification result supersedes the earlier non-stubbed
        # verification result (the agent loop stubs it). The note reports
        # only the status (pinned in specs/sandbox_impl-low.md); the failure
        # details live in the content, never in the note.
        return ToolResult(
            content=content,
            supersedes=True,
            note=note,
        )

    def _diff_report(self) -> str:
        """Diff of each changed file vs. its content at run start, truncated.

        The report is bounded by the diff size limit (config; default 1000
        chars): a larger diff is cut to its first `limit` characters, followed
        by a footer stating the truncated size and the full change counts.
        """
        import difflib

        sections: List[str] = []
        for file_path in self._changed_files:
            old = self._pre_write_snapshots.get(file_path)
            real_path = self.config.file_mappings[file_path]
            try:
                with open(real_path, "r", encoding="utf-8") as f:
                    current = f.read()
            except Exception:
                current = None
            if old is None or current is None:
                sections.append(
                    f"### {file_path}: diff unavailable (no baseline for this run)"
                )
                continue
            diff = difflib.unified_diff(
                old.splitlines(),
                current.splitlines(),
                fromfile=f"{file_path} (at run start)",
                tofile=f"{file_path} (now)",
            )
            sections.append(f"### diff for {file_path}\n" + "\n".join(diff))
        if not sections:
            return "No files were changed in this run."

        full = "\n\n".join(sections)
        limit = self.config.diff_size_limit if self.config.diff_size_limit is not None else 1000
        if len(full) <= limit:
            return full
        lines = full.splitlines()
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        footer = (
            f"\n... diff truncated: showing {limit} of {len(full)} chars "
            f"({len(self._changed_files)} file(s), +{additions}/-{deletions} lines). "
            "Raise diff_size_limit to see it in full."
        )
        return full[:limit] + footer

    # Change summaries must stay bounded so the change messages broadcast to
    # dependents stay concise. A soft bound nudges one short sentence; a hard
    # bound caps the message. succeed() rejects a summary over the soft bound
    # (with shortening guidance) up to a grace count, then accepts it when
    # within the hard bound; a summary still over the hard bound after its
    # grace count turns succeed() into a hard failure.
    SOFT_CHANGE_SUMMARY_LENGTH = 200
    HARD_CHANGE_SUMMARY_LENGTH = 500
    SUMMARY_LENGTH_GRACE = 4

    # edit_file supports only short search/replace strings: a whole-file swap
    # must go through replace_lines (which requires the line-numbered view).
    MAX_EDIT_LENGTH = 100

    def succeed(self, changes: Optional[List[Dict[str, str]]] = None) -> ToolCallOutcome:
        """Signal successful termination, carrying the agent's change summary.

        Gated on verification first: when a verification callback is
        configured, succeed() may only be called after verify() has succeeded
        (exit 0). Then, when the run changed files, `changes` must list one
        entry per changed file — {file, summary} — each summary a single
        short sentence on what changed (not how). A file counts as changed
        only when its current content differs from its run-start snapshot; a
        run whose writes all net out to no change reports no change.
        """
        changes = changes or []
        if self.config.verification_callback is not None and self._verify_passed is not True:
            if self._verify_passed is None:
                return ToolFailure[str](
                    "Cannot succeed: verify() has not been called. Call "
                    "verify() and fix any reported issues before succeeding, "
                    "or call fail() or blame() to end the run."
                )
            return ToolFailure[str](
                "Cannot succeed: the last verify() call failed. Fix the "
                "reported issues and call verify() again before succeeding, "
                "or call fail() or blame() to end the run."
            )
        if self._changed_files and self._verify_passed is None:
            return ToolFailure[str](
                "Cannot succeed: verify() has not been called. Call verify() "
                "to report the diff of the run's changes before succeeding, "
                "or call fail() or blame() to end the run."
            )
        # A write may net out to no change (e.g., an edit undone by a later
        # edit): only files whose current content differs from their run-start
        # snapshot count as changed for succeed()'s requirements and result.
        # A claimed change for a net-unchanged file is fabricated and rejected.
        effectively_changed: List[str] = []
        for file_path in self._changed_files:
            real_path = self.config.file_mappings[file_path]
            try:
                with open(real_path, "r", encoding="utf-8") as f:
                    current = f.read()
            except Exception:
                current = None
            if current != self._pre_write_snapshots.get(file_path):
                effectively_changed.append(file_path)

        if not effectively_changed:
            if changes:
                return ToolFailure[str](
                    "Cannot succeed: the run wrote files but net-changed "
                    "nothing — each file's current content equals its content "
                    "at run start. Call succeed() with no changes to report "
                    "no change."
                )
            return TerminateAgentWithSuccess(NoChangeResult())

        if not changes:
            failure_message = (
                "Cannot succeed: the run changed files ({changed}). Call "
                "succeed(changes=[{{file, summary}}, ...]) with one entry "
                "per changed file — each summary one short sentence on "
                "what changed in that file (not how it was done) — so the "
                "next agent knows what changed, or call fail() or blame() "
                "to end the run."
            ).format(changed=", ".join(effectively_changed))
            return ToolFailure[str](failure_message)

        changed_set = set(effectively_changed)
        mentioned: set = set()
        messages: List[str] = []
        for entry in changes:
            file_name = (entry or {}).get("file")
            summary = (entry or {}).get("summary")
            if not file_name or not summary or not summary.strip():
                return ToolFailure[str](
                    "Cannot succeed: each change entry must have a "
                    "non-empty 'file' and a non-empty one-sentence "
                    "'summary' of what changed in that file."
                )
            if file_name not in changed_set:
                unknown_message = (
                    "Cannot succeed: '{file}' was not changed by this run; "
                    "report only the changed files ({changed})."
                ).format(file=file_name, changed=", ".join(effectively_changed))
                return ToolFailure[str](unknown_message)
            summary_text = summary.strip()
            summary_length = len(summary_text)
            if summary_length > self.HARD_CHANGE_SUMMARY_LENGTH:
                if self._summary_hard_rejections >= self.SUMMARY_LENGTH_GRACE:
                    # The hard-limit grace is exhausted: succeed() turns into
                    # a hard failure ending the run.
                    return TerminateAgentWithFailure[str](
                        f"Task failed: the change summary for '{file_name}' "
                        f"could not be shortened to the hard limit "
                        f"({self.HARD_CHANGE_SUMMARY_LENGTH} characters) "
                        f"after repeated attempts."
                    )
                self._summary_hard_rejections += 1
                return ToolFailure[str](
                    "Cannot succeed: the summary for '{file}' is {length} "
                    "characters (max {max} — the hard limit). Shorten it to "
                    "at most {max} characters: name the parts of the file "
                    "that changed in one short sentence, dropping how it was "
                    "done, then call succeed() again with the shortened "
                    "summary.".format(
                        file=file_name,
                        length=summary_length,
                        max=self.HARD_CHANGE_SUMMARY_LENGTH,
                    )
                )
            if summary_length > self.SOFT_CHANGE_SUMMARY_LENGTH:
                if self._summary_soft_rejections < self.SUMMARY_LENGTH_GRACE:
                    self._summary_soft_rejections += 1
                    return ToolFailure[str](
                        "Cannot succeed: the summary for '{file}' is {length} "
                        "characters (aim for at most {soft}). Shorten it to "
                        "at most {soft} characters: name the parts of the "
                        "file that changed in one short sentence, so the next "
                        "agent knows what to pay attention to when updating "
                        "further artifacts, dropping how it was done, then "
                        "call succeed() again with the shortened summary."
                        .format(
                            file=file_name,
                            length=summary_length,
                            soft=self.SOFT_CHANGE_SUMMARY_LENGTH,
                        )
                    )
                # The soft-limit grace is exhausted: accept the summary when
                # it is within the hard bound.
            # An accepted summary resets the rejection counters.
            self._summary_soft_rejections = 0
            self._summary_hard_rejections = 0
            mentioned.add(file_name)
            messages.append("{}: {}".format(file_name, summary_text))

        missing = changed_set - mentioned
        if missing:
            missing_message = (
                "Cannot succeed: changed files not covered by the change "
                "summary ({missing}). Add one entry per changed file."
            ).format(missing=", ".join(sorted(missing)))
            return ToolFailure[str](missing_message)

        return TerminateAgentWithSuccess(ChangeResult(messages=messages))

    def fail(self) -> ToolCallOutcome:
        """End the session in failure (agent failure)."""
        return TerminateAgentWithFailure[str]("Task failed")

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        """Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs."""
        if not self.config.blame_targets:
            return ToolFailure[str]("Blame targets are not configured")

        if not blames:
            return ToolFailure[str]("Blame list must not be empty")

        invalid_blames = [(t, f) for (t, f) in blames if t not in self.config.blame_targets]
        if invalid_blames:
            return ToolFailure[str](f"Blame assignment rejected for: {invalid_blames}")

        return TerminateAgentWithSuccess(FeedbackResult(messages=blames))

    def get_write_occurred(self) -> WriteOccurred:
        """Return whether the agent has modified the filesystem during the current run."""
        return self.write_occurred

    # Helper methods

    def _create_tool_definition(self, name: str, description: str,
                                parameters: Dict[str, Any],
                                required: Optional[List[str]] = None) -> ToolDefinition:
        """Create a tool definition in OpenAI function-calling format."""
        schema = {
            "type": "object",
            "properties": parameters,
            "additionalProperties": False,
        }
        if required:
            schema["required"] = required
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": schema,
            },
        }

    def _error_response(self, error_message: str) -> ToolFailure[str]:
        """Create a ToolFailure response for a policy or parameter violation."""
        return ToolFailure[str](self._virtualize_paths(error_message))

    def _readable_list(self) -> str:
        """Comma-separated list of virtual file names the agent may read."""
        return ", ".join(sorted(set(self.config.readable_paths)))

    def _writable_list(self) -> str:
        """Comma-separated list of virtual file names the agent may write."""
        return ", ".join(sorted(set(self.config.writable_paths)))

    def _virtualize_paths(self, message: str) -> str:
        """
        Replace real on-disk paths in a message with their virtual names.

        The agent only ever sees virtual file names (e.g. 'foo.txt'), so error
        text that embeds the resolved absolute path (like "File '/Users/.../
        tests/example/foo.txt' does not exist") is rewritten to use the
        virtual name ('foo.txt') before being returned to the agent.
        """
        for real_path in self._real_paths_sorted:
            if real_path in message:
                message = message.replace(real_path, self._real_to_virtual[real_path])
        return message

    def _perform_search(self, path: str, pattern: str) -> List[Tuple[str, str]]:
        """Perform a recursive search for pattern in files.

        Returns (virtual_name, match_text) pairs; matches in writable files
        are suppressed by search_files (their content is never rendered).
        """
        results: List[Tuple[str, str]] = []
        pattern_re = re.compile(pattern)

        def _scan(real_file: str) -> None:
            virtual = self._real_to_virtual.get(real_file, os.path.basename(real_file))
            try:
                with open(real_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            results.append(
                                (virtual, f"{os.path.basename(real_file)}:{line_num}: {line.strip()}")
                            )
            except (UnicodeDecodeError, PermissionError):
                pass

        if os.path.isfile(path):
            _scan(path)
        else:
            for root, _dirs, files in os.walk(path):
                for file in files:
                    _scan(os.path.join(root, file))

        return results
