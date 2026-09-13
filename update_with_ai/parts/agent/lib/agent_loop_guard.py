"""Agent loop guard interface and data types."""

from dataclasses import dataclass
from typing import Optional, Protocol, Union
from update_with_ai.parts.sandbox.lib import tool_provider


@dataclass(frozen=True)
class LoopReminder:
    feedback: str


@dataclass(frozen=True)
class LoopFailure:
    explanation: str


class LoopGuard(Protocol):
    def record_tool_execution(
        self, tool_name: str, bindings: tool_provider.ActualParameterBindings
    ) -> Optional[Union[LoopReminder, LoopFailure]]: ...

    def record_progress(self) -> None: ...
