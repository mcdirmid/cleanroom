# bazel_storage_impl implementation component

imports: bazel_target, update_with_ai_proto_ext, file_paths
implements: agent_storage, dag_storage

## Assumptions and Requirements

### Requirements

1. The agent storage maintains node definitions and task prompts mapped to nodes in dag storage.
2. The agent storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files.
3. All nodes located within the same package directory share a common package message file named `.update_with_ai.textproto`.
4. The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
5. Propagating dependencies exclude silent dependencies declared on a node.
6. A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.
7. Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
8. Clearing the dependents of a node empties all recorded dependents for that node.
9. Adding a message to a node records the message explaining why the node requires cleaning.
10. Clearing messages for a node removes all recorded messages explaining why it requires cleaning.

## Grounding Facts

### Knowledge Needed

- Package message file name (`.update_with_ai.textproto`).
- Package directory and workspace root paths.
- Protobuf schema from `update_with_ai_proto_ext`.
- Source file presence in workspace.
- Non-silent dependencies.

### Actions Needed

- Read and write protobuf text format message files.
- Evaluate node dirty status based on messages and source file presence.
- Register and clear node dependents.
- Add and clear node messages.
