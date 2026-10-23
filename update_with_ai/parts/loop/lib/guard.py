from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
# Requirements specified in guard.pyi
from dataclasses import dataclass
from typing import Any, Mapping, NewType, Optional, Protocol, Union
from update_with_ai.parts.sandbox.lib import tool_provider

LoopFeedback = NewType("LoopFeedback", str)
FailureExplanation = NewType("FailureExplanation", str)


# Contract: LoopReminder - diagnostic feedback warning an agent of detected repetition.
@dataclass(frozen=True)
class LoopReminder:
    feedback: LoopFeedback


# Contract: LoopFailure - outcome signaling that an agent session has failed due to unresolvable repetition.
@dataclass(frozen=True)
class LoopFailure:
    explanation: FailureExplanation


# Contract: LoopGuard protocol - session service tracking repetitive tool executions and edit oscillations across turns.
class LoopGuard(Singleton[AgentSessionTier], Protocol):
    # Contract: LoopGuard.evaluate - evaluates tool invocation against repetition warning and fatal thresholds.
    def evaluate(
        self,
        tool_name: tool_provider.ToolName,
        arguments: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> Optional[Union[LoopReminder, LoopFailure]]: ...

    # Contract: LoopGuard.reset - clears repetition tracking when a tool execution demonstrates forward progress.
    def reset(self) -> None: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
