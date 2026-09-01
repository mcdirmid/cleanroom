"""Implementation of BazelNodeIdUtils."""

from .dag_storage import NodeId
from .node_id_utils import NodeDirectory, RawIdentifier, ContextIdentifier, WorkspaceRootPath
from .bazel_node_id_utils import BazelNodeIdUtils
from .bazel_target_labels_ext import canonicalize_label, extract_package_directory


class BazelNodeIdUtilsImpl(BazelNodeIdUtils):
    """Implementation of Bazel-specific node identifier utilities."""

    def __init__(self) -> None:
        pass

    def canonicalize_node_id(
        self, raw_id: RawIdentifier, current_context: ContextIdentifier
    ) -> NodeId:
        return canonicalize_label(raw_id, current_context)

    def extract_node_directory(
        self, node: NodeId, workspace_root: WorkspaceRootPath
    ) -> NodeDirectory:
        return extract_package_directory(node, workspace_root)
