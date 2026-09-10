from typing import Optional
from . import bazel_node_id_utils
from . import dag_storage
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry

class BazelNodeIdentifierUtility(bazel_node_id_utils.BazelNodeIdentifierUtility, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def normalize(self, raw_label: str) -> dag_storage.Node:
        # Requirement: The bazel node identifier utility normalizes raw target labels by stripping repository qualifiers and expanding omitted target names.
        # Requirement: [BazelNodeIdentifierUtility] The bazel node identifier utility normalizes an arbitrary target identifier string into a canonical node.
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
        # Requirement: The bazel node identifier utility derives node directories from normalized nodes relative to a workspace root.
        # Requirement: [BazelNodeIdentifierUtility] The bazel node identifier utility extracts a node directory from a node.
        package_part = node.address[2:].split(":")[0]
        obj = object.__new__(bazel_node_id_utils.NodeDirectory)
        object.__setattr__(obj, "path", package_part)
        return obj

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelNodeIdentifierUtility,
        keys=[BazelNodeIdentifierUtility, bazel_node_id_utils.BazelNodeIdentifierUtility],
        tier="system",
    )
