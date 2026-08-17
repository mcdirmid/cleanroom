"""
Implementation LLS: bazel_graph_storage_impl
Provides the bazel_graph_storage implementation that fulfills the
bazel_graph_storage (and hence dag_storage) contract: Bazel-workspace-backed
storage with per-package message files.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
import os
from pathlib import Path

from .bazel_graph_storage import (
    BazelGraphStorage,
    GraphConfig,
    NodeDefinition,
    NodeId,
    PackageDirectory,
    GraphSource,
)
from .dag_storage import (
    NodeMessage,
    PendingMessages,
    NodeDependencies,
    KnownReverseDependencies,
)
from .sandbox import (
    SandboxConfig,
    VerificationCallback,
    FileMapping,
    ReadablePaths,
    WritablePaths,
    BlameTargets,
)

# The implementation is constructed with the interface's GraphConfig (see
# bazel_graph_storage-low.md); the Config alias names it per the implementation spec.
Config = GraphConfig

# The per-package data file (pinned by the implementation LLS): maps node IDs
# to entries holding the node's pending messages and known reverse dependencies.
HARNESS_FILE = ".bazelharness.json"


class BaseBazelGraphStorageImpl(BazelGraphStorage):
    """
    Implementation of the bazel_graph_storage interface.

    Resolves node labels to package directories, node definitions, and
    dependency edges from the configured graph source, and persists messages
    and known reverse dependencies in a per-package message file. Never invokes
    Bazel tooling during processing: `bazel query`, `cquery`, and aspects are at
    most offline extraction tools used outside the component's processing.
    """

    def __init__(self, config: GraphConfig) -> None:
        """
        Initialize the graph storage implementation.

        The config must provide at least one of:
        - graph_source: a precomputed graph artifact
        - workspace_root: a path to the Bazel workspace root

        The graph source is resolved by the concrete implementation.
        """
        self._config = config
        self._graph_source: GraphSource = self._resolve_graph_source()
        self._adjacency: Dict[NodeId, List[NodeId]] = self._build_adjacency()
        self._definitions: Dict[NodeId, NodeDefinition] = self._build_definitions()
        self._package_dirs: Dict[NodeId, PackageDirectory] = self._build_package_dirs()

    def _resolve_graph_source(self) -> GraphSource:
        """
        Resolve the graph source from config.

        At least one of graph_source or workspace_root must be provided.
        """
        if self._config.graph_source is not None:
            return self._config.graph_source
        if self._config.workspace_root is not None:
            return self._config.workspace_root
        raise ValueError(
            "GraphConfig must provide at least one of graph_source or workspace_root"
        )

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        """
        Build the dependency adjacency map from the graph source.

        Returns a mapping from each node to its direct dependencies.
        """
        raise NotImplementedError(
            "Subclasses must implement _build_adjacency"
        )

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        """
        Build the node definitions from the graph source.

        Returns a mapping from node_id to NodeDefinition.
        """
        raise NotImplementedError(
            "Subclasses must implement _build_definitions"
        )

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        """
        Build the package directory mapping from the graph source.

        Returns a mapping from node_id to its package directory
        (the directory containing its BUILD file).
        """
        raise NotImplementedError(
            "Subclasses must implement _build_package_dirs"
        )

    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition:
        """
        Return the agent prompt and sandbox configuration declared by a node's target.

        Operation Implemented: bazel_graph_storage.resolve_node_definition

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns a NodeDefinition containing the node's agent prompt
          and sandbox configuration as declared by the target

        Failure Handling:
        - Unknown nodes raise ValueError (a precondition violation; the
          implementation need not throw at all).
        """
        definition = self._definitions.get(node_id)
        if definition is None:
            raise ValueError(f"Unknown node: {node_id}")
        return definition

    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory:
        """
        Return the directory containing the node's BUILD file.

        Operation Implemented: bazel_graph_storage.resolve_package_directory

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns the package directory as the directory containing the node's BUILD file
        - Also the directory where the node's messages are stored

        Failure Handling:
        - Unknown nodes raise ValueError (a precondition violation; the
          implementation need not throw at all).
        """
        package_dir = self._package_dirs.get(node_id)
        if package_dir is None:
            raise ValueError(f"Unknown node: {node_id}")
        return package_dir

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        """
        Retrieve all pending messages for a given node.

        Operation Implemented: dag_storage.get_pending_messages

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns list of pending messages (empty if none)

        Failure Handling:
        - If node_id does not exist, behavior is undefined.
        """
        pkg_dir = self.resolve_package_directory(node_id)
        harness_file = os.path.join(pkg_dir, HARNESS_FILE)
        return self._read_messages(harness_file, node_id)

    def add_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        """
        Add messages to a node's pending set.

        Operation Implemented: dag_storage.add_messages

        Preconditions:
        - node_id is a valid Bazel target label
        - messages are valid strings

        Postconditions:
        - All messages are added atomically to the node's pending set

        Failure Handling:
        - If node_id does not exist, behavior is undefined.
        """
        pkg_dir = self.resolve_package_directory(node_id)
        harness_file = os.path.join(pkg_dir, HARNESS_FILE)
        self._add_messages(harness_file, node_id, messages)

    def delete_node_data(self, node_id: NodeId) -> None:
        """
        Delete a node's data: its pending messages and its known reverse dependencies.

        Operation Implemented: dag_storage.delete_node_data

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - The node's pending messages and known reverse dependencies are deleted atomically

        Failure Handling:
        - If node_id does not exist, behavior is undefined.
        """
        pkg_dir = self.resolve_package_directory(node_id)
        harness_file = os.path.join(pkg_dir, HARNESS_FILE)
        self._delete_node_data(harness_file, node_id)

    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies:
        """
        Retrieve the direct dependencies of a node.

        Operation Implemented: dag_storage.get_node_dependencies

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns the node's direct dependencies
        - As a side effect, records the node as a known reverse dependency of
          each provided dependency (each dependency's message-file entry gains
          the node among its known reverse dependencies)

        Failure Handling:
        - Unknown nodes raise ValueError (a precondition violation; the
          implementation need not throw at all).
        """
        deps = self._adjacency.get(node_id)
        if deps is None:
            raise ValueError(f"Unknown node: {node_id}")
        # Side effect per the dag_storage contract: record the node as a known
        # reverse dependency of each dependency it provides, at most once per
        # dependency (deduplicated). Every declared dependency resolves to a
        # package directory (dependencies lacking their own manifest are
        # synthesized from their label during manifest loading).
        for dep in deps:
            pkg_dir = self.resolve_package_directory(dep)
            harness_file = os.path.join(pkg_dir, HARNESS_FILE)
            self._add_reverse_dependency(harness_file, dep, node_id)
        return deps

    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies:
        """
        Retrieve the nodes recorded as depending on this node.

        Operation Implemented: dag_storage.get_known_reverse_dependencies

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns the node's known reverse dependencies exactly as recorded
          (empty if none recorded)

        Failure Handling:
        - If node_id does not exist, behavior is undefined.
        """
        pkg_dir = self.resolve_package_directory(node_id)
        harness_file = os.path.join(pkg_dir, HARNESS_FILE)
        return self._read_reverse_dependencies(harness_file, node_id)

    def _read_file(self, path: str) -> Dict[str, Any]:
        """Read the messages file and return the node->entry mapping."""
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)

    def _write_file(self, path: str, data: Dict[str, Any]) -> None:
        """Write the messages file atomically."""
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)

    def _entry(self, data: Dict[str, Any], node_id: NodeId) -> Dict[str, Any]:
        """Return the node's entry (messages + known reverse dependencies), creating it if absent."""
        entry = data.get(node_id)
        if entry is None:
            entry = {"messages": [], "reverse_dependencies": []}
            data[node_id] = entry
        return entry

    def _read_messages(self, harness_file: str, node_id: NodeId) -> PendingMessages:
        """Read pending messages for a node from the file."""
        data = self._read_file(harness_file)
        entry = data.get(node_id)
        if entry is None:
            return []
        return list(entry.get("messages", []))

    def _add_messages(self, harness_file: str, node_id: NodeId, messages: List[NodeMessage]) -> None:
        """Add messages to a node's pending set and write atomically."""
        data = self._read_file(harness_file)
        entry = self._entry(data, node_id)
        entry["messages"].extend(messages)
        self._write_file(harness_file, data)

    def _delete_node_data(self, harness_file: str, node_id: NodeId) -> None:
        """Delete all pending messages for a node and write atomically."""
        data = self._read_file(harness_file)
        if node_id in data:
            del data[node_id]
        self._write_file(harness_file, data)

    def _read_reverse_dependencies(self, harness_file: str, node_id: NodeId) -> KnownReverseDependencies:
        """Read the node's known reverse dependencies from the file."""
        data = self._read_file(harness_file)
        entry = data.get(node_id)
        if entry is None:
            return []
        return list(entry.get("reverse_dependencies", []))

    def _add_reverse_dependency(self, harness_file: str, node_id: NodeId, dep: NodeId) -> None:
        """Record a node as a known reverse dependency of node_id and write atomically."""
        data = self._read_file(harness_file)
        entry = self._entry(data, node_id)
        reverse_deps = entry["reverse_dependencies"]
        if dep not in reverse_deps:
            reverse_deps.append(dep)
        self._write_file(harness_file, data)


