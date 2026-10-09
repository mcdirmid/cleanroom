# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T00:44:00Z
# LAST_CHANGED: 2026-10-08T00:44:00Z
# CHANGE: Remove materialize_templates from Sandbox implementation
# CODE_HASH: 7839be7eafa0
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox_impl.pyi
from typing import Optional
from . import sandbox
from . import sandbox_file_editor
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session


class Sandbox(sandbox.Sandbox, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def has_modifications(self) -> bool:
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        return edit_mgr.has_modifications


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Sandbox,
        keys=[Sandbox, sandbox.Sandbox],
        tier=agent_session,
    )
