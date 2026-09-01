# manifest_node_loader_impl

imports: dag_storage, sandbox, virtual_file_name, node_id_utils, build_graph_storage, manifest_node_loader, build_agent_config, json_manifest_ext
types from dag_storage: node, dependency, propagating dependency
types from sandbox: sandbox configuration
types from virtual_file_name: virtual file name, virtual file mapping, virtual file mapper factory
types from node_id_utils: node identifier utility
types from build_graph_storage: build graph storage, node definition, task prompt
types from manifest_node_loader: manifest loader, manifest
types from build_agent_config: config target
types from json_manifest_ext: json manifest, manifest node reference, manifest file path
implements: manifest loader

## Purpose

Loads external JSON format manifests, resolves node references and package-relative file paths, computes star-dependency transitive source closures, and derives minimal virtual file mappings.

## Behavior

- A *manifest loader* parses *manifests* from JSON files written by the build system in workspace directories or runfiles trees into *json manifests*.
- A *manifest loader* extracts *manifest node references* from a *json manifest* and normalizes them into canonical *nodes* using a *node identifier utility*.
- A *manifest loader* extracts *manifest file paths* from a *json manifest* and resolves them relative to target package directories extracted by a *node identifier utility*.
- A *manifest loader* resolves a target node's declared source file, template, and silent source files into writable workspace files and startup template mappings in its *sandbox configuration*.
- A *manifest loader* resolves declared direct dependencies and transitive star-dependency closures into read-only files in the target *sandbox configuration* by retrieving declared source files from corresponding dependency node *manifests*.
- A *manifest loader* registers declared silent dependencies as non-propagating *dependencies* in *build graph storage*, excluding their source files from dependent *sandbox configurations*.
- A *manifest loader* resolves declared guide targets into task guides from declared source files of referenced guide *manifests*, excluding step-mode guide source files from declared read-only files.
- A *manifest loader* maps declared source files of feedback dependencies to blame targets associated with their owning dependency *nodes* in the target *sandbox configuration*.
- A *manifest loader* derives *virtual file mappings* for all accessible workspace files using a *virtual file mapper factory*.
