"""File reader implementation with line numbering and path sanitization."""

import os
import re
from typing import Sequence, List, Dict, Tuple, Optional
from .tool_provider import (
    Tool,
    ToolMetadata,
    ToolResult,
    ToolFailure,
    ToolOutcome,
    ToolArguments,
)
from .file_reader import (
    FileReader,
    FileReaderFactory,
    FileReaderConfig,
    SessionStartRead,
    UnsanitizedContent,
    SanitizedContent,
)


def _resolve_disk_path(path: str) -> Optional[str]:
    if not path:
        return None
    if os.path.isfile(path):
        return path
    ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")
    if ws:
        cand = os.path.join(ws, path)
        if os.path.isfile(cand):
            return cand
    runfiles = os.environ.get("RUNFILES_DIR") or os.environ.get("BAZEL_RUNFILES")
    if runfiles:
        for sub in ["", "_main"]:
            cand = os.path.join(runfiles, sub, path) if sub else os.path.join(runfiles, path)
            if os.path.isfile(cand):
                return cand
    return None


class FileReaderFactoryImpl(FileReaderFactory):
    def create_file_reader(self, config: FileReaderConfig) -> FileReader:
        return _FileReaderImpl(config)


class _FileReaderImpl(FileReader):
    def __init__(self, config: FileReaderConfig) -> None:
        self.config = config

    def get_read_tool(self) -> Tool:
        class ReadTool:
            def __init__(self, parent: _FileReaderImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="read_file",
                    purpose="Read content from a workspace file",
                    parameters_schema={
                        "file_name": "string",
                        "line_numbers": "boolean",
                    },
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                vname = str(arguments.get("file_name", "") or arguments.get("target_file", ""))
                line_numbers = arguments.get("line_numbers")
                line_numbers_bool = (line_numbers is True or str(line_numbers).strip().lower() == "true")

                if self.parent.config.step_mode_guide:
                    if vname == self.parent.config.step_mode_guide or vname == os.path.basename(self.parent.config.step_mode_guide):
                        return ToolFailure(feedback=f"Guide {vname} is delivered progressively through advance() and cannot be read directly.")

                # Resolve host path
                readable_files = sorted(list(self.parent.config.file_mappings.keys())) if self.parent.config.file_mappings else sorted(list(self.parent.config.read_only_files) + list(self.parent.config.read_write_files))
                host_path = self.parent.config.file_mappings.get(vname)
                if not host_path:
                    if vname in self.parent.config.read_only_files or vname in self.parent.config.read_write_files:
                        host_path = vname
                    else:
                        return ToolFailure(feedback=f"File {vname} is not mapped or accessible. Available readable files: {readable_files}")

                is_rw = (vname in self.parent.config.read_write_files) or (host_path in self.parent.config.read_write_files)
                is_ro = (vname in self.parent.config.read_only_files) or (host_path in self.parent.config.read_only_files)

                if not is_rw and not is_ro:
                    return ToolFailure(feedback=f"File {vname} is not in declared read-only or read-write set. Available readable files: {readable_files}")

                if is_rw:
                    if not line_numbers_bool:
                        return ToolFailure(feedback=f"Reading read-write file {vname} requires line_numbers=True")
                elif is_ro:
                    if line_numbers_bool:
                        return ToolFailure(feedback=f"Reading read-only file {vname} requires line_numbers=False or omitted")

                disk_path = _resolve_disk_path(host_path)
                if not disk_path:
                    return ToolFailure(feedback=f"File {vname} ({host_path}) not found on disk. Available readable files: {readable_files}")

                try:
                    with open(disk_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except Exception as e:
                    return ToolFailure(feedback=f"Error reading {vname}: {e}")

                if is_rw:
                    formatted_lines = [f"{i}: {line}" for i, line in enumerate(lines, start=1)]
                    content = "".join(formatted_lines)
                else:
                    content = "".join(lines)

                return ToolResult(content=content)

        return ReadTool(self)

    def get_search_tool(self) -> Tool:
        class SearchTool:
            def __init__(self, parent: _FileReaderImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="search_files",
                    purpose="Search regex patterns across workspace files",
                    parameters_schema={"pattern": "string"},
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                pattern_str = str(arguments.get("pattern", "") or arguments.get("query", ""))
                try:
                    regex = re.compile(pattern_str)
                except re.error as e:
                    return ToolFailure(feedback=f"Invalid regex pattern '{pattern_str}': {e}")

                results: List[str] = []
                # Search across all accessible files
                all_files: List[Tuple[str, bool]] = []
                for f in self.parent.config.read_write_files:
                    all_files.append((f, True))
                for f in self.parent.config.read_only_files:
                    all_files.append((f, False))

                for vname, is_rw in all_files:
                    host_path = self.parent.config.file_mappings.get(vname, vname)
                    disk_path = _resolve_disk_path(host_path)
                    if not disk_path:
                        continue
                    try:
                        with open(disk_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                    except Exception:
                        continue

                    if is_rw:
                        # Report match count on writable files
                        match_count = sum(1 for line in lines if regex.search(line))
                        if match_count > 0:
                            results.append(f"{vname}: {match_count} matches")
                    else:
                        # Report matching lines on read-only files
                        for i, line in enumerate(lines, start=1):
                            if regex.search(line):
                                results.append(f"{vname}:{i}: {line.rstrip()}")

                if self.parent.config.search_result_limit and len(results) > self.parent.config.search_result_limit:
                    results = results[:self.parent.config.search_result_limit]
                    results.append("... (results truncated)")

                return ToolResult(content="\n".join(results) if results else "No matches found")

        return SearchTool(self)

    def get_session_start_reads(self) -> Sequence[SessionStartRead]:
        reads: List[SessionStartRead] = []
        for vname in self.config.read_only_files:
            host_path = self.config.file_mappings.get(vname, vname)
            disk_path = _resolve_disk_path(host_path)
            if disk_path:
                try:
                    with open(disk_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    reads.append(SessionStartRead(content=content))
                except Exception:
                    pass
        return reads

    def sanitize_paths(self, content: UnsanitizedContent) -> SanitizedContent:
        # Sort host paths by length descending
        sorted_mappings = sorted(
            self.config.file_mappings.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
        res = content
        for vname, host_path in sorted_mappings:
            if host_path:
                res = res.replace(host_path, vname)
        return res

    def get_tools(self) -> Sequence[Tool]:
        return [self.get_read_tool(), self.get_search_tool()]
