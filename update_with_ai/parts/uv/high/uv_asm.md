<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 2246c7585af7
-->

# uv_asm assembly component

assembles: file_paths_impl, uv_manifest_loader_impl, uv_node_config_impl, uv_target_impl
imports: agent_config, filesystem_ext, src_metadata_ext, tool_provider, uv_manifest_ext, uv_target_labels_ext
implements: agent_file_alias, agent_node_config, file_paths, uv_manifest_loader, uv_target

## Purpose

The uv_asm assembly component aggregates workspace manifest loading, target resolution, file paths resolution, and node configuration implementations into a unified Cleanroom workspace subsystem assembly.

Building an autonomous multi-agent development environment requires integrating methodology configuration parsing, topological target execution, and sanitized file alias configuration into a cohesive Cleanroom subsystem. Fragmented workspace configuration forces callers to orchestrate individual infrastructure components imperatively, introducing initialization order defects and incomplete workspace bindings. The uv_asm assembly component unifies these implementations into a dedicated assembly, realizing workspace contracts while propagating unclosed service dependencies to the root program assembly.

**Out of scope:** The uv_asm assembly component does not parse command-line options, define remote provider communication protocols, manage host operating system processes, or assemble other subsystems; these are handled by other components.

## Types and Behavior

The *uv assembly* unites the Cleanroom workspace implementations into a cohesive subsystem. The uv assembly initializes its constituent implementations recursively, registering all singleton services with the system lifecycle prototype to achieve interface closure across Cleanroom workspace contracts.

The uv assembly aggregates the following constituents:

- The uv manifest loader implementation from uv_manifest_loader_impl, closing the uv manifest loader interface to parse role definitions, resolve node references, and compute dependency closures.

- The uv target implementation from uv_target_impl, closing the uv target interface to normalize target labels and resolve package directory paths.

- The uv node config implementation from uv_node_config_impl, closing the agent node config and agent file alias interfaces to configure target session boundaries and resolve sanitized file aliases.

- The file paths implementation from file_paths_impl, closing the file paths interface to create, validate, and resolve path representations against the physical workspace root.
