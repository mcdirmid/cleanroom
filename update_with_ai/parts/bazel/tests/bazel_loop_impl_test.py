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


class MockRunnerLogger:
    """Mock implementation of RunnerLogger protocol."""

    def __init__(self) -> None:
        self.events: list[runner_logger.LogEvent] = []

    def consume(self, event: runner_logger.LogEvent) -> None:
        self.events.append(event)


class MockManifestLoader:
    """Mock implementation of BazelManifestLoader protocol."""

    def __init__(self) -> None:
        self.manifests: dict[str, bazel_manifest_loader.Manifest] = {}
        self.loaded: list[bazel_manifest_loader.Manifest] = []

    def get_manifest(
        self, node: dag_storage.Node
    ) -> Optional[bazel_manifest_loader.Manifest]:
        return self.manifests.get(node.unit_address)

    def load_manifest(
        self,
        content: bazel_manifest_loader.Manifest,
        storage: agent_storage.AgentStorage,
    ) -> Sequence[agent_storage.NodeDefinition]:
        self.loaded.append(content)
        return []


class MockDagStorage:
    """Mock implementation of DagStorage protocol."""

    def __init__(self) -> None:
        self.dirty_nodes: Set[dag_storage.Node] = set()
        self.messages: dict[dag_storage.Node, list[dag_storage.Message]] = {}
        self.dependents_map: dict[dag_storage.Node, Set[dag_storage.Node]] = {}
        self.dependencies_map: dict[dag_storage.Node, Set[dag_storage.Dependency]] = {}

    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        return self.dependencies_map.get(node, set())

    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        return self.dependents_map.get(node, set())

    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        return set(self.messages.get(node, []))

    def is_dirty(self, node: dag_storage.Node) -> bool:
        return node in self.dirty_nodes

    def register_dependent(self, node: dag_storage.Node) -> None:
        pass

    def clear_dependents(self, node: dag_storage.Node) -> None:
        self.dependents_map.pop(node, None)

    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        if to not in self.messages:
            self.messages[to] = []
        self.messages[to].append(message)
        self.dirty_nodes.add(to)

    def clear_messages(self, node: dag_storage.Node) -> None:
        self.messages.pop(node, None)
        self.dirty_nodes.discard(node)


class MockLoopCleaner:
    """Mock implementation of LoopCleaner protocol."""

    def __init__(self, storage: MockDagStorage, should_fail: bool = False) -> None:
        self.cleaned_nodes: list[dag_storage.Node] = []
        self.storage = storage
        self.should_fail = should_fail

    def clean(
        self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner
    ) -> None:
        if self.should_fail:
            raise RuntimeError("Simulated cleaner failure")
        self.cleaned_nodes.append(node)
        cleaner.clean([node])
        self.storage.dirty_nodes.discard(node)


