# bazel_node_config_impl implementation component

imports: agent_config, bazel_manifest_loader, dag_storage, file_paths, tool_provider
implements: agent_node_config, agent_file_alias

## Purpose

The bazel_node_config_impl implementation component realizes node configuration parameters and alias management for target nodes in agent sessions.

Multi-turn agent execution within Bazel workspaces requires binding node-specific manifest metadata to virtual session boundaries. Individual sessions require hermetic file isolation, mapping relative target sources to read-write paths, expanding direct and transitive dependencies to read-only paths, and isolating local host paths from language model visibility. The bazel_node_config_impl implementation component resolves the active target nodes' manifests via the manifest loader, constructs declared file sets and guide bindings for the node config, and maintains minimal unambiguous file aliases and path masking for the alias manager.

**Out of scope:** The bazel_node_config_impl implementation component does not parse JSON files, drive agent turns, or manage file modification permissions during runs; these are handled by other components.

## Types and Behavior

The node config and alias manager realize session configuration and file alias resolution for the target nodes presented by the cleaned nodes using the bazel manifest loader.

When initialized for an agent session, the node config and alias manager retrieve the active nodes from the cleaned nodes and load target manifests.

The node config provides session parameters resolved from the target node manifests.

The node config provides:

- Declared source files and templates from the manifests as the session read-write files and templates, mapping read-write files to initial file content.

- Declared template parameters from the target node manifests as the session template parameters.

- Declared direct dependencies and transitive star dependencies resolved across dependency manifests as the session read-only files, excluding declared silent dependencies and their source files, and excluding files present in the session read-write files.

- Whether the nodes allow step mode, resolved from the target node manifests.

- Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.

- Declared guide targets from the target node manifest as the guide file and task guide when guide step mode is active.

- Declared feedback dependencies from the manifests as blame targets mapped to their owning dependency nodes, and blame targets by node mapping each session node to its declared blame targets.

- Declared verification checks from the manifests' verification commands as the session verification checks, and verification checks by node mapping each session node to its verification checks.

- Declared src file alias by node mapping each session node to the relative path of its declared source file alias.

- Declared verification success message from the target node manifest when the session contains exactly one node as the session verification success message.

- Declared feedback messages retrieved from graph storage for the session nodes as the session feedback.

The alias manager maintains virtual file addressing and path masking for the active session.

The alias manager:

- Generates file aliases with relative paths for all accessible workspace files associated with the active nodes.

- Converts wire type strings to file aliases, matching relative paths to corresponding file aliases and producing unbound files when relative paths are unmapped.

- Sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.
