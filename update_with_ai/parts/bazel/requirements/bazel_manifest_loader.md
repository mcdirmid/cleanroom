# bazel_manifest_loader interface component

imports: agent_storage, bazel_target, dag_storage, agent_file_alias, agent_node_config

## Assumptions and Requirements

### Requirements

1. The bazel manifest loader retrieves the manifest for a node in dag storage.
2. A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations, populating the agent storage.
3. A manifest loader resolves declared source files and templates into read-write files and templates in node configurations.
4. A manifest loader resolves declared silent source files into read-write files while excluding them from dependent read-only files.
5. A manifest loader resolves declared direct dependencies into read-only files, and star dependencies into transitive read-only file closures.
6. A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
7. A manifest loader resolves declared guide targets into task guides in node configurations.
8. A manifest loader resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in node configurations.
9. A manifest loader generates node configurations with minimally disambiguated file aliases.
10. A manifest loader synthesizes definitions for declared dependencies lacking explicit manifests.
11. A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.

## Grounding Facts

### Knowledge Needed

- Node manifests in workspace or runfiles.
- Source files, templates, silent sources, and guide targets.
- Direct dependencies, star dependencies, and silent dependencies.
- Feedback dependencies and blame targets.
- Active component types per role.

### Actions Needed

- Retrieve manifest for target node.
- Resolve manifests into node definitions, prompts, and configurations.
- Populate `agent_storage` and `dag_storage`.
- Synthesize fallback and promptless pass-through node definitions.
