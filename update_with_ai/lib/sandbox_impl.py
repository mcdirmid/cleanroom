"""
Implementation of the LLS Sandbox interface.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

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


# Pinned maximum content a single read tool call may return (bytes).
# Reads (file or chunk) that would return more than this fail and the agent
# must paginate explicitly with offset/limit or chunk_indices.
READ_SIZE_LIMIT = 20000


class SandboxImpl(Sandbox):
    """
    Implementation of the LLS Sandbox interface.
    
    Provides secure file system operations with stubbing semantics,
    policy enforcement, and state management per run.
    """
    
    def __init__(self, config: SandboxConfig):
        """
        Initialize the sandbox with configuration.
        
        Args:
            config: Configuration object containing file mappings, policies, etc.
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
        
        # Per-run stubbing state
        self._read_regions: Dict[VirtualName, List[Tuple[int, int]]] = {}  # file -> [(start_line, end_line)]
        self._chunk_reads: Dict[VirtualName, Set[int]] = {}  # file -> set of chunk indices
        self._searches: Set[Tuple[VirtualName, str, int, Optional[int]]] = set()  # (path, pattern, offset, limit)
        # Line-numbered read regions, cleared by any write: replace_lines may
        # edit only ranges currently visible in context (read with line
        # numbers after the file's last write).
        self._numbered_regions: Dict[VirtualName, List[Tuple[int, int]]] = {}
        # Sticky line-number mode: once a file is read with line numbers, a
        # plain read of it is a hard tool failure, ever (never a stub).
        self._line_numbered_reads: Set[VirtualName] = set()

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
        
        # Validate Python accessibility
        self._python_accessible = self._check_python_access()
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return tool definitions based on configuration."""
        definitions = []
        
        # Always available
        definitions.extend([
            self._create_tool_definition(
                "read_file",
                "Read content from a file with line numbers",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "start_line": {"type": "integer", "description": "1-indexed first line to read (default: 1)", "default": 1},
                    "end_line": {"type": "integer", "description": "1-indexed last line to read (default: end of file); must be >= start_line"},
                    "include_line_numbers": {"type": "boolean", "description": "Prefix each line with its line number; line numbers serve replace_lines edits and are allowed only for writable files (default: false)", "default": False}
                }
            ),
            self._create_tool_definition(
                "write_file",
                "Create a NEW file with the given content. Fails if the file already exists — use edit_file (content-based) or replace_lines (line-based) to modify existing files. Empty content is rejected.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                }
            ),
            self._create_tool_definition(
                "edit_file",
                "Replace text in a file (content-based search and replace): replaces exactly one occurrence of old_str with new_str; fails when old_str is absent or matches more than once unless expect_multiple=True (then replaces all occurrences).",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "old_str": {"type": "string", "description": "Exact text to find"},
                    "new_str": {"type": "string", "description": "Replacement text"},
                    "expect_multiple": {"type": "boolean", "description": "Allow multiple matches and replace all of them", "default": False}
                }
            ),
            self._create_tool_definition(
                "replace_lines",
                "Replace, delete, or insert lines by 1-indexed line range: replaces lines start_line..end_line with new_content; start_line > end_line inserts new_content before start_line; empty new_content deletes the range. You can only edit line ranges currently visible in context: read_file(..., include_line_numbers=true) the range first (reads go stale after every edit). Line numbers are 1-indexed.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "start_line": {"type": "integer", "description": "1-indexed start line (inclusive); between 1 and len(file)+1"},
                    "end_line": {"type": "integer", "description": "1-indexed end line (inclusive); between 0 and len(file)"},
                    "new_content": {"type": "string", "description": "Replacement content; empty deletes the range"}
                }
            ),
            self._create_tool_definition(
                "search_files",
                "Search for a pattern in files",
                {
                    "path": {"type": "string", "description": "Virtual path to search"},
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "offset": {"type": "integer", "description": "Match offset to start from (default: 0)", "default": 0},
                    "limit": {"type": "integer", "description": f"Maximum matches to return (1..{self.config.search_result_limit}); if omitted, returns all matches, which fails if more than {self.config.search_result_limit} exist. Each result includes a note reporting how many matches remain and the offset to continue from."}
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
                                "summary": {"type": "string", "description": "One short sentence on what changed in the file (not how it was done)"}
                            },
                            "required": ["file", "summary"],
                            "additionalProperties": False
                        },
                        "description": "Required when the run changed files: one entry per changed file, each summarizing what changed in one short sentence"
                    }
                },
            ),
            self._create_tool_definition(
                "fail",
                "Signal failed termination",
                {}
            )
        ])
        
        # Conditional: Python chunk tools
        if self._python_accessible:
            definitions.extend([
                self._create_tool_definition(
                    "read_chunks",
                    "Read semantic chunks from a Python file",
                    {
                        "file_path": {"type": "string", "description": "Virtual path to the Python file"},
                        "chunk_indices": {"type": "array", "items": {"type": "integer"}, "description": f"Chunk indices to read; if omitted, reads all chunks, which fails if their total content exceeds {self.config.read_size_limit} bytes. Each result includes a note reporting how many chunks remain."},
                        "include_adjacent": {"type": "boolean", "description": "Include neighboring chunks", "default": False}
                    }
                ),
                self._create_tool_definition(
                    "replace_chunks",
                    "Replace multiple chunks in a Python file atomically",
                    {
                        "file_path": {"type": "string", "description": "Virtual path to the Python file"},
                        "replacements": {"type": "array", "description": "List of replacements with 'index' and 'new_content'"},
                        "encoding": {"type": "string", "description": "Optional file encoding"}
                    }
                )
            ])
        
        # Always: verify — reports the diff of the run's changes; runs the
        # configured verification callback when one exists.
        definitions.append(
            self._create_tool_definition(
                "verify",
                "Report the diff of the run's file changes vs. their state at run start. When a verification callback is configured, run it and report whether the output passed. When the run changed files, succeed() requires verify() to have been called.",
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
    
    def read_file(self, file_path: VirtualName, start_line: int = 1,
                  end_line: Optional[int] = None,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        """Read lines from a file, optionally numbered."""
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
        
        # Sticky line-number mode: once a file is read with line numbers, a
        # plain read of it is a hard tool failure, ever — never a stub.
        if not include_line_numbers and file_path in self._line_numbered_reads:
            return self._error_response(
                f"Plain read of '{file_path}' is not allowed: the file was "
                f"read with include_line_numbers=true; keep "
                f"include_line_numbers=true for this file"
            )
        
        # Validate parameters
        if not isinstance(start_line, int) or start_line < 1:
            return self._error_response("start_line must be a positive integer (1-indexed)")
        if end_line is not None:
            if not isinstance(end_line, int):
                return self._error_response("end_line must be an integer or omitted")
            if end_line < start_line:
                return self._error_response(
                    f"end_line ({end_line}) must be >= start_line ({start_line})"
                )
        
        # Resolve path
        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")
        if not os.path.isfile(real_path):
            return self._error_response(f"Path '{real_path}' is not a file")
        
        # Read and split into lines
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
        except Exception as e:
            return self._error_response(f"Error reading file: {str(e)}")
        
        n = len(lines)
        if start_line > n + 1:
            return self._error_response(
                f"start_line ({start_line}) is beyond the end of the file ({n} lines)"
            )
        read_end = n if end_line is None else min(end_line, n)
        if read_end < start_line:
            # Empty read at EOF: no lines in range, not stubbed.
            note = (
                f"File has {n} lines; no lines remain to read (start_line={start_line} "
                f"is past end of file); 0 lines remain"
            )
            return ToolResult(
                content="",
                content_id=file_path,
                stub_previous=False,
                note=note,
            )
        
        selected = lines[start_line - 1:read_end]
        if include_line_numbers:
            width = len(str(read_end))
            content = "\n".join(
                f"{i:>{width}} \u2502 {line}" for i, line in enumerate(selected, start=start_line)
            )
        else:
            content = "\n".join(selected)
        
        # The read size limit bounds how much content a single read may
        # return; an oversized read fails and the agent must narrow the range.
        if len(content) > self.config.read_size_limit:
            return self._error_response(
                f"Reading lines {start_line}-{read_end} produces {len(content)} "
                f"chars, exceeding the maximum read size "
                f"({self.config.read_size_limit} chars); specify a smaller "
                f"start_line/end_line range"
            )
        
        # A read always returns content. Dedup stubs the previous instances of
        # the file's content in the conversation (stub_previous=True) — never
        # the read itself.
        overlaps = self._overlaps_previous_read(
            file_path, start_line, read_end, numbered_only=include_line_numbers
        )
        
        # Update state: every read returns content, so every read records its
        # region; future overlapping reads stub these instances. A numbered
        # read also marks the file as line-numbered (sticky): plain reads of
        # it fail from then on, ever.
        self._read_regions.setdefault(file_path, []).append((start_line, read_end))
        if include_line_numbers:
            self._numbered_regions.setdefault(file_path, []).append((start_line, read_end))
            self._line_numbered_reads.add(file_path)
        
        remaining = max(n - read_end, 0)
        note = (
            f"Read lines {start_line}-{read_end} ({read_end - start_line + 1} "
            f"lines); file has {n} lines; {remaining} lines remain; continue "
            f"with start_line={read_end + 1}"
        )
        
        result = ToolResult(
            content=content,
            content_id=file_path,
            stub_previous=overlaps,
            note=note,
        )
        return result
    
    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome:
        """Write content to a file."""
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
        if file_path not in self._pre_write_snapshots:
            try:
                with open(real_path, "r", encoding="utf-8") as f:
                    self._pre_write_snapshots[file_path] = f.read()
            except FileNotFoundError:
                self._pre_write_snapshots[file_path] = ""
            except Exception:
                self._pre_write_snapshots[file_path] = None

        # Write file
        try:
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")
        
        # Update state
        self.write_occurred = True
        self._numbered_regions.pop(file_path, None)
        if file_path not in self._changed_files:
            self._changed_files.append(file_path)
        # Clear read regions for this file since it was modified
        self._read_regions.pop(file_path, None)
        self._chunk_reads.pop(file_path, None)
        # Clear search deduplication for this file
        self._searches = {k for k in self._searches if k[0] != file_path}
        
        result = ToolResult(
            content=json.dumps({"success": True, "message": "File written successfully"}),
            content_id=file_path,
            stub_previous=True
        )
        return result

    def _apply_write(self, file_path: VirtualName, real_path: str, new_content: str,
                     result: Dict[str, Any]) -> ToolCallOutcome:
        """Snapshot pre-write content, write the file, and update per-run state.

        Shared by the editing tools (edit_file, replace_lines): a successful
        edit is a file write — it sets the write-occurred flag, records the
        changed file, clears per-file stubbing state, and returns a minimal
        structured result (no file-content echo).
        """
        if file_path not in self._pre_write_snapshots:
            try:
                with open(real_path, "r", encoding="utf-8") as f:
                    self._pre_write_snapshots[file_path] = f.read()
            except FileNotFoundError:
                self._pre_write_snapshots[file_path] = ""
            except Exception:
                self._pre_write_snapshots[file_path] = None

        try:
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")

        self.write_occurred = True
        self._numbered_regions.pop(file_path, None)
        if file_path not in self._changed_files:
            self._changed_files.append(file_path)
        self._read_regions.pop(file_path, None)
        self._chunk_reads.pop(file_path, None)
        self._searches = {k for k in self._searches if k[0] != file_path}

        return ToolResult(
            content=json.dumps(result),
            content_id=file_path,
            stub_previous=True
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
            message = f"Replaced {count} occurrences"
        else:
            new_content = content.replace(old_str, new_str, 1)
            message = "Replaced 1 occurrence"
        return self._apply_write(
            file_path, real_path, new_content,
            {"success": True, "matches_found": count, "message": message},
        )

    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                      new_content: str) -> ToolCallOutcome:
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

        # replace_lines operates on 1-indexed line numbers: the edited range
        # must be currently visible in context — read with line numbers since
        # the file's last write (any write clears what is visible).
        if start_line <= end_line:
            need_start, need_end = start_line, end_line
        else:
            need_start, need_end = max(1, start_line - 1), min(start_line, n)
        if not self._range_visible(file_path, need_start, need_end):
            return self._error_response(
                f"replace_lines range lines {start_line}-{end_line} is not "
                f"currently visible in context: call read_file('{file_path}', "
                f"include_line_numbers=true, start_line={need_start}, "
                f"end_line={need_end}) first; reads go stale after every edit"
            )

        insertion = [new_content] if new_content else []
        if start_line > end_line:
            new_lines = lines[:start_line - 1] + insertion + lines[start_line - 1:]
            result = {"success": True, "inserted_before": start_line,
                      "message": f"Inserted content before line {start_line}"}
        else:
            new_lines = lines[:start_line - 1] + insertion + lines[end_line:]
            removed = end_line - start_line + 1
            if new_content:
                result = {"success": True, "lines_replaced": removed,
                          "message": f"Replaced lines {start_line}-{end_line}"}
            else:
                result = {"success": True, "lines_deleted": removed,
                          "message": f"Deleted lines {start_line}-{end_line}"}

        if new_lines:
            content = '\n'.join(new_lines)
            if trailing:
                content += '\n'
        else:
            content = ""
        return self._apply_write(file_path, real_path, content, result)
    
    def search_files(self, path: VirtualName, pattern: str,
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        """Search for a pattern in files."""
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
        
        # A search always returns its results. Dedup stubs the previous
        # instances of the same search in the conversation (stub_previous) —
        # never the search itself. Stubbing is per pagination window: paging
        # through results with a new offset is a distinct search.
        search_key = (path, pattern, offset, limit)
        overlaps = search_key in self._searches
        
        # Perform search
        try:
            results = self._perform_search(real_path, pattern)
        except Exception as e:
            return self._error_response(f"Error searching: {str(e)}")
        total = len(results)
        if limit is None:
            # Omitted limit means all matches; allowed only within the
            # search result limit, otherwise the tool fails and the agent
            # must page through results with offset/limit.
            if total > self.config.search_result_limit:
                return self._error_response(
                    f"Search returned {total} matches, exceeding the search "
                    f"result limit ({self.config.search_result_limit}); "
                    f"specify offset/limit to page through results"
                )
            page = results
        else:
            page = results[offset:offset + limit]
        content = "\n".join(page)
        
        # Update state: every search returns results and records its key;
        # future identical searches stub these instances.
        self._searches.add(search_key)
        
        page_end = offset + len(page)
        remaining = max(total - page_end, 0)
        note = (
            f"{total} matches total; {remaining} more after this page; "
            f"continue with offset={page_end}"
        )
        
        result = ToolResult(
            content=content,
            content_id=path,
            stub_previous=overlaps,
            note=note,
        )
        return result
    
    def read_chunks(self, file_path: VirtualName, 
                    chunk_indices: Optional[List[int]] = None,
                    include_adjacent: bool = False) -> ToolCallOutcome:
        """Read semantic chunks from a Python file."""
        # Validate Python accessibility
        if not self._python_accessible:
            return self._error_response("Python files are not accessible")
        
        # Validate file
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File path '{file_path}' not found in mappings. "
                f"Files you can read: {self._readable_list()}"
            )
        if file_path not in self.config.readable_paths:
            return self._error_response(
                f"File path '{file_path}' is not readable. "
                f"Files you can read: {self._readable_list()}"
            )
        
        real_path = self.config.file_mappings[file_path]
        if not real_path.endswith('.py'):
            return self._error_response(f"File '{file_path}' is not a Python file")
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")

        # Parse Python file into chunks
        try:
            chunks = self._parse_python_chunks(real_path)
        except Exception as e:
            return self._error_response(f"Error parsing Python file: {str(e)}")

        # Validate requested chunk indices: per the sandbox LLS they must be
        # valid non-negative indices; an out-of-range index is a parameter
        # error (unlike replace_chunks' neighbors, no index is silently dropped).
        if chunk_indices is not None:
            for idx in chunk_indices:
                if idx < 0 or idx >= len(chunks):
                    return self._error_response(
                        f"Chunk index {idx} out of range (max: {len(chunks)-1})"
                    )

        if not chunks:
            # Empty file returns empty content
            result = ToolResult(
                content="",
                content_id=file_path,
                stub_previous=False,
                note="File is empty; no chunks",
            )
            return result
        
        # Determine which chunks to return
        if chunk_indices is None:
            indices_to_read = set(range(len(chunks)))
        else:
            indices_to_read = set(chunk_indices)
            if include_adjacent:
                for idx in chunk_indices:
                    if idx > 0:
                        indices_to_read.add(idx - 1)
                    if idx < len(chunks) - 1:
                        indices_to_read.add(idx + 1)
        
        # The read size limit bounds how much content a single chunk read may
        # return. Omitted chunk_indices means "all chunks": allowed only when
        # the total content fits within the limit; otherwise the tool fails
        # and the agent must paginate with explicit chunk_indices.
        total_bytes = sum(len(chunks[idx]) for idx in indices_to_read)
        if total_bytes > self.config.read_size_limit:
            if chunk_indices is None:
                return self._error_response(
                    f"Reading all chunks ({total_bytes} bytes) exceeds the "
                    f"maximum read size ({self.config.read_size_limit} bytes); "
                    f"specify chunk_indices to read them in parts"
                )
            return self._error_response(
                f"Requested chunks total {total_bytes} bytes, exceeding the "
                f"maximum read size ({self.config.read_size_limit} bytes); "
                f"specify fewer chunk indices"
            )
        
        # A chunk read always returns content. Dedup stubs the previous
        # instances of the file's content (stub_previous=True) — never the
        # read itself.
        overlaps = self._overlaps_previous_chunks(file_path, indices_to_read)
        
        # Build result
        result_lines = []
        for idx in sorted(indices_to_read):
            if idx < len(chunks):
                result_lines.append(f"--- Chunk {idx} ---")
                result_lines.append(chunks[idx])
        content = "\n".join(result_lines)
        
        # Update state: every chunk read returns content and records its
        # chunks; future overlapping reads stub these instances.
        self._chunk_reads.setdefault(file_path, set()).update(indices_to_read)
        
        remaining_chunks = len(chunks) - len(indices_to_read)
        note = (
            f"Read chunks {sorted(indices_to_read)} of {len(chunks)} "
            f"({total_bytes} bytes); {remaining_chunks} chunks remain; "
            f"specify chunk_indices to read more"
        )
        
        result = ToolResult(
            content=content,
            content_id=file_path,
            stub_previous=overlaps,
            note=note,
        )
        return result
    
    def replace_chunks(self, file_path: VirtualName, replacements: List[Dict],
                       encoding: Optional[str] = None) -> ToolCallOutcome:
        """Replace multiple chunks in a Python file atomically."""
        # Validate Python accessibility
        if not self._python_accessible:
            return self._error_response("Python files are not accessible")
        
        # Validate file
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
        
        real_path = self.config.file_mappings[file_path]
        if not real_path.endswith('.py'):
            return self._error_response(f"File '{file_path}' is not a Python file")
        if not os.path.exists(real_path):
            return self._error_response(f"File '{real_path}' does not exist")
        
        # Validate replacements
        if not replacements:
            return self._error_response("Replacements list must not be empty")
        for r in replacements:
            if 'index' not in r or 'new_content' not in r:
                return self._error_response("Each replacement must have 'index' and 'new_content'")
            if not isinstance(r['index'], int) or r['index'] < 0:
                return self._error_response("Each replacement index must be a non-negative integer")
        
        # Parse file
        try:
            chunks = self._parse_python_chunks(real_path)
        except Exception as e:
            return self._error_response(f"Error parsing Python file: {str(e)}")
        
        if not chunks:
            return self._error_response("Cannot replace chunks in empty file")
        
        # Validate indices
        for r in replacements:
            if r['index'] >= len(chunks):
                return self._error_response(f"Chunk index {r['index']} out of range (max: {len(chunks)-1})")
        
        # Snapshot pre-write content (first write of the run only) for the
        # no-callback verify diff.
        if file_path not in self._pre_write_snapshots:
            try:
                with open(real_path, 'r', encoding=encoding or 'utf-8') as f:
                    self._pre_write_snapshots[file_path] = f.read()
            except FileNotFoundError:
                self._pre_write_snapshots[file_path] = ""
            except Exception:
                self._pre_write_snapshots[file_path] = None

        # Apply replacements (atomic)
        try:
            for r in replacements:
                chunks[r['index']] = r['new_content']
            
            # Reconstruct file content
            new_content = "\n".join(chunks) + "\n"
            
            # Write file
            with open(real_path, 'w', encoding=encoding or 'utf-8') as f:
                f.write(new_content)
        except Exception as e:
            return self._error_response(f"Error writing file: {str(e)}")
        
        # Update state
        self.write_occurred = True
        self._numbered_regions.pop(file_path, None)
        if file_path not in self._changed_files:
            self._changed_files.append(file_path)
        self._read_regions.pop(file_path, None)
        self._chunk_reads.pop(file_path, None)
        # Clear search deduplication for this file
        self._searches = {k for k in self._searches if k[0] != file_path}
        
        result = ToolResult(
            content=json.dumps({
                "success": True,
                "chunks_replaced": len(replacements),
                "message": f"Replaced {len(replacements)} chunk(s)",
            }),
            content_id=file_path,
            stub_previous=True
        )
        return result
    
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
                content_id="verify",
                stub_previous=True
            )
        
        try:
            success, output = self.config.verification_callback()
        except Exception as e:
            return ToolFailure[str](f"Verification error: {str(e)}")
        
        self._verify_passed = success
        content = diff if not output else diff + "\n\n" + output
        if success:
            content += "\nVerification passed; succeed() may now be called."
        else:
            content += (
                "\nVerification failed; fix the reported issues by changing "
                "files (edit_file/replace_lines/write_file) and then call "
                "verify() again, or call blame() or fail() to end the run."
            )
        return ToolResult(
            content=content,
            content_id="verify",
            stub_previous=True
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
    
    MAX_CHANGE_SUMMARY_LENGTH = 200

    def succeed(self, changes: Optional[List[Dict[str, str]]] = None) -> ToolCallOutcome:
        """Signal successful termination, carrying the agent's change summary.

        Gated on verification first: when a verification callback is
        configured, succeed() may only be called after verify() has succeeded
        (exit 0). Then, when the run changed files, `changes` must list one
        entry per changed file — {file, summary} — each summary a single
        short sentence on what changed (not how).
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
        # A claimed change must appear in the diff: a file identical to its
        # run-start snapshot has not changed, and reporting it as changed is a
        # fabricated summary (the file was rewritten with the same content).
        for change in changes:
            file_path = change.get("file")
            if file_path not in self._pre_write_snapshots:
                continue  # the changed-file gate below covers unknown files
            real_path = self.config.file_mappings[file_path]
            try:
                with open(real_path, "r", encoding="utf-8") as f:
                    current = f.read()
            except Exception:
                continue
            if current == self._pre_write_snapshots[file_path]:
                return ToolFailure[str](
                    f"Cannot succeed: the claimed change for '{file_path}' "
                    f"does not appear in the diff; the file is unchanged — "
                    f"report no change."
                )
        if self._changed_files:
            if not changes:
                failure_message = (
                    "Cannot succeed: the run changed files ({changed}). Call "
                    "succeed(changes=[{{file, summary}}, ...]) with one entry "
                    "per changed file — each summary one short sentence on "
                    "what changed in that file (not how it was done) — so the "
                    "next agent knows what changed, or call fail() or blame() "
                    "to end the run."
                ).format(changed=", ".join(self._changed_files))
                return ToolFailure[str](failure_message)

            changed_set = set(self._changed_files)
            mentioned: Set[str] = set()
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
                    ).format(file=file_name, changed=", ".join(self._changed_files))
                    return ToolFailure[str](unknown_message)
                summary_text = summary.strip()
                if len(summary_text) > self.MAX_CHANGE_SUMMARY_LENGTH:
                    long_message = (
                        "Cannot succeed: the summary for '{file}' is {length} "
                        "chars (max {max}). Use one short sentence on what "
                        "changed in the file."
                    ).format(
                        file=file_name,
                        length=len(summary_text),
                        max=self.MAX_CHANGE_SUMMARY_LENGTH,
                    )
                    return ToolFailure[str](long_message)
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
        return TerminateAgentWithSuccess(NoChangeResult())
    
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
    
    def _overlaps_previous_read(self, file_path: VirtualName, start_line: int, end_line: int,
                                numbered_only: bool = False) -> bool:
        """Whether the line range overlaps a previously read range.

        A line-numbered read is a distinct view (it carries line numbers a
        plain read never showed): it overlaps only previous numbered reads.
        Overlap does not stub the current read — the read always returns
        content, and overlap only signals that previous instances of the
        file's content in the conversation should be stubbed.
        """
        regions = (
            self._numbered_regions.get(file_path, [])
            if numbered_only
            else self._read_regions.get(file_path, [])
        )
        for prev_start, prev_end in regions:
            if start_line <= prev_end and end_line >= prev_start:
                return True
        return False

    def _range_visible(self, file_path: VirtualName, start_line: int, end_line: int) -> bool:
        """Whether the line range is fully covered by current numbered reads.

        Numbered-read regions are cleared by any write, so this reflects only
        what the agent can currently see in context with line numbers.
        """
        regions = sorted(self._numbered_regions.get(file_path, []))
        if not regions:
            return False
        merged: List[Tuple[int, int]] = []
        for s, e in regions:
            if merged and s <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        return any(s <= start_line and end_line <= e for s, e in merged)
    
    def _overlaps_previous_chunks(self, file_path: VirtualName,
                                  indices: Set[int]) -> bool:
        """Whether the requested chunk indices overlap previously read chunks.

        Overlap does not stub the current read — the read always returns
        content; overlap only signals that previous instances of the file's
        content in the conversation should be stubbed.
        """
        if file_path not in self._chunk_reads:
            return False
        
        return bool(indices & self._chunk_reads[file_path])
    
    def _perform_search(self, path: str, pattern: str) -> List[str]:
        """Perform a recursive search for pattern in files."""
        results = []
        pattern_re = re.compile(pattern)
        
        if os.path.isfile(path):
            # Search a single file
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            results.append(f"{os.path.basename(path)}:{line_num}: {line.strip()}")
            except (UnicodeDecodeError, PermissionError):
                pass
        else:
            # Search directory recursively
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line_num, line in enumerate(f, 1):
                                if pattern_re.search(line):
                                    rel_path = os.path.relpath(file_path, path)
                                    results.append(f"{rel_path}:{line_num}: {line.strip()}")
                    except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                        continue
        
        return results
    
    def _check_python_access(self) -> bool:
        """Check if Python files are accessible."""
        for virtual_path, real_path in self.config.file_mappings.items():
            if real_path.endswith('.py') and virtual_path in self.config.readable_paths:
                return True
        return False
    
    def _parse_python_chunks(self, file_path: str) -> List[str]:
        """Parse a Python file into semantic chunks (top-level constructs)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            return []
        
        # Parse by top-level constructs (class/function definitions)
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            # Check if this is a top-level definition (indent 0 and not empty/comment)
            is_top_level = (indent == 0 and stripped and not stripped.startswith('#'))
            
            if is_top_level and current_chunk:
                # Save current chunk and start a new one
                if any(c.strip() for c in current_chunk):
                    chunks.append('\n'.join(current_chunk))
                current_chunk = []
            
            current_chunk.append(line)
        
        # Add the last chunk
        if current_chunk and any(c.strip() for c in current_chunk):
            chunks.append('\n'.join(current_chunk))
        
        return chunks