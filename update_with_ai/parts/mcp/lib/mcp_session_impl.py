from __future__ import annotations
from typing import Mapping, Optional
import time
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    Singleton,
    begin_phase,
    get_default_registry,
    get_singleton,
    system,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib import dag_subgraph
from . import mcp_session

# Requirements specified in mcp_session_impl.pyi

class RoleSessionManager(mcp_session.RoleSessionManager, Singleton):
    tier = system

    def __init__(self) -> None:
        self._sessions: dict[mcp_session.ConversationId, mcp_session.RoleAgentSession] = {}

    @property
    def active_sessions(self) -> Mapping[mcp_session.ConversationId, mcp_session.RoleAgentSession]:
        return dict(self._sessions)

    def register_session(
        self,
        conversation_id: mcp_session.ConversationId,
        role_address: str,
        unit_root: str,
    ) -> LifecycleScope:
        if conversation_id in self._sessions:
            raise ValueError(f"Session '{conversation_id}' already registered")
        scope = begin_phase(agent_session)
        with scope.activate():
            try:
                agent_cfg = scope.get_singleton(agent_config.AgentConfig)
                if hasattr(agent_cfg, "is_mcp_mode"):
                    setattr(agent_cfg, "is_mcp_mode", True)
                if hasattr(agent_cfg, "_is_mcp_mode"):
                    setattr(agent_cfg, "_is_mcp_mode", True)
            except LookupError:
                pass

            try:
                role_cfg = scope.get_singleton(agent_node_config.RoleConfig)
                if hasattr(role_cfg, "set_role"):
                    getattr(role_cfg, "set_role")(role_address)
                elif hasattr(role_cfg, "_role"):
                    setattr(role_cfg, "_role", role_address)
                elif hasattr(role_cfg, "role"):
                    setattr(role_cfg, "role", role_address)
            except LookupError:
                pass

            try:
                subgraph = scope.get_singleton(dag_subgraph.DagSubgraph)
                root_node = dag_storage.Node(unit_address=unit_root, role_address=role_address)
                subgraph.set_target(root_node)
            except LookupError:
                pass

        session = mcp_session.RoleAgentSession(
            conversation_id=conversation_id,
            role_address=role_address,
            unit_root=unit_root,
            scope=scope,
            last_active_timestamp=time.time(),
            status=mcp_session.Active(),
        )
        self._sessions[conversation_id] = session
        return scope

    def deregister_session(self, conversation_id: mcp_session.ConversationId) -> None:
        session = self._sessions.get(conversation_id)
        if session is None:
            raise ValueError(f"Session '{conversation_id}' not found")
        session.scope.close()
        del self._sessions[conversation_id]

    def get_session_scope(self, conversation_id: mcp_session.ConversationId) -> Optional[LifecycleScope]:
        session = self._sessions.get(conversation_id)
        return session.scope if session is not None else None

    def touch_session(self, conversation_id: mcp_session.ConversationId) -> None:
        session = self._sessions.get(conversation_id)
        if session is not None:
            self._sessions[conversation_id] = mcp_session.RoleAgentSession(
                conversation_id=session.conversation_id,
                role_address=session.role_address,
                unit_root=session.unit_root,
                scope=session.scope,
                last_active_timestamp=time.time(),
                status=mcp_session.Active(),
            )

    def set_session_status(self, conversation_id: mcp_session.ConversationId, status: mcp_session.SessionStatus) -> None:
        session = self._sessions.get(conversation_id)
        if session is not None:
            self._sessions[conversation_id] = mcp_session.RoleAgentSession(
                conversation_id=session.conversation_id,
                role_address=session.role_address,
                unit_root=session.unit_root,
                scope=session.scope,
                last_active_timestamp=session.last_active_timestamp,
                status=status,
            )

    def get_session(self, conversation_id: mcp_session.ConversationId) -> Optional[mcp_session.RoleAgentSession]:
        return self._sessions.get(conversation_id)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RoleSessionManager,
        keys=[RoleSessionManager, mcp_session.RoleSessionManager],
        tier=system,
    )

_initialize_ = __initialize__
