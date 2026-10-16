# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:25:00Z
# CHANGE: Define storage_asm library implementation
# CODE_HASH: ac603acd403f
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import (
    src_metadata_impl,
    src_storage_impl,
)

CONSTITUENTS = (
    src_metadata_impl,
    src_storage_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the storage assembly component by delegating to its constituents."""
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)

_initialize_ = __initialize__
