<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-05T05:19:03Z
CHANGE: Add delegated statement, align session config ontology, eliminate regex and cache mechanics, and decompose parameter catalog
CODE_HASH: ab2d297ab584
-->

# bazel_node_config_impl implementation component

imports: agent_config, bazel_manifest_loader, dag_storage, file_paths, tool_provider
implements: agent_node_config, agent_file_alias

## Purpose

The bazel_node_config_impl implementation component realizes node configuration parameters and alias management for target nodes in agent sessions.

Multi-turn agent execution within Bazel workspaces requires binding node-specific manifest metadata to virtual session boundaries. Individual sessions require hermetic file isolation, mapping relative target sources to read-write paths, expanding direct and transitive dependencies to read-only paths, and isolating local host paths from language model visibility. The bazel_node_config_impl implementation component resolves the active target nodes' manifests via the manifest loader, constructs declared file sets and guide bindings for the node config, and maintains minimal unambiguous file aliases and path masking for the alias manager.

**Out of scope:** The bazel_node_config_impl implementation component does not parse JSON files, drive agent turns, or manage file modification permissions during runs; these are handled by other components.

**Delegated:** Target manifest retrieval is delegated to bazel_manifest_loader; graph storage and feedback messages are delegated to dag_storage; path validation and workspace root resolution are delegated to file_paths; agent step mode permissions are delegated to agent_config; wire parameter conversions are delegated to tool_provider.

## Types and Behavior

The session config and alias manager realize session configuration and file alias resolution for the target nodes presented by the role config.

The session config provides configuration parameters for active nodes in the role config, resolving parameters from target node manifests.

When resolving parameters for a node from its manifest:

- Declared source files and templates provide read-write files and templates, with declared template parameters providing template bindings.

- Direct dependencies and transitive star dependencies across dependency manifests provide read-only files, excluding declared silent dependencies and read-write files.

- Declared feedback dependencies provide blame targets mapped to their owning dependency nodes, declared verification commands provide verification checks, and graph storage provides incoming feedback messages.

When a node declares a guide target, the session config retrieves the guide target's manifest via the manifest loader. Guide markdown content is loaded by reading the guide file resolved across workspace and runfiles trees using candidate relative paths derived from the guide target manifest's declared source file or the guide target label. An unbound guide file is provided using the relative filename derived from the guide target label.

Parsing a node guide from guide markdown extracts the guide summary from content preceding the first section heading and under any heading titled `Summary`, captures verification failure instructions when a section heading begins with `Verification failure`, and creates sequential step sections for subsequent level-two headings while excluding sections whose title begins with `Summary`, `Lint checks`, or `Verification failure`.

The session config dynamically aggregates session parameters across active nodes' per node info.

The session config dynamically provides:

- The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.

- The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.

- The session template parameters combining template parameters across the active nodes.

- Step mode eligibility, permitted for single-node sessions when the target node allows step mode.

- Step mode activation, active when permitted by agent config, the session is eligible for step mode, and session feedback is absent.

- The session guide file and task guide from the single active node when guide step mode is active.

- The session blame targets by node mapping each active node to its declared blame targets.

- The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.

- The session src file alias by node mapping each active node to the relative path of its declared source file alias.

- The session verification success message from the active node when the session contains exactly one node.

- The session feedback combining feedback messages retrieved from graph storage across the active nodes.

- The session per node info by node mapping each active node to its per node info.

The alias manager maintains virtual file addressing and path masking for accessible workspace files associated with the active nodes in the role config.

The alias manager:

- Generates file aliases with relative paths for all accessible workspace files associated with the active nodes.

- Converts wire type strings to file aliases, matching relative paths to corresponding file aliases and producing unbound files when relative paths are unmapped.

- Sanitizes output text by masking occurrences of workspace root path prefixes and execution root path prefixes, replacing matching host paths with relative workspace paths.
