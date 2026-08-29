# lib/file_reader.py
"""
Interface definitions for the LLS FileReader.
"""

from typing import Dict, List, Optional, Protocol, Tuple, TypeAlias
from dataclasses import dataclass
from .tool_provider import (
    ToolDefinition,
    PresentedToolResult,
    ToolCallOutcome,
)

VirtualName: TypeAlias = str
FilePath: TypeAlias = str
FileMapping: TypeAlias = Dict[VirtualName, FilePath]
ReadablePaths: TypeAlias = List[VirtualName]
SearchResultLimit: TypeAlias = int


@dataclass
class FileReaderConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    search_result_limit: SearchResultLimit = 5
    session_start_reads_enabled: bool = True


class FileReader(Protocol):
    def get_tool_definitions(self) -> List[ToolDefinition]:
        ...

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        ...

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        ...

    def search_files(self, path: VirtualName = ".", pattern: str = "",
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        ...

    def sanitize_paths(self, text: str) -> str:
        ...

    def resolve_path(self, file_path: VirtualName) -> Optional[str]:
        ...

    def is_readable(self, file_path: VirtualName) -> bool:
        ...
