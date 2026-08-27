"""
Implementation of the Sandbox Protocol per sandbox_impl.md.

Provides file-read/write tools, session-start reads, step-mode guide delivery,
verification delegation, and termination via advance/fail/blame.
"""

from __future__ import annotations

import os
import re
from typing import TypeAlias, Literal
from dataclasses import dataclass
from difflib import unified_diff

from sandbox import (
    SandboxConfig,
    VirtualName,
    FilePath,
    WriteOccurred,
)
from tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolCallOutcome,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
)
from dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from dag_storage import NodeMessage

NodeId: TypeAlias = str

DiffSizeLimit: TypeAlias = int

_DEFAULT_DIFF_SIZE_LIMIT: int = 1000
_DEFAULT_SOFT_BOUND: int = 200
_DEFAULT_HARD_BOUND: int = 500
_GRACE: int = 4
_FAILURE_VALUE: str = "Task failed"

class SandboxImpl:
    def __init__(
        self,
        config: SandboxConfig,
        diff_size_limit: DiffSizeLimit | None = None,
    ) -> None:
        """Configure the sandbox and initialize templates."""
        self._config = config
        self._file_mappings: dict[VirtualName, FilePath] = dict(config.file_mappings)
        self._readable_paths: set[VirtualName] = set(config.readable_paths)
        self._writable_paths: set[VirtualName] = set(config.writable_paths)
        self._blame_targets: dict[VirtualName, str] = {k: str(v) for k, v in config.blame_targets.items()} if config.blame_targets else {}  # type: ignore[assignment]
        self._session_start_reads_enabled: bool = config.session_start_reads_enabled
        self._step_mode: bool = config.step_sections_enabled
        self._feedback_pending: bool = config.feedback_pending
        self._templates: dict[VirtualName, str] = dict(config.templates)
        self._verification_callback = config.verification_callback
        self._diff_size_limit: int = (
            diff_size_limit if diff_size_limit is not None else _DEFAULT_DIFF_SIZE_LIMIT
        )
        self._search_result_limit: int = config.search_result_limit
        self._guide_virtual_name: VirtualName | None = config.guide
        self._write_occurred: bool = False
        self._view_modes: dict[VirtualName, bool] = {}

        # Per-run state (reset every run)
        self._snapshots: dict[VirtualName, str] = {}
        self._changed_files: set[VirtualName] = set()
        self._guide_content: str | None = None
        self._guide_summary: str | None = None
        self._step_sections: list[tuple[str, str]] = []
        self._step_section_pointer: int = 0
        self._soft_rejection_count: int = 0
        self._hard_rejection_count: int = 0

        # Initialize templates at config time (not a run write)
        self._initialize_templates()


    # ── Template initialization ──────────────────────────────────────
    def _initialize_templates(self) -> None:
        for virtual_name, template_content in self._templates.items():
            path = self._file_mappings.get(virtual_name)
            if path is None:
                continue
            if not os.path.exists(path):
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w") as f:
                    f.write(template_content)

    # ── Guide parsing ────────────────────────────────────────────────

    def _parse_guide(self) -> None:
        if self._guide_virtual_name is None:
            return
        path = self._file_mappings.get(self._guide_virtual_name)
        if path is None or not os.path.exists(path):
            return
        with open(path, "r") as f:
            self._guide_content = f.read()

        lines = self._guide_content.split("\n")
        if not lines:
            self._guide_summary = ""
            self._step_sections = []
            return

        summary_lines = [lines[0]]

        summary_start: int | None = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "## Summary":
                summary_start = i
                break

        if summary_start is not None:
            summary_lines.append(lines[summary_start])
            i = summary_start + 1
            while i < len(lines):
                if lines[i].startswith("## ") and lines[i].strip() != "## Summary":
                    break
                summary_lines.append(lines[i])
                i += 1
            self._guide_summary = "\n".join(summary_lines)
            self._step_sections = self._extract_step_sections(lines[i:])
        else:
            self._guide_summary = self._guide_content
            self._step_sections = []

    def _extract_step_sections(
        self, lines: list[str]
    ) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if line.startswith("## "):
                if current_heading is not None:
                    sections.append((current_heading, "\n".join(current_lines)))
                current_heading = line.strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_heading is not None:
            sections.append((current_heading, "\n".join(current_lines)))

        return sections

    def _build_guide_output(self, section_only: bool = False) -> str:
        parts: list[str] = []
        parts.append(self._guide_summary or "")
        parts.append("")
        parts.append("Ensure the following steps are complete:")
        if section_only and self._step_sections:
            heading, content = self._step_sections[self._step_section_pointer]
            parts.append("")
            parts.append(heading)
            parts.append(content)
        return "\n".join(parts)

    # ── Per-run helpers ──────────────────────────────────────────────

    def _start_run(self) -> None:
        self._write_occurred = False
        self._view_modes = {}
        self._snapshots = {}
        self._changed_files = set()
        self._soft_rejection_count = 0
        self._hard_rejection_count = 0
        self._step_section_pointer = 0
        self._parse_guide()

    def _capture_snapshot(self, virtual_name: VirtualName, path: FilePath) -> None:
        if virtual_name not in self._snapshots:
            with open(path, "r") as f:
                self._snapshots[virtual_name] = f.read()

    # ── Policy helpers ───────────────────────────────────────────────

    def _resolve_path(self, virtual_name: VirtualName) -> ToolFailure[str] | FilePath:
        path = self._file_mappings.get(virtual_name)
        if path is None:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{virtual_name}' is not in file_mappings. "
                    f"Writable paths: {list(self._writable_paths)}"
                ),
                type="tool_failure",
            )
        return path

    def _check_readable(self, virtual_name: VirtualName) -> ToolFailure[str] | None:
        if virtual_name not in self._file_mappings:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{virtual_name}' is not in file_mappings. "
                    f"Readable paths: {list(self._readable_paths)}"
                ),
                type="tool_failure",
            )
        if virtual_name not in self._readable_paths:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{virtual_name}' is not in readable_paths. "
                    f"Readable paths: {list(self._readable_paths)}"
                ),
                type="tool_failure",
            )
        return None

    def _check_writable(self, virtual_name: VirtualName) -> ToolFailure[str] | None:
        if virtual_name not in self._file_mappings:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{virtual_name}' is not in file_mappings. "
                    f"Writable paths: {list(self._writable_paths)}"
                ),
                type="tool_failure",
            )
        if virtual_name not in self._writable_paths:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{virtual_name}' is not in writable_paths. "
                    f"Writable paths: {list(self._writable_paths)}"
                ),
                type="tool_failure",
            )
        return None

    def _read_content(self, path: FilePath) -> str:
        with open(path, "r") as f:
            return f.read()

    def _write_content(self, path: FilePath, content: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def _make_tool_result(
        self, content: str, supersedes: bool, note: str = ""
    ) -> ToolResult:
        return ToolResult(
            content=content, supersedes=supersedes, note=note, type="tool_result"
        )

    def _make_injected_read(
        self, virtual_name: VirtualName, content: str, line_count: int
    ) -> PresentedToolResult:
        lines = content.split("\n")
        numbered = "\n".join(f"{i + 1} \u2502 {line}" for i, line in enumerate(lines))
        tool_result = self._make_tool_result(
            numbered, supersedes=True, note=f"{line_count} lines"
        )
        return PresentedToolResult(
            name="read_file",
            arguments={"file_path": virtual_name, "include_line_numbers": True},
            result=tool_result,
            type="presented_tool_result",
        )

    # ── Diff helpers ─────────────────────────────────────────────────

    def _compute_diff(self, virtual_name: VirtualName) -> str:
        path_result = self._resolve_path(virtual_name)
        if isinstance(path_result, ToolFailure):
            return ""
        path = path_result
        current = self._read_content(path)
        snapshot = self._snapshots.get(virtual_name, "")
        if snapshot == current:
            return ""
        diff_lines = list(
            unified_diff(
                snapshot.splitlines(keepends=True),
                current.splitlines(keepends=True),
                fromfile=f"a/{virtual_name}",
                tofile=f"b/{virtual_name}",
            )
        )
        diff_text = "".join(diff_lines)
        full_len = len(diff_text)
        limit = self._diff_size_limit
        if full_len > limit:
            diff_text = diff_text[:limit]
            diff_text += (
                f"\n... diff truncated: showing {limit} of {full_len} chars ..."
            )
        return diff_text

    def _build_diff_report(self) -> str:
        parts: list[str] = []
        for vn in sorted(self._changed_files):
            diff = self._compute_diff(vn)
            if diff:
                parts.append(f"=== {vn} ===\n{diff}")
        return "\n\n".join(parts)

    # ── Change-summary validation ────────────────────────────────────

    def _validate_changes(
        self, changes: list[dict[str, str]]
    ) -> TerminateAgentWithFailure[str] | str | None:
        # Determine truly changed files (content differs from snapshot)
        truly_changed: set[VirtualName] = set()
        for vn in self._changed_files:
            if vn in self._snapshots:
                path = self._file_mappings.get(vn)
                if path and os.path.exists(path):
                    current = self._read_content(path)
                    if current != self._snapshots[vn]:
                        truly_changed.add(vn)
            else:
                truly_changed.add(vn)

        if not changes:
            if truly_changed:
                return (
                    f"Run changed files but no changes provided. "
                    f"Changed files: {sorted(truly_changed)}"
                )
            return "no_change"

        # Check no entry names a file that actually didn't change
        net_out = True
        for entry in changes:
            file_name = entry.get("file")
            if file_name and file_name in truly_changed:
                net_out = False
                break

        if net_out:
            return (
                "The run net-changed nothing (every written file's current content "
                "equals its run-start content). Call advance() with no changes to report no change."
            )

        for entry in changes:
            file_name = entry.get("file")
            summary = entry.get("summary")
            if not file_name or not summary:
                return "Entry missing 'file' or 'summary' field."
            if file_name not in truly_changed:
                return (
                    f"Entry names '{file_name}' which the run did not change. "
                    f"Changed files: {sorted(truly_changed)}"
                )

        provided_files = {e.get("file", "") for e in changes}
        for vn in truly_changed:
            if vn not in provided_files:
                return (
                    f"Changed file '{vn}' not listed in changes. "
                    f"Changed files: {sorted(truly_changed)}"
                )

        for entry in changes:
            summary = entry["summary"]
            if len(summary) > _DEFAULT_HARD_BOUND:
                if self._hard_rejection_count >= _GRACE:
                    return TerminateAgentWithFailure(
                        value=(
                            f"Summary for '{entry['file']}' exceeds hard bound "
                            f"({_DEFAULT_HARD_BOUND} chars) after {self._hard_rejection_count} "
                            f"rejections. Run fails."
                        ),
                        type="terminate_failure",
                    )
                self._hard_rejection_count += 1
                return (
                    f"Summary for '{entry['file']}' exceeds hard bound "
                    f"({_DEFAULT_HARD_BOUND} chars). Shorten it."
                )
            elif len(summary) > _DEFAULT_SOFT_BOUND:
                if self._soft_rejection_count >= _GRACE:
                    self._soft_rejection_count = 0
                    self._hard_rejection_count = 0
                    continue
                self._soft_rejection_count += 1
                return (
                    f"Summary for '{entry['file']}' exceeds soft bound "
                    f"({_DEFAULT_SOFT_BOUND} chars). Shorten it."
                )

        self._soft_rejection_count = 0
        self._hard_rejection_count = 0
        return None

    # ── Tool definitions ─────────────────────────────────────────────

    def _base_tool_defs(self) -> list[ToolDefinition]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file's entire content using the virtual name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "include_line_numbers": {"type": "boolean"},
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace text in a file by content-based search and replace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "old_str": {"type": "string"},
                            "new_str": {"type": "string"},
                            "expect_multiple": {"type": "boolean"},
                        },
                        "required": ["file_path", "old_str", "new_str"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "replace_lines",
                    "description": "Replace, delete, or insert lines by 1-indexed range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"},
                            "new_str": {"type": "string"},
                        },
                        "required": ["file_path", "start_line", "end_line", "new_str"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for a pattern in files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "pattern": {"type": "string"},
                            "offset": {"type": "integer"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["path", "pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "advance",
                    "description": "Signal run completion or deliver step sections.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "changes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "file": {"type": "string"},
                                        "summary": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fail",
                    "description": "End the session in failure.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
        ]

    def _blame_tool_def(self) -> ToolDefinition:
        return {
            "type": "function",
            "function": {
                "name": "blame",
                "description": "Signal termination with blame.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blames": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target": {"type": "string"},
                                    "feedback": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["blames"],
                },
            },
        }

    # ── Sandbox Protocol methods ─────────────────────────────────────

    def get_tool_definitions(self) -> list[ToolDefinition]:
        defs = self._base_tool_defs()
        if self._step_mode and self._guide_virtual_name is not None:
            if self._step_sections and self._step_section_pointer < len(self._step_sections):
                for d in defs:
                    if d["function"]["name"] == "advance":
                        props = d["function"]["parameters"]["properties"]
                        if "changes" in props:
                            del props["changes"]
                        break
        if self._blame_targets:
            defs.append(self._blame_tool_def())
        return defs

    def get_session_start_reads(self) -> list[PresentedToolResult]:
        self._start_run()
        results: list[PresentedToolResult] = []
        read_only = sorted(
            vn for vn in self._readable_paths if vn not in self._writable_paths
        )
        if self._step_mode and self._guide_virtual_name is not None:
            read_only = [vn for vn in read_only if vn != self._guide_virtual_name]
        if self._session_start_reads_enabled:
            for vn in read_only:
                path = self._file_mappings.get(vn)
                if path is None or not os.path.exists(path):
                    continue
                if not os.path.isfile(path):
                    continue
                content = self._read_content(path)
                tool_result = self._make_tool_result(content, supersedes=False, note="")
                presented = PresentedToolResult(
                    name="read_file",
                    arguments={"file_path": vn},
                    result=tool_result,
                    type="presented_tool_result",
                )
                results.append(presented)
        if self._step_mode and self._guide_content is not None and self._step_section_pointer < len(self._step_sections):
            guide_output = self._build_guide_output(section_only=False)
            tool_result = self._make_tool_result(guide_output, supersedes=True, note="")
            presented = PresentedToolResult(
                name="advance",
                arguments={},
                result=tool_result,
                type="presented_tool_result",
            )
            results.append(presented)
        return results

    def read_file(
        self,
        file_path: VirtualName,
        include_line_numbers: bool = False,
    ) -> ToolCallOutcome:
        # Step mode: reject reads of the guide
        if self._step_mode and file_path == self._guide_virtual_name:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{file_path}' is the step-mode guide and is not readable. "
                    f"Readable paths: {list(self._readable_paths)}"
                ),
                type="tool_failure",
            )
        read_error = self._check_readable(file_path)
        if read_error is not None:
            return read_error
        path = self._resolve_path(file_path)
        if isinstance(path, ToolFailure):
            return path
        if include_line_numbers and file_path not in self._writable_paths:
            return ToolFailure[str](
                value="Parameter error: include_line_numbers=True is only allowed for writable files.",
                type="tool_failure",
            )
        if file_path in self._writable_paths and not include_line_numbers and os.path.exists(path):
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{file_path}' is a writable file that already exists. "
                    f"Call read_file(file_path='{file_path}', include_line_numbers=True)."
                ),
                type="tool_failure",
            )
        content = self._read_content(path)
        line_count = len(content.split("\n"))
        if include_line_numbers:
            lines = content.split("\n")
            numbered = "\n".join(f"{i + 1} \u2502 {line}" for i, line in enumerate(lines))
            content = numbered
            self._view_modes[file_path] = True
            note = f"{line_count} lines (line-numbered view)"
        else:
            note = f"{line_count} lines"
        tool_result = self._make_tool_result(
            content,
            supersedes=file_path in self._writable_paths,
            note=note,
        )
        return [tool_result]

    def edit_file(
        self,
        file_path: VirtualName,
        old_str: str,
        new_str: str,
        expect_multiple: bool = False,
    ) -> ToolCallOutcome:
        check_error = self._check_writable(file_path)
        path = self._resolve_path(file_path)
        if isinstance(path, ToolFailure):
            return path
        if not os.path.exists(path):
            return ToolFailure[str](
                value=f"File '{file_path}' does not exist. Edits modify existing files only.",
                type="tool_failure",
            )
        if not old_str:
            return ToolFailure[str](
                value="Parameter error: old_str must be non-empty.",
                type="tool_failure",
            )
        if len(old_str) > 100 or len(new_str) > 100:
            return ToolFailure[str](
                value=(
                    f"Parameter error: old_str or new_str exceeds 100 characters. "
                    f"Use replace_lines for larger edits."
                ),
                type="tool_failure",
            )
        if old_str == new_str:
            return ToolFailure[str](
                value="Parameter error: old_str and new_str are identical. The edit would change nothing.",
                type="tool_failure",
            )
        content = self._read_content(path)
        if old_str not in content:
            return ToolFailure[str](
                value=f"Search string not found in '{file_path}'.",
                type="tool_failure",
            )
        if not expect_multiple:
            if content.count(old_str) > 1:
                return ToolFailure[str](
                    value=(
                        f"Multiple occurrences of '{old_str}' found in '{file_path}'. "
                        f"Use expect_multiple=True or a narrower search string."
                    ),
                    type="tool_failure",
                )
        if expect_multiple:
            new_content = content.replace(old_str, new_str)
            count = content.count(old_str)
        else:
            new_content = content.replace(old_str, new_str, 1)
            count = 1
        self._capture_snapshot(file_path, path)
        self._write_content(path, new_content)
        self._write_occurred = True
        self._view_modes[file_path] = False
        write_confirmation = self._make_tool_result(
            f"Replaced {count} occurrence(s) of '{old_str}' in '{file_path}'.",
            supersedes=True,
            note=f"Replaced {count} occurrence(s) of '{old_str}' in '{file_path}'",
        )
        injected = self._make_injected_read(file_path, new_content, len(new_content.split("\n")))
        return [write_confirmation, injected]

    def replace_lines(
        self,
        file_path: VirtualName,
        start_line: int,
        end_line: int,
        new_str: str,
    ) -> ToolCallOutcome:
        path = self._resolve_path(file_path)
        if isinstance(path, ToolFailure):
            return path
        if not os.path.exists(path):
            return ToolFailure[str](
                value=f"File '{file_path}' does not exist. Edits modify existing files only.",
                type="tool_failure",
            )
        if file_path not in self._view_modes or not self._view_modes[file_path]:
            return ToolFailure[str](
                value=(
                    f"Policy violation: '{file_path}' is not in line-numbered view. "
                    f"Call read_file(file_path='{file_path}', include_line_numbers=True) first."
                ),
                type="tool_failure",
            )
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            return ToolFailure[str](
                value="Parameter error: start_line and end_line must be integers.",
                type="tool_failure",
            )
        content = self._read_content(path)
        lines = content.split("\n")
        line_count = len(lines)
        if start_line < 1 or start_line > line_count + 1:
            return ToolFailure[str](
                value=f"Parameter error: start_line {start_line} out of bounds (1-{line_count + 1}).",
                type="tool_failure",
            )
        if end_line < 0 or end_line > line_count:
            return ToolFailure[str](
                value=f"Parameter error: end_line {end_line} out of bounds (0-{line_count}).",
                type="tool_failure",
            )
        new_lines = lines[: start_line - 1] + (new_str.split("\n") if new_str else []) + lines[end_line:]
        new_content = "\n".join(new_lines)
        self._capture_snapshot(file_path, path)
        self._write_content(path, new_content)
        self._write_occurred = True
        self._view_modes[file_path] = False
        write_confirmation = self._make_tool_result(
            f"Replaced lines {start_line}-{end_line} in '{file_path}'.",
            supersedes=True,
            note=f"Replaced lines {start_line}-{end_line} in '{file_path}'",
        )
        injected = self._make_injected_read(file_path, new_content, len(new_content.split("\n")))
        return [write_confirmation, injected]

    def search_files(
        self,
        path: VirtualName,
        pattern: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> ToolCallOutcome:
        read_error = self._check_readable(path)
        if read_error is not None:
            return read_error
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            return ToolFailure[str](
                value=f"Parameter error: invalid regex pattern '{pattern}': {e}",
                type="tool_failure",
            )
        if offset is not None and offset < 0:
            return ToolFailure[str](
                value="Parameter error: offset must be non-negative.",
                type="tool_failure",
            )
        if limit is not None:
            if limit <= 0:
                return ToolFailure[str](
                    value="Parameter error: limit must be positive.",
                    type="tool_failure",
                )
            if limit > self._search_result_limit:
                return ToolFailure[str](
                    value=f"Parameter error: limit {limit} exceeds search result limit {self._search_result_limit}.",
                    type="tool_failure",
                )
        path_result = self._resolve_path(path)
        if isinstance(path_result, ToolFailure):
            return path_result
        file_path = path_result
        all_matches: list[str] = []
        writable_suppressed = 0
        writable_paths_set = set()
        for vn in self._writable_paths:
            vp = self._file_mappings.get(vn)
            if vp:
                writable_paths_set.add(os.path.abspath(vp))
        for root, dirs, files in os.walk(file_path):
            for fname in sorted(files):
                full = os.path.abspath(os.path.join(root, fname))
                rel = os.path.relpath(full, file_path)
                is_writable = full in writable_paths_set
                try:
                    with open(full, "r") as f:
                        file_content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue
                for i, line in enumerate(file_content.split("\n"), 1):
                    if compiled.search(line):
                        match_text = f"{rel}:{i}:{line}"
                        if is_writable:
                            writable_suppressed += 1
                        else:
                            all_matches.append(match_text)
        total = len(all_matches)
        start = offset if offset is not None else 0
        if limit is not None:
            rendered = all_matches[start : start + limit]
        else:
            rendered = all_matches[start:]
        if limit is None and total > self._search_result_limit:
            return ToolFailure[str](
                value=f"Parameter error: {total} rendered matches exceed search result limit {self._search_result_limit}. Use limit and offset pagination.",
                type="tool_failure",
            )
        remaining = total - (start + len(rendered))
        note_parts = [
            f"Total rendered matches: {total}",
            f"Matches remaining: {remaining}",
            f"Offset: {start}",
        ]
        if writable_suppressed > 0:
            note_parts.append(f"Suppressed matches in writable files: {writable_suppressed}")
        note = "; ".join(note_parts)
        content = "\n".join(rendered)
        tool_result = self._make_tool_result(content, supersedes=False, note=note)
        return [tool_result]

    def advance(
        self,
        changes: list[dict[str, str]] = [],
    ) -> ToolCallOutcome:
        self._start_run()
        # Step mode
        if self._step_mode and self._guide_content is not None and self._step_sections:
            if self._step_section_pointer < len(self._step_sections):
                # Passing verification with step sections remaining → next section
                if self._verification_callback is not None:
                    try:
                        passed, message = self._verification_callback()
                    except Exception as e:
                        return ToolFailure[str](
                            value=f"Verification error: {e}",
                            type="tool_failure",
                        )
                    if not passed:
                        guide_output = self._build_guide_output(section_only=False)
                        error_output = f"{guide_output}\n\nVerification failed: {message}"
                        tool_result = self._make_tool_result(
                            error_output, supersedes=True, note="Verification failed."
                        )
                        return [tool_result]
                guide_output = self._build_guide_output(section_only=True)
                tool_result = self._make_tool_result(guide_output, supersedes=True, note="")
                self._step_section_pointer += 1
                return [tool_result]
            else:
                # No step sections remaining — fall through to termination logic
                pass
        # Determine truly changed files (content differs from snapshot)
        truly_changed: set[VirtualName] = set()
        for vn in self._changed_files:
            if vn in self._snapshots:
                path = self._file_mappings.get(vn)
                if path and os.path.exists(path):
                    current = self._read_content(path)
                    if current != self._snapshots[vn]:
                        truly_changed.add(vn)
            else:
                truly_changed.add(vn)

        # No-change case
        if not truly_changed:
            if self._feedback_pending:
                return ToolFailure[str](
                    value="feedback_pending is set. The agent must change files, blame, or fail.",
                    type="tool_failure",
                )
            return TerminateAgentWithSuccess(
                value=NoChangeResult(type="no_change"),
                type="terminate_success",
            )
        validation = self._validate_changes(changes)
        if isinstance(validation, TerminateAgentWithFailure):
            return validation
        if validation is not None:
            return ToolFailure[str](
                value=validation,
                type="tool_failure",
            )
        # All changes valid — build ChangeResult
        messages: list[NodeMessage] = []
        for entry in changes:
            messages.append(
                NodeMessage(kind="change", text=f"{entry['file']}: {entry['summary']}")
            )
        return TerminateAgentWithSuccess(
            value=ChangeResult(messages=messages, type="change"),
            type="terminate_success",
        )

    def fail(self) -> ToolCallOutcome:
        return TerminateAgentWithFailure(value=_FAILURE_VALUE, type="terminate_failure")

    def blame(self, blames: list[tuple[str, str]]) -> ToolCallOutcome:
        self._start_run()
        if not self._blame_targets:
            return ToolFailure[str](
                value="Blame targets not configured. The blame tool is not available.",
                type="tool_failure",
            )
        if not blames:
            return ToolFailure[str](
                value="Empty blames list. Provide at least one blame pair.",
                type="tool_failure",
            )
        messages: list[tuple[str, NodeMessage]] = []
        for target, feedback in blames:
            if target not in self._blame_targets:
                return ToolFailure[str](
                    value=f"Invalid blame target '{target}'. Must be one of: {list(self._blame_targets.keys())}",
                    type="tool_failure",
                )
            node_id = self._blame_targets[target]
            messages.append((node_id, NodeMessage(kind="feedback", text=feedback)))
        return TerminateAgentWithSuccess(
            value=FeedbackResult(messages=messages, type="feedback"),
            type="terminate_success",
        )

    def get_write_occurred(self) -> WriteOccurred:
        self._start_run()
        return self._write_occurred
