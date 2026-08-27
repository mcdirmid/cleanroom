"""
Interface LLS: sandbox

The sandbox provides file-reading/writing tools and session-termination tools
to the agent loop. It resolves virtual file names to filesystem paths, enforces
read/write policies, manages file state (line-numbered views, injected reads),
handles templates, session-start reads, blame, and step mode.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar, Generic, TypeAlias
from dataclasses import dataclass, field
from tool_provider import ToolDefinition, ToolResult, PresentedToolResult, Signal, TerminateAgentWithSuccess, TerminateAgentWithFailure, TerminateSuccessResult, ToolFailure, ToolCallOutcome, T_tool

VirtualName: TypeAlias = str

FilePath: TypeAlias = str

FileMapping: TypeAlias = dict[VirtualName, FilePath]

ReadablePaths: TypeAlias = list[VirtualName]

WritablePaths: TypeAlias = list[VirtualName]

BlameTargets: TypeAlias = list[str]

BlameTarget: TypeAlias = str

Feedback: TypeAlias = str

Blame: TypeAlias = tuple[BlameTarget, Feedback]

SearchResultLimit: TypeAlias = int

TemplateMapping: TypeAlias = dict[VirtualName, str]

VerificationCallback: TypeAlias = Callable[[], tuple[bool, str]] | None

@dataclass
class SandboxConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    session_start_reads_enabled: bool = True
    guide: VirtualName | None = None
    step_sections_enabled: bool = True
    feedback_pending: bool = False
    templates: TemplateMapping = field(default_factory=dict)
    verification_callback: VerificationCallback = None

WriteOccurred: TypeAlias = bool


class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def get_session_start_reads(self) -> list[PresentedToolResult]: ...
    def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName, pattern: str, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
