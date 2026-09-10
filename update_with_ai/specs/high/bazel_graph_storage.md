# bazel_graph_storage interface component

imports: dag_storage, bazel_node_id_utils

## Purpose

The bazel_graph_storage interface component stores workspace target graph relationships, node definitions, pending messages, and reverse dependencies across package directories.

Task execution across structured projects requires maintaining target dependency relationships alongside durable inter-node messages. The bazel_graph_storage interface component preserves propagating and non-propagating graph relationships, task prompts, and node definitions populated from workspace target manifests, while persisting pending messages and reverse dependencies in per-package files using node directories resolved by Bazel node identifier utilities.

**Out of scope:** The bazel_graph_storage interface component does not orchestrate agent turns, parse JSON manifest syntax, or execute filesystem edits; these are handled by other components.

## Types and Behavior

A *task prompt* is an instruction describing the work required to clean a node.

A *node definition* is metadata describing task prompts for a node.

The *bazel graph storage* is a system service that is a dag storage backed by workspace build target manifests.

The bazel graph storage:

- Maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.

- Provides task prompts and node definitions for declared nodes.

- Marks dependent nodes dirty when propagating dependencies change.

- Reads and writes pending messages and reverse dependencies for nodes in node directories resolved by the bazel node identifier utility.

- Creates missing package message files on write and treats absent files as empty.

- Preserves existing records on failure when modifying messages or reverse dependencies.
