from dataclasses import dataclass
from typing import Mapping, Optional, Protocol
from framework import LifecycleScope, data_type, operation, singleton_type, variant

@data_type
class ConversationId(str):
    """
PURPOSE:
Identifies a sub-agent conversation, wrapping a string value
"""
    ...

@dataclass(frozen=True, init=False)
@data_type
class SessionStatus:
    """
PURPOSE:
Classifies the operational state of a role sub-agent session
"""
    ...

@dataclass(frozen=True)
@variant
class Active(SessionStatus):
    """
PURPOSE:
Classifies an active session currently executing or ready for interaction turns
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Idle(SessionStatus):
    """
PURPOSE:
Classifies an idle session waiting for upstream tasks
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Terminated(SessionStatus):
    """
PURPOSE:
Classifies a terminated session that has concluded
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@data_type
class RoleAgentSession:
    """
PURPOSE:
Records the runtime state of a sub-agent session
"""

    def __init__(self, conversation_id: ConversationId, role_address: str, unit_root: str, scope: LifecycleScope, last_active_timestamp: float, status: SessionStatus) -> None:
        ...

    @property
    def conversation_id(self) -> ConversationId:
        """
PURPOSE:
Uniquely addresses the sub-agent conversation
"""
        ...

    @property
    def role_address(self) -> str:
        """
PURPOSE:
Specifies the engineering role label of the session
"""
        ...

    @property
    def unit_root(self) -> str:
        """
PURPOSE:
Specifies the target unit sub-graph root label
"""
        ...

    @property
    def scope(self) -> LifecycleScope:
        """
PURPOSE:
Governs session-scoped services
"""
        ...

    @property
    def last_active_timestamp(self) -> float:
        """
PURPOSE:
Records the time of the most recent interaction turn
"""
        ...

    @property
    def status(self) -> SessionStatus:
        """
PURPOSE:
Provides the current operational status of the session
"""
        ...

@singleton_type('system')
class RoleSessionManager(Protocol):
    """
PURPOSE:
System service that maintains active role agent sessions

FRESH_REQUIREMENTS:
- Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active.
- Deregistering a session closes the session scope, releasing held resources and file locks, and removes the session from the active registry.
- Exposes all currently registered sessions mapped by conversation identifier.
"""

    @property
    def active_sessions(self) -> Mapping[ConversationId, RoleAgentSession]:
        """
PURPOSE:
Exposes all currently registered sessions mapped by conversation identifier
"""
        ...

    @operation
    def register_session(self, conversation_id: ConversationId, role_address: str, unit_root: str) -> LifecycleScope:
        """
PURPOSE:
Registers a role agent session, creating and opening an agent session phase scope
"""
        ...

    @operation
    def deregister_session(self, conversation_id: ConversationId) -> None:
        """
PURPOSE:
Deregisters a session and closes its lifecycle scope
"""
        ...

    @operation
    def get_session_scope(self, conversation_id: ConversationId) -> Optional[LifecycleScope]:
        """
PURPOSE:
Retrieves the open lifecycle scope for a conversation
"""
        ...

    @operation
    def touch_session(self, conversation_id: ConversationId) -> None:
        """
PURPOSE:
Updates the last active timestamp for a session to the current time
"""
        ...

    @operation
    def set_session_status(self, conversation_id: ConversationId, status: SessionStatus) -> None:
        """
PURPOSE:
Transitions the operational status of a registered session
"""
        ...

    @operation
    def get_session(self, conversation_id: ConversationId) -> Optional[RoleAgentSession]:
        """
PURPOSE:
Retrieves the role agent session record for a conversation
"""
        ...
