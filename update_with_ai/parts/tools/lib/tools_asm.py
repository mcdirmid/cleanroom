# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T21:19:01Z
# CHANGE: new file
# CODE_HASH: 86db72bd90ad
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import (
    tool_coverage,
    tool_coverage_impl,
)

CONSTITUENTS = (
    tool_coverage_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Initializes the tools assembly component and registers its singletons."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        tool_coverage_impl.CoverageEvaluator,
        keys=[tool_coverage.CoverageEvaluator, tool_coverage_impl.CoverageEvaluator],
    )

_initialize_ = __initialize__
