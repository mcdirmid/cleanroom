from __future__ import annotations
from typing import Optional
from .lifecycle import LifecycleRegistry
from . import agent_asm
from . import dag_asm
from . import sandbox_asm
from . import bazel_graph_storage_impl
from . import bazel_manifest_loader_impl
from . import bazel_model_config_impl
from . import bazel_node_config_impl
from . import bazel_node_id_utils_impl
from . import bazel_runner_impl
from . import runner_logger_impl

CONSTITUENTS = (
    bazel_runner_impl,
    bazel_manifest_loader_impl,
    bazel_graph_storage_impl,
    bazel_node_id_utils_impl,
    bazel_model_config_impl,
    bazel_node_config_impl,
    runner_logger_impl,
    agent_asm,
    dag_asm,
    sandbox_asm,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
