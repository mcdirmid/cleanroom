<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T05:29:29Z
CHANGE: Add silent source file path contract, remove collaborator leakage, and align citations
CODE_HASH: deaa385ecf58
-->

# bazel_manifest_loader_impl implementation component

imports: agent_storage, bazel_manifest_ext, bazel_target, dag_storage, file_paths
implements: bazel_manifest_loader

## Intent

Target execution requires transforming build system metadata into fully qualified graph nodes and dependencies. The build system emits factored unit manifests and role manifests across workspace directories and runfiles trees. The bazel_manifest_loader_impl implementation component locates manifest files across candidate search paths, decodes unit and role schemas, evaluates source patterns and prompt templates, synthesizes pass-through nodes for inactive stages, and registers dependency relationships in agent storage.

By locating manifest files across workspace directories or runfiles trees, normalizing targets, evaluating path and prompt templates, and synthesizing pass-through definitions when role stages are inactive, the implementation provides reliable runtime configuration for build-driven workflows.

## Factored Contracts

### Contracts

- The bazel manifest loader retrieves target manifests from workspace directories for graph nodes. [retrieve_from_workspace_directories]
- The bazel manifest loader retrieves target manifests from runfiles trees for graph nodes. [retrieve_from_runfiles_trees]
- The bazel manifest loader anchors relative package directories to the workspace root. [anchor_workspace_package_paths]
- The bazel manifest loader anchors canonical package paths to candidate runfiles roots. [anchor_runfiles_package_paths]
- The bazel manifest loader loads unit manifests using bazel manifest ext. [load_unit_manifest_via_ext]
- The bazel manifest loader loads role manifests using bazel manifest ext. [load_role_manifest_via_ext]
- The bazel manifest loader loads monolithic target manifests using bazel manifest ext. [load_target_manifest_via_ext]
- The bazel manifest loader evaluates role source patterns parameterized with unit metadata. [evaluate_role_source_patterns]
- The bazel manifest loader evaluates task prompt templates parameterized with unit metadata. [evaluate_task_prompt_templates]
- The bazel manifest loader evaluates verification check templates parameterized with unit metadata. [evaluate_verification_check_templates]
- The bazel manifest loader cross-products unit dependencies with role dependencies to produce target dependencies. [crossproduct_unit_role_dependencies]
- The bazel manifest loader incorporates fixed role node dependencies as declared direct dependencies across unit and role dimensions. [incorporate_role_node_dependencies]
- The bazel manifest loader synthesizes promptless pass-through node definitions when a unit component type is not active for a role. [synthesize_promptless_passthrough_definitions]
- The bazel manifest loader populates agent storage with node definitions carrying task prompts. [populate_node_definitions_in_storage]
- The bazel manifest loader records declared primary source file paths in agent storage without duplicating package path segments. [record_source_file_paths_in_storage]
- The bazel manifest loader records silent source file paths in agent storage without duplicating package path segments. [record_silent_source_file_paths_in_storage]
- The bazel manifest loader registers declared direct dependencies in agent storage. [register_direct_dependencies_in_storage]
- The bazel manifest loader registers declared feedback dependencies in agent storage. [register_feedback_dependencies_in_storage]
- The bazel manifest loader registers declared silent dependencies as non-propagating dependencies in agent storage. [register_silent_dependencies_in_storage]
- The bazel manifest loader synthesizes fallback node definitions for referenced targets lacking manifests. [synthesize_fallback_definitions_for_missing_targets]

## Woven Contracts

- Package path resolution anchors relative package directories to the workspace root retrieved from the file path manager and canonical paths to candidate runfiles roots. \[anchor_workspace_package_paths, anchor_runfiles_package_paths, file_paths: [resolve_workspace_path]\]
- Target manifests are discovered across candidate paths in workspace directories or runfiles trees and loaded via bazel manifest ext. \[retrieve_from_workspace_directories, retrieve_from_runfiles_trees, anchor_workspace_package_paths, anchor_runfiles_package_paths, load_target_manifest_via_ext, bazel_manifest_ext: [parse_monolithic_target_fields], bazel_manifest_loader: [retrieve_manifest_for_node], file_paths: [resolve_workspace_path]\]
- Unit and role manifests decode metadata schemas and synthesize target records by evaluating source patterns and prompt templates. \[load_unit_manifest_via_ext, load_role_manifest_via_ext, evaluate_role_source_patterns, evaluate_task_prompt_templates, evaluate_verification_check_templates, crossproduct_unit_role_dependencies, incorporate_role_node_dependencies, synthesize_promptless_passthrough_definitions, bazel_manifest_ext: [parse_unit_label, parse_role_label, parse_node_deps], bazel_manifest_loader: [retrieve_manifest_for_node, synthesize_passthrough_definitions]\]
- Manifest loading populates agent storage with node definitions, declared source paths and silent source paths normalized without duplicate package segments, and graph dependency edges while synthesizing definitions for missing targets. \[populate_node_definitions_in_storage, record_source_file_paths_in_storage, record_silent_source_file_paths_in_storage, register_direct_dependencies_in_storage, register_feedback_dependencies_in_storage, register_silent_dependencies_in_storage, synthesize_fallback_definitions_for_missing_targets, agent_storage: [maintain_workspace_targets, provide_node_definitions], dag_storage: [access_dag_dependencies], bazel_manifest_loader: [resolve_manifests_into_nodes, resolve_manifests_into_definitions, resolve_manifests_into_prompts, populate_agent_storage, resolve_direct_dependencies_graph_edges, resolve_silent_dependencies_non_propagating, synthesize_missing_dependency_definitions]\]
