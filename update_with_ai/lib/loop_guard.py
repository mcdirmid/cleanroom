"""
lib/loop_guard.py

Loop Guard Interface Protocol.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias, Tuple, Optional
from .tool_provider import ToolCall

LoopDecision: TypeAlias = Tuple[bool, Optional[str], Optional[str]]


class LoopGuard(Protocol):
    """
    Protocol for detecting repetition loops, range spins, degenerate outputs,
    and providing termination reminders.
    """

    def reset(self) -> None:
        """Reset repetition tracking state and reminder flags."""
        ...

    def record_tool_call(self, tool_call: ToolCall) -> LoopDecision:
        """Evaluate a tool call for identical call repetition and range repetition."""
        ...

    def check_degenerate_response(self, content: Optional[str]) -> bool:
        """Check if a truncated model response consists of a single character repeated."""
        ...

    def get_termination_reminder(self) -> str:
        """Provide termination reminder text when model stops without tool calls."""
        ...
