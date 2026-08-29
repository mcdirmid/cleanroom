"""
Tests for the BuildMessageStoreImpl implementation.
"""

import os
import shutil
import tempfile
import unittest
from typing import cast

from lib.dag_storage import NodeMessage, MessageKind
from lib.build_message_store_impl import (
    BuildMessageStoreImpl,
    HARNESS_FILE,
    _proto_quote,
    _proto_unquote,
)


def msg(text: str, kind: str = "change") -> NodeMessage:
    return NodeMessage(kind=cast(MessageKind, kind), text=text)


class TestProtoEscaping(unittest.TestCase):
    def test_quote_unquote_roundtrip(self) -> None:
        strings = [
            "hello world",
            "hello \"world\"",
            "line 1\nline 2",
            "tab\tseparated",
            "path\\to\\file",
            "special chars: !@#$%^&*()",
            "",
        ]
        for s in strings:
            quoted = _proto_quote(s)
            self.assertTrue(quoted.startswith("\"") and quoted.endswith("\""))
            unquoted = _proto_unquote(quoted)
            self.assertEqual(unquoted, s)


class TestBuildMessageStoreImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.pkg_dir = os.path.join(self.temp_dir, "pkg")
        os.makedirs(self.pkg_dir, exist_ok=True)
        self.store = BuildMessageStoreImpl()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(self.store.read_package_messages(self.pkg_dir), {})
        self.assertEqual(self.store.get_pending_messages(self.pkg_dir, "//pkg:target"), [])
        self.assertEqual(self.store.get_known_reverse_dependencies(self.pkg_dir, "//pkg:target"), [])

    def test_add_and_get_pending_messages(self) -> None:
        target = "//pkg:target"
        self.store.add_pending_message(self.pkg_dir, target, msg("first message", "change"))
        self.store.add_pending_message(self.pkg_dir, target, msg("second message", "feedback"))

        pending = self.store.get_pending_messages(self.pkg_dir, target)
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0].text, "first message")
        self.assertEqual(pending[0].kind, "change")
        self.assertEqual(pending[1].text, "second message")
        self.assertEqual(pending[1].kind, "feedback")

    def test_set_pending_messages(self) -> None:
        target = "//pkg:target"
        self.store.add_pending_message(self.pkg_dir, target, msg("old message", "change"))
        new_msgs = [msg("new message", "change")]
        self.store.set_pending_messages(self.pkg_dir, target, new_msgs)

        pending = self.store.get_pending_messages(self.pkg_dir, target)
        self.assertEqual(pending, new_msgs)

    def test_clear_pending_messages_preserves_rev_deps(self) -> None:
        target = "//pkg:target"
        self.store.add_pending_message(self.pkg_dir, target, msg("msg", "change"))
        self.store.add_known_reverse_dependency(self.pkg_dir, target, "//other:consumer")

        self.store.clear_pending_messages(self.pkg_dir, target)
        self.assertEqual(self.store.get_pending_messages(self.pkg_dir, target), [])
        self.assertEqual(self.store.get_known_reverse_dependencies(self.pkg_dir, target), ["//other:consumer"])

    def test_delete_node_messages(self) -> None:
        target = "//pkg:target"
        self.store.add_pending_message(self.pkg_dir, target, msg("msg", "change"))
        self.store.add_known_reverse_dependency(self.pkg_dir, target, "//other:consumer")

        self.store.delete_node_messages(self.pkg_dir, target)
        self.assertEqual(self.store.get_pending_messages(self.pkg_dir, target), [])
        self.assertEqual(self.store.get_known_reverse_dependencies(self.pkg_dir, target), [])

    def test_known_reverse_dependencies_deduplicated(self) -> None:
        target = "//pkg:target"
        self.store.add_known_reverse_dependency(self.pkg_dir, target, "//consumer:a")
        self.store.add_known_reverse_dependency(self.pkg_dir, target, "//consumer:a")
        self.store.add_known_reverse_dependency(self.pkg_dir, target, "//consumer:b")

        revs = self.store.get_known_reverse_dependencies(self.pkg_dir, target)
        self.assertEqual(sorted(revs), ["//consumer:a", "//consumer:b"])

    def test_clear_known_reverse_dependencies(self) -> None:
        target = "//pkg:target"
        self.store.add_pending_message(self.pkg_dir, target, msg("msg", "change"))
        self.store.add_known_reverse_dependency(self.pkg_dir, target, "//consumer:a")

        self.store.clear_known_reverse_dependencies(self.pkg_dir, target)
        self.assertEqual(self.store.get_known_reverse_dependencies(self.pkg_dir, target), [])
        self.assertEqual(len(self.store.get_pending_messages(self.pkg_dir, target)), 1)

    def test_multiple_nodes_in_same_package(self) -> None:
        t1 = "//pkg:t1"
        t2 = "//pkg:t2"
        self.store.add_pending_message(self.pkg_dir, t1, msg("m1", "change"))
        self.store.add_pending_message(self.pkg_dir, t2, msg("m2", "feedback"))

        self.assertEqual(self.store.get_pending_messages(self.pkg_dir, t1)[0].text, "m1")
        self.assertEqual(self.store.get_pending_messages(self.pkg_dir, t2)[0].text, "m2")


if __name__ == "__main__":
    unittest.main()
