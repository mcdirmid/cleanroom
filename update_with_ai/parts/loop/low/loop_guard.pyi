# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 0e314b906130
# --- END CLEANROOM METADATA ---

"""Loop guard low-level interface specification."""

from dataclasses import dataclass
from typing import Any, Mapping, NewType, Optional, Protocol, Union
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import tool_provider

LoopFeedback = NewType("LoopFeedback", str)
FailureExplanation = NewType("FailureExplanation", str)


@dataclass(frozen=True)
@data_type
class LoopReminder:
    """Diagnostic feedback warning an agent of detected repetition.

    Args:
        feedback: The warning text.
    """
    feedback: LoopFeedback


@dataclass(frozen=True)
@data_type
class LoopFailure:
    """Outcome signaling that an agent session has failed due to unresolvable repetition.

    Args:
        explanation: The explanation text.
    """
    explanation: FailureExplanation


@singleton_type("agent_session")
class LoopGuard(InTier[AgentSessionTier], Protocol):
    """Session service tracking repetitive tool executions and edit oscillations."""

    @operation
    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> Optional[Union[LoopReminder, LoopFailure]]:
        """Evaluates tool invocation against repetition thresholds.

        Args:
            tool_name: The name of the tool being executed.
            arguments: The actual parameter bindings passed to the tool.

        Returns:
            Optional loop reminder or loop failure.

        POSTCONDITIONS:
        - MUST evaluate consecutive executions of identical tools and file edits.
        - WHEN consecutive repetitions reach the warning threshold, MUST produce a loop reminder.
        - WHEN consecutive repetitions reach the fatal threshold, MUST produce a loop failure communicating session termination.
        """
        ...

    @operation
    def reset(self) -> None:
        """Clears repetition tracking when a tool execution demonstrates forward progress.

        POSTCONDITIONS:
        - MUST clear repetition tracking when a tool execution demonstrates forward progress.
        """
        ...