def _build_verify_callback(verify_cmd: str) -> Optional[VerificationCallback]:
    """Build a verification callback from a shell command string."""
    if not verify_cmd:
        return None
    def _callback() -> str:
        result = os.popen(verify_cmd).read()
        return result
    return _callback


def _build_sandbox_config(
    manifest: Dict[str, object],  # pyright: ignore[reportArgumentType]
    file_mappings: FileMapping,  # pyright: ignore[reportArgumentType]
    readable_paths: List[str],  # pyright: ignore[reportArgumentType]
    writable_paths: List[str],  # pyright: ignore[reportArgumentType]
) -> SandboxConfig:  # pyright: ignore[reportReturnType]
    """Build a SandboxConfig from a manifest dict. (pyright: ignore[reportArgumentType])"""
    return SandboxConfig(
        file_mappings=file_mappings,
        readable_paths=readable_paths,
        writable_paths=writable_paths,
        blame_targets=list(manifest.get("deps", [])) + list(manifest.get("silent_deps", [])),  # pyright: ignore[reportArgumentType]
        read_size_limit=8096,
        search_result_limit=10,
        verification_callback=_build_verify_callback(
            str(manifest.get("verify") or "")  # pyright: ignore[reportArgumentType]
        ),
    )


def _package_dir_from_label(label: str, real_root: Path) -> PackageDirectory:
    """Derive the package directory for a canonical Bazel label (//pkg/path:name or @@//pkg/path:name)."""
    if label.startswith("@@"):
        label = label[2:]
    if label.startswith("//"):
        package = label[2:].split(":", 1)[0]
    else:
        package = ""
    return str(real_root / package)