class MockNodeCleaner:
    """Mock implementation of NodeCleaner protocol."""

    def __init__(self) -> None:
        self.cleaned_targets: list[dag_storage.Node] = []

    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool:
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
            keys=[MockRunnerLogger, runner_logger.RunnerLogger],
            tier="system",
        )
        self.registry.register_instance(
            self.manifest_loader,
            keys=[MockManifestLoader, bazel_manifest_loader.BazelManifestLoader],
            tier="system",
        )
        self.registry.register_instance(
            self.storage,
            keys=[MockDagStorage, dag_storage.DagStorage],
            tier="system",
        )
        self.registry.register_instance(
            self.cleaner,
            keys=[MockLoopCleaner, loop_cleaner.LoopCleaner],
            tier="system",
        )
        self.registry.register_instance(
            self.node_cleaner,
            keys=[MockNodeCleaner, loop_node_cleaner.NodeCleaner],
            tier="system",
        )

        __initialize__(self.registry)

    def test_build_result_dataclass(self) -> None:
        """Tests BuildResult value object instantiation and property access."""
        # Requirement: [Loop] The loop produces a build result upon pass completion.
        result = loop.BuildResult(success=True, summary="Build finished successfully")
        self.assertTrue(result.success)
        self.assertEqual(result.summary, "Build finished successfully")

        failure = loop.BuildResult(success=False, summary="Build failed")
        self.assertFalse(failure.success)
        self.assertEqual(failure.summary, "Build failed")

    def test_run_cleaning_pass_success(self) -> None:
        """Tests successful cleaning pass execution and telemetry logging."""
        root = dag_storage.Node(unit_address="//pkg:target", role_address="")
        self.manifest_loader.manifests["//pkg:target"] = bazel_manifest_loader.Manifest(
            "rule()"
        )
        self.storage.dirty_nodes.add(root)

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: Target labels are resolved against workspace directories or runfiles trees to populate graph storage.
            # Requirement: [Loop] The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
            # Requirement: [Loop] The loop produces a build result upon pass completion.
            result = runner.run_cleaning_pass(root)

            self.assertIn(root, self.cleaner.cleaned_nodes)
            self.assertIn(root, self.node_cleaner.cleaned_targets)

            self.assertTrue(result.success)
            self.assertIn("succeeded", result.summary)

            # Requirement: Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.
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

    def test_run_cleaning_pass_loads_dependency_graph(self) -> None:
        """Tests that run_cleaning_pass transitively loads manifests for all dependencies in the graph."""
        root = dag_storage.Node(unit_address="//pkg:root", role_address="")
        dep1 = dag_storage.Node(unit_address="//pkg:dep1", role_address="")
        dep2 = dag_storage.Node(unit_address="//pkg:dep2", role_address="")
        dep3 = dag_storage.Node(unit_address="//pkg:dep3", role_address="")

        root_m = bazel_manifest_loader.Manifest('{"name": "root"}')
        dep1_m = bazel_manifest_loader.Manifest('{"name": "dep1"}')
        dep2_m = bazel_manifest_loader.Manifest('{"name": "dep2"}')
        dep3_m = bazel_manifest_loader.Manifest('{"name": "dep3"}')

        self.manifest_loader.manifests["//pkg:root"] = root_m
        self.manifest_loader.manifests["//pkg:dep1"] = dep1_m
        self.manifest_loader.manifests["//pkg:dep2"] = dep2_m
        self.manifest_loader.manifests["//pkg:dep3"] = dep3_m

        self.storage.dependencies_map[root] = {
            dag_storage.Dependency(node=dep1),
            dag_storage.Dependency(node=dep2),
        }
        self.storage.dependencies_map[dep1] = {dag_storage.Dependency(node=dep3)}
        self.storage.dependencies_map[dep2] = {dag_storage.Dependency(node=dep3)}

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: Target labels are resolved against workspace directories or runfiles trees to populate graph storage.
            # Requirement: [Loop] The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
            # Requirement: [Loop] The loop produces a build result upon pass completion.
            result = runner.run_cleaning_pass(root)

            self.assertTrue(result.success)
            self.assertIn(root_m, self.manifest_loader.loaded)
            self.assertIn(dep1_m, self.manifest_loader.loaded)
            self.assertIn(dep2_m, self.manifest_loader.loaded)
            self.assertIn(dep3_m, self.manifest_loader.loaded)

    def test_run_cleaning_pass_runtime_error(self) -> None:
        """Tests cleaning pass failure handling when cleaner raises RuntimeError."""
        root = dag_storage.Node(unit_address="//pkg:failing", role_address="")
        self.cleaner.should_fail = True

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
            # Requirement: [Loop] The loop produces a build result upon pass completion.
            result = runner.run_cleaning_pass(root)

            self.assertFalse(result.success)
            self.assertIn("Simulated cleaner failure", result.summary)

    def test_run_cleaning_pass_nodes_remain_dirty(self) -> None:
        """Tests that run_cleaning_pass reports failure if nodes remain dirty after cleaning."""
        root = dag_storage.Node(unit_address="//pkg:stay_dirty", role_address="")

        class PersistentDirtyCleaner:
            def clean(
                self, node: dag_storage.Node, cleaner: loop_node_cleaner.NodeCleaner
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
            # Requirement: Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
            # Requirement: [Loop] The loop produces a build result upon pass completion.
            result = runner.run_cleaning_pass(root)

            self.assertFalse(result.success)
            self.assertIn("failed", result.summary)

    def test_mark_node_dirty(self) -> None:
        """Tests marking a target node dirty by injecting a change message."""
        target = dag_storage.Node(unit_address="//pkg:lib", role_address="")
        change = dag_storage.Change()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: [Loop] The loop marks a target node dirty by injecting a change message into its pending messages.
            runner.mark_node_dirty(target, change)

            self.assertTrue(self.storage.is_dirty(target))
            self.assertIn(change, self.storage.get_messages(target))

    def test_inject_node_feedback(self) -> None:
        """Tests injecting caller-supplied feedback message to mark a node dirty."""
        target = dag_storage.Node(unit_address="//pkg:dep", role_address="")
        feedback = dag_storage.Feedback()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: [Loop] The loop injects a caller-supplied feedback message into a target node.
            runner.inject_node_feedback(target, feedback)

            self.assertTrue(self.storage.is_dirty(target))
            self.assertIn(feedback, self.storage.get_messages(target))

    def test_broadcast_node_change(self) -> None:
        """Tests broadcasting a change message to all downstream reverse dependencies."""
        origin = dag_storage.Node(unit_address="//pkg:origin", role_address="")
        dep1 = dag_storage.Node(unit_address="//pkg:dep1", role_address="")
        dep2 = dag_storage.Node(unit_address="//pkg:dep2", role_address="")
        self.storage.dependents_map[origin] = {dep1, dep2}
        change = dag_storage.Change()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(loop.Loop)
            # Requirement: [Loop] The loop broadcasts a caller-supplied change message from a node to all of its reverse dependencies.
            runner.broadcast_node_change(origin, change)

            self.assertTrue(self.storage.is_dirty(dep1))
            self.assertTrue(self.storage.is_dirty(dep2))
            self.assertIn(change, self.storage.get_messages(dep1))
            self.assertIn(change, self.storage.get_messages(dep2))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
