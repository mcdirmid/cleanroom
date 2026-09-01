from typing import Optional
from .dag_storage import DagStorage, NodeId, DagMessage, MessageContent
from .dag_cleaner import DagCleaner
from .dag_node_cleaner import NodeCleaner
from .runner_logger import RunnerLogger, LogEvent
from .manifest_node_loader import ManifestLoader
from .build_runner import BuildRunner, BuildResult


class BuildRunnerImpl(BuildRunner):
    def __init__(
        self,
        storage: DagStorage,
        cleaner: DagCleaner,
        node_cleaner: NodeCleaner,
        logger: RunnerLogger,
        manifest_loader: ManifestLoader,
    ) -> None:
        self.storage = storage
        self.cleaner = cleaner
        self.node_cleaner = node_cleaner
        self.logger = logger
        self.manifest_loader = manifest_loader

    def run_cleaning_pass(self, root: NodeId) -> BuildResult:
        self.logger.log(
            LogEvent(
                name="pass_started",
                summary=f"Starting cleaning pass for {root}",
                transcript=f"Cleaning pass started for root node {root}",
            )
        )
        try:
            self.cleaner.clean_subgraph(root, self.storage, self.node_cleaner)
        except Exception as e:
            self.logger.log(
                LogEvent(
                    name="pass_failed",
                    summary=f"Cleaning pass failed for {root}: {e}",
                    transcript=f"Cleaning pass failed for {root}: {e}",
                )
            )
            return BuildResult(success=False, summary=f"Cleaning pass failed: {e}")
        return BuildResult(success=True, summary="Cleaning pass completed successfully")

    def mark_node_dirty(self, target: NodeId, message: MessageContent) -> None:
        self.storage.queue_pending_messages(target, [DagMessage(content=message)])

    def inject_node_feedback(self, target: NodeId, feedback: MessageContent) -> None:
        self.storage.queue_pending_messages(target, [DagMessage(content=feedback)])

    def broadcast_node_change(self, origin: NodeId, change: MessageContent) -> None:
        msg = DagMessage(content=change, sender=origin)
        for rdep in self.storage.get_reverse_dependencies(origin):
            self.storage.queue_pending_messages(rdep, [msg])
