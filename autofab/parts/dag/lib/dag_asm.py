from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import subgraph_impl

# Contract: Declared constituents forming the dag subsystem assembly.
CONSTITUENTS = (
    subgraph_impl,
)


# Contract: Aggregates topological subgraph queries and bounded visit tracking into the dag subsystem assembly.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Aggregates topological subgraph queries and bounded visit tracking into the dag subsystem assembly."""
    reg = get_default_registry() if registry is None else registry
    for constituent in CONSTITUENTS:
        constituent.__initialize__(reg)

_initialize_ = __initialize__

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:18Z
# CHANGE: Resolve the default lifecycle registry in assembly initialization before delegating to constituents
# --- END CLEANROOM METADATA ---
