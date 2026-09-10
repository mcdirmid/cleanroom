# bazel_node_config_impl implementation component

imports: dag_storage, dag_node_cleaner, bazel_manifest_loader, tool_provider, sandbox_guide_delivery, sandbox_file_editor, file_paths, sandbox_run_control
implements: node_config, file_alias

## Purpose

The bazel_node_config_impl implementation component realizes node configuration parameters and alias management for target nodes in agent sessions.

Multi-turn agent execution within Bazel workspaces requires binding node-specific manifest metadata to virtual session boundaries. Individual sessions require hermetic file isolation, mapping relative target sources to read-write paths, expanding direct and transitive dependencies to read-only paths, and isolating local host paths from language model visibility. The bazel_node_config_impl implementation component resolves the active target node's manifest via the manifest loader, constructs declared file sets and guide bindings for the node config, and maintains minimal unambiguous file aliases and path masking for the alias manager.

**Out of scope:** The bazel_node_config_impl implementation component does not parse JSON files, drive agent turns, or manage file modification permissions during runs; these are handled by other components.

## Types and Behavior

The node config and alias manager realize session configuration and file alias resolution for the target node presented by the cleaned node using the bazel manifest loader.

When initialized for an agent session, the node config and alias manager retrieve the active node from the cleaned node and load target manifests from the bazel manifest loader.

For the node config:

- Exposes declared source files and templates from the manifest as the session's read-write files and templates in the node config, mapping read-write files to initial file content from the edit manager.

- Exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files in the node config, excluding declared silent dependencies and their source files.

- Exposes declared guide targets from the manifest as the guide file and task guide in the node config when step mode is active, or absent if no guide is configured.

- Exposes declared feedback dependencies from the manifest as blame targets mapped to their owning dependency nodes in dag storage.

- Exposes declared verification checks from the manifest's verification command as the session's verification checks in the node config.

For the alias manager:

- Generates file aliases with minimal unambiguous short names for all accessible workspace files associated with the active node.

- Implements parameter converter for the actual type file alias and wire type string, converting short names to matching file aliases, and producing unbound files when short names are unmapped.

- Sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its minimal short name, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.
