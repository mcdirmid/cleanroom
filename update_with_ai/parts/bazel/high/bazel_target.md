<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T05:17:47Z
LAST_CHANGED: 2026-10-05T05:17:47Z
CHANGE: Remove code-level constructor constraint and introduce callable operations in infinitive form
CODE_HASH: b0424439f038
-->

# bazel_target interface component

imports: dag_storage, file_paths

## Purpose

The bazel_target interface component normalizes Bazel target labels into canonical graph nodes and determines package filesystem directories.

Multi-step workflows require deterministic node addressing and durable state storage within project package structures. The bazel_target interface component defines operations to convert arbitrary Bazel target identifier strings into canonical node references in dag storage and resolve the workspace package directories that contain them.

**Out of scope:** The bazel_target interface component does not inspect disk files, parse build target manifests, or execute topological cleaning; these are handled by other components.

## Types and Behavior

A *node directory* is a workspace path addressing the workspace package directory of a node.

A system's *bazel target* can *normalize* an arbitrary Bazel target identifier string into a canonical node and *extract* a node directory from a node.
