"""Agent runner interface and execution models."""

from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from .tool_provider import ToolProvider, TerminationOutcome
from .conversation_history import ConversationHistory, HistoryMessage
from .loop_guard import LoopGuard
from .runner_logger import RunnerLogger

IterationLimit: TypeAlias = int


@dataclass(frozen=True)
class AgentOutcome:
    termination: TerminationOutcome
    history: Sequence[HistoryMessage]


class AgentRunner(Protocol):
    def run(
        self,
        tool_provider: ToolProvider,
        history: ConversationHistory,
        logger: Optional[RunnerLogger] = None,
        loop_guard: Optional[LoopGuard] = None,
        iteration_limit: IterationLimit = 20,
    ) -> AgentOutcome:
        ...
