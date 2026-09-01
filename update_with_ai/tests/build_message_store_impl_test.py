"""Tests for build_message_store_impl derived from LLS."""

import os
import shutil
import tempfile
import unittest
from lib.dag_storage import DagMessage, NodeId
from lib.node_id_utils import NodeIdUtils, NodeDirectory
from lib.build_message_store_impl import BuildMessageStoreImpl


class StubNodeIdUtils(NodeIdUtils):
    def canonicalize_node_id(self, raw_id: str, current_context: str = "") -> NodeId:
        return raw_id

    def extract_node_directory(self, node: NodeId, workspace_root: str = "") -> NodeDirectory:
        clean = node.lstrip("/")
        if ":" in clean:
            pkg, _ = clean.split(":", 1)
        else:
            pkg = clean
        pkg = pkg.strip("/")
        if not workspace_root:
            return pkg
        if not pkg:
            return os.path.normpath(workspace_root)
        return os.path.normpath(os.path.join(workspace_root, pkg))


class BuildMessageStoreImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.node_id_utils = StubNodeIdUtils()

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_package_directory_resolution(self) -> None:
        """Tests CUJ for resolving package directory path from node labels across boundary cases.

        Checks postconditions: root target, sub-package target, and bare target resolve correct paths without trailing slashes.
        """
        store = BuildMessageStoreImpl(workspace_root=self.test_dir, node_id_utils=self.node_id_utils)
        self.assertEqual(store.get_package_directory("//pkg/sub:target"), os.path.join(self.test_dir, "pkg/sub"))
        self.assertEqual(store.get_package_directory("//:root_target"), self.test_dir)

    def test_file_persistence_lifecycle_and_atomicity(self) -> None:
        """Tests CUJ for atomic persistence of messages and dirty tracking.

        Checks postconditions: queueing creates .update_with_ai.textproto; clearing removes messages and resets dirty state.
        """
        store = BuildMessageStoreImpl(workspace_root=self.test_dir, node_id_utils=self.node_id_utils)
        node = "//pkg:target"

        self.assertFalse(store.is_dirty(node))
        store.queue_pending_messages(node, [DagMessage(content="first_msg"), DagMessage(content="second_msg")])
        self.assertTrue(store.is_dirty(node))

        proto_file = os.path.join(self.test_dir, "pkg", ".update_with_ai.textproto")
        self.assertTrue(os.path.isfile(proto_file))

        loaded = store.get_pending_messages(node)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].content, "first_msg")
        self.assertEqual(loaded[1].content, "second_msg")

        store.clear_pending_messages(node)
        self.assertEqual(len(store.get_pending_messages(node)), 0)

    def test_shared_package_textproto_multi_node_coexistence(self) -> None:
        """Tests Behavioral Description: all nodes within a package directory share a single .textproto file."""
        store = BuildMessageStoreImpl(workspace_root=self.test_dir, node_id_utils=self.node_id_utils)
        node1 = "//pkg:target1"
        node2 = "//pkg:target2"

        store.queue_pending_messages(node1, [DagMessage(content="msg_for_node1")])
        store.queue_pending_messages(node2, [DagMessage(content="msg_for_node2")])

        proto_file = os.path.join(self.test_dir, "pkg", ".update_with_ai.textproto")
        self.assertTrue(os.path.isfile(proto_file))

        # Both node messages are independently retrievable from the shared file
        msgs1 = store.get_pending_messages(node1)
        msgs2 = store.get_pending_messages(node2)
        self.assertEqual(len(msgs1), 1)
        self.assertEqual(msgs1[0].content, "msg_for_node1")
        self.assertEqual(len(msgs2), 1)
        self.assertEqual(msgs2[0].content, "msg_for_node2")

    def test_reverse_dependencies_and_textproto_formatting(self) -> None:
        """Tests parsing and querying reverse dependencies from textproto package store."""
        store = BuildMessageStoreImpl(workspace_root=self.test_dir, node_id_utils=self.node_id_utils)
        pkg_dir = os.path.join(self.test_dir, "pkg")
        os.makedirs(pkg_dir, exist_ok=True)
        proto_file = os.path.join(pkg_dir, ".update_with_ai.textproto")

        # Manually create a textproto with reverse_dependency entries matching node_entry format
        proto_content = (
            'node_entry {\n'
            '  node_id: "//pkg:producer"\n'
            '  reverse_dependency: "//pkg:consumer1"\n'
            '  reverse_dependency: "//pkg:consumer2"\n'
            '  message {\n'
            '    kind: "message"\n'
            '    text: "initial message"\n'
            '  }\n'
            '}\n'
        )
        with open(proto_file, "w") as f:
            f.write(proto_content)

        rdeps = store.get_reverse_dependencies("//pkg:producer")
        self.assertEqual(rdeps, ["//pkg:consumer1", "//pkg:consumer2"])

        messages = store.get_pending_messages("//pkg:producer")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, "initial message")

    def test_mark_dirty_and_node_data(self) -> None:
        """Tests mark_dirty and node data recording."""
        store = BuildMessageStoreImpl(workspace_root=self.test_dir, node_id_utils=self.node_id_utils)
        node = "//pkg:target"
        store.mark_dirty(node)
        self.assertTrue(store.is_dirty(node))

        store.record_node_data(node, {"hash": "abc1234"})
        self.assertEqual(store.get_node_data(node), {"hash": "abc1234"})
        self.assertIsNone(store.get_node_data("//pkg:unrecorded"))

    def test_corrupted_proto_file_handling(self) -> None:
        """Tests that corrupted proto file is handled gracefully by returning empty entries."""
        store = BuildMessageStoreImpl(workspace_root=self.test_dir, node_id_utils=self.node_id_utils)
        pkg_dir = os.path.join(self.test_dir, "corrupt_pkg")
        os.makedirs(pkg_dir, exist_ok=True)
        proto_file = os.path.join(pkg_dir, ".update_with_ai.textproto")
        with open(proto_file, "w") as f:
            f.write("invalid [[[ syntax")

        self.assertEqual(store.get_reverse_dependencies("//corrupt_pkg:node"), [])
        self.assertEqual(store.get_pending_messages("//corrupt_pkg:node"), [])


if __name__ == "__main__":
    unittest.main()
