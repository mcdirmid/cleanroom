<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T05:18:30Z
CHANGE: Streamline manifest resolution to eliminate redundant dependency statements
CODE_HASH: 225982be0fea
-->

# bazel_manifest_loader interface component

imports: agent_storage, bazel_target, dag_storage

## Purpose

The bazel_manifest_loader interface component discovers and translates build system target manifests into runtime graph structures and node definitions.

Target execution requires resolving build metadata into executable nodes and persistent graph definitions. The build system emits unit, role, and target manifests describing component types, source path patterns, prompt templates, and dependencies. The bazel_manifest_loader interface component reads these manifests, synthesizes target manifest records, populates node definitions in agent storage, and registers graph dependency edges in dag storage using Bazel targets.

**Out of scope:** The bazel_manifest_loader interface component does not orchestrate agent turns, resolve session file aliases, or configure session read-write file sets; these are handled by other components.

## Types and Behavior

A *target manifest* is a build artifact written by the build system carrying node reference fields and file path fields for a workspace target, including target node label, task prompt, declared source file, silent source files, template, direct dependencies, silent dependencies, star dependencies, feedback dependencies, guide target, and verification check.

A system's *bazel manifest loader* resolves manifests into graph structures and node definitions.

The bazel manifest loader:

- Retrieves the manifest for a node.

- Resolves manifests into target nodes, node definitions, and task prompts, populating agent storage.

- Resolves declared direct dependencies into dependency graph edges in agent storage.

- Resolves declared silent dependencies as non-propagating dependencies in agent storage.

- Synthesizes definitions for declared dependencies lacking explicit manifests.

- Synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.
