from typing import Optional, Union
from framework import operation, override, singleton_type
import agent_loop_guard
import tool_provider

@singleton_type('agent_session')
class LoopGuard(agent_loop_guard.LoopGuard):
    """
PURPOSE:
Implements loop guard tracking identical tools and edit spans

GROUNDING_ARGUMENT:
- As an agent_session singleton, LoopGuard tracks tool executions and edits within the active session scope and relies on types from imported agent_loop_guard and tool_provider in the same lifecycle tier.
"""

    @operation
    @override
    def record_tool_execution(self, tool_name: str, bindings: tool_provider.ActualParameterBindings) -> Optional[Union[agent_loop_guard.LoopReminder, agent_loop_guard.LoopFailure]]:
        """
PURPOSE:
Tracks consecutive identical tool calls and edits

FRESH_REQUIREMENTS:
- The loop guard tracks consecutive executions of identical tools with identical arguments.
- The loop guard produces a loop reminder when consecutive identical tool executions reach the reminder threshold.
- The loop guard produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
- The loop guard tracks consecutive edits to the same file and line range, producing a reminder at the reminder threshold and a loop failure at the fatal threshold.

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
