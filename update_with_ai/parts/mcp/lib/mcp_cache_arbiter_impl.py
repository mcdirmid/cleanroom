from __future__ import annotations
import time
from typing import Optional, Sequence
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from update_with_ai.parts.dag.lib import dag_subgraph
from . import mcp_cache_arbiter
from . import mcp_session

# Requirements specified in mcp_cache_arbiter_impl.pyi

class CacheArbiter(mcp_cache_arbiter.CacheArbiter, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def evaluate_session_readiness(
        self, conversation_id: mcp_session.ConversationId
    ) -> mcp_cache_arbiter.CacheRoutingAction:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        session = session_mgr.get_session(conversation_id)
        if session is None or not isinstance(session.status, mcp_session.Idle):
            return mcp_cache_arbiter.NoRoutingAction()

        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        ready_nodes = subgraph.next_ready_batch()
        matching_ready = [n for n in ready_nodes if n.role_address == session.role_address]
        if not matching_ready:
            return mcp_cache_arbiter.NoRoutingAction()

        elapsed = time.time() - session.last_active_timestamp
        if elapsed <= 900.0:
            prompt = (
                f"Ready work is available for role '{session.role_address}'. "
                "Please call 'get_work' to retrieve your next batch of tasks."
            )
            return mcp_cache_arbiter.WarmCacheWakeup(
                conversation_id=conversation_id,
                role_address=session.role_address,
                wakeup_prompt=prompt,
            )
        else:
            prompt = (
                f"Cache window expired for conversation '{conversation_id}' "
                f"(elapsed {elapsed:.1f}s > 900s). Terminate worker and spawn a fresh sub-agent "
                f"for role '{session.role_address}' at unit root '{session.unit_root}'."
            )
            return mcp_cache_arbiter.ColdCacheRecycle(
                conversation_id=conversation_id,
                role_address=session.role_address,
                unit_root=session.unit_root,
                recycle_prompt=prompt,
            )

    def evaluate_all_idle_sessions(self) -> Sequence[mcp_cache_arbiter.CacheRoutingAction]:
        session_mgr = get_singleton(mcp_session.RoleSessionManager)
        actions: list[mcp_cache_arbiter.CacheRoutingAction] = []
        for conv_id, session in session_mgr.active_sessions.items():
            if isinstance(session.status, mcp_session.Idle):
                action = self.evaluate_session_readiness(conv_id)
                if not isinstance(action, mcp_cache_arbiter.NoRoutingAction):
                    actions.append(action)
        return tuple(actions)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        CacheArbiter,
        keys=[CacheArbiter, mcp_cache_arbiter.CacheArbiter],
        tier=system,
    )

_initialize_ = __initialize__
