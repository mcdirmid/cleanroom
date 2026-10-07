# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: b6f6c35dbb41
# --- END CLEANROOM METADATA ---

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
