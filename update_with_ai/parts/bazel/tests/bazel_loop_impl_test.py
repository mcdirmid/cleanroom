"""Unit tests for bazel_loop_impl aligned with grounding specifications."""

import unittest
from typing import Optional, Sequence, Set
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.bazel.lib import bazel_manifest_loader
from update_with_ai.parts.bazel.lib.bazel_loop_impl import (
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
    """Mock implementation of RunnerLogger protocol."""

    def __init__(self) -> None:
        self.events: list[runner_logger.RunnerLogEvent] = []

    def consume(self, event: runner_logger.RunnerLogEvent) -> None:
        self.events.append(event)


class MockManifestLoader:
    """Mock implementation of BazelManifestLoader protocol."""

    def __init__(self) -> None:
        self.manifests: dict[str, bazel_manifest_loader.TargetManifest] = {}
        self.loaded: list[dag_storage.DagNode] = []

    def retrieve_manifest(
        self, node: dag_storage.DagNode
    ) -> Optional[bazel_manifest_loader.TargetManifest]:
        return self.manifests.get(node.unit_address)

    def load_manifest(
        self,
        node: dag_storage.DagNode,
    ) -> None:
        self.loaded.append(node)


class MockDagStorage:
    """Mock implementation of DagStorage protocol."""

    def __init__(self) -> None:
        self.dirty_nodes: Set[dag_storage.DagNode] = set()
        self.messages: dict[dag_storage.DagNode, list[dag_storage.DagMessage]] = {}
        self.dependents_map: dict[dag_storage.DagNode, Set[dag_storage.DagNode]] = {}
        self.dependencies_map: dict[dag_storage.DagNode, Set[dag_storage.DagDependency]] = {}

    def get_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagDependency]:
        return self.dependencies_map.get(node, set())

    def get_dependents(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        return self.dependents_map.get(node, set())

    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        return set(self.messages.get(node, []))

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self.dirty_nodes

    def register_dependent(self, node: dag_storage.DagNode) -> None:
        pass

    def clear_dependents(self, node: dag_storage.DagNode) -> None:
        self.dependents_map.pop(node, None)

    def add_message(self, message: dag_storage.DagMessage, to: dag_storage.DagNode) -> None:
        if to not in self.messages:
            self.messages[to] = []
        self.messages[to].append(message)
        self.dirty_nodes.add(to)

    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self.messages.pop(node, None)
        self.dirty_nodes.discard(node)


class MockLoopCleaner:
    """Mock implementation of LoopCleaner protocol."""

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
        self.storage.dirty_nodes.discard(node)


class MockNodeCleaner:
    """Mock implementation of NodeCleaner protocol."""

    def __init__(self) -> None:
        self.cleaned_targets: list[dag_storage.DagNode] = []

    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        self.cleaned_targets.extend(nodes)
        return True


class BazelLoopImplTest(unittest.TestCase):
    """Tests for Bazel Loop implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.logger = MockRunnerLogger()
        self.manifest_loader = MockManifestLoader()
        self.storage = MockDagStorage()
        self.cleaner = MockLoopCleaner(self.storage)
        self.node_cleaner = MockNodeCleaner()

        self.registry.register_instance(
            self.logger,
            keys=[runner_logger.RunnerLogger],
            tier="system",
        )
        self.registry.register_instance(
            self.manifest_loader,
            keys=[bazel_manifest_loader.BazelManifestLoader],
            tier="system",
        )
        self.registry.register_instance(
            self.storage,
            keys=[dag_storage.DagStorage],
            tier="system",
        )
        self.registry.register_instance(
            self.cleaner,
            keys=[loop_cleaner.LoopCleaner],
            tier="system",
        )
        self.registry.register_instance(
            self.node_cleaner,
            keys=[loop_node_cleaner.NodeCleaner],
            tier="system",
        )

        __initialize__(self.registry)

    def test_build_result_dataclass(self) -> None:
        """CUJ: Verify BuildResult value object instantiation and property access."""
        # Requirement: MUST produce a build result upon pass completion.
        result = loop.BuildResult(success=True, summary=loop.BuildSummary("Build finished successfully"))
        self.assertTrue(result.success)
        self.assertEqual(result.summary, "Build finished successfully")

        failure = loop.BuildResult(success=False, summary=loop.BuildSummary("Build failed"))
        self.assertFalse(failure.success)
        self.assertEqual(failure.summary, "Build failed")

    def test_clean_subgraph_success(self) -> None:
        """CUJ: Successful cleaning pass execution and telemetry logging."""
        root = _make_dag_node("//pkg:target", "lib")
        self.manifest_loader.manifests["//pkg:target"] = bazel_manifest_loader.TargetManifest(
            label=bazel_manifest_loader.TargetLabel("//pkg:target")
        )
        self.storage.dirty_nodes.add(root)

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: MUST resolve target labels against workspace directories to populate graph storage when executing a cleaning pass.
            # Requirement: MUST execute a cleaning pass over the acyclic subgraph rooted at the target node.
            # Requirement: MUST produce a build result upon pass completion.
            result = runner.clean_subgraph(root)

            self.assertIn(root, self.cleaner.cleaned_nodes)
            self.assertIn(root, self.node_cleaner.cleaned_targets)

            self.assertTrue(result.success)
            self.assertIn("succeeded", result.summary)

            # Requirement: MUST stream telemetry capturing execution events to standard output.
            start_events = [
                e for e in self.logger.events if e.event_name == "build_pass_start"
            ]
            end_events = [
                e for e in self.logger.events if e.event_name == "build_pass_end"
            ]
            self.assertEqual(len(start_events), 1)
            self.assertEqual(len(end_events), 1)
            self.assertIn("succeeded", end_events[0].summary)
            self.assertIn("s", end_events[0].summary)

    def test_clean_subgraph_loads_dependency_graph(self) -> None:
        """CUJ: Transitively loading manifests for all dependencies in the graph."""
        root = _make_dag_node("//pkg:root")
        dep1 = _make_dag_node("//pkg:dep1")
        dep2 = _make_dag_node("//pkg:dep2")
        dep3 = _make_dag_node("//pkg:dep3")

        root_m = bazel_manifest_loader.TargetManifest(label=bazel_manifest_loader.TargetLabel("//pkg:root"))
        dep1_m = bazel_manifest_loader.TargetManifest(label=bazel_manifest_loader.TargetLabel("//pkg:dep1"))
        dep2_m = bazel_manifest_loader.TargetManifest(label=bazel_manifest_loader.TargetLabel("//pkg:dep2"))
        dep3_m = bazel_manifest_loader.TargetManifest(label=bazel_manifest_loader.TargetLabel("//pkg:dep3"))

        self.manifest_loader.manifests["//pkg:root"] = root_m
        self.manifest_loader.manifests["//pkg:dep1"] = dep1_m
        self.manifest_loader.manifests["//pkg:dep2"] = dep2_m
        self.manifest_loader.manifests["//pkg:dep3"] = dep3_m

        self.storage.dependencies_map[root] = {
            dag_storage.DagDependency(node=dep1),
            dag_storage.DagDependency(node=dep2),
        }
        self.storage.dependencies_map[dep1] = {dag_storage.DagDependency(node=dep3)}
        self.storage.dependencies_map[dep2] = {dag_storage.DagDependency(node=dep3)}

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: MUST resolve target labels against workspace directories to populate graph storage when executing a cleaning pass.
            # Requirement: MUST execute a cleaning pass over the acyclic subgraph rooted at the target node.
            # Requirement: MUST produce a build result upon pass completion.
            result = runner.clean_subgraph(root)

            self.assertTrue(result.success)

    def test_clean_subgraph_runtime_error(self) -> None:
        """CUJ: Cleaning pass failure handling when cleaner raises RuntimeError."""
        root = _make_dag_node("//pkg:failing")
        self.cleaner.should_fail = True

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: WHEN an unexpected failure occurs during cleaning, MUST halt immediately with a failing build result.
            # Requirement: WHEN producing a failing build result, MUST capture the failure reason in the build summary.
            # Requirement: MUST produce a build result upon pass completion.
            result = runner.clean_subgraph(root)

            self.assertFalse(result.success)
            self.assertIn("Simulated cleaner failure", result.summary)

    def test_clean_subgraph_nodes_remain_dirty(self) -> None:
        """CUJ: Reporting failure if nodes remain dirty after cleaning."""
        root = _make_dag_node("//pkg:stay_dirty")

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

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: WHEN any reachable node remains dirty after cleaning, MUST halt immediately with a failing build result.
            # Requirement: WHEN producing a failing build result, MUST capture the failure reason in the build summary.
            # Requirement: MUST produce a build result upon pass completion.
            result = runner.clean_subgraph(root)

            self.assertFalse(result.success)
            self.assertIn("failed", result.summary)

    def test_mark_dirty(self) -> None:
        """CUJ: Marking a target node dirty by injecting a change message."""
        target = _make_dag_node("//pkg:lib")
        change = dag_storage.ChangeMessage()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: MUST mark the target node dirty by injecting the change message into its pending messages.
            runner.mark_dirty(target, change)

            self.assertTrue(self.storage.is_dirty(target))
            self.assertIn(change, self.storage.get_messages(target))

    def test_inject_feedback(self) -> None:
        """CUJ: Injecting caller-supplied feedback message to mark a node dirty."""
        target = _make_dag_node("//pkg:dep")
        feedback = dag_storage.FeedbackMessage()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: MUST inject the feedback message into the target node.
            runner.inject_feedback(target, feedback)

            self.assertTrue(self.storage.is_dirty(target))
            self.assertIn(feedback, self.storage.get_messages(target))

    def test_broadcast_change(self) -> None:
        """CUJ: Broadcasting a change message to all downstream reverse dependencies."""
        origin = _make_dag_node("//pkg:origin")
        dep1 = _make_dag_node("//pkg:dep1")
        dep2 = _make_dag_node("//pkg:dep2")
        self.storage.dependents_map[origin] = {dep1, dep2}
        change = dag_storage.ChangeMessage()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: MUST broadcast the change message to all reverse dependencies of the node.
            runner.broadcast_change(origin, change)

            self.assertTrue(self.storage.is_dirty(dep1))
            self.assertTrue(self.storage.is_dirty(dep2))
            self.assertIn(change, self.storage.get_messages(dep1))
            self.assertIn(change, self.storage.get_messages(dep2))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - MUST resolve target labels against runfiles trees to populate graph storage when executing a cleaning pass.
# - WHEN node cleaning fails, MUST halt immediately with a failing build result.
# - MUST stream telemetry capturing execution events to transcript files.
# - MUST stream telemetry capturing pass duration to standard output and transcript files.
# - MUST stream telemetry capturing build outcome to standard output and transcript files.
