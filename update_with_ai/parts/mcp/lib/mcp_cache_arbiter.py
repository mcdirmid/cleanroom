from __future__ import annotations
from typing import Protocol, Sequence
from dataclasses import dataclass
from . import mcp_session

# Requirements specified in mcp_cache_arbiter.pyi

@dataclass(frozen=True, init=False)
class CacheRoutingAction:
    pass


@dataclass(frozen=True)
class WarmCacheWakeup(CacheRoutingAction):
    conversation_id: mcp_session.ConversationId
    role_address: str
    wakeup_prompt: str


@dataclass(frozen=True)
class ColdCacheRecycle(CacheRoutingAction):
    conversation_id: mcp_session.ConversationId
    role_address: str
    unit_root: str
    recycle_prompt: str


@dataclass(frozen=True)
class NoRoutingAction(CacheRoutingAction):
    pass


class CacheArbiter(Protocol):
    def evaluate_session_readiness(
        self, conversation_id: mcp_session.ConversationId
    ) -> CacheRoutingAction:
        ...

    def evaluate_all_idle_sessions(self) -> Sequence[CacheRoutingAction]:
        ...
