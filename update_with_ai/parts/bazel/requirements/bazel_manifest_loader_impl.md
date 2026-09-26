# bazel_manifest_loader_impl implementation component

imports: agent_storage, bazel_manifest_loader, bazel_target, dag_storage, agent_file_alias, json_manifest_ext, agent_node_config
implements: bazel_manifest_loader

## Assumptions and Requirements

### Requirements

1. The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
2. A manifest loader parses JSON manifests using the filesystem into json manifest records.
3. A manifest loader normalizes node references into canonical nodes.
4. A manifest loader resolves package-relative file paths against target package directories.
5. A manifest loader maps declared source files, templates, and silent source files into read-write files and template entries.
6. A manifest loader expands direct dependencies and star dependencies into read-only files.
7. A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
8. A manifest loader resolves guide targets into task guides and feedback dependencies into blame targets.
9. A manifest loader derives file aliases for all accessible workspace files.
10. A manifest loader synthesizes node definitions for referenced dependency targets lacking manifests.
11. A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
12. A manifest loader synthesizes target node manifests with templates, template parameters, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.
13. A manifest loader evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized nodes.
14. A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.

## Grounding Facts

### Knowledge Needed

- Manifest file paths in workspace or runfiles trees.
- JSON manifest schema and contents.
- Unit manifests and role manifests.
- Package directories and file paths.
- Active component types.

### Actions Needed

- Load and parse JSON manifests.
- Normalize node references and resolve package paths.
- Expand dependencies into read-only files and blame targets.
- Populate `agent_storage` and synthesize pass-through definitions.
