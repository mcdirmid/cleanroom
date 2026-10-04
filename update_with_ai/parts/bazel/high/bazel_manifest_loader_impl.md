# bazel_manifest_loader_impl implementation component

imports: agent_storage, bazel_manifest_ext, bazel_target, dag_storage, file_paths
implements: bazel_manifest_loader

## Purpose

The bazel_manifest_loader_impl implementation component discovers manifest JSON files in workspace directories and runfiles trees, synthesizes unit and role metadata into target manifests, and populates graph storage with node definitions and dependency edges.

Target execution requires transforming build system metadata into fully qualified graph nodes and dependencies. The build system emits factored unit manifests and role manifests across workspace directories and runfiles trees. The bazel_manifest_loader_impl implementation component locates manifest files across candidate search paths, decodes unit and role schemas using bazel manifest ext, evaluates source patterns and prompt templates, synthesizes pass-through nodes for inactive stages, and registers dependency relationships in agent storage.

**Out of scope:** The bazel_manifest_loader_impl implementation component does not execute build commands, drive agent turns, or resolve session file aliases; these are handled by other components.

## Types and Behavior

The bazel manifest loader loads target manifests to construct graph structures and node definitions.

When resolving workspace directories, the loader anchors relative package paths against the workspace root retrieved from the file path manager (or process environment). When resolving runfiles trees, the loader anchors canonical relative package paths against candidate runfiles roots. When recording declared source files and silent source files in agent storage, the loader normalizes repository-relative paths across package directories and workspace roots without prepending redundant package path segments.

The bazel manifest loader:

- Retrieves target manifests from workspace directories or runfiles trees for graph nodes, checking package paths and candidate runfile directories.

- Loads unit manifests and role manifests using bazel manifest ext to synthesize target manifest records across unit and role dimensions.

- Synthesizes target node manifests with source files, templates, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.

- Incorporates fixed role node dependencies as declared direct dependencies across unit and role dimensions.

- Evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized target manifests.

- Synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.

- Populates agent storage with node definitions carrying task prompts for target nodes.

- Records declared primary source files and silent source files in agent storage, normalizing repository-relative paths across package directories and workspace roots without duplicating package path segments.

- Registers declared direct dependencies, feedback dependencies, and non-propagating silent dependencies in agent storage.

- Synthesizes empty node definitions for referenced dependency targets lacking manifests.