def _synthesized_manifest(label: str) -> Dict[str, Any]:
    """A minimal manifest for a declared dependency lacking its own manifest."""
    return {
        "label": label,
        "name": label.split(":")[-1],
        "prompt": "",
        "tools": [],
        "deps": [],
        "silent_deps": [],
        "srcs": [],
        "silent_srcs": [],
        "verify": None,
        "dependency_paths": [],
    }


def _synthesized_definition() -> NodeDefinition:
    """A minimal node definition (empty prompt, empty sandbox configuration)."""
    return NodeDefinition(
        prompt="",
        sandbox_config=SandboxConfig(
            file_mappings={},
            readable_paths=[],
            writable_paths=[],
            blame_targets=[],
            read_size_limit=8096,
            search_result_limit=10,
            verification_callback=None,
        ),
    )


class BazelGraphStorageFileImpl(BaseBazelGraphStorageImpl):
    """
    File-based implementation that reads node manifests from the workspace.

    Loads node definitions and dependencies from JSON manifest files
    produced by update_with_ai rules. No Bazel tooling is invoked at runtime.
    """

    def __init__(self, config: GraphConfig) -> None:
        """
        Initialize from a workspace root.

        The config must provide workspace_root pointing to the Bazel workspace.
        """
        if config.workspace_root is None:
            raise ValueError("BazelGraphStorageFileImpl requires workspace_root in config")
        self._workspace_root = Path(config.workspace_root)
        # Under `bazel run` the process CWD and the manifest runfiles tree live in
        # the output base, not the real workspace. Bazel exposes the real source
        # root via BUILD_WORKSPACE_DIRECTORY; use it so package directories (and
        # therefore sandbox file I/O and message storage) resolve to the source
        # tree instead of the ephemeral runfiles tree.
        self._real_root = Path(
            os.environ.get("BUILD_WORKSPACE_DIRECTORY") or self._workspace_root
        )
        self._definitions: Dict[NodeId, NodeDefinition] = {}
        self._adjacency: Dict[NodeId, List[NodeId]] = {}
        self._package_dirs: Dict[NodeId, PackageDirectory] = {}
        self._load_manifests()
        # Complete the base-class construction pipeline: resolve the graph
        # source and populate the maps through the _build_* overrides (which
        # return the manifest-derived data loaded above).
        super().__init__(config)

    def _load_manifests(self) -> None:
        """
        Load all manifest files from the workspace root.

        Two passes: first read every manifest (so a node's dependencies and
        their srcs are all resolvable), then build definitions and sandbox
        configs. A node can read the srcs of its dependencies by bare name;
        the sandbox maps each name to the dependency's real package directory.
        """
        manifests = list(self._workspace_root.rglob("*_manifest.json"))

        raw: Dict[NodeId, Any] = {}
        pkg_dirs: Dict[NodeId, PackageDirectory] = {}
        for json_path in manifests:
            with open(json_path) as f:
                manifest = json.load(f)
            node_id: NodeId = manifest["label"]

            # The manifest lives in the (possibly runfiles-mirrored) workspace
            # root; map its location back onto the real source tree so package
            # directories and sandbox file I/O point at real source paths.
            rel_pkg = json_path.parent.relative_to(self._workspace_root)
            pkg_dirs[node_id] = str(self._real_root / rel_pkg)
            raw[node_id] = manifest

        for node_id, manifest in raw.items():
            # Collect dependency srcs (bare names) -> their package directories.
            dep_srcs: Dict[str, str] = {}
            for dep in list(manifest.get("deps", [])) + list(manifest.get("silent_deps", [])):
                dep_manifest = raw.get(dep)
                if dep_manifest is None:
                    continue  # dep manifest not in this graph's runfiles
                dep_pkg = pkg_dirs[dep]
                for src in dep_manifest.get("srcs", []):
                    s = str(src)
                    dep_srcs.setdefault(s, dep_pkg)

            own_srcs: List[str] = [str(s) for s in manifest.get("srcs", [])]
            own_silent_srcs: List[str] = [str(s) for s in manifest.get("silent_srcs", [])]
            pkg_dir = pkg_dirs[node_id]

            # Dependency file mappings first; the node's own files win on
            # name collisions.
            file_mappings: FileMapping = {
                s: os.path.join(d, s) for s, d in dep_srcs.items()
            }
            for s in own_srcs + own_silent_srcs:
                file_mappings[s] = os.path.join(pkg_dir, s)

            readable_paths = own_srcs + [s for s in dep_srcs if s not in own_srcs]
            writable_paths = own_srcs + own_silent_srcs

            self._definitions[node_id] = NodeDefinition(
                prompt=manifest["prompt"],
                sandbox_config=_build_sandbox_config(
                    manifest,
                    file_mappings=file_mappings,
                    readable_paths=readable_paths,
                    writable_paths=writable_paths,
                ),
            )

            # Build adjacency: deps and silent_deps are the node's dependencies
            deps: List[NodeId] = list(manifest.get("deps", []))
            silent_deps: List[NodeId] = list(manifest.get("silent_deps", []))
            all_deps: List[NodeId] = deps + silent_deps
            self._adjacency[node_id] = all_deps

            # Package directory = parent of manifest file (in the real source tree)
            self._package_dirs[node_id] = pkg_dir

        # Synthesize manifests for declared dependencies that lack their own
        # manifest: every declared dependency resolves to a node (per the
        # bazel_graph_storage_impl contract). The dependency's package
        # directory is derived from its label.
        declared_deps: List[NodeId] = []
        for manifest in raw.values():
            declared_deps.extend(manifest.get("deps", []))
            declared_deps.extend(manifest.get("silent_deps", []))
        for dep in declared_deps:
            if dep in raw:
                continue
            if dep in self._definitions:
                continue  # already synthesized
            raw[dep] = _synthesized_manifest(dep)
            self._definitions[dep] = _synthesized_definition()
            self._adjacency[dep] = []
            self._package_dirs[dep] = _package_dir_from_label(dep, self._real_root)

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        """Override: adjacency is pre-built from manifests."""
        return self._adjacency

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        """Override: definitions are pre-built from manifests."""
        return self._definitions

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        """Override: package dirs are pre-built from manifests."""
        return self._package_dirs
