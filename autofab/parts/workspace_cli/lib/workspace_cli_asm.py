from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import auto_initialize
from . import (
    coverage_impl,
    check_impl,
    commands_impl,
    dirtiness_impl,
    pending_impl,
    cli_tool_impl,
    work_impl,
)

CONSTITUENTS = (
    coverage_impl,
    check_impl,
    commands_impl,
    dirtiness_impl,
    pending_impl,
    cli_tool_impl,
    work_impl,
)


# Contract: Assembles tool and inspection services into the tools package on the system lifecycle tier by delegating to constituents.
__initialize__ = auto_initialize()
_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:55:45Z
# CHANGE: Delegate assembly initialization to CONSTITUENTS on the system tier instead of registering the constituent singleton directly
# --- END CLEANROOM METADATA ---
