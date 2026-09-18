# bazel_asm assembly component

assembles: bazel_manifest_loader_impl, bazel_node_config_impl, bazel_storage_impl, bazel_target_impl, file_paths_impl
imports: agent_config, bazel_target_labels_ext, filesystem_ext, json_manifest_ext, loop_node_cleaner, tool_provider, update_with_ai_proto_ext
implements: agent_file_alias, agent_node_config, agent_storage, bazel_manifest_loader, bazel_target, dag_storage, file_paths

## Purpose

The bazel_asm assembly component aggregates workspace manifest loading, dependency graph storage, message persistence, target resolution, file paths resolution, and node configuration implementations into a unified Bazel workspace subsystem assembly.

Building an autonomous multi-agent development environment requires integrating build graph parsing, persistent message delivery, topological target execution, and sanitized file alias configuration into a cohesive Bazel subsystem. Fragmented workspace configuration forces callers to orchestrate individual Bazel infrastructure components imperatively, introducing initialization order defects and incomplete workspace bindings. The bazel_asm assembly component unifies these implementations into a dedicated assembly, realizing workspace contracts while propagating unclosed service dependencies to the root program assembly.

**Out of scope:** The bazel_asm assembly component does not parse command-line options, define remote provider communication protocols, manage host operating system processes, or assemble agent, DAG, and sandbox subsystems; these are handled by other components.

## Types and Behavior

The *bazel assembly* unites the Bazel workspace implementations into a cohesive subsystem. The bazel assembly initializes its constituent implementations recursively, registering all singleton services with the system lifecycle prototype to achieve interface closure across Bazel workspace contracts.

The bazel assembly aggregates the following constituents:

- The bazel manifest loader implementation from bazel_manifest_loader_impl, closing the bazel manifest loader interface to parse JSON manifests, resolve node references, and compute dependency closures.

- The bazel storage implementation from bazel_storage_impl, closing the agent storage and dag storage interfaces to provide in-memory graph indexing and durable message and reverse dependency persistence.

- The bazel target implementation from bazel_target_impl, closing the bazel target interface to normalize target labels and resolve package directory paths.

- The bazel node config implementation from bazel_node_config_impl, closing the agent node config and agent file alias interfaces to configure target session boundaries and resolve sanitized file aliases.

- The file paths implementation from file_paths_impl, closing the file paths interface to create, validate, and resolve path representations against the physical workspace root.
