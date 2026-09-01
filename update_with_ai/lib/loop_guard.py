"""Loop guard interface and repetition monitors."""

from typing import Protocol, TypeAlias, Optional, Union
from dataclasses import dataclass
from .tool_provider import ToolArguments, ToolResult, ToolFailure, ToolName

ReminderThreshold: TypeAlias = int
FatalThreshold: TypeAlias = int
FilePath: TypeAlias = str
LineRange: TypeAlias = tuple[int, int]


@dataclass(frozen=True)
class LoopGuardConfig:
    reminder_threshold: ReminderThreshold = 3
    fatal_threshold: FatalThreshold = 6


LoopReminder: TypeAlias = ToolResult
LoopFailure: TypeAlias = ToolFailure


class LoopGuard(Protocol):
    def record_tool_call(
        self, tool_name: ToolName, arguments: ToolArguments
    ) -> Optional[Union[LoopReminder, LoopFailure]]:
        ...

    def record_file_edit(
        self, file_path: FilePath, line_range: LineRange
    ) -> Optional[Union[LoopReminder, LoopFailure]]:
        ...

    def reset_progress(self) -> None:
        ...

