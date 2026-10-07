# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T12:45:00Z
# CHANGE: add grounding sections
# CODE_HASH: 9ca7c1878180
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
    """Realizes threshold-based repetition tracking for tools and line-bounded file edits.

    GROUNDING:
    - Maintains in-memory call signatures and file edit ranges, emitting LoopReminder
      at warning thresholds and LoopFailure at fatal thresholds.
    """

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

        GROUNDING:
        - Grounded via tracking consecutive identical tool calls and file edit coordinate spans,
          producing LoopReminder at two repetitions and LoopFailure at fatal limits.

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

        GROUNDING:
        - Grounded via clearing internal consecutive repetition counters when forward progress occurs.

        POSTCONDITIONS:
        - MUST reset repetition counters in the loop guard.
        """
        ...
