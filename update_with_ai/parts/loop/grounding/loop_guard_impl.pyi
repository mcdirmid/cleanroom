from typing import Optional, Union
from framework import operation, override, singleton_type
import loop_guard
import tool_provider

@singleton_type('agent_session')
class LoopGuard(loop_guard.LoopGuard):
    """
PURPOSE:
Implements loop guard tracking identical tools and edit spans

GROUNDING_ARGUMENT:
- As an agent_session singleton, LoopGuard tracks tool executions and edits within the active session scope and relies on types from imported loop_guard and tool_provider in the same lifecycle tier.
"""

    @operation
    @override
    def record_tool_execution(self, tool_name: str, bindings: tool_provider.ActualParameterBindings) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        """
PURPOSE:
Tracks consecutive identical tool calls and edits

FRESH_REQUIREMENTS:
- Produces a loop reminder advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated when consecutive identical tool executions reach the reminder threshold of two repetitions.
- Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
- Produces a loop reminder at the reminder threshold of two repetitions when consecutive edits target the same file and line range.
- Produces a loop failure at the fatal threshold when consecutive edits target the same file and line range.

INHERITED_REQUIREMENTS:
- [LoopGuard] A loop guard evaluates consecutive executions of identical tools and edits.
- [LoopGuard] Consecutive repetitions reaching a warning threshold produce a loop reminder.
- [LoopGuard] Consecutive repetitions reaching a fatal threshold produce a loop failure communicating session termination.

GROUNDING_ARGUMENT:
- The operation accesses tool_name and parameter bindings passed as arguments, evaluates them against internal repetition tracking state on self, and constructs LoopReminder or LoopFailure data variants without requiring external collaborator singletons.
"""
        ...

    @operation
    @override
    def record_progress(self) -> None:
        """
PURPOSE:
Resets repetition counters on forward progress

FRESH_REQUIREMENTS:
- A tool execution demonstrating forward progress resets repetition counters in the loop guard.

INHERITED_REQUIREMENTS:
- [LoopGuard] Executing a tool that demonstrates progress clears repetition tracking in the loop guard.

GROUNDING_ARGUMENT:
- The operation accesses and resets internal repetition counters stored directly on self within the agent_session singleton.
"""
        ...
