# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 6ae3327d7f19
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for uv_loop_impl aligned with low-level specifications."""

import unittest
from typing import Optional, Sequence, Set
from update_with_ai.parts.uv.lib import uv_manifest_loader
from update_with_ai.parts.uv.lib.uv_loop_impl import (
    Loop as LoopImpl,
    __initialize__,
)
from update_with_ai.parts.loop.lib import loop
from update_with_ai.parts.loop.lib import loop_cleaner
from update_with_ai.parts.loop.lib import loop_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import runner_logger
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton


def _make_dag_node(unit_address: str, role_address: str = "") -> dag_storage.DagNode:
    return dag_storage.DagNode(
        unit_address=dag_storage.UnitAddress(unit_address),
        role_address=dag_storage.RoleAddress(role_address),
    )


class MockRunnerLogger:
    def __init__(self) -> None:
        self.events: list[runner_logger.RunnerLogEvent] = []

    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        self.events.append(event)


class MockManifestLoader:
    def __init__(self) -> None:
        self.manifests: dict[str, uv_manifest_loader.TargetManifest] = {}
        self.loaded: list[dag_storage.DagNode] = []

    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[uv_manifest_loader.TargetManifest]:
        return self.manifests.get(node.unit_address)

    def load_manifest(
        self,
        node: dag_storage.DagNode,
    ) -> None:
        self.loaded.append(node)


class MockDagStorage:
    def __init__(self) -> None:
        self.dirty_nodes: Set[dag_storage.DagNode] = set()
        self.messages: dict[dag_storage.DagNode, list[dag_storage.DagMessage]] = {}
        self.dependencies_map: dict[
            dag_storage.DagNode, Set[dag_storage.DagDependency]
        ] = {}
        self.cleaned_nodes: list[dag_storage.DagNode] = []
        self.cleaned_changes: dict[
            dag_storage.DagNode, Optional[dag_storage.ChangeDescription]
        ] = {}
        self.materialized_nodes: list[dag_storage.DagNode] = []

    def get_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagDependency]:
        return self.dependencies_map.get(node, set())

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        return set(self.messages.get(node, []))

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self.dirty_nodes

    def add_message(
        self, message: dag_storage.DagMessage, to: dag_storage.DagNode
    ) -> None:
        self.messages.setdefault(to, []).append(message)
        self.dirty_nodes.add(to)

    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self.messages.pop(node, None)
        self.dirty_nodes.discard(node)

    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        self.dirty_nodes.add(node)

    def mark_node_clean(
        self,
        node: dag_storage.DagNode,
        change_description: Optional[dag_storage.ChangeDescription] = None,
    ) -> None:
        self.cleaned_nodes.append(node)
        self.cleaned_changes[node] = change_description
        self.clear_messages(node)

    def materialize_template(self, node: dag_storage.DagNode) -> None:
        self.materialized_nodes.append(node)


class MockLoopCleaner:
    def __init__(self, storage: MockDagStorage, should_fail: bool = False) -> None:
        self.cleaned_nodes: list[dag_storage.DagNode] = []
        self.storage = storage
        self.should_fail = should_fail

    def clean(
        self, node: dag_storage.DagNode, cleaner: loop_node_cleaner.NodeCleaner
    ) -> None:
        if self.should_fail:
            raise RuntimeError("Simulated cleaner failure")
        self.cleaned_nodes.append(node)
        cleaner.clean([node])
        self.storage.dirty_nodes.clear()


class MockNodeCleaner:
    def __init__(self) -> None:
        self.cleaned_batches: list[Sequence[dag_storage.DagNode]] = []

    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self.cleaned_batches.append(nodes)


class TestUvLoopImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.logger = MockRunnerLogger()
        self.manifest_loader = MockManifestLoader()
        self.storage = MockDagStorage()
        self.cleaner = MockLoopCleaner(self.storage)
        self.node_cleaner = MockNodeCleaner()

        self.registry.register_instance(
            self.logger, keys=[runner_logger.RunnerLogger], tier="system"
        )
        self.registry.register_instance(
            self.manifest_loader,
            keys=[uv_manifest_loader.UvManifestLoader],
            tier="system",
        )
        self.registry.register_instance(
            self.storage, keys=[dag_storage.DagStorage], tier="system"
        )
        self.registry.register_instance(
            self.cleaner, keys=[loop_cleaner.LoopCleaner], tier="system"
        )
        self.registry.register_instance(
            self.node_cleaner, keys=[loop_node_cleaner.NodeCleaner], tier="system"
        )

    def test_clean_subgraph_happy_path(self) -> None:
        """CUJ: Successful cleaning pass over target subgraph."""
        root = _make_dag_node("//pkg:root", "lib")
        dep = _make_dag_node("//pkg:dep", "lib")
        self.storage.dependencies_map[root] = {
            dag_storage.DagDependency(node=dep, is_silent=False)
        }
        self.storage.dirty_nodes.add(root)
        self.storage.dirty_nodes.add(dep)

        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            result = loop_service.clean_subgraph(root)

            self.assertTrue(result.success)
            self.assertIn("//pkg:root#lib", result.summary)
            # Both nodes were discovered and manifests loaded
            self.assertIn(root, self.manifest_loader.loaded)
            self.assertIn(dep, self.manifest_loader.loaded)

            # Telemetry events emitted
            event_names = [e.event_name for e in self.logger.events]
            self.assertIn("build_pass_start", event_names)
            self.assertIn("build_pass_end", event_names)

    def test_clean_subgraph_cleaner_failure(self) -> None:
        """CUJ: Cleaner failure halts execution and captures error reason."""
        root = _make_dag_node("//pkg:root", "lib")
        self.cleaner.should_fail = True

        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            result = loop_service.clean_subgraph(root)

            self.assertFalse(result.success)
            self.assertIn("Simulated cleaner failure", result.summary)

    def test_clean_subgraph_nodes_remain_dirty(self) -> None:
        """CUJ: Reporting failure if nodes remain dirty after cleaning."""
        root = _make_dag_node("//pkg:stay_dirty", "lib")

        class PersistentDirtyCleaner:
            def clean(
                self, node: dag_storage.DagNode, cleaner: loop_node_cleaner.NodeCleaner
            ) -> None:
                pass

        self.storage.dirty_nodes.add(root)
        self.registry.register_instance(
            PersistentDirtyCleaner(),
            keys=[loop_cleaner.LoopCleaner],
            tier="system",
        )

        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            result = loop_service.clean_subgraph(root)

            self.assertFalse(result.success)
            self.assertIn("failed", result.summary)
            self.assertIn("reachable nodes remain dirty", result.summary)

    def test_mark_subgraph_clean(self) -> None:
        """CUJ: Marking subgraph clean materializes templates and marks clean."""
        root = _make_dag_node("//pkg:root", "lib")
        dep = _make_dag_node("//pkg:dep", "lib")
        self.storage.dependencies_map[root] = {
            dag_storage.DagDependency(node=dep, is_silent=False)
        }
        self.storage.dirty_nodes.add(root)
        self.storage.dirty_nodes.add(dep)

        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            loop_service.mark_subgraph_clean(root)

            self.assertIn(root, self.storage.cleaned_nodes)
            self.assertIn(dep, self.storage.cleaned_nodes)
            self.assertIn(root, self.storage.materialized_nodes)
            self.assertIn(dep, self.storage.materialized_nodes)

    def test_mark_dirty(self) -> None:
        """CUJ: Marking node dirty deletes last cleaned and records optional change message."""
        node = _make_dag_node("//pkg:unit", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            msg = dag_storage.ChangeMessage(content=dag_storage.MessageContent("touched"))
            loop_service.mark_dirty(node, msg)

            self.assertTrue(self.storage.is_dirty(node))
            self.assertIn(msg, self.storage.get_messages(node))

    def test_record_change(self) -> None:
        """CUJ: Recording change marks node clean with change description and clears last cleaned."""
        node = _make_dag_node("//pkg:unit", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            msg = dag_storage.ChangeMessage(content=dag_storage.MessageContent("refactored"))
            loop_service.record_change(node, msg)

            self.assertIn(node, self.storage.cleaned_nodes)
            self.assertEqual(
                self.storage.cleaned_changes[node],
                dag_storage.ChangeDescription("refactored"),
            )
            self.assertTrue(self.storage.is_dirty(node))

    def test_inject_feedback(self) -> None:
        """CUJ: Injecting feedback records feedback message in storage."""
        node = _make_dag_node("//pkg:unit", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            loop_service = scope.get_singleton(loop.Loop)
            fb = dag_storage.FeedbackMessage(content=dag_storage.MessageContent("assertion failed"))
            loop_service.inject_feedback(node, fb)

            self.assertIn(fb, self.storage.get_messages(node))


if __name__ == "__main__":
    unittest.main()
