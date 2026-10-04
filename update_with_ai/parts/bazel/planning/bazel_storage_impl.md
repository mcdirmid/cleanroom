# bazel_storage_impl implementation component

imports: bazel_target, update_with_ai_proto_ext, file_paths
implements: agent_storage, dag_storage

## Intent

Coordinating multi-node builds requires fast in-memory access to target metadata alongside durable on-disk persistence of inter-node communication records. The bazel_storage_impl implementation component maintains target configurations and graph edges in memory, serializes message queues and reverse dependencies into per-package `.update_with_ai.textproto` files, evaluates node dirty conditions from pending messages and source file presence, and filters silent dependencies from dirty propagation.

By storing message records in package-level textproto files, ignoring missing files on read, and isolating silent dependencies, the implementation ensures hermetic inter-task coordination across the workspace.

## Factored Contracts

### Contracts

- The agent storage maintains node definitions mapped to nodes in dag storage. [maintain_node_definitions]
- The agent storage maintains task prompts mapped to nodes in dag storage. [maintain_task_prompts]
- The agent storage maintains dependencies mapped to nodes in dag storage. [maintain_node_dependencies]
- The agent storage maintains reverse dependencies mapped to nodes in dag storage. [maintain_reverse_dependencies]
- A node in dag storage is dirty when it has messages explaining why it requires cleaning. [node_dirty_when_messages_present]
- A node in dag storage is dirty when its declared source file is missing from the workspace root. [node_dirty_when_source_missing]
- A node records a change message to implement the source file when its declared source file is missing. [record_change_message_when_source_missing]
- The agent storage serializes pending messages into protobuf text format files. [serialize_pending_messages_to_proto]
- The agent storage serializes reverse dependencies into protobuf text format files. [serialize_reverse_deps_to_proto]
- Nodes located within the same package directory share a package message file named ".update_with_ai.textproto". [share_package_message_file]
- The agent storage resolves package directories against the workspace root to read and write message files at their absolute path. [resolve_package_dir_for_message_file]
- The agent storage creates message files if missing on write. [create_message_file_if_missing]
- The agent storage ignores absent message files on read. [ignore_absent_message_files_on_read]
- Propagating dependencies exclude silent dependencies declared on a node when evaluating dependency propagation. [exclude_silent_dependencies_from_propagation]

## Woven Contracts

- The storage implementation maintains in-memory node definitions, task prompts, and graph edges, excluding silent dependencies from change propagation. [maintain_node_definitions, maintain_task_prompts, maintain_node_dependencies, maintain_reverse_dependencies, exclude_silent_dependencies_from_propagation, agent_storage: [maintain_workspace_targets, provide_task_prompts, provide_node_definitions], dag_storage: [access_dag_dependencies]]
- Nodes are evaluated as dirty if pending messages exist or if their source file is missing from the workspace root, generating an initial change message when missing. [node_dirty_when_messages_present, node_dirty_when_source_missing, record_change_message_when_source_missing, dag_storage: [expose_node_dirty, dirty_when_messages_present]]
- Inter-node messages and reverse dependencies are serialized to and read from per-package `.update_with_ai.textproto` files, creating files when writing and tolerating missing files on read. [serialize_pending_messages_to_proto, serialize_reverse_deps_to_proto, share_package_message_file, resolve_package_dir_for_message_file, create_message_file_if_missing, ignore_absent_message_files_on_read, update_with_ai_proto_ext: [serialize_proto_text, parse_proto_text], file_paths: [resolve_ws_path], bazel_target: [extract_node_dir_from_node]]
