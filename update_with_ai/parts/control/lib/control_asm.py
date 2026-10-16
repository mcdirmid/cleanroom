# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:54Z
# CHANGE: Delegate assembly initialization to CONSTITUENTS instead of registering constituent singletons inline
# CODE_HASH: a4b370b77fb6
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import (
    control_attribution_impl,
    control_coordinate_impl,
    control_submit_impl,
    control_verification_impl,
    control_work_scheduler_impl,
)

CONSTITUENTS = (
    control_attribution_impl,
    control_coordinate_impl,
    control_submit_impl,
    control_verification_impl,
    control_work_scheduler_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the control assembly component by delegating to its constituents."""
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)


_initialize_ = __initialize__
