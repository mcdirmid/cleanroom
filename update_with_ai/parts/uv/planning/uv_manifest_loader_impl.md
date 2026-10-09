<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: eb6416b40da2
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# uv_manifest_loader_impl implementation component

imports: agent_storage, dag_storage, file_paths, uv_manifest_ext, uv_target
implements: uv_manifest_loader

## Intent

Target execution requires transforming methodology configurations and package structures into fully qualified graph nodes and dependencies. Workspaces declare roles and component specifications across package hierarchies without depending on centralized build tools. The uv_manifest_loader_impl implementation component locates role definition files, evaluates source patterns and prompt templates, synthesizes pass-through nodes for inactive stages, and registers dependency relationships in node storage.

By resolving package directories against the workspace root, parsing role configuration TOML files, and mapping unit dependencies across lifecycle stages, the implementation populates agent storage with concrete execution targets and dependency structures.

## Factored Contracts

### Contracts

- The uv manifest loader discovers methodology bindings by searching package directories upwards for scope configuration files and locates role definition files. [locate_role_definitions]
- The uv manifest loader evaluates role source patterns parameterized with unit metadata. [evaluate_source_patterns]
- The uv manifest loader evaluates role prompt templates parameterized with unit metadata. [evaluate_prompt_templates]
- The uv manifest loader normalizes repository-relative paths without duplicating package paths. [normalize_repository_paths]
- The uv manifest loader resolves bare cross-package unit dependency references to their containing packages within parts workspaces. [resolve_cross_package_units]
- The uv manifest loader forwards constituent unit dependencies and role dependencies for inactive pass-through nodes. [forward_pass_through_dependencies]
- The uv manifest loader synthesizes empty node definitions for referenced targets lacking explicit definitions. [synthesize_empty_definitions]

### Woven Contracts

- Locating role definitions and evaluating parameterized patterns synthesizes target manifests and populates agent storage, resolving cross-package references and forwarding pass-through dependencies. [locate_role_definitions, evaluate_source_patterns, evaluate_prompt_templates, normalize_repository_paths, resolve_cross_package_units, forward_pass_through_dependencies, uv_manifest_loader: [resolve_manifests_into_nodes, resolve_manifests_into_definitions, resolve_manifests_into_prompts, populate_agent_storage]]
- Missing dependency manifests synthesize empty graph definitions in agent storage to maintain graph reachability. [synthesize_empty_definitions, uv_manifest_loader: [synthesize_missing_dependency_definitions]]

## Grounding

### Knowledge Provisions

- Target manifest synthesis and graph loading from role definitions and package structures. [uv_manifest_loading_implementation]

### Inherited Deferred Requirements

- Role definition discovery and package specification reading.
  - Grounded: [uv_manifest_ext: [package_directory_conventions], file_paths: [path_resolution_service]]
- Parsing role definition TOML schemas and component classifications.
  - Grounded: [uv_manifest_ext: [role_manifest_parsing, component_type_classification]]
- Evaluation of role path patterns and prompt templates against unit attributes.
  - Grounded: [uv_manifest_ext: [role_manifest_parsing]]
- Populating target definitions, source file paths, and dependency edges in agent and dag storage.
  - Grounded: [agent_storage: [agent_storage_service], dag_storage: [dag_storage_service]]

### Knowledge Requirements

- Locating role definition configuration files across the workspace.
  - Grounded: [file_paths: [path_resolution_service], uv_manifest_ext: [package_directory_conventions]]
- Evaluating source and prompt templates against unit attributes.
  - Grounded: [uv_manifest_ext: [role_manifest_parsing]]
- Registering node definitions and dependency edges in graph storage.
  - Grounded: [agent_storage: [agent_storage_service], dag_storage: [dag_storage_service]]
