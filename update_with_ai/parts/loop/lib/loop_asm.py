# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T21:19:01Z
# CHANGE: new file
# CODE_HASH: 5f26382e30fd
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import loop_cleaner_impl
from . import loop_guard_impl
from . import loop_node_cleaner_impl
from update_with_ai.parts.openai.lib import openai_conversation_impl
from update_with_ai.parts.openai.lib import openai_driver_impl

CONSTITUENTS = (
    loop_cleaner_impl,
    loop_guard_impl,
    loop_node_cleaner_impl,
    openai_conversation_impl,
    openai_driver_impl,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
