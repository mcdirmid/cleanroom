# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T22:55:00Z
# CHANGE: core constituents
# CODE_HASH: d163cd923cdd
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import (
    workspace_provision,
    workspace_provision_impl,
    workspace_registry,
    workspace_registry_impl,
    workspace_sync,
    workspace_sync_impl,
    workspace_work,
    workspace_work_impl,
)

CONSTITUENTS = (
    workspace_registry_impl,
    workspace_provision_impl,
    workspace_sync_impl,
    workspace_work_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the workspace assembly component and registers its singletons."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        workspace_registry_impl.WorkspaceRegistry,
        keys=[
            workspace_registry.WorkspaceRegistry,
            workspace_registry_impl.WorkspaceRegistry,
        ],
    )
    reg.register_singleton(
        workspace_provision_impl.WorkspaceProvisioner,
        keys=[
            workspace_provision.WorkspaceProvisioner,
            workspace_provision_impl.WorkspaceProvisioner,
        ],
    )
    reg.register_singleton(
        workspace_sync_impl.WorkspaceSynchronizer,
        keys=[
            workspace_sync.WorkspaceSynchronizer,
            workspace_sync_impl.WorkspaceSynchronizer,
        ],
    )
    reg.register_singleton(
        workspace_work_impl.WorkspaceWorkManager,
        keys=[
            workspace_work.WorkspaceWorkManager,
            workspace_work_impl.WorkspaceWorkManager,
        ],
    )

_initialize_ = __initialize__
