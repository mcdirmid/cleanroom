# lib/file_editor.py
"""
Interface definitions for the LLS FileEditor.
"""

from typing import Dict, List, Optional, Protocol, TypeAlias
from dataclasses import dataclass, field
from .file_reader import VirtualName
from .tool_provider import (
    ToolDefinition,
    ToolCallOutcome,
)

WritablePaths: TypeAlias = List[VirtualName]
TemplateMapping: TypeAlias = Dict[VirtualName, str]
WriteOccurred: TypeAlias = bool


@dataclass
class FileEditorConfig:
    writable_paths: WritablePaths
    templates: TemplateMapping = field(default_factory=dict)


class FileEditor(Protocol):
    def get_tool_definitions(self) -> List[ToolDefinition]:
        ...

    def replace(self, file_path: VirtualName, old_str: str, new_str: str,
                expect_multiple: bool = False) -> ToolCallOutcome:
        ...

    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                     new_str: str) -> ToolCallOutcome:
        ...

    def get_write_occurred(self) -> WriteOccurred:
        ...

    def get_changed_files(self) -> List[VirtualName]:
        ...

    def get_run_start_snapshot(self, file_path: VirtualName) -> Optional[str]:
        ...

    def get_current_content(self, file_path: VirtualName) -> Optional[str]:
        ...

    def is_writable(self, file_path: VirtualName) -> bool:
        ...
