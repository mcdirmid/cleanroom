# bazel_manifest_loader_impl implementation component

imports: dag_storage, agent_node_config, agent_file_alias, bazel_target, agent_storage, json_manifest_ext
implements: bazel_manifest_loader

## Purpose

The bazel_manifest_loader_impl implementation component loads JSON format manifests, resolves node references and package-relative file paths, computes star-dependency transitive source closures, derives minimal file aliases, and constructs target node configurations.

Target manifests emitted by Bazel record target labels, source files, and dependencies using workspace-relative or package-relative representations. Executing agents and maintaining dependency graphs requires transforming these declarative records into fully qualified graph nodes, resolving relative source files, and constructing isolated node configurations. The bazel_manifest_loader_impl implementation component parses JSON manifest files, normalizes node references, computes transitive source closures for star dependencies, resolves guide and blame mappings, and populates graph storage with complete node definitions.

**Out of scope:** The bazel_manifest_loader_impl implementation component does not execute build commands, drive agent turns, or manage file modification permissions during runs; these are handled by other components.

## Types and Behavior

The bazel manifest loader loads target manifests to construct graph structures and node configurations.

The bazel manifest loader:

- Retrieves target manifests from workspace directories or runfiles trees for graph nodes.

- Parses manifests from JSON files written by the build system in workspace directories or runfiles trees into json manifests.

- Extracts manifest node references from a json manifest and normalizes them into canonical nodes.

- Extracts manifest file paths from a json manifest and resolves them relative to target package directories.

- Resolves a target node's declared source file, template, and silent source files into read-write files and startup template mappings in its node configuration.

- Resolves declared direct dependencies into read-only files, and transitive star-dependency closures into read-only files in the target node configuration by retrieving declared source files from corresponding dependency node manifests.

- Registers declared silent dependencies as non-propagating dependencies in graph storage, excluding their source files from dependent node configurations.

- Resolves declared guide targets into task guides from declared source files of referenced guide manifests, excluding step-mode guide source files from declared read-only files.

- Maps declared source files of feedback dependencies to blame targets associated with their owning dependency nodes in the target node configuration.

- Derives file aliases for all accessible workspace files.

- Synthesizes node definitions for referenced dependency targets lacking manifests.

- Resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.

- Synthesizes target node manifests with templates, template parameters, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.

- Evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized nodes.

- Synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.
