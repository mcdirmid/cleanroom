# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T03:21:58Z
# CHANGE: Canonicalize warning-of-two and fatal thresholds and split reminder content statements
# CODE_HASH: 86baa7b3771e
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
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
    - Realizes loop_guard.LoopGuard.evaluate and loop_guard.LoopGuard.reset as the session-scoped
      loop_guard_service knowledge provision for repetition tracking and loop prevention across
      consecutive tool executions and file edits.
    - Backs consecutive tool tracking with an ordered sequence of consecutive call signatures held
      in internal backing state, each signature formed from tool_provider.ToolName and the
      tool_provider.ToolParameter to tool_provider.SomeParameterActualType argument bindings, so
      identical executions are compared by identical arguments rather than by wire text.
    - Backs consecutive edit tracking with a recorded file and line range span, comparing the file
      identity and line range of each edit invocation against the span recorded for its predecessor.
    - Maintains a counter for consecutive identical tool executions and a counter for consecutive
      edits to the same file and line range, each evaluated against the warning threshold of two
      repetitions and against the fatal threshold.
    - Derives the evaluated executions from the tool execution capability of tool_provider, whose
      tool_provider.ToolManager.execute_tool and tool_provider.Tool.execute_tool members execute the
      tool calls the session loop submits for repetition evaluation, grounding the inherited
      consecutive tool signature tracking requirement on tool_provider:[tool_execution_capability].
    - Materializes loop_guard.LoopReminder for advisory repetition feedback and loop_guard.LoopFailure
      for the fatal failure communicating session failure, and clears the counters through
      loop_guard.LoopGuard.reset whenever a tool execution demonstrates forward progress.
    """

    @operation
    @override
    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        """Evaluates consecutive identical executions against the warning and fatal thresholds.

        Args:
            tool_name: The name of the tool being executed.
            arguments: The actual parameter bindings passed to the tool.

        Returns:
            Optional loop reminder or loop failure.

        GROUNDING:
        - Builds the call signature of the observed execution from tool_name and arguments, then
          compares that signature with the predecessor recorded in the sequence of consecutive call
          signatures so identical tool executions with identical arguments are tracked as a streak.
        - Reads the file identity and line range of an edit invocation out of the argument bindings
          and compares them with the recorded file and line range span, so the edit streak extends
          only while both the target file and the line range are unchanged.
        - Compares the identical tool execution counter and the edit repetition counter against the
          warning threshold of two repetitions and against the fatal threshold, then materializes
          loop_guard.LoopReminder carrying advisory feedback or loop_guard.LoopFailure carrying the
          failure explanation, according to which counter reached which threshold.
        - Leaves the evaluated execution recorded in internal backing state so the next evaluation
          measures repetition from the immediately preceding invocation.

        POSTCONDITIONS:
        - MUST track consecutive executions of identical tools with identical arguments.
        - MUST track consecutive edits to the same file and line range.
        - WHEN consecutive identical tool executions reach the warning threshold of two repetitions,
          MUST produce a loop reminder advising the agent that no new information will be revealed
          until session read-write files are updated.
        - WHEN consecutive identical tool executions reach the warning threshold of two repetitions,
          MUST warn through that loop reminder that repeating without modifying files will trigger
          fatal termination.
        - WHEN consecutive identical tool executions reach the fatal threshold, MUST produce a loop
          failure communicating session failure.
        - WHEN consecutive edits target the same file and line range and reach the warning threshold
          of two repetitions, MUST produce a loop reminder.
        - WHEN consecutive edits target the same file and line range and reach the fatal threshold,
          MUST produce a loop failure.
        """
        ...

    @operation
    @override
    def reset(self) -> None:
        """Resets repetition tracking counters upon forward progress.

        GROUNDING:
        - Clears the recorded sequence of consecutive call signatures and the recorded file and line
          range span held in internal backing state, so the next evaluated execution is compared
          against no predecessor.
        - Reinitializes the identical tool execution counter and the same-file, same-line-range edit
          counter, satisfying the repetition counter reset knowledge requirement grounded on
          loop_guard_service.

        POSTCONDITIONS:
        - MUST reset repetition counters when a tool execution demonstrates forward progress.
        - MUST clear the recorded consecutive call signatures and file and line range span.
        """
        ...
