"""Unit tests for bazel_runner_impl aligned with grounding specifications."""

import unittest
from typing import Optional, Sequence, Set
from lib import bazel_graph_storage
from lib import bazel_manifest_loader
from lib import bazel_runner
from lib import bazel_runner_impl
from lib import dag_cleaner
from lib import dag_node_cleaner
from lib import dag_storage
from lib import runner_logger
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton


class MockRunnerLogger(runner_logger.RunnerLogger):
    """Mock implementation of RunnerLogger protocol."""

    def __init__(self) -> None:
        self.events: list[runner_logger.LogEvent] = []

    def consume(self, event: runner_logger.LogEvent) -> None:
        self.events.append(event)


class MockManifestLoader(bazel_manifest_loader.BazelManifestLoader):
    """Mock implementation of BazelManifestLoader protocol."""

    def __init__(self) -> None:
        self.manifests: dict[str, bazel_manifest_loader.Manifest] = {}
        self.loaded: list[bazel_manifest_loader.Manifest] = []

    def get_manifest(self, node: dag_storage.Node) -> Optional[bazel_manifest_loader.Manifest]:
        return self.manifests.get(node.address)

    def load_manifest(
        self,
        content: bazel_manifest_loader.Manifest,
        storage: bazel_graph_storage.BazelGraphStorage,
    ) -> Sequence[bazel_graph_storage.NodeDefinition]:
        self.loaded.append(content)
        return []


class MockDagStorage(dag_storage.DagStorage):
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


class MockDagCleaner(dag_cleaner.DagCleaner):
    """Mock implementation of DagCleaner protocol."""

    def __init__(self, storage: MockDagStorage, should_fail: bool = False) -> None:
        self.cleaned_nodes: list[dag_storage.Node] = []
        self.storage = storage
        self.should_fail = should_fail

    def clean(self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner) -> None:
        if self.should_fail:
            raise RuntimeError("Simulated cleaner failure")
        self.cleaned_nodes.append(node)
        cleaner.clean(node)
        self.storage.dirty_nodes.discard(node)


class MockNodeCleaner(dag_node_cleaner.NodeCleaner):
    """Mock implementation of NodeCleaner protocol."""

    def __init__(self) -> None:
        self.cleaned_targets: list[dag_storage.Node] = []

    def clean(self, node: dag_storage.Node) -> bool:
        self.cleaned_targets.append(node)
        return True


