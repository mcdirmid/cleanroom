# lib/sandbox.py
"""
Interface definitions for the LLS Sandbox.

The sandbox is a facade: it composes the read machinery (file_reader),
the write machinery (file_editor), the step-mode guide delivery (guide_delivery),
and the verification and termination rules (run_control) into a single tool surface.
"""

from typing import List, Optional, Protocol
from dataclasses import dataclass, field
from .tool_provider import (
    ToolDefinition,
    PresentedToolResult,
    ToolCallOutcome,
)
from .file_reader import (
    FileMapping,
    FilePath,
    FileReader,
    FileReaderConfig,
    ReadablePaths,
    SearchResultLimit,
    VirtualName,
)
from .file_editor import (
    FileEditor,
    FileEditorConfig,
    TemplateMapping,
    WritablePaths,
    WriteOccurred,
)
from .run_control import (
    Blame,
    BlameTarget,
    BlameTargets,
    Feedback,
    VerificationCallback,
)


@dataclass
class SandboxConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    session_start_reads_enabled: bool = True
    guide: Optional[VirtualName] = None
    step_sections_enabled: bool = True
    feedback_pending: bool = False
    templates: TemplateMapping = field(default_factory=dict)
    verification_callback: VerificationCallback = None


class Sandbox(Protocol):
    def get_tool_definitions(self) -> List[ToolDefinition]:
        ...

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        ...

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        ...

    def replace(self, file_path: VirtualName, old_str: str, new_str: str,
                expect_multiple: bool = False) -> ToolCallOutcome:
        ...

    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                     new_str: str) -> ToolCallOutcome:
        ...

    def search_files(self, path: VirtualName = ".", pattern: str = "",
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        ...

    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome:
        ...

    def fail(self) -> ToolCallOutcome:
        ...

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        ...

    def get_write_occurred(self) -> WriteOccurred:
        ...
