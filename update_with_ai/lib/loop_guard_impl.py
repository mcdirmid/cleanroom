"""Loop guard implementation tracking identical operations."""

from typing import Optional, Union, Tuple
from .tool_provider import ToolArguments, ToolName
from .loop_guard import (
    LoopGuard,
    LoopGuardConfig,
    LoopReminder,
    LoopFailure,
    FilePath,
    LineRange,
)


class LoopGuardImpl(LoopGuard):
    def __init__(self, config: Optional[LoopGuardConfig] = None) -> None:
        self.config = config or LoopGuardConfig()
        self._last_call: Optional[Tuple[str, str]] = None
        self._call_count = 0
        self._last_edit: Optional[Tuple[str, Tuple[int, int]]] = None
        self._edit_count = 0

    def record_tool_call(
        self, tool_name: ToolName, arguments: ToolArguments
    ) -> Optional[Union[LoopReminder, LoopFailure]]:
        call_key = (tool_name, str(sorted(arguments.items())))
        if self._last_call == call_key:
            self._call_count += 1
        else:
            self._last_call = call_key
            self._call_count = 1

        if self._call_count >= self.config.fatal_threshold:
            return LoopFailure(
                feedback="Fatal repetition detected: Identical tool calls exceeded threshold"
            )
        if self._call_count >= self.config.reminder_threshold:
            return LoopReminder(content="Warning: Repeated identical tool calls detected")
        return None

    def record_file_edit(
        self, file_path: FilePath, line_range: LineRange
    ) -> Optional[Union[LoopReminder, LoopFailure]]:
        edit_key = (file_path, line_range)
        if self._last_edit == edit_key:
            self._edit_count += 1
        else:
            self._last_edit = edit_key
            self._edit_count = 1

        if self._edit_count >= self.config.fatal_threshold:
            return LoopFailure(
                feedback="Fatal repetition detected: Repeated edits to identical line bounds"
            )
        if self._edit_count >= self.config.reminder_threshold:
            return LoopReminder(content="Warning: Repeated identical file edits detected")
        return None

    def reset_progress(self) -> None:
        self._last_call = None
        self._call_count = 0
        self._last_edit = None
        self._edit_count = 0
