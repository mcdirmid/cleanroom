<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 8f4587055edf
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# uv_manifest_loader interface component

imports: agent_storage, dag_storage, agent_file_alias

## Purpose

The uv_manifest_loader interface component discovers and translates workspace role definitions and package structures into runtime graph structures and node definitions.

Target execution requires resolving methodology configurations and package layouts into executable nodes and persistent graph definitions. Cleanroom workspaces declare roles, patterns, prompts, and dependencies in configuration files rather than hard-coded build rules. The uv_manifest_loader interface component reads these definitions, synthesizes target manifest records, populates node definitions in node storage, and registers graph dependency edges in graph storage.

**Out of scope:** The uv_manifest_loader interface component does not orchestrate agent turns, resolve session file aliases, or configure session read-write file sets; these are handled by other components.

**Delegated:** Target prompt and node storage is delegated to agent_storage; graph node definitions and DAG relations are delegated to dag_storage; file alias types are delegated to agent_file_alias.

## Types and Behavior

A *target manifest* is a build artifact carrying node reference fields and file path fields for a workspace target, including target node label, task prompt, declared source file, silent source files, template, direct dependencies, silent dependencies, star dependencies, feedback dependencies, guide target, and verification check.

A system's *uv manifest loader* resolves manifests into graph structures and node definitions.

The uv manifest loader retrieves the manifest of a node.

The uv manifest loader resolves manifests into target nodes, node definitions, and task prompts, and resolves the declared direct dependencies into dependency graph edges in node storage.

The uv manifest loader resolves declared silent dependencies as non-propagating dependencies in node storage, and synthesizes definitions for declared dependencies that lack an explicit manifest.

The uv manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when the component type of a unit is not active for a role.
