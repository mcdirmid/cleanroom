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

HARNESS_FILE = ".bazelharness.json"


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
    ) -> None:
        self._adjacency = adjacency
        self._definitions = definitions or {}
        self._package_dirs = package_dirs or {}
        super().__init__(GraphConfig(graph_source="mock-graph-source"))

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        return self._adjacency

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
    reverse dependency of each dependency (at most once); recordings persist."""

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
        """LLS: a missing .bazelharness.json reads as empty and is not created."""
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

    def test_harness_file_is_bazelharness_json_in_package_dir(self):
        """LLS: a single JSON file named .bazelharness.json in the node.s package directory."""
        self.graph.add_messages("node_a", ["msg"])

        messages_file = self.harness_file("node_a")
        self.assertEqual(os.path.dirname(messages_file), self.pkg_a)
        self.assertEqual(os.path.basename(messages_file), HARNESS_FILE)
        self.assertTrue(os.path.isfile(messages_file))

    def test_single_messages_file_per_package_directory(self):
        """LLS: one .bazelharness.json per package directory holds all nodes in it."""
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
        """LLS: each package directory holds its own .bazelharness.json."""
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
        """LLS: writes go to a temporary file, then atomically replaced onto .bazelharness.json."""
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
                 srcs=["b1.txt", "shared.txt"], silent_srcs=["b_priv.txt"]
      //pkg_c:c  srcs=["shared.txt"]
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
        )
        self.write_manifest(
            "pkg_c", "c", "//pkg_c:c", "prompt for c", srcs=["shared.txt"]
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
            # b's readable: own srcs (b1, shared) + a's srcs (a1). c's
            # "shared.txt" collides with b's own src and is not duplicated.
            self.assertCountEqual(
                graph.resolve_node_definition("//pkg_b:b").sandbox_config.readable_paths,
                ["b1.txt", "shared.txt", "a1.txt"],
            )
            # a's readable: own srcs (a1) + c's srcs (shared).
            self.assertCountEqual(
                graph.resolve_node_definition("//pkg_a:a").sandbox_config.readable_paths,
                ["a1.txt", "shared.txt"],
            )

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

    def test_blame_targets_are_deps_plus_silent_deps(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            self.assertEqual(
                graph.resolve_node_definition("//pkg_b:b").sandbox_config.blame_targets,
                ["//pkg_a:a", "//pkg_c:c"],
            )
            self.assertEqual(
                graph.resolve_node_definition("//pkg_a:a").sandbox_config.blame_targets,
                ["//pkg_c:c"],
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

    def test_get_node_dependencies_records_reverse_dependencies(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            graph.get_node_dependencies("//pkg_b:b")

            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_a:a"), ["//pkg_b:b"]
            )
            self.assertEqual(
                graph.get_known_reverse_dependencies("//pkg_c:c"), ["//pkg_b:b"]
            )
            self.assertEqual(graph.get_known_reverse_dependencies("//pkg_b:b"), [])

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
                self.assertEqual(callback().strip(), "verification-output")

    def test_verification_callback_none_without_verify(self):
        with self._workspace() as ws:
            graph = self._build_graph(ws)
            callback = graph.resolve_node_definition(
                "//pkg_b:b"
            ).sandbox_config.verification_callback
            self.assertIsNone(callback)


if __name__ == "__main__":
    unittest.main()
