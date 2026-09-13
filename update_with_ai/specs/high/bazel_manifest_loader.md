# bazel_manifest_loader interface component

imports: dag_storage, node_config, file_alias, bazel_target, agent_storage

## Purpose

The bazel_manifest_loader interface component discovers and translates build system target manifests into runtime graph structures and node configurations.

Target execution requires resolving build metadata into executable nodes and virtual workspace mappings. The build system emits declarative target manifests describing source files, silent source files, dependencies, silent dependencies, guides, templates, and verification checks. The bazel_manifest_loader interface component reads these manifests, constructs dependency graphs in dag storage using Bazel targets, and generates isolated node configurations with minimally disambiguated file aliases, read-write source files, and read-only dependency files.

**Out of scope:** The bazel_manifest_loader interface component does not orchestrate agent turns, execute build commands, or serialize protobuf text records; these are handled by other components.

## Types and Behavior

A *manifest* is a build artifact written by the build system carrying node reference fields and file path fields for a workspace target, including target node label, task prompt, declared source file, silent source files, template, direct dependencies, silent dependencies, star dependencies, feedback dependencies, guide target, and verification check.

The *bazel manifest loader* is a system service that resolves manifests into graph structures and node configurations.

The bazel manifest loader:

- Retrieves the manifest for a node.

- Resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using the bazel target, populating the agent storage.

- Resolves declared source files and templates from manifests into read-write files and templates in a node configuration.

- Resolves declared silent source files into read-write files in a node configuration while excluding them from dependent read-only files.

- Resolves declared direct dependencies into read-only files, and star dependencies into transitive read-only file closures in a node configuration.

- Resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.

- Resolves declared guide targets into task guides in a node configuration.

- Resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in a node configuration.

- Generates node configurations with minimally disambiguated file aliases for target nodes.

- Synthesizes definitions for declared dependencies lacking explicit manifests.
