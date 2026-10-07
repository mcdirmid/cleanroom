# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T15:15:00Z
# CHANGE: implement singleton registration in tools_asm
# CODE_HASH: 04f55d701b65
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
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
        tier=agent_session.agent_session,
    )
