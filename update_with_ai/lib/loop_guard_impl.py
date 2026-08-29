"""
lib/loop_guard_impl.py

Implementation of LoopGuard protocol for repetition detection and reminders.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

from .agent_loop_config import AgentLoopConfig
from .loop_guard import LoopDecision, LoopGuard
from .tool_provider import ToolCall


class LoopGuardImpl(LoopGuard):
    """
    Detects repetition loops, same-range update spins, and provides reminders.
    """

    def __init__(self, config: Optional[AgentLoopConfig] = None) -> None:
        self._config = config
        self._loop_last_signature: Optional[Tuple[str, str]] = None
        self._loop_repeat_count = 0
        self._loop_last_range: Optional[Tuple[Any, Any, Any]] = None
        self._loop_range_count = 0
        self._loop_reminder_injected = False

    def reset(self) -> None:
        """Reset repetition tracking state and reminder flags."""
        self._loop_last_signature = None
        self._loop_repeat_count = 0
        self._loop_last_range = None
        self._loop_range_count = 0
        self._loop_reminder_injected = False

    def record_tool_call(self, tool_call: ToolCall) -> LoopDecision:
        """Evaluate a tool call for identical call repetition and range repetition."""
        name = tool_call.get("function", {}).get("name", "")
        raw_args = tool_call.get("function", {}).get("arguments", "")
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            arguments = {}

        # The advance tool is exempt and resets tracking
        signature = (name, json.dumps(arguments, sort_keys=True) if isinstance(arguments, dict) else str(arguments))
        if name == "advance":
            self._loop_last_signature = None
            self._loop_repeat_count = 0
        elif signature == self._loop_last_signature:
            self._loop_repeat_count += 1
        else:
            self._loop_last_signature = signature
            self._loop_repeat_count = 1

        if self._loop_repeat_count >= 8:
            error_msg = "Degenerate loop: same tool call repeated 8 consecutive times"
            return (True, None, error_msg)

        if self._loop_repeat_count >= 4 and not self._loop_reminder_injected:
            self._loop_reminder_injected = True
            reminder = (
                f"You have called '{name}' with the same arguments {self._loop_repeat_count} "
                f"times in a row. Review the latest tool results and make progress: "
                f"change the file (replace/update_lines) or finish "
                f"the run with advance(), fail(), or blame()."
            )
            return (False, reminder, None)

        if name == "update_lines" and isinstance(arguments, dict):
            range_signature = (
                arguments.get("file_path"),
                arguments.get("start_line"),
                arguments.get("end_line"),
            )
            if range_signature == self._loop_last_range:
                self._loop_range_count += 1
            else:
                self._loop_last_range = range_signature
                self._loop_range_count = 1

            if self._loop_range_count >= 8 and range_signature[0] is not None:
                error_msg = (
                    "Degenerate loop: update_lines targeted the same file "
                    "and line range 8 consecutive times"
                )
                return (True, None, error_msg)

            if (
                self._loop_range_count >= 4
                and not self._loop_reminder_injected
                and range_signature[0] is not None
            ):
                self._loop_reminder_injected = True
                reminder = (
                    f"You have edited lines {range_signature[1]}-{range_signature[2]} of '{range_signature[0]}' "
                    f"{self._loop_range_count} times in a row without progress. Re-read the file "
                    f"(read_file('{range_signature[0]}', include_line_numbers=True)) and "
                    f"reassess, or finish the run with advance(), fail(), or blame()."
                )
                return (False, reminder, None)

        return (False, None, None)

    def check_degenerate_response(self, content: Optional[str]) -> bool:
        """Check if a truncated model response consists of a single character repeated."""
        return isinstance(content, str) and len(content) > 0 and len(set(content)) == 1

    def get_termination_reminder(self) -> str:
        """Provide termination reminder text when model stops without tool calls."""
        if self._config is not None and self._config.termination_reminder_generator is not None:
            return self._config.termination_reminder_generator()
        return (
            "You must signal termination by calling advance(), fail(), "
            "or blame() to end the run."
        )
