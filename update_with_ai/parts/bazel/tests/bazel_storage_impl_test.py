"""Unit tests for bazel_storage_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
from typing import Any, cast
import unittest
from unittest.mock import patch
from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.bazel.lib.bazel_storage_impl import (
    AgentStorage as AgentStorageImpl,
    __initialize__,
)
from update_with_ai.parts.core.lib.file_paths import (
    AbsolutePath,
    FilePathManager,
    HostPath,
    PathString,
    WorkspacePath,
    WorkspaceRoot,
)
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.dag.lib.dag_storage import (
    ChangeMessage,
    DagStorage,
    DagDependency,
    FeedbackMessage,
    DagNode,
    MessageContent,
    RoleAddress,
    UnitAddress,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address))


class FakeBazelTarget:
    tier = "system"

    def normalize_target(self, target_identifier: str) -> DagNode:
        if "#" in target_identifier:
            u, r = target_identifier.split("#", 1)
            return _make_dag_node(u, r)
        return _make_dag_node(target_identifier, "")

    def extract_node_dir(self, node: DagNode) -> NodeDirectory:
        pkg = node.unit_address.split(":")[0].lstrip("/")
        return NodeDirectory(path=PathString(pkg))


class FakeFilePaths:
    tier = "system"

    def __init__(self, root_dir: str) -> None:
        self.root_dir = root_dir

    def get_workspace_root(self) -> WorkspaceRoot:
        return WorkspaceRoot(path=PathString(self.root_dir))

    def create_host_path(self, path: str) -> HostPath:
        return HostPath(path=PathString(path))

    def create_absolute_path(self, path: str) -> AbsolutePath:
        return AbsolutePath(path=PathString(path))

    def create_workspace_path(self, path: str) -> WorkspacePath:
        return WorkspacePath(path=PathString(path))

    def resolve_path(
        self, root: AbsolutePath, relative: WorkspacePath
    ) -> AbsolutePath:
        joined = os.path.join(root.path, relative.path)
        return AbsolutePath(path=PathString(joined))


class BazelStorageImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.orig_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir
        self.registry = LifecycleRegistry()
        self.file_paths_service = FakeFilePaths(self.test_dir)
        self.node_id_utils = FakeBazelTarget()

        self.registry.register_instance(
            self.file_paths_service, keys=[FilePathManager], tier="system"
        )
        self.registry.register_instance(
            self.node_id_utils, keys=[BazelTarget], tier="system"
        )
        __initialize__(self.registry)

    def tearDown(self) -> None:
        if self.orig_env is not None:
            os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.orig_env
        else:
            os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_node_definition_and_dependencies(self) -> None:
        """CUJ: Storing and querying node definitions and direct graph dependencies."""
        node = _make_dag_node("//pkg:target")
        dep_node = _make_dag_node("//pkg:dep")
        defn = NodeDefinition(task_prompt=TaskPrompt("Clean prompt"))

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            self.assertIsInstance(storage, AgentStorageImpl)
            assert isinstance(storage, AgentStorageImpl)

            # Store node definition
            storage.store_node_definition(node, defn)
            # Requirement: [AgentStorage] MUST provide node definitions for declared nodes.
            # Requirement: MUST provide node definitions for declared nodes.
            self.assertEqual(storage.get_node_definition(node), defn)
            # Requirement: MUST provide task prompts for declared nodes.
            self.assertEqual(storage.get_task_prompt(node), defn.task_prompt)

            # Dependencies
            dep = DagDependency(node=dep_node, is_silent=False)
            cast(Any, storage)._dependencies[node] = {dep}
            # Requirement: [AgentStorage] MUST return the set of upstream dependencies for the node.
            # Requirement: MUST return the set of upstream dependencies for the node.
            self.assertEqual(storage.get_dependencies(node), {dep})

    def test_messages_persistence_and_dirty_state(self) -> None:
        """CUJ: Adding messages persists feedback to in-band source metadata and controls dirty state."""
        node = _make_dag_node("//pkg/sub:target", "lib")
        rel_path = "pkg/sub/target.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-01T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-01T10:00:00Z\n"
                "# CHANGE: init\n"
                "# --- END CLEANROOM METADATA ---\n"
                "print('hello')\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            cast(Any, storage)._source_files[node] = rel_path
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

            # Add ChangeMessage and FeedbackMessage messages
            # Requirement: WHEN message is a feedback message, MUST append an unacted feedback entry to the target source file metadata.
            # Requirement: MUST add the message to the node.
            storage.add_message(ChangeMessage(content=MessageContent("Need refactor")), to=node)
            storage.add_message(FeedbackMessage(content=MessageContent("Syntax error on line 5")), to=node)

            # Requirement: WHEN source file metadata is missing or contains unacted feedback entries, MUST return true.
            # Requirement: MUST return the set of messages recorded for the node.
            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 2)
            self.assertTrue(any(isinstance(m, ChangeMessage) for m in msgs))
            self.assertTrue(any(isinstance(m, FeedbackMessage) for m in msgs))

            # Verify in-band metadata has unacted feedback entry
            with open(abs_src, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Syntax error on line 5", content)

            # Clear messages resets dirty state and updates metadata
            # Requirement: MUST clear all messages from the node.
            # Requirement: MUST update the last cleaned timestamp and remove unacted feedback entries from source metadata.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())
            with open(abs_src, "r", encoding="utf-8") as f:
                content_after = f.read()
            self.assertNotIn("Syntax error on line 5", content_after)

    def test_missing_source_file_dirty_state(self) -> None:
        """CUJ: A node is dirty when its declared source file is missing from the workspace root."""
        node = _make_dag_node("//pkg/src:target", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # DagNode with declared source file that does not exist yet
            rel_path = "pkg/src/target.py"
            cast(Any, storage)._source_files[node] = rel_path
            # Requirement: WHEN a declared source file is missing from the workspace root, MUST return true and record a change message to implement the source file.
            self.assertTrue(storage.is_dirty(node))

            # Calling is_dirty recorded a change message to implement the source file
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 1)
            msg = next(iter(msgs))
            assert isinstance(msg, ChangeMessage)
            self.assertEqual(msg.content, f"implement {rel_path}")

            # Consecutive call to is_dirty is idempotent and does not add duplicate messages
            self.assertTrue(storage.is_dirty(node))
            self.assertEqual(len(storage.get_messages(node)), 1)

            # Even after creating the declared source file on disk without valid metadata, the node remains dirty
            abs_src = os.path.join(self.test_dir, rel_path)
            os.makedirs(os.path.dirname(abs_src), exist_ok=True)
            with open(abs_src, "w", encoding="utf-8") as f:
                f.write("# source file\n")
            self.assertTrue(storage.is_dirty(node))

            # Clearing messages once the source file exists writes valid cleaned metadata and clears the dirty state
            # Requirement: MUST clear all messages from the node.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))

    def test_dependents_and_dependency_timestamps_dirty_state(self) -> None:
        """CUJ: Querying dependents and dynamic dirty evaluation from dependency timestamps."""
        upstream = _make_dag_node("//pkg/lib:core", "lib")
        downstream = _make_dag_node("//pkg/app:main", "lib")
        silent_upstream = _make_dag_node("//pkg/silent:tool", "lib")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # Set dependencies: one normal, one silent
            cast(Any, storage)._dependencies[downstream] = {
                DagDependency(node=upstream, is_silent=False),
                DagDependency(node=silent_upstream, is_silent=True),
            }

            # Requirement: MUST return the set of downstream nodes depending on the node.
            self.assertEqual(storage.get_dependents(upstream), {downstream})
            self.assertEqual(storage.get_dependents(silent_upstream), set())

            # Create source files: upstream changed after downstream was cleaned
            upstream_file = "pkg/lib/core.py"
            downstream_file = "pkg/app/main.py"
            abs_up = os.path.join(self.test_dir, upstream_file)
            abs_down = os.path.join(self.test_dir, downstream_file)
            os.makedirs(os.path.dirname(abs_up), exist_ok=True)
            os.makedirs(os.path.dirname(abs_down), exist_ok=True)

            with open(abs_up, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-02T15:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-02T15:00:00Z\n"
                    "# CHANGE: upstream update\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )
            with open(abs_down, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                    "# CHANGE: initial main\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )

            cast(Any, storage)._source_files[upstream] = upstream_file
            cast(Any, storage)._source_files[downstream] = downstream_file

            # Requirement: WHEN a non-silent forward dependency has a last changed timestamp newer than the node's last cleaned timestamp, MUST return true.
            self.assertTrue(storage.is_dirty(downstream))

            # Cleaning downstream brings its last_cleaned forward, making it not dirty
            storage.clear_messages(downstream)
            self.assertFalse(storage.is_dirty(downstream))

    def test_delete_last_cleaned_marks_dirty(self) -> None:
        """CUJ: Deleting last_cleaned from source metadata marks the node dirty without modifying last_changed or change description."""
        node = _make_dag_node("//pkg/app:service", "lib")
        rel_path = "pkg/app/service.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T15:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T15:00:00Z\n"
                "# CHANGE: initial clean\n"
                "# --- END CLEANROOM METADATA ---\n"
                "def run(): pass\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            cast(Any, storage)._source_files[node] = rel_path

            # Initially clean
            self.assertFalse(storage.is_dirty(node))

            # Requirement: MUST delete the last cleaned timestamp from the source file metadata header.
            cast(Any, storage).delete_last_cleaned(node)

            # File on disk must have LAST_CLEANED removed, but retain LAST_CHANGED and CHANGE
            with open(abs_src, "r", encoding="utf-8") as f:
                disk_content = f.read()
            self.assertNotIn("LAST_CLEANED:", disk_content)
            self.assertIn("LAST_CHANGED: 2026-10-02T15:00:00Z", disk_content)
            self.assertIn("CHANGE: initial clean", disk_content)

            # Node evaluates as dirty
            self.assertTrue(storage.is_dirty(node))

        # Simulate a fresh process run (new storage instance reading disk)
        fresh_registry = LifecycleRegistry()
        fresh_registry.register_instance(
            self.file_paths_service, keys=[FilePathManager], tier="system"
        )
        fresh_registry.register_instance(
            self.node_id_utils, keys=[BazelTarget], tier="system"
        )
        __initialize__(fresh_registry)

        with enter_phase("system", registry=fresh_registry) as scope:
            fresh_storage = scope.get_singleton(AgentStorage)
            cast(Any, fresh_storage)._source_files[node] = rel_path

            # In the fresh process, node is still dirty purely from disk state
            self.assertTrue(fresh_storage.is_dirty(node))

            # Clearing messages stamps LAST_CLEANED and makes it clean
            fresh_storage.clear_messages(node)
            self.assertFalse(fresh_storage.is_dirty(node))
            with open(abs_src, "r", encoding="utf-8") as f:
                cleaned_content = f.read()
            self.assertIn("LAST_CLEANED:", cleaned_content)
            self.assertIn("LAST_CHANGED: 2026-10-02T15:00:00Z", cleaned_content)
            self.assertIn("CHANGE: initial clean", cleaned_content)

    def test_dag_storage_protocol_aliasing(self) -> None:
        """CUJ: Resolving singleton via DagStorage protocol alias."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DagStorage)
            graph = scope.get_singleton(AgentStorage)
            self.assertIs(dag, graph)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
