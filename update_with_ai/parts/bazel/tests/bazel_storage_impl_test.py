# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: f1b5604efbc4
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

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
    ChangeDescription,
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
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


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

    def resolve_path(self, root: AbsolutePath, relative: WorkspacePath) -> AbsolutePath:
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
            storage.store_dependencies(node, {dep})
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
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

            # Add ChangeMessage and FeedbackMessage messages
            # Requirement: WHEN message is a feedback message, MUST append an unacted feedback entry to the target source file metadata.
            # Requirement: MUST add the message to the node.
            storage.add_message(
                ChangeMessage(content=MessageContent("Need refactor")), to=node
            )
            storage.add_message(
                FeedbackMessage(content=MessageContent("Syntax error on line 5")),
                to=node,
            )

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

            # Clear messages resets in-memory messages but does not alter source file metadata on disk
            storage.clear_messages(node)
            self.assertEqual(len(storage.get_messages(node)), 1)
            self.assertTrue(
                all(isinstance(m, FeedbackMessage) for m in storage.get_messages(node))
            )
            with open(abs_src, "r", encoding="utf-8") as f:
                self.assertIn("Syntax error on line 5", f.read())

            # Mark node clean resets dirty state and updates metadata
            # Requirement: MUST update the last cleaned timestamp and remove unacted feedback entries from source metadata.
            storage.mark_node_clean(node)
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
            storage.record_source_file(node, rel_path)
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

            # Marking node clean once the source file exists writes valid cleaned metadata and clears the dirty state
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

    def test_dependency_timestamps_dirty_state(self) -> None:
        """CUJ: Dynamic dirty evaluation from dependency timestamps."""
        upstream = _make_dag_node("//pkg/lib:core", "lib")
        downstream = _make_dag_node("//pkg/app:main", "lib")
        silent_upstream = _make_dag_node("//pkg/silent:tool", "lib")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # Set dependencies: one normal, one silent
            storage.store_dependencies(
                downstream,
                {
                    DagDependency(node=upstream, is_silent=False),
                    DagDependency(node=silent_upstream, is_silent=True),
                },
            )

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

            storage.record_source_file(upstream, upstream_file)
            storage.record_source_file(downstream, downstream_file)

            # Requirement: WHEN a non-silent forward dependency has a last changed timestamp newer than the node's last cleaned timestamp, MUST return true.
            self.assertTrue(storage.is_dirty(downstream))

            # Cleaning downstream brings its last_cleaned forward, making it not dirty
            storage.mark_node_clean(downstream)
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
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            # Initially clean
            self.assertFalse(storage.is_dirty(node))

            # Requirement: MUST delete the last cleaned timestamp from the source file metadata header.
            storage.delete_last_cleaned(node)

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
            assert isinstance(fresh_storage, AgentStorageImpl)
            fresh_storage.record_source_file(node, rel_path)

            # In the fresh process, node is still dirty purely from disk state
            self.assertTrue(fresh_storage.is_dirty(node))

            # Marking node clean stamps LAST_CLEANED and makes it clean
            fresh_storage.mark_node_clean(node)
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

    def test_auditor_role_dirty_evaluation_and_stamping(self) -> None:
        """CUJ: Auditor role dirtiness tracks feedback target audit tags and upstream contracts."""
        grounding_node = _make_dag_node("//pkg/spec:item", "grounding")
        contract_node = _make_dag_node("//pkg/spec:item", "low")
        auditor_node = _make_dag_node("//pkg/spec:item", "grounding_qa")

        grounding_file = "pkg/spec/grounding/item.py"
        contract_file = "pkg/spec/low/item.pyi"
        abs_grounding = os.path.join(self.test_dir, grounding_file)
        abs_contract = os.path.join(self.test_dir, contract_file)
        os.makedirs(os.path.dirname(abs_grounding), exist_ok=True)
        os.makedirs(os.path.dirname(abs_contract), exist_ok=True)

        with open(abs_contract, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: low spec\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            storage.record_source_file(grounding_node, grounding_file)
            storage.record_source_file(contract_node, contract_file)
            storage.store_dependencies(
                auditor_node,
                {
                    DagDependency(node=contract_node, is_silent=False),
                    DagDependency(node=grounding_node, is_silent=False),
                },
            )
            storage.store_feedback_dependencies(auditor_node, {grounding_node})

            # Requirement: WHEN an auditor node has any verified feedback target file missing or any feedback target node dirty, MUST return true.
            self.assertTrue(storage.is_dirty(auditor_node))

            # Create target file with valid metadata, but missing GROUNDING_QA_AUDIT tag
            with open(abs_grounding, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-02T11:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-02T11:00:00Z\n"
                    "# CHANGE: grounding spec\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )

            # Requirement: WHEN an auditor node has any verified feedback target file metadata missing, unparseable, or missing the auditor role audit timestamp, MUST return true.
            self.assertTrue(storage.is_dirty(auditor_node))

            # Requirement: WHEN node is an auditor role, MUST stamp the role audit timestamp on each verified feedback target file metadata without updating last changed timestamp.
            storage.mark_node_clean(auditor_node)
            with open(abs_grounding, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("GROUNDING_QA_AUDIT:", content)
            self.assertIn("LAST_CHANGED: 2026-10-02T11:00:00Z", content)
            self.assertFalse(storage.is_dirty(auditor_node))

            # If target file is modified with newer LAST_CHANGED, auditor becomes dirty
            # Requirement: WHEN an auditor node has any verified feedback target file with last changed timestamp newer than its audit timestamp, MUST return true.
            with open(abs_grounding, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2026-10-02T12:00:00Z\n"
                    "# LAST_CHANGED: 2026-10-02T12:00:00Z\n"
                    "# CHANGE: grounding spec edit\n"
                    "# GROUNDING_QA_AUDIT: 2026-10-02T11:30:00Z\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )
            self.assertTrue(storage.is_dirty(auditor_node))

            # Re-certify grounding target
            storage.mark_node_clean(auditor_node)
            self.assertFalse(storage.is_dirty(auditor_node))

            # If upstream contract is modified with newer LAST_CHANGED, auditor becomes dirty
            # Requirement: WHEN an auditor node has any non-silent contract dependency with last changed timestamp newer than a verified feedback target file audit timestamp, MUST return true.
            with open(abs_contract, "w", encoding="utf-8") as f:
                f.write(
                    "# --- CLEANROOM METADATA ---\n"
                    "# LAST_CLEANED: 2099-01-01T10:00:00Z\n"
                    "# LAST_CHANGED: 2099-01-01T10:00:00Z\n"
                    "# CHANGE: contract update\n"
                    "# --- END CLEANROOM METADATA ---\n"
                )
            self.assertTrue(storage.is_dirty(auditor_node))

    def test_auditor_dual_target_qa_evaluation(self) -> None:
        """CUJ: Dual-target QA auditor checks both lib and test files and stamps both on clean."""
        lib_node = _make_dag_node("//pkg/mod:item", "lib")
        test_node = _make_dag_node("//pkg/mod:item", "test")
        qa_node = _make_dag_node("//pkg/mod:item", "qa")

        lib_file = "pkg/mod/lib/item.py"
        test_file = "pkg/mod/tests/item_test.py"
        abs_lib = os.path.join(self.test_dir, lib_file)
        abs_test = os.path.join(self.test_dir, test_file)
        os.makedirs(os.path.dirname(abs_lib), exist_ok=True)
        os.makedirs(os.path.dirname(abs_test), exist_ok=True)

        with open(abs_lib, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: lib init\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
        with open(abs_test, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: test init\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            storage.record_source_file(lib_node, lib_file)
            storage.record_source_file(test_node, test_file)

            # Prior to storing feedback dependencies, auditor operations raise KeyError
            with self.assertRaises(KeyError):
                storage.get_feedback_dependencies(qa_node)
            with self.assertRaises(KeyError):
                storage.is_dirty(qa_node)

            # Store feedback dependencies for QA auditor
            storage.store_feedback_dependencies(qa_node, {lib_node, test_node})
            feedback_deps = storage.get_feedback_dependencies(qa_node)
            self.assertEqual(feedback_deps, {lib_node, test_node})

            # Initially dirty because neither file has QA_AUDIT
            self.assertTrue(storage.is_dirty(qa_node))

            # Marking node clean stamps QA_AUDIT on BOTH lib and test
            storage.mark_node_clean(qa_node)
            self.assertFalse(storage.is_dirty(qa_node))

            with open(abs_lib, "r", encoding="utf-8") as f:
                lib_content = f.read()
            with open(abs_test, "r", encoding="utf-8") as f:
                test_content = f.read()

            self.assertIn("QA_AUDIT:", lib_content)
            self.assertIn("QA_AUDIT:", test_content)
            self.assertIn("LAST_CHANGED: 2026-10-02T10:00:00Z", lib_content)
            self.assertIn("LAST_CHANGED: 2026-10-02T10:00:00Z", test_content)

            # If lib is modified with mark_node_clean, QA becomes dirty
            storage.mark_node_clean(lib_node, ChangeDescription("updated logic"))
            self.assertTrue(storage.is_dirty(qa_node))

            # Stamping QA clean restores clean state
            storage.mark_node_clean(qa_node)
            self.assertFalse(storage.is_dirty(qa_node))

            # If test is modified with mark_node_clean, QA becomes dirty
            storage.mark_node_clean(test_node, ChangeDescription("updated tests"))
            self.assertTrue(storage.is_dirty(qa_node))

    def test_auditor_delete_last_cleaned_removes_audit_tag(self) -> None:
        """CUJ: delete_last_cleaned on an auditor node removes its audit tag from targets."""
        lib_node = _make_dag_node("//pkg/svc:item", "lib")
        test_node = _make_dag_node("//pkg/svc:item", "test")
        qa_node = _make_dag_node("//pkg/svc:item", "qa")

        lib_file = "pkg/svc/lib/item.py"
        test_file = "pkg/svc/tests/item_test.py"
        abs_lib = os.path.join(self.test_dir, lib_file)
        abs_test = os.path.join(self.test_dir, test_file)
        os.makedirs(os.path.dirname(abs_lib), exist_ok=True)
        os.makedirs(os.path.dirname(abs_test), exist_ok=True)

        with open(abs_lib, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: init\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
        with open(abs_test, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: init\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            storage.record_source_file(lib_node, lib_file)
            storage.record_source_file(test_node, test_file)
            storage.store_feedback_dependencies(qa_node, {lib_node, test_node})

            # Stamp clean
            storage.mark_node_clean(qa_node)
            self.assertFalse(storage.is_dirty(qa_node))

            # Requirement: WHEN node is an auditor role, MUST remove the role audit timestamp from each verified feedback target file metadata.
            storage.delete_last_cleaned(qa_node)

            with open(abs_lib, "r", encoding="utf-8") as f:
                lib_content = f.read()
            with open(abs_test, "r", encoding="utf-8") as f:
                test_content = f.read()

            self.assertNotIn("QA_AUDIT:", lib_content)
            self.assertNotIn("QA_AUDIT:", test_content)
            self.assertTrue(storage.is_dirty(qa_node))

    def test_mark_node_clean_with_change_description_updates_metadata(self) -> None:
        """CUJ: mark_node_clean records change description and updates timestamps on source file."""
        node = _make_dag_node("//pkg/feat:calc", "lib")
        rel_path = "pkg/feat/calc.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-01T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-01T10:00:00Z\n"
                "# CHANGE: old change\n"
                "# --- END CLEANROOM METADATA ---\n"
                "def add(a, b):\n    return a + b\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            # Requirement: MUST record change description and mark clean.
            storage.mark_node_clean(node, ChangeDescription("Added multiplication"))
            self.assertFalse(storage.is_dirty(node))

            with open(abs_src, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("CHANGE: Added multiplication", content)
            self.assertNotIn("CHANGE: old change", content)

    def test_materialize_template_creates_file_and_preserves_existing(self) -> None:
        """CUJ: materialize_template creates missing source file without overwriting existing files."""
        node_new = _make_dag_node("//pkg/new:item", "lib")
        node_existing = _make_dag_node("//pkg/exist:item", "lib")
        rel_new = "pkg/new/item.py"
        rel_exist = "pkg/exist/item.py"
        abs_exist = os.path.join(self.test_dir, rel_exist)
        os.makedirs(os.path.dirname(abs_exist), exist_ok=True)
        with open(abs_exist, "w", encoding="utf-8") as f:
            f.write("existing content\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node_new, rel_new)
            storage.record_source_file(node_existing, rel_exist)

            # Requirement: Materialize template creates missing file on disk
            storage.materialize_template(node_new)
            abs_new = os.path.join(self.test_dir, rel_new)
            self.assertTrue(os.path.isfile(abs_new))

            # Requirement: Materialize template does not overwrite existing file
            storage.materialize_template(node_existing)
            with open(abs_exist, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "existing content\n")

    def test_non_file_dependencies_do_not_mark_node_dirty(self) -> None:
        """CUJ: Non-file dependencies (e.g. guide targets) do not mark an otherwise clean node dirty."""
        node = _make_dag_node("//pkg/feat:calc", "lib")
        guide_node = _make_dag_node("//pkg/guides:guide", "")
        rel_path = "pkg/feat/calc.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-01T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-01T10:00:00Z\n"
                "# CHANGE: initial\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            # Register non-silent dependency on guide_node (which has no source file)
            storage.store_dependencies(
                node,
                {DagDependency(node=guide_node, is_silent=False)},
            )

            self.assertFalse(storage.is_dirty(node))

    def test_qualified_auditor_node_stamps_and_cleans(self) -> None:
        """CUJ: Fully qualified auditor node with store_feedback_dependencies stamps audit and marks clean."""
        lib_node = _make_dag_node("//pkg/svc:item", "//update_python_with_ai:lib")
        test_node = _make_dag_node("//pkg/svc:item", "//update_python_with_ai:test")
        qa_node = _make_dag_node("//pkg/svc:item", "//update_python_with_ai:qa")

        lib_file = "pkg/svc/lib/item.py"
        test_file = "pkg/svc/tests/item_test.py"
        abs_lib = os.path.join(self.test_dir, lib_file)
        abs_test = os.path.join(self.test_dir, test_file)
        os.makedirs(os.path.dirname(abs_lib), exist_ok=True)
        os.makedirs(os.path.dirname(abs_test), exist_ok=True)

        with open(abs_lib, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: init\n"
                "# --- END CLEANROOM METADATA ---\n"
            )
        with open(abs_test, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T10:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T10:00:00Z\n"
                "# CHANGE: init\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(lib_node, lib_file)
            storage.record_source_file(test_node, test_file)

            storage.store_feedback_dependencies(qa_node, {lib_node, test_node})
            self.assertEqual(
                storage.get_feedback_dependencies(qa_node), {lib_node, test_node}
            )

            self.assertTrue(storage.is_dirty(qa_node))
            storage.mark_node_clean(qa_node)
            self.assertFalse(storage.is_dirty(qa_node))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
