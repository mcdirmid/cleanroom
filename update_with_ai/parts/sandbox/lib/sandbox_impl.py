# Requirements specified in sandbox_impl.pyi
from typing import Optional
from update_with_ai.parts.agent.lib.agent_session import agent_session
from . import sandbox
from . import sandbox_file_editor
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class Sandbox(sandbox.Sandbox, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def has_modifications(self) -> bool:
        # Requirement: Querying file modifications delegates to the edit manager.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        return edit_mgr.has_modifications

    def materialize_startup_templates(self) -> None:
        # Requirement: Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        edit_mgr.materialize_templates()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Sandbox,
        keys=[Sandbox, sandbox.Sandbox],
        tier=agent_session,
    )
