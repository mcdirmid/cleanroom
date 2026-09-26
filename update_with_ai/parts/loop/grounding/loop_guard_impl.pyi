from typing import Optional, Union, Self
from framework import operation, override, singleton_type
import loop_guard
import tool_provider


@singleton_type('agent_session')
class LoopGuard(loop_guard.LoopGuard):
    """Implements loop guard tracking identical tools and edit spans.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, LoopGuard tracks tool executions and edits within the active session scope and relies on types from imported loop_guard and tool_provider in the same lifecycle tier.
    """

    @operation
    @override
    def record_tool_execution(self, tool_name: str, bindings: tool_provider.ActualParameterBindings) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        """Tracks consecutive identical tool calls and edits.

        REQUIREMENTS:
        - Produces a loop reminder advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated and that repeating the tool call without modifying files will trigger fatal loop termination when consecutive identical tool executions reach the reminder threshold of two repetitions.
        - Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
        - Produces a loop reminder at the reminder threshold of two repetitions when consecutive edits target the same file and line range.
        - Produces a loop failure at the fatal threshold when consecutive edits target the same file and line range.

        GROUNDING_IMPLEMENTS:
        - action("record_tool_execution", Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]): Tracks consecutive identical tool calls and edits.
        """
        ...

    @operation
    @override
    def record_progress(self) -> None:
        """Resets repetition counters on forward progress.

        REQUIREMENTS:
        - A tool execution demonstrating forward progress resets repetition counters in the loop guard.

        GROUNDING_IMPLEMENTS:
        - action("record_progress", None): Resets repetition tracking.
        """
        ...
