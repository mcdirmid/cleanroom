# lib/sandbox_impl.py
"""
Implementation of the LLS Sandbox interface.
"""

from typing import Callable, Dict, List, Optional

from .sandbox import Sandbox, SandboxConfig
from .file_reader import FileReader, FileReaderConfig, VirtualName
from .file_editor import FileEditor, FileEditorConfig, WriteOccurred
from .guide_delivery import GuideDelivery, GuideDeliveryConfig
from .run_control import RunControl, RunControlConfig, DiffSizeLimit, Blame
from .tool_provider import (
    ToolDefinition,
    PresentedToolResult,
    ToolCallOutcome,
    ToolFailure,
)


class SandboxImpl(Sandbox):
    def __init__(
        self,
        config: SandboxConfig,
        make_file_reader: Callable[[FileReaderConfig], FileReader],
        make_file_editor: Callable[[FileEditorConfig, FileReader], FileEditor],
        make_guide_delivery: Callable[[GuideDeliveryConfig], GuideDelivery],
        make_run_control: Callable[[RunControlConfig, FileReader, FileEditor, GuideDelivery], RunControl],
        diff_size_limit: Optional[DiffSizeLimit] = None,
    ):
        self.config = config
        self.diff_size_limit = diff_size_limit

        self._step_mode: bool = bool(
            config.step_sections_enabled and config.guide
        )
        readable_paths = list(config.readable_paths)
        if self._step_mode:
            readable_paths = [p for p in readable_paths if p != config.guide]

        guide_real = config.file_mappings.get(config.guide) if config.guide else None

        self.file_reader = make_file_reader(FileReaderConfig(
            file_mappings=config.file_mappings,
            readable_paths=readable_paths,
            search_result_limit=config.search_result_limit,
            session_start_reads_enabled=config.session_start_reads_enabled,
        ))
        self.file_editor = make_file_editor(
            FileEditorConfig(
                writable_paths=config.writable_paths,
                templates=config.templates,
            ),
            self.file_reader,
        )
        self.guide_delivery = make_guide_delivery(GuideDeliveryConfig(
            guide=guide_real,
            step_sections_enabled=config.step_sections_enabled,
        ))
        self.run_control = make_run_control(
            RunControlConfig(
                verification_callback=config.verification_callback,
                feedback_pending=config.feedback_pending,
                blame_targets=config.blame_targets,
                diff_size_limit=diff_size_limit if diff_size_limit is not None else 1000,
            ),
            self.file_reader,
            self.file_editor,
            self.guide_delivery,
        )

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return (
            self.file_reader.get_tool_definitions()
            + self.file_editor.get_tool_definitions()
            + self.guide_delivery.get_tool_definitions()
            + self.run_control.get_tool_definitions()
        )

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        return (
            self.file_reader.get_session_start_reads()
            + self.guide_delivery.get_session_start_reads()
        )

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        if self._step_mode and file_path == self.config.guide:
            return ToolFailure(
                value=f"'{file_path}' is the guide for this node. It is delivered section by section through advance; reading it directly is not permitted."
            )
        return self.file_reader.read_file(file_path, include_line_numbers)

    def replace(self, file_path: VirtualName, old_str: str, new_str: str,
                expect_multiple: bool = False) -> ToolCallOutcome:
        return self.file_editor.replace(file_path, old_str, new_str, expect_multiple)

    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                     new_str: str) -> ToolCallOutcome:
        return self.file_editor.update_lines(file_path, start_line, end_line, new_str)

    def search_files(self, path: VirtualName = ".", pattern: str = "",
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        if self._step_mode and path == self.config.guide:
            return ToolFailure(
                value=f"'{path}' is the guide for this node. It is delivered section by section through advance; searching it directly is not permitted."
            )
        return self.file_reader.search_files(path, pattern, offset, limit)

    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome:
        return self.run_control.advance(changes)

    def fail(self) -> ToolCallOutcome:
        return self.run_control.fail()

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        return self.run_control.blame(blames)

    def get_write_occurred(self) -> WriteOccurred:
        return self.file_editor.get_write_occurred()
