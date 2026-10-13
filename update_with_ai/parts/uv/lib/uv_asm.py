# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-11T05:09:56Z
# CHANGE: Resolve the default lifecycle registry in assembly initialization before delegating to constituents and document the aggregation
# CODE_HASH: b589db914d43
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from update_with_ai.parts.core.lib import file_paths_impl
from . import uv_manifest_loader_impl
from . import uv_node_config_impl
from . import uv_target_impl

CONSTITUENTS = (
    file_paths_impl,
    uv_manifest_loader_impl,
    uv_node_config_impl,
    uv_target_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Aggregates workspace manifest loading, target resolution, file paths resolution, and node configuration implementations into a unified Cleanroom workspace subsystem assembly."""
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)


_initialize_ = __initialize__
