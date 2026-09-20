from typing import Mapping, Optional
from framework import LifecycleScope, operation, override, singleton_type
import agent_config
import agent_node_config
import agent_session
import dag_storage
import dag_subgraph
import mcp_session

@singleton_type('system')
class RoleSessionManager(mcp_session.RoleSessionManager):
    """
PURPOSE:
Implements role session manager to govern multi-turn sub-agent session scopes and active session registries

INHERITED_REQUIREMENTS:
- [RoleSessionManager] Registering a session initiates an agent session phase scope, sets role on role config, configures unit root on dag subgraph, and records the session as active.
- [RoleSessionManager] Deregistering a session closes the session scope, releasing held resources and file locks, and removes the session from the active registry.
- [RoleSessionManager] Exposes all currently registered sessions mapped by conversation identifier.

GROUNDING_ARGUMENT:
- As a system singleton, RoleSessionManager maintains registered role agent sessions in an internal mapping keyed by ConversationId, managing agent_session lifecycle phase scopes using support.lib.lifecycle.begin_phase and scope.close.
"""

    @property
    @override
    def active_sessions(self) -> Mapping[mcp_session.ConversationId, mcp_session.RoleAgentSession]:
        """
PURPOSE:
Exposes all currently registered sessions mapped by conversation identifier

GROUNDING_ARGUMENT:
- Maintained directly in an internal dictionary mapping ConversationId to RoleAgentSession populated on session registration and evicted on session deregistration.
"""
        ...

    @operation
    @override
    def register_session(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str) -> LifecycleScope:
        """
PURPOSE:
Registers a role agent session, creating and opening an agent session phase scope

GROUNDING_ARGUMENT:
- Validates that conversation_id is absent from active_sessions, calls begin_phase for agent_session tier, configures imported agent_config.AgentConfig.is_mcp_mode to True, sets role on imported agent_node_config.RoleConfig, and sets target unit root on imported dag_subgraph.DagSubgraph with a root node constructed for the unit address and role address in imported dag_storage within the activated scope.
"""
        ...

    @operation
    @override
    def deregister_session(self, conversation_id: mcp_session.ConversationId) -> None:
        """
PURPOSE:
Deregisters a session and closes its lifecycle scope

GROUNDING_ARGUMENT:
- Resolves the session by conversation_id, invokes scope.close on the session LifecycleScope executing singleton teardowns in LIFO order, and removes conversation_id from the active_sessions registry.
"""
        ...

    @operation
    @override
    def get_session_scope(self, conversation_id: mcp_session.ConversationId) -> Optional[LifecycleScope]:
        """
PURPOSE:
Retrieves the open lifecycle scope for a conversation

GROUNDING_ARGUMENT:
- Looks up conversation_id in the internal active_sessions mapping, returning session.scope when present or None when absent.
"""
        ...

    @operation
    @override
    def touch_session(self, conversation_id: mcp_session.ConversationId) -> None:
        """
PURPOSE:
Updates the last active timestamp for a session to the current time

GROUNDING_ARGUMENT:
- Looks up conversation_id in active_sessions and updates last_active_timestamp with the current time, ensuring the status is set to Active.
"""
        ...

    @operation
    @override
    def set_session_status(self, conversation_id: mcp_session.ConversationId, status: mcp_session.SessionStatus) -> None:
        """
PURPOSE:
Transitions the operational status of a registered session

GROUNDING_ARGUMENT:
- Looks up conversation_id in active_sessions and replaces the recorded session record with updated status.
"""
        ...

    @operation
    @override
    def get_session(self, conversation_id: mcp_session.ConversationId) -> Optional[mcp_session.RoleAgentSession]:
        """
PURPOSE:
Retrieves the role agent session record for a conversation

GROUNDING_ARGUMENT:
- Looks up conversation_id in active_sessions, returning the RoleAgentSession record when present or None when absent.
"""
        ...
