# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 6d103feb712f
# --- END CLEANROOM METADATA ---

# Requirements specified in loop_guard.pyi
from dataclasses import dataclass
from typing import Any, Mapping, NewType, Optional, Protocol, Union
from update_with_ai.parts.sandbox.lib import tool_provider

LoopFeedback = NewType("LoopFeedback", str)
FailureExplanation = NewType("FailureExplanation", str)


@dataclass(frozen=True)
class LoopReminder:
    feedback: LoopFeedback


@dataclass(frozen=True)
class LoopFailure:
    explanation: FailureExplanation


class LoopGuard(Protocol):
    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[LoopReminder, LoopFailure]]: ...

    def reset(self) -> None: ...
