<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 70797961975b
-->

# uv_target interface component

imports: dag_storage, file_paths

## Purpose

The uv_target interface component normalizes target identifier strings into canonical graph nodes and determines package filesystem directories.

Multi-step workflows require deterministic node addressing and durable state storage within project package structures. Target specifications arrive from command-line arguments, dependency manifests, and directory layouts in various string forms. The uv_target interface component defines operations to convert arbitrary target identifier strings into canonical node references in graph storage and resolve the workspace package directories that contain them.

**Out of scope:** The uv_target interface component does not inspect disk files, parse build target manifests, or execute topological cleaning; these are handled by other components.

## Types and Behavior

A *node directory* is a workspace path addressing the workspace package directory of a node.

A system's *uv target* can *normalize* an arbitrary target identifier string into a canonical node and *extract* a node directory from a node.
