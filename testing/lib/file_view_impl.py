"""
Implementation of the LLS file_view interface.

Provides secure file system operations, policy enforcement, and per-run
state (write-occurred flag, per-file view modes, pre-write snapshots).
No stubbing state is maintained: the supersedes flag is set statically
per operation type and file_view tracks nothing about prior results;
the agent loop applies the stubbing.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .file_view import (
    FileView,
    FileViewConfig,
    VirtualName,
    WriteOccurred,
)
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolCallOutcome,
    ToolFailure,
)


class FileViewImpl(FileView):
    """
    Implementation of the LLS FileView interface.

    Provides secure file system operations, policy enforcement, and per-run
    state (write-occurred flag, per-file view modes, pre-write snapshots).
    No stubbing state is maintained: the supersedes flag is set statically
    per operation type and file_view tracks nothing about prior results;
    the agent loop applies the stubbing.
    """

    # replace supports only short search/replace strings: a whole-file swap
    # must go through update_lines (which requires the line-numbered view).
    MAX_EDIT_LENGTH = 200

    def __init__(self, config: FileViewConfig):
        """
        Initialize the file machinery with configuration.

        Args:
            config: Configuration object containing file mappings, policies,
                templates, the search result limit, and whether session-start
                reads are enabled.
        """
        self.config = config
        self.write_occurred: WriteOccurred = False

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

        # Files written by the run (virtual names, deduped, in write order).
        # advance() reports these when called without a change message.
        self._changed_files: List[str] = []

        # Pre-write content snapshots: each file's content at run start (before
        # this run's first write of that file), used by advance()'s diff report
        # when no verification callback is configured.
        self._pre_write_snapshots: Dict[VirtualName, Optional[str]] = {}

        # Template initialization (per the file_view contract): a writable file
        # with a configured template that does not exist on disk is created
        # with the template's content at run start, before any tool call; an
        # existing writable file is never modified. Initialization is part of
        # the file_view's configuration, not a run write: it does not set the
        # write-occurred flag and does not record the file as changed (the
        # file's first write of the run snapshots the template content as the
        # run-start baseline for advance()'s diff).
        for virtual, content in self.config.templates.items():
            real_path = self.config.file_mappings.get(virtual)
            if real_path is None:
                continue
            if os.path.exists(real_path):
                continue
            parent_dir = os.path.dirname(real_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return the file tools' definitions."""
        definitions = []

        # Always available
        definitions.extend([
            self._create_tool_definition(
                "read_file",
                "Read a file's ENTIRE content (files are small; reads are never paginated). "
                "Reading a writable file makes its content the file's current content in the "
                "conversation (an earlier read of the same file is replaced by a stub). "
                "Line numbers are metadata, not file content: reading "
                "a writable file that already exists REQUIRES include_line_numbers=True to enable editing via update_lines (a "
                "plain read without include_line_numbers=True is rejected); reads of read-only files provide plain content (include_line_numbers=False).",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "include_line_numbers": {"type": "boolean", "description": "Prefix each line with its line number; REQUIRED when reading a writable file that already exists; line numbers serve update_lines edits and are allowed only for writable files (default: false)", "default": False}
                }
            ),
            self._create_tool_definition(
                "replace",
                "Replace short text in a file (content-based search and replace: takes file_path, old_str, new_str, expect_multiple). Only for short one-line phrase replacements — old_str and new_str are strictly limited to at most 200 characters each. For multi-line edits, functions, classes, or block updates, always use update_lines instead (which operates on line ranges and requires include_line_numbers=True). Replaces exactly one occurrence of old_str with new_str; fails when old_str is absent or matches more than once unless expect_multiple=True (then replaces all occurrences). After an edit the file is automatically re-read with line numbers.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "old_str": {"type": "string", "description": "Exact text to find"},
                    "new_str": {"type": "string", "description": "Replacement text"},
                    "expect_multiple": {"type": "boolean", "description": "Allow multiple matches and replace all of them", "default": False}
                }
            ),
            self._create_tool_definition(
                "update_lines",
                "Replace, delete, or insert lines by 1-indexed line range (takes file_path, start_line, end_line, new_str — does NOT take old_str). Preferred tool for modifying functions, classes, and multi-line blocks: replaces lines start_line..end_line with new_str; start_line > end_line inserts new_str before start_line; empty new_str deletes the range. Requires the line-numbered view: call read_file(file_path, include_line_numbers=True) first; after a write the automatic re-read provides the line-numbered view. Line numbers are 1-indexed and current only in the most recent read.",
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
                "Search for a pattern in files. Takes optional path (virtual file name, or '.' / '/' to search all readable files; default: '.'), pattern, and optional offset/limit. Renders matches only for read-only files; matches in writable files are counted in the note but never shown (their content is not supported and would go stale).",
                {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Virtual path to search, or '.' / '/' to search all readable files (default: '.')", "default": "."},
                    "offset": {"type": "integer", "description": "Match offset to start from (default: 0)", "default": 0},
                    "limit": {"type": "integer", "description": f"Maximum rendered matches to return (1..{self.config.search_result_limit}); if omitted, returns all rendered matches, which fails if more than {self.config.search_result_limit} exist. Each result includes a note reporting how many rendered matches remain and the offset to continue from."}
                },
                required=["pattern"],
            ),
        ])

        return definitions

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        """The session-start reads: plain reads of the read-only files.

        When session-start reads are enabled, provides a session-start read
        for every file that is readable but not writable and exists as a
        regular file on disk, sorted by virtual name: a PresentedToolResult
        pairing the read_file call with the file's plain read result (never
        superseding — reads of files that are not writable never supersede).
        When disabled, provides no reads. Requesting the reads changes no
        file_view state; filesystem errors reading a readable file are
        unhandled (propagate).
        """
        if not self.config.session_start_reads_enabled:
            return []
        reads: List[PresentedToolResult] = []
        read_only = sorted(
            set(self.config.readable_paths) - set(self.config.writable_paths)
        )
        for file_path in read_only:
            real_path = self.config.file_mappings.get(file_path, file_path)
            if not os.path.isfile(real_path):
                continue
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            content = self._render_lines(lines, False)
            n = len(lines)
            reads.append(PresentedToolResult(
                name="read_file",
                arguments={"file_path": file_path},
                result=ToolResult(
                    content=content,
                    supersedes=False,
                    note=f"Read {n} lines (plain)",
                ),
            ))
        return reads

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

        # Line numbers exist to serve update_lines edits, which require a
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
            return self._error_response(f"File '{file_path}' does not exist")
        if not os.path.isfile(real_path):
            return self._error_response(f"Path '{file_path}' is not a file")

        # A writable file that already exists on disk is only readable in the
        # line-numbered view: the agent must buy into line numbers (they are
        # metadata, not file content), which also guarantees the numbered
        # view that update_lines requires. A plain read fails with guidance.
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
        # the view persists across writes and gates update_lines.
        self._file_views[file_path] = include_line_numbers

        content = self._render_lines(lines, include_line_numbers)
        n = len(lines)
        view = "line-numbered" if include_line_numbers else "plain"
        note = f"Read {n} lines ({view})"

        # Routing per the file_view contract's Stubbing rules: a read of a
        # writable file supersedes the earlier result for that file (the
        # agent loop stubs it); a read of a file that is not writable never
        # supersedes an earlier result — reads of readable files are not
        # stubbed.
        if file_path in self.config.writable_paths:
            return [ToolResult(
                content=content,
                supersedes=True,
                note=note,
            )]
        return [ToolResult(content=content, supersedes=False, note=note)]

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

        Shared by the editing tools (replace, update_lines): a successful
        edit is a file write — it sets the write-occurred flag and records the
        changed file. The outcome is a sequence of two results: the write
        confirmation (a `ToolResult` whose content is the operation's status,
        a structured success message, never a file-content echo; supersedes
        is set so the agent loop stubs the file's earlier read) and the
        injected read (the automatic re-read, per the file_view contract).
        A write invalidates the line-numbered view; the injected read that
        follows re-enables it, so a line-range edit may follow a write
        without a further read.
        """
        self._snapshot(file_path, real_path)
        # The write changes the line structure: reset the view to plain so
        # the injected read re-establishes fresh line numbers.
        self._file_views[file_path] = False

        try:
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")

        self.write_occurred = True
        if file_path not in self._changed_files:
            self._changed_files.append(file_path)

        return self._write_outcome(file_path, status)

    def _write_outcome(self, file_path: VirtualName, status: str) -> ToolCallOutcome:
        """The two-result outcome of a successful file write, in order.

        Per the file_view contract's Auto re-read rules: the write confirmation
        (a `ToolResult` with `supersedes` set, its content a minimal status)
        and the injected read (a `PresentedToolResult` pairing the `read_file`
        call with its numbered result, `supersedes` set). The injected read
        supersedes the write confirmation, so the file's most recent
        non-stubbed result is a read; the next write or read for the file
        supersedes it, per the Stubbing rules.
        """
        return [
            ToolResult(content=status, supersedes=True),
            self._injected_read(file_path),
        ]

    def _injected_read(self, file_path: VirtualName) -> PresentedToolResult:
        """The auto re-read after a file write: a numbered read of the file.

        The injected read carries the file's full current content rendered in
        the line-numbered view with `supersedes` set, and re-enables the
        file's line-numbered view (a write reset it to plain). It is
        presented as `read_file(file_path, include_line_numbers=True)`; the
        consuming agent loop assigns the call's id and presents the call
        immediately before the result.
        """
        real_path = self.config.file_mappings[file_path]
        with open(real_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        # A file just written is expected to be readable; a read failure here
        # is a filesystem error, which is unhandled per the file_view contract.
        self._file_views[file_path] = True
        content = self._render_lines(lines, True)
        n = len(lines)
        return PresentedToolResult(
            name="read_file",
            arguments={"file_path": file_path, "include_line_numbers": True},
            result=ToolResult(
                content=content,
                supersedes=True,
                note=f"Read {n} lines (line-numbered)",
            ),
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

    def replace(self, file_path: VirtualName, old_str: str, new_str: str,
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
                f"replace supports only short old_str and new_str (at most "
                f"{self.MAX_EDIT_LENGTH} characters each; got old_str="
                f"{len(old_str)}, new_str={len(new_str)}). Use update_lines "
                f"for larger edits (requires the line-numbered view: "
                f"read_file(file_path, include_line_numbers=True))."
            )

        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(
                f"File '{file_path}' does not exist; replace and update_lines modify existing files only"
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

    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
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

        # update_lines operates on 1-indexed line numbers: the file's current
        # view must be line-numbered (the agent enabled line numbers by reading
        # with include_line_numbers=True). A write resets the view to plain —
        # the line numbers are invalidated until the next numbered read — so
        # a line edit after a write fails with the reminder below. The failure
        # supersedes nothing and removes nothing (per the file_view contract).
        if not self._file_views.get(file_path, False):
            return ToolFailure(
                value=(
                    f"update_lines requires the line-numbered view: call "
                    f"read_file('{file_path}', include_line_numbers=True) to "
                    f"re-enable it (a write invalidated the line numbers); the "
                    f"file's current view is plain"
                ),
            )

        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(
                f"File '{file_path}' does not exist; replace and update_lines modify existing files only"
            )
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")

        lines, trailing = self._split_lines(content)
        n = len(lines)
        if n == 0:
            if start_line == 1 and end_line in (0, 1):
                new_lines = [new_str] if new_str else []
                message = f"Inserted content before line 1 in {file_path}"
                content = new_str if new_str else ""
                return self._apply_write(file_path, real_path, content, message)
            else:
                return self._error_response(
                    f"File '{file_path}' is empty (0 lines): use start_line=1, end_line=0 (or end_line=1) to insert content"
                )
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

    def search_files(self, path: VirtualName = ".", pattern: str = "",
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        """Search for a pattern in files; render matches only for read-only files."""
        # Determine files to search based on path scope
        if path in (".", "/", ""):
            search_virtuals = sorted(set(self.config.readable_paths))
        elif path in self.config.file_mappings:
            if path not in self.config.readable_paths:
                return self._error_response(
                    f"Path '{path}' is not readable. "
                    f"Files you can read: {self._readable_list()}"
                )
            real_path = self.config.file_mappings[path]
            if not os.path.exists(real_path):
                return self._error_response(f"Path '{real_path}' does not exist")
            search_virtuals = [path]
        else:
            # Check if path matches directory prefix of readable files
            norm_prefix = path.rstrip("/") + "/"
            matching = [
                v for v in self.config.readable_paths
                if v.startswith(norm_prefix) or v == path.rstrip("/")
            ]
            if matching:
                search_virtuals = sorted(set(matching))
            else:
                return self._error_response(
                    f"File path '{path}' not found in mappings. "
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

        if offset is None:
            offset = 0

        # Perform search across all scoped files; matches are (virtual_name, text) pairs
        matches: List[Tuple[str, str]] = []
        for vpath in search_virtuals:
            real_path = self.config.file_mappings.get(vpath)
            if not real_path or not os.path.exists(real_path):
                continue
            try:
                matches.extend(self._perform_search(real_path, pattern))
            except Exception as e:
                return self._error_response(f"Error searching '{vpath}': {str(e)}")

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
        return [ToolResult(content=content, supersedes=False, note=note)]

    def get_write_occurred(self) -> WriteOccurred:
        """Return whether the agent has modified the filesystem during the current run."""
        return self.write_occurred

    def get_changed_files(self) -> List[VirtualName]:
        """The files written by the run, in write order (deduped)."""
        return list(self._changed_files)

    def get_run_start_snapshot(self, file_path: VirtualName) -> Optional[str]:
        """The file's content at run start (before the run's first write of
        the file); None when no baseline was captured."""
        return self._pre_write_snapshots.get(file_path)

    def get_current_content(self, file_path: VirtualName) -> Optional[str]:
        """The file's current content on disk; None when unreadable."""
        real_path = self.config.file_mappings.get(file_path)
        if real_path is None:
            return None
        try:
            with open(real_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

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

    def sanitize_paths(self, text: str) -> str:
        """Translate referenced disk paths, workspace paths, and package prefixes in text into virtual names."""
        if not text:
            return text
        result = text
        for real_path in self._real_paths_sorted:
            vname = self._real_to_virtual[real_path]
            # Replace full absolute path
            result = result.replace(real_path, vname)
            # Replace relative subpaths (e.g. testing/lib/foo.py or lib/foo.py)
            parts = real_path.replace("\\", "/").split("/")
            for i in range(1, len(parts)):
                subpath = "/".join(parts[i:])
                if subpath and subpath in result:
                    result = result.replace(subpath, vname)
            # Replace Bazel target formats if present (e.g. //testing/lib:stem)
            stem = os.path.splitext(os.path.basename(real_path))[0]
            if stem:
                result = re.sub(r"//[a-zA-Z0-9_/]+:" + re.escape(stem) + r"\b", vname, result)
        return result

    def _virtualize_paths(self, message: str) -> str:
        """Alias for sanitize_paths."""
        return self.sanitize_paths(message)

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
