from __future__ import annotations
from typing import Optional
from support.lib.lifecycle import LifecycleRegistry
from . import agent_asm
from . import bazel_graph_storage_impl
from . import bazel_manifest_loader_impl
from . import bazel_model_config_impl
from . import bazel_node_config_impl
from . import bazel_node_id_utils_impl
from . import bazel_runner_impl
from . import dag_asm
from . import file_paths_impl
from . import runner_logger_impl
from . import sandbox_asm

CONSTITUENTS = (
    agent_asm,
    bazel_graph_storage_impl,
    bazel_manifest_loader_impl,
    bazel_model_config_impl,
    bazel_node_config_impl,
    bazel_node_id_utils_impl,
    bazel_runner_impl,
    dag_asm,
    file_paths_impl,
    runner_logger_impl,
    sandbox_asm,
)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    for mod in CONSTITUENTS:
        mod.__initialize__(registry)

_initialize_ = __initialize__
