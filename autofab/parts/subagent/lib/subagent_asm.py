from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import auto_initialize
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


# Contract: initializes subagent assembly component and its constituents (subagent_coordinator_impl, subagent_harness_impl, subagent_tool_impl)
__initialize__ = auto_initialize()
_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_asm assembly module
# --- END CLEANROOM METADATA ---
