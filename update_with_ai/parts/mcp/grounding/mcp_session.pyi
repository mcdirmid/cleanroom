from dataclasses import dataclass
from typing import Mapping, Optional, Protocol
from framework import LifecycleScope, data_type, operation, singleton_type, variant

@data_type
class ConversationId(str):
    """Conversation identifier string."""
    ...

@dataclass(frozen=True, init=False)
@data_type
class SessionStatus:
    """Session operational status."""
    ...

@dataclass(frozen=True)
@variant
class ActiveSession(SessionStatus):
    """Active session state."""
    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class IdleSession(SessionStatus):
    """Idle session state."""
    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class TerminatedSession(SessionStatus):
    """Terminated session state."""
    def __init__(self) -> None:
        ...


@dataclass(frozen=True)
@data_type
class RoleAgentSession:
    """Role agent session information."""
    def __init__(self, conversation_id: ConversationId, role_address: str, unit_root: str, scope: LifecycleScope, last_active_timestamp: float, status: SessionStatus) -> None:
        ...

    @property
    def conversation_id(self) -> ConversationId:
        ...

    @property
    def role_address(self) -> str:
        ...

    @property
    def unit_root(self) -> str:
        ...

    @property
    def scope(self) -> LifecycleScope:
        ...

    @property
    def last_active_timestamp(self) -> float:
        ...

    @property
    def status(self) -> SessionStatus:
        ...

@singleton_type('system')
class RoleSessionManager(Protocol):
    """System service that maintains active role agent sessions.

    REQUIREMENTS:
    - Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active.
    - Deregistering a session closes the session scope, releasing held resources and file locks, and removes the session from the active registry.
    - Exposes all currently registered sessions mapped by conversation identifier.

    GROUNDING_PROVISIONS:
    - action("register_session", LifecycleScope): Initiates session scope and records session as active.
    - action("deregister_session", None): Closes session scope and releases held resources.
    - action("get_session_scope", Optional[LifecycleScope]): Retrieves session phase scope.
    - action("touch_session", None): Updates session activity timestamp.
    - action("set_session_status", None): Transitions session status.
    - action("get_session", Optional[RoleAgentSession]): Retrieves session record by conversation identifier.
    - knows("active_sessions", Mapping[ConversationId, RoleAgentSession]): Exposes all registered active sessions.
    """

    @property
    def active_sessions(self) -> Mapping[ConversationId, RoleAgentSession]:
        ...

    @operation
    def register_session(self, conversation_id: ConversationId, role_address: str, unit_root: str) -> LifecycleScope:
        ...

    @operation
    def deregister_session(self, conversation_id: ConversationId) -> None:
        ...

    @operation
    def get_session_scope(self, conversation_id: ConversationId) -> Optional[LifecycleScope]:
        ...

    @operation
    def touch_session(self, conversation_id: ConversationId) -> None:
        ...

    @operation
    def set_session_status(self, conversation_id: ConversationId, status: SessionStatus) -> None:
        ...

    @operation
    def get_session(self, conversation_id: ConversationId) -> Optional[RoleAgentSession]:
        ...