class BazelRunnerImplTest(unittest.TestCase):
    """Tests for BazelRunner and BuildResult implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.logger = MockRunnerLogger()
        self.manifest_loader = MockManifestLoader()
        self.storage = MockDagStorage()
        self.cleaner = MockDagCleaner(self.storage)
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
            keys=[MockDagCleaner, dag_cleaner.DagCleaner],
            tier="system",
        )
        self.registry.register_instance(
            self.node_cleaner,
            keys=[MockNodeCleaner, dag_node_cleaner.NodeCleaner],
            tier="system",
        )

        bazel_runner_impl.__initialize__(self.registry)

    def test_build_result_dataclass(self) -> None:
        """Tests BuildResult value object instantiation and property access."""
        # Requirement: [BazelRunner] A bazel runner produces a build result upon pass completion.
        result = bazel_runner.BuildResult(success=True, summary="Build finished successfully")
        self.assertTrue(result.success)
        self.assertEqual(result.summary, "Build finished successfully")

        failure = bazel_runner.BuildResult(success=False, summary="Build failed")
        self.assertFalse(failure.success)
        self.assertEqual(failure.summary, "Build failed")

    def test_run_cleaning_pass_success(self) -> None:
        """Tests successful cleaning pass execution and telemetry logging."""
        root = dag_storage.Node(address="//pkg:target")
        self.manifest_loader.manifests["//pkg:target"] = bazel_manifest_loader.Manifest("rule()")
        self.storage.dirty_nodes.add(root)

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: The bazel runner resolves target labels and loads workspace target graphs into dag storage using a manifest loader.
            # Requirement: [BazelRunner] A bazel runner resolves target manifests and loads workspace target graphs into dag storage using a manifest loader.
            # Requirement: [BazelRunner] A bazel runner executes a cleaning pass over an acyclic subgraph rooted at a target node in dag storage.
            result = runner.run_cleaning_pass(root)

            # Requirement: The bazel runner executes cleaning passes in topological order using the dag cleaner and the node cleaner.
            # Requirement: [BazelRunner] A bazel runner cleans dirty nodes in topological order using the dag cleaner and the node cleaner.
            self.assertIn(root, self.cleaner.cleaned_nodes)
            self.assertIn(root, self.node_cleaner.cleaned_targets)

            # Requirement: [BazelRunner] A bazel runner produces a build result upon pass completion.
            self.assertTrue(result.success)
            self.assertIn("succeeded", result.summary)

            # Requirement: [BazelRunner] A bazel runner logs execution events to standard output and transcript files using the runner logger.
            start_events = [e for e in self.logger.events if e.event_name == "build_pass_start"]
            end_events = [e for e in self.logger.events if e.event_name == "build_pass_end"]
            self.assertEqual(len(start_events), 1)
            self.assertEqual(len(end_events), 1)

    def test_run_cleaning_pass_loads_dependency_graph(self) -> None:
        """Tests that run_cleaning_pass transitively loads manifests for all dependencies in the graph."""
        root = dag_storage.Node(address="//pkg:root")
        dep1 = dag_storage.Node(address="//pkg:dep1")
        dep2 = dag_storage.Node(address="//pkg:dep2")

        root_m = bazel_manifest_loader.Manifest('{"name": "root"}')
        dep1_m = bazel_manifest_loader.Manifest('{"name": "dep1"}')
        dep2_m = bazel_manifest_loader.Manifest('{"name": "dep2"}')

        self.manifest_loader.manifests["//pkg:root"] = root_m
        self.manifest_loader.manifests["//pkg:dep1"] = dep1_m
        self.manifest_loader.manifests["//pkg:dep2"] = dep2_m

        self.storage.dependencies_map[root] = {dag_storage.Dependency(node=dep1)}
        self.storage.dependencies_map[dep1] = {dag_storage.Dependency(node=dep2)}

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: The bazel runner resolves target labels and loads workspace target graphs into dag storage using a manifest loader.
            # Requirement: [BazelRunner] A bazel runner resolves target manifests and loads workspace target graphs into dag storage using a manifest loader.
            result = runner.run_cleaning_pass(root)

            self.assertTrue(result.success)
            self.assertIn(root_m, self.manifest_loader.loaded)
            self.assertIn(dep1_m, self.manifest_loader.loaded)
            self.assertIn(dep2_m, self.manifest_loader.loaded)

    def test_run_cleaning_pass_runtime_error(self) -> None:
        """Tests cleaning pass failure handling when cleaner raises RuntimeError."""
        root = dag_storage.Node(address="//pkg:failing")
        self.cleaner.should_fail = True

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: The bazel runner halts cleaning and reports failure if a node cleaning fails, if an unexpected failure occurs during cleaning capturing the failure reason in the build summary, or if any reachable node in the target subgraph remains dirty after cleaning.
            result = runner.run_cleaning_pass(root)

            self.assertFalse(result.success)
            self.assertEqual(result.summary, "Cleaning pass failed for //pkg:failing: Simulated cleaner failure")

            end_events = [e for e in self.logger.events if e.event_name == "build_pass_end"]
            self.assertEqual(len(end_events), 1)
            self.assertEqual(end_events[0].summary, "Cleaning pass failed for //pkg:failing: Simulated cleaner failure")

    def test_run_cleaning_pass_remaining_dirty(self) -> None:
        """Tests cleaning pass reporting failure if root remains dirty after cleaning."""
        root = dag_storage.Node(address="//pkg:dirty_root")
        # Custom cleaner that does not clear dirty status
        class PersistentDirtyCleaner(dag_cleaner.DagCleaner):
            def clean(self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner) -> None:
                pass

        self.storage.dirty_nodes.add(root)
        self.registry.register_instance(
            PersistentDirtyCleaner(),
            keys=[dag_cleaner.DagCleaner],
            tier="system",
        )

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: The bazel runner halts cleaning and reports failure if a node cleaning fails, if an unexpected failure occurs during cleaning capturing the failure reason in the build summary, or if any reachable node in the target subgraph remains dirty after cleaning.
            result = runner.run_cleaning_pass(root)

            self.assertFalse(result.success)
            self.assertIn("failed", result.summary)

    def test_run_cleaning_pass_dependency_remaining_dirty(self) -> None:
        """Tests cleaning pass reporting failure if a dependency remains dirty after cleaning."""
        root = dag_storage.Node(address="//pkg:clean_root")
        dep = dag_storage.Node(address="//pkg:dirty_dep")
        self.storage.dependencies_map[root] = {dag_storage.Dependency(node=dep)}

        class PersistentDirtyCleaner(dag_cleaner.DagCleaner):
            def clean(self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner) -> None:
                pass

        self.storage.dirty_nodes.add(dep)
        self.registry.register_instance(
            PersistentDirtyCleaner(),
            keys=[dag_cleaner.DagCleaner],
            tier="system",
        )

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: The bazel runner halts cleaning and reports failure if a node cleaning fails, if an unexpected failure occurs during cleaning capturing the failure reason in the build summary, or if any reachable node in the target subgraph remains dirty after cleaning.
            result = runner.run_cleaning_pass(root)

            self.assertFalse(result.success)
            self.assertIn("failed", result.summary)

    def test_mark_node_dirty(self) -> None:
        """Tests marking a target node dirty by injecting a change message."""
        target = dag_storage.Node(address="//pkg:lib")
        change = dag_storage.Change()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: Marking a node dirty injects a change message with text set to check.
            # Requirement: [BazelRunner] A bazel runner marks a target node dirty by injecting a non-triggering check change message into its pending messages in dag storage.
            runner.mark_node_dirty(target, change)

            self.assertTrue(self.storage.is_dirty(target))
            self.assertIn(change, self.storage.get_messages(target))

    def test_inject_node_feedback(self) -> None:
        """Tests injecting caller-supplied feedback message to mark a node dirty."""
        target = dag_storage.Node(address="//pkg:dep")
        feedback = dag_storage.Feedback()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: Injecting feedback or broadcasting changes transmits caller-provided message content.
            # Requirement: [BazelRunner] A bazel runner injects a caller-supplied feedback message into a target node.
            runner.inject_node_feedback(target, feedback)

            self.assertTrue(self.storage.is_dirty(target))
            self.assertIn(feedback, self.storage.get_messages(target))

    def test_broadcast_node_change(self) -> None:
        """Tests broadcasting a change message to all downstream reverse dependencies."""
        origin = dag_storage.Node(address="//pkg:origin")
        dep1 = dag_storage.Node(address="//pkg:dep1")
        dep2 = dag_storage.Node(address="//pkg:dep2")
        self.storage.dependents_map[origin] = {dep1, dep2}
        change = dag_storage.Change()

        with enter_phase("system", registry=self.registry):
            runner = get_singleton(bazel_runner.BazelRunner)
            # Requirement: Injecting feedback or broadcasting changes transmits caller-provided message content.
            # Requirement: [BazelRunner] A bazel runner broadcasts a caller-supplied change message from a node to all of its reverse dependencies.
            runner.broadcast_node_change(origin, change)

            self.assertTrue(self.storage.is_dirty(dep1))
            self.assertTrue(self.storage.is_dirty(dep2))
            self.assertIn(change, self.storage.get_messages(dep1))
            self.assertIn(change, self.storage.get_messages(dep2))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - When an agent session concludes, the bazel runner logs cumulative token usage and pass duration.
