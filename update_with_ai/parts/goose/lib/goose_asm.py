# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_asm assembly library
# CODE_HASH: cb98be4a112f
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import (
    goose_workspace_impl,
    goose_harness_impl,
)

CONSTITUENTS = (
    goose_workspace_impl,
    goose_harness_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the goose assembly component and its constituents."""
    for constituent in CONSTITUENTS:
        constituent.__initialize__(registry)


_initialize_ = __initialize__
