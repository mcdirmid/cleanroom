# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:04:06Z
# CHANGE: Delegate assembly initialization through CONSTITUENTS instead of re-registering each constituent singleton inline
# CODE_HASH: 2b8e0ccd5cd5
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import (
    workspace_provision_impl,
    workspace_registry_impl,
    workspace_roles_impl,
    workspace_scaffold_impl,
    workspace_stub_impl,
    workspace_sync_impl,
)

# Contract: Declares assembly constituents for the workspace tier.
CONSTITUENTS = (
    workspace_roles_impl,
    workspace_registry_impl,
    workspace_scaffold_impl,
    workspace_provision_impl,
    workspace_stub_impl,
    workspace_sync_impl,
)


# Contract: Initializes workspace assembly component and delegates registration to all constituent modules.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the workspace assembly component and its constituents."""
    for constituent in CONSTITUENTS:
        constituent.__initialize__(registry)


_initialize_ = __initialize__
