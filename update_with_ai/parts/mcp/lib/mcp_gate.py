from __future__ import annotations
from typing import Protocol, Sequence
from dataclasses import dataclass
from . import mcp_session

# Requirements specified in mcp_gate.pyi

@dataclass(frozen=True)
class AccessDecision:
    is_allowed: bool
    reason: str


class AccessGate(Protocol):
    def validate_access(
        self,
        conversation_id: mcp_session.ConversationId,
        tool_name: str,
        file_path: str,
    ) -> AccessDecision:
        ...

    def filter_directory_listing(
        self,
        conversation_id: mcp_session.ConversationId,
        directory_path: str,
        entries: Sequence[str],
    ) -> Sequence[str]:
        ...
