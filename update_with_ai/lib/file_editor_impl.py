"""File editor implementation with text replacement and line updates."""

import os
from typing import Sequence
from .tool_provider import (
    Tool,
    ToolMetadata,
    ToolResult,
    ToolFailure,
    ToolOutcome,
    ToolArguments,
)
from .file_editor import FileEditor, FileEditorFactory, FileEditorConfig


def _resolve_write_disk_path(path: str) -> str:
    if os.path.isfile(path):
        return path
    ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")
    if ws:
        cand = os.path.join(ws, path)
        if os.path.isfile(cand) or os.path.isdir(os.path.dirname(cand)):
            return cand
    return path


class FileEditorFactoryImpl(FileEditorFactory):
    def create_file_editor(self, config: FileEditorConfig) -> FileEditor:
        return _FileEditorImpl(config)


class _FileEditorImpl(FileEditor):
    def __init__(self, config: FileEditorConfig) -> None:
        self.config = config
        self._modified = False

    def get_replacement_tool(self) -> Tool:
        class ReplacementTool:
            def __init__(self, parent: _FileEditorImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="replace",
                    purpose="Replace unique matching text in a read-write file",
                    parameters_schema={
                        "file_name": "string",
                        "target_text": "string",
                        "replacement_text": "string",
                    },
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                fname = str(arguments.get("file_name", "") or arguments.get("target_file", ""))
                host_path = self.parent.config.file_mappings.get(fname, fname)
                if fname not in self.parent.config.read_write_files and host_path not in self.parent.config.read_write_files:
                    return ToolFailure(feedback=f"File {fname} is not read-write")

                target_text = str(arguments.get("target_text", "") or arguments.get("target_content", ""))
                replacement_text = str(arguments.get("replacement_text", "") or arguments.get("replacement_content", ""))

                disk_path = _resolve_write_disk_path(host_path)
                if not os.path.isfile(disk_path):
                    return ToolFailure(feedback=f"File {fname} does not exist")

                with open(disk_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if len(target_text) > 100000:
                    return ToolFailure(feedback=f"Target text exceeds maximum replacement size limit (100,000 characters)")

                if target_text not in content:
                    return ToolFailure(feedback=f"Target text not found in {fname}")

                if content.count(target_text) > 1:
                    return ToolFailure(feedback=f"Target text matches multiple locations in {fname}")

                new_content = content.replace(target_text, replacement_text, 1)
                with open(disk_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                self.parent._modified = True
                return ToolResult(content=f"Replaced text in {fname}")

        return ReplacementTool(self)

    def get_line_update_tool(self) -> Tool:
        class LineUpdateTool:
            def __init__(self, parent: _FileEditorImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="update_lines",
                    purpose="Update or replace a range of lines in a read-write file",
                    parameters_schema={
                        "file_name": "string",
                        "start_line": "integer",
                        "end_line": "integer",
                        "replacement_text": "string",
                    },
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                fname = str(arguments.get("file_name", "") or arguments.get("target_file", ""))
                host_path = self.parent.config.file_mappings.get(fname, fname)
                if fname not in self.parent.config.read_write_files and host_path not in self.parent.config.read_write_files:
                    return ToolFailure(feedback=f"File {fname} is not read-write")

                disk_path = _resolve_write_disk_path(host_path)
                if not os.path.isfile(disk_path):
                    return ToolFailure(feedback=f"File {fname} does not exist")

                start_line = int(arguments.get("start_line", 1))
                end_line = int(arguments.get("end_line", 1))
                replacement = str(arguments.get("replacement_text", "") or arguments.get("replacement_content", ""))

                with open(disk_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                if start_line < 1 or start_line > len(lines) + 1:
                    return ToolFailure(feedback=f"Invalid start line {start_line} for file of length {len(lines)}")

                if start_line <= end_line:
                    if end_line > len(lines):
                        return ToolFailure(feedback=f"Invalid end line {end_line} for file of length {len(lines)}")
                    prefix = lines[:start_line - 1]
                    suffix = lines[end_line:]
                else:
                    # Insertion at start_line without replacing lines
                    prefix = lines[:start_line - 1]
                    suffix = lines[start_line - 1:]

                rep_lines = [l + "\n" if not l.endswith("\n") else l for l in replacement.splitlines()] if replacement else []

                new_lines = prefix + rep_lines + suffix
                with open(disk_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

                self.parent._modified = True
                return ToolResult(content=f"Updated lines in {fname}")

        return LineUpdateTool(self)

    def materialize_templates(self) -> None:
        for fname, template in self.config.templates.items():
            host_path = self.config.file_mappings.get(fname, fname)
            disk_path = _resolve_write_disk_path(host_path)
            if not os.path.exists(disk_path):
                os.makedirs(os.path.dirname(os.path.abspath(disk_path)), exist_ok=True)
                template_content = template
                tmpl_disk = _resolve_write_disk_path(template)
                if os.path.isfile(tmpl_disk):
                    try:
                        with open(tmpl_disk, "r", encoding="utf-8") as tf:
                            template_content = tf.read()
                    except Exception:
                        pass
                with open(disk_path, "w", encoding="utf-8") as f:
                    f.write(template_content)

    def has_file_modifications(self) -> bool:
        return self._modified

    def get_tools(self) -> Sequence[Tool]:
        return [self.get_replacement_tool(), self.get_line_update_tool()]
