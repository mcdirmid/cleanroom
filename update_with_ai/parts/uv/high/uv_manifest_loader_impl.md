<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: b0f3537055fe
-->

# uv_manifest_loader_impl implementation component

imports: agent_storage, dag_storage, file_paths, uv_manifest_ext, uv_target
implements: uv_manifest_loader

## Purpose

The uv_manifest_loader_impl implementation component discovers role definition files and package directories, synthesizes unit and role metadata into target manifests, and populates graph storage with node definitions and dependency edges.

Target execution requires transforming methodology configurations and package structures into fully qualified graph nodes and dependencies. Workspaces declare roles and component specifications across package hierarchies without depending on centralized build tools. The uv_manifest_loader_impl implementation component locates role definition files, evaluates source patterns and prompt templates, synthesizes pass-through nodes for inactive stages, and registers dependency relationships in node storage.

**Out of scope:** The uv_manifest_loader_impl implementation component does not execute build commands, drive agent turns, or resolve session file aliases; these are handled by other components.

**Delegated:** Role configuration parsing and layout conventions are delegated to uv_manifest_ext; target label normalization and package directory resolution are delegated to uv_target; workspace root path resolution is delegated to file_paths; node definitions and dependency registration are delegated to agent_storage; graph edge coordination is delegated to dag_storage.

## Types and Behavior

The uv manifest loader loads target manifests to construct graph structures and node definitions.

When resolving workspace directories, the loader anchors relative package paths against the workspace root retrieved from the file path manager. When recording declared source files and silent source files in node storage, the loader normalizes repository-relative paths across package directories and workspace roots without prepending redundant package path segments.

The uv manifest loader:

- Discovers methodology bindings by searching package directories upwards for scope configuration files, and retrieves target manifests from workspace directories for graph nodes, checking package paths and candidate configuration directories.

- Loads and decodes unit specifications and role definitions to synthesize target manifest records across unit and role dimensions.

- Synthesizes target node manifests with source files, templates, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.

- Incorporates fixed role node dependencies as declared direct dependencies across unit and role dimensions.

- Evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized target manifests.

- Resolves bare cross-package unit dependency references to their containing packages within parts workspaces across unit and role dimensions.

- Synthesizes promptless pass-through node definitions that forward dependency edges to constituent units and role dependencies when a unit's component type is not active for a role.

- Populates node storage with node definitions carrying task prompts for target nodes.

- Records declared primary source files and silent source files in node storage, normalizing repository-relative paths across package directories and workspace roots without duplicating package path segments.

- Registers declared direct dependencies, feedback dependencies, and non-propagating silent dependencies in node storage.

- Synthesizes empty node definitions for referenced dependency targets lacking manifests.
