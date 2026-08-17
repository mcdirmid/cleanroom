# lib/bazel_graph_impl.py
"""
Implementation LLS: bazel_graph_impl
Provides the bazel_graph implementation that fulfills the bazel_graph contract.
"""

from __future__ import annotations
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple
import json
import os
from pathlib import Path

from .bazel_graph import (
    BazelGraph,
    GraphConfig,
    NodeDefinition,
    NodeId,
    PackageDirectory,
    NodeSubgraph,
)
from .bazel_graph import GraphSource
from .sandbox import SandboxConfig, VerificationCallback, FileMapping, ReadablePaths, WritablePaths, BlameTargets

# The implementation is constructed with the interface's GraphConfig (see
# bazel_graph-low.md); the Config alias names it per the implementation spec.
Config = GraphConfig


class BazelGraphImpl(BazelGraph):
    """
    Implementation of the bazel_graph interface.

    Resolves node labels to package directories, node definitions, and
    dependency edges from the configured graph source. Never invokes Bazel
    tooling during processing: `bazel query`, `cquery`, and aspects are at
    most offline extraction tools used outside the component's processing.

    Subgraph enumeration is lazy: the implementation expands the transitive
    dependency closure from the root node on demand, rather than materializing
    the entire workspace graph.
    """

    def __init__(self, config: GraphConfig) -> None:
        """
        Initialize the graph implementation.

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

        Returns a mapping from each node to its direct dependencies,
        ordered in dependency-before-dependent order (topological order).
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

        Preconditions:
        - node_id is a valid Bazel target label
        - The node ID resolves to a target with a complete definition

        Postconditions:
        - Returns a NodeDefinition containing the node's agent prompt
          and sandbox configuration as declared by the target

        Failure Handling:
        - No failure conditions; all valid node IDs resolve to complete definitions.

        HLS Justification: "Query a node's definition (the agent prompt and sandbox configuration)."
        """
        definition = self._definitions.get(node_id)
        if definition is None:
            raise ValueError(f"Unknown node: {node_id}")
        return definition

    def resolve_node_dependencies(self, node_id: NodeId) -> List[NodeId]:
        """
        Return the direct dependencies of a node, ordered before the node in build order.

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns the node's direct dependency node IDs
        - Dependencies are ordered before the node (Bazel build order)

        Failure Handling:
        - No failure conditions; all valid node IDs have declared dependencies.
        - Unknown nodes raise ValueError (a precondition violation; the
          implementation need not throw at all).

        HLS Justification: "Query a node's direct dependencies."
        """
        deps = self._adjacency.get(node_id)
        if deps is None:
            raise ValueError(f"Unknown node: {node_id}")
        return deps

    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory:
        """
        Return the directory containing the node's BUILD file.

        Preconditions:
        - node_id is a valid Bazel target label

        Postconditions:
        - Returns the package directory as the directory containing the node's BUILD file
        - Also the directory where the node's messages are stored

        Failure Handling:
        - No failure conditions; all valid node IDs have a package directory.

        HLS Justification: "Query a node's package directory."
        """
        package_dir = self._package_dirs.get(node_id)
        if package_dir is None:
            raise ValueError(f"Unknown node: {node_id}")
        return package_dir

    def enumerate_subgraph(self, node_id: NodeId) -> NodeSubgraph:
        """
        Enumerate the subgraph rooted at the given node in topological order.
        Uses the adjacency map (populated by _build_adjacency in subclasses).
        """
        reachable: set[NodeId] = set()  # pyright: ignore[reportArgumentType]
        stack: list[NodeId] = [node_id]  # pyright: ignore[reportArgumentType]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for dep in self._adjacency.get(current, []):
                if dep not in reachable:
                    stack.append(dep)

        # Topological sort using Kahn's algorithm (pyright: ignore[reportArgumentType])
        in_degree: dict[NodeId, int] = {}  # pyright: ignore[reportArgumentType]
        for n in reachable:  # pyright: ignore[reportArgumentType]
            in_degree[n] = 0
        for n in reachable:  # pyright: ignore[reportArgumentType]
            for dep in self._adjacency.get(n, []):  # pyright: ignore[reportArgumentType]
                if dep in reachable:
                    in_degree[n] += 1

        queue: list[NodeId] = sorted(n for n in reachable if in_degree[n] == 0)  # pyright: ignore[reportArgumentType]
        result: list[NodeId] = []  # pyright: ignore[reportArgumentType]
        while queue:
            node = queue.pop(0)
            result.append(node)
            for other in reachable:
                if node in self._adjacency.get(other, []):
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)
            queue.sort()

        return result

    def items(self) -> List[Tuple[NodeId, List[NodeId]]]:
        """Return the adjacency map as a list of (node, deps) pairs. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement items")

    def __iter__(self) -> Iterator[NodeId]:
        """Iterate over node IDs. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement __iter__")

    def __getitem__(self, node_id: NodeId) -> List[NodeId]:
        """Return the direct dependencies of a node. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement __getitem__")


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


class BazMentalGraphFileImpl(BazelGraphImpl):
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
            raise ValueError("BazMentalGraphFileImpl requires workspace_root in config")
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

    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition:
        """Return the agent prompt and sandbox configuration declared by a node."""
        definition = self._definitions.get(node_id)
        if definition is None:
            raise ValueError(f"Unknown node: {node_id}")
        return definition

    def resolve_node_dependencies(self, node_id: NodeId) -> List[NodeId]:
        """Return the direct dependencies of a node."""
        deps = self._adjacency.get(node_id)
        if deps is None:
            raise ValueError(f"Unknown node: {node_id}")
        return deps

    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory:
        """Return the directory containing the node's BUILD file."""
        package_dir = self._package_dirs.get(node_id)
        if package_dir is None:
            raise ValueError(f"Unknown node: {node_id}")
        return package_dir

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        """Override: adjacency is pre-built from manifests."""
        return self._adjacency

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        """Override: definitions are pre-built from manifests."""
        return self._definitions

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        """Override: package dirs are pre-built from manifests."""
        return self._package_dirs

    def enumerate_subgraph(self, node_id: NodeId) -> NodeSubgraph:
        """
        Enumerate the subgraph rooted at the given node in topological order.

        Uses the pre-built adjacency map (populated from manifests during init).
        """
        # Collect all reachable nodes via BFS/DFS
        reachable: Set[NodeId] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for dep in self._adjacency.get(current, []):
                if dep not in reachable:
                    stack.append(dep)

        # Topological sort: dependencies before dependents
        # Using Kahn's algorithm on the induced subgraph
        in_degree: Dict[NodeId, int] = {n: 0 for n in reachable}
        for n in reachable:
            for dep in self._adjacency.get(n, []):
                if dep in reachable:
                    in_degree[n] += 1

        # Nodes with in-degree 0 in the induced subgraph are those with
        # no dependencies within the subgraph (leaves of the dependency tree)
        queue: List[NodeId] = [n for n in reachable if in_degree[n] == 0]
        queue.sort()

        result: List[NodeId] = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for other in reachable:
                if node in self._adjacency.get(other, []):
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)
            queue.sort()

        return result

    def items(self) -> List[Tuple[NodeId, List[NodeId]]]:
        """Return the adjacency map as an iterable of (node, deps) pairs."""
        return list(self._adjacency.items())

    def __iter__(self):
        """Iterate over node IDs (keys of the adjacency map)."""
        return iter(self._adjacency.keys())

    def __getitem__(self, node_id: NodeId) -> List[NodeId]:
        """Return the direct dependencies of a node."""
        return self._adjacency.get(node_id, [])
