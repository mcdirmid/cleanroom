"""Tests for build_runner_impl derived from LLS."""

import unittest
from typing import Sequence, Any, Optional
from lib.dag_storage import NodeId, DagMessage, PendingMessage, DagStorage, NodeData
from lib.dag_cleaner import DagCleaner
from lib.dag_node_cleaner import NodeCleaner
from lib.runner_logger import RunnerLogger, LogEvent
from lib.build_graph_storage import BuildGraphStorage, NodeDefinition
from lib.manifest_node_loader import ManifestLoader, ManifestContent
from lib.build_runner import BuildResult
from lib.build_runner_impl import BuildRunnerImpl


class MockStorage(DagStorage):
    def __init__(self) -> None:
        self.dirty_nodes: set[str] = set()
        self.queued_messages: dict[str, list[DagMessage]] = {}
        self.reverse_deps: dict[str, list[str]] = {}

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return []

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.reverse_deps.get(node, [])

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        return self.queued_messages.get(node, [])

    def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None:
        if node not in self.queued_messages:
            self.queued_messages[node] = []
        self.queued_messages[node].extend(messages)
        self.dirty_nodes.add(node)

    def clear_pending_messages(self, node: NodeId) -> None:
        self.queued_messages[node] = []
        self.dirty_nodes.discard(node)

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        pass

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return None

    def mark_dirty(self, node: NodeId) -> None:
        self.dirty_nodes.add(node)

    def is_dirty(self, node: NodeId) -> bool:
        return node in self.dirty_nodes


class MockDagCleaner(DagCleaner):
    def __init__(self) -> None:
        self.cleaned_roots: list[str] = []

    def clean_subgraph(self, root: NodeId, storage: DagStorage, cleaner: NodeCleaner) -> None:
        self.cleaned_roots.append(root)


class MockNodeCleaner(NodeCleaner):
    def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> Any:
        return []


class MockLogger(RunnerLogger):
    def __init__(self) -> None:
        self.events: list[LogEvent] = []

    def log(self, event: LogEvent) -> None:
        self.events.append(event)


class MockManifestLoader(ManifestLoader):
    def load_manifest(self, content: ManifestContent, storage: BuildGraphStorage) -> Sequence[NodeDefinition]:
        return []


class BuildRunnerImplTest(unittest.TestCase):
    def test_build_result_dataclass(self) -> None:
        """Tests Data Types: BuildResult dataclass instantiation."""
        res = BuildResult(success=True, summary="Pass completed")
        self.assertTrue(res.success)
        self.assertEqual(res.summary, "Pass completed")

    def test_run_cleaning_pass_and_logging(self) -> None:
        """Tests CUJ for executing a cleaning pass and logging events.

        Checks postconditions: delegates root cleaning to DagCleaner, logs pass events, and returns BuildResult.
        """
        storage = MockStorage()
        cleaner = MockDagCleaner()
        node_cleaner = MockNodeCleaner()
        logger = MockLogger()
        manifest_loader = MockManifestLoader()
        runner = BuildRunnerImpl(
            storage=storage,
            cleaner=cleaner,
            node_cleaner=node_cleaner,
            logger=logger,
            manifest_loader=manifest_loader,
        )

        res = runner.run_cleaning_pass("//pkg:root")
        self.assertEqual(cleaner.cleaned_roots, ["//pkg:root"])
        self.assertIsInstance(res, BuildResult)
        self.assertTrue(len(logger.events) > 0)

    def test_mark_node_dirty_and_inject_feedback(self) -> None:
        """Tests CUJ for marking nodes dirty and injecting feedback messages.

        Checks postconditions: queues messages on target node and marks node dirty in storage.
        """
        storage = MockStorage()
        cleaner = MockDagCleaner()
        node_cleaner = MockNodeCleaner()
        logger = MockLogger()
        manifest_loader = MockManifestLoader()
        runner = BuildRunnerImpl(
            storage=storage,
            cleaner=cleaner,
            node_cleaner=node_cleaner,
            logger=logger,
            manifest_loader=manifest_loader,
        )

        runner.mark_node_dirty("//pkg:target", "check")
        self.assertTrue(storage.is_dirty("//pkg:target"))
        dirty_msgs = storage.get_pending_messages("//pkg:target")
        self.assertTrue(any(m.content == "check" for m in dirty_msgs))

        runner.inject_node_feedback("//pkg:target", "Feedback text")
        msgs = storage.get_pending_messages("//pkg:target")
        self.assertTrue(any(m.content == "Feedback text" for m in msgs))

    def test_broadcast_node_change(self) -> None:
        """Tests CUJ for broadcasting change message to all reverse dependencies.

        Checks postconditions: queues change message on each reverse dependency and marks them dirty.
        """
        storage = MockStorage()
        storage.reverse_deps["//pkg:origin"] = ["//pkg:rdep1", "//pkg:rdep2"]
        cleaner = MockDagCleaner()
        node_cleaner = MockNodeCleaner()
        logger = MockLogger()
        manifest_loader = MockManifestLoader()
        runner = BuildRunnerImpl(
            storage=storage,
            cleaner=cleaner,
            node_cleaner=node_cleaner,
            logger=logger,
            manifest_loader=manifest_loader,
        )

        runner.broadcast_node_change("//pkg:origin", "API change")
        self.assertTrue(storage.is_dirty("//pkg:rdep1"))
        self.assertTrue(storage.is_dirty("//pkg:rdep2"))
        msgs1 = storage.get_pending_messages("//pkg:rdep1")
        msgs2 = storage.get_pending_messages("//pkg:rdep2")
        self.assertTrue(any(m.content == "API change" for m in msgs1))
        self.assertTrue(any(m.content == "API change" for m in msgs2))

    def test_run_cleaning_pass_failure(self) -> None:
        """Tests Failure Handling when a node cleaning fails during a pass.

        Checks postconditions: halts pass and returns a failing BuildResult.
        """
        class FailingDagCleaner(DagCleaner):
            def clean_subgraph(self, root: NodeId, storage: DagStorage, cleaner: NodeCleaner) -> None:
                raise RuntimeError("Node compilation failure")

        storage = MockStorage()
        cleaner = FailingDagCleaner()
        node_cleaner = MockNodeCleaner()
        logger = MockLogger()
        manifest_loader = MockManifestLoader()
        runner = BuildRunnerImpl(
            storage=storage,
            cleaner=cleaner,
            node_cleaner=node_cleaner,
            logger=logger,
            manifest_loader=manifest_loader,
        )

        res = runner.run_cleaning_pass("//pkg:root")
        self.assertIsInstance(res, BuildResult)
        self.assertFalse(res.success)


if __name__ == "__main__":
    unittest.main()
