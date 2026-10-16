# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_asm assembly module
# CODE_HASH: b47e9b176c83
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import (
    subagent_coordinator_impl,
    subagent_harness_impl,
    subagent_tool_impl,
)

CONSTITUENTS = (
    subagent_coordinator_impl,
    subagent_harness_impl,
    subagent_tool_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the subagent assembly component and its constituents."""
    for constituent in CONSTITUENTS:
        constituent.__initialize__(registry)


_initialize_ = __initialize__
