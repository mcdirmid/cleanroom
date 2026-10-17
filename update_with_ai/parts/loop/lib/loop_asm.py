# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T21:19:01Z
# CHANGE: new file
# CODE_HASH: 129a9ec9aeae
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import loop_guard_impl
from . import loop_node_cleaner_impl

CONSTITUENTS = (
    loop_guard_impl,
    loop_node_cleaner_impl,
)

# Contract: Aggregates loop guard repetition tracking, subgraph iteration, and node cleaning orchestration into the loop subsystem assembly.
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__

