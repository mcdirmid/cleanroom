# manifest_node_loader_impl

fulfills: manifest_node_loader
imports: build_graph_storage (node definition, package directory, silent dependency, star dependency), sandbox (file mappings, readable paths, writable paths, blame targets, templates)
terms (from manifest_node_loader): manifest resolution, synthetic definition
terms (from build_graph_storage): node definition, package directory, silent dependency, star dependency
terms (from run_control): blame target
terms (from file_reader): virtual name
terms (from file_editor): template
terms (from guide_delivery): guide, step mode
terms (from dag_storage): node, dependency, propagating dependency

## Deltas

- Reads target manifest JSON files using deterministic path conventions (`<package>/<target>.manifest.json`).
- Resolves relative path mappings to absolute filesystem paths under the workspace root.
- Generates synthetic manifests for external dependencies and non-cleanroom targets.

## Non-concerns

- Dynamic rebuild of manifests: manifests are assumed pre-built.
