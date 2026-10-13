# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_asm assembly module
# CODE_HASH: f7f79b87fa7f
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import (
    antigravity_coordinator_impl,
    antigravity_harness_impl,
    antigravity_workspace_impl,
)

CONSTITUENTS = (
    antigravity_coordinator_impl,
    antigravity_harness_impl,
    antigravity_workspace_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the antigravity assembly component and its constituents."""
    for constituent in CONSTITUENTS:
        constituent.__initialize__(registry)


_initialize_ = __initialize__
