from __future__ import annotations
from typing import Optional
from .lifecycle import LifecycleRegistry
from . import sandbox_change_summary_validator_impl
from . import sandbox_file_editor_impl
from . import sandbox_file_reader_impl
from . import sandbox_guide_delivery_impl
from . import sandbox_impl
from . import sandbox_run_control_impl
from . import tool_provider_impl

CONSTITUENTS = (
    sandbox_impl,
    sandbox_file_reader_impl,
    sandbox_file_editor_impl,
    sandbox_run_control_impl,
    sandbox_guide_delivery_impl,
    sandbox_change_summary_validator_impl,
    tool_provider_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
