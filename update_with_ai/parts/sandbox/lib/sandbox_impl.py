# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: c38f35d28191
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox_impl.pyi
from typing import Optional
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.dag.lib import dag_storage
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

    def materialize_templates(self) -> None:
        try:
            storage = get_singleton(dag_storage.DagStorage)
            cfg = get_singleton(agent_node_config.NodeConfig)
            for f in getattr(cfg, "read_write_files", []):
                owning_node = getattr(f, "owning_node", None)
                if owning_node is not None:
                    storage.materialize_template(owning_node)
        except (LookupError, KeyError, RuntimeError, ValueError):
            pass


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Sandbox,
        keys=[Sandbox, sandbox.Sandbox],
        tier=agent_session,
    )
