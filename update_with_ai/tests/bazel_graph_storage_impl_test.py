"""
Tests for the bazel_graph_storage_impl component (LLS: bazel_graph_storage_impl,
with dependencies dag_storage-low.md, bazel_graph_storage-low.md, sandbox-low.md).

Covers the BaseBazelGraphStorageImpl base-class behavior (message-file operations,
dependency retrieval with the reverse-dependency recording side effect,
definition/package-directory resolution) and the manifest-driven
BazelGraphStorageFileImpl concrete implementation: sandbox configuration
derived from manifests, package directory resolution, manifest synthesis for
declared dependencies lacking their own manifest, and configuration validation.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional
from unittest import mock

from update_with_ai.lib.bazel_graph_storage import (
    GraphConfig,
    NodeDefinition,
    NodeId,
    PackageDirectory,
)
from update_with_ai.lib.bazel_graph_storage_impl import (
    BaseBazelGraphStorageImpl,
    BazelGraphStorageFileImpl,
)
from update_with_ai.lib.dag_storage import NodeMessage, PendingMessages
from update_with_ai.lib.sandbox import SandboxConfig

HARNESS_FILE = ".update_with_ai.json"


def _make_definition(prompt: str) -> NodeDefinition:
    """Build a NodeDefinition with an (empty) sandbox config."""
    return NodeDefinition(
        prompt=prompt,
        sandbox_config=SandboxConfig(
            file_mappings={},
            readable_paths=[],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=100,
            search_result_limit=10,
        ),
    )


class _MockGraphStorageImpl(BaseBazelGraphStorageImpl):
    """Minimal concrete BaseBazelGraphStorageImpl used to exercise the base class."""

    def __init__(
        self,
        adjacency: Dict[NodeId, List[NodeId]],
        definitions: Optional[Dict[NodeId, NodeDefinition]] = None,
        package_dirs: Optional[Dict[NodeId, PackageDirectory]] = None,
        propagating: Optional[Dict[NodeId, List[NodeId]]] = None,
    ) -> None:
        self._adjacency = adjacency
        self._definitions = definitions or {}
        self._package_dirs = package_dirs or {}
        # By default every dependency propagates; pass `propagating` to model
        # dependencies whose changes do not propagate (silent deps).
        self._propagating = propagating if propagating is not None else adjacency
        super().__init__(GraphConfig(graph_source="mock-graph-source"))

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        return self._adjacency

    def _build_propagating_deps(self) -> Dict[NodeId, List[NodeId]]:
        return self._propagating

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        return self._definitions

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        return self._package_dirs


def _make_pkg_dir(root: str, name: str) -> str:
    """Create and return a real package directory under the temp root."""
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    return d


class TestBaseBazelGraphStorageImplConfig(unittest.TestCase):
    """Config validation for the BaseBazelGraphStorageImpl base class."""

    def test_config_without_graph_source_or_workspace_root_raises_value_error(self):
        """GraphConfig must provide at least one of graph_source or workspace_root."""
        with self.assertRaises(ValueError) as ctx:
            BaseBazelGraphStorageImpl(GraphConfig())
        self.assertIn("graph_source", str(ctx.exception))


class TestBaseBazelGraphStorageImplResolution(unittest.TestCase):
    """Base-class resolution behavior (definitions, package dirs, dependencies)."""

    def setUp(self) -> None:
        self._tmp_root = tempfile.mkdtemp(prefix="bgsi_resolve_")
        self.pkg_a = _make_pkg_dir(self._tmp_root, "pkg_a")
        self.pkg_b = _make_pkg_dir(self._tmp_root, "pkg_b")
        self.pkg_c = _make_pkg_dir(self._tmp_root, "pkg_c")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def _graph(self) -> BaseBazelGraphStorageImpl:
        return _MockGraphStorageImpl(
            adjacency={
                "//pkg:a": ["//pkg:b", "//pkg:c"],
                "//pkg:b": [],
                "//pkg:c": [],
            },
            definitions={"//pkg:a": _make_definition("prompt-a")},
            package_dirs={
                "//pkg:a": self.pkg_a,
                "//pkg:b": self.pkg_b,
                "//pkg:c": self.pkg_c,
            },
        )

    def test_resolve_node_definition_returns_prompt_and_sandbox_config(self):
        graph = self._graph()
        definition = graph.resolve_node_definition("//pkg:a")
        self.assertEqual(definition.prompt, "prompt-a")
        self.assertIsInstance(definition.sandbox_config, SandboxConfig)

    def test_resolve_package_directory_returns_directory(self):
        graph = self._graph()
        self.assertEqual(graph.resolve_package_directory("//pkg:a"), self.pkg_a)

    def test_get_node_dependencies_returns_dependencies(self):
        graph = self._graph()
        self.assertEqual(
            graph.get_node_dependencies("//pkg:a"), ["//pkg:b", "//pkg:c"]
        )
        self.assertEqual(graph.get_node_dependencies("//pkg:c"), [])

    def test_get_known_reverse_dependencies_empty_when_none_recorded(self):
        graph = self._graph()
        self.assertEqual(graph.get_known_reverse_dependencies("//pkg:b"), [])


class TestReverseDependencyRecording(unittest.TestCase):
    """dag_storage contract: get_node_dependencies records the node as a known
    reverse dependency of each propagating dependency (at most once);
    dependencies whose changes do not propagate are not recorded; recordings
    persist."""

    def setUp(self) -> None:
        self._tmp_root = tempfile.mkdtemp(prefix="bgsi_revdep_")
        self.pkg_a = _make_pkg_dir(self._tmp_root, "pkg_a")
        self.pkg_b = _make_pkg_dir(self._tmp_root, "pkg_b")
        self.pkg_c = _make_pkg_dir(self._tmp_root, "pkg_c")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def _graph(self) -> BaseBazelGraphStorageImpl:
        return _MockGraphStorageImpl(
            adjacency={
                "//pkg:a": ["//pkg:b", "//pkg:c"],
                "//pkg:b": [],
                "//pkg:c": [],
            },
            definitions={},
            package_dirs={
                "//pkg:a": self.pkg_a,
                "//pkg:b": self.pkg_b,
                "//pkg:c": self.pkg_c,
            },
        )

    def test_get_node_dependencies_records_node_as_reverse_dependency(self):
        graph = self._graph()
        graph.get_node_dependencies("//pkg:a")

        self.assertEqual(
            graph.get_known_reverse_dependencies("//pkg:b"), ["//pkg:a"]
        )
        self.assertEqual(
            graph.get_known_reverse_dependencies("//pkg:c"), ["//pkg:a"]
        )
        self.assertEqual(graph.get_known_reverse_dependencies("//pkg:a"), [])

    def test_non_propagating_dependencies_are_not_recorded(self):
        """dag_storage LLS: a node is recorded as a reverse dependency only of
        its propagating dependencies; dependencies whose changes do not
        propagate to it (silent deps) are not recorded."""
        graph = _MockGraphStorageImpl(
            adjacency={
                "//pkg:a": ["//pkg:b", "//pkg:c"],
                "//pkg:b": [],
                "//pkg:c": [],
            },
            propagating={
                # c is an adjacency dependency of a but does not propagate.
                "//pkg:a": ["//pkg:b"],
                "//pkg:b": [],
                "//pkg:c": [],
            },
            definitions={},
            package_dirs={
                "//pkg:a": self.pkg_a,
                "//pkg:b": self.pkg_b,
                "//pkg:c": self.pkg_c,
            },
        )
        graph.get_node_dependencies("//pkg:a")

        self.assertEqual(
            graph.get_known_reverse_dependencies("//pkg:b"), ["//pkg:a"]
        )
        self.assertEqual(graph.get_known_reverse_dependencies("//pkg:c"), [])

    def test_repeated_recordings_are_deduplicated(self):
        # dag_storage LLS: a node is recorded at most once per dependency;
        # repeated recordings do not add duplicates.
        graph = self._graph()
        graph.get_node_dependencies("//pkg:a")
        graph.get_node_dependencies("//pkg:a")
        graph.get_node_dependencies("//pkg:a")

        self.assertEqual(
            graph.get_known_reverse_dependencies("//pkg:b"), ["//pkg:a"]
        )

    def test_recordings_persist_across_instances(self):
        # The recording is stored in the dependency's message file, so a fresh
        # instance sees the recorded reverse dependency.
        graph = self._graph()
        graph.get_node_dependencies("//pkg:a")

        fresh = self._graph()
        self.assertEqual(
            fresh.get_known_reverse_dependencies("//pkg:b"), ["//pkg:a"]
        )


class TestMessageFileOperations(unittest.TestCase):
    """Message-file operations per dag_storage-low.md and the impl LLS."""

    def setUp(self) -> None:
        self._tmp_root = tempfile.mkdtemp(prefix="bgsi_store_")
        self.pkg_a = _make_pkg_dir(self._tmp_root, "pkg_a")
        self.pkg_b = _make_pkg_dir(self._tmp_root, "pkg_b")
        self.pkg_other = _make_pkg_dir(self._tmp_root, "pkg_other")
        self.graph = _MockGraphStorageImpl(
            adjacency={"node_a": [], "node_b": ["node_a"], "other": []},
            definitions={},
            package_dirs={
                "node_a": self.pkg_a,
                "node_b": self.pkg_b,
                "other": self.pkg_other,
            },
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def harness_file(self, node_id: NodeId) -> str:
        return os.path.join(self.graph.resolve_package_directory(node_id), HARNESS_FILE)

    # -- get_pending_messages ------------------------------------------------

    def test_get_pending_messages_missing_file_returns_empty(self):
        """LLS: a missing .update_with_ai.json reads as empty and is not created."""
        self.assertEqual(self.graph.get_pending_messages("node_a"), [])
        self.assertFalse(os.path.exists(self.harness_file("node_a")))

    def test_get_pending_messages_missing_node_entry_returns_empty(self):
        """LLS: an absent node entry reads as an empty list."""
        self.graph.add_messages("other", ["msg"])
        self.assertEqual(self.graph.get_pending_messages("node_a"), [])

    def test_get_pending_messages_returns_stored_messages(self):
        """LLS: returns the node's pending messages exactly as stored."""
        self.graph.add_messages("node_a", ["msg1", "msg2"])
        self.assertEqual(
            self.graph.get_pending_messages("node_a"), ["msg1", "msg2"]
        )

    # -- add_messages --------------------------------------------------------

    def test_add_messages_appends_to_pending_set_and_persists(self):
        """LLS: add_messages appends to the node's pending set and persists."""
        self.graph.add_messages("node_a", ["msg1"])
        self.graph.add_messages("node_a", ["msg2", "msg3"])

        self.assertEqual(
            self.graph.get_pending_messages("node_a"), ["msg1", "msg2", "msg3"]
        )
        self.assertTrue(os.path.isfile(self.harness_file("node_a")))

    def test_add_messages_visible_to_new_store_instance(self):
        """LLS: a new store instance reading the same directory sees the messages."""
        self.graph.add_messages("node_a", ["msg1"])

        fresh = _MockGraphStorageImpl(
            adjacency={"node_a": [], "node_b": []},
            definitions={},
            package_dirs={"node_a": self.pkg_a, "node_b": self.pkg_b},
        )

        self.assertEqual(fresh.get_pending_messages("node_a"), ["msg1"])

    # -- delete_node_data -----------------------------------------------------

    def test_delete_node_data_removes_messages_and_reverse_dependencies(self):
        """LLS: delete_node_data deletes the node's data — both its pending
        messages and its known reverse dependencies."""
        self.graph.add_messages("node_a", ["msg1", "msg2"])
        # node_b depends on node_a; resolving node_b's dependencies records
        # node_b as a known reverse dependency of node_a.
        self.graph.get_node_dependencies("node_b")
        self.assertEqual(
            self.graph.get_known_reverse_dependencies("node_a"), ["node_b"]
        )

        self.graph.delete_node_data("node_a")

        self.assertEqual(self.graph.get_pending_messages("node_a"), [])
        self.assertEqual(self.graph.get_known_reverse_dependencies("node_a"), [])

    def test_delete_node_data_leaves_other_nodes_untouched(self):
        """LLS: deleting one node's entry leaves other nodes' entries intact."""
        self.graph.add_messages("node_a", ["a"])
        self.graph.add_messages("node_b", ["b"])

        self.graph.delete_node_data("node_a")

        self.assertEqual(self.graph.get_pending_messages("node_a"), [])
        self.assertEqual(self.graph.get_pending_messages("node_b"), ["b"])

    # -- file naming and layout ---------------------------------------------

    def test_harness_file_is_update_with_ai_json_in_package_dir(self):
        """LLS: a single JSON file named .update_with_ai.json in the node.s package directory."""
        self.graph.add_messages("node_a", ["msg"])

        messages_file = self.harness_file("node_a")
        self.assertEqual(os.path.dirname(messages_file), self.pkg_a)
        self.assertEqual(os.path.basename(messages_file), HARNESS_FILE)
        self.assertTrue(os.path.isfile(messages_file))

    def test_single_messages_file_per_package_directory(self):
        """LLS: one .update_with_ai.json per package directory holds all nodes in it."""
        shared = _make_pkg_dir(self._tmp_root, "shared_pkg")
        graph = _MockGraphStorageImpl(
            adjacency={"node_a": [], "node_b": []},
            definitions={},
            package_dirs={"node_a": shared, "node_b": shared},
        )

        graph.add_messages("node_a", ["a"])
        graph.add_messages("node_b", ["b"])

        self.assertEqual(graph.get_pending_messages("node_a"), ["a"])
        self.assertEqual(graph.get_pending_messages("node_b"), ["b"])

    def test_different_packages_have_separate_message_files(self):
        """LLS: each package directory holds its own .update_with_ai.json."""
        self.graph.add_messages("node_a", ["a"])
        self.graph.add_messages("node_b", ["b"])

        self.assertNotEqual(self.pkg_a, self.pkg_b)
        self.assertEqual(
            len(list(Path(self.pkg_a).glob(HARNESS_FILE))), 1
        )
        self.assertEqual(
            len(list(Path(self.pkg_b).glob(HARNESS_FILE))), 1
        )

    # -- atomic writes -------------------------------------------------------

    def test_write_uses_temp_file_and_atomic_replace(self):
        """LLS: writes go to a temporary file, then atomically replaced onto .update_with_ai.json."""
        messages_file = self.harness_file("node_a")
        calls: List[tuple] = []
        real_replace = os.replace

        def _recording_replace(src: str, dst: str) -> None:
            calls.append((src, dst))
            return real_replace(src, dst)

        with mock.patch(
            "update_with_ai.lib.bazel_graph_storage_impl.os.replace", side_effect=_recording_replace
        ):
            self.graph.add_messages("node_a", ["msg"])

        self.assertEqual(len(calls), 1)
        src, dst = calls[0]
        self.assertEqual(dst, messages_file)
        self.assertNotEqual(src, messages_file)  # written via a temp file
        self.assertFalse(os.path.exists(src))  # temp file consumed by the replace

    def test_write_failure_before_replace_leaves_previous_file_unchanged(self):
        """LLS: a failed replace leaves the previous message file unchanged."""
        self.graph.add_messages("node_a", ["old"])

        with mock.patch(
            "update_with_ai.lib.bazel_graph_storage_impl.os.replace",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaises(OSError):
                self.graph.add_messages("node_a", ["new"])

        self.assertEqual(self.graph.get_pending_messages("node_a"), ["old"])

    @unittest.skipIf(os.geteuid() == 0, "root bypasses directory write permissions")
    def test_write_failure_read_only_dir_leaves_file_unchanged(self):
        """LLS: a failure before replacement (unwritable dir) leaves the file unchanged."""
        self.graph.add_messages("node_a", ["old"])
        os.chmod(self.pkg_a, 0o500)
        try:
            with self.assertRaises(OSError):
                self.graph.add_messages("node_a", ["new"])
        finally:
            os.chmod(self.pkg_a, 0o700)

        self.assertEqual(self.graph.get_pending_messages("node_a"), ["old"])

    # -- persistence / no in-memory state -----------------------------------

    def test_no_in_memory_state_reads_reflect_file(self):
        """LLS: the message file is the sole state; another instance's writes are visible."""
        self.graph.add_messages("node_a", ["m1"])

        other = _MockGraphStorageImpl(
            adjacency={"node_a": [], "node_b": []},
            definitions={},
            package_dirs={"node_a": self.pkg_a, "node_b": self.pkg_b},
        )
        other.add_messages("node_a", ["m2"])

        self.assertEqual(
            self.graph.get_pending_messages("node_a"), ["m1", "m2"]
        )

    def test_messages_persist_across_component_restarts(self):
        """LLS: messages persist across component restarts (JSON file on disk)."""
        self.graph.add_messages("node_a", ["m1", "m2"])

        restarted = _MockGraphStorageImpl(
            adjacency={"node_a": [], "node_b": []},
            definitions={},
            package_dirs={"node_a": self.pkg_a, "node_b": self.pkg_b},
        )
        self.assertEqual(restarted.get_pending_messages("node_a"), ["m1", "m2"])

        restarted.add_messages("node_a", ["m3"])
        self.assertEqual(
            self.graph.get_pending_messages("node_a"), ["m1", "m2", "m3"]
        )


class _Workspace:
    """A temporary workspace with manifest-defined nodes.

    Node graph (labels and manifest contents):

      //pkg_a:a  deps=["//pkg_c:c"], srcs=["a1.txt"],
                 silent_srcs=["a_priv.txt"], verify="echo verification-output"
      //pkg_b:b  deps=["//pkg_a:a"], silent_deps=["//pkg_c:c"],
                 feedback_deps=["//pkg_a:a"],
                 srcs=["b1.txt", "shared.txt"], silent_srcs=["b_priv.txt"]
      //pkg_c:c  srcs=["shared.txt", "c_only.txt"]
      //pkg_d:d  feedback_deps=["//pkg_a:a"], srcs=["d1.txt"]
      //pkg_e:e  star_deps=["//pkg_a:a"], srcs=["e1.txt", "shared.txt"]
                 (star dep a's closure covers c: c's srcs are readable by e;
                 e's own "shared.txt" wins over c's on name collision)
    """

    def __init__(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_graph_storage_impl_test_")
        self.root = Path(self._tmp)

    def write_manifest(
        self,
        pkg: str,
        name: str,
        label: str,
        prompt: str,
        srcs: Optional[List[str]] = None,
        silent_srcs: Optional[List[str]] = None,
        deps: Optional[List[str]] = None,
        silent_deps: Optional[List[str]] = None,
        feedback_deps: Optional[List[str]] = None,
        star_deps: Optional[List[str]] = None,
        verify: Optional[str] = None,
    ) -> None:
        pkg_dir = self.root / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "label": label,
            "name": name,
            "prompt": prompt,
            "tools": [],
            "deps": deps or [],
            "silent_deps": silent_deps or [],
            "feedback_deps": feedback_deps or [],
            "star_deps": star_deps or [],
            "srcs": srcs or [],
            "silent_srcs": silent_srcs or [],
            "verify": verify,
        }
        (pkg_dir / f"{name}_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        for src in (srcs or []) + (silent_srcs or []):
            (pkg_dir / src).touch()

    def populate(self) -> None:
        """Write the manifest graph described in the class docstring."""
        self.write_manifest(
            "pkg_a",
            "a",
            "//pkg_a:a",
            "prompt for a",
            srcs=["a1.txt"],
            silent_srcs=["a_priv.txt"],
            deps=["//pkg_c:c"],
            verify="echo verification-output",
        )
        self.write_manifest(
            "pkg_b",
            "b",
            "//pkg_b:b",
            "prompt for b",
            srcs=["b1.txt", "shared.txt"],
            silent_srcs=["b_priv.txt"],
            deps=["//pkg_a:a"],
            silent_deps=["//pkg_c:c"],
            feedback_deps=["//pkg_a:a"],
        )
        self.write_manifest(
            "pkg_c",
            "c",
            "//pkg_c:c",
            "prompt for c",
            srcs=["shared.txt", "c_only.txt"],
        )
        self.write_manifest(
            "pkg_d",
            "d",
            "//pkg_d:d",
            "prompt for d",
            srcs=["d1.txt"],
            feedback_deps=["//pkg_a:a"],
        )
        self.write_manifest(
            "pkg_e",
            "e",
            "//pkg_e:e",
            "prompt for e",
            srcs=["e1.txt", "shared.txt"],
            star_deps=["//pkg_a:a"],
        )

    def close(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestBazelGraphStorageFileImpl(unittest.TestCase):
    """Tests for the manifest-driven BazelGraphStorageFileImpl."""

    @contextmanager
    def _workspace(self):
        ws = _Workspace()
        try:
            ws.populate()
            yield ws
        finally:
            ws.close()

    def _build_graph(self, ws: _Workspace) -> BazelGraphStorageFileImpl:
        """Build the graph with BUILD_WORKSPACE_DIRECTORY absent so package
        directories resolve deterministically inside the temp workspace."""
        with mock.patch.dict(os.environ):
            os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
            return BazelGraphStorageFileImpl(
                GraphConfig(workspace_root=str(ws.root))
            )

    def test_graph_source_only_config_raises_value_error(self):
        """BazelGraphStorageFileImpl requires workspace_root (graph_source-only rejected)."""
        with self.assertRaises(ValueError) as ctx:
            BazelGraphStorageFileImpl(GraphConfig(graph_source="//some:artifact"))
        self.assertIn("workspace_root", str(ctx.exception))

    def test_config_without_workspace_root_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            BazelGraphStorageFileImpl(GraphConfig())
        self.assertIn("workspace_root", str(ctx.exception))

    def test_resolve_node_definition_returns_prompt_and_sandbox_config(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            definition = graph.resolve_node_definition("//pkg_a:a")
            self.assertEqual(definition.prompt, "prompt for a")
            self.assertIsInstance(definition.sandbox_config, SandboxConfig)
            self.assertEqual(
                graph.resolve_node_definition("//pkg_b:b").prompt, "prompt for b"
            )

    def test_readable_paths_are_own_srcs_plus_dep_srcs(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            # b's readable: own srcs (b1, shared) + deps' srcs (a's a1). c is a
            # silent dep of b: its "shared.txt" collides with b's own src and is
            # not duplicated, and "c_only.txt" is not readable at all.
            self.assertCountEqual(
                graph.resolve_node_definition("//pkg_b:b").sandbox_config.readable_paths,
                ["b1.txt", "shared.txt", "a1.txt"],
            )
            # a's readable: own srcs (a1) + deps' srcs (c's shared, c_only).
            self.assertCountEqual(
                graph.resolve_node_definition("//pkg_a:a").sandbox_config.readable_paths,
                ["a1.txt", "shared.txt", "c_only.txt"],
            )

    def test_readable_paths_exclude_silent_dep_srcs(self):
        """A silent dep's srcs are not readable: c is b's silent dep, so
        c_only.txt (c's src) is neither readable nor mapped for b."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            b_readable = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.readable_paths
            b_mappings = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.file_mappings
            self.assertNotIn("c_only.txt", b_readable)
            self.assertNotIn("c_only.txt", b_mappings)

    def test_readable_paths_exclude_silent_srcs(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            # Neither a node's own silent_srcs nor its deps' silent_srcs are readable.
            b_readable = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.readable_paths
            a_readable = graph.resolve_node_definition(
                "//pkg_a:a"
            ).sandbox_config.readable_paths
            self.assertNotIn("b_priv.txt", b_readable)  # own silent_srcs
            self.assertNotIn("a_priv.txt", b_readable)  # dep's silent_srcs
            self.assertNotIn("a_priv.txt", a_readable)  # own silent_srcs

    def test_feedback_deps_are_included_in_deps(self):
        """A feedback dep is automatically a dep: d declares only feedback_deps
        ["//pkg_a:a"], so a's srcs are readable, a is in d's adjacency, and a
        is d's only blame target."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            d_readable = graph.resolve_node_definition(
                "//pkg_d:d"
            ).sandbox_config.readable_paths
            self.assertCountEqual(d_readable, ["d1.txt", "a1.txt"])
            self.assertEqual(graph.get_node_dependencies("//pkg_d:d"), ["//pkg_a:a"])

    def test_star_deps_transitive_closure_srcs_are_readable(self):
        """A star dep's closure is readable: e's star dep a depends on c, so
        e can read a's and c's srcs (plus its own)."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            e_readable = graph.resolve_node_definition(
                "//pkg_e:e"
            ).sandbox_config.readable_paths
            self.assertCountEqual(
                e_readable, ["e1.txt", "shared.txt", "a1.txt", "c_only.txt"]
            )
            e_mappings = graph.resolve_node_definition(
                "//pkg_e:e"
            ).sandbox_config.file_mappings
            self.assertEqual(
                e_mappings["a1.txt"], str(ws.root / "pkg_a" / "a1.txt")
            )
            self.assertEqual(
                e_mappings["c_only.txt"], str(ws.root / "pkg_c" / "c_only.txt")
            )
            # e's own src wins on name collision with closure src (c's shared.txt).
            self.assertEqual(
                e_mappings["shared.txt"], str(ws.root / "pkg_e" / "shared.txt")
            )
            # silent_srcs of closure nodes are not readable.
            self.assertNotIn("a_priv.txt", e_readable)
            # writable set is unchanged: only own srcs + own silent_srcs.
            e_writable = graph.resolve_node_definition(
                "//pkg_e:e"
            ).sandbox_config.writable_paths
            self.assertCountEqual(e_writable, ["e1.txt", "shared.txt"])

    def test_star_deps_are_included_in_deps(self):
        """A star dep is automatically a dep: e declares only star_deps
        ["//pkg_a:a"], so a is in e's adjacency and is a propagating dep."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            self.assertEqual(graph.get_node_dependencies("//pkg_e:e"), ["//pkg_a:a"])
            # Star deps are propagating: retrieving e's deps recorded e as
            # a's reverse dependency (a changes propagate to e).
            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_a:a"), ["//pkg_e:e"]
            )

    def test_star_closure_skips_silent_deps(self):
        """Silent deps inside a star closure are cleaned but their srcs are
        not readable: r stars s (deps=[t], silent_deps=[u]); t's srcs are
        readable, u's are not."""
        ws = _Workspace()
        try:
            ws.write_manifest("pkg_t", "t", "//pkg_t:t", "pt", srcs=["t1.txt"])
            ws.write_manifest("pkg_u", "u", "//pkg_u:u", "pu", srcs=["u1.txt"])
            ws.write_manifest(
                "pkg_s",
                "s",
                "//pkg_s:s",
                "ps",
                srcs=["s1.txt"],
                deps=["//pkg_t:t"],
                silent_deps=["//pkg_u:u"],
            )
            ws.write_manifest(
                "pkg_r",
                "r",
                "//pkg_r:r",
                "pr",
                srcs=["r1.txt"],
                star_deps=["//pkg_s:s"],
            )
            graph = self._build_graph(ws)
            r_readable = graph.resolve_node_definition(
                "//pkg_r:r"
            ).sandbox_config.readable_paths
            self.assertCountEqual(r_readable, ["r1.txt", "s1.txt", "t1.txt"])
            self.assertNotIn("u1.txt", r_readable)
        finally:
            ws.close()

    def test_plain_deps_transitive_srcs_are_not_readable(self):
        """Closure is only via star deps: a plain dep's transitive deps'
        srcs are not readable. v deps=[s]; t (s's dep) is not readable."""
        ws = _Workspace()
        try:
            ws.write_manifest("pkg_t", "t", "//pkg_t:t", "pt", srcs=["t1.txt"])
            ws.write_manifest(
                "pkg_s",
                "s",
                "//pkg_s:s",
                "ps",
                srcs=["s1.txt"],
                deps=["//pkg_t:t"],
            )
            ws.write_manifest(
                "pkg_v",
                "v",
                "//pkg_v:v",
                "pv",
                srcs=["v1.txt"],
                deps=["//pkg_s:s"],
            )
            graph = self._build_graph(ws)
            v_readable = graph.resolve_node_definition(
                "//pkg_v:v"
            ).sandbox_config.readable_paths
            self.assertCountEqual(v_readable, ["v1.txt", "s1.txt"])
            self.assertNotIn("t1.txt", v_readable)
        finally:
            ws.close()

    def test_star_dep_without_manifest_contributes_nothing(self):
        """A star dep whose manifest is not loaded is synthesized (no srcs):
        the node resolves and its readable set gains nothing."""
        with self._workspace() as ws:
            ws.write_manifest(
                "pkg_f",
                "f",
                "//pkg_f:f",
                "pf",
                srcs=["f1.txt"],
                star_deps=["//missing:m"],
            )
            graph = self._build_graph(ws)
            f_readable = graph.resolve_node_definition(
                "//pkg_f:f"
            ).sandbox_config.readable_paths
            self.assertCountEqual(f_readable, ["f1.txt"])
            # The missing star dep is synthesized into a resolvable node.
            self.assertEqual(
                graph.resolve_package_directory("//missing:m"),
                str(ws.root / "missing"),
            )

    def test_writable_paths_are_own_srcs_plus_own_silent_srcs(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            b_writable = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.writable_paths
            self.assertCountEqual(b_writable, ["b1.txt", "shared.txt", "b_priv.txt"])
            # Deps' srcs (and deps' silent_srcs) are not writable.
            self.assertNotIn("a1.txt", b_writable)
            self.assertNotIn("a_priv.txt", b_writable)
            a_writable = graph.resolve_node_definition(
                "//pkg_a:a"
            ).sandbox_config.writable_paths
            self.assertCountEqual(a_writable, ["a1.txt", "a_priv.txt"])
            self.assertNotIn("shared.txt", a_writable)  # c's src, not writable

    def test_blame_targets_are_feedback_deps(self):
        """Only feedback deps may receive feedback: b's blame targets are its
        feedback dep a; its silent dep c is not a blame target."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            self.assertEqual(
                graph.resolve_node_definition("//pkg_b:b").sandbox_config.blame_targets,
                ["//pkg_a:a"],
            )
            self.assertEqual(
                graph.resolve_node_definition("//pkg_d:d").sandbox_config.blame_targets,
                ["//pkg_a:a"],
            )
            # No feedback deps declared -> no blame targets (deps and silent
            # deps alone do not make targets blameable).
            self.assertEqual(
                graph.resolve_node_definition("//pkg_a:a").sandbox_config.blame_targets,
                [],
            )
            self.assertEqual(
                graph.resolve_node_definition("//pkg_c:c").sandbox_config.blame_targets,
                [],
            )

    def test_file_mappings_map_bare_names_to_real_paths(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            b_mappings = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.file_mappings
            self.assertEqual(
                b_mappings["b1.txt"], str(ws.root / "pkg_b" / "b1.txt")
            )
            self.assertEqual(
                b_mappings["b_priv.txt"], str(ws.root / "pkg_b" / "b_priv.txt")
            )
            self.assertEqual(
                b_mappings["a1.txt"], str(ws.root / "pkg_a" / "a1.txt")
            )
            # b's silent dep c's srcs are not mapped (not readable).
            self.assertNotIn("c_only.txt", b_mappings)
            # a's dep src maps into its own package dir
            a_mappings = graph.resolve_node_definition(
                "//pkg_a:a"
            ).sandbox_config.file_mappings
            self.assertEqual(
                a_mappings["shared.txt"], str(ws.root / "pkg_c" / "shared.txt")
            )

    def test_file_mappings_own_files_win_on_name_collision(self):
        """b's own shared.txt wins over dep c's shared.txt."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            b_mappings = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.file_mappings
            self.assertEqual(
                b_mappings["shared.txt"], str(ws.root / "pkg_b" / "shared.txt")
            )

    def test_get_node_dependencies_returns_deps_plus_silent_deps(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            self.assertEqual(
                graph.get_node_dependencies("//pkg_b:b"),
                ["//pkg_a:a", "//pkg_c:c"],
            )
            self.assertEqual(
                graph.get_node_dependencies("//pkg_a:a"), ["//pkg_c:c"]
            )
            self.assertEqual(graph.get_node_dependencies("//pkg_c:c"), [])
            # d declares only feedback deps; they are its dependencies.
            self.assertEqual(
                graph.get_node_dependencies("//pkg_d:d"), ["//pkg_a:a"]
            )

    def test_get_node_dependencies_records_reverse_dependencies(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            graph.get_node_dependencies("//pkg_b:b")

            # a is b's dep (propagating): b is recorded as a's reverse dep.
            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_a:a"), ["//pkg_b:b"]
            )
            # c is b's silent dep: b is NOT recorded as c's reverse dep, so
            # c's changes do not propagate to b (b does not become dirty).
            self.assertEqual(graph.get_known_reverse_dependencies("//pkg_c:c"), [])
            self.assertEqual(graph.get_known_reverse_dependencies("//pkg_b:b"), [])

    def test_silent_deps_are_dependencies_but_do_not_propagate_changes(self):
        """A silent dep is still a dependency (adjacency, cleaned before the
        node) but does not record the node as a reverse dependency."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            # c is b's silent dep: it is in b's dependencies...
            self.assertEqual(
                graph.get_node_dependencies("//pkg_b:b"),
                ["//pkg_a:a", "//pkg_c:c"],
            )
            # ...but b is not recorded as c's reverse dependency.
            self.assertEqual(graph.get_known_reverse_dependencies("//pkg_c:c"), [])
            # a is b's (propagating) dep: b is recorded.
            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_a:a"), ["//pkg_b:b"]
            )
            # Feedback deps propagate too: d declares a as a feedback dep, so
            # d is recorded as a's reverse dependency when d's deps resolve.
            graph.get_node_dependencies("//pkg_d:d")
            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_a:a"),
                ["//pkg_b:b", "//pkg_d:d"],
            )

    def test_resolve_package_directory_returns_manifest_directory(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            self.assertEqual(
                graph.resolve_package_directory("//pkg_b:b"), str(ws.root / "pkg_b")
            )
            self.assertEqual(
                graph.resolve_package_directory("//pkg_a:a"), str(ws.root / "pkg_a")
            )

    def test_package_directory_maps_onto_build_workspace_directory(self):
        """BUILD_WORKSPACE_DIRECTORY maps manifest dirs onto the real source tree."""
        fake_real_root = tempfile.mkdtemp(prefix="cleanroom_fake_root_")
        try:
            with self._workspace() as ws, mock.patch.dict(
                os.environ, {"BUILD_WORKSPACE_DIRECTORY": fake_real_root}
            ):
                graph = BazelGraphStorageFileImpl(
                    GraphConfig(workspace_root=str(ws.root))
                )
                self.assertEqual(
                    graph.resolve_package_directory("//pkg_b:b"),
                    os.path.join(fake_real_root, "pkg_b"),
                )
        finally:
            shutil.rmtree(fake_real_root, ignore_errors=True)

    def test_declared_dependency_without_manifest_is_synthesized(self):
        """A declared dependency lacking its own manifest is synthesized from its
        label: it resolves to a node (package dir from the label's package
        path), and the recording side effect writes to its package's message file."""
        with self._workspace() as ws:
            # a2 declares //pkg_x:phantom, which has no manifest of its own.
            ws.write_manifest(
                "pkg_a",
                "a2",
                "//pkg_a:a2",
                "prompt for a2",
                deps=["//pkg_x:phantom"],
            )
            (ws.root / "pkg_x").mkdir()  # the phantom's package exists on disk

            graph = self._build_graph(ws)

            self.assertEqual(
                graph.get_node_dependencies("//pkg_a:a2"), ["//pkg_x:phantom"]
            )
            # The phantom resolves to a node with a package dir from its label.
            self.assertEqual(
                graph.resolve_package_directory("//pkg_x:phantom"),
                str(ws.root / "pkg_x"),
            )
            # The recording side effect reached the phantom's message file.
            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_x:phantom"),
                ["//pkg_a:a2"],
            )

    def test_synthesis_handles_canonical_at_prefix_labels(self):
        """Manifest labels use Bazel's canonical @@// form; a synthesized
        dependency's package dir is derived from the label's package path."""
        with self._workspace() as ws:
            ws.write_manifest(
                "pkg_a",
                "a3",
                "@@//pkg_a:a3",
                "prompt for a3",
                deps=["@@//pkg_x:phantom"],
            )
            (ws.root / "pkg_x").mkdir()  # the phantom's package exists on disk

            graph = self._build_graph(ws)

            self.assertEqual(
                graph.get_node_dependencies("@@//pkg_a:a3"), ["@@//pkg_x:phantom"]
            )
            self.assertEqual(
                graph.resolve_package_directory("@@//pkg_x:phantom"),
                str(ws.root / "pkg_x"),
            )
            self.assertEqual(
                graph.get_known_reverse_dependencies("@@//pkg_x:phantom"),
                ["@@//pkg_a:a3"],
            )

    def test_verification_callback_runs_shell_command(self):
        """The manifest's verify shell command backs the verification callback."""
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            callback = graph.resolve_node_definition(
                "//pkg_a:a"
            ).sandbox_config.verification_callback
            self.assertIsNotNone(callback)
            if callback is not None:
                success, output = callback()
                self.assertTrue(success)
                self.assertEqual(output.strip(), "verification-output")

    def test_verification_callback_none_without_verify(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            callback = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.verification_callback
            self.assertIsNone(callback)


if __name__ == "__main__":
    unittest.main()
