# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-11T05:04:06Z
# CHANGE: Delegate assembly initialization through CONSTITUENTS instead of re-registering each constituent singleton inline
# CODE_HASH: f442c97be40f
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import (
    workspace_provision_impl,
    workspace_registry_impl,
    workspace_sync_impl,
    workspace_work_impl,
)

CONSTITUENTS = (
    workspace_registry_impl,
    workspace_provision_impl,
    workspace_sync_impl,
    workspace_work_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the workspace assembly component and its constituents."""
    for constituent in CONSTITUENTS:
        constituent.__initialize__(registry)


_initialize_ = __initialize__
