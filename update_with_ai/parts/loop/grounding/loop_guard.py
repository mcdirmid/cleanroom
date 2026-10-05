# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 907ba900124f
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Loop guard grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, NewType, Optional, Protocol, Union
from support.lib.grounding_support import InTier, AgentSessionTier, key, value
from parts.sandbox.grounding import tool_provider

LoopFeedback = NewType("LoopFeedback", str)
FailureExplanation = NewType("FailureExplanation", str)


@dataclass(frozen=True)
class LoopReminder:
    """Diagnostic feedback warning an agent of detected repetition.

    COVERED:
    - Encapsulates feedback string attribute.
    """

    feedback: LoopFeedback


@dataclass(frozen=True)
class LoopFailure:
    """Outcome signaling that an agent session has failed due to unresolvable repetition.

    COVERED:
    - Encapsulates explanation string attribute.
    """

    explanation: FailureExplanation


class LoopGuard(InTier[AgentSessionTier], Protocol):
    """Session service tracking repetitive tool executions and edit oscillations."""

    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[LoopReminder, LoopFailure]]:
        """
        COVERED:
        - MUST evaluate consecutive executions of identical tools and file edits.
          - Condition knowledge: access tool_name and parameter bindings from arguments.
          - Consequent knowledge: construct LoopReminder or LoopFailure.
        - WHEN consecutive repetitions reach the warning threshold, MUST produce a loop reminder.
          - Condition knowledge: test repetition count against warning threshold.
          - Consequent knowledge: return LoopReminder.
        - WHEN consecutive repetitions reach the fatal threshold, MUST produce a loop failure communicating session termination.
          - Condition knowledge: test repetition count against fatal threshold.
          - Consequent knowledge: return LoopFailure.

        DEFERRED:
        - Repetition counter tracking and threshold comparison deferred to loop_guard_impl.py."""
        _sample_param = key(arguments)
        _sample_val = value(arguments)
        _sample_reminder = LoopReminder(
            feedback=LoopFeedback(f"Warning: tool '{tool_name}' repetition")
        )
        _sample_failure = LoopFailure(
            explanation=FailureExplanation(
                f"Fatal loop detected for tool '{tool_name}'"
            )
        )
        _res: Optional[Union[LoopReminder, LoopFailure]] = _sample_reminder
        raise NotImplementedError

    def reset(self) -> None:
        """
        DEFERRED:
        - MUST clear repetition tracking when a tool execution demonstrates forward progress.
          - Deferred to refining implementation in loop_guard_impl.py.
        """
        raise NotImplementedError
