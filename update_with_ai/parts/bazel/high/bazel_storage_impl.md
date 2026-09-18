# bazel_storage_impl implementation component

imports: bazel_target, update_with_ai_proto_ext, file_paths
implements: agent_storage, dag_storage

## Purpose

The bazel_storage_impl implementation component realizes in-memory graph indexing, protobuf text format persistence, dirty node evaluation, and silent dependency filtering for Bazel targets.

Coordinating multi-node builds requires fast in-memory access to target metadata alongside durable on-disk persistence of inter-node communication records. The bazel_storage_impl implementation component maintains target configurations and graph edges in memory, serializes message queues and reverse dependencies into per-package `.update_with_ai.textproto` files, evaluates node dirty conditions from pending messages and source file presence, and filters silent dependencies from dirty propagation.

**Out of scope:** The bazel_storage_impl implementation component does not deserialize JSON files, drive agent loops, or execute verification commands; these are handled by other components.

## Types and Behavior

The agent storage maintains node definitions, task prompts, dependencies, and reverse dependencies mapped to nodes in dag storage.

A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.

The agent storage serializes pending messages and reverse dependencies for nodes into protobuf text format files using the proto package store.

All nodes located within the same package directory resolved by the bazel target share a common package message file named `.update_with_ai.textproto`. The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.

When evaluating dependency propagation in the agent storage, propagating dependencies exclude silent dependencies declared on a node.
