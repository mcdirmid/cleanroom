# bazel_node_config_impl implementation component

imports: agent_config, bazel_manifest_loader, dag_storage, file_paths, tool_provider
implements: agent_node_config, agent_file_alias

## Purpose

The bazel_node_config_impl implementation component realizes node configuration parameters and alias management for target nodes in agent sessions.

Multi-turn agent execution within Bazel workspaces requires binding node-specific manifest metadata to virtual session boundaries. Individual sessions require hermetic file isolation, mapping relative target sources to read-write paths, expanding direct and transitive dependencies to read-only paths, and isolating local host paths from language model visibility. The bazel_node_config_impl implementation component resolves the active target nodes' manifests via the manifest loader, constructs declared file sets and guide bindings for the node config, and maintains minimal unambiguous file aliases and path masking for the alias manager.

**Out of scope:** The bazel_node_config_impl implementation component does not parse JSON files, drive agent turns, or manage file modification permissions during runs; these are handled by other components.

## Types and Behavior

The node config and alias manager realize session configuration and file alias resolution for the target nodes presented by the role config.

The node config caches per node info loaded for active nodes from the role config, checking the role config version to unload cached per node info when nodes are no longer being cleaned, and loading per node info for newly active nodes from target node manifests.

Loading per node info for a node resolves its declared source files and templates from the manifest as the node read-write files and templates, declared template parameters as the node template parameters, direct dependencies and transitive star dependencies resolved across dependency manifests as the node read-only files excluding declared silent dependencies and read-write files, whether the node allows step mode, declared guide targets as the guide file and task guide, declared feedback dependencies as blame targets mapped to their owning dependency nodes, declared verification commands as verification checks, declared source file alias relative path as the src file alias, declared verification success message, and feedback messages from graph storage as the feedback.

The node config dynamically aggregates session parameters across active nodes' per node info.

The node config dynamically provides:

- The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.

- The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.

- The session template parameters combining template parameters across the active nodes.

- Whether the node allows step mode resolved when the session contains exactly one node.

- Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.

- The session guide file and task guide from the single active node when guide step mode is active.

- The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.

- The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.

- The session src file alias by node mapping each active node to the relative path of its declared source file alias.

- The session verification success message from the active node when the session contains exactly one node.

- The session feedback combining feedback messages retrieved from graph storage across the active nodes.

- The session per node info by node mapping each active node to its per node info.

The alias manager maintains virtual file addressing and path masking for the active session, checking the role config version to update file aliases and path masking for the active nodes retrieved from the role config.

The alias manager:

- Generates file aliases with relative paths for all accessible workspace files associated with the active nodes.

- Converts wire type strings to file aliases, matching relative paths to corresponding file aliases and producing unbound files when relative paths are unmapped.

- Sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.
