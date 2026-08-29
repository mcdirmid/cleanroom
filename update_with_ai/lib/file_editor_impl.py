# lib/file_editor_impl.py
"""
Implementation of the LLS file_editor interface.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from .file_reader import FileReader, VirtualName
from .file_editor import (
    FileEditor,
    FileEditorConfig,
    WriteOccurred,
)
from .tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolCallOutcome,
    ToolFailure,
)


class FileEditorImpl(FileEditor):
    """
    Implementation of the LLS FileEditor interface.
    """

    MAX_EDIT_LENGTH = 200

    def __init__(self, config: FileEditorConfig, file_reader: FileReader):
        self.config = config
        self.file_reader = file_reader
        self.write_occurred: WriteOccurred = False

        self._file_views: Dict[VirtualName, bool] = {}
        self._changed_files: List[str] = []
        self._pre_write_snapshots: Dict[VirtualName, Optional[str]] = {}

        # Template initialization
        for virtual, content in self.config.templates.items():
            real_path = self.file_reader.resolve_path(virtual)
            if real_path is None or os.path.exists(real_path):
                continue
            parent_dir = os.path.dirname(real_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(real_path, "w", encoding="utf-8") as f:
                f.write(content)

    def is_writable(self, file_path: VirtualName) -> bool:
        return file_path in self.config.writable_paths

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return [
            self._create_tool_definition(
                "replace",
                "Replace short text in a file (content-based search and replace: takes file_path, old_str, new_str, expect_multiple). Only for short one-line phrase replacements — old_str and new_str are strictly limited to at most 200 characters each. For multi-line edits, functions, classes, or block updates, always use update_lines instead (which operates on line ranges and requires include_line_numbers=True). Replaces exactly one occurrence of old_str with new_str; fails when old_str is absent or matches more than once unless expect_multiple=True (then replaces all occurrences). After an edit the file is automatically re-read with line numbers.",
                {
                    "file_path": {"type": "string", "description": "Virtual path to the file"},
                    "old_str": {"type": "string", "description": "Exact text to find"},
                    "new_str": {"type": "string", "description": "Replacement text"},
                    "expect_multiple": {"type": "boolean", "description": "Allow multiple matches and replace all of them", "default": False}
                },
                required=["file_path", "old_str", "new_str"]
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
                required=["file_path", "start_line", "end_line", "new_str"]
            )
        ]

    def _snapshot(self, file_path: VirtualName, real_path: str) -> None:
        if file_path not in self._pre_write_snapshots:
            if os.path.exists(real_path):
                with open(real_path, "r", encoding="utf-8") as f:
                    self._pre_write_snapshots[file_path] = f.read()
            else:
                self._pre_write_snapshots[file_path] = None

    def _apply_write(self, file_path: VirtualName, real_path: str, new_content: str, status: str) -> ToolCallOutcome:
        self._snapshot(file_path, real_path)
        self.write_occurred = True
        self._file_views[file_path] = False

        if file_path not in self._changed_files:
            self._changed_files.append(file_path)

        parent_dir = os.path.dirname(real_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(real_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        confirmation = ToolResult(
            content={"status": status, "file": file_path},
            supersedes=True,
            note=f"write confirmation: {file_path}",
        )
        injected = self._injected_read(file_path)
        return [confirmation, injected]

    def _injected_read(self, file_path: VirtualName) -> PresentedToolResult:
        real_path = self.file_reader.resolve_path(file_path)
        content = ""
        if real_path and os.path.exists(real_path):
            with open(real_path, "r", encoding="utf-8") as f:
                content = f.read()

        lines = content.splitlines(keepends=True)
        rendered = "".join(f"{i + 1:6d} | {line}" for i, line in enumerate(lines))
        self._file_views[file_path] = True

        return PresentedToolResult(
            name="read_file",
            arguments={"file_path": file_path, "include_line_numbers": True},
            result=ToolResult(
                content=rendered,
                supersedes=True,
                note=f"injected re-read: {file_path} ({len(lines)} lines, numbered view)",
            ),
        )

    def replace(self, file_path: VirtualName, old_str: str, new_str: str,
                expect_multiple: bool = False) -> ToolCallOutcome:
        if len(old_str) > self.MAX_EDIT_LENGTH or len(new_str) > self.MAX_EDIT_LENGTH:
            return ToolFailure(
                value=f"replace supports strings up to {self.MAX_EDIT_LENGTH} chars (got old_str={len(old_str)}, new_str={len(new_str)}). Use update_lines instead."
            )

        if not old_str:
            return ToolFailure(value="old_str cannot be empty. Use update_lines to insert content.")

        if old_str == new_str:
            return ToolFailure(value="old_str and new_str are identical; no changes to make.")

        real_path = self.file_reader.resolve_path(file_path)
        if not real_path:
            return ToolFailure(value=f"File '{file_path}' does not exist. Writable files are: {self._writable_list()}")

        if not self.is_writable(file_path):
            return ToolFailure(value=f"File '{file_path}' is read-only. Writable files are: {self._writable_list()}")

        if not os.path.exists(real_path):
            return ToolFailure(value=f"File '{file_path}' does not exist yet. Use update_lines to create it.")

        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()

        count = content.count(old_str)
        if count == 0:
            return ToolFailure(value=f"old_str not found in '{file_path}'. Check exact spelling and whitespace.")

        if count > 1 and not expect_multiple:
            return ToolFailure(
                value=f"old_str matches {count} times in '{file_path}'. Set expect_multiple=True to replace all, or use update_lines."
            )

        new_content = content.replace(old_str, new_str)
        suffix = "s" if count > 1 else ""
        status = f"replaced {count} occurrence{suffix}"
        return self._apply_write(file_path, real_path, new_content, status)

    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                     new_str: str) -> ToolCallOutcome:
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            return ToolFailure(value="start_line and end_line must be integers")

        real_path = self.file_reader.resolve_path(file_path)
        if not real_path:
            return ToolFailure(value=f"File '{file_path}' does not exist. Writable files are: {self._writable_list()}")

        if not self.is_writable(file_path):
            return ToolFailure(value=f"File '{file_path}' is read-only. Writable files are: {self._writable_list()}")

        file_exists = os.path.exists(real_path)
        if file_exists and not self._file_views.get(file_path, False):
            return ToolFailure(
                value=f"update_lines requires line-numbered view. Call read_file('{file_path}', include_line_numbers=True) first."
            )

        lines: List[str] = []
        has_trailing_newline = True
        if file_exists:
            with open(real_path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines(keepends=True)
            has_trailing_newline = content.endswith("\n") if content else True

        total_lines = len(lines)

        if start_line < 1 or start_line > total_lines + 1:
            return ToolFailure(value=f"start_line {start_line} out of range (file has {total_lines} lines)")

        if end_line < 0 or end_line > total_lines:
            return ToolFailure(value=f"end_line {end_line} out of range (file has {total_lines} lines)")

        new_lines: List[str] = []
        if new_str:
            new_lines = new_str.splitlines(keepends=True)
            if has_trailing_newline and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"

        if start_line > end_line:
            # Insertion before start_line
            insert_idx = start_line - 1
            updated = lines[:insert_idx] + new_lines + lines[insert_idx:]
            status = f"inserted {len(new_lines)} lines before line {start_line}"
        else:
            # Range replacement
            start_idx = start_line - 1
            end_idx = end_line
            updated = lines[:start_idx] + new_lines + lines[end_idx:]
            status = f"updated lines {start_line}-{end_line}"

        new_content = "".join(updated)
        return self._apply_write(file_path, real_path, new_content, status)

    def get_write_occurred(self) -> WriteOccurred:
        return self.write_occurred

    def get_changed_files(self) -> List[VirtualName]:
        return list(self._changed_files)

    def get_run_start_snapshot(self, file_path: VirtualName) -> Optional[str]:
        return self._pre_write_snapshots.get(file_path)

    def get_current_content(self, file_path: VirtualName) -> Optional[str]:
        real_path = self.file_reader.resolve_path(file_path)
        if not real_path or not os.path.exists(real_path):
            return None
        with open(real_path, "r", encoding="utf-8") as f:
            return f.read()

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

    def _writable_list(self) -> str:
        return ", ".join(sorted(self.config.writable_paths))
