"""File editor interface and configuration."""

from typing import Protocol, TypeAlias, Sequence, Mapping
from dataclasses import dataclass
from .tool_provider import Tool, ToolProvider, ToolFailure
from .file_reader import ReadWriteFile
from .virtual_file_name import VirtualFileMapping

FileTemplate: TypeAlias = str
TemplateMapping: TypeAlias = Mapping[ReadWriteFile, FileTemplate]


@dataclass(frozen=True)
class FileEditorConfig:
    read_write_files: Sequence[ReadWriteFile]
    file_mappings: VirtualFileMapping
    templates: TemplateMapping


class FileEditor(ToolProvider, Protocol):
    def get_replacement_tool(self) -> Tool:
        ...

    def get_line_update_tool(self) -> Tool:
        ...

    def materialize_templates(self) -> None:
        ...


class FileEditorFactory(Protocol):
    def create_file_editor(self, config: FileEditorConfig) -> FileEditor:
        ...
