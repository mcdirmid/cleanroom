# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-11T04:58:56Z
# CHANGE: Restrict assembly CONSTITUENTS to exactly the constituent modules declared in the grounding specification
# CODE_HASH: 9edb479d3655
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import sandbox_file_editor_impl
from . import sandbox_file_reader_impl
from . import sandbox_guide_delivery_impl
from . import sandbox_impl
from . import sandbox_run_control_impl
from . import template_format_impl
from . import tool_provider_impl

CONSTITUENTS = (
    sandbox_file_editor_impl,
    sandbox_file_reader_impl,
    sandbox_guide_delivery_impl,
    sandbox_impl,
    sandbox_run_control_impl,
    template_format_impl,
    tool_provider_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
