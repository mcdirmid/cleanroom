from typing import Self
from framework import operation, override, singleton_type
import bazel_target
import bazel_target_labels_ext
import dag_storage
import file_paths


@singleton_type('system')
class BazelTarget(bazel_target.BazelTarget):
    """Implements bazel target normalizing labels and extracting directories.

    GROUNDING_ARGUMENT:
    - As a system singleton, BazelTarget provides deterministic target label normalization and package directory derivation without external service dependencies.
    """

    @operation
    @override
    def normalize(self, raw_label: str) -> dag_storage.DagNode:
        """Normalizes raw target labels by stripping repo qualifiers and expanding targets.

        REQUIREMENTS:
        - The bazel target normalizes raw target labels by stripping repository qualifiers and expanding omitted target names.

        GROUNDING_IMPLEMENTS:
        - action("normalize", dag_storage.DagNode): Normalizes target label.
        """
        ...

    @operation
    @override
    def extract_directory(self, node: dag_storage.DagNode) -> bazel_target.NodeDirectory:
        """Derives node directories relative to workspace root.

        REQUIREMENTS:
        - The bazel target derives node directories from normalized nodes relative to a workspace root.

        GROUNDING_IMPLEMENTS:
        - action("extract_directory", bazel_target.NodeDirectory): Derives package directory.
        """
        ...
