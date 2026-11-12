from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import auto_initialize
from . import (
    dsh_workspace_impl,
    dsh_telemetry_impl,
    dsh_harness_impl,
)

# Contract: Constituent modules for the dsh assembly.
CONSTITUENTS = (
    dsh_workspace_impl,
    dsh_telemetry_impl,
    dsh_harness_impl,
)


# Contract: Initializes the dsh assembly component and its constituents.
__initialize__ = auto_initialize()
_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_asm assembly library
# --- END CLEANROOM METADATA ---
