# manifest_node_loader

imports: dag_storage, sandbox, virtual_file_name, node_id_utils, build_graph_storage, build_agent_config
types from dag_storage: node, dependency, propagating dependency
types from sandbox: sandbox configuration
types from virtual_file_name: virtual file name
types from node_id_utils: node identifier utility
types from build_graph_storage: build graph storage, node definition, task prompt
types from build_agent_config: config target

## Purpose

Discovers and translates build system target manifests into runtime graph structures and sandbox configurations.

Target execution requires resolving build metadata into executable nodes and virtual workspace mappings. The build system emits declarative target manifests describing source files, silent source files, dependencies, silent dependencies, guides, templates, and verification checks. Manifest node loader reads these manifests, constructs dependency graphs using node identifier utilities, and generates isolated sandbox configurations with minimally disambiguated virtual file mappings, read-write source files, and read-only dependency files.

## Types

- A *manifest loader* is a service that resolves *manifests* into graph structures and *sandbox configurations*
- A *manifest* is a structured build artifact written by the build system carrying node reference fields and file path fields for a workspace target (such as target node label, task prompt, declared source file, silent source files, template, direct dependencies, silent dependencies, star dependencies, feedback dependencies, guide target, verification check, and configuration target)

## Behavior

- A *manifest* carries node reference fields addressing target *nodes* and file path fields addressing workspace files.
- A *manifest loader* loads *manifests* to resolve target *nodes*, *dependencies*, *node definitions*, *task prompts*, *config targets*, and *sandbox configurations* using a *node identifier utility*, populating a *build graph storage*.
- A *manifest loader* resolves declared source files and templates from *manifests* into writable files and templates in a *sandbox configuration*.
- A *manifest loader* resolves declared silent source files from *manifests* into writable files in a *sandbox configuration* while excluding them from dependent read-only files.
- A *manifest loader* resolves declared direct dependencies into declared read-only files, and star dependencies into transitive read-only file closures in a *sandbox configuration*.
- A *manifest loader* resolves declared silent dependencies as non-propagating *dependencies* in a *build graph storage* while excluding their source files from read-only files.
- A *manifest loader* resolves declared guide targets into task guides in a *sandbox configuration*.
- A *manifest loader* resolves declared feedback dependencies into blame targets mapped to their owning dependency *nodes* in a *sandbox configuration*.
- A *manifest loader* resolves declared verification checks into a *sandbox configuration*.
- A *manifest loader* generates *sandbox configurations* with minimally disambiguated *virtual file names* for target *nodes*.
- A *manifest loader* synthesizes definitions for declared dependencies lacking explicit *manifests*.
