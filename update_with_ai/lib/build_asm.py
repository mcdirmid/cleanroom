"""Build runner assembly wiring graph storage, logger, DAG cleaner, and node cleaner."""

import os
from typing import Optional
from .build_agent_config import ConfigTarget
from .build_runner_impl import BuildRunnerImpl
from .build_message_store_impl import BuildMessageStoreImpl
from .bazel_node_id_utils_impl import BazelNodeIdUtilsImpl
from .build_graph_storage_impl import BuildGraphStorageImpl
from .manifest_node_loader_impl import ManifestLoaderImpl
from .runner_logger_impl import RunnerLoggerImpl
from .dag_cleaner_impl import DagCleanerImpl
from .agent_node_cleaner_asm import AgentNodeCleanerAsm


class BuildAsm(BuildRunnerImpl):
    def __init__(
        self,
        config_target: Optional[ConfigTarget] = None,
        workspace_root: str = "",
    ) -> None:
        effective_ws = workspace_root or os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
        node_id_utils = BazelNodeIdUtilsImpl()
        message_store = BuildMessageStoreImpl(workspace_root=effective_ws, node_id_utils=node_id_utils)
        storage = BuildGraphStorageImpl(message_store=message_store)
        manifest_loader = ManifestLoaderImpl(node_id_utils=node_id_utils)
        logger = RunnerLoggerImpl(
            transcript_file_path=os.path.join(effective_ws, "agent_loop.log")
        )
        cleaner = DagCleanerImpl()
        node_cleaner = AgentNodeCleanerAsm(
            config_target=config_target, storage=storage, logger=logger
        )
        super().__init__(
            storage=storage,
            cleaner=cleaner,
            node_cleaner=node_cleaner,
            logger=logger,
            manifest_loader=manifest_loader,
        )
