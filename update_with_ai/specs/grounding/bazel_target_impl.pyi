from framework import operation, override, singleton_type
import bazel_target
import bazel_target_labels_ext
import dag_storage
import file_paths

@singleton_type('system')
class BazelTarget(bazel_target.BazelTarget):
    """
PURPOSE:
Implements bazel target normalizing labels and extracting directories

GROUNDING_ARGUMENT:
- As a system singleton, BazelTarget provides deterministic target label normalization and package directory derivation without external service dependencies.
"""

    @operation
    @override
    def normalize(self, raw_label: str) -> dag_storage.Node:
        """
PURPOSE:
Normalizes raw target labels by stripping repo qualifiers and expanding targets

FRESH_REQUIREMENTS:
- The bazel target normalizes raw target labels by stripping repository qualifiers and expanding omitted target names.

INHERITED_REQUIREMENTS:
- [BazelTarget] The bazel target normalizes an arbitrary Bazel target identifier string into a canonical node.

GROUNDING_ARGUMENT:
- Receives raw_label directly as a parameter and applies string normalization to produce canonical dag_storage.Node records.
"""
        ...

    @operation
    @override
    def extract_directory(self, node: dag_storage.Node) -> bazel_target.NodeDirectory:
        """
PURPOSE:
Derives node directories relative to workspace root

FRESH_REQUIREMENTS:
- The bazel target derives node directories from normalized nodes relative to a workspace root.

INHERITED_REQUIREMENTS:
- [BazelTarget] The bazel target extracts a node directory from a node.

GROUNDING_ARGUMENT:
- Receives node directly as a parameter and extracts the relative package directory from its canonical label.
"""
        ...
