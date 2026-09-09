# bazel_node_id_utils interface component

imports: dag_storage, file_alias

## Purpose

The bazel_node_id_utils interface component normalizes Bazel target labels into canonical graph nodes and determines package filesystem directories.

Multi-step workflows require deterministic node addressing and durable state storage within project package structures. The bazel_node_id_utils interface component defines operations to convert arbitrary Bazel target identifier strings into canonical node references in dag storage and resolve the workspace package directories that contain them.

**Out of scope:** The bazel_node_id_utils interface component does not inspect disk files, parse build target manifests, or execute topological cleaning; these are handled by other components.

## Types and Behavior

A *node directory* is a directory path from file alias addressing the workspace package directory of a node from dag storage.

The *bazel node identifier utility* is a *system* service that normalizes Bazel target labels and resolves package locations. The bazel node identifier utility:

- *Normalizes* an arbitrary Bazel target identifier string into a canonical node in dag storage.

- *Extracts* a node directory from a node.
