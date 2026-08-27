"""
Implementation of the LLS Sandbox interface.

The sandbox is a facade: it composes the file machinery (file_view), the
step-mode guide delivery (guide_delivery), and the verification and
termination rules (run_control) into a single tool surface. Each operation
delegates to the owning component's operation; the composition is described
in specs/low/sandbox_impl.md.
"""

from typing import Dict, List, Optional

from .sandbox import Sandbox, SandboxConfig
from .file_view import FileViewConfig, VirtualName, WriteOccurred
from .guide_delivery import GuideDeliveryConfig
from .run_control import RunControlConfig, DiffSizeLimit, Blame
from .file_view_impl import FileViewImpl
from .guide_delivery_impl import GuideDeliveryImpl
from .run_control_impl import RunControlImpl
from .tool_provider import (
    ToolDefinition,
    PresentedToolResult,
    ToolCallOutcome,
    ToolFailure,
)


class SandboxImpl(Sandbox):
    """
    Implementation of the LLS Sandbox interface.

    An assembler: wires together the file machinery (FileViewImpl), the
    step-mode delivery (GuideDeliveryImpl), and the verification and
    termination rules (RunControlImpl) from the aggregate SandboxConfig,
    and dispatches each tool call to the owning component. Holds only
    per-run state, in the components: the file state (file_view), the step
    state (guide_delivery), and the verification state (run_control);
    nothing persists across runs.
    """

    def __init__(self, config: SandboxConfig, diff_size_limit: Optional[DiffSizeLimit] = None):
        """
        Initialize the sandbox with configuration.

        Args:
            config: Configuration object containing file mappings, policies,
                etc.
            diff_size_limit: Maximum characters a verification diff may report
                (default: 1000 when None).
        """
        self.config = config
        self.diff_size_limit = diff_size_limit

        # Step mode (per the sandbox contract): when step mode is enabled and
        # a guide is configured, the guide is not readable and its content
        # reaches the agent only through advance's outputs. The guide is
        # excluded from the file machinery's readable paths, so reads of the
        # guide are rejected (with the step-mode policy message below) and the
        # guide never appears among the session-start reads.
        self._step_mode: bool = bool(
            config.step_sections_enabled and config.guide
        )
        readable_paths = list(config.readable_paths)
        if self._step_mode:
            readable_paths = [p for p in readable_paths if p != config.guide]

        # The guide's full path, resolved from the guide's virtual name via
        # the file mappings; None when no guide is declared.
        guide_real = config.file_mappings.get(config.guide) if config.guide else None

        self.file_view = FileViewImpl(FileViewConfig(
            file_mappings=config.file_mappings,
            readable_paths=readable_paths,
            writable_paths=config.writable_paths,
            templates=config.templates,
            search_result_limit=config.search_result_limit,
            session_start_reads_enabled=config.session_start_reads_enabled,
        ))
        self.guide_delivery = GuideDeliveryImpl(GuideDeliveryConfig(
            guide=guide_real,
            step_sections_enabled=config.step_sections_enabled,
        ))
        self.run_control = RunControlImpl(
            RunControlConfig(
                verification_callback=config.verification_callback,
                feedback_pending=config.feedback_pending,
                blame_targets=config.blame_targets,
                diff_size_limit=diff_size_limit if diff_size_limit is not None else 1000,
            ),
            file_view=self.file_view,
            guide_delivery=self.guide_delivery,
        )

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Return the composed tool registry: the file tools, the advance
        tool, and the termination tools, presented together as the sandbox's
        tool surface."""
        return (
            self.file_view.get_tool_definitions()
            + self.guide_delivery.get_tool_definitions()
            + self.run_control.get_tool_definitions()
        )

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        """The session-start reads: the plain reads of the read-only files
        and, in step mode, the guide's presentation, presented together
        before the model's first turn."""
        return (
            self.file_view.get_session_start_reads()
            + self.guide_delivery.get_session_start_reads()
        )

    def read_file(self, file_path: VirtualName,
                  include_line_numbers: bool = False) -> ToolCallOutcome:
        """Read a file's entire content, optionally in the line-numbered view."""
        if self._in_step_mode(file_path):
            return ToolFailure[str](
                f"File path '{file_path}' is not readable in step mode: the "
                f"guide's content reaches the agent only through advance outputs."
            )
        return self.file_view.read_file(file_path, include_line_numbers)

    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str,
                  expect_multiple: bool = False) -> ToolCallOutcome:
        """Replace text in a file (content-based search and replace)."""
        return self.file_view.edit_file(file_path, old_str, new_str, expect_multiple)

    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                      new_str: str) -> ToolCallOutcome:
        """Replace, delete, or insert lines by 1-indexed line range."""
        return self.file_view.replace_lines(file_path, start_line, end_line, new_str)

    def search_files(self, path: VirtualName, pattern: str,
                     offset: Optional[int] = None,
                     limit: Optional[int] = None) -> ToolCallOutcome:
        """Search for a pattern in files; render matches only for read-only files."""
        if self._in_step_mode(path):
            return ToolFailure[str](
                f"Path '{path}' is not readable in step mode: the "
                f"guide's content reaches the agent only through advance outputs."
            )
        return self.file_view.search_files(path, pattern, offset, limit)

    def advance(self, changes: List[Dict[str, str]] = []) -> ToolCallOutcome:
        """Signal the run's completion: verify the run and then signal
        successful termination, or provide feedback on a failing verification.

        Delegates to run_control.advance, which sequences verification, the
        step-mode output (per guide_delivery's output rule), and the
        termination machinery.
        """
        return self.run_control.advance(changes)

    def fail(self) -> ToolCallOutcome:
        """End the session in failure (agent failure)."""
        return self.run_control.fail()

    def blame(self, blames: List[Blame]) -> ToolCallOutcome:
        """Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs."""
        return self.run_control.blame(blames)

    def get_write_occurred(self) -> WriteOccurred:
        """Return whether the agent has modified the filesystem during the current run."""
        return self.file_view.get_write_occurred()

    def _in_step_mode(self, file_path: VirtualName) -> bool:
        """Whether a file is excluded by step mode: the guide is not readable."""
        return self._step_mode and file_path == self.config.guide
