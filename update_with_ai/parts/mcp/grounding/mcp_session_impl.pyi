from typing import Mapping, Optional, Sequence
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
- Validates that conversation_id is absent from active_sessions, calls begin_phase for agent_session tier, configures imported agent_config.AgentConfig.is_mcp_mode to True, sets role on imported agent_node_config.RoleConfig, and sets target unit root on imported dag_subgraph.DagSubgraph with a root node constructed for the unit address and role address in imported dag_storage within the activated scope when no target is set or the root node is not an existing dependency in the target subgraph, loading reachable target manifests into dag storage via imported bazel_manifest_loader when available.
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

@singleton_type('agent_session')
class RoleConfig(agent_node_config.RoleConfig):
    """
PURPOSE:
Implements role config presenting the active role, nodes, and version

GROUNDING_ARGUMENT:
- Maintains active node references, role, and version in self across the agent session execution phase, requiring no external singleton dependencies.
"""

    @property
    @override
    def role(self) -> str:
        """
PURPOSE:
Role of the agent session

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config provides the role of the session.

GROUNDING_ARGUMENT:
- Holds the active role configured via set_nodes or set_role when the agent session phase is initiated.
"""
        ...

    @property
    @override
    def nodes(self) -> Sequence[dag_storage.Node]:
        """
PURPOSE:
Sequence of nodes currently being cleaned in the agent session

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config provides the sequence of nodes currently being cleaned in the agent session.

GROUNDING_ARGUMENT:
- Holds the active Node sequence configured via set_nodes when the agent session phase is initiated.
"""
        ...

    @property
    @override
    def version(self) -> int:
        """
PURPOSE:
Execution version that increments whenever the cleaned nodes change

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config provides an execution version that increments whenever the cleaned nodes change.

GROUNDING_ARGUMENT:
- Holds the integer version incremented by set_nodes when the active nodes change.
"""
        ...

    @operation
    def set_role(self, role: str) -> None:
        """
PURPOSE:
Sets the role of the agent session

GROUNDING_ARGUMENT:
- Receives role as an input parameter and sets the role on self.
"""
        ...

    @operation
    @override
    def set_nodes(self, nodes: Sequence[dag_storage.Node]) -> None:
        """
PURPOSE:
Sets the nodes currently being cleaned in the agent session

INHERITED_REQUIREMENTS:
- [RoleConfig] The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.

GROUNDING_ARGUMENT:
- Receives nodes directly as a positional parameter, sets nodes and role on self, and increments the integer version.
"""
        ...
