import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set, cast
from update_with_ai.parts.agent.lib import agent_storage
from . import bazel_manifest_loader
from . import bazel_target
from update_with_ai.parts.dag.lib import dag_storage
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class BazelManifestLoader(bazel_manifest_loader.BazelManifestLoader, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._manifests: Dict[dag_storage.Node, bazel_manifest_loader.Manifest] = {}

    def get_manifest(
        self, node: dag_storage.Node
    ) -> Optional[bazel_manifest_loader.Manifest]:
        # Check in-memory cache first
        if node in self._manifests:
            return self._manifests[node]

        # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
        # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
        node_util = get_singleton(bazel_target.BazelTarget)
        pkg_dir = node_util.extract_directory(node)
        target_name = (
            node.address.split(":")[-1]
            if ":" in node.address
            else os.path.basename(node.address)
        )
        manifest_filename = f"{target_name}_manifest.json"

        candidates = [
            os.path.join(pkg_dir.path, ".manifest.json"),
            os.path.join(pkg_dir.path, manifest_filename),
            os.path.join("bazel-bin", pkg_dir.path, manifest_filename),
            manifest_filename,
        ]
        for base in (
            os.environ.get("RUNFILES_DIR", ""),
            os.environ.get("BAZEL_RUNFILES", ""),
        ):
            if base:
                candidates.extend(
                    [
                        os.path.join(base, manifest_filename),
                        os.path.join(base, "_main", manifest_filename),
                        os.path.join(base, "_main", pkg_dir.path, manifest_filename),
                        os.path.join(base, pkg_dir.path, manifest_filename),
                    ]
                )

        for path in candidates:
            if os.path.exists(path) and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        m = bazel_manifest_loader.Manifest(f.read())
                        self._manifests[node] = m
                        return m
                except (OSError, UnicodeDecodeError):
                    pass

        return None

    def load_manifest(
        self,
        content: bazel_manifest_loader.Manifest,
        storage: agent_storage.AgentStorage,
    ) -> Sequence[agent_storage.NodeDefinition]:
        # Requirement: A manifest loader parses JSON manifests using the filesystem into json manifest records.
        data = json.loads(str(content))
        node_util = get_singleton(bazel_target.BazelTarget)
        results: List[agent_storage.NodeDefinition] = []

        targets = data.get("targets", [data]) if isinstance(data, dict) else []
        for t in targets:
            label = t.get("label", "")
            # Requirement: A manifest loader normalizes node references into canonical nodes using node identifier utilities.
            node = node_util.normalize(label)
            # Cache the manifest for this node
            self._manifests[node] = bazel_manifest_loader.Manifest(
                json.dumps(t) if "targets" in data else str(content)
            )

            prompt = agent_storage.TaskPrompt(t.get("prompt", t.get("task_prompt", "")))
            defn = agent_storage.NodeDefinition(node=node, task_prompt=prompt)
            results.append(defn)

            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the agent storage.
            storage_any = cast(Any, storage)
            if hasattr(storage_any, "_definitions"):
                storage_any._definitions[node] = defn

            src = t.get("src")
            if src and hasattr(storage_any, "_source_files"):
                pkg_path = node_util.extract_directory(node).path
                norm_rel = os.path.normpath(os.path.join(pkg_path, src))
                storage_any._source_files[node] = norm_rel

            # Requirement: A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
            # Requirement: [BazelManifestLoader] A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
            deps: Set[dag_storage.Dependency] = set()
            for dep_label in t.get("deps", []):
                dep_node = node_util.normalize(dep_label)
                deps.add(dag_storage.Dependency(node=dep_node, is_silent=False))
            for dep_label in t.get("silent_deps", []):
                dep_node = node_util.normalize(dep_label)
                deps.add(dag_storage.Dependency(node=dep_node, is_silent=True))

            if hasattr(storage_any, "_dependencies"):
                storage_any._dependencies[node] = deps

        return results


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelManifestLoader,
        keys=[BazelManifestLoader, bazel_manifest_loader.BazelManifestLoader],
        tier="system",
    )
