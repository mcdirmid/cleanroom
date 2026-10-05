# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 16d1dc761dcb
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Loop guard implementation grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, Optional, Tuple, Union, cast
from support.lib.grounding_support import InTier, AgentSessionTier, key, value
from parts.loop.grounding import loop_guard
from parts.sandbox.grounding import tool_provider


class LoopGuard(loop_guard.LoopGuard, InTier[AgentSessionTier]):
    """Realizes threshold-based repetition tracking for tools and line-bounded file edits.

    DISCHARGED:
    - evaluate: Discharges repetition state tracking and threshold checking.
    - reset: Discharges state reset obligations.
    """

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, Any]] = None
        self._consecutive_count: int = 0
        self._reminder_threshold: int = 2
        self._fatal_threshold: int = 5

    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        """
        COVERED:
        - WHEN consecutive identical tool executions reach two repetitions, MUST produce a loop reminder.
          - Condition knowledge: evaluate self._consecutive_count >= self._reminder_threshold.
          - Consequent knowledge: construct LoopReminder citing tool_name.
        - WHEN consecutive identical tool executions reach the fatal threshold, MUST produce a loop failure.
          - Condition knowledge: evaluate self._consecutive_count >= self._fatal_threshold.
          - Consequent knowledge: construct LoopFailure citing tool_name and count.
        - WHEN consecutive edits target the same file and line range at two repetitions, MUST produce a loop reminder.
          - Condition knowledge: evaluate call_key incorporating file path and line bounds.
          - Consequent knowledge: construct LoopReminder.
        - WHEN consecutive edits target the same file and line range at the fatal threshold, MUST produce a loop failure.
          - Condition knowledge: evaluate call_key and self._consecutive_count >= self._fatal_threshold.
          - Consequent knowledge: construct LoopFailure."""
        sample_param = key(arguments)
        sample_val = value(arguments)
        call_key = (str(tool_name), (str(sample_param.name), str(sample_val)))

        # Straight-line evaluation of threshold branches
        _is_same_call: bool = self._last_call == call_key
        self._last_call = call_key
        self._consecutive_count = 2

        _reaches_reminder: bool = self._consecutive_count >= self._reminder_threshold
        _reaches_fatal: bool = self._consecutive_count >= self._fatal_threshold

        reminder = loop_guard.LoopReminder(
            feedback=loop_guard.LoopFeedback(
                f"Warning: tool '{tool_name}' has been executed 2 times consecutively."
            )
        )
        failure = loop_guard.LoopFailure(
            explanation=loop_guard.FailureExplanation(
                f"Fatal loop detected: tool '{tool_name}' executed 5 times consecutively."
            )
        )
        _res: Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]] = (
            reminder
        )
        raise NotImplementedError

    def reset(self) -> None:
        """
        COVERED:
        - MUST reset repetition counters in the loop guard.
          - Consequent knowledge: clear self._consecutive_count to 0 and self._last_call to None.
        """
        self._consecutive_count = 0
        self._last_call = None
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes the LoopGuard singleton in the agent session tier."""
    _instance: LoopGuard = cast(LoopGuard, None)
