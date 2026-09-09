from typing import Optional, Protocol, Union
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
import tool_provider

@dataclass(frozen=True)
@data_type
class LoopReminder:
    """
PURPOSE:
Diagnostic feedback warning an agent of detected repetition
"""

    def __init__(self, feedback: str) -> None:
        ...

    @property
    def feedback(self) -> str:
        """
PURPOSE:
Advisory message guiding the agent to try a different approach
"""
        ...

@dataclass(frozen=True)
@data_type
class LoopFailure:
    """
PURPOSE:
Outcome signaling that an agent session has failed due to repetition
"""

    def __init__(self, explanation: str) -> None:
        ...

    @property
    def explanation(self) -> str:
        """
PURPOSE:
Explanation of why the run failed due to runaway repetition
"""
        ...

@singleton_type('agent_session')
class LoopGuard(Protocol):
    """
PURPOSE:
Defined as an agent session service that tracks repetitive execution patterns
"""

    @operation
    def record_tool_execution(self, tool_name: str, bindings: tool_provider.ActualParameterBindings) -> Optional[Union[LoopReminder, LoopFailure]]:
        """
PURPOSE:
Evaluates tool repetition, returning reminder or failure when thresholds are reached

FRESH_REQUIREMENTS:
- A loop guard evaluates consecutive executions of identical tools and edits.
- Consecutive repetitions reaching a warning threshold produce a loop reminder.
- Consecutive repetitions reaching a fatal threshold produce a loop failure communicating session termination.
"""
        ...

    @operation
    def record_progress(self) -> None:
        """
PURPOSE:
Clears repetition tracking when forward progress is observed

FRESH_REQUIREMENTS:
- Executing a tool that demonstrates progress clears repetition tracking in the loop guard.
"""
        ...
