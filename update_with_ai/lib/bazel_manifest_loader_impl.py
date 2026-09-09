import json
import os
from typing import Any, List, Optional, Sequence, Set, cast
from . import bazel_graph_storage
from . import bazel_manifest_loader
from . import bazel_node_id_utils
from . import dag_storage
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class BazelManifestLoader(bazel_manifest_loader.BazelManifestLoader, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def get_manifest(self, node: dag_storage.Node) -> Optional[bazel_manifest_loader.Manifest]:
        # Requirement: Reads package manifest file from disk if present
        node_util = get_singleton(bazel_node_id_utils.BazelNodeIdentifierUtility)
        pkg_dir = node_util.extract_directory(node)
        manifest_path = os.path.join(pkg_dir.path, ".manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return bazel_manifest_loader.Manifest(f.read())
        return None

    def load_manifest(
        self, content: bazel_manifest_loader.Manifest, storage: bazel_graph_storage.BazelGraphStorage
    ) -> Sequence[bazel_graph_storage.NodeDefinition]:
        # Requirement: Deserializes target manifest JSON into structured definitions
        data = json.loads(str(content))
        node_util = get_singleton(bazel_node_id_utils.BazelNodeIdentifierUtility)
        results: List[bazel_graph_storage.NodeDefinition] = []

        targets = data.get("targets", [data]) if isinstance(data, dict) else []
        for t in targets:
            label = t.get("label", "")
            # Requirement: Normalizes target labels to canonical nodes
            node = node_util.normalize(label)
            prompt = bazel_graph_storage.TaskPrompt(t.get("task_prompt", t.get("prompt", "")))
            defn = bazel_graph_storage.NodeDefinition(node=node, task_prompt=prompt)
            results.append(defn)

            # Requirement: Stores node definition and task prompt in graph storage
            storage_any = cast(Any, storage)
            if hasattr(storage_any, "_definitions"):
                storage_any._definitions[node] = defn

            # Requirement: Resolves and records standard and silent dependencies
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
