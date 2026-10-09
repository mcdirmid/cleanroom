# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: new file
# CODE_HASH: 8d0b25788e27
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation for workspace_registry_impl."""

from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from . import workspace_registry

REGISTRY_FILE = workspace_registry.REGISTRY_FILE
_ROLE_CACHE = workspace_registry._ROLE_CACHE
_parse_pat_to_glob = workspace_registry._parse_pat_to_glob
_build_role_definitions = workspace_registry._build_role_definitions
_load_roles_from_toml_file = workspace_registry._load_roles_from_toml_file
_load_roles_from_build_file = workspace_registry._load_roles_from_build_file
_normalize_role_name = workspace_registry._normalize_role_name


class WorkspaceRegistry(workspace_registry._DefaultWorkspaceRegistry, Singleton):
    """Realizes role configuration resolution and persistent workspace registration."""

    tier = agent_session.agent_session


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkspaceRegistry,
        keys=[workspace_registry.WorkspaceRegistry, WorkspaceRegistry],
        tier=agent_session.agent_session,
    )
