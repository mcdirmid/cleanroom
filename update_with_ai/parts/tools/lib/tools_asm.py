# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-11T04:55:45Z
# CHANGE: Delegate assembly initialization to CONSTITUENTS on the system tier instead of registering the constituent singleton directly
# CODE_HASH: b3a749ad8487
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import tool_coverage_impl

CONSTITUENTS = (
    tool_coverage_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the tools assembly component on the system lifecycle tier by delegating to its constituents."""
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)

_initialize_ = __initialize__
