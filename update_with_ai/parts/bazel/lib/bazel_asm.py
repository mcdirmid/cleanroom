# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: dcba053e3d8b
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import bazel_manifest_loader_impl
from . import bazel_node_config_impl
from . import bazel_storage_impl
from . import bazel_target_impl
from update_with_ai.parts.core.lib import file_paths_impl

CONSTITUENTS = (
    bazel_manifest_loader_impl,
    bazel_node_config_impl,
    bazel_storage_impl,
    bazel_target_impl,
    file_paths_impl,
)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)


_initialize_ = __initialize__
