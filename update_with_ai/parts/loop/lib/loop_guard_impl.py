from typing import Any, Optional, Tuple, Union
from . import loop_guard
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry


class LoopGuard(loop_guard.LoopGuard, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, Any]] = None
        self._consecutive_count: int = 0
        self._reminder_threshold: int = 2
        self._fatal_threshold: int = 5

    def record_tool_execution(
        self, tool_name: str, bindings: tool_provider.ActualParameterBindings
    ) -> Optional[Union[loop_guard.LoopReminder, loop_guard.LoopFailure]]:
        # Requirement: [LoopGuard] A loop guard evaluates consecutive executions of identical tools and edits.
        call_key = (
            tool_name,
            frozenset((p.name, str(v)) for p, v in bindings.bindings),
        )
        if self._last_call == call_key:
            self._consecutive_count += 1
        else:
            self._last_call = call_key
            self._consecutive_count = 1

        # Requirement: Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
        if self._consecutive_count >= self._fatal_threshold:
            return loop_guard.LoopFailure(
                explanation=f"Fatal loop detected: tool '{tool_name}' executed {self._consecutive_count} times consecutively."
            )
        # Requirement: Produces a loop reminder advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated when consecutive identical tool executions reach the reminder threshold of two repetitions.
        elif self._consecutive_count >= self._reminder_threshold:
            return loop_guard.LoopReminder(
                feedback=f"Warning: tool '{tool_name}' has been executed {self._consecutive_count} times consecutively, no new information will be revealed by this tool call until session read-write files are updated. Repeating this tool call without modifying files will trigger fatal loop termination."
            )
        return None

    def record_progress(self) -> None:
        # Requirement: A tool execution demonstrating forward progress resets repetition counters in the loop guard.
        # Requirement: [LoopGuard] Executing a tool that demonstrates progress clears repetition tracking in the loop guard.
        self._consecutive_count = 0
        self._last_call = None


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        LoopGuard,
        keys=[LoopGuard, loop_guard.LoopGuard],
        tier="agent_session",
    )
