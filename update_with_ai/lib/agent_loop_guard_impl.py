from typing import Any, Optional, Tuple, Union
from . import agent_loop_guard
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

class LoopGuard(agent_loop_guard.LoopGuard, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, Any]] = None
        self._consecutive_count: int = 0
        self._reminder_threshold: int = 3
        self._fatal_threshold: int = 5

    def record_tool_execution(
        self, tool_name: str, bindings: tool_provider.ActualParameterBindings
    ) -> Optional[Union[agent_loop_guard.LoopReminder, agent_loop_guard.LoopFailure]]:
        # Requirement: The loop guard tracks consecutive executions of identical tools with identical arguments.
        call_key = (tool_name, frozenset((p.name, str(v)) for p, v in bindings.bindings))
        if self._last_call == call_key:
            self._consecutive_count += 1
        else:
            self._last_call = call_key
            self._consecutive_count = 1

        # Requirement: The loop guard produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.
        if self._consecutive_count >= self._fatal_threshold:
            return agent_loop_guard.LoopFailure(
                explanation=f"Fatal loop detected: tool '{tool_name}' executed {self._consecutive_count} times consecutively."
            )
        # Requirement: The loop guard produces a loop reminder when consecutive identical tool executions reach the reminder threshold.
        elif self._consecutive_count >= self._reminder_threshold:
            return agent_loop_guard.LoopReminder(
                feedback=f"Warning: tool '{tool_name}' has been executed {self._consecutive_count} times consecutively without progress."
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
        keys=[LoopGuard, agent_loop_guard.LoopGuard],
        tier="agent_session",
    )
