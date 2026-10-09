from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
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
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
