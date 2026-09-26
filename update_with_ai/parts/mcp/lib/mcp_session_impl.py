from __future__ import annotations
from typing import Any, Mapping, Optional, Sequence, cast
import time
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
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

class RoleConfig(agent_node_config.RoleConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._role: str = ""
        self._nodes: Sequence[dag_storage.DagNode] = ()
        self._version: int = 0

    @property
    def role(self) -> str:
        return self._role

    def set_role(self, role: str) -> None:
        self._role = role

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        return self._nodes

    @property
    def version(self) -> int:
        return self._version

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._nodes = tuple(nodes)
        self._version += 1


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
                try:
                    setattr(agent_cfg, "is_mcp_mode", True)
                except (AttributeError, TypeError):  # pragma: no cover (assumption: is_mcp_mode writable)
                    pass  # pragma: no cover (assumption: is_mcp_mode writable)
                if hasattr(agent_cfg, "_is_mcp_mode"):
                    setattr(agent_cfg, "_is_mcp_mode", True)
            except LifecycleResolutionError:  # pragma: no cover (assumption: AgentConfig bound in system)
                pass  # pragma: no cover (assumption: AgentConfig bound in system)

            try:
                role_cfg = scope.get_singleton(agent_node_config.RoleConfig)
                if hasattr(role_cfg, "set_role"):
                    getattr(role_cfg, "set_role")(role_address)
            except LifecycleResolutionError:  # pragma: no cover (assumption: RoleConfig bound in session)
                pass  # pragma: no cover (assumption: RoleConfig bound in session)

            try:
                subgraph = scope.get_singleton(dag_subgraph.DagSubgraph)
                root_node = dag_storage.DagNode(unit_address=unit_root, role_address=role_address)
                try:
                    storage = scope.get_singleton(dag_storage.DagStorage)
                    from update_with_ai.parts.bazel.lib import bazel_manifest_loader
                    manifest_loader = scope.get_singleton(bazel_manifest_loader.BazelManifestLoader)
                    visited: set[dag_storage.DagNode] = set()
                    queue: list[dag_storage.DagNode] = [root_node]
                    while queue:
                        curr = queue.pop(0)
                        if curr in visited:
                            continue
                        visited.add(curr)
                        manifest = manifest_loader.get_manifest(curr)
                        if manifest is not None:
                            manifest_loader.load_manifest(manifest, cast(Any, storage))
                        for dep in storage.get_dependencies(curr):
                            if dep.node not in visited:
                                queue.append(dep.node)
                except Exception:
                    pass
                current_root = getattr(subgraph, "_root", getattr(subgraph, "target", None))
                current_nodes = getattr(subgraph, "_nodes", None)
                if current_root is None or current_nodes is None or root_node not in current_nodes:
                    subgraph.set_target(root_node)
            except LifecycleResolutionError:  # pragma: no cover (assumption: DagSubgraph bound in system)
                pass  # pragma: no cover (assumption: DagSubgraph bound in system)

        session = mcp_session.RoleAgentSession(
            conversation_id=conversation_id,
            role_address=role_address,
            unit_root=unit_root,
            scope=scope,
            last_active_timestamp=time.time(),
            status=mcp_session.ActiveSession(),
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
                status=mcp_session.ActiveSession(),
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
    reg.register_singleton(
        RoleConfig,
        keys=[RoleConfig, agent_node_config.RoleConfig],
        tier=agent_session,
    )

_initialize_ = __initialize__
