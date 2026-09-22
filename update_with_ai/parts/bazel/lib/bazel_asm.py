from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import bazel_manifest_loader_impl
from . import bazel_node_config_impl
from . import bazel_storage_impl
from . import bazel_target_impl
from . import file_paths_impl

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
