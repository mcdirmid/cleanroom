"""Sandbox interface and aggregated tool provider."""

from typing import Protocol, TypeAlias, Sequence, Mapping, Optional
from dataclasses import dataclass
from .tool_provider import ToolProvider, ToolResult
from .virtual_file_name import VirtualFileMapping
from .file_reader import ReadOnlyFile, ReadWriteFile, SessionStartRead
from .file_editor import FileTemplate
from .guide_delivery import TaskGuide
from .run_control import RunControlConfig

StartupInteraction: TypeAlias = Sequence[ToolResult]


@dataclass(frozen=True)
class SandboxConfig:
    file_mappings: VirtualFileMapping
    read_only_files: Sequence[ReadOnlyFile]
    read_write_files: Sequence[ReadWriteFile]
    templates: Mapping[ReadWriteFile, FileTemplate]
    guide: Optional[TaskGuide] = None
    step_mode_guide_name: Optional[str] = None
    run_control: Optional[RunControlConfig] = None
    search_result_limit: Optional[int] = None


class Sandbox(ToolProvider, Protocol):
    def get_session_start_reads(self) -> Sequence[SessionStartRead]:
        ...

    def get_startup_interaction(self) -> StartupInteraction:
        ...

    def materialize_startup_templates(self) -> None:
        ...

    def has_file_modifications(self) -> bool:
        ...


class SandboxFactory(Protocol):
    def create_sandbox(self, config: SandboxConfig) -> Sandbox:
        ...
