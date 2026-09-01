# bazel_node_id_utils_impl

imports: dag_storage, node_id_utils, bazel_node_id_utils, bazel_target_labels_ext
types from dag_storage: node
types from node_id_utils: node identifier utility, node directory
types from bazel_node_id_utils: bazel node identifier utility
types from bazel_target_labels_ext: raw target label
implements: bazel node identifier utility

## Behavior

- A *bazel node identifier utility* normalizes *raw target labels* by stripping repository qualifiers and expanding omitted target names.
- A *bazel node identifier utility* derives *node directories* from normalized *nodes* relative to a workspace root.
