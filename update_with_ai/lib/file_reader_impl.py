# lib/file_reader_impl.py
"""
Implementation of the LLS file_reader interface.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .file_reader import (
    FileReader,
    FileReaderConfig,
    VirtualName,
)
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolCallOutcome,
    ToolFailure,
)


class FileReaderImpl(FileReader):
    """
    Implementation of the LLS FileReader interface.
    """

    def __init__(self, config: FileReaderConfig):
        self.config = config

        self._real_to_virtual: Dict[str, str] = {}
        for virtual, real in self.config.file_mappings.items():
            if real:
                self._real_to_virtual.setdefault(real, virtual)
        self._real_paths_sorted: List[str] = sorted(
            self._real_to_virtual.keys(), key=len, reverse=True
        )

    def resolve_path(self, file_path: VirtualName) -> Optional[str]:
        return self.config.file_mappings.get(file_path)

    def is_readable(self, file_path: VirtualName) -> bool:
        return file_path in self.config.readable_paths

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return [
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
                "search_files",
                "Search for a pattern in files. Takes optional path (virtual file name, or '.' / '/' to search all readable files; default: '.'), pattern, and optional offset/limit. Renders matches only for read-only files; matches in writable files are counted in the note but never shown (their content is not supported and would go stale).",
                {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Virtual path to search, or '.' / '/' to search all readable files (default: '.')", "default": "."},
                    "offset": {"type": "integer", "description": "Match offset to start from (default: 0)", "default": 0},
                    "limit": {"type": "integer", "description": f"Maximum rendered matches to return (1..{self.config.search_result_limit}); if omitted, returns all rendered matches, which fails if more than {self.config.search_result_limit} exist. Each result includes a note reporting how many rendered matches remain and the offset to continue from."}
                },
                required=["pattern"]
            )
        ]

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        if not self.config.session_start_reads_enabled:
            return []

        session_reads: List[PresentedToolResult] = []
        for virtual_name in sorted(self.config.readable_paths):
            real_path = self.config.file_mappings.get(virtual_name)
            if not real_path or not os.path.exists(real_path):
                continue
            with open(real_path, "r", encoding="utf-8") as f:
                content = f.read()

            session_reads.append(PresentedToolResult(
                name="read_file",
                arguments={"file_path": virtual_name},
                result=ToolResult(
                    content=content,
                    supersedes=False,
                    note=f"session-start read: {virtual_name}",
                ),
            ))
        return session_reads

    @staticmethod
    def _render_lines(lines: List[str], numbered: bool) -> str:
        if not numbered:
            return "".join(lines)
        return "".join(f"{i + 1:6d} | {line}" for i, line in enumerate(lines))

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        if file_path not in self.config.file_mappings:
            return self._error_response(
                f"File '{file_path}' does not exist. Readable files are: {self._readable_list()}"
            )

        if not self.is_readable(file_path):
            return self._error_response(
                f"File '{file_path}' is not readable. Readable files are: {self._readable_list()}"
            )

        real_path = self.config.file_mappings[file_path]
        if not os.path.exists(real_path):
            return self._error_response(
                f"File '{file_path}' does not exist yet. Use update_lines to create it."
            )

        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines(keepends=True)
        rendered = self._render_lines(lines, include_line_numbers)
        view_name = "numbered" if include_line_numbers else "plain"
        note = f"{file_path} ({len(lines)} lines, {view_name} view)"

        return [ToolResult(
            content=rendered,
            supersedes=False,
            note=note,
        )]

    def search_files(self, path: VirtualName = ".", pattern: str = "",
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        if not pattern:
            return self._error_response("Missing required parameter: pattern")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return self._error_response(f"Invalid regex pattern: {e}")

        clean_path = "." if path in ("/", "") else path

        if clean_path != ".":
            if clean_path not in self.config.file_mappings:
                return self._error_response(
                    f"Path '{clean_path}' does not exist. Readable files are: {self._readable_list()}"
                )
            if not self.is_readable(clean_path):
                return self._error_response(
                    f"Path '{clean_path}' is not readable. Readable files are: {self._readable_list()}"
                )

        if limit is not None and (limit < 1 or limit > self.config.search_result_limit):
            return self._error_response(
                f"limit must be between 1 and {self.config.search_result_limit}; got {limit}"
            )

        raw_matches = self._perform_search(clean_path, pattern)
        rendered_matches = raw_matches

        total_matches = len(rendered_matches)
        start_offset = 0 if offset is None else offset

        if limit is None:
            if total_matches > self.config.search_result_limit:
                return self._error_response(
                    f"Search produced {total_matches} matches, which exceeds the limit of {self.config.search_result_limit}. "
                    f"Please refine your pattern or use offset and limit (e.g. limit={self.config.search_result_limit}, offset=0) to paginate."
                )
            selected = rendered_matches[start_offset:]
            remaining = 0
            next_offset = None
        else:
            selected = rendered_matches[start_offset:start_offset + limit]
            remaining = max(0, total_matches - (start_offset + len(selected)))
            next_offset = (start_offset + len(selected)) if remaining > 0 else None

        if not selected:
            content = "No matches found."
        else:
            formatted: List[str] = []
            for virt, line_text in selected:
                formatted.append(f"{virt}: {line_text}")
            content = "\n".join(formatted)

        notes = [f"{len(selected)} of {total_matches} matches shown"]
        if remaining > 0 and next_offset is not None:
            notes.append(f"{remaining} remaining; continue with offset={next_offset}")
        note = "; ".join(notes)

        return [ToolResult(content=content, supersedes=False, note=note)]

    def _perform_search(self, path: str, pattern: str) -> List[Tuple[str, str]]:
        regex = re.compile(pattern)
        matches: List[Tuple[str, str]] = []

        if path == ".":
            for virt in sorted(self.config.readable_paths):
                real = self.config.file_mappings.get(virt)
                if real and os.path.exists(real):
                    with open(real, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            if regex.search(line):
                                matches.append((virt, line.rstrip("\r\n")))
        else:
            real = self.config.file_mappings.get(path)
            if real and os.path.exists(real):
                with open(real, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if regex.search(line):
                            matches.append((path, line.rstrip("\r\n")))
        return matches

    def sanitize_paths(self, text: str) -> str:
        result = text
        for real_path in self._real_paths_sorted:
            virtual = self._real_to_virtual[real_path]
            result = result.replace(real_path, virtual)
        return result

    def _create_tool_definition(self, name: str, description: str,
                                properties: Dict[str, Any],
                                required: Optional[List[str]] = None) -> ToolDefinition:
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required is not None:
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
        return ToolFailure(value=self._virtualize_paths(error_message))

    def _readable_list(self) -> str:
        return ", ".join(sorted(self.config.readable_paths))

    def _virtualize_paths(self, message: str) -> str:
        return self.sanitize_paths(message)
