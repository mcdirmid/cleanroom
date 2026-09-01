"""File reader interface and configuration."""

from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from .tool_provider import Tool, ToolProvider, ToolResult, ToolFailure
from .virtual_file_name import (
    VirtualFileName,
    VirtualFileMapping,
    UnsanitizedContent,
    SanitizedContent,
)

HostPath: TypeAlias = str
ReadOnlyFile: TypeAlias = VirtualFileName
ReadWriteFile: TypeAlias = VirtualFileName


@dataclass(frozen=True)
class FileReaderConfig:
    read_only_files: Sequence[ReadOnlyFile]
    read_write_files: Sequence[ReadWriteFile]
    file_mappings: VirtualFileMapping
    step_mode_guide: Optional[VirtualFileName] = None
    search_result_limit: Optional[int] = None


SessionStartRead: TypeAlias = ToolResult


class FileReader(ToolProvider, Protocol):
    def get_read_tool(self) -> Tool:
        ...

    def get_search_tool(self) -> Tool:
        ...

    def get_session_start_reads(self) -> Sequence[SessionStartRead]:
        ...

    def sanitize_paths(self, content: UnsanitizedContent) -> SanitizedContent:
        ...


class FileReaderFactory(Protocol):
    def create_file_reader(self, config: FileReaderConfig) -> FileReader:
        ...
