from typing import Optional
from . import bazel_node_id_utils
from . import dag_storage
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry

class BazelNodeIdentifierUtility(bazel_node_id_utils.BazelNodeIdentifierUtility, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def normalize(self, raw_label: str) -> dag_storage.Node:
        # Requirement: Normalize raw target labels by stripping repository qualifiers and expanding omitted target names
        label = raw_label.strip()
        if "//" in label:
            label = "//" + label.split("//", 1)[1]
        else:
            label = f"//{label.lstrip('/')}"

        if ":" not in label:
            parts = label[2:].split("/")
            target_name = parts[-1] if parts and parts[-1] else ""
            label = f"{label}:{target_name}"

        return dag_storage.Node(address=label)

    def extract_directory(self, node: dag_storage.Node) -> bazel_node_id_utils.NodeDirectory:
        # Requirement: Derive node directories from normalized nodes relative to workspace root
        package_part = node.address[2:].split(":")[0]
        return bazel_node_id_utils.NodeDirectory(path=package_part)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelNodeIdentifierUtility,
        keys=[BazelNodeIdentifierUtility, bazel_node_id_utils.BazelNodeIdentifierUtility],
        tier="system",
    )
