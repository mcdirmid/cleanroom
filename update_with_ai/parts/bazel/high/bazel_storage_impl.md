<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: ed3e42e6c9d8
-->

# bazel_storage_impl implementation component

imports: bazel_target, file_paths, src_metadata_ext
implements: agent_storage, dag_storage

## Purpose

The bazel_storage_impl implementation component realizes in-memory graph indexing, in-band source file metadata persistence, dynamic forward dirty node evaluation, and silent dependency filtering for Bazel targets.

Coordinating multi-node builds requires fast in-memory access to target metadata alongside durable on-disk persistence of inter-node communication records. Storing inter-node communication records in sidecar package files causes state desynchronization, ghost records, and merge conflicts across branches. The bazel_storage_impl implementation component resolves declared source files against the workspace root, extracts and updates in-band comment headers using src_metadata_ext, evaluates dirty status dynamically from forward dependency timestamps and unacted feedback, and filters silent dependencies from dirty propagation.

**Out of scope:** The bazel_storage_impl implementation component does not deserialize JSON manifests, drive agent loops, or execute verification commands; these are handled by other components.

## Types and Behavior

The agent storage records declared source file paths, forward dependencies, silent source file paths, and feedback dependencies mapped to nodes in dag storage, maintaining node definitions and task prompts.

The agent storage resolves each node's declared source file against the workspace root, reading and writing in-band metadata comment blocks containing last cleaned timestamps, last changed timestamps, change descriptions, and unacted feedback entries.

Evaluating whether a node is dirty in dag storage inspects the node's source file and in-band metadata.

A node evaluates as dirty when:

- Its declared source file is missing from the workspace root, synthesizing a change message to implement the source file.

- Its source file metadata is missing, unparseable, or its last cleaned timestamp is missing.

- Its source file metadata contains unacted feedback entries, synthesizing feedback messages for the unacted entries.

- Any non-silent forward dependency has a last changed timestamp strictly newer than the node's last cleaned timestamp, synthesizing a change message describing the dependency update.

Marking a node clean clears messages for the node and updates in-band metadata with a clean timestamp. When an optional change description is provided for a node with a source artifact, marking the node clean updates its last changed timestamp and change description in its in-band metadata, and clears unacted feedback.

Deleting the last cleaned timestamp from a node's source file metadata header marks the node dirty without modifying its change description or last changed timestamp.

Evaluating whether an auditor role node is dirty in dag storage inspects the in-band metadata of its verified feedback target files. Querying feedback dependencies or evaluating dirty status for an auditor role node without configured feedback dependencies fails fast with an error.

An auditor role node evaluates as dirty when:

- Any verified feedback target file is missing from the workspace root, or any verified feedback target node evaluates as dirty.

- Any verified feedback target file metadata is missing, unparseable, or missing the auditor role audit timestamp.

- Any verified feedback target file has a last changed timestamp strictly newer than its audit timestamp for that auditor role.

- Any non-silent contract dependency has a last changed timestamp strictly newer than any verified feedback target file audit timestamp for that auditor role.

Marking an auditor role node clean records the current timestamp as the auditor role audit timestamp on each verified feedback target file in-band metadata header without modifying the target file last changed timestamp.

Deleting the last cleaned timestamp from an auditor role node removes the auditor role audit timestamp from each verified feedback target file in-band metadata header.

Materializing template for a node writes configured template content into its declared source file if the file is missing from the workspace root without overwriting existing files.

Recording a feedback message against a dependency target node updates the target node's source file in-band metadata header in-place, appending an unacted feedback entry carrying the current timestamp, blaming node address, and feedback explanation.
