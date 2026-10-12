# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-09T02:23:45Z
# CHANGE: Implement Sandbox in sandbox_impl.py
# CODE_HASH: b15ef226ec2b
# COVERAGE_AUDIT: 2026-10-12T18:21:04Z
# QA_AUDIT: 2026-10-12T18:21:04Z
# --- END CLEANROOM METADATA ---

from typing import Optional
from support.lib.lifecycle import InTier, LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier, agent_session
from . import sandbox
from . import sandbox_file_editor

# Requirements specified in sandbox_impl.pyi

class Sandbox(sandbox.Sandbox, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def has_modifications(self) -> bool:
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        return edit_mgr.has_modifications


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Sandbox,
        keys=[Sandbox, sandbox.Sandbox, InTier[AgentSessionTier]],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
