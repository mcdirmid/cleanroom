from typing import Optional, Protocol, Union
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
import tool_provider


@dataclass(frozen=True)
@data_type
class LoopReminder:
    """Diagnostic feedback warning an agent of detected repetition."""

    def __init__(self, feedback: str) -> None:
        ...

    @property
    def feedback(self) -> str:
        """Advisory message guiding the agent to try a different approach."""
        ...


@dataclass(frozen=True)
@data_type
class LoopFailure:
    """Outcome signaling that an agent session has failed due to repetition."""

    def __init__(self, explanation: str) -> None:
        ...

    @property
    def explanation(self) -> str:
        """Explanation of why the run failed due to runaway repetition."""
        ...


@singleton_type('agent_session')
class LoopGuard(Protocol):
    """Session service that tracks repetitive execution patterns."""

    @operation
    def record_tool_execution(self, tool_name: str, bindings: tool_provider.ActualParameterBindings) -> Optional[Union[LoopReminder, LoopFailure]]:
        """Evaluates tool repetition, returning reminder or failure when thresholds are reached.

        REQUIREMENTS:
        - A loop guard evaluates consecutive executions of identical tools and edits.
        - Consecutive repetitions reaching a warning threshold produce a loop reminder.
        - Consecutive repetitions reaching a fatal threshold produce a loop failure communicating session termination.

        GROUNDING_PROVISIONS:
        - action("record_tool_execution", Optional[Union[LoopReminder, LoopFailure]]): Evaluates tool repetition.
        """
        ...

    @operation
    def record_progress(self) -> None:
        """Clears repetition tracking when forward progress is observed.

        REQUIREMENTS:
        - Executing a tool that demonstrates progress clears repetition tracking in the loop guard.

        GROUNDING_PROVISIONS:
        - action("record_progress", None): Resets repetition counters.
        """
        ...
