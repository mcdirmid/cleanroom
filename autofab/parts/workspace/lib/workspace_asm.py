from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import auto_initialize
from . import (
    provision_impl,
    role_registry_impl,
    roles_impl,
    scaffold_impl,
    stub_impl,
    sync_impl,
)

# Contract: Declares assembly constituents for the workspace tier.
CONSTITUENTS = (
    roles_impl,
    role_registry_impl,
    scaffold_impl,
    provision_impl,
    stub_impl,
    sync_impl,
)


# Contract: Initializes workspace assembly component and delegates registration to all constituent modules.
__initialize__ = auto_initialize()
_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:04:06Z
# CHANGE: Delegate assembly initialization through CONSTITUENTS instead of re-registering each constituent singleton inline
# --- END CLEANROOM METADATA ---
