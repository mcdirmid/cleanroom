# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:58:56Z
# CHANGE: Restrict assembly CONSTITUENTS to exactly the constituent modules declared in the grounding specification
# CODE_HASH: af81874198e0
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import sandbox_file_editor_impl
from . import sandbox_file_reader_impl
from . import sandbox_guide_delivery_impl
from . import sandbox_run_control_impl
from . import sandbox_submission_impl
from . import template_format_impl
from . import tool_provider_impl

CONSTITUENTS = (
    sandbox_file_editor_impl,
    sandbox_file_reader_impl,
    sandbox_guide_delivery_impl,
    sandbox_run_control_impl,
    sandbox_submission_impl,
    template_format_impl,
    tool_provider_impl,
)

# Contract: sandbox_asm.__initialize__ - aggregates file inspection, guarded editing, execution control, guide delivery, and tool dispatch constituents into sandbox subsystem assembly.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
