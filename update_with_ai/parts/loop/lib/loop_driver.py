from dataclasses import dataclass
from typing import Protocol
from . import loop_conversation
from update_with_ai.parts.sandbox.lib import tool_provider


@dataclass(frozen=True)
class LoopOutcome:
    response: tool_provider.ToolResponse
    conversation: loop_conversation.ModelRequest


class LoopDriver(Protocol):
    def run(self) -> LoopOutcome: ...
