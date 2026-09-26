from typing import Mapping, Optional, Self, Sequence
from framework import LifecycleScope, operation, override, singleton_type
import agent_config
import agent_node_config
import agent_session
import dag_storage
import dag_subgraph
import mcp_session

@singleton_type('system')
class RoleSessionManager(mcp_session.RoleSessionManager):
    """System service implementation maintaining active role agent sessions.

    GROUNDING_ARGUMENT:
    - System singleton initiating agent session phase scopes, setting role config, configuring unit roots on DAG subgraphs, and tracking active sessions.
    """

    @property
    @override
    def active_sessions(self) -> Mapping[mcp_session.ConversationId, mcp_session.RoleAgentSession]:
        """
        GROUNDING_IMPLEMENTS:
        - knows("active_sessions", Mapping[mcp_session.ConversationId, mcp_session.RoleAgentSession]): Exposes all registered active sessions.
        """
        ...

    @operation
    @override
    def register_session(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str) -> LifecycleScope:
        """
        GROUNDING_PROVISIONS:
        - action("register_session", LifecycleScope): Initiates session scope and records session as active.

        GROUNDING_ARGUMENT:
        - action("register_session", Self) :- action("begin_phase", agent_session), configures("role", agent_node_config.RoleConfig), configures("unit_root", dag_subgraph.DagSubgraph).
        """
        ...

    @operation
    @override
    def deregister_session(self, conversation_id: mcp_session.ConversationId) -> None:
        """
        GROUNDING_PROVISIONS:
        - action("deregister_session", None): Closes session scope and releases held resources.

        GROUNDING_ARGUMENT:
        - action("deregister_session", Self) :- action("close", LifecycleScope).
        """
        ...

    @operation
    @override
    def get_session_scope(self, conversation_id: mcp_session.ConversationId) -> Optional[LifecycleScope]:
        """
        GROUNDING_IMPLEMENTS:
        - action("get_session_scope", Optional[LifecycleScope]): Retrieves session phase scope.
        """
        ...

    @operation
    @override
    def touch_session(self, conversation_id: mcp_session.ConversationId) -> None:
        """
        GROUNDING_IMPLEMENTS:
        - action("touch_session", None): Updates session activity timestamp.
        """
        ...

    @operation
    @override
    def set_session_status(self, conversation_id: mcp_session.ConversationId, status: mcp_session.SessionStatus) -> None:
        """
        GROUNDING_IMPLEMENTS:
        - action("set_session_status", None): Transitions session status.
        """
        ...

    @operation
    @override
    def get_session(self, conversation_id: mcp_session.ConversationId) -> Optional[mcp_session.RoleAgentSession]:
        """
        GROUNDING_IMPLEMENTS:
        - action("get_session", Optional[mcp_session.RoleAgentSession]): Retrieves session record by conversation identifier.
        """
        ...

@singleton_type('agent_session')
class RoleConfig(agent_node_config.RoleConfig):
    """Session-scoped role configuration.

    GROUNDING_ARGUMENT:
    - Session singleton holding active role label and assigned DAG nodes within the agent session scope.
    """

    @property
    @override
    def role(self) -> str:
        """
        GROUNDING_IMPLEMENTS:
        - knows("role", str): Active role label.
        """
        ...

    @property
    @override
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        """
        GROUNDING_IMPLEMENTS:
        - knows("nodes", Sequence[dag_storage.DagNode]): Active nodes assigned.
        """
        ...

    @property
    @override
    def version(self) -> int:
        """
        GROUNDING_IMPLEMENTS:
        - knows("version", int): Version counter.
        """
        ...

    @operation
    def set_role(self, role: str) -> None:
        """
        GROUNDING_IMPLEMENTS:
        - action("set_role", None): Updates role label.
        """
        ...

    @operation
    @override
    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """
        GROUNDING_IMPLEMENTS:
        - action("set_nodes", None): Updates assigned nodes and increments version counter.
        """
        ...
