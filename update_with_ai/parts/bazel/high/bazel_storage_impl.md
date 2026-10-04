# bazel_storage_impl implementation component

imports: bazel_target, file_paths, src_metadata_ext
implements: agent_storage, dag_storage

## Purpose

The bazel_storage_impl implementation component realizes in-memory graph indexing, in-band source file metadata persistence, dynamic forward dirty node evaluation, and silent dependency filtering for Bazel targets.

Coordinating multi-node builds requires fast in-memory access to target metadata alongside durable on-disk persistence of inter-node communication records. Storing inter-node communication records in sidecar package files causes state desynchronization, ghost records, and merge conflicts across branches. The bazel_storage_impl implementation component resolves declared source files against the workspace root, extracts and updates in-band comment headers using src_metadata_ext, evaluates dirty status dynamically from forward dependency timestamps and unacted feedback, and filters silent dependencies from dirty propagation.

**Out of scope:** The bazel_storage_impl implementation component does not deserialize JSON manifests, drive agent loops, or execute verification commands; these are handled by other components.

## Types and Behavior

The agent storage maintains node definitions, task prompts, declared source paths, and forward dependencies mapped to nodes in dag storage.

The agent storage resolves each node's declared source file against the workspace root, reading and writing in-band metadata comment blocks containing last cleaned timestamps, last changed timestamps, change descriptions, and unacted feedback entries.

Evaluating whether a node is dirty in dag storage inspects the node's source file and in-band metadata.

A node evaluates as dirty when:

- Its declared source file is missing from the workspace root, synthesizing a change message to implement the source file.

- Its source file metadata is missing, unparseable, or its last cleaned timestamp is missing.

- Its source file metadata contains unacted feedback entries, synthesizing feedback messages for the unacted entries.

- Any non-silent forward dependency has a last changed timestamp strictly newer than the node's last cleaned timestamp, synthesizing a change message describing the dependency update.

Marking a node clean updates the source file's in-band metadata header in-place, recording the current timestamp as the last cleaned timestamp, updating the last changed timestamp and change description when file modifications occurred, and removing all unacted feedback entries.

Deleting the last cleaned timestamp from a node's source file metadata header marks the node dirty without modifying its change description or last changed timestamp.

Recording a feedback message against a dependency target node updates the target node's source file in-band metadata header in-place, appending an unacted feedback entry carrying the current timestamp, blaming node address, and feedback explanation.
