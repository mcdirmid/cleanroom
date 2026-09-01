# bazel_node_id_utils

imports: dag_storage, node_id_utils
types from dag_storage: node
types from node_id_utils: node identifier utility, node directory

## Purpose

Defines Bazel-specific node identifier utilities normalizing Bazel target labels and determining Bazel package directories.

Bazel targets use specialized label formats with repository qualifiers and package-relative targets. Bazel node identifier utilities specify the specialized normalization rules and directory mappings that bridge Bazel label syntax with opaque node identifiers.

## Types

- A *bazel node identifier utility* is a *node identifier utility* specialized for Bazel target labels and package structures

## Behavior

- A *bazel node identifier utility* normalizes Bazel target labels into canonical *nodes*.
- A *bazel node identifier utility* extracts *node directories* based on Bazel package path structure.
