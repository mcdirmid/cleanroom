<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: ebd1cedd1114
-->

# bazel_manifest_loader interface component

imports: agent_storage, bazel_target, dag_storage

## Intent

Target execution requires resolving build metadata into executable nodes and persistent graph definitions. The build system emits unit, role, and target manifests describing component types, source path patterns, prompt templates, and dependencies. The bazel_manifest_loader interface component reads these manifests, synthesizes target manifest records, populates node definitions in agent storage, and registers graph dependency edges in dag storage using Bazel targets.

By synthesizing unit and role manifests into target records, translating declared dependencies into DAG edges, and synthesizing pass-through definitions when role stages are inactive, the loader translates static build manifests into active execution state.

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
- The bazel manifest loader retrieves the manifest for a node. [retrieve_manifest_for_node]
- The bazel manifest loader resolves manifests into target nodes. [resolve_manifests_into_nodes]
- The bazel manifest loader resolves manifests into dependencies. [resolve_manifests_into_dependencies]
- The bazel manifest loader resolves manifests into node definitions. [resolve_manifests_into_definitions]
- The bazel manifest loader resolves manifests into task prompts. [resolve_manifests_into_prompts]
- The bazel manifest loader populates agent storage with resolved structures. [populate_agent_storage]
- The bazel manifest loader resolves declared direct dependencies into dependency graph edges in agent storage. [resolve_direct_dependencies_graph_edges]
- The bazel manifest loader resolves declared silent dependencies as non-propagating dependencies in agent storage. [resolve_silent_dependencies_non_propagating]
- The bazel manifest loader synthesizes definitions for declared dependencies lacking explicit manifests. [synthesize_missing_dependency_definitions]
- The bazel manifest loader synthesizes promptless pass-through node definitions when a unit component type is not active for a role. [synthesize_passthrough_definitions]
- Synthesized pass-through node definitions act as graph dependencies without propagating changes. [passthrough_definitions_non_propagating]

## Woven Contracts

- Manifest loading retrieves build manifests and populates agent storage with nodes, dependencies, definitions, and prompts. \[retrieve_manifest_node_supplied, retrieve_manifest_for_node, resolve_manifests_into_nodes, resolve_manifests_into_dependencies, resolve_manifests_into_definitions, resolve_manifests_into_prompts, populate_agent_storage, agent_storage: [maintain_workspace_targets, provide_node_definitions]\]
- Direct and silent dependencies populate dependency graph edges in agent storage, recording silent dependencies as non-propagating edges. \[resolve_direct_dependencies_graph_edges, resolve_silent_dependencies_non_propagating, dag_storage: [access_dag_dependencies]\]
- Missing dependency manifests and inactive role stages synthesize pass-through graph definitions that participate in ordering without propagating modifications. \[synthesize_missing_dependency_definitions, synthesize_passthrough_definitions, passthrough_definitions_non_propagating, dag_storage: [dependencies_form_dag]\]
