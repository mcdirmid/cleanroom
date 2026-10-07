# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T17:05:00Z
# CHANGE: new file
# CODE_HASH: ea364b558f15
# --- END CLEANROOM METADATA ---

"""Cleanroom master root system assembly implementation."""

from __future__ import annotations

from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.control.lib import control_asm
from update_with_ai.parts.core.lib import file_paths_impl
from update_with_ai.parts.systems.lib import bazel_openai_loop_asm
from update_with_ai.parts.tools.lib import tools_asm
from update_with_ai.parts.workspace.lib import workspace_asm

CONSTITUENTS = (
    bazel_openai_loop_asm,
    control_asm,
    file_paths_impl,
    tools_asm,
    workspace_asm,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)


_initialize_ = __initialize__
