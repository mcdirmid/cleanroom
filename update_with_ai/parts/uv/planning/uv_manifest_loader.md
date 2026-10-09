<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: d9d953f8b4b8
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# uv_manifest_loader interface component

imports: agent_storage, dag_storage, uv_target, agent_file_alias

## Intent

Target execution requires resolving methodology configurations and package layouts into executable nodes and persistent graph definitions. Cleanroom workspaces declare roles, patterns, prompts, and dependencies in configuration files rather than hard-coded build rules. The uv_manifest_loader interface component reads these definitions, synthesizes target manifest records, populates node definitions in node storage, and registers graph dependency edges in graph storage.

By synthesizing unit specifications and role definitions into target records, translating declared dependencies into DAG edges, and synthesizing pass-through definitions when role stages are inactive, the loader translates static methodology configurations into active execution state.

## Factored Contracts

### Typing

- A target manifest is a build artifact carrying node reference fields and file path fields for a workspace target.
- A target manifest includes a target node label.
- A target manifest includes a task prompt.
- A target manifest includes a declared source file.
- A target manifest includes silent source files.
- A target manifest includes a template.
- A target manifest includes direct dependencies.
- A target manifest includes silent dependencies.
- A target manifest includes star dependencies.
- A target manifest includes feedback dependencies.
- A target manifest includes a guide target.
- A target manifest includes a verification check.

### Contracts

- A caller supplies a node when retrieving a manifest. [retrieve_manifest_node_supplied]
- The uv manifest loader retrieves the manifest for a node. [retrieve_manifest_for_node]
- The uv manifest loader resolves manifests into target nodes. [resolve_manifests_into_nodes]
- The uv manifest loader resolves manifests into node definitions. [resolve_manifests_into_definitions]
- The uv manifest loader resolves manifests into task prompts. [resolve_manifests_into_prompts]
- The uv manifest loader populates agent storage with resolved structures. [populate_agent_storage]
- The uv manifest loader resolves declared direct dependencies into dependency graph edges in agent storage. [resolve_direct_dependencies_graph_edges]
- The uv manifest loader resolves declared silent dependencies as non-propagating dependencies in agent storage. [resolve_silent_dependencies_non_propagating]
- The uv manifest loader synthesizes definitions for declared dependencies lacking explicit manifests. [synthesize_missing_dependency_definitions]
- The uv manifest loader synthesizes promptless pass-through node definitions when a unit component type is not active for a role. [synthesize_passthrough_definitions]
- Synthesized pass-through node definitions act as graph dependencies without propagating changes. [passthrough_definitions_non_propagating]

### Woven Contracts

- Manifest loading retrieves role configurations and populates agent storage with nodes, definitions, and prompts. [retrieve_manifest_node_supplied, retrieve_manifest_for_node, resolve_manifests_into_nodes, resolve_manifests_into_definitions, resolve_manifests_into_prompts, populate_agent_storage, agent_storage: [maintain_workspace_targets, provide_node_definitions]]
- Direct and silent dependencies populate dependency graph edges in agent storage, recording silent dependencies as non-propagating edges. [resolve_direct_dependencies_graph_edges, resolve_silent_dependencies_non_propagating, dag_storage: [access_dag_dependencies]]
- Missing dependency manifests and inactive role stages synthesize pass-through graph definitions that participate in ordering without propagating modifications. [synthesize_missing_dependency_definitions, synthesize_passthrough_definitions, passthrough_definitions_non_propagating, dag_storage: [dependencies_form_dag]]

## Grounding

### Knowledge Provisions

- Manifest loading, target record synthesis, and graph storage population. [manifest_loading_service]

### Knowledge Requirements

- Role definition discovery and package specification reading.
  - Deferred: Delegated to uv_manifest_loader_impl across workspace directories.
- Parsing role definition TOML schemas and component classifications.
  - Deferred: Delegated to uv_manifest_ext in implementation.
- Evaluation of role path patterns and prompt templates against unit attributes.
  - Deferred: Evaluated in uv_manifest_loader_impl during target record synthesis.
- Populating target definitions, source file paths, and dependency edges in agent and dag storage.
  - Deferred: Delegated to agent_storage and dag_storage in implementation.
