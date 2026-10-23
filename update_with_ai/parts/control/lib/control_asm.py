from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import (
    attribution_impl,
    coordinate_impl,
    submit_impl,
    verification_impl,
    work_scheduler_impl,
)

CONSTITUENTS = (
    attribution_impl,
    coordinate_impl,
    submit_impl,
    verification_impl,
    work_scheduler_impl,
)


# Contract: Initializes the control assembly component by delegating to its constituents.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the control assembly component by delegating to its constituents."""
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)


_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:54Z
# CHANGE: Delegate assembly initialization to CONSTITUENTS instead of registering constituent singletons inline
# --- END CLEANROOM METADATA ---
