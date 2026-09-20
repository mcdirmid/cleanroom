# Requirements specified in mcp_session.pyi

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol
from support.lib.lifecycle import LifecycleScope


class ConversationId(str):
    pass


@dataclass(frozen=True, init=False)
class SessionStatus:
    pass


@dataclass(frozen=True)
class Active(SessionStatus):
    pass


@dataclass(frozen=True)
class Idle(SessionStatus):
    pass


@dataclass(frozen=True)
class Terminated(SessionStatus):
    pass


@dataclass(frozen=True)
class RoleAgentSession:
    conversation_id: ConversationId
    role_address: str
    unit_root: str
    scope: LifecycleScope
    last_active_timestamp: float
    status: SessionStatus


class RoleSessionManager(Protocol):
    @property
    def active_sessions(self) -> Mapping[ConversationId, RoleAgentSession]: ...

    def register_session(
        self,
        conversation_id: ConversationId,
        role_address: str,
        unit_root: str,
    ) -> LifecycleScope: ...

    def deregister_session(self, conversation_id: ConversationId) -> None: ...

    def get_session_scope(
        self, conversation_id: ConversationId
    ) -> Optional[LifecycleScope]: ...

    def touch_session(self, conversation_id: ConversationId) -> None: ...

    def set_session_status(
        self, conversation_id: ConversationId, status: SessionStatus
    ) -> None: ...

    def get_session(
        self, conversation_id: ConversationId
    ) -> Optional[RoleAgentSession]: ...
