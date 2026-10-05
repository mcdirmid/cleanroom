# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 48aec8080a13
# --- END CLEANROOM METADATA ---

"""Loop guard implementation low-level specification."""

from typing import Any, Mapping, Optional, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import loop_guard
import tool_provider


@singleton_type("agent_session")
class LoopGuard(loop_guard.LoopGuard, InTier[AgentSessionTier]):
    """Realizes threshold-based repetition tracking for tools and line-bounded file edits."""

    @operation
    @override
    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        """Evaluates consecutive identical executions against configured reminder and fatal limits.

        Args:
            tool_name: The name of the tool being executed.
            arguments: The actual parameter bindings passed to the tool.

        Returns:
            Optional loop reminder or loop failure.

        POSTCONDITIONS:
        - WHEN consecutive identical tool executions reach two repetitions, MUST produce a loop reminder.
        - WHEN consecutive identical tool executions reach the fatal threshold, MUST produce a loop failure.
        - WHEN consecutive edits target the same file and line range at two repetitions, MUST produce a loop reminder.
        - WHEN consecutive edits target the same file and line range at the fatal threshold, MUST produce a loop failure.
        """
        ...

    @operation
    @override
    def reset(self) -> None:
        """Resets repetition tracking counters upon forward progress.

        POSTCONDITIONS:
        - MUST reset repetition counters in the loop guard.
        """
        ...
