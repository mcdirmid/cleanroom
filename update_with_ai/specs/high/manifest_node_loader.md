# manifest_node_loader

imports: build_graph_storage (node definition, package directory, silent dependency, star dependency), sandbox (file mappings, readable paths, writable paths, blame targets, templates)
terms (from build_graph_storage): node definition, package directory, silent dependency, star dependency
terms (from run_control): blame target
terms (from file_reader): virtual name
terms (from file_editor): template
terms (from guide_delivery): guide, step mode
terms (from dag_storage): node, dependency, propagating dependency
terms (owned): manifest resolution, synthetic definition

## Purpose

Discovers, parses, and translates build-time target manifests into runtime graph structures, node definitions, and sandbox configurations.

## Terms

- Manifest resolution: the process of reading JSON manifest files from a workspace directory and resolving all dependency edges and file paths.
- Synthetic definition: a generated node definition for a declared dependency that lacks a build manifest of its own.

## Contract

**Inputs**

- A workspace root directory and a root target label.

**Operations**

- Resolve the full dependency graph and per-node definitions starting from a root target.
- Construct a sandbox configuration from manifest data.

**Guarantees**

- Resolves declared sources, silent sources, templates, and guides for all reachable nodes.
- Computes transitive closures for star dependencies.
- Synthesizes definitions for targets lacking explicit manifests so all declared dependencies resolve cleanly.
- Maps files to virtual names with collision avoidance.

**Assumptions**

- Manifest files are accessible on disk.

## Non-concerns

- File content verification: handled by sandbox and run_control.
